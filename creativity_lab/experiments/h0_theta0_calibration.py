#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **θ₀ 的多口径重算 + 判决影响评估**（★ 2026-10-24 第 1 层论证线质询触发）

> 落点：`creativity_lab/experiments/h0_theta0_calibration.py`
> 数据：新批 `runs/topo-arm-v2-2026-10-24`（层②口径）＋ 旧批 `runs/tot-arm-2026-10-24`（层①口径）
> 输出：`runs/topo-arm-v2-2026-10-24/h0_theta0_multicalib.json`

★★ **为什么有这个脚本** ★★
★ 预注册 `docs/cmp8/routes/COLLAPSE/eval/PREREG-TOPOLOGY-ARM.md` §5.0b2-i 写死的 H0 原料是：
★ **① 正式批 `nosel_b3`（层②口径，6 题 × 2 rep = 12 个同题配对差）② 旧批 `nosel_b5`（层①口径，3 题 × 3 rep = 9 个）⇒ 共 21 个**。
★ 而 `partial_verdict.py` 实际用的是【全部臂】配对（`for arm in ARMS`）且未并旧批 ⇒ **口径偏离预注册**。
★ ⇒ 本脚本把四套口径**并列算一遍**，并逐套**重算判决**，回答一个问题：
★ **「θ₀ 差多少」＋「判决结论是否随之改变」。**

★★ **四套口径（★ 全部用同一条 `read_set` 口径）★★
| 口径 | 原料 | 地位 |
|---|---|---|
| `A_all_arms` | 新批 **全部 6 臂** × 同题 rep1−rep2 | ★ **当前实现实际用的**（偏离预注册） |
| `B_prereg_new` | 新批 **`nosel_b3`** × 同题 rep1−rep2 | ★ **预注册主项** |
| `B_prereg_full` | `B_prereg_new` ＋ 旧批 `nosel_b5` 9 个 | ★ **预注册完整口径（21 个）** |
| `C_old_only` | 旧批 `nosel_b5` 9 个 | ★ **诊断用**：跨口径混合是否有效 |

★★ **输出（★ 每个口径都要能独立复核）★★
· H0 统计量：n_pairs / q95(nearest-rank, linear) / q95 bootstrap CI / σ / σ bootstrap CI / X₀=q95_lin/√2 / θ₀=X₀/σ
· 判决重算：三个单因子对比在**该口径的 σ 与 θ₀ 下**的「超门槛格数 / 题级方向 / 三尺一致」
· 判决结论格（四格：成立 / 未观察到支持 / 不可分辨 / 未检验）

★★ **纪律** ★★
★ ① **同口径重算**：读数一律走 `partial_verdict.load_groups` + `partial_verdict.read_set`（★ 同一函数 ⇒ 同一口径 ★）
★ ② **回源闸门**：旧批读数用【存档 `read.vendi`】并用 `arts` **独立重算一遍逐值比对**（★ 不一致即报错退出 ★）
★ ③ **旧批层① vs 新批层②的量纲差**单独报（★ 跨口径混合是否有效 ★）
★ ④ **不碰正在跑的批代码**（`topo_arm.py` / `client.py` 一律不改）★
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from creativity_lab.experiments.partial_verdict import (  # noqa: E402
    ARMS, CONTRASTS, MAIN_METRIC, TRI_SCALE, consistency_from_dirs,
    load_groups, q95_linear, q95_nearest_rank, read_set, sd,
)

NEW_DIR = os.path.join(ROOT, "runs", "topo-arm-v2-2026-10-24")
OLD_MANIFEST = os.path.join(ROOT, "runs", "tot-arm-2026-10-24", "manifest.json")


def bootstrap_ci(xs, fn, n_boot: int, seed: int, alpha: float = 0.05):
    """★ 与 `partial_verdict.bootstrap_ci` 同实现（★ 避免跨文件 import 漂移 ★）"""
    import random
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


# ─────────────────────────────────────────────────────────────
# 旧批：层①口径（nosel_b5）读数 —— 存档值 + 独立重算闸门
# ─────────────────────────────────────────────────────────────
def old_nosel_b5_reads(recompute: bool) -> Tuple[Dict[Tuple[str, int], Dict[str, Any]], Dict[str, Any]]:
    """返回 {(tid, rep): {'vendi':…, 'n':…}} + 闸门报告。

    ★ 闸门：用存档 `arts` 走【同一个 read_set】重算 vendi，与存档 `read.vendi` 逐值比对。
    ★ 不一致 ⇒ raise（★ 不许输出"看起来对"的结果 ★）
    """
    m = json.load(open(OLD_MANIFEST, encoding="utf-8"))
    out: Dict[Tuple[str, int], Dict[str, Any]] = {}
    mismatch = []
    checked = 0
    for g in m.get("groups", []):
        d = (g.get("arms") or {}).get("nosel_b5")
        if not d:
            continue
        rec = d.get("read") or {}
        v_stored = rec.get("vendi")
        if v_stored is None:
            continue
        out[(g["tid"], g["rep"])] = {"vendi": v_stored, "n": rec.get("n")}
        if recompute:
            arts = [a for a in (d.get("arts") or []) if isinstance(a, str) and a.strip()]
            if arts:
                from creativity_lab.client import LLM
                vecs = LLM().embed(arts)
                v_re = read_set(arts, vecs)["vendi"]
                checked += 1
                if abs(v_re - v_stored) > 1e-6:
                    mismatch.append({"tid": g["tid"], "rep": g["rep"],
                                     "stored": v_stored, "recomputed": v_re})
    gate = {"n_checked": checked, "n_mismatch": len(mismatch),
            "mismatch": mismatch,
            "passed": len(mismatch) == 0}
    return out, gate


# ─────────────────────────────────────────────────────────────
# H0 统计量
# ─────────────────────────────────────────────────────────────
def h0_stats(diffs: List[float], boot: int, seed: int) -> Dict[str, Any]:
    adiffs = [abs(d) for d in diffs]
    q_nr = q95_nearest_rank(adiffs)
    q_li = q95_linear(adiffs)
    s = sd(diffs)
    ci = bootstrap_ci(adiffs, q95_linear, boot, seed)
    sci = bootstrap_ci(diffs, sd, boot, seed)
    x0 = q_li / math.sqrt(2.0)
    return {
        "n_pairs": len(diffs),
        "diffs": [round(d, 4) for d in diffs],
        "q95_nearest_rank": round(q_nr, 4),
        "q95_linear": round(q_li, 4),
        "q95_bootstrap_ci": [round(ci[0], 4), round(ci[1], 4)],
        "sigma_rep": round(s, 4) if s == s else None,
        "sigma_bootstrap_ci": [round(sci[0], 4), round(sci[1], 4)],
        "X0_q95_over_sqrt2": round(x0, 4),
        "theta0_standardized": round(x0 / s, 3) if s and s == s and s > 0 else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=NEW_DIR)
    ap.add_argument("--runs-per-arm", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--no-recompute-old", action="store_true",
                    help="★ 跳过旧批独立重算闸门（★ 默认要跑 ★）")
    ap.add_argument("--unit-list", default=None,
                    help="★ 冻结的单元清单文件（★ 每行一个 basename ★）⇒ ★ 与 partial_verdict 同源 ★")
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
    tids = sorted({k[0] for k in full})
    reps = sorted({k[1] for k in full})
    print("== 0. 覆盖 ==")
    print("   已落盘单元 %d ｜ 满 %d run 的 (题,rep,臂) 组 %d ｜ 题 %s ｜ rep %s"
          % (n_units, len(full), len(full), tids, reps))
    if not full:
        print("   ✘ 没有满组的单元")
        return 3

    # ── 读数（同口径）──
    from creativity_lab.client import LLM
    llm = LLM()
    texts = []
    for k, arts in full.items():
        for t in arts:
            if t not in texts:
                texts.append(t)
    print("   嵌入文本 %d 条" % len(texts))
    vecs = llm.embed(texts)
    vmap = {t: v for t, v in zip(texts, vecs)}
    reads: Dict[tuple, Dict[str, Any]] = {}
    for k, arts in full.items():
        reads[k] = read_set(arts, [vmap[t] for t in arts])

    # ── 旧批（层①）──
    old_reads, gate = old_nosel_b5_reads(recompute=not a.no_recompute_old)
    print("\n== 旧批回源闸门（★ 层① nosel_b5：存档 vs 独立重算）==")
    print("   核对 %d 组 ｜ 不符 %d 组 ⇒ %s"
          % (gate["n_checked"], gate["n_mismatch"],
             "✔ 通过" if gate["passed"] else "✘★ 不通过 ⇒ 报错退出 ★"))
    if not gate["passed"]:
        print(json.dumps(gate["mismatch"], ensure_ascii=False, indent=1))
        return 4

    # ── 四套口径的配对差 ──
    def new_pairs(arms: List[str]) -> List[Tuple[str, str, int]]:
        out = []
        for arm in arms:
            for tid in tids:
                if (tid, 1, arm) in reads and (tid, 2, arm) in reads:
                    out.append((arm, tid, 0))
        return out

    def old_pairs() -> List[Tuple[str, str, int]]:
        out = []
        by_tid = defaultdict(list)
        for (tid, rep), r in old_reads.items():
            by_tid[tid].append((rep, r["vendi"]))
        for tid, lst in by_tid.items():
            lst.sort()
            for i in range(len(lst)):
                for j in range(i + 1, len(lst)):
                    out.append(("nosel_b5", tid, 1))
                    break
        return out

    # 旧批：每题 C(rep,2) 对（3 rep ⇒ 3 对）
    old_diffs: List[float] = []
    old_detail: List[Dict[str, Any]] = []
    by_tid = defaultdict(list)
    for (tid, rep), r in old_reads.items():
        by_tid[tid].append((rep, r["vendi"]))
    for tid, lst in sorted(by_tid.items()):
        lst.sort()
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                d = lst[i][1] - lst[j][1]
                old_diffs.append(d)
                old_detail.append({"arm": "nosel_b5", "tid": tid,
                                   "rep_pair": (lst[i][0], lst[j][0]),
                                   "diff": round(d, 4), "kaline": "层①"})

    A_diffs, A_detail = [], []
    for arm in ARMS:
        for tid in tids:
            if (tid, 1, arm) in reads and (tid, 2, arm) in reads:
                d = reads[(tid, 1, arm)][MAIN_METRIC] - reads[(tid, 2, arm)][MAIN_METRIC]
                A_diffs.append(d)
                A_detail.append({"arm": arm, "tid": tid, "rep_pair": (1, 2),
                                 "diff": round(d, 4), "kaline": "层②"})

    B_diffs, B_detail = [], []
    for arm in ["nosel_b3"]:
        for tid in tids:
            if (tid, 1, arm) in reads and (tid, 2, arm) in reads:
                d = reads[(tid, 1, arm)][MAIN_METRIC] - reads[(tid, 2, arm)][MAIN_METRIC]
                B_diffs.append(d)
                B_detail.append({"arm": arm, "tid": tid, "rep_pair": (1, 2),
                                 "diff": round(d, 4), "kaline": "层②"})

    calib = {
        "A_all_arms": {"desc": "★ 当前实现实际用的：新批全部 6 臂 × 同题 rep1−rep2",
                        "short": "新批全部 6 臂 × rep1−rep2",
                        "detail": A_detail},
        "B_prereg_new": {"desc": "★ 预注册主项：新批 nosel_b3 × 同题 rep1−rep2",
                         "short": "新批 `nosel_b3` × rep1−rep2",
                         "detail": B_detail},
        "B_prereg_full": {"desc": "★ 预注册完整：B_prereg_new ＋ 旧批 nosel_b5 9 个",
                          "short": "上者 ＋ 旧批 `nosel_b5` 9 个",
                          "detail": B_detail + old_detail},
        "C_old_only": {"desc": "★ 诊断：旧批 nosel_b5 单独 9 个（层①口径）",
                       "short": "旧批 `nosel_b5` 9 个（层①）",
                       "detail": old_detail},
    }
    diff_sets = {"A_all_arms": A_diffs, "B_prereg_new": B_diffs,
                 "B_prereg_full": B_diffs + old_diffs, "C_old_only": old_diffs}

    print("\n== 1. 各口径 H0 统计量 ==")
    h0: Dict[str, Any] = {}
    for name, ds in diff_sets.items():
        st = h0_stats(ds, a.boot, a.seed)
        st["desc"] = calib[name]["desc"]
        st["short"] = calib[name]["short"]
        st["detail"] = calib[name]["detail"]
        h0[name] = st
        print("   %-16s n=%2d ｜ q95(nr)=%.4f q95(lin)=%.4f CI[%.4f,%.4f] ｜ σ=%.4f CI[%.4f,%.4f] ｜ X0=%.4f ｜ θ0=%.3fσ"
              % (name, st["n_pairs"], st["q95_nearest_rank"], st["q95_linear"],
                 st["q95_bootstrap_ci"][0], st["q95_bootstrap_ci"][1],
                 st["sigma_rep"], st["sigma_bootstrap_ci"][0], st["sigma_bootstrap_ci"][1],
                 st["X0_q95_over_sqrt2"], st["theta0_standardized"]))

    # ── 判决重算（每套口径各自用自己的 σ 与 θ₀）──
    print("\n== 2. 判决重算（★ 每套口径各自用自己的 σ / θ₀ ★）==")
    verdicts: Dict[str, Any] = {}
    for cname, (A, B) in CONTRASTS.items():
        cells = [(tid, rep) for tid in tids for rep in reps
                 if (tid, rep, A) in reads and (tid, rep, B) in reads]
        rows_base = []
        for tid, rep in cells:
            ra, rb = reads[(tid, rep, A)], reads[(tid, rep, B)]
            rows_base.append({"tid": tid, "rep": rep,
                              "vendi_diff": round(ra[MAIN_METRIC] - rb[MAIN_METRIC], 4),
                              "modes_diff": ra["modes"] - rb["modes"],
                              "structured_dedup_diff": ra["structured_dedup"] - rb["structured_dedup"]})
        by_tid = defaultdict(list)
        for r in rows_base:
            by_tid[r["tid"]].append(r["vendi_diff"])
        dir_votes = []
        for tid, ds in sorted(by_tid.items()):
            m = sum(ds) / len(ds)
            dir_votes.append((tid, m, 1 if m > 0 else (-1 if m < 0 else 0)))
        pos = sum(1 for _t, _m, s in dir_votes if s > 0)
        neg = sum(1 for _t, _m, s in dir_votes if s < 0)
        tri_dirs = {m: (sum(1 for r in rows_base if r[m + "_diff"] > 0),
                        sum(1 for r in rows_base if r[m + "_diff"] < 0)) for m in TRI_SCALE}
        dead, info, n_info, tri_consistent, tri_verdict = consistency_from_dirs(tri_dirs)

        per_calib = {}
        for hname, st in h0.items():
            sigma = st["sigma_rep"]
            theta0 = st["theta0_standardized"]
            if not sigma or theta0 is None:
                per_calib[hname] = {"error": "★ 该口径 σ 或 θ₀ 不可用"}
                continue
            std_list = [round(r["vendi_diff"] / sigma, 3) for r in rows_base]
            n_over = sum(1 for x in std_list if abs(x) >= theta0)
            n_over_mde = sum(1 for r in rows_base if abs(r["vendi_diff"]) >= 0.448)
            # 判决格
            cond_mde = n_over_mde > 0
            cond_theta = n_over > 0
            cond_dir = (pos >= 2 or neg >= 2) and n_tid_ok(dir_votes)
            cond_tri = tri_consistent is True
            if tri_consistent is None:
                verdict = "不可判定（★ 有信息的尺子不足 2 把 ★）"
            elif cond_theta and cond_dir and cond_tri:
                verdict = "成立（★ 但须同时报 0.448 门槛 ★）" if cond_mde else "未观察到支持（★ 达 θ₀ 未达 0.448 ★）"
            elif cond_tri and cond_dir:
                verdict = "未观察到支持"
            else:
                verdict = "不可分辨"
            per_calib[hname] = {
                "sigma_rep": sigma, "theta0": theta0,
                "std_list": std_list,
                "n_cells_over_theta0": n_over,
                "n_cells_over_mde_0.448": n_over_mde,
                "n_tid": len(dir_votes), "pos": pos, "neg": neg,
                "tri_consistent": tri_consistent, "tri_verdict": tri_verdict,
                "n_rulers_informative": n_info, "dead_rulers": list(dead.keys()),
                "verdict": verdict,
            }
            print("   %-12s %-16s ｜ σ=%.4f θ0=%.3fσ ｜ 超 θ0 格 %d/%d ｜ 超 0.448 格 %d ｜ 题级 %d正%d负 ｜ 三尺一致=%s ⇒ %s"
                  % (cname, hname, sigma, theta0, n_over, len(rows_base), n_over_mde,
                     pos, neg, tri_verdict, verdict))
        verdicts[cname] = {"contrast": [A, B], "n_cells": len(rows_base),
                            "dir_votes": dir_votes, "tri_dirs": tri_dirs,
                            "per_calibration": per_calib}

    # ── 判决是否随口径改变 ──
    print("\n== 3. ★ 判决是否随口径改变（★ 本脚本要回答的核心问题 ★）==")
    changed = []
    for cname, v in verdicts.items():
        vs = {h: p.get("verdict") for h, p in v["per_calibration"].items()}
        uniq = sorted(set(x for x in vs.values() if x))
        same = len(uniq) == 1
        print("   %-12s ⇒ %s ｜ %s" % (cname, "★ 判决不随口径改变 ★" if same else "★★ 判决随口径改变 ★★", vs))
        if not same:
            changed.append({"contrast": cname, "verdicts_by_calibration": vs})
    # ★ ★ 断言（★ 承诺必须是断言，★ 不能只写在文档里 ★）★★
    #   报告里承诺了「批跑满后切回预注册口径 + 加一道『两口径判决必须一致』的断言」
    #   ⇒ ★ 这道断言现在就落在这里：★ A 口径（当前实现）与 B_prereg_full（预注册）
    #   ⇒ ★ 在【判决格】上必须一致；★ 不一致 ⇒ 响亮失败（★ 不许输出"看起来对" ★）★★
    #   ★ 前置条件：★ 预注册口径必须【原料充分】（★ n<6 不可标定 ★）⇒ ★ 不满足时跳过并说明。
    if changed:
        print("\n   ✘✘✘ 两口径判决不一致 ⇒ ★ 口径偏离【已改变判决】⇒ ★ 必须按【事后改判据】处理 ★")
        print("   %s" % json.dumps(changed, ensure_ascii=False))
        return 5
    nB_full = h0["B_prereg_full"]["n_pairs"]
    if nB_full < 6:
        print("\n   ★ 断言【已落】：★ 当前 A 与 B_prereg_full 的判决格一致（★ 通过 ★）")
        print("   ★ ★ 但预注册口径原料 n=%d < 6 ⇒ ★ 该断言【暂不生效】（★ 原料不足时 B 口径本身不可标定 ★）⇒ ★ 批跑满后自动生效 ★" % nB_full)
    else:
        print("\n   ✔ 断言【通过】：★ 当前实现口径（A）与预注册口径（B_prereg_full）的判决格一致 ⇒ ★ "
              "★ 口径偏离在本批【未改变判决】★")
    # 方向性风险检查：噪声地板变小 ⇒ 效应看起来更大
    print("\n== 4. ★ 方向性风险检查（★ 「地板变小 ⇒ 判决偏向可分辨」是危险方向 ★）==")
    risk = {}
    thA = h0["A_all_arms"]["theta0_standardized"]
    thB = h0["B_prereg_full"]["theta0_standardized"]
    sigA = h0["A_all_arms"]["sigma_rep"]
    sigB = h0["B_prereg_full"]["sigma_rep"]
    xA = h0["A_all_arms"]["X0_q95_over_sqrt2"]
    xB = h0["B_prereg_full"]["X0_q95_over_sqrt2"]
    risk.update({
        "theta0_current_A": thA, "theta0_prereg_B": thB,
        "theta0_ratio_B_over_A": round(thB / thA, 4) if thA else None,
        "sigma_current_A": sigA, "sigma_prereg_B": sigB,
        "sigma_ratio_B_over_A": round(sigB / sigA, 4) if sigA else None,
        "X0_current_A": xA, "X0_prereg_B": xB,
        "X0_ratio_B_over_A": round(xB / xA, 4) if xA else None,
        "note": "★ 门槛是【标准化效应量】⇒ θ₀ 变大 ⇒ 更难超门槛 ⇒ 判决偏向【不可分辨】；★ θ₀ 变小 ⇒ 更易超门槛 ⇒ 偏向【可分辨】★",
    })
    print("   θ0: A=%.3fσ → B(预注册)=%.3fσ ｜ 比值 %.4f ⇒ ★ 预注册口径的门槛 %s ★"
          % (thA, thB, thB / thA,
             "【更严】⇒ 判决偏向【不可分辨】（★ 保守方向 ★）" if thB > thA else "【更松】⇒ 判决偏向【可分辨】（★★ 危险方向 ★★）"))
    print("   σ : A=%.4f → B=%.4f ｜ 比值 %.4f" % (sigA, sigB, sigB / sigA))
    print("   X0: A=%.4f → B=%.4f ｜ 比值 %.4f" % (xA, xB, xB / xA))

    out = {"n_units_actual": n_units, "n_groups_full": len(full),
           "tids": tids, "reps": reps,
           "old_recompute_gate": gate,
           "h0": h0, "verdicts": verdicts,
           "verdict_changed_by_calibration": changed,
           "direction_risk": risk,
           "status": "★ 已跑批·部分 n=%d ｜ ★ 不得当作整批结论 ★" % n_units,
           "seed": a.seed, "n_boot": a.boot}
    dest = a.json_out or os.path.join(a.out, "h0_theta0_multicalib.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("\n✓ 落盘 %s" % dest)
    return 0


def n_tid_ok(dir_votes) -> bool:
    """★ 题级方向是否【可判定】（★ 题数 ≥3 时才谈「≥2/3 同向」★）"""
    return len(dir_votes) >= 3


if __name__ == "__main__":
    raise SystemExit(main())
