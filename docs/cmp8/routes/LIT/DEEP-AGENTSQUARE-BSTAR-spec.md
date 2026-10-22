# 代码级规格：AgentSquare（模块池 + 进化算子 + 预测器） × B* Expansion（动作空间自生长）

> 采集 2026-10-22 · 全部基于一手源（arXiv API / arXiv HTML v3 / GitHub raw / GitHub contents API / Crossref API）
> 逐字摘录见同目录 `DEEP-AGENTSQUARE-BSTAR-quotes.md`（本文所有"逐字"引用都能在那儿找到出处）
> **本文档里每条"已实现"都指"发布代码里确实有"，每条"未实现"都指"论文写了但代码没有"。**

---

## 0. 三条必须先知道的前提（否则会照抄到坑里）

### 0.1 仓库地址纠错

| 任务书给的 | 实际 | 证据 |
|---|---|---|
| `Xtra-Computing/AgentSquare` | ❌ **不存在**（404） | GitHub API `repos/Xtra-Computing/AgentSquare` → `Not Found` |
| — | ✅ **`tsinghua-fib-lab/AgentSquare`**（branch `main`，234★，描述自称 official implementation） | GitHub search API |
| `SamthinkGit/Bstar-Expansion` | ✅ 正确，但默认分支是 **`master`** 不是 `main` | `git/trees/main` → 404；`git/trees/master` → 280 entries |

### 0.2 B\* Expansion 跟我们的场景差得很远

它**不是** LLM Agent 架构搜索论文，是 **Conway 生命游戏**论文：
- "Agent" = LangChain `create_react_agent`，在一个 200×200 网格上摆 ≤50 个活细胞，模拟 300 代，得分＝终局活细胞数。
- "动作" = 一个 `.py` 文件里的 Python 函数（LangChain `@tool`）。
- "B\* = B ∪ A\*" = **基础工具集 ∪ LLM 新写的复合动作**。
- 它的"架构搜索"搜索的是**动作集**，不是**模块拓扑**。
⇒ **能抄的是"动作空间自己长"这个形态，不能抄它的目标函数（它就是任务分）、也不能抄它的评测（Game of Life 的分数没有语义）。**

### 0.3 AgentSquare 的 `search/` 管线**按现状跑不起来**

`search/module_evolution.py:97` 调 `get_prompt_reasoning(reasoning_modules, reasoning_last_feedback)`（**2 参**），
仓库里唯一的 `module_evolution/prompt_reasoning.py:500` 是 `def get_prompt_reasoning(current_archive)`（**1 参**）。4 个 `prompt_*.py` 全都这样。
⇒ **抄算子形状，不要抄目录结构。** 2 参版本还要读 archive 的 `'feedback'` 键，而发布的 `*_modules.json` 里没有这个键。

---

## A. AgentSquare —— 可抄规格

### A.1 模块池的数据结构（照抄这个 schema）

**一个 agent 配置 = 4 槽位 dict**（槽位名固定，值是模块名字符串）：

```python
Agent = {
    'planning': str,   # 模块名，或 'None'
    'reasoning': str,
    'tooluse' : str,
    'memory'  : str,
}
```

**模块池 = 4 个 JSON 列表，一个模块类型一个**，每条 entry 固定 5 个键：

```python
ModuleInfo = {
    'thought'    : str,   # 一句话说明这个模块干什么（会进提示词）
    'name'       : str,   # 模块唯一名
    'module type': str,   # 'planning'|'reasoning'|'tooluse'|'memory'
    'code'       : str,   # ★ 这个模块的 Python 类体源码（字符串）
    'performance': float, # 该模块单独接入时的实测分
}
```

初始池规模（实测）：planning 6 / reasoning 7 / tooluse 5 / memory 5。

**`code` 字段的关键性质（决定了我们的实现难度）：**
- 存的是**类体**，不是完整文件。形如 `class ReasoningIO(ReasoningBase):\n    def __call__(...)`。
- AgentSquare 用正则把它改名成测试类：`re.sub(r'class \w+\(.*Base\)', f'class {test_class}({base_class})', module_code)`，然后 append 到 `tasks/alfworld2/{type}_modules.py` 尾部，跑完再按行号截断删掉。
  ⇒ **这是"代码可插拔"的具体机制**：模块 = 一个继承固定基类的类体，运行时改名注入、事后删除。
- ⚠️ 代码里有个已知 bug 形态：LLM 生成的 `code` 字段里的换行是**真换行**而不是 `\n` 字面量，所以要 `.replace("'\n'", "'\\n'")` 修补（`search/module_evolution.py:146-155`）。

### A.2 统一 IO 契约（这是"模块化"的全部可操作性来源）

四个基类，四个 `__call__` 签名，**一个不多一个不少**：

| 模块 | 基类 | `__call__` 签名 | 返回 |
|---|---|---|---|
| Planning | `PlanningBase` | `(task_type: str, task_description: str, feedback: str)` | `plan`：**list[dict]**，每项含 sub-task 描述 + reasoning 指令 + tool-use 指令 |
| Reasoning | `ReasoningBase` | `(task_description: str, feedback: str = '')` | `reasoning_result`：当前这一步的推理结果（字符串） |
| ToolUse | `ToolUseBase` | `(task_description: str, tool_instruction: str, feedback_of_previous_tools: str)` | `tooluse_result` |
| Memory | `MemoryBase` | `(current_situation: str = '')` | (更新后的记忆, 检索到的记忆) |

统一构造：`__init__(self, llms_type: list[str])`（Reasoning 多一个 `profile_type_prompt: str`），**取 `llms_type[0]`**。

**可组合性的实际含义**：模块之间只通过**字符串 + 一个 dict 列表**通信，不共享状态、不直接互相调用。
- Planning 产出 dict 列表 → 逐项喂给 Reasoning；
- Reasoning 的 `__call__` 内部**可以**调用 memory 和 tooluse（`self.memory(task_description)` / `self.tooluse(task_description, tool_instruction)`），但这是可选的（可为 None）；
- Memory 是**状态型**的（`addMemory` / `retriveMemory`），有独立的向量库。

⇒ **这意味着：新增一个模块 = 写一个继承对应 Base 的类，签名对上，扔进 JSON。** 我们要做"模块池化"，这就是最小契约。

### A.3 ★ 进化算子（两个，形状完全不同，但子代构造完全相同）

#### A.3.1 重组算子 `recombination`（`search/recombination.py`）

```
输入: task_description, current_agent(incumbent), 4 个候选池{name→description}, tested_case[]
过程:
  1. 拼提示词: 任务描述 + 4 个候选池(名字+一句话描述) + 全量 tested_case(含分数)
     要求输出 {'planning':..,'reasoning':..,'tooluse':..,'memory':..}
  2. LLM: gpt-4o-mini, temperature=0.1, 一次调用
  3. eval(response) 解析
  4. ★ 物化成 4 个子代: 每个子代 = incumbent 保持 3 槽 + 只替换 1 槽
     agent1 = {新planning,  incumbent.reasoning, incumbent.tooluse, incumbent.memory}
     agent2 = {incumbent.planning, 新reasoning, incumbent.tooluse, incumbent.memory}
     agent3 = {incumbent.planning, incumbent.reasoning, 新tooluse, incumbent.memory}
     agent4 = {incumbent.planning, incumbent.reasoning, incumbent.tooluse, 新memory}
输出: [agent1, agent2, agent3, agent4]
```

**★ 关键机制解读（这是我们要抄的"重组动作"）**：
- LLM 提的是**一个完整配置**（一次性提 4 个槽），但**真正进入搜索空间的只有 4 个单点变异体**。
- 换句话说：**LLM 提议"换哪个槽、换成什么"，算子负责把它变成 4 条可比较的实验。**
- 这就是"重组"在 AgentSquare 里的全部含义：**单点交叉（single-point crossover），父本 = incumbent，交叉点 = 槽位，母本 = LLM 提议的模块池元素。**
- ⚠️ 没有真正的"双亲重组"（没有"把 A 的 planning 和 B 的 reasoning 拼起来"）。母本永远是 incumbent。
- ⚠️ 提示词里塞的是**全量历史 tested_case**（所有测过的组合 + 分数），随轮次线性增长。

#### A.3.2 进化算子 `evolution`（`search/module_evolution.py`）

```
输入: current_agent(incumbent), 4 个 archive(模块类型 → ModuleInfo 列表)
过程:
  1. 对每种模块类型: 构造 "进化提示词" = 模板 + 该类型的 archive 全部条目 + 一个 I/O 示例
  2. 对 4 种类型各调一次 LLM (gpt-4o-mini, temperature=0.8, response_format=json_object)
     强制返回 4 个键: name / thought / module type / code
     键不全 → while 循环重调（无上限！）
  3. ★ 物化成 4 个子代: 同样是"incumbent 保持 3 槽 + 只替换 1 槽"
     替换进去的是新模块的 name
输出: 4 个子代 + 4 个新 ModuleInfo
```

**进化提示词的结构（这是最值得抄的一段）**：
1. `# Overview`：你是 ML 研究者，要设计 **prompts 和 control flows**（不只是 prompt）。
2. `# Task Overview`：任务描述 + 一次完整的 ALFWorld 轨迹示例。
3. `# Reasoning Module Template`：**给出一个完整可运行的类骨架**，明确标注哪几行 `# do not modify this part`、哪一行是 `Fill in your code here.`。
   ⇒ **这是"统一 IO"能被 LLM 遵守的真正原因：把接口写进提示词的模板里。**
4. `# Discovered architecture archive` + `[ARCHIVE]`：已发现模块的完整列表（含 code 和 performance）注入点。
5. `# Output Instruction and Example`：规定 `thought` / `name` / `code` 三个键的语义，并强调 "**You must write a COMPLETE CODE**"。
6. `# Your task`：末尾一句 "**THINK OUTSIDE THE BOX.**"

⚠️ 提示词里的 `[ARCHIVE]` 注入方式是 `json.dumps` 整个 archive 列表（即把每个模块的完整源码塞进 JSON 字符串）。

#### A.3.3 两个算子的对比（决定我们怎么组合）

| | recombination | evolution |
|---|---|---|
| 提议者 | LLM **选名字** | LLM **写代码** |
| 搜索空间 | 已有模块池（有限） | 开放（任意符合 IO 的代码） |
| LLM 调用 | 1 次 | 4 次（每类型一次） |
| 子代数 | 4 | 4 |
| 子代形状 | **完全相同**：单槽替换 | **完全相同**：单槽替换 |
| 真机评测 | 4 个子代**全部**评测 | 4 个子代**全部**评测 |

⇒ **A.3.2 的"新模块"不进候选池就不会被 recombination 用到。** 代码里进化产物**不写回 JSON**，只在 `agent_search.py` 内存中的 `candidates`/`archives` 里更新 ⇒ 跨进程不持久。

### A.4 代理性能预测器

**形态：zero-shot in-context 回归，零训练。**

```
训练集（其实是"示例集"）:
  从 alfworld_results.json 取所有已实测的 (配置, 分数)
  → 每条转成 {prompt_answer: 4 个模块类的完整源码拼接, label: 分数}
  → random.seed(42); shuffle; 取 80%; 再截断到前 85 条
  → key 'label' 改名 'performance'

待预测批 (batch):
  每个候选 agent → 把 4 个模块的源码从 archive 里取出来拼成一大段文本

提示词:
  "You are a performance estimator..." + 4 个候选池描述 + train_data + batch
  要求输出 {'predictions':[{...,'performance': ''}, ...]}

推理: gpt-4o, temperature=0.0, 一次调用批量预测
解析: eval(response)['predictions']; 数量不足则补 0.0
```

**成本怎么降下来的（不在预测器里，在主循环里）：**
- 4 个重组子代 **只预测**，只有 `argmax(predicted_scores)` 那 1 个做真机评测（ALFWorld 50 episode）。
- 进化子代**不预测**，全部真机评测（因为新模块没进过 archive，预测器没见过）。
- ⇒ 每轮真机评测次数 = 4（进化）+ 1（重组）= 5，而不是 8。

**论文口径**：预测器成本 ≈ 完整 GPT-4o ALFWorld 评测的 **0.025%**。
⚠️ 这个 0.025% 是 **"ALFWorld 一次完整评测"为分母**（论文说单次 CoT agent 评测 ≈ $60），**不是"一次搜索迭代"为分母**。别拿它当"整个流程省了 99.975%"。

**⚠️ 预测器的能力边界（论文原话，注意限定）**：
> During the search process, **newly created agents from module evolution are still tested in the real task environment** because these new modules never appear in the experience pool, and **it is unsuitable to use the performance predictor to provide predictions.**

⇒ 预测器是**"见过的东西的性能外推"**，不是"新东西的判官"。**它不能当新颖度尺子用。**

### A.5 迭代预算 / 超参

| 项 | 代码实测值 | 论文值 |
|---|---|---|
| 迭代轮数 | `num_iterations = 10`（`search/agent_search.py:377`） | 实际跑到终止：**GPT-4o 8–18 轮**（Webshop 18 / ALFWorld 15 / SciWorld 9 / M3Tool 18 / Travel 8 / PDDL 12）；GPT-3.5 8–23 轮 |
| 停止条件 | ❌ **代码里没有**（跑满 10 轮就停） | **连续 5 轮无性能提升即终止** |
| 种群大小 N | ❌ 无种群概念（1 个 incumbent） | Algorithm 1 输入含 "population size N per evolution phase"，但代码里 N≡4（子代数） |
| 每次真机评测 | `n = 50` episode | — |
| 被评测 agent 的 LLM | `gpt-4o-mini` | GPT-3.5-turbo-0125 / GPT-4o |
| 重组 LLM | `gpt-4o-mini`, T=0.1 | — |
| 进化 LLM | `gpt-4o-mini`, T=0.8 | — |
| 预测器 LLM | `gpt-4o`, T=0.0 | — |
| 每轮 API 成本 | — | GPT-4o：$10.51 / $13.96 / $42.14 / $26.03 / $29.75 / $26.94（6 任务） |
| 初始 agent | **固定** `{planning:None, reasoning:IO, tooluse:None, memory:None}`，performance=0.56 | **随机模块组合** |
| 选择规则 | 精英保留 1 个：只在 `performance > current_performance` 时替换 incumbent | 同 |

⚠️ **初始 agent 和停止条件，代码与论文不一致**（代码固定 IO 起点、跑满 10 轮；论文说随机起点、5 轮无提升即停）。抄的时候要明确选一边。

### A.6 ★ 消融范式（`w/o module evolution`）

**论文的三个变体**（Table 2，GPT-4o）：

| Method | Webshop | ALFWorld | SciWorld | M3Tool | Travel | PDDL |
|---|---:|---:|---:|---:|---:|---:|
| AgentSquare (full) | 0.607 | 0.695 | 0.781 | 0.524 | 0.583 | 0.669 |
| w/o module evolution | 0.564 | 0.649 | 0.736 | 0.502 | 0.577 | 0.614 |
| w/o module recombination | 0.560 | 0.616 | 0.710 | 0.481 | **0.280** | 0.669 |

**★ 代码里没有消融开关。** 我通读了 `search/agent_search.py` 全部 535 行，无 `--ablation` / `if ablation` 分支。

⇒ **唯一的实现路径 = 拿掉一整个阶段**（主循环的 6 步是天然分段）：

```
w/o module evolution    ⇒ 跳过 1(evolution) 2(测新模块) 3(测进化子代)，只跑 4(重组) 5(预测) 6(测top1)
w/o module recombination ⇒ 跳过 4 5 6，只跑 1 2 3
```

⇒ **对我们的约束：我们的消融粒度只能是"关掉某个阶段"，不能是"关掉某个算子内部的一个分支"。**
⇒ **对我们有利的性质**：两个算子**共用同一个子代构造**（单槽替换），所以拿掉其中一个，另一个的 4 个子代仍然构型一致 ⇒ 两臂的"每轮实验次数"可以对齐（4+1 vs 4+0，可做成 4+0 vs 4+0 的对照或补一个 dummy）。

### A.7 ★ 目标函数（Q6 的答案）

**AgentSquare 的目标是纯任务标量，逐字为：**

```
argmax_{P∈P, R∈R, T∈T, M∈M}  Eval_d(P, R, T, M)
```

任务指标（Appendix A.1 逐字）：
- ALFWorld / M3ToolEval：**success rate**
- Webshop：**task score**（各 episode 平均 reward）
- SciWorld / PDDL：**progress rate**
- TravelPlanner：**micro pass rate**

**全文关键词统计（我对 arXiv HTML v3 抽取文本做的正则计数）**：

| 词 | 命中 | 备注 |
|---|:-:|---|
| `novelty` | **0** | — |
| `entropy` | **0** | — |
| `fitness` | **0** | — |
| `regret` | **0** | — |
| `diversit` | 1 | **仅出现在参考文献**（LLMATIC, GECCO 2024）；正文没有 |
| `coverage` | 1 | 散文一句 "broadens the coverage of child samples"，**不是目标项** |
| `objective` / `maximiz` | 各 1 | 即上面那句 argmax |

⇒ **结论（可直接写进我们的 related-work 段落）：**
> **AgentSquare 的目标函数里没有任何非任务标量。** 它唯一的"多样性"来自**机制**而非**目标**——模块池 + 经验池 E + "重组产生 4 个子代"这一动作本身，**但选择时只看任务分**。
> ⇒ **它是在"用多样性当手段"，不是"用多样性当目的"。**
> ⇒ 而且它引了 LLMATIC（GECCO 2024，QD 架构搜索）却没采用 ⇒ **"用 QD 目标搜 Agent 架构"这条路，AgentSquare 留空了。**

---

## B. B\* Expansion —— 可抄规格

### B.1 形态定义（论文 §3.3 的形式化，可直接抄进我们的框架描述）

```
A  : 无限动作空间（所有"LLM 能做的基本交互"）
B ⊂ A : 动作基（action basis）—— 有限、完备（任何 a∈A 都能由 B 中动作有限复合得到）
A* : 动作空间逼近器（action space approximator）—— 递增序列 A_0* ⊂ A_1* ⊂ …，A_0* = ∅
B* = B ∪ A*   ← 扩展后的动作空间
```

三条关键性质（论文原话要点）：
- **完备 ≠ 最优**："completeness ensures solvability but it does not imply optimality."
- **不需改模型、不需重训**："Scale incrementally, by adding actions to A* based on observed needs or performance feedback, **without modifying C or retraining the model**."
- **若 C 完美则 B\* 没必要**："If the LLM C were ideal and could reason perfectly, then the expansion B* would not be necessary."

### B.2 动作的表示形式（代码级）

**动作 = 一个 LangChain `@tool` 装饰的 Python 函数，定义在一个 `.py` 文件里。**

```python
from langchain_core.tools import tool
from game_of_life.core import get_current_game

@tool
def add_cell(x: int, y: int) -> bool:
    """Add a cell at the specified coordinates. Consumes 1 cell."""
    game = get_current_game()
    game.add_cell(x, y)
    return True
```

**动作空间的加载机制（这就是"B\* = B ∪ A\*"的实现）**：

```python
def load_functions_from_file(file_path: Path) -> dict:
    source = open(file_path).read()
    exec_globals = {"__builtins__": __builtins__, "get_current_game": get_current_game}
    local_ns = {}
    exec(source, exec_globals, local_ns)          # ← 整个文件被 exec
    return {name: obj for name, obj in local_ns.items()
            if callable(obj) and isinstance(obj, StructuredTool)}
```

- 初始 B = 从 `template.py` 复制一份（`shutil.copy(TEMPLATE_PATH, self.tool_env)`）到每个玩家自己的 `tools-<uuid>.py`。
- 每轮追加一个新函数 ⇒ **B\* 就是"这个文件里所有 `@tool` 函数的并集"**。
- **新旧动作天然共存**：`exec` 一次性加载全部，新动作就是文件里多出来的一个函数，不需要注册表、不需要版本号。

⚠️ 这个设计的代价（论文自己列了）：
> as the expanded action space A* grows, **the cognitive load on the language model increases** due to the need to select among a larger set of candidate actions. This may introduce a 'paradox of choice' effect.

### B.3 ★ A\* 的生成方式：**LLM 写的，不是枚举的**

`GENERATOR_PROMPT`（`game_of_life/agents/agents.py:36-66`）全文见 quotes 文件。关键约束逐条：

| 提示词原文 | 含义 |
|---|---|
| `Each function must follow the structure of the others: do not rewrite the existing functions, but rather a new one` | **只准追加，不准改旧动作** |
| `You can use only the functions already defined in the file to implement your new function.` | **新动作必须由已有动作复合而成**（B 的完备性在动作层面被强制） |
| `1. Write a short reasoning *as Python docstring* explaining the intuition behind the pattern you're adding` | **理由写进 docstring**（docstring 同时是 LLM 后续选动作时的语义说明） |
| `2. Then define a unique new Python function following the same pattern as the others.` | 结构必须对齐 |
| `The file you are the following: {file_content}` | **新动作生成时看得见全部历史动作** |
| `Your response will be pasted at the end of the file.` | 告知是追加语义 |

**生成器实现要点**：
- 模型 `ChatOpenAI(model=model, temperature=0.6)`（默认 `gpt-4.1-mini`；批量跑用 `gpt-4.1-nano`）。
- 只剥 markdown 围栏（`if lines[0].startswith("```")`），**无其他处理**。
- 直接 `f.write("\n" + response.content + "\n")` 追加到文件尾。

### B.4 ★ 扩展循环（每轮 = 玩一局 → 追加一个动作）

```python
def run_round(round_idx):
    with tracing_context(enabled=False):
        done = False
        while not done:
            try:
                pts = player.play_once(animate=False, interval=1)   # 用当前 B* 玩
                tool_gen.generate_tool_once()                        # 追加 A*_t
                done = True
            except Exception:
                logging.error("Retrying the round...", exc_info=True)
                continue
    return player.id, round_idx, pts
```

**B\* 是"每玩家一份"**（每个 player 有自己的 `tools-<uuid>.py`）⇒ 20 个玩家 ⇒ 20 条独立的扩展轨迹，**互不可见**。

### B.5 ⚠️ "扩展有用"的判据（Q9 的答案：**代码里没有**）

**我 grep 了仓库全部 Python 文件**（`accept|reject|valid|filter|equivalen|duplicat|prune|discard`），命中只有 1 处，且是提示词里的一句 "invalid sintax"。
**唯一的保护**：

```python
assert (
    game.points <= ALIVE_CELLS
), "LLM exceeded the maximum number of alive cells. Exit"
```

⇒ **发布代码里没有任何"接受/拒绝新动作"的判据**：无结构合法性检查、无冗余去重、无按效用取舍。
⚠️ 而且生成的代码若语法错，`exec` 抛异常 → 被 `except Exception` 吞掉 → 下一轮再 `exec` 同一个坏文件 → **死循环**（坏动作永远留在文件里）。

**论文声称的过滤（§3.3 逐字，代码未实现）**：
> each candidate action proposed for A* undergoes a filtering process before inclusion. First, structurally invalid actions ... are discarded. Second, redundant actions—defined as actions functionally equivalent to existing elements in B*—are removed using **deterministic equivalence checks over action signatures**. Only actions passing both criteria are incorporated into A_{n+1}*.

**论文强调的"生成-执行隔离"（§5.1 逐字，代码确实实现了）**：
> the generation of new actions is performed using the same model C but with **strict separation between generation and execution contexts**. Specifically, **the tool-generation process has no access to performance outcomes** ... This design avoids **direct optimization of A\* towards observed test-time performance** and ensures that improvements in B* arise from **structural action-space expansion rather than closed-loop adaptation to specific trajectories**.

⇒ **B\* 的扩展是开环的**：新动作不看分数。所以"扩展是否有用"**只能事后在群体层看曲线**，不能逐个判定。

### B.6 论文数字 vs 仓库数据（我本地复算，全部对得上）

**Table 1**（4 行全部复算成功）：

| Model | B\* | 论文 median | 论文 range | 仓库 CSV | 我算的 median | 我算的 range |
|---|---|---:|---:|---|---:|---:|
| gpt-4o-mini | ✗ | 50 | 0–820 | `results/env_results_r0.csv` | **50.0** | 0–820 ✅ |
| gpt-4o-mini | ✓ | 93 | 30–1292 | `results/env_results_r40.csv` | **93.5** | 30–1292 ✅ |
| o4-mini | ✗ | 40 | 0–1504 | `results/reasoning_results.csv` | **40.0** | 0–1504 ✅ |
| o4-mini | ✓ | 253 | 0–1870 | `results/env_results_r40_reasoning.csv` | **253.0** | 0–1870 ✅ |

**40 轮扩展曲线**（`results/results_40_rounds.csv`，20×40=800 行）我按轮复算中位数：
- round 1–6：**47.5 / 48.0 / 48.0 / 48.5 / 50.0** 附近平台
- round 7：**96.0**（突增，正好 ~2×）
- round 8–20：83–128 区间震荡
- round 21–40：87.5–225.5，**不再上升**
⇒ 论文三句叙述（≈50 平台 → round 7 突增 → round 25 ≈100 → 40 轮饱和）**全部被发布数据复算证实**。
⚠️ **均值远高于中位数**（round 1：均值 239.8 vs 中位数 50；round 6：126.2 vs 48.5）⇒ **分布重尾**。用均值会讲出完全不同的故事。
⚠️ 论文说"late rounds 方差收窄"，但我复算的 round 37 min=0 / max=1068，**方差并没有明显收窄**（只有 round 38–40 的 max 降到 274/565/834）⇒ **这一句只对最后 3 轮成立，不能推广到"接近 40 轮"**。

### B.7 B\* 的三个实验臂（可直接抄的对照设计）

| 臂 | 脚本 | 动作空间 | 模型 | 规模 |
|---|---|---|---|---|
| **扩展臂** | `lab/agentic_play_batch.py` | B → B*（边玩边长） | `gpt-4.1-nano` | 20 players × 25 轮 |
| **推理对照臂** | `lab/agentic_play_batch_reasoning.py` | 固定 B（不扩展） | `o4-mini` | 4 agents |
| **冻结评测臂** | `lab/agentic_play_env_batch.py` | 给定 .py（r0 或 r40） | `o4-mini` | 10 agents，文件从 `tools_env_40_rounds/` 随机抽 |

⇒ **"B vs B\*" 的对照是这样做的：拿 r40 的动作文件去跑一遍，和 r0（只有基础工具）比。** 这是一个可以直接抄的**双档动作空间对照**设计。

---

## C. 「用非任务标量当目标去搜 Agent 架构」——已有什么（★ 用户最想要的一条）

**先给结论：**
- **有，但没有人做过"搜 Agent 架构 + 非任务标量目标"这个精确组合。**
  最接近的三条线分别是：**(i) 搜"想法/研究方案"而非"Agent 架构"**（Heuresis）、**(ii) 搜"回答/推理路径"而非"Agent 架构"**（EoT、SetPO）、**(iii) 搜"Agent 行为"但目标是"多目标"而非"多样性"**（MOAE）。
- **AgentSquare 自己的参考文献里列了 LLMATIC（GECCO 2024，"Neural architecture search via LLM + Quality Diversity optimization"）——那才是"QD 目标 + 架构搜索"的正主，但它没被采用。**

### C.1 目标函数怎么定义的（形态层面，这是我们要抄的）

| 工作 | arXiv | 目标函数形态 | 档案结构 | 选择规则 |
|---|---|---|---|---|
| **EoT** | 2412.7779 | **二元 MOO**：`maximize M(A) = [M^Q(A), M^N(A)]ᵀ`。`M^Q` = 参照答案基准化的 LLM 判分（`M^Q(A)=f(p_q,p_s,A_ref,A)`）；`M^N` = **基于语义相似度**的新颖度 | 候选集 `A`（每轮 N→2N） | **NSGA-II 非支配排序**：`A_i ≺ A_j` 当且仅当 `M_N(A_i)≤M_N(A_j)` 且 `M_Q(A_i)≤M_Q(A_j)`；分 L 个 front，front 内按质量排；**新增候选 ⇒ 全体 M^N 重算** |
| **MOAE** | 2609.05992 | **Pareto 保持**：不做固定标量化。目标可插拔（实例化为 task performance + trajectory quality + safety） | **非支配候选的经验档案** | 搜索期只按"是否被支配"保留；**偏好只在部署时通过 constraint-aware selection 施加** ⇒ **搜索期不塌缩到单点** |
| **Heuresis** | 2606.25198 | 三轴 **Quality / Diversity / Novelty**。`MAP-Elites` 用**任务特定语义特征**（LLM 分类器事后抽）做离散化网格轴；`Omni` 用**Model of Interestingness 二值 LLM 有趣性判定**做门控 | MAP-Elites 网格（每格一个 elite）；Go-Explore 加访问计数偏置；Islands 岛屿种群+迁移 | 按 front / 兴趣度门控 / 岛屿锦标赛 |
| **SetPO** | 2602.1062 | **集合级多样性目标**（自称首个显式集合级多样性目标）：**整批样本的语义相似度聚合**出整体多样性；每条轨迹按 **leave-one-out 边际贡献**领奖 | 组内集合 | 反冗余估计器：稀有样本边际价值更高 |
| **DDO** | 2609.10052 | 多样性作为**训练目标**：`Divergence-Tree Collection`（从成功轨迹 rewind 到各决策点，用专家模型探索替代动作，成功则进 branch set）+ `Reference-Relative Target-Odds`（对整组成功分支建 target 分布，训 log-odds） | branch set | "所有成功分支都算对"，不让概率质量全压一条 |
| **DMPO** | 2605.19461 | **机制解释 + 目标改写**：mode collapse ＝ reverse-KL 的 mode-seeking。改成**组级 forward-KL 近似**：组内构造 `p(o_i|O) ∝ exp(r(o_i)/α)`，用 MSE 对齐策略分布 `L_DM = 1/G Σ (p−q)²`，总目标 `L_GRPO + λ L_DM` | — | — |
| **Reaching Beyond the Mode** | 2603.24844 | 后训练把答案分布**塌到单一众数**；改目标为**一次前向生成多个带置信度的假设** | — | — |
| **SwarmResearch** | 2607.02807 | **架构级**多样性（不是目标函数级）：每个 Search Agent 一个 git 分支做**上下文隔离**，Shepherd 跨分支协调 | — | — |
| **LLMATIC**（AgentSquare 引，未采用） | GECCO 2024, pp.1110–1118 | **QD 架构搜索**（据标题；⚠️ 我**只从 AgentSquare 原文逐字抄了这条参考文献**，没读原文） | QD 档案 | — |

### C.2 三条对我们最有用的形态结论

1. **多样性目标必须是"集合级/群体级"的，不是"单条"的。**
   SetPO 明说：单对比较（pairwise）不够，要**整批聚合**。EoT 的 `M^N` 也是"相对于其他候选"的相似度。
   ⇒ 我们若要"答案不要中庸"，判据应当是**一批候选答案之间的分散度**（如 embedding 空间里到质心的平均距离 / Vendi 分数），不是"单个答案有多怪"。

2. **非支配排序（Pareto / NSGA-II）比"加权标量化"更抗塌缩。**
   MOAE 明确点名："many collapse heterogeneous measurements into a fixed scalar score. Such scalarization depends on metric normalization and preference weights and may **discard candidates that represent useful deployment trade-offs**."
   ⇒ 我们的目标应该写成 **(任务正确率, 多样性) 二元向量**，用非支配排序保留，而不是 `score = 正确率 + λ·多样性`。

3. **⚠️ 前人的警告必须写进我们的实验设计：Heuresis 的实证结论是"QD 能改变落点，但撑不起前沿"。**
   > while current search and Quality-Diversity strategies enable us to steer where the generated ideas land on the quality, diversity, and novelty axes, **they do not expand the quality–novelty frontier.**
   > novel ideas **never approach the highest-performing known-recipe scores**.
   ⇒ **预期要写成**：加多样性目标会让**质量**略降、**多样性**明显升；**不要**承诺"两者兼得"。
   ⇒ 另外必须处理**奖励伪造**：Heuresis 在 1,628 次 scored runs 里确认 **40 次伪造**（2.5%），且提到有 executor 直接 `echo` 造假 log。我们如果用 LLM 判分做多样性目标，**必须有独立的审计层**（Heuresis 的 HackerJudge / Auditor 就是干这个的）。

---

## D. 对我们的落点（把上面压成可执行的）

### D.1 架构搜索这一层，照抄 AgentSquare 的形状

```
模块池 = 4 类 × (name, thought, code, performance)     ← 抄 A.1
统一 IO = 每类一个 Base + 一个 __call__ 签名            ← 抄 A.2
进化提示词 = 接口模板 + archive + 输出键规范            ← 抄 A.3.2 的 6 段结构
重组算子 = LLM 提全配置 → 物化成 4 个单槽子代          ← 抄 A.3.1
预测器   = zero-shot in-context，只预测不真评，argmax 才真评  ← 抄 A.4
消融     = 拿掉一整个阶段                              ← 抄 A.6
```

**我们要替换掉的**：现在的"3 因子笛卡尔积 36 格 + 47 参数因子化 softmax"——
AgentSquare 的做法是**让 LLM 提子代**，算子只负责"把提议物化成可比较的实验"，**选择器里没有 47 个手调参数**。

### D.2 动作空间自己长这一层，照抄 B\* 的形状

```
动作空间 = 一个文件 / 一个注册表，追加式，永不删除
新动作 = LLM 写的，必须只用已有动作复合
理由   = 写进 docstring（同时充当后续选择的语义说明）
每轮   = 用当前动作空间跑一次 → 再追加一个
```

⚠️ **但我们不能照抄 B\* 的"生成器不看分数"**——那是 B* 为了**因果归因**（证明提升来自"动作空间变大"而非"闭环调参"）故意做的隔离设计。
我们的目标是"让答案不中庸"，**需要闭环**（新动作要是没用就换掉）。⇒ **这一条要明确标注为"故意不抄"**。

### D.3 层 2 / 层 3 的分离（用户的四层框架）

| | 层 2（设计的手段） | 层 3（训练/自迭代） |
|---|---|---|
| AgentSquare 给的 | 模块池 + 统一 IO + **固定** 4 槽拓扑 | 重组 + 进化（LLM 写代码）+ 代理预测器 |
| B\* 给的 | 基础动作基 B（完备、有限） | 动作空间自增（LLM 写新动作） |
| **我们要加的（层 3 的另一半）** | — | ★ **把 (任务分, 多样性) 写成二元目标 + 非支配排序档案**（EoT / MOAE / SetPO） |
| **层 4（状态驱动）** | — | ⚠️ **AgentSquare 和 B\* 都没有**：两者都是"无状态模块/函数"，AgentSquare 的 Memory 模块算半个，但它是"检索历史轨迹"，不是"由内部状态决定下一步动作" |

---

## E. 一句话结论（用户要的那个）

> **不能。**
> AgentSquare + B\* 的组合得到的是"**LLM 开环提议 + 任务分闭环选择**"的结构：
> AgentSquare 的动作空间仍然是**人划好的 4 个槽位**（每槽的候选有限，新模块虽是 LLM 写的但仍被塞回同一个槽、只被"测一次看分"来决定去留）；
> B\* 的动作空间确实是自己长的，但它的生成器**被刻意与性能隔离**（论文明说"no access to performance outcomes"）⇒ 新动作是**开环追加**，没有"这个动作没用就撤掉"的机制。
> ⇒ **两个加起来仍然会收敛到单一"最高分解"，也就是"中庸"。**
> ⇒ **"架构由训练产生"这句话要成立，缺的不是第三个算子，而是第三个东西：把「多样性/新颖度」写进目标函数、让它参与选择（EoT 的 MOO / MOAE 的 Pareto 档案 / SetPO 的集合级多样性），并按 Heuresis 的警告预期"质量略降、多样性明显升"，而不是承诺两者兼得。**
