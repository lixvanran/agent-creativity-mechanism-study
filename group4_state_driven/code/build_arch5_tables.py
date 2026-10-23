#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5 读数表**程序化生成**（runs/arch5_analysis.json ⇒ runs/arch5_tables.md）。"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "runs", "arch5_analysis.json")
OUT = os.path.join(HERE, "runs", "arch5_tables.md")

with open(SRC, encoding="utf-8") as f:
    R = json.load(f)

L = []
W = L.append
S = R["summary"]

W("# v5 读数表（程序化生成，源：`runs/arch5_analysis.json`）\n")
W("批次：`%s`\n" % "`, `".join("%s=%s" % (k, v) for k, v in R["batches"].items()))
W("样本：%d 条 ｜ 失败：%d\n" % (R["n_records"], S["n_errors"]))

W("\n## 表 1 · 主读数（零判官）\n")
W("| 读数 | n | 均值 | 中位 | 最小 | 最大 |")
W("|---|---|---|---|---|---|")
for key, name in [
        ("H1_decl_parse_rate", "H1′ 声明解析成功率"),
        ("decl_distinct", "声明多样性（不同声明数 / 3）"),
        ("align_state", "align(状态化选择)"),
        ("align_generic", "align(通用选择)"),
        ("H3p_gap", "★H3′ 同池 gap"),
        ("fulfill_state", "H2′ 兑现率（state选）"),
        ("fulfill_generic", "H2′ 兑现率（generic选）"),
        ("violation_state", "H3′′ 违禁率（state选）"),
        ("violation_generic", "H3′′ 违禁率（generic选）"),
        ("cand_sim_mean", "候选两两相似度（诊断）")]:
    a = S.get(key, {})
    if not a.get("n"):
        W("| %s | 0 | — | — | — | — |" % name)
        continue
    W("| %s | %d | %s | %s | %s | %s |" % (name, a["n"], a["mean"], a["median"],
                                            a["min"], a["max"]))

W("\n## 表 2 · H3′ 判据逐条核对（预注册：判决在 `WF-v5` 臂内）\n")
v = R["per_arm"].get("WF-v5", {})
w = v.get("wins", {})
n_nt = w.get("state", 0) + w.get("generic", 0)
W("| 判据 | 阈值 | 实测 | 结论 |")
W("|---|---|---|---|")
W("| 逐例 state 胜率 | ≥ 2/3 | %s | %s |" % (
    ("%d/%d = %.0f%%" % (w.get("state", 0), n_nt, w.get("state", 0) / n_nt * 100))
    if n_nt else "无有效对比（全部打平）",
    "**不通过**" if n_nt == 0 else "见备注"))
W("| 同池 gap 均值 | ≥ +0.15 | %s | %s |" % (
    v.get("H3p_gap", {}).get("mean"),
    "**不通过**" if (v.get("H3p_gap", {}).get("mean") or 0) < 0.15 else "通过"))
W("| 样本量 | n ≥ 6 | %s | %s |" % (v.get("n"),
    "**可判定**" if (v.get("n") or 0) >= 6 else "**不可判定**"))
W("\n> 预注册阈值未达成 ⇒ **H3′ 不成立**（若 n ≥ 6 ⇒ 可判定地不成立）。\n")

W("\n## 表 3 · 分臂读数（`WF-v5-blind` = 盲选地板）\n")
W("| 臂 | n | align(state选) | align(通用选) | gap 均值 | 胜/负/平 | 兑现率 | 违禁率 | 有取舍代价 |")
W("|---|---|---|---|---|---|---|---|---|")
for arm, x in R["per_arm"].items():
    W("| `%s` | %d | %s | %s | %s | %d/%d/%d | %s | %s | %d |" % (
        arm, x["n"], x["align_state"].get("mean"), x["align_generic"].get("mean"),
        x["H3p_gap"].get("mean"), x["wins"]["state"], x["wins"]["generic"], x["wins"]["tie"],
        x["fulfill_state"].get("mean"), x["violation_state"].get("mean"),
        x.get("has_tradeoff_cost", 0)))
if "state_info_gain" in R:
    g = R["state_info_gain"]
    W("\n> ★ **状态信息增量**：%s（给缺口）− %s（盲选地板）= **%s**（×%s）\n" % (
        g["align_WF_v5"], g["align_WF_v5_blind_floor"], g["gain"], g["ratio"]))

W("\n## 表 4 · ★ 承诺与行为的落差（v5 的核心读数）\n")
W("| 量 | 定义 | 均值 |")
W("|---|---|---|")
W("| 兑现率 | 候选**声明写透**的缺口，其实体在正文**真的写了**的比例 | %s |" %
  S["fulfill_state"].get("mean"))
W("| 违禁率 | 候选**声明放弃**的缺口，其实体在正文**却写了**的比例 | %s |" %
  S["violation_state"].get("mean"))
W("| ★ 言行落差 | 1 − 兑现率（声明了却没做） | %s |" % (
    round(1 - S["fulfill_state"]["mean"], 4) if S["fulfill_state"].get("mean") is not None else "—"))
W("\n> ⇒ 产出的可核验证据**不是\"它说了什么取舍\"，而是\"它实际上放弃了什么\"**。\n")

W("\n## 表 5 · 逐题读数（分析单元 = 题）\n")
W("| 题 | n | align(state选) | gap 均值 | 声明解析率 | 兑现率 | 有取舍代价 |")
W("|---|---|---|---|---|---|---|")
for tid, x in R["per_topic"].items():
    W("| %s | %d | %s | %s | %s | %s | %d |" % (
        tid, x["n"], x["align_state"].get("mean"), x["H3p_gap"].get("mean"),
        x["H1_decl_parse_rate"].get("mean"), x["fulfill_state"].get("mean"),
        x.get("has_tradeoff_cost", 0)))

W("\n## 表 6 · 失败与缺失（显式）\n")
if R.get("errors"):
    W("| 题 | 臂 | # | 错误 |")
    W("|---|---|---|---|")
    for e in R["errors"]:
        W("| %s | %s | %s | %s |" % (e["topic"], e["arm"], e["tag"], e["error"]))
else:
    W("本次实验 **0 失败 / %d 条记录**（无缺失、无静默归零）。\n" % R["n_records"])

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("[out] %s" % OUT)
print("\n".join(L))
