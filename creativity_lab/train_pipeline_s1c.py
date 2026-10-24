# -*- coding: utf-8 -*-
"""S1c：修 claim→verdict 映射后重算奖励。不消耗新的模型调用。

Bug：verdicts 字典按**去重后的池**建键，候选自身的断言若被去重判为近重复，
就查不到判定 → 既不计支持也不计错误 → 静默消失。
修法：每条候选断言映射到**最近的池内断言**，继承其判定。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402
from creativity_lab.metrics import _mat    # noqa: E402

OUT = "runs/train"
ARMS = ("direct", "dual_fuse", "dual_select")
TOPICS = json.load(open("creativity_lab/data/legal_topics.json", encoding="utf-8"))["topics"]
texts = json.load(open("%s/texts.json" % OUT, encoding="utf-8"))
allclaims = json.load(open("%s/claims.json" % OUT, encoding="utf-8"))
verdicts = json.load(open("%s/verdicts3.json" % OUT, encoding="utf-8"))

NEAR = 0.55


def embed_rows(texts):
    """注意：embedding 接口对**完全相同**的输入会去重，返回行数少于输入。
    不自己建索引映射会导致行错位，静默污染任何对齐计算。"""
    uniq, idx = [], []
    seen = {}
    for t in texts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    V = _mat(LLM().embed(uniq))
    return V[idx]


def nn_verdict(tid, claims):
    """每条断言 → 池内最近邻的判定。"""
    pool = verdicts[tid]["pool"]
    ok = verdicts[tid]["ok"]
    if not claims:
        return {}
    if not pool:
        return {c: "未提及" for c in claims}
    M = embed_rows(list(claims) + list(pool))
    S = M[:len(claims)] @ M[len(claims):].T
    out = {}
    for i, c in enumerate(claims):
        j = int(S[i].argmax())
        out[c] = ok.get(pool[j], "未提及") if float(S[i].max()) >= NEAR else "未提及"
    return out


def cov(cands, pool, llm, thr=NEAR):
    if not cands or not pool:
        return 0
    M = embed_rows(list(cands) + list(pool))
    S = M[:len(cands)] @ M[len(cands):].T
    return sum(1 for i in range(len(cands)) if float(S[i].max()) >= thr)


llm = LLM()
recs = []
for k, txt in texts.items():
    tid, arm, rep = k.split("|")
    cs = allclaims[k]
    V = nn_verdict(tid, cs)
    dpool = [c for kk, cc in allclaims.items()
             if kk.split("|")[0] == tid and kk.split("|")[1] == "direct" for c in cc]
    new = [c for c in cs if V[c] == "支持" and cov([c], dpool, llm) == 0]
    # 断言抽取失败的候选（n_claims=0）不能记为「丢了全部」——那是抽取环节坏了，不是答案丢了内容
    lost = [c for c in dpool if cov([c], cs, llm) == 0] if cs else None
    wrong = [c for c in cs if V[c] == "矛盾"]
    sup = [c for c in cs if V[c] == "支持"]
    recs.append(dict(
        key=k, tid=tid, arm=arm, rep=int(rep), length=len(txt),
        n_claims=len(cs), n_sup=len(sup), n_new=len(new),
        n_lost=len(lost) if lost is not None else -1,   # -1 = 抽取失败，不参与比较
        n_wrong=len(wrong),
        reward=round(len(new) / max(len(txt), 1) * 100, 4),
        net=(round((len(new) - len(lost)) / max(len(txt), 1) * 100, 4)
             if lost is not None else None),
    ))
json.dump(recs, open("%s/records3c.json" % OUT, "w"), ensure_ascii=False, indent=1)

print("%-22s %5s %5s %5s %5s %5s %8s" % ("key", "len", "clm", "sup", "new", "lost", "net"))
for r in sorted(recs, key=lambda x: -(x["net"] if x["net"] is not None else -9e9)):
    print("%-22s %5d %5d %5d %5d %5d %8s"
          % (r["key"], r["length"], r["n_claims"], r["n_sup"], r["n_new"], r["n_lost"],
             "抽取失败" if r["net"] is None else "%.4f" % r["net"]))

print("\n== 按臂汇总（每臂 10 份）==")
for a in ARMS:
    R = [r for r in recs if r["arm"] == a]
    G = [r for r in R if r["net"] is not None]
    print("  %-11s net均值 %+.4f (n=%d, 剔抽取失败 %d)  sup总和 %2d  new总和 %d"
          % (a, sum(x["net"] for x in G) / max(len(G), 1), len(G), len(R) - len(G),
             sum(x["n_sup"] for x in R), sum(x["n_new"] for x in R)))

# 校准门：有没有足够信号可训练
sup_tot = sum(r["n_sup"] for r in recs)
new_tot = sum(r["n_new"] for r in recs)
G = [r for r in recs if r["net"] is not None]
print("\n== 校准门 ==")
print("  支持断言总数 %d / 断言总数 %d = 可核验率 %.1f%%"
      % (sup_tot, sum(r["n_claims"] for r in recs),
         100 * sup_tot / max(sum(r["n_claims"] for r in recs), 1)))
print("  门1 增益点支持率 <20% → 判死 : %s" % ("是，判死" if new_tot == 0 else "不适用(无增益点)"))
print("  门2 存在可用于训练的方差     : %s"
      % ("否，可训练候选仅 %d/%d，不可训练" % (len(G), len(recs)) if len(G) < len(recs) or new_tot == 0 else "待查"))
print("  门3 自信说错(矛盾)样本数    : %d" % sum(r["n_wrong"] for r in recs))
