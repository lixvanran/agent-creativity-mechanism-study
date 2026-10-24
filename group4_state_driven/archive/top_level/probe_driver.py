#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 驱动机有效性探针（driver probe）

════════════════════════════════════════════════════════════════════════
★ 问题：驱动机**有没有在驱动产出**？
  如果把驱动内容换掉，产出跟着换吗？

★ 三个变体（全部零判据，零阈值）
  D1 裸状态   同一份 keeps，**只去掉 brief 里的元层标记**（【这一轮要守住的取舍】等）
              ⇒ 测「提示词的格式效应」有多大
              ⇒ 若产出几乎不变 ⇒ 之前的差异来自内容，不是来自"这是状态"这件事
  D2 反极性   驱动内容换成**同一题的对立面**（复用已跑的 WF-a-R，不额外调用）
              ⇒ 测「驱动内容」本身有没有在驱动
  D3 无关驱动  驱动内容换成**结构相似、领域无关**的另一个议题
              （"公共图书馆是否应该延长夜间开放时间"——同为公共议题+两难）
              ⇒ 测**地板**：模型会不会盲从无关的驱动内容
              ⚠️ 选"结构相似"是为了让模型**有能力**照做；它仍然忽略 ⇒ 才是真地板

★ 读数（全零判官）
  dist_hit = (变体 keeps 的实词 − 基线 keeps 的实词) 在产出正文里的命中率
             ⇒ **区分性实词**才是判别力所在（两版 keeps 大部分词是共享的）
  topic_drift = 产出中本题关键词（高考/英语/作文/考试/写作）的密度
             ⇒ D3 会不会把话题带跑

★ 理想读数
  基线 dist_hit 低 ＋ D2 dist_hit 高 ＋ D3 dist_hit 低 ⇒ 驱动内容在驱动产出
  D1 与基线几乎无差异 ⇒ 之前的效应不是"提示词格式"带来的
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
from run_arch_compare import (QUESTION, STANCE_SYS, build_constraints, BASE, KEY_ENV)
import run_minimal_compare as RMC

#: 与本题结构相似、领域无关的对照议题（驱动内容用）
OFF_TOPIC = "公共图书馆是否应该延长夜间开放时间？写成一篇文章。"

#: 话题漂移的关键词
TOPIC_WORDS = ["高考", "英语", "作文", "考试", "写作", "考生", "阅卷", "模板", "评分"]


def chat_text(messages, model="MiniMax-M3", max_tokens=6000, json_mode=False):
    return api_any.chat(messages, model, BASE, KEY_ENV,
                         max_tokens=max_tokens, json_mode=json_mode)


def stance_for(topic, model="MiniMax-M3"):
    """对任意议题生成一组驱动内容（立场 + 3 条不可牺牲）。"""
    raw = chat_text([{"role": "user", "content": topic + "\n\n" + STANCE_SYS}],
                    model, max_tokens=2000, json_mode=True)
    from run_minimal_compare import loose_json
    d = loose_json(raw) or {}
    keeps = d.get("不能牺牲") if isinstance(d.get("不能牺牲"), list) else []
    keeps = [str(x).strip() for x in keeps if str(x).strip()][:3]
    return {"stance": str(d.get("立场") or "").strip(),
            "keeps": keeps or ["把这一轮真正想说的话说清楚，不要滑回套话"]}


def content_words(text):
    t = text or ""
    out = []
    for m in re.findall(r"[一-鿿]{2,}", t):
        for n in (2, 3):
            for i in range(len(m) - n + 1):
                out.append(m[i:i + n])
    for m in re.findall(r"[A-Za-z]{3,}", t):
        out.append(m.lower())
    return set(out)


def dist_hit(keeps_a, keeps_b, text):
    """keeps_a 相对 keeps_b 的**区分性实词**在 text 里的命中率。"""
    A = content_words(" ".join(keeps_a or []))
    B = content_words(" ".join(keeps_b or []))
    D = A - B
    if not D:
        return None, 0
    T = content_words(text)
    return (len(D & T) / len(D)), len(D)


CJK_RE = re.compile(r"[一-鿿]")
EN_RE = re.compile(r"[A-Za-z]")


def lang_ratio(text):
    """产出语言构成：中文占比。★ 判据跑之前必须先验这个，否则 n-gram 读数会被污染。"""
    t = text or ""
    c = len(CJK_RE.findall(t)); e = len(EN_RE.findall(t))
    return round(c / max(c + e, 1), 4)


def topic_drift(text):
    if not text:
        return None
    n = sum(text.count(w) for w in TOPIC_WORDS)
    return round(n / max(len(text) / 100.0, 1.0), 3)   # 每百字命中数


# ---------------------------------------------------------------- 变体执行

def run_D1(sample, model="MiniMax-M3"):
    """裸状态：同一 keeps，去掉所有元层标记，只重跑定稿步。"""
    s1 = sample["state1"]
    keeps = s1.get("keeps") or []
    brief = (QUESTION + "\n\n" + "\n".join(keeps) +
             "\n\n" + (s1.get("draft") or "") +      # placeholder, replaced below
             "\n\n现在写出这一轮的定稿。直接输出文章正文。")
    # 用真实初稿
    brief = (QUESTION + "\n\n" + "\n".join(keeps) +
             "\n\n" + (sample.get("draft") or "") +
             "\n\n现在写出这一轮的定稿。直接输出文章正文。")
    txt = RMC.strip_think(chat_text([{"role": "user", "content": brief}], model))
    return {"variant": "D1_naked", "tag": sample.get("tag"), "text": txt,
            "keeps_used": keeps, "calls": 1, "lang_cn_ratio": lang_ratio(txt)}


def run_D3(sample, off_keeps, model="MiniMax-M3"):
    """无关驱动：把驱动内容换掉，重跑**整条链**（立场→写作→观测→转移→定稿）。"""
    # ★ transfer() 要求 WA.State（纯函数，不接受 dict）
    st = WA.State(keeps=list(off_keeps["keeps"]), stance=off_keeps["stance"])
    brief1 = (QUESTION + "\n\n【这一轮要守住的取舍】\n" + "\n".join("· " + k for k in st.keeps) +
              "\n\n直接输出文章正文。")
    draft = RMC.strip_think(chat_text([{"role": "user", "content": brief1}], model))
    from run_arch_compare import OBSERVE_SYS
    raw = chat_text([{"role": "user", "content":
                      OBSERVE_SYS.format(question=QUESTION, draft=draft)}],
                    model, max_tokens=3500, json_mode=True)
    obs, status = WA.parse_observation(raw)
    if obs is None:
        obs = {"used": [], "gaps": [], "new_constraints": [], "sharpest": ""}
    cand = build_constraints(obs)
    new_st, trace = WA.transfer(st, obs if (obs.get("gaps") or obs.get("used")) else None,
                                rewriter=lambda g, p, e: cand)
    brief2 = (QUESTION + "\n\n【这一轮要守住的取舍】\n" + new_st.render_keeps() +
              ("\n\n【这一轮不能再走的路】\n" + new_st.render_excluded() if new_st.excluded else "") +
              "\n\n【初稿】\n" + draft +
              "\n\n现在写出这一轮的定稿。直接输出文章正文。")
    final = RMC.strip_think(chat_text([{"role": "user", "content": brief2}], model))
    return {"variant": "D3_offtopic", "tag": sample.get("tag"), "text": final,
            "keeps_used": off_keeps["keeps"], "draft": draft, "lang_cn_ratio": lang_ratio(final),
            "observation": obs, "trace": trace, "calls": 4}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "runs", "arch_compare.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "driver_probe.jsonl"))
    ap.add_argument("--model", default="MiniMax-M3")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    rs = [json.loads(l) for l in open(args.src, encoding="utf-8") if l.strip()]
    base = sorted([r for r in rs if r.get("arm") == "WF-a"], key=lambda r: r.get("tag") or 0)
    rev = {r.get("tag"): r for r in rs if r.get("arm") == "WF-a-R"}
    print("WF-a 样本 %d ｜ WF-a-R 样本 %d" % (len(base), len(rev)))

    # 无关驱动内容：生成一次
    off = stance_for(OFF_TOPIC, args.model)
    print("无关驱动内容：%s" % off["keeps"])

    batch = "dprobe-%s" % time.strftime("%Y%m%d-%H%M%S")
    # ★ 增量写盘：每完成一个立刻落盘 ⇒ 单个样本失败/卡住不丢已得结果
    out_f = open(args.out, "w", encoding="utf-8")
    def flush(rec):
        out_f.write(json.dumps(rec, ensure_ascii=False) + "\n"); out_f.flush()
    jobs = []
    for s in base:
        jobs.append(("D1", s))
        jobs.append(("D3", s))
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = []
        meta = {}
        for kind, s in jobs:
            if kind == "D1":
                fu = ex.submit(run_D1, s, args.model)
            else:
                fu = ex.submit(run_D3, s, off, args.model)
            futs.append(fu)
            meta[fu] = (kind, s)
        for fu in as_completed(futs):
            kind, s = meta[fu]
            try:
                r = fu.result()
            except Exception as e:
                print("  ERR %s #%s: %s" % (kind, s.get("tag"), e), flush=True)
                continue
            r["batch_id"] = batch
            r["src_arm"] = "WF-a"
            results.append(r)
            flush(r)
            print("  [%s] %s #%s  %d字" % (batch, kind, r.get("tag"), len(r.get("text") or "")),
                  flush=True)

    out_f.close()
    with open(args.out.replace(".jsonl", ".off.json"), "w", encoding="utf-8") as f:
        json.dump(off, f, ensure_ascii=False, indent=2)

    # ---------------- 读数 ----------------
    print("\n=== 驱动机有效性读数 ===")
    print("（dist_hit = 区分性实词命中率；分母 = 该变体相对基线的区分性实词数）")
    rows = []
    for s in base:
        tag = s.get("tag")
        base_keeps = (s.get("state1") or {}).get("keeps") or []
        # 基线：反向区分词（原 keeps − 反极性 keeps）
        rev_keeps = (rev.get(tag, {}).get("state1") or {}).get("keeps") or \
                    (rev.get(tag, {}).get("state0") or {}).get("keeps") or []
        bh, bn = dist_hit(base_keeps, rev_keeps, s.get("text"))
        r_h, r_n = dist_hit(rev_keeps, base_keeps, (rev.get(tag, {}).get("text") or ""))
        rows.append({"tag": tag,
                     "基线(原驱动)dist_hit": bh, "基线分母": bn,
                     "D2(反极性)dist_hit": r_h, "D2分母": r_n,
                     "基线topic_drift": topic_drift(s.get("text")),
                     "D2_topic_drift": topic_drift(rev.get(tag, {}).get("text"))})
    for r in rows:
        print("  #%s 基线 dist_hit=%s(分母%s) ｜ D2 反极性 dist_hit=%s(分母%s) ｜ 漂移 %s→%s"
              % (r["tag"],
                 "%.3f" % r["基线(原驱动)dist_hit"] if r["基线(原驱动)dist_hit"] is not None else "-",
                 r["基线分母"],
                 "%.3f" % r["D2(反极性)dist_hit"] if r["D2(反极性)dist_hit"] is not None else "-",
                 r["D2分母"], r["基线topic_drift"], r["D2_topic_drift"]))

    d1 = [r for r in results if r["variant"] == "D1_naked"]
    d3 = [r for r in results if r["variant"] == "D3_offtopic"]
    print("\n  D1（裸状态）—— 与基线的实词重合：")
    for r in sorted(d1, key=lambda x: x.get("tag") or 0):
        s = [x for x in base if x.get("tag") == r.get("tag")][0]
        ov = dist_hit(r["keeps_used"], [], r.get("text"))
        base_ov = dist_hit(s["state1"]["keeps"], [], s.get("text"))
        inter = content_words(r.get("text")) & content_words(s.get("text"))
        uni = content_words(r.get("text")) | content_words(s.get("text"))
        print("    #%s  中文占比=%.0f%%  裸状态正文 vs 原正文 实词Jaccard=%.4f ｜ 自身驱动词命中=%.3f / 基线=%.3f"
              % (r.get("tag"), 100 * (r.get("lang_cn_ratio") or 0), len(inter) / len(uni) if uni else 0,
                 ov[0] or 0, base_ov[0] or 0))
    print("\n  D3（无关驱动）—— 话题漂移：")
    for r in sorted(d3, key=lambda x: x.get("tag") or 0):
        print("    #%s  %d字  中文占比=%.0f%%  漂移=%.3f/百字  无关驱动词命中=%.3f(分母%s)"
              % (r.get("tag"), len(r.get("text") or ""), 100 * (r.get("lang_cn_ratio") or 0),
                 topic_drift(r.get("text")) or 0,
                 (dist_hit(r["keeps_used"], [], r.get("text"))[0] or 0),
                 dist_hit(r["keeps_used"], [], r.get("text"))[1]))

    print("\n[out] %s  (调用 %d 次)" % (args.out, len(api_any.TRACE)))


if __name__ == "__main__":
    main()
