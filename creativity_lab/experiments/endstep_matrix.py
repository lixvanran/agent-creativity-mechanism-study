#!/usr/bin/env python3
"""**层2 · 第一个设计变量：末步类型（4 臂对照）**

> 2026-10-23 ｜ 第二组 · 层2 ｜ 落点：`creativity_lab/experiments/endstep_matrix.py`
>
> ## 为什么要有这个实验
> 项目的目标是**设计工作流/架构去扩展 Agent 的思维面**，判定只是尺子。
> 那第一个可设计的变量是什么？——**末步**：发散出的「面」在最后一步被怎么处理。
>
> ## ★ 为什么不能直接用现成的 dual_fuse / dual_select
> 现有两臂的**发散层就不一样**（fuse 发散成「判断片段」，select 发散成「完整文章」）
> ⇒ 末步效应与任务形态效应**混在一起** ⇒ 测不出「末步类型」这一个变量。
> ⇒ 所以这里让 4 个臂**吃同一批发散产物**（同一次发散）⇒ **末步是唯一变量**。
>
> ## 4 臂
> | 臂 | 末步 | 额外 LLM 调用 | 预期面宽 |
> |---|---|--:|---|
> | `end_fuse`   | 融合门：把 5 篇融成 1 篇（LLM） | 2 | 2–3 |
> | `end_greedy` | 纯函数选**最独特**的一支 | **0** | 1 |
> | `end_sample` | 纯函数按独特度**加权随机**选（ToT method_select='sample'） | **0** | 1 |
> | `end_raw`    | **不做末步**：直接输出 5 篇（面宽上界参照） | **0** | 5 |
>
> ★ 三个末步是**纯函数** ⇒ 零温度、零随机源、**逐字节可复算**。
> ★ `end_raw` 是**参照**不是竞争者：它的输出量天然是别的臂的 5 倍
>   ⇒ 所以因变量必须**三元组并列**：面宽（covered_branches）× 面深（survival_rate）
>     × 输出量（chars）⇒ 否则就是在奖励「多写」。
>
> ## 因变量（全部零判官、零 embedding、可离线复算）
> - `covered_branches`（thr 事前登记 = 0.30，另给整条阈值曲线）：输出里还留着几支
> - `survival_rate`：平均每支的保留比例（面深）
> - `out_chars` / `chars_per_covered`：单位面成本
> - `branch_diversity`：发散层自身的面宽（4 臂共享的基线）
>
> ## 落盘纪律
> **不靠文件名约定配对**（历史归档就是这么错位出来的）⇒ 一切配对信息写进
> `manifest.json`，且**每个臂的分支都落盘**（历史跑批漏了融合臂的分支 ⇒
> "融合吃掉了多少面"事后算不了）。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.arms.dual import Dual, _branch_specs       # noqa: E402
from creativity_lab.client import DEFAULT_EFFORT, LLM          # noqa: E402
from creativity_lab.metrics import emb_coverage, fixed_len_coverage  # noqa: E402
from creativity_lab.gates.base import Select                   # noqa: E402
from creativity_lab.metrics import (branch_diversity, covered_branches,  # noqa: E402
                                    coverage_curve, distinctness_scores,
                                    survival_rate)
from creativity_lab.prompts import FUSE_ASK, OUT_SPEC, PREMISE_Q  # noqa: E402

ARMS = ["end_fuse", "end_greedy", "end_sample", "end_raw"]
THR = 0.30          # ★ 事前登记：面保留数的判定阈值
SEED_BASE = 20261023


def _fuse_articles(llm, topic, arts):
    """融合门：吃**完整**分支（历史臂3 吃的是被截到 400 字的片段）。

    ★ 与历史臂3 的差异已在报告里登记（内部可比性由"共享发散层"保证）。
    """
    joined = "\n\n".join(f"[第{i+1}篇]\n{a}" for i, a in enumerate(arts))
    pre = llm.chat(PREMISE_Q.format(n=len(arts), cands=joined), purpose="end_fuse:premise")
    return llm.chat(FUSE_ASK.format(topic=topic["ask"], frags=joined,
                                     pre=pre[:1200], spec=OUT_SPEC),
                    purpose="end_fuse:fuse")


def build_specs(alive, n=5):
    """按**可用**型号构造分支扇出（轴A 框架 × 轴B 型号 × persona）。

    ★ 2026-10-23：`MODELS` 池 9 个里有 3 个已下架（M2.1 / M2 / M2.1-highspeed 实测 404）
      ⇒ 死分支会被**静默丢弃** ⇒ 发散层从 5 支变 4 支 ⇒ 分母漂移而表看不出来。
      ⇒ 这里只用**探测过的活型号**，并把型号池记进 manifest。
    """
    base = _branch_specs()
    specs = []
    for i in range(n):
        frame, _m, persona = base[i % len(base)]
        specs.append((frame, alive[i % len(alive)], persona))
    return specs


def run_group(llm, topic, rep, model, effort, specs=None, embed_fn=None):
    """跑一个 (题, rep)：**一次发散，4 个末步共享**。"""
    g: Dict[str, Any] = {"tid": topic["tid"], "rep": rep, "model": model,
                          "effort": effort, "arms": {}}
    t0 = time.time()
    # ---- 发散层（4 臂共享，唯一一次）----
    # ★ 并行：5 支互不依赖 ⇒ 并发 3（实测并发 >4 会 429）
    #   ⇒ 单组耗时从 5×T 降到 ~2×T（治"单组卡十几分钟"）
    from concurrent.futures import ThreadPoolExecutor
    from creativity_lab.prompts import BRANCH_ASK
    from creativity_lab.arms.dual import _branch_specs
    base = _branch_specs()
    prompts, models = [], []
    for i, (frame, _m, persona) in enumerate(specs):
        prompts.append(BRANCH_ASK.format(
            topic=topic["ask"], frame_name=frame["name"], frame_text=frame["text"],
            persona=persona, spec=OUT_SPEC,
            extra="\n直接写出**完整的答复本身**，不要写判断片段。"))
        models.append(_m)
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(llm.chat, prompts[i], model=models[i],
                          purpose=f"diverge:{models[i]}") for i in range(len(prompts))]
        arts = [f.result() for f in futs]
    arts = [o for o in arts if o]
    g["n_arts"] = len(arts)
    g["n_arts_expected"] = len(specs) if specs else 5
    g["divergence_secs"] = round(time.time() - t0, 1)
    g["branch_diversity"] = round(branch_diversity(arts), 4) if len(arts) > 1 else None
    g["distinctness"] = [round(x, 4) for x in distinctness_scores(arts)]
    g["arts_chars"] = [len(a) for a in arts]
    if len(arts) < 3:
        g["valid"] = False
        g["reason"] = "divergence_too_few_arts(%d)" % len(arts)
        g["channel_failed"] = True
        return g
    if len(arts) < g["n_arts_expected"]:
        # ★ 分支缺失 ⇒ **分母漂移** ⇒ 显式标记（不静默）
        g["arts_deficit"] = g["n_arts_expected"] - len(arts)
    g["valid"] = True

    scores = distinctness_scores(arts)
    rng = random.Random(SEED_BASE + rep)

    # ---- 4 个末步 ----
    outs: Dict[str, str] = {}
    for arm in ARMS:
        n0 = len(llm.rec)
        t1 = time.time()
        if arm == "end_fuse":
            txt = _fuse_articles(llm, topic, arts)
        elif arm == "end_greedy":
            i = Select(mode="greedy")(scores)[0]
            txt = arts[i]
            g.setdefault("picked", {})[arm] = i
        elif arm == "end_sample":
            i = Select(mode="sample", rng=rng)(scores)[0]
            txt = arts[i]
            g.setdefault("picked", {})[arm] = i
        else:                                    # end_raw
            txt = "\n\n=====\n\n".join(arts)
        calls = [c for c in llm.rec[n0:]]
        outs[arm] = txt
        cov = covered_branches(arts, txt, THR)
        g["arms"][arm] = {
            "text": txt,
            "n_calls": len(calls),
            "calls": [{"purpose": c.purpose, "model": c.model, "max_tokens": c.max_tokens,
                       "finish_reason": c.finish_reason, "content_len": c.content_len,
                       "ok": c.ok, "secs": round(c.secs, 1), "effort": c.effort}
                      for c in calls],
            "covered_branches": cov,
            "survival_rate": round(survival_rate(arts, txt), 4),
            "coverage_curve": coverage_curve(arts, txt),
            "out_chars": len(txt),
            "chars_per_covered": round(len(txt) / cov, 1) if cov else None,
            "emb": emb_coverage(arts, txt, embed_fn) if embed_fn else None,
            "fixed_len": [fixed_len_coverage(arts, txt, L) for L in (300, 400, 600)],
            "secs": round(time.time() - t1, 1),
            "valid": bool(txt.strip()),
        }
    g["arts"] = arts           # ★ 全部落盘（历史跑批漏了 ⇒ 算不了）
    g["total_secs"] = round(time.time() - t0, 1)
    return g


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", default=None)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--model", default="MiniMax-M3")
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
    ap.add_argument("--out", default="runs/endstep-matrix")
    ap.add_argument("--only-tid", default=None)
    ap.add_argument("--resume", action="store_true", help="已有有效组则跳过（断点续跑）")
    a = ap.parse_args()

    from creativity_lab import topics as T
    ts = T.load(a.topics or T.DEFAULT_TOPIC_FILE)
    if a.only_tid:
        ts = [t for t in ts if t["tid"] in a.only_tid.split(",")]
    print("题：%s｜rep=%d｜model=%s｜effort=%s" % ([t["tid"] for t in ts], a.reps, a.model, a.effort))

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       a.out)
    os.makedirs(out, exist_ok=True)
    from creativity_lab.experiments.probe_models import probe
    pr = probe()
    alive = pr["alive"]
    if len(alive) < 5:
        print("可用型号不足 5 个：%s" % alive)
    specs = build_specs(alive, 5)
    print("分支型号池（已探测）：%s" % [m for _, m, _ in specs])

    llm = LLM()
    emb_llm = LLM()

    def embed_fn(texts):
        return emb_llm.embed(list(texts))

    groups: List[Dict[str, Any]] = []
    for topic in ts:
        for rep in range(1, a.reps + 1):
            gp = os.path.join(out, "group_%s_r%d.json" % (topic["tid"], rep))
            if a.resume and os.path.exists(gp):
                try:
                    g_old = json.load(open(gp, encoding="utf-8"))
                    if g_old.get("valid"):
                        print("  ⏩ %s rep%d 已有有效组，跳过" % (topic["tid"], rep), flush=True)
                        groups.append(g_old)
                        continue
                except Exception:                      # noqa: BLE001
                    pass
            print("  → %s rep%d ..." % (topic["tid"], rep), flush=True)
            g = run_group(llm, topic, rep, a.model, a.effort, specs=specs, embed_fn=embed_fn)
            groups.append(g)
            with open(os.path.join(out, "group_%s_r%d.json" % (g["tid"], g["rep"])),
                      "w", encoding="utf-8") as f:
                json.dump(g, f, ensure_ascii=False, indent=2, sort_keys=True)
            for arm, d in g.get("arms", {}).items():
                print("     %-11s covered=%d survival=%.3f chars=%d calls=%d"
                      % (arm, d["covered_branches"], d["survival_rate"],
                         d["out_chars"], d["n_calls"]), flush=True)
            if not g.get("valid"):
                print("     ⚠️ 组作废：%s" % g.get("reason"), flush=True)

    # ---- manifest：一切配对信息在这里，不靠文件名 ----
    health = {
        "n_groups": len(groups),
        "n_valid": sum(1 for g in groups if g.get("valid")),
        "n_channel_failed": sum(1 for g in groups if not g.get("valid")),
        "n_calls_total": len(llm.rec),
        "n_calls_failed": sum(1 for c in llm.rec if not c.ok),
        "n_calls_truncated": sum(1 for c in llm.rec if c.finish_reason == "length"),
        "n_calls_empty": sum(1 for c in llm.rec if c.content_len == 0),
        "model": a.model, "effort": a.effort, "thr": THR, "seed_base": SEED_BASE,
        "model_pool": [m for m in alive],
        "dead_models": pr["dead"],
        "branch_specs": [[f[0]["name"], m, f[2]] for f, (_, m, _) in zip(specs, specs)],
        "arms": ARMS,
    }
    health["channel_health"] = (round(1 - health["n_calls_failed"] / max(health["n_calls_total"], 1), 4))
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"health": health, "groups": [{k: v for k, v in g.items() if k != "arts"}
                                                for g in groups]},
                  f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out, "calllog.jsonl"), "w", encoding="utf-8") as f:
        for c in llm.rec:
            f.write(json.dumps(c.__dict__, ensure_ascii=False) + "\n")

    print("\n== 通道健康 ==")
    for k, v in health.items():
        print("  %-22s %s" % (k, v))
    print("\n✓ 落盘 %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
