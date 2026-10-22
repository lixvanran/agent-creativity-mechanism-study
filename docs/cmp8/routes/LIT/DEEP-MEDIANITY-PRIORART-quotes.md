# DEEP-MEDIANITY · 先验工作逐字摘录

> 配套：`/workspace/lab/routes/LIT/DEEP-MEDIANITY-PRIORART.md`
> 摘录日期：**2026-10-22**
> 抓取人：General（root session 455189915857002）

---

## 0. 来源代号与本地副本（**所有引文均可 `grep` 复核**）

本地副本目录：`/workspace/lab/routes/LIT/_priorart_src/`
— `.html` = arXiv LaTeXML 原文（未改动）；`.txt` = 去标签后的纯文本（仅归一空白）。

| 代号 | 论文 | arXiv id | 本地副本 | 抓取路径 |
|---|---|---|---|---|
| **[KUG23]** | Kuhn, Gal & Farquhar — *Semantic Uncertainty: Linguistic Invariances for Uncertainty Estimation in Natural Language Generation*（ICLR 2023 Spotlight） | `2302.09664v3` | `se.txt`（75,997 字符） | `https://arxiv.org/html/2302.09664v3` |
| **[SC23]** | Wang, Wei, Schuurmans, Le, Chi, Narang, Chowdhery & Zhou — *Self-Consistency Improves Chain of Thought Reasoning in Language Models*（ICLR 2023） | `2203.11171v4` | `abs_2203.11171.txt` | `https://arxiv.org/abs/2203.11171` |
| **[LAK25]** | Lake, Choi & Durrett — *From Distributional to Overton Pluralism: Investigating Large Language Model Alignment*（NAACL 2025 Main） | `2406.17692v2` | `H_2406.17692.txt` | `https://arxiv.org/html/2406.17692v2` |
| **[HIV25]** | Jiang, Chai, Li, Liu, Fok, Dziri & Tsvetkov — *Artificial Hivemind: The Open-Ended Homogeneity of Language Models (and Beyond)*（NeurIPS 2025 D&B Oral） | `2510.22954v2` | `H_2510.22954.txt` | `https://arxiv.org/html/2510.22954v1` |
| **[POO26]** | Poole-Dayan, Wu, Sorensen, Pei & Bakker — *Benchmarking Overton Pluralism in LLMs*（ICLR 2026 accepted） | `2512.01351v2` | `H_2512.01351.txt` | `https://arxiv.org/html/2512.01351v1` |
| **[TAN26]** | Tan, Choy, Alsagoff, Wangsajaya, Banerjee, Saikia & Chan — *Automated Creativity Evaluation of Language Models Across Open-Ended Tasks*（ACL 2026 Main） | `2606.11762v1` | `H_2606.11762.txt` | `https://arxiv.org/html/2606.11762v1` |
| **[GIA25]** | Giannone, Xu, Nayak, Awhad, Sudalairaj, Xu & Srivastava — *Mitigating Premature Exploitation in Particle-based Monte Carlo for Inference-Time Scaling*（preprint） | `2510.05825v2` | `H_2510.05825.txt` | `https://arxiv.org/html/2510.05825v1` |
| **[JAI25]** | Jain, Lanchantin, Nickel, Ullrich, Wilson & Watson-Daniels — *LLM Output Homogenization is Task Dependent*（v3 改题 *Task-Dependent Evaluation of LLM Output Homogenization: A Taxonomy-Guided Framework*） | `2509.21267v1` | `H_2509.21267.txt` | `https://arxiv.org/html/2509.21267v1` |
| **[VIJ18]** | Vijayakumar, Cogswell, Selvaraju, Sun, Lee, Crandall & Batra — *Diverse Beam Search*（AAAI 2018） | `1610.02424v2` | `h_1610.02424.txt` | `https://arxiv.org/html/1610.02424v1` |
| **[LI23]** | Li, Lan, Fu, Cai, Liu, Collier & Watanabe — *Repetition In Repetition Out*（NeurIPS 2023） | `2310.10226v1` | `H_2310.10226.txt` | `https://arxiv.org/html/2310.10226v1` |
| **[MAJ24]** | Majumder, Surana, Agarwal, Dalvi Mishra, Meena, Prakhar, Vora & Khot — *DiscoveryBench: Towards Data-Driven Discovery with Large Language Models* | `2407.01725v1` | `h_2407.01725.txt` | `https://arxiv.org/html/2407.01725v1` |
| **[CHE23]** | Chen, Aksitov, Alon, Ren, Xiao & Yin — *Universal Self-Consistency for Large Language Model Generation* | `2311.17311v1` | `h_2311.17311.txt` | `https://arxiv.org/html/2311.17311v1` |
| **[SKO26]** | Skobelev, Fithian & Han — *Fine-Tuning Fixes Mode Collapse and Over-Dispersion in LLMs*（预印本） | `2609.16454v1` | ⚠️ **未落盘**（本次经 `web_search` 后端读到 `arxiv.org/html/2609.16454v1` 的 `content` 字段；引文见 §7，标注为"经检索后端取得"） | `web_search` → `arxiv.org/html/2609.16454v1` |
| **[MIN26]** | Min, Vaccarino, Chen, Wu, Yona & Cheng — *Stop When Reasoning Converges*（under review） | `2605.17672v1` | ⚠️ **未落盘**（同 [SKO26]） | `web_search` → `arxiv.org/html/2605.17672v1` |

> **空白归一说明**：LaTeXML / `pdftotext` 会在标点前后加空格、把换行渲染成 ` \`。下面引文**保留原词、原拼写、原数学记号**，
> 只归一**纯排版空白**。**每条引文都用 `norm(q) in norm(file)` 程序核对过**（34/34 通过；2 条初稿因 LaTeXML 零宽字符差异被程序判 MISS，已改用可逐字命中的片段，见 [GIA25] 与 [MAJ24]）。

---

## Q1 — 语义熵：聚类用什么、要不要外部模型（★ 关键）

**[KUG23 §方法, Step 2]**
> In general, any natural language inference classification system (NLI) can be used for our bidirectional entailment clustering algorithm. In our case, we use a Deberta-large model ( He et al., 2020a ) that is fine-tuned on the NLI data set MNLI ( Williams et al., 2017 ).

📌 **可抄点**：语义熵的聚类器 = **NLI 判别模型**（DeBERTa-large / MNLI），**不是句向量几何**。
⇒ 依赖类型是"**外部判别模型**"，不是"**embedding**"。二者不可混为一谈。
⚠️ **MNLI 是英文** ⇒ 中文场景不能直接套；**但我们不需要它**——我们的 `family_key`（决策指纹聚类）就是那个等价类。

**[KUG23 附录 B.2]**
> Because this component is novel, we confirm in Section B.2 that the bidirectional entailment classifier works by manually labelling 300 generations for semantic equivalence, finding an accuracy of 92.7% on TriviaQA and 95.5% on CoQA.

📌 **分母**：人工标注 **300** 条生成。**分数据集**：TriviaQA **92.7%** / CoQA **95.5%**。
⇒ 聚类器本身**会错 ~5–8%** ⇒ 报任何基于聚类的数时都要交代这一点。

**[KUG23 §6.2]**
> First, as we show in Section 6.2 , M < 20 is often sufficient for good uncertainty.

📌 **采样量口径**：`M < 20` 通常够 ⇒ 我们的"一题采几条"可照此量级定（**别超过 20，成本线性上升**）。

---

## Q2 — 语义熵的读数（**带绝对分母**）与"最朴素的那个数"

**[KUG23 Table 2]**（表题逐字：`Table 2: Incorrectly answered questions have more semantically distinct answers than correct ones.`）
> | Dataset | Average # of semantically distinct answers | AUROC | Correctly answered | Incorrectly answered | Semantic entropy | # distinct answers |
> | CoQA | 1.27 | 1.77 | 0.77 | 0.66 |
> | TriviaQA | 1.89 | 3.89 | 0.83 | 0.79 |

（表格在 LaTeXML 中被拆成列标题行与两条数据行；**逐字原文**为：
`Dataset Average # of semantically distinct answers AUROC Correctly answered Incorrectly answered Semantic entropy # distinct answers CoQA 1.27 1.77 0.77 0.66 TriviaQA 1.89 3.89 0.83 0.79`）

**[KUG23 §实验, Table 2 紧邻正文]**
> On its own, this count is a reasonable uncertainty measure, though semantic entropy is better.

📌 **可抄点**：**"平均不同答案数"（# distinct answers）本身就是一个合法测度** ⇒ 我们**不必**只报熵，可以同时报这个更朴素的数。
📌 **分母**：CoQA / TriviaQA 两个数据集的**全体平均**（论文未在表内给样本数；**表内每个数字都带数据集名 + 指标名**，不写"总体"）。

---

## Q3 — Self-Sim：我们"中庸距离"的已发表等价物（★ 最该抄）

**[LAK25 §2.3]**
> Given a set of sampled responses to a prompt, we measure the per-input similarity of responses by averaging Jaccard similarity over all pairs after converting each response into a set of unique word stems. We refer to this as Self-Sim and display the average over for N = 5 samples for each input.

📌 **逐字口径**（可直接实现）：
- 输入 = 一个 prompt 的 **N = 5** 条采样响应
- 每条响应 → **唯一词干集合**
- **所有响应两两**算 **Jaccard 相似度**
- 取平均 = **Self-Sim**
⚠️ **中文口径必须自己定**：英文"词干"要换成"分词后词干 / 字元"，**不能直接照抄英文 stemmer**。

**[LAK25 §2.3 表头与 Table 2]**（`Self-Sim` 与 `Length` 两列）
> | | Quality (measured by GPT-4) | Output | | | | | |
> | Model | Prompt | Helpfulness | Clarity | Factuality | Depth | Engagement | **Self-Sim** | **Length** |
> | ConflictingQA | Llama 2 | - | 2.21 | 3.29 | 2.30 | 1.49 | 1.78 | **0.17** | **37** |
> | ConflictingQA | Llama 2 | URIAL | 4.00 | 4.72 | 3.64 | 3.18 | 3.79 | **0.23** | **203** |
> | ConflictingQA | Llama 2 Chat | - | 4.78 | 4.94 | 4.26 | 4.48 | 3.88 | **0.36** | **412** |
> | ConflictingQA | GPT-3.5 Turbo | - | 4.37 | 4.95 | 4.65 | 3.08 | 3.10 | **0.45** | **98** |
> | LIMA-OE | Llama 2 | - | 3.08 | 3.80 | 3.43 | 2.36 | 2.54 | **0.11** | **149** |
> | LIMA-OE | Llama 2 | URIAL | 4.34 | 4.88 | 4.56 | 3.46 | 3.86 | **0.24** | **261** |
> | LIMA-OE | Llama 2 Chat | - | 4.94 | 5.00 | 4.62 | 4.72 | 4.30 | **0.34** | **552** |
> | LIMA-OE | GPT-3.5 Turbo | - | 4.90 | 5.00 | 4.92 | 4.48 | 4.14 | **0.36** | **355** |

📌 **分母**：每个格 = **1 个模型 × 1 个提示方案 × 1 个数据集**，Self-Sim = **N=5** 采样的两两平均。
📌 **表注逐字**："All Llama 2 models are 7B variants."
📌 **区间**：**0.11（Llama 2 base，LIMA-OE）～ 0.45（GPT-3.5 Turbo，ConflictingQA）** ⇒ 我们的读数应当落在这个量级附近才有可比性。

**[LAK25 §2.3 末]**
> Their notion of distributional pluralism , or the ability of LLM to surface diverse information across samples, can be reflected by the lexical diversity metric we introduced ( Self-Sim ). On the other hand, Overton pluralism , which requires surfacing diverse information within a single response, is not captured this way, but may be captured by length, as capturing diverse information can lead to longer answers.

📌 **★ 定位**："**分布性多元主义**（跨采样的多样信息）"= Self-Sim 代理；"**Overton 多元主义**（单条回复内）"= **这个指标抓不到**。
⇒ **我们的"中庸"跨了两个轴**（批内互相像不像 / 单分布的众数集中度）⇒ 只抄 Self-Sim 覆盖**前一个轴**。

---

## Q4 — "中庸"在文献里的名字与病灶：OvertonScore

**[POO26 摘要]**
> We introduce a novel framework for measuring Overton pluralism in LLMs—the extent to which diverse viewpoints are represented in model outputs. We (i) formalize Overton pluralism as a set coverage metric ( OvertonScore ), (ii) conduct a large-scale U.S.-representative human study (N = 1209; 60 questions; 8 LLMs), and (iii) develop an automated benchmark that closely reproduces human judgments. On average, models achieve OvertonScore s of 0.35–0.41, with DeepSeek V3 performing best; yet all models remain far below the theoretical maximum of 1.0, revealing substantial headroom for improvement. Because repeated large-scale human studies are costly and slow, scalable evaluation tools are essential for model development. Hence, we propose an automated benchmark that achieves high rank correlation with human judgments ( ρ = 0.88 ), providing a practical proxy without replacing human assessment.

📌 **绝对分母**：**N = 1209** 名美国代表性参与者 × **60** 题 × **8** 个前沿 LLM；平均 OvertonScore **0.35–0.41**（理论上限 **1.0**）；自动判官与人类的**秩相关 ρ = 0.88**。

**[POO26 §2, 公式逐字]**
> which model response is Overton-pluralistic, we can calculate the proportion of the Overton window it covers. Concretely, for a subjective question x , if a majority of humans who hold some viewpoint y ∈ W ( x ) feel that a model response ℳ ( x ) represents their view, then we consider y to be covered , denoted by y ∈ ℳ ( x ) . Therefore, we define Overton coverage of a model response for a query as:
> Coverage ( ℳ , x ) = (1/| W ( x ) |) ∑_{y ∈ W(x)} 1{ y ∈ ℳ ( x ) }
> The OvertonScore for a model ℳ over a set of queries X = { x 1 , … , x n } is the average Coverage : OvertonScore ( ℳ , X ) = (1/n) ∑_{i=1}^n Coverage ( ℳ , x i )

📌 **★ 形式先例**：`覆盖率 = 被覆盖的参照集元素 / 参照集大小`，再对题取平均。
⇒ **我们"覆盖饱和度"的形式先例在此**；**差别在分母**：`W(x)` = 人类观点集，vs 我们的 `C_t` = **预注册的结论空间**。
📌 **判定门槛**：某个观点被"覆盖"= 该观点簇内**多数人**给模型回复打 **≥4**（1–5 分量表）。

**[POO26 §4.1]**
> Across models, the average adjusted OvertonScore is 0.39, well below the theoretical maximum of 1.0. Still, we find that DeepSeek V3/R1, Llama 3.3, and GPT-4.1 achieve the highest scores, while Gemma 3-27B performs significantly below average ( p = 0.015

📌 **adjusted 版**（按题固定效应标准化）的平均 = **0.39**；显著性检验分母 = **8 个模型**。

---

## Q5 — "众数吸引"的严格定义：碰撞概率 / N₂ / 碰撞比 R

**[SKO26 摘要]**
> We quantify LLM output diversity by collision probability—the probability that two responses sampled independently conditional on the same fixed prompt coincide—or, more generally, by their expected similarity under a kernel.

**[SKO26 §1]**
> Their collision gap is the model's collision probability minus the target's; where zero indicates calibrated diversity, a positive gap indicates mode collapse, and a negative gap indicates over-dispersion.

**[SKO26 §3]**
> The inverse Simpson index is the number of equally likely choices that would give the same collision probability.

**[SKO26 §4.2]**
> We find that three of the four base models are 1.6 to 2.9 times under-dispersed relative to the human populations

**[SKO26 §4.3]**
> On this same dataset, some base models are under-diverse and others over-diverse (R=0.74–1.64): mode collapse depends on the model.

📌 **可复算的核心式**（原文 LaTeXML 渲染）：
`C(π) = Σ_a π(a)²`；`N₂(π) = 1/C(π)`；`R := C(q)/C(p) = N₂(p)/N₂(q)`（**R=1 标定；R>1 塌缩；R<1 过度离散**）
核推广：`C_{p,k}(x) = E_{Y,Y'~p(·|x)}[k(Y,Y')]`，精确碰撞核 `k(y,y') = 1{y = y'}`。
📌 **分母**：**3 / 4** 个基座模型 vs 人类调查人群（GSS / ANES / WVS）离散不足 **1.6–2.9 倍**；CodeNet 上 `R = 0.74–1.64`（**4 个模型**里有的塌、有的过散）。
📌 **温度可达区间（引理 1）**：`N₂_T(x) ∈ (g*(x), S(x))`，`g*` = 众数个数、`S` = 支撑集大小；`T→0 ⇒ g*`，`T→∞ ⇒ S`。
⇒ ★ **这就是"落在分布中心"的严格说法**：低温时分布**只能**取那 `g*` 个众数。
⚠️ **R 的分母是"目标分布"（人类）** ⇒ 我们**没有人类目标分布**，只能用**批内自参照**，且必须声明"**只能读同批内相对中庸，不能读相对人类**"。
⚠️ **预印本，无同行评审**。

---

## Q6 — 过早闭合：ESS

**[GIA25 附录 A.3]**（LaTeXML 原文的 LaTeX 源码串为 `ESS(t)=\dfrac{1}{\sum^{N}_{i=1}(w_{t}^{i})^{2}}`，下方为纯文本渲染）
> ESS(t) = 1 / ∑_{i=1}^{N} (w_t^i)²
> This formulation is intuitive:
> • Maximum ESS: If all weights are uniform ( w_t^i = 1/N ), then ESS = 1/∑(1/N)² = 1/(N/N²) = N . The effective size is the total number of particles.
> • Minimum ESS: In the most degenerate case, one weight is 1 and all others are 0. Then ESS = 1/(1²) = 1 . The effective size has collapsed to a single particle.

**[GIA25 §3.1]**
> Crucially, low variance in the resampling distribution at step t corresponds to high diversity among the particles selected for propagation to step t+1 .

📌 **逐字口径**：`ESS(t) = 1/Σ_i (w_t^i)²`；**最大 = N**（权重均匀），**最小 = 1**（塌成单粒子）。
📌 **★ 关键发现**：**ESS 在数学上就是 N₂**（与 §Q5 的逆 Simpson 指数同一个式子）⇒ **"中庸"与"过早闭合"可以用同一个数**。
📌 **我们的用法**：权重 `w_t` = **第 t 轮新发现的承重族数**（不是布尔）⇒ `ESS(t)` 逐轮可算、可跨臂比较。
⚠️ 若只有"是/否新发现"的二值记录，ESS 会退化为"有效路径数"，分辨率低 ⇒ **需先改记录方式**。

**[GIA25 §3.1 另一段]**
> High variance indicates that the weight distribution is concentrated on only a few particles, leading to a low E S S ( t ) , a low-entropy state, and ultimately a poor approximation of the posterior

📌 **同义改写**（LaTeXML 在 `ESS` 内插了零宽字符，故此处引文含 `E  S  S  ( t )`；**公式本体在附录 A.3 那条里是干净的**）。

---

## Q7 — 离散 n-gram 覆盖率（"覆盖饱和度"的 n-gram 版）

**[VIJ18 §5.1]**
> Diversity Statistics : We count the number of distinct n-grams present in the list of generated outputs. Similar to Li et al. 2015) , we divide these counts by the total number of words generated to bias against long sentences.

**[VIJ18 §3]**
> Hamming Diversity. This form penalizes the selection of tokens used in previous groups proportional to the number of times it was selected before.
> Cumulative Diversity. Once two sequences have diverged sufficiently, it seems unnecessary and perhaps harmful to restrict that they cannot use the same words at t

📌 **逐字口径**：`distinct n-gram 数 ÷ 生成总词数`（**除以总词数**是为了抑制长句偏置）⇒ 这是"覆盖率"口径的**已发表出处**。
📌 **Hamming / Cumulative** 是**搜索内**多样性的标准罚函数形式。

---

## Q8 — 重复率 rep-2（辅助轴）

**[LI23 §实验]**
> Fig. 2 demonstrates a strong correlation between the rep-2 scores of human and generated text on each dataset, indicating that the degeneration issue becomes more severe as the percentage of repetitions in training data increases.

**[LI23 §实验]**
> neural LM will amplify the repetition in data by more than 10 times , similar to the bias amplification found in Zhao et al. [39] .

📌 **分母**：四个 Pile 子集各随机抽 **2,000** 句作验证/测试集（训练/验证/测试互不重叠）。
📌 ⚠️ **rep-2 的定义式本次未逐字取到**（只取到表列名 `Rep-2` 与"重复百分比"的口径）⇒ 引用时**不写公式**。
📌 ⚠️ **重复 ≠ 趋同**：rep-2 测**退化/循环**，不测"落在分布中心"⇒ 只能作辅助列。

---

## Q9 — "同质化"的概念锚（embedding 路线，必须排除但值得引）

**[HIV25 §3]**
> We then obtain sentence embeddings for all responses using OpenAI's text-embedding-3-small model. To measure response consistency, we compute two types of semantic similarity scores:
> • Within-prompt similarity : Average pairwise similarity among the 20 responses generated from the same original prompt
> • Cross-paraphrase similarity : Average similarity between responses from the original prompt and responses from its paraphrases

**[HIV25 §3]**
> Our results across all 42 models show that the within-prompt similarity averaged 0.821, while the cross-paraphrase similarity averaged 0.781.

**[HIV25 §2]**
> Under the sampling parameters (top-p = 0.9 , temperature = 1.0 ), the average pairwise similarity among responses to the same prompt typically exceeds 0.8. As a baseline, randomly paired responses from the global pool 100% fall within the 0.1–0.2 range.

**[HIV25 §1 Fig.1 说明]**
> Each of the 25 models generates 50 responses using top-p sampling ( p = 0.9 ) and temperature = 1.0 . Despite the diversity of model families and sizes, the responses form just two primary clusters

📌 **绝对分母**：**42** 个模型 × **20** 响应/模型（§3 的同 prompt 相似度）；**25** 个模型 × **50** 响应/模型（Fig.1 的 PCA 聚类）。
📌 **读数**：同 prompt 两两相似度均值 **0.821**；跨改写 **0.781**；**全局随机配对 100%** 落在 **0.1–0.2**。
⚠️ **必须排除**：`text-embedding-3-small` ⇒ embedding 几何，违反本项目纪律。
📌 **可用之处**：① 借"**within-prompt similarity**"这个**命名**；② 它的读数可作"我们的中庸度换算过去会落在哪个区间"的**粗参照**。

---

## Q10 — "语义熵 = 无参照的新颖度/多样性"已有 2026 ACL 先例

**[TAN26 摘要]**
> Divergent creativity is measured using semantic entropy, a reference-free and robust metric for novelty and diversity, validated against human annotations, LLM-based novelty judgments and baseline diversity measures. Convergent creativity is assessed via a novel retrieval-based multi-agent judge framework that delivers context-sensitive evaluation of task fulfilment with over 60% improved efficiency.

**[TAN26 附录 C.3.3]**
> We use tasksource/deberta-base-long-nli as our DeBERTa model to cluster samples into semantic classes. We selected it for our framework because it achieved the highest accuracy on the MacGyver dataset, which we considered essential to ensure the reliability and consistency of downstream analyses for our specific domain case. At the same time, the framework remains agnostic to the choice of entailment model: researchers are free to substitute stronger or more efficient encoders as they become available.

**[TAN26 附录 C.3.3]**
> The details for the greedy entailment algorithm, retrieved from Farquhar et al. (2024) , are as follows:

📌 **★ 意义**：**我们"用语义熵测多样性/新颖度"这件事，在 2026 年 ACL 已有直接先例** ⇒ 引用它可挡掉"你为什么用这个奇怪指标"。
📌 **依赖仍是 NLI**（`deberta-base-long-nli`），**不是 embedding** ⇒ 与我们的替代路线一致。
📌 **"agnostic to the choice of entailment model"** ⇒ 论文明确允许换聚类器 ⇒ **我们换成 `family_key` 是合规的、可写进论文的**。
📌 **口径分层**：论文区分 **step-level** 与 **solution-level** 语义熵 ⇒ 我们的"逐轮边际"与"整题中庸"正好对应这两层。
📌 **分母**：三个域（MacGyver / HypoGen / BookMIA）；附录 C.2 的 entailment 人工标注 **Cohen's κ** 矩阵，判定计数 **Positive 26 / Negative 29**。

---

## Q11 — 任务无关的多样性指标会误判（我们的 4-gram 口径要自陈的风险）

**[JAI25 §实验]**
> We validate the LLM-judges on a stratified random sample of 225 response pairs across models, tasks, and sampling strategies. Two authors independently labeled these responses for functional diversity, and agreed 79% with the LLM-judges (80% agreement between annotators). This is comparable to Zhang et al. (2025b) 's evaluation of functional diversity in creative tasks, where a fine-tuned judge also achieved 79% agreement with human labels.

📌 **绝对分母**：**225** 对响应；判官与人类一致 **79%**；两位标注者之间一致 **80%**。
📌 **★ 警示**：任务无关的指标（embedding 距离、词面重叠）分不清"**实质变化**"vs"**改写**"⇒ **我们的 4-gram 组件就是"词面重叠"** ⇒ 必须自陈这个风险，并**把语义那一层交给 `family_key`**。

---

## Q12 — 众数答案：Self-Consistency 的原语

**[SC23 摘要]**
> It first samples a diverse set of reasoning paths instead of only taking the greedy one, and then selects the most consistent answer by marginalizing out the sampled reasoning paths.

**[SC23 摘要]**
> self-consistency boosts the performance of chain-of-thought prompting with a striking margin on a range of popular arithmetic and commonsense reasoning benchmarks, including GSM8K (+17.9%), SVAMP (+11.0%), AQuA (+12.2%), StrategyQA (+6.4%) and ARC-challenge (+3.9%).

📌 **分母**：5 个基准（GSM8K / SVAMP / AQuA / StrategyQA / ARC-challenge），**相对 CoT 贪心解码**的提升。
📌 **口径**："把推理路径 marginalize 掉，取**最一致的答案**" ⇒ **众数答案是既有原语**，我们的"交集率"应改写成**多数票份额**。

**[CHE23 §2]**
> self-consistency ( Wang et al., 2022 ) augments chain-of-thought prompting ( Wei et al., 2022 ) by sampling multiple reasoning chains and then taking a majority vote on the final answer set.

**[CHE23 摘要]**
> we propose Universal Self-Consistency (USC), which leverages LLMs themselves to select the most consistent answer among multiple candidates.

📌 **★ 边界**：Self-Consistency 的多数票依赖**答案抽取**（数学题可精确匹配 ⇒ 零 embedding）；自由文本**做不了**，于是 USC 改用**LLM 判蕴含**⇒ **我们若走这条路，也必须付出"外部模型"代价**（或用 `family_key` 顶替）。

---

## Q13 — 锚外：三个先例的参照系各是什么

**[MAJ24 §4]**
> We now introduce a novel benchmark, DiscoveryBench , for discovering data-driven hypotheses. In this benchmark, a data-driven discovery task is defined as follows: Given one or more task dataset(s) D and a discovery goal G , derive a hypothesis h = ψ ( c , v , r ) addressing G with the highest specificity for the context c , variables v , and relationship r supported by D .

**[MAJ24 §数据构建]**
> This is particularly useful as our goal is to evaluate LLMs' ability to solve a discovery task that is realistic but never reported before.

**[MAJ24 §3.2]**
> we additionally introduce a structured formalism that breaks a hypothesis down into three hypothesis dimensions : • Contexts ( c ) : Boundary conditions that limit the scope of a hypothesis. E.g., "for men over the age of 30" or "in Asia and Europe" or unbounded/full dataset when not specified. • Variables ( v ) : Known set of concepts that interact in a meaningful way under a given context to produce the hypothesis. E.g., gender , age , or income . Note that each hypothesis is associated with a target variable and a set of independent variables. • Relationships ( r ) : Interactions between a given set of variables under a given context that produces the hypothesis. E.g., "quadratic relationship" , "inversely proportional" , or piecewise conditionals.

📌 **★ 参照系差异（写进我们的论文）**：
- **DiscoveryBench 的"新"** = "**从未被发表过**"（文献/已发表研究）⇒ 参照系是**世界**
- **PSFA 的"漏掉项"**（项目已精读，`LIT/DEEP-30-ProblemSpaceFormulation-spec.md`）= 人类专家问题空间分解（Newell 1980 / GOMS），候选槽位**先验封闭**⇒ 参照系是**人类分解**
- **OvertonScore 的分母** = 人类观点集 `W(x)` ⇒ 参照系是**人类观点**
- **我们的 `C_t`** = **事前预注册的结论空间** ⇒ 参照系是**我们自己划的答案空间**
⇒ 三条检索路径（open-ended problem formulation / problem space coverage / discovering new problem dimensions）都跑过，**未找到参照系相同的先例**；但**"集合覆盖率"这个形式有先例**（Q4）⇒ 措辞必须是"**形式有先例，参照系与判据是新的**"。

---

## Q14 — 过早闭合的另一条路（必须排除，但概念要借）

**[MIN26 摘要]**
> We identify reasoning-level semantic redundancy as a complementary signal for semantic-preserving early exit: when successive steps no longer add novel progress and instead revisit established conclusions, the reasoning trajectory has likely converged.

**[MIN26 §1]**
> To quantify this redundancy, we analyze five representative LRMs and find that 41–52% of reasoning tokens are generated after the model has already reached its final answer

**[MIN26 摘要]**
> Across five LRMs and five challenging reasoning benchmarks, PUMA achieves 26.2% average token reduction while preserving accuracy and retained CoT quality.

📌 **概念对应**：这**就是**我们"边际利用率"想说的事（"最近还在不在产生新信息"）⇒ **概念可引，指标不可用**。
⚠️ **实现用了微调过的 `Qwen3-Embedding-0.6B`**（`s_t^(k) = max_{t-k≤j<t} cos(f(r_j), f(r_t))`，默认 `τ_sim = 0.35`、`k = 1`）⇒ **按本项目纪律排除**。
📌 **分母**：**5** 个 LRM × **5** 个基准；**41–52%** 的推理 token 落在"最终答案之后"。
⚠️ **"置信度信号误停率 ≈44%、答案一致性 ≈64%"** 这两个数字**来自二手中文报道，本次未在论文正文核实** ⇒ 引用须标"二手"或回原文补核。

---

## Q15 — "中庸无害？不对，有害"——先例已经论证过了（★ 这条替我们省了一整段自证）

**[POO26 §1]**
> However, the goal of true political neutrality has been shown to be impossible—and not always desirable ( Fisher et al., 2025 ) ; a neutral answer may still omit or misportray minority perspectives.

**[POO26 §1]**
> Traditional alignment strategies that aggregate over diverse preferences have been shown to exacerbate this issue ( Casper et al., 2023 ; Kaufmann et al., 2024 ; Feffer et al., 2023 ) , collapsing genuine disagreements ( Durmus et al., 2024 ; Sorensen et al., 2024a ; Bakker et al., 2022 ; AlKhamissi et al., 2024 ; Ryan et al., 2024 ) into a single normative stance—an issue known as value monism ( Gabriel, 2020 ) . Outputs that appear neutral often encode majority or developer-preferred biases, entrenching representational harms ( Chien & Danks, 2024 ) and heightening safety risks

**[POO26 附录 B, 逐字]**
> we find a moderate negative association between the two metrics (Pearson r = − 0.41 , Spearman ρ = − 0.32 , Kendall τ = − 0.24 ). This divergence reinforces that political neutrality (i.e., low slant) and pluralistic representation are distinct constructs. A model may appear neutral by producing a single centrist or generic answer that omits minority viewpoints, thereby achieving low perceived slant but low pluralism. Conversely, a model that surfaces multiple valid perspectives may be perceived as more "biased" in a pairwise comparison, even while achieving higher pluralistic coverage. This underscores the need for a dedicated Overton pluralism metric

📌 **★ 这就是"中庸"的既有名字与它的代价**：
- **"value monism"（价值一神论）** = 把真实分歧**塌成单一规范立场**
- **"a single centrist or generic answer that omits minority viewpoints"** = **中庸答案的逐字描述**
- **"政治中立 ≠ 多元代表"**：两者相关系数为**负**（Pearson **r = −0.41** / Spearman **ρ = −0.32** / Kendall **τ = −0.24**）⇒ **看起来越中立，覆盖反而可能越差**
⇒ ★ 我们的立论（"产出中庸"是失败模式）**有现成论证可引，不必自证**；且"中庸"这个概念在文献里叫 **value monism / a single centrist or generic answer**。
