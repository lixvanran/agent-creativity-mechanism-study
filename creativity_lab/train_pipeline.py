# -*- coding: utf-8 -*-
"""S1：生成 → 断言抽取 → 依据核验 → 每候选奖励。

核验复用已验证的 `check_claims`，喂给它的是**权威依据原文**而非接收端输出。
每题的断言集合只核验一次，所有候选共享 → 成本与候选数无关。
"""
from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM                      # noqa: E402
from creativity_lab.metrics import _mat                    # noqa: E402
from creativity_lab.receiver import check_claims           # noqa: E402

OUT = "runs/train"
os.makedirs(OUT, exist_ok=True)
REPS = int(os.environ.get("REPS", "2"))
ARMS = ("direct", "dual_fuse", "dual_select")
TOPICS = json.load(open("creativity_lab/data/legal_topics.json", encoding="utf-8"))["topics"]

ASSERT = """把下面这段回答里的**可判真假的陈述**逐条列出来。

要求：
- 一条一个可独立核验的事实性陈述（数字、法规条文、权利义务、程序、时限、主体责任）。
- **不要**主观评价、不要「建议」「应该」这类无事实内容的句子。
- 每条 10-40 字，一行一条，最多 10 条。

文本：
{t}"""


# ---------------------------------------------------------------- 生成
def gen(topic, arm, rep):
    from creativity_lab.arms.direct import Direct
    from creativity_lab.arms.dual import Dual
    llm = LLM()
    if arm == "direct":
        return llm.chat("问题：%s\n\n给出你的方案与理由，400字以内。" % topic["ask"],
                        model="MiniMax-M3", purpose="g_direct", min_ok=200)
    mode = "fuse" if arm == "dual_fuse" else "select"
    return Dual(mode).run(llm, topic, rep).text


# ---------------------------------------------------------------- 断言
def claims_of(llm, text):
    t = llm.chat(ASSERT.format(t=text[:1200]), model="MiniMax-M3", purpose="assert",
                 max_tokens=1600, budgets=(2200, 3000), min_ok=20) or ""
    out = []
    for ln in t.splitlines():
        ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
        if 8 <= len(ln) <= 60 and ln not in out:
            out.append(ln)
    return out


# ---------------------------------------------------------------- 语义
def covered(cands, pool, thr=0.55, llm=None):
    """cands 中被 pool 语义覆盖的条数。"""
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


# ---------------------------------------------------------------- 主流程
def main():
    llm = LLM()
    print("== 1. 生成 ==", flush=True)
    texts = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(gen, T, a, i): (T["tid"], a, i)
                for T in TOPICS for a in ARMS for i in range(1, REPS + 1)}
        for f in as_completed(futs):
            k = futs[f]
            try:
                texts["%s|%s|%d" % k] = f.result()
            except Exception as e:
                print("  ERR %s: %s" % (k, str(e)[:70]), flush=True)
    json.dump(texts, open("%s/texts.json" % OUT, "w"), ensure_ascii=False, indent=1)
    for a in ARMS:
        L = [len(v) for k, v in texts.items() if k.split("|")[1] == a]
        print("  %-11s %d 份，平均 %dB" % (a, len(L), sum(L) / max(len(L), 1)), flush=True)

    print("\n== 2. 断言抽取 ==", flush=True)
    allclaims = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(claims_of, LLM(), v): k for k, v in texts.items()}
        for f in as_completed(futs):
            allclaims[futs[f]] = f.result()
    json.dump(allclaims, open("%s/claims.json" % OUT, "w"), ensure_ascii=False, indent=1)
    for a in ARMS:
        n = [len(allclaims[k]) for k in allclaims if k.split("|")[1] == a]
        print("  %-11s 每次断言 %s 条" % (a, n), flush=True)

    print("\n== 3. 依据核验（每题一次，全候选共享）==", flush=True)
    verdicts = {}
    for T in TOPICS:
        pool = dedup([c for k, cs in allclaims.items()
                      if k.split("|")[0] == T["tid"] for c in cs], llm)
        ok = {}
        for i in range(0, len(pool), 8):          # 分批，避开输出上限
            batch = pool[i:i + 8]
            _, v = check_claims(llm, batch, T["evidence"], model="MiniMax-M3")
            ok.update(dict(zip(batch, v)))
        verdicts[T["tid"]] = dict(pool=pool, ok=ok)
        s = sum(ok.values())
        print("  %s 断言 %d 条，依据支持 %d 条 (%.0f%%)"
              % (T["tid"], len(pool), s, 100 * s / max(len(pool), 1)), flush=True)
        for c, v in ok.items():
            print("     %s %s" % ("支持" if v else "不支持", c[:44]), flush=True)
    json.dump(verdicts, open("%s/verdicts.json" % OUT, "w"), ensure_ascii=False, indent=1)

    print("\n== 4. 每候选奖励 ==", flush=True)
    recs = []
    for k, txt in texts.items():
        tid, arm, rep = k.split("|")
        T = next(x for x in TOPICS if x["tid"] == tid)
        V = verdicts[tid]
        cs = allclaims[k]
        # 相对**直调基线**的新增：工作流相对直调，直调自身为 0
        dpool = [c for kk, cc in allclaims.items()
                 if kk.split("|")[0] == tid and kk.split("|")[1] == "direct" for c in cc]
        new = [c for c in cs if V["ok"].get(c) == 1 and covered([c], dpool, 0.55, llm) == 0]
        lost = [c for c in dpool if V["ok"].get(c) == 1 and covered([c], cs, 0.55, llm) == 0]
        sup = [c for c in cs if V["ok"].get(c) == 1]
        recs.append(dict(
            key=k, tid=tid, arm=arm, rep=rep, length=len(txt),
            n_claims=len(cs), n_supported=len(sup), n_new=len(new), n_lost=len(lost),
            verifiable=round(len(sup) / max(len(cs), 1), 3),
            reward=round(len(new) / max(len(txt), 1) * 100, 4),
            lost_penalty=round(len(lost) / max(len(txt), 1) * 100, 4),
        ))
    json.dump(recs, open("%s/records.json" % OUT, "w"), ensure_ascii=False, indent=1)

    print("%-22s %6s %5s %5s %5s %7s" % ("key", "len", "clm", "sup", "new", "reward"))
    for r in sorted(recs, key=lambda x: -x["reward"]):
        print("%-22s %6d %5d %5d %5d %7.4f"
              % (r["key"], r["length"], r["n_claims"], r["n_supported"], r["n_new"], r["reward"]))

    print("\n== 按臂汇总 ==", flush=True)
    for a in ARMS:
        R = [r for r in recs if r["arm"] == a]
        if R:
            print("  %-11s reward 均值 %.4f  可核验率均值 %.2f  n_new 总和 %d"
                  % (a, sum(x["reward"] for x in R) / len(R),
                     sum(x["verifiable"] for x in R) / len(R), sum(x["n_new"] for x in R)))
    print("DONE")


if __name__ == "__main__":
    main()
