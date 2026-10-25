# -*- coding: utf-8 -*-
"""DEV 生成器（第二组自用）—— 给 `VD_anchor_out` / 跨判官实验提供**真实**答案。

> 2026-10-22 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/dev_gen.py`
> ⚠️ **不碰** `routes/COLLAPSE/workflow.py`、**不碰** `routes/DEV/`、**不碰**共享跑批。
> ⇒ 本文件是**第二组自己的、独立的一条生成侧**，只用于 DEV 集的方法学验证。

## 两条臂（只差**架构**，输入完全相同）

| 臂 | 架构 | 输出形态 |
|---|---|---|
| `B0_direct` | **1 次**直接调用 | 自由文本（模型自定结构）|
| `W_div` | **3 次**独立视角 + **1 次**机械装配（不汇总、不让模型改写） | `- [EV-xx] 断言` 列表，**代码级 400 字上限** |

⚠️ **两条臂的输出格式不同**（这是**已知混淆项**，不是 bug）⇒
跨臂比较必须配 `audit_format_symmetry.py` 的读数一起看。
⇒ 本文件把两条臂的**结构统计**一并落盘，让格式贡献可见。

## 成本

被测侧 = OpenRouter（跨厂商）｜判官侧 = MiniMax 订阅 ⇒ `judge_same_vendor = false`。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import vd_anchor_out as V  # noqa: E402

# ── 三个视角（"人为设计"的一组先验；层2 的典型做法）──────────────────
ANGLES = [
    ("risk", "【视角】风险与失败模式：先想这件事会**在哪儿崩**、崩了会怎样、谁承担后果。"),
    ("ops", "【视角】日常运行：先想**每天/每周**要做什么、要盯什么、什么会过期。"),
    ("tradeoff", "【视角】取舍与成本：先想**代价落在谁头上**、换来的收益是什么、能不能便宜点做。"),
]

OUT_SPEC = ("【输出规格】\n"
            "- 只输出 3–6 条，每条一行，行首用「- 」\n"
            "- 每条必须**具体**：带一个数字 / 一个明确条件 / 一个可核查的判断\n"
            "- 每条行首写「- [EV-xx] 」，xx 是你引用的依据条目编号（自生信息写「- 」不带编号）\n"
            "- 不写开场白、不写总结、不写免责说明\n"
            "- 不超过 400 字")

DIRECT_SPEC = ("请直接回答下面的问题。给出可核查的结论，必要时引用依据条目编号（如 EV-03）。"
               "不要写开场白和总结。")


def build_prompts(task: Dict[str, Any]) -> Dict[str, Any]:
    ev = V.evidence_items_from_dev(task)
    ev_text = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev))
    ct_text = "\n".join("%s. %s" % (c["id"], c["text"]) for c in V.ct_of_dev(task))
    return {"ev": ev, "ev_text": ev_text, "ct_text": ct_text, "ask": task.get("ask", "")}


def gen_direct_noev(llm: V.LLM, task: Dict[str, Any], model: str) -> Dict[str, Any]:
    """**不给依据包**的直调臂 ⇒ 唯一变量 = "任务表示是否把空间写死"。

    ★ 用途：检验层1 假说 H6（可枚举任务表示 ⇒ 生成侧被锁在清单里）。
      若 `VD_anchor_out` 在这一臂上显著高于"给了依据包"的臂
      ⇒ **我们的"锚外发现"能力是被任务表示卡住的，不是模型没有**。
    """
    prompt = ("问题：\n%s\n\n%s" % (task.get("ask", ""), DIRECT_SPEC))
    txt = llm.chat(prompt, model=model, temp=0.7, max_tokens=8000,
                   budgets=(12000,), min_ok=20, purpose="gen_direct_noev")
    return {"answer": txt or "", "n_calls": 1, "arm": "B0_noev"}


def gen_direct(llm: V.LLM, task: Dict[str, Any], model: str) -> Dict[str, Any]:
    p = build_prompts(task)
    prompt = ("问题：\n%s\n\n依据条目：\n%s\n\n%s"
              % (p["ask"], p["ev_text"], DIRECT_SPEC))
    txt = llm.chat(prompt, model=model, temp=0.7, max_tokens=8000,
                   budgets=(12000,), min_ok=20, purpose="gen_direct")
    return {"answer": txt or "", "n_calls": 1, "arm": "B0_direct"}


def gen_wdiv(llm: V.LLM, task: Dict[str, Any], model: str) -> Dict[str, Any]:
    p = build_prompts(task)
    drafts: List[str] = []
    for _, head in ANGLES:
        prompt = ("问题：\n%s\n\n依据条目：\n%s\n\n%s\n\n%s"
                  % (p["ask"], p["ev_text"], head, OUT_SPEC))
        d = llm.chat(prompt, model=model, temp=0.7, max_tokens=8000,
                     budgets=(12000,), min_ok=20, purpose="gen_angle")
        drafts.append(d or "")
    # 机械装配：代码级 400 字上限；**不让模型改写**
    lines: List[str] = []
    used = 0
    cap = 400
    for d in drafts:
        for ln in (d or "").splitlines():
            ln = ln.strip()
            if not ln.startswith("-"):
                continue
            item = ln if len(ln) <= 120 else ln[:120]
            if used + len(item) + 1 > cap:
                continue
            lines.append(item)
            used += len(item) + 1
    body = "\n".join(lines) if lines else "- （无）"
    return {"answer": body, "n_calls": len(ANGLES), "arm": "W_div",
            "n_items": len(lines), "n_chars": len(body), "drafts": drafts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="D01,D05,D08")
    ap.add_argument("--dev", default=V.DEV_DIR)
    ap.add_argument("--model", default="x-ai/grok-4.3")
    ap.add_argument("--vendor", default="openrouter")
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "dev"))
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--only", default="", help="逗号分隔的臂名（默认全部）")
    args = ap.parse_args(argv)

    devset = V.load_devset(args.dev)
    tasks = [V.dev_task(devset, t) for t in args.tasks.split(",") if t.strip()]
    os.makedirs(args.out, exist_ok=True)
    llm = V.LLM(args.vendor, args.model)
    manifest: List[Dict[str, Any]] = []

    def one(task: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = []
        arms = [("B0_direct", gen_direct), ("W_div", gen_wdiv)]
        if os.environ.get("VD_INCLUDE_NOEV", "1") == "1":
            arms.append(("B0_noev", gen_direct_noev))
        for arm, fn in arms:
            if args.only and arm not in args.only.split(","):
                continue
            r = fn(llm, task, args.model)
            d = os.path.join(args.out, arm)
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, "%s.answer.md" % task["task_id"])
            with open(path, "w", encoding="utf-8") as f:
                f.write(r["answer"])
            meta = {k: v for k, v in r.items() if k != "answer"}
            meta.update(task_id=task["task_id"], arm=arm, model=args.model,
                        n_chars=len(r["answer"]), answer_file=path)
            with open(os.path.join(d, "%s.meta.json" % task["task_id"]), "w",
                      encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            rows.append({"answer_id": "%s#%s" % (arm, task["task_id"]),
                         "task_id": task["task_id"], "arm": arm, "answer_file": path})
            print("[gen] %-28s %5d 字  %d 次调用" % (rows[-1]["answer_id"],
                                                      len(r["answer"]), r["n_calls"]))
        return rows

    with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        for rows in ex.map(one, tasks):
            manifest.extend(rows)

    mp = os.path.join(args.out, "manifest.json")
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("\n✓ 答案落盘 %s（%d 份）｜manifest: %s"
          % (args.out, len(manifest), mp))
    print("✓ 调用账本：", json.dumps(llm.log.summary(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
