# 架构化改造说明（第四组 · arch）

> 本文说明**改了什么、为什么改**。
> 实测数据见 `REPORT_arch.md`；原始记录见 `runs/arch_compare.jsonl`、`runs/arch_probe.jsonl`。

---

## 0. 为什么要改造

上一轮的 "WF 臂"（`run_minimal_compare.py`）**不是架构，是提示词**。

看它的 `F_SYS` / `G_SYS`：

```
【输出要求】分三段，全部用叙述性自然语言：
第一段「未落地」：…
第二段「本轮约束」：…恰好 3 行…
第三段「已排除」：…恰好 2 行…
```

**状态转移律（"看初稿 → 产新约束 + 产排除项"）是硬编码在提示词模板里的。**

⇒ 三个后果：

| 后果 | 实测证据 |
|---|---|
| ① 能否工作取决于模型**自觉遵守格式** | 上一轮转移步的"未落地"段被解析器当成了写作约束（诊断句进了 `keeps`） |
| ② 格式一崩就**静默降级** | 解析器没有"这条不是约束"的判据，只能按关键词猜 |
| ③ "状态依赖观测"只是**提示词请求**，不是结构保证 | 模型可以不看初稿就说"不要再出现 X" |

**用户原则**：能用架构/机制解决就少用预制提示词解决，因为后者更容易造成过拟合。
⇒ 这次改造就是按这条原则做的：**把状态机从提示词里搬进代码。**

---

## 1. 改造后的结构

```
State  ← 代码里的 dataclass（字段固定、类型明确、可序列化、可差分）
  │  stance / keeps / slip / first / excluded / gaps / step / polarity
  │
  ├─ step_stance()    模型：给出立场 + 3 条取舍 + 失守点 + 第一次反应
  │                   代码：校验、补齐、写入 State
  │
  ├─ step_draft()     模型：写初稿
  │
  ├─ step_observe()   模型：**只描述事实**（used / gaps / new_constraints / sharpest）
  │                   代码：解析（容错）、显式标记缺字段
  │
  ├─ transfer(prev, observation)   ← ★ 状态转移律，现在是**代码里的纯函数**
  │      ① 缺口      ← 来自观测
  │      ② 已排除    ← **代码从观测里机械抽取**（模型不负责自述）
  │      ③ 新约束    ← 由缺口触发，模型改写，**代码校验绑定**
  │      ④ 补齐      ← 不足 3 条时沿用上一轮，**显式标注来源**
  │
  └─ step_final()     模型：写定稿
```

### 关键改动 1：「已排除」由代码机械抽取

旧实现：提示词要求模型自己写一段"已排除"。

新实现：模型只说"初稿里已经用过 X"，**代码**把 X 转成 `不要再出现：X`。

⇒ **"已排除"在结构上必然依赖观测**（没有观测就没有可抽的东西）。
   这不是"模型听话"，是代码保证。

### 关键改动 2：转移律接受 `observation` 作为**显式参数**

```python
def transfer(prev, observation, rewriter=None) -> (State, trace)
```

⇒ `observation=None` 就是**消融**（无观测 ⇒ 不产生新约束、不产生已排除）。
⇒ 换一份 observation 就是**置换探针**。
⇒ 这两件事在旧实现里做不到——旧实现的转移逻辑埋在提示词字符串里。

### 关键改动 3：绑定从"相似度猜测"改成"结构声明"

第一次改造时，绑定校验用字符 2-gram Jaccard 猜"这条约束对应哪个 gap"。
**实测发现它有假阴性**：

```
score=0.0526 linked=False
  约束: 选择一个具体话题，按"问题是什么—影响是什么—如何解决"的路径写出示例内容…
  gap : 初稿提到"具体的例子和真实的分析，比漂亮的套话更有说服力"，但没有给出一个完整例子…
```

约束明写"对应第一个缺口"，语义上绑定清清楚楚，字面相似度却只有 0.05。

⇒ 修法（与第四组既有原则一致：**极性/绑定必须以结构进入，不能靠措辞**）：
观测步的 JSON 改成

```json
"new_constraints": [{"gap_index": 1, "constraint": "..."}]
```

代码按 `gap_index` 直接绑定 ⇒ **零歧义、零阈值**。
字面相似度降级为**辅助信号**（`method: lexical_fallback`），并统计有多少条走了退化路径。

### 关键改动 4：`rewriter` 注入 ⇒ 转移律保持纯函数

`transfer()` 不自己调模型，模型改写由调用方注入 ⇒
**可以用假实现做单元测试**（零成本、不依赖 API、结果确定）。
⇒ `workflow_arch.py` 的 24 项自检里包含**变异注入**（把修复改回旧写法，测试必须 FAIL）。

---

## 2. 五臂设计

| 臂 | 结构 | 作用 |
|---|---|---|
| **A** | 直接调用，1 次，无 system | 基线 |
| **S** | **等调用数中性管线**，4 步，**不建状态** | 剥离"步数 / 上下文强度"混淆 |
| **WF-p** | 提示词式状态机（`run_minimal_compare` 逐字同源） | 旧机制 |
| **WF-a** | 架构化状态机，4 步 | 新机制 |
| **WF-a-R** | 架构化 + **反极性立场**，5 步 | 换极性武器 |
| **WF-a-NO** | 架构化 **消融**：转移不喂初稿 | 检验"观测依赖" |

**唯一输入**（逐字，两臂相同）：

```
你如何看待高考英语作文？写成一篇文章。
```

**没有** `audience` / `genre` / `length` / `brief` / `dilemma` / `pole_a` / `pole_b` / `role` /
字数上限 / "用第一人称"类指令。**A 臂完全不发 system。**

### 对照公平性怎么保证

- WF-p 臂**直接 import** 旧模块的 `STANCE_SYS` / `WRITE_SYS` / `F_SYS` / `G_SYS`，
  **不手抄** ⇒ 逐字同源，不可能漂移。
  验证方式：`run_minimal_compare.STANCE_SYS == run_arch_compare.STANCE_SYS` 等 4 项全 True。
- 所有臂走**同一个传输层** `api_any.chat`（同一模型、同一 temperature、同一 max_tokens 策略）。
- 传输层规则：结构化步关 thinking、创作步开 thinking、返回值统一剥 `<think>`。
  ⇒ 旧实现的 `parse3()` 不用改也能吃干净内容 ⇒ WF-p 仍是逐字旧实现。

---

## 3. 本轮新增的 API 事实（2026-10-21 实测）

| 事实 | 结果 |
|---|---|
| **OpenRouter 全线 401** | `/api/v1/auth/key`、`/credits`、`/chat/completions`（grok-4.20 / deepseek-v4.1-flash）**全部** `{"error":{"message":"User not found.","code":401}}` ⇒ 跨厂商判官通道不可用 |
| MiniMax-M3 纯写作 | thinking **默认开**，`<think>` 块被塞进 `message.content`；`reasoning_content` 字段**不存在** |
| MiniMax-M3 JSON 模式 | content 干净（无 think），`thinking:{type:"disabled"}` 也接受 |
| 截断 | `finish_reason=length`；`<think>` 开了没闭 = 被截断 ⇒ 传输层**加预算重试**，不返回截断内容 |

⇒ **本轮全零判官**，只跑离散结构量。这既是限制，也是纪律：
判官不可用时，第四组本来就该用零判官指标，而不是硬凑一个同源模型当判官。

---

## 4. 文件清单

| 文件 | 作用 |
|---|---|
| `workflow_arch.py` | 架构化状态机（`State` / `transfer` / `resolve_binding` / `build_excluded`）+ 24 项自检（含变异注入） |
| `api_any.py` | 统一传输层（MiniMax / OpenRouter 双通道、thinking 策略、截断重试、usage 记录） |
| `run_arch_compare.py` | 六臂 runner |
| `probe_arch.py` | 状态历史置换探针（swap vs same 噪声地板） |
| `analyze_arch.py` | 全零判官分析器 |
| `kill_runner.py` | 残留进程清理（模式写在文件里，避免 pkill 自匹配） |
| `run_pipeline.sh` | 后台串行（setsid 独立 session） |
