# -*- coding: utf-8 -*-
"""等预算的 $ 轴（B-2e）—— 把 best-of-k 的对齐轴从"节点数"换成"钱"。

> 2026-10-22 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/budget_axis.py`
> 依据：协议 §4.4（等预算对照：等调用数 / 等 token；**选择规则必须与内容无关**）、
#      §3.3 F6（未提供等预算对照 ⇒ 该臂结果不可归因于架构）、
#      `routes/COLLAPSE-REMEDY-2026-10-22.md` §三-1（ToT：CoT best-of-100 **49%** vs ToT b=5 **74%**）
>      与 §六 否证条件 ③（"同预算 best-of-k 后增益消失 ⇒ 增益由采样次数解释"）

## 为什么轴必须换成 $

ToT 那个对比（best-of-100 49% vs b=5 74%）用的是**节点数**。节点数在**成本上不等价**：
一次"节点"可能是一次 200 token 的扩展，也可能是一次 4000 token 的自我反思；
**同样 5 个节点，两条路线的账单可以差一个数量级**。

⇒ 我们要回答的是："**我们多花的那些钱，能不能自己买到同样的增益？**"
⇒ 所以对齐轴必须是**可计价的单位**，而不是**结构单位**。

## 成本口径（不许拍脑袋）

```
cost_usd = prompt_tokens/1e6 * price_prompt + completion_tokens/1e6 * price_completion
```
- 价目表来源：OpenRouter `GET /api/v1/models` 的 `pricing` 字段（**访问日期 2026-10-22**），
  代码内 `PRICE_TABLE` 里逐条记了来源与日期。
- **MiniMax 订阅侧 = $0**（协议 §4.8）⇒ 判官/抽取侧不计入被测成本，
  但**必须单列**（`cost_judge_usd = 0` 也要写出来，不能不写）。
- ⚠️ **同一模型在不同时间的价格会变** ⇒ 任何成本比较**必须带 `price_table_date`**。
  跨批次比成本前先核对价目表日期。

## 三条对齐线的关系（不要混用）

| 线 | 对齐什么 | 我们的实现 |
|---|---|---|
| **等调用数** | `n_calls` | 协议 §4.4 的 B1（K 次内部采样，取第 K 份）|
| **等 token** | `n_tokens` | 协议 §4.4 的 B2（采到 token 预算为止，取最后一份）|
| **等 $（本文件）** | `cost_usd` | `budget_axis.py`：给定目标预算，反解**能买几个候选**，再选一个 |

⇒ ★ **等 $ 是最严的一条**（它同时约束了 calls 与 tokens 的组合）⇒
**它是"增益是不是只是因为多花了钱"的最终检验**。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

# ── 价目表（USD / 每 1M token）｜来源：OpenRouter `GET /api/v1/models` 的 `pricing`
#    访问日期 2026-10-22；**跨批次比成本前必须核对日期**
PRICE_TABLE: Dict[str, Dict[str, float]] = {
    "x-ai/grok-4.3": {"prompt": 1.25, "completion": 2.50},
    "openai/gpt-4.1-mini": {"prompt": 0.40, "completion": 1.60},
    "google/gemini-2.5-flash": {"prompt": 0.30, "completion": 2.50},
    "deepseek/deepseek-chat": {"prompt": 0.2574, "completion": 1.0287},
}
#: MiniMax 订阅侧：**$0**（协议 §4.8）⇒ 仍然要写进报表（不许不写）
FREE_VENDORS = {"minimax"}
PRICE_TABLE_DATE = "2026-10-22"
PRICE_TABLE_SOURCE = "OpenRouter GET /api/v1/models → pricing"


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int,
             vendor: str = "openrouter") -> Dict[str, Any]:
    """返回该次调用的成本（USD）与价目表身份。**价目表里没有的型号 ⇒ 显式报错，
    不许静默当 0**（否则"贵的模型看起来免费"）。"""
    if vendor in FREE_VENDORS:
        return {"cost_usd": 0.0, "price_source": "subscription($0)",
                "price_table_date": PRICE_TABLE_DATE}
    if model not in PRICE_TABLE:
        raise KeyError("价目表里没有 %s（访问日期 %s）⇒ 补价目表，不许当 0 处理"
                       % (model, PRICE_TABLE_DATE))
    p = PRICE_TABLE[model]
    c = (prompt_tokens / 1e6) * p["prompt"] + (completion_tokens / 1e6) * p["completion"]
    return {"cost_usd": round(c, 8), "price_source": PRICE_TABLE_SOURCE,
            "price_table_date": PRICE_TABLE_DATE,
            "price_prompt_per_1M": p["prompt"], "price_completion_per_1M": p["completion"]}


def cost_of_log(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从调用账本（`vd_anchor_out.LLM.log.rows` 结构）算一臂的总成本。"""
    tot = 0.0
    per_model: Dict[str, Dict[str, int]] = {}
    for r in rows:
        m = r.get("model", "?")
        v = r.get("vendor", "openrouter")
        d = per_model.setdefault(m, {"prompt_tokens": 0, "completion_tokens": 0, "n_calls": 0})
        d["prompt_tokens"] += int(r.get("prompt_tokens") or 0)
        d["completion_tokens"] += int(r.get("completion_tokens") or 0)
        d["n_calls"] += 1
        c = cost_usd(m, int(r.get("prompt_tokens") or 0),
                     int(r.get("completion_tokens") or 0), v)
        tot += c["cost_usd"]
    return {"cost_usd": round(tot, 8), "per_model": per_model,
            "n_calls": len(rows), "price_table_date": PRICE_TABLE_DATE}


def equal_budget_bestofk(budget_usd: float, per_candidate_usd: float,
                         fixed_usd: float = 0.0) -> Dict[str, Any]:
    """在给定 $ 预算下，最多能买几个候选。

    ⚠️ **选择规则必须与内容无关**：拿到 K 个候选后，协议 §4.4 允许两种取法：
      - 固定取第 K 份（**纯预算对照**，不是 best-of-N）；
      - 由**外部核验器**挑矛盾最少的一份（**B3 强基线**，代价是 K 倍判官成本）。
    ⇒ 两者必须**分别**报告，**不许**用生成臂自评选（自评天然偏好分布中心附近的输出 = 最平庸的候选）。
    """
    if per_candidate_usd <= 0:
        return {"k": None, "note": "单候选成本为 0（订阅侧）⇒ $ 轴无法区分 ⇒ 改用等 token 轴"}
    usable = max(budget_usd - fixed_usd, 0.0)
    k = int(usable // per_candidate_usd)
    return {"budget_usd": round(budget_usd, 8), "fixed_usd": round(fixed_usd, 8),
            "per_candidate_usd": round(per_candidate_usd, 8),
            "k_max": k, "k_max_note": "K = floor((预算 − 固定开销) / 单候选成本)",
            "selection_rules": ["固定取第 K 份（内容无关）",
                                "外部核验器挑矛盾最少（K 倍判官成本）"]}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", help="调用账本 JSON（vd_anchor_out 的 calls.rows）")
    ap.add_argument("--out")
    ap.add_argument("--target-usd", type=float, default=None,
                    help="等预算目标；给了就把能买的候选数算出来")
    args = ap.parse_args(argv)

    if not args.log:
        print(json.dumps({"price_table": PRICE_TABLE, "price_table_date": PRICE_TABLE_DATE,
                          "price_table_source": PRICE_TABLE_SOURCE,
                          "free_vendors": sorted(FREE_VENDORS)}, ensure_ascii=False, indent=2))
        return 0

    rows = json.load(open(args.log, encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("rows", [])
    rep = cost_of_log(rows)
    if args.target_usd is not None:
        n_calls = max(rep["n_calls"], 1)
        per = rep["cost_usd"] / n_calls
        rep["equal_budget"] = equal_budget_bestofk(args.target_usd, per)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
