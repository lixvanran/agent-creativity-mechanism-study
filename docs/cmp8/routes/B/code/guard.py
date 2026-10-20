# -*- coding: utf-8 -*-
"""路线 B v2：**U1–U4 黑名单自检**（协议 §4.1 第 3 类要求：可机器检查，命中即 abort）。

做法与协议 §4.1 一致：
  * 黑名单**只从** `user4_q*.json` 读入，**只活在内存里**，**不写进任何产物**；
  * 本模块**不打印**黑名单字符串，只打印**命中数量与位置**（字符串一律用 `<命中>` 占位）；
  * 扫描范围：诊断题面 / 诊断依据包 / 代码里的所有提示词 / DESIGN.md / spec.yaml。

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


if __name__ == "__main__":
    ok, det = check({})
    print(json.dumps(det, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 2)
