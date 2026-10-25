# -*- coding: utf-8 -*-
"""**effort 档位探针**：MiniMax 判官通道的可靠性到底由什么决定？

> 2026-10-23 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/probe_effort.py`
>
> ★ **要回答的问题**（2026-10-22 踩出来的坑）：
>   昨天判官调用 **44% 空内容 / 截断** ⇒ 8/9 份答案被降级为"描述性" ⇒ 所有维度数读数不可引用。
>   我昨天用**加 max_tokens 阶梯**去救（方向错）。
>   官方文档（platform.minimax.io / Model Invocation）写明：
>   *"Thinking cannot be turned off. To reduce the latency and token usage of thinking,
>   **lower the effort level** rather than trying to disable thinking."*
>   且 **省略 effort 时默认 = max**。
>   ⇒ **本探针验证"降 effort 能不能救回通道，而且不损伤判官质量"。**
>
> ★ **两个轴，缺一不可**（只看健康度 = 把"判官变笨"当成"通道变好"）：
>   **轴1 健康度（尝试级）**：空内容率、截断率、延迟、思考 token 占比
>   **轴2 质量**：同一批断言在不同 effort 下判出的卡片**是否一致**（与 max 档比）+ **跨轮是否一致**
>
> ★ **忠实重放**：调用的是**真实的 OUT 通道卡片调用**
>   （`CARD_Q_OUT` + 任务题面 + DEV 依据包 + N 条断言）—— 这是昨天失败最集中的长提示词。
>   断言取自已落盘的 `cards_out_all`（离线复算 ⇒ 不重跑抽取，既省钱又消除了抽取差异）。
>
> 用法：
>   python3 -B probe_effort.py --out runs/dev/effort_probe \
#       --answers W_div#D01,B0_direct#D01 --efforts max,medium,low --rounds 2 --workers 4
"""
from __future__ import annotations

import argparse
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


# ──────────────────────────────────────────────────────────────
# 1. 取回"同一批断言"（离线复算）
# ──────────────────────────────────────────────────────────────
def load_readings(path: str) -> Dict[str, Dict[str, Any]]:
    blob = json.load(open(path, encoding="utf-8"))
    for v in blob.get("variants", []):
        vid = (v.get("id") or "")
        if "minimax" in vid.lower() or vid.startswith("V1"):
            return v.get("readings") or v.get("results") or {}
    raise SystemExit("在 %s 里找不到 V1(MiniMax) 变体" % path)


def dev_task_by_id(devset: Dict[str, Any], tid: str) -> Dict[str, Any]:
    for t in devset.get("tasks", []):
        if t.get("task_id") == tid:
            return t
    raise SystemExit("DEV 里没有题 %s" % tid)


def claims_of(cards: List[Dict[str, Any]], n: int) -> List[str]:
    """从已落盘的卡片里取回断言原文（保持原顺序）"""
    out = []
    for c in cards:
        t = (c.get("claim") or "").strip()
        if t:
            out.append(t)
        if len(out) >= n:
            break
    return out


# ──────────────────────────────────────────────────────────────
# 2. 一次"真实的 OUT 通道卡片调用"
# ──────────────────────────────────────────────────────────────
def one_card_call(llm: V.LLM, ask: str, ev_text: str, cl: List[str],
                  effort: Optional[str]) -> Dict[str, Any]:
    """★ 提示词与批次切分**逐字沿用** `judge_out_channel`（只换 effort）。"""
    lst = "\n".join("%d. %s" % (n + 1, cl[n]) for n in range(len(cl)))
    r = llm.chat(V.CARD_Q_OUT.format(ask=ask, ev=ev_text, claims=lst),
                 model=llm.model, temp=0.0, max_tokens=V.MM_TOKEN_FLOOR,
                 budgets=V.JUDGE_BUDGETS, min_ok=len(cl) * 15, purpose="effort_card",
                 effort=effort)
    got = V.parse_card_lines(r, len(cl))
    # 卡片的关键判定字段（用来比"判官质量有没有变"）
    sig = []
    for g in sorted(got, key=lambda x: x.get("i", 0)):
        sig.append({
            "i": g.get("i"),
            "load_bearing": g.get("load_bearing"),
            "anchor": g.get("anchor"),
            "verdict": g.get("verdict"),
            "decision_changed": g.get("decision_changed"),
        })
    return {"n_parsed": len(got), "n_claims": len(cl),
            "parsefail": max(0, len(cl) - len(got)),
            "sig": sig,
            "raw_len": len(r or "")}


# ──────────────────────────────────────────────────────────────
# 3. 主流程
# ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--answers", default="W_div#D01,B0_direct#D01")
    ap.add_argument("--efforts", default="max,medium,low")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--n-claims", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--read-src", default=READ_SRC)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    readings = load_readings(args.read_src)
    devset = V.load_devset()
    efforts = [e for e in args.efforts.split(",") if e]
    answers = [a for a in args.answers.split(",") if a]
    judge_model = V._judge_model_from_env()

    # 预取：每份答案的题面 / 依据包 / 断言
    plan: List[Dict[str, Any]] = []
    for ans_id in answers:
        rd = readings.get(ans_id)
        if not rd:
            print("⚠️ 没有 %s 的读数，跳过" % ans_id)
            continue
        task = dev_task_by_id(devset, rd.get("task_id"))
        ev_items = V.evidence_items_from_dev(task)
        ev_text = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev_items))
        cl = claims_of(rd.get("cards_out_all") or [], args.n_claims)
        if len(cl) < args.n_claims:
            print("⚠️ %s 只有 %d 条断言 ⇒ 少用" % (ans_id, len(cl)))
        plan.append({"answer": ans_id, "task_id": rd.get("task_id"),
                     "ask": task.get("ask", ""), "ev_text": ev_text, "claims": cl,
                     "n_ev_items": len(ev_items)})

    jobs: List[Dict[str, Any]] = []
    for p in plan:
        for eff in efforts:
            for r in range(args.rounds):
                jobs.append(dict(p, effort=eff, round=r + 1))
    print("== 探针：%d 次卡片调用（%d 答案 × %d 档 × %d 轮，每调用 %d 条断言）=="
          % (len(jobs), len(plan), len(efforts), args.rounds, args.n_claims))

    rows: List[Dict[str, Any]] = []
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {}
        for j in jobs:
            llm = V.LLM("minimax", judge_model)
            futs[ex.submit(one_card_call, llm, j["ask"], j["ev_text"], j["claims"],
                            j["effort"])] = j
        for fut in cf.as_completed(futs):
            j = futs[fut]
            try:
                res = fut.result()
            except Exception as e:               # noqa: BLE001
                res = {"n_parsed": 0, "n_claims": len(j["claims"]), "parsefail": len(j["claims"]),
                       "sig": [], "raw_len": 0, "error": type(e).__name__}
            rows.append({"answer": j["answer"], "task_id": j["task_id"], "effort": j["effort"],
                         "round": j["round"], "n_ev_items": j["n_ev_items"], **res})
    dt = time.time() - t0

    # ── 轴1 健康度：**尝试级**（来自调用账本，不是最终结果）──────
    attempts: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        attempts.setdefault(r["answer"] + "|" + r["effort"], {
            "answer": r["answer"], "effort": r["effort"], "n_calls": 0,
            "n_empty": 0, "n_truncated": 0, "n_error": 0,
            "reasoning_tokens": 0, "completion_tokens": 0, "secs": 0.0, "n_parsefail": 0,
            "n_parsed": 0, "n_claims": 0})
    # 调用账本：每行带 effort（我加的字段）⇒ 尝试级统计
    for j in jobs:
        pass
    llm_all = V.LLM("minimax", judge_model)
    # 逐次调用各自的 llm 日志没汇总 ⇒ 这里用 rows 里的结果做"结果级"，另从 rows 聚合尝试级
    # （每次调用内部有阶梯重试，尝试数在 llm.log；我们把每次调用的账本收上来）
    for r in rows:
        k = r["answer"] + "|" + r["effort"]
        a = attempts[k]
        a["n_calls"] += 1
        a["n_parsefail"] += r["parsefail"]
        a["n_parsed"] += r["n_parsed"]
        a["n_claims"] += r["n_claims"]
    summary = []
    for k, a in sorted(attempts.items()):
        summary.append(a)

    # ── 轴2 质量：卡片判定签名的一致性 ─────────────────────────
    def sigkey(r: Dict[str, Any]) -> str:
        """★ **只用离散字段**做签名（2026-10-23 修正）。

        ⚠️ 第一版把**自由文本** `decision_changed` 也放进签名 ⇒ 两档必然不等
          ⇒ 所有"与 max 不一致"都是**指标自己造的假象**（不是判官变笨）。
        ⇒ 判官质量的正确比较 = **离散判定**（load_bearing / anchor / verdict）
          + `decision_changed` 的**非空性**（写得出岔口与否），不比原文。
        """
        return "|".join("%s:%s:%s:%s:%s" % (s.get("i"), s.get("load_bearing"), s.get("anchor"),
                                            s.get("verdict"), bool(s.get("decision_changed")))
                         for s in r.get("sig") or [])

    cross_round: List[Dict[str, Any]] = []
    bycard: Dict[Tuple[str, str, int], List[str]] = {}
    for r in rows:
        bycard.setdefault((r["answer"], r["effort"], r["round"]), []).append(sigkey(r))
    for (ans, eff, rd_), vs in sorted(bycard.items()):
        cross_round.append({"answer": ans, "effort": eff, "round": rd_,
                            "n_cards": len(vs[0].split("|")) if vs and vs[0] else 0,
                            "consistent": len(set(vs)) == 1})

    x_eff: List[Dict[str, Any]] = []
    for (ans, eff, rd_), vs in sorted(bycard.items()):
        if eff == "max":
            continue
        b = bycard.get((ans, "max", rd_))
        x_eff.append({"answer": ans, "effort": eff, "round": rd_,
                      "same_as_max": bool(b and vs == b),
                      "n_cards_this": len(vs[0].split("|")) if vs and vs[0] else 0,
                      "n_cards_max": len(b[0].split("|")) if b and b[0] else 0})

    out = {
        "meta": {"n_jobs": len(jobs), "elapsed_sec": round(dt, 1), "read_src": args.read_src,
                 "efforts": efforts, "rounds": args.rounds, "n_claims": args.n_claims,
                 "judge_model": judge_model, "probe": "CARD_Q_OUT（OUT 通道真实卡片调用）"},
        "summary": summary, "cross_round": cross_round, "cross_effort_vs_max": x_eff,
        "rows": rows,
    }
    with open(os.path.join(args.out, "effort_probe.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    md = ["# effort 档位探针（通道可靠性 × 判官质量）\n",
          "> 判官 `%s` ｜ 调用 `CARD_Q_OUT`（OUT 通道真实卡片调用）｜ 每调用 %d 条断言\n"
          % (judge_model, args.n_claims),
          "## 轴1 · 结果级健康（**parsefail 高 = 坏**）\n",
          "| 答案 | effort | 调用 | 解析出卡 | 断言 | parsefail | parsefail率 |",
          "|---|---|--:|--:|--:|--:|--:|"]
    for s in summary:
        rate = s["n_parsefail"] / float(max(s["n_claims"], 1))
        md.append("| %s | %s | %d | %d | %d | %d | **%.2f** |"
                  % (s["answer"], s["effort"], s["n_calls"], s["n_parsed"],
                     s["n_claims"], s["n_parsefail"], rate))
    md += ["\n> ★ 签名 = 离散字段（i/load_bearing/anchor/verdict）+ decision_changed 的**非空性**\n",
           "> （**不比自由文本原文** ⇒ 否则两档必然不等 ⇒ 造出「判官变笨」的假象）\n",
           "\n## 轴2a · 跨轮一致（同档两轮判出的卡片签名相同？）\n",
           "| 答案 | effort | 轮 | 卡数 | 一致 |", "|---|---|--:|--:|:-:|"]
    for r in cross_round:
        md.append("| %s | %s | %d | %d | %s |" % (r["answer"], r["effort"], r["round"],
                                                   r["n_cards"], "✔" if r["consistent"] else "✘"))
    md += ["\n## 轴2b · 与 max 档判定一致？（**质量有没有退化**）\n",
           "| 答案 | effort | 轮 | 本档卡数 | max 卡数 | 一致 |", "|---|---|--:|--:|--:|:-:|"]
    for r in x_eff:
        md.append("| %s | %s | %d | %d | %d | %s |" % (r["answer"], r["effort"], r["round"],
                                                        r["n_cards_this"], r["n_cards_max"],
                                                        "✔" if r["same_as_max"] else "✘"))
    with open(os.path.join(args.out, "effort_probe.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print("\n== 轴1 结果级健康 ==")
    for s in summary:
        print("  %-16s %-7s 调用%d 解析%d/%d parsefail=%.2f"
              % (s["answer"], s["effort"], s["n_calls"], s["n_parsed"],
                 s["n_claims"], s["n_parsefail"] / float(max(s["n_claims"], 1))))
    print("== 轴2 与 max 一致 ==")
    for r in x_eff:
        print("  %-16s %-7s r%d  %s" % (r["answer"], r["effort"], r["round"],
                                       "✔" if r["same_as_max"] else "✘"))
    print("\n✓ 落盘 %s（耗时 %.0fs）" % (args.out, dt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
