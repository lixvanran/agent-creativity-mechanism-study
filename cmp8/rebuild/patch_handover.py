#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HANDOVER-cmp8-2026-10-20.md 的两处补丁（唯一真相源，幂等）。

用法：python3 patch_handover.py <HANDOVER-cmp8-2026-10-20.md 路径>

改动 1：§4.1 资产表填实 node_id（原来写"用 search 查"，对接手者不友好）
        + 补上 cmp8_交接包.zip 这一行
改动 2：§5.0 换用 v3 的 node_id，并说明脚本会做下载 + sha256 + unzip -t + 关键文件检查
"""
import io
import sys

OLD1 = """| 文件 | node_id | 字节 | 内容 |
|---|---|---:|---|
| `cmp8_交付包.zip` | `454375285564150` | **166,303** | 39 个真实文件：完整 cmp8/ 树 + 2 份方法文档 + rebuild/ |
| `cmp8_交付包_v3.zip` | （新文件名 ⇒ 新 node，用 `mavis drive files search --keyword=v3` 查） | 168,677 | 40 个文件：**额外含执行手册的「判官解析失败率」处置规则** |
| `cmp8_交付包.zip`（另一 node） | `454380578374669` | 165,267 | 旧版（无解析失败率统计）——**别用这版** |

**拉取方法**（沙箱里 bash 可用时）：
```bash
mavis drive files download --node_id=454375285564150   # → download_url
curl -sL -o cmp8.zip "<download_url>"
```
**用户本地**（无 mavis CLI）：去 Mavis 文件管理界面找 `cmp8_交付包.zip` 下载。
"""

NEW1 = """| 文件 | node_id | 字节 | 内容 |
|---|---|---:|---|
| **`cmp8_交付包_v3.zip`** | **`454382563336916`** | **168,677** | **40 个真实文件 ← 接手方拿这个**：完整 cmp8/ 树 + METHOD.md + AGENT_RUNBOOK.md（**含「判官解析失败率」处置规则**）+ cmp8_fetch.py + rebuild/（p0/p1/p2 + patch_or.py + patch_runbook.py + rebuild.sh） |
| `cmp8_交付包.zip` | `454375285564150` | 166,303 | 39 个文件：同 v3，但**执行手册缺「解析失败率」那一节**（其余一致） |
| `cmp8_交付包.zip` | `454380578374669` | 165,267 | 旧版（无解析解析失败率统计）——**别用这版** |
| **`cmp8_交接包.zip`** | **`454384890003597`** | **203,976** | **45 个真实文件 ← 接手方的完整工作集**：本交接文件 ×2 + METHOD ×2 + RUNBOOK ×2 + cmp8_fetch ×2 + 完整 cmp8/ 树 + rebuild/ |
| `cmp8_交接包_v2.zip` | （新文件名 ⇒ 新 node，由发包方回填） | — | = 上一个包 + 本交接文件 §4.1 回填（node_id 改动 3） |

**拉取方法**（沙箱里 bash 可用时）：
```bash
mavis drive files download --node_id=454382563336916   # → download_url
curl -sL -o cmp8.zip "<download_url>"
```
**用户本地**（无 mavis CLI）：去 Mavis 文件管理界面找 `cmp8_交付包_v3.zip` 下载，
或直接用包内/同目录的 `cmp8_fetch.py`（见 §5.0）。
"""

OLD2 = """### 5.0 拿到包（本地无 mavis CLI 时）
```bash
python3 cmp8_fetch.py --node-id 454375285564150
# 或：python3 cmp8_fetch.py --url "<签名下载链接>"
# 或：python3 cmp8_fetch.py --local ./cmp8_交付包.zip
```
"""

NEW2 = """### 5.0 拿到包（本地无 mavis CLI 时）
```bash
python3 cmp8_fetch.py --node-id 454382563336916      # 需本机有 mavis CLI
# 或：python3 cmp8_fetch.py --url "<签名下载链接>"
# 或：python3 cmp8_fetch.py --local ./cmp8_交付包_v3.zip
```
脚本会下载 + 算 sha256 + `unzip -t` + 检查关键文件是否齐全，并打印下一步命令。
**它不碰任何 key，只做下载与校验。**
"""


# 改动 3：填实 cmp8_交接包.zip 的 node_id、删掉 v2 行、补上"单文件 zip"行 + 为什么不写自己地址的说明
OLD3 = """| **`cmp8_交接包.zip`** | **`454384890003597`** | **203,976** | **45 个真实文件 ← 接手方的完整工作集**：本交接文件 ×2 + METHOD ×2 + RUNBOOK ×2 + cmp8_fetch ×2 + 完整 cmp8/ 树 + rebuild/ |
| `cmp8_交接包_v2.zip` | （新文件名 ⇒ 新 node，由发包方回填） | — | = 上一个包 + 本交接文件 §4.1 回填（node_id 改动 3） |"""
NEW3 = """| **`cmp8_交接包.zip`** | **`454384890003597`** | **203,976** | **45 个真实文件 ← 接手方的完整工作集**：本交接文件 ×2 + METHOD ×2 + RUNBOOK ×2 + cmp8_fetch ×2 + 完整 cmp8/ 树 + rebuild/（p0/p1/p2 + patch_or.py + patch_runbook.py + patch_handover.py + rebuild.sh） |
| `HANDOVER-cmp8-2026-10-20.zip` | 见发包方消息（drive 节点随抽取延迟出现） | ~13.4 KB | **只含本文件一个 md**（`-j` 压平、无目录层级）⇒ **要转手给下一个 Agent 时的最小单文件** |

> ⚠️ **为什么本文件里不写「最新那个 zip」的 node_id**：
> 一个包含自己地址的文件**无法自洽** —— 填进 node_id 会改文件、改文件会改 zip、改 zip 就换了 node_id ⇒ 无限回环。
> ⇒ **本文件只引用地址稳定的包**（`454382563336916` / `454384890003597`）；
> 「只含本文件的单文件 zip」的地址**写在发包方的消息里**，不写进文件内部。
> 这不是遗漏，是**故意的**。"""



# --- 改动 4：§0 后加「接手前 10 分钟」清单 ---
OLD4 = """---

## 1. 项目在问什么
"""
NEW4 = """---

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
"""

# --- 改动 5：§4.2 整段换掉（说清"代码在哪"+"训练侧在哪"）---
OLD5 = """### 4.2 GitHub

- 公开仓：`https://github.com/lixvanran/agent-creativity-mechanism-study`
- 本项目相关文件：`creativity_lab/{ops,verify,client,metrics}.py`（+ 本次新增的 `orclient.py` / `learnarch.py` / `adhd_repro.py` / `data/user4_q*`）、
  报告 `TRAINING-METHOD-REPORT.md`、`docs/CORRECTION-2026-10-18-breadth.md`、`POSTMORTEM.md`、`FINDINGS.md`
- 近期 HEAD `e012f1e`（**含 v3 架构学习的 `ops.py` / `train_policy.py` / `REPORT-ARCHLEARN-2026-10-19.md`**）
- **接手者入口（本次新增）**：`HANDOVER-cmp8-2026-10-20.md`（仓库根）＋ `docs/cmp8/{HANDOVER,METHOD,AGENT_RUNBOOK}.md`
"""
NEW5 = """### 4.2 GitHub（**代码与数据的主战场**）

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
"""


# =====================================================================
# 改动 6：接收者视角自查的 10 处（2026-10-20 17:30）
# 每条都有独立的幂等标记；锚点对不上就报错，不静默跳过。
# =====================================================================
EDITS6 = []


def E(mark, old, new, tag):
    EDITS6.append((mark, old, new, tag))


# 6-1a §4.1 标题 + 取用优先级
E("zip 只是快照，GitHub 才是权威",
  "### 4.1 交付包（**主资产**）",
  """### 4.1 交付包（**zip 只是快照，GitHub 才是权威**）

**⚠️ 取用优先级（按这个来，别按文件新旧猜）**：
1. **GitHub 分支 `cmp8-handover-2026-10-20`** = **权威副本**，永远是最新的（版本受控、可 diff、可回滚）
2. **drive 的 zip** = **某一时刻的快照**，可能比 GitHub 旧
3. 本文件（md）= **索引**，指向上面两者

⚠️ **下表里 node `454384890003597`（203,976 B）那个 zip 是较早的快照**，**它的副本里可能没有 §0.5 / §4.2 / §4.2.1 这几段**。
⇒ **要最新 ⇒ clone GitHub 分支，别用 zip。**""", "6-1a 标题+优先级")

# 6-1b 交接包.zip 行：标注快照
E("**（快照，可能略旧于 GitHub）**",
  "| **`cmp8_交接包.zip`** | **`454384890003597`** | **203,976** | **45 个真实文件 ← 接手方的完整工作集**：本交接文件 ×2 + METHOD ×2 + RUNBOOK ×2 + cmp8_fetch ×2 + 完整 cmp8/ 树 + rebuild/（p0/p1/p2 + patch_or.py + patch_runbook.py + patch_handover.py + rebuild.sh） |",
  "| **`cmp8_交接包.zip`** | **`454384890003597`** | **203,976** | **45 个真实文件 ← 接手方的完整工作集**：本交接文件 ×2 + METHOD ×2 + RUNBOOK ×2 + cmp8_fetch ×2 + 完整 cmp8/ 树 + rebuild/（p0/p1/p2 + patch_or.py + patch_runbook.py + patch_handover.py + rebuild.sh） **（快照，可能略旧于 GitHub）** |",
  "6-1b 交接包行标快照")

# 6-1c 单文件 zip 字节数
E("~15.1 KB", "~13.4 KB", "~15.1 KB", "6-1c 单文件字节数")

# 6-2 §3.2 状态会过期块
E("下表是写这份文件那一刻的快照",
  "### 3.2 云端跑批现状\n\n| | |\n|---|---|\n",
  """### 3.2 云端跑批现状

**⚠️ 下表是写这份文件那一刻的快照，会过期。自己查当前状态，别信这张表**：
```bash
# 在仓库 cmp8/ 下
wc -l runs/cmp8/runlog.jsonl          # 做了几次（总 84）
ls runs/cmp8/analysis.json 2>/dev/null # 存在 = 已分析完 = 有结果了
```
**状态判定**：
- `runlog` 行数 = 84 且 `analysis.json` 在 ⇒ **跑完了**，直接进 §9 P0
- 行数 < 84 ⇒ **还在跑** ⇒ **不要重跑、不要另起炉灶**（见下面的处置）
- 整条路径都不存在 ⇒ 云端没推上来 ⇒ 走 §5 本地路径

| | |
|---|---|
""", "6-2 状态自检块")

# 6-3a 执行会话行
E("你可能看不到它的消息",
  "| 执行会话 | `454370675753049`（标题「[cron] 打包五族对比实验交付包」） |",
  "| 执行会话 | `454370675753049`（标题「[cron] 打包五族对比实验交付包」）—— **同一个 Mavis 账号下的会话，你可能看不到它的消息，但产物会推到同一分支** |",
  "6-3a 执行会话行")

# 6-3b 产物行 + 不许改臂行
E("跑批期间**不许改任何臂的行为**",
  "| 产物 | `runs/cmp8/`（答案 + `runlog.jsonl` + `analysis.json`）、`runs/cmp8_mmemb/`、`compare5_report.html` |",
  "| 产物 | `runs/cmp8/`（答案 + `runlog.jsonl` + `analysis.json`）、`runs/cmp8_mmemb/`、`compare5_report.html` |\n| ⚠️ 跑批期间**不许改任何臂的行为** | 改臂 = 改处理方式 = 前后样本不可比。样本无效**只能排除 + 如实报 valid/total** |",
  "6-3b 产物行+不许改臂")

# 6-4 §0.5 第 1 步 tar 目录名
E("tar 解出来的目录名是",
  "（若本机 git CA 有问题，用 `gh api` / `https://github.com/.../archive/refs/heads/<branch>.tar.gz` 下载。）",
  "（若本机 git CA 有问题，用 `gh api` / `https://github.com/.../archive/refs/heads/<branch>.tar.gz` 下载。）\n⇒ tar 解出来的目录名是 **`agent-creativity-mechanism-study-cmp8-handover-2026-10-20/`**，要 `cd` 进去。\n⇒ **拉完先看一眼**：`ls cmp8/runs/cmp8/analysis.json` 在不在（不在 = 跑批还没完，见第 3 步）。",
  "6-4 tar 目录名")

# 6-5 §0.5 第 3 步 别自己重跑
E("不要自己重跑**（会造出第二套不可比的数据）",
  "- **只要结果** → 数据在 `cmp8/runs/cmp8/analysis.json`，判读页 `cmp8/compare5_report.html`。**不要重跑 800 次调用。**",
  "- **只要结果** → 数据在 `cmp8/runs/cmp8/analysis.json`，判读页 `cmp8/compare5_report.html`。**不要重跑 800 次调用。**\n  ⚠️ **如果 `analysis.json` 不存在 ⇒ 云端还在跑 ⇒ 不要自己重跑**（会造出第二套不可比的数据）⇒ 按 §3.2 的状态判定，或直接问用户要产物。",
  "6-5 别自己重跑")

# 6-6 §0.5 第 4 步 凭据
E("secret 自动注入",
  "- 在 Mavis 里用 `mavis secret list` 看有哪些 secret；**没有就让用户给，别硬编码**",
  "- **在 Mavis 平台内（同账号新会话）⇒ secret 自动注入**，`env | grep -iE 'minimax|openrouter'` 直接看得到\n- **在平台外（自己电脑）⇒ 必须让用户贴 key 值**，只放进环境变量，别写进脚本/文件/git\n- 在 Mavis 里用 `mavis secret list` 看有哪些 secret（**只列名字**，明文拿不到，这是设计如此）；**没有就让用户给，别硬编码、别写进文件**",
  "6-6 凭据说明")

# 6-7 §4.2.1 两份 creativity_lab
E("最容易拿错的一处：仓库里有两份",
  "### 4.3 依据包（4 份，各 16 条原子事实）",
  """### ⚠️ 4.2.1 **最容易拿错的一处：仓库里有两份 `creativity_lab/`**

| 路径 | 是什么 | 谁用 |
|---|---|---|
| `creativity_lab/`（仓库根） | **训练侧**：策略学习、核验器训练、测量脚本、题库 | 训练/复盘时用 |
| `cmp8/creativity_lab/` | **执行侧**：被测客户端、判官客户端、核验器 v4、操作集、依据包 | **跑这套对比实验时用** |

⚠️ **两边的同名文件（`verify.py` / `client.py` / `metrics.py`）可能是不同版本！**
⇒ **执行侧一律以 `cmp8/creativity_lab/` 为准**；从仓库根 import 会拿到训练侧那份，
判官就会用旧的 CHECK4（"是不是法律主张"）⇒ 在你的四道题上会误判。
⇒ **跑实验前先确认 `sys.path` 指向 `cmp8/`**（`run_compare5.py` 里的 `HERE` 已经处理好了）。

**训练侧文件清单（仓库根，204 个文件里）**：
- `creativity_lab/data/`：`legal_topics.json` / `legal_topics_v2.json`（**核验器回归集 18 题**）/
  `policy_topics.json`（**8 道政策域训练题**）/ `train_topics.json` / `topics.json`
- `creativity_lab/train_policy.py`（**产出那 14 维权重的 REINFORCE 脚本**）/
  `arch_v2.py` / `train_agent.py` / `train_selector.py` / `train_pipeline*.py`
- `creativity_lab/measure_breadth.py` / `measure_paradox2.py` / `check_breadth_validity.py` /
  `test_verifier.py` / `gate_policy.py` / `reverify_all.py` / `drill*.py` / `pilot_v2*.py`
- `creativity_lab/{workflow,scipy_free,calibration,contrasts,leakage,prompts}.py` /
  `arms/{base,direct,dual}.py` / `gates/{base,__init__}.py`

⇒ **接手者想重训权重、复核训练结论、扩题，都有现成脚本在仓库根，不用从零写。**

### 4.3 依据包（4 份，各 16 条原子事实）""",
  "6-7 §4.2.1 两份 lab")

# 6-8 §4.5 四道题题面
E("### 4.5 用户的四道题（题面在哪）",
  "用 `mavis secret list` 管理；**绝不要把 key 写进任何文件或提交**。\n\n---\n\n## 5. 命令（照抄）",
  """用 `mavis secret list` 管理；**绝不要把 key 写进任何文件或提交**。

### 4.5 用户的四道题（题面在哪）

| | |
|---|---|
| 题面定义 | **`cmp8/armdeps/topics4.py`**（`TOPICS4`，单一真相源）→ `cmp8/run_compare5.py` 优先从那里读 |
| 依据包 | `cmp8/creativity_lab/data/user4_q{1..4}.json`（各 16 条原子事实，见 §4.3） |
| 题目内容 | A1 湖北 620 分选 AI ｜ A2 公路赛战术 ｜ A3 假期作业 ｜ A4 气质量表（**A4 有确定答案**） |
| ⚠️ **禁止** | 这 4 道题**是最终外部测试集，全程不进训练**；依据包**只进判官/核验侧**，**不许进被测臂的提示词** |

---

## 5. 命令（照抄）""",
  "6-8 §4.5 四道题")

# 6-9 §6 加第 10/11 条
E("**先写预注册文件再动手**",
  "9. **429 只退避不换模型**（换模型会悄悄改掉\"模型构成\"这个变量）；**只有连续 529 才降级**，且降级要记录。",
  """9. **429 只退避不换模型**（换模型会悄悄改掉"模型构成"这个变量）；**只有连续 529 才降级**，且降级要记录。
10. **⚠️ 非要改口径怎么办（不许偷偷改）**：
    - **先写预注册文件再动手**（项目已有先例：第四组的 `PREREG_p1.md`；格式 = 假设 / 操作 / 判据 / 停止条件 / 日期）
    - 改过的口径**必须在报告里列出"改了哪一条、为什么、什么时候改的"**
    - **改完之后，这批数据前后不可比** ⇒ 要么重跑全量，要么在报告里划清界限
    - **理由不成立的改动不许做**：例「某臂解析失败率高/样本数少 ⇒ 重跑那一臂」=
      **把仪器故障当实验结论 + p-hacking**，明令禁止（与 §7 坑 2/3 同族：都是**仪器坏了却当成好结果**）
11. **不允许「跑通了就宣布成功」**：判官自检不通过 ⇒ 一切指标无效，先修仪器。""",
  "6-9 §6 口径 10/11")

# 6-10 §7 第 25 行
E("把仪器故障当成实验结论",
  "| 24 | 跨会话文件不可互传 | 挂载单向 | 我的 write → 它看得见；**它的 write → 我看不见** |",
  "| 24 | 跨会话文件不可互传 | 挂载单向 | 我的 write → 它看得见；**它的 write → 我看不见** |\n| 25 | **把仪器故障当成实验结论** | 某臂解析失败率高 / 样本数少 / 产出为空 ⇒ \"重跑那一臂\" | **样本无效只能排除 + 如实报 valid/total**；**重跑 = p-hacking**，明令禁止 |",
  "6-10 §7 坑 25")

# 6-11a P0 代码块
E("# 首选：读仓库里已推上来的产物",
  "# 云端：读打包会话的回报，或直接看 runs/cmp8/analysis.json",
  "# 首选：读仓库里已推上来的产物\ncat cmp8/runs/cmp8/analysis.json | head -100",
  "6-11a P0 代码块")

# 6-11b P0 第 7 项加 samples
E("`embed` / `census` / `samples`",
  "7. `judge_selfcheck.json`、`analysis.json` 的 `judge` / `judge_used` / `judge_same_vendor` / `embed` / `census`",
  "7. `judge_selfcheck.json`、`analysis.json` 的 `judge` / `judge_used` / `judge_same_vendor` / `embed` / `census` / `samples`",
  "6-11b P0 第7项")

# 6-11c P0 第 10 项后加两块
E("**⚠️ 报告放哪儿（别写完就散在聊天里）**",
  "10. 判读页路径（`compare5_report.html`）",
  """10. 判读页路径（`compare5_report.html`）

**⚠️ 报告放哪儿（别写完就散在聊天里）**：
- 写到 **`docs/cmp8/REPORT-cmp8-2026-XX-XX.md`**（命名带日期）⇒ **推回同一分支**（`cmp8-handover-2026-10-20` 或新开分支 + PR）
- 同时在仓库根留一份 **`REPORT-cmp8-LATEST.md`**（指向最新那份）
- 最终给用户的**必须是一份能下载的文件**（GitHub raw 链接 + drive 里的 zip 附件），不是聊天里的复述

**⚠️ 交回时必须带的东西**（少了这些，结论不能用）：
① `analysis.json` 的**原样 JSON**（不是截图/不是手抄表）
② **样本列 valid/total**（哪个臂掉了几个样本）
③ **判官自检结果**（`judge_selfcheck.json`）—— **没这个 = 判官可能整个是坏的，指标全是假的**
④ §10 的全部声明（改一个字都不行）""",
  "6-11c P0 报告放哪儿")


def patch(path):
    s = io.open(path, encoding="utf-8").read()
    orig = s

    if "454382563336916" not in s:
        if OLD1 not in s:
            raise SystemExit("✗ 锚点 1 未命中：%s" % path)
        s = s.replace(OLD1, NEW1, 1)
        print("  ✓ 改动 1：§4.1 资产表填实 node_id")
    else:
        print("  · 改动 1 已在，跳过")

    if "无限回环" not in s:
        if OLD3 not in s:
            raise SystemExit("✗ 锚点 3 未命中：%s" % path)
        s = s.replace(OLD3, NEW3, 1)
        print("  ✓ 改动 3：§4.1 填实 node_id + 删 v2 行 + 补单文件行与自洽说明")
    else:
        print("  · 改动 3 已在，跳过")

    if "454382563336916      # 需本机有 mavis CLI" not in s:
        if OLD2 not in s:
            raise SystemExit("✗ 锚点 2 未命中：%s" % path)
        s = s.replace(OLD2, NEW2, 1)
        print("  ✓ 改动 2：§5.0 换用 v3 的 node_id")
    else:
        print("  · 改动 2 已在，跳过")

    if "接手前 10 分钟" not in s:
        if OLD4 not in s:
            raise SystemExit("✗ 锚点 4 未命中：%s" % path)
        s = s.replace(OLD4, NEW4, 1)
        print("  ✓ 改动 4：§0.5 接手前 10 分钟清单")
    else:
        print("  · 改动 4 已在，跳过")

    if "训练侧不需要重搬" not in s:
        if OLD5 not in s:
            raise SystemExit("✗ 锚点 5 未命中：%s" % path)
        s = s.replace(OLD5, NEW5, 1)
        print("  ✓ 改动 5：§4.2 换成 GitHub 主战场版（含训练侧准确路径）")
    else:
        print("  · 改动 5 已在，跳过")

    # ---- 改动 6：10 处（逐条独立幂等）----
    applied = 0
    for mark, old, new, tag in EDITS6:
        if mark in s:
            continue
        if old not in s:
            raise SystemExit("✗ 改动 6 锚点未命中：%s" % tag)
        s = s.replace(old, new, 1)
        applied += 1
    if applied:
        print("  ✓ 改动 6：应用了 %d 处（接收者视角自查 10 条）" % applied)

    if s != orig:
        io.open(path, "w", encoding="utf-8").write(s)
    return s != orig


if __name__ == "__main__":
    for p in (sys.argv[1:] or ["HANDOVER-cmp8-2026-10-20.md"]):
        print("patch_handover:", p)
        patch(p)
    print("done")
