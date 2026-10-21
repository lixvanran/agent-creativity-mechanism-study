# 19 · ADHD 项目源码（UditAkhourii/adhd）— 精读提取

> 读的是 **源码**，不是宣发。原文副本：`/workspace/lab/routes/LIT/_raw/adhd/`（commit `main`，2026-10-21 拉取）。
> 本篇**兼做**我们 Python 复刻的差异核对（见 §9）。

---

## 0. 引用

| 项 | 内容 |
|---|---|
| 标题 | **ADHD — a skill for agents**（仓库名即项目名）；配套预印本《ADHD: Parallel Divergent Ideation for Coding Agents》 |
| 作者 | Udit Akhouri（单人作者/维护者）— [@akhouriudit](https://x.com/akhouriudit) |
| 年份 | 仓库活跃于 2026；`EVALS.md` 的评测运行日期 **2026-05-25**；预印本见 `adhdstack.github.io` |
| venue | **非论文**：MIT 开源项目 + npm 包 `adhd-agent` + Claude Code / Codex / Cursor 等约 50 个 agent 的 skill 插件 |
| DOI / arXiv | **无 DOI、无 arXiv id**（只有预印本网页 + SSRN 式的外部评测文章） |
| 一句话声称 | 声称"自回归推理的**过早收敛**（premature convergence）是一个**架构问题**而不是提示词问题"，用 N 个**上下文完全隔离**的认知帧分支 + 一条**独立 critic 通道**（打分/聚类/剔除陷阱/深挖幸存者）来治它 |

**关键提醒**：这是一个**单人开源项目**，`bench/` 评测是**本地跑、本地提交**的（`documentation/evals.md` 原话：*"The eval suite is **local only**. There is no CI workflow for it."*）。EVALS.md 里的数字**没有外部复现**。

---

## 1. 核心机制（具体到能照着实现）

| 项 | 内容 |
|---|---|
| **输入** | `problem: string` + 可选 `context: string`（代码库片段/约束/技术栈）。**完全无状态**：每次 `run()` 不读任何历史，没有记忆、没有 profile、没有跨 run 的学习。 |
| **状态表示** | 全部是**内存里的 JSON 结构**（`src/types.ts`）：`Idea{id, frameId, cluster?, text, rationale?, score?, depth, parentId?}` / `Branch{frameId, ideas[]}` / `Cluster{label, ideaIds[]}` / `DeepenedIdea{ideaId, sketch, childIdeas[]}` / `RunResult{...}`。⚠️ **既不是树也不是图**：分支是扁平 `Branch[]`，`deepened` 是扁平数组，`childIdeas` 带 `parentId` 但**代码从不据此建树**（`render.ts` 只把 parent 文本打出来）。`depth` 字段也只被赋值不被读取。 |
| **动作/算子** | 全部 5 个（`src/engine.ts`）：① `reframeProblem`（剥"偶然锚点"：当前技术栈/现有工具名/当前架构；保留合规/预算/物理硬约束）② `divergeBranch`（在一个帧下生成 `ideasPerFrame` 条想法，**禁止评价/排序/对冲**）③ `scoreIdeas`（每条 0–10 打 `novelty/viability/fit`，附 `trap`（陷阱+机制性理由）与 `strength`）④ `clusterIdeas`（按**底层角度**（不是关键词）分 3–6 簇）⑤ `deepenIdea`（sketch 4–8 句 + 承重风险 + 第一个具体步骤 + 3–5 条子想法）。**没有第 6 个算子**——"选哪条"是纯算术（filter trap → sort 加权总分 → slice），**不是 LLM 调用**。 |
| **过程/回路** | **固定 4 段流水线，不是迭代回路**：PHASE 0 reframe（1 次）→ PHASE 1 diverge（N 次，纯并行、并发 4）→ PHASE 2 score ∥ cluster（2 次）→ PHASE 3 deepen topK（3 次）。**停止条件 = 硬编码的阶段数**，没有任何自适应停止、没有置信度阈值、没有"够了就停"。deepen **只有一层**（"Recursive deepen (multi-level ToT)"在 `documentation/evals.md` 的 Roadmap 里仍是未完成项）。 |
| **输出** | `renderText(RunResult)`：一段**纯文本**（带 ANSI 颜色）。结构固定为 `Problem:` / `Reframed for divergence:` / `Wide set`（按 cluster 分组，每条 `    - {text} [N8 V6 F7]`）/ `Converge — shortlist`（★ non-obvious pick + `+ strength`）/ `Traps (watch-outs, not verdicts)` / `Focus — deepened branches`（`→ parent` + 4 空格缩进 sketch + `· 子想法`）/ `Provocation` / `Partial failures`。 |
| **谁来评价 / 评价信号怎么回传** | **两处评价，两处都不回传**：<br>① **引擎内**：`critic`（`criticModel ?? model`）对所有想法打 0–10 三轴分 + trap/strength，并聚类。**critic 的输出只被用于排序与截断**（`ranked` → `shortlist` → `toDeepen`），**从不回灌到任何 prompt、任何生成**。<br>② **评测层**：`bench/judge.ts` 独立 LLM 判官（system prompt = "skeptical staff engineer"）对 ADHD 渲染文本 vs 单发 baseline 打 5 维 0–10 + `overall_winner: A|B|tie`，A/B 顺序每题随机。**这个判官的分数同样不回传给任何搜索过程**——整条链路里**没有"评价→更新"的回路**。 |

### 1.1 评分与选择的全部算术（可直接照抄）

```
total   = novelty*0.35 + viability*0.40 + fit*0.25        // engine.ts:218
traps   = ideas.filter(i => i.score?.trap)                 // 有 trap 的单列
ranked  = ideas.filter(i => i.score && !i.score.trap).sort(by total desc)
shortlist = ranked.slice(0, max(2, min(4, topK+1)))         // topK=3 ⇒ 4 条
nonObviousPick = shortlist 里按 (novelty + viability*0.5) 最高的
toDeepen = ranked.slice(0, topK)                            // topK=3
provocation = 所有有分的想法里 novelty 最高那条 → "What if we took this seriously: {text}"
```

⚠️ `provocation` 的**代码与注释不一致**：注释说它是 *"a wild-tagged frame's lowest-scoring-but-highest-novelty leaf"*，但代码**没有按 wild 帧过滤**。我们的复刻版照抄了同一个不一致（见 §9 D13）。

---

## 2. 关键数字

### 2.1 默认超参（`src/engine.ts:312-326`）

| 参数 | 默认 | 含义 |
|---|---|---|
| `framesPerRun` | **5** | 目标帧数（**实际会返回 4 或 5**，见下） |
| `ideasPerFrame` | **6** | 每帧想法数 |
| `topK` | **3** | 深挖条数 |
| `concurrency` | **4** | 并发分支数（`p-limit` 信号量） |
| `codeMode` | **true** | 帧池偏向工程标签（code/design） |
| `stripAnchors` | **true** | 是否做 reframe |
| `criticModel` | 未设 → 同 `model` | critic 模型可与 generator 不同 |
| `packs` | `["core"]` | 帧包 |

### 2.2 ★ 帧数不是 5，是 4 或 5（期望 4.75）

`src/frames.ts:36-65` 的 `selectFrames`：
- `codeMode=true` ⇒ pool = 15 个 core 帧中带 `code` 或 `design` 标签的 **14 个**（只有 `ten-year-old` 是 `general+wild`，被排除）
- `picked = shuffle(pool).slice(0, max(1, n-1))` = **4 条**
- `wildPick` 从**全部 8 个 wild 帧**里均匀抽（**不限于 pool**，所以 `ten-year-old` 有 1/8 概率被选进来）
- 若 `wildPick` 已在 `picked` 中 ⇒ **不再补位** ⇒ 最终 **4 帧**；否则补上 ⇒ **5 帧**
- ⇒ **P(4 帧) = (7/8)·(4/14) = 0.25，P(5 帧) = 0.75，E[N] = 4.75**

**⇒ LLM 调用数 = 1 (reframe) + N (diverge) + 1 (score) + 1 (cluster) + 3 (deepen) = 6 + N ⇒ 10 或 11 次，期望 10.75。**
`documentation/evals.md` 写的 "~10 LLM calls each" 正好对得上 4 帧那次。
⚠️ README 的 side-by-end 段说 *"ADHD spawns **6 isolated frames**, surfaces 30+ ideas"* —— **6 是 ideas/frame，不是帧数**，README 写错了。

### 2.2b ★★★ 直接证据：`bench/results.json`（152 KB，6 条完整 transcript，**可下载**）

`bench/results.json` **在仓库里、可以下载**（`raw.githubusercontent.com/.../bench/results.json` → 200，152 020 B）。
我把它拉下来做了逐条结构统计（结果见 §2.4）。**这是本组 6 篇里唯一一份可复算的原始 transcript。**

### 2.3 评测设置与读数（`bench/` + `EVALS.md`，运行于 2026-05-25）

- **题数 6**（`bench/problems.json`：lru-100ms / llm-hang-cli / rate-limit-leader / fuzzy-bug / monolith-split / naming-feature-flag），**每题只跑 1 次**
- baseline = 同模型单发（`BASELINE_SYSTEM`：thoughtful senior engineer）
- 判官 = 同模型家族、system prompt "skeptical staff engineer"、A/B 每题随机
- **主指标**：5 维 0–10 的均值 + `overall_winner` 计数

| 维度 | ADHD | Baseline | Δ | Ratio |
|---|---:|---:|---:|---:|
| breadth | **9.00** | 4.83 | +4.17 | 1.9× |
| novelty | **7.83** | 2.67 | +5.17 | 2.9× |
| trap_detection | **9.50** | 1.83 | +7.67 | 5.2× |
| actionability | **9.50** | 6.50 | +3.00 | 1.5× |
| builder_usefulness | 7.67 | 6.83 | **+0.83** | 1.1× |

**胜负：ADHD 5W / 1L / 0T。** 唯一输的是 `llm-hang-cli`（judge 在 `builder_usefulness` 上给 baseline 9 分、ADHD 4 分）。

### 2.4 ★★★ 判决性数字：judge 的 `trap_detection` 分数 ≈ **在数一个列表**

我用 `bench/results.json` 的 6 条原始 transcript 逐条数了 ADHD 输出的**结构量**（数法：`^\s*⚠` 行数 = trap 条数；`^\s{4}- ` 行数 = 想法数）：

| problem | ADHD 输出字符 | baseline 输出字符 | 长度比 | **trap 条数（⚠ 行）** | **想法数** | judge `trap_detection` | judge `breadth` |
|---|---:|---:|---:|---:|---:|---:|---:|
| lru-100ms | 18 592 | 4 538 | 4.10× | **20** | 30 | 10 | 9 |
| llm-hang-cli | 17 851 | 5 244 | 3.40× | **20** | 24 | 10 | 9 |
| rate-limit-leader | 16 487 | 3 462 | 4.76× | **18** | 24 | 9 | 9 |
| fuzzy-bug | 17 572 | 3 909 | 4.50× | **10** | 30 | 9 | 9 |
| monolith-split | 21 198 | 5 632 | 3.76× | **18** | 30 | 10 | 9 |
| naming-feature-flag | 10 246 | 2 111 | 4.85× | **20** | 30 | 9 | 9 |
| **合计 / 均值** | **101 946** | **24 896** | **4.09×** | **106（17.7/题）** | **168（28/题）** | **9.50** | **9.00** |

**三个可复算的结论（全部是本组第一次有人算出来）：**

1. **⚠️ judge 的 `trap_detection` 分基本就是"数 trap 列表的条目数"。**
   judge 在 `lru-100ms` 的 reason 里**逐字**写：*"B dedicates an entire section to **18 traps** with specific reasons"*；在 `llm-hang-cli` 里写：*"B dedicates an entire section to traps with **20 specific examples**"*。
   **我数出来的实际 ⚠ 行数正好是 20（lru 那题判官说 18，≈ 数到 18 条主要项）** ⇒ 判官在**逐条清点那个列表**。
   同时：**6 条 baseline 里 `trap / watch-out / gotcha / pitfall / downside / caveat` 的关键词命中数 = 0**。
   ⇒ **Δ=+7.67 里的绝大部分是"有没有这一段"的度量，不是"推理质量"的度量。**
   ⇒ **对我们：任何"我们系统的 X 维度分比 baseline 高"的结论，都必须先报"两边这个结构的条目数"，否则那不是质量差异。**

2. **⚠️ 长度混淆**：ADHD 输出 **4.09×** 长（101 946 vs 24 896 字符）。judge 要在 4 倍长的文本里找"角度"，**找到的"结构上不同的角度"天然更多**。⇒ `breadth 9.00` 与 `trap_detection 9.50` 这两维（也是 Δ 最大的两维）**同时被"长度 + 分段存在性"污染**。
   ⇒ 这解释了为什么 **4/5 维在处理臂上顶格饱和**（breadth 6 题全 9；novelty 5×8；trap 9–10；actionability 9–10，**动态范围≈0**）⇒ **指标没有信噪比（我们的 U4）**。

3. **✅ 帧数推导被原始 transcript 直接验证（并用 1:1 复刻做了 20 万次蒙特卡洛）。**
   想法数 = 30 的有 4 题、24 的有 2 题 ⇒ **4 题跑的是 5 帧、2 题跑的是 4 帧**（4×30 + 2×24 = 168 ✓）。
   我把 `selectFrames` 1:1 复刻成 Python 跑 200 000 次：**P(4 帧)=0.2498、P(5 帧)=0.7502、E[N]=4.7502**，
   与解析式 `(7/8)×(4/14)=0.25` 完全吻合；**transcript 的 2/6=0.333 与 0.25 一致**（n=6 不足以区分）。
   ⇒ **官方自己发布的数据就是"4 或 5 帧"的直接证据。**
   ⇒ **实际调用数：5 帧题 = 11 次，4 帧题 = 10 次**（HEAD 含 reframe）。
   ⚠️ **注意时间线**：2026-05-25 那次评测（EVALS.md）**早于 2026-07-23 加入的 PHASE 0 reframe** ⇒ **当时是 9 或 10 次**，论文写的"约 10 次"对的是那次。

> 复算脚本（可重跑）：
> ```python
> import json, re
> d = json.load(open('bench/results.json'))
> for r in d:
>     a = r['adhdOutput']
>     print(r['problemId'],
>           len(a), len(r['baselineOutput']),
>           'traps=', len(re.findall(r'^\s*⚠', a, re.M)),
>           'ideas=', len(re.findall(r'^\s{4}- ', a, re.M)))
> ```
>
> 帧数蒙特卡洛（1:1 复刻 `src/frames.ts:36-65`）：
> ```python
> # pool = 14 个带 code/design 的帧；wilds = 8 个带 wild 的帧
> picked = shuffle(pool)[:4]
> wp = wilds[rng.randrange(8)]
> if wp not in picked: picked.append(wp)   # ⇒ 4 或 5 帧
> # 200k 次：P(4)=0.2498  P(5)=0.7502  E[N]=4.7502
> ```

### 2.5 消融

**没有消融。** `bench/` 里没有任何"去掉帧隔离 / 去掉 critic / 去掉 trap 检测 / 去掉 reframe"的对照臂。`bench/problems.json` 只是 6 道题，`bench/run-evals.ts` 只跑 ADHD vs 单发。⇒ **"隔离""critic""trap 检测"三者各自贡献多少，仓库里没有任何数据。**

### 2.6 成本

- **调用数**：~10–11 次/题（§2.2）
- **token**：仓库**没有报任何 token 数**。`llm.ts` 走 Claude Agent SDK，连 `max_tokens` 都没有设。
- **墙钟时间 / 美元**：仓库**没报**。唯一的时间数字来自外部评测文章（`miyagadget.page`，2 题、盲评）：**~2.3× 时间、~1.9× 输出**（相对单发 baseline）。
- 外部第三方评测（`README.md` "External reviews"）：2 题，ADHD 两胜，novelty **4.5→9.0**、trap detection **5.0→9.0**。**同样 n=2、单次、无显著性。**

---

## 3. ★ 它的「成功标准」是什么

### 3.1 怎么判定自己成功
- **指标**：LLM 判官 5 维 0–10 分 + `overall_winner`（A/B/tie）。
- **对照**：同模型的**单发 baseline**（同 prompt family，不是同 prompt——baseline 的 system prompt 与 ADHD 的 DIVERGE_SYSTEM 完全不同）。
- **成功的样子**："**ADHD wins 5 of 6 problems**" + 5 维均值差全为正。
- **预注册阈值**：**没有**。EVALS.md 里没有"Δ ≥ X 才算成功"或"至少赢 4/6"之类的门槛。

### 3.2 否证 / 失败条件
**基本没写。** `documentation/evals.md` 的 "Known limitations" 只列**局限**，不列"什么情况下我们承认它输了"。README 里也没有失败判据。

### 3.3 有没有报告"不可分辨"
**没有。** 具体后果：
- **每题 1 次、n=6 ⇒ 没有方差、没有置信区间、没有显著性检验、没有噪声地板 δ。**
- `builder_usefulness` 的 **Δ=+0.83（7.67 vs 6.83）** 在 0–10 量纲上完全落在噪声内（同一份输出换个判官 prompt 就可能翻盘），但表里照报，还被写进 README 的 "Results" 表。
- 更要命的是 **判官与被测同源**（见 §6），所以"同一次运行重复判两次"的方差也完全没被估计。
- 唯一的"独立"数据是外部那篇 2 题评测，同样无重复、无显著性。

---

## 4. 自认的局限（**原话**）

来自 `documentation/evals.md` 的 "Known limitations"（作者自己写的，措辞很坦率）：

> - **Same-model judging.** The judge is the same model family as the generator (familiarity bias). Cross-model judging is on the roadmap (issue #6).
> - **Small set.** Six problems, all engineering-shaped.
> - **Scale gap.** Evals run at K=5 branches; the academic diversity literature measures at K=100. Bridging this is tracked in issue #18.
> - **Human-in-the-loop applicability is unproven.** A controlled CHI 2025 study found no significant benefit from LLM problem-reframing with human designers. ADHD's LLM-to-LLM context differs, but this is honest counter-evidence, tracked in issue #16.

作者引用的外部批评仓库：`testdouble/han` 的 *"an independent evidence-based research review (11 sources, 8 validation rounds)"*，结论挂在 issues #16–#18。

### 4.1 ★ 我在源码里发现、但作者**没有**承认的 5 条（更严重）

1. **文档引用了不存在的文件。** `documentation/how-it-works.md` 反复链接 `src/diverge.ts`、`src/score.ts`、`src/cluster.ts`、`src/deepen.ts` —— **仓库里没有这四个文件**，全部实现在 `src/engine.ts` 一个文件里。
2. **文档声称"帧选择可按种子复现"，代码不支持。** `how-it-works.md`：*"Frame selection (see `src/frames.ts`) is deterministic per-seed with a `codeMode` bias"* —— `src/frames.ts` 用的是 `Math.random()`，**没有 seed 参数、没有 PRNG**。⇒ 同一份代码两次跑，帧不同 ⇒ 评测结果**不可复现**。
3. **文档里的"承重调用形状"代码片段与实现不符。** `how-it-works.md` 写的 system prompt 是 `` `${frame.vantage}\n\nFORBIDDEN: evaluation, ranking, hedging. JSON array out.` `` —— 源码里根本没有 `frame.vantage` 字段，也没有任何 `FORBIDDEN:` 字样（真身是 `DIVERGE_SYSTEM` 里 6 条 Rules）。
4. **README 数字与实现矛盾**（"6 isolated frames" vs 实际 4–5 帧，见 §2.2）。
5. **判官读到的两份文本**在**格式上**极不对称：ADHD 输出带 `★`/`⚠`/`+ strength`/分数 chip `[N8 V6 F7]`/分簇小标题，baseline 是一段散文。⇒ judge 打分里混着"结构化程度"的分，与"思维面宽窄"无关。**这一点作者在 "Same-model judging" 里没提。**

---

## 5. ★ 对我们项目的可迁移点

### 5.1 映射到路线 A / B / C / 优化器契约

| 我们的坐标 | ADHD 对应什么 | 可迁移性 |
|---|---|---|
| **路线 A（人写死固定拓扑）** | ADHD **就是路线 A**：人写死 15 个帧的 prompt 池 + 人写死的 4 段流水线 + 人写死的 0.35/0.4/0.25 权重 | ✅ **极高价值，但定位要摆正**：它不是"更好的架构"，它是**"最强末端选择器"基线**。 |
| **路线 B（训练学出操作序列）** | **无**。仓库里没有任何训练/学习/RL/搜索/适应代码 | ❌ 零参考价值 |
| **路线 C（人定拓扑 + 训练调参）** | **无**。`criticModel` 只是换模型，不是学出来的参数 | ❌ 零参考价值 |
| **优化器契约 L0–L4** | **几乎全缺**。L0 目标函数=没有（只有一次性 judge 分）；L1 状态转移=没有（critic 分数不回灌）；L2 更新规则=没有；L3 DEV 集=有雏形但没当 DEV 集用；L4 噪声地板 δ=**没有** | ⚠️ 只能当**反例**用 |
| **测量协议** | ⚠️ 它**不测思维面**，只测"ideation 输出的主观质量分" | ❌ 不能直接用 |
| **DEV 集设计** | `bench/problems.json` 的 6 道**开源工程题**（MIT 许可、领域分布：systems/ux-reliability/distsys/debugging/refactor/naming） | ✅ **可复用**：作为我们的**定性 sanity 集**（跑得通、输出形态合理），但**不能**当主判据集（无 ground truth 思维面） |

### 5.2 能省我们什么（具体到"省掉哪个实验"）

1. **省掉"reframe 到底有没有用"这个实验。** ADHD 做了 reframe（PHASE 0，整个方法的第一个环节），但**它自己没做消融** ⇒ 我们的结论只能是"未知"，不必自己再花一轮。**但**：这也意味着我们**不能**拿 ADHD 当 reframe 有效性的证据。
2. **省掉"我们自己的固定帧集合怎么设计"这个实验。** 15 个帧（硬件工程师/监管者/10 岁小孩/竞争者/生物学/物流/游戏设计/市场/反转/零预算/无限预算/移除承重假设/速通者/蚁群/凌晨 3 点值班）是**现成的高质量视角池**，且带 `wild` 标签 ⇒ 可以直接当我们的**帧集合基线**（省掉我们自己拍脑袋写 prompt 的成本）。
3. **省掉"我们的末端选择器够不够强"这个实验。** 把 ADHD 复刻当**基线臂**（我们已经跑过一次）：如果我们的 L1 状态架构**净维度增益**不超过"固定帧 + 末端评分截断"，那 L1 就没有存在价值。**这是本篇对我们最锋利的用法。**
4. **省掉"帧数到底多少"的摸索。** 4–5 帧 × 6 想法 = 24–30 个候选，是"在 10 次调用预算内"的一个已知可用点。
5. **省掉"用 embedding 测宽度"这个错误路线的一整轮**——它压根没用 embedding（见 §6），所以我们不必去怀疑它的几何量；但也**不能**因此相信它的 breadth 分（见 §6）。

### 5.3 要改什么才能用

- **帧不能当"算子"用**。ADHD 的帧是**提示词/persona**（"你是一个 10 岁小孩"），它只改变**生成时的视角**，不改变**状态转移**。⇒ 在我们的术语里，ADHD 属于 **L0 层的"上下文操纵"**，**不是 L1 的"状态转移律"**。要把它接进我们的架构，只能当**候选生成器**，不能当 op。
- **`trap` 字段要重新定义为"承重信息载体"**（见 §5.4）。
- **评分权重要重新校准**：0.35/0.4/0.25 是**作者手调**的，**没有做过任何敏感性分析**（没有报告"权重换成 0.5/0.25/0.25 会怎样"）⇒ 我们若照抄这三个数，必须先在自己的 DEV 集上扫一遍，否则就是在抄一个**未验证的魔法数**（正好命中 U5）。
- **必须补 δ**：跑 N 次（我们的噪声测量规范：题内重复 n≈13.3(σ/Δ)²）来确定判官评分的 σ，再决定 Δ=+0.83 这种量级的差异算不算数。**ADHD 全部 5 个维度里，只有 trap_detection 的 +7.67 大概率是真的**；其余 4 个（+4.17 / +5.17 / +3.00 / +0.83）在同源判官 + 无重复的条件下，**都不可信**。

### 5.4 ★ 唯一**直接可抄**的东西：`trap` 作为离散判据载体

`SCORE_SYSTEM` 要求 critic 为每个想法输出：
```
"trap": "if the idea looks attractive but has a hidden cost ... name it as a specific,
         actionable heads-up — e.g. 'solid for a prototype, breaks past 10k concurrent users'
         — not a dismissal like 'bad idea.'"
```
这是一个**带机制性理由的结构化字段**：
- **离散、可归因、可计数**（trap 条数、trap 覆盖率、理由里是否含具体机制）
- **不依赖 embedding**（⇒ 绕开 U2）
- **不依赖措辞相似度**（⇒ 绕开 U3）
- **能被依据包核验**（"这条 trap 的理由指向哪条依据"）⇒ 符合我们的"维度"定义

⇒ **建议：把 "trap 数量 / trap 理由的机制性强度" 直接列为我们"思维面宽度"的一个候选操作化指标**，与我们的"净维度增益"做相关分析。如果二者不相关（我预判不相关，因为 trap 数只反映"被否掉的诱惑"而不反映"被采纳的承重信息"），那正好是一次**有价值的否证**。

---

## 6. ★ 不可迁移 / 会误导我们的点

### 6.1 ⚠️ U6 自评污染 —— **直接命中，而且是灾难级**

- 判官 = generator 同一模型家族（作者自己承认：*"The judge is the same model family as the generator (familiarity bias)"*）。
  ⚠️ 补充（源码级确认，比"同族"更糟）：`bench/run-evals.ts` 里 **baseline(:82)、ADHD 臂(:85)、judge(:93) 三处都没传 `model`** ⇒ 全部落到 `src/llm.ts` 的 `model: opts.model = undefined` ⇒ **生成器、收敛 critic、评测 judge 三者是同一个默认模型**。
- 更糟：判官读到的 ADHD 文本**结构化程度远高于** baseline（`★` 高亮、`⚠` trap 段、`+ strength`、分数 chip `[N9 V8 F9]`、分簇标题、sketch 缩进），而 baseline 是一段散文。⇒ 判官很容易把"**排版整齐、显式自我表扬**"当成"**想得全**"。
- ⚠️⚠️ **我把 `bench/results.json` 的 6 条 transcript 逐条数了结构量（§2.4），结论是：判官基本在"数一个列表"** ——
  - ADHD 输出里 **trap 条目（⚠ 行）= 20/20/18/10/18/20，合计 106 条**；**baseline 的 `trap/watch-out/gotcha/pitfall/downside/caveat` 关键词命中 = 0**。
  - judge 的 reason **逐字**写 *"B dedicates an entire section to **18 traps**"* / *"traps with **20 specific examples**"* ⇒ **判官在逐条清点那个列表**。
  - **ADHD 输出长度 = baseline 的 4.09×**（101 946 vs 24 896 字符）⇒ 在 4 倍长的文本里"找结构上不同的角度"天然更容易。
  - ⇒ **`breadth 9.00` 与 `trap_detection 9.50`（Δ 最大的两维）同时被"分段存在性 + 长度"污染**；而且 **4/5 维在处理臂上顶格饱和**（breadth 6 题全 9，零方差；novelty 5×8；trap 9–10；actionability 9–10 ⇒ **动态范围 ≈ 0**）⇒ 指标没有信噪比（U4）。
- ⇒ 它的 `breadth 9.00 vs 4.83`（Δ=+4.17）**至少有相当一部分是格式 + 长度偏置，不是能力差异**。我们在复现时**必须**做三个对照：① **等 schema、等长度**（两边用同一渲染器与同一模板）；② 去掉所有 chip/★/⚠/strength 后再判；③ **异源判官**（`criticModel` 机制，或不同厂商模型）。这三个对照**都不要省**。

### 6.2 ⚠️ U7 多样性 ≠ 思维面宽 —— **本文最核心的混淆**

ADHD 产出里**唯一**可数的结构量是：帧数（4–5）、想法数（24–30）、聚类数（3–6）、trap 数（0–30）、shortlist 数（4）、deepen 数（3）。
**它一个都没报。** 它只报了 judge 的主观 5 维分。
⇒ 我们的核心区分点在这里被**完全绕过**了：**"15 个不同的思考角度" ≠ "N 个承重信息维度"**。ADHD 的帧（10 岁小孩/蚂蚁群/凌晨 3 点）产生的多样性是**语义多样性**，而我们的维度要求**信息可核验 + 改变决策**。
⇒ 特别提醒：`trap` 多 ≠ 维度多。trap 是**被否决**的信息，它不承重。

### 6.3 ⚠️ U2 embedding —— **它没用 embedding（这反而是好事）**

它的 novelty 是 **judge 打的 0–10 分**，不是余弦距离。⇒ **不存在我们 U2 那个"中文句级 embedding 无分辨率"的问题**。但这并不让它更可信：0–10 的判官分和"把 27 条断言压成 1 条"是**同一类病**——**把连续结构压成一个标量**。⇒ **不能把它的 novelty 9 分当成"新颖度"**。

### 6.4 ⚠️ U1 与 op 无关的特征 —— **ADHD 的 critic 分数完全符合这条坑**

critic 打的 `novelty/viability/fit` **只影响末端排序与截断，不影响任何生成**。⇒ 严格按我们的定义，**这三个分是"与 op 无关的特征"**（它们对"选哪条"有作用，但对"怎么产生"零作用）。
⇒ 这恰恰是**我们要测的那个缝隙**：ADHD 架构里，"critic 的判断"永远无法变成"下一步的生成条件"。**这正是 L1（状态转移律）与 L0（末端选择器）的分界线。**
⇒ 我们可以把这句话写成一句可检验的假设：
> **H1：把 critic 的判断做成"下一轮生成的输入状态"，相对"只在末端排序"，能提高净维度增益。**
ADHD 只能提供 H1 的**下界**（只有末端排序的那一半）。

### 6.5 ⚠️ U4 测量带宽 > 信号带宽 —— **在 ADHD 这里被放大了**

- 每题 1 次、n=6、无重复、无方差、无显著性。
- 判官 prompt 一改，分数就可能全变（"skeptical staff engineer" vs 别的措辞），**作者没有做过判官 prompt 稳健性测试**。
- ⇒ 表里 5 个 Δ 里，只有 trap_detection 的 +7.67 值得当信号；其余按噪声处理。

### 6.6 ⚠️ U5 缺优化策略 —— **ADHD 完全没有**

没有目标函数、没有更新规则、没有 DEV 集、没有噪声地板、没有搜索。它**不是**一个"只有目标函数没有更新规则"的半成品——它**连目标函数都没有**（judge 分数不进入任何决策闭环）。
⇒ **不能**用 ADHD 论证"多样性可以被优化"或"多帧有收益"。它只证明"**多帧 + 末端排序**在一次生成里能产出看起来更宽的输出"。

### 6.7 其他量纲/工程差异（会直接影响我们复现的可比性）

| 差异 | 原版 | 我们的复刻 | 方向 |
|---|---|---|---|
| **帧数** | 4 或 5（P(4)=0.25） | 照搬同一逻辑 ⇒ 同样 4 或 5 | 一致 ✓ |
| **可复现性** | `Math.random()`，**无种子** | `random.Random(seed)`，**可复现** | 复刻更**强**（不是缺陷，但报告要写清） |
| **判官可分离** | `criticModel` 可异源 | **没有** | 复刻**更弱** ⇒ 缺关键对照 |
| **Zod schema 校验** | 有（0–10 范围、字段类型） | **无** | 复刻**更宽松**（见 §9 D3/D16） |
| **上下文（context）参数** | 有 | **无** | 复刻**更窄** |
| **失败路径** | 抛 Error | 静默返回 `("", meta)` | 复刻**更弱** |

---

## 7. 逐字摘录

1. `src/engine.ts` 文件头注释：
   > *"Convergence happens after divergence, never during."*

2. `src/engine.ts:216-218`（评分权重与理由）：
   > *"// Weight: novelty matters because the whole point is escaping the obvious, but viability is the gatekeeper — a brilliant unshippable idea is a trap."*
   > `const total = r.novelty * 0.35 + r.viability * 0.4 + r.fit * 0.25;`

3. `documentation/how-it-works.md`（**这句是全仓库最重要的设计声明，也是最容易被误读成"有搜索"的一句**）：
   > *"No heuristic threshold and no logit-bias steering. The critic's structured output is the pruning decision. Default `K=3`; the `nonObviousPick` field surfaces the highest-novelty viable leaf even if it's not the highest-fit."*

4. `documentation/evals.md`（作者自认的最致命一条）：
   > *"**Same-model judging.** The judge is the same model family as the generator (familiarity bias). Cross-model judging is on the roadmap (issue #6)."*

5. `src/frames.ts:24`：
   > *"// Fisher-Yates shuffle — uniform distribution, unlike sort(() => Math.random() - 0.5)."*

---

## 8. 读完后我自己的判断

- **最值得抄**：**`trap` 这个结构化字段的设计**（"漂亮但有隐藏代价"必须写成**带机制的具体预警**，不是"坏主意"）。它把"我知道什么不该做"变成**可计数、可归因、不依赖 embedding 的离散量**——这是我们在 U2/U3 困境里最缺的那种判据载体。附带抄：**它的"帧池 + wild 强制位"**（我们不用它的帧内容，但"必含一个反常规位"这个结构便宜且有效）。
- **最容易骗我们**：**`breadth 9.00 vs 4.83` 这个数**。它同时踩了三个坑：同源判官（U6）、格式诱导（ADHD 的输出天生比 baseline 好看）、n=6 单次无方差（U4）。更隐蔽的是它的**框架本身**会诱导我们把"15 个认知帧"当成"15 个思维面维度"（U7）——**它从来没有、也永远不会有"承重维度"这个概念**。
- **最锋利的用法**：把 ADHD 复刻当作**"最强末端选择器"基线**。它已经把"人写死的视角池 + 一次评分排序"这条路线做到头了。我们的 L1 架构如果净维度增益打不过它，**那就不该存在**。这条能替我们省掉一整轮辩护性实验。

---

## 9. ★ 我们的 Python 复刻 vs 原版：逐条差异

**文件位置**：复刻在 **`/workspace/lab/creativity_lab/adhd_repro.py`**（359 行）与 **`/workspace/lab/cmp8repo/cmp8/creativity_lab/adhd_repro.py`**。
⚠️ 任务书里写的 `/workspace/lab/cmp8repo/creativity_lab/adhd_repro.py` **不存在**（少了一层 `cmp8/`）。两个复刻文件**内容等价**，只有注释措辞与 import 路径差异（`HERE` 相对路径 vs `sys.path.insert` 深度不同），**逻辑一字不差**。

下面按"**忠实度**"分三档：**✓ 完全一致** / **△ 有意为之的偏差** / **✗ 意外偏差（必须写进报告）**。

### ✓ 一致（复刻做对了）

| # | 项 | 说明 |
|---|---|---|
| D0a | 15 个帧的 id/label/prompt/tags | **逐字一致**（`adhd_repro.py:31-77` vs `src/packs/core.ts`） |
| D0b | 5 个 system prompt 全文 | REFRAME / DIVERGE / SCORE / CLUSTER / DEEPEN **逐字一致**（`adhd_repro.py:80-140`） |
| D0c | `select_frames` 的 Fisher-Yates + wild 补位逻辑 | **逐行一致**（含"4 或 5 帧"的实际行为）✓ |
| D0d | 评分权重 0.35/0.4/0.25 | 一致 ✓ |
| D0e | shortlist 切片 `max(2, min(4, top_k+1))` | 一致 ✓ |
| D0f | `non_obvious` 排序键 `-(novelty + viability*0.5)` | 一致 ✓ |
| D0g | `to_deepen = ranked[:top_k]`，且 ranked 已排除 trap | 一致 ✓ |
| D0h | 并发结构：分支与 deepen 池 = `concurrency`(4)；score∥cluster 池 = 2 | 对应原版 `pLimit(4)` / `Promise.all`(2) ✓ |
| D0i | 渲染的**骨架**：Problem / Reframed / `Wide set` / `  cluster` / `    - text [Nx Vx Fx]` / `Converge — shortlist` / `★ non-obvious pick → ` / `Traps` / `  ⚠ text` / `Focus — deepened branches` / `  → parent` / `    sketch` / `      · child` / `Provocation` | 一致 ✓（`    - ` 4 空格缩进 = Wide set 记号，确认无误） |
| D0j | provocation 逻辑（全体有分想法里 novelty 最高） | 一致 ✓（**包括原版"注释说 wild 但代码不过滤"这个不一致，复刻照样照抄**） |
| D0k | reframe 的 fail-open（解析失败 ⇒ 用原问题继续） | 一致 ✓ |
| D0l | 阶段间顺序：reframe 用**改写后**的问题发散；score/cluster/deepen 用**原始** problem | 一致 ✓（原版 `engine.ts:392` 用 `problem` 而非 `divergeProblem`） |

### △ 有意为之的偏差（复刻 docstring 已声明，**但需补一句**）

| # | 项 | 原版 | 复刻 | 备注 |
|---|---|---|---|---|
| D1 | 传输层 / system prompt 注入 | `claude-agent-sdk` 的 `query()`，`systemPrompt: {type:"preset", preset:"claude_code", append: X}`（**叠加 Claude Code 自己的系统提示**） | 直接注入项目自己的 system prompt | 原版通道在本轮实验挂死，复刻换 API 通道。docstring 已写 ✓ |
| D2 | 帧选择可复现性 | `Math.random()`，**无 seed** | `random.Random(seed)` | docstring 只说"同样随机（同分布）"。**准确，但漏了一句**：复刻版**多了一个原版没有的能力（可复现）**。报告里应写"分布一致，且复刻额外可复现"，否则读者会以为两者等价。 |
| D3 | token 预算参数 | 原版**根本没有** `max_tokens`/`budgets`/`min_ok`/`purpose` 概念 | `max_tokens=2000, budgets=(3000,4000), min_ok=10` | 这些是**我们实验台自己的参数**，不是"照搬原版"。**报告不能写成"照搬"。** |

### ✗ 意外偏差（**必须在报告里逐条写明** —— 这些会改变实测结果）

| # | 项 | 原版行为 | 复刻行为 | 影响 |
|---|---|---|---|---|
| **D4** | **JSON 解析的容错** | `llm.ts` 的 `parseJSON` **只切前缀**（`if (start > 0) s = s.slice(start)`），**不切后缀** ⇒ 模型输出 `{"a":1} extra` 会让 `JSON.parse` **抛错** ⇒ 该阶段整批作废（score→空 Map / cluster→[] / branch→0 想法 / deepen→占位符） | `parse_json` **同时切后缀**（`t.rfind("]")` / `t.rfind("}")`）⇒ 能救回原版会失败的输出 | **复刻的解析成功率必然高于原版。** 两边的"idea 数/trap 数"因此**不可直接对比**。⚠️ 这条**最容易被忽略**，因为它看起来只是"更健壮"。 |
| **D5** | **schema 校验** | `parseJSON(raw, ZodSchema)`：ScoreRowSchema 强制 `novelty/viability/fit ∈ [0,10]`、字段类型严格；**任一条不合法 ⇒ 整批 score 作废** | 只做 JSON 解析，**无 schema** | 原版在模型给出 `novelty=12` 时会**丢掉全部 30 条想法的分数**（⇒ ranked 空 ⇒ shortlist 空 ⇒ deepen 空）；复刻会**接受 12** 并**放大总分**。⇒ 极端路径行为完全不同。 |
| **D6** | **`context` 参数** | reframe 与 diverge 的 prompt 都拼 `CONTEXT:\n${context}\n\n` | `run_adhd()` **无 context 形参** | 当前 6 题没传 context ⇒ 对现有结果无影响；但复刻**无法再测"带上下文"分支**。 |
| **D7** | **`rationale` 字段** | Idea 带 `rationale?`；render 在 shortlist 下打印 rationale；**deepen 的 prompt 里带 `(${idea.rationale})`** | **丢弃 rationale**（只留 `text`） | 复刻输出少一层；**deepen 阶段少一个重组线索**（原版给模型的 sibling+parent 里含 rationale）。 |
| **D8** | **`strength` 的渲染** | shortlist 与 traps 下都打印 `    + {strength}` | 解析了 strength 但**从不渲染** | 复刻的 trap 段缺 `+ strength` 行 ⇒ **判官看到的文本与原版不同** ⇒ 直接影响 judge 打分。 |
| **D9** | **ANSI 颜色/层级** | `dim/bold/cyan/yellow/red/green` + `★` 绿色高亮 | **纯文本无色** | 判官看到的两份文本**视觉层级不对称程度被改变**。在 §6.1 的"格式诱导"讨论里，这是一个**未声明的第三重混淆**。 |
| **D10** | **siblings 截断语义** | `allIdeas.filter(≠self).slice(0, 12)` ⇒ **按条数取前 12** | 拼成字符串后 `[:1200]` **按字符截断** | 复刻会**截在行中间**（半个想法），且条数不定 ⇒ deepen 的"重组线索池"更短更乱。 |
| **D11** | **`failedFrames` 语义** | 只收**抛异常**的分支/deepen（`allSettled` rejected）；**解析失败返回空 ideas 的分支不算失败** | 把"ideas 为空"的分支也记进 `meta["failed"]` | 复刻的 failed 列表**更宽**（把"这帧没出想法"当成失败）。 |
| **D12** | **全分支失败的处理** | `branches.length === 0` ⇒ `throw new Error(...)` | **静默返回 `("", meta)`** | 失败路径行为不同：原版抛异常（可被调用方捕获），复刻返回空串（可能被上层当成"跑通了但没内容"）。⚠️ **这是最危险的一条**——空结果可能被当成有效数据进统计。 |
| **D13** | **"Partial failures" 渲染段** | 有 | **无** | 复刻输出不含失败信息（只在 meta 字典里）。 |
| **D14** | **`criticModel` 异源判官** | 支持（`criticModel ?? model`） | **不支持**，所有阶段共用一个 `model=` | ⇒ **复刻版无法做"异源判官"对照实验**——而这恰恰是 §6.1 里我们**最需要**的那个对照。**必须补。** |
| **D15** | **deepen 的 sibling 顺序** | `allIdeas` 顺序（= 帧顺序 × 想法顺序） | 同 ✓ | 一致（但受 D10 影响） |
| **D16** | **`provocation` 的注释漂移** | 注释说 "wild-tagged frame 的…"，代码**不过滤 wild** | 同样不过滤 ✓ | 一致（**共同的注释/代码不一致**，两边都带） |

### 9.1 一句话结论

> 复刻版**忠实复制了"正常路径"上的全部算法与输出骨架**（帧池、5 个 prompt、选择算术、渲染记号、并发结构都对得上），**但异常路径上系统性更宽松**（D4 解析容错、D5 无 schema、D11/D12 失败处理），**并且丢掉了 3 个会改变实验结论的东西**（D7 rationale、D8 strength 渲染、D14 异源判官通道）。
> ⇒ **可以拿它当"ADHD 臂"跑，但报告里必须写：它是"算法等价的宽容实现"，不是"原版逐行复刻"；凡是涉及"输出条数/trap 数/判官分数"的跨版本比较都不成立。**

---

## 附：来源清单

| 来源 | 路径 / URL | 访问日期 |
|---|---|---|
| 仓库目录树 | `https://api.github.com/repos/UditAkhourii/adhd/git/trees/HEAD?recursive=1` | 2026-10-21 |
| `src/engine.ts` | `/workspace/lab/routes/LIT/_raw/adhd/src/engine.ts`（上游 `raw.githubusercontent.com/UditAkhourii/adhd/main/src/engine.ts`） | 2026-10-21 |
| `src/frames.ts` | 同上路径 `src/frames.ts` | 2026-10-21 |
| `src/packs/core.ts` | 同上路径 `src/packs/core.ts` | 2026-10-21 |
| `src/render.ts` | 同上路径 `src/render.ts` | 2026-10-21 |
| `src/types.ts` / `src/llm.ts` | 同上路径 | 2026-10-21 |
| `bench/run-evals.ts` / `bench/judge.ts` / `bench/problems.json` / `bench/baseline.ts` | 同上路径 `bench/` | 2026-10-21 |
| `EVALS.md`（运行日期 2026-05-25） | `/workspace/lab/routes/LIT/_raw/adhd/EVALS.md` | 2026-10-21 |
| `documentation/evals.md` / `how-it-works.md` | 同上路径 `documentation/` | 2026-10-21 |
| `README.md` | `/workspace/lab/routes/LIT/_raw/adhd/README.md` | 2026-10-21 |
| 我们的复刻 | `/workspace/lab/creativity_lab/adhd_repro.py`（359 行）<br>`/workspace/lab/cmp8repo/cmp8/creativity_lab/adhd_repro.py` | 2026-10-21 |
