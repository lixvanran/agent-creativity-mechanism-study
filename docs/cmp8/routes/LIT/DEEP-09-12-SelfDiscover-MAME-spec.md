# DEEP-09-12 · Self-Discover + B\* 展开 → **可直接抄进代码的规格**

> **产出类型**：规格（不是摘要）。每条规则标注**出处等级**：
> `【原文】`＝论文/代码逐字可核 ｜ `【代码】`＝官方仓库实际实现 ｜ `【我方】`＝本文提出的设计（论文没有）｜ `【推断】`＝由原文事实推出，论文未直接写。
> **取证日期**：2026-10-21 ｜ **逐字摘录**见同目录 `DEEP-09-12-quotes.md`（编号 Q-01…Q-40 两篇通用）。
> **本文件不含任何实验结论**，只含可执行规格与判据。

---

## §0 引用与必须先纠正的 5 处

### 0.1 任务书把**两篇不同的论文**当成了一篇

| 代号 | 真实身份 | 正文获取 | 代码 |
|---|---|---|---|
| **P1** | **Self-Discover**: Zhou et al., *Self-Discover: Large Language Models Self-Compose Reasoning Structures*, **arXiv:2402.03620**（v1, 2024-02-06, 17p/11fig/5tab） | ✅ **全文读到**（arXiv LaTeXML HTML 196,310 B 完整 + PDF 1,262,297 B 完整） | 官方仓 `skelearn/Self-Discover` **已 404（账号不存在）**；只找到第三方复现 `catid/self-discover`（明确写"implements Google's algorithm"） |
| **P2** | **B\* 展开**: Posadas & Vega, *Thinking Is Not Enough: The B\* Expansion Technique for Enhancing Autonomous LLM Agents*, **Expert Systems 2026, 43(8), e70333**, DOI `10.1111/exsy.70333`, CC BY-NC-ND | ✅ **全文读到**（Wiley 页面 via `web_search` 后端，122,831 B） | ✅ **官方仓可读**：`github.com/SamthinkGit/Bstar-Expansion`（master, push 2025-07-09, 0★） |
| **P3** | **MAME**（= 任务书里"含 GFF / 逐对影响矩阵 / weight vector modulation / 置信度"的那篇）= Zhang et al., *Diversity-driven reasoning…*, **EAAI 2026, Vol.164:113126**, DOI `10.1016/j.engappai.2025.113126` | ⚠️ **只读到** Abstract / Introduction / "Effects of GFF" 段首 / Conclusion / 参考文献 51 条。**方法节（MAP、置信矩阵公式、weight vector modulation 实现）未读到** | ❌ 声称开源的 `github.com/ioio0614/MAME` **实测 404**；作者 `ioio0614` 4 个公开仓库里没有它 |

⇒ **任务书的 B 节把 P2（P3 的机制来源）和 P3 混成了一篇。** 本规格**分源**给出：P2 供给 §4（动作空间演化），P3 供给 §3（影响矩阵的**结构原型**），P1 供给 §1/§2/§5/§6。

### 0.2 5 处必须纠正（否则照抄会抄错）

| # | 任务书原文 | 事实 | 影响 |
|---|---|---|---|
| C1 | "MAME（SciDirect 选定的那篇，DOI 10.1111/exsy.70333）" | `exsy.70333` = **Expert Systems**（Wiley AI 刊），作者 Posadas & Vega（Rey Juan Carlos），**框架名是 `B\*`，正文里没有 "MAME" 三个字母** | 全部 B 节要拆成两篇 |
| C2 | "B\* 展开那篇里有 GFF 群体反馈融合矩阵" | **P2 里没有 GFF、没有 agent×agent 矩阵、没有置信度**。GFF 在 **P3**（EAAI）里 | §3 的来源必须写成 P3，且 P3 方法节未读到 |
| C3 | "weight vector modulation 到底是什么（改权重还是改 prompt）" | **未查清**。P3 方法节抓不到（ScienceDirect 爬虫文本跳过方法节）+ 代码 404。⇒ 按任务书自己的规则，**查清前不得算作路线 C 的证据** | §8 记为**未决**，禁止引用 |
| C4 | "Self-Discover 的 **40 个**原子模块（Appendix A）" | **是 39 个**。arXiv HTML 与 PDF 两处逐字均为 "all **39** reasoning modules"；表行号 1–39；第三方复现的模块表也正好 39 条 | §2 清单按 **39** 抄；多出的第 40 条是误记 |
| C5 | "P2 里有 'weight vector modulation' 机制" | P2 全文**无此词**。P2 的机制是**动作空间展开**（B → B∪A\*） | §4 用 P2 自己的机制，不用 P3 的词 |

### 0.3 取证等级总表（读了什么 / 没读什么）

| 对象 | 读到了 | 没读到 |
|---|---|---|
| **P1 Self-Discover** | Abstract、§2 两阶段全文（含公式 1–4）、§3 设置、§4.1–4.4（**含 Figure 5 效率图与图注逐字**）、§5.1 消融、§5.2 跨模型搬运、Appendix A（**39 模块表逐条** + Stage-2 提示词逐字）、Appendix B/C/D/E | **Figure 10 三个 meta-prompt 的原文**（该图是位图，PDF/HTML 均无文字层）⇒ §1.3 的 meta-prompt **只有结构 + 第三方复现版**，逐字原文**未取得** |
| **P2 B\*** | §1–§8 **全文**（含 Table 1 四个配置、统计检验方法、§7 局限、§8 复现）、官方代码 `agents.py` / `core.py` / `template.py` / `lab/*.py` / `results/*.csv`、**1300 行的结果 CSV** | 未读：`logs/` 下的原始轨迹（20 MB 级）、`tools_env_mini` 的全部 18 个文件 |
| **P3 MAME** | Abstract、Introduction（含三段方法总述与三条贡献）、"Effects of GFF" 段首、Conclusion、CRediT、Index Terms、参考文献 51 条 | **方法节全部**（MAP 如何分配属性、置信矩阵的维度/取值域/聚合、credibility score 公式、weight vector modulation 实现、最大轮次数、四个数据集名、完整结果矩阵、消融表、成本数字） |

---

## §1 显式步骤结构 schema

### 1.1 原文的做法（可直接对照的公式与逐字提示词）

**两阶段**【原文 Q-03, Q-04】：

```
Stage 1（任务级，3 次 meta-prompt 调用）:
  SELECT   : D_S = M(p_S ‖ D ‖ t_i)                      (1)
  ADAPT    : D_A = M(p_A ‖ D_S ‖ t_i)                     (2)
  IMPLEMENT: D_I = M(p_I ‖ S_human ‖ D_A ‖ t_i)           (3)
Stage 2（实例级，每实例 1 次调用）:
  A = M(D_S ‖ t),  ∀t ∈ T                                  (4)
```

⚠️ 论文 eq.(4) 印的是 `D_S`，但正文语义是"用**已实现的结构** `D_I` 填值"（Q-04 原文："follow the provided structure by filling each key"）⇒ **论文公式与正文有一处不一致，按正文/图示为准**。

**Stage-2 提示词（逐字）**【原文 Q-05】：
> "Follow the step-by-step reasoning plan in JSON to correctly solve the task. Fill in the values following the keys by reasoning specifically about the task given. Do not simply rephrase the keys."

**JSON 的真实形态**（Figure 6 实例，逐字）【原文 Q-06】：
```json
{
  "Type and color of each item": "<填好的值>",
  "Number of items of each color": "<填好的值>",
  "Number of items of each type": "<填好的值>",
  "Number of items of each color and type": "<填好的值>",
  "Final answer": "Break down to sub-tasks"
}
```
另一个实例（`dyck_languages`）【原文 Q-07】：
```json
{
  "Parentheses that are not closed properly": "<值>",
  "Stack to store the closing parentheses": "<值>",
  "If the next symbol is a closing parenthesis, pop the stack and check if the popped symbol matches the next symbol": "<值>",
  "If the stack is empty, add the next symbol to the stack": "<值>"
}
```

**⇒ 抽取出的 schema 事实**（这几条是可抄的硬约束）：

| 事实 | 说明 |
|---|---|
| **键 = 自然语言问句/目标串** | 不是 slug、不是枚举 ID。键本身**就是这一步要产出什么**的规格（"Parentheses that are not closed properly"） |
| **值 = 该步的产出** | 由模型按序填充；最后一个键通常是 `"Final answer"` |
| **顺序 = 执行顺序** | 依赖 JSON 对象插入序；"step-by-step" 是靠序而非靠 ID |
| **结构是"扁平的"** | 没有嵌套、没有 `depends_on`、没有每步的元数据 ⇒ **我们的 schema 是它的超集** |
| **每步不绑定依据** | Self-Discover 的键值对**不带来源标注**；这正是我们要加的东西 |

### 1.2 我们的 `step_structure` schema（可直接写进 `config/` 与拓扑表示）

```jsonc
{
  "schema_version": "step-structure/1.0",
  "task_id": "T-xxx",
  "layer": "task_level",                  // task_level | instance_level
  "produced_by": {                        // 谁生成的、什么时候生成的（§5 用）
    "model": "<model_id>",
    "stage": "select|adapt|implement|human",
    "calls": 3,
    "created_at": "<iso8601>"
  },

  // ① 选中的认知位置（对应 D_S）—— mid 必须指向 §2 池子里的稳定 ID
  "selected_modules": [
    { "mid": 10, "name": "Critical Thinking", "text": "<池中原文>" }
  ],

  // ② 任务特化后的描述（对应 D_A）
  "adapted_modules": [
    { "mid": 10, "task_specific_text": "<改写后的描述>" }
  ],

  // ③ 编译出的步骤结构（对应 D_I）—— 执行顺序 = 数组顺序
  "steps": [
    {
      "key": "<自然语言问句/目标串，同 P1>",
      "instruction": "<这一步怎么做>",
      "source_modules": [10],              // ★我方增项：这一步由哪个认知位置生成
      "bound_evidence": ["E-012", "E-037"],// ★我方增项：这一步的依据 ID（可核验集合）
      "output_type": "list|number|string|bool|table",
      "depends_on": [],                    // ★我方增项：前序 key（显式，不靠位置）
      "verify": {                          // ★我方增项：这一步怎么验
        "by": "evidence_match|deterministic|self_check",
        "rule": "<可执行判据；缺依据 ⇒ 不可为承重项>"
      }
    }
  ],
  "final_step_key": "Final answer",

  // ④ 搬运与版本（我方增项：拓扑必须可跨模型搬运 ⇒ 显式记录）
  "portable": { "model_agnostic": true, "min_model_tier": "<tier>" },
  "provenance": { "parent_structure_id": null, "round": 0 }
}
```

**三条硬约束**（写进 `spec.yaml` 的校验）：
1. `steps[].bound_evidence` **为空 ⇒ 该步不得计入 VD_net**（无依据的步骤不是维度）。
2. `steps[].key` 必须**逐字唯一**（P1 靠模型生成，可能撞名 ⇒ 我们必须查重）。
3. `steps[].depends_on` 必须构成 **DAG**（P1 只有隐式顺序；我们显式化 ⇒ 便于做"换值 ⇒ 痕迹同步变"的置换检验）。

### 1.3 meta-prompt 的结构（**逐字原文未取得**，只给可核结构）

论文 Appendix A 的 Figure 10 是**位图**（PDF 与 arXiv HTML 均无文字层）⇒ **三个 meta-prompt 的逐字原文本次未取得**。
已核实的**结构**【原文 Q-08】：
> "Each meta-prompt consists of an instruction in the beginning and the end, reasoning module descriptions, and task examples without labels. For IMPLEMENT, to show model an example of a reasoning structure (plan), we present a human-written structure in JSON for another task."

⇒ **可抄的 meta-prompt 骨架**（照此写即可，槽位是确定的）：
```
SELECT  meta-prompt := [前置指令] + D(全部 39 条模块) + t_i(无标签样例) + [后置指令]
ADAPT   meta-prompt := [前置指令] + D_S(选中子集) + t_i + [后置指令]
IMPLEMENT meta-prompt := [前置指令] + S_human(他人写的 JSON 示例) + D_A + t_i + [后置指令]
```
第三方复现（`catid/self-discover`，**非官方**）给出的是**简化版**语义，可当"意思已对齐"的旁证，不能当原文引用：
- SELECT: "Given the task: {task_description}, which of the following reasoning modules are relevant? Do not elaborate on why."
- ADAPT: "Without working out the full solution, adapt the following reasoning modules to be specific to our task:\n{selected_modules}\n\nOur task:\n{task_example}"
- IMPLEMENT: "Without working out the full solution, create an actionable reasoning structure for the task using these adapted reasoning modules:\n{adapted_modules}\n\nTask Description:\n{task_description}"

⚠️ 注意：官方仓 `skelearn/Self-Discover` **已 404**（GitHub 用户 `skelearn` 不存在）⇒ 若我们要把 meta-prompt 当资产，**必须自己重写并冻结**（把 P1 的 Figure 10 从 PDF 里做 OCR/人工誊写，是一次性的取证任务，值得排期）。

---

## §2 认知位置池

### 2.1 P1 的 39 个原子模块（**逐条抄**，表序 = 原文表序）

> 原文表题逐字【Q-02】："Table 2. All **39** reasoning modules consisting of high-level cognitive heuristics for problem-solving. We adopt them from Fernando et al. (2023)."
> 原文正文逐字【Q-01】："Table 2 shows all **39** reasoning modules we use for SELF-DISCOVER, adopted from Fernando et al. (2023), that contain cognitive heuristics of problem-solving."

| mid | 原文（逐字） | 我方最贴近的承载面 | 映射强度 |
|---|---|---|---|
| 1 | How could I devise an experiment to help solve that problem? | — | 无 |
| 2 | Make a list of ideas for solving this problem, and apply them one by one to the problem to see if any progress can be made. | —（多候选→逐个试） | 弱 |
| 3 | How could I measure progress on this problem? | FA3 数量与门槛 | 强 |
| 4 | How can I simplify the problem so that it is easier to solve? | —（简化） | 无 |
| 5 | What are the key assumptions underlying this problem? | FA2 依据与约束 | 强 |
| 6 | What are the potential risks and drawbacks of each solution? | FA5 例外与失效条件 | 强 |
| 7 | What are the alternative perspectives or viewpoints on this problem? | FA4 情形分支与差异 | 强 |
| 8 | What are the long-term implications of this problem and its solutions? | — | 无 |
| 9 | How can I break down this problem into smaller, more manageable parts? | —（分解） | 无 |
| 10 | Critical Thinking: This style involves analyzing the problem from different perspectives, questioning assumptions, and evaluating the evidence or information available. It focuses on logical reasoning, evidence-based decision-making, and identifying potential biases or flaws in thinking. | FA2 | 中 |
| 11 | Try creative thinking, generate innovative and out-of-the-box ideas to solve the problem. Explore unconventional solutions, thinking beyond traditional boundaries, and encouraging imagination and originality. | FA4 | 弱 |
| 12 | Seek input and collaboration from others to solve the problem. Emphasize teamwork, open communication, and leveraging the diverse perspectives and expertise of a group to come up with effective solutions. | —（协作） | 无 |
| 13 | Use systems thinking: Consider the problem as part of a larger system and understanding the interconnectedness of various elements. Focuses on identifying the underlying causes, feedback loops, and interdependencies that influence the problem, and developing holistic solutions that address the system as a whole. | FA1 | 弱 |
| 14 | Use Risk Analysis: Evaluate potential risks, uncertainties, and tradeoffs associated with different solutions or approaches to a problem. Emphasizes assessing the potential consequences and likelihood of success or failure, and making informed decisions based on a balanced analysis of risks and benefits. | FA5 | 强 |
| 15 | Use Reflective Thinking: Step back from the problem, take the time for introspection and self-reflection. Examine personal biases, assumptions, and mental models that may influence problem-solving, and being open to learning from past experiences to improve future approaches. | FA6 | 弱 |
| 16 | What is the core issue or problem that needs to be addressed? | FA1 | 强 |
| 17 | What are the underlying causes or factors contributing to the problem? | FA2 | 中 |
| 18 | Are there any potential solutions or strategies that have been tried before? If yes, what were the outcomes and lessons learned? | FA2 | 强 |
| 19 | What are the potential obstacles or challenges that might arise in solving this problem? | FA5 | 强 |
| 20 | Are there any relevant data or information that can provide insights into the problem? If yes, what data sources are available, and how can they be analyzed? | FA2 | 中 |
| 21 | Are there any stakeholders or individuals who are directly affected by the problem? What are their perspectives and needs? | FA1 | 中 |
| 22 | What resources (financial, human, technological, etc.) are needed to tackle the problem effectively? | FA6 | 弱 |
| 23 | How can progress or success in solving this problem be measured or evaluated? | FA3 | 强 |
| 24 | What indicators or metrics can be used? | FA3 | 强 |
| 25 | Is the problem a technical or practical one that requires a specific expertise or skill set? Or is it more of a conceptual or theoretical problem? | FA1 | 强 |
| 26 | Does the problem involve a physical constraint, such as limited resources, infrastructure, or space? | FA1 | 中 |
| 27 | Is the problem related to human behavior, such as a social, cultural, or psychological issue? | FA1 | 强 |
| 28 | Does the problem involve decision-making or planning, where choices need to be made under uncertainty or with competing objectives? | FA1 | 强 |
| 29 | Is the problem an analytical one that requires data analysis, modeling, or optimization techniques? | FA1 | 强 |
| 30 | Is the problem a design challenge that requires creative solutions and innovation? | FA1 | 强 |
| 31 | Does the problem require addressing systemic or structural issues rather than just individual instances? | FA1 | 强 |
| 32 | Is the problem time-sensitive or urgent, requiring immediate attention and action? | FA1 | 强 |
| 33 | What kinds of solution typically are produced for this kind of problem specification? | FA4 | 强 |
| 34 | Given the problem specification and the current best solution, have a guess about other possible solutions. | FA4 | 强 |
| 35 | Let's imagine the current best solution is totally wrong, what other ways are there to think about the problem specification? | FA4 | 强 |
| 36 | What is the best way to modify this current best solution, given what you know about these kinds of problem specification? | FA4 | 强 |
| 37 | Ignoring the current best solution, create an entirely new solution to the problem. | FA4 | 强 |
| 38 | Let's think step by step. | —（执行方式） | 无 |
| 39 | Let's make a step by step plan and implement it with good notion and explanation. | —（执行方式） | 无 |

**覆盖统计**（我方算的，论文无此对照）：FA1←10 条 ｜ FA2←5 条 ｜ FA3←4 条 ｜ FA4←7 条 ｜ FA5←3 条 ｜ FA6←**2 条且都只是"弱"**（M15/M22）｜ **无对应 11 条**（M1,2,4,8,9,12,38,39 等）。

### 2.2 三条**可操作**结论（这才是这一节的价值）

1. **层不同，不可直接替换。** 我们的 6 承载面是**程序面**（"先做什么程序"，来自协议 C1/C2/C3），39 模块是**提问面**（"先问什么"）。
   ⇒ 正确用法不是"把 39 模块当新目录"，而是：**把 39 模块当作"目录 + 每题选子集 + 编译成显式结构"这套表示法的已发表先例**（P1 的三段式：SELECT → ADAPT → IMPLEMENT）。
2. **"目录"这个对象本身在 P1 里是被检验的假设，不是既成事实。** P1 做了三段消融（`-S` / `-SA` / `SAI`）【原文 Q-09】：
   > "We find that with each stage, model's zero-shot reasoning capability improve consistently across tasks, indicating that all three actions are beneficial."
   ⚠️ 注意：P1 消融的是**三个动作**（SELECT/ADAPT/IMPLEMENT），**不是**"模块池本身 vs 无模块池"。⇒ **"换一整套目录会不会更好/更差"这个问题，P1 也没回答** ⇒ 对我们而言这是一个**现成的、空白的关键对照**（见 §2.3 第 3 条）。
3. **⇒ 建议新增一个消融臂（低成本、直接可跑）**：`FACETS_39` 臂 —— 把我们 6 承载面目录换成 P1 的 39 模块目录（其余协议、模型、预算、题目全同），同跑 VD_net。
   目的不是"证明 39 更好"，而是**把"目录是先验"这件事变成被检验的变量**（现在它在我们这里是未检验的常量）。这也是我们"目录本身是待检验假设"纪律的兑现。
   ⚠️ 纪律沿用：两套目录都必须满足"不含评价口径词 / 不含题目实体 / 不含答案暗示"（`leakage.py` 零命中 + `redline_check.json` 复核）。

### 2.3 与 6 承载面的对照结论（可写进报告）

- **我们比 P1 多的**：FA6（缺口与不确定）在 39 模块里**只有弱对应** ⇒ 我们的"哪里不确定"是 P1 目录里没有的一格（对应协议 C3"结论空间外不算维度，但'哪里不确定'常是承重项"）。
- **P1 比我们多的**：多候选→逐个试（2）、分解（9）、协作（12）、系统视角（13）、长期影响（8）、实验设计（1）⇒ 这些是我们 6 面**没有的认知位置**，若要加，按我们既有纪律走"目录扩展 + 消融"。
- **两边都不要收进目录的**：38/39（"逐步思考"）是**执行方式**，不是认知位置 ⇒ 我们的拓扑本身承担"逐步"，不占目录槽位。

---

## §3 agent × 依据 影响矩阵 schema（我们要直接实现的那张表）

### 3.1 P3（MAME / GFF）能给我们的**结构原型**（只有这些可核）

【原文 Q-20, Q-21, Q-22, Q-23】
> "we define a **dynamic confidence matrix** and an **answer credibility score** to quantify inter-agent influence. These metrics dynamically guide agents in adjusting their reasoning paths based on collective feedback."

> "each agent in the framework refines its answer to the suggestions of the other agents and gives the **credibility of the pair of agents** and the **feasible confidence of the answer**"

> "The agent in the framework have a **confidence score for other agents and reasoning answers**"

> "the final answer with the **highest confidence level** is taken as the answer to the given question."

⇒ 可抄的**结构**：
- 矩阵是 **agent × agent**（"pair of agents" 的 credibility）＋ 一列 **agent × answer**（answer credibility score）；
- 矩阵**每轮更新**（dynamic）；
- 矩阵**回灌进下一轮 prompt**（"adjusting their reasoning paths based on collective feedback"）；
- **终局仲裁 = 置信度最高者**（← 这一条是**我们要删掉的**）。

⚠️ **未读到**：矩阵维度、取值域、聚合规则、"回灌 prompt"的**具体格式**、最大轮数。⇒ **我们不能声称"复现 GFF"**，只能说"借 GFF 的表形态，把单元格换掉"。

### 3.2 我们的替换（这一节是本文件的核心可抄件）

**替换原则**（任务书定调，我方实现化）：**单元格 = "这条反馈实际引用的依据 ID"**，取代"agent 自报置信度"。

| | P3 / GFF | **我们** |
|---|---|---|
| 行 | agent | **agent（= 一次回答的作者/一条主张）** |
| 列 | agent（+ answer） | **依据 ID（依据包里的原子事实）** |
| 单元格 | 自报 credibility / confidence（连续、主观） | **引用的依据 ID 集合（离散、可核验）** |
| 终局仲裁 | 置信度最高者 | **依据被引用且改变了结论者（承重）** |
| 依赖 | embedding/措辞相似度 | **无**：纯 ID 引用 + 置换检验** |

### 3.3 schema（可直接实现）

```jsonc
{
  "schema_version": "evidence-citation-matrix/1.0",
  "task_id": "T-xxx", "rep": 0, "round": 2,
  "agents": ["A1", "A2", "A3"],           // 行
  "evidence": ["E-001", "E-002", "..."],  // 列（依据包原子事实 ID，来自 user4_q*.json）

  "cells": {
    "A1|E-012": {
      "cited": true,                     // 二值
      "count": 1,                        // 引用次数
      "quote": "逐字片段",                // 可程序核对
      "span": [120, 188],                // 在该 agent 文本中的字符区间
      "effect": {                        // ★ 置换检验用（决定"承重"）
        "changed": true,                 // 换掉该依据的值 ⇒ 结论是否变
        "before_hash": "sha256:...",      // 结论段的哈希
        "after_hash":  "sha256:..."
      }
    }
  },

  // 派生量（纯确定性计算，零 API）
  "derived": {
    "cited_pairs":      [["A1","E-012"], ...],
    "load_bearing":     [["A1","E-012"]],   // cited && effect.changed
    "cited_but_inert":  [["A2","E-030"]],   // 被引用但换值不改结论 ⇒ 不承重
    "unreferenced_evidence": ["E-044"],     // 依据包里没人用 ⇒ 该依据不承重
    "per_agent_cited_count": { "A1": 6, "A2": 3 },
    "column_budget_violations": ["A1"]      // 超过 per_agent_cite_budget 的行
  },

  // 配置（预注册，写进 spec.yaml）
  "config": {
    "per_agent_cite_budget": 6,            // 防"选择悖论"（见 §4.4）
    "effect_test": "swap_value",           // 置换检验方式
    "min_quote_len": 8
  }
}
```

### 3.4 派生量 → 主判据的接线（与既有 `analysis_net_gain.md` 对齐）

既有口径【本项目既有文件】：**净维度增益 = 新增（工作流有、基线无）− 丢失（基线有、工作流无）**，基线 = 同题同重复的 A1 直调，事实来自 4 份依据包的 64 条原子事实。

⇒ 把矩阵接进去：
1. **"维度"的身份 = 依据 ID**（不是文本、不是 embedding）⇒ 新增/丢失 = **依据 ID 集合的差**。
2. **承重维度 ⊆ 被引用维度**：`load_bearing` 才是承重集合；`cited_but_inert` 单独报（"引用了但没承重" ⇒ 引用是**表态**不是**承重**）。
3. **必须同时报分母与绝对条数**（沿用 `batch-U1/PREREG.md` 第 4 条）。
4. **反向断言（负例）**：注入一条违规内容 ⇒ 矩阵必须出现对应 `E-xxx` 的 `cited=true` 且 `effect.changed=true` ⇒ **"断言通过"≠"断言有效"** 这条纪律要落到矩阵上。

### 3.5 为什么**自报置信度**这个回路在我们项目里不能用（这节要写进报告）

P3 自己在 Introduction 里批评了同族方法，然后在自己身上复现了同一个病【原文 Q-24, Q-25】：
> "self-reflection approaches such as **self-refine (Madaan et al., 2024)** may have **unstable intrinsic reflection ability of the large language models in the absence of external feedback**, especially in the face of complex reasoning scenarios."

> "…the model will be convinced that its answer is correct **even with multiple feedbacks**."

而 P3 的终局仲裁是"**confidence 最高者**"——**没有外部反馈**。

⇒ 我们项目里这条更致命：**我们的判官与被测同源**（同一模型族做判官与被测）⇒ 自报置信度与判官判据**共享同一套先验与偏见** ⇒ 它不是独立信号，是同源信号的相关副本。
⇒ **结论：GFF 的"表形态"可抄，"单元格内容"不可抄。** 自报置信度在 P3 内部就已经是它自己批评的病；在我们这里再加一层同源污染。

---

## §4 动作空间演化（B\*）的规格

### 4.1 形式层（可直接抄的最小形式化）

【原文 Q-10 ~ Q-14】
- 动作空间 `A`（无限集）、解空间 `S = A*`（**不可变、顺序敏感**的序列）、`S(p)` = 满足 p 的非空序列集合。
- **动作基 B**：有限子集，且"**完备**"——当且仅当每个动作都可写成 B 中动作的有限组合（式 6）。
  > "An action basis is complete if and only if every action can be expressed as a finite composition of actions in B."
- **认知函数**：`f_M : P × A → S`，M 是不透明固定模型；输出落在**可达集** `S_A`（reachability）内。
- **动作空间逼近子** `A*` = 逐轮动作空间 `A_t` 的并（式 8）；**展开动作空间** `B* = B ∪ A*`（式 9）。
- 三条能力声明：`B*` ⇒ 保证可解（B 完备）+ 提升解质量（逼近最优）+ **无需改模型即可增量扩展**。

### 4.2 动作构造算子（**由谁 / 用什么提示 / 产出什么** —— 逐字）

**产出物形态**：**一个 Python 函数**（带 `@tool` 装饰器 ⇒ LangChain `StructuredTool`），追加到该 player 的 `tools-<uuid>.py` 文件末尾。

**生成提示词（官方代码逐字）**【代码 Q-30】：
> "You are an AI assistant helping to design new atomic actions ("tools") for Conway's Game of Life.
> The file you are editing contains Python functions. Each function defines a new action that can be used by a Game of Life agent to place patterns on a {GRID_SIZE}x{GRID_SIZE} grid. …
> Each function must follow the structure of the others: do not rewrite the existing functions, but rather a new one that can be used by the agent to play better the game. **You can use only the functions already defined in the file to implement your new function.**
> Your goal: Follow exactly these steps:
> 1. Write a short reasoning *as Python docstring* explaining the intuition behind the pattern you're adding — why it may be beneficial in Conway's Game of Life. …
> 2. Then define a unique new Python function following the same pattern as the others.
> The file is the following: {file_content}
> Your response will be pasted at the end of the file."

**调用契约**【代码 Q-31】：
- 模型：`gpt-4.1-mini`，**temperature = 0.6**（注意：与论文"temperature = 0"是**两处**，0 只用于执行侧）
- system = 上述提示词（内含当前工具文件全文）；user = `"Start now writing the docstring and the new function."`
- 响应：剥掉 ```` ``` ```` 围栏 → **原样追加到文件末尾**
- 执行侧：`load_functions_from_file()` 用 `exec()` 跑文件，收集**所有 `StructuredTool` 实例** ⇒ **新动作立刻进入可调用集合**（这就是"转移"）

**关键设计（论文侧逐字）**【原文 Q-15, Q-16】：
> "the same LLM model was used to generate, at each iteration of the experiment, a new tool that would be added to the action space A*. This was done to avoid possible biases in the action space that could violate the environment's non-triviality property. This action generation process was carried out **completely independently and without information, memory or context from previous runs** of the environment, so that the model creating the actions could not 'correct' errors made in previous iterations."

> "the tool-generation process **has no access to performance outcomes** from the experimental runs and is executed independently for each run without shared memory or cross-run information. This design avoids direct optimization of A* towards observed test-time performance and ensures that improvements in B* arise from **structural action-space expansion rather than closed-loop adaptation** to specific trajectories."

### 4.3 论文声称的**两道过滤闸** vs 代码里**实际实现**（⚠️ 差距，必须知道）

论文逐字【原文 Q-17】：
> "First, structurally invalid actions (e.g., malformed arguments or undefined operations) are discarded. Second, **redundant actions—defined as actions functionally equivalent to existing elements in B*—are removed using deterministic equivalence checks over action signatures.** Only actions passing both criteria are incorporated into A*."

代码里实际有的【代码 Q-32】：
- 闸 ① 的**隐式版本**：`exec()` 失败会抛错；`load_functions_from_file` 只收 `StructuredTool` ⇒ 语法错/签名错的函数**根本进不了动作集**。
- 闸 ②（**冗余/等价检查**）：**在已发布代码里找不到实现**（没有 signature 比较、没有去重表）。
- 另有**执行侧硬闸**：`assert game.points <= ALIVE_CELLS`（放超 50 格 ⇒ 直接崩）。

⇒ **我们若抄 B\* 的 op 演化，必须自己补闸 ②**，否则 op 集会被重复 op 撑大（而 B\* 的效果恰恰依赖 op 集"变宽"而不是"变重复"）。

### 4.4 我们要怎么让 **op 集本身可长**（我们版规格）

把 B\* 的三件套映射到我们的 op 集：

| B\* | 我们的对应物 | 说明 |
|---|---|---|
| 动作基 `B` | **固定 op 基**（当前拓扑里人定的算子集合：分解/取依据/否决/合成/终局…） | 必须**完备**：任何拓扑步都能用 B 组合出来 |
| `A*` | **候选新 op**（复合算子） | 每个新 op 必须是 B 中 op 的组合（否则破坏完备性） |
| `B* = B ∪ A*` | **演化后的 op 集** | 增量加入，不重写 B |
| 动作构造算子（§4.2） | **proposer**（路线 B/C 已有 `proposer.py`） | 提示词改写成"设计新的 op，输出 JSON/函数，只能用已存在的 op 实现" |
| 生成/执行**上下文隔离** | **硬规则** | proposer **看不到**评测结果、看不到上一次运行记忆 ⇒ 防"朝测试指标闭环优化" |
| 完备性 | **不变式断言** | 新 op 只能用已存在 op 组合（可静态检查） |

**op 集演化的三条判据（预注册）**：
1. **增量有效性**：新 op 必须**至少在一道题上**改变 VD_net（否则是冗余 ⇒ 丢弃，与 §4.3 闸 ② 对齐）。
2. **饱和点**：连续 K 轮新增 op 的 |ΔVD_net| < δ ⇒ 停止扩张（见下条警告）。
3. **选择预算**：每题可见的 op 数上限 `M`（防止"选择悖论"）。

### 4.5 B\* 给我们的三条**警告**（原文 §7 局限，逐字）——这三条直接约束我们的 op 集路线

【原文 Q-18】
> "First, as the expanded action space grows, the **cognitive load** on the language model increases due to the need to select among a larger set of candidate actions. This may introduce a **'paradox of choice'** effect, where overly rich action spaces can degrade decision quality if not properly structured or ranked."

> "Second, the automatic generation of actions introduces additional computational overhead, as each expansion step requires either LLM inference or decomposition-based synthesis. While this process is **amortized over multiple executions**, it may still represent a non-trivial cost in real-world deployments."

> "Third, the effectiveness of B* may depend on the structure of the task. In highly sequential or syntax-constrained domains (e.g., program synthesis or formal verification), **naive action expansion may not yield improvements** unless the generated actions preserve strict semantic correctness."

> "Finally, the current evaluation is limited to a **single controlled environment** (Conway's Game of Life). While this environment provides a measurable and highly sensitive testbed, it does not cover domains such as API planning, symbolic reasoning or real-world tool orchestration."

**另有一条来自结果的警告（比局限更硬）**【原文 Q-19】：
> "When repeating and extending the same experiment to 40 rounds (Figure 4), we observe that the median performance **maintains stable**, indicating that the **reach of the LLM has saturated under the current cognitive function**. This suggests that further gains are no longer driven by the growth of the action space B*, but instead depend on the model's inherent ability to reason over increasingly complex and abundant tools."

⇒ **对我们最关键的一条**：**op 集变宽 ≠ 执行器变强**。若执行器不变，扩宽 op 集会饱和（我方用官方 CSV 复算：40 轮中位数在 ~25 轮后不再上升，见 §6.3）。
⇒ 与我们既有硬证据对齐：「扩宽思维面必然带来等比例更多的错误」「拓展思维面在提示词层买不到」⇒ **B\* 给的第三条路是"长 op 集"而不是"长候选数"**，这正是我们要试的。

---

## §5 任务级 vs 实例级的分工（"学一次用 N 次"）

### 5.1 P1 的分工（逐字）

【原文 Q-04】
> "**Stage 1 operates on task-level, meaning we only need to run SELF-DISCOVER once for each task.** Then, in Stage 2, we can simply use the discovered reasoning structure to solve every instance of the given task by instructing models to follow the provided structure by filling each key and arrive at a final answer."

【原文 Q-11】
> "we subsample 200 examples from the MATH ( Hendrycks et al., 2021 ) test set, and **generate instance-level reasoning structures via a one-shot demonstration** to adapt to the complexity of MATH tasks."

⇒ **"学一次用 N 次"在 P1 里不是普适的**：MATH 上作者自己退回了实例级结构。⇒ 我们不能把"任务级结构"当成对所有题都成立的先验。

### 5.2 我们的四层分工表（可直接写进 `spec.yaml`）

| 层 | 产物 | 频次 | 生成者 | 可否跨题复用 | 可否跨模型搬运 |
|---|---|---|---|---|---|
| **L0 目录层** | 6 承载面（§2.2）/ 或 39 模块池（消融臂） | **一次**（人写，冻结） | 人 | ✅ 跨题通用 | ✅ 天生可搬运 |
| **L1 拓扑层** | `step_structure`（§1.2） | **每题**（一次，N 个实例复用） | 路线 B/C 的 proposer 或人 | ❌ **不可跨题**（那是知识，不是结构） | ✅ **必须可搬运**（"拓扑"的定义要求） |
| **L2 执行层** | 实例答案 | 每实例 | 模型 | — | — |
| **L3 依据层** | 依据包原子事实（`user4_q*.json`） | 每题（人/外部） | 人/外部 | ✅ 跨题 | — |

**⇒ "学一次用 N 次"的正确边界**：L0 一次 + **L1 每题一次** + L2 每实例 ⇒ **每题摊销 3 次 meta-prompt 调用**（与 P1 完全同构：1 per instance + 3 task-level）。
⚠️ **可搬运性证据**（P1 §5.2，逐字）【Q-12, Q-13】：
> "Self-Discover outperforms OPRO on 3 out of 4 tasks despite that OPRO used 20% data to optimize the prompt."（PaLM 2-L 发现的结构喂给 GPT-4）
> "using self-discovered structures on Llama2 (**52%**) outperforms CoT (**42%**) on disambiguation QA zero-shot and on GPT-3.5-turbo (**56%**) outperforms CoT (**51%**) on geometry"
⇒ **这就是"显式步骤结构可跨模型搬运"的已发表证据**（不只是"提示词能搬"）。

### 5.3 一条我们自己的加固（针对 P1 的一个软点）

P1 的结构是**纯文本 JSON**，没有"每步依赖哪条依据"。⇒ 结构被搬到另一个模型时，**它可能被另一个模型"用自己的知识"填值** ⇒ 维度看似变宽，实际是**换了个来源的幻觉**。
⇒ **我们的加固**：每步 `bound_evidence` 必填（§1.2）⇒ 跨模型搬运时，**只允许搬结构、不允许搬知识**（值必须由依据包支撑）。
⇒ 这条同时是 §3 矩阵的**上游**：没有 `bound_evidence` 就填不出 `cells`。

---

## §6 效率并列判据（调用数/token 必须与 VD_net 并列报）

### 6.1 原文怎么报的（**这一段是本节最该抄的**）

【原文 Q-14 / Figure 5 图注逐字】
> "Figure 5. Comparison of accuracy with number of inference calls required per instance. For CoT-Self-Consistency, we sample 10 times. Best of each RM method requires gold labels (*). **SELF-DISCOVER requires only 1 inference call per instance (plus 3 more meta-prompts on the task-level), same as Direct and CoT while reaching better performance compared with 40x more call required methods (majority voting of each RM) on GPT-4. We acknowledge that SELF-DISCOVER input and output are longer than CoT and Direct prompting, increasing cost. However, as the number of instances increases, the efficiency of SELF-DISCOVER in terms of inference per instance is highly desirable.**"

【原文 Q-14 正文逐字】
> "Efficiency wise, SELF-DISCOVER only requires **one call per instance and three more inference calls on the task-level**, CoT-self-consistency requires 10 times more since we have to sample 10 times for each instance, and methods using each RM requires **40 times more as we use 40 RMs**."

**⇒ 三个可抄的报法**：
1. **调用数分层报**：任务级 vs 实例级**分开**（P1: 3 + 1×N）。
2. **自己认账**："input and output are longer than CoT and Direct prompting, increasing cost" ⇒ **P1 明确承认自己不是等 token 配平的**（这正是任务书 A6 要的原文，已在 Q-14 逐字给出）。
3. **摊销论证**："as the number of instances increases, the efficiency … is highly desirable" ⇒ 摊销项必须和主指标一起报。

### 6.2 我们的**并列判据**（预注册口径，写进 `spec.yaml`）

**任何臂都必须同时报这 6 项，缺一项 ⇒ 该臂数据不成立**：

| # | 指标 | 口径 | 出处 |
|---|---|---|---|
| E1 | **VD_net（净维度增益）** | 新增 − 丢失（双边），**同时报绝对条数与分母** | 本项目既有口径 |
| E2 | **LLM 调用数** | 任务级 + 实例级**分开报**（并报总数） | P1 §4.3 |
| E3 | **token** | 输入 / 输出**分开报**（总数） | P1 Figure 5 图注（它自认更贵） |
| E4 | **等 token 对照臂** | 把基线的 token 上限抬到与实验臂相同 ⇒ **同时报"不等 token"与"等 token"两条数** | 我方新增（P1 未做 ⇒ P1 的优势在等 token 下未验证） |
| E5 | **中位数 + 95% bootstrap CI + 效应量** | 报中位数与区间；效应量用 Cliff's Delta；组间比较用 Mann–Whitney U + Bonferroni 校正 | **P2 §5.2 直接可抄**【Q-19b】 |
| E6 | **噪声地板 δ** | 同臂同题重跑，量 run-to-run 波动；**净增益 < δ 一律不认** | 我方纪律（P1/P2 都没有） |

**禁止项**（写进自检脚本）：
- ❌ 只报"最高值/最好格"（P3 的 "+39.1% up to" 就是这个模式 ⇒ 不可抄）。
- ❌ 只报准确率/单一指标（量纲与 VD_net 不可比）。
- ❌ 报"提宽思维面"而不报 token（我方既有硬证据：提示词层扩宽必然等比例扩错面）。

### 6.3 我方用官方 CSV 复算的 B\* 数字（可作为 §6 的示范读数）

P2 官方仓 `results/results_40_rounds.csv` = **800 行 = 20 player × 40 轮**（`player_id, round, points`）。**我方复算的逐轮中位数**（原始 CSV，未加工）：

| round | 1 | 2 | 3 | 4 | 5 | 6 | **7** | 8 | 10 | 15 | 20 | **25** | 30 | 35 | 40 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| median | 50 | 48 | 48 | 47 | 48 | 48 | **96** | 83 | 92.5 | 103.5 | 98.5 | **129.5** | 117.5 | 93 | 87.5 |

⇒ 与论文叙述一致：前期中位数 ≈ 50（= 允许放置的活细胞数上限）⇒ **"不扩张动作集时，agent 基本只做到把初始活细胞放满"**；round 7 出现拐点；~round 25 后不再上升（**饱和**）。
⇒ **这组数给我们两条可直接用的判据**：
① **"净增益 = 0"的基线读数长什么样**：基线不是 0，而是 **50**（把预算用满但不产生结构优势）⇒ 我们的 VD_net 基线也必须报"用满预算的平凡解"。
② **饱和拐点可测**：P1/P2 都给了"到第几轮就不再变"的**可测形态** ⇒ 我们的 op 集扩张必须预先声明 K 与 δ。

### 6.4 成本公式（任务书 B6）

⚠️ **`O(agents² × rounds)` 是我方推断，不是 P3 原文**（P3 全文未读到方法节，也未见此式）。
- 结构性依据：P3 每轮"每个 agent 对每个其他 agent 给 credibility" ⇒ 互评边数 = agents×(agents−1)/2 ⇒ 评分调用次数 `Θ(agents²)`，乘轮数 ⇒ `Θ(agents² × rounds)`。**标注为【推断】**。
- **P3 自认的开销**（逐字）【Q-26】："This framework faces challenges such as **high computational overhead**, uneven performance across different task types, sensitive design of social attributes, **difficulty in expanding the number of agents**, and lack of theoretical guarantees."
- ⇒ 对我们的含义：agent 数是**平方级**成本 ⇒ 我们的臂用**少量 agent + 少量轮次**（如 3 agent × 2 轮），否则 VD_net 的净增益会被成本吃掉。

---

## §7 与既有路线 A / B / C 的接线（一句话一条）

| 路线 | 本文件的哪一节可直接接 | 怎么接 |
|---|---|---|
| **A（人定固定拓扑）** | §1.2（`step_structure` schema）＋ §2.3（目录消融臂） | 把 6 承载面目录换成 39 模块池 ⇒ 新增 `FACETS_39` 消融臂；结构里加 `bound_evidence` |
| **B（训练学出操作序列）** | §4（op 集演化） | proposer 改为"B\* 模式"：提出**复合 op**（只能由已有 op 组合），带上下文隔离规则 |
| **C（人定拓扑 + 训练调参）** | §3（agent×依据矩阵）＋ §6.2 | 目标函数加**承重依据数**（`load_bearing`）作第二目标；**⚠️ 不得引用 P3 的 "weight vector modulation" 作路线 C 证据**（§8 未决项） |
| **测量协议** | §6.2（E1–E6） | VD_net 与 calls/token **并列**进结果表；禁止只报最好格 |

---

## §8 未决项（**不得当作已解决**）

| # | 未决 | 状态 | 影响 | 补法（一次性） |
|---|---|---|---|---|
| U1 | **P3 的 "weight vector modulation" 到底改权重还是改 prompt** | ❌ **未查清**。已试：ScienceDirect 页面（爬虫文本跳过方法节）、Mendeley 目录（仅摘要）、ACM 目录（仅摘要+引文）、S2 API（abstract 为 null、无 OA PDF）、Crossref（abstract 空）、Unpaywall（closed）、`github.com/ioio0614/MAME` **404**、作者其余 4 个公开仓库（无 MAME） | **按任务书规则：查清前不得算作路线 C 的证据**（§7 已按此写） | 取 Elsevier TDM API（需 key）或作者直系索取；拿到后只需回答"改的是 prompt 文本 / 隐向量 / 权重"三选一 |
| U2 | **P1 三个 meta-prompt 的逐字原文**（Figure 10 是位图） | ❌ 未取得。官方仓 `skelearn/Self-Discover` **404（账号不存在）** | §1.3 只能给结构 + 第三方复现版 | 从 arXiv PDF 抽图 OCR / 人工誊写（Figure 10 存在 PDF 里） |
| U3 | P3 的置信矩阵**维度/取值域/聚合公式/回灌格式**、最大轮数、四数据集名、消融表、成本数字 | ❌ 未读到（方法节抓不到） | §3 只能借**表形态**，不能声称复现 | 同 U1 |
| U4 | P2 的"冗余动作等价检查"是否真在代码里 | ❌ **在已发布代码中未找到实现**（只找到隐式的语法/类型闸） | 我们若抄必须**自补**闸 ②（§4.3） | 已足够：直接自补 |
| U5 | P2 论文写 "gpt-4o-mini"，官方代码默认 `"openai:gpt-4.1-mini"`（生成器 temp 0.6） | ⚠️ **论文与代码不一致** | 复现时以代码为准；引用数字时标注模型名 | 已在 §4.2 标注 |

---

## §9 一页速查（可以直接贴进组会）

1. **表示法可抄**：显式步骤结构 = 自然语言键 + 顺序 + 每步绑定依据（Self-Discover 给了前两项，依据绑定是我们的增项）。
2. **目录要当假设检验**：39 模块 vs 我们的 6 承载面 ⇒ 新增 `FACETS_39` 消融臂（协议、预算、题目全同）。
3. **矩阵形态可抄、内容不可抄**：GFF 的 agent×agent 置信矩阵 ⇒ 换成 **agent×依据** 的引用表（离散、可核验、无 embedding）；**终局仲裁不许用自报置信度**。
4. **op 集可以长**：B\* = 完备基 + 复合 op（只能用基组合）+ 两道闸 + 生成/执行上下文隔离 ⇒ op 集演化的规格。
5. **报数要并列**：VD_net + 任务级/实例级调用数 + 输入/输出 token + **等 token 对照臂** + 中位数/CI/效应量 + 噪声地板 δ。
6. **两条硬警告**：op 集变宽会**饱和**（我方复算：~25 轮后中位数不升）；op 集变大带来**选择悖论**（须设可见 op 上限）。
