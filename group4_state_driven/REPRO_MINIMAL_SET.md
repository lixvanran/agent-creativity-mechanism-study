# 第四组 · 复现最小充分集与落盘方案（v6 教训驱动）

**写入**：2026-10-25 ｜ **触发**：v6 Stage-1 的三次工程坑（`Select(k=n)` 返回原序 / 失败调用漏记 / `align=None` 被当 0）

---

## 1. ★ 复现的最小充分集（四件，缺一不可）

| # | 项 | v6 现状 | 处置 |
|---|---|---|---|
| **①** | **原始 scores**（派生指标的唯一源头） | ✅ 已落盘 | ★ **必须带【候选 id】与【生成顺序】** —— 否则重算排序时无法复原并列（v6 这次是靠样例文本对上的，**太脆**）⇒ ⇒ **v7 起：scores 落成逐候选记录 `{cand_id, gen_order, score, score_raw, decl_write, decl_drop, decl_parsed, error}`** |
| **②** | **模型标识** | ✅ 已落盘（`model`） | 保持 |
| **③** | **采样参数** | ⚠️ **部分**（temperature/max_tokens 在 calllog；**顶层未落盘**） | ★ v7 起**每个样本顶层落盘** `temperature / max_tokens / thinking / json_mode` |
| **④** | **seed** | ❌ **未落盘** | ★ **v7 起强制落盘**：请求体里**显式带 seed**（若 API 不支持，则记录 `temperature + 采样器状态` 并**如实标注"不可按 seed 复现"**） |

⇒ ⇒ ★ **一句话**：**我这次保住的是 ①（scores）与 ②（模型），③ 要查、④ 要加** ⇒ ⇒ ⇒ **派生指标可以重算，但原始输出不能丢** ⇒ ⇒ ⇒ **落盘的粒度必须能支撑"重算"**。

---

## 2. 落盘规格（v7 起，字段级）

### 2.1 每次调用（`calllog.jsonl`，★ 已有，逐次）
```json
{"ts":"…","url":"…","base_url":"…","model":"…","kind":"text|json|embedding",
 "prompt_chars":1234,"max_tokens":3200,"attempts":2,"errors":["HTTP 429: …"],
 "ok":true,"latency":33.5,"finish_reason":"stop","usage":{…}}
```
★ **一条 = 一次逻辑调用**（重试折叠在 `attempts/errors`）⇒ ⇒ **失败必须进分母**（`ok=false` 也落盘）。

### 2.2 每个样本（`*.jsonl`，★ v7 起补）
```json
{"arm":"…","tag":"…","topic_id":"…","rep":1,"batch_id":"…","model":"MiniMax-M3",
 "seed":12345,"temperature":1.0,"max_tokens":3200,"thinking":"on|off",
 "cands":[{"cand_id":1,"gen_order":1,"decl_write":[1],"decl_drop":[],
           "decl_parsed":true,"error":null,"score_state":0.3333,"score_generic":null,
           "text_len":812,"text_sha256":"…"}],
 "scores":{"B_state_nocost":[…],"D_state_quota":[…],"F_family":{…}},
 "rank":{"B":[1,2,3],"D":[2,3,1]},              "selected":{"B":1,"D":2},
 "fulfill":{…},"violation":{…},"error":null}
```
★ `cand_id` + `gen_order` 是**并列复原的前提**（排序稳定 ⇒ 必须知道原序）。

### 2.3 顶层还要落
- **环境快照**（`env_snapshot.json`，★ 已有）：`OPENROUTER_BASE_URL` 的**原值**与**钉住后的值**、key 是否设置、代码 ref；
- **门活性报告**（`gates_report.json`）：各 Gate 的 `var / spread_range / len_corr / constant`；
- **代码指纹**：`git rev-parse HEAD` + 关键文件 sha256（⇒ 工作包一的"实际执行版本"栏）。

---

## 3. ★ 三个必须显式区分的 0（沿用三组「两种 0」+ 本轮新增第三类）

| 类型 | 含义 | v6 的实例 |
|---|---|---|
| **仪器层 0** | 判官/抽取器/打分器失败 | v4 的 9/9 全 0（提取器漏检） |
| **内容层 0** | 仪器正常，读数确实为 0 | v6 T07-3 的 `align=[0,0,0]` —— ⚠️ ★ **它其实是【第三类】** |
| ★ **不可打分 0（None）** | **打不出分**（候选无有效声明 / 状态两格皆空） | ⇒ ⇒ **不得当 0**（v5 铁律）⇒ ⇒ v6 旧实现把它转成了 0 ⇒ ⇒ **已修**（排除候选 + 显式 `n_scorable`）⇒ ⇒ ⚠️ **已落盘的 T07-3 那条仍带着旧的 0.0 ⇒ 分析时必须显式标记，不能当"内容层 0"** |

⇒ ⇒ ★ **落盘必须能区分这三类** ⇒ ⇒ v7 的 `scores` 逐候选记录里，`score_raw` 与 `decl_parsed`/`error` 缺一不可。

---

## 4. 第三方代码的边界入参必须枚举冒烟（★ 本轮新增通则）

`creativity_lab/gates/base.py::Select.__call__` 有 `if k >= n: return list(range(n))`
⇒ ⇒ **k == n 时返回原始顺序**（不是按分数排序）⇒ ⇒ 任何"用 k=n 取完整排序"的写法都会
⇒ ⇒ ⇒ **把排序改变率变成恒 0**（v6 实际发生 ⇒ ⇒ 一度被写成"建议收摊"）。

⇒ ⇒ **脚本**：`probe_select_boundary.py`（枚举 k = 0 / 1 / n−1 / n / n+1 × 三个 mode）
⇒ ⇒ **已确证**：① k≥n ⇒ 原序；② k=1 时 greedy ≡ sample。
⇒ ⇒ ★ **通则：凡引入外部 Gate/Select/解析器，一律做一次边界入参枚举冒烟，并把它固化成脚本**（不要只在脑子里知道）。
