#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 架构化对照实验（arch vs prompt）

════════════════════════════════════════════════════════════════════════
★ 五臂，全部只吃**唯一输入**：
      你如何看待高考英语作文？写成一篇文章。

  A     直接调用 LLM，1 次，无 system                —— 基线
  S     等调用数中性管线，4 步，**不建状态**          —— 剥离"步数/上下文强度"混淆
  WF-p  提示词式状态机（= 上一轮的 WF 臂），4 步     —— 旧机制
  WF-a  架构化状态机（状态与转移律在代码里），4 步   —— 新机制
  WF-a-R 架构化 + **反极性立场**，5 步                —— 换极性武器

★ 为什么 S 臂必须有
  A 臂 1 次调用 vs WF 臂 4 次调用 ⇒ **预算混淆**。
  任何"WF 更好"都可能被"多调了 3 次模型"解释掉。
  S 臂 = 同样 4 步、同样吃初稿、但**不建状态**，用来把管线深度与上下文强度剥出来。

★ 为什么 WF-p 直接 import 原模块的常量
  对照臂必须与旧实现**逐字同源**。任何手抄都可能漂移 ⇒ 直接 import，
  再 monkeypatch 传输层（换成带 429 长退避 + usage 记录的那层），
  提示词与流程**一个字符都不动**。

★ 记录 batch_id（单批）、每臂实际调用数、每次调用的 token 用量。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import api_any
import workflow_arch as WA

# ★ 直接 import 旧实现的常量 ⇒ 对照臂逐字同源，不可能漂移
from run_minimal_compare import (
    QUESTION, STANCE_SYS, WRITE_SYS, F_SYS, G_SYS,
    parse3, strip_think, loose_json,
)

# ---------------------------------------------------------------- 传输层
# ★ 统一：结构化步 max_tokens 照旧；创作步抬到 6000（MiniMax thinking 会吃 token，
#   否则会被截断）。**两个架构臂走完全相同的传输层** ⇒ 预算可比。
CREATIVE_BUDGET = 6000
TRACE: list = []

#: 传输层端点（main 按 --api 改写）
BASE = api_any.MINIMAX_BASE
KEY_ENV = api_any.MINIMAX_KEY


def chat(messages, model, base, key_env, max_tokens=4000, temperature=1.0, json_mode=False):
    mt = max_tokens if json_mode else max(max_tokens, CREATIVE_BUDGET)
    t0 = len(TRACE)
    c = api_any.chat(messages, model, base, key_env,
                     max_tokens=mt, temperature=temperature, json_mode=json_mode)
    return c


# 把旧模块的传输层换成统一的（提示词不动）
import run_minimal_compare
run_minimal_compare.chat = chat


# ---------------------------------------------------------------- 新提示（瘦）
# ★ 与 WF-p 的差别：**不含任何格式纪律**（不要"恰好 3 行"、不要"第一段/第二段"）。
#   格式纪律由代码承担（解析、归类、补齐、绑定校验）。

OBSERVE_SYS = """[问题]
{question}

[初稿]
{draft}

只根据上面这份初稿回答四件事。每件事都用你自己的话，说清楚事实，不要评价、不要打分、不要给建议：

1. "used"：这份初稿里已经用过的具体说法、比喻、句式套路——挑**最有代表性的 5 到 6 条**，
   每条尽量带上原文里出现的那个具体词。不要逐句罗列全文。
2. "gaps"：这份初稿里哪些地方只是提到了、但没有真正展开？逐条列出，2 到 3 条。
3. "new_constraints"：针对上面每一条 gap，这一轮写作具体应该守住什么？
   逐条列出，和 gap 一一对应，不要重复上一轮已经写过的取舍。
   ★ 每一条都要写明它对应的是第几条 gap（从 1 开始数）——这是结构标注，不是措辞。
4. "sharpest"：这份初稿里最锋利、最具体的一句是哪句？原文引用。

只输出一个 JSON 对象，不要输出 JSON 以外的任何文字、不要用代码围栏。
{{"used": ["..."], "gaps": ["..."], "new_constraints": [{{"gap_index": 1, "constraint": "..."}}], "sharpest": "..."}}"""

REVERSE_SYS = """你刚才对下面这个写作问题给出的立场是：
{stance}

现在请你站在**与它相反**的立场上，重新想清楚：站在另一边，你的写作会牺牲什么。
你必须做出取舍，不许骑墙、不许"两边都有道理"。

[问题]
{question}

只输出一个 JSON 对象，不要输出 JSON 以外的任何文字、不要用代码围栏。
{{"立场":"...","不能牺牲":["...","...","..."],"最容易失守":"...","第一次反应":"..."}}"""

NEUTRAL1_SYS = """[问题]
{question}

列出让这篇文章写得扎实的几个方面。3 到 5 条，每条一句话。
只列方面，不要给立场，不要给结论，不要给建议。

只输出 3 到 5 行，每行一条，不要编号、不要标题、不要解释。"""

NEUTRAL2_SYS = """[问题]
{question}

[初稿]
{draft}

指出上面这份初稿最需要修改的三个地方。恰好 3 行，每行一句，只说问题和该怎么改。
不要评价整篇文章，不要给立场。

只输出这 3 行，不要任何编号、标题、解释、前后缀。"""

FINAL_SYS = """[问题]
{question}

[上一轮的建议]
{advices}

[初稿]
{draft}

按上面的建议写出这一轮的定稿。直接输出文章正文，不要复述建议，不要解释。"""


# ---------------------------------------------------------------- 步骤实现

def step_stance(question, model, tag, reverse_from=None):
    """立场步 → WA.State。返回 (state, raw, status)"""
    if reverse_from:
        prompt = question + "\n\n" + REVERSE_SYS.format(stance=reverse_from, question=question)
    else:
        prompt = question + "\n\n" + STANCE_SYS
    raw = chat([{"role": "user", "content": prompt}], model, BASE, KEY_ENV,
               max_tokens=2000, json_mode=True)
    d = loose_json(raw) or {}
    keeps = d.get("不能牺牲") if isinstance(d.get("不能牺牲"), list) else []
    keeps = [str(x).strip() for x in keeps if str(x).strip()][:3]
    st = WA.State(
        stance=str(d.get("立场") or "").strip(),
        keeps=keeps,
        slip=str(d.get("最容易失守") or "").strip(),
        first=str(d.get("第一次反应") or "").strip(),
        polarity="reversed" if reverse_from else "default",
    )
    st.keeps = st.keeps or ["把这一轮真正想说的话说清楚，不要滑回套话"]
    return st, raw, ("ok" if d else "stance_empty")


def step_draft(question, model, st: WA.State):
    brief = (question + "\n\n【这一轮要守住的取舍】\n" + st.render_keeps() +
             "\n\n直接输出文章正文。")
    raw = chat([{"role": "user", "content": brief}], model, BASE, KEY_ENV, max_tokens=4000)
    return strip_think(raw)


def step_observe(question, model, draft):
    """观测步：只描述事实。**失败显式标记**。"""
    raw = chat([{"role": "user", "content":
                 OBSERVE_SYS.format(question=question, draft=draft)}],
               model, BASE, KEY_ENV, max_tokens=2500, json_mode=True)
    obs, status = WA.parse_observation(raw)
    if obs is None:
        obs = {"used": [], "gaps": [], "new_constraints": [], "sharpest": ""}
    return obs, raw, status


def build_constraints(obs: dict) -> list:
    """代码侧：取出 new_constraints 原始项（dict 带 gap_index，或 str）。

    ★ **不在这里做绑定判断** —— 绑定由 `WA.resolve_binding` 统一处理：
      结构声明（gap_index）优先，字面相似度只作辅助信号。
    """
    out = []
    for item in (obs.get("new_constraints") or []):
        if isinstance(item, dict):
            c = WA.norm_line(str(item.get("constraint") or ""))
        else:
            c = WA.norm_line(str(item))
        if c:
            out.append(item)
        if len(out) >= 3:
            break
    return out


def run_arch(question, model, tag, reverse=False):
    """架构化状态机。返回一条结果记录。"""
    t0 = time.time()
    calls = []
    st, raw_s, st_st = step_stance(question, model, tag)
    calls.append(("stance", len(raw_s)))
    errs = []
    if st_st != "ok":
        errs.append("stance:" + st_st)

    if reverse:
        st2, raw_s2, st2_st = step_stance(question, model, tag, reverse_from=st.stance)
        calls.append(("stance_rev", len(raw_s2)))
        if st2_st != "ok":
            errs.append("stance_rev:" + st2_st)
        st = st2

    draft = step_draft(question, model, st)
    calls.append(("draft", len(draft)))
    if len(draft.strip()) < 50:
        errs.append("draft_too_short")

    obs, raw_o, ob_st = step_observe(question, model, draft)
    calls.append(("observe", len(raw_o)))
    if ob_st == "parse_failed":
        errs.append("observe:" + ob_st)

    # ★ 状态转移在代码里（rewriter 用模型给的 new_constraints，但**绑定由代码校验**）
    cand = build_constraints(obs)
    missing = obs.get("_missing") or []
    new_st, trace = WA.transfer(st, obs if obs.get("gaps") or obs.get("used") else None,
                                rewriter=lambda gaps, p, e: cand)
    # transfer 内部已算好链接信息（结构声明优先）
    calls.append(("transfer", 0))   # 转移在代码里，不产生调用
    if missing:
        trace["observation_missing_fields"] = missing

    brief = (question + "\n\n【这一轮要守住的取舍】\n" + new_st.render_keeps() +
             ("\n\n【这一轮不能再走的路】\n" + new_st.render_excluded() if new_st.excluded else "") +
             "\n\n【初稿】\n" + draft +
             "\n\n现在写出这一轮的定稿。直接输出文章正文。")
    final = strip_think(chat([{"role": "user", "content": brief}], model, BASE, KEY_ENV,
                              max_tokens=4000))
    calls.append(("final", len(final)))
    if len(final.strip()) < 50:
        errs.append("final_too_short")

    return {"arm": "WF-a-R" if reverse else "WF-a", "tag": tag,
            "text": final, "draft": draft,
            "state0": st.to_dict(), "state1": new_st.to_dict(),
            "observation": obs, "trace": trace,
            "calls": calls, "elapsed": round(time.time() - t0, 1),
            "error": ";".join(errs) if errs else None}


def run_arch_noobs(question, model, tag):
    """WF-a 的**消融**：转移步不喂初稿（observation=None）⇒ 状态只能沿用。"""
    t0 = time.time()
    calls = []
    st, raw_s, st_st = step_stance(question, model, tag)
    calls.append(("stance", len(raw_s)))
    draft = step_draft(question, model, st)
    calls.append(("draft", len(draft)))
    new_st, trace = WA.transfer(st, None, rewriter=lambda g, p, e: [])
    calls.append(("transfer", 0))
    brief = (question + "\n\n【这一轮要守住的取舍】\n" + new_st.render_keeps() +
             ("\n\n【这一轮不能再走的路】\n" + new_st.render_excluded() if new_st.excluded else "") +
             "\n\n【初稿】\n" + draft +
             "\n\n现在写出这一轮的定稿。直接输出文章正文。")
    final = strip_think(chat([{"role": "user", "content": brief}], model, BASE, KEY_ENV,
                              max_tokens=4000))
    calls.append(("final", len(final)))
    errs = []
    if st_st != "ok":
        errs.append("stance:" + st_st)
    if len(final.strip()) < 50:
        errs.append("final_too_short")
    return {"arm": "WF-a-NO", "tag": tag, "text": final, "draft": draft,
            "state0": st.to_dict(), "state1": new_st.to_dict(),
            "trace": trace, "calls": calls, "elapsed": round(time.time() - t0, 1),
            "error": ";".join(errs) if errs else None}


def run_S(question, model, tag):
    """等调用数中性管线：无状态、无取舍、无排除。第③步只产通用改稿意见。"""
    t0 = time.time()
    calls = []
    raw1 = chat([{"role": "user", "content": question + "\n\n" + NEUTRAL1_SYS.format(question=question)}],
                 model, BASE, KEY_ENV, max_tokens=1200)
    calls.append(("neutral1", len(raw1)))
    aspects = [WA.norm_line(x) for x in strip_think(raw1).splitlines() if WA.norm_line(x)][:5]
    brief1 = (question + "\n\n【需要注意的方面】\n" + "\n".join("· " + a for a in aspects) +
              "\n\n直接输出文章正文。")
    draft = strip_think(chat([{"role": "user", "content": brief1}], model, BASE, KEY_ENV, max_tokens=4000))
    calls.append(("draft", len(draft)))
    raw2 = chat([{"role": "user", "content": NEUTRAL2_SYS.format(question=question, draft=draft)}],
                 model, BASE, KEY_ENV, max_tokens=1200)
    calls.append(("neutral2", len(raw2)))
    advices = [WA.norm_line(x) for x in strip_think(raw2).splitlines() if WA.norm_line(x)][:3]
    brief2 = (question + "\n\n【上一轮的建议】\n" + "\n".join("· " + a for a in advices) +
              "\n\n【初稿】\n" + draft +
              "\n\n按上面的建议写出这一轮的定稿。直接输出文章正文。")
    final = strip_think(chat([{"role": "user", "content": brief2}], model, BASE, KEY_ENV, max_tokens=4000))
    calls.append(("final", len(final)))
    errs = []
    if len(final.strip()) < 50:
        errs.append("final_too_short")
    return {"arm": "S", "tag": tag, "text": final, "draft": draft,
            "aspects": aspects, "advices": advices,
            "calls": calls, "elapsed": round(time.time() - t0, 1),
            "error": ";".join(errs) if errs else None}


def run_A(question, model, tag):
    t0 = time.time()
    raw = chat([{"role": "user", "content": question}], model, BASE, KEY_ENV, max_tokens=4000)
    txt = strip_think(raw)
    errs = []
    if len(txt.strip()) < 50:
        errs.append("text_too_short")
    return {"arm": "A", "tag": tag, "text": txt, "calls": [("direct", len(txt))],
            "elapsed": round(time.time() - t0, 1), "error": ";".join(errs) if errs else None}


def run_WF_p(question, model, tag):
    """旧实现（提示词式状态机），**逐字同源**，只换了传输层。"""
    try:
        r = run_minimal_compare.run_workflow(question, model, BASE, KEY_ENV, tag)
    except Exception as e:
        return {"arm": "WF-p", "tag": tag, "text": "", "error": "workflow:%s" % e}
    r["arm"] = "WF-p"
    if len((r.get("text") or "").strip()) < 50:
        r["error"] = (r.get("error") or "") + ";final_too_short"
    return r


# ---------------------------------------------------------------- main

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="minimax", choices=["minimax", "openrouter"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--reps", default="1,2,3")
    ap.add_argument("--arms", default="A,S,WF-p,WF-a,WF-a-R,WF-a-NO")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch_compare.jsonl"))
    args = ap.parse_args()

    global BASE, KEY_ENV
    if args.api == "minimax":
        BASE, KEY_ENV = api_any.MINIMAX_BASE, api_any.MINIMAX_KEY
        model = args.model or "MiniMax-M3"
    else:
        BASE, KEY_ENV = api_any.OPENROUTER_URL, api_any.OPENROUTER_KEY
        model = args.model or "x-ai/grok-4.20"
    args.model = model

    reps = [int(x) for x in args.reps.split(",") if x.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    batch = "arch-%s-%s" % (time.strftime("%Y%m%d-%H%M%S"), args.api)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    dispatch = {
        "A": run_A, "S": run_S, "WF-p": run_WF_p,
        "WF-a": lambda q, m, t: run_arch(q, m, t, reverse=False),
        "WF-a-R": lambda q, m, t: run_arch(q, m, t, reverse=True),
        "WF-a-NO": run_arch_noobs,
    }
    for a in arms:
        assert a in dispatch, "未知臂：%s" % a

    results, futs = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for a in arms:
            for s in reps:
                futs.append(ex.submit(dispatch[a], QUESTION, model, s))
        for fu in as_completed(futs):
            try:
                r = fu.result()
            except Exception as e:
                r = {"arm": "ERR", "tag": 0, "text": "", "error": "%s: %s" % (type(e).__name__, e)}
            r["batch_id"] = batch
            r["api"] = args.api
            results.append(r)
            print("  [%s] %s #%s  %s字 %s" % (batch, r.get("arm"), r.get("tag"),
                                              len((r.get("text") or "").strip()),
                                              ("ERR:" + str(r.get("error"))) if r.get("error") else "ok"))
    results.sort(key=lambda r: (str(r.get("arm")), r.get("tag") or 0))
    with open(args.out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(args.out.replace(".jsonl", ".usage.json"), "w", encoding="utf-8") as f:
        json.dump({"batch_id": batch, "model": model, "api": args.api,
                   "cost": api_any.cost_estimate(),
                   "trace": api_any.TRACE}, f, ensure_ascii=False, indent=2)
    print("\n[out] %s" % args.out)
    print("[batch] %s | 调用 %d 次" % (batch, len(api_any.TRACE)))
    c = api_any.cost_estimate()
    print("[token] prompt=%d completion=%d" % (c["prompt_tokens"], c["completion_tokens"]))


if __name__ == "__main__":
    main()
