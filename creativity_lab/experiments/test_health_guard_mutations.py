#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **health_guard 的变异注入（★ 2026-10-24）—— 证明早停守卫【是活的】**

★★★ **★ 主会话的要求（★ 原话）★★**
★ > 「★ **证明它活了**：★ **变异注入** —— ★ 构造一个「健康度 < 0.80」的批，★ 断言它**真的中止**（★ 抓断言失败行，★ 崩溃不算）★」

★★★★ **★ 本文件的三条纪律（★ 与我今天的教训一一对应）★★**
★ ① **★ 只认【断言失败行】（★ `✘` 前缀）★★** ⇒ ⇒ ★ ⇒ **崩溃（Traceback / ImportError）一律不算数**
★ ⇒ ⇒ ★ **★ 【★ 教训：★ 上一次 endstep 那批，★ "崩溃"被我当"断言失败"⇒ ⇒ 什么都没测到 ★】★★**
★ ② **★ 变异体必须与原文件【同目录】★★** ⇒ ⇒ ★ ⇒ **否则 import 失败 ⇒ ⇒ 崩溃 ⇒ ⇒ 假绿**
★ ③ **★ 先证明【变异真的发生】★★** ⇒ ⇒ ★ ⇒ **再检查"判据是否抓住"** ⇒ ⇒ ★ ⇒ **否则"漏抓"的诊断方向会错**

★ 用法：`python3 -B creativity_lab/experiments/test_health_guard_mutations.py`
★ 退出码：★ 0 = 全过｜★ 1 = 有变异未被抓住（★ 假绿）｜★ 2 = 基线就不对
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "health_guard.py")
FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ✔ %s" % name)
    else:
        print("  ✘ %s  %s" % (name, detail))
        FAILED.append(name)


def run_guard(root):
    """★ 跑被测模块的 __main__ 自测（★ 变异体与原文件【同目录】⇒ ⇒ import 不会崩）"""
    env = dict(os.environ)
    env["PYTHONPATH"] = root
    r = subprocess.run([sys.executable, "-B", os.path.join(root, "creativity_lab", "experiments", "health_guard.py")],
                       capture_output=True, text=True, cwd=root, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# ★ 变异清单：★ (名字, 旧片段, 新片段)
MUTS = [
    ("m1_never_abort",
     "            if h.channel_health < self.min_health:",
     "            if False:"),
    ("m2_empty_excluded_from_denominator",
     "        bad = int(n_failed) + int(n_empty)",
     "        bad = int(n_failed)"),
    ("m3_failed_excluded_from_denominator",
     "        bad = int(n_failed) + int(n_empty)",
     "        bad = int(n_empty)"),
    ("m4_checkpoint_never_reached",
     "        if (n_calls // self.every) != ((n_calls - 1) // self.every):",
     "        if False:"),
    ("m5_threshold_strictly_wrong",
     "            if h.channel_health < self.min_health:",
     "            if h.channel_health < self.min_health - 0.5:"),
]


def main() -> int:
    print("== ★ health_guard · 变异注入（★ 证明早停守卫是活的）==")
    if not os.path.isfile(TARGET):
        print("✘ 缺 %s" % TARGET)
        return 2
    orig = open(TARGET, encoding="utf-8").read()

    # ── ① 基线：★ 必须全绿（★ 否则失败无意义）──
    tmp = tempfile.mkdtemp(prefix="hg_mut_")
    try:
        os.makedirs(os.path.join(tmp, "creativity_lab", "experiments"), exist_ok=True)
        shutil.copy2(TARGET, os.path.join(tmp, "creativity_lab", "experiments", "health_guard.py"))
        rc, out = run_guard(tmp)
        if rc != 0 or FAILED:
            print("✘ 基线不绿（★ exit %d）:\n%s" % (rc, out[-900:]))
            return 2
        print("  ✔ 基线全绿（★ exit 0）")

        # ── ② 变异注入 ──
        missed = []
        for name, old, new in MUTS:
            n = orig.count(old)
            if n != 1:
                print("  ✘ %-42s ★ 变异【没发生】（★ 锚点命中 %d 次）" % (name, n))
                missed.append(name)
                continue
            mutated = orig.replace(old, new, 1)
            assert mutated != orig, "★ 变异没改变内容"
            # ★ ★ 变异体与原文件【同目录】（★ ⇒ import 不会崩 ⇒ ⇒ 不会假绿）★★
            shutil.copy2(TARGET, os.path.join(tmp, "creativity_lab", "experiments", "health_guard.py.bak"))
            open(os.path.join(tmp, "creativity_lab", "experiments", "health_guard.py"), "w",
                 encoding="utf-8").write(mutated)
            try:
                rc, out = run_guard(tmp)
                fail_lines = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("✘")]
                # ★ ★ 崩溃的判定：★ 只把【真崩溃】算崩溃；★ AssertionError 是【断言失败】★★
                crashed = (("Traceback" in out) and ("AssertionError" not in out)) \
                    or ("ImportError" in out) or ("ModuleNotFound" in out)
                if fail_lines:
                    print("  ✔ %-42s ★ 被抓住（★ 断言失败 %d 条）｜ ★ %s"
                          % (name, len(fail_lines), fail_lines[0][:52]))
                elif crashed:
                    print("  ✘ %-42s ★ ★ 只崩了（★ 崩溃不算 ⇒ ⇒ 【没测到东西】）" % name)
                    missed.append(name)
                else:
                    print("  ✘ %-42s ★ ★ 没有任何断言失败（★ 变异没被抓住）" % name)
                    missed.append(name)
            finally:
                shutil.copy2(os.path.join(tmp, "creativity_lab", "experiments", "health_guard.py.bak"),
                             os.path.join(tmp, "creativity_lab", "experiments", "health_guard.py"))
        print()
        if missed:
            print("✘ 变异注入：★ %d/%d 未被抓住（★ ★ ⇒ 有假绿）★ ⇒ %s" % (len(missed), len(MUTS), missed))
            return 1
        print("✔ 变异注入：★ %d/%d 全部被【断言失败】抓住（★ 早停守卫是活的）" % (len(MUTS), len(MUTS)))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
