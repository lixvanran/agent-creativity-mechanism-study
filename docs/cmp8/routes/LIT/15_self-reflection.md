# 15 · matthewrenze/self-reflection（GitHub 仓库 · 代码与数据面）

> ⚠️ **重要结构性事实**：这个仓库**不是第 5 篇独立工作**，它是 **文件 14（arXiv 2405.06682）的官方代码与数据仓库**（README 首行即写明对应论文，README 的 "Research paper" 链接指向 `https://arxiv.org/abs/2405.06682`）。任务书把它单列一篇，是因为它额外暴露了**论文正文没写的东西**——尤其是**成本/token 账本**和**每个臂的确切实现**。本文件因此是"**同一工作的第二来源**"而不是"第七篇论文"，读法与前四篇不同。

---

## 0. 引用

- **仓库**：`matthewrenze/self-reflection`（GitHub，MIT）｜**作者**：Matthew Renze, Erhan Guven（Johns Hopkins）
- **对应论文**：arXiv 2405.06682 v2（2024-09-08），*Self-Reflection in LLM Agents: Effects on Problem-Solving Performance*
- **年份**：代码与数据 2024-04（`data/results/results.csv` 里的运行时间戳最早 2024-04-18）；仓库最后更新见 GitHub API
- **一句话声称**：README 写的是"研究自我反思在 LLM agent 上对解题表现的影响"——但**仓库自己给出的信息量远超论文正文**：它公开了 9 模型 × 11 题集 × 9 个臂的**逐题明细**（CSV）、**每题 token 数**、**每次运行美元成本**、**墙钟耗时**，以及**全部提示词原文**。

**我实际读了什么**（全部通过 `raw.githubusercontent.com` + GitHub REST API 拉取，逐文件）
- ✅ `README.md`（全文）
- ✅ `source/1_solve_with_baseline.py`（全文）、`source/2_reflect_on_solutions.py`（全文）、`source/3_save_reflections.py`（全文）、`source/4_solve_with_reflections.py`（全文）、`source/8_analyze_details.py`（全文）、`source/9_analyze_keywords.py`（全文）
- ✅ `source/agents/agent_factory.py`、`source/agents/answer_agent.py`、`source/agents/reflection_agent.py`（**全部提示词原文**）
- ✅ `source/instructions/instructions_file.py`
- ✅ `data/tables/pivot-results-by-model-and-agent.csv`（9×9 完整准确率矩阵）、`data/tables/results-by-model-and-agent.csv`（72 行，含 McNemar 统计量与 p 值）
- ✅ `data/results/results.csv`（**891 行运行账本**，含 token / 美元 / 耗时 —— **论文正文完全没报这些**）
- ✅ 目录结构（`source/` 27 项、`data/` 52,838 个 blob 的树形清单）
- ❌ **未读**：`data/dialogs/`（全部对话 JSON）、`data/logs/`（全部运行日志）、`data/reflections/`（全部反思原文）、`source/5,6,7_plot_*.py`、`source/verify_results.py`、`source/process/process_details.py`、`source/shared.py`（这些是绘图与校验脚本，不含新的机制信息）
- ⚠️ **未跑**：仓库代码本身（需要 9 家 API key + 付费调用），**没有复现任何数字**

---

## 1. 核心机制（**代码级**，能照着实现）

| 项 | 内容 |
|---|---|
| **输入** | 单步 MCQA，JSONL 格式：`{source, source_id, topic, context, question, choices:{A..D}, answer, solution}`。11 个题集文件：`comprehensive-100 / aqua-rat-100 / logiqa-en-100 / lsat-ar-100 / lsat-lr-100 / lsat-rc-100 / sat-en-100 / sat-math-100 / arc-challenge-100 / hella-swag-100 / med-mcqa-100` |
| **状态表示** | **纯文本**。`AnswerAgent.dialog` = 一个消息列表（system / user / assistant 示例 / user 题面 / assistant 答案）。反思状态 = 一个**字符串**，被 `set_reflection()` 拼到题面消息尾部 |
| **动作/算子** | `agent_factory.create(agent_type, model, topic)` 支持 10 个名字：`baseline, retry, keywords, advice, explanation, instructions, solution, composite, unredacted`（9 个走 `AnswerAgent`）+ `reflection`（走 `ReflectionAgent`）。<br>`AnswerAgent.get_answer()` → 模型产出 → `get_answer_choice()` 用正则 `Answer\("([^"]*)"\)` 抽字母；抽不到 = `None` = 判错 |
| **过程/回路** | **4 段批处理管线**（不是 agent 循环）：<br>`1_solve_with_baseline.py`（基线答题，`attempt_id=1`）→ `2_reflect_on_solutions.py`（对**答错**的题生成反思）→ `3_save_reflections.py`（**redact 答案** + 按 5 个小节切开存 6 份）→ `4_solve_with_reflections.py`（`attempt_id=2`，注入各自反思重答）<br>**停止条件：没有停止条件。** 每题只跑"基线一次 + 反思一次 + 重答一次"。**没有迭代、没有选择、没有更新规则** |
| **输出** | `data/details/{model} - {agent} - {exam}.csv`（逐题明细）+ `data/results/results.csv`（每次运行一行：token、成本、耗时）+ `data/tables/*.csv`（汇总） |
| **谁来评价** | ★ **外部 oracle**（题库标准答案）。`is_correct = (answer == problem.answer)`，`score = 1 if is_correct else 0`。<br>**评价信号怎么回传**：**不回传**。唯一的"回传"是 `if details_reader.is_correct(...)` 这个**分支**——答对了就跳过，不再进反思流程 |

**★ 三个"臂"的实现细节（论文正文说得含糊，代码里很清楚）**

1. **`retry` 臂的内容字面量是 `"No reflection information provided."`**（`4_solve_with_reflections.py` 第 ~130 行）：
   ```python
   if agent_name == "retry":
       reflection = "No reflection information provided."
   else:
       reflection = reflection_reader.read(reflection_file_path)
   ```
   ⇒ **`retry` 不是"不给任何东西"，而是"给同样格式的提示词框架，但内容为空"**。而这个框架的前缀（`answer_agent.py` 的 `reflection_prefix`）逐字是：
   > "Reflection:\nYou previously answered this question incorrectly.\nThen you reflected on the problem, your solution, and the correct answer.\nUse your self-reflection (below) to help you answer this question.\nAny information that you are not allowed to see will be marked [REDACTED]."
   ⇒ ★★ **`retry` 臂的 +0.041（GPT-4）度量的是"负向措辞 + 再答一次"这个纯框架效应，内容为零。**

2. **redact 的实现是贪婪字符串替换**（`3_save_reflections.py`）：对每个选项，把 `A ` / `A"` / `A.` / `A,` / `A:` / `A;` 以及**选项正文全文**替换成 `[REDACTED]`。脚注 1 承认 "It often redacting additional text that did not leak the answer."

3. **反思 prompt 里直接给了正确答案**（`2_reflect_on_solutions.py`）：
   ```python
   user_prompt = problem_text + "\n" + solution_text + "\n" + "\n --- \n"
   user_prompt += f"Correct Answer: {correct_answer}\n"
   ```
   ⇒ **oracle 进入了状态**。`unredacted` 臂 = 同一份反思但**不**做 redact。

---

## 2. 关键数字

**规模**
- 9 个模型 × 11 个题集 × 100 题 = **9900 次基线答题**（`data/details`）
- 基线答对后**不再重答**：只有答错的 **3794 题**进入反思+重答流程 ⇒ 8 个反思臂各 **3794 次重答**
- 整个研究共 **891 次运行记录**，**总花费 $262.07**

**★ 成本账本（`data/results/results.csv`，论文正文一个字都没提）**

| 臂 | 处理题数 | $/题 | token/题 | 相对基线成本 |
|---|---|---|---|---|
| baseline | 9900 | **$0.00743** | 671 | 1.00× |
| retry | 3794 | $0.00523 | 768 | 0.70× |
| keywords | 3794 | $0.00596 | 829 | 0.80× |
| advice | 3794 | $0.00630 | 886 | 0.85× |
| instructions | 3794 | $0.00660 | 904 | 0.89× |
| explanation | 3794 | $0.00561 | 840 | 0.76× |
| solution | 3794 | $0.00571 | 858 | 0.77× |
| **composite** | 3794 | **$0.00722** | **1107** | 0.97× |
| unredacted | 3794 | $0.00703 | 1154 | 0.95× |

**按模型（$/题）**
| 模型 | baseline | composite | 成本倍率 | token 倍率（baseline→composite） |
|---|---|---|---|---|
| GPT-4 | $0.02119 (611 tok) | $0.03198 (958 tok) | **+51%** | +57% |
| Claude 3 Opus | $0.02694 (808 tok) | $0.04068 (1435 tok) | **+51%** | +78% |
| Llama 2 70B | $0.00124 (780 tok) | $0.00224 (1403 tok) | **+81%** | +80% |
| Llama 2 7B / Gemini / Mistral 等 | — | — | — | — |

**准确率矩阵**（`pivot-results-by-model-and-agent.csv`，完整 9×9，见文件 14 Table 4）
- **GPT-4**：Baseline 0.786 → Retry 0.827 → Keywords 0.832 → Advice 0.840 → Instructions 0.849 → Explanation 0.876 → Solution 0.925 → Composite 0.932 → Unredacted 0.971
- **Llama 2 7B**（最弱）：0.297 → Composite 0.427 → Unredacted 0.495
- **Llama 2 70B**：0.376 → Composite 0.672 → Unredacted 0.837（**Unredacted−Composite = +0.165，最大**）

**统计量**（`results-by-model-and-agent.csv`，72 行）：McNemar 统计量 + p 值。**GPT-4 / retry**：χ=88.011, p=6.509e-21（文件 14 Table 3 写 χ=39.024 —— **仓库 CSV 与论文 Table 3 的 Retry 行不一致**！详见 §6 第 6 条）

**误差关键词分析**（`9_analyze_keywords.py`）：把反思里的 "Error Keywords" 段按**层级（depth）**统计（`depth == 1` 为最顶层），做**人工 remap**（`misinterpretation→interpretation`、`knowledge gap→knowledge`、…）和**停用词删除**（`error` / `incorrect` / `of the question` / `lack of` …），再按模型堆叠出 Top-100 关键词条形图。⚠️ **关键词只在 `comprehensive-100` 上统计**（代码里 `if "comprehensive-100" not in file_path: continue`）——**而这个题集被排除在论文主分析之外**。

---

## 3. ★ 它的「成功标准」是什么

**怎么判定自己成功了**（代码级）
1. **唯一指标 = 逐题 0/1 正确性**，聚合公式（`8_analyze_details.py` 内联实现，与论文 Eq.1 一致）：
   `baseline_accuracy = baseline_sum / total_rows`；`agent_accuracy = agent_sum / total_rows`（`agent_sum` = baseline 的分 + 反思臂重答对的数量）
2. **配对显著性 = McNemar**（`statsmodels.stats.contingency_tables.mcnemar`，`exact=False`），2×2 列联表由 `(baseline_scores[i], agent_scores[i])` 逐题填
3. **代码里有两条硬断言**（值得抄的工程习惯）：
   ```python
   assert len(baseline_table) == len(agent_table)
   assert baseline_sum <= agent_sum
   ```
   ⇒ **"反思臂不可能比基线差"被写成了断言**。（⚠️ 实际数据里 `explanation` 在 Llama-2-70B 上是 0.600 vs baseline 0.376，但那是**不同分母**下的聚合；这条断言只在"全体题"口径下成立。）

**否证/失败条件**
- ✅ **代码层有**：`verify_results.py` 存在（**我没读它的内容**）；`8_analyze_details.py` 里有 `assert baseline_sum <= agent_sum`
- ❌ **统计层没有"不可分辨"**：全部 p 值要么 `< 0.001` 要么给到 3 位有效数字；**没有重复运行、没有方差、没有噪声地板**
- ❌ **没有"这个臂没有效果"的报告格式**

**★ 一个论文没说、但代码暴露的事实**
`retry` 臂 = **同样的负向前缀 + 空内容**。所以 Baseline→Retry 的 +0.041（GPT-4）**不是"再试一次"的效果，而是"带负向措辞再试一次"的效果**。论文把它写成 *"the mere knowledge that the agent previously made a mistake improves the agent's performance"* —— **代码支持这个读法，但论文把它归因成了"自我察觉"，代码其实只支持"提示词框架变了"**。

---

## 4. 自认的局限（**代码里的自认，论文里没有**）

代码注释里作者自己写的 TODO / NOTE（逐字）：
- `agents/reflection_agent.py` 顶部：**"TODO: I need to add an section for error keywords to the reflection agent"**、**"TODO: I might need to refactor the explanation section to be more generic"**；`reflect()` 方法上方：**"TODO: Should I add the correct solution to the reflect prompt?"**
- `agents/answer_agent.py`：**"TODO: Should I add the number of times the question was answered incorrectly?"**、**"TODO: Should I move this into the constructor?"**
- `2_reflect_on_solutions.py` / `3_save_reflections.py` / `4_solve_with_reflections.py` 里成片的 **"# DEBUG: Answer only the first n problems"**、**"# DEBUG: Only process n problems"**（默认全跑，调试时截断）
- `8_analyze_details.py`：**"# Note: Don't use comprehensive 100 for analysis"**（排除题集）、`"# Sort by model_name, agent_name, exam_name, and problem_id"`、以及一段被注释掉的 `results._append` 旧版 pandas 用法（说明代码写于 pandas 1.x，后期 API 已变）
- `9_analyze_keywords.py`：关键词只在 `comprehensive-100` 上统计（`continue` 过滤），且**用大量人工 remap 表**做归一——**说明"错误类型"这个维度没有稳定的自动判据**

⚠️ 论文正文自认的局限见文件 14 §4（单步题、API 错误最高 2.8%、天花板压缩、LSAT-AR 主导聚合）。

---

## 5. ★ 对我们项目的可迁移点

### 5.1 ★★★ 抄「**框架 vs 内容**」的分离——这是本仓库最值钱的一行代码
`retry` 臂把**提示词框架（含负向措辞）保持完全一致，只把内容置空**。于是：
`Baseline → retry` = **纯框架效应**（含"上次错了"这句话本身）
`retry → composite` = **纯内容效应**
`composite → unredacted` = **答案残留效应**
⇒ **三段差值把"反思有用"这个复合命题拆成了三个可分离的量。**
- **省掉什么实验**：我们的"结构化状态"消融**必须包含这个空内容臂**。否则我们会把"提示词里多了一段话/多了一个负向措辞"记成"思维面变宽"。这正好对上我们坑 ⑦（负向措辞会把模型推进"修改上一版"模式 ⇒ 漂移被放大）。
- **要改什么**：我们的空内容臂不能是"空字符串"（那会让 prompt 结构变化），要抄它的做法：**保留同一段落模板、只把内容替换成一句无信息量的占位**。

### 5.2 ★★ 抄「**逐题明细 + token + 美元 + 耗时全量公开**」
`data/results/results.csv` 一行一次运行，带 `Input Tokens / Output Tokens / Total Tokens / Total Cost / Cost per Question / Runtime`。**论文正文一个字没提成本，仓库全给了。**
- **省掉什么实验**：我们的预算对齐（PROTOCOL §4.4）可以直接用这个**字段结构**做账本模板：`{arm, model, exam, nQ, in_tok, out_tok, $, wall_s}`。以后每跑一批实验，这个 CSV 就是唯一事实源，**成本不再是事后回忆**。
- **抄它的具体读数作为基线预期**：**"自我反思工作流 ≈ 基线成本的 1.5×（GPT-4/Opus），token ≈ 1.6–1.8×"**。这可以写进我们的**护栏 G1–G3（成本护栏）**做预注册阈值（例：允许工作流臂成本 ≤ 基线的 2×，超过就触发"用花絮换分数"的怀疑）。

### 5.3 ★★ 抄「**Unredacted 上界臂的代码实现 = 一个布尔开关**」
redact 逻辑集中在一个函数里（对 choice 字母做贪婪替换 + 对 choice 正文做全文替换），`unredacted` 臂 = **跳过这个函数**。⇒ 我们做"依据包全量直塞 vs 抽稀直塞"时，可以抄这个结构：一个 `redact(evidence) -> str` 函数 + 一个开关 ⇒ 两条臂只差这一个函数调用，**其余管线完全同构**（这正是我们需要的"公平对照"）。

### 5.4 抄「**McNemar + 2×2 列联表逐题填**」
`8_analyze_details.py` 的实现是教科书式的：逐题 `(baseline, agent)` 填 2×2 表 ⇒ **配对**。我们 DEV 集小、重复多，**配对检验比非配对更有功效**，可直接沿用。
- ⚠️ 但要改一处：它**只报 p 值不报效应量区间**。我们要加 **Δ 的 bootstrap CI**（因为我们的 n 小，p 值会误导）。

### 5.5 抄「**"错误类型"要做成有层级的离散标签**」
`9_analyze_keywords.py` 的设计很有启发：反思里让模型输出 **"Error Keywords: 从最泛到最具体"** 的分层列表，再按 `depth` 统计（`depth == 1` = 顶层类别），并用人工 remap 归一。
- ⇒ 我们的失败模式可以照抄成**分层标签**（顶层：前提错 / 工具错 / 目标错 → 底层具体项），而且**分层让我们能做"顶层类别分布"这种鲁棒统计**（不受措辞漂移影响）。
- ⚠️ 它的教训：**人工 remap 表的存在本身就说明"错误类型"没有稳定自动判据**。我们若要自动化，必须有**可核验的判据**（依据包里的具体条目），不能靠模型自由生成的关键词。

### 5.6 路线 A / B / C 的定位
- **路线 A（固定拓扑）**：这个仓库就是一个**极简固定拓扑**——`答题 → （若错）反思 → 重答`，反思的 5 个槽位是人写死的。**它就是路线 A 在单步题上的最小实例**。我们要做的是给它加上"多步 + 自由文本 + 依据包核验"。
- **路线 B（训练架构）**：仓库里**没有任何训练**（无 LoRA、无梯度、无 RL）。它是**纯 in-context**。⇒ 它的"改进"**全部来自上下文**。⇒ 它是路线 B 的**上界/对照**，不是先例。
- **路线 C（先设计再训练）**：它的"设计"部分（5 个槽位）是人写的，"调参"部分是 temperature=0 与 few-shot 例的选择。⇒ 它对应我们的 **L0（目标可重复）做得最干净的情形**（temp=0），**但 L1–L4 全缺**。

---

## 6. ★ 不可迁移 / 会误导我们的点

1. **★ 它的"成功"里有 oracle。** 反思 prompt 里写着 `Correct Answer: {correct_answer}`。**"反思"在这里是"把答案翻译成提示"**。⇒ 我们若照抄"把依据包喂给模型让它自己反思"⇒ 我们的"净维度增益"里会混进"依据被复述"的收益，**这就是坑 ⑥（自评污染）的温床**。
2. **★ `retry` 臂不是"无反馈"臂，是"负向措辞 + 空内容"臂。** 论文把它当成"只是重试"，代码证明它带着完整的负向框架。⇒ **论文里的 +0.041（GPT-4）不能被解释成"重试有用"，只能解释成"换了提示词框架有用"**。⇒ 我们引用这个数字时**必须带上这个限定**，否则我们会得出"给模型一句'你错了'就能涨分"这个危险结论。
3. **★ 仓库与论文的数字不一致（必须自己核）**：`results-by-model-and-agent.csv` 里 `gpt-35-turbo / retry` 的 Test Statistic = **88.011**、p = **6.509e-21**；而论文 Table 3 把 **88.011** 标在 **Explanation** 行、Retry 行的统计量是 **39.024**。⇒ **仓库 CSV 与论文表格存在错位**。⇒ 我们不能把仓库 CSV 当成论文表格的"更权威版本"直接引用；**引用前必须逐行对一遍**。
4. **★ `comprehensive-100` 的双重身份**：它被排除在**主统计**之外（`8_analyze_details.py` 注释），却被用作**错误关键词统计的唯一来源**（`9_analyze_keywords.py`）。⇒ 关键词结论的样本基础是**一个被排除的题集**，且**只有 100 题 × 9 模型**。⇒ 它的"错误类型分布"是**极弱证据**。
5. **★ 判据同源 + 单步 + 4 选 1**：和文件 14 同样的问题——**架构可抄，指标一句不可抄**。我们的"有效信息维度"是自由文本上的量，这篇的 0/1 正确性与之**不同量纲**。
6. **★ 没有重复运行**：温度 0.0 意味着**同一 prompt 重复跑结果相同**（缓存也一致）⇒ **它无法估计"同一臂换一次跑"的方差**。⇒ 它的臂间差值里混着供应商侧变动与 API 错误（自认最高 2.8%），**而 2.8% 已经大于很多臂间 Δ**（如 Command R+ 的 Keywords 0.770 vs Retry 0.745）。
7. **⚠️ 成本数字是 2024-04 的价目表**：仓库 `models/pricing.py` 用的是当时的单价，**不能直接搬到 2026 的价目上**。⇒ 抄的是**结构**和**倍率**（≈1.5× 成本、≈1.6–1.8× token），不是**绝对值**。
8. **⚠️ 它的"反思"是自由文本**：我们已知坑 ③（措辞级相似度在改写型环节彻底失效，约束 keep-Jaccard = 0.000）⇒ **不能靠"反思和上一版像不像"来判定反思有没有用**。这个仓库没有犯这个错（它靠 0/1 正确性），但**我们如果想用"反思长度/多样性"当辅助指标，就会踩进去**。

---

## 7. 逐字摘录

1. **`source/4_solve_with_reflections.py`（retry 臂的实现）**：
   > `if agent_name == "retry":` / `    reflection = "No reflection information provided."` / `else:` / `    reflection = reflection_reader.read(reflection_file_path)`
2. **`source/agents/answer_agent.py`（所有臂共享的负向前缀）**：
   > "Reflection:\nYou previously answered this question incorrectly.\nThen you reflected on the problem, your solution, and the correct answer.\nUse your self-reflection (below) to help you answer this question.\nAny information that you not allowed to see will be marked [REDACTED]."（原文大小写见文件）
3. **`source/2_reflect_on_solutions.py`（oracle 进入状态的那一行）**：
   > `user_prompt += f"Correct Answer: {correct_answer}\n"`
4. **`source/8_analyze_details.py`（配对检验与两条断言）**：
   > `assert len(baseline_table) == len(agent_table)` / `assert baseline_sum <= agent_sum` / `test_result = mcnemar(table, exact=False)`
5. **`source/8_analyze_details.py`（排除题集的注释）**：
   > `# Note: Don't use comprehensive 100 for analysis`

---

## 8. 读完后我自己的一句判断

- **最值得抄的**：**`retry` 臂那一行 `reflection = "No reflection information provided."`**。它是一个几乎零成本、却能把"反思有用"劈成"框架有用"和"内容有用"的实验设计。我们只要照抄这个模式，就能在自己的 DEV 集上一次性排掉坑 ⑦ 的干扰——**"结构化状态"到底是在传递信息，还是仅仅在改变提示词的形状。**
- **最容易骗我们的**：**这个仓库的"逐题明细 + 成本 + token"看起来像一份可直接对照的实验计划书**。它有 891 次运行、9 个模型、10,000 道题，**规模感压倒性地强于我们的 DEV 集**。但它的每一个数字背后都站着同一个 oracle（标准答案直接进提示词），而它的"改进"只在 4 选 1 的正确率上有定义。⇒ **我们很容易在讨论时不小心把它当成"自我反思应该长什么样"的模板，而它其实只是"答案怎么传给模型"的模板。** 抄它的**管线形状和账本结构**，不抄它的**效果预期**。
