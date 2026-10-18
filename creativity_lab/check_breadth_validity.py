# -*- coding: utf-8 -*-
"""「思维面宽度」测量的可信度检查。

疑点：direct 每份答案 3.25 条已支持断言，两次采样 6.5 条，
但语义去重（thr=0.75）后并集只有 1.6 条 —— 与「同臂两次余弦 0.94-0.996」
（几乎一样的文本）矛盾。

两种可能：
  A. 去重阈值 0.75 卡在歧义区（近义句余弦本身在 0.75-0.89），
     措辞略变的同一事实被判成不同 → 并集被虚增
  B. 抽取每次产出的措辞差异大，真的没重合

检查：
  1. 并集大小对去重阈值的敏感度
  2. 手工核对一道题：两次采样的断言逐条列出 + 判定 + 两两余弦
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402
from creativity_lab.metrics import _mat    # noqa: E402

OUT = "runs/train2"
DATA = json.load(open("creativity_lab/data/legal_topics_v2.json", encoding="utf-8"))
TOPICS = DATA["topics"]
ARMS = ("direct", "dual_fuse", "dual_select")


def embed_rows(ts):
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    return _mat(LLM().embed(uniq))[idx]


def pair_sims(a, b):
    if not a or not b:
        return []
    M = embed_rows(list(a) + list(b))
    return (M[:len(a)] @ M[len(a):].T)


def main():
    texts = json.load(open("%s/texts.json" % OUT, encoding="utf-8"))
    claims = json.load(open("%s/claims.json" % OUT, encoding="utf-8"))
    verd = json.load(open("%s/verdicts_v4_full.json" % OUT, encoding="utf-8"))

    by = defaultdict(lambda: defaultdict(list))
    for k, cs in claims.items():
        tid, arm, rep = k.split("|")
        by[tid][arm].append((rep, cs))

    # ---------- 1. 敏感度 ----------
    print("=" * 80)
    print("1. 并集大小对去重阈值的敏感度（每题每臂，18 题均值）")
    print("=" * 80)
    print("%-10s %12s %12s %12s" % ("阈值", "direct", "dual_fuse", "dual_select"))
    for thr in (0.60, 0.70, 0.75, 0.80, 0.85, 0.90):
        res = {}
        for a in ARMS:
            sizes = []
            for T in TOPICS:
                tid = T["tid"]
                if tid not in by:
                    continue
                allc = [c for _, cs in by[tid][a] for c in cs]
                if not allc:
                    sizes.append(0); continue
                M = embed_rows(allc)
                S = M @ M.T
                keep = []
                for i in range(len(allc)):
                    if all(S[i, j] < thr for j in keep):
                        keep.append(i)
                sizes.append(len(keep))
            res[a] = sum(sizes) / len(sizes)
        print("%-10.2f %12.2f %12.2f %12.2f" % (thr, res["direct"], res["dual_fuse"], res["dual_select"]))

    # ---------- 2. 手工核对一道题 ----------
    tid = "A1"
    print("\n" + "=" * 80)
    print("2. 手工核对：题 %s 的 direct 两次采样" % tid)
    print("=" * 80)
    reps = by[tid]["direct"]
    for rep, cs in reps:
        print("\n  rep%s（%d 条断言）:" % (rep, len(cs)))
        for c in cs:
            print("    [%-4s] %s" % (verd.get(c, "?"), c[:56]))
    a = [c for _, cs in reps[:1] for c in cs]
    b = [c for _, cs in reps[1:] for c in cs]
    S = pair_sims(a, b)
    print("\n  两两余弦矩阵（rep1 × rep2）:")
    print("        " + "".join("  j%-2d" % (j + 1) for j in range(len(b))))
    for i in range(len(a)):
        print("    i%-2d  " % (i + 1) + "".join(" %.2f" % S[i, j] for j in range(len(b))))
    hi = [(i, j, S[i, j]) for i in range(len(a)) for j in range(len(b)) if S[i, j] >= 0.55]
    print("\n  余弦≥0.55 的配对（同一事实的不同说法）: %d 对" % len(hi))
    for i, j, v in sorted(hi, key=lambda x: -x[2])[:8]:
        print("    %.3f  %s" % (v, a[i][:30]))
        print("           %s" % b[j][:30])

    # ---------- 3. 结论用的宽度指标（不依赖单一阈值）----------
    print("\n" + "=" * 80)
    print("3. 稳健的宽度指标：并集在多个阈值上的平均（避免单点误判）")
    print("=" * 80)
    THRS = (0.65, 0.70, 0.75, 0.80, 0.85)
    acc = {a: [] for a in ARMS}
    for thr in THRS:
        for a in ARMS:
            for T in TOPICS:
                tid = T["tid"]
                if tid not in by:
                    continue
                allc = [c for _, cs in by[tid][a] for c in cs]
                if not allc:
                    continue
                M = embed_rows(allc)
                S = M @ M.T
                keep = []                       # 每个臂/阈值都要重置（否则索引越界）
                for i in range(len(allc)):
                    if all(S[i, j] < thr for j in keep):
                        keep.append(i)
                acc[a].append(len(keep))
    for a in ARMS:
        v = acc[a]
        print("  %-13s 均值 %6.2f  中位 %5.1f  区间 %d–%d"
              % (a, sum(v) / len(v), sorted(v)[len(v) // 2], min(v), max(v)))
    b = acc["dual_fuse"]; d = acc["direct"]; s = acc["dual_select"]
    n = min(len(b), len(d), len(s))
    print("\n  相对 direct:  dual_fuse %+.1f%%   dual_select %+.1f%%"
          % (100 * (sum(b[:n]) - sum(d[:n])) / sum(d[:n]),
             100 * (sum(s[:n]) - sum(d[:n])) / sum(d[:n])))


if __name__ == "__main__":
    main()
