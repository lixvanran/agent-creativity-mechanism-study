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



# =====================================================================
# 改动 7：第二轮「可执行性」自查 8 处（2026-10-20 17:40）
# =====================================================================
EDITS7 = []


def E7(mark, old, new, tag):
    EDITS7.append((mark, old, new, tag))


E7("17:30 修订：接收者视角自查后补 19 处",
   "> 生成：2026-10-20 16:50 Asia/Shanghai\n> 状态：核心装置已交付并自检通过；**主对比实验正在云端跑**，本文件随实验结果更新。",
   "> 生成：2026-10-20 16:50 Asia/Shanghai（**17:30 修订：接收者视角自查后补 19 处**）\n> 状态：核心装置已交付并自检通过；**主对比实验正在云端跑**，本文件随实验结果更新。\n>\n> **本文件是索引，不是唯一真相** —— 最新版以 **GitHub 分支 `cmp8-handover-2026-10-20`** 为准（§4.1/§4.2）。",
   "7-1 头部")

E7("| **这项目在多组研究里的位置** | **§0.9** |",
   "| 这项目在问什么 | §1 |",
   "| 这项目在问什么 | §1 |\n| **这项目在多组研究里的位置** | **§0.9** |",
   "7-1b 30秒表")

E7("## 0.9 这项目在多组研究里的位置",
   "## 1. 项目在问什么",
   """## 0.9 这项目在多组研究里的位置（**接手者先看这段，否则会问"这结论凭什么可信"**）

本项目是「Agent 洞察力机制」研究里的**第四组（论证组）**。四组并行、各自独立：

| 组 | 在干什么 | 产出 |
|---|---|---|
| 一组 | 文献审计（ADHD × 创造力） | 结论：「ADHD 整体提高创造力」**未通过证据审计** |
| 二组 | multi-mind 多 Agent 协作平台工程 | 五层创造力机制 L1–L5、lean 流水线 |
| 三组 | 机制实证（公开仓） | 训练/巡练相关证据链 |
| **四组（本组）** | **论证 + 架构学习 + 这套对比实验** | 本文件 + `cmp8/` |

**本组已经确立的三件事（§2.1 有完整表）**：
1. **写作增强是真实的** —— 双轴**去融合门**（各分支各自成文）让开放文章**逃逸度 0.0377 → 0.1048（2.8×）**，
   跨重复离散度从 0.9786 降到 0.7006。**这是正面成果，要保留。**
2. **但"逃逸度 2.8×"后来被证伪**（~90% 置信）—— 它只是个重加权指标，**不是**独立的能力度量（§2.2）。
3. **架构学习学到的是"更谨慎地核验"，不是"探索更多"** —— v3 留出集：矛盾率 33.3% → 0.0%，
   但宽度没变（1.33 → 1.33）。**⇒ 目标函数应该是「少说错」而不是「多想到」。**

⚠️ **所以这套对比实验的胜负手不是"谁的答案是空的"，而是"谁在**不打架**的前提下覆盖更多"。**
唯一仲裁器 = **矛盾率**（§2.3 记录了为什么放弃其他量当仲裁器）。

---

## 1. 项目在问什么""",
   "7-2 §0.9")

E7("**答案文件命名**",
   "| 产物 | `runs/cmp8/`（答案 + `runlog.jsonl` + `analysis.json`）、`runs/cmp8_mmemb/`、`compare5_report.html` |",
   "| 产物 | `runs/cmp8/`（答案 + `runlog.jsonl` + `analysis.json`）、`runs/cmp8_mmemb/`、`compare5_report.html` |\n| **答案文件命名** | **`{题号}_r{重复号}_{臂}.md`** —— 例：`A3_r1_A4.md` = 第 3 题 / 第 1 次重复 / A4 臂。**84 个文件 = 4 题 × 3 重复 × 7 臂**。空文件（0 字节）= 该样本无效，**排除 + 如实报 valid/total** |",
   "7-3 答案命名")

E7("# ★ 唯一第三方依赖",
   "pip install numpy                        # 唯一第三方依赖",
   """pip install numpy                        # ★ 唯一第三方依赖

**依赖只有 numpy + Python 标准库**（已核）：`client.py` / `orclient.py` 用 `urllib.request`（**不用 requests**）；
`creativity_lab/scipy_free.py` 是**刻意避开 scipy** 的实现 ⇒ **不要 `pip install scipy`，也不要改这些文件去 import scipy**。
（看到 `import requests` 报错？那是你改错文件了。）""",
   "7-4 依赖块")

E7("### 5.2 ★ 两条路径，**目录名不一样，别混**",
   """### 5.2 重建 + 静态自检
```bash
cd cmp8pkg && bash rebuild/rebuild.sh
for f in $(find . -name "*.py"); do python3 -m py_compile "$f" || echo "FAIL: $f"; done
```
""",
   """### 5.2 ★ 两条路径，**目录名不一样，别混**

**路径 A · GitHub（推荐，最快）**
```bash
git clone https://github.com/lixvanran/agent-creativity-mechanism-study.git
cd agent-creativity-mechanism-study
git fetch origin cmp8-handover-2026-10-20 && git checkout cmp8-handover-2026-10-20
cd cmp8                      # ★ 目录叫 cmp8
# ↓ 树已经是打好补丁的，**直接往下走 §5.3，不要跑 rebuild.sh**
```

**路径 B · zip（无 git / CA 坏了）**
```bash
unzip cmp8_交接包.zip         # 解压出来的根目录叫 cmp8pkg
cd cmp8pkg
bash rebuild/rebuild.sh       # ★ 只有这条路径才需要重建
```

> **⚠️ `rebuild.sh` 是"从还原脚本重建"的路径，不是"准备环境"的路径。**
> GitHub 树**已经打好补丁**，再跑 `rebuild.sh` 等于用 p0/p1/p2 重写一遍文件（补丁脚本幂等，最后会补回来，
> 但**没必要、且多一次把好树写坏的机会**）。
> ⇒ **路径 A 不要跑 rebuild.sh**；路径 B 必须跑（否则默认模型还是已下架的 `grok-3-mini`）。

**静态自检（两条路径都做）**
```bash
for f in $(find . -name "*.py"); do python3 -m py_compile "$f" || echo "FAIL: $f"; done
```
⚠️ **编译过 ≠ 能跑**：`py_compile` 只查语法，查不出**运行时才炸**的错（历史坑：`learnarch.py` 用了
`time.sleep` 却漏 `import time` ⇒ 只在异常路径触发，指向完全无关的位置）。
⇒ 编译过之后**至少跑一次 §5.3 冒烟**，再跑一次单臂小样（§5.4 的 `--arms A1 --reps 1 --workers 1`）。
""",
   "7-5 §5.2 重写")

E7("判官整个坏掉时，指标会呈现",
   "```bash\npython3 smoke_or.py\n```\n**通过标准：判官自检「真断言 ≥3/4 且 假断言 ≥3/4」。不过 ⇒ 不要跑批，直接回报。**",
   "```bash\npython3 smoke_or.py\n```\n**通过标准：判官自检「真断言 ≥3/4 且 假断言 ≥3/4」。不过 ⇒ 不要跑批，直接回报。**\n⚠️ **别跳过这步**：判官整个坏掉时，指标会呈现\"全 0 矛盾率\"的**完美假象**（§7 坑 2/3）。",
   "7-6 §5.3 警告")

E7("**实测 ≈3.5–4 小时**",
   "约 1.5–2 小时。**`--workers 4` 不要调高**（8 并发实测触发 429 整片失败）。**中途不要重跑**（跨批次重复会污染统计）。",
   """**实测 ≈3.5–4 小时**（总 84 个臂样本、≈800 次调用、~33 s/次 ÷ 4 并发；**A5 三臂偏慢，实测 491–734 s/臂样本** ⇒ 是总时长的主要来源）。
**`--workers 4` 不要调高**（8 并发实测触发 429 整片失败）。**中途不要重跑**（跨批次重复会污染统计）。
⚠️ **跑批期间不许改任何臂的行为**（§6 第 10 条：改臂 = 改处理方式 = 前后样本不可比）。""",
   "7-7 §5.4 耗时")

E7("判官与被测同源 ⇒ 指标就废了",
   "CMP_OUT=runs/cmp8_mmemb EMBED_PROVIDER=minimax python3 analyze_cmp6.py   # 遍2：embo-01（0.75 的标定基准）\npython3 build_compare5_page.py\n```",
   """CMP_OUT=runs/cmp8_mmemb EMBED_PROVIDER=minimax python3 analyze_cmp6.py   # 遍2：embo-01（0.75 的标定基准）
python3 build_compare5_page.py
```

⚠️ **遍 1 如果 OpenRouter 不通，`judge_provider.py` 会自动退到 MiniMax**（并打大字警告）⇒
**判官与被测同源 ⇒ 指标就废了**。⇒ **必须检查 `analysis.json` 的 `judge_same_vendor` / `judge_used` / `embed`
三个字段**，并在报告里声明（§10 第 3 条）。**不许悄悄用同源结果。**""",
   "7-8 §5.5 同源警告")



# =====================================================================
# 改动 8：第四轮「交叉核对已知事实」4 处（2026-10-20 17:45）
#   核心问题：「A4 掉样本」这件事只以"规则"出现过（掉样本要标样本数），
#   从没以"事实"被记录 ⇒ 而 §3.2 的状态快照会过期 ⇒ 接手的人根本不会知道。
# =====================================================================
EDITS8 = []


def E8(mark, old, new, tag):
    EDITS8.append((mark, old, new, tag))


# 8-1 §3.1 臂表加「已知异常」列
E8("| 臂 | 是什么 | 调用数 | 作用 | 已知异常 |",
   """| 臂 | 是什么 | 调用数 | 作用 |
|---|---|:-:|---|
| **A1** | 直调 | 1 | 基线 |
| **A2** | 开源 ADHD 项目（**机制复现**） | 11–12 | 外部项目对照 |
| **A3** | 双轴·**融合门** | 8 | 旧架构 |
| **A4** | 双轴·**去融合门** | 6 | 旧架构最强版 |
| **A5a** | 新架构·**无核验** | ~12 | 控制：隔离 oracle |
| **A5b** | 新架构·**学到的策略** | ~14 | **主实验** |
| **A5c** | 新架构·**初始 w=0** | ~14 | 控制：隔离权重 |""",
   """| 臂 | 是什么 | 调用数 | 作用 | 已知异常 |
|---|---|:-:|---|---|
| **A1** | 直调 | 1 | 基线 | |
| **A2** | 开源 ADHD 项目（**机制复现**） | 11–12 | 外部项目对照 | **原版通道死**（claude-agent-sdk 挂死）⇒ 走复现，见 §10-1 |
| **A3** | 双轴·**融合门** | 8 | 旧架构 | |
| **A4** | 双轴·**去融合门** | 6 | 旧架构最强版 | ⚠️ **掉 1 样本（11/12）** ⇒ 离散度须标样本数 |
| **A5a** | 新架构·**无核验** | ~12 | 控制：隔离 oracle | |
| **A5b** | 新架构·**学到的策略** | ~14 | **主实验** | |
| **A5c** | 新架构·**初始 w=0** | ~14 | 控制：隔离权重 | |""",
   "8-1 臂表加已知异常列")

# 8-2 §3.2 表格加「已知异常」行
E8("★ **已知异常（截至 2026-10-20 17:39）**",
   "| ⚠️ 跑批期间**不许改任何臂的行为** | 改臂 = 改处理方式 = 前后样本不可比。样本无效**只能排除 + 如实报 valid/total** |",
   """| ⚠️ 跑批期间**不许改任何臂的行为** | 改臂 = 改处理方式 = 前后样本不可比。样本无效**只能排除 + 如实报 valid/total** |
| ★ **已知异常（截至 2026-10-20 17:39）** | **① A4 掉了 1 个样本**（`A3_r1_A4.md` = 0 字节）⇒ A4 是 **11/12**，其余臂全满。**A4 是"去融合门离散度更低"这个正面结论的载体** ⇒ 它掉样本 ⇒ 方差更大 ⇒ **它的离散度必须标样本数，不许给"单点值 + 假装同精度"的读法**。**② 臂2 原版通道死**（`Claude Code process exited with code 1`，1200s 零输出）⇒ 走 Python 复现（见 §10 第 1 条的三处差异）。**③ 无整臂 0 字** |""",
   "8-2 §3.2 已知异常行")

# 8-3a 自己查代码块加 samples 步骤
E8("★ 还要查每臂的样本数",
   "ls runs/cmp8/analysis.json 2>/dev/null # 存在 = 已分析完 = 有结果了\n```",
   """ls runs/cmp8/analysis.json 2>/dev/null # 存在 = 已分析完 = 有结果了
# ★ 还要查每臂的样本数（在 analysis.json 的 samples 字段里）：
python3 -c "import json;d=json.load(open('runs/cmp8/analysis.json'));print(d.get('samples'))"
```""",
   "8-3a 代码块加 samples")

# 8-3b 状态判定加一条
E8("`samples` 里任何 `valid < total`",
   "- 整条路径都不存在 ⇒ 云端没推上来 ⇒ 走 §5 本地路径",
   """- 整条路径都不存在 ⇒ 云端没推上来 ⇒ 走 §5 本地路径
- **`samples` 里任何 `valid < total` ⇒ 该臂有样本被排除** ⇒ 它的离散度**必须标样本数**（见下面的「已知异常」）""",
   "8-3b 状态判定加一条")

# 8-4 附录加「推 GitHub 分支后必须复核 ref HEAD」
E8("推 GitHub 分支后，必须复核 ref HEAD",
   """- **自己写的代码必须让自己以外的东西跑一遍**（兄弟会话、外部审计者都算）。
  本项目今天就靠这条抓出了 `cmp8_p0.py` 的 raw-string 未闭合（在我自己机器上永远跑不出来）。""",
   """- **自己写的代码必须让自己以外的东西跑一遍**（兄弟会话、外部审计者都算）。
  本项目今天就靠这条抓出了 `cmp8_p0.py` 的 raw-string 未闭合（在我自己机器上永远跑不出来）。
- ★ **推 GitHub 分支后，必须复核 ref HEAD**（2026-10-20 实测踩坑）：
  `PATCH /git/refs/heads/<branch>` **可能静默失败**（不报错、返回 200-ish 但没生效）⇒
  **commit 建好了，分支 ref 却停在旧 SHA** ⇒ 仓库看起来"是好的"（旧版但完整），**实际没更新**。
  ⇒ **纪律**：① `PATCH` 的响应体**必须检查**；② 推完 `GET /git/ref/heads/<branch>`，
  把返回的 SHA 和目标 commit **逐字比对**，不一致就重推。
  ⇒ **别用 `raw.githubusercontent.com` 做校验**（**有 CDN 缓存**，会给你旧内容）——
  用 API：`/git/ref/heads/<branch>`、`/git/trees/<sha>?recursive=1`、`/contents/<path>?ref=<branch>`。""",
   "8-4 附录加推分支纪律")



# =====================================================================
# 改动 9：第五轮「两份必留声明清单对齐」5 处（2026-10-20 17:50）
#   核心问题：METHOD §7（7 条）与 HANDOVER §10（8 条）互有缺漏 ⇒
#   接收者照哪份抄就漏另一份。⇒ 两边统一成 9 条，逐条对应。
# =====================================================================
EDITS9 = []


def E9(mark, old, new, tag):
    EDITS9.append((mark, old, new, tag))


# 9-a §10 标题下插入说明段
E9("本清单与 `METHOD.md` §7 是同一份（9 条，逐条对应）",
   """## 10. 最终报告**必须**保留的声明

1. **臂2 是机制复现，不是原版本体**。""",
   """## 10. 最终报告**必须**保留的声明

> ⚠️ **本清单与 `METHOD.md` §7 是同一份（9 条，逐条对应）。**
> 抄报告声明时**两边对一遍**，别只抄一份 —— 漏一条就是一个漏洞。
> （METHOD §7 那版原本漏了第 4 条"依据包/外部测试集"，本文件那版原本漏了第 8 条"权重范数 0.062"，
> **两份都已补齐，现在逐条一致**。）

1. **臂2 是机制复现，不是原版本体**。""",
   "9-a §10 说明段")

# 9-b 第 2 条补 429/529
E9("**429 只退避不换模型；只有连续 529 才降级。**",
   """2. **模型集被固定为 5 个健康档位**（M3.1-Flash-Preview / M2.7 / M2.5 / M2.1 / M2），各臂完全一致
   —— 因为 M3 当天整片返回 529 过载。""",
   """2. **模型集被固定为 5 个健康档位**（M3.1-Flash-Preview / M2.7 / M2.5 / M2.1 / M2），各臂完全一致
   —— 因为 M3 当天整片返回 529 过载。**429 只退避不换模型；只有连续 529 才降级。**""",
   "9-b 第2条 429/529")

# 9-c 第 3 条
E9("""3. **判官是跨厂商的**（被测 MiniMax、判官 deepseek/grok）；**若退到 MiniMax 则同源，必须声明**
   （`analysis.json` 的 `judge_same_vendor`）。""",
   "3. **判官是跨厂商的**（被测 MiniMax、判官 deepseek/grok）；**若退到 MiniMax 则同源，必须声明**。",
   """3. **判官是跨厂商的**（被测 MiniMax、判官 deepseek/grok）；**若退到 MiniMax 则同源，必须声明**
   （`analysis.json` 的 `judge_same_vendor`）。""",
   "9-c 第3条")

# 9-d 第 4 条
E9("**依据包只进判官/核验侧，不进被测臂的提示词。**",
   "4. **用户的四道题是外部测试集**，全程未进训练；依据包由子代理联网独立构造，**不读任何已有答案**、只收原子事实、不收建议。",
   """4. **用户的四道题是外部测试集，全程未进训练**；依据包由子代理联网独立构造，**不读任何已有答案**、只收原子事实、不收建议。
   **依据包只进判官/核验侧，不进被测臂的提示词。**""",
   "9-d 第4条")

# 9-e 第 8 条 → 8 + 9
E9("A5b 权重范数仅 0.062",
   "8. **最终评分由人做。**",
   """8. **A5b 权重范数仅 0.062**，ε-greedy 的随机加分（0–2.0）比策略信号（最大 ~0.09）**大 20 倍**
   ⇒ **⑤b vs ⑤c 的差异极可能只是噪声** ⇒ **必须与种子噪声地板对照**；超不过写「**不可分辨**」。
9. **最终评分由人做**（判读页给的是原始答案，指标只是辅助）。""",
   "9-e 第8+9条")



# =====================================================================
# 改动 10：第六轮「把抓到的坑写进坑表」1 处（2026-10-20 17:55）
#   幂等 marker 太泛 ⇒ 静默漏改（本轮实战踩到：9-c 的 marker 在 §2.3 也有）
# =====================================================================
EDITS10 = []


def E10(mark, old, new, tag):
    EDITS10.append((mark, old, new, tag))


E10("幂等 marker 写得太泛 ⇒ 静默漏改",
    """| 25 | **把仪器故障当成实验结论** | 某臂解析失败率高 / 样本数少 / 产出为空 ⇒ "重跑那一臂" | **样本无效只能排除 + 如实报 valid/total**；**重跑 = p-hacking**，明令禁止 |""",
    """| 25 | **把仪器故障当成实验结论** | 某臂解析失败率高 / 样本数少 / 产出为空 ⇒ "重跑那一臂" | **样本无效只能排除 + 如实报 valid/total**；**重跑 = p-hacking**，明令禁止 |
| 26 | ★ **幂等 marker 写得太泛 ⇒ 静默漏改** | marker 用了"新文本里某个短语"，而这个短语**在文件别处也出现** ⇒ 脚本误判"已打过"而**跳过这一处** | marker 必须是**新文本里独有的整段**（不是某个短语）；**改完必须用独立校验脚本逐条比对**，不能只看脚本自己说"applied" |""",
    "10-1 坑表第26行")


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

    # ---- 改动 10：1 处（幂等）----
    applied10 = 0
    for mark, old, new, tag in EDITS10:
        if mark in s:
            continue
        if old not in s:
            raise SystemExit("✗ 改动 10 锚点未命中：%s" % tag)
        s = s.replace(old, new, 1)
        applied10 += 1
    if applied10:
        print("  ✓ 改动 10：应用了 %d 处（坑表第 26 行）" % applied10)

    # ---- 改动 9：5 处（逐条独立幂等）----
    applied9 = 0
    for mark, old, new, tag in EDITS9:
        if mark in s:
            continue
        if old not in s:
            raise SystemExit("✗ 改动 9 锚点未命中：%s" % tag)
        s = s.replace(old, new, 1)
        applied9 += 1
    if applied9:
        print("  ✓ 改动 9：应用了 %d 处（两份必留声明对齐）" % applied9)

    # ---- 改动 8：4 处（逐条独立幂等）----
    applied8 = 0
    for mark, old, new, tag in EDITS8:
        if mark in s:
            continue
        if old not in s:
            raise SystemExit("✗ 改动 8 锚点未命中：%s" % tag)
        s = s.replace(old, new, 1)
        applied8 += 1
    if applied8:
        print("  ✓ 改动 8：应用了 %d 处（已知事实入档 4 条）" % applied8)

    # ---- 改动 7：8 处（逐条独立幂等）----
    applied7 = 0
    for mark, old, new, tag in EDITS7:
        if mark in s:
            continue
        if old not in s:
            raise SystemExit("✗ 改动 7 锚点未命中：%s" % tag)
        s = s.replace(old, new, 1)
        applied7 += 1
    if applied7:
        print("  ✓ 改动 7：应用了 %d 处（可执行性自查 8 条）" % applied7)

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
