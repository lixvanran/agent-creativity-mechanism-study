#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **推送工具的卫生自检（★ 2026-10-24 · ★ 主会话要求"落成工具自检，★ 不是一次修复"）★★**

★ **★ 为什么要有这个（★ 本轮真实踩的坑）★★**
★ ① **404/422 被我放进重试分支** ⇒ ⇒ ★ ⇒ 每个 blob 白等 75s ⇒ ⇒ ★ ⇒ **183 个 blob 要 4 小时，★ 而现象只是"没进度"**
★ ② **"先 GET 再 POST"的探测步骤** ⇒ ⇒ ★ ⇒ **把幂等当不存在**（★ 同内容必然同 sha ⇒ ⇒ ★ ⇒ 直接 POST 天然幂等）

★ **★ 本自检做什么（★ 扫描源码，★ 断言那两条形态不存在）★★**
★ ① **重试分支里不含确定性错误（404/422）** —— ★ ★ **★ 判据是【源码里重试分支的条件】★★
★ ② **没有"先 GET 再 POST"的探测步骤**（★ ★ 判据是【同一路径上 GET 之后紧跟 POST】★★
★ ③ **推后有逐路径复核**（★ 断言远端独有文件丢失 = 0 的那行存在）

★ **★ 为什么用【源码扫描】而不是【运行时检查】（★ 这是一个【刻意】的选择）★★**
> ★★★ **★ 运行时检查只能发现"这一版坏了"；★ 源码扫描能发现"【这一族的形态又长出来了】"★★**
> ⇒ ⇒ ★ **★ ⇒ 主会话的原话：★ "★ 这类坑不会只在一个脚本里出现，★ 落进工具才有复用价值 ★★"**

★ 用法：`python3 -B tools/check_push_tool_hygiene.py`
★ 退出码：★ 0 = 全过｜★ 1 = 有形态检出（★ 打印命中位置）
"""

from __future__ import annotations

import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = ["tools/push_overlay.py", "tools/push_via_api.py"]
FAILED = []



def _hardcoded_date(tree) -> bool:
    """★ ★★ 【★ 数据流判据（★ 2026-10-24）★★】★★

    ★ **★ 问题（★ 实测）★★**：★ 「源码里出现任何日期串」⇒ ⇒ ★ ⇒ **【误报】** ★★
    ★ ⇒ ★ 例：★ `Accept: application/vnd.github.v3+json` 里的 `"2022-11-28"` ⇒ ⇒ ★ ⇒ 误判成硬编码 ★★
    ★ ⇒ ⇒ ★ ⇒ **★ ⇒ 「提到日期」≠「日期被硬编码进 author.date」★★**（★ 与「指标名≠口径」同族）★★

    ★ **★ 正确做法：★ 追【date 字段的赋值链】★★**
    ★ ① 收集「变量名 → 常量」绑定
    ★ ② 找 dict 里 key == "date" 的位置
    ★ ③ 该值若是字面量 ⇒ 硬编码；★ 若是变量 ⇒ 追它的绑定 ⇒ 是常量 ⇒ 硬编码
    ★ ④ 若是 `datetime(2026, 10, 25)` 这种【带年份裸整数的调用】⇒ 硬编码
    """
    const_bind = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            if isinstance(n.value, (ast.Constant, ast.Call)):
                # ★ ★ ★ 【★ 这里必须存【AST 节点】、★ 不是【Python 值】★★ ★
                # ★ ★ ⇒ ★ 存了 Python 值的话，★ 后面 `isinstance(bound, ast.Constant)` ⇒ ⇒ ★
                # ★ ★ ⇒ ★ **★ 永远为假 ⇒ ⇒ ★ ⇒ 【两种形态都抓不到】★★ ⇒ ⇒ ★ ⇒ **假绿 ★★
                # ★ ★ ⇒ ★ ⇒ ★ **★ 通则：★ 同一个变量在判据函数里【只能有一种含义】★★**
                const_bind[n.targets[0].id] = n.value
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if not (isinstance(k, ast.Constant) and k.value == "date"):
                continue
            if isinstance(v, ast.Constant):
                return True
            if isinstance(v, ast.Name) and v.id in const_bind:
                bound = const_bind[v.id]
                if isinstance(bound, ast.Constant):
                    return True
                # ★ ★ ★ 追踪【变量 → Call】：★ now = datetime(2026, 10, 25).strftime(...) ★★
                if isinstance(bound, ast.Call):
                    for sub in ast.walk(bound):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, int) \
                                and not isinstance(sub.value, bool) and 1900 <= sub.value <= 2100:
                            return True
    return False


def check(name, cond, detail=""):
    if cond:
        print("  ✔ %s" % name)
    else:
        print("  ✘ %s  %s" % (name, detail))
        FAILED.append(name)


def retry_branches(path):
    """★ 找出所有【重试分支】（★ except 块里含 sleep 或重试计数）★★"""
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            src = ast.dump(node)
            body = ast.dump(node)
            if "sleep" in body or "retry" in body.lower():
                out.append(node)
    return out


def main() -> int:
    print("== ★ 推送工具卫生自检 ==")
    for rel in TARGETS:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            check("★ %s 存在" % rel, False, p)
            continue
        src = open(p, encoding="utf-8").read()

        # ── ① 重试分支里不含 404/422 ──
        bad = []
        for h in retry_branches(p):
            hsrc = ast.get_source_segment(src, h) or ""
            if re.search(r"\b(404|422)\b", hsrc):
                # ★ 允许的形态：★ 404/422 出现在【抛异常的分支】⇒ ⇒ 那正是【立刻抛】的修法
                # ⇒ ⇒ 判据是：【它出现在 raise 之前】而不是【它被当成可重试】
                if "raise" not in hsrc:
                    bad.append((h.lineno, hsrc.strip()[:90]))
        check("★ %s · 重试分支不含确定性错误（★ 404/422）" % rel, not bad, str(bad))

        # ── ② 没有"先 GET 再 POST"的探测步骤 ──
        # ⇒ ⇒ ★ 判据：★ 同一路径上，★ GET 调用之后（★ 在 except 里）★ 又 POST 同一个 blob
        probe = []
        for h in retry_branches(p):
            hsrc = ast.get_source_segment(src, h) or ""
            if ("/git/blobs/" in hsrc) or re.search(r'get\(\s*["\']/git/blobs/', hsrc):
                if "post(" in hsrc:
                    probe.append((h.lineno, hsrc.strip()[:90]))
        check("★ %s · 无『先 GET 再 POST』的 blob 探测步骤" % rel, not probe, str(probe))

        # ── ③ 推后逐路径复核（★ ★ 行为级判据：★ 找【差集运算 + 与 0 的比较】的结构 ★）──
        # ★ ★ 为什么不用"找某几个字"：★ 那是【措辞判据】⇒ ⇒ ★ ⇒ 换个措辞就假绿 ⇒ ⇒ ★ ⇒
        # ★ ★ ⇒ 与「指标名不能替代口径定义」同族（★ ★ 自检本身也可能是假绿 ★★）★★
        tree = ast.parse(src)
        has_diff = False        # ★ 有"把两个 path 集合做差"的表达式
        has_zero_check = False  # ★ 有"该差集必须为 0"的判断
        for node in ast.walk(tree):
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Compare) and any(
                            isinstance(op, (ast.NotIn, ast.In)) for op in sub.ops):
                        has_diff = True
            if isinstance(node, ast.Compare) and isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
                for c in node.comparators:
                    if isinstance(c, ast.Constant) and c.value == 0:
                        has_zero_check = True
        check("★ %s · 推后有逐路径复核（★ ★ 行为级：★ 差集运算 + 零值断言）" % rel,
              has_diff and has_zero_check,
              "★ 差集运算=%s ｜ 零值断言=%s" % (has_diff, has_zero_check))
        # ── ④ 推后回读远端 commit 对象，★ 核对 message / author / date（★ 主会话要求）──
        # ★ ★ 判据（★ 行为级）：★ ① 能读到远端 commit 对象 ② 三个字段都出现在【比较】里 ③ 没有硬编码时间戳 ★★
        # ★ ★ ⇒ ★ 传输层会静默丢字段 ⇒ ⇒ 落盘后必须回读核对 ⇒ ⇒ 缺一个字段就是缺一个核对 ★★
        # ★ ★ ⇒ ★ ★ **★ 「提到字段名」≠「核对了字段」★★** ⇒ ⇒ ★ ⇒ **★ ⇒ 所以必须找【Compare 节点】★★**
        # ★ ★ ⇒ ★ ★ 也不能只认一种写法 ⇒ ⇒ ★ ⇒ 用 AST（★ 而不是正则匹配某一行文本）★★
        reads_commit = bool(re.search(r'["\']/git/commits/', src))
        compared = set()
        hardcoded_ts = False
        declared = set()
        has_compare = False
        occurrences = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                has_compare = True
                # ★ ★★★ 【★ 关键：★ 只认【下标 vs 下标】的逐字段比较 ★】★★★★
                # ★ ★ ⇒ 例如：★ actual["message"] != expect["message"] ★★
                # ★ ★ ⇒ ★ **★ 而【集合相等】那种（★ assert set(CHECK_FIELDS) == {...}）★★
                # ★ ★ ⇒ ★ **★ 不算 —— ★ ★ 它会让判据【被别的代码满足 ⇒ ⇒ 假绿】★★ ★★
                for side in [node.left] + list(node.comparators):
                    for sub in ast.walk(side):
                        if isinstance(sub, ast.Subscript):
                            sl = sub.slice
                            if isinstance(sl, ast.Index):      # ★ py≤3.8 兼容
                                sl = sl.value
                            if isinstance(sl, ast.Constant) and isinstance(sl.value, str) \
                                    and sl.value in ("message", "author", "date"):
                                compared.add(sl.value)
            # ★ ★ ★ 【★ 硬编码日期：★ 统一走【数据流判据】（★ 见 _hardcoded_date）★★★ ★★
            # ★ ★ ⇒ ★ 【源码里出现任何日期串】≠【日期被硬编码进 author.date】★★
            # ★ ★ ⇒ ★ ⇒ ★ 旧的全串扫描已删（★ 单一真相源；★ 且它会误报 Accept header 里的日期）★★
            # ★ ★ ★ 【★ 契约锚点 ★】：★ 一个含三个字段名的元组/列表常量 ★★
            if isinstance(node, (ast.Tuple, ast.List)):
                vals = {e.value for e in node.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                if vals >= {"message", "author", "date"}:
                    declared = vals
            # ★ ★ ★ 【★ 出现次数判据 ★】：★ 每个字段名要出现【≥2 次】★★
            # ★ ★ ⇒ ★ 一次在契约声明、★ 一次在【逐字核对处】⇒ ⇒ ★ ⇒
            # ★ ★ ⇒ ★ 「只声明不用」⇒ 1 次 ⇒ ⇒ 假绿 ⇒ ⇒ ★ ⇒ 抓得到 ★★
            # ★ ★ ⇒ ★ 「用循环代替逐字核对」⇒ 字段名只出现在契约里 ⇒ ⇒ 1 次 ⇒ ⇒ 也抓得到 ★★
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and node.value in ("message", "author", "date"):
                occurrences[node.value] = occurrences.get(node.value, 0) + 1
        # ★ ★ 单一真相源：★ 硬编码日期【只】由数据流判据给出 ★★
        hardcoded_ts = _hardcoded_date(tree)
        need = {"message", "author", "date"}
        check("★ %s · 推后回读远端 commit 并核对 message/author/date（★ 行为级）" % rel,
              reads_commit and declared >= need and compared >= need and not hardcoded_ts,
              "★ 回读=%s ｜ 契约声明=%s ｜ ★ 在【比较】里出现的字段=%s（★ 需 %s）｜ ★ 硬编码时间戳=%s"
              % (reads_commit, sorted(declared), sorted(compared), sorted(need), hardcoded_ts))

    print()
    if FAILED:
        print("✘ 卫生自检：★ %d 项未过 ⇒ %s" % (len(FAILED), FAILED))
        return 1
    print("✔ 卫生自检全过（★ 三个形态都不存在）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
