#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 架构化状态机 v2 的对照实验

════════════════════════════════════════════════════════════════════════
★ 改进（相对 v1，全部是改代码/数据结构，不是加提示词）

  ① 实体槽位：状态携带**代码校验过**的离散实体（⊆ 初稿字面）
     ⇒ 「这一轮要写进文章里什么」由**代码**从实体集里选 ⇒ 决策权回代码
  ② 候选集强制：代码算出「必须出现」与「不要写」，写作后**代码检查并带违规项重试**
  ③ 产出验证闸门：非空 / 长度 / **中文占比** / 必含实体命中率
     ⇒ 不合格就重试 ⇒ **代码强制**，治 v1 观察到的"漂移在写作步、状态机不纠正"
  ④ 去框架标签：brief 里不再出现「【这一轮要守住的取舍】」这类**框架性标签**
     （保留内容性指令——那是机制本体，不是元层包装）

★ 四臂
  A       直调（1 步）                         —— 复用 v1 实现，保证同源
  WF-p    提示词式状态机（v1 旧实现）          —— 复用 run_minimal_compare，逐字同源
  WF-a2   架构化 v2（4 步 + 闸门重试）
  WF-a2-NO  v2 消融：无观测（3 步）

★ 唯一输入（逐字，四臂相同）
      你如何看待高考英语作文？写成一篇文章。
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import api_any
import workflow_arch as WA
import workflow_arch2 as WA2
from run_minimal_compare import QUESTION, STANCE_SYS, strip_think, loose_json
import run_minimal_compare as RMC

BASE = api_any.MINIMAX_BASE
KEY_ENV = api_any.MINIMAX_KEY
MODEL = "MiniMax-M3"

# ---------------------------------------------------------------- 传输层
# 与 v1 完全一致：结构化步关 thinking、创作步开 thinking、返回前剥 think
def chat(messages, max_tokens=4000, temperature=1.0, json_mode=False, model=MODEL):
    mt = max_tokens if json_mode else max(max_tokens, 6000)
    # ★ **结构化中间态步关 thinking**（见 api_any 里的实测依据）
    #   判定：json_mode=True（立场步/观测步）⇒ 关
    #        自然语言但有格式约束（转移步，max_tokens=2500）⇒ 关
    #        纯创作（写作步/定稿步，max_tokens=4000）⇒ **开**（保留推理）
    no_think = json_mode or (not json_mode and max_tokens <= 3000)
    return api_any.chat(messages, model, BASE, KEY_ENV, max_tokens=mt,
                        temperature=temperature, json_mode=json_mode, no_think=no_think)


# ★ 把旧实现的传输层也换成同一个 ⇒ WF-p 与 v2 的模型参数/thinking 策略完全一致
def _patched_chat(messages, model, base, key_env, max_tokens=4000,
                  temperature=1.0, json_mode=False):
    return chat(messages, max_tokens=max_tokens, temperature=temperature,
                json_mode=json_mode, model=model)


RMC.chat = _patched_chat


# ---------------------------------------------------------------- 提示（瘦）
# 观测步：加 entities（候选实体，**代码会校验它逐字出现在初稿里**）
OBSERVE2_SYS = """[问题]
{question}

[初稿]
{draft}

只根据上面这份初稿回答四件事。每件事都用你自己的话，说清楚事实，不要评价、不要打分：

1. "used"：这份初稿里已经用过的具体说法、比喻、句式套路——挑最有代表性的 5 到 6 条，
   每条尽量带上原文里出现的那个具体词。
2. "gaps"：这份初稿里哪些地方只是提到了、但没有真正展开？逐条列出，2 到 3 条。
3. "new_constraints"：针对上面每一条 gap，这一轮写作具体应该守住什么？
   逐条列出，和 gap 一一对应，不要重复上一轮已经写过的取舍。
   ★ 每一条都要写明它对应的是第几条 gap（从 1 开始数）——这是结构标注，不是措辞。
4. "sharpest"：这份初稿里最锋利、最具体的一句是哪句？原文引用。

只输出一个 JSON 对象，不要输出 JSON 以外的任何文字、不要用代码围栏。
{{"used": ["..."], "gaps": ["..."], "new_constraints": [{{"gap_index": 1, "constraint": "..."}}], "sharpest": "..."}}"""

#: ★ 观测步额外要"实体"（代码校验其逐字出现在初稿里 ⇒ 取值空间封闭）
ENTITY_PROBE = """

另外再给一个字段：
5. "entities"：这份初稿里出现过的、**读者能一眼认出来的具体事物**（评分标准、阅卷老师、模板、考生…）。
   4 到 6 个，每个 2 到 6 个字，必须是初稿里**原样出现过**的词，不要改写、不要概括、不要生造。
   这些词会用来指定这一轮文章必须写到哪些具体东西，所以只挑**确实出现在初稿里**的。

只输出一个 JSON 对象，格式：
{{"used": ["..."], "gaps": ["..."], "new_constraints": [{{"gap_index": 1, "constraint": "..."}}],
 "sharpest": "...", "entities": ["..."]}}"""


def render_writing(question, keeps, must=None, forbidden=None, draft=None, final=False,
                   lang="zh"):
    """**代码渲染 brief**：无框架标签，只有内容。

    ★ 对比 v1：v1 用「【这一轮要守住的取舍】」「【这一轮不能再走的路】」「【初稿】」
      这类**框架性标签**。v2 全部去掉 ⇒ 去掉"这是个状态对象"的元层提示。
      保留的「要写进文章里 X」「不要写 Y」是**内容性指令**（机制本体），不是包装。
    """
    parts = [question, ""]
    # ★ 语言要求由**代码**从状态槽位渲染（lang ∈ {zh, en} 封闭枚举）
    if lang == "zh":
        parts.append("用中文写。")
        parts.append("")
    for k in (keeps or []):
        parts.append("· " + k)
    if must:
        parts.append("")
        parts.append("· 要写进文章里：" + "、".join(must))
    if forbidden:
        parts.append("· 不要写：" + "、".join(forbidden))
    if draft is not None:
        parts += ["", draft]
    parts += ["", "现在写出定稿。直接输出文章正文。" if final
              else "直接输出文章正文。"]
    return "\n".join(parts)


# ---------------------------------------------------------------- 步骤
def step_stance2(question, tag):
    raw = chat([{"role": "user", "content": question + "\n\n" + STANCE_SYS}],
               max_tokens=2000, json_mode=True)
    d = loose_json(raw) or {}
    keeps = d.get("不能牺牲") if isinstance(d.get("不能牺牲"), list) else []
    keeps = [str(x).strip() for x in keeps if str(x).strip()][:3]
    st = WA2.State2(stance=str(d.get("立场") or "").strip(),
                    keeps=keeps or ["把这一轮真正想说的话说清楚，不要滑回套话"],
                    slip=str(d.get("最容易失守") or "").strip(),
                    first=str(d.get("第一次反应") or "").strip())
    return st, raw, ("ok" if d else "stance_empty")


def step_observe2(question, draft):
    prompt = OBSERVE2_SYS.format(question=question, draft=draft) + ENTITY_PROBE
    raw = chat([{"role": "user", "content": prompt}], max_tokens=3500, json_mode=True)
    obs, status = WA2.parse_observation2(raw)
    if obs is None:
        obs = {"used": [], "gaps": [], "new_constraints": [], "entities": [],
               "sharpest": "", "_missing": ["*"]}
    obs["_draft"] = draft
    return obs, raw, status


def gated_call(brief, must, forbidden, tag, step, max_retry=None, lang="zh"):
    """**带闸门的创作调用**：不合格 ⇒ 代码带违规项重试。

    ★ 这是 v2 的核心新增：**代码强制**，不是提示词请求。
    """
    g = WA2.GATE
    max_retry = g["max_retry"] if max_retry is None else max_retry
    attempts, gates = [], []
    cur = brief
    for k in range(max_retry + 1):
        txt = strip_think(chat([{"role": "user", "content": cur}], max_tokens=6000))
        gr = WA2.gate_output(txt, must, forbidden)
        gates.append(gr.to_dict())
        attempts.append({"k": k, "len": len(txt), "lang": gr.lang_cn,
                         "must_hit": gr.must_hit, "ok": gr.ok})
        if gr.ok or k == max_retry:
            return txt, gates, attempts
        # ★ 重试：**正向**提示 + 具体违规项（观测驱动反馈，非预制）
        cur = brief + WA2.retry_hint(gr.reasons, lang=lang)
    return txt, gates, attempts


# ---------------------------------------------------------------- 臂
def run_A2(tag):
    t0 = time.time()
    raw = chat([{"role": "user", "content": QUESTION}], max_tokens=4000)
    txt = strip_think(raw)
    return {"arm": "A", "tag": tag, "text": txt, "calls": [("direct", len(txt))],
            "elapsed": round(time.time() - t0, 1),
            "error": None if len(txt.strip()) >= 50 else "text_too_short"}


def run_WF_p2(tag):
    """v1 旧实现（提示词式状态机），**逐字同源**。"""
    try:
        r = RMC.run_workflow(QUESTION, MODEL, BASE, KEY_ENV, tag)
    except Exception as e:
        return {"arm": "WF-p", "tag": tag, "text": "", "error": "workflow:%s" % e}
    r["arm"] = "WF-p"
    if len((r.get("text") or "").strip()) < 50:
        r["error"] = (r.get("error") or "") + ";final_too_short"
    return r


def run_WF_a2(tag, no_obs=False):
    t0 = time.time()
    calls, errs = [], []
    st, raw_s, s_st = step_stance2(QUESTION, tag)
    calls.append(("stance", len(raw_s)))
    if s_st != "ok":
        errs.append("stance:" + s_st)

    # ② 写作步（初稿）—— **也过闸门**（漂移发生在这一步）
    brief1 = render_writing(QUESTION, st.keeps, lang=st.lang)
    draft, g1, a1 = gated_call(brief1, [], [], tag, "draft", lang=st.lang)
    calls.append(("draft", len(draft)))
    calls.append(("draft_gate", len(g1)))

    # ③ 观测步
    obs, raw_o, o_st = step_observe2(QUESTION, draft)
    calls.append(("observe", len(raw_o)))
    if o_st == "parse_failed":
        errs.append("observe:parse_failed")

    # ④ 转移（代码）
    if no_obs:
        new_st, trace = WA2.transfer2(st, None, rewriter=lambda g, p, e: [])
    else:
        cand = [c for c in (obs.get("new_constraints") or [])]
        new_st, trace = WA2.transfer2(st, obs, rewriter=lambda g, p, e: cand)
    calls.append(("transfer", 0))

    # ⑤ 定稿步（带候选集）
    brief2 = render_writing(QUESTION, new_st.keeps, new_st.must_include,
                            new_st.forbidden, draft, final=True, lang=new_st.lang)
    final, g2, a2 = gated_call(brief2, new_st.must_include, new_st.forbidden, tag,
                               "final", lang=new_st.lang)
    calls.append(("final", len(final)))
    calls.append(("final_gate", len(g2)))
    if len(final.strip()) < 50:
        errs.append("final_too_short")
    # ★ 硬闸：闸门最终未通过 ⇒ 样本显式标记为无效（不放行）
    gate_failed = any((not g.get("ok")) for g in (g1 + g2))
    if gate_failed:
        errs.append("hard_gate_failed")

    return {"arm": "WF-a2-NO" if no_obs else "WF-a2", "tag": tag,
            "gate_failed": gate_failed,
            "text": final, "draft": draft,
            "state0": st.to_dict(), "state1": new_st.to_dict(),
            "observation": {k: v for k, v in obs.items() if k != "_draft"},
            "trace": trace, "gates": {"draft": g1, "final": g2},
            "attempts": {"draft": a1, "final": a2},
            "calls": calls, "elapsed": round(time.time() - t0, 1),
            "error": ";".join(errs) if errs else None}


# ---------------------------------------------------------------- main
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", default="1,2,3")
    ap.add_argument("--arms", default="A,WF-p,WF-a2,WF-a2-NO")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch2_compare.jsonl"))
    args = ap.parse_args()

    reps = [int(x) for x in args.reps.split(",") if x.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    batch = "arch2-%s" % time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    dispatch = {
        "A": run_A2, "WF-p": run_WF_p2,
        "WF-a2": lambda t: run_WF_a2(t, no_obs=False),
        "WF-a2-NO": lambda t: run_WF_a2(t, no_obs=True),
    }
    for a in arms:
        assert a in dispatch, a

    # ★ 增量写盘：单个样本卡住不丢已得结果
    out_f = open(args.out, "w", encoding="utf-8")
    results = []
    futs, meta = [], {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for a in arms:
            for s in reps:
                fu = ex.submit(dispatch[a], s)
                futs.append(fu); meta[fu] = (a, s)
        for fu in as_completed(futs):
            a, s = meta[fu]
            try:
                r = fu.result()
            except Exception as e:
                r = {"arm": a, "tag": s, "text": "", "error": "%s: %s" % (type(e).__name__, e)}
            r["batch_id"] = batch; r["model"] = MODEL
            results.append(r)
            out_f.write(json.dumps(r, ensure_ascii=False) + "\n"); out_f.flush()
            print("  [%s] %-10s #%s  %5d字  闸门通过=%s  %s" % (
                batch, r.get("arm"), r.get("tag"), len((r.get("text") or "").strip()),
                (all(g["ok"] for g in (r.get("gates") or {}).get("final", []) or [{}]) if r.get("gates") else "-"),
                ("ERR:" + str(r.get("error"))) if r.get("error") else "ok"), flush=True)
    out_f.close()
    c = api_any.cost_estimate()
    print("\n[out] %s" % args.out)
    print("[batch] %s ｜ 调用 %d 次 ｜ prompt=%d completion=%d"
          % (batch, c["calls"], c["prompt_tokens"], c["completion_tokens"]))


if __name__ == "__main__":
    main()
