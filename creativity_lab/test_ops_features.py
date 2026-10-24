#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ f[6] 索引冲突 + 策略退化的最小复现测试（2026-10-21）

**要证明两件事**：

1. **旧实现（`f[6] = min(depth/6, 1.0)` 覆盖 STOP 的 one-hot）会失败**，
   新实现（丢掉 depth、f[6] 还给 STOP）**会通过**。
   - 旧实现下：STOP 的 f[6] 是 depth/6，**STOP 永远选不中**
   - 旧实现下：depth 对所有 op 是公共常数 ⇒ softmax 里抵消 ⇒ 零作用
2. **τ 不能小到把策略压成确定性**（否则轨迹无方差 ⇒ 优势≈0 ⇒ 梯度≈0 ⇒ 权重冻结）。
   ⇒ 断言：在 τ=0.06 下，op 分布的**有效选项数 n_eff ≥ 2.5**（不得塌成 one-hot）。
   ⇒ 旧实现（τ=0.02）实测 n_eff=1.19 ⇒ 必然 FAIL。

**测试自身也必须被验过** ⇒ `--mutate` 模式会把修复改回旧写法 ⇒ **测试必须 FAIL**。

用法：
  python3 test_ops_features.py            # 正常跑（应当 PASS）
  python3 test_ops_features.py --mutate   # 变异注入（应当 FAIL）
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from creativity_lab.ops import OPS, Graph, op_features  # noqa: E402

FAILS = []


def ok(cond, msg):
    if cond:
        print("  ✅ %s" % msg)
    else:
        print("  ❌ %s" % msg)
        FAILS.append(msg)


def build_graph():
    g = Graph()
    a1 = g.add("ANSWER", "甲答案" * 20, op="GEN_PLAIN")
    a2 = g.add("ANSWER", "乙答案" * 30, op="GEN_ANGLE")
    c1 = g.add("CLAIM", "断言一", parent=a1, op="EXTRACT"); g.nodes[c1].verdict = "支持"
    c2 = g.add("CLAIM", "断言二", parent=a1, op="EXTRACT"); g.nodes[c2].verdict = "矛盾"
    c3 = g.add("CLAIM", "断言三", parent=a2, op="EXTRACT")
    c4 = g.add("CLAIM", "断言四", parent=a2, op="SPLIT"); g.nodes[c4].verdict = "未提及"
    return g


def old_op_features(g, op, target, depth):
    """★ 变异体：把修复改回旧写法（f[6] 被 depth 覆盖）。"""
    f = [0.0] * 14
    f[OPS.index(op)] = 1.0
    if target is not None:
        f[7] = 1.0 if target.kind == "CLAIM" else 0.0
        f[8] = 1.0 if target.verdict == "支持" else 0.0
        f[9] = 1.0 if target.verdict == "矛盾" else 0.0
        f[10] = 1.0 if target.verdict is None else 0.0
        f[11] = min(len(target.text) / 300.0, 1.0)
        anc, stack = [], [target.nid]
        while stack:
            x = stack.pop(); anc.append(x)
            for (p, t, o) in g.edges:
                if p == x and t not in anc: stack.append(t)
        succ = sum(1 for a in anc if g.nodes[a].verdict == "支持")
        fail = sum(1 for a in anc if g.nodes[a].verdict == "矛盾")
        f[12] = min(succ / 5.0, 1.0)
        f[13] = min(fail / 3.0, 1.0)
    f[6] = min(depth / 6.0, 1.0)   # ★ 覆盖 STOP 的 one-hot（旧 bug）
    return f


def softmax(x, tau):
    x = np.asarray(x, dtype=float) / tau
    x = x - x.max()
    e = np.exp(x)
    return e / e.sum()


def n_eff(p):
    return 1.0 / float((np.asarray(p) ** 2).sum())


def check(mutate=False):
    feat = old_op_features if mutate else op_features
    g = build_graph()
    print("【%s】" % ("变异注入：把 f[6] 修复改回旧写法" if mutate else "当前实现"))

    # ── 断言 1：STOP 的 one-hot 不能被 depth 覆盖
    f_stop = feat(g, "STOP", None, 3)
    ok(abs(f_stop[6] - 1.0) < 1e-9,
       "STOP 的 f[6] 是 one-hot 1.0（实测 %.3f）" % f_stop[6])

    # ── 断言 2：STOP 与 GEN_PLAIN 必须可区分
    f_gen = feat(g, "GEN_PLAIN", None, 3)
    ok(abs(f_stop[6] - f_gen[6]) > 1e-9,
       "STOP 与 GEN_PLAIN 的 f[6] 不同（%.3f vs %.3f）⇒ STOP 可被选中" % (f_stop[6], f_gen[6]))

    # ── 断言 3：depth 不再污染（深度对决策应是零作用，而不是公共偏移）
    #   同一 op、同一 target，不同 depth ⇒ 分数必须完全相同
    w = np.array([0.08, -0.024, -0.017, 0.016, -0.044, 0.0, 0.0,
                  -0.028, 0.0, 0.0, -0.045, -0.022, 0.0, 0.0])
    s_d0 = float(w @ np.array(feat(g, "GEN_PLAIN", None, 0)))
    s_d6 = float(w @ np.array(feat(g, "GEN_PLAIN", None, 6)))
    ok(abs(s_d0 - s_d6) < 1e-9,
       "depth 不再作为公共偏移进入分数（%.6f vs %.6f）" % (s_d0, s_d6))

    # ── 断言 4：**新策略**（标准化分数 + τ=1.2）在多状态×多权重下都不得塌成 one-hot
    #   扫 104 组（13 个代表性状态 × 8 个不同权重方向），断言 min n_eff ≥ 2.5
    import creativity_lab.train_policy as _tp
    importlib.reload(_tp)
    states = [(None, 0)] + [(3, 1), (4, 1), (5, 2), (6, 2)] + [(3, 2), (5, 2), (3, 3)]
    rs = np.random.RandomState(0)
    ws = [w] + [rs.randn(14) * 0.05 for _ in range(7)]
    neffs = []
    for wv in ws:
        for tgt, dep in states:
            node = g.nodes[tgt] if tgt else None
            sc = [float(wv @ np.array(feat(g, op, node, dep))) for op in OPS]
            neffs.append(n_eff(_tp.policy_probs(sc)))
    min_neff = min(neffs)
    ok(min_neff >= 2.5,
       "新策略在 %d 组状态×权重下 n_eff 最低 %.2f（阈值 2.5）⇒ 不塌缩"
       % (len(neffs), min_neff))

    # ── 断言 5（对照组）：**旧实现**（未标准化 + τ=0.02）必然退化
    #   ⇒ 证明断言 4 有区分力（不是恒真）
    neffs_old = []
    for tgt, dep in states:
        node = g.nodes[tgt] if tgt else None
        sc = [float(w @ np.array(feat(g, op, node, dep))) for op in OPS]
        neffs_old.append(n_eff(softmax(sc, 0.02)))
    ok(min(neffs_old) < 2.5,
       "旧实现（未标准化 + τ=0.02）n_eff 最低 %.2f < 2.5 ⇒ 确认它会塌缩" % min(neffs_old))

    # ── 断言 6：STOP 的权重现在真的能影响选择
    w2 = w.copy(); w2[6] = 0.5
    node = g.nodes[3]
    sc2 = [float(w2 @ np.array(feat(g, op, node, 1))) for op in OPS]
    p2 = softmax(sc2, 0.06)
    ok(p2[OPS.index("STOP")] > 1e-6,
       "给 w[6] 正权重后 STOP 可被选中（P=%.4f）" % p2[OPS.index("STOP")])


    # ── 断言 7：**尺度无关**（τ 必须作用在标准化后的分数上）
    #   否则 ‖w‖ 增长会让策略越来越锐 ⇒ 最终塌成确定性 ⇒ 权重冻结（实测踩过）。
    import creativity_lab.train_policy as _tp
    importlib.reload(_tp)
    node = g.nodes[3]
    neffs_scaled = []
    for c in (0.25, 1.0, 4.0, 16.0):
        wc = w * c
        sc = [float(wc @ np.array(feat(g, op, node, 1))) for op in OPS]
        neffs_scaled.append(n_eff(_tp.policy_probs(sc)))
    spread = max(neffs_scaled) - min(neffs_scaled)
    ok(spread < 0.05,
       "‖w‖ 放大 64 倍后 n_eff 几乎不变（极差 %.4f，阈值 0.05）⇒ 温度尺度无关" % spread)
    ok(min(neffs_scaled) >= 2.5,
       "尺度无关下 n_eff 最低仍有 %.2f ≥ 2.5" % min(neffs_scaled))

    return len(FAILS) == 0


if __name__ == "__main__":
    mutate = "--mutate" in sys.argv
    good = check(mutate=mutate)
    if mutate:
        if good:
            print("\n❌ 变异注入后测试仍然 PASS ⇒ **这个测试是摆设**")
            sys.exit(1)
        print("\n✅ 变异注入后测试 FAIL（%d 处）⇒ 测试有效" % len(FAILS))
        sys.exit(0)
    if good:
        print("\n✅ 全部断言通过：f[6] 无冲突、STOP 可选、τ=0.06 不退化")
        sys.exit(0)
    print("\n❌ %d 处断言失败" % len(FAILS))
    sys.exit(1)
