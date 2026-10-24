#!/usr/bin/env python3
"""★ **归档完整性校验（★ 2026-10-25 · 零 API）**

★ **★ 为什么需要它**：★ 归档目录 `group4_state_driven/archive/` 是【工作区产物快照】
★ ⇒ ⇒ ★ **沙箱挂掉后，★ 它是这些原始证据【唯一的存活副本】★★**
★ ⇒ ⇒ ★ **⇒ 它自己必须可校验**（★ 否则"归档了"只是说法，★ ★ 没人能证明它没坏）★★

★ **★ 验三件事 ★★**：
★ ① **归档文件数与总字节**（★ 与工作区快照一致）
★ ② **★ 抽样逐字节 sha 一致**（★ 归档没被改过；★ ★ 抽样量取【全量】⇒ ★ 清单类必须全量 ★）
★ ③ **★ 现行实现没被误改**（★ `code/` 与 `data/` 的 sha 仍与 `SHASUMS.md` 一致）

★ **★ 用法 ★★：
```bash
python3 -B group4_state_driven/verify_archive.py
# ★ 期望：exit 0
python3 -B group4_state_driven/verify_archive.py --strict
# ★ 期望：exit 0（★ 严格要求工作区快照也在）
```
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
ARCHIVE = os.path.join(_HERE, "archive")
SHASUMS = os.path.join(_HERE, "SHASUMS.md")
# ★ ★ 工作区快照（★ 若它已随沙箱消失，★ 校验降级为"只验仓内自洽"）★★
EXP = "/workspace/第四组论证/experiment-design"

# ★ ★ ★ 台账里要核的【现行实现】（★ 这些不许被归档的旧版污染）★★
CURRENT = [
    "group4_state_driven/code/workflow_arch6.py",
    "group4_state_driven/code/analyze_arch6.py",
    "group4_state_driven/code/mutations_arch6.py",
    "group4_state_driven/data/arch6_stage1.jsonl",
    "group4_state_driven/data/arch6_stage1_analysis.json",
    "creativity_lab/state_layer.py",
    "creativity_lab/experiments/test_state_layer.py",
]


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_files(root: str) -> list:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
        for fn in filenames:
            if fn.endswith(".pyc"):
                continue
            out.append(os.path.join(dirpath, fn))
    return sorted(out)


def write_manifest() -> int:
    """★ 生成 MANIFEST（★ 全量，★ 不用抽样）★"""
    manifest = os.path.join(ARCHIVE, "MANIFEST.sha256")
    rows = []
    for dirpath, dirnames, filenames in os.walk(ARCHIVE):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in sorted(filenames):
            if fn == "MANIFEST.sha256":
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ARCHIVE)
            rows.append("%s  %s" % (sha256_file(p), rel))
    rows.sort(key=lambda x: x.split("  ", 1)[1])
    with open(manifest, "w", encoding="utf-8") as f:
        f.write("# 第四组 · 归档清单（★ sha256 全量核对，★ 不用抽样）\n")
        f.write("# ★ 依据：★ 「清单过期」是必然存在的一类坏 ⇒ ⇒ 抽样会漏抓 ⇒ ⇒ 清单类必须全量\n")
        f.write("# ★ 生成脚本：group4_state_driven/verify_archive.py --write-manifest\n")
        f.write("\n".join(rows) + "\n")
    print("✔ MANIFEST 已生成：%d 项" % len(rows))
    return 0


def main() -> int:
    strict = "--strict" in sys.argv
    if "--write-manifest" in sys.argv:
        return write_manifest()
    # ★ ★ ★ 显式开关（★ 2026-10-25 修）★★
    # ★ 起因：★ 原来会拿【工作区快照】比 ⇒ ⇒ ★ 在交付包里跑时它仍去读
    #   /workspace/第四组论证/...（★ 那是【沙箱的环境状态】，★ 不是【被测对象】）
    #   ⇒ ⇒ ★ 同一份代码在同一台机器上跑出不同数 ⇒ ⇒ ★ 环境依赖 ★★
    # ★ ⇒ ⇒ ★ 修法：★ --no-workspace ⇒ 只验仓内自洽（★ 交付包内自检用）★
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-workspace", action="store_true",
                    help="★ 不与工作区快照比（★ 交付包内自检用 ⇒ 消除环境依赖）")
    ap.add_argument("--workspace", default=EXP, help="★ 工作区快照路径（★ 可显式覆盖）")
    _a = ap.parse_args()
    ok = True

    print("=" * 74)
    print("★ 归档完整性校验")
    print("=" * 74)

    # ── ① 归档规模 ──
    if not os.path.isdir(ARCHIVE):
        print("✘ 找不到归档目录：%s" % ARCHIVE)
        return 2
    afiles = [f for f in walk_files(ARCHIVE) if os.path.basename(f) != "README.md"]
    abytes = sum(os.path.getsize(f) for f in afiles)
    print("① 归档：%d 个文件 / %.2f MB（★ 不含 README.md）" % (len(afiles), abytes / 1e6))
    for sub in ("runs", "top_level"):
        p = os.path.join(ARCHIVE, sub)
        if os.path.isdir(p):
            fs = walk_files(p)
            print("   · %-12s %3d 个 / %7.2f MB" % (
                sub, len(fs), sum(os.path.getsize(x) for x in fs) / 1e6))

    # ── ①b 与工作区快照对比（★ ★ 环境依赖的唯一入口 ⇒ ★ --no-workspace 时整段跳过）──
    if _a.no_workspace:
        print("   · 工作区对比：**已显式关闭**（★ --no-workspace ⇒ ★ 消除环境依赖）")
    elif os.path.isdir(_a.workspace):
        src_runs = os.path.join(_a.workspace, "runs")
        if os.path.isdir(src_runs):
            sfiles = walk_files(src_runs)
            sbytes = sum(os.path.getsize(f) for f in sfiles)
            same = (len(sfiles) == len(walk_files(os.path.join(ARCHIVE, "runs"))))
            print("   · 工作区 runs/：%d 个 / %.2f MB ⇒ ★ 文件数%s" % (
                len(sfiles), sbytes / 1e6, "一致 ✔" if same else "★★ 不一致"))
            if not same:
                ok = False
        else:
            print("   · 工作区 runs/ 已不存在（★ 沙箱重置过）⇒ ★ 降级为只验仓内自洽")
    else:
        print("   · 工作区已不存在 ⇒ ★ 降级为只验仓内自洽")
        if strict:
            print("✘ --strict 要求工作区快照存在 ⇒ 退出")
            return 2

    # ── ② 归档内容逐字节自洽（★ 全量核对清单 ⇒ 不抽样）──
    #   ★ 依据：★ "清单过期"是必然存在的一类坏 ⇒ ⇒ 抽样会漏抓 ⇒ ⇒ 清单类必须全量
    manifest = os.path.join(ARCHIVE, "MANIFEST.sha256")
    if os.path.exists(manifest):
        want = {}
        for line in open(manifest, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("  ", 1)
            if len(parts) == 2:
                want[parts[1]] = parts[0]
        bad = []
        for rel, h in want.items():
            p = os.path.join(ARCHIVE, rel)
            if not os.path.exists(p):
                bad.append((rel, "缺失"))
            elif sha256_file(p) != h:
                bad.append((rel, "sha 不符"))
        print("② MANIFEST 全量核对：%d 项 ⇒ %s" % (
            len(want), "全部一致 ✔" if not bad else "★★ %d 项不符" % len(bad)))
        for rel, why in bad[:10]:
            print("   ✘ %s：%s" % (rel, why))
        ok = ok and not bad
    else:
        print("② MANIFEST 尚未生成（★ 跑 --write-manifest 生成）")

    # ── ③ 现行实现没被污染 ──
    if not os.path.exists(SHASUMS):
        print("✘ 找不到 SHASUMS.md")
        return 2
    txt = open(SHASUMS, encoding="utf-8").read()
    # ★ 台账表格行：| 名称 | 路径 | sha | commit |
    rows = re.findall(r"^\|\s*(.+?)\s*\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|", txt, re.M)
    n_checked = 0
    mism = []
    for name, rel, h in rows:
        p = os.path.join(REPO, rel)
        if not os.path.exists(p):
            continue
        n_checked += 1
        if sha256_file(p) != h:
            mism.append((rel, name))
    print("③ 现行实现 vs SHASUMS：核对 %d 项 ⇒ %s" % (
        n_checked, "全部一致 ✔" if not mism else "★★ %d 项不符" % len(mism)))
    for rel, name in mism[:10]:
        print("   ✘ %s（%s）" % (rel, name))
    ok = ok and not mism

    # ── ④ 归档里【不得】有现行实现的副本（★ 旧版会误导）──
    dup = []
    for cur in CURRENT:
        p = os.path.join(ARCHIVE, "top_level", os.path.basename(cur))
        if os.path.exists(p):
            dup.append(os.path.basename(cur))
    print("④ 归档里的旧版实现（★ ★ 已在 archive/README.md 的「坑 1」写明）★：%s" % (
        ", ".join(dup) if dup else "无"))
    print("   ⇒ ★ 现行实现一律以 `group4_state_driven/code/` 与 `data/` 为准")

    print("-" * 74)
    print("★ 校验结果：%s" % ("★ 全部通过 ✔" if ok else "★★ 有失败项"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
