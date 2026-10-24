#!/usr/bin/env python3
"""**判别实验 · 基线多样性水平 → 支间重叠度 / 论证路径数**（一张表解决 C1）

> 落点：`creativity_lab/experiments/cogpos_matrix.py`
> 触发：2026-10-24 跨组 C1 冲突（三组「认知位置/认知帧」vs 第二组「认知框架」结论相反）
> 依据：主会话裁决 —— 差异主因 = **指标口径** + **实验设计（基线多样性水平）**，
> 且要求「同一题集、同时测两个量、基线跨三个多样性水平」
>
> ## ★ 为什么必须做（★ 这是本实验存在的唯一理由）
> | | 基线 | 支间重叠度 | 论证路径数 |
> |---|---|--:|--:|
> | 三组 | **同模型直调 3 次** | **0.41–0.61** | （未测） |
> | 我（前几轮） | **5 框架 + 5 型号** | **0.05–0.12** | 4–7 模态 |
> ⇒ ⇒ **两边的基线多样性水平本身差一个数量级** ⇒ ⇒
> **"支间重叠度"不是绝对量，而是相对于基线多样性水平的量** ⇒ ⇒
> ⇒ ★ 所以"3 次独立直调重叠 0.41–0.61 ⇒ 独立采样不独立"**在他们的基线上成立，
> 但可能只是"同模型重复采样本就共享 prior"的平凡结果**；
> ⇒ 而"认知位置真的把 prior 改掉了"这个更强的说法，
> **必须在基线多样性变化的条件下才说得清**。
>
> ## ★ 臂 = **基线多样性水平的一条轴**（★ 每个臂都同时测两个量）
> | 臂 | 处理 | 分支来源 | n | 预期支间重叠度 |
> |---|---|---|--:|--:|
> | `direct_b3` | **直调 × 3 重复**（同模型、重复采样） | 无框架无 persona | 3 | ★ **≈0.4–0.6（三组量级）** |
> | `models_b5` | 5 型号 + **单**框架 + 5 persona | 换型号 | 5 | 中 |
> | `frames_b5` | 单型号 + **5 认知框架** | 换框架 | 5 | 中低 |
> | `cogpos_b5` | ★ **认知位置/认知帧**（三组处理变量） | 认知位置 | 5 | ★ **应显著低于 direct_b3** |
> | `base_b5` | 5 框架 + 5 型号 + 5 persona（我原基线） | 全换 | 5 | ★ **≈0.05–0.12** |
>
> ## ★ 两道必答的问题（主会话推论 (a)(b)(c)）
> - **(a)** `direct_b3` 的重叠度是否 ≈ 三组的 0.41–0.61？⇒ 若是 ⇒ 三组"独立采样不独立"是**同模型重复采样的平凡结果**
> - **(b)** `cogpos_b5` 相对 `direct_b3` 的增量，在**基线多样性水平变化**后还剩多少？⇒
> - **(c)** **重叠度与路径数是否解耦**？⇒ ★ 这才是 C1 的核心：两个量是不是同一个东西
>
> ## ⚠️ 口径纪律
> - **重叠度用比值型量**（`lexical_sharing` / `branch_diversity`）⇒ 跨 n 可比
> - **路径数用 `modes`（字面模态数）+ Vendi + self-BLEU** ⇒ ★ **Vendi 的 n 基线必须减掉**
>   （基线见 `runs/n-baseline-2026-10-24/n_baseline.json`）
> - ⇒ **每个臂都报 `n_calls`**，调用数不同 ⇒ 预算不可直接比
> - ⇒ `cogpos_b5` 的 prompt **必须与三组逐字一致** ⇒ ★ 已在文件头标注**待替换点**；
#   三组未回信前，跑的是**仓内 `FRAMES` 版本**（很可能是同一个资产，待确认）
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.arms.dual import _branch_specs          # noqa: E402
from creativity_lab.client import DEFAULT_EFFORT, LLM      # noqa: E402
from creativity_lab.metrics import effective_rank, modes    # noqa: E402
from creativity_lab.metrics_ext import (distinct_n, self_bleu,  # noqa: E402
                                         vendi_score)
from creativity_lab.prompts import BRANCH_ASK, OUT_SPEC     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARMS = ["direct_b3", "models_b5", "frames_b5", "cogpos_b5", "base_b5"]
ARMS = ARMS  # noqa

# ★★ 待替换点：认知位置/认知帧的 prompt 模板
#    三组（session 451241289920777）的原文一到，**逐字替换这里**再重跑本臂。
#    当前用仓内 `prompts.py::FRAMES`（推测为同一资产，**待三组确认**）。
COGPOS_TEMPLATE = None      # None ⇒ 走 FRAMES 路径

MODEL_POOL = ["MiniMax-M3"]


def lexical_sharing(arts: List[str]) -> float:
    from creativity_lab.metrics import keywords
    if len(arts) < 2:
        return 0.0
    ks = [keywords(a) for a in arts]
    vals = []
    for i in range(len(arts)):
        for j in range(i + 1, len(arts)):
            u = len(ks[i] | ks[j])
            vals.append((len(ks[i] & ks[j]) / u) if u else 0.0)
    vals.sort()
    return float(vals[len(vals) // 2])


def branch_diversity(arts: List[str]) -> float:
    """两两 2-gram Jaccard **距离**的中位（越大越不同）。"""
    from creativity_lab.metrics import keywords
    if len(arts) < 2:
        return 0.0
    ks = [keywords(a) for a in arts]
    vals = []
    for i in range(len(arts)):
        for j in range(i + 1, len(arts)):
            u = len(ks[i] | ks[j])
            vals.append(1.0 - (len(ks[i] & ks[j]) / u if u else 0.0))
    vals.sort()
    return float(vals[len(vals) // 2])


def build_specs(arm: str, alive: List[str]) -> List[tuple]:
    """按臂构造分支扇出。★ 每一臂只改"分支来源"这一个因子。"""
    base = _branch_specs()
    if arm == "direct_b3":
        # ★ 直调：同模型、**无框架无 persona**，3 个独立重复采样
        return [(base[0][0], alive[0], "") for _ in range(3)]
    if arm == "models_b5":
        # 换型号（单框架、5 persona）
        return [(base[0][0], alive[i % len(alive)], base[i % len(base)][2])
                for i in range(5)]
    if arm == "frames_b5":
        # 换认知框架（单型号、5 persona）
        return [(base[i % len(base)][0], alive[0], base[i % len(base)][2])
                for i in range(5)]
    if arm == "cogpos_b5":
        # ★ 认知位置/认知帧（照抄三组的处理变量；★ 与 frames_b5 的差别 = 待三组确认）
        return [(base[i % len(base)][0], alive[0], base[i % len(base)][2])
                for i in range(5)]
    if arm == "base_b5":
        return [base[i % len(base)] for i in range(5)]
    raise ValueError(arm)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", default="creativity_lab/data/topics_2x2.json")
    ap.add_argument("--only-tid", default="")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--model", default="MiniMax-M3")
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", default="runs/cogpos-matrix-2026-10-24")
    a = ap.parse_args()

    topics = json.load(open(os.path.join(ROOT, a.topics), encoding="utf-8"))
    if isinstance(topics, dict):
        topics = topics.get("topics", topics.get("items", []))
    if a.only_tid:
        keep = set(a.only_tid.split(","))
        topics = [t for t in topics if t.get("tid") in keep]
    arms = [x for x in a.arms.split(",") if x]

    llm = LLM()
    emb_llm = LLM()
    outdir = os.path.join(ROOT, a.out)
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "runs", "logs"), exist_ok=True)
    logf = open(os.path.join(ROOT, "runs", "logs", "cogpos-matrix.log"), "a", encoding="utf-8")

    def log(m):
        print(m, flush=True)
        logf.write(m + "\n")
        logf.flush()

    log("题：%s｜rep=%d｜臂：%s" % ([t["tid"] for t in topics], a.reps, arms))
    groups: List[Dict[str, Any]] = []

    for topic in topics:
        for rep in range(1, a.reps + 1):
            g: Dict[str, Any] = {"tid": topic["tid"], "rep": rep, "arms": {}}
            for arm in arms:
                specs = build_specs(arm, MODEL_POOL)
                prompts = []
                for frm, mdl, p in specs:
                    if arm == "direct_b3":
                        # ★ 直调：无框架无 persona ⇒ 走"纯题目"提示
                        prompts.append(
                            "问题：\n%s\n\n请直接写出**完整的答复本身**。\n%s"
                            % (topic["ask"], OUT_SPEC))
                    else:
                        prompts.append(BRANCH_ASK.format(
                            topic=topic["ask"], frame_name=frm["name"],
                            frame_text=frm["text"], persona=p, spec=OUT_SPEC,
                            extra="\n直接写出**完整的答复本身**，不要写判断片段。"))
                n0 = len(llm.rec)
                t0 = time.time()
                with ThreadPoolExecutor(max_workers=a.workers) as ex:
                    outs = list(ex.map(
                        lambda i: llm.chat(prompts[i], model=specs[i][1],
                                           purpose="cogpos:%s" % arm),
                        range(len(prompts))))
                arts = [o for o in outs if o.strip()]
                d: Dict[str, Any] = {"n_expected": len(specs), "n_arts": len(arts),
                                     "n_calls": len(llm.rec) - n0,
                                     "secs": round(time.time() - t0, 1),
                                     "models": [s[1] for s in specs],
                                     "frames": [s[0]["name"] for s in specs]}
                if len(arts) >= 2:
                    vecs = emb_llm.embed(list(arts))
                    d["valid"] = True
                    d["modes"] = modes(vecs)
                    d["vendi"] = round(vendi_score(vecs), 4)
                    d["self_bleu"] = round(self_bleu(arts), 4)
                    d["distinct_2"] = round(distinct_n(arts, 2), 4)
                    d["effective_rank"] = round(effective_rank(vecs), 4)
                    d["lexical_sharing"] = round(lexical_sharing(arts), 4)
                    d["branch_diversity"] = round(branch_diversity(arts), 4)
                else:
                    d["valid"] = False
                    d["reason"] = "too_few_arts(%d)" % len(arts)
                d["arts"] = arts
                g["arms"][arm] = d
                log("  %s r%d %-11s 支=%d/%d 共享度=%.4f 差异=%.4f 模态=%s Vendi=%s (%.0fs)"
                    % (topic["tid"], rep, arm, d["n_arts"], d["n_expected"],
                       d.get("lexical_sharing", -1), d.get("branch_diversity", -1),
                       d.get("modes"), d.get("vendi"), d["secs"]))
            with open(os.path.join(outdir, "group_%s_r%d.json" % (topic["tid"], rep)),
                      "w", encoding="utf-8") as f:
                json.dump(g, f, ensure_ascii=False, indent=1, sort_keys=True)
            groups.append(g)

    tot = sum((g["arms"].get(x, {}) or {}).get("n_calls", 0) for g in groups for x in arms)
    failed = sum(1 for c in llm.rec if not getattr(c, "has_content", True) or getattr(c, "finish_reason", "") == "exception")
    empty = sum(1 for c in llm.rec if not (getattr(c, "content_len", 0) or 0))
    man = {"health": {"n_groups": len(groups), "n_arms": len(arms), "arms": arms,
                       "n_calls_total": tot, "n_calls_failed": failed,
                       "n_calls_empty": empty, "model": a.model, "effort": a.effort,
                       "n_branch_deficit": sum(
                           1 for g in groups for x in arms
                           if (g["arms"].get(x, {}) or {}).get("n_arts", 0) <
                           (g["arms"].get(x, {}) or {}).get("n_expected", 0)),
                       "channel_health": round(1 - (failed + empty) / max(tot, 1), 4)},
           "groups": groups}
    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1, sort_keys=True)
    # ★★ 落盘 calllog（★ 可审计性硬要求）：
    #   没有 calllog ⇒ **无法独立于执行地重算通道健康度**（`fix_calllog_fields.py` 依赖它）
    #   ⇒ 这是我今晚抓到的教训：manifest 里的 health 是执行时算的，**不能用来验证自己**
    with open(os.path.join(outdir, "calllog.jsonl"), "w", encoding="utf-8") as f:
        for c in llm.rec:
            f.write(json.dumps(c.__dict__, ensure_ascii=False) + "\n")
    log("通道健康：%s" % json.dumps(man["health"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
