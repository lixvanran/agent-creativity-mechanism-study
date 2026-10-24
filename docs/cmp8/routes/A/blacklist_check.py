# -*- coding: utf-8 -*-
"""黑名单自检：确认路线 A 的文件里**没有** U1–U4 的内容。

依据：`/workspace/lab/routes/PROTOCOL.md` §4.1（红线 R-1 / R-13）。

纪律（协议 §4.1 末段）：
- 黑名单字符串**只允许读进内存做比对**；
- **不得**出现在任何提示词、诊断集、校准集、DEV 依据包或路线文档里；
- 因此本脚本**不打印命中字符串本身**，只打印
  「文件 / 行号 / 类别 / 命中长度 / 命中片段的 sha1 前 8 位」。

黑名单三类（协议 §4.1 原文）：
  ① 题面字符串      —— U1–U4 的 `ask` 字段，逐字
  ② 依据包片段      —— 依据包每一条原子事实文本，及其 ≥ 8 字的连续片段
  ③ 答案键          —— 标准结论词及其最长公共子串
     （本脚本不硬编码任何答案键：只从 user4_*.json 的 `ask` / `name` 派生，
       因为协议只允许把 user4 文件里的字符串读进内存比对。）

用法：
    python3 blacklist_check.py <文件> [<文件> ...]
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

USER4_GLOBS = [
    "/workspace/lab/creativity_lab/data/user4_q*.json",
    "/workspace/lab/cmp8repo/cmp8/creativity_lab/data/user4_q*.json",
]

FRAG_MIN = 8        # 协议 §4.1 ②：≥ 8 字的连续片段
NGRAM_MIN = 4       # 提示类：来自题面/题名的 ≥ 4 字 n-gram（只提示，不 abort）


def _cjk_runs(s: str) -> list:
    """抽出连续的中日韩字符段。"""
    out, cur = [], []
    for ch in s:
        if "\u4e00" <= ch <= "\u9fff":
            cur.append(ch)
        else:
            if len(cur) >= 2:
                out.append("".join(cur))
            cur = []
    if len(cur) >= 2:
        out.append("".join(cur))
    return out


def _frags(s: str, k: int) -> list:
    s = (s or "").strip()
    if len(s) < k:
        return [s] if s else []
    return [s[i:i + k] for i in range(len(s) - k + 1)]


def build_blacklist() -> tuple:
    """返回 (strict_set, hint_set, n_checked)。字符串只在内存里。"""
    strict, hint = set(), set()
    n = 0
    for pat in USER4_GLOBS:
        for path in sorted(glob.glob(pat)):
            try:
                d = json.load(open(path, encoding="utf-8"))
            except Exception:
                continue
            n += 1
            ask = d.get("ask") or ""
            name = d.get("name") or ""
            ev = d.get("evidence") or ""
            srcs = d.get("sources") or []
            # ① 题面 / 题名（逐字）
            for s in (ask, name):
                if len(s) >= 4:
                    strict.add(s)
            # ② 依据包片段（≥8 字连续片段）+ sources 的每条原子事实
            for s in _frags(ev, FRAG_MIN):
                strict.add(s)
            for src in srcs:
                f = (src or {}).get("fact") or ""
                if len(f) >= 4:
                    strict.add(f)
                for s in _frags(f, FRAG_MIN):
                    strict.add(s)
            # ③ 答案键的代理：题面/题名里的中文 n-gram（≥4 字）
            for base in (ask, name):
                for run in _cjk_runs(base):
                    for i in range(len(run) - NGRAM_MIN + 1):
                        hint.add(run[i:i + NGRAM_MIN])
    return strict, hint, n


def _h(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def scan(paths: list) -> dict:
    strict, hint, n_src = build_blacklist()
    res = dict(source_files=n_src, blacklist_strict=len(strict), blacklist_hint=len(hint),
               files=[], strict_hits=0, hint_hits=0, files_scanned=0, files_missing=0)
    for path in paths:
        if not os.path.exists(path):
            res["files"].append(dict(path=path, missing=True))
            res["files_missing"] += 1
            continue
        text = open(path, encoding="utf-8").read()
        lines = text.splitlines()
        fh = []
        for ln_no, line in enumerate(lines, 1):
            for s in strict:
                if s and s in line:
                    fh.append(dict(line=ln_no, cls="strict", len=len(s), sha1=_h(s)))
                    res["strict_hits"] += 1
            for s in hint:
                if s and s in line:
                    fh.append(dict(line=ln_no, cls="hint", len=len(s), sha1=_h(s)))
                    res["hint_hits"] += 1
        res["files"].append(dict(path=path, chars=len(text), lines=len(lines), hits=fh))
        res["files_scanned"] += 1
    return res


if __name__ == "__main__":
    args = sys.argv[1:]
    out = scan(args)

    # ⚠️ **空目标守卫**（第二轮返工 F7 的修法）。
    #    旧版：`args=sys.argv[1:]` → `scan(args)` → `exit(1 if strict_hits else 0)`，
    #    于是「一个文件都没扫」会打印 `"files": []` 并 **exit 0**（= 橡皮图章）。
    #    现在：被扫对象为空 / 黑名单来源没找到 / 黑名单本身为空 ⇒
    #    显式报「未执行」并以**非零**退出码结束，**绝不**能报 PASS。
    guards = []
    if not args:
        guards.append("no_target_args: 命令行没有给出任何被扫文件")
    if out["files_scanned"] == 0:
        guards.append("no_files_scanned: 被扫对象列表里没有一个存在的文件")
    if out["source_files"] == 0:
        guards.append("no_blacklist_source: 找不到 U1–U4 的 user4_*.json（黑名单是空的）")
    if out["blacklist_strict"] == 0:
        guards.append("empty_blacklist: strict 黑名单为空（检查无意义）")

    out["guards_failed"] = guards
    out["status"] = "NOT_RUN" if guards else ("FAIL" if out["strict_hits"] else "PASS")
    out["scanned_files"] = [f.get("path") for f in out["files"]]
    # 落盘产物（与 redline_check.json 同款，便于复核者直接查）
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "blacklist_check.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if guards:
        print("\n结论：未执行（守卫触发）—— 不可据此声称「零泄漏」", file=sys.stderr)
        for g in guards:
            print("  - %s" % g, file=sys.stderr)
        sys.exit(2)
    if out["strict_hits"]:
        print("\n结论：strict 命中 ⇒ 存在泄漏", file=sys.stderr)
        sys.exit(1)
    print("\n结论：扫了 %d 个文件，strict 命中 0" % out["files_scanned"], file=sys.stderr)
    sys.exit(0)
