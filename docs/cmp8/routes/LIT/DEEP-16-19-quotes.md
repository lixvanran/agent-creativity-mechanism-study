# DEEP-16-19 · 逐字摘录（可直接引用）

> **用途**：为 `DEEP-16-19-DiversityCollapse-ADHD-spec.md` 提供**逐字可核**的原文底稿。
> **定位方式**：
> - **论文**：`PDF p.<n> / 会议 p.<m>`（`m = 250 + n`，会议页码 251–306 共 56 页）+ `ar5iv 文本行号 L<n>`（我用 `https://ar5iv.labs.arxiv.org/html/2604.18005` 抽取的 2,565 行纯文本，行号可复现）。
> - **代码**：`仓库路径:行号`。
> - **站点/预印本**：`URL §小节`。
> - **论文文本源**：ACL Anthology 官方 PDF `https://aclanthology.org/2026.findings-acl.13.pdf`（4,557,455 字节，**56 页完整**，`pdftotext` 逐页可核）。⚠️ arXiv 的 PDF 端点在本沙盒下产出 **xref 损坏**的文件（`pdftotext` 报 "Couldn't find trailer dictionary"），故页码一律以 ACL PDF 为准。
> - **访问日期**：2026-10-21（UTC）

---

## 0. 一页速查表

| 主题 | 落在 | PDF p. / 会议 p. |
|---|---|---|
| Table 1（人类一致率） | §2.3 | p.3 / 253 |
| §4 五种 persona 定义 | §4 | p.4 / 254 |
| Fig 3 caption（Sycophancy Trap） | §3 | p.5 / 255 |
| §5 绝对 Vendi「单调上升」+ Vendi/N 1.03→0.47 | §5 | p.6 / 256 |
| §5.2 三拓扑 + Fig 10 | §5.2 | p.7 / 257 |
| §8 Conclusion | §8 | p.9 / 259 |
| Limitations（人类验证只覆盖多样性轴） | Limitations | p.10 / 260 |
| **Appendix B 人类验证全流程** | App B | **p.14 / 264** |
| **Appendix C 四度量定义** | App C | **p.15 / 265** |
| **Appendix D Constructive Conflict 公式 + 判官提示词** | App D | **p.16 / 266** |
| Appendix E 子组流程 | App E | p.16 / 266 · p.18 / 268 |
| **Appendix F 敏感性（Table 2 全表）** | App F | **p.19 / 269** |
| **Appendix G.1 礼貌性共识塌缩三判据 + 61%** | App G.1 | **p.20 / 270** |
| Appendix G.3 **标题 TTR（★ 我们的离散判据）** | App G.3 | **p.22 / 272** |
| Appendix G.4 锚定相似度 0.627 vs 0.441 | App G.4 | p.23 / 273 |
| **Appendix H 逐主题规模表（Table 8）** | App H | **p.24–25 / 274–275** |
| **Appendix I 2×2 因子（Table 9/10/11/12）** | App I | **p.24–27 / 274–277** |
| Appendix K 2×2 提示词（Senior>Junior in flat） | App K | p.28 / 278 · p.31 / 281 |
| **Appendix M GPT-5.1 复现（Table 25）** | App M | **p.32–33 / 282–283** |
| **Appendix N 立场判定 rubric + R_crit** | App N | **p.33 / 283** |

---

## A. Diversity Collapse（论文）

### A.1 §2.3 — 度量体系 + 人类验证的**一句话**（PDF p.3 / 会议 p.253）

> **Table 1**（`L44–52`）：
> ```
> Metric | Human Agreement (%)
> Vendi Score | 87%
> 1-φ | 82%
> PCD | 81%
> Table 1: Agreement between human judgments and metric-induced ordering in pairwise diversity comparisons.
> ```

> `L62`：
> *"We validated these metrics via human evaluation (see Appendix B ) using pairwise comparisons by five expert annotators: the Vendi Score matched expert diversity judgments in 87% of cases, with all three embedding-based metrics exceeding 80% agreement (Table 1 )."*

> `L54–61`（四度量定义，逐字）：
> *"**Effective Diversity (Vendi Score 15 )**: Measures the effective number of unique semantic modes in the set X based on the spectral entropy of the kernel matrix. Unlike simple counting, it is robust to cluster imbalances, indicating whether the system is exploring the semantic space efficiently."*
> *"**Structural Disorder**: Adapted from the order parameter φ 23 ; 42 as the average cosine similarity between individual proposals and the group's mean embedding, this metric diagnoses the group's dynamic state. Low values of 1-φ indicate collapse toward a single centroid (Echo Chamber 43 state), while high values indicate that the system maintains pluralistic perspectives despite interaction."*
> *"**Semantic Dispersion (PCD)**: Computes the average pairwise cosine distance between proposals. While Vendi Score counts the modes , Dispersion measures the magnitude of the spread."*
> *"**Lexical Uniqueness**: Utilizes IDF-weighted n-gram statistics to measure surface-level redundancy. This serves as a sanity check: high semantic diversity scores should not be driven merely by verbose rephrasing of identical ideas."*

---

### A.2 §3 — Fig 3 caption：★ "Sycophancy Trap" 原文（PDF p.5 / 会议 p.255）

> `L68`：
> *"**Figure 3: Diversity Metrics across Cognitive Structures.** Horizontal collaboration (Junior-driven) consistently maximizes diversity (Vendi: **8.08**), identifying the "Unbound Junior" effect. Surprisingly, Interdisciplinary collaboration exhibits the lowest diversity (Vendi: **4.65**), suggesting that distinct expert roles induce a "**Sycophancy Trap**" where agents converge on safe, high-level generalities."*

> `L69`（Fig 4 caption）：
> *"**Figure 4: Semantic Regimes of Cognitive Structures.** UMAP projection reveals a bifurcation. The Conservative Cluster (Bottom) is dominated by expert-driven structures (Leader-Led, Interdisciplinary), while the Innovation Frontier (Top) is populated by junior-driven structures (Horizontal, Vertical). This confirms that "Seniority" tends to constrain the semantic search space."*

---

### A.3 §4 — ★ 五种 persona 的确切定义（PDF p.4 / 会议 p.254）

> `L77–82`：
> ```
> We compare five cognitive structures (detailed in Appendix) designed to mimic real-world scientific collaboration:
> Naive Collaboration: Agents interact without defined roles or hierarchy.
> Leader-Led Collaboration: A designated senior expert guides discussion, with junior agents aligned to follow authoritative directives.
> Horizontal Collaboration: A group of early-career researchers collaborates flatly without senior oversight.
> Interdisciplinary Collaboration: Experts from distinct fields collaborate to synthesize cross-domain ideas.
> Vertical Collaboration: A hierarchical mix of senior experts, mid-career researchers, and early-career scholars.
> ```

---

### A.4 §4.1–4.3 — ★ "Authority-Induced Collapse" 机制原文（PDF p.4–5 / 会议 p.254–255）

> `L85`（★ **"不是专家本身，是专家+层级"**）：
> *"Although "Interdisciplinary" might be thought to conflate expertise with implicit authority, the explicitly authority-weighted "Leader-Led" condition collapses nearly identically (Figure 5 ), and **under a flat peer-to-peer topology, Senior personas actually produce higher diversity than Junior personas** (Appendix K , which also rules out directive prompt tone)—indicating that **the combination of expertise and hierarchy, not expertise alone, drives the collapse**."*

> `L88–90`（★ **Gravitational Collapse 机制段**）：
> ```
> The density plot reveals a sharp cognitive dichotomy:
> Gravitational Collapse (Leader-Led/Naive): The Leader-Led structure (Red) closely mirrors the Naive baseline (Grey), exhibiting high Kurtosis. This suggests that the presence of senior authority acts as a strong attractor. Junior agents likely succumb to sycophancy, aligning their vectors with the leader rather than offering orthogonal critiques.
> Sustained Divergence (Horizontal/Vertical): The Horizontal (Cyan) and Vertical (Green) distributions significantly flatten the peak. The Vertical structure is particularly notable: by mixing senior guidance with junior exploration, it avoids the total collapse seen in Leader-Led setups, maintaining a "Goldilocks" zone of divergence.
> ```

> `L97`（★ 论文对 **Authority-Induced Collapse** 的定义句）：
> *"**Authority-Induced Collapse is a form of directed coupling that accelerates convergence.** The Vertical structure which mixes authority levels, offers a compromise, mitigating the chaos of juniors with the structure of seniors."*

> `L98`（★ 质量-多样性不对称，**这是它的招牌结论，也是我们要警惕的**）：
> *"While Interdisciplinary attains the highest Overall Quality (8.50 vs. Horizontal's 7.88, a + 0.6 gap on a 10-point scale, Figure 6 ), this gain does not offset the much larger diversity drop between the same two conditions (Vendi 4.65 vs. 8.08, Figure 3 ). The Overall-Quality advantage also does not extend to Workability, where Horizontal proposals score highest, and Vertical (OQ 8.32) occupies an intermediate position that preserves distributional divergence (Figure 5 ), suggesting that **rigid hierarchical authority often optimises for safe consensus at the expense of actionable exploration**."*

---

### A.5 §5 — ★ Vendi/N 读数 + ★ **「单调上升」的原句（用于纠正）**（PDF p.6 / 会议 p.256）

> `L103–104`（逐字）：
> ```
> Increasing group size yields diminishing marginal returns in effective diversity, revealing a significant efficiency gap.
> While the absolute Vendi Score (blue line) increases monotonically from N=3 to N=7 , the Diversity Utilization Ratio (red bars), defined as \text{Vendi}/N , plummets from 1.03 to 0.47. This indicates that adding agents does not linearly expand the semantic search space; rather, new agents increasingly overlap with existing ones. This phenomenon aligns with the "Compute Efficiency Paradox," suggesting that without structural intervention, simply scaling group size faces rapid saturation in information gain. A per-topic decomposition (Appendix H ) rules out topic-capacity exhaustion as the cause.
> ```
> ⚠️ **"increases monotonically from N=3 to N=7" 与它自己 Table 8 的 Mean 行矛盾 —— 见 A.9。**

> `L101`（Fig 7 caption）：
> *"**Figure 7: The Divergence from Theory in Scaling Efficiency.** This plot compares the observed Effective Diversity (Vendi Score, blue line) against the theoretical Diversity Utilization Ratio (Vendi/ N , red bars) as group size increases. While diversity grows, the efficiency per agent drops significantly."*

> `L110`（★ **"Stable Expansion" —— 一会话内局部变宽 vs 跨会话全局收缩**）：
> *"This "divergence within convergence" reflects within-session refinement: agents, while agreeing on a general direction, continue to expand the radius around the stabilising centroid. This is distinct from the across-run diversity collapse in Sections 4 and 5 : a single session can expand locally while the broader pool still shows structural contraction."*

---

### A.6 §5.2 — ★ 三拓扑 + Fig 10 机制（PDF p.7 / 会议 p.257）

> `L114–118`：
> ```
> Finally, we examine how different communication topologies, Standard, Nominal Group Technique (NGT) 12 , and Subgroups (detailed in Appendix E ), influence the dynamics of diversity and conflict.
> Figure 10: Mechanism of Process Intervention. (Left) Evolution of Semantic Diversity shows NGT's early advantage and Subgroups' late rebound. (Right) Density of Constructive Conflict highlights Subgroups' ability to sustain critical engagement. See Appendix N for the detailed prompting strategy and scoring rubric.
> Process interventions effectively disrupt consensus collapse, with NGT maximizing initial diversity and Subgroups sustaining critical engagement.
> Figure 10 (Left) shows that NGT (green) initiates with the highest semantic diversity, significantly outperforming the Standard baseline (red). This confirms that the "blind-writing" phase of NGT effectively mitigates production blocking and anchoring effects. Meanwhile, the Subgroups topology (cyan) demonstrates a unique "resilience spike" in diversity midway through the discussion. Crucially, Figure 10 (Right) reveals that Subgroups maintain the highest and most stable density of constructive conflict (interactions with critique score \geq 7 ; metric formalised in Appendix D ) in the latter half of the debate. This suggests that partitioning the social graph creates "local pockets of divergence" that prevent the premature "rush to agreement" observed in the Standard mode. A 2 \times 2 Persona \times Topology factorial (Appendix I ) and a cross-model replication on GPT-5.1 (Appendix M ) further show that this topology ranking is structural rather than model-specific.
> ```

---

### A.7 §6 / §8 — 结论 + 我们的两个三档映射（PDF p.9 / 会议 p.259）

> `L153`（§8 Conclusion 逐字）：
> *"We systematically evaluated diversity in multi-agent systems for open-ended idea generation, using scientific proposal tasks as a testbed. **Simply increasing agent count does not guarantee greater idea diversity. Rather, diversity collapse arises from structural coupling across three levels: alignment at the model level, hierarchical or role-differentiated coordination at the cognition level, and dense communication at the system level.** These factors jointly promote premature consensus. **Interaction designs that preserve independence, such as the blind-writing phase of NGT and subgroup isolation, consistently yield higher diversity with only modest differences in judged quality.**"*

> `L118`（★ **"先独立后汇总"最直接的背书**）：
> *"This confirms that the "**blind-writing**" phase of NGT effectively mitigates production blocking and anchoring effects."*

> `L139`（§6.2 "The Rush to Agreement"）：
> *"The density-collapse patterns in Figure 5 and the transcripts in Appendix G suggest that **under structural coupling, agents treat agreement as a proxy for correctness**: the very mechanisms designed to ensure quality, namely collaboration and peer critique, can force the system to prematurely abandon unconventional ideas to satisfy collective pressure for consensus."*

> `L140`：
> *"In summary, achieving effective and diverse ideation in MAS requires more than simply assembling a larger or more connected group. **Diversity is a fragile property, easily sacrificed in the rush to agreement.**"*

---

### A.8 ★★ Appendix B — 人类验证全流程（PDF p.14 / 会议 p.264）★ §6 的抄写底稿

> `L587–594`（**全文逐字**）：
> ```
> Appendix B Human Evaluation Details
> To assess whether the automatic diversity metrics used in this work align with human judgments under our task setting, we recruited five AI PhD students with expertise in relevant research areas.
> B.1 Procedure
> For each topic, annotators were presented with 25 randomly sampled pairwise comparisons of proposal sets generated under different collaboration modes. In total, each annotator evaluated 100 pairwise comparisons. Blind to the system identities, they were asked a single question: "Which proposal set exhibits greater diversity of research ideas?"
> B.2 Quality Control
> Annotators were also instructed to verify that all proposal sets met a basic bar of idea quality (coherent, on-topic, plausible). All evaluated sets satisfied this criterion. This confirms our assumption that diversity analysis is performed on a valid candidate set.
> B.3 Agreement Results
> We measured the agreement between human majority judgments and the ranking induced by automatic metrics. The Vendi Score achieved the highest alignment (87%), followed by Structural Disorder ( 1-\phi ) and Semantic Dispersion (PCD), validating our use of embedding-based metrics for this domain.
> ```
> ⚠️ **W-D-3 不在 Table 1 里 ⇒ 论文从未用人类验证过 W-D-3。**

---

### A.9 ★★ Appendix H — 逐主题规模表 + ★ **「单调上升」的反证**（PDF p.24–25 / 会议 p.274–275）

> `L1108`（Appendix H.1，逐字）：
> *"The aggregate analysis in Figure 7 shows that the **Diversity Utilization Ratio (Vendi/N) declines from 1.03 at N{=}3 to 0.47 at N{=}7**. A natural alternative hypothesis is that this saturation reflects the finite complexity of the 20 ICLR research topics used as our testbed: perhaps each topic supports only ∼3 genuinely distinct ideas, and groups larger than N{=}3 simply exhaust the available ideation space. To test this hypothesis, we decompose the scaling analysis to the individual topic level."*

> `L1110`（H.2 Method）：
> *"For each of the 20 ICLR topics and each group size N\in\{3,4,5,6,7\} , we have 50 proposals generated by independent N -agent MAS runs (no cross-run interaction). We compute the per-topic Vendi Score using the same **OpenAI text-embedding-3-large** embeddings and cosine-similarity kernel as in the main paper."*

> `L1113`（H.3 Finding 1，★ 逐字）：
> *"Aggregated across topics, the mean Vendi Score **increases monotonically from 3.09 at N{=}3 to 3.32 at N{=}7 (+7.4%, paired t{=}5.46 , p{<}0.0001 )**, with **17 out of 20 topics** exhibiting growth. This directly refutes the "low-hanging fruit" hypothesis: if topics were limited to ∼3 distinct ideas, the Vendi Score would plateau at ∼3 regardless of group size. Instead, larger groups consistently produce a broader semantic space of proposals."*

> **Table 8 的 Mean 行（ACL PDF p.24 逐字，按列布局）**：
> ```
> Mean | 3.09 | 3.22 | 3.24 | 3.37 | 3.32
> Table 8: Per-topic Vendi Score across group sizes (N =3 to N =7 ). Each cell is computed from 50 independent
> proposals. Topics are sorted by Vendi at N =3 (descending). The mean Vendi increases from 3.09 to 3.32, with
> 17/20 topics showing growth from N =3 to N =7 .
> ```
> ⚠️⚠️ **★ 纠正**：**Mean 行是 3.09 → 3.22 → 3.24 → 3.37 → 3.32**，**N=7 比 N=6 低 0.05** ⇒ §5 正文的 *"increases monotonically"* **不成立**。
> ⚠️ **而 Table 8 的 caption 自己只写 "The mean Vendi increases from 3.09 to 3.32"（端点），没有说 monotonic** ⇒ **是 §5 的行文多说了，不是表错了**。
> ⚠️ 我用 20×5 原始格复算：**20 个主题里 0 个**在 N=3..7 全程非递减（19/20 至少降一次）；"17/20" 只是 **N=3→N=7 的端点方向**。
> ⚠️ **可以安全转述的三件事**：① **利用率 Vendi/N 单调下降** 1.03→0.80→0.65→0.56→0.47；② **端点 +7.4%**（paired t=5.46, p<0.0001, 17/20）；③ **"饱和而非耗尽"**（r=−0.14, p=0.55 排除主题容量假说）。

> `L1253` 附近（H.4 Finding 2）：
> *"The correlation is not statistically significant (Pearson r{=}{-}0.14 , p{=}0.55 ). Both high-capacity topics (e.g., General ML: 3.51{\to}3.53 ; Physical Sciences: 3.42{\to}3.75 ) and low-capacity topics (e.g., Transfer/Meta: 2.60{\to}2.74 ; NeuroSymbolic: 2.74{\to}3.04 ) exhibit similar utilization slopes ( -0.143 vs. -0.127 ). This confirms that the sub-linear scaling is a structural property of multi-agent consensus dynamics, not an artifact of topic-specific ideation ceilings."*

---

### A.10 ★★ Appendix I — 2×2 析因：拓扑定义 + persona 定义 + 读数（PDF p.24–27 / 会议 p.274–277）

> `L1271–1280`（★ **拓扑与 persona 的确切定义，§1 与 §2 的抄写底稿**）：
> ```
> Topology definitions.
> • Recursive : All 3 agents see the full conversation history and speak sequentially in each round (4 discussion rounds + 1 proposal round). This corresponds to grouped_sequential order with all visibility.
> • NGT (Nominal Group Technique): Round 1 is a blind-writing phase where each agent writes independently without seeing others' contributions. Rounds 2–3 involve sequential discussion among non-leader agents with full visibility. Round 4 includes all agents (including the leader). Round 5 produces the proposal.
> Persona definitions.
> • Naive : Agents are prompted as "senior AI researchers with expertise in [topic]" with no specific role differentiation.
> • Horizontal : Agents are prompted as "first-year PhD students with limited research experience in [topic]" who bring "fresh curiosity and basic academic foundation."
> ```

> `L1282`（★ Metric note，**"两种 Vendi 量纲"警告**）：
> *"We report within-topic Vendi Scores : for each of the 20 ICLR topics, we compute the Vendi Score over the 50 proposals generated under that topic, then average across topics. This measures how semantically spread out proposals are within a single research domain . It is complementary to the global Vendi Score used in the main paper, which pools all proposals across topics and additionally captures between-topic spread; the two views can rank conditions slightly differently because they measure different facets of diversity."*

> `L1490`（I.3 Finding 4，★ 逐主题拓扑效应）：
> *"Panel (b) displays per-topic topology effects for both personas — the Naive persona shows a consistently large negative effect (**all 20 topics**), while the Horizontal persona shows a mixed pattern (**9/20 negative, 11/20 near-zero or positive**). Panel (c) shows the cross-persona effect correlation ( r=0.30 , p=0.20 ), indicating that the per-topic topology sensitivity does not reliably transfer across personas."*

> `L1494–1498`（I.4 Interpretation，★ **§2 的抄写底稿**）：
> ```
> 1. Topology is a genuine structural lever. Under the Naive persona, switching between Recursive and NGT produces a large, consistent within-topic diversity difference ( d=2.21 , all 20 topics). This confirms that communication topology has a real causal effect on within-topic diversity, independent of persona.
> 2. Persona moderates topology magnitude. The significant interaction ( p<0.0001 ) confirms that persona modulates the topology effect size. Under the Horizontal persona, the within-topic topology effect is negligible ( d=0.25 , p=0.298 ).
> 3. Mechanistic reading. The Horizontal persona (less directive, exploratory agents) is more robust to topology changes, suggesting that when agents are less constrained by authority priors, the communication structure has less marginal impact on within-topic diversity. The Naive persona (senior researchers with stronger priors) is more susceptible to coupling-induced convergence, making topology a more effective lever. When baseline coupling is already low, structural interventions yield diminishing marginal returns.
> ```

> **Table 11（PDF p.27）读数**：
> ```
> Effect | Mean Difference | t | p | Cohen's d
> Naive: Rec. - NGT | + 0.456 | 9.65 | < 0.0001 | 2.21
> Horizontal: Rec. - NGT | + 0.040 | 1.07 | 0.298 | 0.25
> Interaction: Persona × Topology | Δ_N − Δ_H = 0.416 | −8.18 | < 0.0001 | —
> ```
> ⚠️ **符号提醒**：论文表里写的是 "Rec. − NGT"（**正值 = Recursive 更高 = NGT 更低**）。正文 §A.10 上面那句 "NGT 把多样性从 3.125 压到 2.669" 方向是 **NGT < Recursive** ⇒ **在提案池层面 NGT 是降低多样性的**。⚠️ 这与 §5.2 的 "NGT 初始多样性最高" **方向相反**（那是轮内曲线）⇒ **论文内部存在两个口径**。

> **Table 12（PDF p.27）PCD 独立验证**：
> ```
> Recursive | NGT
> Naive     | 0.187 ± 0.014 | 0.158 ± 0.020
> Horizontal| 0.127 ± 0.024 | 0.122 ± 0.019
> ```

---

### A.11 ★★ Appendix C — 四度量的数学定义（PDF p.15 / 会议 p.265）★ §3 的抄写底稿

> `L597–617`：
> ```
> C.1 Effective Diversity (Vendi Score)
> The Vendi Score measures diversity as the effective number of distinct samples, derived from the spectral entropy of a similarity kernel. Proposal embeddings are obtained using a fixed pretrained text embedding model. A cosine similarity kernel is constructed and normalized by the number of samples. The eigenvalue spectrum of this kernel reflects how variance is distributed across semantic directions.
> ...
> C.2 Structural Disorder ( 1-\phi )
> The order parameter \phi measures the degree of alignment among proposals by computing the average cosine similarity between each proposal embedding and the mean embedding. Unlike pairwise metrics, \phi captures a global property of the system: whether collaboration induces convergence toward a shared semantic direction.
> We report Structural Disorder as 1-\phi so that higher values consistently correspond to greater diversity. This metric is sensitive to collaboration-induced consensus even when pairwise distances remain moderate, allowing us to distinguish systems that appear diverse locally but are globally aligned around a single dominant perspective.
> C.3 Semantic Dispersion (PCD)
> Semantic Dispersion is computed as the mean pairwise cosine distance between proposal embeddings. This metric directly measures the geometric spread of proposals in representation space.
> While Effective Diversity captures how many semantic modes are present, Semantic Dispersion captures how far apart those modes are. Including both prevents misinterpretation of diversity arising from either tightly packed clusters or uniformly dispersed noise.
> C.4 Lexical Uniqueness (Content-only WDistinct-n
> Lexical Uniqueness is designed to measure surface-level redundancy while minimizing sensitivity to shared academic templates and formatting artifacts.
> Content-only preprocessing.
> All proposals are lowercased and tokenized using a simple alphabetic tokenizer. Stopwords are removed using a fixed list of high-frequency functional words (e.g., articles, prepositions, auxiliaries). In addition, common academic boilerplate terms (e.g., paper , method , results ) are filtered to reduce the influence of structural conventions shared across proposals.
> n-gram construction.
> After preprocessing, the remaining content tokens are treated as a sequence, and contiguous n-grams are extracted. This preserves local semantic structure while avoiding reliance on extracted keyphrases or sentence boundaries.
> IDF weighting and global normalization.
> To downweight ubiquitous expressions and emphasize content-specific phrasing, each n-gram is weighted by inverse document frequency (IDF), computed over the union of proposals from all collaboration settings. This global normalization ensures that lexical scores are comparable across different experimental conditions.
> Choice of n.
> We use n=3 by default. Trigrams provide a stable granularity that captures method- and concept-level expressions, while larger n-grams tend to become nearly unique in open-ended generation and are dominated by surface-level phrasing rather than substantive content.
> Interpretation.
> Lexical Uniqueness reflects whether agents avoid repeating the same formulations and boilerplate patterns. It is not intended as a proxy for semantic diversity, but as a complementary signal that detects lexical echoing that may persist even when semantic metrics suggest diversity.
> ```
> ⚠️ **最后一句是引用本文时最该带上的一句**："It is **not** intended as a proxy for semantic diversity"。

---

### A.12 ★★ Appendix D — Constructive Conflict 公式 + 判官提示词（PDF p.16 / 会议 p.266）★ §6 的抄写底稿

> `L618–655`：
> ```
> Appendix D Constructive Conflict Metric.
> We combine semantic embeddings and large language model (LLM) judgment to construct a metric for constructive conflict in multi-speaker discussions. For each utterance, we obtain a sentence embedding using the text-embedding-3-large model. To avoid truncating long texts, we adopt a chunk-and-average strategy: the utterance is split into contiguous character chunks \{c_{k}\}_{k=1}^{K} (each up to ∼ 12000 characters), each chunk is embedded as \mathbf{e}(c_{k}) , and we compute the mean-pooled, \ell_{2}-normalized embedding
>
> \tilde{\mathbf{e}}=\frac{1}{K}\sum_{k=1}^{K}\mathbf{e}(c_{k}),\quad\mathbf{e}=\frac{\tilde{\mathbf{e}}}{\|\tilde{\mathbf{e}}\|_{2}}.
>
> Within each discussion, we treat the first utterance as an anchor with embedding \mathbf{e}_{1} . For utterance t ( t\geq 2 ) with embedding \mathbf{e}_{t} , we measure its semantic deviation from the anchor via cosine similarity
>
> \operatorname{sim}_{t}=\frac{\mathbf{e}_{t}^{\top}\mathbf{e}_{1}}{\|\mathbf{e}_{t}\|_{2}\,\|\mathbf{e}_{1}\|_{2}},
>
> and define its semantic divergence as
>
> \operatorname{Divergence}_{t}=1-\operatorname{sim}_{t}.
>
> To distinguish mere novelty from constructive disagreement, we further use a chat-based LLM to rate the degree of disagreement/novelty between consecutive utterances. Let x_{t-1} denote the previous utterance and x_{t} the current utterance. We prompt the LLM with the following instruction:
>
> Compare Speaker B's statement
> to Speaker A's context.
> Speaker A: "< previous context truncated to last 400 characters>..."
> Speaker B: "< current statement>"
> Task: Rate level of DISAGREEMENT/NOVELTY (1-10).
> Strict Scoring:
> - 1-4: Echo/Additive (Safe)
> - 5-6: Minor Detail
> - 7-8: Soft Critique/Refinement
> - 9-10: Major Disruption
> Output integer only.
>
> The model outputs a single integer score s_{t}\in\{1,\dots,10\} . We interpret scores s_{t}\geq 7 as indicating the presence of clear critique or constructive conflict, and define a binary indicator
>
> C_{t}=\mathbb{I}[s_{t}\geq 7].
>
> For a given experimental condition (e.g., Standard , NGT , or Subgroups ), we aggregate across all discussions at the same turn index t and compute the Constructive Conflict Ratio
>
> \operatorname{CCR}_{t}=\mathbb{E}[C_{t}],
>
> along with its standard error of the mean (SEM) for visualization. In our figures, the right-hand panel plots \operatorname{CCR}_{t} over the first few turns (here, t\leq 5 ) for each condition, capturing how the density of constructive conflict evolves as the discussion progresses under different institutional designs.
> ```

> **Appendix N.1 的立场 rubric + N.3 的 R_crit（PDF p.33 / 会议 p.283）**：
> ```
> N.1 Scoring Rubric
> We utilized gpt-4o-mini as the evaluator to rate the Critical Contribution of a response relative to the previous context. The scoring follows a strict 1-10 scale designed to penalize non-informative agreement (sycophancy):
> • 1-3 (Echo/Safe): The agent merely agrees, repeats the previous point, or adds minor "fluff" (e.g., "I agree", "Building on that…").
> • 4-6 (Additive): The agent adds specific details or examples but remains strictly within the logical framework of the previous speaker.
> • 7-8 (Refinement): The agent points out a gap, limitation, or edge case in the previous logic (Soft Critique).
> • 9-10 (Disruption): The agent fundamentally challenges the premise, proposes a competing paradigm, or steers the discussion to a completely new dimension.
> ...
> N.3 Metric Calculation
> The High Critique Ratio ( R_{crit} ) for a collaborative session is calculated as:
>
> R_{crit}=\frac{1}{N}\sum_{i=1}^{N}\mathbb{I}(S_{i}\geq 7)
>
> where N is the total number of turns (excluding the initial anchor), S_{i} is the LLM-assigned score for turn i , and \mathbb{I} is the indicator function.
> ```
> ⚠️ **注意两处差异**：Appendix D 用 **≥7 记冲突**、Appendix N 的 rubric 把 **7–8 定义为 "Soft Critique"（软批评）** ⇒ **"≥7 就算建设性冲突"是一个偏松的阈值**，我们照抄时要显式声明。

> **Stance Classification Prompt（Appendix N.2 / O，PDF p.33）逐字**：
> ```
> You are an expert in analyzing academic discourse.
> Context (Previous Speaker): "{PREV_TEXT}..."
> Current Speaker: "{CURRENT_TEXT}"
> Task: Rate the "Critical Contribution" of the Current Speaker on a scale of 1 to 10.
> Strict Scoring Rubric:
> • 1-3: Mere agreement or repetition.
> • 4-6: Additive details without conflict.
> • 7-8: Identifying gaps or limitations.
> • 9-10: Fundamental disagreement or novel pivot.
> Instruction: Be harsh. Most cooperative dialogues in LLM interactions tend to be sycophantic and should score between 3-5. Only rate \geq 7 if there is a clear, independent critical thought.
> Output: Output ONLY the integer score.
> ```
> ⇒ ★ **这个提示词本身就是我们要抄的"离散冲突载体"**：它**不评质量**，只评"有没有独立批判"。

---

### A.13 ★★ Appendix F + Table 2 — 敏感性 + ★ **W-D-3 的权威轴分辨率**（PDF p.19 / 会议 p.269）★ §3 的核心底稿

> `L819`（F.1）：
> *"Across all settings, we observe that qualitative trends and relative comparisons across collaboration modes remain invariant."*

> `L831–837`（★ **F.4，W-D-3 的定位**）：
> ```
> F.4 Consistency Across the Four Reported Metrics
> We examine the relationship among the four metrics reported in the main paper (Table 2 ). Three of them are structural metrics computed in embedding space (Vendi, 1-\phi , and PCD using the OpenAI embedding), while the fourth captures lexical uniqueness (content-only weighted distinct-3, W-D-3).
> Across collaboration modes, the embedding-based structural metrics induce highly consistent relative orderings (with only minor local swaps), suggesting that our main structural conclusions are not driven by a single particular formulation.
> In contrast, W-D-3 does not necessarily match the embedding-based ordering, which is expected: it measures surface-level lexical novelty that can vary independently from semantic dispersion.
> We therefore treat W-D-3 as a complementary signal rather than a redundant proxy for structural diversity.
> ```

> `L838–846`（F.5 / F.6）：
> ```
> F.5 Lexical Uniqueness and n gram Order
> We assess the sensitivity of Lexical Uniqueness to the choice of n-gram order by computing content-only weighted distinct-n for n\in\{2,3,4\} . Relative ordering across collaboration modes remains stable for n=2 and n=3 , while higher-order n-grams exhibit mild saturation effects.
> ...
> F.6 Content-only Tokenization
> To evaluate the impact of content-only tokenization, we compare raw distinct-3 with content-only weighted distinct-3 . Raw lexical counts exhibit higher variance due to ubiquitous boilerplate expressions. Content-only tokenization reduces this variance while preserving the relative ordering across collaboration modes.
> ```

> **Table 2 全表（PDF p.19，逐格照录）** —— ★ **这张表是 §3 决策的依据**：
> ```
> Collaboration Mode | Vendi ↑ | (1-φ) ↑ | PCD ↑ | Vendi ↑ | (1-φ) ↑ | PCD ↑ | W-D-3 ↑ | Raw D-3 | W-D-2 | W-D-4
>                    |   OpenAI Embedding (Structural; Main)   |  BGE Embedding (Structural)  | Lexical (Main) | Lexical Sensitivity |
> Leader-Led        | 6.932 | 0.161 | 0.296 | 5.096 | 0.134 | 0.251 | 0.780 | 0.680 | 0.543 | 0.897
> Vertical          | 6.082 | 0.146 | 0.272 | 4.131 | 0.114 | 0.215 | 0.781 | 0.694 | 0.530 | 0.882
> Naive             | 5.567 | 0.154 | 0.285 | 4.141 | 0.127 | 0.239 | 0.638 | 0.522 | 0.426 | 0.754
> Interdisciplinary  | 4.647 | 0.119 | 0.225 | 3.623 | 0.098 | 0.187 | 0.734 | 0.665 | 0.465 | 0.866
> Horizontal         | 8.080 | 0.170 | 0.311 | 5.849 | 0.143 | 0.266 | 0.788 | 0.687 | 0.563 | 0.883
> ```
> ⚠️⚠️ **★ 决定性读数（§3.1 的依据）**：
> | 对比 | Vendi 落差 | **W-D-3 落差** |
> |---|---|---|
> | Leader-Led vs Horizontal | −1.148（**−14.2%**） | −0.008（**−1.0%**） |
> | Vertical vs Horizontal | −1.998（−25.3%） | −0.007（−0.9%） |
> | Interdisciplinary vs Horizontal | −3.433（**−42.5%**） | −0.054（−6.9%） |
> | Naive vs Horizontal | −2.513（−31.1%） | −0.150（−19.0%） |
> ⇒ **W-D-3 几乎测不出"权威 vs 平级"** ⇒ **不能当我们的主判据**。

---

### A.14 ★★ Appendix G.1 / G.3 / G.4 — 定性判据 + ★ **标题 TTR（我们的离散判据底稿）**（PDF p.20–23 / 会议 p.270–273）

> `L856–871`（★ **G.1 全部规则，§6 的抄写底稿**）：
> ```
> G.1 Inspection Rule Definitions
> Polite Consensus Collapse.
> We operationalize "polite consensus collapse" as a purely behavioral pattern satisfying all of the following criteria within a single session:
> 1. Absence of counter-claims : no turn contains an explicit critique, disagreement marker, or alternative proposal branch (defined as an explicit proposal of a different research direction from the one assigned by the Leader).
> 2. Absence of independent sub-problems : no Collaborator turn introduces a research question or sub-problem not already present in the Leader's framing.
> 3. Final-proposal alignment : the final proposal title and abstract recombine keywords and directions from the Leader's Round 1 assignment without introducing new thematic anchors.
> Deference and Pushback Markers.
> We define two complementary marker vocabularies applied to the opening sentence of each Collaborator turn:
> • Deference markers (agreement-first phrases): "Building on…," "Following…," "As you noted…," "Excellent point…," "I fully agree…," "I'd like to add to what…," "Great insight…," "That's a fascinating point…," and paraphrase-then-extend patterns (restating a prior speaker's claim before adding content).
> • Pushback markers : "I disagree," "however," "counterpoint," "I'm not convinced," "I would challenge," "alternatively," "a different view," "I'd push back," "I'm skeptical," "correct me if I'm wrong."
> Under these definitions, deference-marker openings appear in approximately 61% of Leader-Led sessions; pushback markers appear in fewer than 1%.
> ```

> `L893–934`（★★ **G.3 —— 标题级词汇集中度，这就是我们要用的离散度量**）：
> ```
> G.3 Title Keyword Frequency and Lexical Concentration Analysis
> To quantify the thematic concentration observed in Section 4 , we compute title-level lexical statistics across all 20 topics for the Interdisciplinary and Horizontal configurations.
> Method.
> We extract all proposal titles (924 Interdisciplinary; 632 Horizontal), tokenize after lowercasing and removing stopwords, and compute:
> (i) Type-Token Ratio (TTR = unique tokens / total tokens),
> (ii) top-k unigram and bigram frequencies,
> (iii) Jaccard similarity of the full vocabulary sets.
> Results.
> Statistic | Interdisciplinary | Horizontal
> Number of titles | 924 | 632
> Total tokens | 10,411 | 6,146
> Unique tokens | 729 | 958
> Type-Token Ratio (TTR) | 0.070 | 0.156
> Table 3: Lexical concentration comparison. Despite having more titles and tokens, Interdisciplinary proposals use fewer unique words, yielding a TTR 2.2 × lower than Horizontal.
> ...
> The full-vocabulary Jaccard similarity is 0.211 (294 shared words out of a union of 1,393), confirming that the two configurations draw from largely distinct lexical pools.
> Top-10 bigram overlap is 4/10, with shared bigrams being generic ML terminology ( metric learning , neural networks , reinforcement learning , representation learning ).
> ```
> ⇒ ★ **TTR 在权威轴上有 2.2× 分辨率，且方向安全**（Interdisciplinary token **更多** 10,411 > 6,146，而 TTR 随长度下降 ⇒ 长度效应与观察方向相反 ⇒ 真实差距更大）。
> ⇒ ★ **Table 4 top-10 词表（PDF p.22）**：
> ```
> Interdisciplinary: multi-scale, modeling, computational, clinical, biological, systems, integrating, learning, networks, bio-inspired
> Horizontal:        exploring, learning, investigating, neural, deep, bridging, methods, hybrid, networks, balancing
> Table 4: ... Overlap is 2/10 ( learning , networks ). Interdisciplinary titles center on cross-domain combinations; Horizontal titles prioritize methodological exploration verbs.
> ```

> `L935–980`（G.4 参与度 vs 语义新颖性 + 锚定相似度）：
> ```
> Table 5: Participation and semantic novelty comparison. Leader-Led Collaborators produce fewer words per turn and drastically fewer total words per session, yet their per-turn semantic novelty is statistically indistinguishable from Horizontal agents ( p=0.068 , Cohen's d=-0.069 ). This indicates that Collaborators are active but semantically anchored to the Leader's framing.
> ...
> Configuration | Mean Cosine Sim to Anchor | Std
> Leader-Led    | 0.627 | 0.181
> Horizontal    | 0.441 | 0.211
> Table 6: Per-turn cosine similarity to the session anchor (Leader's Round 1 for Leader-Led; first speaker's Round 1 for Horizontal). Leader-Led turns remain substantially closer to the anchor framing (difference = + 0.19), consistent with semantic gravitational anchoring.
> ```
> ⇒ ★ **"参与度相同但语义被锚定"** —— 这是"权威塌缩 ≠ 有人偷懒"的证据。

---

### A.15 ★ Appendix E — 子组拓扑流程（PDF p.16 / 会议 p.266；p.18 / 会议 p.268）

> `L656–659`：
> ```
> Appendix E Randomized Subgroup Text Collaboration
> This section describes the randomized subgroup collaboration procedure in its purely textual variant. In this setting, each agent produces visible natural language utterances, without any latent state being passed between calls. A designated leader agent subsequently reads a subset of the discussion and synthesizes a final answer.
> High-level overview
> Given a question or topic, a fixed set of agents participate in a multi-round discussion. In each round, the full set of agents is randomly partitioned into disjoint subgroups of a specified size. Within every subgroup, agents speak in sequence, with each utterance visible only to members of the same subgroup. After a pre-defined number of rounds, a leader agent reads a transcript of the most recent subgroup discussions together with a short summary of the corresponding round structure, and produces the final response.
> ```
> `L727–732`（产物清单 + ★ "no latent representations"）：
> ```
> the leader's final textual answer, which serves as the method's prediction;
> a detailed set of agent-level traces for all non-leader agents and the leader, each trace containing the agent role, the round in which the utterance was produced, the full prompt used to query the model, and the resulting output;
> a summary of the subgroup structure in each round.
> In this "text-only" variant, no latent representations are maintained across calls, and the leader bases its decision solely on visible natural language content from a small number of recent rounds. This makes the method a clean baseline for comparing purely textual collaboration with alternative designs that share richer latent state between agents.
> ```

---

### A.16 ★ Appendix M — GPT-5.1 复现（PDF p.32–33 / 会议 p.282–283）

> `L1896`：
> *"To test whether the topology ranking observed for DeepSeek-V3 (Section 5 ) generalizes across models, we computed per-topic Vendi Scores for GPT-5.1 under three communication topologies (**Standard, NGT, Recursive**), all using the Interdisciplinary persona at N=3 , with 50 proposals per topic across 20 ICLR topics."*

> **Table 25（PDF p.33）**：
> ```
> Topology | Mean Vendi | Std | 95% CI
> Recursive | 2.823 | 0.238 | ± 0.104
> NGT      | 2.526 | 0.253 | ± 0.111
> Standard | 1.659 | 0.185 | ± 0.081
> Table 25: Per-topic Vendi Scores for GPT-5.1 across three topologies ( n=20 topics each).
> ```

> `L1915–1922`：
> ```
> One-way ANOVA: F(2,57)=137.88 , p<0.0001 , \eta^{2}=0.829 (very large effect). All pairwise contrasts are significant after Bonferroni correction:
> • Recursive vs. Standard: \Delta=+1.16 , d=5.47 , p<0.0001
> • NGT vs. Standard: \Delta=+0.87 , d=3.90 , p<0.0001
> • Recursive vs. NGT: \Delta=+0.30 , d=1.21 , p=0.002
> The topology ranking (Recursive > NGT > Standard) is identical to DeepSeek-V3, confirming cross-model robustness. Notably, the topology effect is stronger for GPT-5.1 ( \eta^{2}=0.829 ) than for DeepSeek-V3 ( \eta^{2}=0.544 ), suggesting that more aligned models benefit more from structural interventions.
> ```

> `L1924–1933`（M.2 跨模型）：
> ```
> Under identical conditions (Standard topology, Interdisciplinary persona, N=3 ), DeepSeek-V3 produces substantially higher per-topic diversity than GPT-5.1:
> • DeepSeek-V3: mean Vendi = 3.092 ± 0.097
> • GPT-5.1: mean Vendi = 1.659 ± 0.081
> • Independent t-test: t=21.49 , p<0.0001 , Cohen's d=6.97
> • GPT-5.1 produces 46% lower per-topic diversity
> This gap is consistent across all 20 topics (DeepSeek-V3 higher in 20/20 cases), ruling out topic-specific artifacts.
> ```
> ⚠️⚠️ **★ 这就是"Standard vs Recursive"标签混乱的现场**：Appendix M 把 `Recursive` 与 `Standard` 当**两个不同的格**报 3 组 ANOVA，但：
> - 仓库 `ASSETS.md` 的「Simulation config ↔ paper condition」表**只列 9 个 config**，GPT-5.1 只有 `gpt5_1_interdisciplinary_recursive.yaml` 与 `gpt5_1_interdisciplinary_ngt.yaml` ⇒ **没有 "Standard" config**；
> - 仓库 `analysis/figures/fig10_topology_dynamics.py:22` 把 **`"Standard"` 映射到 `./data/extracted_proposals/extracted_proposals_recursive`** ⇒ **Fig 10 的 "Standard" 与 Appendix I 的 "Recursive" 是同一份数据**。
> ⇒ **"Recursive(2.823) ≫ Standard(1.659)" 这条旗舰对比在 shipped 代码里没有对应实现。**

---

### A.17 ★ Appendix K — ★ "flat 拓扑下 Senior 反而更多样"（PDF p.28 / 会议 p.278；p.31 / 会议 p.281）

> `L1700`（Table 18，逐字）：
> *"**Tone is not a significant factor ( p=0.172 , \eta^{2}=0.023 ). Identity has a small but significant effect ( p=0.031 , \eta^{2}=0.058 ), but notably in the opposite direction from the original experiments: under flat topology, Senior personas produce higher diversity than Junior personas.**"*
> `L1662`（Table 17）：*"All four conditions produce similar diversity levels (range: 2.873–3.092), with no dramatic collapse in any cell."*
> `L1644`（Table 16 设计）：*"All four conditions use DeepSeek-V3 with temperature 0.7 , group size N{=}3 , and flat peer-to-peer topology (Standard, no leader). Only the persona identity label and prompt tone vary."*

---

### A.18 Limitations / §6.1 — 自认的局限（PDF p.10 / 会议 p.260）

> `L158`：
> *"Third, our diversity evaluation relies on **embedding-based and lexical metrics**, supplemented by human validation on a limited scale. Although agreement with expert judgments is high, **no single metric can fully capture the nuanced notion of creativity or novelty in ideation**. Quality scores are obtained via an LLM-as-Judge protocol (DeepSeek-V3, temperature 0) and therefore **inherit the standard biases of automatic judges; our human evaluation (Appendix B ) validates the diversity axis only.** Our metrics are intended to diagnose relative differences between collaboration modes rather than to provide absolute measures of creativity."*

> `L127`（§6.1 "The Weight of Cognitive Alignment"，★ 对我们"权威结构 + 稠密上游"最刺耳的一句）：
> *"In heavily aligned models like GPT-5.1, the model's prior appears dominant: even under the persona and topology variations we test (Appendices M and J ), these agents tend to concentrate in the same narrow consensus region. This is consistent with the finding that **diversity collapse can be driven by alignment priors alone, producing a floor that the structural interventions do not fully breach.**"*

> `L125`（§6.1 "How Intelligence and Topology Interact"，★ **Alignment-Topology Mismatch**）：
> *"For reasoning-heavy models (e.g., o1-mini), the same structural coupling may instead act as a hindrance, a pattern consistent with the reading that their high-level internal deliberation is fragile and that **dense external coordination (the blue dashed arrow) produces a synchronization effect that reduces the unique perspectives each agent could have contributed**."*

---

## B. `MAS_Diversity` 仓库（代码逐字）

### B.1 ★ `analysis/metrics/compute_vendi_and_order.py` — Vendi 怎么算（**确认用 embedding**）

> `compute_vendi_and_order.py:33–45`：
> ```python
> def vendi_score(emb: np.ndarray) -> float:
>     try:
>         from vendi_score import vendi
>     except ImportError:
>         raise ImportError("vendi_score package not found. Please install it with: pip install vendi-score")
>
>     n = emb.shape[0]
>     if n == 0:
>         return float("nan")
>
>     K = emb @ emb.T
>     K = (K + K.T) / 2.0
>     score = vendi.score_K(K)
>     return float(score)
> ```

> `compute_vendi_and_order.py:72–74`（★ **embedding 来源**）：
> ```python
> def get_openai_embeddings(texts, model="text-embedding-3-large", batch_size=50):
>     """
>     Fetch embeddings from OpenAI API in batches.
>     """
> ```

> `compute_vendi_and_order.py:52–61`（order parameter φ = 1-φ 的分子）：
> ```python
> def order_parameter(emb: np.ndarray) -> float:
>     if emb.shape[0] == 0:
>         return float("nan")
>     v_avg = emb.mean(axis=0)
>     nrm = np.linalg.norm(v_avg) + 1e-12
>     v_avg = v_avg / nrm
>     dots = emb @ v_avg
>     return float(dots.mean())
> ```

> `compute_vendi_and_order.py:64–72`（PCD）：
> ```python
> def pairwise_cosine_distance(emb: np.ndarray) -> float:
>     n = emb.shape[0]
>     if n < 2:
>         return float("nan")
>     cosine_similarities = emb @ emb.T
>     triu_indices = np.triu_indices(n, k=1)
>     similarities = cosine_similarities[triu_indices]
>     distances = 1.0 - similarities
>     return float(distances.mean())
> ```

> ⚠️ **`compute_vendi_and_order.py:143–160`（★ legend 映射，证明 "Standard" ≡ "Recursive"）**：
> ```python
> legend_names = {
>     "leader": "Leader-Led Collaboration",       # Echo Chamber (Red)
>     "x": "Interdisciplinary Collaboration",     # High Value (Purple)
>     "mix": "Vertical Collaboration (Ours)",     # Balanced (Green)
>     "young": "Horizontal Collaboration",        # Divergent (Cyan)
>     "rec": "Naive Collaboration",               # Baseline (Grey)
> }
> ```

### B.2 ★★ `analysis/metrics/compute_vendi_extended.py` — ★ **三个非 embedding 度量的完整实现**（§3 的落码底稿）

> `compute_vendi_extended.py:21–41`（词表常量）：
> ```python
> _TOKEN_PATTERN = re.compile(r"[a-z]+")  # fast + stable
>
> # Basic stopwords (avoid nltk download overhead)
> _STOPWORDS = {
>     "a", "an", "and", "are", "as", "at", "be", "but", "by",
>     "for", "from", "has", "have", "had", "he", "her", "him",
>     "i", "in", "is", "it", "its", "may", "might", "more", "most",
>     "of", "on", "or", "our", "ours", "she", "so", "some", "such",
>     "than", "that", "the", "their", "them", "these", "they", "this",
>     "to", "was", "we", "were", "what", "when", "which", "who", "will",
>     "with", "would", "you", "your",
> }
>
> # Optional: remove common academic boilerplate words to reduce template effects
> # (You can tune this list or auto-mine from corpus later.)
> _BOILERPLATE = {
>     "paper", "work", "study", "approach", "method", "methods", "framework",
>     "model", "models", "propose", "proposed", "novel", "new",
>     "evaluate", "evaluation", "experiment", "experiments", "results", "performance",
>     "dataset", "datasets", "task", "tasks", "analysis", "system", "systems",
> }
> ```

> `compute_vendi_extended.py:291–300`（`get_content_words`）：
> ```python
> def get_content_words(text: str):
>     """
>     Content-only token stream:
>     - lower
>     - regex tokenize [a-z]+
>     - remove stopwords + optional boilerplate
>     """
>     text = text.lower()
>     toks = _TOKEN_PATTERN.findall(text)
>     return [t for t in toks if t not in _STOPWORDS and t not in _BOILERPLATE]
> ```

> `compute_vendi_extended.py:303–332`（★ **全局 IDF**）：
> ```python
> def build_global_content_ngram_idf(all_datasets, n=3):
>     """
>     Build global IDF across ALL datasets (full corpus) to ensure comparability.
>     Streaming DF accumulation (doesn't store all texts).
>     """
>     df = defaultdict(int)
>     valid_docs = 0
>     for dpath in all_datasets:
>         proposals = load_dataset(dpath)
>         if not proposals:
>             continue
>         texts = [t for _, t in proposals]
>         for text in texts:
>             words = get_content_words(text)
>             if len(words) < n:
>                 continue
>             valid_docs += 1
>             grams = set(tuple(words[i:i+n]) for i in range(len(words) - n + 1))
>             for g in grams:
>                 df[g] += 1
>     if valid_docs == 0:
>         return {}, 0
>     # Non-negative smoothed IDF: log((1+N)/(1+df))
>     idf = {g: float(math.log((1.0 + valid_docs) / (1.0 + dfg))) for g, dfg in df.items()}
>     return idf, valid_docs
> ```

> `compute_vendi_extended.py:335–361`（★ **W-D-3 本体**）：
> ```python
> def content_only_wdistinct_n(texts, idf, n=3):
>     """
>     WDistinct-n over content-only tokens using GLOBAL IDF table.
>     WDistinct-n = sum_idf(unique ngrams) / sum_idf(all ngrams)
>     """
>     all_ngrams = []
>     for text in texts:
>         words = get_content_words(text)
>         if len(words) < n:
>             continue
>         all_ngrams.extend(tuple(words[i:i+n]) for i in range(len(words) - n + 1))
>     if not all_ngrams:
>         return float("nan")
>     sum_idf_all = 0.0
>     sum_idf_unique = 0.0
>     seen = set()
>     for g in all_ngrams:
>         w = idf.get(g, 0.0)
>         sum_idf_all += w
>         if g not in seen:
>             sum_idf_unique += w
>             seen.add(g)
>     return float(sum_idf_unique / (sum_idf_all + 1e-12))
> ```

> `compute_vendi_extended.py:368–392`（`self_bleu`，★ **论文全文未报数 ⇒ 未验证**）：
> ```python
> def self_bleu(texts):
>     try:
>         from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
>     except ImportError:
>         print("nltk not available, falling back to basic BLEU implementation")
>         return compute_self_bleu_basic(texts)
>     if len(texts) < 2:
>         return float("nan")
>     smoothing = SmoothingFunction().method1
>     bleu_scores = []
>     for i, hypothesis in enumerate(texts):
>         hyp_tokens = hypothesis.split()
>         references = [ref.split() for j, ref in enumerate(texts) if j != i]
>         if not references:
>             continue
>         score = sentence_bleu(references, hyp_tokens, smoothing_function=smoothing)
>         bleu_scores.append(score)
>     if not bleu_scores:
>         return float("nan")
>     return float(np.mean(bleu_scores))
> ```

> `compute_vendi_extended.py:439–454`（`distinct_n`）：
> ```python
> def distinct_n(texts, n=2):
>     if len(texts) == 0:
>         return float("nan")
>     all_ngrams = []
>     for text in texts:
>         tokens = text.split()
>         if len(tokens) < n:
>             continue
>         for i in range(len(tokens) - n + 1):
>             all_ngrams.append(tuple(tokens[i:i+n]))
>     if len(all_ngrams) == 0:
>         return float("nan")
>     return float(len(set(all_ngrams)) / len(all_ngrams))
> ```

### B.3 ★ `analysis/figures/fig10_topology_dynamics.py:20–25` — ★ **"Standard" ≡ `extracted_proposals_recursive` 的行级铁证**

> ```python
> {
>     "Standard": "./data/extracted_proposals/extracted_proposals_recursive",
>     "NGT": "./data/extracted_proposals/extracted_proposals_ngt",
>     "Subgroups": "./data/extracted_proposals/extracted_proposals_subgroup"
> }
> ```
> ⚠️ **这是本文档对 "Standard vs Recursive" 标签混乱的最强证据**：Fig 10 里叫 "Standard" 的那份数据，目录名就是 `extracted_proposals_recursive`。

### B.4 ★ `docs/persona_mapping.md` — persona ↔ 目录后缀

> ```
> | Paper name | Directory suffix | Description |
> |------------|------------------|-------------|
> | Naive | `rec_final` | No role assignment — baseline |
> | Horizontal | `young_final` | Junior peer-to-peer (all first-year PhD) |
> | Vertical | `mix_final` | Hierarchical mix (senior + junior) |
> | Leader-Led | `leader_experience2` | One designated leader assigns directions |
> | Interdisciplinary | `x_final` | Senior experts from different fields |
> ```
> ⚠️ **注意 `rec_final` = Naive**（不是 "Recursive"！）⇒ **目录后缀的 "rec" 指 "recursive 讨论方式"，不是 persona 名** ⇒ 进一步说明 "Recursive" 这个词在仓库里是**拓扑名**、在 persona 表里是**别的东西**。

### B.5 ★ `ASSETS.md` — config ↔ paper condition 对照（★ 证明没有 "Standard" config）

> ```
> | Paper condition | Config file |
> |-----------------|-------------|
> | DSV3 + Naive + Recursive | `simulation/configs/dsv3_naive_recursive.yaml` |
> | DSV3 + Naive + NGT | `simulation/configs/dsv3_naive_ngt.yaml` |
> | DSV3 + Naive + Subgroup | `simulation/configs/dsv3_naive_subgroup.yaml` |
> | DSV3 + Horizontal + Recursive | `simulation/configs/dsv3_horizontal_recursive.yaml` |
> | DSV3 + Interdisciplinary + Recursive | `simulation/configs/dsv3_interdisciplinary_recursive.yaml` |
> | GPT-5.1 + Interdisciplinary + Recursive | `simulation/configs/gpt5_1_interdisciplinary_recursive.yaml` |
> | GPT-5.1 + Interdisciplinary + NGT | `simulation/configs/gpt5_1_interdisciplinary_ngt.yaml` |
> | o1-mini + Horizontal + Recursive | `simulation/configs/o1_mini_horizontal_recursive.yaml` |
> | o1-mini + Horizontal + Subgroup | `simulation/configs/o1_mini_horizontal_subgroup.yaml` |
>
> The 8-way identical standard runner (`run_dynamic_topic.py`) handles Recursive / NGT topologies; Subgroup uses the dedicated `run_dynamic_topic_subgroup.py`. Topology selection is driven by the `rule` field in each config.
> ```
> ⚠️ **9 个 config，三档拓扑（recursive / ngt / subgroup）** ⇒ **没有 "Standard" config**。

### B.6 ★ `simulation/configs/dsv3_horizontal_recursive.yaml` — ★ **Horizontal 的确切做法（§2 的抄写底稿）**

> ```yaml
> name: Early-Career Researchers Only Academic Discussion with AI-Researcher Integration
> environment:
>   env_type: sim-basic
>   max_turns: 5
>   round0_concurrent: false
>   incremental_memory_each_message: true
>   rule:
>     order:      { type: grouped_sequential }
>     visibility: { type: all }
>     selector:   { type: basic }
>     updater:    { type: basic }
>     describer:  { type: basic }
> agents:
>   - name: PhD Student A
>     role_description: A first-year PhD student in AI research with limited research experience in
>       {topic_lower}, bringing fresh curiosity and basic academic foundation to the discussion.
>   # PhD Student B / C 同上
> ```
> ⚠️ **收口 agent 的 role_description 也同步改写**：
> ```yaml
>   - agent_type: tool
>     name: PhD Student A   # 实际 config 里名字是 Participant 1，描述为：
>     role_description: The same first-year PhD student who participated in the discussion, now
>       attempting to synthesize the group's limited but fresh perspectives into a research proposal.
> ```
> ⇒ ★ **两处权威信号都要改：role_description + agent 名字 + 收口者身份。**

### B.7 ★ `simulation/configs/dsv3_naive_ngt.yaml` — ★ **NGT 的 rule 五字段（§1 的抄写底稿）**

> ```yaml
> name: NGT Collaboration – Early-Career Researchers
> environment:
>   env_type: sim-basic
>   max_turns: 5
>   rule:
>     order:
>       type: ngt
>       leader_idx: 3   # index of Leader; Leader only speaks in final round
>     visibility: { type: ngt }
>     selector:   { type: ngt }
>     updater:    { type: ngt }
>     describer:  { type: ngt }
> ```
> ⚠️ **注意该文件的 `name:` 写的是 "Early-Career Researchers"，但三路 role_description 全是 "A senior AI researcher"** ⇒ **config 里的 `name` 字段是从 horizontal 那边复制过来没改** ⇒ **该文件是 Naive persona × NGT**（见 `ASSETS.md`），**不要被 `name` 误导**。

### B.8 ★ `simulation/configs/dsv3_naive_subgroup.yaml` — Subgroup 的 rule

> ```yaml
> name: Randomized Subgroup Collaboration – Anti-Groupthink
> environment:
>   max_turns: 5
>   rule:
>     order:
>       type: subgroup_random
>       group_sizes: [1, 2, 3, 2]
>       rounds_per_size: 1
>       leader_idx: -1
>       final_leader: true
>       include_leader_in_subgroups: false
>     visibility: { type: subgroup }
>     selector:   { type: ngt }
>     updater:    { type: subgroup }
>     describer:  { type: subgroup }
> ```

### B.9 ★ `analysis/figures/figA1_gpt51_cross_topology.py:61–62, 89–90` — Appendix M 的三条件标签

> ```python
> colors_topo = {'GPT5.1-Standard': '#d62728', 'GPT5.1-NGT': '#ff7f0e', 'GPT5.1-Recursive': '#2ca02c'}
> labels_topo = {'GPT5.1-Standard': 'Standard', 'GPT5.1-NGT': 'NGT', 'GPT5.1-Recursive': 'Recursive'}
> ...
> dsv3_std = dsv3[dsv3['condition'] == 'Standard'].set_index('topic')
> gpt51_std = gpt51[gpt51['condition'] == 'GPT5.1-Standard'].set_index('topic')
> ```
> ⚠️ **这些 CSV（`tsne_code/pertopic_vendi_gpt51_topologies.csv` 等）仓库 README 明示不 ship** ⇒ **Appendix M 的三条件无法从 shipped 代码复现**。

### B.10 `README.md` — 仓库自述的排除项（★ "我们没读到的是什么"的官方依据）

> ```
> ### What's excluded
> To keep the repository lightweight, the following are **not** shipped:
> - Raw proposal `.txt` directories (~10,000 proposals across all configurations)
> - OpenAI / BGE embedding `.pkl` caches
> - LLM-as-judge quality evaluation `.jsonl` caches
> - Aggregated metric CSVs (regenerated from stage 2)
> - LLM-as-judge batch evaluation scripts (paper-specific infrastructure)
> ```
> ⇒ ★ **论文里所有需要真实数据的数字我都没能在真实数据上复算**（与既有 22 号精读一致）。

---

## C. ADHD 项目（三处来源合并）

### C.1 ★★ `src/packs/core.ts` — 15 认知帧逐字（**`UditAkhourii/adhd`**，MIT）

> `src/packs/core.ts:1–109`（**全文件**）：
> ```typescript
> import type { Frame } from "../frames.js";
>
> export const core: Frame[] = [
>   {
>     id: "hardware-eyes",
>     label: "Hardware engineer",
>     prompt:
>       "You think in latency, memory layout, and physical constraints. Re-ask this problem as if it were a hardware/firmware problem. What does the bus topology, the cache, the timing budget tell you?",
>     tags: ["code", "wild"],
>   },
>   {
>     id: "regulator",
>     label: "Regulator / auditor",
>     prompt:
>       "You audit systems for compliance and failure modes. What ideas surface when you ask: what must be provable, traceable, or refusable here?",
>     tags: ["design", "general"],
>   },
>   {
>     id: "ten-year-old",
>     label: "10-year-old",
>     prompt:
>       "You are a curious 10-year-old who has never seen software before. Describe naive but unencumbered approaches. Ignore convention.",
>     tags: ["general", "wild"],
>   },
>   {
>     id: "adversary",
>     label: "Competitor trying to break it",
>     prompt:
>       "You are a hostile competitor or attacker. Generate approaches that exploit, fail, or sabotage the obvious solution. Then invert into ideas.",
>     tags: ["code", "design"],
>   },
>   {
>     id: "biology",
>     label: "Cross-domain: biology",
>     prompt:
>       "Transplant a mechanism from biology — immune systems, neural plasticity, cell signaling, evolution, gut flora — and force-fit it onto this engineering problem.",
>     tags: ["code", "wild"],
>   },
>   {
>     id: "logistics",
>     label: "Cross-domain: logistics / supply chain",
>     prompt:
>       "Steal mechanisms from logistics: queues, batching, just-in-time, hub-and-spoke, returns, last-mile. Apply them literally to this problem.",
>     tags: ["code", "design"],
>   },
>   {
>     id: "game-design",
>     label: "Cross-domain: game design",
>     prompt:
>       "Approach this as a game designer. What are the loops, rewards, friction, save-states, speedrun tricks? Treat the user/system as a player.",
>     tags: ["design", "general"],
>   },
>   {
>     id: "markets",
>     label: "Cross-domain: markets",
>     prompt:
>       "Treat the problem as a market. Who are the buyers, sellers, market-makers? What does an auction, a futures contract, a clearing house look like here?",
>     tags: ["design", "wild"],
>   },
>   {
>     id: "inversion",
>     label: "Inversion",
>     prompt:
>       "Ask the OPPOSITE question. If the goal is X, brainstorm 'how would we guarantee NOT-X' — then negate each answer back into an idea.",
>     tags: ["code", "design", "general"],
>   },
>   {
>     id: "extreme-zero",
>     label: "Extreme: $0 budget, 1 hour",
>     prompt:
>       "You have no money, no team, one hour. What's the crudest version that still does the load-bearing thing? Hacks, hardcoded values, manual loops welcome.",
>     tags: ["code", "general"],
>   },
>   {
>     id: "extreme-infinite",
>     label: "Extreme: infinite budget, 10 years",
>     prompt:
>       "You have infinite compute, infinite engineers, a decade. What does the maximalist version look like? What would only be possible at that scale?",
>     tags: ["design", "wild"],
>   },
>   {
>     id: "remove-assumption",
>     label: "Remove the load-bearing assumption",
>     prompt:
>       "Name the thing everyone treats as fixed in this problem (the framework, the database, the request/response model, the file system, the network). Imagine it's gone. Generate ideas that only exist in that world.",
>     tags: ["code", "design", "wild"],
>   },
>   {
>     id: "speedrunner",
>     label: "Speedrunner",
>     prompt:
>       "You're a speedrunner. Find glitches, skips, out-of-bounds tricks, frame-perfect shortcuts. What's the abusive-but-legal path through this problem?",
>     tags: ["code", "wild"],
>   },
>   {
>     id: "ant-colony",
>     label: "Ant colony / swarm",
>     prompt:
>       "No central planner. Many dumb agents, local rules, pheromone trails. How does the problem solve itself emergently?",
>     tags: ["code", "wild"],
>   },
>   {
>     id: "ops-3am",
>     label: "On-call at 3am",
>     prompt:
>       "You're the on-call engineer woken at 3am when this thing breaks. What design would let you not get paged? What's the runbook-shaped solution?",
>     tags: ["code", "design"],
>   },
> ];
> ```

### C.2 ★★ `src/frames.ts` — ★ `selectFrames` 逐字 + 两个缺陷（§5.2 的抄写底稿）

> `src/frames.ts:24–32`（★ **无 PRNG**）：
> ```typescript
> // Fisher-Yates shuffle — uniform distribution, unlike sort(() => Math.random() - 0.5).
> function shuffle<T>(arr: T[]): T[] {
>   const a = [...arr];
>   for (let i = a.length - 1; i > 0; i--) {
>     const j = Math.floor(Math.random() * (i + 1));
>     [a[i], a[j]] = [a[j], a[i]];
>   }
>   return a;
> }
> ```

> `src/frames.ts:34–65`（★ **缺陷 ②：会少返回一帧**）：
> ```typescript
> // Pick N frames for a run. Bias toward engineering tags when codeMode is on,
> // but always include at least one wildcard so divergence stays weird.
> export function selectFrames(n: number, codeMode = true, packs = ["core"]): Frame[] {
>   // Without this an empty list pools nothing and the core wild fallback turns
>   // it into a one-frame run.
>   if (packs.length === 0) throw new Error("selectFrames needs at least one pack name");
>   const named = [...new Set(packs)].map((name) => {
>     if (!Object.hasOwn(PACKS, name)) {
>       throw new Error(`Unknown frame pack "${name}". Available packs: ${Object.keys(PACKS).join(", ")}`);
>     }
>     return PACKS[name];
>   });
>   // By id, so a pack that reuses another pack's frame can't put it in a run twice.
>   const unique = (list: Frame[]) => [...new Map(list.map((f) => [f.id, f])).values()];
>   const frames = unique(named.flat());
>   // Narrowed per pack: a pack written for a non-engineering domain may have no
>   // code or design frame, and narrowing it would drop it even when pooled with core.
>   const pool = codeMode
>     ? unique(named.flatMap((p) => {
>         const engineering = p.filter((f) => f.tags.includes("code") || f.tags.includes("design"));
>         return engineering.length > 0 ? engineering : p;
>       }))
>     : frames;
>   const pooledWild = frames.filter((f) => f.tags.includes("wild"));
>   const wild = pooledWild.length > 0 ? pooledWild : FRAMES.filter((f) => f.tags.includes("wild"));
>
>   const shuffled = shuffle(pool);
>   const picked = shuffled.slice(0, Math.max(1, n - 1));      // ← n-1 个
>   const wildPick = wild[Math.floor(Math.random() * wild.length)];
>   if (!picked.find((f) => f.id === wildPick.id)) picked.push(wildPick);   // ← 已在里面就不补
>   return picked.slice(0, n);                                     // ← 于是返回 n-1
> }
> ```
> **我实测复刻（逐行照搬上面逻辑，n=5, codeMode=true, 200,000 次）**：
> ```
> pool size (codeMode) : 14
> wild pool size       : 8
> returned-length histogram over 200000 runs (n=5 requested): { '4': 50150, '5': 149850 }
> P(returned 4) = 25.07%
> distinct frame-sets observed in 20k runs: 3823
> ```
> ⇒ **25.07% 的运行静默只跑 4 帧**（理论 7/8 × 4/14 = 0.25，模拟吻合）。

> `src/frames.ts:7–16`（`Frame` 类型 —— ★ 我们的中文版要保留 `tags` 语义）：
> ```typescript
> export type Frame = {
>   id: string;
>   label: string;
>   // The system prompt fragment injected into the divergent branch.
>   // Written as an instruction: "you are X, generate ideas as X would."
>   prompt: string;
>   // Engineering domain tag — used by the orchestrator to bias frame
>   // selection when the problem looks code-shaped.
>   tags: ("code" | "design" | "general" | "wild")[];
> };
> ```

### C.3 ★★ `src/engine.ts` — ★ 权重 + `SCORE_SYSTEM` + trap 用法（§5.3 的抄写底稿）

> `src/engine.ts:71–89`（★ **SCORE_SYSTEM 全文逐字**）：
> ```typescript
> const SCORE_SYSTEM = `You are in CONVERGENT mode. You are now the critic.
> Score each idea on three axes 0-10:
> - novelty: distance from the obvious default solution
> - viability: could this actually ship / work in practice
> - fit: how directly it addresses the stated problem
>
> Tell the truth about weaknesses — don't soften the substance. But the
> critic's job is to produce two symmetric signals, not just one:
>
> - "strength": required for every idea, even weak ones. The single most
>   concrete thing this idea gets right that a competing idea doesn't.
> - "trap" (optional): if the idea looks attractive but has a hidden cost
>   (false economy, won't scale, premature abstraction), name it as a
>   specific, actionable heads-up — e.g. "solid for a prototype, breaks
>   past 10k concurrent users" — not a dismissal like "bad idea." The
>   fact stays the fact; only the framing changes: information you can
>   act on, not a verdict on the idea's worth.
>
> Output JSON only.`;
> ```

> `src/engine.ts:192–199`（用户提示词 + JSON schema）：
> ```typescript
>   const userPrompt = `PROBLEM:
> ${problem}
>
> IDEAS (id → text):
> ${ideas.map((i) => `${i.id} :: ${i.text}`).join("\n")}
>
> Score each. Output JSON array:
> [{"id":"...","novelty":0-10,"viability":0-10,"fit":0-10,"strength":"...","trap":"... or omit"}]`;
> ```

> `src/engine.ts:214–228`（★ **权重 .35/.4/.25 的确切位置**）：
> ```typescript
>   const out = new Map<string, Score>();
>   for (const r of rows) {
>     // Weight: novelty matters because the whole point is escaping the obvious,
>     // but viability is the gatekeeper — a brilliant unshippable idea is a trap.
>     const total = r.novelty * 0.35 + r.viability * 0.4 + r.fit * 0.25;    // ← :218
>     out.set(r.id, {
>       novelty: r.novelty,
>       viability: r.viability,
>       fit: r.fit,
>       total,
>       trap: r.trap,
>       strength: r.strength,
>     });
>   }
> ```

> `src/engine.ts:404–408`（★ **trap 是硬性排除 + 单独成段**）：
> ```typescript
>   // Shortlist: top by total, excluding traps. Traps reported separately.
>   const traps = allIdeas.filter((i) => i.score?.trap);
>   const shortlist = allIdeas
>     .filter((i) => i.score && !i.score.trap)
>     .sort((a, b) => (b.score!.total - a.score!.total));
> ```

> `src/engine.ts:36–40`（schema 的 trap 字段）：
> ```typescript
>     novelty: z.number().min(0).max(10),
>     viability: z.number().min(0).max(10),
>     fit: z.number().min(0).max(10),
>     trap: z.string().optional(),
> ```

> `src/types.ts:12–19`（`Score` 类型逐字）：
> ```typescript
> export type Score = {
>   novelty: number;     // 0-10, away from the obvious
>   viability: number;   // 0-10, could actually ship
>   fit: number;         // 0-10, addresses the stated problem
>   total: number;       // weighted
>   trap?: string;       // if it looks good but is a trap, why
>   strength?: string;   // the one concrete thing this idea gets right
> };
> ```

> `src/render.ts:60–64`（★ trap 段的标题逐字）：
> ```typescript
>   if (r.traps.length > 0) {
>     out.push(bold("Traps (watch-outs, not verdicts)"));
>     for (const t of r.traps) {
>       ...
>       out.push(`    ${dim(t.score?.trap ?? "")}`);
> ```

### C.4 ★★ `documentation/frames.md:31` + 站点 `concepts/frames` — ★ **文档说了假话（3 处同源）**

> `documentation/frames.md:31`：
> *"**Selection is deterministic per-seed so runs are reproducible.**"*

> 站点 `https://adhd.mintlify.site/concepts/frames.md`（"How frames are selected"）：
> *"Selection is **deterministic per-seed** so runs are reproducible — but varies across sessions so the same problem produces different candidate sets when re-run."*
> ⚠️ **自相矛盾**：前半句说可复现，后半句说每次都变。

> 站点 `https://adhd.mintlify.site/concepts/how-it-works.md` + `documentation/how-it-works.md:63`：
> *"Frame selection (see `src/frames.ts`) is **deterministic per-seed** with a `codeMode` bias"*

> ⚠️ **三处全部与源码矛盾**：`src/frames.ts:28` / `:62` 用裸 `Math.random()`，`src/types.ts:50-68` 的 `RunOptions` **没有 `seed` 字段**。
> ⚠️ 另：仓库 `documentation/frames.md` 的帧表**只有 14 行**（把 `$0 budget / infinite budget` 合并成一行），而源码是 **15 帧**（`extreme-zero` / `extreme-infinite` 是两条）⇒ **文档少列一帧**。

### C.5 ★ `bench/problems.json` — 6 道题逐字（§6 的 DEV 集参考）

> ```json
> [
>   { "id": "lru-100ms", "category": "systems",
>     "problem": "Design a thread-safe LRU cache that survives process restart without losing more than the last 100ms of writes." },
>   { "id": "llm-hang-cli", "category": "ux/reliability",
>     "problem": "We have a CLI that calls an LLM and the LLM sometimes hangs for 90 seconds before responding. Design the right retry/timeout/UX strategy." },
>   { "id": "rate-limit-leader", "category": "distsys",
>     "problem": "Design a rate limiter that stays correct across a leader election. Existing leader had counters in memory; new leader takes over with no warning." },
>   { "id": "fuzzy-bug", "category": "debugging",
>     "problem": "0.1% of API requests time out intermittently. No stack trace, no obvious pattern, no recent deploy. How should we investigate? Generate hypothesis classes, not specific fixes." },
>   { "id": "monolith-split", "category": "refactor",
>     "problem": "We have a 200k-line Rails monolith. The team wants to split it. Generate strategies for how to decompose it — by domain, data, team, churn, or otherwise." },
>   { "id": "naming-feature-flag", "category": "naming",
>     "problem": "Generate names for a feature-flag service that supports gradual rollout, kill-switches, and per-tenant overrides. The name should signal control and reversibility." }
> ]
> ```

### C.6 ★ `bench/judge.ts` + `bench/run-evals.ts` — ★ **盲评协议（§6 的抄写底稿）**

> `bench/judge.ts:1–11`（逐字）：
> ```
> // LLM-as-judge.
> //
> // We can't ground-truth ideation, so we use a separate critic pass to score
> // two outputs (ADHD vs baseline) on the dimensions that matter for *open-ended*
> // design work: breadth, novelty, trap detection, actionability, and overall
> // usefulness to a builder.
> //
> // To reduce same-model bias: the judge runs with a system prompt that asks
> // for adversarial reading ("be a skeptical staff engineer"), and it sees BOTH
> // outputs blinded (labelled A/B in random order per problem) so positional bias
> // is balanced across runs.
> ```

> `bench/judge.ts:25–39`（判官 system prompt 逐字）：
> ```typescript
> const JUDGE_SYSTEM = `You are a skeptical staff engineer reviewing two ideation outputs (A and B)
> for the same problem. Your job is to score them on the dimensions of open-ended
> design work, not on prose polish.
>
> You do NOT know which system produced which output. Score on substance only.
>
> Rubric (each dimension 0-10):
> - breadth: range of structurally DISTINCT angles. 10 minor variations of one idea = low breadth.
> - novelty: how many ideas are non-obvious-but-viable. The obvious textbook answer is NOT novel.
> - trap_detection: does it name ideas that look good but are traps, with reasons?
> - actionability: does the top recommendation have a sketch, named risk, and first concrete step?
> - builder_usefulness: if you were the engineer who had to ship, which is more useful to you?
>
> Then declare overall_winner: "A", "B", or "tie".
> Output JSON only. No prose preamble.`;
> ```

> `bench/run-evals.ts:87–90`（★ **盲评顺序随机，但无种子**）：
> ```typescript
>     // Randomize A/B order so the judge's positional bias is balanced.
>     const swapped = Math.random() < 0.5;
>     const outA = swapped ? baselineOutput : adhdOutput;
>     const outB = swapped ? adhdOutput : baselineOutput;
> ```
> ⇒ ★ **`swapped` 标志被落盘**（`bench/run-evals.ts:95–103` 的 `rows.push({... swapped, ...})`）⇒ **这一条我们照抄**（ADHD 做对了）。

> `bench/run-evals.ts:33–45`（★ **ADHD 臂的运行参数**）：
> ```typescript
> async function adhd(problem: string): Promise<string> {
>   const result = await run({
>     problem,
>     framesPerRun: 5,
>     ideasPerFrame: 6,
>     topK: 3,
>     concurrency: 4,
>     codeMode: true,
>     onEvent: () => {},
>   });
>   // Strip ANSI for the judge — color codes are noise to the model.
>   return renderText(result).replace(/\x1b\[[0-9;]*m/g, "");
> }
> ```

### C.7 ★ `EVALS.md` — 6 题读数（逐字，§6 的噪声地板讨论需要）

> ```
> Run: 2026-05-25T11:28:55.772Z · problems: 6
> **Headline:** ADHD 5W / 1L / 0T vs single-shot baseline.
>
> | Dimension | ADHD | Baseline | Δ |
> | breadth | 9.00 | 4.83 | +4.17 |
> | novelty | 7.83 | 2.67 | +5.17 |
> | trap_detection | 9.50 | 1.83 | +7.67 |
> | actionability | 9.50 | 6.50 | +3.00 |
> | builder_usefulness | 7.67 | 6.83 | +0.83 |
> ```
> ⚠️ **6 题 × 每题 1 次 = n=1，零重复、零显著性、零噪声地板、零 seed** ⇒ **这些 Δ 全部没有不确定度**。

### C.8 ★ 预印本 `adhdstack.github.io` — 关键段逐字（★ 帧的定位 + 隔离不变式 + 自认局限）

> **§Method / Phase 1（Diverge）**：
> *"Given a problem p , we select N frames F 1 , …, F N from a library of **15** (e.g. hardware engineer , regulator , biology , logistics , game design , markets , inversion , $0 budget , remove the load-bearing assumption , speedrunner , ant colony , 3am on-call ). For each frame we make a fresh, parallel LLM call with: a generator-only system prompt that forbids evaluation, ranking, or hedging, the problem statement, the frame's vantage prompt …, a JSON-only output instruction asking for k short, distinct candidate ideas."*
> *"**Critically, the N calls do not share context. The regulator branch never reads what the speedrunner branch produced. Anchoring is eliminated by construction, not by prompting.**"*
> *"The frame library is tagged ( code , design , general , wild ). When codeMode is enabled (the default) we bias selection toward engineering-relevant tags but always reserve one slot for a wild frame to preserve range."*

> **§Method / Why the separations matter（★ 三个"承重不变量"，可直接抄成我们的架构条款）**：
> *"Three invariants are load-bearing. Removing any of them collapses ADHD into a method that already exists."*
> *"**Isolation, not search.** CoT and ToT branches share a context window; by step 4 the model has anchored on what it wrote in steps 1–3. ADHD's N branches are N distinct LLM calls with no shared history. **Anchoring is mechanically impossible across branches.**"*
> *"**Frames, not next-step variation.** ToT typically varies the next move within a search problem. ADHD varies the entire vantage point of the generator . It is not "what step comes next from here"; it is "re-ask the whole question as if you were an immune system". This produces structurally different ideas, not nearby ones, which is the prerequisite for surfacing cross-domain transplants."*
> *"**Generator–critic split is mechanical.** The generator system prompt forbids evaluation. The critic system prompt forbids generation. They are different calls. A single model evaluating as it generates is exactly the "critic strangles the generator" failure the original skill warns against."*

> **§Method-acting and persona prompting（★ 对我们最关键的一段：帧 ≠ 权威 persona）**：
> *"A separate strand of work assigns the model a role — "you are an expert X" — to bias output style or domain knowledge. **ADHD's cognitive frames superficially resemble this but differ in intent: frames are not chosen for expertise but for structural distortion . The "10-year-old" frame is not asked to be correct; it is asked to ignore convention . The "speedrunner" frame is not asked to be authoritative; it is asked to look for glitches . Frames are vantage operators, not credentials.**"*

> **§Discussion and limitations（★ 自认局限，逐字）**：
> *"**Same-model judging.** Our LLM-as-judge runs on the same model family as the generator. We mitigated with adversarial system prompts and randomised A/B order, but we cannot exclude familiarity bias entirely. A useful follow-up is cross-model judging (e.g. judge with a different vendor's model) and human ratings on a held-out subset."*
> *"**Small problem set.** Six problems is enough to see consistent direction but not enough to make strong quantitative claims."*
> *"**Frame library is hand-authored.** The 15 frames in the current library reflect our judgement about which vantage points produce distinct outputs on engineering problems. **A frame can fail silently — producing paraphrases of another frame's ideas — without the harness catching it.** Frame-quality evaluation is future work."*
> *"**Confounded by deepen quality.** The actionability delta is partly explained by the deepen pass, which gives ADHD a structural advantage (sketch + risk + first step) that the baseline's free-form prose does not enforce. A fairer ablation would equip the baseline with the same output schema; we expect ADHD's lead to shrink on this dimension but not on breadth, novelty, or trap detection."*

> **§Cost（★ 成本模型）**：
> *"A default ADHD run uses **≈10 LLM calls (5 divergence + 1 score + 1 cluster + 3 deepen)** versus 1 for the baseline. Wall-clock latency at concurrency 4 is typically 30–90 s. We frame this honestly: ADHD is for decision points, not inner loops."*
> ⚠️ **"5 divergence" 在 25% 的运行里实际是 4**（见 C.2）。

### C.9 ★ `SOURCE-SPEC.md` — 原始 skill 规格（★ "发散/收敛" 二阶段的出处）

> `SOURCE-SPEC.md:9`：
> *"This skill widens the search before it narrows. The default failure mode in idea generation is **premature convergence**: latching onto the first plausible answer and polishing it. That produces competent, forgettable output. The goal here is to generate a genuinely broad and weird candidate set first, then converge with judgment. **Breadth is cheap; a missed idea is expensive.**"*

> `SOURCE-SPEC.md:15`：
> *"Run two distinct phases. Keep them separate. **Mixing them is what kills idea quality, because the critic strangles the generator.**"*

> `SOURCE-SPEC.md:17`（Phase 1）：
> *"**Phase 1 — Diverge** (generate, no judging). Produce a large set of candidates fast. Suspend evaluation entirely. Bad, obvious, and absurd ideas are all welcome here because they seed better ones. Aim for quantity and variety, not quality. **Do not stop at the first 3 — the first 3 are almost always the obvious ones everyone already thought of.** Push past the obvious into the awkward middle where the interesting ideas live."*

> `SOURCE-SPEC.md:19`（Phase 2）：
> *"**Phase 2 — Converge** (select with judgment). Now bring the critic back. Cluster the candidates, kill the dead ones, and surface the few worth pursuing. Be honest about tradeoffs. This is where builder-judgment applies: which of these could actually ship, which is most non-obvious-but-viable, which is a trap."*

> `SOURCE-SPEC.md:25–32`（★ **六种"技术"，与 15 帧一一对应**）：
> ```
> Don't free-associate randomly — that drifts toward the familiar. Use structured prompts to push attention into corners it wouldn't naturally go. Pick a few per session; don't grind through all of them.
> - **Vary the frame.** Re-ask the question from radically different vantage points: how would a hardware person solve this software problem? A regulator? A 10-year-old? A competitor trying to make it fail?
> - **Cross-domain transplant.** Take the mechanism from a distant field and force-fit it. Biology, logistics, game design, immune systems, ant colonies, futures markets, speedrunning.
> - **Invert it.** Ask the opposite question. Instead of "how do we get users to stay," ask "how would we drive every user away" — then negate the answers.
> - **Push to extremes.** $0 budget / infinite budget. 1 hour / 10 years. Extremes break the anchoring on the reasonable middle.
> - **Remove the load-bearing assumption.** Name the thing everyone treats as fixed and ask what becomes possible if it's gone.
> - **Combine two unrelated candidates.** Take ideas #3 and #11 from the list and ask what their hybrid looks like.
> ```

> `SOURCE-SPEC.md:41–46`（★ **反模式清单**）：
> ```
> - Convergence disguised as divergence (10 minor variations of one idea).
> - Weird-for-weird's-sake with no convergence.
> - Walls of equally-weighted prose hiding the good ideas.
> - Refusing to commit. After diverging, take a position.
> ```

### C.10 ★ `ADOPTERS.md` — ★ 我们要抄哪一条（★ 三条最有价值的采纳记录）

> `ADOPTERS.md:22`（★ **godplans —— 直接抄它的"基线对照臂 + 独立审计门"**）：
> *"**godplans** — Shipped v1.8.0 turning its self-audit into an independent audit gate (separate scoring pass, isolated context) and adding a **no-skill baseline control arm** to its eval harness, inspired by ADHD's generator/critic split — while explicitly rejecting the novelty-scoring axis and randomized frame selection as unsuited to its own goals."*（PR #8）

> `ADOPTERS.md:24`（★ **multi —— 跨模型族分配帧 = 论文 §4.1 "权威 vs 专家" 的另一种解法**）：
> *"**multi** — Cross-model port of ADHD as a Claude Code plugin skill — the diverge→converge loop, but **each frame is handed to a different model family** (Claude sub-agent, OpenAI Codex, a cheap third via OpenCode/OpenRouter), so ideas diverge by frame and by model priors at once. Generator/critic split kept … plus an **explicit confound note so a run is never reported back as a model comparison**."*（`/multi:adhd`）

> `ADOPTERS.md:21`（★ **godaudits —— 抄它的"独立反驳 + 归因/限制追踪"**）：
> *"**godaudits** — Shipped v2.11.0 adopting measurement and provenance discipline from an ADHD review — an **independent refutation pass (`refute plan`/`apply`), severity-aware recall metrics, and attribution/limits tracking on eval results**."*（PR #13）

> `ADOPTERS.md:20`（★ **mythify —— 抄它的"陷阱条款"**）：
> *"**mythify** — Added trap-clause and alternatives guidance to its analysis prompt packet after evaluating ADHD's divergent-frames-then-critic pattern — surfaces "the one that looks good but isn't, and why" before a plan is committed to."*（PR #18）

> `ADOPTERS.md:19`（★ **wtfismyrepo —— 抄它的"确定性层 → 帧"管道**）：
> *"**wtfismyrepo** — Uses ADHD as the explanation engine for codebase onboarding. The **deterministic layer** (import-graph PageRank, git-churn fragility, GitHub PR/issue signals) produces an analysis object that is formatted as an ADHD `problem` + `context`. The ADHD diverge→score→cluster→deepen loop then generates onboarding angles across 12 codebase-specific frames ( `new-grad` , `archeologist` , `security-researcher` , `on-call-at-3am` , `refactorer` , `inversion` , …), **scores them for fit to the developer's level + goal, prunes traps**, and deepens the non-obvious pick into a full walkthrough."*

### C.11 ★ 站点 `adhd.mintlify.site/concepts/frames.md` — ★ **"Frames vs personas"（§2.3 的直接依据）**

> *"A frame is a **vantage operator**: a system-prompt payload that re-poses the entire problem from a different cognitive position. **Not a persona, not a domain expert** — a deliberate distortion that forces the generator into a corner it would not naturally drift toward."*

> *"**Frames vs personas** — Frames are **not** personas. Persona-prompting research (e.g. *"you are John, a 34-year-old engineer"*) studies simulated identities; some findings report that **ordinary attribute-personas outperform curated expert-personas**. ADHD frames are neither — they are *vantage operators* ( *"you think in latency, memory layout, and physical constraints"* ) that **re-pose the problem**, not identities the model role-plays. The mechanisms are different, so persona findings do not map directly onto frame selection."*（issue #17）"

> *"**How to author your own frame** — A frame is ~5 lines in `src/frames.ts` … A good frame passes at least two of: **Distinct vocabulary** — concepts no existing frame uses …; **Distinct posture** — adversarial vs constructive vs naive vs maximalist. Not just a different domain saying the same thing.; **Reproducible distortion** — consistently surfaces ideas the other frames don't."*

---

## D. ⚠️ 未读到 / 不可核（不脑补）

| 项 | 状态 |
|---|---|
| 论文附录 **G.2 完整 transcript**（4 个 mini-case） | ❌ 未逐条读（只读了 G.1 规则 / G.3 统计 / G.4 统计） |
| 论文附录 **O 的全部提示词模板** | ❌ 只读了 O 的 "Proposal Generation Format Prompt" 与 N 的 "Stance Classification Prompt" |
| 论文 **10,000 条原始 proposal** / 所有聚合 CSV | ❌ 仓库 README 明示不 ship（见 B.10）⇒ **论文侧所有指标数值均未能独立复算** |
| 论文附录 **L（温度）** 逐主题数字 | ⚠️ 只读了结论（既有 22 号精读已记录 T=0.3/0.7/1.0 的 per-topic 值），本次未逐格复算 |
| **`bench/results.json`** 的 6 条完整 transcript | ❌ 未取（只读了 `EVALS.md` 逐题裁决表 + `bench/judge.ts` + `bench/run-evals.ts`） |
| 论文附录 **N.2 / O** 的完整 agent 提示词 | ❌ 只取到 stance judge 与 proposal format 两段 |
| **"Standard" 是否为第四种拓扑** | ❌ **论文没说清**；我补了行级铁证（B.3：`fig10_topology_dynamics.py:22` 把 "Standard" 映射到 `extracted_proposals_recursive`）⇒ **Fig 10 的 "Standard" ≡ Appendix I 的 "Recursive"**，而 Appendix M 仍把二者当两格报 ANOVA。**标为未解决。** |
| 我**没有跑任何模型** | ⚠️ 唯一执行的是 `selectFrames` 的**逻辑复刻**（C.2），其余全部为逐字引用 |
| arXiv PDF | ⚠️ 本沙盒下载出的 PDF **xref 损坏**（`pdftotext` 报 "Couldn't find trailer dictionary"）⇒ 页码一律以 ACL Anthology PDF 为准 |

---

## E. 引用与来源

| 来源 | 标识 | 读取方式 |
|---|---|---|
| 论文 PDF（56 页） | `https://aclanthology.org/2026.findings-acl.13.pdf`（4,557,455 B） | `curl` + `pdftotext`（**无 `-layout`**，双栏下才不串行） |
| 论文全文（ar5iv） | `https://ar5iv.labs.arxiv.org/html/2604.18005`（945,502 B） | `curl` → 自写 HTML→text（2,565 行） |
| 论文元数据 | arXiv `2604.18005` / DOI `10.18653/v1/2026.findings-acl.13` / 会议页 251–306 | ACL PDF 首页 |
| `MAS_Diversity` | `https://github.com/Xtra-Computing/MAS_Diversity`（MIT） | GitHub contents API（base64）+ `raw.githubusercontent.com` |
| `adhd` | `https://github.com/UditAkhourii/adhd`（MIT） | 同上 |
| ADHD 文档站 | `https://adhd.mintlify.site`（`/llms.txt`、`/concepts/frames.md`、`/concepts/how-it-works.md`、`/evals/methodology.md`） | `curl` |
| ADHD 预印本 | `https://adhdstack.github.io`（v0.1, 2026-05-25, MIT） | `curl` → HTML→text |

**访问日期**：2026-10-21（UTC）｜ **本文件所有 `L<n>` 行号基于我抽取的 `paper.txt`（2,565 行），可按同一流程复现。**
