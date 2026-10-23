#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 架构化状态机 v3 的对照实验

════════════════════════════════════════════════════════════════════════
★ 五臂（唯一输入逐字相同）
  A        直调，1 步，无 system                         —— 基线
  WF-p     提示词式状态机（v1 旧实现，逐字同源），4 步   —— 旧机制
  S-self   **等预算 + 取舍意识 + 无状态**，5 步          —— ★ 关键新对照
  WF-a3    架构化 v3（立场→初稿→观测→决策→定稿），5 步   —— 新机制
  WF-a3-NO v3 消融：转移不喂初稿，4 步

★ S-self 为什么必须有
  "状态机"和"一次性让模型自己想清楚再写"（自我说明）在**产出上可能没区别**。
  ⇒ S-self = 同样 5 步、同样有"取舍意识"、但**不建可转移状态**
  ⇒ 若 WF-a3 ≈ S-self ⇒ **状态机相对自我说明没有增量**。

★ v3 的机制差异（相对 v2）
  · 观测步：gaps 每个带 1-2 个**相关实体**（代码逐字校验 ⊆ 初稿）
  · **决策步（新增）**：模型对每个缺口表态 depth ∈ {深入展开, 点到为止, 放弃}
    + priority ∈ {1,2,3}（**封闭枚举**，越界丢弃并标记）
  · 转移（代码）：深度=深入展开 ⇒ 该缺口实体进 must_include
                深度=放弃     ⇒ 该缺口实体进 forbidden
  · forbidden（决策推导）与 excluded（观测措辞）**分开存、分开渲染、分开归因**
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
import workflow_arch2 as WA2
import workflow_arch3 as WA3
from run_minimal_compare import QUESTION, STANCE_SYS, strip_think, loose_json
import run_minimal_compare as RMC

BASE = api_any.MINIMAX_BASE
KEY_ENV = api_any.MINIMAX_KEY
MODEL = "MiniMax-M3"


def chat(messages, max_tokens=4000, temperature=1.0, json_mode=False, model=MODEL):
    mt = max_tokens if json_mode else max(max_tokens, 6000)
    no_think = json_mode or (not json_mode and max_tokens <= 3000)
    return api_any.chat(messages, model, BASE, KEY_ENV, max_tokens=mt,
                        temperature=temperature, json_mode=json_mode, no_think=no_think)


def _patched_chat(messages, model, base, key_env, max_tokens=4000,
                  temperature=1.0, json_mode=False):
    return chat(messages, max_tokens=max_tokens, temperature=temperature,
                json_mode=json_mode, model=model)


RMC.chat = _patched_chat

# ---------------------------------------------------------------- 提示
OBSERVE3_SYS = """[问题]
{question}

[初稿]
{draft}

只根据上面这份初稿回答下面几件事。每件事用你自己的话，说清事实，不要评价、不要打分：

1. "used"：这份初稿里已经用过的具体说法、比喻、句式套路——挑最有代表性的 5 到 6 条，
   每条尽量带上原文里出现的那个具体词。
2. "gaps"：这份初稿里哪些地方只是提到了、但没有真正展开？**2 到 3 条**。
   每条写成两个字段：
     · "text"：这个缺口是什么（用自己的话）
     · "entities"：要写透这个缺口，**必须提到**这个初稿里的哪 1 到 2 个具体东西？
       给 1 到 2 个，必须是**初稿里原样出现过**的词（2 到 6 个字），不要改写、不要生造。
3. "new_constraints"：针对每一条 gap，这一轮写作具体应该守住什么？
   逐条列出，每条写明对应第几条 gap（"gap_index" 从 1 开始数）——这是结构标注，不是措辞。
4. "sharpest"：这份初稿里最锋利、最具体的一句是哪句？原文引用。

只输出一个 JSON 对象，不要输出 JSON 以外的任何文字、不要用代码围栏。
{{"used": ["..."],
 "gaps": [{{"text": "...", "entities": ["..."]}}],
 "new_constraints": [{{"gap_index": 1, "constraint": "..."}}],
 "sharpest": "..."}}"""

DECIDE_SYS = """[问题]
{question}

[初稿]
{draft}

[这份初稿里还没展开的地方]
{gaps}

你要为这一轮做一个**取舍决定**：这些地方，哪些这一轮真的写透，哪些这一轮就不碰了。

对**每一个**缺口，给出：
· "gap_index"：它是第几条（从 1 开始数）
· "depth"：只能是下面三个之一
    - "深入展开"：这一轮要真正写透它
    - "点到为止"：提一下就够，不展开
    - "放弃"：这一轮完全不碰它
· "priority"：1、2 或 3。1 = 这一轮最重要的取舍，3 = 最次要的
· "note"：一句话说明为什么这么选

★ 你不能什么都"深入展开"：**这一轮你必须放弃至少一个**（除非缺口不足两个）。

只输出一个 JSON 对象，不要输出 JSON 以外的任何文字、不要用代码围栏。
{{"decisions": [{{"gap_index": 1, "depth": "深入展开", "priority": 1, "note": "..."}}]}}"""

# ★ S-self 用的中性修订意见（不含任何状态概念）
NEUTRAL_REV_SYS = """[问题]
{question}

[初稿]
{draft}

指出上面这份初稿最需要修改的三个地方。恰好 3 行，每行一句，只说问题和该怎么改。
不要评价整篇文章，不要给立场，不要提任何"取舍"。

只输出这 3 行，不要任何编号、标题、解释、前后缀。"""

SELF_SYS = """你是一个写作助手。你将面对下面这一个写作问题。

你要先想清楚：站在这个问题的哪一边，你的写作会**牺牲什么**。
你必须做出取舍，不许骑墙、不许"两边都有道理"。

只输出一个 JSON 对象，不要输出 JSON 以外的任何文字、不要用代码围栏。键和值用英文双引号包裹。
JSON 必须能被 JSON.parse 直接解析。

字段：
· "立场" —— 一个可以被反驳的判断。
· "不能牺牲" —— JSON 数组，恰好 3 个元素，每个是一句"不能牺牲什么"。
· "最容易失守" —— 一句话，这一轮写作最容易滑向哪里。
· "第一次反应" —— 面对这个题目，你脑子里冒出来的第一个念头是什么（一句短语）。

示例格式：
{"立场":"...","不能牺牲":["...","...","..."],"最容易失守":"...","第一次反应":"..."}"""


# ---------------------------------------------------------------- 渲染
def render(question, keeps=None, must=None, forbidden=None, excluded=None,
           draft=None, final=False, lang="zh", nl_decisions=None):
    """**代码渲染 brief**：无框架标签。forbidden（决策推导）与 excluded（观测措辞）分开。"""
    parts = [question, ""]
    if lang == "zh":
        parts += ["用中文写。", ""]
    for k in (keeps or []):
        parts.append("· " + k)
    if nl_decisions:
        parts.append(nl_decisions)
    if must:
        parts.append("· 要写进文章里：" + "、".join(must))
    if forbidden:
        parts.append("· 不要写：" + "、".join(forbidden))
    if excluded:
        parts.append("· 已经写过、不要再写：" + "、".join(excluded))
    if draft is not None:
        parts += ["", draft]
    parts += ["", "现在写出定稿。直接输出文章正文。" if final else "直接输出文章正文。"]
    return "\n".join(parts)


def gated_call(brief, must, forbidden, lang="zh", max_retry=None):
    """**带闸门的创作调用**（语言/长度/必含命中/禁含）。不合格 ⇒ 代码带违规项重试。"""
    g = WA2.GATE
    max_retry = g["max_retry"] if max_retry is None else max_retry
    gates, attempts = [], []
    cur = brief
    for k in range(max_retry + 1):
        txt = strip_think(chat([{"role": "user", "content": cur}], max_tokens=6000))
        gr = WA2.gate_output(txt, must, forbidden)
        gates.append(gr.to_dict())
        attempts.append({"k": k, "len": len(txt), "lang": gr.lang_cn,
                         "must_hit": gr.must_hit, "ok": gr.ok})
        if gr.ok:
            return txt, gates, attempts
        if k == max_retry:
            attempts.append({"k": k, "hard_gate_failed": True, "reasons": gr.reasons})
            return txt, gates, attempts
        cur = brief + WA2.retry_hint(gr.reasons, lang=lang)
    return txt, gates, attempts


# ---------------------------------------------------------------- 步骤
def step_stance3(question):
    raw = chat([{"role": "user", "content": question + "\n\n" + STANCE_SYS}],
               max_tokens=2000, json_mode=True)
    d = loose_json(raw) or {}
    keeps = d.get("不能牺牲") if isinstance(d.get("不能牺牲"), list) else []
    keeps = [str(x).strip() for x in keeps if str(x).strip()][:3]
    st = WA3.State3(stance=str(d.get("立场") or "").strip(),
                    keeps=keeps or ["把这一轮真正想说的话说清楚，不要滑回套话"],
                    slip=str(d.get("最容易失守") or "").strip(),
                    first=str(d.get("第一次反应") or "").strip())
    return st, raw, ("ok" if d else "stance_empty")


def step_observe3(question, draft):
    raw = chat([{"role": "user", "content":
                 OBSERVE3_SYS.format(question=question, draft=draft)}],
               max_tokens=3500, json_mode=True)
    obs, status = WA3.parse_observation3(raw, draft)
    if obs is None:
        obs = {"used": [], "gaps": [], "new_constraints": [], "entities": [],
               "sharpest": "", "_missing": ["*"]}
    return obs, raw, status


def step_decide(question, draft, gaps):
    gl = "\n".join("%d. %s" % (g["index"], g["text"]) for g in gaps) or "（没有缺口）"
    raw = chat([{"role": "user", "content":
                 DECIDE_SYS.format(question=question, draft=draft, gaps=gl)}],
               max_tokens=2000, json_mode=True)
    decs, meta = WA3.parse_decisions(raw)
    return decs, raw, meta


# ---------------------------------------------------------------- 臂
def run_A3(tag):
    t0 = time.time()
    raw = chat([{"role": "user", "content": QUESTION}], max_tokens=4000)
    txt = strip_think(raw)
    return {"arm": "A", "tag": tag, "text": txt, "calls": [("direct", len(txt))],
            "elapsed": round(time.time() - t0, 1),
            "error": None if len(txt.strip()) >= 50 else "text_too_short"}


def run_WF_p3(tag):
    try:
        r = RMC.run_workflow(QUESTION, MODEL, BASE, KEY_ENV, tag)
    except Exception as e:
        return {"arm": "WF-p", "tag": tag, "text": "", "error": "workflow:%s" % e}
    r["arm"] = "WF-p"
    if len((r.get("text") or "").strip()) < 50:
        r["error"] = (r.get("error") or "") + ";final_too_short"
    return r


def run_S_self(tag):
    """★ 等预算 + 取舍意识 + **无状态**的对照臂（5 步）。"""
    t0 = time.time()
    calls, errs = [], []
    raw_s = chat([{"role": "user", "content": QUESTION + "\n\n" + SELF_SYS}],
                 max_tokens=2000, json_mode=True)
    calls.append(("self", len(raw_s)))
    d = loose_json(raw_s) or {}
    keeps = d.get("不能牺牲") if isinstance(d.get("不能牺牲"), list) else []
    keeps = [str(x).strip() for x in keeps if str(x).strip()][:3] or ["把真正想说的话说清楚"]
    if not d:
        errs.append("self:empty")

    brief1 = render(QUESTION, keeps)
    draft, g1, a1 = gated_call(brief1, [], [], lang="zh")
    calls.append(("draft", len(draft)))

    advices = []
    for k in range(2):                       # 两次中性修订意见（无状态）
        raw_r = chat([{"role": "user", "content":
                       NEUTRAL_REV_SYS.format(question=QUESTION, draft=draft)}],
                     max_tokens=1200)
        advices.append([WA.norm_line(x) for x in strip_think(raw_r).splitlines()
                        if WA.norm_line(x)][:3])
    calls.append(("rev1", 0)); calls.append(("rev2", 0))

    brief2 = render(QUESTION, keeps, None, None, None, draft, final=True,
                    lang="zh")
    brief2 = brief2.replace("直接输出文章正文。", "") + \
             "\n".join("· " + a for grp in advices for a in grp) + \
             "\n\n现在写出定稿。直接输出文章正文。"
    final, g2, a2 = gated_call(brief2, [], [], lang="zh")
    calls.append(("final", len(final)))
    if len(final.strip()) < 50:
        errs.append("final_too_short")
    return {"arm": "S-self", "tag": tag, "text": final, "draft": draft,
            "keeps": keeps, "advices": advices,
            "gates": {"draft": g1, "final": g2}, "attempts": {"draft": a1, "final": a2},
            "calls": calls, "elapsed": round(time.time() - t0, 1),
            "error": ";".join(errs) if errs else None}


def run_WF_a3(tag, no_obs=False, nl_only=False):
    """nl_only=True ⇒ **只走自然语言通道**：决策以叙述进入 brief，
       **不产生 must_include / forbidden**（⇒ 产出变化是模型的选择，不是代码强制）
       ⇒ 这才是可核验的**驱动力**读数。"""
    t0 = time.time()
    calls, errs = [], []
    st, raw_s, s_st = step_stance3(QUESTION)
    calls.append(("stance", len(raw_s)))
    if s_st != "ok":
        errs.append("stance:" + s_st)

    brief1 = render(QUESTION, st.keeps, lang=st.lang)
    draft, g1, a1 = gated_call(brief1, [], [], lang=st.lang)
    calls.append(("draft", len(draft)))

    obs, raw_o, o_st = step_observe3(QUESTION, draft)
    calls.append(("observe", len(raw_o)))
    if o_st == "parse_failed":
        errs.append("observe:parse_failed")

    if no_obs:
        new_st, trace = WA3.transfer3(st, None, None, draft)
    else:
        decs, raw_d, d_meta = step_decide(QUESTION, draft, obs.get("gaps") or [])
        calls.append(("decide", len(raw_d)))
        if d_meta.get("status") == "parse_failed":
            errs.append("decide:parse_failed")
        if d_meta.get("n_rejected"):
            errs.append("decide:rejected=%d" % d_meta["n_rejected"])
        new_st, trace = WA3.transfer3(st, obs, decs, draft)

    if nl_only:
        brief2 = render(QUESTION, new_st.keeps, nl_decisions=new_st.render_nl_decisions(),
                        draft=draft, final=True, lang=new_st.lang)
        final, g2, a2 = gated_call(brief2, [], [], lang=new_st.lang)
    else:
        brief2 = render(QUESTION, new_st.keeps, new_st.must_include, new_st.forbidden,
                        new_st.excluded, draft, final=True, lang=new_st.lang)
        final, g2, a2 = gated_call(brief2, new_st.must_include,
                                   new_st.forbidden + new_st.excluded, lang=new_st.lang)
    calls.append(("final", len(final)))
    if len(final.strip()) < 50:
        errs.append("final_too_short")
    # ★ **bug 修复（2026-10-21 23:25）**：原先用 `any(not ok)` ⇒ 只要**曾经**失败过
    #   就把整个样本标成失败 ⇒ 重试后**最终通过**的样本被误标（实测 WF-a3 #2：
    #   ok=False → ok=False → ok=True，仍被标失败）⇒ 白丢一个有效样本。
    #   正确判定：**最后一次**尝试是否通过。
    all_gates = list(g1) + list(g2)
    gate_failed = bool(all_gates) and (not all_gates[-1].get("ok"))
    if gate_failed:
        errs.append("hard_gate_failed")

    if nl_only:
        # ★ NL 臂：代码强制字段**未被使用** ⇒ 从 state1 里清空（避免被误读为"被强制"）
        new_st.must_include = []
        new_st.forbidden = []
        new_st.excluded = []
    return {"arm": ("WF-a3-NO" if no_obs else ("WF-a3-NL" if nl_only else "WF-a3")), "tag": tag,
            "text": final, "draft": draft,
            "state0": st.to_dict(), "state1": new_st.to_dict(),
            "nl_only": bool(nl_only),
            "observation": obs, "trace": trace,
            "gates": {"draft": g1, "final": g2}, "attempts": {"draft": a1, "final": a2},
            "calls": calls, "elapsed": round(time.time() - t0, 1),
            "gate_failed": gate_failed,
            "error": ";".join(errs) if errs else None}


# ---------------------------------------------------------------- main
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", default="1,2,3")
    ap.add_argument("--arms", default="A,WF-p,S-self,WF-a3,WF-a3-NO,WF-a3-NL")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch3_compare.jsonl"))
    ap.add_argument("--batch-id", default=None,
                    help="★ 指定批号（用于**同批**补跑，避免跨批不可比）")
    ap.add_argument("--append", action="store_true",
                    help="★ 追加到已有 jsonl（同批补跑用）")
    args = ap.parse_args()

    reps = [int(x) for x in args.reps.split(",") if x.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    batch = args.batch_id or ("arch3-%s" % time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    dispatch = {"A": run_A3, "WF-p": run_WF_p3, "S-self": run_S_self,
                "WF-a3": lambda t: run_WF_a3(t, False, False),
                "WF-a3-NO": lambda t: run_WF_a3(t, True, False),
                "WF-a3-NL": lambda t: run_WF_a3(t, False, True)}
    for a in arms:
        assert a in dispatch, a

    out_f = open(args.out, "a" if args.append else "w", encoding="utf-8")
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
            out_f.write(json.dumps(r, ensure_ascii=False) + "\n"); out_f.flush()
            print("  [%s] %-10s #%s %5d字 %s" % (
                batch, r.get("arm"), r.get("tag"), len((r.get("text") or "").strip()),
                ("ERR:" + str(r.get("error"))) if r.get("error") else "ok"), flush=True)
    out_f.close()
    c = api_any.cost_estimate()
    print("\n[out] %s" % args.out)
    print("[batch] %s ｜ 调用 %d 次 ｜ prompt=%d completion=%d"
          % (batch, c["calls"], c["prompt_tokens"], c["completion_tokens"]))


if __name__ == "__main__":
    main()
