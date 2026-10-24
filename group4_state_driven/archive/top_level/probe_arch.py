#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 架构化状态机的**状态历史置换探针**（极简版 D-2）

════════════════════════════════════════════════════════════════════════
★ 要问的问题
  状态 S₁ 是**真的依赖观测 O₁**，还是只是把 S₀ 换个说法复述一遍？
  ⇒ 检验方法：把第③步看到的初稿**换成别的样本的初稿**，看状态变多少。

★ 两条对照线，缺一不可
  · swap  （换历史）：用**另一个样本**的 draft 重跑 观测→转移
  · same  （不换历史）：用**同一个** draft 再跑一次 观测→转移
    ⇒ same 就是"种子噪声地板"（API 的 temperature=0 也不是确定性 ⇒ 同一输入也会漂）
  ★ 判据：**swap 的状态变化显著大于 same 的变化** 才算"状态依赖观测"。
    只报 swap 不报 same ⇒ 无法区分"机制在动"和"API 在抖"。

★ 单一输入（与主实验逐字相同）：
      你如何看待高考英语作文？写成一篇文章。
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import api_any
import workflow_arch as WA
from run_arch_compare import (QUESTION, OBSERVE_SYS, step_stance, step_draft,
                              build_constraints, BASE, KEY_ENV)
import run_minimal_compare as RMC


def rerun(model, st, draft, tag, kind):
    """给定状态 + 一份 draft，重跑 观测→转移→定稿。返回 (state1, final, obs)。"""
    raw = api_any.chat([{"role": "user", "content":
                         OBSERVE_SYS.format(question=QUESTION, draft=draft)}],
                        model, BASE, KEY_ENV, max_tokens=3500, json_mode=True)
    obs, status = WA.parse_observation(raw)
    if obs is None:
        obs = {"used": [], "gaps": [], "new_constraints": [], "sharpest": "", "_missing": ["*"]}
    cand = build_constraints(obs)
    new_st, trace = WA.transfer(st, obs if (obs.get("gaps") or obs.get("used")) else None,
                                rewriter=lambda g, p, e: cand)
    brief = (QUESTION + "\n\n【这一轮要守住的取舍】\n" + new_st.render_keeps() +
             ("\n\n【这一轮不能再走的路】\n" + new_st.render_excluded() if new_st.excluded else "") +
             "\n\n【初稿】\n" + draft +
             "\n\n现在写出这一轮的定稿。直接输出文章正文。")
    final = RMC.strip_think(api_any.chat([{"role": "user", "content": brief}],
                                         model, BASE, KEY_ENV, max_tokens=6000))
    return new_st, final, obs, trace, status, len(raw)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "runs", "arch_compare.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch_probe.jsonl"))
    ap.add_argument("--model", default="MiniMax-M3")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    src = [json.loads(l) for l in open(args.src, encoding="utf-8") if l.strip()]
    pool = [r for r in src if r.get("arm") == "WF-a" and r.get("draft") and not r.get("error")]
    print("WF-a 可用样本：%d" % len(pool))
    if len(pool) < 2:
        print("样本不足，无法做置换"); return

    batch = "probe-%s" % time.strftime("%Y%m%d-%H%M%S")
    jobs = []
    for i, r in enumerate(pool):
        st = WA.State(**{k: v for k, v in r["state0"].items()})
        other = pool[(i + 1) % len(pool)]
        jobs.append(("same", r, st, r["draft"], i))
        jobs.append(("swap", r, st, other["draft"], i))

    futs = []
    meta = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for kind, r, st, draft, i in jobs:
            fu = ex.submit(rerun, args.model, st, draft, r.get("tag"), kind)
            futs.append(fu)
            meta[fu] = (kind, i)
        results = []
        for fu in as_completed(futs):
            kind, i = meta[fu]
            try:
                ns, final, obs, trace, status, rlen = fu.result()
            except Exception as e:
                print("  ERR %s #%d: %s" % (kind, i, e), flush=True); continue
            rec = {"kind": kind, "src_tag": pool[i].get("tag"),
                   "src_index": i, "state1": ns.to_dict(), "text": final,
                   "observation": obs, "trace": trace, "obs_raw_len": rlen,
                   "obs_status": status, "batch_id": batch}
            results.append(rec)
            print("  [%s] %s #%d  约束%s 排除%s linked=%s" %
                  (batch, kind, pool[i].get("tag"), ns.keeps, len(ns.excluded),
                   trace.get("n_linked")), flush=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in sorted(results, key=lambda x: (x["src_index"], x["kind"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("\n[out] %s  (调用 %d 次)" % (args.out, len(api_any.TRACE)))


if __name__ == "__main__":
    main()
