# DEEP-JUDGE-NONDET — 逐字摘录（Verbatim Quotes）

> 任务：查"LLM-as-judge 在 temperature=0 下仍不可复现"这一**我们自己发现的现象**是否已知。
> 采集时间：2026-10-22（UTC）
> 采集方式：arXiv API（题录核对） + arXiv HTML/PDF 全文抓取（`https://arxiv.org/html/<id>v1`，`curl` + `pdftotext`） + `web_search` 渲染正文 + 官方 blog 抓取。
> **本沙盒 `web_fetch` 工具完全失效**，全部改用 `bash` + `curl` / `web_search`。

---

## 阅读深度标记（重要）

| 标记 | 含义 |
|:-:|---|
| ✅FULL | 抓到并通读 arXiv HTML 或 PDF **正文全文**（含表格数字） |
| ✅HTML | 抓到 arXiv HTML 全文（经 `web_search` 渲染读取） |
| ✅BLOG | 抓取官方 blog 正文全文 |
| ⚠️ABS | **只读到摘要/题录**，正文未读（已明确标注，不做外推） |

---

## E1 ✅FULL — Kumar, Rathore & Moitra (2026) — **最直接的先例**

- 真实标题：**All Verdicts are Not Equal: Rethinking LLM Judge Reliability**
- 作者：Vineet Kumar, Darshita Rathore, Anindya Moitra（均属 PayPal Artificial Intelligence, Bengaluru）
- arXiv id：**2610.12083**（v1, 2026-10-08）
- venue：arXiv comment 自报 **"Accepted at AACL IJCNLP (Main) 2026"**
- 阅读深度：✅FULL（574 KB arXiv HTML，含 Table 1/2/3、Appendix A/C）

### 摘录 1.1 — §1 Introduction（核心断言）

> "This treatment carries an implicit assumption that the verdict is a stable function of the inputs. That re-querying the same judge with the same pair yields the same answer, and that swapping which response is shown first does not change the preferred one. **Both assumptions fail in practice. In our audit, 7–17% of verdicts change across identical replications**, and up to **98% of verdicts flip** when the presentation order of the two candidates is swapped. The most striking case in our data is a judge that returns the same verdict on 100% of repeated calls — maximally deterministic by every single-shot diagnostic in common use — yet whose verdicts agree with ground truth only 51% of the time, barely above chance. **Determinism, in other words, is not reliability.**"

### 摘录 1.2 — Abstract（同样断言）

> "Our empirical analysis reveals severe vulnerabilities: **verdicts change across identical replications at temperature zero**, position-order swaps flip the majority of verdicts on challenging tasks, and the most deterministic judge achieves perfect consistency by trivially repeating incorrect verdicts, agreeing with ground truth only 51% of the time."

### 摘录 1.3 — §3.2 指标定义（可复算口径）

> "For each pair, holding the format f and dataset fixed, we define three Bernoulli indicators:
> N = 1[verdict reproducible across independent runs]
> P = 1[verdict invariant under candidate-order swap]
> R = 1[verdict matches ground truth]
> The corresponding population rates are directly observable from repeated elicitations:
> **C ≔ Pr(N = 1)** (consistency rate)
> 1 − φ ≔ Pr(P = 1) (φ is the position flip rate)
> A ≔ Pr(R = 1) (overall accuracy)"

### 摘录 1.4 — §4.2/§4.3 实验设计（含**对我们归因最关键的一句**）

> "We evaluate 6 models from 4 providers: GPT-5.2 and GPT-4o (OpenAI), Gemini-2.5-Pro and Gemini-2.0-Flash (Google), Claude-Sonnet-4.6 (Anthropic), and Llama-3.3-70B. This spans frontier closed-weight models and a strong open-weight model, **with 2 reasoning-specialized models (GPT-5.2, Gemini-2.5-Pro) and 4 standard models**."

> "Each pair is presented in both AB and BA order. Every (pair, judge, format, order) combination is **repeated 10 times**. We run at three sampling temperatures: Ts = 0 (all 6 judges), Ts = 0.5, and Ts = 1.0 (**4 judges; reasoning models excluded as public API does not support the temperature parameter**)."

### 摘录 1.5 — Appendix A 开头（明确 reasoning model 被排除出温度扫描）

> "Table 3 reports (C, φ, A, T) across sampling temperatures Ts ∈ {0, 0.5, 1.0} for the four temperature-tunable judges (GPT-4o, Gemini-2.0-Flash, Claude-Sonnet-4.6, Llama-3.3-70B; **GPT-5.2 and Gemini-2.5-Pro are excluded because their public APIs do not expose a temperature parameter**)."

### 摘录 1.6 — Table 1 关键读数（Ts = 0，我们最常引的数）

- GPT-5.2 CoT–XML @ JudgeBench：**C = 75.5**，φ = 12.0，A = 68.0，T = 46.8
- GPT-5.2 CoT–JSON @ JudgeBench：C = 79.0，φ = 13.0，A = 70.5，T = 50.6
- GPT-5.2 CoT–JSON @ MT-Bench：C = 82.1，φ = 6.1，A = 66.8，T = 52.3
- GPT-5.2 Direct @ MT-Bench：C = 89.3，φ = 5.1，A = 64.8，T = 55.6
- Llama-3.3-70B Direct @ JudgeBench：C = 100.0，φ = 26.0，A = 55.5，T = 42.5
- Claude-Sonnet-4.6 Verdict-first @ JudgeBench：C = 94.0，φ = 9.9，A = 77.6，T = 68.3

### 摘录 1.7 — §5.4 Temperature ablation（温度对"噪声项"的影响）

> "Sampling temperature should primarily affect the noise-survival term C, not the bias-adjusted capability term (A − φ/2). A sweep over Ts ∈ {0, 0.5, 1.0} on the four temperature-tunable judges confirms this prediction. As shown in Figure 3, **mean C drops by 12.1 points across the sweep**, while (A − φ/2) changes by only +0.3 points across 48 cells. The resulting decline in T is therefore attributable almost entirely to reduced stochastic consistency."

### 摘录 1.8 — §5.5 失效模式分区（"Confidently biased" 区）

> "Figure 4 organizes judge failures into four regions of (C, φ) space. The Trustworthy region is the only regime where the residual gap 1 − φ/2 − A primarily reflects model capability rather than position bias... The **Confidently biased** region is the most dangerous. Here, high C creates the appearance of reliability while high φ drives T toward zero. **The worst observed cell in our study, with φ = 98% and T = 2.0%, falls in this region.**"

### 摘录 1.9 — §6 Conclusion and Recommendations（**我们可直接引的"规则"**）

> "The implication for practice is concrete. As LLM judges become infrastructure for RLHF, leaderboards, automated evaluation pipelines, and downstream model selection — the field needs **reliability audits alongside accuracy benchmarks**. We recommend that **benchmark releases report at minimum (C, φ, A, T) per cell**, that **judge selection use T rather than accuracy as the comparative scalar**, and that **protocols which leave φ unobservable (single-order evaluation) be treated as fundamentally under-specified**."

> "We also argue that this ceiling is empirically tight; i.e., near-deterministic judges can still produce verdicts that are worse than chance; and **reliability is item-specific rather than judge-level**. The most striking case in our data is a single judge × format × dataset configuration with C = 100% and T = 2%."

### 摘录 1.10 — Limitations（三条自认局限）

> "First, due to computational tractability, we restricted our evaluation to four English-only benchmarks... Second, we evaluate closed-weight models without access to log-probabilities or internal states, which precludes the analysis of finer-grained token confidence signals. Third, our audit focuses exclusively on pairwise preference data."

---

## E2 ✅BLOG — Thinking Machines Lab (2025) — "批不变性"原始出处

- 真实标题：**Defeating Nondeterminism in LLM Inference**
- 作者：Horace He in collaboration with others at Thinking Machines
- 出处：Thinking Machines Lab blog（Connectionism），**2025-09-10**
- URL：https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
- 阅读深度：✅BLOG（38.9 KB 正文全文抓取）
- 代码：https://github.com/thinking-machines-lab/batch-invariant-ops

### 摘录 2.1 — 开篇（直接否证"temp=0 ⇒ 可复现"）

> "Reproducibility is a bedrock of scientific progress. However, it's remarkably difficult to get reproducible results out of large language models."

> "For example, you might observe that asking ChatGPT the same question multiple times provides different results. This by itself is not surprising, since getting a result from a language model involves 'sampling'... What might be more surprising is that **even when we adjust the temperature down to 0** (thus making the sampling theoretically deterministic), **LLM APIs are still not deterministic in practice**. Even when running inference on your own hardware with an OSS inference library like vLLM or SGLang, sampling still isn't deterministic."

### 摘录 2.2 — "The original sin" 与被推翻的民间解释

> "One common hypothesis is that some combination of floating-point non-associativity and concurrent execution leads to nondeterminism based on which concurrent core finishes first. We will call this the 'concurrency + floating point' hypothesis for LLM inference nondeterminism."

> "While this hypothesis is not entirely wrong, it doesn't reveal the full picture. For example, even on a GPU, running the same matrix multiplication on the same data repeatedly will always provide bitwise equal results. We're definitely using floating-point numbers. And our GPU definitely has a lot of concurrency. Why don't we see nondeterminism in this test?"

### 摘录 2.3 — Experiments（**注意括号里的 "non-thinking mode"**）

> "We use Qwen/Qwen3-235B-A22B-Instruct-2507 and sample **1000 completions at temperature 0** with the prompt 'Tell me about Richard Feynman' **（non-thinking mode）**, generating 1000 tokens each. Surprisingly, we generate **80 unique completions**, with the most common of these occuring 78 times. Looking at where the completions differ, we see that the completions are actually **identical for the first 102 tokens**! The first instance of diverging completions occurs at the 103rd token. All completions generate the sequence 'Feynman was born on May 11, 1918, in' However, **992 of the completions go on to generate 'Queens, New York' whereas 8 of the completions generate 'New York City'**. On the other hand, when we enable our batch-invariant kernels, **all of our 1000 completions are identical**."

### 摘录 2.4 — 性能代价（可引的绝对数字）

> "We will set up an API server with one GPU running Qwen-3-8B, and request 1000 sequences with an output length of between 90 and 110. Configuration Time (seconds) vLLM defau[lt]…" （原文表格：vLLM default 26s / batch-invariant unoptimized 55s / improved attention kernel 42s；同一数字在 §Performance 与 §Experiments 两处出现）

---

## E3 ✅FULL — Yuan et al. (2025) — **对"thinking/reasoning ⇒ 噪声放大"最接近的机制证据**

- 真实标题（**v2，当前版**）：**Understanding and Mitigating Numerical Sources of Nondeterminism in LLM Inference**
- ⚠️ **v1（2025-06-11）标题是另一个**：*Give Me FP32 or Give Me Death? Challenges and Solutions for Reproducible Reasoning*
- 作者：Jiayi Yuan (Rice University), Hao Li (Univ. of Minnesota Twin Cities), Xinheng Ding, Wenya Xie, Yu-Jhe Li, Wentian Zhao, Kun Wan, Jing Shi (Adobe), Xia Hu, Zirui Liu
- arXiv id：**2506.09501**（v1 2025-06-11；v2 2025-10-24）
- 阅读深度：✅FULL（v1 HTML 511 KB + v2 HTML 512 KB 均已抓取）

### 摘录 3.1 — Abstract（**"reasoning models 放大噪声"原话**）

> "We demonstrate that the reproducibility of LLM performance is fragile: changing system configuration, such as evaluation batch size, GPU count, and GPU version, can introduce significant differences in the generated responses. **This issue is especially pronounced in reasoning models, where minor rounding differences in early tokens can cascade into divergent chains of thought, ultimately affecting accuracy.** For instance, under bfloat16 precision with greedy decoding, a reasoning model like DeepSeek-R1-Distill-Qwen-7B can exhibit **up to 9% variation in accuracy and 9,000 tokens difference in response length** due to differences in GPU count, type, and evaluation batch size. We trace the root cause of this variability to the non-associative nature of floating-point arithmetic under limited numerical precision."

### 摘录 3.2 — §3.1 实验设置（2 reasoning + 2 non-reasoning 模型）

> "We conduct experiments on four recent LLMs, including **two reasoning models: DeepSeek-R1-Distill-Qwen-7B, DeepSeek-R1-Distill-Llama-8B and two non-reasoning models: Qwen2.5-7B-Instruct and Llama-3.1-8B-Instruct**, across five commonly used LLM evaluation benchmarks: AIME'24, MATH500, LiveCodeBench-Easy, LiveCodeBench-Medium, and LiveCodeBench-Hard."

### 摘录 3.3 — §3.2 节标题本身就是结论

> "**3.2 Greedy Decoding ≠ Deterministic Output** — Contrary to common belief, our experiments reveal that greedy decoding does not guarantee deterministic outputs across different hardware and system configurations. However, using FP32 precision helps a lot."

> "The results demonstrate a clear pattern: **FP32 consistently achieves near-perfect reproducibility with negligible variance, FP16 shows moderate variability, while BF16 exhibits substantial instability.** This pattern is particularly pronounced for reasoning models like DeepSeek-R1-Distill-Qwen-7B, where **BF16 precision introduces up to 9% standard deviation in accuracy on AIME'24**, compared to virtually zero variance under FP32."

### 摘录 3.4 — Figure 3 说明（**"reasoning 模型的 token 概率间隙常常极小"**）

> "Figure 3: Left: the top-5 tokens and their predicted probabilities at the divergence index for two different answers to the same question in BF16. Right: The gap between the top-two competing tokens probability. **We observe the token probability gap are often minimal in reasoning models.**"

### 摘录 3.5 — Table 4（输出长度标准差，12 种 runtime 配置：GPU 型号/数量/batch size）

> "Table 4: Standard deviation of output length of greedy decoding across 12 different settings (GPU types, GPU counts, and batch sizes) under BF16, FP16, and FP32 numerical precisions. **The output length of reasoning models exhibit large variance.**"

> AIME'24 / MATH500 / LiveCodeBench-Easy（B16 / F16 / F32）：
> - DeepSeek-R1-Distill-Qwen-7B：**9.15% / 5.74% / 0** ；**1.04% / 1.12% / 0.12%** ；**1.67% / 1.28% / 0.37%**
> - DeepSeek-R1-Distill-Llama-8B：4.60% / 6.00% / 5.8e-17 ；1.59% / 0.73% / 0.23% ；2.31% / 1.92% / 0.29%
> - Qwen2.5-7B-Instruct：1.71% / 1.45e-17 / 1.45e-17 ；0.83% / 0.36% / 1.16e-16 ；0.79% / 0.48% / 1.16e-16
> - Llama-3.1-8B-Instruct：1.92% / 1.30% / 0 ；0.94% / 0.34% / 0.13% ；1.00% / 0.67% / 0.25%

### 摘录 3.6 — §1 Introduction（"seed 也不够"）

> "same prompt and random seed, the generated output can still differ significantly between different hardware and system configurations."

> "This issue is particularly problematic for recent reasoning-focused models, which generate very long chains of thought. In such cases, **small numerical errors accumulate during the token genera[tion]**…"

### 摘录 3.7 — 修复方案（LayerCast）

> "if using greedy decoding, please use FP32 precision to improve the reproducibility of the efficient reasoning research."

---

## E4 ✅FULL — Atil et al. (2024/2025) — "确定性设置的确定性"被系统性量化

- 真实标题（**v5，当前版**）：**Non-Determinism of "Deterministic" LLM Settings**
- ⚠️ **v1（2024-08-06）标题是另一个**：*LLM Stability: A detailed analysis with some surprises*
- 作者：Berk Atil, Sarp Aykent, Alexa Chittams, Lisheng Fu, Rebecca J. Passonneau, Evan Radcliffe, Guru Rajan Rajagopal, Adam Sloan, Tomasz Tudrej, Ferhan Ture, Zhe Wu, Lixinyu Xu, Breck Baldwin
- 机构：Penn State University + Comcast AI Technologies
- arXiv id：**2408.04667**（v1 2024-08-06；v5 2025-04-02）
- 代码/数据：https://github.com/breckbaldwin/llm-stability
- 阅读深度：✅FULL（arXiv PDF v5 经 `pdftotext -layout` 抽取，47 998 字节）

### 摘录 4.1 — Abstract（**最常被引的两个数**）

> "We investigate non-determinism in **five LLMs configured to be deterministic** when applied to **eight common tasks in across 10 runs**, in both zero-shot and few-shot settings. We see **accuracy variations up to 15% across naturally occurring runs with a gap of best possible performance to worst possible performance up to 70%**. In fact, **none of the LLMs consistently delivers repeatable accuracy across all tasks, much less identical output strings**."

### 摘录 4.2 — 指标定义（TARr@N / TARa@N，**"原始串 vs 解析后答案"两层口径**）

> "Total agreement rate@N (TAR@N): the percentage of test set questions across N runs where generated answers are **all identical**, regardless of whether the answer was correct. We have two variants of TAR@N:
> – **TARr@N** (TAR@N for the raw model response) The LLM responses are string equivalent.
> – **TARa@N** (TAR@N for the answer) The parsed answers are the same, e.g., 'The answer is a)' is the same as 'a) is the answer'."

> "TARa@10 values are much more consistent than TARr@10, yet still lead to high instablity of up to 15% shown in Figure 1."

### 摘录 4.3 — §2/§3 "surprises"（作者自述的三条发现）

> "The evaluated LLMs are rarely deterministic at the raw output level; they are much more deterministic at the parsed output/answer level but still rarely 100% stable across 5 re-runs with same data input."
> "LLM accuracy variation is not normally distributed."
> "Stability varies based on task."

### 摘录 4.4 — 结构性原因（厂商侧）

> "Sharing preliminary results with insiders has revealed that non-determinism perhaps essential to the efficient use of compute resources via co-mingled data in input buffers so this issue is not going away anytime soon."

---

## E5 ✅FULL — Zhao, Esmaeili & Fard (2026) — **CR 口径 + "读数塌到空"的先例**

- 真实标题：**Bias in the Loop: Auditing LLM-as-a-Judge for Software Engineering**
- 作者：Zixiao Zhao, Amirreza Esmaeili, Fatemeh Fard（University of British Columbia, Kelowna BC）
- arXiv id：**2604.16790**（v1, 2026-04-18），cs.SE，ACM 模板（预印本）
- 阅读深度：✅FULL（540 KB arXiv HTML，含 Table 9/10/12 与 §5.3/§5.4）

### 摘录 5.1 — §4.2 指标定义（**CR 的完整口径 + 控制变量清单**）

> "To measure the consistency of LLM judges, we evaluate each evaluation case **twice** with an identical rubric and prompt, no additional context, and with session isolation. We disable all explicit bias cues and keep order, formatting, and instructions fixed. To minimize hidden variance, we (i) **fix decoding settings (temperature, top-p, max tokens)**, (ii) **start fresh conversations for each run to avoid context carryover**, and (iii) **clear any caching artifacts by re-issuing the full prompt**. We use the Consistency Rate (CR) proposed by Ye et al. (2024) to evaluate the consistency of LLMs:
> **CR = (1/|D|) Σ_{i∈D} 𝕀(ŷ^(i,1) = ŷ^(i,2))**
> …For item i, ŷ^(i,1) denotes the LLM judge's decision on the first run, and ŷ^(i,2) denotes the decision on a second, independent run under the same rubric and prompt (i.e., a repeated pass with a different sampling seed)."

### 摘录 5.2 — Table 9（Qwen3-4B，**两次独立跑**的 CR%，no-bias 行）

> "no-bias 91.67 77.34 76.83 **83.60** 97.03 91.90 83.07 **91.41** 86.21 63.79 58.60 **70.56**"
> （列序：CodeGen Easy/Med/Hard/Overall | CodeRepair Easy/Med/Hard/Overall | TestGen Easy/Med/Hard/Overall）

### 摘录 5.3 — Table 10（Qwen2.5-Coder-3B，no-bias 行）

> "no-bias 59.63 56.30 59.29 **58.57** 68.72 64.86 64.12 **65.75** 53.65 47.15 49.73 **50.36**"

> "Across Table 10, Qwen2.5-coder reveals an **alarming baseline instability**. Under the no-bias setting, the Overall Consistency Rate (CR) sits at **58.57 for CodeGen, 65.75 for CodeRepair, and a near-random 50.36 for TestGen**. The model clearly struggles to maintain stable pairwise preferences across independent runs. … In complex scenarios like TestGen, its judgments without bias are **practically indistinguishable from a coin flip**."

### 摘录 5.4 — §5.3 Answer Rate（**"判官读数塌成空"最直接的先例**）

> "The code-specialised Qwen2.5-Coder-3B maintains answer rates around 99% on all three tasks, indicating that it almost always follows the expected judging schema and terminates with an explicit A/B choice. By contrast, the generic Qwen3-4B model only answers roughly **49% of CodeGen cases and around 42% and 41% on CodeRepair and TestGen, with an overall answer rate of 44.37%**. In many of the remaining cases, **the model keeps generating free-form text until it hits its context limit, without ever producing a syntactically valid pred field**, or it drifts into solving the underlying code task instead of issuing a structured judgment. **These failures are not simply lower-quality judgments; they are non-judgments that never enter the accuracy computation at all.**"

> Table 12（Answer rate of two judge models across tasks）：
> "CodeGen Qwen2.5-Coder-3B 99.12 / CodeRepair 99.37 / TestGen 98.64 / **Overall 99.16**；
> CodeGen Qwen3-4B 48.90 / CodeRepair 41.92 / TestGen 40.55 / **Overall 44.37**"

### 摘录 5.5 — §5.4 Implications（**"必须把判官当测量仪器"这条规则**）

> "Our findings suggest that **LLM-as-a-Judge should be treated as a measurement instrument with measurable CR variance and prompt induced bias, rather than as a drop-in replacement for human evaluation** in software engineering contexts. This perspective changes what it means to claim progress. A single accuracy number from one prompt and one ordering is rarely a stable summary of judge b[ehavior]…"

### 摘录 5.6 — 引言（"没有标准的一致性量化口径"）

> "First, **we lack a systematic account of test-retest reliability**: repeated assessments of the same case under a fixed rubric may yield variable outcomes, yet **there is no standard quantification of consistency for the judgments**. Second, prompt-sensitive biases, both explicit (e.g., position, verbosity, authority cues) and implicit (e.g., bandwagon, sentiment), can systematically distort decisions…"

> "Even when evaluating identical instances against predetermined 'fixed' scoring criteria, subtle variations in prompt wording, formatting, or candidate order, alongside the **inherent randomness of the generation process**, can alter judges' scores and choices. This renders outcomes fragile, volatile, and susceptible to manipulation."

---

## E6 ✅FULL — Ye et al. (2024) — **CR 指标的原始出处（CALM）**

- 真实标题：**Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge**
- 作者：Jiayi Ye, Yanbo Wang, Yue Huang, Dongping Chen, Qihui Zhang, Nuno Moniz, Tian Gao, Werner Geyer, Chao Huang, Pin-Yu Chen, Nitesh V. Chawla, Xiangliang Zhang
- 机构：Peking University / IBM Research / University of Hong Kong
- arXiv id：**2410.02736**（v2, 2024-10-03）
- 项目页：https://llm-judge-bias.github.io/
- 阅读深度：✅FULL（arXiv HTML，84.6 KB）

### 摘录 6.1 — §2.3 CR 的原始定义（**注意：原文用的是 temperature 0.7，不是 0**）

> "To assess whether the LLM judge is robust and unbiased, we use the following metrics. The LLM judge is executed twice for each evaluation. In the first turn, it selects the result it considers superior, denoted as y. In the second turn, we perform two parallel judgement: one without any perturbation to obtain y_rand, and another with a bias introduced into the candidate answers, obtaining ŷ. Based on these judgement outcomes, we define two metrics: **Robustness Rate (RR) and Consistency Rate (CR)**, calculating over all samples in test dataset D:
> **RR = (1/|D|) Σ_{i=1}^{|D|} 𝕀(y^i = ŷ^i),  CR = (1/|D|) Σ_{i=1}^{|D|} 𝕀(y^i = y_rand^i)**
> RR measures how consistently the LLM judge's decisions remain the same before and after introducing the bias. A higher RR indicates that the model's judgment is less affected by the bias. **CR evaluates how consistent the model’s decisions are when tested under identical [conditions]**…"

### 摘录 6.2 — §3 超参（**这一条对我们是警示，不是支持**）

> "**Hyperparameters.** We followed the experimental setup of Chen et al. (2024a) by **setting the temperature to 0.7** and applied it to all judge models and generating models to ensure stable output quality and strong reproducibility."

### 摘录 6.3 — Abstract（12 类 bias + CALM 框架）

> "we identify 12 key potential biases and propose a new automated bias quantification framework—CALM—which systematically quantifies and analyzes each type of bias in LLM-as-a-Judge by using automated and principle-guided modification. …while advanced models have achieved commendable overall performance, **significant biases persist in certain specific tasks**. Empirical results suggest that there remains room for improvement in the reliability of LLM-as-a-Judge."

---

## E7 ✅HTML — Shi, Ma, Liang, Diao, Ma & Vosoughi (2025) — **RS（Repetition Stability）口径**

- 真实标题：**Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge**
- 作者：Lin Shi, Chiyu Ma, Wenhua Liang, Xingjian Diao, Weicheng Ma, Soroush Vosoughi（Dartmouth College）
- arXiv id：**2406.07791**（v1 2024-06-12；v9 当前版）
- venue：arXiv comment 自报 **"AACL-IJCNLP 2025"**
- 阅读深度：✅HTML（arXiv HTML 正文经 `web_search` 渲染读取；题录经 arXiv API 核对）

### 摘录 7.1 — §2.2 RS 定义（**"同一 query 重复多次"的第一个正式指标**）

> "**Repetition Stability (RS)** evaluates the **reliability of LLM judges when presented with identical queries multiple times**. It is essential to determine whether the judgments of LLMs, and consequently the observations of position bias, stem from a consistent evaluation pattern or by random variations. We measure this by calculating the **percentage of the most frequent selections across multiple trials for each query**, aggregated from all queries within each dataset. This metric is formalized as
> **RS = (1/N) Σ_{j=1}^{N} (1/n_j) max_{k∈S} {|C_k^j|}**
> where S = {A,B,C,…} refers to the set of choice options depending on the option mode, |C_k^j| denotes the counts of each choice option selected by the judge for the jth query, n_j represents the total number of repeating trials for that query, and N is the total number of queries. The value of RS ranges from a small positive value depending on the option mode, indicating completely random decisions, to 1.0, indicating perfect stability."

### 摘录 7.2 — §3.1 实验设置（**注意 temperature = 1**）

> "To compute repetition stability, we sampled 3 questions per task and 4 candidate models, paired with baseline candidates, for each judge to evaluate across **3 repetitive trials**. This resulted in 576 instances per judge for MTBench and 432 instances per judge for DevBench. **The temperature hyperparameter was set to 1 for all judge models to generate nontrivial results.**"

### 摘录 7.3 — Table 2（RS 读数，**"最一致的判官"与"最不稳的判官"**）

> "Claude-3.5-Sonnet 0.96 ± 0.07 … Gemini-1.5-flash 1.00 ± 0.00 … GPT-4o 1.00 ± 0.02 … GPT-4 0.97 ± 0.05 … o1-mini 0.90 ± 0.07 … Llama-2-7B 0.83 ± 0.15 … **Llama-2-13B 0.45 ± 0.22 … Llama-3-8B 0.16 ± 0.18**"

> "Errors arise from judgment failures (e.g., exceeding context window, not following output format). High error rates and low RS are marked red, rendering further evaluations invalid due to insufficient data."

### 摘录 7.4 — §4 Main Findings（**"重复一致性是位置偏差分析的前置条件"**）

> "Position Bias of Capable Judges are not Mere Random Variations: As shown in Table 2, the capable judges on the benchmark tasks, supported by minimal 'Error' rates, generally exhibit RS values above 0.85. …These results confirm that LLM judgments, and the resulting position bias, are **not due to random variations**."

> "**A high position consistency does not guarantee fairness.** For example, on coding task evaluations, GPT-4 and GPT-4o achieve the top consistency but are significantly recency-preferred and primacy-preferred, respectively."

---

## E8 ✅FULL — Gu, Jiang, Shi, et al. (2024) — 综述 + **"Empty Content"偏差**

- 真实标题：**A Survey on LLM-as-a-Judge**
- 作者：Jiawei Gu, Xuhui Jiang, Zhichao Shi, Hexiang Tan, Xuehao Zhai, Chengjin Xu, Wei Li, Yinghan Shen, Shengjie Ma, Honghao Liu, Yuanzhuo Wang, Wen Gao, Lionel Ni, Jian Guo（IDEA Research / 中国科学院计算技术研究所 / 帝国理工 / 人大高瓡 AI）
- arXiv id：**2411.15594**（v1, 2024-11-23）
- 项目页：https://awesome-llm-as-a-judge.github.io/ ；仓库 https://github.com/IDEA-FinAI/LLM-as-Evaluator
- 阅读深度：✅FULL（arXiv HTML，136 KB）

### 摘录 8.1 — §5.1.4 Model Configuration（**"temp=0 是为了稳定"这一主流做法**）

> "To stabilize the evaluation results of LLMs, **we set the hyper parameter temperature to 0 to reduce the impact of randomness in LLMs' output.** For Summarize by Multiple Rounds, we conduct 5 rounds for each sample."

### 摘录 8.2 — §5.2 偏差表（**"Empty Content" 一栏，n=24**）

> 表头："Model | Model Biases: Alignment | Position | Length | Conciseness | **Empty Content** | Nested | Familiar with Human | Reference | Continuation | Instruction | Knowledge"
> 表头分母："(n=5106) (n=2633) (n=34) (n=28) (n=26) (n=24) (n=24) (n=24)"
> 读数行："GPT-4-turbo 61.57 80.49 91.18 89.29 65.38 95.83 70.83 100.0 … / LLaMA3-8B-Instruct 50.72 38.85 20.59 57.14 65.38 75.00 45.83 54.17 … / GPT-3.5-turbo 54.72 …"

> ⚠️ **该表是"偏差强度"矩阵，不是"读数塌到 0"的直接证据**；Empty Content 一栏 n=24，样本极小。

### 摘录 8.3 — §2.2.2（**闭源 judge 的可复现性问题**）

> "…the opacity of API models also challenges the evaluation reproducibility."

> "**closed-source LLM-as-a-Judge leads to low reproducibility due to potential changes in models behind the API.**"

### 摘录 8.4 — Abstract（综述框架）

> "This paper provides a comprehensive survey of LLM-as-a-Judge, addressing the core question: **How can reliable LLM-as-a-Judge systems be built?** We explore strategies to enhance reliability, including improving consistency, mitigating biases, and adapting to diverse assessment scenarios. Additionally, we propose **methodologies for evaluating the reliability of LLM-as-a-Judge systems**, supported by a novel benchmark designed for this purpose."

---

## E9 ✅FULL — Jeon, Kim, Son, Lee, Jeong & Lee (2026) — **最接近我们场景的 Agent 架构评测**

- 真实标题：**ISD-Agent-Bench: A Comprehensive Benchmark for Evaluating LLM-based Instructional Design Agents**
- 作者：YoungHoon Jeon, Suwan Kim, Haein Son, Sookbun Lee, Yeil Jeong, Unggi Lee（Upstage / Opentutorials / Indiana University Bloomington / Korea University Sejong）
- arXiv id：**2602.10620**（v1, 2026-02-11），cs.SE
- 阅读深度：✅FULL（370 KB arXiv HTML）

### 摘录 9.1 — §5.1（**多判官协议 + 中位数聚合**）

> "Evaluating across three LLMs (Gemini-3-Flash, GPT-5-mini, Solar-Pro3) with a **multi-judge protocol achieving 0.905 reliability**…"

> "Evaluation employs a multi-judge protocol using **two LLMs from different providers: GPT-4o-mini (OpenAI) and Gemini-2.5-flash-lite (Google)**. This cross-provider design mitigates potential self-preference bias where models may favor outputs from the same provider. **Final scores are computed using median aggregation across judges to ensure robustness.**"

### 摘录 9.2 — Table 5（**5,183 次评估的判官间一致性分布**）

> "Table 5. Inter-judge reliability and bias analysis across 5,183 evaluations.
> Agreement | Mean Reliability **0.905** | Std. Deviation **0.084** | Min / Max **0.293 / 1.000**
> Distribution | Excellent (≥0.9) **63.3%** | Good (0.75–0.9) **31.4%** | Moderate (0.5–0.75) **5.1%** | Low (<0.5) **0.3%**
> Bias | Gemini-2.5-flash-lite **+0.060** | GPT-4o-mini **−0.060**"

> "The high inter-judge reliability (0.905) with 94.7% of evaluations achieving good or excellent agreement validates our multi-judge protocol."

### 摘录 9.3 — Abstract（**"agent 评测里的 judge bias 风险"被明确承认**）

> "However, evaluating these agents remains challenging due to the **lack of standardized benchmarks and the risk of LLM-as-judge bias**."

---

## E10 ✅FULL — Paiva, Canedo & Rocha Filho (2026) — **κ/α 口径 + 显式承认 LLM 非确定性**

- 真实标题：**From issue titles to requirements: an empirical study of large language models and prompt engineering strategies**
- 作者：Guilherme Paiva, Edna Dias Canedo, Geraldo Pereira Rocha Filho（University of Brasília / Federal University of Bahia）
- venue：**Requirements Engineering 31, 7 (2026)**（Springer）；DOI **10.1007/s00766-026-00462-z**
- 判官模型：Qwen QwQ-32B（LLM-as-a-Judge），900 条 requirement
- 阅读深度：✅FULL（Springer 全文页 558 KB 抓取 + 抽取）

### 摘录 10.1 — §4.6.4 Agreement metrics（**他们选了哪几个系数**）

> "To comprehensively assess the reliability and potential bias of the LLM-as-a-Judge methodology, we computed the following agreement metrics… These metrics capture complementary aspects of agreement, including inter-rater reliability, rank consistency, pairwise agreement, and systematic bias:
> (i) **Krippendorff's alpha (ordinal)**: inter-rater reliability among the five human evaluators, computed per quality attribute. Values ≥ 0.667 indicate acceptable agreement and values ≥ 0.800 indicate strong agreement;
> (ii) **Spearman's rank correlation (ρ)**: monotonic association between the mean human scores and the LLM-judge scores…
> (iii) **Cohen's weighted kappa**: pairwise agreement between each individual evaluator and the LLM-as-a-Judge, accounting for ordinal proximity in disagreements…
> (iv) **Percentage agreement (exact and ±1)**…
> (v) **Signed mean deviation**: systematic bias direction and magnitude…"

### 摘录 10.2 — §4.6.5 Human validation results（**α 的真实值域，勿与 κ 混**）

> "**Inter-rater reliability.** Krippendorff's alpha values were low for all three attributes (**α = 0.150–0.394**), falling below the α ≥ 0.667 threshold for acceptable agreement. This indicates substantial disagreement among the five human evaluators themselves, with **Verifiability showing the lowest consensus (α = 0.150) and Singularity the highest (α = 0.394)**."

> "**Pairwise agreement.** The mean quadratic-weighted Cohen's kappa between individual evaluators and the LLM-as-a-Judge ranged from **κ_w = 0.286 (Unambiguity) to κ_w = 0.372 (Singularity)**, indicating fair agreement according to Landis and Koch's scale. **Individual evaluator–LLM kappa values ranged from κ_w = 0.094 to κ_w = 0.488**, reflecting the variability also observed among human raters."

> "**Percentage agreement.** When comparing the human median score to the LLM-judge score, within-one-point agreement (±1) reached **84% for Unambiguity, 96% for Verifiability, and 72% for Singularity**. Exact agreement was lower (**34–42%**)."

### 摘录 10.3 — §5 Threats to validity（**"LLM Non-Determinism"被显式列为内效度威胁**）

> "(2) **LLM Non-Determinism**: Although we used fixed seeds and temperature settings, **inherent non-determinism in LLM APIs or underlying optimizations could potentially introduce slight variations. While we observed practical reproducibility during our experiments, we cannot guarantee identical outputs upon exact replication.**"

### 摘录 10.4 — §4.6.6（**一个与我们冲突的强主张，值得单列**）

> "The LLM judge performs comparably to an individual human evaluator whose agreement with peers is itself limited while **offering perfect consistency and scalability** across the full set of 900 requirements."

> ⚠️ **"perfect consistency"是一个未被其自身设计证成的强主张**（他们用 §5 的"LLM Non-Determinism"威胁自相矛盾），我们的读数直接反驳这一主张。

---

## E11 ✅FULL — 2408.04667 的姊妹篇：Song, Wang, Li & Lin (2024)

- 真实标题：**The Good, The Bad, and The Greedy: Evaluation of LLMs Should Not Ignore Non-Determinism**
- 作者：Yifan Song, Guoyin Wang, Sujian Li, Bill Yuchen Lin
- arXiv id：**2407.10457**（v1, 2024-07-15）
- 阅读深度：⚠️**ABS**（只读到 arXiv API 摘要；正文未读，未做任何外推）

> "Current evaluations of large language models (LLMs) often **overlook non-determinism**, typically focusing on a single output per example. This limits our understanding of LLM performance variability in real-world applications. … Through extensive experiments, we observe that **greedy decoding generally outperforms sampling methods** for most evaluated tasks. We also observe consistent performance across different LLM sizes and alignment methods, noting that **alignment can reduce sampling variance**. Moreover, our best-of-N sampling approach demonstrates that smaller LLMs can match or surpass larger models such as GPT-4-Turbo…"

---

## E12 ⚠️ABS — Liu, Jin (2026) — **唯一直接把 temperature 当 facet 做方差分解的论文**

- 真实标题：**Generalizability Theory for LLM-as-Evaluator Reliability: Univariate and Multivariate Variance Decomposition Across Models, Prompts, and Temperatures in Text Classification**
- 作者：Jin Liu（Takeda Development Center Americas, Inc.）
- 出处：SSRN preprint，**6432598**，日期 **2026-03-17**，DOI 10.2139/ssrn.6432598
- 阅读深度：⚠️**ABS**（SSRN 页面直连超时，只读到检索到的完整摘要段；**未读正文**）

> "We applied univariate and multivariate generalizability theory (G-theory) to decompose LLM annotation variance across four facets (**evaluator, prompt type, temperature, seed**) using a fully crossed design (**64,800 observations** across hate-speech, mental-health, and drug-review tasks). **Item difficulty dominated total variance in univariate decompositions (66.5–88.5%)**, with the item-by-evaluator interaction as the primary nuisance source and **temperature contributing effectively zero**, while multivariate decompositions showed per-dimension reliability varied with construct clarity rather than base rate (**Eρ² = 0.841 to 0.989**). D-study projections showed univariate generalizability reached **Eρ² = 0.940 to 0.988** under the full design and **Eρ² = 0.678 to 0.889** under the single-evaluator, single-prompt baseline… **inter-model agreement consistently exceeded LLM–human agreement, exposing a reliability–validity distinction**…"

> ⚠️ 这条是**对我们归因的最强反面证据**（在他们的实验里 temperature 这一 facet 对总方差贡献 ≈ 0）。

---

## E13 ⚠️ABS — RobustJudge (2025) — 判官鲁棒性框架

- 真实标题：**LLMs Cannot Reliably Judge (Yet?): A Comprehensive Assessment on the Robustness of LLM-as-a-Judge**
- 作者：Songze Li, Chuokun Xu, Jiaying Wang, Xueluan Gong, Chen Chen, Jirui Zhang, Jun Wang, Kwok-Yan Lam, Shouling Ji
- arXiv id：**2506.09443**（v1 2025-06-11；v3 当前版）
- 阅读深度：⚠️**ABS**（只读摘要；正文未读）

> "…these systems are susceptible to adversarial attacks that can manipulate evaluation outcomes, raising critical concerns about their robustness and trustworthiness. Existing evaluation methods for LLM-based judges are often fragmented and lack a unified framework for comprehensive robustness assessment. Furthermore, **the impact of prompt template design and model selection on judge robustness has rarely been explored, and their performance in real-world deployments remains largely unverified.** To address these gaps, we introduce RobustJudge, a fully automated and modularly extensible framework designed to systematically evaluate the robustness of LLM-as-a-Judge across task datasets, judge prompt templates, judge models, attacks, and defenses. Specifically, RobustJudge investigates the effectiveness of **15 attack methods and 8 defense strategies across 13 models (RQ1)**, examines the impact of prompt template design and model selection (RQ2)…"

---

## E14 ⚠️ABS — Agent-as-a-Judge 综述 (2026)

- 真实标题：**Agent-as-a-Judge**
- 作者：Runyang You, Hongru Cai, Caiqi Zhang, Qiancheng Xu, Meng Liu, Tiezheng Yu, Yongqi Li, Wenjie Li
- arXiv id：**2601.05111**（v1, 2026-01-08）
- 阅读深度：⚠️**ABS**（只读摘要；正文未读）

> "LLM-as-a-Judge has revolutionized AI evaluation by leveraging large language models for scalable assessments. However, as evaluands become increasingly complex, specialized, and multi-step, **the reliability of LLM-as-a-Judge has become constrained by inherent biases, shallow single-pass reasoning, and the inability to verify assessments against real-world observations.** This has catalyzed the transition to Agent-as-a-Judge, where agentic judges employ planning, tool-augmented verification, multi-agent collaboration, and persistent memory to enable more robust, verifiable, and nuanced evaluations."

---

## E15 ⚠️ABS — "Give Me FP32…" 的 v1 标题证据（**标题被改过，务必引用 v2**）

已在 arXiv abs 页核对提交历史：

> "arXiv:2506.09501 — Submission history — From: Jiayi Yuan — [v1] Wed, 11 Jun 2025 08:23:53 UTC (471 KB) — [v2] Fri, 24 Oct 2025 21:04:56 UTC (474 KB)"
> 当前标题（H1）："Title: Understanding and Mitigating Numerical Sources of Nondeterminism in LLM Inference"
> v1 HTML 页内标题（arXiv:2506.09501v1 [cs.CL] 11 Jun 2025）："Give Me FP32 or Give Me Death? Challenges and Solutions for Reproducible Reasoning"

同样地，2408.04667 的提交历史：

> "arXiv:2408.04667 — [v1] Tue, 6 Aug 2024 16:43:35 UTC … [v5] Wed, 2 Apr 2025 15:17:02 UTC"；当前 H1 标题 "Non-Determinism of 'Deterministic' LLM Settings"；v1 HTML 页内标题 "LLM Stability: A detailed analysis with some surprises"

---

## 抓取工具备忘（本沙盒实测）

| 通道 | 状态 |
|---|---|
| `web_fetch` 工具 | ❌ 完全失效（一律 "file load failed"） |
| `bash` + `curl` → arxiv.org / export.arxiv.org / api.crossref.org | ✅ 可用 |
| `bash` + `curl` → arxiv.org/pdf + `pdftotext -layout` | ✅ 可用（2408.04667 全文走这条路） |
| `bash` + `curl` → thinkingmachines.ai | ✅ 可用（200，102 KB） |
| `bash` + `curl` → link.springer.com | ✅ 可用（200，558 KB） |
| `bash` + `curl` → ssrn.com | ❌ 超时（只拿到 190 字节） |
| `web_search` | ✅ 可用，`content` 字段带渲染正文 |
| arXiv HTML 断点续传 | 本次 6 篇全部一次到位（`content-length` == 实收字节数），未触发 resume 循环 |
