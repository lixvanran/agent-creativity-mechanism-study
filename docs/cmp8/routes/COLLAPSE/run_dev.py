# -*- coding: utf-8 -*-
"""治塌缩工作流（W）· **真实跑批**（DEV 集上）

> 2026-10-22 ｜ 配套 `workflow.py` ｜ **这是第一次把 W 接到真模型上跑**

## 跑什么
两条臂，同题、同模型、同测量：

| 臂 | 是什么 | 作用 |
|---|---|---|
| `B0_direct` | **直调**：题面 + 输出规格，一次调用 | 参照基线（= "不知道该考虑哪些维度"的状态）|
| `W_collapse` | **治塌缩工作流**：认知帧解耦 → 去冗余 → **动作演化** → 汇总 → 机械装配 | 我们的架构 |

⇒ 读数：**承重维度数**（`load_bearing` 且 `supports_conclusions` 非空且去冗余后）
＋ **中庸度四指标**（交集率 / 边际利用率 / 中庸距离 / 覆盖饱和度）
＋ **动作演化读数**（动作档案从 0 长到几个、失败类型分布）
＋ **行为格数**（探索了几种东西）

## 成本
被测与测量**都用 MiniMax 订阅（$0）**。被测 `MiniMax-M3.1-Flash-Preview`。
⇒ ⚠️ 判官与被测**同厂商** ⇒ `judge_same_vendor=true` ⇒ 读数**只能用于内部对照**，
   **不能**作为对外结论（协议 §4.3 的跨厂商要求）。

## 纪律
* **失败不许静默变 0**：每臂的 `parsefail_rate`、`n_load_bearing`、调用数全部落盘。
* **不重跑到好看**：跑几次就是几次，invalid 也如实报。
* **密钥只从环境读**，不写进任何文件。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 复用既有的真实客户端与测量流水线（**不重写**）
BATCH_U1 = "/workspace/lab/batch-U1"
sys.path.insert(0, BATCH_U1)

import u1_lib as U            # noqa: E402
import measure as M           # noqa: E402
import workflow as W          # noqa: E402

DEV = "/workspace/lab/routes/DEV"
OUT = os.path.join(HERE, "runs")


# ══════════════════════════════════════════════════════════════════════
# 工具
# ══════════════════════════════════════════════════════════════════════
def load_tasks(n=None):
    with open(os.path.join(DEV, "devset.json"), encoding="utf-8") as f:
        d = json.load(f)
    tasks = d["tasks"] if isinstance(d, dict) and "tasks" in d else d
    return tasks[:n] if n else tasks


def ev_items(task):
    return [{"id": e["id"], "text": e["text"]} for e in task.get("evidence") or []]


def ct_text(task):
    """结论空间给判官的文本（**编号即结论编号**）。"""
    cs = task.get("conclusion_space") or []
    return "\n".join("%d. [%s] %s" % (i + 1, c.get("id", ""), c.get("text", ""))
                     for i, c in enumerate(cs))


def measure_one(llm, task, answer, answer_id):
    """用协议判官把一份答案折成**承重卡片**（沿用 batch-U1 的 `measure_answer`）。"""
    res = M.measure_answer(llm, task["ask"], ev_items(task), ct_text(task),
                           answer, answer_id)
    cards = []
    for i, c in enumerate(res.get("cards_all") or []):
        v = c.get("verdict")
        st = {"支持": "supported", "矛盾": "contradicted",
              "未提及": "unmentioned", "非主张": "unverifiable"}.get(v, "unverifiable")
        cards.append(dict(
            card_id="%s#%d" % (answer_id, i),
            claim=c.get("claim"),
            verify_status=st,
            verdict=v,
            load_bearing=bool(c.get("load_bearing")),
            # ⚠️ int → 结论 id（`family_key` 要字符串，否则 join 报 TypeError）
            supports_conclusions=["C%d" % int(x) for x in (c.get("supports_conclusions") or [])],
            stage="final",
        ))
    return res, cards


def dims_from_cards(cards):
    """承重维度数 = 去冗余后的**不同结论族**数（与生产读数同口径：`family_key`）。"""
    fams = set()
    for c in cards:
        if c.get("load_bearing") and c.get("verify_status") == "supported" \
                and c.get("supports_conclusions"):
            fams.add("|".join(sorted(c["supports_conclusions"])))
    return fams


def claims_text(cards):
    return [c.get("claim") or "" for c in cards]


# ══════════════════════════════════════════════════════════════════════
# 两条臂
# ══════════════════════════════════════════════════════════════════════
def arm_direct(llm, task, model):
    """直调基线：一次调用。**没有帧、没有演化、没有汇总。**"""
    prompt = "问题：%s\n\n%s" % (task["ask"], W._OUT_SPEC)
    out = W._chat(llm, prompt, purpose="B0_direct", model=model, temp=0.7,
                  max_tokens=2000, min_ok=20)
    return dict(answer=out or "", claims=W._extract_claims(llm, out, model=model),
                ops=["GEN[direct]"], frames=[], archive={}, failures={}, illum={})


def arm_workflow(llm, task, model, seed=0, n_slots=4, max_rounds=2):
    wf = W.CollapseFixWorkflow(llm, n_slots=n_slots, seed=seed,
                                model=model, judge_model=model,
                                max_rounds=max_rounds)
    r = wf.run(task["ask"])
    return dict(answer=r["answer"], claims=r["claims"], ops=r["ops"],
                frames=r["frames"], archive=r["archive"], failures=r["failures"],
                illum=r["illum"], rounds=r["rounds"])


# ══════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=3, help="跑前 N 道 DEV 题")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--slots", type=int, default=4)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--dry", action="store_true", help="只跑不落盘")
    args = ap.parse_args()

    tasks = load_tasks(args.tasks)
    model = os.environ.get("MM_MODEL", "MiniMax-M3.1-Flash-Preview")
    llm = U.MiniMaxLLM()
    print("模型：%s ｜ 题数：%d ｜ rep：%d" % (model, len(tasks), args.reps))
    print("=" * 74)

    all_rows = []
    t0 = time.time()
    for ti, task in enumerate(tasks):
        for rep in range(1, args.reps + 1):
            row = dict(task_id=task["task_id"], rep=rep, arms={})
            for arm_name, fn in (("B0_direct", lambda: arm_direct(llm, task, model)),
                                 ("W_collapse", lambda: arm_workflow(
                                     llm, task, model, seed=rep, n_slots=args.slots,
                                     max_rounds=args.rounds))):
                c0 = llm.n_api_calls
                try:
                    a = fn()
                    res, cards = measure_one(llm, task, a["answer"],
                                             "%s/%s/rep%d" % (arm_name, task["task_id"], rep))
                    fams = dims_from_cards(cards)
                    row["arms"][arm_name] = dict(
                        answer=a["answer"], n_chars=len(a["answer"]),
                        claims=a["claims"],
                        n_cards=len(cards),
                        n_load_bearing=sum(1 for c in cards if c["load_bearing"]),
                        n_dims=len(fams),
                        dims=sorted(fams),
                        parsefail_rate=res.get("parsefail_rate"),
                        cards=cards,
                        ops=a.get("ops"), frames=a.get("frames"),
                        archive=a.get("archive"), failures=a.get("failures"),
                        illum=a.get("illum"),
                        rounds=a.get("rounds"),
                        calls=llm.n_api_calls - c0,
                    )
                except Exception as e:
                    row["arms"][arm_name] = dict(error="%s: %s" % (type(e).__name__, e))
                print("  %-4s %-11s dims=%-3s lb=%-3s calls=%-3s %s"
                      % (task["task_id"], arm_name,
                         row["arms"][arm_name].get("n_dims", "-"),
                         row["arms"][arm_name].get("n_load_bearing", "-"),
                         row["arms"][arm_name].get("calls", "-"),
                         row["arms"][arm_name].get("error", "")))
            all_rows.append(row)
            print("  " + "-" * 70)

    # ── 汇总读数
    summary = dict(
        model=model, judge_same_vendor=True,
        note=("判官与被测**同厂商**（MiniMax）⇒ 内部对照用；"
              "**不能**作为对外结论（协议 §4.3 要求跨厂商判官）"),
        n_tasks=len(tasks), reps=args.reps, slots=args.slots, rounds=args.rounds,
        secs=round(time.time() - t0, 1), total_calls=llm.n_api_calls,
        arms={}, rows=all_rows,
    )
    for arm in ("B0_direct", "W_collapse"):
        dims, lbs, pf = [], [], []
        for row in all_rows:
            a = row["arms"].get(arm) or {}
            if "error" in a:
                continue
            dims.append(a.get("n_dims") or 0)
            lbs.append(a.get("n_load_bearing") or 0)
            pf.append(a.get("parsefail_rate") or 0.0)
        summary["arms"][arm] = dict(
            n=len(dims), dims=dims, mean_dims=(sum(dims) / len(dims)) if dims else 0,
            mean_load_bearing=(sum(lbs) / len(lbs)) if lbs else 0,
            mean_parsefail=(sum(pf) / len(pf)) if pf else 0,
        )

    # ── 中庸度（跨臂，按题）
    common_rates = []
    for row in all_rows:
        arms = row["arms"]
        if "error" in arms.get("B0_direct", {}) or "error" in arms.get("W_collapse", {}):
            continue
        common_rates.append(W.common_rate([
            [c.get("claim") or "" for c in arms["B0_direct"]["cards"]],
            [c.get("claim") or "" for c in arms["W_collapse"]["cards"]],
        ]))
    summary["medianity"] = dict(
        common_rate_across_arms=common_rates,
        mean_common_rate=(sum(common_rates) / len(common_rates)) if common_rates else 0.0,
    )

    # ── 动作演化读数
    evo = []
    for row in all_rows:
        a = row["arms"].get("W_collapse") or {}
        if "error" in a:
            continue
        evo.append(dict(task_id=row["task_id"],
                        n_actions=(a.get("archive") or {}).get("n_actions", 0),
                        actions=(a.get("archive") or {}).get("names", []),
                        failures=a.get("failures") or {},
                        n_cells=(a.get("illum") or {}).get("n_cells", 0)))
    summary["evolution"] = evo

    print("=" * 74)
    for arm, s in summary["arms"].items():
        print("  %-11s n=%d  平均维度数=%.2f  平均承重卡=%.2f  平均解析失败率=%.3f"
              % (arm, s["n"], s["mean_dims"], s["mean_load_bearing"], s["mean_parsefail"]))
    print("  跨臂交集率均值=%.3f" % summary["medianity"]["mean_common_rate"])
    print("  动作演化：%s" % json.dumps(evo, ensure_ascii=False))
    print("  总调用 %d 次 ／ %.1f 秒" % (summary["total_calls"], summary["secs"]))
    print("=" * 74)

    if not args.dry:
        os.makedirs(args.out, exist_ok=True)
        path = os.path.join(args.out, "w_dev_run.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)
        print("  落盘：%s" % path)


if __name__ == "__main__":
    main()
