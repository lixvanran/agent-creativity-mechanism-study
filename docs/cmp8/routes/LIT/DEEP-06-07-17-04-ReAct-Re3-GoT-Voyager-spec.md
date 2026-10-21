# DEEP-06-07-17-04 — ReAct / Re3 / GoT / Voyager → 可演化动作空间规格

> 项目：**思维面 = 有效信息维度数**（让答案不再中庸，治「搜索空间过早闭合」）
> 现状动作空间：**固定 7 个 op** — `GEN_PLAIN` / `GEN_ANGLE` / `EXTRACT` / `SPLIT` / `VERIFY` / `MERGE` / `STOP`
> 本文件目标：**动作/结构本身怎么「长出来」**，而不是又一套固定流程。
> 逐字证据：`/workspace/lab/routes/LIT/DEEP-06-07-17-04-quotes.md`（下文用 `V1 / R4 / E1 / G3 / C12` 等编号引用）

---

## 0. 阅读须知（先读这节，否则会误用）

### 0.1 标注约定

| 标记 | 含义 |
|---|---|
| **【文献】** | 能在本次抓取的原文里逐字定位（给 quote 编号） |
| **【我们的】** | 我们自己的设计，**没有**文献直接支撑；是为了项目目标推出来的 |
| **【警示】** | 看起来像某篇论文的做法，但**不能照抄**，附理由与证据 |
| **【未核】** | 本次没读到 / 抓不到 / 属于用户内部读数 |

### 0.2 四篇的实际读数（先摆证据强度，再谈规格）

| 论文 | 实际测的是什么 | 样本量 / 设置 | 证据强度 |
|---|---|---|---|
| **Voyager**（2305.16291v2） | Minecraft 探索：unique items ×3.3、tech tree 最快 ×15.3、地图 ×2.3 | 3 trials；GPT-4-0314 / GPT-3.5-turbo-0301；温度 0（课程 0.1） | 中。消融清晰，但**没有任何"新原语被发明"的证据**（见 §1.1） |
| **ReAct**（2210.03629v3） | HotpotQA / FEVER / ALFWorld / WebShop | PaLM-540B + GPT-3；6 个 HotpotQA few-shot、3 个 FEVER | 中高（多基准 + 受控 Act 消融） |
| **Re3**（2210.06774v3） | 2000–2500 词故事；人工 pairwise | **50 个故事 × 3 名 MTurk 标注者**；GPT3-175B | **弱**。n=50，且"改写"其实是重排序（见 §4） |
| **GoT**（2308.09687v4） | sorting / set ops / keyword counting / doc merging | **100 样本/任务**；GPT-3.5；temperature 1.0；4k context | 中（工程可复现，仓库开源） |

### 0.3 三个必须先纠正的误解（否则整个规格会歪）

1. **Voyager 没有让动作空间演化。** 它的动作空间是"代码"（`V1`），但**原语全是作者手写固定的**（`V14`：`exploreUntil` / `mineBlock` / `craftItem` / `placeItem` / `smeltItem` / `killMob` / `getItemFromChest` / `depositItemIntoChest` + 17 个 Mineflayer API）。LLM 只做**组合**，从不被允许发明新原语。**我们能抄的是它的"回路形状"，不是它的"演化"。**（详见 §1.1）
2. **Re3 的 "Rewrite" 不是改写，是重排序。** 原文：`Our Rewrite module models this rewriting process by reranking Draft module outputs`（`E1`）。真正做"改写"的是 Edit 模块，而消融显示 **Edit 贡献很小**，论文自陈它"may struggle with larger changes"、"sometimes makes undesired edits or additions"（`E8`）。
3. **ReAct 没有"防止模型不产出 Action"的显式机制。** 论文里**没有**任何 "you must output an action" 指令。它靠的是**槽位语法 + 环境握手**（`R4`/`R5`/`R6`）。照抄时抄结构，不要抄"写一句自然语言约束"这个动作。

### 0.4 ToT 读数的地位

用户提到「我们项目里 ToT 的读数：改写型环节的 refine 不弱于纯搜索」——
**ToT（Yao et al., arXiv 2305.10601）不在本次精读清单内，我没有读它。**
本文件凡涉及 ToT 的对照，一律标注 **【未核·用户内部读数】**，只用来与 Re3/GoT 的**结构性**结论做方向性对照，不作为证据。

---

## 1. §1 动作空间可演化的规格（主干：Voyager 迭代提示 + 技能库）

### 1.1 先明确 Voyager 到底给了什么、没给什么

| Voyager 的机制 | 逐字依据 | 它**给**了我们什么 | 它**没**给什么 |
|---|---|---|---|
| 动作空间 = 代码 | `V1`「We opt to use code as the action space instead of low-level motor commands」 | 动作可以**有时间跨度、可组合** | ❌ 动作空间是图灵完备 ⇒ 无界。**不是**"有界但可扩展" |
| 控制原语**手写固定** | `V14`（8 个自实现原语 + 17 个 Mineflayer API，§A.4.1(2)(3)） | — | ❌ **LLM 从不发明新原语**。技能库增长的是**函数实例/组合**，不是**原语** |
| 迭代提示（三类反馈 + 4 轮） | `V3`/`V5`/`V7` | **失败 → 解释 → 重生成 → 验证 → 入库** 的完整回路 | ❌ 没有"失败 → **新动作**（新原语）"这一步 |
| 技能库（描述嵌入 + top-5 检索） | `V6`/`V11`/`V16` | **库 = 描述的向量 → 程序**；检索 top-5，命中 96.5% | ❌ 库里的东西全是**程序**，不是**能力声明** |
| 课程目标恒定 | `V10`（Prompt 1 第一句 "My ultimate goal is to discover as many diverse things as possible"） | **目标固定、手段演化** —— 治"中庸"的关键模式 | — |
| 任务格式 | `V10` 准则 3：「"Mine [quantity] [block]", "Craft [quantity] [item]" … It should be a single phrase」 | 任务 = **带参模板的一次实例化** | ❌ 模板**集**是固定的（6 个动词） |

**结论【我们的】**：Voyager 的可演化发生在**实例层**（技能库），**不在原语层**。
我们项目要的是**原语层/动作集层**的演化 —— Voyager **没有**给这个能力，**必须由我们自己补**（§1.4 的 L1 层）。

### 1.2 Voyager 的回路，逐字拆成 6 个可实现步骤

来源：`V7`（Algorithm 1 完整伪代码）+ `V5`（三类反馈）+ `V8`（提示槽位）

```
【文献】Voyager Algorithm 1（V7，L939-L963）翻译成我们的语义。
      （下方为**改写排版**：原文把 tuple 赋值拆成 3 行、变量名保留原样；语义未变）

for i in range(4):                              # 最多 4 轮修同一个目标
    skills = skill_manager.retrieve_skills(task, environment_feedback)
    code   = action_agent.generate_code(task, code,            # 上一轮产物
                                        environment_feedback,  # 环境反馈
                                        execution_errors,     # 执行错误
                                        critique,             # 自验证评语
                                        skills)
    # 原文为 3 行 tuple 赋值：
    #   (agent_state, environment_feedback, execution_errors) = environment.step(code)
    (agent_state, environment_feedback, execution_errors) = environment.step(code)
    success, critique = critic_agent.check_task_success(task, agent_state)
    if success: break
if success:
    skill_manager.add_skill(code)               # ← 只有验证通过才入库
    curriculum_agent.add_completed_task(task)
else:
    curriculum_agent.add_failed_task(task)
```

拆成 6 步（**每步都标了出处**）：

| # | 步骤 | 依据 | 我们的实现要点 |
|---|---|---|---|
| S1 | **检索**（用当前目标 + 环境反馈去检索库） | `V6`「we query the skill library with the embedding of self-generated task plans and environment feedback」 | 检索键 = `embed(子目标描述 + 失败证据摘要)`；取 top-5 |
| S2 | **生成**（带上一轮产物 + 全部失败信息） | `V8` 槽位序 | 提示**固定槽序**，失败信息单独成槽 |
| S3 | **执行**（拿环境反馈 + 执行错误） | `V5`「(1) Environment feedback … (2) Execution errors」 | 我们的三通道：`tool_error` / `env_feedback` / `critique` |
| S4 | **验证**（critic 判成败 + 出 critique） | `V12`（JSON `{reasoning, success, critique}`） | 解析失败 ⇒ 记 `parse_error`，不静默当成功 |
| S5 | **入库 or 放弃** | `V7`「if success: skill_manager.add_skill(code)」/ `V5`「If the agent gets stuck after 4 rounds of code generation, then we query the curriculum for another task」 | 4 轮不通过 ⇒ **换目标**，不无限重试 |
| S6 | **记完成/记失败** | `V7` 末尾两支 | 失败也要入库**失败簇**（Voyager 没有，【我们的】） |

### 1.3 ★ 核心可抄件：失败 → 新动作的**提示槽位契约**

**这是本次精读里对我们最值钱的一块。** Voyager 不是把错误信息"重喂"给模型，而是给错误信息一个**专属槽位**，并且**强制模型先解释再计划**。

`V8`（Prompt 4，L1464-L1484）逐字：

```
At each round of conversation, I will give you
Code from the last round: …
Execution error: …
Chat log: …
[… 本块省略原文中 10 行状态槽：Biome / Time / Nearby blocks / Nearby entities / Health / Hunger / Position / Equipment / Inventory / Chests …]
Task: …
Context: …
Critique: …
You should then respond to me with
Explain (if applicable): Are there any steps missing in your plan? Why does the code not complete the task? What does the chat log and execution error imply?
Plan: How to complete the task step by step. […]
Code:
```

> ⚠️ 注意槽位序里的三处细节，全部要抄：
> 1. `Code from the last round` **在** `Execution error` **之前** —— 模型先看到自己上一轮写了什么，再看它为什么炸。
> 2. `Critique` **在最后** —— critic 的评语是**最靠后**的、也是**最该被采信**的。
> 3. `Explain` 的三个子问是**固定的三个**：`Are there any steps missing in your plan?` / `Why does the code not complete the task?` / `What does the chat log and execution error imply?` —— **不是**"请解释一下"。

#### 【可直接抄进代码】我们的 op 生成提示契约

```python
# 槽位序严格照抄 Voyager Prompt 4（V8）
OP_PROMPT_SLOTS = [
    "retrieved_ops",        # ← 对应 Voyager 的 {retrieved_skills}（V8 L1463）
    "code_from_last_round", # 上一轮产物
    "tool_error",           # ← 对应 Execution error
    "env_feedback",         # ← 对应 Chat log（Voyager 用 bot.chat 产生）
    "state",                # 当前状态（inventory/health/position 的对应物）
    "task",                 # 当前子目标
    "context",              # 上下文
    "critique",             # ← 对应 Critique（核验侧的评语）
]
# 响应格式：三段，顺序不可换
OP_RESPONSE_FORMAT = """Explain (if applicable): Are there any steps missing in your plan? \
Why does the code not complete the task? What does the feedback and error imply?
Plan: <step by step>
Action: <the op invocation, structured>"""
```

**为什么 `Explain` 必须在 `Plan` 前面**【文献 + 我们的推断】：
Voyager 的规则里 `Explain` 标了 "(if applicable)"，但**它排在 Plan 前面**，而且是**唯一**一个把"为什么失败"作为显式提问的槽。
【我们的】这正是我们要的"从失败里长出新动作"的**语义入口**：失败不是被重喂的素材，而是一个**必须被回答的问题**。如果 `Plan` 在 `Explain` 前面，模型会直接跳到"再试一次"，而"再试一次"只会收敛到中庸。

**⚠️【警示】不要抄成"给模型一句'请从失败中学习'的提示"。** Voyager 的价值在于**槽位是结构性的**（错误有自己的位置、解释有自己的位置），不在于措辞。改成自然语言提醒 = 丢掉全部收益。

### 1.4 【我们的】从"失败"到"新动作"的三级演化

Voyager 只到 L0。**这一节是我们自己的扩展**，明确标注。

```
L0  原语固定        —— Voyager 的位置：8 个手写原语 + 17 个 Mineflayer API（V14）
                    LLM 组合它们成"技能函数"，从不发明新原语
L1  动作集演化      —— 【我们的】op_template 集合可增可删（§5）
L2  结构演化        —— 【我们的·GoT 支撑】边类型可增可删（depends / aggregates / instantiates / retires）
                    加一条 aggregates 边 ⇒ volume 上升（GoT 的核心机制，G3）
L3  元演化          —— 【我们的·无来源支撑】「如何从一个失败簇生成一个 op 模板」这一步本身
                    也可以被建模成一个 op 模板，从而被改写/替换
                    ⇒ 建议 v1 不做，但**必须先把 L3 的接口留出来**，否则 L1/L2 会长成死胡同
```

#### L1：失败 → 新 op 的 5 步（【我们的】，骨架来自 `V8`/`V7`）

```
STEP 1  采集失败三元组
        failure = {op_template, params, tool_error, env_feedback, critique, state_before, state_after}
        依据：V5 的三通道（环境反馈 / 执行错误 / 自验证评语）

STEP 2  强制解释（复用 §1.3 的 Explain 槽，单独跑一轮）
        产出：explain ∈ {缺步骤 | 目标没达成 | 证据不足} × {指向什么}
        依据：V8「Why does the code not complete the task? What does the chat log and execution error imply?」

STEP 3  归类（【我们的】——Voyager 没有这一步）
        bad_params        → 同一 op，换参数重试           （不是新 op）
        missing_precond   → 给已有 op **加前置守卫**      （不是新 op）
        wrong_order       → 已有 op，换顺序                （不是新 op）
        missing_capability→ **候选新 op**                  ← 只有这一类能长出新动作
        依据：V9 规则 2「Reuse the above useful programs as much as possible」
              ⇒ 「能用已有原语拼出来就不许新造原语」这一条，
                 正是 Voyager 缺的那条护栏，我们补上。

STEP 4  构造候选 op 模板（【我们的】，字段格式见 §5.1）
        - 名字必须"有意义、任务可从名字推出"（V9 规则 11）
        - 必须声明 precondition / postcondition / checker
        - 必须挂到来源失败簇（provenance 必填）

STEP 5  试跑 + 入库闸门（§2）
        - 试跑 1 次成功 ⇒ 进入 §2 闸门
        - 4 轮上限（V5）不通过 ⇒ 候选作废，失败簇保留
```

#### 固定目标原则【文献 + 我们的推论】

`V10` Prompt 1 第一句（逐字）：
> `My ultimate goal is to discover as many diverse things as possible, accomplish as many diverse tasks as possible and become the best Minecraft player in the world.`

这个 goal **整个 run 不变**，变的是 task stream。
【我们的】映射到我们项目：
- **固定**：待回答的问题（用户给的题）、以及"有效信息维度数"这个**读数**。
- **演化**：op 模板集合、图结构、检索到的 op。
- ⛔ **不要**把"维度数"当**优化目标**写进提示 —— 一旦目标里出现"维度数"，模型会开始**堆砌无关维度**（伪中庸 → 假多样）。**维度数只做读数，不做奖励。**

#### 渐进放量【文献 → 我们的】

`V17`（Voyager 课程 warm-up schedule，逐字）：
> `In practice, we adopt a warm-up schedule to gradually incorporate the agent's state and the additional context into the prompt based on how many tasks the agent has completed. This ensures that the prompt is exposed to increasing amounts of information over the exploration progress and therefore begins with basic skills and progressively advances towards more intricate and diverse ones.`

【我们的】op 模板也要 warm-up：前 N 次只暴露 3 个基础 op（`GEN_PLAIN` / `EXTRACT` / `VERIFY`），之后按"被成功使用的次数"逐步放开新 op。否则 12 个 op 一次性进提示，每个都不被真正掌握。

---

## 2. §2 「可执行性优先」的筛选判据（怎么判一个新动作跑得通）

### 2.1 三篇各自的判据（先摆事实）

| 来源 | 判据 | 确定性？ | 缺陷 |
|---|---|---|---|
| **Voyager**（`V7`） | 执行不报错 **且** GPT-4 critic 在最终状态上给 `success=true` | ❌ 半 —— 判成败靠 LLM critic | 无 ground truth；critic 自身有幻觉底噪（`R7`：CoT 假阳率 14% vs ReAct 6%） |
| **Voyager 课程**（`V10` 准则 8） | 「Tasks that require information beyond the player's status to verify should be avoided」 | ✅ 结构性 | 这是**任务层**的可判定性，不是动作层的 |
| **GoT 仓库**（`C12`） | `test_sorting`：`sorted_list == correct_list`，**精确匹配** | ✅ 完全确定 | 只适用"有标准答案"的题 |
| **GoT 仓库**（`C13`） | `num_errors`：error-scope（错序对数 + 频次偏差），**部分给分** | ✅ 完全确定 | 需要 ground truth |
| **GoT 仓库**（`C5`） | `KeepValid`：`if not thought.validated or thought.valid` | ✅ 规则 | **未验证的也保留** —— 宽松 |
| **GoT 仓库**（`C9`） | `ValidateAndImprove`：validate → 不过就改写，**最多 `num_tries=3`** | ✅ | 3 次后仍不过就放弃 |
| **GoT 仓库**（`C6`） | `GroundTruth`：确定性 callable；**异常 ⇒ `solved=False`** | ✅ | — |

### 2.2 ★ 我们要用的闸门（4 闸 + 1 反例）

**设计原则【我们的】**：把 Voyager 的"LLM critic 判生死"**降级为旁证**，把 GoT 的"确定性 checker"**升为主判据**，并加一条**两家都没有的反例检查**。

| 闸 | 检查 | 判定 | 依据 |
|---|---|---|---|
| **G0 Schema** | 模板能解析；参数满足 schema（类型/域/默认值）；名字有意义 | 确定性 | `V9` 规则 1/11；`C2`（OperationType 枚举） |
| **G1 Executable** | 实例化后在沙箱**跑完不抛异常**，输出结构合法 | 确定性 | `V5`「Execution errors from the program interpreter」；`C5` 的 `thought.valid` |
| **G2 Postcondition** | `checker(state_after) == True` | 确定性 | `C12` 精确匹配；`V10` 准则 8 |
| **G2b 反例（★）** | `checker(state_after_corrupted) == False`，其中 corrupted = 对成功输出做**最小破坏** | 确定性 | **两家都没有**；见 §2.3 |
| **G3 Reuse** | 该模板在**别的**上下文里至少成功过一次 | 半确定 | `V9` 规则 3「Your function will be reused for building more complex functions」 |
| **G4 Critic（旁证）** | LLM critic 输出 JSON `{reasoning, success, critique}`；`success` 只做**参考**，`critique` 才是下一轮的输入 | 模型 | `V12`/`V13` |
| **预算闸** | 单个候选最多 4 轮修复（`V5`） | — | `V5` |

### 2.3 ★ G2b 反例检查：为什么必须有，以及怎么实现

**问题**：`checker` 如果对任何东西都返回 True，它就是废的。GoT 的精确匹配 checker 天然免疫（因为它跟 ground truth 比），但**任何 LLM-based checker 都不免疫**——而我们的很多 op 没有标准答案，checker 必然部分依赖 LLM 或规则。

**做法**：入库前，对该 op 的**一次成功输出**做**最小破坏**，要求 checker 必须翻脸。

```python
# 【我们的】G2b：反例检查（可执行）
CORRUPTIONS = [
    ("truncate",   lambda s: s[: max(1, len(s)//2)]),
    ("drop_tail",  lambda s: "\n".join(s.split("\n")[:-1])),
    ("swap_dims",  lambda s: s.replace("dim_2", "dim_7")),   # 换掉一个维度声明
    ("negate",     lambda s: s.replace("supports", "refutes")),
    ("shuffle",    lambda s: "\n".join(reversed(s.split("\n")))),
]

def negative_control_ok(op_template, state_after, checker) -> tuple[bool, str]:
    """返回 (是否通过, 失败的破坏类型)。全部破坏都必须让 checker 翻脸。"""
    for name, corrupt in CORRUPTIONS:
        broken = corrupt(state_after)
        if broken == state_after:
            continue                      # 该破坏不适用此输出，跳过
        if checker(broken) is True:
            return False, f"checker 未能识别破坏 '{name}' → checker 无判别力"
    return True, ""
```

**为什么这条是"可执行性优先"的核心【我们的】**：
一个"看起来对但跑不通"的动作，本质就是**它的成功判据不判别**。G2b 把"看起来对"变成一个**可测的失败**。
这正是用户要的"我们的代码里怎么判『新动作可执行』"的**可落地**答案。

### 2.4 与 Voyager 的差别（一句话）

Voyager：`success = critic(task, final_state)`。
我们：`success = G0 ∧ G1 ∧ G2 ∧ G2b`，`critic` 只贡献 `critique`（下一轮的输入），**不贡献 success**。

---

## 3. §3 轮次与终止条件（ReAct / Re3 / GoT 三种对照 → 我们选哪个）

### 3.1 三种轮次结构（逐字依据）

#### (a) ReAct — **两种**轮次结构，论文明说是二选一

`R1`（L134-L135，逐字）：
> `For the tasks where reasoning is of primary importance (Figure 1(1)), we alternate the generation of thoughts and actions so that the task-solving trajectory consists of multiple thought-action-observation steps.`
> `In contrast, for decision making tasks that potentially involve a large number of actions (Figure 1(2)), thoughts only need to appear sparsely in the most relevant positions of a trajectory, so we let the language model decide the asynchronous occurrence of thoughts and actions for itself.`

| 结构 | 形态 | 出现在 | 逐字例子 |
|---|---|---|---|
| **dense** | `[Thought+Action] → [Observation] → [Thought+Action] → …` | HotpotQA / FEVER | `R4`：`Thought 1` / `I need to search Pavel Urysohn and Leonid Levin…` / `Action 1` / `Search[Pavel Urysohn]` / `Observation 1` / … |
| **sparse** | `[Thought] → [OK.] → [Action] → [Observation] → …` | ALFWorld / WebShop | `R5`：`> think: To solve the task, I need to find and take a lettuce…` / `OK.` / `go to fridge 1` / `The fridge 1 is closed.` <br> `R6`：`Action: think[B078GWRC1J and B078GTKVXY are bright citrus deodorant less then 50 dollars. I can check B078GWRC1J first.]` / `Observation: OK.` / `Action: click[B078GWRC1J]` |

**"怎么防止模型不产出 Action"——诚实答案**：
ReAct 论文里**没有**任何显式机制。真正起作用的是三件事的叠加：
1. **槽位语法**（`R4`）：few-shot 示例里 `Thought k` 后面**永远紧跟**一个 `Action k`，模型学的是这个配对。
2. **环境握手**（`R5`/`R6`）：环境**总是**回一个非空 Observation（thought 之后回 `OK.`），所以轨迹永远能往下走，模型不会卡在"没输出东西"上。
3. **Action 语法是受限的**（`R2`）：`search[entity]` / `lookup[string]` / `finish[answer]` —— 只有 3 个动作，`finish[answer]` 本身就是**终止动作**。

> **⇒ 我们的抄法**：
> - ✅ 抄：槽位语法（Thought 与 Action **同一轮 assistant 消息**内成对出现）、Action 受限语法 + 一个显式终止动作、Observation 独立成轮。
> - ✅ 抄：环境永远回非空 Observation（我们的对应物：`env_feedback` 槽永不置空；失败时回"失败原因"而不是空串）。
> - ⛔ 不抄：写"你必须输出 action"这种自然语言约束（无效）；也不要靠模型自觉。
> - ✅ 抄（工程侧补强）：**用解析器而不是自然语言当契约** —— 解析不出合法 Action ⇒ 判为"未产出 Action" ⇒ 重试或降级。这条 ReAct 没做，但它是"可判定"的前提。

#### (b) Re3 — **结构先验的固定轮次**

`E4`（L199，逐字）：
> `Thus we re-sample the initial outlines (Section 3.1) until they contain exactly three points, and generate exactly four 256-token continuations for each outline point before moving on to the next. As a story-ending mechanism, we use the GPT3-175B Insert API to complete the story to the suffix "The End."`

结构：
```
Plan（1 次）：setting + ≤3 characters + numbered outline   ← E5, V10 风格的"结构化计划"
for each outline point (×3):
    Draft: 独立生成 4 个 256-token 候选          ← E4
    Rewrite: 按 (coherence, relevance) 重排序 + 规则过滤 → 留 1 个  ← E1（注意：是重排序不是改写）
    Edit: 属性-值字典上的**局部**事实修正          ← E6（消融显示贡献小）
结束：Insert API 补到后缀 "The End."              ← E4
```
终止条件：**结构先验**（3 点 × 4 段 + 后缀），**不是**预算、**不是**"够好了"。

#### (c) GoT — **静态图即程序即终止条件**

`G6`（L989-L997，排序 32 的 GoO，逐字）：
> `1. Split the input list into two sub-lists of equal size (split_prompt)`
> `2. For each sub-list: Sort the sub-list (sort_prompt) five times; score each sort attempt; keep the best`
> `3. Merge the sorted sub-lists into one fully sorted list (merge_prompt) 10 times; score each merge attempt; keep the best`
> `4. Fix any potential mistakes in the sorted list (improve_prompt) 10 times; score each improvement attempt; keep the best`

代码侧（`C11`，`Controller.run`）：
```python
execution_queue = [op for op in self.graph.operations if op.can_be_executed()]
while len(execution_queue) > 0:
    current_operation = execution_queue.pop(0)
    current_operation.execute(self.lm, self.prompter, self.parser, **self.problem_parameters)
    for operation in current_operation.successors:
        if operation.can_be_executed():
            execution_queue.append(operation)
self.logger.info("All operations executed")
```
终止条件 = **队列空**。图是**静态**的（`C10`：`GraphOfOperations` 在执行前一次性构造完；`G2`：「The user constructs a GoO instance, which prescribes the execution plan of thought operations. The GoO is a static structure that is constructed once, before the execution starts.」）。
预算则是**横切**的（`C17`：`budget = 30` 美元；`C17` 里的 `if budget <= 0.0: break`）。

### 3.2 三者对照表

| 维度 | ReAct | Re3 | GoT | **我们选** |
|---|---|---|---|---|
| 轮次结构 | dense / sparse 二选一 | Plan→(Draft×4→Rewrite→Edit)×3→End | 静态 DAG 拓扑序 | **GoT 的图**（外层）+ **ReAct dense**（单 op 内部） |
| 谁决定"下一步做什么" | 模型（sparse 时） | 固定的 outline 顺序 | 固定的 GoO | **模型 + 硬闸门**：模型提候选，闸门过滤 |
| 终止条件 | `finish[action]` + 步数上限（7/5，`R3`） | 结构先验（3×4+后缀） | 队列空 | **三条件合取**（§3.3） |
| 分支/宽度 | 由模型自定 | 固定 4 候选 | 固定 5/10/10 次 | 由预算与闸门共同决定 |
| 失败处理 | 步数用尽 → 回退 CoT-SC | 下一个 outline 点 | 走下一个 op | **失败 → 失败簇 → 可能长出新 op**（§1.4） |

### 3.3 ★ 我们的终止条件（三条合取，任一满足即停）

```python
# 【我们的】终止判据（全部要有、且要可判定）
TERMINATION = {
  # T1 预算闸（可判定）
  "T1_budget": lambda st: (st.op_instances >= MAX_OP_INSTANCES
                            or st.llm_calls >= MAX_LLM_CALLS
                            or st.wall_clock >= MAX_SECONDS
                            or st.llm_cost_usd >= MAX_COST),
  # T2 目标达成（可判定 —— 必须走 §2 的 G2 checker，不是 critic）
  "T2_objective": lambda st: st.objective_checker(st.final_state) is True,
  # T3 ★ 思维面停滞（这是本项目独有，三篇论文都没有对应物）
  "T3_dim_stall": lambda st: (st.dimension_count(st.history[-K:])
                               == st.dimension_count(st.history[:-K])
                               and st.new_template_count(st.history[-K:]) == 0),
}
# 停止条件：T1 or T2 or T3
```

**T3 的定义与理由**：
- 「有效信息维度数」必须用**独立维度覆盖数**来算（不是答案长度、不是相似度、不是自评分）—— 理由见 §4.2。
- 停滞 = **最近 K 个 op 实例没有带来任何新维度，也没有产生任何新 op 模板**。
- 这直接对应"治搜索空间过早闭合"：**不是**停在一个平庸答案上（那要看 T2/T1），而是**停在一个连动作空间都不再扩张的状态**。
- 【未核】三篇论文都没有这个东西。GoT 的 `volume`（`G3`）是**空间侧**的指标（能有多少 thought 汇聚到一个答案），**不是**时间侧的停滞检测器。两者互补：volume 答"这答案吃进去多少信息"，T3 答"还要不要继续找"。

### 3.4 轮次骨架（可直接落代码）

```python
# 【我们的】三轮骨架：外 Voyager / 中 GoT / 内 ReAct-dense
def run_episode(problem):
    # ── 外层：Voyager 课程 + 迭代提示 ────────────────────────
    while not terminated(T1, T2, T3):
        subgoal = curriculum.propose(               # 目标固定、手段演化
            goal=problem.goal,                      # ← goal 整个 run 不变（V10）
            state=state, progress=progress)          # progress 来自 history
        for round_i in range(4):                     # ← V5 的 4 轮上限
            ops = skill_manager.retrieve(subgoal, env_feedback)   # V6 top-k
            action = action_agent.generate(          # ← §1.3 的槽位契约
                slots={..., "tool_error": err, "critique": critique})
            state, env_feedback, err = environment.step(action)   # V7
            ok, critique = verifier.check(subgoal, state)         # V12 JSON
            if ok: break
        if ok:
            skill_manager.add(action)                # ← 入库走 §2 闸门
        else:
            failure_cluster.add(...)                 # ← 失败簇（我们的扩展）
            maybe_mint_new_op_template(...)          # ← §1.4 STEP 3-5
    return final_answer
```

---

## 4. §4 改写型环节的教训（Re3 / GoT；ToT 读数为【未核】）

### 4.1 ★ 最重要的一条：**"重排序"不是"改写"，而且只有重排序有地板**

`E1`（L127-L130，逐字）：
> `The generator's first output continuation is often low-quality, even with the planning and recursive reprompting in the Plan and Draft modules. Humans may encounter a similar problem after a first draft, particularly upon receiving feedback from others, and be forced to rewrite a passage altogether.`
> `Our Rewrite module models this rewriting process by reranking Draft module outputs based on coherence with the previous passage and relevance to the current outline point (Figure 4).`

**结构事实**：Re3 在每个 outline 点**独立生成 4 个候选**（`E4`），Rewrite 只是**在这 4 个里按 (coherence, relevance) 排序取 1**。
⇒ **选择（max over N）有地板**：结果 ≥ 最好候选；改写（原地替换）**没有地板**：可能比改写前更差。

**这是"越改越平庸"的结构性解释**【我们的】：
- 原地改写 = 单步随机游走，**没有下界**，而 LLM 改写天然向**训练分布的均值**收缩 ⇒ 文本更长、更顺、更平庸。
- 选择式改写 = 在一个**固定的候选池**里取 max，**地板由构造保证**。

### 4.2 Re3 真正做"改写"的 Edit 模块：论文自己说它没用

`E7`（L372-L373，逐字）：
> `Results. Table 4 shows that both the Plan and Rewrite modules, mimicking the human planning and rewriting processes, are critical for overall plot coherence and premise relevance. However, the Edit module contributes little to these metrics.`

`E8`（L391-L393，逐字）：
> `we generally observed that it can fix isolated details but may struggle with larger changes. It also sometimes makes undesired edits or additions.`
> `Taken together, the compounding errors from the detection and correction subsystems make it difficult for our current Edit module to effectively improve factual consistency over a multiple-thousand-word horizon, without simultaneously introducing unnecessary changes.`

**可抄的**：Edit 的**作用域受限**设计（`E6`）：只维护**角色属性-值字典**，只对"被蕴含模型判为矛盾"的 (key, value) 做**受控局部编辑**（GPT3 Edit API），并且
`E6`（L151 附近）：`In steps prone to hallucination, we generate three outputs and keep only those which are repeated, or entailed by other outputs according to a BART-Large-based entailment model` ——
**三次采样取一致的那个**（自洽过滤）。

**⛔ 不可抄的**：把"LLM 直接改写答案"当主要改进手段。

### 4.3 改写型环节的卫生条款（Re3 附录 B，`E3`）—— 直接抄

`E3`（L729-L737，逐字，四类）：
1. `we filter out any empty outputs.`
2. 重复：`We simply check for repeated sequences of 5 words or more, and also check if the edit distance between any two sentences is a sufficiently small fraction of their length.`
3. 叙述风格突变：`we filter out any generations containing any of a fixed list of strings, such as "\nComment" and "copyright". For some strings which may reasonably appear in a normal story passage as well, we filter out passages if two or more appear. We also filter out generations where any paragraph contains a colon within the first few words (a likely indicator of an analysis header).`
4. 人称漂移：`we detect whether a continuation is written in first or second person by searching for the presence of "I," "we," and "you" outside of quotations and filter out such continuations.`

【我们的映射】到我们的答案改写环节：

| Re3 规则 | 我们的对应 |
|---|---|
| 空输出 | 解析失败 / 空答案 ⇒ 直接判失败，不进改写 |
| ≥5 词连续重复 | 答案内 n-gram 重复率超阈 ⇒ 判失败 |
| 句间编辑距离过小 | 相邻两段近乎重复 ⇒ 判"原地踏步" |
| 固定字符串黑名单 | 模板泄漏黑名单（`<think>` / `Here is` / `Based on the` / `总结` / `首先`…）⇒ 判格式漂移 |
| 段首几词含冒号 | 段首出现"标题式"前缀 ⇒ 判结构漂移 |
| 引号外人称 | 视角漂移（我们的答案是第三人称称述）⇒ 判风格漂移 |

**这 6 条全部是确定性的、零 LLM 成本、可以在改写前跑一遍。** ⇒ 建议做成 `pre_refine_lint(answer) -> list[Violation]`，**有 violation 就不进改写**（先修 lint 再改写）。

### 4.4 长篇生成的"长度/质量"读数（Re3 附录 F，`E9`）

`E9`（L906-L912，逐字）：
> `Here, experiment with generating from re3 using the same outlines, but with two or six 256-token passages per outline section instead. We refer to these modified version of re3 as re3-short and re3-long respectively.`
> `For the most part, the sample size of 50 stories for this comparison proved insufficient to draw clear quantitative conclusions on the impact of length on re3 story quality. However, interestingly, annotators judged the longer stories to be more interesting. Additionally, it seems intuitive that longer stories are more likely to suffer the presence of writing problems at some point in the story simply due to having more total text.`
> `Qualitatively, we also observe that the generator may become repetitive or lose the plot thread over longer time horizons, but ending generation too early can also yield stories which seem "truncated" before they reach the main plot points.`

**必须如实转述的三点**：
1. **n=50，样本量不足以得出明确量化结论**（论文自己这么说）。不能拿它当"长度无害/有害"的定量证据。
2. 方向性观察：长故事更"interesting"，但**问题总数更多**（更多文本 ⇒ 更多出错机会）；"generator may become repetitive or lose the plot thread"；**过早结束会显得 truncated**。
3. 长度和质量是**双向约束**，不是单调关系。

### 4.5 GoT 侧的对照：Improve 没有 validity 门

`C8`（`operations.py:480-533`）：`Improve` 对单条 thought 原地改写，`num_responses=1`，**没有** validity 检查。
`C9`（`operations.py:269-309`）：`ValidateAndImprove` 才有门 —— `validate_function` → 不过就改写 → **最多 `num_tries=3`**。
`G8`（GoT §7.3，逐字）：
> `The overall goal when conducting graph decomposition is to break down a task to the point, where the LLM can solve it correctly for the majority of time using a single prompt (or with a few additional improvement steps). This significantly lowers the number of improvement/refinement steps needed during the later stages of the graph exploration.`

**⇒ 推论**：GoT 自己也知道"改写步数应该尽量少"，办法是**把任务分解到一次提示就能做对**。

### 4.6 ★ 我们在改写环节要格外小心的（汇总成 6 条硬规则）

| # | 规则 | 依据 | 可判定？ |
|---|---|---|---|
| **W1** | 改写**只允许局部**：只能改被判失败的维度所覆盖的段落，其余逐字不动 | `E6`（属性-值字典式局部编辑） | ✅ |
| **W2** | 改写**前先跑 lint**（§4.3 的 6 条），有 violation 就不改 | `E3` | ✅ |
| **W3** | **没有失败维度就不进改写**（避免无意义重写） | `E8`（"unnecessary changes"） | ✅ |
| **W4** | 改写**必须带地板**：`refined.score ≥ pre_refine.score`，否则回退旧版本 | `E1`（选择的构造性地板） | ✅ |
| **W5** | 优先**选择式**：先生成 N 个候选再取 max，而不是原地改一次 | `E1`/`E4`（4 候选 + 重排序） | ✅ |
| **W6** | 改写的读数**单独报 `refine_delta`**，不折进最终答案分 | `E7`（消融必须把模块拆开读，否则贡献不可见） | ✅ |

**W4 + W5 合起来，正好同时兼容**：
- 用户的 ToT 读数「refine 不弱于纯搜索」**【未核·用户内部读数】** —— W5 把 refine 变成"选 max"，与"搜索"是同一个动作（多采样 + 取优），不冲突；
- Re3 的结构性结论（重排序有地板、原地改写没地板）—— W4 保证不退化。

**★ 最关键的一条推论**：
> **改写会拉长文本，但可能完全不增加"有效信息维度数"。**
> Re3 附录 F 正是这个失败模式的长篇版（更长 ⇒ 更多问题、可能重复、可能丢线索）。
> ⇒ **我们的"思维面"读数必须用独立维度覆盖数，不能用答案长度 / 相似度 / LLM 自评。**
> 否则我们会造出一个"越来越长、越来越顺、维度数不涨"的中庸机器 —— 那正是项目要治的病。

---

## 5. §5 我们的 7 个固定 op → 可演化动作空间

### 5.1 动作的结构（op 模板 schema）【我们的，字段格式受 Voyager 约束】

从"7 个 op 名字"升级成"**op 模板**"。**每个模板必须自带 checker**，否则进不了库（§2）。

```python
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

OpStatus = Literal["candidate", "active", "retired"]

@dataclass
class ParamSpec:
    name: str
    type: Literal["str", "int", "float", "bool", "list[str]"]
    domain: Optional[str] = None      # 取值域描述
    default: Any = None

@dataclass
class OpTemplate:
    # ── 身份 ──────────────────────────────────────────────
    name: str                            # 有意义、任务可从名字推出（V9 规则 11）
    description: str                     # ≤6 句、单行、不含名字（V9→V11 的描述规范）
    arity: int
    params: list[ParamSpec]
    # ── 可判定性 ──────────────────────────────────────────
    precondition: str                    # 状态谓词（人类可读 + 机器可解析）
    postcondition: str                   # 成功态谓词
    checker: Callable[[dict], bool]      # ★ 确定性 checker（§2 G2）
    # ── 证据约束 ──────────────────────────────────────────
    evidence_slots: list[str] = field(default_factory=list)
    #   允许读哪些依据槽；核验类 op 才能读 "evidence_raw"（§5.5）
    # ── 血缘与结构 ────────────────────────────────────────
    parents: list[str] = field(default_factory=list)   # 复用了哪些已有模板（V9 规则 2）
    created_from: Optional[str] = None   # 来源失败簇 id（必填，provenance）
    status: OpStatus = "candidate"
    # ── 度量 ──────────────────────────────────────────────
    uses: int = 0
    successes: int = 0
    dimension_contribution: int = 0      # 累计贡献的新维度数
```

**为什么是这几个字段**（逐项对应）：

| 字段 | 抄自 | 说明 |
|---|---|---|
| `description` + 嵌入 | `V11`（Prompt 5 描述规范）+ `V6`（**键 = 描述的嵌入**） | 检索键 = 描述向量；**不是**名字 |
| `checker` | `C12`/`C13` | 确定性判据 + 部分给分 |
| `precondition` / `postcondition` | `V10` 准则 8 | 「可从状态验证」从**任务层**下沉到**动作层** |
| `evidence_slots` | `R2`/`R4`/`R5`（§5.5） | 依据白名单 |
| `parents` | `V9` 规则 2「Reuse the above useful programs as much as possible」 | **新建 op 必须尽量复用旧 op** —— 这是我们补的护栏 |
| `created_from` | 【我们的】 | 没有来源的 op 不许进库（防止 op 集合无节制膨胀） |
| `status` + `uses`/`successes` | `G2`（V⁻/E⁻ 可删除）+ `C5`（KeepValid） | 退休机制（§5.4） |

### 5.2 op 实例 = 模板的一次带参调用

**Voyager 的课程任务格式就是模板实例化**（`V10` 准则 3，逐字）：
> `The next task should follow a concise format, such as "Mine [quantity] [block]", "Craft [quantity] [item]", "Smelt [quantity] [item]", "Kill [quantity] [mob]", "Cook [quantity] [food]", "Equip [item]" etc. It should be a single phrase.`

```python
@dataclass
class OpInstance:
    id: str
    template_name: str
    params: dict[str, Any]
    # 执行结果
    state_before: dict
    state_after: dict
    tool_error: Optional[str]      # ← 对应 Execution error
    env_feedback: str               # ← 对应 Chat log
    critique: str                   # ← 对应 Critique
    success: bool                   # 由 §2 闸门决定，不是 critic 决定
    new_dimensions: list[str] = field(default_factory=list)  # 本次新增的维度
    round_i: int = 0
```

**当前 7 个 op 的模板化**（示例，参数与 checker 由我们定义）：

```python
SEED_TEMPLATES = [
  OpTemplate(name="GEN_PLAIN", arity=0, params=[], postcondition="answer 存在且非空",
             checker=lambda s: bool(s.get("answer","").strip()),
             evidence_slots=[], parents=[], created_from="SEED"),
  OpTemplate(name="GEN_ANGLE", arity=1, params=[ParamSpec("angle","str")],
             postcondition="答案覆盖了指定视角的维度",
             checker=lambda s: s.get("covered_dimensions", set()) >= s.get("required_dimensions", set()),
             evidence_slots=[], parents=["GEN_PLAIN"], created_from="SEED"),
  OpTemplate(name="EXTRACT", arity=1, params=[ParamSpec("source","str")],
             postcondition="抽出的片段可溯源",
             checker=lambda s: s.get("extract_ok") is True,
             evidence_slots=["evidence_digest"], parents=[], created_from="SEED"),
  OpTemplate(name="SPLIT", arity=1, params=[ParamSpec("n","int")],
             postcondition="切成 n 份且每份非空",
             checker=lambda s: len(s.get("parts",[]))==s.get("n") and all(s.get("parts",[])),
             evidence_slots=[], parents=[], created_from="SEED"),
  OpTemplate(name="VERIFY", arity=1, params=[ParamSpec("claim","str")],
             postcondition="判定可复现（通过 / 不通过）",
             checker=lambda s: s.get("verify_verdict") in ("pass","fail"),
             evidence_slots=["evidence_raw","evidence_digest"], parents=[], created_from="SEED"),
  OpTemplate(name="MERGE", arity=2, params=[ParamSpec("parts","list[str]")],
             postcondition="合并且不丢维度",
             checker=lambda s: s.get("covered_dimensions",set()) >= s.get("pre_merge_dimensions",set()),
             evidence_slots=[], parents=[], created_from="SEED"),
  OpTemplate(name="STOP", arity=0, params=[], postcondition="终止",
             checker=lambda s: s.get("stopped") is True, created_from="SEED"),
]
```

### 5.3 两层图（GoT 异质图，`G1`）+ ★ 思维面 = volume

`G1`（L171，逐字）：
> `In certain use cases, graph nodes belong to different classes. […] GoT embraces a heterogeneous graph $G=(V,E,c)$ to model the LLM reasoning, where $c$ maps vertices $V$ into their respective classes $C$ (in the above case, it would be $C=\{plan,par\}$ ).`

**我们的两层图**：

```
节点类 C = { op_template, op_instance }
边类型 E = { depends, aggregates, instantiates, retires }

  op_template ──instantiates──▶ op_instance
  op_instance ──depends───────▶ op_instance   （前后继）
  op_instance ──aggregates────▶ op_instance   （★ MERGE 产生；缺这条边 volume 上不去）
  op_template ──retires───────▶ op_template   （退休）
```

**★ volume 定义（照抄 GoT，`G3` L259 逐字）**：
> `We define volume – for a given thought $t$ – as the number of preceding LLM thoughts that could have impacted $t$ . Formally, the volume of $t$ is the number of thoughts from which there exists a path to $t$ in the graph of thoughts.`

我们的对应：
```python
def volume(graph, node) -> int:
    """GoT volume：能沿有向边到达 node 的 op_instance 数（不含 node 本身）。
    只数 op_instance；op_template 节点是元信息，不计入。"""
    seen, stack = set(), [e for e in graph.out_edges(node) if e.edge_type == "depends"]
    while stack:
        v = stack.pop()
        if v in seen: continue
        seen.add(v)
        for e in graph.out_edges(v):
            if e.edge_type in ("depends", "aggregates"):
                stack.append(e.target)
    return len(seen)
```

**GoT 的关键读数（`G3` L263 逐字）**：
> `ToT offers a latency of $\log_{k}N$ but also has low volume. GoT is the only scheme to come with both a low latency of $\log_{k}N$ and a high volume $N$ . This is enabled by the fact that GoT harnesses aggregations of thoughts, making it possible to reach the final thought from any other intermediate thought in the graph decomposition.`

**⇒ 对我们的直接含义**：
> 如果我们现在的 7 个 op 是**链式/树式**执行的（ToT 形态），那么 `volume(answer) ≈ 深度` —— **低**。
> 想把"思维面"提上去，**不是加更多 op**，而是**让图上出现 `aggregates` 边**（即我们的 `MERGE` op 真的把多个来源汇进一个答案）。
> ⇒ **可演化动作空间的第一优先级不是"长出新 op"，而是"让图长出聚合边"**。
> 这是 GoT 相对 ToT 的**唯一**结构性增益（`G3`），也是"思维面 = 有效信息维度数"最直接可借的公式。

⚠️ **注意 volume 与"维度数"不是一回事**【我们的区分】：
- `volume` = **信息汇聚的广度**（多少个实例汇进答案）；
- `维度数` = **答案覆盖了多少个独立的有效信息维度**（质量）。
- 二者**必须同时报**。volume 高但维度数不涨 = 堆了一堆没用的东西（正是"中庸"的一种形态）。
- ⇒ 建议的复合读数：`mind_surface = dimension_count(final_answer)`，**同时**报 `volume(final_answer)` 作为**结构侧**的诊断量。

### 5.4 怎么归档（库 + 退休）

**Voyager 的库结构**（`V6` 逐字）：
> `we add it to the skill library, represented by a vector database. The key is the embedding vector of the program description (generated by GPT-3.5), while the value is the program itself.`
> 检索：`we first leverage GPT-3.5 to generate a general suggestion for solving the task, which is combined with environment feedback as the query context. Subsequently, we perform querying to identify the top-5 relevant skills.`

**我们的对应**：

```python
class OpLibrary:
    def __init__(self, embedder): self.embedder, self.store = embedder, {}   # name -> OpTemplate
    def _key(self, template) -> np.ndarray:
        # ★ 键 = 描述的嵌入（不是名字）—— 抄 V6
        return self.embedder(template.description)

    def add(self, template: OpTemplate, instances: list[OpInstance]):
        # ★ 入库闸门（§2）：G0 ∧ G1 ∧ G2 ∧ G2b
        if not self.gates_pass(template, instances): return False
        template.status = "active"
        self.store[template.name] = template
        return True

    def retrieve(self, subgoal: str, env_feedback: str, k: int = 5) -> list[OpTemplate]:
        # ★ 查询上下文 = 子目标 + 环境反馈（抄 V6）
        q = self.embedder(subgoal + "\n" + env_feedback)
        return topk(self.store.values(), q, k)          # Voyager 用 top-5（V16: 96.5% 命中）

    def retire(self, name: str, reason: str):
        """退休而非删除：保留 provenance。GoT 的 V⁻/E⁻ 删除能力（G2）提供先例。"""
        self.store[name].status = "retired"
        self.store[name].retire_reason = reason
```

**退休规则【我们的】**（ Voyager 没有；GoT 只提供了"能删"这个能力，`G2`）：
- 一个 op 模板连续 N 次被检索但都没被选中 ⇒ `retired`。
- 一个 op 模板的实例 `dimension_contribution == 0` 且用了 ≥M 次 ⇒ `retired`。
- **退休不删记录**（保留 provenance，便于失败簇分析）。
- 提示里**只放** active 的 top-k 模板（GoT 的上下文瘦身思想，`G8`）。

### 5.5 「依据包只进核验侧」——ReAct 结构的抄法

**ReAct 的事实**（`R4`/`R5`/`R6`）：工具返回**只出现在 Observation 槽**；Thought 槽里出现的是模型**自己复述/推理过的**内容（`R1` 里 "x was started in 1844" 这类抽取式 thought），**不是工具原文**。
**但 ReAct 没有强制机制** —— 它的 grounding 是**经验性**的（`R7`：CoT 假阳率 14% vs ReAct 6%，`R1` 归因于"有外部知识库可访问"），不是结构性保证。

**⇒ 我们的抄法**（结构 + 工程补强，两者都要）：

```python
# 证据槽分两级
EVIDENCE_SLOTS = {
    "evidence_raw":    [],     # ★ 原始依据：只允许 VERIFY 类 op 读
    "evidence_digest": [],     # 摘要/结构化依据：生成侧 op 可读
}
# 生成侧 op 的 prompt 里：
prompt[...]["evidence"] = digest_only(state)      # 原文不进生成侧提示
# 核验侧（VERIFY / 闸门 checker）的 prompt 里：
prompt[...]["evidence"] = full_evidence(state)    # 原文只进这里
```

**结构依据**：`R2`（Action 空间受限：只有 3 个动作）、`R4`（槽位语法）。
**工程补强【我们的】**：靠"提示里不写原文"是**约定**不是保证；要在**代码层**做槽位白名单（`OpTemplate.evidence_slots`），由 prompt builder 强制裁剪，而不是靠提示词自觉。
**⛔ 不要抄 ReAct 的"在 Thought 槽里复述事实"** —— 我们的维度读数要靠 `evidence_digest` 的**可判定**内容，复述会引入幻觉维度（**伪维度**）。伪维度会虚高"思维面"，必须靠"该维度必须可溯源到 evidence_digest 的某条 digest"来过滤。

### 5.6 完整演化回路（端到端伪码）

```python
def evolve_and_solve(problem):
    lib, failures, graph = OpLibrary(embedder), FailureClusterStore(), OpGraph()
    templates = {t.name: t for t in SEED_TEMPLATES}
    for t in templates.values(): t.status = "active"

    while not terminated(T1, T2, T3):
        subgoal = curriculum.propose(goal=problem.goal, state=state, progress=progress)

        action, err, fb, crit, ok = None, None, "", "", False
        for round_i in range(4):                                  # V5: 4 轮上限
            retrieved = lib.retrieve(subgoal, fb, k=5)             # V6: top-5
            action = generate(slots={                              # §1.3 槽位契约
                "retrieved_ops": retrieved, "code_from_last_round": action,
                "tool_error": err, "env_feedback": fb,
                "state": state, "task": subgoal, "context": ctx, "critique": crit})
            state, fb, err = environment.step(action)              # V7
            ok, crit = verifier.check(subgoal, state)              # V12 JSON（critique 用于下一轮）

            if round_i == 0 and not ok:
                # ★ 从失败里长出新动作（§1.4）
                expl = explain_failure(action, err, fb, crit)     # V8 的 Explain 槽
                kind = classify_failure(expl)                      # bad_params/missing_precond/wrong_order/missing_capability
                if kind == "missing_capability":
                    cand = mint_template(expl, parents=names_of(retrieved),
                                          created_from=failures.add(action, err, fb, crit))
                    if trial_run(cand, state, lib):                # §2 闸门
                        templates[cand.name] = cand; lib.add(cand, ...)
                break                                             # 新动作下一轮才用得上，本轮不再改
            if ok: break

        inst = record_instance(action, state, err, fb, crit, ok)
        graph.add_instance(inst, edge_type="depends")
        if ok:
            lib.add(templates[action.template_name], [inst])
        else:
            failures.add(...)

    # 收口：把多个来源用 MERGE 汇进最终答案（★ aggregates 边 = volume 的来源）
    final = merge_into_final(graph, lib)      # 产生 aggregates 边
    return final, metrics(volume(final), dimension_count(final), refine_delta, ...)
```

---

## 6. 交付摘要：本规格里哪些是抄的、哪些是我们的

### 6.1 【文献】可直接抄的（带 quote 编号）

| # | 抄什么 | 出处 |
|---|---|---|
| 1 | 失败信息**独占槽位** + `Explain` 槽在 `Plan` 之前 + Explain 的三个固定子问 | `V8` |
| 2 | 4 轮修复上限，超限换目标 | `V5`/`V7` |
| 3 | 入库前必须**验证通过**；未通过的上一轮产物**不入库** | `V7`（算法）+ `V9` 规则 4 |
| 4 | 库键 = **描述的嵌入**；检索查询 = 子目标 + 环境反馈；top-5 | `V6`/`V11`/`V16` |
| 5 | 描述规范：不提名字、≤6 句、单行 | `V11`（Prompt 5 规则 1/4/5） |
| 6 | op 必须可复用、优先复用已有原语、名字有意义 | `V9` 规则 2/3/11 |
| 7 | 目标固定、任务流演化 | `V10`（Prompt 1 首句） |
| 8 | 只做**可从状态验证**的事 | `V10` 准则 8 |
| 9 | 提示槽位序：Thought+Action 同一轮、Observation 独立轮、Action 语法受限 + 终止动作 | `R4`/`R5`/`R6`/`R2` |
| 10 | 改写 = **多候选 + 重排序**（有地板），不做原地改写 | `E1`/`E4` |
| 11 | 改写前的 6 条确定性 lint | `E3` |
| 12 | 局部编辑 + 三次采样取自洽 | `E6` |
| 13 | 图 = 有向图、**异质图**（多节点类）、可增可删 | `G1`/`G2` |
| 14 | **volume** 定义与"聚合边抬高 volume" | `G3` |
| 15 | 确定性 checker（精确匹配 + 部分给分）+ 异常即失败 | `C12`/`C13`/`C6` |
| 16 | 保留规则 `not validated or valid`；改进最多 3 次 | `C5`/`C9` |

### 6.2 【我们的】文献没有、由项目目标推出来的

| # | 我们的设计 | 为什么文献没有 |
|---|---|---|
| 1 | **失败分类**（bad_params / missing_precond / wrong_order / missing_capability）—— 只有第 4 类能长出新 op | Voyager 只区分"成功/失败"，无归因层 |
| 2 | **op 模板带 `checker` + `precondition`/`postcondition`** | Voyager 的 checker 是 critic（无 ground truth）；GoT 的 checker 是任务特定的、非模板化 |
| 3 | **G2b 反例检查**（checker 必须在被破坏输出上翻脸） | 两家都没有 |
| 4 | **两层图**（`op_template` + `op_instance`）+ `instantiates` 边 | GoT 的异质图是 {plan, par}，没有"元动作"层 |
| 5 | **退休机制**（`status=retired` + 使用量/维度贡献驱动） | Voyager 无退休；GoT 只提供"能删"这个原语 |
| 6 | **T3 维度停滞终止** | 三篇都没有时间侧停滞检测 |
| 7 | **"目标固定、维度数只做读数不做奖励"** | Voyager 的 goal 固定原则是隐式的，我们把它显式化并加"不作为奖励" |
| 8 | **evidence 槽双层（raw / digest）+ 代码层白名单** | ReAct 靠约定，不靠机制 |
| 9 | **refine_delta 单独报** | Re3 消融是模块级、不是 refine 级 |
| 10 | **op 模板 warm-up** | Voyager 只对课程上下文 warm-up（`V17`），未对技能库做 |

### 6.3 【警示】本规格刻意**没有**采纳的东西

| 东西 | 为什么不要 |
|---|---|
| Voyager 的"code 即动作空间" | 图灵完备 ⇒ 动作空间无界 ⇒ **恰恰不是"可演化"**，且无法做"可判定的成败"。我们只抄它的**回路形状** |
| Voyager 的"critic 判成败" | 无 ground truth；critic 自身有幻觉底噪（`R7`） |
| Re3 的 Edit 式"LLM 原地改写" | 论文自陈：贡献很小、可能引入不必要改动、检测+纠正复合错误（`E7`/`E8`） |
| GoT 的裸 `Improve`（无 validity 门） | `C8` 无门；我们要用 `ValidateAndImprove` 的门（`C9`） |
| ReAct 的"Thought 里复述事实" | 会产生**伪维度**，虚高思维面 |

### 6.4 落地顺序建议

| 阶段 | 做什么 | 依赖 |
|---|---|---|
| **P0**（1 天） | 提示改槽位契约（§1.3）；加 `Explain` 槽并强制在 `Plan` 之前 | 无 |
| **P1**（2–3 天） | op 模板化（§5.1/5.2）+ checker 字段 + **G2b 反例检查**（§2.3） | P0 |
| **P2**（2 天） | 两层图 + `aggregates` 边 + `volume()`（§5.3）；**先把 MERGE 真的用起来** | P1 |
| **P3**（3 天） | 失败簇 + 失败分类 + `mint_template`（§1.4）+ 退休机制（§5.4） | P1/P2 |
| **P4**（2 天） | refine 走"候选池 + 地板 + lint"（§4.6 的 W1–W6）+ `refine_delta` 读数 | P1 |
| **P5**（1 天） | T3 终止 + 复合读数（维度数 / volume / refine_delta 三件套） | P2–P4 |

---

## 7. 已知缺口（诚实清单）

1. **ToT 未读**（不在本次清单）。「refine 不弱于纯搜索」是用户内部读数，本文件只做方向性对照。
2. **Re3 的读数强度弱**（n=50 故事 × 3 人，人工 pairwise，非受控）。§4 里关于"改写型环节"的结论主要靠**结构事实**（重排序 vs 原地改写、局部 vs 全局、有地板 vs 没地板），不靠它的效应量。
3. **Re3 附录 F 的长度结论是"样本量不足"的定性观察**，不能当定量证据（论文自己这么说）。
4. **venue 未核**（arXiv API 的 `journal_ref`/`comment` 全空）。NeurIPS 2023 / ICLR 2023 / EMNLP 2022 / AAAI 2024 的说法**未在本次抓取中验证**。
5. **GoT 的数字是 GPT-3.5 上的**（`G5`：temperature 1.0、4k context、100 样本/任务）；论文明确说因预算限制没跑前沿模型。我们若换模型，量级可能变。
6. **Voyager 的所有读数都是 Minecraft 域**的；把"4 轮上限""top-5 检索""描述嵌入做键"搬到我们域，**超参必须重新调**（Voyager 的 4/5 是该域的，不是普适常数）。
7. **本规格的 P0–P5 全部未实现、未验证**。这是规格书，不是实验报告。

---

## 8. 自查表（本文件的每一处外部断言都已程序核对）

**核对脚本与结果**（可复现；脚本在 `/workspace/lab/tmp/`）：

| 检查项 | 方法 | 结果 |
|---|---|---|
| 4 篇全文完整 | `curl -sIL` 取 `Content-Length` vs 落盘字节数；并检查结尾 `</html>` | 4/4 **COMPLETE**（2210.03629 546946/546946；2210.06774 894964/894964；2305.16291 1361269/1361269；2308.09687 849722/849722） |
| 引用编号完整 | 正则抽出本文件里所有 `[VREGC]\d+` 引用，逐一在 quotes 文件的 `### <id>` 标题里查 | 47 个引用 **全部命中**（唯一的 `G0` 是 §2.2 的闸门名 `G0 Schema`，非引用编号） |
| quotes 文件逐字性 | 对每个 `L<n> | …` 行，断言其正文能在对应源文件（`txt_*.txt` / GitHub raw）中**原样子串命中** | **1449 / 1449 命中，0 失配** |
| 本文件内的论文引文逐字性 | 抽出全部 `> ` 块引用与无标签代码块，做归一化（去 markdown 标记、直/弯引号统一）后子串匹配 | 23 条：**22 条完全命中**，1 条（GoT 异质图）为**显式 `[…]` 省略**，两段均命中 |
| 编码污染 | 全文扫描 `U+FFFD` | 两份文件均为 **0** |
| 数字核对 | 逐条回查原文行号：96.5%（V16, L2066）／14% vs 6%（R7, L253）／100 样本 + temp 1.0 + 4k（G5, L285）／3 点 × 4 段 256-token（E4, L199）／budget=30（C17, L726）／`not validated or valid`（C5, L755-759）／`num_tries=3`（C9, L280）／8+17 个原语（V14, L1212-1264） | 全部命中 |

**本文件里**没有**被程序核对**的部分（属设计主张，不属外部事实）：
§1.4 的失败四分类、§2.2 的四闸门、§2.3 的 G2b 反例检查、§3.3 的 T1/T2/T3 终止判据、§5.1 的 op 模板 schema、§5.3 的两层图与 `volume()` 实现、§5.4 的退休规则、§4.6 的 W1–W6、§6.2 的十条"我们的"、§6.4 的 P0–P5 排期。
**这些是规格，不是实验结果。**
