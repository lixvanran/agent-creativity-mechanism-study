# -*- coding: utf-8 -*-
"""检验关键混淆：**「工作流无增益」是不是只发生在「模型本来就很确定」的题上？**

若增益点集中在**直调跨重复不一致**（= 模型自己也没底）的题上，
那就说明工作流在「模型不确定处」是有用的，只是我的训练集全是模型有把握的题。

指标：
  conf(题)  = 该题 direct 两份答案的平均余弦（越高=模型越确定）
  gain(题)  = 该题所有工作流臂的增益点总数
  集中度    = 高增益题目的 conf 是否系统性更低
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402
from creativity_lab.metrics import _mat    # noqa: E402

OUT = "runs/train2"
texts = json.load(open("%s/texts.json" % OUT, encoding="utf-8"))
recs = json.load(open("%s/records.json" % OUT, encoding="utf-8"))
recs = [r for r in recs if not r["dead"]]

by_tid = {}
for r in recs:
    by_tid.setdefault(r["tid"], []).append(r)

llm = LLM()
rows = []
for tid in sorted(by_tid):
    d = [k for k in texts if k.split("|")[0] == tid and k.split("|")[1] == "direct"]
    if len(d) < 2:
        continue
    M = _mat(llm.embed([texts[k] for k in d]))
    conf = float(np.mean([M[i] @ M[j] for i in range(M.shape[0]) for j in range(i + 1, M.shape[0])]))
    gain = sum(r["n_new"] for r in by_tid[tid] if r["arm"] != "direct")
    sup = sum(r["n_sup"] for r in by_tid[tid] if r["arm"] == "direct")
    rows.append(dict(tid=tid, conf=round(conf, 4), gain=gain, direct_sup=sup))

print("%-6s %10s %8s %10s" % ("题", "直调一致性", "增益点", "直调已支持"))
for r in sorted(rows, key=lambda x: -x["gain"]):
    print("%-6s %10.4f %8d %10d" % (r["tid"], r["conf"], r["gain"], r["direct_sup"]))

c = np.array([r["conf"] for r in rows])
g = np.array([r["gain"] for r in rows], dtype=float)
print("\n一致性 vs 增益点  秩相关:", end=" ")
from creativity_lab.scipy_free import spearman
print("%.3f" % spearman(c, g))

hi = [r for r in rows if r["gain"] > 0]
lo = [r for r in rows if r["gain"] == 0]
if hi and lo:
    print("  有增益题的平均一致性 %.4f (n=%d)" % (np.mean([r["conf"] for r in hi]), len(hi)))
    print("  无增益题的平均一致性 %.4f (n=%d)" % (np.mean([r["conf"] for r in lo]), len(lo)))
print("\n一致性最低的 5 题（模型最没底的）：")
for r in sorted(rows, key=lambda x: x["conf"])[:5]:
    print("  %s conf=%.4f gain=%d" % (r["tid"], r["conf"], r["gain"]))
