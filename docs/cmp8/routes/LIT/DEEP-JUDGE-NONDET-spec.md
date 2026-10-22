# DEEP-JUDGE-NONDET-spec

> **任务**：查"LLM-as-judge 在 `temperature=0` 下仍不可复现"这一**我们自己实测发现的现象**是否有前人先例。
> **产出**：`/workspace/lab/routes/LIT/DEEP-JUDGE-NONDET-spec.md`（本文）+ `/workspace/lab/routes/LIT/DEEP-JUDGE-NONDET-quotes.md`（逐字摘录）
> **检索日**：2026-10-22
> **工具**：`web_fetch` 在本沙盒完全失效 ⇒ 全程 `bash` + `curl`（arXiv API / arXiv HTML / arXiv PDF + `pdftotext` / thinkingmachines.ai / link.springer.com） + `web_search`
> **原始素材**：`/workspace/lab/routes/LIT/_priorart_src/ft/*.txt`（已抓正文）· `ft/*.log`（抓取完整性日志）· `fetch_arxiv_html.sh`（断点续传抓取器）

---

## §0 一句话结论

> ### 这是**已知现象**，而且**已被反复量化**；但我们提出的那条具体归因——"**噪声来自启用 adaptive thinking 的模型**"——**在我检索到的全部文献里未找到直接先例**。
>
> 更准确地说，三件事必须拆开说：
> 1. **"temp=0 ⇒ 可复现"这个假设被明确质疑过，且已有 4 组独立量化**（Thinking Machines 的批不变性、Atil et al. 的 TAR@N、Yuan et al. 的数值精度分解、Kumar et al. 的 C/φ/A/T 审计）⇒ **"已知且已量化"**。
> 2. **"同一判官重复打分不一致"已有正式指标**（CALM 的 CR、Shi et al. 的 RS、Zhao et al. 的 CR、Kumar et al. 的 C）⇒ **"已知且已量化"**。
> 3. **"噪声来自 thinking/reasoning 模式"这个自变量，据我所检索的文献没有任何一篇做过 thinking on/off 对照**；而 **Yuan et al. 给出了间接的机制支持**，**Thinking Machines 的 80-unique 实验明确跑的是 "(non-thinking mode)"**（即他们那条最著名的证据**恰好不覆盖** thinking 模式），**Kumar et al. 明确写着 reasoning models 因 API 不支持 temperature 参数而被排除出温度扫描** ⇒ **"已知但未量化（在我们这个归因上）"**。
>
> ★ **但有一个已被充分证实的竞争解释，比我们的归因适用面更广**：**批不变性 / 浮点归约序**（batch-invariance）。它对**所有**模型成立、与 thinking 无关，且在托管 API 上**不可控**。我们的读数目前**不能**排除它。详见 §2-D 与 §4-4。
>
> ★ **所以我们的论文贡献不能写"我们发现了 LLM 判官不可复现"**（会被 2610.12083 / 2604.16790 / 2408.04667 直接打掉）。能写的只有两条：
> **(A) 在 Agent 架构评测场景下把"判官读数不可复现 + 读数塌到 0"这一失败模式量化到 agent 评测流水线**（本轮检索中，该场景的既有工作只做到"多判官 + 报判官间一致性 0.905"这一层，**没有人报"同一判官的重测一致性"**）；**(B) 补上 thinking on/off 的对照实验**——这是目前文献里最明显的空洞，且是我们的设计天然能填的。

---

## §1 逐条证据表

> 阅读深度标记：**✅FULL** = 抓到并通读 arXiv HTML/PDF 正文全文；**✅HTML** = 抓到 arXiv HTML 正文（经 `web_search` 渲染）；**✅BLOG** = 抓取官方 blog 全文；**⚠️ABS** = **只读到摘要/题录，正文未读**（不做任何外推）。
> 逐字摘录全文见 `DEEP-JUDGE-NONDET-quotes.md`。

| # | 类型 | 真实标题 | 作者 | venue | arXiv id / DOI | 日期 | 读 | 关键量化（带绝对分母） |
|:-:|---|---|---|---|---|---|:-:|---|
| **E1** | 论文 | **All Verdicts are Not Equal: Rethinking LLM Judge Reliability** | Kumar, Rathore, Moitra（PayPal AI） | AACL IJCNLP (Main) 2026（作者自报） | **2610.12083** | 2026-10-08 | ✅FULL | 6 判官 × 4 数据集 × 5 格式 × 2 序 × 3 温度 × **每格 10 次重复**；**"7–17% 的裁决在完全相同的重复中改变"**；换序最多 **98% 翻转**；最差格 **C=100% 但 T=2.0%**；Ts=0 最低单格一致性 **C=75.5%**（GPT-5.2 CoT-XML @JudgeBench，100 题） |
| **E2** | 工程帖 | **Defeating Nondeterminism in LLM Inference** | Horace He + Thinking Machines Lab | Thinking Machines Lab blog | — | 2025-09-10 | ✅BLOG | Qwen3-235B-A22B-Instruct-2507，**temp=0，1000 次**，prompt "Tell me about Richard Feynman"**（non-thinking mode）** ⇒ **80 个唯一补全**，最常见者出现 78 次；**前 102 token 完全一致，第 103 token 分叉**（992 "Queens, New York" vs 8 "New York City"）；上 batch-invariant kernels 后 **1000/1000 逐位相同**；性能 26s → 55s → 42s |
| **E3** | 论文 | **Understanding and Mitigating Numerical Sources of Nondeterminism in LLM Inference**（⚠️v1 标题为 *Give Me FP32 or Give Me Death? Challenges and Solutions for Reproducible Reasoning*） | Yuan, Li, Ding, Xie, Li, Zhao, Wan, Shi, Hu, Liu（Rice / UMN / Adobe） | arXiv（cs.CL） | **2506.09501**（v2） | 2025-06-11 / v2 2025-10-24 | ✅FULL | 4 模型（**2 reasoning + 2 non-reasoning**）× 5 benchmark × **12 种 runtime 配置**（GPU 型号/数量/batch size）；greedy + bf16 下 **R1-Distill-Qwen-7B 准确率标准差最高 9.15%（AIME'24）**、**输出长度标准差最高 9.15%**、**长度差最大 9,000 token**；FP32 近乎零方差；"**reasoning model 的 top-2 token 概率间隙常常极小**" |
| **E4** | 论文 | **Non-Determinism of "Deterministic" LLM Settings**（⚠️v1 标题为 *LLM Stability: A detailed analysis with some surprises*） | Atil, Aykent, Chittams, Fu, Passonneau, Radcliffe, Rajagopal, Sloan, Tudrej, Ture, Wu, Xu, Baldwin（Penn State + Comcast AI Tech） | arXiv（cs.CL） | **2408.04667**（v5） | 2024-08-06 / v5 2025-04-02 | ✅FULL | **5 个"配置为确定性"的 LLM × 8 任务 × 10 次运行 × {zero-shot, few-shot}**；**准确率波动最高 15%**；**最好-最差性能差最高 70%**；新指标 **TARr@N（原始串全同率）/ TARa@N（解析后答案全同率）**；"**没有哪个 LLM 在所有任务上稳定复现准确率，更不用说给出完全相同的输出串**" |
| **E5** | 论文 | **Bias in the Loop: Auditing LLM-as-a-Judge for Software Engineering** | Zhao, Esmaeili, Fard（UBC） | arXiv（cs.SE，ACM 模板） | **2604.16790** | 2026-04-18 | ✅FULL | **CR = (1/\|D\|) Σ 𝕀(ŷ^(i,1)=ŷ^(i,2))**，两次独立跑、固定 temperature/top-p/max tokens、每次新会话、清缓存；Qwen3-4B no-bias **CR 83.60%（CodeGen）/ 91.41%（CodeRepair）/ 70.56%（TestGen）**；Qwen2.5-Coder-3B no-bias **CR 58.57 / 65.75 / 50.36（≈随机）**；**Answer rate：Qwen3-4B 仅 44.37%（CodeGen 48.90 / CodeRepair 41.92 / TestGen 40.55），Qwen2.5-Coder-3B 99.16%**；"**这些不是更差的裁决，而是根本不进入准确率计算的『非裁决』**" |
| **E6** | 论文 | **Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge**（CALM 框架） | Ye, Wang, Huang, Chen, Zhang, Moniz, Gao, Geyer, Huang, Chen, Chawla, Zhang（PKU / IBM / HKU） | arXiv | **2410.02736**（v2） | 2024-10-03 | ✅FULL | **CR / RR 指标的原始出处**：CR = (1/\|D\|) Σ 𝕀(y^i = y_rand^i)，RR = (1/\|D\|) Σ 𝕀(y^i = ŷ^i)；12 类 bias；⚠️ **其超参是 temperature = 0.7**（不是 0） |
| **E7** | 论文 | **Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge** | Shi, Ma, Liang, Diao, Ma, Vosoughi（Dartmouth） | AACL-IJCNLP 2025（作者自报） | **2406.07791**（v9） | 2024-06-12 | ✅HTML | 首次定义 **Repetition Stability (RS)** = (1/N) Σ_j (1/n_j) max_k \|C_k^j\|（"同一 query 重复多次的最常见选择占比"）；**15 判官 × 2 数据集 × 22 任务，>150,000 次评估**；**RS：Gemini-1.5-flash 1.00±0.00 / GPT-4o 1.00±0.02 / Claude-3.5-Sonnet 0.96±0.07 / Llama-2-7B 0.83±0.15 / Llama-2-13B 0.45±0.22 / Llama-3-8B 0.16±0.18**；⚠️ **其 RS 实验 temperature = 1** |
| **E8** | 论文（综述） | **A Survey on LLM-as-a-Judge** | Gu, Jiang, Shi, Tan, Zhai, Xu, Li, Shen, Ma, Liu, Wang, Gao, Ni, Guo（IDEA / 中科院计算所 / 帝国理工 / 人大） | arXiv（后发表于 *The Innovation*） | **2411.15594** | 2024-11-23 | ✅FULL | 综述"如何构建可靠的 LLM-as-a-Judge"；**其自评实验把 temperature 设为 0 来"降低随机性影响"**；bias 矩阵含 **Empty Content 一栏（n=24）**；明确指出**闭源 judge"可复现性低"**（API 背后模型会变） |
| **E9** | 论文 | **ISD-Agent-Bench: A Comprehensive Benchmark for Evaluating LLM-based Instructional Design Agents** | Jeon, Kim, Son, Lee, Jeong, Lee（Upstage / Opentutorials / IU Bloomington / Korea Univ.） | arXiv（cs.SE） | **2602.10620** | 2026-02-11 | ✅FULL | ★ **最接近我们场景**：Agent 架构 benchmark；**多判官协议（GPT-4o-mini + Gemini-2.5-flash-lite 跨供应商）+ 中位数聚合**；**5,183 次评估的判官间一致性：均值 0.905，SD 0.084，min/max 0.293/1.000，Excellent(≥0.9) 63.3%、Low(<0.5) 0.3%**；判官偏差 ±0.060 分 |
| **E10** | 论文 | **From issue titles to requirements: an empirical study of large language models and prompt engineering strategies** | Paiva, Canedo, Rocha Filho（Univ. Brasília / UFBA） | **Requirements Engineering 31, 7 (2026)**（Springer） | DOI **10.1007/s00766-026-00462-z** | 2026-05-26 | ✅FULL | 判官 = Qwen QwQ-32B，**900 条 requirement**；**Krippendorff's α (ordinal) = 0.150–0.394**（5 名人类评分者之间）；**人类↔判官 二次加权 Cohen's κ_w 均值 0.286(Unambiguity)–0.372(Singularity)，个体区间 0.094–0.488**；**±1 分一致率 84%/96%/72%，精确一致仅 34–42%**；**把 "LLM Non-Determinism" 显式列为内效度威胁**；同时断言判官"提供 **perfect consistency**"（**与自身威胁陈述矛盾，且被我们的读数反驳**） |
| **E11** | 论文 | **The Good, The Bad, and The Greedy: Evaluation of LLMs Should Not Ignore Non-Determinism** | Song, Wang, Li, Lin | arXiv | **2407.10457** | 2024-07-15 | ⚠️ABS | 摘要级：评测"通常只看单个输出"而忽视非确定性；greedy 通常优于 sampling；**对齐可降低 sampling 方差**；best-of-N 可让小模型追平 GPT-4-Turbo |
| **E12** | 预印本 | **Generalizability Theory for LLM-as-Evaluator Reliability: Univariate and Multivariate Variance Decomposition Across Models, Prompts, and Temperatures in Text Classification** | Liu, Jin（Takeda Development Center Americas） | SSRN preprint **6432598**（DOI 10.2139/ssrn.6432598） | 6432598 | 2026-03-17 | ⚠️ABS | ★ **唯一把 temperature 当作 G-theory facet 做方差分解的工作**：**64,800 次观测**，全交叉 4 facet（evaluator / prompt type / **temperature** / seed）；**item 难度占单变量总方差 66.5–88.5%**；**temperature 贡献"effectively zero"**；D-study：全设计 **Eρ² = 0.940–0.988** vs 单判官单提示词基线 **0.678–0.889**；"**判官间一致性始终高于 LLM–人一致性**" |
| **E13** | 论文 | **LLMs Cannot Reliably Judge (Yet?): A Comprehensive Assessment on the Robustness of LLM-as-a-Judge** | Li, Xu, Wang, Gong, Chen, Zhang, Wang, Lam, Ji | arXiv | **2506.09443**（v3） | 2025-06-11 | ⚠️ABS | 摘要级：RobustJudge 框架，**15 种攻击 × 8 种防御 × 13 个模型**；"**提示模板设计与模型选择对判官鲁棒性的影响此前很少被探索，其真实部署表现基本未被验证**" |
| **E14** | 论文（综述） | **Agent-as-a-Judge** | You, Cai, Zhang, Xu, Liu, Yu, Li, Li | arXiv | **2601.05111** | 2026-01-08 | ⚠️ABS | 摘要级：从 LLM-as-Judge 转向 Agent-as-Judge 的首份综述；指出 LLM 判官"**shallow single-pass reasoning**、无法对照真实观测验证"等可靠性约束 |
| **E15** | 工程实现 | **batch-invariant-ops**（Thinking Machines Lab）+ **vLLM / SGLang 确定性模式** | Thinking Machines Lab / vLLM Project / SGLang | GitHub + 官方 docs | `thinking-machines-lab/batch-invariant-ops` | 2025-09 起 | ✅BLOG | batch-invariant kernels 使 **1000/1000 逐位相同**；vLLM `VLLM_BATCH_INVARIANT=1`（需 H100/H200/B100/B200） |

**旁证（非学术，作为"社区共识已被传播"的证据，不作机制依据）**：`community.openai.com/t/defeating-nondeterminism-in-llm-inference`、`llmwatch.com/p/eli5-defeating-nondeterminism-in`、`huelv.com`（Towards Data Science 的 token-flip 公式推导，引用了 TML 的 Feynman 计数）、`cloudai.pt`（引用 2506.09501 的 9% / 9000 token 数）、`baristalabs.io`、`wpnews.pro`（结构化输出 ≠ 确定性，引 2408.04667）。

---

## §2 每条证据**支持 / 不支持**我们的归因

我们的归因有四个分句，逐一判：

> **我们的原话**：*噪声来自启用 adaptive thinking 的模型；**不是**"多步判定任务本身不确定"、**不是**"厂商差异"、**不是**"代码问题"。*

### A. "噪声来自启用 adaptive thinking 的模型"

| 证据 | 立场 | 理由（带原文） |
|---|:-:|---|
| **E3 (2506.09501)** | 🟢 **间接支持（最有力的一条）** | 原文："**This issue is especially pronounced in reasoning models, where minor rounding differences in early tokens can cascade into divergent chains of thought**"；且 Table 4 显示 reasoning model 的输出长度标准差（bf16/AIME'24：**9.15%**）远高于 non-reasoning（Qwen2.5-7B-Instruct：**1.71%**）；并给出机制："**We observe the token probability gap are often minimal in reasoning models**" ⇒ **CoT 越长，token 翻转越容易级联** —— 与我们的"thinking 开启 ⇒ 路径分叉 ⇒ 判官读数跳变"机制**同构**。⚠️ 但 E3 的自变量是**硬件/精度/batch**，不是"thinking 开关"；且其 reasoning model 是蒸馏 R1（CoT 固定生成），不是"adaptive thinking（由模型自己决定要不要想）"。 |
| **E2 (TML)** | 🟡 **划界，不是支持** | TML 跑 1000 次得 80 个唯一补全，**但实验明确标注 "(non-thinking mode)"** ⇒ 这条最著名的"temp=0 也不可复现"的证据**恰恰不覆盖 thinking 模式**。⇒ **文献里没有任何一条能替我们回答"thinking 模式下不可复现的幅度是多少"**。 |
| **E1 (2610.12083)** | 🟡 **划界** | 原文："Ts = 0 (all 6 judges), Ts = 0.5, and Ts = 1.0 (**4 judges; reasoning models excluded as public API does not support the temperature parameter**)"，Appendix A 再写一次"GPT-5.2 and Gemini-2.5-Pro are **excluded** because their public APIs do not expose a temperature parameter" ⇒ **两大 reasoning 判官被排除出温度扫描**。而且它对"reasoning 判官在 Ts=0 的 C"有读数（GPT-5.2 Direct @MT-Bench C=89.3 等），但**因为其 Ts=0 对 reasoning 判官可能并非真的 temp=0**（API 忽略该参数），这个读数**不能**用来支撑或反驳我们的 thinking 假设。 |
| **E12 (SSRN 6432598)** | 🔴 **对我们不利** | 原文："**temperature contributing effectively zero**"，且方差主要来自 "item-by-evaluator interaction" ⇒ 在他们的实验里，**温度这一 facet 几乎不解释任何方差**。⚠️ 他们的 "temperature" 是采样温度，不是"是否开启思考"；但这条至少说明"**把噪声归因到某个可调参数**"这种思路本身有先例且结果相反。**我们必须在论文里正面处理这条。** |
| **E6 (CALM)** | 🔴 **警示** | CALM 用 **temperature = 0.7**（"to ensure stable output quality and strong reproducibility"）来量化判官可靠性 ⇒ 既有文献在"测判官可靠性"时**根本没有用 temp=0** ⇒ 我们用 temp=0 做判官审计是一个**未覆盖的实验设置**，这也意味着我们的读数**无法与 CALM/E5/E7 的数字直接对齐**。 |
| **E4 (2408.04667)** | 🟡 **间接支持（弱）** | 稳定性"varies based on task"、且厂商差异不主导 ⇒ 与"噪声有结构、不是随机"一致；但它**没有**测 thinking 开关。 |

**⇒ A 的结论**：**归因本身在文献中无直接先例**（🟢 已检索范围内）。**E3 提供了同构的机制解释**（长 CoT 放大微小扰动），**E2/E1 划出了文献没做过的边界**（non-thinking / reasoning 判官被排除）。**但我们目前只有 2 个判官 × 2 组读数序列 × 1 道题**，**强度远不足以宣称"机制结论"**。**必须补**：thinking off 对照组 + 至少 5–10 道题 + 多判官（否则 2610.12083 的 "reliability is item-specific" 一句就会打掉我们）。

### B. "不是多步判定任务本身不确定"

| 证据 | 立场 | 理由 |
|---|:-:|---|
| **我们自己的对照** | 🟢 **成立（但 n 很小）** | "2+3 等于几" × 3 次 → 3/3 完全一致；而同一判官、同一答案、同一 prompt 的多步判定 × 3 次 → 读数跳 3。**这两组的自变量是"任务复杂度"，其余（模型/参数/判官提示词）保持不变** ⇒ 我们已经在自己的实验里排除了 B。 |
| **E1 (2610.12083)** | 🟡 **需限定** | E1 的 C 是**在固定题目上重复 10 次**测的（不是跨题目），所以它测的正是"重测噪声"而非"任务难度"；同时 E1 报告**可靠性是 item-specific**（"reliability is item-specific rather than model-level"）⇒ **难度确实是分层因素**，但那是在**跨题目比较**时；在**同题重测**层面，我们的对照设计正好把它分离掉了。 |
| **E4 (2408.04667)** | 🟡 **支持"难度会加剧不稳定"，但支持的是别的机制** | "Stability varies based on task"、TARa@10 仍"up to 15%" ⇒ **任务难度确实调制稳定性**。⇒ **在我们的论文里必须写清楚：B 说的是"跨任务方差"，我们的实验说的是"同题重测方差"，两者不可混。** |
| **E7 (RS)** | 🟢 **支持我们的实验设计** | RS 的定义前提就是"先确认同一 query 重复多次的稳定性，否则位置偏差分析无意义"（"A high RS is particularly important as a prerequisite for meaningful computations of PC and PF"）⇒ **先做同题重测、再谈别的，是既有文献公认的顺序**。 |

**⇒ B 的结论**：**在我们的实验设置下成立**（自变量单一、其余固定）。**但它对"跨任务比较"不成立**——E4/E1 都显示难度/题目是方差的主要来源之一。**表述纪律**：不要写"多步判定任务本身不确定"这个大话，要写"**在同题、同判官、同参数的条件下重测，读数仍跳变**"。

### C. "不是厂商差异"

| 证据 | 立场 | 理由 |
|---|:-:|---|
| **E4 (2408.04667)** | 🟢 **支持** | 5 个跨厂商模型（gpt3.5 / gpt4o / llama8b / llama70b / mixtral8-7b），**"没有哪个 LLM 在所有任务上稳定复现"** ⇒ 不存在"某厂商坏"的模式。 |
| **E7 (RS)** | 🟢 **强支持** | 同一批 15 个判官里，**RS 从 0.16（Llama-3-8B）到 1.00（Gemini-1.5-flash / GPT-4o）** ⇒ 决定性变量是**判官个体与配置**，不是厂商。 |
| **E5 (2604.16790)** | 🟢 **支持** | **Qwen3-4B answer rate 44.37% vs Qwen2.5-Coder-3B 99.16%**（同厂商！）⇒ **同厂商内差 55 个百分点**，厂商远不如"是否针对判官任务训练过"重要。 |
| **E1 (2610.12083)** | 🟢 **支持** | "**no model dominates uniformly**"（Figure 5 描述）；"reliability is **item-specific** rather than model-level" ⇒ 厂商级标签不成立。 |
| **E12 (SSRN)** | 🟢 **支持** | "**inter-model agreement consistently exceeded LLM–human agreement**" + item 难度占方差 66.5–88.5% ⇒ 主要方差源是**题目**，不是模型/厂商。 |
| **我们自己的数据** | 🟢 **支持** | 同一个 OpenRouter 通道下，MiniMax 波动 3、grok-4.3 波动 0–1 ⇒ 差异在**模型/模式**层，不在"厂商"层（严格说 grok-4.3 也走 OpenRouter ⇒ 通道一致，差异只能来自模型或模式）。 |

**⇒ C 的结论**：**成立，且文献强力支持**。可以写成："噪声不由供应商决定，而由**判官个体 + 判官模式（是否 thinking）+ 题目**决定"（E1 的 "item-specific" + E7 的 RS 离散度 + E5 的同厂商大差距）。

### D. "不是代码问题" —— ⚠️ **这一句最危险，必须重写**

| 证据 | 立场 | 理由 |
|---|:-:|---|
| **E2 (TML)** | 🔴 **我们可能说错了一半** | TML 证明在**自托管 vLLM/SGLang** 上，根因是**批不变性**（kernel 的归约序随 batch size 变），**不是**"并发+浮点"那种老生常谈，也不是代码 bug ⇒ 这是一个**基础设施层的真实机制**，不是"代码写错了"。 |
| **E2 (TML) 的托管推论** | 🔴 **对我们不利** | TML 明说"**LLM APIs are still not deterministic in practice**"、自托管 vLLM/SGLang 也一样 ⇒ **在托管 API 上，batch size 我们不可控 ⇒ temp=0 本来就不保证一致**，这与 thinking 无关。 |
| **E3 (2506.09501)** | 🔴 **对我们不利** | 根因是"浮点非结合性 + 有限精度"，**跨硬件/跨 batch size/跨 GPU 版本**都会变；BF16 下 FP32 能救 ⇒ 同样与 thinking 无关（thinking 只是**放大器**，不是**根因**）。 |
| **E5 (2604.16790)** | 🟢 **支持"不是我们的代码"** | 他们把可控的代码侧变量全控住了：固定 temperature/top-p/max tokens、每次新会话避免上下文携带、清缓存重发完整 prompt ⇒ **CR 仍只有 50.36–91.41%** ⇒ 残余噪声不是调用代码能消掉的。 |
| **E10 (Paiva et al.)** | 🟢 **支持"不是代码问题"** | 把 "LLM Non-Determinism" 列为**内效度威胁**（与"输入质量混杂"并列）⇒ 既有文献也把残余非确定性归给 API/底层优化，而不是研究者代码。 |
| **E8 (Gu et al. 综述)** | 🟡 **补一条真·代码问题** | "closed-source LLM-as-a-Judge **leads to low reproducibility due to potential changes in models behind the API**" ⇒ **模型版本漂移**是托管 API 侧的真实代码/配置风险（我们的读数若跨时间复现需锁版本）。 |

**⇒ D 的结论（必须改写）**：
- ✅ **"不是我们的代码 bug"** —— 成立（E5 的控制清单 + E10 的威胁归因）。
- ❌ **"不是数值/基础设施层面的系统性噪声"** —— **不成立**。**批不变性（E2）与浮点精度（E3）是一条已被充分证实、且与 thinking 无关的竞争解释**。
- ★ **这恰好暴露了我们实验设计的价值点**：我们手上有 **thinking 开关**这个自变量，**E2/E3 从未在 thinking 开关上做过对照**（E2 明确是 non-thinking mode）。**只要我们补上 "同判官、同答案、同参数、thinking off" 这一组**，就能把"批不变性底噪"与"thinking 增量"分离开 —— 这才是我们论文真正能站住的贡献。
- ★ **必须写进 limitations**：托管 API 上 batch size 不可控 ⇒ 我们的读数是"**批不变性底噪 + thinking 增量**"的**混合**，**不能**把全部波动归给 thinking，除非有 thinking-off 对照且对照也跳。

### E. 附带发现："判官读数塌到 0 / 空"

| 证据 | 立场 | 理由 |
|---|:-:|---|
| **E5 (2604.16790)** | 🟢 **直接先例（"塌成空"）** | Qwen3-4B **answer rate 仅 44.37%**，"**模型一直生成自由文本直到撞到 context 上限，从未产出语法合法的 pred 字段**" ⇒ "这些不是更差的裁决，而是**根本不进入准确率计算的『非裁决』**" ⇒ **判官读数"空/缺"是一种已量化的失效模式**。 |
| **E8 (Gu et al.)** | 🟡 **弱先例** | bias 矩阵含 "**Empty Content**" 一栏（**n=24**），GPT-4-turbo 95.83 / LLaMA3-8B-Instruct 75.00 ⇒ 判官输出"空内容"被作为一种 bias 量化过，但 n 极小。 |
| **E1 (2610.12083)** | 🟡 **邻近** | "**Confidently biased**" 区（高 C + 高 φ ⇒ T→0），最差格 **φ=98%、T=2.0%** ⇒ 判官"自信地给出错误裁决"是已量化的；但那是"错"，不是"空"。 |
| **E7 (RS)** | 🟡 **邻近** | Table 2 有 "**Error**" 列，"Errors arise from judgment failures (e.g., **exceeding context window, not following output format**)"，且"**High error rates and low RS are marked red, rendering further evaluations invalid due to insufficient data**" ⇒ 判官错误率被当作**前置门槛**（超阈值的评测**作废**），这是最接近"必须做一致性/健康度检验才能用"这条规则的表述。 |
| **—** | ❌ **未找到** | **没有找到"pointwise rubric 分数整体塌到 0"作为独立失效模式的文献**。我们观察到的"读数 [3,3,0] / [0,0,3,2]"里，**那个 0 究竟是"合法的 0 分"还是"解析失败被默认成 0"**——这正是 E5 那条 dev.to 工程帖描述的经典坑（"`_safe_parse_json` returned `None`. The scoring loop treated `None` as a valid result, **defaulted the score to 0**, and logged 47 evaluations as failures — all of them wrong, all of them silent."）⇒ **我们必须先区分"合法 0" vs "缺裁决被默认 0"，否则这条观察不可用。** |

---

## §3 我们能**直接引用**的 3–5 条（含它们的量化口径）

> 选标准：① 真实标题/作者/venue/arXiv id 已核；② 量化口径能落到我们的表上；③ 引用它不会让我们的贡献被吞掉。

### ★ 引用 1（必引，构成"已知"基线）— Kumar, Rathore & Moitra (2026), *All Verdicts are Not Equal: Rethinking LLM Judge Reliability*, arXiv:2610.12083, AACL IJCNLP (Main) 2026

- **口径**：`C = Pr(N=1)`（同题重复 10 次给同一裁决的题目比例）、`φ = Pr(P=0)`（换序翻转率）、`A = Pr(R=1)`（对 GT 的准确率）、`T = C·(A − φ/2)`（trustworthy verdict rate）；**6 判官 × 4 数据集 × 5 格式 × 2 序 × 3 温度 × 10 次重复**。
- **可引的数字**：**"7–17% 的裁决在完全相同的重复中改变"**；换序最多 **98%** 翻转；Ts=0 单格最低 **C=75.5%**（GPT-5.2 CoT-XML @JudgeBench，100 题）；最差格 **C=100% 而 T=2.0%**。
- **为什么必引**：它**单独就覆盖了我们 80% 的观察**（temp=0 不可复现 + 重复打分不一致 + 报告规则）。**不引它 = 审稿人第一条就问"你和 arXiv:2610.12083 什么关系"**。
- **它的边界（我们的空间）**：**reasoning 判官因 API 不支持 temperature 参数而被排除出温度扫描**；它只做 pairwise 偏好，**不做 pointwise rubric 分数**；它不做 agent 架构评测。

### ★ 引用 2（构成"机制 + 竞争解释"）— Yuan et al. (2025), *Understanding and Mitigating Numerical Sources of Nondeterminism in LLM Inference*, arXiv:2506.09501(v2)

- **口径**：4 模型（**2 reasoning + 2 non-reasoning**）× 5 benchmark × **12 种 runtime 配置**（GPU 型号/数量/batch size），greedy 解码，BF16/FP16/FP32 三档精度；指标 `Std@Acc`（12 配置下准确率的样本标准差）与 `Avg_Std@Output_Length`。
- **可引的数字**：**R1-Distill-Qwen-7B 在 AIME'24 上 BF16 的准确率标准差 9.15%**、**输出长度标准差 9.15%**、**长度差最高 9,000 token**；non-reasoning 对照 Qwen2.5-7B-Instruct 为 **1.71%**；**"reasoning model 的 top-2 token 概率间隙常常极小"**；FP32 下方差近乎为 0。
- **⚠️ 引用时必须写清 v1/v2 标题不同**（v1 = *Give Me FP32 or Give Me Death?…*）——这是我们历史 50% 记错标题的高危项。
- **为什么引**：它是**唯一把"reasoning/长 CoT"与"噪声放大"直接挂钩的机制证据**，是我们 thinking 归因的**最强外部支撑**；同时它**诚实地告诉我们：根因是数值精度，thinking 只是放大器**。

### ★ 引用 3（构成"读数塌 0/空"的先例）— Zhao, Esmaeili & Fard (2026), *Bias in the Loop: Auditing LLM-as-a-Judge for Software Engineering*, arXiv:2604.16790

- **口径**：`CR = (1/|D|) Σ_{i∈D} 𝕀(ŷ^(i,1) = ŷ^(i,2))`（**两次独立跑**；固定 temperature/top-p/max tokens；每次新会话；清缓存重发）；另报 **Answer rate**（判官是否给出合法裁决）。
- **可引的数字**：Qwen3-4B no-bias **CR 83.60 / 91.41 / 70.56**（CodeGen/CodeRepair/TestGen）；Qwen2.5-Coder-3B no-bias **CR 58.57 / 65.75 / 50.36**（TestGen ≈ 随机）；**Answer rate：Qwen3-4B 44.37% vs Qwen2.5-Coder-3B 99.16%**（同厂商）。
- **为什么引**：它同时覆盖了我们的两个观察（**重复打分不一致** + **读数空/缺**），并给出"**把判官当测量仪器、必须报 CR 方差**"这条规则。

### ★ 引用 4（构成"指标出处 + 我们用哪个口径"）— Ye et al. (2024), *Justice or Prejudice?…* (CALM), arXiv:2410.02736 + Shi et al. (2025), *Judging the Judges…*, arXiv:2406.07791

- **口径**：
  - CALM：**CR**（同条件重测一致率）/ **RR**（注入偏置后的不变率）；⚠️ **CALM 自己用 temperature=0.7**。
  - Shi et al.：**RS = (1/N) Σ_j (1/n_j) max_k |C_k^j|**（**最常见选择占比**，可与随机下界比较）；15 判官、>150,000 次评估、**temperature=1**。
- **可引的数字**：RS 从 **0.16±0.18（Llama-3-8B）到 1.00±0.00（Gemini-1.5-flash）**；"**RS 高是位置偏差分析的前提**"；"**高位置一致性 ≠ 公平**"。
- **为什么引**：我们的"波动 3 / 波动 0–1"这种**幅度式**读数，**必须挂到一个已有的、有下界含义的指标上**（RS 的随机下界由选项数决定；CR 的分母是题数）。**否则我们的数字在审稿人眼里不可比。** ★ **建议我们把 3–4 次重复补到 ≥10 次，然后报 CR / RS。**

### ★ 引用 5（构成"最接近我们场景"）— Jeon et al. (2026), *ISD-Agent-Bench…*, arXiv:2602.10620

- **口径**：多判官（跨供应商 2 个）+ 中位数聚合；报**判官间一致性**（5,183 次评估）。
- **可引的数字**：**均值 0.905 / SD 0.084 / min-max 0.293–1.000**；Excellent(≥0.9) 63.3%、**Low(<0.5) 0.3%**。
- **为什么引**：这是**Agent 架构评测场景**里判官可靠性的**现状水位线**。它**只做"判官 vs 判官"（inter-judge）**，**完全没做"同一判官 vs 自己"（test–retest）** ⇒ ★ **这就是我们的缺口所在，也是我们引它来"划界"的理由。**

---

## §4 我们的读数与它们的可比性

### 4-1 我们自己的读数（重述，供对照）

| 判官 | 读数序列 | 波动幅度 | 备注 |
|---|---|:-:|---|
| `MiniMax-M3.1-Flash-Preview`（启用 adaptive thinking） | **[3, 3, 0]**；**[0, 0, 3, 2]** | **3** | 同一答案、同一判官提示词、同一模型、同一参数，重复判定 3 / 4 次 |
| `x-ai/grok-4.3`（OpenRouter） | **[2,2,3]**；**[3,3,3]** | **0–1** | 同上 |
| MiniMax temp=0 简单提示词（"2+3 等于几"） | 3/3 完全一致 | **0** | 任务复杂度对照 |

### 4-2 逐维可比性矩阵

| 维度 | **我们** | E1 (2610.12083) | E5 (2604.16790) | E7 (RS) | E4 (2408.04667) | E3 (2506.09501) |
|---|---|---|---|---|---|---|
| **读数类型** | pointwise rubric **0–3 分** | pairwise 偏好（A/B） | pairwise 偏好（A/B） | pairwise / listwise 选项 | **QA 答案**（原始串 + 解析答案） | 自由生成（答案 + 长度） |
| **重复次数 N** | **3 / 4** | **10** | **2** | 3（RS 实验） | 10 | 12 种 runtime 配置 |
| **题目数（分母）** | **1–2** | 100/数据集 × 4 | 5,352 总计 | 576(judge,MTBench)+432(judge,DevBench) | 8 任务 × 5 模型 × 10 运行 | 5 benchmark |
| **判官模型** | MiniMax-M3.1-Flash-Preview / grok-4.3 | 6 个 frontier（2 reasoning） | Qwen3-4B / Qwen2.5-Coder-3B / GPT | 15 个（GPT/Claude/Gemini/Llama） | 5 个（gpt3.5/gpt4o/llama8b/llama70b/mixtral8-7b） | 2 reasoning + 2 non-reasoning |
| **温度** | **0** | {0, 0.5, 1.0} | 固定（temperature/top-p/max tokens 固定，**具体值正文未核**） | **1**（RS 实验） | 0（"configured to be deterministic"） | greedy（0 等价） |
| **部署** | **托管 API（MiniMax / OpenRouter）** | 托管 API | 托管 / 自托管 | 托管 API | 托管 API | **自托管 vLLM** |
| **thinking 模式** | **实验自变量（on）** | **reasoning 判官被排除出温度扫描** | 未区分 | 判官含 o1-mini 但未按 thinking 分层 | 未区分 | **CoT 型 reasoning（非 adaptive）** |
| **主指标** | 读数极差（分） | **C / φ / A / T** | **CR** + **Answer rate** | **RS** | **TARr@N / TARa@N** | **Std@Acc / Avg_Std@Output_Length** |

### 4-3 结论：**口径不一致 ⇒ 不能直接比大小**

1. **量纲不同**：我们报的是"分"（0–3 的极差），它们报的是"比率"（C / CR / RS / TAR@N）。**我们的 [3,3,0] 不能说"等于 C=66.7%"** —— 那是把**单题上的极差**当成了**题目集上的一致率**。★ **必须改报 CR/RS。**
2. **分母差 2–3 个数量级**：我们 n=1 题 × 3–4 次；E1 是 100 题 × 10 次 × 120 格；E5 是 5,352 题 × 2 次。⇒ 我们的读数是**点估计，无区间**，任何百分比都会显得比文献更极端。
3. **任务类型不同**：pointwise 0–3 分 vs pairwise A/B。E1 自己的数据就显示 **pairwise 与 rubric 范式的 T 差异巨大**（G-Eval 在 JudgeBench 上 C=68.5 vs Direct 86.0；FLASK 塌到 C=34.8）⇒ **"读数跳 3"在 rubric 尺度上的严重程度，不能用 pairwise 的 C 直接类比。**
4. **温度不可比**：E6 用 0.7、E7 用 1.0、E1 用 {0,0.5,1.0}、E5 用"固定但未公开具体值" ⇒ **只有 E1 的 Ts=0 与我们同温，但它的 reasoning 判官那一格存疑（API 忽略 temperature 参数）。**
5. **部署不可比**：E2/E3 是**自托管**（能控制 batch size、能上 batch-invariant kernels）；**我们是托管 API，batch size 不可控** ⇒ 我们的底噪**必然**包含批不变性噪声（见 §2-D）。
6. ★ **能比的只有两件事**：**(i) 现象存在性**（temp=0 下同题重测会变 —— 已被 4 组独立工作证实，E1/E4/E5/E7）；**(ii) 方向性结论**（"决定性变量是判官个体+模式+题目，不是厂商"——E1/E4/E5/E7/E12 一致）。

### 4-4 ★ 我们读数**能**贡献的增量（不与文献比大小，而是补两个洞）

| 洞 | 文献现状 | 我们能补什么 |
|---|---|---|
| **洞 1：thinking 开关从未被当作自变量** | E2 明写 "(non-thinking mode)"；E1 明写 reasoning 判官"excluded"；E3 用的是固定 CoT 蒸馏模型 | **同判官、同答案、同参数、同部署，唯一变 thinking on/off** ⇒ 分离"批不变性底噪"与"thinking 增量" |
| **洞 2：agent 架构评测只做 inter-judge，没做 test–retest** | E9（ISD-Agent-Bench）只报"判官间一致性 0.905"；E14（Agent-as-a-Judge 综述）只泛泛谈"可靠性受限" | **在 agent 评测流水线里报"同一判官的重测一致性" + "读数塌 0 的发生率"** |
| **洞 3："读数塌到 0"未被作为独立失效模式** | E5 量化了"空/缺"（answer rate 44.37%），但那是"不产出裁决"；**无人量化"rubric 分数整体塌 0"** | 需先区分"合法 0 分"与"缺裁决被默认 0"，再报发生率 |

---

## §5 确实**没有**先例的部分（明确写"未找到"）+ 已跑过的检索路径

### 5-1 明确"未找到"的 4 条

| # | 我们要找的 | 结论 | 边界说明 |
|:-:|---|---|---|
| **N1** | **"自适应思考 / thinking 模式 ⇒ temp=0 下不可复现"**的直接实证（thinking on/off 受控对照） | ❌ **未找到** | 我检索到的所有工作里：E2 明确是 non-thinking mode；E1 明确把 reasoning 判官排除出温度扫描；E3 的 reasoning 是固定 CoT 蒸馏模型；E7 的 o1-mini 未按 thinking 分层。**没有一篇做 thinking 开关对照。** |
| **N2** | **"LLM 判官在 pointwise rubric 上的读数整体塌到 0"**的量化 | ❌ **未找到** | 相邻先例只有 E5 的 answer rate（44.37%，"不产出裁决"）与 E8 的 "Empty Content"（n=24）。**没有"rubric 分数塌 0"的专门量化。** |
| **N3** | **"判官读数波动的幅度 vs 题目难度"**的联合量化 | ❌ **未找到** | E1 说 reliability 是 item-specific、E4 说 stability 随任务变，但**都没有把"同题重测的波动幅度"与"题目难度"放在同一张表里**。 |
| **N4** | **"判官必须选可复现模型 / 必须做一致性检验"作为一条显式准入规则** | 🟡 **部分找到（见下）** | 已有的是**分散的**建议（E1 §6、E5 §5.4、E7 的 RS 前置门槛、E10 的 κ/α 组合 + 非确定性威胁）；**没有**一篇把它写成"**判官选型准入规则**"的正式条文。E7 的 "one needs to select task-specific LLMs whose consistency and fairness are in balance" 是最接近的**选型句**，但它以 RS 为判据且未与 thinking 挂钩。 |

### 5-2 已跑过的检索路径（可辩护清单）

**A. arXiv API（`export.arxiv.org/api/query`）——题录级核对，14 个 id 全部核过**
- `id_list` 直查并解析 title/authors/published/updated/comment：**2610.12083, 2604.16790, 2603.25764, 2602.10620, 2506.09501(→v2), 2408.04667, 2411.15594, 2306.05685, 2407.10457, 2410.02736, 2406.07791, 2506.09443, 2601.05111**
- `search_query=ti:"Judging the Judge"`（因 2406.04409 猜错而改用标题检索）→ 命中 2406.07791
- 全部走了 `abs` 页**提交历史**核对 ⇒ 发现 **2 处标题被改版**（2506.09501 v1/v2、2408.04667 v1/v5），已全部标注
- `api.crossref.org/works/10.1007/s00766-026-00462-z` → 核对 E10 的 title/authors/container/volume/issue/date
- `api.semanticscholar.org` / `api.openalex.org`：本轮**未使用**（沙盒白名单内，但 arXiv+Crossref 已覆盖所需题录；SSRN 走 Crossref/SSRN 摘要兜底）

**B. arXiv 全文抓取（`curl` + 断点续传 + `pdftotext -layout`）——8 篇正文**
`2610.12083`（574 KB）· `2604.16790`（540 KB）· `2602.10620`（370 KB）· `2411.15594`（350 KB）· `2410.02736` · `2506.09501` v1（511 KB）+ **v2（512 KB）** · `2408.04667` **PDF v5（1.23 MB → pdftotext 48 KB）**（该篇 arXiv HTML 只有 v1 摘要页，故改走 PDF）
脚本：`/workspace/lab/routes/LIT/_priorart_src/fetch_arxiv_html.sh`（`curl -C -` 续传 + `content-length` 校验），日志 `ft/*.log`（本轮 6 篇全部一次到位）
解析：`/workspace/lab/routes/LIT/_priorart_src/html2txt.py`（HTML→纯文本，表格单元格保留为 `\t`）

**C. 官方 blog / 期刊页**
- `thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/`（200，102 KB → 38.9 KB 正文）
- `link.springer.com/article/10.1007/s00766-026-00462-z`（200，558 KB → 116 KB 正文）
- `ssrn.com/abstract=6432598` → ❌ **超时（190 字节）**，E12 因此只标 ⚠️ABS
- `github.com` API：可达（本轮未拉到 batch-invariant-ops / llm-stability 的 raw 文件，只用其仓库名与 blog 原文）

**D. `web_search` 检索式（全部实际执行，命中数 6–10/次）**
1. `batch invariance LLM inference determinism OpenAI "not deterministic"` → 命中 TML 原始讨论
2. `reasoning model temperature 0 nondeterminism extended thinking not reproducible` → 命中 TML、UMich 社区帖、SGLang 文档
3. `LLM-as-a-judge repeated runs variance same prompt judge consistency agreement rate` → **命中 2610.12083**（connectedresearchers.top 镜像）
4. `LLM judge test-retest reliability ICC Krippendorff alpha intra-rater agreement` → 命中 RE 领域（E10 全文）
5. `LLM judge parse failure JSON output empty invalid structured output reliability evaluation pipeline` → 命中解析失败工程帖（E5 引用的同类）
6. `"thinking" model "temperature=0" not deterministic same prompt different output reasoning tokens sampling` → 命中 TML/SDL
7. `"thinking mode" OR "extended thinking" LLM same prompt different output non-deterministic reasoning enabled reproducibility` → 命中 TML 二次报道
8. `LLM judge repeated measurement reliability coefficient Krippendorff alpha intraclass correlation generalizability theory G-study evaluator agreement` → **命中 E12 (SSRN 6432598)**
9. `Ye 2024 "Judging the Judge" CALM position bias LLM-as-a-Judge consistency rate arXiv` → 命中 E7 + LLM-as-Judge 安全综述

**E. 明确未做/未成功的**
- ❌ SSRN 全文（超时）⇒ E12 只到摘要
- ❌ E11（2407.10457）、E13（2506.09443）、E14（2601.05111）**正文未读**（只读摘要）
- ❌ 未检索 OpenReview（非白名单）
- ❌ 未检索 ACM DL / IEEE（付费墙；E5、E10 为 arXiv 预印本 / Springer OA，已拿到）
- ⚠️ `web_fetch` 全程不可用，未做 PDF 视觉阅读

---

## §6 给主会话的 5 条行动建议（可直接写进论文）

1. **改写标题级断言**：不要写"我们发现 temp=0 不可复现"（已被 4 组工作证实）。写成"**在 Agent 架构评测场景下，判官读数的**重测**不可复现（此前只报过 inter-judge 一致性）**"。
2. **补 thinking-off 对照**（**唯一能把我们从"复述已知"变成"新增"的一步**）：同判官、同答案、同参数、同部署、**只切 thinking**，各 ≥10 次，并同时报告 **CR 与 RS**（挂到 E6/E7 的既有口径上）。没有这一组，我们的归因就只是"另一个未排除的解释"。
3. **把"波动 3"改写成有分母的指标**：现在 n=1 题 × 3 次，**不可比**。至少 10 题 × 10 次，报 **CR = (1/|D|)Σ𝕀(ŷ1=ŷ2)**（E6/E5 口径）与 **RS**（E7 口径）。E1 的 7–17% 就是这样报的，我们才能被放进同一张表。
4. **区分"合法 0"与"缺裁决被默认 0"**：在解析层埋点（原始输出是否为空/是否有 `pred` 字段/是否撞 context 上限），把 answer rate（E5 口径）一起报。否则"塌到 0"这条观察不可用 —— 工程界已有"静默默认 0"的经典坑记录。
5. **在 limitations 里显式承认批不变性底噪**：托管 API 上 batch size 不可控（E2），我们读到的是"**批不变性底噪 + thinking 增量**"的混合；同时把 E12（temperature 贡献 ≈ 0）作为"另一种可能"一起讨论。★ **把 E3 的标题改版（v1/v2）写进参考文献时务必用 v2 标题**，这是我们历史上 50% 记错标题的高危项。

---

## 附：本轮使用的可复现抓取产物

| 路径 | 内容 |
|---|---|
| `/workspace/lab/routes/LIT/_priorart_src/ft/*.html` | 8 篇 arXiv/期刊 HTML 原文 |
| `/workspace/lab/routes/LIT/_priorart_src/ft/*.txt` | 抽好的纯文本（表格保留 \t，可直接 grep 核对数字） |
| `/workspace/lab/routes/LIT/_priorart_src/ft/2408.04667.pdf` + `.pdf.txt` | Atil et al. v5 全文 PDF 与 `pdftotext -layout` 抽取 |
| `/workspace/lab/routes/LIT/_priorart_src/ft/*.log` | 每个 id 的抓取完整性日志（got vs content-length） |
| `/workspace/lab/routes/LIT/_priorart_src/fetch_arxiv_html.sh` | 断点续传抓取器 |
| `/workspace/lab/routes/LIT/_priorart_src/html2txt.py` | HTML→文本 |
| `/workspace/lab/routes/LIT/DEEP-JUDGE-NONDET-quotes.md` | 逐字摘录（15 条，含阅读深度标记） |
