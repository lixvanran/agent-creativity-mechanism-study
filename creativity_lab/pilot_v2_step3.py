# -*- coding: utf-8 -*-
"""第 3 步：语义去重 → 有向差集。读取 pilot_v2 的缓存，不重新生成。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402
from creativity_lab.metrics import _mat    # noqa: E402

OUT = "runs/v2_pilot"
allc = json.load(open("%s/claims.json" % OUT, encoding="utf-8"))
llm = LLM()


def present(cands, pool, thr=0.55):
    """cands 中已被 pool 覆盖的条数（语义去重，非字面）。"""
    if not cands or not pool:
        return 0
    M = _mat(llm.embed(list(cands) + list(pool)))
    A, B = M[:len(cands)], M[len(cands):]
    S = A @ B.T                       # 余弦
    return sum(1 for i in range(len(cands)) if float(S[i].max()) >= thr)


def dedup(lst, thr=0.75):
    """组内去重：语义近乎相同的只留一条。"""
    out = []
    for c in lst:
        if not out or present([c], out, thr) == 0:
            out.append(c)
    return out


print("== 3a. 组内去重 ==", flush=True)
pool = {a: dedup([x for cs in allc[a] for x in cs]) for a in allc}
for a in pool:
    print("  %-7s 断言 %d 条 -> 去重后 %d 条" % (a, sum(len(c) for c in allc[a]), len(pool[a])))

print("\n== 3b. 有向差集 ==", flush=True)
gain = [c for c in pool["work"] if present([c], pool["direct"]) == 0]
lost = [c for c in pool["direct"] if present([c], pool["work"]) == 0]
print("  增益点（工作流有、直调无）%d 条" % len(gain), flush=True)
print("  损失点（直调有、工作流无）%d 条" % len(lost), flush=True)
for c in gain:
    print("   + %s" % c)
for c in lost:
    print("   - %s" % c)

json.dump(dict(pool=pool, gain=gain, lost=lost),
          open("%s/diff.json" % OUT, "w"), ensure_ascii=False, indent=1)
print("\n下一步：核验上述 %d 条增益点 / %d 条损失点" % (len(gain), len(lost)))
