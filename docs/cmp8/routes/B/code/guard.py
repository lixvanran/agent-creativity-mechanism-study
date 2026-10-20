# -*- coding: utf-8 -*-
"""路线 B v2：**U1–U4 黑名单自检**（协议 §4.1 第 3 类要求：可机器检查，命中即 abort）。

做法与协议 §4.1 一致：
  * 黑名单**只从** `user4_q*.json` 读入，**只活在内存里**，**不写进任何产物**；
  * 本模块**不打印**黑名单字符串，只打印**命中数量与位置**（字符串一律用 `<命中>` 占位）；
  * 扫描范围：诊断题面 / 诊断依据包 / 代码里的所有提示词 / DESIGN.md / spec.yaml。

⚠️ **"命中即 abort"的两个执行点**（2026-10-21 修 F9：此前 `__main__` 扫的是空文本 ⇒ 恒 0 命中）：
  ① `smoke.py`：在**任何 LLM 调用之前**跑 `route_payload()` + `check()` ⇒ 命中 ⇒ SystemExit；
  ② 本文件 `__main__`：`python3 guard.py` 扫**同一份清单** ⇒ 命中 ⇒ 退出码 **2**。
  ⚠️ guard 的覆盖范围**就是** `route_payload()` 列出的那一份清单（见该函数 docstring）；
     运行期模型输出**不在**覆盖范围内 ⇒ 不许把它说成"全量扫描"。

黑名单三类（协议 §4.1）：
  ① 题面字符串（`ask` 逐字）
  ② 依据包片段（`evidence` 的每一条原子事实文本及其 ≥8 字的连续片段）
  ③ 答案键（`name` / `sources` 中的标准结论词及其最长公共子串）

⚠️ 协议 §4.1 的 L14：子串匹配**抓不住"换皮搬运"** ⇒ 本模块只能证明
   "没有原样搬运"，不能证明"没有改写搬运" ⇒ 报告里必须这么写。
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

USER4_GLOBS = [
    "/workspace/lab/cmp8repo/cmp8/creativity_lab/data/user4_q*.json",
    "/workspace/lab/cmp8repo/creativity_lab/data/user4_q*.json",
]
FRAG_MIN = 8          # 协议 §4.1：≥8 字的连续片段


def _user4_files():
    out = []
    for g in USER4_GLOBS:
        out.extend(sorted(glob.glob(g)))
    return sorted(set(out))


def build_blacklist(min_frag: int = FRAG_MIN):
    """返回 (黑名单字符串集合, 来源说明)。**调用方不得打印集合内容。**"""
    bl = set()
    src = []
    for f in _user4_files():
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        src.append(os.path.basename(f))
        for key in ("ask", "name"):
            v = d.get(key)
            if isinstance(v, str) and len(v) >= 4:
                bl.add(v.strip())
        ev = d.get("evidence")
        if isinstance(ev, str):
            for line in re.split(r"[\n\r。；;]", ev):
                line = line.strip()
                if len(line) >= min_frag:
                    bl.add(line)
                    for i in range(0, len(line) - min_frag + 1):
                        bl.add(line[i:i + min_frag])
        for s in (d.get("sources") or []):
            if isinstance(s, str) and len(s) >= min_frag:
                bl.add(s.strip())
    # 太短或太泛的串会造成假阳性：长度 < min_frag 的整条直接丢（片段已覆盖）
    bl = {b for b in bl if len(b) >= min_frag}
    return bl, src


def scan_texts(texts: dict, blacklist=None):
    """texts: {标签: 文本}。返回 {标签: 命中数}（不打印命中内容）。"""
    if blacklist is None:
        blacklist, _ = build_blacklist()
    hits = {}
    for tag, txt in texts.items():
        if not txt:
            hits[tag] = 0
            continue
        t = txt.replace(" ", "").replace("\n", "")
        n = 0
        for b in blacklist:
            bb = b.replace(" ", "").replace("\n", "")
            if len(bb) < FRAG_MIN:
                continue
            if bb in t:
                n += 1
        hits[tag] = n
    return hits


def scan_files(paths, blacklist=None):
    out = {}
    for p in paths:
        try:
            txt = open(p, encoding="utf-8").read()
        except Exception:
            continue
        out[os.path.basename(p)] = scan_texts({p: txt}, blacklist)
    return out


def check(prompt_texts: dict, extra_files=()):
    """完整检查：返回 (ok, 明细)。**明细里只有计数，没有黑名单内容。**"""
    bl, src = build_blacklist()
    hits = scan_texts(prompt_texts, bl)
    files = scan_files(list(extra_files), bl) if extra_files else {}
    total = sum(hits.values()) + sum(v for d in files.values() for v in d.values())
    detail = dict(
        blacklist_source_files=src,
        blacklist_size=len(bl),
        fragment_min_len=FRAG_MIN,
        text_hits=hits,
        file_hits=files,
        total_hits=total,
        ok=(total == 0),
        caveat="子串匹配只证明'没有原样搬运'，不能证明'没有改写搬运'（协议 L14）",
    )
    return (total == 0), detail


# ───────────────────────────────────────── 本路线的**确切覆盖范围**（F9）
def route_payload(code_dir=None, route_dir=None):
    """本路线**实际交付/会用到**的全部文本 ⇒ (texts, files)。

    ⚠️ 这份清单就是「guard 覆盖哪些入口」的**确切口径**（DESIGN §11 L10）：
      · **覆盖**：四条提示词（GEN / EXTRACT / SPLIT / CHECK_V2）、2 道诊断题的题面与依据包、
        `code/*.py`、`DESIGN.md`、`spec.yaml`。
      · **不覆盖**：运行期模型输出、训练中间产物、用户四道题（红线 R-1：本路线不接触）。
    ⚠️ 命中即 abort 的**执行点**有两个：
      ① `smoke.py` 在**任何 LLM 调用之前**调用它（命中 ⇒ SystemExit，不烧预算）；
      ② 本文件 `__main__`（`python3 guard.py`）扫同一份清单 ⇒ 命中 ⇒ 退出码 2。
    """
    code_dir = code_dir or os.path.dirname(os.path.abspath(__file__))
    route_dir = route_dir or os.path.dirname(code_dir)
    import evidence_index
    import train_policy_v2 as tpv

    texts = {
        "prompt_GEN": tpv.GEN_Q,
        "prompt_EXTRACT": tpv.EXTRACT_Q,
        "prompt_SPLIT": tpv.SPLIT_Q,
        "prompt_CHECK_V2": evidence_index.CHECK_V2,
    }
    data_path = os.path.join(code_dir, "data", "diag_topics.json")
    if os.path.exists(data_path):
        data = json.load(open(data_path, encoding="utf-8"))
        for t in data["topics"]:
            texts["diag_ask_%s" % t["topic_id"]] = t["ask"]
            texts["diag_evidence_%s" % t["topic_id"]] = json.dumps(t["items"], ensure_ascii=False)
            texts["diag_ct_%s" % t["topic_id"]] = json.dumps(t.get("conclusion_space", []),
                                                              ensure_ascii=False)
    files = [os.path.join(code_dir, f) for f in sorted(os.listdir(code_dir))
             if f.endswith(".py")]
    for extra in (data_path, os.path.join(route_dir, "DESIGN.md"), os.path.join(route_dir, "spec.yaml")):
        if os.path.exists(extra):
            files.append(extra)
    return texts, files


if __name__ == "__main__":
    _texts, _files = route_payload()
    ok, det = check(_texts, _files)
    det["scanned_texts"] = len(_texts)
    det["scanned_files"] = [os.path.basename(f) for f in _files]
    det["scope_caveat"] = ("guard 只覆盖本清单里的文本（提示词/诊断题/代码/文档）；"
                           "运行期模型输出不在覆盖范围内")
    print(json.dumps(det, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 2)
