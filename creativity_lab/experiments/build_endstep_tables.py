#!/usr/bin/env python3
"""**把末步对照的读数变成证据表**（程序化生成 ⇒ 表里没有手写数字）。

> 2026-10-23 ｜ 落点：`creativity_lab/experiments/build_endstep_tables.py`
> 输入：`runs/endstep-matrix-2026-10-23/manifest.json`
> 输出：`docs/cmp8/routes/COLLAPSE/eval/results/ENDSTEP-*.md`（进 git）
>
> ★ 读数纪律：**报范围/曲线，不报单点**（阈值敏感、样本小）。
> ★ 每个表都带**分母**（组数、有效组数、通道失败数）。
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

import sys as _sys
_sys.path.insert(0, "/workspace/lab")
from creativity_lab.metrics import self_coverage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN = os.path.join(ROOT, "runs", "endstep-matrix-2026-10-23")
OUT = os.path.join(ROOT, "docs", "cmp8", "routes", "COLLAPSE", "eval", "results")
ARMS = ["end_fuse", "end_greedy", "end_sample", "end_raw"]
ARMLABEL = {"end_fuse": "融合门（LLM）", "end_greedy": "纯函数·选最独特",
            "end_sample": "纯函数·加权随机", "end_raw": "不做末步（参照）"}


def med(v: List[float]):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def rng(v: List[float]):
    v = [x for x in v if x is not None]
    return (min(v), max(v)) if v else (None, None)


def main() -> int:
    man = json.load(open(os.path.join(RUN, "manifest.json"), encoding="utf-8"))
    h = man["health"]
    groups = man["groups"]
    valid = [g for g in groups if g.get("valid")]
    # ★ manifest 里没有 `arts`（体积大，被排除）⇒ 自覆盖率要从组文件补读
    for g in valid:
        gp = os.path.join(RUN, "group_%s_r%d.json" % (g["tid"], g["rep"]))
        if os.path.exists(gp):
            try:
                g["arts"] = json.load(open(gp, encoding="utf-8")).get("arts")
            except Exception:                      # noqa: BLE001
                g["arts"] = None
    os.makedirs(OUT, exist_ok=True)

    # ── 表1：通道健康 ───────────────────────────────
    t1 = ["# 表1 · 通道健康（分母齐全）\n",
          "> 源：`runs/endstep-matrix-2026-10-23/manifest.json`｜"
          "生成：`creativity_lab/experiments/build_endstep_tables.py`\n",
          "\n| 项 | 值 |\n|---|---:|"]
    for k in ("n_groups", "n_valid", "n_channel_failed", "n_calls_total", "n_calls_failed",
              "n_calls_truncated", "n_calls_empty", "channel_health", "model", "effort",
              "thr", "seed_base"):
        t1.append("| %s | %s |" % (k, h.get(k)))
    t1.append("| 分支型号池 | %s |" % ", ".join(h.get("model_pool", [])))
    t1.append("| **已下架型号（被剔除）** | %s |" % ", ".join(h.get("dead_models", [])))
    t1.append("\n> ★ **下架型号必须显式剔除**：M2.1 / M2 / M2.1-highspeed 实测 404 ⇒\n"
              "> 死分支会被**静默丢弃** ⇒ 发散层 5 支变 4 支 ⇒ **分母漂移而表看不出来**。\n")

    # ── 表2：逐组读数 ───────────────────────────────
    t2 = ["# 表2 · 逐组读数（4 臂共享同一发散层）\n",
          "\n| 组 | 分支 | 面宽@0.3 | 面深 | 语义宽 | 语义深 | **自覆盖率** | 输出字数 | 字/覆盖 | 定长400 覆盖 | 定长400 深 |",
          "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for g in valid:
        for arm in ARMS:
            d = g["arms"].get(arm)
            if not d:
                continue
            emb = d.get("emb") or {}
            fl = next((x for x in (d.get("fixed_len") or []) if x["L"] == 400), {})
            arts = g.get("arts")
            sc = self_coverage(arts, d["text"]) if arts else None
            t2.append("| %s r%d · %s | %d | %d | %.3f | %s | %s | %s | %d | %s | %s | %s |"
                      % (g["tid"], g["rep"], ARMLABEL[arm], g["n_arts"],
                         d["covered_branches"], d["survival_rate"],
                         ("%d" % emb.get("width", "—")) if emb else "—",
                         ("%.3f" % emb.get("mean_inc", 0)) if emb else "—",
                         ("%.3f" % sc) if sc is not None else "—",
                         d["out_chars"],
                         ("%.0f" % d["chars_per_covered"]) if d.get("chars_per_covered") else "—",
                         fl.get("covered", "—"), fl.get("survival", "—")))
    t2.append("\n> 有效组 %d / %d（通道失败 %d）\n" % (len(valid), len(groups), h["n_channel_failed"]))

    # ── 表3：阈值曲线（面宽 vs 阈值）─────────────────
    t3 = ["# 表3 · 阈值曲线（**面宽**随判定阈值的变化）\n",
          "\n> ★ 阈值敏感 ⇒ **单点数字不可引用**；下面给的是**中位数 + 范围**。\n",
          "\n| 臂 | thr=0.10 | 0.20 | 0.30 | 0.40 | 0.50 | 0.60 |\n|---|--:|--:|--:|--:|--:|--:|"]
    for arm in ARMS:
        cells = []
        for t in ("0.10", "0.20", "0.30", "0.40", "0.50", "0.60"):
            vs = [g["arms"][arm]["coverage_curve"][t] for g in valid
                  if arm in g.get("arms", {}) and t in g["arms"][arm]["coverage_curve"]]
            m = med(vs)
            lo, hi = rng(vs)
            cells.append("**%.1f**" % m if m is not None else "—")
            if m is not None and hi is not None and hi != lo:
                cells[-1] += " (%.0f–%.0f)" % (lo, hi)
        t3.append("| %s | %s |" % (ARMLABEL[arm], " | ".join(cells)))

    # ── 表4：定长对照（消除"多写"混淆）──────────────
    t4 = ["# 表4 · 定长对照（输出截到 L 字再算覆盖）\n",
          "> ★ **这是本实验的关键控制**：各臂输出量天然不同 ⇒ 不控长度就是在测"
          "「谁写得多」而不是「谁留得下」。\n",
          "\n| 臂 | L | 面宽@0.3（中位） | 面深（中位） | 输出字数（中位） |\n|---|--:|--:|--:|--:|"]
    for arm in ARMS:
        for L in (300, 400, 600):
            cov, surv, ch = [], [], []
            for g in valid:
                d = g["arms"].get(arm)
                if not d:
                    continue
                fl = next((x for x in (d.get("fixed_len") or []) if x["L"] == L), None)
                if fl:
                    cov.append(fl["covered"]); surv.append(fl["survival"]); ch.append(fl["chars"])
            if not cov:
                continue
            t4.append("| %s | %d | **%.1f** | %.3f | %.0f |"
                      % (ARMLABEL[arm], L, med(cov) or 0, med(surv) or 0, med(ch) or 0))

    # ── 表5：汇总 ───────────────────────────────────
    t5 = ["# 表5 · 汇总（每臂一行，中位数 + 范围）\n",
          "\n| 臂 | 面宽@0.3 | 面深 | 语义宽 | 语义深 | 输出字数 | LLM 调用/组 |\n",
          "|---|--:|--:|--:|--:|--:|--:|"]
    for arm in ARMS:
        cov, sur, ew, ed, ch, cl = [], [], [], [], [], []
        for g in valid:
            d = g["arms"].get(arm)
            if not d:
                continue
            cov.append(d["covered_branches"]); sur.append(d["survival_rate"])
            ch.append(d["out_chars"]); cl.append(d["n_calls"])
            if d.get("emb"):
                ew.append(d["emb"]["width"]); ed.append(d["emb"].get("mean_inc", 0))
        t5.append("| %s | **%.1f** (%.0f–%.0f) | %.3f (%.3f–%.3f) | %.1f | %.3f | %.0f (%.0f–%.0f) | %.1f |"
                  % (ARMLABEL[arm], med(cov) or 0, *rng(cov), med(sur) or 0, *rng(sur),
                     med(ew) or 0, med(ed) or 0, med(ch) or 0, *rng(ch), med(cl) or 0))

    # ── 表6：语义面宽的两种口径（为什么必须用增量判据）──
    t6 = ["# 表6 · 语义面宽的**两种口径**（为什么必须用增量判据）\n",
          "> 旧口径：组内归一化 cos ≥0.7 就算覆盖。\n",
          "> 新口径（**增量**）：`cos(支j,输出) > max_{k≠j} cos(支j,支k)`（严格大于）。\n",
          "> ⇒ 旧口径会把「输出=某支原文」误报成留了多支（分支之间本来就相似）。\n",
          "\n| 臂 | 旧口径 面宽 | **新口径 面宽** | 语义面深(增量均值) |\n|---|--:|--:|--:|"]
    for arm in ARMS:
        wn, wn2, mi = [], [], []
        for g in valid:
            d = g["arms"].get(arm)
            if not d or not d.get("emb"):
                continue
            wn.append(d["emb"].get("width_naive", 0))
            wn2.append(d["emb"].get("width", 0))
            mi.append(d["emb"].get("mean_inc", 0))
        if wn:
            t6.append("| %s | %.1f | **%.1f** | %.3f |" % (ARMLABEL[arm], med(wn) or 0, med(wn2) or 0, med(mi) or 0))

    for name, body in (("ENDSTEP-1-CHANNEL.md", t1), ("ENDSTEP-2-READINGS.md", t2),
                       ("ENDSTEP-6-SEMANTIC-CALIBRATION.md", t6),
                       ("ENDSTEP-3-CURVE.md", t3), ("ENDSTEP-4-FIXEDLEN.md", t4),
                       ("ENDSTEP-5-SUMMARY.md", t5)):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")
        print("✓ %s" % name)
    print("\n有效组 %d / %d" % (len(valid), len(groups)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
