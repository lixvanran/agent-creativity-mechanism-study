#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **endstep_newlost_probe 的交叉验证 + 变异注入（★ 2026-10-25 重做）**

★★★ **★ 为什么重做（★ 负责人 2026-10-25 指出，★ 批评成立）★★**
★ 上一次那批负向测试：★ 变异体拷到临时目录 ⇒ ⇒ `import` 失败 ⇒ ⇒ **崩溃** ⇒ ⇒
★ **非零退出码被我判成"变异体如期失败 ⇒ 测试是活的"** ⇒ ⇒ ★★ **★ 什么都没测到 ★★**
★ ⇒ ⇒ **★ 崩溃 ≠ 断言失败（★ 任何非零退出都不等于"断言失败"）★★**

★★★★ **★ 本文件的三个修正 ★★★★**
★ ① **★ 变异体必须与原文件【同目录】★★** ⇒ ⇒ ★ ⇒ **否则 import 失败 ⇒ ⇒ 变成崩溃 ⇒ ⇒ 假绿**
★ ② **★ 只认【断言失败行】（★ `✘` 前缀）★★** ⇒ ⇒ ★ ⇒ **崩溃（Traceback / ImportError）一律不算数**
★ ③ **★ 先证明【变异真的发生了】★★** ⇒ ⇒ ★ ⇒ **再检查"判据是否抓住"** ⇒ ⇒ ★ ⇒ **否则"漏抓"的诊断方向是错的**

★★★★ **★ 交叉验证的设计（★ 独立实现，★ 不照抄）★★**
★ · 检查器**自己**重算 4-gram 覆盖与新增率（★ **不 import endstep 的 `norm`/`grams`**）
★ · 断言：★ 检查器算出的值 == `newlost_probe.json` 里 endstep 算出的值
★ ⇒ ⇒ ★ **★ 同源测试会一起错时一起绿；★ 独立实现才是真交叉验证 ★★**
★ ⇒ ⇒ ★ 变异 endstep 的判据 ⇒ ⇒ ★ 两边不再一致 ⇒ ⇒ ★ **断言失败** ⇒ ⇒ ★ **★ 证明判据是活的 ★★**

★ 用法：`python3 -B creativity_lab/experiments/test_endstep_newlost_mutations.py`
★ 退出码：★ 0 = 全过｜★ 1 = 有变异未被抓住（★ 假绿）｜★ 2 = 基线就不对（★ 变异测试无意义）
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(HERE, "endstep_newlost_probe.py")
RUN = os.path.join(ROOT, "runs", "endstep-matrix-2026-10-23")
OUT = os.path.join(RUN, "newlost_probe.json")
NGRAM = 4

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ✔ %s" % name)
    else:
        print("  ✘ %s  %s" % (name, detail))
        FAILED.append(name)


# ══════ ★ 独立实现（★ 不 import 被测模块）══════
def norm_indep(t: str) -> str:
    return re.sub(r"[^0-9A-Za-z一-鿿]+", "", t or "")


def grams_indep(t: str, n: int = NGRAM):
    t = norm_indep(t)
    return set(t[i:i + n] for i in range(max(0, len(t) - n + 1)))


def recompute(rows):
    """★ 独立重算：★ 从【原始 group_*.json】重算覆盖与新增率"""
    out = {}
    for fn in sorted(os.listdir(RUN)):
        if not (fn.startswith("group_") and fn.endswith(".json")):
            continue
        d = json.load(open(os.path.join(RUN, fn), encoding="utf-8"))
        arts = d.get("arts") or []
        if not arts:
            continue
        pool = [grams_indep(a) for a in arts]
        union = set().union(*pool) if pool else set()
        for arm, a in (d.get("arms") or {}).items():
            txt = a.get("text") or ""
            g = grams_indep(txt)
            cov = [round(len(p & g) / max(1, len(p)), 4) for p in pool]
            novel = len(g - union)
            out[(d.get("tid"), d.get("rep"), arm)] = {
                "coverage_per_branch": cov,
                "coverage_mean": round(sum(cov) / len(cov), 4) if cov else None,
                "novel_4gram_rate": round(novel / max(1, len(g)), 4),
                "out_chars_norm": len(norm_indep(txt)),
            }
    return out


# ══════ ★ 跑被测脚本 ══════
def run_probe():
    r = subprocess.run([sys.executable, "-B", TARGET], capture_output=True, text=True, cwd=ROOT)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def load_out():
    if not os.path.isfile(OUT):
        return None
    return json.load(open(OUT, encoding="utf-8"))


# ══════ ★ 交叉验证（★ ★ 每次变异后【都要重跑】★★）
def cross_check(verbose=True):
    # ★ 把 endstep 的产出与【独立重算】逐条对比 ⇒ ⇒ ★ 断言失败即【判据抓不住】
    global FAILED
    FAILED = []
    d = load_out()
    if not d:
        check("★ 产出存在", False, OUT)
        return 0
    mine = recompute(d.get("rows") or [])
    n = 0
    for row in d.get("rows") or []:
        for arm, r in (row.get("arms") or {}).items():
            key = (row.get("tid"), row.get("rep"), arm)
            m = mine.get(key)
            if m is None:
                continue
            check("★ %s r%s %s · 覆盖率一致" % (key[0], key[1], arm),
                  r.get("coverage_per_branch") == m["coverage_per_branch"],
                  "probe=%s indep=%s" % (r.get("coverage_per_branch"), m["coverage_per_branch"]))
            check("★ %s r%s %s · 新增率一致" % (key[0], key[1], arm),
                  r.get("novel_4gram_rate") == m["novel_4gram_rate"],
                  "probe=%s indep=%s" % (r.get("novel_4gram_rate"), m["novel_4gram_rate"]))
            n += 1
    if verbose:
        for f in FAILED:
            print("    ✘ %s" % f)
    return n


# ══════ ★ 变异清单（★ 每个旧片段必须唯一命中 ⇒ 否则"变异没发生"）══════
MUTS = [
    ("m1_ngram_4_to_3",
     "N = 4", "N = 3"),
    ("m2_coverage_denominator",
     "cov = [round(len(p & g) / max(1, len(p)), 4) for p in pool]",
     "cov = [round(len(p & g) / max(1, len(g)), 4) for p in pool]"),
    ("m3_novel_denominator",
     "novel_rate = round(novel / max(1, len(g)), 4)",
     "novel_rate = round(novel / max(1, len(pool_union)), 4)"),
    ("m4_norm_keeps_punct",
     't = re.sub(r"[^0-9A-Za-z一-鿿]+", "", t or "")',
     't = re.sub(r"[^0-9A-Za-z一-鿿]+", " ", t or "")'),
    ("m5_grams_uses_set_of_full",
     "return set(t[i:i + n] for i in range(max(0, len(t) - n + 1)))",
     "return set([t]) if t else set()"),
]


def main() -> int:
    print("== ★ endstep_newlost_probe · 交叉验证 + 变异注入 ==")
    if not os.path.isdir(RUN):
        print("✘ 缺 %s" % RUN)
        return 2
    orig = open(TARGET, encoding="utf-8").read()

    # ── ① 基线：★ 跑一次 ⇒ ★ 独立重算与它【逐条一致】──
    rc, out = run_probe()
    if rc != 0:
        print("✘ 基线跑不动（★ exit %d）:\n%s" % (rc, out[-800:]))
        return 2
    d = load_out()
    if not d:
        print("✘ 基线没产出 %s" % OUT)
        return 2
    n_cmp = cross_check()
    print("  ★ 交叉验证比对了 %d 个 (题,rep,臂) 读数" % n_cmp)
    if FAILED:
        print("  ✘ 基线就不一致 ⇒ ★ 变异测试无意义")
        return 2

    # ── ② 变异注入：★ 每个变异必须【被断言失败抓住】──
    backup = OUT + ".bak_for_mutation"
    shutil.copy2(OUT, backup)
    try:
        missed = []
        for name, old, new in MUTS:
            n = orig.count(old)
            if n != 1:
                print("  ✘ %-28s ★ 变异【没发生】（★ 锚点命中 %d 次，★ 应 1）" % (name, n))
                missed.append(name)
                continue
            mutated = orig.replace(old, new, 1)
            assert mutated != orig
            # ★ ★ 变异体必须与原文件【同目录】（★ 否则 import 失败 ⇒ ⇒ 崩溃 ⇒ ⇒ 假绿）★★
            open(TARGET, "w", encoding="utf-8").write(mutated)
            try:
                rc, out = run_probe()
                crashed = ("Traceback" in out) or ("ImportError" in out) or ("ModuleNotFound" in out)
                # ★★★ ★ 变异后【必须重跑交叉验证断言】★ ⇒ ★ ⇒ ★ 断言失败 = 被抓住 ★★★
                n_cmp2 = cross_check(verbose=False)
                fail_lines = list(FAILED)
                if fail_lines:
                    print("  ✔ %-28s ★ 被抓住（★ 断言失败 %d 条 / 比对 %d 读数）｜ ★ %s"
                          % (name, len(fail_lines), n_cmp2, fail_lines[0][:56]))
                elif crashed:
                    print("  ✘ %-28s ★ ★ 只崩了（★ 崩溃不算断言失败 ⇒ ⇒ 【没测到东西】）" % name)
                    missed.append(name)
                else:
                    print("  ✘ %-28s ★ ★ 没有任何断言失败（★ 变异没被抓住）" % name)
                    missed.append(name)
            finally:
                open(TARGET, "w", encoding="utf-8").write(orig)
                # ★ 还原产物（★ 变异版写过同一个 OUT ⇒ ⇒ 必须还原）
                if os.path.isfile(OUT):
                    shutil.copy2(backup, OUT)
        print()
        if missed:
            print("✘ 变异注入：★ %d/%d 未被抓住（★ ★ ⇒ 有假绿）★ ⇒ %s"
                  % (len(missed), len(MUTS), missed))
            return 1
        print("✔ 变异注入：★ %d/%d 全部被【断言失败】抓住（★ 判据是活的）" % (len(MUTS), len(MUTS)))
        return 0
    finally:
        if os.path.isfile(backup):
            shutil.copy2(backup, OUT)
            os.remove(backup)


if __name__ == "__main__":
    sys.exit(main())
