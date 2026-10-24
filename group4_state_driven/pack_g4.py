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
import hashlib
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

# ★ ★ ★ 【可独立复验清单】（★ 2026-10-25 修：★ 跨桶依赖）★★
# ★ 起因：★ 校验器是 .py ⇒ 归 CODE 桶；★ 它读的 analysis.json 归 DATA 桶
#   ⇒ ⇒ ★ 【CODE 桶有校验器没数据、★ DATA 桶有数据没校验器】★ ⇒ ⇒ **两边都跑不起来** ★★
# ★ ⇒ ⇒ ★ 修法：★ 让 DATA 桶【带上校验器 + 它要校验的那几个数据文件】★★
#   ⇒ ⇒ ★ **DATA 包解压后能独立自证"我的读数就是这些样本算出来的"** ★★
VERIFIERS = [
    "group4_state_driven/verify_report_stage1.py",
    "group4_state_driven/verify_archive.py",
    "group4_state_driven/check_independent_samples.py",
    "group4_state_driven/code/analyze_gate_semantics.py",
]
# ★ ★ 校验器依赖的数据（★ 缺任何一个 ⇒ 校验器跑不动）★★
VERIFIER_DATA = [
    "group4_state_driven/data/arch6_stage1.jsonl",
    "group4_state_driven/data/arch6_stage1_analysis.json",
    "group4_state_driven/data/arch6_gate_semantics.json",
    "group4_state_driven/data/duplicate_resampling.json",
    "group4_state_driven/SHASUMS.md",          # ★ 归档校验器要读它（★ 缺了就报「找不到」）
    "group4_state_driven/REPORT_arch6_stage1.md",   # ★ ★ 校验器的【被测对象】★ ★
    #   ★ 缺了它 ⇒ 校验器只跑 12 项全局检查（★ 55 项 per-report 全跳过）⇒ ⇒ ★ 读数不可比 ★★
    "group4_state_driven/archive/MANIFEST.sha256",
]


def classify(rel: str) -> str:
    """★ 返回 'CODE' / 'REPORT' / 'DATA'（★ ★ 规则写死，★ 不靠临场判断 ★）"""
    # ★ ★ ★ 归档是【一个整体】★★（★ 2026-10-25 修）
    # ★ 起因：★ 原来按扩展名分 ⇒ archive/runs/*.md 归 REPORT、*.jsonl 归 DATA、*.py 归 CODE
    #   ⇒ ⇒ ★ 归档被拆散在三个桶里 ⇒ ⇒ ★ 它的 MANIFEST 要求成员同在
    #   ⇒ ⇒ ★ 清单在任何单桶里都对不上 ⇒ ⇒ ★ verify_archive.py 报 3 项失败
    # ★ ⇒ ⇒ ★ 修法：★ archive/ 下的所有文件一律进 DATA 桶（★ 归档是数据资产）
    if rel.startswith("group4_state_driven/archive/"):
        return "DATA"
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
    if bucket == "DATA":
        # ★ ★ DATA 包必须【能独立自证】★★（★ 校验器 + 它要校验的数据 同桶）
        for dep in VERIFIERS + VERIFIER_DATA:
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
        # ── ② 生成 SHA256SUMS.txt（★ ★ 2026-10-25 加）★★
        #   ★ 理由：★ 底层 pack_repo.py 的自检【有清单才走全量核对】，★ 没有清单就退回抽样 5 个
        #   ⇒ ⇒ ★ 所以【清单必须由本层生成】★ ⇒ ⇒ ★ 清单与包内容【同批】算 ⇒ ⇒ ★ 不会"清单过期"
        #   ★ 依据：★ 「清单过期」是必然存在的一类坏 ⇒ ⇒ ★ 抽样会漏抓 ⇒ ⇒ 清单类必须全量
        _sums = []
        for rel in sorted(files):
            _p = os.path.join(tmpd, rel)
            if os.path.isfile(_p):
                _sums.append("%s  %s" % (hashlib.sha256(open(_p, "rb").read()).hexdigest(), rel))
        with open(os.path.join(tmpd, "SHA256SUMS.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(_sums) + "\n")
        print("★ 已生成 SHA256SUMS.txt（%d 条，★ 与包内容同批）" % len(_sums))
        # ── ③ 委托底层打包器（★ zip + 自检逻辑只有一份）──
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
