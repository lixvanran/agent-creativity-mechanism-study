# 独立复核：路线 C（先设计再训练）· DESIGN.md

> 来源：team-engine 的 Verifier 会话（session 454518893678848），2026-10-21 01:26–01:30
> 结论：**VERDICT: FAIL**
> 原文见引擎会话记录；此处为结构化摘录 + 负责人补充。

## 结论
> "问题集中在「设计声明」与「可执行实现」之间的落差，以及一条会盖过真实结果的假自检。"

## Check 结果
| # | 检查 | 结果 |
|:-:|---|:-:|
| 1 | track-d §5 八条 ⛔ 危险区是否被重新写进设计 | **PASS**（全文扫描所有命中均在禁止性语境） |
| 2 | Mednick 双条件是否真的合取 | **PASS**（探针：theta_util=0.0/0.5/1.0 ⇒ 答案 56/74/74 字符 ⇒ 门控真实生效） |
| 3 | 红线（U1–U4 泄漏 / OpenRouter / 自述判据） | **PASS（实体成立）**，但**证据链有缺陷**（见 F2） |
| 4 | 代理错位（有效维度是否退化成条数/宽度/长度） | **PASS（带保留）**：设计未自造「有效维度」定义，但训练信号 J 是计数，合法性全押在 C-F2 上 |
| 5 | 否证条件可失败吗 + 对照臂够吗（含等预算） | **PASS**（9 条臂含 B0/B1/B2/B3；C-F1..C-F9 各带触发数据） |
| 6 | **可执行性** | ❌ **FAIL（两处独立失败）** |
| 7 | 有没有把「设计」说成「结论」 | **PASS** |
| — | 冒烟日志独立核对 | **PASS**（13 行 == n_posts 13 ≤ 20；tokens 5383+7904=13287 与日志一致；13 条 URL 全 minimaxi；openrouter 0 次） |

## FAIL 明细
### 6a｜`spec.yaml` 画不出程序流程图（任务第 9 项要求「拓扑节点图」）
用实验室自带的独立消费方 `build_spec_flowchart.py` 实测：
```
route A: bytes=4449 rects=9  paths=16 texts=9
route B: bytes=1693 rects=0  paths=0  texts=0
route C: bytes=1683 rects=0  paths=0  texts=0     ← 空页
```
`spec.yaml` 顶层无 `nodes/edges`（路线 A 有：`A/spec.yaml:99` / `:224`）；
路线 C 把阶段信息嵌在 `topology.stages`（dict）与 `topology.templates[*].stages`（list）里，**没有任何边结构**。
`spec_parsed.json` 同样渲染为空 ⇒ `DESIGN.md:600` 的「导出为 spec_parsed.json（**供画流程图用**）」不成立。

### 6b｜训练回路学不动它声称要学的参数（路线 C 的立身机制）
- **`P12 stop_patience` 是死代码**：`params.py:62` 定义、DESIGN §2.2.2 标「生效拓扑 T1–T5」、`spec.yaml:140` 有条目，
  但 **`executor.py` 从不读取**（T0–T5 无 STOP 阶段，只有日志标签 `BUDGET_STOP`）。
  探针：`stop_patience=0` vs `=3` ⇒ 答案同为 74 字符，**完全无效**。
- **`P3 theta_util` / `P11 m_clusters` 对 J 不变**：J 在 `executor.py:333-352` 由 `self.claims` + verdict 算出，
  而 `_merge` 在其后执行且**不改变 claims** ⇒ J 对二者不变。探针：`theta_util∈{0,0.5,1.0}` ⇒ J 全 = 2；
  `m_clusters∈{1,4,8}` ⇒ J 全 = 2。而 `train_params.py:171-184` 只在 `score > cur_res["J"]` 时接受挑战者
  ⇒ **这两个参数永远回不到先验之外**。
- **真实 8 题语料实测**：坐标下降**只移动了 `n_cand_per_frame`**；
  `theta_util / m_clusters / stop_patience / theta_dist / n_verify_max / n_frames` 全部停在先验。
- **后果**：DESIGN 的「T2 下活着的 7 个参数」实际**只有 4 个可动**；
  **68 次评估里 30 次（44%）可证明结果恒同**；交付物首页「12 个参数由带收缩的坐标下降…学」与所交付代码不符；
  C-F7（C vs A）在门控/装配旋钮上部分空转。
- **两个自检都看不见它**：`check_spec.py` 只对账 spec↔params/topology（**从不校验 params↔executor 接线**）；
  `test_train_loop.py` 只验回路跑得通。

### 6c｜「泄漏在结构上不可能发生」的机制根本不存在
`DESIGN.md:280` 写「提案者只接收 `structural_diagnostics(episodes) -> dict` 这一个入口函数；白名单化 ⇒ **泄漏在结构上不可能发生**」。
全仓 grep `structural_diagnostics` / `whitelist` = **0 命中**；冒烟实际只把说明书传给提案者。
该模式虽默认关闭（`enabled_by_default: false`），但设计的整个 §3.2.2/§3.2.4 论证都靠它。

### 6d｜自检橡皮图章 + 对环境的事实性误述
`verify_blacklist.py:24` 写死 `/workspace/lab/cmp8repo/creativity_lab/data/user4_q*.json`，
而 U1–U4 包实际在 `/workspace/lab/creativity_lab/data/`。
脚本因此打印「**本沙箱不存在**」并**跳过 [1]/[3]/[6]，却仍输出「结果：PASS」并 exit 0**。
`DESIGN.md:612`（§12.6）、`DESIGN.md:640`（附录B R-1）、`train_corpus_meta.json` 的 note、交付物 N2
全部据此写下「U1–U4 依据包文件不在本沙箱」这一**不成立的陈述**。
⇒ 复核者用正确路径独立重跑：**0 命中**（323 条黑名单串 + 5,561 个 ≥8 字片段 × 全部 17 个路线 C 文件）
⇒ **红线实体成立**，但「机器可查证据 = 自检 PASS」这条链是假的，且交付物里 4 处陈述与环境事实相反。

### 6e｜训练侧正确性约束 C2 可被未支持文本满足
`train_params.py:95` 的 `key_hit` 匹配**整份机械答案**，而 `executor.py:280-285` 会把「依据未覆盖」「未经核验」两节也写进答案
⇒ **降低 `theta_util` 放进无依据文本，反而可能抬高 `key_conclusion_hit`**
⇒ C2（每题命中 ≥ 基线）被**未支持文本**满足。

## 复核给出的六条必修
1. 接上 `P12`（在执行器里加真实 STOP/耐心阶段），**或**把它从参数表、spec.yaml 及「12 参数 / T2 活 7 个 / 68 配置」的全部算术中删掉。
2. 让 J 对门控/装配旋钮敏感（建议在**已交付答案**上算「被支持且互不重复的条数」），或明写哪些参数可学并把其余移出搜索空间，然后重算成本。
3. 给 `spec.yaml` 补顶层 `nodes/edges`（或 `flowchart:` 块），使 `build_spec_flowchart.py` 能渲染拓扑图；之后才可写「供画流程图用」。
4. 修 `verify_blacklist.py` 的 glob（改为 `/workspace/lab/creativity_lab/data/`）并重跑；订正 DESIGN §12.6 / 附录B R-1 / `train_corpus_meta.json` note / 交付物 N2 里「不在本沙箱」的表述。
5. 实现 `structural_diagnostics` 白名单入口，或把「结构上不可能泄漏」降级为待实现项。
6. 把 `key_conclusion_hit` 改为只在**被支持子集**上计算。

## 通过的部分（复核者明确要求保留）
拓扑/参数分离判据可机械核对、拓扑析因 + 随机拓扑零假设（**这是本路线真正的增量**）、9 条臂含等预算、
9 条带阈值的否证条件、约束「作废而非扣分」、机械装配不由模型重写、提案者默认关闭 + 强制回退、
冒烟日志真实可审计、失败/未实现项的主动披露（§10/§12）。

## 负责人补充（2026-10-21 02:30）
- 复核者的 6d 与本项目同族教训完全一致：**「自检 PASS」不等于「检查跑过了」**。
  本项目自己的 `push_via_api.py` 也踩过同款（跳过检查仍报"没有需要推送的改动"）。
- 复核者的 6b 正是本项目已记录的 **f[5] 死维**在参数表层面的推广：
  **一个声明存在、但代码从不读取的参数 = 一个死维**。⇒ 任何参数表都应配一条"接线断言"。
