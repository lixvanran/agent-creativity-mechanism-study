# 第四组 · v6 Stage-1 · EXEC-LOG（★ 执行记录与语义影响自核）

**版本**：2026-10-25 v1 ｜ **批号**：`v6s1-main-001` ｜ **模型**：`MiniMax-M3`（`https://api.minimaxi.com/v1`）

> ★ **本文件的作用**：★ 记录【谁跑了什么 / 跑出了什么 / 语义变过没有】⇒ ⇒
> ★ **让第三方能独立重算，不必信我们的自述**。

---

## 1. ★ 执行记录（命令 / 退出码 / 调用数 / 失败计数）

| 项 | 值 |
|---|---|
| ★ **主批命令** | `python3 -B run_arch6_stage1.py --topics G01,T07,T10 --reps 1,2,3 --batch-id v6s1-main-001` |
| ★ **补跑命令** | `python3 -B run_arch6_stage1.py --topics T10 --reps 1,2 --batch-id v6s1-main-001 --append` |
| ★ **产物** | `runs/arch6_stage1.jsonl`（★ 仓内副本 `group4_state_driven/data/arch6_stage1.jsonl`） |
| ★ **通道日志** | `runs/calllog.jsonl`（★ 仓内副本 `group4_state_driven/data/calllog.jsonl`） |
| ★ **环境快照** | `runs/env_snapshot.json`（★ G0-1：★ `OPENROUTER_BASE_URL` 实际生效值） |
| ★ **分析脚本** | `analyze_arch6.py`（★ **从 scores 重算排序**，★ 不读落盘 rank） |
| ★ **seed** | ⚠️ **未落盘**（★ runner 里 `rec["seed"] = None`）⇒ ⇒ **本批不可按 seed 复现**（★ 已知缺口） |

### 1.1 ★★ 补跑为什么需要（★ 一个真实的工程坑）

| ★ 现象 | ★ 根因 | ★ 处置 |
|---|---|---|
| ★ 主批只落了 **G01×3 + T07×3 + T10×3 中的 T10-3**（★ 缺 T10-1/T10-2） | ★ **runner 没有"跳过已存在单元"的逻辑** ⇒ ★ `--append` **只是开文件模式**（`mode = "a" if args.append else "w"`）⇒ ★ ★ **上一次续跑是按 `--reps 3` 单点跑的** ⇒ ★ ⇒ **只补了 rep=3** | ★ 改用 `--reps 1,2` **精确补缺口**；★ **同批号 `v6s1-main-001`**（★ 跨批不可混用） |
| ★ 补跑进程"活着但一次调用都没发出"（★ 持有一个 socket、calllog 无新增） | ★ **我自己起的探针进程并发占住了 MiniMax 通道**（★ 一次起了 2 个）⇒ ⇒ **通道被自己占死** | ★ 全部杀掉（★ **连 `timeout` 包装进程一起杀** ⇒ 否则变孤儿继续跑）⇒ ★ 通道冒烟 OK（3.0–3.7s）⇒ ★ **单实例**重跑 |
| ★ "Stage-1 卡住" | ★ **不是卡住，是慢**：★ 逐步打点实测 ⇒ `run_A` 16.5s ／ `build_state5` 61s（4 步状态链）／ ★ `gen_candidates_blind` >105s（★ 3 候选 × thinking 爆炸 + 加预算重试） | ★ **不改代码**（★ 改了会破坏同批可比性）⇒ ★ 单样本约 **5–10 分钟** ⇒ ★ 补跑 2 样本约 11–20 分钟 |

★ ★ **★ 逐步打点的实测轨迹（★ `probe_stage1_step_timing.py`）**：
```
[    0.0s] ① import run_arch6_stage1
[    0.2s] ② imported
[    0.2s] ③ 题面就绪 len=63
[    0.2s] ④ run_A 开始
[   16.5s] ⑤ run_A 结束 err=None text_len=1580
[   16.5s] ⑥ build_state5 开始
[   77.5s] ⑦ build_state5 结束 gaps=3 decisions=3
[   77.5s] ⑧ state_variants6 开始
[   77.5s] ⑨ state_variants6 结束 qmeta={'n_decisions': 3, 'natural_quota': 0, 'dropped_quota': 0, 'quota_forced': True}
[   77.5s] ⑩ gen_candidates_blind 开始
```
★ ★ **★ 这条轨迹同时暴露一个成本事实**：★ `gen_candidates_blind` 里每个候选 `max_tokens=3200` 且**不关 thinking**
★ ⇒ ★ calllog 实测出现 `reasoning_tokens` 吃掉 3199/3200 ⇒ `finish_reason=length` ⇒ **加预算重试**（×1.8 ⇒ 5760 ⇒ 10368）
★ ⇒ ★ ★ **单样本成本被重试放大约 3 倍** ⇒ ⇒ **★ Stage-2 跑长臂前必须先修这一条**（★ 候选生成是结构化输出 ⇒ 应关 thinking ⇒ ★ 预计省约 95% token、把单样本从 5–10 分钟压到 1–2 分钟）
★ ⇒ ⇒ ★ **但本批不能改**（★ 改了 ⇒ 同批内样本不可比 ⇒ ⇒ **改口径必须重跑整批**）。

★ ★ **★ 这两条都是「n 悄悄变小 / 失败静默漏记」的同族** ⇒ ⇒
★ ★ **⇒ 交付纪律：★ n 必须作为一等读数报出（★ 每个对比单独报）；★ 失败调用必须进分母**。

### 1.2 ★★ 补跑期间发现的一个 runner 缺陷（★ 已记录，未修）

★ `_with_watchdog`（`run_arch6_stage1.py:211`）在 `th.join(limit)` 超时后**返回失败记录**，
★ ★ **但那个 daemon 线程仍在后台跑** ⇒ ⇒ **它继续持有 socket 与文件句柄，并继续发 API 调用** ⇒ ⇒
★ ★ **⇒ 风险：① 同一文件被两个线程同时写；② 白烧额度。**
★ ★ **本次未触发**（★ 补跑在 watchdog 前就完成了），★ ★ **但 Stage-2 跑长臂前必须修**
★ ★ **（★ 修法：★ watchdog 超时后关闭 socket / 用可中断的请求；★ 或改成子进程隔离）**。

### 1.4 ★★ calllog 的一个缺口（★ 显式标注，★ 不当作无事发生）

| ★ 项 | ★ 值 |
|---|---|
| ★ **calllog 落盘条数** | ★ **21**（★ 覆盖第一批 7 个样本，★ 时间 13:51:51 – 14:00:23） |
| ★ **补跑段的调用** | ★ **未落盘**（★ 补跑进程在 `dump_calllog()` 之前被终止 ⇒ ★ 进程内存里的 TRACE 一并丢失） |
| ★ **样本级调用数（★ 可独立核）** | ★ 每样本固定 **9** 个逻辑步骤（`A` / `stance` / `draft` / `observe` / `decide` / `cand1..3` / `embed_ref`）⇒ ★ **9 样本 = 81 逻辑步骤** |
| ★ **⚠️ 口径警告** | ★ **81（逻辑步骤）≠ HTTP 调用数**：★ 每个 `cand*` 步内部可能有多次 HTTP 重试（★ thinking 截断 ⇒ 加预算重试 ⇒ 实测出现 3200→5760→10368 三次）⇒ ⇒ ★ **差值不能解读为"漏记的失败调用"** |
| ★ **影响** | ★ **通道健康度的分母不完整** ⇒ ⇒ ★ **凡用 calllog 算健康度的结论，★ 本批【不成立】** ⇒ ⇒ ★ **Stage-2 必须修**（★ 修法：**每次逻辑调用后立即追加落盘**，★ 不要等进程结束） |

★ ★ **★ 缺口性质**：★ 这是「失败/成功调用漏记」的**同族**，★ 但方向相反 ——
★ **★ 不是"失败被藏起来"，★ 而是"整段成功调用被藏起来"** ⇒ ⇒ ★ **同样会让分母变小** ⇒ ⇒ ★ **同样要显式标注**。

### 1.5 ★★ 重复采样的处置（★ 一次真实的重复，非文件损坏）

★ **现象**：★ 补跑期间**三个进程同时在跑**同一个命令（★ 4917 / 5235 / 5271）
⇒ ⇒ ★ 其中一个在被 kill 前已把 **T10-1** 写盘 ⇒ ⇒ ★ **同一 (题, rep) 出现两条记录**。

★ **★ 这不是文件损坏**：★ 两条都是**完整合法的独立采样**
（★ 各 9 次调用 / 0 错误 / 同批号 / ★ **决策 note 措辞不同** ⇒ ⇒ 确实是两次独立采样）。

★ **处置（★ `fix_duplicate_resampling.py` · ★ 显式留痕）**：
★ ① **两条都保留**（★ 都是有效数据）
★ ② 后写入的那条**重标记为 `T10-2`**（★ `tag` 与 `rep` **两个字段都改** ⇒ ★ 否则按 `rep` 分组仍会重复计权）
★ ③ ⇒ ★ **每题恰好 3 个重复 ⇒ ★ 臂间 n 相等**
★ ④ 留痕：`runs/duplicate_resampling.json`

★ ★ **★ 为什么不能静默处理**：★ **① 静默去重** ⇒ 丢掉一次有效采样 ⇒ **样本量悄悄变小**；
★ **② 静默保留两条** ⇒ T10 计权 4 次、G01/T07 各 3 次 ⇒ **臂间 n 不等**；
★ ⇒ ⇒ ★ **两种"不吭声"都会把缺口藏起来** ⇒ ⇒ ★ **⇒ 必须显式处置 + 留痕**。

★ ★ **★ 教训（★ 与「n 悄悄变小」同族）**：★ **★ 起同一个 runner 的进程必须先扫一遍残留 PID 并杀光**
★ ⇒ ★ ★ **杀的时候要连 `timeout` 包装进程一起杀**（★ 否则它变孤儿继续跑、继续写同一个文件）。

### 1.6 ★★ 仓内产物同步（★ 一次被主会话当场抓出的不一致）

★ **主会话 2026-10-25 21:0x 抓到**：★ 仓内 `data/arch6_stage1.jsonl` = **6 行**，
★ 而工作区 `runs/arch6_stage1.jsonl` = **7 行** ⇒ ★ md5 不同 ⇒ ⇒ **仓内那份过期了**。

| ★ 文件 | ★ 同步前（工作区 → 仓内） | ★ 同步后 |
|---|---|---|
| ★ `arch6_stage1.jsonl` | 7 行 → **6 行**（★ 不一致） | ★ **9 行，sha 核对通过** |
| ★ `calllog.jsonl` | 21 行 → **10 行**（★ 不一致） | ★ **21 行，sha 核对通过** |
| ★ `env_snapshot.json` | sha 不同 | ★ **sha 核对通过** |
| ★ `arch6_stage1_analysis.json` | ★ **n_rows = 5**（★ ★ **派生读数描述的是另一批数据**） | ★ **已重算 ⇒ n_rows 与原始样本一致** |

★ ★ **★ 这比"少跑 2 个样本"严重得多**：★ **少跑是【缺口】（看得见），★ 交旧数据是【缺口被藏起来】（看不见）**
★ ⇒ ⇒ ★ **⇒ 落地：`sync_stage1_data.py`**（★ 原子写 + 回读核行数 + sha256 + **★ 派生文件行数一致性检查**）
★ ⇒ ⇒ ★ **★ 今后每次同步后必须核「analysis 的 n_rows == 原始样本行数」**。

---

## 2. ★★★ 语义影响自核：★ rev1（死路判定语义变更）是否影响本批已跑数据

> ★ **主会话 2026-10-25 20:5x 的硬要求**：★ 「★ 请核，不要用"大概率不影响"代替那次 grep」。

### 2.1 ★ 三层核（★ 从弱到强）

| 层 | 核法 | 结果 |
|:-:|---|---|
| ① | **关键词 grep**：`check_dead_end` / `at.used` / `dead_end` / `consecutive_no_new` / `DEAD_END` / `detect_tie` / `HYP_SUPPORTED` / `state_layer` / `preserve_divergence` / `choose_action` / `record_attempt` | ★ **0 命中** |
| ② | **反向 import 核**：★ Stage-1 的 import 链 = `api_any` / `workflow_arch5` / `workflow_arch6` / `run_arch5_compare` / `run_arch3_compare` ⇒ ★ **不 import 第二组 `state_layer`** | ★ **零依赖** |
| ③ | ★ **结构性核（最强）**：★ Stage-1 的状态实现是 **`workflow_arch5.py:25` 独立定义的 `State5`** ⇒ ★ **与第二组 `state_layer.py` 是两套完全不同的代码**；★ 且 `dead` 一词在 `workflow_arch5.py` / `workflow_arch6.py` 中 **0 命中** ⇒ ⇒ **★ 死路判定语义在 Stage-1 的代码里【根本不存在】** | ★ **不影响** |

### 2.2 ★ 结论（★ 一行）

> ★★ **已核：★ 本批（`v6s1-main-001`）已跑数据【不受 rev1 死路判定语义变更的影响】。**
> ★★ **依据 = 上面第 ③ 层（结构性核）**，★ 不是"大概率"。
> ★★ **★ 且 Stage-1 只 import 三组的 `gates/base.py`（md5 `400d27894a7716085c594ef5e603065b`）与 `client.py`** ⇒ ★ **那两份本轮未改动**。

### 2.3 ★★ 留痕（★ 纪律：★ "不影响"本身是个需要证据的断言）

| ★ 项 | ★ 值 |
|---|---|
| ★ **核验时间** | 2026-10-25 |
| ★ **核验方式** | ★ 三层（关键词 / import 链 / 结构性） |
| ★ **受影响？** | ★ **否** |
| ★ **影响若存在会怎么表现** | ★ 若 Stage-1 用了第二组死路判定 ⇒ ★ **D0 地板会偏大、且"代价触发换路"的计数会偏多** ⇒ ★ 本批 `align_shift_var_mean` 与排序改变率都会被污染 |
| ★ **旁证** | ★ 本批 D0 参照值沿用 v3 实测 `D0 = 0.0720`（★ **来自 v3 自己的实现**，★ 不经第二组代码） |

---

## 3. ★★★ 「规格本身有洞」的三行（★ 主会话 2026-10-25 20:5x 要求）

★ **这是我们目前最缺的一类证据**：★ 「规格有洞」是【被测试发现的】还是【被人工发现的】？★ 两者可信度差一个量级。

| ★ 行 | ★ 内容 |
|:-:|---|
| ★ **1. 先写错** | ★ 第四组写 `test7_detect_tie` 时，★ **按"任意并列都算"** 写断言（★ `detect_tie([0.5,0.5,0.9])` 应检出）⇒ ★ **该断言在 rev1 实现下失败**（★ 实际返回 `None`） |
| ★ **2. 暴露哪个规格缺口** | ★ **规格从未规定 `detect_tie` 是"只查最高分"还是"查所有并列簇"** ⇒ ★ ⇒ ★ **这是规格的洞，不是实现的错** ⇒ ★ 而第二组第一版实现选了"只查最高分" ⇒ ★ ⇒ ★ **双方都以为对方知道** |
| ★ **3. 修完怎么验** | ★ 第二组 rev2 改为"返回所有并列簇"（★ 返回类型 `Dict` ⇒ `List[Dict]`，★ 空时 `[]`）⇒ ★ 第四组 `test7` 断言改为**同时覆盖**「最高分并列检出」+「中位并列检出」+「无并列返回空列表」⇒ ★ ★ **并在 rev1 下【明确失败】**（★ 已验证：rev1 下 test7 红，★ 证明这条断言真的在测 rev2 语义） |

★ ★ **★ 为什么这三行有分量**：★ ★ **如果测试是照着实现写的，★ 它【不可能】先写错** ⇒ ⇒
★ ⇒ ★ **而它确实先写错了** ⇒ ⇒ ★ ⇒ ★ **这是「测试与实现【独立】」的【观测到的证据】**（★ 不是声明）★ ⇒
★ ⇒ ★ **⇒ 与「照抄 = 同源 ⇒ 一起错时一起绿」是同一件事的两面**。

---

## 4. ★★ 关键源码索引（★ 仓内 `路径:行号`）

| ★ 内容 | ★ 位置 |
|---|---|
| ★ Stage-1 runner | `group4_state_driven/code/run_arch6_stage1.py` |
| ★ 分析脚本（★ **从 scores 重算排序**） | `group4_state_driven/code/analyze_arch6.py` |
| ★ 状态实现（★ **与第二组无关**） | `group4_state_driven/code/workflow_arch5.py:25`（`class State5`） |
| ★ 选择器与 Gate 接线 | `group4_state_driven/code/workflow_arch6.py` |
| ★ ★ **`Select(k>=n)` 返回原序的坑**（★ 「排序改变率=0」假象的根因） | `group4_state_driven/code/workflow_arch6.py`（★ `Select.__call__`）⇒ ★ 边界枚举见 `group4_state_driven/probe_select_boundary.py` |
| ★ 预注册 | `group4_state_driven/prereg/PREREG_v6.md`（★ v3） |
| ★ Stage-1 规格 | `group4_state_driven/prereg/STAGE1_SPEC.md` |

---

## 5. ★★ 原始样本清单

| ★ 文件 | ★ 内容 |
|---|---|
| ★ `data/arch6_stage1.jsonl` | ★ 逐样本记录（★ 每行 = 一个 (题, rep)） |
| ★ `data/calllog.jsonl` | ★ 逐次 API 调用（★ **含失败调用** ⇒ 分母完整） |
| ★ `data/env_snapshot.json` | ★ G0-1 环境快照 |
| ★ `data/arch6_stage1_analysis.json` | ★ 分析输出 |

★ **复现命令**：
```bash
python3 -B group4_state_driven/code/analyze_arch6.py \
        group4_state_driven/data/arch6_stage1.jsonl
```
