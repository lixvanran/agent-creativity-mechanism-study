#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pack_repo —— 全仓交付包打包器（★ 2026-10-25 新增）

★★★ **★ 为什么自己写而不用 `zip` 命令（★ 这是今天踩出来的硬坑）★★**
★ **★ 系统 `zip` 【不设】UTF-8 标志位（★ flag_bits |= 0x800）⇒ ⇒ ★ 中文文件名在解压端变成 mojibake**
★ ⇒ ⇒ ★ 实测：`zip -UN=UTF8` ★ ★ **也不管用**（★ flag_bits 仍是 0x0）
★ ⇒ ⇒ ★ ★★ **★ 后果（★ 比"文件名难看"严重得多）★★**
★ · 收件人解压后看到乱码文件名
★ · ★★ **★ `sha256sum -c SHA256SUMS.txt` 会因"文件不存在"【当场失败】⇒ ⇒ ★ ⇒ 通道 B 的核对链直接断** ★★
★ ⇒ ⇒ ★ **★ 所以：★ 打包器必须自己写，★ 且必须【自检解压端能还原原名】★★**

★ **★ Python 3 的 zipfile 对非 ASCII 文件名会【自动】设 UTF-8 标志位 ⇒ ⇒ ★ ⇒ 本工具用它**

★ 用法：
★   python3 -B creativity_lab/experiments/pack_repo.py --out /workspace/交付.zip --include-md a.md b.md
★   python3 -B creativity_lab/experiments/pack_repo.py --out x.zip --repo /workspace/lab --prefix creativity-lab
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile
from typing import List, Tuple

EXCLUDE_DIRS = {".git", "__pycache__", ".ipynb_checkpoints", ".pytest_cache", ".mypy_cache"}
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".so", ".o", ".a")


def collect_files(root: str, base: str = "") -> List[Tuple[str, str]]:
    """★ 返回 [(磁盘绝对路径, zip 内路径)]"""
    out: List[Tuple[str, str]] = []
    root = os.path.realpath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for fn in sorted(filenames):
            if fn.endswith(EXCLUDE_SUFFIX):
                continue
            ap = os.path.join(dirpath, fn)
            if not os.path.isfile(ap) or os.path.islink(ap):
                continue
            rel = os.path.relpath(ap, root)
            out.append((ap, os.path.join(base, rel) if base else rel))
    return out


def build(out_zip: str, repo: str, prefix: str, extra_md: List[str]) -> int:
    files = collect_files(repo, prefix)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for ap, arc in files:
            zi = zipfile.ZipInfo(arc, date_time=(2026, 10, 25, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            # ★★ 关键：★ 非 ASCII 文件名 ⇒ ★ Python 自动设 UTF-8 标志位（★ 显式写出来更保险）
            if not arc.isascii():
                zi.flag_bits |= 0x800
            zi.external_attr = 0o644 << 16
            with open(ap, "rb") as f:
                z.writestr(zi, f.read())
        for m in extra_md:
            if not os.path.isfile(m):
                print("  ⚠ 跳过（不存在）：%s" % m)
                continue
            arc = os.path.basename(m)
            zi = zipfile.ZipInfo(arc, date_time=(2026, 10, 25, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            if not arc.isascii():
                zi.flag_bits |= 0x800
            zi.external_attr = 0o644 << 16
            with open(m, "rb") as f:
                z.writestr(zi, f.read())
    return len(files)


def verify(out_zip: str, repo: str, prefix: str, extra_md: List[str]) -> bool:
    """★ ★ 自检：★ ① 解压端能还原原名 ② 内容 sha 一致 ③ 无 .git 混入"""
    ok = True
    with zipfile.ZipFile(out_zip) as z:
        names = z.namelist()
        # ① UTF-8 标志位
        bad_flag = [i.filename for i in z.infolist()
                    if not i.filename.isascii() and not (i.flag_bits & 0x800)]
        if bad_flag:
            print("  ✘ 非 ASCII 文件名未设 UTF-8 标志位：%s" % bad_flag[:5])
            ok = False
        else:
            n_nonascii = sum(1 for i in z.infolist() if not i.filename.isascii())
            print("  ✔ 非 ASCII 文件名 %d 个，★ 全部带 UTF-8 标志位" % n_nonascii)
        # ② .git
        if any(".git/" in n for n in names):
            print("  ✘ 包里混进了 .git")
            ok = False
        else:
            print("  ✔ 无 .git 混入")
        # ③ 内容 sha：★ 抽 5 个文件比对
        import random
        sample = [n for n in names if not n.endswith("/")][:200]
        random.seed(0)
        for n in random.sample(sample, min(5, len(sample))):
            disc = os.path.join(repo, os.path.relpath(n, prefix)) if n.startswith(prefix + "/") else None
            if disc is None or not os.path.isfile(disc):
                continue
            a = hashlib.sha256(z.read(n)).hexdigest()
            b = hashlib.sha256(open(disc, "rb").read()).hexdigest()
            if a != b:
                print("  ✘ 内容 sha 不符：%s" % n)
                ok = False
        print("  ✔ 抽样 5 个文件内容 sha 一致" if ok else "  ✘ 抽样内容比对有问题")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default="/workspace/lab")
    ap.add_argument("--prefix", default="creativity-lab")
    ap.add_argument("--include-md", nargs="*", default=[])
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()

    n = build(args.out, args.repo, args.prefix, args.include_md)
    size = os.path.getsize(args.out)
    sha = hashlib.sha256(open(args.out, "rb").read()).hexdigest()[:24]
    print("  打包：%s ｜ %d 文件 ｜ %d bytes ｜ sha256 %s" % (args.out, n, size, sha))
    if not args.no_verify:
        print("  ── 自检 ──")
        if not verify(args.out, args.repo, args.prefix, args.include_md):
            print("  ⇒ ✘ 自检未过")
            return 1
        print("  ⇒ ✔ 自检全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
