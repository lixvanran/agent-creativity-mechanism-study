# 独立复核：路线 B · 训练架构（操作序列由训练学出）

**复核者**：Verifier ｜ **日期**：2026-10-20 ｜ **对象**：`/workspace/lab/routes/B/`（DESIGN.md / spec.yaml / code/ / smoke/）
**原始依据**：`/workspace/research/adhd-creativity/track-d-transfer/deliverable.md` §4–§5、`/workspace/lab/routes/PROTOCOL.md`
**方法**：全部结论回到原始文件与可执行代码；不采信生产者的自述；不改任何项目文件（临时脚本只落在 `/tmp`）。

---

## 0. 一句话结论

**这条路线本身是真的可被否证的**（否证条件、监控、变异自测、等预算对照臂、预注册校准都经得起对抗性检查，R-1…R-13 全部干净，冒烟日志经字节级重建证明为真实运行）。
**但交付物当前不能按"已核验的规格"接受**：`DESIGN.md` 全文唯一的"实测"章节（§3.8 / §9.1 / §9.2）对自己引用的那份冒烟日志**报了 6 处错**，其中一处把截断发生的通道**说反了**，并据此宣称"已被 D1 修好"——而冒烟脚本的结构**决定了它根本不可能验证 D1**；同时文档与交付说明都声称已实现"训练循环"，而该循环在代码里**不存在**。

⇒ **VERDICT: FAIL**（缺陷全部可修；路线架构本身不必推倒重来）

---

## 1. 判死项（必须修）

### F1 ★ DESIGN.md 唯一"实测"章节对它自己引用的日志报了 6 处错
**Method**：把 `DESIGN.md` §3.8/§9.1/§9.2 的每个数字与 `smoke/smoke_log.json` 的 `calls[]` / `e2e[]` / `t0,t_end,total_secs` 逐格对拍。
**Evidence**：

| 位置 | DESIGN 的说法 | 日志/代码的实际值 | 判定 |
|---|---|---|---|
| `DESIGN.md:479` | 尝试级截断 `finish_reason=length` **2 次（都是 `al_ex`）** | 两次都是 **`check2`**（判官通道，`evidence_index.py:152`）：`call#5 mt=1200 length content_len=0`、`call#6 mt=2000 length content_len=0`；两次 `al_ex` 调用（`call#2`、`call#10`）都是 `finish_reason=stop` | **说反了** |
| `DESIGN.md:289` | "**冒烟最后一次运行**：DS2 的 `al_ex` 两次都截断 ⇒ `n_claims=0`、`w_hat=0.0`、最终答案是空壳" | 最后一次运行 DS2：`n_claims=9`、`w_hat=0.333`、`answer_len=312` | **与所引日志矛盾** |
| `DESIGN.md:305` (D7) | "冒烟里 `n_calls=11` 就是'8 次逻辑调用 + 3 次重试'" | `n_calls=14`、`n_logical_calls=12`、`n_calls_ok=12` | **错** |
| `DESIGN.md:478` | "**端到端耗时** 197.9 s" | 日志自身 `t0=01:50:06 → t_end=01:53:10` = **184.0 s**；`197.9` 是逐次尝试**累计**秒数之和（`client.py:63` 每次 `chat()` 只设一次 `t0` ⇒ 重试那次被重复计时） | **口径标错** |
| `DESIGN.md:478` | "均值 ≈ **14.1 s/次**" | 真均值 = 184.0/14 = **13.1 s/次** | **偏高 ~7.5%** |
| `DESIGN.md:496` | "按冒烟实测 **16.6 s/次**外推" | 与 §9.1 自己的 14.1、真值 13.1 **都对不上**；且 640×16.6 s ÷ 8 worker = **0.37 h**，非所称"1.5–2 h"（差 ~5×）；C4 种群 1920×16.6÷15 = **0.59 h**，非所称"4–6 h"（差 ~8.5×） | **成本估算不成立于自身输入** |

**Result: FAIL** — `DESIGN.md:479 / 289 / 305 / 478 / 496`

### F2 ★ "D1 已被验证"这个结论，冒烟结构上给不出
**Method**：读 `smoke.py:88-93` 与 `client.py:53-58` 的重试阶梯语义。
**Evidence**：
```
smoke.py:92        kw["budgets"] = (2000,)        # 无条件覆盖调用方给的 budgets
train_policy_v2.py:136  al_ex  : max_tokens=2000, budgets=(3200, 4400)   # D1 修好的阶梯
evidence_index.py:153   check2 : max_tokens=1200, budgets=(1800, 2400)   # 判官的生产阶梯
client.py:58      for mt in (max_tokens,) + tuple(budgets):
```
`smoke.py:92` 覆盖了**所有**通道的阶梯 ⇒ 冒烟里 `al_ex` 跑的是 (2000,2000)、判官跑的是 (1200,2000)，**都不是生产配置**。
⇒ 观察到的 2 次截断是"被冒烟自己降级的预算"造成的；`DESIGN.md:479` 归因给 `al_ex`、`:485` 归因给"D1 已消失"**均无证据支撑**，且真正截断的判官通道不在 D1 的处置范围内。
**Result: FAIL** — `DESIGN.md:479 / 485`（并须修 smoke 的阶梯覆盖，或声明"冒烟不测 D1"）

### F3 ★ 声称已实现的"训练循环"在代码里不存在
**Method**：`grep` 全代码树找驱动点。
**Evidence**：
```
$ grep -rn "reinforce(|Ema(|Monitor(|TauController(" code/*.py | grep -v "def |__pycache__"
（无调用点）
$ grep -n "^def |^class " code/train_policy_v2.py
46:def _last_call   59:def _call_flags   68:def run_episode   218:def reinforce   244:class Ema
```
`reinforce()` 从未被调用；`Ema` 从未被任何调用方实例化；没有轮次循环、没有滑动基线更新、没有早停、没有 §4.4 的校准闸门。`DESIGN.md:571`（§12 实现映射）写"**新写**：训练循环（on-policy + EMA + 留出纪律 + 校准闸门）| `code/train_policy_v2.py`"，交付说明的文件表也写"训练循环参考实现"——**两者都不成立**。§3.6 的伪代码是完整的（可实现），但"可执行"目前只到组件级。
**Result: FAIL** — `DESIGN.md:571` + 交付说明文件表

### F4 ★ 声称的 on-policy REINFORCE 梯度不是所实现策略的梯度
**Method**：对 `policy_probs`（先标准化再 softmax）做中心差分真梯度 vs `reinforce()` 用的解析式 `φ_a − Σ_i π_i φ_i`。
**Evidence**：
```
trial0: cos(解析式, 数值真梯度) = +0.7887   max|Δ| = 2.3668   (真梯度范数 0.855)
trial1: cos = +0.6327   max|Δ| = 1.0289  (范数 0.344)
trial2: cos = +0.9061   max|Δ| = 1.2134  (范数 0.364)
```
`π = softmax((s−mean(s))/std(s)/τ)` 的 log-π 对 w 的梯度还含 mean/std 的 Jacobian，解析式漏掉了这一项 ⇒ 估计量**有偏**（方向大体对，不是 score function）。`DESIGN.md:210` 把该式当作精确式列出，§3.3 又以"on-policy 三个必要条件"的口径作保证。（此性质继承自旧实现，plan 明确说"已修好的东西不要重复发明"；但设计重新推导并公示了这条公式，就应标注它的偏差。）
**Result: FAIL** — `DESIGN.md:205-212`

### F5 ★ 判官提示词违反协议的强制条款，且全文未提
**Method**：把 `CHECK_V2`（`evidence_index.py:78-105`）与 `PROTOCOL.md:521-526` 逐句对拍。
**Evidence**：
```
PROTOCOL.md:522  「只要陈述里含有超出问题本身的信息…就当它是断言」        -> CHECK_V2 中不存在
PROTOCOL.md:523  「由题面数值 + 依据包规则推导出的结论，是断言，不是复述」 -> CHECK_V2 中不存在
PROTOCOL.md:524  「不确定时一律答『未提及』」                          -> 存在 ✔
PROTOCOL.md:526  「判官必须拿到题面（prompt）与结论空间 C_t」           -> CHECK_V2 只有 {ask}{ev}{claims}{n}，C_t 从未传入
```
`CHECK_V2` 用的是自己的"法律主张 vs 复述情形"判准，而 DEV 集被协议规定为**跨领域**（`PROTOCOL.md:444`：常识判断/短期规划/分类判定/冲突权衡/数量比较/规则应用）⇒ 域偏置的判准在非法律类题上落空。`DESIGN.md`/`spec.yaml` 全文未出现 "§4.6"（grep 无输出）。
**Result: FAIL** — `evidence_index.py:78-105` + DESIGN 需新增 §4.6 自查

---

## 2. 应修项（不判死，但要写清）

### F6 Mednick 双条件的"远"这一半，在训练目标里没有、也从未被点名
**Evidence**：`grep -n "Mednick" DESIGN.md spec.yaml code/*.py` → **0 命中**；`DESIGN.md` 全文的"多样性"只指**任务多样性**(C1)、**策略种群多样性**(C4)、搜索闭合诊断——都不是 Mednick 的"远"（协议 §1.4 的"去冗余/删除反事实"）。
代理 `Ŵ` 按**依据条目**计数，G1 自己承认"协议按删除反事实归族 ⇒ 代理系统性偏大"。
**为何不判死**：合取在**验收层**被强制执行——主判据是协议的 VD（族级去冗余）+ F1/F2/F5，且 §4.4 预注册了 `Spearman(Ŵ, vd_final) ≥ 0.50` 的交叉校验与 FB6 杀死开关 ⇒ **任何路线 B 的"成功"都不可能在违反"远"的输出上拿到**。
**为何仍要写**：读 §4 的人会以为训练目标实现了完整判据。**要求**：§4 明写"代理只实现合取中的'有用/承重'一半；'远'由协议 VD 在验收层强制，代理偏离由 FB6 判死"。

### F7 步级奖励是一个未去重的"条数"项，§4.5 第 3 条说得太满
**Method**：用设计自己的代码跑对抗对照（`/tmp/probe2.py`、`/tmp/probe3.py`）。
**Evidence**：
```
A. 1 条断言 + 1 次核验（覆盖 E1）          Ŵ=0.3333  步奖励=+1.0  终局=+1.0  总回报=+2.000
B. 3 句改写同一件事 + 2 次核验（仍只覆盖 E1） Ŵ=0.3333  步奖励=+2.0  终局=+1.0  总回报=+3.000
C. 8 句改写同一件事 + 4 次核验            Ŵ=0.3333  步奖励=+4.0  终局=+1.0  总回报=+5.000
D. 3 件不同的事（覆盖 E1/E2/E3）           Ŵ=1.0000  步奖励=+2.0  终局=+3.0  总回报=+5.000
```
`Ŵ` 本身确实抗灌水（分母固定 + 按条目去重 ✔），但 `VERIFY→支持 +1.0/步`（`train_policy_v2.py:192-197`）**按核验步数计**，不受条目去重保护 ⇒ **灌水能追平诚实策略**（C 与 D 同分）。`DESIGN.md:223` 的理由"避免'多写多抽'被直接奖励"与 `DESIGN.md:363` 的"灌水/重复/加长**都不涨分**"对**总回报**不成立（只对 Ŵ 成立）。此缺口未出现在 G1–G6 或 L1–L9。
**要求**：步级奖励按条目去重，或把 §4.5-3 明确限定为"只对 Ŵ 成立"，并在差距表补一行。

### F8 判官解析器不是"严格"的
**Evidence**（`/workspace/lab/routes/B/code/evidence_index.py:116` 正则 `^\s*(非主张|支持|矛盾|未提及)\s*[|｜:：/]?\s*(.*)$`）：
```
"支持 E1"（无分隔符）      -> 接受 → 支持|E1
"支持 | E99"（伪造编号）   -> 接受 → rel=支持, items=[]  ⇒ n_supported/support_rate 虚高、conflict_rate 被压低（F8 同族）
"支持 | E1 blah blah"（尾部垃圾）-> 接受，无告警
"大概支持 | E2"（未知关系）-> 该行被丢弃 → 配对错位；但因行数不符 ⇒ 触发"解析失败"⇒ 重试 ✔（计数保护有效）
```
`DESIGN.md:523` 的"被**严格**逐行解析器识别"与代码 docstring 的"严格逐行解析"名不副实（其真实意图"前言不被误配"是达成的）。**要求**：把 `支持|E99` 判为解析失败并把分隔符设为必需。

### F9 guard 的"命中即 abort"在已交付入口上基本不成立
**Evidence**：`guard.py` 的 `__main__` 调 `check({})`（**不传任何文本**）⇒ 命中恒为 0 ⇒ `python3 guard.py` 恒 `EXIT=0`（实测）；`smoke.py:126-129` 的 `check_blacklist()` 只把 `bl_ok` 记到 `smoke.py:467-469` 的最终返回码 ⇒ **命中不会中止运行**，仍会先烧掉 LLM 预算。`guard.py:1-6` 声称"命中即 abort"。
**另**：`smoke.py:37` `CALL_CAP = int(os.environ.get("SMOKE_CALL_CAP","20"))` ⇒ "硬上限 20"是**可被环境变量改写的默认值**；`smoke.py:76` 的 docstring（"budgets=() ⇒ 1 次逻辑调用 = 1 次 HTTP 调用（无重试）"）与 `smoke.py:92` 自相矛盾；`DESIGN.md:592` 写"FB1–FB11"而 §7 实为 FB1–**FB12**；`spec.yaml` 的 `chosen: yes` 在 yaml_lite 下是**字符串 `'yes'`**、在 PyYAML(YAML 1.1) 下是**布尔 `True`**（可移植性隐患）。

---

## 3. 通过项（必须承认，避免一棍子打死）

| # | 检查 | Method | Evidence | Result |
|:-:|---|---|---|---|
| P1 | 交付物是否真实存在 | `ls -laR lab/routes/B/` | 15 个文件全部在位（DESIGN.md 51 KB / spec.yaml 26 KB / code/ 9 个 .py / smoke/ 3 个日志 / data/） | PASS |
| P2 | R-1/R-13：U1–U4 是否泄漏 | grep `多血质\|陈会昌\|胆汁质\|user4` 全路线 + 重跑 guard | 仅 `guard.py:26-27` 的黑名单**读取路径**；`guard.py` 实跑 `total_hits=0, ok=true`；诊断题为自造"图书馆/健身房" | PASS |
| P3 | R-8：无 OpenRouter | 读 `smoke.py:97-104` + 日志 | 端点 `https://api.minimaxi.com/v1`，`openrouter_used:false`，14 次调用 model 全为 `MiniMax-M3.1-Flash-Preview`；子代理实测把端点改成 openrouter.ai 会 `SystemExit: ABORT` | PASS |
| P4 | R-2/R-3/R-4/R-5/R-6/R-7 | 打印 4 条提示词全文 + grep 人格词 + 读特征实现 | 生成侧提示词只含 `{ask}`/`{t}`/`{c}`/任务无关角度词表；无答案暗示、无评价标准、无题目实体、无自述当判据；`SLOTS` 不在 `FEATURE_NAMES`；`anchored` 分母不进特征也不进生成提示词 | PASS |
| P5 | track-d §5.1–§5.8 危险区是否被重新写进设计 | 逐条对拍 §5.1–§5.8 | 无条件加随机性/ sleep(30)/ 只追语义距离/ LLM 自评择优/ 只注入多样性/ 辩论/ ADHD 人格 / 发散思维当验收 —— **均未出现**；τ 是塌缩控制器（还会在熵过高时**调低**），不是创造力旋钮 | PASS |
| P6 | Mednick "有用"侧是否扎实 | 读 `proxy_report` + 独立探针 | 分母 = `len(anchored)` 固定；分子 = `set` 去重的锚定条目；重复/花絮/矛盾 ΔŴ=0，只有新锚定条目才涨 | PASS |
| P7 | 代理是否退化成"条数/宽度/长度" | 读特征表 + `spec.yaml features.excluded_features` | Ŵ 是**比例**且按条目去重；`text_length` 明确排除出特征；承重检验可逐条说清（每条 anchored 条目指名它承载的结论） | PASS |
| P8 | 冒烟日志是否真实存在、≤20 次 | 独立读日志 + 子代理**字节级重建** | 用 `raw_outputs` 重建装配答案 ⇒ DS1 `answer_len=307`/`answer_head` **逐字节相同**、DS2 `312`/逐字节相同；12/12 内部一致性检查通过；14 ≤ 20；端点/模型/黑名单全部一致 | PASS |
| P9 | 见证回归断言是否摆设 | 亲自跑两模式 | 正常 `PASS=true`；`--mutate` ⇒ 5 个 argmax 全塌成 `GEN_PLAIN`、`PASS=false`；子代理另注入 4 种更强变异（清零交叉项/交换 t1 t2 语义/让旧特征变成 op×state 依赖/全零特征）全部 `PASS=false` | PASS |
| P10 | 监控告警会不会响 | 亲自跑 `monitor.selftest()` | 8/8 全 true（塌缩/操作熵/动作覆盖/权重冻结/奖励停滞/矛盾越界/搜索闭合/τ 反向） | PASS |
| P11 | 是否"看起来合理"之外还可被否证 | 读 §7/§6/§4.4 | FB1–FB12 每条带数字触发条件；8 条对照臂含协议 §8(c) 全套（B0/B1/B2/B3，best-of-N 由**外部核验器**选）；§4.4 预注册校准 + FB6 杀死开关 | PASS |
| P12 | 有没有把"设计"说成"结论" | grep + 读 §1.5/§10.2/§11 | 无训练结果、无路线优劣；P-1 明确标为"预注册预测（不是成绩）"；§10.2 列明冒烟没验证什么 | PASS |
| P13 | spec.yaml 能否据此画流程图 | 用项目自带 `yaml_lite` 解析 | 23 个顶层键（与声称一致）；8 臂 / 12 FB / 16 监控项 / 7 个特征块，与 DESIGN 一致；动作空间/候选规则/特征表/超参/奖励/数据流齐备 | PASS（PyYAML 缺失，无法双解析对拍，已记为局限） |

---

## 4. 复核方法与局限

- 全部结论回到原始文件与**可执行代码**（跑 `test_v2_witness.py` 两模式、`monitor.selftest()`、`guard.py`、自写 3 个 `/tmp` 对抗探针）；两个独立子代理分别做冒烟日志审计与代码/规格审计，其结论我逐条复算后才采纳（例如子代理称"4 行/3 断言 ⇒ 无重试"，我复算后确认是**行数不符会触发重试**，故未采纳该条措辞）。
- **未做**：未重跑那 14 次真实 API 调用（沙箱无外呼，遵守 R-8）；未做 `Ŵ↔真VD` 校准（协议 N2 抽取器未就绪，设计已如实声明）；未验证 PyYAML 与 `yaml_lite` 的逐值对拍（PyYAML 未安装且无网络）。
- **未改动任何项目文件**；临时脚本仅在 `/tmp`；`cmp8repo` 未触碰（`ops.py` 未动，v2 为并列新模块，`check_ops_consistency.py` 约束被遵守）。

## 5. 放行条件（修完即可复验）

1. 重写 `DESIGN.md` §3.8 表 2/4、§3.8-D7、§9.1、§9.2：按日志实况改（截断通道 = 判官 `check2`；`n_calls=14=12+2`；端到端 184.0 s、均值 13.1 s/次；统一 §9.2 的每调用耗时并让 wall-clock 由其推出）。
2. 要么让 `smoke.py` 不用统一覆盖 `budgets`（按通道用生产阶梯），要么在 §3.8/§9.1 明写"**本次冒烟未检验 D1 的阶梯**"，并把判官通道的阶梯处置补进 D1。
3. 实现 §3.6 的训练循环（轮次 / 滑动基线 / EMA 部署 / 早停 / 校准闸门），或在 §12 与交付说明中把 `train_policy_v2.py` 改称"组件库"并列出待补清单。
4. 在 §3.3 标注标准化 softmax 下解析梯度有偏（或改用精确 score function）。
5. 判官提示词补齐 `PROTOCOL.md:522-523` 两句、传入 `C_t`，并在 DESIGN 增加 §4.6 自查行。
6. §4 增写"代理只实现合取中的'有用/承重'一半；'远'由验收层 VD 强制、偏离由 FB6 判死"。
7. 步级奖励按条目去重，或把 §4.5-3 限定为"只对 Ŵ 成立"并进差距表。
8. 解析器：`支持|E99` 判解析失败；分隔符设为必需。`guard.py` 的 `__main__` 真正扫描并以非零码退出；`smoke.py` 命中即 abort（在进行 LLM 调用之前）。

---

*本报告为独立复核，不含任何"路线 B 更优/更劣"的判断，也未复述生产者的任何未经复算的结论。*
