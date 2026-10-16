"""诊断：指标可靠性、规则触发率、效应量、成本核算。"""
from __future__ import annotations
import json, math, statistics
from collections import defaultdict, Counter
from analyze import spearman, mean, sd, paired_t, perm_p, col, ARMS, ARMLABEL

rows = [json.loads(l) for l in open("results/merged.jsonl") if "error" not in l]

print("="*78); print("诊断 1  新颖性指标的可靠性：分族 vs 合并"); print("="*78)
print(f"{'范围':<22}{'n':>6}{'Spearman ρ (TFIDF vs N-gram)':>34}")
for f in sorted({r["family"] for r in rows}):
    sub = [r for r in rows if r["family"] == f]
    x = [r[f"arm_{a}_winner_tfidf"] for r in sub for a in ARMS]
    y = [r[f"arm_{a}_winner_ngram"] for r in sub for a in ARMS]
    print(f"{'  '+f:<22}{len(x):>6}{spearman(x,y):>34.3f}")
x = [r[f"arm_{a}_winner_tfidf"] for r in rows for a in ARMS]
y = [r[f"arm_{a}_winner_ngram"] for r in rows for a in ARMS]
print(f"{'  合并全部':<22}{len(x):>6}{spearman(x,y):>34.3f}")
print("\n  判读：若分族内 ρ 高而合并 ρ 低 → 指标本身可用，合并时被族间尺度差异污染。")

print("\n" + "="*78); print("诊断 2  选择规则的实际触发率"); print("="*78)
print("（S=紧 命中『效用门+选最异』说明批内确实存在更异且过门的候选；")
print("  大量 fallback 说明该臂的增益其实来自『挑了效用最高的』而非『挑了更异的』）")
print(f"\n{'臂':<26}{'规则':<28}{'占比':>8}")
for a in ARMS:
    c = Counter(r.get(f"arm_{a}_rule") for r in rows)
    for k, v in c.most_common():
        print(f"{ARMLABEL[a]:<26}{str(k):<28}{v/len(rows)*100:>7.1f}%")

print("\n" + "="*78); print("诊断 3  效应量（Cohen's d，配对）"); print("="*78)
print(f"{'对比':<30}{'指标':<10}{'Δ':>10}{'95%CI':>20}{'d':>9}{'p(perm)':>10}")
BASE = "loose_loose"
for a in ARMS[1:]:
    for key, lab in (("utility","效用"), ("winner_tfidf","新颖")):
        b = col(rows, BASE, key); c = col(rows, a, key)
        d = [x-y for x, y in zip(c, b)]
        m, s = mean(d), sd(d)
        ci = 1.96*s/math.sqrt(len(d))
        dc = m/s if s else float("nan")
        p = perm_p(d, iters=8000)
        print(f"{ARMLABEL[a]:<30}{lab:<10}{m:>+10.4f}{f'[{m-ci:+.3f},{m+ci:+.3f}]':>20}{dc:>9.2f}{p:>10.4f}")
    print()

print("="*78); print("诊断 4  成本核算（每个 (task,seed) 单元的 API 调用数）"); print("="*78)
print("  G=松 采 8 次；G=紧 最多采 16 次（被相似度拒绝的丢弃）。")
lo = mean([r["n_loose"] for r in rows]); ti = mean([r["n_tight"] for r in rows])
print(f"  实际平均：G松保留 {lo:.2f} 个 / G紧保留 {ti:.2f} 个")
print(f"  API 调用：G松 8 次，G紧 16 次 → G紧臂成本是 G松臂的 2.00×")
print(f"  全实验总调用数 ≈ {sum(8 + 16 for _ in rows)} 次（{len(rows)} 单元 × 24）")

print("\n" + "="*78); print("诊断 5  REMOTE 族：「远」「用」两轴的分离度（逐单元）"); print("="*78)
rem = [r for r in rows if r["family"] == "REMOTE"]
print(f"{'臂':<26}{'Δ远':>10}{'Δ用':>10}{'两轴反向的单元占比':>20}")
bnd = mean([r["arm_loose_loose_novel_distinct"] for r in rem])
bud = mean([r["arm_loose_loose_useful"] for r in rem])
for a in ARMS[1:]:
    nd = [r[f"arm_{a}_novel_distinct"] for r in rem]
    us = [r[f"arm_{a}_useful"] for r in rem]
    opp = sum(1 for i in range(len(rem))
              if (nd[i]-bnd)*(us[i]-bud) < 0) / len(rem) * 100
    print(f"{ARMLABEL[a]:<26}{mean(nd)-bnd:>+10.4f}{mean(us)-bud:>+10.4f}{opp:>19.1f}%")
print("  >50% 表示两轴多数单元反向变动 = 确实是两个独立维度，不是同一件事的两种说法。")
