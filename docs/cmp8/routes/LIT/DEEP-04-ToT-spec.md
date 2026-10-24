# DEEP-04 · Tree of Thoughts → 「思维面 = 有效信息维度数」可抄规格

> **来源**：arXiv `2305.10601` v2（Yao, Yu, Zhao, Shafran, Griffiths, Cao, Narasimhan；NeurIPS 2023）+ `princeton-nlp/tree-of-thought-llm` HEAD `8050e67`。
> **逐字引文与行号**：全部在 `DEEP-04-ToT-quotes.md`。本文只写"抄什么 / 怎么改 / 为什么"。
> **本文所有数字**：要么是论文原文，要么是我用官方发布日志反算（已标"实测"）。凡未取到的一律写"未取到"。

---

## 0. 三个零件的一句话结论（先看这个）

| 我们要的东西 | ToT 里的对应物 | 抄不抄 | 一句话 |
|---|---|---|---|
| ① 中间状态做成**可枚举离散对象** | `state_key`（Game 24 = 剩余数字多重集；Crosswords = 棋盘+status） | **抄（核心）** | 关键不是"thought 是一段文本"，而是 **状态被投影成一个可哈希的键**，评估只吃这个键。 |
| ② 配一个"**这个状态值多少**"的评估器 | `value`（`sure/likely/impossible` → 数值） | **抄结构，不抄数值** | 抄"末行标签 + 多次采样 + 聚合"；**不抄** `{'impossible':0.001,'likely':1,'sure':20}`（作者自己标 `# TODO: ad hoc`）。 |
| ②' 另一种评估器 | `vote`（多选一，多数票） | **抄结构，修解析** | 抄"一次调用看全部候选 + 多次独立投票 + 计数"；**必须修**贪婪正则和越界静默丢票。 |
| ③ 同预算 best-of-k 对照 | Fig 3(a) | **抄方法，不抄轴** | 论文的轴是"**节点数**"，不是钱。**节点轴在成本上不等价**（见 §5.3）——我们必须换成 $ 轴。 |

---

## §1 离散状态的可抄定义

### 1.1 ToT 原来的（要抄的机制）

论文 p.3：`each node is a **state** $s = [x, z_{1 \cdots i}]$ representing a partial solution with the input and the sequence of thoughts so far.`

代码里 state 就是**一个字符串**，子节点 = 父串 + 新思路 + `'\n'`（`src/tot/methods/bfs.py:34-37`）。
**真正值得抄的不是字符串，是"状态投影"**：

```python
# src/tot/tasks/game24.py:9-11
def get_current_numbers(y: str) -> str:
    last_line = y.strip().split('\n')[-1]
    return last_line.split('left: ')[-1].split(')')[0]
```
```python
# src/tot/tasks/game24.py:75-83  —— 评估器只吃投影，不吃路径
    @staticmethod
    def value_prompt_wrap(x: str, y: str) -> str:
        last_line = y.strip().split('\n')[-1]
        if 'left: ' not in last_line:  # last step
            ans = last_line.lower().replace('answer: ', '')
            return value_last_step_prompt.format(input=x, answer=ans)
        current_numbers = get_current_numbers(y)
        return value_prompt.format(input=current_numbers)
```

⇒ **三个可抄的要点**：
1. **state_key 是路径无关的**（只由当前局面决定）⇒ 同一个 `state_key` 的两条路径得到同一个分 ⇒ 天然去重。
2. **state_key 是闭集可枚举的**（Game 24 = 剩余数字多重集；Crosswords = 10 个线索各自的字母约束）⇒ "维度数"可数。
3. **`value_cache` 以 `value_prompt` 字符串为键**（`bfs.py:6-14`）⇒ 相同投影的状态共享评估结果，**成本直接降一个量级**（实测：b=5 每题被打分 84.1 次，但去重后只有 **70.1** 个不同状态）。

### 1.2 我们的版本（可直接抄进代码）

```python
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

# ---------- 状态：可枚举离散对象 ----------
@dataclass(frozen=True)
class StateKey:
    """
    一个"思维面状态"的离散投影。闭集、可哈希、与路径无关。
    维度（dimension）= 本对象中已激活的轴集合。
    例：StateKey(axis_ids=(0, 2, 5), tags=("高成本",))  ⇒ 3 个有效维度
    """
    axis_ids: tuple            # 已激活的"信息轴"编号（升序，元组 ⇒ 天然去重）
    tags: tuple = ()           # 离散标签（如证据等级/风险级别），排序固定

    def canon(self) -> str:    # 序列化键：跨进程/跨缓存必须稳定
        return f"{','.join(map(str, self.axis_ids))}|{','.join(self.tags)}"

    @property
    def n_dims(self) -> int:   # 有效信息维度数
        return len(self.axis_ids)


@dataclass
class ThoughtNode:
    node_id: str                       # 全局唯一（run_id + 序号）
    state: StateKey                    # ① 离散状态
    thought_text: str                  # ② 这一步的自然语言理由（可读、可喂回 LLM）
    parent_id: Optional[str] = None
    depth: int = 0
    # ③ 评估结果（见 §2/§3）
    label_counts: Dict[str, int] = field(default_factory=dict)   # ← 关键：保留原始标签计数
    value: Optional[float] = None
    value_map_id: Optional[str] = None    # 记录用哪张映射表算出来的
    votes: Optional[int] = None
    eval_model: Optional[str] = None
    eval_samples: Optional[List[str]] = None
    # ④ 溯源
    parent_state: Optional[str] = None
    n_children: int = 0
```

**序列化格式（JSONL，一行一个节点，字段名与上面一致）**：

```jsonl
{"node_id":"r7-0041","state":{"axis_ids":[0,2],"tags":["低成本"]},"thought_text":"……","parent_id":"r7-0033","depth":2,"label_counts":{"sure":2,"likely":1},"value":3.0,"value_map_id":"map_v1","votes":3,"eval_model":"judge-A","eval_samples":["…","…"]}
```

**三条硬规则**（对应 ToT 的隐式行为，我们显式化）：
- `StateKey.canon()` 相同 ⇒ **同一个维度**（去重、缓存、投票都按它聚合）。
- `state.axis_ids` 必须来自**预先声明的闭集轴表**（否则"维度数"不可数）。
- `label_counts` **必须保留原始标签计数**，不要像 ToT 那样在解析时就把数值乘死（见 §2.4）。

### 1.3 从"b"到"维度数"的关键澄清（必须写进我们的文档）

**ToT 的 `b` 不是分支数，也不是维度数。**
README 明说：`--n_select_sample`: `number of states to keep from each step (i.e. b in the paper's ToT + BFS algorithm)`。
- `b` = **每步保留几个状态**（beam width）。
- 真正的分支因子 = 每个父状态生成几个想法，**实测**（官方 b=5 日志，每步 `len(new_ys)/len(ys)`）：

| 步 | 每父状态生成想法数（均值） |
|---|---|
| step0 | 9.47 |
| step1 | 6.36 |
| step2 | 4.09 |
| step3 | 4.48 |

- ⇒ "b=1→45%、b=5→74%" 的正确读法是：**"每步留 1 个 vs 留 5 个状态，成功率 45%→74%"**，中间还顺带把节点数从 ~20 拉到 ~66（Fig 3(a) 实测反算）。
- ⇒ **绝对不能读成"多开 4 个维度就 +29pp"**。我们自己的"维度数"必须用 `StateKey.n_dims` 定义，且**必须报告每次扩维带来的净增维度数**（见 §4）。

---

## §2 value 评估器（状态值评估）

### 2.1 提示词全文（照抄 ToT 的骨架，标签换成我们的）

ToT 原文（`src/tot/prompts/game24.py:66-105`，8 条示例）——**结构照抄，示例内容换成我们的领域**：

```
Evaluate if given numbers can reach 24 (sure/likely/impossible)
10 14
10 + 14 = 24
sure
11 12
11 + 12 = 23
12 - 11 = 1
11 * 12 = 132
11 / 12 = 0.91
impossible
...
{input}
```

**ToT 提示词骨架的三个可抄要点**：
1. **先给标签集**（`sure/likely/impossible`）⇒ 模型输出空间被压到 3 个。
2. **示例是"局面 + 推理 + 标签"三段式**，标签在**最后一行**。
3. **"我做不到"也必须打标签**（`I cannot obtain 24 now, but numbers are within a reasonable range` → `likely`）⇒ 避免模型输出自由文本。

我们的版本（骨架相同，标签改 4 档，示例给"证据等级"）：

```
Evaluate if the given information set can support a non-trivial answer (certain/likely/unsupported/contradicted).
<状态投影的键与内容>
<reasoning 一到两句>
<label>
...
{input}
```

⚠️ **必须与代码对齐的坑**：ToT 论文正文写 `sure/maybe/impossible`（PDF p.6），**代码写 `sure/likely/impossible`**（`prompts/game24.py:66`），而 `value_map` 的键是 `'likely'`（`tasks/game24.py:90`）。
⇒ **若照论文写 `maybe` 而保留代码的 `value_map`，每一次评估都会落到 0.001**。我们的实现里 label 与 map 必须在同一处定义（见 2.3）。

### 2.2 输出 schema

```jsonc
{
  "raw": "……推理……\ncertain",      // 原始文本
  "label": "certain",                // 归一化后的标签（解析结果）
  "parsed": true                     // false ⇒ 走失败处理
}
```
解析规则（**我们比 ToT 严格**）：
1. 取**最后一个非空行**（ToT 用 `_.split('\n')[-1]`，不做 strip ⇒ 尾随空格就解析失败）。
2. `strip()` → 去尾部 `.`/`。`/`,` → `lower()`。
3. 匹配 `^(certain|likely|unsupported|contradicted)$`。
4. 失败 ⇒ `parsed=false`，**不静默当 0 分**（ToT 是 `value_names.count(name)`，解析失败自然贡献 0 且不计数）。

### 2.3 数值映射（**这是 ToT 最不该抄的一行**）

ToT 原文（`src/tot/tasks/game24.py:90`）：
```python
value_map = {'impossible': 0.001, 'likely': 1, 'sure': 20}  # TODO: ad hoc
```
—— 作者自己标了 `# TODO: ad hoc`。而且它有量纲问题：`sure=20, likely=1` ⇒ 差 20×；`impossible=0.001` ⇒ 差 1000×。这个比例直接决定 BFS 的排序行为。

**我们的替代方案（必须做，且要在论文里写清）**：

```python
# value_map 不再手填，改成"标定"产物，且与标签计数解耦
@dataclass
class ValueMap:
    map_id: str
    weights: Dict[str, float]      # 例如 {"contradicted":0.0,"unsupported":0.25,"likely":0.75,"certain":1.0}
    calibration_report: str        # 标定方法 + 样本量 + 与外部 oracle 的一致性指标

def score(node: ThoughtNode, vm: ValueMap) -> float:
    """从 label_counts 直接算 ⇒ 换映射表不需要重新调 API。"""
    n = sum(node.label_counts.values())
    if n == 0:
        return 0.0
    return sum(vm.weights.get(k, 0.0) * c for k, c in node.label_counts.items()) / n
```

**标定流程（替代手填）**：
1. 采 N≥100 个状态（覆盖好/中/差三档，人工或强模型给出**排序**）。
2. 拟合一个单调标量刻度（保序回归 / 只拟合相邻差值比），得到 `weights`。
3. 报告**保序相关系数**（目标 ≥0.8）与**人工标注一致性**。
4. `weights` 写进 `ValueMap.calibration_report`，**随实验产物一起发布**。

> ⚠️ ToT 的做法无法做这件事：它在解析时就把标签乘成数值（`value_map`），日志里**只存了乘完的数**（`values` 字段），所以换一张映射表必须**重跑 API**。我们保留 `label_counts` 就是为了让映射表变成**可后处理**的纯函数。

### 2.4 采样与聚合

ToT 做法（`bfs.py:6-14`）：一次 API 调用 `n=n_evaluate_sample`（Game 24 用 3），把 n 个输出的末行标签计数后求和加权。
- **抄**：`n_evaluate_sample` 独立采样 + 计数聚合（比单次输出稳）。
- **改**：不求"和"，求"**均值**"（ToT 求和 ⇒ 分数随 n 线性放大，而 `method_select=='sample'` 那条路直接用 `values/sum(values)` 当概率，见 §7-#7），并把 `n` 记进日志。

### 2.5 失败处理（ToT 没有的，我们必须加）

| 情况 | ToT 行为 | 我们的行为 |
|---|---|---|
| 末行不是合法标签 | 该样本计 0，**不记录、不告警** | 记 `parsed=false`，计入 `unparsed_rate`；单节点 `unparsed_rate > 0.5` ⇒ 该节点标 `value=None`（**不可用**），不参与选择，但**保留在树里**并可被人工检查 |
| 全部 n 个样本都解析失败 | 返回 0.0 ⇒ 与"impossible"同分 | 返回 `None` ⇒ 该状态被标记为"未评估"，不与 `contradicted` 混同 |
| API 失败/超时 | `models.py:18-20` 用 `backoff` 重试；仍失败则整个 run 崩 | 同左 + 单次评估失败降级为"未评估"，**不中断整棵树** |
| 标签集写错（论文 `maybe` vs 代码 `likely`） | 静默全 0 | **启动时做一次自检**：用一个探针 prompt 跑一遍，验证至少能解析出预期标签集；否则直接 abort |

> 最后一条是血的教训：ToT 论文与代码的标签不一致，**在代码里静默降级为 0.001**，不报错。

---

## §3 vote 评估器（跨候选比较）

### 3.1 提示词全文（ToT 原文，照抄）

`src/tot/prompts/text.py:18-19`：
```
Given an instruction and several choices, decide which choice is most promising. Analyze each choice in detail, then conclude in the last line "The best choice is {s}", where s the integer id of the choice.
```
`src/tot/tasks/text.py:60-66`（拼接方式）：
```python
    @staticmethod
    def vote_prompt_wrap(x: str, ys: list) -> str:
        prompt = vote_prompt
        for i, y in enumerate(ys, 1):
            # y = y.replace('Plan:\n', '')
            # TODO: truncate the plan part?
            prompt += f'Choice {i}:\n{y}\n'
        return prompt
```
⚠️ **`{s}` 从未被 `.format()`** ⇒ 模型看到字面量 `"The best choice is {s}"`。
⚠️ 论文 p.6 的转述（`"analyze choices below, then conclude which is most promising for the instruction"`）**与代码原文不一致** ⇒ 以代码为准。
⚠️ `# TODO: truncate the plan part?` —— 作者自己知道候选可能被截断。

### 3.2 输出 schema 与解析

```jsonc
{ "raw": "……The best choice is 3", "choice_id": 3, "parsed": true }
```
ToT 的解析（`tasks/text.py:69-80`）：
```python
            pattern = r".*best choice is .*(\d+).*"
            match = re.match(pattern, vote_output, re.DOTALL)
            if match:
                vote = int(match.groups()[0]) - 1
                if vote in range(n_candidates):
                    vote_results[vote] += 1
            else:
                print(f'vote no match: {[vote_output]}')
```
**两个必须修的静默失效**：
1. `.*(\d+).*` 贪婪 ⇒ 抓**输出里最后一个数字**。模型若写 "The best choice is 3 (choice 1 is weak)" ⇒ 抓到 1。**改为** `r"best choice is\s*(\d+)"`（非贪婪 + 锚定关键词）。
2. 越界票（`vote not in range(n_candidates)`）**被直接丢弃** ⇒ 票数总和可能 < n，且不知道丢了多少。**改为**：越界票计入 `invalid_votes`，`invalid_votes/n > 0.2` ⇒ 该次投票作废（不计入任何人）。

### 3.3 我们的用法：vote ⇒ 「依据包核验」+「新颖性/冗余」

ToT 的 vote 是**"选谁"**。我们要的两件事，用**同一套协议**（一次调用看全部候选 → 多次独立投票 → 计数）跑两遍：

| 用途 | 问法（保持"ToT 协议"不变，只换目标） | 读出的量 |
|---|---|---|
| **依据包核验**（≈ ToT value） | 保留原 prompt：`which choice is most promising` | `votes[i]` ⇒ 依据包的被支持度；`argmax` 选最终包 |
| **新颖性/冗余** | 变体 prompt：`…conclude in the last line "The most redundant choice is {s}"` | `redundancy[i] = #{票选中 i 被判最冗余}`；再配合 `StateKey.canon()` 去重 |

**为什么用 vote 做冗余是成立的**：vote 协议天然是"**一次看全部候选**"的——这正是判定冗余需要的视野（value 协议是逐个看，看不到别的候选）。而"得票集中度"本身就是冗余的代理：若 n 票全落在一个候选，其余候选在本轮被判为被支配 ⇒ 可剪。

**可抄的 ToT vote 配置**（`scripts/text/bfs.sh`）：
```bash
    --method_generate sample \
    --method_evaluate vote \
    --method_select greedy \
    --n_generate_sample 5 \
    --n_evaluate_sample 5 \
    --n_select_sample 1 \
    --prompt_sample cot \
    --temperature 1.0
```
⇒ **vote 的两阶段结构**（ToT Creative Writing，论文 p.6）：
> `We build a ToT with depth 2 (and only 1 intermediate thought step) — the LM first generates k=5 plans and votes for the best one, then similarly generate k=5 passages based on the best plan then vote for the best one. Here the breadth limit b=1, as only one choice is kept per step.`

**这个"两阶段各采样 5 各投票 5、每阶段只留 1 个"的结构可以直接抄**——它是 ToT 里唯一一个"结构增益 > 采样次数"证据最强的设计（因为 b=1，没有"多开分支"的混淆）。

---

## §4 停止与剪枝（**我们要重做的部分**）

### 4.1 ToT 原来的（不能抄）

| ToT | 位置 | 问题 |
|---|---|---|
| 固定步数 `for step in range(task.steps)` | `bfs.py:56` | 跑到 T 步就停，**无早停** |
| 全局绝对阈值 `V(s) ≤ v_th` ⇒ 剪枝 | 论文 p.4 Algorithm 2 | **`v_th` 在代码里根本不存在**（全仓库 `grep v_th` 无输出）；阈值无从抄 |
| 论文伪代码自身不一致 | 论文 p.4 | Algorithm 2 写 `V(pθ,{s′})(s) > vth`（求值**父状态**），正文写 `V(pθ,{s})(s) ≤ vth`（求值**当前状态**） |
| Crosswords 的实际剪枝 | notebook cell 7 | `if not prune or count['impossible'] < 1:` ⇒ **任一线索判 impossible 就剪整棵子树**；手写常量 1 |
| 论文自己承认 | 论文 p.14 | `BFS could early stop when solution is found, or trim down beam size to when some thoughts are "impossible".` |

**⇒ 结论：ToT 的剪枝/停止没有可抄的实现。全部重做。**（这也是好事：我们要绑 δ。）

### 4.2 我们要绑的两个 δ（先测量，再写进配置）

```
δ_v : 评估器噪声地板 —— 同一状态重复评估 n_eval 次，value 的 run-to-run 标准差
δ_d : 维度噪声地板 —— |StateKey.n_dims| 在"同状态重采样"下的标准差（通常为 0，取 0 则退化为"只增不减"）
```
**测量协议（必须先做）**：
1. 从真实 run 里随机抽 ≥50 个状态，每个重复评估 n_eval=5 次。
2. 算每个状态的 value 标准差，取 **中位数** 作为 δ_v（不要取均值，会被离群状态拉高）。
3. **同时报告**：未解析率、标签分布、value 的 run-to-run 极差。
4. 把 δ_v 写进配置文件和实验日志；**任何 < δ_v 的差异一律报"不可分辨"**。

> 这条直接来自我们已有的教训：**论文的 ± 几乎总只覆盖"题目抽样"，不覆盖"生成随机性"** ⇒ 拿到自己系统的 δ 之前，任何小幅净增益都不该被接受。

### 4.3 停止规则（替代 `for step in range(task.steps)`）

```python
def search(run, task, δ_v: float, δ_d: float, b: int, max_steps: int, max_nodes: int):
    beam = [root_node(task)]
    seen_states = {beam[0].state.canon()}
    log = []
    for step in range(max_steps):                 # ① 硬上限（预算保险），不是停止条件
        children = expand(beam, task)              # 每个父状态生成若干想法
        scored   = evaluate(children, task)        # value 评估（§2）
        # ② 硬去重：同一 state_key 只留最好的一个 —— 这一步就是"维度不重复"
        best_per_state = {}
        for node in scored:
            k = node.state.canon()
            if k not in best_per_state or node.value > best_per_state[k].value:
                best_per_state[k] = node
        pool = sorted(best_per_state.values(), key=lambda n: n.value, reverse=True)

        # ③ 选：多样性约束下的 top-b
        beam_new = select_diverse(pool, b)         # 规则见 4.4

        # ④ 净维度增益
        dims_before = dims(beam)                  # |union of state.axis_ids|
        dims_after  = dims(beam_new)
        Δd = len(dims_after) - len(dims_before)

        # ⑤ 停止判定（全部与 δ 挂钩）
        if Δd <= δ_d:
            stop_reason = "net_dimension_gain_below_delta"; break
        if value_spread(beam_new) <= δ_v:
            stop_reason = "evaluator_cannot_discriminate"; break
        if nodes_visited(run) >= max_nodes:
            stop_reason = "node_budget"; break

        log.append(dict(step=step, nodes=nodes_visited(run), dims=dims_after,
                        Δd=Δd, value_spread=value_spread(beam_new)))
        beam = beam_new
    return beam, log, stop_reason
```

**三条停止条件，优先级从高到低**：
| # | 条件 | 含义 | 对应 ToT 的什么 |
|---|---|---|---|
| S1 | `Δd ≤ δ_d` | 这一轮没带来新的有效维度 ⇒ 继续搜只是重复 | ToT **没有**（ToT 只按 value 排序） |
| S2 | `value_spread(beam) ≤ δ_v` | 评估器在这个 beam 上已经分不开 ⇒ 再搜也是噪声 | ToT **没有** |
| S3 | `nodes_visited ≥ max_nodes` | 预算耗尽 | ToT 的 `task.steps`（固定步数，**不是**预算轴） |

> ⚠️ **S1/S2 必须同时报告**：`stop_reason` 决定了"为什么停"，否则审稿人会问"是不是搜够了"。**"跑满预算"和"自然收敛"必须分开报**。

### 4.4 剪枝规则（替代 `v_th`）

**要抄的 ToT 思想**：状态评估可以**否证**一条子树（Crosswords 的 `count['impossible'] < 1`）。这是"负向剪枝"，比正向排序更稳。

**要改的**：
```python
# ToT（不能抄）：全局绝对阈值，阈值手填
# if V(s) <= v_th: prune

# 我们的版本 A：相对 beam 最优 + δ 余量（阈值自动随 beam 走）
def prunable(node, beam_best, δ_v):
    return node.value is None or (beam_best.value - node.value) <= δ_v
    #      ↑ 未评估的也不保留       ↑ 与最优的差不超过噪声地板 ⇒ 不可能翻盘

# 我们的版本 B：全局阈值的标定版（若必须用绝对阈值）
# v_th = 标定集上 value 分布的第 5 百分位（不是手填 0.001）
```
**且必须加一条 ToT 没有的剪枝**（这才是"维度"真正的杠杆）：
```python
# 同一 state_key 只留一个 —— 直接实现"维度不重复"
# 并且：若某个候选的 axis_ids 已被 beam 里其他节点的并集完全覆盖 ⇒ 纯冗余，剪
def is_redundant(node, beam_axis_union):
    return set(node.state.axis_ids) <= beam_axis_union
```
⇒ **这一步是 ToT 完全没有的，也是"思维面"最核心的机制**：ToT 的 BFS 是 `argmax` 取 top-b（`bfs.py:74-75`），**允许同一个状态被保留多次**（`get_values` 里的 `local_value_cache` 只在**打分**时去重，不在**保留**时去重）。

### 4.5 BFS / DFS 我们要哪个？

| | ToT BFS | ToT DFS（Crosswords） |
|---|---|---|
| 代码 | `src/tot/methods/bfs.py` | 只有 notebook，`scripts/crosswords/search_crosswords-dfs.ipynb` cell 7 |
| 剪枝 | 无 | `count['impossible'] < 1` |
| 回溯 | 无 | `env.reset(...)` 手动回滚 board/status/steps |
| 停止 | 固定步数 | `time_limit=100` / `env.steps<10` / `max_per_state=3` |
| 节点预算实测 | b=5：84.1 次打分 / 70.1 个不同状态 | prune 版 92.8 状态/局；no-prune 版 **20/20 局全部撞满 100** |

**建议**：**我们先只做 BFS**。理由：DFS 在 ToT 里**只有一个任务、只有一个 notebook、没有进 `run.py`、没有参数化、也没有对应的发布日志以外的验证**，且它的三个硬编码上限（100 / 10 / 3）互不一致（`env.steps>=20` 在 `crosswords.py:151` 又是另一个数）。DFS 的价值在于"能回溯"，而我们的维度搜索里，回溯 = 换一条路径继续吃新维度 ⇒ **可以在 BFS 里用一个"轴覆盖优先"的评分实现**，不必先做 DFS。

> 若必须做 DFS，唯一值得抄的是**手动回滚**这个动作（notebook cell 7 的 `board/status/steps` 三元组快照），以及"候选按分数降序尝试、每个状态最多展开 k 个子"（`max_per_state`）。

---

## §5 同预算 best-of-k 换算

### 5.1 论文的原始做法（逐字，PDF p.6）

> `We also consider an oracle setup for IO/CoT, by calculating the success rate using best of k samples (1 ≤ k ≤ 100). To compare IO/CoT (best of k) with ToT, we consider calculating the tree nodes visited per task in ToT across b=1···5, and map the 5 success rates in Figure 3(a), treating IO/CoT (best of k) as visiting k nodes in a bandit.`

⇒ **轴的定义**：
- ToT：`x = 每个任务访问的树节点数`
- IO/CoT best-of-k：`x = k`（"把 best-of-k 当作访问了 k 个节点的 bandit"）

### 5.2 论文 Fig 3(a) 的**精确数值**（我从 arXiv 源码包里的 `figures/game24_scale.pdf` 矢量数据反算）

标定：`x_data = (px − 54.196)/(259.212 − 54.196) × 100`；`y_data = (py − 40.348)/276.385`（竖网格 0/25/50/75/100，横网格 0.2/0.4/0.6）。六个端点全部与正文表格吻合（<1.5pp）。

| 曲线 | 点 | 节点数 x | 成功率 y | 来源 |
|---|---|---|---|---|
| **ToT (b=1…5)** | b=1 | **20.0** | **0.444** | 矢量反算（正文只说 45%） |
| | b=2 | **31.3** | **0.571** | 矢量反算（正文无） |
| | b=3 | **42.7** | **0.646** | 矢量反算（正文无） |
| | b=4 | **54.2** | **0.695** | 矢量反算（正文无） |
| | b=5 | **66.3** | **0.735** | 矢量反算（正文说 74%） |
| IO (best of k) | k=1 | 1.0 | 0.068 | 矢量（正文 7.3%） |
| IO (best of k) | k=100 | 100.0 | 0.325 | 矢量（正文 33%） |
| CoT (best of k) | k=1 | 1.0 | 0.035 | 矢量（正文 4.0%） |
| CoT (best of k) | k=100 | 100.0 | 0.485 | 矢量（正文 49%） |

> 中间三点（57.1 / 64.6 / 69.5）是**我从图里解出来的，不是论文正文数字**。引用时必须标"自 Fig 3(a) 矢量数据反算"。

### 5.3 ⚠️ 节点轴在成本上**不等价**（这是我们必须改的第一件事）

用官方发布日志实测（每例 = 1 个游戏）：

| 方法 | 节点数 | completion tok | prompt tok | $/例 | $/节点 |
|---|---|---|---|---|---|
| CoT best-of-100（bandit，100 节点） | 100 | 4,619（表 7: 6,700） | 1,486（表 7: 2,200） | $0.322（表 7: $0.47） | **$0.0032** |
| ToT b=5 | 70.1 去重状态（论文画 66.3） | 5,479（表 7: 5,500 ✓） | **13,879**（表 7 印 1.4k ✗） | $0.745（表 7: $0.74 ✓） | **$0.0106** |

⇒ **1 个 ToT 节点 ≈ 3.3 个 bandit 节点的美元成本**；**prompt token 数差 9.3×**（13,879 vs 1,486）。
⇒ 论文的 x 轴（节点数）**系统性地让 ToT 看起来更划算**——在同样的节点数下 ToT 贵 3×。

### 5.4 我们的换算规格（照抄论文的骨架，换轴）

**必须同时画两条轴**：

```
轴 A（论文的）：节点数        —— 回答"结构 vs 采样次数"的**机制**问题
轴 B（我们的）：$ 或 total tok —— 回答"结构 vs 采样次数"的**可买**问题
```
**做法**：
1. 跑 `best-of-k` 基线，k ∈ {1,2,5,10,20,50,100}，**记录每例的 completion tok / prompt tok / $**。
2. 跑我们的方法，**记录每例的节点数（去重状态数）与同样的三个成本量**。
3. 画两条曲线：
   - 成功 vs 节点数（对齐论文，可与 Fig 3(a) 并排）
   - 成功 vs **$**（对齐成本；ToT 与 best-of-k 各自单调）
4. **在 $ 轴上取交点**：找到"我们花 X 美元达到的成功率"，然后问"best-of-k 花同样 X 美元能到多少"。
   ⇒ **这才是"增益来自结构还是采样次数"的判别式**。

**best-of-k 的节点数怎么算（照抄论文的约定）**：`x = k`（每个样本 = 访问一个 bandit 臂）。
⚠️ 但**必须同时记 token**，因为 best-of-k 的 k 个样本**共享同一个 prompt**（`models.py:26-37` 把 n 切成 ≤20 一批，每批重复计一次 prompt token）⇒ **k 越大，prompt token 越大（近似线性）**，而 ToT 的 prompt token 随节点数增长得更快（每次评估一个独立 prompt）。
> 复现要点：`chatgpt` 里 `cnt = min(n, 20)` 分批 ⇒ **n=100 的 prompt token ≈ 5 × 单次 prompt**，不是 1×。这就是"表 7 的 CoT prompt 2.2k"和"发布日志 1.5k"会差一大截的机制之一。

### 5.5 我们要用的对照基线（诚实的版本）

**不要用 "CoT 4% → ToT 74%"。** 理由（全部实测/原文）：
- CoT 4.0% 是**异常低基线**（IO 7.3% 反而更高）⇒ 70pp 的落差里有一大块是"CoT 提示词在 24 点这个任务上特别差"，不是"ToT 的结构好"。
- 同一份发布日志上，**CoT best-of-100 = 49%**（实测，逐字复现论文的 49%）⇒ **诚实的对照是 49% → 74%（+25pp），不是 4% → 74%**。
- 而 74% vs 49% 这 25pp，在 n=100 下是显著的（z=3.63, p=2.8e-4，CI 不重叠）⇒ **这个对照可以用**。
- ⚠️ 但发布日志的 ToT b=5 只有 **69.0%（any-of-5）** ⇒ 诚实的数字是 **49% → 69%（+20pp）**，且 69% 与 49% 的差在 n=100 下 z≈2.8、p≈0.005 ⇒ 仍显著，但**没有 25pp 那么漂亮**。
- ⚠️ 且 45%（ToT b=1）vs 33%（IO best-of-100）= 12pp，n=100 下 **z=1.74, p=0.082 ⇒ 不可区分**。⇒ "ToT 连 b=1 都赢过 best-of-100" 这句话**在论文的样本量下站不住**。
- 69% vs 49%（n=100）：**z=2.88, p=0.0040 ⇒ 仍显著**（73.5% vs 49% 则 z=3.56, p=0.0004）。

⇒ **我们自己的对照必须预注册 n**（§6.3 的功效表）。

---

## §6 换评估模型交叉实验的规格（用来检验"判官同源"）

### 6.1 ToT 做了什么（逐字，PDF p.14）

> `On Game of 24 (we changed 1-shot proposal prompt to 3-shot to make it work), GPT-3.5+ToT's 19% is far worse than GPT-4+ToT's 74%. To further understand the importance of generation vs. evaluation, we ran GPT-4 generation + GPT-3.5 evaluation (64%) and GPT-3.5 generation + GPT-4 evaluation (31%). This suggests the game's bottleneck is thought generation, and different generation/evaluation language models might attain decent results while reducing costs.`

Table 5（PDF p.13）：GPT-4 ToT 74% / GPT-3.5 ToT 19%；IO 7.3% / 6%；CoT 4.0% / 3%。

**确切设置**：
- 任务：**只有 Game of 24**（100 题，index 901–1000，与主实验同一测试集）。
- 2×2：生成模型 {GPT-4, GPT-3.5} × 评估模型 {GPT-4, GPT-3.5} ⇒ 4 格 = 74% / 64% / 31% / 19%。
- ⚠️ **有提示词混淆**：GPT-3.5 生成时把 **1-shot proposal prompt 改成 3-shot** ⇒ 2×2 **不是受控 A/B**。
- **重复次数未报告；置信区间全文没有。** n=100 的一次性成功率。

### 6.2 官方代码**没有**跑这个实验的能力（必须改）

```python
# src/tot/methods/bfs.py:49-51
def solve(args, task, idx, to_print=True):
    global gpt
    gpt = partial(gpt, model=args.backend, temperature=args.temperature)
```
⇒ **生成和评估共用同一个全局 `gpt`**，且 `run.py:45` 只有 `--backend` 一个后端参数。
⇒ 交叉实验 = **必须把全局拆成两个**：

```python
# 我们的版本
def solve(args, task, idx, to_print=True):
    gpt_gen = partial(gpt, model=args.gen_model, temperature=args.temperature)
    gpt_eval = partial(gpt, model=args.eval_model, temperature=args.temperature)
    # 传入 get_value/get_votes 的评估器用 gpt_eval；expand 用 gpt_gen
```
（改法：给 `get_value` / `get_votes` / `get_proposals` / `get_samples` 加一个显式的 `gen_fn` / `eval_fn` 参数，**不要用全局**。）

### 6.3 我们的交叉实验规格

**设计**：2×2（或 2×2×k）完全交叉，**四个格子用完全相同的提示词**（消除 ToT 的 shot 混淆）：

| 格 | 生成模型 | 评估模型 | 提示词 |
|---|---|---|---|
| A | G | G | 固定 S |
| B | G | J | 固定 S |
| C | J | G | 固定 S |
| D | J | J | 固定 S |

**报告的量（缺一不可）**：
1. 四格主指标 + **95% CI**（二项 / 或对配对题目用 McNemar）。
2. **未解析率**（评估器输出解析失败的比例）——ToT 代码里这类失败静默计 0。
3. **评估器与 oracle 的一致性**（在标定集上算保序相关 / pairwise accuracy）。
4. **生成随机性**：每格至少 3 个随机种子，报 run-to-run 波动。⇒ **这一步是 ToT 完全没做的，也是最可能推翻结论的一步。**

**n 的预注册（关键）**：论文 n=100 时，74% vs 64%（10pp）**不可区分**（z=1.53, p=0.126）。我们算过：

| 想检出的差 | 每格所需 n（α=0.05, power=0.8, p̄=0.69） |
|---|---|
| 10pp | **336** |
| 15pp | 149 |
| 20pp | 84 |

⇒ **若我们的主问题就是"判官同源会不会改变结论"，且预期差 <15pp，就必须把 n 提到 ≥150/格；若 n 不够，必须显式声明"该差异不可分辨"，不许含糊带过。**

### 6.4 "判官同源"在 Creative Writing 上更严重（照抄论文的实测）

- 生成者 GPT-4，判官也是 GPT-4（`src/tot/tasks/text.py:35`：`gpt(prompt, n=5, model='gpt-4')`）。
- 论文的人工盲评（PDF p.6）：
  > `humans prefer ToT over CoT in 41 out of 100 passage pairs, while only prefer CoT over ToT in 21 (other 38 pairs are found "similarly coherent")`
  ⇒ **59% 的配对人类都分不出来**。
- 而 GPT-4 自评分（论文 p.6）：ToT 7.56 vs IO 6.19 vs CoT 6.93；人工只给出 41:21。
- ⚠️ **发布日志里 ToT 的分数全是 0**（`logs/text/...generate_sample_select_greedy_sample5_*.json` 的 100 个 `accs` 全为 0）⇒ **7.56 这个数字无法从发布产物复现**；IO 6.19 / CoT 6.93 我能精确复现（各 1000 个分数的均值）。

**⇒ 我们的规格必须包含**：
1. **第三方判官**（生成与评估不同源）作为默认配置。
2. **人工盲评**作为最终仲裁，且**必须报告"分不出来"的比例**（ToT 的 38/100 = 38% 就是这种信息）。
3. 人工评审的一致性指标（Krippendorff α 或简单一致率）。

---

## §7 我们要改的 ad-hoc 清单（逐条：哪一行抄、哪一行重做）

> `抄` = 照搬机制；`改` = 保留思想、重写实现；`弃` = 不要用。
> 判据：**凡是"数值/阈值靠手填"或"失败静默降级"的，一律重做。**

| # | 文件:行 | 原文（逐字） | 处置 | 我们的做法 |
|---|---|---|---|---|
| 1 | `src/tot/tasks/game24.py:90` | `value_map = {'impossible': 0.001, 'likely': 1, 'sure': 20}  # TODO: ad hoc` | **改** | 标定产生的 `ValueMap`；保留 `label_counts` 使映射表可后处理（§2.3） |
| 2 | `src/tot/tasks/game24.py:89` | `value_names = [_.split('\n')[-1] for _ in value_outputs]` | **改** | 末非空行 + strip + 标点剥离 + 严格正则；解析失败记 `parsed=false`（§2.2） |
| 3 | `src/tot/tasks/game24.py:91` | `value = sum(value * value_names.count(name) for name, value in value_map.items())` | **改** | 存 `label_counts`，value = 后处理（换 map 不重跑 API）；改求和为均值（否则分数随 n 缩放） |
| 4 | `src/tot/tasks/game24.py:87-88` | `if len(y.strip().split('\n')) == 4 and 'answer' not in y.lower(): return 0` | **弃** | 硬编码"4 行"结构断言；改成**状态不变量**检查（`state_key` 合法 + 终止标记存在） |
| 5 | `src/tot/tasks/crosswords.py:221` | `confidence_to_value = {'certain': 1, 'high': 0.5, 'medium': 0.2, 'low': 0.1}  # TODO: ad hoc` | **改** | 同 #1，标定 + 保留原始置信标签计数 |
| 6 | `src/tot/tasks/crosswords.py:243` | `assert n_evaluate_sample == 1 # TODO: ad hoc` | **弃** | 允许 n>1，按标签计数聚合（同 #3） |
| 7 | `src/tot/methods/bfs.py:56` | `for step in range(task.steps):` | **改** | 预算上限 + δ 停止条件（S1/S2/S3，§4.3），并记录 `stop_reason` |
| 8 | `src/tot/methods/bfs.py:74-75` | `select_ids = sorted(ids, key=lambda x: values[x], reverse=True)[:args.n_select_sample]` | **改** | 加**多样性约束**：同 `state_key` 只留一个；`axis_ids ⊆ 已覆盖并集` ⇒ 剪（§4.4） |
| 9 | `src/tot/methods/bfs.py:71-73` | `ps = np.array(values) / sum(values); select_ids = np.random.choice(ids, size=..., p=ps)` | **改/弃** | vote 的计数与 value 的分数被**混用同一条归一化**（一个是整数票数，一个是 0.001–20 的分数）；且 `sum(values)==0` 会崩。→ 分开两套选择器；value 用标定后的分位数归一 |
| 10 | `src/tot/methods/bfs.py:36` | `proposals = gpt(propose_prompt, n=1, stop=None)[0].split('\n')` | **改** | 单次采样 + 裸 `split` 会产生**空串子节点**；加：去空、去重、每父节点上限、**多采样聚合**（Crosswords DFS 就是 `n=8` 聚合） |
| 11 | `src/tot/methods/bfs.py:8-13` | `if cache_value and value_prompt in task.value_cache:` | **抄** | 缓存键改成显式 `state.canon()`（而不是整条 prompt 字符串）；**这是成本降一个量级的关键**（实测 84.1 次打分 → 70.1 个不同状态） |
| 12 | `src/tot/tasks/game24.py:9-11` | `get_current_numbers(y)` | **抄（思想）** | "把路径投影成状态键"是这个项目最值钱的零件；但**解析方式要重做**（现在是 `split('left: ')[-1].split(')')[0]` 的字符串 hack，脆弱） |
| 13 | `src/tot/tasks/text.py:72` | `pattern = r".*best choice is .*(\d+).*"` | **改** | 贪婪 ⇒ 抓最后一个数字。改 `r"best choice is\s*(\d+)"`（§3.2） |
| 14 | `src/tot/tasks/text.py:76-77` | `if vote in range(n_candidates): vote_results[vote] += 1` | **改** | 越界票静默丢弃 ⇒ 改记 `invalid_votes`，超阈值整票作废 |
| 15 | `src/tot/prompts/text.py:18` | `...conclude in the last line "The best choice is {s}"...` | **改** | `{s}` 从未 format（模型看到字面量）。要么真 format，要么改成不含花括号的措辞 |
| 16 | `src/tot/tasks/text.py:48` | `info = {'rs': scores, 'r': sum(scores) / len(scores) if scores else 0}` | **改** | 判分解析失败 ⇒ 静默当 0 分，把均值拉低。改：`scores` 为空 ⇒ `r=None`（不可用），并统计未匹配率 |
| 17 | `src/tot/tasks/text.py:35` | `score_outputs = gpt(prompt, n=5, model='gpt-4')` | **改** | **判官与生成者同源**（都 gpt-4）。改：默认第三方判官 + 人工盲评仲裁（§6.4） |
| 18 | `src/tot/methods/bfs.py:51` | `gpt = partial(gpt, model=args.backend, temperature=args.temperature)` | **改** | 全局单模型 ⇒ 无法做生成/评估分离的交叉实验。拆成 `gen_fn` / `eval_fn` 显式传参（§6.2） |
| 19 | `src/tot/tasks/crosswords.py:151` vs `:172` vs notebook | `self.steps >= 20` / `self.steps = 10  # TODO: variable steps??` / `env.steps < 10` + `time_limit=100` + `max_per_state=3` | **改** | 三个互不一致的深度/预算上限。统一成一个**预算（节点数 / 美元）** + 一个 δ 停止条件 |
| 20 | `src/tot/models.py:39-47` | `gpt_usage(backend)` + 硬编码单价 | **改** | `backend` 不在三项 ⇒ `cost` 未定义（NameError）；单价写死。改：单价表可配置 + 成本按 (gen_tok, eval_tok) **分开计**，并区分"每例"与"每节点" |
| 21 | `src/tot/models.py:29-31` | `while n > 0: cnt = min(n, 20); n -= cnt; res = completions_with_backoff(..., n=cnt, ...)` | **改（记账）** | 分批 ⇒ **每批重复计一次 prompt token**（n=100 ⇒ 5 批 ⇒ prompt token ×5）。成本表必须注明"批大小"，否则不同实现的 $/例 不可比 |
| 22 | 论文 Algorithm 2 | `if V(pθ, {s′})(s) > vth` | **弃（照抄会错）** | 论文伪代码求值的是**父状态 s**，正文求值的是**当前 s**。我们不抄伪代码；用 §4.4 的 δ 版 |
| 23 | 论文 `v_th` | `V(pθ, {s})(s) ≤ vth` | **弃** | 代码里根本没有 `v_th`（全仓库 grep 无输出）⇒ 无从抄。改：相对 beam 的 δ 版（§4.4） |
| 24 | 论文 p.14 | `BFS could early stop when solution is found` | **抄（作为待办）** | 论文自己点名的改进项；我们用 §4.3 的 S1/S2 两条**与"是否已找到解"无关**的停止条件（更一般） |
| 25 | `scripts/text/bfs.sh` | `--method_evaluate vote --n_evaluate_sample 5 --n_select_sample 1` | **抄** | "每阶段生成 5 → 投票 5 → 只留 1"的两阶段结构（§3.3） |

### 7.1 抄的东西汇总（可直接进我们的代码库）

1. **状态投影 → 可枚举键**（`get_current_numbers` 的思想，`StateKey.canon()` 的形式）。
2. **评估只吃状态投影，不吃路径**（`value_prompt_wrap`）。
3. **按状态键缓存评估结果**（`value_cache` ⇒ 成本降一个量级）。
4. **末行标签 + 多采样计数聚合**（`value_outputs_unwrap` 的协议，解析重写）。
5. **vote 协议**：一次看全部候选、多次独立投票、计数。
6. **两阶段 generate→vote→keep-1**（Creative Writing 结构）。
7. **propose 模式：一次调用返回多个候选**（`split('\n')`）——但要修空串与重复。
8. **每步保留 top-b + 多样性约束**（top-b 抄，约束加）。
9. **手动回滚三元组**（DFS 的 board/status/steps 快照）——若我们做 DFS。
10. **成本记账分 gen/eval 两路**（`gpt_usage` 的思想）。

### 7.2 绝不能抄的东西（4 条）

1. **`value_map` 的手填数值**（`{'impossible':0.001,'likely':1,'sure':20}`）——作者标了 `# TODO: ad hoc`；必须标定 + 保留原始标签计数。
2. **`v_th` 绝对阈值**（论文有、代码无、且伪代码自相矛盾）——必须改成绑 δ 的相对阈值。
3. **固定步数当停止条件**（`for step in range(task.steps)`）——必须改成 δ 停止 + 预算上限双轨，并报 `stop_reason`。
4. **解析失败静默降级**（value 的 `count` 不匹配即 0；vote 的越界票丢弃；score 解析失败当 0 分）——必须改成"未评估"状态且可统计。

---

## 8. 引用 ToT 时必须带的三条免责声明

1. **"4% → 74%" 不许单独引用。** 同一份发布日志上 CoT best-of-100 = **49%**（实测复现），ToT b=5 = **69.0%**（实测，论文写 74%）。诚实的对照是 **49% → 69~74%**。
2. **"b=1→45%、b=5→74%" 不许读成"多开 4 个维度 +29pp"。** b 是**每步保留几个状态**；真正的分支因子实测 4.1–9.5（每父状态）；节点数 20 → 66（Fig 3(a) 反算）。且 45% vs IO-best-of-100 的 33% 在 n=100 下 **p=0.082（不可区分）**。
3. **Creative Writing 的增益是自评 + 59% 配对分不出来。** 生成 GPT-4 / 判官 GPT-4；人工盲评 41 : 21 : 38；且发布日志的 ToT 分数全为 0（7.56 无法复现）。

---

## 9. 本文档的诚实清单

**我核到了什么**（全部一手）：
- 论文：标题/作者/版本（arXiv API）、正文两路全文（ar5iv 保公式 + PDF 保页码）、Algorithm 1/2（源码包 `main.tex`）、Table 2–8、Appendix B.2/B.3、Fig 3(a) 的**矢量数据**（源码包 `figures/game24_scale.pdf`）。
- 代码：全仓逐行；`git grep` 确认 `v_th` **不存在**；4 处 `# TODO: ad hoc` 全部定位。
- 发布日志：6 个 run 的 100 题全部重算（按 `run.py` 原始口径），复现了 IO 7.34%/33%、CoT 4.03%/49%、Creative Writing IO 6.19 / CoT 6.93；**未复现** ToT 74%（得 69.0%）与 Table 7 的 CoT 成本行。

**我没核到 / 明确写"未取到"的**：
- `v_th` 的具体数值（代码里不存在）⇒ §4 全部是我们自己的设计。
- Fig 3(b) 误差分析的逐条百分比（只引了正文的 "around 60%"）。
- GPT-3.5 交叉实验的**重复次数与 CI**（论文没报）⇒ §6.3 的功效预注册是我们加的。
- Creative Writing 人工盲评的评审人数与一致性（论文只给 41/21/38）。
- 论文 v1 与 v2 的正文差异（作者名单已变；正文数字未逐一比对）。
- 官方仓库是否有**未推送的**交叉实验分支：**已闭合** —— `git fetch --unshallow` 后拿到**全部 50 个 commit**，`git grep "v_th" $(git rev-list --all)` **命中 0 次**，`# TODO: ad hoc` 在历史中始终只有 3 处（`.py`）+ notebook 1 处重复（根目录 `tasks/` 时代是 `tasks/game24.py:90`、`tasks/crosswords.py:220,242`）。⇒ **`v_th` 与交叉实验开关在整个公开历史里都不存在。**
