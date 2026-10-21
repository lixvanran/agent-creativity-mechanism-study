# 精读 22 · Xtra-Computing/MAS_Diversity ——「多样性崩溃」研究仓库 + 论文

> **本条目的形态**：这不是一篇"论文 + 附件"，而是一个**研究代码仓库**（`simulation/` 生成数据 + `analysis/` 算指标 + `configs/` 定义拓扑）。
> 本条目同时提取了 **① 仓库代码**（39 个文件全部读，关键脚本全部逐行读）与 **② 论文正文**（arXiv:2604.18005v2 LaTeXML 全文，56 页）。
> **凡是"仓库里能算出来的"与"论文里写的"我分开标注**，因为**两者对不上，而且对不上的地方正是本条目最有价值的部分**。

---

## 0. 引用

- **标题**：Diversity Collapse in Multi-Agent LLM Systems: Structural Coupling and Collective Failure in Open-Ended Idea Generation
- **作者**：Nuo Chen, Yicheng Tong, Yuzhe Yang, Yufei He, Xueyi Zhang, Qingyun Zou, Qian Wang, Bingsheng He（新加坡国立大学 NUS + 香港中文大学（深圳））
- **年份 / venue**：2026；**Findings of ACL 2026**；arXiv:2604.18005v2（2026-04-21），56 页 15 图
- **代码**：https://github.com/Xtra-Computing/MAS_Diversity （MIT）
- **一句话声称解决什么**：**"多智能体协作并不会自动扩大想法空间——恰恰相反，交互结构本身（"structural coupling"）会收缩 agent 的探索空间，导致 diversity collapse；因此多样性崩溃是"集体失效"而不是"模型不够强"。"**

> ⚠️ 论文只做**观测/诊断**，**没有提出任何优化器**。没有搜索、没有策略学习、没有梯度、没有更新规则。
> 这正好落在我们的 **U5（缺优化策略）** 上，但性质相反：它是"连目标函数都没有，只有一张观测报表"。

---

## 1. 核心机制（具体到能照着实现）

### 1.1 任务与单位（论文 §2.1 / Appendix A）

| 项 | 内容 |
|---|---|
| **输入** | 一个研究领域字符串 `{topic}`（20 个 ICLR 主题，见 `figA1_gpt51_cross_topology.py:26-52` 的 20 个短名映射）+ 一个 persona 角色描述。**没有题面、没有状态变量** |
| **产物形态** | 半结构化 research proposal，固定 5 段：`1. Title / 2. Problem Statement / 3. Motivation & Hypothesis / 4. Proposed Method / 5. Step-by-Step Experiment Plan`（+ 可选 `References`）。格式硬编码在 `simulation/configs/dsv3_naive_recursive.yaml:115-146` |
| **采集单位** | **1 次 MAS 会话 = 1 个 proposal**。`simulation/extract_txt.py:49-53` 用正则 `1\.\s*Title:` 从会话日志里切出第 5 轮综述输出，存成 `paper_txts = [...]` 列表 |
| **样本量** | 20 主题 × 50 次独立会话 = **每配置 1,000 个 proposal**；全库 >10,000 个 proposal（论文 §2.2） |

### 1.2 流水线（论文 §2.2 三阶段 + 仓库实现）

```
Role Instantiation → Iterative Deliberation → Proposal Synthesis
   persona 角色串        4 轮讨论（AgentVerse sim-basic）   第 5 轮：Editor 写 proposal
```

仓库侧（`simulation/run_dynamic_topic.py`）：

| 项 | 内容 | 来源 |
|---|---|---|
| **状态表示** | **纯文本 chat_history**（`memory_type: chat_history`），没有结构化状态、没有隐藏向量 | `configs/*.yaml:48-52` |
| **算子（全部）** | ① 三个 conversation agent 按轮次发言；② 一个 `agent_type: tool` 的 agent 作为 **Editor/综述者**在第 5 轮写最终 proposal | `configs/dsv3_naive_recursive.yaml:44-155` |
| **agent 数** | **3 个讨论 agent + 1 个综述 agent = 4 个 agent 条目**；但第 4 个与第 1 个同名（`Participant 1` / `PhD Student A`） | 同上 |
| **轮数 / 停止条件** | `max_turns: 5` **写死**（4 轮讨论 + 1 轮综述）。**没有停止判据、没有自适应终止、没有预算控制** | `configs/*.yaml:29` |
| **采样参数** | 讨论 agent `temperature 0.7 / 0.8`，`max_tokens 6000`；综述 agent `temperature 0.4`，`max_tokens 8000` | 各 config `llm:` 段 |
| **输出** | 一段 Markdown proposal 文本 | `extract_txt.py:54` |
| **谁来评价** | ① **多样性**：4 个自动指标（3 个 embedding 几何 + 1 个词汇 n-gram）；② **质量**：LLM-as-Judge（**DeepSeek-V3, temperature 0**，9 维量表）；③ **仅多样性轴**有人工校验（5 名 AI 博士生，实验 87%/82%/81% 一致率） | 论文 §2.3、Table 1、Table 7、Appendix B |
| **评价信号怎么回传给搜索** | **不回流。这不是优化器，是一张观测报表。** 没有任何 arm 之间的反馈环 | — |

### 1.3 ★ 拓扑到底是什么（**直接对应我们的路线 A/B/C**）

**结论：全部是路线 A（人写死的固定拓扑），全部是"通信图"层面的硬编码，没有一个是学出来的。**

拓扑由 AgentVerse 的 `environment.rule` 决定，5 个槽位：`order / visibility / selector / updater / describer`（`configs/*.yaml:32-42`）。仓库里只存在 **3 种拓扑取值**：

| 拓扑名（仓库/论文） | `rule.order.type` | 其它 4 槽 | 语义 |
|---|---|---|---|
| **grouped_sequential**（论文里叫 *Recursive*，Fig 10 里又叫 *Standard*） | `grouped_sequential` | `visibility: all`，其余 `basic` | 3 个 agent 顺序发言，**全部可见全部历史**（全连接稠密图） |
| **ngt** | `ngt`, `leader_idx: 3` | 全部 `ngt` | Nominal Group Technique：第 1 轮"盲写"（各 agent 独立写、互相不可见），第 2–3 轮非 leader 顺序讨论，第 4 轮全员，第 5 轮出 proposal（论文 Appendix I「Topology definitions」） |
| **subgroup_random** | `subgroup_random`, `group_sizes: [1,2,3,2]`, `rounds_per_size: 1`, `leader_idx: -1`, `final_leader: true`, `include_leader_in_subgroups: false` | `visibility: subgroup`, `selector: ngt`, `updater/describer: subgroup` | 每轮把 agent **随机切成不相交子组**，子组内可见、组间不可见；最后由 leader 读最近几轮转录做综述（论文 Appendix E 逐条描述了这个过程） |

**⇒ 对应我们的路线**：
- 路线 A（固定拓扑）：**这三个全部是 A**，而且是"通信可见性图"这一个维度的 A。
- 路线 B（训练学出操作序列）：**完全没有**。没有 policy、没有 RL、没有 action sequence 学习。整个仓库没有一行训练代码。
- 路线 C（固定结构 + 可学习参数）：**完全没有**。所有 YAML 里唯一可变的量是 `temperature`（0.4/0.7/0.8）和 `max_tokens`，且这些是手工枚举的。

### 1.4 ★ 逐个配置差异表（我从 10 个 YAML 实际解析出来的，非照抄 ASSETS.md）

| 配置文件 | `llm.model`（**实际**） | 拓扑 | persona（role_description 哈希） | 讨论 temp / max_tok | 综述 temp / max_tok | `prompts` 键 | 内部 `name` |
|---|---|---|---|---|---|---|---|
| `dsv3_naive_recursive.yaml` | `deepseek-v3` | grouped_sequential | **B**（senior） | 0.7 / 6000 | 0.4 / 8000 | `prompt` | Multi Researchers Academic Discussion… |
| `dsv3_naive_ngt.yaml` | `deepseek-v3` | **ngt** | **B** | 0.7 / 6000 | 0.4 / 8000 | `prompt` | NGT Collaboration – **Early-Career** Researchers ⚠️名实不符 |
| `dsv3_naive_subgroup.yaml` | `deepseek-v3` | **subgroup_random** | **B** | 0.7 / 6000 | 0.4 / 8000 | `prompt` | Randomized Subgroup Collaboration – **Anti-Groupthink** |
| `dsv3_horizontal_recursive.yaml` | **`o1-mini`** ⚠️ | grouped_sequential | **A**（first-year PhD） | 0.8 / 6000 | 0.7 / 8000 | `first_year_phd_prompt` | Early-Career Researchers Only… |
| `dsv3_interdisciplinary_recursive.yaml` | **`gpt-5.1`** ⚠️ | grouped_sequential | **B**（senior！） | 0.7 / 6000 | 0.4 / 8000 | `prompt` | Multi Researchers Academic Discussion… |
| `gpt5_1_interdisciplinary_recursive.yaml` | `gpt-5.1` | grouped_sequential | **B** | 0.7 / 6000 | 0.4 / 8000 | `prompt` | 同上 |
| `gpt5_1_interdisciplinary_ngt.yaml` | `gpt-5.1` | **ngt** | **B** | 0.7 / 6000 | 0.4 / 8000 | `prompt` | 同上 |
| `o1_mini_horizontal_recursive.yaml` | `o1-mini` | grouped_sequential | **A** | 0.8 / 6000 | 0.7 / 8000 | `first_year_phd_prompt` | Early-Career Researchers Only… |
| `o1_mini_horizontal_subgroup.yaml` | `o1-mini` | **subgroup_random** | **A** | 0.8 / 6000 | 0.7 / 8000 | `first_year_phd_prompt` | Early-Career Researchers Only… |

- role 哈希 A = `'A first-year PhD student in AI research with limited research experience in {topic_lower}, bringing fresh curiosity and basic academic foundation…'`（3 个 config）
- role 哈希 B = `'A senior AI researcher with expertise in {topic_lower}, conducting thoughtful self-reflection and literature review.'`（6 个 config）
- **全部 10 个 config 只有 2 种 persona**（A=junior / B=senior-generic）。论文的 5 种 persona 里，**Vertical（混合资历）、Leader-Led（leader 指派）、Interdisciplinary（跨领域专家团）在代码里根本不存在**。
- 归一化掉 `llm.model` 后做全量 JSON 比对，10 个 config 实际只对应 **7 个不同配置**：`dsv3_horizontal_recursive` ≡ `o1_mini_horizontal_recursive`；`dsv3_interdisciplinary_recursive` ≡ `gpt5_1_interdisciplinary_recursive`。

---

## 2. 关键数字

### 2.1 ★ 多样性度量到底是什么（**逐个说清：输入 / embedding / 归一化**）

| 指标 | 输入是什么 | embedding | 怎么算 / 怎么归一化 | 代码位置 |
|---|---|---|---|---|
| **Vendi Score**（主指标） | **一个 proposal 全文**（第 5 轮综述输出）的 embedding；**一个样本 = 一个 proposal** | **OpenAI `text-embedding-3-large`（3072 维）**；超长文本按 **12000/32000 字符切片后 mean-pooling 再 L2 归一化** | `K = X Xᵀ`（cosine 核，**除以 n**）→ 特征值谱 → 指数谱熵 `exp(H(λ))`。**Vendi ∈ [1, n]，n=完全相同提案时=1，n=完全正交时=n** | `compute_vendi_extended.py:250-263`；`compute_vendi_and_order.py:28-41` |
| **Order Parameter φ / Structural Disorder 1−φ** | 同上 | 同上 | `φ = mean_i ⟨x_i, mean(X)⟩`（先归一化均值向量）；报告 **1−φ**（越大越分散） | `compute_vendi_extended.py:266-273` |
| **PCD（Pairwise Cosine Distance / Semantic Dispersion）** | 同上 | 同上 | 上三角所有 `1 − cos` 的均值 | `compute_vendi_extended.py:276-284` |
| **Lexical Uniqueness（W-D-3）** | proposal **纯文本** | **不用 embedding** | lower → `[a-z]+` 切词 → 去停用词 + 去学术套话词表 → 内容 3-gram → **全局 IDF**（对**所有** dataset 联合统计，保证跨条件可比）→ `Σidf(unique) / Σidf(all)` | `compute_vendi_extended.py:21-41, 303-361` |
| **Self-BLEU / Distinct-n** | proposal 纯文本 | 不用 embedding | NLTK `sentence_bleu`（method1 平滑），每条 proposal 以其余全部为参考 | `compute_vendi_extended.py:368-392, 439-454` |
| **Centroid distance 密度**（Fig 5） | proposal embedding | 同上 | **按 topic 分组**求质心（归一化），算每条到本 topic 质心的 cosine 距离，做 KDE | `fig05_distance_density.py:179-190` |
| **UMAP 指纹**（Fig 4） | proposal embedding | 同上 | **先按 topic 做 StandardScaler 白化**（去掉 topic 簇效应，只留结构内散布），再 `umap.UMAP(n_neighbors=30, min_dist=0.1, metric='cosine', random_state=42)` | `fig04_umap.py:174-199` |
| **MMD（Fig 8B）** | proposal embedding，**按轮次** | 同上 | `sklearn.rbf_kernel` **默认 gamma = 1/n_features = 1/3072**，`MMD² = mean(XX)+mean(YY)−2mean(XY)`（**含对角线 = 有偏 V 统计量**，代码注释却写"简单的无偏估计"） | `fig08_high_dim_mmd.py:93-111` |
| **Constructive Conflict Ratio**（Fig 10 右） | **单条发言（turn 级）** | 同上 | 第 1 句为 anchor，`Divergence_t = 1 − cos(e_t, e_1)`；再用 **gpt-4o-mini** 打 1–10 分（DISAGREEMENT/NOVELTY），`C_t = 1[s_t ≥ 7]`，`CCR_t = E[C_t]` | `fig10_topology_dynamics.py:85-111, 126-161`；论文 Appendix D/N |
| **Interaction Density（Fig 11 X 轴）** | **同一场会话内所有 turn** | 同上 | 正则切出每个发言者（`Participant \d+` 或 `PhD Student [A-Z]`）→ 逐句 embedding → **场内的两两 cosine 相似度均值**（= 共识强度） | `fig11_interaction_landscape.py:315-341` |
| **★ Vendi over AGENTS**（Fig 7） | **每个 agent 的全部发言拼接后的文本**（跨 topic 合并） | 同上 | 按 `Participant N` 把发言拼成 N 个 agent 文本 → N 个 embedding → **Vendi over N 个 agent**；理论上限 `y=N`；**Utilization = Vendi / N** | `fig07_scaling_gap.py:98-110, 178-206, 321-329, 349-350` |
| **per-topic Vendi**（附录 H/I/M） | 同一 topic 的 50 个 proposal | 同上 | 先算 topic 内 Vendi，再跨 20 topic 平均（**与主文的全局 Vendi 量纲不同**，论文 Appendix I「Metric note」明确警告） | `figA2_topic_complexity.py:105-127`；`figA3_w3_factorial.py:131-148` |

**⇒ 一句话回答"多样性是什么量纲"**：
> **主指标 Vendi 的量纲 = "一组 proposal 里有效正交语义模态的个数"**，取值 [1, n]，n = 样本数。
> 在 Fig 7 那一支，n 换成了 **agent 数**，于是 Vendi/N = "每个 agent 平均贡献了多少个有效独立视角"。

### 2.2 ★⚠️ **U2 直接命中：它的 embedding 是什么语言 / 什么粒度**

| 判据 | 结论 |
|---|---|
| 语言 | **纯英文**（20 个 ICLR 主题 + 英文 proposal 全文）。BGE 变体是 `BAAI/bge-large-en-v1.5`（**英文**模型）；`all-MiniLM-L6-v2` 也是英文模型 |
| 粒度 | **proposal 全文**（主指标，≈ 数千 token，mean-pooling）；**turn 级**（冲突率、Interaction Density）；**agent 级**（Fig 7）。**从不是句级、不是 token 级、不是 claim 级** |
| 归一化 | L2 归一化；Vendi 内部再除以 n 做谱熵；词汇指标用**全局 IDF**（跨所有条件统一统计） |
| **对我们意味着什么** | 我们已知 **embo-01 的中文句级几何没有分辨率**（U2）。这篇论文的整套主判据 **就是 embedding 几何**（Vendi/1−φ/PCD/UMAP/MMD 全部），只是跑在**英文长文本**上。所以：<br>① **它的"宽度"结论不能翻译到我们的中文句级场景**；<br>② 但它**给了我们一个现成的对照实验**：同一个 MAS 产出，**用 embedding 几何算的宽度** vs **用结构特征算的宽度**，如果前者塌成 1 而后者不塌，就正好复现我们的 U2 并证明"宽度必须用结构量"。<br>③ 它自己做了 embedding 换模型的敏感性（OpenAI ↔ BGE，**排序不变**）—— 这说明**换 embedding 不改变排序，但两个模型都可能是"没有分辨率"的那个**；**它没做"这个指标在无意义场景下会不会也给出相同排序"的对照** |

### 2.3 主结果数字（论文 §3–§5、Appendix B/C/D/F/G/H/I/J/K/L/M）

**（a）五种 persona 的多样性（论文 Table 2 = 仓库 `fig06_quality_diversity.py:39-45` 硬编码值）**

| Cognitive Structure | Vendi | 1−φ | PCD | W-D-3 | Overall Quality（judge=DSV3,T=0） |
|---|---|---|---|---|---|
| **Horizontal (Junior)** | **8.080** | 0.170 | 0.311 | 5.849 | 7.88 |
| **Leader-Led** | **6.932** | 0.161 | 0.296 | 5.096 | 8.03 |
| **Vertical (Mixed)** | **6.082** | 0.146 | 0.272 | 4.131 | 8.32 |
| **Naive** | **5.567** | 0.154 | 0.285 | 4.141 | 7.95 |
| **Interdisciplinary** | **4.647** | 0.119 | 0.225 | 3.623 | **8.50** |

- 质量总表：Table 7 给出 9 维（OQ / Novelty / Workability / Relevance / Specificity / Integration Depth / Strategic Vision / Methodological Rigor / Argumentative Cohesion），每格 n=60，均值±SEM。
- 质量 ANOVA：**F=31.1, p<0.001, η²=0.297**；**Horizontal vs Naive p=0.190（不显著）**；**Horizontal vs Interdisciplinary p<0.001, Cohen's d=−1.46**。
- 质量的各维 η²：OQ 0.297、Nov 0.470、Work 0.385、Rel 0.054、Spec 0.017、IntD 0.188、StrV 0.498、MRig 0.038、ArgC 0.060。
- 论文的"不对称"结论：质量 +0.6 vs 多样性 −3.4（Vendi 8.08 vs 4.65，**74% 相对差**；质量 7.88–8.50，**0.62 分 / 6% 绝对差**）。⚠️ 质量那一侧是**自评污染**（见 §6）。

**（b）人工校验（Table 1 / Appendix B）**
- 5 名 AI 博士生；每 topic 25 组随机成对比较；**每人 100 组**；盲评；问句只有一句："Which proposal set exhibits greater diversity of research ideas?"
- 一致率：**Vendi 87%、1−φ 82%、PCD 81%**。
- 质量**没有**人工校验（论文自己承认）。

**（c）群体规模（Fig 7 / Table 8 / Appendix H）**
- Utilization `Vendi/N`：**1.03 (N=3) → 0.76 (N=5) → 0.47 (N=7)**。
- per-topic 绝对 Vendi（50 proposal/topic，20 topic 平均）：**N=3 3.09 → N=4 3.22 → N=5 3.24 → N=6 3.37 → N=7 3.32**（仓库 `figA2_topic_complexity.py:10-12` 的 docstring 也写了 3.09 / 3.32）。
- N=3→7：**+7.4%，paired t=5.46, p<0.0001，17/20 个 topic 增长**。
- 反驳"每题只有 ~3 个想法"：绝对 Vendi 增长而非封顶；**内在容量与增长率不相关：Pearson r=−0.14, p=0.55**（n.s.）。
- Utilization 的跨 topic 变异很小：**CV=0.07 (N=3) → 0.09 (N=7)**。
- Table 8 完整 20×5 矩阵我在论文里全部抄到了（General ML 3.51→3.53 最宽，Transfer/Meta 2.60→2.74 最窄）。

**（d）时间演化（Fig 8）**
- 指标：Centroid Drift Velocity（相邻轮质心 cosine 距离）、MMD（相邻轮分布差）、Dispersion（轮内到质心平均距离）。
- 结论：Drift ↓、MMD ↓、**Dispersion ↑** ⇒ 论文称之为 **"divergence within convergence"** / "Stable Expansion"（单场会话内局部扩张，但跨会话池整体收缩）。

**（e）拓扑干预（Fig 10 / 附录 I）**
- Fig 10（turn 级）：**NGT 起始轮多样性最高**；**Subgroups 后半程"constructive conflict"密度最高**（`CCR_t`）。
- **附录 I 的 2×2 因子（DSV3，per-topic Vendi，50 run × 20 topic/cell）**：
  - Naive：Recursive **3.125 ± 0.050** vs NGT **2.669 ± 0.062** ⇒ **Δ = −0.456, t = 9.65, p < 0.0001, Cohen's d = 2.21**（**NGT 降低多样性**）
  - Horizontal：Δ = **+0.040, t = 1.07, p = 0.298, d = 0.25**（**几乎无效应**）
  - **交互检验：Δ_N − Δ_H = 0.416, t = −8.18, p < 0.0001**（persona 显著调节拓扑效应）
  - 跨 persona 效应相关：**r = 0.30, p = 0.20（n.s.）** ⇒ "逐 topic 的拓扑敏感性不可跨 persona 迁移"
  - PCD 复核：Naive 0.187±0.014 → 0.158±0.020；Horizontal 0.127±0.024 → 0.122±0.019
  - 表格 10 逐 topic 明细我已全部抄到（20 行）。

**（f）跨模型（附录 M）**
- GPT-5.1 + Interdisciplinary + N=3，per-topic Vendi：**Recursive 2.823 ± 0.238、NGT 2.526 ± 0.253、Standard 1.659 ± 0.185**
- ANOVA：**F(2,57)=137.88, p<0.0001, η²=0.829**；Recursive vs Standard Δ=+1.16 (d=5.47)、NGT vs Standard Δ=+0.87 (d=3.90)、Recursive vs NGT Δ=+0.30 (d=1.21, p=0.002)
- 跨模型（Standard 拓扑，Interdisciplinary，N=3）：**DSV3 3.092 ± 0.097 vs GPT-5.1 1.659 ± 0.081，t=21.49, p<0.0001, Cohen's d=6.97，GPT-5.1 低 46%**，20/20 topic DSV3 更高。（仓库 `figA1_gpt51_cross_topology.py:109` 把 `d = 6.97` 硬编码进了图注）
- 论文还引用了一个 "DeepSeek-V3 拓扑效应 η²=0.544"（附录 M 散文）——**这个数字在全文只出现这一次，没有任何表格给出它**（未验证）。

**（g）温度敏感性（附录 L，2×3 因子，6,000 proposal）**
- per-topic Vendi：Naive **3.387 / 3.092 / 3.445**，Leader-Led **2.787 / 2.285 / 2.788**（T=0.3/0.7/1.0）
- Δ：+0.600 / +0.807 / +0.657，全部 p<0.0001，d = 1.62 / 2.82 / 1.69；**Naive 在 18–20/20 topic 胜出**
- 双因素 ANOVA：**Structure η²=0.420、F=109.13**；**Temperature η²=0.135、F=17.56**；**交互 η²=0.007, F=0.88, p=0.419（n.s.）**
- 相对 gap 稳定在 **17.7%–26.1%**（ANOVA on gap: F(2,57)=1.479, p=0.236）

**（h）prompt 消融（附录 K，2×2，4,000 proposal）**
- 4 格 per-topic Vendi 范围 **2.873–3.092**（**无 dramatic collapse**）
- ANOVA：**Identity η²=0.058, F=4.85, p=0.031（*）**；**Tone η²=0.023, F=1.90, p=0.172（n.s.）**；**Identity×Tone η²=0.011, p=0.348（n.s.）**
- **反直觉关键结果**：在**扁平拓扑**下，**Senior 的多样性反而高于 Junior**（方向与主实验相反）⇒ 崩溃只在"专业 + 层级"同时出现时发生。
- 结论句：Identity+Tone 合计只解释 **9.2%** 的方差，结构效应解释 **42%** ⇒ 差 ~5×。

**（i）异构模型（附录 J）**
- 每个 agent 位置用不同模型：P1=DSV3、P2=GPT-4o、P3=Claude-Sonnet-4
- Table 13 per-topic Vendi：Interdisciplinary 单模型 2.197±0.343 → 异构 2.943±0.297（**+34.0%, p=0.0003, d=2.33**）；Leader-Led 2.285→2.619（+14.6%, p=0.071, d=0.99）；**Horizontal 2.755→2.641（−4.1%, p=0.627, d=−0.29，无收益）**
- Experiment B：mixed-model horizontal，20 topic × 50 run
- Finding 4：GPT-5.1 + Horizontal + Standard，**mean Vendi 2.868, std 0.354**

**（j）"不是参与度问题"的排除（附录 G.4，Table 5）**
- 400 场会话/配置。Leader-Led vs Horizontal：每轮词数 **167.0±37.4 vs 240.6±122.2**（d=−0.70）；**每轮语义新颖度 0.295±0.111 vs 0.306±0.173，p=0.068（n.s.），d=−0.069**；整场总词数 **336.6 vs 1203.2（d=−8.97）**
- Table 6：到 anchor 的 cosine 相似度 **Leader-Led 0.627±0.181 vs Horizontal 0.441±0.211**
- Table 3：Interdisciplinary 924 标题 / 10,411 token / 729 唯一词 / **TTR 0.070**；Horizontal 632 / 6,146 / 958 / **TTR 0.156**（2.2× 差距）；全词表 Jaccard **0.211**（294/1393）

**（k）任务谱（Fig 12）**
- 4 个任务域：Physics（硬约束）/ Policy（软约束）/ Creative（无约束）/ AI Research
- **AI Research 的 bootstrap Vendi > 2.6**（最高内在熵）
- bootstrap：50 次重采样，样本量 0.8N，random_state=42（`fig12_task_spectrum.py:183-191`）

**（l）成本**
- ⚠️ **论文与仓库都没有报任何 token / 美元 / 调用数**。我按配置反推：每次 MAS = 4 轮讨论（≤6000 tok）+ 1 轮综述（≤8000 tok）= **5 次生成调用/会话**；1,000 proposal/配置 ⇒ **约 5,000 次生成调用/配置**；>10,000 proposal ⇒ **>50,000 次生成调用**；外加 ~10,000 次 embedding 调用（3072 维，长文本还要切片）、每条发言 1 次 gpt-4o-mini 判官调用（>10,000 proposal × ~12 turn）、以及 9 维质量评分调用。**embedding API 成本没报**。

---

## 3. ★ 它的「成功标准」是什么

### 3.1 它怎么判定自己成功

- **主判据**：**Vendi Score（per-topic 或全局）**，辅以 1−φ / PCD / W-D-3；**拓扑效应 = 配对 t 检验 + Cohen's d + "n/N topic 胜出计数"**。
- **"多样性更好"的阈值**：**没有绝对阈值**。它用的是"**结构效应 vs 交互项的方差分解**"作为总判据：结构 η²=0.420 ≫ 温度 η²=0.135，交互 η²=0.007（n.s.）。
- **人工校验门槛**：Vendi 与专家判断一致率 87%（>80% 才算过关）。
- **效应量门槛**：附录 I 用 d=2.21 认"真效应"、d=0.25 认"无效应"；附录 M 用 d=5.47/3.90/1.21。

### 3.2 ★ 它有没有写否证条件（**这是它最值得抄的部分**）

**有，而且是成体系的。每一条主要结论都配了一个"替代假设 + 一个能把它推翻的测量"：**

| 它的替代假设 | 它用什么把它否掉 | 数字 |
|---|---|---|
| "每题只有 ~3 个好想法，所以 N>3 没意义" | per-topic 绝对 Vendi 是否随 N 单调增长 | 3.09→3.32，+7.4%，t=5.46 p<0.0001，17/20 topic 增长；容量 vs 增长率 r=−0.14 p=0.55 |
| "崩溃只是 prompt 语气（directive）造成的" | Identity × Tone 2×2 因子 | Tone η²=0.023 p=0.172 n.s.；且 Identity 方向**反转** |
| "崩溃只是参与度不均（Collaborator 少说话）" | 每轮词数 + 每轮语义新颖度 | 词数确实差很多（d=−8.97），但**新颖度 n.s.（p=0.068, d=−0.069）** |
| "温度是混淆" | Structure × Temperature 2×3 因子 | 交互 η²=0.007 p=0.419 n.s.；相对 gap 17.7–26.1% 稳定 |
| "拓扑效应是模型特有" | 跨模型复现 + 异构模型 | GPT-5.1 上 η²=0.829；异构模型对 Horizontal **无收益**（p=0.627） |
| "指标是 embedding 选型的产物" | 换 BGE 重算 + 换 n-gram 阶 + 换 tokenization | 排序在所有变体下不变 |
| "persona 混淆了拓扑效应" | 2×2 因子（人控） | 交互 t=−8.18 p<0.0001 |
| "per-topic 效应不可跨条件迁移" | 跨 persona 效应相关 | **r=0.30, p=0.20（明确写成 n.s.）** |

### 3.3 ★ 它有没有报告"不可分辨"这种结果

**有，而且多处，这是它比大多数论文诚实的地方：**
- 质量的 Horizontal vs Naive：**p=0.190（不显著）**
- prompt Tone：**p=0.172（n.s.）**；Identity×Tone：**p=0.348（n.s.）**
- 附录 I 的 Horizontal 拓扑效应：**p=0.298（n.s.）**
- 跨 persona 效应相关：**r=0.30, p=0.20（n.s.）**
- 每轮语义新颖度：**p=0.068（n.s.）**
- 异构模型 Horizontal：**p=0.627（n.s.）**
- 温度交互：**p=0.419（n.s.）**
- 附录 F 甚至说明："Given the limited number of collaboration modes (n=5), rank correlations trivially reach 1.0 whenever orderings coincide. We therefore report **ordering consistency rather than correlation magnitudes**."（**n=5 时报 Spearman ρ=1.0 是没有信息量的**——这句自我警觉很专业）

### 3.4 ⚠️ 它**没有**做的（我们必须自己补）

- **没有噪声地板 δ**：全文**没有一处**报告"同一份数据、换一个判官/换一版 embedding 指标，结论会不会变"。它的 87% 一致率是"指标 vs 人类"，**不是**"指标 vs 指标版本"。⇒ 我们已知自己的 U4（跨判官提示词版本，净增益从 0/+1/−1 变成 +1/+4/0）——**这篇论文正好缺这一环，而这一环正是我们的差异化空间**。
- **没有否证主结论的"反例组"**：它没有构造"一个已知的无多样性场景"来检验这些指标是否会给高分（我们 U2 的直接对应）。
- **没有 seed 复现**：50 次会话给出的是**会话级**方差，但没有"同一批数据、重新抽一次判官/embedding"的分层方差。
- **没有成本报告**。
- **没有把"人写的固定拓扑"和"学出来的拓扑"对比**（它没有路线 B 的对照臂）。

---

## 4. 自认的局限（**原话优先**）

**论文 §Limitations 全文四条（逐条引用）**：

> **First**, our analysis is centered on scientific proposal generation as a representative ideation task. While this domain offers a structured yet open-ended testbed with high intrinsic entropy, the observed dynamics may not directly transfer to tasks with stronger ground-truth constraints (e.g., mathematical problem solving) or to unconstrained creative writing. We view our setting as a stress test for diversity under hybrid constraints rather than a universal proxy for all generative tasks.

> **Second**, our primary analyses use DeepSeek-V3 as the backbone to isolate the effects of interaction and structure. Cross-model replication on GPT-5.1 and o1-mini (Figure 11; Appendix M) and genuinely heterogeneous-model ensembles that mix DeepSeek-V3, GPT-4o, and Claude-Sonnet-4 (Appendix J) confirm that the structural findings generalise across backbones, but a broader sweep over additional architectures and pretraining families remains future work.

> **Third**, our diversity evaluation relies on embedding-based and lexical metrics, supplemented by human validation on a limited scale. Although agreement with expert judgments is high, **no single metric can fully capture the nuanced notion of creativity or novelty in ideation. Quality scores are obtained via an LLM-as-Judge protocol (DeepSeek-V3, temperature 0) and therefore inherit the standard biases of automatic judges; our human evaluation (Appendix B) validates the diversity axis only.** Our metrics are intended to diagnose relative differences between collaboration modes rather than to provide absolute measures of creativity.

> **Finally**, we analyze interaction protocols with a fixed number of rounds and a default sampling temperature. Although we sweep group size from N=3 to N=7 (Section 5) and verify robustness to temperature across T∈{0.3,0.7,1.0} (Appendix L), **adaptive or dynamically optimized interaction strategies may exhibit different behaviors that are not captured in this study.**

**另外两处它自己打的补丁（原话）**：

> "Because Figure 12 compares only baseline intrinsic entropy across domains and does not re-run the topology manipulations on the other tasks, we do not claim that the structural findings automatically transfer to them."（§6.2）

> "Because cells mix personas across models, this plot is illustrative, and a persona-controlled factorial appears in Appendix I."（Fig 11 题注）

**仓库自认的局限（README）**：

> "To keep the repository lightweight, the following are **not** shipped: Raw proposal `.txt` directories (~10,000 proposals across all configurations) / OpenAI / BGE embedding `.pkl` caches / LLM-as-judge quality evaluation `.jsonl` caches / Aggregated metric CSVs (regenerated from stage 2) / LLM-as-judge batch evaluation scripts (paper-specific infrastructure)."（`README.md:90-97`）

> ⚠️ **它没写的局限（我发现的，见 §6）**：代码与论文的 persona/模型/拓扑对应关系大面积对不上；README 的复现命令跑不通；质量判官与被测模型同源。

---

## 5. ★ 对我们项目的可迁移点

### 5.1 ★★★ **最值得抄：把"多样性"定义成"有效独立模态数"，并给出利用率 = 有效数/N**

`fig07_scaling_gap.py` 的做法是：
1. 用 `Participant \d+` 正则把会话日志切成 **N 个 agent**；
2. 把每个 agent 的全部发言拼成一段文本；
3. 对这 **N 个 agent** 算 Vendi（**不是对 N 个 proposal**）；
4. 画 `Vendi` vs `N` 的理论上限 `y=N`，再画 **Utilization = Vendi/N**。

⇒ **这就是我们"思维面 = 有效信息维度数"的同构物**。区别只在**核函数**：
- 它：核 = 文本 embedding 的 cosine 相似度 ⇒ 有效维度数 = 有效**语义**模态数；
- 我们：核 = **结构特征**（操作序列 / 依据包签名 / 承重结论标识）的相似度 ⇒ 有效维度数 = 有效**承重**维度数。

**能省我们什么**：省掉一整个"怎么把多臂结果折成单一宽度数字"的设计论证。**Vendi/N 这个量纲和"理论上限=N"的图，直接可以搬到我们的净维度增益协议里**（把 `y=N` 换成 `y=工作流臂数`）。
**要改什么**：把 embedding 换成结构特征向量（这是我们和 U2 挂钩的关键一步），并**同时报告两版**（embedding 版 vs 结构版）⇒ 这就是我们的对照实验。

### 5.2 ★★★ **"跨 agent 聚合"是一个我们没用过的测量单位**

我们目前的宽度测量基本都是"对一批答案"算。而它提供的是**对一批 agent** 算。这两个量纲回答不同的问题：
- 对 proposal 算 ⇒ "这一轮产出有多少种想法"
- 对 **agent** 算 ⇒ "这 N 个 agent 里，有几个真正贡献了**互相正交**的视角"

⇒ **后者更接近"思维面"**：一个 N 人的团队如果 3 个人说一样的话，Vendi(agents) 就掉到 2–3，而 Vendi(proposals) 可能还很高（因为综述 agent 措辞不同）。**我们应当把"agent 级有效维度"作为第二个主指标**——而且它的输入是**结构可归因的**（谁说了什么、执行了什么 op、引用了哪些依据），天然绕开 embedding。

### 5.3 ★★ **附录 I 的 2×2 因子协议是一份现成的统计模板**

它的做法（`figA3_w3_factorial.py:195-243, 437-479`）：
1. 固定模型、只变 2 个因素（persona × topology），**每格 20 topic × 50 run**；
2. **per-topic 内**先算指标，再跨 topic 配对检验（`stats.ttest_rel`）；
3. 同时报 **Δ、p、% 变化、Cohen's d、wins 数（n/N topic 胜出）**；
4. 再做**交互检验**（两个 Δ 的配对 t）和**跨条件效应相关**（逐 topic Δ 的 Pearson r）。

⇒ **建议直接抄进我们的测量协议**：
- 我们的"wins 数"版判据（每个 DEV 题上哪个臂胜出，n/12 计数）——**它就是这么做的**；
- 我们的"净维度增益"如果只在部分题上出现，**就应该报跨题效应相关 r 与 p**，而不是只报平均 Δ；
- 它的"**persona 显著调节拓扑效应（交互 p<0.0001）**"提醒我们：**A/B/C 三条路线的比较不能混着报**，必须先做交互检验确认"路线 × 臂"不是交互项。

### 5.4 ★★ **"排除替代解释"的三件套模板**

它对每个机制都配了一个排除实验（§3.2 表）。我们可以直接照搬这个结构到我们的三件套：
- 我们的"承重信息变多"会不会只是"**写得更长**"？→ 它对 Leader-Led vs Horizontal 的处理（词数差 d=−8.97，但**语义新颖度 n.s.**）就是范式：**用一个"体量代理量"和一个"实质代理量"同时测，如果体量变了而实质没变，机制就被否掉**。我们的对应：claim 长度 / token 数 vs 承重结论数。
- 我们的"决策变了"会不会只是"判官更宽松"？→ 需要它那种"换个判官/换套指标仍然同序"的鲁棒性检验。
- 我们的"DEV 题太简单"会不会只是"**题只有这么多个答案**"？→ 它的 Appendix H 是范式：先测"内在容量"，再看"容量能不能预测增长率"，**r=−0.14, p=0.55 ⇒ 容量不预测 ⇒ 饱和是结构性的**。我们的对应：先测每道 DEV 题"可承重结论空间的大小"，再看它能不能预测净维度增益；**如果相关，就说明我们的地板效应是题的问题而不是架构的问题**。

### 5.5 ★★ **指标换型鲁棒性应作为最低证据门槛（Table 2 / Appendix F）**

它对每个主结论都做了：换 embedding 模型（OpenAI ↔ BGE-large）、换指标族、换 n-gram 阶、换 tokenization，**只报"排序是否不变"**。
⇒ **我们的协议里应加一条硬门槛**：任何宽度指标，至少要通过 ①换 embedding/编码器 ②换归一化 ③换判官提示词版本 ④加一个"已知无多样性"对照组。**它只做到了第 ①②项，第 ③④项正是我们的 U2/U4 缺口。**

### 5.6 ★ **它缺的那块 = 我们的机会：噪声地板 δ + 反例组**

- 它报 87% 的"指标 vs 人"一致率，但**没报"指标版本之间"的稳定性**。我们要报的是：**同一批产出，换一版判官 prompt / 换一版 embedding，Δ 的符号会不会翻**。这正是我们已经实测会翻的（U4）。
- 它没做**反例组**（一个已知没有多样性的场景，指标是否也给高分）。我们已经有了 U2 的实测（embo-01 中文句级把 27 条断言压成 1 条）⇒ **这就是一个天然的反例组**，可以正式写进论文当"指标无效性证明"。

### 5.7 ★ 成本模型（我们该报而它没报）

按其配置反推：**5 次生成调用/会话**（4 讨论 + 1 综述），每次 ≤6000/8000 tok；1,000 proposal/配置；>10,000 proposal ⇒ **>50,000 次生成调用** + ~10,000 次 embedding 调用（长文本还要切片，即**一次 proposal 可能多次 embedding**）+ 每 turn 一次 gpt-4o-mini 判官 + 9 维质量评分。
⇒ 我们的成本表可以按这个结构填（调用数·token·美元），并明确"embedding 成本常常被忽略"。

### 5.8 关于路线 A/B/C 的直接结论

- **它只提供路线 A 的证据**（而且是"通信可见性图"这一个维度的 A）。
- **它没有 B 的对照** ⇒ 我们的路线 B（学出来的 op 序列）**没有现成对照可抄**。
- **它提示了一个我们该做的对照**：既然"拓扑=谁看得见谁"会改变多样性，那么**路线 B 学出来的 op 序列 vs 路线 A 写死的 op 序列**，是不是也应该在**同一个"可见性图"指标**下比？⇒ **它暗示"拓扑"应该被当成一个可测量的一等公民，而不是一个设计细节。**

---

## 6. ★ 不可迁移 / 会误导我们的点

### 6.1 ⚠️⚠️ **U2 直接命中：它的主判据就是 embedding 几何**

- 主指标 Vendi / 1−φ / PCD / UMAP / MMD **全部**建立在 **OpenAI `text-embedding-3-large` 的 3072 维英文 embedding** 上。
- 粒度是**整篇 proposal**（不是句、不是 claim、不是 token）。
- 它自己的敏感性分析只证明"**换 embedding 排序不变**"——**但如果两个 embedding 都无分辨率，换不换都一样**。它**没有**做"在一个已知无意义的多样性场景下，这个指标会不会照样给出高区分度"的检验。
- ⇒ **在我们的中文句级场景，这套指标不能当主判据**（embo-01 已被我们实测压成 1 条）。我们只能把它当**参照系 / 对照组**，不能当方法。

### 6.2 ⚠️⚠️ **U6 自评污染：质量那一轴是同源自评**

- 论文 Table 7 题注原文：*"Table 7: Quality scores (1–10) across five persona structures, evaluated by **DeepSeek-V3 (LLM-as-Judge, temperature 0)**."*
- 而 **DeepSeek-V3 同时是主实验的生成 backbone**（附录 I / L 的所有 DSV3 臂）。
- ⇒ **判官 = 被测模型**。论文自己承认："Quality scores are obtained via an LLM-as-Judge protocol (DeepSeek-V3, temperature 0) and therefore inherit the standard biases of automatic judges; our human evaluation (Appendix B) validates the diversity axis only."
- ⇒ ★ **它的旗舰结论"质量只差 0.6，多样性差 3.4，所以权衡是不对称的"完全建立在自评的质量轴上**。**我们不能引用这个不对称性作为已确立事实。**
- 多样性轴**不是**自评（OpenAI embedding + 人工校验 87%）⇒ 这一侧相对干净。
- 立场/冲突判官用 `gpt-4o-mini`，与被测（DSV3 / GPT-5.1 / o1-mini）不同家但同厂；**GPT-5.1 那批是被 GPT 家模型判的**，次一级风险。

### 6.3 ⚠️⚠️ **U7：它数的是"角度"，不是"承重维度"**

- 它的 Vendi = "有效正交**语义模态**数"。它**从不**检查一条信息是否**可核验**、是否**改变了决策**。
- ⇒ 它的 "Horizontal 8.08" 与我们的 "思维面宽度" **是两个不同的量**，只是共用了"多样性/宽度"这个词。
- ⇒ 它说"Junior 团队想法更多样"**完全不能推出**"Junior 团队产出了更多可承重的信息维度"。**这正是我们项目的核心区分点。**
- ⇒ 它的"Persona/Topology 影响多样性"的因果链，对我们**只提供"环境假设"（结构会影响产出分布），不提供"结构会影响承重维度"的证据**。

### 6.4 ⚠️ **"多样性"在它内部有两种互相矛盾的量化**

- **轮内（turn 级）**：Fig 9/10 的 `Divergence` / `CCR`。结论：**NGT 起始轮最高、Subgroups 后半程最高**（"process interventions effectively disrupt consensus collapse"）。
- **轮间（proposal 池级）**：附录 I 的 per-topic Vendi。结论：**NGT 把多样性从 3.125 压到 2.669（p<0.0001, d=2.21）**，对 Horizontal 则**毫无作用**（p=0.298）。
- ⇒ **同一个"NGT"干预，在两种量纲下符号相反。** 论文正文只强调前者，附录才给出后者，但正文没做调和。
- ⇒ ★ **这是最容易骗我们的一条**：如果我们把"多样性更好"等价于"指标更高"，就会踩进"选一个量纲、挑对自己有利的那一侧"的坑。**我们必须先规定量纲，再看结论。**

### 6.5 ⚠️ **Fig 8B 的 MMD 带宽是退化的（我实跑验证过）**

- `fig08_high_dim_mmd.py:93-111` 用 `sklearn.metrics.pairwise.rbf_kernel(..., gamma=None)` ⇒ sklearn 默认 `gamma = 1/n_features = 1/3072`。
- 在 **L2 归一化的 3072 维向量**上，两个随机向量的平方 L2 距离约 2.0 ⇒ `exp(-2/3072) = 0.99935` ⇒ **RBF 核 ≈ 单位阵**，只有对角线有信息。
- **我的实测**（合成数据，`vendi-score` 0.0.3 + sklearn 1.9.1）：
  - 两组随机向量：MMD ≈ **2.7e-05**
  - 一组是另一组的近复制（eps=1e-4）：MMD ≈ **3.9e-10**
  - 中等扰动（eps=0.05 / 0.2 / 0.5）：MMD ≈ **1.7e-05 / 2.5e-05 / 2.5e-05**（**不单调**，eps=0.05 反而比两组独立随机更小）
  - 换成中位数启发式带宽（`gamma=1/(2h)`）后同一批数据的 MMD 变成 **0.011–0.016**，**有分辨力**。
- 且它是**有偏** V 统计量（含对角线），而代码注释写的是"简单的无偏估计"——**注释与实现不符**。
- ⇒ **结论：不要把 Fig 8B 的 MMD 曲线当证据。** 论文"Distribution Shift (MMD) reduces, confirming structural convergence"这句，在实现层面站不住（**真实数据未 shipped，我无法验证真实数值量级——标"未验证"**）。

### 6.6 ⚠️ **"Standard" vs "Recursive" 的拓扑标签在论文里是乱的，而且关键数字没有对应 config**

- 论文 §5.2 把三个拓扑写成 "**Standard**, NGT, Subgroups"；附录 I 把基线写成 "**Recursive**: … This corresponds to **grouped_sequential** order with **all** visibility"；附录 K/L 又写 "flat peer-to-peer topology (**Standard, no leader**)"，且 "Naive (Multi): … standard sequential discussion (N=3, **Standard** topology). This corresponds to the 'Naive' baseline in the main paper."
- ⇒ **"Naive @ Standard"（附录 L 的 3.092）与 "Naive @ Recursive"（附录 I 的 3.125）指的是同一个 `grouped_sequential + all` 配置**，只是两次测量的微小差异。
- 而附录 M Table 25 把 GPT-5.1 的 **Recursive = 2.823** 和 **Standard = 1.659** 列为**两个不同的格**，并用它得出"Recursive ≫ NGT ≫ Standard"、以及跨模型"DSV3 3.092 vs GPT-5.1 1.659，d=6.97，GPT-5.1 低 46%"。
- ⇒ ⚠️ **这个 1.659（论文最出名的"Compute Efficiency Paradox"数字）在仓库里没有对应 config**：`gpt5_1_interdisciplinary_*` 只有 Recursive 和 NGT，没有 Standard。**该数字不可从 shipped 代码复现。**
- ⇒ **"Standard" 到底是不是"Recursive"之外的第四种拓扑，论文没说清。** 标为"未解决/未验证"。

### 6.7 ⚠️ **仓库层面的可复现性缺陷（我逐条验证过）**

| # | 问题 | 证据 |
|---|---|---|
| 1 | **README 的复现命令跑不通**：`python simulation/launch_scientist.py --config simulation/configs/dsv3_naive_recursive.yaml` —— `launch_scientist.py` 的 argparse **没有 `--config`**（`launch_scientist.py:29-92`），我实测报 `error: unrecognized arguments: --config`。而且该文件是 SakanaAI/AI-Scientist 的 launcher **原样拷贝**（跑 nanoGPT 实验 + LaTeX 写作 + review），**与 MAS 流水线无关** | 实测 argparse 复现 |
| 2 | **真正的 runner 不接受 config 参数**：`run_dynamic_topic.py:82` 硬编码读 `Path(__file__).parent / "config.yaml"`，而该文件**不在仓库里**（只有 `configs/*.yaml`）。⇒ 复现链断裂 | `run_dynamic_topic.py:82`；`ls simulation/` |
| 3 | **两个 config 名实不符**：`dsv3_horizontal_recursive.yaml` 实际 `model: 'o1-mini'`；`dsv3_interdisciplinary_recursive.yaml` 实际 `model: 'gpt-5.1'`。这与 `ASSETS.md:30-44` 的"条件→config"表直接冲突 | 我解析 10 个 YAML 得到 |
| 4 | **"Interdisciplinary" persona 在代码里根本不存在**：`dsv3_interdisciplinary_recursive.yaml` 与 `dsv3_naive_recursive.yaml` 的 **3 个讨论 agent 的 role_description 完全相同**（"A senior AI researcher with expertise in {topic_lower}"），差别只有 ①模型 ②综述 agent 的提示词措辞。⇒ **论文最出名的"Horizontal 8.08 vs Interdisciplinary 4.65"在 shipped 代码里没有对应实现** | 逐 agent 逐键 diff（只有 `llm` + 综述 `prompt_template` 不同） |
| 5 | **`run_dynamic_topic_subgroup.py` 不是"专用 runner"**：与 `run_dynamic_topic.py` 的唯一差别是加了 `--seed` / `--seed_offset`（以及 `PYTHONHASHSEED`/`random.seed`/`np.random.seed`）。**拓扑切换完全靠 config 里的 `rule` 字段**，与 runner 无关。`ASSETS.md:44` 的"Subgroup uses the dedicated run_dynamic_topic_subgroup.py"是误导 | `diff -u` 全文 |
| 6 | **fig02 与 metric 脚本的 CSV schema 不匹配**：`fig02_pareto_landscape.py:111` 读 `row['topic']`，但 `compute_vendi_sec_models.py:180-187` 写的 CSV **没有 `topic` 列**（按 dataset 聚合）⇒ fig02 会 KeyError | 代码对照 |
| 7 | **仓库里有论文里没有的模型**：`fig02_pareto_landscape.py:38-42` 和 `compute_vendi_sec_models.py:24` 都含 **Grok-4**，但论文正文**一次都没出现 "Grok"**（我在 LaTeXML 正文里大小写不敏感 grep = 0 命中；唯一的 "grok" 出现在第三方 Pith 综述的元数据 `grok-4.3`，是**审稿模型名**，不是论文的模型）。论文用的是 DSV3 / GPT-5.1 / o1-mini / GPT-4o / Claude-Sonnet-4 | grep |
| 8 | **`requirements.txt` 漏依赖**：`sentence-transformers` 被 `compute_proposal_metrics.py:57` 和 `compute_vendi_sensitivity.py:105-110` 依赖（后者是 BGE 敏感性分析**唯一**的 embedding 来源），但 **不在 requirements.txt** | 文件对照 |
| 9 | **论文引用了一个没有出处的数字**：附录 M 说 "the topology effect is stronger for GPT-5.1 (η²=0.829) than for DeepSeek-V3 (**η²=0.544**)"，但 **0.544 在全文只出现这一次**（搜索快照确认恰好 1 处命中，且是在正文散文里；LaTeXML 纯文本因数学被替换成 `MATH` 而 grep=0），**没有任何表格给出这个数** | 附录 M 散文 + 全文计数 |
| 10 | **论文正文指错附录**："Specific experimental setups … are detailed in **Appendix N.2**"，但 N.2 是 stance judge 的 prompt template，不是实验设置表 | 论文 §2.2 vs 附录 N 目录 |

### 6.8 ⚠️ 其它不可迁移

- **样本量与量纲不匹配**：它的 "Vendi = 8.08" 是在 **50 个 proposal** 上算的，我们的 DEV 集是 **12 份**。⇒ Vendi 在 n=12 上的分辨率与 n=50 完全不同，**不能拿它的绝对值当我们的目标值**。
- **"50 次独立会话"是它的降噪手段**：同一个 topic 跑 50 次再平均 ⇒ 它的"每 topic 读数"本身就是 50 次平均的结果。我们没有这个预算 ⇒ **我们的 per-item 噪声会大得多**（这正是我们地板效应的来源之一）。
- **成本模型缺 embedding**：它没算 embedding 的钱，而 embedding 在长文本 proposal 上要切片多次。**预算表要单独列这一项。**

---

## 7. 逐字摘录（原话，标出处）

> **① 论文 §Limitations（第三条）**
> "our diversity evaluation relies on embedding-based and lexical metrics, supplemented by human validation on a limited scale. Although agreement with expert judgments is high, **no single metric can fully capture the nuanced notion of creativity or novelty in ideation. Quality scores are obtained via an LLM-as-Judge protocol (DeepSeek-V3, temperature 0) and therefore inherit the standard biases of automatic judges; our human evaluation (Appendix B) validates the diversity axis only.** Our metrics are intended to diagnose relative differences between collaboration modes rather than to provide absolute measures of creativity."

> **② 论文 §2.3（Table 1 附近）**
> "We validated these metrics via human evaluation (see Appendix B) using pairwise comparisons by five expert annotators: the Vendi Score matched expert diversity judgments in 87% of cases, with all three embedding-based metrics exceeding 80% agreement."

> **③ 论文 §5.2（拓扑干预结论）**
> "Figure 10 (Left) shows that NGT (green) initiates with the highest semantic diversity, significantly outperforming the Standard baseline (red). This confirms that the 'blind-writing' phase of NGT effectively mitigates production blocking and anchoring effects. Meanwhile, the Subgroups topology (cyan) demonstrates a unique 'resilience spike' in diversity midway through the discussion."

> **④ 论文 附录 I（Table 10 题注，与 ③ 方向相反）**
> "Under the Naive persona, the topology effect is large and consistent across all 20 topics; under the Horizontal persona, the effect is near zero."

> **⑤ 仓库 `analysis/figures/fig11_interaction_landscape.py:781-787`（被注释掉的 `compute_interaction_density`）**
> ```python
> # def compute_interaction_density(chat_dir, debug=False):
> #     """
> #     计算 Interaction Density (Consensus Strength).
> #     逻辑：读取 outputs 里的对话，计算所有发言两两之间的平均相似度。
> #     相似度越高 = Consensus 越强 (Rigid)。
> #     相似度越低 = Interaction 越发散 (Wild)。
> #     """
> ```

> **⑥ 仓库 `analysis/figures/fig07_scaling_gap.py:325-329`（"利用率"定义的出处）**
> ```python
> # 计算 Utilization Ratio (利用率)
> # Ratio = Actual Vendi / Theoretical Max (N)
> # 这是一个 [0, 1] 的无量纲指标，可以安全地比较
> df_agg["Utilization"] = df_agg["mean"] / df_agg["Group Size"]
> ```

---

## 8. 读完后我自己的一句判断

**最值得抄的是 `fig07_scaling_gap.py` 的整套框架**——它把"多智能体系统有没有把想法空间想宽"换算成了一个**和我们的量纲同构**的数：**在 agent 粒度上算 Vendi，再用 `Vendi/N` 做"利用率"，理论上限画成 `y=N`**（我实跑验证了 vendi-score 0.0.3 的语义：N 个完全相同向量 Vendi=1.0，N 个正交向量 Vendi=N）。它唯一的关键假设是**核函数**——它用英文 embedding 的 cosine 核，我们可以用**结构特征的核**；**如果把同一个框架的核从 embedding 换成"操作序列/依据包签名"，就得到一个完全不用 embedding 的"有效承重维度数 + 利用率"**⇒ 这既是我们的度量方案，也是我们**证明 U2（embedding 几何无分辨率）的对照实验载体**：同一批产出，embedding 版 Vendi 塌成 1、结构版 Vendi 不塌 ⇒ 结论就是"宽度必须用结构量"。

**最容易骗我们的恰好是它的招牌动作**：它在**同一篇论文里用两种量纲测"多样性"，而且符号相反**（轮内 turn 级：NGT 最好；轮间 proposal 池级：NGT 把多样性从 3.125 压到 2.669、d=2.21、p<0.0001），正文只强调对自己有利的轮内口径，附录才给出轮间口径却不调和；再加上它最出名的两个数字（"Interdisciplinary 4.65" 和 "GPT-5.1 1.659, d=6.97"）**在 shipped 代码里都没有对应实现**（前者根本没有跨领域专家的 config，后者根本没有 "Standard" 这个 config），以及它的"质量只差 0.6 / 多样性差 3.4"这条旗舰结论**完全建立在与被测模型同源的 LLM 判官上**（DSV3 判 DSV3）——**⇒ 我们若把"它证明了多样性会崩溃"当成前提来设计我们的架构，很可能继承的是它自己都没调和的那一半口径，以及一个自评污染的质量基线。**

---

## 附：来源清单

**访问日期：2026-10-21（全部条目）**

### 论文
| 类型 | URL | 状态 |
|---|---|---|
| arXiv HTML 全文 v2（56 页 LaTeXML） | `https://arxiv.org/html/2604.18005v2` | ✅ 已抓取全文（1,022,591 bytes HTML → 203,007 chars 文本） |
| arXiv abs 页 | `https://arxiv.org/abs/2604.18005` | ✅ 已抓取（元数据确认：arXiv:2604.18005v2 [cs.MA], 21 Apr 2026） |
| arXiv API | `http://export.arxiv.org/api/query?id_list=2604.18005` | ❌ **未取到**（返回 0 bytes / upstream connect error） |
| arXiv PDF | `https://arxiv.org/pdf/2604.18005` | ❌ **未取到**（未下载 PDF；改用 HTML 全文，表格数字以 LaTeXML 文本 + 搜索快照交叉核对） |
| 第三方 AI 综述（pith.science） | `https://pith.science/paper/2604.18005` | ⚠️ 仅作为**搜索快照**读入（`/workspace/lab/routes/LIT/_raw/mas_div_paper_searchdump.txt`）；**其 "Main Results" 汇总表把 Leader-Led / Vertical 的 Vendi 对调了（写成 6.08 / 6.93），与论文 Table 2 及仓库 fig06 硬编码值（6.932 / 6.082）矛盾 ⇒ 该表不作为依据，只当"第三方摘要有误"的例证** |
| alphaXiv 中文版 | `https://www.alphaxiv.org/zh/abs/2604.18005` | ✅ 读到摘要译文（用于交叉验证摘要表述） |

### 仓库（GitHub API + raw.githubusercontent）
| 文件 | 路径 | 状态 |
|---|---|---|
| 目录树 | `https://api.github.com/repos/Xtra-Computing/MAS_Diversity/git/trees/HEAD?recursive=1` | ✅ 已拉最新（`truncated: false`，39 个 blob） |
| README | `README.md` | ✅ 全文读 |
| ASSETS | `ASSETS.md` | ✅ 全文读 |
| 依赖 | `requirements.txt` / `LICENSE` / `.gitignore` | ✅ 读 |
| 人格映射 | `docs/persona_mapping.md` | ✅ 全文读 |
| 指标 | `analysis/metrics/compute_proposal_metrics.py` | ✅ 全文读 |
| 指标 | `analysis/metrics/compute_vendi_and_order.py` | ✅ 全文读（325 行） |
| 指标 | `analysis/metrics/compute_vendi_extended.py` | ✅ 全文读（1503 行，含 §1–550 逐行 + 剩余函数清单） |
| 指标 | `analysis/metrics/compute_vendi_sec_models.py` | ✅ 全文读 |
| 指标 | `analysis/metrics/compute_vendi_sensitivity.py` | ✅ 全文读（§72-228 embedding、§470-700 相关性/main） |
| 图 | `analysis/figures/fig02_pareto_landscape.py` | ✅ 全文读 |
| 图 | `analysis/figures/fig03_persona_bar.py` | ✅ 全文读 |
| 图 | `analysis/figures/fig04_umap.py` | ✅ 全文读 |
| 图 | `analysis/figures/fig05_distance_density.py` | ✅ 全文读 |
| 图 | `analysis/figures/fig06_quality_diversity.py` | ✅ 全文读 |
| 图 | `analysis/figures/fig07_scaling_gap.py` | ✅ 全文读 |
| 图 | `analysis/figures/fig08_high_dim_mmd.py` | ✅ 全文读 |
| 图 | `analysis/figures/fig09_trajectory.py` | ✅ 全文读 |
| 图 | `analysis/figures/fig10_topology_dynamics.py` | ✅ 全文读 |
| 图 | `analysis/figures/fig11_interaction_landscape.py` | ✅ 全文读（984 行，§1-620 + 注释段 622-984） |
| 图 | `analysis/figures/fig12_task_spectrum.py` | ✅ 全文读 |
| 图 | `analysis/figures/figA1_gpt51_cross_topology.py` | ✅ 全文读 |
| 图 | `analysis/figures/figA2_topic_complexity.py` | ✅ 全文读 |
| 图 | `analysis/figures/figA3_w3_factorial.py` | ✅ 全文读 |
| 配置 | `simulation/configs/dsv3_naive_recursive.yaml` | ✅ 全文读 + 结构化解析 |
| 配置 | `simulation/configs/dsv3_naive_ngt.yaml` | ✅ 同上 |
| 配置 | `simulation/configs/dsv3_naive_subgroup.yaml` | ✅ 同上 |
| 配置 | `simulation/configs/dsv3_horizontal_recursive.yaml` | ✅ 同上 |
| 配置 | `simulation/configs/dsv3_interdisciplinary_recursive.yaml` | ✅ 同上 |
| 配置 | `simulation/configs/gpt5_1_interdisciplinary_recursive.yaml` | ✅ 同上 |
| 配置 | `simulation/configs/gpt5_1_interdisciplinary_ngt.yaml` | ✅ 同上 |
| 配置 | `simulation/configs/o1_mini_horizontal_recursive.yaml` | ✅ 同上 |
| 配置 | `simulation/configs/o1_mini_horizontal_subgroup.yaml` | ✅ 同上 |
| runner | `simulation/run_dynamic_topic.py` | ✅ 全文读 |
| runner | `simulation/run_dynamic_topic_subgroup.py` | ✅ 全文读 + 与上一文件 `diff -u` |
| runner | `simulation/launch_scientist.py` | ✅ 全文读 + **实测 argparse 复现失败** |
| 工具 | `simulation/extract_txt.py` | ✅ 全文读 |

### 本地落盘
- 仓库全量：`/workspace/lab/routes/LIT/_raw/mas_div/`（39 个文件 + `tree.json`）
- 论文 HTML：`/workspace/lab/routes/LIT/_raw/mas_div_paper.html`；转文本：`/workspace/lab/routes/LIT/_raw/mas_div_paper.txt`
- 搜索快照：`/workspace/lab/routes/LIT/_raw/mas_div_paper_searchdump.txt`

### 我实际跑过的东西
| 动作 | 结果 |
|---|---|
| `pip install vendi-score==0.0.3`（阿里云镜像）+ 复算论文的 Vendi / order φ / PCD 公式 | ✅ 跑通。验证：N 个相同向量 Vendi=**1.0**、φ=1.0、PCD=0.0；N 个正交向量 Vendi=**N**、PCD=1.0；3072 维随机向量 n=3/5/10/20/50 ⇒ Vendi≈n（利用率 0.99–1.00） |
| 复核 `vendi-score` 源码语义（`score_K` → `weight_K(K, None)` = `K/n` → `exp(H(λ))`） | ✅ 确认 Vendi ∈ [1, n]，"有效正交模态数" |
| `fig08` 的 MMD 带宽诊断（合成 3072 维 L2 归一化向量） | ✅ 跑通。`gamma=None`（=1/3072）下 MMD 落在 **1e-05 量级**，近复制才掉到 **1e-10**，中等扰动**不单调**；换中位数启发式带宽后 MMD 变为 0.011–0.016 有分辨力。⇒ 判据：Fig 8B 曲线不可作证据（**真实数据量级未验证——数据未 shipped**） |
| `analysis/metrics/compute_proposal_metrics.py` 端到端 | ✅ 跑通（合成 `paper_txts` 目录 + TF-IDF fallback），产出 `metrics_summary.csv`（n_samples=24, n_topics=2, embedding=tfidf） |
| `analysis/figures/fig03_persona_bar.py` 端到端 | ✅ 跑通（用 Table 2 数值播种 `metrics_vendi_order.csv`），产出 `bar_chart_metrics_final.png` |
| `python simulation/launch_scientist.py --config …` | ❌ **实测失败**：`error: unrecognized arguments: --config …`（与 §6.7 第 1 条一致） |
| 10 个 YAML 的结构化解析（模型/拓扑/agent/温度/角色哈希/归一化后全量比对） | ✅ 跑通 ⇒ 产出 §1.4 差异表与 §6.7 的 3/4/5 条结论 |

### 明确**没有**取到 / 没有跑的东西
- **原始 proposal 语料（~10,000 条）、embedding 缓存、质量评分 JSONL/JSON、聚合 CSV**：仓库 README 明示不 ship ⇒ **所有需要真实数据的指标（Vendi/PCD/1−φ/W-D-3/UMAP/MMD/Interaction Density/质量分）我都没能在真实数据上复算**。文中所有这些数值均标注为"论文/仓库代码给出"，非我实测。
- `fig06_quality_diversity.py:16-19` 读的 `~/AI-Scientist/proposals/tsne_code/quality_persona_results.json`（仓库外绝对路径）⇒ 未取到。
- `fig02` 依赖的 `sec_models/ai_researcher_multi_topic_*/_OVERALL_AVERAGES.txt` ⇒ 未取到。
- **Grok-4** 的全部数据与论文里的任何出处 ⇒ 未取到（论文全文无 "Grok"）。
- 论文 **PDF**（仅取到 HTML 全文本）⇒ 表格的**排版对齐**未核对；数字以 LaTeXML 文本 + 搜索快照双向核对。
- 论文 **Appendix G.1–G.3 的完整转录本**、**Table 26 的 20 个 ICLR 主题全名与描述**、**Figure 1/9/13/14/15 的图像本身** ⇒ 未逐字读。
- 附录 M 的 "DSV3 拓扑效应 η²=0.544" ⇒ 全文无出处，**未验证**。
- 论文中 "Standard"（GPT-5.1, Vendi=1.659）到底对应什么拓扑 ⇒ **论文未定义，仓库无 config，未解决**。
- **我没有**在本沙盒跑任何 LLM 生成或 OpenAI embedding 调用（无 OpenAI key；环境只有 OpenRouter / MiniMax / GitHub token），故 §2 中所有 embedding 相关的数字**均非本地复算**。
