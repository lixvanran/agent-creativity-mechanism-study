# DEEP-06-07-17-04 — 逐字摘录（Voyager / ReAct / Re3 / GoT + spcl/graph-of-thoughts）

> 配套规格：`/workspace/lab/routes/LIT/DEEP-06-07-17-04-ReAct-Re3-GoT-Voyager-spec.md`
> 采集时间：2026-10-21（沙盒）

## 0. 来源与核对（全部为本次实抓，非记忆）

### 0.1 标签核对结果

| 任务书给的 ID | 实际标题 | 实际作者 | 核对结论 |
|---|---|---|---|
| `2305.16291` | **Voyager: An Open-Ended Embodied Agent with Large Language Models** | Guanzhi Wang, Yuqi Xie, Yunfan Jiang, Ajay Mandlekar, Chaowei Xiao, Yuke Zhu, Linxi "Jim" Fan, Anima Anandkumar | ✅ 确为 Voyager。**不是** "Lost in the Middle" |
| `2210.03629` | **ReAct: Synergizing Reasoning and Acting in Language Models** | Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, Yuan Cao | ✅ 确为 ReAct。**不是** Re3 |
| `2210.06774` | **Re3: Generating Longer Stories With Recursive Reprompting and Revision** | Kevin Yang, Yuandong Tian, Nanyun Peng, Dan Klein | ✅ 确为 Re3 |
| `2308.09687` | **Graph of Thoughts: Solving Elaborate Problems with Large Language Models** | Maciej Besta, Nils Blach, Ales Kubicek, Robert Gerstenberger, Michal Podstawski, Lukas Gianinazzi, Joanna Gajda, Tomasz Lehmann, Hubert Niewiadomski, Piotr Nyczyk, Torsten Hoefler | ✅ 确为 GoT |
| `spcl/graph-of-thoughts` | 仓库 | ETH Zurich / SPCL（main author: Nils Blach） | ✅ 确为 GoT 官方实现 |

**任务书里 4 个 arXiv ID 全部正确**；唯一需要修的是「Lost in the Middle」这个误挂（它对应 arXiv 2307.03172 *Lost in the Middle: How Language Models Use Long Contexts*，Liu et al.，**不在本次精读范围内**）。

**venue 核对**：arXiv API 的 `journal_ref` / `comment` 字段在这 4 条上**全部为空**。
- Voyager：NeurIPS 2023（Outstanding Paper / D&B）。**此信息来自 arXiv API 返回的空 comment 之外 ⇒ 未在本次抓取中验证**，以论文正文/官网为准。
- ReAct：ICLR 2023。
- Re3：EMNLP 2022。
- GoT：AAAI 2024。
⇒ 上述 4 条 venue 均**未经本次抓取核实**（arXiv API 字段为空）。本文件因此不把 venue 当作已核事实。

### 0.2 抓取方式（可复现）

- 论文正文：`curl https://export.arxiv.org/api/query?id_list=<id>` 核对元数据；
  `curl https://arxiv.org/html/<id>` 抓 LaTeXML HTML 全文（**用 `curl -C -` 循环续传直到字节数 == Content-Length**；Voyager 首次只拿到 872076/1361269 字节，GoT 829667/849722，均续传 1 次到位）。
- 纯文本化：`/workspace/lab/tmp/h2t.py`（剥标签、保留 `<math alttext>`、行内去缩进、丢弃空行）。
- 仓库：GitHub REST API `contents` + `git/trees?recursive=1`（匿名 API 403 限流，用 `${GITHUB_TOKEN_LIXVANRAN}` 认证）。
- 全文 4 篇均读到，**没有**任何一篇只读到摘要。ToT（Yao et al. 2305.10601）**不在本次精读清单内**，凡涉及 ToT 的读数一律标注为"用户项目内部读数，本次未核"。

### 0.3 逐字性声明

以下所有代码块为**逐字**摘录，行首 `L<n> | ` 是本工具加的行号前缀，正文部分未经改写。
- 论文源是 arXiv 的 **LaTeXML HTML 渲染**，不是 PDF；因此引号字形（`'` → `’`）、破折号、表格竖线可能与 PDF 排版不同，**逐字引用时以 HTML 渲染为准**。
- LaTeXML 渲染会把跨页表格/附录的翻页标记（"Continued on next page" / "Continued from previous page"）**插进正文中间**。这些行已用 `[LaTeXML-PAGEBREAK-ARTIFACT]` 前缀标出，**不是论文内容**，不要引用。
- 仓库源是 GitHub raw 原文，行号与网页上的 blob 一致。


---

## 1. Voyager（arXiv 2305.16291v2，v2 = 2023-10-19）

### V1 — 动作空间 = code（**关键：这是 Voyager 没有真正让动作空间演化的根因**）

<!-- lines 99-99 of txt_2305.16291.txt -->
```
L99 | We opt to use code as the action space instead of low-level motor commands because programs can naturally represent temporally extended and compositional actions [16, 22], which are essential for many long-horizon tasks in Minecraft.
```


### V2 — 摘要：三个部件（自动课程 / 可执行代码技能库 / 迭代提示）

<!-- lines 84-88 of txt_2305.16291.txt -->
```
L84 | We introduce Voyager, the first LLM-powered embodied lifelong learning agent in Minecraft that continuously explores the world, acquires diverse skills, and makes novel discoveries without human intervention. Voyager consists of three key components: 1) an automatic curriculum that maximizes exploration, 2) an ever-growing skill library of executable code for storing and retrieving complex behaviors, and 3) a new iterative prompting mechanism that incorporates environment feedback, execution errors, and self-verification for program improvement.
L85 | Voyager interacts with GPT-4 via blackbox queries, which bypasses the need for model parameter fine-tuning. The skills developed by Voyager are temporally extended, interpretable, and compositional, which compounds the agent’s abilities rapidly and alleviates catastrophic forgetting.
L86 | Empirically, Voyager shows strong in-context lifelong learning capability and exhibits exceptional proficiency in playing Minecraft.
L87 | It obtains $3.3\times$ more unique items, travels $2.3\times$ longer distances, and unlocks key tech tree milestones up to $15.3\times$ faster than prior SOTA. Voyager is able to utilize the learned skill library in a new Minecraft world to solve novel tasks from scratch, while other techniques struggle to generalize.
L88 | Figure 1: Voyager discovers new Minecraft items and skills continually by self-driven exploration, significantly outperforming the baselines. X-axis denotes the number of prompting iterations.
```


### V3 — 为什么需要迭代提示：LLM 一次写不对代码

<!-- lines 140-147 of txt_2305.16291.txt -->
```
L140 | We introduce an iterative prompting mechanism for self-improvement through three types of feedback:
L141 | (1)
L142 | Environment feedback, which illustrates the intermediate progress of program execution (Fig. 5, left). For example, “I cannot make an iron chestplate because I need: 7 more iron ingots” highlights the cause of failure in crafting an iron chestplate. We use bot.chat() inside control primitive APIs to generate environment feedback and prompt GPT-4 to use this function as well during code generation;
L143 | (2)
L144 | Execution errors from the program interpreter that reveal any invalid operations or syntax errors in programs, which are valuable for bug fixing (Fig. 5, right);
L145 | (3)
L146 | Self-verification for checking task success. Instead of manually coding success checkers for each new task proposed by the automatic curriculum, we instantiate another GPT-4 agent for self-verification. By providing Voyager’s current state and the task to GPT-4, we ask it to act as a critic [47, 48, 49] and inform us whether the program achieves the task. In addition, if the task fails, it provides a critique by suggesting how to complete the task (Fig. 6). Hence, our self-verification is more comprehensive than self-reflection [30] by both checking success and reflecting on mistakes.
L147 | During each round of code generation, we execute the generated program to obtain environment feedback and execution errors from the code interpreter, which are incorporated into GPT-4’s prompt for the next round of code refinement. This iterative process repeats until self-verification validates the task’s completion, at which point we add this new skill to the skill library and ask the automatic curriculum for a new objective (Fig. 2). If the agent gets stuck after 4 rounds of code generation, then we query the curriculum for another task. This iterative prompting approach significantly improves program synthesis for embodied control, enabling Voyager to continuously acquire diverse skills without human intervention.
```


### V4 — 技能库的 5 个提示组件（含「检索到的技能」与「上一轮生成的代码」）

<!-- lines 126-139 of txt_2305.16291.txt -->
```
L126 | The input prompt to GPT-4 consists of the following components:
L127 | (1)
L128 | Guidelines for code generation, such as “Your function will be reused for building more complex functions. Therefore, you should make it generic and reusable.”;
L129 | (2)
L130 | Control primitive APIs, and relevant skills retrieved from the skill library, which are crucial for in-context learning [36, 37, 38] to work well;
L131 | (3)
L132 | The generated code from the last round, environment feedback, execution errors, and critique, based on which GPT-4 can self-improve (Sec. 2.3);
L133 | (4)
L134 | The agent’s current state, including inventory, equipment, nearby blocks and entities, biome, time, health and hunger bars, and position;
L135 | (5)
L136 | Chain-of-thought prompting [46] to do reasoning before code generation.
L137 | We iteratively refine the program through a novel iterative prompting mechanism (Sec. 2.3), incorporate it into the skill library as a new skill, and index it by the embedding of its description (Fig. 4, top). For skill retrieval, we query the skill library with the embedding of self-generated task plans and environment feedback (Fig. 4, bottom). By continuously expanding and refining the skill library, Voyager can learn, adapt, and excel in a wide spectrum of tasks, consistently pushing the boundaries of its capabilities in the open world.
L138 | 2.3 Iterative Prompting Mechanism
L139 | Figure 5: Left: Environment feedback. GPT-4 realizes it needs 2 more planks before crafting sticks. Right: Execution error. GPT-4 realizes it should craft a wooden axe instead of an acacia axe since there is no acacia axe in Minecraft. We only display the partial prompt for brevity. The full prompt structure for code generation is in Appendix, Sec. A.4.
```


### V5 — 迭代提示的三种反馈 + 4 轮上限（**失败→新动作的回路本体**）

<!-- lines 141-148 of txt_2305.16291.txt -->
```
L141 | (1)
L142 | Environment feedback, which illustrates the intermediate progress of program execution (Fig. 5, left). For example, “I cannot make an iron chestplate because I need: 7 more iron ingots” highlights the cause of failure in crafting an iron chestplate. We use bot.chat() inside control primitive APIs to generate environment feedback and prompt GPT-4 to use this function as well during code generation;
L143 | (2)
L144 | Execution errors from the program interpreter that reveal any invalid operations or syntax errors in programs, which are valuable for bug fixing (Fig. 5, right);
L145 | (3)
L146 | Self-verification for checking task success. Instead of manually coding success checkers for each new task proposed by the automatic curriculum, we instantiate another GPT-4 agent for self-verification. By providing Voyager’s current state and the task to GPT-4, we ask it to act as a critic [47, 48, 49] and inform us whether the program achieves the task. In addition, if the task fails, it provides a critique by suggesting how to complete the task (Fig. 6). Hence, our self-verification is more comprehensive than self-reflection [30] by both checking success and reflecting on mistakes.
L147 | During each round of code generation, we execute the generated program to obtain environment feedback and execution errors from the code interpreter, which are incorporated into GPT-4’s prompt for the next round of code refinement. This iterative process repeats until self-verification validates the task’s completion, at which point we add this new skill to the skill library and ask the automatic curriculum for a new objective (Fig. 2). If the agent gets stuck after 4 rounds of code generation, then we query the curriculum for another task. This iterative prompting approach significantly improves program synthesis for embodied control, enabling Voyager to continuously acquire diverse skills without human intervention.
L148 | Figure 6: Self-verification examples. We only display the partial prompt for brevity. See Appendix, Sec. A.5 for the full prompt structure.
```


### V6 — 技能库检索：嵌入向量 = 程序描述的嵌入；top-5

<!-- lines 122-125 of txt_2305.16291.txt -->
```
L122 | 2.2 Skill Library
L123 | Figure 4:
L124 | Skill library. Top: Adding a new skill. Each time GPT-4 generates and verifies a new skill, we add it to the skill library, represented by a vector database. The key is the embedding vector of the program description (generated by GPT-3.5), while the value is the program itself. Bottom: Skill retrieval. When faced with a new task proposed by the automatic curriculum, we first leverage GPT-3.5 to generate a general suggestion for solving the task, which is combined with environment feedback as the query context. Subsequently, we perform querying to identify the top-5 relevant skills.
L125 | With the automatic curriculum consistently proposing increasingly complex tasks, it is essential to have a skill library that serves as a basis for learning and evolution. Inspired by the generality, interpretability, and universality of programs [45], we represent each skill with executable code that scaffolds temporally extended actions for completing a specific task proposed by the automatic curriculum.
```


### V7 — Algorithm 1（完整伪代码：**执行 → 取反馈 → 重生成 → critic 判成败**）

<!-- lines 913-963 of txt_2305.16291.txt -->
```
L913 | Pseudocode 1: Voyager algorithm.
L914 | ⬇
L915 | def voyager(
L916 | environment, # environment that uses code as action space
L917 | curriculum_agent, # curriculum agent for proposing the next task
L918 | action_agent, # action agent for code generation
L919 | critic_agent, # critic agent for self-verification
L920 | skill_manager, # skill manager for adding new skills and skill retrieval
L921 | ):
L922 | agent_state = environment.reset()
L923 | while True:
L924 | exploration_progress = (
L925 | curriculum_agent.get_exploration_progress(
L926 | curriculum_agent.get_completed_tasks(),
L927 | curriculum_agent.get_failed_tasks(),
L928 | )
L929 | )
L930 | task = curriculum_agent.propose_next_task(
L931 | agent_state, exploration_progress
L932 | )
L933 | code = None
L934 | environment_feedback = None
L935 | execution_errors = None
L936 | critique = None
L937 | success = False
L938 | # try at most 4 rounds before moving on to the next task
L939 | for i in range(4):
L940 | skills = skill_manager.retrieve_skills(
L941 | task, environment_feedback
L942 | )
L943 | code = action_agent.generate_code(
L944 | task,
L945 | code,
L946 | environment_feedback,
L947 | execution_errors,
L948 | critique,
L949 | skills,
L950 | )
L951 | (
L952 | agent_state,
L953 | environment_feedback,
L954 | execution_errors,
L955 | ) = environment.step(code)
L956 | success, critique = critic_agent.check_task_success(
L957 | task, agent_state
L958 | )
L959 | if success:
L960 | break
L961 | if success:
L962 | skill_manager.add_skill(code)
L963 | curriculum_agent.add_completed_task(task)
```


### V8 — Prompt 4 槽位清单（**失败信息进哪几个槽**）

<!-- lines 1463-1484 of txt_2305.16291.txt -->
```
L1463 | {retrieved_skills}
L1464 | At each round of conversation, I will give you
L1465 | Code from the last round: …
L1466 | Execution error: …
L1467 | Chat log: …
L1468 | Biome: …
L1469 | Time: …
L1470 | Nearby blocks: …
L1471 | Nearby entities (nearest to farthest):
L1472 | Health: …
L1473 | Hunger: …
L1474 | Position: …
L1475 | Equipment: …
L1476 | Inventory (xx/36): …
L1477 | Chests: …
L1478 | Task: …
L1479 | Context: …
L1480 | Critique: …
L1481 | You should then respond to me with
L1482 | Explain (if applicable): Are there any steps missing in your plan? Why does the code not complete the task? What does the chat log and execution error imply?
L1483 | Plan: How to complete the task step by step. You should pay attention to Inventory since it tells what you have. The task completeness check is also based on your final inventory.
L1484 | Code:
```


### V9 — Prompt 4 的 11 条硬规则（动作的结构契约；规则 3 = 可复用性；规则 4 = 上一轮不入库）

<!-- lines 1485-1500 of txt_2305.16291.txt -->
```
L1485 | 1) Write an async function taking the bot as the only argument.
L1486 | 2) Reuse the above useful programs as much as possible.
L1487 | - Use ‘mineBlock(bot, name, count)‘ to collect blocks. Do not use ‘bot.dig‘ directly.
L1488 | - Use ‘craftItem(bot, name, count)‘ to craft items. Do not use ‘bot.craft‘ directly.
L1489 | - Use ‘smeltItem(bot, name count)‘ to smelt items. Do not use ‘bot.openFurnace‘ directly.
L1490 | - Use ‘placeItem(bot, name, position)‘ to place blocks. Do not use ‘bot.placeBlock‘ directly.
L1491 | - Use ‘killMob(bot, name, timeout)‘ to kill mobs. Do not use ‘bot.attack‘ directly.
L1492 | 3) Your function will be reused for building more complex functions. Therefore, you should make it generic and reusable. You should not make strong assumption about the inventory (as it may be changed at a later time), and therefore you should always check whether you have the required items before using them. If not, you should first collect the required items and reuse the above useful programs.
L1493 | 4) Functions in the "Code from the last round" section will not be saved or executed. Do not reuse functions listed there.
L1494 | 5) Anything defined outside a function will be ignored, define all your variables inside your functions.
L1495 | 6) Call ‘bot.chat‘ to show the intermediate progress.
L1496 | 7) Use ‘exploreUntil(bot, direction, maxDistance, callback)‘ when you cannot find something. You should frequently call this before mining blocks or killing mobs. You should select a direction at random every time instead of constantly using (1, 0, 1).
L1497 | 8) ‘maxDistance‘ should always be 32 for ‘bot.findBlocks‘ and ‘bot.findBlock‘. Do not cheat.
L1498 | 9) Do not write infinite loops or recursive functions.
L1499 | 10) Do not use ‘bot.on‘ or ‘bot.once‘ to register event listeners. You definitely do not need them.
L1500 | 11) Name your function in a meaningful way (can infer the task from the name).
```


### V10 — Prompt 1 课程准则 1–8（准则 3 = 任务的可判定性；准则 8 = **只保留可从状态验证的任务**）

<!-- lines 1092-1107 of txt_2305.16291.txt -->
```
L1092 | Failed tasks that are too hard: …
L1093 | You must follow the following criteria:
L1094 | 1) You should act as a mentor and guide me to the next task based on my current learning progress.
L1095 | 2) Please be very specific about what resources I need to collect, what I need to craft, or what mobs I need to kill.
L1096 | 3) The next task should follow a concise format, such as "Mine [quantity] [block]", "Craft [quantity] [item]", "Smelt [quantity] [item]", "Kill [quantity] [mob]", "Cook [quantity] [food]", "Equip [item]" etc. It should be a single phrase. Do not propose multiple tasks at the same time. Do not mention anything else.
L1097 | 4) The next task should not be too hard since I may not have the necessary resources or have learned enough skills to complete it yet.
L1098 | 5) The next task should be novel and interesting. I should look for rare resources, upgrade my equipment and tools using better materials, and discover new things. I should not be doing the same thing over and over again.
L1099 | 6) I may sometimes need to repeat some tasks if I need to collect more resources to complete more difficult tasks. Only repeat tasks if necessary.
L1100 | 7) Do not ask me to build or dig shelter even if it’s at night. I want to explore the world and discover new things. I don’t want to stay in one place.
L1101 | 8) Tasks that require information beyond the player’s status to verify should be avoided. For instance, "Placing 4 torches" and "Dig a 2x1x2 hole" are not ideal since they require visual confirmation from the screen. All the placing, building, planting, and trading tasks should be avoided. Do not propose task starting with these keywords.
L1102 | You should only respond in the format as described below:
L1103 | RESPONSE FORMAT:
L1104 | Reasoning: Based on the information I listed above, do reasoning about what the next task should be.
L1105 | Task: The next task.
L1106 | Here’s an example response:
L1107 | Reasoning: The inventory is empty now, chop down a tree to get some wood.
```


### V11 — Prompt 5：技能描述生成（**入库键 = 描述的嵌入**，≤6 句、单行）

<!-- lines 1518-1526 of txt_2305.16291.txt -->
```
L1518 | Prompt 5: Full system prompt for generating function descriptions. This is used when adding a new skill to the skill library. We give a one-shot example in the prompt.
L1519 | ⬇
L1520 | You are a helpful assistant that writes a description of the given function written in Mineflayer javascript code.
L1521 | 1) Do not mention the function name.
L1522 | 2) Do not mention anything about ‘bot.chat‘ or helper functions.
L1523 | 3) There might be some helper functions before the main function, but you only need to describe the main function.
L1524 | 4) Try to summarize the function in no more than 6 sentences.
L1525 | 5) Your response should be a single line of text.
L1526 | For example, if the function is:
```


### V12 — Prompt 6：自验证输出 JSON（reasoning / success / critique）

<!-- lines 1730-1739 of txt_2305.16291.txt -->
```
L1730 | Chests: If the task requires me to place items in a chest, you can find chest information here.
L1731 | Task: The objective I need to accomplish.
L1732 | Context: The context of the task.
L1733 | You should only respond in JSON format as described below:
L1734 | {
L1735 | "reasoning": "reasoning",
L1736 | "success": boolean,
L1737 | "critique": "critique",
L1738 | }
L1739 | Ensure the response can be parsed by Python ‘json.loads‘, e.g.: no trailing commas, no single quotes, etc.
```


### V13 — 自验证 few-shot 示例（**判据是「最终状态」上的可数事实**）

<!-- lines 1740-1762 of txt_2305.16291.txt -->
```
L1740 | Here are some examples:
L1741 | INPUT:
L1742 | Inventory (2/36): {’oak_log’:2, ’spruce_log’:2}
L1743 | Task: Mine 3 wood logs
L1744 | RESPONSE:
L1745 | {
L1746 | "reasoning": "You need to mine 3 wood logs. You have 2 oak logs and 2 spruce logs, which add up to 4 wood logs.",
L1747 | "success": true,
L1748 | "critique": ""
L1749 | }
L1750 | INPUT:
L1751 | Inventory (3/36): {’crafting_table’: 1, ’spruce_planks’: 6, ’stick’: 4}
L1752 | Task: Craft a wooden pickaxe
L1753 | RESPONSE:
L1754 | {
L1755 | "reasoning": "You have enough materials to craft a wooden pickaxe, but you didn’t craft it.",
L1756 | "success": false,
L1757 | "critique": "Craft a wooden pickaxe with a crafting table using 3 spruce planks and 2 sticks."
L1758 | }
L1759 | INPUT:
L1760 | Inventory (2/36): {’raw_iron’: 5, ’stone_pickaxe’: 1}
L1761 | Task: Mine 5 iron_ore
L1762 | RESPONSE:
```


### V14 — 控制原语 API 是**作者手写固定**的（§A.4.1(2)(3)：8 个自实现原语 + 17 个 Mineflayer API）

<!-- lines 1212-1264 of txt_2305.16291.txt -->
```
L1212 | Control primitive APIs implemented by us: These APIs serve a dual purpose: they demonstrate the usage of Mineflayer APIs, and they can be directly called by GPT-4.
L1213 | •
L1214 | exploreUntil(bot, direction, maxTime = 60, callback): Allow the agent to explore in a fixed direction for maxTime. The callback is the stopping condition implemented by the agent to determine when to stop exploring;
L1215 | •
L1216 | mineBlock(bot, name, count = 1): Mine and collect the specified number of blocks within a 32-block distance;
L1217 | •
L1218 | craftItem(bot, name, count = 1): Craft the item with a crafting table nearby;
L1219 | •
L1220 | placeItem(bot, name, position): Place the block at the specified position;
L1221 | •
L1222 | smeltItem(bot, itemName, fuelName, count = 1): Smelt the item with the specified fuel. There must be a furnace nearby;
L1223 | •
L1224 | killMob(bot, mobName, timeout = 300): Attack the mob and collect its dropped item;
L1225 | •
L1226 | getItemFromChest(bot, chestPosition, itemsToGet): Move to the chest at the specified position and get items from the chest;
L1227 | •
L1228 | depositItemIntoChest(bot, chestPosition, itemsToDeposit): Move to the chest at the specified position and deposit items into the chest;
L1229 | (3)
L1230 | Control primitive APIs provided by Mineflayer:
L1231 | •
L1232 | await bot.pathfinder.goto(goal): Go to a specific position. See below for how to set the goal;
L1233 | •
L1234 | new GoalNear(x, y, z, range): Move the bot to a block within the specified range of the specified block;
L1235 | •
L1236 | new GoalXZ(x, z): For long-range goals that don’t have a specific Y level;
L1237 | •
L1238 | new GoalGetToBlock(x, y, z): Not get into the block, but get directly adjacent to it. Useful for fishing, farming, filling a bucket, and using a bed.;
L1239 | •
L1240 | new GoalFollow(entity, range): Follow the specified entity within the specified range;
L1241 | •
L1242 | new GoalPlaceBlock(position, bot.world, {}): Position the bot in order to place a block;
L1243 | •
L1244 | new GoalLookAtBlock(position, bot.world, {}): Path towards a position where a face of the block at position is visible;
L1245 | •
L1246 | bot.isABed(bedBlock): Return true if bedBlock is a bed;
L1247 | •
L1248 | bot.blockAt(position): Return the block at position;
L1249 | •
L1250 | await bot.equip(item, destination): Equip the item in the specified destination. destination must be one of “hand”, “head”, “torso”, “legs”, “feet”, “off-hand”;
L1251 | •
L1252 | await bot.consume(): Consume the item in the bot’s hand. You must equip the item to consume first. Useful for eating food, drinking potions, etc.;
L1253 | •
L1254 | await bot.fish(): Let bot fish. Before calling this function, you must first get to a water block and then equip a fishing rod. The bot will automatically stop fishing when it catches a fish;
L1255 | •
L1256 | await bot.sleep(bedBlock): Sleep until sunrise. You must get to a bed block first;
L1257 | •
L1258 | await bot.activateBlock(block): This is the same as right-clicking a block in the game. Useful for buttons, doors, etc. You must get to the block first;
L1259 | •
L1260 | await bot.lookAt(position): Look at the specified position. You must go near the position before you look at it. To fill a bucket with water, you must look at it first;
L1261 | •
L1262 | await bot.activateItem(): This is the same as right-clicking to use the item in the bot’s hand. Useful for using a bucket, etc. You must equip the item to activate first;
L1263 | •
L1264 | await bot.useOn(entity): This is the same as right-clicking an entity in the game. Useful for shearing a sheep. You must get to the entity first;
```


### V15 — 消融项（skill library / env feedback / execution errors / self-verification 各可单独去掉）

<!-- lines 1984-1999 of txt_2305.16291.txt -->
```
L1984 | We ablate 6 design choices (automatic curriculum, skill library, environment feedback, execution errors, self-verification, and GPT-4 for code generation) in Voyager and study their impact on exploration performance.
L1985 | •
L1986 | Manual Curriculum: We substitute the automatic curriculum with a manually designed curriculum for mining a diamond: “Mine 3 wood log”, “Craft 1 crafting table”, “Craft 1 wooden pickaxe”, “Mine 11 cobblestone”, “Craft 1 stone pickaxe”, “Craft 1 furnace”, “Mine 3 iron ore”, “Smelt 3 iron ore”, “Craft 1 iron pickaxe”, “Mine 1 diamond”. A manual curriculum requires human effort to design and is not scalable for open-ended exploration.
L1987 | •
L1988 | Random Curriculum: We curate 101 items obtained by Voyager and create a random curriculum by randomly selecting one item as the next task.
L1989 | •
L1990 | w/o Skill Library: We remove the skill library, eliminating skill retrieval for code generation.
L1991 | •
L1992 | w/o Environment Feedback: We exclude environment feedback (chat log) from the prompt for code generation.
L1993 | •
L1994 | w/o Execution Errors: We exclude execution errors from the prompt for code generation.
L1995 | •
L1996 | w/o Self-Verification: For each task, we generate code without self-verification and iteratively refine the program for 3 rounds (equivalent to 4 rounds of code generation in total).
L1997 | •
L1998 | GPT-3.5: We replace GPT-4 with GPT-3.5 for code generation. We retain GPT-4 for the automatic curriculum and the self-verification module.
L1999 | B.4 Evaluation Results
```


### V16 — 技能检索准确率（309 样本，top-5 = 96.5%）

<!-- lines 2063-2068 of txt_2305.16291.txt -->
```
L2063 | Figure A.3: Zero-shot generalization to unseen tasks. We visualize the intermediate progress of each method on the other two tasks. We do not plot ReAct and Reflexion since they do not make any meaningful progress.
L2064 | The results of zero-shot generalization to unseen tasks for the other two tasks are presented in Fig. A.3. Similar to Fig. 8, Voyager consistently solves all tasks, while the baselines are unable to solve any task within 50 prompting iterations. Our skill library, constructed from lifelong learning, not only enhances Voyager’s performance but also provides a boost to AutoGPT [28].
L2065 | B.4.4 Accurate Skill Retrieval
L2066 | We conduct an evaluation of our skill retrieval (309 samples in total) and the results are in Table. A.4. The top-5 accuracy standing at 96.5% suggests our retrieval process is reliable (note that we include the top-5 relevant skills in the prompt for synthesizing a new skill).
L2067 | Table A.4: Skill retrieval accuracy.
L2068 | Top-1 Acc |
```


### V18 — 实验设置（模型 / 温度 / 嵌入模型）

<!-- lines 151-151 of txt_2305.16291.txt -->
```
L151 | We leverage OpenAI’s gpt-4-0314 [35] and gpt-3.5-turbo-0301 [50] APIs for text completion, along with text-embedding-ada-002 [51] API for text embedding. We set all temperatures to 0 except for the automatic curriculum, which uses temperature $=$ 0.1 to encourage task diversity. Our simulation environment is built on top of MineDojo [23] and leverages Mineflayer [52] JavaScript APIs for motor controls. See Appendix, Sec. B.1 for more details.
```


### V17 — 课程 warm-up schedule（**上下文随进度逐步放量** ⇒ op 集合也应渐进放量）

<!-- lines 1011-1013 of txt_2305.16291.txt -->
```
L1011 | A.3.3 Warm-up Schedule
L1012 | In practice, we adopt a warm-up schedule to gradually incorporate the agent’s state and the additional context into the prompt based on how many tasks the agent has completed. This ensures that the prompt is exposed to increasing amounts of information over the exploration progress and therefore begins with basic skills and progressively advances towards more intricate and diverse ones. The warm-up setting that we use across all the experiments is shown in Table. A.1.
L1013 | Table A.1: Warm-up schedule for automatic curriculum.
```

<!-- lines 1014-1067 of txt_2305.16291.txt -->
```
L1014 | Information in the prompt
L1015 | |
L1016 | After how many tasks are completed
L1017 | |
L1018 | core inventory (only including log, planks, stick, crafting table, furnace, dirt, coal, pickaxe, sword, and axe)
L1019 | |
L1020 | 0
L1021 | |
L1022 | |
L1023 | |
L1024 | equipment
L1025 | |
L1026 | 0
L1027 | |
L1028 | nearby blocks
L1029 | |
L1030 | 0
L1031 | |
L1032 | position
L1033 | |
L1034 | 0
L1035 | |
L1036 | nearby entities
L1037 | |
L1038 | 5
L1039 | |
L1040 | full inventory
L1041 | |
L1042 | 7
L1043 | |
L1044 | other blocks that are recently seen
L1045 | |
L1046 | 10
L1047 | |
L1048 | biome
L1049 | |
L1050 | 10
L1051 | |
L1052 | health bar
L1053 | |
L1054 | 15
L1055 | |
L1056 | hunger bar
L1057 | |
L1058 | 15
L1059 | |
L1060 | time
L1061 | |
L1062 | 15
L1063 | |
L1064 | additional context
L1065 | |
L1066 | 15
L1067 | |
```


---

## 2. ReAct（arXiv 2210.03629v3，v3 = 2023-03-10）


### R1 — 轮次结构：dense（推理型）vs sparse（决策型，模型自选何时出 Thought）

<!-- lines 133-140 of txt_2210.03629.txt -->
```
L133 | We show some GPT-3 (Brown et al., 2020) results in Appendix A.1, which outperforms PaLM-540B. , is prompted with few-shot in-context examples to generate both domain-specific actions and free-form language thoughts for task solving (Figure 1 (1d), (2b)). Each in-context example is a human trajectory of actions, thoughts, and environment observations to solve a task instance (see Appendix C).
L134 | For the tasks where reasoning is of primary importance (Figure 1(1)), we alternate the generation of thoughts and actions so that the task-solving trajectory consists of multiple thought-action-observation steps.
L135 | In contrast, for decision making tasks that potentially involve a large number of actions (Figure 1(2)), thoughts only need to appear sparsely in the most relevant positions of a trajectory, so we let the language model decide the asynchronous occurrence of thoughts and actions for itself.
L136 | Since decision making and reasoning capabilities are integrated into a large language model, ReAct enjoys several unique features:
L137 | A) Intuitive and easy to design: Designing ReAct prompts is straightforward as human annotators just type down their thoughts in language on top of their actions taken. No ad-hoc format choice, thought design, or example selection is used in this paper. We detail prompt design for each task in Sections 3 and 4.
L138 | B) General and flexible: Due to the flexible thought space and thought-action occurrence format, ReAct works for diverse tasks with distinct action spaces and reasoning needs, including but not limited to QA, fact verification, text game, and web navigation.
L139 | C) Performant and robust: ReAct shows strong generalization to new task instances while learning solely from one to six in-context examples, consistently outperforming baselines with only reasoning or acting across different domains. We also show in Section 3 additional benefits when finetuning is enabled, and in Section 4 how ReAct performance is robust to prompt selections.
L140 | D) Human aligned and controllable: ReAct promises an interpretable sequential decision making and reasoning process where humans can easily inspect reasoning and factual correctness. Moreover, humans can also control or correct the agent behavior on the go by thought editing, as shown in Figure 5 in Section 4.
```


### R2 — 动作空间三件套（search / lookup / **finish**）

<!-- lines 149-154 of txt_2210.03629.txt -->
```
L149 | Action Space
L150 | We design a simple Wikipedia web API with three types of actions to support interactive information retrieval:
L151 | (1) search[entity], which returns the first 5 sentences from the corresponding entity wiki page if it exists, or else suggests top-5 similar entities from the Wikipedia search engine,
L152 | (2) lookup[string], which would return the next sentence in the page containing string, simulating Ctrl+F functionality on the browser.
L153 | (3) finish[answer], which would finish the current task with answer.
L154 | We note that this action space mostly can only retrieve a small part of a passage based on exact passage name, which is significantly weaker than state-of-the-art lexical or neural retrievers. The purpose is to simulate how humans would interact with Wikipedia, and force models to retrieve via explicit reasoning in language.
```


### R3 — 步数上限与回退（7 / 5 步后切 CoT-SC）

<!-- lines 165-172 of txt_2210.03629.txt -->
```
L165 | Combining Internal and External Knowledge
L166 | As will be detail in Section 3.3, we observe that the problem solving process demonstrated by ReAct is more factual and grounded, whereas CoT is more accurate in formulating reasoning structure but can easily suffer from hallucinated facts or thoughts. We therefore propose to incorporate ReAct and CoT-SC, and let the model decide when to switch to the other method based on the following heuristics:
L167 | A)
L168 | ReAct $\to$ CoT-SC: when ReAct fails to return an answer within given steps, back off to CoT-SC. We set 7 and 5 steps for HotpotQA and FEVER respectively as we find more steps will not improve ReAct performance33
L169 | 3
L170 | Of all trajectories with correct final answers, those with 7 steps on HotpotQA and 5 steps on FEVER only take up 0.84% and 1.33% respectively..
L171 | B)
L172 | CoT-SC $\to$ ReAct: when the majority answer among $n$ CoT-SC samples occurs less than $n/2$ times (i.e. internal knowledge might not support the task confidently), back off to ReAct.
```


### R4 — HotpotQA few-shot 轨迹的**槽位语法**（Thought k / Action k / Observation k）

<!-- lines 955-975 of txt_2210.03629.txt -->
```
L955 | Were Pavel Urysohn and Leonid Levin known for the same type of work?
L956 | Thought 1
L957 | I need to search Pavel Urysohn and Leonid Levin, find their types of work, then find if they are the same.
L958 | Action 1
L959 | Search[Pavel Urysohn]
L960 | [LaTeXML-PAGEBREAK-ARTIFACT] Continued on next page
L961 | [LaTeXML-PAGEBREAK-ARTIFACT] Hotpot QA Prompts – Continued from previous page
L962 | Observation 1
L963 | Pavel Samuilovich Urysohn (February 3, 1898 - August 17, 1924) was a Soviet mathematician who is best known for his contributions in dimension theory.
L964 | Thought 2
L965 | Pavel Urysohn is a mathematician. I need to search Leonid Levin next and find its type of work.
L966 | Action 2
L967 | Search[Leonid Levin]
L968 | Observation 2
L969 | Leonid Anatolievich Levin is a Soviet-American mathematician and computer scientist.
L970 | Thought 3
L971 | Leonid Levin is a mathematician and computer scientist. So Pavel Urysohn and Leonid Levin have the same type of work.
L972 | Action 3
L973 | Finish[yes]
L974 | C.2 Fever
L975 | FEVER Prompts
```


### R5 — ALFWorld 的 ReAct 轨迹（**`> think:` 后环境回 `OK.`，然后才是 action**）

<!-- lines 1237-1272 of txt_2210.03629.txt -->
```
L1237 | Table 8: An ReAct prompt on the ALFWorld clean task.
L1238 | You are in the middle of a room. Looking quickly around you, you see a cabinet 13, a cabinet 12, a cabinet 11, a cabinet 10, a cabinet 9, a cabinet 8, a cabinet 7, a cabinet 6, a cabinet 5, a cabinet 4, a cabinet 3, a cabinet 2, a cabinet 1, a coffeemachine 1, a countertop 1, a diningtable 1, a drawer 1, a fridge 1, a garbagecan 1, a microwave 1, a shelf 3, a shelf 2, a shelf 1, a sinkbasin 1, a stoveburner 4, a stoveburner 3, a stoveburner 2, a stoveburner 1, and a toaster 1.
L1239 | Your task is to: put a clean lettuce in diningtable.
L1240 | |
L1241 | > think: To solve the task, I need to find and take a lettuce, then clean it with sinkbasin, then put it in diningtable.
L1242 | |
L1243 | OK.
L1244 | |
L1245 | > think: First I need to find a lettuce. A lettuce is more likely to appear in fridge (1), diningtable (1), sinkbasin (1), stoveburner (1-3), cabinet (1-13). I can check one by one, starting with fridge 1.
L1246 | |
L1247 | OK.
L1248 | |
L1249 | > go to fridge 1
L1250 | |
L1251 | The fridge 1 is closed.
L1252 | |
L1253 | > open fridge 1
L1254 | |
L1255 | You open the fridge 1. The fridge 1 is open. In it, you see a cup 3, a egg 2, a potato 3, and a potato 2.
L1256 | |
L1257 | > go to diningtable 1
L1258 | |
L1259 | On the diningtable 1, you see a apple 1, a bread 1, a butterknife 2, a cup 2, a fork 2, a knife 2, a knife 1, a ladle 1, a lettuce 1, a mug 2, a mug 1, a pan 2, a peppershaker 1, a spatula 3, a tomato 2, and a tomato 1.
L1260 | |
L1261 | > think: Now I find a lettuce (1). Next, I need to take it.
L1262 | |
L1263 | OK.
L1264 | |
L1265 | > take lettuce 1 from diningtable 1
L1266 | |
L1267 | You pick up the lettuce 1 from the diningtable 1.
L1268 | |
L1269 | > think: Now I take a lettuce (1). Next, I need to go to sinkbasin (1) and clean it.
L1270 | |
L1271 | OK.
L1272 | |
```


### R6 — WebShop 的 ReAct 轨迹（**Thought 走 Action 通道：`Action: think[...]` → `Observation: OK.`**）

<!-- lines 1164-1195 of txt_2210.03629.txt -->
```
L1164 | 2.7 oz, 2-Pack)
L1165 | $15.95
L1166 | Action: think[B078GWRC1J and B078GTKVXY are bright citrus
L1167 | deodorant less then 50 dollars. I can check B078GWRC1J first.
L1168 | Observation: OK.
L1169 | Action: click[B078GWRC1J]
L1170 | Observation:
L1171 | [Back to Search]
L1172 | [Prev]
L1173 | scent [assorted scents][bright citrus][calming lavender][ginger
L1174 | [fresh] simply non-scents]
L1175 | size [travel set (4-pack)][3 ounce (pack of 1)][3-ounce (2
L1176 | -pack)]
L1177 | Bright Citrus Deodorant by Earth Mama | Natural and Safe for
L1178 | Sensitive Skin, Pregnancy and Breastfeeding, Contains Organic
L1179 | Calendula 3-Ounce
L1180 | Price: $10.99
L1181 | Rating: N.A.
L1182 | [Description]
L1183 | [Features]
L1184 | [Reviews]
L1185 | [Buy Now]
L1186 | Action: think[For 3 ounce bottle of bright citrus deodorant
L1187 | for sensitive skin, the item has options ’bright citrus’
L1188 | and ’3 ounce (pack of 1)’ and seems good to buy.]
L1189 | Observation: OK.
L1190 | Action: click[bright citrus]
L1191 | Observation: You have clicked bright citrus.
L1192 | Action: click[3 ounce (pack of 1)]
L1193 | Observation: You have clicked 3 ounce (pack of 1).
L1194 | Action: click[Buy Now]
L1195 | |
```


### R7 — 幻觉读数（**CoT 14% vs ReAct 6% 假阳率** ⇒ LLM judge 本身有幻觉底噪）

<!-- lines 252-255 of txt_2210.03629.txt -->
```
L252 | Some key observations are as follows:
L253 | A) Hallucination is a serious problem for CoT, resulting in much higher false positive rate than ReAct (14% vs. 6%) in success mode, and make up its major failure mode (56%).
L254 | In contrast, the problem solving trajectory of ReActis more grounded, fact-driven, and trustworthy, thanks to the access of an external knowledge base.
L255 | B) While interleaving reasoning, action and observation steps improves ReAct’s groundedness and trustworthiness, such a structural constraint also reduces its flexibility in formulating reasoning steps, leading to more reasoning error rate than CoT.
```


### R8 — 论文对「thought / action 交错」的方法论定位（无 ad-hoc 格式设计）

<!-- lines 140-147 of txt_2210.03629.txt -->
```
L140 | D) Human aligned and controllable: ReAct promises an interpretable sequential decision making and reasoning process where humans can easily inspect reasoning and factual correctness. Moreover, humans can also control or correct the agent behavior on the go by thought editing, as shown in Figure 5 in Section 4.
L141 | 3 Knowledge-Intensive Reasoning Tasks
L142 | We begin with knowledge-intensive reasoning tasks like multi-hop question answering and fact verification.
L143 | As shown in Figure 1(1d), by interacting with a Wikipedia API, ReAct is able to retrieve information to support reasoning, while also use reasoning to target what to retrieve next, demonstrating a synergy of reasoning and acting.
L144 | 3.1 Setup
L145 | Domains
L146 | We consider two datasets challenging knowledge retrieval and reasoning: (1) HotPotQA (Yang et al., 2018), a multi-hop question answering benchmark that requires reasoning over two or more Wikipedia passages, and
L147 | (2) FEVER (Thorne et al., 2018), a fact verification benchmark where each claim is annotated SUPPORTS, REFUTES, or NOT ENOUGH INFO, based on if there exists a Wikipedia passage to verify the claim.
```


### R10 — few-shot 示例数量（HotpotQA 6 个 / FEVER 3 个）

<!-- lines 157-157 of txt_2210.03629.txt -->
```
L157 | For HotpotQA and Fever, we randomly select 6 and 3 cases22
```


### R9 — ReAct 名字的由来 / 与 CoT、Act 基线的关系（**Act = 去掉 thought 的消融**）

<!-- lines 156-164 of txt_2210.03629.txt -->
```
L156 | ReAct Prompting
L157 | For HotpotQA and Fever, we randomly select 6 and 3 cases22
L158 | 2
L159 | We find more examples do not improve performance. from the training set and manually compose ReAct-format trajectories to use as few-shot exemplars in the prompts. Similar to Figure 1(d), each trajectory consists of multiple thought-action-observation steps (i.e. dense thought), where free-form thoughts are used for various purposes. Specifically, we use a combination of thoughts that decompose questions (“I need to search x, find y, then find z”), extract information from Wikipedia observations (“x was started in 1844”, “The paragraph does not tell x”), perform commonsense (“x is not y, so z must instead be…”) or arithmetic reasoning (“1844 < 1989”), guide search reformulation (“maybe I can search/look up x instead”), and synthesize the final answer (“…so the answer is x”). See Appendix C for more details.
L160 | Baselines
L161 | We systematically ablate ReAct trajectories to build prompts for multiple baselines (with formats as Figure 1(1a-1c)):
L162 | (a) Standard prompting (Standard), which removes all thoughts, actions, observations in ReAct trajectories.
L163 | (b) Chain-of-thought prompting (CoT) (Wei et al., 2022), which removes actions and observations and serve as a reasoning-only baseline. We also build a self-consistency baseline (CoT-SC) (Wang et al., 2022a; Wang et al., 2022b) by sampling 21 CoT trajectories with decoding temperature 0.7 during inference and adopting the majority answer, which is found to consistently boost performance over CoT.
L164 | (c) Acting-only prompt (Act), which removes thoughts in ReAct trajectories, loosely resembling how WebGPT (Nakano et al., 2021) interacts with the Internet to answer questions, though it operates on a different task and action space, and uses imitation and reinforcement learning instead of prompting.
```


---

## 3. Re3（arXiv 2210.06774v3，v3 = 2022-10-22）


### E1 — Rewrite 模块**只做重排序，不做原地改写**（**改写型环节的关键结构**）

<!-- lines 127-139 of txt_2210.06774.txt -->
```
L127 | The generator’s first output continuation is often low-quality, even with the planning and recursive reprompting in the Plan and Draft modules. Humans may encounter a similar problem after a first draft, particularly upon receiving feedback from others, and be forced to rewrite a passage altogether.
L128 | Our Rewrite module models this rewriting process by reranking Draft module outputs based on coherence with
L129 | the previous passage and relevance to the current outline point (Figure 4).
L130 | We note that this Rewrite module is the only part of Re3 which uses prior story data. All of the modules which actually generate text (Plan, Draft, and to some extent Edit) do not require prior data.
L131 | Coherence Reranker.
L132 | We train a discriminative model to predict whether a continuation is coherent with the previous story. As data, we split stories from the WritingPrompts dataset Fan et al. (2018) into passages up to 1000 tokens long, labeling the ending up to 200 tokens as the gold continuation. Inspired by the contrastive learning setup of Wang et al. (2020) and Guan et al. (2020), we obtain negative examples by replacing the gold continuation with a random other continuation from either the same story or a different one. We then finetune a pretrained Longformer-Base Beltagy et al. (2020)
L133 | to classify whether a continuation is the true continuation for a given passage.
L134 | Relevance Reranker.
L135 | We train a relevance model with the same architecture as our coherence model to predict whether a continuation is relevant to the current outline point. We construct a dataset of 2000 training examples, where each example consists of a 200-token story passage from WritingPrompts and a brief summary written by GPT3-Instruct-13B. Negative examples are constructed by selecting the summary of a different passage, whether in the same story or a different one.
L136 | Additional Heuristics. Finally, we filter out continuations with some writing problems which are easy to detect via rule-based heuristics.
L137 | For example, we check for repetition issues,
L138 | e.g., repeating chunks of the structured prompt.
L139 | Similarly, to maintain consistent narration, we filter out first person continuations to enforce a consistent third person perspective. Full details in Appendix B.
```


### E2 — 重排序器 + 规则启发式过滤（Additional Heuristics）

<!-- lines 136-139 of txt_2210.06774.txt -->
```
L136 | Additional Heuristics. Finally, we filter out continuations with some writing problems which are easy to detect via rule-based heuristics.
L137 | For example, we check for repetition issues,
L138 | e.g., repeating chunks of the structured prompt.
L139 | Similarly, to maintain consistent narration, we filter out first person continuations to enforce a consistent third person perspective. Full details in Appendix B.
```


### E3 — 附录 B：全部 4 类过滤规则（**改写型环节的卫生条款**）

<!-- lines 729-737 of txt_2210.06774.txt -->
```
L729 | Appendix B Details on Additional Reranking Heuristics
L730 | We elaborate on the details of the additional filtering heuristics used in our Rewrite system (Section 3.3). There are a few broad categories of problems which we aim to largely filter out with simple heuristics.
L731 | First, we filter out any empty outputs.
L732 | Second, we aim to reduce repetition in the generation both within itself and with the prompt. We simply check for repeated sequences of 5 words or more, and also check if the edit distance between any two sentences is a sufficiently small fraction of their length.
L733 | Third, we aim to avoid jarring changes in narration. For example, this can result from the GPT3 generator reverting to the style of the prompt, with e.g., headings for story commentary or author notes. Thus we filter out any generations containing any of a fixed list of strings, such as “\nComment” and “copyright”. For some strings which may reasonably appear in a normal story passage as well, we filter out passages if two or more appear. We also filter out generations where any paragraph contains a colon within the first few words (a likely indicator of an analysis header).
L734 | Fourth, we aim to maintain consistent third person narration, so we detect whether a continuation is written in first or second person by searching for the presence of “I,” “we,” and “you” outside of quotations and filter out such continuations.
L735 | Appendix C Details on Editing System Information Extraction
L736 | As discussed in Section 3.4, the core subroutine of our Edit module’s detection system is an information extraction system for gathering structured information about a given character from a newly generated passage. We will illustrate this process using a running example taken mid-generation for a story starting from the plan shown in Table 7.
L737 | Premise: In a future world where the sun has gone out, a group of people huddle around a fire in a small cabin. They are waiting for a message from the outside that will tell them what to do next.
```


### E4 — 长度/轮次/终止条件（**3 个 outline 点 × 每点 4 段 256 token**；`The End.` 后缀收尾）

<!-- lines 197-200 of txt_2210.06774.txt -->
```
L197 | Method Instantiation. For fair comparison, it is desirable for the concrete implementation (henceforth re3) of our Re3 framework to output stories of consistent length. While Re3 is capable of generating shorter or longer stories (see e.g., our 7500-word example in Appendix M), here we aim for roughly 3000 tokens (2000-2500 words).66
L198 | 6
L199 | See Appendix F for analysis on how story length may impact quality. Thus we re-sample the initial outlines (Section 3.1) until they contain exactly three points, and generate exactly four 256-token continuations for each outline point before moving on to the next. As a story-ending mechanism, we use the GPT3-175B Insert API to complete the story to the suffix “The End.” Of course, more adaptive schemes for moving on to the next outline point and/or ending the story are possible, and we explore one possible “outline alignment” method in Appendix M.
L200 | Baselines. As prior methods focus on dramatically shorter stories compared to Re3,
```


### E5 — Draft 模块的提示构成（Relevant Context / Previous Sections' Outlines / Recent Story Summary / Current Section Outline / Autoregressive Context）

<!-- lines 112-126 of txt_2210.06774.txt -->
```
L112 | story passages before moving on to the next outline point. Each passage is generated as a fixed-length continuation from a structured prompt, which is composed by our recursive reprompting procedure as shown in Figure 3.
L113 | The prompt begins with a selection of “Relevant Context” shown at the top of Figure 3. As the story progresses, we dynamically update the list of character descriptions using a named-entity-recognition-based pipeline, which identifies new entities from each new story passage using Flair Akbik et al. (2018) and writes descriptions using GPT3-Instruct-175B. Thus “Relevant Context” initially contains all of the premise, setting, and characters shown in Figure 2, but subsequently selects only what is most relevant to the most recent story passage using a pretrained Dense Passage Retrieval (DPR) model Karpukhin et al. (2020).
L114 | The remainder of the prompt can be viewed as a coarse-to-fine description of the previous story, following the intuition that an author needs detailed information
L115 | about the most recent passage but perhaps only higher-level information about much earlier passages. As shown in Figure 3, we include ‘‘Previous Sections’ Outlines’’ as a very high-level summary of previous larger story sections, followed by a ‘‘Recent Story Summary’’ written by GPT3-Instruct-13B33
L116 | 3
L117 | As economical usage of large language models is becoming increasingly important Strubell et al. (2019), we use the 13B model where we observe it is not substantially worse.
L118 | of a few penultimate passages. At the end we repeat verbatim the immediately preceding passage as “Autoregressive Context” from which point the story should continue. Finally, to enforce relevance to the current outline point,
L119 | we include the “Current Section Outline” in the prompt just before “Autoregressive Context.”
L120 | Finally, the full prompt is fed to GPT3-175B to generate the next story passage.44
L121 | 4
L122 | This step does not use GPT3-Instruct-175B, as we observed in preliminary experiments that an earlier version of GPT3-Instruct-175B would
L123 | frequently repeat sections of the prompt. Generators other than GPT3-175B are also possible in principle:
L124 | for example, retrieval-augmented architectures like RAG Lewis et al. (2020) or architectures designed for long-range dependencies like S4 Gu et al. (2021). However, it is critical to use a sufficiently high-quality language model: even scaling down to GPT3-13B resulted in noticeably less coherent outputs in our preliminary experiments.
L125 | 3.3 Rewrite Module
L126 | Figure 4: Re3’s Rewrite module reranks the Draft module’s continuations for coherence and relevance.
```


### E6 — Edit 模块：属性-值字典 + 蕴含模型（**局部改写，作用域受限**）

<!-- lines 142-159 of txt_2210.06774.txt -->
```
L142 | In contrast to the Rewrite module which reranks complete alternate continuations, the Edit module makes local edits to further refine a passage produced by careful planning, drafting, and rewriting.
L143 | Specifically,
L144 | we aim to remove long-range factual
L145 | inconsistencies. When a human detects a small factual discontinuity upon proofreading, he or she might simply edit the offending detail, rather than making major changes to the high-level plan or doing substantial rewriting.
L146 | Our Edit module mimics this process in two steps: detecting factual inconsistencies, and correcting them.
L147 | Detecting Factual Inconsistencies.
L148 | An inconsistency involves two statements. As the number of statement pairs scales quadratically with story length, naively comparing all pairs can result in a sea of false positive “contradictions” (Section 5.2). Flagging inconsistencies while avoiding false positives requires overwhelming precision.
L149 | Task Framing. To make the task more tractable,
L150 | we focus on factual inconsistencies
L151 | in character attributes (e.g., age, occupation,
L152 | relationship to another character). At a high level, our detection system maintains a compact knowledge base in the form of Figure 5’s “Attribute Dictionary” for each character. With each new story passage, we check for contradictions against only these attribute-value dictionaries instead of all previous text.
L153 | The dictionaries are then updated for the new passage, and new dictionaries are created for new characters when detected as described in Section 3.2.
L154 | Thus, the core of our detection system is a high-precision information extraction procedure for obtaining attribute-value pairs for a given character from a story passage. Rather than hard-coding a fixed set of attributes, our system is inspired by Open Information Extraction Etzioni et al. (2008), in order to capture the wide variety of possible attributes which may be salient in different stories.
L155 | Implementation Details. We begin by prompting GPT3-Instruct-175B for a numbered list of facts about the given character, shown as “Inferred Facts” in Figure 5. Each fact is fed with a few-shot prompt to GPT3-Instruct-13B to extract attribute keys. We then prompt GPT3-Instruct-13B with the fact and each attribute key to obtain complete attribute-value pairs. In steps prone to hallucination, we generate three outputs and keep only those which are repeated, or entailed by other outputs according to a BART-Large-based Lewis et al. (2019) entailment model trained on MNLI Williams et al. (2018). See Appendix C for complete details on information extraction, with example prompts.
L156 | Finally, we add new pairs to our dictionary, and use the entailment model to flag contradictions between new and old values for the same key.
L157 | Correcting Factual Inconsistencies.
L158 | Once an inconsistency is detected, we frame the task of correcting it as controlled text editing. The original natural language fact (i.e., “Inferred Facts” in Figure 5) from which we extracted the contradicted attribute-value pair now becomes the basis for
L159 | the “Editing Instruction” in Figure 5. This instruction is then fed along with the original continuation to the beta GPT3 Edit API.
```


### E7 — 消融结论（**Plan 与 Rewrite 关键；Edit 贡献很小**）

<!-- lines 362-376 of txt_2210.06774.txt -->
```
L362 | 5 Analysis
L363 | 5.1 Ablation Study
L364 | Ablated Modules. We investigate the relative contribution of the individual modules of Re3: Plan, Draft, Rewrite, and Edit.
L365 | We ablate each module in turn as follows, except the Draft module as it is unclear how our system would operate without it.
L366 | 1.
L367 | draft-rewrite-edit, a version of re3 without the Plan module. Accordingly, we remove the recursive reprompting in Draft. Thus draft-rewrite-edit generates text identically to the rolling baseline, but is revised by our Rewrite and Edit modules.
L368 | 2.
L369 | plan-draft-edit, a version of re3 without the Rewrite module reranking.
L370 | 3.
L371 | plan-draft-rewrite, a version of re3 which no longer edits using the Edit module.
L372 | Results. Table 4 shows that both the Plan and Rewrite modules, mimicking the human planning and rewriting processes, are critical for overall plot coherence
L373 | and premise relevance. However, the Edit module contributes little to these metrics. We also observe qualitatively that there remain many continuity issues in re3’s final stories which are not resolved by our Edit module, but which could be fixed by an attentive human editor. Such continuity issues range from non-character-centric inconsistencies, to facts which change over time, to outline plot points which were omitted in the story.
L374 | 5.2 Further Analysis of Edit Module
L375 | We use a controlled setting to investigate if the Edit module can at least detect the character-based factual inconsistencies for which it is designed. We will refer to our detection subsystem as structured-detect to avoid conflation with the Edit module as a whole.
L376 | Task Setup. We construct an evaluation dataset as follows. First we generate setups following our Plan module, up to but not including the outline. For each setup $s$ we randomly resample a character’s description until we manually observe a contradiction with the original, yielding a contradictory setup $s^{\prime}$ . For each of $s$ and $s^{\prime}$ , we generate a story ( $t$ and $t^{\prime}$ ), resampling until the contradicted attribute appears in the story. If the resampling fails after 5 attempts we restart the whole procedure. We generate 50 $(s,s^{\prime},t,t^{\prime})$ tuples in total; see Appendix L for an example.
```


### E8 — Edit 的自陈失败：复合错误、引入不必要改动

<!-- lines 388-394 of txt_2210.06774.txt -->
```
L388 | Results. As shown in Table 5, when detecting character-based inconsistencies, structured-detect outperforms the two baselines according to the standard ROC-AUC metric for classification Hanley and McNeil (1982). Indeed, the most naive entailment system’s ROC-AUC score is barely better than chance performance (0.5), highlighting the core challenge wherein the detection system must be overwhelmingly precise. Moreover, structured-detect is designed to scale to longer passages; we hypothesize that the performance gap compared to baselines would widen in an evaluation with longer inputs such as the stories from our main experiments.
L389 | Even so, the absolute performance of all systems remains low, even in this simplified setting. Additionally, many of our generated full stories contain non-character-based inconsistencies, such as in the setting or current scene. Some stories also contain false positives (flagged non-contradictions), such as character attributes which change over time.
L390 | Additionally, while we did not formally analyze the
L391 | GPT3 Edit API’s ability to correct inconsistencies after they are detected (as this system is largely not our contribution), we generally observed that it can fix isolated details but may struggle with larger changes. It also
L392 | sometimes makes undesired edits or additions.
L393 | Taken together, the compounding errors from the detection and correction subsystems make it difficult for our current Edit module to effectively improve factual consistency over a multiple-thousand-word horizon, without simultaneously introducing unnecessary changes.
L394 | 6 Discussion
```


### E9 — 附录 F：长度 vs 质量（**样本量不足，长故事更「有趣」但更容易出问题**）

<!-- lines 906-912 of txt_2210.06774.txt -->
```
L906 | The only preexisting story dataset used in this work is the WritingPrompts dataset Fan et al. (2018), which is used to train our relevance and coherence rerankers (and the generator for the rolling-ft baseline). GPT3 is additionally used to derive summaries of WritingPrompts passages for training the relevance reranker. Finally, we generated some examples of contradictory story setups and story beginnings when analyzing our Edit module in Section 5.2, which relied solely on prompting GPT3, and not any preexisting dataset.
L907 | All data used or generated for this paper, together with documentation, can be found through our codebase located at https://github.com/yangkevin2/emnlp22-re3-story-generation.
L908 | Appendix F Length vs. Story Quality Analysis
L909 | In our main experiments, we ran re3 with three outline sections and generated four 256-token passages per outline section. Here, experiment with generating from re3 using the same outlines, but with two or six 256-token passages per outline section instead. We refer to these modified version of re3 as re3-short and re3-long respectively. The results are shown in Table 13.
L910 | For the most part, the sample size of 50 stories for this comparison proved insufficient to draw clear quantitative conclusions on the impact of length on re3 story quality. However, interestingly, annotators judged the longer stories to be more interesting. Additionally, it seems intuitive that longer stories are more likely to suffer the presence of writing problems at some point in the story simply due to having more total text.
L911 | Qualitatively, we also observe that the generator may become repetitive or lose the plot thread over longer time horizons, but ending generation too early can also yield stories which seem “truncated” before they reach the main plot points. Trying to balance these factors by determining the length of story passages more dynamically could be an interesting avenue for future research.
L912 | Appendix G Full Metrics for Miscellaneous Writing Problems
```


### E10 — 主指标表（人工 pairwise；n=50 故事 × 3 名标注者）

<!-- lines 160-171 of txt_2210.06774.txt -->
```
L160 | 4 Evaluation
L161 | Method |
L162 | Interesting $\uparrow$ |
L163 | Coherent $\uparrow$ |
L164 | Relevant $\uparrow$ |
L165 | Humanlike $\uparrow$ |
L166 | Misc. Problems $\downarrow$ |
L167 | rolling |
L168 | 45.0 |
L169 | 45.7 |
L170 | 44.0 |
L171 | 74.0 |
```


### E11 — 结构化检测的 ROC-AUC（**判别式一致 vs 逐句蕴含**）

<!-- lines 380-391 of txt_2210.06774.txt -->
```
L380 | ROC-AUC $\uparrow$ |
L381 | entailment |
L382 | 0.528 |
L383 | entailment-dpr |
L384 | 0.610 |
L385 | structured-detect |
L386 | 0.684 |
L387 | Table 5: ROC-AUC score of predicted contradiction probabilities for different methods on our evaluation set. structured-detect outperforms our two entailment-based baselines.
L388 | Results. As shown in Table 5, when detecting character-based inconsistencies, structured-detect outperforms the two baselines according to the standard ROC-AUC metric for classification Hanley and McNeil (1982). Indeed, the most naive entailment system’s ROC-AUC score is barely better than chance performance (0.5), highlighting the core challenge wherein the detection system must be overwhelmingly precise. Moreover, structured-detect is designed to scale to longer passages; we hypothesize that the performance gap compared to baselines would widen in an evaluation with longer inputs such as the stories from our main experiments.
L389 | Even so, the absolute performance of all systems remains low, even in this simplified setting. Additionally, many of our generated full stories contain non-character-based inconsistencies, such as in the setting or current scene. Some stories also contain false positives (flagged non-contradictions), such as character attributes which change over time.
L390 | Additionally, while we did not formally analyze the
L391 | GPT3 Edit API’s ability to correct inconsistencies after they are detected (as this system is largely not our contribution), we generally observed that it can fix isolated details but may struggle with larger changes. It also
```


---

## 4. Graph of Thoughts（arXiv 2308.09687v4，v4 = 2024-02-06）


### G1 — 推理过程 = **有向图**（含**异质图** G=(V,E,c)：节点可以有类）

<!-- lines 167-172 of txt_2308.09687.txt -->
```
L167 | 3.1 Reasoning Process
L168 | We model the reasoning process as a directed graph $G=(V,E)$ ; $V$ is a set of vertices and $E\subseteq V\times V$ is a set of edges.
L169 | $G$ is directed and thus the edges are a subset of ordered vertex pairs $E\subseteq V\times V$ .
L170 | A vertex contains a solution to a problem at hand (be it an initial, intermediate, or a final one). The concrete form of such a thought depends on the use case; it could be a paragraph (in writing tasks) or a sequence of numbers (in sorting). A directed edge $(t_{1},t_{2})$ indicates that thought $t_{2}$ has been constructed using $t_{1}$ as “direct input”, i.e., by explicitly instructing the LLM to use $t_{1}$ for generating $t_{2}$ .
L171 | In certain use cases, graph nodes belong to different classes. For example, in writing tasks, some vertices model plans of writing a paragraph, while other vertices model the actual paragraphs of text. In such cases, GoT embraces a heterogeneous graph $G=(V,E,c)$ to model the LLM reasoning, where $c$ maps vertices $V$ into their respective classes $C$ (in the above case, it would be $C=\{plan,par\}$ ). Hence, any vertex $v$ can model different aspects of reasoning.
L172 | We associate $G$ with the LLM reasoning process. To advance this process, one applies thought transformations to $G$ . An example of such a transformation is to merge best-scoring (so far) thoughts into a new one. Another example is to loop over a thought, in order to enhance it. Note that these transformations strictly extend the set of transformations available in the CoT, CoT-SC, or ToT.
```


### G2 — 三种图启用变换：**Aggregation / Refining / Generation**（+ 可删除 V⁻/E⁻）

<!-- lines 178-195 of txt_2308.09687.txt -->
```
L178 | Formally, each such transformation can be modeled as $\mathcal{T}(G,p_{\theta})$ where $G=(V,E)$ is the graph reflecting the current state of the reasoning, and $p_{\theta}$ is the used LLM. $\mathcal{T}$ modifies $G$ usually by adding new vertices and their incoming edges.
L179 | We have $G^{\prime}=\mathcal{T}(G,p_{\theta})=(V^{\prime},E^{\prime})$ , where $V^{\prime}=(V\cup V^{+})\setminus V^{-}$ and $E^{\prime}=(E\cup E^{+})\setminus E^{-}$ . $V^{+}$ and $E^{+}$ are new vertices and edges inserted into $G$ to model the new thoughts and their dependencies, respectively. To maximize the expressiveness of GoT – we also enable the user to explicitly remove thoughts, by specifying the corresponding vertices and edges to be removed ( $V^{-}$ and $E^{-}$ , respectively).
L180 | Here, it is the user’s responsibility to ensure that the sets $V^{+},E^{+},V^{-},$ and $E^{-}$ come with consistent transformations (i.e., for example, that the user does not attempt to remove a vertex that does not exist).
L181 | This enables seamless incorporation of schemes where, in order to save space within the context, one can remove parts of reasoning that do not promise improvements.
L182 | The specific form of $\mathcal{T}$ and how it impacts $G$ depends on a specific transformation. We first detail the primary graph-enabled thought transformations, and then proceed to describe how GoT embraces the transformations from the earlier schemes. Unless stated otherwise, $V^{-}=E^{-}=\emptyset$ .
L183 | Figure 3: The system architecture of GoT, and the APIs of respective modules. The user can straightforwardly extend the design towards new prompting schemes, experiment with novel thought transformations, and plug in different LLMs. The blue part of the figure contains the architecture overview, the green part lists the API, and the red part contains example prompts together with a GRS and operations involved.
L184 | Aggregation Transformations
L185 | First, with GoT, one can aggregate arbitrary thoughts into new ones, to combine and reinforce the advantages of these thoughts, while eliminating their disadvantages.
L186 | In the basic form, in which only one new vertex is created, $V^{+}=\{v^{+}\}$ and $E^{+}=\{(v_{1},v^{+}),...,(v_{k},v^{+})\}$ , where $v_{1},...,v_{k}$ are the merged $k$ thoughts.
L187 | More generally, this enables aggregating reasoning paths, i.e., longer chains of thoughts, beyond just individual thoughts. With the graph model, it is simply achieved by adding outgoing edges from the vertices $v_{1},...,v_{k}$ , modeling final thoughts in several chains, into a single thought $v^{+}$ combining these chains.
L188 | Refining Transformations
L189 | Another thought transformation is the refining of a current thought $v$ by modifying its content: $V^{+}=\{\}$ and $E^{+}=\{(v,v)\}$ . This loop in the graph indicates an iterated thought with the same connections as the original thought.
L190 | Generation Transformations
L191 | Finally, one can generate one or more new thoughts based on an existing single thought $v$ . This class embraces analogous reasoning steps from earlier schemes, such as ToT or CoT-SC. Formally, we have $V^{+}=\{v^{+}_{1},...,v^{+}_{k}\}$ and $E^{+}=\{(v,v^{+}_{1}),...,(v,v^{+}_{k})\}$ .
L192 | 3.3 Scoring & Ranking Thoughts
L193 | Thoughts are scored to understand whether the current solution is good enough. A score is modeled as a general function $\mathcal{E}(v,G,p_{\theta})$ , where $v$ is a thought to be evaluated. We use the state of the whole reasoning process ( $G$ ) in $\mathcal{E}$ for maximum generality, because – for example – in some evaluation scenarios, scores may be relative to other thoughts.
L194 | GoT can also rank thoughts. We model this with a function $\mathcal{R}(G,p_{\theta},h)$ where $h$ specifies the number of highest-ranking thoughts in $G$ to be returned by $\mathcal{R}$ . While the specific form of $\mathcal{R}$ depends on the use case, we most often use a simple yet effective strategy where $h$ thoughts with the highest scores are returned, i.e., $v_{1},...,v_{h}=\mathcal{R}(G,p_{\theta},h)$ .
L195 | Specific forms of $\mathcal{E}$ and $\mathcal{R}$ depend on the use case. We discuss the details in Section 5. For example, the score (or rank) for sorting corresponds to the count of elements correctly sorted (or incorrectly, when using the error as a score).
```


### G3 — **volume**（体积）定义与各方案对照（**「思维面」的现成公式**）

<!-- lines 258-268 of txt_2308.09687.txt -->
```
L258 | 6 The Latency-Volume Tradeoff
L259 | We now show that GoT improves upon previous prompting schemes in terms of the tradeoff between latency (number of hops in the graph of thoughts to reach a given final thought) and volume. We define volume – for a given thought $t$ – as the number of preceding LLM thoughts that could have impacted $t$ . Formally, the volume of $t$ is the number of thoughts from which there exists a path to $t$ in the graph of thoughts.
L260 | We assume that outputting a single thought costs $O(1)$ time and fix the total cost to $\Theta(n)$ for each prompting scheme.
L261 | The structure of the schemes is as follows. CoT-SC consists of $k$ independent chains originating from a single starting thought. ToT is a complete $k$ -ary tree. Finally, in GoT, a complete $k$ -ary tree is joined at its leaves with a “mirrored” $k$ -ary tree of the same size but with its edges reversed.
L262 | The analysis is detailed in Table 2.
L263 | CoT offers a large volume of up to $N$ , but at the cost of a high latency of $N$ . CoT-SC reduces the latency by a factor of $k$ (which corresponds to its branching factor), but it simultaneously decreases the volume by $k$ as well. ToT offers a latency of $\log_{k}N$ but also has low volume. GoT is the only scheme to come with both a low latency of $\log_{k}N$ and a high volume $N$ . This is enabled by the fact that GoT harnesses aggregations of thoughts, making it possible to reach the final thought from any other intermediate thought in the graph decomposition.
L264 | Scheme |
L265 | Latency |
L266 | Volume |
L267 | Chain-of-Thought (CoT) |
L268 | $N$ |
```


### G4 — 排序任务的打分函数 error-scope（**部分给分的可判定指标**）

<!-- lines 222-252 of txt_2308.09687.txt -->
```
L222 | To score an outcome, denote an input sequence with $[a_{1},a_{2},...,a_{n}]$ and an output one with $[b_{1},b_{2},...,b_{m}]$ .
L223 | We use the following score that determines “the scope” of errors:
L224 | |
L225 | $\text{error-scope}=X+Y$ |
L226 | |
L227 | where $p\in\{1,...,m\}$ , $q\in\{1,...,n\}$ , and
L228 | |
L229 | $\displaystyle X$ |
L230 | $\displaystyle=\sum_{i=1}^{m-1}\text{sgn}(\max(b_{i}-b_{i+1},0)),$ |
L231 | |
L232 | |
L233 | $\displaystyle Y$ |
L234 | $\displaystyle=\sum_{i=0}^{9}\left|\ |\{b_{p}:b_{p}=i\}|-|\{a_{q}:a_{q}=i\}|\ \right|$ |
L235 | |
L236 | Here, $X$ indicates how many consecutive pairs of numbers are incorrectly sorted. If two numbers $i$ and $i+1$ are incorrectly sorted (i.e., $b_{i}>b_{i+1}$ ), then the expression within the summation returns 1, increasing the error score by one. For two numbers correctly sorted, this expression amounts to 0.
L237 | Then, $Y$ determines how well a given output sequence preserves the frequency of output numbers. Specifically, for each considered number $x$ ( $x\in\{0,...,9\}$ ), we obtain the difference between the count of input elements being equal to $x$ , vs. the count of output elements equal to $x$ . For an output sequence perfectly preserving the frequency of $x$ , this would amount to 0. Any single “deviation” in this count, increases the “error scope” by 1. We then sum this over all considered values of $x$ .
L238 | When plotting this score, to improve the clarity of plots, we additionally apply clipping $\min(\text{error-scope},n)$ , as some baselines (IO, CoT) result in large numbers of outliers with high error scope.
L239 | Finally, to use a “positive score” describing “the scope of correctly sorted” elements, one can use the value $\max(n-\text{error-scope},0)$ .
L240 | Figure 4: An example graph decomposition of the sorting use case in GoT. All used operations (Generate, Aggregate, Score, KeepBest) are described in Figure 3.
L241 | 5.2 Set Operations
L242 | Moreover, we also consider set operations, focusing on set intersection. They have numerous applications (particularly set intersection) in problems ranging from genome or document comparisons
L243 | to pattern matching [20, 58, 38, 11, 27, 50, 10, 9].
L244 | Set intersection of two sets is implemented similarly as the sorting. The second input set is split into subsets and the intersection of those subsets with the first input set is determined with the help of the LLM. Afterwards the resulting intersection sets are aggregated for the final results. For the evaluation we use different set sizes of 32, 64 and 128 elements and we vary the number of elements found in both sets to be between 25% and 75%.
L245 | Our score indicates the total number of missing or incorrectly included elements in the final intersection. Specifically, denote two input sets with $A=[a_{1},a_{2},...,a_{n}]$ and $B=[b_{1},b_{2},...,b_{n}]$ , and the output set with $C=[c_{1},c_{2},...,c_{m}]$ . Then,
L246 | |
L247 | $\text{error-scope}=X_{1}+X_{2}+X_{d}$ |
L248 | |
L249 | where $X_{1}=|C\setminus(A\cap B)|$ are the number of elements in $C$ that are not supposed to be there, $X_{2}=|(A\cap B)\setminus C|$ are the number of elements missing from $C$ , and $X_{d}$ is the number of duplicates in $C$ (because the LLM expresses the set as a list in natural language).
L250 | Finally, to use a “positive score” describing “the scope of correctly computed” elements, one can use the value $\max(n-\text{error-scope},0)$ .
L251 | 5.3 Keyword Counting
L252 | Keyword counting finds the frequency of keywords in a given category (countries in our example implementation) within the input text. GoT splits the input text into multiple passages, counts the keywords in each passage and aggregates the subresults. The number of passages is configurable and can also be left to the LLM, making it possible to treat each sentence as a separate passage.
```


### G5 — 评估方法学（100 样本/任务、temperature 1.0、4k context、k 与 L 的取值）

<!-- lines 282-292 of txt_2308.09687.txt -->
```
L282 | 7 Evaluation
L283 | We show the advantages of GoT over the state of the art. We focus on comparing GoT to ToT, as it was shown to consistently outperform other schemes. Still, for a broad comparison, we also experiment with IO, CoT, and CoT-SC. As our analysis results in a large evaluation space, we present representative results and omit data that does not bring relevant insights (e.g., CoT-SC).
L284 | 7.1 Evaluation Methodology
L285 | We use 100 input samples for each task and comparison baseline. We set the temperature to 1.0 and use a 4k context size unless stated otherwise. For each experiment, we fix the numbers of thoughts in respective schemes to achieve similar costs in each experiment.
L286 | Parameters
L287 | We experiment extensively with the branching factor $k$ and the number of levels $L$ to ensure that we compare GoT to cost-effective and advantageous configurations. We plot two variants of ToT: one with higher $k$ and lower depth (ToT), the other with lower $k$ but higher $L$ (ToT2).
L288 | We usually aim to achieve a sweet spot in the tradeoff between sparser generation rounds (lower $k$ ) vs. more rounds (larger $L$ ). Usually more responses per round is more expensive (e.g., 80 vs. 60 total responses for Figure 7 but $6 vs. $3 costs).
L289 | We also try different problem sizes $P$ (e.g., in sorting, $P$ states how many numbers are to be sorted).
L290 | Used LLMs
L291 | Due to budget restrictions, we focus on GPT-3.5.
L292 | We also experimented with Llama-2, but it was usually worse than GPT-3.5 and also much slower to run, making it infeasible to obtain enough samples.
```


### G6 — 排序 32 的 GoO 执行计划（**静态图即终止条件**）

<!-- lines 988-998 of txt_2308.09687.txt -->
```
L988 | Table 5: Sorting of a 32 element list: Execution plan (GoO)
L989 | GoO:
L990 | 1.
L991 | Split the input list into two sub-lists of equal size (split_prompt)
L992 | 2.
L993 | For each sub-list: Sort the sub-list (sort_prompt) five times; score each sort attempt; keep the best
L994 | 3.
L995 | Merge the sorted sub-lists into one fully sorted list (merge_prompt) 10 times; score each merge attempt; keep the best
L996 | 4.
L997 | Fix any potential mistakes in the sorted list (improve_prompt) 10 times; score each improvement attempt; keep the best
L998 | |
```


### G7 — GoT vs ToT 读数（P=128 中位错误降 ~62%，成本降 >31%）

<!-- lines 296-302 of txt_2308.09687.txt -->
```
L296 | Overall, GoT improves the quality of outcomes over all the considered baselines and it reduces inference costs compared to ToT.
L297 | Figure 6: Number of errors and cost in set intersection tasks with ChatGPT-3.5. $L$ and $k$ indicate the structure of ToT (see Sections 3.2 and 6).
L298 | GoT vs. ToT
L299 | GoT improves upon ToT and ToT2 by a large margin over all the considered problem instances. ToT usually comes with somewhat higher quality than ToT2, but simultaneously much higher costs. GoT’s costs are always lower than ToT, and comparable (in some cases lower, in others higher) to ToT2. For example, it reduces median error by $\approx$ 62%, thereby achieving a higher quality of sorting, for $P=128$ in comparison to ToT while ensuring $>$ 31% cost reductions. These advantages are due to GoT’s ability to decompose complex tasks into simpler subtasks, solve these subtasks independently, and then incrementally merge these outcomes into the final result.
L300 | GoT vs. IO and CoT
L301 | GoT consistently delivers much higher quality of outcomes than IO/CoT. For example, for sorting ( $P=64$ ), GoT’s median error is $\approx$ 65% and $\approx$ 83% lower than, respectively, CoT and IO. Yet, the costs of GoT – and ToT – are much higher than in IO and CoT. This is mostly due to our configuration of CoT, where we do not artificially inflate the lengths of the chains of reasoning if this does not improve the outcomes. The higher costs of GoT and ToT are driven by $k$ new thoughts built for each Generate operation; these multiple thoughts are one of the reasons for GoT’s superiority in quality.
L302 | Increasing Complexity of Tackled Problems
```


### G8 — 任务分解的讨论（**「分解到单次提示就能做对」的目标 ⇒ 减少 improve 步数**）

<!-- lines 306-309 of txt_2308.09687.txt -->
```
L306 | 7.3 Discussion on Task Decomposition
L307 | When splitting a task into subtasks and then solving these subtasks, the size of responses and the input (in tokens) are reduced proportionally to the degree of the task decomposition. However, the “static” part of the prompt (i.e., few-shot examples) may become a significant overhead (see GoT4 to GoT8 in Figure 7).
L308 | Here, we observe that these few-shot examples can usually also be reduced in size (e.g., the passages used to demonstrate keyword counting can also be made smaller and still be indicative of the actual input size), thus actively working towards decreasing the cost (e.g., see the difference between GoT8 and GoTx in Figure 7).
L309 | The overall goal when conducting graph decomposition is to break down a task to the point, where the LLM can solve it correctly for the majority of time using a single prompt (or with a few additional improvement steps). This significantly lowers the number of improvement/refinement steps needed during the later stages of the graph exploration. Furthermore, as indicated by our results, combining or concatenating subresults is usually an easier task than solving large task instances from scratch. Hence, the LLM is often successful when aggregating the final solution.
```


---

## 5. 仓库 `spcl/graph-of-thoughts`（main 分支）


### C1 — `graph_of_thoughts/operations/thought.py`：**Thought 数据结构**（state + score + valid + solved + validated/scored 标志）

<!-- graph_of_thoughts_operations_thought.py:15-37 -->
```
L15 | class Thought:
L16 |     """
L17 |     Represents an LLM thought with its state, constructed by the parser, and various flags.
L18 |     """
L19 | 
L20 |     _ids: Iterator[int] = itertools.count(0)
L21 | 
L22 |     def __init__(self, state: Optional[Dict] = None) -> None:
L23 |         """
L24 |         Initializes a new Thought instance with a state and various default flags.
L25 | 
L26 |         :param state: The state of the thought. Defaults to None.
L27 |         :type state: Optional[Dict]
L28 |         """
L29 |         self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
L30 |         self.id: int = next(Thought._ids)
L31 |         self.state: Dict = state
L32 |         self._score: float = 0.0
L33 |         self._valid: bool = False
L34 |         self._solved: bool = False
L35 |         self.scored: bool = False
L36 |         self.validated: bool = False
L37 |         self.compared_to_ground_truth: bool = False
```


### C2 — `graph_of_thoughts/operations/operations.py`：**OperationType 枚举**（9 种算子）

<!-- graph_of_thoughts_operations_operations.py:22-36 -->
```
L22 | class OperationType(Enum):
L23 |     """
L24 |     Enum to represent different operation types that can be used as unique identifiers.
L25 |     """
L26 | 
L27 |     score: int = 0
L28 |     validate_and_improve: int = 1
L29 |     generate: int = 2
L30 |     improve: int = 3
L31 |     aggregate: int = 4
L32 |     keep_best_n: int = 5
L33 |     keep_valid: int = 6
L34 |     ground_truth_evaluator: int = 7
L35 |     selector: int = 8
L36 | 
```


### C3 — `operations.py`：**Aggregate（合并算子）实现**（按分数排序合并 state，num_responses 次采样后逐个成点）

<!-- graph_of_thoughts_operations_operations.py:536-609 -->
```
L536 | class Aggregate(Operation):
L537 |     """
L538 |     Operation to aggregate thoughts.
L539 |     """
L540 | 
L541 |     operation_type: OperationType = OperationType.aggregate
L542 | 
L543 |     def __init__(self, num_responses: int = 1) -> None:
L544 |         """
L545 |         Initializes a new Aggregate operation.
L546 | 
L547 |         :param num_responses: Number of responses to use for aggregation. Defaults to 1.
L548 |         :type num_responses: int
L549 |         """
L550 |         super().__init__()
L551 |         self.thoughts: List[Thought] = []
L552 |         self.num_responses: int = num_responses
L553 | 
L554 |     def get_thoughts(self) -> List[Thought]:
L555 |         """
L556 |         Returns the thoughts associated with the operation after aggregation.
L557 | 
L558 |         :return: List of aggregated thoughts.
L559 |         :rtype: List[Thought]
L560 |         """
L561 |         return self.thoughts
L562 | 
L563 |     def _execute(
L564 |         self, lm: AbstractLanguageModel, prompter: Prompter, parser: Parser, **kwargs
L565 |     ) -> None:
L566 |         """
L567 |         Executes the Aggregate operation by aggregating the predecessors' thoughts.
L568 |         The thoughts are aggregated by prompting the LM with the predecessors' thought states.
L569 | 
L570 |         :param lm: The language model to be used.
L571 |         :type lm: AbstractLanguageModel
L572 |         :param prompter: The prompter for crafting prompts.
L573 |         :type prompter: Prompter
L574 |         :param parser: The parser for parsing responses.
L575 |         :type parser: Parser
L576 |         :param kwargs: Additional parameters for execution.
L577 |         :raises AssertionError: If operation has no predecessors.
L578 |         """
L579 |         assert (
L580 |             len(self.predecessors) >= 1
L581 |         ), "Aggregate operation must have at least one predecessor"
L582 | 
L583 |         previous_thoughts: List[Thought] = self.get_previous_thoughts()
L584 | 
L585 |         if len(previous_thoughts) == 0:
L586 |             return
L587 | 
L588 |         # applied in order of score
L589 |         base_state: Dict = {}
L590 |         for thought in sorted(previous_thoughts, key=lambda thought: thought.score):
L591 |             base_state = {**base_state, **thought.state}
L592 | 
L593 |         previous_thought_states = [thought.state for thought in previous_thoughts]
L594 |         prompt = prompter.aggregation_prompt(previous_thought_states)
L595 | 
L596 |         self.logger.debug("Prompt for LM: %s", prompt)
L597 | 
L598 |         responses = lm.get_response_texts(
L599 |             lm.query(prompt, num_responses=self.num_responses)
L600 |         )
L601 | 
L602 |         self.logger.debug("Responses from LM: %s", responses)
L603 | 
L604 |         parsed = parser.parse_aggregation_answer(previous_thought_states, responses)
L605 | 
L606 |         if isinstance(parsed, dict):
L607 |             parsed = [parsed]
L608 |         for new_state in parsed:
L609 |             self.thoughts.append(Thought({**base_state, **new_state}))
```


### C4 — `operations.py`：**KeepBestN**（`higher_is_better` 参数，排序取前 n）

<!-- graph_of_thoughts_operations_operations.py:612-668 -->
```
L612 | class KeepBestN(Operation):
L613 |     """
L614 |     Operation to keep the best N thoughts from predecessors based on their score.
L615 |     """
L616 | 
L617 |     operation_type: OperationType = OperationType.keep_best_n
L618 | 
L619 |     def __init__(self, n: int, higher_is_better: bool = True) -> None:
L620 |         """
L621 |         Initializes a new KeepBestN operation.
L622 | 
L623 |         :param n: Maximum number of thoughts to keep.
L624 |         :type n: int
L625 |         :param higher_is_better: Whether higher scores are better. Defaults to True.
L626 |         :type higher_is_better: bool
L627 |         :raises AssertionError: If `n` is not greater than zero.
L628 |         """
L629 |         super().__init__()
L630 |         self.n: int = n
L631 |         assert self.n > 0, "KeepBestN operation must keep at least one thought"
L632 |         self.higher_is_better: bool = higher_is_better
L633 |         self.thoughts: List[Thought] = []
L634 | 
L635 |     def get_best_n(self) -> List[Thought]:
L636 |         """
L637 |         Returns the best N thoughts from the predecessors based on their score.
L638 | 
L639 |         :return: List of best N thoughts.
L640 |         :rtype: List[Thought]
L641 |         :raises AssertionError: If not all predecessors have been executed.
L642 |         :raises AssertionError: If not all thoughts have been scored.
L643 |         """
L644 |         previous_thoughts: List[Thought] = self.get_previous_thoughts()
L645 |         assert all(
L646 |             previous_thought.scored for previous_thought in previous_thoughts
L647 |         ), "Not all thoughts have been scored"
L648 | 
L649 |         try:
L650 |             return sorted(
L651 |                 previous_thoughts,
L652 |                 key=lambda thought: thought.score,
L653 |                 reverse=self.higher_is_better,
L654 |             )[: self.n]
L655 |         except:
L656 |             self.logger.error("Error in KeepBestN operation")
L657 |             self.logger.error(
L658 |                 "Previous operation: %s", [op.id for op in self.predecessors]
L659 |             )
L660 |             self.logger.error("Previous thoughts: %s", previous_thoughts)
L661 |             self.logger.error(
L662 |                 "Scores: %s", [thought.score for thought in previous_thoughts]
L663 |             )
L664 |             return sorted(
L665 |                 [i for i in previous_thoughts if isinstance(i.score, float)],
L666 |                 key=lambda thought: thought.score,
L667 |                 reverse=self.higher_is_better,
L668 |             )[: self.n]
```


### C5 — `operations.py`：**KeepValid**（**保留规则 = `not validated or valid`**，即未验证的也留）

<!-- graph_of_thoughts_operations_operations.py:712-773 -->
```
L712 | class KeepValid(Operation):
L713 |     """
L714 |     Operation to keep valid thoughts from predecessors.
L715 |     """
L716 | 
L717 |     operation_type: OperationType = OperationType.keep_valid
L718 | 
L719 |     def __init__(self) -> None:
L720 |         """
L721 |         Initializes a new KeepValid operation.
L722 |         """
L723 |         super().__init__()
L724 |         self.thoughts: List[Thought] = []
L725 | 
L726 |     def get_thoughts(self) -> List[Thought]:
L727 |         """
L728 |         Returns the thoughts kept by the operation.
L729 | 
L730 |         :return: List of kept thoughts.
L731 |         :rtype: List[Thought]
L732 |         """
L733 |         return self.thoughts
L734 | 
L735 |     def _execute(
L736 |         self, lm: AbstractLanguageModel, prompter: Prompter, parser: Parser, **kwargs
L737 |     ) -> None:
L738 |         """
L739 |         Executes the KeepValid operation by keeping the valid thoughts from the predecessors.
L740 |         Keeps unvalidated thoughts as well.
L741 | 
L742 |         :param lm: The language model to be used.
L743 |         :type lm: AbstractLanguageModel
L744 |         :param prompter: The prompter for crafting prompts.
L745 |         :type prompter: Prompter
L746 |         :param parser: The parser for parsing responses.
L747 |         :type parser: Parser
L748 |         :param kwargs: Additional parameters for execution.
L749 |         :raises AssertionError: If operation has no predecessors.
L750 |         """
L751 |         assert (
L752 |             len(self.predecessors) >= 1
L753 |         ), "KeepValid operation must have at least one predecessor"
L754 | 
L755 |         self.thoughts: List[Thought] = [
L756 |             Thought.from_thought(thought)
L757 |             for thought in self.get_previous_thoughts()
L758 |             if not thought.validated or thought.valid
L759 |         ]
L760 | 
L761 |         if any(not thought.validated for thought in self.thoughts):
L762 |             self.logger.warning(
L763 |                 "KeepValid operation %d has unvalidated thoughts", self.id
L764 |             )
L765 | 
L766 |         for thought in self.thoughts:
L767 |             self.logger.debug(
L768 |                 "Thought %d with state %s kept", thought.id, thought.state
L769 |             )
L770 | 
L771 |         self.logger.info(
L772 |             "KeepValid operation %d kept %d thoughts", self.id, len(self.thoughts)
L773 |         )
```


### C6 — `operations.py`：**GroundTruth**（**确定性判成败**；异常 → solved=False）

<!-- graph_of_thoughts_operations_operations.py:776-837 -->
```
L776 | class GroundTruth(Operation):
L777 |     """
L778 |     Operation to evaluate if thoughts correctly solve the problem, using a ground truth evaluator
L779 |     """
L780 | 
L781 |     operation_type: OperationType = OperationType.ground_truth_evaluator
L782 | 
L783 |     def __init__(self, ground_truth_evaluator: Callable[[Dict], bool]) -> None:
L784 |         """
L785 |         Initializes a new GroundTruth operation.
L786 | 
L787 |         :param ground_truth_evaluator: A function to evaluate if a thought solves the problem.
L788 |         :type ground_truth_evaluator: A function that takes a thought state and returns a boolean.
L789 |         """
L790 |         super().__init__()
L791 |         self.ground_truth_evaluator: Callable[[Dict], bool] = ground_truth_evaluator
L792 |         self.thoughts: List[Thought] = []
L793 | 
L794 |     def get_thoughts(self) -> List[Thought]:
L795 |         """
L796 |         Returns the thoughts associated with the operation.
L797 | 
L798 |         :return: List of evaluated thoughts.
L799 |         :rtype: List[Thought]
L800 |         """
L801 |         return self.thoughts
L802 | 
L803 |     def _execute(
L804 |         self, lm: AbstractLanguageModel, prompter: Prompter, parser: Parser, **kwargs
L805 |     ) -> None:
L806 |         """
L807 |         Executes the GroundTruth operation by evaluating the predecessors' thoughts using the ground truth evaluator function.
L808 | 
L809 |         :param lm: The language model to be used.
L810 |         :type lm: AbstractLanguageModel
L811 |         :param prompter: The prompter for crafting prompts.
L812 |         :type prompter: Prompter
L813 |         :param parser: The parser for parsing responses.
L814 |         :type parser: Parser
L815 |         :param kwargs: Additional parameters for execution.
L816 |         :raises AssertionError: If operation has no predecessor.
L817 |         """
L818 |         assert (
L819 |             len(self.predecessors) >= 1
L820 |         ), "GroundTruth operation must have at least one predecessor"
L821 | 
L822 |         previous_thoughts: List[Thought] = self.get_previous_thoughts()
L823 | 
L824 |         for thought in previous_thoughts:
L825 |             new_thought = Thought.from_thought(thought)
L826 |             try:
L827 |                 new_thought.solved = self.ground_truth_evaluator(new_thought.state)
L828 |             except:
L829 |                 new_thought.solved = False
L830 |             self.thoughts.append(new_thought)
L831 | 
L832 |         self.logger.info(
L833 |             "GroundTruth operation %d evaluated %d thoughts and %d solved the problem",
L834 |             self.id,
L835 |             len(self.thoughts),
L836 |             len([thought for thought in self.thoughts if thought.solved]),
L837 |         )
```


### C7 — `operations.py`：**Generate**（num_branches_prompt × num_branches_response）

<!-- graph_of_thoughts_operations_operations.py:391-477 -->
```
L391 | class Generate(Operation):
L392 |     """
L393 |     Operation to generate thoughts.
L394 |     """
L395 | 
L396 |     operation_type: OperationType = OperationType.generate
L397 | 
L398 |     def __init__(
L399 |         self, num_branches_prompt: int = 1, num_branches_response: int = 1
L400 |     ) -> None:
L401 |         """
L402 |         Initializes a new Generate operation.
L403 | 
L404 |         :param num_branches_prompt: Number of responses that each prompt should generate (passed to prompter). Defaults to 1.
L405 |         :type num_branches_prompt: int
L406 |         :param num_branches_response: Number of responses the LM should generate for each prompt. Defaults to 1.
L407 |         :type num_branches_response: int
L408 |         """
L409 |         super().__init__()
L410 |         self.num_branches_prompt: int = num_branches_prompt
L411 |         self.num_branches_response: int = num_branches_response
L412 |         self.thoughts: List[Thought] = []
L413 | 
L414 |     def get_thoughts(self) -> List[Thought]:
L415 |         """
L416 |         Returns the thoughts associated with the operation.
L417 | 
L418 |         :return: List of generated thoughts.
L419 |         :rtype: List[Thought]
L420 |         """
L421 |         return self.thoughts
L422 | 
L423 |     def _execute(
L424 |         self, lm: AbstractLanguageModel, prompter: Prompter, parser: Parser, **kwargs
L425 |     ) -> None:
L426 |         """
L427 |         Executes the Generate operation by generating thoughts from the predecessors.
L428 |         The thoughts are generated by prompting the LM with the predecessors' thought states.
L429 |         If there are no predecessors, the kwargs are used as a base state.
L430 | 
L431 |         :param lm: The language model to be used.
L432 |         :type lm: AbstractLanguageModel
L433 |         :param prompter: The prompter for crafting prompts.
L434 |         :type prompter: Prompter
L435 |         :param parser: The parser for parsing responses.
L436 |         :type parser: Parser
L437 |         :param kwargs: Additional parameters for execution.
L438 |         """
L439 |         previous_thoughts: List[Thought] = self.get_previous_thoughts()
L440 | 
L441 |         if len(previous_thoughts) == 0 and len(self.predecessors) > 0:
L442 |             return
L443 | 
L444 |         if len(previous_thoughts) == 0:
L445 |             # no predecessors, use kwargs as base state
L446 |             previous_thoughts = [Thought(state=kwargs)]
L447 | 
L448 |         for thought in previous_thoughts:
L449 |             base_state = thought.state
L450 |             prompt = prompter.generate_prompt(self.num_branches_prompt, **base_state)
L451 |             self.logger.debug("Prompt for LM: %s", prompt)
L452 |             responses = lm.get_response_texts(
L453 |                 lm.query(prompt, num_responses=self.num_branches_response)
L454 |             )
L455 |             self.logger.debug("Responses from LM: %s", responses)
L456 |             for new_state in parser.parse_generate_answer(base_state, responses):
L457 |                 new_state = {**base_state, **new_state}
L458 |                 self.thoughts.append(Thought(new_state))
L459 |                 self.logger.debug(
L460 |                     "New thought %d created with state %s",
L461 |                     self.thoughts[-1].id,
L462 |                     self.thoughts[-1].state,
L463 |                 )
L464 |         if (
L465 |             len(self.thoughts)
L466 |             > self.num_branches_prompt
L467 |             * self.num_branches_response
L468 |             * len(previous_thoughts)
L469 |             and self.num_branches_prompt > 0
L470 |         ):
L471 |             self.logger.warning(
L472 |                 "Generate operation %d created more thoughts than expected",
L473 |                 self.id,
L474 |             )
L475 |         self.logger.info(
L476 |             "Generate operation %d created %d new thoughts", self.id, len(self.thoughts)
L477 |         )
```


### C8 — `operations.py`：**Improve**（**单条改写，无 validity 门，num_responses=1**）

<!-- graph_of_thoughts_operations_operations.py:480-533 -->
```
L480 | class Improve(Operation):
L481 |     """
L482 |     Operation to improve thoughts.
L483 |     """
L484 | 
L485 |     operation_type: OperationType = OperationType.improve
L486 | 
L487 |     def __init__(self) -> None:
L488 |         """
L489 |         Initializes a new Improve operation.
L490 |         """
L491 |         super().__init__()
L492 |         self.thoughts: List[Thought] = []
L493 | 
L494 |     def get_thoughts(self) -> List[Thought]:
L495 |         """
L496 |         Returns the thoughts associated with the operation after improvement.
L497 | 
L498 |         :return: List of improved thoughts.
L499 |         :rtype: List[Thought]
L500 |         """
L501 |         return self.thoughts
L502 | 
L503 |     def _execute(
L504 |         self, lm: AbstractLanguageModel, prompter: Prompter, parser: Parser, **kwargs
L505 |     ) -> None:
L506 |         """
L507 |         Executes the Improve operation by improving the predecessors' thoughts.
L508 |         The thoughts are improved by prompting the LM with the predecessors' thought states.
L509 | 
L510 |         :param lm: The language model to be used.
L511 |         :type lm: AbstractLanguageModel
L512 |         :param prompter: The prompter for crafting prompts.
L513 |         :type prompter: Prompter
L514 |         :param parser: The parser for parsing responses.
L515 |         :type parser: Parser
L516 |         :param kwargs: Additional parameters for execution.
L517 |         :raises AssertionError: If operation has no predecessors.
L518 |         """
L519 |         previous_thoughts: List[Thought] = self.get_previous_thoughts()
L520 | 
L521 |         assert len(self.predecessors) > 0, "Needs at least one predecessor"
L522 | 
L523 |         for thought in previous_thoughts:
L524 |             improve_prompt = prompter.improve_prompt(**thought.state)
L525 |             self.logger.debug("Prompt for LM: %s", improve_prompt)
L526 |             responses = lm.get_response_texts(lm.query(improve_prompt, num_responses=1))
L527 |             self.logger.debug("Responses from LM: %s", responses)
L528 |             state_update = parser.parse_improve_answer(thought.state, responses)
L529 |             self.thoughts.append(Thought({**thought.state, **state_update}))
L530 | 
L531 |         self.logger.info(
L532 |             "Improve operation %d improved %d thoughts", self.id, len(self.thoughts)
L533 |         )
```


### C9 — `operations.py`：**ValidateAndImprove**（**validity 门 + 最多 num_tries=3 次改写**）

<!-- graph_of_thoughts_operations_operations.py:269-309 -->
```
L269 | class ValidateAndImprove(Operation):
L270 |     """
L271 |     Operation to validate and improve thoughts.
L272 |     """
L273 | 
L274 |     operation_type: OperationType = OperationType.validate_and_improve
L275 | 
L276 |     def __init__(
L277 |         self,
L278 |         num_samples: int = 1,
L279 |         improve: bool = True,
L280 |         num_tries: int = 3,
L281 |         validate_function: Callable[[Dict], bool] = None,
L282 |     ) -> None:
L283 |         """
L284 |         Initializes a new ValidateAndImprove operation.
L285 | 
L286 |         :param num_samples: Number of samples to use for validation. Defaults to 1.
L287 |         :type num_samples: int
L288 |         :param improve: Whether to improve the thought if it is not valid. Defaults to True.
L289 |         :type improve: bool
L290 |         :param num_tries: Number of tries to improve the thought before giving up. Defaults to 3.
L291 |         :type num_tries: int
L292 |         :param validate_function: A function to validate thoughts (if not using LM). Defaults to None.
L293 |         :type validate_function: Takes a thought state and returns a boolean.
L294 |         """
L295 |         super().__init__()
L296 |         self.num_samples: int = num_samples
L297 |         self.improve: bool = improve
L298 |         self.num_tries: int = num_tries
L299 |         self.validate_function: Callable[[Dict], bool] = validate_function
L300 |         self.thoughts: List[List[Thought]] = []
L301 | 
L302 |     def get_thoughts(self) -> List[Thought]:
L303 |         """
L304 |         Returns the list of final thoughts, after validation and improvement.
L305 | 
L306 |         :return: List of final validated and improved thoughts.
L307 |         :rtype: List[Thought]
L308 |         """
L309 |         return [thought_list[-1] for thought_list in self.thoughts]
```


### C10 — `graph_of_thoughts/operations/graph_of_operations.py`：**GraphOfOperations = 静态 DAG**（roots/leaves/append/add）

<!-- graph_of_thoughts_operations_graph_of_operations.py:15-69 -->
```
L15 | class GraphOfOperations:
L16 |     """
L17 |     Represents the Graph of Operations, which prescribes the execution plan of thought operations.
L18 |     """
L19 | 
L20 |     def __init__(self) -> None:
L21 |         """
L22 |         Initializes a new Graph of Operations instance with empty operations, roots, and leaves.
L23 |         The roots are the entry points in the graph with no predecessors.
L24 |         The leaves are the exit points in the graph with no successors.
L25 |         """
L26 |         self.operations: List[Operation] = []
L27 |         self.roots: List[Operation] = []
L28 |         self.leaves: List[Operation] = []
L29 | 
L30 |     def append_operation(self, operation: Operation) -> None:
L31 |         """
L32 |         Appends an operation to all leaves in the graph and updates the relationships.
L33 | 
L34 |         :param operation: The operation to append.
L35 |         :type operation: Operation
L36 |         """
L37 |         self.operations.append(operation)
L38 | 
L39 |         if len(self.roots) == 0:
L40 |             self.roots = [operation]
L41 |         else:
L42 |             for leave in self.leaves:
L43 |                 leave.add_successor(operation)
L44 | 
L45 |         self.leaves = [operation]
L46 | 
L47 |     def add_operation(self, operation: Operation) -> None:
L48 |         """
L49 |         Add an operation to the graph considering its predecessors and successors.
L50 |         Adjust roots and leaves based on the added operation's position within the graph.
L51 | 
L52 |         :param operation: The operation to add.
L53 |         :type operation: Operation
L54 |         """
L55 |         self.operations.append(operation)
L56 |         if len(self.roots) == 0:
L57 |             self.roots = [operation]
L58 |             self.leaves = [operation]
L59 |             assert (
L60 |                 len(operation.predecessors) == 0
L61 |             ), "First operation should have no predecessors"
L62 |         else:
L63 |             if len(operation.predecessors) == 0:
L64 |                 self.roots.append(operation)
L65 |             for predecessor in operation.predecessors:
L66 |                 if predecessor in self.leaves:
L67 |                     self.leaves.remove(predecessor)
L68 |             if len(operation.successors) == 0:
L69 |                 self.leaves.append(operation)
```


### C11 — `graph_of_thoughts/controller/controller.py`：**Controller.run 的终止条件 = 队列空**

<!-- graph_of_thoughts_controller_controller.py:56-88 -->
```
L56 |     def run(self) -> None:
L57 |         """
L58 |         Run the controller and execute the operations from the Graph of
L59 |         Operations based on their readiness.
L60 |         Ensures the program is in a valid state before execution.
L61 |         :raises AssertionError: If the Graph of Operation has no roots.
L62 |         :raises AssertionError: If the successor of an operation is not in the Graph of Operations.
L63 |         """
L64 |         self.logger.debug("Checking that the program is in a valid state")
L65 |         assert self.graph.roots is not None, "The operations graph has no root"
L66 |         self.logger.debug("The program is in a valid state")
L67 | 
L68 |         execution_queue = [
L69 |             operation
L70 |             for operation in self.graph.operations
L71 |             if operation.can_be_executed()
L72 |         ]
L73 | 
L74 |         while len(execution_queue) > 0:
L75 |             current_operation = execution_queue.pop(0)
L76 |             self.logger.info("Executing operation %s", current_operation.operation_type)
L77 |             current_operation.execute(
L78 |                 self.lm, self.prompter, self.parser, **self.problem_parameters
L79 |             )
L80 |             self.logger.info("Operation %s executed", current_operation.operation_type)
L81 |             for operation in current_operation.successors:
L82 |                 assert (
L83 |                     operation in self.graph.operations
L84 |                 ), "The successor of an operation is not in the operations graph"
L85 |                 if operation.can_be_executed():
L86 |                     execution_queue.append(operation)
L87 |         self.logger.info("All operations executed")
L88 |         self.run_executed = True
```


### C12 — `examples/sorting/utils.py`：**test_sorting = 精确匹配 ground truth**（**成功率的判定方式**）

<!-- examples_sorting_utils.py:28-43 -->
```
L28 | def test_sorting(state: Dict) -> bool:
L29 |     """
L30 |     Function to test whether the final solution matches ground truth.
L31 | 
L32 |     :param state: Thought state that represents the final solution.
L33 |     :type state: Dict
L34 |     :return: Returns whether the solution matches the ground truth.
L35 |     :rtype: bool
L36 |     """
L37 | 
L38 |     try:
L39 |         correct_list = sorted(string_to_list(state["original"]))
L40 |         sorted_list = string_to_list(state["current"])
L41 |         return sorted_list == correct_list
L42 |     except:
L43 |         return False
```


### C13 — `examples/sorting/utils.py`：**num_errors = 局部误差打分**（error-scope 的代码实现）

<!-- examples_sorting_utils.py:46-77 -->
```
L46 | def num_errors(state: Dict) -> float:
L47 |     """
L48 |     Function to locally count the number of errors that serves as a score.
L49 | 
L50 |     :param state: Thought state to be scored.
L51 |     :type state: Dict
L52 |     :return: Number of errors.
L53 |     :rtype: float
L54 |     """
L55 | 
L56 |     try:
L57 |         unsorted_list = state["original"]
L58 |         if (
L59 |             "unsorted_sublist" in state
L60 |             and state["unsorted_sublist"] != ""
L61 |             and state["unsorted_sublist"] is not None
L62 |             and len(state["unsorted_sublist"]) < len(unsorted_list) - 5
L63 |         ):
L64 |             unsorted_list = state["unsorted_sublist"]
L65 |         correct_list = sorted(string_to_list(unsorted_list))
L66 |         current_list = string_to_list(state["current"])
L67 |         num_errors = 0
L68 |         for i in range(10):
L69 |             num_errors += abs(
L70 |                 sum([1 for num in current_list if num == i])
L71 |                 - sum([1 for num in correct_list if num == i])
L72 |             )
L73 |         num_errors += sum(
L74 |             [1 for num1, num2 in zip(current_list, current_list[1:]) if num1 > num2]
L75 |         )
L76 |         return num_errors
L77 |     except:
```


### C14 — `examples/sorting/sorting_032.py`：**GoT 的 GoO**（含 5 次/10 次/10 次的默认重试数）

<!-- examples_sorting_sorting_032.py:554-598 -->
```
L554 | def got() -> operations.GraphOfOperations:
L555 |     """
L556 |     Generates the Graph of Operations for the GoT method.
L557 | 
L558 |     :return: Graph of Operations
L559 |     :rtype: GraphOfOperations
L560 |     """
L561 |     operations_graph = operations.GraphOfOperations()
L562 | 
L563 |     plans = operations.Generate(1, 1)
L564 |     operations_graph.append_operation(plans)  # generate the sublists
L565 |     for i in range(1, 3):
L566 |         list_id = f"List {i}"
L567 |         sub_list = operations.Selector(
L568 |             lambda thoughts, list_id=list_id: [
L569 |                 thought for thought in thoughts if thought.state["part"] == list_id
L570 |             ]
L571 |         )
L572 |         sub_list.add_predecessor(plans)
L573 |         operations_graph.add_operation(sub_list)
L574 |         sort_sub_list = operations.Generate(1, 5)
L575 |         sort_sub_list.add_predecessor(sub_list)
L576 |         operations_graph.add_operation(sort_sub_list)
L577 |         score_sub_list = operations.Score(1, False, utils.num_errors)
L578 |         score_sub_list.add_predecessor(sort_sub_list)
L579 |         operations_graph.add_operation(score_sub_list)
L580 |         keep_best_sub_list = operations.KeepBestN(1, False)
L581 |         keep_best_sub_list.add_predecessor(score_sub_list)
L582 |         operations_graph.add_operation(keep_best_sub_list)
L583 | 
L584 |     final_aggregate = operations.Aggregate(10)
L585 |     operations_graph.append_operation(final_aggregate)
L586 |     operations_graph.append_operation(operations.Score(1, False, utils.num_errors))
L587 |     keep_best_aggregate_final = operations.KeepBestN(1, False)
L588 |     operations_graph.append_operation(keep_best_aggregate_final)
L589 | 
L590 |     operations_graph.append_operation(operations.Generate(1, 10))
L591 |     score_aggr_3 = operations.Score(1, False, utils.num_errors)
L592 |     score_aggr_3.add_predecessor(keep_best_aggregate_final)
L593 |     operations_graph.append_operation(score_aggr_3)
L594 |     operations_graph.append_operation(operations.KeepBestN(1, False))
L595 | 
L596 |     operations_graph.append_operation(operations.GroundTruth(utils.test_sorting))
L597 | 
L598 |     return operations_graph
```


### C15 — `examples/sorting/sorting_032.py`：**ToT 的 GoO**（b=20, depth=2）—— 对照组

<!-- examples_sorting_sorting_032.py:496-522 -->
```
L496 | def tot() -> operations.GraphOfOperations:
L497 |     """
L498 |     Generates the Graph of Operations for the ToT method.
L499 |     ToT uses a wider tree, where on each level there are more branches.
L500 | 
L501 |     :return: Graph of Operations
L502 |     :rtype: GraphOfOperations
L503 |     """
L504 |     operations_graph = operations.GraphOfOperations()
L505 | 
L506 |     operations_graph.append_operation(operations.Generate(1, 20))
L507 |     operations_graph.append_operation(operations.Score(1, False, utils.num_errors))
L508 |     keep_best_1 = operations.KeepBestN(1, False)
L509 |     operations_graph.append_operation(keep_best_1)
L510 | 
L511 |     for _ in range(1):
L512 |         operations_graph.append_operation(operations.Generate(1, 20))
L513 |         operations_graph.append_operation(operations.Score(1, False, utils.num_errors))
L514 |         keep_best_2 = operations.KeepBestN(1, False)
L515 |         keep_best_2.add_predecessor(keep_best_1)
L516 |         operations_graph.append_operation(keep_best_2)
L517 |         keep_best_1 = keep_best_2
L518 | 
L519 |     operations_graph.append_operation(operations.KeepBestN(1, False))
L520 |     operations_graph.append_operation(operations.GroundTruth(utils.test_sorting))
L521 | 
L522 |     return operations_graph
```


### C16 — `examples/sorting/sorting_032.py`：**ToT2 的 GoO**（b=10, depth=3）

<!-- examples_sorting_sorting_032.py:525-551 -->
```
L525 | def tot2() -> operations.GraphOfOperations:
L526 |     """
L527 |     Generates the Graph of Operations for the ToT2 method.
L528 |     ToT2 uses a tree with more levels, but with fewer branches per level.
L529 | 
L530 |     :return: Graph of Operations
L531 |     :rtype: GraphOfOperations
L532 |     """
L533 |     operations_graph = operations.GraphOfOperations()
L534 | 
L535 |     operations_graph.append_operation(operations.Generate(1, 10))
L536 |     operations_graph.append_operation(operations.Score(1, False, utils.num_errors))
L537 |     keep_best_1 = operations.KeepBestN(1, False)
L538 |     operations_graph.append_operation(keep_best_1)
L539 | 
L540 |     for _ in range(2):
L541 |         operations_graph.append_operation(operations.Generate(1, 10))
L542 |         operations_graph.append_operation(operations.Score(1, False, utils.num_errors))
L543 |         keep_best_2 = operations.KeepBestN(1, False)
L544 |         keep_best_2.add_predecessor(keep_best_1)
L545 |         operations_graph.append_operation(keep_best_2)
L546 |         keep_best_1 = keep_best_2
L547 | 
L548 |     operations_graph.append_operation(operations.KeepBestN(1, False))
L549 |     operations_graph.append_operation(operations.GroundTruth(utils.test_sorting))
L550 | 
L551 |     return operations_graph
```


### C17 — `examples/sorting/sorting_032.py`：**默认运行参数**（budget=30 美元、samples 0..99、5 个方法）

<!-- examples_sorting_sorting_032.py:716-732 -->
```
L716 | if __name__ == "__main__":
L717 |     """
L718 |     Input (x)   : an unordered list of 32 numbers between 0 and 9 (inclusive)
L719 |     Output (y)  : a sorted list of 32 numbers between 0 and 9 (inclusive)
L720 |     Correct     : y == sorted(x)
L721 |     Input Example:
L722 |         [0, 1, 9, 4, 2, 2, 0, 5, 1...]
L723 |     Output Example:
L724 |         [0, 0, 0, 0, 1, 1, 1, 1, 2...]
L725 |     """
L726 |     budget = 30
L727 |     samples = [item for item in range(0, 100)]
L728 |     approaches = [io, cot, tot, tot2, got]
L729 | 
L730 |     spent = run(samples, approaches, budget, "chatgpt")
L731 | 
L732 |     logging.info(f"Spent {spent} out of {budget} budget.")
```


### C18 — `graph_of_thoughts/language_models/config_template.json`：**默认 LLM 超参**（temperature 1.0 / max_tokens 1536 / cost 表）

<!-- graph_of_thoughts_language_models_config_template.json:1-21 -->
```
L1 | {
L2 |     "chatgpt" : {
L3 |         "model_id": "gpt-3.5-turbo",
L4 |         "prompt_token_cost": 0.0015,
L5 |         "response_token_cost": 0.002,
L6 |         "temperature": 1.0,
L7 |         "max_tokens": 1536,
L8 |         "stop": null,
L9 |         "organization": "",
L10 |         "api_key": ""
L11 |     },
L12 |     "chatgpt4" : {
L13 |         "model_id": "gpt-4",
L14 |         "prompt_token_cost": 0.03,
L15 |         "response_token_cost": 0.06,
L16 |         "temperature": 1.0,
L17 |         "max_tokens": 4096,
L18 |         "stop": null,
L19 |         "organization": "",
L20 |         "api_key": ""
L21 |     },
```


### C19 — `README.md`：最小可跑示例（**GoO 三行即可表达一个方法**）

<!-- README.md:39-73 -->
```
L39 | ```python
L40 | from examples.sorting.sorting_032 import SortingPrompter, SortingParser, utils
L41 | from graph_of_thoughts import controller, language_models, operations
L42 | 
L43 | # Problem input
L44 | 
L45 | to_be_sorted = "[0, 2, 6, 3, 8, 7, 1, 1, 6, 7, 7, 7, 7, 9, 3, 0, 1, 7, 9, 1, 3, 5, 1, 3, 6, 4, 5, 4, 7, 3, 5, 7]"
L46 | 
L47 | # Create the Graph of Operations
L48 | gop = operations.GraphOfOperations()
L49 | gop.append_operation(operations.Generate())
L50 | gop.append_operation(operations.Score(scoring_function=utils.num_errors))
L51 | gop.append_operation(operations.GroundTruth(utils.test_sorting))
L52 | 
L53 | # Configure the Language Model (Assumes config.json is in the current directory with OpenAI API key)
L54 | lm = language_models.ChatGPT("config.json", model_name="chatgpt")
L55 | 
L56 | # Create the Controller
L57 | ctrl = controller.Controller(
L58 |   lm, 
L59 |   gop, 
L60 |   SortingPrompter(), 
L61 |   SortingParser(),
L62 |   # The following dictionary is used to configure the initial thought state
L63 |   {
L64 |     "original": to_be_sorted,
L65 |     "current": "",
L66 |     "method": "cot"
L67 |   }
L68 | )
L69 | 
L70 | # Run the Controller and generate the output graph
L71 | ctrl.run()
L72 | ctrl.output_graph("output_cot.json")
L73 | ```
```
