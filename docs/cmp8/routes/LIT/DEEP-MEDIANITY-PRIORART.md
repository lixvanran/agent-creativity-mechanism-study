# DEEP-MEDIANITY · 先验工作检索（PRIOR ART）

> **目的**：为「答案有多中庸 / 搜索空间塌缩 / 过早闭合 / 落在分布中心」这一组测度，
> 判定**我们自造的四个指标**（交集率 / 边际利用率 / 中庸距离 / 覆盖饱和度）与
> **`VD_anchor_out`（锚外新增维度数）** 到底是**该换成既有指标**、**该对齐既有口径**，
> 还是**确实没有先例、必须自造**。
>
> **配套逐字摘录**：`/workspace/lab/routes/LIT/DEEP-MEDIANITY-PRIORART-quotes.md`
> **原始抽取副本**：`/workspace/lab/routes/LIT/_priorart_src/`（`.html` = arXiv LaTeXML 原文，`.txt` = 去标签纯文本，可 `grep` 复核）
> **检索日期**：2026-10-22
> **作者**：General（root session 455189915857002）

---

## 0. 结论摘要（TL;DR）

### 0.1 ★ 三条该换用（换成/对齐既有口径）

| # | 我们的指标 | 换成的既有指标 | 为什么换 | 迁移成本 | 风险 |
|:-:|---|---|---|---|---|---|
| **1** | **中庸距离**<br>（族交并比 + 4-gram） | **Self-Sim**（Lake, Choi & Durrett, **NAACL 2025**, arXiv:2406.17692）<br>＋ **碰撞概率 / N₂ / 碰撞比 R**（Skobelev, Fithian & Han, arXiv:2609.16454） | Self-Sim = "词干集合两两 Jaccard 的平均"，**零 embedding、零外部模型、有 N=5 的标准采样口径**，且论文自报了一张可比表（0.11–0.45）。我们的"族交并比 + 4-gram"是它的一个**更严、但无出处、且在中文更脆**的变体。<br>而"**落在分布中心 / 众数吸引**"这件事的严格定义是碰撞比 R（C=Σπ²，N₂=1/C，R>1 即 mode collapse），**它自带 KL 界与温度可达区间定理**——这正是"中庸"该有的数学。 | 低：我们的 `family_key` 已经是"语义等价类"，直接套 Self-Sim 的两两平均即可；碰撞概率是纯计数 | 4-gram 属 **form-sensitive**（Tevet & Berant 2021 的 content- vs form-sensitive 之分）；中文 4-gram 比英文词干更不可靠 ⇒ **必须两版并报**，不能只留 4-gram |
| **2** | **交集率**<br>（出现在所有臂/重复里的承重结论占比） | **多数票份额**（Self-Consistency, Wang et al., **ICLR 2023**, arXiv:2203.11171）<br>＋ **平均不同答案数 "# distinct answers"** 与 **离散语义熵 DSE**（Kuhn, Gal & Farquhar, **ICLR 2023**, arXiv:2302.09664） | "众数答案占多大比例"是 Self-Consistency 的**原语**，不是我们的发明。Kuhn et al. 直接报 "Average # of semantically distinct answers"（TriviaQA **1.89** 答对 vs **3.89** 答错）。**关键**：语义熵的聚类步骤需要 NLI 模型，**而我们的 `family_key` 聚类就是那个等价类** ⇒ 我们可以**零外部模型**地实现**离散语义熵**，并引用一个有名字、有读数的方法。 | 中：要重写交集率的口径（按族而非按结论条目），并同时产出 3 个数（多数票份额 / #distinct / DSE） | DSE 的"熵"值依赖等价类质量 ⇒ **必须同时报 #distinct**（Kuhn 自己就这么做，且自己说"# distinct 这个计数本身就是个合理的测度"） |
| **3** | **边际利用率**<br>（第 k 轮/第 k 个组件带来的**新**承重结论占比） | **ESS（Effective Sample Size）**（Giannone et al., arXiv:2510.05825）<br>＋ **逐轮 distinct-n / 总词数**（Vijayakumar et al., **AAAI 2018**, arXiv:1610.02424 的 "Diversity Statistics"） | "第 k 轮骤降 = 提前停了" 是我们自造的曲线形状。ESS = 1/Σ(w_t)² 是粒子过滤 / MCMC 里"**搜索塌成少数路径**"的**标准离散量**，且**它就是 N₂**（与第 1 条同数学）——一条口径同时覆盖"中庸"和"过早闭合"。max ESS = N、min ESS = 1，边界可解释。 | 中：需要把"新发现族数"变成权重 w_t（不是二值） | 我们若只有"是/否新发现"的二值，ESS 退化为 1/Σw²，**仍可算但分辨率低** ⇒ 需改记录方式 |

### 0.2 ★ 三条该保留自造（并说明为什么）

| # | 保留什么 | 为什么先例不成立（已核） | 但必须显式声明的边界 |
|:-:|---|---|---|
| **1** | **`VD_anchor_out`（锚外新增维度数）+ 它的判定链**（承重 ∧ 被依据支持 ∧ 写得出决策岔口 ∧ 岔口 ∉ `C_t`，且由**不知道 `C_t`** 的判官判） | 三个最接近的先例**参照系都不同**：<br>① **PSFA**（Wray/Kirk/Laird, arXiv:2405.12147，项目已精读）——"漏掉项"的参照系是**人类专家的问题空间分解**（Newell 1980 / GOMS），候选槽位**先验封闭**；<br>② **DiscoveryBench**（Majumder et al., arXiv:2407.01725）——"新"的参照系是**文献/已发表研究**（"realistic but **never reported before**"）；<br>③ **OvertonScore**（Poole-Dayan et al., **ICLR 2026**, arXiv:2512.01351）——参照系是**人类观点集合 W(x)**。<br>⇒ **"事前预注册的结论空间 + 决策岔口"这个组合，我没找到先例。** | 形式上**有**先例（=集合覆盖率口径，见 OvertonScore）⇒ 论文里必须写"**形式有先例，参照系是新的**"，不能写"无人做过" |
| **2** | **承重检验 C1/C2/C3**（决策岔口可指名 / 删除反事实成立 / 在结论空间内） | 没有先例把"**删掉这条信息后结论是否改变**"当作承重判据。Curiosity Search（Stanton & Clune, PLoS ONE 2016，项目已精读）的 leave-one-out 判的是**行为新颖性**；MAME 的影响矩阵判的是**agent×依据归因**。两者都不是"结论承重"。 | 它和 `C_t` 预注册是**一对**——没有预注册就没有"删除反事实"的参照面 ⇒ 两者必须一起留 |
| **3** | **覆盖饱和度**（已找到族集合 ÷ \|C_t\|）+ **塌缩 / 闭合 / 耗尽三分** | 形式有先例（OvertonScore = 集合覆盖），但**分母不同**：OvertonScore 的分母是人类观点集 \|W(x)\|，且它**只报覆盖**，不区分"空间被穷尽"vs"空间在缩小"。我们的分母是**预注册结论空间 \|C_t\|**，且三者必须分开报。 | 改名对齐为 "**coverage over a pre-registered conclusion space**"，并把 \|C_t\| 写成**绝对分母**（我们早期读数分母=1 的教训） |

### 0.3 最重要的一句话

> **我们四个自造指标里，有三个的"形"已经被做过了——而且其中两个（Self-Sim、ESS/N₂）在数学上是同一个东西的不同叫法。**
> 但**把它们全部换掉也不对**：`VD_anchor_out` + 承重检验 + 覆盖饱和度这一组，是围绕**"预注册的结论空间"**组织的，
> 我检索了 open-ended problem formulation / problem space coverage / novel dimension discovery 三条路径，**没有找到参照系相同的先例**。
>
> ⇒ **正确动作不是"换"或"不换"，而是：③换口径（保留我们的数据组织）、①②换口径并引用、④与 `VD_anchor_out` 保留并改名对齐。**
> ⇒ **且：语义熵这条路本来是"要 NLI 模型"的死路——因为我们已经有 `family_key` 等价类，这条路反而是通的。**

---

## 1. 被审对象：我们自造的东西（逐字口径，先对齐再比先例）

来源：`/workspace/lab/PAPER-2026-10-25.md` §3.4 / §3.6，`/workspace/lab/routes/COLLAPSE/anchor_out.py`

| 我们的指标 | 原文定义 | 测什么 |
|---|---|---|
| ① **交集率** | "出现在所有臂/所有重复里的承重结论占比" | 中庸的**直接**度量 |
| ② **边际利用率** | "第 k 轮/第 k 个组件带来的**新**承重结论占比" | **过早闭合的信号**（骤降 = 提前停了）|
| ③ **中庸距离** | "与'众数答案'的离散距离（**族交并比 + 4-gram**）" | 只比同批内相对序 |
| ④ **覆盖饱和度** | "已找到的族集合 ÷ \|C_t\|" | **区分塌缩 / 闭合 / 耗尽** |

```
VD_anchor_out(arm) = |{新出现的承重族：其支撑的结论 ⊄ C_t}|
```

`anchor_out.py` 的判定链（已读源码，`routes/COLLAPSE/anchor_out.py:71-102`）：
**离散、零 embedding**——把 `C_t` 每条结论与判官给的 `decision_changed` 都压成**「决策指纹」**（选项标记 / 数值集合 / 2-gram 内容词集合），
指纹有交集 ⇒ 锚内；无交集 ⇒ 锚外。

> 论文自陈的**项目级硬约束**（`PAPER-2026-10-25.md:143-145`）：
> "我们实测所用的 `embo-01` 在中文句级**无分辨率**（27 条断言被压成 1 条）；且**措辞级相似度在改写型环节彻底失效**（keep-Jaccard = 0.000）。"
> ⇒ **本检索的判据**：任何候选指标若**必须**依赖句向量几何 ⇒ 直接排除（但仍要记录，因为它是概念上的最近邻）。

---

## 2. 检索方法：跑了哪些路径（"未找到"要可辩护）

### 2.1 沙盒工具实测

| 工具 | 实测 | 本次怎么用 |
|---|---|---|
| `web_fetch` | **本沙盒全面失败**（按任务书告知，未再消耗轮次） | — |
| `web_search` | 可用，`content` 字段带**抓到的正文整段** | 用于**发现**候选 + 读出版页/二手综述正文 |
| `bash` + `curl` | 可用 | **所有元数据与正文的一手来源** |
| arXiv API `export.arxiv.org` | 可用（**必须用 `https`**，http 返回 0 字节）；连续 4–5 次查询后会限流（`entries=0`），需 sleep 3–6s | 题录核验的唯一权威源 |
| arXiv HTML `arxiv.org/html/<id>v1` | 可用（老论文可能无 HTML ⇒ 回退 `ar5iv`） | 正文抽取（12 篇） |
| `api.github.com`（带 token） | 可用 | 官方仓 README |
| `aclanthology.org` | **404**（本次试的 `2020.naacl-main.195` 不存在）⇒ 该路径本次**未走通**，venue 字段改由 arXiv `comment` 字段给出 | — |

### 2.2 题录核验：**先按标题反查 arXiv id，再取全文**（不靠记忆）

⚠️ **本次实测：靠记忆填 arXiv id 有 2/9 是错的**：
- 我记忆中 `1810.00420` = Vendi Score（Mirza et al.）⇒ **实际是** *"Holographic entanglement of purification for thermofield double states and thermal quench"*（凝聚态物理）
- 我记忆中 `1909.10292` = *"The Black Box of Search Errors"*（Stahlberg & Byrne）⇒ **实际是** *"State-selective coherent motional excitation ... single molecular ions"*（物理化学）
- 我记忆中 `2006.14171` = Welleck et al. 重复类论文 ⇒ **实际是** *"A Closer Look at Invalid Action Masking in Policy Gradient Algorithms"*

⇒ **纪律：所有 id 一律用 `search_query=ti:"..."` 反查得到，写进本文的每个 id 都经 `export.arxiv.org` API 回验过题名/作者/日期/venue comment。**
（`ti:` 短语查询在 10 次批量里 8 次命中，2 次 0 命中——**0 命中一律当"未确认"，不写进引用表**。）

### 2.3 三条"锚外先例"检索路径（都跑了）

1. `open-ended problem formulation evaluation` → 命中 PSFA（已精读）、DiscoveryBench、AI Scientist
2. `problem space coverage benchmark` → 命中 OvertonScore、Task-Dependent Homogenization、NoveltyBench
3. `discovering new problem dimensions LLM` → 命中 Artificial Hivemind、LiveIdeaBench、Can LLMs Generate Novel Research Ideas

### 2.4 本次**没有**做的事（诚实边界）

- **没有**做中文句级 embedding 的任何实验（我们只有 `embo-01` 的既有实测结论）
- **没有**把任何候选指标**实现出来**跑一遍——本文是**口径对账**，不是复现；凡涉及"我们能不能算"的判断，只按"输入是否可得 + 是否需外部模型"推断
- **没有**读《The Black Box of Search Errors》原文（arXiv 上按标题 0 命中、ACL Anthology 404）⇒ 该条**只作为未验证线索记录**，不进主表

---

## 3. ★ 主表：候选指标 × (定义可复算? / 需 embedding? / 需要什么输入) × 一句话结论

**图例**：`可复算` = 有明确公式/算法/伪代码，我能照着实现；`emb` = 是否需要句向量几何；`外部模型` = 是否需要 NLI / LLM / 外部 API 之外的模型

### A 组 —「趋同 / 众数吸引」

| # | 候选指标 | 出处（已核） | 可复算? | emb? | 外部模型? | 需要什么输入 | 一句话结论 |
|:-:|---|---|:-:|:-:|:-:|---|---|
| A1 | **Self-Consistency 多数票**（多数票份额 = 众数答案占比） | Wang et al., **ICLR 2023**, arXiv:2203.11171v4 | ✅ | ❌ | ❌ | N 条推理路径 + 答案抽取（精确匹配） | **"众数答案"这件事的规范实现**；我们的"交集率"应该改写成它 |
| A2 | **离散语义熵 DSE** / 语义熵 | Kuhn, Gal & Farquhar, **ICLR 2023 (Spotlight)**, arXiv:2302.09664v3 | ✅ | ❌ | ⚠️ **需要 NLI 模型**（DeBERTa-large-MNLI） | M 条采样 + 语义等价聚类 | **"中庸"的教科书口径**；聚类要 NLI ⇒ **我们用 `family_key` 顶替即可，零外部模型** |
| A3 | **平均不同答案数**（# distinct answers） | 同 A2，Table 2 | ✅ | ❌ | ⚠️ 同上 | 同上 | **最朴素、最可比的收敛度读数**（TriviaQA 1.89 vs 3.89）；A2 论文自陈"这个计数本身就是个合理测度" |
| A4 | **碰撞概率 C / N₂（逆 Simpson 指数）/ 碰撞比 R** | Skobelev, Fithian & Han, arXiv:2609.16454v1（2026-09-15，预印本无 venue） | ✅ | ❌（离散核；可换核） | ❌ | 一组采样（+ 可选目标分布做参照） | **"众数吸引"最严格的定义**；自带偏差-方差分解、KL 界、温度可达区间 (g\*, S) |
| A5 | **Self-Sim**（词干 Jaccard 两两平均） | Lake, Choi & Durrett, **NAACL 2025 (Main)**, arXiv:2406.17692v2 | ✅ | ❌ | ❌ | 每个 prompt **N=5** 次采样 | **我们"中庸距离"的已发表等价物**（比我们的 4-gram 版更稳、且有对照表 0.11–0.45） |
| A6 | **Within-prompt similarity** | Jiang et al., **NeurIPS 2025 D&B (Oral)**, arXiv:2510.22954v2 | ✅ | ✅ **必须** | ❌ | 20 响应/模型（42 模型） | 概念最贴题（"同质化"）但**必须排除**：embedding 几何 |
| A7 | **Universal Self-Consistency (USC)** | Chen, Aksitov, Alon, Ren, Xiao & Yin, arXiv:2311.17311v1 | ✅ | ❌ | ⚠️ **需 LLM 判蕴含** | 候选答案列表 | 自由文本版的"选最一致的那个"；**依赖 LLM 判定蕴含**（我们要避免的那类依赖） |
| A8 | **语义熵作发散性/多样性度量** | Tan, Choy, Alsagoff, Wangsajaya, Banerjee, Saikia & Chan, **ACL 2026 (Main)**, arXiv:2606.11762v1 | ✅ | ❌ | ⚠️ **需 NLI**（`tasksource/deberta-base-long-nli`） | 多域多采样 + 人类标注 | ★ **"语义熵 = 无参照的新颖度/多样性"已有 2026 ACL 直接先例** ⇒ 我们的用法**有出处可引** |
| A9 | **Vendi / 1−φ / PCD / MMD + W-D-3 / Self-BLEU / Distinct-n** | Chen, Tong, Yang, He, Zhang, Zou, Wang & He, **Findings of ACL 2026**, arXiv:2604.18005v2 | ✅ | ⚠️ 一半要 | ❌ | 一组 proposal | **项目已精读**（`LIT/22_MAS_Diversity.md`）；词法子集（W-D-3 / Self-BLEU / Distinct-n）**零 embedding** |
| A10 | **任务依赖型同质化（8 类任务分类 + 功能多样性）** | Jain, Lanchantin, Nickel, Ullrich, Wilson & Watson-Daniels（FAIR@Meta / MIT）, arXiv:2509.21267v1 | ⚠️ 靠 LLM judge | ❌ | ⚠️ 需 LLM judge | 任务分类 + 成对比较 | **警告先例**：任务无关的指标（embedding 距离、词面重叠）分不清"实质变化"vs"改写" ⇒ 我们的 4-gram 口径要自己交代这个风险 |
| A11 | **NoveltyBench** | Zhang, Diddee, Holm, Liu, Liu, Samuel, Wang & Ippolito, arXiv:2504.05228v4（venue COLM 2025 来自 A10 的二手引用，arXiv 元数据未标） | ⚠️ | ⚠️ | ⚠️ | — | A10 明确批评其"任务无关"；我们若引用多样性基准，需引它并声明我们的任务依赖性 |

### B 组 —「过早闭合 / 搜索停太早」

| # | 候选指标 | 出处（已核） | 可复算? | emb? | 外部模型? | 需要什么输入 | 一句话结论 |
|:-:|---|---|:-:|:-:|:-:|---|---|
| B1 | **ESS（有效样本量）** = 1/Σ(w_t)² | Giannone, Xu, Nayak, Awhad, Sudalairaj, Xu & Srivastava, arXiv:2510.05825v2（preprint） | ✅ | ❌ | ❌ | 粒子/分支的权重 w_t | ★ **"搜索塌到少数路径"的标准离散量**；**数学上就是 N₂**；max=N、min=1 |
| B2 | **Diversity Statistics**（distinct n-grams ÷ 总词数） | Vijayakumar, Cogswell, Selvaraju, Sun, Lee, Crandall & Batra, **AAAI 2018**, arXiv:1610.02424v2 | ✅ | ❌ | ❌ | 一组生成结果 | 离散 n-gram 覆盖率口径；**我们"覆盖饱和度"的 n-gram 版已有出处** |
| B3 | **Hamming / Cumulative Diversity** | 同 B2 | ✅ | ❌ | ❌ | beam 分组 | 搜索内多样性的标准罚函数（Δ 项） |
| B4 | **rep-2（重复 bigram 占比）** | Li, Lan, Fu, Cai, Liu, Collier & Watanabe, **NeurIPS 2023**, arXiv:2310.10226v1 | ✅ | ❌ | ❌ | 文本 | 退化/重复的离散率；**数据重复率被模型放大 >10 倍**（原文口径） |
| B5 | **推理级语义冗余（早停）** | Min, Vaccarino, Chen, Wu, Yona & Cheng, arXiv:2605.17672v1（under review） | ✅ | ✅ **必须** | ❌ | 推理步轨迹 | 概念上**正是**我们的"边际利用率"（"最近还在不在产生新信息"），但**必须排除**：微调过的 Qwen3-Embedding-0.6B |
| B6 | **核采样 / 退化机制** | Holtzman, Buys, Du, Forbes & Choi, **ICLR 2020**, arXiv:1904.09751v2 | — 机制 | ❌ | ❌ | — | **机制来源**（"概率最大化的引力"），**不是指标口径来源**（其指标公式本次未逐字取到） |

### C 组 —「"中庸"在别处怎么量化」

| # | 候选 | 出处（已核） | 可复算? | emb? | 外部模型? | 需要什么输入 | 一句话结论 |
|:-:|---|---|:-:|:-:|:-:|---|---|
| C1 | **OvertonScore（集合覆盖率）** | Poole-Dayan, Wu, Sorensen, Pei & Bakker, **ICLR 2026 (accepted)**, arXiv:2512.01351v2 | ✅ | ❌ | ⚠️ 需 LLM judge（Gemini 2.5 Pro）+ **人类观点集 W(x)** | W(x) + 60 题 | ★ **"覆盖一个参照集"的形式先例**；**并且它直接点名"中立 = 泛泛而谈"的病灶**（"bland, centrist summaries"） |
| C2 | **分布性多元主义 / Self-Sim** | Lake et al., **NAACL 2025**, arXiv:2406.17692v2 | ✅ | ❌ | ❌ | N=5 采样 | "**跨采样的分布**"正是我们的中庸场景；**Overton 式（单条回复内）不算** |
| C3 | **众数数 g\* 与有效支撑 S**（温度可达区间 (g\*, S)） | Skobelev et al., arXiv:2609.16454v1 | ✅ | ❌ | ❌ | 单个分布 | **"落在分布中心"的严格表述**：T→0 ⇒ 只剩 g\* 个众数；T→∞ ⇒ 逼近 S 个支撑点 |
| C4 | **heaping（LLM 打分堆在"喜爱数字"）** | Licht, Sarkar, Wu, Goel, Stoehr, Ash, Miserlis & Hoyle, **EMNLP 2025**（*Meeting's Field* / DOI 未核） | ⚠️ | ❌ | ⚠️ 需 LLM 打分 | 1–9 分打分 | ★ **"答案堆在分布中心"的已知现象**，但在**标量打分**语境，不在**答案语义**语境 ⇒ 只能当**类比**引 |
| C5 | **hedging 五级量表 + P(4)+P(5)** | Anthropic `political-neutrality-eval` 仓（**无同行评审**） | ✅ | ❌ | ⚠️ 需 LLM judge + token 概率 | 响应 | **有口径无学术地位**：1–5 级 + `P(high_hedging)=P(4)+P(5)` + 阈值 0.5/0.1；**只能当工程参考，不能当先例引用** |
| C6 | **"generic / 平淡的中间答案"作为病灶的定性论证** | OvertonScore 论文相关工作（"value monism" / "algorithmic monoculture"）+ 任务依赖型同质化（A10） | ❌ 定性 | — | — | — | **"中庸有害"这个论断本身有先例**；但**没人把它做成一个可复算的数**（除了 C1 的覆盖率） |

### D 组 —「锚外发现有没有先例」

| # | 先例 | 出处（已核） | 参照系是什么 | 与 `VD_anchor_out` 的差异 |
|:-:|---|---|---|---|
| D1 | **PSFA**（问题空间表述） | Wray, Kirk & Laird, arXiv:2405.12147（*Cognitive Systems Research* 94:101409, 2025）——**项目已精读** | **人类专家的问题空间分解**（Newell 1980 / GOMS），候选槽位**先验封闭** | 参照系是**外部人类分解**；我们的是**事前预注册的结论空间 `C_t`** |
| D2 | **DiscoveryBench** | Majumder, Surana, Agarwal, Dalvi Mishra, Meena, Prakhar, Vora & Khot, arXiv:2407.01725v1（code: `allenai/discoverybench`） | **文献/已发表研究**——"realistic but **never reported before**" | "新" = **没被发过**；我们 = **不在 `C_t` 里**（`C_t` 是我们自己的预注册答案空间，不是世界） |
| D3 | **OvertonScore** | Poole-Dayan et al., arXiv:2512.01351v2 | **人类观点集合 W(x)**（1,209 名美国代表性参与者、60 题） | 分母是**人类观点集**；我们的是**预注册结论空间** |
| D4 | **Artificial Hivemind / NoveltyBench / 任务依赖型同质化** | A6 / A11 / A10 | 参照系 = **待比较的另一批输出**（同质化）或**任务分类** | 都不是"**参照一个事先划好的答案空间**" |
| ⇒ | **结论** | — | — | ★ **"锚外"这个口径我没找到先例**（三条检索路径都跑过）。但**形式（集合覆盖率）有先例**（D3），且 **D1 的"closed candidate slots"恰好是 `C_t` 结构性阻止发现**的同类病 ⇒ 论文里应引 D1 作为"我们的病 = 它的病，但我们的解药是换一个参照系" |

---

## 4. A 组细读（最该抄的四条）

### A2 / A3 — 语义熵（Kuhn et al., ICLR 2023）★ 重点

**算法（可复算）**：
1. 从固定 prompt 用同一模型采样 **M** 条答案（论文用 multinomial sampling；`M < 20` 通常够）
2. **语义聚类**：对每一对答案 `s, s'`，把 **context+s** 与 **context+s'** 拼接后做 **双向蕴含**判定（`s ⊨ s'` 且 `s' ⊨ s` ⇒ 等价）⇒ 合并簇。**判定器 = DeBERTa-large，在 MNLI 上微调**
3. **语义熵**：把每个簇内序列的似然加起来当作"该含义的概率"，对**含义分布**求熵
4. **离散变体（discrete semantic entropy）**：无 token 概率时，用**样本频率**当簇质量 ⇒ **只要答案 + 簇就够**

**读数（带分母）**：
- 聚类器准确率：人工标注 **300** 条生成 ⇒ **TriviaQA 92.7% / CoQA 95.5%**
- Table 2（**每个数据集的全体平均**）：

| Dataset | 平均不同语义答案数（答对） | （答错） | AUROC：语义熵 | AUROC：# distinct answers |
|---|---:|---:|---:|---:|
| CoQA | **1.27** | **1.77** | **0.77** | 0.66 |
| TriviaQA | **1.89** | **3.89** | **0.83** | 0.79 |

**对我们的意义（三条，缺一不可）**：
1. ★ **"中庸"有一个已成名的口径** ⇒ 我们的"交集率/中庸距离"可以挂到它下面，评审不必再问"你这度量哪来的"
2. ⚠️ **它的聚类依赖外部 NLI 模型**（DeBERTa-large-MNLI，**英文**）⇒ 在中文上不能直接用；**但我们不需要它**——我们的 `family_key`（决策指纹聚类）**就是那个等价类**
3. ⚠️ 论文自陈"# distinct 这个计数本身就是个合理的测度，语义熵更好" ⇒ **必须同时报 #distinct**，不能只报熵
4. **它已不是新东西了**：A8（ACL 2026）已经把语义熵当成**无参照的多样性/新颖度**度量在用 ⇒ 我们的用法是**跟随**，不是发明

### A4 — 碰撞概率 / N₂ / 碰撞比 R（Skobelev et al., 2026）★ 最该抄的"严格版"

**定义（可复算，零 embedding）**：
```
碰撞概率：  C(π) = Σ_a π(a)²                      # 两次独立采样撞在一起的概率
逆 Simpson： N₂(π) = 1 / C(π)                     # "若要造成同样碰撞概率，需要多少个等可能选项"
碰撞比：    R := C(q) / C(p) = N₂(p) / N₂(q)
            R = 1 → 多样性标定；R > 1 → mode collapse；R < 1 → over-dispersion
核推广：    C_{p,k}(x) = E_{Y,Y'~p(·|x)}[k(Y,Y')],  k ∈ [0,1], k(y,y)=1
            精确碰撞核：k(y,y') = 1{y = y'}
```
**理论（这是自造指标给不了的）**：
- **偏差-方差分解**：`E[R] = 1 + (1/C_h(p))·[Tr Cov(q̂) + ‖b_h‖² + 2 p_hᵀ b_h]` ⇒ 有限样本**不蕴含**塌缩
- **定理 1**：`|模型碰撞概率 − 目标碰撞概率| ≤ sqrt(KL(p‖q))` ⇒ 靠近最优的模型不会任意错标定多样性
- **引理 1（温度可达区间）**：`N₂_T(x) ∈ (g*(x), S(x))`，`g*` = 众数个数、`S` = 支撑集大小；`T→0 ⇒ g*`，`T→∞ ⇒ S`
  ⇒ ★ **这就是"落在分布中心"的严格说法**：低温时分布**只能**取那 `g*` 个众数
- **定理 2**：温度**不改变支撑集**、不改变次序 ⇒ 温度调不出目标分布

**读数（带分母）**：
- **3 / 4** 个基座模型相对**人类调查人群**（GSS / ANES / WVS，LoRA 微调）**离散不足 1.6–2.9 倍**
- CodeNet（人类代码解法，AST 的归一化 Zhang–Shasha 相似度核）：`R = 0.74–1.64`（**有的模型过度离散、有的塌缩** ⇒ 方向取决于模型）
- 实验 1：**100** 个小 transformer × **100** 个对数间隔样本量 × **2** 个 order-16 合成语言

**对我们的意义**：
- ★ 我们的"中庸距离"想测的"**众数吸引**"，这里有**教科书定义 + 理论 + 界** ⇒ 应当直接引用而不是自造
- ⚠️ **R 的分母是"目标分布"**（人类参照）。我们**没有人类目标分布** ⇒ 用**批内自参照**（把同批臂当作 q）要显式声明：**那 R 只能读"同批内相对中庸"，不能读"相对人类"**
- ⚠️ 预印本，**无同行评审** ⇒ 引用时必须写"preprint"

### A5 — Self-Sim（Lake et al., NAACL 2025）★ 最直接可抄

**定义（逐字可复算，零 embedding）**：
> 给定一个 prompt 的一组采样响应，把每个响应转成**唯一词干集合**，对**所有响应两两**算 **Jaccard 相似度**并取平均；**每个 input 用 N = 5 个样本**。

**读数（带分母，Table 2）**：

| 模型 | ConflictingQA Self-Sim | LIMA-OE Self-Sim | 长度（ConflictingQA） |
|---|---:|---:|---:|
| Llama 2 (base, no prompt) | **0.17** | **0.11** | 37 |
| Llama 2 + URIAL prompt | **0.23** | **0.24** | 203 |
| Llama 2 Chat | **0.36** | **0.34** | 412 |
| GPT-3.5 Turbo | **0.45** | **0.36** | 98 |

**对我们的意义**：
- ★ 这是**我们"中庸距离"的已发表等价物**：同一形状（批内相对位置）、同一"离散、零 embedding"纪律、且**有对照表**⇒ 评审可以直接问"你们和 Lake et al. 的 0.11–0.45 差多少"
- ★ 论文自己把 Self-Sim 定位为 **"distributional pluralism"**（跨采样的分布多元主义）的代理 ⇒ **"中庸"这个词在文献里有位置了**
- ⚠️ 口径警告：他们同时说 **Overton pluralism（单条回复内）这个指标抓不到**，⇒ **Self-Sim 只覆盖"跨采样"轴**；我们的"中庸"若指"单条答案落在分布中心"，还需要另一半（见 C3 的 g\*/S）
- ⚠️ 词干化在中文上要换成"分词后词干/字元"，**这是我们必须自己定的口径**（不能直接抄英文 stemmer）

### A6 / A8 / A9 — 三个"最近邻"及其处置

| | 最近邻 | 处置 |
|---|---|---|
| A6 | **Artificial Hivemind**（within-prompt similarity 0.821，42 模型 × 20 响应；同 prompt 两两相似度典型 >0.8；全局随机配对 **100%** 落在 0.1–0.2） | **概念锚 + 数字锚，不是可用指标**（`text-embedding-3-small`）。它的"within-prompt similarity"命名值得借；它的**读数**可以作为"我们的中庸度若换算过去会落在哪个区间"的粗参照 |
| A8 | **Tan et al., ACL 2026** | ★ **我们"用语义熵测多样性"这件事有 2026 ACL 直接先例** ⇒ 引用它可挡掉"你为什么用这个奇怪指标" |
| A9 | **MAS Diversity**（项目已精读） | 我们已有词法子集（W-D-3 / Self-BLEU / Distinct-n）的完整口径与代码位置；**Vendi 主判据因 embedding 排除**，与本项目 U2 一致 |

---

## 5. B 组细读：过早闭合该用哪个

### B1 — ESS（ePF, arXiv:2510.05825）★ 首选

**定义（逐字）**：
```
ESS(t) = 1 / Σ_{i=1..N} (w_t^i)²
最大：权重均匀 (w=1/N) ⇒ ESS = N（= 总粒子数）
最小：一个权重 1、其余 0 ⇒ ESS = 1（"有效规模已塌成单个粒子"）
```
**语义（逐字）**：
> "低方差的重采样分布 ⇔ 高的粒子多样性"——ESS 是**在每一步**度量"搜索是否塌到少数路径"的标准量。

**读数（带分母）**：AIME 2025，**2 个粒子**预算下任务奖励相对标准 PF **最高 +50%（相对）**；AIME 2024 上 **8 粒子**追平标准 PF 的 **32 粒子**；消融含 ESS 专节（附录 D.9）。

**为什么它对我们的"边际利用率"更合适**：
- 我们的"边际利用率"是**逐轮新发现占比**的**曲线**；ESS 是**逐轮的标量**，且**理论上下界可解释**（1 = 塌成一条路径，N = 完全不塌）
- ⇒ **两个都报**：曲线给形状，ESS 给单值可跨臂比较
- ⚠️ ESS 需要**权重**而不是"是/否"⇒ 我们记录时要存"每轮新发现族数"（当权重），不能只存布尔

### B2 / B3 — Diverse Beam Search（AAAI 2018）

- **Diversity Statistics（逐字）**："数出生成列表中出现的**不同 n-gram** 数；类似 Li et al. 2015，我们把这些计数**除以生成的总词数**以抑制长句偏置。"
  ⇒ ★ 这是**离散 n-gram 覆盖率的规范口径**，与我们"覆盖饱和度"的 n-gram 变体同源
- **Hamming Diversity**："按**已被选中的次数**成比例惩罚前组用过的 token"；**Cumulative Diversity**：两条序列一旦分得够开就不再互相限制
  ⇒ 可作**搜索内**多样性的标准罚函数参考

### B4 — rep-2（NeurIPS 2023）

- 度量：**重复 bigram 的占比**（表列名 `Rep-2`）；原文口径："神经 LM 会把数据里的重复**放大 10 倍以上**"
- ⚠️ **重复 ≠ 趋同**：rep-2 测**退化/循环**，不测"答案落在分布中心" ⇒ **不可替代 ①②③**，只作**辅助**（同一份文本既重复又中庸是两件事）

### B5 — PUMA（必须排除，但概念要借）

- 概念（逐字）："当**连续的推理步不再增加新进展**、而只是重访既有结论时，推理轨迹**很可能已经收敛**"——这**就是**我们"边际利用率"想说的事
- ⚠️ **实现用了微调过的 `Qwen3-Embedding-0.6B`**（`s_t^(k) = max_{t-k≤j<t} cos(f(r_j), f(r_t))`，默认 `τ_sim = 0.35`、`k = 1`）⇒ **按我们的纪律排除**
- 它的**反事实读数**值得引：五个 LRM 中 **41–52%** 的推理 token 是在"模型已给出最终答案之后"生成的；且答案就绪类信号会**误停**（置信度信号误停率约 **44%**、答案一致性约 **64%**——⚠️ 这两个数字来自**二手中文报道**，**未从论文正文核实**，引用须标注）
- ⇒ **可借的替代实现**：把"语义冗余"换成"**新承重族数**"⇒ 正好就是我们的 ②，只是曲线/标量之争

---

## 6. C 组细读：「中庸」在别处怎么量化

### C1 — OvertonScore（ICLR 2026）★ 形式先例 + 病灶论证

**定义（逐字公式）**：
```
Coverage(ℳ, x) = (1/|W(x)|) · Σ_{y ∈ W(x)} 1{ y ∈ ℳ(x) }
OvertonScore(ℳ, X) = (1/n) · Σ_{i=1..n} Coverage(ℳ, x_i)
```
- `W(x)` = 该问题的 **"Overton window"** = **人类参与者自由书写 + 投票聚类**得到的观点集合
- `y ∈ ℳ(x)` = 该观点的簇内多数人觉得模型回复代表了自己的看法（1–5 分量表，**平均 ≥4** 记为"被覆盖"）
- 另有权重版 `Weighted OvertonScore`（按簇规模加权）

**读数（带分母）**：
- 人类研究：**N = 1209** 名美国代表性参与者、**60** 题（15 题 Model Slant + 45 题 PRISM values-guided）、**8** 个前沿 LLM
- **8 个模型的平均 adjusted OvertonScore = 0.39**（区间 **0.35–0.41**），理论上限 **1.0**；DeepSeek V3/R1、Llama 3.3、GPT-4.1 最高；Gemma 3-27B 显著低于均值（**p = 0.015**）
- 自动判官（Gemini 2.5 Pro）与人类判断的**秩相关 ρ = 0.88**

**两条对我们特别重要**：
1. ★ **"中立 = 平淡的中间答案"这个病灶有先例点名**：论文逐字写 **"A model may appear neutral by producing a single centrist or generic answer that omits minority viewpoints, thereby achieving low perceived slant but low pluralism."**（即"看起来中立 = 给一个**平淡的中间答案**、抹掉少数观点"）；并把这个现象命名为 **value monism**（"collapsing genuine disagreements … into a single normative stance"）。而且**"中立 ≠ 多元"**有定量：政治中立（低 slant）与多元代表之间的相关为**负**（**Pearson r = −0.41 / Spearman ρ = −0.32 / Kendall τ = −0.24**）
   ⇒ ★ **这就是"中庸"在文献里的名字与它的危害的证据** ⇒ **我们的立论可以引它，不必自证"中庸有害"**
2. ★ **形式上，它就是我们的"覆盖饱和度"**（覆盖率 / 分母）⇒ 我们的口径要**显式说"分母不同"**：`W(x)` = 人类观点集，vs 我们的 `C_t` = **预注册的结论空间**

### C2 / C3 — 两半都要

- **C2（跨采样轴）** = Self-Sim（A5）：分布性多元主义的代理
- **C3（单分布轴）** = g\*/S 区间（Skobelev et al.）：**低温时分布只能取 g\* 个众数** ⇒ "单条答案落在分布中心"的严格说法
- ⇒ **"中庸"其实是两个轴**：① 批内答案互相像不像（Self-Sim / 碰撞概率）；② 分布的众数集中度（N₂、g\*）。我们的四个指标只覆盖了 ① 的一部分 ⇒ **建议补一个 N₂/碰撞比读数**

### C4 — heaping（EMNLP 2025）

- 现象：让 LLM 打 1–9 分，它会**堆在"喜爱数字"上（1、5、8）**⇒ 分布呈"块状"（lumpy），与人类评分相关性差
- ⇒ **这是"输出堆在分布中心"的一个已知现象**，但在**标量打分**语境 ⇒ **只能当类比引**，不能当"中庸答案"的度量
- ⚠️ venue 记为 EMNLP 2025，**DOI 未核**（来源为二手综述页）⇒ 引用前必须补核

### C5 — hedging

- 找到的唯一**可复算**的工程口径：`anthropics/political-neutrality-eval`（**无同行评审**）——五级量表（No / Minimal / Moderate / Substantial / Extreme Hedging），`P(high_hedging) = P(4)+P(5)`，成对平均后按阈值二值化（同 provider 0.5 / 跨 provider 校准到 0.1），**406** 对
- ⚠️ **不是学术先例**；且**它测的是"承认对立观点"，不是"答案落在分布中心"** ⇒ **不构成"中庸"的替代指标**
- ⇒ **诚实结论：hedging 这一支，学术上我没有找到一条"可复算 + 有分母 + 与中庸直接相关"的度量。** 这反而支持我们保留自造（但要在论文里明说"检索过，没找到"）

---

## 7. D 组细读：锚外发现有没有先例

### D1 — PSFA（项目已精读，最接近）
- "漏掉项"的参照系 = **人类专家问题空间分解**（Newell 1980 / GOMS）⇒ **候选槽位先验封闭**
- 自陈 "the least successful of all the nodes we included"；把"生成 novel problem spaces"列为**开放问题**
- 自陈 **"strong attractor effect"** 与 **"parrot similar problems and solutions"**
- ⇒ **量纲差异正是我们的"锚外"**：它承认发现不了 ⇒ 我们用**预注册结论空间**做参照系，但**这恰恰把"发现"变成了"预注册之外"** ⇒ ★ **必须正面回应**：我们的 `C_t` 也是人事先划的 ⇒ 评审可问"你和 PSFA 的封闭性差在哪"
  ⇒ **答案**：`C_t` 是**结论**空间（答案侧），PSFA 的封闭性是**问题槽位**空间（问题侧）⇒ 我们放开的是"**结论可以超出预注册**"，它没放开的是"**问题可以超出人类分解**"。**这是可辩护的区分，但必须写出来。**

### D2 — DiscoveryBench
- 任务形式（逐字）："给定一个或多个任务数据集 D 与一个发现目标 G，导出一个假设 `h = ψ(c, v, r)`，在 D 的支持下对上下文 c、变量 v、关系 r 达到最高的specificity"
- 目标（逐字）："评估 LLM 解决**一个逼真但从未被发表过**的发现任务的能力"
- ⇒ **"新"的参照系是"世界上没人发过"**（文献/已发表研究）⇒ **与我们的 `C_t`（我们自己的答案空间）完全不同维度**
- ⇒ 借它做**对照叙事**很好（它证明"发现型评测"这条路存在），但**不能借它的"新"的口径**

### D3 — OvertonScore
- 分母 = 人类观点集 ⇒ 覆盖率先例，但**参照系是外部人类集合**

### ⇒ D 组结论（写进论文的措辞）
> "我们检索了 open-ended problem formulation、problem space coverage、discovering new problem dimensions 三条路径，
> **未找到参照系为『事前预注册的结论空间』的『锚外发现』度量**。
> 最接近的三个先例（PSFA / DiscoveryBench / OvertonScore）的参照系分别是**人类专家问题分解**、**已发表文献**、**人类观点集合**，
> 而『集合覆盖率』这一**形式**已有先例（OvertonScore）。
> ⇒ 我们的贡献是**参照系 + 判据（决策岔口 + leave-one-out 承重）**的组合，不是『覆盖率』这个形式本身。"

---

## 8. 决策矩阵：我们四个指标 + `VD_anchor_out` 的逐项对账

| 我们的指标 | 现状 | 先例中**最贴近**的一条 | 决定 | 落到执行层 |
|---|---|---|---|---|
| ① **交集率** | 出现在所有臂/重复里的承重结论占比 | **多数票份额**（A1）+ **# distinct**（A3）+ **DSE**（A2） | **换口径** | 报 3 个数：<br>①a 多数票份额（族级多数票）<br>①b 平均不同族数<br>①c 离散语义熵（用 `family_key` 当等价类 ⇒ 零 NLI）<br>并注明"Kuhn et al. 用 NLI 聚类，我们用决策指纹聚类，**等价类来源不同**" |
| ② **边际利用率** | 第 k 轮/组件带来的新承重结论占比 | **ESS**（B1）+ **DBS diversity statistics**（B2） | **换口径** | 保留曲线，**加报 ESS(t)**（权重 = 该轮新发现族数）<br>并同时报"逐轮 distinct-n ÷ 总词"作为**跨论文可比的 n-gram 版** |
| ③ **中庸距离** | 与众数答案的离散距离（族交并比 + 4-gram） | **Self-Sim**（A5）+ **碰撞概率/N₂/R**（A4） | **换口径（部分保留）** | 离散距离本体改为 **Self-Sim**（词干/字元集合 Jaccard 两两平均，N=5 口径）<br>4-gram 降为**辅助列**（form-sensitive，中文更脆）<br>**新增 N₂ / 碰撞比**（批内自参照，并声明"非相对人类"）<br>保留"只比同批内相对序"这一**性质声明** |
| ④ **覆盖饱和度** | 已找到族集合 ÷ \|C_t\| | **OvertonScore**（C1） | **保留 + 改名对齐** | 改名 "coverage over a pre-registered conclusion space"；<br>显式写"形式同 OvertonScore，分母不同（预注册结论空间 vs 人类观点集）"；<br>\|C_t\| 写成**绝对分母**；<br>保持"塌缩 / 闭合 / 耗尽"三分不合并 |
| ⑤ **`VD_anchor_out`** | 新承重族中结论 ⊄ `C_t` 的数量 | 无（形式先例 = OvertonScore；参照系先例 = PSFA/DiscoveryBench） | **保留** | 写清"形式有先例、参照系无先例"；<br>与 PSFA 的**问题侧 vs 结论侧**区分必须写出来；<br>判据链（承重 ∧ 被依据支持 ∧ 决策岔口 ∧ 岔口∉`C_t`，判官不知 `C_t`）逐条列出 |
| ⑥ **承重检验 C1/C2/C3** | 决策岔口 / 删除反事实 / 在结论空间内 | 无 | **保留** | 与 ⑤ 成对保留；与 Curiosity Search 的 leave-one-out 做**对象差异**说明（行为新颖性 vs 结论承重） |

---

## 9. 引用清单（全部经 `export.arxiv.org` API 回验题名 / 作者 / 日期 / venue comment）

| 简称 | 题名 | 作者 | 日期 | venue（arXiv comment 原文） | arXiv id |
|---|---|---|---|---|---|
| KUG23 | Semantic Uncertainty: Linguistic Invariances for Uncertainty Estimation in Natural Language Generation | Lorenz Kuhn, Yarin Gal, Sebastian Farquhar | 2023-02-19 | "International Conference on Learning Representations 2023 (Spotlight)" | 2302.09664v3 |
| WAN23 | Self-Consistency Improves Chain of Thought Reasoning in Language Models | Xuezhi Wang, Jason Wei, Dale Schuurmans, Quoc Le, Ed Chi, Sharan Narang, Aakanksha Chowdhery, Denny Zhou | 2022-03-21 | "Published at ICLR 2023 … v4: camera ready" | 2203.11171v4 |
| SKO26 | Fine-Tuning Fixes Mode Collapse and Over-Dispersion in LLMs | Kirill Skobelev, Eric Fithian, X. Y. Han | 2026-09-15 | （无 comment ⇒ 预印本） | 2609.16454v1 |
| GIA25 | Mitigating Premature Exploitation in Particle-based Monte Carlo for Inference-Time Scaling | Giorgio Giannone, Guangxuan Xu, Nikhil Shivakumar Nayak, Rahul Mahesh Awhad, Shivchander Sudalairaj, Kai Xu, Akash Srivastava | 2025-10-07 | "preprint" | 2510.05825v2 |
| LAK25 | From Distributional to Overton Pluralism: Investigating Large Language Model Alignment | Thom Lake, Eunsol Choi, Greg Durrett | — | "NAACL 2025 (Main Conference)" | 2406.17692v2 |
| JIA25 | Artificial Hivemind: The Open-Ended Homogeneity of Language Models (and Beyond) | Liwei Jiang, Yuanjun Chai, Margaret Li, Mickel Liu, Raymond Fok, Nouha Dziri, Yulia Tsvetkov | — | "NeurIPS 2025 D&B Paper (Oral); Camera-Ready Version" | 2510.22954v2 |
| POO26 | Benchmarking Overton Pluralism in LLMs | Elinor Poole-Dayan, Jiayi Wu, Taylor Sorensen, Jiaxin Pei, Michiel A. Bakker | — | "Paper accepted to ICLR 2026" | 2512.01351v2 |
| TAN26 | Automated Creativity Evaluation of Language Models Across Open-Ended Tasks | Min Sen Tan, Zachary Kit Chun Choy, Syed Ali Redha Alsagoff, Nadya Yuki Wangsajaya, Mohor Banerjee, Swaagat Bikash Saikia, Alvin Chan | — | "Accepted to ACL 2026 (Main Conference). 35 pages, 16 figures. Code: github.com/tanminsen/creativity-eval" | 2606.11762v1 |
| JAI25 | LLM Output Homogenization is Task Dependent ⚠️（v3 改题 "Task-Dependent Evaluation of LLM Output Homogenization: A Taxonomy-Guided Framework"） | Shomik Jain, Jack Lanchantin, Maximilian Nickel, Karen Ullrich, Ashia Wilson, Jamelle Watson-Daniels | 2025-09-25 | （无 comment） | 2509.21267v1 |
| VIJ18 | Diverse Beam Search: Decoding Diverse Solutions from Neural Sequence Models | Ashwin K Vijayakumar, Michael Cogswell, Ramprasath R. Selvaraju, Qing Sun, Stefan Lee, David Crandall, Dhruv Batra | 2016-10-07 | "16 pages; accepted at AAAI 2018" | 1610.02424v2 |
| LI23 | Repetition In Repetition Out: Towards Understanding Neural Text Degeneration from the Data Perspective | Huayang Li, Tian Lan, Zihao Fu, Deng Cai, Lemao Liu, Nigel Collier, Taro Watanabe | — | "Accepted to NeurIPS 2023" | 2310.10226v1 |
| HOL20 | The Curious Case of Neural Text Degeneration | Ari Holtzman, Jan Buys, Li Du, Maxwell Forbes, Yejin Choi | 2019-04-22 | "Published in ICLR 2020" | 1904.09751v2 |
| MIN26 | Stop When Reasoning Converges: Semantic-Preserving Early Exit for Reasoning Models | Dehai Min, Giovanni Vaccarino, Huiyi Chen, Yongliang Wu, Gal Yona, Lu Cheng | — | "under review" | 2605.17672v1 |
| MAJ24 | DiscoveryBench: Towards Data-Driven Discovery with Large Language Models | Bodhisattwa Prasad Majumder, Harshit Surana, Dhruv Agarwal, Bhavana Dalvi Mishra, Abhijeetsingh Meena, Aryan Prakhar, Tirth Vora, Tushar Khot | 2024-07-01 | "Website: github.com/allenai/discoverybench" | 2407.01725v1 |
| CHE23 | Universal Self-Consistency for Large Language Model Generation | Xinyun Chen, Renat Aksitov, Uri Alon, Jie Ren, Kefan Xiao, Pengcheng Yin | — | （无 comment） | 2311.17311v1 |
| MAUVE21 | MAUVE: Measuring the Gap Between Neural Text and Human Text using Divergence Frontiers | Krishna Pillutla, Swabha Swayamdipta, Rowan Zellers, John Thickstun, Sean Welleck, Yejin Choi, Zaid Harchaoui | 2021-02-02 | "NeurIPS 2021 (Oral Presentation)" | 2102.01454v3 |
| ZH23 | Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena | Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, et al. | 2023-06-09 | "NeurIPS 2023 Datasets and Benchmarks Track" | 2306.05685v4 |
| ZHA25 | NoveltyBench: Evaluating Language Models for Humanlike Diversity | Yiming Zhang, Harshita Diddee, Susan Holm, Hanchen Liu, Xinyue Liu, Vinay Samuel, Barry Wang | — | （无 comment；COLM 2025 为二手引用） | 2504.05228v4 |
| SI24 | Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers | Chenglei Si, Diyi Yang, Tatsunori Hashimoto | — | "main paper is 20 pages" | 2409.04109v1 |
| WRA25 | Eliciting problem specifications for LLM-modulo cognitive systems ⚠️（arXiv 题名为 "Eliciting Problem Specifications via Large Language Models"） | Nicholas Wray, Jaroslav Kirk, Christopher Laird | — | （*Cognitive Systems Research* 94:101409, 2025） | 2405.12147v2 |
| CHE26 | Diversity Collapse in Multi-Agent LLM Systems: Structural Coupling and Collective Failure in Open-Ended Idea Generation（**项目已精读**） | Nuo Chen, Yicheng Tong, Yuzhe Yang, Yufei He, Xueyi Zhang, Qingyun Zou, Qian Wang, Bingsheng He | — | Findings of ACL 2026 | 2604.18005v2 |

---

## 10. 未能验证 / 未找到清单（诚实清单）

| 项 | 状态 | 已试过的路径 | 影响 |
|---|---|---|---|
| **Stahlberg & Byrne《The Black Box of Search Errors》** | ❌ **未取到** | arXiv `ti:"The Black Box of Search Errors"` → 0 命中；`au:Stahlberg_B` → 0 命中；`aclanthology.org/2020.naacl-main.195` → **404** | 该文"search error rate = beam search 与模型真 argmax 的不一致率"**是"过早闭合"最贴题的度量之一**，但本次**没有原文** ⇒ **不进主表**；若要进，必须先补 `aclanthology.org` 正确条目号 |
| **Holtzman et al. 的多样性指标公式** | ⚠️ **只确认机制，未取到指标公式** | 读了 arXiv HTML 全文（`h_1904.09751.txt`），只抽到 "The Gravitational Force of Repetition" 等机制段 | 若要引用其读数，**必须**再取其 PDF 表格；本次只在正文里当**机制来源**用 |
| **rep-2 的精确定义式** | ⚠️ **只取到表列名与文字口径** | `H_2310.10226.txt` 中 `rep-2 score` 全部命中均为讨论段；**未取到定义式** | 用它时写"重复 bigram 占比（论文表列名 Rep-2）"，**不写公式** |
| **PUMA 的"误停率 ≈44% / 答案一致性 ≈64%"** | ⚠️ **二手** | 数字来自中文二手报道（机器之心/今日头条转述），**未在论文正文核实** | 若要用，**必须**标"二手"或回原文补核 |
| **Licht et al. (EMNLP 2025) 的 DOI / venue** | ⚠️ **未核** | 仅从二手综述页读到题名与作者顺序 | 引用前须补 Crossref/OpenAlex |
| **LiveIdeaBench（Nat Commun 17:3625, 2026）** | ⚠️ **二手，未读原文** | 经一篇科普站（clearskyscience.com）读到摘要级描述 | 只作"发散思维基准"的背景提及，**不引其数字** |
| **"Diversity of Thoughts"（Lingam et al., ICLR 2025）** | ⚠️ **二手，未核** | 来自一篇博客的转述 | 不进引用表 |
| **heaping 论文的 arXiv id** | ❌ **未取到** | 只拿到题名 + 作者 | 同上 |
| **"Cultivating Pluralism in Algorithmic Monoculture"（2507.09650）** | ❌ **未读原文** | 只从 A10 的参考文献列表看到 arXiv id | 不进引用表 |

---

## 11. 给主会话的三行行动摘要

1. **立刻可做（零额外成本）**：把 ①交集率 → 多数票份额 / #distinct / DSE 三个数；②边际利用率 → 加报 ESS(t)；③中庸距离 → 主体改成 Self-Sim、4-gram 降为辅助、新增 N₂/碰撞比。全部用我们**已有的** `family_key` 等价类，**不需要 embedding、不需要 NLI**。
2. **论文措辞要改**：④覆盖饱和度 与 `VD_anchor_out` 的贡献陈述，必须写成"**集合覆盖的形式有先例（OvertonScore, ICLR 2026），参照系（预注册结论空间）与判据（决策岔口）没有**"。
3. **两个必须正面回应的质疑**：(a) 我们的 `C_t` 也是人事先划的 ⇒ 与 PSFA 的"封闭候选槽位"差在哪（我们封的是**结论**侧，它封的是**问题**侧）；(b) 我们的"中庸"跨了**两个轴**（批内互相像不像 vs 分布众数集中度），现有四个指标只覆盖前者 ⇒ 补 N₂/碰撞比才完整。
