# -*- coding: utf-8 -*-
"""**通道诊断**：判官调用为什么会整批失败？（不猜，直接测）

> 2026-10-23 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/probe_channel.py`
>
> ★ **背景（三次假设，三次被数据推翻）**：
>   ① 2026-10-22：我以为是 `max_tokens` 太小 ⇒ 加了预算阶梯（12000/20000/28000）
>      ⇒ 仍失败（老批 73 次调用里 36 次空内容 + 34 次截断）。
>   ② 2026-10-23 早：官方文档说 *"lower the effort level"* ⇒ 我以为是 effort 默认=max 烧光预算
>      ⇒ **实测 effort 降档后，失败照样出现**（而且 max 档也出现 ⇒ 不是 effort 决定）。
>      ⇒ 但 effort 降档**没有损害判官质量**（离散判定完全一致）⇒ effort 仍值得用来省 token/延迟。
>   ③ 现在：**失败是"整批 0 卡"（全有全无）** ⇒ 不是部分退化 ⇒ 机制待测。
>
> ★ **本探针测什么**（单次尝试、**不重试** ⇒ 看到原始行为）：
>   - `finish_reason`（length = 预算烧光 / stop = 正常）
>   - `reasoning_len`（思考块多长 ⇒ 是不是思考吃光了预算）
>   - `completion_tokens` / `prompt_tokens`
>   - `content_len` / 解析出的卡数
>   - 延迟
>   ⇒ **两组因子**：`batch`（一批几条断言）× `effort`（max/medium/low）
>
> 用法：
>   python3 -B probe_channel.py --out runs/dev/channel_probe --repeats 4 --workers 4
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import vd_anchor_out as V  # noqa: E402

READ_SRC = "runs/dev/judge_variants3/judge_variants.json"


def load_readings(path: str) -> Dict[str, Dict[str, Any]]:
    blob = json.load(open(path, encoding="utf-8"))
    for v in blob.get("variants", []):
        vid = (v.get("id") or "")
        if "minimax" in vid.lower() or vid.startswith("V1"):
            return v.get("readings") or v.get("results") or {}
    raise SystemExit("在 %s 里找不到 V1(MiniMax) 变体" % path)


def dev_task(devset: Dict[str, Any], tid: str) -> Dict[str, Any]:
    for t in devset.get("tasks", []):
        if t.get("task_id") == tid:
            return t
    raise SystemExit("DEV 里没有题 %s" % tid)


def raw_call(judge_model: str, ask: str, ev_text: str, claims: List[str],
             effort: Optional[str], max_tokens: int) -> Dict[str, Any]:
    """★ **单次尝试**（不走 LLM.chat 的阶梯）⇒ 看到原始行为。
    自己发一次请求，把 thinking 长度/finish_reason/usage 全记下来。"""
    import urllib.request
    import urllib.error

    llm = V.LLM("minimax", judge_model)
    lst = "\n".join("%d. %s" % (n + 1, claims[n]) for n in range(len(claims)))
    payload: Dict[str, Any] = {
        "model": judge_model,
        "messages": [{"role": "user",
                      "content": V.CARD_Q_OUT.format(ask=ask, ev=ev_text, claims=lst)}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    if effort:
        payload["reasoning_effort"] = effort
    headers = {"Authorization": "Bearer " + llm.key, "content-type": "application/json"}
    req = urllib.request.Request(llm.base + "/chat/completions",
                                 data=json.dumps(payload).encode(), headers=headers)
    t0 = time.time()
    rec: Dict[str, Any] = {"n_claims": len(claims), "effort": effort or "(default=max)",
                           "max_tokens": max_tokens, "secs": 0.0}
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            d = json.loads(resp.read().decode())
        ch = (d.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        raw = msg.get("content") or ""
        u = d.get("usage") or {}
        got = V.parse_card_lines(raw, len(claims))
        rec.update({
            "finish_reason": ch.get("finish_reason", ""),
            "content_len": len(raw),
            "reasoning_len": len(msg.get("reasoning_content") or ""),
            "completion_tokens": int(u.get("completion_tokens") or 0),
            "prompt_tokens": int(u.get("prompt_tokens") or 0),
            "n_parsed": len(got),
            "parsefail": max(0, len(claims) - len(got)),
            "secs": round(time.time() - t0, 2),
            "ok": True,
        })
    except Exception as e:                       # noqa: BLE001
        rec.update({"finish_reason": "error:%s" % type(e).__name__, "content_len": 0,
                    "reasoning_len": 0, "completion_tokens": 0, "prompt_tokens": 0,
                    "n_parsed": 0, "parsefail": len(claims),
                    "secs": round(time.time() - t0, 2), "ok": False})
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--answer", default="W_div#D01")
    ap.add_argument("--batches", default="2,4,8")
    ap.add_argument("--efforts", default="max,medium,low")
    ap.add_argument("--repeats", type=int, default=4)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=12000)
    ap.add_argument("--read-src", default=READ_SRC)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    readings = load_readings(args.read_src)
    devset = V.load_devset()
    judge_model = V._judge_model_from_env()
    rd = readings[args.answer]
    task = dev_task(devset, rd.get("task_id"))
    ev_items = V.evidence_items_from_dev(task)
    ev_text = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev_items))
    all_claims = [c.get("claim", "") for c in (rd.get("cards_out_all") or [])
                  if (c.get("claim") or "").strip()]

    jobs: List[Dict[str, Any]] = []
    for b in [int(x) for x in args.batches.split(",") if x]:
        for eff in [e for e in args.efforts.split(",") if e]:
            for r in range(args.repeats):
                jobs.append({"batch": b, "effort": eff, "rep": r + 1,
                             "claims": all_claims[:b]})
    print("== 通道诊断：%d 次单发调用（批大小 × effort × 重复）｜max_tokens=%d =="
          % (len(jobs), args.max_tokens))

    rows: List[Dict[str, Any]] = []
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(raw_call, judge_model, task.get("ask", ""), ev_text,
                           j["claims"], j["effort"], args.max_tokens): j for j in jobs}
        for fut in cf.as_completed(futs):
            j = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:               # noqa: BLE001
                rec = {"ok": False, "finish_reason": "error:%s" % type(e).__name__,
                       "content_len": 0, "reasoning_len": 0, "completion_tokens": 0,
                       "prompt_tokens": 0, "n_parsed": 0, "parsefail": j["batch"],
                       "secs": 0.0}
            rows.append({"batch": j["batch"], "effort": j["effort"], "rep": j["rep"], **rec})
    dt = time.time() - t0

    # ── 汇总 ────────────────────────────────────────────────
    agg: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for r in rows:
        k = (r["batch"], r["effort"])
        a = agg.setdefault(k, {"batch": r["batch"], "effort": r["effort"], "n": 0,
                                "n_trunc": 0, "n_err": 0, "n_empty": 0,
                                "n_parsefail": 0, "n_claims": 0, "n_parsed": 0,
                                "reasoning_len": [], "completion_tokens": [],
                                "content_len": [], "secs": []})
        a["n"] += 1
        a["n_trunc"] += 1 if r.get("finish_reason") == "length" else 0
        a["n_err"] += 1 if not r.get("ok") else 0
        a["n_empty"] += 1 if int(r.get("content_len") or 0) == 0 else 0
        a["n_parsefail"] += int(r.get("parsefail") or 0)
        a["n_claims"] += int(r.get("n_claims") or 0)
        a["n_parsed"] += int(r.get("n_parsed") or 0)
        for kk in ("reasoning_len", "completion_tokens", "content_len", "secs"):
            a[kk].append(int(r.get(kk) or 0))
    summary = []
    for k, a in sorted(agg.items()):
        def avg(x: List[int]) -> float:
            return round(sum(x) / float(max(len(x), 1)), 1)
        summary.append({
            "batch": a["batch"], "effort": a["effort"], "n_calls": a["n"],
            "n_truncated": a["n_trunc"], "n_error": a["n_err"], "n_empty_content": a["n_empty"],
            "n_parsefail": a["n_parsefail"], "n_claims": a["n_claims"],
            "n_parsed": a["n_parsed"],
            "parsefail_rate": round(a["n_parsefail"] / float(max(a["n_claims"], 1)), 4),
            "avg_reasoning_len": avg(a["reasoning_len"]),
            "avg_completion_tokens": avg(a["completion_tokens"]),
            "avg_content_len": avg(a["content_len"]),
            "avg_secs": avg(a["secs"]),
        })

    out = {"meta": {"answer": args.answer, "task_id": rd.get("task_id"),
                     "judge_model": judge_model, "max_tokens": args.max_tokens,
                     "repeats": args.repeats, "n_jobs": len(jobs),
                     "elapsed_sec": round(dt, 1),
                     "note": "单次尝试，不走阶梯 ⇒ 看到原始行为"},
           "summary": summary, "rows": rows}
    with open(os.path.join(args.out, "channel_probe.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    md = ["# 判官通道诊断（单次尝试，不重试）\n",
          "> 判官 `%s` ｜ max_tokens=%d ｜ 答案 `%s`（题 %s）\n"
          % (judge_model, args.max_tokens, args.answer, rd.get("task_id")),
          "\n## 主表\n",
          "| 批大小 | effort | 调用 | 截断 | 空内容 | 错误 | parsefail | 解析率 | 平均思考字符 | 平均完成token | 平均内容字符 | 平均秒 |",
          "|---:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for s in summary:
        pr = s["n_parsed"] / float(max(s["n_claims"], 1))
        md.append("| %d | %s | %d | %d | %d | %d | %d | **%.2f** | %d | %d | %d | %.0f |"
                  % (s["batch"], s["effort"], s["n_calls"], s["n_truncated"],
                     s["n_empty_content"], s["n_error"], s["n_parsefail"], pr,
                     s["avg_reasoning_len"], s["avg_completion_tokens"],
                     s["avg_content_len"], s["avg_secs"]))
    md += ["\n## 逐次明细\n", "| 批 | effort | 重复 | finish_reason | content_len | reasoning_len | 完成token | 解析卡 | 秒 |",
           "|---:|---|--:|---|--:|--:|--:|--:|--:|"]
    for r in sorted(rows, key=lambda x: (x["batch"], x["effort"], x["rep"])):
        md.append("| %d | %s | %d | `%s` | %d | %d | %d | %d | %.0f |"
                  % (r["batch"], r["effort"], r["rep"], r.get("finish_reason", ""),
                     r.get("content_len", 0), r.get("reasoning_len", 0),
                     r.get("completion_tokens", 0), r.get("n_parsed", 0),
                     r.get("secs", 0)))
    with open(os.path.join(args.out, "channel_probe.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print("\n== 诊断结果 ==")
    for s in summary:
        pr = s["n_parsed"] / float(max(s["n_claims"], 1))
        print("  批%-2d %-7s 调用%d 截断%d 空%d 解析率%.2f 平均思考%d tok 完成token%d %.0fs"
              % (s["batch"], s["effort"], s["n_calls"], s["n_truncated"],
                 s["n_empty_content"], pr, s["avg_reasoning_len"],
                 s["avg_completion_tokens"], s["avg_secs"]))
    print("\n✓ 落盘 %s（耗时 %.0fs）" % (args.out, dt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
