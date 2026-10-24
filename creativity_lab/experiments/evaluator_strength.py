#!/usr/bin/env python3
"""**评估器强度 × 末步取舍**（零生成成本；ToT 式 value / vote 双评估器）

> 2026-10-24 ｜ 第二组 · 层2 ｜ 落点：`creativity_lab/experiments/evaluator_strength.py`
>
> ## 动机（这轮实验是被一个自我批评逼出来的）
> 上一轮 4 臂对照里，「选一臂」这条臂的**选择器 = `distinctness_scores`**
> （词块 Jaccard 最小距离 ⇒ 纯词面、无语义、不看质量）⇒ **是个极弱的评估器**。
> ⇒ 我把「选择器」当成了**常量**而不是**变量** ⇒ ⇒
> **「选」这条臂的收益上限，我根本没测到** ⇒ ⇒ 报告里「融合门是双输」这句结论，
> **隐含前提是"我的评估器很弱"** ⇒ 必须补测。
>
> ## 为什么能用 ToT 的组件
> ToT 论文原话（已一手核实，PDF p.6 / Appendix B.2）：
> > "best of 100 CoT samples achieve a success rate of 49%, but still much worse than
> >  exploring more nodes in ToT (b > 1)"
> > "This suggests the game's bottleneck is **thought generation**"
> ⇒ 「多采样 + 选」与「搜索」之间有明确差距（49% → 74%）⇒
> ⇒ **同一批生成结果，换评估器，分数就变（74% / 64% / 31%）** ⇒
> ⇒ **评估器强度是主变量** ⇒ 而 ToT 的 **value + vote 双评估器是现成的**。
>
> ## ★ 本实验是**自足**的（不需要外部基准、不需要跨厂商判官）
> 因变量不是"哪个评估器更好"（那需要质量基准），而是
> **「换了评估器，被选中的那一支变没变」** ⇒ 这是**评估器之间的一致性**。
> ⇒ ⇒ OpenRouter 额度耗尽（limit_remaining=0）也不影响本实验。
>
> ## ★ 硬闸（沿用第四组的纪律）
> 1. **位置去偏**：vote 同一组跑两个不同排列（order A / order B）⇒ 位置一致率
> 2. **一致率 < 0.5 ⇒ 判"在随机作答" ⇒ 该对比直接判不可用**，不得计入结论
> 3. **两票不一致 ⇒ 该组 vote 读数不可用**（不强行挑一个）
> 4. **通道健康度 < 0.9 ⇒ 全部读数不生效**（写"不能据此说成立或不成立"）
>
> ## 评估器
> | 评估器 | 机制 | 额外 LLM 调用/组 |
> |---|---|--:|
> | `lex` | 词块独特度（上一轮用的弱评估器） | 0 |
> | `value` | ToT 式 **value**：对每支**独立**打分，取最高 | 5 |
> | `vote` | ToT 式 **vote**：一次比较 5 支选 1（**两个排列各跑一次**） | 2 |
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.client import DEFAULT_EFFORT, LLM                    # noqa: E402
from creativity_lab.gates.base import Select                            # noqa: E402
from creativity_lab.metrics import (branch_diversity, covered_branches,  # noqa: E402
                                    coverage_curve, distinctness_scores,
                                    emb_coverage, fixed_len_coverage,
                                    survival_rate)
from creativity_lab.prompts import VALUE_Q, VOTE_Q                      # noqa: E402
from creativity_lab.experiments import guard_io  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "runs", "endstep-matrix-2026-10-23")
THR = 0.30


def parse_json(text: str) -> dict:
    """从模型输出里抠出 JSON（容忍 think 块/前后废话）。"""
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    t = re.sub(r"^.*?</think>", "", t, flags=re.S).strip()
    m = re.search(r"\{.*\}", t, flags=re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:                                    # noqa: BLE001
        return {}


def arm_readings(arts: List[str], out: str, embed_fn) -> dict:
    """用**同一套**指标口径给一个末步输出算读数（与上一轮表可比）。"""
    if not out:
        return {"valid": False}
    cov = covered_branches(arts, out, THR)
    return {"valid": True, "text": out,
            "covered_branches": cov,
            "survival_rate": round(survival_rate(arts, out), 4),
            "coverage_curve": coverage_curve(arts, out),
            "out_chars": len(out),
            "emb": emb_coverage(arts, out, embed_fn),
            "fixed_len": [fixed_len_coverage(arts, out, L) for L in (300, 400, 600)]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default="runs/evaluator-strength-2026-10-24")
    ap.add_argument("--model", default="MiniMax-M3")
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
    a = ap.parse_args()

    out_dir = os.path.join(ROOT, a.out)
    os.makedirs(out_dir, exist_ok=True)
    llm = LLM()
    emb_llm = LLM()

    def embed_fn(ts):
        return emb_llm.embed(list(ts))

    groups: List[Dict[str, Any]] = []
    # ★★★ 输入/输出隔离（★ 2026-10-24 统一形态：★ 解析输入的同一处就断言）
    # ★★★ ★ 特别提醒：★ 本工具【写出的也是 group_*.json】⇒ ⇒ ★ 「文件名过滤」救不了它
    # ★★★ ★ 真正救它的是【输出目录 ≠ 输入目录】⇒ ⇒ ★ ⇒ 所以这里必须做【目录级 realpath 断言】
    guard_io.assert_output_outside_input_dir(SRC, out_dir, "evaluator_strength")
    for f in sorted(os.listdir(SRC)):
        if not f.startswith("group_"):
            continue
        g = json.load(open(os.path.join(SRC, f), encoding="utf-8"))
        arts = g.get("arts") or []
        if len(arts) < 3:
            continue
        g["_file"] = f
        groups.append(g)
    print("载入 %d 组，每组 %d 支" % (len(groups), len(groups[0]["arts"]) if groups else 0))

    for g in groups:
        arts = g["arts"]
        n = len(arts)
        res: Dict[str, Any] = {}
        # ---- lex（弱评估器，零调用）----
        sc = distinctness_scores(arts)
        res["lex"] = {"pick": Select(mode="greedy")(sc)[0], "calls": 0}
        # ---- value（ToT 式独立打分）----
        t0 = time.time()
        vals = []
        for i, art in enumerate(arts):
            raw = llm.chat(VALUE_Q.format(cand=art[:1200]), model=a.model,
                           purpose="value:%d" % i, effort=a.effort,
                           min_ok=20)   # ★ 短输出：默认 200 会把成功误判为失败
            j = parse_json(raw)
            try:
                s = float(j.get("score", 0))
            except Exception:                            # noqa: BLE001
                s = 0.0
            vals.append(s)
        best = max(range(n), key=lambda i: (vals[i], -i))
        res["value"] = {"pick": best, "scores": vals, "calls": n,
                        "secs": round(time.time() - t0, 1)}
        # ---- vote（两个排列 ⇒ 位置去偏）----
        orders = [list(range(n)), list(range(n))[::-1]]
        picks, raw_pick = [], []
        t0 = time.time()
        for oi, order in enumerate(orders):
            shown = "\n\n".join("[第%d篇]\n%s" % (k + 1, arts[j]) for k, j in enumerate(order))
            raw = llm.chat(VOTE_Q.format(arts=shown, n=n), model=a.model,
                           purpose="vote:%d" % oi, effort=a.effort,
                           min_ok=20)   # ★ 同上
            j = parse_json(raw)
            try:
                p = int(j.get("pick", 0)) - 1
            except Exception:                            # noqa: BLE001
                p = -1
            if not (0 <= p < n):
                p = -1
            raw_pick.append(p)
            picks.append(order[p] if p >= 0 else -1)
        pos_ok = (picks[0] == picks[1] and picks[0] >= 0)
        res["vote"] = {"picks": picks, "raw_pick": raw_pick, "calls": 2,
                       "position_consistent": pos_ok,
                       "pick": picks[0] if pos_ok else -1,
                       "secs": round(time.time() - t0, 1)}
        # ---- 读数（用各评估器选出的那一支作末步输出）----
        g["evaluators"] = res
        g["readings"] = {}
        for ev, d in res.items():
            if d.get("pick", -1) < 0:
                g["readings"][ev] = {"valid": False,
                                     "reason": "position_inconsistent" if ev == "vote" else "no_pick"}
                continue
            g["readings"][ev] = arm_readings(arts, arts[d["pick"]], embed_fn)
        g["branch_diversity"] = round(branch_diversity(arts), 4)
        with open(os.path.join(out_dir, "group_%s_r%d.json" % (g["tid"], g["rep"])),
                  "w", encoding="utf-8") as fh:
            json.dump(g, fh, ensure_ascii=False, indent=2, sort_keys=True)
        print("  %s r%d | lex=%s value=%s vote=%s %s" %
              (g["tid"], g["rep"], res["lex"]["pick"], res["value"]["pick"], res["vote"]["picks"],
               ("✔位置一致" if res["vote"]["position_consistent"] else "✘位置不一致⇒不可用")))

    # ---- 一致率 ----
    evs = ["lex", "value", "vote"]
    agree: Dict[str, int] = {}
    tot = 0
    for i in range(len(evs)):
        for j in range(i + 1, len(evs)):
            k = "%s|%s" % (evs[i], evs[j])
            c = 0
            for g in groups:
                a1 = g["evaluators"][evs[i]].get("pick", -1)
                a2 = g["evaluators"][evs[j]].get("pick", -1)
                if a1 >= 0 and a2 >= 0 and a1 == a2:
                    c += 1
            agree[k] = c
            tot += 1
    pos_c = sum(1 for g in groups if g["evaluators"]["vote"]["position_consistent"])
    health = {"n_groups": len(groups),
              "n_calls_total": len(llm.rec),
              # ★ 健康度 = **传输成功率**（has_content），不是"内容长度达标率"
              "n_calls_failed": sum(1 for c in llm.rec if not c.has_content),
              "n_calls_empty": sum(1 for c in llm.rec if c.content_len == 0),
              "n_calls_ok_len": sum(1 for c in llm.rec if c.ok),
              "channel_health": round(1 - sum(1 for c in llm.rec if not c.has_content) / max(len(llm.rec), 1), 4),
              "position_consistency": round(pos_c / max(len(groups), 1), 4),
              "pairwise_agreement": {k: round(v / max(len(groups), 1), 4) for k, v in agree.items()},
              "model": a.model, "effort": a.effort}
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"health": health,
                   "groups": [{k: v for k, v in g.items() if k != "arts"} for g in groups]},
                  f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "calllog.jsonl"), "w", encoding="utf-8") as f:
        for c in llm.rec:
            f.write(json.dumps(c.__dict__, ensure_ascii=False) + "\n")
    print("\n== 通道与一致性 ==")
    for k, v in health.items():
        print("  %-24s %s" % (k, v))
    print("\n✓ 落盘 %s" % out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
