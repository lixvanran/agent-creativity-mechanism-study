# 21 · ADHD: Parallel Divergent Ideation for Coding Agents（精读提取）

> 精读对象：预印本单页论文 `https://adhdstack.github.io/`（v0.1，2026-05-25），配套代码仓库 `github.com/UditAkhourii/adhd`（HEAD `7b91ce6`，2026-10-06）。
> 提取日期：2026-10-21。凡标「本人复核」的数字均由我直接读 `bench/results.json` / 源码重新计算，非论文原话。

---

## 0. 引用

- **标题**：ADHD: Parallel Divergent Ideation for Coding Agents
- **作者**：Udit Akhouri Raj（**单作者**，无 et al.）
- **年份**：2026
- **venue**：**无**。自印预印本，GitHub Pages 单页（`adhdstack.github.io`），MIT 许可。页脚给出的引用格式是：
  > "Akhouri Raj, U. ADHD: Parallel Divergent Ideation for Coding Agents. 2026. adhdstack.github.io."
- **DOI / arXiv id**：**无**。我用 arXiv API 核对过：`search_query=all:"Parallel Divergent Ideation"` → **0 条 entry**；`ti:"ADHD"` → 20 条 entry，逐条看过标题，**全部是临床注意力缺陷多动障碍研究或别的作者**，没有本文；`au:"Akhouri"` → 10 条，是同姓物理学家（qubit dynamics 等），与本文无关。仓库内无 OpenReview、无 DOI 字段。**结论：这是一篇没有进入任何同行评议索引的预印本**，证据等级按"个人发布 + 自评"计。
- **代码 / 制品**：`github.com/UditAkhourii/adhd`（MIT，npm 包 `adhd-agent@0.1.4`）。
- **一句话——它声称自己解决了什么**：LLM 在开放式构思任务上会 **premature convergence**（只会给出"资深工程师 30 秒能想到的三个答案"）；ADHD 用 **N 个互不可见的并行分支**（各带一个"认知框架"）产生发散，再用一个**独立的 critic 回合**做打分/聚类/加深top-K，声称在 6 道开放式工程题上以同模型对单发 baseline 取得 **5W/1L/0T**，并在 novelty(+5.17)、breadth(+4.17)、trap detection(+7.67) 上大幅领先。

---

## 1. 核心机制（具体到能照着实现）

源码事实优先于论文措辞。论文里的机制描述与 `src/engine.ts`（HEAD）基本一致，但**论文对应的是 2026-05-25 的代码版本**（见 §6f）。

| 项 | 内容 |
|---|---|
| **输入** | 一个自由文本 `problem`（外加可选 `context`）。无状态、无多轮、无历史记忆。评测集 = 6 道题（`bench/problems.json`），全是工程题：LRU 缓存 / CLI 挂起重试 UX / leader election 限流器 / 0.1% 间歇超时 / 20 万行 Rails 单体拆分 / feature-flag 命名。 |
| **状态表示** | 纯内存对象树，**没有任何向量/embedding/图结构**：`Branch[] → Idea[]`（字段 `id / frameId / text / rationale / depth / score{novelty, viability, fit, total, trap, strength} / cluster`）→ `Cluster[]`（`label + ideaIds`）→ `DeepenedIdea[]`（`sketch + childIdeas[]`）。最终渲染成**纯文本**报告，每个叶子带一个分数 chip `[N7 V8 F9]`（`src/render.ts:17-21`）。 |
| **动作/算子（全枚举）** | ① `selectFrames(n, codeMode, packs)`（`src/frames.ts:36`）——从 15 帧库里抽 N 个；`codeMode=true` 时只保留带 `code`/`design` 标签的帧，并**强制留一个 `wild` 帧**；② `reframeProblem()`（**仅 HEAD 有**，见下）；③ `divergeBranch()` × N（`src/engine.ts:144`）——每帧一次独立 LLM 调用；④ `scoreIdeas()`（`engine.ts:185`）——**一次** critic 调用给全部叶子打 3 轴分并可标 trap；⑤ `clusterIdeas()`（`engine.ts:231`）——**一次** critic 调用做 3–6 组聚类；⑥ shortlist / nonObviousPick 选取（纯代码，`engine.ts:404-419`）；⑦ `deepenIdea()` × K（`engine.ts:259`）——每条一个调用，产 sketch + 3–5 个 child idea；⑧ wildcard provocation（**零调用**，纯代码挑 novelty 最高的叶子，`engine.ts:449-454`）。 |
| **过程/回路 + 停止条件** | **两阶段、单趟、无循环、无搜索、无回传**。停止条件**纯粹是计数**：`N=5` 帧 × `k=6` 想法；shortlist = `max(2, min(4, topK+1))` = **固定 4 条**；deepen `topK=3`；每次调用一次性返回，不迭代。**没有"再展开一轮"、没有"分数不达标就重试"、没有自适应停止。** ⚠️ 值得注意：作者的 skill 源规格（`skills/adhd/SKILL.md:187`）里**写了**一条自适应停止规则（"When to stop diverging? Stop when new candidates start repeating the shape of existing ones. The space is mapped. Do not pad to hit a number."），但**代码里没有实现**——实现是固定计数。 |
| **分支隔离的实现方式** | **真隔离，不是提示词约束**：`src/llm.ts` 对每个分支调一次 Claude Agent SDK 的 `query()`，**stateless session、`tools: []`（不挂工具）**、除 `claude_code` preset 外无共享 system prompt、**无共享 message history**。论文原话："Anchoring is eliminated by construction, not by prompting." ⚠️ 但注意两点：① 所有分支看到**同一个 problem**（HEAD 上还是同一个 reframe 后的 problem），真正变化的只有 frame prompt；② **隔离只存在于 Phase 1**——deepen 调用会拿到**最多 12 条其它分支的想法**做重组（`engine.ts:272-277`），即收敛阶段是跨分支可见的。 |
| **输出** | 文本报告，固定 5 段：`Problem` → `Wide set`（按 cluster 标签分组的全部叶子）→ `Converge — shortlist`（4 条，带 ★ non-obvious pick）→ `Traps (look good, aren't)`（每条附一行原因）→ `Focus — deepened branches`（3 条 sketch + `branches off:` 子想法）→ `Provocation`（一句）。 |
| **谁来评价 + 评价信号怎么回传** | **三层评价，两层同源**：<br>① **critic（score + cluster）** = pipeline 内部的"评委"。`engine.ts:330`：`const critic = criticModel ?? model;` → **默认与生成器同模型**（`criticModel` 选项是 2026-06-30 才加的，评测当时不存在）。它给每条想法打 novelty/viability/fit 三轴分，可标 trap。<br>② **打分如何回传搜索**：**不回传**。critic 的输出只用于**剪枝与选择**（排 top-K、剔 trap、选 non-obvious pick），**没有任何"分数 → 改写 prompt → 再生成"的回路**。这是"一次筛选"而不是"优化"。<br>③ **judge（外部判官）** = `bench/judge.ts`，独立调用，盲评 A/B，5 维 0–10 + `overall_winner` + `one_line_summary`。`bench/run-evals.ts:93` 调 `judge(problem, outA, outB)` **不传 model** → 与生成器**同模型族**（也是 SDK 默认模型；评测记录里**没有存模型名**）。 |
| **评分维度 / 权重 / 聚类算法 / 硬编码数字** | ⚠️ **这些论文正文里没有，源码里有**：<br>• **加权总分**：`total = novelty*0.35 + viability*0.4 + fit*0.25`（`engine.ts:218`；2026-05-25 版本同值，已用 `git show 9a46221:src/engine.ts` 核对）。代码注释："viability is the gatekeeper"。<br>• **聚类算法**：**没有算法**——是一次 LLM 调用，prompt 要求 "group ideas into 3-6 clusters by their UNDERLYING ANGLE (not by surface keywords)"（`engine.ts:91-94`），**不使用 embedding、不使用相似度、不使用 k-means**。<br>• **non-obvious pick 规则**：`max(novelty + viability*0.5)`，在 shortlist 内（`engine.ts:412-419`）。<br>• **shortlist 长度**：恒 4（`topK+1` 上限 4）。<br>• **deepen top-K**：按 `total` 排序、**排除 trap**（`engine.ts:404-408`）。<br>• **provocation**：取**全体**叶子中 novelty 最高者（**不排除 trap**，`engine.ts:449-451`）。 |
| **总调用次数** | **评测当时 = 10 次**（5 diverge + 1 score + 1 cluster + 3 deepen），与论文一致。⚠️ **仓库 HEAD = 11 次**：2026-07-23 的 commit `b670af0`（"Add anchor-stripping pre-pass before fan-out"）加了一个 PHASE 0 reframe 调用（`stripAnchors` 默认 `true`），**论文完全没提这一步**。 |
| **失败处理（fail-soft）** | 全部静默降级：reframe 解析失败 → 用原 problem 继续；某分支解析失败 → **该分支变成空**（不重试、不报错）；score 解析失败 → **score map 为空 ⇒ 无 shortlist、无 deepen**（整个收敛阶段静默消失）；cluster 解析失败 → `[]`（全部叶子落进 "(unclustered)"）。**只有"全部分支都炸"才 throw**（`engine.ts:382-386`）。 |

---

## 2. 关键数字

### 2.1 实验设置
- 题数 **6**；**每题只跑 1 次**（无重复、无多种子）。
- 配置（`bench/run-evals.ts:34-42`）：`framesPerRun: 5, ideasPerFrame: 6, topK: 3, concurrency: 4, codeMode: true`。
- **模型：未记录**。generator / critic / judge 全部走 SDK 默认模型（`model` 一律不传）⇒ **三者同源**。`tests/llm.test.ts:8` 里出现过 `claude-sonnet-4-5`，但那只是单测桩，**不是评测用的模型**。
- 判官 prompt 全文见 `bench/judge.ts:25-39`（"You are a skeptical staff engineer…" + 五维 rubric + "Output JSON only"），用户 prompt 结构见 `judge.ts:47-69`。
- A/B 顺序：每题**随机一次**（`run-evals.ts:88` `Math.random() < 0.5`，**无种子**）。实测 4 题 swapped=true、2 题 swapped=false（lru-100ms / llm-hang-cli / rate-limit-leader / fuzzy-bug 为 true；monolith-split / naming-feature-flag 为 false）。

### 2.2 聚合分数（论文表 + 我从 `bench/results.json` 重算，**完全一致**）
| Dimension | ADHD | Baseline | Δ |
|---|---:|---:|---:|
| breadth | 9.00 | 4.83 | +4.17 |
| novelty | 7.83 | 2.67 | +5.17 |
| trap_detection | 9.50 | 1.83 | +7.67 |
| actionability | 9.50 | 6.50 | +3.00 |
| builder_usefulness | 7.67 | 6.83 | +0.83 |

### 2.3 逐题胜负与逐题分数（本人从 `bench/results.json` 复核）
| 题 | category | breadth | novelty | trap | action | builder | 胜者 |
|---|---|---:|---:|---:|---:|---:|---|
| lru-100ms | systems | 9 / 4 | 7 / 3 | 10 / 2 | 9 / 8 | 8 / 7 | **ADHD** |
| llm-hang-cli | ux/reliability | 9 / 6 | 8 / 3 | 10 / 2 | 9 / 8 | **4 / 9** | **baseline**（唯一败局） |
| rate-limit-leader | distsys | 9 / 5 | 8 / 3 | 9 / 2 | 10 / 7 | 9 / 6 | **ADHD** |
| fuzzy-bug | debugging | 9 / 6 | 8 / 3 | 9 / 1 | 10 / 7 | 8 / 7 | **ADHD** |
| monolith-split | refactor | 9 / 4 | 8 / 2 | 10 / 3 | 9 / 6 | 8 / 7 | **ADHD** |
| naming-feature-flag | naming | 9 / 4 | 8 / 2 | 9 / 1 | 10 / 3 | 9 / 5 | **ADHD** |
| **合计** | | 9.00/4.83 | 7.83/2.67 | 9.50/1.83 | 9.50/6.50 | 7.67/6.83 | **5W / 1L / 0T** |

**关键结构读数（本人从渲染产物里数出来的，论文里没有）**：
| 题 | 发散叶子数 | cluster 标签数 | shortlist | trap 条数 | deepen 分支 | child 想法 | 最高 N 分 | ADHD 字符数 | baseline 字符数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| lru-100ms | 30 | 7 | 4 | 20 | 3 | 15 | 10 | 18,592 | 4,538 |
| llm-hang-cli | **24** | 6 | 4 | 20 | 3 | 15 | 9 | 17,851 | 5,244 |
| rate-limit-leader | **24** | 5 | 4 | 18 | 3 | 15 | 9 | 16,487 | 3,462 |
| fuzzy-bug | 30 | 6 | 4 | 10 | 3 | 15 | 8 | 17,572 | 3,909 |
| monolith-split | 30 | 6 | 4 | 18 | 3 | 15 | 10 | 21,198 | 5,632 |
| naming-feature-flag | 30 | 7 | 4 | 20 | 3 | 15 | 10 | 10,246 | 2,111 |
| **合计** | **168**（名义 180） | 37 | 24 | **106** | 18 | 90 | — | — | — |

要点：
- **168 ≠ 180**（5×6×6）：**这是 2 道题只拿到 24 个叶子**（llm-hang-cli、rate-limit-leader），另外 4 道题是 30 个。
  ⚠️ **归因更正（本组交叉复核）**：这**不是**"有分支少产或解析丢失"——`src/frames.ts:36` 的 `selectFrames(5, true, packs)` 会**返回 4 帧或 5 帧**：它先取 `shuffle(pool).slice(0, n-1)=4` 个工程帧，再从 8 个 wild 帧里随机抽 1 个，**若抽中的 wild 已经在那 4 个里则不补入**（`frames.ts:63` 的 `if (!picked.find(...))`）⇒ 4 帧；否则补上 ⇒ 5 帧。理论 **P(4 帧) = (7/8)×(4/14) = 0.25**。
  我用 1:1 复刻该函数跑了 200 000 次：**P(4 帧)=0.2498、P(5 帧)=0.7502、E[N]=4.7502**，与理论完全吻合；**transcript 的 2/6 = 0.333 与 0.25 一致（n=6 不足以区分）**。⇒ **4 帧 × 6 = 24，5 帧 × 6 = 30，4×30 + 2×24 = 168 ✓。**
  ⇒ 顺带修正调用数：**HEAD = 10 或 11 次**（reframe + N + score + cluster + 3 deepen），**评测当时（2026-05-25，reframe 尚未加入）= 9 或 10 次**。
- cluster 标签实际是 **5–7 个**（各题标签如 `periodic-batch-flush plays` / `economic-incentive plays` / `hardware-backed shared-memory plays` / `game-mechanics-lens plays` / `bet-the-company plays` / `circuit-protection plays`），**论文正文说的是 "6–9 structurally different angles per problem"**（Analysis 节）——比自己的产物高。
- **trap 总数 106 条**（每条附一行机制性理由），这是整个产物里最"结构化"的东西。
- ADHD 输出体量是 baseline 的 **3.4–4.9 倍**（合计 101 946 vs 24 896 字符，**4.09×**）。
- ⚠️ **判官在"数列表"**：judge 的 reason 逐字写 *"B dedicates an entire section to **18 traps**"*（lru-100ms）/ *"traps with **20 specific examples**"*（llm-hang-cli），与我数出的 ⚠ 行数（20 / 20）吻合；而 **6 条 baseline 的 `trap/watch-out/gotcha/pitfall/downside/caveat` 关键词命中 = 0**。⇒ **`trap_detection` 的 Δ=+7.67 基本是"这一段有多少条"的度量**，且长度 4.09× 的混淆同时作用在 `breadth` 上。

### 2.4 消融
**没有消融。** 论文与仓库里**不存在**任何"去掉帧隔离 / 去掉 critic / 去掉 trap 检测 / 去掉 cluster / 去掉 deepen / 把 N 调成 1"的对照实验。`documentation/evals.md` 的 roadmap 里把 "Pluggable scorers"、"Frame packs"、"Memory across runs" 列为**未来工作**。唯一接近消融的是 Limitations 段的一句自认："A fairer ablation would equip the baseline with the same output schema"（即作者自己承认 deepen 给了 ADHD 结构优势，但**没有做**这个消融）。

### 2.5 成本
- 论文：约 **10 次调用** vs baseline 1 次；concurrency 4 下墙钟 **30–90 s**；原话 "spend US$0.30 to widen a US$50k architecture decision"。
- **无 token 数、无单次调用耗时、无逐项美元账**：`bench/results.json` 每行只有 `problemId / category / problem / swapped / baselineOutput / adhdOutput / verdict`（我逐字段核过，**没有任何 token/time/cost/frame/seed 字段**）。
- 仓库 `documentation/when-to-use.md` 给了比论文更诚实的成本公式（论文正文没有）：
  ```
  cost ≈ N × (base_context + branch_output)   ← divergence
       + critic_context                        ← score + cluster see all N×k ideas
       + K × deepen_context                    ← focus passes
  ```
  并指出 "If the base substrate is ~26K tokens, five branches re-load ~130K tokens of substrate before any divergence"。
- 一个**外部**数字（我**未核实**，来自 README 第 199 行转述第三方博客）：2 道题的独立盲评，novelty 4.5→9.0、trap detection 5.0→9.0，代价 ~2.3× 时间、~1.9× 输出。

---

## 3. ★ 它的「成功标准」是什么

- **怎么判定自己成功**：一个 5 维 0–10 的 **LLM-as-judge rubric**（breadth / novelty / trap_detection / actionability / builder_usefulness）+ 一个 `overall_winner ∈ {A, B, tie}` 的单票判决。成功 = "5W/1L/0T" **且** 均值 Δ 为正。**没有阈值、没有零假设、没有显著性检验、没有效应量门槛、没有多重比较校正**。winner 是**一个字符串**，没有"margin ≥ x 才算赢"的规则。
- **否证/失败条件**：**没有写**。最接近的两句都不是否证条件：(a) "if a junior would Google it and find the answer, baseline wins"（使用启发式）；(b) Limitations 里 "we expect ADHD's lead to shrink on this dimension but not on breadth, novelty, or trap detection"（**预测，但没有实验去检验它**）。
- **"不可分辨"这种结果**：**完全没有报告**。全文 grep `significan|p-value|confidence interval|repeat|re-run|variance|noise|seed|bootstrap|std` → **0 命中**。噪声地板（δ）不存在，每题 n=1。
- **它自己的判据其实自带可测噪声——而论文没发现**（本人复核）：
  - 判官在 **3/6 题上把 trap 条数说错**：lru-100ms 判官说 "18 traps"（实际 20）、monolith-split 说 "20 traps"（实际 18）、naming-feature-flag 说 "21 trap ideas"（实际 20）。另 3 题（20/18/10）说对。
  - 判官在 **4/6 题上把 cluster 数说错**：llm-hang-cli 说 "9 categories"（实际 6）、rate-limit-leader 说 "6 families"（实际 5）、fuzzy-bug 说 "7 lens families"（实际 6）、naming 说 "8 conceptual spaces"（实际 7）；lru 的 "7 categories" 与 monolith 的 "6 categories" 说对。判官还声称 "spanning 40+ ideas"（实际 30）。
  - 也就是说：**它唯一的成功判据（判官读文本后的整体印象）在单次样本上就已经有 30–50% 的可数事实错误率，而论文完全没察觉。**
- **可复现性更糟**：评测当时的帧选择是**无种子**的 `sort(() => Math.random() - 0.5)`（`git show 9a46221:src/frames.ts:132`，还是那个有偏洗牌），HEAD 才改成 Fisher-Yates。而**每题实际用了哪 5 个帧，一个字都没记**（`results.json` 无 frame 字段）⇒ **"novelty 增益来自跨域帧"这个归因无法从产物复核**。

---

## 4. 自认的局限（原话优先，论文 §7 Discussion and limitations）

> **1. Same-model judging.** "Our LLM-as-judge runs on the same model family as the generator. We mitigated with adversarial system prompts and randomised A/B order, but we cannot exclude familiarity bias entirely. A useful follow-up is cross-model judging (e.g. judge with a different vendor's model) and human ratings on a held-out subset."

> **2. Small problem set.** "Six problems is enough to see consistent direction but not enough to make strong quantitative claims. We released the harness so the set can be extended; adding a new problem is a four-line change."

> **3. Frame library is hand-authored.** "The 15 frames in the current library reflect our judgement about which vantage points produce distinct outputs on engineering problems. **A frame can fail silently — producing paraphrases of another frame's ideas — without the harness catching it.** Frame-quality evaluation is future work."

> **4. Confounded by deepen quality.** "The actionability delta is partly explained by the deepen pass, which gives ADHD a structural advantage (sketch + risk + first step) that the baseline's free-form prose does not enforce. A fairer ablation would equip the baseline with the same output schema; we expect ADHD's lead to shrink on this dimension but not on breadth, novelty, or trap detection."

> **5. Domain.** "All six problems are engineering-shaped. The frame library is biased toward engineering when codeMode is enabled. Whether ADHD's wins generalise to product strategy, scientific brainstorming, or pure creative writing is plausible but not demonstrated here."

**论文正文没写、但仓库 `documentation/evals.md` 写了的（更狠）**：

> **6. Scale gap.** "Evals run at K=5 branches; the academic diversity literature measures at K=100."
> **7. Human-in-the-loop.** "A controlled CHI 2025 study found no significant benefit from LLM problem-reframing with human designers. ADHD's LLM-to-LLM context differs, but this is honest counter-evidence."

**作者自己在 skill 源规格里写的失败模式（`skills/adhd/SKILL.md:160-177`，论文只提了其中两条）**：
> - "**Convergence disguised as divergence.** Ten minor variations of one idea is not breadth. If every candidate shares the same underlying assumption, you have not diverged. You have decorated."
> - "**Weird-for-weird's-sake with no convergence.** A pile of 30 unsorted absurdities is as useless as one safe answer. Always converge."
> - "**Skipping the isolation invariant.** If you simulate parallel branches by writing them sequentially in one context, you have not done ADHD. You have done a wider single thought."

---

## 5. ★ 对我们项目的可迁移点

**路线定位**：ADHD 本身**就是路线 A（人写死的固定拓扑）**——拓扑写死在代码里（5 路并行 → 1 打分 → 1 聚类 → K 加深），**没有学习出来的策略、没有更新规则、没有搜索**（对应我们 U5：它连"目标函数"都没有，只有一遍筛选）。所以它**不是我们的路线 B/C 的竞品，而是我们的"固定拓扑对照臂"的现成实现**。

**能省掉的具体实验**：
- 不用再自己写"宽扇出 vs 单发"这一层的最小实现。`src/engine.ts` 的 Phase 1 隔离写得很干净（stateless `query()` + `tools: []`），可直接当"路线 A 扇出臂"接进我们的 harness。
- 不用再自己实现"打散 + 聚类 + top-K"这套 glue（`scoreIdeas` / `clusterIdeas` / shortlist 选择 / deepen prompt 都现成）。
- 不用再自己设计"每条候选带分数 chip"的渲染格式（`[N V F]`）。

**能抄的三条（按对我们"结构量判据"的适配度排序）**：

1. ★ **trap 列表 = 一种"可核验的承重性反例"载体**。作者的 "trap" 语义与我们"依据包"高度同构：**一个看起来有吸引力、但有一条具体机制性理由说明它承载不了的候选**（例："Truncate-and-rewrite on restart scales O(n) with cache size, becomes prohibitive at 10k+ entries"）。它**离散、可数、可逐条核**（本次共 106 条），而且**不是措辞相似度**。我们的判据载体可以照抄这个形态：每条候选必须带一条**可被依据包否证的具体理由**。这是本篇最值得抄的东西。
2. ★ **帧隔离做成"机械保证 + 可断言的不变量"**，而不是提示词。它甚至在 skill 里写明了反面："If you simulate parallel branches by writing them sequentially in one context, you have not done ADHD." 我们可以照此写一条**代码级断言**（任一 branch 的 prompt 不得包含其它 branch 的输出），把"隔离"变成 CI 可测的契约。这对我们 L0/L1 的区分（状态有没有被真的用过）是直接基础设施。
3. **cluster 标签 = 一个可数的"角度分类"**，且每个叶子带一个标签。注意：它的聚类**没有算法**，是一次 LLM 调用；但**产出的标签数是可数的**（5–7），**不依赖 embedding**。这给了我们一个比"句级 embedding 距离"更靠谱的宽度代理：**数标签 + 查标签的稳定性**（把 cluster 调用重跑 K 次看标签数/归属是否漂移）——这恰好绕开了我们 embo-01 的无分辨率问题。

**必须改什么才能用**：
- **判官必须换源**（同源即 U6，见 §6）。至少：judge 用不同厂商/不同模型族；生成器、critic、judge 三层不能同族。
- **成功判据必须换成我们的"净维度增益"**，不能沿用 5 维 rubric。特别是 `breadth` / `novelty` 这两个必须换成**能被依据包核验、且改变了决策**的计数。
- **必须补重复与噪声地板**：n=1 完全不可用（见 §6c）。我们按记忆里的规矩定：题内重复 k 次、预注册"不可分辨"档、显著性用题为单位。
- **帧的归因要留痕**：它没记每题用了哪几帧，我们若要声称"某个 op 引入了某维度"，必须把每题的实际 op 组合落盘（这正是我们"证据包"要装的东西）。
- **成本公式直接用**：`cost ≈ N × (base_context + branch_output) + critic_context + K × deepen_context`。它提醒我们"扇出的 N 倍乘在 **substrate** 上而不是输出上"——若我们把扇出塞进一个带大上下文的 agent session，代价远高于"10 次调用"这个直觉数。

**DEV 集设计**：`bench/problems.json` 与 runner 分离、加一题 4 行——这个模式值得照抄（问题集与打分逻辑解耦，方便扩题而不动 harness）。另外它的 6 道题本身（尤其 `fuzzy-bug` 那种"生成假设类别"的题）也是我们 DEV 集的好候选。

---

## 6. ★ 不可迁移 / 会误导我们的点

**(a) 它的"宽度/新颖性"是 embedding 做的吗？—— 不是，但更糟。**
全仓库 grep `embedding|cosine|similarity|vector` → **0 命中**。它的 breadth / novelty **完全不是几何量**：
- pipeline 内部的 "novelty" 是 **critic 自评的 0–10 整数**（`Score.novelty`），直接来自生成器同族模型的一次调用；
- 判官侧的 "breadth" / "novelty" 是 **LLM 读一整块文本后的整体印象 0–10**。
⇒ 它**不会**踩我们 embo-01 的"embedding 中文句级几何无分辨率"那个坑，但它踩了**更根本的坑：宽度没有任何可核验载体**。产物里其实**存在**可数代理（叶子 24–30、cluster 5–7、trap 106 条），而**判官在 4/6 题把 cluster 数说错、3/6 题把 trap 数说错**——即：连"数出来的宽度"都没被认真使用。

**(b) 判官与被测同源（U6）：是，而且是最严重的一档。**
生成器 = critic = judge = 同一个默认模型（`criticModel ?? model`，`judge()` 不传 model）。三重同源意味着：判官给"novelty"打的 7.83 分，与被测的 novelty 芯片（critic 自评 N 分）**是同一个模型对同一件事的两次自述**。论文自己承认同源，但**没意识到这使"+5.17 novelty"这一头条数字变成了自评的对齐度测量**。可观测后果：判官的可数事实错误率 30–50%（§3）。

**(c) n=6 且每题只跑 1 次（U4）：比"小样本"更糟的三件事。**
1. **零重复、零显著性、零噪声地板、零种子**（§3）。"5W/1L" 在 n=6 上的不确定度极大，而胜负由**一个字符串**决定，没有 margin 规则。
2. **帧选择无种子**（评测时是 `sort(() => Math.random()-0.5)`），且**每题实际帧组合未记录** ⇒ 同一命令重跑会得到不同结果，**无法复现论文数字**。⚠️ 而且**文档在这件事上说了假话**：`documentation/how-it-works.md:63` 与 `documentation/frames.md:31` 都写 "Frame selection … is **deterministic per-seed** so runs are reproducible"，但**代码里根本没有 seed 这个参数**——`RunOptions`（`src/types.ts:50-68`）没有 `seed` 字段，`src/frames.ts` 至今仍用裸 `Math.random()`。这个"可复现"承诺在评测版本和 HEAD **两个版本上都不成立**。
3. **产物本身有未报告的损耗**：**两道题只有 24 个叶子**（llm-hang-cli、rate-limit-leader；名义 30），另外 4 道题是 30 个 ⇒ 合计 168。⚠️ **归因更正（见 §2.3）：这不是"分支掉链子"，而是 `selectFrames` 本来就会返回 4 帧或 5 帧**（1:1 复刻 + 20 万次蒙特卡洛：P(4 帧)=0.2498、P(5 帧)=0.7502、E[N]=4.7502；transcript 的 2/6 与 0.25 一致）。⇒ **真正该被追问的不是"少了 12 个想法"，而是"论文正文把分支数写成固定的 5，而实现是随机的 4 或 5，论文与 EVALS.md 都没报过这件事"。**
⇒ 按我们自己的规矩，**这篇的 Δ 一律不能进我们的对照表**（噪声带宽未知，测了等于没测）。

**(d) "角度多"被当成"思维面宽"（U7）：这篇正是这个病的活标本。**
- 论文自己的判据里，"width" 的全部含义就是"有几个不同的角度"（cluster 5–7）+ "判官觉得新颖"；**没有任何一处检查某个角度是否承载了可核验的承重信息、是否真的改变了决策**。
- **反例就在论文自己的数据里**：`llm-hang-cli` 是 ADHD 侧最"宽"的一题（6 个 cluster、20 条 trap、3 条 deepen 分支、输出 17.8K 字符），**但它输了**，builder_usefulness **4 vs 9**——判官原话："A [baseline] delivers a pragmatic, immediately implementable solution… B's top pick (rage-quit button) is creative but introduces UX complexity… without solving the core reliability problem"。**角度数最多的那一题，承重维度最少。** 这就是 U7 在一篇 5/6 胜率的论文内部被直接演示。
- 论文自己的 skill 源规格已经写下正确警告（"Ten minor variations of one idea is not breadth"），但**测量端没实现它**——警告与判据脱节。

**(e) 量纲不同。** 我们的主判据是**净维度增益 =（走工作流）−（直调 baseline）**，单位是"能被依据包核验且改变决策的承重信息维数"。他们的单位是"LLM 对文本的 0–10 印象"。**两者不可换算**，他们的 +4.17 / +5.17 / +7.67 不能被读成我们的任何量。

**(f) 发布的代码 ≠ 产生数字的代码（复现性断层）。** `EVALS.md`/`results.json` 由 2026-05-25 的代码生成，但仓库 HEAD（2026-10-06）已改了三处**影响机制**的地方：
- `b670af0`（2026-07-23）加了 **PHASE 0 reframe**（调用数 10→11，且**改写了生成器看到的 problem**；论文完全没提这一步）；
- `027b039`（2026-07-23）给 critic 加了 `strength` 字段（critic 输出 schema 变了）；
- `8997917`（2026-06-30）加了 `criticModel`（可异构判官，评测时**不存在**）。
⇒ 想复现必须 checkout `9a46221`/`75616bf`，而仓库默认分支给的是另一套行为。（补充核对：我逐文件 diff 过，**评测harness 本身没变**——`bench/judge.ts`、`bench/problems.json`、`bench/run-evals.ts` 在 `75616bf`(2026-05-25) 与 HEAD 之间**逐字节相同**；漂移**只发生在 `src/engine.ts`**，即"被判的那一方"变了，判官与题集没变。）

**(g) ★ 论文 Analysis 节的"见证性例子"大部分在发布的产物里查无实据（本人复核）。** 论文举了 5 个具体例子，我在 `bench/results.json` 里逐个查：
| 论文原文例子 | 在发布产物中的命中 |
|---|---|
| "On llm-hang-cli, ADHD flagged a **'multi-rail redundancy'** idea (fire identical requests to 2–3 endpoints simultaneously) as a trap" | **0 命中**。该题 20 条 trap 逐条看过，没有这一条；"hedged/parallel requests" 其实是 **baseline** 的方案（判官语 "A presents textbook solutions: … hedged requests"）。论文把 baseline 的点安到了 ADHD 的 trap 名下。 |
| "On lru-100ms, ADHD flagged a **'treat disk as NVRAM with timer-interrupt commits'** idea as a trap…" | **0 命中**。该题 20 条 trap 里没有 NVRAM / timer-interrupt 任何一条；整个输出里 `NVRAM` 0 次。 |
| "on llm-hang-cli, … a **first-byte vs chunk-idle dual timer** design — distinguishing NEVER_CONNECTED, STALLED_MID_STREAM, and COMPLETED_SLOW … It **arose from the regulator frame**" | **0 命中**（`first-byte`/`chunk-idle`/`NEVER_CONNECTED`/`STALLED` 全部 0）。且帧归因无法查（帧组合未记录）。 |
| "on fuzzy-bug, the **biology frame** surfaced a '**fever-response circuit-breaker**' … progressive degradation tiers (Opus → Sonnet → Haiku → cached)" | **0 命中**（`fever`/`progressive degradation`/`Haiku` 全 0）。 |
| "on rate-limit-leader … **proof-of-work** rate limiting" | ✅ 命中（`proof-of-work` 5 次）。 |
⇒ 保守表述：**这 5 个见证例子里 4 个无法在唯一发布的运行里复现**。可能这些例子来自另一次未发布的运行（若如此，则论文引用的不是它公开的那份证据），但无论哪种情况，**"novelty 来自跨域帧"这一核心机制叙事在发布产物层面是不可核的**。（这一点对我们极重要：这篇论文的"证据"结构与我们要防的"不可核断言"是同一类。）

**(h) 连作者自己的 README 都与发布产物对不上。** README 描述 llm-hang-cli 那题："ADHD spawns **6 isolated frames**, surfaces **30+** ideas"、"**20 traps** flagged"、并写 "Independent LLM judge on this problem: breadth 9 vs 6, novelty 8 vs 3, **trap detection ~8 vs ~2**"。而产物里：该题**叶子 24**（不是 30+）、trap 20（对）、**记录的 trap_detection 是 10 vs 2**（不是 ~8 vs ~2）。⇒ **同一份运行的叙述在仓库内部就有三个版本**（EVALS.md / results.json / README）。

**(i) 论文正文的角度数与自己的产物对不上**："ADHD surfaces **6–9** structurally different angles per problem"，实际 cluster 标签数是 **5–7**（rate-limit-leader 只有 5 个，llm-hang-cli/fuzzy-bug/monolith-split 各 6 个）。

**(j) 其它要防的点**：判官输出的 "reason" 字段是**自由散文**，我们若要拿它做判据载体就会踩 U3（措辞级）；`bench/results.json` 把 **整段渲染文本**（含 ANSI 已剥离）交给判官，等于把"结构化程度"也变成了被评对象（结构做得好的那侧天然占便宜——论文自己在 Limitations 里承认了 actionability 维度被 deepen 的结构优势污染，**但没做那个消融**）。

---

## 7. 逐字摘录

> **① 论文 §Method / Phase 1 — Diverge（讲隔离）**
> "Critically, the N calls do not share context. The regulator branch never reads what the speedrunner branch produced. Anchoring is eliminated by construction, not by prompting."

> **② 论文 §Evaluation / Judging（讲判官与去偏）**
> "The judge sees both outputs blinded as A/B in randomised order per problem (recorded for de-bias), and scores on five dimensions: breadth (range of structurally distinct angles), novelty (non-obvious-but-viable ideas), trap_detection (does it name ideas that look good but aren't, with reasons), actionability (does the top pick have a sketch + named risk + first concrete step), and builder_usefulness (which is more useful to the engineer who actually has to ship)."

> **③ 论文 §Analysis（讲那个查无实据的例子）**
> "On llm-hang-cli, ADHD flagged a 'multi-rail redundancy' idea (fire identical requests to 2–3 endpoints simultaneously) as a trap because it doubles or triples API costs and may violate rate limits — a real concern any builder would otherwise discover only at the bill."

> **④ 源码 `src/engine.ts:216-218`（论文没写的权重）**
> ```
> // Weight: novelty matters because the whole point is escaping the obvious,
> // but viability is the gatekeeper — a brilliant unshippable idea is a trap.
> const total = r.novelty * 0.35 + r.viability * 0.4 + r.fit * 0.25;
> ```

> **⑤ 源码 `skills/adhd/SKILL.md:187-188`（写了但没实现的停止条件）**
> "**When to stop diverging?** Stop when new candidates start repeating the shape of existing ones. The space is mapped. Do not pad to hit a number."

---

## 8. 读完后我自己的一句判断

**最值得抄的是两样东西，且都不是它的"5/6 胜率"**：一是 **trap 那种"看起来有吸引力、但有一条具体机制性理由说明它承载不了"的候选标注**（本次 106 条，条条可数、条条可核、条条带理由）——这几乎就是我们"依据包"想要的反例载体；二是**把分支隔离做成代码级不变量而不是提示词祈使**（`tools: []` + stateless `query()` + 可写断言），这是我们区分 L0/L1 时最省事的一块基础设施。

**最容易骗我们的是它的头条数字本身**：一篇**没进任何同行评议索引的单作者预印本**，用**与被测同源**的 LLM 判官，在**同源模型自报的 novelty 轴**上，测出 +5.17、5W/1L/0T；我核对它唯一发布的运行产物时发现，判官在 3/6 题把 trap 条数说错、4/6 题把 cluster 数说错，论文 Analysis 段 5 个"见证性创新"里 4 个在产物里查无实据，连它自己 README 的数字都和 `results.json` 对不上——**"角度多"被当成"思维面宽"（U7）在这个 5/6 胜率的案例内部就已经发生**（角度最多的那一题恰恰输了，builder_usefulness 4 vs 9）。所以我们能拿走的只有它的**机制骨架（路线 A 的固定拓扑 + 结构化标注形态）**，它的**任何 Δ 数字都不能进我们的对照表**；而它最该被我们记住的，是那句它自己写下、却没在测量端兑现的警告——"Ten minor variations of one idea is not breadth… You have decorated."

---

## 附：来源清单

全部访问日期均为 **2026-10-21**。

| # | 来源 | URL / 路径 | 取到了什么 |
|---|---|---|---|
| S1 | 预印本正文（GitHub Pages 单页，v0.1，2026-05-25） | `https://adhdstack.github.io/` | 全文（摘要/Intro/Related/Method/Implementation/Evaluation/Analysis/Discussion+Limitations/Conclusion/References）。已存为 `_raw/adhdstack/index.html` 与纯文本 `_raw/adhdstack/paper.txt`（338 行） |
| S2 | 同上，原始 HTML 抓取命令 | `curl -sS -m 30 -L https://adhdstack.github.io/ -o index.html` | HTTP 200，38,080 bytes |
| S3 | 站点是否有子页面 | `https://adhdstack.github.io/{docs,paper,index2.html,eval.html,adhd.html}` | 全部 **404** ⇒ 单页论文，无其它子页面 |
| S4 | 代码仓库（完整克隆，含历史） | `https://github.com/UditAkhourii/adhd` | 存于 `_raw/adhdstack/repo`；HEAD `7b91ce6` (2026-10-06)，已 `git fetch --unshallow` 取到全部历史 |
| S5 | 评测运行记录 | `repo/bench/results.json`（223 行） | 6 题 × (baselineOutput, adhdOutput, verdict) 全文。**无 token/耗时/帧/成本字段** |
| S6 | 逐题判决（人读版） | `repo/EVALS.md`（112 行） | 5W/1L/0T、逐维理由、run 时间戳 `2026-05-25T11:28:55.772Z` |
| S7 | 判官实现与 prompt 全文 | `repo/bench/judge.ts`（73 行） | JUDGE_SYSTEM rubric 五维原文、`overall_winner` 枚举、A/B 盲评 |
| S8 | 评测 runner | `repo/bench/run-evals.ts`（204 行） | `framesPerRun:5, ideasPerFrame:6, topK:3, concurrency:4, codeMode:true`；`Math.random()<0.5` 决定 A/B；`judge()` 不传 model |
| S9 | 题集 | `repo/bench/problems.json`（32 行） | 6 题全文 |
| S10 | 主引擎 | `repo/src/engine.ts`（468 行，HEAD） | 权重 0.35/0.40/0.25；shortlist `max(2,min(4,topK+1))`；nonObviousPick 规则；critic = `criticModel ?? model`；PHASE 0 reframe；fail-soft 分支 |
| S11 | 评测当时的引擎（历史版本） | `git show 9a46221:src/engine.ts` → `_raw/adhdstack/engine_2026-05-25.ts` | 权重/shortlist/pick 规则与 HEAD 一致；**无 reframe** ⇒ 当时确为 10 次调用 |
| S12 | 帧库 | `repo/src/packs/core.ts`（109 行）+ `repo/src/frames.ts`（65 行） | 15 帧全文与标签；`selectFrames` 的 codeMode + 强制 wild 规则 |
| S13 | 评测当时的帧选择 | `git show 9a46221:src/frames.ts` → `_raw/adhdstack/frames_2026-05-25.ts` | `sort(() => Math.random() - 0.5)`，**无种子** |
| S14 | LLM 调用封装 | `repo/src/llm.ts`（73 行） | 每次调用 = 独立 stateless `query()`，`tools: []`，不传 model ⇒ SDK 默认模型；无 temperature 设置 |
| S15 | 渲染器 | `repo/src/render.ts`（97 行，HEAD） | `[N V F]` chip 格式、输出五段结构 |
| S16 | 源规格（skill 正文） | `repo/skills/adhd/SKILL.md`（215 行） | 加权 0.35/0.40/0.25、隔离不变量、五条 anti-pattern、"When to stop diverging"（未实现） |
| S17 | 文档：怎么工作 | `repo/documentation/how-it-works.md`（76 行） | "No heuristic threshold and no logit-bias steering. The critic's structured output is the pruning decision."（⚠️ 同文件 :63 的 "deterministic per-seed" 与代码不符，见 §6c） |
| S18 | 文档：何时用（含成本公式） | `repo/documentation/when-to-use.md`（67 行） | `cost ≈ N × (base_context + branch_output) + critic_context + K × deepen_context`；~26K substrate ⇒ 5 分支重载 ~130K tokens |
| S19 | 文档：评测说明与已知局限 | `repo/documentation/evals.md`（56 行） | 比率列、K=5 vs K=100 scale gap、CHI 2025 人类实验反证、issue #6/#16/#18 |
| S20 | 仓库 README | `repo/README.md` | 第三方独立评测数字（~2.3× 时间、~1.9× 输出）、README 与产物不一致处 |
| S21 | 版本漂移的提交历史 | `git log --date=short -- src/engine.ts bench/` | `9a46221`(2026-05-25 初始)、`75616bf`(2026-05-25 加 eval harness)、`8997917`(2026-06-30 criticModel)、`b670af0`(2026-07-23 reframe)、`027b039`(2026-07-23 strength)、`7b91ce6`(2026-10-06 HEAD) |
| S22 | arXiv 元数据核对 | `http://export.arxiv.org/api/query?search_query=all:"Parallel Divergent Ideation"`（0 entry）、`ti:"ADHD"`（20 entry，逐条看过标题，无本文）、`au:"Akhouri"`（10 entry，同姓物理学家） | **确认无 arXiv 版** |
| S23 | 站点 vs 仓库 docs 版论文 | `https://adhdstack.github.io/` vs `repo/docs/index.html` | 文本相似度 0.936，差异集中在成本段（仓库版更详细），**数字部分一致** |

**未能取到 / 未验证的项（不猜、不补）**：
- **模型型号**：评测与判官实际用的模型名**任何地方都没记录**（`results.json` 无字段，runner 不传 model）⇒ 只能确定"三者同族同源"，具体是哪个模型**未验证**。
- **token 数、单次调用耗时、真实美元成本**：**未取到**（论文只有"US$0.30 / US$50k"这个比喻；`results.json` 无成本字段）。
- **每题实际使用的 5 个帧**：**未取到**（无记录；且当时帧选择无种子）⇒ 论文"novelty 来自跨域帧"的归因**不可核**。
- **第三方独立评测**（README 转述的 2 题、4.5→9.0、~2.3×/~1.9×）：只读到 README 的**二手转述**，未访问原博客，**未验证**。
- **CHI 2025 那项人类实验**：只读到 `documentation/evals.md` 的**二手转述**（未给论文标题/DOI），**未核**。
- **paper §Analysis 里的 4 个见证例子**：在唯一发布的运行中**查无实据**（§6g）；我无法判断它们是否来自另一次未发布的运行。
