#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 独立可复算件：★ 「剔除污染单元」重算 + 【脆弱格】标色 ★

★ ★★ 为什么需要这个件（★ 2026-10-26 主会话要求：★ 「我要能自己跑一遍」★★）
★ 拓扑臂 v2 的部分预判决里，★ 4c（综述效应）那个 +2.69σ 的正面格
★ **由一个 198 字的输出贡献** ⇒ ★ 剔除后该格消失、题级效应 ↓86.6%
★ ⇒ ★ **「不可分辨」是稳的、★ 「有个大效应」是脆的** ⇒ ★ 两者的区别必须【可复算】★★

★ ★★ 本件做三件事（★ 全部零生成调用 ★）★★
| # | 事 | 怎么做的 |
|:-:|---|---|
| ① | ★ **找出污染单元** ★ | ★ 按【最终输出长度 < `min_ok`】判定；★ 阈值可配（★ 默认 200 = 本批 `min_ok` ★）★ |
| ② | ★ **剔除后重算** ★ | ★ 复制 `units/` 目录、★ **只删那些文件**、★ **同一脚本同一参数**再跑一遍 `partial_verdict.py` ★ |
| ③ | ★ **标出【脆弱格】** ★ | ★ **A 有 B 无**的格 ⇒ ★ 该格**由污染单元支撑** ★ ⇒ ★ 输出里单独成列 ★ |

★ ★★ 输出（JSON + stdout 表格）★★
- `contaminated_units`: 污染单元清单（basename + 臂 + 题 + rep + 长度 + 该臂已落盘单元数）
- `fragile_cells`: 脆弱格清单（对比 + 题 + rep + A 里的效应值 + B 里的题级效应）
- `stable_cells`: 稳健格清单
- `verdict_impact`: 题级效应 A→B 的变化（含相对降幅）

★ ★★ 判定口径（★ 写清楚，★ 免得被质疑 ★）★★
★ **脆弱格** = 在【含污染单元】的运行里存在、★ 在【剔除污染单元】的运行里消失的可比单元。
★ **★ 注意：★ 这不是「效应错了」，★ 是「该格的读数依赖一个不合格的输出」★★
★ ⇒ ★ **结论必须分两半写**（★ 主会话已采信 ★）：★ 「不可分辨」不依赖它；★ 「有个大效应」依赖它。★★

用法：
    python3 -B creativity_lab/experiments/recompute_excluding.py \
        --out /workspace/lab/runs/topo-arm-v2-2026-10-25 \
        --runs-per-arm 5 --target-units 360 --seed 20261025 --boot 10000 \
        --json-out runs/topo-arm-v2-2026-10-25/recompute_excluding.json
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PV = os.path.join(HERE, "partial_verdict.py")


def die(msg):
    print("✘ %s" % msg)
    sys.exit(1)


def find_contaminated(unit_dir, max_len):
    out = []
    if not os.path.isdir(unit_dir):
        die("units 目录不存在：%s" % unit_dir)
    for fn in sorted(os.listdir(unit_dir)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(unit_dir, fn)
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            die("读不了单元 %s：%s" % (fn, e))
        post = (d.get("post") or "").strip()
        if len(post) < max_len:
            out.append({"file": fn, "content_len": len(post),
                        "post_source": d.get("post_source", "")})
    return out


def run_pv(out_dir, runs_per_arm, target_units, seed, boot, json_out):
    cmd = [sys.executable, "-B", PV, "--out", out_dir,
           "--runs-per-arm", str(runs_per_arm), "--target-units", str(target_units),
           "--seed", str(seed), "--boot", str(boot), "--json-out", json_out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die("partial_verdict.py 失败（exit %d）：\n%s\n%s" % (r.returncode, r.stdout[-2000:], r.stderr[-2000:]))
    return json.load(open(json_out, encoding="utf-8"))


def cell_key(c):
    return (c["tid"], c["rep"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="★ 批的输出目录（★ 含 units/ ★）")
    ap.add_argument("--runs-per-arm", type=int, default=5)
    ap.add_argument("--target-units", type=int, default=360)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--max-content-len", type=int, default=200,
                    help="★ 污染判定阈值（★ 默认 200 = 本批 min_ok ★）")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    unit_dir = os.path.join(a.out, "units")
    contaminated = find_contaminated(unit_dir, a.max_content_len)
    print("== ① 污染单元（★ 最终输出长度 < %d ★）==" % a.max_content_len)
    if not contaminated:
        print("   （无）★ ⇒ ⇒ ★ 本批没有长度型污染，★ 下面的对比【不需要】做剔除重算 ★")
        res = {"contaminated_units": [], "fragile_cells": [], "stable_cells": [],
               "verdict_impact": {}, "note": "★ 无污染单元 ⇒ 未做剔除重算 ★"}
        if a.json_out:
            json.dump(res, open(a.json_out, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1, sort_keys=True)
            print("✔ 落盘 %s" % a.json_out)
        return 0

    # 臂级 n（★ 用于算臂级污染率 ★）
    import re as _re
    def arm_of(base):
        """★ 文件名形如 `S5_r1_nosel_b3_u1` ⇒ ★ 臂 = `nosel_b3`、run 索引 = `u1`。
        ★ ★ 坑：★ 直接把 parts[2:] 拼起来会把 run 索引算进臂名 ⇒ ★ 臂级 n 会算错。★★"""
        parts = base.split("_")
        arm = "_".join(parts[2:])
        return _re.sub(r"_u[0-9]+$", "", arm)

    arm_counts = {}
    for fn in os.listdir(unit_dir):
        if fn.endswith(".json"):
            arm = arm_of(fn[:-5])
            arm_counts[arm] = arm_counts.get(arm, 0) + 1
    for c in contaminated:
        parts = c["file"][:-5].split("_")
        c["arm"] = arm_of(c["file"][:-5])
        c["tid"] = parts[0] if len(parts) > 0 else "?"
        c["rep"] = parts[1] if len(parts) > 1 else "?"
        c["arm_units"] = arm_counts.get(c["arm"], 0)
        c["arm_pollution_rate"] = round(1.0 / c["arm_units"], 4) if c["arm_units"] else None
        print("   %-28s 臂=%-22s 长度=%d ｜ 该臂已落盘 %d 单元 ⇒ 臂级污染率 %.2f%%"
              % (c["file"], c["arm"], c["content_len"], c["arm_units"],
                 100.0 * c["arm_pollution_rate"]))
    n_all = len([f for f in os.listdir(unit_dir) if f.endswith(".json")])
    print("   ★ 总体污染率：%d / %d = %.2f%%" % (len(contaminated), n_all,
                                        100.0 * len(contaminated) / n_all))

    # ② 剔除后重算
    tmp = tempfile.mkdtemp(prefix="excl_")
    try:
        staged = os.path.join(tmp, "batch")
        shutil.copytree(a.out, staged, ignore=shutil.ignore_patterns("units_excl*"))
        sdir = os.path.join(staged, "units")
        for c in contaminated:
            os.remove(os.path.join(sdir, c["file"]))
        jA = os.path.join(tmp, "A.json")
        jB = os.path.join(tmp, "B.json")
        A = run_pv(a.out, a.runs_per_arm, a.target_units, a.seed, a.boot, jA)
        B = run_pv(staged, a.runs_per_arm, a.target_units, a.seed, a.boot, jB)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ③ 脆弱格
    print()
    print("== ③ 脆弱格（A 有 B 无 ⇒ 该格由污染单元支撑）==")
    fragile, stable, impact = [], [], {}
    for name in sorted(A["verdicts"].keys()):
        ca = A["verdicts"][name]["cells"]
        cb = B["verdicts"].get(name, {}).get("cells", [])
        kb = {cell_key(c): c for c in cb}
        # ★ dir_votes 在 json 里是 [["tid", mean, sign], ...] ⇒ ★ 第一个元素【就是】tid 字符串
        va = {tid: mean for tid, mean, _sgn in A["verdicts"][name]["dir_votes"]}
        vb = {tid: mean for tid, mean, _sgn in B["verdicts"].get(name, {}).get("dir_votes", [])}
        for c in ca:
            k = cell_key(c)
            if k in kb:
                stable.append({"contrast": name, "tid": c["tid"], "rep": c["rep"],
                               "vendi_diff": c["vendi_diff"], "vendi_std": c["vendi_std"]})
            else:
                fragile.append({"contrast": name, "tid": c["tid"], "rep": c["rep"],
                                "vendi_diff": c["vendi_diff"], "vendi_std": c["vendi_std"],
                                "vendi_std_B": None})
                print("   ★ 脆弱格：%s ｜ %s r%d ｜ A: %+.4f (%+.2fσ) ⇒ B 中【消失】"
                      % (name, c["tid"], c["rep"], c["vendi_diff"], c["vendi_std"]))
        for tid in va:
            if tid in vb:
                d = vb[tid] - va[tid]
                rel = (d / va[tid]) if va[tid] else None
                impact.setdefault(name, {})[tid] = {
                    "A": va[tid], "B": vb[tid], "delta": d, "rel_change": rel}
                if rel is not None and abs(rel) > 0.01:
                    print("   ★ 题级影响：%s ｜ %s ｜ A %+.4f ⇒ B %+.4f （%+.1f%%）"
                          % (name, tid, va[tid], vb[tid], 100.0 * rel))

    print()
    print("== 汇总 ==")
    print("   污染单元 %d ｜ 脆弱格 %d ｜ 稳健格 %d" % (len(contaminated), len(fragile), len(stable)))
    print("   ★ ★ 结论必须【分两半写】：★ 「不可分辨」不依赖污染单元；★ 「有个大效应」依赖它。★ ★")

    res = {
        "n_units_total": n_all,
        "max_content_len": a.max_content_len,
        "contaminated_units": contaminated,
        "overall_pollution_rate": round(len(contaminated) / n_all, 4) if n_all else None,
        "fragile_cells": fragile,
        "stable_cells": stable,
        "verdict_impact": impact,
        "A": {"n_units_actual": A["n_units_actual"], "theta0": A["theta0"],
              "h0_n_pairs": A["h0"]["vendi"]["n_pairs"]},
        "B": {"n_units_actual": B["n_units_actual"], "theta0": B["theta0"],
              "h0_n_pairs": B["h0"]["vendi"]["n_pairs"]},
    }
    if a.json_out:
        json.dump(res, open(a.json_out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print("✔ 落盘 %s" % a.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
