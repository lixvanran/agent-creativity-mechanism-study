#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **判官提示词自查**（DESIGN §4.6；2026-10-21 独立复核 F5 的放行条件第 5 条）。

要证明的事（全部**逐字**判定，不是"大意一致"）：
  ❶ 协议 `PROTOCOL.md:522`「只要陈述里含有**超出问题本身**的信息（数字/阈值/名称/规则/主体关系/
     比较/归类），就当它是断言」——**逐字**在判官提示词里（带 markdown 标记与去标记两种判法都成立）。
  ❷ 协议 `PROTOCOL.md:523`「**由题面数值 + 依据包规则推导出的结论，是断言，不是复述**」——逐字在提示词里。
  ❸ 协议 `PROTOCOL.md:524`「不确定时一律答『未提及』」——逐字在提示词里。
  ❹ 协议 `PROTOCOL.md:526`「判官必须拿到题面（prompt）与结论空间 `C_t`」——逐字在提示词里，
     **且** C_t 通过 `{ct}` 槽真的传进去。
  ❺ **`C_t` 实际非空**（不是空列表、不是占位串），且每一条款空间项都出现在渲染后的提示词里。

⚠️ "逐字"的判定口径（写明，避免"看起来像"）：
   · `raw`     ：协议那一行的**原文**（含 markdown 标记）是否作为**子串**出现在提示词里；
   · `normalized`：把两侧的 `**` 与反引号**全部去掉**后是否作为子串出现。
   两种判法**都**必须为真 ⇒ 既不是"改写过"，也不是"只差一个强调号"。

用法：python3 test_judge_prompt.py
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PROTOCOL = os.environ.get("PROTOCOL", "/workspace/lab/routes/PROTOCOL.md")
DATA = os.path.join(HERE, "data", "diag_topics.json")

from evidence_index import CHECK_V2, CHECK_V2_VERSION  # noqa: E402


def _norm(s: str) -> str:
    return s.replace("**", "").replace("`", "")


def protocol_lines():
    txt = open(PROTOCOL, encoding="utf-8").read().split("\n")
    out = {}
    for i, ln in enumerate(txt, 1):
        if i in (522, 523, 524, 526):
            out[i] = ln
    return out


def extract_sentences(lines):
    """从协议原文里抽出要**逐字**比对的那几句。"""
    s522 = re.search(r"「(.+?)」", lines[522]).group(1)
    s523 = re.search(r"「(.+?)」", lines[523]).group(1)
    s524 = re.search(r"「(.+?)」", lines[524]).group(1)
    # 526：取「判官…结论空间 `C_t`」这一段（到第一个中文逗号为止）
    m = re.search(r"(判官.+?结论空间\s*`C_t`)", lines[526])
    s526 = m.group(1) if m else ""
    return dict(s522=s522, s523=s523, s524=s524, s526=s526)


def render_prompt(topic, claims):
    from evidence_index import EvidenceIndex
    evi = EvidenceIndex(topic["topic_id"], topic["ask"], topic["items"],
                        topic.get("conclusion_space", []))
    lst = "\n".join("%d. %s" % (j + 1, c) for j, c in enumerate(claims))
    return CHECK_V2.format(n=len(claims), ask=evi.ask, ct=evi.ct_text(),
                            ev=evi.numbered_text(), claims=lst)


def check():
    out = {"protocol": PROTOCOL, "check_v2_version": CHECK_V2_VERSION}
    lines = protocol_lines()
    s = extract_sentences(lines)
    out["protocol_sentences"] = s
    out["protocol_raw_lines"] = {str(k): v.strip() for k, v in lines.items()}

    data = json.load(open(DATA, encoding="utf-8"))
    topic = data["topics"][0]
    claims = ["普通图书借阅期限为 30 天", "读者证有效期为 3 年"]
    prompt = render_prompt(topic, claims)
    out["rendered_prompt"] = prompt

    # ── ❶–❹ 逐字在提示词里 ──
    np_ = _norm(prompt)
    out["verbatim"] = {}
    for key in ("s522", "s523", "s524", "s526"):
        raw = s[key]
        out["verbatim"][key] = {
            "sentence": raw,
            "raw_in_prompt": raw in prompt,
            "normalized_in_prompt": _norm(raw) in np_,
        }
    # 任务书引文形态（:526 带反引号、不带 **）：单独再判一次
    task_q526 = "判官必须拿到题面（prompt）与结论空间 `C_t`"
    out["verbatim"]["s526_taskbook_quote"] = {
        "sentence": task_q526,
        "raw_in_prompt": task_q526 in prompt,
        "normalized_in_prompt": _norm(task_q526) in np_,
    }
    # 任务书引文形态（:522 去掉 markdown 标记）
    task_q522 = _norm(s["s522"])
    out["verbatim"]["s522_taskbook_quote"] = {
        "sentence": task_q522,
        "raw_in_prompt": task_q522 in prompt,
        "normalized_in_prompt": task_q522 in np_,
    }

    # ── ❺ C_t 实际非空 ──
    ct = topic.get("conclusion_space") or []
    out["ct"] = {
        "topic_id": topic["topic_id"],
        "n_conclusion_space": len(ct),
        "is_empty_list": len(ct) == 0,
        "items": ct,
        "all_items_in_prompt": all(c in prompt for c in ct),
        "placeholder_absent": "（本题未提供结论空间）" not in prompt,
        "ask_in_prompt": topic["ask"] in prompt,
        "evidence_ids_in_prompt": all("[%s]" % it["id"] in prompt for it in topic["items"]),
    }

    out["PASS"] = bool(
        # 协议四句：原文（连 markdown 强调标记）逐字在提示词里 **且** 归一化后也在
        all(v["raw_in_prompt"] and v["normalized_in_prompt"]
            for k, v in out["verbatim"].items()
            if k in ("s522", "s523", "s524", "s526"))
        # 任务书 :526 引文形态（去 **、保留 `C_t`）必须逐字在提示词里
        and out["verbatim"]["s526_taskbook_quote"]["raw_in_prompt"]
        # 任务书 :522 引文形态（去 markdown 标记）必须**归一化后**逐字在提示词里
        and out["verbatim"]["s522_taskbook_quote"]["normalized_in_prompt"]
        and out["ct"]["n_conclusion_space"] > 0
        and out["ct"]["all_items_in_prompt"]
        and out["ct"]["placeholder_absent"]
        and out["ct"]["ask_in_prompt"]
        and out["ct"]["evidence_ids_in_prompt"]
    )
    return out


if __name__ == "__main__":
    r = check()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["PASS"] else 1)
