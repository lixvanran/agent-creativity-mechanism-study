# 路线 C · 复核意见 6a–6e 的**逐条对照表**（收尾轮）

> **日期**：2026-10-21 ｜ **对应交付**：`/workspace/lab/routes/C/`（`DESIGN.md` vC-1.1 / `spec.yaml` / `check_wiring.py`）
> **性质**：本轮**不重写设计**，只做"可执行性 + 可核对性"的收尾。**没有**跑训练、**没有**新增任何 API 调用、**没有**产出任何实验结论、**没有**声称任何路线更优、**没有**触碰 U1–U4。
> **未改的文件**：`PROTOCOL.md`（只读）、`/workspace/lab/cmp8repo/**`（有训练进程在跑）、`/workspace/lab/routes/A/**`、`/workspace/lab/routes/B/**`。

---

## 总览

| 复核编号 | 复核指出的问题 | 本轮处置 | 状态 | 一句话证据 |
|---|---|---|---|---|
| **6a** | 路线 C 的 spec 渲染成**空页**（1,683 字节 / 0 rect / 0 path / 0 text）⇒ 缺顶层 `nodes:`/`edges:` | **补上**：`spec.yaml` 顶层 8 个节点（N1–N8）+ 10 条边；DESIGN 新增 §3.1.1 与之一一对应 | ✅ | `rects=8 / paths=20 / texts=26`（门槛：rects ≥ 8、paths ≥ 7） |
| **6b** | P12 `stop_patience` 是**死代码**（`params.py` 有定义、`spec.yaml` 有条目、DESIGN 标「生效 T1–T5」，但 `executor.py` **从不读**；`=0` 与 `=3` 产出逐字相同的答案） | **选 (a) 接上**（不是删掉）：执行器新增**深挖回路** `Episode._deepen`；`stop_patience` = 装配前最多再走几步 | ✅ | 探针：T2 `stop_patience` 0→2 ⇒ **J 1.0000 → 2.0000** |
| **6b 连带** | （复核未点，**接线自检抓出来的**）P7 `stall_window` 同样是死参数：`k` 只被用作 `k<=0` 的守卫，值域 {1,2,3,4} 行为完全相同 | **接上**：P7 改成"连续空转窗口"的真参数；P8 保留"进展率"信号 ⇒ T4 有**两条互补**的停滞信号 | ✅ | 探针：T4 `stall_window` 1→4 ⇒ **J 4.0000 → 2.0000** |
| **6c** | 「提案者只接收 `structural_diagnostics(episodes) -> dict` 一个入口 ⇒ 泄漏在结构上不可能发生」—— 全仓 grep `structural_diagnostics` / `whitelist` = **0 命中** | **确认已实现且被调用**（`proposer.py`），并补**变异注入自测** | ✅ | `test_proposer.py` [9][10][11] ⇒ PASS |
| **6d** | 黑名单 glob 指向**空目录** ⇒ 子串检查根本没跑却报 PASS；「U1–U4 依据包不在本沙箱」 | **重跑**并写入真实数字；**改掉 4 处旧陈述**；加**硬规则**（跳过 ⇒ 绝不 PASS、必须非零退出）+ 自测 | ✅ | 9/9 可执行、**0 跳过**、**0 命中**（4 个源文件 / 8,820 条黑名单条目） |
| **6e** | `key_conclusion_hit` 匹配**整份机械答案**（含「依据未覆盖」「未经核验」两节）⇒ 降 `theta_util` 塞无依据文本反而抬高命中 ⇒ **C2 正确性约束可被未支持文本满足** | **改为只在「已交付 ∧ 被支持」子集上算**，并加**断言护栏** | ✅ | 被支持子集=1.00 / 整份答案(未核验文本)=1.00 / **C2 用(未核验文本)=0.00** |
| **接线盲区** | 「两个自检都看不见它：`check_spec.py` 只对账 spec↔params/topology；`test_train_loop.py` 只验回路跑得通」 | **新增 `check_wiring.py`**：每参数 ① 读点 ② 改它 ⇒ J 真的变；**带变异注入** | ✅ | 12/12 读点 + 12/12 探针 + 变异被抓住（退出码 1） |

---

## ① 6a · spec 补顶层 `nodes:` / `edges:`

**改在哪**
- `/workspace/lab/routes/C/spec.yaml`：**顶层**新增 `nodes:`（8 条，块式）与 `edges:`（10 条，块式）—— 位置在 `protocol_version:` 之后、`redlines:` 之前。
- `/workspace/lab/routes/C/DESIGN.md`：新增 **§3.1.1「规格流程图的 8 个节点」**（节点表 + 边表 + 复核命令 + 与 `spec_parsed.json` 的对应关系）。
- `/workspace/lab/routes/C/check_spec.py`：**修了自己 YAML 子集解析器的一个真实缺陷** —— 它只认「`- key: value` 后跟**同缩进**续行」，认不了**标准块式**（续行缩进更深）；而通用渲染器 `build_spec_flowchart.py` 的迷你 YAML **只支持块式**、认不了流映射（`- {id: N1, ...}` 会被解析成 `{"{id": "N1, label: ..."}` 这种坏结构）。⇒ 两者必须同时支持，才写得出一份两边都能解析的 spec。改完后 `spec.yaml` 的 `nodes:`/`edges:` 用**块式**写（与路线 A 一致），两边都解析通过。

**8 个节点是什么**：N1 生成 / N2 抽取 / N3 核验 / N4 拆分 / N5 坍缩检测 / N6 条件重组 / N7 停滞检测 / N8 机械装配 —— 即 `spec.yaml:topology.stages` 的 8 个阶段**逐一对应**（`kind`：前 7 个 `process`、N8 `terminal`）。

**为什么没有回边**：真实拓扑有 4 条回边（拆分回灌 / 深挖回路 / 条件重组回灌 / 停滞重分配）；渲染器的分层算法遇到回边会把层数炸到 **7216 px**（实测）⇒ 图不可用。⇒ 图给的是**无环可达骨架**，回边写在节点 `sub` 里，并在 `spec.yaml:topology.deep_loop` 里给了机读版说明。

**怎么验证的**
```bash
cd /workspace/lab && T=$(mktemp -d) && python3 build_spec_flowchart.py /workspace/lab/routes/C/spec.yaml "$T" "路线C" "t" && \
python3 -c "import re;h=open('$T/index.html',encoding='utf-8').read();print('bytes=%d rects=%d paths=%d texts=%d'%(len(h),len(re.findall(r'<rect',h)),len(re.findall(r'<path',h)),len(re.findall(r'<text',h))))"
# ⇒ bytes=6297 rects=8 paths=20 texts=26      （门槛：rects ≥ 8 且 paths ≥ 7）✅
```
- 另出**第二张图**（各对应各的用途）：`python3 /workspace/lab/build_topology_flowchart.py` ⇒ `visual-page/routes-flowcharts/routeC-topologies.html`（rects=36 / paths=23 / texts=89），它表达"六条阶段链谁多一个阶段、谁能看到什么"。
- 两张图都落盘到 `visual-page/spec-flowcharts/routeC/index.html` 与 `visual-page/routes-flowcharts/routeC-topologies.html`。
- `check_spec.py` 重新导出 `spec_parsed.json`（顶层 22 键，`nodes` 8 / `edges` 10），对账输出「**全部一致**」。

---

## ② 6b · P12 `stop_patience`：**选 (a) 接上**

**为什么选 (a) 而不是 (b) 删掉**：任务书建议 (a)，理由成立 ——「**何时停**」是本路线"搜索空间不过早闭合"这个核心命题的**可学版本**；删掉 P12 之后，这条命题就只剩断言、没有旋钮。**而且 (b) 会连带改动三个已写死的数字**（12 参数 / T2 活 7 个 / 68 次评估）。

**改在哪**
- `params.py`：**重新加入** P12（`values=[0,1,2,3]`, `default=1`, `group="stop"`, `applies_to=[T1..T5]`），并把 docstring 里上一轮执行者写的「已删除」段落改成「**已接上**」的实现说明。
- `params.py:FROZEN_ASSETS`：新增 **`deep_suffix`**（深挖提示词）—— 冻结资产，跨臂/跨模板一致，**不含**任何题面特征、答案暗示或评价标准。
- `executor.py`：新增 **`Episode._deepen(stages)`**（深挖回路），并在 `run()` 里**接上调用**（位置：VERIFY/SPLIT 之后、STALL 之前）。
- `executor.py`：`_stall()` 改为**只**用 P8 的"进展率"信号（P7 原来只是 `k<=0` 的守卫 ⇒ 已移出）。
- `spec.yaml`：`parameters.table` 重新加回 P12；`frozen_assets.deep_suffix`；`topology.deep_loop`（机读版的回路说明）；`objective.primary_surrogate` 改成"已交付集"口径。
- `DESIGN.md`：§2.2.2（参数表 P7/P12 两行 + 「★ 6b 的处置」段）、§2.2.3（新增深挖提示词行）、§4.1、§4.5、§4.7（新增）。

**深挖回路的语义**（写进 DESIGN §2.2.2 与 `spec.yaml:topology.deep_loop`）
1. **一步** = 换一个**已授权的认知位置**（P1 授权的那几个，**不新增位置**）+ 深挖提示词 → 抽取 → 核验。
   ⇒ **不改变 P1 的语义**（总路数不变）；**不破坏 T1「远不可得」的消融**（T1 只有「直答」一个位置，深挖只是对同一位置再问一次，不是换位置）。
2. **步数上限 = P12 `stop_patience`**：`0` = **不深挖** ⇒ 搜索空间在第一轮就闭合（=「过早闭合」的对照臂）；`k>0` = 最多再走 k 步。
3. **空转** = 一步「没有新增被支持断言」（= 没有新承重信息）⇒ 连续空转 ≥ **P7** ⇒ 判停滞 ⇒ 预算重分配（T4）。
4. **阶段集合不随 P12 改变**（深挖只是把已有的 GEN/EXTRACT/VERIFY **再执行一遍**）⇒ 分离判据仍成立：改变 P12 不改变「有哪些阶段、谁能看到什么」。

**连带修掉的 P7**：接线自检（④）报出 P7 也是死参数 ⇒ 一并接上（P7 = 连续空转窗口；P8 = 进展率阈值；两者**互补**，任一触发即判停滞 ⇒ 预算重分配）。

**三个数字复核**（选 (a) ⇒ 不用重算，但要**核对**）：参数总数 **12** ✓；T2 活 **7** 个（P1,P2,P3,P4,P5,P11,P12）✓；坐标下降评估 **68** 个配置 = 2 轮 × 34 档（5+3+5+5+6+6+4）✓；默认向量哈希 `sha256:839e98e61ea6e962`（与 `spec.yaml:parameters.default_hash` 一致）✓。

**怎么验证的**
- `check_wiring.py` 探针：T2 `stop_patience` 0→2 ⇒ **J 1.0000 → 2.0000（Δ+1.0000）** ⇒ 不是死参数。
- 手工探针（假客户端）：`patience=0/1/2/3` ⇒ episode 调用数 4/6/8/10，阶段序列出现 `DEEPEN` ⇒ 输出随参数变化。
- `check_spec.py` 对账：「全部一致」（12 个参数的 id/name/type/取值域/默认/生效拓扑 + 哈希）。

**诚实边界（写进 §4.7）**：P12 与 P1 **争用同一份调用预算**（C3 ≤ 12 次/episode）⇒ 默认配置约 10 次调用（预算内），`n_frames=5 且 stop_patience≥1` 这类组合会被 **C3 作废**。这是**约束在起作用**，不是死参数。

---

## ③ 6c · 提案者白名单：确认实现 + 变异注入自测

**复核的原话**：「提案者只接收 `structural_diagnostics(episodes) -> dict` 一个入口 ⇒ 泄漏在结构上不可能发生」—— 但全仓 grep `structural_diagnostics` / `whitelist` = **0 命中**。

**实际情况**：`proposer.py` **确实存在且确实实现了**（上一轮执行者已经写了），但 DESIGN 里的那句话**没有对应的自测**。⇒ 本轮做的是：**逐条核对 + 补上可证的变异注入自测**。

**改在哪**
- `proposer.py`：**未改逻辑**（复核的实现是对的：`structural_diagnostics` 只从白名单 `ALLOWED_KEYS` 取值；`assert_no_oracle_leak` 对序列化后的载荷做关键字扫描 + 禁浮点 + 禁白名单外键；`run_proposal` 的第一步就是 `structural_diagnostics`）。
- `test_proposer.py`：新增 **[9][10][11]** 三条自测。
- `DESIGN.md` §3.2.2：把「实现约定」改写成**可核对**的表述（代码位置 + 被调用证据 + 三条自测）。

**三条自测（`test_proposer.py`）**
| # | 做什么 | 期望 | 实测 |
|---|---|---|---|
| [9] | **变异注入（源侧）**：把 `conflict_rate_pre` / `n_supported_distinct` / `key_conclusion_hit` / `verdicts` 塞进**源 episode 字典**，再跑 `structural_diagnostics` | 载荷**逐字不变**（白名单彻底挡掉，不是"过滤后仍被看见"） | `载荷逐字不变=True` ✅ |
| [10] | **变异注入（载荷侧）**：直接往载荷里塞 `conflict_rate` / `key_conclusion_hit` / `n_supported_distinct` | `assert_no_oracle_leak` **必须抛错** | 3/3 被拒 ✅ |
| [11] | `run_proposal` 返回的 `diagnostics` 与 `structural_diagnostics` 的输出**逐字相同** | 证明入口没被绕过 | `True` ✅ |

**结论**：那句话**不是**"待实现项"—— 它在代码里成立，且现在有**能失败**的回归护栏。

---

## ④ 6d · 黑名单：重跑 + 改 4 处陈述 + 「跳过 ⇒ 非零退出」硬规则

**改在哪**
1. `verify_blacklist.py`：**v3** —— 抽出 `finalize(results)`，把「跳过」判死写进**函数**（不是只写在文档里），并新增 **`--selftest`** 模式自测这条规则。
2. `DESIGN.md` **§12.6**：旧陈述「不能在本沙箱执行协议 §4.1 的完整黑名单检查（U1–U4 依据包文件不在本沙箱）⇒ fail-closed」⇒ **改成事实**：依据包**在本沙箱**、该检查**已执行**（8,820 条黑名单条目、0 命中），并保留一条真实边界（它只覆盖路线 C 自己的文件，不覆盖协议 §4.1 对 DEV 集/抽取器的要求，那归路线 A）。
3. `DESIGN.md` **附录 B R-1**：⚠️ 部分 ⇒ **✅**（写清源路径、条目数、命中数、检查项）。
4. `train_corpus_meta.json` 的 `note`：旧陈述「与 U1–U4 的子串重叠检查**在本沙箱未执行**……⇒ fail-closed」⇒ **改成事实**，并新增机读字段 `blacklist_check`（源 glob / 4 个源文件 / 8,820 条 / 本文件 0 命中 / 检查脚本）。
5. 交付物 `deliverable.md` 的 **N2**：见本文件末尾的交付物（已改写为事实）。

**事实（重跑输出）**
```
[PASS] 黑名单源可用        命中源文件 4 个 / 黑名单条目 8820 条
[PASS] 路线C文件 × 黑名单   扫描 17 个文件，命中 0 处
[PASS] 路线C文件 × U4锚点词  命中 0 处
[PASS] 训练语料 × 黑名单    命中 0 处
[PASS] 训练标注 × 黑名单    命中 0 处
[PASS] 冒烟调用账           POST=13(上限20) 逐条记录=13 openrouter字样=0
[PASS] 冒烟日志 × 黑名单    命中 0 处
[PASS] 被测侧端点断言       smoke.py 里有端点断言
[PASS] 提案者诊断白名单入口  proposer.py 实现了 structural_diagnostics 白名单
可执行项 9 / 9；失败 0；跳过 0      结果：PASS
```
> 复核独立重跑得到的也是 **0 命中** ⇒ **红线实体成立**。本轮复核时发现的唯一命中是 DESIGN 里一个小节标题（它恰好包含 U4 答案名里的 4 字片段 = 「判定」+「规则」的组合，**纯巧合**，与 U4 无关；**注**：U4 的答案名与判准锚点词本身**不得**出现在本路线的任何文件里，因此这里也不逐字引用）⇒ 已把该小节标题改成 `### 5.2 判读规则（事前写死）`（不改变任何含义）。

**硬规则（写进代码注释 + 有自测）**
> **自检跳过任何一项检查时，绝不能输出 PASS，必须非零退出。**

- 代码：`verify_blacklist.py:finalize()` —— `code = 0 if (not failed and not skipped) else 1`；所有"跳过"分支（无黑名单源、冒烟日志不存在…）都进 `executed=False`。
- 自测：`python3 verify_blacklist.py --selftest` ⇒ 4/4 PASS（全部通过⇒0；含跳过⇒1；含失败⇒1；跳过+失败⇒1）。

---

## ⑤ 6e · `key_conclusion_hit` 只在被支持子集上算（+ 断言）

**改在哪**
- `train_params.py`：新增 **`supported_text_of(d)`**（取被支持子集文本 + **断言**）与 **`key_hit_supported(d, key_conclusions)`**；`evaluate()` 里的 C2 指标改用 `key_hit_supported`；整份答案口径保留为 `kh_any`（**仅描述性参考**，不进任何约束判定）。
- `test_train_loop.py`：新增 **[7][8]**。
- `DESIGN.md` §4.2：写清 J 的交付集口径与 C2 的 key_hit 口径（含理由与断言护栏）。

**断言护栏**：`supported_text_of()` 会检查用于计算的文本里**没有**未被支持的断言、且每一行都属于被支持子集；不满足 ⇒ **直接抛 `AssertionError`**（不静默降级）。

**实测**
```
[7] key_hit 口径：被支持子集=1.00｜整份答案(未核验文本)=1.00｜C2 用(未核验文本)=0.00（期望 1.00 / 1.00 / 0.00）
[8] 未支持断言混入 supported_text：已抛错（key_hit 的输入里混入了未被支持的断言：['机密文本']）
```
⇒ 同样一句"答案词"放在**未核验**断言里：整份答案口径会给命中（1.00），**C2 用的口径不给**（0.00）⇒ **C2 不会再被未支持文本满足**。

---

## ⑥ 接线盲区 · 新增 `check_wiring.py`（复核指出的盲区）

**复核的原话**：「两个自检都看不见它：`check_spec.py` 只对账 spec↔params/topology（**从不校验 params↔executor 接线**）；`test_train_loop.py` 只验回路跑得通。」

**新建文件**：`/workspace/lab/routes/C/check_wiring.py`

**两个断言**
1. **读点**（grep 级）：`executor.py` 里存在 `theta.get("<name>")` / `theta["<name>"]`。
2. **探针**（行为级）：**改它 ⇒ 目标函数 J 真的变**。探针跑的是 `train_params.evaluate`（**真正的训练目标函数**，不是副本），用**假客户端 + 假判官**（0 次真实 API 调用）。

**变异注入（否则是摆设）**：把 `executor.py` 里的 `int(self.theta.get("n_verify_max", 6))` 换成 `int(6)`（**在 `mktemp` 的副本上做，不碰原件**）⇒ 本自检**必须 FAIL**（退出码 1）。
实测：变异副本**同时**被 ①（读点缺失 P5）与 ②（`n_verify_max` 探针 ΔJ 归零）抓住 ⇒ 变异被抓住 ⇒ 退出码 0。

**实测输出（12/12）**
```
[PASS] 参数→执行器 读点       12 个参数的读点：全部命中
[PASS] 探针 n_frames          T2 1→3：J 1.0000 → 3.0000（Δ+2.0000）
[PASS] 探针 n_cand_per_frame  T2 1→3：J 1.0000 → 0.5000（Δ-0.5000）
[PASS] 探针 theta_util        T2 0.0→1.0：J 0.5000 → 1.0000（Δ+0.5000）
[PASS] 探针 theta_dist        T2 0.25→1.0：J 2.0000 → 1.0000（Δ-1.0000）
[PASS] 探针 n_verify_max      T2 0→12：J 0.0000 → 1.0000（Δ+1.0000）
[PASS] 探针 n_split_max       T3 0→4：J 1.0000 → 2.0000（Δ+1.0000）
[PASS] 探针 stall_window      T4 1→4：J 4.0000 → 2.0000（Δ-2.0000）
[PASS] 探针 theta_stall       T4 0.0→0.75：J 1.0000 → 3.0000（Δ+2.0000）
[PASS] 探针 realloc_frac      T4 0.0→0.25：J 1.0000 → 3.0000（Δ+2.0000）
[PASS] 探针 theta_collapse    T5 0.0→0.75：J 1.0000 → 2.0000（Δ+1.0000）
[PASS] 探针 m_clusters        T2 1→8：J 1.0000 → 2.0000（Δ+1.0000）
[PASS] 探针 stop_patience     T2 0→2：J 1.0000 → 2.0000（Δ+1.0000）
[PASS] 探针表覆盖             参数 12 个 / 探针 12 个
```

**探针的诚实边界（写进 DESIGN §4.7 / §11.1 / §12.6）**
- 探针用**刻意构造**的假语料/假判官 ⇒ 证明每个参数**能够**改变 J；**不**证明在真实语料与真实判官上**一定会**改变 J（那要等真跑；本路线尚未跑任何正式测量）。
- 探针的调用上限（24）**大于**训练期的 `CALL_CAP`（12）⇒ 目的是不让"预算超限 ⇒ 配置被截断"把参数效应掩盖掉；**预算约束由 C3 单独管**（训练期不变）。
- `P7`/`P8`/`P9`/`P10` 是**条件性生效**的参数（条件不满足时与默认值等价）—— 这是**条件性**，不是死参数，但也不能被当成"总是有贡献"。

---

## ⑦ 本轮**没有**做的事（诚实清单）

| 没做 | 为什么 |
|---|---|
| 重跑冒烟 | 不新增任何 API 调用（任务书：本任务不需要再调模型）⇒ 冒烟日志是 **01:21 的旧日志**，与现在的执行器不同源（DESIGN §9.3 / §12.9 已写明"正式批次前必须重跑一次"） |
| 跑参数训练 / 产出实验数字 | 任务书明令；且 DEV 集尚未建成（协议 §9 N1，归路线 A） |
| 改 `PROTOCOL.md` | 只读约束 |
| 改 `/workspace/lab/cmp8repo/**` | 有训练进程在跑 |
| 改 `build_spec_flowchart.py` / `build_topology_flowchart.py` | 它们是**别的路线的共用脚本**；本轮只让**自己的 spec** 适配它们（块式 `nodes:`/`edges:`），不动共用脚本 ⇒ 复核可用原脚本原样再跑 |
| 声称任何路线更优 | 全程无比较结论 |

---

## ⑧ 复核者可以原样再跑的命令

```bash
cd /workspace/lab/routes/C
python3 check_spec.py                                   # → 全部一致（exit 0）
python3 check_wiring.py                                 # → 12/12 + 变异被抓住（exit 0）
python3 verify_blacklist.py                             # → 9/9 可执行 0 跳过 0 命中（exit 0）
python3 verify_blacklist.py --selftest                  # → 4/4（exit 0）
python3 test_proposer.py                                # → PASS（exit 0）
python3 test_train_loop.py                              # → PASS（exit 0）
cd /workspace/lab && T=$(mktemp -d) && python3 build_spec_flowchart.py /workspace/lab/routes/C/spec.yaml "$T" "路线C" "t" && \
python3 -c "import re;h=open('$T/index.html',encoding='utf-8').read();print('bytes=%d rects=%d paths=%d texts=%d'%(len(h),len(re.findall(r'<rect',h)),len(re.findall(r'<path',h)),len(re.findall(r'<text',h))))"
#   ⇒ bytes=6297 rects=8 paths=20 texts=26
python3 /workspace/lab/build_topology_flowchart.py       # → routeC-topologies.html
```
