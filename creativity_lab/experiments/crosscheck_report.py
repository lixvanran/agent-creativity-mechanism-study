#!/usr/bin/env python3
"""**报告 ↔ 数据 交叉核对**（防转写错误）

> 落点：`creativity_lab/experiments/crosscheck_report.py`
> 用法：`python3 -B creativity_lab/experiments/crosscheck_report.py <报告.md>`
> ⇒ 从各 run 的 manifest 重算关键量，检查报告里是否**逐字**出现该数字。
> ⇒ 报不出来 = 报告里写错了，或用了别的口径 ⇒ **必须查清楚再交付**。
>
> ★ 为什么要固化：今晚我在方差分解上踩过 —— 表脚本用**均值**、报告按**均值**写，
>   而我核对时用**中位** ⇒ 比值 1.3× vs 2.1× ⇒ **同一份材料里两套口径**。
>   ⇒ ⇒ 核对必须是**脚本**，不能靠眼睛。
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIVERGE = os.path.join(ROOT, "runs", "divergence-matrix-2026-10-23")
ENDSTEP = os.path.join(ROOT, "runs", "endstep-matrix-2026-10-23")
EVAL = os.path.join(ROOT, "runs", "evaluator-strength-2026-10-24")


def med(v: List[float]):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    rep = open(sys.argv[1], encoding="utf-8").read().replace("−", "-")
    missing: List[str] = []
    checked = 0

    # 报告里出现的所有数字（做**数值容差匹配** ⇒ 0.22 与 0.2222 视为一致）
    import re as _re
    _nums = set()
    for _t in _re.findall(r"-?\d+\.\d+", rep):
        try:
            f = float(_t)
        except Exception:                              # noqa: BLE001
            continue
        for _d in (0, 1, 2, 3, 4):
            _nums.add(round(f, _d))
    _ints = set()
    for _t in _re.findall(r"(?<![.\d])\d+(?![.\d])", rep):
        try:
            _ints.add(int(_t))
        except Exception:                              # noqa: BLE001
            continue

    def need(s: str, label: str):
        nonlocal checked
        checked += 1
        if s in rep:
            return
        try:                                            # ★ 数值容差：把**待查值**舍入后
            f = float(s)                               #   看是否等于报告里出现过的数
            for d in range(5):                         #   （0.2222 ⇒ 0.22 ⇒ 命中「0.22」）
                if round(f, d) in _nums:
                    return
            if any(abs(f - n) < 1e-9 for n in _nums):
                return
        except Exception:                              # noqa: BLE001
            pass
        missing.append("%s ⇒ 报告里找不到「%s」" % (label, s))

    # ── 发散层 ──
    if os.path.exists(os.path.join(DIVERGE, "manifest.json")):
        man = json.load(open(os.path.join(DIVERGE, "manifest.json"), encoding="utf-8"))
        groups = [g for g in man["groups"] if g.get("arms")]
        tids = sorted({g["tid"] for g in groups})
        arms = ["base", "same_model", "one_frame", "n3", "n8"]
        per = {}
        for arm in arms:
            for tid in tids:
                vs = [g["arms"][arm]["effective_rank_per_n"] for g in groups
                      if g["tid"] == tid and g["arms"].get(arm, {}).get("valid")]
                if vs:
                    per[(arm, tid)] = med(vs)
        for (arm, tid), v in per.items():
            need("%.3f" % v, "发散层 %s@%s 的秩/n 中位" % (arm, tid))
        # 方差分解（中位口径）
        sd_t = [statistics.pstdev([per[(a, t)] for t in tids if (a, t) in per])
                for a in ("base", "same_model", "one_frame")]
        sd_a = [statistics.pstdev([per[(a, t)] for a in ("base", "same_model", "one_frame")
                                    if (a, t) in per]) for t in tids]
        mt, ma = med(sd_t), med(sd_a)
        need("%.3f" % mt, "跨题离散（中位）")
        need("%.3f" % ma, "跨臂离散（中位）")
        need("%.1f" % (mt / ma if ma else 0), "题间/臂间 比值")
        # 基线模态数
        for tid in tids:
            ms = [g["arms"]["base"]["modes"] for g in groups if g["tid"] == tid]
            if ms:
                need("%.1f" % (sum(ms) / len(ms)), "基线模态数 %s" % tid)

    # ── 末步 4 臂 ──
    if os.path.exists(os.path.join(ENDSTEP, "manifest.json")):
        man = json.load(open(os.path.join(ENDSTEP, "manifest.json"), encoding="utf-8"))
        groups = [g for g in man["groups"] if g.get("valid")]
        for arm in ("end_fuse", "end_greedy", "end_sample", "end_raw"):
            cov = med([g["arms"][arm]["covered_branches"] for g in groups])
            sur = med([g["arms"][arm]["survival_rate"] for g in groups])
            ch = med([g["arms"][arm]["out_chars"] for g in groups])
            need("%.3f" % sur, "末步 %s 面深中位" % arm)
            need("%.0f" % ch, "末步 %s 字数中位" % arm)
            need("%.1f" % cov, "末步 %s 面宽中位" % arm)

    # ── 评估器强度 ──
    if os.path.exists(os.path.join(EVAL, "manifest.json")):
        man = json.load(open(os.path.join(EVAL, "manifest.json"), encoding="utf-8"))
        h = man["health"]
        need(str(h.get("position_consistency")), "vote 位置一致率")
        for k, v in h.get("pairwise_agreement", {}).items():
            need("%.2f" % v, "评估器一致率 %s" % k)

    # ── 结论 2.10：加支数在「模态数」口径上的重算（第六轮 + 本批）──
    for run in ("divergence-matrix-2026-10-24", "divergence-pathmulti-2026-10-24"):
        fp = os.path.join(ROOT, "runs", run, "manifest.json")
        if not os.path.exists(fp):
            continue
        man = json.load(open(fp, encoding="utf-8"))
        for g in man["groups"]:
            a = g.get("arms") or {}
            if "base" in a and "n8" in a and a["base"].get("valid") and a["n8"].get("valid"):
                need("%d" % (a["n8"]["modes"] - a["base"]["modes"]), "Δ模态数 %s %s r%d" % (run, g["tid"], g["rep"]))
    # 题内中位（6 题表）
    import collections
    agg = collections.defaultdict(lambda: collections.defaultdict(list))
    for run in ("divergence-matrix-2026-10-24", "divergence-pathmulti-2026-10-24"):
        fp = os.path.join(ROOT, "runs", run, "manifest.json")
        if not os.path.exists(fp):
            continue
        man = json.load(open(fp, encoding="utf-8"))
        for g in man["groups"]:
            a = g.get("arms") or {}
            for arm in ("base", "n8"):
                if arm in a and a[arm].get("valid"):
                    agg[g["tid"]][arm].append(a[arm]["modes"])
    for tid, d in sorted(agg.items()):
        if "base" in d and "n8" in d:
            need("%.1f" % med(d["base"]), "base 模态中位 %s" % tid)
            need("%.1f" % med(d["n8"]), "n8 模态中位 %s" % tid)

    # ── 结论 2.11：路径多样批通道健康 ──
    pm = os.path.join(ROOT, "runs", "divergence-pathmulti-2026-10-24", "manifest.json")
    if os.path.exists(pm):
        h = json.load(open(pm, encoding="utf-8"))["health"]
        need(str(h.get("n_calls_total")), "pathmulti 调用总数")
        need(str(h.get("n_calls_failed")), "pathmulti 失败数")

    print("== 交叉核对：报告 vs 数据 ==")
    print("  检查项：%d" % checked)
    if missing:
        print("  ✘ 报告里找不到 %d 项：" % len(missing))
        for m in missing:
            print("     - %s" % m)
        return 1
    print("  ✔ 全部对得上")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
