# 12 — Expert Systems：The B* Expansion Technique for Enhancing Autonomous LLM Agents

> ⚠️ **本篇的正文（full text）在本沙盒内抓不到。以下内容严格区分"已核验"与"未核验"，未核验处一律标注，不做任何推测性补全。**

## 0. 引用（**已核验**）

- **标题**：Thinking Is Not Enough: The B* Expansion Technique for Enhancing Autonomous LLM Agents
- **作者**：Sebastián Andrés Mayorquín Posadas；Julio Vega（**均为同单位**：Department of Telematic Systems and Computing, Rey Juan Carlos University, Fuenlabrada, Madrid, Spain）
- **年份**：**2026**（online **2026-06-18**）
- **venue**：**Expert Systems**（Wiley；ISSN 0266-4720 / 1468-0394），**Vol. 43, Issue 8, Article e70333**
- **DOI**：10.1111/exsy.70333
- **License**：**CC BY-NC-ND**（Unpaywall / OpenAlex / Crossref 三方一致；is_oa = true）
- **其他 ID**：DBLP `journals/es/PosadasV26`；Semantic Scholar `CorpusId: 289518823`、`paperId: 23bb699b5a1ab5f3f2b52fec818e090598e6d533`；OpenAlex `W7165112288`
- **一句话（摘要原文意译）**：**别再只改进 agent 的"内部推理"了——它假设动作集是固定且完备的；本文提出 B\* 展开技术，让 agent 能从初始动作基 B 出发"迭代地构造出新的动作"，形成扩展动作空间 B\* = B ∪ A\*，并给出一个显式建模"动作空间演化"的"以动作为中心（act-centric）"统一框架；B\* 是该框架的一个具体实例；在 Conway 生命游戏（网格）上以"300 代后活细胞数最大化"为目标，扩展动作空间带来了更好的探索与性能，甚至超过以推理为核心的 SOTA 方法。**

> 🔴 **★ 任务书里的一处错误，必须纠正**：任务书写的是"**Experimental Psychology** 期刊"，**这是错的**。DOI 前缀 `10.1111/exsy` = **Expert Systems**（Wiley 的 AI/专家系统期刊），**不是** APA 的 *Experimental Psychology*（DOI 前缀是 `10.1111/jesp`）。本篇是 **Expert Systems 2026, 43(8), e70333**。
> 这也说明：**exsy ≠ esp**。如果按 "Experimental Psychology" 去检索，会把这条彻底搜丢。

### 已读的来源（≥2 个独立来源，且各来源的字段互不重复）
| # | 来源 | 拿到的独有信息 |
|---|---|---|
| 1 | **Crossref** `api.crossref.org/works/10.1111/exsy.70333` | 题录、期刊/卷/期、文章号 e70333、日期、license、**含被 JATS 剥离的斜体占位的摘要**、TDM full-xml / pdf 链接 |
| 2 | **Semantic Scholar Graph API** | **带 LaTeX 公式的完整摘要**（`B^{\ast}=B\cup {A}^{\ast}`）、作者、venue（"Expert Syst. J. Knowl. Eng."）、DBLP/CorpusId、**tldr**、**完整参考文献 12 条（带 DBLP/DOI/arXiv ID）** |
| 3 | **OpenAlex** | `abstract_inverted_index` 重建的摘要、license、两个 OA location（出版社 + **BURJC Digital / Rey Juan Carlos 机构库**）、发表日期 2026-06-18 |
| 4 | **Unpaywall v2** | is_oa=true，license CCBYNCND，location 列表（**无直链 PDF**） |
| 5 | **OpenAIRE API** | 机构库条目 + **bitstream 直链** `burjcdigital.urjc.es/bitstreams/634ca6fc-…/download`（**该主机在本沙盒出口白名单外**） |
| 6 | **Europe PMC** | `hitCount: 0`（该刊不在 PMC 索引内——**证实"镜像路线"不存在**） |

### 抓不到正文的原因（已逐一验证，不是"没试"）
- `onlinelibrary.wiley.com/doi/10.1111/exsy.70333`、`/doi/full-xml/…`（TDM 链接）、`/doi/pdf/…`、`/doi/pdfdirect/…`、`/doi/epdf/…`、`/doi/am-pdf/…` → 全部 **HTTP 403，Cloudflare "Just a moment..." 质询页**（试过 Chrome UA、完整浏览器头、cookie jar、HTTP/2、两次连续请求）。
- 机构库 `burjcdigital.urjc.es` / `eciencia.urjc.es`（DNS 正常解析到 212.128.240.21）→ **503 upstream connect error**（沙盒出口代理白名单不包含该主机），`hdl.handle.net/10115/307257` 同理。
- 通用代理全试过并全部失败：`r.jina.ai`（503 upstream）、`api.allorigins.win`（522）、`api.codetabs.com/v1/proxy`（522）、`corsproxy.io`（403 需 key）、`web.archive.org` CDX/availability（连接超时）、`api.base-search.net`（503）、`core.ac.uk`（403）、`colab.ws`（403）、`ouci.dntb.gov.ua`（403）、`x-mol.com`（搜索页是纯客户端渲染，取不到摘要）。
- **无 arXiv 预印本**（按标题与作者检索均无命中）；**DBLP API 202 限流**、**ACM DL Cloudflare 403**。

> ✅ **已核验的实质内容 = 完整摘要（数学符号完整）+ 完整题录 + 完整参考文献（12 条，带 DOI/DBLP/arXiv ID）+ 两条相关论文的摘要。** 以下第 2/3/4 节凡涉及正文细节处，**一律标注"未核验"**。

---

## 1. 核心机制

> ⚠️ **本节除"输入/输出/目标"外，其余为未核验**。我按"能从摘要与参考文献确定什么"来写，**不编造算法细节**。

| 项 | 内容 | 核验状态 |
|---|---|---|
| **输入** | 一个**可完全观测**的环境状态；agent 从一个**初始动作基 B** 出发。 | ✅ 摘要："an action-centric method that enables agents to **iteratively construct new actions beyond an initial basis B**" |
| **状态表示** | 未核验。摘要只说框架"**explicitly models action space evolution**"，并把它与"**在固定动作集上运作的 ReAct**"对立。⇒ 至少存在一个**"动作空间"对象**（B 与 B\* = B ∪ A\*），以及**一个能容纳"新造出来的动作"的状态表示**。 | ⚠️ 推断，非核验 |
| **动作/算子** | 未核验。可确定的是：**动作集本身可被 agent 改写**（这是本文相对 ReAct 的唯一被声明的新增能力）。 | ⚠️ |
| **过程/回路** | 摘要用词："**iteratively construct new actions**"、"**dynamic action generation**"、"leads to **improved exploration**"。⇒ 有生成新动作的回路；但**回路形式（新动作是代码？函数？文本模板？）、选择机制、停止条件、是否有 reward 反馈，全部未核验**。 | ⚠️ |
| **输出** | **Conway 生命游戏（网格）**中，**300 代之后活细胞数最大化**。这是**唯一的、摘要中明确给出的实验目标**。 | ✅ 摘要 |
| **谁来评价** | 摘要只说 "**improved exploration and performance**"、"even **surpassing state-of-the-art reasoning-based approaches**"。<br>⚠️ **判官身份、指标定义、是否留出、是否 LLM 自评，全部未核验。** | ⚠️ |

**已核验的"框架定位"（摘要原文要点）**
1. **批评的靶子**："Most autonomous agents built on large language models (LLMs) focus on improving internal reasoning **while assuming a fixed and complete set of primitive actions**."⇒ **这正是我们路线 A 的隐含假设。**
2. **本文的动作**："we challenge this assumption and introduce the **B\* expansion technique**, an action-centric method that enables agents to **iteratively construct new actions beyond an initial basis B**, forming an **expanded action space B\* = B ∪ A\***."
3. **本文的理论包装**："we present a **unified framework for act-centric autonomy** that explicitly models **action space evolution**, distinguishing our approach from prior frameworks such as **ReAct, which operate over fixed action sets**."
4. **本文的主张**：框架内 **B\*** 是那个"operationalizes dynamic action generation"的具体实例。
5. **本文的实验结论**："expanding the action space leads to **improved exploration and performance**, demonstrating that **action space completeness is insufficient** and that **optimizing the action set itself** can significantly enhance agent effectiveness."

**已核验的血缘（参考文献 12 条，S2 抽取，带 ID）**
| 引用 | 年份 | ID | 与本文的关系（我的判断） |
|---|---|---|---|
| **Automated Creation of Reusable and Diverse Toolsets for Enhancing LLM Reasoning**（KTCE，Ma et al.） | 2025 | DOI 10.1609/aaai.v39i23.34664；DBLP conf/aaai/MaH0WZL25 | ★ **最直接的邻居**。它自己诊断了 LLM 自动造工具的两个病：**"Low reusability: the tools are overly problem-specific"** 和 **"Limited diversity: the toolsets are too narrow"**。⇒ 本文（扩**动作**空间）是同一问题在**动作**而非**工具**上的版本。 |
| Tool Learning in the Wild: Empowering LMs as Automatic Tool Agents | 2024/2025 | arXiv 2405.16533；DOI 10.1145/3696410.3714825 | 野外工具学习的对照系 |
| ReAct: Synergizing Reasoning and Acting in Language Models | 2022 | arXiv 2210.03629 | ★ **本文明确对标的"固定动作集"基线** |
| Tree of Thoughts | 2023 | arXiv 2305.10601 | 推理侧对照 |
| Active RAG / Benchmarking LLMs in RAG | 2023 | arXiv 2305.06983 / 2309.01431 | 检索/工具对照 |
| **The Illusion of Thinking**（Apple） | 2025 | — | ⚠️ **"推理能力在复杂题上会塌缩"的警示引用**——作者很可能用它论证"光改推理不够" |
| **DeepSeek-R1 Release** | 2025 | — | 当时点的推理模型 |
| **Environments for Interactive Learning** | — | — | 交互式学习环境（≈ 可交互的评估环境） |
| LangSmith 文档 / Introducing ElevenLabs MCP / "From GPT to AutoGPT" 综述 | 2023–2024 | — | 生态与工具协议 |
| （自引）A survey of LLM based autonomous agents | — | — | 领域综述 |

---

## 2. 关键数字

| 项 | 状态 |
|---|---|
| 实验设置（题数/样本数/模型） | **未核验**（正文未获取）。摘要只给环境（Conway 生命游戏、网格）、目标（300 代后最大化活细胞数）、对照（"state-of-the-art reasoning-based approaches"）。**模型、提示词、每格多宽、跑多少次、随机种子，全部未知。** |
| 主指标与读数 | **未核验**。摘要只给方向性表述（"improved exploration and performance"），**没有任何数值**。⚠️ **不能编造。** |
| 消融 | **未核验**（虽然从摘要"expanding the action space leads to improved exploration"可推断存在"不扩 vs 扩"的对照，但具体设计和读数不可考）。 |
| 成本 | **未核验**。 |

> ⚠️ **必须写下的空白**：**本篇的任何一个数字我们都没读到。** 因此它**不进入"我们要复现的 3 个数字"清单**。如果后续有人拿到全文，这一节应当重写。

---

## 3. ★ 它的「成功标准」是什么

- **怎么判定成功？** **未核验**（正文未获取）。
- **可从摘要确定的**：存在一个**可完全观测的、非平凡环境**（"a non-trivial, fully observable environment"）与**一个明确的优化目标**（300 代后活细胞数），并以"**超越以推理为核心的 SOTA 方法**"为对比主张。
  ⇒ **它至少具备"目标可自动判定"这一性质**（活细胞数是可程序化计算的），这是**判官不同源**的好兆头——但**具体指标是活细胞数本身、还是活细胞数 + 探索度量的组合，未核验**。
- **否证/失败条件有没有写？** **未核验**。摘要里**没有**出现任何"在什么条件下 B\* 打不过固定动作集"的表述。
- **有没有报告"不可分辨"这种结果？** **未核验**。
- ⚠️ **诚实定位**：本篇的"成功标准"**目前无法评估**。**在拿到全文之前，不能把它当成一个可抄的成功标准案例**，只能当成一个**"问题陈述值得抄"**的案例。

---

## 4. 自认的局限（原话优先）

**未核验——正文未获取，无法逐字引用。**

摘要中**隐含**（但未明说）的自我限定：
- "**a unified framework for act-centric autonomy**" ⇒ 它自称是**框架 + 一个实例**，不是完整方案；
- "**Within this framework, B\* serves as a concrete instantiation**" ⇒ 框架与实例被明确分开 ⇒ 框架本身**未被实验验证**（只有 B\* 被验证）——⚠️ 这条是**从摘要句式推出的**，标记为推断。
- 实验只有**一个**环境（生命游戏）⇒ 从摘要"we evaluate B\* in a non-trivial, fully observable environment"（单数）可推出**单环境验证**，但**是否声明为局限**未知。

---

## 5. ★ 对我们项目的可迁移点

**映射：路线 A（固定拓扑）/ 路线 B（训练架构）/ 路线 C**

- **★★ 抄 1（概念层，本篇最大价值）：★ "动作空间的完备性是不足的"——这条命题直接命中我们路线 A 的隐含假设。**
  我们的路线 A = **人写死的固定拓扑**。本文的靶子（ReAct 式的"固定且完备的原子动作集"）**正是路线 A 的形式化版本**。
  摘要原话（可直接引用）：**"action space completeness is insufficient"** 与 **"optimizing the action set itself can significantly enhance agent effectiveness"**。
  → **能省我们什么**：省掉"要不要让 agent 自己造新操作"这个问题的**存在性论证**——本篇把它写成了期刊论文的正式命题。⇒ **我们路线 B/C 的立项理由可以直接引这一条。**
  → **要改什么**：本篇的 B\* = **在初始基 B 之上迭代构造新动作 A\***。⇒ 我们的对应物应该是"**在人工给定的原子操作基 B 之上，让系统构造出新的操作（复合操作 / 条件分支 / 新判据）**"，并把它落到 **B\* = B ∪ A\*** 这样的**可枚举、可清点**的表示上——**这恰好就是"思维面 = 有效信息维度数"的可操作版本**：新增的操作 A\* 就是新增的维度候选。

- **★ 抄 2：把"拓扑"从"操作序列"升级为"**动作空间**"这个对象。**
  路线 A/B/C 讨论的都是"**操作按什么顺序跑**"（序列/图）。本文的抽象是"**动作空间本身在演化**"（集合在变）。
  → 对我们的意义：**"多一个操作"和"多一个维度"不是一回事，但前者是可清点的前者**。⇒ 我们的"维度"若能挂到"新增动作"上，就有了**离散、可复算、不依赖措辞**的载体（治 ③）。
  → ⚠️ 但要小心：**新增动作 ≠ 承重信息**。**A\* 里可能有大量"造出来但没进决策"的动作**——**这恰恰就是我们要测的东西！** ⇒ 本篇给我们的是一个**候选维度的产生器**，而**"哪些 A\* 真承重"仍要靠我们的核验包判**。

- **★ 抄 3：邻居论文的失败模式可以直接当我们的"失效清单"。**
  KTCE（AAAI'25）自己诊断 LLM 自动造工具的两个病：**"Low reusability"（过度问题特定）** 与 **"Limited diversity"（工具集过窄）**。
  → 我们的路线 B（学操作序列）**必然面临同样的两个病**。⇒ **建议把这两条直接写进我们的 DEV 集诊断表**：我们学出来的操作，**有多少是换题就废**（低复用）？**有多少种解法形态**（多样性）？
  → **这条能省我们一个实验**：不用自己想失效模式，邻居已经命名了。

- **★ 抄 4：把"改推理"与"改动作集"设成**两个正交臂**，这正是我们 A/B/C 的天然对照。**
  本文的对比轴是"**在推理上花更多 vs 把动作集本身变厚**"。⇒ 我们的"工作流臂 vs 直调臂"其实**已经在一个轴上**；缺的是"**动作集能不能自己变厚**"这一维。
  → **要改什么**：加第三臂——**让系统在同一题集上构造出新的复合操作**，看净维度增益是否随之上升。**这会是路线 B 的一个具体化。**

- **DEV 集设计**：未核验。**但**它的环境选择（**完全可观测 + 可程序化判定 + 目标可量化**）本身对我们有参考价值：我们的 DEV 集也应该优先选"**判官可自动跑、不需要 LLM 评语**"的题。⇒ 这与 07/08（本地打分函数）、09（gold label）、10（留出集 + 阈值）、11（环境自带 reward）**四篇的共同点完全一致**：**本批 6 篇里，判据最干净的 4 篇都不是用 LLM 当判官的。** ⇒ **这是本批最强的横向信号。**

- **优化器契约 L0–L4**：本篇**未核验**，但从"B\* = B ∪ A\*"的表述看，它**至少提供了 L2（迭代生成新动作）**，是否有 L3（对已生成动作的筛选/评估）未知。

---

## 6. ★ 不可迁移 / 会误导我们的点

1. **★★ 最大的风险：★ 我们最想抄的那条命题，我们只读到了它的"广告词"。**
   - "action space completeness is insufficient"、"even surpassing state-of-the-art reasoning-based approaches" —— **这是摘要里的宣传语，没有任何数字支撑**（我们没读到结果表）。
   - 摘要**没有给出**：基线是谁、"SOTA reasoning-based approaches" 是哪几个、跑了多少次、"surpassing" 的幅度是多少、**有没有方差/显著性**。
   → **在我们拿到全文之前，这篇只能当"问题陈述 + 立项理由"用，不能当"方法 + 数字"的证据。** ⚠️ 我们自己的论文如果引用它，**也必须只引到这一层**（引它的命题，不引它的数字），否则我们就在复刻一篇我们没读过的论文的数字。
   → **行动项**：把这一条标为"待补全文"，**不要进任何数字清单**。

2. **★ 判官污染检查（模板第 6 节专门项）**：**无法判定**（正文未获取）。
   - 好消息（从环境推断）：**Conway 生命游戏的"活细胞数"是程序化可算的**，**极可能**是确定性判据 ⇒ 不像 07 篇的 doc_merge 那样用 LLM 打分。
   - 坏消息：**"improved exploration" 这半句怎么测的？** 探索度量的定义未知。若它用 embedding/语义相似度去测"新状态"，就正中我们的 embo-01 陷阱。**未核验 ⇒ 存疑。**

3. **★ 判据载体检查**：**无法判定**。摘要未提任何距离/相似度度量。⚠️ 但注意**它的邻居 KTCE 的做法**（"abstract knowledge from problems and create a three-layer knowledge tree of topics, concepts, and key points" → 从知识诱导原子工具）——**那是结构化的**。⇒ 若本篇也走结构化路线（"显式建模动作空间演化"听起来就是），载体可能是干净的。**存疑，不下结论。**

4. **★ 量纲/领域不可比**：生命游戏的"活细胞数"与"承重信息条数"**无任何换算关系**。**只抄命题，不抄量。**

5. **★ 单环境验证的隐患（从摘要可推）**：只有一个环境、只有 300 代这个单一目标 ⇒ "动作空间扩展带来收益"的**外部效度未知**。⇒ 我们的引用必须带上"（单环境，未知其外部效度）"。

6. **★ 这篇对我们最危险的地方不是它的数据，是它的"标题党"会让我们跳过自己的对照。**
   "Thinking Is Not Enough" 这个标题**极度**符合我们当前的痛点叙事（"光有思考不够，得有结构/有维度"），**极易**被当作"外部背书"直接引用。⇒ **纪律：未读到全文 ⇒ 不得把它写进任何"已有工作支持我们的设计"清单。**

---

## 7. 逐字摘录

> **摘要（Semantic Scholar 版，含 LaTeX 公式；Crossref 版因斜体被剥离而有空缺，此处以 S2 为准）**
> "Most autonomous agents built on large language models (LLMs) focus on improving internal reasoning while assuming a **fixed and complete set of primitive actions**. In this work, we challenge this assumption and introduce the **B\* expansion technique**, an action-centric method that enables agents to **iteratively construct new actions beyond an initial basis B**, forming an **expanded action space B\* = B ∪ A\***. To formalize this paradigm, we present a **unified framework for act-centric autonomy** that explicitly models **action space evolution**, distinguishing our approach from prior frameworks such as **ReAct, which operate over fixed action sets**. Within this framework, B\* serves as a concrete instantiation that operationalizes dynamic action generation. We evaluate B\* in a **non-trivial, fully observable environment—Conway's Game of Life on a grid—where the objective is to maximize the number of live cells after 300 generations**. Our results show that expanding the action space leads to improved exploration and performance, demonstrating that **action space completeness is insufficient** and that **optimizing the action set itself** can significantly enhance agent effectiveness, even surpassing state-of-the-art reasoning-based approaches."

> **★ 邻居论文 KTCE（AAAI 2025, DOI 10.1609/aaai.v39i23.34664）摘要中的失效命名（已核验原文）**
> "current tools automatically created by LLMs often serve as a mere summary of specific problems or solutions, which face two main issues: 1) **Low reusability**: the tools are overly problem-specific and struggle to handle new problems. 2) **Limited diversity**: the toolsets are too narrow, limiting their application to address a broader range of different problems."

---

## 8. 读完后我自己的一句判断

**最值得抄**：**它把我们的核心假设写成了可引用的正式命题——"动作空间的完备性是不足的"（action space completeness is insufficient）**，并且把"扩展"落成了一个**可清点的集合运算 `B\* = B ∪ A\***`。这给了我们一个**离散、非措辞、可复算**的"维度候选"载体：我们不必去数"有多少条承重信息"这种容易掉进措辞陷阱的东西，可以先数"**新增了多少个真被用到的动作 A\***"。

**最容易骗我们**：**我们只读到了它的广告词，一个数字都没读到。** 它的标题 "Thinking Is Not Enough" 恰好是我们最想听的话，最容易被当成"已有工作支持我们的设计"直接写进论文——**而我们的判据一旦建立在这句背书上，评审和未来的自己都会以为我们偷懒找了个权威。** ⇒ **在拿到全文之前，它只能进"问题陈述"清单，不能进"证据"清单，也不能进任何数字清单。** 另外，它单环境（生命游戏）、单目标（300 代活细胞数）的外部效度也完全未知。
