# 08 — 官方实现：spcl/graph-of-thoughts

> 这不是一篇论文，是 GoT（见 07）的**官方代码库**。按"读 README + 目录树 + 入口函数 + 默认超参"的要求精读。
> 源码来源：`git clone --depth 1 https://github.com/spcl/graph-of-thoughts.git`（本会话实际 clone 到 `.work/got_repo`，逐文件读过）
> 论文对应：arXiv:2308.09687（见 `07_2308.09687.md`）

---

## 0. 引用
- **标题 / 身份**：Graph of Thoughts (GoT) —— 官方实现仓库（README 首行："This is the official implementation of Graph of Thoughts: Solving Elaborate Problems with Large Language Models"）
- **作者 / 组织**：ETH Zurich, Scalable Parallel Computing Lab (SPCL)；作者同 07 篇（Besta, Blach, Kubicek, Gerstenberger, Podstawski, Gianinazzi, Gajda, Lehmann, Niewiadomski, Nyczyk, Hoefler）
- **年份**：仓库随 2023-08 论文发布并持续维护（含 `main` 分支上的 `graph_of_thoughts` 包化版本）
- **venue**：N/A（软件仓库）；**License：BSD-style**（源码头注释："You can redistribute it and/or modify it under the terms and conditions of the BSD-style license which can be found in the LICENSE file."）
- **arXiv id**：论文 arXiv:2308.09687
- **一句话**：它声称——**把"用哪种 prompting 范式"从代码里解耦成一个可插拔的静态操作图（GoO）**，你只要写 `Prompter` / `Parser` / 一个打分函数，就能复用同一套引擎跑 CoT / ToT / GoT。

---

## 1. 核心机制（具体到能照着实现）

| 项 | 内容 |
|---|---|
| **输入** | 任务题面（排序例子是一个 `[0, 2, 6, 3, ...]` 的字符串列表）+ **一个 dict 形式的初始 thought state**：`{"original": to_be_sorted, "current": "", "phase": 0, "method": "got"}`。 |
| **状态表示** | `Thought` 对象（`graph_of_thoughts/operations/thought.py`）= 一个 dict 载荷 + 元数据（`state`、`scored`、`score`、`validated`、`valid`、`solved`）。<br>**GRS（Graph Reasoning State）** 是运行时状态：`operation.executed` 标志 + 每个 operation 持有的 `thoughts` 列表。 |
| **动作/算子** | **9 个 Operation 类**（`operations/operations.py`），`OperationType` 枚举：<br>`score`(0) / `validate_and_improve`(1) / `generate`(2) / `improve`(3) / `aggregate`(4) / `keep_best_n`(5) / `keep_valid`(6) / `ground_truth_evaluator`(7) / `selector`(8)。<br>每个 Operation 有 `predecessors` / `successors` / `executed`；`can_be_executed()` = 所有 predecessor 都已执行。 |
| **过程/回路** | `GraphOfOperations`（`operations/graph_of_operations.py`）提供两种挂载方式：<br>• `append_operation(op)`：**串行**，自动把 op 接到当前所有 leaf 之后（leaf 集合收缩为 [op]）——即 `GoT` 的线性主干。<br>• `add_operation(op)`：**并行分支**，需要显式 `add_predecessor(...)` 来接边；`roots`/`leaves` 自动维护。<br>`Controller.run()`：`while len(execution_queue) > 0:` —— 取出当前 operation 执行，把它的 successors 入队。**拓扑序、一次过、跑完即止**。 |
| **输出** | `ctrl.output_graph("output_got.json")` → 一个 JSON，含**每个 operation** 的：`type` / `thoughts`（每条含 `state` / `scored` / `score` / `validated` / `valid` / `solved`）/ `cost` / `total_tokens`。**这就是"依据包"的现成形状。** |
| **谁来评价** | 打分由 `Score` 承载，可选三种：<br>• `scoring_function`（**本地 Python 函数**，如 `utils.num_errors`）——**首选**；<br>• LLM 打分（`combined_scoring` + prompter/parser 路径）；<br>• `GroundTruth(fn)`（与预计算答案比对，返回 `solved` 标志）。<br>**信号不回传搜索**：`Score` 只填 `thought.score`；`KeepBestN` 靠它排序取 top-n；没有任何参数更新。 |

**目录树（实测）**
```
graph_of_thoughts/
  controller/     controller.py + README.md   # 遍历 GoO，维护 GRS
  language_models/ chatgpt.py, llamachat_hf.py, abstract_language_model.py, config_template.json
  operations/     operations.py (9 个 op), graph_of_operations.py, thought.py + README.md
  parser/         parser.py
  prompter/       prompter.py
examples/
  sorting/        sorting_032.py sorting_064.py sorting_128.py utils.py plot.py + prompts
  set_intersection/ set_intersection_032/064/128.py utils.py dataset_gen_intersection.py + prompts
  keyword_counting/ keyword_counting.py countries.csv dataset_gen_countries.py + prompts
  doc_merge/      doc_merge.py documents.csv pure_documents.json + prompts
paper/
  final_results_gpt35.tar.bz2   # 论文用的原始结果
  plots.py, pics/preview.svg
```
- **安装**：`pip install graph_of_thoughts`（PyPI）或 `pip install -e .`（源码）；要求 **Python ≥ 3.8**。

**入口函数（`examples/sorting/sorting_032.py` 的 `got()`）**
```python
plans = operations.Generate(1, 1)                      # 拆子列表
for i in range(1, 3):                                   # 2 个子列表
    sub_list = operations.Selector(lambda ...: 按 state["part"]=="List i" 过滤)
    sort_sub_list = operations.Generate(1, 5)            # 每个子列表生成 5 个排序候选
    score_sub_list = operations.Score(1, False, utils.num_errors)
    keep_best_sub_list = operations.KeepBestN(1, False)
final_aggregate = operations.Aggregate(10)               # 合并
operations_graph.append_operation(operations.Score(1, False, utils.num_errors))
operations_graph.append_operation(operations.KeepBestN(1, False))
operations_graph.append_operation(operations.Generate(1, 10))   # 合并后再生成 10 个
operations_graph.append_operation(operations.Score(1, False, utils.num_errors))
operations_graph.append_operation(operations.KeepBestN(1, False))
operations_graph.append_operation(operations.GroundTruth(utils.test_sorting))
```
> ⚠️ 注意：这条 GoO **完全是手写的**——拓扑、每个 op 的 k 值、合并层数，全是人写死的常量。**仓库里没有任何"搜索/学习拓扑"的代码。**

**默认超参（`graph_of_thoughts/language_models/config_template.json`，逐字）**
| key | model_id | temperature | max_tokens | prompt $/1k tok | response $/1k tok |
|---|---|---|---|---|---|
| `chatgpt` | `gpt-3.5-turbo` | 1.0 | 1536 | 0.0015 | 0.002 |
| `chatgpt4` | `gpt-4` | 1.0 | 4096 | 0.03 | 0.06 |
| `llama7b-hf` | `Llama-2-7b-chat-hf` | 0.6 | 4096 | 0.0 | 0.0 |
| `llama13b-hf` | `Llama-2-13b-chat-hf` | 0.6 | 4096 | 0.0 | 0.0 |
| `llama70b-hf` | `Llama-2-70b-chat-hf` | 0.6 | 4096 | 0.0 | 0.0 |
（llama 额外 `top_k: 10`；`stop: null`；`cache_dir`）

**默认打分函数（`examples/sorting/utils.py::num_errors`，逐字逻辑）**
- 频次偏差：`for i in range(10): err += |count_current(i) - count_correct(i)|`
- 逆序对：`err += count(zip(current, current[1:]) if n1 > n2)`
- **异常时 `return 300`**（= 一个封顶的错误数）—— 静默把解析失败当成"很错"。

**论文 Appendix F 的 GoO 配置（32/64/128 集合求交）**
- `Generate(k=1)` 把第二个集合切成 **2 / 4 / 8 份**（每份 16 元素）→ 每份 `Generate(k=5)` → `Score(k=1)` → `KeepBestN(1)` → 逐级 `Aggregate(10)` + `Score` + `KeepBestN` → 末级 `Aggregate(10)` → `GroundTruth()`。
- ⚠️ 元素数 32/64/128 变了，**切分份数和合并层数就变** ⇒ 拓扑是**手工按题规模特调的**，不是学出来的、也不是自动适配的。

---

## 2. 关键数字

- **代码本身不报数字**；论文的读数在 07 篇。
- 可从代码读出的**结构性数字**：
  - sorting-032 的 GoO：`Generate(1,1)` → 2×(`Generate(1,5)`→`Score`→`KeepBestN(1)`) → `Aggregate(10)` → `Score`→`KeepBestN` → `Generate(1,10)` → `Score`→`KeepBestN` → `GroundTruth`。
    ⇒ **单臂一次推理的 LLM 调用数上限 ≈ 1×1 + 2×5 + 10 + 10 = 31 次**（不含 Score/GroundTruth，它们在本题用本地函数，不调 LLM）。
  - set_intersection-32：`Generate(1)` + 2×(`Generate(5)`) + `Aggregate(10)` ⇒ **≈ 21 次**；-64：4×5 + 3×10 = **50**；-128：8×5 + 7×10 = **110**。
    ⇒ ★ **题规模翻倍，调用数大致翻 2.5–3 倍。** 这就是"工作流臂"在成本上的真实量级，直接关系到我们能不能做**等预算配平**。
  - `num_errors` 的上限/封顶 = 300（异常路径）。
- 仓库带 `paper/final_results_gpt35.tar.bz2`（论文原始结果包）与 `plot.py`（4 个用例的画图脚本）。

---

## 3. ★ 它的「成功标准」是什么

- **代码层面没有成功标准**——引擎只管执行。成功与否完全由**注入的打分函数 + `GroundTruth`** 决定。
- **库设计上最值得学的一点：判据是 plug-in 的外部函数**（`Score(1, False, utils.num_errors)`），不是引擎内置的 LLM 评分。⇒ **判据与被测天然不同源。**
- **否证条件**：库不提供。`GroundTruth` 只给 `solved` 的 True/False，**不参与任何分支决策**（看 `controller.py`：`thought.solved` 被写进输出 JSON，但**没有 operation 读它来提前终止**）——即"做对了"不触发"停"。**停止 = 拓扑跑完。**
- **不可分辨**：库不处理。没有任何重复采样/方差/噪声地板机制。

---

## 4. 自认的局限（原话优先）

> 来自 README 与源码注释的作者自述：
- README：**"The framework gives you the ability to solve complex problems by modeling them as a Graph of Operations (GoO), which is automatically executed with a Large Language Model (LLM) as the engine."** —— 引擎只执行固定计划。
- Controller README：**"GoO prescribes the execution plan of thought operations and the Controller invokes their execution, generating the Graph Reasoning State (GRS)."** —— **执行计划是规定好的**，不是被搜出来的。
- Controller README：**"After the run the graph is written to an output file, which contains individual operations, their thoughts, information about scores and validity and total amount of used tokens / cost."** —— 这句直接定义了我们要的"依据包"里应该有什么。
- 源码（`num_errors`）：`except: return 300` —— 解析失败被静默折算成错误数。

---

## 5. ★ 对我们项目的可迁移点

**映射：路线 A（固定拓扑）—— 这是本篇对我们的直接价值**

- **★ 整个仓库就是"路线 A"的最小完整实现**，而且实现得相当干净。我们的路线 A 臂如果重写引擎，**这个仓库可以当参考实现**（BSD license，可直接借鉴/移植）。
  - `Controller.run()` 的拓扑序遍历 + `GraphOfOperations.append/add_operation` 的图装配 = 路线 A 的"拓扑执行器"。
  - `Operation` 的 `predecessors/successors/executed/can_be_executed()` = 路线 A 需要的"操作依赖 + 门控"。
- **★ 能省我们哪个实验**：省掉"**手写静态拓扑的执行引擎**"的工程量（我们不用再写调度器）。**更重要的是它给了一个"拓扑成本函数"的现成口径**：每个 op 声明它会调几次 LLM（`Generate(k)` ⇒ k 次、`Aggregate(10)` ⇒ 1 次但 prompt 变长、`Score` 用本地函数 ⇒ 0 次），我们可以用同样的方式**把拓扑折算成调用数/token**，从而做**等预算配平**（这正是 07 篇最大的漏洞）。
- **★ `GRS` 导出格式可以当我们的"依据包" schema 参考**：
  `operation → [thought → {state, scored, score, validated, valid, solved}]` + `cost` + `total_tokens`。
  我们的"承重信息"只需再加一个字段（如 `load_bearing: bool` + `justification`），**其余（算子、状态、依赖、有效性、成本）完全可复用**。
- **★ `Score` 用 plug-in 本地函数 = 我们治 ⑥（自评污染）的现成做法**。
- **DEV 集 / 噪声地板 δ**：仓库**不提供**。但它提供了 `paper/final_results_gpt35.tar.bz2` —— 一个"逐样本 × 逐 operation × 逐 thought（含 score/cost/token）"的原始结果包。**可以拿它当"如何导出可复核证据"的样板**（不是数据源，题域是排序）。
- **优化器契约 L0–L4**：这个仓库**只有 L0（静态拓扑）+ L1（执行）**。`operations.py` 里**没有任何"根据反馈改变下一步做什么"的逻辑**。⇒ 它是**"只有目标函数（打分）没有更新/搜索规则"的教科书案例**——正好是我们 ⑤ 缺的那一块的反面教材。

---

## 6. ★ 不可迁移 / 会误导我们的点

1. **★ 它没有"搜索"，所以它的"图"不能当"学到的工作流"来引用。**
   它的 GoO 是**常量**：`Generate(1,5)` 里的 5、`Aggregate(10)` 里的 10、集合求交里"32 元素切 2 份、64 切 4 份、128 切 8 份"，**全是人按题规模手调的**。
   → 引用它来支持"路线 B/C 的学出来的拓扑有效"是**无效的**；它只能支持"**人写死的拓扑**也能赢"。

2. **★ 它的 "Ag?"（arbitrary graph）能力是纸面的，代码里根本没有真正的"任意图"操作。**
   9 个 op 里能产生多入边的只有 `Aggregate`；`Improve` 是自环（`E⁺={(v,v)}`）；**没有任何 op 能表达"从图中删除节点/边"**——论文 §3.2 明写支持 `V⁻/E⁻` 删除，**但 `operations.py` 里没有实现删除**。
   → 论文的"任意图"是**理论表述**，落地的是**一个固定的 3 层 DAG 模板**。我们的 07 篇笔记如果照抄"图"这个词而不去读代码，会高估它的表达力。

3. **★ `GroundTruth` 不控制终止 ⇒ 成功信号与停止条件脱钩。**
   `thought.solved` 只写进输出 JSON，**没有任何 operation 读它来决定是否继续**。做对了也要把预算烧完。
   → 我们的"净维度增益"必须有**早停**（否则同样的信号、不同拓扑，信号会因为"多跑"而虚高）——这正是我们 ④ 测量带宽问题的解药：**早停 + 预算封顶必须同时定**。

4. **★ 判据载体问题（模板第 6 节专门检查）**：
   - `num_errors` / `test_sorting` 是**纯计数函数**，**没有 embedding，没有措辞相似度**。✅ 对我们无害。
   - 但 `doc_merge` 的打分是**问 LLM 要 0–10 分**（3 次取平均再取调和平均）——**这是同源自评**，会污染那个用例的读数。我们如果照这个模式做"哪些信息承重"的判官，**等于把 ⑥ 引进架构**。
   - `Selector` 的过滤条件是 `thought.state["part"] == "List i"` —— **结构化字段匹配**，也是干净的。

5. **★ 成本量级不可忽略**：`Generate(1,10)` + `Aggregate(10)` 这类 op **每次的 prompt 长度远大于普通 CoT 一步**。`config_template.json` 里 1536/4096 的 `max_tokens` 说明单次生成是长的。
   → 我们做等预算配平时，**不能只数"调用次数"**，必须用**实际 token**（仓库已经帮我们记了 `total_tokens` 和 `cost`）。**这是它给我们最实用的一个可执行物。**

6. **"偏差"风险：GoT 排序用的 baseline 之一是 `cot`，其 GoO 在同一份 `sorting_032.py` 里也是手写的**——也就是说，**"CoT vs GoT"的差 = 两份手写 GoO 的差，不是"方法"的差**。我们若要引用"图 vs 链"，必须说清是**在同一人写拓扑空间内的两个具体手写拓扑之间的差**。

---

## 7. 逐字摘录

> **`graph_of_thoughts/controller/README.md`**
> "GoO prescribes the execution plan of thought operations and the Controller invokes their execution, generating the Graph Reasoning State (GRS)."

> **`graph_of_thoughts/controller/README.md`**
> "After the run the graph is written to an output file, which contains individual operations, their thoughts, information about scores and validity and total amount of used tokens / cost."

> **`examples/sorting/utils.py::num_errors`**
> `except: return 300`

> **`examples/sorting/sorting_032.py::got()`**（结构，见上文代码块）
> `final_aggregate = operations.Aggregate(10)` / `operations_graph.append_operation(operations.Generate(1, 10))`

---

## 8. 读完后我自己的一句判断

**最值得抄**：**`output_graph()` 的 GRS 导出 schema（op → thought → {state, score, valid, solved} + cost + total_tokens）**——这几乎就是我们"依据包"该长的样子，而且它**已经把成本记在每条边上**了。配上 `Score` 的 plug-in 本地函数，就能同时解决我们的 ③（判据载体是结构不是措辞）和 ⑥（判官不同源），并顺带给我们做**等预算配平**所需的口径。

**最容易骗我们**：**"图"这个词。** 代码里能表达多入边的只有 `Aggregate` 一个 op，删除操作根本没实现，拓扑全是**按题规模手调的常量**。如果我们读完论文（07）就以为"GoT 证明了任意图拓扑有效"，会直接抄一个**它自己没实现的东西**——而我们要做的恰恰是"**拓扑从哪来**"（路线 B/C）。
