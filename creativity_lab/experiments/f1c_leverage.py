#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ F-1c 落我方：★ 位置基线归一化 + 【单组降级重算】★

★ ★★ 起因：★ 第 1 层论证线 2026-10-26 的来件（★ §二 ★）★★
★ 他们指出：★ 在【K 固定】的批里做 leave-one-out，★ **最后一个单元天然杠杆最大**
★ ⇒ ⇒ ★ 不归一化就会把【K 边界位置效应】误报成【单元内容退化】★★
★ ⇒ ★ 他们要求我方对那个被剔单元（★ `S5_r1_nosel_b3_u1`，★ 198 字 ★）★ 做同一个检查。

★ ★★ ★ 但我方的结构与他们的不同，★ 而且这个不同【改变结论】★★
★ | | 他们（第 1 层） | ★ 我方（拓扑臂 v2）★★ |
★ |---|---|---|
★ | 指标 | PR 参与秩 | ★ **Vendi（谱熵的指数）** ★ |
★ | 剔一个后 | PR 的 Σλ = (K-1)/K ≠ 1 ⇒ **需要「固定参照」** | ★ ★ **Vendi 每次都归一化到 Σλ=1 ⇒ 「固定分母」自动成立** ★★ |
★ | 「位置」 | PR 的第 k 个向量（★ **有序** ★） | ★ 组内 run 索引 u0..u4（★ **同分布独立抽** ★）★ |

★ ★★ **★★ 我方还查出一条【更要紧的实现事实】★★**
★ `partial_verdict.py` 的 `full` 只收 `len(v) >= runs_per_arm`（=5）的组
★ ⇒ ★ **剔掉一个文件 ⇒ 该组只剩 4 份 ⇒ 整组被排除 ⇒ ⇒ 那个格是【整组退出】**
★ ⇒ ★ **不是「该单元被剔后重算」★ ⇒ ★ ⇒ 「+2.69σ 消失」这句话【不精确】★★
★ ★★ **⇒ 本脚本做两件正事 ★★**
★ ① **位置基线**：★ 对每个满组，★ 逐个剔 run 索引 i（★ 剩 4 份按普通口径重算 ★）
★    ⇒ ★ 统计各 i 位置的平均杠杆 ⇒ ★ 那个污染单元的杠杆 vs 同位置基线
★ ② **单组降级重算**：★ ★ 剔一个单元后，★ 该组【不退出】，★ 而是用剩下的份数算读数（★ 标 n=4 ★）
★    ⇒ ★ 重算三个对比 ⇒ ★ **回答「+2.69σ 到底还在不在」★★**

★ 用法：
    python3 -B creativity_lab/experiments/f1c_leverage.py \
        --out /workspace/lab/runs/topo-arm-v2-2026-10-25 \
        --runs-per-arm 5 --seed 20261025 \
        --json-out runs/topo-arm-v2-2026-10-25/f1c_leverage.json
"""

import argparse
import glob
import json
import math
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from creativity_lab.metrics_ext import vendi_score  # noqa: E402

ARMS = ["nosel_b3", "nosel_b3_synth", "topo_gs_homo", "topo_ngt_homo",
        "topo_sg_homo", "topo_ngt_hetero"]
CONTRASTS = {
    "H-TOPO-4a": ("topo_ngt_homo", "nosel_b3_synth"),
    "H-TOPO-4c": ("nosel_b3_synth", "nosel_b3"),
    "H-TOPO-4d": ("topo_ngt_homo", "topo_gs_homo"),
}
THETA0 = 1.339      # ★ 与 partial_verdict 同批噪声地板（★ 批末会重算 ★）


def die(msg):
    print("✘ %s" % msg)
    sys.exit(1)


def load_groups(unit_dir):
    """★ (tid, rep, arm) → [(run_idx, post_text), ...] ★"""
    g = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(unit_dir, "*.json"))):
        b = os.path.basename(f)[:-5]
        m = re.match(r"(\S+)_r(\d+)_(\S+)_u(\d+)$", b)
        if not m:
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        post = (d.get("post") or "").strip()
        if post:
            g[(m.group(1), int(m.group(2)), m.group(3))].append((int(m.group(4)), post))
    return {k: sorted(v) for k, v in g.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs-per-arm", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--min-content-len", type=int, default=200)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    unit_dir = os.path.join(a.out, "units")
    groups = load_groups(unit_dir)
    full = {k: v for k, v in groups.items() if len(v) >= a.runs_per_arm}
    if not full:
        die("没有满组（>= %d 份）" % a.runs_per_arm)
    print("== 满组 %d 个（组内 %d 份）==" % (len(full), a.runs_per_arm))

    # ── embed（★ 一次性，★ 真实 API，★ 成本极低：★ 135 段 / 32 ≈ 5 次调用 ★）──
    from creativity_lab.client import LLM
    llm = LLM()
    all_texts = []
    for v in full.values():
        for _i, t in v:
            all_texts.append(t)
    uniq = list(dict.fromkeys(all_texts))
    print("★ embed %d 段（去重后 %d）…" % (len(all_texts), len(uniq)))
    vecs = llm.embed(uniq)
    vmap = dict(zip(uniq, vecs))

    def v_of(items):
        return vendi_score([vmap[t] for _i, t in items])

    # ★ ★★ 断言：★ 所有重算的【可比单元数】必须与基线一致（★ 无「整组退出」副作用）★★
    # ★ 来源：★ 第 1 层论证线 2026-10-26（★ P-1/P-2 ★）：★ 「剔除类结论必须用
    # ★ 与主分析同口径的独立路径重算，★ 且必须写清剔除后该组是【退出】还是【降级】」
    # ★ ★ ★ 我方正好踩在「退出」那一侧：★ partial_verdict.py 的 full 只收满
    # ★ 5 份的组 ⇒ ★ 剔一个文件 ⇒ 该组只剩 4 份 ⇒ 整组被排除 ⇒ ★ ⇒ 那不是
    # ★ 「单元杠杆」，★ 是「分母规则副作用」★ ★ ⇒ ★ ⇒ 本断言把「没踩到」从
    # ★ 【运气】变成【被检查过】★★
    def n_comparable(subset):
        """★ 该子集下、三个对比各自的【可比单元数】（★ (题,rep) 齐全的臂对数 ★）"""
        out = {}
        for cname, (A, B) in CONTRASTS.items():
            tids = sorted({kk[0] for kk in subset if kk[2] in (A, B)})
            n = 0
            for tid in tids:
                reps = sorted({kk[1] for kk in subset if kk[0] == tid and kk[2] in (A, B)})
                for rep in reps:
                    if any(kk[0] == tid and kk[1] == rep and kk[2] == A for kk in subset) and \
                       any(kk[0] == tid and kk[1] == rep and kk[2] == B for kk in subset):
                        n += 1
            out[cname] = n
        return out

    base_cmp = n_comparable(full)
    print("★ 基线可比单元数：%s" % base_cmp)

    # ── ① 位置基线 ──
    print()
    print("== ① 位置基线（★ 逐个剔 run 索引 i，★ 剩 4 份按普通口径重算 ★）==")
    lev = defaultdict(list)          # run 索引 → 各组的 |Δ|
    group_base = {}
    for k, v in full.items():
        base = v_of(v)
        group_base[k] = base
        for i in range(len(v)):
            sub = [x for j, x in enumerate(v) if j != i]
            if len(sub) < 2:
                continue
            lev[v[i][0]].append(abs(v_of(sub) - base))
    pos_mean = {}
    for i in sorted(lev):
        xs = lev[i]
        pos_mean[i] = sum(xs) / len(xs)
        print("   位置 u%d：%d 组 ｜ 平均 |ΔVendi| = %.5f" % (i, len(xs), pos_mean[i]))
    all_levs = [x for xs in lev.values() for x in xs]
    grand = sum(all_levs) / len(all_levs)
    print("   ★ 基线均值（全部位置）= %.5f" % grand)

    # ── 污染单元的杠杆 vs 同位置基线 ──
    print()
    print("== ② 污染单元的杠杆 vs 同位置基线（★ 他们的 ③：≥2× 才算内容依赖 ★）==")
    contaminated = []
    for k, v in full.items():
        for i, (run_idx, t) in enumerate(v):
            if len(t) < a.min_content_len:
                contaminated.append((k, i, run_idx, len(t)))
    verdict_ratio = None
    for (k, i, run_idx, ln) in contaminated:
        v = full[k]
        base = group_base[k]
        sub = [x for j, x in enumerate(v) if j != i]
        d = abs(v_of(sub) - base)
        bm = pos_mean.get(run_idx, grand)
        ratio = (d / bm) if bm else float("inf")
        verdict_ratio = ratio
        print("   单元 %s_r%d_%s_u%d（长度 %d）" % (k[0], k[1], k[2], run_idx, ln))
        print("   ★ 该单元杠杆 |ΔVendi| = %.5f ｜ 同位置(u%d)基线 = %.5f ｜ 比值 = %.2f×"
              % (d, run_idx, bm, ratio))
        print("   ★ ⇒ %s" % ("★ **内容依赖**（★ ≥2× ⇒ 触发脆弱性标注 ★）"
                              if ratio >= 2.0 else
                              "★ **不属内容依赖**（★ <2× ⇒ 更像位置/普通噪声 ⇒ 不触发降级 ★）"))
        print("   ★ （★ 同位置其它位置的杠杆：%s ★）"
              % ("、".join("u%d=%.5f" % (i2, pos_mean[i2]) for i2 in sorted(pos_mean))))

    # ★ 断言：对【降级后】的子集，★ 可比单元数必须与基线一致 ★
    for (k, i, run_idx, ln) in contaminated:
        sub = {kk: [x for j, x in enumerate(vv) if not (kk == k and j == i)]
               for kk, vv in full.items()}
        sub = {kk: vv for kk, vv in sub.items() if len(vv) >= 2}
        cmp2 = n_comparable(sub)
        same = (cmp2 == base_cmp)
        print("   ★ 断言（★ 可比单元数不变 ★）：%s ｜ 降级后 %s ｜ 基线 %s ⇒ %s"
              % (k, cmp2, base_cmp, "✔ 通过（★ 无『整组退出』副作用 ★）" if same
                 else "✘ 不一致（★ 有整组退出 ⇒ 读数不可用于杠杆判断 ★）"))
        if not same:
            print("   ★ ★ 不一致 ⇒ ★ 本脚本的杠杆结论【不可用】★ ⇒ ★ 请改用『降级重算』路径 ★")

    # ── ③ 单组降级重算：★ 剔一个单元后该组【不退出】，★ 用剩下份数算读数 ★─
    print()
    print("== ③ 单组降级重算（★ 剔一个后该组用 n=%d 参与对比，★ 而不是整组退出 ★）=="
          % (a.runs_per_arm - 1))
    for (k, i, run_idx, ln) in contaminated:
        for cname, (A, B) in CONTRASTS.items():
            if k[2] not in (A, B):
                continue
            cells = []
            for kk, vv in full.items():
                if kk[0] != k[0] or kk[1] != k[1] or kk[2] not in (A, B):
                    continue
                items = list(vv)
                n_here = len(items)
                if kk == k:
                    items = [x for j, x in enumerate(items) if j != i]
                if len(items) < 2:
                    continue
                cells.append((kk[2], v_of(items), n_here))
            by = defaultdict(list)
            for arm, val, n_here in cells:
                by[arm].append((val, n_here))
            if A not in by or B not in by or len(by[A]) != len(by[B]):
                continue
            diffs = [va - vb for (va, _), (vb, _) in zip(by[A], by[B])]
            mean = sum(diffs) / len(diffs)
            print("   %s ｜ %s r%d ｜ 剔 u%d 后 ｜ 组内 n=%d ｜ 题级 mean %+.4f"
                  % (cname, k[0], k[1], run_idx, a.runs_per_arm - 1, mean))
            print("   ★ 逐格：%s" % (" ｜ ".join("%+.4f" % d for d in diffs)))
            print("   ★ 标准化（÷ 题内 σ，★ σ 取本批 vendi 值）：%+.2fσ" % (mean / 0.2248))
    print()
    print("== 汇总 ==")
    print("   ★ 位置基线（各 run 索引的平均 |ΔVendi|）：%s"
          % ("、".join("u%d=%.5f" % (i, pos_mean[i]) for i in sorted(pos_mean))))
    if verdict_ratio is not None:
        print("   ★ 污染单元杠杆比值 = %.2f× ⇒ %s"
              % (verdict_ratio,
                 "★ 内容依赖 ⇒ 触发脆弱性标注 ★" if verdict_ratio >= 2.0
                 else "★ 不属内容依赖 ⇒ **不触发降级** ★"))

    if a.json_out:
        res = {"position_leverage": {str(k): v for k, v in pos_mean.items()},
               "grand_leverage": grand,
               "contaminated": [{"group": list(k), "idx": i, "run": r, "len": ln}
                                for (k, i, r, ln) in contaminated],
               "content_dependency_ratio": verdict_ratio,
               "n_full_groups": len(full)}
        json.dump(res, open(a.json_out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print("✔ 落盘 %s" % a.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
