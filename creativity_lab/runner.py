"""统一跑器。审计只认 `llm.rec` 里的调用记录，不认 arm 的自述。"""
from __future__ import annotations
import json, os, time
from dataclasses import asdict
from creativity_lab.client import LLM
from creativity_lab.arms.direct import Direct
from creativity_lab.arms.dual import Dual

ARMS = {
    "direct":       lambda: Direct(),
    "dual_fuse":    lambda: Dual("fuse"),
    "dual_select":  lambda: Dual("select"),
}


def run_matrix(topics: list[dict], arm_names: list[str], reps: int,
               outdir: str, topic_workers: int = 1) -> str:
    os.makedirs(outdir, exist_ok=True)

    def one_topic(T):
        rec_all = []
        for rep in range(1, reps + 1):
            for an in arm_names:
                llm = LLM()
                arm = ARMS[an]()
                t0 = time.time()
                try:
                    r = arm.run(llm, T, rep)
                except Exception as e:
                    r = None
                    err = str(e)[:200]
                n_calls = len(llm.rec)
                n_ok = sum(1 for c in llm.rec if c.ok)
                with open(f"{outdir}/{T['tid']}_r{rep}_{an}.md", "w", encoding="utf-8") as f:
                    f.write((r.text if r else "") or "")
                rec = dict(arm=an, tid=T["tid"], rep=rep,
                           chars=len(r.text) if r else 0,
                           branches=r.branches if r else 0,
                           calls=n_calls, calls_ok=n_ok,
                           secs=round(time.time() - t0, 1),
                           call_log=[asdict(c) for c in llm.rec])
                rec_all.append(rec)
                print(f"  [{T['tid']} r{rep}] {an:<12} {rec['chars']:>5}B "
                      f"分支{rec['branches']}/5 调用{n_ok}/{n_calls} {rec['secs']}s", flush=True)
        return rec_all

    allrec = []
    for T in topics:                      # 题级串行：题内也串行，实测最稳
        allrec += one_topic(T)
    with open(f"{outdir}/_calllog.jsonl", "w", encoding="utf-8") as f:
        for r in allrec:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return f"{outdir}/_calllog.jsonl"
