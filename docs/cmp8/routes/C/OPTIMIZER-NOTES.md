# 优化器契约 · 落地说明（路线 C）

> 2026-10-21 ｜ 把 `/workspace/lab/routes/OPTIMIZER-CONTRACT.md`（**设计**）变成**可执行代码**。
> ⚠️ **本文件里的所有数字都是「合成读数」**（本地假客户端 + DEV 金标卡），
> **不是实验结论**，也不能用来比较任何路线/臂/配置。真实跑批前必须先冻结 `measure_version`。

---

## 0. 交付物清单

| 文件 | 角色 | 对应契约小节 |
|---|---|---|
| `config.py` | 统一 config 对象（L2） | §3 |
| `optimizer.py` | L3 契约执行器 + 测量内核 + 4 道守卫 | §4.1 ①–⑧、§1.3 L0-1/L0-5 |
| `noise_floor.py` | 真实现的 `estimate_noise_floor` | §1.3 L0-3/L0-4/L0-5 |
| `credit.py` | 消融式信用分配 | §2 |
| `test_optimizer.py` | 自检 + **变异注入** | 全部 |
| `optimizer_out/` | 自检读数与一次完整契约跑批的产物 | —— |

**没做也不假装做了的**（契约里的 S4/S5 与 L4 元优化）：
本轮**只落地契约的机械件**（L0/L1/L2/L3），**没有**做 L4 元优化器，
**没有**跑任何真实模型实验，**没有**产出任何路线优劣结论。

### 怎么复现（三条命令）

```bash
cd /workspace/lab/routes/C

# ① 自检 + 变异注入（正常模式必须全过；4 个变异必须全部被抓住；退出码 0 才算通过）
python3 test_optimizer.py

# ② 一次完整契约跑批（L0 噪声地板 → L3 优化轨迹 → L1 信用分配），产物落在 optimizer_out/
python3 test_optimizer.py --demo

# ③ 单元演示（config 对象 / 自由度差异 / 哈希）
python3 config.py
```

⚠️ 三条命令**都不调任何模型 API**（不调 OpenRouter、不调 MiniMax）⇒ 跑完不会花一分钱。

---

## 1. ★ 逐条对应契约 §4.1 的 8 条纪律

### ① 一次只改一个自由度（可归因）

* **实现在哪**：`optimizer.py:329` `_check_single_freedom()`（薄封装 `config.diff_configs`）
  ⇒ 真正的判定在 `config.py:422` `diff_configs()`：
  变了 >1 个自由度 ⇒ 抛 `MultiFreedomChangeError`（`config.py:91`）；
  完全没变 ⇒ 抛 `NoFreedomChanged`（`config.py:87`）。
  调用点：`optimizer.py:605–611`（在 `Optimizer.run()` 主循环里，**测量之前**）。
* **额外一道**：`optimizer.py:621`「死参数守卫」——改动若落在**当前拓扑下不活**的自由度上
  （`config.free_degrees()`，路线 C 默认拓扑下 12 个参数只活 7 个），
  则该改动不产生行为差异 ⇒ 没有归因价值 ⇒ 拒绝并落盘 `guard="dead_freedom"`。
* **怎么验证**：`test_optimizer.py` 的 `guard_single_freedom`（直接调守卫）
  ＋ `optimizer_rejects_two_freedom`（**端到端**：提案者直接交一整份改了 2 个自由度的 config）。
* **验证读数**：正常模式 `✓ guard_single_freedom：如期抛出 MultiFreedomChangeError：一次改了 2 个自由度（params.n_cand_per_frame, params.n_frames）⇒ 违反契约 ①「一次只改一个自由度」`；
  端到端 `✓ optimizer_rejects_two_freedom：双自由度候选：守卫抛出=True，落盘守卫标签=['single_freedom']，进入「改动」的多自由度记录=0 条`。
  ⚠️ 注意：提案接口**特意**允许提案者直接交整份 config（`optimizer.py:593`），
  否则「一次只改一个」只是 `set_freedom()` 的副产品，守卫拦不住乱改的提案者。

### ② 改动后重复测量 R_meas 次，取中位数

* **实现在哪**：`optimizer.py:163` `measure_arm()`：
  每题**生成一次**（种子固定 ⇒ 可复现；θ 与 θ′ 共用同一批种子 ⇒ **配对比较**），
  然后**测量 R_meas 次**（每次换一个判官随机种子），
  最后取**中位数那一 rep** 的读数（族集合与分子分母都取它，`optimizer.py:157` `_median_rep_index`）。
* **怎么验证**：`test_optimizer.py` 的 `optimizer_log_fields`（每条记录带 `r_meas` 与逐 rep 读数）
  ＋ `optimizer_end_to_end`（端到端跑 4 次改动）。
* **验证读数**：`✓ optimizer_log_fields：落盘 4 条（改动 4 条），缺字段：无`；
  落盘样例（`optimizer_out/trajectory.jsonl`）里每条 `change` 记录都带 `r_meas: 5` 与 `reps`（逐 rep 的 `vd_final/n_supported/n_contradicted/n_key_hit/n_cards_total`）。
* **⚠️ 一处必须讲清的口径**：读数用**固定生成种子**（配对），而阈值用 **δ_total**（端到端）⇒
  判据**偏严**（宁可漏过真改进，不可误收噪声）。这是有意的选择。

### ③ 接受条件：`VD_net(θ′) − VD_net(θ) > δ` **且** 所有反判据不劣化

* **实现在哪**：`optimizer.py:350` `_accept_decision()`
  —— `return bool(gain > delta and counter_ok)`；
  反判据在 `optimizer.py:361` `counter_criteria()`（R1–R4）。
  调用点：`optimizer.py:526–530`（测量新臂 → 算增益 → 比反判据 → 判定）。
* **R1 矛盾率不上升**：按**协议 §3.2 的三段判读**（`≤1×地板` ⇒ 不劣化；
  `1×<差值≤2×地板` ⇒ **warning 但不判死**； `>2×地板` ⇒ 失败）。
  地板来自 `noise_floor.py` 的 `floors.conflict_rate`（同臂同任务跨 rep 的逐份 `conflict_rate` 池化）。
* **R2 正确答案不丢**：逐题比 `key_conclusion_hit`，任一题低于原臂 ⇒ 失败。
* **R3 成本可接受**：超预注册上限（`n_calls/n_tokens/cost_usd`）⇒ 失败。
* **R4 依据支持率不下降**：**描述量**（协议 §3.2）⇒ 只报 warning，不判死。
* **怎么验证**：`test_optimizer.py` 的 `accept_rule_gain_above_delta` / `accept_rule_gain_below_delta` /
  `accept_rule_counter_regression`（用**钉死读数**的 `ScriptedRunner` 把三种情形分别构造出来）。
* **验证读数**：
  * `✓ accept_rule_gain_above_delta：增益 2 > δ ⇒ 接受（实测 2）`
  * `✓ accept_rule_gain_below_delta：增益 0 ≤ δ ⇒ 回退`
  * `✓ accept_rule_counter_regression：增益 2 > δ 但 R2 退化 ⇒ 回退`
  * 端到端（合成 runner）：`✓ optimizer_end_to_end：改动 4 次，决策序列 ['accept', 'rollback', 'rollback', 'rollback']，停止原因 converged_no_gain_3`。
  * 一次完整跑批（`optimizer_out/trajectory.jsonl`）里第 1 次改动**带 warning 被接受**：
    `⚠ R1 矛盾率方向不利但不可分辨（0.0286 → 0.0943，地板 0.0552）`、
    `⚠ R4 依据支持率下降（0.9714 → 0.9057）；描述量，不判死（与 R1 联合看）`。

### ④ 预算上限 K（事前写死）

* **实现在哪**：`optimizer.py:585–587`（循环开头判 `n_changes >= self.budget` ⇒ 停，`halt_reason="budget_exhausted"`）；
  `optimizer.py:641–642`（提案跑完但已用满预算时，停止原因也记 `budget_exhausted`）。
  ⚠️ **计数口径**：**被守卫拦下的候选不计入 K**（没测量 ⇒ 没发生「改动」）；
  **回退也计入 K**（那也是一次改动）。
* **怎么验证**：`test_optimizer.py` 的 `optimizer_budget_K`。
* **验证读数**：`✓ optimizer_budget_K：K=3 ⇒ 实际改动 3 次，停止原因 budget_exhausted`。

### ⑤ 禁止在 TEST 集上做改动决策

* **实现在哪**：`optimizer.py:312` `_check_dev_only()` —— **逐题**判定，非 DEV 题直接抛 `TestSetLeakError`（`optimizer.py:55`）。
  判别口径 `optimizer.py:304` `_is_dev_task()`：有 `split` 字段则必须是 `dev`；否则任务号必须形如 `D<数字>`。
  **两个调用点**：`optimizer.py:481`（构造时）与 `optimizer.py:500`（**每次测量时**都查，不只构造时）。
  另外 `noise_floor.py:177` 与 `credit.py:112` 各自也调这道守卫 ⇒ **地板估计与消融臂同样进不来 TEST 集**。
* **怎么验证**：`test_optimizer.py` 的 `guard_dev_only`（直接调守卫）+ `optimizer_rejects_test_dataset`（端到端构造）。
* **验证读数**：
  * `✓ guard_dev_only：如期抛出 TestSetLeakError：⑤ 违反：改动决策不得使用 TEST 集（发现非 DEV 题：U1）`
  * `✓ optimizer_rejects_test_dataset：如期抛出 TestSetLeakError：⑤ 违反：改动决策不得使用 TEST 集（发现非 DEV 题：U1）`
* **附带的冻结校验**：`test_optimizer.py:295` `_devset_hash()` 重算 DEV 集哈希并与 `MANIFEST.json` 对账，
  读数 `DEV 集：9 题，冻结哈希 sha256:41bbb538a454d9b0（现算 sha256:41bbb538a454d9b0）⇒ 一致`。

### ⑥ 禁止改 `measure_version`（改它 ⇒ 带宽变 ⇒ 全部重测并声明）

* **实现在哪**：
  * `config.py:236` `bind_measure_version()` —— 把**四项**绑定
    （判官提示 / 抽取器 / 卡片 schema / 依据包哈希）哈希成一个 `measure_version`；
    改任一项 ⇒ `measure_version` 变（`config.py:341` `_measure_changed()`）。
  * `optimizer.py:337` `_check_measure_version()` —— 变了就抛 `MeasureVersionChangeError`（`optimizer.py:59`）。
    调用点：`optimizer.py:613–619`（**测量之前**）。
* **怎么验证**：`test_optimizer.py` 的 `measure_version_binding`（四项逐项改）+ `guard_measure_version` + `optimizer_rejects_measure_version`。
* **验证读数**：
  * `✓ measure_version_binding：judge_prompt_version→version变=True diff报=measure_version；extractor_version→version变=True diff报=measure_version；card_schema_version→version变=True diff报=measure_version；evidence_hash→version变=True diff报=measure_version`
  * `✓ guard_measure_version：如期抛出 MeasureVersionChangeError：⑥ 违反：不得在优化过程中修改 measure_version（sha256:abed10a12e2e3703 → sha256:2172f5fe00034d75）⇒ 测量带宽变了，全部历史读数作废并须重测`
  * `✓ optimizer_rejects_measure_version：改 measure_version 的候选被守卫拦下=True`
* **⚠️ 诚实说明**：目前绑定里带的是**占位值**（`config.py:71` `PLACEHOLDER_MEASURE`）⇒
  `measure_version` **尚未真正冻结**。每条落盘记录都带 `measure_placeholder: true` 标记，
  真实跑批前必须由负责人冻结这四项并**全部重测**（L0-1）。

### ⑦ 每次改动的 (θ, θ′, VD_net, 反判据, δ, 接受/回退) 全部落盘

* **实现在哪**：`optimizer.py:432` `JsonlLog` —— **append-only**，`optimizer.py:441` `append()` 每次写完立即
  `flush()` + `os.fsync()`（崩溃不丢已记录的改动）。
  记录构造在 `optimizer.py:524` `evaluate()`，调用点 `optimizer.py:632`。
  记录字段：`theta / theta_prime / changed_freedom / vd_net_theta / vd_net_theta_prime /
  vd_net_theta_per_task / vd_net_theta_prime_per_task / gain / delta / delta_source / r_meas / reps /
  counter_criteria / decision / reason / config_hash_theta / config_hash_theta_prime /
  measure_version / devset_hash / floor_check / measure_placeholder`。
  **被守卫拦下的候选也落盘**（`kind="guard_reject"`，带 `guard` 标签与 `detail`）⇒ 拦下的理由不丢。
* **怎么验证**：`test_optimizer.py` 的 `optimizer_log_fields`（字段齐全）+ `optimizer_log_append_only`（追加而非覆盖）。
* **验证读数**：
  * `✓ optimizer_log_fields：落盘 4 条（改动 4 条），缺字段：无`
  * `✓ optimizer_log_append_only：同一日志文件：4 条 → 5 条（追加而非覆盖）`
  * 实际产物：`optimizer_out/trajectory.jsonl`（4 次改动 + 守卫记录，每行一条 JSON）。

### ⑧ 收敛判据：连续 3 次改动收益都 ≤ δ ⇒ 停

* **实现在哪**：`optimizer.py:637–640` —— `no_gain` 计数：本次改动 `gain ≤ δ` 则 +1，否则清零；
  `no_gain ≥ 3` ⇒ `halt_reason="converged_no_gain_3"` 并 break。
  ⚠️ **口径**：字面按契约「收益 ≤ δ」计 ⇒ **回退（收益为负）也算一次"没收益"**。
* **怎么验证**：`test_optimizer.py` 的 `optimizer_convergence_3`（用钉死读数让 4 次改动收益全为 0）。
* **验证读数**：`✓ optimizer_convergence_3：连续 3 次收益 ≤ δ ⇒ 停；实际改动 3 次，停止原因 converged_no_gain_3`。
  端到端同款：`✓ optimizer_end_to_end：… 停止原因 converged_no_gain_3`。

---

## 2. L0 · 目标可重复性（契约 §1.3）

| 契约条 | 实现 | 验证读数 |
|---|---|---|
| **L0-1 测量协议版本冻结** | `config.py:236` `bind_measure_version()`（四项绑定）+ `optimizer.py:337` 守卫 ⑥ | `✓ measure_version_binding`（四项逐项改都报 `measure_version`） |
| **L0-2 重复测量 R_meas 次取中位数** | `optimizer.py:163` `measure_arm()` | `✓ optimizer_log_fields`（每条记录带 `r_meas` 与逐 rep 读数） |
| **L0-3 噪声地板 δ** | `noise_floor.py` `estimate_noise_floor()`（真实现）＋ **`delta_judge_version`**（2026-10-22 补，见 §2.1.1） | `✓ noise_floor_estimates` / `✓ delta_judge_version_is_computed` / `✓ hard_gate_blocks_degenerate_judge_noise` / `✓ credible_threshold_covers_judge_version` |
| **L0-4 接受阈值 > δ** | `optimizer.py:350` `_accept_decision()` | `✓ accept_rule_gain_below_delta：增益 0 ≤ δ ⇒ 回退` |
| **L0-5 地板检测** | `optimizer.py:268` `floor_check()` + `optimizer.py:63` `FloorEffectError` | `✓ optimizer_floor_effect_blocks：地板臂触发 FloorEffectError=True L0-5：被优化量长期贴 0（该臂多数题一条维度都没造出来）⇒ **先修测量/扩依据包，再谈优化**（L0-5）（median vd_final=0，零值题占比 1.00）` |

### 2.1 `estimate_noise_floor` 的三个数（+ 一个补的第四个）

| δ | 怎么造重复 | 每次读什么 | 本次合成读数 |
|---|---|---|---|
| `delta_judge` | 同一份答案，**只换判官种子**，测 R_meas 次 | 单题 `vd_final` | `0`（n=45，MAD 退化）/ mean_abs_dev 0.348 |
| **`delta_judge_version`** | 同一份答案，换**判官变体**（跨 `measure_version` / 跨判官模型） | 单题 `vd_final` | 由 `judge_variants` 实测得出（见 §2.1.1）|
| `delta_gen` | **换生成种子**重新生成，判官种子固定 | 单题 `vd_final` | `0`（n=27）/ mean_abs_dev ≈0.15 |
| `delta_total` | 端到端（换生成种子 + 换判官种子） | 单题 `vd_final` | `0`（n=135）/ mean_abs_dev 0.348 |
| **阈值** | `max(MAD×1.4826, mean_abs_dev)` | —— | **δ\* = 0.3481** |
| **可信门槛** | `max(δ_total, δ_judge_version)` | —— | **判官侧漂移不再被漏掉** |

#### 2.1.1 ★★ 2026-10-22 复核发现：种子地板在 temp=0 下**没有信息量**

**发现**：`delta_judge` 恒为 0，而判官跑 `temperature=0`
⇒ **同一 `measure_version` 内判定是确定性的** ⇒ 「只换判官种子」**测不出任何东西**
（**定义造成的，不是仪器稳**）。而本文件第 178 行原写「MAD 退化」却**仍拿 `δ*=0.3481`
当「增益 > δ ⇒ 可信」的门槛** ⇒ **逻辑是断的**：
用一个恒为 0 的地板当门槛 ⇒ **任何非零增益都会被判为可信**。

**而我们真实栽的跟头恰恰是跨 `measure_version` 的漂移**（U1 实测：v1→v2 净增益
`0/+1/−1` → `+1/+4/0`）⇒ **判官侧漂移被完全漏掉**。

**修（三处）**：
1. `noise_floor.py` 新增 `judge_variants` 参数 ⇒ 测 **`delta_judge_version`**（跨判官版本/模型）
2. 新增**硬闸门**：种子地板退化且未提供 `judge_variants` ⇒ **`optimization_allowed=False`**
   + 判决写明原因（不许静默放行）
3. **可信门槛** = `max(δ_total, δ_judge_version)` ⇒ 判官侧漂移进入判定

**依据文献**：ToT 的**换评估模型交叉实验**（同源 74% / 换评估器 64% / 31%）；
Diversity Collapse 的**换度量/换 embedding 检查排序稳定性**。

**自检**：`test_noise_floor_version.py`（4 项检查 + **3 个变异注入**），
变异注入**基线 4/4 全过才执行**（否则会假阳性，见 §2.1.2）。

#### 2.1.2 ★ 复核发现的第二个 bug：δ 的统计量与决策变量**错位**

`noise_floor.py` 的三个 δ 循环**各自手写了一遍族归并**（`"|".join(sups)`），
**漏了 `stage == "internal"` 的过滤**
⇒ δ 测的是 `vd_internal` 那个量，而**决策变量是 `vd_final`**（`stage=internal` 的卡被排除）
⇒ **地板迁移不到「增益 > δ」的判定上**。
⇒ **修**：删掉手写归并，改为**直接调用生产的 `optimizer._task_reading()`**
⇒ 统计量**按构造一致**（重复逻辑就是 bug 的窝）。
⇒ 顺带修：`_measure_with_variant` 在 runner 不支持 `variant` 时**显式报错**，
**不许静默退回同版本测量**（静默退回会让「跨版本 δ」冒充成真读数）。

#### 2.1.3 ★ 自检自身的假阳性（第三个 bug，在测试里）

`test_noise_floor_version.py` 首版变异注入报「3/3 全被抓住」，
**但失败的全是那条基线本来就失败的检查** ⇒ **被预存在的失败抓住，不是被变异抓住**。
根因有二：
1. 变异跑在子目录，但 `run_checks()` 用**模块顶层绑定的 `NF`** ⇒ 删 `sys.modules` **不重绑**
   ⇒ **变异根本没生效** ⇒ 永远是假阳性
2. 变异自检**没要求基线先全过**

⇒ **修**：① 变异路径 `importlib.import_module()` 重绑模块；② **基线有失败 ⇒ 变异自检直接判无效**。
⇒ 现在：**基线 4/4 过，3 个变异各自被对应检查抓住**。

* **「正确答案」参照 = DEV 金标卡**（`gold/Dxx_cards.json`）⇒ **不依赖任何抽取器**；
  金标卡的 `supports_conclusions` 决定「哪些族是真实存在的」，`is_load_bearing` 决定承重。
* **每个 δ 都带分母**（`n_samples` / `n_tasks` / `frac_nonidentical` / `degenerate`）⇒
  「δ 的估计本身也不稳」这件事被写在读数里，而不是藏在注释里。
* **⚠️ 本次读数里三个 δ 的 MAD 都退化成 0**（过半样本相同 ⇒ 绝对偏差中位数 = 0）。
  ⇒ 阈值取 `max(MAD×1.4826, mean_abs_dev)` = **0.3481**（`noise_floor.py:79` `mad_sigma` 同时返回两个估计量）。
  公式与取用规则都写在 `noise_floor.py` 的模块 docstring 里（**事前写死**）。
* **判决**：`threshold_delta(0.3481) < 0.5×典型增益尺度(2)` 且未见地板效应 ⇒ `optimization_allowed=True`。
  典型增益尺度 = 替代 config 扫描得到的臂间 `|ΔVD_net|` 中位数（`noise_floor.py:122` `default_alternatives`）。

### 2.2 地板检测为什么看 `vd_final` 而不是 `VD_net`（`optimizer.py:268`）

`VD_net` 是**相对参照臂的净增益**，优化起点上它本来就是 0（「这一版和基线一样」是正常起点），
用它当地板判据会让优化器**永远无法起步**。
契约 L0-5 说的「绝对值」指的是维度数本身（U1 批次「9/12 份 D=0」）
⇒ 判据用 **`vd_final`**（该臂在多数题上**一条维度都没造出来**），
`net_at_zero` 仍然一并报出（描述量，不用来拦优化）。

---

## 3. L1 · 信用分配（契约 §2）

* **实现在哪**：`credit.py:102` `delta_component()`（单组件消融）
  与 `credit.py:157` `credit_table()`（整表 + 分类清单）。
* **Δ 的符号约定（事前写死）**：`Δ = VD_net(完整) − VD_net(消融掉该组件)`
  ⇒ `Δ > δ` = **contributing** ｜ `|Δ| ≤ δ` = **redundant**（可删）｜ `Δ < −δ` = **reverse**（该组件在挤掉别的维度）。
  消融注册表在 `credit.py:57` `ABLATIONS`（阶段级：`stage:SPLIT/ STALL/ COLLAPSE`；参数级：`params:n_frames/ n_split_max/ stop_patience/ m_clusters/ n_cand_per_frame`；A 的臂级常量）。
* **生成与测量分开计费**：`credit.py:149` 分别报 `cost_gen`（消融臂那一趟**重新生成**的账单）与
  `cost_meas`（同一趟的**重复测量**，MiniMax 订阅 $0 ⇒ `cost_usd` 记 0，只记次数）+ `n_measurements`。
* **怎么验证**：`test_optimizer.py` 的 `credit_table_shape` / `credit_billing_split` / `credit_reverse_component`。
* **验证读数**：
  * `✓ credit_table_shape：contributing=['params:n_frames', 'params:m_clusters'] redundant=['params:stop_patience'] reverse=[]`
  * `✓ credit_billing_split：生成账 {'n_calls': 81.0, 'n_tokens': 32400.0, 'cost_usd': 0.1134} ／ 测量账 {'n_calls': 27.0, 'n_tokens': 10800.0, 'cost_usd': 0.0} ／ 测量次数 162`
  * `✓ credit_reverse_component：钉死读数下 Δ=-2（完整 0 → 消融 2）⇒ 判词 reverse`
    （合成 runner 下没有出现反向组件 ⇒ 用**钉死读数**单独构造一例，证明这条判词分支真的能被走到）
  * 一次完整跑批（`optimizer_out/credit_table.json`）：`params:n_frames Δ=+2 contributing`、
    `params:stop_patience Δ=+0 redundant`、`params:m_clusters Δ=+1 contributing`、
    `params:n_cand_per_frame Δ=+0 redundant`；生成账 108 次调用 / 43200 token / $0.1512，
    测量账 36 次调用 / 14400 token / **$0**，测量次数 360。

---

## 4. L2 · 统一 config（契约 §3）

* **实现在哪**：`config.py:276` `make_config()`、`config.py:332` `config_hash()`、
  `config.py:422` `diff_configs()`、`config.py:346` `free_degrees()`。
* **三条路线的自由度都映射成同一个对象**：

| 路线 | config 里的自由度 | 来源 | 本次读数（`python3 config.py`） |
|---|---|---|---|
| A | `params.*`（**17 项**预注册常量） | `config.py:113` `A_PARAMS`（镜像 `A/route_a.py` 的 `DEFAULTS`） | 18 个自由度（17 参数 + `prompt_version`） |
| B | `weights.w00..w29`（30 维） | `config.py:193` `b_weight_names()`（**用 AST 静态取出**，不 import `cmp8repo`） | 31 个自由度（30 权重 + `prompt_version`） |
| C | `params.*`（12 个，**当前拓扑下活 7 个**）+ `topology`（6 选 1） | `C/params.py`、`C/topology.py`（**唯一来源，不复制**） | 9 个自由度（7 活参数 + `topology` + `prompt_version`） |

* **⚠️ 与契约口径的差异（如实报，不擅自裁剪）**：契约 §0/§7 说 A 有「**12 个**预注册常量」，
  而 `A/route_a.py` 的 `DEFAULTS` 实际是 **17 项**（15 标量 + 2 facet 列表）。
  本实现**暴露全部 17 项**（裁剪＝丢自由度），并用对账项 `a_params_mirror_in_sync` 保证镜像不漂移：
  `✓ a_params_mirror_in_sync：config.A_PARAMS 17 项 vs route_a.py DEFAULTS 17 项；差集=[]`
* **怎么验证**：`test_optimizer.py` 的 `config_hash_stable` / `config_hash_changes_on_param` /
  `diff_single_freedom` / `diff_multi_freedom_raises` / `diff_no_change_raises` / `a_params_mirror_in_sync`。
* **验证读数**（摘）：
  * `✓ config_hash_stable：同 config 两次哈希相同：sha256:79a29a2fadc4226e`
  * `✓ diff_single_freedom：单自由度改动 ⇒ 报出 'params.n_frames'`
  * `✓ diff_multi_freedom_raises：如期抛出 MultiFreedomChangeError：一次改了 2 个自由度（params.n_cand_per_frame, params.n_frames）⇒ 违反契约 ①「一次只改一个自由度」`

---

## 5. 变异注入：测试自身也要被验（`test_optimizer.py:617` `MUTATIONS`）

**机制**：把 `optimizer.py` 的源码**复制一份**，用 `test_optimizer.py:234` `mutate_function()`
替换掉某个守卫/判定函数的**整个函数体**，用 `test_optimizer.py:253` `load_mutant()` 动态加载成独立模块，
再跑**同一套**自检（`test_optimizer.py:300` `selfcheck(mod, …)`）。
⇒ 变异是**源码级**的（不是 monkeypatch 影子），自检也**按模块对象参数化**（真实模块与变异模块共用同一套检查）。

| 变异 | 改坏什么 | 自检**必须** FAIL 在 | 实测失败项 |
|---|---|---|---|
| ① | 接受规则改成「接受一切」 | `accept_rule_gain_below_delta`、`accept_rule_counter_regression` | 这两项 + `optimizer_end_to_end`（决策序列从 `['accept','rollback','rollback','rollback']` 变成 `['accept','accept','accept','accept']`） |
| ② | 去掉 TEST 守卫 | `guard_dev_only`、`optimizer_rejects_test_dataset` | 这两项（均报「**没有抛异常**」） |
| ③ | 去掉「一次只改一个自由度」守卫 | `guard_single_freedom`、`optimizer_rejects_two_freedom` | 这两项 + 8 项连带（守卫一去，所有改动都判不出 `changed_freedom` ⇒ 全部被死参数守卫拦下 ⇒ 改动数 0） |
| ④（附加） | 去掉 `measure_version` 守卫 | `guard_measure_version`、`optimizer_rejects_measure_version` | 这两项（均报「**没有抛异常**」） |

* **总读数**：
  ```
  正常模式：28 项检查，全部通过
  变异注入：全部被抓住（4/4）
  ```
  退出码 0 = 正常模式 PASS **且** 4 个变异全部被抓住；任一不满足 ⇒ 退出码 1。
* **⚠️ 一处实现耦合（如实标注）**：`optimizer_rejects_two_freedom` 断言落盘里的守卫标签是
  `single_freedom`（**实现耦合**：换一种等效实现会被误判为失败）。
  但它同时断言**行为**（落盘里不得出现多自由度的「改动」记录）⇒ 行为层是稳健的。
  变异 ③ 被抓住也靠这条行为断言（守卫一去，双自由度候选就会进入「改动」）。

---

## 6. 一次完整契约跑批（合成读数）

```
python3 test_optimizer.py --demo
```

| 阶段 | 产物 | 读数 |
|---|---|---|
| L0 噪声地板 | `optimizer_out/noise_floor.json` | `δ_judge=0(n=45) δ_gen=0(n=27) δ_total=0(n=135)`；阈值 `δ*=0.3481`；典型增益尺度 `2`；`允许优化=True` |
| L3 优化轨迹 | `optimizer_out/trajectory.jsonl` | 改动 4 次，决策 `['accept','rollback','rollback','rollback']`，停止原因 `converged_no_gain_3` |
| L1 信用分配 | `optimizer_out/credit_table.json` | contributing `[params:n_frames, params:m_clusters]`；redundant `[params:stop_patience, params:n_cand_per_frame]`；reverse `[]` |

⚠️ **这些数字是合成的**：`FakeRunner`（`test_optimizer.py:64`）用 DEV 金标卡造出一个**合成响应模型**
（族数 = 拓扑基数 − 门控惩罚 ± 帧数修正，再被装配数与核验预算截断；生成侧按种子丢族、判官侧按种子翻状态、
偶尔塞一条金标干扰项）。它**只证明契约的机械逻辑跑得通**，**不模拟任何真实臂的行为**。

---

## 7. 还没做 / 做不到的（如实清单）

1. **L4 元优化器**（在 A/B/C 之上选架构、留出折、复杂度罚）——**未实现**（契约 §5 的 S5）。
2. **真实 `measure_version`** —— 现在是**占位**（`config.py:71`）⇒ 真实跑批前必须冻结四项绑定并**全部重测**。
3. **真实 runner 接入** —— 本轮只用假客户端；真实臂（路线 C 的 `executor.py`）要接到
   `generate(task, cfg, seed)` / `measure(task, answer, seed)` 这两个接口上才能用本契约。
4. **协议 §1.7 的完整族匹配** —— 本模块用**简化族键**（只取 `supports_conclusions` 排序拼接，
   丢掉 `decision_point`），因为 DEV 金标卡没有 `decision_point` 字段。真实臂的卡片有该字段时应切回完整口径。
5. **R3 的预注册预算上限** —— 契约里 `caps` 由负责人事前写死；本轮自检里没给（合成 runner 的成本是编的）。
6. **任何实验结论** —— 本轮**没有**跑真实模型、**没有**比较任何路线、**没有**产出任何优劣判断。
7. **契约 §6 的 S4**（A/B/C 各自的 L3 落地）—— 本模块是**共用**执行器；
   路线 A 的「人」走这条（提案 = 人改 DESIGN.md）、B 的 REINFORCE、C 的坐标下降都接到 `Optimizer.run()` 即可，
   但**接线本身本轮没做**。

---

*本文件描述的是**代码落地**，不是实验。契约的所有阈值（`R_meas`、`δ`、`K`、预算上限）仍需负责人确认后才冻结。*
