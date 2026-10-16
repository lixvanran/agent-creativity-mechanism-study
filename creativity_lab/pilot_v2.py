# -*- coding: utf-8 -*-
"""最小端到端：直调 ×3 vs 工作流 ×3 → 切断言 → 差集 → 核验。

**只用 1 道题 1 轮。目的是验证链路跑不跑得通，不追求显著结果。**
用户四道题不进本脚本。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM          # noqa: E402
from creativity_lab.metrics import _mat          # noqa: E402
from creativity_lab import prompts as P       # noqa: E402

REPS = 3
OUT = "runs/v2_pilot"
os.makedirs(OUT, exist_ok=True)

# 题目选有外部核验渠道的域（交通法规）。不是用户原题。
TOPIC = {
    "tid": "V1",
    "ask": "预算两万、每天通勤三十公里，电动车选电摩还是电自？",
}

ASSERT = """把下面这段回答里的**可判真假的陈述**逐条列出来。

要求：
- 一条一个可独立核验的事实性陈述（数字、法规、门槛、因果、做法效果）。
- **不要**主观评价、不要「建议」「应该」这类无事实内容的句子。
- 每条 10-40 字，一行一条，最多 10 条。

文本：
{t}"""


def claims(llm, text, model="MiniMax-M3"):
    t = llm.chat(ASSERT.format(t=text[:1200]), model=model, purpose="assert",
                 max_tokens=1600, budgets=(2200, 3000), min_ok=20) or ""
    out = []
    for ln in t.splitlines():
        ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
        if 8 <= len(ln) <= 60 and ln not in out:
            out.append(ln)
    return out


def sim_sets(a, b, thr=0.55):
    """语义去重：a 中与 b 任一条相似度 ≥thr 的判为已存在。"""
    if not a or not b:
        return set(range(len(a)))
    pairs = [(x, y) for x in a for y in b]
    M = llm.embed([x for p in pairs for x in p])
    A = M[0::2]
    B = M[1::2]
    cover = set()
    for i, (x, _) in enumerate(pairs):
        if float(A[i] @ B[i]) >= thr and i // len(b) not in cover:
            cover.add(i // len(b))
    return cover


def gen(arm, i):
    llm = LLM()
    if arm == "direct":
        return llm.chat("问题：%s\n\n给出你的方案与理由，400字以内。" % TOPIC["ask"],
                        model="MiniMax-M3", purpose="v2_direct", min_ok=200)
    from creativity_lab.arms.dual import Dual
    return Dual("select").run(llm, TOPIC, i).text


llm = LLM()
print("== 1. 生成 ==", flush=True)
texts = {a: [gen(a, i) for i in range(1, REPS + 1)] for a in ("direct", "work")}
for a in texts:
    print("  %-7s 平均 %dB × %d" % (a, sum(len(t) for t in texts[a]) / REPS, REPS), flush=True)
json.dump(texts, open("%s/texts.json" % OUT, "w"), ensure_ascii=False, indent=1)

print("== 2. 切断言 ==", flush=True)
allc = {a: [claims(llm, t) for t in texts[a]] for a in texts}
json.dump(allc, open("%s/claims.json" % OUT, "w"), ensure_ascii=False, indent=1)
for a in allc:
    print("  %-7s 每次 %s 条" % (a, [len(c) for c in allc[a]]), flush=True)

print("== 3. 差集（W 有 / D 无）==", flush=True)
dpool = [c for cs in allc["direct"] for c in cs]
seen_w = set()
gain, lost = [], []
for c in allc["work"]:
    key = tuple(c)
    if key in seen_w:
        continue
    seen_w.add(key)
    if not sim_sets(c, dpool):
        gain += c
dseen = set()
for c in allc["direct"]:
    key = tuple(c)
    if key in dseen:
        continue
    dseen.add(key)
    if not sim_sets(c, [x for cs in allc["work"] for x in cs]):
        lost += c
print("  增益点 %d 条 / 损失点 %d 条" % (len(gain), len(lost)), flush=True)
for i, c in enumerate(gain[:10]):
    print("   + %s" % c)
for i, c in enumerate(lost[:6]):
    print("   - %s" % c)

json.dump(dict(topic=TOPIC, texts=texts, claims=allc, gain=gain, lost=lost),
          open("%s/pilot.json" % OUT, "w"), ensure_ascii=False, indent=1)
print("\n下一步：对上面 %d 条增益点做外部核验（脚本外进行，结论回填）" % len(gain))
