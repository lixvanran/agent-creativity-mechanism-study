# -*- coding: utf-8 -*-
"""架构 V2「核验在环」——不是探索出来的，是**测出来应该长什么样**。

依据（全部来自本项目的实测）：
  1. 矛盾率是唯一有方差的量（法律域 0.4% vs 政策域 33–71%）
     → 所以它能当仲裁器
  2. 「选赢家」在有限样本上信号量≈0（Spearman +0.166，训练第1名→留出第15名）
     → 所以架构不能靠「在题集上挑最好的那个」
  3. 覆盖是单调的（候选越多并集越大），argmax 没有自由参数
     → 所以「收集并集 + 按证据过滤」既不过拟合又单调

架构：
  ① 生成 N 份候选（不同切入角度）      ← 思维面变宽
  ② 抽取全部断言，去重
  ③ 逐条对照依据核验                   ← 唯一的外部锚
  ④ 组装最终答案：只用被依据支持的断言；
     依据未提及的，明确标为「未见明确规定」；被依据否掉的，剔除
  ⑤ **重新核验最终答案**                ← 闭环

关键性质：
  - 宽度 = 所有候选触及的**不同考虑**（含未提及的，作为「已探索但未证」清单）
  - 错误 = 理论上被构造压到 0（最终答案只由被支持的断言组成）
  - 单调：候选越多 → 宽度越大，且不引入新的错误
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM                        # noqa: E402
from creativity_lab.metrics import _mat                      # noqa: E402
from creativity_lab.workflow import BRANCH_Q, OUT_SPEC       # noqa: E402
from creativity_lab.verify import (check_claims, extract_claims, score_of)  # noqa: E402

OUT = "runs/v2arch"
os.makedirs(OUT, exist_ok=True)
DATA = json.load(open("creativity_lab/data/policy_topics.json", encoding="utf-8"))
LAWS, TOPICS = DATA["laws"], DATA["topics"]
law_of = {t["tid"]: t["law"] for t in TOPICS}
SEARCH = TOPICS[:5]
HOLD = TOPICS[5:]

COMPOSE = """下面是针对同一问题的多份独立分析，已逐条对照权威依据核验过。

【经核验成立、可以直接使用的内容】
{sup}

【依据未覆盖、可以参考但需注明不确定的内容】
{un}

【与依据冲突、已剔除的内容（不要使用，也不要复述）】
{bad}

【要求】
1. 只使用【经核验成立】里的内容作为事实性依据。
2. 【依据未覆盖】里的内容可以提，但要明确说明这一点属于建议或推断。
3. 绝不出现【与依据冲突】里的任何内容。
4. 给出可执行的具体方案，300字以内。

问题：{ask}"""

ANGLES = [
    "先确定适用的规则来源，再据此作答。",
    "从「哪些做法会踩红线」的角度切入。",
    "从「办理流程与所需材料」的角度切入。",
    "从「按不同情形分别处理」的角度切入。",
]


def embed_rows(ts):
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    return _mat(LLM().embed(uniq))[idx]


def dedup_n(claims, thr=0.75):
    if not claims:
        return []
    M = embed_rows(claims)
    S = M @ M.T
    keep = []
    for i in range(len(claims)):
        if all(S[i, j] < thr for j in keep):
            keep.append(i)
    return [claims[i] for i in keep]


def run_v2(topic, n_cand=3):
    """完整的 V2 架构跑一遍，返回最终答案 + 中间数据。"""
    ev = LAWS[law_of[topic["tid"]]]["evidence"]
    ask = topic["ask"]

    # ① 生成 N 份候选（不同切入角度）
    cands = []
    for i in range(n_cand):
        p = BRANCH_Q.format(ask=ask, pf="\n\n【切入角度】" + ANGLES[i % len(ANGLES)], spec=OUT_SPEC)
        a = LLM().chat(p, model="MiniMax-M3", purpose="v2cand", min_ok=150)
        if a and len(a) > 40:
            cands.append(a)
    if not cands:
        return None

    # ② 抽取 + 去重
    raw = []
    for c in cands:
        raw.extend(extract_claims(LLM(), c))
    pool = dedup_n(raw, 0.75)
    if not pool:
        return None

    # ③ 逐条核验
    verd = check_claims(LLM(), ask, ev, pool)
    sup = [c for c in pool if verd.get(c) == "支持"]
    bad = [c for c in pool if verd.get(c) == "矛盾"]
    un = [c for c in pool if verd.get(c) in ("未提及", "非主张")]

    # ④ 组装
    if not sup and not un:
        return None
    p = COMPOSE.format(
        sup="\n".join("- " + c for c in sup) or "（无）",
        un="\n".join("- " + c for c in un) or "（无）",
        bad="\n".join("- " + c for c in bad) or "（无）",
        ask=ask)
    final = LLM().chat(p, model="MiniMax-M3", purpose="v2compose", min_ok=120)
    if not final or len(final) < 40:
        return None

    # ⑤ 重新核验最终答案（闭环）
    fclaims = extract_claims(LLM(), final)
    fverd = check_claims(LLM(), ask, ev, fclaims)
    fs = score_of(fverd, fclaims)
    return dict(tid=topic["tid"], final=final, n_cand=len(cands),
                pool_size=len(pool), n_sup=len(sup), n_bad=len(bad), n_un=len(un),
                f_claims=len(fclaims), f_sup=fs["n_sup"], f_con=fs["n_con"],
                f_non=fs["n_non"], f_unment=fs["n_unment"],
                f_score=fs["score"], width=len(pool),
                f_width=len(dedup_n(fclaims, 0.75)),
                final_text=final)


def baseline_direct(topic):
    ev = LAWS[law_of[topic["tid"]]]["evidence"]
    a = LLM().chat("问题：%s\n\n给出你的方案与理由，400字以内。" % topic["ask"],
                    model="MiniMax-M3", purpose="b2direct", min_ok=150)
    if not a or len(a) < 40:
        return None
    cs = extract_claims(LLM(), a)
    v = check_claims(LLM(), topic["ask"], ev, cs)
    s = score_of(v, cs)
    return dict(tid=topic["tid"], n_cand=1, pool_size=len(dedup_n(cs, 0.75)), n_sup=s["n_sup"],
                n_bad=s["n_con"], n_un=s["n_unment"], f_claims=len(cs),
                f_sup=s["n_sup"], f_con=s["n_con"], f_non=s["n_non"],
                f_unment=s["n_unment"], f_score=s["score"], width=len(cs),
                f_width=len(dedup_n(cs, 0.75)), final_text=a,
                f_fail=sum(1 for c in cs if False))


def summarize(rows, name):
    legal = sum(r["f_sup"] + r["f_con"] for r in rows)
    fail = sum(r["f_claims"] for r in rows) - legal - sum(r["f_unment"] for r in rows) - sum(r["f_non"] for r in rows)
    print("  %-14s 宽度 %5.2f  最终答案支持率 %5.1f%%  矛盾率 %5.1f%%  "
          "最终断言 %d 条 [已核验 %d / 未提及 %d / 解析失败 %d]"
          % (name, np.mean([r["width"] for r in rows]),
             100 * sum(r["f_sup"] for r in rows) / max(legal, 1),
             100 * sum(r["f_con"] for r in rows) / max(legal, 1),
             sum(r["f_claims"] for r in rows), legal,
             sum(r["f_unment"] for r in rows), fail), flush=True)
    return dict(width=float(np.mean([r["width"] for r in rows])),
                conflict=sum(r["f_con"] for r in rows) / legal,
                support=sum(r["f_sup"] for r in rows) / legal,
                f_width=float(np.mean([r["f_width"] for r in rows])),
                n=len(rows))


def main():
    t0 = time.time()
    for label, TPs in (("搜索题", SEARCH), ("留出题", HOLD)):
        print("\n== %s %s ==" % (label, [t["tid"] for t in TPs]), flush=True)
        res = {}
        for name, fn in (("direct 基线", baseline_direct), ("V2 核验在环", run_v2)):
            rows = []
            with ThreadPoolExecutor(max_workers=2) as ex:
                futs = {ex.submit(fn, T): T["tid"] for T in TPs}
                for f in as_completed(futs):
                    try:
                        r = f.result()
                        if r: rows.append(r)
                    except Exception as e:
                        print("  ERR %s" % str(e)[:60], flush=True)
            res[name] = rows
            if rows:
                summarize(rows, name)
            else:
                print("  %-14s 全部失败" % name, flush=True)
        json.dump(res, open("%s/%s.json" % (OUT, "search" if label == "搜索题" else "hold"),
                            "w"), ensure_ascii=False, indent=1, sort_keys=True)
    print("\n总耗时 %.0f 分钟" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
