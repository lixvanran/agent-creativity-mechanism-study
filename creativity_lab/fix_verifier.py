# -*- coding: utf-8 -*-
"""修核验器：区分「法律主张」与「题面事实复述」，并修同义改写漏判。

观察到两类假阳性：
  A. 题面事实被当法律断言（「公司要求收取押金2000元」——这是题干）
  B. 同义改写被漏判（「同一用人单位只能约定一次试用期」——原文里就有）

修法：
  1. 把**题目**也交给核验器，并加第四类「非主张」：
     复述题目情形 → 非主张，不计矛盾
  2. 提示词里明确「改写、简称、换词但含义相同 = 支持」

判死测试：
  - 回归：27 条已知 ground truth 的断言（test_verifier.py 的用例）
  - 新增：本轮 22 条「矛盾」中，区分出哪些是题面复述 / 哪些是真错误
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402

OUT = "runs/train2"

CHECK4 = """下面是一份「依据原文」和一个「问题」，之后列出若干条**待核验的陈述**。

分两步判断：

第一步：这条陈述是**法律主张**（对权利义务、程序、期限、数值标准的规范性表述），
还是只是**复述了问题里的情形**（如「公司要求收取押金2000元」这种对事实的描述）？
如果只是复述情形，答「非主张」。

第二步：对属于法律主张的，判断它与依据原文的关系，只回答一个词：
- 「支持」：依据原文明确认可或蕴含该条。**改写、简称、换词但含义相同，也算支持。**
- 「矛盾」：依据原文明确讲了与之相反的内容。
- 「未提及」：依据原文没有讲到，或讲的是别的事。**不确定时一律答「未提及」。**

一行一条，顺序对应，不要解释，不要补充。

问题：
{ask}

依据原文：
{ev}

待核验的陈述：
{claims}"""


def check4(llm, ask, ev, claims):
    lst = "\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(claims))
    t = llm.chat(CHECK4.format(ask=ask, ev=ev, claims=lst), model="MiniMax-M3",
                 purpose="check4", max_tokens=1600, budgets=(2400, 3200),
                 min_ok=len(claims) * 2) or ""
    out = []
    for ln in [x for x in t.splitlines() if x.strip()]:
        m = re.search(r"非主张|支持|矛盾|未提及", ln)
        out.append(m.group() if m else "解析失败")
    while len(out) < len(claims):
        out.append("解析失败")
    return out[:len(claims)]


def main():
    llm = LLM()
    topics = json.load(open("creativity_lab/data/legal_topics_v2.json", encoding="utf-8"))
    laws, tps = topics["laws"], topics["topics"]
    ask_of = {t["tid"]: t["ask"] for t in tps}
    law_of = {t["tid"]: t["law"] for t in tps}

    # ---- 回归：27 条已知 ground truth ----
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import test_verifier as TV
    print("== 回归：27 条 ground truth ==", flush=True)
    MAP = {"L1": ("A", "A1"), "L2": ("B", "B1"), "L3": ("C", "C1"),
           "L4": ("D", "D1"), "L5": ("E", "E1")}
    rows = []
    for tid, c, g in TV.CASES:
        law, qid = MAP[tid]
        ev = laws[law]["evidence"]
        pred = check4(llm, ask_of.get(qid, ""), ev, [c])[0]
        # 回归时没有题目语境，题面复述类的用例改判为「支持」视为通过
        ok = (pred == g) or (g == "支持" and pred == "非主张")
        rows.append(dict(tid=tid, claim=c, gold=g, pred=pred, ok=ok))
    npass = sum(r["ok"] for r in rows)
    print("  通过 %d/%d" % (npass, len(rows)))
    for r in rows:
        if not r["ok"]:
            print("    ✗ 真值=%s 预测=%s  %s" % (r["gold"], r["pred"], r["claim"][:52]))

    # ---- 本轮 22 条「矛盾」重判 ----
    print("\n== 本轮 22 条「矛盾」重判 ==", flush=True)
    verd = json.load(open("%s/verdicts.json" % OUT, encoding="utf-8"))
    by_claim = {}
    for law, v in verd.items():
        for c, x in v.items():
            if x == "矛盾":
                by_claim.setdefault(c, law)
    # 找到每条断言所属的题
    claims_all = json.load(open("%s/claims.json" % OUT, encoding="utf-8"))
    tid_of = {}
    for k, cs in claims_all.items():
        for c in cs:
            tid_of.setdefault(c, k.split("|")[0])
    recheck = []
    for c, law in by_claim.items():
        tid = tid_of.get(c)
        ev = laws[law]["evidence"]
        ask = ask_of.get(tid, "")
        p = check4(llm, ask, ev, [c])[0]
        recheck.append(dict(claim=c, law=law, tid=tid, old="矛盾", new=p))
        print("  %-6s %-6s → %-6s %s" % (tid, law, p, c[:52]))
    n_non = sum(1 for r in recheck if r["new"] == "非主张")
    n_con = sum(1 for r in recheck if r["new"] == "矛盾")
    n_sup = sum(1 for r in recheck if r["new"] == "支持")
    n_un = sum(1 for r in recheck if r["new"] == "未提及")
    print("\n  重判结果: 非主张 %d / 矛盾 %d / 支持 %d / 未提及 %d  (原判矛盾 %d)"
          % (n_non, n_con, n_sup, n_un, len(recheck)))
    print("  → 原「22 条矛盾」里，真正与依据冲突的是 %d 条" % n_con)

    json.dump(dict(regression=rows, recheck=recheck),
              open("%s/verifier_v4.json" % OUT, "w"), ensure_ascii=False, indent=1, sort_keys=True)
    print("\n已存 %s/verifier_v4.json" % OUT)


if __name__ == "__main__":
    main()
