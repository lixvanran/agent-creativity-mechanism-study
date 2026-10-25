#!/usr/bin/env python3
"""**ToT 原版臂 + ADHD 臂** 的读数表（按预注册出表 + 判决）

> 落点：`creativity_lab/experiments/build_totarm_tables.py`
> 预注册：`docs/cmp8/routes/COLLAPSE/eval/PREREG-TOT-ARM.md`
> 输入：`runs/tot-arm-2026-10-24/manifest.json`（+ `runs/cogpos-matrix-2026-10-24/` 若存在）
>
> ## ★★★ 读数设计的修正（跑前已写死的是"面宽差"，实测发现**定义上恒等** ⇒ 必须改）
> 预注册的 H-T1 / H-T3 比较的是**候选集面宽**（Vendi）。
> ★ 但 `nosel_b5` / `tot_greedy_b5` / `tot_vote_b5` / `tot_sample_b5` **共享同一次发散**
>   ⇒ ⇒ **候选集 Vendi 在四个臂里完全相同** ⇒ ⇒ **"面宽差"恒为 0，定义上不可判**。
> ⇒ ⇒ ★ 与"秩/n"同一类错误（**恒等式**）⇒ ⇒ **修正不依赖结果方向**，必须改。
> ⇒ ⇒ ★★ **正确的读数是「选中了哪一支」** —— 这也正是 ToT 真正关心的事（选得对不对）：
>   | 原假说 | 修正后 | 理由 |
>   |---|---|---|
>   | H-T1 面宽差（nosel vs tot_greedy） | ★ **合并进 H-T6（消耗率，报告性）** | 候选集恒等 |
>   | H-T3 面宽差（vote vs value） | ★★ **H-T3'：选中支的代表性差** | 评估器只改"选谁"，不改"候选集" |
>   | H-T2 消耗率差（sample vs greedy） | 不变 | 有效 |
>   | H-T4 消耗率差（adhd vs tot_greedy） | 不变 | 有效（比值型，跨 n 可比） |
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "cmp8", "routes", "COLLAPSE", "eval", "results")
TOT = os.path.join(ROOT, "runs", "tot-arm-2026-10-24")
COG = os.path.join(ROOT, "runs", "cogpos-matrix-2026-10-24")
ARMS = ["nosel_b5", "tot_greedy_b5", "tot_vote_b5", "tot_sample_b5",
        "tot_greedy_b1", "adhd_b5"]
LAB = {"nosel_b5": "无选择器（5支）", "tot_greedy_b5": "ToT·value·greedy",
       "tot_vote_b5": "ToT·vote·greedy", "tot_sample_b5": "ToT·value·sample",
       "tot_greedy_b1": "ToT·value·greedy·b=1", "adhd_b5": "ADHD 真代码"}


def med(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def load(path):
    if not os.path.exists(os.path.join(path, "manifest.json")):
        return None
    return json.load(open(os.path.join(path, "manifest.json"), encoding="utf-8"))


def main() -> int:
    man = load(TOT)
    if not man:
        print("✘ 没有 tot-arm 的 manifest")
        return 1
    groups = [g for g in man["groups"] if g.get("arms")]
    h = man["health"]
    tids = sorted({g["tid"] for g in groups})

    # ══ 表T1 通道健康（★ 用 calllog 独立重算值，不用 manifest 的）══
    hb = load(TOT)
    t1 = ["# 表T1 · 通道健康（★ 独立重算，见 `fix_calllog_fields.py`）\n",
          "\n| 项 | 值 |\n|---|---:|"]
    for k in ("n_groups", "n_arms", "n_calls_total", "n_calls_failed",
              "n_calls_empty", "n_branch_deficit", "channel_health", "effort", "model"):
        if k in h:
            t1.append("| %s | %s |" % (k, h[k]))
    t1.append("\n> ⚠️ **本次跑批的 `channel_health` 用的是修正后的判据**"
              "（`has_content` + `finish_reason=='exception'` + `content_len==0`）")

    # ══ 表T2 逐组 ══
    t2 = ["# 表T2 · 逐组读数\n",
          "\n| 题 | 组 | 臂 | 支 | Vendi | self-BLEU | Distinct-2 | 模态数 | 词面共享度 | **消耗率** | **选中支代表性** | 调用数 |",
          "|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for g in sorted(groups, key=lambda x: (x["tid"], x["rep"])):
        for arm in ARMS:
            d = g["arms"].get(arm)
            if not d:
                continue
            r = d.get("read") or {}
            t2.append("| %s | r%d | %s | %s/%s | %s | %s | %s | %s | %s | %s | %s | %s |"
                      % (g["tid"], g["rep"], LAB[arm], d.get("n_arts"), d.get("n_expected"),
                         r.get("vendi", "—"), r.get("self_bleu", "—"), r.get("distinct_2", "—"),
                         r.get("modes", "—"), r.get("lexical_sharing", "—"),
                         d.get("selector_consumption", "—"),
                         d.get("pick_representativeness", "—"), d.get("n_calls", "—")))

    # ══ 表T3 题内中位 + 对照差 ══
    per: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for arm in ARMS:
        for tid in tids:
            gs = [g["arms"][arm] for g in groups
                  if g["tid"] == tid and g["arms"].get(arm)]
            gs = [d for d in gs if d]
            if not gs:
                continue
            per[(arm, tid)] = {
                "vendi": med([(d.get("read") or {}).get("vendi") for d in gs]),
                "self_bleu": med([(d.get("read") or {}).get("self_bleu") for d in gs]),
                "modes": med([(d.get("read") or {}).get("modes") for d in gs]),
                "consume": med([d.get("selector_consumption") for d in gs]),
                "repr": med([d.get("pick_representativeness") for d in gs]),
                "calls": med([d.get("n_calls") for d in gs]),
                "n": len(gs),
            }

    def delta(arm_a, arm_b, key, tid):
        a, b = per.get((arm_a, tid)), per.get((arm_b, tid))
        if not a or not b or a.get(key) is None or b.get(key) is None:
            return None
        return a[key] - b[key]

    def dirn(arm_a, arm_b, key, tid):
        ds = []
        for g in groups:
            if g["tid"] != tid:
                continue
            da, db = g["arms"].get(arm_a), g["arms"].get(arm_b)
            if not da or not db:
                continue
            va = da.get(key)
            vb = db.get(key)
            if va is None or vb is None:
                continue
            ds.append(1 if va > vb else (-1 if va < vb else 0))
        p = sum(1 for x in ds if x > 0)
        m = sum(1 for x in ds if x < 0)
        return "↑%d/↓%d" % (p, m) if ds else "—"

    t3 = ["# 表T3 · 题内中位 + 预注册对照的差\n",
          "\n| 题 | 臂 | Vendi | self-BLEU | 模态数 | **消耗率** | **选中支代表性** | 调用数 |",
          "|---|---|--:|--:|--:|--:|--:|--:|"]
    for tid in tids:
        for arm in ARMS:
            v = per.get((arm, tid))
            if not v:
                continue
            t3.append("| %s | %s | %s | %s | %s | %s | %s | %s |"
                      % (tid, LAB[arm],
                         "%.2f" % v["vendi"] if v["vendi"] is not None else "—",
                         "%.3f" % v["self_bleu"] if v["self_bleu"] is not None else "—",
                         "%.1f" % v["modes"] if v["modes"] is not None else "—",
                         "%.3f" % v["consume"] if v["consume"] is not None else "—",
                         "%.3f" % v["repr"] if v["repr"] is not None else "—",
                         "%.0f" % v["calls"] if v["calls"] is not None else "—"))

    # ══ 表T4 判决 ══
    t4 = ["# 表T4 · 预注册判决\n",
          "\n> 题级 n=3、题数 %d ⇒ 只报方向与范围，**不报 p 值**；"
          "「否证」与「低于分辨率」在 n=3 下无法区分 ⇒ 统一写「**未观察到支持**」。\n" % len(tids),
          "\n| 假说 | 对比 | 读数（按题） | 阈值 | 判决 |",
          "|---|---|---|---|---|"]

    def judge(arm_a, arm_b, key, thr, label):
        ds = []
        for tid in tids:
            d = delta(arm_a, arm_b, key, tid)
            if d is not None:
                ds.append(d)
        if not ds:
            t4.append("| %s | %s | **无数据** | ≥%.2f | **不可判** |" % (label, "", thr))
            return
        pos = sum(1 for d in ds if d > 0)
        neg = sum(1 for d in ds if d < 0)
        big = sum(1 for d in ds if abs(d) >= thr)
        vals = " / ".join("%+.3f" % d for d in ds)
        if big >= 2 and pos >= 2:
            v = "**成立**"
        elif big >= 2 and neg >= 2:
            v = "**成立（方向相反）**"
        else:
            v = "**未观察到支持**"
        t4.append("| %s | %s | %s | ≥%.2f | %s |" % (label, "%s vs %s" % (LAB[arm_a], LAB[arm_b]),
                                                     vals, thr, v))
    t4.append("> ★ **H-T2 的读数修正**（出表时发现）：原用「消耗率」⇒ **定义上恒等**"
              "（消耗率只依赖候选集，与选哪一支无关）⇒ 改用「选中支代表性」")

    # ★★ 修正（出表时发现，2026-10-24）：H-T2 原用「消耗率」⇒ **定义上恒等**
    #   （selector_consumption = (Vendi_cand−1)/Vendi_cand ⇒ **只依赖候选集**，与选哪一支无关）
    #   ⇒ ★ 改用「选中支代表性」：sample（弱选择器）应选到更不"代表性"的支
    judge("tot_sample_b5", "tot_greedy_b5", "repr", 0.05, "**H-T2'** 选择器强度（sample vs greedy → 选中支代表性）")
    judge("tot_vote_b5", "tot_greedy_b5", "repr", 0.05, "**H-T3'** 评估器类型（vote vs value → 选中支代表性）")
    judge("adhd_b5", "tot_greedy_b5", "consume", 0.10, "**H-T4** 外部基线（ADHD vs ToT → 消耗率）")
    t4.append("")
    t4.append("### ★ 报告性读数（不判效应）\n")
    t4.append("| 题 | 候选集 Vendi（5 支） | **选择器消耗率** | ToT 选中支代表性 |")
    t4.append("|---|--:|--:|--:|")
    for tid in tids:
        v = per.get(("tot_greedy_b5", tid))
        if v:
            t4.append("| %s | %.2f | %.3f | %.3f |"
                      % (tid, v["vendi"] or 0, v["consume"] or 0, v["repr"] or 0))
    t4.append("\n> **H-T1 / H-T1'**：原写「nosel vs tot_greedy 的面宽差」⇒ ★ **定义上恒等**"
              "（四臂共享同一次发散 ⇒ 候选集 Vendi 相同）⇒ **不可判** ⇒ 改以「消耗率」表达（见上表）。")

    # ══ 表T5 判别实验（若已跑）══
    cog = load(COG)
    t5 = ["# 表T5 · 判别实验：基线多样性水平 → 支间重叠度 / 论证路径数\n"]
    if not cog:
        t5.append("（**未跑** —— `runs/cogpos-matrix-2026-10-24/` 不存在）")
    else:
        cg = [g for g in cog["groups"] if g.get("arms")]
        ctids = sorted({g["tid"] for g in cg})
        t5 = ["# 表T5 · 判别实验：基线多样性水平 → 支间重叠度 / 论证路径数\n",
              "\n> ★ 三组基线 = 「同模型直调 3 次」（重叠 0.41–0.61）；我原基线 = 「5 框架+5 型号」（0.05–0.12）\n",
              "\n| 题 | 臂 | n | **词面共享度** | 分支差异 | **模态数（路径数）** | Vendi | self-BLEU | 调用数 |",
              "|---|---|--:|--:|--:|--:|--:|--:|--:|"]
        for g in sorted(cg, key=lambda x: (x["tid"], x["rep"])):
            for arm in sorted(g["arms"]):
                d = g["arms"][arm]
                t5.append("| %s | r%d | %s | %s | %s | %s | %s | %s | %s |"
                          % (g["tid"], g["rep"], arm, d.get("n_arts"), d.get("n_expected"),
                             ("%.4f" % d["lexical_sharing"]) if d.get("lexical_sharing") is not None else "—",
                             ("%.4f" % d.get("branch_diversity", 0)) if d.get("branch_diversity") is not None else "—",
                             d.get("modes", "—"),
                             d.get("vendi", "—"), d.get("self_bleu", "—"), d.get("n_calls", "—")))
        t5.append("\n### ★ 题内中位（按臂）\n")
        t5.append("| 臂 | **词面共享度** | 分支差异 | **模态数** | Vendi | self-BLEU |")
        t5.append("|---|--:|--:|--:|--:|--:|")
        for arm in sorted({a for g in cg for a in g["arms"]}):
            gs = [g["arms"][arm] for g in cg if g["arms"].get(arm) and g["arms"][arm].get("valid")]
            if not gs:
                continue
            t5.append("| %s | %.4f | %.4f | %.1f | %.2f | %.3f |"
                      % (arm, med([d["lexical_sharing"] for d in gs]),
                         med([d["branch_diversity"] for d in gs]),
                         med([d["modes"] for d in gs]),
                         med([d["vendi"] for d in gs]), med([d["self_bleu"] for d in gs])))

    for name, body in (("TOTARM-1-CHANNEL.md", t1), ("TOTARM-2-PER-GROUP.md", t2),
                       ("TOTARM-3-WITHIN.md", t3), ("TOTARM-4-VERDICT.md", t4),
                       ("TOTARM-5-COGPOS.md", t5)):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")
        print("✓ %s" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
