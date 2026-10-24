#!/usr/bin/env python3
"""★ **第四组交付包打包器（★ ★ 非 ASCII 文件名安全 ★）**

★ **★ 为什么必须自己写（★ 不等第二组的 `pack_repo.py`）★★**
★ ★ 系统 `zip` 命令【不设 UTF-8 标志位】（★ `flag_bits` 保持 `0x0`）
★ ⇒ ⇒ ★ **中文文件名在解压端变成 mojibake**
★ ⇒ ⇒ ★ **★ 后果比"文件名难看"严重得多：★ `sha256sum -c SHA256SUMS.txt` 会因
★ ⇒ ⇒ ★ ★ 【文件不存在】当场失败 ⇒ ⇒ ★ ⇒ 核对链直接断**
★ ⇒ ⇒ ★ ★ `zip -UN=UTF8`【也不管用】（★ 第二组实测：★ `flag_bits` 仍是 `0x0`）

★ **★ 正解**：★ 用 Python `zipfile`（★ Python 3 对非 ASCII 名【自动】设 `flag_bits |= 0x800`）
★ ⇒ ⇒ ★ ⇒ 解压端能还原原名 ⇒ ⇒ ★ ⇒ `sha256sum -c` 链不断

★ **★ 四道自检（★ 打包完当场跑，★ 跑不过就不算交付）★★**：
★ ① **非 ASCII 名全部带 UTF-8 标志位**（★ 逐个查 `flag_bits`）
★ ② **解压端能还原原名**（★ ★ 真的解压一遍，★ 用 `ls -b` 等价方式比对）
★ ③ **抽样内容 sha 一致**（★ 解压后的字节 vs 源文件字节）
★ ④ **查 `.git` 混入**（★ 打包源码仓时最常见的坑）

★ **用法**：
```bash
python3 -B group4_state_driven/pack_g4.py --out /workspace/第四组交付包.zip
python3 -B group4_state_driven/pack_g4.py --out /workspace/x.zip --self-test
```
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ★ ★ ★ 分包规则（★ ★ 写死，★ 第三方可机械复现 ★ ★）
# ★ ★ 依据：★ 用户要求「代码 / 论证文档 / 原始数据【分开打包】」⇒ ⇒ ★ 三包
CODE_EXT = (".py", ".sh", ".tex", ".lua")
REPORT_EXT = (".md", ".pdf")


def classify(rel: str) -> str:
    """★ 返回 'CODE' / 'REPORT' / 'DATA'（★ ★ 规则写死，★ 不靠临场判断 ★）"""
    if rel.startswith("group4_state_driven/data/"):
        if rel.endswith(".py"):
            return "CODE"          # ★ 版本归档（rev0/rev1）是【代码】
        return "DATA"              # ★ *.jsonl / *.json 是【原始数据与派生读数】
    if rel.endswith(".pdf"):
        return "REPORT"            # ★ 论文 PDF
    if rel.endswith(REPORT_EXT):
        return "REPORT"            # ★ *.md
    if rel.endswith(CODE_EXT):
        return "CODE"              # ★ *.py / *.sh / *.tex / *.lua
    return "DATA"                  # ★ 兜底 ⇒ ★ 宁进数据包也不丢


# ★ ★ ★ 打包范围（★ ★ 显式白名单，★ 不打整个仓库 ★ ★）
# ★ ★ 理由：★ 仓库是共享的（★ `creativity_lab/` 大部分是【第三组】的学习方向代码）
# ★ ⇒ ⇒ ★ **第四组的交付包不能把别人的代码整包带走**（★ ⇒ ⇒ ★ 责任边界不清 + 体积虚胖）
# ★ ⇒ ⇒ ★ 但第四组的代码【依赖】三组的 gates/client ⇒ ⇒ ★ **依赖项必须随包走**（★ 否则包跑不起来）
SHARED_DEPS = [
    "creativity_lab/__init__.py",
    "creativity_lab/client.py",
    "creativity_lab/gates/__init__.py",
    "creativity_lab/gates/base.py",
    "creativity_lab/arms/__init__.py",
    "creativity_lab/arms/dual.py",
    "creativity_lab/state_layer.py",
    "creativity_lab/experiments/test_state_layer.py",
]
G4_ROOT = "group4_state_driven"


def collect(repo: str, bucket: str = None) -> list:
    """★ 收集要打包的文件（★ 显式白名单 + 排除 .git / __pycache__ / .pyc）"""
    out = []
    excl_dirs = {".git", "__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
    for root, dirs, files in os.walk(os.path.join(repo, G4_ROOT)):
        dirs[:] = [d for d in dirs if d not in excl_dirs]
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                continue
            rel = os.path.relpath(os.path.join(root, f), repo)
            if bucket is not None and classify(rel) != bucket:
                continue
            out.append(rel)
    # ★ 共享依赖项（★ ★ 全部归 CODE 桶：★ 它们是【可执行代码】★★）
    if bucket in (None, "CODE"):
        for dep in SHARED_DEPS:
            if os.path.exists(os.path.join(repo, dep)):
                out.append(dep)
    return sorted(set(out))


def build(repo: str, out: str, arc_prefix: str = "", bucket: str = None) -> list:
    """★ 用 zipfile 打包（★ ★ 非 ASCII 名自动带 0x800 标志位 ★）"""
    files = collect(repo, bucket)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    tmp = out + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            arc = os.path.join(arc_prefix, rel) if arc_prefix else rel
            z.write(os.path.join(repo, rel), arc)
    os.replace(tmp, out)
    return files


def self_test(out: str, repo: str, arc_prefix: str = "") -> int:
    """★ ★ 四道自检 ★"""
    ok = True
    print("=" * 74)
    print("★ 打包自检：%s" % out)
    print("=" * 74)

    with zipfile.ZipFile(out) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]

        # ── ① 非 ASCII 名必须带 UTF-8 标志位 ──
        bad_flag = [i.filename for i in infos
                    if any(ord(c) > 127 for c in i.filename) and not (i.flag_bits & 0x800)]
        n_non_ascii = sum(1 for i in infos if any(ord(c) > 127 for c in i.filename))
        print("① 非 ASCII 文件名 %d 个，%s" % (
            n_non_ascii, "全部带 UTF-8 标志位 ✔" if not bad_flag else "✘ 缺标志位：%r" % bad_flag))
        ok = ok and not bad_flag

        # ── ④ .git 混入 ──
        git_leak = [n for n in names if ".git/" in n or n.endswith("/.git")]
        print("④ .git 混入：%s" % ("无 ✔" if not git_leak else "✘ %r" % git_leak[:5]))
        ok = ok and not git_leak

        # ── ② 解压端能还原原名 + ③ 抽样内容 sha 一致 ──
        tmpd = tempfile.mkdtemp(prefix="g4unpack_")
        try:
            z.extractall(tmpd)
            # 解压后清单必须与压缩包清单逐名一致
            got = []
            for root, dirs, fs in os.walk(tmpd):
                for f in fs:
                    got.append(os.path.relpath(os.path.join(root, f), tmpd))
            got_set = set(got)
            missing = [n for n in names if n not in got_set]
            print("② 解压后文件名还原：%s" % (
                "全部一致 ✔" if not missing else "✘ 丢失/乱码 %r" % missing[:5]))
            ok = ok and not missing

            # 抽样 8 个文件做内容 sha 比对
            sample = names[:: max(1, len(names) // 8)][:8]
            mismatch = []
            for n in sample:
                src = os.path.join(repo, os.path.relpath(n, arc_prefix) if arc_prefix else n)
                if not os.path.exists(src):
                    mismatch.append((n, "源文件不存在（★ bucket 打包时路径推导可能错）"))
                    continue
                dst = os.path.join(tmpd, n)
                if not os.path.exists(src):
                    mismatch.append((n, "源文件不存在"))
                elif sha256_file(src) != sha256_file(dst):
                    mismatch.append((n, "内容 sha 不一致"))
            print("③ 抽样 %d 个文件内容 sha：%s" % (
                len(sample), "全部一致 ✔" if not mismatch else "✘ %r" % mismatch))
            ok = ok and not mismatch
        finally:
            shutil.rmtree(tmpd, ignore_errors=True)

    print("─" * 74)
    print("★ 包：%s" % out)
    print("★ 字节：%d" % os.path.getsize(out))
    print("★ 文件数：%d" % len(names))
    print("★ 包 sha256：%s" % sha256_file(out))
    print("★ 自检：%s" % ("★ 全部通过 ✔" if ok else "★ ★ 有失败项 ✘"))
    print("=" * 74)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--arc-prefix", default="")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--bucket", default=None,
                    choices=[None, "CODE", "REPORT", "DATA"],
                    help="★ 只打某一类（★ None = 全部）")
    args = ap.parse_args()

    files = build(args.repo, args.out, args.arc_prefix, args.bucket)
    print("✔ 已打包 %d 个文件 ⇒ %s" % (len(files), args.out))
    if args.self_test:
        return self_test(args.out, args.repo, args.arc_prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
