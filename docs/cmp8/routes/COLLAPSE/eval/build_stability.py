# -*- coding: utf-8 -*-
"""把各判官变体的读数**合并**成一张跨变体稳定性表（零 API，不重跑）。

> 2026-10-22 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/build_stability.py`
> 用法：
>   python3 build_stability.py --out runs/dev/stability \
#       --v1 runs/dev/measure/anchor_readout.json \
#       --vx runs/dev/judge_variants/judge_variants.json \
#       --vx runs/dev/judge_variants2/judge_variants.json
> ⇒ 各变体的**读数已在各自跑批时落盘**；这里只做**合并 + 稳定性判定**（不花钱、不重跑）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import judge_variants as JV  # noqa: E402


def load_v1(path: str) -> Dict[str, Any]:
    blob = json.load(open(path, encoding="utf-8"))
    # ★ 兼容两种格式：judge_variants.json（变体数组） 或 anchor_readout.json（results 字典）
    if "variants" in blob:
        for v in blob.get("variants", []):
            vid = v.get("id") or v.get("variant") or ""
            if "minimax" in vid.lower() or "V1" in vid:
                return {"id": v.get("id", "V1-minimax-m31"),
                        "vendor": v.get("vendor", "minimax"),
                        "model": v.get("model", ""),
                        "note": "主批跑（锚内通道 + 本组锚外通道，修好预算阶梯后）",
                        "results": v.get("readings", v.get("results", {})),
                        "calls": v.get("calls", {}),
                        "selfcheck": v.get("selfcheck", {})}
    if not blob.get("results"):
        raise SystemExit("load_v1: 文件里既没有 variants 也没有 results ⇒ " + path)
    return {"id": "V1-minimax-m31", "vendor": "minimax",
            "model": blob.get("judge_model", "MiniMax-M3.1-Flash-Preview"),
            "note": "主批跑（batch-U1 口径的锚内通道 + 本组的锚外通道）",
            "results": blob.get("results", {}), "calls": blob.get("calls", {}),
            "selfcheck": {"note": "见 selftest_out_c/selftest.json"}}


def load_vx(path: str) -> List[Dict[str, Any]]:
    blob = json.load(open(path, encoding="utf-8"))
    out = []
    for v in blob.get("variants", []):
        if v.get("id", "").endswith("(merged)"):
            continue
        out.append(v)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v1", required=True)
    ap.add_argument("--vx", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    variants: List[Dict[str, Any]] = []
    if os.path.exists(args.v1):
        variants.append(load_v1(args.v1))
    for p in args.vx:
        if os.path.exists(p):
            variants.extend(load_vx(p))

    if not variants:
        print("没有可合并的读数")
        return 1

    # ── 每份答案的**有效**性检查（坏通道不许进表）──────────────
    print("| 变体 | 读数份数 | 有效份数 | 通道失败 | parsefail>10% 的份数 |")
    print("|---|---|---|---|---|")
    for v in variants:
        res = v.get("results", {})
        valid = sum(1 for r in res.values() if r.get("valid", 1) == 1)
        chfail = sum(1 for r in res.values() if r.get("channel_failed"))
        pf = sum(1 for r in res.values() if (r.get("parsefail_rate") or 0) > 0.10)
        print("| `%s` | %d | %d | %d | %d |" % (v["id"], len(res), valid, chfail, pf))

    blob = {"meta": {"generated_at": "2026-10-22", "sources": [args.v1] + args.vx},
            "variants": variants, "stability": JV.stability_table(variants)}
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "judge_variants_merged.json"), "w", encoding="utf-8") as f:
        json.dump(blob, f, ensure_ascii=False, indent=2)
    JV.write_markdown(os.path.join(args.out, "JUDGE-VARIANTS-RESULTS.md"), blob)
    print("\n✓ 落盘 %s" % args.out)

    st = blob["stability"]
    print("\n| 指标 | 极差 | 逐答案完全一致 | 判读 |")
    print("|---|---|---|---|")
    for row in st["rows"]:
        print("| %s | %s | %s/%s | %s |" % (
            row["label"], row["spread"], row["n_identical_across_variants"],
            row["n_answers"], "稳" if row["stable"] else "**不稳**"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
