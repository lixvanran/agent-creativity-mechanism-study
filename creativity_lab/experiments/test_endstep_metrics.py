#!/usr/bin/env python3
"""**层2 指标的自检 + 负向测试**（Tier A 级，秒级，零 API）。

> 2026-10-23 ｜ 落点：`creativity_lab/experiments/test_endstep_metrics.py`
> ★ 纪律：**检查器必须先证明自己能抓到东西**（否则一个"永远返回 0"的指标
>   和一个真的没信号的指标看起来一模一样）。
> ★ 每个负向测试都要**变异注入**过：把被检逻辑改坏 ⇒ 测试必须失败。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.metrics import (branch_diversity, covered_branches,  # noqa: E402
                                    coverage_curve, distinctness_scores, emb_coverage,
                                    fixed_len_coverage, keywords, survival_rate)

FAILED = []


def check(name, cond, extra=""):
    if cond:
        print("  ✔ %s" % name)
    else:
        print("  ✘ %s %s" % (name, extra))
        FAILED.append(name)


def fake_emb_factory(table):
    def f(ts):
        return [table[t] for t in ts]
    return f


def main() -> int:
    print("== Tier A：指标自检 ==")
    # ★ 夹具必须**机械校验**：三支之间**零 2-gram 重合**
    #   （第一版夹具 A/B 结尾共享"乙丙丁" ⇒ 存活率自比 < 1 ⇒
    #     **伪装成指标坏了**——这是"自检集设计错误伪装成判官问题"的翻版）
    A = "车间工人的AI时代看法"
    B = "银河系第三旋臂碳基装置"
    C = "紫色退款申请处理流程"
    arts = [A * 3, B * 3, C * 3]
    _ks = [keywords(x) for x in arts]
    _ov = [len(_ks[0] & _ks[1]), len(_ks[0] & _ks[2]), len(_ks[1] & _ks[2])]
    check("夹具有效性：三支零 2-gram 重合", all(o == 0 for o in _ov), str(_ov))

    # 1 存活率：**跨分支均值**语义
    #    ★（第一版期望写成"自比=1"是**测试自己写错了**：
    #      survival_rate 是对**所有分支**取均值 ⇒ 3 支只贴 1 支 ⇒ 1/3，不是 1.0）
    check("存活率：单支自比=1", abs(survival_rate([A * 3], A * 3) - 1.0) < 1e-9)
    check("存活率：单支异支=0", survival_rate([C * 3], A * 3) < 1e-9)
    check("存活率：3支只贴1支 ⇒ 1/3", abs(survival_rate(arts, A * 3) - 1.0 / 3) < 1e-6,
          str(survival_rate(arts, A * 3)))
    check("存活率：3支全贴 ⇒ 1.0", abs(survival_rate(arts, A * 3 + B * 3 + C * 3) - 1.0) < 1e-9)
    # 2 面保留数
    check("面保留数=3（全部贴上）", covered_branches(arts, A * 3 + B * 3 + C * 3, 0.3) == 3)
    check("面保留数=1（只贴一支）", covered_branches(arts, A * 3, 0.3) == 1)
    # 3 曲线单调
    cv = coverage_curve(arts, A * 3 + B * 3 + C * 3)
    vals = [cv[k] for k in ("0.10", "0.20", "0.30", "0.40", "0.50", "0.60")]
    check("阈值曲线单调不增", all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1)), str(vals))
    # 4 分支差异 & 独特度
    check("分支差异>0", branch_diversity(arts) > 0)
    check("独特度非负", all(x >= 0 for x in distinctness_scores(arts)))
    # 5 定长对照
    fl = fixed_len_coverage(arts, (A * 3 + B * 3 + C * 3), 60)
    check("定长后字数被截断", fl["chars"] == 60, str(fl))
    check("定长后覆盖≤原覆盖", fl["covered"] <= covered_branches(arts, A * 3 + B * 3 + C * 3, 0.3))

    print("== Tier A：语义层增量判据 ==")
    # 支0 与 支1 相似；输出 = 支0 ⇒ 只能算覆盖 1 支
    tab = {"a": [1.0, 0, 0], "b": [0.9, 0.43589, 0], "c": [0, 0, 1], "OUT": [1.0, 0, 0]}
    r = emb_coverage(["a", "b", "c"], "OUT", fake_emb_factory(tab))
    check("增量判据：输出=支0 ⇒ width=1", r["width"] == 1, str(r))
    check("增量判据：旧口径会误报 ≥1", r["width_naive"] >= 1)
    # 输出 = 支c（完全不相干的那支）⇒ 仍只覆盖 1 支
    tab2 = dict(tab); tab2["OUT2"] = [0, 0, 1]
    r2 = emb_coverage(["a", "b", "c"], "OUT2", fake_emb_factory(tab2))
    check("增量判据：输出=支c ⇒ width=1", r2["width"] == 1, str(r2))
    # 输出 = 三支的"平均方向" ⇒ 应覆盖多支
    tab3 = {"a": [1.0, 0, 0], "b": [0, 1.0, 0], "c": [0, 0, 1.0], "MIX": [0.577, 0.577, 0.577]}
    r3 = emb_coverage(["a", "b", "c"], "MIX", fake_emb_factory(tab3))
    check("增量判据：输出=三支混合 ⇒ width=3", r3["width"] == 3, str(r3))
    # 空输出不得静默变成"全覆盖"
    r4 = emb_coverage(["a", "b", "c"], "", fake_emb_factory(tab))
    check("空输出 ⇒ width=0（不静默）", r4["width"] == 0, str(r4))
    # 词块：空文本
    check("空文本词块=0", keywords("") == set())
    check("空分支不崩", survival_rate(["", A], A) >= 0)

    print("== Tier A：主因变量「有效秩」有分辨力吗 ==")
    import numpy as _np
    from creativity_lab.metrics import effective_rank, modes

    def _mk(groups):
        return [_np.array(v, dtype=float) for g in groups for v in g]

    er1 = effective_rank(_mk([[[1, 0, 0]] * 5]))
    er2 = effective_rank(_mk([[[1, 0, 0]] * 3, [[0, 1, 0]] * 2]))
    er3 = effective_rank(_mk([[[1, 0, 0]] * 2, [[0, 1, 0]] * 2, [[0, 0, 1]] * 1]))
    check("有效秩：全同 ⇒ 1.0", abs(er1 - 1.0) < 1e-6, str(er1))
    check("有效秩：2 模态 ⇒ ≈1.9", abs(er2 - 2.0) < 0.35, str(er2))
    check("有效秩：3 模态 ⇒ ≈2.8", abs(er3 - 3.0) < 0.35, str(er3))
    check("模态数：全同 ⇒ 1", modes(_mk([[[1, 0, 0]] * 5])) == 1)
    # ★ 陷阱（修正版）：**低维随机向量**的有效秩受**维数上界**限制
    #   ⇒ 3 维里放 5 支"互不相同"的随机向量，有效秩**不可能**超过 3
    #   ⇒ 用玩具低维数据测"模态数"会**系统性低估** ⇒ 真实 embedding（1536 维）不受此限
    #   ⚠️ 第一版这个测试写错了：循环里每次 `RandomState(0)` ⇒ 5 个向量**完全相同**
    #      ⇒ 测到的"全同"是**夹具的错**，不是低维陷阱（⇒ 测试写错 ≠ 指标坏）
    rs = _np.random.RandomState(0)
    noise = [rs.rand(3) for _ in range(5)]        # ★ 同一个 RandomState 连续生成 ⇒ 真随机
    check("低维随机向量：有效秩不超过维数上界 3",
          effective_rank(noise) <= 3.0 + 1e-6,
          "有效秩=%.3f" % effective_rank(noise))
    check("低维随机向量：5 支互不相同（夹具自检）",
          len({tuple(v) for v in noise}) == 5)

    print("\n%s" % ("全部通过" if not FAILED else "失败：%s" % FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
