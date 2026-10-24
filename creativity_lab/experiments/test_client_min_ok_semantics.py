#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 自测：★ `client.LLM.chat()` 的「未达 min_ok」语义（★ 独立实现 ★）

★ ★★ **判据来源**：★ 第 1 层论证线 2026-10-26 给的【判据描述】（★ 文本版 ★）
★ ⇒ ★ **我们按描述自己实现，★ 不抄对方的代码、★ 不抄对方的测试** ★
★ ⇒ ★ **交叉核对协议**：★ 双方各自实现修法、★ 各自写 RED/GREEN 测试、★ 只交换判据描述 ★

★ **★ 假对象纪律（★ 对方的核心提醒，★ 我们照办 ★）★★**
★ **只把网络层换掉**（★ `LLM._post` ⇒ 假函数 ★），★ **其余全部走真实代码路径** ★
★ ⇒ ★ **不替换 `chat()` 本身、★ 不替换 `LLM`、★ 不替换 payload 构造** ★
★ ⇒ ★ **⇒ 断言打在真实路径上** ★
★ ⇒ ★ **★ 若用自制假 LLM（★ 直接让某支返短文本 ★）⇒ ★ 它绕过了 `client.chat()` ★**
★ ⇒ ★ **⇒ 打在 `client.py` 上的修法对它完全无效 ⇒ ⇒ 判据没打在真实路径上 ★**
★ ⇒ ★ **⇒ 而它当时【看起来是红的】⇒ ⇒ 差点让我判「修法没用」★★ ⇒ ⇒ 【判据必须打在真实路径上】★★**

★ ★★ **★ 状态：★ 本文件【默认模式当前预期为红（exit 1）】★★**
★ ⇒ ★ 因为 `client.py` 的修法**还没落地**（★ 批运行期间不改它 ★）★
★ ⇒ ★ **这不是"测试坏了"★ ⇒ ★ 是"判据已经准备好、★ 等修法上线就变绿"★★**
★ ⇒ ★ **⇒ 任何人看到它 exit 1，★ 请看这一行而不是以为它坏了。★★**

★ **★ 本文件的两种模式 ★★**
| 模式 | 命令 | 期望 |
|---|---|---|
| ★ **修法已落地** ★ | `python3 -B test_client_min_ok_semantics.py` | ★ 全绿（exit 0）★ |
| ★ **修法未落地** ★ | `python3 -B test_client_min_ok_semantics.py --expect-red` | ★ 全绿（exit 0）★ 且明确打印「★ 修法未落地，★ 判据是活的」★ |

★ ⇒ ★ **⇒ 两种模式都是 exit 0 ⇒ ⇒ CI 不会红；★ 但【任何一种模式下判据失效】（★ 例如判据被写成恒真 ★）⇒ 必然 exit 非 0 ★**

★ **核心判据（★ 修法前 RED / 修法后 GREEN 的那一条 ★）**：
★ 传 `min_ok=200`，★ 假 `_post` 每次返回 **一段短的非空文本**（★ 本文件用 16 字 ★）
★ ⇒ ★ **期望 `chat()` 返回空串**（★ 不是那 20 字的短文本 ★）★
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# ★ `client.py` 在上一层（`creativity_lab/`）⇒ ★ 加进来才能 import 到【真实的】那个 ★
sys.path.insert(0, os.path.dirname(HERE))

from selftest_kit import suite, check, AssertionFailure  # noqa: E402

import client  # noqa: E402


SHORT = "这是一段只有二十个字左右的短内容"          # ★ 实测 16 字（★ 数字以 len(SHORT) 为准 ★）
FAKE = {"choices": [{"message": {"content": SHORT}, "finish_reason": "stop"}]}


def make_llm():
    """★ 真实 `client.LLM`，★ 只把网络层 `_post` 换掉。★"""
    llm = client.LLM()
    calls = []

    def fake_post(url, payload):
        calls.append((url, payload))
        return FAKE

    llm._post = fake_post
    return llm, calls


def t_core_returns_empty_when_below_min_ok():
    """★ 核心判据：★ 未达 min_ok ⇒ 返回空串（★ 不是短文本 ★）。★"""
    llm, calls = make_llm()
    out = llm.chat("测试提示", model="MiniMax-M3", min_ok=200)
    check("★ 走的是真实 chat() 路径（★ 假网络被调用过 ★）", len(calls) >= 1, str(len(calls)))
    check("★ 未达 min_ok ⇒ 返回空串", out == "", repr(out[:40]))
    check("★ 返回值不是那 20 字短文本", out != SHORT, repr(out[:40]))


def t_rec_keeps_the_failure():
    """★ 失败不许消失：★ rec 仍有条目，★ 且 ok == False。★"""
    llm, _ = make_llm()
    llm.chat("测试提示", model="MiniMax-M3", min_ok=200)
    check("★ rec 有条目", len(llm.rec) >= 1, str(len(llm.rec)))
    check("★ 该条目 ok == False", llm.rec[-1].ok is False, repr(llm.rec[-1]))
    check("★ 该条目 finish_reason == 'stop'（★ 传输本身成功 ★）",
          llm.rec[-1].finish_reason == "stop", repr(llm.rec[-1].finish_reason))


def t_transport_success_is_not_lost():
    """★ 传输成功的信息【不丢】：★ has_content == True 且 content_len == 20。★"""
    llm, _ = make_llm()
    llm.chat("测试提示", model="MiniMax-M3", min_ok=200)
    r = llm.rec[-1]
    check("★ has_content == True（★ 传输成功 ★）", r.has_content is True, repr(r))
    check("★ content_len == len(SHORT)（★ 内容长度被如实记账 ★）", r.content_len == len(SHORT),
          "%r vs %d" % (r.content_len, len(SHORT)))


def t_lowering_min_ok_lets_it_pass():
    """★ 证明这次改动【不是一刀切拒短】：★ min_ok=10 ⇒ 同样短的文本应当通过。★"""
    llm, _ = make_llm()
    out = llm.chat("测试提示", model="MiniMax-M3", min_ok=10)
    check("★ min_ok=10 ⇒ 返回正文", out == SHORT, repr(out[:40]))
    check("★ min_ok=10 ⇒ rec 里 ok == True", llm.rec[-1].ok is True, repr(llm.rec[-1]))
    check("★ min_ok=10 ⇒ has_content == True", llm.rec[-1].has_content is True, repr(llm.rec[-1]))


def t_default_min_ok_is_200():
    """★ 记录一个事实：★ 默认 min_ok 是 200（★ 与提示词「400 字以内」冲突 ⇒ 见报告 §6.12.5 ★）。★"""
    import inspect
    sig = inspect.signature(client.LLM.chat)
    dflt = sig.parameters["min_ok"].default
    check("★ 默认 min_ok == 200", dflt == 200, repr(dflt))


def run_all():
    t_core_returns_empty_when_below_min_ok()
    t_rec_keeps_the_failure()
    t_transport_success_is_not_lost()
    t_lowering_min_ok_lets_it_pass()
    t_default_min_ok_is_200()


def main():
    expect_red = "--expect-red" in sys.argv
    print("== 模式：%s ==" % ("★ 修法未落地（★ 判据应为 RED ★）★" if expect_red
                           else "★ 修法已落地（★ 判据应为 GREEN ★）★"))
    # ★ 先实测当前行为（★ 不靠推测 ★）
    llm, _ = make_llm()
    cur = llm.chat("测试提示", model="MiniMax-M3", min_ok=200)
    currently_red = (cur != "")     # ★ 修法未落地 ⇒ 返回短文本 ⇒ 判据 RED
    print("== 当前实测：min_ok=200 时 chat() 返回 %r（长度 %d）=="
          % (cur[:30], len(cur)))
    if expect_red:
        # ★ ★ 关键：★ 本模式下【核心那条判据本来就该红】⇒ ⇒ ★ 若直接跑它，
        #   ★ suite 会判成「失败」⇒ ★ 退出码变 1 ⇒ ★ 【那就分不清是
        #   ★ 「修法没落地（正常）」还是「判据失效（异常）」了】★★
        #   ⇒ ⇒ ★ 落法：★ 在本模式下【断言它确实红】★ ⇒ ★ 红了才算通过。★★
        with suite("client min_ok 语义（★ 期望修法未落地 ★）") as s:
            def expect_core_to_be_red():
                llm2, _ = make_llm()
                out = llm2.chat("t", model="MiniMax-M3", min_ok=200)
                check("★ 修法【确实还没落地】（★ 返回的是短文本而非空串 ★）",
                      out != "", repr(out[:30]))
                # ★ ★ 反向断言：★ 核心判据【此刻必须失败】★ ⇒ ★ 否则判据失效
                try:
                    t_core_returns_empty_when_below_min_ok()
                except AssertionFailure:
                    print("  ✔ ★ 核心判据此刻如预期为 RED（★ 判据是活的 ★）")
                    return
                raise AssertionFailure("★ 核心判据此刻居然是绿的 ⇒ ★ 判据失效（★ 恒真？）★")
            s.run("★ 修法未落地 且 核心判据此刻为 RED", expect_core_to_be_red)
            s.run("★ 其余判据（★ 这些应当现在就成立 ★）", t_rec_keeps_the_failure)
            s.run("★ 传输成功信息不丢（★ 现在就成立 ★）", t_transport_success_is_not_lost)
            s.run("★ min_ok 调小仍通过（★ 现在就成立 ★）", t_lowering_min_ok_lets_it_pass)
            s.run("★ 默认 min_ok == 200", t_default_min_ok_is_200)
        return 0
    with suite("client min_ok 语义（★ 修法已落地 ★）") as s:
        s.run("核心：未达 min_ok ⇒ 返回空串", t_core_returns_empty_when_below_min_ok)
        s.run("rec 保留失败条目", t_rec_keeps_the_failure)
        s.run("传输成功信息不丢", t_transport_success_is_not_lost)
        s.run("min_ok 调小仍通过", t_lowering_min_ok_lets_it_pass)
        s.run("默认 min_ok == 200", t_default_min_ok_is_200)
    return 0


if __name__ == "__main__":
    sys.exit(main())
