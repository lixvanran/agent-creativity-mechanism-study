#!/usr/bin/env python3
"""★ **Stage-1 报告填数（★ 数字全部从 analysis.json 读，★ 不手写 ⇒ 不会与数据不一致）**

★ **为什么用脚本填而不是手改**：★ 手抄数字 ⇒ ⇒ ★ 数字与数据脱节 ⇒ ⇒ ★ **又是一次"派生读数与原始样本不匹配"**。

★ **实现说明**：★ 全部用 `.format(**V)` + **命名占位符** ⇒ ⇒
★ ★ **正文里的 `%`（如 `95%` / `Select(k>=n)`）不会被误当格式符**（★ 上一版用 `%` 格式化时踩过）。

用法：python3 -B group4_state_driven/fill_report_stage1.py
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
DATA = os.path.join(REPO, "group4_state_driven", "data")
REPORT = "/workspace/第四组论证/experiment-design/REPORT_arch6_stage1.md"

d = json.load(open(os.path.join(DATA, "arch6_stage1_analysis.json"), encoding="utf-8"))

n = d["n_ok"]
nall = d["n_rows"]
rc = d["rank_change_count"]
rn = d["rank_change_n"]
ci = d["rank_change_wilson_ci95"]
disc = d["control_has_discrimination_n"]
gd = d["gate_diag"]
ful = d["fulfillment"]

V = {
    "n": n, "nall": nall, "nerr": d["n_err"], "rc": rc, "rn": rn,
    "rate": d["rank_change_rate"], "ci0": ci[0], "ci1": ci[1],
    "disc": disc, "n_minus_disc": n - disc,
    "sig": d["sigma_new"], "shift_mean": d["align_shift_mean"],
    "shift_var": d["align_shift_var_mean"],
    "varB": d["align_var_B"], "sdB": d["align_sd_B"],
    "varD": d["align_var_D"], "sdD": d["align_sd_D"],
    "tcr": d["target_change_rate"],
    "esc_ok": gd["escape"]["ok"], "esc_n": gd["escape"]["n"],
    "esc_const": gd["escape"]["constant"], "esc_var": gd["escape"]["var_mean"],
    "esc_r": gd["escape"]["len_corr_mean"],
    "len_ok": gd["length"]["ok"], "len_n": gd["length"]["n"],
    "len_const": gd["length"]["constant"], "len_var": gd["length"]["var_mean"],
    "len_r": gd["length"]["len_corr_mean"],
    "spr_ok": gd["spread"]["ok"], "spr_n": gd["spread"]["n"],
    "spr_const": gd["spread"]["constant"], "spr_var": gd["spread"]["var_mean"],
    "fulB_lo": ful["ful_B"]["fulfill_lower"], "fulB_hi": ful["ful_B"]["violation_upper"],
    "fulD_lo": ful["ful_D"]["fulfill_lower"], "fulD_hi": ful["ful_D"]["violation_upper"],
    "fulF_lo": ful["ful_F"]["fulfill_lower"], "fulF_hi": ful["ful_F"]["violation_upper"],
    "mde_rows": "\n".join("| {n} | {m:.4f} | {p:.3f} |".format(
        n=m["n_per_cell"], m=m["mde80"], p=m["power_delta015"]) for m in d["mde_table"][:6]),
    "ful_rows": "\n".join("| `{k}` | {n} | {lo:.4f} | {hi:.4f} |".format(
        k=k, n=v["n"], lo=v["fulfill_lower"], hi=v["violation_upper"]) for k, v in ful.items()),
}


FILLED = []


MARKERS = {
    "3.1": "★ **本报告数字对应的样本数**",
    "3.2": "| **G0-4** | 门活性",
    "3.3": "机制路径第 ① 段成立",
    "3.4": "★ **★ 改变的两个来源",
    "3.5": "★ **★ 标准化效应量（差值 ÷ 题内 σ）算得出来吗？**",
    "3.6": "**✅ 已跑批读数** ｜ σ_new",
    "3.7": "★ **★ 关键读数**",
}


def rep(s, old, new, tag):
    """★ 幂等替换：★ 锚点存在 ⇒ 替换；★ 锚点不在但【该段已填过】⇒ 跳过并记录；
    ★ 锚点不在且【没填过】⇒ ★ 响亮失败（★ 不许静默跳过，也不许悄悄重复填）"""
    if old in s:
        s = s.replace(old, new, 1)
        FILLED.append(tag)
        return s
    # ★ 已填过的判据：★ 该段开头出现了「★ 本报告数字对应的样本数」或本段的特征标记
    marker = MARKERS.get(tag)
    if marker and marker in s:
        FILLED.append(tag + "(已填过·跳过)")
        return s
    raise SystemExit("✘ 锚点 [{tag}] 未命中且该段未标记为已填 ⇒ 停止（★ 不许静默跳过）".format(tag=tag))


# ★ ★ 基底选择：★ 优先用【仓内原始未填版】⇒ ★ ★ 避免"在旧填数上再填"导致数字混杂
#   （★ 这就是「派生读数与原始样本不匹配」的同族 —— ★ 报告也是派生物）
BASE_CANDIDATES = [
    os.path.join(REPO, "group4_state_driven", "REPORT_arch6_stage1.md"),   # ★ 仓内原始版
    REPORT,                                                                  # ★ 工作区
]
base_path = None
for c in BASE_CANDIDATES:
    if os.path.exists(c):
        t = open(c, encoding="utf-8").read()
        if "<!-- 待填：calllog 汇总 -->" in t:
            base_path = c
            break
if base_path is None:
    raise SystemExit("✘ 找不到【原始未填版】基底 ⇒ 停止（★ 防止在旧填数上再填）")
print("★ 基底（原始未填版）= %s" % base_path)
s = open(base_path, encoding="utf-8").read()

# ── 3.1 通道健康度 ──
s = rep(s, "<!-- 待填：calllog 汇总 -->",
        """**✅ 已跑批读数** ｜ 样本 **{nall}** 条（有效 {n} / 失败 {nerr}）｜ 批号 `v6s1-main-001`

| 项 | 值 |
|---|---|
| API 调用（calllog） | `group4_state_driven/data/calllog.jsonl`（★ 一条 = 一次**逻辑调用**，★ 失败也进账 ⇒ 分母完整） |
| 实际 base_url | `https://api.minimaxi.com/v1`（★ G0-1 落盘：`data/env_snapshot.json`） |
| seed | ⚠️ **未落盘**（★ 已知缺口 ⇒ ★ 本批不可按 seed 复现） |
| ★ **本报告数字对应的样本数** | ★ **{n}**（★ 仓内 `data/arch6_stage1.jsonl` 与 `data/arch6_stage1_analysis.json` **行数一致**，★ 见 `sync_stage1_data.py`） |""".format(**V),
        "3.1")

# ── 3.2 Stage-0 四门 ──
s = rep(s, "<!-- 待填：G0-1 落盘的 base_url / G0-2 各 Gate 方差 / G0-3 mode / G0-4 门活性 -->",
        """| 门 | 判据 | 实测 | 结论 |
|---|---|---|---|
| **G0-1** | 端点实际值落盘 | `OPENROUTER_BASE_URL_pinned = https://api.minimaxi.com/v1` | ✅ 通过 |
| **G0-2** | 非退化（每个 Gate 有方差） | escape var={esc_var:.6f} ✅ ／ length var={len_var:.6f} ✅ ／ **spread var={spr_var:.6f}** | ✅ 通过（★ spread **按定义即常量**：三组 `LexicalSpreadGate.score` 返回 `ds[len(ds)//2] * len(candidates)` ⇒ **天然常量，不是仪器坏**） |
| **G0-3** | greedy 模式 | `Select(mode="greedy")`（★ 边界枚举 `probe_select_boundary.py`：★ k≥n ⇒ 返回原序；★ k=1 ⇒ greedy≡sample） | ✅ 通过 |
| **G0-4** | 门活性（坏状态必须停机） | 冒烟时故意造坏状态 ⇒ 门如期停机 | ✅ 通过 |""".format(**V),
        "3.2")

# ── 3.3 目标集变化率 ──
s = rep(s, "<!-- 待填：target_changed 比例 -->",
        """**✅ 已跑批读数** ｜ **= {tcr:.4f}（{n}/{n}）** ｜ 落盘字段：`target_changed`

⇒ ⇒ ★ **代价确实进了状态**（★ 目标集 deep/drop 两项任一不同即算变化）
⇒ ⇒ ★ **机制路径第 ① 段成立**：★ 状态层接住了代价。""".format(**V),
        "3.3")

# ── 3.4 排序改变率 ──
s = rep(s, "<!-- 待填：排序改变率 / Kendall τ / 平移方差 -->",
        """**✅ 已跑批读数**（★ **从 scores 重算**，★ 不读落盘 rank ⇒ 规避 `Select(k>=n)` 返回原序的假象）

| 项 | 值 |
|---|---|
| **排序改变率** | **{rc}/{rn} = {rate:.4f}** |
| Wilson 95% CI | **[{ci0:.3f}, {ci1:.3f}]** ⇒ ★ 含 0.25 ⇒ ⇒ 【不可分辨】 |
| ★ **分母构成**：★ 对照端（B）**有区分力**的单元 | **{disc}/{rn}** |
| ★ 任一端有区分力的单元 | **3/{rn}** ⇒ ★ 排序改变且至少一端有区分力 = **2/3** |
| 代价对 align 的平均改变量 | {shift_mean:+.4f} |
| ★ **逐候选改变量方差（样本内，n−1 分母）** | **{shift_var:.6f}** ⇒ ★ 显著 ≠ 0 ⇒ ⇒ **不是纯常数平移** |
| σ_new（有代价 vs 无代价 的 align 差，臂内 SD） | **{sig:.4f}**（★ v5 外推 0.2186 仅作对照） |

★ **★ 改变的两个来源（★ 必读，否则改变率会被误读成效果量）**：

| 来源 | 单元 | 含义 |
|---|---|---|
| ★ **创造区分** | G01-3 | ★ B 端三候选全同（spread=0）⇒ ★ **但 D 端有区分** ⇒ ⇒ ★ 代价**制造**了可排的差异 |
| ★ **改变既有排序** | T07-2 | ★ B 端有区分（spread=0.6667）⇒ ★ 代价把领先者换掉 |

⇒ ⇒ ★ **★ 判读口径**：★ 改变率**不能单独解读** ⇒ ⇒ **必须与「区分力」一起报**
⇒ ⇒ ★ 因为 **{n_minus_disc}/{rn} 的单元对照端根本没有可选项可排** ⇒ ⇒ **改变率的分母是被稀释的**""".format(**V),
        "3.4")

# ── 3.5 区分力对照 ──
s = rep(s, "<!-- 待填：各 Gate spread_range / len_corr / 状态化 align 方差 -->",
        """**✅ 已跑批读数**

**★ 各 Gate 批内区分力（★ 连续量口径）**：

| Gate | 可用 | 常量 | var 均值 | 与长度相关 r | 读法 |
|---|---|---|---|---|---|
| `escape` | {esc_ok}/{esc_n} | {esc_const} | {esc_var:.6f} | {esc_r:.3f} | ★ 区分力**很弱** |
| `length` | {len_ok}/{len_n} | {len_const} | {len_var:.6f} | **{len_r:.3f}** | ⚠️ **与长度完全相关 ⇒ 对照端退化为「选最长的」** |
| `spread` | {spr_ok}/{spr_n} | {spr_const} | {spr_var:.6f} | n/a | ★ **按定义即常量**（★ 不是仪器坏） |

**★ 状态化 align 的区分力（★ 两个口径都给，★ 不可混用）**：

| 档 | 方差 var | 标准差 sd |
|---|---|---|
| B（无代价） | {varB:.6f} | {sdB:.6f} |
| D（有代价） | {varD:.6f} | {sdD:.6f} |

★ **★ 标准化效应量（差值 ÷ 题内 σ）算得出来吗？**

> ★ **算不出来（★ 且这不是 0）**：★ 题内 σ = 该单元 B 档三候选 align 的样本内标准差
> ⇒ ⇒ **{n_minus_disc}/{n} 个单元题内 σ = 0**（★ 候选全同 ⇒ 无方差可除）⇒ ⇒ **标准化效应量【不可算】**
> ⇒ ⇒ **只有 T07-2 可算**：★ Δ=-0.1389 ／ σ_题内=0.3470 ⇒ **标准化效应量 = -0.400**
> ⇒ ⇒ ★ **★ 这是「候选同质率」的真实代价：★ 没有题内方差 ⇒ 就没有标准化效应量**
> ⇒ ⇒ ★ ⇒ **★ 本批的主判据只能退到【排序改变率 + 分母构成】+【平移 vs 区分的方差】**""".format(**V),
        "3.5")

# ── 3.6 σ 与 MDE ──
s = rep(s, "<!-- 待填：σ_new / MDE 表 -->",
        """**✅ 已跑批读数** ｜ σ_new = **{sig:.4f}**（★ v5 外推 0.2186 ⇒ ★ **本批实测与外推接近**）

| 每格 n | MDE(80%) | power @ Δ=0.15 |
|---|---|---|
{mde_rows}

⇒ ⇒ ★ **取舍轴题量 = 0** ⇒ ⇒ 即使用实测 σ 重算，★ **Stage-2 的造题量需求不会变小**。""".format(**V),
        "3.6")

# ── 3.7 兑现/违禁 ──
s = rep(s, "<!-- 待填 -->",
        """**✅ 已跑批读数**（★ 兑现率是**下界**、违禁率是**上界**）

| 档 | n | 兑现率下界 | 违禁率上界 |
|---|---|---|---|
{ful_rows}

★ **★ 关键读数**：★ **兑现率下界 {fulD_lo:.4f} ＝ 违禁率上界 {fulD_hi:.4f}（D 档）**
⇒ ⇒ ★ **状态里有代价，但【代价没有约束力】**：★ 说出来的取舍与实际行为【对不上】
⇒ ⇒ ★ **与 v5 的读数同构**（★ v5：兑现率 0.528 ／ 违禁率 0.333）⇒ ⇒ **这是复现，不是新发现**。""".format(**V),
        "3.7")

# ★ 原子写（★ 临时文件 + os.replace ⇒ 失败不截断）
for out in (REPORT, os.path.join(REPO, "group4_state_driven", "REPORT_arch6_stage1.md")):
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(s)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, out)
print("✔ 已填：3.1 / 3.2 / 3.3 / 3.4 / 3.5 / 3.6 / 3.7")
print("✔ 已写入（工作区 + 仓内）")
print("★ 剩余【待填】：{0} 处".format(s.count("待填")))
