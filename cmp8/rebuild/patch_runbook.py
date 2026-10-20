#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AGENT_RUNBOOK.md 的两处补丁（唯一真相源，幂等）。

用法：python3 patch_runbook.py <AGENT_RUNBOOK.md 路径>

改动 1：判读规则段末尾追加「★ 判官解析失败率」
        （分析器已输出这张表 ⇒ 手册必须教本地 Agent 怎么看，否则要么忽略要么误读）
改动 2：阶段 5 回报清单第 7/8/9 条 → 7/8/9/10（补上「判官解析失败率」表这一项）
"""
import io
import sys

SEC = """
### ★ 判官解析失败率（分析器会打这张表，**必须看**）

判定失败的断言**既不进分子也不进分母**（这是对的：不把"读不懂"当成"说对了"）。
**但失败条数必须报出来** ⇒ 分析器会输出「判官解析失败率」表。

| 解析失败率 | 判读与动作 |
|---|---|
| ≤ 10% | 正常 |
| > 10% | ⚠️ **该臂的矛盾率是在"悄悄缩小后的分母"上算的** ⇒ 表上看不出来，但臂间**不可比**。**不要重跑掩盖它**，把它标出来一起报 |

⚠️ **不许因为失败率高就重跑**——那是把仪器故障当成实验结论。
正确动作是：**报失败率 + 标注该臂矛盾率不可比**。
"""

ANCHOR1 = '''  宽度轴废了也能用它撑住"谁覆盖得更多"。
'''
ANCHOR2 = '''7. 两遍分析的 `n_raw` / `width` / 保留率对比
8. 判读页路径
9. **没跑完/哪几个臂挂了 ⇒ 照实说**
'''
NEW2 = '''7. 两遍分析的 `n_raw` / `width` / 保留率对比
8. **「判官解析失败率」表**（逐臂 `n_parsefail` / `parsefail_rate`）
9. 判读页路径
10. **没跑完/哪几个臂挂了 ⇒ 照实说**
'''


def patch(path):
    s = io.open(path, encoding="utf-8").read()
    orig = s

    # 改动 1
    if "★ 判官解析失败率" not in s:
        if ANCHOR1 not in s:
            raise SystemExit("✗ 锚点 1 未命中：%s" % path)
        s = s.replace(ANCHOR1, ANCHOR1 + SEC, 1)
        print("  ✓ 改动 1：判读规则段追加「判官解析失败率」")
    else:
        print("  · 改动 1 已在，跳过")

    # 改动 2
    if "**「判官解析失败率」表**" not in s:
        if ANCHOR2 not in s:
            raise SystemExit("✗ 锚点 2 未命中：%s" % path)
        s = s.replace(ANCHOR2, NEW2, 1)
        print("  ✓ 改动 2：阶段 5 回报清单补第 8 项")
    else:
        print("  · 改动 2 已在，跳过")

    if s != orig:
        io.open(path, "w", encoding="utf-8").write(s)
    return s != orig


if __name__ == "__main__":
    for p in (sys.argv[1:] or ["AGENT_RUNBOOK.md"]):
        print("patch_runbook:", p)
        patch(p)
    print("done")
