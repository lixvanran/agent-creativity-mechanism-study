#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **钻牛角尖率**检测器（零判官、纯文本、可机械复算）

> 2026-10-24 ｜ 配套 `DEV/DEV-ADV-2026-10-24.json`（诱导钻牛角尖型理科题集）

## 为什么需要它
我们的核心问题是「搜索空间过早闭合」。要证明**架构治好了它**，就得能**机械地**判定
"这一次 Agent 是否钻了牛角尖"⇒ ⇒ 不能靠人看 ⇒ ⇒ 于是给每道题配一组**陷阱指纹**。

## ★ 关键设计：指纹必须是**带断言上下文的正则**，不是纯字符串
纯字符串会**误报**：正确推理**经常引用那个错数字当前提**
（例：正确答案"一瓶蛋白质 1.5 g"的推理里必然出现"每 100 mL 是 0.3 g"）
⇒ ⇒ 所以只匹配**断言位置**的错值（"为/是/＝/=" + 错值）⇒ ⇒ 引理里的数字不算踩坑。

## 判定
```
premature_closure(task, answer_text) -> dict(
    hit: bool,                  # 是否踩了坑
    matched: [命中的指纹...],
    n_fingerprints: int,
)
```
⇒ 逐份答案算 ⇒ **钻牛角尖率 = 命中份数 / 有效份数**（**必报绝对分母**）。

## 纪律
* **失败不许静默**：解析不出题 ⇒ 该题**不计入**分母，且必须报 `n_skipped`
* 只在**同一题内**比不同臂 ⇒ 不跨题聚合
* 这是**机制属性**（不是效果属性）⇒ 与"承重维度数"**分开报**
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

ADV_PATH = os.environ.get(
    "ADV_DEVSET",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "DEV",
                 "DEV-ADV-2026-10-24.json"))


def load_tasks(path: Optional[str] = None) -> List[Dict[str, Any]]:
    p = path or ADV_PATH
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    return d["tasks"] if isinstance(d, dict) and "tasks" in d else d


# ★ 断言上下文：错值必须出现在"为/是/＝/="之后
_ASSERT = r"(?:为|是|＝|=|应为|等于)\s*"
# 数值的可选单位/空格
_NUM = r"\s*(?:g|mg|kg|kJ|A|W|mm|℃|%|个|份|月|天|日|次)?"


def build_regexes(task: Dict[str, Any]) -> List[str]:
    """从任务里的 `trap_fingerprints` 生成带断言上下文的正则。

    ★ 每条指纹可以是：
      · 普通字符串（如 "5 A"）⇒ 自动补断言上下文
      · 已含 `(?` 的正则片段（如 "±0\\.005"）⇒ **原样使用**（自行带上下文）
    """
    out = []
    for fp in (task.get("trap_fingerprints") or []):
        if "(?" in fp:
            out.append(fp)
        else:
            esc = re.escape(fp.strip())
            out.append(_ASSERT + esc)
    return out


def premature_closure(task: Dict[str, Any], answer_text: str) -> Dict[str, Any]:
    """判定一份答案是否踩了坑（纯文本、零判官）。"""
    txt = answer_text or ""
    pats = build_regexes(task)
    matched = []
    for p in pats:
        try:
            if re.search(p, txt):
                matched.append(p)
        except re.error:
            # 坏正则不许静默跳过 ⇒ 记下来
            matched.append("__BADREGEX__:" + p[:40])
    return dict(task_id=task.get("task_id"),
                hit=bool([m for m in matched if not m.startswith("__BADREGEX__")]),
                matched=matched,
                n_fingerprints=len(pats),
                n_chars=len(txt))


def rate_over(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """跨臂汇总钻牛角尖率（**必报绝对分母**）。"""
    by = {}
    for r in records:
        a = r.get("arm")
        by.setdefault(a, []).append(r)
    out = {}
    for a, rs in by.items():
        valid = [x for x in rs if x.get("hit") is not None]
        hits = [x for x in valid if x.get("hit")]
        out[a] = dict(n_total=len(rs), n_valid=len(valid),
                      n_hit=len(hits),
                      rate=(len(hits) / float(len(valid))) if valid else None,
                      n_skipped=len(rs) - len(valid))
    return out


if __name__ == "__main__":
    tasks = load_tasks()
    print("诱导钻牛角尖题集：%d 题" % len(tasks))
    for t in tasks:
        rs = build_regexes(t)
        print("  %-4s %-22s 指纹 %d 条：%s" % (
            t["task_id"], t["title"][:22], len(rs), rs[:2]))
