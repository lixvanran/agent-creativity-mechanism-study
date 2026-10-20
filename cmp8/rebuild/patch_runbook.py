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



# =====================================================================
# 改动 4：第三轮「可执行性」自查 A1–A6（2026-10-20 17:45）
#   核心问题：RUNBOOK 里 `cd cmp8pkg` 出现在 3 处，
#   接收者从 GitHub clone 下来目录叫 `cmp8/` ⇒ 第一步就卡死。
# =====================================================================
EDITS4 = []


def E4(mark, old, new, tag):
    EDITS4.append((mark, old, new, tag))


# A1 阶段 1 整段重写（用「起止标记」区域替换，避开三引号嵌套问题）
def replace_region(text, start_mark, end_mark, new_text):
    i = text.find(start_mark)
    if i < 0:
        raise SystemExit("✗ 改动 4 区域起点未命中：%s" % start_mark[:30])
    j = text.find(end_mark, i)
    if j < 0:
        raise SystemExit("✗ 改动 4 区域终点未命中：%s" % end_mark[:30])
    return text[:i] + new_text + text[j:]


A1_NEW = """## 阶段 1 · 定位实验根目录 + 静态自检

### ⚠️ 第一件事：进对目录（**GitHub 和 zip 的目录名不一样**）

```bash
#  A) GitHub（推荐）：
#     cd agent-creativity-mechanism-study
#     git fetch origin cmp8-handover-2026-10-20 && git checkout cmp8-handover-2026-10-20
#     cd cmp8                      # ★ 目录叫 cmp8
#
#  B) zip（无 git / CA 坏了）：
#     unzip cmp8_交接包.zip
#     cd cmp8pkg                   # ★ 目录叫 cmp8pkg
```

> **⚠️ `rebuild.sh` 只在路径 B 需要。**
> GitHub 树**已经打好补丁**（默认模型已是 `deepseek/deepseek-chat`），再跑 `rebuild.sh`
> 等于用 p0/p1/p2 把整棵树重写一遍（幂等，最后会补回来，但**没必要**）。
> ⇒ **路径 A 直接跳到下面的静态自检**。
>
> 路径 B 的话先跑：`bash rebuild/rebuild.sh`（**别跳**，否则默认模型还是已 404 的 `grok-3-mini`）。

### 静态自检（必须全过再往下）

```bash
for f in $(find . -name "*.py"); do python3 -m py_compile "$f" || echo "COMPILE FAIL: $f"; done
python3 - <<'PY'
import json, sys, os
sys.path.insert(0, 'armdeps')
for i in (1,2,3,4):
    d = json.load(open('creativity_lab/data/user4_q%d.json' % i, encoding='utf-8'))
    assert d['evidence'] and d['ask'], i
    print('依据包 Q%d: evidence %d 字符' % (i, len(d['evidence'])))
w = json.load(open('runs/arch_learn/result.json', encoding='utf-8'))['w']
print('权重 w: %d 维, 范数 %.4f' % (len(w), sum(x*x for x in w)**0.5))
from topics4 import TOPICS4
print('题目:', [t['tid'] for t in TOPICS4])
PY
```

**期望**：无 COMPILE FAIL；4 个依据包；权重 14 维；题目 A1–A4。
**权重范数应该很小（~0.06）——这是正常的**，别以为是文件坏了（见 METHOD §2.5）。
⚠️ **编译过 ≠ 能跑**：`py_compile` 查不出运行时才炸的错（历史坑：漏 `import time` ⇒ 只在异常路径触发）。
⇒ 静态自检过了**还要**跑阶段 2 冒烟。

---

"""

# A2 阶段 0 依赖说明
E4("看到 `import requests` 报错",
   "pip install numpy            # 唯一的第三方依赖（其余全标准库）",
   """pip install numpy            # ★ 唯一的第三方依赖（其余全标准库）

`client.py` / `orclient.py` 用 `urllib.request`（**不用 requests**）；
`creativity_lab/scipy_free.py` 是**刻意避开 scipy** 的实现 ⇒ **不要 pip install scipy**。
看到 `import requests` 报错 = 你改错文件了。""",
   "A2 阶段0 依赖")

# A3 阶段 3
E4("# 已在实验根目录（阶段 1 进对了就别再 cd）",
   "```bash\ncd cmp8pkg\npython3 run_compare5.py",
   "```bash\n# 已在实验根目录（阶段 1 进对了就别再 cd）\npython3 run_compare5.py",
   "A3 阶段3 去 cd")

E4("实测 ≈3.5–4 小时 / 84 份答案",
   "**约 1.5–2 小时 / 84 份答案。**",
   """**实测 ≈3.5–4 小时 / 84 份答案**（≈800 次调用 × ~33 s ÷ 4 并发；
**A5 三臂偏慢，实测 491–734 s/臂样本** ⇒ 是总时长的主要来源）。""",
   "A3 阶段3 耗时")

# A4 阶段 4
E4("判官与被测同源 ⇒ 矛盾率失效 ⇒ 整套作废",
   "```bash\ncd cmp8pkg\n# 遍一：OpenRouter embedding",
   "```bash\n# 已在实验根目录\n# 遍一：OpenRouter embedding",
   "A4 阶段4 去 cd")

E4("**不许悄悄用同源结果。**",
   "  python3 analyze_cmp6.py\n```",
   """```bash\n# 已在实验根目录\npython3 analyze_cmp6.py && python3 build_compare5_page.py
```

⚠️ **遍一如果 OpenRouter 不通，`judge_provider.py` 会自动退到 MiniMax**（并打大字警告）⇒
**判官与被测同源 ⇒ 矛盾率失效 ⇒ 整套作废**。
⇒ **必须检查 `analysis.json` 的 `judge_same_vendor` / `judge_used` / `embed` 三个字段**，
并在回报里声明。**不许悄悄用同源结果。**""",
   "A4 阶段4 同源警告")

# A5 故障排查表加一行
E4("| `cd: cmp8pkg: No such file or directory` |",
   "| 症状 | 大概率原因 | 处理 |",
   """| 症状 | 大概率原因 | 处理 |
| `cd: cmp8pkg: No such file or directory` | **目录名搞错了**（GitHub 的是 `cmp8/`，zip 的是 `cmp8pkg/`） | 回阶段 1，看"进对目录"那段 |""",
   "A5 故障排查行")

# A6 阶段 5 回报清单
E4("`embed` / `census` / **samples**",
   "4. `analysis.json` 的 `judge` / `judge_used` / `judge_same_vendor` / `embed` / `census`",
   "4. `analysis.json` 的 `judge` / `judge_used` / `judge_same_vendor` / `embed` / `census` / **samples**",
   "A6 阶段5 第4项")

E4("4b. **逐臂样本列 `valid/total`**",
   "5. `runlog.jsonl` 里 **A5 三个臂的 `ops` 直方图**",
   """4b. **逐臂样本列 `valid/total`**（哪个臂掉了几个样本；掉样本的臂其离散度**必须标样本数**，
    不许给"单点值 + 假装同精度"的读法）
5. `runlog.jsonl` 里 **A5 三个臂的 `ops` 直方图**""",
   "A6 阶段5 4b")


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

    # ---- 改动 4：A1–A6（逐条独立幂等）----
    if "阶段 1 · 定位实验根目录 + 静态自检" not in s:
        s = replace_region(s, "## 阶段 1 · 重建 + 静态自检", "## 阶段 2 · 冒烟", A1_NEW)
        print("  ✓ A1：阶段 1 整段重写（目录名两条路径）")
    else:
        print("  · A1 已在，跳过")
    applied4 = 0
    for mark, old, new, tag in EDITS4:
        if mark in s:
            continue
        if old not in s:
            raise SystemExit("✗ 改动 4 锚点未命中：%s" % tag)
        s = s.replace(old, new, 1)
        applied4 += 1
    if applied4:
        print("  ✓ 改动 4：应用了 %d 处（A2–A6）" % applied4)


    # ===== 改动 5：默认判官改 grok-4.3 =====
    if 'export OR_PRIMARY=x-ai/grok-4.3          # 判官' not in s:
        if 'export OR_PRIMARY=deepseek/deepseek-chat          # 判官：跨厂商，非 MiniMax' in s:
            s = s.replace('export OR_PRIMARY=deepseek/deepseek-chat          # 判官：跨厂商，非 MiniMax', 'export OR_PRIMARY=x-ai/grok-4.3                   # 判官：跨厂商，非 MiniMax（**deepseek 自检不稳 ⇒ 不用它**）', 1)
            print('  ✓ applied: 改动 5：默认判官改 grok-4.3')
    if '默认模型已是 `x-ai/grok-4.3`' not in s:
        if '> GitHub 树**已经打好补丁**（默认模型已是 `deepseek/deepseek-chat`），再跑 `rebuild.sh`' in s:
            s = s.replace('> GitHub 树**已经打好补丁**（默认模型已是 `deepseek/deepseek-chat`），再跑 `rebuild.sh`', '> GitHub 树**已经打好补丁**（默认模型已是 `x-ai/grok-4.3`），再跑 `rebuild.sh`', 1)
            print('  ✓ applied: 改动 5：默认判官改 grok-4.3')
    if 'OR_PRIMARY=x-ai/grok-4.3 python3 analyze_cmp6.py' not in s:
        if 'CMP_OUT=runs/cmp8 OR_PRIMARY=deepseek/deepseek-chat python3 analyze_cmp6.py' in s:
            s = s.replace('CMP_OUT=runs/cmp8 OR_PRIMARY=deepseek/deepseek-chat python3 analyze_cmp6.py', 'CMP_OUT=runs/cmp8 OR_PRIMARY=x-ai/grok-4.3 python3 analyze_cmp6.py', 1)
            print('  ✓ applied: 改动 5：默认判官改 grok-4.3')
    if 'OR_PRIMARY=x-ai/grok-4.3 \\\\' not in s:
        if 'CMP_OUT=runs/cmp8_mmemb EMBED_PROVIDER=minimax OR_PRIMARY=deepseek/deepseek-chat \\' in s:
            s = s.replace('CMP_OUT=runs/cmp8_mmemb EMBED_PROVIDER=minimax OR_PRIMARY=deepseek/deepseek-chat \\', 'CMP_OUT=runs/cmp8_mmemb EMBED_PROVIDER=minimax OR_PRIMARY=x-ai/grok-4.3 \\', 1)
            print('  ✓ applied: 改动 5：默认判官改 grok-4.3')

    if s != orig:
        io.open(path, "w", encoding="utf-8").write(s)
    return s != orig


if __name__ == "__main__":
    for p in (sys.argv[1:] or ["AGENT_RUNBOOK.md"]):
        print("patch_runbook:", p)
        patch(p)
    print("done")
