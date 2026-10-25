#!/usr/bin/env python3
"""**2×2 任务结构对照的证据表 + 按预注册判决**。

> 落点：`creativity_lab/experiments/build_2x2_tables.py`
> 输入：`runs/divergence-matrix-2x2-2026-10-24/`
> 预注册：`docs/cmp8/routes/COLLAPSE/eval/PREREG-2X2.md`（判决规则写在那里）
>
> ★ 判决纪律：
> 1. **以题为单位**，不把同格的题当独立样本做统计
> 2. 模态数差 **≥2** 且 **≥2/3 组同向** 才算支持（预注册 §3）
> 3. **H-2x2-B 若成立 ⇒ H-2x2-A 的归因必须改写**（唯一解 > 理科）
> 4. 题级 n=3 ⇒ 只报方向与范围，**不报 p 值**
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN = os.path.join(ROOT, "runs", "divergence-matrix-2x2-2026-10-24")
OUT = os.path.join(ROOT, "docs", "cmp8", "routes", "COLLAPSE", "eval", "results")
MODE_THR = 2          # ★ 预注册：模态数差 ≥2
CONS_THR = 0.8        # ★ 预注册：一致率 ≥0.8
CELL = {"T1": ("文科", "多解"), "S4": ("文科", "唯一解"),
        "T2": ("理科", "唯一解"), "S1": ("理科", "唯一解"),
        "S2": ("理科", "唯一解"), "S3": ("理科", "唯一解"),
        "T3": ("理科", "多解")}


def med(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def main() -> int:
    man = json.load(open(os.path.join(RUN, "manifest.json"), encoding="utf-8"))
    h = man["health"]
    groups = man["groups"]
    # 数值一致性（用同一个提取器）
    from creativity_lab.experiments.num_consistency import consistency_of
    rows: List[Dict[str, Any]] = []
    for g in groups:
        gp = os.path.join(RUN, "group_%s_r%d.json" % (g["tid"], g["rep"]))
        if not os.path.exists(gp):
            continue
        full = json.load(open(gp, encoding="utf-8"))
        d = g["arms"].get("base")
        if not d or not d.get("valid"):
            continue
        arts = full["arms"]["base"]["arts"]
        cons = consistency_of(arts)
        rows.append({"tid": g["tid"], "rep": g["rep"], "modes": d["modes"],
                     "effective_rank": d["effective_rank"],
                     "lexical_sharing": d["lexical_sharing"],
                     "cons_mean": cons["mean_agreement"],
                     "cons_nq": cons["n_questions_with_values"],
                     "cons": cons["per_q"]})
    tids = sorted({r["tid"] for r in rows}, key=lambda t: (CELL.get(t, ("zz", "zz"))[0], t))

    # ── 表X1：通道 + 分母 ──
    t1 = ["# 表X1 · 通道健康与分母\n", "\n| 项 | 值 |\n|---|---:|"]
    for k in ("n_groups", "n_arms", "n_calls_total", "n_calls_failed", "n_calls_truncated",
              "n_calls_empty", "channel_health", "n_branch_deficit"):
        t1.append("| %s | %s |" % (k, h.get(k)))
    t1.append("| 型号池 | %s |" % ", ".join(h.get("model_pool", [])))
    t1.append("| 已下架（剔除） | %s |" % ", ".join(h.get("dead_models", [])))

    # ── 表X2：逐组 ──
    t2 = ["# 表X2 · 逐组读数（2×2 任务结构）\n",
          "\n| 题 | 格子 | 组 | 模态数 | 有效秩 | 词面共享度 | 数值一致率 | 逐问一致 |",
          "|---|---|--:|--:|--:|--:|--:|---|"]
    for r in sorted(rows, key=lambda x: (x["tid"], x["rep"])):
        dom, uni = CELL.get(r["tid"], ("?", "?"))
        per = "；".join("(%s) %d/%d→%s" % (q, v["n_agree"], v["n_extractable"], v["modal_value"])
                        for q, v in r["cons"].items())
        t2.append("| %s | %s·%s | r%d | %d | %.2f | %.3f | %s | %s |"
                  % (r["tid"], dom, uni, r["rep"], r["modes"], r["effective_rank"],
                     r["lexical_sharing"],
                     ("%.2f" % r["cons_mean"]) if r["cons_mean"] is not None else "—", per))

    # ── 表X3：按题汇总 + 2×2 格子 ──
    t3 = ["# 表X3 · 按题汇总 与 2×2 格子\n",
          "\n| 题 | 格子 | n 组 | 模态数（中位） | 模态数范围 | 有效秩（中位） | 词面共享度 | 数值一致率（中位） | 抽到数值的问数 |",
          "|---|---|--:|--:|---|--:|--:|--:|--:|"]
    per_tid = {}
    for tid in tids:
        rs = [r for r in rows if r["tid"] == tid]
        per_tid[tid] = rs
        dom, uni = CELL.get(tid, ("?", "?"))
        cm = [r["cons_mean"] for r in rs if r["cons_mean"] is not None]
        t3.append("| %s | %s·%s | %d | **%.1f** | %d–%d | %.2f | %.3f | %s | %d |"
                  % (tid, dom, uni, len(rs), med([r["modes"] for r in rs]),
                     min(r["modes"] for r in rs), max(r["modes"] for r in rs),
                     med([r["effective_rank"] for r in rs]),
                     med([r["lexical_sharing"] for r in rs]),
                     ("%.2f" % med(cm)) if cm else "—",
                     sum(r["cons_nq"] for r in rs)))

    # ── 表X4：判决（严格按预注册）──
    def modes_of(tid):
        rs = per_tid.get(tid, [])
        return med([r["modes"] for r in rs]) if rs else None

    def cons_of(tid):
        rs = per_tid.get(tid, [])
        cm = [r["cons_mean"] for r in rs if r["cons_mean"] is not None]
        return med(cm) if cm else None

    t4 = ["# 表X4 · 判决（严格按 `PREREG-2X2.md` §3：模态数差 ≥2 且 ≥2/3 组同向）\n"]
    # H-2x2-A：理科唯一解 vs 文科多解
    stem_u = [t for t in tids if CELL.get(t, ("", ""))[0] == "理科" and CELL[t][1] == "唯一解"]
    hum_m = [t for t in tids if CELL.get(t, ("", ""))[0] == "文科" and CELL[t][1] == "多解"]
    t4.append("\n### H-2x2-A · 理科题更易塌缩（理科唯一解 vs 文科多解）\n")
    t4.append("\n| 对比 | 理科唯一解 | 文科多解 | 差值 | 门槛 | 判决 |\n|---|--:|--:|--:|:--:|---|")
    for t in stem_u:
        for u in hum_m:
            a, b = modes_of(t), modes_of(u)
            if a is None or b is None:
                continue
            d = a - b
            ok = d <= -MODE_THR
            t4.append("| %s(%s) vs %s(%s) | %.1f | %.1f | %+.1f | ≤−%d | %s |"
                      % (t, CELL[t][1], u, CELL[u][1], a, b, d, MODE_THR,
                         "✔ 支持" if ok else "✘"))
    # H-2x2-B：文科唯一解 vs 文科多解
    hum_u = [t for t in tids if CELL.get(t, ("", ""))[0] == "文科" and CELL[t][1] == "唯一解"]
    t4.append("\n### H-2x2-B · ★ 塌缩由「唯一解」驱动，不由「理科」驱动\n")
    t4.append("\n| 对比 | 文科唯一解 | 文科多解 | 差值 | 门槛 | 判决 |\n|---|--:|--:|--:|:--:|---|")
    b_ok = False
    for t in hum_u:
        for u in hum_m:
            a, b = modes_of(t), modes_of(u)
            if a is None or b is None:
                continue
            d = a - b
            ok = d <= -MODE_THR
            b_ok = b_ok or ok
            t4.append("| %s vs %s | %.1f | %.1f | %+.1f | ≤−%d | %s |"
                      % (t, u, a, b, d, MODE_THR, "✔ 支持" if ok else "✘"))
    t4.append("\n> ★ **这是主判据**：若 H-2x2-B 成立 ⇒ **H-2x2-A 的归因必须改写**"
              "（是「唯一解」，不是「理科」）。\n")
    # H-2x2-C / D
    t4.append("\n### H-2x2-C / D · 理科题的塌缩是「大家都算对了」还是「真钻牛角尖」\n")
    t4.append("\n| 题 | 格子 | 模态数（中位） | 数值一致率（中位） | 签名 | 判定 |\n|---|---|--:|--:|---|---|")
    true_drill = False
    for tid in tids:
        m, c = modes_of(tid), cons_of(tid)
        if m is None:
            continue
        dom, uni = CELL.get(tid, ("?", "?"))
        if c is None:
            sig, verdict = "无一致率可算", "—"
        elif m <= 2 and c >= CONS_THR:
            sig, verdict = "**低模态 + 高一致**", "⇒ 大家都算出同一个数 ⇒ **不是钻牛角尖**"
        elif m <= 2 and c < 0.5:
            sig, verdict = "**低模态 + 低一致**", "★★ **真·钻牛角尖签名**"
            true_drill = True
        elif m > 2 and c is not None and c >= CONS_THR:
            sig, verdict = "高模态 + 高一致", "⇒ 答案一致但走的是不同路"
        else:
            sig, verdict = "其它", "—"
        t4.append("| %s | %s·%s | %.1f | %s | %s | %s |"
                  % (tid, dom, uni, m, ("%.2f" % c) if c is not None else "—", sig, verdict))
    t4.append("\n**H-2x2-C 判决**：%s\n" % ("**成立**" if any(
        (modes_of(t) is not None and modes_of(t) <= 2 and cons_of(t) is not None
         and cons_of(t) >= CONS_THR) for t in tids) else "**不成立/证据不足**"))
    t4.append("**H-2x2-D 判决**：%s\n" % ("★ **存在真·钻牛角尖的题**" if true_drill
                                        else "**当前任务集上不存在「钻牛角尖」签名** ⇒ ⇒ "
                                             "「治塌缩」没有靶子"))
    t4.append("\n## 边界\n")
    t4.append("- ⚠️ **S4 是自编题** ⇒ 若它的行为异常，先怀疑题。\n")
    t4.append("- ⚠️ **一致性 ≠ 正确性** ⇒ 只说「5 支算出同一个数」，不说「算对了」。\n")
    t4.append("- ⚠️ **每格题数不等** ⇒ 跨格比较以**题为单位**报方向，不做统计。\n")
    t4.append("- ⚠️ **题级 n=3** ⇒ 不报 p 值。\n")

    for name, body in (("DIVERGENCE-2X2-1-CHANNEL.md", t1),
                       ("DIVERGENCE-2X2-2-PER-GROUP.md", t2),
                       ("DIVERGENCE-2X2-3-SUMMARY.md", t3),
                       ("DIVERGENCE-2X2-4-VERDICT.md", t4)):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")
        print("✓ %s" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
