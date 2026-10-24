# 第四组 · 工作包三 · 最小架构草案：「保留—检验—换路」

**版本**：2026-10-25 v1 ｜ **性质**：★ **离线设计草案 + 可执行离线测试**（**未跑任何能力实验**）
**来源**：外部来信的最小架构草案（由主会话转述）+ 第四组层 4 的既有机制（v3–v6）
> ⚠️⚠️ **【接口来源待对齐 · 2026-10-25】** 主会话告知：第二组已交 `creativity_lab/state_layer.py` +
> `creativity_lab/experiments/test_state_layer.py`（接口 + 离线测试，exit 0 全绿）⇒ ⇒ **按分工，
> 接口应以第二组的为准**。⇒ ⇒ **但我方从 GitHub 三个分支（main / feature/g4-arch4-state-driven /
> cmp8-handover-2026-10-20）全部取不到该文件（contents API 404，tree 检索 `state_layer` 0 命中）**
> ⇒ ⇒ ⇒ **⇒ 本文件当前的接口与规则是第四组【自建版本】，尚未与第二组对齐** ⇒ ⇒
> ⇒ ⇒ ★ **待第二组把文件推上 branch 或给出可取路径后，应以第二组接口为准，本文件降级为"实现与读数侧"的配套说明**。
★ **本包只主张"设计落实度"，不主张"能力提高"** —— 沿用外部那句：**「接口自检通过只证明设计落实，不证明能力提高」**。

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

## 2. 动作接口（8 种；★ **动作类型的变化是"换路"的唯一可机检判据**）

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
| ✅ **证明** | 五条规则**被实现且可执行**；T3/T4/T5 直接对应第四组已知的三类坑（并列被吃掉 / 目标不可撤销 / 失败漏记）⇒ ⇒ **离线测试是有真实靶子的，不是凑数**。 |
| ❌ **没证明** | ★ **不证明能力提高**。离线全绿只说明**规则落实**。★ **与第四组既有教训同构**：「接口自检通过只证明设计落实，不证明能力提高」——第四组自己的自检（v5 33/33、v6 32/32）同样**一次都没证明过驱动力成立**。 |
| ⚠️ **下一步（若要跑）** | 需要**能力实验**：在同一题集上比较「有/无 保留—检验—换路」两臂，判据沿用 v6 的纪律（**零判官**、**必报地板**、**必报区分力**、**代价必须进排序**）。⇒ ★ **且必须先解决 v6 暴露的候选同质问题**，否则测的仍是一批等价候选。 |

---

## 6. 复现（本包的全部可执行部分）

```bash
# 五个离线测试（无 LLM 调用）
python3 workpack3_tests.py
# 机制层自检
python3 workflow_arch6.py
```
