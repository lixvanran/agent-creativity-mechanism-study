#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 核心实验：判官驱动力读数（多维），对上「纯概率检索 vs 由观点驱动」。

三个维度（各对应目标的一个侧面）：
  D1 **取舍明确度**（state1）——作者是否做出了明确取舍（写透什么 / 放弃什么）
  D2 **观点驱动力**（state2）——产出是"由一个观点组织出来的"，还是"面面俱到的通用写作"
  D3 **人类似然感**（state3）——这篇读起来像一个有明确主张的人在写，
     还是像一段从语料里检索拼出来的流畅文字

★ 纪律：
  · 判官与被测**不同厂商**（被测 MiniMax-M3，判官 grok）⇒ 判据与被测不同源
  · **盲化**：判官拿不到臂标签、题号、模型名
  · **题内配对**：分析单元 = 题，绝不把"同 prompt 跑两次"当配对
  · 分数只用**题内相对排序**，不用绝对分（判官自检显示两判官系统性不同）
  · 失败/解析失败**显式标记**，不静默剔除
"""
import argparse
import json
import os
import re
import time
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

DIMS = {
    "D1_取舍明确度": (
        "判断作者是否做出了**明确的取舍**——他明确表示了\"这一轮我写透/坚持的是某一点，"
        "某一点我选择不展开/放弃\"，而不是面面俱到地讲。\n"
        "0=完全没有取舍，通篇平行铺陈；1=几乎没有；2=有取舍倾向但被大量铺陈稀释；"
        "3=有明确取舍，说清了保留什么；4=明确取舍，且说清保留与放弃、理由具体"),
    "D2_观点驱动力": (
        "判断这篇文字是**由一个明确观点组织出来的**，还是**面面俱到的通用写作**。\n"
        "0=纯通用/八面玲珑，看不出任何主张；1=有零星主张但整体平行罗列；"
        "2=能看出一个主张但论述没有围绕它组织；3=全文围绕一个明确主张展开；"
        "4=全文由一个尖锐主张贯穿，并且为它做了取舍（有些东西明确不写）"),
    "D3_人类似然感": (
        "判断这篇文字读起来像**一个有自己的主张、在写给他人看的人**写的，"
        "还是像**从语料里检索拼出来的流畅但无所谓段落**。\n"
        "0=完全是流畅但无主的拼贴；1=大部分是拼贴；2=有人的痕迹但不稳定；"
        "3=明显像一个有立场的人在写；4=强烈地像一个人在为自己的某个想法写作"),
}

JUDGE_TMPL = """你是一位严格的写作评估者。下面给你一篇中文文章。

请按以下维度打分（每个维度 0-4 的整数），并给出简短依据。

{dim_def}

只输出 JSON，键为 score、evidence：
{{"score": 整数, "evidence": "不超过40字"}}

文章：
<<<
{article}
>>>"""


MM_BASE = "https://api.minimaxi.com/v1"


def call_judge_mm(model, prompt, timeout=120):
    """MiniMax 判官（**同源**）。M3 需 thinking disabled 才有干净 JSON。"""
    key = os.environ.get("MINIMAX_SUBSCRIPTION_KEY", "")
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 600, "temperature": 0,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"}}
    req = urllib.request.Request(
        MM_BASE + "/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=timeout)
    d = json.loads(r.read().decode())
    txt = (d["choices"][0]["message"].get("content") or "").strip()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("判官未返回 JSON: %r" % txt[:120])
    return json.loads(m.group(0))


def call_judge(model, prompt, timeout=120):
    key = os.environ.get("OPENROUTER_API_KEY", "")
    body = {"model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300, "temperature": 0,
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


def load_samples(paths):
    """从若干 jsonl 收集产出样本。**不读臂标签进判官**（只用于事后归因）。"""
    out = []
    for p in paths:
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            txt = (r.get("text") or "").strip()
            if len(txt) < 200:
                continue
            lr = r.get("lang_cn_ratio")
            if lr is not None and lr < 0.9:
                continue
            if r.get("error"):
                continue
            out.append({
                "src": os.path.basename(p),
                "arm": r.get("arm"),
                "tag": r.get("tag"),
                "topic": r.get("topic_id") or r.get("topic") or "G01",
                "batch": r.get("batch_id"),
                "text": txt,
                "has_state": bool(r.get("state1")),
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "judge_driver.json"))
    ap.add_argument("--judge", default="x-ai/grok-4.20")
    ap.add_argument("--judge2", default="x-ai/grok-4.3")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-per-source", type=int, default=99)
    args = ap.parse_args()

    samples = load_samples(args.src)
    # 每 (src, arm, tag) 只取最后一条（同批补跑去重）
    buck = defaultdict(list)
    for s in samples:
        buck[(s["src"], s["arm"], s["tag"])].append(s)
    samples = [g[-1] for g in buck.values()]
    print("样本 %d 篇" % len(samples), flush=True)

    jobs = []
    for s in samples:
        for dname, ddef in DIMS.items():
            for jm in (args.judge, args.judge2):
                jobs.append((s, dname, ddef, jm))
    print("判官任务 %d 个（%d 样本 × %d 维 × %d 判官）"
          % (len(jobs), len(samples), len(DIMS), 2), flush=True)

    import concurrent.futures as cf

    def one(s, dname, ddef, jm):
        prompt = JUDGE_TMPL.replace("{dim_def}", ddef).replace("{article}", s["text"])
        try:
            fn = call_judge_mm if jm.startswith("MiniMax") else call_judge
            j = fn(jm, prompt)
            return {"arm": s["arm"], "tag": s["tag"], "topic": s["topic"],
                    "src": s["src"], "batch": s["batch"], "dim": dname,
                    "judge": jm, "score": j.get("score"),
                    "evidence": j.get("evidence"), "error": None}
        except Exception as e:
            return {"arm": s["arm"], "tag": s["tag"], "topic": s["topic"],
                    "src": s["src"], "batch": s["batch"], "dim": dname,
                    "judge": jm, "score": None, "evidence": None,
                    "error": "%s: %s" % (type(e).__name__, e)}

    results = []
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(one, *j) for j in jobs]
        for i, fu in enumerate(cf.as_completed(futs)):
            results.append(fu.result())
            if (i + 1) % 20 == 0:
                print("  %d/%d  %.0fs" % (i + 1, len(futs), time.time() - t0), flush=True)

    errs = [r for r in results if r.get("error")]
    print("完成 %d 条，错误 %d 条，%.0fs" % (len(results), len(errs), time.time() - t0))

    # ---------- 题内配对分析 ----------
    by = defaultdict(dict)          # (topic, dim, judge) -> {(arm, tag): score}
    meta = {}
    for r in results:
        if r.get("score") is None:
            continue
        by[(r["topic"], r["dim"], r["judge"])][(r["arm"], r["tag"])] = r["score"]
        meta[(r["arm"], r["tag"])] = r
    ARMS = ["A", "S-self", "WF-a3-NL", "WF-a3", "WF-p", "WF-a3-NO"]

    def mean(v):
        return round(sum(v) / len(v), 4) if v else None

    analysis = {}
    for (topic, dim, jm), m in sorted(by.items()):
        arms_present = [a for a in ARMS if any(k[0] == a for k in m)]
        if len(arms_present) < 2:
            continue
        # 题内：每臂取该题内所有 rep 的均值（rep 是重复测量，不是配对单位）
        per_arm = {}
        for a in arms_present:
            vals = [v for k, v in m.items() if k[0] == a]
            per_arm[a] = {"mean": mean(vals), "vals": vals, "n": len(vals)}
        analysis.setdefault(topic, {}).setdefault(dim, {})[jm] = per_arm

    out = {"meta": {"judges": [args.judge, args.judge2], "dims": list(DIMS),
                    "n_samples": len(samples), "n_results": len(results),
                    "n_errors": len(errs), "srcs": args.src,
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")},
           "逐条": results, "题内分析": analysis}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---------- 打印摘要 ----------
    print("\n【题内配对：各臂均值】")
    for topic, dims in sorted(analysis.items()):
        for dim, jms in sorted(dims.items()):
            for jm, per_arm in jms.items():
                tag = "A" if jm == args.judge else "B"
                line = "  %-6s %-14s [%s] " % (topic, dim, tag)
                for a in ARMS:
                    v = per_arm.get(a)
                    line += "%s=%.3f(n%d) " % (a, v["mean"], v["n"]) if v else "%s=- " % a
                print(line)
    print("\n[out] %s" % args.out)


if __name__ == "__main__":
    main()
