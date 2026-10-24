# DEEP-18-11 · Curiosity Search + POET → 「思维面 = 有效信息维度数」可抄规格

> **产出定位**：不是摘要，是**能直接抄进我们代码/协议**的规格。
> **取材**：`PMC5010182` 与 `arXiv:1901.01753` 的**全文**（PDF 抽取文本，71 条引文全部程序核对，见 `DEEP-18-11-quotes.md`）。
> **标注约定**（每条断言都带标签，不许混）：
> - `【论文】` = 原文事实，引文 ID 见 `DEEP-18-11-quotes.md`（如 `C17` = Curiosity Search 引文 17）。
> - `【代码】` = 官方实现 `uber-research/poet` 的事实（`file:line`）。
> - `【我们】` = **本规格新增的设计**（两篇论文都没有）——落地前需要 owner 确认。
> - `【论文没写】` = 缺口（照抄会踩空的地方）。
>
> **我们项目的既有口径**（引用自 `routes/PROTOCOL.md` / `routes/DEV/DEV-SPEC.md`，未改写）：
> `VD_net`（净有效维度增益，逐任务 `VD_added − VD_lost`）、`vd_final`、`n_cards_total`、承重卡、`conflict_rate`、
> 种子噪声地板与三段判读表（`> 2× 地板` 可分辨 / `≤ 2×` 写"不可分辨"）、F1–F8、`devset_id`/`devset_hash`/`judge_prompt_version`/`arm_config_hash`。

---

## 0. 身份核对（**先看这个：任务书里的标签有三处不对**）

| 任务书写的 | 核实结果 | 证据 |
|---|---|---|
| `PMC5010182` = "Curiosity Search … Pathak, Agrawal, Efros, Darrell, ICML 2019" | ❌ **标题对，作者/出处全错**。PMC5010182 = **Stanton C, Clune J (2016)**, *Curiosity Search: Producing Generalists by Encouraging Individuals to Continually Explore and Acquire Skills throughout Their Lifetime*, **PLoS ONE 11(9): e0162235**, DOI 10.1371/journal.pone.0162235, PMID 27589267 | Europe PMC 记录；PDF p.1 题名页与 `Citation:` 块（`_raw/deep18/PMC5010182_text_paged.txt` p.1） |
| "ICML 2019 有 Pathak 的 Curiosity Search" | ❌ **该论文不存在**。PMLR v97（ICML 2019）索引里 grep "Curiosity" 只命中 *Curiosity-Bottleneck: Exploration By Distilling Task-Specific Novelty*；同族的 Pathak 论文是 v97/pathak19a = **"Self-Supervised Exploration via Disagreement"**（抓取 PMLR 页面确认标题） | `https://proceedings.mlr.press/v97/`（750KB 索引）、`.../v97/pathak19a.html` |
| "CS_O = f = t，把目标从适应度里拿掉" | ⚠️ **语义反了**。`CSO`/`CNTO` 出自 PMC5010182 的 **S4 Fig**：`f = t`（**tiles only**），下标 `O` = **“only”**，不是 “objective”。同段还写了 "it is enough for the algorithm to reward exploration alone" | `C24` / `C24b` / `C25` |
| `1901.01753` = POET | ✅ **对**。全名：*Paired Open-Ended Trailblazer (POET): Endlessly Generating Increasingly Complex and Diverse Learning Environments and Their Solutions*；作者 **Rui Wang, Joel Lehman, Jeff Clune, Kenneth O. Stanley**（PDF 首页标注 Clune & Stanley 为共同资深作者）；arXiv v3, 2019-02-21；GECCO 2019 | arXiv API `id_list=1901.01753`；PDF p.1 |

**顺带核过（避免又一次抄错家族）**：`arXiv:1806.00553` = *Deep Curiosity Search*（Stanton & Clune, ALife 2018）。全文 grep：**没有** `f = t` / `CS_O` / `NS_T` / `NSGA` ⇒ 用户记忆里的 "`CS_O (f = t)`" **只可能**来自 PMC5010182 自己的 S4 Fig。

**对本规格的影响**：**没有影响** —— 用户点名的全部机制（NS vs CS、拿掉门、Fig 7b、CSO、NSGA-II、终身距离、POET 的最小准则/迁移/共演化）**全部真实存在**，只是出处是 Stanton & Clune 2016 + Wang et al. 2019，不是 Pathak et al. 2019。下面的规格照原计划写。

---

## 1. 行为刻画（BC）的可抄定义 —— 替代「答案文本 embedding」

### 1.1 论文给了三种 BC 形态（都能直接抄）

| 形态 | 原文 | 引文 | 适用我们哪一部分 |
|---|---|---|---|
| **离散计数** | "one might create a discretization in which there are **K possible behaviors** and the score is the number of behaviors in K that have been expressed" | `C3` | 单份答案的"有效维度数"（我们口径：`vd_final` / 承重卡覆盖的结论数） |
| **距离切分** | "the intra-life novelty score might instead demarcate behaviors using a **distance function**" | `C3`（同段） | 跨样本新颖度（NS 口径） |
| **遗传编码（= 免 BC）** | "the encoding of an environment is in effect a **genetic representation** … in POET in effect novelty is a **genetic diversity** measure. That way, POET **does not in principle require a behavior characterization (BC)** to be devised for environments, though doing so is also not precluded." | `P23` | DEV 题本身：题 = 一串基因（见 §5），题的多样性 = 基因向量的新颖度 |

**距离口径（NS 距离，CS 论文原文）**：
> "distance is computed by the **averaged Manhattan distance between each coordinate** (i.e. `||a − b||₁ / k` where k is the length of vectors a and b; **this has sometimes been mistakenly referred to as Euclidean distance**)."
> —— `C9`

⚠️ 我们在文档/代码里**必须写"逐坐标平均曼哈顿"，不许写"欧氏距离"**（论文自己点名了这个误称）。

**新颖度算法（POET 口径，可直接抄）**：`kNN` 平均距离，`k = 5`，`L2`，参考集 = **当前活跃集 + 归档 archive**（`P21` `P24`；代码 `novelty.py:30-44`、`poet_algo.py:272-273`）。
→ **我们的对应：k=5，参考集 = 曾准入过的 DEV 题的参考解 BC（archive）**。

### 1.2 【我们】BC 规格（写进 `spec.yaml` / `metrics.py`）

```yaml
bc:
  type: typed_slots_over_conclusion_space     # 不用 free-text embedding
  unit: DEV 题的 conclusion_space（DEV-SPEC §2，3–8 条命题，id C1..C8）
  vector_of_sample:
    - "onehot(conclusion_id) for c in covered_conclusions"   # 长度 = |conclusion_space|
    - "n_load_bearing / 8"                                    # 承重卡数 / 归一
    - "n_total / 16"                                          # 卡片总数 / 归一
    - "key_hit / 3"                                           # 命中 key_conclusions 的条数 / 3
  distance: L1                 # 逐坐标平均曼哈顿，同族于 C9
  knn_k: 5                     # 同 POET（P24）
  archive: DEV/MANIFEST.json 里所有曾准入版本的参考解 BC
  forbidden: 答案文本 embedding / 余弦相似度
```

**为什么禁 embedding**（模板 §6 的专项检查，答案在这里）：
- 两篇论文的"宽度/新颖性"**都不是** embedding 余弦：CS 用逐坐标曼哈顿（`C9`），POET 用**显式基因编码的 L2**（`P24`）⇒ 抄它们**不会**继承 embo-01 那种"句级几何无分辨率"的病。
- 我们 `creativity_lab/metrics.py` 里现存的 `escape / spread / effective_rank / modes / dispersion` **全是 embedding 家族**（`metrics.py:17-57`）⇒ 若继续用它们量"宽度"，就等于在"有效信息维度数"上继续用一把没有分辨率的尺子。

### 1.3 终身行为距离（NST / 轨迹距离）的定义、实现口径与**成本**

| 项 | 内容 | 出处 |
|---|---|---|
| **定义** | 比**整条轨迹**而不是终点；"aims to make Novelty Search more **lifetime-aware**" | `C8` |
| **距离公式** | 逐坐标平均曼哈顿：`||a − b||₁ / k`，`k` = 向量长度 | `C9` |
| **参数来源** | "Both metrics use the same parameters as **Velez and Clune 2014 [9]**" —— 本文**不重述** k 值等参数 | `C9`（同段） |
| **实现口径** | "we chose **trajectory-based** Novelty Search over a **tile-based** implementation to enable comparisons to the former, which has already been shown to work well on other tasks [19] and **for which a tested implementation was already provided in rtNEAT and Sferes**" ⇒ 实现依托 NS 框架的 **archive + kNN**，不是自定义距离表 | `C10` |
| **计算成本** | ⚠️ **【论文没写】**：CS 论文**没有给任何复杂度/开销分析**，也没给 archive 规模、每代 kNN 的开销。POET 那边同样只给 k=5 与 L2（`P24`），没有成本表 | — |

**【我们】成本口径（工程估算，非论文主张）**：
- 时间：每算一个新样本的新颖度 = 与 archive 中**每个**成员算一次距离 ⇒ `O(|archive| × 轨迹长度)`；kNN 取前 5 只是排序开销。
- 空间：archive 要存**整条轨迹**（不是只存终点）⇒ `O(|archive| × 轨迹长度)`；这就是 NST 相对 NSE 的**主要额外成本**（NSE 只需存终点）。
- ⇒ **在我们的场景**：若轨迹 = "答案覆盖的结论 id 序列"，长度 ≤ `|conclusion_space|`（3–8）⇒ 成本可忽略 ⇒ **建议直接上轨迹口径**；这也解释了为什么论文说轨迹版"explore more but not usually as much as CS"（`C13`）。
- ⚠️ **别把 k 值抄成未知数**：`C9` 只说"参数同 Velez & Clune 2014" ⇒ 我们若要写进协议，**必须自己定 k 并预注册**（建议 k=5，与 POET 一致，`P24`），并写明"这是我们的取值，不是论文的取值"。

**我们已有一个现成的、judge-independent 的 BC 候选（可直接复用，别重造）**：
`net_dimension_gain.hard_tokens`（数字/书名号专名/拉丁长词）+ `net_dimension_gain.cjk_ngrams`（4 字中文 n-gram 覆盖率，阈值 `thr=0.45`）—— 确定性、**零模型调用**、路线 A 已在用它做跨臂对齐（`routes/A/DESIGN.md:115`）。
⇒ **建议：BC 的"硬指纹/内容词"通道直接复用这套口径**，与 `conclusion_space` 槽位通道**并列**（一个给"说了什么内容"，一个给"覆盖了哪些结论维度"）。

**验收**：
1. 同一题、不同样本的 BC 距离 **= 0** ⟺ 二者覆盖同一组结论 ⇒ 「有效维度数」有了**定义式**落点，而不是 embedding 距离的代理。
2. BC 向量维数**与题无关**（schema 固定）⇒ 跨题可比、可做 kNN。
3. **地板自检**：在中庸样本上 BC 不得退化为零向量（否则又是一次地板效应）。

**【论文没写】**：BC 的**自动发现**。CS 论文明说 "Because the automatic identification of new and increasingly complex behaviors is **not yet technically feasible**"（`C29`）⇒ 我们的 BC **必须人工/规则定义并写进协议**，否则换一次协议版本就换了一把尺子（这正是我们要治的漂移）。

---

## 2. 终身（轨迹）距离 vs 终点距离 —— 我们选哪个、为什么

### 2.1 论文事实

- NS 的两版行为距离：**NSE = 只比终点**；**NST = 比整条轨迹**（`C8`）。NST "aims to make Novelty Search more **lifetime-aware**"（`C8`）。
- 为什么终点距离会"早闭"（原文）：
  > "In an endpoints-version of Novelty Search, specialization occurs because if e.g. the west branch is most novel, **there is no incentive for an individual to first head east before fully exploring the west branch—only the final location matters.** However, a trajectory-version of Novelty Search does reward an individual for this behavior …"
  > —— `C11`
- 读数：4/5 迷宫里 NSE 最佳个体探索 **< 50%** 域，NST 显著更多（`p < 0.0001`）（`C14`）。
- 图级证据：Fig 4 —— "(a) Fifty trajectories from a NSE population are overlaid to show the **population-level coverage** … but (b) a **typical NSE individual** only explores a small portion of that domain, whereas (c) a typical CS individual tends to explore significantly more"（`C13`）⇒ **同一张图里，群体覆盖与个体承重是两条曲线**。
- **但轨迹距离是"群体相对"的**：
  > "Curiosity Search rewards individuals for doing everything (or … for going everywhere); **Novelty Search instead rewards individuals for being different from other individuals.**"
  > —— `C12`

### 2.2 【我们】选择：**自相对（intra-life）为主 + 群组相对（轨迹 kNN）为辅**

| 口径 | 论文出处 | 我们的角色 | 落地 |
|---|---|---|---|
| **自相对计数**（"我这一份覆盖了多少互不相同的维度"） | CS：`f = t + d`（`C5`） | **主目标** | `VD_net` / `vd_final`（协议 §3.1），判据绑**单份答案/单题** |
| **群组相对轨迹距离**（kNN, k=5） | POET 新颖度（`P21` `P24`）+ CS 的 NST（`C8`） | **辅助目标**（NSGA-II 的第二目标，见 §4） | BC 向量的 kNN L1 距离均值 |
| **终点距离** | NSE（`C8`） | **只用于"同一份答案的内部结构"**（如是否停在单一结论上） | ❗**不作为新颖度主口径** |

**理由（对照我们两个病灶）**：
1. **地板效应（9/12 样本 VD=0）**：终点距离奖励"停在一个新点"——中庸答案最容易在中庸点稳定 ⇒ 终点距离**在地板上饱和**。CS 论文的病灶描述正是我们病灶的机制同构（`C11`）。轨迹/自相对口径才能区分"去过 3 个地方"与"停在 1 个地方"。
2. **搜索空间过早闭合**：CS 论文证明"只要终点"就会诱导**专精**（specialization），并用 Fig 7b 证明**种群覆盖 ≠ 个体承重**（`C17`）⇒ 终点口径同时制造早闭。

**必须同时满足的两条护栏**（`【论文没写】`的部分是我们加的）：
- **护栏 A（防早闭）**：任何新颖度指标在**单维度答案**上必须**单调不饱和**（天花板检验）。
- **护栏 B（防地板）**：任何新颖度指标在**中庸答案**上**不得**给出"新颖"信号（地板检验）⇒ 读数恒 0 的样本必须被标 `untestable`，不得计入"多样"。

---

## 3. leave-one-out 判「某条依据是不是一个独立维度」

### 3.1 论文先例（**不是 LOO，但机制同构，可直接借**）

| 先例 | 原文 | 引文 | 借给我们的什么 |
|---|---|---|---|
| **拿掉门** | "we test CS and NST in each maze **with and without doors**. If the doors are merely obstacles requiring no skill to open, **removing them should have little to no effect** on our results" | `C18` | LOO 的**零假设**：去掉一个维度 ⇒ 读数应几乎不变 |
| 拿掉门的**读数** | "both CS and NST agents explore **nearly twice as much** … when the doors are removed (p < 0.0001 …). Furthermore, the exploration gap … **disappears almost entirely**" | `C19` | LOO 的**阳性判据**：去掉后读数**显著变化** ⇒ 该维度是**独立技能** |
| 拿掉门的**图注** | "suggesting that the doors in these experiments are an **abstraction of distinct skills**, which CS seems better able to acquire" | `C20` | 我们对"独立维度"的措辞 |
| **单技能探针** | "placing agents in an environment in which **the only task is to open doors**; agents were graded on **how many different types of doors they could open**" | `C22` | **only-d 探针**（§3.2 的第一项） |
| 探针的读数口径 | "each of which is designed to test a **single door-opening skill** … Agents are given 250 time steps … scores based on the number of mazes in which they successfully open the door (up to 4; values are **normalized to fall within [0, 1]**)" | `C23` | 探针的**评分归一**口径 |
| **别加惩罚** | "all tested forms of punishment **severely reduced individual exploration** … any punishment … may actually discourage exploration because it punishes the natural process of trial-and-error. Thus **we do not use any punishment model**" | `C33` | 我们**不惩罚中庸**（中庸本身不是错误，只是无信息） |

### 3.2 【我们】LOO 规格（两轴 + 地板守卫）

```python
# 输入：DEV 题 D（conclusion_space = {c_1..c_m}，evidence = {EV-..}），基线臂 B0 与被测臂 A
# 读数：VD_net（协议 §3.1）；门槛：协议 §3.2 三段判读表（> 2× 种子噪声地板 ⇒ 可分辨）

def independent_conclusion(D, c, A, B0):
    """c 是否是一个独立维度（不是别的结论的冗余）"""
    D_minus = D_without_conclusion(D, c)              # 删掉 c，其余结论/依据包不变
    delta = VD_net(A, D) - VD_net(A, D_minus)          # 逐任务净增益之差
    if not detectable(delta, floor=2 * seed_noise_floor):
        return "not_independent"        # 去掉它读数不变 ⇒ 冗余（与别的结论重复）
    if VD_net(A, D_minus) <= 0:
        return "untestable"              # 去掉后塌成地板 ⇒ 不是"不独立"，是"测不出来"
    return "independent"

def load_bearing_evidence(D, ev, A):
    """某条依据是否承重（删掉它 ⇒ 引用它的承重卡消失）"""
    cards = extract_cards(A, D_without_evidence(D, ev))
    return not any(c.evidence_ref == ev for c in cards)   # 承重卡消失 ⇒ 该依据承重

def only_probe_detectable(D, c, A):
    """only-c 探针可检出（C22 式）：只留 c 一条结论，其余从结论空间移除"""
    return VD_net(A, D_with_only_conclusion(D, c)) > 0
```

**判定表（可直接抄进协议）**

| `only-c` 探针 | Δ(去掉 c) vs 地板 | 结论 | 写法 |
|---|---|---|---|
| 不可检出（VD=0） | — | **不可测** | `untestable`（**不得**写"不独立"）← 这就是 9/12 样本 VD=0 的病 |
| 可检出 | 不可分辨（≤ 2× 地板） | **不独立**（冗余） | `not_independent` ⇒ 该结论与别的重复 ⇒ 合并/删除 |
| 可检出 | 可分辨（> 2× 地板） | **独立维度** | `independent` |

**为什么必须带"untestable"这一档**：我们的地板效应（VD=0）会让"删掉这个维度 → VD 仍然是 0"看起来像"这个维度不重要"，其实它是"**这一题整体测不出来**"。这两件事混在一起，我们就会把**尺子坏了**当成**题没维度**——正好治反了。

**否证/失败条件（协议侧）**：若 9 道 DEV 题里 **≥5 道**存在 `not_independent` 的结论 ⇒ **DEV 集本身有冗余** ⇒ 先修 DEV 集再谈架构（否则 `VD_net` 的天花板被人为压低，F1 会恒触发）。
**【论文没写】**：LOO 判据本身两篇论文都没有；上面是借"拿掉门"的机制**自造**的（`【我们】`）。

---

## 4. 多目标（NSGA-II）配置

### 4.1 论文事实

- **是 NSGA-II**（Deb et al. 2002），用 Sferes 的默认参数：
  > "Because Curiosity Search optimizes a **single objective**, it could suffer from **deception** … and might benefit from added diversity … **We combine Curiosity Search + Novelty Search using NSGA-II [34]**, adopting default NSGA-II parameters provided by Sferes."
  > —— `C7`
- 两目标 = CS 的适应度（`f = t + d`）与 NS 的新颖度；两版行为距离 CNE / CNT（`C7` `C8`）。
- **为什么必须要多目标**（单分数会"混淆"多样个体）：
  > "In this paper, fitness in Curiosity Search only considers the **number** of unique behaviors expressed. An agent that learns how to swim and drive has expressed the same number of behaviors as an agent that instead learns how to climb stairs and pick locks … a single fitness score … **might conflate a plethora of diverse agents**."
  > —— `C4`
- **读数**：
  - 多目标让探索 **+20–50%**，并让"终点 vs 轨迹"的差异**完全消失**（`C15`）。
  - CNT 探索 **≈90%**，比任一单独处理高 **15–25%**（`p < 0.0001`）⇒ CS 作为 **helper objective** 最好（`C16`）。
  - CS 单独用会"possibly prone to deception"（`C16` 原文）⇒ 辅助多样性目标是**必需品**，不是装饰。

### 4.2 【我们】配置（主目标 VD_net，辅助 多样性）

```yaml
multiobjective:
  algorithm: NSGA-II            # 同 C7（Deb 2002）；参数从 Sferes 默认改成我们的
  objectives:                    # ← 两个独立目标，不做加权和
    - id: VD_net
      direction: maximize
      definition: 协议 §3.1 逐任务 (VD_added - VD_lost)，臂内取任务级中位数
    - id: novelty_bc
      direction: maximize
      definition: BC 向量对 archive 的 kNN 平均 L1 距离（k=5，§1.2）
  pareto_selection:              # ← 【论文没写】必须我们自己预注册
    rule: "取前沿上 VD_net 最大者；VD_net 并列时取 novelty_bc 更大者；再并列取前沿中 BC 距离最大者"
    tie_break_must_be_preregistered: true
  archive: 前沿全体入 archive（防早闭）；每代记 front_size / front_spread
  guard:
    - "辅助目标不得进入 F1 的符号判据（协议 §3.2：F1 判符号、不受 2× 门槛约束）"
    - "多目标只影响『选哪个解』，不改主判据与门槛"
```

**为什么不用加权和**：加权和会把两个不同量纲（净维度数 vs 距离）压成一行，阈值随权重漂 ⇒ 我们已经有"读数跨版本漂移"这个病，不能再引入一个自由参数。CS 论文正是用 NSGA-II（而非加权和）来解决"多样性只能当辅助"的矛盾（`C7` `C16`）。

**【论文没写】**：CS 论文**没有**描述 Pareto 前沿怎么选、也没给 NSGA-II 的具体参数（只说"Sferes 默认"）⇒ 我们的 `pareto_selection.rule` **必须自己写死并预注册**（否则就是"看结果挑前沿"= 自污染）。另外：**CS 论文的读数显示，多目标会抹平"终点 vs 轨迹"的差异**（`C15`）⇒ 对我们意味着：**辅助目标会掩盖 BC 口径的差别**，所以 BC 口径的选择必须在多目标**之外**单独做消融（§2 的护栏 A/B）。

**否证**：若多目标只在 `novelty_bc` 上变好而 `VD_net` 中位数不变 ⇒ 辅助目标**不可分辨**（按协议三段判读写"不可分辨"，**不写**"有效"）。

---

## 5. POET 式 DEV 题共演化（按"最小准则"筛/增 DEV 题）

### 5.1 POET 的确切机制（全部逐字在 quotes 里）

| 环节 | 原文 | 引文 |
|---|---|---|
| 三个主任务 | "1. generating new environments E(·) from those currently active, 2. optimizing paired agents within their respective environments, and 3. attempting to transfer current agents θ from one environment to another." | `P5` |
| **变异 = 扰动编码** | "POET simply **mutates** (i.e. randomly perturbs) the **encoding** (i.e. the parameter vector) of an active environment." | `P6` |
| 基因表 | stump height / gap width / step height / step number / surface roughness | `P12`（Table 1） |
| **变异步** | "an obstacle parameter takes a **mutation step** (whose magnitude is given in Table 1), and either **adds or subtracts** the step value from its current value." | `P11` |
| **seed 决定实际采样** | "the actual environment sampled from that distribution is the result of a **random seed**. This seed value is stored with each environment so that environments can be be reproduced precisely, ensuring **repeatability**." | `P10` |
| **繁殖资格** | "the paired agent of the environment achieves a **reward of 200 or above**" | `P13` |
| **★ 最小准则（确切判据）** | "The **minimal criterion (MC) 50 ≤ E_child(θ_child) ≤ 300** then filters out child environments that appear **too challenging or too trivial** for the current level of capability of agents." | `P14` |
| MC 的语义 | "not added … unless they are **neither too hard nor too easy** for the current population" | `P9`；"not too trivial and **not too hard** (which would lead to little progress)" `P20` |
| **★ 新颖度排序** | "**priority is given to those candidate environments that are most novel**, which produces a force for diversification that encourages many different kinds of problems to be solved in a single run" | `P7`；"ranked based on their novelty … calculated with respect to the current active population of environments and **an archive** of all previously active environments" `P21`；"**L2-norm** … nearest neighbors **k … is 5**" `P24` |
| **转移后再查一次 MC** | "Each pair is then **checked against the minimal criterion again** in case some pairs no longer satisfy the minimal criterion after the transfer (e.g. if an environment is **exposed as too easy**)" | `P22` |
| 容量/退休 | "capped at a maximum size … the **oldest environments are removed** to make room (as in a queue)" | `P8` |
| **难度分级**（可借来给 DEV 题分级） | "a **challenging** environment satisfies one of the three conditions; a **very challenging** environment satisfies two of the three; and satisfying all three makes an environment **extremely challenging**" | `P33` |
| **隐式课程** | "Because newer environments in POET are created through **mutations of older environments** and because POET only accepts new environments that are **not too easy not too hard** … POET **implicitly builds a curriculum** for learning each environment it creates." | `P32` |

**【代码】交叉核对**（`uber-research/poet`）：
- `poet_algo.py:237-241` `pass_mc(score)` ⇒ `score < mc_lower or score > mc_upper` ⇒ **False**。
- `poet_algo.py:270` **子环境用父环境的 agent 去评**（`o.evaluate_theta(self.optimizers[parent_optim_id].theta)`）⇒ MC 量的是"**以当前能力**看，这道题是太难还是太 trivial"。这是 MC 的灵魂：**相对当前能力的难度带**。
- `poet_algo.py:272-273` 新颖度 `k=5`；`novelty.py:30-44` 顶层 kNN 均值。
- `poet_algo.py:312-321` 定向转移后再 `pass_mc(score_child)` 才准入。
- `poet_algo.py:346/354` 节奏：`adjust_interval(=4) × steps_before_transfer(=25)` ⇒ **每 100 次迭代生成一次新环境，每 25 次迭代做一次转移**（`master.py:57,66`）。

**⚠️ 两处「论文 vs 代码」不一致（照抄必错，必须知道）**：
1. **MC 带**：论文写 `50 ≤ E ≤ 300`（`P14`），**代码默认是 `mc_lower=25, mc_upper=340`**（`master.py:59-60`）。
2. **准入排序**：论文正文说"若过 MC 的子环境太多，**分数更低（更难）**的先收"（`P15`），但 **Algorithm 3 + 代码是按新颖度降序收**（`poet_algo.py:279` `sorted(child_list, key=lambda x: x[4], reverse=True)`）。
   ⇒ 我们的 DEV 题准入规则**必须自己写一条并预注册**，不能抄。
3. （附带）Table 1 的 gap width 上限写 `(10.0, 10.0)`，代码是 `max_value=[8.0, 8.0]`（`reproduce_ops.py:101-102`），而论文自己的归一化段落也写 `Gap_lower = Gap_upper = 8` ⇒ **表格不可盲抄**。

### 5.2 【我们】DEV 题共演化规格（把 DEV 题当 POET 的 environment）

**基因表**（落到 `routes/DEV/DEV-SPEC.md` 的真实字段）：

| 基因 | 含义 | 初值 | 变异步长 | 上限 | 依据 |
|---|---|---|---|---|---|
| `n_conclusions` | `conclusion_space` 条数 | 4 | ±1 | 8（DEV-SPEC §2） | `P11` 式 ±step |
| `n_evidence` | `evidence` 条数 | 按题 | ±1 | 12（DEV-SPEC §3） | 同上 |
| `n_distractors` | `gold/*.json` 的 `distractors` 条数 | 3 | +1 | 6（DEV-SPEC §4） | 同上 |
| `ask_len` | 题面字数 | 20–60 字 | ±10 字 | 60（DEV-SPEC §1） | 同上 |
| `key_ratio` | `key_conclusions` 占结论空间比例 | 1–3 / 3–8 | ±1 比例点 | 3（DEV-SPEC §2） | 同上 |
| `seed` | 抽取/判官采样种子 | 固定 | 重采样 | — | `P10` |

**最小准则（我们的 MC）** —— **必须带通，且参考解法器必须冻结**：

```
s(D')  = 分离度读数(冻结参考解法器 σ_ref, 冻结判官提示词版本 v_judge, 候选题 D')
MC 带:  L ≤ s(D') ≤ U         # L, U 在 DEV 集建库时一次定死，随 pipeline 不变
准入:  s(D') ∈ [L, U]  且  novelty(D') ∈ 前 N（k=5 kNN L2, P21/P24）
```

**为什么必须是"带通"而不是单边**（这是我们与 POET 唯一需要**改造**的地方）：
- POET 的带：下界 = 太难（当前能力够不到），上界 = 太 trivial（`P9` `P14` `P20`）。
- 我们：**太难**（答案里什么都测不出 ⇒ VD=0）与**太中庸**（答案里什么都测不出 ⇒ VD=0）**产生同一个读数** ⇒ 两端都会塌。⇒ 必须用**带通**（`L ≤ s ≤ U`）而不是"越高越好"或"越高越难越好"。

**⚠️ 关键约束（与 §7 绝不能抄 #1 同源，这里是它的正面写法）**：
- `s(D')` **不得**用"当前 pipeline 在 D' 上的 VD_net"来算（那会随 pipeline 漂移 ⇒ 尺子每版换一次 ⇒ 复现不了）。
- `s(D')` **必须**用**冻结**的参考解法器 + **冻结**的判官提示词版本，并把 `judge_prompt_version` / `arm_config_hash` 一起写进 MC 记录（协议 §4.4 的元数据清单已含这两项）。
- **零模型、零判官的候选读数**：`net_dimension_gain.hard_tokens` + `cjk_ngrams`（`thr=0.45`）是确定性的 ⇒ **MC 的下界/上界应优先用这类口径标定**（`s` 的"下限"= 至少有多少条依据被答案提到），判官读数只做**上限侧**的复核。

**退休与复检**：
- **退休**：`REMOVE_OLDEST` 式（`P8`）——DEV 题超上限时退最早的，`MANIFEST.json` 记 `retired_at`（可复现）。
- **复检**：照 `P22`（转移后再查一次 MC）⇒ **每跑完一版 pipeline，对 DEV 题重查 MC**：若某题掉出带上界（`s > U`，已经太 trivial ⇒ 测不出差别）⇒ 标记 `exhausted` 并退休，**不许**继续留在 DEV 集当诊断题（否则就是拿一道已失效的题反复测地板）。

**⚠️ 我们与 POET 的关键分歧（必须写进协议）**：
- POET 是**开放演化**（题库无限扩张）；**我们的 DEV 集是冻结后共享的**（协议 §4.2）⇒ **共演化只能产出新版本**（`devset_id` + `devset_hash` 递增），**不许原地改 D01–D09**。
- ⇒ 我们做的是「**有上限的离线题库扩展**」，不是开放演化。报告里必须这么写，别把 POET 的"无尽"叙事搬过来。

**验收 / 否证**：
- 若新造题（过 MC）的 `VD_net` 中位数与原 DEV 集**不可分辨**（≤ 2× 地板）⇒ 共演化**没带来新信息** ⇒ 停，并写"不可分辨"（不写"失败/成功"二选一）。
- 若新造题把 `only-c` 探针的可检出率拉低 ⇒ 新题更中庸 ⇒ 回滚该基因步长。

---

## 6. 迁移 / 留出纪律（防"任务级结构过拟合到该任务"）

### 6.1 论文事实

**CS 的迁移协议（三步，照抄）**：
> "We test whether CS produces agents with similar or better exploration skills than Novelty Search by **(1) evolving individuals in the Cross Maze, (2) transferring the best-exploring individuals into the other four mazes, and (3) evaluating their ability to explore the new environment, both without and with further evolution.**"
> —— `C26`

读数（**两段必须分开报**）：
- **不进一步进化**："Curiosity Search **matches, but only rarely exceeds**, the transfer performance of NST … in aggregate **no significant difference** (p ≥ 0.05). However, … (CNT) explores **10% more** than any other treatment (p < 0.01 in aggregate)"（`C27`）
- **进一步进化**："There was **no significant difference** (p ≥ 0.05) between NST and CS after further evolution. Also, **the original exploration difference disappears immediately at the onset of evolution**"（`C28`）
  ⇒ ⚠️ **教训**：迁移的"净学习"在**第一代**就可能被洗掉。**不把"迁移后继续进化"和"迁移瞬间"混成一段读数**，就会把"被洗掉"读成"没差别"。
- **反直觉，必须记住**："Target Endpoints, which explored the **least** in the original maze, **outperforms all treatments after transfer** except for CNT"（`C27` 上下文 / Fig 9 图注）
  ⇒ **低探索 ≠ 低可迁移性** ⇒ 我们的 DEV 题**不能**因为"当前读数低"就判死。
- **迁移机制本身**："POET adopts a transfer mechanism that allows one agent (the emigrant) to attempt to transfer its learned capabilities to a target environment, **possibly replacing the current target environment’s agent**"（`P25`）；"each agent in the augmented list (the original M agents and each of their M proposals) is evaluated in E(·) and **the one with the highest reward is returned**"（`P26`）⇒ **迁移的判据 = 在目标环境里的最高奖励**，不是"源环境里更好"。
- **双向迁移（子 → 父）**："the child agent eventually learns to stand up and jump over the stumps, and at iteration 1,175 that skill is **transferred back to the parent environment**" ⇒ 同等算力下，原步态 **309** 分 vs 迁移后步态 **349** 分（`P28`）
  ⇒ **单向"父 → 子"的课程是不够的**；我们的留出池必须允许**反向**迁移（子集学到的结构回到留出题上）。

**POET 的迁移纪律**：
- 定期**全互试**（`N_transfer`，`P19`）；两类替换：**direct**（直接搬）与 **proposal**（先在目标环境走一步 ES 再搬）（`P27`）。
- **记账**："replacement attempts in RUN 1, RUN 2, and RUN 3 are **18,894, 19,014, 18,798**, respectively, out of which, **53.62%, 49.26%, 48.89%**, respectively, are **successful replacements**"（`P29`）
- **覆盖率度量**（像样子的空间度量，不是"种群很宽"）：均匀采 1,000 + 1,000 + 1,000 = **3,000** 个环境，算每个到"已创建并已解出"的最近距离，**覆盖越好 ⇒ 最近距离之和越小**（`P30`）。
- **消融（最硬的一条）**："the coverage … created and solved by POET is **significantly greater** than by POET without transfer (**p < 2.2e−16** …) … in POET without transfer, **no extremely challenging environments are solved at all**"（`P31`）
  ⇒ 迁移不是锦上添花，是"**能不能碰到难题**"的前提。

### 6.2 【我们】留出纪律（可直接抄进协议）

```yaml
holdout:
  pools:
    generator_pool:  D01–D09      # 允许被变异 / 共演化 / 调参
    holdout_pool:     D10+        # 冻结；只在新版本里出现，只在最终读数时用
  frozen:
    - judge_prompt_version         # 迁移读数必须用固定版本（协议 §4.4 已有该字段）
    - arm_config_hash
    - devset_id + devset_hash
  transfer_readout_two_segments:   # 照 C28 的教训
    - segment_A: 零适应迁移（在留出题上直接评，不做任何进化）
    - segment_B: 迁移后继续进化 N 轮再评
  report: 两段分开报；A 段显著、B 段不显著 ⇒ 写"迁移的净学习在第一代被洗掉"，不写"迁移无效"
  overfit_probe:                  # 任务级结构过拟合的直接证据
    rule: 同一题在 holdout_pool 的 VD_net 显著低于在 generator_pool 的 VD_net ⇒ 存在题级结构记忆
    action: 必须写明；不得只报 generator_pool 读数
  transfer_accounting:            # 照 P29
    record: 每次 pipeline/提示词版本切换的"迁移尝试数 / 成功替换数 / 成功率"
```

**判据锚点**：迁移判据必须绑**最终产物**（协议已有规则）⇒ 迁移读数 = 留出池上、由冻结 pipeline 算出的 `VD_net`。
**否证**：若留出池上的 `VD_net` 中位数 ≤ 0 **且**与生成池**不可分辨** ⇒ 增益是题级结构记忆 ⇒ 该臂按 **F1 判死**。

---

## 7. 绝不能抄（4 条）

### ❌ 绝不能抄 #1：把"最小准则"实现成"用会漂移的判官读数做带"
POET 的 MC 量的是**参考解法器**在一个**有物理意义的刻度**上的分数（走完赛道得多少分；`P13` `P14`），并且**子环境是用父环境的 agent 去评的**（`poet_algo.py:270`）⇒ MC 是"**相对当前能力的难度带**"。
我们若改成"当前 pipeline 在题上的 `VD_net`"当 MC：
1. MC 随 pipeline 变 ⇒ **每版都在换尺子** ⇒ 在 9/12 = 0 的地板上量 0（正是我们要治的病）；
2. 更糟：MC 会**挑出"当前判官能分辨"的题** ⇒ 把**测量带宽**当成**信号**。
**修法**：`s(D')` 必须由**冻结**的参考解法器 + **冻结**的判官提示词版本算出；`L/U` 一次定死；`judge_prompt_version` 进 MC 记录；优先用**零模型**口径（`hard_tokens` + `cjk_ngrams`）标定下界。

### ❌ 绝不能抄 #2：把"种群覆盖"当成个体能力
Fig 7b 原文：
> "The **population of every treatment**, even those that produce specialists (such as TE), can explore the entire maze, **revealing that population diversity alone is not sufficient to encourage generalists.**"
> —— `C17`
⇒ 我们的 9 道 DEV 题"覆盖了很多维度"**不能**当"答案不中庸"的证据；判据必须绑**单份答案**（`VD_net` 是逐任务/逐样本的，协议 §3.1）。
同理 POET 的覆盖率度量（`P30`）是**环境空间覆盖**，不是个体能力 —— 照搬成"我们的题库覆盖广 ⇒ 我们的系统宽"是同一类错误。

### ❌ 绝不能抄 #3：把 MC 当作"可解性证明"
POET 接受环境靠的是**乐观接受**："we accept problems if (**according to some heuristics**) they seem likely to be improved upon and/or solved after some amount of dedicated optimization effort"（`P4`）；论文还点明 MCC 路线的局限："in MCC problems have to be solvable by the current population, so **complexity can only arise through drift**"（`P3`）。
⇒ **形式化可解性**必须由 `routes/DEV/DEV-SPEC.md` §2/§4 保证（`conclusion_space` 可判定 + `gold/Dxx_cards.json` + `distractors`），**不能靠 MC**。

### ❌ 绝不能抄 #4：照抄 POET 的准入排序（论文与代码冲突）
论文正文说"过 MC 的太多时，**分数更低（更难）**的先收"（`P15`），代码却按**新颖度降序**收（`poet_algo.py:279`）。这类"论文 ↔ 代码不一致"的地方一抄就抄错。
⇒ **我们的准入规则自己写死一行并预注册**（建议：先按新颖度降序取前 N，再在带内；`exhausted` 的题优先退休）。

---

## 8. 交付摘要：3 条能直接用 + 2 条绝不能抄

**能直接用（3 条）**
1. **BC 口径（§1.2）**：`BC = 承重卡覆盖的 conclusion_space 指示向量 ⊕ 归一计数`，距离 = 逐坐标平均曼哈顿 `||a−b||₁/k`（`C9`，不许写"欧氏"），新颖度 = **kNN(k=5) 平均距离**（`P24`），参考集 = archive（`P21`）。**不用答案文本 embedding**（两篇论文都不用 ⇒ 不继承 embo-01 的病）。
2. **NSGA-II 双目标（§4.2）**：主目标 = `VD_net`（协议 §3.1），辅助 = `novelty_bc`；**不加权和**；**Pareto 前沿选择规则必须自己预注册**（论文没写）。读数依据：多目标让探索 +20–50%（`C15`）、CNT ≈ 90% 域（`C16`）。
3. **POET 式 DEV 题共演化（§5.2）**：基因表（仿 Table 1）+ ±step 变异 + seed 可复现（`P11` `P10`）；**MC = 带通** `L ≤ s(D') ≤ U`（POET 原式 `50 ≤ E ≤ 300`，`P14`），**s 用冻结的参考解法器/冻结判官版本**；新颖度排序 k=5（`P24`）；MC **转移后复检**（`P22`）；超容量**退最老**（`P8`）。

**绝不能抄（2 条）**
1. **别把 MC 建立在会漂移的判官读数上**（否则尺子每版换一次，且把测量带宽当信号）——见 §7 #1。
2. **别把"种群/题库覆盖"当个体能力**（Fig 7b，`C17`）——判据必须绑单份答案；POET 的覆盖率是环境空间覆盖（`P30`），不是个体宽度。

（另外两条：别把 MC 当可解性证明 `P3`/`P4`；别抄 POET 那个自相矛盾的准入排序 `P15` vs `poet_algo.py:279`。）

---

## 9. 证据索引与复核方法

| 产物 | 路径 | 说明 |
|---|---|---|
| 逐字摘录（71 条，全部程序核对） | `/workspace/lab/routes/LIT/DEEP-18-11-quotes.md` | 锚点 = PDF 页 + 刊印页 + 抽取文本行号 |
| CS 原文 PDF（PLoS ONE） | `_raw/deep18/PMC5010182_stanton_clune_2016_plosone.pdf` | 21 页 |
| CS 抽取文本（分页） | `_raw/deep18/PMC5010182_text_paged.txt` | 引文行号锚点 |
| CS Europe PMC 全文 XML | `_raw/deep18/PMC5010182_europepmc_fulltextXML.xml` | 章节结构（JATS） |
| POET 原文 PDF | `_raw/deep18/1901.01753v3_poet.pdf` | 29 页 |
| POET 抽取文本（分页） | `_raw/deep18/1901.01753v3_poet_text_paged.txt` | |
| POET 官方实现（本次下载的快照） | `_raw/deep18/poet_repo/` | `poet_algo.py` / `novelty.py` / `reproduce_ops.py` / `master.py` |

**复核命令**（任何人可重跑）：
```bash
# 1) 重跑引文核对（找不到 ⇒ abort，不出文件）
python3 /workspace/work/build_quotes.py
# 2) 抽查任意一条引文：页码 + 行号
python3 - <<'PY'
t=open('/workspace/lab/routes/LIT/_raw/deep18/PMC5010182_text_paged.txt',encoding='utf-8').read().split('\f')
print(t[12].split('\n')[7:12])      # PDF 第 13 页 = Fig 7 图注
PY
# 3) 论文 ↔ 代码差异
grep -n "mc_lower\|mc_upper" /workspace/lab/routes/LIT/_raw/deep18/poet_repo/master.py
grep -n "sorted(child_list" /workspace/lab/routes/LIT/_raw/deep18/poet_repo/poet_algo.py
```

**本次核验发现的 3 个标签错误（已在 §0 修正）**：① PMC5010182 的作者/出处不是 Pathak et al. ICML 2019（是 Stanton & Clune 2016 PLoS ONE）；② ICML 2019 没有 "Curiosity Search" 这篇（Pathak 同族是 v97/pathak19a "Self-Supervised Exploration via Disagreement"）；③ `CS_O` 的 `O` = **tiles only**，不是 "objective removed"。
