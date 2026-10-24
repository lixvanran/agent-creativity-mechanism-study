#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 形态受控性表（★ 零额外 API · 零额外调用 · 全部从【已落盘单元内联的 calls】算 ★）

> 落点：`creativity_lab/experiments/morphology_control.py`
> 用法：
>   python3 -B creativity_lab/experiments/morphology_control.py \
>       --run-dir runs/topo-arm-v2-2026-10-24 --unit-list runs/.../UNITS-n149.txt \
>       --json-out runs/topo-arm-v2-2026-10-24/morphology_control.json
>
> ★ **为什么这个脚本以前不在仓里（★ 一条真缺口 ★）** ★
★ 报告 §6.12.8 的形态表一直有读数，★ 但仓里【没有生成它的脚本】⇒ ★
★ ⇒ ★ **那份读数不可复算**（★ 与「数字必须脚本回填」同族：★ 数字有出处，★ 但没有可执行的出处 ★）★
★ ⇒ ★ 本脚本把它补回仓里，★ 并让它与其它分析脚本读【同一份冻结单元清单】⇒ ★ n 结构性一致 ★
>
> ★ **口径定义（★ 逐条写死，★ 免得复算时各人一套 ★）** ★
| 量 | 定义 |
|---|---|
| ★ 截断率 | ★ 该臂内 `finish_reason == "length"` 的调用数 ÷ 该臂调用数 ★ |
| ★ 无内容率 | ★ 该臂内 `has_content == false` 的调用数 ÷ 该臂调用数 ★ |
| ★ think 未闭合率 | ★ 该臂内 `purpose` 含 think 且 `finish_reason != "stop"` 的调用数 ÷ 该臂调用数 ★ |
| ★ 长度中位 | ★ 该臂内 `content_len` 的中位数 ★ |
| ★ 长度极差 | ★ 该臂内 `content_len` 的 min–max（★ 显示为区间 ★）★ |
| ★ 臂间极差 | ★ 各臂该指标的 max−min ★ |
>
> ★ **闸门**（★ 阈值【不可跨批套用】⇒ ★ 每批自己测 ★）：
> ★ 截断率/无内容率/未闭合率的臂间极差须 = 0；★ 长度中位极差须 ≤ 20 字
> ★ ⇒ ★ 但**长度极差这一门有适用条件**：★ 若【长度是被测量或它的中介】⇒ ★ 该门不适用 ★
> ★   （★ 理由：★ 否则会把【效应本身】当成【形态污染】测出来 ★）★ ⇒ ★ 本脚本照实报数，★ 适用性由读报告的人判 ★
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys

PAT = re.compile(r"(\S+)_r(\d+)_(\S+)_u(\d+)$")


def die(msg):
    print("✘ %s" % msg)
    sys.exit(1)


def arm_of(base):
    """★ `S5_r1_nosel_b3_u1` ⇒ 臂 `nosel_b3`（★ run 索引不能进臂名 ★）★"""
    parts = base.split("_")
    arm = "_".join(parts[2:])
    return re.sub(r"_u[0-9]+$", "", arm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--unit-list", default=None)
    ap.add_argument("--len-range-gate", type=float, default=20.0)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    unit_dir = os.path.join(a.run_dir, "units")
    if not os.path.isdir(unit_dir):
        die("units 目录不存在：%s" % unit_dir)
    allowed = None
    if a.unit_list:
        if not os.path.isfile(a.unit_list):
            die("unit-list 不存在：%s" % a.unit_list)
        allowed = set(x.strip() for x in open(a.unit_list, encoding="utf-8") if x.strip())

    by_arm = {}
    n_units = 0
    for fn in sorted(os.listdir(unit_dir)):
        if not fn.endswith(".json"):
            continue
        base = fn[:-5]
        if allowed is not None and base not in allowed:
            continue
        if not PAT.match(base):
            continue
        n_units += 1
        d = json.load(open(os.path.join(unit_dir, fn), encoding="utf-8"))
        arm = arm_of(base)
        rec = by_arm.setdefault(arm, {"calls": 0, "trunc": 0, "nocontent": 0,
                                      "unclosed": 0, "lens": [], "think_calls": 0})
        for c in (d.get("calls") or []):
            rec["calls"] += 1
            fr = c.get("finish_reason")
            rec["trunc"] += 1 if fr == "length" else 0
            rec["nocontent"] += 1 if not c.get("has_content") else 0
            purpose = (c.get("purpose") or "")
            if "think" in purpose.lower():
                rec["think_calls"] += 1
                rec["unclosed"] += 1 if fr != "stop" else 0
            cl = c.get("content_len")
            if isinstance(cl, int):
                rec["lens"].append(cl)

    if not by_arm:
        die("没有可用单元")

    rows = []
    stats = {}
    for arm in sorted(by_arm):
        r = by_arm[arm]
        n = r["calls"] or 1
        trunc = r["trunc"] / n
        noc = r["nocontent"] / n
        uncl = (r["unclosed"] / r["think_calls"]) if r["think_calls"] else 0.0
        med = statistics.median(r["lens"]) if r["lens"] else 0
        lo, hi = (min(r["lens"]), max(r["lens"])) if r["lens"] else (0, 0)
        stats[arm] = {"trunc": trunc, "nocontent": noc, "unclosed": uncl, "len_med": med}
        rows.append((arm, r["calls"], trunc, med, lo, hi, noc, uncl))

    def rng(k):
        vals = [s[k] for s in stats.values()]
        return max(vals) - min(vals)

    trunc_range = rng("trunc")
    noc_range = rng("nocontent")
    uncl_range = rng("unclosed")
    len_range = rng("len_med")

    tbl = ["| 臂 | 调用数 | 截断率(length) | 长度中位 | 长度极差 | 无内容率 | think 未闭合率 |",
           "|---|--:|--:|--:|:--:|--:|--:|"]
    for arm, calls, trunc, med, lo, hi, noc, uncl in rows:
        tbl.append("| `%s` | %d | %.3f | %d | %d–%d | %.3f | %.3f |"
                   % (arm, calls, trunc, med, lo, hi, noc, uncl))
    tbl.append("| ★ **臂间极差** | — | ★ **%.3f** | ★ **%d** | — | ★ **%.3f** | ★ **%.3f** |"
               % (trunc_range, len_range, noc_range, uncl_range))
    table = "\n".join(tbl)

    n_calls = sum(r["calls"] for r in by_arm.values())
    out = {"n_units": n_units, "n_calls": n_calls,
           "trunc_range": round(trunc_range, 4),
           "nocontent_range": round(noc_range, 4),
           "unclosed_range": round(uncl_range, 4),
           "len_med_range": round(len_range, 1),
           "pass_trunc": trunc_range == 0,
           "pass_nocontent": noc_range == 0,
           "pass_unclosed": uncl_range == 0,
           "pass_len": len_range <= a.len_range_gate,
           "len_range_gate": a.len_range_gate,
           "len_gate_applicability_note": "★ 长度若是【被测量或中介】⇒ ★ 本门不适用 ⇒ ★ 不得把长度差异读成形态污染 ★",
           "per_arm": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv)
                           for kk, vv in v.items()} for k, v in stats.items()},
           "unit_list": a.unit_list,
           "table": table}
    print(table)
    print()
    print("== 闸门 ==")
    print("   截断率臂间极差 %.3f ⇒ %s" % (trunc_range, "✔" if out["pass_trunc"] else "✘"))
    print("   无内容率臂间极差 %.3f ⇒ %s" % (noc_range, "✔" if out["pass_nocontent"] else "✘"))
    print("   think 未闭合率臂间极差 %.3f ⇒ %s" % (uncl_range, "✔" if out["pass_unclosed"] else "✘"))
    print("   长度中位极差 %.1f 字（门槛 ≤ %.0f）⇒ %s（★ 适用性见 note ★）"
          % (len_range, a.len_range_gate, "✔" if out["pass_len"] else "✘ 不适用"))
    print("   ★ 单元 %d ｜ 调用 %d" % (n_units, n_calls))
    if a.json_out:
        tmp = a.json_out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, a.json_out)
        print("✔ 落盘 %s" % a.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
