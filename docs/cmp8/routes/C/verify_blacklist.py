# -*- coding: utf-8 -*-
"""路线 C · 红线自检（黑名单泄漏 / 端点 / 调用数 / 落盘一致性）。

**这一版修掉了一个"假自检"**：上一版把黑名单 glob 指向了一个**不含 U1–U4 文件**的目录树，
于是子串比对根本没跑，却整体报了 PASS。⇒ 本版：
  - 黑名单源路径是**多个候选**（含真实存在的那一个）；
  - **源不存在 ⇒ 整体结果不是 PASS**（fail-closed：整体 exit code 非 0）；
  - 每一项检查**单独标注 executed / skipped**，不把 skipped 当 passed。

黑名单三类（协议 §4.1）：
  (1) 题面字符串：`ask` 逐字
  (2) 依据包片段：每条原子事实（`sources[].fact`）逐字 + 其 ≥8 字的连续片段
  (3) 答案键：`name` 逐字 + 其 ≥4 字的连续片段（比协议更严，用来兜住「多血质」这种短结论词）

⚠️ 黑名单字符串**只读进内存做比对**：命中时只报「文件名 / 任务号 / 类别 / 长度 / 哈希前缀」，
**不打印、不落盘**匹配到的原文（协议 §4.1）。
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys

ROOT = "/workspace/lab/routes/C"
# ★ 真实存在 U1–U4 依据包的是第一个路径；第二个是历史副本（cmp8repo 树里没有这些文件）
BLACKLIST_GLOBS = [
    "/workspace/lab/creativity_lab/data/user4_q*.json",
    "/workspace/lab/cmp8repo/creativity_lab/data/user4_q*.json",
]
CORPUS = "/workspace/lab/cmp8repo/creativity_lab/data/policy_topics.json"

# 协议 §1.1 判准锚点里出现的 U4 词（路线 C **不需要**这些锚点 ⇒ 出现即视为泄漏）
ANCHOR_WORDS = ["陈会昌", "多血质", "胆汁质", "粘液质", "抑郁质", "气质量表"]

SCAN_GLOBS = ["*.py", "*.yaml", "*.md", "*.json", "*.txt"]
# 自指排除：检查脚本自身含锚点词与 glob 路径（用于比对），不算泄漏
SELF_EXCLUDE = {"verify_blacklist.py"}


# ------------------------------------------------------------------ 黑名单
def _fragments(s: str, n: int) -> set:
    t = s or ""
    return {t[i:i + n] for i in range(max(len(t) - n + 1, 0))}


def build_blacklist():
    """返回 (sources, entries)。entries = [(tid, kind, text), ...]"""
    sources, entries = [], []
    for g in BLACKLIST_GLOBS:
        for p in sorted(glob.glob(g)):
            try:
                d = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            sources.append(p)
            tid = str(d.get("tid") or os.path.basename(p))
            ask = d.get("ask") or ""
            name = d.get("name") or ""
            if ask:
                entries.append((tid, "ask", ask))
            if name:
                entries.append((tid, "name", name))
                for fr in _fragments(name, 4):
                    entries.append((tid, "name_frag4", fr))
            for s in (d.get("sources") or []):
                fact = (s or {}).get("fact") or ""
                if not fact:
                    continue
                entries.append((tid, "fact", fact))
                for fr in _fragments(fact, 8):
                    entries.append((tid, "fact_frag8", fr))
    return sources, entries


def scan_text(text: str, entries) -> list:
    """返回 [(tid, kind, len, sha1[:8])]，不含原文。"""
    hits = []
    for tid, kind, s in entries:
        if s and s in text:
            hits.append((tid, kind, len(s),
                         hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]))
    return hits


# ------------------------------------------------------------------ 汇总
# ★★ 硬规则（复核 6d 的要求）★★
#   **自检跳过任何一项检查时，绝不能输出 PASS，必须非零退出。**
#   理由："跳过"不是"通过"——一个没跑的检查既不能证明红线成立，也不能证明红线不成立；
#   把 skipped 当 passed 就是"假自检"（上一版正是栽在这里）。
#   ⇒ 本文件里所有"跳过"分支（无黑名单源、冒烟日志不存在……）都进 `executed=False`，
#     由 `finalize()` 统一判死。
def finalize(results):
    """把检查结果汇总成 (exit_code, n_executed, n_failed, n_skipped)。"""
    failed = [r for r in results if r[1] and not r[2]]
    skipped = [r for r in results if not r[1]]
    n_exec = sum(1 for r in results if r[1])
    code = 0 if (not failed and not skipped) else 1
    return code, n_exec, len(failed), len(skipped)


def selftest():
    """自测：证明「跳过 ⇒ 非零退出」这条规则**真的**在代码里生效。

    用构造出来的结果表驱动 `finalize()`（不跑真实检查）：
      - 有一项 skipped ⇒ 退出码必须非 0
      - 有一项 failed  ⇒ 退出码必须非 0
      - 全部通过        ⇒ 退出码必须为 0
    """
    good = ("某项", True, True, "ok")
    skip = ("某项", False, False, "**未执行**")
    bad = ("某项", True, False, "坏了")
    cases = [
        ("全部通过", [good, good], 0),
        ("含跳过", [good, skip], 1),
        ("含失败", [good, bad], 1),
        ("跳过+失败", [skip, bad], 1),
    ]
    ok = True
    print("== 自测：跳过/失败 ⇒ 非零退出 ==")
    for name, res, want in cases:
        code, n_exec, n_fail, n_skip = finalize(res)
        good_case = (code == want)
        print("[%-4s] %-12s 退出码=%d（期望 %d）"
              % ("PASS" if good_case else "FAIL", name, code, want))
        ok = ok and good_case
    print("结果：%s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# ------------------------------------------------------------------ 检查
def main():
    results = []          # (name, executed, ok, detail)

    # [1] 黑名单源
    sources, entries = build_blacklist()
    have_bl = bool(sources and entries)
    results.append(("黑名单源可用", True, have_bl,
                    "命中源文件 %d 个 / 黑名单条目 %d 条（glob: %s）"
                    % (len(sources), len(entries), " , ".join(BLACKLIST_GLOBS))))

    # [2] 路线 C 自身文件 vs 黑名单
    if have_bl:
        scanned, hits = 0, []
        for g in SCAN_GLOBS:
            for p in sorted(glob.glob(os.path.join(ROOT, g))):
                base = os.path.basename(p)
                if base in SELF_EXCLUDE:
                    continue
                try:
                    s = open(p, encoding="utf-8").read()
                except Exception:
                    continue
                scanned += 1
                for h in scan_text(s, entries):
                    hits.append((base,) + h)
        results.append(("路线C文件 × 黑名单", True, not hits,
                        "扫描 %d 个文件，命中 %d 处%s"
                        % (scanned, len(hits),
                           ("：" + "; ".join("%s/%s/%s(len=%d,h=%s)" % h for h in hits[:5]))
                           if hits else "")))
    else:
        results.append(("路线C文件 × 黑名单", False, False, "**未执行**（无黑名单源）"))

    # [3] U4 锚点词（独立于黑名单源的可执行替代检查）
    hits = []
    for g in SCAN_GLOBS:
        for p in sorted(glob.glob(os.path.join(ROOT, g))):
            base = os.path.basename(p)
            if base in SELF_EXCLUDE:
                continue
            try:
                s = open(p, encoding="utf-8").read()
            except Exception:
                continue
            for w in ANCHOR_WORDS:
                if w in s:
                    hits.append((base, w))
    results.append(("路线C文件 × U4锚点词", True, not hits,
                    "命中 %d 处%s" % (len(hits),
                                     ("：" + "; ".join("%s/%s" % h for h in hits[:5]))
                                     if hits else "")))

    # [4] 训练语料 vs 黑名单
    if have_bl:
        corpus = json.load(open(CORPUS, encoding="utf-8"))
        blob = json.dumps(corpus, ensure_ascii=False)
        h = scan_text(blob, entries)
        results.append(("训练语料 × 黑名单", True, not h,
                        "命中 %d 处%s" % (len(h),
                                         ("：" + "; ".join("%s/%s(len=%d)" % (x[0], x[1], x[2])
                                                           for x in h[:5]))
                                         if h else "")))
    else:
        results.append(("训练语料 × 黑名单", False, False, "**未执行**（无黑名单源）"))

    # [5] 训练侧标注 vs 黑名单
    if have_bl:
        meta = open(os.path.join(ROOT, "train_corpus_meta.json"), encoding="utf-8").read()
        h = scan_text(meta, entries)
        results.append(("训练标注 × 黑名单", True, not h, "命中 %d 处" % len(h)))
    else:
        results.append(("训练标注 × 黑名单", False, False, "**未执行**（无黑名单源）"))

    # [6] 冒烟日志：调用数 / 端点 / openrouter 字样
    log = os.path.join(ROOT, "smoke_log.json")
    if os.path.exists(log):
        d = json.load(open(log, encoding="utf-8"))
        n = d["calls"]["n_posts"]
        raw = open(log, encoding="utf-8").read()
        ol = len(re.findall("openrouter", raw, re.I))
        jl = os.path.join(ROOT, "smoke_calls.jsonl")
        lines = [l for l in open(jl, encoding="utf-8")] if os.path.exists(jl) else []
        ok = (n <= 20 and ol == 0 and len(lines) == n
              and "openrouter" not in d["base_url"].lower())
        results.append(("冒烟调用账", True, ok,
                        "POST=%d(上限20) 逐条记录=%d openrouter字样=%d 端点=%s"
                        % (n, len(lines), ol, d["base_url"])))
        if have_bl:
            h = scan_text(raw, entries)
            results.append(("冒烟日志 × 黑名单", True, not h, "命中 %d 处" % len(h)))
        else:
            results.append(("冒烟日志 × 黑名单", False, False, "**未执行**（无黑名单源）"))
    else:
        results.append(("冒烟调用账", True, False, "冒烟日志不存在 ⇒ 未跑"))

    # [7] 被测侧端点断言（代码里必须有）
    src = open(os.path.join(ROOT, "smoke.py"), encoding="utf-8").read()
    has_assert = ('assert "openrouter" not in BASE.lower()' in src
                  and 'BASE == "https://api.minimaxi.com/v1"' in src)
    results.append(("被测侧端点断言", True, has_assert,
                    "smoke.py 里有端点断言" if has_assert else "**缺端点断言**"))

    # [8] 提案者诊断入口必须是白名单实现（不接受裸 episode 字典）
    prop = os.path.join(ROOT, "proposer.py")
    if os.path.exists(prop):
        ps = open(prop, encoding="utf-8").read()
        has_gate = ("structural_diagnostics" in ps and "ALLOWED_KEYS" in ps
                    and "def structural_diagnostics" in ps)
        results.append(("提案者诊断白名单入口", True, has_gate,
                        "proposer.py 实现了 structural_diagnostics 白名单" if has_gate
                        else "**proposer.py 缺少白名单入口**"))
    else:
        results.append(("提案者诊断白名单入口", True, False, "**proposer.py 不存在**"))

    # ---- 汇总 ----
    print("== 路线 C 自检（v3：黑名单源真实可查；skipped ≠ passed；跳过 ⇒ 非零退出）==")
    for name, executed, ok, detail in results:
        mark = "PASS" if (executed and ok) else ("FAIL" if executed else "SKIP")
        print("[%-4s] %-24s %s" % (mark, name, detail))
    code, n_exec, n_failed, n_skipped = finalize(results)
    print("\n可执行项 %d / %d；失败 %d；跳过 %d"
          % (n_exec, len(results), n_failed, n_skipped))
    if n_skipped:
        print("⚠️ 有项目**未执行**（不算通过 ⇒ 按硬规则整体判 FAIL 并非零退出）")
    print("结果：%s" % ("PASS" if code == 0 else "FAIL"))
    return code


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
