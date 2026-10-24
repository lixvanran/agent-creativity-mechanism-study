#!/usr/bin/env python3
"""★ **Stage-1 卡点逐步打点探针（★ 零副作用 · ★ 不写 jsonl）**

★ **为什么**：★ 补跑进程三次都在「第一次调用发出前」消失，★ 而 `run_A` 单独跑 9.9s 成功
★ ⇒ ⇒ ★ **卡点不在 `run_A` 本身** ⇒ ⇒ ★ **必须逐步打点，不能猜**。

★ **做法**：★ 逐个函数包一层计时器，★ 每步立即 flush 打印 ⇒ ⇒ ★ 死在哪一步一目了然。
★ ★ **本探针不写任何 jsonl**（★ 避免污染正式批）。

用法：python3 -B group4_state_driven/probe_stage1_step_timing.py
"""
from __future__ import annotations

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
EXP = "/workspace/第四组论证/experiment-design"
sys.path.insert(0, EXP)
os.environ["OPENROUTER_BASE_URL"] = "https://api.minimaxi.com/v1"

T0 = time.time()


def mark(msg):
    print("[%7.1fs] %s" % (time.time() - T0, msg), flush=True)


def main():
    mark("① import run_arch6_stage1")
    import run_arch6_stage1 as R
    mark("② imported")

    q = R.load_topics().get("T10")
    mark("③ 题面就绪 len=%d" % len(q))

    # ── 逐步：run_A ──
    mark("④ run_A 开始")
    a = R.run_A(q)
    mark("⑤ run_A 结束 err=%r text_len=%d" % (a.get("error"), len(a.get("text") or "")))
    if a.get("error"):
        return 1

    # ── 逐步：build_state5（★ 状态链 · 4 步 · 之前从未单独测过）──
    mark("⑥ build_state5 开始")
    try:
        st, smeta = R.build_state5(q)
        mark("⑦ build_state5 结束 gaps=%d decisions=%d" % (len(st.gaps), smeta.get("n_decisions")))
    except Exception as e:
        mark("✘ build_state5 抛错：%s: %s" % (type(e).__name__, e))
        return 1

    # ── 逐步：state_variants6 ──
    mark("⑧ state_variants6 开始")
    st_base, st_quota, qmeta = R.state_variants6(st)
    mark("⑨ state_variants6 结束 qmeta=%s" % qmeta)

    # ── 逐步：候选生成（★ 3 个候选 · ★ 每个都可能有 thinking 爆炸）──
    mark("⑩ gen_candidates_blind 开始")
    cands = R.gen_candidates_blind(st_base)
    mark("⑪ gen_candidates_blind 结束 n=%d ok=%d errors=%s" % (
        len(cands), sum(1 for c in cands if not c.error), [c.error for c in cands]))

    # ── 逐步：embedding ──
    mark("⑫ embed 开始")
    try:
        vecs, err = R.embed_texts([a["text"]], [])
        mark("⑬ embed 结束 n=%d err=%r" % (len(vecs), err))
    except Exception as e:
        mark("✘ embed 抛错：%s: %s" % (type(e).__name__, e))
        return 1

    mark("★ 全步骤跑通")
    return 0


if __name__ == "__main__":
    sys.exit(main())
