# -*- coding: utf-8 -*-
"""**锚外闸门标定**：用金标卡测出 `VD_anchor_out` 闸门的**灵敏度 / 特异度**。

> 2026-10-23 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/calibrate_anchor_out.py`
> 规程：`routes/COLLAPSE/eval/ANCHOROUT-GOLD.md` §3
>
> ★ **为什么必须有这一步**：
>   协议 §3.3 F7 只要求判官"自检过"，但**没有金标** ⇒ 闸门的灵敏度/特异度**从未被标定**。
>   ⇒ 只报 `VD_anchor_out` 而不报灵敏度/特异度的，**不构成证据**（ANCHOROUT-GOLD §6.3）。
>
> ★ **走的是真实路径**（不是简化版）：
>   ① `CARD_Q_OUT`（OUT 通道的卡片提示）⇒ 判官逐条给 `anchor/load_bearing/verdict/decision_point_out`
>   ② `assign_forks`（岔口归并）⇒ 同一族 = 1 维度
>   ③ `fork_probe` + `fork_probe2`（**两个独立探针，AND**）⇒ A4 / A4′
>   ④ `anchor_out_gate`（A1–A9，含 A3′ 族级锚外判定）
>   ⇒ **放行 = 该卡被算作一个锚外维度**。
>
> 用法：
>   python3 -B calibrate_anchor_out.py --out runs/dev/anchor_calibration \
#       --gold gold_anchor/gold_anchor_candidates.json --effort low --workers 4
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import vd_anchor_out as V  # noqa: E402

BATCH = 8


def load_gold(path: str) -> List[Dict[str, Any]]:
    blob = json.load(open(path, encoding="utf-8"))
    cards = blob["cards"] if isinstance(blob, dict) and "cards" in blob else blob
    return [c for c in cards if c.get("label") != "disputed"]


def dev_task(devset: Dict[str, Any], tid: str) -> Dict[str, Any]:
    for t in devset.get("tasks", []):
        if t.get("task_id") == tid:
            return t
    raise SystemExit("DEV 里没有题 %s" % tid)


# ──────────────────────────────────────────────────────────────
# 一步：把一道题的全部金标卡走完整条闸门
# ──────────────────────────────────────────────────────────────
def run_task(llm: V.LLM, task: Dict[str, Any], gold: List[Dict[str, Any]],
             judge_model: str, effort: Optional[str]) -> Dict[str, Any]:
    ask = task.get("ask", "")
    ev_items = V.evidence_items_from_dev(task)
    ev_text = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev_items))
    ev_ids = [e.get("id") or "EV-%02d" % (i + 1) for i, e in enumerate(ev_items)]
    ct = V.ct_of_dev(task)
    ct_ids = [c["id"] for c in ct]
    ct_text = "\n".join("%s. %s" % (c["id"], c["text"]) for c in ct)

    claims = [c["claim"] for c in gold]

    # ① 卡片判官（OUT 通道提示词；**按题分批**，与真实管线一致）
    cards: List[Dict[str, Any]] = []
    n_parsefail = 0
    for i in range(0, len(claims), BATCH):
        b = claims[i:i + BATCH]
        lst = "\n".join("%d. %s" % (n + 1, b[n]) for n in range(len(b)))
        r = llm.chat(V.CARD_Q_OUT.format(ask=ask, ev=ev_text, claims=lst),
                     model=judge_model, temp=0.0, max_tokens=V.MM_TOKEN_FLOOR,
                     budgets=V.JUDGE_BUDGETS, min_ok=len(b) * 15, purpose="cal_card",
                     effort=effort)
        got = V.parse_card_lines(r, len(b))
        n_parsefail += max(0, len(b) - len(got))
        for g in got:
            g["claim"] = b[g["i"] - 1] if 1 <= g["i"] <= len(b) else ""
            cards.append(g)

    # ② 岔口归并
    forks = V.assign_forks(llm, cards, judge_model) if cards else {"forks": []}

    # ③ 双探针（只对锚外候选发问）
    cand = [c for c in cards
            if c.get("is_claim") and c.get("load_bearing") is True
            and c.get("decision_changed")]
    targets = [i for i, c in enumerate(cand, 1)
               if str(c.get("anchor", "")).lower() == "out"]
    probe = V.fork_probe(llm, task, cards, judge_model, targets) if targets else {}
    probe2 = V.fork_probe2(llm, task, cards, judge_model, targets) if targets else {}

    # ④ 闸门
    gate = V.anchor_out_gate(cards, forks, ct_ids, ev_ids, probe, probe2)
    passed_idx = set()
    for p in gate.get("passing", []) or []:
        passed_idx.add(p.get("idx") or p.get("i"))
    # ★ 闸门的 passing 列表不一定带 idx ⇒ 用 rejected 之外的顺序兜底
    rejected_claims = {r.get("claim", "") for r in (gate.get("rejected") or [])}
    pass_claims = [c.get("claim", "") for c in cand
                   if c.get("claim", "") not in rejected_claims]

    # 逐卡对账：把金标卡与闸门结果对上
    verdict: Dict[str, str] = {}
    for c in cand:
        verdict[c.get("claim", "")] = ("放行" if c.get("claim", "") in pass_claims else "拒绝")
    for g in gold:
        if g["claim"] not in verdict:
            # 没进候选池：不是断言 / 不承重 / 解析失败 ⇒ 闸门不放行
            verdict[g["claim"]] = "拒绝"

    return {
        "task_id": task.get("task_id"),
        "n_gold": len(gold),
        "n_claims": len(claims),
        "n_cards": len(cards),
        "n_parsefail": n_parsefail,
        "n_cand": len(cand),
        "n_probe_calls": len(targets),
        "gate_counters": gate.get("gate_counters", {}),
        "rejected": gate.get("rejected", []),
        "cards": cards,
        "forks": forks,
        "verdict": verdict,
    }


# ──────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--gold", default=os.path.join(HERE, "gold_anchor",
                                                   "gold_anchor_candidates.json"))
    ap.add_argument("--effort", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tasks", default="")
    ap.add_argument("--limit-per-task", type=int, default=0)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    gold_all = load_gold(args.gold)
    devset = V.load_devset()
    judge_model = V._judge_model_from_env()

    by_task: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for c in gold_all:
        by_task[c["task_id"]].append(c)
    tids = [t for t in sorted(by_task) if not args.tasks or t in args.tasks.split(",")]
    if args.limit_per_task:
        for t in tids:
            by_task[t] = by_task[t][:args.limit_per_task]

    n_calls_est = sum((len(v) + BATCH - 1) // BATCH + 1 + 2 * 6 for v in
                       (by_task[t] for t in tids))
    print("== 标定：%d 题 / %d 张金标卡（disputed 已排除）｜估算调用 ~%d 次｜effort=%s =="
          % (len(tids), sum(len(by_task[t]) for t in tids), n_calls_est,
             args.effort or "(默认=max)"))

    t0 = time.time()
    results: Dict[str, Any] = {}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {}
        for t in tids:
            llm = V.LLM("minimax", judge_model, effort=args.effort)
            futs[ex.submit(run_task, llm, dev_task(devset, t), by_task[t],
                            judge_model, args.effort)] = t
        for fut in cf.as_completed(futs):
            t = futs[fut]
            try:
                results[t] = fut.result()
            except Exception as e:               # noqa: BLE001
                results[t] = {"task_id": t, "error": type(e).__name__, "verdict": {}}
                print("⚠️ 题 %s 失败：%s" % (t, e))
    dt = time.time() - t0

    # ── 汇总：灵敏度 / 特异度（**必带绝对分子分母**）──────────
    by_label = collections.defaultdict(lambda: collections.Counter())
    for t in tids:
        r = results.get(t) or {}
        vd = r.get("verdict") or {}
        for g in by_task[t]:
            v = vd.get(g["claim"], "拒绝")
            by_label[g["label"]][v] += 1
            by_label[g["label"]]["n"] += 1

    def rate(label: str, want: str) -> Dict[str, Any]:
        c = by_label[label]
        n = c["n"]
        k = c[want]
        return {"label": label, "n": n, "n_hit": k, "rate": round(k / float(max(n, 1)), 4)}

    sens = rate("anchor_out_real", "放行")
    spec = rate("anchor_out_fake", "拒绝")
    pool_n = sum(by_label[l]["n"] for l in
                 ("anchor_out_fake", "in_anchor", "contradicted", "not_load_bearing"))
    pool_k = sum(by_label[l]["拒绝"] for l in
                 ("anchor_out_fake", "in_anchor", "contradicted", "not_load_bearing"))
    pooled_spec = {"label": "池化特异度(其余四类全拒)", "n": pool_n, "n_hit": pool_k,
                   "rate": round(pool_k / float(max(pool_n, 1)), 4)}

    gates: Dict[str, int] = collections.Counter()
    for t in tids:
        for k, v in ((results.get(t) or {}).get("gate_counters") or {}).items():
            gates[k] += v

    summary = {
        "meta": {"n_tasks": len(tids), "n_gold_cards": sum(len(by_task[t]) for t in tids),
                 "judge_model": judge_model, "effort": args.effort or "(default=max)",
                 "elapsed_sec": round(dt, 1), "gold_file": args.gold,
                 "batch": BATCH},
        "sensitivity": sens, "specificity": spec, "pooled_specificity": pooled_spec,
        "per_label": {l: dict(c) for l, c in by_label.items()},
        "gate_counters": dict(gates),
    }
    with open(os.path.join(args.out, "calibration.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)

    md = ["# 锚外闸门标定（灵敏度 / 特异度）\n",
          "> 判官 `%s` ｜ effort `%s` ｜ %d 题 / %d 张金标卡（disputed 已排除）｜批次 %d\n"
          % (judge_model, args.effort or "(default=max)", len(tids),
             summary["meta"]["n_gold_cards"], BATCH),
          "> 源：`%s` ｜ 规程：`ANCHOROUT-GOLD.md` §3\n" % os.path.basename(args.gold),
          "\n## 1. 三个读数（**必带绝对分子分母**）\n",
          "| 读数 | 分子 | 分母 | 值 | 含义 |", "|---|--:|--:|--:|---|"]
    md.append("| **探针层灵敏度** | %d | %d | **%.3f** | 真锚外卡被放行的比例（低 ⇒ `VD_anchor_out` 被低估）|"
              % (sens["n_hit"], sens["n"], sens["rate"]))
    md.append("| **探针层特异度** | %d | %d | **%.3f** | 假锚外卡被拒绝的比例（低 ⇒ 维度数通胀 ⇒ 立论被高估）|"
              % (spec["n_hit"], spec["n"], spec["rate"]))
    md.append("| **池化特异度** | %d | %d | **%.3f** | 其余四类（假/锚内/矛盾/花絮）全被拒的比例 |"
              % (pooled_spec["n_hit"], pooled_spec["n"], pooled_spec["rate"]))
    md += ["\n## 2. 逐类明细\n", "| 标签 | 张数 | 放行 | 拒绝 | 期望 | 判定 |",
           "|---|--:|--:|--:|---|:-:|"]
    expect = {"anchor_out_real": "放行", "anchor_out_fake": "拒绝", "in_anchor": "拒绝",
              "contradicted": "拒绝", "not_load_bearing": "拒绝"}
    for l, c in sorted(by_label.items()):
        ok = "✔" if c[expect[l]] == c["n"] else ("—" if c[expect[l]] else "✘")
        md.append("| `%s` | %d | %d | %d | 全%s | %s |"
                  % (l, c["n"], c["放行"], c["拒绝"], expect[l], ok))
    md += ["\n## 3. 闸门拒绝原因分解（全部题合计）\n",
           "| 闸门 | 次数 |", "|---|--:|"]
    for k, v in sorted(gates.items(), key=lambda kv: -kv[1]):
        md.append("| `%s` | %d |" % (k, v))
    with open(os.path.join(args.out, "calibration.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print("\n== 标定结果 ==")
    print("  灵敏度   %d/%d = %.3f" % (sens["n_hit"], sens["n"], sens["rate"]))
    print("  特异度   %d/%d = %.3f" % (spec["n_hit"], spec["n"], spec["rate"]))
    print("  池化特异 %d/%d = %.3f" % (pooled_spec["n_hit"], pooled_spec["n"],
                                       pooled_spec["rate"]))
    print("\n✓ 落盘 %s（耗时 %.0fs）" % (args.out, dt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
