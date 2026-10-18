# -*- coding: utf-8 -*-
"""重测：工作流作为「探索器」的价值 —— 我之前只测了「验证器」的价值。

差集核验只算**已核验**的断言，那是 exploitation。
探索的产物是**多报出来的考虑**，其中必然有一部分没被验证、甚至错。

分解成三个正交量：
  探索量  = 该臂在不同次采样间触及的**不同考虑**总数（并集），
            以及相对直调**多报出来**的那些（不论是否被验证）
  质量    = 并集里被依据支持的比例
  风险    = 并集里与依据矛盾的比例

如果 dual 臂的并集更大、但支持率更低 → 那不是「工作流没用」，
那是**探索量换质量**，我之前的单指标只看后一项。
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402
from creativity_lab.metrics import _mat    # noqa: E402

OUT = "runs/train2"
DATA = json.load(open("creativity_lab/data/legal_topics_v2.json", encoding="utf-8"))
TOPICS = DATA["topics"]
law_of = {t["tid"]: t["law"] for t in TOPICS}
ARMS = ("direct", "dual_fuse", "dual_select")


def embed_rows(ts):
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    return _mat(LLM().embed(uniq))[idx]


def dedup_sem(claims, thr=0.75):
    """语义去重：同一件事的不同说法只留一条。"""
    if not claims:
        return []
    M = embed_rows(claims)
    S = M @ M.T
    keep = []
    for i in range(len(claims)):
        if all(S[i, j] < thr for j in keep):
            keep.append(i)
    return [claims[i] for i in keep]


def main():
    texts = json.load(open("%s/texts.json" % OUT, encoding="utf-8"))
    claims = json.load(open("%s/claims.json" % OUT, encoding="utf-8"))
    verd = json.load(open("%s/verdicts_v4_full.json" % OUT, encoding="utf-8"))

    by = defaultdict(lambda: defaultdict(list))     # tid -> arm -> [claims]
    for k, cs in claims.items():
        tid, arm, rep = k.split("|")
        by[tid][arm].extend(cs)

    print("每题每臂：不同次采样触及的「不同考虑」并集大小\n")
    hdr = "%-5s" % "题"
    for a in ARMS:
        hdr += " %14s" % a
    hdr += "   %10s" % "多报(选-直调)"
    print(hdr)
    print("-" * (len(hdr) + 4))

    tot = {a: [] for a in ARMS}
    tot_new = []
    for T in TOPICS:
        tid = T["tid"]
        if tid not in by:
            continue
        unions = {}
        for a in ARMS:
            raw = by[tid].get(a, [])
            u = dedup_sem(raw)
            unions[a] = u
            tot[a].append(len(u))
        d = set(unions["direct"])
        s_new = [c for c in unions["dual_select"] if c not in d]
        # 语义上「不在直调并集里」
        if s_new:
            M = embed_rows(s_new + list(d))
            S = M[:len(s_new)] @ M[len(s_new):].T
            s_new = [s_new[i] for i in range(len(s_new)) if float(S[i].max()) < 0.55]
        tot_new.append(len(s_new))
        line = "%-5s" % tid
        for a in ARMS:
            line += " %14d" % len(unions[a])
        line += "   %10d" % len(s_new)
        print(line)

    print("-" * (len(hdr) + 4))
    line = "%-5s" % "均值"
    for a in ARMS:
        line += " %14.1f" % (sum(tot[a]) / len(tot[a]))
    line += "   %10.1f" % (sum(tot_new) / len(tot_new))
    print(line)

    # ---- 质量 / 风险 分解（在各自的并集上）----
    print("\n在各自并集上：支持数 / 矛盾数 / 未提及数")
    print("%-13s %8s %8s %8s %10s %10s" % ("arm", "并集", "支持", "矛盾", "支持率", "矛盾率"))
    for a in ARMS:
        U, S, C, UN = set(), 0, 0, 0
        for T in TOPICS:
            tid = T["tid"]
            if tid not in by:
                continue
            for c in dedup_sem(by[tid].get(a, [])):
                U.add((tid, c))
        for tid, c in U:
            v = verd.get(c, "解析失败")
            S += v == "支持"; C += v == "矛盾"; UN += v == "未提及"
        legal = max(len(U) - UN, 1)
        print("%-13s %8d %8d %8d %9.1f%% %9.1f%%"
              % (a, len(U), S, C, 100 * S / legal, 100 * C / legal))

    # ---- 多报出来的那部分，质量和风险如何 ----
    print("\n相对直调「多报出来」的那些考虑（dual_select − direct），它们的去向：")
    news = []
    for T in TOPICS:
        tid = T["tid"]
        if tid not in by:
            continue
        d = dedup_sem(by[tid].get("direct", []))
        s = dedup_sem(by[tid].get("dual_select", []))
        extra = [c for c in s if c not in d]
        if extra:
            M = embed_rows(extra + d)
            S = M[:len(extra)] @ M[len(extra):].T
            extra = [extra[i] for i in range(len(extra)) if float(S[i].max()) < 0.55]
        for c in extra:
            news.append((tid, c, verd.get(c, "解析失败")))
    cnt = defaultdict(int)
    for _, _, v in news:
        cnt[v] += 1
    print("  多报 %d 条 → 支持 %d / 矛盾 %d / 未提及 %d"
          % (len(news), cnt["支持"], cnt["矛盾"], cnt["未提及"]))
    print("  （这些是**探索产物**：还没被依据支持，但也不与依据冲突）")
    for tid, c, v in news[:12]:
        print("    [%s] %-5s %s" % (tid, v, c[:52]))


if __name__ == "__main__":
    main()
