#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 部分预判决（★ 基于【已跑批单元】★ 不依赖整批跑完）★★

> 2026-10-25 ｜ 第二组 · 层2 拓扑臂 v2
> 落点：`creativity_lab/experiments/partial_verdict.py`

★ **用途**：★ 批未跑满时，★ 对【已落盘单元】做一次可复核的部分预判决 ★
★ ⇒ ★ 输出必须标【已跑批·部分 n=现值/目标】★★ ★ **不得**当作整批结论 ★

★★ **口径（★ 与 PREREG-TOPOLOGY-ARM.md 一致）★★
· 主读数层 = ★ **每臂 5 份【综述后 proposal】** ★（每 (题, rep, 臂) 5 次 run 的 `post`）
· 主读数 = ★ **绝对 Vendi**（★ 臂间 n 相等 ⇒ 直接可比 ★）；副读数 = modes / structured_dedup
· H0 零分布 = ★ **同臂、同题、不同 rep** 的读数差 ★（★ 唯一合法来源 ★）
· 主判据 = ★ **标准化效应量 = 差值 ÷ 题内 σ** ★；门槛 θ₀ = X₀/σ，★ X₀ = q95/√2 ★
· 辅助条件 = 方向一致（★ 但本项在题级 n=2 时【不可判定】★ ⇒ 如实写）
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from creativity_lab.metrics import modes                       # noqa: E402
from creativity_lab.metrics_ext import (distinct_n, self_bleu,  # noqa: E402
                                        structured_dedup_count, vendi_score)

ARMS = ["nosel_b3", "nosel_b3_synth", "topo_gs_homo", "topo_ngt_homo",
        "topo_sg_homo", "topo_ngt_hetero"]
CONTRASTS = {
    "H-TOPO-4a": ("topo_ngt_homo", "nosel_b3_synth"),   # 唯一差：有无交互
    "H-TOPO-4c": ("nosel_b3_synth", "nosel_b3"),        # 唯一差：有无综述
    "H-TOPO-4d": ("topo_ngt_homo", "topo_gs_homo"),    # 唯一差：轮内可见性图
}
MAIN_METRIC = "vendi"
TRI_SCALE = ("vendi", "modes", "structured_dedup")


# ─────────────────────────────────────────────────────────────
# 读数：与 topo_arm.read_set 同一函数（★ 同一口径 ★）
# ─────────────────────────────────────────────────────────────
def read_set(arts: List[str], vecs: List[List[float]]) -> Dict[str, Any]:
    if len(arts) < 2:
        return {"valid": False, "n": len(arts)}
    return {"valid": True, "n": len(arts),
            "vendi": round(vendi_score(vecs), 4),
            "modes": modes(vecs),
            "structured_dedup": structured_dedup_count(arts),
            "self_bleu": round(self_bleu(arts), 4),
            "distinct_2": round(distinct_n(arts, 2), 4)}


def load_groups(unit_dir: str, allowed=None) -> Dict[tuple, List[str]]:
    """(tid, rep, arm) → 该组已落盘的 run 的 `post` 文本（按 run 序）

    ★ `allowed`：★ 可选的「basename 集合」（★ 不含 .json ★）⇒ ★ 只读清单里的单元 ★
      ★ 用途：★ 批在跑时，★ 多个分析脚本若各自 glob，★ 就会读到【不同时刻】的单元集
      ★ ⇒ ★ 两个脚本的 n 可能差 1–2 ⇒ ★ 派生读数对不上 ⇒ ★
      ★ ⇒ ★ 做法：★ 冻结一份单元清单，★ 所有分析脚本都读它 ⇒ ★ n 结构性一致 ★
    """
    g: Dict[tuple, List[tuple]] = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(unit_dir, "*.json"))):
        b = os.path.basename(f)[:-5]
        if allowed is not None and b not in allowed:
            continue
        m = re.match(r"(\S+)_r(\d+)_(\S+)_u(\d+)$", b)
        if not m:
            continue
        tid, rep, arm, run = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        post = (d.get("post") or "").strip()
        if post:
            g[(tid, rep, arm)].append((run, post))
    return {k: [t for _r, t in sorted(v)] for k, v in g.items()}


# ─────────────────────────────────────────────────────────────
# H0：同臂同题不同 rep 的差
# ─────────────────────────────────────────────────────────────
def q95_nearest_rank(xs: List[float]) -> float:
    s = sorted(xs)
    if not s:
        return float("nan")
    import math as _m
    k = max(1, int(_m.ceil(0.95 * len(s))))
    return s[k - 1]


def q95_linear(xs: List[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    if n == 1:
        return s[0]
    pos = 0.95 * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def bootstrap_ci(xs: List[float], fn, n_boot: int, seed: int, alpha: float = 0.05):
    if len(xs) < 3:
        return (float("nan"), float("nan"))
    rnd = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        samp = [xs[rnd.randrange(len(xs))] for _ in range(len(xs))]
        vals.append(fn(samp))
    vals.sort()
    lo = vals[max(0, int((alpha / 2) * n_boot) - 1)]
    hi = vals[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return (lo, hi)


def sd(xs: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


# ─────────────────────────────────────────────────────────────
def consistency_from_dirs(tri_dirs):
    """★ 从「每把尺子的 (pos, neg) 计数」算一致性判定。★★

    ★ ★ 核心纪律（★ 2026-10-26 修 ★）：★ **零分辨力尺子必须先剔除** ★
    ★ 恒定尺子（全 0 diff）对【任何】对比都恒为「一致」⇒ 留在里面 ⇒
    ★ 一致性门变成【恒真】⇒ 「三尺一致 = 是」是空的。
    ★ ⇒ ⇒ **判据：一把尺子若在所有可比单元上 diff 全为 0 ⇒ 它对本对比零分辨力。★★

    返回 (dead_dirs, info_dirs, n_info, tri_consistent, tri_verdict)。
    ★ `tri_consistent` 为 None 表示【不可判定】（有信息的尺子不足 2 把）。
    """
    dead = {m: v for m, v in tri_dirs.items() if v[0] + v[1] == 0}
    info = {m: v for m, v in tri_dirs.items() if v[0] + v[1] > 0}
    n_info = len(info)
    if n_info < 2:
        return dead, info, n_info, None, (
            "★ 不可判定（★ 有信息的尺子只有 %d 把 ⇒ 一致性门无意义 ★）" % n_info)
    consistent = len({(v[0] > v[1]) for v in info.values()}) == 1
    return dead, info, n_info, consistent, ("是" if consistent else "否 ⇒ 不可分辨")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="★ 批的输出目录（★ 含 units/ ★）")
    ap.add_argument("--runs-per-arm", type=int, default=5)
    ap.add_argument("--target-units", type=int, default=360)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--unit-list", default=None,
                    help="★ 冻结的单元清单文件（★ 每行一个 basename，★ 不含 .json ★）⇒ ★ 与其它分析脚本同源 ★")
    a = ap.parse_args()

    unit_dir = os.path.join(a.out, "units")
    allowed = None
    if a.unit_list:
        if not os.path.isfile(a.unit_list):
            print("✘ unit-list 不存在：%s" % a.unit_list)
            return 2
        allowed = set(x.strip() for x in open(a.unit_list, encoding="utf-8") if x.strip())
        print("   ★ 单元清单：%s（★ %d 个 ★）" % (a.unit_list, len(allowed)))
    groups = load_groups(unit_dir, allowed)
    full = {k: v for k, v in groups.items() if len(v) >= a.runs_per_arm}
    n_units = sum(len(v) for v in groups.values())
    print("== 0. 覆盖 ==")
    print("   已落盘单元 %d / 目标 %d ｜ 满 %d run 的 (题,rep,臂) 组 %d"
          % (n_units, a.target_units, a.runs_per_arm, len(full)))

    if not full:
        print("   ✘ 没有满组的单元")
        return 3

    # ── 读数（主层：每组 5 份 post）──
    from creativity_lab.client import LLM
    llm = LLM()
    texts, need = [], []
    for k, arts in full.items():
        for t in arts:
            if t not in texts:
                texts.append(t)
    print("   嵌入文本 %d 条（embo-01）" % len(texts))
    vecs = llm.embed(texts)
    vmap = {t: v for t, v in zip(texts, vecs)}

    reads: Dict[tuple, Dict[str, Any]] = {}
    for k, arts in full.items():
        reads[k] = read_set(arts, [vmap[t] for t in arts])

    # ── H0 ──
    tids = sorted({k[0] for k in full})
    reps = sorted({k[1] for k in full})
    pairs = []
    for arm in ARMS:
        for tid in tids:
            if (tid, 1, arm) in reads and (tid, 2, arm) in reads:
                pairs.append((arm, tid))
    print("\n== 1. H0 标定（同臂、同题、不同 rep 的差）==")
    print("   可用配对数 = %d（★ 目标 21 ★）" % len(pairs))

    h0: Dict[str, Any] = {}
    for metric in TRI_SCALE + ("self_bleu", "distinct_2"):
        diffs = [reads[(t, 1, a)][metric] - reads[(t, 2, a)][metric] for a, t in pairs]
        adiffs = [abs(d) for d in diffs]
        q_nr, q_li = q95_nearest_rank(adiffs), q95_linear(adiffs)
        s = sd(diffs)
        ci = bootstrap_ci(adiffs, q95_linear, a.boot, a.seed)
        sci = bootstrap_ci(diffs, sd, a.boot, a.seed)
        x0 = q_li / math.sqrt(2.0)
        h0[metric] = {"n_pairs": len(pairs), "diffs": [round(d, 4) for d in diffs],
                      "q95_nearest_rank": round(q_nr, 4), "q95_linear": round(q_li, 4),
                      "q95_bootstrap_ci": [round(ci[0], 4), round(ci[1], 4)],
                      "sigma_rep": round(s, 4), "sigma_bootstrap_ci": [round(sci[0], 4), round(sci[1], 4)],
                      "X0_q95_over_sqrt2": round(x0, 4),
                      "theta0_standardized": round(x0 / s, 3) if s and s == s and s > 0 else None}
        print("   %-16s q95(nr)=%.4f q95(lin)=%.4f CI[%.4f,%.4f] ｜ σ=%.4f CI[%.4f,%.4f] ｜ X0=%.4f ｜ θ0=%.2fσ"
              % (metric, q_nr, q_li, ci[0], ci[1], s, sci[0], sci[1], x0,
                 (x0 / s) if s and s == s and s > 0 else float("nan")))

    sigma = h0[MAIN_METRIC]["sigma_rep"]
    theta0 = h0[MAIN_METRIC]["theta0_standardized"]

    # ── 主判据：三个单因子对比 ──
    print("\n== 2. 主判据（标准化效应量 = 差值 ÷ 题内 σ）==")
    print("   门槛 θ₀ = %.2f σ（★ 锚本批噪声地板 ★）" % theta0)
    verdicts: Dict[str, Any] = {}
    for name, (A, B) in CONTRASTS.items():
        cells = []
        for tid in tids:
            for rep in reps:
                if (tid, rep, A) in reads and (tid, rep, B) in reads:
                    cells.append((tid, rep))
        rows = []
        for tid, rep in cells:
            ra, rb = reads[(tid, rep, A)], reads[(tid, rep, B)]
            row = {"tid": tid, "rep": rep, "n_cells": len(cells)}
            for metric in TRI_SCALE:
                d = ra[metric] - rb[metric]
                row[metric + "_diff"] = round(d, 4)
                row[metric + "_std"] = round(d / sigma, 3) if sigma else None
            rows.append(row)
        # 方向一致（题级）：★ 题数太少时不可判定 ★
        by_tid = defaultdict(list)
        for r in rows:
            by_tid[r["tid"]].append(r[MAIN_METRIC + "_diff"])
        dir_votes = []
        for tid, ds in by_tid.items():
            m = sum(ds) / len(ds)
            dir_votes.append((tid, m, 1 if m > 0 else (-1 if m < 0 else 0)))
        n_tid = len(dir_votes)
        pos = sum(1 for _t, _m, s in dir_votes if s > 0)
        neg = sum(1 for _t, _m, s in dir_votes if s < 0)
        # 三尺一致（H-TOPO-5，仅面宽轴）
        tri_dirs = {m: (sum(1 for r in rows if r[m + "_diff"] > 0),
                        sum(1 for r in rows if r[m + "_diff"] < 0)) for m in TRI_SCALE}
        # ★★★ 2026-10-26 修：★ 零分辨力尺子必须【先剔除】再算一致性 ★★★
        #   恒定尺子（全 0 diff）对【任何】对比都恒为「一致」⇒ 留在里面 ⇒
        #   一致性门变成恒真 ⇒ 「三尺一致 = 是」是【空的】。
        #   判据：一把尺子若在所有可比单元上 diff 全为 0 ⇒ 它对本对比零分辨力。
        dead_dirs, info_dirs, n_info, tri_consistent, tri_verdict = consistency_from_dirs(tri_dirs)
        # 检出力：当前 n_cells 能检出的最小标准化效应（★ 用 H0 的 θ₀ 与单元数 ★）
        n_eff = len(rows)
        mde_std = theta0 * math.sqrt(2.0) if theta0 else None
        verdicts[name] = {"contrast": [A, B], "cells": rows, "n_cells": n_eff,
                           "n_tid": n_tid, "dir_votes": dir_votes, "pos": pos, "neg": neg,
                           "tri_dirs": tri_dirs, "tri_consistent": tri_consistent,
                           "tri_dead_rulers": dead_dirs, "n_rulers_informative": n_info,
                           "theta0": theta0, "mde_standardized_approx": mde_std}
        print("\n   ── %s：%s − %s（★ 唯一差一个因子 ★）" % (name, A, B))
        print("      可比单元 = %d（题 %s）｜ 题级 n = %d" % (n_eff, tids, n_tid))
        for r in rows:
            print("        %s r%d ｜ vendi %+.4f (%+.2fσ) ｜ modes %+d ｜ sdedup %+d"
                  % (r["tid"], r["rep"], r["vendi_diff"], r["vendi_std"],
                     r["modes_diff"], r["structured_dedup_diff"]))
        print("      题级方向：%s" % ("；".join("%s %+.4f" % (t, m) for t, m, _s in dir_votes) or "—"))
        print("      三尺方向：%s" % (tri_dirs,))
        if dead_dirs:
            print("      ★ 零分辨力尺子（★ 全 0 diff ⇒ 对本对比【无信息】★）：%s ⇒ ★ 已剔除，不参与一致性门 ★"
                  % (list(dead_dirs.keys()),))
        print("      ★ 三尺一致（★ 只在【有信息的 %d 把】尺子上算 ★）= %s" % (n_info, tri_verdict))
        print("      ★ 方向一致辅助条件：题级 n=%d ⇒ ★ 【≥2/3 题同向】不可判定 ★" % n_tid)

    # ── 检出力地板 ──
    print("\n== 3. 检出力地板（★ 报『不可分辨』时必须同时报它 ★）==")
    for name, (A, B) in CONTRASTS.items():
        v = verdicts[name]
        print("   %-12s n_cells=%d ｜ θ₀=%.2fσ ｜ ★ 当前每单元需 |标准化效应| > %.2fσ 才可判『有差异』★"
              % (name, v["n_cells"], theta0, theta0))
        print("               ⇒ ★ 若实际 |标准化效应| 落在 θ₀ 以下 ⇒ 结论只能是【不可分辨】★")

    out = {"n_units_actual": n_units, "n_units_target": a.target_units,
           "n_groups_full": len(full), "tids": tids, "reps": reps,
           "h0_pairs": len(pairs), "h0": h0, "theta0": theta0,
           "sigma_rep": sigma, "verdicts": verdicts,
           "status": "★ 已跑批·部分 n=%d/%d（★ 不得当作整批结论 ★）" % (n_units, a.target_units),
           "seed": a.seed, "n_boot": a.boot}
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        print("\n✓ 落盘 %s" % a.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
