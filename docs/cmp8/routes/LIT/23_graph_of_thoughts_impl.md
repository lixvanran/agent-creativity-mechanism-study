# 精读 23 · `spcl/graph-of-thoughts`（GoT）——**实现细节 / 默认超参 / 评估代码**专项

> **分工声明**：本篇只写**实现层**（数据结构、算子签名、默认超参、评估脚本、复现成本）。
> 论文叙事、贡献论证、正文实验表由另一组负责；本文只在"代码能支撑什么判断"处引用论文级信息。
> ⚠️ 本文所有数字**全部来自仓库代码或仓库发布的 `final_results_gpt35.tar.bz2` 原始结果**，
> 我自己用 `paper/plots.py` 的打分逻辑重算过（脚本见 §2.3），**没有一处是估的**。

---

## 0. 引用

| 项 | 内容 |
|---|---|
| 标题 | *Graph of Thoughts: Solving Elaborate Problems with Large Language Models* |
| 作者 | Besta, Maciej; Blach, Nils; Kubicek, Ales; Gerstenberger, Robert; Gianinazzi, Lukas; Gajda, Joanna; Lehmann, Tomasz; Podstawski, Michał; Niewiadomski, Hubert; Nyczyk, Piotr; Hoefler, Torsten（ETH Zürich + Linköping University） |
| 年份 / venue | 2024，**AAAI 2024**（Vol. 38, No. 16, pp. 17682–17690） |
| DOI | `10.1609/aaai.v38i16.29720` |
| arXiv | `2308.09687` |
| 代码仓 | `https://github.com/spcl/graph-of-thoughts`（默认分支 `main`，2844★，BSD-3 风格 LICENSE，PyPI 包名 `graph_of_thoughts` v0.0.3） |
| 一句话 | **声称**自己解决了什么：把"思维链/思维树"这种**线性/树状**的推理结构推广成**任意有向图上的操作图（Graph of Operations, GoO）**，让 LLM 在图上做"生成 / 聚合 / 打分 / 改进 / 选择"等操作，从而解决"需要多个中间结果相互依赖"的复杂任务。 |

**代码层面的定位（对我们最重要的一句）**：
这个仓库**不是一个算法**，它是**一个"可插拔算子 + 静态拓扑"的执行框架**：
框架本身不知道任何任务语义，任务语义全部由两件事提供 ——
① 一张**人写死的算子 DAG**（`GraphOfOperations`），② 一对**自定义 Prompter / Parser**。
**评分、判优、终止全部在拓扑里写死。**

---

## 1. 核心机制（具体到能照着实现）

### 1.1 包结构（`graph_of_thoughts/`）

```
graph_of_thoughts/
├── controller/controller.py        # Controller：执行 GoO，产出 GRS
├── operations/
│   ├── operations.py              # 9 个算子 + Operation 基类 + OperationType 枚举
│   ├── thought.py                 # Thought：节点数据结构
│   └── graph_of_operations.py     # GraphOfOperations：GoO（拓扑）容器
├── language_models/
│   ├── abstract_language_model.py # AbstractLanguageModel（config/缓存/token 计数）
│   ├── chatgpt.py                 # ChatGPT（OpenAI）
│   ├── llamachat_hf.py            # Llama2HF（本地 4bit 量化）
│   └── config_template.json       # ★ 全部默认超参都在这里
├── parser/parser.py               # Parser 抽象基类（5 个 parse_* 方法）
└── prompter/prompter.py           # Prompter 抽象基类（5 个 *_prompt 方法）
examples/                          # 4 个 benchmark 的完整实现
paper/plots.py                     # ★ 官方出图 + 打分脚本
paper/final_results_gpt35.tar.bz2  # ★ 论文全部数字的原始结果（6.5MB / 656MB 解包）
```

### 1.2 状态表示 —— **"图"其实是两层，不是运行时数据图**

**⚠️ 这是最容易读错的地方**：GoT 里有两个不同的"图"。

**第一层：GoO（Graph of Operations）= 算子 DAG（静态，人写死）**

```python
class GraphOfOperations:
    operations: List[Operation]   # 全部算子，按添加顺序
    roots:     List[Operation]    # 无前驱者（入口）
    leaves:    List[Operation]    # 无后继者（出口，最终答案从这取）
```
- `append_operation(op)`：线性追加语义 —— 新 op 挂到**当前所有 leaf** 上，`leaves = [op]`。
- `add_operation(op)`：DAG 插入语义 —— 自己先 `op.add_predecessor(p)`（它会同时 `p.successors.append(op)`），
  再 `add_operation(op)`；`add_operation` 负责 roots/leaves 的簿记（把已完成的前驱从 leaves 移除）。
- **拓扑在执行前一次性构造完毕，运行中不可改**。

**第二层：GRS（Graph Reasoning State）= 运行时"隐式"的数据图**

代码里**没有一个 `Graph` / `Node` / `Edge` 类**。数据图是**在算子 DAG 执行时隐式形成的**：

- 节点 = `Thought` 实例（每个算子内部持有一个 `List[Thought]`）；
- 边 = "B 的输入来自 A" 这个**算子级**关系（A 是 B 的 predecessor）；
- 一次 `Generate` 产出多个 Thought ⇒ 数据图在这一层**分叉**；
- 一次 `Aggregate` 把多个 Thought 合成一个 ⇒ 数据图在这一层**合流**。

⇒ **分支/合流是"算子级"的现象，不是"节点级"的图。** 一个 Thought 不会被两条边共享
（`get_previous_thoughts()` 把前驱的 Thought **扁平化拷贝**到下游），
所以运行时的数据图其实是**树形的（每个 Thought 有唯一父）**，只是算子层面看起来是 DAG。

**`Thought` 完整字段**（`operations/thought.py:15-117`）：

```python
class Thought:
    id: int                    # 全局 itertools.count 自增
    state: Dict                # ★ 全部内容都在这个 dict 里（键值随 example 而异）
    _score: float = 0.0        # + scored: bool
    _valid: bool = False       # + validated: bool
    _solved: bool = False      # + compared_to_ground_truth: bool
```
三个 setter 会顺带置位标志（`score` → `scored=True`；`valid` → `validated=True`；`solved` → `compared_to_ground_truth=True`）。
`Thought.from_thought(t)` 复制标志，但 **state dict 是同一个对象引用（浅拷贝）** ⇒ 复制出来的 Thought
共享 state，后续任何原地修改会互相影响。**这是一个实现坑，我们复刻时要改成深拷贝。**

### 1.3 动作/算子全枚举（9 种，`operations/operations.py:22-35`）

```python
class OperationType(Enum):
    score: int = 0
    validate_and_improve: int = 1
    generate: int = 2
    improve: int = 3
    aggregate: int = 4
    keep_best_n: int = 5
    keep_valid: int = 6
    ground_truth_evaluator: int = 7
    selector: int = 8
```

**基类契约**（`operations.py:38-151`）：
```python
Operation.execute(lm, prompter, parser, **kwargs) -> None
    assert self.can_be_executed()          # 所有前驱都 executed
    self._execute(lm, prompter, parser, **kwargs)
    self.executed = True
Operation.get_previous_thoughts() -> List[Thought]   # 所有前驱 get_thoughts() 的扁平化拼接
Operation.get_thoughts() -> List[Thought]             # 抽象
```

**逐算子签名（输入 → 实现 → 输出）**

| 算子 | 构造参数（默认） | 输入 | LLM 调用 | 输出 |
|---|---|---|---|---|
| **Generate** | `num_branches_prompt=1, num_branches_response=1` | 前驱的 thoughts（无前驱时用 `**kwargs` 即 problem_parameters 当基态） | 每个输入 thought 调 1 次：`prompter.generate_prompt(num_branches_prompt, **state)` → `lm.query(prompt, num_responses=num_branches_response)` | `parser.parse_generate_answer(base_state, responses)` → 每个返回 dict 合并 `{**base_state, **new_state}` → 一个新 Thought |
| **Improve** | 无参 | 前驱 thoughts | 每个输入 1 次：`prompter.improve_prompt(**state)` → 1 响应 | `parser.parse_improve_answer(state, responses)` → `{**state, **update}` → 1 Thought |
| **ValidateAndImprove** | `num_samples=1, improve=True, num_tries=3, validate_function=None` | 前驱 thoughts | 每次校验 1 次（L1 模式：`prompter.validation_prompt` + `parser.parse_validation_answer`，`num_samples` 个响应）；改进每次 1 次（`num_responses=1`） | `self.thoughts: List[List[Thought]]`（每个输入一条"修补链"）；`get_thoughts()` 只返回**每条链的最后一个** |
| **Score** | `num_samples=1, combined_scoring=False, scoring_function=None` | 前驱 thoughts | 若 `scoring_function` 为 None ⇒ 走 LLM：`prompter.score_prompt(states)` → `lm.query(..., num_responses=num_samples)` → `parser.parse_score_answer(states, responses)` | 拷贝每个 Thought 并 `.score = score` |
| **Aggregate** | `num_responses=1` | 前驱 thoughts | **恒 1 次**：`prompter.aggregation_prompt(states)` → `lm.query(prompt, num_responses=num_responses)` | `parser.parse_aggregation_answer(states, responses)` → 每个 dict 合并到 `base_state` 上 |
| **KeepBestN** | `n`（必填, >0）, `higher_is_better=True` | 前驱 thoughts（**断言全部 `scored`**） | 0 | 按 `thought.score` 排序取前 n，拷贝为新 Thought |
| **KeepValid** | 无参 | 前驱 thoughts | 0 | 保留 `not thought.validated or thought.valid` 的 |
| **Selector** | `selector: Callable[[List[Thought]], List[Thought]]` | 前驱 thoughts | 0 | 纯 Python 过滤后的 Thought 拷贝 |
| **GroundTruth** | `ground_truth_evaluator: Callable[[Dict], bool]` | 前驱 thoughts | 0 | 置 `thought.solved`（异常 ⇒ False） |

**几个必须知道的实现细节**

1. **`Score` 的判据是"state 上的 Python 函数"，不是"文本相似度"** ★★★
   ```python
   scoring_function: Callable[[Union[List[Dict], Dict]], Union[List[float], float]]
   ```
   判据吃的是 **state dict**，输出一个 float。
   3/4 个 benchmark 用的是纯 Python 计数器（`utils.num_errors`），
   只有 doc_merge 退化成 LLM 打分（见 §6 的 U6 命中）。
   ⇒ **这正是我们要的"判据载体是结构量、不是措辞"（U3）**，
   而且它把**判据与拓扑解耦**了 —— 换判据不用改拓扑。

2. **`Aggregate` 的 `base_state` 是"字典覆盖合并"，不是真合并** ★
   ```python
   # applied in order of score
   base_state: Dict = {}
   for thought in sorted(previous_thoughts, key=lambda thought: thought.score):
       base_state = {**base_state, **thought.state}
   ```
   按 score **升序**遍历（分数低者先写、高分者后写 ⇒ **高分者覆盖低分者的同名字段**）。
   ⇒ 看起来像"把所有分支的字段并起来"，实际是"**同名字段被最高分那一支覆盖**"。
   合并出来的内容本身（LLM 生成的 `current`）**代码里完全不校验**。

3. **`Selector` 是唯一的"路由"机制**，而且路由键是 **state 里的离散字段**：
   ```python
   operations.Selector(lambda thoughts, list_id=list_id:
       [t for t in thoughts if t.state["part"] == list_id])
   ```
   全部 example 的路由键都是 `"List 1"/"List 2"`、`"Paragraph 1..8"`、`"Sentence 1..32"`。
   ⇒ **离散、可归因、无 embedding、无措辞相似度**（U1/U2/U3 全绕开）。

4. **`KeepBestN` 是"末端选择器"**，不是状态转移律：它只在**已有分支**里排序取 n，
   **不改变拓扑、不产生新状态**。

### 1.4 过程/回路 + **停止条件（代码常量级）**

**主循环**（`controller/controller.py:68-88`）：

```python
execution_queue = [op for op in self.graph.operations if op.can_be_executed()]
while len(execution_queue) > 0:
    current_operation = execution_queue.pop(0)
    current_operation.execute(self.lm, self.prompter, self.parser, **self.problem_parameters)
    for operation in current_operation.successors:
        assert operation in self.graph.operations
        if operation.can_be_executed():
            execution_queue.append(operation)
```
FIFO 队列；一个 op 在**所有前驱都 executed 后**才入队（因此不会重复执行）。

**★ 停止条件（共 4 个，全部枚举）**

| # | 停止条件 | 常量/位置 | 性质 |
|---|---|---|---|
| 1 | **队列空**（全部 op 执行完） | `while len(execution_queue) > 0` | **数据无关**。轮数 = 拓扑长度，**写死在 GoO 里** |
| 2 | **ValidateAndImprove 的修补上限** | `num_tries=3`（`operations.py:280`）；判据 `not self.improve or current_thought.valid or current_try >= self.num_tries` | **唯一的数据依赖型停止**，且是布尔通过/不通过 |
| 3 | **美元预算耗尽** | `budget = 30`（各 example `__main__`）；`if budget <= 0.0: break`（`sorting_032.py:667,675`） | **外部预算**，不是算法内的 |
| 4 | **Generate 超量告警（不是停止！）** | `if len(self.thoughts) > num_branches_prompt*num_branches_response*len(previous_thoughts) and num_branches_prompt > 0: logger.warning(...)`（`operations.py:464-474`） | 只是 warning |

**⇒ 关键结论：GoT 里没有任何"质量驱动的早停 / 回退 / 重规划"。**
"跑几轮"完全由 `for _ in range(k)` 这样的**硬编码常量**决定，例如：
- `sorting_032.tot()`：`for _ in range(1)`（1 层）；`tot2()`：`for _ in range(2)`（2 层）
- `keyword_counting.tot()`：`range(3)`；`tot2()`：`range(5)`
- `sorting_064/128` 的 GoT：拓扑里直接画了 `improve_aggregate_i` 节点（人写死的"回到上一层再修一次"）

### 1.5 输出

- **运行时**：`Controller.get_final_thoughts() -> List[List[Thought]]` = 所有 **leaf** 算子的 thoughts。
- **落盘**：`Controller.output_graph(path)` 写一个 JSON 数组：
  ```json
  [ {"operation": "generate", "thoughts": [ {state...}, ... ],
     "scored": [bool...], "scores": [float...],
     "validated": [...], "validity": [...],
     "compared_to_ground_truth": [...], "problem_solved": [...]},
    ...每个 op 一项...,
    {"prompt_tokens": 3741, "completion_tokens": 2685, "cost": 0.01098} ]
  ```
  ⇒ **"图"最终被序列化成 op 序列 + 每 op 的 thought 列表**，没有显式 node/edge 数组。
- **最终答案的取法在 `paper/plots.py`**（见 §3.1）：排序/集合/计数三个 benchmark 取
  `ground_truth_evaluator` op 的 `min(scores)` 与 `any(problem_solved)`；
  doc_merge 取最后一个 `score` op 的 `max(scores)`。

### 1.6 谁来评价 + 评价信号怎么回传给搜索

| benchmark | 判官 | 信号形态 | 信号用在哪 |
|---|---|---|---|
| sorting_032/064/128 | **纯 Python** `utils.num_errors`（数"错元素个数"） | 离散整数（越低越好） | `KeepBestN(1, higher_is_better=False)` 选分支 |
| set_intersection_* | **纯 Python** `utils.num_errors`（对齐两个有序表算错位数） | 离散整数 | 同上 |
| keyword_counting | **纯 Python** `num_errors`（按国家逐个比对频次） | 离散整数 | 同上 |
| document_merging | ⚠️ **同一个 LLM（gpt-3.5-turbo）自评** | 0–10 浮点（两个子分的 F1） | `KeepBestN(n, higher_is_better=True)` 选分支 |

**信号如何回传**：**它不回传给"搜索"，只回传给"选择"。**
`score` 被写进 `Thought._score`（置 `scored=True`），之后只被两处消费：
1. `KeepBestN.get_best_n()`：`sorted(previous_thoughts, key=lambda t: t.score, reverse=higher_is_better)[:n]`；
2. `Aggregate._execute`：`sorted(previous_thoughts, key=lambda t: t.score)`（决定 base_state 覆盖顺序）。

**没有任何算子会根据 score 改变拓扑、决定下一个算子、或触发回退。**
⇒ **GoT = 静态拓扑 + 末端选择器**，与"评价信号驱动的状态转移律"是两回事（见 §8）。

---

## 2. 关键数字（全部来自代码 + 官方发布的原始结果）

### 2.1 实验设置（代码常量）

| 项 | 值 | 出处 |
|---|---|---|
| 模型 | `gpt-3.5-turbo`（`config_template.json` 的 `chatgpt` 段；`gpt-4` 备选） | `language_models/config_template.json` |
| 归档名 | `final_results_gpt35.tar.bz2` ⇒ 论文数字全部来自 GPT-3.5 | `paper/README.md` |
| benchmark × 规模 | sorting {32,64,128}、set_intersection {32,64,128}、keyword_counting（1 档）、document_merging（1 档） | `examples/*/README.md` |
| 每 benchmark 题数 | sorting / set_intersection / keyword_counting **100 题**；document_merging **50 题** | 各 `__main__`：`samples = [item for item in range(0, 100)]` / `range(0, 50)` |
| **每题重复次数** | **1**（`run()` 里每个 (sample, method) 只跑一次，无重复、无自一致性投票） | `sorting_032.py:665-711` |
| **随机种子** | **LLM 侧完全没有**（OpenAI 调用不传 seed，`temperature=1.0`）。仅数据集生成器有 `seed = 42`（只用于 set_intersection） | `chatgpt.py:117-124`；`dataset_gen_intersection.py:47` |
| **并发** | **串行单线程**（`for data: for method:` 双层循环，无 asyncio / threading） | 各 `run()` |
| 预算 | `budget = 30` USD / 每次 `run()` | 各 `__main__` |
| 缓存 | `ChatGPT(..., cache=True)`，但**每个 (sample, method) 新建一个 LM 实例** ⇒ 缓存**不跨样本**生效 | `sorting_032.py:680-687` |

### 2.2 ★ 默认超参全表

**A. 模型层**（`language_models/config_template.json` + `chatgpt.py`）

| 键 | `chatgpt` | `chatgpt4` | `llama{7,13,70}b-hf` | 出处 |
|---|---|---|---|---|
| `model_id` | `gpt-3.5-turbo` | `gpt-4` | `Llama-2-{7,13,70}b-chat-hf` | config_template.json |
| **`temperature`** | **1.0** | **1.0** | **0.6** | config_template.json |
| **`top_p`** | **不存在**（全仓 `grep top_p` 0 命中，OpenAI 调用根本没传） | — | — | — |
| `top_k` | — | — | **10** | config_template.json |
| **`max_tokens`** | **1536** | **4096** | **4096**（作 `max_length`） | config_template.json / `llamachat_hf.py:96` |
| `stop` | `null` | `null` | — | config_template.json |
| `prompt_token_cost`（/1k tok） | **0.0015** | 0.03 | 0.0 | config_template.json |
| `response_token_cost`（/1k tok） | **0.002** | 0.06 | 0.0 | config_template.json |
| `organization` | `""`（空则 warn） | `""` | — | `chatgpt.py:54-56` |
| `api_key` | env `OPENAI_API_KEY` 优先，否则 config | 同 | — | `chatgpt.py:57-59` |
| `cache`（构造参数） | `False`（类默认）；**example 里传 `True`** | — | `False` | `chatgpt.py:28` / `sorting_032.py:686` |
| **重试** | `@backoff.on_exception(backoff.expo, OpenAIError, max_time=10, max_tries=6)`；`query()` 内部另有"批量对半降级 + `sleep(random.randint(1,3))`"，`total_num_attempts = num_responses` | — | — | `chatgpt.py:83-104` |
| **单次 API 请求的样本数** | `n=num_responses`（**一次 API 调用拿 n 个样本**，不是 n 次调用） | — | 逐条循环 | `chatgpt.py:117-124` |
| `seed` | **无** | 无 | 无（`do_sample=True`，无固定 seed） | — |

**B. 算子层**（`operations/operations.py` 构造器默认值）

| 算子 | 参数 | 默认 | 行号 |
|---|---|---|---|
| `Score` | `num_samples` | **1** | `:163` |
| `Score` | `combined_scoring` | **False**（⇒ **逐条打分**，每个 thought 一次 API 调用） | `:164` |
| `Score` | `scoring_function` | `None`（⇒ 走 LLM） | `:167` |
| `ValidateAndImprove` | `num_samples` | **1** | `:277` |
| `ValidateAndImprove` | `improve` | **True** | `:278` |
| `ValidateAndImprove` | **`num_tries`** | **3** | `:280` |
| `ValidateAndImprove` | `validate_function` | `None` | `:281` |
| `Generate` | `num_branches_prompt` | **1**（只传给 prompter，让 prompt 文本里"要求分几支"） | `:399` |
| `Generate` | `num_branches_response` | **1**（**真正的 API 采样数 n**） | `:399` |
| `Improve` | — | 无参 | `:487` |
| `Aggregate` | `num_responses` | **1** | `:543` |
| `KeepBestN` | `n` | 必填（`assert n > 0`） | `:619` |
| `KeepBestN` | `higher_is_better` | **True** | `:619` |
| `KeepValid` / `Selector` / `GroundTruth` | — | — | — |

**C. 拓扑层（各 example 的 GoO 常量）**

| example | 方法 | 分支/层数常量 |
|---|---|---|
| sorting_032 | `io`/`cot` | `Generate(1,1)` → Score → GroundTruth（**1 次调用**） |
| sorting_032 | `tot` | `Generate(1,20)`，**1 层**；`tot2`：`Generate(1,10)`，**2 层** |
| sorting_032 | `got` | split `Generate(1,1)` → 2×[Selector → `Generate(1,5)` → Score → KeepBestN(1)] → `Aggregate(10)` → Score → KeepBestN(1) → `Generate(1,10)` → Score → KeepBestN(1) → GroundTruth |
| sorting_064/128 | `got` | 多级 aggregate，**每级 aggregate 后接一个 `Generate(1,5)` 的"改进"节点**（128 元素版有 4+3 级） |
| set_intersection_032 | `got` | 2 路 split → 2×[Selector → `Generate(1,5)` → Score → KeepBestN] → `Aggregate(10)` |
| set_intersection_128 | `got` | **8 路** split → 8 子链 → 4×`Aggregate(5)` → 2×`Aggregate(5)` → 1×`Aggregate(5)` |
| keyword_counting | `got4`/`got8`/`gotx` | 4/8/32 路 split → 子链 → 逐级 `Aggregate(3)`，每级插入 `ValidateAndImprove(1, True, 3, valid_aggregation)` |
| document_merging | `tot` | `branch_factor=10`，**2 层** |
| document_merging | `got` | `Generate(1,5)` → Score(3) → KeepBestN(3) → `Aggregate(5)` → Score(3) → KeepBestN(1) → `Generate(1,10)` → Score(3) → KeepBestN(1) |
| document_merging | `got2` | 2 组子文档 → 递归两两 `Aggregate(5)` → 每级 `Generate(1,5)` + Score(3) |

### 2.3 ★ 主指标读数（我按 `paper/plots.py` 的官方打分逻辑，对 `final_results_gpt35.tar.bz2` 重算）

> 打分逻辑（`paper/plots.py:36-61`）：`score = min(op["scores"])`（ground_truth op），
> `solved = any(op["problem_solved"])`；doc_merge 用 `get_final_scores_doc_merge`（`plots.py:64-89`）：
> **倒序**遍历取**最后一个** `score` op 的 `max(op["scores"])`。
> 我的复算脚本：`/workspace/lab/routes/LIT/_raw/got/analyze.py`，输出：`.../got/analysis.txt`。

**① sorting（错误元素数，越低越好；n=100/方法）**

| 方法 | 32 元素 | 64 元素 | 128 元素 | solved(32/64/128) |
|---|---|---|---|---|
| IO | mean 4.53 (median 4) | 41.52 (40.5) | 123.93 (128) | 2 / 0 / 0 |
| CoT | 6.58 (6) | 21.63 (20) | 64.56 (57) | 0 / 0 / 0 |
| ToT（宽树, 20 支） | 1.90 (2) | 16.79 (16) | 52.87 (45.5) | 10 / 0 / 0 |
| ToT2（深树, 10 支） | 2.25 (2) | 19.53 (18) | 63.04 (55) | 7 / 0 / 0 |
| **GoT** | **1.84 (2)** | **7.00 (7)** | **17.52 (17)** | **10 / 0 / 0** |

**② set_intersection（错位数，越低越好；n=100/方法）**

| 方法 | 32 元素 | 64 元素 | 128 元素 | solved(32/64/128) |
|---|---|---|---|---|
| IO | 5.72 (3) | 17.33 (16) | 49.39 (48.5) | 7 / 0 / 0 |
| CoT | 4.49 (4) | 16.41 (15) | 42.11 (40.5) | 6 / 0 / 0 |
| ToT | 1.21 (1) | 10.05 (10) | 31.01 (31) | 31 / 0 / 0 |
| ToT2 | 1.47 (1) | 11.56 (11) | 34.14 (34) | 29 / 0 / 0 |
| **GoT** | **2.58 (1)** | **5.96 (4)** | 21.80 (12.5)〔n=10〕 | **49 / 2 / 0** |
| GoT2 | 3.28 (1) | 5.58 (4) | 21.80 (12.5) | 43 / 4 / 0 |

**③ keyword_counting（错频次数，越低越好；n=100/方法）**

| 方法 | mean (median) | solved | 成本 |
|---|---|---|---|
| IO | 14.82 (14) | 0 | $0.1448 |
| CoT | 14.90 (14) | 0 | $0.3003 |
| ToT | 4.60 (4) | 1 | $5.8503 |
| ToT2 | 5.56 (5) | 0 | $2.8139 |
| **GoT4** | **3.78 (3)** | **8** | $2.9291 |
| GoT8 | 3.78 (3) | 7 | $4.3936 |
| **GoTx**（按句拆 32 段） | **1.55 (1)** | **25** | $3.1820 |

**④ document_merging（★ LLM 自评 0–10 分，越高越好）**

| 方法 | n | mean (median) | 总成本 | 平均/题 |
|---|---|---|---|---|
| IO | 51 | 6.40 (6.43) | $0.8738 | $0.0171 |
| CoT | 51 | 6.63 (6.67) | $0.8648 | $0.0170 |
| ToT | 50 | 7.86 (7.94) | $11.9468 | $0.2389 |
| **GoT** | 50 | **7.86 (7.78)** | $10.5349 | $0.2107 |
| **GoT2** | 50 | 7.80 (7.77) | $8.8129 | $0.1763 |

⚠️ **这张表是 U6 的直接受害者**：分数是 gpt-3.5-turbo 自己打的（详见 §6.1）。

### 2.4 成本（token / 美元，来自发布的原始结果）

| benchmark | 方法 | prompt_tokens | completion_tokens | 总成本 | 平均/题 |
|---|---|---|---|---|---|
| sorting_032 | CoT | 161,900 | 25,558 | $0.2940 | $0.0029 |
| sorting_032 | **GoT** | 373,818 | 292,192 | $1.1451 | $0.0115 |
| sorting_032 | ToT | 230,758 | 488,102 | $1.3223 | $0.0132 |
| sorting_128 | CoT | 190,700 | 101,907 | $0.4899 | $0.0049 |
| sorting_128 | **GoT** | 2,135,458 | 2,601,524 | $8.4062 | $0.0841 |
| sorting_128 | ToT | 596,652 | 5,678,391 | $12.2518 | $0.1225 |
| set_int_032 | CoT | 162,300 | 20,264 | $0.2840 | $0.0028 |
| set_int_032 | **GoT** | 497,726 | 162,393 | $1.0714 | $0.0107 |
| keyword_counting | CoT | 141,242 | 44,222 | $0.3003 | $0.0030 |
| keyword_counting | **GoTx** | 1,552,607 | 426,553 | $3.1820 | $0.0318 |
| doc_merge | CoT | 189,956 | 73,722 | $0.8648 | $0.0170 |
| doc_merge | **GoT** | 1,795,632 | 1,287,010 | $10.5349 | $0.2107 |

⇒ **GoT 的 token 成本是 CoT 的 3.8–17.2 倍**
（sorting_032 $1.1451/$0.2940 = 3.9×；set_int_032 $1.0714/$0.2840 = 3.8×；
keyword_counting $3.1820/$0.3003 = 10.6×；sorting_128 $8.4062/$0.4899 = 17.2×；
doc_merge $10.5349/$0.8648 = **12.2×**）。
⇒ ⚠️ **GoT 赢的每一个 benchmark，都是"多花了 3.8–17 倍的钱"换来的**，代码里**没有做等预算对照**。

### 2.5 ★ 复现成本：一次 run 多少次 LLM 调用

**这是我自己跑出来的**（`/workspace/lab/routes/LIT/_raw/got/simulate.py`：用**真实**的 `operations.py` /
`controller.py`，只把 OpenAI SDK 与 prompter/parser 换成 mock，逐 op 统计 `lm.query()` 次数）：

| benchmark | 方法 | **API 调用次数** | 请求响应总数 | 每次调用的 n |
|---|---|---|---|---|
| sorting_032 | IO / CoT | **1** | 1 | [1] |
| sorting_032 | ToT | **2** | 40 | [20, 20] |
| sorting_032 | ToT2 | **3** | 30 | [10,10,10] |
| sorting_032 | **GoT** | **5** | 31 | [1, 5, 5, 10, 10] |
| sorting_064 | ToT / ToT2 | 4 / 7 | 80 / 70 | [20×4] / [10×7] |
| sorting_064 | **GoT** | **7** | 46 | [1,5,5,10,5,10,10] |
| sorting_128 | ToT / ToT2 | 4 / 10 | 80 / 100 | [20×4] / [10×10] |
| sorting_128 | **GoT** | **9** | 61 | [1,5,5,10,5,10,5,10,10] |
| set_int_032 | **GoT** | 4 | 21 | [1,5,5,10] |
| set_int_064 | **GoT** | 5 | 31 | [1,5,5,10,10] |
| set_int_128 | **GoT** | 6 | 26 | [1,5,5,5,5,5] |
| keyword_counting | ToT / ToT2 | 4 / 6 | 80 / 60 | [20×4] / [10×6] |
| keyword_counting | **GoT4 / GoT8 / GoTx** | **8 / 16 / 64** | 50 / 102 / 414 | [1,10×4,3×3] / [1,10×8,3×7] / [1,10×32,3×31] |
| doc_merge | IO / CoT | **2** | 4 | [1, 3]（3 = Score 的 num_samples） |
| doc_merge | ToT | **33** | 120 | [10, 3, 3, …] |
| doc_merge | **GoT / GoT2** | **23 / 24** | 80 / 80 | [5,3,3,3,3,3,…] |

**读法**：**"API 调用次数"很少（1–64 次），但"请求的响应总数"很大（4–414）**。
GoT 的贵不来自调用次数，而来自**每问一次要 5–10 个样本**（`n=` 参数）**加上超长 prompt**
（doc_merge 的 prompt 塞了 4 份完整 NDA + 全部中间摘要）。

**复现总成本估算**（用发布结果反推，GPT-3.5-turbo 价目 0.0015/0.002 per 1k）：
- 完整复现论文 8 张图 ≈ **$150–200**（各 benchmark × 各方法 × 100 题的美元和见 §2.4；
  实际论文还跑了 gpt-4 与 llama 变体，未在本归档中）。
- 单题单方法：CoT 约 $0.003；GoT 约 $0.01（sorting_032）到 $0.21（doc_merge）。

---

## 3. ★ 它的「成功标准」是什么

### 3.1 代码里怎么判定"成功"（`paper/plots.py`）

```python
# get_final_scores (sorting / set_intersection / keyword_counting)
for op in result["data"]:
    if "operation" in op and op["operation"] == "ground_truth_evaluator":
        score = min(op["scores"])          # ← 全图最小错误数（不是最后一个节点的分数）
        solved = any(op["problem_solved"]) # ← 图里任意一个节点判定为 solved 就算 solved
# get_final_scores_doc_merge (document_merging)
for op in reversed(result["data"]):
    if "operation" in op and op["operation"] == "score":
        score = max(op["scores"])          # ← 最后一个 score op 的最大分
```

- **主指标**：三个 benchmark = **错误元素数（越低越好）+ solved 计数（exact match）**；
  doc_merge = **0–10 的 LLM 自评分（越高越好）**。
- **对照**：`io`（直接问）、`cot`、`tot`（宽树 ToT）、`tot2`（深树 ToT2），
  以及 `got2`/`gsp4`/`gsp8`/`gspx` 等 GoT 变体。
- **阈值**：**没有**。代码里没有"多少分算成功"的阈值；成功 = "同一张图里的另一个方法更低/更高"。
- **否证条件**：**代码里完全没有**。没有"如果 GoT 不显著优于 ToT 则……"这类分支。
- **"不可分辨"报告**：**没有**。`plots.py` 只画 boxplot + 成本柱状图，**不画误差棒、不做显著性检验**。

### 3.2 ★ 三个必须点名的方法学问题

1. **`solved = any(op["problem_solved"])` 是"全图最优"口径** ⇒
   读数是 **best-of-graph**，不是"最终答案准确率"。
   一个方法只要在图里**任何一处**撞上正确答案就算 solved ⇒
   **分支数越多，solved 的期望就越高**（ToT 分支 20、GoT 拆 8/32 段 ⇒ 天然占便宜）。
   ⇒ 这正是我们说的"**条数多 ≠ 承重维度多**"（U7）在**判据层面**的体现。
2. **判据（选分支）与判据（报成绩）同一个** ⇒ 存在 **winner's curse**：
   `KeepBestN` 用 score 选出的那条"最优分支"，其 score 天然是**被同一个判官挑出来的最大值**，
   再把它当成绩报出来 ⇒ 系统性偏乐观。代码层面无任何校正。
3. **⚠️ 归档里有"截断"样本**（我解压后逐目录数过）：
   - `set_intersection_gpt35_128/tog`（GoT）**只有 10 个 json**（0–9），其他方法都是 100；
   - `document_merging_gpt35_16k/{io,cot}` 有 51 个，其余 50。
   ⇒ 说明这些跑次是**撞上 `$30` 预算上限被 `break` 截断**的。
   `plots.py` 对缺失样本**不补齐、直接画 boxplot** ⇒ **GoT-128 的均值是在 n=10 上算的，
   且样本是非随机的前 10 题** ⇒ 存在**选择性偏差**。

### 3.3 复现性提示（我核对过的）

- 归档里的方法目录名是**旧命名**：`tog / tog2 / gsp / gsp4 / gsp8 / gspx`；
  当前代码里的函数名是 `got / got2 / got4 / got8 / gotx` ⇒ **发布的数字产自比当前 HEAD 更早的代码版本**。
- 更硬的证据：归档里 sorting 的聚合 op 名字是 **`combine`**，而当前代码 `OperationType.aggregate.name == "aggregate"`；
  doc_merge 的归档里却是 `aggregate` ⇒ **同一份归档内部就混了两个版本的代码产出**。
- 好消息：我逐 op 对比了 `sorting_gpt35_032/tog/0.json` 的 op 序列
  （`generate(2) → selector → generate(5) → score(5) → keep_best_n → selector → generate(5) → score(5) →
  keep_best_n → combine(10) → score(10) → keep_best_n → generate(10) → score(11) → keep_best_n → ground_truth_evaluator`）
  与当前 `sorting_032.got()` 的拓扑，**结构一致** ⇒ 拓扑层面可复现，但命名/细节已漂移。

---

## 4. 自认的局限

⚠️ **本仓库没有 Limitations 章节**（论文正文由另一组负责）。以下**全是"代码自身暴露"的事实**，
不是作者原话；**唯一能引为原话的是仓库文档里的几句**：

> "The Controller class is responsible for traversing the Graph of Operations (GoO), which is a **static structure that is constructed once, before the execution starts**."
> —— `graph_of_thoughts/controller/README.md:3`

> "GoO prescribes the execution plan of thought operations and the Controller invokes their execution, generating the Graph Reasoning State (GRS)."
> —— `graph_of_thoughts/controller/README.md:4`

代码层面可见的局限（我的判断，逐条可指到文件行）：

1. **拓扑是静态的、一次写死的**（`controller/README.md:3`）⇒ 没有"根据中间结果改变下一步"的能力。
2. **`Aggregate` 不校验合并是否保住了输入**（`operations.py:563-609`）⇒ 合并可以静默丢信息，
   且 `base_state` 是**按 score 覆盖合并**（`:588-591`）⇒ 同名字段被高分分支覆盖。
3. **`Improve` 没有任何验证**（`operations.py:503-533`）⇒ 纯措辞改写后直接进 `Score` 排序，
   改坏了也只能靠分数被淘汰。
4. **`Thought.from_thought` 浅拷贝 state**（`thought.py:39-54`）⇒ 多个 Thought 共享同一 dict，
   原地修改会互相污染。
5. **无早停 / 无 max rounds / 无质量阈值** ⇒ 轮数写死在 `for _ in range(k)` 里，
   题目难度变化时不会自适应。
6. **每题只跑 1 次、`temperature=1.0`、无 seed** ⇒ **run-to-run 方差完全没被测**。
7. **不测"宽度/多样性"** ⇒ 整份归档里**没有任何一个指标**衡量图宽、角度数、信息覆盖度；
   "分 4 段/8 段/32 句"是**设计时写死的常量**，不是被测出来的量。

---

## 5. ★ 对我们项目的可迁移点

### 5.1 路线 A（固定拓扑）：**它就是路线 A 的一个成熟实现，可以直接抄骨架**

它的 `GraphOfOperations` + 9 个算子 = **一个"人写死拓扑"框架的标准答案**。
对我们路线 A 的直接价值：
- **算子契约**（`execute(lm, prompter, parser, **kwargs)` + `get_thoughts()`）可以作为我们
  GEN/EXTRACT/VERIFY/SPLIT/MERGE/STOP 的**统一签名草案**；
- **`Prompter` / `Parser` 分离**是很好的工程决策：算子只管"状态进出"，prompt 模板与解析各归各文件
  ⇒ 对我们的 DEV 集换判官（U4）很友好，**改判官不动拓扑**。

### 5.2 ★★★ 最值得抄的一条：**判据是"state 上的 Python 函数"，不是 prompt**

```python
Score(num_samples=1, combined_scoring=False,
      scoring_function: Callable[[Union[List[Dict], Dict]], Union[List[float], float]] = None)
```
3/4 个 benchmark 的判据就是 `utils.num_errors(state) -> float` —— **数错元素个数**，
**纯离散、纯可核验、完全不碰措辞相似度**。
⇒ 这直接命中我们的 **U3**：GoT 的 score 算子**可以是结构量**，而且它的实现方式是我们要的形态：
**把判据写成"吃 state dict 的函数"，而不是"让 LLM 打分"**。
⇒ 对我们的**测量协议**：我们的"承重信息核验"应该长成
`Callable[[State], float]`（或 `Callable[[State], bool]`），
这样它天然**可被依据包核验**，也天然**与 embedding/措辞无关**（绕开 U1/U2/U3）。

### 5.3 ★★ 第二值得抄的：**`valid_aggregation` —— 12 行的"承重性不变量检查"**

`examples/keyword_counting/keyword_counting.py:58-82`：

```python
def valid_aggregation(state: Dict) -> bool:
    aggr1 = json.loads(state["aggr1"]); aggr2 = json.loads(state["aggr2"]); current = json.loads(state["current"])
    if set(aggr1.keys()) | set(aggr2.keys()) != set(current.keys()):
        return False
    for country in current.keys():
        aggr1_freq = aggr1[country] if country in aggr1.keys() else 0
        aggr2_freq = aggr2[country] if country in aggr2.keys() else 0
        if aggr1_freq + aggr2_freq != current[country]:
            return False
    return True
```
**语义**：合并结果必须**恰好**包含两个输入的键集之并，且每个键上的量必须**等于两个输入之和**
⇒ **"合并不许丢承重信息"的机器可核验断言**。
⇒ ★★★ **这是"承重信息合并"最干净的实现范式**：
**合并 = 一次生成 + 一条结构不变量断言**，不是"再让 LLM 总结一次"。

### 5.4 ★ 第三值得抄的：**`Selector` 用 state 里的离散键做路由**

```python
operations.Selector(lambda thoughts, list_id=list_id:
    [t for t in thoughts if t.state["part"] == list_id])
```
路由键是 `"List 1"` / `"Paragraph 3"` / `"Sentence 17"` —— **离散、可归因、零 embedding、零措辞相似度**。
⇒ 我们的"维度拆分/分派"算子可以直接用这个形态：**给每个子任务打一个离散 ID，用 ID 做路由**。
⇒ 与我们已知的 U2（embo-01 中文句级几何无分辨率）**完全无关** ⇒ 天然绕开。

### 5.5 ★ "维度合成"算子能不能直接用 `Aggregate`？——**不能直接用，但外壳可以抄**

| GoT 的 Aggregate | 我们要的"维度合成" | 差距 |
|---|---|---|
| 把 k 个 state 的文本拼进 prompt，让 LLM 自由合并 | 把 k 条**承重信息**合成**一个可核验的结论** | **合并结果不校验**（`operations.py:563-609`） |
| `base_state` 按 score **覆盖**合并 | 应为**并集/受约束合成** | 覆盖 ≠ 合并（`:588-591`） |
| 合并后只 `Score` 排序 | 合并后要**断言承重性未丢** | 缺 `valid_aggregation` 那一步 |

⇒ **可抄的外壳**：`Aggregate → ValidateAndImprove(rule_based_validator) → Score → KeepBestN`
这**四元组 = "合成 + 承重性断言 + 打分 + 选优"**，
可以作为我们"维度合成算子"的**流水线**；
但要把中间那个**自由文本 LLM 合并**换成"**带依据包的结构化合成**"，
并把 validator 换成**我们自己的承重性不变量**（谁承重、在合成结果里还在不在）。

### 5.6 回溯/goback：**它没有实现 ⇒ 对我们的 L1 区分没有提供任何东西**

- 全仓 `grep -rni "goback|go_back|backtrack"` **0 命中**；
  `OperationType` 9 项里**没有** go-back 类算子。
- 代码里"看起来像回退"的三样东西，**没有一样是状态转移律**：
  1. `KeepBestN(n)` —— **末端选择器**（在已有分支里挑 n 个，不产生新状态、不改拓扑）；
  2. `Improve` / `ValidateAndImprove` —— **原地改写当前 state**，不回退到别的节点；
  3. 拓扑里**人写死**的"回到上一层再修一次"（如 `sorting_128.got()` 里的 `improve_aggregate_i` 节点）。
- ⇒ **GoT = 静态拓扑 + 末端选择器**。**评价信号从不决定"下一步去哪"**。
  ⇒ 对我们 **L1（状态转移律 vs 末端选择器）** 这条线，**GoT 站在"末端选择器"一侧**：
  它是**路线 A 的强基线**，但**不能**被当成"L1 已被实现"的正例。

### 5.7 优化器契约 L0–L4 的位置

| 契约层 | GoT 给了什么 |
|---|---|
| L0 目标函数 | ⚠️ **半个**。有 score（错误数 / 自评分），但**没有把它写成一个可优化的目标**，只是排序键 |
| **L1 状态转移律** | ❌ **没有**。转移是硬编码的算子 DAG，score **不进入任何转移决策** |
| L2 更新规则 | ❌ 没有（无梯度、无迭代改进） |
| L3 搜索/预算分配 | ❌ 没有（只有 §1.4 的美元预算截断） |
| L4 元优化 | ❌ 没有 |
| **可迁移的"正资产"** | ✅ **算子接口 + 判据回调 + 离散路由 + 承重性不变量**（§5.1–§5.4） |

### 5.8 DEV 集设计：能省我们什么

- **可以直接借用的题库**（都是"多中间结果相互依赖"型难题；**除 doc_merge 外都带程序化 ground truth**）：
  - `examples/keyword_counting/countries.csv` — **100 段文本**（国家频次，**有程序化 ground truth**）；
  - `examples/sorting/sorting_{032,064,128}.csv` / `set_intersection_*.csv` — 各 100 题（**有程序化 ground truth**）；
  - `examples/doc_merge/documents.csv` — **50 组 4 份 NDA**（带重叠条款，⚠️ **只有 LLM 自评分，没有 oracle**）。
- **能省掉的实验**：我们不必自己造"多路中间结果 + 需要合流"的 DEV 题
  ⇒ **可省掉一轮 DEV 集造题**（BRIEF 里"9 道题 + 装配器"的工作量可以少一半），
  且这些题**自带可核验 ground truth**，正好匹配我们"依据包可核验"的要求。
- ⚠️ 但注意：这些题**测的是"结果对不对"**，**不测"思维面宽不宽"** ⇒
  它们只能当我们的**任务层 DEV 集**，**不能**当我们的**维度测量集**（那还是得自己造）。
  ⚠️ 且 **doc_merge 没有 oracle**（只有 LLM 自评分）⇒ 用它做 DEV 题要另配 ground truth。

---

## 6. ★ 不可迁移 / 会误导我们的点

### 6.1 ⚠️⚠️ **U6 自评污染：doc_merge 直接命中，必须点名**

**代码证据链**（`examples/doc_merge/doc_merge.py`）：

```python
def io():
    operations_graph.append_operation(operations.Generate(1, 1))
    operations_graph.append_operation(operations.Score(3, False))   # ← 第 2 参数 False = combined_scoring
    #                                     ↑ 第 3 参数 scoring_function 缺省 = None ⇒ 走 LLM 打分
```
`Score._execute`（`operations.py:240-260`）在 `scoring_function is None` 时：
```python
prompt = prompter.score_prompt([thought.state])
responses = lm.get_response_texts(lm.query(prompt, num_responses=self.num_samples))  # num_samples=3
score = parser.parse_score_answer([thought.state], responses)[0]
```
而 `lm` 与生成用的是**同一个实例**：`language_models.ChatGPT(config.json, model_name="chatgpt")`
⇒ **`gpt-3.5-turbo` 生成合并稿，又给同一条合并稿打分**。

**打分协议**（`doc_merge.py:404-456`）：
1. prompt 要求输出 `<Redundancy>x</Redundancy>` 与 `<Retained>y</Retained>` 两个 0–10 分；
2. 采 **3 个样本**（`num_samples=3`）；
3. 各自取 3 个样本的**均值**（`fmean`）；
4. 最终分 = **两个均值的调和平均（F1）**：`2*r*m/(r+m)`。

**我用官方 prompt 日志手算验证过**（`examples/doc_merge/example_prompts_document_merging.md:963-1004`）：
```
<Redundancy>5</Redundancy> <Retained>10</Retained>     → 均值 r = (5+8+3)/3 = 5.333
<Redundancy>8</Redundancy> <Retained>10</Retained>
<Redundancy>3</Redundancy> <Retained>9</Retained>      → 均值 m = (10+10+9)/3 = 9.667
Overall Score (Harmonic Mean of Averages) = 6.87     ← = 2*5.333*9.667/(5.333+9.667) ✓
```

**⇒ 三重污染，必须点名**：
1. **判官 = 被测**（U6 原文命中）：同一个 gpt-3.5-turbo 既写答案又打分；
2. **选择器 = 判官**：`KeepBestN(3, True)` / `KeepBestN(1, True)` 用**这个自评分**挑分支
   ⇒ 被选中的分支天然是自评分最高的那个 ⇒ **winner's curse**；
3. **报的分数 = 选择用的分数**：`plots.py` 的 `get_final_scores_doc_merge` 取 `max(op["scores"])`，
   而这批 score 正是被 `KeepBestN` 用过的同一批数 ⇒ **选择与报告不独立**。

**⇒ 后果**：doc_merge 上"GoT 7.86 vs CoT 6.63"这个 +1.23 分的差，
**没有任何独立证据支撑**；它完全可能是"更长的输出更讨 LLM 喜欢"的自评偏差
（GoT 的 prompt 与输出都更长：GoT 平均 **35,912** prompt tok / **25,740** completion tok，
CoT 只有 **3,724** / **1,445** ⇒ **长度差 9.6×（prompt）与 17.8×（completion）**）。
⇒ ★ **这组数字对我们零可用性；且它恰好是 GoT 唯一"信息保留/覆盖"类的任务**。

**公允地补一句**：sorting / set_intersection / keyword_counting 三个 benchmark 的 score 是
**纯 Python 规则函数**，**不是 LLM 判官** ⇒ **它们的成功判据没有被自评污染**。
⇒ 结论不是"GoT 整体污染"，而是"**GoT 的第 4 个 benchmark 污染**"。

### 6.2 ⚠️ **"宽度/新颖性"指标：它根本没测 ⇒ 对我们是"反面教材"**

- 全仓**没有任何** embedding / 余弦 / 多样性 / 覆盖度指标（`grep -i embedding|cosine|diversity` 0 命中）。
- 好消息：**不吃 U2 的坑**（没用 embo-01 那类 embedding 余弦）。
- 坏消息：**它也压根没回答我们的问题**。GoT 的"思维面宽度"是**拓扑里写死的常量**
  （split 成 2 段 / 4 段 / 8 段 / 32 句），**不是测出来的量**。
  ⇒ ★★ **这正是 U7 的教科书级反面案例**：
  **"我把图搭得更宽"是设计选择，不是测量结果；宽出来的那些分支到底承不承重，代码从不检查。**
  ⇒ 对我们：**"拓扑宽度"不能当"有效信息维度数"的代理**（U7），
  这条从 GoT 的代码里可以直接读出来，不用查文献。

### 6.3 ⚠️ **等预算对照缺失 ⇒ "GoT 更好"与"GoT 更贵"完全混淆**

GoT 的 token 成本是 CoT 的 **3.8–17.2 倍**（§2.4），代码里**从来没有做过等预算/等 token 的对照**。
论文的图把分数和成本并排画，但**没有一条"在同等花费下谁更好"的曲线**。
⇒ 对我们 **主判据"净维度增益 = 工作流 − 直调 baseline"**：
**必须在等预算下测**，否则我们的"净增益"会变成"多花钱的收益"，正是我们要防的那个混淆。

### 6.4 ⚠️ **"best-of-graph" 口径 ⇒ 分支越多越占便宜**

`solved = any(op["problem_solved"])` + `score = min(op["scores"])` ⇒ 读数是**全图最优**。
ToT 分支 20、GoTx 拆 32 句、GoT 8 路 ⇒ 命中正确解的**采样次数天然更多**。
⇒ 我们的"净维度增益"如果用 "best-of-N" 口径衡量，**会被 N 的大小直接污染** ⇒ 必须区分
"单次运行的最终产出"与"全图最优"。

### 6.5 ⚠️ **统计上的三个洞**

1. **每题 1 次、temperature=1.0、无 seed** ⇒ 100 题的均值是**单次抽样**，
   **run-to-run 方差完全没有测**。我们的协议要求重复次数 ⇒ GoT 给了我们反面教材。
2. **截断样本**：`set_intersection_gpt35_128/tog` 只有 10 题（非随机前 10 题），
   `plots.py` 不补齐直接画 ⇒ **选择性偏差**。
3. **无显著性检验**：只有 boxplot，无误差棒、无 p 值、无"不可分辨"的报告。
   ⇒ 我们已知 **U4（跨判官 prompt 漂移 ⇒ 带宽 > 信号）**；
   GoT 连"跨判官漂移"这一步都没做，**更不用说报"不可分辨"**。
   ⇒ 对我们的启发：**"报告不可分辨"应当写进协议**，GoT 正好是反例。

### 6.6 其他工程坑（复刻时要改）

- `Thought.from_thought` 浅拷贝 state ⇒ 多 Thought 共享 dict（`thought.py:47`）。
- `Aggregate` 的 `base_state` 是**覆盖**不是合并（`operations.py:588-591`）。
- `KeepBestN.get_best_n()` 用 `except:` 裸捕获，异常时回退到"只保留 float 分数"
  ⇒ **静默改变语义**（`operations.py:655-668`）。
- `Score` 不校验 `parse_score_answer` 返回的长度是否等于 thought 数 ⇒ `zip` 会静默截断。
- `ChatGPT.query` 的重试逻辑 `next_try = (next_try + 1)//2` 会**减少样本数**
  ⇒ 失败重试后**分支数变少**却**不报错**（`chatgpt.py:83-98`）⇒ 结果不可比。
- `openai` SDK 版本锁 `<2.0.0`、`torch>=2.0.1` 等依赖已相当老（`pyproject.toml`）。

---

## 7. 逐字摘录（可引用原话）

> **① 拓扑是静态的**
> "The Controller class is responsible for traversing the Graph of Operations (GoO), which is a **static structure that is constructed once, before the execution starts**."
> —— `graph_of_thoughts/controller/README.md:3`

> **② Aggregate 的 base_state 是"按分数覆盖"**
> ```python
> # applied in order of score
> base_state: Dict = {}
> for thought in sorted(previous_thoughts, key=lambda thought: thought.score):
>     base_state = {**base_state, **thought.state}
> ```
> —— `graph_of_thoughts/operations/operations.py:588-591`

> **③ doc_merge 的评估方式：自评**
> ```python
> """
> Input (x1, x2, x3, x4): Four NDAs
> Output (y): A new combined NDA
> Evaluation: According to information coverage without repetition (scored by the LLM)
> """
> ```
> —— `examples/doc_merge/doc_merge.py:755-760`

> **④ 分数必须先被算出来才能选**
> ```python
> assert all(
>     previous_thought.scored for previous_thought in previous_thoughts
> ), "Not all thoughts have been scored"
> ```
> —— `graph_of_thoughts/operations/operations.py:645-647`

> **⑤ 官方打分口径：全图最优 + 任一命中**
> ```python
> score = min(op["scores"])
> solved = any(op["problem_solved"])
> ```
> —— `paper/plots.py:49-50`

---

## 8. 读完后我自己的一句判断

**最值得抄的是"判据的形状"，不是"图"**：
GoT 真正的设计遗产是 **`scoring_function: Callable[[State], float]`** 这个签名 ——
判据吃的是 **state dict**，输出一个离散数，**与措辞、与 embedding 完全无关**；
再加上 `valid_aggregation` 那种**"合并后必须等于输入之和"的结构不变量**，
以及 `Selector` 用**离散 ID** 做路由。
⇒ 这三件拼起来正好是**我们"承重信息维度"的机器可核验骨架**：
**"拆成带 ID 的子问题（Selector）→ 各解（Generate）→ 结构量打分（Score(fn)）→
带不变量断言的合成（Aggregate + validator）→ 选优（KeepBestN）"**。
⇒ 而且它**天然绕开 U1/U2/U3**：全程不碰 embedding、不碰措辞相似度。

**最容易骗我们的是"图"这个字眼**：
GoT 看起来是"让 LLM 在图上自由探索"，但代码里 **图宽是写死的常量、转移是写死的 DAG、
评价信号只用于末端排序** ⇒ **它既没有测宽度（U7 的反面教材），也没有状态转移律（不占我们 L1）**。
而且它唯一"信息保留"类任务的成绩（doc_merge）**是同一个模型自己打的分**（U6 正面命中，
还叠加了 winner's curse 与 5–14 倍的长度差）⇒ **那组数字我们一条都不能用**。
⇒ ★ 我们的教训：**"搭出一张更宽的图"不等于"思维面更宽"**；
而要证明后者，**必须有一个与图宽无关的、能被依据包核验的量** ——
GoT 全程没有这个东西，这正是我们要补的位置。

---

## 附：来源清单

> 全部访问日期：**2026-10-21**。仓库默认分支 `main`，最新 commit `3d9d9dbd8937d47a4441f681b8b40e3c5b054f16`。
> 下载方式：`https://api.github.com/repos/spcl/graph-of-thoughts/git/trees/HEAD?recursive=1` 取树 +
> `https://raw.githubusercontent.com/spcl/graph-of-thoughts/main/<path>` 取文件。
> 本地落盘：`/workspace/lab/routes/LIT/_raw/got/`（源码 `raw/`、官方结果 `results/`、我的复算脚本 `analyze.py` / `simulate.py` / `count_ops.py` / `call_counts.txt` / `analysis.txt`）。

**仓库元信息**
- `https://api.github.com/repos/spcl/graph-of-thoughts`（默认分支、star 数、创建/推送时间）
- `https://api.github.com/repos/spcl/graph-of-thoughts/git/trees/HEAD?recursive=1`（完整文件树，49 个 blob）
- `https://github.com/spcl/graph-of-thoughts`（README、Quick Start、引用格式）
- `https://raw.githubusercontent.com/spcl/graph-of-thoughts/main/README.md`
- `https://raw.githubusercontent.com/spcl/graph-of-thoughts/main/LICENSE`（BSD-3 风格，ETH Zurich 2023）
- `https://raw.githubusercontent.com/spcl/graph-of-thoughts/main/pyproject.toml`（v0.0.3、依赖版本）

**核心框架**
- `raw/graph_of_thoughts/operations/operations.py`（算子实现，900 行）★
- `raw/graph_of_thoughts/operations/thought.py`（Thought 数据结构）★
- `raw/graph_of_thoughts/operations/graph_of_operations.py`（GoO 容器）★
- `raw/graph_of_thoughts/operations/README.md`（算子参数文档）
- `raw/graph_of_thoughts/controller/controller.py`（执行循环、output_graph）★
- `raw/graph_of_thoughts/controller/README.md`（★ "static structure" 原话）
- `raw/graph_of_thoughts/prompter/prompter.py`、`raw/graph_of_thoughts/parser/parser.py`（抽象接口）
- `raw/graph_of_thoughts/language_models/abstract_language_model.py`
- `raw/graph_of_thoughts/language_models/chatgpt.py`（★ 全部 API 参数与重试逻辑）
- `raw/graph_of_thoughts/language_models/llamachat_hf.py`
- `raw/graph_of_thoughts/language_models/config_template.json`（★ 默认超参全表）
- `raw/graph_of_thoughts/language_models/README.md`

**examples / 评估代码**
- `raw/examples/sorting/sorting_032.py`、`sorting_064.py`、`sorting_128.py` ★（GoT/ToT/ToT2 拓扑）
- `raw/examples/sorting/utils.py`（`num_errors`、`test_sorting`）★
- `raw/examples/sorting/README.md`
- `raw/examples/set_intersection/set_intersection_{032,064,128}.py`、`utils.py`、`README.md`
- `raw/examples/set_intersection/dataset_gen_intersection.py`（`seed = 42`）
- `raw/examples/keyword_counting/keyword_counting.py`（★ `valid_aggregation`、`got4/got8/gotx`）★
- `raw/examples/keyword_counting/dataset_gen_countries.py`、`README.md`
- `raw/examples/doc_merge/doc_merge.py`（★ LLM 自评打分路径）★
- `raw/examples/doc_merge/example_prompts_document_merging.md`（★ 官方 prompt/response 日志，2634 行；我手算验证 6.87 的出处）
- `raw/examples/README.md`
- `raw/paper/plots.py`（★ 官方打分与出图逻辑）★
- `raw/paper/README.md`
- `paper/final_results_gpt35.tar.bz2` ← `https://raw.githubusercontent.com/spcl/graph-of-thoughts/main/paper/final_results_gpt35.tar.bz2`（★ 6,499,375 B，解包 656MB，4162 个结果 json）

**我自己的复算脚本（可复跑）**
- `/workspace/lab/routes/LIT/_raw/got/analyze.py` → `analysis.txt`（按 `plots.py` 逻辑重算全部准确率/成本/token）
- `/workspace/lab/routes/LIT/_raw/got/simulate.py` → `call_counts.txt`（用真实 operations/controller + mock LLM 统计 API 调用次数）
- `/workspace/lab/routes/LIT/_raw/got/count_ops.py`（逐 op 打印结果 json 的 op 序列与 thought 数）
- `/workspace/lab/routes/LIT/_raw/got/_stubs/`（openai / backoff / torch / transformers 的最小桩，仅为离线跑 simulate.py）

**未取到 / 未做的事**
- ❌ **没有跑通真实 API**（无 OpenAI key；且无 `config.json`），因此所有成本数字来自**官方发布的原始结果**，而非我的重跑。
- ❌ **没有跑 Llama-2 变体**（需 GPU + HF 权重 + `llama*-hf` 配置），故 §2 全部是 GPT-3.5 口径。
- ❌ **未复现论文的图**（`plots.py` 需 `matplotlib`，且缺 `document_merging_gpt35_16k` 等目录的完整同版本对齐）；我用等价脚本重算了全部读数。
- ❌ **论文正文/ Limitations 未读**（分工给另一组）；本文件 §4 的"局限"全部标注为**代码可见事实**，不是作者原话。
- ⚠️ **发布结果与当前 HEAD 不同版本**（op 名 `combine` vs `aggregate`；方法目录名 `tog/gsp*` vs 代码里的 `got*`）⇒ §2 数字**不能保证由当前 HEAD 逐位复现**。
