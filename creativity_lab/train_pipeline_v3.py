# -*- coding: utf-8 -*-
"""S1d：修 direct 偏置 —— 每条断言**直接核验**，不做最近邻继承。

复核查出的两个病根都在 v3 里：
  1. verdicts 按去重池建键，候选近重复断言静默消失
  2. 0.55 余弦最近邻继承判定 → 220 条里只有 10 条是真判定，其余 102 条是传播；
     且 10 条种子里 6 条逐字出自 direct，dedup 贪心 first-wins 让 direct 赢下建池

修法：不做传播、不建种子池。每条断言各自送核验器，判定即判定。
成本 220 条 / 8 条一批 ≈ 28 次调用，与候选数无关，可承受。
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402
from creativity_lab.metrics import _mat    # noqa: E402

OUT = "runs/train"
ARMS = ("direct", "dual_fuse", "dual_select")
TOPICS = json.load(open("creativity_lab/data/legal_topics.json", encoding="utf-8"))["topics"]
texts = json.load(open("%s/texts.json" % OUT, encoding="utf-8"))
allclaims = json.load(open("%s/claims.json" % OUT, encoding="utf-8"))

CHECK3 = """下面是一份「依据原文」，之后列出若干条**待核验的具体做法**。

逐条判断这条与依据原文的关系，只回答一个词：
- 「支持」：依据原文明确认可或蕴含该条。
- 「矛盾」：依据原文明确讲了与之相反的内容。
- 「未提及」：依据原文没有讲到，或讲的是别的事。**不确定时一律答「未提及」。**

一条一行，顺序对应，不要解释，不要补充。

依据原文：
{ev}

待核验的具体做法：
{claims}"""
BATCH = 8


def verify(llm, ev, claims):
    """每条断言独立判定。不继承、不建池。"""
    out = {}
    for i in range(0, len(claims), BATCH):
        b = claims[i:i + BATCH]
        lst = "\n".join("%d. %s" % (j + 1, c) for j, c in enumerate(b))
        t = llm.chat(CHECK3.format(ev=ev, claims=lst), model="MiniMax-M3",
                     purpose="v_direct", max_tokens=1400, budgets=(2000, 2800),
                     min_ok=len(b) * 2) or ""
        lines = [x for x in t.splitlines() if x.strip()]
        for c, ln in zip(b, lines):
            m = re.search(r"支持|矛盾|未提及", ln)
            out[c] = m.group() if m else "解析失败"
    return out


def embed_rows(texts_):
    """embed 接口对完全相同的输入会去重，返回行数少于输入；必须自建索引映射。"""
    uniq, idx, seen = [], [], {}
    for t in texts_:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    V = _mat(LLM().embed(uniq))
    return V[idx]


def cov(cands, pool, llm, thr=0.55):
    if not cands or not pool:
        return 0
    M = embed_rows(list(cands) + list(pool))
    S = M[:len(cands)] @ M[len(cands):].T
    return sum(1 for i in range(len(cands)) if float(S[i].max()) >= thr)


def main():
    llm = LLM()
    print("== 直接核验每条断言（无传播、无种子池）==", flush=True)
    verd = {}
    for T in TOPICS:
        tid = T["tid"]
        pool = sorted({c for k, cs in allclaims.items()
                       if k.split("|")[0] == tid for c in cs})
        v = verify(llm, T["evidence"], pool)
        verd[tid] = v
        n = {x: sum(1 for y in v.values() if y == x) for x in ("支持", "矛盾", "未提及", "解析失败")}
        print("  %s 断言 %2d → 支持 %2d / 矛盾 %2d / 未提及 %2d / 失败 %d"
              % (tid, len(pool), n["支持"], n["矛盾"], n["未提及"], n["解析失败"]), flush=True)
    json.dump(verd, open("%s/verdicts_v3.json" % OUT, "w"), ensure_ascii=False, indent=1, sort_keys=True)

    print("\n== 每候选奖励 ==", flush=True)
    recs = []
    for k, txt in texts.items():
        tid, arm, rep = k.split("|")
        cs = allclaims[k]
        V = verd[tid]
        dpool = [c for kk, cc in allclaims.items()
                 if kk.split("|")[0] == tid and kk.split("|")[1] == "direct" for c in cc]
        if not cs:
            recs.append(dict(key=k, tid=tid, arm=arm, n_claims=0, n_sup=0, n_con=0,
                             n_new=0, n_unment=0, reward=0.0, dead=True))
            continue
        sup = [c for c in cs if V.get(c) == "支持"]
        con = [c for c in cs if V.get(c) == "矛盾"]
        un = [c for c in cs if V.get(c) == "未提及"]
        new = [c for c in sup if cov([c], dpool, llm) == 0]
        recs.append(dict(
            key=k, tid=tid, arm=arm, length=len(txt), n_claims=len(cs),
            n_sup=len(sup), n_con=len(con), n_unment=len(un), n_new=len(new),
            reward=round(len(new) / max(len(txt), 1) * 100, 4), dead=False))
    json.dump(recs, open("%s/records_v3.json" % OUT, "w"), ensure_ascii=False, indent=1, sort_keys=True)

    print("\n%-22s %5s %5s %5s %5s %5s %7s" % ("key", "clm", "sup", "con", "unm", "new", "reward"))
    for r in sorted(recs, key=lambda x: -x["reward"]):
        if r["dead"]:
            print("%-22s   —— 断言抽取失败，不参与比较" % r["key"])
        else:
            print("%-22s %5d %5d %5d %5d %5d %7.4f"
                  % (r["key"], r["n_claims"], r["n_sup"], r["n_con"], r["n_unment"],
                     r["n_new"], r["reward"]))

    print("\n== 按臂汇总 ==")
    print("%-12s %6s %6s %7s %7s %7s" % ("arm", "断言", "支持", "支持率", "未提及率", "增益点"))
    for a in ARMS:
        R = [r for r in recs if r["arm"] == a and not r["dead"]]
        cl = sum(r["n_claims"] for r in R); su = sum(r["n_sup"] for r in R)
        un = sum(r["n_unment"] for r in R); nw = sum(r["n_new"] for r in R)
        print("%-12s %6d %6d %6.1f%% %6.1f%% %7d  (n=%d)"
              % (a, cl, su, 100 * su / max(cl, 1), 100 * un / max(cl, 1), nw, len(R)))
    cl = sum(r["n_claims"] for r in recs if not r["dead"])
    su = sum(r["n_sup"] for r in recs if not r["dead"])
    un = sum(r["n_unment"] for r in recs if not r["dead"])
    nw = sum(r["n_new"] for r in recs if not r["dead"])
    print("%-12s %6d %6d %6.1f%% %6.1f%% %7d" % ("合计", cl, su, 100 * su / max(cl, 1),
                                            100 * un / max(cl, 1), nw))
    print("\n对照 v3（近邻继承 + 窄包）：可核验率 50.9% → %.1f%%，增益点 1 → %d"
          % (100 * su / max(cl, 1), nw))


if __name__ == "__main__":
    main()
