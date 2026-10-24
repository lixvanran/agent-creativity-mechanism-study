#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 自测：★ `partial_verdict.consistency_from_dirs` —— 零分辨力尺子必须被剔除 ★

★ **要钉住的那条承诺**（★ 2026-10-26 事故 ★）：
★   「一把尺子若在所有可比单元上 diff 全为 0 ⇒ 它对本对比零分辨力
★    ⇒ 必须先剔除 ⇒ 不得参与一致性门。」

★ **为什么值得钉**：★ 恒定尺子对【任何】对比都恒为「一致」⇒ 留在里面 ⇒
★ 一致性门变成【恒真】⇒ 「三尺一致 = 是」这句话是【空的】★
★ ⇒ ★ 而报告里如果引用了这句话，★ 就是把一个空门当成了证据。★

★ **判据必须行为级**：★ 只断言【返回值】，★ 不断言【源码长什么样】。★
★ 变异注入：★ 把「剔除恒定尺子」这一步去掉 ⇒ 测试必须红。★
"""

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from selftest_kit import suite, check, AssertionFailure  # noqa: E402
import partial_verdict  # noqa: E402


def t_three_rulers_one_constant():
    """★ 本批真实形态：★ structured_dedup 全 0，★ 另两把有信息。★"""
    dead, info, n_info, consistent, verdict = partial_verdict.consistency_from_dirs(
        {"vendi": (2, 2), "modes": (1, 1), "structured_dedup": (0, 0)})
    check("恒定尺子被判为零分辨力", list(dead.keys()) == ["structured_dedup"], repr(dead))
    check("恒定尺子被剔除出 info", "structured_dedup" not in info, repr(info))
    check("有信息的尺子数 = 2", n_info == 2, str(n_info))
    check("两把有信息的尺子方向一致 ⇒ consistent=True", consistent is True, repr(consistent))
    check("verdict 文本含『有信息的 2 把』", "有信息的 2 把" in verdict, verdict)


def t_two_rulers_opposite():
    """★ 两把有信息的尺子方向相反 ⇒ 一致性门应判否。★"""
    dead, info, n_info, consistent, verdict = partial_verdict.consistency_from_dirs(
        {"vendi": (3, 0), "modes": (0, 3)})
    check("无恒定尺子", dead == {}, repr(dead))
    check("有信息的尺子数 = 2", n_info == 2, str(n_info))
    check("方向相反 ⇒ consistent=False", consistent is False, repr(consistent))
    check("verdict 含『不可分辨』", "不可分辨" in verdict, verdict)


def t_only_one_informative():
    """★ 有信息的尺子不足 2 把 ⇒ 【不可判定】，★ 不能给 True/False。★"""
    dead, info, n_info, consistent, verdict = partial_verdict.consistency_from_dirs(
        {"vendi": (3, 0)})
    check("有信息的尺子数 = 1", n_info == 1, str(n_info))
    check("consistent 必须是 None（★ 不可判定 ★）", consistent is None, repr(consistent))
    check("verdict 含『不可判定』", "不可判定" in verdict, verdict)


def t_all_constant():
    """★ 三把全恒定 ⇒ 零信息 ⇒ 不可判定（★ 不能说『一致』 ★）。★"""
    dead, info, n_info, consistent, verdict = partial_verdict.consistency_from_dirs(
        {"a": (0, 0), "b": (0, 0), "c": (0, 0)})
    check("三把都判零分辨力", len(dead) == 3, repr(dead))
    check("有信息的尺子数 = 0", n_info == 0, str(n_info))
    check("consistent 必须是 None", consistent is None, repr(consistent))


def t_constant_would_otherwise_flip_verdict():
    """★★ 最关键的一条：★ 恒定尺子能【否决】一个真的一致 ⇒ 假「不一致」★★

    ★ 票的定义：每把尺子投 ``v[0] > v[1]``（正格数多于负格数 ⇒ 投 True）。
    ★ 恒定尺子 (0,0) ⇒ 恒投 False。
    ★ ⇒ ★ **若两把有信息的尺子都投 True，★ 加上恒定尺子的 False ⇒ 票集 len=2
    ★ ⇒ 旧逻辑判「不一致」⇒ 【假阴性】★**
    ★ ⇒ 而正确答案是「一致」（★ 恒定尺子无信息，★ 不该有投票权 ★）。

    ★ **本批的三个对比里 old == new（★ 实测 ★）** ⇒ ★ **我们报出的数字不受影响** ★
    ★ ⇒ ★ **但门本身是不稳的：★ 它可能【否决】一个真的一致 ⇒ ⇒ 必须修。★★
    """
    tri = {"vendi": (3, 0), "modes": (2, 0), "dead": (0, 0)}
    dead, info, n_info, consistent, verdict = partial_verdict.consistency_from_dirs(tri)
    check("★ 恒定尺子被剔除", "dead" in dead, repr(dead))
    check("★ 有信息的尺子数 = 2", n_info == 2, str(n_info))
    check("★ 两把信息尺同投 True ⇒ 判一致", consistent is True, repr(consistent))
    check("★ verdict = 是", verdict.strip() == "是", verdict)
    # ★ 对照：旧逻辑（不剔除）确实会给出假「不一致」
    old_votes = {(v[0] > v[1]) for v in tri.values()}
    check("★ 旧逻辑（不剔除）会给出假『不一致』", len(old_votes) == 2, repr(old_votes))


def t_tie_rulers_are_consistent():
    """★ 两把尺子都是 1 正 1 负（平局）⇒ 票相同 ⇒ 一致。★

    ★ ★ 这条是【修正我自己第一版测试的期望】★★：★ 我原先写「平局 ⇒ 不一致」是错的 ★
    ★ —— 票的定义是「正格数是否多于负格数」，★ (1,1) 不多于 ⇒ 投 False ★
    ★ —— 两把都投 False ⇒ 票一致 ⇒ 「一致」是对的。★
    """
    tri = {"vendi": (1, 1), "modes": (1, 1), "dead": (0, 0)}
    dead, info, n_info, consistent, verdict = partial_verdict.consistency_from_dirs(tri)
    check("恒定尺子被剔除", list(dead.keys()) == ["dead"], repr(dead))
    check("★ 两把平局尺子票相同 ⇒ 一致", consistent is True, repr(consistent))


def t_this_batch_old_equals_new():
    """★ 记录一个诚实的事实：★ 本批三个对比，★ 旧逻辑与新逻辑【结果相同】。★★

    ★ ⇒ ★ **⇒ 我们报出的数字【不受】这次修复影响** ★
    ★ ⇒ ★ **⇒ 这是一次【门的稳健性】修复，★ 不是【读数更正】★★
    ★ ⇒ ★ **⇒ 写报告时必须这么写，★ 不能说成「读数算错了」。★★
    """
    for tri in ({"vendi": (2, 2), "modes": (1, 1), "d": (0, 0)},
                {"vendi": (2, 2), "modes": (1, 2), "d": (0, 0)},
                {"vendi": (1, 3), "modes": (1, 2), "d": (0, 0)}):
        dead, info, n_info, consistent, verdict = partial_verdict.consistency_from_dirs(tri)
        old_votes = {(v[0] > v[1]) for v in tri.values()}
        old_consistent = len(old_votes) == 1
        check("★ 本批用例：旧新一致（★ 读数不受影响 ★）", old_consistent == consistent,
              "old=%s new=%s" % (old_consistent, consistent))


def main():
    with suite("partial_verdict · 一致性门的零分辨力剔除") as s:
        s.run("三尺其一直定", t_three_rulers_one_constant)
        s.run("两把方向相反", t_two_rulers_opposite)
        s.run("只有一把有信息", t_only_one_informative)
        s.run("三把全恒定", t_all_constant)
        s.run("★ 恒定尺子能否决真一致", t_constant_would_otherwise_flip_verdict)
        s.run("★ 两把平局尺子 ⇒ 一致", t_tie_rulers_are_consistent)
        s.run("★ 本批 old==new（读数不受影响）", t_this_batch_old_equals_new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
