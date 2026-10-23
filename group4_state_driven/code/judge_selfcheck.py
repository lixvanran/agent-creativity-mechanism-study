#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判官自检（第四组铁律：检查器必须先证明自己能抓到东西）。

设计（照搬既有的测量纪律）：
  · **跨厂商判官**：grok-4.20（主判官） vs grok-4.3（第二判官）——互相独立
  · **盲化**：剥掉臂标签、随机编号；判官拿不到任何来源信息
  · **长度配对**：同一题的样本尽量覆盖不同长度，避免"长文显得更有取舍"的混淆
  · **判据自检指标**：分数方差、判官间 Spearman、每篇的判官分歧
  · ⚠️ **没有客观标签**（措辞级判据已被证伪：keep-Jaccard 地板 = 0.000）
    ⇒ 有效性证据来自「方差」+「跨主体一致性」+「人工盲评定性复核」

用法： python3 judge_selfcheck.py --out runs/judge_selfcheck.json
"""
import argparse
import json
import os
import random
import re
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

JUDGE_PROMPT = """你是一位严格的写作评估者。下面给你一篇中文文章。

请判断作者是否做出了**明确的取舍**——也就是：他明确表示了"这一轮我写透/坚持的是某一点，
某一点我选择不展开/放弃"，而不是面面俱到地讲。

评分标准（0-4 分）：
4 = 明确取舍，并说清了什么被保留、什么被放弃，理由具体
3 = 有明确取舍，但只说清了保留什么（或只笼统说别的先不谈）
2 = 有取舍倾向但被大量全面铺陈稀释，读者需要自己拼出取舍
1 = 几乎没有取舍，通篇平行铺陈
0 = 完全没有取舍，标准八面玲珑的通用写作

只输出 JSON：{"score": 0到4的整数, "has_tradeoff": true/false, "evidence": "不超过40字的依据"}

文章：
<<<
{article}
>>>"""


def call_judge(model, prompt, timeout=120):
    key = os.environ.get("OPENROUTER_API_KEY", "")
    body = {"model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400, "temperature": 0,
            "response_format": {"type": "json_object"}}
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=timeout)
    d = json.loads(r.read().decode())
    txt = (d["choices"][0]["message"].get("content") or "").strip()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("判官未返回 JSON: %r" % txt[:120])
    return json.loads(m.group(0))


def spearman(x, y):
    n = len(x)
    if n < 3:
        return None
    def rank(v):
        order = sorted(range(n), key=lambda i: v[i])
        rk = [0. * n] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk
    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return round(num / (dx * dy), 4) if dx and dy else None


def var(v):
    n = len(v)
    if n < 2:
        return 0.0
    m = sum(v) / n
    return round(sum((x - m) ** 2 for x in v) / n, 4)


def collect_samples(limit_per_source=4):
    """从现有产出里抽样本，**剥掉臂标签**。"""
    samples = []
    def add(src, arm, text, topic):
        t = (text or "").strip()
        if len(t) < 200:
            return
        samples.append({"src": src, "arm": arm, "topic": topic, "text": t})

    for fn, src in (("runs/arch3_compare.jsonl", "G01-v3"),
                    ("runs/arch2_compare.jsonl", "G01-v2"),
                    ("runs/min_compare.jsonl", "G01-min")):
        p = os.path.join(HERE, fn)
        if not os.path.exists(p):
            continue
        rows = []
        for line in open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("error") or r.get("gate_failed"):
                continue
            if (r.get("lang_cn_ratio") is not None and r["lang_cn_ratio"] < 0.9):
                continue
            rows.append(r)
        # 每臂最多取 2 条 + 覆盖不同长度
        seen = {}
        for r in sorted(rows, key=lambda z: len(z.get("text") or "")):
            arm = r.get("arm", "?")
            seen.setdefault(arm, 0)
            if seen[arm] >= 2:
                continue
            seen[arm] += 1
            add(src, arm, r.get("text"), "G01")
    for fn, src in (("runs/p2_orig.jsonl", "T01-p2"),):
        p = os.path.join(HERE, fn)
        if not os.path.exists(p):
            continue
        rows = []
        for line in open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("error"):
                continue
            rows.append(r)
        seen = {}
        for r in sorted(rows, key=lambda z: len(z.get("text") or "")):
            arm = r.get("arm", "?")
            seen.setdefault(arm, 0)
            if seen[arm] >= 2:
                continue
            seen[arm] += 1
            add(src, arm, r.get("text"), r.get("topic") or "T01")
    return samples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "judge_selfcheck.json"))
    ap.add_argument("--judge-a", default="x-ai/grok-4.20")
    ap.add_argument("--judge-b", default="x-ai/grok-4.3")
    ap.add_argument("--max-samples", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20261022)
    args = ap.parse_args()

    samples = collect_samples()
    random.Random(args.seed).shuffle(samples)
    # 长度分层：长的、中的、短的交替取 ⇒ 避免判官只吃长度
    samples.sort(key=lambda s: len(s["text"]))
    half = len(samples) // 2
    mixed = []
    lo, hi = 0, half
    while lo < half or hi < len(samples):
        if lo < half:
            mixed.append(samples[lo]); lo += 1
        if hi < len(samples):
            mixed.append(samples[hi]); hi += 1
    samples = mixed[:args.max_samples]

    # 盲化编号
    for i, s in enumerate(samples):
        s["blind_id"] = "S%02d" % (i + 1)

    print("样本 %d 篇（盲化）" % len(samples), flush=True)
    for s in samples:
        print("  %s len=%d src=%s" % (s["blind_id"], len(s["text"]), s["src"]), flush=True)

    import concurrent.futures as cf
    results = []

    def judge_one(s, model, key):
        try:
            j = call_judge(model, JUDGE_PROMPT.replace("{article}", s["text"]))
            return {"blind_id": s["blind_id"], "model": model, "score": j.get("score"),
                    "has_tradeoff": j.get("has_tradeoff"), "evidence": j.get("evidence"),
                    "error": None}
        except Exception as e:
            return {"blind_id": s["blind_id"], "model": model, "score": None,
                    "has_tradeoff": None, "evidence": None,
                    "error": "%s: %s" % (type(e).__name__, e)}

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = []
        for s in samples:
            futs.append((s["blind_id"], ex.submit(judge_one, s, args.judge_a, "A")))
            futs.append((s["blind_id"], ex.submit(judge_one, s, args.judge_b, "B")))
        for bid, fu in futs:
            results.append(fu.result())

    A = {r["blind_id"]: r for r in results if r["model"] == args.judge_a}
    B = {r["blind_id"]: r for r in results if r["model"] == args.judge_b}
    ids = [s["blind_id"] for s in samples]
    okA = [i for i in ids if A.get(i, {}).get("score") is not None]
    okB = [i for i in ids if B.get(i, {}).get("score") is not None]
    both = [i for i in ids if A.get(i, {}).get("score") is not None
            and B.get(i, {}).get("score") is not None]

    sa = [A[i]["score"] for i in both]
    sb = [B[i]["score"] for i in both]
    out = {
        "n_samples": len(samples),
        "n_scored_A": len(okA), "n_scored_B": len(okB), "n_both": len(both),
        "judge_A": args.judge_a, "judge_B": args.judge_b,
        "判官A_分数分布": {str(v): sa.count(v) for v in sorted(set(sa))},
        "判官B_分数分布": {str(v): sb.count(v) for v in sorted(set(sb))},
        "判官A_方差": var(sa), "判官B_方差": var(sb),
        "Spearman_A_vs_B": spearman(sa, sb),
        "逐篇": [],
        "盲化映射（审稿/复核用，判官看不到）": [
            {"blind_id": s["blind_id"], "src": s["src"], "arm": s["arm"],
             "topic": s["topic"], "len": len(s["text"])} for s in samples],
    }
    for i in both:
        out["逐篇"].append({
            "blind_id": i,
            "A_score": A[i]["score"], "B_score": B[i]["score"],
            "A_evidence": A[i]["evidence"], "B_evidence": B[i]["evidence"],
            "分歧": A[i]["score"] != B[i]["score"],
        })
    # 硬闸：判官必须能分开（方差 > 0 且 判官间一致）
    out["硬闸_判官可用"] = bool(
        len(both) >= 8 and var(sa) > 0 and (out["Spearman_A_vs_B"] or 0) >= 0.3)
    out["硬闸说明"] = ("n>=8 且 A 方差>0 且 Spearman(A,B)>=0.3 ⇒ 判官可用；"
                       "否则判官视为不可用，不得用于判决")
    # 判官自身错误
    out["判官错误"] = [r for r in results if r.get("error")]
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n【判官自检】n=%d  A方差=%s  B方差=%s  Spearman(A,B)=%s" % (
        out["n_both"], out["判官A_方差"], out["判官B_方差"], out["Spearman_A_vs_B"]))
    print("  A 分布 %s" % out["判官A_分数分布"])
    print("  B 分布 %s" % out["判官B_分数分布"])
    print("  硬闸_判官可用 = %s" % out["硬闸_判官可用"])
    print("  判官错误 %d 条" % len(out["判官错误"]))
    print("  [out] %s" % args.out)


if __name__ == "__main__":
    main()
