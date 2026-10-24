#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
★ 【H0 检出力报告】—— ★ ★ **★ 报三个数（★ 2026-10-25 主会话要求）★★★** ★★
============================================================================

★ **★ 为什么要这个脚本（★ 主会话 ⑦）★★**
------------------------------------------------------------------------
★ **★ 问题：★ n=21 时 q95 的估计【很不稳】★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ q95 大致落在第 20 个顺序统计量上 ⇒ ⇒ ★ ⇒ **★ ⇒ 换一个样本，q95 可能跳 30%**★★** ⇒ ⇒ ★ ⇒
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 而它要跟第四组 σ_new 0.2457 做【跨组量级对照】⇒ ⇒ ★ ⇒⇒ **★ ⇒ ⇒ 【跨组对照的精度受限于【标定样本量】，★ 而不只是受限于【被对照那个读数】】★★** ★★**

★ **★ ⇒ ⇒ ★ ⇒ ★ 所以报 q95 时【必须同时报三样】★★**
------------------------------------------------------------------------
★ **① 【估计方法】** —— ★ **两种都报**：★ 【最近秩（nearest-rank）】与【线性插值（linear interpolation）】★★
★ ★ ⇒ ⇒ ★ ⇒ **★ ⇒ n=21 时两者差得不少 ⇒ ⇒ ★ ⇒ ⇒ 只报一个 = 【把方法选择藏起来】★★** ★★
★ **② 【不确定度】** —— ★ **bootstrap percentile 区间**（★ B=2000，★ 固定 seed ★）★★
★ **③ 【与题内 rep σ 的对照关系】** —— ★ **这两个数【是同源的】★★**
★ ★ ⇒ ⇒ ★ ⇒ **★ ⇒ 都来自【同题 rep 重复】⇒ ⇒ ★ ⇒ ⇒ **★ ⇒ ⇒ ⇒ ⇒ 它们【一起】才构成检出力门槛 ★】★★** ★★
★ ★ ⇒ ⇒ ★ ⇒ **★ ⇒ ⇒ ⇒ 【别把它们当两个独立的数报 ★】★★** ★★

★ **★ 另外必须一起报的（★ 作用域限制）★★**
------------------------------------------------------------------------
★ **★ 【★ 零结果的作用域被限死 ★】★★** ⇒ ★ **★ 本报告的零分布【只刻画【本批共享的那个上游随机源】下的 rep 间噪声】★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 它【不】刻画【题目难度差异】、★ 【不】刻画【跨模型差异】、★ 【不】刻画【别的上游服务】★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ ⇒ 任何【跨组、跨模型、跨题集】的 H0 比较，★ 【必须重新标定】，★ 不得【直接搬用】本批的 θ₀ ★★**

★ **★ 用法 ★★
------------------------------------------------------------------------
★   python3 -B creativity_lab/experiments/h0_report.py
★   ⇒ 落盘：★ runs/topo-arm-v2-2026-10-25/h0_report.json
★   ⇒ 退出码：★ 0 = 已出报告；★ 1 = 原料不足
"""

from __future__ import annotations

import itertools
import json
import math
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from creativity_lab.experiments.h0_calibration import (  # noqa: E402
    NEW, OLD, paired_diffs)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "runs", "topo-arm-v2-2026-10-25", "h0_report.json")
BOOT = 2000
SEED = 20261025


# ══════════════════════════════════════════════════════════════════════
# ★ 两个估计方法（★ n 小时结果不同 ⇒ 两个都报）★★
# ══════════════════════════════════════════════════════════════════════

def q_nearest_rank(xs, p):
    """★ 最近秩（★ 保守、★ 不插值 ★）★"""
    s = sorted(xs)
    if not s:
        return None
    import math as _m
    k = max(1, min(len(s), int(_m.ceil(p * len(s)))))
    return s[k - 1]


def q_linear(xs, p):
    """★ 线性插值（★ numpy 默认的 'linear' 口径 ★）★"""
    s = sorted(xs)
    if not s:
        return None
    if len(s) == 1:
        return s[0]
    h = (len(s) - 1) * p
    lo = int(math.floor(h))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def bootstrap_ci(xs, p, B=BOOT, seed=SEED):
    """★ bootstrap percentile 区间（★ 重抽样有放回 ★）★"""
    if len(xs) < 2:
        return None
    rng = random.Random(seed)
    stats = []
    n = len(xs)
    for _ in range(B):
        samp = [xs[rng.randrange(n)] for _ in range(n)]
        v = q_linear(samp, p)
        if v is not None:
            stats.append(v)
    if not stats:
        return None
    stats.sort()
    lo = stats[int(0.025 * (len(stats) - 1))]
    hi = stats[int(0.975 * (len(stats) - 1))]
    return (lo, hi)


def within_topic_sigma(path, arm, key="read_post", field="vendi"):
    """★ 题内 rep σ（★ 每个题内 rep 值的【样本标准差】★ ⇒ ★ 再取中位数 ★）★★

    ★ ★ 【★ 与 q95【同源】：★ 都来自【同题 rep 重复】★★】★
    ★ ⇒ ⇒ ★ ⇒ **★ ⇒ ⇒ 这两个数【一起】才构成检出力门槛 ★★**
    """
    if not os.path.exists(path):
        return []
    m = json.load(open(path, encoding="utf-8"))
    by_tid = {}
    for g in m.get("groups", []):
        d = (g.get("arms") or {}).get(arm)
        if not d:
            continue
        r = d.get(key)
        if isinstance(r, dict) and r.get(field) is not None:
            by_tid.setdefault(g["tid"], []).append(r[field])
    out = []
    for tid, vals in sorted(by_tid.items()):
        if len(vals) >= 2:
            out.append({"tid": tid, "n_reps": len(vals),
                        "sigma": statistics.stdev(vals),
                        "values": vals})
    return out


def main():
    new_d = paired_diffs(NEW, "nosel_b3")
    old_d = paired_diffs(OLD, "nosel_b5", key="read", field="vendi")
    all_d = new_d + old_d
    print("== ★ H0 原料（同题 rep 配对差 = 纯噪声）==")
    print("   新批 nosel_b3（层②口径）：%d 个" % len(new_d))
    print("   旧批 nosel_b5（层①口径）：%d 个" % len(old_d))
    print("   合计 %d 个同题配对差" % len(all_d))
    if len(all_d) < 6:
        print("★ 原料不足（%d）⇒ 等新批跑完再跑" % len(all_d))
        return 1

    diffs = [d["diff"] for d in all_d]
    absd = [abs(x) for x in diffs]
    n = len(absd)

    # ── ① q95（两个估计方法）──
    q_nr = q_nearest_rank(absd, 0.95)
    q_li = q_linear(absd, 0.95)
    ci = bootstrap_ci(absd, 0.95)
    print()
    print("== ★ ① q95（★ 报【两个估计方法】★ ⇒ n=%d 时两者差得不少 ★）==" % n)
    print("   最近秩 nearest-rank  q95 = %.4f" % q_nr)
    print("   线性插值 linear      q95 = %.4f" % q_li)
    print("   ⇒ 两法之差 = %.4f（★ %.1f%% of q95）" % (abs(q_li - q_nr), 100 * abs(q_li - q_nr) / max(abs(q_li), 1e-9)))
    print()
    print("== ★ ② 不确定度（★ bootstrap percentile 95%% 区间，★ B=%d）==" % BOOT)
    if ci:
        print("   q95 的 bootstrap 区间 = [%.4f, %.4f]" % ci)
        print("   ⇒ 区间宽度 = %.4f（★ %.1f%% of q95）★ ⇒ ★ 【n=%d 时 q95 的估计不稳】★"
              % (ci[1] - ci[0], 100 * (ci[1] - ci[0]) / max(abs(q_li), 1e-9), n))
    else:
        print("   ★ 原料太少 ⇒ 区间不可靠")

    # ── ③ 与题内 rep σ 的对照（★ 同源 ★）──
    sig_new = within_topic_sigma(NEW, "nosel_b3")
    sig_old = within_topic_sigma(OLD, "nosel_b5", key="read", field="vendi")
    sig_all = sig_new + sig_old
    sigs = [s["sigma"] for s in sig_all]
    print()
    print("== ★ ③ 题内 rep σ（★ ★ 【与 q95 同源】★ ⇒ 一起才是检出力门槛 ★）==")
    print("   新批题内 σ：%d 题" % len(sig_new))
    print("   旧批题内 σ：%d 题" % len(sig_old))
    if sigs:
        med = statistics.median(sigs)
        print("   题内 σ 中位数 = %.4f（★ 范围 %.4f – %.4f）" % (med, min(sigs), max(sigs)))
        thr = q_li / math.sqrt(2)
        print()
        print("   ★ ★ 【★ 检出力门槛 X₀ = q95/√2 = %.4f/%.4f = %.4f ★】★★" % (q_li, math.sqrt(2), thr))
        print("   ⇒ 与题内 σ 中位数（%.4f）之比 = %.2f" % (med, thr / max(med, 1e-9)))
        print("   ⇒ ★ ★ 【★ 标准化效应量 = 差值 ÷ 题内 σ ⇒ ★ ⇒ 门槛 X₀/σ = %.2f 个题内 σ ★】★★"
              % (thr / max(med, 1e-9)))
        print("   ⇒ ★ ★ 【★ 跨组对照（★ 例：★ 第四组 σ_new 0.2457）★ ⇒ ★ ★ 只能说【量级】★★")
        print("      ⇒ ★ 第四组若报的是【题内 σ】⇒ ★ 可比；★ 若是【别的口径】⇒ ★ ★ 不可比 ★★")
    else:
        print("   ★ 题内 σ 还不可算（★ 新批未跑完）")

    payload = {
        "n_total": n, "n_new": len(new_d), "n_old": len(old_d),
        "q95": {"nearest_rank": q_nr, "linear": q_li,
                "bootstrap_ci95": list(ci) if ci else None,
                "bootstrap_B": BOOT, "bootstrap_seed": SEED},
        "threshold_X0": (q_li / math.sqrt(2)) if q_li is not None else None,
        "within_topic_sigma": {"per_topic": sig_all,
                                "median": statistics.median(sigs) if sigs else None},
        "scope_note": ("★ 本报告的零分布【只刻画本批共享的那个上游随机源】下的 rep 间噪声；★ "
                       "不刻画题目难度差异、不刻画跨模型差异、不刻画别的上游服务。★ "
                       "跨组/跨模型/跨题集比较必须重新标定。★"),
        "cross_group_note": ("★ 跨组量级对照时，★ 必须先核【对方报的是不是【题内 rep σ】】——★ "
                             "口径不同则不可比。★ 精度同时受限于【标定样本量 n=%d】与【对方读数】。" % n),
        "diffs": all_d,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print()
    print("✔ 落盘：%s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
