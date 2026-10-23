#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多题扩展运行器（v3 架构化状态机 · 扩题版）。

★ 换题时**严格遵守极简原则**（第四组铁律）：
  只给"题目一句话"，**不带** audience / genre / length / brief / dilemma /
  pole_a / pole_b / role 等手写题库装饰 —— 那些是解法提示，会造成过拟合。
  只有当题目本身必须交代"产出是什么"时，才保留 genre（产出类型不是解法）。

用法：
  python3 run_multitopic.py --topics T06,T07,T10 --arms A,S-self,WF-a3-NL,WF-a3 --reps 3
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import runner as RUNNER            # noqa: E402
import run_arch3_compare as RAC     # noqa: E402

# ★ 极简题面：只保留"情境 + 任务 (+ 产出类型)"。
#   不含 audience / length / dilemma / link / axis / pp —— 那些是解法泄漏。
MINIMAL = {
    "T06": "女儿在父亲的葬礼上读一篇悼词。父亲与女儿决裂三年，最后也没有和好。"
           "这篇悼词该怎么写？",
    "T07": "当 AI 生成的代码出了 bug，程序员要不要负责？写一篇科普小品讲清楚这件事。",
    "T10": "一个人 28 岁，连续三年被裁员，最后在殡仪馆做了一年半殡葬师，"
           "现在要应聘同一家殡葬服务公司的带班岗。他该怎么写这段求职自述？",
    # G01 沿用 v3 原题（一字不改），保证与 v3 已有数据可比
    "G01": "你如何看待高考英语作文？写成一篇文章。",
}


def topic_of(tid):
    for t in RUNNER.TOPICS:
        if t.get("id") == tid:
            return t
    return None


def minimal_question(tid):
    if tid in MINIMAL:
        return MINIMAL[tid]
    t = topic_of(tid)
    if not t:
        raise KeyError("题库无此题: %s" % tid)
    # 兜底：仍只取 title + brief 首句
    return t["title"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", default="T06,T07,T10")
    ap.add_argument("--arms", default="A,S-self,WF-a3-NL,WF-a3")
    ap.add_argument("--reps", default="3")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "runs", "multitopic"))
    ap.add_argument("--batch-prefix", default="mt")
    args = ap.parse_args()

    tids = [x.strip() for x in args.topics.split(",") if x.strip()]
    arms = [x.strip() for x in args.arms.split(",") if x.strip()]
    reps = [x.strip() for x in args.reps.split(",") if x.strip()]
    os.makedirs(args.out_dir, exist_ok=True)

    import concurrent.futures as cf

    for tid in tids:
      try:
        q = minimal_question(tid)
        # ★ monkey-patch：函数体引用模块全局 QUESTION ⇒ 改这里即生效
        RAC.QUESTION = q
        # 供下游分析用：把题面写进每条记录
        batch = "%s-%s-%s" % (args.batch_prefix, tid,
                              time.strftime("%Y%m%d-%H%M%S"))
        out = os.path.join(args.out_dir, "mt_%s.jsonl" % tid)
        if os.path.exists(out):
            os.remove(out)
        print("\n===== %s | batch=%s =====" % (tid, batch), flush=True)
        print("  题面: %s" % q, flush=True)

        # 复用 run_arch3_compare 的臂实现（逐臂、逐 rep）
        jobs = []
        for arm in arms:
            for rep in reps:
                jobs.append((arm, rep))
        out_f = open(out, "w", encoding="utf-8")

        # dispatch 在 RAC.main() 内部（局部变量）⇒ 这里自己建一份
        dispatch = {
            "A": RAC.run_A3,
            "WF-p": RAC.run_WF_p3,
            "S-self": RAC.run_S_self,
            "WF-a3": lambda t: RAC.run_WF_a3(t, False, False),
            "WF-a3-NO": lambda t: RAC.run_WF_a3(t, True, False),
            "WF-a3-NL": lambda t: RAC.run_WF_a3(t, False, True),
        }

        def one(arm, rep):
            try:
                rec = dispatch[arm](rep)
            except Exception as e:
                rec = {"arm": arm, "tag": rep, "text": "", "error": str(e)}
            rec["topic_id"] = tid
            rec["question"] = q
            rec["batch_id"] = batch
            return rec

        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(one, a, r): (a, r) for a, r in jobs}
            for fu in cf.as_completed(futs):
                arm, rep = futs[fu]
                rec = fu.result()
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out_f.flush()
                print("  [%s] %-9s #%s %5d字 %s" % (
                    batch, arm, rep, len(rec.get("text") or ""),
                    "ok" if not rec.get("error") else "ERR:" + str(rec.get("error"))[:60]),
                    flush=True)
        out_f.close()
      except Exception as e:
        # ★ 一题失败**不拖死整轮**（上次 S-self 超时把整个进程带走了）
        import traceback
        print("  [题 %s 失败] %s: %s" % (tid, type(e).__name__, e), flush=True)
        traceback.print_exc()
        continue
    print("\n[done] %s" % args.out_dir, flush=True)


if __name__ == "__main__":
    main()
