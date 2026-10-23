#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · v5 分析：全部主读数零判官（声明是编号离散结构；兑现/违禁由代码核验）。

读数（对照 PREREG_v5.md）：
  H1′  声明解析成功率
  H2′  兑现率（声明写透 ⇒ 正文真写了）
  H3′′ 违禁率（声明放弃 ⇒ 正文却写了）
  ★H3′ 状态化 vs 通用（同池 gap）—— 判决在 WF-v5 臂内
  ★地板 WF-v5-blind 臂的 align（盲选时）
  ★状态信息增量 = align(WF-v5) − align(WF-v5-blind)
  诊断：声明多样性、候选相似度、决策退化（无取舍代价的样本）
"""
import argparse
import json
import os
import statistics as stx
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import workflow_arch5 as WA5          # noqa: E402


def agg(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "mean": round(sum(vals) / len(vals), 4),
            "min": round(min(vals), 4), "max": round(max(vals), 4),
            "median": round(stx.median(vals), 4)}


def fisher_2x2(a, b, c, d):
    from math import comb
    n = a + b + c + d
    r1, r2 = a + b, c + d
    c1 = a + c

    def p(x):
        return (comb(r1, x) * comb(r2, c1 - x)) / comb(n, c1)
    obs = p(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return round(sum(p(x) for x in range(lo, hi + 1)
                     if p(x) <= obs * (1 + 1e-9)), 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", default=os.path.join(HERE, "runs", "arch5_compare.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch5_analysis.json"))
    args = ap.parse_args()

    recs = []
    with open(args.inp, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                recs.append(json.loads(ln))
    # 每题只保留最新批次
    by_topic = defaultdict(list)
    for r in recs:
        by_topic[r.get("topic_id", "?")].append(r)
    latest = {}
    for tid, rs in by_topic.items():
        bids = sorted({r.get("batch_id", "") for r in rs})
        latest[tid] = bids[-1] if bids else ""
    recs = [r for r in recs if r.get("batch_id") == latest[r.get("topic_id", "?")]]

    res = {"n_records": len(recs), "batches": latest, "per_sample": [], "per_topic": {}}

    wf = [r for r in recs if str(r.get("arm", "")).startswith("WF-v5")]
    per = []
    for r in wf:
        if r.get("error"):
            per.append({"topic": r.get("topic_id"), "tag": r.get("tag"),
                        "arm": r.get("arm"), "error": r.get("error")})
            continue
        st = WA5.State5.from_dict(r.get("state") or {})
        cands = r.get("candidates") or []
        decls = [tuple(sorted(c.get("decl_write") or [])) +
                 tuple(sorted(c.get("decl_drop") or [])) for c in cands]
        item = {
            "topic": r.get("topic_id"), "tag": r.get("tag"), "arm": r.get("arm"),
            "blind": r.get("blind"),
            "n_gaps": len(st.gaps), "n_decisions": len(st.decisions),
            "deep_set": sorted(st.deep_set()), "drop_set": sorted(st.drop_set()),
            "has_tradeoff_cost": bool(st.drop_set()),
            "n_cand": len(cands),
            "n_decl_parsed": sum(1 for c in cands if c.get("decl_parsed")),
            "H1_decl_parse_rate": (sum(1 for c in cands if c.get("decl_parsed")) / len(cands)
                                   if cands else None),
            "decl_distinct": len(set(decls)),
            "decls": [list(d) for d in decls],
            "chosen_state_idx": r.get("chosen_state_idx"),
            "chosen_generic_idx": r.get("chosen_generic_idx"),
            "same_choice": r.get("chosen_state_idx") == r.get("chosen_generic_idx"),
            "align_state": r.get("align_state"),
            "align_generic": r.get("align_generic"),
            "H3p_gap": (None if r.get("align_state") is None or r.get("align_generic") is None
                        else round(r["align_state"] - r["align_generic"], 4)),
            "fulfill_state": r.get("fulfill_state"),
            "fulfill_generic": r.get("fulfill_generic"),
            "violation_state": r.get("violation_state"),
            "violation_generic": r.get("violation_generic"),
            "cand_sim_mean": (round(sum(r.get("candidate_pair_sim") or [0]) /
                                    max(1, len(r.get("candidate_pair_sim") or [1])), 4)),
        }
        per.append(item)
    res["per_sample"] = per
    ok = [p for p in per if "error" not in p]

    # ---------------- 汇总 ----------------
    s = {
        "H1_decl_parse_rate": agg([p["H1_decl_parse_rate"] for p in ok]),
        "decl_distinct": agg([p["decl_distinct"] for p in ok]),
        "align_state": agg([p["align_state"] for p in ok]),
        "align_generic": agg([p["align_generic"] for p in ok]),
        "H3p_gap": agg([p["H3p_gap"] for p in ok]),
        "fulfill_state": agg([p["fulfill_state"] for p in ok]),
        "fulfill_generic": agg([p["fulfill_generic"] for p in ok]),
        "violation_state": agg([p["violation_state"] for p in ok]),
        "violation_generic": agg([p["violation_generic"] for p in ok]),
        "cand_sim_mean": agg([p["cand_sim_mean"] for p in ok]),
        "n_has_tradeoff_cost": sum(1 for p in ok if p["has_tradeoff_cost"]),
        "n_no_tradeoff_cost": sum(1 for p in ok if not p["has_tradeoff_cost"]),
        "n_errors": len([p for p in per if "error" in p]),
    }
    w = {"state": 0, "generic": 0, "tie": 0}
    for p in ok:
        g = p["H3p_gap"]
        if g is None:
            continue
        if g > 1e-9:
            w["state"] += 1
        elif g < -1e-9:
            w["generic"] += 1
        else:
            w["tie"] += 1
    s["H3p_wins"] = w
    s["same_choice_rate"] = (round(sum(1 for p in ok if p["same_choice"]) / len(ok), 4)
                              if ok else None)
    res["summary"] = s

    # ---------------- 分臂 ----------------
    res["per_arm"] = {}
    for arm in sorted({p["arm"] for p in ok}):
        ps = [p for p in ok if p["arm"] == arm]
        g = [p["H3p_gap"] for p in ps if p["H3p_gap"] is not None]
        ww = {"state": 0, "generic": 0, "tie": 0}
        for x in g:
            if x > 1e-9:
                ww["state"] += 1
            elif x < -1e-9:
                ww["generic"] += 1
            else:
                ww["tie"] += 1
        n_nt = ww["state"] + ww["generic"]
        res["per_arm"][arm] = {
            "n": len(ps),
            "align_state": agg([p["align_state"] for p in ps]),
            "align_generic": agg([p["align_generic"] for p in ps]),
            "H3p_gap": agg(g),
            "wins": ww,
            "non_tie_rate": (round(ww["state"] / n_nt, 4) if n_nt else None),
            "H1_decl_parse_rate": agg([p["H1_decl_parse_rate"] for p in ps]),
            "fulfill_state": agg([p["fulfill_state"] for p in ps]),
            "violation_state": agg([p["violation_state"] for p in ps]),
            "decl_distinct": agg([p["decl_distinct"] for p in ps]),
            "has_tradeoff_cost": sum(1 for p in ps if p["has_tradeoff_cost"]),
        }
    # ★ 状态信息增量（跨臂，同题同模型）
    v5 = res["per_arm"].get("WF-v5", {})
    bl = res["per_arm"].get("WF-v5-blind", {})
    if v5.get("align_state", {}).get("n") and bl.get("align_state", {}).get("n"):
        res["state_info_gain"] = {
            "align_WF_v5": v5["align_state"]["mean"],
            "align_WF_v5_blind_floor": bl["align_state"]["mean"],
            "gain": round(v5["align_state"]["mean"] - bl["align_state"]["mean"], 4),
            "ratio": (round(v5["align_state"]["mean"] / bl["align_state"]["mean"], 3)
                      if bl["align_state"]["mean"] else None),
        }

    # ---------------- 逐题 ----------------
    by_t = defaultdict(list)
    for p in ok:
        by_t[p["topic"]].append(p)
    for tid, ps in sorted(by_t.items()):
        res["per_topic"][tid] = {
            "n": len(ps),
            "align_state": agg([p["align_state"] for p in ps]),
            "align_generic": agg([p["align_generic"] for p in ps]),
            "H3p_gap": agg([p["H3p_gap"] for p in ps]),
            "H1_decl_parse_rate": agg([p["H1_decl_parse_rate"] for p in ps]),
            "fulfill_state": agg([p["fulfill_state"] for p in ps]),
            "has_tradeoff_cost": sum(1 for p in ps if p["has_tradeoff_cost"]),
        }
    # 其他臂
    res["other_arms"] = {}
    arm_len = defaultdict(list)
    for r in recs:
        if r.get("error"):
            continue
        arm_len[r.get("arm")].append(len((r.get("text") or "").strip()))
    for arm, v in sorted(arm_len.items()):
        res["other_arms"][arm] = {"n": len(v), "len_mean": round(sum(v) / len(v), 1)}
    res["errors"] = [{"topic": r.get("topic_id"), "tag": r.get("tag"), "arm": r.get("arm"),
                      "error": r.get("error")} for r in recs if r.get("error")]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    print("=" * 74)
    print("v5 分析（零判官）｜ 批次: %s" % latest)
    print("=" * 74)
    print("WF-v5 有效样本 %d ｜ 失败 %d" % (len(ok), s["n_errors"]))
    print("-- H1′ 声明解析成功率        : %s" % s["H1_decl_parse_rate"])
    print("-- 声明多样性(不同声明数/3) : %s" % s["decl_distinct"])
    print("-- align(状态化选择)         : %s" % s["align_state"])
    print("-- align(通用选择)           : %s" % s["align_generic"])
    print("-- ★H3′ 同池 gap             : %s" % s["H3p_gap"])
    print("-- ★H3′ 胜负 state/gen/tie   : %s" % s["H3p_wins"])
    print("-- H2′ 兑现率(state选)       : %s" % s["fulfill_state"])
    print("-- H3′′ 违禁率(state选)      : %s" % s["violation_state"])
    print("-- 有/无取舍代价样本         : %d / %d" % (s["n_has_tradeoff_cost"],
                                                    s["n_no_tradeoff_cost"]))
    print("-- 候选相似度均值            : %s" % s["cand_sim_mean"])
    print("-- 分臂:")
    for arm, v in res["per_arm"].items():
        print("     %-14s n=%d align(s)=%s align(g)=%s gap=%s 胜/负/平=%s 非平率=%s 兑现=%s 违禁=%s" % (
            arm, v["n"], v["align_state"].get("mean"), v["align_generic"].get("mean"),
            v["H3p_gap"].get("mean"), v["wins"], v["non_tie_rate"],
            v["fulfill_state"].get("mean"), v["violation_state"].get("mean")))
    if "state_info_gain" in res:
        g = res["state_info_gain"]
        print("-- ★状态信息增量: %s − %s = %s (×%s)" % (
            g["align_WF_v5"], g["align_WF_v5_blind_floor"], g["gain"], g["ratio"]))
    print("-- 逐题:")
    for tid, v in res["per_topic"].items():
        print("     %-5s n=%d align(s)=%s gap=%s 兑现=%s 有代价=%d" % (
            tid, v["n"], v["align_state"].get("mean"), v["H3p_gap"].get("mean"),
            v["fulfill_state"].get("mean"), v["has_tradeoff_cost"]))
    print("\n[out] %s" % args.out)


if __name__ == "__main__":
    main()
