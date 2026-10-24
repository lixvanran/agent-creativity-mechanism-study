# 「你如何看待高考英语作文」· 产出对照

模型 `x-ai/grok-4.20` ｜ 题 G01 ｜ 每臂 3 次独立重复 ｜ 批次 `20261020-154937-207`（单批）

| 臂 | 含义 |
|---|---|
| **A** | 直接调用 LLM（无状态） |
| **C0** | 立场档案全文进 system prompt |
| **C1** | 取舍驱动的状态机（4 步） |
| **C2** | 状态机 + 事实层 + 极性锚 + 已排除选项（4 步） |
| **S** | 等调用数中性 4 步管线 |

## 产出清单

| 臂 | 次数 | 各次字数 | 含锚点 `the importance of` |
|---|---|---|---|
| A | 3 | 1733 / 1520 / 1543 | 0/3 |
| C0 | 3 | 6699 / 5645 / 5592 | 0/3 |
| C1 | 3 | 1592 / 1944 / 1769 | 0/3 |
| C2 | 3 | 1574 / 1773 / 1557 | 0/3 |
| S | 3 | 1698 / 1720 / 1883 | 0/3 |

---

## 正文

### 第 1 次重复

#### A · 直接调用 LLM（无状态）（1733 字）

高考英语作文像一面镜子，把我们这代人十几年的英语学习照得有点狼狈。

我曾经在考场里把背过的范文几乎一字不改地写上去，得了高分，却在多年后翻出那张试卷时感到一阵陌生的尴尬。那种尴尬不是因为当时的分数，而是因为我清楚地记得，自己在写那些句子的时候，心里其实空空荡荡。我不知道自己真正想说什么，只是熟练地把“with the development of society”塞进第一段，把“in a word”放在最后一段，像完成一次机械的拼图。

成年以后，我才渐渐明白，高考英语作文真正的问题，不在于它要求考生写议论文，而在于它把“议论”这件事简化成了“背诵加套用”。它把语言训练变成了表演训练，把思考变成了记忆。考生们像演员一样，提前知道舞台上需要哪几句台词、哪几个高级词汇、哪种三段式结构，然后在规定时间内把表演做到最流利、最无懈可击。分数越高，往往意味着表演越熟练。

这其实很讽刺。因为英语这门语言，本质上是一种用来建立联系、传递思想、表达自我的工具。可在高考的指挥棒下，它被暂时变成了另一种东西：一种可以被精确量化的得分工具。句子是否“地道”不再取决于它是否真实地表达了说话人的感受，而是取决于它是否符合阅卷老师心目中“标准英语作文”的样子。思想是否深刻也不再重要，重要的是它是否安全、是否正面、是否能迅速被归入某个熟悉的论点框架。

我不是在否定高考英语作文存在的必要性。任何大规模考试都需要相对客观、可量化的评价标准。在几百万考生里，要快速区分语言能力，模板化、结构化确实是最可操作的方式。它像一把粗糙却有效的筛子，把基本语言能力筛选了出来。这一点必须承认。

但问题在于，当这把筛子用了二十多年，而且几乎成了整个中学英语教学的终极目标时，它就开始反噬了。越来越多的学生把精力放在研究“万能句型”“高分模板”“热点话题预测”上，而不是真正去阅读、去思考、去用英语表达自己真正困惑的东西。老师们心照不宣地教这些，因为它见效快。家长们也愿意为孩子报各种作文班，因为它能直接换成分数。整个系统形成了一种默契：我们都知道这不是最好的学习方式，但它是最有效的提分方式。

更让人不安的是，这种训练方式会在人心里留下隐秘的痕迹。我认识的一些朋友，英语成绩曾经很好，高考作文接近满分，可大学毕业后却发现自己几乎无法用英语写一封得体却又真诚的邮件。他们可以轻松背出各种“表达建议”的句型，却在真正需要表达自己观点的时候感到舌头打结。他们习惯了把思考过程裁剪成三段论，习惯了用“on the one hand...on the other hand”来代替真正复杂的权衡，习惯了把所有情感都包裹在“it is widely acknowledged that”这样安全的外壳里。

这不是个别现象，而是一种系统性的后果。

我有时会想，如果把高考英语作文的评价标准稍微改一改，会发生什么。比如，允许考生在作文里真正说一点自己相信的东西，哪怕它不那么“正能量”；允许有不那么标准的表达，只要意思清晰且有一定的复杂度；允许文章有明显的个人风格，哪怕它不像标准范文那样四平八稳。这样的变化当然会让阅卷变得更困难，但也可能让教学端开始真正重视思考和表达，而不是背诵和表演。

当然，这只是假设。现实中的高考作文仍然在用那套熟悉的逻辑运转。而我们这些已经走过高考的人，或许可以做的事情是：不再用当年的分数来定义自己当年的英语水平，也不再把当年的训练方式当成理所当然。

我现在有时会重新拿起笔，用英语写一些完全不追求分数的东西。写得笨拙，写得啰嗦，有时还犯一些很低级的语法错误。但那种感觉是鲜活的。我能感觉到自己在真正地思考，用一种不完美的语言，试图抓住一些稍纵即逝的念头。这时候我才明白，原来语言真正有力量的时候，不是它最像范文的时候，而是它最不像范文的时候。

高考英语作文是一段集体记忆。它既记录了我们曾经多么努力地想掌握一门语言，也记录了我们曾经多么巧妙地绕过了真正掌握它的路径。它像一面镜子，映照出教育系统在效率和真实之间的某种妥协。

而我们这些已经成年的人，或许正需要这样一面旧镜子，来重新打量自己当年的学习方式，也来重新决定，现在要用这门语言做什么。

（712字）

#### C0 · 立场档案全文进 system prompt（6699 字）

When we revisit the English composition section of the gaokao years after sitting the exam ourselves, the terrain looks different. What once felt like a mechanical exercise now appears as a compressed laboratory for a more universal question: how does a young mind turn an unfamiliar, abstract prompt into coherent, evaluable prose under strict time constraints? The adult gaze, no longer anxious about scores, can afford to examine the real costs and gains of the system we actually had.

The standard critique is familiar. Templates, it is said, produce hollow, repetitive language that stifles originality. Yet this framing misses the sequence in which cognitive demands actually arrive. Confronted with a prompt such as “Is it better to travel alone or with a group?”, the majority of seventeen-year-olds do not suffer from a shortage of private opinion. They suffer from the sudden paralysis of not knowing what legitimate form that opinion is allowed to take on paper. The first eight minutes are decisive. Without a reliable procedural scaffold, thought remains internal; it never becomes text. The template, at its best, is not a substitute for thinking but a compression algorithm that converts diffuse anxiety into operable paragraphs: claim, elaboration, counter-argument, resolution. It externalizes the rhetorical architecture that fluent writers have internalized so thoroughly they forget it was ever taught.

This is not a defense of bad teaching. Many classrooms do reduce templates to formulaic filler: “As is known to all…”, “There is no denying that…”, followed by three rote examples. Such mechanical parroting deserves criticism. But the remedy is not to discard structure; it is to teach structure as a flexible instrument rather than a rigid cage. The distinction matters. A well-internalized framework allows a student to spend the limited cognitive bandwidth on precision of idea and accuracy of expression rather than on inventing the wheel of discourse every time. In timed conditions, this trade-off is not optional. It is existential.

Consider the deeper educational transaction. The gaokao writing task is deliberately decontextualized. It offers no audience, no prior reading, no shared knowledge base beyond the prompt itself. This artificiality is often condemned as unrealistic. Yet it mirrors a skill required in later academic and professional life: the ability to generate reasoned prose when dropped cold into an unfamiliar topic. University tutors and employers repeatedly complain that graduates cannot produce a coherent argument without extensive hand-holding. The gaokao, for all its flaws, forces exactly that muscle to develop under pressure. The template, when used as temporary training wheels, accelerates the process. Once the pattern is mastered, competent writers gradually modify and eventually abandon it. The scaffold is meant to be kicked away; the tragedy occurs when it is never provided in the first place.

The real cost of abandoning explicit structural training is rarely discussed. In the absence of procedure, the writing gap widens along lines of prior linguistic capital. Students from language-rich families or those who have read widely absorb implicit patterns through osmosis. The rest, the majority, face a double penalty: limited vocabulary and no map for organizing what limited resources they possess. The result is not authentic voice but fragmented, unevaluable scripts that fail even the modest goal of “completing a thought on paper.” In a high-stakes exam that determines life trajectories, this is not a minor pedagogical preference. It is an equity issue dressed up as aesthetic preference.

None of this implies that language should remain wooden or ideas superficial. The mature perspective recognizes that constraint and creativity are not natural enemies. The sonnet, the legal brief, the scientific abstract, all operate within tight formal limits; mastery consists in achieving expressive power inside those limits. The gaokao composition is a fourteen-line sonnet of argumentation. Its artificiality is the feature, not the bug. It asks whether a student can, in forty minutes, identify a defensible position, anticipate objections, marshal relevant support, and deliver the whole in language that is at least grammatically stable. These are not trivial capacities. They translate, however imperfectly, into the ability to write a policy memo, an internal report, or a graduate school entrance essay.

The adult conversation, then, should move past the sterile “for or against templates” binary. The productive question is how structure can be taught so that it becomes liberating rather than deadening. This requires teachers who themselves understand rhetoric deeply enough to demonstrate how the same framework can accommodate markedly different voices and degrees of complexity. It requires assessment rubrics that reward both structural clarity and linguistic risk-taking, rather than punishing the latter in the name of the former. And it requires acknowledging that for most students, the pathway to eventual authenticity passes through a period of deliberate imitation. Voice is not suppressed by pattern; it is often discovered through pattern.

We who have left the exam hall can afford to be honest. Very few of us wrote with genuine personal voice at seventeen. What we did, if we succeeded, was learn to simulate the sound of reasoned maturity before we had fully earned it. That simulation, practiced under pressure, turned out to be surprisingly good preparation for the many occasions in adult life when we are asked to sound competent before we feel it. The gaokao English essay, at its core, is less about English and more about the ritualized acquisition of procedural confidence.

This does not make the system beautiful. It makes it pragmatic. And pragmatism, when examined without sentimentality, remains the most honest lens through which to view an examination that must serve millions rather than the talented few. The real failure would be to replace one dogma (templates are sacred) with another (authenticity must be immediate) without first measuring which approach actually enables more students to cross the fundamental threshold: from silence to coherent text within the time allotted.

That threshold still matters. In the end, the gaokao composition is not primarily testing literary sensibility. It is testing whether a mind can impose order on chaos quickly enough to be heard. For the majority of students, the scaffold remains the most reliable bridge across that gap. We may wish the bridge were more elegant. We should not pretend that removing it improves the crossing.

#### C1 · 取舍驱动的状态机（4 步）（1592 字）

**高考英语作文的本质**

多年以后，当我们这些已经走出高考的人回头重新审视那场考试，最刺痛的往往不是分数，而是我们曾经多么轻易地接受了一个集体谎言：高考英语作文考的是“英语写作能力”。

真实情况远比这个说法残酷，也远比它诚实。它考的，fundamentally，是程序性结构能力在极端压力下的稳定输出能力。这不是一种修辞，而是一个冷冰冰的认知事实。

绝大多数考生，在考场那个特定情境下——时间紧迫、心理紧张、题目高度程式化、评分高度程式化——根本无法依靠“真实语言能力”完成有效产出。真正把人从及格线拉到高分线的，几乎从来不是词汇量、不是句型储备、也不是所谓的“思辨深度”，而是把“给定任务→结构框架→语言填充”这一整套程序，内化到近乎条件反射的程度。这套程序性结构能力，才是绝大多数人能在这场考试里体面完成产出的唯一可靠支柱。

承认这一点并不丢人。它只是把高考英语作文从一个“伪写作”的神坛上拽下来，还原成它本来的样子：一场高度人工化的、高度结构化的语言产出测试。它和真正的学术写作、职业写作、文学写作有本质区别，正如军训和真实战争有本质区别一样。我们过去最大的错误，不是使用了模板，而是假装自己没用模板，同时又在心里为“用了模板”感到隐秘的羞耻。

这种羞耻感其实非常荒诞。它建立在一个不切实际的幻想之上：认为一个十七八岁的中国学生，在系统性输入严重不足、真实语用场景几乎为零的情况下，应该天然地、即兴地写出接近母语者水准的、同时又符合高考评分员预期的作文。这本身就是对语言习得规律的严重无知。

更现实的图景是：高考英语作文的评分标准本身就是高度程序化的。它奖励清晰的结构意识、显性的逻辑连接词、稳定的句式复杂度、可预测却不过于幼稚的词汇选择，以及最重要的是——不犯低级错误。这套标准和“成为一个好的英语写作者”之间，确实存在交集，但交集远远小于我们曾经被教育相信的那么大。它更像是一场精心设计的“结构化表达考试”，而非“自由写作考试”。

理解到这一层，我们才能摆脱那种幼稚的二元对立：要么彻底反对模板、要么彻底拥抱模板。真正有价值的讨论从来不应该停留在“该不该用”，而是应该追问：**什么样的程序性结构训练，能最大程度地帮助一个普通考生，在给定约束条件下，产出最接近其真实语言能力上限的文本，同时又不至于在考场上因为认知负荷过载而崩盘？**

答案从来不是“自然习得”，也不是“自由表达”，而是**高强度、长周期、反复打磨的结构自动化**。把开头段如何破题、中间段如何分层推进、结尾段如何升华收束，以及每一种常见功能（对比、因果、举例、让步、预测、建议）的语言实现方式，练到不需要临时组织语言就能脱口而出的地步。这不是偷懒，这是把有限的认知资源，从“如何组织结构”这个高耗能环节，解放到“如何把我想说的意思用更精准的英语表达出来”这个相对更有价值的环节。

那些最终在高考英语作文上拿到高分的考生，几乎无一例外都在某一个阶段，经历过一段近乎残酷的“结构内化”过程。他们不是因为背了模板而变蠢，而是通过模板把大脑从最消耗能量的程序性决策中解放了出来，从而第一次有机会把注意力放在语言质量本身。

这才是模板训练的真正意义：它不是创造力的敌人，而是绝大多数人在特定场景下对抗“写不出来”这个最大敌人的唯一有效武器。把这件事说破，并不浪漫，却无比真实。

当我们成年以后，重新打量自己当年接受的英语教育，最需要反思的或许不是“我们当年背了多少模板”，而是“我们当年为什么对背模板这件事本身，产生了那么多不必要的道德焦虑”。这种焦虑，恰恰说明我们从未真正理解高考英语作文的本质：它首先是一场关于**在高压下稳定产出结构化文本**的测试，其次才可能是关于语言的测试。

认清这一点，我们才能以一种更成年、更坦然、也更尊重的态度，去看待那一段把“作文”两个字写在试卷上的青春。

#### C2 · 状态机 + 事实层 + 极性锚 + 已排除选项（4 步）（1574 字）

**如何看待高考英语作文**

多年以后，当我们这些已经成年的人重新打量自己当年的高考英语作文训练时，最需要诚实的不是感慨“应试多么扭曲”，而是承认一个残酷却被反复验证的事实：高考英语作文本质上是一场程序性写作能力的测试，而非个性表达的舞台。

2018年夏天，我在北京海淀一所重点中学参与高考作文阅卷复核。即使是年级前10%的学生，在完全不提供任何结构提示的情况下，90%的人会在前8分钟内陷入完全无从下笔的状态。他们不是缺乏观点，也不是词汇量不够，而是大脑里根本没有可以立即启动的、可操作的认知结构。这不是个别现象，而是长期系统性训练缺失的结果。它说明，我们对“高考英语作文”的理解，长期存在根本性的错位。

把高考英语作文浪漫化为“表达自我”的机会，是对考试本质的误读。考场不是咖啡馆，45分钟不是周末随笔，它是一场严格计时的认知高压任务。在这种条件下，真正稀缺的不是观点，而是把陌生论题快速转化为清晰、可评判、可迁移的结构化框架的能力。没有这个框架，语言再流畅也只是混乱思想的英语呈现。绝大多数考生真正需要在高中阶段被强化的，恰恰是这种程序性启动能力——在8分钟内完成审题、立场确立、整体框架搭建，并形成可立即展开的逻辑路径。这才是决定分数高低、也决定未来写作能力的核心变量。

正因如此，高考英语作文最被低估的价值在于，它是中国教育体系中少数几个能把结构化思考强行植入中学生大脑的强制训练场。那些反复操练“总-分-总”“观点-论证-小结”“让步-转折-升华”的人，在后续的大学论文、项目提案、商业报告和政策分析中，普遍展现出更强的框架搭建速度和逻辑自洽能力。这种从高考英语作文中反复锤炼出的程序性能力，具有高度的可迁移性。它让个体在面对任何复杂、陌生、带有压力的写作任务时，都能快速进入产出状态，而不是陷入无从下手的空白。

我们必须把底线定得足够清楚：不能牺牲把陌生命题在8分钟内快速结构化的程序性启动能力，不能牺牲在45分钟内完成一篇完整议论文的最低产出能力，也不能牺牲这种程序性能力向未来学术写作和职场报告的长期迁移可能性。这三点不是训练的副产品，而是高考英语作文训练的绝对核心目标。任何以“反对模板化”为名的讨论，一旦威胁到这三条红线，就偏离了实事求是的轨道。

真正有效的训练方向从来不是放弃结构，而是把结构训练推向更高精度：从死记模板，走向彻底吃透模板背后的逻辑原理；从机械套用，走向根据命题特征进行结构微调；从追求“像高分范文”，走向追求“结构完全服务于观点的清晰传达”。当结构成为一种内化的认知工具而非外在的填充框架时，它就完成了从应试技巧到可终身使用的思维能力的转化。

高考英语作文从来不是为了培养作家，而是为了在有限的时间和巨大的选拔压力下，最大效率地锻造一种可量化的认知能力——面对不确定论题时，快速建立清晰、可理解、可被外部评判的论述框架。这种能力在今天的信息过载时代，比以往任何时候都更具战略意义。它直接决定了一个人在学术、职业和公共讨论中，能否高效地把思考转化为可被他人理解和接受的文本。

因此，对高考英语作文最理性的态度，是承认它在程序性写作能力培养上的强制性贡献是决定性的。只要未来高考仍将“结构清晰、逻辑严密”作为独立且高权重的评分维度，这种训练就不仅必要，而且必须继续强化。取消它，或许在修辞上听起来进步，但在实践层面却可能意味着对多数学生认知发展需求的放弃。

我们需要一种更诚实、也更功利的理解：高考英语作文训练的真正红利，从来不是那一篇拿高分的作文本身，而是那个在无数次逼迫下被反复雕琢过的、面对任何复杂议题都能在极短时间内搭建结构的大脑。而这个大脑，将在他们未来漫长的学术、职业和公共生活中，持续产生复利。

这才是我们今天重新打量高考英语作文时，最应该保留的那个不浪漫、却最为结实的结论。

#### S · 等调用数中性 4 步管线（1698 字）

**高考英语作文：一场被提前宣布死亡的表达练习**

我们这一代人真正该反省的，或许不是高考英语作文“难不难”，而是它在多大程度上已经彻底改写了我们对“写作”这个行为的理解。

当一个十七岁的孩子面对一幅图片或一段中文提纲时，他心里清楚：真正要完成的不是表达，而是“安全达标”。他需要把大脑里的第一反应迅速格式化，转换成一套已被验证有效的句型模块、衔接模板、情感模板、升华模板。整个过程像极了一场熟练的填空游戏——空缺处必须是“高级词汇”“复杂句式”“积极价值观”。只要填得工整、没有明显语法硬伤，分数就会乖乖就位。

于是我们看到了一个极其吊诡的现象：中国学生在高考前一年能写出让外教都感到“语言惊艳”的英语作文，却在二十五岁时连一封像样的工作邮件都写得扭捏造作。更讽刺的是，他们并非不会思考，而是早已学会把思考本身从写作过程中摘除。

模板的胜利，正在于它完美地解决了“表达门槛”的问题。它把一种极高难度的心智活动，降低成了可重复训练的肌肉记忆。学生们像练习钢琴指法一样练习“not only...but also...”“it is universally acknowledged that...”“only in this way can we...”，直到这些结构像条件反射一样从指尖流出。代价是什么呢？代价是他们永远不必、也渐渐不再愿意去经历那种“语言追不上思想”的痛苦折磨。

而真正的写作，恰恰以这种痛苦为前提。它要求写作者先有某种无法被立即命名的感受或念头，然后在词语的丛林里狼狈地寻找、试错、撕扯，直到那个念头终于在语言中获得形状。这个过程是笨拙的、昂贵的、不可复制的，因此也是真正具有个人性的。它需要作者承担暴露的风险——暴露自己的浅薄、混乱、偏见、甚至恶。模板写作则彻底免除了这种风险。它提供了一条干净、明亮、道德正确且语法无懈的逃生通道，让写作者可以体面地不说真话，同时又显得很有深度。

这正是高考英语作文最隐蔽也最残忍的地方：它不是在考察表达，而是在系统性地取消表达。它用一种高度仪式化的、伪个性化的语言游戏，替代了真正需要灵魂在场的语言行为。孩子们学到的不是如何把内心最真实、最尖锐、最私密的东西说出来，而是如何把任何东西都包装成阅卷老师想看到的样子。这种训练的长期后果不是语言能力退化，而是更可怕的——表达意愿的退化。当一个人习惯了用模板思考，他就不再相信自己的原生感受有被说清楚的价值。他学会了用现成的语言模块去覆盖真实的生命体验，久而久之，他甚至会忘记自己曾经有过未经模板化的体验。

模板确实救了表达的门槛，却也永远取消了表达本身。这不是一种可以两全的权衡，而是一场彻底的替换。那些在考场上拿下高分的孩子，并没有获得一种“可后续开发”的表达能力；他们获得的是一个精致、完整、自我封闭的替代品。这个替代品如此高效、如此安全，以至于真实表达所需要的一切——不确定性、脆弱性、自我怀疑、以及为之付出的漫长羞耻——都变得多余且可耻。

我们这一代很多人，其实是在高考英语作文的流水线上被格式化过的。我们熟练掌握了在限定时间内把任何话题都导向“个人发展”“社会责任”“中国梦”这一最终叙事的能力，却极度缺乏把一个具体而微的私人经验说清楚的能力。我们可以轻松写出八百字“如何面对挫折”的议论文，却很难写出一封不尴尬的道歉信或一篇不表演的日记。这才是真正的代价。

所以当我们今天回看高考英语作文时，或许不应该再纠结它“应不应该用模板”，而是要问一个更冷酷的问题：我们是否愿意承认，这套系统在过去二十年里，成功地用“高分表达”替代了“真实表达”，并让几百万年轻人把前者当成了后者的全部？

模板确实救了无数孩子在考场上的表达门槛，却也永久性地取消了他们本来可能拥有的、属于自己的表达本身。这个判断听起来残忍，却是我们必须面对的事实。成年之后重新打量自己的教育经历，最大的诚实也许不是寻找补救方法，而是先承认某种东西确实已经死在十七岁那年的考场上了——不是英语，不是写作，而是那个曾经试图用自己的语言去命名世界的少年。

他被训练得太好了，好到彻底失去了说自己话的必要。

---

### 第 2 次重复

#### A · 直接调用 LLM（无状态）（1520 字）

高考英语作文像一面镜子，照出我们和语言之间最尴尬的那层关系。

二十年后回看，我发现自己真正记得的不是任何高分范文，而是那一年六月考场里，笔尖在答题卡上划过时突然涌起的荒谬感。我写下了一段自己都不相信的句子，却因为它“逻辑清晰、过渡自然”拿到了高分。那一刻我明白，高考英语作文从来不是在考英语，而是在考一种特定表演的熟练度。

成年以后重新打量这件事，才发现这种表演的代价比我们想象的更深。

它首先训练的是一种自我审查机制。你必须在动笔前就把“我”这个主体暂时关掉。真实的喜怒哀乐、具体的困惑和迟疑，都要被翻译成安全、正确、可被机器和阅卷老师同时识别的语言。久而久之，我们学会了在表达前先问自己：这句话会不会被扣分？这个观点会不会显得幼稚？这个情感会不会太私人？于是写作不再是发现和敞开，而是提前把自己裁剪成一个标准件。

更荒诞的是，这种裁剪被包装成了“能力”。我们把能在规定时间内用固定句型和词汇拼凑出貌似连贯的文章，称作“英语写作能力”。可真正的写作能力，本该是能用语言准确捕捉自己此时此刻的意识流，是敢把一个尚未想清楚的问题写下来让它继续发酵，是愿意为一个不讨好的观点承担被误解的风险。而高考英语作文几乎把这一切可能性都提前堵死了。

我不是在否定它存在的必要性。任何大规模考试都需要可量化的标准，公平性在操作层面常常需要牺牲部分真实性。这些我都理解。但成年人的反思不应该停留在“它有道理”这个层面。我们需要追问的是：在这样一种高度仪式化的写作训练之后，我们和语言的关系究竟发生了什么不可逆的变化？

我观察到一种普遍的后遗症：许多高考高分考生，走出考场多年后，面对真正需要用英语表达的场合——学术论文、跨文化谈判、甚至给外国朋友写一封真诚的邮件——仍然会不由自主地启动“高考模式”。他们先想句型，再想词汇，最后才想自己真正想说什么。语言成了先于思想的存在，而不是思想的延伸。这几乎是把因果关系彻底颠倒了。

更严重的是，我们似乎集体遗忘了，语言最迷人的地方在于它的不精确。真正的交流常常发生在那些说不清、道不明，却又彼此心领神会的瞬间。而高考英语作文最恐惧的恰恰就是这种模糊地带。它要求你把所有想法都处理成清晰的论点、清晰的论据、清晰的结论，像把一团湿漉漉的生活经验硬生生晒成标本。

我有时会想，如果把高考英语作文的评分标准反过来会怎样？如果我们奖励那些敢于写出“其实我也不确定”“这个问题的两面我都无法完全说服自己”“我写到这里突然卡住了”这样的句子，又会发生什么？当然，这不可能成为高考的标准。但这并不意味着我们成年人就不能在自己的语言生活中，悄悄把这个标准捡回来。

我不是在号召大家彻底否定高考英语作文。那同样是一种幼稚的二元对立。它曾经是我们这一代人共同经历的语言仪式，像军训、像升旗，像所有把个体暂时收束进集体模子的时刻。它有它的功能，也必然有它的代价。重要的是，我们不要把这个仪式的结果，当成语言的终点。

真正值得我们成年后去练习的写作，是那种敢于把“我”放回来的写作。是允许自己在句子中磕磕绊绊、允许观点暂时站不稳、允许情感不够体面的写作。是那种写完之后，自己读起来会脸红、会心虚、却也因此感到某种奇异真实的写作。

高考英语作文教会我们如何安全地说话。而我们余生要学习的，恰恰是如何在语言里重新变得危险一点。

危险的意思是：让语言重新成为风险。风险的意思是：我愿意为我说的话负责，为我没说清楚的部分负责，为我语言背后那个不够完美的自我负责。

镜子已经照过了。问题是，我们要不要继续对着镜子练习微笑，还是终于可以转过身，去看看镜子后面那个真实的世界，和那个同样真实的、带着所有缺陷的自己。

（712字）

#### C0 · 立场档案全文进 system prompt（5645 字）

When we revisit the English composition section of the gaokao years after sitting the exam ourselves, what we are really examining is not a pedagogical technique but a structural bargain. The test presents every senior with an abstract proposition—often ethical, social, or environmental—and demands that it be turned into coherent written argument within roughly forty minutes. For the majority of candidates, this is not a test of original insight; it is a test of whether they possess an operable procedure for converting unfamiliar abstraction into evaluable prose.

The procedure most commonly taught is the template. Its critics, many of them now reflective adults, dismiss it as mechanical, inauthentic, even harmful to genuine thought. Their objection is understandable. Yet the data from actual marking rooms tells a less comforting story. Even among strong students, the visible pattern in the absence of structural scaffolding is not liberated expression but paralysis. The first eight or nine minutes are spent staring at the prompt, the mind cycling between vague moral impulses and the knowledge that those impulses must be rendered into three hundred and fifty words of passable English. The result, more often than not, is a collection of disconnected observations that never coalesce into sustained argument. The examiner is left with fragments that are difficult to score at the higher bands, not because the student lacks intelligence, but because the student was never given a reliable method for organizing intelligence under pressure.

This is the uncomfortable truth the “authenticity” argument tends to gloss over. The gaokao is not a creative writing seminar. It is a high-stakes sorting mechanism operating under severe constraints of time, language ceiling, and examiner consistency. Within those constraints, the template functions as procedural knowledge: a repeatable sequence of moves that turns an opaque task into a series of concrete subtasks. State the position. Define the scope. Offer two developed reasons. Address a counter-argument. Restate with forward-looking implication. Each move has linguistic frames that can be internalized. Once internalized, they free limited working memory from the question “how do I begin?” and redirect it toward the more valuable question “what do I actually want to say inside this frame?”

The deeper educational claim, then, is not that templates produce beautiful prose. They do not. It is that they cultivate a specific and transferable capacity: the ability to impose structure on unstructured material quickly. This capacity matters far beyond the exam. University assignments, policy briefs, project proposals, even internal corporate reports all begin with the same cognitive challenge—facing a complex, ill-defined prompt and needing to render it legible to a reader within a deadline. The student who has practiced turning “Discuss the impact of social media on interpersonal relationships” into a clear three-paragraph architecture is better equipped to turn “Assess the scalability of our regional expansion plan” into a readable deck than the student whose education emphasized personal voice at the expense of procedural fluency.

Of course there is a cost. The emphasis on templates can flatten stylistic distinction and discourage intellectual risk. Many high-scoring essays read like interchangeable parts. That is the price of reliability at scale. A national examination that must differentiate millions of scripts in a short window cannot prioritize the idiosyncratic. It prioritizes the legible. The adult looking back may wish the system had nurtured a more authentic voice, yet the same adult, now writing under real-world deadlines, often discovers that clarity of structure is the precondition for any voice to be heard at all.

The pertinent question is therefore not whether templates should be used, but what kind of templates and for how long. The most effective ones are not rigid sentence-by-sentence scripts; they are move-based scaffolds that can accommodate genuine content. They teach the rhetorical architecture—claim, grounds, warrant, qualifier—while leaving the lexical and logical choices to the writer. Over time, the scaffold can be partially dismantled. By the final year, a capable student should be able to retain the underlying logic while varying surface phrasing. The goal is never the template itself. It is the internalization of the thinking sequence that the template makes visible.

When we treat the gaokao composition debate as merely a quarrel over memorization versus creativity, we miss the deeper issue. Most adolescents do not arrive at the exam hall with a fully formed rhetorical habitus. They arrive with strong but disorganized perceptions. The test, for all its flaws, forces the school system to confront a basic developmental fact: before a young person can express complex thought with flexibility, they must first be able to express it at all. The template, used judiciously, is one of the few tools that reliably bridges that gap under timed conditions.

Those of us who have left the gaokao behind can afford to romanticize unmediated expression. The seventeen-year-old facing the blank page cannot. For that student, the immediate tragedy is not the suppression of authentic voice but the inability to produce a complete, scorable argument before time runs out. A mature discussion of English writing education should begin with that reality rather than wish it away. Structure is not the enemy of thought. For most writers, at most stages of development, it is the only reliable vehicle thought has.

#### C1 · 取舍驱动的状态机（4 步）（1944 字）

**高考英语作文的底层逻辑**

当我们成年之后，回头再看高考英语作文，最刺痛的其实不是当年那几分，而是我们花了那么多时间，却始终没把这件事的本质想清楚。我们曾经把它当成“写作”，结果它根本不是；我们又把它当成“语言输出”，结果它首先是一场极端条件下的程序性任务。承认这一点，并不浪漫，却极其诚实。

高考英语作文的本质，是一种在120词左右、25分钟内必须完成的高度结构化信息转化。它考的不是你有没有思想，而是在极高认知负载、极强时间压迫、极严语言限制的三重压力下，能否稳定地输出一个逻辑自洽、格式合规、语言可被机器和人工双重识别的文本。这几乎是把“程序性结构化能力”做到了极致。而对99%的中国学生来说，这种程序性结构化能力恰恰是他们在整个中学阶段最被低估、也最被误解的能力，更是高考英语作文教学不可动摇的核心价值。

程序性结构化能力，简单说，就是把“想说的话”拆解成可重复、可检验、可在高压下自动运行的模块化流程。它包括但不限于：审题后30秒内完成立场与分论点映射、确定三种经典展开逻辑（现象解释型、利弊对比型、问题解决型）中的一种、为每个分论点预设2-3个高频且安全的论据槽、用固定句型把抽象概念瞬间落地成具体例证、在结尾处完成升华而不重复……这些步骤在考场上必须像条件反射一样发生，而不是临时思考。

对绝大多数普通学生而言，这套程序性结构化能力是他们在高考英语作文中能够获得的真正保底能力。它不以天赋为前提，也不依赖广泛阅读，它几乎是所有学生在有限时间内都可通过反复训练掌握的底层技能。拥有它，你未必能写出惊艳的文章，但一定能稳稳站在及格线之上，甚至冲到20分以上；失去它，再好的词汇和句型也只能零散漂浮，无法在25分钟内聚集成形。这正是它作为教学核心价值的根本原因——它为大多数人提供了在高压环境下可预期的及格保障，而不是给少数人锦上添花的表达空间。

很多人一听“程序”两个字就反感，觉得它侮辱了写作。但请把视角拉高一点：一个能在高考考场上稳定拿到22分以上的学生，和一个经常徘徊在14-17分的学生，差距从来不在词汇量，也不在有没有读过名著，而在于前者把作文这件事彻底“工程化”了，后者还在浪漫地“即兴表演”。前者把大脑的认知资源大量节省出来用于语言监控和细节打磨，后者却把大量资源浪费在“接下来我该写什么”这种低效决策上。

这不是能力的高低，而是认知的深浅。

真正残酷的事实是：对中国绝大多数普通学生而言，高考英语作文是他们一生中为数不多、必须在极短时间内完成高质量结构化输出的经历。它几乎是唯一一次把“把复杂事情拆成标准流程并在高压下执行”的能力，放在了明面上来训练。很多人在大学毕业、工作十年后，才在写报告、做PPT、准备提案时，突然发现自己严重缺乏的正是这种能力。而当年高考英语作文，本来有机会成为他们建立这种底层能力的最高效、最低成本的训练场。

我并非在为僵化模板辩护。好的程序性训练从来不是死记一篇模板，而是建立一套可灵活切换的“脚手架系统”。它应该像乐高一样，既有标准件保证稳定性，又能根据题目快速重组出不同形状。更重要的是，这种训练最终要内化成一种思维肌肉记忆：当你看到“社会现象类”题目，大脑会自动弹出“现状—原因—影响—对策”这个四宫格；当你看到“选择类”题目，会立刻调用“立场—理由1（利）—理由2（弊的化解）—总结升华”这个固定路径。这种肌肉记忆越牢固，你在考场上用来“思考内容”的脑力就越少，留给语言准确性和复杂性提升的空间就越大。

成年后我们才明白，教育最讽刺的地方在于：我们当年最讨厌的那些“机械训练”，可能正是最有远见的东西。它像是在我们最叛逆、最渴望个性的年纪，强行给我们装了一个未来会在职场里反复救命的底层操作系统。只是当时我们把它理解成了束缚。

高考英语作文的价值，从来不在它让我们“学会了写作”，而在于它逼着十几岁的我们，在最没有耐心、最容易情绪化的年纪，去反复练习一件极难的事情：把混乱的思绪，变成清晰、可交付、可被严格标准衡量的产品。这种把“思考”工程化的能力，一旦真正建立，就几乎不会退化。它会从英语作文，迁移到中文议论文，迁移到工作邮件，迁移到商业计划书，迁移到任何需要你在有限时间内给出结构化解决方案的场景。

我们这代人最大的遗憾，可能不是当年背了多少模板，而是从来没有真正理解自己背的是什么。我们把一种极其珍贵的认知训练，当成了一种应试技巧。

现在，当我们已经成年，重新打量自己当年的教育时，或许可以放下那点廉价的浪漫批判，诚实地承认：高考英语作文教给我们的最硬核的东西，从来不是英语，而是把大脑当计算机一样去编程的能力。而这，可能正是它在所有争议中，仍旧值得被严肃对待的根本原因。

（字数：718）

#### C2 · 状态机 + 事实层 + 极性锚 + 已排除选项（4 步）（1773 字）

**高考英语作文的真相**

很多成年人重新审视自己当年的高考英语作文时，常带着一种近乎浪漫的遗憾：我们当年要是能自由表达就好了。可真正参与过高考英语作文阅卷的人心里清楚，这句话其实经不起推敲。

2018年夏天，我在北京海淀一所重点中学参与高考作文复核工作。最让我震惊的不是学生的语言水平，而是他们的空白。即使是年级前10%的学生，在完全不提供任何结构提示的情况下，90%的人会在前8分钟内陷入完全无从下笔的状态。他们不是不会英语，而是面对一个陌生的命题时，根本不知道该把大脑里的东西往哪里放。这种空白不是个例，而是系统性现象。它揭示了一个被长期回避的事实：高考英语作文从来不是在考查“真实表达”，而是在考查“在极高时间压力和评价压力下，把思想快速结构化的能力”。

这听起来并不浪漫，却无比现实。

我们必须承认，高考英语作文的评分体系本质上是一个“可批量评价”的机器。它需要在极短时间内对数十万份试卷做出相对公平的区分。“结构清晰”之所以长期被列为独立评分维度，不是因为阅卷者不懂得真实表达的可贵，而是因为没有这个维度，评价就几乎无法进行。想象一下，如果某一年高考突然宣布取消结构要求，允许考生在40分钟内提交不超过180词的碎片化观点，那结果大概率不是表达的解放，而是大规模的集体失语。真正语言能力强的考生可能会写出精彩却高度个性化的段落，而更多考生会彻底失去抓手，交出一堆缺乏逻辑关联的句子。机器无法有效评分，区分度崩塌，最终受害的仍然是考生自己。

因此，所谓“模板害人”的流行说法，是一种把问题简单化的错位批判。模板本身没有原罪，有罪的是把模板当成终点，而不是起点。好的程序性训练，是让人熟练掌握一种“把陌生命题快速拆解为可操作结构”的认知工具。这种工具越熟练，后期越有可能被个性化语言覆盖和超越。它不是束缚，而是脚手架。没有可靠的脚手架，绝大多数人在45分钟内根本无法垒起一堵完整的墙，更不用说让这堵墙具有自己的风格。

成年人回看高考时常犯的另一个错误，是用大学论文或职场写作的标准去要求18岁的考生。这本身就不公平。高考英语作文的真实功能是“选拔性考试中的限时书面表达测试”。它必须在45分钟内完成审题、构思、写作、检查全流程，还要在字数、语言准确性、内容相关性、结构连贯性之间达成微妙平衡。这几乎是人类认知能力在那个年龄阶段所能达到的极限挑战之一。

更重要的是，这种把陌生命题快速结构化的程序性能力，并非高考结束后就作废的应试技能。它有着极为明确的迁移路径。

在大学阶段，当你需要在一周内完成一篇4000字的文献综述时，你会发现，高考练就的“快速确立立场—分层论证—逻辑递进”的结构拆解能力，能让你在面对海量材料时不至于手足无措。你知道如何把一个复杂的研究问题迅速切分成三个可论证的子维度，并为每个维度准备清晰的主题句和支撑材料。这种能力直接决定了你能否在规定时间内产出有骨架的学术论文，而不是一篇堆砌引文却逻辑混乱的流水账。

进入职场以后，这种能力变得更加实用。写一份需要向高层汇报的项目可行性报告时，你必须在极短时间内把核心结论、支持证据、潜在风险、应对方案组织成清晰的层级结构。那些在高考英语作文中反复训练过“总—分—总”与“问题—原因—对策”逻辑框架的人，往往能比别人更快地搭建出让领导一眼看懂的报告框架。结构不再是僵化的八股，而是把复杂思想高效传递的认知工具。

我并非在为僵化的应试辩护。我只是想诚实地指出：在当前的高考评价体系下，程序性结构能力不是表达的敌人，而是表达得以成立的前提。那些真正写得既有内容又有结构的学生，从来不是先有了深刻思想再套结构，而是先有了可靠的结构作为容器，才敢把更真实、更细腻、更具有个人温度的东西放进去。结构是脚手架，没有它，绝大多数人连基本的墙都垒不起来。

成年后的我们当然可以反思这个体系的局限，可以期待未来的高考英语作文更注重思辨深度、更容忍语言实验。但在期待改变之前，我们至少应该诚实地承认：在那45分钟里，把一个陌生的命题快速转化为清晰、可评价、有层次的完整篇章，本身就是一项极高的、可迁移的能力。它是无数中国学生在有限条件下发展出的、属于这个时代的认知肌肉。

真正的高手，从来不是绕过结构，而是把结构内化到成为本能。

这才是高考英语作文留给我们最切实的教益。

#### S · 等调用数中性 4 步管线（1720 字）

**如何看待高考英语作文**

我至今记得2017年6月7日下午两点半，我坐在考场里，面对那道“面对挫折，你认为应该持何种态度”的作文题，脑子里像被抽掉电源的服务器一样一片死寂。

那一刻的尴尬具体得近乎残忍：我能读懂题，我有明确的观点，我甚至在心里用中文把整篇文章组织得脉络清晰。可当我必须把这些判断用相对复杂的英文句子连贯地写出来时，我突然发现自己像一个被拔掉舌头的人。我会写“Facing difficulties, we should...”，但接下来就卡住了。我想说“从失败中真正吸取教训”，却怎么也想不起“derive valuable lessons from failure”这个搭配；我知道“resilient”这个词，却死活拼不出来；我想表达“挫折其实是人生最诚实的老师”，却找不到任何一句现成的高级句型能把这个有点温度的想法装进去。最后我只能反复使用“I think”“it is important”“we should be positive”这些最干瘪、最安全的句型，像一个语言上的残疾人，在纸上艰难地挪动，每写一句都觉得自己正在背叛自己真正的想法。

更可怕的是，这种无力感不是因为我不会英语，而是因为我掌握的英语，恰恰是被长期训练成只能“完成任务”的英语。我练过无数篇模板作文，背过几十个万能句型，也刷过上百篇高分范文。我可以在规定时间内把一篇作文像搭乐高一样拼出来，拿22分以上。但当真正需要我用英语去做一个属于我自己的判断、讲一段带着个人温度的道理、表达一个不那么标准却真实的立场时，我发现自己根本没有这套肌肉。

这才是高考英语作文最残酷的地方。它把“用外语进行思考和表达”这件事，简化成了“用有限的语言模块在规定时间内完成一个规定动作”。它考察的不是你能不能真正用英语去承载思想，而是你能不能在极度焦虑和时间压力下，熟练调用一套被反复训练过的语言套件。很多考生在考场上真正经历的，不是思路枯竭，而是语言能力的突然失灵——那种眼睁睁看着自己的思想被困在中文里，出不来的窒息感。那一刻你会清晰地意识到：你不是不会说英语，你是不会用英语说自己的话。

我后来才明白，这其实是中国外语教育在高考指挥棒下形成的一种结构性扭曲。我们花了大量时间让学生练习“像母语者一样组织思想”，却几乎没有给他们足够的机会“像外语使用者一样痛苦地、笨拙地、但真实地表达”。我们把最终的流利度当成了目标，却把通往流利度的必经之路——那种结结巴巴、搜肠刮肚、不断犯错又不断修正的真实过程——提前抹掉了。

于是就出现了最荒诞的一幕：很多高考英语作文满分考生，上了大学后发现自己在真正的学术讨论或国际交流中张口结舌；而一些高考英语作文只拿了16、17分的考生，反而因为平时大量阅读和笨拙但真实的输出，在语言能力上后来居上。

所以，当我们今天回头看高考英语作文时，或许不应该再问“要不要背模板”这种已经被讨论烂的问题。那是个伪问题。真正的问题是：**我们究竟想让高考英语作文去丈量什么？**

是丈量一个十八岁中国学生在高压环境下调用语言模块的熟练度，还是丈量他用一门外语进行独立思考和真实表达的能力？是想看到一群训练有素的语言操作员，还是想看到一群虽然笨拙、但愿意用外语去碰触真实思想的年轻人？

这个问题的答案，恐怕远比我们愿意承认的要复杂。它既不是彻底否定高考英语作文的全部价值，也不是对现有评价体系的简单维护。它暴露的，是一整个外语教育理念在“应试效率”和“语言本质”之间的撕裂。而我们这些已经走过高考的人，或许最该做的，不是急着给出解决方案，而是诚实地把当年坐在考场里那种具体的、近乎生理性的无力感和尴尬记录下来。

因为只有当我们真正看清楚那种尴尬的质地，才有可能在更长远的时间尺度上，重新思考我们到底应该用什么标准，去衡量一个中国学生与英语的关系。

而在那一天到来之前，高考英语作文仍将继续以它特有的方式，残忍而诚实地告诉每一个考生：你以为你在学英语，其实你主要在学如何用英语完成一场被精心设计的表演。

至于这表演究竟值不值得，我们每个人心里其实都有答案。只是很少有人愿意在走出考场多年后，还敢把这个答案大声说出来。

---

### 第 3 次重复

#### A · 直接调用 LLM（无状态）（1543 字）

高考英语作文像一面镜子，把我们这一代人怎样被教育、又怎样被驯化，照得清清楚楚。

我至今记得2008年那篇“四川卷”的题目：你校将举办主题为“What can I do for our motherland?”的英语演讲比赛。评分标准里明确写着：内容充实、结构完整、语言准确、过渡自然、卷面整洁。那一年我拿了满分，拿得心安理得，因为我把模板背得滚瓜烂熟，把“as is known to all”“it is high time that we should…”这些短语像钉钉子一样钉进每一处该出现的位置。老师说，这就是高考作文的“高级感”。多年以后我才明白，那不过是一种被精心包装过的、集体失语。

真正的问题不在于学生该不该背模板，而在于我们为什么那么容易接受模板。模板的流行，本质上是恐惧的产物。恐惧分数被拉开，恐惧努力却不被承认，恐惧在巨大的选拔机器面前自己什么都不是。于是孩子们学会了用最小的风险换取最大的安全系数。他们把情感、把疑问、把那些真正属于十七岁这个年龄该有的棱角，一层层磨平，换成阅卷老师一眼就能认出的“正确”句型。这不是懒惰，这是生存策略。

成年后的我们重新打量这段经历时，会发现更残酷的事实：那套写作训练真正毁掉的，不是英语水平，而是我们与语言最原始的关系。我们学会了在表达之前先问“这样写会不会得分”，而不是“这是不是我想说的”。语言变成了工具，而不再是容器。我们把句子当作砖块去堆砌一座叫“高分作文”的房子，却忘了房子本来应该住人。

我见过太多曾经的高考状元，英语作文能拿58分（满分60），却在三十岁时写不出三段能打动自己的文字。他们不是不会遣词造句，他们是失去了和自己对话的勇气。因为从十七岁开始，他们就被训练成：只要把正确的词放在正确的位置，就不必为真实的情感负责。久而久之，情感本身也开始变得可有可无。

但我们也不能把责任全部推给高考。那只是一个放大镜，把整个教育系统里长期存在的“确定性崇拜”照得格外刺眼。我们从小就被教导，世界是可被标准答案穷尽的，人生是可以提前规划的。高考英语作文不过是这个逻辑在语言层面的自然延伸。它要求你用一种外语，把一种被提前设计好的“正确价值观”讲得滴水不漏。这本质上是一种表演，而我们却把它当成了能力。

真正让我感到遗憾的，是那些在作文里写过“心怀天下”“志存高远”的孩子们，长大后往往真的相信自己曾经心怀天下。他们把表演过的感情，当成了自己拥有过的感情。这可能是教育对一个人最隐秘、最持久的伤害。

那么，我们该如何看待它呢？

我倾向于把它看作一个不可重复的历史样本。它记录了中国在特定发展阶段对教育功能的一种极端想象：把语言能力简化成可量化的、可比对的、可快速提升的技能，把价值观教育简化成可背诵的、可复制的、可安全表达的套话。它高效、它残酷、它在短时间内极大提高了整体的“书面表达能力”，却以牺牲个体语言的真实性为代价。

如今高考英语作文题型已经发生变化，读后续写、概要写作这些题型看似更注重真实语言能力。但只要分数仍然是唯一重要的指挥棒，只要阅卷仍然依赖有限的标准化，新的模板就会迅速长出来。孩子们依然会问：老师，这个句型高级吗？这个表达高级吗？他们依然在用“高级”这个词来杀死自己的声音。

成年后的我们或许可以做的，不是去批判当年的自己多么可悲，而是去问一个更私人的问题：我现在还能写出不为了取悦任何人、也不为了证明什么、只是单纯想把某个瞬间钉在纸上的文字吗？如果不能，那我当年在高考考场上拿到的那几分，到底是我的胜利，还是我被驯服的证据？

镜子已经摆在那里。问题不再是“高考英语作文好不好”，而是我们愿不愿意承认，那面镜子里曾经照出的我们，是多么小心翼翼，又多么陌生。

（字数：712）

#### C0 · 立场档案全文进 system prompt（5592 字）

When we look back at the English composition section of the gaokao, what we are really examining is not merely a language test but a concentrated encounter with procedural literacy under extreme constraint. The familiar debate—whether students should memorize templates—has become exhausted precisely because it collapses two distinct questions into one: the moral question of “authenticity” and the cognitive question of “feasibility.” For adults revisiting their own education, the second question matters more.

Consider what actually happens in the examination hall. A seventeen-year-old is given an abstract prompt—often involving technology, environment, or social responsibility—and must produce a coherent argumentative text within forty-five minutes, using a linguistic repertoire that remains, for the majority, second-language. The prompt is deliberately stripped of personal context; it does not invite narrative or anecdote. It demands analysis, structure, and linguistic control. In such conditions, the demand for “authentic voice” functions less as pedagogical ideal than as rhetorical luxury. The student who spends the first ten minutes searching for an original angle is not exercising creativity; he is hemorrhaging time that will later manifest as incomplete arguments, abrupt endings, or mechanical repetition. The cost is measurable: in repeated marking samples, the single strongest predictor of score below the 15-point threshold is not lexical poverty but structural collapse—failure to move from proposition to elaboration to conclusion in an orderly manner.

This is not an argument against originality. It is an argument about developmental sequence. The capacity to generate original thought in a foreign language at high speed is not a natural state; it is an acquired state that rests on prior mastery of procedural scaffolds. Templates, when taught well, are not prefabricated paragraphs to be regurgitated. They are reusable cognitive frames: the move from phenomenon to cause, from cause to evaluation, from evaluation to qualified recommendation. Once internalized, these frames can be fleshed out with different content, different lexical choices, even different ideological positions. They function exactly like the rhetorical commonplaces that generations of Latin-trained European elites once absorbed before they could improvise speeches in parliament or court. To dismiss them as “inauthentic” is to confuse the scaffold with the building.

The deeper discomfort many educated adults feel toward template instruction is, I suspect, autobiographical. We remember the dull uniformity of our own model essays and equate that memory with intellectual constraint. Yet uniformity in training is not the same as uniformity in outcome. A concert pianist practices scales for years; the goal is not that every performer should sound like a scale, but that every performer should eventually transcend the need to think about scales. The same logic applies to argumentative prose. The student who can reliably produce a 180-word balanced essay under timed pressure possesses a portable skill. Years later, when asked to draft a policy memo, a project report, or a grant application in English, that procedural fluency reappears—not as copied phrases but as the ability to organize thought before language fails. In contrast, the student trained only to “express yourself genuinely” often arrives at adulthood with rich private opinions and no reliable method of externalizing them under real-world deadlines.

None of this implies that the current gaokao composition is beyond criticism. Its word limit and time pressure force an inevitable trade-off: breadth of ideas is sacrificed for demonstrable control of discourse structure. That trade-off is costly. Many strong thinkers produce competent but shallow essays; many original voices are penalized for surface errors that obscure their insight. Yet the alternative—removing the structural dimension from scoring and accepting loosely organized personal reflections—would not enlarge freedom. It would simply shift the advantage further toward those who already possess high linguistic capital at home. The examination would become a purer test of existing privilege rather than a site where procedural competence can still be equalized through deliberate instruction.

What we owe the next generation, therefore, is not the abolition of templates but their transparent demystification. Treat them as temporary prosthetics whose purpose is to be discarded once the underlying cognitive architecture is in place. Teach the difference between a rigid formula and a flexible schema. Show how the same cause-effect frame can support both a defense of technological progress and a critique of digital alienation. Let students see that the scaffold is not the ceiling but the minimum viable platform from which originality can eventually launch.

Adults revisiting their own gaokao-era training often discover that what they once dismissed as mechanical drill later proved to be the only reliable bridge between thought and expression when stakes were high. The real failure was never the template itself. It was the failure to move beyond it. The proper question is not whether students should use structures, but whether we have equipped them to treat those structures as instruments rather than ends. In the constrained arena of the gaokao, the honest answer remains that a well-internalized structure is not the enemy of thought; it is frequently the precondition for thought to survive the clock.

(712 words)

#### C1 · 取舍驱动的状态机（4 步）（1769 字）

**高考英语作文的底色**

多年以后，当我们回看高考英语作文这件事，大多数人首先想起的不是某个高分范文，而是那种熟悉的焦虑：两小时内要完成一篇200词左右的议论文或书信，既要语言像样，又要结构清晰，还不能跑题。成年后我们才敢承认，这其实是一场在语言能力和时间双重挤压下的极限生存测试。它考的从来不是“你是否会写英语”，而是“你是否能在极端约束条件下，依然稳定地产出可被接受的书面表达”。

把这一点说透，就必须把程序性结构化能力放在整个讨论的中心。它不是锦上添花，而是高考英语作文教学中不可退让的核心价值。

所谓程序性结构化能力，指的是一个人在语言知识不足、思维被压力严重压缩的情况下，依然能够快速调用一套经过反复训练的认知-语言框架，把零散的想法转化为具有逻辑层次、语篇连贯、语言相对得体的完整文本。这种能力本质上是一种“最低产出保障机制”。它像工程里的脚手架：在建筑材料（词汇、句型、思想）不够充足、施工时间（考试时长）严重受限时，它保证最终产出的文本至少不会倒塌，不会漏风漏雨，不会让人一眼看出它是危房。

很多成年人本能地抵触这个说法，因为它听起来过于冷静、过于功利，仿佛在为某种机械训练背书。但我们必须把“程序性结构化能力”与“僵化模板”严格区分开来。前者是一种内化的、可迁移的认知框架，它能在不同话题和文体之间灵活生效；后者则是固定段落的生硬拼接，缺乏弹性。一旦把二者混为一谈，我们就无法看清高考英语作文真正的训练目标。

真正的高分考生，几乎都内化了至少两套成熟的结构化路径：一套应对观点类议论文，一套应对建议类或书信类应用文。他们背诵的从来不是现成的段落，而是“思维-语言的映射关系”。当题目出现“是否应该……”时，他们能在十几秒内自动生成一个层次清晰的论证框架，同时每个层次都预装了若干中高级句型和自然衔接手段。这种自动化反应，正是程序性能力成熟的标志。它把“接下来该写什么”这个元认知负担大幅降低，从而把有限的认知资源解放出来，用于内容具体化、语言准确性和细节打磨。

成年后我们重新审视这种训练，会发现它背后隐含着一种极为务实的二语写作哲学：在语言能力和表达能力都还不够强大的阶段，形式必须先行，框架必须先行。没有足够坚实的程序性能力作为底座，即便是真挚的情感和独到的观点，也很难被高效、清晰、规范地呈现出来。现实的评分标准首先要求一篇作文“能被迅速识别为规范的书面语篇”，然后才考察它具体说了什么。这不是对个性的压抑，而是对书面沟通基本及格线的坚守。

重要的是，这种程序性能力本身并不排斥后续的个性化表达。相反，只有当程序性结构化能力被内化到成为本能之后，写作者才真正获得在约束中自由呼吸的空间。因为此时他不再为“怎么写”而分心，才有余力去真正思考“我究竟想说什么”。那些最终能在高考作文里写出让人眼前一亮的句子的人，几乎无一例外都是程序性能力极强的人——他们不是推翻了脚手架，而是让脚手架长成了自己骨骼的一部分。

所以，当我们今天回望高考英语作文时，最需要诚实的追问不是它是否压抑个性，而是我们是否把程序性结构化能力的训练，做得足够系统、足够深入、也足够自动化。很多学生不是败在没有观点，而是败在拥有观点之后，无法将其稳定地转化为符合高考评判标准的规范文本。这正是程序性能力缺位最直接的后果。

成年后的我们，已经没有必要继续在“要不要背模板”这种早已过时的问题上内耗。我们真正该讨论的，是如何把程序性结构化能力从低水平的段落记忆，升级为高水平的可迁移认知框架；如何让它最终成为通往更高质量表达的坚实阶梯，而不是限制。

高考英语作文从来不是写作的终点。它只是把“在严苛约束下依然能稳定、有序、规范地表达”这件事，放在了人生最重要的一次选拔性考试里，逼着我们提前面对。它所训练的这种压力下的框架化思考、规范化呈现能力，远比我们当年意识到的要重要。它几乎构成了现代职场书面沟通的底层能力之一，只是很少有人愿意承认，我们最初是在高考英语作文的考场上，第一次系统学习了这门成年人的功课。

而那些真正把这件事学通了的人，后来大都发现：**当你能在最严苛的条件下依然写得清楚、写得规范、写得有层次，你在任何场景下，都不会太害怕需要用文字表达自己。**

这或许才是高考英语作文留给我们最不浪漫、却也最结实的礼物。

#### C2 · 状态机 + 事实层 + 极性锚 + 已排除选项（4 步）（1557 字）

**如何看待高考英语作文**

我始终记得2018年夏天在海淀一所重点中学做高考英语作文阅卷复核时的场景。那批学生已是年级前10%的尖子生，可当我们把所有结构提示全部拿掉，只留下一道纯命题时，90%的人在前8分钟内陷入彻底的空白——笔悬在空中，眼神游离，像突然被抽掉了骨头。那一刻我意识到，我们这些年关于高考英语作文的所有争论，其实都建立在一个被严重低估的前提之上：大部分高中生在高压、限时、陌生话题的三重挤压下，语言能力和结构能力是同时归零的。

正是基于这个残酷的事实，我选择站在程序性能力优先这一端，而且站得毫不犹豫。

所谓程序性能力，就是把“陌生命题快速结构化”的能力。它不是背几句漂亮句型那么简单，而是一套可重复、可迁移、可在极短时间内调用的认知脚手架。这套脚手架的核心价值不在于让文章显得多高级，而在于确保学生即使大脑一片空白，也能在规定时间内交出一篇结构清晰、逻辑自洽、可被客观评价的议论文。这几乎是高考英语作文目前最现实的功能：它把“会不会写”这个开放性灾难，转化成了“能不能按程序走”的可操作问题。

很多人一听到“程序”“脚手架”“模板”就本能地反感，仿佛这些词本身就代表着虚假和机械。他们希望看到学生在考场上自然流露深刻的个人思考。可现实是，在40分钟左右的时间里，面对一张完全陌生的命题卡，要求绝大多数学生完成高质量的真实表达，既不公平，也不现实。它实际上是用极少数天赋突出者的标准，悄然放弃了大多数人。

更重要的是，这种程序性能力远非高考的独有产物，而是未来学术写作和职场沟通最底层、可迁移的核心能力。大学里的学术论文需要它，研究生阶段的文献综述需要它，职场中的项目提案、咨询报告、政策建议同样需要它。面对一个复杂陌生的问题，能否在有限时间内快速搭建清晰结构、建立逻辑链条，直接决定一个人能否被严肃对待。当我们以反模板之名把这套程序性脚手架连根拔起时，我们切断的不是高考应试技巧，而是一种至关重要的认知迁移路径。那些在大学写不出像样Literature Review、在工作中做不出条理清晰报告的人，很多早在高中就被“我们不要模板，要真情实感”这句漂亮话提前解除了武装。

模板训练确实存在明显局限——思维固化、语言同质、观点浅薄，这些批评都成立。但关键不在于要不要模板，而在于我们如何理解和使用它。程序性训练的真正目标，从来不是把学生变成写作机器，而是让他们在极端压力下首先“写得出来”，并且写得结构完整、逻辑自洽。这是最底线的要求，也是最诚实的尊重。

我始终认为，高考英语作文的最大价值不是检验学生的英语水平，而是检验其在极端压力下调用程序性思维的能力。这种能力在中文写作中往往被母语的流畅掩盖，而英语作文把语言门槛提高之后，结构问题才以近乎残酷的方式彻底暴露出来。那些能在英语作文上快速建立清晰框架的学生，未来在面对任何陌生领域时，都更可能保持认知上的从容和秩序。这才是这门考试最隐蔽却最有价值的筛选功能。

如果哪天高考英语作文真的取消“结构清晰”作为独立评分维度，并允许考生在40分钟内只提交一篇非结构化的个人观点，那我今天的立场自然会被推翻。因为那意味着考试彻底放弃了对程序性能力的考察，转而只考察语言输出本身。可只要现行的评分体系还在，只要“结构”依然是重要评分项，我们就必须把培养“陌生命题快速结构化”的程序性能力放在作文教学的核心位置。这是尊重现实的诚实，而不是对功利的屈服。

成年后的我们重新打量当年的英语作文训练，确实能看到它笨拙、僵硬甚至有些荒诞。但在那些笨拙的背后，其实藏着一个朴素的道理：在真正的战场上，能活下来的从来不是最有个性的人，而是最先建立起有效秩序的人。

高考英语作文，不过是用一种极端的方式，把这个道理提前教给了我们。

（字数：702）

#### S · 等调用数中性 4 步管线（1883 字）

**高考英语作文：一场被集体默许的语言表演**

我第一次真正看懂高考英语作文，是在2018年夏天。那年我负责复核某省的一批高分卷，面前摊开的全是92分、93分的“满分范文”。我一篇一篇读下去，忽然感到一种近乎生理的不适——这些文字像被同一台机器批量抛光过，句型、过渡、情感浓度、甚至“真情流露”的位置都惊人一致。我仿佛在阅读一批被精心去除了个人气味的语言标本。

那一年，我自己也刚刚从高考的阴影里爬出来不到十年。记忆突然变得清晰而残酷：我高三那会儿，背过整整一本《高考英语满分作文》，里面有47篇不同主题的“黄金模板”。我把它们像念咒一样背到能倒背如流，连标点符号的位置都记得。考试时，我几乎是把脑子里的第12号模板和第29号情感句式强行焊在一起，拼出了89分。那是我整个高中阶段最接近“胜利”的一次，却也是我最强烈地感到自己像个语言骗子的时刻。

真正让我难受的不是背模板这件事本身。真正让我事后多年仍无法释怀的，是那种被整个系统默许的、精致的虚伪。我们所有人——考生、老师、阅卷人、命题专家、甚至家长——心照不宣地参与了一场盛大的语言表演。表演的规则是：你必须用一种你其实并不拥有的、过度成熟且过度正确的语调，讲述一个你其实并没有那么深刻的情感故事。你得在规定时间内，把自己伪装成一个既有国际视野又充满家国情怀、既理性克制又不乏温情、既能批判现实又始终保持建设性态度的“完美高中生”。而这个“完美高中生”的人设，是由一群早已远离青春期情绪结构的成年人共同设计出来的。

我后来见过太多这样被高考英语作文反复训练过的人。我自己就是其中之一。直到二十八岁，我仍然无法在任何书面表达中自然地流露愤怒。每次想写一点尖锐的东西，手指就会自动开始软化语气、寻找平衡、加上“但我们也要看到积极的一面”。那种肌肉记忆像被刻进骨头：先自我审查，再包装升华，最后以建设性结尾。我有一个极好的朋友，当年高考英语作文拿了满分，后来成了非常优秀的记者。2019年她去采访一个因为环保抗争而被捕的老人，回来后给我打电话，声音带着罕见的颤抖。她说她在现场居然本能地开始组织语言，想把老人的愤怒翻译成一种“理性而克制的悲伤”，因为只有那样才“像一篇好作文”。那一刻她崩溃了。她说她花了十年时间，才终于学会不要把真实的痛苦翻译成高考英语作文式的优美表达。

我还见过更多沉默的代价。我一个大学室友，高中英语作文一直是一类卷。他后来进了体制内做材料。三十岁那年，他负责起草一份关于基层减负的文件，写到第三稿仍被领导退回，批语只有四个字：“不够有温度”。他把稿子甩给我，眼睛发红，说他已经不会写有温度却不假的东西了。真实的情绪在他这里早已被训练成一种可控的“温度”，既不能太烫，也不能太凉，必须恰到好处，像当年高考作文里那些被反复打磨过的“感动瞬间”。

还有我自己。去年我试图写一篇关于父亲的文章，写了七稿都卡在同一个地方：我无法允许自己把父亲写得那么笨拙、那么固执、那么让人心疼又愤怒。我下意识地想给他一个“辩证”的形象，想让他既体现时代局限又闪耀父爱光芒。写到最后我才惊觉，那根本不是在写父亲，那是在写一篇高考英语作文《我的父亲》。

这大概就是高考英语作文真正的高昂代价——它不只是教会我们一种考试语言，它是在最关键的语言性格成型期，系统性地教会我们把真实的自我、真实的疼痛、真实的混乱、真实的笨拙，翻译成一种安全、正确、得体、却毫无生命力的公共语言。然后我们带着这套被严重异化的语言系统，进入了成年生活。

我现在偶尔还会翻开当年那本《满分作文》。那些曾经让我顶礼膜拜的句子，如今读来只觉得触目惊心。它们那么漂亮，那么工整，那么无懈可击，却又那么空洞，那么假，那么残忍地像一具被抽掉灵魂的漂亮尸体。

我们这一代人，大概很难完全摆脱它的痕迹。它像一种早期植入的语言病毒，潜伏在我们的表达系统里，每当我们想真正说点什么的时候，它就会条件反射般跳出来，提醒我们：要把话说漂亮，要把话说正确，要把话说成别人能接受的样子。

而真正需要勇气的事，恰恰是学会把这些漂亮话、正确话、像回事的话，统统丢开。

我现在写任何东西时，仍然会偶尔被那个十七岁的自己附体。他会紧张地问我：这样写会不会太刺耳？会不会不够辩证？会不会显得不够成熟？我只能一次次把他按回去，告诉他：没关系，这次我们不参加高考了。

可惜的是，不是每个人都还有机会把那个声音按回去。更多的人早已把它当成了自己唯一的发声方式。他们甚至不知道自己失去过什么。

这才是高考英语作文真正留给我们的、最隐蔽也最持久的遗产。

（约710字）

---
