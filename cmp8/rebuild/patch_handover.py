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

    if s != orig:
        io.open(path, "w", encoding="utf-8").write(s)
    return s != orig


if __name__ == "__main__":
    for p in (sys.argv[1:] or ["HANDOVER-cmp8-2026-10-20.md"]):
        print("patch_handover:", p)
        patch(p)
    print("done")
