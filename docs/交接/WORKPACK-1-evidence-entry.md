# 工作包一 · 最新版证据入口（第二组）

> 出处：`/workspace/lab`（分支 `cmp8-handover-2026-10-20`）
> ★ **判据版本锚（★ 负责人 2026-10-25 裁决：不写死 sha，写"正式批启动时的 HEAD"）**：
> ★ **正式批启动时的 HEAD = `17244d2d329c69939e88476f3a93d275ec7296a6`（2026-10-24 13:44:51 +0800）**
> ★ **该 commit 已包含 6 臂设计（含 `nosel_b3_synth`）+ §2.0d 两因子分解 + H-TOPO-4c/4d**
> ★ **凡此后的任何判据改动，一律登记在 `PREREG-TOPOLOGY-ARM.md` §6「数据产生后的改动记录」**
> ★ **本包生成时间**：2026-10-25｜★ **指纹 = sha256 前 16 位**｜★ **本包不删旧表述，只标"最新/已更正"**

---

## ★ 0. 先说三条读本表的纪律

1. ★ **「代码版本」≠「实际执行版本」** —— ★ 二者可能不同（★ 例：拓扑臂正式批跑的是 `17244d2` 的代码，而 `check_readout_liveness.py` 是**跑完之后**才加的 ⇒ ⇒ **它没有参与那批数据的产生**）
2. ★ **「指标名」≠「口径」** —— ★ **同一批数据在两代指标下读数不可比**（★ 例：2×2 批用的是 `effective_rank`/`spread`（旧代），拓扑臂用的是 `vendi`/`modes`（新代）⇒ ⇒ **跨批对数前必须先对口径名**）
3. ★ **自检门禁全绿 ≠ 内容正确** —— ★ `crosscheck_report.py` 查的是**内部一致性**；★ 数字本身对不对，必须有**独立回源路径**（★ 本表第四列就是）

---

## ★ 1. 方向 → 证据入口总表

| # | ★ **方向** | ★ **代码版本（指纹）** | ★ **实际执行版本** | ★ **数据路径（仓内）** | ★ **分析入口** | ★ **当前报告** |
|:-:|---|---|---|---|---|---|---|
| 1 | ★ **层2 拓扑臂（6 臂，主线）** | `creativity_lab/experiments/topo_arm.py` `c1b45dea3dee0362` | ★ **`17244d2`**（★ 正式批启动时的 HEAD） | ★ `runs/topo-arm-v2-2026-10-25/`（★ **进行中**）｜`units/*.json`（★ run 级）｜`manifest.json`｜`calllog.jsonl` | `python3 -B creativity_lab/experiments/topo_arm.py`（★ 续跑 = 同一条命令）<br>★ 活性检查：`check_readout_liveness.py`（★ **跑后**）<br>★ H0 标定：`h0_calibration.py` | ★ `PREREG-TOPOLOGY-ARM.md`（**633 行**）<br>★ 报告 §2.22/§2.24/§2.25 |
| 2 | ★ **ToT 原版臂（6 臂）** | `creativity_lab/experiments/tot_arm.py` `88704484d1ecd658` | ★ `e3be08a` 及更早 | ★ `runs/tot-arm-2026-10-24/`（9 组） | `build_totarm_tables.py` | ★ 报告 §2.16b（★ **含一条撤回**：4 个 b=5 臂的 `read` 定义上恒等） |
| 3 | ★ **ADHD 臂** | 同上（`run_adhd` 复用 `cmp8/creativity_lab/adhd_repro.py`） | ★ `e3be08a` 及更早 | ★ `runs/tot-arm-adhd-2026-10-24/`（6 组，★ **3 组作废**） | ★ 归因回源：`frame_structure_probe.py`（★ **零 API**） | ★ 报告 §2.20 / §2.20b |
| 4 | ★ **第五把尺子（`family_key` 语义级）** | `creativity_lab/experiments/family_key_ruler.py` `65d79d07c6fb173c` | ★ `e3be08a` 及更早 | ★ `runs/family-key-2026-10-25/family_key.json` | ★ **零 API**（★ 输入 = `docs/cmp8/batch-U1/measurement_v2.json` 的卡片 + 结论空间） | ★ 报告 §2.22 / §2.24（★ **33.7% 暂不可对外报**，★ 底本只有 16 条命题） |
| 5 | ★ **四把尺子并排重算** | `creativity_lab/experiments/four_rulers_recompute.py` `e32e5f762103a58c` | ★ `e3be08a` 及更早 | ★ `runs/four-rulers-2026-10-24/four_rulers.json` | ★ **严格零 API**（★ 只新算零 embedding 的 `structured_dedup`） | ★ 报告 §2.24 |
| 6 | ★ **n 基线（计数型指标的 n 依赖）** | `creativity_lab/metrics_ext.py` `352a3d0517276523` | ★ `e3be08a` 及更早 | ★ `runs/n-baseline-2026-10-24/n_baseline.json` | `n_baseline()`（★ 在 `metrics_ext.py`） | ★ 报告 §2.21 |
| 7 | ★ **嵌套子集校准** | `creativity_lab/experiments/nested_calibration.py` `56b5a90c824f0f73` | ★ `e3be08a` 及更早 | ★ `runs/nested-calibration-2026-10-24/nested_calibration.json` | `nested_calibration.py` | ★ 报告 §2.21 |
| 8 | ★ **2×2 任务结构对照（★ 旧指标代际）** | ★ **旧代指标**（★ `effective_rank`/`spread`/`lexical_sharing`/`branch_diversity`） | ★ `e3be08a` 及更早 | ★ `runs/divergence-matrix-2x2-2026-10-24/`（21 组 = 7 题 × 3 rep） | ★ 逐组 `group_*.json`（★ 键：`arms.base.modes` / `.effective_rank` / `.spread`） | ★ 报告 §2.19（★ **★ 2026-10-25 已更正 3 处**，★ 见 §2.25 纪律 1） |
| 9 | ★ **pathmulti（路径多样性决定性实验）** | 同 #8 | ★ `e3be08a` 及更早 | ★ `runs/divergence-pathmulti-2026-10-24/`（9 组） | 同 #8 | ★ 报告 §2.19（★ **探索性**：★ 无事前预注册） |
| 10 | ★ **末步类型 4 臂对照** | ★ 旧臂实现 | ★ `e3be08a` 及更早 | ★ `runs/endstep-matrix-2026-10-23/`（9 组） | 逐组 JSON | ★ 报告 §2.15 |
| 11 | ★ **评估器强度** | ★ 旧臂实现 | ★ `e3be08a` 及更早 | ★ `runs/evaluator-strength-2026-10-24/`（9 组） | 逐组 JSON | ★ 报告 §2.14 |
| 12 | ★ **跨批复现** | — | ★ `e3be08a` 及更早 | ★ `runs/divergence-matrix-2026-10-24/` + `runs/divergence-matrix-B2-2026-10-24/` | 逐组 JSON | ★ 报告 §2.13 |
| 13 | ★ **跨组 C1 合成命题（表层分化 ≠ 路径分化）** | `creativity_lab/experiments/cogpos_matrix.py` `a4cbfcaf683bd9b7` | ★ `e3be08a` 及更早 | ★ `runs/cogpos-smoke-2026-10-24/`（★ **冒烟级**，★ 非判决数据） | `cogpos_matrix.py` | ★ 报告 §2.23 |
| 14 | ★ **结论空间（事前写死的互斥命题）** | `creativity_lab/experiments/build_conclusion_spaces.py` | ★ `e3be08a` 及更早 | ★ `creativity_lab/data/conclusion_spaces.json` `7a2e761e56de7244` | `build_conclusion_spaces.py` | ★ 报告 §2.22 |
| 15 | ★ **前人真实配置物证（MAS_Diversity）** | — | ★ `c3f63a6`（★ 清单 181 行） | ★ `docs/cmp8/routes/COLLAPSE/eval/MAS_Diversity-ACTUAL-CONFIGS.md` `f64755adefdfbd33` | ★ 逐 YAML 解析：`/workspace/vendor/mas_configs_parsed.json` | ★ 报告 §2.22（★ 附 **A 篇已收进交差包**） |
| 16 | ★ **题库** | — | ★ `e3be08a` 及更早 | ★ `creativity_lab/data/topics_2x2.json` `effc2a2c350e72ee`（9 题）<br>★ `creativity_lab/data/legal_topics_v2.json` `05b109a9970bc40f`（★ 18 题，★ **语义级轴的底本**） | — | ★ 报告 §2.19 |
| 17 | ★ **H0 标定脚本** | `creativity_lab/experiments/h0_calibration.py` `468e0dbc96c2a6ff` | ★ **跑后**（★ 不参与产生读数） | ★ `runs/topo-arm-v2-2026-10-25/h0_calibration.json` | `h0_calibration.py` | ★ `PREREG-TOPOLOGY-ARM.md` §5.0b2-i |
| 18 | ★ **读数项活性检查** | `creativity_lab/experiments/check_readout_liveness.py` `41888b8a70c38d57` | ★ **跑后**（★ **事后质量门**，★ 不参与产生读数） | ★ `runs/<run_dir>/liveness_check.json` | `check_readout_liveness.py` | ★ `PREREG-TOPOLOGY-ARM.md` §6 改动 1 |

---

## ★ 2. 三条需要特别标注的「实际执行版本 ≠ 代码版本」

| 读数 | 实际跑的代码 | 现在仓里的代码 | 差异 | 影响 |
|---|---|---|---|---|
| ★ **拓扑臂正式批** | ★ `17244d2` | ★ `17244d2` + 未提交改动 | ★ **无差异**（★ 刻意不改 `topo_arm.py`） | ★ **无** —— ★ 活性检查做成了独立脚本，就是为了不碰正在跑的代码 |
| ★ **2×2 批 / pathmulti 批 / 末步批** | ★ 旧指标代际 | ★ 仓里已有新代（`metrics_ext.py`） | ★ **指标口径不同** | ★ **跨批对数前必须先对口径名** —— ★ **Vendi 与 `effective_rank` 不可直接对数** |
| ★ **第五把尺子（`family_key`）** | ★ 底本 `U1-measure-v1-2026-10-21`（★ **只有 16 条命题**） | ★ 目标底本 v2（**69 条命题**） | ★ **底本版本不同** | ★ **⇒ 那个 33.7% 未覆盖率【暂不可对外报】**（★ manifest 已标 caveat） |

---

## ★ 3. 交付通道（★ 负责人 2026-10-25 裁决：双通道 + 纯文本第三条）

| 通道 | 内容 | 依赖 | 状态 |
|---|---|---|---|
| ★ **A（主）** | GitHub branch `cmp8-handover-2026-10-20` | ★ **PAT 需重发**（★ 负责人手工） | ★ **22+ commit 未推** |
| ★ **B（兜底）** | ① `runs/topo-arm-v2-2026-10-25/` 全量 zip ② **直接发层2会话 + 论文簇会话** ③ 落 drive 节点 + sha256 | ★ **零外部依赖** | ★ **跑完即发，不等谁** |
| ★ **C（纯文本）** | ★ **读数表 + H0 标定 + 判决结论，以纯文本直接发到会话** | ★ **无** | ★ **零文件依赖 ⇒ 零单点故障** |

★ **⇒⇒ 结论：★ 即使 A、B 全断，★ 判决要用的数字仍在 C 通道里。**

---

## ★ 4. 数字回源路径（★ 纪律：每个进结论句的数字都要有独立回源路径）

| 数字 | 回源路径 | 备注 |
|---|---|---|
| ★ 拓扑臂 6 臂设计 | `creativity_lab/experiments/topo_arm.py` + `PREREG-TOPOLOGY-ARM.md` §2.0d | ★ 6 臂全部 n 单元 = 5、主层 1 份、辅层 3 份 |
| ★ 2×2 批的 modes | `runs/divergence-matrix-2x2-2026-10-24/group_S1_r1.json` → `arms.base.modes` | ★ **★ 恒定性必须逐题看**（★ S1/S2 恒 1；S3 = [1,3,1]；T2 = [2,1,4]） |
| ★ ToT 候选集 Vendi | `runs/tot-arm-2026-10-24/manifest.json` | ★ S4 1.74 / S5 1.91 / S6 1.61 |
| ★ ADHD 归因回源 | `runs/tot-arm-adhd-2026-10-24/` + `frame_structure_probe.py` | ★ 结构效应只解释 8.1–30.0%（中位 12.0%） |
| ★ `family_key` 覆盖率 | `runs/family-key-2026-10-25/family_key.json` | ★ ⚠️ **旧底本 ⇒ 33.7% 不可对外报** |
| ★ n 基线 | `runs/n-baseline-2026-10-24/n_baseline.json` | ★ Vendi ↑300/↓0；秩/n 0.85→0.56 |
| ★ 嵌套校准 | `runs/nested-calibration-2026-10-24/nested_calibration.json` | ★ 模态 10/27、Vendi 5/27 超机械 p90 |
| ★ **自检门禁** | `python3 -B creativity_lab/experiments/lint_docstrings.py`（197 文件）<br>`test_call_accounting.py`（★ 变异注入有效）<br>`metrics_ext.py`（29 项）<br>`crosscheck_report.py`（48 项） | ★ **★ 门禁全绿 ≠ 内容正确**（★ §2.25 纪律 2） |
