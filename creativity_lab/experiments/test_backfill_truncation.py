#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 变异自测：★ backfill_vectors 的【断长守卫】与【计数自检】会不会红 ★★

★ ★★ 为什么这个测试存在（★ 2026-10-24 第 1 层论证线那条同族 ★）★★
★ 他们踩到：★ 同一个文件里【两个键函数】算法不一致 ⇒ ★ 「查表全部落空」
★   ★ ⇒ 「转换 0 条」却 exit=0 ⇒ ★ 全绿假象 ★
★ ⇒ ★ 我方自查发现【同族、且更隐蔽】的形态：★
★   ★ `zip(ids, vecs)` ⇒ ★ 若通道返回的向量数【少于】请求数 ⇒ ★ zip 静默截断 ★
★   ★ ⇒ ★ 漏掉的 uid 【既不在 successes 也不在 failures】⇒ ★ exit 0、★ manifest 正常、★
★   ★ 失败清单为空 ⇒ ★ ★ 【一切自检全绿】而那批单元的向量【根本没落盘】★★ ★
★   ★ ⇒ ★ 离线重算时它们会被【跳过或算错】⇒ ⇒ ★ 必须在 zip【之前】拦住 ★★★★
★ ⇒ ★ ⇒ ★ 本测试用【变异注入】证明这两道闸门【真的会红】★ ★

★ ★★ 纪律：★ 变异必须【精准打击被测的那一处】★★
★   ★ 不能连带删掉别的代码 ⇒ ★ 否则测到的是【耦合】而不是【被测物】★
★   ★ ⇒ ★ 本测试只改【embed 的返回条数】与【返回维度】⇒ ★ 不动闸门代码 ★
★   ★ ⇒ ★ 硬判据用【exit 码 + 报错文本】⇒ ★ 不断言 exit==0（★ 可能撞上另一道挡 ★）
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from selftest_kit import check, suite          # noqa: E402
import backfill_vectors as BV                 # noqa: E402

DIM = 1536


def _make_fixture(tmp):
    """★ 造 2 个单元的最小 run-dir + 单元清单 ★"""
    run = os.path.join(tmp, "run")
    ud = os.path.join(run, "units")
    os.makedirs(ud, exist_ok=True)
    ids = []
    for i, (arm, u) in enumerate([("nosel_b3_synth", 1), ("nosel_b3_synth", 2)]):
        uid = "S4_r1_%s_u%d" % (arm, u)
        ids.append(uid)
        with open(os.path.join(ud, "%s.json" % uid), "w", encoding="utf-8") as f:
            json.dump({"unit": uid, "post": "第 %d 个单元的综述后提案文本，内容足够长以避免空串判定。" % (i + 1),
                       "calls": []}, f, ensure_ascii=False)
    ul = os.path.join(tmp, "UNITS.txt")
    with open(ul, "w", encoding="utf-8") as f:
        f.write("\n".join(ids) + "\n")
    return run, ul, ids


def _run_main(run, ul, out, cache, monkey_vecs):
    """★ patch LLM.embed 的返回条数 ⇒ 调 main ★ ⇒ 捕获 SystemExit ★
    ★ ★ 注意：★ 脚本会先做一次【单条探针】来测通道并取 dim（第 1 次调用 ★）
    ★   ★ ⇒ ★ 变异必须【区分探针与批量】★ ⇒ ⇒ ★ 否则探针先炸 ⇒ ★ 测的根本不是被测物 ★★
    ★   ★ ⇒ ★ 这正是第 1 层论证线那条「★ 变异必须【精准打击被测的那一处】★」★★ ★"""
    from creativity_lab import client as CL

    orig = CL.LLM.embed
    state = {"n": 0}

    def fake(self, texts, typ="db", **kw):
        state["n"] += 1
        if state["n"] == 1:                       # ★ 探针：★ 单条、★ 正常 1536 维 ★
            return [[0.0] * DIM]
        return monkey_vecs(len(texts))
    CL.LLM.embed = fake
    old_argv = sys.argv
    sys.argv = ["backfill_vectors.py", "--run-dir", run, "--unit-list", ul,
                "--out-dir", out, "--cache-dir", cache]
    code = None
    try:
        # ★ ★ 脚本末尾是 `sys.exit(main())` ⇒ ⇒ main 的【返回值】就是进程退出码 ★
        #   ★ ⇒ ★ 直接调 main() 时必须把它当退出码（★ 否则 None ⇒ 判据必假 ★）★★
        _rc = BV.main()
        code = 0 if _rc is None else int(_rc)
    except SystemExit as e:
        code = e.code
    finally:
        CL.LLM.embed = orig
        sys.argv = old_argv
    return code


def main():
    with suite("backfill_vectors 断长守卫 / 计数自检（★ 变异自测 ★）") as s:
        tmp = tempfile.mkdtemp(prefix="bv_mut_")
        try:
            run, ul, ids = _make_fixture(tmp)

            # ★ ★ 每个场景用【独立的 out/cache】⇒ ★ 否则场景间互相污染 ★
            #   ★ （★ 上一版就是栽在这儿：★ 场景② 成功后场景③ 已无待补 ⇒ 幂等 ⇒ 断言全红 ★）★★
            def sc(name):
                o = os.path.join(tmp, "vec_" + name)
                c = os.path.join(tmp, "cache_" + name)
                os.makedirs(o, exist_ok=True)
                return o, c

            # ── 变异 ①：★ 通道返回【少于】请求数的向量（★ zip 静默截断 ★）──
            o1, c1 = sc("m1")
            code = _run_main(run, ul, o1, c1, lambda n: [[0.0] * DIM for _ in range(n - 1)])
            s.run("① 变异：返回条数少于请求数 ⇒ 须响亮失败（★ 不能 exit 0 ★）",
                  lambda: code != 0)
            s.run("① 变异：失败时【不许写出 manifest】（★ 否则下游会以为补录过 ★）",
                  lambda: not os.path.isfile(os.path.join(o1, "MANIFEST-post-hoc.json")))
            s.run("① 变异：失败时【不许留下半截向量件】（★ 静默漏掉的单元最毒 ★）",
                  lambda: len([f for f in os.listdir(o1) if f.endswith(".json")]) == 0)

            # ── 反向对照：★ 返回条数正确 ⇒ 必须成功 ★
            o2, c2 = sc("ok")
            code2 = _run_main(run, ul, o2, c2, lambda n: [[0.0] * DIM for _ in range(n)])
            s.run("② 反向：返回条数正确 ⇒ 须成功（★ exit 0 ★）",
                  lambda: code2 == 0)
            s.run("② 反向：manifest 的 n_vectors_written == 2",
                  lambda: json.load(open(os.path.join(o2, "MANIFEST-post-hoc.json"),
                                        encoding="utf-8"))["n_vectors_written"] == 2)

            # ── 变异 ②：★ 维度不符 ⇒ 逐条记账 + 响亮失败 ★
            o3, c3 = sc("m2")
            code3 = _run_main(run, ul, o3, c3, lambda n: [[0.0] * 7 for _ in range(n)])
            s.run("③ 变异：维度不符 ⇒ 须记失败并 exit≠0",
                  lambda: code3 == 1)
            s.run("③ 变异：失败清单里 2 条都要在（★ 不得静默吞掉 ★）",
                  lambda: len(json.load(open(os.path.join(o3, "MANIFEST-post-hoc.json"),
                                             encoding="utf-8"))["failures"]) == 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
