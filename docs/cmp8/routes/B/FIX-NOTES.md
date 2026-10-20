# 路线 B 收尾修复记录（FIX-NOTES）

**对象**：`/workspace/lab/routes/B/`（DESIGN.md / spec.yaml / code/）
**依据**：`/workspace/lab/routes/routeB-verification-2026-10-20.md`（独立复核，VERDICT: FAIL，5 判死 + 4 应修）
＋ 复核补充项「路线 B 的 spec 渲染出来是空页」（判死）
**日期**：2026-10-21 ｜ **执行**：路线 B 收尾（不重写设计，只做收尾）
**硬约束遵守情况**：未改 `PROTOCOL.md`；未改 `/workspace/lab/cmp8repo/**`；未跑训练；未产出任何实验结论；
未声称任何路线更优；**未调用任何模型**（本轮**没有重跑冒烟**，`smoke_log.json` 保持原样 ⇒ 没有"改日志去迁就报告"）；
未触碰 U1–U4。

---

## 0. 总览

| # | 复核意见 | 处置 | 落在哪 |
|:-:|---|---|---|
| ① | **spec 渲染是空页**（判死项） | ✅ 修 | `spec.yaml` 顶层 `nodes:`/`edges:`（20 节点 / 24 边）+ DESIGN §3.9 + `code/test_spec_flowchart.py` |
| 1 | **F1** 实测章节对日志报 6 处错 | ✅ 修 | DESIGN §3.8 表 2/4、D7、§9.1、§9.2、§10.1、§10.3 |
| 2 | **F2** "D1 已被验证"结构上给不出 | ✅ 修（**改文档 + 给代码加开关**） | DESIGN §3.8.1（新）、§9.1、§10.2、§11 L10；`code/smoke.py` 的 `SMOKE_LADDER` |
| 3 | **F3** 声称的训练循环在代码里不存在 | ✅ 修（**代码已由上一轮补齐，本轮核实并写进文档**） | DESIGN §3.6（新增逐行对照 + 实测输出块）、§12、交付说明文件表 |
| 4 | **F4** 梯度公式不是代码在算的 | ✅ 修（**代码已由上一轮改成精确式，本轮把文档改成代码实际在算的**） | DESIGN §3.3（新增推导 + 逐行对拍表）、§4.6.5 旁证 |
| 5 | **F5** 判官提示词违反协议 + 缺 §4.6 自查 | ✅ 修（**代码已由上一轮补 `C_t` 槽，本轮补齐三句逐字 + 新增 §4.6**） | `code/evidence_index.py`（`CHECK_V2`）、`code/smoke.py`（补传 C_t）、DESIGN §4.6（新）、`code/test_judge_prompt.py` |
| 6 | **F6** Mednick"远"这一半没被点名 | ✅ 修 | DESIGN §4.1.1（新）、§4.6.4（新）、`spec.yaml` `reward.proxy.mednick_coverage` |
| 7 | **F7** 步级奖励未去重、§4.5-3 说得太满 | ✅ 修（**代码已由上一轮改成按条目去重，本轮把文档与实测对齐**） | DESIGN §3.4、§4.3 G7、§4.5-3、§9.1；`code/test_step_reward_dedup.py` |
| 8 | **F8** 解析器不是"严格"的 | ✅ 修（**代码已由上一轮改成严格版，本轮把"接受什么/丢什么"逐条写出来**） | DESIGN §4.6.5（新）、§10.1 ❷、§11 L12；`code/test_judge_parser.py` |
| 9 | **F9** guard 的"命中即 abort"不成立 | ✅ 修（**代码已由上一轮改了一半，本轮把入口真正接上**） | `code/guard.py`（`route_payload()` + `__main__` 真扫 + 退出码 2）、`code/smoke.py`（LLM 调用**之前** abort）；DESIGN §11 L11 |

---

## ① spec 渲染空页（判死项）

**复核实测**：路线 B 的 spec 渲染出来是空页（1693 字节，0 rect / 0 path / 0 text）
⇒ 渲染器 `/workspace/lab/build_spec_flowchart.py` 的 `normalize()` 只吃**顶层** `nodes:` / `edges:`。

**改在哪**
- `spec.yaml`：**新增顶层 `nodes:`（20 个）与 `edges:`（24 条）**，插在 `protocol:` 块之后、`action_space:` 之前。
  节点 id = `n0_start … n19_eval`，`kind` ∈ {terminal, process, decision}；边用**块式** `- from:/to:/label:`
  （渲染器自带的极简 YAML 解析器**不吃** flow mapping，写成 `- {from: …}` 会被它解析坏 ⇒ 刻意用块式）。
- `DESIGN.md` **§3.9（新，446–485 行）**：节点 id ↔ DESIGN 章节的逐条对照表 + 边的条件分支语义 + 自检命令。
- `code/test_spec_flowchart.py`（新）：**双解析**（渲染器的极简 YAML + 本路线 `yaml_lite`）+ 渲染非空 + **变异注入**。

**怎么验证**（实测输出）
```
$ cd /workspace/lab && T=$(mktemp -d) && python3 build_spec_flowchart.py /workspace/lab/routes/B/spec.yaml "$T" "路线B" "t" && \
  python3 -c "import re;h=open('$T/index.html',encoding='utf-8').read();print('bytes=%d rects=%d paths=%d texts=%d'%(len(h),len(re.findall(r'<rect',h)),len(re.findall(r'<path',h)),len(re.findall(r'<text',h))))"
✓ .../index.html 已生成（11966 字节）
bytes=11966 rects=17 paths=48 texts=64
```
⇒ **rects=17 ≥ 5**、**paths=48 ≥ 4**、texts=64、**非空页**（与判死时的 0/0/0 相反）。
⚠️ 判死时记录的字节数是 1693；本轮复现的变异体是 **1949 字节 / 0 rect / 0 path / 0 text** ——
差别来自渲染器在 2026-10-21 02:22 又扩了写法与告警文案，**"0 rect / 0 path / 0 text"这个关键事实不变**。

```
$ python3 code/yaml_lite.py spec.yaml
YAML OK · 顶层键 25 个：version, route, route_name, status, produced_at, protocol, nodes, edges, action_space, candidate_rules, features, policy
```
⇒ 顶层键 **23 → 25**（+`nodes` +`edges`），yaml_lite 仍可解析。

```
$ python3 code/test_spec_flowchart.py      # 退出码 0，PASS=true
real: n_nodes=20, n_edges=24, 两个解析器读到的节点 id 集合一致=true,
      render={bytes:11967, rects:17, paths:48, texts:64, empty_page_warning:false}
mutations: remove_nodes_and_edges → PASS=false（errors: 顶层 nodes 缺失或为空 / 顶层 edges 缺失或为空 / 渲染出的是空页告警）
           remove_nodes_only        → PASS=false（错误同上 + 24 条悬空边）
mutations_all_fail_as_expected: true
```

---

## 1. F1 · 实测章节对日志报 6 处错

**改在哪**（逐条；行号为改后 DESIGN.md）

| 复核指出的错 | 改在哪 | 改成什么（= 日志真值） | 日志字段 |
|---|---|---|---|
| 479「尝试级截断 2 次**都是 `al_ex`**」 | §3.8 表第 2 行（394 行）、§9.1「尝试级截断」行（815 行）、§8 监控表 | **2 次全在判官通道 `check2`**（`calls[4]` 1200/length/0、`calls[5]` 2000/length/0）；两次 `al_ex`（`calls[1]`、`calls[9]`）都是 `stop` | `calls[4]/calls[5]`、`n_attempts_truncated=2` |
| 289「DS2 的 `al_ex` 两次都截断 ⇒ `n_claims=0`、`w_hat=0.0`、答案是空壳」 | §3.8 表第 4 行（396 行）、§9.1 之后的"原始现场"段（831 行） | 记录在案的那次**没有**发生：DS2 `n_claims=9`、`w_hat=0.333`、`answer_len=312`、两题 `n_truncated=0`/`n_empty=0`。"空壳"那次是**更早的开发运行**、**日志未保留** ⇒ 明确标注"无法从留存物复核" | `e2e[0..1]`、`truncated_rate_overall=0.0` |
| 305（D7）「`n_calls=11` = 8 次逻辑 + 3 次重试」 | §3.8 D7 行（412 行）、§9.1 | **`n_calls=14` = 12 个步骤 + 2 次重试尝试**；并注明 `n_logical_calls=12` 是**步骤数**（实际客户端 `chat` 次数 13） | `n_calls=14`、`n_logical_calls=12`、`n_calls_ok=12` |
| 478「端到端耗时 197.9 s」 | §9.1（812–813 行） | **wall clock = 184.0 s**（`t0 01:50:06 → t_end 01:53:10`）；`total_secs=197.9` 是**逐次尝试秒数之和**（client 每次 `chat()` 只设一次 `t0` ⇒ 重复计时，多计 13.99 s） | `t0`/`t_end`/`total_secs`/`sum(calls[].secs)` |
| 478「均值 ≈ 14.1 s/次」 | §9.1（814 行） | **13.1 s/次**（184.0 ÷ 14，wall clock 口径） | 同上 |
| 496「按 16.6 s/次外推」+ wall clock 1.5–2 h / 4–6 h | §9.2（853 行）+ 新增交叉核对段（856–861 行） | 统一用 **13.1 s/次**：640 次 ⇒ 8 384 s ≈ 2.33 h 串行 ⇒ 8 worker **≈ 0.29 h**；1 920 次 ⇒ 25 152 s ≈ 6.99 h 串行 ⇒ 15 worker **≈ 0.47 h**；并用分通道均值（al_gen 43.7 / al_ex 13.7 / check2 8.3 s）交叉核对 ≈ 0.28 h | `calls[].secs` 按 purpose 分组 |

**怎么验证**
- 逐条对拍脚本（本轮实跑）：把 `smoke/smoke_log.json` 的 `calls[]` / `e2e[]` / `t0` / `t_end` / `total_secs` 与 DESIGN 的每个数字对齐；
  §9.1 的表格**第三列就是逐字段对照**（读者可按字段名自己复核）。
- `spec.yaml` 的 `cost.measured_smoke` / `cost.training_estimate` **同步改正**（否则机读规格与文档又对不上）。
- 断言：`grep -n "16\.6\|14\.1 s\|n_calls=11\|1\.5–2 h\|4–6 h" DESIGN.md spec.yaml` ⇒ **0 命中**。

---

## 2. F2 · "D1 已被验证"结构上给不出

**问题**：`smoke.py` 无条件 `kw["budgets"] = (2000,)` ⇒ 那次冒烟里 `al_ex` 跑 `(2000,2000)`、判官跑 `(1200,2000)`，
**都不是生产配置** ⇒ 观察到的 2 次截断与 D1 无关。

**改在哪**
- **文档层**（任务要求的"明确写「冒烟不测 D1」"）：
  - `DESIGN.md` **§3.8.1（新，416–444 行）**：「★ **本次冒烟不测 D1**」——把 D1 的地位从"已修好"降级为
    "**未经检验的工程措施**"；列出四种通道在两种模式下的生效阶梯。
  - §9.1 末尾、§10.2（"冒烟没有验证什么"新增 3 条）、§11 **L10**（950 行，新）逐条呼应。
  - §3.8 的 **D1 行**补上**判官通道** `check2` 的生产阶梯 `(1200 → 1800 → 2400)`（原处置只覆盖 `al_ex`/`al_split`）。
- **代码层**（让"能不能测 D1"变成结构事实，而不是靠嘴说）：
  - `code/smoke.py`：`SMOKE_LADDER` 开关（`override` = 历史行为 / `production` = 生产阶梯）+
    `ladder_report()`（**离线、0 次调用**打印每通道的生效阶梯与 `tests_D1` 标志）。
  - `code/smoke.py`：`BudgetedLLM.chat` 在 `production` 模式下**不覆盖** `budgets`。

**怎么验证**
```
$ python3 -c "import smoke,json;print(json.dumps(smoke.ladder_report(),ensure_ascii=False,indent=1))"
mode=override；al_gen/al_ex/al_split/check2 的 is_production 全为 false；tests_D1=false；
note="override 模式 ⇒ 冒烟**不测 D1**（预算阶梯加长没有被检验）"
```
⇒ **没有保留任何"结构上不可能产生的结论"**：文档里现在只有"那次冒烟**不**检验 D1"与"D1 至今未经检验"。

---

## 3. F3 · 声称的训练循环在代码里不存在

**现状核查**：复核时的 `code/train_policy_v2.py` 只有 `run_episode` / `reinforce` / `Ema`（`reinforce` 从未被调用）。
**本轮开工时**该文件已含 `run_training(...)`（轮次 / 并行 / 滑动基线 / EMA / 监控 / 早停 / checkpoint）。
⇒ 本轮做的是**核实它真能跑**，并把它**写进文档**（此前文档只说"参考实现"，两头占）。

**改在哪**
- `DESIGN.md` **§3.6（299–372 行）**：标题改为"伪代码 + **可执行版的实测**"；新增
  ① **逐行对照表**（伪代码行 → `run_training` 的代码位置）；② **离线自测的实测输出块**（`test_train_loop.py` 的真实 JSON）；
  ③ 明确"能证明什么 / 不能证明什么"（stub 回答固定 ⇒ **不产生任何"学到东西"的结论**；真实 8 轮训练批**未跑**）。
- `DESIGN.md` **§12（967 行）**：实现映射里"训练循环参考实现"→"**训练循环**（`run_training`：轮次 / 并行跑题 / 逐 episode 更新 / 滑动基线 / EMA 部署 / 监控 / 早停①校准闸门 / 早停②fatal 闸门 / checkpoint 原子写 + 续跑）+ 精确策略梯度 + 步级奖励按条目去重"，并列出三个自测脚本。
- 交付说明（`/workspace/.mavis/plans/plan_9e024318/outputs/t2-routeB/deliverable.md`）的文件表**同步改正**。
- 新增 `code/stub_llm.py`（离线 stub）与 `code/test_train_loop.py`（自测）。

**怎么验证**（实测输出，已贴进 DESIGN §3.6）
```
$ python3 code/test_train_loop.py     # 退出码 0
rounds_done=4, w_changed=true, baseline_updated=true, ema_differs_from_w=true,
monitor_rounds=4, checkpoint_written=true, checkpoint_resumable=true, stub_calls=72,
no_real_api_calls=true,
calibration_stopped=true, calibration_reason="calibration_failed:0.100<0.500",
fatal_stopped=true, fatal_stopped_reason="fatal_alarm:COLLAPSE_CRIT,SEARCH_CLOSURE",
PASS=true
```
⇒ 伪代码的每一步都有**可执行**对应物；两个早停闸门都会响；**0 次真实 API 调用**。

---

## 4. F4 · 梯度公式不是代码在算的

**现状核查**：复核指出 `φ_a − Σ_i π_i φ_i` 不是标准化 softmax 的 log-π 梯度（漏掉 mean/std 的 Jacobian）。
**本轮开工时** `code/train_policy_v2.py` 已有 `policy_logprob_grad`（**精确**版）与 `code/test_policy_grad.py`（对拍）。
⇒ 本轮把**文档改成代码实际在算的**，并把对拍结果写进 DESIGN。

**改在哪**
- `DESIGN.md` **§3.3（199–256 行）**：更新公式块（`g_t = ∇_w log π(a_t|s_t)`，并给出**精确**的
  `∂z_i/∂w` 推导：`(F_i − F̄)/(τσ̃) − (s_i−μ)/(τσ̃²)·∂σ̃/∂w`）、
  **滑动基线**的真实口径（`b ← 0.1b + 0.9·mean(G)`）、
  **梯度裁剪**（`grad_clip=1.0`，文档此前没写）、
  明确写出"**代码里算的是上面这个式子，不是旧实现那条**"。
- 新增 **逐行对拍表**（代码位置 ↔ 公式 ↔ 实测值）。
- `spec.yaml` `policy.update` 段同步标注算法为"精确 log-π 梯度（标准化 softmax，含 mean/std Jacobian）"。

**怎么验证**（实测输出，已贴进 DESIGN §3.3）
```
$ python3 code/test_policy_grad.py     # 退出码 0
12 个用例（4 个 τ × 3 个候选）：max_rel_err_exact = 2e-09（判据 ≤1e-5 ⇒ 通过）
                            min_rel_err_legacy = 0.22306（>1e-3 ⇒ 确认旧解析式有偏）
exact_matches_numeric=true, legacy_form_is_biased=true, PASS=true
```
⇒ 文档里的公式 = 代码在算的公式（数值上对得上，误差 ≤ 2e-09）。

---

## 5. F5 · 判官提示词违反协议强制条款 + 全文未提 §4.6

**现状核查**：`evidence_index.py` 已有 `conclusion_space` 字段与 `{ct}` 槽（上一轮补的），
但 §522 那句在提示词里是**整句加粗**（协议是**句中**加粗）⇒ 原文不是逐字子串；§526 那句**完全不在**提示词里。

**改在哪**
- `code/evidence_index.py`：`CHECK_V2` ①
  ① 第 ① 句改成与协议**同一个强调位置** ⇒ 协议原文成为提示词的**逐字子串**；
  ② **补上**协议 §4.6:526 的「判官必须拿到题面（prompt）与结论空间 `C_t`」（**两种形态**都写进去）；
  ③ 新增 `CHECK_V2_VERSION = "routeB-judge-v2-protocol-4.6-2026-10-21"`（判官缓存身份变化，DESIGN §2.4-4 已同步）。
- `code/smoke.py`：`run_e2e` 构造 `EvidenceIndex` 时**补传** `conclusion_space`
  （此前**漏传** ⇒ 记录在案的那次冒烟判官拿到的是占位串）。
- `DESIGN.md` **§4.6（新，565–696 行）**：5 个小节 ——
  ❶ 判官提示词**全文**（逐字打印）；❷ 协议 522/523/524/526 的**逐字断言表**（`raw` + `normalized` 两种口径都必须为真）
  + 任务书引文形态的对照；❸ **`C_t` 实际非空**（5 条、逐条在提示词里、占位串缺席、题面与依据编号都在）；
  ❹ Mednick 双条件覆盖自查（→ §4.1.1）；❺ 判官解析器**接受什么/丢什么**（→ F8）。
- `DESIGN.md` §10.2/§10.3：写明"那次冒烟**没有**检验 C_t 真的送进判官"。

**怎么验证**
```
$ python3 code/test_judge_prompt.py     # 退出码 0，PASS=true
s522 raw=true normalized=true | s523 raw=true normalized=true | s524 raw=true normalized=true
s526 raw=true normalized=true | s526 任务书引文 raw=true | s522 任务书引文 raw=false（提示词保留协议强调标记）normalized=true
ct: n_conclusion_space=5, is_empty_list=false, all_items_in_prompt=true,
    placeholder_absent=true, ask_in_prompt=true, evidence_ids_in_prompt=true
```
⚠️ **诚实标注**：`s522 任务书引文 raw=false` 是**故意**的 —— 提示词里用的是**协议原文写法**（含 `**超出问题本身**` 强调标记），
所以"协议原文"是提示词的逐字子串；反过来"去掉标记的形态"只在归一化后相同。**两种口径都写在 §4.6.2 的表里，不含糊。**

---

## 6. F6 · Mednick 双条件的"远"这一半没被点名

**改在哪**
- `DESIGN.md` **§4.1.1（新，499–514 行）**：一张表写清
  「**有用/承重** = ✅ 代理 Ŵ 实现」/「**远/去冗余** = ❌ **未实现**，由**协议主判据 VD 在验收层**强制（协议按删除反事实归族 ⇒ 代理系统性偏大 = G1）」，
  以及 4 条后果：训练目标只覆盖一半、"远"是训练**盲区**、违反"远"的输出在验收层拿不到分、**代理偏离由 FB6 判死**。
- `DESIGN.md` **§4.6.4（新，661–668 行）**：同一张表的 §4.6 版自查。
- `spec.yaml` `reward.proxy.mednick_coverage`（新）：机读规格里也写死这条。

**怎么验证**：文档自洽性检查 —— `grep -n "Mednick" DESIGN.md spec.yaml` ⇒ 命中 §4.1.1 / §4.6.4 / spec 的
`mednick_coverage`（复核时是 **0 命中**）。

---

## 7. F7 · 步级奖励是未去重的"条数"项

**现状核查**：`train_policy_v2.run_episode` 现在**已按锚定条目去重**（`covered` 集合）⇒ 上一轮已改代码；
**本轮**是把文档与实测对齐（此前文档仍写"每次核验 +1.0"，且 §4.5-3 对总回报说得太满）。

**改在哪**
- `DESIGN.md` **§3.4（258–286 行）**：奖励表加上"**口径（代码实际在算的）**"列
  （支持 → **每条新覆盖的锚定条目 +1.0**、矛盾 → **每条断言 −2.0（不去重，保守方向）**、花絮条目 +0），
  并新增 **A/B/C/D 实测表**与"为什么步级必须去重"段。
- `DESIGN.md` **§4.3 新增 G7**（537 行）：把**残余**的两处不对称写进差距表。
- `DESIGN.md` **§4.5 第 3 条**（557–562 行）：改成"这条**对总回报也成立**了（修 F7 后）"，但仍写明剩余的两处不对称。
- `spec.yaml` `reward.step_terms`（加 `unit` 字段）+ `reward.proxy.known_gaps` 加 G7 + `mednick_coverage`。

**怎么验证**（实测输出，已贴进 DESIGN §3.4）
```
$ python3 code/test_step_reward_dedup.py     # 退出码 0，PASS=true
A 1 条断言覆盖E1        步级 +1.0  终局 +1.0  总回报 2.0  Ŵ 0.3333
B 3 句改写同一件事      步级 +1.0  终局 +1.0  总回报 2.0  Ŵ 0.3333
C 8 句改写同一件事      步级 +1.0  终局 +1.0  总回报 2.0  Ŵ 0.3333
D 3 件不同的事          步级 +3.0  终局 +3.0  总回报 6.0  Ŵ 1.0000
assertions: A_step_sum_is_1 / B_step_equals_A / C_step_equals_A / D_step_is_3 /
            total_ABC_equal / D_beats_C / w_hat_D_is_1 ⇒ 全 true
```
⇒ **灌水/重复改写追不平诚实策略**（复核修前的表是 A 2.0 / B 3.0 / C 5.0 / D 5.0）。

---

## 8. F8 · 判官解析器不是"严格"的

**现状核查**：`evidence_index._parse_verdict_lines` 现在**已是严格版**（分隔符必需、未知编号 ⇒ 解析失败、尾部垃圾 ⇒ 解析失败），
上一轮已改；**本轮**把"到底接受什么、什么会被丢"**逐条写出来**并加上离线自测。

**改在哪**
- `DESIGN.md` **§4.6.5（新，670–696 行）**：11 行行为表（接受 6 种、判失败 5 种）+ **已知弱点**（行丢弃 ⇒ 位置配对错位，
  但必然产生一个 `解析失败` ⇒ 触发重试 ⇒ 计入 `parsefail_rate`、不进分子/分母）。
- `DESIGN.md` **§10.1 ❷**（887 行）：把"被**严格**逐行解析器识别"改成**可核**的说法
  （那次运行的产出行行合法 ⇒ 没有一行被丢弃；⚠️ 日志**没有** `parsefail_rate` 字段 ⇒ 那次的值**无法从日志复原**）。
- `DESIGN.md` **§11 L12**（952 行）：把"日志缺 `parsefail_rate`"记成局限。
- 新增 `code/test_judge_parser.py`（11 条行为 + 1 条已知弱点，退出码 0，`PASS=true`）。

**怎么验证**：`python3 code/test_judge_parser.py` ⇒ 11/11 行为符合预期，
其中 `支持 E1`（无分隔符）/ `支持 | E99` / `支持 | E1 blah blah` / `大概支持 | E2` / `未提及 | E3` **全部判解析失败**。

---

## 9. F9 · guard 的"命中即 abort"在已交付入口上基本不成立

**现状核查**：`guard.py` 的 `__main__` 调 `check({})`（**不传任何文本**）⇒ 命中恒为 0 ⇒ 恒 `EXIT=0`；
`smoke.py` 的 `check_blacklist()` 只把 `bl_ok` 记进返回码 ⇒ **命中不会中止运行**，还会先烧掉 LLM 预算。

**改在哪**
- `code/guard.py`：新增 **`route_payload()`** —— 一份**确切**的覆盖清单（4 条提示词 / 2 道诊断题的题面·依据包·C_t /
  `code/*.py` / `data/diag_topics.json` / `DESIGN.md` / `spec.yaml`）；
  `__main__` 改为**真扫这份清单** ⇒ 命中 ⇒ **退出码 2**；模块 docstring 写明两个执行点与"不覆盖运行期模型输出"。
- `code/smoke.py`：`check_blacklist()` 改用 `guard.route_payload()`；`main()` 里
  **命中即 `SystemExit("ABORT: …")`，且发生在创建 LLM 客户端与任何调用之前**。
- `DESIGN.md` **§11 L11**（951 行）：如实写"guard 只覆盖 `route_payload()` 那份清单"，并指出两个已生效的执行点。
- 顺带修掉 F9 同段点出的两个小问题：`SMOKE_CALL_CAP` 现在**只能调低**（`min(20, env)`）⇒ "硬上限 20"不可被抬高；
  `smoke.py` 里那句与代码自相矛盾的 docstring（"budgets=() ⇒ 1 次逻辑调用 = 1 次 HTTP 调用"）已改正。

**怎么验证**
```
$ python3 code/guard.py     # 退出码 0
total_hits=0, ok=true, blacklist_size=5167
text_hits: 10 项全 0；scanned_files: 15 个 .py + diag_topics.json + DESIGN.md + spec.yaml
$ python3 -c "import smoke; print(smoke.CALL_CAP)"   # 20
$ SMOKE_CALL_CAP=50 python3 -c "import smoke; print(smoke.CALL_CAP)"   # 20（只能调低）
```
⇒ 命中 ⇒ 退出码 2 / `SystemExit`（**不发起任何模型调用**）这条路径已写进代码与文档；
⚠️ **没有**用真黑名单内容做"命中演示"（黑名单只在内存里、不落盘 ⇒ 只能靠代码路径断言，不做投毒测试）。

---

## 附：本轮**没有**做的事（明确声明）

- **没有**重跑冒烟（**不调模型**）⇒ `smoke/smoke_log.json` 保持原样；DESIGN 里的所有数字仍以该日志为准。
  收尾期间改动的代码与"记录在案的那次运行"**不等价**的地方，已在 **DESIGN §10.3** 逐条列表（7 行）。
- **没有**跑训练、没有跑 DEV/U1–U4、**没有**产出任何实验结论、**没有**声称任何路线更优。
- **没有**用生产阶梯重跑一次冒烟（那是 D1 的检验，**未跑**）⇒ D1 的地位是"**未经检验**"（§11 L10）。
- **没有**改 `PROTOCOL.md`、**没有**改 `/workspace/lab/cmp8repo/**`（该仓库有在跑的训练进程；`check_ops_consistency.py` 的约束照旧）。
- 顺带修掉两处**字符损坏**（`DESIGN.md`、`code/ops_v2.py` 各有 1 处 U+FFFD）—— 属静默污染，一并清掉。

## 附：复核命令汇总（本轮全部实跑）

```bash
cd /workspace/lab/routes/B/code
python3 test_v2_witness.py        # PASS
python3 test_policy_grad.py       # PASS
python3 test_train_loop.py        # PASS
python3 test_step_reward_dedup.py # PASS
python3 test_judge_parser.py      # PASS
python3 test_judge_prompt.py      # PASS
python3 test_spec_flowchart.py    # PASS
python3 guard.py                  # total_hits=0, 退出码 0
cd /workspace/lab && T=$(mktemp -d) && python3 build_spec_flowchart.py routes/B/spec.yaml "$T" "路线B" "t"
#   ⇒ bytes=11966 rects=17 paths=48 texts=64
```
