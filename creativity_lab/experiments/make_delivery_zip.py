#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 交付包一键打包（★ 可复现 ★）—— ★ 底层 zip 委托 `pack_repo.py` ★

★ ★★ 为什么要有这个 wrapper（★ 2026-10-24 实测逼出来的 ★）★★
★ `pack_repo.py` 本身是对的（★ UTF-8 标志位、★ 全量清单核对 ★），★ 但它有两个缺口：
★ ① **它走的是【文件系统】不是【版本管理的文件集】** ⇒ ★ `.tmp/`、`.mavis/` 这类
★    未受管的临时物会混进包（★ 实测：1430 个文件里 266 个是 `.tmp/` 下的 ★）
★ ② **它没有清单时退回【抽样 5 个】** ⇒ ★ 抽样量不够 ⇒ ★ 抓不到「清单过期」
★ ⇒ ★ ⇒ ★ **本 wrapper 补上这两点：★ ① 用 `git ls-files -z` 取受管文件 ★
★ ② 总是自己生成 `SHA256SUMS.txt`（★ 路径用包内 arcname ★）⇒ ★ 打包器走全量核对 ★

★ ★★ 另加一道【打包器自己没查的】检查 ★★
★ `pack_repo.py` 只查「**清单里的**在包内」，★ **不查「包内的都在清单里」** ★
★ ⇒ ★ 本 wrapper 补上：★ **双向差集都必须为空**（★ 清单自身除外 ★）★

★ ★★ 步骤（★ 全部可复现 ★）★★
| 步 | 做什么 |
|:-:|---|
| ① | `git ls-files -z` ⇒ 受管文件清单（★ 必须加 `-z` ★）★ |
| ② | 拷到**仓外**暂存目录（★ 输出目录 ≠ 输入目录 ★）★ |
| ③ | 生成 `SHA256SUMS.txt`（★ 放仓外 ★）★ |
| ④ | 调 `pack_repo.py`（★ 它做 UTF-8 标志位 + 全量清单核对 ★）★ |
| ⑤ | ★ 本 wrapper 自己再核：★ 双向差集 + 独立全量重算 sha256 ★ |

用法：
    python3 -B creativity_lab/experiments/make_delivery_zip.py \
        --repo /workspace/lab --out /workspace/第二组交付包_2026-10-24.zip \
        --prefix 第二组交付_2026-10-24
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(HERE, "pack_repo.py")
EXCLUDE_DIRS = {".git", "__pycache__", ".ipynb_checkpoints", ".pytest_cache", ".mypy_cache"}
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".so", ".o", ".a")


def die(msg):
    print("✘ %s" % msg)
    sys.exit(1)


def git_ls_files(repo):
    """★ `git ls-files -z`（★ 必须加 `-z` ★）⇒ ★ 路径里的特殊字符不会串行。★"""
    r = subprocess.run(["git", "-C", repo, "ls-files", "-z"],
                       capture_output=True)
    if r.returncode != 0:
        die("git ls-files 失败：%s" % r.stderr.decode("utf-8", "replace")[:500])
    out = []
    for b in r.stdout.split(b"\x00"):
        if not b:
            continue
        out.append(b.decode("utf-8"))
    return out


def stage(repo, files, dst):
    n = 0
    for rel in files:
        src = os.path.join(repo, rel)
        if not os.path.isfile(src):
            continue
        d = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(src, d)
        n += 1
    return n


def collect(stage_dir, prefix):
    out = []
    for dp, dn, fn in os.walk(stage_dir):
        dn[:] = sorted(d for d in dn if d not in EXCLUDE_DIRS)
        for f in sorted(fn):
            if f.endswith(EXCLUDE_SUFFIX):
                continue
            ap = os.path.join(dp, f)
            if os.path.islink(ap) or not os.path.isfile(ap):
                continue
            rel = os.path.relpath(ap, stage_dir)
            out.append((ap, os.path.join(prefix, rel)))
    out.sort(key=lambda x: x[1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--keep-stage", action="store_true")
    a = ap.parse_args()

    repo = os.path.abspath(a.repo)
    out_zip = os.path.abspath(a.out)
    if os.path.commonpath([repo, out_zip]) == repo:
        die("★ 输出 zip 不能放在仓内（★ 会被打包器自己收进去 ★）：%s" % out_zip)

    files = git_ls_files(repo)
    print("① 受管文件（git ls-files -z）：%d" % len(files))

    tmp = tempfile.mkdtemp(prefix="pack_")
    try:
        stage_dir = os.path.join(tmp, "stage")
        os.makedirs(stage_dir)
        n = stage(repo, files, stage_dir)
        print("② 暂存到【仓外】：%d 个（★ 输出目录 ≠ 输入目录 ★）" % n)

        members = collect(stage_dir, a.prefix)
        sums_path = os.path.join(tmp, "SHA256SUMS.txt")
        lines = []
        for ap, arc in members:
            h = hashlib.sha256(open(ap, "rb").read()).hexdigest()
            lines.append("%s  %s" % (h, arc))
        open(sums_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print("③ 生成 SHA256SUMS.txt：%d 条（★ 放仓外，★ 用 --include-md 放进包根 ★）" % len(lines))

        r = subprocess.run([sys.executable, "-B", PACK, "--out", out_zip,
                            "--repo", stage_dir, "--prefix", a.prefix,
                            "--include-md", sums_path], capture_output=True, text=True)
        print(r.stdout.rstrip())
        if r.returncode != 0:
            die("pack_repo.py 失败（exit %d）：\n%s" % (r.returncode, r.stderr[-1500:]))

        # ★ ⑤ 本 wrapper 自己再核（★ 打包器没查的方向 ★）
        print("④ ★ 本 wrapper 独立复核（★ 打包器只查『清单→包内』，★ 不查『包内→清单』★）")
        with zipfile.ZipFile(out_zip) as z:
            names = set(n for n in z.namelist() if not n.endswith("/"))
            entries = {}
            for ln in z.read("SHA256SUMS.txt").decode("utf-8").splitlines():
                m = re.match(r"^([0-9a-f]{64})\s+\*?(.+)$", ln.strip())
                if m:
                    entries[m.group(2)] = m.group(1)
            missing = sorted(names - set(entries) - {"SHA256SUMS.txt"})
            extra = sorted(set(entries) - names)
            if missing:
                die("★ 在包里但不在清单里：%d 个（★ 例：%s ★）" % (len(missing), missing[:3]))
            if extra:
                die("★ 在清单里但不在包里：%d 个（★ 例：%s ★）" % (len(extra), extra[:3]))
            bad = 0
            for arc, want in entries.items():
                got = hashlib.sha256(z.read(arc)).hexdigest()
                if got != want:
                    bad += 1
            if bad:
                die("★ 独立全量重算 sha256：%d 条不符 ★" % bad)
            n_zip = len(names)
            n_sum = len(entries)
        print("   ✔ 包内成员 %d ｜ 清单 %d 条 ｜ 双向差集 0 ｜ 独立全量重算 0 条不符" % (n_zip, n_sum))

        sha = hashlib.sha256(open(out_zip, "rb").read()).hexdigest()
        size = os.path.getsize(out_zip)
        print("⑤ ✔ 打包完成：%s ｜ %d 字节 ｜ sha256 %s" % (out_zip, size, sha))
        print(json.dumps({"zip": out_zip, "bytes": size, "sha256": sha,
                          "n_members": n_zip, "n_manifest": n_sum},
                         ensure_ascii=False))
    finally:
        if a.keep_stage:
            print("（暂存区保留：%s）" % tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
