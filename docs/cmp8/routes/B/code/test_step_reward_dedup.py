#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **步级奖励的"去重"探针**（2026-10-21 独立复核 F7）。

F7 指出：步级奖励是**未去重的"条数"项**（`VERIFY → 支持` 每核验一步 +1.0），
而 DESIGN §4.5 第 3 条说"灌水/重复/加长**都不涨分**"⇒ 只对 Ŵ 成立、对**总回报**不成立。
复核者用 A/B/C/D 四个情形实测：改写同一件事 N 遍能把总回报刷到与"做了 3 件不同事"一样。

现在 `train_policy_v2.run_episode` 的步级奖励**按依据条目去重**（新覆盖一个锚定条目 +1.0，
重复覆盖同一条目 +0）。本探针**用真实代码路径**（`run_episode` + 假模型）复跑同样的四个情形：

  A：1 条断言，覆盖 E1
  B：3 句改写同一件事，仍只覆盖 E1
  C：8 句改写同一件事，仍只覆盖 E1
  D：3 件不同的事，覆盖 E1/E2/E3

期望（修好之后）：**A = B = C**（灌水不涨分），且 **D > C**（诚实策略严格更优）。

用法：python3 test_step_reward_dedup.py
"""
from __future__ import annotations

import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from evidence_index import EvidenceIndex  # noqa: E402
from train_policy_v2 import run_episode  # noqa: E402

ASK = "自造探针题：下列规则各自要求什么？（与任何真实题无关）"
ITEMS = [
    {"id": "E1", "text": "第一条依据：普通图书借阅期限为 30 天，到期前可续借。", "anchored": True},
    {"id": "E2", "text": "第二条依据：读者证有效期为 3 年，到期需换证。", "anchored": True},
    {"id": "E3", "text": "第三条依据：逾期归还每天每册收取 0.2 元滞纳金。", "anchored": True},
]


class _Rec:
    """`client.LLM.Call` 的最小替身（`_call_flags` 只读这两个字段）。"""
    def __init__(self, purpose, content_len):
        self.model = "fake-offline"
        self.purpose = purpose
        self.max_tokens = 0
        self.finish_reason = "stop"
        self.content_len = content_len
        self.ok = True
        self.secs = 0.0


class FakeModel:
    """假模型：生成固定答案；抽取返回 n 条断言；判官按"断言文本 → 条目编号"给「支持」。"""

    def __init__(self, claims, item_ids):
        self.rec = []
        self.by_text = {c: i for c, i in zip(claims, item_ids)}
        self.claims = claims

    def chat(self, prompt, **kw):
        p = prompt or ""
        if "待核验的陈述" in p:
            blk = p.split("待核验的陈述：", 1)[1]
            out = []
            for ln in blk.split("\n"):
                m = re.match(r"^\s*\d+\.\s*(.+)$", ln)
                if not m:
                    continue
                txt = m.group(1).strip()
                out.append("支持 | %s" % self.by_text.get(txt, "E1"))
            self.rec.append(_Rec("check2", len("\n".join(out))))
            return "\n".join(out)
        if "逐条列出其中" in p:
            self.rec.append(_Rec("al_ex", len("\n".join(self.claims))))
            return "\n".join("- %s" % c for c in self.claims)
        self.rec.append(_Rec("al_gen", 40))
        return "自造探针答案：以下三点分别说明期限、证件与滞纳金的具体数值与办理要求。"


def _picker_factory():
    st = {"extracted": False}

    def pick(step, g, cands):
        legal = {op for op, _t in cands}
        if not g.of_kind("ANSWER"):
            return "GEN_ANGLE"
        if "EXTRACT" in legal and not st["extracted"]:
            st["extracted"] = True
            return "EXTRACT"
        if "VERIFY" in legal:
            return "VERIFY"
        return "STOP"

    return pick


def scenario(name, claims, item_ids):
    evi = EvidenceIndex("PRB", ASK, ITEMS, [])
    m = FakeModel(claims, item_ids)
    _g, _traj, rewards, info = run_episode(
        {"topic_id": "PRB", "ask": ASK}, evi, [0.0] * 30, random.Random(7),
        llm=m, budget=10, forced_picker=_picker_factory())
    step_sum = sum(rewards[:-1])          # 末位是终局奖励
    terminal = rewards[-1]
    return dict(name=name, n_claims=len(claims), n_steps=info["steps"],
                n_verify=info["n_verify"], step_sum=round(step_sum, 4),
                terminal=round(terminal, 4), total=round(step_sum + terminal, 4),
                w_hat=round(info["proxy"]["w_hat"], 4),
                covered_anchored=info["proxy"]["covered_anchored"])


def check():
    same = "普通图书的借阅期限是 30 天，到期之前可以办理一次续借。"
    diff1 = "读者证的有效期是 3 年，到期后需要携带身份证件换证。"
    diff2 = "逾期归还的图书每天每册收取 0.2 元滞纳金。"
    long_claim = "普通图书的借阅期限是 30 天，到期之前可以办理一次续借，并且续借后不能再次续借。"
    rows = [
        scenario("A_1条覆盖E1", [same], ["E1"]),
        scenario("B_3句改写同一件事", [same, long_claim, same.replace("30 天", "三十天")], ["E1"] * 3),
        scenario("C_8句改写同一件事",
                 [same, long_claim, same.replace("30 天", "三十天")] * 2 + [same, long_claim],
                 ["E1"] * 8),
        scenario("D_3件不同的事", [same, diff1, diff2], ["E1", "E2", "E3"]),
    ]
    by = {r["name"]: r for r in rows}
    A, B, C, D = (by["A_1条覆盖E1"], by["B_3句改写同一件事"],
                  by["C_8句改写同一件事"], by["D_3件不同的事"])
    out = {"scenarios": rows}
    out["assertions"] = {
        "A_step_sum_is_1": abs(A["step_sum"] - 1.0) < 1e-9,
        "B_step_equals_A": abs(B["step_sum"] - A["step_sum"]) < 1e-9,
        "C_step_equals_A": abs(C["step_sum"] - A["step_sum"]) < 1e-9,
        "D_step_is_3": abs(D["step_sum"] - 3.0) < 1e-9,
        "total_ABC_equal": abs(A["total"] - B["total"]) < 1e-9 and abs(A["total"] - C["total"]) < 1e-9,
        "D_beats_C": D["total"] > C["total"] + 1e-9,
        "w_hat_D_is_1": abs(D["w_hat"] - 1.0) < 1e-9,
    }
    out["PASS"] = all(out["assertions"].values())
    return out


if __name__ == "__main__":
    r = check()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["PASS"] else 1)
