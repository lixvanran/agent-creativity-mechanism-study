#!/usr/bin/env python3
"""★ **Stage-1 产物同步进仓（★ 原子写 · ★ 带行数与 sha256 核验 · ★ 零 API）**

★ **为什么需要它**：★ 仓内 `data/arch6_stage1.jsonl` 曾是 **6 行**版，
★ 而工作区 `runs/arch6_stage1.jsonl` 是 **7 行**版 ⇒ ⇒ ★ **派生读数与原始样本不匹配**
★ ⇒ ★ **交付的是旧数据却带着看起来完整的 sha256** ⇒ ⇒ ★ **这比"少跑样本"严重**（★ 缺口被藏起来）。

★ **三条纪律**：
★ ① **原子写**（★ 临时文件 + `os.replace`）⇒ ★ 写失败不会把目标截断成 0 字节
★ ② **★ 同步后【回读核行数 + 给 sha256】** ⇒ ★ 不许只说"同步了"
★ ③ **★ 派生文件（analysis）必须与原始样本【同一批行数】** ⇒ ★ 否则报"派生读数与原始样本不匹配"

用法：
```bash
python3 -B group4_state_driven/sync_stage1_data.py            # ★ 同步并核验
python3 -B group4_state_driven/sync_stage1_data.py --check    # ★ 只核验，不写
```
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
EXP = "/workspace/第四组论证/experiment-design"
RUNS = os.path.join(EXP, "runs")
DATA = os.path.join(REPO, "group4_state_driven", "data")

FILES = [
    ("arch6_stage1.jsonl", "★ 原始样本（★ 每行 = 一个 (题, rep)）"),
    ("calllog.jsonl", "★ 逐次 API 调用（★ 含失败调用 ⇒ 分母完整）"),
    ("env_snapshot.json", "★ G0-1 环境快照"),
]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def nlines(path: str) -> int:
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for l in f if l.strip())


def atomic_copy(src: str, dst: str) -> None:
    """★ 原子写：★ 临时文件 + fsync + os.replace ⇒ ★ 失败不会截断目标"""
    tmp = dst + ".tmp"
    with open(tmp, "wb") as f:
        shutil.copyfileobj(open(src, "rb"), f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dst)


def atomic_write_text(dst: str, text: str) -> None:
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dst)


def main():
    check_only = "--check" in sys.argv
    os.makedirs(DATA, exist_ok=True)
    print("=" * 76)
    print("★ Stage-1 产物同步进仓（★ 原子写 · ★ 带核验）")
    print("=" * 76)

    # ── ① 原始样本 ──
    print("\n── ① 原始样本")
    for name, desc in FILES:
        src = os.path.join(RUNS, name)
        dst = os.path.join(DATA, name)
        if not os.path.exists(src):
            print("   ⚠ 工作区没有 %s ⇒ 跳过" % name)
            continue
        s_sha, s_n = sha256(src), nlines(src)
        if check_only:
            d_sha = sha256(dst) if os.path.exists(dst) else "(不存在)"
            d_n = nlines(dst) if os.path.exists(dst) else 0
            same = (s_sha == d_sha)
            print("   %-28s 工作区 %s (%d 行) ｜ 仓内 %s (%d 行) ⇒ %s"
                  % (name, s_sha[:16], s_n, d_sha[:16], d_n, "✔ 一致" if same else "★ 不一致"))
            continue
        atomic_copy(src, dst)
        d_sha, d_n = sha256(dst), nlines(dst)
        ok = (d_sha == s_sha) and (d_n == s_n)
        print("   %-28s %s  %s (%d 行) ⇒ %s" % (
            name, d_sha[:16], desc, d_n, "✔ 回读核验通过" if ok else "✘ 回读核验失败"))
        if not ok:
            return 1

    # ── ② 派生读数（analysis）：★ 必须与原始样本同批行数 ──
    print("\n── ② 派生读数（★ analysis）：★ 必须与原始样本【同一批行数】")
    src_jsonl = os.path.join(DATA, "arch6_stage1.jsonl")
    dst_an = os.path.join(DATA, "arch6_stage1_analysis.json")
    if not os.path.exists(src_jsonl):
        print("   ✘ 仓内没有原始样本 ⇒ 先同步")
        return 1
    n_data = nlines(src_jsonl)
    old_n = None
    if os.path.exists(dst_an):
        try:
            old_n = json.load(open(dst_an, encoding="utf-8")).get("n_rows")
        except Exception:
            old_n = None
    print("   原始样本行数 = %d ｜ 仓内 analysis 记录的行数 = %s" % (n_data, old_n))
    if old_n is not None and old_n != n_data:
        print("   ★ ★ **不一致** ⇒ ★ 派生读数描述的是另一批数据 ⇒ ⇒ 必须重算")
    else:
        print("   ✔ 一致")

    if not check_only:
        # 重算 analysis（★ 用仓内那份原始样本 ⇒ 保证可复现）
        sys.path.insert(0, os.path.join(REPO, "group4_state_driven", "code"))
        os.chdir(os.path.join(REPO, "group4_state_driven", "code"))
        import subprocess
        p = subprocess.run([sys.executable, "-B", "analyze_arch6.py", src_jsonl],
                           capture_output=True, text=True)
        os.chdir(REPO)
        # 分析脚本把结果写到 EXP/runs/ ⇒ 把它拷进仓
        produced = os.path.join(RUNS, "arch6_stage1_analysis.json")
        if os.path.exists(produced):
            atomic_copy(produced, dst_an)
            new_n = json.load(open(dst_an, encoding="utf-8")).get("n_rows")
            print("   ★ 已重算并同步 analysis ⇒ n_rows = %s ⇒ %s"
                  % (new_n, "✔ 与原始样本一致" if new_n == n_data else "✘ 仍不一致"))
            if new_n != n_data:
                return 1
        else:
            print("   ✘ 分析脚本没产出结果文件（★ stderr: %s）" % p.stderr[-400:])
            return 1

    print("\n" + "=" * 76)
    print("★ 最终核验（★ 仓内）")
    for name, _ in FILES:
        p = os.path.join(DATA, name)
        if os.path.exists(p):
            print("   %-28s %s  %d 行" % (name, sha256(p)[:16], nlines(p)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
