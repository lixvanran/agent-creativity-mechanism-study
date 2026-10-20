# 执行手册 · 给本地 Agent

> 你拿到这个包，是为了**跑出一批可信的数据**。
> 配套的《实验方法》见同包 `METHOD.md`——**方法学、判据口径、已知局限都在那里**，出问题先查它。
>
> ⚠️ **这个包最危险的地方不是跑不起来，是"跑起来了但结论是假的"。**
> 本手册里的**闸门**就是为此设计的。**闸门不过，不要往下走。**

---

## 你是谁 / 任务是什么

你的任务：**执行这套对比实验，把结果原样回报**。

- 7 个臂 × 4 道题 × 3 次重复 = 84 份答案，然后跨厂商判官核验 + 出表 + 判读页
- **你不负责下结论。** 结论由人下。你负责：**跑对、跑完整、把数原样报上去**。

---

## 硬约束（违反其一，这批数据就废了）

1. **不许改任何阈值。** 特别是去重阈值 `0.75`、判官自检的 `≥3/4` 门槛、矛盾率的分母定义。
   这些是**预注册**的。改了就不叫复现，叫另做一件事。
2. **不许中途重跑。** 中断重跑会产生**跨批次重复**（同一臂×样本两条、两个 batch_id），
   污染统计。要重跑就**整批重来**，旧的隔离到别处。
3. **不许"跑完了就宣布成功"。** 判官自检不过 ⇒ 整套作废（矛盾率是唯一的仲裁器）。
4. **不许用兜底值填缺失。** 某臂跑了/没跑、失败了，**照实说**。
5. **不许把"解析失败"算进分母。** 它既不是支持也不是矛盾。
6. **不许改模型。** 429 限流 → 退避重试**同一模型**（换模型会悄悄改掉"模型构成"这个变量，
   臂间对比就失效）。只有连续 529 过载才降级，且**降级了必须记下来**。

---

## 阶段 0 · 环境准备

```bash
pip install numpy            # ★ 唯一的第三方依赖（其余全标准库）

`client.py` / `orclient.py` 用 `urllib.request`（**不用 requests**）；
`creativity_lab/scipy_free.py` 是**刻意避开 scipy** 的实现 ⇒ **不要 pip install scipy**。
看到 `import requests` 报错 = 你改错文件了。
```

```bash
export MINIMAX_SUBSCRIPTION_KEY=<你的 minimax 订阅 key>
export OPENROUTER_API_KEY=<你的 openrouter key>
export PRIMARY_MODEL=MiniMax-M3.1-Flash-Preview   # M3 当天持续 529，用健康档位
export OR_PRIMARY=deepseek/deepseek-chat          # 判官：跨厂商，非 MiniMax
export OR_EMBED=qwen/qwen3-embedding-8b            # embedding：4096 维
export CMP_OUT=runs/cmp8
export ADH_MODE=repro                              # 臂2 走 Python 复刻
export OPENROUTER_BASE_URL=https://api.minimaxi.com/v1   # MiniMax 侧
export OR_BASE_URL=https://openrouter.ai/api/v1           # OpenRouter 侧
```

> ⚠️ `OR_PRIMARY` **不要**用 `x-ai/grok-3-mini`——它**已 404 下架**。
> 旧代码会把 404 静默重试 4 次后返回空串 ⇒ 判官拿到空串 ⇒ 所有断言"解析失败"
> ⇒ **矛盾率 = 0/0 = 0 ⇒ 你会看到一个"零错误"的完美结果**。
> 这是本项目最阴的一种失败。包内已修（404→立刻换模型 + 全失败抛错带原因），
> **但你仍必须看冒烟的自检结果，不能只看"跑完了"。**

---

## 阶段 1 · 定位实验根目录 + 静态自检

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

## 阶段 2 · 冒烟 ★ 闸门

```bash
python3 smoke_or.py
```

看四段输出：① 判官通道 ② embedding 通道 ③ **判官自检** ④ MiniMax 被测侧。

### ★ 闸门判定

| 判官自检结果 | 动作 |
|---|---|
| **真断言 ≥3/4 且 假断言 ≥3/4** | ✅ 继续阶段 3 |
| 否则 | ❌ **停。不要跑批。** 把全部输出原样报上去，说明判官不可用 |

**为什么这么严**：矛盾率是这套实验**唯一的仲裁器**。
判官不行 ⇒ 矛盾率不可信 ⇒ 84 份答案跑完也是废的，而且**数字会看起来很美**。

### 如果 ① 判官通道没输出

先确认模型还活着（OpenRouter 侧模型下架很频繁）：

```bash
python3 - <<'PY'
import os, json, urllib.request
B = os.environ.get("OR_BASE_URL", "https://openrouter.ai/api/v1")
K = os.environ.get("OPENROUTER_API_KEY", "")
for m in ["deepseek/deepseek-chat", "x-ai/grok-4.3", "qwen/qwen3.7-plus",
          "meta-llama/llama-3.3-70b-instruct", "z-ai/glm-4.5"]:
    try:
        r = urllib.request.Request(B + "/chat/completions",
            data=json.dumps({"model": m, "messages": [{"role":"user","content":"用一句话说明什么是复利"}],
                             "max_tokens": 200}).encode(),
            headers={"Authorization": "Bearer " + K, "content-type": "application/json"})
        d = json.loads(urllib.request.urlopen(r, timeout=45).read().decode())
        c = d["choices"][0]; t = c["message"].get("content") or ""
        print("%-42s %s" % (m, ("OK %d字" % len(t)) if t.strip() else "EMPTY"))
    except Exception as e:
        print("%-42s ERR %s" % (m, str(e)[:80]))
PY
```

挑一个能用的 `export OR_PRIMARY=<它>`，重跑冒烟。

**如果全都不行**：说明这把 key 的可用面变了（**不是你的错**）——
把 `GET /key` 和 `GET /credits` 的返回报上去，账号余额/额度会被用来判断是 key 级还是模型级问题。

---

## 阶段 3 · 跑批

```bash
# 已在实验根目录（阶段 1 进对了就别再 cd）
python3 run_compare5.py --arms A1,A2,A3,A4,A5a,A5b,A5c --reps 3 --workers 4
```

**实测 ≈3.5–4 小时 / 84 份答案**（≈800 次调用 × ~33 s ÷ 4 并发；
**A5 三臂偏慢，实测 491–734 s/臂样本** ⇒ 是总时长的主要来源）。

### 监控规则（跑的过程中就要看，不是跑完再看）

| 现象 | 含义 | 动作 |
|---|---|---|
| 某个臂**整臂**都是 0 字 | 529 过载把该臂打空了 | **停**。降并发到 2，整批重来。空答案混进统计会得到"全都零错误"的假象 |
| 某一份 0 字但同臂其他份正常 | 单次抖动 | 记下来，继续 |
| 大量 `[orclient] ... 持续限流` | 429 | **正常**，会自己退避。别调高并发 |
| 卡住不动 | — | 查 `runlog.jsonl` 最后几行 |

**`--workers 4` 不要调高。** 调高会触发整片 429 失败（实测 8 并发 ⇒ 36 次调用整片失败）。

**中途不要重跑**（见硬约束 2）。

---

## 阶段 4 · 分析（★ 两遍都要跑）

```bash
# 已在实验根目录
# 遍一：OpenRouter embedding（qwen3-embedding-8b，4096 维）
CMP_OUT=runs/cmp8 OR_PRIMARY=deepseek/deepseek-chat python3 analyze_cmp6.py
# 遍二：MiniMax embo-01（0.75 阈值的标定基准）—— 必须落在独立目录
CMP_OUT=runs/cmp8_mmemb EMBED_PROVIDER=minimax OR_PRIMARY=deepseek/deepseek-chat \
```bash
# 已在实验根目录
python3 analyze_cmp6.py && python3 build_compare5_page.py
```

⚠️ **遍一如果 OpenRouter 不通，`judge_provider.py` 会自动退到 MiniMax**（并打大字警告）⇒
**判官与被测同源 ⇒ 矛盾率失效 ⇒ 整套作废**。
⇒ **必须检查 `analysis.json` 的 `judge_same_vendor` / `judge_used` / `embed` 三个字段**，
并在回报里声明。**不许悄悄用同源结果。**

### 为什么要两遍

去重阈值 `0.75` 标定在 MiniMax `embo-01` 上。换了 embedding 模型，余弦尺度变了。

**最坏情况不是"偏"，是"退化"**：所有臂的去重宽都塌成 1~2 ⇒
"宽度"这一列**没有任何区分度**，表格看着正常，其实这轴已废。**这比报错危险。**

### 分析器自带的体检

分析器会打印**去重体检表**（保留率 = 去重宽 / 原始断言数）：

| 保留率 | 判读 |
|---|---|
| < 0.15 | ⚠️ 去重几乎全合并 ⇒ **宽度轴退化**，明说 |
| 0.15 – 0.85 | 去重在工作，宽度轴可用 |
| > 0.85 | ⚠️ 阈值太松，几乎没去重，**明说** |

### 判读规则

- 两遍**臂间排序一致** ⇒ 宽度结论**稳健**，写「两种 embedding 下排序一致」
- 排序**不一致** ⇒ **两个数都报**，写「宽度结论依赖 embedding 通道，**不稳**」
- **无论哪种情况，都要同时给 `n_raw` 和 `width` 两列，并说明用哪一列下结论、为什么。**
  `n_raw`（原始断言数）**不依赖 embedding**，是对所有臂一视同仁的广度指标 ⇒
  宽度轴废了也能用它撑住"谁覆盖得更多"。

### ★ 判官解析失败率（分析器会打这张表，**必须看**）

判定失败的断言**既不进分子也不进分母**（这是对的：不把"读不懂"当成"说对了"）。
**但失败条数必须报出来** ⇒ 分析器会输出「判官解析失败率」表。

| 解析失败率 | 判读与动作 |
|---|---|
| ≤ 10% | 正常 |
| > 10% | ⚠️ **该臂的矛盾率是在"悄悄缩小后的分母"上算的** ⇒ 表上看不出来，但臂间**不可比**。**不要重跑掩盖它**，把它标出来一起报 |

⚠️ **不许因为失败率高就重跑**——那是把仪器故障当成实验结论。
正确动作是：**报失败率 + 标注该臂矛盾率不可比**。

```bash
python3 build_compare5_page.py      # 判读页：每臂每题每重复的原始答案 + 指标
```

---

## 阶段 5 · 回报（**原样贴，不要自己重算、不要改写**）

1. **`analyze_cmp6.py` 的全部终端输出**（7 臂表、逐题并集宽度、逐题矛盾率、**去重体检表**）
2. **【⑤b vs ⑤c】那段原文**（含种子间标准差）—— 整轮实验的胜负手
3. `judge_selfcheck.json`
4. `analysis.json` 的 `judge` / `judge_used` / `judge_same_vendor` / `embed` / `census` / **samples**
4b. **逐臂样本列 `valid/total`**（哪个臂掉了几个样本；掉样本的臂其离散度**必须标样本数**，
    不许给"单点值 + 假装同精度"的读法）
5. `runlog.jsonl` 里 **A5 三个臂的 `ops` 直方图**
   （**A5b 与 A5c 的操作分布若一模一样 ⇒ 权重没起作用，这本身就是结论**）
6. **A5 三个臂的 `fallback` 字段**（机械装配产出空壳时退回最长 ANSWER；
   **大面积为 true ⇒ 这批 A5 数据要打折**）
7. 两遍分析的 `n_raw` / `width` / 保留率对比
8. **「判官解析失败率」表**（逐臂 `n_parsefail` / `parsefail_rate`）
9. 判读页路径
10. **没跑完/哪几个臂挂了 ⇒ 照实说**

---

## ★ 阶段 6 · 结论怎么写（**这一节是给你和读报告的人的**）

**唯一能当仲裁器的量是矛盾率。** 其它都是辅助。

- **⑤b vs ⑤c 的差异必须与种子噪声地板比。**
  差异 ≤ 地板 ⇒ **写「不可分辨」**，**不写「无效应」**（n=3 分不清"无效应"和"没测出来"）。
  背景：学到的权重范数只有 ~0.062，ε-greedy 的随机加分（0–2.0）比策略信号（最大 ~0.09）**大 20 倍**。
- **不许宣布"成功/失败"。** 最终评分和标注由**人**做。判读页给的是原始答案，指标只是辅助。
- 报告里**必须**保留这些声明（照抄 `METHOD.md` §7）：
  臂2 是**机制复现**非原版本体（3 处差异）｜模型集因 M3 过载被固定为 5 个健康档位｜
  判官是**跨厂商**（若退到 MiniMax 则同源，必须声明）｜oracle **没有第二来源交叉核**｜
  n 小（12 份/臂）⇒ 方向性结论不是精确裁决｜去重阈值**依赖 embedding 通道**｜
  依据包**全程未进训练**，四道题是外部测试集

---

## 故障排查速查

| 症状 | 大概率原因 | 处理 |
| `cd: cmp8pkg: No such file or directory` | **目录名搞错了**（GitHub 的是 `cmp8/`，zip 的是 `cmp8pkg/`） | 回阶段 1，看"进对目录"那段 |
|---|---|---|
| 冒烟 ① 输出 0 字符 | 模型 404 下架 | 换 `OR_PRIMARY`（见阶段 2 的探针） |
| 冒烟 ② 报 ToS/403 | 供应商封禁该 embedding | 换 `OR_EMBED`（用 `baai/bge-m3` 或 `sentence-transformers/all-minilm-l6-v2`） |
| 判官自检假断言 < 50% | 判官不认识依据包 | **停**，报上去。不要跑批 |
| 整臂 0 字 | 529 过载 | 降并发到 2，整批重来 |
| MiniMax 529 | M3 过载 | `PRIMARY_MODEL` 用 `MiniMax-M3.1-Flash-Preview` |
| `KeyError: 'cap'` 之类 | dry-run 路径长期未测 | 报上去，别自己猜着改 |
| 装配输出是「（无）」 | 断言全被丢掉 | 已在包内修（单列"未经核验"一节）；若仍出现，报上去 |

---

## 你**绝对不要**做的事

- ❌ 改阈值、改提示词、改判据措辞来"让结果好看"
- ❌ 只报好看的臂
- ❌ 把"解析失败"当"无矛盾"
- ❌ 中途重跑后混合两批数据
- ❌ 宣布结论、宣布"成功"、宣布"这证明了 X"
- ❌ 因为结果不符合预期就重跑（那是 p-hacking）
