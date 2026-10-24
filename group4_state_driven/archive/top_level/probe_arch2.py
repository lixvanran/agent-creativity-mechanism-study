#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · v2 状态机的探针（D1/D2/D3/D4）

════════════════════════════════════════════════════════════════════════
★ 四个变体，各管一件事
  D1 裸状态   同一份状态，**去掉候选集**（必含实体 + 禁含措辞）⇒ **波动地板**
  D2 反极性   驱动内容换成同一题的对立面，整条链重建         ⇒ **信号**
  D3 无关驱动 驱动内容换成结构相似、领域无关的议题           ⇒ **盲从地板**
  D4 换源     把观测换成**别的样本的初稿** ⇒ 候选集（必含/禁含）是否整份换源
              ⇒ 这是 v2 新增的封闭槽位的**直接归因读数**

★ 读数（全零判官）
  实词 J        产出 vs 基线（越低 = 差异越大）
  话题密度      每百字命中本题关键词数
  must_hit      必含实体字面命中率（候选集是否被执行）
  forbidden_hit 禁含措辞字面命中（禁含是否被执行）
  候选集换源    D4 的必含/禁含措辞**逐字**来自哪份初稿

★ 判据纪律：所有读数**先过语言闸门**（中文占比 ≥ 0.9），漂移样本单列。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import api_any
import workflow_arch as WA
import workflow_arch2 as WA2
from run_minimal_compare import QUESTION, STANCE_SYS, strip_think, loose_json
from run_arch2_compare import (chat, step_stance2, step_observe2, render_writing,
                               gated_call, MODEL, BASE, KEY_ENV)
import run_minimal_compare as RMC

OFF_TOPIC = "公共图书馆是否应该延长夜间开放时间？写成一篇文章。"
REVERSE_SYS = """你刚才对下面这个写作问题给出的立场是：
{stance}

现在请你站在**与它相反**的立场上，重新想清楚：站在另一边，你的写作会牺牲什么。
你必须做出取舍，不许骑墙、不许"两边都有道理"。

[问题]
{question}

只输出一个 JSON 对象，不要输出 JSON 以外的任何文字、不要用代码围栏。
{{"立场":"...","不能牺牲":["...","...","..."],"最容易失守":"...","第一次反应":"..."}}"""

CJK = re.compile(r"[一-鿿]")
EN = re.compile(r"[A-Za-z]")
TOPIC_WORDS = ["高考", "英语", "作文", "考试", "写作", "考生", "阅卷", "模板", "评分"]


def words(t):
    t = t or ""
    out = []
    for m in re.findall(r"[一-鿿]{2,}", t):
        for n in (2, 3):
            for i in range(len(m) - n + 1):
                out.append(m[i:i + n])
    for m in re.findall(r"[A-Za-z]{3,}", t):
        out.append(m.lower())
    return set(out)


def J(a, b):
    A, B = words(a), words(b)
    return round(len(A & B) / len(A | B), 4) if (A | B) else None


def lang_cn(t):
    t = t or ""
    if not t.strip():
        return None
    c, e = len(CJK.findall(t)), len(EN.findall(t))
    return round(c / max(c + e, 1), 4)


def topic(t):
    return round(sum(t.count(w) for w in TOPIC_WORDS) / max(len(t or "") / 100, 1), 3)


def stance_off_topic():
    raw = chat([{"role": "user", "content": OFF_TOPIC + "\n\n" + STANCE_SYS}],
               max_tokens=2000, json_mode=True)
    d = loose_json(raw) or {}
    keeps = d.get("不能牺牲") if isinstance(d.get("不能牺牲"), list) else []
    keeps = [str(x).strip() for x in keeps if str(x).strip()][:3]
    return {"stance": str(d.get("立场") or "").strip(),
            "keeps": keeps or ["把这一轮真正想说的话说清楚，不要滑回套话"]}


def stance_reversed(stance):
    raw = chat([{"role": "user", "content":
                 REVERSE_SYS.format(stance=stance, question=QUESTION)}],
                max_tokens=2000, json_mode=True)
    d = loose_json(raw) or {}
    keeps = d.get("不能牺牲") if isinstance(d.get("不能牺牲"), list) else []
    keeps = [str(x).strip() for x in keeps if str(x).strip()][:3]
    return {"stance": str(d.get("立场") or "").strip(),
            "keeps": keeps or ["把这一轮真正想说的话说清楚，不要滑回套话"]}


def run_chain(tag, st, draft=None, use_candidate=True, obs_draft=None, variant=""):
    """跑一遍 v2 链。st=State2；draft=None 则先生成初稿。"""
    calls = []
    if draft is None:
        brief1 = render_writing(QUESTION, st.keeps)
        draft, g1, _ = gated_call(brief1, [], [], tag, "draft")
        calls.append("draft")
    obs, raw_o, o_st = step_observe2(QUESTION, obs_draft if obs_draft is not None else draft)
    calls.append("observe")
    cand = list(obs.get("new_constraints") or [])
    new_st, trace = WA2.transfer2(st, obs, rewriter=lambda g, p, e: cand)
    must = new_st.must_include if use_candidate else []
    forb = new_st.forbidden if use_candidate else []
    brief2 = render_writing(QUESTION, new_st.keeps, must, forb, draft, final=True)
    final, g2, _ = gated_call(brief2, must, forb, tag, "final")
    calls.append("final")
    return {"variant": variant, "tag": tag, "text": final, "draft": draft,
            "state1": new_st.to_dict(), "observation": {k: v for k, v in obs.items() if k != "_draft"},
            "trace": trace, "gates": {"final": g2}, "calls": calls,
            "lang_cn_ratio": lang_cn(final)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "runs", "arch2_compare.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch2_probe.jsonl"))
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    rs = [json.loads(l) for l in open(args.src, encoding="utf-8") if l.strip()]
    base = sorted([r for r in rs if r.get("arm") == "WF-a2" and not r.get("error")],
                  key=lambda r: r.get("tag") or 0)
    print("WF-a2 可用样本：%d" % len(base), flush=True)
    if len(base) < 2:
        print("样本不足"); return

    off = stance_off_topic()
    print("无关驱动：%s" % off["keeps"], flush=True)

    batch = "a2probe-%s" % time.strftime("%Y%m%d-%H%M%S")
    out_f = open(args.out, "w", encoding="utf-8")
    futs, meta = [], {}

    def submit(fn, *a, **kw):
        # ★ _tag 只用于日志，**不能**传给目标函数（否则 unexpected keyword argument）
        tag = kw.pop("_tag", "?")
        fu = ex.submit(fn, *a, **kw)
        futs.append(fu)
        meta[fu] = tag

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(base):
            st = WA2.State2(**r["state0"])
            other = base[(i + 1) % len(base)]
            # D1：去掉候选集（内容不变）
            submit(run_chain, r.get("tag"), st, r.get("draft"), False, None,
                   "D1_nocandidate", _tag="D1#%s" % r.get("tag"))
            # D2：反极性驱动（整条链重建）
            submit(run_chain_rev, r.get("tag"), i, base, off, _tag="D2#%s" % r.get("tag"))
            # D3：无关驱动（整条链重建）
            submit(run_chain_off, r.get("tag"), off, _tag="D3#%s" % r.get("tag"))
            # D4：换源（用别的样本的初稿做观测）
            submit(run_chain, r.get("tag"), st, r.get("draft"), True,
                   other.get("draft"), "D4_swapsource", _tag="D4#%s" % r.get("tag"))
        results = []
        for fu in as_completed(futs):
            try:
                rec = fu.result()
            except Exception as e:
                print("  ERR %s: %s" % (meta[fu], e), flush=True); continue
            rec["batch_id"] = batch
            results.append(rec)
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n"); out_f.flush()
            print("  [%s] %-16s #%s %5d字 中文%.0f%%" % (
                batch, rec["variant"], rec.get("tag"), len(rec.get("text") or ""),
                100 * (rec.get("lang_cn_ratio") or 0)), flush=True)
    out_f.close()
    print("\n[out] %s ｜ 调用 %d 次" % (args.out, len(api_any.TRACE)))


def run_chain_rev(tag, i, base, off, _tag=""):
    """D2：反极性立场 ⇒ 整条链重建。"""
    r = base[i]
    rev = stance_reversed((r.get("state0") or {}).get("stance", ""))
    st = WA2.State2(stance=rev["stance"], keeps=rev["keeps"], polarity="reversed")
    return run_chain(tag, st, None, True, None, "D2_reversed")


def run_chain_off(tag, off, _tag=""):
    """D3：无关驱动 ⇒ 整条链重建。"""
    st = WA2.State2(stance=off["stance"], keeps=off["keeps"])
    return run_chain(tag, st, None, True, None, "D3_offtopic")


if __name__ == "__main__":
    main()
