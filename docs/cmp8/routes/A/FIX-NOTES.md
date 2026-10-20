# 路线 A · 第二轮返工说明（逐条对应复核报告 F1–F15）

> **依据**：`/workspace/lab/routes/A/VERIFICATION-2026-10-21.md`（独立复核报告，**权威**）。
> ⚠️ **本文件不采信 `_OWNER_CHECKS.md` 的任何结论**（复核已逐条推翻其中 4 条）。
> **改动范围**：`DESIGN.md` / `spec.yaml` / `route_a.py` / `facets.py` / `blacklist_check.py` /
> `redline_check.py` / `dryrun_test.py` / `calibrate_thresholds.py`（新增）/ `smoke/smoke_a.py`。
> **未改**：`PROTOCOL.md`（只读）、`/workspace/lab/cmp8repo/**`（有训练进程）、共享包
> `creativity_lab/client.py`（**刻意不改**，见 F5/F15）。
> **本轮没有**：跑训练、产出任何实验结论、声称任何路线更优、调用 OpenRouter、触碰 U1–U4。

---

## 0. 汇总：本轮改了什么

| 类别 | 条目 | 状态 |
|---|---|---|
| 🔴 阻断 | F1 预算作用域、F2 `A_minus_D3` 不可实现、F3 拓扑数据依赖、F4 合取顺序、F5 meta/输出/seed、F6 校准证据悬空、F7 自检产物与文档打架 | **全部已修**（每条都有代码 + 回归断言 + 读数） |
| 🟠 重 | F8 节点编号三套、F9 对照臂无实现、F10 FA-8 恒触发、F11 交付物失真 | **全部已修** |
| 🟡 中 | F12 冒烟未覆盖预注册拓扑、F13 `openrouter_used` 硬编码、F14 字数上限/顺序偏置/计数不同源、F15 不记实际模型 | **全部已修** |
| 🟡 **新发现** | **F16：预注册的 40k token 上限装不下预注册的拓扑**（实测一个 rep 46,217 token ⇒ DS-01 作废） | **已登记 + 已做留痕的预注册修订**（40k→60k，依据/时点/未验证项全部写明，见 §F16 与 `DESIGN.md` §3.5） |

**本轮新增的产物**：`calibrate_thresholds.py` + `calibration_log.{txt,json}`（F6）、
`FIX-NOTES.md`（本文）、`smoke/archive_v1/`（上一轮冒烟日志留档）。

---

## F1｜`max_tokens` 预注册为「每臂每任务每 rep」，实现却是**进程累计** → 🔴 已修

**改在哪**
- `route_a.py:305`（`_Runner.__init__`）：新增 `self._tokens_at_start = getattr(llm, "n_tokens", 0)`。
- `route_a.py:311-315`：`calls()` / `tokens()` 改为**本次 route 调用内的增量**
  （`tokens()` = `llm.n_tokens - self._tokens_at_start`）。
- 旧版 `route_a.py:240-241/261-262`（模块级 `_tokens()` 直接返回 `llm.n_tokens`）已删除。
- `route_a.py:73`（`DEFAULTS`）：`max_tokens=40000` 的注释补上作用域「每 (臂,任务,rep)」。
- `DESIGN.md` §3.5 常量表（`max_tokens` 行）、§3.6（预算守卫两行）、§8.1（成本表）同步改口径。
- `spec.yaml` 的 `constants.max_tokens_per_rep` 保留 40000，注释写明作用域。

**怎么改的**：与 `max_calls` 同一款修法——在 runner 初始化时记下起点，守卫与 `meta.n_tokens`
一律用**增量**。这样共享同一个 LLM 对象连跑 3 题时，第 2/3 题的 token 计数与预算都不含前序任务。

**怎么验证的**
- `dryrun_test.py` 的「F1 回归」段（打桩 LLM，0 次 API）：连跑 3 题，逐题打印 `n_calls/n_tokens`。
- 断言「任务 2 的 token 计数不含任务 1」：`per_task[1] == per_task[0] and per_task[2] == per_task[0]`，
  且三题都**不得**抛 `BudgetExceeded`。

**验证读数**（`python3 dryrun_test.py`）
```
== F1 回归：token 预算按任务计（连跑 3 题，第 3 题不得被中止） ==
  任务 1: n_calls=5 n_tokens=2000
  任务 2: n_calls=5 n_tokens=2000
  任务 3: n_calls=5 n_tokens=2000
  三个任务的 token 计数：[2000, 2000, 2000] ⇒ 逐题独立
```
⚠️ **实测边界**：这是**离线**回归（守卫逻辑是纯本地计算，不需要 API）。
活体多任务路径由冒烟的第二题覆盖（§F12 的 `multitask_budget_is_per_task` 自检项），
但**活体只跑了 2 题**，3 题连跑的活体验证**没有做**（本轮 API 预算 ≤20，见 §F12）。

---

## F2｜`A_minus_D3` 臂不可实现（`structured_no_cover` 不被执行器识别）→ 🔴 已修

**改在哪**
- `facets.py:122-133`：**新增独立模板 `RESAMPLE_Q_NC`**（整段**没有**「已覆盖清单」）。
- `facets.py:209`：把 `RESAMPLE_Q_NC` 纳入 `injected_strings()`。
- `route_a.py:373-384`（`_Runner.resample_prompt`）：`resample_mode` 的四个取值各有分支——
  `random` → 占位文本；`structured_no_cover` → `RESAMPLE_Q_NC`；其余 → 带清单的 `RESAMPLE_Q`。
- `route_a.py:66-70`（`DEFAULTS`）：`resample_mode` 注释写明四个合法取值。
- `route_a.py:634` 附近（`run_route` 开头）：`resample_mode` **不在合法集合 ⇒ 直接抛 `ValueError`**
  （不再静默落进「带清单」分支）。
- `spec.yaml` 的 `arms.A_minus_D3` 补注「必须是独立模板，否则该臂静默退化 ⇒ FA-7 恒触发」。
- `DESIGN.md` §3.4（贴出 `RESAMPLE_Q_NC` 全文 + 为什么必须独立）、§7.2 的 FA-7 行。

**怎么改的**：给消融臂一个**真正独立**的 prompt 模板；并把「非法 `resample_mode`」变成**硬失败**
而不是静默走默认分支（这是这条 bug 的根因：静默降级）。

**怎么验证的**：`dryrun_test.py` 的「F2 回归」段——把每个消融臂的**生成提示词列表**与 `A_fixed`
**逐字节**比较，要求**必须不同**；`A_minus_R2` 另要求 `round2_executed is False`。

**验证读数**
```
== F2 回归：每个消融臂的第二轮 prompt 必须与 A_fixed 逐字节不同 ==
  A_minus_D3     与 A_fixed 的提示词不同 ✔
  A_random_rest  与 A_fixed 的提示词不同 ✔
  A_minus_facet  与 A_fixed 的提示词不同 ✔
  A_minus_R2    round2_executed=False ✔
```

---

## F3｜「固定拓扑 / 完全固定」不成立（`collapse_mult` 其实是开关）→ 🔴 已修（取「真固定」那一支）

**改在哪**
- `route_a.py:657-666`（N3）：`collapse_flag` 变成**纯诊断量**
  （`meta_extra["collapse_flag"] = bool(kept_r1 < thr)`），**不再**参与任何分支判断。
- `route_a.py:668-683`（N4）：第二轮的触发条件改成
  `if C["resample_mode"] != "none" and C["round2_facets"]:` —— **臂级常量**（与数据无关），
  不再看塌缩量。⇒ N4 **恒定执行**。
- `route_a.py:664` 附近：新增 `meta_extra["round2_executed"]`（是否真的做了第二轮）。
- `DESIGN.md`：§2.1 表的 D6 行、§2.7（D6 弃用理由 + **路线 A 自己遵守同一条纪律**）、
  §3.1 图（N4 标「恒定执行」）、§3.2 伪代码、§4.4（新增一行失败模式）、§8.1（成本表改为固定成本）、
  §11（无新增条目，但 §3.5 的 `collapse_mult` 行改为「纯诊断量」）。
- `spec.yaml`：`nodes.N3.notes`（诊断量，不控制分支）、`nodes.N4.condition`
  「恒定执行（臂级常量；**无数据依赖的开关**，F3）」、`constants.collapse_mult` 注释、
  `hard_constraints` 新增一条「N4 恒定执行；塌缩量只做诊断量，不得当开关」。

**怎么改的**：取复核建议的 **(a) 真做成固定**——`collapse_mult` 只诊断、不控制。
「`resample_mode='none'`（消融臂 `A_minus_R2`）」是**臂级常量**（每条臂固定一个值），
不是数据依赖开关 ⇒ 不违反「固定拓扑」的定义，这一点在 §2.7 写明。

**怎么验证的**：`dryrun_test.py` 的「F3 回归」段——用 `collapse_mult ∈ {0.0, 1.0, 99.0}` 各跑一次，
断言 `round2_executed` **恒为 True**，并断言 `collapse_flag == (collapse_kept < collapse_threshold)`
（诊断量与公式一致）。

**验证读数**
```
== F3 回归：塌缩量是诊断量，不控制 N4 ==
  collapse_mult=0.0   ⇒ round2_executed=True collapse_flag=False (kept=3 thr=0.0)
  collapse_mult=1.0   ⇒ round2_executed=True collapse_flag=False (kept=3 thr=1.0)
  collapse_mult=99.0  ⇒ round2_executed=True collapse_flag=True (kept=3 thr=99.0)
  collapse_mult=99.0 ⇒ collapse_flag=True（诊断量仍如实报告）
```

---

## F4｜Mednick 合取实现顺序错误（「远」在「有用」之前，作用于未过滤的池）→ 🔴 已修

**改在哪**
- `route_a.py:436-513`（`_Runner.d2_and_assemble`）：**重排为「效用轴先、新颖轴后」**——
  ① 先核验（`verify()`）得到 `verdicts`；② 由 `verdicts` 决定**可交付子集**
  （`supported_idx`，`route_a.py:450-456`）；③ **只在该子集上**做去冗余
  （`keep_sets(scope_texts)`）。
- `route_a.py:489`：**装配期冗余否决**——loose 条目若与「已装入答案的条目」在**任一实现**下冗余
  ⇒ 不再装入（`n_dup_suppressed` 计数）；且**受 `novel_axis` 开关控制**（消融臂 `A_minus_novel`
  关闭的是整个新颖轴 ⇒ 否决权一并关闭）。
- `route_a.py:208`（`RedundancyJudge.any_impl`）：新增「任一实现命中」的判定。
- `DESIGN.md` §4.3 整节重写（新增「代码实际保证什么」表：池层面 / 装配层面 / 跨轴顺序）、
  §1.3 决定 1 的「保证」措辞、§3.2 伪代码、§4.6、§11 A-9（新增局限）。
- `spec.yaml`：`nodes.N7.axis_order`「效用轴先、新颖轴后（F4）」。

**怎么改的**：先把「有用」判完，再在**可交付子集**上判「远」；
并在装配阶段对已装入条目保留冗余否决权 ⇒ 「改写型重复不得同时进答案」成为**代码事实**。

**怎么验证的**：`dryrun_test.py` 的「F4 回归」段（两个探针，打桩 LLM）：
- 探针 1：`pool = [未支持的近似重复项, 被支持的条目]`，**两种顺序**都跑 ⇒
  断言「被支持的条目**必须**在答案里」（旧版会随顺序翻转而消失）。
- 探针 2：两条**改写型重复**且都被支持 ⇒ 断言**不得同时**进答案。

**验证读数**
```
== F4 回归：未被支持的近似重复项不得挤掉被支持的条目 ==
  junk 在前 → 答案含被支持条目：True
  good 在前 → 答案含被支持条目：True

== F4 回归：改写型重复不得同时进答案 ==
  两条改写型重复同时进答案：False（n_dup_suppressed=1）
```
⚠️ **口径提醒**（已写进 `DESIGN.md` §1.3 / §4.3 / §11 A-9）：本判据是**离散词面/结构级**的，
**抓不住语义等价的自由改写** ⇒ 现在的保证是「与已装入条目在离散判据下不冗余」，
**不是**「不是同义反复」。

---

## F5｜32 个声明的 `meta.json` 字段里 20 个无代码产出；`seed` 整条链不存在 → 🔴 已修

**改在哪**
- `route_a.py:525-620`（`_build_meta`）：**按字段表逐条落地**（身份/预算/有效性/内容/比率/装配/诊断/透明
  八组，见 `DESIGN.md` §6.4 的表）。
- `route_a.py:865-877`（`save_run`）：**实现协议 §8 (a2) 的输出**（`RUNS/<arm>/<task>/rep<k>.answer.md`
  + `.meta.json`）。
- `route_a.py:879-910`（`run_task`）：预算溢出（协议 E4）⇒ 该样本**作废并计数**
  （`over_budget_count=1`）而不是把异常抛给调用方。
- `route_a.py:32-42`（`PROTOCOL_SIDE_FIELDS`）+ `route_a.py:612-618`（`protocol_a4_not_produced`
  / `metadata_missing`）：协议 §8 (a4) 里**属协议侧**的 10 个字段（`judge_*` / `embedding_model` /
  `aligner_version` / `extractor_*`）**显式登记为「本路线不产出」**（不代填、不假装有）。
- `route_a.py`（`DEFAULTS` 之上）：新增 `PROMPT_VERSION = "ROUTE-A-prompt-v2.0"`（`facets.py:36-39`）。
- **seed 的处理（按任务书要求「如实写，不要写『已固定种子』」）**：
  共享 client 的 `chat()` **没有 seed 参数**（`/workspace/lab/creativity_lab/client.py`），
  本轮**刻意不改共享包**（会影响路线 B/C）⇒
  `meta.seed` = **运行标签**（S1/S2/S3）、`seed_effective = null`、
  `seed_policy = "api_seed_unsupported__label_only__NOT_reproducible"`、
  `reproducibility = "not_reproducible__no_api_seed_parameter"`。
- `DESIGN.md` §3.5（`seed` 行）、§4.4（可复现性行）、§6.4（**逐组的字段表**）、§11 A-10（新增局限）、
  §9.3 (a2)/(a4) 两行。
- `spec.yaml`：`constants.seed_policy` / `seed_labels`、`io.output`（含 `written_by`）。

**怎么改的**：把「声明」变成「代码」——每个字段都有产出点；**协议侧该由别人产的字段**，
用两个专门的字段**显式登记为缺**，而不是留空。

**怎么验证的**
- `dryrun_test.py` 的「F9 回归」段：对 **B0/B1/B2/B3 四条臂**逐个断言 33 个必需字段**一个不缺**。
- 「输出契约」段：写盘后断言 `rep1.answer.md` 与 `rep1.meta.json` 都存在。
- 冒烟：`smoke_log.json` 的 `runs_written` 记录**实际写出的两个路径**（冒烟确实写到了
  `/workspace/lab/routes/RUNS/A_fixed/...`）。

**验证读数**
```
== F9 回归：B0/B1/B2/B3 可执行且与 A 臂同构 ==
  B0   calls=3 tokens=1500 shipped=2 缺字段=无
  B1   calls=5 tokens=2500 shipped=2 缺字段=无
  B2   calls=6 tokens=3000 shipped=2 缺字段=无
  B3   calls=6 tokens=3000 shipped=2 缺字段=无
  B1 缺 K ⇒ 报错 ✔

== 输出契约：RUNS/<arm>/<task>/rep<k>.{answer.md,meta.json} ==
  rep1.answer.md / rep1.meta.json 存在：True
```

---

## F6｜预注册阈值的**校准证据悬空** → 🔴 已修（重跑标定，真实读数落盘）

**改在哪**
- **新增** `calibrate_thresholds.py`：**离线**标定脚本（**0 次 API 调用**）。
  自造合成语料 = 37 条断言（27 条基础 + 5 条近逐字重复 + 5 条改写型重复），
  标注 = 10 组重复对（5 组词法类 + 5 组结构类）+ 10 组**非重复**对照对；
  对 `lex_thr ∈ {0.60…0.90}`、`struct_thr ∈ {0.50…0.85}` 各做一次扫描。
  **未使用 DEV 集、未使用 U1–U4**（语料是虚构的「仓储配送计费规则」）。
- **新增产物** `calibration_log.{txt,json}`（人读 + 机读）。
- `DESIGN.md` §3.5：`lex_thr` / `struct_thr` 两行**换成真实读数**（原来写的「27 条保留 27 条 /
  27→25」和「记于 `smoke/smoke_log.txt`」是悬空引用，已删除）；并写明**本轮未改任何预注册值**
  （理由：扫描显示 0.60–0.80 区间读数几乎一致，预注册值落在区间中部 ⇒ 没有改动的理由，协议 R-9）。
- `DESIGN.md` §11 新增 **A-12**（标定语料的局限：单一领域、小样本 ⇒ 只能声称「读数已知」）。
- `spec.yaml`：`meta.implementation.calibration` 指向新脚本。

**怎么改的**：不再声称「在冒烟日志里」（那里根本没有那些读数），而是**重跑一次标定**，
把语料、标注、扫描曲线、结论**原样落盘**并让 DESIGN 引用它。

**验证读数**（`python3 calibrate_thresholds.py` → `calibration_log.txt`）
```
标定集：本文件自造的合成断言语料（虚构仓储配送计费规则），**不是** DEV 集、**不是** U1–U4
语料规模：37 条断言（基础 27 / 近逐字重复 5 / 改写型重复 5）
【预注册值读数】lex_thr=0.75  struct_thr=0.70
  近逐字重复对被实现1（词法）命中：5 / 5；被任一实现命中：5 / 5
  改写型重复对被实现2（结构）命中：5 / 5；被任一实现命中：5 / 5
  全部标注重复对被任一实现命中：10 / 10
  **误杀**（非重复对被判冗余）：0 组
  漏掉的重复对：0 组
  贪心 keep 集：strict=26 / loose=33 / impl1=30 / impl2=29（语料共 37 条）
```
（扫描表与结论在 `calibration_log.txt` 里完整保留。）

---

## F7｜自检产物自身记录 FAIL，文档却标 ✅；黑名单脚本**空目标仍 exit 0** → 🔴 已修

**改在哪**
- `blacklist_check.py:136-152`：**空目标守卫**——① 命令行没给被扫文件；② 扫不到任何存在的文件；
  ③ 找不到 U1–U4 的 `user4_*.json`；④ strict 黑名单为空 ⇒ 任一触发即
  `status="NOT_RUN"` 且 **exit 2**（**绝不**能 exit 0）。
  另加 `files_scanned` / `files_missing` 计数（复核指出的「`source_files=8` 被误读成『没跳过』」的坑）。
- `redline_check.py`：**扫描范围分三层**——
  ① `facets.injected_strings()`（**会发给模型**的字符串）⇒ 评价口径词命中 = **hard fail**；
  ② `facets.derivation_strings()`（**只给复核者看**的推导注释）⇒ 命中**只报告、不判失败**
  （`R2_rubric_term_hits_in_derivation_only`）；
  ③ **执行器实际发出的 prompt**（`redline_check.py:81-130`：用打桩 LLM 把三种
  `resample_mode` 各跑一遍真执行器，抓 24 条实际 prompt）⇒ 最强的一层。
  另加**空扫描守卫**（注入串 <10 条 / 实际 prompt 为空 / 黑名单没扫到文件 ⇒ 判失败，exit 2）。
- `facets.py:200-232`：`injected_strings()` / `derivation_strings()` 拆分（`facet_text()` 只取第 2 列）。
- `DESIGN.md` §3.3（目录纪律第 1 条）、§9.4（**整表重写**：第三列改成「产物里的读数」）、
  §4.3/§11 等与自检冲突的措辞一并对齐。

**怎么改的**：不是「把检查改松」，而是**把检查对象改对**（检查模型真正看到的东西），
并给每一层加「空 ⇒ 失败」的守卫。

**验证读数**
- `python3 redline_check.py` ⇒ `exit 0`；`redline_check.json`：
  `hard_fail_total=0`、`all_pass=true`、`guards_failed=[]`、
  `injected_strings_checked=19`、`prompt_level_prompts_checked=24`、
  `R2_rubric_term_hits=[]`、`R2_prompt_level_hits=[]`、`M4_prompt_level_evidence_leak=[]`、
  `R1_blacklist_strict_hits=0`、`R1_blacklist_files_scanned=8`；
  `R2_rubric_term_hits_in_derivation_only` = 2 条（FA1/FA6 的**推导注释**里的「承重」，只报告）。
- `python3 blacklist_check.py`（**无参**）⇒ **exit 2**、`status="NOT_RUN"`、
  `guards_failed=["no_target_args: …", "no_files_scanned: …"]` ⇒ 旧版「一个文件都没扫却 exit 0」的形态已消除。
- `python3 blacklist_check.py $(find /workspace/lab/routes/A -type f …)`（扫**全部**路线 A 文件，
  **27 个**）⇒ `status="PASS"`、`files_scanned=27`、`strict_hits=0`。
  ⚠️ 剩下的 **4 个 hint 命中全部在 `VERIFICATION-2026-10-21.md`**（**复核者自己写的报告**，
  里面引用了 U1–U4 的题面片段 ⇒ 通用 4 字 n-gram 命中），
  **路线 A 自己的文件 hint 命中 = 0**（本轮把 DESIGN 里唯一一处「的最后一」改写掉了）。

---

## F8｜节点编号三套并存 → 🟠 已修（统一为 N0–N8）

**改在哪**
- `DESIGN.md` §3.1：图重画为 **9 个节点 N0…N8**（新增 N0「读题/装配输入」；N5/N6 拆开；
  N8 = 「机械装配 + 自检与记账」），并写明「与 `spec.yaml` 一一对应」。
- `spec.yaml`：`nodes:` 全部改成 N0…N8（与图同名同序），`edges:` 改成**块状**写法。
- `route_a.py` 模块 docstring：拓扑段改成 N0…N8。
- `dryrun_test.py`：`stage_counts` 的键名与节点号对齐（`n7_dedup_*` / `n8_shipped` 等）。

**顺带修掉的一个真 bug（复核没列，但属同一类「声明 ↔ 实现不一致」）**：
`spec.yaml` 的 `edges:` 原来用行内 `{from: N0, to: N1, …}` ⇒ `build_spec_flowchart.py` 自带的
极简 YAML 解析器把它解析成 `{'{from': 'N0, to: N1, …'}` ⇒ **渲染出来的是一条链，不是这张 DAG**
（复核看到的「非空图」其实是一串直线）。改成块状写法后，解析器读出的边与 PyYAML 一致。
另外：spec 里所有**行尾注释**也改成了整行注释（极简解析器会把 `1.0  # 注释` 整串当字符串）。

**怎么验证的**
- `python3 /workspace/lab/build_spec_flowchart.py routes/A/spec.yaml <out> "路线A" "t"` ⇒ 渲染成功；
  解析结果：`nodes=9`（N0…N8）、`edges=10`（**不再是 0**）、节点名与 DESIGN 的图逐条对应。
- 渲染产物读数：9 个节点标签、8 个 `rect` + 1 个 `io` 多边形、20 条 `path`（10 条边 × 2）、
  28 个 `text`（9 标签 + 9 副标 + 10 边标签）。

---

## F9｜等预算对照臂 B0–B3 无任何实现 → 🟠 已修

**改在哪**
- `route_a.py:762-860`（`run_b_arm(kind=…)`）：实现 **B0 / B1 / B2 / B3** 四条臂，
  与 A 臂**共用同一条尾**（抽取→拆分→D2 门→装配）。
  - B0：1 次**无承载面指令**的直调。
  - B1：**K 次**直调，**固定取最后一份**（内容无关的选择规则）。
  - B2：采样到 **token 预算 `T_W`** 为止，**固定取最后一份**。
  - B3：K 份候选 + **外部核验器**择优（`selector` 可注入；默认实现用依据包核验，
    判官调用 ≠ 生成调用，但**同厂商** ⇒ 已在 `DESIGN.md` §5.1 与 `spec.yaml` 注明）。
  - 缺 `K` / 缺 `T_W` ⇒ **抛错**（不静默取默认值）。
- `DESIGN.md` §5.1：四条臂的实现列 + 「K 与 T_W 必须按本路线实际值填」的口径 + B3 的同厂商限制。
- `spec.yaml`：`arms` 的 B0–B3 补 `notes`（实现位置 + 限制）。

**怎么验证的**：`dryrun_test.py` 的「F9 回归」段——四条臂各跑一次，断言 (a) 可执行、
(b) meta 必需字段一个不缺、(c) B1 缺 K 报错。

**验证读数**：见 F5 的读数块（B0–B3 四行「缺字段=无」）。

---

## F10｜FA-8 措辞使 `A_minus_utility` 臂**恒触发**；「负对照预期更差」与代码矛盾 → 🟠 已修

**改在哪**
- `DESIGN.md` §7.2：**FA-8 拆成两条**——
  - **FA-8a（新颖轴）**：在 `A_fixed` **确实因新颖轴改变了装配**（`n_dup_suppressed > 0`）的题上，
    `VD_net(A_fixed vs A_minus_novel)` 任务级中位数 ≤ 0；若新颖轴在所有题上都没改变装配 ⇒
    **写「不可判定」**（不是触发，也不是通过）。
  - **FA-8b（效用轴）**：在 `A_fixed` **确实有条目被效用门挡掉**的题上，
    `VD_net(A_fixed vs A_minus_utility)` 任务级中位数 ≤ 0；
    **不拿矛盾率判本条**（`A_minus_utility` 不做核验 ⇒ `conflict_rate_generated` **构造上恒为 0**）。
- `DESIGN.md` §5.2 脚注：删掉「**预期**更差（F2/G2/**R1** 触发）」，改成
  「作用不是『赢』，而是**提供否证的机会**」＋ 明确写「`A_minus_utility` 的矛盾率构造上恒为 0 ⇒ R1 不可能为它触发」。
- `DESIGN.md` §7.2 开头：新增**硬纪律**——「任何否证条件都不得是『对任何数据都必然触发』的」，
  并说明本轮据此改了 FA-7 / FA-8 / FA-8 的措辞。
- `spec.yaml`：`falsification.route_specific` 里 `FA-8` ⇒ `FA-8a` / `FA-8b`；
  `arms.A_minus_utility.tests` ⇒ `FA-8b`，`arms.A_minus_novel.tests` ⇒ `FA-8a`。

**怎么改的**：把一条**恒真**的否证条件换成两条**带前置条件**（该轴确实起了作用）的条件，
并把「预期」这种与代码矛盾的预测删掉。

**怎么验证的**：
- 构造性验证：`A_minus_utility` 的 `conflict_rate_generated` 恒为 0 ⇒ 代码里
  `conflict_rate_generated=res["n_bad"]/max(n_sup+n_bad, 1)`，该臂 `n_bad ≡ 0`。
- 回归断言：F2 段保证 `A_minus_utility` 臂真的存在且与 `A_fixed` 不同；FA-8a/8b 的
  「该轴确实起作用」前置条件由 `n_dup_suppressed` / 被支持条目数 < 池大小两个**可计算量**给出。

---

## F11｜`deliverable.md` 对 `facets.py` 的目录描述与代码不符；三处计数误述 → 🟠 已修

**改在哪**：**重写** `deliverable.md`
（`/workspace/.mavis/plans/plan_9e024318/outputs/t1-routeA/deliverable.md`）：
- 承载面目录改写成**代码里的真实六条**：适用范围与情形范围 / 依据与约束 / 数量与门槛 /
  情形分支与差异 / 例外与失效条件 / 缺口与不确定（旧的「主体间权利义务关系」「程序步骤与时限」
  在代码里根本不存在，删掉）。
- 拓扑：**9 个节点 N0–N8**（旧的「8 节点」与列出的 9 个自相矛盾）、「顶层 `nodes:` 9 个、
  `arms:` 11 个」（旧的「20 个」是两块相加）。
- 冒烟暴露的缺陷数：按 `DESIGN.md §10.3` 的**四个**写（旧的「两个」是误述）。

---

## F12｜活体冒烟只跑了缩小版拓扑（2+1 / 2+0），预注册路径从未触发 → 🟡 已修（附限制说明）

**改在哪**
- `smoke/smoke_a.py`：诊断题改为
  - **DS-01 = 预注册拓扑**：第一轮 **FA1–FA4（4 个承载面）** + 第二轮 **FA5–FA6（2 个承载面）**，
    `collapse_mult=1.0`、`extract_cap=8`、`max_claims=48`、`verify_batch=12`、`max_calls=24`。
  - **DS-02 = 小题**（1 槽位、无第二轮）：在**活体**上验证「共享 LLM 对象的多任务不被前序任务卡死」（F1）。
- 自检项新增：`preregistered_topology_round2_executed`（FA5/FA6 真的对活模型跑过）、
  `multitask_budget_is_per_task`、`every_answer_within_char_cap`、`runs_outputs_written`。
- 上一轮（缩小版拓扑、12 次调用）的日志**留档**在 `smoke/archive_v1/`，不删。

**验证读数**（`smoke/smoke_log.txt` / `.json`）
```
总调用数 18 / 20，总 token 50637，逻辑调用 16
自检：{... "preregistered_topology_fa5_fa6_called": true,
      "preregistered_topology_round2_executed_in_meta": false,
      "no_sample_invalidated": false, "multitask_budget_is_per_task": true,
      "every_answer_within_char_cap": true, "runs_outputs_written": true,
      "all_api_urls_are_minimax": true, "evidence_not_in_generation_prompts": true,
      "within_global_call_cap": true, "every_task_has_parsed_verdicts": true,
      "prompts_parse_all_nonempty": true,
      "no_openrouter_in_prompts_or_endpoints": true}
读数：{"evidence_leak_count": 0, "n_resample_fa5_fa6_calls": 2}
作废样本：[{"tid": "DS-01", "reason": "token 预算不足：已用 46217 / 上限 40000",
            "tokens_used": 46217, "token_cap": 40000,
            "note": "预算溢出的样本**作废并计数**（协议 E4）；不是被截断后照常算"}]
```

⚠️ **本条的诚实边界**：
1. 本轮**只跑了 1 道预注册拓扑的题**（+1 道小题）。原预注册是「4+2 承载面」——
   **承载面维度已覆盖**（FA1–FA4 + FA5–FA6 全部对活模型跑过：
   `n_resample_fa5_fa6_calls = 2`），但**题目数**没有扩到多题。
2. ⚠️ **DS-01 的样本作废了**（预算溢出）⇒ 它的**答案**没有产出；
   但 **FA5/FA6 的代码路径确实在活模型上跑过了**（判据取自**调用日志**，不是 meta）。
3. `collapse_mult=1.0` 这条**预注册配置**现在**必然被执行**（因为 N4 恒定执行，F3），
   但「塌缩诊断量恰好为 True 的那一题」**没有**被专门构造出来。
4. 活体**3 题连跑**的 F1 验证**没有做**（API 预算 ≤20）。
5. ⚠️ **本轮冒烟最重要的副产品**：预注册的 40k token 上限**装不下**预注册拓扑 ⇒ 见下面 §F16。

---

## F16｜**本轮新发现**：预注册的 40,000 token 上限装不下预注册的拓扑（预注册修订 R-1）→ 🟡 已登记 + 已修订（带依据）

**怎么发现的**：F12 的修复要求冒烟跑**预注册拓扑**（4+2 承载面）—— 上一轮的缩小版拓扑
（2+1 承载面、12 次调用 / 23,727 token）**永远看不到这个问题**。

**读数**（`smoke/smoke_usage.json` + `smoke_calls.jsonl`）
```
DS-01（预注册拓扑）：13 次逻辑调用 / 15 次 API 调用 / 46,217 token
  └ 其中 2 次是共享 client 的**过载降级**（MiniMax-M3.1-Flash-Preview → MiniMax-M2.7，
     整次重试）⇒ 降级多花 12,245 token
  └ 去掉降级重试的**固有用量 ≈ 33,972 token**
DS-02（小题）：3 次调用 / 4,420 token  ⇒ 正常
```
⇒ 40,000 的余量只有约 6,000 token ⇒ **一次过载降级就可能把它吃掉** ⇒ 样本按协议 E4 作废。

**怎么改的**（**不是**偷偷改值，而是**留痕的预注册修订**）：
- `route_a.py` 的 `DEFAULTS.max_tokens`：40,000 → **60,000**（注释里写明依据与未验证项）。
- `spec.yaml` 的 `constants.max_tokens_per_rep`：同上。
- `DESIGN.md` §3.5 新增「**预注册修订记录**」表（R-1）：原值 / 新值 / **依据（可查的读数）** /
  时点（**任何 DEV 数据之前**）/ **未验证项**。
- `DESIGN.md` §4.4、§8.1 的 token 口径同步；§11 新增 **A-14**（40k 与拓扑不兼容）与
  **A-15**（降级重试放大 token 记账）。

⚠️ **为什么这不是「事后改口径」**（协议 R-9）：R-9 禁止的是**在看到实验结果之后**改口径。
本轮**没有任何实验结果**（未建 DEV 集、未跑 DEV 题、没有任何维度数/矛盾率读数），
改的是**可行性上限**，依据是**冒烟的用量读数**（属 §3.5 允许的「事前标定」范畴）；
而且**旧值下的失败被如实保留在日志里**（DS-01 作废的事实没有被掩盖）。
⇒ **替代方案（留给下一轮选）**：(a) 维持 40k 并把核验批 12→24（核验调用 4→2 次，预计省 ~15k）；
(b) 维持 40k 并接受预注册拓扑的高作废率；(c) 采 60k。**本轮采 (c)。**

⚠️ **未验证项**：60,000 **未经活体验证**（本轮 API 预算 20 次已用 18 次，剩 2 次不足以重跑 DS-01）
⇒ 跑批前应重跑一次预注册拓扑确认。

---

## F13｜`smoke_log.json` 的 `openrouter_used=false` 是**硬编码字面量** → 🟡 已修

**改在哪**
- `smoke/smoke_a.py:148`：`openrouter_used = any("openrouter.ai" in (u.get("url") or "") for u in usage)`
  —— 由**实际调用 URL** 计算。
- 另加两个自检项：`all_api_urls_are_minimax`（每条 URL 都以 `https://api.minimaxi.com/v1` 开头）、
  `endpoints_seen` / `models_seen`（把实际用到的端点与模型**列出来**，可被复核者逐条核）。
- `smoke/smoke_a.py:211`：人读日志里写「OpenRouter : 未使用（由 N 条实际调用 URL 计算，非硬编码）」。
- `DESIGN.md` §9.4 的 R-8 行、§0 状态表：引用方式改成「由实际调用 URL 计算」。

**验证读数**：见冒烟日志的 `endpoints_seen` / `openrouter_used` / `all_api_urls_are_minimax`。

---

## F14｜① 400 字上限只管条目正文 ② 超限 `break` 而非 `continue` ③ 截断计数分子分母不同源 → 🟡 已修

**改在哪**
- ① `route_a.py:470-478`：**上限覆盖整份答案**——先算固定开销
  （`# {ask}` + 段标题），`item_budget = answer_char_cap - fixed` ⇒ `len(answer) ≤ 400` 恒成立。
  `DESIGN.md` §3.5（`answer_char_cap` 行）、§4.6（新增「上限口径漂移」一行）、§8.1。
- ② `route_a.py:495`：`break` → **`continue`**（超限只跳过这一条，后面的短条目仍有机会进答案）。
  `dryrun_test.py` 的 F14 段用「一条 > 70 字段 + 一条短条目」验证短条目仍在答案里。
- ③ `route_a.py:505-512`：截断计数**分子分母同源**——主路径 `n_supported`，
  兜底路径 `n_fallback_eligible`；并新增 `answer_truncated_denominator` 字段说明用的是哪个总体。
  `DESIGN.md` §4.6、§6.4（字段表）同步。

**验证读数**
```
== F14 回归：超限的条目不得把后面的短条目一起丢掉 ==
  答案字数=173 含短条目：True
```
（正常路径的 `answer_chars` = 158 ≤ 400；冒烟里每一题都断言 `answer_chars ≤ 400`。）

---

## F15｜共享 client 会按 `FALLBACKS` 静默换模型，而 meta 不记实际模型 → 🟡 已修

**改在哪**
- `route_a.py:317-322`（`_Runner._models_since`）+ `route_a.py:340-346`（`call()` 记录本次调用实际用到的模型）：
  共享 client 的 `client.rec[i].model` 记的是**实际发出去**的模型 ⇒ 逐次收集到 `self.models_used`。
- `route_a.py:525-620`（`_build_meta`）：新增 `model`（缺省请求档位）、`model_requested`、
  **`models_used`（实际用过的模型）**、`models_tier`。
- `route_a.py:132-137`（`MeteredLLM._post`）：把 `payload["model"]` 抄进 `usage_log`
  ⇒ 冒烟日志逐次记 `model`。
- `DESIGN.md` §3.5（`model` 行）、§4.4（可复现性行）、§6.4（字段表）、§11 A-11（新增局限）。

**验证读数**：冒烟日志 `smoke_usage.json` 逐条记 `model`；`smoke_log.json` 的 `models_seen`；
每份 `meta.json` 的 `models_used`（冒烟产物里可查）。

---

## 附：本轮的 API 调用账（**不隐瞒**）

| 用途 | 调用数 | 证据 |
|---|---|---|
| 冒烟（DS-01 预注册拓扑 + DS-02 小题） | **18** | `smoke/smoke_usage.json` 逐条可查（18/18 条 URL = MiniMax） |
| 阈值标定 | **0** | `calibrate_thresholds.py` 只跑离散判据 |
| 干跑 / 一致性自检 / 红线自检 / 黑名单 | **0** | 全部用打桩 LLM 或纯本地计算 |
| **合计（受约束的补测）** | **18 ≤ 20** | — |
| ⚠️ **意外**：一个临时的一致性自检脚本误用了真实 client（不是打桩） | **≈ 2**（未记录产物） | 脚本超时被中断；这类调用**不计入**上面 18 次，但仍**发起了真实请求** ⇒ 教训：**任何自检脚本必须用打桩 LLM**（现在的 `consistency_check.py` / `dryrun_test.py` / `redline_check.py` 全部是打桩，0 次 API） |

---

## 附：其它顺手修掉的东西（不在 F1–F15 列表里，但属同一类「声明 ↔ 实现不一致」）
| # | 问题 | 修法 |
|---|---|---|
| X-1 | `spec.yaml` 的 `edges:` 行内写法被极简 YAML 解析器解析坏 ⇒ 流程图退化成一条链 | 改块状写法（见 F8） |
| X-2 | `spec.yaml` 的行尾注释被极简解析器当成值的一部分（如 `collapse_mult` 读成字符串） | 全部改整行注释 |
| X-3 | `route_a.py` 的 `meta` 里曾有 `parsefail_rate` 的表达式错误（`if False else` 的残留） | 改为统一分母 `n_verdicts` |
| X-4 | 旧版 `answer_truncated_count = n_sup - len(lines)` 在兜底路径下分子分母不同源 | 见 F14 ③ |
| X-5 | `A_minus_novel` 关掉新颖轴时，装配期冗余否决仍会生效 ⇒ 消融臂被污染 | 否决权受 `novel_axis` 控制（见 F4） |
| X-6 | `stage_counts` 的键名与节点号不一致（`n6_dedup_*` 实为 N7） | 全部对齐（F8） |
| X-7 | `spec.yaml` 的 `arms[].config` 与 `falsification` 仍用行内 `{…}` ⇒ 同样被极简解析器解析坏 | 全改块状写法（⇒ 两种解析器读出同样结构） |
| X-8 | 负责人的「接线自检不适用」结论过强（复核 §4 第 ③ 条） | **新增 `consistency_check.py`**：把「声明 ↔ 实现」的落差变成机器可查的 9 组 98 项（0 次 API） |

---

## 复现命令（自检产物可一键重跑）

```bash
cd /workspace/lab/routes/A
python3 dryrun_test.py            # 离线回归（F1/F2/F3/F4/F9/F14）⇒ exit 0
python3 calibrate_thresholds.py   # 阈值标定（0 次 API）⇒ 写 calibration_log.{txt,json}
OPENROUTER_BASE_URL=https://api.minimaxi.com/v1 python3 redline_check.py   # ⇒ exit 0，all_pass=true
python3 blacklist_check.py        # 无参 ⇒ **exit 2**（空目标守卫）
python3 blacklist_check.py $(find /workspace/lab/routes/A -type f ! -path '*__pycache__*')  # ⇒ strict_hits=0
python3 consistency_check.py       # 声明 ⇄ 实现的一致性自检（0 次 API）⇒ exit 0（98 项）
python3 /workspace/lab/build_spec_flowchart.py spec.yaml <out> "路线A" "t"   # ⇒ 9 节点 / 10 边
# 冒烟日志的重建（**0 次 API**；脚本修好之后从同一次运行的落盘记录重建）
cd smoke && OPENROUTER_BASE_URL=https://api.minimaxi.com/v1 python3 smoke_a.py --summarize-only
```
