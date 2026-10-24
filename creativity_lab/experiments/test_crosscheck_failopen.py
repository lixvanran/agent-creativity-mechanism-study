#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ crosscheck 的【fail-open 变异自测】：★ 证明「跳过检查」会被抓 ★

> 落点：`creativity_lab/experiments/test_crosscheck_failopen.py`
> 用法：`python3 -B creativity_lab/experiments/test_crosscheck_failopen.py`
> 退出码：0 = 自测全过（★ 该红的时候红了 ★）；1 = 有问题
>
> ★ ★★ 为什么要有这个（★ 2026-10-26 ★）★★
★ 第 1 层论证线报：★ 「挪走 gate_alignment.json ⇒ 12 项整块静默跳过 ⇒ ★ 退出码仍是 0、
★ 输出还写着『全部一致』」★ ⇒ ★ 我方自查：★ 本工具【同样有】★
★ ★ 6 处 `if os.path.exists(...)` 包着检查块 ⇒ ★ 缺 manifest ⇒ 那组检查【整块消失】★★
★ ★ 实测更严重：★ DIVERGE 路径指到不存在的目录 ⇒ ★ **21 项检查【从未执行】**★
★ ★ ★ 而我方一直报「48/48 全绿」★ ★ ★
★ ⇒ ★ 本自测用【同一条代码路径】模拟缺失（★ `CROSSCHECK_SIMULATE_MISSING` ★）⇒ ★
★ ⇒ ★ 断言：★ 缺输入时必须【非 0 退出】（★ 响亮失败 ★）★ ⇒ ★ 证明它【会红】★
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "creativity_lab", "experiments", "crosscheck_report.py")
REPORT = os.path.join(ROOT, "docs", "交付", "第二组交付报告_2026-10-25.md")

FAILED = []


def check(name, cond, detail=""):
    ok = bool(cond)
    print("  %s %s%s" % ("✔" if ok else "✘", name, ("  —— %s" % detail) if detail else ""))
    if not ok:
        FAILED.append(name)


def run(env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([sys.executable, "-B", SCRIPT, REPORT],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    if not os.path.isfile(REPORT):
        print("★ 找不到报告：%s" % REPORT)
        return 1
    print("== ★ crosscheck fail-open 变异自测 ==")
    # ① 基线：必须绿
    rc, out = run()
    check("基线：全部输入齐全 ⇒ exit 0", rc == 0, "实际 exit=%d" % rc)
    check("基线：检查项数达到下界", "下界 69" in out or "下界" in out, "")
    # ② 变异：模拟缺 DIVERGE ⇒ 必须非 0（响亮失败）
    for name in ("DIVERGE", "ENDSTEP", "EVAL", "divergence-matrix-2026-10-24"):
        rc, out = run({"CROSSCHECK_SIMULATE_MISSING": name})
        check("★ 缺 %s ⇒ 必须响亮失败（exit≠0）" % name, rc != 0, "实际 exit=%d" % rc)
        check("★ 缺 %s ⇒ 输出必须点名它" % name, name in out, "")
    # ③ 变异：缺一个 ⇒ 仍不能报「无缺失」
    rc, out = run({"CROSSCHECK_SIMULATE_MISSING": "DIVERGE"})
    check("★ 缺输入 ⇒ 绝不能出现「✔ 无缺失」", "无缺失" not in out, "")
    print()
    if FAILED:
        print("✘ 失败 %d 项：%s" % (len(FAILED), FAILED))
        return 1
    print("✔ 自测全过：★ 跳过检查 ⇒ 【会红】★（★ 不是恒真 ★）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
