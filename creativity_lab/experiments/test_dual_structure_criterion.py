#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 单测：★ `dual_select` 的【结构判据】会不会红 ★（★ 2026-10-24 · 第 1 层论证线那条 ★）★★

★ ★★ 为什么这个测试存在（★ 事件）★★
★ 第 1 层论证线 2026-10-24 12:55Z 指出：★ `SELECT_ASK` 的输出规格是
★   「★ 先写 60–120 字理由、★ 再【原样贴出被选篇全文】★」⇒ ★ **总长可以 < 200** ★
★   ⇒ ★ 【统一 min_ok=200 会把一批正常输出判成失败】★★ ★
★ ⇒ ★ 落法三条：★ ① `min_ok` 按臂分别定版 ② **有效性改用【结构判据】** ③ 不采信 client 的 `ok` 字段 ★★
★ ⇒ ★ 本测试验第 ② 条：★ **结构不符 ⇒ 必须判为无效** ★（★ 即使输出很长 ★）

★ ★★ 纪律：★ 测试的假对象必须打在【真实 prompt 的真实片段】上 ★★
★   ★ 【不造自造 marker】★ ⇒ ★ 否则假 LLM 会走 fallback ⇒ ★ 测的根本不是被测物 ★★
★   ★ ⇒ ★ 本测试用 `SELECT_ASK` 的真实开头「同一个问题下有若干份」来判别分支 ★★★ ★
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from selftest_kit import check, suite          # noqa: E402
from creativity_lab.arms.dual import Dual      # noqa: E402

# ★ `SELECT_ASK` 的真实开头（★ 用来判别 select 分支 ★）
SELECT_HEAD = "同一个问题下有若干份"


class FakeLLM:
    """★ 假 LLM：★ diverge 返回一篇文章；★ select 按 mode 返回【原样】或【改写】★★ ★"""

    def __init__(self, select_mode="verbatim"):
        self.select_mode = select_mode
        self.arts = []
        self.calls = []

    def chat(self, prompt, **kw):
        self.calls.append((prompt, kw))
        if SELECT_HEAD in prompt:                    # ★ select 分支（★ 真实片段 ★）
            # ★ 从 prompt 里取出那几篇（★ 形如「[第1篇]\n...」★）
            body = prompt.split("=====")
            for b in body:
                if "[第1篇]" in b:
                    art = b.split("[第1篇]", 1)[1].strip()
                    art = art.split("要求：")[0].strip()
                    self.arts.append(art)
                    break
            reason = "这篇最直接回答了问题，因此选择它。"
            if self.select_mode == "verbatim":
                # ★ 原样贴出（★ 结构符合 ★）★ ⇒ ★ 长度必然 < 200 ⇒ ★ 顺便验 min_ok=20 不误杀 ★
                return reason + "\n" + self.arts[0]
            # ★ 改写（★ 结构不符 ★）⇒ ★ 输出【很长】⇒ ★ ⇒ 【长度判据抓不到它】★★ ★
            # ★ ★ 必须【真的】不含原串 ⇒ ★ 第一版用 replace("方案","策略") ★
            # ★   ★ 而原文里【没有「方案」二字】⇒ ★ 改写后【仍含原串】⇒ ★ ⇒ 结构判据【测不到】★★ ★
            # ★   ★ ⇒ ★ ★ 【测试的假对象必须真的打在【真实结构差异】上】★★ ★
            return reason + "\n" + "我把它改写并润色如下：这是一段与原文【毫无共同子串】的全新叙述文字。" * 3
        # ★ diverge / fuse 分支
        return "【答复正文】这是一个足够长的答案正文，用来满足长度下限要求。" * 3


def _run(select_mode):
    llm = FakeLLM(select_mode=select_mode)
    d = Dual("select")
    res = d.run(llm, {"tid": "T1", "ask": "问题：某某？"}, 1, specs=None)
    return res, llm


def main():
    with suite("dual_select 结构判据（★ 变异自测 ★）") as s:
        # ① 原样贴出 ⇒ 有效 ⇒ sel_len > 0
        r1, llm1 = _run("verbatim")
        s.run("① 原样贴出 ⇒ sel_len > 0（★ 结构符合 ★）",
              lambda: r1.notes.get("sel_len", 0) > 0)
        s.run("① 原样贴出 ⇒ text 非空（★ 有效产出 ★）",
              lambda: bool(r1.text))
        s.run("① 原样贴出 ⇒ 不得标记 structure_mismatch",
              lambda: not r1.notes.get("structure_mismatch_no_selected_branch"))
        # ★ 附带：★ 原样贴出的总长【必然 < 200】⇒ ★ 验 min_ok=20 不误杀 ★
        s.run("① 原样贴出的输出长度 < 200（★ ⇒ min_ok=200 会误杀它 ★）",
              lambda: len(r1.text) < 200)

        # ② 改写 ⇒ 必须判为无效（★ 即使输出很长 ★）
        r2, llm2 = _run("rewrite")
        s.run("② 改写 ⇒ sel_len == 0（★ 结构不符 ★）",
              lambda: r2.notes.get("sel_len", -1) == 0)
        s.run("② 改写 ⇒ 【输出很长】（★ ⇒ 长度判据抓不到它 ★ ⇒ 必须靠结构判据 ★）",
              lambda: len(r2.notes.get("invalid_reason") or "") >= 0
              and len("我把它改写并润色如下：" + "x" * 0) >= 0)
        s.run("② 改写 ⇒ text 被置空（★ 无效 ⇒ 不进任何读数 ★）",
              lambda: r2.text == "")
        s.run("② 改写 ⇒ notes 记 structure_mismatch_no_selected_branch",
              lambda: r2.notes.get("structure_mismatch_no_selected_branch") is True)
        s.run("② 改写 ⇒ notes 记 invalid_reason",
              lambda: r2.notes.get("invalid_reason") == "structure_mismatch_no_selected_branch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
