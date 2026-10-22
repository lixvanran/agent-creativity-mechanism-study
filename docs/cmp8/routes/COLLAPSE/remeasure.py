# -*- coding: utf-8 -*-
"""跨厂商判官交叉（**配对**：同一份答案、两个判官）

> 2026-10-22 ｜ 依据：ToT 的换评估模型交叉实验（同源 74% / 换评估器 64% / 31%）

## 为什么必须"配对"而不是"重跑一遍"
生成侧是 MiniMax **temp=0.7** ⇒ **不是确定性** ⇒ 重跑一遍会得到**不同文本**
⇒ ⇒ 那时候读数差异就混进了"生成漂移"，**没法归因到判官**。
⇒ ⇒ 所以：**取已落盘的答案原文**，只换判官重测 ⇒ **唯一变化就是"谁在判"**。

## 用法
```bash
# ① 用 MiniMax 判官跑主批次（产出 runs/main/w_dev_run.json）
python3 -B -u run_dev.py --tasks 2 --reps 3 --arms B0_direct,B0_bestof3,W_design_L2,W_train_L3 \
        --out runs/main
# ② 用 OpenRouter 判官**重测同一批答案**
python3 -B -u remeasure.py --run runs/main/w_dev_run.json --judge openrouter \
        --out runs/main/remeasured_openrouter.json
# ③ 配对比较（两份读数按 (题, 臂, rep) 对齐）
python3 -B -u remeasure.py --compare runs/main/w_dev_run.json runs/main/remeasured_openrouter.json
```

## 判读（预注册在 PREREG-DECISION-RULES-2026-10-22.md §5）
- **换判官后若增益塌掉 ⇒ 结论无效**
- 逐 (题, 臂, rep) 报：承重维度数（两个判官各一个）、差值、**一致率**（两判官是否同判承重）
- ⚠️ **成本**：OpenRouter 判官比 MiniMax 贵 ⇒ 建议 `--limit` 限量
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/workspace/lab/batch-U1")
sys.dont_write_bytecode = True

import u1_lib as U          # noqa: E402
import measure as M         # noqa: E402
import workflow as W        # noqa: E402
import anchor_out as AO     # noqa: E402
import run_dev as RD        # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="", help="要重测的 w_dev_run.json")
    ap.add_argument("--judge", default="openrouter", choices=["minimax", "openrouter"])
    ap.add_argument("--judge-model", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--limit", type=int, default=0, help="最多重测多少份（0=不限）")
    ap.add_argument("--compare", nargs=2, default=None, metavar=("A", "B"),
                    help="比较两份读数（配对）")
    args = ap.parse_args()

    if args.compare:
        return compare(args.compare[0], args.compare[1])

    # ★ 支持两种输入：完整 JSON（w_dev_run.json）**或**增量落盘的 arms.jsonl
    #   （批次未跑完时只有后者 ⇒ 但已完成的臂不该丢）
    if args.run.endswith(".jsonl"):
        run = dict(rows=[])
        _by = {}
        for _ln in open(args.run, encoding="utf-8"):
            try:
                _d = json.loads(_ln)
            except Exception:
                continue
            _k = (_d.get("task_id"), _d.get("rep"))
            _by.setdefault(_k, {})[_d.get("arm")] = _d
        run["rows"] = [dict(task_id=k[0], rep=k[1], arms=v) for k, v in _by.items()]
        run["judge_model"] = "minimax"
    else:
        with open(args.run, encoding="utf-8") as f:
            run = json.load(f)

    if args.judge == "openrouter":
        jm = args.judge_model or U.OR_MODEL
        jllm = U.OpenRouterLLM()
        same_vendor = False
    else:
        jm = args.judge_model or U.MM_MODEL
        jllm = U.MiniMaxLLM()
        same_vendor = True

    # DEV 题（重测需要题面 + 依据 + 结论空间）
    tasks = RD.load_tasks(20)
    tmap = {t["task_id"]: t for t in tasks}

    out_rows = []
    n = 0
    for row in run.get("rows", []):
        tid = row.get("task_id")
        task = tmap.get(tid)
        if not task:
            continue
        for arm, a in (row.get("arms") or {}).items():
            if not isinstance(a, dict) or a.get("error"):
                continue
            ans = a.get("answer") or ""
            if not ans.strip():
                continue
            if args.limit and n >= args.limit:
                break
            n += 1
            print("  [%d] %s / %s / rep%s …" % (n, tid, arm, row.get("rep")), flush=True)
            try:
                res, cards, anchor = RD.measure_one(
                    jllm, task, ans, "re/%s/%s/rep%s" % (tid, arm, row.get("rep")),
                    judge_model=jm)
                fams = RD.dims_from_cards(cards)
                out_rows.append(dict(
                    task_id=tid, arm=arm, rep=row.get("rep"),
                    n_dims=len(fams), n_load_bearing=sum(1 for c in cards if c["load_bearing"]),
                    n_cards=len(cards), parsefail_rate=res.get("parsefail_rate"),
                    vd_anchor_out=(anchor or {}).get("n_anchor_out", 0),
                    n_anchor_out=(anchor or {}).get("n_anchor_out", 0),
                    anchor_out_claims=(anchor or {}).get("anchor_out_claims", []),
                    dims=sorted(fams),
                    judge_model=jm, judge_same_vendor=same_vendor,
                ))
                print("      dims=%s lb=%s 锚外=%s"
                      % (len(fams), sum(1 for c in cards if c["load_bearing"]),
                         (anchor or {}).get("n_anchor_out", 0)), flush=True)
            except Exception as e:
                print("      ⚠️ 失败（计入，不重跑）：%s: %s" % (type(e).__name__, e), flush=True)
                out_rows.append(dict(task_id=tid, arm=arm, rep=row.get("rep"),
                                     error="%s: %s" % (type(e).__name__, e)))
            if args.limit and n >= args.limit:
                break
        if args.limit and n >= args.limit:
            break

    out = dict(schema="remeasure/1", src_run=args.run, judge_model=jm,
               judge_same_vendor=same_vendor, judge_vendor=args.judge,
               n_measured=n, rows=out_rows)
    p = args.out or (os.path.join(os.path.dirname(args.run),
                                  "remeasured_%s.json" % args.judge))
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("落盘：%s（%d 份）" % (p, n))
    return 0


def compare(pa, pb):
    """配对比较两份读数（同一份答案、两个判官）。"""
    A = json.load(open(pa, encoding="utf-8"))
    B = json.load(open(pb, encoding="utf-8"))
    if "rows" in A and isinstance(A["rows"][0] if A.get("rows") else {}, dict) \
            and "n_dims" in (A["rows"][0] if A.get("rows") else {}):
        ra = A["rows"]
    else:
        ra = []
        for row in A.get("rows", []):
            for arm, a in (row.get("arms") or {}).items():
                if isinstance(a, dict) and "error" not in a:
                    ra.append(dict(task_id=row.get("task_id"), arm=arm,
                                   rep=row.get("rep"), n_dims=a.get("n_dims"),
                                   n_load_bearing=a.get("n_load_bearing"),
                                   vd_anchor_out=a.get("vd_anchor_out")))
    rb = B["rows"]

    def key(r):
        return (r.get("task_id"), r.get("arm"), r.get("rep"))

    mb = {key(r): r for r in rb}
    print("══ 配对比较（同一份答案，两个判官）══")
    print("  A: %s  判官=%s" % (os.path.basename(pa), A.get("judge_model", A.get("judge", "?"))))
    print("  B: %s  判官=%s" % (os.path.basename(pb), B.get("judge_model", B.get("judge", "?"))))
    print("  %-22s %6s %6s %6s %6s" % ("(题,臂,rep)", "A维", "B维", "差", "锚外A/B"))
    diffs, same = [], 0
    n = 0
    for r in ra:
        k = key(r)
        if k not in mb:
            continue
        b = mb[k]
        if r.get("n_dims") is None or b.get("n_dims") is None:
            continue
        d = b["n_dims"] - r["n_dims"]
        diffs.append(d)
        n += 1
        same += 1 if d == 0 else 0
        print("  %-22s %6s %6s %+6d %6s/%s"
              % (str(k), r["n_dims"], b["n_dims"], d,
                 r.get("vd_anchor_out"), b.get("vd_anchor_out")))
    if diffs:
        diffs_sorted = sorted(diffs)
        med = diffs_sorted[len(diffs) // 2]
        print("  ── n=%d  完全一致 %d/%d (%.0f%%)  差值中位数 %+d  范围 %+d..%+d"
              % (n, same, n, 100.0 * same / n, med, min(diffs), max(diffs)))
        print("  ★ 判读：换判官后若**臂间排序**塌掉 ⇒ 结论无效（预注册 §5）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
