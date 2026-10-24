#!/usr/bin/env python3
"""★ **归因回源：同 n 校准里的 1.29–1.57× 到底归因于「结构」还是「生成策略」？**

> 落点：`creativity_lab/experiments/frame_structure_probe.py`
> 原始数据：`runs/tot-arm-adhd-2026-10-24/manifest.json`（`arts`）+ `runs/tot-arm-2026-10-24/manifest.json`
> 触发：负责人审查回执 ③ —— 「差异落在每框架内发散次数（6 vs 1）」这条归因**可能不成立**
> ⇒ ⇒ **本脚本是零 API 调用的纯离线重算**（不跑新批）

## ★★ 问题
同 n 校准后（ToT 4 支 vs ADHD 抽 4 支）读数：Vendi 高 1.29–1.57×、self-BLEU 低 2.4–9.8×。
⇒ ⇒ 两条候选解释：
- **H-结构**：ADHD「每框架内连发 6 个想法」⇒ **同一框架的支彼此更相似** ⇒ ⇒ 归因于**结构**
- **H-策略**：ADHD「一次连发 6 个想法」这个**生成策略** ⇒ **产出的想法彼此更不重复** ⇒ ⇒ 归因于**策略**

⇒ ⇒ ★ **两者的可观测后果相反**，而且**都能用"两两相似度"判**：
- H-结构 ⇒ **同框架的支对更相似** ⇒ ⇒ 随机 4 支里那部分同框架对**会把相似度拉高**
- H-策略 ⇒ **同框架的支也不相似** ⇒ ⇒ 随机 4 支的相似度**不会**因为含同框架对而升高

## ★★ 判别设计（★★ 零标签、不需要框架标签）
> ⚠️ **为什么不需要标签**：ADHD 的 `picked` 在 manifest 里是 `null` ⇒ **每支属哪个框架没被保存**
> ⇒ ⇒ 本脚本**不试图恢复标签**，而是用**"含同框架对的比例"这个统计量**做对照。

设：
- `S_tot4` = ToT 4 支两两相似度均值（★ **每框架 1 支 ⇒ 0% 同框架对**）
- `S_adhd4` = ADHD 随机 4 支两两相似度均值（★ **含 ~46% 同框架对**，见下面的期望值）
- `S_adhd24` = ADHD 全量 24 支两两相似度均值（★ 同框架对占 6×C(6,2)/C(24,2) ≈ 27%）

| 若 | 则 |
|---|---|
| `S_adhd4` ≈ `S_adhd24` **且** `S_adhd4` **≪** `S_tot4` | ★★★ **同框架对没有把相似度拉高 ⇒ H-结构 被否证 ⇒ 归因于 H-策略** |
| `S_adhd4` **>** `S_adhd24`（因同框架对被高估）**且** `S_adhd4` 接近 `S_tot4` | ★ H-结构 成立 |

## ★★ 同框架对的期望比例（★ 负责人的「0.8 支/框架」是什么意思）
- ADHD 结构：**F 框架 × 6 想法**（S4 r1 实测 F=4 ⇒ 24 支；S4 r2 实测 F=5 ⇒ 30 支）
- 随机抽 k 支 ⇒ **每框架期望支数 = k/F**（★ 负责人算的 **0.8 = 4/5** 就是这个量）
- ⇒ ⇒ ⚠️ **但"每框架支数"≠"覆盖框架数"** ⇒ ★ **覆盖框架数 = F×(1 − C(F·6−k, k)/C(F·6, k))**
  （S4 r1, k=4, F=4 ⇒ **2.18 个框架**；⇒ ⇒ **同框架支对占 C(4,2) 的 ~46%**）
- ⇒ ⇒ ★★ **⇒ 所以"每框架内发散次数"这个机制在 4 支里**确实**出现过（46% 的支对同框架）**
  ⇒ ⇒ **⇒ 关键不是"有没有出现"，而是"出现时它把相似度拉高了吗"** ⇒ ⇒ **本脚本直接测这个**

## ★★ 相似度用什么
主口径 **`self_bleu`（Zhu et al. 2018，照抄 `metrics_ext.py`）**；辅口径 **token 集 Jaccard**（零 embedding、零阈值、零聚类）
⇒ ⇒ 两者都是**比率型 ⇒ 不受 n 影响** ⇒ ⇒ 正好用来做同 n 之外的结构对照
"""
import itertools
import json
import os
import random
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.metrics_ext import self_bleu  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADHD = os.path.join(ROOT, "runs", "tot-arm-adhd-2026-10-24", "manifest.json")
TOT = os.path.join(ROOT, "runs", "tot-arm-2026-10-24", "manifest.json")
OUT = os.path.join(ROOT, "runs", "tot-arm-adhd-2026-10-24", "frame_structure_probe.json")


def toks(t):
    return set(w for w in re.findall(r"[A-Za-z一-鿿]+", (t or "").lower()) if w)


def jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def mean_pair(arts, sim):
    vals = [sim(a, b) for a, b in itertools.combinations(arts, 2)]
    return statistics.mean(vals) if vals else float("nan")


def expect_frame_coverage(F, k, ideas=6):
    """★ 随机抽 k 支 ⇒ 覆盖框架数的期望（超几何）。"""
    N = F * ideas
    if k > N:
        return float("nan")
    p_same_frame = 1.0 - (F * ideas - k) / N if False else None
    # 用组合数算"至少有一支来自某框架"的无重叠期望
    # E[覆盖框架数] = F * (1 - C(N-k, k) / C(N, k))  近似（各框架事件独立时的精确无重叠版本）
    from math import comb
    if N - k < k:
        return float(F)
    return F * (1.0 - comb(N - k, k) / comb(N, k))


def main():
    adm = json.load(open(ADHD, encoding="utf-8"))
    tdm = json.load(open(TOT, encoding="utf-8"))
    tot_arts = {}
    for g in tdm["groups"]:
        dd = (g.get("arms") or {}).get("nosel_b5") or {}
        if dd.get("arts"):
            tot_arts[(g["tid"], g["rep"])] = dd["arts"]

    rows = []
    for g in adm["groups"]:
        tid, rep = g["tid"], g["rep"]
        a = g["arms"]["adhd_b5"]
        arts = a["arts"]
        F = len(a["frames"])
        N = len(arts)
        if N < 4:
            continue
        tar = tot_arts.get((tid, rep))
        if not tar:
            continue
        k = len(tar)          # ★ ToT 的 n（本批 = 4）
        per = 6               # ★ 每框架 6 个想法
        # ★ 随机 4 支：K=400 次取中位（比率型，不受 n 影响 ⇒ 可直接平均）
        rng = random.Random(20261024 + rep)
        sub_bleu, sub_jac = [], []
        for _ in range(400):
            idx = rng.sample(range(N), k)
            sub = [arts[i] for i in idx]
            sub_bleu.append(self_bleu(sub))
            sub_jac.append(mean_pair(sub, lambda x, y: jac(toks(x), toks(y))))
        s_adhd4_bleu = statistics.mean(sub_bleu)
        s_adhd4_jac = statistics.mean(sub_jac)
        s_adhd24_bleu = mean_pair(arts, lambda x, y: self_bleu([x, y]))
        s_adhd24_jac = mean_pair(arts, lambda x, y: jac(toks(x), toks(y)))
        s_tot4_bleu = self_bleu(tar)
        s_tot4_jac = mean_pair(tar, lambda x, y: jac(toks(x), toks(y)))
        cov = expect_frame_coverage(F, k, per)
        same_pair_frac = 1.0 - 1.0 / cov if cov and cov > 1 else 0.0
        rows.append(dict(tid=tid, rep=rep, n_adhd=N, n_expected=a.get("n_expected"), n_frames=F, k=k,
                         cover_expect=cov, same_frame_pair_frac=same_pair_frac,
                         tot_bleu=s_tot4_bleu, adhd4_bleu=s_adhd4_bleu, adhd24_bleu=s_adhd24_bleu,
                         tot_jac=s_tot4_jac, adhd4_jac=s_adhd4_jac, adhd24_jac=s_adhd24_jac))
        print("%s r%s ｜ ADHD %d 支 / %d 框架 ｜ 抽 %d 支 ⇒ 覆盖框架期望 %.2f ⇒ 同框架支对占 %.0f%%"
              % (tid, rep, N, F, k, cov, same_pair_frac * 100))
        print("   self-BLEU： ToT4=%.4f  ｜ ADHD@4=%.4f  ｜ ADHD全量24=%.4f" % (s_tot4_bleu, s_adhd4_bleu, s_adhd24_bleu))
        print("   Jaccard ： ToT4=%.4f  ｜ ADHD@4=%.4f  ｜ ADHD全量24=%.4f" % (s_tot4_jac, s_adhd4_jac, s_adhd24_jac))
        print("   ⇒ ★ 判据： ADHD@4 vs ADHD全量 差 %.1f%%（同框架对是否把相似度拉高）"
              % ((s_adhd4_bleu - s_adhd24_bleu) / s_adhd24_bleu * 100 if s_adhd24_bleu else 0))

    print()
    if rows:
        # ★ 只用「有效组」（掉支 < 30%）：作废组单列
        # ★ 有效组判据：★ 必须用 manifest 的 n_expected（预注册口径）⇒ 不用自造的 F×6
        #   （自造口径会把掉支 40% 的 S5 r1 误判为有效 ⇒ ★ 这就是"用自己的量代替预注册的量"）
        valid = [r for r in rows if r["n_expected"] and r["n_adhd"] >= 0.7 * r["n_expected"]]
        void = [r for r in rows if r not in valid]
        print("★ 有效组 %d 个（作废 %d 个：%s）" % (len(valid), len(void),
              [(r["tid"], r["rep"]) for r in void]))
        print()
        print("═══ 判决（★ 核心量：结构效应能解释总差距的百分之几）═══")
        for r in valid:
            s24, s4, st = r["adhd24_bleu"], r["adhd4_bleu"], r["tot_bleu"]
            struct = s4 - s24          # ★ 同框架对把相似度拉高多少
            total = st - s24           # ★ 从"ADHD 全量"到"ToT 4 支"的总差距
            frac = struct / total if total else float("nan")
            print("%s r%s ｜ 结构效应 +%.4f ｜ 总差距 %.4f ⇒ ★ 结构解释 %.1f%%（其余 %.1f%% 归生成策略）"
                  % (r["tid"], r["rep"], struct, total, frac * 100, (1 - frac) * 100))
        fr = []
        for r in valid:
            s24, s4, st = r["adhd24_bleu"], r["adhd4_bleu"], r["tot_bleu"]
            total = st - s24
            if total:
                fr.append((s4 - s24) / total)
        mf = statistics.median(fr) if fr else float("nan")
        print()
        print("★ 中位：★ 结构解释 %.1f%%  ⇒⇒ 归生成策略 %.1f%%" % (mf * 100, (1 - mf) * 100))
        print("★ 逐组范围：%.1f%%–%.1f%% ⇒ ⇒ ★ 按「倍数型读数必须报浮动范围」这条通则 ⇒ **只报区间**"
              % (min(fr) * 100, max(fr) * 100))
        # ★ 第三把尺子：Jaccard 与 self-BLEU 是否同向
        dis = [(r["tid"], r["rep"]) for r in valid
               if (r["adhd4_bleu"] < r["tot_bleu"]) != (r["adhd4_jac"] < r["tot_jac"])]
        print("★ 尺子分歧：self-BLEU 与 Jaccard 方向相反的组 = %s" % (dis or "无"))
        verdict = ("H-struct-minor" if mf < 0.30 else
                   "H-struct-major" if mf > 0.60 else "undecided")
        print()
        print("★★ 判决：%s" % verdict)
        if verdict == "H-struct-minor":
            print("   → ★★★ **结构效应真实存在但只能解释总差距的 %.1f%% ⇒ 主因是「生成策略」**" % (mf * 100))
            print("   → ⇒ 归因改写为：「ADHD 真代码的『一次连发 6 个想法』的生成策略，产出了彼此更不重复的想法」")
            print("   → ⇒ ⇒ ★★ **这批【不能】用来支持「交互结构级有效」**（结构不是主因）")
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump({"rows": rows, "valid": [(r["tid"], r["rep"]) for r in valid],
                   "struct_explain_frac_median": mf, "verdict": verdict,
                   "metric_disagreement": dis,
                   "note": "★ 零 API 调用；框架标签在 manifest 里已丢失（picked=null）⇒ 本检验不依赖标签"},
                  open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
        print("\n✔ 落盘：%s" % OUT)


if __name__ == "__main__":
    main()
