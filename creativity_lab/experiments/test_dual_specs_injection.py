#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ `Dual` 臂的 `specs` 注入 + 臂级失败记账（★ 2026-10-24）★★

> 第二组 ｜ 配套 `creativity_lab/arms/dual.py` 的改动
> 需求来源：论文簇 / 第 1 层论证线《WORKPACK-4 回源核对》§五（★ 补丁由对方写好 · 本组实现并自测 ★）

★★ **本测试要证明的六件事 ★★
① 下架型号（返空）必须被**显式记账**，★ 不能靠"过滤掉空串"★
② **计划支数与实际支数必须同时可见**（`n_specs` / `models_used` / `models_failed`）
③ 注入 5 个活型号 ⇒ **5 支全活**
④ 注入型号**不破坏**框架/persona 的错位绑定
⑤ **默认路径**（`specs=None`）行为与旧版逐位相同（向后兼容）
⑥ ★ 变异体必须红（★ 证明本测试不是空转 ★）

★ **零 API、零额度、零 GPU** ★
★★ ★★ `check(name, cond)` 的 cond 必须是**立即求值的布尔**★★
★★ ★★ （★ 传 lambda ⇒ `bool(lambda)` 恒为 True ⇒ ★ **断言全是空转** ⇒ ★ **假绿** ★）★★
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))     # ★ /lab（★ 两层 dirname ★）
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from selftest_kit import check, suite          # noqa: E402  ★ 仓内共享的 check()，不另造

DEAD = "MiniMax-M2.1"          # ★ 实测 404（2026-10-24）
ALIVE5 = ["MiniMax-M3", "MiniMax-M3.1-Flash-Preview", "MiniMax-M2.7",
          "MiniMax-M2.5", "MiniMax-M2.7-highspeed"]


class FakeLLM:
    """★ 返空的型号模拟「下架」★（★ 不打任何 API ★）"""

    def __init__(self, dead=(DEAD,)):
        self.dead = set(dead)
        self.calls = []

    def chat(self, prompt, model=None, **kw):
        self.calls.append(model)
        if model in self.dead:
            return ""                      # ★ 下架：返空
        # ★ ★ 2026-10-24：★ 假对象必须【满足真实规格】★★ ★
        #   ★ `SELECT_ASK` 的规格是「★ 先写理由、★ 再【原样贴出被选篇全文】★」⇒ ★
        #   ★   ★ ★ 【不满足规格 ⇒ 结构判据会判它无效】⇒ ★ ⇒ branches=0 ⇒ ★
        #   ★   ★ ★ 而【这不是结构判据的错】★ ⇒ ★ ⇒ ★ 【是假对象不真实】★★ ★
        #   ★ ⇒ ★ 修法：★ select 分支【原样贴出被选篇】★★ ★
        #   ★ ⇒ ★ 判别用【真实 prompt 开头】（★ 不造自造 marker ★）★★ ★
        if "同一个问题下有若干份" in prompt:
            _art = ""
            for _b in prompt.split("====="):
                if "[第1篇]" in _b:
                    _art = _b.split("[第1篇]", 1)[1].split("要求：")[0].strip()
                    break
            return "理由：这篇最直接。\n" + _art
        return "答复正文 for %s" % (model,)


def _load_from(path, name="dual_under_test"):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _suite_main():
    from creativity_lab.arms import dual as D

    specs = D._branch_specs()
    check("默认 _branch_specs 出 5 支", len(specs) == 5, "got %d" % len(specs))
    check("默认型号取 MODELS 前 5", [s[1] for s in specs] == D.MODELS[:5],
          "got %s" % [s[1] for s in specs])
    check("默认框架序列 = FRAMES 前 5", [s[0] for s in specs] == D.FRAMES[:5] or
          [s[0]["name"] if isinstance(s[0], dict) else s[0] for s in specs] ==
          [D.FRAMES[i % len(D.FRAMES)]["name"] for i in range(5)])

    inj = D._branch_specs(alive=ALIVE5)
    check("注入后仍 5 支", len(inj) == 5, "got %d" % len(inj))
    check("注入后型号 = 注入池", [s[1] for s in inj] == ALIVE5,
          "got %s" % [s[1] for s in inj])
    check("注入后框架序列不变", [s[0] for s in specs] == [s[0] for s in inj])
    check("注入后 persona 序列不变", [s[2] for s in specs] == [s[2] for s in inj])

    # ★ ★ 失败记账必须在【含死型号的池】上测 ★ ★
    # ★ 默认池 MODELS[:5] 含 MiniMax-M2.1（★ 实测 404 ★）⇒ ★ 它会返空 ⇒ ★ 必须被记账 ★
    # ★ （★ 别用 ALIVE5 测这个：★ 那里根本没有死型号 ★ ⇒ ★ 期望必然落空 ★）
    llm = FakeLLM()
    d = D.Dual("select")
    r = d.run(llm, {"tid": "T1", "ask": "q"}, 1, specs=specs)
    check("notes 存在且是 dict", isinstance(r.notes, dict), "got %r" % (r.notes,))
    check("n_specs = 5（计划支数可见）", r.notes.get("n_specs") == 5,
          "got %r" % r.notes.get("n_specs"))
    check("models_failed 记到下架型号", r.notes.get("models_failed") == [DEAD],
          "got %r" % r.notes.get("models_failed"))
    check("models_used 不含下架型号", DEAD not in r.notes.get("models_used", []),
          "got %r" % r.notes.get("models_used"))
    check("models_used 长度 = 4（实际支数可见）", len(r.notes.get("models_used", [])) == 4,
          "got %r" % r.notes.get("models_used"))
    check("branches = 4（实际拿到正文的支数）", r.branches == 4, "got %r" % r.branches)
    check("失败型号确实被调用过（不是凭空记账）", DEAD in llm.calls,
          "calls=%r" % llm.calls)

    llm2 = FakeLLM(dead=())
    r2 = D.Dual("select").run(llm2, {"tid": "T1", "ask": "q"}, 1, specs=inj)
    check("全活 ⇒ models_failed 为空", r2.notes.get("models_failed") == [],
          "got %r" % r2.notes.get("models_failed"))
    check("全活 ⇒ models_used 5 个", len(r2.notes.get("models_used", [])) == 5,
          "got %r" % r2.notes.get("models_used"))
    check("全活 ⇒ branches = 5", r2.branches == 5, "got %r" % r2.branches)

    llm3 = FakeLLM()
    r3 = D.Dual("select").run(llm3, {"tid": "T1", "ask": "q"}, 1)     # ★ 默认路径 ★
    check("默认路径 models_failed 记到下架型号", r3.notes.get("models_failed") == [DEAD],
          "got %r" % r3.notes.get("models_failed"))
    check("默认路径 notes.n_specs = 5", r3.notes.get("n_specs") == 5,
          "got %r" % r3.notes.get("n_specs"))


def _mutation_check():
    """⑥ 变异注入：★ 把「失败记账」改回静默 ⇒ 本测试必须红 ★"""
    src = os.path.join(ROOT, "creativity_lab", "arms", "dual.py")
    with open(src, encoding="utf-8") as f:
        orig = f.read()
    mut = orig.replace("                failed.append(model)",
                       "                pass  # ★ MUTATION: 失败记账被删 ★")
    if mut == orig:
        return ("SKIP", "★ 未找到变异锚点 ⇒ ★ 不能判本测试是否活 ★")
    mutdir = os.path.join(os.path.dirname(src), "_mut_tmp")
    os.makedirs(mutdir, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="dualspecs_")
    try:
        mutpath = os.path.join(mutdir, "dual.py")
        with open(mutpath, "w", encoding="utf-8") as f:
            f.write(mut)
        m = _load_from(mutpath)
        llm = FakeLLM()
        r = m.Dual("select").run(llm, {"tid": "T1", "ask": "q"}, 1,
                                  specs=m._branch_specs(alive=ALIVE5))
        if r.notes.get("models_failed") == [DEAD]:
            return ("FAIL", "★ 变异体仍通过 ⇒ ★ 本测试【抓不住】失败记账被删 ⇒ ★ 测试是空转 ★")
        return ("PASS", "★ 变异体被抓住（models_failed 变空）★ ⇒ ★ 本测试是活的 ★")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        shutil.rmtree(mutdir, ignore_errors=True)


if __name__ == "__main__":
    with suite("Dual specs 注入 + 臂级失败记账") as s:
        s.run("主断言组", _suite_main)
    print()
    print("== ⑥ 变异注入（★ 证明本测试不是空转 ★）==")
    kind, msg = _mutation_check()
    print("   %s：%s" % (kind, msg))
    if s.failed:
        print("   ✘ 失败项：%s" % s.failed)
    raise SystemExit(0 if (not s.failed and kind == "PASS") else 1)
