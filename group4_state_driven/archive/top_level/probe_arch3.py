#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · v3 探针（D0 纯重跑地板 / D2' 换决策 / D3 无关议题）

════════════════════════════════════════════════════════════════════════
★ 严格依据 PREREG_v3.md §3 的判据设计

  D0   **纯重跑地板**：同输入、同驱动、同代码，整条链再跑一次
       ⇒ 读数：产出 vs 基线的实词 Jaccard
       ⇒ 作用：给"任何差异"一个自然波动的量级。**缺它 ⇒ 一切结论不可判。**

  D2'  **换决策（单变量）**：gaps、观测、实体、代码、模板**全同**，
       只把**决策**（对每个缺口的 depth/priority）换掉
       ⇒ 换法：让模型在**同样的 gaps** 上做**反极性**表态（每个 depth 取相反）
         （决策仍是模型产物，不是代码编造）
       ⇒ 测的正是第四组的核心命题：**取舍内容 → 产出**
       ⇒ 读数：
           · 产出 vs 基线 实词 Jaccard（期望显著低于 D0）
           · R_tradeoff = (换后"被选为深入展开"的实体出现率)
                        − (换前同一实体的出现率)  ⇒ 期望 > 0

  D3   **无关议题（盲从地板）**：把 gaps 换成**结构相似、领域无关**的另一个议题
       （"公共图书馆是否应延长夜间开放时间"的缺口）
       ⇒ 测：模型对**无关**的取舍是不是也照做
       ⇒ 若 D2' 与 D3 不可区分 ⇒ 不可分辨

★ 读数全部零判官；所有 n-gram 读数**先过语言闸门**（中文占比 ≥ 0.9）。
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
import workflow_arch3 as WA3
from run_minimal_compare import QUESTION, strip_think, loose_json
from run_arch3_compare import (chat, render, gated_call, step_stance3, step_observe3,
                               step_decide, DECIDE_SYS, OBSERVE3_SYS, MODEL)
import run_minimal_compare as RMC

OFF_TOPIC = "公共图书馆是否应该延长夜间开放时间？写成一篇文章。"

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


FLIP = {"深入展开": "放弃", "放弃": "深入展开", "点到为止": "点到为止"}


def decisions_flipped(decs):
    """反极性决策：每个 depth 取相反，优先级倒序。"""
    out = []
    for d in decs:
        nd = dict(d)
        nd["depth"] = FLIP.get(d.get("depth"), d.get("depth"))
        try:
            nd["priority"] = 4 - int(d.get("priority") or 2)
        except Exception:
            pass
        nd["note"] = "（反极性）"
        out.append(nd)
    return out


def run_chain(st, draft, decisions=None, obs=None, variant="", tag=0, use_obs=True,
              nl_only=True):
    """跑 v3 链的后半段（写作已完成时用 draft，否则现场写）。"""
    calls = []
    if draft is None:
        brief1 = render(QUESTION, st.keeps, lang=st.lang)
        draft, g1, a1 = gated_call(brief1, [], [], lang=st.lang)
        calls.append("draft")
    if obs is None:
        obs, raw_o, o_st = step_observe3(QUESTION, draft)
        calls.append("observe")
    if decisions is None:
        decisions, raw_d, d_meta = step_decide(QUESTION, draft, obs.get("gaps") or [])
        calls.append("decide")
    new_st, trace = WA3.transfer3(st, obs, decisions, draft)
    if nl_only:
        # ★ 只走自然语言通道 ⇒ 无代码强制 ⇒ "产出怎么变"是**模型的选择**
        brief2 = render(QUESTION, new_st.keeps, nl_decisions=new_st.render_nl_decisions(),
                        draft=draft, final=True, lang=new_st.lang)
        final, g2, a2 = gated_call(brief2, [], [], lang=new_st.lang)
    else:
        brief2 = render(QUESTION, new_st.keeps, new_st.must_include, new_st.forbidden,
                        new_st.excluded, draft, final=True, lang=new_st.lang)
        final, g2, a2 = gated_call(brief2, new_st.must_include,
                                   new_st.forbidden + new_st.excluded, lang=new_st.lang)
    calls.append("final")
    return {"variant": variant, "tag": tag, "text": final, "draft": draft,
            "state1": new_st.to_dict(), "observation": obs, "trace": trace,
            "decisions": decisions, "gates": {"final": g2}, "calls": calls,
            "lang_cn_ratio": lang_cn(final)}


def off_topic_gaps():
    """D3：结构相似、领域无关的另一个议题的缺口（由模型生成后代码校验）。"""
    st, raw_s, s_st = step_stance3(OFF_TOPIC)
    brief1 = render(OFF_TOPIC, st.keeps, lang="zh")
    draft, g1, a1 = gated_call(brief1, [], [], lang="zh")
    raw_o = chat([{"role": "user", "content":
                   OBSERVE3_SYS.format(question=OFF_TOPIC, draft=draft)}],
                 max_tokens=3500, json_mode=True)
    obs, status = WA3.parse_observation3(raw_o, draft)
    if not obs:
        raise RuntimeError("D3 观测解析失败: %s" % status)
    return obs, st, draft


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "runs", "arch3_compare.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch3_probe.jsonl"))
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    rs = [json.loads(l) for l in open(args.src, encoding="utf-8") if l.strip()]
    arm_pick = "WF-a3-NL" if any(r.get("arm") == "WF-a3-NL" for r in rs) else "WF-a3"
    print("探针基准臂：%s" % arm_pick, flush=True)
    # 同批补跑 ⇒ 同 tag 可能多条 ⇒ 取**有效**的最后一条
    _buck = {}
    for r in rs:
        if r.get("arm") != arm_pick:
            continue
        _buck.setdefault(r.get("tag"), []).append(r)
    base = []
    for tag, g in _buck.items():
        good = [x for x in g if not (x.get("gate_failed") or x.get("error"))]
        base.append(good[-1] if good else g[-1])
    base.sort(key=lambda r: r.get("tag") or 0)
    print("WF-a3 可用样本：%d" % len(base), flush=True)
    if not base:
        print("无有效样本"); return

    off_obs, off_st, off_draft = off_topic_gaps()
    print("无关议题缺口数：%d" % len(off_obs.get("gaps") or []), flush=True)

    batch = "a3probe-%s" % time.strftime("%Y%m%d-%H%M%S")
    out_f = open(args.out, "w", encoding="utf-8")
    futs, meta = [], {}

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        def sub(fn, *a, **kw):
            tag = kw.pop("_tag", "?")
            fu = ex.submit(fn, *a, **kw)
            futs.append(fu); meta[fu] = tag

        for r in base:
            tag = r.get("tag")
            st = WA3.State3(**r["state0"])
            obs = r.get("observation") or {}
            decs = (r.get("trace") or {}).get("decisions") or []
            # D0：纯重跑（同输入同驱动，整条链重跑）
            sub(run_chain, st, None, None, None, "D0_rerun", tag, True, _tag="D0#%s" % tag)
            # D2'：换决策（gaps/观测/实体全同，只换 depth/priority）
            sub(run_chain, st, r.get("draft"), decisions_flipped(decs), obs,
                "D2flip_NL", tag, True, _tag="D2#%s" % tag)
            # D3：无关议题的 gaps（结构相似、领域无关）
            sub(run_chain, st, r.get("draft"), None, off_obs,
                "D3off_NL", tag, True, _tag="D3#%s" % tag)
        results = []
        for fu in as_completed(futs):
            try:
                rec = fu.result()
            except Exception as e:
                import traceback
                print("  ERR %s: %s" % (meta[fu], e), flush=True)
                traceback.print_exc()
                continue
            rec["batch_id"] = batch
            results.append(rec)
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n"); out_f.flush()
            print("  [%s] %-14s #%s %5d字 中文%.0f%%" % (
                batch, rec["variant"], rec.get("tag"), len(rec.get("text") or ""),
                100 * (rec.get("lang_cn_ratio") or 0)), flush=True)
    out_f.close()
    print("\n[out] %s ｜ 调用 %d 次" % (args.out, len(api_any.TRACE)))


if __name__ == "__main__":
    main()
