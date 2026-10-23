#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 pairwise json 生成论文用的 markdown 表格（程序化生成 ⇒ 杜绝手抄错误）。"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PAIRS = [("A", "WF-a3"), ("S-self", "WF-a3"), ("WF-a3-NO", "WF-a3"), ("WF-p", "WF-a3")]
DIMS = ["D1_取舍明确度", "D2_观点驱动力", "D3_人类似然感"]
DIM_SHORT = {"D1_取舍明确度": "D1 取舍明确度", "D2_观点驱动力": "D2 观点驱动力",
             "D3_人类似然感": "D3 人类似然感"}


def load(p):
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def table(path, judge_label, out):
    d = load(path)
    if not d:
        return False
    rows = [r for r in d["逐条"] if r.get("winner_x_vs_y")]
    judges = sorted({r["judge"] for r in rows})
    for jm in judges:
        table_one(path, judge_label, out, jm)
    return True


def table_one(path, judge_label, out, only_judge):
    d = load(path)
    rows = [r for r in d["逐条"] if r.get("winner_x_vs_y") and r["judge"] == only_judge]
    if not rows:
        return
    out.append("#### %s · 判官 `%s`\n" % (judge_label, only_judge))
    topics = sorted({r["topic"] for r in rows})
    out.append("| 对比 | 维度 | " + " | ".join(topics) + " |")
    out.append("|---|---|" + "---|" * len(topics))
    for x, y in PAIRS:
        for dim in DIMS:
            buckets = defaultdict(list)
            for r in rows:
                if r["dim"] == dim and r["x"] == x and r["y"] == y:
                    buckets[(r["topic"], r["tag"])].append(r["winner_x_vs_y"])
            cells = []
            for t in topics:
                agg = {"x": 0, "y": 0, "tie": 0, "n": 0}
                consist = 0
                for (tt, tag), vs in buckets.items():
                    if tt != t:
                        continue
                    agg["n"] += 1
                    agg["x"] += sum(1 for v in vs if v == "x")
                    agg["y"] += sum(1 for v in vs if v == "y")
                    agg["tie"] += sum(1 for v in vs if v == "tie")
                    if len(vs) == 2 and (vs[0] == vs[1] or "tie" in vs):
                        consist += 1
                if agg["n"] == 0:
                    cells.append("—")
                else:
                    cr = round(consist / agg["n"], 2)
                    cells.append("%d胜%d负 (n=%d, 一致率%s)" % (agg["x"], agg["y"], agg["n"], cr))
            out.append("| **%s vs %s** | %s | %s |" % (x, y, DIM_SHORT[dim], " | ".join(cells)))
    out.append("")
    return True


def main():
    out = []
    out.append("<!-- 本节表格由 build_paper_tables.py 程序化生成，请勿手改 -->\n")
    out.append("### 6.3.1 两两比较（位置一致率为硬闸）\n")
    table(os.path.join(HERE, "runs", "judge_pairwise_multi.json"),
          "判官 `MiniMax-M3`（**同源**：与被测生成器同厂商）· 全部 4 题", out)
    table(os.path.join(HERE, "runs", "_smoke_pw.json"),
          "判官 `x-ai/grok-4.20` / `x-ai/grok-4.3`（**跨厂商**）· 仅 G01", out)
    # 几何读数
    mt = load(os.path.join(HERE, "runs", "multitopic_analysis.json"))
    if mt:
        out.append("### 6.3.2 零判官几何读数（多题）\n")
        out.append("| 题 | 对比 | 逐例实词 J | 均值 |")
        out.append("|---|---|---|---|")
        for t, v in sorted(mt["per_topic"].items()):
            for p, dd in sorted(v["臂间实词J"].items()):
                if p.split(" vs ")[0] > p.split(" vs ")[1]:
                    continue
                out.append("| %s | %s | %s | %.4f |"
                           % (t, p, ", ".join("%.4f" % x for x in dd["vals"]), dd["mean"]))
        out.append("")
    # 失败样本
    if mt and mt.get("失败样本"):
        out.append("### 6.3.3 失败与闸门（显式列出，不静默剔除）\n")
        out.append("| 题 | 臂 | rep | 原因 | 字数 |")
        out.append("|---|---|---|---|---|")
        for f in mt["失败样本"]:
            out.append("| %s | %s | %s | %s | %d |"
                       % (f["topic"], f["arm"], f["tag"], f.get("error"), f["n_chars"]))
        out.append("")
    p = os.path.join(HERE, "runs", "paper_tables.md")
    open(p, "w", encoding="utf-8").write("\n".join(out))
    print("[out] %s (%d bytes)" % (p, os.path.getsize(p)))
    print("\n".join(out[:60]))


if __name__ == "__main__":
    main()
