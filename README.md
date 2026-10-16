# creativity-lab

**可复现实验台：检验「多样性机制」在开放任务上是否真的有效。**

> 起源于一项关于 ADHD 认知机制能否增强 Agent 创造力的对抗性迁移研究。
> 目标不是造一个更好的 Agent，而是**造一把能判断某个机制到底有没有用的尺子**。

---

## 为什么会有这个东西

研究中出现过一个反复出现的现象：**同一个机制，在开放作文题上有效，在有正确答案的实际题上完全失效。**

于是问题变成了：这个机制到底是在「扩大搜索空间」，还是只在「重加权已有分布」？

本仓库给出的答案是：**大多数所谓多样性机制，两者都不是——它们只是让分布挪了个位置。**

而**挪位置**和**变大**，必须用不同的仪器测。这就是这个包存在的理由。

---

## 安装与运行

```bash
pip install -e .

export OPENROUTER_BASE_URL="https://api.minimaxi.com/v1"
export MINIMAX_SUBSCRIPTION_KEY=...

# 1) 先验提示词没泄漏，再跑
creativity-lab leak --paths creativity_lab/prompts.py

# 2) 跑对照矩阵
creativity-lab run --arms direct,dual_fuse,dual_select --reps 3 --out runs/exp1

# 3) 分析
creativity-lab analyze --run runs/exp1

# 4) 可达性探针：区分「够不到 / 不愿说 / 差一步」
creativity-lab reach --topics creativity_lab/data/topics.json --probes probes.json
```

无需 pytest（沙箱 pip 不通）：`python3 tests/run_tests.py`

---

## 三条设计纪律（每条都对应一次真实失败）

### 1. 门控只允许「度量」，不允许「先验」

我此前三次犯同一种错：手挑认知框架 → 手写实体表 → 手挑选项类别。
**本质都是「在门控里写我以为该出现的答案」。**

`gates/base.py` 的接口被设计成只能计算度量，参照系必须由调用方从**真实产出**传入。
`tests/test_core.py` 里有一条 `test_gate_contains_no_content_words` 专门守这个。

### 2. 审计只认调用日志，不认 arm 的自述

早期实验里，一个 arm 详细汇报了「空放前 vs 空放后」的差异——**而根本没有空放**。它为一个没发生的机制编造了执行记录。

现在 `client.LLM` 维护 `llm.rec`，每次真实调用一条 `Call` 记录。
`analyze` 的可靠性表只读这个日志。**arm 没有机会自述。**

### 3. 检查器必须先证明自己能抓到东西

复盘里最尴尬的一条：我建了泄题检查器，禁词表里全是「新颖 / 可检验 / 承重」这类抽象词，
而代码里实际写的是「**最不像套话 / 最站得住 / 最不像常规**」——**一条都没命中**，
而我把它当成证据用了两轮。

现在 `leakage.self_test()` 会往临时文件里塞已知违规，**确认能抓到才允许被使用**。
禁词表补了当时漏掉的三个口语化表述。

---

## 架构：ToT 式的可插拔槽位

读了 `princeton-nlp/tree-of-thought-llm` 的源码之后（见 [FINDINGS.md](FINDINGS.md)），
本包采用同样的槽位化设计：

| 槽位 | 本包实现 | 备注 |
|---|---|---|
| 状态 | 外部对象，逐步累积 | 不在上下文窗口里搜索 |
| 生成 | `Dual._diverge` | 5 路零共享上下文 |
| 评估 | `metrics.*` | 纯函数，可换成非 LLM |
| **选择** | **`gates.Select`** | **纯函数**，`greedy` / `sample` / `novelty_biased` 一行切换 |
| 搜索 | 单层并行 + 末步 | BFS/DFS 未实现 |

**「选择器是可插拔纯函数」是此前四臂里完全缺失的槽位**——
它们把选择塞进一次 LLM 调用，于是连温度都调不了。

---

## 目录

```
creativity_lab/
  client.py       MiniMax 双通道客户端（chat + embed），三重失败防护
  prompts.py      **全部发给模型的字符串**（隔离，leakage 只扫这一个文件）
  leakage.py      泄漏静态检查（先自检再扫）
  gates/base.py   Gate 协议 + Select 选择器（纯函数）
  metrics.py      逃逸度 / 离散度 / 有效秩 / 模态数
  arms/
    direct.py     臂1 直接调用
    dual.py       臂3（fuse=融合门）/ 臂4（select=只选不融）
  runner.py       统一跑器 + 调用日志
  analyze.py      统一分析
  cli.py          命令行
data/
  practical-4q/    48 份历史产出（实际问题）
  writing-3q4arm/  27 份历史产出（作文题）
docs/             文献综合、外部实测
POSTMORTEM.md     六个错误与更正
FINDINGS.md       源码级核实记录
```

---

## 当前状态

**已成立**
- 融合门是坍缩点：同一批发散，末步「融合」→「验证+选择」，逃逸度 0.0377 → 0.1048
- ToT 源码核实（4 个可插拔槽位），含对某论文转述错误的更正
- 84 份无编造产出 + 逐次调用日志
- 六类方法论错误的定位与更正

**下一步（按优先级）**
1. **末步类型 → 探索存活率**曲线：融合 / greedy 选 / 验证后选 / 不做末步，四组对照。`Select` 已经是纯函数，只差对照设计。
2. **真正的外部基线**：本包目前只有 direct / dual_fuse / dual_select，臂2（ADHD 项目真代码）与 ToT 原版尚未接入。
3. **换评估量**：逃逸度是重加权指标，测不出扩张。需要 Vendi 熵或 control-variate coverage。
4. **精读 MACE 方法节全文**——它是唯一正面处理「agent 不会互相探索」的论文，而我至今只读了摘要（其代码至今未放，仓库只有一行 README）。

---

## 立场

宁可记录一个被推翻的结论，也不留一个无法复现的领先。

**MIT License**
