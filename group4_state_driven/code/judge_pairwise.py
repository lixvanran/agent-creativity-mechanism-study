#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 两两比较判官（pairwise）—— 消除绝对打分的天花板效应。

为什么必须改：
  · 绝对打分在 D1 上**饱和**：判官 grok-4.20 把 18 篇全打 3.000 ⇒ 零区分度
  · 两判官**系统性严格度不同**（4.20 偏松、4.3 偏严）⇒ 绝对分不可跨判官比
  · 而 pairwise：① 题内配对天然成立 ② 判官只做"哪一个更好"的相对判断
    ③ **位置偏差可测**（同一对交换位置各跑一次）

对照对（覆盖 RQ1–RQ3 + 旧核心问题）：
  1. A      vs WF-a3      ★ 状态机 vs 直答
  2. S-self vs WF-a3      ★★ 状态机 vs 等预算自我说明（RQ3）
  3. WF-a3-NO vs WF-a3    ★ 观测的贡献
  4. WF-p   vs WF-a3      ★ 状态机 vs 提示词状态机（L0）

输出：每对的 win/tie/lose（题内、按 tag 配对），以及**位置一致性**（交换位置后结论是否翻转）。
"""
import argparse
import json
import os
import re
import time
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

PAIRS = [("A", "WF-a3"), ("S-self", "WF-a3"),
         ("WF-a3-NO", "WF-a3"), ("WF-p", "WF-a3")]

DIMS = {
    "D1_取舍明确度": "哪一篇做出了更**明确的取舍**（明确说清写透什么、放弃什么）？",
    "D2_观点驱动力": "哪一篇更**由一个明确观点组织**（而不是面面俱到的通用写作）？",
    "D3_人类似然感": "哪一篇更像是**一个有自己的主张的人在写**，而不是检索拼贴出来的流畅文字？",
}

TMPL = """你是一位严格的写作评估者。下面给你两篇中文文章（同一题目下的两个不同版本）。

问题：{dim_def}

请只回答哪一个更好。
- "A" 表示第一篇更好
- "B" 表示第二篇更好
- "tie" 表示两篇在这件事上没有可辨差异

只输出 JSON：{{"winner": "A" 或 "B" 或 "tie", "evidence": "不超过40字"}}

第一篇：
<<<
{t1}
>>>

第二篇：
<<<
{t2}
>>>"""


MM_BASE = "https://api.minimaxi.com/v1"
MM_KEY_ENV = "MINIMAX_SUBSCRIPTION_KEY"


def call_judge_mm(model, prompt, timeout=120):
    """MiniMax 端点判官（**同源**：被测生成器也是 MiniMax-M3）。

    ⚠️ 同源判官的固有限制：它与被测共享偏好 ⇒ 不能作**主判据**。
       正确用法是**交叉验证**：与跨厂商判官（grok）在同一批数据上比方向。
    ★ MiniMax-M3 需 `thinking:{type:"disabled"}` 才有干净 JSON；
      M2.7 会把 <think> 塞进 content ⇒ 不可用。
    """
    key = os.environ.get(MM_KEY_ENV, "")
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 600, "temperature": 0,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"}}
    req = urllib.request.Request(
        MM_BASE + "/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    # ★ 429 必须**退避重试**（实测 MiniMax 会限流；不重试 ⇒ 失败系统性集中在后跑的题 ⇒ 污染读数）
    last = None
    for attempt in range(5):
        try:
            r = urllib.request.urlopen(req, timeout=timeout)
            d = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503):
                time.sleep(4 * (attempt + 1))
                continue
            raise
    else:
        raise last
    txt = (d["choices"][0]["message"].get("content") or "").strip()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("判官未返回 JSON: %r" % txt[:120])
    return json.loads(m.group(0))


def call_judge(model, prompt, timeout=120):
    key = os.environ.get("OPENROUTER_API_KEY", "")
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 600, "temperature": 0,
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


def load(paths):
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
            if len(txt) < 200 or r.get("error"):
                continue
            lr = r.get("lang_cn_ratio")
            if lr is not None and lr < 0.9:
                continue
            out.append({"arm": r.get("arm"), "tag": r.get("tag"),
                        "topic": r.get("topic_id") or r.get("topic") or "G01",
                        "text": txt, "src": os.path.basename(p)})
    # 同 (arm,tag) 去重取最后一条
    b = defaultdict(list)
    for s in out:
        b[(s["arm"], s["tag"], s["topic"])].append(s)
    return [g[-1] for g in b.values()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "judge_pairwise.json"))
    ap.add_argument("--judges", nargs="+", default=["x-ai/grok-4.20", "x-ai/grok-4.3"])
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    S = load(args.src)
    idx = {(s["arm"], s["tag"], s["topic"]): s for s in S}
    topics = sorted({s["topic"] for s in S})
    print("样本 %d ｜ 臂 %s ｜ 题 %s" % (
        len(S), sorted({s['arm'] for s in S}), topics), flush=True)

    jobs = []
    for topic in topics:
        tags = sorted({s["tag"] for s in S if s["topic"] == topic})
        for (x, y) in PAIRS:
            for t in tags:
                if (x, t, topic) not in idx or (y, t, topic) not in idx:
                    continue
                for dim, q in DIMS.items():
                    for jm in args.judges:
                        for order in (0, 1):
                            jobs.append({"topic": topic, "tag": t, "x": x, "y": y,
                                         "dim": dim, "judge": jm, "order": order})
    print("判官任务 %d 个" % len(jobs), flush=True)

    import concurrent.futures as cf

    def one(j):
        sx, sy = idx[(j["x"], j["tag"], j["topic"])], idx[(j["y"], j["tag"], j["topic"])]
        t1, t2 = (sx["text"], sy["text"]) if j["order"] == 0 else (sy["text"], sx["text"])
        prompt = (TMPL.replace("{dim_def}", DIMS[j["dim"]])
                  .replace("{t1}", t1).replace("{t2}", t2))
        raw = None
        try:
            fn = call_judge_mm if j["judge"].startswith("MiniMax") else call_judge
            raw = fn(j["judge"], prompt)
            w = raw.get("winner")
            # 放宽解析："A"/"B"/"tie"/"Article A"/"第一篇"/"A (因为...)" 等
            if isinstance(w, str):
                ws = w.strip().strip('"\'')
                low = ws.lower()
                if low.startswith("a") or "第一篇" in ws or "前者" in ws:
                    w = "A"
                elif low.startswith("b") or "第二篇" in ws or "后者" in ws:
                    w = "B"
                elif "tie" in low or "平" in ws or "无差异" in ws or "相当" in ws:
                    w = "tie"
                else:
                    w = None
            else:
                w = None
        except Exception as e:
            w = None
            j = dict(j, error="%s: %s" % (type(e).__name__, e))
        # order=0 ⇒ 位置A是x；order=1 ⇒ 位置A是y ⇒ 归一到"x vs y"
        if w is None:
            res = None
        elif w == "tie":
            res = "tie"
        else:
            first_is_x = (j["order"] == 0)
            x_wins = (w == "A") == first_is_x
            res = "x" if x_wins else "y"
        out = dict(j)
        out["winner_x_vs_y"] = res
        if res is None:
            # ★ 失败必须**显式标记并保留原始返回**（不许静默吞掉）
            out["error"] = j.get("error") or ("unparsable_winner: %r" % (raw,))
        return out

    results = []
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(one, j) for j in jobs]
        for i, fu in enumerate(cf.as_completed(futs)):
            results.append(fu.result())
            if (i + 1) % 25 == 0:
                print("  %d/%d %.0fs" % (i + 1, len(futs), time.time() - t0), flush=True)

    errs = [r for r in results if r.get("winner_x_vs_y") is None]
    print("完成 %d，解析失败 %d，%.0fs" % (len(results), len(errs), time.time() - t0))

    # ---------- 汇总 ----------
    agg = defaultdict(lambda: defaultdict(list))   # (judge, dim, pair) -> [res]
    pos_flip = defaultdict(list)                  # 位置不一致
    for r in results:
        v = r.get("winner_x_vs_y")
        if v is None:
            continue
        key = (r["judge"], r["dim"], "%s vs %s" % (r["x"], r["y"]))
        agg[key][(r["topic"], r["tag"], r["order"])].append(v)

    table = {}
    for key, d in sorted(agg.items()):
        # 位置去偏：同一 (topic,tag) 的 order=0 与 order=1 两票合并
        merged = {}
        for (topic, tag, order), vs in d.items():
            merged.setdefault((topic, tag), []).extend(vs)
        # ★ merged 的值是**票的列表**（每个 order 一票）⇒ 必须展平后再计数
        flat = [v for vs in merged.values() for v in vs]
        wins = sum(1 for v in flat if v == "x")
        loses = sum(1 for v in flat if v == "y")
        ties = sum(1 for v in flat if v == "tie")
        # 位置一致性：两票是否一致
        consist = sum(1 for vs in merged.values()
                      if len(vs) == 2 and (vs[0] == vs[1] or "tie" in vs))
        table.setdefault(key[0], {}).setdefault(key[1], {})[key[2]] = {
            "n_pairs": len(merged), "n_votes": len(flat),
            "win": wins, "tie": ties, "lose": loses,
            "位置一致数": consist, "位置一致率": round(consist / len(merged), 4) if merged else None,
        }

    out = {"meta": {"pairs": PAIRS, "dims": list(DIMS), "judges": args.judges,
                    "n_samples": len(S), "n_results": len(results),
                    "n_parse_fail": len(errs), "srcs": args.src,
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")},
           "汇总": table, "逐条": results}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n【两两比较：x 胜 / 平 / y 负】")
    for jm, dims in sorted(table.items()):
        print("  判官 %s" % jm)
        for dim, pairs in sorted(dims.items()):
            print("    %s" % dim)
            for p, v in pairs.items():
                print("      %-22s 胜%d 平%d 负%d  (n=%d, 位置一致率 %s)"
                      % (p, v["win"], v["tie"], v["lose"], v["n_votes"], v["位置一致率"]))
    print("\n[out] %s" % args.out)


if __name__ == "__main__":
    main()
