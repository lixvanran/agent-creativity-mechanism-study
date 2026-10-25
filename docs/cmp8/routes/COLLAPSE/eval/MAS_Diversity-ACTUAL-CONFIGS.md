# `MAS_Diversity` 真实配置清单（★ 物证：代码里到底有什么）

> **落点**：`docs/cmp8/routes/COLLAPSE/eval/MAS_Diversity-ACTUAL-CONFIGS.md`
> **物证来源**：`https://github.com/Xtra-Computing/MAS_Diversity`（★ **已实际 clone 到本地核过**，不是转述）
> **核验方式**：本组用**正则解析 YAML 原文**（★ PyPI 不可达 ⇒ `PyYAML` 装不上 ⇒ 改用正则），
> 核验脚本与落盘数据：`vendor/mas_configs_parsed.json`
> **核验时间**：2026-10-25 ｜ **第二组 · 层2**
> ★ **主会话 2026-10-25 要求**：★ **论文簇正在做"同类风险排查"（凡引用某论文的某个配置/某个臂，都要核一遍那个配置在他们的仓里到底存不存在）** ⇒ ⇒ **本文件是那条排查的物证**

---

## 0 · 一句话结论

> ★★ **`MAS_Diversity` 的代码里只有 **3 种拓扑** 和 **2 种对话 persona（按【资历】区分）**。
> ⇒ ⇒ ★★★ **「Interdisciplinary = 跨领域专家团」在代码里【不存在】**
> ⇒ ⇒ ★★ **他们 Fig 3 的「专家角色 ⇒ Sycophancy Trap」在代码层面更像「【资历更高】的 persona 收敛更快」**
> ⇒ ⇒ ★★★ **⇒ 真正要拆的变量是【资历 / 权威层级】，不是【领域】**

---

## 1 · ★ 拓扑：代码里真实存在的 `order.type`（**3 种**，与论文的 4/5 档不同）

| `order.type` | 出现 YAML 数 | 对应论文叫法 | 真实参数（`order` 槽位） |
|---|:-:|---|---|
| **`grouped_sequential`** | **5** | *Recursive* / *Standard* / *Horizontal* / *Vertical* | 无额外参数 |
| **`ngt`** | **2** | *NGT* | `leader_idx: 3`（★ 注释：`index of Leader; Leader only speaks in final round`） |
| **`subgroup_random`** | **2** | *Subgroup* | `group_sizes: [1, 2, 3, 2]`、`rounds_per_size: 1`、`leader_idx: -1`、`final_leader: true`、`include_leader_in_subgroups: false` |

⇒ ⇒ ★★ **三种拓扑的五槽位（`environment.rule`）逐 YAML 实测**：

| YAML | order | visibility | selector | updater | describer | `max_turns` | `round0_concurrent` | `incremental_memory_each_message` |
|---|---|---|---|---|---:|---:|---|---|
| `dsv3_naive_recursive.yaml` | grouped_sequential | **all** | basic | basic | basic | 5 | false | true |
| `dsv3_horizontal_recursive.yaml` | grouped_sequential | **all** | basic | basic | basic | 5 | false | true |
| `dsv3_interdisciplinary_recursive.yaml` | grouped_sequential | **all** | basic | basic | basic | 5 | false | true |
| `gpt5_1_interdisciplinary_recursive.yaml` | grouped_sequential | **all** | basic | basic | basic | 5 | false | true |
| `o1_mini_horizontal_recursive.yaml` | grouped_sequential | **all** | basic | basic | basic | 5 | false | true |
| `dsv3_naive_ngt.yaml` | **ngt** | **ngt** | **ngt** | **ngt** | **ngt** | 5 | —（未设） | —（未设） |
| `gpt5_1_interdisciplinary_ngt.yaml` | **ngt** | **ngt** | **ngt** | **ngt** | **ngt** | 5 | —（未设） | —（未设） |
| `dsv3_naive_subgroup.yaml` | **subgroup_random** | **subgroup** | **ngt** | **subgroup** | **subgroup** | 5 | false | true |
| `o1_mini_horizontal_subgroup.yaml` | **subgroup_random** | **subgroup** | **ngt** | **subgroup** | **subgroup** | 5 | false | true |

★ **注**：`ngt` 的 YAML **没有** `round0_concurrent` / `incremental_memory_each_message` 两个键 ⇒ ⇒ 走默认值
⇒ ⇒ ★ **⇒ 引用前人 YAML 时不可跨文件假设这两个键存在**

---

## 2 · ★★ persona：代码里真实存在的 `role_description`（**对话 agent 只有 2 种**）

| 类别 | `role_description` 原文（节选） | 出现 YAML 数 | ★ **它区分的是什么** |
|---|---|:-:|---|
| ★ **A** | `A first-year PhD student in AI research with limited research experience in {topic_lower}, bringing fresh curiosity…` | **3** | ★ **【低资历】**（一年级博士生） |
| ★ **B** | `A senior AI researcher with expertise in {topic_lower}, conducting thoughtful self-reflection and literature review.` | **6** | ★ **【高资历】**（资深研究员） |

★ **另有 2 条 tool agent 的 role_description**（综述者，与上面一一对应）：
· `The same first-year PhD student who participated in the discussion, now attempting to synthesize the group's limitations…`
· `The same senior AI researcher with expertise in {topic_lower} who participated in the discussion, now synthesizing…`

⇒ ⇒ ★★★ **承重结论**：
> ★★ **代码里唯一的 persona 轴是【资历：一年级博士生 vs 资深研究员】**
> ⇒ ⇒ **★ "Interdisciplinary = 跨领域专家团"在代码里【不存在】**（9 个 YAML 里的 `role_description` 全是这两种之一）
> ⇒ ⇒ ★★ **★ 他们 Fig 3 的「专家角色 ⇒ Sycophancy Trap」在代码层面更像「【资历更高】的 persona 收敛更快」**
> ⇒ ⇒ ★★★ **⇒ 引用他们时必须带这个限定；⇒ ⇒ 对我们的直接含义：真正要拆的变量是【资历 / 权威层级】，不是【领域】**
> ⇒ ⇒ ★ **⇒ 这恰好让 `B-2a`（去权威化 2×2）的落点更准**

---

## 3 · ★★★ 两个此前没被记录的承重结构事实（★ 影响照抄设计）

### 3.1 ★★ **每个 YAML 都是「3 个 conversation agent + 1 个 tool agent（综述者）」⇒ N = 3，不是 5**

| YAML | `agent_type: conversation` | `agent_type: tool` |
|---|:-:|:-:|
| **全部 9 个** | **3** | **1** |

⇒ ⇒ ★★★ **⇒ 预注册里写的「N = 5 个 agent」与代码不符** ⇒ ⇒ **照抄 ⇒ N = 3**
⇒ ⇒ ★★ **⇒ 而且 `ngt` 的 `leader_idx: 3` 指向的正是第 4 个 agent（tool agent / 综述者）**
⇒ ⇒ ★★ **⇒ 5 轮结构解读**：轮 1–4 = 3 个 conversation agent 讨论（`ngt`：盲写轮 → 非 leader 顺序讨论 → 全员轮）｜轮 5 = leader（tool agent）出 proposal

### 3.2 ★★★ **一次运行产出 1 份 proposal ⇒ 要拿到 5 份必须跑 5 次**

⇒ ⇒ ★★ **⇒ 因此**：**臂间 n 相等 = 5 的正确实现 = 每臂跑 5 次（不同 seed）取 5 份 proposal** ⇒ ⇒ **这与 `nosel_b5` 的 5 支天然对齐** ✔
⇒ ⇒ ★ **⇒ 调用量**：`5 次 × (4 轮 × 3 agent + 1 综述) = 65 次/臂/题`

---

## 4 · ★ 模型 / 依赖（★ 引用前人数字时必须带的可比性限定）

| 项 | 代码里的真实值 |
|---|---|
| 模型 | `deepseek-v3`（5 个 YAML）｜`gpt-5.1`（3 个）｜`o1-mini`（3 个）★ **同一个 YAML 内 3 个对话 agent 用同一个模型** |
| LLM 采样 | `temperature: 0.7` ｜ `max_tokens: 6000` |
| 额外依赖（`requirements.txt` 明示） | ★ **`AgentVerse`（`github.com/OpenBMB/AgentVerse`）+ `AI-Scientist`（`github.com/SakanaAI/AI-Scientist`）** |
| runner 怎么找 AgentVerse | `MAS_AGENTVERSE_ROOT` 环境变量，或把本仓作为 **AgentVerse 的同级目录** |
| runner 入口 | `simulation/run_dynamic_topic.py`（`from agentverse.simulation import Simulation`）｜`run_dynamic_topic_subgroup.py` |

⇒ ⇒ ★★ **⇒ 我们只有 MiniMax（预算 $0）⇒ ⇒ 跨模型不可比 ⇒ ⇒ 任何"复现"只能是【定性对照】，不是数值复现**

---

## 4.5 ★★★ **【第二类】"配置里有，但被指向的依赖版本里没有对应实现"（★ 比 §2 的 persona 那条更硬）**

> ★★★ **★ 单独成段（★ 负责人 2026-10-25 要求：不要混在 persona 那条里）**

### 事实（★ 全部实做核过，命令见 §7）

| # | 事实 | 证据 |
|:-:|---|---|
| ① | ★★ **`grouped_sequential` / `subgroup_random` 在 AgentVerse main 里【无对应实现】** | `AgentVerse` HEAD = `f90c4bd`（**2024-09-09**）｜`agentverse/environments/simulation_env/rules/order/` 只有 `sequential` / `concurrent` / `random` / `classroom` / `prisoner` / `sde_team` ｜★ **全仓 grep `grouped_sequential` / `subgroup_random` = 0 命中** |
| ② | ★★ **`MAS_Diversity` README 未指定任何 AgentVerse 分支或版本** | 只写 "clone it as a sibling of this repo" ⇒ ⇒ **无法确定他们实际用的是哪个版本** |
| ③ | ★★ **时间线不自洽** | `MAS_Diversity` HEAD = `7ee05c1`（**2026-04-23**）｜`AgentVerse` main = `f90c4bd`（**2024-09-09**）⇒ ⇒ **差 19 个月**；`git ls-remote --heads AgentVerse` = **空**（只有 main + `v0.1.5`~`v0.1.8.1` 四个 tag） |
| ④ | 沙箱额外事实 | ★ **PyPI 索引不可达**（`pip install pyyaml` ⇒ `from versions: none`）⇒ ⇒ `requirements.txt` 的依赖全装不上 |

### ⇒⇒★ 判定

> ★★★ **「前人的拓扑轴在代码层的可复现性是存疑的」**
> ⇒ ⇒ ★★ **① 是"配置写了但（被指向的依赖里）没实现"；② 是"连依赖库本身都没有这个 rule"** ⇒ ⇒ **两者合起来 ⇒ 前人的"拓扑轴"在代码层的可复现性是存疑的**
> ⇒ ⇒ ★★★ **⇒ 这直接冲击 H-TOPO-1 的立论（前人的交互结构级证据）**
> ⇒ ⇒ ★★★ **⇒ ⇒ 我们这批的价值反而上升**：★ **若前人拓扑的调度实现不可得 ⇒ ⇒ "照抄"只能照抄【参数与语义意图】，调度必须自建 ⇒ ⇒ ⇒ 「与前人调度语义等价的程度」未经核对 ⇒ ⇒ ★ 必须标 `topology_impl` 并写进结论边界**

### ★ 我们照抄了什么 / 自建了什么 / 等价程度未核对（★ 三列并排，★ 清单与预注册同口径）

| 元素 | 处置 | ★ **等价性** |
|---|---|---|
| **YAML 五槽位的真实取值与参数** | ★ **照抄** | ✔ **逐 YAML 核过**（§1） |
| **persona（senior / first-year-PhD）** | ★ **照抄** | ✔ **逐字核过**（§2） |
| **轮次结构（`max_turns=5`，轮 5 由 leader 出 proposal）** | ★ **照抄** | ✔ 9/9 YAML 一致 |
| ★★ **调度实现（谁先说、谁看得见谁）** | ⚠️ **自建** | ★★ **【未经核对】** —— ★ 被指向的依赖版本无对应实现 ⇒ ⇒ **无参照物可比** |
| ★ **LLM 后端** | ★ **换**（MiniMax） | ★ **跨模型不可比**（前人用 deepseek-v3 / gpt-5.1 / o1-mini）|
| ★ **异构轴** | ⚠️ **改写** | ★★ **前人 = 异构【模型】⇒ 我们 = 异构【资历】（senior / first-year-PhD）⇒ 不同轴 ⇒ 不可与其 Table 13 数值直接比** |

⇒ ⇒ ★★ **⇒ manifest 必写**：`topology_impl: "local_minimal_ported_params"`（★ **绝不许写 `agentverse_yaml`**）＋ ★ `dispatch_equivalence_verified: false`

---

## 5 · ★★ 论文里有、但代码里【没有】的东西（★ 引用时必须显式说明）

| 论文里的说法 | 代码里 | 处置 |
|---|---|---|
| ★ **"Interdisciplinary" = 跨领域专家团** | ❌ **不存在**（persona 只有 senior / first-year-PhD 两种） | ⇒ **★ 改写为「资历轴」** |
| ★ **5 种 persona** | ❌ 只有 2 种 | ⇒ 同上 |
| ★ **Vertical / Leader-Led / Horizontal 作为拓扑轴** | ⚠️ **代码里 `order.type` 只有 3 种**；Horizontal/Vertical 体现在 **persona 组合与模型**上 | ⇒ **⇒ 不得把 Horizontal/Vertical 当成 `order.type`** |
| ★ **Appendix M 的三条件** | ❌ **CSV 不 ship**（README 明示 `pertopic_vendi_gpt51_topologies.csv` 等不随仓发布） | ⇒ **不得声称复现了 Appendix M**；只能对照 Fig 3 / Table 13 的主文数字 |

---

## 6 · ★★ 本文件的用法（★ 论文簇「同类风险排查」直接用）

> ★★ **规则**：★ **凡论文/报告里写「某论文的某个配置 / 某个臂」⇒ 必须在本文件里找到对应行 ⇒ 找不到 ⇒ 就是「我搜到了 ≠ 它是这个」**
⇒ ⇒ ★ **本文件的三种判定**：
> | 判定 | 含义 |
> |---|---|
> | ✔ **代码里有** | 本文件列出了对应 YAML + 五槽位 + 参数 |
> | ⚠️ **论文里有但代码里没有** | §5 列出 ⇒ **引用必须带限定** |
> | ✖ **两边都没有** | ⇒ **不许引用** |

⇒ ⇒ ★ **配套的通用纪律（★ 今日跨组共同新增）**：
> ★ **★ 指标名不能替代口径定义；跨组引用前必须对齐口径名**（★ 三组自己查出的口径错误：我问他的 `''` 怎么处理 ⇒ 他回头查发现自己的"模态数"其实是"断言文本数" ⇒ 他论文里一处会让人读错结论的论据被推翻）

---

## 7 · ★ 核验命令（★ 外部可复现）

```bash
# ① 拿仓
git clone --depth 1 https://github.com/Xtra-Computing/MAS_Diversity.git

# ② 核五槽位（本组用正则，因为 PyPI 不可达 ⇒ PyYAML 装不上）
cd MAS_Diversity/simulation/configs
for f in *.yaml; do echo "── $f"; sed -n '/^environment:/,/^agents:/p' "$f"; done

# ③ 核 agent 数与 persona
grep -c "agent_type: conversation" *.yaml
grep -h "role_description:" *.yaml | sort -u

# ④ 本组的解析结果（落盘）
vendor/mas_configs_parsed.json
```

⚠️ **环境事实（★ 2026-10-25 实测）**：★ **本沙箱 PyPI 索引不可达**（`pip install pyyaml` ⇒ `from versions: none`）
⇒ ⇒ **任何需要 `pip install` 的 A 档依赖都装不上**（`PyYAML` / `AgentVerse` 全家桶）⇒ ⇒ **这是 A 档不可行的直接原因之一**
