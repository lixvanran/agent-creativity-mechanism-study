#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 动作—特征对齐的最小复现测试（2026-10-20 审计要求）

**要证明的事**：
  旧实现（特征与分数错位）**会失败**，新实现（成对排序 + 真实 choice）**会通过**。

**测试自身也必须被验过** ⇒ 提供 `--mutate` 模式：
  把修复改回旧写法（特征用原始顺序、choice 恒为 0）⇒ **测试必须 FAIL**。
  ⇒ 报不出 FAIL ⇒ 这个测试是摆设。

用法：
  python3 test_policy_alignment.py            # 正常跑（应当 PASS）
  python3 test_policy_alignment.py --mutate   # 变异注入（应当 FAIL）
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from creativity_lab.ops import OPS, Graph, op_features  # noqa: E402


def build_graph():
    """造一个可区分的图：2 个 ANSWER + 4 个 CLAIM（verdict 各不相同）。"""
    g = Graph()
    a1 = g.add("ANSWER", "甲答案" * 20, op="GEN_PLAIN")
    a2 = g.add("ANSWER", "乙答案" * 30, op="GEN_ANGLE")
    c1 = g.add("CLAIM", "断言一", parent=a1, op="EXTRACT"); g.nodes[c1].verdict = "支持"
    c2 = g.add("CLAIM", "断言二", parent=a1, op="EXTRACT"); g.nodes[c2].verdict = "矛盾"
    c3 = g.add("CLAIM", "断言三", parent=a2, op="EXTRACT")
    c4 = g.add("CLAIM", "断言四", parent=a2, op="SPLIT"); g.nodes[c4].verdict = "未提及"
    return g


def cands_of(g):
    out = [("GEN_PLAIN", None), ("GEN_ANGLE", None)]
    for n in g.of_kind("ANSWER")[-1:]:
        out.append(("EXTRACT", n))
    for n in [x for x in g.of_kind("CLAIM") if x.verdict is None][:2]:
        out.append(("VERIFY", n))
    for n in g.of_kind("CLAIM")[:1]:
        if n.verdict in (None, "未提及"):
            out.append(("SPLIT", n))
    return out


def check(force_mutation=False):
    """返回 (通过?, 失败原因列表)"""
    fails = []
    import creativity_lab.train_policy as tp
    if force_mutation:
        # —— 变异注入：把 rank_and_pick 换回旧的有 bug 版本 ——
        def buggy(cands, g, w, step, rng, explore=0.25):
            cand_f = []
            scored = []
            for op, tgt in cands:
                f = np.array(op_features(g, op, tgt, step))
                cand_f.append(f)
                sc = float(w @ f)
                if rng.random() < explore:
                    sc += rng.random() * 2.0
                scored.append((sc, op, tgt))
            scored.sort(key=lambda x: -x[0])
            order = [i for i, _ in sorted(enumerate(scored), key=lambda x: -x[1][0])]
            F = np.array([cand_f[i] for i in order])
            s_all = np.array([scored[i][0] for i in order])
            op, tgt = scored[0][1], scored[0][2]
            return op, tgt, F, s_all, 0, scored
        tp.rank_and_pick = buggy

    g = build_graph()
    cands = cands_of(g)
    # 给一个"非平凡"的 w：让不同候选分数不同，且**顺序与原始候选顺序不同**
    w = np.zeros(14)
    w[OPS.index("GEN_ANGLE")] = 0.09
    w[OPS.index("VERIFY")] = 0.05
    w[OPS.index("EXTRACT")] = 0.03
    w[OPS.index("GEN_PLAIN")] = 0.01
    w[OPS.index("SPLIT")] = 0.07

    for explore in (0.0, 0.25):
        for seed in range(12):
            rng = random.Random(seed)
            op, tgt, F, s_all, choice, pairs = tp.rank_and_pick(cands, g, w, 1, rng, explore)
            if op is None:
                fails.append("explore=%s seed=%s: 没有候选" % (explore, seed)); continue
            if len(F) != len(cands) or len(s_all) != len(cands):
                fails.append("explore=%s seed=%s: F/s_all 长度 != 候选数" % (explore, seed))
                continue
            if choice < 0 or choice >= len(F):
                fails.append("explore=%s seed=%s: choice 越界 %s" % (explore, seed, choice))
                continue
            # ★ 核心断言 1：F[choice] 必须就是**被选中动作**的特征
            want = np.array(op_features(g, op, tgt, 1))
            if not np.allclose(F[choice], want):
                fails.append("explore=%s seed=%s: F[choice] ≠ 被选中动作的特征（op=%s）"
                             % (explore, seed, op))
            # ★ 核心断言 2：F[i] 与 s_all[i] 必须描述**同一个候选**（分数单调降序）
            if len(s_all) > 1 and not all(s_all[i] >= s_all[i + 1] - 1e-12
                                          for i in range(len(s_all) - 1)):
                fails.append("explore=%s seed=%s: s_all 不是降序" % (explore, seed))
            # ★ 核心断言 3：每一行 F[i] 的 one-hot 必须对应一个真实存在的候选 op
            for i in range(len(F)):
                oh = [j for j in range(len(OPS)) if F[i][j] > 0.5]
                if len(oh) != 1:
                    fails.append("explore=%s seed=%s: F[%d] 的 op one-hot 不唯一" % (explore, seed, i))
                    break
                if OPS[oh[0]] not in [c[0] for c in cands]:
                    fails.append("explore=%s seed=%s: F[%d] 指向不存在的 op" % (explore, seed, i))
                    break
            # ★ 核心断言 4：s_all 必须是**干净分**（不含 U(0,2) 噪声）
            #   干净分 = w·f ⇒ 重算一遍必须逐字相等
            for i in range(len(s_all)):
                sc = float(w @ F[i])
                if abs(sc - s_all[i]) > 1e-9:
                    fails.append("explore=%s seed=%s: s_all[%d] 不是干净分（含噪声？）"
                                 % (explore, seed, i))
                    break
    return (len(fails) == 0), fails


if __name__ == "__main__":
    mutate = "--mutate" in sys.argv
    ok, fails = check(force_mutation=mutate)
    if mutate:
        print("=== 变异注入模式：把修复改回旧实现 ===")
        if ok:
            print("❌❌ 测试在有 bug 的实现上**通过了** ⇒ 这个测试是摆设！")
            sys.exit(2)
        print("✅ 测试在有 bug 的实现上**失败**（%d 处）⇒ 测试本身有效" % len(fails))
        for f in fails[:4]:
            print("   · %s" % f)
        sys.exit(0)
    print("=== 正常模式：当前实现 ===")
    if ok:
        print("✅ 全部断言通过：F/s_all 同序、choice 真实、s_all 为干净分")
        sys.exit(0)
    print("❌ 失败 %d 处：" % len(fails))
    for f in fails[:10]:
        print("   · %s" % f)
    sys.exit(1)
