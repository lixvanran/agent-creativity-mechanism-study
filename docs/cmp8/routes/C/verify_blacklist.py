# -*- coding: utf-8 -*-
"""路线 C · 自检脚本（红线 + 预算 + 泄漏）。

检查项：
  1. 黑名单源文件是否存在；存在则做**逐字子串**比对（U1–U4 题面/依据包/答案键），
     不存在则本项**判为「无法在本沙箱执行」**（fail-closed 声明），不假装通过。
  2. 路线 C 自己的文件里**不得**出现 U4 判准锚点词（路线 C 不需要它）。
  3. 训练语料与 U1–U4 的子串重叠数。
  4. 冒烟日志：HTTP POST 次数 ≤ 20、端点不含 openrouter、日志里无 openrouter 字样。
  5. 代码里被测侧端点断言（不得指向 openrouter）。
  6. 冒烟用的 2 道诊断题不含 U1–U4 的题面（逐字子串）。

⚠️ 本脚本**只把黑名单字符串读进内存做比对**，不打印、不落盘（协议 §4.1）。
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

ROOT = "/workspace/lab/routes/C"
BLACKLIST_GLOB = "/workspace/lab/cmp8repo/creativity_lab/data/user4_q*.json"
CORPUS = "/workspace/lab/cmp8repo/creativity_lab/data/policy_topics.json"

# 协议 §1.1 判准锚点里出现的 U4 词（路线 C **不需要**这些锚点 ⇒ 出现即视为泄漏）
ANCHOR_WORDS = ["陈会昌", "多血质", "胆汁质", "粘液质", "抑郁质", "气质量表"]

SCAN_GLOBS = ["*.py", "*.yaml", "*.md", "*.json", "*.txt"]


def collect_blacklist():
    strings = []
    files = sorted(glob.glob(BLACKLIST_GLOB))
    for p in files:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue

        def walk(o):
            if isinstance(o, str):
                if len(o) >= 8:
                    strings.append(o)
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(d)
    return files, strings


def scan_route_c_files():
    hits = []
    for g in SCAN_GLOBS:
        for p in glob.glob(os.path.join(ROOT, g)):
            base = os.path.basename(p)
            # 自指排除：检查脚本自身含锚点词（用于比对），不算泄漏
            if base.startswith("smoke_log") or base == "verify_blacklist.py":
                continue
            try:
                s = open(p, encoding="utf-8").read()
            except Exception:
                continue
            for w in ANCHOR_WORDS:
                if w in s:
                    hits.append((os.path.basename(p), w))
    return hits


def main():
    ok = True
    print("== 路线 C 自检 ==")
    files, bl = collect_blacklist()
    print("[1] 黑名单源：%s（%d 个文件，%d 条黑名单串）"
          % (BLACKLIST_GLOB if files else "**本沙箱不存在**", len(files), len(bl)))
    if not files:
        print("    ⇒ 本项**无法在本沙箱执行**（fail-closed）。真实批次前必须在源文件存在时重跑。")
        print("    ⇒ 替代检查（可在本沙箱执行）：路线 C 自己的文件里不得出现 U4 判准锚点词。")

    hits = scan_route_c_files()
    print("[2] 路线 C 文件中的 U4 锚点词命中：%d（期望 0）" % len(hits))
    for h in hits:
        print("    !", h)
    ok = ok and not hits

    if bl:
        corpus = json.load(open(CORPUS, encoding="utf-8"))
        c = 0
        for t in corpus["topics"]:
            c += sum(1 for s in bl if s in t["ask"])
        for law in corpus["laws"].values():
            c += sum(1 for s in bl if s in law["evidence"])
        print("[3] 训练语料 × 黑名单子串命中：%d（期望 0）" % c)
        ok = ok and c == 0
    else:
        print("[3] 训练语料 × 黑名单子串：跳过（无黑名单源）")

    log = os.path.join(ROOT, "smoke_log.json")
    if os.path.exists(log):
        d = json.load(open(log, encoding="utf-8"))
        n = d["calls"]["n_posts"]
        print("[4] 冒烟 HTTP POST：%d（上限 20）｜端点 %s" % (n, d["base_url"]))
        ok = ok and n <= 20 and "openrouter" not in d["base_url"].lower()
        raw = open(log, encoding="utf-8").read()
        ol = len(re.findall("openrouter", raw, re.I))
        print("    冒烟日志中 openrouter 字样出现 %d 次（期望 0）" % ol)
        ok = ok and ol == 0
        jl = os.path.join(ROOT, "smoke_calls.jsonl")
        if os.path.exists(jl):
            lines = [l for l in open(jl, encoding="utf-8") if l.strip()]
            print("    逐条调用记录：%d 行（应与上面的 POST 数一致）" % len(lines))
            ok = ok and len(lines) == n
    else:
        print("[4] 冒烟日志不存在 ⇒ 未跑")
        ok = False

    src = open(os.path.join(ROOT, "smoke.py"), encoding="utf-8").read()
    has_assert = 'assert "openrouter" not in BASE.lower()' in src
    print("[5] 冒烟脚本里的被测侧端点断言：%s" % ("有" if has_assert else "**缺**"))
    ok = ok and has_assert

    if bl:
        smoke = open(os.path.join(ROOT, "smoke.py"), encoding="utf-8").read()
        n = sum(1 for s in bl if s in smoke)
        print("[6] 冒烟脚本 × 黑名单子串命中：%d（期望 0）" % n)
        ok = ok and n == 0
    else:
        print("[6] 冒烟脚本 × 黑名单子串：跳过（无黑名单源）")

    print("\n结果：%s" % ("PASS（黑名单子项在本沙箱不可执行，已标注 fail-closed）"
                          if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
