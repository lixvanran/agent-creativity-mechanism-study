#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 冻结快照：★ 正在产生的批次的读数不得进入定版文献 ⇒ ★ 冻结一份带 sha256 的副本 ★

> 落点：`creativity_lab/experiments/freeze_snapshot.py`
> 用法：
>   python3 -B creativity_lab/experiments/freeze_snapshot.py \
>       --run-dir runs/topo-arm-v2-2026-10-25 \
>       --src partial_verdict.json \
>       --src h0_theta0_multicalib.json \
>       --tag n144
>
> 行为：
>   1. 每个源文件拷成 `SNAPSHOT-<stem>-<tag>-<date>.json`（★ 先写临时名再 os.replace ★）
>   2. 算 sha256 与字节数
>   3. 追加进 `SNAPSHOT-REGISTRY.json`（★ 追加、不覆盖 ★）
>   4. 打印可直接粘进报告的登记行
>
> 纪律：
>   · 已有同名快照 ⇒ 响亮失败（★ 不许静默覆盖 ★）
#   · registry 用 os.replace 原子写
#   · 快照文件本身不进 registry 的 sha 覆盖范围
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys


def die(msg):
    print("✘ %s" % msg)
    sys.exit(1)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--src", action="append", required=True,
                    help="★ 要冻结的源文件名（可多次）★")
    ap.add_argument("--tag", required=True, help="★ 标签（★ 如 n146 ★）")
    ap.add_argument("--date", default=None,
                    help="★ 文件名里的日期（★ 叙事日期，★ 如 2026-10-26 ★）")
    ap.add_argument("--label-date", default=None,
                    help="★ 叙事日期（★ 写进 registry 的 label_date 字段 ★）；★ "
                         "frozen_at 一律用【机器 UTC 时钟】⇒ ★ 不与叙事日期混用 ★")
    ap.add_argument("--note", default=None)
    ap.add_argument("--replace", action="store_true",
                    help="★ 显式允许覆盖已存在的同名快照（★ 默认响亮失败 ★）★")
    a = ap.parse_args()

    if not os.path.isdir(a.run_dir):
        die("run-dir 不存在：%s" % a.run_dir)
    date = a.date or dt.datetime.utcnow().strftime("%Y-%m-%d")
    label_date = a.label_date or date
    frozen_at = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ")

    entries = []
    for src in a.src:
        sp = os.path.join(a.run_dir, src)
        if not os.path.isfile(sp):
            die("源文件不存在：%s" % sp)
        stem = os.path.splitext(os.path.basename(src))[0]
        # ★ 若 stem 已含 tag（★ 如 UNITS-n151 ★）⇒ ★ 不重复拼 ★
        _tail = a.tag if (a.tag in stem) else ("%s-%s" % (stem, a.tag))
        dst_name = "SNAPSHOT-%s-%s.json" % (_tail, date)
        dst = os.path.join(a.run_dir, dst_name)
        if os.path.exists(dst):
            if not a.replace:
                die("快照已存在（★ 不许静默覆盖 ★；★ 确需覆盖请显式加 --replace ★）：%s" % dst)
            print("★ --replace：覆盖已存在的快照 %s" % dst_name)
        tmp = dst + ".tmp"
        shutil.copyfile(sp, tmp)
        os.replace(tmp, dst)
        sha = sha256_of(dst)
        size = os.path.getsize(dst)
        print("✔ 冻结 %s → %s ｜ %d B ｜ sha256 %s" % (src, dst_name, size, sha))
        entries.append({"src": src, "snapshot": dst_name, "sha256": sha,
                        "bytes": size, "frozen_at": frozen_at})

    reg_path = os.path.join(a.run_dir, "SNAPSHOT-REGISTRY.json")
    history = []
    prev_top = None
    if os.path.exists(reg_path):
        reg = json.load(open(reg_path, encoding="utf-8"))
        if isinstance(reg, list):
            history = list(reg)
            prev_top = history[-1] if history else None
            history = history[:-1]
        elif isinstance(reg, dict):
            if "history" in reg:
                history = list(reg["history"])
                prev_top = {k: v for k, v in reg.items() if k != "history"}
            else:
                history = []
                prev_top = dict(reg)
        else:
            die("registry 格式不认识：%s" % type(reg))
    if prev_top:
        # ★ 同名覆盖时【不】推进 history（★ 否则 history 里会出现同名不同内容的条目 ★）
        if prev_top.get("snapshot") == entries[0]["snapshot"] and a.replace:
            print("★ --replace：★ 顶层同名快照被替换（★ history 不推进 ★）")
        else:
            history.append(prev_top)

    primary = entries[0]
    pv = json.load(open(os.path.join(a.run_dir, primary["src"]), encoding="utf-8"))
    n_units = pv.get("n_units_actual")
    tids = pv.get("tids") or []
    theta0 = pv.get("theta0")

    top = {
        "snapshot": primary["snapshot"],
        "src": primary["src"],
        "sha256": primary["sha256"],
        "bytes": primary["bytes"],
        "frozen_at": frozen_at,
        "label_date": label_date,
        "clock_note": "★ frozen_at = 机器 UTC 时钟；★ label_date = 叙事日期（★ 二者可能不同 ★）★",
        "n_units": n_units,
        "tids": tids,
        "theta0": theta0,
        "note": a.note or "★ 本批仍在跑；★ 交稿文献引用的部分预判决以本快照为准（★ 副本+sha256+条数 ★）★",
        "entries": entries,
    }
    if len(entries) > 1:
        top["companions"] = [
            {"snapshot": e["snapshot"], "src": e["src"], "sha256": e["sha256"],
             "bytes": e["bytes"]} for e in entries[1:]]
    top["history"] = history

    tmp = reg_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(top, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, reg_path)
    print("✔ registry 已更新：%s（★ 顶层=最新，★ history 追加 %d 条 ★）" % (reg_path, len(history)))
    print()
    print("★ 可直接粘进报告的登记行：")
    print("| ★ 快照文件 | ★ `%s` ★ |" % primary["snapshot"])
    print("| ★ n（单元） | ★ **%s** / 360 ｜ 已跑题 %s ｜ θ₀ = %s |"
          % (n_units, "、".join(tids), theta0))
    print("| ★ sha256 | ★ `%s` ★ |" % primary["sha256"])
    print("| ★ 字节数 | ★ %d |" % primary["bytes"])
    print("| ★ 冻结时点 | ★ %s |" % frozen_at)
    if len(entries) > 1:
        print("| ★ 伴随快照 | ★ %s |"
              % ("；".join("`%s`（%s，sha256 `%s`）" % (e["snapshot"], e["src"], e["sha256"])
                          for e in entries[1:])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
