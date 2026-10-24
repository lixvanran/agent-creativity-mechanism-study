# -*- coding: utf-8 -*-
"""**effort 敏感性对照**：锚外读数 `VD_anchor_out` 到底是不是"思考深度"的产物？

> 2026-10-23 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/sweep_effort.py`
>
> ★ **要回答的问题（今天最重要的一个）**：
>   2026-10-22 的终局跑批里，`W_div#D01` 判出 `VD_anchor_out=4`、`W_div#D08` 判出 `5`，
>   而**另外三个判官（grok / qwen / deepseek）的 OUT 全是 0**。
>   2026-10-23 的 effort 探针又发现：**同一份答案，max 档判出的 2 张 `anchor=out`，
>   在 low/medium 档消失了**（而同一档的离散判定在完整解析时**完全一致**）。
>   ⇒ ★ **昨天的 OUT=4/5 可能是"判官思考深度"的产物，而不是"内容里真的有锚外维度"。**
>   ⇒ ⇒ 这件事不查清，昨天的读数**不能引用**。
>
> ★ **为什么只重判 OUT 那一段**（成本从 3.5h 降到 ~1h）：
>   上游"抽取断言"（extract_claims）的结果**已落盘**（`cards_out_all[*].claim`）
>   ⇒ 只重跑**会因 effort 而改变**的那几步：
>   `judge_out_channel`（卡片判官，产出 `anchor`）→ `assign_forks`（岔口）→ **双探针** → `anchor_out_gate`。
>   ⇒ 变的是"判官怎么判"，不变的是"被判的内容" ⇒ **干净的单因子对照**。
>
> 用法：
>   python3 -B sweep_effort.py --out runs/dev/effort_sweep --efforts max,low --workers 4
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

READ_SRC = "runs/dev/judge_variants3/judge_variants.json"


def load_readings(path: str) -> Dict[str, Dict[str, Any]]:
    blob = json.load(open(path, encoding="utf-8"))
    for v in blob.get("variants", []):
        vid = (v.get("id") or "")
        if "minimax" in vid.lower() or vid.startswith("V1"):
            return v.get("readings") or v.get("results") or {}
    raise SystemExit("在 %s 里找不到 V1(MiniMax) 变体" % path)


def dev_task(devset: Dict[str, Any], tid: str) -> Dict[str, Any]:
    for t in devset.get("tasks", []):
        if t.get("task_id") == tid:
            return t
    raise SystemExit("DEV 里没有题 %s" % tid)


def _out_channel_batched(llm: V.LLM, ask: str, ev_text: str, claims: List[str],
                         model: str, batch: int) -> Dict[str, Any]:
    """OUT 通道卡片判官（**批大小可配**）。

    ★ 为什么不用 `judge_out_channel` 的自适应批大小：它按证据包长度给 4~8，
      而 **max 档在批 ≥4 时 100% 截断**（见 channel_probe）⇒ 对照会被"截断"污染。
      ⇒ 这里固定小批，保证三档面对**同样的输入规模**。
    """
    cards: List[Dict[str, Any]] = []
    n_parsefail = 0
    for i in range(0, len(claims), batch):
        b = claims[i:i + batch]
        lst = "\n".join("%d. %s" % (n + 1, b[n]) for n in range(len(b)))
        r = llm.chat(V.CARD_Q_OUT.format(ask=ask, ev=ev_text, claims=lst),
                     model=model, temp=0.0, max_tokens=V.MM_TOKEN_FLOOR,
                     budgets=V.JUDGE_BUDGETS, min_ok=len(b) * 15, purpose="sweep_card")
        got = V.parse_card_lines(r, len(b))
        n_parsefail += max(0, len(b) - len(got))
        for g in got:
            g["claim"] = b[g["i"] - 1] if 1 <= g["i"] <= len(b) else ""
            cards.append(g)
    return {"cards_all": cards, "n_cards": len(cards), "n_parsefail": n_parsefail,
            "parsefail_rate": n_parsefail / max(len(claims), 1)}


def sweep_one(judge_model: str, effort: Optional[str], task: Dict[str, Any],
              claims: List[str], batch: int = 2) -> Dict[str, Any]:
    """一条答案 × 一个 effort ⇒ 走完 OUT 判定链"""
    llm = V.LLM("minimax", judge_model, effort=effort)
    ask = task.get("ask", "")
    ev_items = V.evidence_items_from_dev(task)
    ev_text = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev_items))
    ev_ids = [e.get("id") or "EV-%02d" % (i + 1) for i, e in enumerate(ev_items)]
    ct = V.ct_of_dev(task)
    ct_ids = [c["id"] for c in ct]

    # ① OUT 通道卡片判官
    outr = _out_channel_batched(llm, ask, ev_text, claims, judge_model, batch)
    cards = outr["cards_all"]
    # ② 岔口归并
    forks = V.assign_forks(llm, cards, judge_model) if cards else {"forks": []}
    # ③ 双探针（只对锚外候选）
    cand = [c for c in cards
            if c.get("is_claim") and c.get("load_bearing") is True
            and c.get("decision_changed")]
    targets = [i for i, c in enumerate(cand, 1)
               if str(c.get("anchor", "")).lower() == "out"]
    probe = V.fork_probe(llm, task, cards, judge_model, targets) if targets else {}
    probe2 = V.fork_probe2(llm, task, cards, judge_model, targets) if targets else {}
    # ④ 闸门
    gate = V.anchor_out_gate(cards, forks, ct_ids, ev_ids, probe, probe2)

    calls = llm.log.summary()
    n_call = max(calls.get("n_calls", 0), 1)
    bad = calls.get("n_empty_content", 0) + calls.get("n_truncated", 0)
    return {
        "effort": effort or "(default=max)",
        "n_claims_in": len(claims),
        "n_cards": len(cards),
        "parsefail_rate": outr.get("parsefail_rate"),
        "n_cand": len(cand),
        "n_out_cand": len(targets),
        "out_cand_anchor_out": [c.get("claim", "")[:40] for c in cand
                                if str(c.get("anchor", "")).lower() == "out"],
        "VD_anchor_out": gate.get("n_pass", None),
        "n_pass": len(gate.get("passing") or []),
        "gate_counters": gate.get("gate_counters", {}),
        "rejected": [{"claim": r.get("claim", "")[:50], "gate": r.get("gate")}
                     for r in (gate.get("rejected") or [])],
        "calls": calls,
        "channel_health": round(1.0 - bad / float(n_call), 4),
        "cards_digest": [{"i": c.get("i"), "claim": (c.get("claim") or "")[:60],
                           "lb": c.get("load_bearing"), "anchor": c.get("anchor"),
                           "verdict": c.get("verdict"),
                           "dpo": (c.get("decision_point_out") or "")[:60]}
                          for c in cand],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--efforts", default="max,low")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--answers", default="")
    ap.add_argument("--batch", type=int, default=2,
                    help="OUT 卡片判官每批几条断言（★ max 档在批≥4 时 100%% 截断 ⇒ 对照须用小批）")
    ap.add_argument("--read-src", default=READ_SRC)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    readings = load_readings(args.read_src)
    devset = V.load_devset()
    judge_model = V._judge_model_from_env()
    efforts = [e for e in args.efforts.split(",") if e]
    ans_ids = [a for a in args.answers.split(",") if a] or sorted(readings.keys())

    jobs: List[Dict[str, Any]] = []
    for aid in ans_ids:
        rd = readings.get(aid)
        if not rd:
            continue
        claims = [c.get("claim", "") for c in (rd.get("cards_out_all") or [])
                  if (c.get("claim") or "").strip()]
        if not claims:
            print("⚠️ %s 没有可复用的断言 ⇒ 跳过" % aid)
            continue
        task = dev_task(devset, rd.get("task_id"))
        for eff in efforts:
            jobs.append({"answer": aid, "effort": eff, "claims": claims, "task": task})

    print("== effort 敏感性对照：%d 份（%d 答案 × %d 档）=="
          % (len(jobs), len(ans_ids), len(efforts)))
    t0 = time.time()
    out: Dict[str, Any] = {}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(sweep_one, judge_model, j["effort"], j["task"], j["claims"],
                           args.batch): j for j in jobs}
        for fut in cf.as_completed(futs):
            j = futs[fut]
            try:
                r = fut.result()
            except Exception as e:               # noqa: BLE001
                r = {"effort": j["effort"], "error": type(e).__name__,
                     "VD_anchor_out": None, "n_pass": 0}
            out.setdefault(j["answer"], {})[j["effort"]] = r
            print("  %-18s %-8s OUT=%-4s 卡%-3s 锚外候选%-3s parsefail=%s 健康度=%s"
                  % (j["answer"], j["effort"], r.get("n_pass"), r.get("n_cards"),
                     r.get("n_out_cand"), r.get("parsefail_rate"),
                     r.get("channel_health")), flush=True)
    dt = time.time() - t0

    with open(os.path.join(args.out, "effort_sweep.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": {"judge_model": judge_model, "efforts": efforts,
                            "elapsed_sec": round(dt, 1), "read_src": args.read_src,
                            "note": "只重判 OUT 判定链（claims 取自已落盘抽取结果 ⇒ 单因子对照）"},
                   "results": out}, f, ensure_ascii=False, indent=2)

    md = ["# effort 敏感性对照：`VD_anchor_out` 是内容里的，还是思考深度的产物？\n",
          "> 判官 `%s` ｜ 只重判 OUT 判定链（claims 取自已落盘的抽取结果 ⇒ **单因子对照**）\n"
          % judge_model,
          "\n## 逐份读数\n",
          "| 答案 | " + " | ".join("%s OUT" % e for e in efforts)
          + " | 锚外候选数 | 判定是否一致 |",
          "|---|" + "---:|" * len(efforts) + "---:|:-:|"]
    n_consistent = 0
    for aid in ans_ids:
        if aid not in out:
            continue
        cells = []
        n_out = 0
        sets = []
        for e in efforts:
            r = out[aid].get(e) or {}
            cells.append(str(r.get("n_pass")))
            n_out = max(n_out, r.get("n_out_cand") or 0)
            sets.append((r.get("n_pass"), r.get("n_out_cand")))
        same = len(set(sets)) == 1
        n_consistent += 1 if same else 0
        md.append("| %s | %s | %d | %s |" % (aid, " | ".join(cells), n_out,
                                            "✔" if same else "**✘ 不同**"))
    md.append("\n> 档位间读数**一致**的答案：%d/%d ⇒ 不一致即说明 `VD_anchor_out` **对思考深度敏感**\n"
              % (n_consistent, len([a for a in ans_ids if a in out])))
    md.append("\n## 逐份明细（锚外候选与闸门）\n")
    for aid in ans_ids:
        if aid not in out:
            continue
        md.append("\n### %s\n" % aid)
        for e in efforts:
            r = out[aid].get(e) or {}
            md.append("**effort=%s** ｜ OUT=%s ｜ 卡=%s ｜ 锚外候选=%s ｜ parsefail=%s ｜ 通道健康度=%s\n"
                      % (e, r.get("n_pass"), r.get("n_cards"), r.get("n_out_cand"),
                         r.get("parsefail_rate"), r.get("channel_health")))
            for c in (r.get("cards_digest") or []):
                if str(c.get("anchor")).lower() == "out":
                    md.append("  - 判为 anchor=out：%s\n" % (c.get("claim") or "")[:70])
    with open(os.path.join(args.out, "effort_sweep.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print("\n✓ 落盘 %s（耗时 %.0fs）" % (args.out, dt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
