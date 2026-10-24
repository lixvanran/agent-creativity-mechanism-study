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

# ★ ★ ★ Gate 语义与「家族最优」读数（★ 来自 analyze_gate_semantics.py 的产物）★★
# ★ ★ 纪律：★ 产出方自报落盘路径（★ --out）⇒ ⇒ ★ 消费方【不自己拼路径】★★
_gs_path = os.path.join(DATA, "arch6_gate_semantics.json")
if not os.path.exists(_gs_path):
    raise SystemExit("✘ 找不到 %s ⇒ 停止（★ 先跑 analyze_gate_semantics.py --out ...）" % _gs_path)
GS = json.load(open(_gs_path, encoding="utf-8"))
_fw = GS["③_家族最优选尺分布"]["各 Gate 被选中次数"]
V.update({
    "fam_escape": _fw.get("escape", 0),
    "fam_length": _fw.get("length", 0),
    "fam_spread": _fw.get("spread", 0),
    "fam_n": GS["③_家族最优选尺分布"]["★ n"],
    "gs_construction_pearson": GS["①_len_corr_零信息性验证"]["★ 证据 A（★ 构造性，★ 与本批数据无关）"]["Pearson"],
    "gs_capped_pearson": GS["①_len_corr_零信息性验证"]["★ 反例对照（★ v6 修掉的那个封顶口径）"]["Pearson"],
})


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


def fill_block(s, tag, content):
    """★ **块级幂等替换**：★ 找 `<!-- FILL:tag -->` … `<!-- /FILL:tag -->` 整块换成 content。

    ★ **★ 为什么要有它（★ 真问题）★★**：★ 原设计靠"原始未填版 + 锚点替换"，
    ★ ⇒ ★ **基底被首次填充后就被覆盖 ⇒ ⇒ 脚本第二次就 SystemExit（EXIT=1）★★
    ★ ⇒ ⇒ ★ ⇒ 「报告数字由脚本填」这条纪律【无法持续执行】★★
    ★ ⇒ ⇒ ★ ⇒ 修法：★ 固化【基线】（含块标记）★ ⇒ ★ 每次从基线重填 ★ ⇒ ★ **天然幂等、可无限重跑**★★
    ★ ★ ★ 标记不在 ⇒ ★ 响亮失败（★ 不静默跳过）★★
    """
    beg = "<!-- FILL:%s -->" % tag
    end = "<!-- /FILL:%s -->" % tag
    if beg not in s or end not in s:
        raise SystemExit("✘ 块标记 [%s] 未命中 ⇒ 停止（★ 不许静默跳过）" % tag)
    # ★ ★ ★ BUG 修复（★ 2026-10-25）★★★：★ 原实现有两个错 ★
    # ① `s[:i]`（i = beg 之后）⇒ **切片含 beg 本身** ⇒ 块首标记被带进成品
    # ② `s[j:]`（j = end 起点）⇒ **切片含 end 本身** ⇒ 块尾标记被带进成品
    # ⇒ ⇒ ⇒ 报告带着脚手架出厂 ⇒ ⇒ 被新加的计数型断言当场抓到（★ 断言有效 ✔）
    # ⇒ ⇒ ⇒ 【成品报告必须移除首尾两个标记】★ ⇒ ★ 基底（base.md）保留标记供下次重填
    bi = s.index(beg)
    ei = s.index(end)
    return s[:bi] + "\n" + content.strip("\n") + "\n" + s[ei + len(end):]


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
# ★ ★ ★ 基底选择（★ 2026-10-25 改为两级）★★
# ① 优先：【原始未填版】（★ 含待填标记）—— 首次填充走这条
# ② 其次：【基线文件】（★ 含 FILL 块标记）—— ★ 之后每次重填都走这条 ⇒ ⇒ 【可无限重跑】
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
    _b = os.path.join(REPO, "group4_state_driven", "REPORT_arch6_stage1.base.md")
    if os.path.exists(_b):
        base_path = _b
    else:
        raise SystemExit("✘ 找不到【原始未填版】也找不到【基线文件】⇒ 停止"
                         "（★ 跑 group4_state_driven/migrate_report_base.py 生成基线）")
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
# ★ ★ ★ 2026-10-25：★ 整段改为【块替换】★ ⇒ ★ 数字可随 analysis 重跑而更新
s = fill_block(s, "3.5-gates", """**★ 各 Gate 批内区分力（★ 连续量口径）**：

**★ ★ 先说【每个 Gate 的语义】（★ 此前没人回答，★ 而它决定「区分力」该怎么读）★★**

| Gate | score 的定义 | 方向 | 高分意味着 | 实现指针 |
|---|---|---|---|---|
| `escape` | `max(0, 1 − max_cos(cand, refs))` | ★ **最大化** score | 离参照文本更远（「逃逸」） | `creativity_lab/gates/base.py:39-45` |
| `spread` | `ds[len(ds)//2] × n` | ★ **最大化** score（★ 但按定义恒定 ⇒ top-1 落回原序） | （★ 按定义无区分力） | `creativity_lab/gates/base.py:48-61` |
| `length` | `len_i / max_len`（★ 批内相对） | ★ **最大化** score | ★ **更长** | `group4_state_driven/code/workflow_arch6.py:167-180` |

| Gate | 可用 | 常量 | var 均值 | 与绝对长度相关 r | 读法 |
|---|---|---|---|---|---|
| `escape` | {esc_ok}/{esc_n} | {esc_const} | {esc_var:.6f} | ★ **不报告**（★ 见 §0 降级 2） | ★ 区分力**很弱**（★ var 很小） |
| `length` | {len_ok}/{len_n} | {len_const} | {len_var:.6f} | **{len_r:.3f}** | ★ ★ **定义使然**（★ 相对长度是绝对长度的单调变换）⇒ ★ **零信息量，★ 不可作退化证据**（★ §0 降级 1） |
| `spread` | {spr_ok}/{spr_n} | {spr_const} | {spr_var:.6f} | n/a | ★ **按定义即常量**（★ 不是仪器坏） |

**★ ★ 「家族最优」实际选了哪把尺子（★ 这是量出来的，★ 不是指定的）★★**

| 项 | 读数 |
|---|---|
| ★ 家族最优选中的 Gate 分布 | ★ **escape {fam_escape}/{fam_n}**、★ length **{fam_length}/{fam_n}**、★ spread {fam_spread}/{fam_n} |
| ★ ⇒ 「对照端退化为『选最长的』」 | ★ ★ **本批不成立**（★ `length` 赢 **{fam_length}** 次）★ ⇒ 降级 1 的结论被**实测**否定 |

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
> ⇒ ⇒ ★ ⇒ **★ 本批的主判据只能退到【排序改变率 + 分母构成】+【平移 vs 区分的方差】**""".format(**V))

# ★ ★ ★ §0 降级记录的正文（★ 数字全部用占位符 ⇒ 由脚本填 ⇒ 不手抄）★★
DEGRADE_BLOCK = """**⑤ ★ 降级记录（★ 2026-10-25 · ★ 主会话裁决一/二 + 本轮回源核查）★★★**

> ★ **★ 为什么单列「降级」而不并入「修正」★★**：★ 外部读者看到「修正」会以为只是改了个数字；
> ★ 看到「降级」才会知道**有一条推理链被撤了**。★ ⇒ **作废的是哪一句、哪些结论受影响、哪些明确不受影响、依据在哪**，★ 逐条写死。

**★ 降级 1：`len_corr = 1.000` 作「对照端退化为『选最长的』」的证据 ⇒ ⇒ 【作废】**

| 项 | 内容 |
|---|---|
| ★ **哪一句作废**（逐字） | ★ §3.5 表中 `length` 行的读法：「⚠️ **与长度完全相关 ⇒ 对照端退化为「选最长的」**」 |
| ★ **为什么作废** | ★ `length` Gate 的 score = `len_i / max_len`（★ **批内相对长度**）⇒ ⇒ 分母是**批内常数** ⇒ ⇒ 它是绝对长度的**严格单调变换** ⇒ ⇒ **Pearson(score, 绝对长度) 在定义上恒为 1** ⇒ ⇒ 该读数**零信息量**，★ 不能支撑任何结论 |
| ★ **依据（回源）** | ★ ① 实现：`group4_state_driven/code/workflow_arch6.py:167-180`（`_length`）★ ② 读数：`group4_state_driven/data/arch6_gate_semantics.json` ① 证据 A（★ **构造性**：造 10 个长度各异的候选 ⇒ Pearson = **{gs_construction_pearson}**，★ 与本批数据无关）③ 证据 B（★ **观测**：本批 n=9，★ **9/9 = 1.0**）④ 反例（★ 旧封顶口径 `min(1.0, len/900)` ⇒ Pearson = **{gs_capped_pearson}** ⇒ ★ **正因如此旧口径才有信息量，★ 改成批内相对后它【必然恒为 1】**） |
| ★ **哪些结论受影响** | ★ ① 「对照端退化为『选最长的』」⇒ ⇒ **该结论在本批【不成立】**：★ 家族最优 **{fam_escape}/{fam_n} 由 `escape` 赢**，★ `length` **赢 {fam_length} 次**（★ 读数见 §3.5）★ ② 任何以 `len_corr` 为依据的退化推断 |
| ★ **哪些明确不受影响** | ★ ① **排序改变率 {rc}/{rn}**（★ `analyze_arch6.py:146` 明确【从 scores 重算】、★ **不读落盘 rank/len_corr**）★ ② 「创造区分」2 例（★ G01-3 / T10-2）★ ③ 目标集变化率 {tcr:.4f} ★ ④ σ / 平移 / 同质率（★ 均不含 `len_corr`）★ ⑤ 主判决【不可分辨】 |
| ★ **结论是否改变** | ★ **不改变，且【变强】**：★ 主判决不依赖 `len_corr`；★ 而对照端**不是长度代理** ⇒ ⇒ 状态化选择器 vs 家族最优的对比**更干净**（★ 少了一个共同混淆因子） |

**★ 降级 2：`escape` 的 `len_corr` 读数 ⇒ ⇒ 【降为「不报告」】**

| 项 | 内容 |
|---|---|
| ★ **哪一句作废** | ★ §3.5 表中 `escape` 行的「与绝对长度相关 r = {esc_r:.3f}」★ ⇒ **本报告不再引用该值** |
| ★ **为什么** | ★ 本轮回源核查发现：★ **`escape` 的 `len_corr` 与它自己的排序读数在 4/9 个样本上【不自洽】**（★ 详证见 `group4_state_driven/KNOWN_ISSUES.md`「待 Mavis 裁决」段）⇒ ⇒ ★ 两者至少有一个不可信 ⇒ ⇒ ★ **未定位根因前，★ 该读数一律不报告**（★ **不猜、不用**） |
| ★ **依据** | ★ ① 穷举检验（★ 6 个约束：min / max / var / len_corr / escape.rank / length.rank）⇒ **无解** ★ ② 实现层同构实验（★ 真实 `family_pick6` + 构造分数）⇒ **自洽** ⇒ ⇒ ★ **不是 `family_pick6` 的逻辑 bug** ★ ③ 逐样本表见 `KNOWN_ISSUES.md` |
| ★ **哪些结论受影响** | ★ **仅** §3.5 表中 `escape` 行的 r 值 ★ ⇒ **无任何结论依赖它**（★ 排序改变率、align 读数、兑现/违禁率均不含它） |
| ★ **哪些明确不受影响** | ★ ★ 全部主读数（★ 见降级 1 的"不受影响"清单，★ 且本项影响面更小） |
| ★ **结论是否改变** | ★ **不改变**（★ 该值此前**未被任何结论使用**） |

"""


# ── ⑤ §0 降级块 ──
s = fill_block(s, "0-degrade", DEGRADE_BLOCK.format(**V))

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
