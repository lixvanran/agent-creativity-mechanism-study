# -*- coding: utf-8 -*-
"""**标定可复现性**：同一套金标，跑 N 次 ⇒ 报**范围**与**逐卡翻转率**。

> 2026-10-23 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/calibration_stability.py`
>
> ★ **为什么要它**（今天实测逼出来的）：
>   第一次标定：灵敏度 22/23 = 0.957 ｜ 特异度 **18/18 = 1.000**
>   第二次标定：灵敏度 21/22 = 0.955 ｜ 特异度 **17/18 = 0.944**
>   ⇒ **同一套金标、同一判官、同一 effort 档，两次结果不同** ⇒
>   ⇒ ★ **"特异度 1.000"是运气，不是性质** ⇒ 单次标定**不能**作为引用读数。
>   ⇒ 并且：两次的失效案例**不一样** ⇒ 必须区分
>      **稳定失效**（同一张卡每次都错 ⇒ 闸门缺陷 ⇒ 该修）
>      vs **随机翻转**（偶尔错 ⇒ 判官噪声 ⇒ 该报范围 + 加重复次数）
>
> 用法：
>   python3 -B calibration_stability.py --out runs/dev/calib_stability --repeats 4 --effort medium
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import calibrate_anchor_out as C  # noqa: E402
import vd_anchor_out as V  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--gold", default=os.path.join(HERE, "gold_anchor",
                                                   "gold_anchor_candidates.json"))
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--repeats", type=int, default=4)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    gold = C.load_gold(args.gold)
    devset = V.load_devset()
    judge_model = V._judge_model_from_env()

    by_task: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for c in gold:
        by_task[c["task_id"]].append(c)

    runs: List[Dict[str, Any]] = []
    for rep in range(1, args.repeats + 1):
        t0 = time.time()
        res: Dict[str, Any] = {}
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {}
            for tid, cl in by_task.items():
                llm = V.LLM("minimax", judge_model, effort=args.effort)
                futs[ex.submit(C.run_task, llm, C.dev_task(devset, tid), cl,
                               judge_model, args.effort)] = tid
            for fut in cf.as_completed(futs):
                tid = futs[fut]
                try:
                    res[tid] = fut.result()
                except Exception as e:           # noqa: BLE001
                    res[tid] = {"task_id": tid, "error": type(e).__name__, "verdict": {}}
        runs.append({"rep": rep, "results": res, "elapsed_sec": round(time.time() - t0, 1)})
        print("  第 %d 次完成（%.0fs）" % (rep, time.time() - t0), flush=True)

    # ── 逐卡：每次的判定 → 翻转率 ──────────────────────────────
    per_card: Dict[str, Dict[str, Any]] = {}
    for c in gold:
        per_card[c["card_id"]] = {
            "card_id": c["card_id"], "task_id": c["task_id"], "label": c["label"],
            "claim": c["claim"], "verdicts": [],
        }
    for run in runs:
        for tid, r in (run["results"] or {}).items():
            vd = r.get("verdict") or {}
            for c in by_task.get(tid, []):
                per_card[c["card_id"]]["verdicts"].append(vd.get(c["claim"], "拒绝"))

    def want(lbl: str) -> str:
        return "放行" if lbl == "anchor_out_real" else "拒绝"

    cards_out: List[Dict[str, Any]] = []
    for c in per_card.values():
        vs = c["verdicts"]
        w = want(c["label"])
        n_ok = sum(1 for v in vs if v == w)
        cards_out.append({
            "card_id": c["card_id"], "task_id": c["task_id"], "label": c["label"],
            "claim": c["claim"][:120], "verdicts": vs, "n_correct": n_ok,
            "n_runs": len(vs), "stable": n_ok == len(vs),
            "flip_rate": round(1 - n_ok / float(max(len(vs), 1)), 3),
        })

    # ── 每次的三个读数 ────────────────────────────────────────
    per_run: List[Dict[str, Any]] = []
    for run in runs:
        cnt = collections.defaultdict(collections.Counter)
        for tid, r in (run["results"] or {}).items():
            vd = r.get("verdict") or {}
            for c in by_task.get(tid, []):
                cnt[c["label"]][vd.get(c["claim"], "拒绝")] += 1
                cnt[c["label"]]["n"] += 1

        def rate(lbl: str, w: str) -> Dict[str, Any]:
            c = cnt[lbl]
            return {"n": c["n"], "n_hit": c[w], "rate": round(c[w] / float(max(c["n"], 1)), 4)}
        sens = rate("anchor_out_real", "放行")
        spec = rate("anchor_out_fake", "拒绝")
        pool_n = sum(cnt[l]["n"] for l in ("anchor_out_fake", "in_anchor",
                                           "contradicted", "not_load_bearing"))
        pool_k = sum(cnt[l]["拒绝"] for l in ("anchor_out_fake", "in_anchor",
                                              "contradicted", "not_load_bearing"))
        per_run.append({"rep": run["rep"], "elapsed_sec": run["elapsed_sec"],
                        "sensitivity": sens, "specificity": spec,
                        "pooled_specificity": {"n": pool_n, "n_hit": pool_k,
                                               "rate": round(pool_k / float(max(pool_n, 1)), 4)}})

    def rng(per_run: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
        vals = [r[key]["rate"] for r in per_run]
        ns = [r[key]["n_hit"] for r in per_run]
        return {"min": min(vals), "max": max(vals), "mean": round(sum(vals) / len(vals), 4),
                "n_hit_range": [min(ns), max(ns)], "n": per_run[0][key]["n"]}

    summary = {
        "meta": {"repeats": args.repeats, "effort": args.effort, "judge_model": judge_model,
                 "gold_file": os.path.basename(args.gold),
                 "n_gold_cards": len(gold)},
        "per_run": per_run,
        "sensitivity_range": rng(per_run, "sensitivity"),
        "specificity_range": rng(per_run, "specificity"),
        "pooled_specificity_range": rng(per_run, "pooled_specificity"),
        "unstable_cards": [c for c in cards_out if not c["stable"]],
        "stable_failures": [c for c in cards_out if not c["stable"] and c["flip_rate"] == 1.0],
    }
    with open(os.path.join(args.out, "calibration_stability.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "cards": cards_out}, f, ensure_ascii=False, indent=2)

    md = ["# 标定可复现性（同一金标 × N 次）\n",
          "> 判官 `%s` ｜ effort `%s` ｜ 重复 %d 次 ｜ %d 张金标卡\n"
          % (judge_model, args.effort, args.repeats, len(gold)),
          "\n## 1. 每次的三个读数\n",
          "| 重复 | 灵敏度 | 特异度 | 池化特异度 | 秒 |", "|---:|---|---|---|--:|"]
    for r in per_run:
        md.append("| %d | %d/%d = **%.3f** | %d/%d = **%.3f** | %d/%d = **%.3f** | %d |"
                  % (r["rep"], r["sensitivity"]["n_hit"], r["sensitivity"]["n"],
                     r["sensitivity"]["rate"], r["specificity"]["n_hit"],
                     r["specificity"]["n"], r["specificity"]["rate"],
                     r["pooled_specificity"]["n_hit"], r["pooled_specificity"]["n"],
                     r["pooled_specificity"]["rate"], r["elapsed_sec"]))
    sr, sp, ps = (summary["sensitivity_range"], summary["specificity_range"],
                  summary["pooled_specificity_range"])
    md += ["\n## 2. ★ 报**范围**（不报单点 —— 单次是运气）\n",
           "| 读数 | 范围 | 均值 | 分母 |", "|---|---|--:|--:|",
           "| 灵敏度 | **%.3f – %.3f** | %.3f | %d |" % (sr["min"], sr["max"], sr["mean"], sr["n"]),
           "| 特异度 | **%.3f – %.3f** | %.3f | %d |" % (sp["min"], sp["max"], sp["mean"], sp["n"]),
           "| 池化特异度 | **%.3f – %.3f** | %.3f | %d |" % (ps["min"], ps["max"], ps["mean"], ps["n"])]
    md += ["\n## 3. 失效卡（**稳定失效** vs **随机翻转**）\n",
           "| 卡 | 题 | 标注 | 各次判定 | 正确率 | 翻转率 | 类型 |",
           "|---|---|---|---|--:|--:|---|"]
    for c in summary["unstable_cards"]:
        kind = "★ **稳定失效**（每次都错 ⇒ 闸门缺陷）" if c["flip_rate"] == 1.0 else "随机翻转（判官噪声）"
        md.append("| `%s` | %s | %s | %s | %d/%d | %.2f | %s |"
                  % (c["card_id"], c["task_id"], c["label"], c["verdicts"],
                     c["n_correct"], c["n_runs"], c["flip_rate"], kind))
        md.append("| | | | *%s* | | | |" % c["claim"][:70])
    if not summary["unstable_cards"]:
        md.append("| （无）| | | | | | |")
    with open(os.path.join(args.out, "calibration_stability.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print("\n== 范围（%d 次）==" % args.repeats)
    print("  灵敏度   %.3f – %.3f（%s / %d）" % (sr["min"], sr["max"], sr["n_hit_range"], sr["n"]))
    print("  特异度   %.3f – %.3f（%s / %d）" % (sp["min"], sp["max"], sp["n_hit_range"], sp["n"]))
    print("  池化特异 %.3f – %.3f（%s / %d）" % (ps["min"], ps["max"], ps["n_hit_range"], ps["n"]))
    print("  不稳定卡：%d（其中稳定失效 %d）"
          % (len(summary["unstable_cards"]), len(summary["stable_failures"])))
    print("\n✓ 落盘 %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
