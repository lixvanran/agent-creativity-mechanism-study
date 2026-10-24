# -*- coding: utf-8 -*-
"""S1b：三分类核验 + 每候选奖励（复用已缓存的生成/抽取结果）。

修正：首版把设计里的三分类压成二分类，导致「依据包沉默」被当成「错误」，
反过来惩罚模型知道包外真知识（12315 是热线、劳动合同法第九条禁扣证件——都是真的）。
**只有矛盾该扣分，沉默必须中性。**
"""
from __future__ import annotations

import json
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM        # noqa: E402
from creativity_lab.metrics import _mat      # noqa: E402

OUT = "runs/train"
REPS = 2
ARMS = ("direct", "dual_fuse", "dual_select")
TOPICS = json.load(open("creativity_lab/data/legal_topics.json", encoding="utf-8"))["topics"]
texts = json.load(open("%s/texts.json" % OUT, encoding="utf-8"))
allclaims = json.load(open("%s/claims.json" % OUT, encoding="utf-8"))

# 三分类：只区分「矛盾」与「沉默」。沉默是中性，不是负面。
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


def check3(llm, ev, claims, model="MiniMax-M3"):
    if not claims:
        return {}
    lst = "\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(claims))
    t = llm.chat(CHECK3.format(ev=ev[:2400], claims=lst), model=model, purpose="check3",
                 max_tokens=1200, budgets=(1800, 2400), min_ok=len(claims) * 2) or ""
    out = {}
    for ln, c in zip([x for x in t.splitlines() if x.strip()], claims):
        m = re.search(r"支持|矛盾|未提及", ln)
        if m:
            out[c] = m.group()
    return out


def covered(cands, pool, thr=0.55, llm=None):
    if not cands or not pool:
        return 0
    M = _mat(llm.embed(list(cands) + list(pool)))
    S = M[:len(cands)] @ M[len(cands):].T
    return sum(1 for i in range(len(cands)) if float(S[i].max()) >= thr)


def dedup(lst, llm, thr=0.75):
    out = []
    for c in lst:
        if not out or covered([c], out, thr, llm) == 0:
            out.append(c)
    return out


def main():
    llm = LLM()
    print("== 3b. 三分类核验 ==", flush=True)
    verdicts = {}
    for T in TOPICS:
        tid = T["tid"]
        pool = dedup([c for k, cs in allclaims.items()
                      if k.split("|")[0] == tid for c in cs], llm)
        ok = {}
        for i in range(0, len(pool), 8):
            ok.update(check3(llm, T["evidence"], pool[i:i + 8]))
        sup = [c for c in pool if ok.get(c) == "支持"]
        con = [c for c in pool if ok.get(c) == "矛盾"]
        un = [c for c in pool if ok.get(c) == "未提及"]
        verdicts[tid] = dict(pool=pool, ok=ok)
        print("\n  %s 断言 %d → 支持 %d / 矛盾 %d / 未提及 %d"
              % (tid, len(pool), len(sup), len(con), len(un)), flush=True)
        for c in sup:
            print("     ✅支持  %s" % c[:46], flush=True)
        for c in con:
            print("     ❌矛盾  %s" % c[:46], flush=True)
    json.dump(verdicts, open("%s/verdicts3.json" % OUT, "w"), ensure_ascii=False, indent=1)

    print("\n== 4b. 每候选奖励 ==", flush=True)
    recs = []
    for k, txt in texts.items():
        tid, arm, rep = k.split("|")
        V = verdicts[tid]
        cs = allclaims[k]
        dpool = [c for kk, cc in allclaims.items()
                 if kk.split("|")[0] == tid and kk.split("|")[1] == "direct" for c in cc]
        new = [c for c in cs if V["ok"].get(c) == "支持" and covered([c], dpool, 0.55, llm) == 0]
        lost = [c for c in dpool if V["ok"].get(c) == "支持" and covered([c], cs, 0.55, llm) == 0]
        wrong = [c for c in cs if V["ok"].get(c) == "矛盾"]
        sup = [c for c in cs if V["ok"].get(c) == "支持"]
        recs.append(dict(
            key=k, tid=tid, arm=arm, rep=int(rep), length=len(txt),
            n_claims=len(cs), n_sup=len(sup), n_new=len(new), n_lost=len(lost),
            n_wrong=len(wrong),
            reward=round(len(new) / max(len(txt), 1) * 100, 4),
            net=round((len(new) - len(lost) - len(wrong)) / max(len(txt), 1) * 100, 4),
        ))
    json.dump(recs, open("%s/records3.json" % OUT, "w"), ensure_ascii=False, indent=1)

    print("\n%-22s %5s %5s %5s %5s %5s %8s" % ("key", "len", "clm", "sup", "new", "wrong", "net"))
    for r in sorted(recs, key=lambda x: -x["net"]):
        print("%-22s %5d %5d %5d %5d %5d %8.4f"
              % (r["key"], r["length"], r["n_claims"], r["n_sup"], r["n_new"], r["n_wrong"], r["net"]))

    print("\n== 按臂汇总 ==")
    for a in ARMS:
        R = [r for r in recs if r["arm"] == a]
        if R:
            print("  %-11s net均值 %+.4f  sup总和 %d  new总和 %d  wrong总和 %d  n=%d"
                  % (a, sum(x["net"] for x in R) / len(R), sum(x["n_sup"] for x in R),
                     sum(x["n_new"] for x in R), sum(x["n_wrong"] for x in R), len(R)))
    print("DONE")


if __name__ == "__main__":
    main()
