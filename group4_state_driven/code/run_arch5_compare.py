#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · v5 主实验：编号化取舍声明 + 结构化绑定。

臂（等预算可比）：
  A              单次直答                                    1 次调用
  WF-v5          状态 → K=3 候选（提示给缺口内容+编号）→ **两个打分器评估同一批候选** → 各选 1   4 次调用
  WF-v5-blind    同上，但提示**只给编号不给内容** ⇒ 候选盲选 ⇒ ★ **D0 地板**

★ 判决位置（★ 与 v4 不同！）：
  - **H3′（状态化打分 vs 通用打分）在 `WF-v5` 臂内判决**：
    候选看到缺口内容但**不知道状态的决定** ⇒ 声明是**自主判断** ⇒ 状态化打分**非恒真**。
  - `WF-v5-blind` 臂 = **地板**（盲选时的对齐率）⇒ 用来判"状态信息是否真的帮到了候选"。

★ 全部主读数零判官（声明是编号离散结构；兑现/违禁由代码从正文抽行为核验）。
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import api_any                                            # noqa: E402
import workflow_arch5 as WA5                              # noqa: E402
from run_arch3_compare import (                           # noqa: E402
    step_stance3, step_observe3, step_decide, strip_think, chat)
from run_multitopic import MINIMAL                        # noqa: E402

QUESTION = "你如何看待高考英语作文？写成一篇文章。"
K = 3
CAND_LO, CAND_HI = 600, 900


# ---------------------------------------------------------------- 状态构建
def build_state5(question):
    """复用 v3 的状态链：立场 → 初稿 → 观测 → 决策（封闭枚举）⇒ State5。"""
    st3, raw_s, _ = step_stance3(question)
    brief1 = WA5.render_candidate_prompt5(
        WA5.State5(stance=st3.stance, keeps=st3.keeps, gaps=[], decisions=[]),
        CAND_LO, CAND_HI)
    draft = strip_think(chat([{"role": "user", "content": brief1}], max_tokens=6000))
    obs, raw_o, o_st = step_observe3(question, draft)
    obs = obs or {"gaps": []}
    gaps = obs.get("gaps") or []
    if not gaps:
        return WA5.State5(stance=st3.stance, keeps=st3.keeps, gaps=[], decisions=[]), \
            {"obs_status": o_st, "n_gaps": 0, "note": "无缺口 ⇒ 状态退化为无取舍"}
    decs, raw_d, d_meta = step_decide(question, draft, gaps)
    # ★ 缺口编号：代码统一重排为 1..N（保证编号连续、结构化）
    ngaps = []
    for i, g in enumerate(gaps, 1):
        g2 = dict(g)
        g2["index"] = i
        ngaps.append(g2)
    # ★ 决策里的 gap_index 一并重映射（决策是按位置给的）
    old_idx = [int(g.get("index") or (i + 1)) for i, g in enumerate(gaps)]
    remap = {old: new for new, old in enumerate(old_idx, 1)}
    ndecs = []
    for d in decs:
        d2 = dict(d)
        d2["gap_index"] = remap.get(int(d.get("gap_index") or 0), 0)
        ndecs.append(d2)
    s5 = WA5.State5(stance=st3.stance, keeps=st3.keeps, gaps=ngaps, decisions=ndecs)
    return s5, {"obs_status": o_st, "n_gaps": len(ngaps), "n_decisions": len(ndecs),
                "decisions": ndecs}


# ---------------------------------------------------------------- 候选生成
def gen_candidates5(st, k=K, blind=False):
    """生成 K 个候选。★ 提示**只给编号 + （非 blind 时）缺口内容**，绝不给状态决定。"""
    max_i = max(st.all_indices()) if st.all_indices() else 0

    def one(i):
        # ★ 每个候选拿到的提示只差"你是第几次尝试"⇒ 候选自己差异化
        prompt = WA5.render_candidate_prompt5(st, CAND_LO, CAND_HI, blind=blind,
                                               cand_no=i, k=k)
        try:
            raw = chat([{"role": "user", "content": prompt}], max_tokens=3200)
            txt = strip_think(raw)
            w, d, rawline, ok = WA5.parse_declaration(txt)
            # 编号越界（声明了不存在的缺口）⇒ 显式标记
            oob = sorted((w | d) - set(range(1, max_i + 1))) if max_i else []
            err = None
            if not ok:
                err = "no_declaration"
            elif oob:
                err = "out_of_range_ids:%s" % oob
            if err and "no_declaration" in err:
                # 重试一次（模型偶尔漏写第一行）
                raw = chat([{"role": "user", "content": prompt}], max_tokens=3600)
                txt = strip_think(raw)
                w, d, rawline, ok = WA5.parse_declaration(txt)
                oob = sorted((w | d) - set(range(1, max_i + 1))) if max_i else []
                err = None if ok else "no_declaration"
                if ok and oob:
                    err = "out_of_range_ids:%s" % oob
            return WA5.Candidate5(idx=i, text=txt, decl_write=w, decl_drop=d,
                                  decl_raw=rawline, decl_parsed=ok, error=err)
        except Exception as e:
            return WA5.Candidate5(idx=i, text="",
                                  error="%s: %s" % (type(e).__name__, e))

    # ★ 内层**串行**：总并发 = 外层 workers（≤4）⇒ 避免 MiniMax Token Plan 429
    #   （教训：嵌套线程池 3×3=9 并发 ⇒ 429 退避 20/40/60s ⇒ 整个实验慢到不可用）
    cands = [one(i) for i in range(1, k + 1)]
    cands.sort(key=lambda c: c.idx)
    return cands


# ---------------------------------------------------------------- 臂
def run_A5(tag):
    t0 = time.time()
    txt = strip_think(chat([{"role": "user", "content": QUESTION}], max_tokens=6000))
    return {"arm": "A", "tag": tag, "text": txt, "calls": ["direct"],
            "elapsed": round(time.time() - t0, 1),
            "error": None if len(txt.strip()) >= 50 else "text_too_short"}


def _run_wf5(tag, blind=False):
    t0 = time.time()
    st, meta = build_state5(QUESTION)
    cands = gen_candidates5(st, blind=blind)
    ok_c = [c for c in cands if not c.error and (c.text or "").strip() and c.decl_parsed]
    rec = {"arm": "WF-v5-blind" if blind else "WF-v5", "tag": tag, "blind": blind,
           "state": st.to_dict(), "meta": meta,
           "candidates": [c.to_dict() for c in cands],
           "calls": ["stance", "draft", "observe", "decide"] + ["cand"] * K,
           "elapsed": round(time.time() - t0, 1), "error": None}
    if not ok_c:
        rec["error"] = "no_valid_declared_candidate"
        rec["text"] = ""
        return rec
    # 两个打分器评估**同一批**候选
    ch_s, sc_s = WA5.select5(ok_c, lambda c: WA5.score_state_alignment5(c, st))
    ch_g, sc_g = WA5.select5(ok_c, lambda c: WA5.score_generic5(c, st))
    # 候选项：状态化打分可能为 None（无声明）⇒ select 已排除 ⇒ 记录被排除数
    rec["n_cand_ok"] = len(ok_c)
    rec["n_cand_scored"] = len(sc_s)
    rec["score_state"] = sc_s
    rec["score_generic"] = sc_g
    rec["chosen_state_idx"] = ch_s.idx if ch_s else None
    rec["chosen_generic_idx"] = ch_g.idx if ch_g else None
    rec["align_state"] = WA5.score_state_alignment5(ch_s, st) if ch_s else None
    rec["align_generic"] = WA5.score_state_alignment5(ch_g, st) if ch_g else None
    rec["fulfill_state"] = WA5.score_fulfillment5(ch_s, st) if ch_s else None
    rec["fulfill_generic"] = WA5.score_fulfillment5(ch_g, st) if ch_g else None
    rec["violation_state"] = WA5.score_violation5(ch_s, st) if ch_s else None
    rec["violation_generic"] = WA5.score_violation5(ch_g, st) if ch_g else None
    rec["text"] = ch_s.text if ch_s else ""
    # 候选多样性（诊断）
    from analyze_arch3 import J
    sims = []
    for i in range(len(ok_c)):
        for j in range(i + 1, len(ok_c)):
            sims.append(round(J(ok_c[i].text, ok_c[j].text), 4))
    rec["candidate_pair_sim"] = sims
    return rec


def run_WF_v5(tag):
    return _run_wf5(tag, blind=False)


def run_WF_v5_blind(tag):
    return _run_wf5(tag, blind=True)


DISPATCH = {"A": run_A5, "WF-v5": run_WF_v5, "WF-v5-blind": run_WF_v5_blind}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", default="1,2,3")
    ap.add_argument("--arms", default="A,WF-v5,WF-v5-blind")
    ap.add_argument("--workers", type=int, default=3,
                    help="★ 外层并发；内层候选生成已改串行 ⇒ 总并发 = workers（≤4）")
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch5_compare.jsonl"))
    ap.add_argument("--batch-id", default=None)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--topics", default="G01")
    args = ap.parse_args()

    global QUESTION
    reps = [int(x) for x in args.reps.split(",") if x.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    for a in arms:
        assert a in DISPATCH, a
    tids = [x.strip() for x in args.topics.split(",") if x.strip()]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out_f = open(args.out, "a" if args.append else "w", encoding="utf-8")

    for tid in tids:
        QUESTION = MINIMAL.get(tid, QUESTION)
        batch = args.batch_id or ("arch5-%s-%s" % (tid, time.strftime("%Y%m%d-%H%M%S")))
        print("\n===== %s | batch=%s =====" % (tid, batch), flush=True)
        futs, meta = [], {}
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for a in arms:
                for s_ in reps:
                    fu = ex.submit(DISPATCH[a], s_)
                    futs.append(fu); meta[fu] = (a, s_)
            for fu in as_completed(futs):
                a, s_ = meta[fu]
                try:
                    r = fu.result()
                except Exception as e:
                    r = {"arm": a, "tag": s_, "text": "",
                         "error": "%s: %s" % (type(e).__name__, e)}
                r["batch_id"] = batch
                r["model"] = "MiniMax-M3"
                r["topic_id"] = tid
                r["question"] = QUESTION
                out_f.write(json.dumps(r, ensure_ascii=False) + "\n"); out_f.flush()
                extra = ""
                if a.startswith("WF-v5"):
                    extra = " | state_pick=%s generic_pick=%s align(s)=%s align(g)=%s decl_ok=%s/%s" % (
                        r.get("chosen_state_idx"), r.get("chosen_generic_idx"),
                        r.get("align_state"), r.get("align_generic"),
                        r.get("n_cand_scored"), r.get("n_cand_ok"))
                print("  [%s] %-13s #%s %5d字 %s%s" % (
                    batch, a, s_, len((r.get("text") or "").strip()),
                    ("ERR:" + str(r.get("error"))[:46]) if r.get("error") else "ok", extra),
                    flush=True)
    out_f.close()
    c = api_any.cost_estimate()
    print("\n[total] 调用 %d 次 ｜ prompt=%d completion=%d"
          % (c["calls"], c["prompt_tokens"], c["completion_tokens"]))


if __name__ == "__main__":
    main()
