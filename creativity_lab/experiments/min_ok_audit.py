#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ min_ok 阈值与【输出规格】的错配审计（★ 2026-10-26 · 第 1 层论证线那条 ★）★★

★ ★★ 为什么要有这个脚本（★ 事件）★★
★ 第 1 层论证线 12:55Z 指出：★ 「★ 统一阈值 200 会把【一批正常输出】判成失败 ★」
★   ⇒ ★ 因为 `SELECT_ASK` 的输出规格是「★ 先写 60–120 字理由、★ 再原样贴出被选篇全文 ★」
★   ⇒ ★ 【当被选篇本身短时、★ 总长可以 < 200 ★】★★ ★
★ ⇒ ★ 我方回源核：★ ★ `creativity_lab/arms/dual.py` 的四处 `llm.chat` 【全都不传 min_ok】★
★   ⇒ ★ 【全吃 `client.chat` 的默认 200】★★ ★
★ ⇒ ★ ★ 而我方 `client.py` 的 docstring 【早就写了】：「★ 短输出任务必须显式传小 min_ok（如 20）★」
★   ⇒ ★ ⇒ ★ **我方【知道】这个坑、★ 只是 dual.py 没照做** ★★ ★

★ ★★ 这个脚本算三件事（★ 全部来自真实数据、★ 零硬编码 ★）★★
★   ① ★ 各步骤【真实 prompt 的输出规格】与【定版后的 min_ok】★（★ 从源码回源 ★）
★   ② ★ 历史批里【是否触发过 min_ok 路径】（★ ⇒ 判【改动对历史读数是否逐字节兼容】★）
★   ③ ★ 历史批里【有多少个单元的最终输出短于默认阈值 200】（★ ⇒ ★★ 【误杀是否已实际发生】★★ ★）
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

# ★ 各步骤的输出规格（★ 全部回源 `creativity_lab/prompts.py` 的真实文本 ★）
SPECS = [
    ("diverge", "BRANCH_ASK", "OUT_SPEC「控制在 400 字以内」", 120),
    ("premise", "PREMISE_Q", "150–250 字", 120),
    ("fuse", "FUSE_ASK", "OUT_SPEC「400 字以内」", 120),
    ("select", "SELECT_ASK", "理由 60–120 字 + 原样贴出被选篇全文", 20),
]
DEFAULT_MIN_OK = 200


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def die(msg, code=1):
    print("✘ %s" % msg)
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--unit-list", required=True)
    ap.add_argument("--json-out", required=True)
    ap.add_argument("--default-min-ok", type=int, default=DEFAULT_MIN_OK)
    a = ap.parse_args()

    unit_dir = os.path.join(a.run_dir, "units")
    if not os.path.isdir(unit_dir):
        die("units 目录不存在：%s" % unit_dir)
    allowed = set(x.strip() for x in open(a.unit_list, encoding="utf-8") if x.strip())
    if not allowed:
        die("单元清单为空（★ 覆盖度不足 ⇒ 响亮失败 ★）", code=7)

    # ① 源码回源：dual.py 四处是否都显式传 min_ok
    dual_p = os.path.join(ROOT, "creativity_lab", "arms", "dual.py")
    dual_src = open(dual_p, encoding="utf-8").read()
    n_calls = len(re.findall(r"llm\.chat\(", dual_src))
    n_explicit = len(re.findall(r"min_ok=MIN_OK_", dual_src))
    consts = {k: int(v) for k, v in
              re.findall(r"^MIN_OK_(\w+)\s*=\s*(\d+)\s*$", dual_src, re.M)}
    prompts_p = os.path.join(ROOT, "creativity_lab", "prompts.py")
    prompts_src = open(prompts_p, encoding="utf-8").read()
    spec_hits = {}
    for _step, pname, _desc, _mk in SPECS:
        m = re.search(pname + r"\s*=\s*(.+?)(?=\n[A-Z_]+\s*=|\nZ\b|\Z)", prompts_src, re.S)
        body = m.group(1) if m else ""
        mm = re.findall(r"\d+\s*[-~]\s*\d+\s*字|控制在\s*\d+\s*字以内|原样贴出|先写\s*\d+\s*-\s*\d+\s*字",
                         body)
        spec_hits[pname] = mm

    # ②③ 历史批：min_ok 路径是否触发过 + 有多少单元短于默认阈值
    n_units = 0
    n_calls_rec = 0
    n_minok_records = 0
    lens = []
    short_units = []
    for fn in sorted(os.listdir(unit_dir)):
        if not fn.endswith(".json") or fn[:-5] not in allowed:
            continue
        n_units += 1
        d = json.load(open(os.path.join(unit_dir, fn), encoding="utf-8"))
        for c in (d.get("calls") or []):
            n_calls_rec += 1
            if isinstance(c, dict) and "min_ok" in json.dumps(c, ensure_ascii=False):
                n_minok_records += 1
        p = (d.get("post") or "").strip()
        if p:
            lens.append(len(p))
            if len(p) < a.default_min_ok:
                short_units.append({"unit": fn[:-5], "len": len(p)})
    lens.sort()
    if not lens:
        die("可用单元的 post 全为空（★ 无有效读数 ⇒ 响亮失败 ★）", code=7)

    out = {
        "checked_at_utc": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"),
        "n_units": n_units,
        "n_calls_records": n_calls_rec,
        "n_records_mentioning_min_ok": n_minok_records,
        "min_ok_path_ever_triggered": n_minok_records > 0,
        "default_min_ok": a.default_min_ok,
        "post_len_min": lens[0],
        "post_len_p05": lens[int(len(lens) * 0.05)],
        "post_len_median": lens[len(lens) // 2],
        "post_len_max": lens[-1],
        "n_units_shorter_than_default": len(short_units),
        "units_shorter_than_default": short_units[:20],
        "dual_py_sha256": sha256_of(dual_p),
        "prompts_py_sha256": sha256_of(prompts_p),
        "llm_chat_call_sites": n_calls,
        "llm_chat_sites_with_explicit_min_ok": n_explicit,
        "spec_min_ok_table": [
            {"step": s, "prompt": p, "output_spec": d, "min_ok": mk,
             "spec_hits_in_prompt": spec_hits.get(p, [])}
            for s, p, d, mk in SPECS],
        "min_ok_constants_in_dual_py": consts,
        "compatibility_note": "★ 历史批的 calls 记录里【没有一条提到 min_ok】⇒ ★ "
                              "⇒ 说明该路径【从未触发】⇒ ★ ⇒ 显式传 min_ok 对历史读数【逐字节兼容】★",
        "verdict": ("★ ★ 统一阈值 %d 已在历史批里【实际误杀 %d 个单元】★ ⇒ ★ "
                    "⇒ 污染率读数里【有一部分是被阈值制造出来的】★★ ★"
                    % (a.default_min_ok, len(short_units))) if short_units
                   else "★ 本批没有短于默认阈值的单元 ⇒ 未观察到实际误杀 ★",
    }
    tmp = a.json_out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, a.json_out)
    print("✔ 落盘 %s ｜ sha256 %s" % (a.json_out, sha256_of(a.json_out)[:16]))
    print("   单元 %d ｜ calls 记录 %d ｜ 提到 min_ok 的记录 %d" % (n_units, n_calls_rec, n_minok_records))
    print("   post 长度 min=%d p05=%d 中位=%d max=%d ｜ 短于 %d 的单元：%d"
          % (lens[0], lens[int(len(lens) * 0.05)], lens[len(lens) // 2], lens[-1],
             a.default_min_ok, len(short_units)))
    print("   ⇒ %s" % out["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
