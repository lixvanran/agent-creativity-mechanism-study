#!/usr/bin/env python3
"""v6 检出力分析（结果产生前写入预注册用）。

问题：2×2 因子（有无代价 × 选择器是否读状态），
以 D0 = 0.0720 为噪声地板基线，要检出交互项 Δ 需要多少题 × 多少重复？

数据来源（只读，不跑新批）：
  runs/arch5_compare.jsonl  → 逐样本 gap（align(state) - align(generic)）→ 估计臂内 SD
  PREREG_v3.md 的 D0 = 0.0720 → 纯重跑地板

方法：
  2×2 交互项 = (判决格 - 无代价·状态化格) - (判决格对照 - 无代价·对照格)
  SE(交互) = σ * sqrt(1/n1 + 1/n2 + 1/n3 + 1/n4) = σ * 2/sqrt(n)   （n = 每格样本数）
  检出力 = Φ(Δ/SE - z_{1-α/2}) + Φ(-Δ/SE - z_{1-α/2})     （双侧 α）
"""
from __future__ import annotations
import json, math
from pathlib import Path

RUNS = Path(__file__).resolve().parent / "runs"
D0 = 0.0720          # v3 纯重跑地板（探针均值）
ALPHA = 0.05


def z(p: float) -> float:
    """标准正态分位（用 erfinv 近似，够用）。"""
    from statistics import NormalDist
    return NormalDist().inv_cdf(p)


def phi(x: float) -> float:
    from statistics import NormalDist
    return NormalDist().cdf(x)


def load_gaps() -> list[float]:
    """从 v5 主实验里取逐样本 gap。"""
    p = RUNS / "arch5_compare.jsonl"
    if not p.exists():
        return []
    gaps = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        st = r.get("align_state")
        gn = r.get("align_generic")
        if st is None or gn is None:
            continue
        try:
            gaps.append(float(st) - float(gn))
        except (TypeError, ValueError):
            continue
    return gaps


def sd(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def power(delta: float, sigma: float, n_per_cell: int) -> float:
    """给定效应量 delta、臂内 SD sigma、每格样本数 n_per_cell，返回检出力。"""
    if n_per_cell <= 0:
        return float("nan")
    se = sigma * math.sqrt(4.0 / n_per_cell)
    if se == 0:
        return 1.0
    lam = delta / se
    return phi(lam - z(1 - ALPHA / 2)) + phi(-lam - z(1 - ALPHA / 2))


def mde(sigma: float, n_per_cell: int, target: float = 0.80) -> float:
    """最小可检出效应量（80% 检出力）。"""
    lo, hi = 0.0, 5.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if power(mid, sigma, n_per_cell) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main() -> None:
    gaps = load_gaps()
    s = sd(gaps) if gaps else float("nan")
    print("=" * 72)
    print("v6 检出力分析（结果产生前）")
    print("=" * 72)
    print("★ 分轴说明（主会话 2026-10-24 14:7x 更正）")
    print("  本脚本 v2 只按『总 n』算 MDE —— 会把检出力算高。v3 要求分轴：")
    print("  · 路径轴（可分叉性）：三组 A02 + 层2 S4/S5/S6 ≈ 4 道（现有）")
    print("  · 取舍轴（可放弃）：现有 0 道（三组 15 道取舍空间全为『无』）")
    print("  ⇒ H1c 的交互项只能用**取舍轴**题 ⇒ ⇒ Stage-1（3 题）**测不了 H1c**")
    print("  ⇒ 下面所有表的『总样本』列请按**取舍轴题量**解读，路径轴题不可用于 H1c。")
    print("-" * 72)
    print(f"噪声地板 D0（v3 纯重跑）= {D0}")
    print(f"v5 逐样本 gap 数 n = {len(gaps)}")
    if gaps:
        m = sum(gaps) / len(gaps)
        print(f"v5 gap 均值 = {m:+.4f}   SD(σ) = {s:.4f}   "
              f"CV = {s/abs(m) if m else float('nan'):.2f}")
    print()
    print("── 情形 A：σ 用 v5 实测 SD ──")
    print(f"{'每格n':>6} {'总样本':>7} {'交互MDE(80%)':>14} {'power@Δ=0.15':>14} {'power@Δ=0.20':>14}")
    for n in (3, 5, 8, 10, 12, 15, 20, 25):
        if s != s:
            continue
        print(f"{n:>6} {n*4:>7} {mde(s, n):>14.4f} {power(0.15, s, n):>14.3f} {power(0.20, s, n):>14.3f}")
    print()
    print("── 情形 B：σ 不可得时，用 D0 地板当保守上界代理（σ = D0）──")
    print(f"{'每格n':>6} {'总样本':>7} {'交互MDE(80%)':>14} {'power@Δ=0.15':>14}")
    for n in (5, 10, 15, 20, 25, 30, 40):
        print(f"{n:>6} {n*4:>7} {mde(D0, n):>14.4f} {power(0.15, D0, n):>14.3f}")
    print()
    print("── 情形 C：若改用题为单位（题内多重复取均值）──")
    print("  若每题 3 重复先取均值，则每格 n=题数、每题均值 SD = σ/√3")
    if s == s:
        for n in (6, 10, 15, 20, 25, 30):
            sp = s / math.sqrt(3)
            print(f"{n:>6} 题  交互MDE(80%) = {mde(sp, n):.4f}   power@Δ=0.15 = {power(0.15, sp, n):.3f}")
    print()
    print("⚠️ 判定规则（写进预注册）：")
    print("   若预算下 MDE > 0.15（预注册主判据阈值）⇒ 检出力不足")
    print("   ⇒ 结论降级为『不可分辨 / 检出力不足』，不得读作『无效应』。")
    out = {
        "D0": D0, "alpha": ALPHA, "v5_gap_n": len(gaps),
        "v5_gap_sd": None if s != s else round(s, 6),
        "v5_gap_mean": None if not gaps else round(sum(gaps) / len(gaps), 6),
        "table_A": (None if s != s else [
            {"n_per_cell": n, "mde80": round(mde(s, n), 4),
             "power_delta015": round(power(0.15, s, n), 3),
             "power_delta020": round(power(0.20, s, n), 3)}
            for n in (3, 5, 8, 10, 12, 15, 20, 25)]),
        "table_B": [
            {"n_per_cell": n, "mde80": round(mde(D0, n), 4),
             "power_delta015": round(power(0.15, D0, n), 3)}
            for n in (5, 10, 15, 20, 25, 30, 40)],
    }
    p = RUNS / "v6_power.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已落盘：{p}")


if __name__ == "__main__":
    main()
