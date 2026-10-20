# 路线 A 独立复核报告（人定固定拓扑，零训练）

> **复核者**：独立复核代理（未参与路线 A 生产；未采信 `_OWNER_CHECKS.md` 的任何结论，全部重做）
> **复核日期**：2026-10-21
> **复核对象**：`/workspace/lab/routes/A/` 的 `DESIGN.md`（640 行 / 60 065 B）、`spec.yaml`、`route_a.py`、`facets.py`、`blacklist_check.py`、`redline_check.py`、`dryrun_test.py`、`smoke/*`
> **对照物（只读）**：`/workspace/research/adhd-creativity/track-d-transfer/deliverable.md` §4/§5、`track-a-mechanism/deliverable.md` §2.3、`/workspace/lab/routes/PROTOCOL.md`
> **约束**：本报告只做复核，**未修改路线 A 的任何文件**；未调用 OpenRouter；探针脚本写在 `/tmp/vrA/`（已清理）。

---

## 0. 结论摘要

**VERDICT: FAIL**

路线 A 的**红线实体**（U1–U4 零泄漏、提示词无评价口径/答案暗示/自述/题目实体、零 OpenRouter、冒烟 12 次调用可逐字节重放）**全部成立**，这是本路线做得最扎实的部分。
但**「可执行、可被否证的规格」这一核心主张不成立**：执行器有 3 个会直接影响结论的硬缺陷（token 预算按进程累计；`A_minus_D3` 不可实现 ⇒ FA-7 恒触发；拓扑实为数据依赖），另有 20/32 个声明的 `meta.json` 字段无代码产出、预注册阈值的校准证据悬空、交付的自检产物自身记录 `all_pass=false` 而文档标 ✅。

**问题密度评级**：设计论证（§1–§2、§4、§11）质量高；**声明 ↔ 实现落差**（§3.5/§6.4/§9.4 vs `route_a.py`）与**自检完整性**是短板 —— 与路线 C 被判 FAIL 的同类问题（不是同一批实例）。

---

## 1. 逐条检查

### Check 1: track-d §5 的 8 条 ⛔ 危险区是否被重新写进设计，且命中的上下文是「禁止」而非「采用」
**Method:** 逐条对 `DESIGN.md` 全文做危险模式扫描（`sleep`/走神/闲聊/`temperature`/语义距离/自我打分/自评/多智能体/辩论/ADHD/发散思维/AUT/DAT），对每处命中判读上下文；再逐条比对 track-d §5.1–§5.8 原文。
**Evidence:**
- 5.2 ⛔模拟走神 —— `DESIGN.md:86,124,284` 三处均为**禁止**语境：「❌ `sleep(N)`；「随便想点别的」；注入与任务无关的闲聊上下文」。代码侧 `facets.py:98-100` 注明「这里没有 sleep、没有「随便想点别的」、没有与任务无关的闲聊上下文」；`route_a.py:76-79` 的 `RANDOM_REST_TEXT` 只在 `resample_mode=="random"` 出现（我实测该臂的 prompt 与 `A_fixed` 逐字节不同，见 Check 7 探针 P7）。
- 5.3 ⛔只追语义距离 —— `DESIGN.md:85,118` **拒绝 D1**（「D1 打的是协议不测的靶」），改用离散结构判据（`DESIGN.md:100-104`）。
- 5.4 ⛔LLM 自我打分选最优 —— `DESIGN.md:49,70,98,362,386,558` 明确禁止自评择优，并诚实标注「内部核验器与生成器同厂商」（`DESIGN.md:98`）。
- 5.5 ⛔只注入多样性不区分新颖/有用 —— `DESIGN.md:120` 明确把「新颖轴/效用轴两个门」作为该坑的解法。
- 5.7 ⛔ADHD 人格 —— 全库 `grep -rn "ADHD|多动|跳脱" /workspace/lab/routes/A/` 仅命中 `DESIGN.md:559`（红线规则本身）与 `redline_check.py` 的词表；提示词零命中。
- 5.1 ⛔无条件提高随机性 —— 温度预注册 0.7 且三臂一致（`DESIGN.md:302`），代码 `route_a.py:66` `temp=0.7` 单一取值，无任何「提高随机性」的路径。
- 5.6 ⛔多智能体辩论 / 5.8 ⛔发散思维↑ —— DESIGN 全文 `grep 多智能体|辩论|发散思维|AUT|DAT` = **0 命中**：路线既不用多智能体，也不用发散思维测验，**没有可违反的落点**。
**Result: PASS**（5.6 / 5.8 未在文中显式登记为「已考虑并拒绝」，属可选的文档完备性缺口，不构成违规）

---

### Check 2: Mednick 双条件是否真的合取（两侧是否各自真实起作用）
**Method:** 定位「远」侧与「有用」侧的**同一条合取路径**：`route_a.py:374`（去冗余，作用于**未经效用过滤**的池）→ `:416`（`order = strict + (loose-strict)`）→ `:420`（只装 `verdict=="支持"`）。再用打桩 LLM 做 4 组对照（全开 / 关 novel / 关 utility / 两侧全关）+ 1 组顺序敏感性探针。
**Evidence:**

对照探针（受控断言池：`C1`=独立、`C2`=C1 的改写型重复、`C3`=独立、`JUNK`=无依据）：
```
[全开 novel+utility] strict=3 loose=4 支持=3  → 答案 3 行（含 C1 与 C2 两句改写重复）
[关 novel（远侧关）] strict=4 loose=4 支持=3 → 答案 3 行（顺序变了：C1,C2,C3）
[关 utility（有用侧关）] 支持=0 → 走 fallback，JUNK 也进了答案（4 行）
[两侧全关]  支持=0 → 4 行
```
⇒ **两侧都真实起作用**：关 utility ⇒ `JUNK`（无依据）进入答案；关 novel ⇒ 条目顺序/入选集合改变。**不存在「只做远不做有用」的坑**。

但**合取不是干净的合取**（对抗性探针）：`pool = [JUNK(未提及), GOOD(支持)]`，两条为近似重复：
```
junk 在前 good 在后 → strict=1 loose=1 | 支持=1 | answer_fallback=True
    ## 依据未覆盖、仅供参考的事项
    - 该服务每月收费 20 元。          ← 交付的是未被依据支持的条目
good 在前 junk 在后 → strict=1 loose=1 | 支持=1 | answer_fallback=False
    ## 经核验成立的依据
    - [EV-1] 该服务每月收费 20 元整。   ← 同一对数据，结论相反
```
⇒ 「远」轴在「有用」轴**之前**、且作用于**未经效用过滤**的池子 ⇒ **一个未被支持的近似重复项可以把被支持的条目挤出答案**，且结果**依赖池内顺序**。同时 `meta.support_rate_generated` 仍报 `1.0`，而交付答案里装的是未核验条目 ⇒ 诊断量与交付物不一致。

另：全开情形下 `C1` 与 `C2`（改写型重复）**同时进入答案** ⇒ `DESIGN.md:62,603` 的「只保证『不是同义反复』」不成立。
**Result: FAIL** —— 基础形态（两腿都在）通过；**合取的实现顺序错误**，且「保证不冗余」是超出代码的断言（详见 §2 F4）

---

### Check 3: 红线 —— 答案暗示 / 评价标准 / 题目实体 / 模型自述 / U1–U4 泄漏 / OpenRouter
**Method:**
(a) 用**正确路径** `/workspace/lab/creativity_lab/data/user4_q*.json` 亲自重跑黑名单比对，并把**被扫对象扩大到路线 A 全部 15 个文件**（生产者的 `redline_check.py` 只扫 8 个）；
(b) 对**真正会发给模型的 19 条字符串**（`facet_text`/`facet_name`/6 个模板/`RANDOM_REST_TEXT`）用比生产者更宽的词表独立扫；
(c) 逐行核对冒烟日志的端点与调用次数。
**Evidence:**

(a) 黑名单独立重跑（源：4+4=8 个 user4 文件；`blacklist_strict=5644` 条、`hint=104` 条）：
```
$ python3 blacklist_check.py <路线 A 全部 15 个文件>
source_files=8 strict=5644 hint=104   strict_hits=0   hint_hits=1
   DESIGN.md:432  cls=hint len=4  sha1=c15d632e
```
命中的是 `DESIGN.md:432` 的 **「的最后一」** —— 来自 U3 题面「…小长假的**的最后**一天…」的 4 字 n-gram，属通用汉语词组，非实质泄漏。**strict 命中 = 0 ⇒ U1–U4 题面/依据包全文/原子事实/≥8 字片段在路线 A 全库零出现。**（生产者的 8 文件扫描同样 0，结论成立；我的扩展扫描未推翻它。）

(b) 注入串卫生（19 条，词表含 新颖/承重/洞见/深度/独特/有用/质量/评价/评分/维度/冗余/多样性 + 答案/正确/应当/最优/标准 + 我考虑/我的思路/我认为 + 阶梯/水费/快递/运费/保价/湖北/高考/620）：
```
[RUBRIC] 命中 0   [HINT] 命中 0   [SELF] 命中 0   [ENTITY] 命中 0
```

(c) OpenRouter：冒烟 12 次调用的 URL **逐条**为 `https://api.minimaxi.com/v1/chat/completions`（12/12），`smoke_log.json` 的 `endpoint=https://api.minimaxi.com/v1`、模型 `MiniMax-M3.1-Flash-Preview`。
**Result: PASS**（红线实体成立；`redline_check.py` 自身的 `all_pass=false` 问题另见 Check 8 / §2 F7）

---

### Check 4: 代理错位 —— 「有效维度」是否退化成条数/宽度/字数；DESIGN「不自带抽取器、不自带卡片定义」是否属实
**Method:** `grep -n "卡片|card|维度|承重|vd_" route_a.py facets.py`（全量命中逐条判读）；`grep -n "^def " route_a.py facets.py`（函数清单）；检查装配侧是否用条数/长度代替承重。
**Evidence:**
- `route_a.py` 的全部函数：`_char_bigrams/_jaccard/redundancy/_lines/_roundrobin/run_route` + `MeteredLLM`；**无卡片抽取器、无卡片 schema、无「维度」概念**。`facets.py` 里「承重/维度」只出现在**推导注释**里（`facets.py:17,18,42,72`），不在注入文本里（注入走 `facet_text()`=`FACETS[fid][1]`）。
- 装配侧（`route_a.py:416-427`）：顺序 = `strict` 优先 + `loose` 填尾（内容无关）+ 400 字上限；**入选的唯一判据是依据核验结果**（`verdict=="支持"`），不是条数/长度/角色数。
- `DESIGN.md:419-424` 明确「本路线不产出指标」「诊断量不得充当卡片组」；`spec.yaml:94-96` 明确不产出 `cards.json` / `summary.json`。**「不自带抽取器/卡片定义」的声明属实。**
- 训练侧无任何替代代理：本路线零训练，`spec.yaml:13-14` `trained: false` / `learned_components: []`，全库无 policy/权重/特征文件。
**Result: PASS**（但见 §2 F4：新颖轴用**离散词面判据**近似「远」，与协议 §1.4 的「交互增益 + 删除反事实」不是同一个量 —— DESIGN §2.2 已诚实标注这是改造，但两轴的交互缺陷未登记）

---

### Check 5: 否证条件是否可失败；对照臂是否够（必须含等预算对照）
**Method:** 逐条找「可触发例子」；核对 `FA-1…FA-11` 各自依赖的臂在执行器里是否可构造；核对协议 §8(c) 的 4 条共用对照臂。
**Evidence:**
- F1–F8 原样照抄（`DESIGN.md:455`），不触发逻辑与协议 §3.3 一致（含三段判读表）—— 通过。
- 不可失败/恒触发的问题：
  - **FA-7 恒触发**：`FA-7` 需要 `A_minus_D3`（第二轮**不带**已覆盖清单）。`spec.yaml:262` 给的 config 是 `resample_mode: structured_no_cover`，而 `route_a.py` 只认 `"structured" | "random" | "none"`（`route_a.py:51,316,323-324`）：任何非 `"random"`/`"none"` 的值都走**带清单**分支 ⇒ **`structured_no_cover` 与 `A_fixed` 逐字节同规格**（实测：`structured` 与 `structured_no_cover` 的第二轮 prompt 逐字节相同）。于是 FA-7 变成「`A_fixed` vs `A_fixed` ⇒ `VD_net` 中位数 = 0 ≤ 0」⇒ **对任何数据都触发**。
  - **FA-8 在 `A_minus_utility` 上恒成立**：`utility_axis=False` ⇒ 全部裁决为「未核验」⇒ `n_contradicted=0` ⇒ `conflict_rate_generated ≡ 0`（构造上不可能大于 `A_fixed`）。而 FA-8 的措辞是「`A_minus_novel` **或** `A_minus_utility` 的 VD/矛盾率**不劣于** `A_fixed`」⇒ 该臂在冲突率上**必然**「不劣」⇒ FA-8 在这条读法下**恒触发**。`DESIGN.md:402` 声称负对照「**预期**更差（F2/G2/**R1** 触发）」—— 探针实测负对照的冲突率为构造性 0，**R1 不可能为它触发**，该预期与代码矛盾。
  - 其余 FA-1/2/3/4/5/6/9/10/11 的触发条件写法与协议三段判读表一致，可触发 —— 通过。
- 等预算对照：协议 §8(c) 要求「每条路线至少 4 条、全部共用」，且「B1/B2 的 K 与 T_W **按该路线实际值填**」。`DESIGN.md:381-386` 列了 B0/B1/B2/B3，但**执行器没有实现任何一条**：`route_a.py` 无 K 次采样循环、无「固定取最后一份」的选择规则、无 token 预算采样循环、无外部核验器择优（B3）。B0 尚可由配置逼近（`facet_enabled=False` + 单槽位），**B1/B2/B3 无实现** ⇒ 协议 F6、FA-2、FA-3 在交付代码上**无法被检验**。
**Result: FAIL** —— FA-7 / FA-8 两条特有关否证条件在交付实现下**不可失败或恒触发**；等预算对照臂无实现

---

### Check 6: 可执行性 —— ①`spec.yaml` 能否被规范渲染器渲染出非空图 ②DESIGN 声明 vs 代码实现 ③spec 与 DESIGN 是否逐节点一致
**Method:**
① 自己跑 `/workspace/lab/build_spec_flowchart.py` 并数 rect/path/text；
② 把 `DESIGN.md §3.5` 常量表、`§6.4` 的 meta 字段表、`§3.1/§3.2` 的节点与伪代码逐项映射到 `route_a.py`；
③ 把 `spec.yaml` 的 `nodes:` 与 `DESIGN.md §3.1` 的图、`route_a.py` 的 docstring 三方对齐。
**Evidence:**

① 渲染（自己跑，**数字如下**）：
```
$ python3 /workspace/lab/build_spec_flowchart.py /workspace/lab/routes/A/spec.yaml $T "路线A" "t"
✓ $T/index.html 已生成（4443 字节）        # 4443 = 字符数；UTF-8 字节数 = 4701
rect = 9    path = 16    text = 9
节点名：读题/装配输入、槽位生成（第一轮）、断言抽取（逐槽位）、离散去冗余+塌缩诊断、
       条件重采样（第二轮）、断言抽取（第二轮）+原子化拆分、机械装配（不由模型重写）、自检与记账
```
⇒ **非空图，读数 9 / 16 / 9**，与负责人口头一致。

② 声明 vs 代码（**逐项**）：
| DESIGN 声明 | 代码现实 | 判定 |
|---|---|---|
| `max_tokens` 40 000「**每臂每任务每 rep**」（`:294`；`spec.yaml:48 max_tokens_per_rep`） | `route_a.py:240-241` `_tokens()` 返回 `llm.n_tokens`（**跨任务累计**），`:261-262` 拿它与上限比 | ❌ 作用域错（见 F1） |
| `collapse_mult`「1.0（**诊断量，不作开关**）」（`:301`） | `route_a.py:315-318` `thr_keep = collapse_mult*len(round1_facets)`；`fire = … kept_r1 < thr_keep …` ⇒ **它就是开关** | ❌ 语义反了（见 F3） |
| `seed` = S1/S2/S3（`:303`）、`§4.4` 的「固定种子 + `seed` 字段」、`§6.4` meta 含 `seed` | 全库无 `seed`；共享 client `client.py:64-66 chat()` **根本没有 seed 参数**（payload 只有 model/messages/temperature/max_tokens） | ❌ 整条链不存在 |
| `§6.4` meta 必含 32 字段 | 执行器实际产出 20 个；**声明了但代码不产出 20 个**：`run_id, arm_id, task_id, rep, seed, model, temperature, prompt_version, arm_config_hash, cost_usd, valid/total, parsefail_rate, silent_empty_count, over_budget_count, n_shipped, collapse_flag, devset_id, devset_hash, evidence_pack_version, evidence_hash` | ❌ 20/32 缺 |
| `§6.4` 输出 `RUNS/<arm>/<task>/rep<k>.answer.md` + `.meta.json` | 路线 A **无任何写文件代码**（`grep -rn "RUNS\|answer.md" A/*.py` = 0 命中）；`/workspace/lab/routes/RUNS/` 不存在 | ❌ 输出契约未实现 |
| `§3.2` 伪代码：N4 无条件执行 | `route_a.py:316-318` 数据依赖 | ❌（见 F3） |
| `§3.5` `answer_char_cap` = 400 字 | 只作用于条目正文；冒烟 DS-02 交付答案 **401 字**（含回显题面） | ⚠️ 口径偏差 |
| `§3.5` `struct_thr` 校准「27 条断言 → 保留 25 条」「`lex_thr` 27 条保留 27 条」且「标定过程与结果记于 `smoke/smoke_log.txt`」 | 交付的 `smoke_log.{txt,json}` 里 `grep "27 条\|lex_thr\|struct_thr\|0.75\|0.70"` = **0 命中**；交付日志的实际读数是 DS-01 `impl1=12/12, impl2=11/12`、DS-02 `10/10` | ❌ 校准证据悬空（见 F6） |
| `§3.3` 目录纪律 1：「`RUBRIC_TERMS` **零命中**」 | `facets.py:42,72` 命中「承重」；`redline_check.json` 记 `hard_fail_total=2` | ❌（见 F7） |
| `§6.2` 诊断量含 `collapse_flag` | 代码只出 `trigger_fired` / `trigger_kept` | ❌ 命名/键不符 |
| `§9.4` R-12：「meta 里 `conflict_n/conflict_den`」 | 代码无这两个键（只有 `n_supported`/`n_contradicted`/`conflict_rate_generated`） | ⚠️ 字段名不存在（实质分母在） |
| `extract_cap`「每槽位最多抽 8 条」 | 第一轮 8 条 ✅；第二轮用 `extract_cap*len(r2_answers)`=16 条（未登记） | ⚠️ |

③ 节点编号 —— **三套并存**：
```
DESIGN.md §3.1 图 : N1..N8（8 个；N5=第二轮抽取, N6=拆分, N7=D2门, N8=装配；无 N0）
spec.yaml nodes  : N0..N8（9 个；N5=第二轮抽取+拆分, N6=D2门, N7=装配, N8=自检与记账）
route_a.py 文档串: N1..N7（7 个；N5=拆分, N6=D2门, N7=装配）
deliverable.md  : 「8 节点」却列出 9 个，且 N5=抽取/N6=拆分/N7=D2门/N8=装配
```
⇒ `DESIGN.md:199`「节点编号与 `spec.yaml` **一一对应**（`spec.yaml` 用 `N1…N8`）」**不成立**（spec 用 N0–N8，且 N5–N8 语义不同）。负责人《必修 1》要求的「与 DESIGN §3.1 的 8 个节点逐一对上」**未满足**。
**Result: FAIL** —— ①渲染通过（9/16/9）；②12 项声明 ↔ 代码落差（其中 6 项为硬缺口）；③节点编号三套并存

---

### Check 7: 冒烟 —— 独立读日志、数调用次数、核对端点与模型、确认 ≤20、确认无 OpenRouter、逐字节重建
**Method:** 独立解析 `smoke_log.json` / `smoke_usage.json` / `smoke_calls.jsonl`；再用日志里记录的**逐次 prompt + output** 做打桩重放，走真实执行器重建装配结果，与日志答案做**逐字节比对**。
**Evidence:**
- 调用次数：`**total_api_calls = 12**` ≤ 上限 20；`smoke_calls.jsonl` 12 行，purpose 序列 = `A_slot_FA2, A_slot_FA3, A_extract_FA2, A_extract_FA3, A_resample_FA4, A_extract_r2, A_verify`（DS-01，7 次）+ `A_slot_FA1, A_slot_FA2, A_extract_FA1, A_extract_FA2, A_verify`（DS-02，5 次）= 12。
- 端点/模型：12/12 条 URL = `https://api.minimaxi.com/v1/chat/completions`；`primary_model = MiniMax-M3.1-Flash-Preview`；`total_tokens = 23 727`（与 `DESIGN.md:492` 的「12 次调用 / 23.7k token」一致）。
- **逐字节重放（我做的）**：
```
DS-01: 答案逐字节相同 = True（133 / 133 字符）  meta + stage_counts 全等
DS-02: 答案逐字节相同 = True（401 / 401 字符）  meta + stage_counts 全等
重放时喂给模型的 prompt 与日志记录的 prompt 逐字节相同（无告警）
总体逐字节重放: PASS
```
⇒ 装配与抽取/去冗余/裁决解析环节**确定性可复现**，这一点比路线 B 的复核还强。
- 但覆盖有缺口：诊断题用 `round1_facets=[FA2,FA3]+[FA1,FA2]`、`round2_facets=[FA4]`/`[]`（**预注册是 4+2**）⇒ **FA5/FA6 从未对活模型跑过**；DS-01 用 `collapse_mult=99.0` **强制**触发第二轮，DS-02 用预注册的 `1.0` 却 `trigger_fired=false` ⇒ **预注册的触发条件在活体上从未被执行过**。
- `smoke_log.json` 的 `openrouter_used=false` 是**硬编码字面量**（`smoke_a.py:122`），不是计算值；真正的证据是 `smoke_usage.json` 的 12 条 URL（我已核）。`DESIGN.md:23,562` 把它当证据引用。
**Result: FAIL** —— 调用次数/端点/模型/无 OpenRouter/逐字节重放全部通过；**但活体冒烟未覆盖预注册拓扑与预注册触发路径**

---

### Check 8: 自检是不是「橡皮图章」；交付物里关于环境的陈述是否与真实文件系统一致
**Method:** 逐个自检脚本审 + **按负责人自己的跑法复现** + 对交付物里的环境陈述逐条核文件系统。
**Evidence:**

(a) **`blacklist_check.py` 无参运行 = 扫 0 个文件、报 0 命中、exit 0**（负责人自己的跑法）：
```
$ python3 blacklist_check.py
{"source_files": 8, "blacklist_strict": 5644, "blacklist_hint": 104,
 "files": [], "strict_hits": 0, "hint_hits": 0}      exit=0
```
`"files": []` 就是「一个文件都没扫」。脚本对**空目标列表没有任何守卫**（`blacklist_check.py:125-129`：`args=sys.argv[1:]` → `scan(args)` → `exit(1 if strict_hits else 0)`）⇒ **这正是《必修 3》明令禁止的「跳过检查却仍 exit 0」**。

(b) **`redline_check.py` 自身在交付状态下 FAIL**：
```
$ OPENROUTER_BASE_URL=https://api.minimaxi.com/v1 python3 redline_check.py
"R2_rubric_term_hits": [FACET:FA1:why 承重, FACET:FA6:why 承重]
"hard_fail_total": 2, "all_pass": false        exit=1
```
交付目录里的 `redline_check.json` 同样写着 `"all_pass": false, "hard_fail_total": 2` —— 而 `DESIGN.md:556`（R-2 行）标 **✅**、`DESIGN.md:261` 声称「`RUBRIC_TERMS` **零命中**（该模块 `self_test()` 通过）」。**实体上这两处「承重」在推导注释里、不进任何提示词**（我独立扫 19 条注入串：rubric/hint/self/entity 全 0 命中）⇒ **红线实体成立，但交付的自检产物与文档声明互相打架**。

(c) `dryrun_test.py` 的消融断言过弱：五条消融臂只断言 `rr["meta"]["n_calls"] > 0`（`dryrun_test.py:101`），**从不断言各臂与 `A_fixed` 有区别** ⇒ 「`structured_no_cover` 静默等于 `A_fixed`」这类 bug 在干跑里不可见。`smoke_a.py` 的退出码只依赖 `within_global_call_cap`（`smoke_a.py:188`），证据泄漏/解析失败不影响退出码。

(d) **交付物里的环境陈述逐条核对**：
| 陈述 | 位置 | 真实文件系统 | 判定 |
|---|---|---|---|
| 「U1–U4 依据包在 `creativity_lab/data/user4_q*.json`」 | `blacklist_check.py:31` | 存在（4 个文件） | ✅ 真 |
| 「`cmp8repo/cmp8/creativity_lab/data/user4_q*.json`」 | `blacklist_check.py:32` | 存在（4 个文件，内容较旧但合法） | ✅ 真 |
| 「`spec.yaml` 顶层 `nodes:` / `edges:`」 | `spec.yaml:99,224` | 存在 | ✅ 真 |
| 「承载面目录（6 个认知位置：…**主体间权利义务关系**…）」 | `deliverable.md` 交付物表 | `facets.py` 的真实目录是「适用范围与情形范围/依据与约束/数量与门槛/情形分支与差异/例外与失效条件/缺口与不确定」；**「主体间权利义务关系」「程序步骤与时限」在代码里根本不存在** | ❌ **假** |
| 「顶层 `nodes:` 20 个」 | `deliverable.md` | `nodes:` 有 **9** 个、`arms:` 有 **11** 个，20 是两块相加 | ❌ 误述 |
| 「8 节点固定拓扑」 | `deliverable.md` | 随后列出 9 个节点 | ❌ 误述 |
| 「两次冒烟暴露并修掉两个真实缺陷」 | `deliverable.md` | `DESIGN.md §10.3` 列的是**四个** | ❌ 误述 |
| 「标定过程与结果记于 `smoke/smoke_log.txt`」 | `DESIGN.md:306` | 该日志内 `27 条/lex_thr/struct_thr` **0 命中** | ❌ 悬空引用 |
**Result: FAIL** —— `blacklist_check.py` 空目标仍 exit 0（负责人自己就是这么跑并据此下结论的）；交付的自检产物 `all_pass=false` 与文档 ✅ 冲突；deliverable 对 `facets.py` 目录的描述与代码不符

---

### Check 9: 有没有把「设计」说成「结论」
**Method:** 扫描 `DESIGN.md` + `deliverable.md` 的比较性/结论性表述。
**Evidence:**
- `DESIGN.md` 全文 `grep "更优|优于|更好|更强|最强|证明|成功了|显著|最佳"` 的命中只有 3 处，**全部是否定式**（`:3`、`:25` 的自我声明，以及 `:402` 的「证明 D2 的两半各自有作用」—— 指的是**否证条件**的用途，不是结论）。
- 无任何实测维度数/矛盾率/路线比较；`:640` 明写「本文是**设计规格**，不是实验报告」。
- `deliverable.md` 的「未跑训练、未产出任何实验结论、未声称任何路线更优」与盘上文件一致。
**Result: PASS**（唯一可议：`DESIGN.md:402` 的「**预期**更差」是一个关于未来数据的预测，且与代码矛盾 —— 归入 Check 5，不重复计）

---

## 2. 会死在哪里（FAIL 清单，file:line + 为什么）

| # | 严重度 | 位置 | 问题 | 为什么是死因 |
|:-:|:-:|---|---|---|
| **F1** | 🔴 阻断 | `route_a.py:240-241,261-262`（对照 `DESIGN.md:294`、`spec.yaml:48`） | `max_tokens` 预注册为「每臂每任务每 rep = 40 000」，实现却是**进程累计** | 实测：共享 LLM 连跑 3 题，第 3 题在「自己只用了 ~3k token」时被 `BudgetExceeded: 已用 36000 / 上限 40000` 中止 ⇒ **真实批次（12 题×3 rep）从第 2–3 题起全部作废**；`meta.n_tokens` 也被前序任务污染 ⇒ 成本记账错（`DESIGN.md §8.1` 的 per-rep 列、协议 (a4) 跨臂元数据）。`max_calls` 已在 `DESIGN §10.3` 第 3 条修成按任务计，**token 的同一 bug 没修** |
| **F2** | 🔴 阻断 | `spec.yaml:260-263` vs `route_a.py:51,316,323-324`；`DESIGN.md:396,467` | `A_minus_D3`（`resample_mode: structured_no_cover`）**不可实现**：执行器只认 `structured/random/none`，任何其他值都走**带清单**分支 | 实测 `structured` 与 `structured_no_cover` 的第二轮 prompt **逐字节相同** ⇒ 该臂静默退化为 `A_fixed` ⇒ **FA-7 恒触发**（`A_fixed` vs `A_fixed`，`VD_net` 中位数 0 ≤ 0）⇒ 一条**对任何数据都会触发**的否证条件 |
| **F3** | 🔴 阻断 | `route_a.py:315-318` vs `spec.yaml:156`、`DESIGN.md:301,146` | 「固定拓扑 / 完全固定」不成立：N4 整节点可被数据依赖地跳过；`collapse_mult` 被声明为「诊断量，不作开关」**实际就是开关** | `spec.yaml:156` 写「**恒定执行**（固定拓扑；不做数据依赖的开关）」；`DESIGN.md:301` 写「诊断量，**不作开关**」；`DESIGN.md:146` 更以「分支开关让拓扑数据依赖 ⇒ 与路线 A 的定义冲突」为由**弃用 D6** —— 路线 A 自己实现了同款数据依赖开关。另：`DESIGN.md §3.2` 伪代码、`§8.1` 成本表（6 次生成）都按 N4 必然执行算 ⇒ 成本与调用数记账随数据漂移 |
| **F4** | 🔴 阻断 | `route_a.py:374,416,420`（对照 `DESIGN.md:62,603`） | Mednick 合取**实现顺序错误**：「远」轴在「有用」轴之前、作用于**未经效用过滤**的池子 | 实测：未被支持的近似重复项可把**被支持**的条目挤出答案（交付的是「依据未覆盖」条目），且**随池内顺序翻转**；同时 `support_rate_generated` 仍报 1.0（诊断量与交付物不一致）。良性情形下改写型重复**同时进入答案** ⇒ `DESIGN.md:62,603` 的「只保证『不是同义反复』」是**超出代码的断言** |
| **F5** | 🔴 阻断 | `DESIGN.md:448`（32 字段）vs 执行器 | **20/32** 个声明的 `meta.json` 字段无代码产出（`run_id/arm_id/task_id/rep/seed/model/temperature/prompt_version/arm_config_hash/cost_usd/valid/total/parsefail_rate/silent_empty_count/over_budget_count/n_shipped/collapse_flag/devset_id/devset_hash/evidence_pack_version/evidence_hash`）；`seed`（S1/S2/S3）**整条链不存在**，且共享 client 的 `chat()` 根本没有 seed 参数 | 协议 (a4) 要求跨臂可比元数据含 `seed_policy`；`DESIGN.md:455` 的 F1–F8 与 §7 的 FA-1/2/3/6 全部依赖 `VD_net`/地板/维度-条数比等协议侧指标；`DESIGN.md §6.4` 声明的 `RUNS/<arm>/<task>/rep<k>.{answer.md,meta.json}` **没有任何代码写**（`/workspace/lab/routes/RUNS/` 不存在）⇒ 路线按交付代码**无法产出协议 (a2) 要求的输出** |
| **F6** | 🔴 阻断 | `DESIGN.md:299-300,306` | 预注册阈值的**校准证据悬空**：引用「27 条断言保留 27 条」「27→25」并称「标定过程与结果记于 `smoke/smoke_log.txt`」，但交付日志里 `27 条/lex_thr/struct_thr/0.75/0.70` **0 命中**；交付日志的实际读数是 12/12 与 11/12、10/10 | `lex_thr/struct_thr` 决定**哪些条目能进答案**（本路线最脆的一环，`DESIGN.md:339` 自认），是预注册的核心数字却无可查证记录 ⇒ 协议 R-9「事后不得改口径」在交付包内**无法自证**；同时交付的 `impl2` 已在 DS-01 上删掉 1/12 条，删除理由无人工确认记录 |
| **F7** | 🔴 阻断（自检完整性） | `redline_check.json`（`all_pass:false, hard_fail_total:2`）vs `DESIGN.md:261,556`；`blacklist_check.py:125-129` | 交付的**自检产物自身记录 FAIL**，文档却标 ✅；黑名单脚本**空目标仍 exit 0** | 负责人《必修 3》明令「跳过任何检查时绝不能输出 PASS / 不能 exit 0」—— 脚本没有空目标守卫，而负责人的核对**正是用无参跑法**（输出 `"files": []`）并把 `source_files=8` 误读成「没跳过」⇒ **该核对项的证据不成立**（结论本身被我用全量扫描独立证成 0 命中） |
| **F8** | 🟠 重 | `DESIGN.md:199` / `spec.yaml:99-221` / `route_a.py:9-17` / `deliverable.md` | 节点编号**三套并存**（DESIGN N1–N8 / spec N0–N8 / 代码 N1–N7），`DESIGN.md:199` 的「一一对应」不成立 | 负责人《必修 1》明文要求「节点 id 用 N1…N8，**必须与 DESIGN §3.1 的 8 个节点逐一对上**」—— 未满足；图（由 spec 渲染）与代码/文档各说各话，读者无法把图对到实现 |
| **F9** | 🟠 重 | `DESIGN.md:381-386`（B0–B3） | 等预算对照臂**无任何实现**（无 K 采样循环、无「固定取最后一份」、无 token 预算采样、无外部核验器择优） | 协议 §8(c) 要求每条路线≥4 条共用臂且「K/T_W 按本路线实际值填」；协议 F6、FA-2、FA-3 都建立在 B1/B2 之上 ⇒ 交付代码**无法满足 F6**（B0 尚可由配置逼近） |
| **F10** | 🟠 重 | `DESIGN.md:457-471`（FA-8）、`:402` | FA-8 措辞使 `A_minus_utility` 臂**恒触发**（该臂 `conflict_rate_generated` 构造上 ≡ 0 ⇒ 必然「不劣于」）；`DESIGN.md:402` 的「负对照**预期**更差（…R1 触发）」与代码矛盾（R1 对该臂不可能触发） | 一条必然触发的否证条件 = 橡皮图章的另一形态；且把「预期更差」写进设计会误导后续跑批的读数 |
| **F11** | 🟠 重 | `deliverable.md` 交付物表 | 对 `facets.py` 的描述**与代码不符**（「主体间权利义务关系」「程序步骤与时限」在代码里不存在；真实目录是 适用范围与情形范围/依据与约束/数量与门槛/情形分支与差异/例外与失效条件/缺口与不确定）；另「顶层 `nodes:` 20 个」「8 节点」「两个真实缺陷」三处误述 | 交付物自述是复核者的第一手索引；描述失真会让复核者照着不存在的目录去核（A-5 建议、FA-10 触发条件都挂在目录条目上） |
| **F12** | 🟡 中 | `smoke/smoke_a.py:48,63`（对照 `DESIGN.md:291-292`） | 活体冒烟只跑了 2+1 / 2+0 个承载面（预注册 4+2）⇒ **FA5/FA6 从未对活模型跑过**；预注册的 `collapse_mult=1.0` 路径从未触发（DS-01 用 99.0 强制，DS-02 `trigger_fired=false`） | 交付的唯一活体证据来自**非预注册配置**；「可执行性已通过」这句话目前只在缩小版拓扑上成立 |
| **F13** | 🟡 中 | `smoke/smoke_a.py:122`；`DESIGN.md:23,562` | `smoke_log.json` 的 `openrouter_used=false` 是**硬编码字面量**，却被 DESIGN 当作证据引用 | 真实证据是 `smoke_usage.json` 的 12 条 URL（我已核，12/12 为 MiniMax）—— 结论为真，**引用的证据是假的**（同类模式：字段值 ≠ 实测） |
| **F14** | 🟡 中 | `route_a.py:424-425,474` | ① 400 字上限只管条目正文，交付答案含回显题面达 401 字；② 超限时 `break` 而非 `continue` ⇒ 后面的短条目被一并丢弃（顺序偏置）；③ `answer_truncated_count = n_sup − len(lines)` 在 fallback 情形下分子分母不同源 | 口径与 `DESIGN.md:372`「字数上限把宽度卡死」的表述有偏差；虽三臂对称，但会让「上限 binding」的判读偏乐观 |
| **F15** | 🟡 中 | `route_a.py:264,306,338` | 预注册 `temperature=0.7` 三臂一致，但共享 client 的 `chat()` 会按 `FALLBACKS` **静默换模型**（`client.py:73` `cands=[model]+FALLBACKS`），而路线 A 的 meta 不记录**实际使用的模型** | 协议 §4.3「若供应商 API 忽略该参数 ⇒ 记录实际值并写进报告」；`DESIGN.md:304` 声明 `model` 为冻结档位集，但**无法从交付物核验每条样本实际用了哪个模型** |

---

## 3. 通过的部分（不要一棍子打死）

1. **U1–U4 零泄漏（硬红线实体成立）**：我用正确路径 `/workspace/lab/creativity_lab/data/` + `cmp8repo/cmp8/creativity_lab/data/` 重建黑名单（5644 条 strict + 104 条 hint），扫**路线 A 全部 15 个文件** ⇒ `strict_hits = 0`。唯一 hint 命中 `DESIGN.md:432` 的「的最后一」是通用汉语词组。
2. **提示词卫生干净**：19 条真正注入的字符串，用比生产者更宽的词表（评价口径 17 词 / 答案暗示 13 词 / 自述 7 词 / 题目实体 11 词）独立扫描 ⇒ **全 0 命中**。R-2/R-3/R-6/R-7 的**实体**成立。
3. **零 OpenRouter**：冒烟 12/12 条 URL = `api.minimaxi.com/v1/chat/completions`；`smoke_a.py:30-32` 启动即断言端点；`route_a.py` 只用 MiniMax 订阅侧。
4. **`spec.yaml` 可被规范渲染器吃**：我实跑 `build_spec_flowchart.py` ⇒ **rects=9 / paths=16 / texts=9**（4443 字符 / 4701 字节），非空图，节点名正确。这是《必修 1》的硬契约，**通过**。
5. **冒烟逐字节可重放**：我用日志里的逐次 prompt+output 打桩重放，**两题的答案（133 / 401 字符）与全部 meta、stage_counts 逐字节相同**，且重放时喂给模型的 prompt 与日志逐字节一致 ⇒ 装配/抽取/去冗余/裁决解析环节确定性成立（强于路线 B 的复核）。
6. **Mednick 两腿都在**：探针证明「远」侧与「有用」侧**各自独立改变交付答案** ⇒ **没有踩「只做远不做有用」这个本项目最容易踩的坑**（F4 是两腿的**交互顺序**问题，不是缺腿）。
7. **不自带抽取器 / 不自带卡片定义**：代码里确无卡片 schema、无维度抽取器、无「维度」概念；装配侧唯一入选判据是依据核验结果，**没有用条数/字数/角色数代替承重** ⇒ R-2 的**代理错位**在路线 A 侧成立。
8. **D3 的 ✅ 形式与 ❌ 对照臂都真的实现了**：`A_random_rest` 的第二轮 prompt 与 `A_fixed` **逐字节不同**（占位文本替换已覆盖清单），`resample_mode="none"` 确实不触发第二轮 ⇒ track-d §4.3 要求的四臂对照里，**能实现的三臂都在**。
9. **不把设计说成结论**：全文无比较性断言、无实测维度数/矛盾率、无「路线 A 更优」。
10. **零训练成立**：`spec.yaml:13-14` `trained:false` / `learned_components:[]`；全库无 policy/权重/特征表；`ops.Graph`/`learnarch` 明确不复用。
11. **诚实清单到位**：`DESIGN.md §11` 的 A-1（不知道 `C_t`）、A-2（同厂商核验器）、A-3（交付侧矛盾率结构性偏低）、A-4（400 字上限大概率 binding）、A-5（DS-01 只剩 1 条被支持）**全部属实**且我在数据里逐条对上了。
12. **干跑与红线脚本会真失败**：`dryrun_test.py` 复跑 exit 0（预算守卫确实抛 `BudgetExceeded`）；`redline_check.py` 确实 exit 1 ⇒ 脚本本身不是「只会 PASS」的假自检（问题在覆盖面与文档一致性，见 F7）。

---

## 4. 对 `_OWNER_CHECKS.md` 的纠错（负责人自己写的核对记录，结论不采信）

| 负责人的结论 | 复核实测 | 判定 |
|---|---|---|
| ①「`spec.yaml` 渲染 `bytes=4443 rects=9 paths=16 texts=9` ⇒ 满足」 | 我实跑得到 **rects=9 / paths=16 / texts=9**（4443 是**字符数**，字节数 4701） | ✅ 结论成立（措辞小瑕） |
| ②「`grep -c '^nodes:'` → 1（**20 个节点**：N0–N8 + **10 条**对照臂）」 | `nodes:` 实际 **9** 条；对照臂在**另一个顶层键 `arms:`** 下、共 **11** 条；20 是两块相加 | ❌ 计数/归属都错 |
| ③「接线自检**不适用** ⇒ 无『声明存在但代码不读』的死维风险」 | 路线 A 无参数表，但**存在同型的声明↔实现落差**：`collapse_mult`（声明为诊断量、实为开关）、`structured_no_cover`（spec 声明、执行器不实现）、`max_tokens`（声明 per-rep、实为进程级）、`seed`（声明、代码无且 client 不支持）、20/32 meta 字段 | ❌ 结论过强，且我已实测出 5 处同型问题 |
| ④「自检**不是橡皮图章**：`source_files=8` ⇒ **没有跳过**；strict_hits=0」 | 负责人贴的输出里有 `"files": []` ⇒ **那次运行一个文件都没扫**；`source_files=8` 数的是**黑名单来源**不是**被扫对象**。`blacklist_check.py` 对空目标列表无守卫（正是《必修 3》禁止的形态） | ❌ **证据不成立**（结论我用全量扫描独立证成 0 命中，但那次核对的**方法**无效） |
| ⑤「全文检索 `不可能\|确保\|必然\|永远` **零命中** ⇒ 没有无代码支撑的断言」 | 该 grep 确实 0 命中 ✅；但 DESIGN 里有**更强的未被 grep 覆盖**的断言：「路线**能保证**『不冗余』」「只**保证**『不是同义反复』」（`:61,:62,:603`）—— 我的探针证明改写型重复会**同时进答案**，该断言不成立 | ⚠️ 结论过强（漏检模式） |
| ⑥「五项负责人收尾要求全部满足」 | 必修 1 只满足「能渲染」不满足「节点逐一对上」；必修 2 未做（无敏感性探针、无变异注入自测）；必修 3 **未满足**（空目标 exit 0）；必修 4 部分（结论写了，**校准记录不在包里**）；必修 5 部分（泄漏类断言有代码强制，但「保证不冗余」类没有） | ❌ 不成立 |
| ⑦「唯一缺的是 `deliverable.md`」 | `deliverable.md` 存在，但其中**对 `facets.py` 目录的描述与代码不符**、「nodes: 20 个」「8 节点」「两个真实缺陷」三处误述 | ⚠️ 补齐了，但引入新的失真 |

---

## 4.5 复核副作用披露（我对路线 A 目录做过什么）

- **`/workspace` 是指向 `/run/csi/mount-root/nas/eab0d61a99b6696edb3d2aff87b585e8` 的符号链接** ⇒ 交付物里那些绝对路径（`redline_check.json` 的 `/run/csi/...`）就是本机的真实路径，**不是「生产者环境不同」的证据**。
- 我运行了生产者自己的 `redline_check.py`（复核必须复现它的失败态）⇒ 它会**重写自己的输出产物** `redline_check.json`。重写前后 **`md5` 完全相同**（`3bba00933a61faf91ac3f6a32b9ffbcf`，mtime 更新）⇒ **内容零变化**；反过来这也证明**交付的 `redline_check.json` 是逐字节可复现的**，`all_pass=false` 是**当前状态**而不是陈旧产物（F7 因此更硬）。
- 除此之外**未修改路线 A 的任何文件**；本目录唯一的新增文件是本报告 `VERIFICATION-2026-10-21.md`；探针脚本写在 `/tmp/vrA/` 并已删除。

---

## 5. 复核方法（可复现）

```bash
# 1) 规范渲染（自己跑）
python3 /workspace/lab/build_spec_flowchart.py /workspace/lab/routes/A/spec.yaml $T "路线A" "t"
#   ⇒ 4443 字符 / 4701 字节；rect=9 path=16 text=9
# 2) 黑名单（用正确路径 + 路线 A 全量文件）
python3 /workspace/lab/routes/A/blacklist_check.py $(find /workspace/lab/routes/A -type f ! -path '*__pycache__*')
#   ⇒ source_files=8 strict=5644 hint=104 strict_hits=0 hint_hits=1(DESIGN.md:432「的最后一」)
# 3) 红线自检（复现交付状态）
cd /workspace/lab/routes/A && OPENROUTER_BASE_URL=https://api.minimaxi.com/v1 python3 redline_check.py
#   ⇒ hard_fail_total=2（FACET:FA1:why / FA6:why 的「承重」）、all_pass=false、exit 1
# 4) 干跑
python3 /workspace/lab/routes/A/dryrun_test.py     # ⇒ 全部通过，exit 0
# 5) 冒烟日志读数
python3 -c "import json;d=json.load(open('/workspace/lab/routes/A/smoke/smoke_log.json'));print(d['total_api_calls'],d['total_tokens'],d['endpoint'],d['primary_model'])"
#   ⇒ 12 23727 https://api.minimaxi.com/v1 MiniMax-M3.1-Flash-Preview
```

**探针清单**（全部写在 `/tmp/vrA/`，未落进路线 A 目录）：
- `replay.py` —— 用冒烟日志做打桩重放，**逐字节**比对答案与 meta
- `probe_token.py` —— 证明 `max_tokens` 守卫是**进程累计**（第 3 题被中止）
- `probe_axes.py` / `probe_axes2.py` / `probe_axes3.py` —— Mednick 两腿对照、A_minus_D3 可实现性、预注册常量下第二轮是否触发
- `probe_evict.py` —— 「远」轴把「有用」条目挤出答案（顺序敏感）
- `probe_random_rest.py` —— `A_random_rest` 的 prompt 与 `A_fixed` 逐字节不同
- `probe_prompt_hygiene.py` —— 19 条注入串 × 4 类宽词表 ⇒ 全 0 命中

---

## 6. 修复清单（交给生产者，按优先级）

1. **F1**：`max_tokens` 改成 per-run 计数（与 `max_calls` 同款本地计数），`meta.n_tokens` 报本 rep 的值；补一条「连跑 3 题第 3 题不被中止」的回归断言。
2. **F2**：给 `resample_mode` 增加真正的 `"structured_no_cover"` 分支（不带已覆盖清单），或把 `A_minus_D3` 改写成一个能被执行的 config；**并给每个消融臂加一条「与 `A_fixed` 逐字节不同」的断言**（现在的干跑断言太弱）。
3. **F3**：二选一 —— 要么删掉数据依赖的塌缩开关（让 N4 恒定执行，与 `spec.yaml:156` 和「固定拓扑」对齐），要么把 `spec.yaml:156`、`DESIGN.md:301,146` 全部改成「条件执行」并如实重述 D6 被弃的理由。
4. **F4**：把新颖轴的输入改成**效用过滤之后**的池（或至少对「被支持」条目优先做冗余判定），并补一条断言：「未支持的条目不得挤掉被支持的条目」；同时删改 `DESIGN.md:62,603` 的「保证不冗余」措辞。
5. **F5**：补 `meta.json` 的 20 个缺失字段与 `RUNS/...` 写出；`seed` 要么接上（需先给 client 加 seed 透传并落进 payload），要么在 §3.5/§6.4 显式标注「不可实现，降级为待实现」（《必修 5》的口径）。
6. **F6**：把 `lex_thr/struct_thr` 的标定过程与读数**落进交付包**（单独的 `CALIBRATION.md` 或写进 `smoke_log.txt`），并与交付日志的实际读数（12/12、11/12、10/10）对齐。
7. **F7**：`blacklist_check.py` 增加「目标列表为空 ⇒ 显式报『未执行』且退出码 ≠ 0」；`redline_check.py` 把扫描范围收窄到**真正注入的字符串**（或把 `why` 字段排除后再判）；`DESIGN.md:261,556` 与 `redline_check.json` 的 `all_pass` 必须一致。
8. **F8**：统一节点编号（建议以 `spec.yaml` 的 N0–N8 为准，DESIGN 图与代码 docstring 对齐），并让 `deliverable.md` 的拓扑描述与之一致。
9. **F9**：实现 B1（K 次直调取最后一份）、B2（采样到 token 预算）、B3（外部核验器择优），否则把 §5.1 改写为「协议侧执行」并注明路线 A 不承担。
10. **F10**：把 FA-8 改成对两个负对照**分别**、且用**主判据**（VD）触发的条件；删掉 `DESIGN.md:402` 的「R1 触发」预期。
11. **F11**：按 `facets.py` 真实目录改写 `deliverable.md` 的描述；修正「nodes: 20 个」「8 节点」「两个缺陷」三处。
12. **F12**：冒烟至少跑一次**预注册拓扑**（4+2 承载面、`collapse_mult=1.0`），把「哪些臂会触发第二轮」记进日志。
13. **F13/F14/F15**：`openrouter_used` 改成由 `usage_log` 计算；字数上限口径与 `break` 偏置说明清楚；`meta` 记录**实际使用的模型**。

---

*本报告为独立复核结论，只做判定不做修补。路线 A 的文件**内容**均未被修改；唯一的副作用是运行生产者自带的 `redline_check.py` 时其输出产物 `redline_check.json` 被重写（md5 前后相同，见 §4.5 披露）。*
