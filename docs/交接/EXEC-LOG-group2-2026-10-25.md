# EXEC-LOG · 第二组 · 2026-10-25（拓扑臂 v2 批运行中 + 2×2 规格交付 + 推送事故修复）

> 落点：`docs/交接/EXEC-LOG-group2-2026-10-25.md`
> 产出方：第二组 ｜ 本轮范围：**不跑新批**（拓扑臂 v2 正式批在后台继续跑）
> 结论句一律标【产出方自算】；设计层疑问写进 `docs/交接/KNOWN_ISSUES.md`

---

## 1. 本轮做了什么（三块）

| # | 块 | 交付物 | 状态 |
|---|---|---|---|
| ① | 共享件抽出 | `tools/push_norm.py`、`tools/verify_remote_overlay.py`、`creativity_lab/experiments/h0_report.py` | 已推 + 独立复核 9 项全过 |
| ② | A 篇 2×2 判死门规格 | `docs/交接/WORKPACK-4-saturation-2x2-spec.md`（238 行） | 已推 + 已回论文簇/第 1 层论证线 |
| ③ | ★★ 推送事故修复 ★★ | 恢复三组 31 个文件 + `push_overlay.py` 覆盖语义改造 + `KNOWN_ISSUES` KI-04 | 已推 + 逐 blob 核过 |

---

## 2. ① 共享件：关键源码（路径:行号）

### 2.1 `tools/push_norm.py`（归一化函数 + 归一化清单表）

| 项 | 位置 |
|---|---|
| 归一化清单表（表驱动，每条挂实测证据） | `tools/push_norm.py:84`（`NORMALIZERS`） |
| 条目字段 | `field` / `what` / `affects` / `not_affects` / `evidence` / `fn` |
| `norm_message` | `tools/push_norm.py:41-52`（实测证据：推 `d9b0286f9f77` 时远端回读尾部无换行） |
| `norm_date` | `tools/push_norm.py:57-70`（实测证据：推 `7006338ecc6a` 时 `+08:00` ⇒ `Z`） |
| 按字段分派 | `tools/push_norm.py:106-112`（`norm_field`） |
| 清单表渲染 | `tools/push_norm.py:114-124`（`describe`） |
| 自检 | `tools/push_norm.py:127-165`（`check_norm`） |

★ **铁律已写进文件**：「只归一化实测到的那几处」；★ **通篇 `strip()` 会掩盖真差异** ⇒ 不许做。

### 2.2 `tools/verify_remote_overlay.py`（独立远端复核）

| 项 | 位置 |
|---|---|
| ★ **刻意不 import 推送工具本体** | 文件头 docstring + 无 `import push_overlay` |
| 远端只走 API | `tools/verify_remote_overlay.py:47`（`API = "https://api.github.com"`）⇒ **git smart-HTTP 不可达不影响它**（★ 它根本不碰 `github.com` 的 git 端点 ★） |
| ★ 本地树用 NUL 分隔 | `tools/verify_remote_overlay.py:61-62`（`git ls-tree -r -z HEAD`）⇒ 非 ASCII 路径不产生假差异 |
| 树内容三数判据 | 本地有远端没有 = 0 ｜ 同路径内容不同 = 0 ｜ 远端独有全部保留 |
| commit 逐字段核对 | message 首行 / owner 行 / author / committer（含 name/email/date） |
| 归一化来源 | ★ 单一真相源 `tools/push_norm.py`（★ 不是各写一份 ★） |

★ **推后复核按推送语义给判据**：叠加语义 = **树内容一致**（不是「远端 sha == 本地 HEAD」）。

### 2.3 `creativity_lab/experiments/h0_report.py`（H0 报告）

| 项 | 位置 |
|---|---|
| 两种 q95 估计法 | nearest-rank 与 linear（同报） |
| bootstrap percentile 95% 区间 | 同报 |
| 题内 rep σ | 中位数 + 范围 |
| `X0 = q95 / √2` | 与 σ 的比值（标准化效应量） |
| 逐位可复现 | `json.dump(..., sort_keys=True)` |

---

## 3. ② A 篇 2×2 规格：原始配方出处（★ 关键：不是新造的 ★）

| 出处 | 内容 |
|---|---|
| `HANDOVER.md` §4.1 | `w_dd` / `w_ds` / 饱和度 = `w_dd − w_ds` |
| `HANDOVER.md` §4.2 | ★ 法律域 18 题：MiniMax-M3、每题 2 次采样、`w_dd` 0.936–0.996、`w_ds` 0.802–0.977、**饱和度均值 +0.0483、范围 0.0064–0.1593** |
| `HANDOVER.md` §4.3 | ★ **原始 `w_dd` 不能当确定度用**（同题不同答的余弦地板 ~0.991）⇒ 必须用差值 |
| `HANDOVER.md` §4.4 | ★ 对四道题的预期：跑出来应明显更低；`w_dd` > 0.97 ⇒ 模型有把握 |
| `creativity_lab/gate_policy.py` §4 | 饱和度实现；嵌入 `embo-01`（★ 与 +0.0483 同一把尺子 ★） |

★ 规格里列了 **5 个口径缺口**（2 个硬阻塞）：
1. ★ `dual.MODELS` 第 5 支 = **已下架的 `MiniMax-M2.1`**；`Dual.run()` 未暴露 `specs` 注入 ⇒ 5 支静默变 4 支
2. ★ 法律域 18 题的**原始文本不在本组工作区**（`runs/policy/` 不存在、全仓 `texts.json` 0 命中）⇒ 同尺子对照需重跑
3. 题数不等（18 vs 4）
4. ★ `cmp8/runs/cmp8/` 那 166 项**配置不同**（`M3.1-Flash-Preview` / `ART` 追加 / `min_ok=120` / 独立 `SELECT_ASK`）⇒ 不可直接当那格
5. 依据包取法（四道题在 `evidence` 字段，不在 `laws` 字典）

---

## 4. ③ 推送事故：完整执行记录

### 4.1 时间线（远端 commit 链可核）

| commit | 谁 | 内容 |
|---|---|---|
| `a0d539ff59` | 第二组 | 共享件 |
| `ccccfea02a` | **三组** | 31 个共享文件（parent = 我们的 `a0d539ff59`） |
| `c9ccdd7dbb8b` | 第二组 | ★ **覆盖了三组那 31 个文件**（本轮事故） |
| `9cf79f670917` | 第二组 | ★ **恢复**（32/33 与三组版本逐字节一致） |
| `5fd4da535d01` | 第二组 | KI-04 落盘；★ 修好的工具首次实跑（冲突 0） |
| `ee7949edd5d6` | **三组** | 他们的 `tools/push_guard.py` + EXEC-LOG（parent = 我们的 `5fd4da535d01`） |
| `fcc12dd03308` | 第二组 | 状态文件换名 + `.gitignore` 双方合并（★ 冲突 0 ★） |

### 4.2 恢复的核验（不是「我推完了」，是逐 blob 比对）

| 项 | 结果 |
|---|---|
| 三组 `ccccfea02a` 改动的 33 个文件 | **32 个逐字节一致** ✔ |
| 唯一差异 | `.gitignore`（三组版 + 本组两块本地忽略项） |
| 三组独有的 `docs/cmp8/PAPER-2026-10-25.md` / `docs/cmp8/KNOWN_ISSUES.md` | ★ 本地无此路径 ⇒ **全程未被触碰** ✔ |
| 远端总 blob | 935（恢复前后同量级 ⇒ 零丢失） |
| 独立复核脚本 | 9 项全过 |

### 4.3 工具修复

| 项 | 位置 |
|---|---|
| 基线参数 | `--base-commit`（`tools/push_overlay.py` 参数区） |
| 状态文件 | `.mavis/push_state.secondgroup.json`（★ 换名避让三组的 `.mavis/push_state.json` ★） |
| 只覆盖本组改过的路径 | `tools/push_overlay.py`（`our_changed` = `git diff --name-only <base> <head>`） |
| 冲突即拒 | 冲突 ⇒ 打印清单 + **exit 3**；强行覆盖须显式 `--allow-conflict` |
| 冲突检测的实测有效性 | ★ 真实场景触发过：三组改 `.gitignore`、我们没动 ⇒ 判冲突 ⇒ 拒绝覆盖 ⇒ 随后合并双方再推，冲突 0 ✔ |

### 4.4 ★★ 恢复动作本身造成 340 行回退（★ 已二次修复 ★）★★

★ **发现**：三组的 `ccccfea02a` 的 parent 就是我们的 `a0d539ff59` ⇒ ★ **他们是从我们的树改的**，
★ 而他们改动的 33 个文件里，**有 6 个是把我们的版本回退成旧版**（★ 他们的工作区里是旧文件，★ 批量同步时覆盖了我们的修复 ★）。

★ **量化（逐 blob 比对，★ 恢复后立刻查出来的）★**：

| 文件 | 若采用三组版会净丢 | 丢的是什么 |
|---|---:|---|
| `creativity_lab/metrics.py` | **209 行** | ★ 末步零判官指标全套（`keywords` / `survival_rate` / `branch_diversity` / …）★ |
| `creativity_lab/client.py` | 68 行 | ★ `DEFAULT_EFFORT=medium`、`_payload_variants`（失败退路）、`has_content` 字段、`deadline` 墙钟上限 ★ |
| `creativity_lab/gates/base.py` | 29 行 | ★ `_weighted_sample`（★ **修"sample 恒等于 greedy"那个真 bug** ★）★ |
| `creativity_lab/prompts.py` | 24 行 | ★ `VALUE_Q` / `VOTE_Q`（★ ToT 评估器强度实验用 ★）★ |
| `cmp8/creativity_lab/adhd_repro.py` | 7 行 | — |
| `creativity_lab/arms/dual.py` | 3 行 | ★ `specs` 注入（★ 剔下架型号 ★）★ |
| **合计** | **340 行** | |

★ **二次修复**：这 6 个文件**改回本组版本**（★ 依据：★ 三组 commit 的 parent 就是我们的 commit ⇒ ★ 他们的"删除"是回退而非有意变更；★ 且 `topo_arm.py` 依赖 `client.DEFAULT_EFFORT` ⇒ ★ **我们的版本正是当前批运行所用版本** ★）。
★ 其余 25 个文件**保持三组版本**（★ 那些是他们的真实新增，★ 本组没有 ★）。
★ `creativity_lab/gate_policy.py` ★ **两版逐字节相同**（diff 0 行）⇒ ★ 判据脚本与 `+0.0483` 引用**无回退** ★。

★★ **元教训**：★ **「从对方 commit 恢复」≠「对方版本就是对的」★ ⇒ ★ 对方可能是【从旧工作区批量同步】⇒ ★ 恢复后【必须逐文件比对我们自己的版本】★ ⇒ ★ 否则用"恢复"之名做了一次静默回退。★★**

### 4.5 与三组的关系

★ 已主动通报（`communicate` ⇒ 451241289920777），★ 含事故经过、恢复核验、工具修法、★ 以及「你们若也用 overlay 推共享 branch 建议加同一条判据」。
★ 三组随后自建 `tools/push_guard.py` 并提交状态文件 ⇒ ★ **两套实现做同一件事**（★ 待裁决，见 §6 ★）。

---

## 5. ★ 本轮同类错误计数表（6 类）

| # | 错误类 | 次数 | 实例 |
|---|---|:-:|---|
| 1 | **未回源就下结论** | **4** | ① 规格第一版写「嵌入模型不同（`qwen3-embedding-8b` vs `embo-01`）⇒ 不可比」——★ 错：+0.0483 本就是 `gate_policy.py` 用 `embo-01` 算的 ⇒ 回源 `HANDOVER.md` §4.2 后推翻 ★ ② 规格第一版称「用户四题那格数据已存在、零生成调用」——★ 只核了文件存在、没核配置（型号/提示词/min_ok 全不同）★ ③ 规格第一版把 `max_tokens` 写成「客户端默认」——★ 实测默认是 **8000**（`client.py:81`），已改 ④ ★★ **恢复三组文件时★ 假定「对方版本＝正确版本」★ ⇒ 恢复后【没逐文件比对我们自己的版本】★★ ⇒ ★ 造成 **340 行静默回退**（★ `metrics.py` 209 行等 6 个文件 ★）★★ ⇒ ★ **已二次修复并逐 blob 核过**（★ 详见 §4.4 ★）|
| 2 | **数字无表号 / 分母 / 路径** | **0** | 规格与回执里每个数字都带出处（`HANDOVER.md` §4.2 / `client.py:81` / `dual.py` / `runs/model_probe.json`）；率与 ETA 全部给绝对分母（单元数、调用数、秒数）与口径（相邻单元增量） |
| 3 | **patch 脚本静默失败** | **0** | 插入 KNOWN_ISSUES 的脚本 assert 命中（`new.count('KI-04')==1` 失败）⇒ ★ **响亮失败且未写坏文件**（assert 在 write 之前）★ —— 这正是应有行为 |
| 4 | **失败路径静默归零** | **0** | 本轮无新读数；批的失败/空内容由单元级 call 记录独立重算（111 单元 / 1113 调用 / 失败 0 / 空 0 / `n_calls` 与 `calls` 长度不符 0） |
| 5 | **事后重算未标注** | **0** | H0 报告当前为**临时值**（原料 10 个，正式批需 21），脚本输出与记忆均标「临时」；规格引用的 +0.0483 标出处为 `HANDOVER.md` §4.2 |
| 6 | **越界改结论或越界推 main** | **1** | ★★ **overlay 覆盖三组 31 个文件** ⇒ 已恢复 + 已通报 + 工具已修 ⇒ ★ **同一轮内第二次被同源检出**（★ 本条就是它自己给的判据抓到的 ★）★★ ｜ ★ 推 main：0 次（`main` 仍 `e012f1e2574c`）★ |

★ **另外两类自评（不属上表 6 类，但本轮确实发生）**：
- **生成层失控**：本轮有 **2 次**在工具调用里写出长串符号链 ⇒ 一次 shell 参数过长失败、一次正文被截断 ⇒ 修法：改朴素散文 + 表格，脚本化插入。
- **算术单位错**：2 次（ETA 把「每分钟」又除 60；`TOT` 写成 int 却去迭代）⇒ 均在输出前被自查抓到，未污染交付物。

---

## 6. 待 Mavis 裁决（设计层疑问）

| # | 疑问 | 背景 | 我的建议 |
|---|---|---|---|
| 1 | ★ **共享 branch 的守卫要留几套？** | 本组 `push_overlay.py` 内置冲突检测；三组另有 `tools/push_guard.py`（★ 硬编码 `ROOT=/workspace/lab/cmp8repo` ⇒ ★ **在本组环境不可执行** ★）⇒ 同一件事两套实现 | ★ 留一套。★ 建议以**参数化**的那套为准（我们的 `--repo-path` 可移植），★ 三组的守卫改为可导入的公共模块 ⇒ ★ **但这是跨组协调，★ 不由我单方定** ★ |
| 2 | ★ **`.mavis/push_state.json` 的归属** | 两组都写状态、格式不同 ⇒ 已用文件名错开；★ 但远端已存在三组提交的那份 | 保持错开；★ 若裁决为「一套」，则统一到一份并写清 schema |
| 3 | **A 篇 2×2 的缺口 1 修法** | 改 `Dual.run()` 加 `specs=None` 透传（一行、不改默认行为）vs 接受 4 支并重跑 18 题 | ★ 推荐前者（★ 本仓已有同模式先例：`topo_arm.py` 的 `specs` 注入 ★） |

---

## 7. 批运行状态（供封版时间估算）

| 项 | 值 | 出处 |
|---|---|---|
| 进程 | PID **2562**，存活 | `ps -eo pid,comm,args` + 只认 `comm=="python3"` |
| 单元 | **111 / 360** | `runs/topo-arm-v2-2026-10-25/units/*.json` |
| 调用 | **1113**（日志显示 1100） | 单元级 call 记录独立重算 |
| 失败 / 空内容 | **0 / 0** | 同上 |
| 健康度 | 1.0000（独立重算） | 同上 |
| 速率 | **0.62 单元/分、6.21 调用/分**（全程 110 单元 / 179 分钟） | 日志 elapsed 差分 |
| 剩余 | **249 单元 / 2427 调用 ≈ 6.4 小时** | 按各臂实测秒/单元；★ 与速率口径交叉校验（402 / 391 分钟）一致 ★ |
| 预计总时长 | ≈ **9.4 小时** | 批已跑 3.0 小时 + 剩余 6.4 小时 |
| 各臂单位成本 | `nosel_b3` 3 调用/24 秒 ｜ `nosel_b3_synth` 4/34 ｜ 四个 topo 臂 13/110–149 秒 | 相邻单元调用增量 |
| 会让速率变化的因素 | ★ **无重试、无限流**（失败 0）★ ｜ ★ 本批**零判官**（无判官排队）★ ｜ ★ 单元级原子落盘、续跑只补缺口（★ 不产生重跑 ★） | |
