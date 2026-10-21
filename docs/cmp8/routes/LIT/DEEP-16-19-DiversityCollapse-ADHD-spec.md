# DEEP-16-19 · 「多样性崩溃」+ ADHD 项目 —— 可直接抄进我们代码的规格

> **产出性质**：规格（可直接落码），不是摘要。
> **对象**：
> 1. **MAS_Diversity / Diversity Collapse** — Nuo Chen, Yicheng Tong, Yuzhe Yang, Yufei He, Xueyi Zhang, Qingyun Zou, Qian Wang, Bingsheng He. *Findings of ACL 2026*, pp. 251–306. DOI `10.18653/v1/2026.findings-acl.13` ｜ arXiv `2604.18005` ｜ 代码 `Xtra-Computing/MAS_Diversity`（MIT）
> 2. **ADHD** — `UditAkhourii/adhd`（MIT）＋ 文档站 `adhd.mintlify.site` ＋ 预印本 `adhdstack.github.io`（Akhouri Raj, U. 2026）
>
> **本文件相对既有 16 / 19 / 20 / 21 / 22 号精读的关系**：
> - **纠正** `16_2026.findings-acl.13.md` §主读数二 的一个**未核实的转述**（"绝对 Vendi 单调上升"）→ 见 §4.2。
> - **补齐** `22_MAS_Diversity.md` §2.1 只列了指标、**没做"我们该用哪个"的判定** → §3 给结论 + 可落码规格。
> - **补齐** `19/20/21_adhd*` 已发现但**未给修法**的帧选择缺陷 → §5.2 给**可落码的替换实现**。
> - **新增** 该文件族里没有的一节：**§2.3 把"专家 persona"与"权威结构"拆成两个变量的 2×2 落码规格**。

---

## 0. 我实际读了什么（可核性声明）

| 来源 | 读到的东西 | 方式 |
|---|---|---|
| 论文全文 | **ar5iv 完整 HTML**（945 KB，转换出 **2,565 行**纯文本，`paper.txt`）→ 读了 §1–§8、Limitations、Appendix A–O **全部 15 个附录** | `curl https://ar5iv.labs.arxiv.org/html/2604.18005`（arXiv PDF 端点本沙盒下载出的文件 **xref 损坏**，`pdftotext` 报 "Couldn't find trailer dictionary"，故改用 ar5iv） |
| 论文 PDF | `https://aclanthology.org/2026.findings-acl.13.pdf` —— 见 `DEEP-16-19-quotes.md` 页码列 | `curl`（页码由该 PDF 复核） |
| `MAS_Diversity` 仓库 | `README.md` / `ASSETS.md` / `docs/persona_mapping.md` / **4 个 metrics 脚本全文** / **5 个 simulation config 全文** / `launch_scientist.py` / `run_dynamic_topic.py` / `run_dynamic_topic_subgroup.py` / `fig10_topology_dynamics.py` / `fig11_interaction_landscape.py` / `figA1_gpt51_cross_topology.py` / `figA3_w3_factorial.py` | GitHub contents API（base64）+ `raw.githubusercontent.com` |
| `adhd` 仓库 | `src/packs/core.ts` / `src/frames.ts` / `src/types.ts` / `src/engine.ts` / `src/render.ts` / `src/llm.ts` / `bench/{problems.json,run-evals.ts,baseline.ts,judge.ts}` / `EVALS.md` / `ADOPTERS.md` / `SOURCE-SPEC.md` / `documentation/{frames.md,evals.md}` / `skills/adhd/SKILL.md` / `CONTRIBUTING.md` | 同上 |
| ADHD 站点 | `adhdstack.github.io`（预印本全本，136 段）＋ `adhd.mintlify.site`（含 `llms.txt` 索引 + `concepts/frames.md` / `concepts/how-it-works.md` / `evals/methodology.md`） | `curl` + HTML→text |
| **未读到** | ⚠️ 论文附录 **G.2 的完整 transcript**（只读了 G.1/G.3/G.4 的统计与规则）、附录 **O 的全部提示词模板**（只读了 O 的 proposal 生成模板与 N 的 stance 模板）、**10,000 条原始 proposal**、**所有聚合 CSV**（仓库 README 明示不 ship）、**`bench/results.json` 的 6 条完整 transcript** | — |
| **未复现** | ⚠️ **没有跑任何模型、没有生成任何 proposal、没有重算任何一个论文指标**。本文所有论文侧数字均为**逐字引用**，非我实测。**唯一我实际执行的是 `selectFrames` 的逻辑复刻**（见 §5.2） | — |

---

## 0.1 任务书数字的核验结果

| 任务书给的 | 核验 | 出处 |
|---|---|---|
| Vendi/N **1.03 → 0.47** | ✅ **完全属实**。逐字：*"the Diversity Utilization Ratio (red bars), defined as \text{Vendi}/N , plummets from 1.03 to 0.47"*；且 **Table 8 的 Mean 行独立复算吻合**：N=3 → 1.0306，N=7 → 0.4746 | 论文 §5 `paper.txt:104`；Appendix H `paper.txt:1108`；Table 8 `paper.txt:1246` |
| **+7.4%** | ✅ 属实。逐字：*"the mean Vendi Score increases monotonically from 3.09 at N{=}3 to 3.32 at N{=}7 (+7.4%, paired t{=}5.46 , p{<}0.0001 )"* | `paper.txt:1113` |
| **p < 0.0001** | ✅ 属实，**且论文自己给了 t 值 5.46**（paired t） | 同上 |
| **17/20 主题** | ✅ 属实。我用 Table 8 的 20×5 原始格**独立复算**：N=3→N=7 增长 **17/20**，含 Mean 行则 18/21 | Table 8 `paper.txt:1114–1246` |
| **绝对 Vendi 单调上升** | ❌ **不成立（论文自身表格与之矛盾）**。Table 8 的 Mean 行是 **3.09 → 3.22 → 3.24 → 3.37 → 3.32**，**N=7 比 N=6 低 0.05**；**20 个主题里只有 1 个**在 N=3..7 全程非递减。详见 **§4.2** | Table 8 Mean 行 `paper.txt:1246` |
| **附录 I 的 2×2 / 附录 M 的 GPT-5.1 复现** | ✅ 均存在，附录 M 的三档读数我已**逐格复算**并与论文表值对齐 | `paper.txt:1255–1498` / `paper.txt:1895–1935` |
| **人类验证 5 位专家 / 成对比较 / 87%·82%·81%** | ✅ 全部属实，**且附录 B 给出了更细的流程**（每题 25 对、每人共 100 对、盲评、单一问题、质量门槛）→ **§6.1** | `paper.txt:587–594`；Table 1 `paper.txt:44–52` |

---

## 1. 我们的三路线拓扑该怎么改

### 1.1 论文的三种拓扑 —— 逐字定义 + YAML 参数（两个来源对齐）

论文正文 §5.2 只写了三个名字（Standard / NGT / Subgroups），**精确定义在 Appendix I.2 与 Appendix E**；仓库 `ASSETS.md` 明确只有三档数据目录 `extracted_proposals_{recursive,ngt,subgroup}`。三处对齐如下：

#### 档 A —— 稠密全连接（论文叫 **Recursive**，正文也叫 **Standard**）

> **Appendix I.2 逐字**：
> *"**Recursive**: All 3 agents see the full conversation history and speak sequentially in each round (4 discussion rounds + 1 proposal round). This corresponds to `grouped_sequential` order with `all` visibility."*

> **YAML**（`simulation/configs/dsv3_naive_recursive.yaml`）：
> ```yaml
> environment:
>   max_turns: 5
>   round0_concurrent: false
>   incremental_memory_each_message: true
>   rule:
>     order:      { type: grouped_sequential }
>     visibility: { type: all }
>     selector:   { type: basic }
>     updater:    { type: basic }
>     describer:  { type: basic }
> ```

#### 档 B —— 先独立后汇总（论文叫 **NGT / Nominal Group Technique**）★ **我们要抄的就是这一档**

> **Appendix I.2 逐字**：
> *"**NGT (Nominal Group Technique)**: Round 1 is a blind-writing phase where each agent writes independently without seeing others' contributions. Rounds 2–3 involve sequential discussion among non-leader agents with full visibility. Round 4 includes all agents (including the leader). Round 5 produces the proposal."*

> **YAML**（`simulation/configs/dsv3_naive_ngt.yaml`）：
> ```yaml
> rule:
>   order:      { type: ngt, leader_idx: 3 }   # index of Leader; Leader only speaks in final round
>   visibility: { type: ngt }
>   selector:   { type: ngt }
>   updater:    { type: ngt }
>   describer:  { type: ngt }
> ```
> ⚠️ **`leader_idx: 3` 是关键**：`order`/`visibility`/`selector`/`updater`/`describer` **五个 rule 全部是 `ngt`** ⇒ 第 1 轮所有人的 `selector` 读不到别人的产出 ⇒ 盲写不是靠 prompt 说的，是靠**调度器字段**保证的。

#### 档 C —— 分组隔离（论文叫 **Subgroups**）

> **Appendix E 逐字**：
> *"Given a question or topic, a fixed set of agents participate in a multi-round discussion. In each round, **the full set of agents is randomly partitioned into disjoint subgroups of a specified size**. Within every subgroup, agents speak in sequence, **with each utterance visible only to members of the same subgroup**. After a pre-defined number of rounds, **a leader agent reads a transcript of the most recent subgroup discussions** together with a short summary of the corresponding round structure, and produces the final response."*

> **YAML**（`simulation/configs/dsv3_naive_subgroup.yaml`）：
> ```yaml
> rule:
>   order: {
>     type: subgroup_random,
>     group_sizes: [1, 2, 3, 2],   # 每轮的子群规模序列
>     rounds_per_size: 1,
>     leader_idx: -1,
>     final_leader: true,
>     include_leader_in_subgroups: false
>   }
>   visibility: { type: subgroup }
>   selector:   { type: ngt }        # ← 注意：selector 借用 ngt
>   updater:    { type: subgroup }
>   describer:  { type: subgroup }
> ```

### 1.2 映射到我们的 A / B / C

| 我们的路线 | 论文对应档 | 交互结构 | 我们的现状问题 | 建议 |
|---|---|---|---|---|
| **A（稠密全连接）** | 档 A（Recursive） | 全员看全量历史，顺序发言，最后 Editor 收口 | 共享的稠密结构 + 权威结构 = 论文的 "Gravitational Collapse" 温床 | 保留作**基线臂**，但必须命名为 `dense_recursive` 并在报告里写清它 = 论文的档 A |
| **B（先独立后汇总）** | 档 B（NGT） | **第 1 轮完全隔离盲写** → 之后才开放 | 我们目前是"人多、连得紧"，**没有真正的隔离期** | ★ **抄 NGT 的调度层做法**：盲写不是靠 prompt 约束，是靠 `visibility/selector` 字段保证 |
| **C（分组隔离）** | 档 C（Subgroups） | 轮内随机切成不相交子群，发言只在本子群内可见，末轮 leader 汇总 | 我们的"三路线"若共享上游，本质仍是档 A | 若要 C，必须**同时**改 `visibility` 与 `updater` 两个字段，只改一个不构成隔离 |

### 1.3 我们要抄的：NGT 的**调度层**做法（不是 prompt 做法）

论文的 NGT 之所以有效，是因为 **§4.1 的 "Prompt tone is not a confound"** 控制 + **调度器层面的硬隔离**。落到我们代码上：

```yaml
# 我们 NGT 臂的调度契约（照抄论文的五字段同构）
routing:
  phase_1:                      # 盲写期
    visibility: isolated        # ← 关键：每路只能看到 problem + 自己的 frame prompt
    selector:   isolated        # ← 关键：不检索他路产出
    history:    none            # ← 关键：不注入他路历史
  phase_2:                      # 汇总期
    visibility: shared
    selector:   shared
  synthesis:                    # 收口
    editor: single              # 单 Editor，不让全员互相改写
```

**落码要点（3 条，都是论文给我们的教训）**：
1. **盲写期必须真的不注入他路历史**。我们现在的"共享上游"（同一依据包 / 同一判官 / 同一套装配约定）如果在 phase_1 就被拼进 prompt，等于没有盲写 —— 这正是论文 §1 指出的 "amplifying shared priors rather than introducing genuine variety"。
2. **收口必须是单一 Editor**。论文 §2.2 的 "Proposal Synthesis" 明确是 *"a designated 'Editor' agent (or the collective group)"*，而 NGT 配置里 `leader_idx: 3` 注释写死 *"Leader only speaks in final round"* ⇒ **leader 不参与中途讨论**。我们若让"判官"中途介入，它就同时是权威和收口者 ⇒ 权威+耦合双杀。
3. **判官与 Editor 必须是不同角色**（见 §2.4）。

### 1.4 拓扑的"不可同时动"清单

论文 §6.1 自己承认图 11 是**示意性**的，因为 *"cells mix personas across models"*。我们做三路线对照时必须**锁住**以下变量，否则我们测的会是 persona 而不是拓扑：

| 必须锁住 | 论文怎么锁的 | 我们的做法 |
|---|---|---|
| 模型 | 附录 I 全用 DeepSeek-V3 | 三臂同模型同温度同 token 预算 |
| persona | 附录 I 用 2×2（Naive / Horizontal × Recursive / NGT） | 见 §2.3 |
| 轮数 / 深度 | `max_turns: 5` | 三臂同轮数 |
| 温度 | `temperature: 0.7` | 同温 |
| 每格样本量 | **50 runs × 20 topics** | 每格 ≥ 30 次独立跑（§6 噪声地板要求） |

---

## 2. 去权威化对照臂（Horizontal 的确切做法）

### 2.1 论文的 Horizontal 逐字定义

> **§4 逐字**（`paper.txt:80`）：
> *"**Horizontal Collaboration**: A group of early-career researchers collaborates flatly without senior oversight."*

> **Appendix I.2 逐字**（`paper.txt:1280`）：
> *"**Horizontal**: Agents are prompted as 'first-year PhD students with limited research experience in [topic]' who bring 'fresh curiosity and basic academic foundation.'"*

> **代码逐字**（`simulation/configs/dsv3_horizontal_recursive.yaml`）—— **这就是我们要抄的"确切做法"**：
> ```yaml
> name: Early-Career Researchers Only Academic Discussion with AI-Researcher Integration
> agents:
>   - name: PhD Student A
>     role_description: A first-year PhD student in AI research with limited research experience in
>       {topic_lower}, bringing fresh curiosity and basic academic foundation to the discussion.
>   - name: PhD Student B        # 同上
>   - name: PhD Student C        # 同上
> ```
> ⚠️ **两个易漏的实现细节**：
> 1. **agent 名字也换了**（`PhD Student A/B/C` 而非 `Participant 1/2/3`）⇒ 权威信号不只在 role_description，还在**称呼**里。
> 2. **收口 agent 的 role_description 也同步改写**：`"The same first-year PhD student who participated in the discussion, now attempting to synthesize the group's limited but fresh perspectives into a research proposal."` ⇒ 收口者**不拥有额外权威**。

**其余 4 个 persona（§4 逐字，`paper.txt:78–82`）**：
> *"**Naive Collaboration**: Agents interact without defined roles or hierarchy."*
> *"**Leader-Led Collaboration**: A designated senior expert guides discussion, with junior agents aligned to follow authoritative directives."*
> *"**Interdisciplinary Collaboration**: Experts from distinct fields collaborate to synthesize cross-domain ideas."*
> *"**Vertical Collaboration**: A hierarchical mix of senior experts, mid-career researchers, and early-career scholars."*

**目录后缀映射**（`docs/persona_mapping.md`）：`rec_final`=Naive ｜ `young_final`=Horizontal ｜ `mix_final`=Vertical ｜ `leader_experience2`=Leader-Led ｜ `x_final`=Interdisciplinary。

### 2.2 论文证明了：**权威 × 拓扑是两个独立变量**

这是我们要抄的核心方法论。论文用**两个正交实验**拆开了"专家"和"权威"：

| 实验 | 结论 | 读数 |
|---|---|---|
| **Appendix K（2×2 Identity × Tone，flat 拓扑）** | 在**无层级**拓扑下，**Senior persona 的多样性反而更高**（方向与主实验相反！）⇒ 塌缩不是"专家身份"造成的 | Identity η²=**0.058**, p=**0.031**；Tone η²=**0.023**, p=**0.172**（不显著） |
| **Appendix I（2×2 Persona × Topology）** | 拓扑效应的大小**被 persona 调节** | Naive: d=**2.21**（p<0.0001，全 20 主题同向）；Horizontal: d=**0.25**（p=**0.298**）；交互 **p<0.0001** |

⇒ **论文的机制主张（§4.1 逐字）**：
> *"indicating that **the combination of expertise and hierarchy, not expertise alone, drives the collapse**."*

### 2.3 ★ 我们怎么把"专家 persona"与"权威结构"拆成两个变量（可落码 2×2）

论文的 Appendix K/I 已经给了现成模板。**我们的 2×2 规格**：

```
                拓扑 = 稠密全连接(dense)   拓扑 = 先独立后汇总(NGT)
persona=平级     Cell A1                    Cell A2
(无层级暗示)      e.g. "同级工程师"          e.g. "同级工程师"

persona=权威     Cell B1                    Cell B2
(显式领导者)      e.g. "首席/leader 分配方向"  e.g. "首席/leader 分配方向"
```

| 我们要回答的问题 | 读哪个对比 |
|---|---|
| **拓扑本身有没有用？**（去权威后还成立吗） | A1 vs A2（平级臂内部比） |
| **权威结构本身有没有害？** | A1 vs B1（同一拓扑内比） |
| **权威会不会吃掉拓扑干预的收益？** | (B1−A1) vs (B2−A2) ⇒ **交互项**，对应论文的 Persona×Topology 交互 p<0.0001 |

**落码约束（照抄论文的教训）**：
1. **权威的载体必须可枚举，不能靠语气暗示。** 论文的 Horizontal 把**agent 名字**也改了（`PhD Student A` vs `Participant 1`）⇒ 我们的"平级臂"必须同时改 **role_description + 称呼 + 收口者身份**三处。
2. **"专家"与"权威"必须能同时存在。** 论文的 Appendix K 证明：flat 拓扑下 Senior persona 的多样性更高 ⇒ 我们的 A2/B2 格里，**"平级"不等于"不专业"**（Horizontal 的人依然是有专业的人，只是不有层级）。**否则我们会把"专业性"和"权威性"一起消掉，测不到真正的交互项。**
3. **提示词语气必须作为第三个被控量**（论文 Appendix K 的 Tone 因子，η²=0.023 不显著）⇒ 我们的 2×2 里**所有四格的措辞风格必须一致**，只改"有无层级暗示"。
4. **每格 50 runs × 20 topics 是论文的量**；我们至少 **30 runs × 我们自己的 DEV 题数**，并**必须报噪声地板**（§6.3）。

### 2.4 ⚠️ 判官不能同时扮演权威（U6 陷阱的具体化）

论文的**质量轴**是 *"LLM-as-Judge protocol (DeepSeek-V3, temperature 0)"* —— **同源自评**（论文 Limitations 逐字：*"inherit the standard biases of automatic judges"*）。

落到我们：我们的"判官"如果同时是"依据包 + 判官"结构的持有者，**它就是论文里的 Leader**。论文的 §4.2 逐字：
> *"the presence of senior authority acts as a strong attractor. Junior agents likely succumb to sycophancy, aligning their vectors with the leader rather than offering orthogonal critiques."*

⇒ **我们的规格**：
- 判官的 **rubric 不得含"谁更专业/谁更权威"的维度**（论文 Appendix N 的 stance rubric 是 1–10 的"DISAGREEMENT/NOVELTY"，**不含质量**⇒ 可直接抄，见 §6）。
- 判官在 A1/B1/A2/B2 四格里**必须是同一个 prompt、同一个模型、同一温度**。
- 判官输出**不得回灌**被评臂的上下文（否则下一轮就锚定了）。

---

## 3. 我们能用的离散多样性度量（不依赖 embedding）

### 3.1 结论先行：**不要用 W-D-3 当主判据**

任务书问"它有没有离散/非 embedding 的多样性度量"。**有 3 个半**，但**能不能用**取决于一件事：**该度量对"权威塌缩"这个目标效应有没有分辨率**。

**论文 Table 2 的 W-D-3 列（`paper.txt:745–803`，我逐格复算过）**：

| Persona | Vendi ↑ | 1−φ ↑ | PCD ↑ | **W-D-3 ↑（无 embedding）** | Vendi 上的权威落差 | **W-D-3 上的落差** |
|---|---:|---:|---:|---:|---|---|
| **Horizontal** | **8.080** | 0.170 | 0.311 | **0.788** | — | — |
| Leader-Led | 6.932 | 0.161 | 0.296 | 0.780 | −1.148（−14.2%） | **−0.008（−1.0%）** |
| Vertical | 6.082 | 0.146 | 0.272 | 0.781 | −1.998（−25.3%） | −0.007（−0.9%） |
| Naive | 5.567 | 0.154 | 0.285 | 0.638 | −2.513（−31.1%） | −0.150（−19.0%） |
| Interdisciplinary | 4.647 | 0.119 | 0.225 | 0.734 | −3.433（−42.5%） | −0.054（−6.9%） |

⇒ **★ 决定性事实**：**W-D-3 几乎测不出"权威 vs 平级"**（Leader-Led 0.780 vs Horizontal 0.788，差 **1.0%**；而 Vendi 差 **14.2%**，Interdisciplinary 更是差 **42.5%**）。
⇒ 论文自己也这么说（Appendix F.4 逐字）：*"**W-D-3 does not necessarily match the embedding-based ordering**"*、*"We therefore treat W-D-3 as a complementary signal rather than a redundant proxy for structural diversity."*
⇒ **若我们把 Vendi 换成 W-D-3 当主判据，我们会直接丢掉我们要测的那个效应。**

### 3.2 ★ 我们该用的：**Appendix G.3 的标题级词汇集中度**（无 embedding + 有分辨率）

这是**全论文唯一**一个「非 embedding + 对权威轴有真实分辨率」的读数。逐字（`paper.txt:893–916`）：

> *"To quantify the thematic concentration observed in Section 4, we compute title-level lexical statistics across all 20 topics for the Interdisciplinary and Horizontal configurations."*
> *"**Method.** We extract all proposal titles (924 Interdisciplinary; 632 Horizontal), tokenize after lowercasing and removing stopwords, and compute: (i) **Type-Token Ratio (TTR = unique tokens / total tokens)**, (ii) top-k unigram and bigram frequencies, (iii) **Jaccard similarity of the full vocabulary sets**."*

| 统计量 | **Interdisciplinary** | **Horizontal** | 判读 |
|---|---:|---:|---|
| 标题数 | 924 | 632 | |
| 总 token | 10,411 | 6,146 | Inter 反而**更多** token |
| 唯一 token | 729 | 958 | Inter **更少**唯一词 |
| **Type-Token Ratio** | **0.070** | **0.156** | ★ **2.2× 差距** |
| 全词表 **Jaccard 相似度** | \multicolumn{2}{c}{**0.211**（294 共享词 / 并集 1,393）} | 两配置词汇池基本不同 |

> **Table 3 逐字**：*"Despite having more titles and tokens, Interdisciplinary proposals use fewer unique words, yielding a TTR 2.2 × lower than Horizontal."*

⇒ **TTR 的长度偏倚在这里对我们有利**：Interdisciplinary 的 token 数**更多**（10,411 > 6,146），而 TTR **随长度单调下降** ⇒ 长度效应是**反向**的 ⇒ 真实的集中度差距**比 2.2× 还要大**。这是一个**方向安全的**读数。

### 3.3 三个候选的完整规格（可直接落码）

#### 候选 ① **标题级 TTR**（★ 推荐主判据）

```
输入：一组产物的一级标题列表（每臂 ≥ 30 条）
处理：lower → 正则 [a-z]+ 切词 → 去停用词（论文用固定高频功能词表）
      → 统计 unique tokens / total tokens
输出：TTR ∈ (0,1]，越大 = 用词越分散
报读数：每臂的 (unique, total, TTR) 三元组 + 臂间 TTR 比
噪声：必报 —— TTR 对样本量敏感，n 变化会改 TTR ⇒ **每臂必须固定 n**
```

#### 候选 ② **词表 Jaccard 相似度**（臂间离散差异度）

```
输入：两臂的标题词集合 A, B
输出：J = |A ∩ B| / |A ∪ B|          # 论文值 0.211（Inter vs Horizontal）
用法：我们三路线两两比 ⇒ 得到 3×3 的 J 矩阵
      高 J = 两臂在同一个词池里打转 = 思维面重合
```

#### 候选 ③ **W-D-3（content-only weighted distinct-3）**（论文 Appendix C.4 的那个，**只做辅证**）

**代码逐字**（`analysis/metrics/compute_vendi_extended.py`）：

```python
# :21
_TOKEN_PATTERN = re.compile(r"[a-z]+")  # fast + stable

# :24-32
_STOPWORDS = {
    "a","an","and","are","as","at","be","but","by",
    "for","from","has","have","had","he","her","him",
    "i","in","is","it","its","may","might","more","most",
    "of","on","or","our","ours","she","so","some","such",
    "than","that","the","their","them","these","they","this",
    "to","was","we","were","what","when","which","who","will",
    "with","would","you","your",
}

# :36-41
_BOILERPLATE = {
    "paper","work","study","approach","method","methods","framework",
    "model","models","propose","proposed","novel","new",
    "evaluate","evaluation","experiment","experiments","results","performance",
    "dataset","datasets","task","tasks","analysis","system","systems",
}

# :291-300
def get_content_words(text: str):
    text = text.lower()
    toks = _TOKEN_PATTERN.findall(text)
    return [t for t in toks if t not in _STOPWORDS and t not in _BOILERPLATE]

# :303-332  —— 全局 IDF（跨所有实验设置联合统计，保证跨条件可比）
def build_global_content_ngram_idf(all_datasets, n=3):
    df = defaultdict(int); valid_docs = 0
    for dpath in all_datasets:
        ...
        for text in texts:
            words = get_content_words(text)
            if len(words) < n: continue
            valid_docs += 1
            grams = set(tuple(words[i:i+n]) for i in range(len(words) - n + 1))
            for g in grams: df[g] += 1
    if valid_docs == 0: return {}, 0
    # Non-negative smoothed IDF: log((1+N)/(1+df))
    idf = {g: float(math.log((1.0 + valid_docs) / (1.0 + dfg))) for g, dfg in df.items()}
    return idf, valid_docs

# :335-361
def content_only_wdistinct_n(texts, idf, n=3):
    """WDistinct-n = sum_idf(unique ngrams) / sum_idf(all ngrams)"""
    ...
    sum_idf_all = 0.0; sum_idf_unique = 0.0; seen = set()
    for g in all_ngrams:
        w = idf.get(g, 0.0)
        sum_idf_all += w
        if g not in seen:
            sum_idf_unique += w
            seen.add(g)
    return float(sum_idf_unique / (sum_idf_all + 1e-12))
```

⚠️ **落码注意 3 条**：
1. **IDF 必须跨臂联合统计**（论文 Appendix C.4 逐字：*"computed over the union of proposals from all collaboration settings. This global normalization ensures that lexical scores are comparable across different experimental conditions."*）—— **分臂算 IDF 会毁掉可比性**。
2. **中文件不能直接用 `[a-z]+`**。论文是纯英文；我们的产物是中文 ⇒ 需换中文分词 + **中文停用词表 + 中文"学术套话"表**（对应 `_BOILERPLATE`）。**这一项论文没有现成方案，我们自己造。**
3. **必须同时报 W-D-2 / W-D-3 / W-D-4**（论文 Appendix F.5 逐字：*"Relative ordering across collaboration modes remains stable for n=2 and n=3, while higher-order n-grams exhibit mild saturation effects."*）⇒ 报告里给 3 个 n，说明结论不依赖单一 n。

#### 候选 ④ **Self-BLEU-4 / Distinct-n**（代码里有、**论文没报数** ⇒ 未验证，只能当探索）

`compute_vendi_extended.py:368-392`（`self_bleu`）与 `:439-454`（`distinct_n`）。
⚠️ **论文全文 grep "Self-BLEU" = 0 命中** ⇒ **没有任何 per-persona 读数** ⇒ **不能引用它说"对权威轴有分辨率"**。若我们用它，必须**自己先做分辨率校准**（§3.4）。

### 3.4 ★ 我们的离散度量面板（最终规格）

**主判据（结构轴，无 embedding）**
1. **标题 TTR**（候选①）—— 唯一有权威分辨率的量化读数（2.2×）
2. **词表 Jaccard 矩阵**（候选②）—— 3×3，臂间思维面重合度
3. **trap 命中率**（§5.3，ADHD 的离散载体）—— "看起来好但会坏"的比例

**辅证（冗余轴）**
4. **W-D-3 / W-D-2 / W-D-4**（候选③）—— 与主判据**方向是否一致**都要报；不一致本身就是结论（论文 Appendix F.4 明说二者不一致是正常的）

**★ 分辨率校准协议（必须先做，否则不知道尺子有没有用）**
> 取我们 DEV 集里**人工公认最分散**与**最集中**的两组产物（各 ≥ 10 条），算全部候选度量。
> - 若某度量在"公认最分散 vs 最集中"上给出 ≥ **2× 的相对差** ⇒ 该度量有分辨率 ⇒ 保留。
> - 若给出 < 1.2× ⇒ **该度量在我们的场景没有分辨率**（这正是 embo-01 的问题）⇒ 只能当"已声明的无判据"，**不得进主表**。
> ⚠️ 论文自己没做这件事（Appendix F 只做"换 embedding 后排序是否不变"，**没做"这个指标在无意义场景下会不会也给出相同排序"的对照**）⇒ 这一步是我们的增量。

---

## 4. Vendi/N 边际利用率读数该怎么进我们的报告

### 4.1 论文的原始读数

> **§5 逐字**（`paper.txt:104`）：
> *"While the absolute Vendi Score (blue line) **increases monotonically** from N=3 to N=7 , the Diversity Utilization Ratio (red bars), defined as \text{Vendi}/N , **plummets from 1.03 to 0.47**. This indicates that **adding agents does not linearly expand the semantic search space; rather, new agents increasingly overlap with existing ones**."*

> **Appendix H.3 Finding 1 逐字**（`paper.txt:1113`）：
> *"Aggregated across topics, the mean Vendi Score increases monotonically from **3.09** at N{=}3 to **3.32** at N{=}7 (**+7.4%**, paired t{=}5.46 , p{<}0.0001 ), with **17 out of 20 topics** exhibiting growth. This directly refutes the 'low-hanging fruit' hypothesis: if topics were limited to ∼3 distinct ideas, the Vendi Score would plateau at ∼3 regardless of group size."*

> **Appendix H.1 逐字**（`paper.txt:1108`）：*"The aggregate analysis in Figure 7 shows that the Diversity Utilization Ratio (Vendi/N) declines from 1.03 at N{=}3 to 0.47 at N{=}7 . A natural alternative hypothesis is that this saturation reflects the finite complexity of the 20 ICLR research topics used as our testbed…"*
> **排除替代解释**（`paper.txt:1253` 附近）：*"the correlation is not statistically significant (Pearson r{=}{-}0.14 , p{=}0.55 )"*；高容量主题（General ML 3.51→3.53）与低容量主题（Transfer/Meta 2.60→2.74）斜率几乎一样（−0.143 vs −0.127）。

### 4.2 ⚠️ **纠正：论文的"单调上升"与它自己的表格矛盾**

**Table 8（Appendix H）的 Mean 行逐格**（`paper.txt:1246`）：

| N | 3 | 4 | 5 | 6 | 7 |
|---|---:|---:|---:|---:|---:|
| **Mean Vendi** | **3.09** | **3.22** | **3.24** | **3.37** | **3.32** |
| **Vendi/N** | **1.03** | 0.80 | 0.65 | 0.56 | **0.47** |

⚠️ **N=7 (3.32) < N=6 (3.37)** ⇒ 绝对 Vendi **不是单调上升**。
⚠️ 我用 Table 8 的 20×5 原始格**独立复算**：
- **20 个主题里 0 个**在 N=3..7 全程非递减 ⇒ **19/20 主题在 N=3..7 的某一步至少下降一次**（例：`Learn Theory` 3.13 / 3.33 / 3.60 / 3.60 / **3.48**，N=6→N=7 降）。
- **+7.4% 是端点比较**（N=3 → N=7），不是逐步单调性的证据。
- **17/20 只统计 N=3 → N=7 的端点方向**，与"单调"无关。

⇒ **对我们的直接影响**：我们**不能**在报告里转述"绝对 Vendi 单调上升"。可以转述的是：
1. **利用率 Vendi/N 单调下降**（1.03 → 0.80 → 0.65 → 0.56 → 0.47）—— **这个是真的单调**；
2. **端点增长 +7.4%**（paired t=5.46, p<0.0001, 17/20 主题）—— **这个是真的**；
3. **"饱和而非耗尽"** —— 真的，且有 r=−0.14/p=0.55 的排除证据。

### 4.3 逐主题表（Table 8 全表，我按 `paper.txt:1114–1246` 逐格复算）

| Topic | N=3 | N=4 | N=5 | N=6 | N=7 | V3/N | V7/N | Δ% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| General ML | 3.51 | 3.54 | 3.65 | 3.76 | 3.53 | 1.17 | 0.50 | +0.6% |
| Physical Sci. | 3.42 | 3.48 | 3.45 | 3.64 | 3.75 | 1.14 | 0.54 | +9.6% |
| Viz/Interp | 3.38 | 3.53 | 3.44 | 3.86 | 3.67 | 1.13 | 0.52 | +8.6% |
| Generative | 3.32 | 3.37 | 3.35 | 3.53 | 3.15 | 1.11 | 0.45 | −5.1% |
| Optimization | 3.26 | 3.35 | 3.37 | 3.50 | 3.59 | 1.09 | 0.51 | +10.1% |
| Neuro/CogSci | 3.20 | 3.24 | 3.21 | 3.50 | 3.33 | 1.07 | 0.48 | +4.1% |
| Infra/SW | 3.18 | 3.36 | 3.29 | 3.80 | 3.69 | 1.06 | 0.53 | +16.0% |
| RL | 3.19 | 3.03 | 3.22 | 3.42 | 3.46 | 1.06 | 0.49 | +8.5% |
| Learn Theory | 3.13 | 3.33 | 3.60 | 3.60 | 3.48 | 1.04 | 0.50 | +11.2% |
| Causal | 3.09 | 3.39 | 3.14 | 3.01 | 3.02 | 1.03 | 0.43 | −2.3% |
| Data/Bench | 3.08 | 3.35 | 3.25 | 3.48 | 3.56 | 1.03 | 0.51 | +15.6% |
| Metric/Kernel | 3.06 | 3.08 | 3.53 | 3.28 | 3.30 | 1.02 | 0.47 | +7.8% |
| Prob/Bayes | 3.01 | 2.99 | 3.21 | 3.23 | 3.49 | 1.00 | 0.50 | +15.9% |
| SSL/Unsup | 3.00 | 3.27 | 3.13 | 3.32 | 3.35 | 1.00 | 0.48 | +11.7% |
| Graphs/Topo | 2.96 | 2.92 | 2.95 | 3.30 | 3.26 | 0.99 | 0.47 | +10.1% |
| Robotics | 2.94 | 2.95 | 3.39 | 2.89 | 2.89 | 0.98 | 0.41 | −1.7% |
| RepLearn | 2.93 | 3.19 | 3.06 | 3.49 | 3.04 | 0.98 | 0.43 | +3.8% |
| Society/Fair | 2.84 | 3.00 | 2.86 | 3.00 | 3.10 | 0.95 | 0.44 | +9.2% |
| NeuroSymbolic | 2.74 | 3.05 | 2.95 | 2.98 | 3.04 | 0.91 | 0.43 | +10.9% |
| Transfer/Meta | 2.60 | 2.92 | 2.73 | 2.84 | 2.74 | 0.87 | 0.39 | +5.4% |
| **Mean** | **3.09** | **3.22** | **3.24** | **3.37** | **3.32** | **1.03** | **0.47** | **+7.4%** |

### 4.4 ★ 我们的报告规格：每个组件都要报利用率

**论文给我们的原型**（`fig07_scaling_gap.py` 口径，仓库实现）：
- 样本单位 = **一个 agent 的全部发言拼接后的文本**（跨 topic 合并）→ N 个 agent 文本 → N 个 embedding → **Vendi over N 个 agent**
- 理论上限 `y = N`；**Utilization = Vendi / N**
- ⇒ 量的含义：**"每个 agent 平均贡献了多少个有效独立视角"**

⇒ **我们的报告模板（每加一个组件就填一行）**：

| 组件 | 绝对读数 | 分母 | **利用率** | 相对上一档 | 噪声地板 δ | 结论 |
|---|---|---|---|---|---|---|
| 基础（直调） | | | | — | | |
| +组件 1 | | | | | | |
| +组件 2 | | | | | | |
| +组件 3 | | | | | | |

**规格条款（可直接抄成 checklist）**：
1. **每一行都要有分母**：分母 = 该档的"agent 数"或"组件数"或"token 预算"（三选一，但**全表必须同一口径**）。
2. **每一行都要有 δ**（噪声地板）：同一配置跑 k 次的读数波动。**没有 δ 的利用率行不许进表**。
3. **绝对读数涨、利用率跌 ⇒ 判为"饱和"**，不许写成"提升"。
4. **必须跑"去掉某组件"的消融**：论文的 §5.1 逐字 —— *"both Semantic Drift Velocity and Maximum Mean Discrepancy (MMD) show a consistent downward trend. This confirms that the group's 'center of gravity' stabilizes over time"*，而 §6.2 逐字 —— *"the very mechanisms designed to ensure quality, namely collaboration and peer critique, can force the system to prematurely abandon unconventional ideas"*。⇒ **"加了组件反而变差"是论文支持的结论形态**，我们不能预设"加组件一定更好"。
5. ⚠️ **不要把 Vendi/N 直接搬过来当我们的"利用率"**：Vendi/N 的分母是"agent 数"，而**我们的"思维面"是"有效信息维度数"**。我们若分母用组件数，得到的量纲是"每组件贡献多少维度"——**这是对的，但要改名叫 `VD_per_component`，并在报告里写明它与论文的 `Vendi/N` 不是同一个量**（论文 Vendi/N 的分母是 agent，而它的 Vendi 本身算的是"proposal 池的语义模态数"；我们若把 Vendi 换成 §3 的离散度量，分子的定义就变了）。

---

## 5. 15 认知帧池 + trap 字段

### 5.1 15 个认知帧 —— `src/packs/core.ts` 逐字（`UditAkhourii/adhd`，MIT）

> `export const core: Frame[] = [` （`src/packs/core.ts:3`）—— **以下 15 条逐字照录，id / label / prompt / tags 全部原样**：

| # | id | label | prompt（逐字） | tags |
|---|---|---|---|---|
| 1 | `hardware-eyes` | Hardware engineer | "You think in latency, memory layout, and physical constraints. Re-ask this problem as if it were a hardware/firmware problem. What does the bus topology, the cache, the timing budget tell you?" | `code, wild` |
| 2 | `regulator` | Regulator / auditor | "You audit systems for compliance and failure modes. What ideas surface when you ask: what must be provable, traceable, or refusable here?" | `design, general` |
| 3 | `ten-year-old` | 10-year-old | "You are a curious 10-year-old who has never seen software before. Describe naive but unencumbered approaches. Ignore convention." | `general, wild` |
| 4 | `adversary` | Competitor trying to break it | "You are a hostile competitor or attacker. Generate approaches that exploit, fail, or sabotage the obvious solution. Then invert into ideas." | `code, design` |
| 5 | `biology` | Cross-domain: biology | "Transplant a mechanism from biology — immune systems, neural plasticity, cell signaling, evolution, gut flora — and force-fit it onto this engineering problem." | `code, wild` |
| 6 | `logistics` | Cross-domain: logistics / supply chain | "Steal mechanisms from logistics: queues, batching, just-in-time, hub-and-spoke, returns, last-mile. Apply them literally to this problem." | `code, design` |
| 7 | `game-design` | Cross-domain: game design | "Approach this as a game designer. What are the loops, rewards, friction, save-states, speedrun tricks? Treat the user/system as a player." | `design, general` |
| 8 | `markets` | Cross-domain: markets | "Treat the problem as a market. Who are the buyers, sellers, market-makers? What does an auction, a futures contract, a clearing house look like here?" | `design, wild` |
| 9 | `inversion` | Inversion | "Ask the OPPOSITE question. If the goal is X, brainstorm 'how would we guarantee NOT-X' — then negate each answer back into an idea." | `code, design, general` |
| 10 | `extreme-zero` | Extreme: $0 budget, 1 hour | "You have no money, no team, one hour. What's the crudest version that still does the load-bearing thing? Hacks, hardcoded values, manual loops welcome." | `code, general` |
| 11 | `extreme-infinite` | Extreme: infinite budget, 10 years | "You have infinite compute, infinite engineers, a decade. What does the maximalist version look like? What would only be possible at that scale?" | `design, wild` |
| 12 | `remove-assumption` | Remove the load-bearing assumption | "Name the thing everyone treats as fixed in this problem (the framework, the database, the request/response model, the file system, the network). Imagine it's gone. Generate ideas that only exist in that world." | `code, design, wild` |
| 13 | `speedrunner` | Speedrunner | "You're a speedrunner. Find glitches, skips, out-of-bounds tricks, frame-perfect shortcuts. What's the abusive-but-legal path through this problem?" | `code, wild` |
| 14 | `ant-colony` | Ant colony / swarm | "No central planner. Many dumb agents, local rules, pheromone trails. How does the problem solve itself emergently?" | `code, wild` |
| 15 | `ops-3am` | On-call at 3am | "You're the on-call engineer woken at 3am when this thing breaks. What design would let you not get paged? What's the runbook-shaped solution?" | `code, design` |

**帧的定位（预印本逐字，`adhdstack.github.io`）**：
> *"A frame is a **vantage operator**: a system-prompt payload that re-poses the entire problem from a different cognitive position. **Not a persona, not a domain expert** — a deliberate distortion that forces the generator into a corner it would not naturally drift toward."*
> *"Frames are **not** personas. Persona-prompting research … studies simulated identities; some findings report that **ordinary attribute-personas outperform curated expert-personas**. ADHD frames are neither — they are *vantage operators* … that **re-pose the problem**, not identities the model role-plays. The mechanisms are different, so persona findings do not map directly onto frame selection."*（issue #17）

⇒ ★ **对我们最重要的一条推论**：论文 §4 证明的"**权威** persona 会压多样性"，**不能**直接推论"**帧**（vantage operator）也会压多样性"。
- 论文的 "Interdisciplinary" = **专家身份 + 层级**（两个因素捆在一起）⇒ 塌缩。
- ADHD 的 15 帧 = **视角重述，刻意去专业化**（"10-year-old"、"$0 budget"）⇒ 应当是**发散**的。
- ⇒ **我们的"去权威化对照臂"应当用"帧"（vantage），不用"专家 persona"**；而"专家 persona"要单独作为**权威轴**的另一个取值去测。
- ⇒ 这恰好就是 §2.3 的 2×2：**{权威轴：平级 vs 专家权威} × {视角轴：无帧 vs 15 帧}**。

### 5.2 `selectFrames` 的机制 + 两个必须修的缺陷

**原版机制逐字**（`src/frames.ts`）：

```ts
// :24-32  —— Fisher-Yates 洗牌
// Fisher-Yates shuffle — uniform distribution, unlike sort(() => Math.random() - 0.5).
function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// :36-65
export function selectFrames(n: number, codeMode = true, packs = ["core"]): Frame[] {
  if (packs.length === 0) throw new Error("selectFrames needs at least one pack name");
  const named = [...new Set(packs)].map((name) => { /* 查 PACKS */ });
  const unique = (list: Frame[]) => [...new Map(list.map((f) => [f.id, f])).values()];
  const frames = unique(named.flat());
  // codeMode 时池子收窄为带 code / design 标签的帧
  const pool = codeMode
    ? unique(named.flatMap((p) => {
        const engineering = p.filter((f) => f.tags.includes("code") || f.tags.includes("design"));
        return engineering.length > 0 ? engineering : p;
      }))
    : frames;
  const pooledWild = frames.filter((f) => f.tags.includes("wild"));
  const wild = pooledWild.length > 0 ? pooledWild : FRAMES.filter((f) => f.tags.includes("wild"));

  const shuffled = shuffle(pool);
  const picked = shuffled.slice(0, Math.max(1, n - 1));      // ← 缺陷 2 在这
  const wildPick = wild[Math.floor(Math.random() * wild.length)];
  if (!picked.find((f) => f.id === wildPick.id)) picked.push(wildPick);
  return picked.slice(0, n);
}
```

#### 缺陷 ① ★★ **没有 PRNG、没有 seed** —— 官方文档在这件事上说了假话

| 位置 | 事实 |
|---|---|
| `src/frames.ts:28` | `const j = Math.floor(Math.random() * (i + 1));` |
| `src/frames.ts:62` | `const wildPick = wild[Math.floor(Math.random() * wild.length)];` |
| `src/types.ts:50-68`（`RunOptions`） | **没有 `seed` 字段** |
| `bench/run-evals.ts:88` | `const swapped = Math.random() < 0.5;` ← **A/B 顺序也是无种子的** |

**文档侧的假话（3 处独立来源，同一错误）**：
> `documentation/frames.md:31`：*"**Selection is deterministic per-seed so runs are reproducible.**"*
> 站点 `adhd.mintlify.site/concepts/frames`：*"Selection is **deterministic per-seed** so runs are reproducible — but varies across sessions so the same problem produces different candidate sets when re-run."*（**自相矛盾**：前半句说可复现，后半句说每次都变）
> 站点 `concepts/how-it-works` / `documentation/how-it-works.md:63`：*"Frame selection … is deterministic per-seed with a `codeMode` bias"*

⚠️ **这 3 句全是假的** ⇒ **"同一份代码两次跑，帧不同 ⇒ 评测结果在帧层面不可复现"**。

#### 缺陷 ② ★★★ **`selectFrames` 会少返回一帧**（4 或 5，不是 5）

**根因**：`picked` 只有 `n-1` 个；若 `wildPick` 已经在 `picked` 里，则**不补入**，`picked.slice(0, n)` 于是返回 **n−1** 个。

**我实测复刻的结果**（逐行照搬 `src/frames.ts` 的逻辑，n=5, codeMode=true）：

```
pool size (codeMode) : 14
wild pool size       : 8
returned-length histogram over 200000 runs (n=5 requested): { '4': 50150, '5': 149850 }
P(returned 4) = 25.07%
distinct frame-sets observed in 20k runs: 3823
```

⇒ **25.07% 的运行静默只跑 4 帧**（理论值 7/8 × 4/14 = 0.25，模拟与理论吻合）。
⇒ **预印本宣称的 "N = 5 frames" 与 "≈10 LLM calls" 在 1/4 的运行里不成立。**
⇒ 对我们：**分支数在 run 间波动 ⇒ 任何以"分支数"为自变量的比较都被这个噪声污染** —— 这正是我们要治的病（共享上游 ⇒ 有效维度被压扁），结果我们自己的尺子先被污染了。

#### ★ 我们的替换实现（可直接落码）

```ts
// ── 带种子、可复现、帧数恒定 ──────────────────────────────────────────
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Fisher-Yates，PRNG 可注入 */
function shuffle<T>(arr: T[], rnd: () => number): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function selectFrames(
  n: number,
  codeMode = true,
  packs = ["core"],
  seed?: number,                 // ← 新增：缺省则回退到原版行为（并 warn）
): Frame[] {
  const rnd = seed === undefined
    ? Math.random
    : mulberry32(seed);
  if (seed === undefined) {
    console.warn("[frames] no seed supplied → run is NOT reproducible");
  }
  // …（packs 校验 / unique / pool 收窄 / wild 池，逻辑照抄原版 :39–58）…

  const shuffled = shuffle(pool, rnd);
  // ★ 修复 ②：先保证 n-1 个，再**强制**补入一个 wild（若已在其中则换一个）
  const picked = shuffled.slice(0, Math.max(1, n - 1));
  const wildIds = new Set(wild.map((f) => f.id));
  let wildPick = wild[Math.floor(rnd() * wild.length)];
  if (picked.some((f) => f.id === wildPick.id)) {
    const alt = wild.filter((f) => !picked.some((p) => p.id === f.id));
    if (alt.length > 0) wildPick = alt[Math.floor(rnd() * alt.length)];
    else wildPick = wild[Math.floor(rnd() * wild.length)];  // wild 不足时保持原语义
  }
  picked.push(wildPick);
  return picked.slice(0, n);      // ★ 现在恒为 n（n ≤ pool.length 时）
}
```

**配套的落码条款**：
1. `RunOptions` 加 `seed?: number`（`src/types.ts:50-68`），并**把 `seed` 写进产物**（否则事后无法复盘）。
2. 我们的 DEV 集必须**锁帧集**：对同一条题的所有臂，用**同一 `seed`** ⇒ 臂间唯一变化是拓扑，不是帧集。
3. 产物里**必须记 `frameIds` 数组**（ADHD 的 `bench/results.json` **没有**这个字段 ⇒ 它的"novelty 增益来自跨域帧"这个归因**无法从产物复核**）。
4. 我们的 A/B 对照臂若也用 `Math.random() < 0.5` 决定顺序，**必须同时落盘 `swapped` 标志**（ADHD 做了这一步，抄）。

### 5.3 `trap` 字段 —— 我们要拿它当"承重/失效条件"的离散载体

**类型定义逐字**（`src/types.ts:12-19`）：
```ts
export type Score = {
  novelty: number;     // 0-10, away from the obvious
  viability: number;   // 0-10, could actually ship
  fit: number;         // 0-10, addresses the stated problem
  total: number;       // weighted
  trap?: string;       // if it looks good but is a trap, why
  strength?: string;   // the one concrete thing this idea gets right
};
```

**评分提示词逐字**（`src/engine.ts:71-89`，`SCORE_SYSTEM`）：
```
You are in CONVERGENT mode. You are now the critic.
Score each idea on three axes 0-10:
- novelty: distance from the obvious default solution
- viability: could this actually ship / work in practice
- fit: how directly it addresses the stated problem

Tell the truth about weaknesses — don't soften the substance. But the
critic's job is to produce two symmetric signals, not just one:

- "strength": required for every idea, even weak ones. The single most
  concrete thing this idea gets right that a competing idea doesn't.
- "trap" (optional): if the idea looks attractive but has a hidden cost
  (false economy, won't scale, premature abstraction), name it as a
  specific, actionable heads-up — e.g. "solid for a prototype, breaks
  past 10k concurrent users" — not a dismissal like "bad idea." The
  fact stays the fact; only the framing changes: information you can
  act on, not a verdict on the idea's worth.

Output JSON only.
```

**输出 schema 逐字**（`src/engine.ts:199`）：
```
[{"id":"...","novelty":0-10,"viability":0-10,"fit":0-10,"strength":"...","trap":"... or omit"}]
```

**权重的确切位置与用法**（`src/engine.ts:214-228`）：
```ts
const out = new Map<string, Score>();
for (const r of rows) {
  // Weight: novelty matters because the whole point is escaping the obvious,
  // but viability is the gatekeeper — a brilliant unshippable idea is a trap.
  const total = r.novelty * 0.35 + r.viability * 0.4 + r.fit * 0.25;   // ← :218
  out.set(r.id, { novelty: r.novelty, viability: r.viability, fit: r.fit, total, trap: r.trap, strength: r.strength });
}
```

**`trap` 的下游用法（这是"离散载体"的关键）**（`src/engine.ts:404-408`）：
```ts
// Shortlist: top by total, excluding traps. Traps reported separately.
const traps = allIdeas.filter((i) => i.score?.trap);
const shortlist = allIdeas
  .filter((i) => i.score && !i.score.trap)          // ← trap = 硬性排除
  .sort((a, b) => (b.score!.total - a.score!.total));
```
⇒ **`trap` 是二值门（存在/不存在）+ 一段自由文本理由**；被标 trap 的点**不进 shortlist**，但**单独成段输出**（`src/render.ts:60-64`，段标题逐字：*"Traps (watch-outs, not verdicts)"*）。

⇒ **为什么它正好是我们的"承重/失效条件"载体**：
| 我们的需求 | `trap` 提供的 | 缺什么 |
|---|---|---|
| 离散（可判定） | ✅ 存在/不存在 = 二值 | — |
| 指向**失效条件**而非"不好" | ✅ 提示词逐字要求 "a hidden cost (false economy, won't scale, premature abstraction)"、*"not a dismissal like 'bad idea'"* | — |
| 指向**承重点** | ⚠️ 只有 `strength` 半边 | 我们的"承重"问句是"这条信息改变了哪个决策"⇒ **需要把 `strength` 的问句改成我们自己的** |
| 与 diversity 度量正交 | ✅ 论文的 Vendi 测不到"这条会坏" | — |

⇒ **我们的落码规格**：
1. **保留 `trap` 的二值 + 自由文本结构**（可判定 + 可行动）。
2. **把 `strength` 的问句改成承重问句**：从 *"The single most concrete thing this idea gets right that a competing idea doesn't"* 改为 **"这个点改变了哪个决策？若没有它，结论会怎样变？"**（这是我们"思维面"的承重定义）。
3. **`trap` 率作为离散多样性指标之一**（§3.4）：`trap_rate = 被标 trap 的比例`。⚠️ **注意方向**：trap 率**高**可能意味着"批判更严"（好事）也可能意味着"想法更诱人但更坏"（坏事）⇒ **必须与另外两个读数联合报，不得单独解读**。
4. ⚠️ **ADHD 的 trap 判定是同源 LLM**（判官 = 生成器同族）⇒ 我们若用 trap_rate 做判据，**判官必须异源**，否则我们只是把 U6 污染搬进新指标。
5. ⚠️ **ADHD 的 judge 在 trap_detection 上有饱和**（既有精读 `20_adhd_mintlify.md` §"最容易骗我们的"已实证：breadth 6 题全 9、零方差）⇒ **我们报 trap_rate 时必须同时报判官自身的方差**，且**必须有人类盲评校准**（§6）。

### 5.4 §5 我们要直接用的两块（清单）

| 要用的 | 从哪抄 | 抄什么 | 必须改什么 |
|---|---|---|---|
| **15 帧池** | `src/packs/core.ts:3-109` | 15 条 id/label/prompt/tags **逐字**；`tags` 语义（`code`/`design`/`general`/`wild`） | ⚠️ 帧是**英文**的 ⇒ 我们的产品是中文 ⇒ **逐条重写 prompt 为中文**（但保持"vantage operator"而非"persona"的定位）；⚠️ 我们的 `remove-assumption` 帧要按我们自己的"承重维度"问句重写 |
| **`trap` 字段** | `src/types.ts:17` + `src/engine.ts:71-89,199,218,404-408` | ① `trap?: string` 二值+理由；② 提示词里"hidden cost / not a dismissal"的措辞纪律；③ trap 门排除 + 单独成段 | ① `strength` 问句换成承重问句；② 判官异源；③ trap 的"不 dismissal"措辞要保留（否则就退化成"打分"） |

---

## 6. 人类验证流程

### 6.1 论文的协议（Appendix B 逐字，全文）

> **Appendix B**（`paper.txt:587–594`）：
> *"To assess whether the automatic diversity metrics used in this work align with human judgments under our task setting, we **recruited five AI PhD students with expertise in relevant research areas**."*
>
> *"**B.1 Procedure** — For each topic, annotators were presented with **25 randomly sampled pairwise comparisons** of proposal sets generated under different collaboration modes. In total, **each annotator evaluated 100 pairwise comparisons**. **Blind to the system identities**, they were asked a single question: **'Which proposal set exhibits greater diversity of research ideas?'**"*
>
> *"**B.2 Quality Control** — Annotators were also instructed to verify that all proposal sets met a **basic bar of idea quality (coherent, on-topic, plausible)**. All evaluated sets satisfied this criterion. This confirms our assumption that diversity analysis is performed on a valid candidate set."*
>
> *"**B.3 Agreement Results** — We measured the agreement between **human majority judgments** and the ranking induced by automatic metrics. The Vendi Score achieved the highest alignment (**87%**), followed by Structural Disorder ( 1−φ ) and Semantic Dispersion (PCD)."*

> **Table 1**（`paper.txt:44–52`）：Metric | Human Agreement (%) —— **Vendi Score 87% / 1−φ 82% / PCD 81%**。
> ⚠️ **W-D-3 不在 Table 1 里** ⇒ **论文从未用人类验证过 W-D-3** ⇒ 又一条"别拿 W-D-3 当主判据"的理由。

### 6.2 我们的 DEV 子集盲评规格（20–50 对）

```
样本量：20–50 对（DEV 子集；先做 20 对做流程彩排，再扩到 50）
单位  ：一对 = (臂 X 的产物集, 臂 Y 的产物集)  ← 成对，不是打分
盲评  ：两侧顺序随机（每对独立随机），并落盘 swapped 标志
单问  ："哪一组的研究想法更多样？"（只这一问，不问质量、不问优劣）
前提  ：每组先过"质量门槛"检查（coherent / on-topic / plausible）——
        不过门槛的组不进入多样性比较（论文 B.2 的纪律）
读数  ：多数票 vs 我们各自动度读数的一致率 —— ★ 必须逐个度量报，不能只报主判据
```

**我们与论文的 3 个必要差异**：

| # | 论文的做法 | 我们的改法 | 理由 |
|---|---|---|---|
| 1 | 5 位**AI 博士生**标注 | **混合标注者：≥1 位真实领域专家 + ≥1 位"资深工程师/目标用户"** | 论文自己承认任务是"科学提案生成"、是"hybrid constraint"域；我们的 DEV 题若偏产品/工程，**专家的"多样性"标准与人不同** ⇒ 至少要有一名目标用户在场 |
| 2 | 只报一致率（87/82/81%） | **一致率 + 一致率的二项置信区间 + "不可分辨"档** | 20–50 对下，87% 的 95% CI 大约是 ±10pp；**必须给出 CI 才不误导**。且要预先定义"不可分辨"（如一致率 < 60% ⇒ 该度量在此域无判据力） |
| 3 | 只在**多样性轴**做人类验证 | **人类验证同时校准我们的 `trap` 标注** | 我们的 `trap_rate` 是离散判据，必须有一个人类锚 |

### 6.3 我们必须自己补的 3 件事（论文没做）

1. **噪声地板 δ**：论文 **每个 setting 只有 1 次采样视角的统计**（per-topic Vendi 是 50 条提案的 Vendi，不是 50 次独立跑）⇒ 论文报不出"同一配置重复跑"的波动。我们必须先测 δ，**所有小于 δ 的差异判为不可分辨**。
2. **反向断言校准**：论文的 Table 1 只报"一致率"。**一致 ≠ 有效**。我们必须加一组**注入实验**：故意把两组做成"明显更集中"（例如把 B 臂产物复制一遍），确认我们的度量**会**报出差距 ⇒ 否则我们不知道自己的尺子是不是恒等于"看起来不一样"。
3. **判官同源 vs 异源双读**：论文的质量轴是 DSV3 判 DSV3（论文 Limitations 自认）。我们若用 `trap` 或任何 LLM 判据，**必须同源 + 异源各读一遍并报差异**。

---

## 7. 未读到 / 不能核的（明确标注，不脑补）

| 项 | 状态 |
|---|---|
| 论文附录 **G.2 完整 transcript** | ❌ 只读了 G.1（检验规则）/ G.3（词汇集中度）/ G.4（参与度 vs 语义新颖度）的**规则与统计**，未逐条读 4 个 mini-case 的原文 |
| 论文附录 **O 的全部提示词模板** | ❌ 只读了 O 的 "Proposal Generation Format Prompt" 与 N 的 "Stance Classification Prompt" |
| 论文 **10,000 条原始 proposal**、所有聚合 CSV | ❌ 仓库 README 明示不 ship ⇒ **所有论文侧指标数值我都没能在真实数据上复算** |
| **`bench/results.json` 的 6 条完整 transcript** | ❌ 未取（本次只读了 `EVALS.md` 的逐题裁决表与 `bench/judge.ts`） |
| 论文 Appendix **L（温度）** 的逐主题数字 | ⚠️ 读了结论段（既有精读 22 号已记录 T=0.3/0.7/1.0 的 per-topic 值），本次未逐格复算 |
| **"Standard" 到底是不是第四种拓扑** | ❌ **论文没说清**。我补一条新证据：`analysis/figures/fig10_topology_dynamics.py:22` 把 **`"Standard"` 映射到 `./data/extracted_proposals/extracted_proposals_recursive`** —— 即 **Fig 10 的 "Standard" 与 Appendix I 的 "Recursive" 是同一份数据**，而 Appendix M 又把 "Standard" 与 "Recursive" 当**两个不同格**报 3 组 ANOVA（η²=0.829）。⇒ **Appendix M 的 "Recursive(2.823) vs Standard(1.659)" 这条旗舰对比在 shipped 代码里没有对应实现**。已由既有 22 号精读独立发现，本文件补上了代码行级证据。 |
| 我**没有跑任何模型** | ⚠️ 唯一执行的是 `selectFrames` 的逻辑复刻（§5.2），其余全部为逐字引用 |

---

## 8. 引用清单

**论文**
- Chen, N., Tong, Y., Yang, Y., He, Y., Zhang, X., Zou, Q., Wang, Q., & He, B. (2026). *Diversity Collapse in Multi-Agent LLM Systems: Structural Coupling and Collective Failure in Open-Ended Idea Generation.* Findings of ACL 2026, 251–306. DOI `10.18653/v1/2026.findings-acl.13` ｜ arXiv `2604.18005`
- 仓库 `Xtra-Computing/MAS_Diversity`（MIT）：`README.md` / `ASSETS.md` / `docs/persona_mapping.md` / `analysis/metrics/{compute_vendi_and_order,compute_vendi_extended,compute_vendi_sec_models,compute_vendi_sensitivity,compute_proposal_metrics}.py` / `analysis/figures/{fig10_topology_dynamics,fig11_interaction_landscape,figA1_gpt51_cross_topology,figA3_w3_factorial}.py` / `simulation/configs/*.yaml`（5 个逐字读）/ `simulation/{launch_scientist,run_dynamic_topic,run_dynamic_topic_subgroup}.py`
- ar5iv 全文：`https://ar5iv.labs.arxiv.org/html/2604.18005`（945 KB 完整）
- ACL PDF：`https://aclanthology.org/2026.findings-acl.13.pdf`

**ADHD**
- Akhouri Raj, U. (2026). *ADHD: Parallel Divergent Ideation for Coding Agents.* 预印本 v0.1, 2026-05-25, MIT. `https://adhdstack.github.io`
- 仓库 `UditAkhourii/adhd`（MIT）：`src/packs/core.ts` / `src/frames.ts` / `src/types.ts` / `src/engine.ts` / `src/render.ts` / `src/llm.ts` / `bench/*` / `EVALS.md` / `ADOPTERS.md` / `SOURCE-SPEC.md` / `documentation/*`
- 文档站 `https://adhd.mintlify.site`（`/llms.txt` 索引、`/concepts/frames.md`、`/concepts/how-it-works.md`、`/evals/methodology.md`）

**访问日期**：2026-10-21（UTC）
