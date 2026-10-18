# -*- coding: utf-8 -*-
"""从已落盘的 holdall_*.json 重算悖论量化指标（不重跑 API）。"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.scipy_free import spearman   # noqa: E402

OUT = "runs/drill"

rows = []
for fn in sorted(os.listdir(OUT)):
    if not fn.startswith("holdall_"):
        continue
    d = json.load(open(os.path.join(OUT, fn), encoding="utf-8"))
    rows.append((d["key"], d["agg"]["score"]))

drill = {}
for fn in sorted(os.listdir(OUT)):
    if not fn.startswith("drill_"):
        continue
    d = json.load(open(os.path.join(OUT, fn), encoding="utf-8"))
    drill[d["key"]] = d["agg"]["score"]

common = [k for k, _ in rows if k in drill]
hold = dict(rows)
print("规格数：巡练 %d，留出 %d，交集 %d" % (len(drill), len(hold), len(common)))
print()
print("%-24s %9s %9s %8s %8s" % ("规格", "巡练分", "留出分", "巡练名", "留出名"))
od = sorted(common, key=lambda k: -drill[k])
oh = sorted(common, key=lambda k: -hold[k])
rd = {k: i + 1 for i, k in enumerate(od)}
rh = {k: i + 1 for i, k in enumerate(oh)}
for k in od:
    print("%-24s %9.2f %9.2f %8d %8d" % (k, drill[k], hold[k], rd[k], rh[k]))

x = [drill[k] for k in common]
y = [hold[k] for k in common]
rho = spearman(x, y)
print()
print("=" * 66)
print("悖论量化")
print("=" * 66)
print("  Spearman(巡练分, 留出分) = %+.3f" % rho)
t1, t2 = od[0], od[1]
print("  训练集第1名 %-22s 巡练 %6.2f → 留出 %6.2f（留出第 %d 名）"
      % (t1, drill[t1], hold[t1], rh[t1]))
print("  训练集第2名 %-22s 巡练 %6.2f → 留出 %6.2f（留出第 %d 名）"
      % (t2, drill[t2], hold[t2], rh[t2]))
print("  后悔量（按训练分选第1，比选第2差）= %+.2f 分" % (hold[t1] - hold[t2]))
best_h = max(common, key=lambda k: hold[k])
print("  留出集最优是 %s（%6.2f）—— 训练集选得到吗？%s"
      % (best_h, hold[best_h], "是" if best_h == t1 else "否"))
print("  训练集冠军在留出集上落后最优 %.2f 分" % (hold[best_h] - hold[t1]))
n_pos = sum(1 for k in common if hold[k] > 0)
print("  留出集上得分为正的规格：%d/%d" % (n_pos, len(common)))
json.dump(dict(drill=drill, hold=hold, rho=rho, regret=hold[t1] - hold[t2],
               rank_drill=rd, rank_hold=rh),
          open(os.path.join(OUT, "paradox.json"), "w"), ensure_ascii=False, indent=1)
