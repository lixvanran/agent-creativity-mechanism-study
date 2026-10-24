# 第四组 · 工作包三 · 最小架构草案：「保留—检验—换路」

**版本**：2026-10-25 v2 ｜ **性质**：★ **离线设计草案 + 可执行离线测试**（**未跑任何能力实验**）
**来源**：外部来信的最小架构草案（由主会话转述）+ 第四组层 4 的既有机制（v3–v6）

> ★★★ **【接口已对齐 · 2026-10-25 · 第二组直发通道】**
> 第二组经**直发通道**（GitHub 三分支仍未推上，`git ls-remote --heads` 只有
> `main` / `feature/g4-arch4-state-driven` / `cmp8-handover-2026-10-20`）把
> `creativity_lab/state_layer.py` **逐字节原文**发到本组 ⇒ ⇒ 已落盘并**核 sha256**：
>
> | 项 | 值 |
> |---|---|
> | 文件 | `creativity_lab/state_layer.py` |
> | **现行版本** | ★ **rev1** sha256 = `69a29c506a4e4ab0`（★ 14055 B） |
> | 上一版 | rev0 sha256 = `38795bf6adfdee05`（★ 10257 B） |
> | 核对 | ✅ **rev1 逐字节一致**（★ 由第四组 `apply_state_layer_rev1.py` 应用 ⇒ ★ **sha256 双向校验通过**） |
> | 差异覆盖 | ★ rev0 的 4 条差异（①②③④）**已由第二组修订并被第四组探针机械确认为「已修复」** ⇒ ★ 新增 1 条待裁决（见 §6.3 ⑤） |
>
> ⇒ ⇒ ★ **接口归属归第二组；本文件降级为「实现与读数侧」的配套说明，以 `creativity_lab/state_layer.py` 为准。**
> ⇒ ⇒ ★ **本文件 §1–§5 的自建接口不再作为实现依据** ⇒ ⇒ ★ **仅保留**：
> ① §0 的**定位关系**（层 4 已有机制 vs 新增槽位）——★ 仍然有效；
> ② §5 的**「证明了什么/没证明什么」**——★ 仍然有效且更重要；
> ③ §7 的**第四组实现与读数侧职责**——★ 本组主线。
> ⇒ ⇒ ★ **§1–§4 的自建 dataclass 与 R1–R7 规则保留作历史对照**，★ 但**不是实现依据**，
> ★ 差异见 §6（★ 4 条规格-实现差异 ⇒ ⇒ 已上报第二组裁决 ⇒ ⇒ 第四组**不单方面改规则**）。
>
> ★ **本包只主张"设计落实度"，不主张"能力提高"** —— 沿用外部那句：**「接口自检通过只证明设计落实，不证明能力提高」**。

---

## 0. 它与第四组已有机制的关系（先定位，避免重复造）

| 第四组已有 | 外部草案新增 | 关系 |
|---|---|---|
| 状态 = stance / keeps / gaps / decisions | **保留项**（条件与关系） | `keeps` 已经是"保留项"的雏形 ⇒ **升级为显式字段** |
| —— | **假设及证据** | ★ **全新**：第四组至今**没有"可被反证的命题"** |
| 决策步（取舍声明） | **可回退的换路点** | ★ **全新**：第四组至今**没有"回退"回路** |
| 状态 → 目标集 → 打分 → 排序 | **子目标由系统提出、可修订、可撤销** | ★ **全新**：第四组至今**目标只能来自观测缺口**，不是系统自己提的 |

⇒ ⇒ **所以这不是换测法，是【接上上游那一段】：把"目标本身可生成、可反证、可撤销"做成可观察的。**

---

## 1. 状态接口（数据结构）

> ⚠️ **【以下为第四组自建版本 · ★ 已被第二组接口取代 · ★ 不是实现依据】**
> ★ 现行接口以 `creativity_lab/state_layer.py`（第二组，sha256 `38795bf6adfdee05…`）为准。
> ★ 两版的关键结构差异见 §6.1。

```python
@dataclass
class SubGoal:
    text: str            # 一句话子目标
    index: int           # 编号（结构化绑定用）
    origin: str          # ★ "它怎么来的"：'model' | 'rollback' | 'code_default'
    evidence: list[str]  # 依据（观测到的具体事实/编号）
    revoked_by: str|None # 撤销原因（None = 活跃）

@dataclass
class Hypothesis:
    claim: str
    evidence: list[str]
    status: str           # 'open' | 'confirmed' | 'refuted'
    refuted_by: str|None

@dataclass
class SwitchPoint:
    frm: str              # 离开的动作类型
    to: str              # 回到的动作类型
    trigger: str         # 触发条件（可机检）
    cost: int            # 回退代价（预算单位）

@dataclass
class State4:
    keeps: list[str]              # 保留项（条件与关系）
    hypotheses: list[Hypothesis]  # 检验中的假设与证据
    switch_points: list[SwitchPoint]
    subgoal: SubGoal|None
    budget: dict                  # {'calls_left': int, 'tokens_left': int}
    history: list[dict]           # ★ 来源日志（谁提出、依据什么、何时撤销）
```

## 2. 动作接口（★ **动作类型的变化是"换路"的唯一可机检判据**）

> ⚠️ **【以下为第四组自建版本 · ★ 已被第二组接口取代 · ★ 不是实现依据】**
> ★ **原标题写「8 种」但表里只有 7 个 ⇒ ★ 那是自建版的一处笔误**，★ 现按实际条数修正为 7。
> ★ 现行动作空间以第二组 `ACTIONS` 为准（★ 7 个）：
> ★ `explore` / `check_hypothesis` / `connect` / `rollback` / `switch_method` / `deliver` / `stop`
> ★ ⇒ ★ 与自建版的差别在**命名**（`check`→`check_hypothesis`、`switch`→`switch_method`、
> ★ `organize`→`deliver`）★ 与**统一决策点**（★ 第二组有 `choose_action(st)` 单点优先级链）。

| 动作 | 含义 | 关键输入 | 关键输出 |
|---|---|---|---|
| `explore` | 独立探索 | 当前 subgoal / 假设 | 新证据 |
| `check` | 检查假设 | hypothesis + 新证据 | `status` 更新（confirmed/refuted） |
| `connect` | 连接两组信息 | 两组证据 | 合并证据 |
| `rollback` | 回退 | switch_point | 回到 `to` 动作 + 撤销相关 subgoal |
| `switch` | 切换方法 | 当前方法标识 | 新方法标识（★ **必须与旧标识实质不同**） |
| `organize` | 组织交付 | 证据 + 结论 | 交付物 |
| `stop` | 停止 | 预算/达成 | 终止 |

### 2.1 ★「换路」的可机检定义（外部那句"须改变实质假设或方法，不是重新措辞"）
> **换路成立 ⇔ 动作类型改变 **或** 方法标识实质不同。**
> ⚠️ **只改措辞（同一动作类型 + 同一方法标识）⇒ 不算换路** ⇒ ⇒ **可被一条断言机械检查**。

## 3. 更新规则（★ 全部是**纯函数** ⇒ 可离线测试）

> ⚠️ **【以下 R1–R7 为第四组自建版本 · ★ 已被第二组接口取代 · ★ 不是实现依据】**
> ★ 现行规则以 `creativity_lab/state_layer.py` 的 `propose_subgoal` / `revoke_subgoal` /
> ★ `revise_subgoal` / `add_evidence` / `rollback` / `record_attempt` / `record_call` /
> ★ `preserve_divergence` / `choose_action` 为准（★ 九个纯函数 + 一个决策函数）。

| 规则 | 触发 | 动作 | 留痕 |
|---|---|---|---|
| **R1 子目标生成** | 观测到新证据 | 模型**提出**子目标（代码只结构化） | `history += {event:'subgoal_set', ...}` |
| **R2 假设反证** | `check` 把假设标 `refuted` | 撤销受该假设支撑的 subgoal | `history += {event:'subgoal_revoked', by:'refuted', ...}` |
| **R3 重复死路** | 连续 **N=3** 次**同动作类型 + 同失败签名** | 强制 `rollback` 或 `switch`（**不许继续同动作**） | `history += {event:'deadlock_break', ...}` |
| **R4 回退** | `rollback` | 回到 `switch_point.to`；**撤销**该段产生的 subgoal | `history += {event:'rollback', from,to }` |
| **R5 换路** | `switch` | 新方法标识（★ 须实质不同，见 §2.1） | `history += {event:'switch', from,to }` |
| **R6 停止** | 预算耗尽 **或** 目标达成 | `stop` | `history += {event:'stop', reason }` |
| **R7 预算记账** | 每次调用 | 扣 `calls_left`；★ **失败调用同样扣**（不静默） | 落 `calllog` |

★ **代码不得替模型选定答案再宣称自主** ⇒ ⇒ **R1 的子目标取值必须由模型给**；代码只做**结构化、记账、撤销**三件事 ⇒ ⇒ ⇒ **"自主"只主张到"系统可提出并撤回自己提出的子目标"，不主张到"子目标有价值"。**

---

## 4. ★ 五个离线测试（**可执行断言**；每条都给输入/期望/断言）

> ⚠️ **【以下 T1–T5 为第四组自建版本的测试设计 · ★ 现行可执行测试是第二组规格表的实现】**
> ★ 现行落点：`creativity_lab/experiments/test_state_layer.py`
> （★ 第二组出规格表 / 第四组按规格实现 ⇒ ★ 6/6 通过 ⇒ exit 0 ⇒ ★ **另带 `--self-test`
> 变异注入自检 6/6** ⇒ ⇒ ★ **每个测试项都证明过自己能抓到东西**）。
> ★ 两版测试的对应关系与差异见 §6.2。

> 全部**离线**（无 LLM 调用）⇒ ⇒ **测的是"规则落实"，不是"能力提高"**。

### T1 重复死路（⇒ 必须打断，不许继续同动作）
- **输入**：动作序列 `explore, explore, explore`，三次**失败签名相同**（同一 `error_class` + 同一目标编号）。
- **期望**：第 3 次后被 R3 打断 ⇒ 动作变为 `rollback` 或 `switch`。
- **断言**：`len(history) >= 1` 且 `history[-1]['event'] in ('deadlock_break','rollback','switch')` 且 **下一动作类型 ≠ `explore`**。

### T2 反证触发回退（⇒ 假设被推翻 ⇒ 回退）
- **输入**：`Hypothesis(claim='X', status='open')`；`check` 返回 `status='refuted'`。
- **期望**：R2 撤销由 X 支撑的 subgoal；随后动作可 `rollback`。
- **断言**：`subgoal.revoked_by is not None` 且 `history` 含 `event=='subgoal_revoked'`。

### T3 合法分歧保留（⇒ 并列不许被贪心吃掉）
- **输入**：两个候选**评分并列**（如 `0.5, 0.5`）且**来自不同来源**。
- **期望**：两者**都保留**在候选集合里（不因 greedy 取一而丢）。
- **断言**：并列后候选集合大小 == 2（★ 注意：**这与第四组 v6 的 `Select(greedy)` 行为不同** ⇒ ⇒ 若要保留分歧，选择器必须显式支持 `keep_ties`）。

### T4 子目标撤销（★ 唯一的新构念）
- **输入**：一个活跃 subgoal + 一次 `revoke(reason='evidence_invalid')`。
- **期望**：当前 subgoal 置空；`history` 留痕；随后**可产生新的 subgoal**（`origin='rollback'` 或 `'model'`）。
- **断言**：`state.subgoal is None` 或 `state.subgoal.origin == 'rollback'`；`history` 同时含 `subgoal_set` 与 `subgoal_revoked`；★ **新 subgoal 的 `origin` 必须被记录**（"它怎么来的"）。

### T5 预算用尽与失败调用（★ 失败不许静默）
- **输入**：`budget={'calls_left':1}`；一次调用**失败**（记入 `calllog` 的 `ok=False`）。
- **期望**：失败**同样扣预算**；预算耗尽 ⇒ 动作 `stop(reason='budget_exhausted')`。
- **断言**：`calls_left == 0`（**失败后也是 0，不是 1**）；`history[-1]['event']=='stop'` 且 `reason=='budget_exhausted'`；★ **失败记录存在于 `calllog` 且未被删除**。

---

## 5. ★ 这五个测试**证明了什么 / 没证明什么**（防止过度解读）

| | 说明 |
|---|---|
| ✅ **证明** | 五条规则**被实现且可执行**；T3/T4/T5 直接对应第四组已知的三类坑（并列被吃掉 / 目标不可撤销 / 失败漏记）⇒ ⇒ **离线测试是有真实靶子的，不是凑数**。★ **现行实现另有 `test6_spec_redlines`（规格三条红线）与 `--self-test` 变异注入自检（6/6）⇒ ⇒ 每个测试项都证明过自己能抓到东西。** |
| ❌ **没证明** | ★ **不证明能力提高**。离线全绿只说明**规则落实**。★ **与第四组既有教训同构**：「接口自检通过只证明设计落实，不证明能力提高」——第四组自己的自检（v5 33/33、v6 32/32）同样**一次都没证明过驱动力成立**。 |
| ⚠️ **★ 更进一步（★ 2026-10-25 新增）** | ★ **离线测试全绿 ≠ 语义无歧义**。★ §6.3 第 2 条是活例：★ 死路判定的「连续 vs 累计」两种语义**都能通过同一套测试** ⇒ ⇒ ★ ⇒ **「测试全绿」只证明「规则被实现」，不证明「实现的就是规格说的那个意思」** ⇒ ⇒ ⇒ **★ 凡是规则带自然语言描述的，★ 都要另配一个语义探针**（★ 见 `probe_state_layer_spec_gap.py`）。 |
| ⚠️ **下一步（若要跑）** | 需要**能力实验**：在同一题集上比较「有/无 保留—检验—换路」两臂，判据沿用 v6 的纪律（**零判官**、**必报地板**、**必报区分力**、**代价必须进排序**）。⇒ ★ **且必须先解决 v6 暴露的候选同质问题**，否则测的仍是一批等价候选。 |

---

## 6. ★★ 第二组接口 vs 第四组自建版：差异对照 + 四条规格-实现差异

### 6.1 两版结构差异（★ 接口层）

| 维度 | 第二组 `state_layer.py`（★ **现行依据**） | 第四组自建版（★ 历史对照） |
|---|---|---|
| 子目标 | **列表** `subgoals[]`（`sid`/`parent_sid`/`revision`/`revocation_reason`） | **单个** `subgoal`（`index`/`origin`/`revoked_by`） |
| 假设 | `Hypothesis(status: open/refuted/supported)` + `evidence[]` | `Hypothesis(claim/status/refuted_by)` |
| 换路点 | ❌ **无显式 switch_point** ⇒ ⇒ `rollback` 只追加 `keep[]` 检查点 | ✅ `SwitchPoint(frm/to/trigger/cost)` |
| 预算 | `budget_remaining` / `budget_used` 两个计数 | `budget{calls_left, tokens_left}` 字典 |
| 分歧 | `divergences[]`（显式调用 `preserve_divergence`） | `kept_candidates[]`（由 `keep_candidates_ties` 产出） |
| 动作空间 | 7 个：`explore`/`check_hypothesis`/`connect`/`rollback`/`switch_method`/`deliver`/`stop` | 7 个：`explore`/`check`/`connect`/`rollback`/`switch`/`organize`/`stop` |
| 决策 | ★ **`choose_action(st)` 单点优先级链**（★ 状态 → 动作） | 分散在 R1–R7 各自触发，**无统一决策点** |
| 失败记账 | ✅ `n_calls_total` / `n_failed_calls`（★ **分母显式**） | ⚠️ 只有 `history` 事件，**无独立失败计数** |

★ **最关键的结构性差别** = ★ **第二组有统一的 `choose_action(st)` 决策点** ⇒ ⇒
★ 这才是「层 4：★ **状态决定当下动作**」的标准形态 ⇒ ⇒ 第四组读数侧必须以它为**动作来源**。

### 6.2 两版测试的对应关系

| 第二组规格表 | 第四组自建版 | 落点（★ 现行） |
|---|---|---|
| T1 重复死路 | T1 重复死路 | `creativity_lab/experiments/test_state_layer.py::test1_dead_end` |
| T2 反证触发回退 | T2 反证触发回退 | `…::test2_refute_rollback` |
| T3 合法分歧保留 | T3 合法分歧保留 | `…::test3_divergence` |
| T4 子目标撤销 | T4 子目标撤销 | `…::test4_subgoal_revocation` |
| T5 预算用尽与失败调用 | T5 预算用尽与失败调用 | `…::test5_budget_and_failure` |
| （★ 规格三条红线） | —— | `…::test6_spec_redlines`（★ 第四组加：JSON 可序列化 + 纯函数不就地改） |

★ **两版测试数不同（6 vs 5）**：★ 第四组多一项 `test6_spec_redlines` ⇒ ⇒
★ **因为第二组的三条红线（可序列化 / 纯函数 / 失败不许静默归零）本身也是规格** ⇒ ⇒ 不测就等于漏。

### 6.3 ★★ 四条「规格 ↔ 实现」差异（★ 已机械坐实 · ★ 上报第二组裁决）

> ★ 探针落点：`group4_state_driven/probe_state_layer_spec_gap.py`（★ 零 API · ★ 只读不改）
> ★ **本探针不改第二组文件** ⇒ ⇒ 差异由第二组裁决 ⇒ ⇒ **第四组不单方面改规则**。
> ★ ★ **探针已改为【双版本差分】**（★ `--both`）⇒ ⇒ **同时加载 rev0 与 rev1** ⇒ ⇒
> ★ **对每条差异给出【两版各自判定】** ⇒ ⇒ ★ **「已修复」与「仍存在」一眼分开**
> ★ ⇒ ⇒ ★ ★ **理由**：★ rev1 修掉了 rev0 的 4 条 ⇒ ⇒ ★ 旧探针会继续报"已修复的 bug"
> ★ ⇒ ⇒ ★ **★ 那是【过期工具】⇒ ⇒ ★ 比没有更坏**（★ 让人以为还有 bug）⇒ ⇒ ★ **探针必须跟着接口版本走**。
> ★ **当前实测**：★ rev0 仍存在 **4** 条 ⇒ ★ rev1 仍存在 **1** 条（⑤）⇒ ★ 差 **3** 条（★ 修订覆盖）。

| # | 差异 | 后果 | 裁决方 |
|:-:|---|---|---|
| **1** | `HYP_SUPPORTED` **定义但不可达**（★ `add_evidence(refutes=False)` 不改状态） ⇒ ⇒ **支持性证据永远把假设留在 `open`** | ⇒ ★ **`check_hypothesis` 分支永久优先于 `connect`** ⇒ ⇒ 实测：连续 10 次支持性证据 + 1 条分歧 ⇒ `choose_action` 仍返回 `('check_hypothesis','h2')` ⇒ ⇒ **分歧连接被无限期阻塞** | 第二组 |
| **2** | 死路判定写的是 `at.used >= 3`（★ **累计**），规格表写「★ **连续** 3 次无新信息」 ⇒ ⇒ **且 `at.produced_new` 是每次覆盖而非累积** | ⇒ 实测 `(True,True,False)` ⇒ **判死路** ⇒ `switch_method` 提前触发 ⇒ ⇒ **比规格更激进**（★ 成功过的方法也会被判死路） | 第二组 |
| **3** | 支持性证据**不写 `progress`**（★ 只有反证写 `refuted:<hid>`） | ⇒ ★ 状态回放时**无法区分支持证据与反证证据** ⇒ ⇒ 与「可回放」红线②有张力 | 第二组（★ 若认为该留痕 ⇒ **属规则变更 ⇒ 须重过预注册**） |
| **4** | 「★ 并列 ⇒ 自动保留分歧」**在代码里没有机制**；只有显式 `preserve_divergence` | ⇒ ★ 第四组 v6 的 `Select(greedy)` **会吃掉并列** ⇒ ⇒ **接线时必须显式补这一步**，★ 否则分歧语义丢失 | 第二组（接口层）+ ★ **第四组（接线层 ⇒ 归第四组实现与读数侧）** |
| **5** | ★ **rev1 新增**：`detect_tie` **只查【最大值处】**（`best = max(scores)`）⇒ ⇒ **中位并列漏检** | ⇒ 实测：`detect_tie([0.9,0.5,0.5])` ⇒ **`None`**（★ 两个 0.5 是"第二好方案并列"的真实分歧）⇒ ⇒ **分歧语义又丢** | 第二组（★ 接口层语义）|

★ **★ 为什么第 2 条不会被离线测试抓到**：★ 规格表说「连续 3 次无新信息」，
★ 按规格写测试 ⇒ 通过；★ 按实现写测试（`True,True,False`）⇒ 也通过（★ 因为实现的判据更宽）
⇒ ⇒ **两条语义都能通过同一套测试** ⇒ ⇒ ⇒ **★ 这就是「离线测试全绿 ≠ 语义无歧义」的实例**
⇒ ⇒ **⇒ 必须补一个独立探针**，★ 这与第四组 v6 的教训同构（★ 「干净 ≠ 有力」）。

---

## 7. ★★ 第四组的职责边界：实现与读数侧（★ 第二组三条使用边界）

第二组在直发消息里写死了三条边界，★ **第四组据此分工**：

| 第二组出的 | 第四组出的 |
|---|---|
| ✅ `state_layer.py`（★ **接口规格** · 逐字节原文 · sha 已核） | ★ **状态怎么被 LLM 读写**（★ 读写协议 · 序列化 · 注入位置） |
| ✅ `test_state_layer.py` 的**规格表**（★ 第四组按表实现可执行版本） | ★ **「提什么子目标」**（★ ★ 这是一个**生成问题** ⇒ ⇒ 必须单独预注册） |
| ✅ 纯函数 + 人写死的固定规则 | ★ **分歧连接后怎么收敛**（★ 连接 ≠ 压平） |
| —— | ★ **读数与判决**（★ 判据 · 地板 · 检出力 · 失败显式标记） |

★ **三条使用边界的具体含义**：

1. **「状态怎么被 LLM 读写 / 提什么子目标 / 分歧怎么收敛」本文件全都没有** ⇒ ⇒
   ★ **那三样是第四组的设计题**，★ 且「提什么子目标」是**生成问题** ⇒ ⇒
   ★ ⇒ **第四组必须在跑任何臂之前单独预注册**，★ 不许边跑边定。
2. **本文件不产生任何读数** ⇒ ⇒ **读数与判决归第四组** ⇒ ⇒
   ★ 第四组的读数侧必须遵守 v6 纪律：**零判官 / 必报 D0 地板 / 必报区分力 / 代价必须进排序**。
3. **「死路」阈值（连续 3 次）、动作优先级、预算扣减规则 = 人写死的固定规则** ⇒ ⇒
   ★ **改它们要重新过一遍预注册** ⇒ ⇒
   ★ ⇒ **★ §6.3 的四条差异一旦被改（尤其是第 2 条死路阈值），★ 就落进这条** ⇒ ⇒
   ★ ⇒ **第四组不单方面改**（★ 已在探针里落成"只读不改"）。

★ **★ 层归属纪律（★ 第二组在消息里点出的两条独立理由，★ 第四组照办）**：
① **加字段 = 加因子** ⇒ ⇒ 2×2 的单因子分解当场失效（★ 第二组上一轮栽过的坑）；
② **层 2 + 层 4 混在一臂 = 层归属污染**（★ 负责人立过「层 2 与层 3 必须拆开」⇒ 层 2 与层 4 同理）。
⇒ ⇒ ★ **三个新槽位（假设 / 子目标 / 分歧保留语义）必须加在第四组自己的新臂/新批**，
★ ★ **绝不混进第二组当前 6 臂主批**。

★ **★ 一个有用的发现（★ 第二组在消息里指出，★ 第四组确认）**：
★ 第二组一直在做「换路」实验（★ `ngt` / `gs` / `subgroup_random` 三臂 = 同一问题、三种可见性图）
⇒ ⇒ ★ **那三个字段在第二组【不是"要加"，是"要显式化 + 要报告"】**
⇒ ⇒ ★ **真正缺的只有三样：假设槽位 + 子目标槽位 + 分歧保留语义 —— ★ 而这三样恰好全是"层 4 专属"**。

---

## 8. 复现（本包的全部可执行部分）

```bash
# ★ 现行可执行测试（第二组规格表 · 第四组实现）—— 8/8 ⇒ exit 0
python3 -B creativity_lab/experiments/test_state_layer.py

# ★ 变异注入自检（证明每个测试项是活的）—— 10/10 ⇒ exit 0
python3 -B creativity_lab/experiments/test_state_layer.py --self-test

# ★ 规格-实现差异探针（零 API · 只读不改第二组文件）—— rev1 仍存在 1 条
python3 -B group4_state_driven/probe_state_layer_spec_gap.py

# ★ 双版本差分（rev0 vs rev1）
python3 -B group4_state_driven/probe_state_layer_spec_gap.py --both

# ★ rev0 → rev1 应用脚本（★ 三道自保护：锚点唯一命中 / 应用后 sha 校验 / 幂等）
python3 -B group4_state_driven/apply_state_layer_rev1.py creativity_lab/state_layer.py

# ★ 第四组自建版测试（★ 历史对照，★ 不是实现依据）—— 5/5
python3 group4_state_driven/workpack3_tests.py

# 机制层自检
python3 group4_state_driven/code/workflow_arch6.py
```

★ **sha256 核对命令（★ 唯一可靠的核对手段）**：
```bash
sha256sum creativity_lab/state_layer.py | cut -c1-16
# ⇒ 必须输出：69a29c506a4e4ab0   （★ rev1 现行版）
```

★ **★ 双向校验是这套协作的底层机制**：★ 发送方给 sha、接收方应用后核 sha ⇒ ⇒
★ **★ 只要两边有一行字不同 ⇒ sha 必不符 ⇒ ⇒ 错误【不可能静默通过】** ⇒ ⇒
★ ★ **这比"记得别改"可靠得多**（★ 双方都已经各栽一次：★ 发送方手改一行 / 手抄 diff 抄错一段）。
