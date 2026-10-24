# 25 — Novelty Search and the Problem with Objectives

> 精读组 5 / 第 1 篇。**这不是"检索页"指向的论文本体定位笔记，而是论文本体的完整提取。**
> 定位过程见 §0「找到它的路径」。

## 0. 引用

| 项 | 内容 |
|---|---|
| 标题 | **Novelty Search and the Problem with Objectives** |
| 作者 | Joel Lehman, Kenneth O. Stanley（均 UCF, Dept. of EECS） |
| 年份 | 2011 |
| venue | *Genetic Programming Theory and Practice IX* (GPTP 2011), Springer New York；丛书 *Genetic and Evolutionary Computation*；**第 1 章，pp. 37–56** |
| DOI | **10.1007/978-1-4614-1770-5_3** |
| 稳定链接（DOI） | `https://doi.org/10.1007/978-1-4614-1770-5_3` |
| 稳定链接（作者自托管全文 PDF，**绿 OA，可直接读**） | `https://www.cs.swarthmore.edu/~meeden/DevelopmentalRobotics/lehmanNoveltySearch11.pdf`（23 页；我实际下载的就是这份） |
| 姊妹论文（同作者同主张，期刊版，引用量主战场） | Lehman & Stanley, *Abandoning Objectives: Evolution Through the Search for Novelty Alone*, **Evolutionary Computation** 19(2), 2011, DOI **10.1162/evco_a_00025**（PubMed 20868264）；OA PDF: `http://web.cs.swarthmore.edu/~meeden/DevelopmentalRobotics/lehman_ecj11.pdf` |
| 引用量（核验时点 2026-10-21） | Semantic Scholar **176**；OpenAlex **127** |

**一句话（它声称自己解决了什么）**：
> 它主张**目标导向搜索（objective-based search）本身有根本病灶——"雄心的目标不会照亮通往自身的路径"**——并给出直接证据：在 360 个随机生成的迷宫上，**完全不知道最终目标的新颖性搜索（novelty search）反而比直接朝目标搜的解出率显著更高**；因此"放弃目标"可能比"追目标"更能到达雄心目标。

### 找到它的路径（可复现）

1. `https://scholar.google.com/scholar?q=...` —— **按预期被拦/不可用作稳定入口**，未作为主路径。
2. **Crossref REST**（主路径，一击命中）：
   `https://api.crossref.org/works?query.bibliographic=Novelty+Search+and+the+Problem+with+Objectives&rows=5`
   → 第 1 条即目标：`TITLE: Novelty Search and the Problem with Objectives` / `AUTH: Joel Lehman, Kenneth O. Stanley` / `2011` / `container-title: Genetic and Evolutionary Computation`（+ 副标题 `Genetic Programming Theory and Practice IX`）/ `DOI: 10.1007/978-1-4614-1770-5_3` / `type: book-chapter`。
3. **拿到全文**：web_search 在 LessWrong 一条长帖里命中作者自托管 PDF 直链 `cs.swarthmore.edu/~meeden/DevelopmentalRobotics/lehmanNoveltySearch11.pdf` → `curl` 下载 **HTTP 200, 198,202 bytes, 23 页** → `pdftotext -layout` 得 60,523 字节全文（本文件所有引文均出自此 PDF，页码 = PDF 页内标注的印刷页码）。
4. **第二/第三来源独立核验**：
   - **OpenAlex** `https://api.openalex.org/works/https://doi.org/10.1007/978-1-4614-1770-5_3` → 标题/作者/年份/venue 一致；`W135283623`；`biblio: first_page 37, last_page 56`；`open_access.is_oa = false`（出版社侧闭源，**但作者自托管版可读**——这一点必须知道，否则会被当成"抓不到"）。
   - **Semantic Scholar** `https://api.semanticscholar.org/graph/v1/paper/DOI:10.1007/978-1-4614-1770-5_3` → `paperId 1325bbd04a3e5a7e8137cf2edf9cbca7fc6fd55d`，`citationCount 176`，`referenceCount 36`，`venue ""`（出版社没喂给 S2）。
   - 同一 Crossref 查询的第 3 条命中姊妹期刊论文（`Abandoning Objectives`, DOI `10.1162/evco_a_00025`）——**说明"这个标题"有两篇同名近作**，引用时不要混。

> ⚠️ **引用陷阱**：这篇是 **Springer 书章**，不是期刊论文。`container-title` 在 Crossref 里显示为丛书名 "Genetic and Evolutionary Computation"，而 `Genetic Programming Theory and Practice IX` 出现在 `publisher` 字段。写 bib 时要用 **GPTP 2011 书名 + pp.37–56 + DOI**，不要写成 "Evolutionary Computation 2011"（那是姊妹篇）。

---

## 1. 核心机制（要具体到能照着实现）

| 项 | 内容 |
|---|---|
| **输入** | GP 迷宫导航任务（表 1-1）。程序由 **终端集** `{Left(左转), Right(右转), Move(前进一格)}` + **函数集** `{IfWallAhead(按正前方有墙选两子程序之一), IfGoalAhead(按目标是否落在正前方 90° 锥内选两子程序之一), Prog2(顺序执行两子程序)}` 构成。**360 个用递归分割法（recursive division）随机生成的迷宫**；起点与目标随机。复杂度代理 = **起点到目标的最短路径长度**（10–100，每长度取 4 个迷宫 ⇒ 360 = 4×(100−10+1)）。 |
| **有没有状态** | 无环境状态；但搜索过程**有状态**：novelty **archive**（永久保存所有"新行为"个体）+ 当前种群。 |
| **状态表示** | **行为空间 = 机器人的"结束位置"坐标（2 维几何）**。原文：「the behavior of a navigator is defined as its ending position」。archive 存的是**行为**不是基因型：「The novelty of a newly-generated individual is computed with respect to the behaviors (i.e. not the genotypes) of an archive of past individuals and the current population」。 |
| **动作/算子** | ① 评测：程序被反复执行 **200 个时间步**，记录结束位置。② 打分：**novelty metric**（见下）**替换** fitness。③ 选择：常规 EA 选择（选高分者繁殖）——「tracking novelty requires little change to any evolutionary algorithm aside from replacing the fitness function with a novelty metric」。④ 变异/交叉为标准 GP 算子（文中未细列）。 |
| **过程/回路** | 每代：全部个体评测 → 算 novelty → 排序选择 → 繁殖出下一代 → **新个体若 novelty 高于阈值则入 archive** → 下一代。**archive + 当前种群 = "搜索去过哪里 + 现在在哪"的完整采样** ⇒ 梯度恒指向"新"。 |
| **停止条件** | **最大代数 200 / 400 / 600**（三档），种群大小 **500**。原文：「Termination: Maximum number of generations = 200, 400 and 600」。 |
| **输出** | 演化出的迷宫导航程序（GP 程序树）。任务成功与否 = **是否在 200 步内到达目标**。 |
| **谁来评价 / 评价信号怎么回传** | ★ **双通道，关键在这里**：<br>① **搜索信号 = novelty metric**（**完全不需要 oracle**，纯内部几何量：到 k 近邻的平均距离）；<br>② **评价信号 = 外部 oracle**（到达目标与否，二值）。oracle **不进入搜索回路**，只用于事后统计"解出率"。<br>公式：ρ(x) = (1/k) Σ_{i=0}^{k−1} dist(x, μ_i)，μ_i 是 x 的第 i 近邻，dist 是**领域相关**的行为距离。 |

**novelty metric 的定义细节（实现级）**
- k 近邻平均距离 ⇒ 度高稀疏区得分高；密集区得分低。
- 近邻计算**必须同时考虑当前种群与永久 archive**。
- 迷宫实验中：k-NN 的距离 = **两个个体结束位置的欧氏距离**。原文给了关键直觉：「two robots stuck in the same corner appear similar, while one robot that simply sits at the start position looks very different from one that reaches the goal, though they are both equally viable to the novelty metric.」

---

## 2. 关键数字

**实验设置**
- 360 迷宫 × **每个 10 次独立运行** × 3 方法（**fitness-based / novelty / random selection**）= 11,400 次运行。
- 种群 500；代数上限 200 / 400 / 600；每次评估 200 步。
- 3 臂里 **random selection 被明确当作"区分 novelty 与随机探索"的对照组**：「Random selection was considered as a control to differentiate novelty search from random exploration of the search space.」

**主指标与读数（具体值）**
- **核心结论**：novelty search 解出的实例**显著更多**（**p < 0.001，Fischer's exact test**）；**线性回归截距显著不同**（**ANCOVA，p < 0.001**）⇒ novelty 在**复杂度更高**处仍然领先。
- **复杂度相关性**：最短路径长度 vs 各方法性能 **adjusted R² > 0.75**（每个方法都成立）⇒ 路径长度是合法复杂度代理。
- **额外评测的利用效率**（图 1-3b）：novelty 的"解出率 vs 评测次数"曲线斜率更好 ⇒ 「novelty search better exploits additional evaluations」。
- **前作数字（本文复述）**
  - 难迷宫（Lehman & Stanley 2008，NEAT）：**novelty 39/40 成功**（解迷宫**不是**它的目标），objective-based **仅 3/40**（解迷宫**就是**它的目标）。
  - 双足行走（50 runs）：novelty **4.04 m (sd 2.57)** vs objective **2.88 m (sd 1.04)**；**最佳**步态 **13.7 m vs 6.8 m**。

**消融**
- 无传统意义的组件消融（这是 EA 论文）。等价的对照是**三臂**（fitness / novelty / random）+ **三档代数**（200/400/600）。⚠️ **没有 k（近邻数）的消融、没有行为描述符的消融** ⇒ 度量的敏感性未测。

**成本**
- 无 token / 美元。计算成本 = 种群 500 × 代数 × 评测（200 步/次）+ archive 的 k-NN 查询。archive 成本被作者点名为真实开销（§7.3），可用 **kd-tree** 降复杂度，且「it may often be possible to limit the size of the archive without harming novelty search's performance」。

---

## 3. ★ 它的「成功标准」是什么

**（a）它怎么判定自己成功了？**
- **评价指标 = 外部 oracle 的解出实例数**（"是否在 200 步内到达目标"），**不是**"新颖性得分高不高"，**不是**"多样性指标"。
- **对照结构 = 三臂**：fitness-based（传统目标搜索） / novelty（本文主张） / **random selection（防"novelty 其实只是随机探索"的对照）**。
- **统计口径**：计数用 **Fischer's exact test**；趋势差异用 **回归 + ANCOVA（截距检验）**；复杂度代理的合法性用 **adjusted R²**。
- ⚠️ 注意这里最精妙的一点：**novelty 在这里只是"搜索信号"，成功与否由一个与 novelty 完全无关的 oracle 判定。** ⇒ 它的主指标**不可能被 novelty 指标本身污染**。

**（b）否证 / 失败条件有没有写？—— 有，而且写得很硬。**
- §6 Results 末：「It is important to note that the performance of each of the three compared methods decreases with increasingly complex maze instances. **Few instances are reliably solved by any of the methods with optimal path length greater than 80.** Thus while novelty search may outperform the other methods in this domain, **it too struggles to discover specific ambitious objectives from first principles**; this result tentatively supports the hypothesis that in some cases attempting to achieve specific objectives from a random starting point may ultimately be futile beyond a certain level of problem complexity.」
- §6 引言：「while **not** susceptible to traditional deception, novelty search also is **not guaranteed** to consistently find specific objectives as problems become more complex.」
- §8：「while novelty search is a viable alternative to objective-based search and has been shown to outperform it in non-trivial domains, **it is no panacea** and also **so far falls short of natural evolution**.」

**（c）有没有报告"不可分辨"这种结果？—— ❌ 没有。**
- 全文**没有**噪声地板 δ、**没有**"在某个区间两者无显著差异"的显式报告、**没有**"效应量 + 置信区间"这套东西（只有 p 值 + adjusted R² + 回归图）。
- 它用 **10 次重复**估方差（biped 报了 sd），但**没有**把"n=10 下 p<0.001 与 p=0.06 之间的差别"处理成"不可分辨"档。
- ⇒ **这正是我们要补的**：我们的协议必须预注册"不可分辨"档（我们已有 σ_d(k) 公式，n≈13.3(σ_d/Δ)²），而它没有。

---

## 4. 自认的局限（原话优先）

1. **★ 度量决定了搜索走哪条路（对我们最致命的一句）**（§6, p.13）：
   > 「**The novelty metric determines the behavior-space through which search will proceed. It is important that the type of behaviors that one hopes to distinguish are recognized by the metric.**」
   （原句：定义 novelty metric "requires careful consideration because it **biases the search in a fundamentally different way than the fitness function**"。）

2. **维度 / 行为空间可以大面积无意义**（§7.2）：
   > 「Of course, it is possible to construct scenarios in which **vast sections of the behavior space are uninteresting**. However, search in such cases can be accelerated by restricting which behaviors are considered novel.」

3. **archive 成本**（§7.3）：
   > 「because it grows continually over the course of evolution, it may eventually become **computationally expensive to calculate the novelty of a new individual**.」

4. **novelty 是不是又一个目标？（辩护性自证）**（§7.4）：
   > 「novelty does not favor any particular part of the search space; instead, it is **relative to what behaviors have been previously encountered, is constantly changing, and is largely orthogonal to the actual objective of the experiment**.」

5. **度量必须领域适配**（§4）：
   > 「like the fitness function, **this measure must be fitted to the domain**.」

6. **与自然进化相比差很远**（§1/§8）：
   > 「although novelty search does outperform objective-based search in many deceptive problems, **it too pales in comparison to the creative achievement of natural evolution**.」

---

## 5. ★ 对我们项目的可迁移点

**映射到：路线 A / B / C / 优化器契约 L0–L4 / 测量协议 / DEV 集设计**

| 我们的东西 | 它对应什么 | 怎么用 |
|---|---|---|
| **测量协议：判据分层** | **搜索信号 vs 评价信号双通道** | ★★★ **最值得抄的一条。** 它用 novelty 搜、用 oracle 判 ⇒ **用来搜的量绝不用来判成功**。我们的对应物：**"净维度增益"（工作流 − 直调）是评价侧；"装配顺序/依据包轮转"是搜索侧**。若我们一边用"新颖度"当搜索压力、一边又用"新颖度/维度"当成功判据，就是它的 §7.4 陷阱（自评污染 ⑥）。**规则：凡出现在依据包里的量，不能同时出现在判官提示词里。** |
| **DEV 集设计 / 对照臂** | **三臂：fitness / novelty / random** | ★★ 加**第三臂**：我们现在是「工作流 vs 直调」二臂。加一臂「**内容无关装配 + 打乱/空依据包**」可区分"增益来自**拓扑**" vs "增益来自**包里真有承重信息**"。这直接对应它用 random selection 排除"novelty 只是随机探索"。**省掉**：以后每个主张都不用再单独辩护"是不是随机波动"。 |
| **维度 = 可被依据包核验且改变决策的承重信息** | **behavior characterization（行为描述符）** | ★★★ 它**强制**把度量放在**行为空间**而非基因型/文本空间，并明说"metric 决定了搜索走哪条路"。⇒ 我们的"依据包可核验性"就是行为描述符的加强版：**可核验 = 结构化 + 可回查**。它给我们一个现成理由说明**为什么不能用措辞/相似度当描述符**（描述符必须在行为层）。 |
| **路线 C（人定拓扑 + 训练调参数）** | **archive（新颖行为记忆）** | ★★ 把"见过什么"从 agent 上下文里挪到**外部结构化 archive**：这是"先设计再训练"路线的最小实现——archive 是人定的结构，参数是搜出来的。⇒ 我们的**依据包**若按 archive 方式组织（存"该方向此前是否已被用过/用过什么"），就是一个可核验的新颖性记忆，**不依赖 embedding 几何**。 |
| **路线 A（固定拓扑）/ 路线 B（训练架构）** | 它是**纯 L0** | ⚠️ 它**不提供**"如何选度量"的学习机制——metric 是**人先验写死**的（k-NN 距离函数 + 行为描述符都是设计者规定的）。⇒ 我们**不能**指望路线 B（训练学出操作序列）能自动学出"什么算新颖"；这块是 L0/L1 的人工设计区，论文没覆盖 ⇒ **别把我们的缺口指望它填。** |
| **缺 DEV 集与噪声地板 δ（坑⑤）** | 它的统计纪律 | 它**有**重复(×10)、**有**对照组、**有**Fisher/ANCOVA，但**没有** δ 噪声地板、**没有**"不可分辨"档。⇒ 我们的 δ 与"不可分辨"预注册是**超越**它的地方，不要倒退。 |

**能省我们什么（具体）**
- 省掉一次"为什么我们的判据不会被自己骗"的论证 ⇒ 直接引它的双通道结构 + §7.4 的自证段落。
- 省掉一整个实验分支：不用再单独证明"我们的新颖性度量不是随便挑的"，因为它提供了**标准做法**（描述符落在行为层、且**必须声明它如何改变搜索**）——但它**没**提供"如何验证描述符的分辨率"，这部分仍要我们自己造（embo-01 的教训）。

**要改什么才能用**
- 它的 novelty = **k-NN 稀疏度（几何距离）**；我们的"承重信息" = **可核验 + 改变决策**。**量纲不同 ⇒ 不可直接抄 metric。**
- 它假设行为空间**低维且有明确几何**（迷宫终点 2 维；另文试过 400 维轨迹）。我们的依据包是**语义/结构**空间 ⇒ 直接套 k-NN 会撞上坑②（embo-01 句级几何无分辨率）。

---

## 6. ★ 不可迁移 / 会误导我们的点

- **★ 最容易骗我们的一条：k-NN 稀疏度 ≠ 承重信息维度。**
  它测的是"**行为几何上不同**"，**不测**"信息是否承重、是否可核验、是否改变决策"。我们若把"新颖"实现成"与已见方向在某个空间里距离远"，就是在测**几何差异**而不是**有效信息维度**——这正是我们坑②的翻版（embo-01 把 27 条断言压成 1 条）。
  ⇒ 它的 novelty **不能**作为我们的"新颖性判据"候选实现；它只能作为**搜索压力**的来源，且必须配一个与 novelty 无关的 oracle。
- **★ 它的"新颖性"是从不作为评价指标的。** 它敢写 §7.4「novelty … is largely orthogonal to the actual objective」，是因为它**从不拿 novelty 判对错**。我们的情况正相反：**"新颖/有效维度"就是我们要测的东西**。⇒ 抄它的辩护词到我们的语境里会变成**自评污染（坑⑥）**。
- **它的行为描述符是"结束位置"这种物理量，不是语义量。** 我们没有"结束位置"这种便宜而干净的行为载体 ⇒ 我们的描述符成本高、噪声大 ⇒ 它的结论"novelty 在高维行为空间仍有效"（400 维轨迹实验）**不可迁移**到我们。
- **它没有报告"不可分辨"** ⇒ 我们若只学它的 p 值用法，会继承"p=0.06 到底是没差别还是有差别"的模糊带。**必须自己加 δ + 不可分辨档。**
- **没有度量敏感性实验**（k 值、行为描述符换法、度量换法都没消融）⇒ "novelty 能work"这个结论对**度量选择**的鲁棒性未验证。⇒ 我们若用它论证"多样性有用"，需自己补一次"换度量还成立吗"。
- **量纲/域不同**：迷宫导航 vs 我们的 Agent 架构研究；种群 500 × 600 代 vs 我们的 LLM 调用预算。**它的成本结论（archive 可截断）在我们的 token 预算下完全未验证。**
- **它不是"新颖性"这个词的规范来源**：真正被引爆的是姊妹篇 *Abandoning Objectives* (ECJ 2011, 1212 引)。若我们要在自己的文里立"新颖性 vs 目标"的主张，**引 ECJ 版更稳**，GPTP 书章作为方法细节出处。

---

## 7. 逐字摘录

1. **§6, p.13（"Experiment Description"段）—— 对我们最致命的一句**
   > "Defining the novelty metric requires careful consideration because it **biases the search in a fundamentally different way than the fitness function**. The novelty metric determines the behavior-space through which search will proceed. **It is important that the type of behaviors that one hopes to distinguish are recognized by the metric.**"

2. **§4, p.9（"Novelty Search"节，"The novelty metric measures how different an individual is from other individuals…"段）**
   > "The novelty of a newly-generated individual is computed with respect to the behaviors (i.e. not the genotypes) of an archive of past individuals and the current population. The aim is to characterize how far away the new individual is from the rest of the population and its predecessors in behavior space, i.e. the space of unique behaviors. **A good metric should thus compute the sparseness at any point in the behavior space.**"

3. **§6, pp.14–15（"Results"节末）—— 它自己写的否证条件**
   > "It is important to note that the performance of each of the three compared methods decreases with increasingly complex maze instances. **Few instances are reliably solved by any of the methods with optimal path length greater than 80.** Thus while novelty search may outperform the other methods in this domain, **it too struggles to discover specific ambitious objectives from first principles**; this result tentatively supports the hypothesis that in some cases attempting to achieve specific objectives from a random starting point may ultimately be futile beyond a certain level of problem complexity."

4. **§7.4, p.16（"Novelty as an Objective"节）—— 全文最容易被我们误引的一段**
   > "While some might say that rewarding novelty effectively means that novelty is just a special kind of objective, **novelty is not an objective in the usual spirit of the word in EC**… Yet novelty does not favor any particular part of the search space; instead, it is **relative to what behaviors have been previously encountered, is constantly changing, and is largely orthogonal to the actual objective of the experiment**."

---

## 8. 读完后我自己的一句判断

**最值得抄**：**"搜索信号"与"评价信号"物理隔离**这条结构性做法（novelty 只管搜，oracle 才管判），加上 **random search 作为第三臂**。它把"我用的那个量来判我自己"的污染从设计上消灭掉，比任何事后提醒都硬。

**最容易骗我们**：**k-NN 稀疏度 = 新颖性**这个直觉迁移。它的"新颖"是**低维几何距离**，我们的"新颖"是**可核验且改变决策的承重信息**；而且它从不拿 novelty 判对错，我们恰要拿它判对错 ⇒ 搬过来就同时踩坑②（几何无分辨率）和坑⑥（自评污染）。

**顺手捡的**：它那句 "The novelty metric determines the behavior-space through which search will proceed" —— 正好是我们**装配顺序**这一决定的合法性依据：装配顺序**就是**我们的"behavior-space 选择"，它决定了 agent 往哪走 → 我们的轮转规则**必须**先有"这个顺序选出了哪条路"的显式说明（第 5 篇会正面处理这件事）。

---

## 附：来源清单（访问日期 2026-10-21）

| 用途 | URL / 路径 |
|---|---|
| 论文全文（作者自托管 PDF，23 页，绿 OA） | `https://www.cs.swarthmore.edu/~meeden/DevelopmentalRobotics/lehmanNoveltySearch11.pdf` —— 本地落盘 `/workspace/raw/p1_novelty.pdf`（198,202 bytes，`file` 确认 PDF 1.4 / 23 pages）与抽取文本 `/workspace/raw/p1_novelty.txt`（60,523 chars，`pdftotext -layout`）。**本文件所有引文与数字均出自此 PDF**（页码 = 论文印刷页码） |
| 书目核验（第一来源） | Crossref `https://api.crossref.org/works?query.bibliographic=Novelty+Search+and+the+Problem+with+Objectives&rows=5` → 第 1 条：`DOI 10.1007/978-1-4614-1770-5_3` / `type: book-chapter` / authors Lehman & Stanley / 2011；第 3 条为姊妹篇 *Abandoning Objectives* DOI `10.1162/evco_a_00025`（**引用时勿混**） |
| 书目核验（第二来源） | OpenAlex `https://api.openalex.org/works/https://doi.org/10.1007/978-1-4614-1770-5_3`（`W135283623`、`biblio: first_page 37, last_page 56`、`cited_by_count 127`、`open_access.is_oa=false`） |
| 书目核验（第三来源） | Semantic Scholar `https://api.semanticscholar.org/graph/v1/paper/DOI:10.1007/978-1-4614-1770-5_3`（`paperId 1325bbd04a3e5a7e8137cf2edf9cbca7fc6fd55d`、`citationCount 176`、`referenceCount 36`） |
| 姊妹期刊论文（Ecj 版，引用量主战场） | `http://web.cs.swarthmore.edu/~meeden/DevelopmentalRobotics/lehman_ecj11.pdf`（DOI `10.1162/evco_a_00025`，PubMed 20868264）—— 本次**未下载**，仅记录 |
| 搜索页（不可作稳定入口） | `https://scholar.google.com/scholar?q=Novelty+Search+and+the+Problem+with+Objectives` —— 按预期未作为主路径使用 |
