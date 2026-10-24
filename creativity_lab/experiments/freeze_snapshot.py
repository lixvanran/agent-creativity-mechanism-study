#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 冻结快照：★ 正在产生的批次的读数不得进入定版文献 ⇒ ★ 冻结一份带 sha256 的副本 ★

> 落点：`creativity_lab/experiments/freeze_snapshot.py`
> 用法：
>   python3 -B creativity_lab/experiments/freeze_snapshot.py \
>       --run-dir runs/topo-arm-v2-2026-10-24 \
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
                    help="★ 文件名里的日期（★ 叙事日期，★ 如 2026-10-24 ★）")
    ap.add_argument("--label-date", default=None,
                    help="★ 叙事日期（★ 写进 registry 的 label_date 字段 ★）；★ "
                         "frozen_at 一律用【机器 UTC 时钟】⇒ ★ 不与叙事日期混用 ★")
    ap.add_argument("--note", default=None)
    ap.add_argument("--replace-companion", action="store_true",
                    help="★ 显式允许【某个 companion 的 sha 变化】（★ 证据格式升级时用 ★）★ "
                         "★ 旧 sha 记入 companions_history ★ ★ 【不许静默替换】★★")
    ap.add_argument("--companions-only", action="store_true",
                    help="★ 只把 --src 追加进【顶层 companions】★：★ 不动顶层条目（★ frozen_at/label_date/sha 保持原样 ★）★、★ 不推进 history ★")
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
            if a.companions_only:
                # ★ companions-only：★ 同名副本已存在 ⇒ ★ 核 sha（★ 同内容必然同 sha ★）
                #   ★ 同 sha ⇒ ★ 跳过（★ 无害 ★）；★ 不同 sha ⇒ ★ 响亮失败（★ 不许静默替换 ★）★★
                _old_sha = sha256_of(dst)
                _new_sha = sha256_of(sp)
                if _old_sha == _new_sha:
                    print("★ companions-only：★ 副本已存在且【sha 相同】⇒ 跳过覆盖：%s" % dst_name)
                else:
                    die("companions-only：★ 同名副本内容已变（★ %s：★ %s ⇒ %s ★）★ ⇒ ★ "
                        "【不许静默替换】★" % (dst_name, _old_sha[:12], _new_sha[:12]))
            elif not a.replace:
                die("快照已存在（★ 不许静默覆盖 ★；★ 确需覆盖请显式加 --replace ★）：%s" % dst)
            else:
                print("★ --replace：覆盖已存在的快照 %s" % dst_name)
        # ★ ★ 无条件执行（★ ★ 别把它塞进上面的 if/elif/else：★ 我曾把它删掉 ⇒ ★
        #   ★ 老样本全过（★ 副本已存在 ⇒ 走 skip 分支 ★）、★ 新样本全崩 ⇒ ★ 只有新路径才暴露 ★）★★
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
    if a.companions_only:
        # ★ ★ companions-only：★ 顶层条目【一个字都不动】★★
        #   ★ 理由：★ 读数逐字节未变时（★ sha 相同 ★），★ 重冻会把「冻结时点」篡改成现在
        #   ★   ⇒ ★ 篡改冻结语义 ⇒ ★ 而冻结时点正是「这批数据何时被钉住」的证据 ★★
        if not prev_top:
            die("companions-only：★ registry 里没有可追加的顶层条目 ★")
        _old_comp = list(prev_top.get("companions") or [])
        _by_src = {c.get("src"): c for c in _old_comp}
        _hist = list(prev_top.get("companions_history") or [])
        for e in entries:
            if e["src"] == prev_top.get("src"):
                continue                       # ★ 顶层自己的 src 不重复登记 ★
            _c = {"snapshot": e["snapshot"], "src": e["src"],
                  "sha256": e["sha256"], "bytes": e["bytes"]}
            _prev = _by_src.get(e["src"])
            if _prev and _prev.get("sha256") != _c["sha256"]:
                if not a.replace_companion:
                    die("companions-only：★ 同一 src 的 sha 变了（★ %s：★ %s ⇒ %s ★）★ ⇒ ★ "
                        "【不许静默替换】★ ★ ⇒ 确需替换（★ 证据格式升级 ★）请显式加 "
                        "--replace-companion ★" % (e["src"], _prev.get("sha256", "")[:12], _c["sha256"][:12]))
                print("★ ★★ --replace-companion：★ companion 的 sha 变了：★ %s：★ %s ⇒ %s ★★"
                      % (e["src"], _prev.get("sha256", "")[:12], _c["sha256"][:12]))
                print("   ⇒ 旧值记入 companions_history（★ 便于追溯 ★）★")
                _hist.append({"src": e["src"], "sha256": _prev.get("sha256"),
                              "bytes": _prev.get("bytes"), "note": "★ 被 --replace-companion 替换的旧值 ★"})
            _by_src[e["src"]] = _c
        _new_comp = sorted(_by_src.values(), key=lambda c: c.get("src") or "")
        # ★ ★ entries 也要同步（★ fill_report 读的是 entries ★）★ ⇒ ★ 两个字段必须一致 ★
        _pe = {"src": prev_top.get("src"), "snapshot": prev_top.get("snapshot"),
               "sha256": prev_top.get("sha256"), "bytes": prev_top.get("bytes"),
               "frozen_at": prev_top.get("frozen_at")}
        _new_entries = [_pe] + [dict(c, frozen_at=frozen_at) for c in _new_comp]
        top = dict(prev_top)
        top["entries"] = _new_entries
        top["companions"] = _new_comp
        if _hist:
            top["companions_history"] = _hist
        top["companions_note"] = ("★ 本表用 --companions-only 扩充（★ 不改顶层条目 ★）；★ "
                                  "顶层 sha256 为 %s ★" % prev_top.get("sha256", "")[:16])
        tmp = reg_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(top, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, reg_path)
        print("✔ registry 已更新（★ companions-only：★ 顶层条目【未动】★）")
        print("★ 顶层快照：%s ｜ frozen_at 保持 %s" % (prev_top.get("snapshot"), prev_top.get("frozen_at")))
        print("★ companions：%d 条 ⇒ %s" % (len(_new_comp),
              "、".join(c.get("src", "") for c in _new_comp)))
        return 0

    if prev_top and not a.companions_only and prev_top.get("src") != entries[0]["src"]:
        # ★ ★ 保护：★ 顶层 src 换了人却【不显式声明】⇒ ★ 旧顶层被推进 history ⇒ ★
        #   ★ 而 history 里那条会被误读为「版本变迁」★ ⇒ ⇒ ★ 必须醒目提示 ★★
        print("★ ★★ 警告：★ 顶层快照的 src 变了：★ %s ⇒ %s ★★" % (prev_top.get("src"), entries[0]["src"]))
        print("   ⇒ 旧顶层会被推入 history（★ 请确认这是【换一份新定版】而不是【误操作】★）")
    if prev_top:
        # ★ 同名覆盖时【不】推进 history（★ 否则 history 里会出现同名不同内容的条目 ★）
        if prev_top.get("snapshot") == entries[0]["snapshot"] and a.replace:
            # ★ ★ 2026-10-24 修：★ 原来【同名覆盖不推进 history】⇒ ★ ⇒ ★
            #   ★ ★ 旧条目【被丢掉】⇒ ★ ⇒ 【旧版本无法追溯】★★ ★
            #   ★ ★ ⇒ ★ 【同名但内容不同】⇒ ★ ⇒ 【必须】推进 history（★ 否则就是丢证据 ★）★★ ★
            #   ★ ★ ⇒ ★ 规则改为：★ 同名 + 【sha 相同】⇒ ★ 不推进（★ 只是重复登记 ★）
            #   ★ ★ ★　　　同名 + 【sha 不同】⇒ ★ 推进（★ 旧版本必须留痕 ★）★★ ★
            if prev_top.get("sha256") == entries[0]["sha256"]:
                print("★ --replace：★ 顶层同名快照被替换（★ sha 相同 ⇒ 不推进 history ★）")
            else:
                print("★ --replace：★ 顶层同名快照被替换（★ ★ sha 变了 ⇒ ★ 旧条目推进 history ★）★")
                history.append(prev_top)
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
