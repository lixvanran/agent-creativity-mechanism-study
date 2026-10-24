#!/usr/bin/env python3
"""★ **第四组交付包打包器（★ ★ 底层委托给第二组的 `pack_repo.py` ★）**

★ **★ 为什么是委托而不是各写一套（★ 2026-10-25 修正）★★**
★ ⇒ ⇒ ★ **★ 底层打包逻辑（zipfile + UTF-8 标志位 + 解压自检）★ ★【只有一份】★★**
★ ⇒ ⇒ ★ **★ 归第二组的 `creativity_lab/experiments/pack_repo.py` 所有 ★★（★ 它是"整目录打包 + 自检"的通用件）
★ ⇒ ⇒ ★ **★ 本文件只贡献第四组特有的东西：★ 【★ 分包规则 ★】+【★ 共享依赖白名单 ★】★★**
★ ⇒ ⇒ ★ **★ ⇒ 纪律：★「★ 动手写新东西前先找前人的实现」★ ★ ⇒ ★ 底层不重复造 ★★**

★ **★ 第四组特有的两条规则（★ 为什么不能直接用 pack_repo）★★**
★ ① **分包规则**：★ 用户要求「代码 / 论证文档 / 原始数据【分开打包】」⇒ ⇒ **三个包**（★ CODE / REPORT / DATA）
★ ② **共享依赖白名单**：★ 仓库是共享的（★ `creativity_lab/` 大部分是【第三组】的学习方向代码）
★ ⇒ ⇒ ★ **第四组的包不能把别人的代码整包带走**（★ 责任边界不清 + 体积虚胖）
★ ⇒ ⇒ ★ **但第四组的代码【依赖】三组的 gates/client** ⇒ ⇒ ★ **依赖项必须随包走**（★ 否则包跑不起来）

★ **★ 用法（★ 与旧版同参）★★**：
```bash
python3 -B group4_state_driven/pack_g4.py --out /workspace/第四组_代码包.zip --bucket CODE --self-test
```
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
PACKER = os.path.join(REPO, "creativity_lab", "experiments", "pack_repo.py")

# ★ ★ ★ 分包规则（★ ★ 写死，★ 第三方可机械复现 ★ ★）
CODE_EXT = (".py", ".sh", ".tex", ".lua")
REPORT_EXT = (".md", ".pdf")
G4_ROOT = "group4_state_driven"

# ★ ★ ★ 打包范围（★ ★ 显式白名单，★ 不打整个仓库 ★ ★）
SHARED_DEPS = [
    "creativity_lab/__init__.py",
    "creativity_lab/client.py",
    "creativity_lab/gates/__init__.py",
    "creativity_lab/gates/base.py",
    "creativity_lab/arms/__init__.py",
    "creativity_lab/arms/dual.py",
    "creativity_lab/state_layer.py",
    "creativity_lab/experiments/test_state_layer.py",
    "creativity_lab/experiments/apply_state_layer_rev3.py",
    "creativity_lab/experiments/pack_repo.py",
    "creativity_lab/experiments/unit_store.py",
    "creativity_lab/experiments/check_batch_progress.py",
]


def classify(rel: str) -> str:
    """★ 返回 'CODE' / 'REPORT' / 'DATA'（★ ★ 规则写死，★ 不靠临场判断 ★）"""
    if rel.startswith("group4_state_driven/data/"):
        if rel.endswith(".py"):
            return "CODE"          # ★ 版本归档（rev0/rev1/rev2）是【代码】
        return "DATA"              # ★ *.jsonl / *.json 是【原始数据与派生读数】
    if rel.endswith(".pdf"):
        return "REPORT"            # ★ 论文 PDF
    if rel.endswith(REPORT_EXT):
        return "REPORT"            # ★ *.md
    if rel.endswith(CODE_EXT):
        return "CODE"              # ★ *.py / *.sh / *.tex / *.lua
    return "DATA"                  # ★ 兜底 ⇒ ★ 宁进数据包也不丢


def collect(bucket: str) -> list:
    """★ 按规则挑文件（★ 相对仓根）"""
    out = []
    excl_dirs = {".git", "__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
    g4 = os.path.join(REPO, G4_ROOT)
    for root, dirs, files in os.walk(g4):
        dirs[:] = [d for d in dirs if d not in excl_dirs]
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                continue
            rel = os.path.relpath(os.path.join(root, f), REPO)
            if classify(rel) != bucket:
                continue
            out.append(rel)
    if bucket == "CODE":
        for dep in SHARED_DEPS:
            if os.path.exists(os.path.join(REPO, dep)):
                out.append(dep)
    return sorted(set(out))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--bucket", required=True, choices=["CODE", "REPORT", "DATA"])
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(PACKER):
        print("✘ 找不到底层打包器：%s" % PACKER)
        print("  ★ 它归第二组所有（★ `creativity_lab/experiments/pack_repo.py`）★")
        return 2

    files = collect(args.bucket)
    if not files:
        print("✘ 桶 %s 选不出任何文件" % args.bucket)
        return 2

    # ── ① 把挑出的文件镜像到临时目录（★ 保持相对路径）──
    tmpd = tempfile.mkdtemp(prefix="g4pack_")
    try:
        for rel in files:
            dst = os.path.join(tmpd, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(REPO, rel), dst)
        # ── ② 委托底层打包器（★ zip + 自检逻辑只有一份）──
        cmd = [sys.executable, "-B", PACKER, "--out", args.out,
               "--repo", tmpd, "--prefix", ""]
        p = subprocess.run(cmd, capture_output=True, text=True)
        out = (p.stdout or "") + (p.stderr or "")
        print(out.rstrip())
        if p.returncode != 0:
            print("✘ 底层打包器退出码 %d" % p.returncode)
            return p.returncode
        print("★ 桶=%s ｜ 选中 %d 个文件 ｜ 底层=第二组 pack_repo.py" % (args.bucket, len(files)))
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
