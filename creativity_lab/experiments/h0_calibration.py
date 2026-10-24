#!/usr/bin/env python3
"""★ **H0 标定**（★ 零分布下「3 题里 ≥2 题同向」的发生率）

> 落点：`creativity_lab/experiments/h0_calibration.py`
> 数据：★ **两批合并** —— 新批 `runs/topo-arm-v2-2026-10-24`（6 题 × 2 rep = 12 个同题配对）
> 　　　＋ 旧批 `runs/tot-arm-2026-10-24` 的 `nosel_b5`（3 题 × 3 rep = **9 个**同题配对）⇒ **共 21 个**
> 输出：`runs/topo-arm-v2-2026-10-24/h0_calibration.json`
>
> ## ★★ 为什么旧批的 9 个配对可以用（★ 负责人 2026-10-24 裁决）
> ★ **`nosel_b5` 那 9 个配对差虽然口径是层①（5 支并行），但【同题 rep 之间的差异】永远是纯噪声**
> ⇒ ⇒ ★ **零分布只要求「同题重复」，不要求口径同** ⇒ ⇒ **用它做 H0 标定是合法的**
> ⇒ ⇒ ★ **★ 预注册里已写明这条**
>
> ## ★★★ 报法（★ 负责人要求：不要报一个精确的率）
> ★ **报「点估计 + 95% 区间」** ⇒ ⇒ 结论写法：**「该判据在零分布下的发生率与 50% 相差 X（区间 …），是否可区分」**
> ⇒ ⇒ ★ **别把它当成一个精确的概率去用**
"""
import itertools
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "runs", "topo-arm-v2-2026-10-24", "h0_calibration.json")
NEW = os.path.join(ROOT, "runs", "topo-arm-v2-2026-10-24", "manifest.json")
OLD = os.path.join(ROOT, "runs", "tot-arm-2026-10-24", "manifest.json")


def paired_diffs(path, arm, key="read_post", field="vendi"):
    """★ 取同臂同题不同 rep 的差（★ rep 差异 = 纯噪声 ⇒ 天然零分布）。"""
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
            by_tid.setdefault(g["tid"], []).append((g["rep"], r[field]))
    out = []
    for tid, lst in by_tid.items():
        lst.sort()
        for (r1, v1), (r2, v2) in itertools.combinations(lst, 2):
            out.append(dict(tid=tid, rep_pair=(r1, r2), diff=v1 - v2))
    return out


def wilson(k, n, z=1.96):
    """★ Wilson 区间（★ 小样本比正态区间稳）。"""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main():
    new_d = paired_diffs(NEW, "nosel_b3")
    old_d = paired_diffs(OLD, "nosel_b5", key="read", field="vendi")
    all_d = new_d + old_d
    print("== ★ H0 标定原料（同题 rep 配对差 = 纯噪声）==")
    print("   新批 nosel_b3（层②口径）：%d 个" % len(new_d))
    print("   旧批 nosel_b5（层①口径，★ 但同题 rep 差永远是纯噪声 ⇒ 合法）：%d 个" % len(old_d))
    print("   合计 %d 个同题配对差" % len(all_d))
    if len(all_d) < 6:
        print("★ 原料不足（%d）⇒ 无法标定 ⇒ 等新批跑完再跑本脚本" % len(all_d))
        return 1
    # ★ 蒙特卡洛：从实测配对差里抽 3 个（= 3 题）算「≥2 题同向」的发生率
    rng = random.Random(20261025)
    K = 5000
    hits = 0
    for _ in range(K):
        samp = [all_d[rng.randrange(len(all_d))]["diff"] for _ in range(3)]
        same = sum(1 for i in range(3) for j in range(i + 1, 3)
                   if (samp[i] > 0) == (samp[j] > 0))
        if same >= 1:            # ★ 3 题里 ≥2 题同向 ⇒ 至少 1 对同向
            hits += 1
    rate = hits / K
    lo, hi = wilson(hits, K)
    print()
    print("== ★ 零分布下「3 题里 ≥2 题同向」的发生率 ==")
    print("   点估计 %.4f ｜ Wilson 95%% 区间 [%.4f, %.4f] ｜ K=%d" % (rate, lo, hi, K))
    print("   ⇒ 与 50%% 相差 %+.4f" % (rate - 0.5))
    if lo > 0.5 or hi < 0.5:
        print("   ⇒ ★★ 区间【不含 50%%】⇒ ⇒ ★ 「≥2/3 题同向」在零分布下【确实携带信息】")
    else:
        print("   ⇒ ★★★ 区间【含 50%%】⇒ ⇒ ★ 「≥2/3 题同向」在零分布下【几乎不携带信息】")
        print("   ⇒ ⇒ ★ ⇒ 主判据重量必须压在【标准化效应量】上（★ 这正是预注册 §5.0b2-i ② 的设计理由）")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"n_new": len(new_d), "n_old": len(old_d), "n_total": len(all_d),
               "K": K, "rate": rate, "ci95": [lo, hi], "delta_from_50": rate - 0.5,
               "diffs": all_d,
               "note": "★ 旧批 nosel_b5 的配对差口径是层①，但同题 rep 差永远是纯噪声 ⇒ 零分布只要求同题重复 ⇒ 合法"},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print("\n✔ 落盘：%s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
