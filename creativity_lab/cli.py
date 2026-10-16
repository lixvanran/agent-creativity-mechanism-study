"""命令行入口。

  python -m creativity_lab run      --topics ... --arms direct,dual_fuse,dual_select --reps 3
  python -m creativity_lab analyze  --run <dir>
  python -m creativity_lab leak     --answers terms.txt
  python -m creativity_lab reach    --topics ...          # 可达性探针
"""
from __future__ import annotations
import argparse, json, os, sys
from collections import defaultdict

from creativity_lab import topics as T
from creativity_lab.client import LLM
from creativity_lab.leakage import QUESTION_TEXTS, ANSWER_ELEMENTS
from creativity_lab.prompts import REACH_PROBE


def cmd_run(a):
    ts = T.load(a.topics)
    if a.topic_ids: ts = [t for t in ts if t["tid"] in a.topic_ids.split(",")]
    QUESTION_TEXTS.extend(t["ask"] for t in ts)
    from creativity_lab.runner import run_matrix, ARMS
    arms = a.arms.split(",")
    for x in arms:
        if x not in ARMS: print("未知 arm:", x); return 1
    out = run_matrix(ts, arms, a.reps, a.out)
    print("完成 →", out)
    return 0


def cmd_leak(a):
    if a.answers:
        ANSWER_ELEMENTS.extend([l.strip() for l in open(a.answers, encoding="utf-8") if l.strip()])
    if a.topics:
        QUESTION_TEXTS.extend(t["ask"] for t in T.load(a.topics))
    from creativity_lab import leakage
    paths = a.paths.split(",") if a.paths else ["creativity_lab/prompts.py"]
    return leakage.main(paths)


def cmd_reach(a):
    """可达性探针：用中性追问测「答案是够不到，还是不愿说/没被激活」。"""
    ts = T.load(a.topics)
    probes = json.load(open(a.probes, encoding="utf-8")) if a.probes else {}
    for t in ts:
        p = probes.get(t["tid"])
        if not p:
            print(f"[{t['tid']}] 无探针，跳过"); continue
        llm = LLM()
        r = llm.chat(REACH_PROBE.format(ask=t["ask"], probe=p),
                     purpose="reach", min_ok=60)
        print(f"[{t['tid']}] {len(r)}B :: {r[:200].strip()}\n")


def cmd_analyze(a):
    from creativity_lab.analyze import analyze
    analyze(a.run)


def main(argv=None):
    ap = argparse.ArgumentParser("creativity_lab")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="跑对照矩阵")
    r.add_argument("--topics"); r.add_argument("--topic-ids")
    r.add_argument("--arms", default="direct,dual_fuse,dual_select")
    r.add_argument("--reps", type=int, default=3)
    r.add_argument("--out", default="runs/latest")
    r.set_defaults(fn=cmd_run)

    l = sub.add_parser("leak", help="泄漏静态检查（先自检再扫）")
    l.add_argument("--paths"); l.add_argument("--topics"); l.add_argument("--answers")
    l.set_defaults(fn=cmd_leak)

    p = sub.add_parser("reach", help="可达性探针")
    p.add_argument("--topics"); p.add_argument("--probes")
    p.set_defaults(fn=cmd_reach)

    an = sub.add_parser("analyze", help="分析一次 run")
    an.add_argument("--run", required=True)
    an.set_defaults(fn=cmd_analyze)

    a = ap.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
