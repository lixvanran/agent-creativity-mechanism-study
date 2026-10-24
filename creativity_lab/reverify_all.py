# -*- coding: utf-8 -*-
"""全量重判：944 条断言用新核验器（带题目 + 非主张类）逐条判定。

目的：看**矛盾率**在三个臂之间是否有差异。
差分奖励（新增）已证明无方差；矛盾率是另一个可能的信号，
而且它直接对应「自信地说错」这个真实失败模式。

若矛盾率在臂间有差异 → 巡练有可用分数 → 工作流搜索有目标
若没有差异 → 这条信号也不行
"""
from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402

OUT = "runs/train2"
DATA = json.load(open("creativity_lab/data/legal_topics_v2.json", encoding="utf-8"))
LAWS, TOPICS = DATA["laws"], DATA["topics"]
ask_of = {t["tid"]: t["ask"] for t in TOPICS}
law_of = {t["tid"]: t["law"] for t in TOPICS}

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
BATCH = 8


def check_batch(args):
    llm, ask, ev, claims = args
    lst = "\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(claims))
    t = llm.chat(CHECK4.format(ask=ask, ev=ev, claims=lst), model="MiniMax-M3",
                 purpose="check4b", max_tokens=1600, budgets=(2400, 3200),
                 min_ok=len(claims) * 2) or ""
    out = []
    for ln in [x for x in t.splitlines() if x.strip()]:
        m = re.search(r"非主张|支持|矛盾|未提及", ln)
        out.append(m.group() if m else "解析失败")
    while len(out) < len(claims):
        out.append("解析失败")
    return claims, out[:len(claims)]


def main():
    claims_all = json.load(open("%s/claims.json" % OUT, encoding="utf-8"))
    print("== 全量重判（每条断言带所属题的语境）==", flush=True)

    # 按题分组（同一题的断言一起判，语境一致）
    by_tid = {}
    for k, cs in claims_all.items():
        if cs:
            by_tid.setdefault(k.split("|")[0], set()).update(cs)
    jobs = []
    for tid, pool in by_tid.items():
        ev = LAWS[law_of[tid]]["evidence"]
        pool = sorted(pool)
        for i in range(0, len(pool), BATCH):
            jobs.append((tid, pool[i:i + BATCH]))
    print("  批次数 %d（共 %d 条）" % (len(jobs), sum(len(p) for _, p in jobs)), flush=True)

    verd = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(check_batch, (LLM(), ask_of[tid], LAWS[law_of[tid]]["evidence"], b)): tid
                for tid, b in jobs}
        for n, f in enumerate(as_completed(futs), 1):
            try:
                cs, ps = f.result()
                for c, p in zip(cs, ps):
                    verd[c] = p
            except Exception as e:
                print("  ERR %s" % str(e)[:60], flush=True)
            if n % 20 == 0:
                print("  %d/%d" % (n, len(futs)), flush=True)
                json.dump(verd, open("%s/verdicts_v4_full.json" % OUT, "w"),
                          ensure_ascii=False, indent=1)
    json.dump(verd, open("%s/verdicts_v4_full.json" % OUT, "w"), ensure_ascii=False, indent=1)
    print("  完成，判定 %d 条" % len(verd), flush=True)

    # ---- 按臂统计 ----
    recs = [r for r in json.load(open("%s/records.json" % OUT, encoding="utf-8"))
            if not r["dead"]]
    print("\n%-14s %6s %6s %6s %6s %8s %8s" % ("arm", "断言", "支持", "矛盾", "非主张", "矛盾率", "支持率"))
    for arm in ("direct", "dual_fuse", "dual_select"):
        R = [r for r in recs if r["arm"] == arm]
        cl = su = co = nm = 0
        for r in R:
            for c in claims_all[r["key"]]:
                v = verd.get(c, "解析失败")
                cl += 1
                su += v == "支持"; co += v == "矛盾"; nm += v == "非主张"
        legal = max(cl - nm, 1)
        print("%-14s %6d %6d %6d %6d %7.1f%% %7.1f%%"
              % (arm, cl, su, co, nm, 100 * co / legal, 100 * su / legal))

    json.dump(verd, open("%s/verdicts_v4_full.json" % OUT, "w"), ensure_ascii=False, indent=1)
    print("\n已存 %s/verdicts_v4_full.json" % OUT)


if __name__ == "__main__":
    main()
