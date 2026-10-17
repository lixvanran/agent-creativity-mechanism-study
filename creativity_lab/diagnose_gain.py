# -*- coding: utf-8 -*-
"""诊断：增益点少，是测量压出来的，还是真的没有。

三个检查：
1. 覆盖阈值敏感度 —— 阈值放紧/放松，增益点怎么变
2. 工作流的已支持断言里，有多少**本来就在**直调里（子集率）
3. 未提及的断言长什么样 —— 是「真但包外」还是「模型瞎编」
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402
from creativity_lab.metrics import _mat    # noqa: E402

OUT = "runs/train2"
recs = json.load(open("%s/records.json" % OUT, encoding="utf-8"))
texts = json.load(open("%s/texts.json" % OUT, encoding="utf-8"))
claims = json.load(open("%s/claims.json" % OUT, encoding="utf-8"))
verd = json.load(open("%s/verdicts.json" % OUT, encoding="utf-8"))
law_of = {t["tid"]: t["law"] for t in json.load(
    open("creativity_lab/data/legal_topics_v2.json", encoding="utf-8"))["topics"]}


def embed_rows(ts):
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    return _mat(LLM().embed(uniq))[idx]


print("=" * 88)
print("检查 1：覆盖阈值敏感度（'新增' 对语义去重阈值的敏感性）")
print("=" * 88)
llm = LLM()
tot_new = {t: 0 for t in (0.40, 0.50, 0.55, 0.65, 0.75)}
sup_work = 0
covered_cnt = {t: 0 for t in tot_new}
for k, txt in texts.items():
    tid, arm, rep = k.split("|")
    cs = claims[k]
    if not cs: continue
    V = verd.get(law_of[tid], {})
    sup = [c for c in cs if V.get(c) == "支持"]
    if arm == "direct": continue
    sup_work += len(sup)
    if not sup: continue
    dpool = [c for kk, cc in claims.items()
             if kk.split("|")[0] == tid and kk.split("|")[1] == "direct" for c in cc]
    if not dpool: continue
    M = embed_rows(sup + dpool)
    S = M[:len(sup)] @ M[len(sup):].T
    for i in range(len(sup)):
        mx = float(S[i].max())
        for t in tot_new:
            if mx >= t: covered_cnt[t] += 1
            else: tot_new[t] += 1
for t in sorted(tot_new):
    print("  阈值 %.2f → 增益点 %3d  （工作流已支持断言 %d 条中的 %.1f%% 落在直调里）"
          % (t, tot_new[t], sup_work, 100 * covered_cnt[t] / max(sup_work, 1)))

print("\n" + "=" * 88)
print("检查 2：工作流的已支持断言，是直调的子集吗？")
print("=" * 88)
print("  工作流两臂的已支持断言总数: %d" % sup_work)
print("  其中不在同题直调里（增益点）: %d  (阈值0.55)" % tot_new[0.55])
print("  子集率: %.1f%%" % (100 * covered_cnt[0.55] / max(sup_work, 1)))

print("\n" + "=" * 88)
print("检查 3：核验器判出的 22 条矛盾（模型真的说错了的）")
print("=" * 88)
seen = set()
for law, v in verd.items():
    for c, x in v.items():
        if x == "矛盾" and c not in seen:
            seen.add(c)
            print("  [法%s] %s" % (law, c[:74]))

print("\n" + "=" * 88)
print("检查 4：未提及的断言 —— 真但包外，还是瞎编？各抽 8 条")
print("=" * 88)
un = []
for law, v in verd.items():
    for c, x in v.items():
        if x == "未提及": un.append((law, c))
for law, c in un[:8]:
    print("  [法%s] %s" % (law, c[:74]))
print("  ...")
for law, c in un[-8:]:
    print("  [法%s] %s" % (law, c[:74]))
