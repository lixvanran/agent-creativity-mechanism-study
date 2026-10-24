# 第四组 · v6 Stage-1 交付包 · 复现说明

**基准 commit**：`21984e002f209600affcaca5e2307f0d0356218d`（分支 `feature/g4-arch4-state-driven`）
**sha256 校验台账**：`group4_state_driven/SHASUMS.md`（★ 对外请以「sha256 + 基准 commit」成对给）

---

## 1. ★ 三种"可复现"的级别（★ 别混为一谈）

| ★ 级别 | ★ 做什么 | ★ 本包能做到吗 |
|:-:|---|---|
| ★ **L1 · 读数可复核** | ★ 用包内原始样本 + 分析脚本**重算**出报告里的每个数字 | ★ **✅ 能**（★ 见 §3） |
| ★ **L2 · 流程可重跑** | ★ 用包内 runner **重新跑一遍**产生新样本 | ★ ⚠️ **需要额外依赖**（★ 见 §4） |
| ★ **L3 · 逐位可复现** | ★ 同 seed 重跑得到**逐字节相同**的输出 | ★ **❌ 不能**（★ seed 未落盘 ⇒ ★ 详见 `EXEC_LOG_stage1.md` §6 局限表第 4 条） |

★ **★ 明确说清：★ 本包达得到 L1，★ 达不到 L3** ⇒ ⇒ ★ **对外引用本批读数时，★ 请写"可复核"而不是"可复现"**。

---

## 2. ★ 包内容清单

### 2.1 读数与派生（★ L1 所需，★ 全在包内）
| ★ 文件 | ★ 内容 |
|---|---|
| ★ `group4_state_driven/data/arch6_stage1.jsonl` | ★ **原始样本**（9 行 = 3 题 × 3 重复） |
| ★ `group4_state_driven/data/arch6_stage1_analysis.json` | ★ **分析输出**（★ 与原始样本行数一致） |
| ★ `group4_state_driven/data/calllog.jsonl` | ★ 逐次 API 调用（★ ★ **已知不完整**，★ 见 §5） |
| ★ `group4_state_driven/data/env_snapshot.json` | ★ G0-1 环境快照 |
| ★ `group4_state_driven/data/duplicate_resampling.json` | ★ **重复采样处置留痕** |

### 2.2 报告与记录
| ★ 文件 | ★ 内容 |
|---|---|
| ★ `group4_state_driven/REPORT_arch6_stage1.md` | ★ Stage-1 报告（★ **数字全部由脚本从 analysis.json 填入** ⇒ 不许手改） |
| ★ `group4_state_driven/EXEC_LOG_stage1.md` | ★ 执行记录 + rev1 语义影响自核 + 「规格有洞」三行 |
| ★ `group4_state_driven/SHASUMS.md` | ★ sha256 台账（★ 绑 commit） |

### 2.3 代码与预注册
| ★ 文件 | ★ 内容 |
|---|---|
| ★ `group4_state_driven/prereg/PREREG_v6.md` | ★ **预注册 v3**（★ 判决口径的来源） |
| ★ `group4_state_driven/prereg/STAGE1_SPEC.md` | ★ Stage-1 实施规格 |
| ★ `group4_state_driven/code/analyze_arch6.py` | ★ 分析脚本（★ **从 scores 重算排序**） |
| ★ `group4_state_driven/code/v6_power.py` | ★ 检出力计算（★ analyze 的依赖） |
| ★ `group4_state_driven/code/run_arch6_stage1.py` | ★ Stage-1 runner |
| ★ `group4_state_driven/code/workflow_arch5.py` / `workflow_arch6.py` | ★ 机制层（★ State5 与选择器） |
| ★ `group4_state_driven/code/api_any.py` | ★ API 适配层 |
| ★ `group4_state_driven/code/run_arch5_compare.py` / `run_arch3_compare.py` / `run_multitopic.py` | ★ runner 的依赖链 |

### 2.4 工具（★ 本轮新增）
| ★ 文件 | ★ 作用 |
|---|---|
| ★ `group4_state_driven/verify_report_stage1.py` | ★ **报告机械校验 69 项**（★ 数字与数据逐字比对） |
| ★ `group4_state_driven/sync_stage1_data.py` | ★ 产物同步 + **派生/原始行数一致性检查** |
| ★ `group4_state_driven/fix_duplicate_resampling.py` | ★ 重复采样处置（★ 显式留痕） |
| ★ `group4_state_driven/fill_report_stage1.py` / `..._verdict.py` | ★ 报告填数（★ §3 / §4–§6） |
| ★ `group4_state_driven/build_shasums.py` | ★ 重建 sha256 台账 |
| ★ `group4_state_driven/probe_stage1_step_timing.py` | ★ 逐步打点探针（★ 定位"慢"而非"卡"） |

---

## 3. ★ L1：读数复核（★ 三条命令，★ 全在包内可跑）

```bash
# ★ ① 重算分析（★ 会写 arch6_stage1_analysis.json 到同目录）
cd group4_state_driven/code
python3 -B analyze_arch6.py ../data/arch6_stage1.jsonl

# ★ ② 校验报告（★ 69 项机械核对）
cd <包根>
python3 -B group4_state_driven/verify_report_stage1.py

# ★ ③ 核 sha256
sha256sum group4_state_driven/REPORT_arch6_stage1.md   # 与 SHASUMS.md 比对
```

★ **★ 注意 ① 的坑**：★ `analyze_arch6.py` 会把结果写到 **它自己所在目录**的 `runs/` 下
★ ⇒ ⇒ ★ **在 `code/` 目录跑会写到 `code/runs/`**（★ 不覆盖包内 `data/` 里的那份）⇒ ⇒ ★ **这是刻意的**
★ ⇒ ⇒ ★ **★ 你跑完请把 `code/runs/arch6_stage1_analysis.json` 与 `data/` 里的那份比对** ⇒ ★ **两者应逐字节相同**
★ ⇒ ⇒ ★ （★ 若不同 ⇒ ★ **说明分析脚本变了** ⇒ ★ **请以 git commit 为准核对**）。

---

## 4. ★ L2：流程重跑（★ 需要额外依赖，★ 已在 §4.2 列出）

```bash
export OPENROUTER_BASE_URL="https://api.minimaxi.com/v1"
export MINIMAX_SUBSCRIPTION_KEY=<你的 key>
export G4_REF_DIR=<三组代码所在目录>       # ★ 见 §4.2
cd <包根>/group4_state_driven/code
python3 -B run_arch6_stage1.py --topics G01,T07,T10 --reps 1,2,3 \
        --batch-id <你的批号> --out runs/arch6_stage1.jsonl
```

### 4.2 ★★ 外部依赖（★ ★ 不在包内，★ 必须自备 ★ ★）
| ★ 依赖 | ★ 来源 | ★ 校验 |
|---|---|---|
| ★ **三组 Gate 与 client** | ★ 仓 `lixvanran/agent-creativity-mechanism-study` 的 `creativity_lab/gates/base.py` 与 `creativity_lab/client.py` | ★ `base.py` blob `3f4f926604`，★ **md5 `400d27894a7716085c594ef5e603065b`** |
| ★ **MiniMax 订阅 key** | ★ secret `MINIMAX_SUBSCRIPTION_KEY` | ★ — |
| ★ **题面** | ★ `run_arch6_stage1.py` 内的 `TOPICS` 常量（★ G01/T07/T10 三题） | ★ — |

★ **★ 注意（★ 一条真实的坑）**：★ `creativity_lab/client.py:14` 的 `BASE` 读 `OPENROUTER_BASE_URL`
★ ⇒ ⇒ ★ **必须在 import 之前钉住这个环境变量**（★ runner 已在 `G0-1` 做了这件事，★ 自跑时也要做）。

### 4.3 ★★ 重跑【不等于】复现（★ 三条已知的口径问题）
| ★ 问题 | ★ 后果 | ★ 修法（★ Stage-2 前必修） |
|---|---|---|
| ★ **seed 未落盘** | ★ 不可逐位复现 | ★ 落盘 seed |
| ★ **候选生成不关 thinking** | ★ 单样本成本被重试放大约 3 倍（★ 实测 `reasoning_tokens` 吃满 3200 ⇒ 截断 ⇒ 重试 ×1.8） | ★ 结构化输出关 thinking |
| ★ **runner 无「跳过已存在单元」** | ★ `--append` 只补最后一次那个 rep ⇒ ★ **n 悄悄变小** | ★ 单元级落盘 + 续跑按单元 skip |
| ★ **`_with_watchdog` 超时后 daemon 线程仍活着** | ★ 继续发调用（★ 白烧额度）+ 同文件双写风险 | ★ 超时后中断请求或子进程隔离 |

---

## 5. ★★ 已知缺口（★ 必须随交付一起给，★ 不许只给好读的）

| ★ 缺口 | ★ 说明 |
|---|---|
| ★ **calllog 不完整** | ★ 补跑段的调用未落盘（★ 进程在 `dump_calllog()` 之前被终止）⇒ ★ **通道健康度的分母不完整** ⇒ ★ **凡用 calllog 算健康度的结论本批不成立** |
| ★ **seed 未落盘** | ★ 不可按 seed 复现（★ L3 达不到） |
| ★ **重复采样已处置** | ★ T10-1 出现两次（★ 两进程并发写）⇒ ★ 后写入者重标记为 T10-2 ⇒ ★ 每题恰好 3 个重复 ⇒ ★ 留痕 `data/duplicate_resampling.json` |
| ★ **人工标注量 = 0；无跨厂商判官** | ★ OpenRouter key 级额度耗尽 ⇒ ★ **本批全部读数是零判官的结构量** ⇒ ★ **不能替代人类质量判断** |
| ★ **取舍轴题量 = 0** | ★ **测不了 2×2 交互项（H1c）** |

---

## 6. ★ 判决（★ 口径全部来自预注册，不是事后解释）

| ★ 预注册条款 | ★ 实测 | ★ 判定 |
|---|---|---|
| ★ Stage-2 门① Stage-0 四门全过 | ★ 四门全过 | ★ **过** |
| ★ Stage-2 门② 排序改变率显著 > 0 | ★ 3/9，CI [0.121, 0.646] 含 0.25 | ★ **不过** ⇒ **不造题、不跑批 Stage-2** |
| ★ Stage-2 门③ 实测 σ 下 power ≥ 0.8 | ★ σ_new = 0.2299 ⇒ n=25 时 power@0.15 = 0.371 | ★ **不过** |
| ★ Stage-2 门④ 题的两轴筛选 | ★ 取舍轴题量 = 0 | ★ **未开始** |
| ★ 终局条款③ MDE(80%) ≤ 0.15 | ★ n=25 时 MDE = 0.2576 | ★ **不满足** ⇒ **按预注册：不触发收摊，只报「检出力不足」** |

⇒ ⇒ **判决：【不可分辨】**
⇒ ⇒ ★ **★ 但定位比"不可分辨"更具体：★ 失败位置收窄到「候选池没有可排的差异」，★ 而不是「状态没进选择器」**
⇒ ⇒ ★ ★ **证据：★ 对照端（B）有区分力的单元仅 1/9；★ 但两处改变都是真改变（G01-3/T10-1 = 代价【创造】区分；T07-2 = 代价【改变】既有排序）**
