# 交接件 · A 篇 2×2 饱和度判死门 · 可执行规格

> 落点：`docs/交接/WORKPACK-4-saturation-2x2-spec.md`｜2026-10-25 第二组
> 收件方：论文簇 / 第 1 层论证线
> 用途：对方在本地补跑「不饱和域（用户四道题）× 2 臂」那格
> **本件只交付规格与继承口径，不含新读数**（对方明确要求「不跑新批」）
> **本件第 4 节列出了 5 个必须先处理的口径缺口，其中 2 个会直接让读数不可比**

---

## 0. 这件事的原始出处（本组已有的交接文档）

★ **这件事的原始配方在 `HANDOVER.md` 第 4 节**，不是新造的。本件只是把它核到可执行。

| 出处 | 内容 |
|---|---|
| `HANDOVER.md` §4.1 | 三个数的定义：`w_dd` / `w_ds` / 饱和度 = `w_dd − w_ds` |
| `HANDOVER.md` §4.2 | 法律域 18 题实测：`w_dd` 0.936–0.996、`w_ds` 0.802–0.977、**饱和度均值 +0.0483，范围 0.0064–0.1593** |
| `HANDOVER.md` §4.3 | ★ **最关键的一条**：原始 `w_dd` **不能**当「确定度」用（同题不同答的余弦地板 ~0.991，主要是题域相同，不是模型有把握）⇒ **必须用差值** |
| `HANDOVER.md` §4.4 | 对四道题的预期：**跑出来饱和度应明显低于 0.0483**；若 `w_dd` 也很高（>0.97）说明模型有把握，工作流没用是真的没用 |
| `HANDOVER.md` §5 | P1–P8 preflight 规格原文（`creativity_lab/workflow.py` 的 `PREFLIGHT_CATALOG` 里也有） |
| `HANDOVER.md` §6 | 「四道题 + 我们的仪器」的坑（四道题是**测试集**，不是巡练集） |

判据脚本（仓内，唯一真相源）：

| 项 | 值 |
|---|---|
| 饱和度版脚本 | `creativity_lab/gate_policy.py`（第 4 段 = 饱和度实现） |
| 早期版脚本 | `creativity_lab/diagnose_uncertainty.py`（只有 `conf`，无饱和度差值） |
| 嵌入 | `creativity_lab/client.py` 的 `LLM().embed` ⇒ 模型 **`embo-01`**，dim 1536 |
| 相似度 | `client.py` 的 `cosine`（归一化点积） |
| 断言抽取 / 核验 | `creativity_lab/verify.py` 的 `extract_claims` / `check_claims` |
| 去重 | `gate_policy.py` 的 `dedup_n(claims, thr)`，阈值 0.70 / 0.75 / 0.80 三档 |

★ **法律域 +0.0483 与我们要跑的四道题，用的是同一把尺子（`embo-01`）、同一批公式、同一个型号（MiniMax-M3）、同样 2 次采样。** ⇒ 公式侧可比。

---

## 1. 2×2 的两个轴与判死门

| 轴 | 水平 | 题集 | 状态 |
|---|---|---|---|
| 域饱和度 | 饱和 | 法律 18 题（6 部法 × 3 角度） | 已有对照值 **+0.0483**（`HANDOVER.md` §4.2） |
| 域饱和度 | 不饱和 | 用户四道题 U1–U4 | **缺** |
| 臂 | 直调 | `direct` | 两格各 1 |
| 臂 | 工作流 | `dual_select`（只选不融） | 两格各 1 |

判死门原文（A 篇 §8.1 第 1 项）：

> 若 2×2 显示增益**只出现在不饱和域**，则「架构无用」需改写为「**增益来自不确定性，不是来自架构**」。

主读数：

```
w_dd   = cos(直调rep1, 直调rep2)          同臂同题两次独立采样
w_ds   = mean over pairs cos(直调, 工作流)  跨臂同题
饱和度 = w_dd − w_ds
```

判读：饱和度高 ⇒ 模型确定 ⇒ 探索空间小 ⇒ 工作流没地方发挥；接近 0 或更低 ⇒ 不饱和 ⇒ 探索可能有价值。

---

## 2. 臂定义

| 臂 | 实现 | 每 rep 调用数 | 提示词 |
|---|---|---|---|
| `direct` | `gate_policy.py` 的 `gen()` 中 `arm == "direct"` 分支 | 1 | `问题：%s\n\n给出你的方案与理由，400字以内。`，`model="MiniMax-M3"`，`min_ok=200` |
| `dual_select` | `creativity_lab/arms/dual.py` 的 `Dual("select")` | 5 发散 + 1 选择 = **6** | `BRANCH_ASK`（发散 5 支）+ `SELECT_ASK`（选择） |

发散层规格：`dual._branch_specs()` = 5 支，框架 / 模型 / persona 三者错位绑定。
框架取 `dual.FRAMES`（7 个，取前 5）、型号取 `dual.MODELS`（取前 5）、persona 取 `dual.PERSONAS`。

⚠️ **成本不匹配**：`dual_select` 6 次 vs `direct` 1 次。A 篇 §7 局限第 12 条已登记此事（未做等预算对照）。对方若要补等预算臂，请另立臂名并单列，不要覆盖 `direct` / `dual_select`。

---

## 3. 题集

### 3.1 不饱和域（要补的那格）

| 题 | 文件 | 内容 |
|---|---|---|
| U1 | `cmp8/creativity_lab/data/user4_q1.json` | 湖北物理类 620 分选校与 AI 专业（依据：2025/2026 湖北一分一段、专业选考要求、武大等三校投档线） |
| U2 | `cmp8/creativity_lab/data/user4_q2.json` | 公路赛个人赛战术与 UCI 规则（依据：UCI 2.3.012 / 2.3.014 / 2.3.036 / 2.3.040 / 2.4.018） |
| U3 | `cmp8/creativity_lab/data/user4_q3.json` | 五一假期最后一天作业没动（依据：番茄工作法 25/5/15-30、Gloria Mark 23 分 15 秒、艾宾浩斯） |
| U4 | `cmp8/creativity_lab/data/user4_q4.json` | 陈会昌气质量表得分判定（依据：60 题计分规则、人民网 2013 阈值规则） |

每题字段：`tid` / `ask` / `name` / `evidence`。核验用的原子事实切法照抄 `cmp8/net_gain.py` 的 `facts_of()`：按 `。；;\n` 切分、保留长度 ≥8 的片段。

### 3.2 饱和域（对照格）

| 题 | 文件 | 规模 |
|---|---|---|
| 法律 18 题 | `creativity_lab/data/legal_topics_v2.json` | 6 部法（A–F）× 3 角度 = 18；`laws[law].evidence` 是依据包 |

顶层结构 `{note, laws, topics}`；每题 `topics[]` 只有 `tid/law/ask`，evidence 在 `laws[law].evidence`。

---

## 4. ★ 五个必须先处理的口径缺口

★ **这五条是本件的核心。前两条不处理，跑出来的数不能和 +0.0483 比。**

### 缺口 1（★ 硬阻塞）★ `dual_select` 的第 5 支绑定了**已下架型号** `MiniMax-M2.1`

| 事实 | 证据 |
|---|---|
| `dual.MODELS` 前 5 = `M3, M3.1-Flash-Preview, M2.7, M2.5, **M2.1**` | `creativity_lab/arms/dual.py` |
| `MiniMax-M2.1` 实测 `alive: false` | `runs/model_probe.json` |
| `Dual._diverge()` **支持 `specs` 注入**（2026-10-23 专为剔掉下架型号而加） | `dual.py:36-40` |
| ★ **但 `Dual.run()` 没有暴露这个参数** ⇒ 走 `run()` 一定带上 M2.1 | `dual.py:66` |

⇒ **后果**：`dual_select` 的 5 支会**静默变 4 支**（下架型号返回空，被 `if o` 过滤掉）⇒
① 发散面从 5 支变 4 支 ⇒ 与 2026-10-18 那批**不等价**；
② **更危险**：失败是静默的，不报错、不减员计数。

★ **处置（两条路，请对方选）**：
- **路 A（推荐）**：给 `Dual.run()` 加一个可选 `specs=None` 形参并透传给 `_diverge`（**一行改动，不改默认行为**），然后在四道题上显式传入 5 个**全活**型号。⇒ 与 `topo_arm.py` 已有的 `specs` 注入做法一致（同一模式，本仓已有先例）。
- **路 B**：接受 4 支，但**必须同时把饱和域 18 题也用同样的 4 支重跑**（否则两域的臂内支数不同 ⇒ 不可比）⇒ 成本从 16 次生成涨到 18×2×2 + 4×2×2。

★ **无论走哪条，manifest 必须落 `models_used`（实际用了哪些型号）**，不能只记计划型号。本组已有同类事故：ToT 臂 manifest 记的是计划型号、不是实际 `models_used`。

### 缺口 2（★ 硬阻塞）★ 法律域 18 题的**原始文本不在本组工作区**

`HANDOVER.md` §4.2 只给了**汇总数**（`w_dd` 0.936–0.996、`w_ds` 0.802–0.977、饱和度 +0.0483、范围 0.0064–0.1593），**没有 18 题的逐题原始文本**。

| 查过的地方 | 结果 |
|---|---|
| `runs/policy/` | 不存在 |
| 全仓 `texts.json` | 0 命中 |
| 全仓 `*legal*` | 只有题面数据（3 个文件），无跑批产出 |
| `runs/` 下 23 个目录 | 无法律域跑批 |

⇒ **要拿到严格同尺子的两域对比，必须重跑饱和域 18 题**（成本：18 题 × 2 臂 × 2 rep × ~6.5 次 ≈ 470 次生成调用；可接受）。
⇒ **如果只跑四道题**，四道题那格的数是**有效的**（公式与配置都对），但**与 +0.0483 的比较缺一环**：+0.0483 是 2026-10-18 在**当时的型号池**下跑的，而现在型号池已变（见缺口 1）⇒ **两域的臂内支数可能不同**。

★ **建议**：**两域一起重跑**（缺口 1 走路 A ⇒ 两域都用同一组 5 个活型号）⇒ 这才是干净的 2×2。

### 缺口 3 ★ 题数不等（18 vs 4）

两域题数差 4.5 倍 ⇒ 饱和度均值带题集构成差异。A 篇 §7 局限第 1 条已登记「两域任务分布不同，不是同域对照」。
⇒ **正确用法**：看 4 题的饱和度落在 +0.0483 的哪一侧（方向与量级），并把 n=4 写进结论句；**不要**用 4 题去「推翻」18 题的对照值。

### 缺口 4 ★ `direct` 臂的提示词必须用 `gate_policy.py` 那版，**不是** A 篇 `run_compare5.py` 那版

| 项 | `gate_policy.py`（★ 继承源） | `run_compare5.py`（A 篇七臂） |
|---|---|---|
| 提示词 | `问题：%s\n\n给出你的方案与理由，400字以内。` | `f"{q}\n\n{ART}"`，ART 另含「观点明确、给出具体动作与依据…」 |
| 型号 | `MiniMax-M3` | `PRIMARY = MiniMax-M3.1-Flash-Preview` |
| max_tokens | 默认 | 4000 |
| min_ok | 200 | 120 |

⇒ ★ **`cmp8/runs/cmp8/` 那 166 项产出（用户四题 × 7 臂 × 2 rep）配置与本实验不同 ⇒ 不能直接当「不饱和域那格」用。** 这一点必须写明，否则对方会误以为「那格的数据已经有了」。

### 缺口 5 ★ 断言核验需要依据包，四道题的依据包在 `evidence` 字段而非 `laws` 字典

`gate_policy.py` 取依据的写法是 `LAWS[law_of[tid]]["evidence"]`（法律域用）。四道题每题自带 `evidence` ⇒ 需改成 `TOPIC[tid]["evidence"]`。核验本身走 `verify.check_claims`，参数形式相同。

---

## 5. 配置继承表（逐项）

### 5.1 必须原样继承

| 项 | 值 | 继承自 |
|---|---|---|
| 饱和度公式 | `w_dd − w_ds` | `HANDOVER.md` §4.1 ＋ `gate_policy.py` §4 |
| 嵌入模型 | `embo-01`（dim 1536） | `creativity_lab/client.py` |
| 直调臂型号 | `MiniMax-M3` | `gate_policy.py` 的 `gen()` |
| effort | `medium`（`DEFAULT_EFFORT`） | `creativity_lab/client.py` |
| temperature | `1.0` | `client.py` 的 `LLM.chat` 默认 |
| max_tokens | **8000**（`LLM.chat` 默认；★ **不要**改成 4000/5000） | `client.py:80` |
| 重复数 | 2 | `gate_policy.py` 的 `REPS = 2` |
| 直调臂 min_ok | 200（★ 与 `LLM.chat` 默认同值，★ **但仍要显式传**，★ 因为默认值将来可能变） | `gate_policy.py` 的 `gen()` |
| 断言抽取 / 核验 | `extract_claims` / `check_claims` | `creativity_lab/verify.py` |
| 去重阈值 | 0.70 / 0.75 / 0.80 三档 | `gate_policy.py` §5 |
| 饱和域对照 | 18 题 / MiniMax-M3 / 每题 2 次采样 | `HANDOVER.md` §4.2 |

### 5.2 必须**改**的（相对 `gate_policy.py`）

| 项 | 改成 | 为什么 |
|---|---|---|
| `DATA` | 四道题（`cmp8/creativity_lab/data/user4_q{1,2,3,4}.json`） | 原为政策域 8 题 |
| 依据包取法 | `TOPIC[tid]["evidence"]` | 四道题无 `laws` 字典（缺口 5） |
| 型号池 | 显式传 5 个**实测存活**的型号 | M2.1 已下架（缺口 1） |
| `OUT` | 新的输出目录 | 避免与政策域混 |

---

## 6. 对方本地补跑的操作顺序

| 步 | 动作 | 生成调用 | 嵌入调用 |
|---|---|---|---|
| 0 | 探测型号存活（`runs/model_probe.json` 的同款探测），挑 5 个活型号 | ~9 | 0 |
| 1 | 改 `Dual.run()` 加 `specs=None` 透传（路 A） | 0 | 0 |
| 2 | 跑**饱和域 18 题**（`direct` × 2 + `dual_select` × 2） | ≈470 | 0 |
| 3 | 跑**不饱和域 4 题**（同上） | ≈104 | 0 |
| 4 | 用 `embo-01` 嵌入两域全部文本 | 0 | ~176 |
| 5 | 按 `w_dd − w_ds` 算两域饱和度（**逐题**，再取均值） | 0 | 0 |
| 6 | 比：4 题 vs 18 题（**同尺子、同型号池、同支数**） | 0 | 0 |
| 7 | 出判决句 | 0 | 0 |

★ 步骤 2 与 3 的顺序无所谓，但**必须同一天、同一型号池**跑（共享上游随机源 ⇒ 跨天可能有别的漂移；本仓纪律：零分布作用域受限，跨批必须重新标定）。

★ **必须逐题落盘**（本组纪律：run 级原子落盘、续跑只补缺口）⇒ 对方的本地跑批若是黑盒长跑，请按这个粒度落。

---

## 7. 已有产出清单（可直接取用）

| 路径 | 内容 |
|---|---|
| ★ `HANDOVER.md` §4 | **本件事的原始配方与法律域对照数（+0.0483、范围、w_dd/w_ds 区间）+ 对四道题的预期** |
| `creativity_lab/gate_policy.py` | 饱和度版判据脚本（含 +0.0483 对照打印行） |
| `creativity_lab/diagnose_uncertainty.py` | 早期版（`conf`，无饱和度差值） |
| `creativity_lab/arms/dual.py` | `dual_fuse` / `dual_select` 两臂实现 ＋ `_diverge(specs=)` 注入点 |
| `creativity_lab/verify.py` | 断言抽取与核验 |
| `creativity_lab/client.py` | `LLM.chat` / `LLM.embed`（`embo-01`）/ `cosine` |
| `cmp8/creativity_lab/data/user4_q{1,2,3,4}.json` | 四题题面 + 依据包 |
| `creativity_lab/data/legal_topics_v2.json` | 法律 18 题题面 + 依据包 |
| `cmp8/net_gain.py` | 依据包原子事实切分口径（`facts_of()`） |
| `cmp8/runs/cmp8/` | ★ **A 篇七臂 × 四题 × 2 rep 的产出（166 项）—— 配置不同（缺口 4），不可直接当那格用，但可作旁证** |
| `cmp8/runs/cmp8/analysis.json` | 七臂的宽度 / 支持率 / 矛盾率读数（含 `judge` / `embed` 字段，是缺口 4 的证据） |
| `runs/model_probe.json` | 型号存活探测（`alive` / `dead` 名单） |

---

## 8. 明确不做的

| 不做 | 理由 |
|---|---|
| 不跑新批 | 对方明确要求「不跑新批」，他们本地跑 |
| 不改 `gate_policy.py` | 它是 A 篇判据的真相源；改数据源请另立脚本并登记 |
| 不把 `cmp8/runs/cmp8/` 当那格数据 | 配置不同（缺口 4） |
| 不用 4 题推翻 18 题对照 | 题数不等（缺口 3） |
| 不重写 A 篇正文 | 摘要定稿要等 §8.1 第 1 项闭合 |
| 不在本件里给读数 | 本件是规格；读数由对方本地跑批产生 |
