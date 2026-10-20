# 交接文件 · Agent「洞察力 / 架构学习」机制实证项目

> **给接手者**：你可能是另一个 Agent，也可能是另一个人。
> 这份文件 + 交付包（§4）＝ 接手所需的全部信息。
> **不需要重推任何东西**，§8 的数字都是实测的，别自己重算。
>
> 生成：2026-10-20 16:50 Asia/Shanghai
> 状态：核心装置已交付并自检通过；**主对比实验正在云端跑**，本文件随实验结果更新。

---

## 0. 30 秒上手

| 你想知道 | 去哪 |
|---|---|
| 这项目在问什么 | §1 |
| 现在到哪一步了 | §2（**先读这张**） |
| 正在跑的是什么、跑完谁接手 | §3 |
| 资产在哪（zip / GitHub / 依据包 / 权重） | §4 |
| 命令（冒烟 → 跑批 → 两遍分析 → 判读页） | §5 |
| 哪些口径不许动 | §6 |
| 踩过的坑（全部已修，别再踩） | §7 |
| 实测数字速查 | §8 |
| 你该做什么（按优先级） | §9 |
| 最终报告必须保留的声明 | §10 |

**三个最重要的纪律**（违反其一，这轮数据就废了）：
1. **判官必须跨厂商**（`deepseek/deepseek-chat`），且**必须先过判官自检闸门**（真 ≥3/4 且 假 ≥3/4）再跑批。
2. **不许改任何阈值**（去重 0.75、矛盾率分母定义、自检门槛）——那是预注册的。
3. **⑤b vs ⑤c 的差异必须与种子噪声地板比**；超不过 ⇒ 写「**不可分辨**」，**不写「无效应」**。

---

## 0.5 接手前 10 分钟（照这个顺序做）

**第 1 步 · 拿到代码**
```bash
git clone https://github.com/lixvanran/agent-creativity-mechanism-study.git
cd agent-creativity-mechanism-study
git fetch origin cmp8-handover-2026-10-20 && git checkout cmp8-handover-2026-10-20
```
⚠️ **必须切到 `cmp8-handover-2026-10-20` 分支** —— `main` 上还没有这些文件。
（若本机 git CA 有问题，用 `gh api` / `https://github.com/.../archive/refs/heads/<branch>.tar.gz` 下载。）

**第 2 步 · 读这三份（别跳）**
1. `HANDOVER-cmp8-2026-10-20.md`（本文件）
2. `docs/cmp8/AGENT_RUNBOOK.md`（执行手册：有闸门、有硬约束）
3. `docs/cmp8/METHOD.md`（方法学：判据口径、指标定义、已知局限）

**第 3 步 · 确认你要的是哪一类活**
- **只要结果** → 数据在 `cmp8/runs/cmp8/analysis.json`，判读页 `cmp8/compare5_report.html`。**不要重跑 800 次调用。**
- **要复现/重跑** → `cd cmp8 && bash rebuild/rebuild.sh`（会跑补丁脚本）→ `python3 smoke_or.py`（**闸门**）→ `python3 run_compare5.py ...`
- **要接着做研究** → 读 §9 的 P0/P1/P2

**第 4 步 · 拿凭据**
- `MINIMAX_SUBSCRIPTION_KEY`（被测侧）、`OPENROUTER_API_KEY`（判官+embedding）
- 在 Mavis 里用 `mavis secret list` 看有哪些 secret；**没有就让用户给，别硬编码**
- ⚠️ **判官必须是跨厂商**：`OR_PRIMARY=deepseek/deepseek-chat`（`grok-3-mini` 已 404 下架）

**第 5 步 · 开工前先确认三件事**
1. 判官自检过没过（真 ≥3/4 且 假 ≥3/4）
2. 你的臂间比较**用的哪个指标**（`n_raw` 还是 `width`）——`width` 依赖 embedding 通道
3. 你要下结论的话，**⑤b vs ⑤c 的差异 vs 种子噪声地板**比过了没

---

## 1. 项目在问什么

**命题**：一个 Agent 的"洞察力"到底来自哪里？

可测量的形式：把五种主流做法（直调 / 开源 ADHD 项目 / 双轴融合门 / 双轴去融合门 /
**训练出来的新架构**）放进**同一批外部真实题**，用**同一个跨厂商判官**打分，
看哪种机制让答案**覆盖更多、且不互相打架**。

**两条不可省的设计**：

**① 跨厂商判官。** 被测是 MiniMax，判官也用 MiniMax 的话，同厂模型容易对同一批错误达成一致
——「判据与被测同源 ⇒ 判据无效」。所以判官走 OpenRouter 上的**非 MiniMax** 模型。

**② 两个控制臂。** 主实验臂 A5b 唯一接触 oracle 的操作是 `VERIFY`（拿依据包核验断言）。
只报 A5b，分不清效果来自"架构更强"、"它拿到了别人没有的事实核验器"、还是"它多花了 2 次调用"。
所以：
- **A5a**（无核验）隔离"有没有 oracle"
- **A5c**（初始 w=0）隔离"学到的权重有没有用"

---

## 2. 现在到哪一步（三张表，**先读这张**）

### 2.1 ✅ 已确立（可以引用，结论稳固）

| 结论 | 关键数字 |
|---|---|
| **双轴去融合门 > 融合门**（写作方向，**正面成果，保留**） | 跨重复离散度 **0.7006 vs 0.9786**（越低越稳）。分支各自成文后信息存活显著提高；融合把差异抹平 |
| **逃逸度 2.8× 判死** | ~90% 置信。它是**重加权指标**，不是真测量 |
| **接收端「净信息增益」路线彻底证伪** | 7 个仪器版本全失败。接收端是"重新推导"不是"复制"；字面相似度与采纳**反向相关** |
| **监督学习不可行（精确化）** | 学不出真正的生成器负空间，但**可以**训练"选择器"和"如何搜索" |
| **目标函数 = 约束优化** | `max 宽度(去重并集) s.t. 矛盾率 ≤ 最优基线`。不再用"更好/更有深度"当目标 |
| **v3 学到的是"更谨慎地核验"，不是"探索更多"** | 留出集：矛盾率 33.3%→**0.0%**（泛化 ✅），宽度 1.33→1.33（**没泛化 ❌**）。训练集宽度 1.20→3.40 ⇒ 宽度增益是过拟合 |
| **判据与被测同源 ⇒ 判据无效** | ⇒ 跨厂商判官是**设计前提**，不是可选项 |
| **在题集上"挑赢家"必然过拟合** | Spearman(巡练, 留出) = **+0.166**；训练第 1 名 → 留出第 15 名（18 名里倒数第 4） |
| **核验器 v4 有效** | 法律域 **27/27**、矛盾召回 **9/9 = 100%**、支持 **11/11**；泛化到非法律域后真 7/7、假 8/10、**漏判 0** |
| **主动提案需要两个前提** | (a) 必须给**行动空间说明书**；(b) 诊断**不能含 oracle 侧统计**（否则 proposer 会去枚举答案） |

### 2.2 ❌ 已证伪（别再提）

- ❌ "逃逸度 2.8× 是真实提升" —— 是重加权假象
- ❌ "接收端净信息增益能测洞察力" —— 7 版仪器全灭
- ❌ "把题集上最好的那个方案当赢家" —— 过拟合
- ❌ "巡练（程序搜索）能提升留出表现" —— ρ=+0.166，无效
- ❌ "直接监督学习能训出更好的生成器"

### 2.3 ⚠️ 未决（**正在测，别提前下结论**）

| 未决问题 | 状态 | 怎么判 |
|---|---|---|
| **A5b（学到的策略）vs A5c（初始 w=0）** | **主对比实验正在跑** | 差异 vs **种子噪声地板**（同臂同题 3 次重复的逐份矛盾率标准差）。超不过 ⇒ 「不可分辨」 |
| **宽度结论是否依赖 embedding 通道** | 跑完后做**两遍分析** | 两遍臂间排序一致 ⇒ 稳健；不一致 ⇒ 两个数都报 + 明写"不稳" |
| **oracle 本身对不对** | **没做第二来源交叉核** | 矛盾率同时含"模型说错"与"oracle 说错"。**必须在报告里声明** |
| 判官若退到 MiniMax | 同源风险 | `analysis.json` 的 `judge_same_vendor` |

---

## 3. 正在跑的是什么

### 3.1 cmp8 五族对比实验（7 臂 × 4 题 × 3 重复 = 84 份）

| 臂 | 是什么 | 调用数 | 作用 |
|---|---|:-:|---|
| **A1** | 直调 | 1 | 基线 |
| **A2** | 开源 ADHD 项目（**机制复现**） | 11–12 | 外部项目对照 |
| **A3** | 双轴·**融合门** | 8 | 旧架构 |
| **A4** | 双轴·**去融合门** | 6 | 旧架构最强版 |
| **A5a** | 新架构·**无核验** | ~12 | 控制：隔离 oracle |
| **A5b** | 新架构·**学到的策略** | ~14 | **主实验** |
| **A5c** | 新架构·**初始 w=0** | ~14 | 控制：隔离权重 |

**新架构的机制**（A5a/b/c 共用）：
- **状态 = 图**：节点 = `CLAIM`（一条可核验断言）/ `ANSWER`（一份完整答案），边 = **操作**
- **操作集 7 个**：`GEN_PLAIN` / `GEN_ANGLE` / `EXTRACT` / `SPLIT` / `VERIFY` / `MERGE` / `STOP`
- **唯一接触 oracle 的是 `VERIFY`**
- **策略 = 14 维局部线性权重**，特征**与题无关**（只看 op 类型、目标节点状态、本分支历史）
  ⇒ n = **决策次数**（能泛化），而不是 n = 题数（必然过拟合）
- **装配是机械的**（不由模型重写）；**未经核验的断言单列一节**（既不静默丢，也不假装核验过）
- A5 的认知位置（FRAME / PERSONA / 模型轮换）与 A3/A4 **逐条一致** ⇒ 测的是架构，不是别的东西

### 3.2 云端跑批现状

| | |
|---|---|
| 执行会话 | `454370675753049`（标题「[cron] 打包五族对比实验交付包」） |
| 状态 | **进行中**（最后报告 12/84，2026-10-20 16:48） |
| 速率 | ≈ 33 s/次调用，总量 ≈ 800 次调用 |
| ETA | **2026-10-20 18:15–18:30 UTC** |
| 监控 | `monitor3.sh`（任务 `454379793445195`）：跑完自动做 ① 0 字检查 ② 分析遍 1（OpenRouter embedding）③ 分析遍 2（`EMBED_PROVIDER=minimax` → `runs/cmp8_mmemb`）④ `n_raw<5` 体检 + **逐臂解析失败率体检** ⑤ 判读页 |
| 产物 | `runs/cmp8/`（答案 + `runlog.jsonl` + `analysis.json`）、`runs/cmp8_mmemb/`、`compare5_report.html` |

**⚠️ 如果云端跑批还在跑、你没有 bash/凭据**：那就走 §5 的本地路径，两边结果互为验证。

### 3.3 判官自检（已过，2026-10-20）

```
判官 deepseek/deepseek-chat ：真断言 4/4 ｜ 假断言 4/4   ✅
判官 x-ai/grok-4.3          ：真断言 4/4 ｜ 假断言 4/4   ✅
```

---

## 4. 资产清单（全部在 drive / GitHub，**接手时按这个拉**）

### 4.1 交付包（**主资产**）

| 文件 | node_id | 字节 | 内容 |
|---|---|---:|---|
| **`cmp8_交付包_v3.zip`** | **`454382563336916`** | **168,677** | **40 个真实文件 ← 接手方拿这个**：完整 cmp8/ 树 + METHOD.md + AGENT_RUNBOOK.md（**含「判官解析失败率」处置规则**）+ cmp8_fetch.py + rebuild/（p0/p1/p2 + patch_or.py + patch_runbook.py + rebuild.sh） |
| `cmp8_交付包.zip` | `454375285564150` | 166,303 | 39 个文件：同 v3，但**执行手册缺「解析失败率」那一节**（其余一致） |
| `cmp8_交付包.zip` | `454380578374669` | 165,267 | 旧版（无解析解析失败率统计）——**别用这版** |
| **`cmp8_交接包.zip`** | **`454384890003597`** | **203,976** | **45 个真实文件 ← 接手方的完整工作集**：本交接文件 ×2 + METHOD ×2 + RUNBOOK ×2 + cmp8_fetch ×2 + 完整 cmp8/ 树 + rebuild/（p0/p1/p2 + patch_or.py + patch_runbook.py + patch_handover.py + rebuild.sh） |
| `HANDOVER-cmp8-2026-10-20.zip` | 见发包方消息（drive 节点随抽取延迟出现） | ~13.4 KB | **只含本文件一个 md**（`-j` 压平、无目录层级）⇒ **要转手给下一个 Agent 时的最小单文件** |

> ⚠️ **为什么本文件里不写「最新那个 zip」的 node_id**：
> 一个包含自己地址的文件**无法自洽** —— 填进 node_id 会改文件、改文件会改 zip、改 zip 就换了 node_id ⇒ 无限回环。
> ⇒ **本文件只引用地址稳定的包**（`454382563336916` / `454384890003597`）；
> 「只含本文件的单文件 zip」的地址**写在发包方的消息里**，不写进文件内部。
> 这不是遗漏，是**故意的**。

**拉取方法**（沙箱里 bash 可用时）：
```bash
mavis drive files download --node_id=454382563336916   # → download_url
curl -sL -o cmp8.zip "<download_url>"
```
**用户本地**（无 mavis CLI）：去 Mavis 文件管理界面找 `cmp8_交付包_v3.zip` 下载，
或直接用包内/同目录的 `cmp8_fetch.py`（见 §5.0）。

**或者**用同包的 `cmp8_fetch.py`（见 §5.0）。

**包内结构**：
```
cmp8pkg/
├─ AGENT_RUNBOOK.md      ← ① 先读：执行手册（硬约束 / 阶段闸门 / 回报清单 / 故障排查）
├─ METHOD.md             ← ② 再读：方法学（臂定义 / 判据协议 / 指标口径 / 已知局限）
├─ README.md             ← ③ 快速上手
├─ EXPERIMENT-v2-DESIGN.md
├─ _CMP8_RECOVERY.md     ← 重建记录 + 4 个 bug 的复现与修法
├─ rebuild/              ← p0/p1/p2 + patch_or.py + patch_runbook.py + rebuild.sh + 2 份文档
├─ creativity_lab/       核心库 7 件 + data/user4_q{1..4}.json（4 份依据包）
├─ armdeps/              旧双轴架构：arm3.py / client2.py / shared.py / topics4.py
├─ run_compare5.py       7 臂驱动
├─ analyze_cmp6.py       跨厂商判官分析器（含去重体检表 + 解析失败率表）
├─ smoke_or.py           冒烟（★ 闸门）
├─ build_compare5_page.py 判读页生成
├─ go_cmp8.sh            一键编排
└─ runs/arch_learn/result.json   学到的 14 维权重（A5b 的命根子）
```

> **重建一致性已终验**：干净解压 → `bash rebuild/rebuild.sh` → **25 个文件与包内逐字节一致**。
> **⚠️ `rebuild.sh` 最后一步会跑 `patch_or.py` + `patch_runbook.py`，不许跳过** ——
> 不跑的话重建出来是**旧版默认模型**（`grok-3-mini` 已 404、`text-embedding-3-small` 已 403）⇒ **不能跑**。

### 4.2 GitHub（**代码与数据的主战场**）

- 公开仓：`https://github.com/lixvanran/agent-creativity-mechanism-study`
- **接手分支：`cmp8-handover-2026-10-20`**（`main` 上还没有这些文件，**必须切分支**）

```bash
git clone https://github.com/lixvanran/agent-creativity-mechanism-study.git
cd agent-creativity-mechanism-study
git fetch origin cmp8-handover-2026-10-20
git checkout cmp8-handover-2026-10-20
```

**仓库里现在有什么**：

| 路径 | 内容 |
|---|---|
| `HANDOVER-cmp8-2026-10-20.md` | **本文件（接手入口）** |
| `docs/cmp8/{METHOD,AGENT_RUNBOOK,EXPERIMENT-v2-DESIGN,_CMP8_RECOVERY}.md` | 方法学 / 执行手册 / 设计 / 重建记录 |
| `cmp8/` | **完整可跑执行树**：7 臂驱动、判官分析器、冒烟、判读页、`creativity_lab/`（核心库 7 件 + **4 份依据包**）、`armdeps/`、`runs/arch_learn/result.json`（14 维权重）、`rebuild/`（一键重建） |
| `cmp8/runs/cmp8/` | **跑批产出**：84 份答案、`runlog.jsonl`、**`analysis.json`**、`judge_selfcheck.json` |
| `cmp8/runs/cmp8_mmemb/` | 第二遍分析（MiniMax `embo-01` 通道） |
| `cmp8/compare5_report.html` | **判读页**（每臂每题每重复的原始答案 + 指标） |
| `creativity_lab/`（**仓库根，不是 `cmp8/` 下**） | **训练侧**：`train_policy.py`（产出那 14 维权重）、`arch_v2.py`、`train_agent.py`、`train_selector.py`、`measure_breadth.py`、`measure_paradox2.py`、`check_breadth_validity.py`、`test_verifier.py`、`workflow.py`、`scipy_free.py`、`calibration.py`、`contrasts.py`、`leakage.py`、`prompts.py`、`arms/`、`gates/`、`drill*.py`、`pilot_v2*.py`、`train_pipeline*.py` |
| `creativity_lab/data/` | **题库与回归集**：`legal_topics.json`、`legal_topics_v2.json`（**核验器回归集，18 题**）、`policy_topics.json`（**8 道政策域训练题**）、`train_topics.json`、`topics.json` |
| `TRAINING-METHOD-REPORT.md` / `REPORT-ARCHLEARN-2026-10-19.md` / `docs/CORRECTION-2026-10-18-breadth.md` / `POSTMORTEM.md` / `FINDINGS.md` | 历史报告与复盘 |

> **训练侧不需要重搬**：上表 `creativity_lab/` 那一行的文件**仓库里已经有了**（HEAD `e012f1e`，共 204 个文件，已逐个核对存在）。
> 缺的只有 `creativity_lab/measure_disagreement.py`（本地也没有，不是漏搬）。
> ⇒ **要重训权重或复核训练结论，直接用仓库根的 `creativity_lab/`**，不要去 `cmp8/creativity_lab/` 找。
> ⚠️ 注意别混：仓库根的 `creativity_lab/` = **训练侧**；`cmp8/creativity_lab/` = **执行侧**（含 orclient / adhd_repro / 依据包）。
> 两边**同名文件可能不同版本**（`verify.py` / `client.py` / `metrics.py` 都有），执行侧以 `cmp8/` 为准。

**⚠️ 拉不到 git 时**（本机 CA 可能有问题）：
```bash
curl -sL -o cmp8.tar.gz https://github.com/lixvanran/agent-creativity-mechanism-study/archive/refs/heads/cmp8-handover-2026-10-20.tar.gz
tar xzf cmp8.tar.gz
```

### 4.3 依据包（4 份，各 16 条原子事实）

在包内 `creativity_lab/data/user4_q{1..4}.json`。由 4 个子代理**联网独立构造**、**不读任何已有答案**。

| 题 | 事实条数 | 来源数 | 性质 |
|:-:|:-:|:-:|---|
| A1 湖北620分选AI | 16 | 30 | 数字型（位次/分数线/选科要求） |
| A2 公路赛战术 | 16 | 29 | 规则型（UCI 规则 + 运动生理） |
| A3 假期作业 | 16 | 26 | 方法学型（实证研究） |
| A4 气质量表 | 16 | 21 | **有确定答案**（阈值链完整） |

**A4 的答案在依据包里推得出来**（不是偷看）：多血质 23 与胆汁质 −6 相差 29 ≫ 4（高出 4 分以上的门槛），且 23 > 20（典型型）⇒ **典型多血质**。

### 4.4 凭据（**只给 secret 名字，不给 key 值**）

| secret 名 | 用途 |
|---|---|
| `MINIMAX_SUBSCRIPTION_KEY` | 被测侧（7 臂的产出，$0） |
| `OPENROUTER_API_KEY` | 判官 + embedding（总计 < $1） |
| `GITHUB_TOKEN_LIXVANRAN` | 推仓库 |

用 `mavis secret list` 管理；**绝不要把 key 写进任何文件或提交**。

---

## 5. 命令（照抄）

### 5.0 拿到包（本地无 mavis CLI 时）
```bash
python3 cmp8_fetch.py --node-id 454382563336916      # 需本机有 mavis CLI
# 或：python3 cmp8_fetch.py --url "<签名下载链接>"
# 或：python3 cmp8_fetch.py --local ./cmp8_交付包_v3.zip
```
脚本会下载 + 算 sha256 + `unzip -t` + 检查关键文件是否齐全，并打印下一步命令。
**它不碰任何 key，只做下载与校验。**

### 5.1 环境变量
```bash
pip install numpy                        # 唯一第三方依赖
export MINIMAX_SUBSCRIPTION_KEY=...
export OPENROUTER_API_KEY=...
export PRIMARY_MODEL=MiniMax-M3.1-Flash-Preview
export OR_PRIMARY=deepseek/deepseek-chat     # 判官：跨厂商、非 MiniMax
export OR_EMBED=qwen/qwen3-embedding-8b       # embedding：4096 维
export CMP_OUT=runs/cmp8
export ADH_MODE=repro                          # 臂2 走 Python 复刻
export OPENROUTER_BASE_URL=https://api.minimaxi.com/v1   # MiniMax 侧
export OR_BASE_URL=https://openrouter.ai/api/v1           # OpenRouter 侧
```

### 5.2 重建 + 静态自检
```bash
cd cmp8pkg && bash rebuild/rebuild.sh
for f in $(find . -name "*.py"); do python3 -m py_compile "$f" || echo "FAIL: $f"; done
```

### 5.3 ★ 冒烟（闸门）
```bash
python3 smoke_or.py
```
**通过标准：判官自检「真断言 ≥3/4 且 假断言 ≥3/4」。不过 ⇒ 不要跑批，直接回报。**

### 5.4 跑批
```bash
python3 run_compare5.py --arms A1,A2,A3,A4,A5a,A5b,A5c --reps 3 --workers 4
```
约 1.5–2 小时。**`--workers 4` 不要调高**（8 并发实测触发 429 整片失败）。**中途不要重跑**（跨批次重复会污染统计）。

### 5.5 分析（**两遍都要**）
```bash
CMP_OUT=runs/cmp8         python3 analyze_cmp6.py    # 遍1：OpenRouter qwen embedding
CMP_OUT=runs/cmp8_mmemb EMBED_PROVIDER=minimax python3 analyze_cmp6.py   # 遍2：embo-01（0.75 的标定基准）
python3 build_compare5_page.py
```

### 5.6 一次性跑完
```bash
bash go_cmp8.sh     # 冒烟 → 跑批 → 两遍分析 → 判读页
```

---

## 6. 口径纪律（**不许动的**）

1. **去重阈值 0.75**（标定在 MiniMax `embo-01` 上）。换 embedding 模型 ⇒ 余弦尺度变 ⇒
   **宽度类指标不可跨 embedding 模型比较** ⇒ 必须两遍分析比排序。
   保留率 `width/n_raw`：0.2–0.6 可用 ｜ <0.15 退化（宽度轴废了）｜ >0.85 阈值太松。
2. **矛盾率 = 矛盾/(支持+矛盾)**，**解析失败既不进分子也不进分母**（不把"读不懂"当"说对了"），
   **但失败条数必须报出来**（`n_parsefail` / `parsefail_rate`）。
   **> 10% ⇒ 该臂矛盾率的分母被悄悄缩小 ⇒ 臂间不可比 ⇒ 标注出来，不许重跑掩盖。**
3. **`n_raw`（原始断言数）不依赖 embedding** ⇒ 最无争议的广度指标。
   宽度轴废了也能用它撑住"谁覆盖得更多"（模型会在一份答案里把同一事实说 3–4 遍 ⇒ 原始条数会被抬高，但**对所有臂一视同仁**）。
4. **判据措辞已泛化**：CHECK4 第一步从「是不是法律主张」改成「是不是可核验的事实性断言」，
   判据 = **只要陈述里含有超出问题本身的信息（数字/阈值/名称/规则/主体关系）就当它是断言**。
   泛化后法律域回归 27/27 保住、矛盾召回 9/9。
5. **每条断言独立核验**，不传播、不建池、不做最近邻继承。
6. **不确定性一律答「未提及」**（不许猜）。
7. **装配必须机械**；未核验的断言单列一节。
8. **判官若退到 MiniMax ⇒ 与被测同源 ⇒ 必须在报告里声明**（`analysis.json` 的 `judge_same_vendor`）。
9. **429 只退避不换模型**（换模型会悄悄改掉"模型构成"这个变量）；**只有连续 529 才降级**，且降级要记录。

---

## 7. 踩过的坑（**全部已修，列出来是为了别再犯**）

| # | 症状 | 根因 | 修法 |
|:-:|---|---|---|
| 1 | 整臂 0 字符，表格看着正常 | M3 整片过载 529 | 过载重试 + 降级 + **记录实际模型** |
| 2 | 判官"0 字符却不报错" | 404 被归成 `other` ⇒ 静默重试 4 次 ⇒ `return ""` | 404→`gone`、403→`forbidden`；遇这两类**立刻换模型**；**全失败抛错带原因** |
| 3 | **坏掉的判官看起来像完美结果** | 空串 ⇒ 所有断言"解析失败" ⇒ 矛盾率 = 0/0 = 0 | 必须看自检结果，不能只看"跑完了" |
| 4 | 解析失败率没被报出来 | 失败条数从未统计 | 加 `n_parsefail` / `parsefail_rate` + 阈值告警 |
| 5 | 新架构臂输出空壳「（无）」 | `assemble` 静默丢 `verdict=None` 的断言 | 单列「未经核验的断言」一节 |
| 6 | 策略学习从未发生 | `scored.sort(key=lambda x: -x[1][0])` —— `x[1]` 是 `(op,tgt)`，按 **op 字符串**倒序排 | 改 `-x[0]`（按分数）；**必须打印操作直方图**，聚合指标会把"没在学"显示成"在学" |
| 7 | 聚合指标骗人 | one-hot 位被别的项覆盖时权重照样"学出东西"，但对决策影响为 0 | 打印每维权重对 argmax 的实际影响 |
| 8 | 显示骗人 | `"%d 次" % np.mean(...)` 把 0.8 截断成 0 | 显示要复现原值 |
| 9 | 进程崩 | `LLM().embed` 瞬时返回 None | 重试 + 字符 bigram 降级；**`learnarch.py` 曾漏 `import time`**（只在异常路径触发 latent NameError） |
| 10 | 核验器在非法律域失效 | CHECK4 问"是不是法律主张" ⇒ "620分累计7436人"被判"复述题面" | 泛化成"可核验的事实性断言" |
| 11 | 直接核验被放大 | direct 偏置（不传播、不建池） | 每条独立核验 |
| 12 | 自我重复被当成覆盖广 | 模型在**一份**答案里把同一事实说 3–4 遍 | 任何按断言条数算的量**必须先去重** |
| 13 | 差集基线串题 | `dpool` 没按题过滤 | 按题过滤 |
| 14 | `pkill -f` 把自己所在 shell 杀了 | 匹配到自己 | 用 `^python3` 前缀 |
| 15 | `subprocess` 管道死锁 | SDK 派生的孙进程继承管道写端不退出 ⇒ `capture_output=True` 永久阻塞 | **重定向到文件** |
| 16 | `rm -rf` 在 NAS 挂载上撞竞态 | 报 "Directory not empty" | 换新输出目录 |
| 17 | 判官限流误触发降级 | 429 被当过载 | 分类：**429 只退避，529 才降级** |
| 18 | embedding 返回错位 | 返回顺序不保证与输入一致 | **必须按 index 排序**（错位会静默污染去重） |
| 19 | embedding 缓存污染 | OpenRouter 缓存是**类级**的（判官实例与 embedding 实例共用）；MiniMax 缓存键漏 `typ`（db/query 语义不同） | 改实例级 + 键带模型名/typ |
| 20 | "一键重建 ≠ 交付包" | 补丁直接打在树上、没并进还原脚本 ⇒ 重建拿到旧版 | **所有补丁合并进唯一真相源脚本**（`patch_or.py` / `patch_runbook.py`），**幂等**（锚点不在但新文本已在 ⇒ 跳过） |
| 21 | **"看起来打上了、其实没打"** | 补丁块插在 `write()` **之后** ⇒ 算出来的值根本没落盘（**语法错误会炸，这个不炸**） | 补丁必须在写盘**之前**；**终验必须从干净解压重建再逐字节 diff** |
| 22 | 交付树与重建树手工维护两份 | 改一边忘另一边 | **让 B 从 A 生成**（树 = 重建产物） |
| 23 | 沙箱重置丢源文件 | —— | 文件正文常留在会话消息历史里（`write` 的 `tool_call_args` 含全文）；也可从 drive 搜回 |
| 24 | 跨会话文件不可互传 | 挂载单向 | 我的 write → 它看得见；**它的 write → 我看不见** |

---

## 8. 实测数字速查（**别重推**）

### 8.1 仪器
- 核验器 v4：法律域 **27/27**；矛盾召回 **9/9 = 100%**；支持 **11/11 = 100%**
- 泛化后新域自检：真 **7/7**、假 **8/10**、**漏判 0**（那 2 条"误判"是自检期望写错：oracle 没写的数字应判「未提及」）
- 判官自检（2026-10-20）：deepseek **4/4 + 4/4**；grok-4.3 **4/4 + 4/4**

### 8.2 v3 架构学习
| | 宽度 | 矛盾率 | 终局奖 |
|---|---|---|---|
| 初始 w=0（留出 3 题） | 1.33 | **33.3%** | −0.47 |
| 学到的 w（留出 3 题） | 1.33 | **0.0%** | **+0.27** |
| 训练集宽度 | 1.20 → **3.40** | | |

**⇒ 学到的是「更谨慎地核验」（泛化了），不是「探索更多」（过拟合了）。目标函数应是「少说错」而非「多想到」。**

### 8.3 学到的权重（A5b 用的）
14 维，**范数仅 0.062**，14 维里 6 维恒为 0。
```
[-0.0162, +0.0099, +0.0154, +0.0154, +0.0066, 0, ~0, +0.0219, 0, 0, +0.0468, +0.0169, 0, 0]
```
**⚠️ ε-greedy 的随机加分（0–2.0）比策略信号（最大 ~0.09）大 20 倍** ⇒
A5b vs A5c 在 n=3 上的差异**极可能只是随机波动** ⇒ **必须用噪声地板判**。

### 8.4 OpenRouter 可用性（2026-10-20 实测，这把 key）
key **健康**（余额 $4.999/$5，账号 $20 额度）⇒ **不是 key/账号/IP 问题**。

| 状态 | 模型 |
|---|---|
| ✅ chat（跨厂商） | `deepseek/deepseek-chat`（$0.26/$1.03 每 M，最便宜）、`x-ai/grok-4.3`（$1.25/$2.50）、`qwen/qwen3.7-plus`（$0.32/$1.28）、`z-ai/glm-4.5`、`meta-llama/llama-3.3-70b-instruct`、`openai/gpt-oss-120b`、`mistralai/mistral-large` |
| ❌ chat 死 | `x-ai/grok-3-mini` / `grok-4-fast` / `grok-3` / `grok-2-1212`（**404 已下架**，xAI 建议改用 grok-4.3）、`openai/gpt-4o-mini` / `google/gemini-2.5-flash`（**403 区域限制**） |
| ✅ embedding | `qwen/qwen3-embedding-8b`(4096)、`qwen3-embedding-4b`(2560)、`baai/bge-m3`(1024)、`sentence-transformers/all-minilm-l6-v2`(384) |
| ❌ embedding 死 | `openai/text-embedding-3-{small,large}`、`google/gemini-embedding-001`（**403 provider ToS**） |

### 8.5 成本
被测走 MiniMax 订阅 **$0**；判官 ≈ $0.12；embedding ≈ $0.05；**总计 < $1**。

---

## 9. 接手者的工作清单

### P0 · 拿到结果（如果云端跑批已结束）
```bash
# 云端：读打包会话的回报，或直接看 runs/cmp8/analysis.json
# 本地：跑 §5.3→§5.5
```
**要交出的东西**：
1. **7 臂表**：字符 / 断言数(n_raw) / 去重宽(width) / 矛盾率 / 支持率 / 离散度
2. **逐题并集宽度**（4 题）
3. **逐题矛盾率**（4 题）
4. **【⑤b vs ⑤c】原文**（含**种子间标准差**）—— **整轮实验的胜负手**
5. **两遍分析的 `n_raw` / `width` / 保留率**对比
6. **「判官解析失败率」表**（>10% 的臂单独标出）
7. `judge_selfcheck.json`、`analysis.json` 的 `judge` / `judge_used` / `judge_same_vendor` / `embed` / `census`
8. **A5 三臂的 `ops` 直方图**（**A5b 与 A5c 分布一样 ⇒ 权重没起作用，这本身就是结论**）
9. **A5 三臂的 `fallback` 字段**（大面积 true ⇒ **这批 A5 数据要打折**）
10. 判读页路径（`compare5_report.html`）

### P1 · 写结论（**不许提前下**）
- 唯一仲裁器 = **矛盾率**
- **A5b vs A5c 的差异 vs 种子噪声地板** ⇒ 超不过写「**不可分辨**」
- **最终评分与标注由人做**；判读页给原始答案，指标只是辅助
- 保留 §10 的全部声明

### P2 · 回到主线（扩大样本）
- 政策域扩到 **20+ 题**、重复 5，把断言分母从 8–21 提到 **100+**
- **把学习单元从"选哪条边"提到"图长什么样"**（节点数、怎么连、并行还是串行）
- **让操作集本身也可学**（强版本：连"有哪些操作"都是学出来的）
- **加题而不是加采样**（功效不足时，n→∞ 也有地板）
- 补 **oracle 第二来源交叉核**（当前最大未决局限）

---

## 10. 最终报告**必须**保留的声明

1. **臂2 是机制复现，不是原版本体**。照搬 `src/engine.ts`（reframe → 5 帧×6 想法 → score+cluster → deepen top3 = 11 次调用）、
   `src/packs/core.ts` 的 15 个认知帧、`src/render.ts` 的输出形状，**只换传输层**。
   差异：① 原用 `systemPrompt:{preset:"claude_code"}` 会叠加 Claude Code 自己的系统提示，复刻版只注入项目自己的；
   ② 帧选择同分布随机；③ 其余照搬。原版走 claude-agent-sdk，实验当天**彻底挂死**
   （`Claude Code process exited with code 1`，1200s 超时零输出）。
2. **模型集被固定为 5 个健康档位**（M3.1-Flash-Preview / M2.7 / M2.5 / M2.1 / M2），各臂完全一致
   —— 因为 M3 当天整片返回 529 过载。
3. **判官是跨厂商的**（被测 MiniMax、判官 deepseek/grok）；**若退到 MiniMax 则同源，必须声明**。
4. **用户的四道题是外部测试集**，全程未进训练；依据包由子代理联网独立构造，**不读任何已有答案**、只收原子事实、不收建议。
5. **oracle 没有第二来源交叉核** ⇒ 矛盾率同时含"模型说错"与"oracle 说错"。
6. **n 小**（12 份/臂、4 题）⇒ 结论是**方向性**的，不是精确裁决。
7. **去重阈值依赖 embedding 通道**（0.75 标在 `embo-01`）⇒ 宽度结论的可比性要按两遍分析的结果说。
8. **最终评分由人做。**

---

## 附：凭据与工程约定

- **不要把任何 key 写进文件或提交。** 只用 secret 名（§4.4）。
- **`pkill -f` 必须带 `^python3` 前缀**（否则会杀掉自己所在的 shell）。
- **NAS 挂载时钟偏移** ⇒ `__pycache__` 的旧 .pyc 可能被当新鲜 ⇒ `find . -name __pycache__ -exec rm -rf {} +`。
- **别用 `rm -rf` 在 NAS 挂载上删目录**（竞态）⇒ 换新输出目录。
- **多机 / 多会话并行时**：改动要写回**源文件**，并明确让对方「重新拷贝再跑」；
  **挂载传播有时延** ⇒ 别假设"对方写了=我这边有"，**要自己复核**。
- **自己写的代码必须让自己以外的东西跑一遍**（兄弟会话、外部审计者都算）。
  本项目今天就靠这条抓出了 `cmp8_p0.py` 的 raw-string 未闭合（在我自己机器上永远跑不出来）。
