#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最后一批文档修订（2026-10-20 19:45）—— 独立脚本，不与其它 patch 脚本耦合。

内容：
  ① 判官 temperature 0.0（矛盾率是确定量）
  ② 遍2 复用遍1 的判官结果（成本闸门 + 报告必须写明）
  ③ 坑 29：判官自检"单次通过"是运气，不是保证
  ④ METHOD §7 补 3b：判官结果在遍1/遍2 之间复用

用法：python3 patch_docs_final.py <要改的 md 路径 ...>
每条规则都**逐条报结果**（应用了 / 已在 / 锚点未命中）—— 不静默假装成功。
"""
import io
import os
import sys

ROW29 = (
    "| 29 | ★★★ **判官自检\"单次通过\"是运气，不是保证** | 判官调用原本在 **temperature 1.0** 下跑 ⇒ "
    "自检结果**带采样噪声** ⇒ 同一模型同一自检集，一次 4/4+4/4 ✅、另一次 3/5+2/5 ❌ | "
    "**判官调用必须 `temperature=0`**（`orclient.chat` 默认 temp=0）；自检作为闸门时**要求可复现**"
    "（temp=0 后连跑 2 次结果一致）。⚠️ 更深一层：**判官在 temp>0 ⇒ 矛盾率不是确定量** ⇒"
    "「种子噪声地板」只测了**被测侧**、**没测判官侧** ⇒ 臂间比较的噪声来源要写清楚 |"
)

# (适用文件, 幂等标记, old, new, 说明)
RULES = [
 ("HANDOVER", "temperature 0.0",
  "- 判官自检（2026-10-20 18:15 演练复核）：**grok-4.3 5/5 + 5/5（fn=0 fp=0）✅**；deepseek **2/5**（两次都不稳）❌",
  "- 判官自检（2026-10-20 18:15 演练复核）：**grok-4.3 5/5 + 5/5（fn=0 fp=0，temp=0 下连跑两次一致）✅**；deepseek **2/5**（两次都不稳）❌\n"
  "- ⚠️ **判官在 temperature 0.0 下运行**（`orclient.chat` 默认 temp=0）⇒ **矛盾率是确定量**。\n"
  "- ⚠️ **遍2 复用遍1 的判官结果**（`judge_cache.json`；两遍唯一变量是 embedding 通道）⇒ 判官成本只付一遍。\n"
  "  ⇒ **报告里必须写明这两条**，否则读报告的人会以为判官带采样噪声、两遍各自独立判过。",
  "判官 temp=0 / 遍2 复用"),

 ("METHOD", "3b. 判官结果在遍1",
  "> 判官 `x-ai/grok-4.3`：真 5/5 ｜ 假 5/5 ✅（2026-10-20 18:15 演练复核）",
  "> 判官 `x-ai/grok-4.3`：真 5/5 ｜ 假 5/5 ✅（2026-10-20 18:15 演练复核，**temp=0 下连跑两次一致**）\n"
  ">\n"
  "> **3b. 判官结果在遍1 / 遍2 之间复用**（`judge_cache.json`）：遍2 的唯一变量是 **embedding 通道**\n"
  "> ⇒ 判官 verdict 是**同一个量**，不该重算（重算 = 判官成本付两遍 ⇒ 破 $1 上限）。\n"
  "> ⇒ `analysis.json` 的 `judge_reused=true` 记录了这一点，**报告里必须写明**，\n"
  "> 否则读者会以为两遍各自独立判了一遍。\n"
  "> ⇒ 附带：判官在 **temperature 0.0** 下运行 ⇒ 矛盾率是确定量\n"
  "> （temp>0 时自检带采样噪声：同一模型同一自检集一次 4/4 一次 2/5）",
  "METHOD §7 补 3b（判官结果复用）"),
]




def apply(path):
    name = os.path.basename(path)
    s = io.open(path, encoding="utf-8").read()
    orig = s
    for who, mark, old, new, desc in RULES:
        if who not in name:
            continue
        if mark in s:
            print("  · %s：%s（已在）" % (name, desc))
            continue
        if old not in s:
            print("  ✗ %s：%s —— 锚点未命中" % (name, desc))
            continue
        s = s.replace(old, new, 1)
        print("  ✓ %s：%s" % (name, desc))
    # 坑 29：行级插入（不靠长行转写）
    if "HANDOVER" in name and "| 29 | ★★★ **判官自检" not in s:
        lines = s.split("\n")
        for i, l in enumerate(lines):
            if l.startswith("| 28 |"):
                lines.insert(i + 1, ROW29)
                s = "\n".join(lines)
                print("  ✓ %s：坑 29（行级插入）" % name)
                break
        else:
            print("  ✗ %s：坑 29 —— 找不到 | 28 | 行" % name)
    if s != orig:
        io.open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    for p in (sys.argv[1:] or ["HANDOVER-cmp8-2026-10-20.md", "METHOD.md"]):
        print("patch_docs_final:", p)
        apply(p)
    print("done")
