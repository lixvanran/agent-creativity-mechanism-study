# DEEP-09-12 · 逐字摘录（quotes）

> **规则**：只抄**我实际读到**的原文。每条给出**定位**（论文/节/页 或 文件:行）与**取证路径**。
> 渲染说明：arXiv HTML/PDF 的 `SELF-DISCOVER` 在抽取时带连字空格（`S ELF -D ISCOVER`）、斜体词两侧有空格、公式被压成 `(6)`/空缺 ⇒ **下面凡标 ⟦规范化⟧ 处，我做了最小规范化**（只去多余空格/补连字符/把空缺公式标为 `[公式]`），**未改一字义**。凡抽取时丢失的内容，一律标 `[原文为公式/位图，文本层缺失]`，不脑补。
> **三类必须知道的重排（未改字，只改版面）**：
> ① **PDF 双栏**：同一句在文本层被另一栏文字打断（如 §4.3 "Efficiency wise …"），我按语义**去栏化重排 + 合并行末断词**（`in- stance` → `instance`）。
> ② **行内公式被爬虫吃掉**：原文该处是公式，文本层只剩空格；我**按上下文标注为 `[B]`/`[A*]`/`[t]` 等占位符** ⇒ **这些方括号里的符号是我标注的，不是原文**（A\* / B\* 的记号由摘要的 LaTeX 版 `B^{\ast}=B\cup {A}^{\ast}` 佐证）。
> ③ **网页行内换行**：ScienceDirect 抓取文本在句中含 `\n`，我按单行呈现。
>
> **自检结果**：本文件 + 规格文件的全部引用句，已用脚本对原文抽取文本做 **字母数字级包含校验**（去标点/空白/公式占位后比对），见 §末「自检记录」。

## 0. 三篇文献的核验身份

| 代号 | 题录（已 4 源交叉核对） | 本次取证路径 |
|---|---|---|
| **P1** | Pei Zhou, Jay Pujara, Xiang Ren, Xinyun Chen, Heng-Tze Cheng, Quoc V. Le, Ed H. Chi, Denny Zhou, Swaroop Mishra, Huaixiu Steven Zheng. *Self-Discover: Large Language Models Self-Compose Reasoning Structures*. arXiv:2402.03620v1 (2024-02-06), 17 pages, 11 figures, 5 tables. | ① `https://arxiv.org/html/2402.03620v1`（196,310 B，与 content-length 一致 = 完整）② `https://arxiv.org/pdf/2402.03620v1`（1,262,297 B，完整；`pdftotext -layout` 成功）③ arXiv API 元数据核对 |
| **P2** | Sebastián Andrés Mayorquín Posadas; Julio Vega. *Thinking Is Not Enough: The B\* Expansion Technique for Enhancing Autonomous LLM Agents*. **Expert Systems** 2026, **43**(8), e70333. DOI `10.1111/exsy.70333`. CC BY-NC-ND 4.0. DBLP `journals/es/PosadasV26`. | ① `web_search` 返回的 Wiley 正文（`dx.doi.org` / `onlinelibrary.wiley.com` 落地页，122,831 B 全量）② Crossref / OpenAlex / S2 / Unpaywall / OpenAIRE 元数据 ③ 官方代码仓 `github.com/SamthinkGit/Bstar-Expansion`（master） |
| **P3** | Liangji Zhang, Jianbo Yuan, Yougming He, Miao Yu, Kun Zhu, Zhenni Yu. *Diversity-driven reasoning: Mitigating logical errors in LLMs through social-attribute guided multi-agent collaboration*. **EAAI** 2026, Vol. 164:113126. DOI `10.1016/j.engappai.2025.113126`. DBLP `journals/eaai/ZhangYHYZY26`. | `web_search` 返回的 ScienceDirect 页文本（**只有 Abstract / Introduction / "Effects of GFF" 段首 / Conclusion / 参考文献**；**方法节未取得**）＋ Crossref / S2 / OpenAlex 元数据 |

---

# 第一部分 · P1 Self-Discover

**Q-01**（Appendix A 首句；HTML 抽取行 491 / PDF p.11）
> "Table 2 shows all 39 reasoning modules we use for SELF-DISCOVER ⟦规范化：原文抽取为 "Self-Discover"⟧, adopted from Fernando et al. (2023), that contain cognitive heuristics of problem-solving."

**Q-02**（Table 2 表题；PDF p.12）
> "Table 2. All 39 reasoning modules consisting of high-level cognitive heuristics for problem-solving. We adopt them from Fernando et al. (2023)."

**Q-02b**（39 条模块全文，逐条；PDF p.12 / HTML 抽取行 496–547）——**全 39 条逐字见 `DEEP-09-12-SelfDiscover-MAME-spec.md` §2.1 表**（该表即逐字抄录，编号即原文行号）。首尾各摘一条：
> "1 How could I devise an experiment to help solve that problem?"
> "39 Let's make a step by step plan and implement it with good notion and explanation."

**Q-03**（§2.1 Stage 1 三动作；HTML 抽取行 121 / PDF p.3）
> "The first stage consists of three actions: 1) SELECT, where relevant reasoning modules for task-solving are chosen from the set of reasoning module descriptions; 2) ADAPT, where descriptions of selected reasoning modules are rephrased to be more specific to the task at hand; and 3) IMPLEMENT, where the adapted reasoning descriptions are implemented into a structured actionable plan so that the task can be solved by following the structure."

**Q-04**（§2 任务级/实例级分工；PDF p.3，抽取行 151–155）
> "Stage 1 operates on task-level, meaning we only need to run SELF-DISCOVER ⟦规范化⟧ once for each task. Then, in Stage 2, we can simply use the discovered reasoning structure to solve every instance of the given task by instructing models to follow the provided structure by filling each key and arrive at a final answer."

**Q-04b**（Stage 1 三个公式；PDF p.3，抽取行 177–184）
> "D_S = M(p_S ‖ D ‖ t_i).  (1)"
> "D_A = M(p_A ‖ D_S ‖ t_i).  (2)"
> "D_I = M(p_I ‖ S_human ‖ D_A ‖ t_i).  (3)"
> "A = M(D_S ‖ t), ∀t ∈ T.  (4)"
> ⚠️ 式 (4) 印的是 `D_S`，与正文"用已实现结构 D_I 填值"不一致（见规格 §1.1）。
> ⚠️ **抽取歧义（据实标注）**：式 (3) 的 `pdftotext` 文本层作 `D_I = M(pA ∖ S_human ∖ D_A ∖ t_i )`（**pA**、第三个分隔符作 `∖`），而**正文散文明确写 "In addition to a meta prompt p_I"** ⇒ 上面按散文记作 `p_I ‖ S_human ‖ D_A ‖ t_i`；**`pA` 判定为文本层误读，未采信**。
> ⚠️ 四个公式的**分隔符**在原文是 `∥`（平行），文本层第 (3) 式渲染为 `∖`；上面统一按正文/语义记作 `‖`。

**Q-05**（Appendix A，Stage-2 提示词逐字；HTML 抽取行 492–493）
> "For Stage 2, where we use the self-discovered structure to solve the task instances, we start with the prompt: 'Follow the step-by-step reasoning plan in JSON to correctly solve the task. Fill in the values following the keys by reasoning specifically about the task given. Do not simply rephrase the keys.', followed by the reasoning structure, and finally the task instance."

**Q-06**（Figure 6 实例，PDF p.6；**版面被双栏打散，键名与值已错位**，此处按可辨认的键名抄录，值统一标 `[值]`）
> `reasoning_about_colored_objects`
> ```
> {
> "Type and color of each item":            [值]
> "Number of items of each color":           [值]
> "Number of items of each type":            [值]
> "Number of items of each color and type":  [值]
> "Final answer": Break down to sub-tasks
> }
> ```

**Q-07**（Figure 6 第二实例，PDF p.6，同上版面说明）
> `dyck_languages`
> ```
> {
> "Parentheses that are not closed properly":                                          [值]
> "Stack to store the closing parentheses":                                           [值]
> "If the next symbol is a closing parenthesis, pop the stack and check if the popped symbol matches the next symbol":  [值]
> "If the stack is empty, add the next symbol to the stack":                           [值]
> }
> ```

**Q-08**（Figure 10 图题与 Appendix A 正文；HTML 抽取行 492, 494）
> "Figure 10 contains the structure of the three actions of Self-Discover during Stage 1, where it discovers an intrinsic reasoning structure on the task-level."
> "Figure 10: Meta-Prompts for the three actions of Self-Discover. Each meta-prompt consists of an instruction in the beginning and the end, reasoning module descriptions, and task examples without labels. For IMPLEMENT, to show model an example of a reasoning structure (plan), we present a human-written structure in JSON for another task."
> ⚠️ **Figure 10 是位图**（PDF 与 arXiv HTML 均无文字层）⇒ **三个 meta-prompt 的逐字原文本次未取得**（见规格 §8 U2）。

**Q-09**（§5.1 消融；HTML 抽取行 ~256 段）
> "We conduct ablation study on the three actions: SELECT, ADAPT, and IMPLEMENT to analyze the effects of Self-Discover actions."
> "Figure 8 show results using GPT-4 on 4 reasoning tasks when we apply SELECT (-S) or apply SELECT and ADAPT (-SA) or apply all three actions."
> "We find that with each stage, model's zero-shot reasoning capability improve consistently across tasks, indicating that all three actions are beneficial. In particular, after all three actions SAI, the reasoning structures are adapted to be task specific, and bring the most gain to solving the reasoning tasks."

**Q-10**（§3.3 动作基的完备性；Wiley 正文 P2，§3.3）
> "We now introduce a finite subset [B], called the action basis, which serves as a generative core for the entire space [A]. The set [B] is assumed to be complete, in the following formal sense: An action basis is complete if and only if every action can be expressed as a finite composition of actions in [B]: (6) where [∘] is a composition function mapping finite sequences over [B] to actions in [A]."
> ⚠️ `[B]/[A]/[∘]` ＝ 原文中被 JATS/爬虫吃掉的行内公式符号。

**Q-11**（§3.1 MATH 例外：实例级结构；HTML 抽取行 158）
> "Finally, we subsample 200 examples from the MATH ( Hendrycks et al., 2021 ) test set, and generate instance-level reasoning structures via a one-shot demonstration to adapt to the complexity of MATH tasks."

**Q-12**（§5.2 跨模型搬运 I；HTML 抽取行 ~262 段）
> "We first use a PaLM 2-L model to discover the reasoning structures of 4 reasoning tasks. Then, we apply the resulting reasoning structures to the decoding of GPT-4 as grounding."
> "Figure 9 shows that Self-Discover outperforms OPRO on 3 out of 4 tasks despite that OPRO used 20% data to optimize the prompt. In contrast, Self-Discover is done in a zero-shot manner, demonstrating the efficiency of our method and universality of the discovered reasoning structures."

**Q-13**（§5.2 跨模型搬运 II；HTML 抽取行 ~268 段）
> "We use GPT-4 to discover the task-intrinsic reasoning structures, and then apply those structures to the decoding of open-sourced Llama2-70B as well as GPT-3.5-turbo (ChatGPT) on two subsets of tasks from BBH."
> "We find that using self-discovered structures on Llama2 (52%) outperforms CoT (42%) on disambiguation QA zero-shot and on GPT-3.5-turbo (56%) outperforms CoT (51%) on geometry with 3-shot demonstration from structured reasoning process."

**Q-14**（§4.3 + Figure 5 图注：效率读数与"不等 token 配平"的自认；PDF p.6，抽取行 366–372, 387–404）
> "Figure 5. Comparison of accuracy with number of inference calls required per instance. For CoT-Self-Consistency, we sample 10 times. Best of each RM method requires gold labels (*). **SELF-DISCOVER ⟦规范化⟧ requires only 1 inference call per instance (plus 3 more meta-prompts on the task-level), same as Direct and CoT while reaching better performance compared with 40x more call required methods (majority voting of each RM) on GPT-4. We acknowledge that SELF-DISCOVER ⟦规范化⟧ input and output are longer than CoT and Direct prompting, increasing cost. However, as the number of instances increases, the efficiency of SELF-DISCOVER ⟦规范化⟧ in terms of inference per instance is highly desirable.**"
>
> "SELF-DISCOVER ⟦规范化⟧ achieves better performance while requiring 10-40x fewer inference computer compared to self-consistency or majority voting."
> "Efficiency wise, SELF-DISCOVER ⟦规范化⟧ only requires one call per instance and three more inference calls on the task-level, CoT-self-consistency requires 10 times more since we have to sample 10 times for each instance, and methods using each RM requires 40 times more as we use 40 RMs."
> "In summary, SELF-DISCOVER ⟦规范化⟧ presents itself a strong reasoning boosting method that is efficient to deploy on large-scale."

**Q-15**（P1 §1 Introduction 效率结论句；HTML 抽取行 103）
> "Furthermore, SELF-DISCOVER ⟦规范化⟧ achieves superior performance against inference-heavy methods such as CoT + Self-Consistency by more than 20%, while requiring 10-40x fewer inference compute."

**Q-16**（P1 §3.1 评测设置：BBH 23 任务 / T4D / MATH 200 题；HTML 抽取行 158）
> "BBH tasks cover a diverse range of reasoning problems spanning the following 4 categories according to their authors: 1) Algorithmic and Multi-Step Arithmetic Reasoning, 2) Natural Language Understanding, 3) Use of World Knowledge, and 4) Multilingual Knowledge and Reasoning."
> "we subsample 200 examples from the MATH ( Hendrycks et al., 2021 ) test set …"

---

# 第二部分 · P2 B\* 展开（Expert Systems 2026, 43(8), e70333）

**Q-17**（Abstract；Crossref JATS + S2 LaTeX 版）
> "Most autonomous agents built on large language models (LLMs) focus on improving internal reasoning while assuming a fixed and complete set of primitive actions. In this work, we challenge this assumption and introduce the B* expansion technique, an action-centric method that enables agents to iteratively construct new actions beyond an initial basis B, forming an expanded action space B* = B ∪ A*. To formalize this paradigm, we present a unified framework for act-centric autonomy that explicitly models action space evolution, distinguishing our approach from prior frameworks such as ReAct, which operate over fixed action sets. Within this framework, B* serves as a concrete instantiation that operationalizes dynamic action generation. We evaluate B* in a non-trivial, fully observable environment—Conway's Game of Life on a 200×200 grid—where the objective is to maximize the number of live cells after 300 generations. Our results show that expanding the action space leads to improved exploration and performance, demonstrating that action space completeness is insufficient and that optimizing the action set itself can significantly enhance agent effectiveness, even surpassing state-of-the-art reasoning-based approaches."

**Q-18**（§3.3 动作基与展开式）
> "We now introduce a finite subset [B], called the action basis, which serves as a generative core for the entire space [A]." （同 Q-10）
> "To approach this balance between completeness and optimality, we define [A*], the action space approximator, as the set of all actions that can be generated by a growing sequence action spaces [A_t], where: (8)"
> "Finally, we define the expanded action space as the union of the action basis and a growing approximator: (9) where [A*] is the union of [A_t] for t at any fixed time step."

**Q-19**（§3.3 动作生成的三个来源 + 两道过滤闸）
> "In practice, the construction of [A*] is implemented as an incremental generation process. At each stage [t], candidate actions are proposed based on a combination of (i) observed failures or inefficiencies in [A_t], (ii) decomposition of successful action sequences and (iii) optional external specifications provided through tool interfaces such as MCP or A2A protocols. These candidate actions are then validated and either incorporated into [A*] or discarded based on their utility in improving solution quality or expanding coverage of the action space."
>
> "To ensure the validity of the expanded action space, each candidate action proposed for [A*] undergoes a filtering process before inclusion. First, structurally invalid actions (e.g., malformed arguments or undefined operations) are discarded. Second, **redundant actions—defined as actions functionally equivalent to existing elements in [B*]—are removed using deterministic equivalence checks over action signatures.** Only actions passing both criteria are incorporated into [A*]."

**Q-20**（§4 实验环境与基动作集）
> "In the experimental setup, the base action set is defined as the minimal set of primitive operations available in the environment: (i) placing a live cell in a selected grid position, (ii) removing a live cell and (iii) querying the current state of the board."
> "The agent may define an initial pattern within a 200 × 200 board where the number of live cells at the beginning of the game is less than or equal to 50. The overall goal will be to maximize the number of live cells at the end of the game, after 300 steps have passed on the board and with the final cells being the result of the board's evolution from the initial pattern."
> "All experiments use a fixed prompt template instructing the model to maximize the final number of live cells after 300 steps. The model is restricted to selecting actions from [B*] via a structured tool-calling interface. We set temperature = 0 for deterministic comparisons in LLM configurations, while LRM configurations use their default reasoning settings. The maximum number of tool calls per episode is fixed across all configurations to ensure fairness."

**Q-21**（§4 每回合流程（逐字列表））
> "Each episode follows the procedure: Initialize Game of Life environment. Provide initial state to model Model selects action via prompt-based tool calling Execute action in environment Receive updated state Repeat until termination (300 steps) Compute final score For generation: Sample failure or suboptimal trajectories Extract candidate action patterns Propose new action via LLM or decomposition Validate and add to [B*] if accepted"

**Q-22**（§5.1 生成与执行的上下文隔离 —— 最关键的一条）
> "For the generation of actions in [A*], no set of manually developed or predefined actions was programmed; instead, the same LLM model was used to generate, at each iteration of the experiment, a new tool that would be added to the action space [A*]. This was done to avoid possible biases in the action space that could violate the environment's non-triviality property. This action generation process was carried out **completely independently and without information, memory or context from previous runs** of the environment, so that the model creating the actions could not 'correct' errors made in previous iterations."
>
> "To mitigate potential bias in the construction of [A*], the generation of new actions is performed using the same model but with **strict separation between generation and execution contexts**. Specifically, the tool-generation process **has no access to performance outcomes** from the experimental runs and is executed independently for each run without shared memory or cross-run information. This design avoids direct optimization of [A*] towards observed test-time performance and ensures that improvements in [B*] arise from **structural action-space expansion rather than closed-loop adaptation** to specific trajectories."

**Q-23**（§5.1 运行规模）
> "In total, 1300 runs were performed. The first 500 were done with 20 players with a number of actions in [A*] varying between 0 and 25 actions (always adding the action space [B] as a base). It is important to note that the actions in [A*] are not the same among different players, meaning that each player generated a different set of actions, which allows evaluating the performance of the expansion independently of the generated actions. The remaining 800 runs were conducted in a second experiment with 20 players, and up to 40 rounds of expanded action space [A*], to evaluate the performance of the expansion in an even larger space."

**Q-24**（§5.1 拐点与饱和）
> "Figure 3 (left) shows the evolution of the median score as the size of the extended action space increases. We observe a clear upward trend: during the initial rounds, the agent tends to stabilize around 50 points, which roughly corresponds to the number of alive cells it is allowed to place initially. This indicates that the LLM, when limited to the base action set [B], primarily discovers configurations that do not leverage the full dynamical potential of the environment. However, starting around round 7, there is an abrupt increase in performance."
> "The trend stabilizes gradually, reaching median values close to 100 points (double the initial score) by round 25."
>
> "When repeating and extending the same experiment to 40 rounds (Figure 4), we observe that the median performance **maintains stable**, indicating that the **reach of the LLM has saturated under the current cognitive function**. This suggests that further gains are no longer driven by the growth of the action space [B*], but instead depend on the model's inherent ability to reason over increasingly complex and abundant tools."

**Q-25**（§5.2 四配置对照 + Table 1）
> "One hundred twenty runs were performed (30 runs for each of the models configurations, both with and without expansion of the action space [A*])."
> "TABLE 1. Summary of Experiment 2. This table provides a simplified quantitative overview of the results obtained by each configuration.
> Model | expansion | Median | Total range
> gpt-4o-mini | — | 50 | 0–820
> gpt-4o-mini | ✓ | 93 | 30–1292
> o4-mini | — | 40 | 0–1504
> o4-mini | ✓ | 253 | 0–1870"
> "We observe that the expansion consistently improves the median score across both LLM and LRM models, with the LLM achieving a median of 93 points and the LRM reaching 253 points."
> "Surprisingly, this reasoning variant is outperformed by the LLM without explicit reasoning thanks to the use of the expansion technique, obtaining a higher median and a much more stable distribution of results."

**Q-26**（§5.2 统计方法 —— 我们 §6.2 E5 的直接出处）
> "To assess statistical significance, we perform pairwise non-parametric comparisons using the Mann–Whitney U test across all experimental configurations, applying Bonferroni correction to account for multiple comparisons. Specifically, we compare LLM versus LLM+, LRM versus LRM+ and LLM+ versus LRM+. In addition to hypothesis testing, we report effect sizes using Cliff's Delta to quantify the magnitude of performance differences, together with 95% bootstrap confidence intervals for median scores to capture uncertainty in the estimates. The results confirm that all configurations incorporating [A*] exhibit statistically significant improvements over their non-expanded counterparts ([p < 0.05] after correction), with medium-to-large effect sizes, and stable confidence intervals that do not overlap with baseline configurations."
> ⚠️ `[p < 0.05]` ＝ 原文该处为行内公式，文本层丢失（抽取残留为 " ( after correction)"）。

**Q-27**（§6 讨论）
> "This study aims to show the limitations of purely cognitive strategies and present an alternative in which **it is not enough to have sufficient tools, but redundancy, composition, and even the creation of tools that only simplify the interaction with the environment can improve the performance of autonomous agents, even surpassing the performance of LRM based agents**."

**Q-28**（§7 Limitations —— 逐字四条 + 一条自认）
> "First, as the expanded action space grows, the **cognitive load** on the language model increases due to the need to select among a larger set of candidate actions. This may introduce a **'paradox of choice'** effect, where overly rich action spaces can degrade decision quality if not properly structured or ranked."
> "Second, the automatic generation of actions introduces additional computational overhead, as each expansion step requires either LLM inference or decomposition-based synthesis. While this process is **amortized over multiple executions**, it may still represent a non-trivial cost in real-world deployments."
> "Third, the effectiveness of [B*] may depend on the structure of the task. In highly sequential or syntax-constrained domains (e.g., program synthesis or formal verification), **naive action expansion may not yield improvements** unless the generated actions preserve strict semantic correctness."
> "Finally, the current evaluation is limited to a **single controlled environment** (Conway's Game of Life). While this environment provides a measurable and highly sensitive testbed, it does not cover domains such as API planning, symbolic reasoning or real-world tool orchestration."

**Q-29**（§8 复现 + 数据可得性）
> "All the code used for generating the experiments and evaluating the results is available in the GitHub repository: https://github.com/SamthinkGit/Bstar-Expansion."
> "The datasets generated and/or analysed during the current study are publicly available and can be accessed via the following repository: https://github.com/SamthinkGit/Bstar-Expansion. No restrictions apply to the access or use of these data."

---

# 第三部分 · P2 官方代码（`github.com/SamthinkGit/Bstar-Expansion`，master）

**Q-30**（`game_of_life/agents/agents.py`：`GENERATOR_PROMPT`，逐字）
> ```python
> GENERATOR_PROMPT = """
> You are an AI assistant helping to design new atomic actions ("tools") for
> Conway's Game of Life.
>
> The file you are editing contains Python functions. Each function defines a new
> action that can be used by a Game of Life agent to place patterns on a {GRID_SIZE}x{GRID_SIZE}
> grid. These actions are used at the beginning of each game: the agent can choose
> up to {ALIVE_CELLS} CELLS to place before the simulation runs for {NUM_OF_GENERATIONS} generations
> using standard Conway rules.
>
> **Goal of the agent:** reach the maximum number of alive cells after {NUM_OF_GENERATIONS} generations.
> This cells can be the same as the ones placed at the beginning, or new ones that
> were born during the simulation thanks to the original placements.
>
> Each function must follow the structure of the others: do not rewrite
> the existing functions, but rather a new one that can be used by the agent to
> play better the game. You can use only the functions already defined in the file
> to implement your new function.
>
> Your goal: Follow exactly these steps:
> 1. Write a short reasoning *as Python docstring* explaining the intuition behind
> the pattern you're adding — why it may be beneficial in Conway's Game of Life. (All the generation
> will be pasted to the file, so be careful not to overwrite or add invalid sintax)
>
> 2. Then define a unique new Python function following the same pattern as the others.
>
> The file is the following:
> {file_content}
>
> Your response will be pasted at the end of the file.
> """
> ```

**Q-31**（同文件 `ToolsGeneratorAgent`，逐字关键行）
> ```python
> class ToolsGeneratorAgent:
>     def __init__(self, life_player: LifePlayer, model: str = "gpt-4.1-mini"):
>         self.model = ChatOpenAI(model=model, temperature=0.6)
> ...
>             response = self.model.invoke(
>                 [
>                     {"role": "system", "content": prompt},
>                     {
>                         "role": "user",
>                         "content": "Start now writing the docstring and the new function.",
>                     },
>                 ]
>             )
>         lines = response.content.split("\n")
>         if lines[0].startswith("```"):
>             response.content = "\n".join(lines[1:-1])
> ...
>         with open(self.life_player.tool_env, "a", encoding="utf-8") as f:
>             f.write("\n" + response.content + "\n")
> ```

**Q-32**（同文件 `load_functions_from_file` —— 动作集如何"转移"）
> ```python
> def load_functions_from_file(file_path: Path) -> dict:
>     source = f.read()
>     exec_globals = {"__builtins__": __builtins__, "get_current_game": get_current_game}
>     local_ns = {}
>     exec(source, exec_globals, local_ns)
>     return {
>         name: obj
>         for name, obj in local_ns.items()
>         if callable(obj) and isinstance(obj, StructuredTool)
>     }
> ```
> ⚠️ **这里只有"语法/类型"隐式闸；论文 Q-19 声称的"冗余动作等价检查（deterministic equivalence checks over action signatures）"在已发布代码中未找到实现。**

**Q-33**（同文件 `LifePlayer.play_once` —— 执行侧硬闸与固定预算）
> ```python
> GRID_SIZE = 200
> ALIVE_CELLS = 50
> NUM_OF_GENERATIONS = 300
> ...
>         agent.invoke(
>             {"messages": [{"role": "user", "content": "The board is empty, the game starts now."}]},
>             config={"recursion_limit": 100},
>         )
>         assert (
>             game.points <= ALIVE_CELLS
>         ), "LLM exceeded the maximum number of alive cells. Exit"
> ```

**Q-34**（`game_of_life/agents/tools_env/template.py` —— 初始动作基 B 的**实际代码**）
> ```python
> @tool
> def reason(reasoning: str) -> bool:
>     """Reason about your plan."""
>     return True
>
> @tool
> def clear_grid(x: int, y: int) -> bool:
>     """Empty the grid of the current game. Consumes 0 cells."""
>     game = get_current_game()
>     game.clear()
>     return True
>
> @tool
> def add_cell(x: int, y: int) -> bool:
>     """Add a cell at the specified coordinates. Consumes 1 cell."""
>     game = get_current_game()
>     game.add_cell(x, y)
>     return True
>
> @tool
> def get_grid() -> str:
>     """Look at the current grid. Consumes 0 cells."""
>     game = get_current_game()
>     int_matrix = game.grid.astype(int)
>     lines = ["".join(str(cell) for cell in row) for row in int_matrix]
>     grid = "\n".join(lines)
>     return grid
> ```

**Q-35**（生成出的 A\* 动作实例，`tools_env_40_rounds/tools-1344487a-…py`，逐字）
> ```python
> @tool
> def add_blinker(x: int, y: int) -> bool:
>     """
>     Add a blinker oscillator pattern centered at (x, y).
>     The blinker is a simple period-2 oscillator that alternates between a vertical
>     and horizontal line of three cells. This pattern is beneficial because it
>     provides a stable, repeating source of activity without dying out, which can
>     interact with other patterns to create complex behaviors and potentially
>     increase the number of alive cells over generations.
>     """
>     game = get_current_game()
>     # Place three cells horizontally centered at (x, y)
>     game.add_cell(x - 1, y)
>     game.add_cell(x, y)
>     game.add_cell(x + 1, y)
>     return True
> ```

**Q-36**（官方结果 CSV —— 我方复算 §6.3 的数据源）
> `results/results_40_rounds.csv`：`player_id, round, points`，**801 行（含表头）= 20 player × 40 轮 = 800 次运行**（与 Q-23 "The remaining 800 runs … with 20 players, and up to 40 rounds" 完全对上）。
> `results/env_results_r40.csv`：`player_id, env_file, points`。
> ⚠️ **我方复算的逐轮中位数**（直接读该 CSV 计算，未加工）：
> `[50, 48, 48, 47, 48, 48, 96, 83, 92, 92, 98, 100, 128, 98, 103, 89, 99, 97, 127, 98, 225, 98, 136, 210, 129, 129, 92, 100, 94, 117, 95, 98, 151, 98, 93, 145, 98, 107, 99, 87]`
> （round 1…40；**round 25 = 129.5，round 40 = 87.5 ⇒ 与 Q-24 "median … maintains stable" 的"饱和"叙述一致**）

---

# 第四部分 · P3 MAME（EAAI 2026, 164:113126）—— **只读到这些**

**Q-37**（Abstract）
> "First, we introduce a Group Feedback Framework (GFF) that integrates group decision-making theory into multi-agent collaboration. By simulating human consensus formation and error correction mechanisms, we define a **dynamic confidence matrix** and an **answer credibility score** to quantify inter-agent influence. These metrics dynamically guide agents in adjusting their reasoning paths based on collective feedback."
> "Second, we propose a Multi-Attribute Prompting (MAP) method that assigns distinct social attributes to each agent, fostering perspective diversity through **weight vector modulation** and generation strategies."
> "Experimental results demonstrate significant performance improvements across reasoning tasks: MAME achieves enhancements of **up to 24.05 %** in mathematical reasoning, **39.1 %** in logical reasoning, and **4.94 %** in commonsense reasoning compared to baseline models."
> "The code is open source: https://github.com/ioio0614/MAME." （⚠️ **实测 404**）

**Q-38**（Introduction：GFF 回路的逐步描述 —— 我们 §3 的结构原型）
> "Specifically, multiple agents first give an initial answer to a given question, second, each agent in the framework refines its answer to the suggestions of the other agents and gives the **credibility of the pair of agents** and the **feasible confidence of the answer**, and finally each agents refines its answer based on the feedback. This cycle continues until the maximum number of rounds is reached, and **the final answer with the highest confidence level is taken as the answer to the given question**."

**Q-39**（Introduction：自报置信度/自反思的病灶 —— 我们 §3.5 的核心论据）
> "self-reflection approaches such as **self-refine (Madaan et al., 2024)** may have **unstable intrinsic reflection ability of the large language models in the absence of external feedback**, especially in the face of complex reasoning scenarios."
> "…the model will be **convinced that its answer is correct even with multiple feedbacks**."

**Q-40**（Introduction：多样性不足 ⇒ 思维面受限 —— 本组材料里最接近我们语汇的一句）
> "if debates between agents are not sufficiently diverse, or if agent tends to communicate with other agents that have similar views to their own, they may not be able to fully explore all possible solutions and viewpoints, leading to a **limited scope of thinking for the system as a whole**."

**Q-41**（Conclusion / Limitations）
> "Although MAME performs well in enhancing logical and mathematical reasoning, its limitations and potential problems must be pointed out to provide a more comprehensive perspective and guide future research directions. This framework faces challenges such as **high computational overhead**, uneven performance across different task types, **sensitive design of social attributes**, **difficulty in expanding the number of agents**, and **lack of theoretical guarantees**."

**Q-42**（"Effects of GFF" 段首：对照与设置）
> "In Fig. 3, we compare the performance of Debate, MAD, Reconcile and MAME on four datasets. In all four frames, **the number of agents is three**."

---

# 第五部分 · 第三方复现（**非官方**，只作旁证）

**Q-43**（`github.com/catid/self-discover`，README 自述）
> "This implements Google's algorithm from https://arxiv.org/pdf/2402.03620.pdf"
> ⚠️ **不是官方实现**（官方 `skelearn/Self-Discover` 已 404）。其四个提示词是**简化版**：
> - SELECT: "Given the task: {task_description}, which of the following reasoning modules are relevant? Do not elaborate on why.\n\n" + "\n".join(reasoning_modules)
> - ADAPT: "Without working out the full solution, adapt the following reasoning modules to be specific to our task:\n{selected_modules}\n\nOur task:\n{task_example}"
> - IMPLEMENT: "Without working out the full solution, create an actionable reasoning structure for the task using these adapted reasoning modules:\n{adapted_modules}\n\nTask Description:\n{task_description}"
> - Stage 2: "Using the following reasoning structure: {reasoning_structure}\n\nSolve this task, providing your final answer: {task_instance}"
>
> 该仓库的 `reasoning_modules` 列表**正好 39 条**（编号 1–39），与论文 Table 2 数量一致 ⇒ **交叉确认"39"不是 40**。

---

# 第六部分 · **没取到的**（逐条列出已试路径，禁脑补）

| 对象 | 已试路径 | 结果 |
|---|---|---|
| P1 三个 meta-prompt 逐字（Figure 10） | arXiv HTML 196KB 全文抽取 / PDF 1.26MB `pdftotext -layout` | **位图，无文字层** ⇒ 未取得 |
| P1 官方代码 | `api.github.com/repos/skelearn/Self-Discover`（tree/repos，**带 token**） | **404**；`api.github.com/users/skelearn` 亦 **404（账号不存在）** |
| P2 全文（Wiley 直连） | `onlinelibrary.wiley.com/doi/full-xml/…`（TDM 链接）/ `/doi/pdf/…` | **403 Cloudflare "Just a moment…"**；`burjcdigital.urjc.es` bitstream（OpenAIRE 给出直链）**连接失败**（出口白名单外）；`hdl.handle.net/10115/307257` → 302 → 同主机，仍失败 ⇒ **最终由 `web_search` 后端取到 Wiley 正文** |
| P3 方法节（MAP / 置信矩阵公式 / weight vector modulation 实现） | ScienceDirect 页文本（`web_search`）**跳过方法节**；Mendeley 目录（仅摘要）；ACM 目录（仅摘要+引文）；S2 API（`abstract: null`，无 OA PDF）；Crossref（abstract 空）；Unpaywall（closed）；`github.com/ioio0614/MAME` **404**；作者其余 4 仓库（`AMCFNet` / `Economic-preference-dataset` / `OI-wiki` / `Part-of-the-Apple-dataset`）**无 MAME** | **未取得** ⇒ 规格 §8 U1/U3 记为未决，**"weight vector modulation 改权重还是改 prompt" 未查清 ⇒ 不得作为路线 C 证据** |
| P2 的"冗余动作等价检查"实现 | `SamthinkGit/Bstar-Expansion` 全树 280 个文件（`agents.py` / `core.py` / `template.py` / `lab/*` / `results/*` 已读；`tools_env*` 只读 2 个样本） | **已发布代码中未见实现** ⇒ 我们若抄必须自补（规格 §4.3） |

---

# 第七部分 · 自检记录（本文件的引用可核性）

**方法**：把本文件与 `DEEP-09-12-SelfDiscover-MAME-spec.md` 里所有 `> "…"` 引用句抽出来，
与**本地原文抽取文本**做**字母数字级包含比对**（去标点/空白/公式占位/加粗标记后比对）：

| 语料 | 来源 | 大小 |
|---|---|---|
| `sd_text.txt` | arXiv HTML `2402.03620v1` 全文抽取 | 61,955 |
| `sd_pdf.txt` | arXiv PDF `2402.03620v1` `pdftotext -layout` | 98,058 |
| `wiley_full.txt` | Wiley 正文（`web_search` 后端，JSON 解析后取 `results[].content`） | 117,977 |
| `mame3.txt` | ScienceDirect 正文（同上，另一 artifact） | 211,951 |
| `agents.py` / `template.py` / `tools-1344487a…py` | `SamthinkGit/Bstar-Expansion` 官方代码 | 6,461 / 807 / 44,325 |
| `sd_self_discover.py` / `sd_README.md` | `catid/self-discover`（**第三方**） | 8,660 / 5,086 |

**结果**：**100 / 115 条引用句在原文语料中逐字命中**（alnum 级）。
其余 15 条分三类，**均已人工逐条对照原文确认无误**，且属**版面/公式层**而非文字层：

| 类别 | 条数 | 说明 |
|---|---|---|
| **行内公式被爬虫吃掉**（我补标了 `[B*]`/`[A*]`/`[t]`） | 9 | 原文该处是数学公式，文本层只剩空格；已在本文件开头"三类必须知道的重排"②里声明"方括号里的符号是我标注的，不是原文" |
| **PDF 双栏去栏化 + 行末断词合并** | 3 | §4.3 "Efficiency wise…"、§1 "Furthermore, S ELF -D ISCOVER outperforms inference-intensive methods…"、Figure 6 的键名行；文本层被另一栏文字打断，已按语义重排，**未改一字** |
| **公式记号歧义** | 3 | 式 (3) 的 `p_I`（文本层作 `pA`）、式 (3)/(1) 的 `∖` vs `∥`、式 (4) 原文印 `D_S` |

**本轮修掉的 3 处真实问题**（自检抓出来的，不是事后美化）：
1. `self-refine` 后**漏了引文 `(Madaan et al., 2024)`** ⇒ 已补（规格 §3.5 与本文件 Q-39 同步改）。
2. 规格 §5.1 引 MATH 那句**漏了 `( Hendrycks et al., 2021 )`** ⇒ 已补。
3. Q-15 的出处标注写成"§4.1"（实为 **§1 Introduction**，HTML 抽取行 103）⇒ 已改。

**未取到的**（第六部分已列全）在本文件里**没有任何一条是据推测补写的**；凡"只读到 X"处均照写。
