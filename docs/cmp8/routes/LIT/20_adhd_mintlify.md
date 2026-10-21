# 20 — ADHD 官方文档站（adhd.mintlify.site）精读提取

> 提取对象：**项目官方文档站** `https://adhd.mintlify.site`（Mintlify 站，21 个页面全量抓取）
> 不是论文。第 4 组另一篇（预印本 preprint）不在本文档范围内；本文档只在需要核对数字时引用预印本原话。
> 抓取方式：`/llms.txt`（页面索引）+ `/llms-full.txt`（104 KB 全文）+ `/sitemap.xml`（22 URL）+ 逐页 `/<path>.md`（Mintlify 的 markdown 端点，16 页 200 OK），
> 原始文件落盘于 `/workspace/lab/routes/LIT/_raw/mintlify/`（`llms.txt` / `llms-full.txt` / `sitemap.xml` / `md_*.md` / `pages/` / `live/`（当日 GitHub HEAD 源码）/ `miyagadget.html`）。
> 所有源码对照均与 **2026-10-21 的 GitHub HEAD** 逐字节 diff 过（`live/src_frames.ts` vs `adhd/src/frames.ts` 等 **7 个文件**：`frames.ts` / `engine.ts` / `render.ts` / `packs/core.ts` / `bench/judge.ts` / `bench/run-evals.ts` / `EVALS.md`：**全部 IDENTICAL**），
> 所以下面的"文档 vs 源码"差异不是"本地快照过期"，而是**文档站当前口径本身**。

---

## 0. 引用

| 项 | 内容 |
|---|---|
| 标题 | **ADHD — Parallel Divergent Ideation for Coding Agents**（文档站首页标题 "ADHD"；站点 tagline："Parallel divergent ideation for coding agents — an architectural fix for premature convergence in autoregressive reasoning."） |
| 作者 | Udit Akhouri（GitHub `UditAkhourii`，@akhouriudit）——文档站各页署名为 "by the [ADHD] project" |
| 年份 | 站点 sitemap `lastmod` = **2026-08-22**；关联预印本 *Preprint v0.1 · 2026-05-25*（https://adhdstack.github.io/，**未取到 arXiv id / DOI**）；npm 包 `adhd-agent` v0.1.4（`package.json`） |
| venue | **无**。这是文档站 + MIT 开源仓库（`UditAkhourii/adhd`，公开，**4444 stars / 302 forks**、created 2026-05-25、last push 2026-10-05、MIT，GitHub API 实测 2026-10-21）。相关外部报道：The New Stack 专题（thenewstack.io/claude-code-adhd/） |
| 一句话声称解决什么 | 把"过早收敛"（premature convergence）当**架构问题**而不是提示词问题来治：发散阶段跑 N 路**上下文互不可见**的并行分支（每路一个"认知畸变"frame），收敛阶段用**机械分离的独立 critic 调用**打分/聚类/剪枝/深挖，从而在开放式工程设计题上产出比"单次直调"更宽、更不显然、且能点出"陷阱想法"的答案。 |

---

## 1. 核心机制（要具体到能照着实现）

| 项 | 内容 |
|---|---|
| **输入** | `problem: string`（自然语言题面）+ 可选 `context`（一段文本/文件内容，CLI `--context PATH`）。**无状态图、无外部检索、无工具**：`src/llm.ts:26` 明确 `tools: []`（注释："No tools — divergence is pure generation. Tools = convergence pressure."） |
| **状态表示** | **纯文本 + JSON 对象数组**，不是树也不是向量。核心对象（`src/types.ts`）：`Idea = {id, frameId, cluster?, text, rationale?, score?, depth, parentId?}`；`Score = {novelty, viability, fit, total, trap?, strength?}`；`Cluster = {label, ideaIds[]}`；`DeepenedIdea = {ideaId, sketch, childIdeas[]}`。注意 `depth` 只有 0/1 两层——deepen 产出的 child idea **不再被评分、也不再被展开**（引擎里 deepen 只做一轮）。`total` 是加权分。 |
| **动作/算子（全部枚举）** | ① **reframe / strip anchors**（`engine.ts:123 reframeProblem`，1 次 LLM 调用，`stripAnchors` 默认 `true`）：剥掉题面里的偶然锚点（当前技术栈/工具名/团队结构），保留真约束（合规/预算/物理限制）。**② diverge**（`engine.ts:144 divergeBranch`）：N 路并行，每路 system prompt = `DIVERGE_SYSTEM`（"You are a generator, not a critic… The first 3 ideas you'd think of are banned… Do not evaluate, hedge, or rank"）+ 一条 frame 的 vantage prompt，user prompt 里给题面 + `Generate {ideasPerFrame} ideas under this frame`，输出 JSON 数组 `[{"text","rationale"}]`。**③ score**（`engine.ts:185`）：1 次调用，对每条 idea 打 `novelty/viability/fit` 0–10，附 `trap`（机械式原因，如 "solid for a prototype, breaks past 10k concurrent users"）与 `strength`（每条都必填的"它比竞争想法强的唯一具体一点"）。**④ cluster**（`engine.ts:231`）：1 次调用，按**底层角度**（不是关键词）分 3–6 组，label 形如 "remove-the-server plays"。**⑤ deepen**（`engine.ts:259`）：top-K 各 1 次调用，产出 `sketch`（4–8 句，含承重风险 + 第一个具体动作）+ 3–5 个 child ideas。**⑥ 纯本地算子**（无 LLM）：加权 `total = novelty*0.35 + viability*0.40 + fit*0.25`（`engine.ts:218`）、shortlist 切片 `ranked.slice(0, max(2, min(4, topK+1)))`、non-obvious pick 取 `argmax(novelty + 0.5*viability)`、provocation 取全池 `argmax(novelty)`。 |
| **过程/回路 + 停止条件** | **单趟，不迭代**：reframe → N×diverge（并发）→ score ∥ cluster（并发）→ K×deepen（并发）→ 结束。**停止条件 = 固定预算（N=5、K=3、并发 4），不是收敛判据**。站点 `how-it-works` 明说："Convergence is a **separate LLM call** with an inverted system prompt (critic posture, evaluation mandatory). **No heuristic threshold** and no logit-bias steering — the critic's structured output *is* the pruning decision. Default `K=3`"。即：critic 只决定"剪谁"，**不决定"何时停止发散"**。唯一近似停止判据的是 `usage/skill` 的一句自然语言启发（"When new candidates start repeating the shape of existing ones, the space is mapped — no padding to hit a number"），它是写给 agent 的建议，不是可执行判据。 |
| **输出** | `renderText`（`src/render.ts`）固定 6 段：**Problem** → **Reframed for divergence** → **Wide set**（按 cluster 分组，每条带 `[N7 V8 F9]` 分数芯片）→ **Converge — shortlist**（含 `★ non-obvious pick` 与每条的 `+ strength`）→ **Traps (watch-outs, not verdicts)** → **Focus — deepened branches**（sketch + `branches off:`）→ **Provocation** → （失败时）**Partial failures**。 |
| **谁来评价 + 评价信号怎么回传** | **三层，全是 LLM 自评，无 oracle、无规则核验、无人类评分**：<br>（a）**loop 内 critic**（score + cluster）——`engine.ts:330` `const critic = criticModel ?? model;`，**默认与 generator 同一个模型**（`--critic-model` 可换，站点 CLI 页把它定位为"decorrelate critic errors"）；deepen 用的是 generator 模型（`engine.ts:427` 传 `model` 而非 `critic`）。<br>（b）**评测判官**（`bench/judge.ts`）——独立 LLM-as-judge 调用，system prompt 角色 "skeptical staff engineer"，5 维 0–10 + `overall_winner`，A/B 每题随机换位。<br>（c）**评价信号回传：几乎没有**。score/cluster 的结果只用于**排序、切片、深挖谁**（一次性的前向流），**不反馈回发散阶段**（分支不会重试、不会自适应换帧、不会因为 critic 说"太浅"而再跑一轮）。整个循环里唯一带"反馈"味道的是 `stripAnchors` 的 reframe——但那是**改题面**，不是改策略。<br>⇒ 按我们项目的优化器契约分级：**只有 L0（目标函数）+ L1（固定动作序列），没有 L2（更新规则）、没有 L3（搜索）、没有 L4（学习）**。 |
| **frame 选择规则** | `selectFrames(n, codeMode, packs)`（`src/frames.ts:36`）：`codeMode=true` 时池子收窄为带 `code`/`design` 标签的帧（core 里 14 个）；Fisher-Yates 洗牌取前 `n-1`=4 个；再从 wild 池（core 里 8 个带 `wild` 标签）随机抽 1 个，**若它已在前面 4 个里则不补入**。`wild` 帧恒占 1 个保留位（"A `wild` frame always gets one **reserved slot** per run"）。**没有 seed 参数**（详见 §6 差异 1）。 |
| **预检门（skill 版才有）** | `skills/adhd/SKILL.md` 有一个 pre-flight gate：显式 `/adhd` 调用跳过；否则 agent 自问三题（open-ended? high-stakes? open phrasing?），任一 "no" 就**直接给普通答案**并中止。 |

---

## 2. 关键数字

**实验设置**：6 道开放式工程题（`bench/problems.json`：systems / ux-reliability / distsys / debugging / refactor / naming），**每题 1 次，无重复运行、无 seed、无方差报告**；ADHD 臂 = 5 frames × 6 ideas，top-3 deepen，concurrency 4（⚠️ 实际有 2 题只跑了 4 帧，见下）；baseline 臂 = 同模型单次调用（system prompt："You are a thoughtful senior engineer… give a useful answer with multiple approaches, tradeoffs, and a recommendation"）。运行时间戳 `Run: 2026-05-25T11:28:55.772Z`（EVALS.md）。**模型名全文未出现**（仓库里 grep 不到任何 `claude-*`/`gpt-*` 字面量；`src/llm.ts:19` 传 `model: opts.model`，为 `undefined` ⇒ 走 Claude Agent SDK 默认模型）。

**主指标（站点 `evals/results` 与仓库 `EVALS.md` 完全一致，我逐题复算过均值，全部吻合）**：

| Dimension | ADHD | Baseline | Δ | Ratio | 我复算的逐题值（ADHD/base） |
|---|---|---|---|---|---|
| breadth | **9.00** | 4.83 | +4.17 | 1.9× | 9/4, 9/6, 9/9, 9/9, 9/9, 9/9 → **ADHD 臂 6 题全 9，零方差** |
| novelty | **7.83** | 2.67 | +5.17 | 2.9× | 7/3, 8/3, 8/3, 8/3, 8/2, 8/2 |
| trap_detection | **9.50** | 1.83 | +7.67 | 5.2× | 10/2, 10/2, 9/2, 9/1, 10/3, 9/1 |
| actionability | **9.50** | 6.50 | +3.00 | 1.5× | 9/8, 9/8, 10/7, 10/7, 9/6, 10/3 |
| builder_usefulness | **7.67** | 6.83 | **+0.83** | 1.1× | 8/7, **4/9**, 9/6, 8/7, 8/7, 9/5 |

**胜负**：ADHD **5W / 1L / 0T**（唯一败局 `llm-hang-cli`，baseline 赢在 `builder_usefulness` 4 vs 9）。站点："**ADHD wins 5 of 6 problems head-to-head.** The biggest gap is **trap detection** — single-shot baselines almost never name the seductive-but-broken ideas, while ADHD's separate critic pass routinely flags **15–20** of them with mechanistic reasons."

**★ transcripts 级复核（我下载了 `bench/results.json`，152 020 B，逐题解析）**——这是本篇最硬的一节，站点与 EVALS.md 都没做过：

| problem | A/B swapped | ADHD 想法数(带分数芯片) | **隐含分支数** | cluster 数 | trap 条目 | baseline 的 "Cons/Risks" 段数 | baseline 风险词(trap/risk/downside/pitfall/caveat) | ADHD 字符 | baseline 字符 | **长度比** | 判官 breadth (a/b) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| lru-100ms | true | 30 | 5 | 7 | 20 | **4** | **0** | 18 592 | 4 538 | **4.10×** | 4 / 9 |
| llm-hang-cli | true | 24 | **4** | 6 | 20 | **4** | 2 | 17 851 | 5 244 | 3.40× | 6 / 9 |
| rate-limit-leader | true | 24 | **4** | 5 | 18 | **5** | 2 | 16 487 | 3 462 | 4.76× | 5 / 9 |
| fuzzy-bug | true | 30 | 5 | 6 | 10 | 0 | 0 | 17 572 | 3 909 | 4.50× | 6 / 9 |
| monolith-split | false | 30 | 5 | 6 | 18 | **6** | 6 | 21 198 | 5 632 | 3.76× | 9 / 4 |
| naming-feature-flag | false | 30 | 5 | 7 | 20 | 0 | 0 | 10 246 | 2 111 | 4.85× | 9 / 4 |

由此**实测确认**四条（都不是文档里写的）：
- **6 题里有 2 题（llm-hang-cli、rate-limit-leader）实际只跑了 4 个分支、24 个想法**，不是 5×6=30。⇒ 站点 "Default is 5 × 6 = 30"、"spawns N parallel branches"（N=5）在这批公开评测里**对 1/3 的题是假的**（成因见 §6.5 差异 3）。
- **trap 段实际条目数是 10–20**（fuzzy-bug 只有 10），站点说的 "15–20" 偏窄。
- **baseline 并不"几乎从不点出陷阱"**：4 题的 baseline 里有 4–6 个显式 `**Cons:**` 段，给出的正是机制性理由（"WAL grows unbounded (need compaction/snapshots)"、"Fsync can block on some filesystems"、"Platform-specific behavior (mmap reliability varies)"、"Cons: Race conditions between cache state and log"…）。判官仍给它们 trap_detection = **1–3**。⇒ 这个指标量的是"**有没有一段叫 Traps 的东西**"，不是"有没有点出陷阱"（详见 §3）。
- **判官看到的 ADHD 文本比 baseline 长 3.4–4.9 倍**（17–21 K 字符 vs 2–5.6 K），且是固定 6 段 schema（`Wide set` / `Converge — shortlist` / `Traps (look good, aren't)` / `Focus — deepened branches` / `Provocation`）+ 30 条带 `[N V F]` 芯片的条目；baseline 是连贯散文 + markdown `##` 小标题。**"盲"是假的**（§6.4）。
- **reframe 阶段在这 6 题里没有触发改写**：6 份 ADHD 输出里都没有 `Reframed for divergence:` 这一行 ⇒ 本轮评测中分支题面未被改写（但那 1 次 LLM 调用仍然发生了，见 §6.5 差异 2）。

**消融**：**站点没有、预印本也没有**。没有去 frame 的消融、没有 N/K 扫描、没有 "parallel-N vs single-prompt-list-N" 对照（站点自己挂在 issue #13 未做）、没有等-schema 对照臂。预印本承认："**Confounded by deepen quality.** The actionability delta is partly explained by the deepen pass, which gives ADHD a structural advantage (sketch + risk + first step) that the baseline's free-form prose does not enforce. A fairer ablation would equip the baseline with the same output schema; we expect ADHD's lead to shrink on this dimension but not on breadth, novelty, or trap detection."

**成本**：
- 站点口径：**5 diverge + 1 score + 1 cluster + 3 deepen ≈ 10 calls/次**，并发 4；skill 版"about 10 Agent calls, 30 to 90 seconds wall clock"；"5–10× a single-shot answer"。
- **实际是 11 次**（源码默认 `stripAnchors=true` 多一次 reframe 调用，站点两处成本口径都没算它——见 §6 差异 2）。
- token 成本模型（站点 `concepts/when-to-use`）：`cost ≈ N × (base_context + branch_output) + critic_context + K × deepen_context`；"If the base substrate is ~26K tokens, five branches re-load ~130K tokens of substrate **before** any divergence"。**美元数字站点故意不给**："a few cents to a few dollars… compute it for your own setup rather than trusting a single headline number"（预印本给了个比喻："spend US$0.30 to widen a US$50k architecture decision"）。
- **外部独立复现**（唯一一处，已实测抓取全文 `miyagadget.html`）：Shichinomiya，2026-06-03，Claude Code CLI 2.1.161，**2 题**，盲评 LLM 判官、A/B 换位：breadth 7.0→9.0、novelty 4.5→9.0、trap detection 5.0→9.0、**actionability 8.5→8.0（baseline 赢这一项）**；ADHD 2/2 胜；耗时 95.4s→216.1s（**2.26×**），输出 5623→10697 字符（**1.93×**）；作者自述 caveat："quality is an LLM-as-judge score (subjective); only 2 problems (small sample)"。
- 站点对外部结果的转述**准确**（"ADHD won both, with the biggest gains in novelty (4.5→9.0) and trap detection (5.0→9.0), at a real cost of ~2.3× time and ~1.9× output"），但**略去了 actionability 上 baseline 反超**这一项。

**引用到的外部文献**（我已逐条核实标题/摘要级）：arXiv:2510.01171v4 "Verbalized Sampling: How to Mitigate Mode Collapse and Unlock LLM Diversity"（2025-10-01），摘要原文 "in creative writing, VS increases diversity by **1.6-2.1x** over direct prompting" ⇒ 站点博客里那个 "recovers 1.6–2.1× diversity" **核实无误**；arXiv:2505.18949v1 "The Price of Format: Diversity Collapse in LLMs"（2025-05-25）⇒ 站点"格式本身诱发锚定、降低语义多样性"这句的出处。

---

## 3. ★ 它的「成功标准」是什么（对我们最有用）

**先给一个硬事实**：我把全站 104 011 字节的 `llms-full.txt` 全文 grep 过——**"success" 一词出现 0 次**；"threshold" 只出现 1 次，且是在讲**剪枝**而不是讲评估（"No heuristic threshold"）；"significant" 1 次（引 CHI 2025 外部反证）；"noise floor / confidence interval / p-value / standard deviation / variance" **全部 0 次**。

**它怎么判定自己成功？**（全部是隐式的，四条并列，无一被写成判据）
1. **判官宣布胜负**：`overall_winner: "A" | "B" | "tie"`，逐题；汇总成 "5W / 1L / 0T"。
2. **5 维 0–10 分数的均值**（breadth/novelty/trap_detection/actionability/builder_usefulness），报 Δ 和倍率。
3. **"对照组"** = 同模型单次直调（single-shot），A/B 位置每题随机。
4. 附带"trap 数量 15–20"这种**过程量**作为佐证（实测实际是 10–20）。

**否证/失败条件**：**没有预注册的"什么结果算失败"**。唯一接近否证结构的东西是 `evals/results` 的 "Known limitations" 四条（把它当准否证条件读：同源判官 / 6 题 / K=5 vs K=100 / 人类在环未验证），外加预印本里的 "Confounded by deepen quality"（自认 actionability 的 Δ 有结构混淆）。**没有"若 Δ < X 则视为失败"这类判据。**

**"不可分辨"这种结果有没有报告？** **完全没有。** 全站 0 次 "indistinguishable / inconclusive / within noise" 之类的表述。这是最要命的一条：按我们项目的测量纪律（n=1 的重复单元零信息量、必须有噪声地板 δ 与"不可分辨"档），它报告的 **+0.83（builder_usefulness）** 是 6 题 × 1 次 × 1 判官、**零重复、零方差估计**的读数，与噪声不可区分。**唯一有真实区分度的维度恰恰是它唯一输的那一维**（builder_usefulness 4 vs 9）——而它的 4 个"胜利"维度在处理臂上全部顶格饱和（breadth 6 题全 9，novelty 5×8，trap 9–10，actionability 9–10），**动态范围≈0**。

**★ 站点自己把"成功"定义成了什么（最露骨的部分）**：
- **它的"成功"**不是"想到了多少承重维度"，而是"**输出里有没有那一段**"。`trap_detection` 之所以能拿 9.50 vs 1.83，是因为 critic 段**必然**产出一个标题为 "Traps (look good, aren't)" 的列表并带机械原因，而 baseline 自由散文里**根本没有叫 Traps 的段**——判官只需做**标签匹配**。**transcripts 实测：4 题的 baseline 里有 4–6 个显式 `**Cons:**` 段，写的正是机制性失败理由，判官照样只给 1–3 分。** 同理 `breadth`：ADHD 输出天然带 5–7 个 cluster label（"remove-the-server plays" 这种），baseline 只有散文，判官更容易"数出角度"。
  **更致命的是：判官报的"角度数"就是聚类数。** 逐题对照（判官 reason 里的数 vs transcripts 里实际的 cluster label 数）：lru-100ms 7 vs 7、monolith-split 6 vs 6、fuzzy-bug 7 vs 6、rate-limit-leader 6 vs 5、naming-feature-flag 8 vs 7、llm-hang-cli 9 vs 6。**判官数的永远是那 5–7 个角度标签（最多 +3），而它的分数恒为 9/10——真实计数 5、6、7 个 cluster 都给 9 分。** ⇒ **breadth=9 是一个常数，与实际宽度无关**；它既没数 30 个想法，也没数 5 个分支，只数了 critic 自己吐出的 5–7 个标签。
  ⇒ 结论：**这不是"宽度"指标，是一个被 schema 决定、且在处理臂上饱和的常数。** 预印本承认了同一现象的一半（actionability 被 deepen 的结构优势混淆），但没意识到它对 breadth/trap 两维同样成立。
- 站点还把自己的"判官即被测同源"问题**写成了机制论**（博客 "Single-context evaluation"：*"When the same call both generates and judges, the implicit critic filters ideas toward safe and defensible **during** generation"*）——**它在理论上精确地描述了自评污染，却在自己的评测里执行了它**（判官与生成器同一个模型，见 §6）。
- 站点对"3× 更常出真想法"的自我标注很诚实："This is directional, **not measured** — one practitioner's observation, not a controlled result."（挂在 issue #13 未做）。**这说明作者知道"不可分辨"这个概念，只是没用在自己的主指标上。**
- ★ 站点**从头到尾没有出现过 "success" 一词**（全站 104 011 B 文本 grep 命中 0 次），也没有阈值、没有显著性、没有 CI、没有噪声地板。**它的"成功"= 判官说 A 赢了 + 5 个维度的均值更好看。** 这是一条可复用的判据检查：拿到任何"某框架有效"的自评文档，先 grep "success/threshold/noise floor/significan"，grep 不到就说明它没有可证伪的成功标准。

---

## 4. 自认的局限（站点 `evals/results` "Known limitations" 原话 + 相关原话）

> **Stated plainly, because reviewers will find them anyway:**
>
> - **Same-model judging.** The judge is the same model family as the generator (familiarity bias). Cross-model judging is on the roadmap (issue #6).
> - **Small set.** Six problems, all engineering-shaped.
> - **Scale gap.** Evals run at K=5 branches; the academic diversity literature measures at K=100. Bridging this is tracked in issue #18.
> - **Human-in-the-loop applicability is unproven.** A controlled CHI 2025 study found no significant benefit from LLM problem-reframing with human designers. ADHD's LLM-to-LLM context differs, but this is honest counter-evidence, tracked in issue #16.

补充三条同源原话：
- 站点 `concepts/vs-cot-and-tot`："**External corroboration (anecdotal).** … This is directional, not measured — one practitioner's observation, not a controlled result."
- 外部评测者（miyagadget）："These quality scores are a blind LLM-as-judge — subjective, and unlike the objective time/size numbers." / "Small sample (2 problems)"
- 预印本 Limitations："**Frame library is hand-authored.** … A frame can fail silently — producing paraphrases of another frame's ideas — without the harness catching it. Frame-quality evaluation is future work."

**没写的局限（我们补上）**：没有写"输出 schema 不对称导致测的是格式"、没有写"同一模型三用（generator/critic/judge）"、没有写"判官打分在处理臂上饱和"、没有写"每题只跑一次"、没有写"帧选择不可复现"。

---

## 5. ★ 对我们项目的可迁移点

**映射到路线 A / B / C**
- 它是**路线 A 的干净实例**：拓扑完全手写固定（reframe → N×diverge → score ∥ cluster → K×deepen），**零学习成分、零更新规则**。对我们：**它提供的是"可照抄的结构约束"，不是"可抄的优化器"**。
- 路线 B（训练架构）：**无贡献**。没有 policy、没有 RL、没有可学习参数、没有梯度。
- 路线 C（人定拓扑 + 训练调参数）：**它是 C 的 L0/L1 部分的一个现成样例**——目标函数（`novelty/viability/fit` 0–10 + 固定权重 0.35/0.40/0.25）、动作集合、硬墙、隔离不变式，全是手写的；**L2–L4 全空**。

**优化器契约 L0–L4 的对应（这一栏最有用）**
| 层级 | 它有没有 | 证据 |
|---|---|---|
| L0 目标函数 | ✅ 有 | `total = novelty*0.35 + viability*0.40 + fit*0.25`（`engine.ts:218`），三轴 0–10 |
| L1 动作算子 | ✅ 有（枚举完备） | reframe / diverge / score / cluster / deepen + 4 个本地算子 |
| L2 更新规则 | ❌ **无** | 评分只用于排序切片，**不回传给发散**；分支失败就失败（`Promise.allSettled` + 记 `failedFrames`），**不重试、不换帧** |
| L3 搜索 | ❌ 无 | 单趟，无 beam、无回溯、无迭代 deepen（递归 deepen 还在 roadmap issue 上） |
| L4 学习 | ❌ 无 | 帧权重、prompt 全部手写；"learn which frames win for which problem shapes" 挂在 issue #10 |

**能省我们哪个具体实验**
1. **省掉"隔离不变式怎么实现"这一类的工程活**：每 branch 独立 `query()`、无共享 KV、无共享 message history、`systemPrompt: {type:"preset", preset:"claude_code", append: ...}`、`tools: []`（`src/llm.ts:17-28`）——这套"真并发推理而非共享轨迹上的交错解码"可以直接抄。
2. **省掉"视角算子怎么写"**：`src/frames.ts` 15 个 frame 的 `prompt` 写法（"You are X. Re-ask this as Y."）+ 四标签体系（`code/design/general/wild`）+ "4 engineering + 1 wild 保留位"的选择规则，可以直接当我们的**维度探针库**。**但要把它们当"视角提示"抄，不能当"维度"抄**（见 §6）。
3. **省掉"DEV 题怎么出"的规范**：`evals/methodology` 给的 4 条好题判据可以直接抄——① answer space 开放（不是"X 的语法是什么"）；② 有**非平凡的显然答案**（让 baseline 有可信的退路）；③ 有**具体约束**（现有题里的 "100ms" / "leader election"）奖励非显然思考；④ category 不要已被过度代表。
4. **省掉"输出 schema 该长什么样"**：`render.ts` 的 6 段式 + `[N V F]` 芯片 + `★ non-obvious pick` + 每条 trap 带机械原因 + 每条 idea 带 `+ strength`，是一份现成的**结构化输出 schema**——对我们有用（可做成"每个承重维度一个固定 slot"的形式化载体），但**必须**配等-schema 对照臂（见下）。

**要改什么才能用（硬性）**
- **判官必须换源**（他们自己列 issue #6）：我们的判官不能与被测同源，且要给出"同源/异源"两套读数。
- **判据载体必须换成结构量**：他们的 0–10 自由打分不可用作"净维度增益"的代理；我们的对应物是"依据包可核验 + 改变决策"的承重信息数。
- **必须加**：重复运行（题内重复测量）、噪声地板 δ、预注册的"不可分辨"档、以及**等 schema 对照臂**（baseline 也给同一份 schema，否则重蹈他们的格式混淆）。
- **重测帧选择**：他们的帧集每次跑都不同（无 seed），我们的实验必须锁帧集（这是他们没有、我们必须有的）。

---

## 6. ★ 不可迁移 / 会误导我们的点

### 6.1 判官同源：**不是"同族"，是同一个模型**（U6 实锤）
`bench/run-evals.ts` 里 baseline（`:82`）、ADHD 臂（`:85`）、judge（`:93`）**三处都没有传 `model`** ⇒ 全部落到 `src/llm.ts:19` 的 `model: opts.model` = `undefined` ⇒ Claude Agent SDK 默认模型。loop 内的 critic 同理（`engine.ts:330` `criticModel ?? model`，评测里也没设 `criticModel`），deepen 用 generator 模型。**生成器、收敛判官、评测判官三者同为默认模型。**
并且**站点同一页自相矛盾**：`evals/results` 开头写 "judged by an **independent** LLM with a skeptical-staff-engineer prompt"（`index.md` 也写 "Independent LLM judge"），而同一页的 Known limitations 写 "the judge is the **same model family** as the generator"。⇒ **他们页面上的"independent"只指"独立的一次 API 调用"，不是"独立的模型"。** 我们不要把这类数字当"有效信息维度数"的证据。

### 6.2 "宽度/新颖性"到底数的是什么（模板第 6 节重点，直接回答）
- **数的是：判官在渲染后的文本里能"数出"的结构上不同的角度**，判官自己写 reason 时口径逐题漂移——EVALS.md 逐题原文分别是："7 structurally distinct categories"（lru-100ms）、"9 structurally different categories"（llm-hang-cli）、"6 architecturally distinct families"（rate-limit-leader）、"7 structurally distinct lens families"（fuzzy-bug）、"~40 structurally distinct ideas across 6 categories"（monolith-split）、"8 structurally distinct conceptual spaces"（naming-feature-flag）。**同一维度在 6 题里有 5 种不同计数单位（categories / families / lens families / ideas / spaces）**。
  ★ **我在 transcripts 里拿到了这些数的真值**：判官报的"角度数" ≈ **critic 输出的 cluster label 数**（5–7 个，最多 +3），既不是 30 个想法、也不是 5（或 4）个分支，也不是 `CLUSTER_SYSTEM` 规定的 3–6。**真实 cluster 数 5 / 6 / 7 时，判官分数一律 9/10** ⇒ 宽度分与实际宽度**脱钩**。
- **不是**想法条数（24–30）、**不是**帧数（5 或 4，见差异 3）；它**≈ 就是 critic 自己吐出的实际 cluster label 数**（5–7 个，比 `CLUSTER_SYSTEM` 规定的 "3-6 clusters" 略多），再在此基础上 +0~+3 的自由发挥。llm-hang-cli 那题判官说"9 categories"却只列了 6 个名字（economic incentives / async control surfaces / gamification / perceptual distortion / collective intelligence / redundancy races）——**它自己数不清**。
- **有没有 embedding / 相似度参与？——没有，一处都没有。** 我对整个仓库（含 `bench/`、`src/`、`documentation/`、`EVALS.md`、`README.md`）grep 了 `embed|cosine|similarity|semantic|vector|minh|bertscore|rouge|bleu|jaccard|levenshtein|tf-?idf`：**唯一命中是 EVALS.md 里一个自然语言 "semantically adjacent"**，无任何计算性用法。**没有去重算法、没有相似度阈值、没有聚类 embedding。**
  ⇒ 我们的 U2/U3 风险（embo-01 embedding 中文句级几何无分辨率）**在这个项目上不成立**——但它换了一种更隐蔽的同源污染：**全部宽度信号由一个同源 LLM 自由打分产生**，且该打分在处理臂上高度饱和（breadth 6 题全 9，零方差；novelty 5×8；trap 9–10；actionability 9–10）。**4/5 维度在处理臂上无区分度 ⇒ 指标没有信噪比（U4）。**
- ⇒ **U7 的正面反例**：它的 "breadth" 数的是"角度数"，不是"承重维度数"，而且是**判官自数的角度数**。它没有、也无法回答我们的问题；照搬"隔离分支数 = 思维面宽"的推论会**把我们项目最核心的区分点弄反**。

### 6.3 schema-as-treatment 混淆（最容易被骗的一点）
baseline = 自由散文；ADHD = 固定 5 段式 schema（`Wide set` / `Converge — shortlist` / `Traps (look good, aren't)` / `Focus — deepened branches` / `Provocation` + `[N7 V8 F9]` 芯片 + `★ non-obvious pick`）。判官要打的"trap detection"在两边**根本不是同一个量**：一边是"有一整段带原因的 trap 列表"，一边是"散文里顺带提了一句风险"。
**transcripts 实证**：4 题的 baseline 里明明有 4–6 个显式 `**Cons:**` 段（机制性理由齐全："WAL grows unbounded (need compaction/snapshots)"、"Fsync can block on some filesystems"、"Platform-specific behavior (mmap reliability varies)"、"Race conditions between cache state and log"），判官仍给 trap_detection = **1–3**；ADHD 臂因为有一段标题就叫 "Traps" 的东西，全部 9–10。⇒ **这一维测的是"段落标题匹配"，不是"是否点出陷阱"。**
`breadth` 同理：cluster label 给判官提供了现成的"角度名"去数，而 transcripts 显示它数的就是 5–7 个 cluster label（真实计数 5/6/7 个 cluster → 判官分数恒为 9）。
再叠加**长度不对称**：判官看到的 ADHD 文本是 baseline 的 **3.4–4.9 倍**（17–21 K vs 2–5.6 K 字符），条目数 24–30 vs 散文若干段。"10 minor variations of one idea = low breadth" 这条 rubric，作用在"30 条带芯片的清单"vs"一段连贯散文"上，**长度与结构本身就足以预测分数**。
⇒ 预印本只承认了 actionability 一维被混淆（"Confounded by deepen quality… A fairer ablation would equip the baseline with the same output schema"），**没意识到 breadth/trap 两维同样被 schema 决定**。**任何"schema 更好的系统赢"的对比，都要先做等-schema 对照臂。**

### 6.4 "盲评"是假盲（transcripts 级实证）
`bench/judge.ts:29` 的 system prompt："You do NOT know which system produced which output. Score on substance only."——但从 transcripts 看，两份输出的**版式**截然不同：ADHD 臂是 6 个固定粗体段 + 30 条带 `[N7 V8 F9]` 芯片的条目 + `★ non-obvious pick` + `Traps (look good, aren't)`；baseline 是连贯散文 + markdown `##` 小标题 + `**Cons:**` 列表。**任何 LLM 判官读一遍就能认出谁是谁**（"Wide set / Converge — shortlist / Focus — deepened branches / Provocation" 这组词是 ADHD 独有的）。**位置偏置被打乱 ≠ 身份盲。**
外部复现也是同样的盲法："quality was scored blind by a separate claude call"——**separate call，但同一个模型家族，同一版式线索**。
⇒ 我们要真盲，必须做**格式归一化**：同一渲染器、同一 schema、同一长度量级，只换内容；再叠加 §6.1 的换判官。

### 6.5 文档站 vs GitHub 仓库（`UditAkhourii/adhd`）的口径差异（逐条，全部与 2026-10-21 HEAD 逐字节核过）
1. **"deterministic per-seed" 是假的**（**两处**）。站点 `concepts/frames`："Selection is **deterministic per-seed** so runs are reproducible — but varies across sessions…"；`concepts/how-it-works`："Frame selection is deterministic per-seed with a `codeMode` bias…"。但 `src/frames.ts:36` 的 `selectFrames(n, codeMode, packs)` **没有 seed 参数**，用 `Math.random()` 做 Fisher-Yates 洗牌 + 随机抽 wild；`tests/frames.test.ts` 的注释直接写 "**Selection is random**, so one call can miss a duplicate that most calls hit"。⇒ **同一题重跑得到不同帧集，评测在帧层面不可复现**；"5 frames" 本身也不固定。
2. **站点 `concepts/how-it-works` 完全没写 PHASE 0 reframe**。源码默认 `stripAnchors=true`，会多一次 LLM 调用并**可能改写发给每个分支的题面**（收敛仍对原题评分，`engine.ts:341` 注释）。站点两处成本口径（"≈ N + K + 2 calls (≈10 at defaults)"、"5 diverge + 1 score + 1 cluster + 3 deepen ≈ 10 Agent calls"）**都没算它 ⇒ 实际 11 次**。
   ⚠️ 但**本轮公开评测里 reframe 没有触发改写**（6 份 transcripts 均无 `Reframed for divergence:` 行）⇒ "分支题面 ≠ baseline 题面"这个处理差**在这批评测中未发生**（调用次数仍是 11）。**注意：这一条只在本次快照上成立，不能推广。**
3. **分支数可能不是 5**（源码机制 + transcripts 实测双证）：`selectFrames` 先取 4 个工程帧，再从 wild 池随机抽 1 个；**若抽中的 wild 已在那 4 个里则不补入**（`frames.ts:63` 的 `if (!picked.find(...))`）。core 的 8 个 wild 帧里有 7 个同时带 `code`/`design` 标签（会进工程池）⇒ 理论 P(只出 4 支) ≈ (7/8)×(4/14) ≈ **25%**。**实测：6 题里 2 题（llm-hang-cli、rate-limit-leader）确实是 4 支 / 24 个想法。** ⇒ 站点"Default is 5 × 6 = 30"、"5 frames × 6 ideas, top-3 deepened"（EVALS.md 方法学脚注）在 1/3 的题上不成立。
4. **旗舰例子的数字与它自己引的 transcripts 对不上**。`index.md` 与仓库 `README.md` 的 side-by-side（明说 "Full transcripts in `bench/results.json`"）写 "ADHD spawns **6** isolated frames, surfaces 30+ ideas" 与 "trap detection **~8** vs ~2"；但 `bench/run-evals.ts:37` 用的是 `framesPerRun: 5`，`EVALS.md` 该题行是 `trap_detection | 10 | 2`（不是 ~8）、breadth 9 vs 6、novelty 8 vs 3。⇒ **index/README 的示例引文与被引记录有出入**（~8 vs 10、6 frames vs 5 frames）。
5. **"independent LLM" vs "same model family" 同一页矛盾**（见 6.1）。
6. **站点与仓库 `documentation/` 是两套文本，不要混用**：站点 21 页，仓库 `documentation/` 只有 8 页（`api/evals/frames/how-it-works/quickstart/vs-cot-and-tot/when-to-use` + `install.md`）；站点多出 `installation`、`usage/cli`、`usage/library`、`usage/agent-integration`、`evals/{results,methodology,roadmap}`、`community/{adopters,contributing}` 与 5 篇 blog。**共有页面的数字完全一致**（results 表 = EVALS.md，5 行均值逐题复算全部吻合）；但站点版在"成本模型 / 外部基准 / 已知局限 / reframe 缺席"上更细 ⇒ **拿仓库 `documentation/` 当站点口径会漏掉这些**。
7. 站点的 `nonObviousPick` 描述略偏：`usage/library` 说 "the highest-novelty **viable** idea"，源码实为 `argmax(novelty + 0.5*viability)`（`engine.ts:412-419`），不是纯 novelty；且 shortlist 长度在默认 `topK=3` 时**恒为 4**（`slice(0, max(2, min(4, topK+1)))`），而文档写"2–4"。
8. 站点 `evals/methodology`："The eval suite is **local only** — there is no CI workflow for it."（指的是评测没有 CI，不是仓库没有 CI；仓库 README 有 CI 徽章。**未核实**线上 `.github/` 内容——GitHub API 当时被限流。）
9. ★ **公开 transcripts 由旧版代码生成，与今天的 HEAD 不是同一份产物**：transcripts 里的 trap 段标题是 **"Traps (look good, aren't)"**，而 HEAD 的 `src/render.ts:61` 写的是 **"Traps (watch-outs, not verdicts)"**（`render.ts` 已逐字节 diff 确认 live == local == HEAD）。⇒ **站点/EVALS.md 引用的数字无法用今天的代码逐字节复现**；引用这些数字时必须标注"生成于旧版 build（2026-05-25）"。
10. 站点说 trap 数量 "15–20"，实测是 **10–20**（fuzzy-bug 只有 10 条）⇒ 站点这一句在**自己出的数据上偏窄**。

### 6.6 量纲 / 样本量 / 其他
- **n=6、每题 1 次、单判官、零重复** ⇒ 所有 Δ 没有方差估计、没有 CI、没有噪声地板。按我们项目的纪律，这些数字**不足以支撑任何"有效维度增益"的结论**。
- **"宽度"的口径与我们的"承重维度"根本不是一回事**（见 6.2）——量纲不同，不可换算。
- **K=5 vs 学术 diversity 文献的 K=100**（站点自认 issue #18）：即使在他们自己的口径下，K=5 也远低于文献测量点。
- **成本口径不可直接引用**：站点只给公式不给美元/token 读数（"a few cents to a few dollars" 是区间话术），我们若要报成本需自己实测。
- **CHI 2025 反证在站点里没有给出文献链接**，只指向 issue #16 ⇒ 该条外部反证**未取到原始出处**（GitHub API 限流，未能打开 issue）。**未验证。**
- **外部独立复现只有 1 个、2 题、且它的判官也是 Claude（"quality was scored blind by a separate claude call"）** ⇒ **同样同源**，不能当"外部同源污染已解决"的证据。
- **文档站自己就写出了 U6 的机制（"Single-context evaluation"），却没在自己的评测里避免它** ⇒ 读这类"自建框架 + 自评"的文档时，**要以源码与 transcripts 为准，不以营销段落为准**。

---

## 7. 逐字摘录

> **Same-model judging.** The judge is the same model family as the generator (familiarity bias). Cross-model judging is on the roadmap ([issue #6](https://github.com/UditAkhourii/adhd/issues/6)).
> — 站点 `evals/results` → "## Known limitations" 第 1 条

> Convergence is a **separate LLM call** with an inverted system prompt (critic posture, evaluation mandatory). No heuristic threshold and no logit-bias steering — the critic's structured output *is* the pruning decision. Default `K=3`; the `nonObviousPick` field surfaces the highest-novelty viable leaf even if it's not the highest-fit.
> — 站点 `concepts/how-it-works` → "## Architecture — the mechanism, not the metaphor" → "### Pruning & convergence criteria"

> Selection is **deterministic per-seed** so runs are reproducible — but varies across sessions so the same problem produces different candidate sets when re-run.
> — 站点 `concepts/frames` → "## How frames are selected"（**与源码 `src/frames.ts:36` 冲突：源码无 seed，用 `Math.random()`**）

> - breadth: range of structurally DISTINCT angles. 10 minor variations of one idea = low breadth.
> - novelty: how many ideas are non-obvious-but-viable. The obvious textbook answer is NOT novel.
> — 仓库 `bench/judge.ts:32-33`，`JUDGE_SYSTEM` 的 rubric 原文（判官读到的就是这两行 + "You do NOT know which system produced which output"）

> **External corroboration (anecdotal).** A reader running the comparison by hand reported that running the same prompt five times in *parallel* agents surfaces actually-distinct ideas about **3× as often** as a single agent prompted to "list 5 options first." This is directional, not measured — one practitioner's observation, not a controlled result.
> — 站点 `concepts/vs-cot-and-tot` → "## Why prompted alternatives don't replicate parallel divergence"

> **Confounded by deepen quality.** The actionability delta is partly explained by the deepen pass, which gives ADHD a structural advantage (sketch + risk + first step) that the baseline's free-form prose does not enforce. A fairer ablation would equip the baseline with the same output schema; we expect ADHD's lead to shrink on this dimension but not on breadth, novelty, or trap detection.
> — 关联预印本（adhdstack.github.io）"Discussion and limitations"（站点未收录此段，但它是最关键的一条自我否定）

> **Cons:** WAL grows unbounded (need compaction/snapshots) · Fsync can block on some filesystems · Platform-specific behavior (mmap reliability varies) — *（baseline 输出 `lru-100ms` 的第 1/3/4 段里逐字摘出的"风险"条目，同一份输出的判官 trap_detection 得分 = 2/10；而同一份 ADHD 输出里有一整段标题为 "Traps (look good, aren't)"、含 20 条带机制理由的条目，得分 10/10。）*
> — `bench/results.json` → `baselineOutput` / `adhdOutput`（2026-05-25 那次运行的原文）

---

## 8. 读完后我自己的一句判断

**最值得抄的**：不是它的数字，而是**它的"硬墙 + 隔离"三条不变式**（分支互不可见；生成与评价必须是分开的 API 调用与相反 system prompt；"score before deepen"）——这三条正是"思维面能不能变宽"的前置条件，抄来当**路线 A 的结构骨架**（配"每个承重维度一个固定 slot、每 slot 必须带一条依据"的 schema，就能把"角度"升级成"可核验维度"）。同时抄它的 `render.ts` **输出 schema**（`[N V F]` 芯片、`★ non-obvious pick`、trap 带机械原因、每条带 `+ strength`）——这是现成的"承重信息载体"模板。

**最容易骗我们的**：**"9.00 vs 4.83"这组数字**。它看起来正是 U7 的正例（隔离 → 更宽），实则是三重偏差的乘积：①**判官与生成器是同一个模型**（源码级确认，连"同族"都不是）；②**判官在处理臂上打满分饱和**（breadth 6 题全 9、零方差；4/5 维无区分度）；③**输出 schema 不对称**（transcripts 级实证：baseline 有 4–6 个带机制理由的 `**Cons:**` 段仍只得 trap_detection 1–3 分，ADHD 有一整段叫 "Traps" 就得 10 分；判官数的"角度数"就是 critic 吐出的 5–7 个 cluster label，真实 5/6/7 个都判 9）。再叠加"每题只跑一次、零重复、零噪声地板、零不可分辨档"、"帧选择无 seed ⇒ 复现不了"、"6 题里 2 题实际只跑了 4 支分支"、"公开 transcripts 由旧版 render 生成（标题文字已变）"。**若照搬"分支隔离 ⇒ 思维面变宽 ⇒ Δ=+4.17"这条推论，我们会把本项目最核心的区分点（角度多 ≠ 承重维度多）弄反。**

**这个项目对我们的真正价值不是结论，而是方法论反例**：它是目前最完整的一份"**同源判官 + 不等 schema + 零重复 + 不可复现帧集**"的成套反例模板。**我们可以直接把它改造成我们 DEV 集的必测对照臂清单**（①等 schema 渲染器；②异源判官 + 同源判官双读数；③题内重复 k 次给噪声地板 δ；④锁帧集 + 记 seed；⑤"不可分辨"档），这五样它一个都没做——**我们只要做齐了，它那 4.17 分就自动失效。**

---

## 附：来源清单

**在线（访问日期 2026-10-21）**
| URL | 取到什么 |
|---|---|
| `https://adhd.mintlify.site/llms.txt` | 200，4 735 B，21 页索引（Introduction/Quickstart/Installation/How It Works/Frames/vs CoT&ToT/When to Use/Skill/CLI/Library/Agent Integration/Results/Methodology/Roadmap/Adopters/Contributing + 5 篇 blog） |
| `https://adhd.mintlify.site/llms-full.txt` | 200，104 011 B，**全站正文**（本篇全部站点引文的来源；已按 `Source:` 行切成 21 个 `pages/*.md`） |
| `https://adhd.mintlify.site/sitemap.xml` | 200，3 032 B，22 URL，全部 `lastmod = 2026-08-22` |
| `https://adhd.mintlify.site/<path>.md`（`index`/`quickstart`/`installation`/`concepts/{how-it-works,frames,vs-cot-and-tot,when-to-use}`/`usage/{skill,cli,library,agent-integration}`/`evals/{results,methodology,roadmap}`/`community/{adopters,contributing}`） | 全部 200（2 085–7 062 B），落盘 `mintlify/md_*.md` |
| `https://raw.githubusercontent.com/UditAkhourii/adhd/main/{src/frames.ts,src/engine.ts,src/packs/core.ts,src/render.ts,src/types.ts,src/cli.ts,src/index.ts,bench/judge.ts,bench/run-evals.ts,EVALS.md,documentation/*.md,tests/frames.test.ts}` | 全部 200；与本地副本 **逐字节相同**（`render.ts` 亦已 diff：live == local == HEAD）；落盘 `mintlify/live/` |
| `https://api.github.com/repos/UditAkhourii/adhd/contents/bench/results.json?ref=main` | 200，**152 020 B**（base64 解码后落盘 `mintlify/live/results.json`）——**公开评测的完整 transcripts**，本篇 §2/§3/§6 的关键证据全部来自它。注：`raw.githubusercontent.com` 直接下载该文件时连接反复超时（分块重试只得 53 108 B 开头片段），改用 contents API 才取全 |
| `https://raw.githubusercontent.com/UditAkhourii/adhd/main/documentation/install.md` | 200（4 271 B）——确认存在，README 链接未断 |
| `https://api.github.com/repos/UditAkhourii/adhd` | 200：stars 4444、forks 302、public、MIT、created 2026-05-25、pushed 2026-10-05、open_issues 15 |
| `https://miyagadget.page/en/blog/2026/06/03/adhd-coding-agent-skill-en/` | 200，83 330 B（落盘 `mintlify/miyagadget.html`）——**唯一外部独立复现全文**（2 题盲评、耗时/输出倍率、caveats） |
| `https://export.arxiv.org/api/query?id_list=2510.01171` | 200 —— "Verbalized Sampling: How to Mitigate Mode Collapse and Unlock LLM Diversity"，摘要含 "increases diversity by 1.6-2.1x over direct prompting"（与站点引用吻合） |
| `https://export.arxiv.org/api/query?id_list=2505.18949` | 200 —— "The Price of Format: Diversity Collapse in LLMs"（站点"格式诱发锚定"那句的出处） |
| `https://adhdstack.github.io/` | 关联预印本（本篇只用于取 §4/§7 两条原话；**未取到 arXiv id / DOI**） |

**本地文件（均为 2026-10-21 抓取/快照）**
- `_raw/mintlify/llms.txt`、`llms-full.txt`、`sitemap.xml`、`md_*.md`（16）、`pages/*.md`（21）、`live/*`（GitHub HEAD 源码 17 个）、`live/results.json`（**评测 transcripts，152 020 B**）、`miyagadget.html`
- `_raw/adhd/src/engine.ts`（phases、权重、shortlist、nonObviousPick、critic 默认）、`src/frames.ts`（`selectFrames` 无 seed）、`src/packs/core.ts`（15 帧 + tags）、`src/llm.ts`（`model: opts.model` = undefined）、`src/render.ts`（输出 schema，trap 段标题 "Traps (watch-outs, not verdicts)"）、`src/types.ts`（状态类型）、`bench/judge.ts`（判官 system prompt 与 rubric）、`bench/run-evals.ts`（baseline/ADHD/judge 三处不传 model；`framesPerRun: 5`）、`bench/problems.json`（6 题）、`EVALS.md`（逐题读数）、`README.md`、`skills/adhd/SKILL.md`（pre-flight gate、成本、15 帧表）
- `_raw/adhdstack/paper.txt`（预印本正文，取 "Confounded by deepen quality" / "Frame library is hand-authored" / "US$0.30" 三处原话）

**★ 评测 transcripts（`bench/results.json`，152 020 B，6 条完整记录：`adhdOutput` / `baselineOutput` / `verdict` / `swapped`）——我逐条解析后的可复算结论**（本篇 §2 表、§3、§6.3/6.4 的证据全部来自它）：

| problem | swapped | ADHD 字符 | baseline 字符 | 长度比 | **trap 段 ⚠ 条目** | **想法数** | 隐含分支数 | **cluster label 数** | judge trap_det | judge breadth |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| lru-100ms | true | 18 592 | 4 538 | 4.10× | 20 | 30 | 5 | 7 | 10 | 9 |
| llm-hang-cli | true | 17 851 | 5 244 | 3.40× | 20 | **24** | **4** | 6 | 10 | 9 |
| rate-limit-leader | true | 16 487 | 3 462 | 4.76× | 18 | **24** | **4** | 5 | 9 | 9 |
| fuzzy-bug | true | 17 572 | 3 909 | 4.50× | 10 | 30 | 5 | 6 | 9 | 9 |
| monolith-split | false | 21 198 | 5 632 | 3.76× | 18 | 30 | 5 | 6 | 10 | 9 |
| naming-feature-flag | false | 10 246 | 2 111 | 4.85× | 20 | 30 | 5 | 7 | 9 | 9 |
| **合计/均值** | — | **101 946** | **24 896** | **4.09×** | **106（17.7/题）** | **168（28/题）** | 4.67 | 6.17 | **9.50** | **9.00** |

四条可复算结论：
1. **判官的"陷阱数"就是段内条目数**（同量级）：judge 的 reason 逐字写 *"an entire section to **18 traps**"*（lru-100ms，实际 ⚠ = 20）、*"traps with **20 specific examples**"*（llm-hang-cli，实际 ⚠ = 20）——它读的是那一段，**不是**在通篇里判断"哪些想法是陷阱"。
2. **baseline 并不是"几乎从不点出陷阱"**（这一点必须说准）：4 题的 baseline 里有 4–6 个显式 `**Cons:**` 段 + 机制性理由（"WAL grows unbounded (need compaction/snapshots)"、"Fsync can block on some filesystems"、"Platform-specific behavior (mmap reliability varies)"、"Race conditions between cache state and log"…）；风险类关键词（trap/risk/downside/pitfall/caveat）逐题命中 0 / 2 / 2 / 0 / 6 / 0，合计 10 次。**判官仍给 trap_detection 1–3 分** ⇒ 该维测的是"**有没有一段标题叫 Traps 的东西**"，不是"是否点出陷阱"。
3. **长度 + 结构混淆**：ADHD 输出 4.09× 长（17–21 K vs 2–5.6 K 字符）、条目化（24–30 条带 `[N V F]` 芯片）⇒ 在更长、结构更规整的文本里"数出角度"天然更容易；Δ 最大的两维（breadth / trap_detection）同时被"段落存在性"与"长度"污染，且 **4/5 维在处理臂上顶格饱和（动态范围≈0）**。
4. **帧数与调用数**：想法数 30 的 4 题 ⇒ 5 帧；24 的 2 题 ⇒ **4 帧**（4×30+2×24=168）⇒ ADHD 侧调用数 = N(4 或 5) + score 1 + cluster 1 + deepen 3 + **reframe 1** = **10 或 11 次**（评测整体再 + baseline 1 + judge 1）。站点宣称的"5 frames × 6 ideas"与"10 calls"在这 2 题上不成立。

**未取到 / 未验证（明确列出试过的路径）**
- 预印本的 **arXiv id / DOI**：试了 `adhdstack.github.io`（页内无 arXiv 链接）、arXiv API（未按此标题检索命中）→ **未取到**，站点与仓库亦未给 arXiv 编号。
- **GitHub issues #6 / #13 / #16 / #18 正文**：`https://api.github.com/repos/UditAkhourii/adhd/issues/{6,13,16,18}` 返回 **403 rate limit**（未带 token 重试）→ **未取到**；因此站点引用的 "A controlled CHI 2025 study found no significant benefit from LLM problem-reframing with human designers" **未核实原始出处**。
- **站点 `community/adopters` 里的 16 个第三方仓库的落地情况**：只读了站点的自述表，**未逐一核验 PR/issue**。
- **评测用的具体模型名**：仓库、transcripts、站点**都没有记录**（只有 `model: undefined` ⇒ SDK 默认）⇒ **未取到**。
- **`.github/workflows` 内容**：GitHub API 限流，**未取到**（站点称评测无 CI，README 有 CI 徽章）。
- **`docs.json`（Mintlify 站点配置）**：`https://raw.githubusercontent.com/UditAkhourii/adhd/main/docs.json` → 404 ⇒ **站点与仓库 `documentation/` 的构建关系未确认**（本篇只记录"两者是两套文本，数字一致"这一事实，不推断生成关系）。
- **公开 transcripts 与 HEAD 的一致性**：已发现 trap 段标题不一致（见 §6.5 差异 9），**未做逐行 diff**（transcripts 是旧版 build 的产物，逐行 diff 必然大量不一致）⇒ 只报了可核的那一处。
