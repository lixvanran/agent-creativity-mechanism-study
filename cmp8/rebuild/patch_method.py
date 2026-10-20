#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""METHOD.md 的两处补丁（唯一真相源，幂等）。

用法：python3 patch_method.py <METHOD.md 路径>

B1 §6 耗时：改成实测值（≈3.5–4 小时，A5 三臂偏慢是主要来源）
B2 §4.3 新增：矛盾率在"分母为 0"时的读法
   —— 这是**关系到结论对错**的一条：分析器里 conflict = con / max(len(legal), 1)，
   当某份答案一条可核验断言都没抽出来时 conflict = 0.0（不是 NaN、不是"无数据"），
   会以「零矛盾 = 完美」的样子进入臂内均值。**这是仪器故障的外观，不是优点。**
"""
import io
import sys

OLD1 = """**耗时**：跑批 1.5–2 小时（`--workers 4`）。"""
NEW1 = """**耗时**：跑批 **实测 ≈3.5–4 小时**（`--workers 4`；≈800 次调用 × ~33 s ÷ 4 并发，
**A5 三臂偏慢，实测 491–734 s/臂样本** ⇒ 是总时长的主要来源）。"""

OLD2 = """### 4.2 模型的"自我重复"
模型在**一份**答案里会把同一事实说 3–4 遍。
⇒ **任何按断言条数算的量都必须先去重**；不去重的话，"啰嗦"会被读成"覆盖广"。
"""

NEW2 = """### 4.2 模型的"自我重复"
模型在**一份**答案里会把同一事实说 3–4 遍。
⇒ **任何按断言条数算的量都必须先去重**；不去重的话，"啰嗦"会被读成"覆盖广"。

### 4.3 ⚠️ 矛盾率在"分母为 0"时的读法（**会被误读成完美结果**）

分析器里矛盾率算的是：

```python
conflict = con / max(len(legal), 1)     # legal = 支持 + 矛盾
```

⇒ **当某份答案一条可核验断言都没抽出来时**（`支持+矛盾 = 0`），
`conflict` = **0.0**（**不是 NaN、不是"无数据"**）
⇒ 这个 0.0 会以「**零矛盾 = 完美**」的样子进入臂内均值。

**这不是优点，是仪器故障的外观。** 同族的问题还有：
- 「太短的产出以 conflict=0 进均值」
- 「判官整个坏掉 ⇒ 所有断言解析失败 ⇒ 0/0 = 0」

**⇒ 判读时必须做三件事**：
1. **看 `n_raw`**：某臂 `n_raw` 接近 0（甚至 < 5）⇒ 它的矛盾率是**没有信息**，不是"很好"。
   分析器有 `n_raw<5` 体检，**必须看那张表**。
2. **看 `samples`（valid/total）**：产出 < 50 字的样本已被闸门排除，**排除数要如实报**。
3. **看解析失败率**：`parsefail_rate > 10%` 的臂，其矛盾率的分母被悄悄缩小 ⇒ **臂间不可比**。

**⇒ 一句话**：**矛盾率低只有在一个臂真的说对了很多话时才是好消息。**
**「矛盾率 0 + `n_raw` 很小 + 解析失败率高」= 仪器坏了，长得像赢家。**
"""


def patch(path):
    s = io.open(path, encoding="utf-8").read()
    orig = s

    if "实测 ≈3.5–4 小时" not in s:
        if OLD1 not in s:
            raise SystemExit("✗ 锚点 1 未命中：%s" % path)
        s = s.replace(OLD1, NEW1, 1)
        print("  ✓ B1：§6 耗时改实测值")
    else:
        print("  · B1 已在，跳过")

    if "矛盾率在\"分母为 0\"时的读法" not in s:
        if OLD2 not in s:
            raise SystemExit("✗ 锚点 2 未命中：%s" % path)
        s = s.replace(OLD2, NEW2, 1)
        print("  ✓ B2：新增 §4.3 矛盾率分母为 0 的读法")
    else:
        print("  · B2 已在，跳过")

    if s != orig:
        io.open(path, "w", encoding="utf-8").write(s)
    return s != orig


if __name__ == "__main__":
    for p in (sys.argv[1:] or ["METHOD.md"]):
        print("patch_method:", p)
        patch(p)
    print("done")
