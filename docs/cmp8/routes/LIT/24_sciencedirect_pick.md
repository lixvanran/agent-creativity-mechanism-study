# 24 · ScienceDirect 上的选定论文 — 精读提取

> ⚠️ 任务书给的 `https://www.sciencedirect.com/` 是**期刊主页**，不是论文。
> 本篇的产出 = **"我在 ScienceDirect 上选了这一篇，理由是什么"** + 按模板的完整提取。
> **取证等级声明见 §0.3**（我读到了什么、没读到什么，逐条写明）。

---

## 0. 引用

### 0.1 论文元数据（已用 4 个独立源交叉核对）

| 项 | 内容 | 核对源 |
|---|---|---|
| **标题** | **Diversity-driven reasoning: Mitigating logical errors in LLMs through social-attribute guided multi-agent collaboration** | Crossref / OpenAlex / S2 / ScienceDirect 页 |
| **作者** | Liangji Zhang, **Jianbo Yuan**, Yougming He, Miao Yu, Kun Zhu, Zhenni Yu<br>（原文脚注：*"Liangji Zhang and Jianbo Yuan contribute equally to this work."*） | ScienceDirect 页 / ACM 文献目录 |
| **作者名拼写不一致** | OpenAlex 作 `Jianbo Yuan` / `Yang He`；Semantic Scholar 作 `Jian-Bo Yuan` / `Yougming He`；ScienceDirect 原文署名段作 **Yougming He** ⇒ 以 ScienceDirect 原文为准 | 三源对比 |
| **期刊 / venue** | *Engineering Applications of Artificial Intelligence* (**EAAI**), **Vol 164, Issue PB** | ACM 文献目录 / Mendeley 目录 |
| **DOI** | **10.1016/j.engappai.2025.113126** | Crossref / OpenAlex / S2 / Unpaywall |
| **PII（ScienceDirect 文章号）** | **S0952197625031574** | ScienceDirect URL + 图片 CDN 路径 `ars.els-cdn.com/content/image/1-s2.0-S0952197625031574-gr6.sml` |
| **ScienceDirect 落地页** | `https://www.sciencedirect.com/science/article/pii/S0952197625031574` | — |
| **年份** | **在线首发 2025-11-30**（OpenAlex `publication_date`）；**正式卷期 2026 年 6 月**（ACM 目录 "Published: 04 June 2026"，Vol 164 为 2026 年卷）；Crossref `issued` 记 2026 | 三源对比 |
| **预印本** | SSRN：**"A Multi-Attribute Mixture Expert Reasoning Approach Based on Large Language Models"**, `abstract_id=5167458`（= 同一工作的更早版本，框架名相同但写作 "Mixture Expert"） | papers.ssrn.com |
| **作者声称的代码** | `https://github.com/ioio0614/MAME` —— **⚠️ 2026-10-21 实测 404，作者账号下 4 个公开仓库里没有它**（见 §6.7） | GitHub API |
| **Keywords** | Group decision making; Large language model; Multi-agent collaboration | Mendeley 目录 |
| **Index Terms** | Computing methodologies; Artificial intelligence; Distributed artificial intelligence; Cooperation and coordination; Intelligent agents; Multi-agent systems; Knowledge representation and reasoning; Reasoning about belief and knowledge; Information systems; World Wide Web; Web applications; Crowdsourcing | ACM 文献目录 |
| **参考文献量** | 51 条 | ScienceDirect 页 |

**一句话**：声称在多轮复杂推理中，**用"社会属性（人格）"给不同 agent 分配不同视角，再用群体决策理论的置信矩阵抑制"错误固化与答案收敛"**，从而缓解 LLM 的逻辑错误。

### 0.2 我为什么选它（**选择依据 + 跟我们项目的关系**）

**选择方法（可复核）**：`https://www.sciencedirect.com/` 直接 curl 返回 **403**（Elsevier 反爬），站内检索 `https://www.sciencedirect.com/search?qs=...` 同样 403 ⇒ 我改用 **Crossref API 限定 Elsevier member=78 + type=journal-article**，跨 5 个检索式建立候选池：

```
multi-agent diversity
diversity multi-agent large language model
self-reflection LLM agent
diverse reasoning paths language model
multi-agent debate diversity role
diverse perspectives self-consistency LLM
social attribute multi-agent collaboration logical errors
hierarchical self-organizing multi-agent topology
reasoning diversity measure evaluation LLM agent
```

**排序标准（三条，按优先级）**：
1. **主题命中度**：本组主题 = 多智能体多样性 / 推理架构 / 自我反思，三者命中几个。
2. **是否回答我们项目的核心区分点（U7：多样性 ≠ 思维面宽）**：即"多样性"在文中被定义成**可枚举的结构量**，还是只是一句形容词。
3. **可核验性**：评测是否有 ground truth、是否有数字、是否可复现。

**最终选择理由**：
- 它是候选池里**唯一同时满足**以下四条的论文：
  ① **主题最贴**：三个子主题全中（多智能体**多样性** + **推理架构** + 自我纠错/反馈回路）。
  ② **它把"多样性"定义成了结构量**：MAP 给每个 agent 分配**离散的、可枚举的社会属性向量**（NEO 大五人格），并用 **"权重向量调制 + 生成策略"** 让属性真的进入生成过程 ⇒ **这是候选池里唯一一篇正面回答 U7 的**（它把"异质性"写成了坐标系，而不是"角度多"）。
  ③ **它有 ground truth 的可核验评测**（GSM8K 类任务准确率），比本组其他几篇（ADHD 的开放题 judge 打分、MAS_Diversity 的模拟）**更接近我们"维度可被依据包核验"的要求**。
  ④ **它是一个真正的"反馈回路"架构**（GFF 的置信矩阵回灌下一轮 prompt）⇒ **比 ADHD 更接近我们的 L1（状态转移律）**，是"路线 A → L1"之间的一个已发表中间点。
- **落选者与原因（同样重要）**：
  - **HiSOMA**（ESWA 2024, DOI 10.1016/j.eswa.2024.124117）：**自组织神经网络 + 多智能体 DRL 的分层拓扑** ⇒ 这是**路线 B/C 的直接对标**（学出来的拓扑），而且**全文在 SSRN 上是绿色 OA、可读**。落选原因：它做的是 **MARL 不是 LLM 推理**，且**"多样性"不是它的变量**（它的变量是任务性能与分层）⇒ 对我们"思维面宽度"这个核心问题**相关性更低**。⚠️ 但它值得单独排期读。
  - **SelfCorrect-Agent**（Neurocomputing 2026, DOI 10.1016/j.neucom.2025.132546）：命中"自我反思"，SSRN 绿 OA 可读。落选原因：**单 agent 自纠错**，**没有多智能体多样性维度**。
  - **"Encouraging divergent thinking in LLMs through multi-agent debate"**（arXiv 2305.19118，Liang et al.）—— 它是 MAME 的**参考文献里最贴近本组主题**的一篇（发散思维 + 多智能体辩论），但**不在 ScienceDirect**（arXiv）⇒ 与"在 ScienceDirect 上找"的任务要求不符。**我建议下一轮单独精读它**。
- **跟我们项目的关系（一句话）**：**MAME 证明了"把异质性写成一个显式属性向量，并让它进入生成过程"能提升有 ground truth 的任务准确率；但它证明的是"准确率"，不是"思维面宽度"** ⇒ 它是我们 U7 的**最佳对照组**：任何"多样性提升推理"的论文，都应该被追问"**你测的是准确率还是承重维度数？**"。

### 0.3 ⚠️ 取证等级（**必读，别当成全文精读**）

**读到了**（原文英文，来自 ScienceDirect 页面本身）：
- 完整 **Abstract**（两版：ScienceDirect 原版 + Mendeley 目录版 + ACM 目录版，三者一致）
- **Introduction** 大段（研究动机、对 CoT/ToT/GoT/Self-Consistency/Self-Refine/Reconcile/MAD 的定位、贡献三条）
- **"Effects of GFF"** 一节开头一段（与 Debate / MAD / Reconcile / MAME 的对比，Qwen2.5:7b、数学推理、3 agent）
- **Conclusion** 全文（含 limitations 原文）
- **CRediT authorship contribution statement**、**Declaration of competing interest**
- **Index Terms**、**Keywords**、**参考文献 51 条**（含 Besta et al. *Graph of Thoughts*、Yao et al. *ToT*、Hui et al. *RoT*、Madaan et al. *Self-Refine*、Shinn et al. *Reflexion*、Chen et al. *ReConcile*、Du et al. *MAD*、Liang et al. *Encouraging divergent thinking*、Barrick et al. 1998 人格-团队效能、**Costa & McCrae 1992 NEO 人格问卷**、Park et al. 2023 *Generative Agents*）
- **元数据**：Crossref / OpenAlex / Semantic Scholar / Unpaywall 四源

**没读到**（**不编造，下面全部标为"未读到"**）：
- ❌ **四个数据集的具体名称**（只读到 "four publicly available datasets" 和三类任务：数学/逻辑/常识推理；图注里的 `MalArb/CSSMK/Coin/Eye/SingularQA` 疑为检索工具自动生成的缩写，**不可信，不采用**）
- ❌ **完整的实验表格**（逐数据集逐模型的准确率矩阵）
- ❌ **消融表**（MAP 拿掉会怎样、GFF 拿掉会怎样——**论文似乎有** "we compare the change in accuracy ... as the number of debate rounds increases as well as the number of agents increases"，但具体数字未读到）
- ❌ **成本数字**（调用数 / token / 墙钟时间 / 美元）
- ❌ **置信矩阵与 credibility score 的公式**
- ❌ **"weight vector modulation" 的实现细节**（是否改权重 / 改隐状态 / 只改 prompt —— **未能确认**）
- ❌ **最大辩论轮数**（只读到"直到达到最大轮数"，具体值未读到）
- ❌ **每个 agent 分到几个社会属性**

**为什么读不到全文（如实报告已试过的路径）**：
| 路径 | 结果 |
|---|---|
| `curl https://www.sciencedirect.com/` | **403**（浏览器 UA、Accept-Language 全带上仍 403） |
| `curl https://www.sciencedirect.com/search?qs=multi-agent+diversity` | **403** |
| `curl https://www.sciencedirect.com/science/article/pii/<PII>` | **403** |
| `curl https://linkinghub.elsevier.com/retrieve/pii/<PII>` | 200（但无正文） |
| `api.elsevier.com/content/...` | 需 API key，未用 |
| `api.crossref.org/works/{DOI}` | 200，但 **`abstract` 字段为空** |
| `api.openalex.org/works/doi:{DOI}` | 200，**`abstract_inverted_index` 为 null** |
| `api.semanticscholar.org/graph/v1/paper/DOI:{DOI}` | 200，**abstract 为空** |
| `api.unpaywall.org/v2/{DOI}` | 返回空对象；**closed access，无 OA 副本** |
| `ouci.dntb.gov.ua`（Elsevier 摘要镜像） | **403** |
| `colab.ws/articles/{DOI}` | **403** |
| `r.jina.ai` 文本代理 | **超时**（30s 上限内未返回） |
| **web_search 后端** | ✅ **成功读到 ScienceDirect 页面正文节选**（本篇正文即由此取得） |
| Mendeley 目录页 / ACM 文献目录页（`acm-stag.literatumonline.com`） | ✅ 成功（摘要 + Index Terms + 作者 + 卷期） |
| SSRN `abstract_id=5167458` | ✅ 成功（早期版摘要） |

---

## 1. 核心机制（具体到能照着实现）

### 1.1 框架总图：MAME = GFF + MAP

| 项 | 内容 |
|---|---|
| **输入** | 一个有标准答案的推理题（数学 / 逻辑 / 常识）。**多轮**输入的是"上一轮各 agent 的答案 + 各自的评价 + 置信度"。 |
| **状态表示** | **每个 agent 自己的答案 + 一张 agent×agent 的动态置信矩阵 + 每个答案的 credibility score**。⚠️ 论文用"state"这个词指代"群体共识状态"，**不是**我们那种"可核验的承重信息包"。矩阵是**结构量**（谁对谁有多大影响），**不含 embedding**（至少我读到的部分没有）。 |
| **动作/算子** | ① **初始作答**（各 agent 独立、带各自社会属性的 prompt）② **互评 + 打分**：每个 agent 对**其他每个 agent** 给出"可信度"，并对**每个答案**给出"可行置信度"③ **基于反馈的修正**（refine）④ **终止投票**：取 confidence 最高的答案作为最终答案（**由 agent 自报的置信度决定**）。 |
| **过程/回路** | **真回路**（与 ADHD 的固定流水线不同）：`初始答案 → 多轮(互评 → 修正) → 终止`。原文：*"multiple agents first give an initial answer … second, each agent … refines its answer to the suggestions of the other agents and gives the credibility of the pair of agents and the feasible confidence of the answer, and finally each agents refines its answer based on the feedback. This cycle continues until the maximum number of rounds is reached, and the final answer with the highest confidence level is taken as the answer to the given question."* **停止条件 = 最大轮数**（⚠️ 具体值未读到；**没有**置信度收敛阈值、没有自适应停止）。 |
| **输出** | 最终答案（+ 置信度）。 |
| **谁来评价 / 评价信号怎么回传** | ⚠️⚠️ **两层，而且两层都自评**：<br>① **系统内部**：GFF 的**置信矩阵 + credibility score 由 agent 互相给出**，然后**回灌进下一轮的 prompt**（"based on the collective feedback"）—— **这是本组几篇里唯一真的"评价→更新"闭环**。<br>② **系统外部**：任务准确率（有 ground truth）。<br>⚠️ **但"最终哪一票胜出"由系统自报置信度决定** ⇒ 成功判定链路里**掺进了系统的自我认知**。 |

### 1.2 两个子机制（逐字）

**GFF（Group Feedback Framework）** —— 把群体决策理论搬进多智能体：
> *"we define a dynamic confidence matrix and an answer credibility score to quantify inter-agent influence. These metrics dynamically guide agents in adjusting their reasoning paths based on collective feedback."*（Abstract）

**MAP（Multi-Attribute Prompting）** —— 给每个 agent 分配不同的社会属性：
> *"we propose a Multi-Attribute Prompting (MAP) method that assigns distinct social attributes to each agent, fostering perspective diversity through **weight vector modulation** and generation strategies."*（Abstract）

**属性来源**：NEO 人格问卷（**Costa & McCrae 1992**，参考文献第 1 条）+ Barrick et al. 1998（人格→团队效能）+ Park et al. 2023 *Generative Agents*（人格驱动 agent）。⇒ **异质性轴 = 大五人格的某个子空间**（具体用了哪几维、每维高低怎么定、每个 agent 怎么组合 —— **未读到**）。

### 1.3 作者自己写的贡献三条（Introduction 结尾）

> *"Inspired by group decision theory, we propose GFF to improve the reasoning ability of agents. The agent in the framework have a confidence score for other agents and reasoning answers, and through multiple rounds of dialogues and continuous feedback, each agent in the framework can continuously adjust and optimize their reasoning paths."*
> *"To reduce the issue of error accumulation and enhance the diversity of the dialogue process, we propose a MAP approach. By assigning each agent different social attributes, agents are encouraged to provide feedback from various perspectives, thereby reducing the risk of logical biases and error accumulation."*
> *"We conducted extensive experiments on four publicly available datasets to discuss the change in accuracy under reasoning in a MAME as the number of debate rounds increases as well as the number of agents increases while comparing with other frameworks with multi-agent synergy … Compared with other methods, there is a significant improvement in mathematical reasoning, logical reasoning, and common sense reasoning in our proposed method."*

---

## 2. 关键数字

### 2.1 实验设置
| 项 | 内容 |
|---|---|
| 模型 | **Qwen2.5 全系列：3B / 7B / 14B / 32B / 72B**（⚠️ 只有开源模型 ⇒ 无 GPT-4/Claude 对照） |
| 数据集 | **4 个公开数据集**（**名字未读到**），覆盖**数学推理 / 逻辑推理 / 常识推理**三类 |
| 对照方法 | **Debate（多智能体辩论）、MAD、ReConcile、MAME**；相关工作里还对比了 CoT / ToT / GoT / RoT / Self-Refine / Self-Consistency / Reflexion |
| agent 数 | 主对比图用 **3 个 agent**（原文：*"In all four frames, the number of agents is three. Let's take Qwen2.5:7b for example."*）；另有"随 agent 数增加"的曲线 |
| 轮数 | 最大轮数（**数值未读到**）；论文声明做了"轮数 vs 准确率"的曲线 |

### 2.2 主指标读数（**只有摘要级的三个数**）

| 任务类型 | 提升（vs baseline） |
|---|---|
| 数学推理 | **最高 +24.05 %** |
| 逻辑推理 | **最高 +39.1 %** |
| 常识推理 | **最高 +4.94 %** |

⚠️⚠️ **三个数都是 "up to"（最高值）**，不是均值、不是期望、不是 CI。**逐数据集逐模型的完整矩阵未读到。**

### 2.3 消融
**未读到。** 论文的贡献列表提到会讨论"轮数增加时准确率变化"和"agent 数增加时准确率变化"（这两条**是 scaling 曲线，不是组件消融**）。**MAP 拿掉 / GFF 拿掉 的消融表未读到**（是否存在于正文，未能确认）。

### 2.4 成本
**未读到任何成本数字**（无调用数 / token / 墙钟时间 / 美元）。但 Conclusion 自认 **"high computational overhead"**（多 agent × 多轮 × 每轮全互评 ⇒ 调用数是 `O(agents² × rounds)` 量级，这是结构决定的，不依赖具体数字）。

---

## 3. ★ 它的「成功标准」是什么

### 3.1 怎么判定自己成功
- **指标**：四个公开数据集上的**任务准确率**（有 ground truth ⇒ **客观、可核验**，这是它比 ADHD 强的地方）。
- **对照**：同模型同题的 **Debate / MAD / ReConcile**（多智能体同类方法）+ 单模型基线。
- **成功的形状**：三类任务上准确率全面提升；"最高"口径为 **+24.05% / +39.1% / +4.94%**。
- **阈值**：**没有预注册门槛**（没有"至少 +X% 才算成功"）。

### 3.2 否证 / 失败条件
**基本没写。** Conclusion 里的 "limitations" 是**工程挑战清单**，不是**否证条件**（没有"如果 MAP 的增益在 XXX 以下，则本方法不成立"这类陈述）。原文：

> *"Although MAME performs well in enhancing logical and mathematical reasoning, its limitations and potential problems must be pointed out to provide a more comprehensive perspective and guide future research directions."*

### 3.3 有没有报告"不可分辨"
**❌ 没有。** 具体缺失：
- **无重复次数、无方差、无置信区间、无显著性检验**。
- **"up to" 口径**本身就是一个**选择偏差**：从一张表里取最好的格子报出来。⇒ **"+39.1%" 是最好情况，不是期望。**
- 常识推理只有 **+4.94%**（三类里最弱），在无重复、无方差的条件下，**这个量级与噪声不可区分** —— 但作者把它和其他两个并列报出。
- ⚠️ **更隐蔽的一层**：**最终答案由"confidence 最高"选出**，而 confidence 是 **agent 自报**的。LLM 的自报置信度**众所周知校准很差**（论文自己在 Introduction 里批评 self-refine "may have unstable intrinsic reflection ability of the large language models **in the absence of external feedback**"，却在自家框架里用了同类的自报机制做最终仲裁）。⇒ **它批评的问题在自己身上复现了。**

---

## 4. 自认的局限（**原话**）

Conclusion 段（逐字）：

> *"Although MAME performs well in enhancing logical and mathematical reasoning, its limitations and potential problems must be pointed out to provide a more comprehensive perspective and guide future research directions. **This framework faces challenges such as high computational overhead, uneven performance across different task types, sensitive design of social attributes, difficulty in expanding the number of agents, and lack of theoretical guarantees.** Especially when the base large language…"*

（最后一句在抓取时被截断，⚠️ 已读到的部分止于此。）

拆成作者自认的 5 条：
1. **计算开销高**（high computational overhead）
2. **不同任务类型上表现不均**（uneven performance across different task types）
3. **社会属性设计敏感**（sensitive design of social attributes）—— ⚠️ **这一条最要命**：意味着"换个属性组合效果就变"，而**没有任何稳健性实验**（未读到）
4. **难以扩展 agent 数量**（difficulty in expanding the number of agents）
5. **缺乏理论保证**（lack of theoretical guarantees）

另外 Introduction 里作者自陈的问题意识（对**我们**也有用）：
> *"existing frameworks for enhancing the reasoning ability of agent through multi-agent collaboration lack theoretical support, and in the process of multi-agent dialogues, after the agent has formed an initial stance on a problem or a solution, it is difficult to generate new reflections or change the original stance due to the lack of effective feedbacks and challenges, similar to the **confirmation bias** of human beings in decision-making."*

> *"if debates between agents are not sufficiently diverse, or if agent tends to communicate with other agents that have similar views to their own, they may not be able to fully explore all possible solutions and viewpoints, leading to a **limited scope of thinking for the system as a whole**."*

⇒ 注意最后这句：**"limited scope of thinking for the system as a whole"** —— 这是本组材料里**最接近我们"思维面宽度"表述**的一句。**但它只是**用它来论证"需要多样性"，**它没有测"scope of thinking"这个量**。

---

## 5. ★ 对我们项目的可迁移点

### 5.1 映射到路线 A / B / C / 优化器契约

| 我们的坐标 | MAME 对应 | 可迁移性 |
|---|---|---|
| **路线 A（人写死固定拓扑）** | ① 人写死 N 个 agent 的人格 prompt ② 人写死"初始→互评→修正→投票"的轮次拓扑 ③ **但**轮次内是**真回路** | ✅ 高 |
| **路线 B（训练学出操作序列）** | **无**（纯推理时方法，无任何训练/学习） | ❌ 零 |
| **路线 C（人定拓扑 + 训练调参）** | ⚠️ "**weight vector modulation**"（Abstract 原词）**可能**触及参数/隐状态层，但**未能确认**。若真是权重层面的调制 ⇒ 这是路线 C 的雏形，**必须先查清再决定** | ⚠️ **待验证，高价值** |
| **优化器契约 L0–L4** | L0 目标函数=任务准确率（**有**）；L1 状态转移=**有**（置信矩阵回灌 prompt）；L2 更新规则=**有**（"按集体反馈调整推理路径"，但是 LLM 提示级，非梯度）；L3 DEV 集=**有**（4 个公开数据集）；L4 噪声地板 δ=**无** | ✅ **L1 那一格是本组最完整的** |
| **测量协议** | ⚠️ 测的是**准确率**，不是**承重维度数** | ❌ 不可直接用 |
| **DEV 集设计** | ✅ **4 个有 ground truth 的公开数据集** ⇒ 这是本组里**唯一带标准答案**的评测集形态 | ✅ 值得引入 |

### 5.2 能省我们什么（具体）

1. **省掉"多样性轴该长什么样"的发散探索。** MAME 给了现成答案：**用一个人格属性向量做坐标轴**（离散、可枚举、可写进 prompt、可核验）。我们不必再自己发明"框架维度"这个词怎么落地。
2. **省掉"要不要给 agent 配异质身份"这个实验的第一次尝试。** 直接抄"异质属性 + 逐对可信度矩阵"的结构，省掉试错。
3. **省掉"评价信号怎么回灌"的设计工作。** GFF 的形式（每个 agent 对每个其他 agent 给可信度 + 对每个答案给置信度 ⇒ 组成矩阵 ⇒ 回灌）是一个**可以直接实现**的 5 行协议。⇒ **这是本组 4 篇里最值得直接抄的一段代码级设计。**
4. **省掉"我们的 DEV 集要不要用有标准答案的题"这个争论** —— 至少**混进**一些有 ground truth 的题，用**准确率**当**第二判据**（与"净维度增益"正交），可以帮我们判断"宽度提升"是不是只带来了"更多话"。

### 5.3 要改什么才能用

- **⚠️ 最关键的一处替换：把"自报 confidence"换成"可核验依据"。**
  MAME 的整个回路靠** agent 自报的置信度**驱动。我们不能直接用（见 §6.1 U6）。⇒ **可迁移的形态是：保留"逐对影响矩阵 + 置信度"这个结构，但把矩阵的单元格从"agent 自报的可信度"换成"**这条反馈实际引用的依据 ID**"。**
  ⇒ 这样一来：矩阵变成 **agent × 依据** 的二值/计数表 ⇒ **可核验、可归因、离散** ⇒ **不依赖 embedding**（绕开 U2）、**不依赖措辞相似度**（绕开 U3）。
  ⇒ **这可能是本组 6 篇里最直接命中我们"依据包 + 承重维度"定义的一个可执行设计。** 建议列为**下一个实验臂**。
- **"weight vector modulation" 必须查清**。如果它改的是模型权重 ⇒ 那是路线 C；如果它只改 prompt ⇒ 那就只是 persona 提示工程，和 ADHD 的帧没有本质区别。**在查清之前不要把它算作路线 C 的证据。**
- **成本必须自己量**：`O(agents² × rounds)` 次调用。⇒ 在我们的成本模型里这会很贵 ⇒ 我们的臂应该用**少量 agent + 少量轮次**（比如 3 agent × 2 轮），否则净维度增益会被成本吃掉。

---

## 6. ★ 不可迁移 / 会误导我们的点

### 6.1 ⚠️⚠️ U6 自评污染 —— **命中，而且是"结构性"命中**

两层自评：
1. **互评层**：每个 agent 给其他 agent 打可信度 —— **agent 之间互相评**。同源模型（全部 Qwen2.5）⇒ 互评者与被评者共享**完全相同的先验与偏见** ⇒ 这不是独立信号，是**同源信号的相关副本**。
2. **仲裁层**：**最终答案由"confidence 最高"决定** ⇒ 系统的成败部分由**系统自己的自我认知**决定。

⚠️ **最尖锐的一点**：论文在 Introduction 里批评 self-refine *"may have unstable intrinsic reflection ability of the large language models **in the absence of external feedback**"*，却在自家框架里用**自报 confidence** 做最终仲裁，**没有外部反馈**。⇒ **它批评的病在自己身上复现了。**

⇒ **我们绝不能抄这一层。** 我们的判据必须来自**依据包**（外部可核验），不能来自 agent 自报。

### 6.2 ⚠️ U7 多样性 ≠ 思维面宽 —— **本篇最核心的混淆**

- MAME 的"多样性" = **人格异质性**（personality diversity），论文原话：*"highlight the critical role of **personality diversity** in mitigating logical stagnation"*。
- **它的判据是任务准确率**，**从不用"多样性"本身或"思维面宽度"做判据**。
- ⇒ **它证明的是"异质人格 ↑ 准确率"，不是"异质人格 ↑ 承重维度数"。**
- ⚠️ 尤其要警惕这条替代解释：**准确率提升可能主要来自"更多投票 + 更多样的人容易碰巧对上一个"（投票收益 / 覆盖收益），而不是"信息维度更多"**。论文有"agent 数 vs 准确率"的曲线（说明作者意识到了这个问题），但**未读到**是否有"**同 agent 数、只改属性**"的对照 ⇒ **这个关键分离实验我们必须自己做。**
  ⇒ **可执行的否证实验**：固定 agent 数、固定轮数、固定模型，**只改属性向量**（同质 vs 异质），测**净维度增益**。如果净维度增益不变而准确率变了 ⇒ 提升来自投票收益，与思维面无关。**这正是我们要做的那个区分。**

### 6.3 ⚠️ U2 embedding —— **未确认（必须标注）**

- 我读到的部分（Abstract / Intro / GFF 段 / Conclusion）**没有出现 embedding 相似度作为多样性度量**。GFF 的量是**置信矩阵**（结构量）⇒ **表面上比 MAS_Diversity 干净**。
- ⚠️ 但 **"weight vector modulation"** 这个词**未确认实现**：如果它是在**隐向量/权重层面**做调制，那"多样性"实际上是在**几何空间**里定义的 ⇒ **命中我们的 U2 风险**（中文句级 embedding 几何无分辨率）。
- ⇒ **行动**：在能读到方法细节之前，**不要把 MAME 当作"避开 embedding 的干净范例"**。它最多只能证明"**多样性轴可以用一个显式属性向量来写**"，不能证明"**多样性度量可以脱离 embedding**"。

### 6.4 ⚠️ U4 测量带宽 > 信号带宽 —— **命中**

- 三个主数字全是 **"up to"**（最好格），**无重复、无方差、无 CI、无显著性**。
- 常识推理 **+4.94%** 在这种条件下**与噪声不可分辨**。
- "**sensitive design of social attributes**"（作者自认）⇒ 属性配置本身就是**一个未搜索的超参空间**，而"取最好的那格"正是**超参搜索 + 报告最好值**的标准模式 ⇒ **"up to 39.1%" 极可能是"在属性配置与轮数上搜了一遍后取最好格"**。

### 6.5 ⚠️ U5 缺优化策略 —— **部分命中**

- 它**有目标函数**（准确率）、**有更新规则**（多轮反馈修正）、**有 DEV 集**（4 个公开数据集）⇒ 比 ADHD 完整。
- 但 **L4 噪声地板 δ 仍缺** ⇒ "提升"没有显著性门槛。

### 6.6 量纲不可比

- 它的"提升"是**任务准确率百分点**（有 ground truth）；我们的主判据是**净维度增益**。⇒ **两个数不能放在一张表里比**。
- 它的 agent 数=3、轮数未知；我们的臂若用 5+ agent、多轮，成本量级完全不同 ⇒ **必须先对齐 agent 数与轮数再比较**。

### 6.7 ⚠️ 不可复现（**硬事实**）

- Abstract 与 SSRN 摘要都写：*"The code is open source: https://github.com/ioio0614/MAME."*
- **2026-10-21 实测**：`https://api.github.com/repos/ioio0614/MAME` ⇒ **404 Not Found**；`https://github.com/ioio0614/MAME` ⇒ **404**；GitHub 仓库搜索 `MAME multi-agent reasoning` ⇒ **0 命中**。
- 作者账号 `ioio0614` **存在**（User，4 个 public repo），但公开仓库是：`AMCFNet`（2022）、`Economic-preference-dataset`（2026-09-14）、`OI-wiki`（2021）、`Part-of-the-Apple-dataset`（2022）—— **没有 MAME**。
- ⇒ **代码已私有或删除。论文的这套方法目前无法复现。** ⚠️ 这本身就是一个值得写进我们报告的**失败条件实例**："声称开源 ≠ 可复现"，**任何基于论文数字的复刻计划都应先验证代码可得性**。

### 6.8 其他

- **只有 Qwen2.5 开源模型** ⇒ 结论**不能外推**到 GPT-4/Claude 系（尤其不能外推到"强模型上多智能体辩论可能反而不如单模型"的情况）。
- **SSRN 早期版标题/框架名不同**（*Multi-Attribute **Mixture** Expert* vs *Multi-Attribute **Hybrid** Expert*）⇒ 检索时**两个名字都要试**；引用时**以期刊版为准**。

---

## 7. 逐字摘录

1. **Abstract**（ScienceDirect 页面）：
   > *"This paper proposes a Multi-Attribute Hybrid Expert (MAME) framework to address the challenges of error solidification in large language models (LLMs) arising from logical error accumulation and answer convergence during multi-round complex reasoning tasks. First, we introduce a Group Feedback Framework (GFF) that integrates group decision-making theory into multi-agent collaboration. By simulating human consensus formation and error correction mechanisms, we define a dynamic confidence matrix and an answer credibility score to quantify inter-agent influence. These metrics dynamically guide agents in adjusting their reasoning paths based on collective feedback."*

2. **Introduction**（方法总述段 —— **本篇最该抄的一句**）：
   > *"Specifically, multiple agents first give an initial answer to a given question, second, each agent in the framework refines its answer to the suggestions of the other agents and gives the credibility of the pair of agents and the feasible confidence of the answer, and finally each agents refines its answer based on the feedback. This cycle continues until the maximum number of rounds is reached, and the final answer with the highest confidence level is taken as the answer to the given question."*

3. **Conclusion / Limitations**（原话）：
   > *"This framework faces challenges such as high computational overhead, uneven performance across different task types, sensitive design of social attributes, difficulty in expanding the number of agents, and lack of theoretical guarantees."*

4. **Introduction**（作者对"多样性不足"的后果的表述 —— 最接近我们语汇的一句）：
   > *"if debates between agents are not sufficiently diverse, or if agent tends to communicate with other agents that have similar views to their own, they may not be able to fully explore all possible solutions and viewpoints, leading to a limited scope of thinking for the system as a whole."*

5. **Abstract 末句**（自我定位，注意是 "first framework" 式的优先权声明）：
   > *"MAME represents the first framework to embed social personality theory within multi-agent cooperation, providing an interpretable error correction mechanism for LLM-based complex reasoning."*

---

## 8. 读完后我自己的判断

- **最值得抄**：**"逐对影响矩阵"这个结构**。MAME 用它把"群体里的互相影响"变成了**可枚举、可核验的 agent×agent 表**。⇒ 我们的对应物应该是 **agent × 依据** 的表（谁引用了哪条依据、引用了几次）⇒ **这就是"承重信息"的天然载体**：不依赖 embedding、不依赖措辞相似度、离散可计数、且**能直接测"改变决策"**（若一条依据被引用了却不改变任何 agent 的结论，它就不承重）。**这几乎就是我们的主判据的表格形态。**
- **最容易骗我们**：**"+39.1%"**。它同时踩了：仅 Qwen2.5（不可外推）、"up to"最好格、无重复无方差、自报置信度做仲裁、以及"社会属性设计敏感"（= 超参空间未搜索报告）。⇒ **我们绝不能拿"多智能体多样性能把准确率提 39%"当路线依据** —— 尤其不能把它当作"多样性 → 思维面宽"的证据。**它测的是准确率，不是思维面。**
- **最该自己补的实验**：**"固定 agent 数 / 固定轮数 / 只改属性向量的同质-异质对照"** —— 这是把"多样性收益"从"投票收益"里剥离出来的唯一办法。⇒ 建议**写进我们的 DEV 集设计**。

---

## 附：来源清单

| 来源 | URL / 路径 | 访问日期 | 取证状态 |
|---|---|---|---|
| 论文落地页（正文节选来源） | `https://www.sciencedirect.com/science/article/pii/S0952197625031574` | 2026-10-21 | ⚠️ curl **403**；经 web_search 后端**读到正文节选**（Abstract / Introduction / Effects of GFF 段 / Conclusion / CRediT / 参考文献） |
| PII 佐证 | `https://ars.els-cdn.com/content/image/1-s2.0-S0952197625031574-gr6.sml` | 2026-10-21 | 图片 CDN 路径含 PII |
| Mendeley 目录（摘要+关键词+引用） | `https://www.mendeley.com/catalogue/d0925ea0-9da2-36b4-a99d-0f1e81917e29` | 2026-10-21 | ✅ |
| ACM 文献目录（作者/卷期/Index Terms/参考文献） | `https://acm-stag.literatumonline.com/doi/10.1016/j.engappai.2025.113126` | 2026-10-21 | ✅ |
| Crossref | `https://api.crossref.org/works/10.1016/j.engappai.2025.113126` | 2026-10-21 | ✅（abstract 字段空） |
| OpenAlex | `https://api.openalex.org/works/https://doi.org/10.1016/j.engappai.2025.113126` | 2026-10-21 | ✅（abstract_inverted_index 为 null） |
| Semantic Scholar | `https://api.semanticscholar.org/graph/v1/paper/DOI:10.1016/j.engappai.2025.113126` | 2026-10-21 | ✅（abstract 空） |
| Unpaywall | `https://api.unpaywall.org/v2/10.1016/j.engappai.2025.113126` | 2026-10-21 | ⚠️ 返回空对象 / closed |
| SSRN 早期版 | `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5167458` | 2026-10-21 | ✅ 摘要（标题为 *Multi-Attribute **Mixture** Expert…*） |
| 代码仓库（声称开源） | `https://api.github.com/repos/ioio0614/MAME` | 2026-10-21 | ❌ **404**；作者其余 4 个公开仓库列表已核 |
| 候选池检索 | `https://api.crossref.org/works?query.bibliographic=...&filter=member:78,type:journal-article`（9 个检索式） | 2026-10-21 | ✅ |
| **落选对照** HiSOMA | DOI `10.1016/j.eswa.2024.124117`（ESWA 2024；SSRN 绿 OA `10.2139/ssrn.4666277`） | 2026-10-21 | 仅元数据（未精读，**建议单独排期**） |
| **落选对照** SelfCorrect-Agent | DOI `10.1016/j.neucom.2025.132546`（Neurocomputing 2026；SSRN 绿 OA `10.2139/ssrn.5679168`） | 2026-10-21 | 仅元数据 |
| **建议补读**（非 ScienceDirect） | Liang et al., *Encouraging divergent thinking in large language models through multi-agent debate*, **arXiv:2305.19118** | 2026-10-21 | 仅从 MAME 参考文献表确认存在 |
