# DEEP-18-11 · 逐字摘录（Curiosity Search + POET）

> **本文件由脚本 `build_quotes.py` 生成：每条引文都在 PDF 抽取文本里程序核对过（找不到 ⇒ 脚本 abort，不出文件）。**
> 锚点格式：`PDF p.<页>` = PDF 物理页；`刊印 p.<n>` = 该页页脚印的页码；`L<a>-<b>` = 抽取文本 `_raw/deep18/<src>_text_paged.txt` 的行号。

> ⚠️ **抽取层已知失真**（引文里的字符以 PDF 渲染为准）：
> - `≥` 在 PLoS 抽取文本里是控制字符 `\x03`；`/` 在 `||a − b||1 / k` 处是 `\x02`；
> - POET 的 `2.2e−16` 用的是 U+2212（减号），不是 ASCII `-`；
> - 破折号是 U+2014（`—`），引号是弯引号（`’ “ ”`）；
> - **只规范化空白**，不改写任何词句。


---

## A. Curiosity Search（PMC5010182）

- **出处**：Stanton C, Clune J (2016) *Curiosity Search: Producing Generalists by Encouraging Individuals to Continually Explore and Acquire Skills throughout Their Lifetime.* PLoS ONE 11(9): e0162235. DOI 10.1371/journal.pone.0162235. PMID 27589267. **PMCID PMC5010182**.
- **获取**：PDF: https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0162235&type=printable (下载副本 `_raw/deep18/PMC5010182_stanton_clune_2016_plosone.pdf`)
- **抽取文本**：`/workspace/lab/routes/LIT/_raw/deep18/PMC5010182_text_paged.txt`

### C1 — Abstract
**锚点**：PDF p.1（刊印 p.1）· `PMC5010182_text_paged.txt` L44-L47

```
However, we hypothesized that Novelty Search would produce sub-populations of specialists, in which each individual possesses a subset of skills, but no one organism acquires all or most of the skills.
```

### C2 — Introduction
**锚点**：PDF p.2（刊印 p.2）· `PMC5010182_text_paged.txt` L32-L34

```
Unlike Novelty Search, this novelty is measured not against the population, but against the individual’s own accomplishments.
```

### C3 — § Intra-Life Novelty Score
**锚点**：PDF p.5（刊印 p.5）· `PMC5010182_text_paged.txt` L32-L35

```
The intra-life novelty score determines how many unique behaviors have been expressed within an individual’s lifetime. This score can be implemented in several ways: on simpler problems, such as the maze exploration task used in this paper, one might create a discretization in which there are K possible behaviors and the score is the number of behaviors in K that have been expressed.
```

### C4 — § Fitness Function
**锚点**：PDF p.6（刊印 p.6）· `PMC5010182_text_paged.txt` L18-L21

```
In this paper, fitness in Curiosity Search only considers the number of unique behaviors expressed. An agent that learns how to swim and drive has expressed the same number of behaviors as an agent that instead learns how to climb stairs and pick locks; therefore, both have the same fitness.
```

### C5 — § Controls and Parameters
**锚点**：PDF p.9（刊印 p.9）· `PMC5010182_text_paged.txt` L35-L36

```
Curiosity Search (CS) uses the fitness function f = t + d, where t is the number of unique grid tiles touched during simulation and d is the total number of doors opened.
```

### C6 — § Controls and Parameters
**锚点**：PDF p.9（刊印 p.9）· `PMC5010182_text_paged.txt` L38-L40

```
We also ran a control in which the fitness function was f = t (tiles only) to determine whether agents could acquire door-opening skills without any direct pressure (or reward) for opening them.
```

### C7 — § Controls and Parameters
**锚点**：PDF p.9（刊印 p.9）· `PMC5010182_text_paged.txt` L44-L46

```
Because Curiosity Search optimizes a single objective, it could suffer from deception [19, 20] and might benefit from added diversity, like many other objective-driven EAs [29]. We combine Curiosity Search + Novelty Search using NSGA-II [34], adopting default NSGA-II parameters provided by Sferes.
```

### C8 — § Controls and Parameters
**锚点**：PDF p.10（刊印 p.10）· `PMC5010182_text_paged.txt` L3-L6

```
We investigate two different behavioral distance functions for Novelty Search: (1) the traditional Novelty Search distance function for this domain (NSE), which compares individuals via their endpoints and which we believe will produce specialists, and (2) a behavioral distance from Lehman and Stanley 2011 [19] that instead compares the entire trajectory of each individual (NST).
```

### C9 — § Controls and Parameters
**锚点**：PDF p.10（刊印 p.10）· `PMC5010182_text_paged.txt` L8-L11

```
Following preexisting work [19], distance is computed by the averaged Manhattan distance between each coordinate (i.e. ||a − b||1 / k where k is the length of vectors a and b; this has sometimes been mistakenly referred to as Euclidean distance).
```

### C10 — § Controls and Parameters
**锚点**：PDF p.10（刊印 p.10）· `PMC5010182_text_paged.txt` L12-L13

```
NST, we chose trajectory-based Novelty Search over a tile-based implementation to enable comparisons to the former, which has already been shown to work well on other tasks [19] and for which a tested implementation was already provided in rtNEAT and Sferes.
```

### C11 — § Controls and Parameters
**锚点**：PDF p.10（刊印 p.10）· `PMC5010182_text_paged.txt` L16-L21

```
In an endpoints-version of Novelty Search, specialization occurs because if e.g. the west branch is most novel, there is no incentive for an individual to first head east before fully exploring the west branch—only the final location matters. However, a trajectory-version of Novelty Search does reward an individual for this behavior (provided other individuals are not doing the same), because the resulting variation in trajectory makes that individual more novel.
```

### C12 — § Controls and Parameters
**锚点**：PDF p.10（刊印 p.10）· `PMC5010182_text_paged.txt` L23-L25

```
Curiosity Search rewards individuals for doing everything (or, in our simplified version, for going everywhere); Novelty Search instead rewards individuals for being different from other individuals.
```

### C13 — Fig 4 (caption)
**锚点**：PDF p.11（刊印 p.11）· `PMC5010182_text_paged.txt` L3-L6

```
Fig 4. Novelty Search produces specialists and Curiosity Search produces generalists. (a) Fifty trajectories from a NSE population are overlaid to show the population-level coverage (results typical for all mazes; see S1 Fig). Novelty Search explores the entire domain, but (b) a typical NSE individual only explores a small portion of that domain, whereas (c) a typical CS individual tends to explore significantly more. (d) NST instead produces individuals that explore similarly to, although not usually as much as, Curiosity Search.
```

### C14 — § Results: Novelty Search Specialization
**锚点**：PDF p.11（刊印 p.11）· `PMC5010182_text_paged.txt` L13-L16

```
As expected, switching to a behavioral characterization that is more lifetime-aware increases exploration. On four out of five mazes, the best-exploring individuals of NSE explore less than 50% of the domain, while those of NST explore significantly more (Fig 6, NSE vs. NST, p < 0.0001).
```

### C15 — § Results: Novelty Search Specialization
**锚点**：PDF p.11（刊印 p.11）· `PMC5010182_text_paged.txt` L16-L17

```
The combination of Curiosity Search and Novelty Search in multi-objective optimization increases exploration by 20-50% and causes the difference between endpoints and trajectories to completely disappear
```

### C16 — § Results: Maze Exploration
**锚点**：PDF p.11（刊印 p.11）· `PMC5010182_text_paged.txt` L24-L26

```
Individuals produced by combining Curiosity Search and Novelty Search (CNT) explore almost 90% of the maze, far more (approximately 15-25%, p < 0.0001) than either treatment alone, indicating that Curiosity Search (1) benefits from the inclusion of a diversity-promoting objective and (2) is possibly prone to deception in this problem.
```

### C17 — Fig 7 (caption) ★
**锚点**：PDF p.13（刊印 p.13）· `PMC5010182_text_paged.txt` L8-L12

```
Fig 7. Curiosity Search produces individuals with greater exploratory skills than Novelty Search, but the populations of all treatments explore the entire maze. Results show the Cross Maze only (data from other mazes shown in S2 Fig). (a) Both curiosity treatments significantly outperform TE and NST over evolutionary time. CNT produces individuals that explore more than either algorithm alone, suggesting that Curiosity Search may be a good helper objective for producing generalists. (b) The population of every treatment, even those that produce specialists (such as TE), can explore the entire maze, revealing that population diversity alone is not sufficient to encourage generalists.
```

### C18 — § Do Doors Represent Distinct Skills?
**锚点**：PDF p.12（刊印 p.12）· `PMC5010182_text_paged.txt` L13-L15

```
To ascertain whether this phenomenon occurs, we test CS and NST in each maze with and without doors. If the doors are merely obstacles requiring no skill to open, removing them should have little to no effect on our results: CS should still slightly, but significantly, outperform NST and overall exploration percentages should remain similar.
```

### C19 — § Do Doors Represent Distinct Skills?
**锚点**：PDF p.12（刊印 p.12）· `PMC5010182_text_paged.txt` L15-L19

```
However, we found that both CS and NST agents explore nearly twice as much of their environment when the doors are removed (Fig 8, p < 0.0001 except for the Cross Maze, in which there is no significant change). Furthermore, the exploration gap between Curiosity Search and Novelty Search disappears almost entirely; in aggregate there is no difference (p ≥ 0.05) after the doors are removed.
```

### C20 — Fig 8 (caption)
**锚点**：PDF p.14（刊印 p.14）· `PMC5010182_text_paged.txt` L3-L7

```
Fig 8. Removing doors increases exploration and causes the difference between Curiosity Search and Novelty Search to disappear. Treatments in which doors were removed are subscripted with N (CSN, NSTN); all other treatments contain doors. If the doors were merely obstacles requiring no skill to open, we would expect little or no change in either algorithm’s ability to explore the domain after doors are removed. However, exploration greatly increases when doors are removed and the difference between treatments disappears almost entirely, suggesting that the doors in these experiments are an abstraction of distinct skills, which CS seems better able to acquire.
```

### C21 — § Do Doors Represent Distinct Skills?
**锚点**：PDF p.12（刊印 p.12）· `PMC5010182_text_paged.txt` L24-L26

```
An additional way to test whether the doors in these experiments represent distinct skills is to directly measure an evolved agent’s ability to open each type of door. If the different doors don’t represent different skills, an agent should be able to open all of them with equal ability.
```

### C22 — § Do Doors Represent Distinct Skills?
**锚点**：PDF p.14（刊印 p.14）· `PMC5010182_text_paged.txt` L10-L13

```
We tested this idea by placing agents in an environment in which the only task is to open doors; agents were graded on how many different types of doors they could open (red, green, blue, etc.). We found that Curiosity Search agents open more types of doors than those of Novelty Search, reinforcing our claim that doors are non-trivial skills that Curiosity Search is better able to acquire (see S3 Fig for the experimental details and results).
```

### C23 — S3 Fig (caption)
**锚点**：PDF p.18（刊印 p.18）· `PMC5010182_text_paged.txt` L25-L29

```
The best-exploring agents produced by evolution (Fig 5) are placed in the four mazes shown in (a), each of which is designed to test a single door-opening skill (the different colors/striping patterns for each door correspond to those in Figs 2 & 3). No further evolution is performed. Agents are given 250 time steps in each maze and receive scores based on the number of mazes in which they successfully open the door (up to 4; values are normalized to fall within [0, 1]). Each maze is intentionally small such that agents are always within each door’s opening range (i.e. no navigation is required to open the door).
```

### C24 — S4 Fig (caption) ★ CS_O
**锚点**：PDF p.18（刊印 p.18）· `PMC5010182_text_paged.txt` L40-L41

```
When doors are removed from the fitness function, leaving only the number of tiles visited in the fitness function (CSO and CNTO, f = t, where the ‘O’ subscript denotes tiles
```

### C24b — S4 Fig (caption) ★ CS_O (续页)
**锚点**：PDF p.19（刊印 p.19）· `PMC5010182_text_paged.txt` L3-L4

```
‘only’), Curiosity Search still acquires door-opening skills at the same rate (p ≥ 0.05 for every maze and in aggregate).
```

### C25 — S4 Fig (caption) ★ CS_O
**锚点**：PDF p.19（刊印 p.19）· `PMC5010182_text_paged.txt` L4-L8

```
Although doors are not included in the fitness function for CSO or CNTO, agents are still measured in this plot by the number of tiles explored and doors opened (for easier comparison to regular Curiosity Search agents). These results indicate that Curiosity Search does not need to directly reward the skills an agent should develop; it is enough for the algorithm to reward exploration alone.
```

### C26 — § Transfer Experiments
**锚点**：PDF p.14（刊印 p.14）· `PMC5010182_text_paged.txt` L19-L20

```
We test whether CS produces agents with similar or better exploration skills than Novelty Search by (1) evolving individuals in the Cross Maze, (2) transferring the best-exploring individuals into the other four mazes, and (3) evaluating their ability to explore the new environment, both without and with further evolution.
```

### C27 — § Transfer Experiments
**锚点**：PDF p.14（刊印 p.14）· `PMC5010182_text_paged.txt` L21-L22

```
Transfer Without Further Evolution. Without any further evolution, we found that Curiosity Search matches, but only rarely exceeds, the transfer performance of NST (Fig 9a); in aggregate there is no significant difference between the two (p ≥ 0.05). However, the combination of Curiosity Search and Novelty Search (CNT) explores 10% more than any other treatment (p < 0.01 in aggregate), again making it superior to either algorithm alone.
```

### C28 — § Transfer Experiments
**锚点**：PDF p.16（刊印 p.16）· `PMC5010182_text_paged.txt` L15-L16

```
There was no significant difference (p ≥ 0.05) between NST and CS after further evolution (Fig 9b). Also, the original exploration difference disappears immediately at the onset of evolution, suggesting that the individuals produced by CS and NST are equally evolvable under Curiosity Search.
```

### C29 — § Conclusions
**锚点**：PDF p.17（刊印 p.17）· `PMC5010182_text_paged.txt` L26-L27

```
Because the automatic identification of new and increasingly complex behaviors is not yet technically feasible, we tested a simpler version of Curiosity Search which instead rewards agents for going to many different places.
```

### C30 — § Conclusions
**锚点**：PDF p.17（刊印 p.17）· `PMC5010182_text_paged.txt` L33-L34

```
we provided evidence that any algorithm that rewards intra-life behavioral novelty (e.g. Novelty Search with a trajectory-based behavioral characterization) may facilitate the production of generalists.
```

### C31 — § Problem Domain
**锚点**：PDF p.6（刊印 p.6）· `PMC5010182_text_paged.txt` L43-L44

```
We adopt the classic domain from Novelty Search, in which wheeled robots are evolved in a 2D maze [19].
```

### C31b — § Problem Domain (续页)
**锚点**：PDF p.7（刊印 p.7）· `PMC5010182_text_paged.txt` L8-L9

```
single start position, no explicit goal, and a number of multicolored doors. We chose a variety of environments to ensure the generality of our results.
```

### C32 — § Problem Domain
**锚点**：PDF p.7（刊印 p.7）· `PMC5010182_text_paged.txt` L22-L22

```
Curiosity Search’s mandate “do something new” can be measured in many ways; we translate that directive into “go somewhere new” because the latter is easy to quantify.
```

### C33 — § Neural Network Structure
**锚点**：PDF p.9（刊印 p.9）· `PMC5010182_text_paged.txt` L15-L20

```
We considered adding a punishment for giving the wrong answer (e.g. activating the red door neuron when a yellow door is present). However, all tested forms of punishment severely reduced individual exploration in all treatments. We note that any punishment—whether by “freezing” a robot in place or by lowering its final fitness—may actually discourage exploration because it punishes the natural process of trial-and-error. Thus we do not use any punishment model in our experiments.
```

### C34 — § Controls and Parameters
**锚点**：PDF p.9（刊印 p.9）· `PMC5010182_text_paged.txt` L30-L30

```
All experiments have a population size of 125 and last 2,000 generations; 25 runs were given for each experiment.
```


---

## B. POET（arXiv:1901.01753）

- **出处**：Wang R, Lehman J, Clune J, Stanley KO (2019) *Paired Open-Ended Trailblazer (POET): Endlessly Generating Increasingly Complex and Diverse Learning Environments and Their Solutions.* arXiv:1901.01753v3 [cs.NE], 21 Feb 2019. GECCO 2019.
- **获取**：PDF: https://arxiv.org/pdf/1901.01753v3 (下载副本 `_raw/deep18/1901.01753v3_poet.pdf`)
- **抽取文本**：`/workspace/lab/routes/LIT/_raw/deep18/1901.01753v3_poet_text_paged.txt`

### P1 — §2.2 MCC
**锚点**：PDF p.5（刊印 p.5）· `1901.01753v3_poet_text_paged.txt` L25-L28

```
For example, in an example in Brant and Stanley [27] with mazes (the problems) and maze solvers (the solutions, represented by neural networks), the minimal criterion for the solvers is that they must solve at least one of the mazes in the maze population, and the minimal criterion for the mazes is to be solved by at least one solver.
```

### P2 — §2.2 MCC
**锚点**：PDF p.5（刊印 p.5）· `1901.01753v3_poet_text_paged.txt` L33-L36

```
However, in MCC there is no force for optimization within each environment (or maze in the example experiment). That is, once a maze is solved there is no pressure to improve its solution; instead, it simply becomes a potential stepping stone to a solution to another maze.
```

### P3 — §2.2 MCC
**锚点**：PDF p.5（刊印 p.5）· `1901.01753v3_poet_text_paged.txt` L37-L38

```
Additionally, in MCC problems have to be solvable by the current population, so complexity can only arise through drift.
```

### P4 — §2.2 MCC
**锚点**：PDF p.5（刊印 p.5）· `1901.01753v3_poet_text_paged.txt` L43-L46

```
In contrast, in POET, we accept problems if (according to some heuristics) they seem likely to be improved upon and/or solved after some amount of dedicated optimization effort (so POET will likely keep E 0 ), enabling a more direct and likely swifter path to increasingly complex, yet solvable challenges.
```

### P5 — §3 POET
**锚点**：PDF p.7（刊印 p.7）· `1901.01753v3_poet_text_paged.txt` L7-L11

```
POET then has three main tasks that it performs at each iteration of its main loop: 1. generating new environments E(·) from those currently active, 2. optimizing paired agents within their respective environments, and 3. attempting to transfer current agents θ from one environment to another.
```

### P6 — §3 POET
**锚点**：PDF p.7（刊印 p.7）· `1901.01753v3_poet_text_paged.txt` L12-L14

```
To generate a new environment, POET simply mutates (i.e. randomly perturbs) the encoding (i.e. the parameter vector) of an active environment.
```

### P7 — §3 POET
**锚点**：PDF p.7（刊印 p.7）· `1901.01753v3_poet_text_paged.txt` L19-L20

```
Furthermore, priority is given to those candidate environments that are most novel, which produces a force for diversification that encourages many different kinds of problems to be solved in a single run.
```

### P8 — §3 POET
**锚点**：PDF p.7（刊印 p.7）· `1901.01753v3_poet_text_paged.txt` L23-L25

```
The population of active environments is capped at a maximum size, and when the size of the population exceeds that threshold, the oldest environments are removed to make room (as in a queue).
```

### P9 — §3 POET
**锚点**：PDF p.7（刊印 p.7）· `1901.01753v3_poet_text_paged.txt` L17-L18

```
when new environments are generated, they are not added to the current population of environments unless they are neither too hard nor too easy for the current population.
```

### P10 — §4.2 Environment Encoding and Mutation
**锚点**：PDF p.10（刊印 p.10）· `1901.01753v3_poet_text_paged.txt` L1-L3

```
Because the parameters of an environment define a distribution, the actual environment sampled from that distribution is the result of a random seed. This seed value is stored with each environment so that environments can be be reproduced precisely, ensuring repeatability.
```

### P11 — §4.2 Environment Encoding and Mutation
**锚点**：PDF p.9（刊印 p.9）· `1901.01753v3_poet_text_paged.txt` L45-L47

```
For subsequent mutations, an obstacle parameter takes a mutation step (whose magnitude is given in Table 1), and either adds or subtracts the step value from its current value.
```

### P12 — §4.2 Environment Encoding and Mutation
**锚点**：PDF p.9（刊印 p.9）· `1901.01753v3_poet_text_paged.txt` L38-L40

```
As enumerated in Table 1, there are five types of obstacles that can be distributed throughout the environment: (1) stump height, (2) gap width, (3) step height, (4) step number (i.e. number of stairs), and (5) surface roughness.
```

### P13 — §4.2 Environment Encoding and Mutation
**锚点**：PDF p.10（刊印 p.10）· `1901.01753v3_poet_text_paged.txt` L9-L12

```
In our experiments, this condition is that the paired agent of the environment achieves a reward of 200 or above, which generally indicates that the agent is capable of reaching the end of the terrain (though slightly below the full success criterion of 230).
```

### P14 — §4.2 Environment Encoding and Mutation
**锚点**：PDF p.10（刊印 p.10）· `1901.01753v3_poet_text_paged.txt` L15-L18

```
Each child is generated from its parent by independently picking and mutating some or all the available parameters of the parent environment and then choosing a new random seed. The minimal criterion (MC) 50 ≤ E child (θchild ) ≤ 300 then filters out child environments that appear too challenging or too trivial for the current level of capability of agents.
```

### P15 — §4.2 Environment Encoding and Mutation
**锚点**：PDF p.10（刊印 p.10）· `1901.01753v3_poet_text_paged.txt` L19-L21

```
In case the number of child environments that satisfy the MC is more than the maximum number of children admitted per reproduction, those with lower E child (θchild ) are admitted until the cap is reached.
```

### P16 — §4.1 Environment and Experiment Setup
**锚点**：PDF p.9（刊印 p.9）· `1901.01753v3_poet_text_paged.txt` L15-L17

```
In this work, we define an environment as solved when it both reaches the far end of the environment and obtains a score of 230 or above. Based on our observations, the score of 230 ensures that the walker is reasonably efficient.
```

### P17 — §4.1 Environment and Experiment Setup
**锚点**：PDF p.9（刊印 p.9）· `1901.01753v3_poet_text_paged.txt` L14-L15

```
The episode immediately terminates when the time limit (2,000 time steps) is reached, when the agent falls, or when it completes the course.
```

### P18 — Algorithm 2 (POET Main Loop)
**锚点**：PDF p.8（刊印 p.8）· `1901.01753v3_poet_text_paged.txt` L9-L15

```
5: if t > 0 and t mod N mutate = 0 then 6: EA_list = MUTATE_ENVS(EA_list) # new environments created by mutation 7: end if
```

### P19 — Algorithm 2 (POET Main Loop)
**锚点**：PDF p.8（刊印 p.8）· `1901.01753v3_poet_text_paged.txt` L32-L32

```
if M > 1 and t mod N transfer = 0 then
```

### P20 — §6.1 Producing New Environments
**锚点**：PDF p.26（刊印 p.26）· `1901.01753v3_poet_text_paged.txt` L21-L25

```
Each child environment E child (·), together with its paired agent θchild , is checked against a predefined minimal criterion (reminiscent of the minimal criterion in the MCC algorithm [27]) and only those satisfying the minimal criterion are kept (denoted as MC_SATISFIED()), ensuring that potential new environments are not too trivial and not too hard (which would lead to little progress).
```

### P21 — §6.1 Producing New Environments
**锚点**：PDF p.26（刊印 p.26）· `1901.01753v3_poet_text_paged.txt` L25-L28

```
All remaining child environments are then ranked based on their novelty (detailed shortly), which is calculated with respect to the current active population of environments and an archive of all previously active environments (i.e. those that were allowed to enter the population previously).
```

### P22 — §6.1 Producing New Environments
**锚点**：PDF p.26（刊印 p.26）· `1901.01753v3_poet_text_paged.txt` L28-L32

```
A transfer attempt is then performed to see whether an agent from a different environment could lead to the best performance in a new child environment. The logic of transfer is described in the next section (Section 6.2). Each pair is then checked against the minimal criterion again in case some pairs no longer satisfy the minimal criterion after the transfer (e.g. if an environment is exposed as too easy).
```

### P23 — §6.1 Producing New Environments
**锚点**：PDF p.26（刊印 p.26）· `1901.01753v3_poet_text_paged.txt` L41-L45

```
For readers familiar with the novelty search algorithm [82], it is important to note here that the encoding of an environment is in effect a genetic representation, which means that in POET in effect novelty is a genetic diversity measure. That way, POET does not in principle require a behavior characterization (BC) [82] to be devised for environments, though doing so is also not precluded.
```

### P24 — §6.1 Producing New Environments
**锚点**：PDF p.26（刊印 p.26）· `1901.01753v3_poet_text_paged.txt` L60-L61

```
Note that in this work the distance between genetic encodings of environments is calculated with an L2-norm and the number of nearest neighbors k in the calculation of novelty is 5.
```

### P25 — §6.2 ES-Based Transfer
**锚点**：PDF p.27（刊印 p.27）· `1901.01753v3_poet_text_paged.txt` L50-L51

```
POET adopts a transfer mechanism that allows one agent (the emigrant) to attempt to transfer its learned capabilities to a target environment, possibly replacing the current target environment’s agent.
```

### P26 — §6.2 ES-Based Transfer
**锚点**：PDF p.27（刊印 p.27）· `1901.01753v3_poet_text_paged.txt` L62-L63

```
Then each agent in the augmented list (the original M agents and each of their M proposals) is evaluated in E(·) and the one with the highest reward is returned.
```

### P27 — §6.2 ES-Based Transfer
**锚点**：PDF p.27（刊印 p.27）· `1901.01753v3_poet_text_paged.txt` L65-L68

```
We refer to the replacement as transfer, and there are two types: the situation when the replacing agent is from the input candidate list (i.e. without an optimization step on E(·)) is referred to as a direct transfer, while if the replacing agent is one of the proposals, it is called a proposal transfer.
```

### P28 — §4.3 Results (two-way transfer)
**锚点**：PDF p.17（刊印 p.17）· `1901.01753v3_poet_text_paged.txt` L11-L13

```
Given the same amount of computation, the agent with the original walking gaits reaches a score of 309, while the one with the more optimal walking gait as illustrated in (b) reaches a score of 349.
```

### P29 — §4.3 Results (transfer accounting)
**锚点**：PDF p.18（刊印 p.18）· `1901.01753v3_poet_text_paged.txt` L11-L14

```
The total number of such replacement attempts in RUN 1, RUN 2, and RUN 3 (labelled in Figure 5) are 18,894, 19,014, and 18,798, respectively, out of which, 53.62%, 49.26%, 48.89%, respectively, are successful replacements (meaning one of the tested agents is better than the current niche champion).
```

### P30 — §4.3 Results (coverage metric)
**锚点**：PDF p.18（刊印 p.18）· `1901.01753v3_poet_text_paged.txt` L23-L28

```
We first uniformly sample 1,000 challenging, 1,000 very challenging, and 1,000 extremely challenging environments. For each of the total 3,000 sampled environments, the distance to the nearest one of the challenging, very challenging, or extremely challenging environments created and solved by POET (and by the control, respectively) is calculated. Note that the better covered the environment space is, the lower the sum of all such nearest distances will be.
```

### P31 — §4.3 Results (transfer ablation)
**锚点**：PDF p.18（刊印 p.18）· `1901.01753v3_poet_text_paged.txt` L28-L33

```
The result is that the coverage of environments created and solved by POET is significantly greater than by POET without transfer (p < 2.2e−16 based on Mann-Whitney U test), meaning POET with transfer explores more of the space of environments, including creating (and solving) more difficult environments. In an even more dramatic statistic showing the essential role of transfer in open-ended search, in POET without transfer, no extremely challenging environments are solved at all (Fig. 8).
```

### P32 — §4.3 Results (implicit curriculum)
**锚点**：PDF p.13（刊印 p.13）· `1901.01753v3_poet_text_paged.txt` L16-L19

```
Because newer environments in POET are created through mutations of older environments and because POET only accepts new environments that are not too easy not too hard for current agents, POET implicitly builds a curriculum for learning each environment it creates.
```

### P33 — §4.3 Results (difficulty levels / Table 2)
**锚点**：PDF p.13（刊印 p.13）· `1901.01753v3_poet_text_paged.txt` L53-L56

```
The difficulty level of an environment is based on how many conditions it satisfies out of the three listed in Table 2. In particular, a challenging environment satisfies one of the three conditions; a very challenging environment satisfies two of the three; and satisfying all three makes an environment extremely challenging.
```

### P34 — §4.3 Results (ES-alone control)
**锚点**：PDF p.10（刊印 p.10）· `1901.01753v3_poet_text_paged.txt` L79-L81

```
The maximum scores out of the five ES runs for the environments illustrated in Figure 2a, 2b, and 2c are 17.9, 39.6, and 13.6, respectively, far below the success threshold of 230 that POET exceeds in each case.
```

### P35 — §5 Discussion
**锚点**：PDF p.19（刊印 p.19）· `1901.01753v3_poet_text_paged.txt` L14-L16

```
The present problem space is a 2-D course of obstacles that can be generated within distributions defined by the genome describing the environment. This space is limited by the maximal ranges of those distributions.
```

