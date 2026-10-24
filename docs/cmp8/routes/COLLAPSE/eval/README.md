# `routes/COLLAPSE/eval/` · 第二组评测层（层2 设计路线 + 层1 原因分析）

> 2026-10-22～23 ｜ 第二组 ｜ 合同：`routes/HANDOVER-GROUP2-DESIGN-LAYER1.md`
>
> **这个目录是干什么的**：给"搜索空间塌缩 / 过早闭合"造**能证伪的尺子**。
> 生成侧（产答案）属主会话；本目录只管**判据、闸门、代理量、审计**。

---

## 0. 三十秒上手

```bash
cd docs/cmp8/routes/COLLAPSE/eval

# ① 机械自检（零 API，秒级）：12 夹具 + 8 个变异注入
python3 -B selftest_fixtures.py --no-api

# ② 判官层自检（需 MiniMax key）：岔口归并纯度 + 锚外探针自检
python3 -B selftest_fixtures.py --out selftest_out_c

# ③ 判官通道健康度探针（★ 昨天 44% 空内容的根因在这）
python3 -B probe_effort.py --out runs/dev/effort_probe \
    --answers W_div#D01,B0_direct#D01 --efforts max,medium,low --rounds 2 --workers 4

# ④ 跨判官稳定性合表（零 API，读已落盘的 JSON）
python3 -B build_stability.py --out runs/dev/stability \
    --v1 runs/dev/judge_variants3/judge_variants.json \
    --vx runs/dev/judge_variants_sc/judge_variants.json

# ⑤ 把读数渲染成**可进 git** 的证据表（原始 JSON 在 runs/，被 .gitignore 忽略）
python3 -B build_evidence_tables.py --out results
```

---

## 1. 文件地图

### 判据 / 闸门（核心）
| 文件 | 作用 | 状态 |
|---|---|---|
| `vd_anchor_out.py` | **锚外通道**：`VD_anchor_in` / `VD_anchor_out`、双探针、族级留一、A3′、闸门 A1–A9、原始卡落盘（可离线复算）| ✅ 实现 + 自检通过 |
| `selftest_fixtures.py` | Tier A（机械，零 API）+ Tier B（判官层）自检 | ✅ Tier A 通过；Tier B 通过（纯度 0.808 / 分离度 0.989 / 探针真 3/4 假 6/6）|
| `ANCHOROUT-GOLD.md` | **锚外金标建设规程**（把读数从"能引用"推到"可信"的最短路径）| ⏳ 规程已写，金标**未建**（DEV 128 张金标卡全是锚内）|

### 判官 / 跨判官
| 文件 | 作用 | 状态 |
|---|---|---|
| `judge_variants.py` | 4 个判官变体 + **按题分组**的自检 + 读数 | ✅ 完成 |
| `build_stability.py` | 把各变体读数合成跨变体稳定性表 | ✅ 完成 |
| `JUDGE-VARIANTS.md` | 设计 + 实测三条硬结论 | ✅ |
| `probe_effort.py` | **effort 档位探针**：通道健康度 × 判官质量（两轴）| ✅ 实现（2026-10-23）|

### 层2 臂设计
| 文件 | 作用 | 状态 |
|---|---|---|
| `NOAUTH-ARMS.md` + `vote_judge.py` | B-2a 去权威化 2×2（N11/N10/N01/N00）+ 逐条对照表判官 | 臂定义 ✅；**实跑属主会话**（生成侧）|
| `BESTOFK-EQUIV.md` + `budget_axis.py` | B-2e 等 **$** 预算轴（节点数在成本上不等价）| 口径 ✅；**实跑属主会话** |
| `audit_format_symmetry.py` | B-2d 格式对称性审计 | ✅ 实测：**4 个字段不对称** |

### 层1 代理量
| 文件 | 作用 | 状态 |
|---|---|---|
| `layer1_proxies.py` | P1a / P1b / P3a / P3b / P4lb | ✅ 已实现并实测 |
| `dev_gen.py` | DEV 三臂生成（B0_direct / B0_noev / W_div）| ✅ 9 份答案已生成 |

### 文献
`../LIT/DEEP-L1-CITED-NUMBERS.md`（核证表，**推翻三处我方归因**）｜`../LIT/DEEP-L1-ATTENTION.md`（机制侧核证）

---

## 2. ★ 读这份代码前必须知道的 5 件事

1. **锚内逐字沿用 `batch-U1/measure.py` 的 `measure.CARD_Q`** —— 只 import 调用，**不改判据**
   ⇒ 锚内读数与历史可比，且避免"判官与指标同源"污染。
2. **两条通道是独立的**：锚外用**新提示词**（`CARD_Q_OUT` + 双探针 `FORK_PROBE_Q` / `FORK_PROBE2_Q`），
   **不共享**锚内判官 ⇒ 不把"同一次判官自问自答"当独立复核。
3. **结构化绑定取代措辞相似度**：岔口归并成封闭枚举 `K1/K2…`；留一**按族**（一族=1 维度，与协议 §1.4 一致）。
   ⇒ 措辞级 Jaccard 实测**恒为 0.000**，不可用。
4. **失败不许静默变 0**：任一调用失败 ⇒ 该份读数 `valid=0` + `channel_failed=true`；
   理论闸门**先过通道健康检查**（健康度 <0.9 ⇒ 闸门不生效）。
5. **本组不改**：`routes/COLLAPSE/workflow.py`、`batch-U1/measure.py` 的判据、`routes/DEV/`、`routes/COLLAPSE/runs/`。

---

## 3. `results/` —— 进版本控制的证据副本

`runs/` 被 `.gitignore` 忽略 ⇒ 原始 JSON 进不了 git ⇒
`build_evidence_tables.py` 把它们**程序化**渲染成 `results/*.md`（**不手抄** ⇒ 摘要与事实不会漂）。

| 文件 | 内容 |
|---|---|
| `JUDGE-STABILITY-2026-10-23.md` | 4 判官 × 9 份的读数 + 各自自检 |
| `CROSS-RUN-REPRO-2026-10-23.md` | 同一判官两次独立跑批的逐份一致性 |
| `SELFTEST-2026-10-23.md` | Tier A / Tier B 自检结果 |
| `EFFORT-PROBE-2026-10-23.md` | effort 档位探针（健康度 × 质量）|

---

## 4. 当前**已知的坑**（都在代码里防住了，但要知道）

| 坑 | 后果 | 防法 |
|---|---|---|
| MiniMax 思考块烧光 `max_tokens` ⇒ **44% 调用空内容/截断** | 8/9 份答案降级为"描述性" ⇒ **所有维度数读数不可引用** | ★ 官方文档：*"lower the effort level"* ⇒ `LLM.chat(effort=...)`；阶梯只是兜底 |
| 自检集**混题** ⇒ 判官真卡率被压到 0.375 ⇒ 误写"判官过严" | **结论方向反了** | 自检**按题分组**（每张卡用它自己那道题）|
| 自检**极性写反**（把"假卡被误放行"当成"通过"）| 坏掉的闸门比没有闸门更糟 | 真卡放行数 / 假卡**拒绝**数**分两个字段**记，并显式断言方向 |
| 提示词模板里的 JSON 花括号没转义 ⇒ `.format()` 抛 `KeyError` | **整批任务全灭而日志是空的** | 模板自检（零成本）|
| 编号 `EV-2` vs `EV-02` 字符串不等 ⇒ "已引用依据"被静默判成"没引用" | 闸门条件被静默清零 | 编号拆成「前缀+数字」再比 |
| 语言闸门"中文 ≥90%" ⇒ 误杀含 `MB/s`/`IOPS` 的中文答案 | 3/9 份被误判成漂移 | 改两道：整体 CJK ≥0.5 **且** 段间差 ≤0.25 |
| `pkill -f <脚本名>` **匹配到自己** | 杀错进程 | kill/detect 模式**写进脚本文件** |

---

## 5. 边界（本目录**不能**做什么）

- **不能**跑生成侧四臂（去权威化 2×2）与等 $ best-of-k 的实跑 ⇒ 属主会话。
- **不能**保证锚外读数可信 ⇒ 缺金标（规程见 `ANCHOROUT-GOLD.md`）。
- **不能**声称"维度数"是绝对刻度 ⇒ 无判官通过自检（见 `results/JUDGE-STABILITY-*.md`）。
