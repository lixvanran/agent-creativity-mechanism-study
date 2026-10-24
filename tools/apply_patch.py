#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
★ 【分段补丁应用器】—— ★ ★ **★ 解决一个我今天栽了三次的真问题 ★★** ★★
============================================================================

★ **★ 问题（★ 2026-10-24 一天内栽了三次）★★**
------------------------------------------------------------------------
★ 我改远端文件时，★ 习惯在【一个 heredoc 脚本里】连做多处替换 ★★
★ ⇒ ★ ★ 每处替换前都有 `assert old in s` ★★
★ ⇒ ★ ★ **★ 但【一个 assert 失败 ⇒ 整个脚本抛异常 ⇒ 后面所有段都没做、★ 且前面成功的也没写盘】★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 我实际损失过：★ ① `push_via_api.py` 的逐路径复核没落盘 ② 归属表的三级化没落盘 ③ 卫生自检的第④项没落盘 ★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 根因：★ 【多段替换写在一个脚本里 ⇒ 失败时【全盘放弃】】★★**

★ **★ 正确行为（★ 本工具实现）★★**
------------------------------------------------------------------------
★ **★ 每段独立：★ 定位 → 唯一性断言 → 替换 → 立即写盘 → 回读断言 ★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 某段失败时：★ 【前面成功的段【已落盘、保留】】★ + ★ 报【第几段失败】★ + ★ 退出码 3 ★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 这不是"容错"，★ 是【正确的失败语义】：★ 已经做对的事不该被后面的失败撤销 ★★**

★ **★ 用法 ★★
------------------------------------------------------------------------
★ 1) 写一个补丁描述文件（★ JSON）：
★    {
★      "patches": [
★        {"file": "tools/x.py", "old": "...", "new": "...",
★         "note": "★ 这次改什么"},
★        ...
★      ]
★    }
★ 2) `python3 -B tools/apply_patch.py patches.json`
★ ⇒ ⇒ ★ **★ 也支持 `--check`（★ 只校验不写盘）★★**

★ **★ 为什么它比"直接编辑"更可靠 ★★
------------------------------------------------------------------------
★ ① **★ 唯一性断言是强制的**（★ `old` 命中 0 次或 >1 次 ⇒ ⇒ 失败）★★
★ ② **★ 回读断言是强制的**（★ 写盘后重读，★ 确认 `new` 已在且 `old` 已不在）★★
★ ③ **★ 原子写**（★ 先写临时文件再 rename）⇒ ⇒ ★ ⇒ 写一半不会留坏文件 ★★
★ ④ **★ 失败不撤销已成功的段** ★★
★ ⑤ **★ 每段单独一行结果**（★ 人能一眼看出第几段出的问题）★★
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

__all__ = ["apply_patch", "apply_patches"]


class PatchError(Exception):
    """★ 某一段补丁失败（★ 定位 / 唯一性 / 回读）★。"""


def _atomic_write(path: str, text: str) -> None:
    """★ 原子写（★ 先临时文件再 rename）★ ⇒ ★ 写一半不会留坏文件。"""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".apply_patch.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def apply_patch(p: dict, *, check_only: bool = False) -> str:
    """★ 应用一段补丁；★ 返回一行结果文本。★ 失败抛 `PatchError`。"""
    path = p["file"]
    old = p["old"]
    new = p.get("new", "")
    note = p.get("note", "")

    if not os.path.exists(path):
        raise PatchError("文件不存在：★ %s" % path)
    with open(path, encoding="utf-8") as f:
        src = f.read()

    n = src.count(old)
    if n == 0:
        raise PatchError("★ 锚点未命中（★ 0 次）：★ %s" % path)
    if n > 1:
        raise PatchError("★ 锚点不唯一（★ %d 次）：★ %s" % (n, path))

    out = src.replace(old, new, 1)

    # ★ ★ 写盘前语法检查（★ .py 文件）：★ 改坏语法就别写了 ★★
    if path.endswith(".py"):
        import ast
        try:
            ast.parse(out)
        except SyntaxError as e:
            raise PatchError("★ 改后语法错误（★ %s L%s）：★ %s" % (path, e.lineno, e.msg))

    if not check_only:
        _atomic_write(path, out)
        # ★ ★ 回读断言：★ 确认真的落盘了 ★★
        with open(path, encoding="utf-8") as f:
            back = f.read()
        if back != out:
            raise PatchError("★ 回读不一致（★ 写盘后内容与预期不同）：★ %s" % path)
        if new and new not in back:
            raise PatchError("★ 回读断言失败（★ 新内容不在文件里）：★ %s" % path)
        # ★ ★ ★ 【★ 不要用「old 不在文件里」当断言 ★】★★
        # ★ ★ ⇒ ★ 当 new 【包含】old（★ 例：★ old="AAA" ⇒ new="AAA2"）⇒ ⇒ ★ ⇒
        # ★ ★ ⇒ ★ 旧内容【必然还在】（★ 作为新内容的一部分）⇒ ⇒ ★ ⇒ 那样判会【假失败】★★
        # ★ ★ ⇒ ★ ⇒ 所以唯一可靠的判据是上面的【整份内容 == out】★★

    return "  ✔ %s  ★ %s%s" % (path, note, ("（★ 仅校验）" if check_only else ""))


def apply_patches(patches: list, *, check_only: bool = False) -> int:
    """★ 逐段独立应用。★ 返回退出码：★ 0 = 全过；★ 3 = 有段失败。"""
    ok = 0
    failed = []
    for i, p in enumerate(patches, 1):
        note = p.get("note", "")
        try:
            print(apply_patch(p, check_only=check_only))
            ok += 1
        except PatchError as e:
            print("  ✘ 第 %d 段失败：★ %s" % (i, e))
            failed.append((i, note, str(e)))
            # ★ ★ ★ 关键：★ 不中断！★ 后面几段继续试（★ 各自独立）★★
        except Exception as e:
            print("  ✘ 第 %d 段异常：★ %s: %s" % (i, type(e).__name__, e))
            failed.append((i, note, "%s: %s" % (type(e).__name__, e)))
    print()
    if failed:
        print("✘ 补丁：★ %d 段成功、★ %d 段失败（★ ★ **★ 成功的段【已落盘、保留】★★ ★）"
              % (ok, len(failed)))
        for i, note, msg in failed:
            print("   - 第 %d 段（★ %s）：★ %s" % (i, note, msg))
        return 3
    print("✔ 补丁：★ %d 段全部成功" % ok)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="★ 分段独立补丁应用器（★ 失败不撤销已成功的段）★")
    ap.add_argument("spec", help="★ 补丁描述 JSON 文件")
    ap.add_argument("--check", action="store_true", help="★ 只校验不写盘")
    a = ap.parse_args()
    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    return apply_patches(spec.get("patches", []), check_only=a.check)


if __name__ == "__main__":
    raise SystemExit(main())
