# -*- coding: utf-8 -*-
"""训练管线 v4：18 题 × 3 臂 × 2 重复。

相对 v3 的三处改动：
1. 题集扩到 18 题（6 部法 × 3 角度），依据包按法共享
2. 断言抽取修可靠性：三级降级（标准 → 宽松 → 逐条追问），空结果不再直接丢弃
3. 核验仍然**每条断言直接判定**，不做最近邻继承（v3 的核心修正，保留）

每阶段落盘，可断点续跑。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402
from creativity_lab.metrics import _mat    # noqa: E402

OUT = "runs/train2"
os.makedirs(OUT, exist_ok=True)
REPS = int(os.environ.get("REPS", "2"))
ARMS = ("direct", "dual_fuse", "dual_select")
DATA = json.load(open("creativity_lab/data/legal_topics_v2.json", encoding="utf-8"))
LAWS, TOPICS = DATA["laws"], DATA["topics"]

# ---------------------------------------------------------------- 断言抽取（三级降级）
ASSERT_MAIN = """把下面这段回答里的**可判真假的陈述**逐条列出来。

要求：
- 一条一个可独立核验的事实性陈述（数字、法规条文、权利义务、程序、时限、主体责任）。
- **不要**主观评价、不要「建议」「应该」这类无事实内容的句子。
- 每条 10-40 字，一行一条，最多 10 条。

文本：
{t}"""
ASSERT_LOOSE = """从下面这段文字里，逐行摘出其中**陈述事实的句子**（不是观点、不是建议）。
一行一条，最多 10 条。原文照抄，不要改写。

文字：
{t}"""
ASSERT_ONE = """从下面这段文字里，摘出**第一条**陈述事实的句子，原文照抄，不要改写。只输出这一句。

文字：
{t}"""


def _clean(t: str) -> list:
    out = []
    for ln in (t or "").splitlines():
        ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
        if 8 <= len(ln) <= 70 and ln not in out:
            out.append(ln)
    return out


def claims_of(text: str) -> list:
    """三级降级抽取。上次 3/30 返空就是这里。"""
    llm = LLM()
    for prompt, cap in ((ASSERT_MAIN, 10), (ASSERT_LOOSE, 10), (ASSERT_ONE, 1)):
        t = llm.chat(prompt.format(t=text[:1200]), model="MiniMax-M3", purpose="assert",
                     max_tokens=1800, budgets=(2400, 3200), min_ok=12) or ""
        c = _clean(t)
        if c:
            return c[:cap]
    return []


# ---------------------------------------------------------------- 生成
def gen(topic, arm, rep):
    llm = LLM()
    if arm == "direct":
        return llm.chat("问题：%s\n\n给出你的方案与理由，400字以内。" % topic["ask"],
                        model="MiniMax-M3", purpose="g2_direct", min_ok=200)
    from creativity_lab.arms.dual import Dual
    mode = "fuse" if arm == "dual_fuse" else "select"
    return Dual(mode).run(llm, topic, rep).text


# ---------------------------------------------------------------- 核验
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
    out = {}
    for i in range(0, len(claims), BATCH):
        b = claims[i:i + BATCH]
        lst = "\n".join("%d. %s" % (j + 1, c) for j, c in enumerate(b))
        t = llm.chat(CHECK3.format(ev=ev, claims=lst), model="MiniMax-M3",
                     purpose="v2", max_tokens=1400, budgets=(2000, 2800),
                     min_ok=len(b) * 2) or ""
        lines = [x for x in t.splitlines() if x.strip()]
        for c, ln in zip(b, lines):
            m = re.search(r"支持|矛盾|未提及", ln)
            out[c] = m.group() if m else "解析失败"
    return out


def embed_rows(ts):
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    return _mat(LLM().embed(uniq))[idx]


def cov(cands, pool, llm, thr=0.55):
    if not cands or not pool:
        return 0
    M = embed_rows(list(cands) + list(pool))
    S = M[:len(cands)] @ M[len(cands):].T
    return sum(1 for i in range(len(cands)) if float(S[i].max()) >= thr)


# ---------------------------------------------------------------- 主流程
def main():
    llm = LLM()
    t0 = time.time()

    print("== 1. 生成（%d 题 × %d 臂 × %d 重复 = %d 份）=="
          % (len(TOPICS), len(ARMS), REPS, len(TOPICS) * len(ARMS) * REPS), flush=True)
    fp = "%s/texts.json" % OUT
    if os.path.exists(fp):
        texts = json.load(open(fp, encoding="utf-8"))
        print("  复用已生成 %d 份" % len(texts), flush=True)
    else:
        texts = {}
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = {ex.submit(gen, T, a, i): (T["tid"], a, i)
                    for T in TOPICS for a in ARMS for i in range(1, REPS + 1)}
            for n, f in enumerate(as_completed(futs), 1):
                k = futs[f]
                try:
                    texts["%s|%s|%d" % k] = f.result()
                except Exception as e:
                    print("  ERR %s: %s" % (k, str(e)[:60]), flush=True)
                if n % 12 == 0:
                    print("  %d/%d  (%.0fs)" % (n, len(futs), time.time() - t0), flush=True)
                    json.dump(texts, open(fp, "w"), ensure_ascii=False, indent=1)
        json.dump(texts, open(fp, "w"), ensure_ascii=False, indent=1)
    for a in ARMS:
        L = [len(v) for k, v in texts.items() if k.split("|")[1] == a]
        print("  %-11s %d 份，平均 %dB" % (a, len(L), sum(L) / max(len(L), 1)), flush=True)

    print("\n== 2. 断言抽取（三级降级）==", flush=True)
    fp = "%s/claims.json" % OUT
    if os.path.exists(fp):
        allclaims = json.load(open(fp, encoding="utf-8"))
        print("  复用 %d 份" % len(allclaims), flush=True)
    else:
        allclaims = {}
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = {ex.submit(claims_of, v): k for k, v in texts.items()}
            for n, f in enumerate(as_completed(futs), 1):
                allclaims[futs[f]] = f.result()
                if n % 24 == 0:
                    print("  %d/%d" % (n, len(futs)), flush=True)
                    json.dump(allclaims, open(fp, "w"), ensure_ascii=False, indent=1)
        json.dump(allclaims, open(fp, "w"), ensure_ascii=False, indent=1)
    empty = [k for k, v in allclaims.items() if not v]
    tot = sum(len(v) for v in allclaims.values())
    print("  断言总数 %d，空抽取 %d 份 (%.1f%%)" % (tot, len(empty), 100 * len(empty) / max(len(allclaims), 1)), flush=True)
    if empty:
        print("  空抽取: %s" % ", ".join(empty[:8]), flush=True)

    print("\n== 3. 逐条直接核验（无传播、无种子池）==", flush=True)
    fp = "%s/verdicts.json" % OUT
    if os.path.exists(fp):
        verd = json.load(open(fp, encoding="utf-8"))
        print("  复用", flush=True)
    else:
        verd = {}
        for law, L in LAWS.items():
            pool = sorted({c for k, cs in allclaims.items()
                           if next(t for t in TOPICS if t["tid"] == k.split("|")[0])["law"] == law
                           for c in cs})
            if not pool:
                continue
            v = verify(llm, L["evidence"], pool)
            verd[law] = v
            n = {x: sum(1 for y in v.values() if y == x) for x in ("支持", "矛盾", "未提及", "解析失败")}
            print("  法%s 断言 %2d → 支持 %2d / 矛盾 %2d / 未提及 %2d / 失败 %d"
                  % (law, len(pool), n["支持"], n["矛盾"], n["未提及"], n["解析失败"]), flush=True)
            json.dump(verd, open(fp, "w"), ensure_ascii=False, indent=1)
    json.dump(verd, open(fp, "w"), ensure_ascii=False, indent=1)

    print("\n== 4. 奖励与差集 ==", flush=True)
    recs = []
    law_of = {t["tid"]: t["law"] for t in TOPICS}
    for k, txt in texts.items():
        tid, arm, rep = k.split("|")
        law = law_of[tid]
        cs = allclaims[k]
        V = verd.get(law, {})
        # 基线必须是**同一题**的直接答案。v4 初版按 law 过滤，把 3 道题的直接答案
        # 全算进基线，基线撑大 3 倍 → 增益点被静默压到接近 0。
        dpool = [c for kk, cc in allclaims.items()
                 if kk.split("|")[0] == tid and kk.split("|")[1] == "direct" for c in cc]
        if not cs:
            recs.append(dict(key=k, tid=tid, law=law, arm=arm, n_claims=0, n_sup=0,
                             n_con=0, n_unment=0, n_new=0, reward=0.0, dead=True))
            continue
        sup = [c for c in cs if V.get(c) == "支持"]
        con = [c for c in cs if V.get(c) == "矛盾"]
        un = [c for c in cs if V.get(c) == "未提及"]
        new = [c for c in sup if cov([c], dpool, llm) == 0]
        recs.append(dict(key=k, tid=tid, law=law, arm=arm, length=len(txt), n_claims=len(cs),
                         n_sup=len(sup), n_con=len(con), n_unment=len(un), n_new=len(new),
                         reward=round(len(new) / max(len(txt), 1) * 100, 4), dead=False))
    json.dump(recs, open("%s/records.json" % OUT, "w"), ensure_ascii=False, indent=1)

    print("\n%-24s %5s %5s %5s %5s %5s" % ("key", "clm", "sup", "con", "unm", "new"))
    for r in sorted(recs, key=lambda x: -x["reward"])[:15]:
        if r["dead"]:
            print("%-24s   —— 抽取失败" % r["key"])
        else:
            print("%-24s %5d %5d %5d %5d %5d" % (r["key"], r["n_claims"], r["n_sup"],
                                                  r["n_con"], r["n_unment"], r["n_new"]))

    print("\n== 按臂汇总 ==")
    print("%-12s %6s %6s %8s %8s %7s" % ("arm", "断言", "支持", "支持率", "未提及率", "增益点"))
    for a in ARMS:
        R = [r for r in recs if r["arm"] == a and not r["dead"]]
        cl = sum(r["n_claims"] for r in R); su = sum(r["n_sup"] for r in R)
        un = sum(r["n_unment"] for r in R); nw = sum(r["n_new"] for r in R)
        print("%-12s %6d %6d %7.1f%% %7.1f%% %7d  (n=%d)"
              % (a, cl, su, 100 * su / max(cl, 1), 100 * un / max(cl, 1), nw, len(R)))

    # ---------------- 校准门 ----------------
    G = [r for r in recs if not r["dead"]]
    cl = sum(r["n_claims"] for r in G); su = sum(r["n_sup"] for r in G)
    un = sum(r["n_unment"] for r in G); nw = sum(r["n_new"] for r in G)
    con = sum(r["n_con"] for r in G)
    nfail = sum(1 for r in recs if r["dead"])
    print("\n== 校准门 ==")
    gates = [
        ("G3 依据包覆盖 <30%未提及", 100 * un / max(cl, 1) < 30, "未提及 %.1f%%" % (100 * un / max(cl, 1))),
        ("G4 抽取失败 <5%%", 100 * nfail / max(len(recs), 1) < 5, "失败 %d/%d" % (nfail, len(recs))),
        ("G5 增益点 >=20", nw >= 20, "增益点 %d" % nw),
        ("G6 题数>=20 重复>=3", len(TOPICS) >= 20 and REPS >= 3, "%d 题 × %d 重复" % (len(TOPICS), REPS)),
    ]
    npass = 0
    for name, ok, det in gates:
        print("  %-24s %-6s %s" % (name, "通过" if ok else "否决", det))
        npass += ok
    print("\n  支持断言 %d/%d = %.1f%%  |  矛盾 %d  |  增益点 %d"
          % (su, cl, 100 * su / max(cl, 1), con, nw))
    print("  %d/%d 门通过" % (npass, len(gates)))
    print("\n" + ("✅ 门通过 → 可进入 S2 训练" if npass == len(gates)
                    else "❌ 门未全过 → 不训练，报告卡在哪"))
    print("总耗时 %.0f 分钟" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
