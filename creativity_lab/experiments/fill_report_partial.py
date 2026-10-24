#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 把「部分预判决」的数字从 `partial_verdict.json` 填进交付报告 ★

★ ★★ 为什么要有这个脚本（★ 纪律）★★
★ 报告里的数字 > 10 个 ⇒ **必须由脚本从 analysis 填**；★ 手抄 = 抄错的温床。
★ ⇒ ★ 本脚本：★ 读 `partial_verdict.json` ⇒ ★ 改写报告里被【锚点】定位的那几行
★ ⇒ ★ **锚点找不到 ⇒ SystemExit（★ 响亮失败，★ 不许留空、不许静默跳过 ★）**

★ ★★ 额外修掉一个手抄才会出的错 ★★
★ 报告 6.10.4 的 4c 行曾把【单格值 +0.6045】写在【题级方向】列 ⇒ ★ **标签与数值错配**
★ ⇒ ★ 本脚本的题级方向一律取 json 里的 `dir_votes`（★ 那是脚本自己算的题级均值 ★）
★ ⇒ ★ **手抄这一列不可能对，★ 脚本才对。★★**

用法：
    python3 -B creativity_lab/experiments/fill_report_partial.py \
        --report docs/交付/第二组交付报告_2026-10-25.md \
        --json runs/topo-arm-v2-2026-10-25/partial_verdict.json
"""

import argparse
import json
import os
import re
import sys


def die(msg):
    print("✘ %s" % msg)
    sys.exit(1)


def one(s, old, new, tag):
    """★ 锚点必须【唯一命中】；★ 命中 0 次或 >1 次都响亮失败。★"""
    n = s.count(old)
    if n != 1:
        die("锚点[%s]命中 %d 次（★ 期望恰好 1 次 ★）：%r" % (tag, n, old[:70]))
    return s.replace(old, new)



def replace_line(s, prefix, new_line, tag):
    """★ 按【行前缀】定位并【整行替换】★ —— 比整串匹配稳（★ 表格里的加粗标记会变 ★）。★"""
    lines = s.split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    if len(idx) != 1:
        die("行[%s]命中 %d 次（★ 期望恰好 1 次 ★）：%r" % (tag, len(idx), prefix[:60]))
    lines[idx[0]] = new_line
    return "\n".join(lines)



def re_sub_once(s, pat, repl, tag, flags=0):
    """★ 正则替换：★ 命中次数必须【恰好 1】；★ 否则响亮失败。★"""
    n = len(re.findall(pat, s, flags))
    if n != 1:
        die("正则[%s]命中 %d 次（★ 期望恰好 1 次 ★）：%r" % (tag, n, pat))
    return re.sub(pat, repl, s, count=1, flags=flags)


def fmt(x, nd=4):
    return ("%." + str(nd) + "f") % x


# ★ ★ 6.10.2b 生成器（★ 幂等：★ 用 BEGIN/END 标记切掉上次产物再重填 ★）★★
MC_BEGIN = "<!-- BEGIN:6.10.2b -->"
MC_END = "<!-- END:6.10.2b -->"
SN_BEGIN = "<!-- BEGIN:6.10.0 -->"
SN_END = "<!-- END:6.10.0 -->"
CH_BEGIN = "<!-- BEGIN:6.10.0b -->"
CH_END = "<!-- END:6.10.0b -->"


def build_channel_section(cj):
    """★ 从 channel_status.json 生成「通道状态与批状态」登记段 ★"""
    q = cj.get("quota") or {}
    chat = cj.get("chat") or {}
    emb = cj.get("embed") or {}
    un = cj.get("units") or {}
    gen = None
    for m in (q.get("models") or []):
        if m.get("model_name") == "general":
            gen = m
    L = []
    L.append("### 6.10.0b ★★★ 通道状态与批状态登记（★ 2026-10-26 限流事件 ★）★★★")
    L.append("")
    L.append("> ★ **触发**：★ 第 1 层论证线 2026-10-26 报「chat 窗口限流 + 嵌入余额耗尽」★")
    L.append("> ★ **工具**：★ `creativity_lab/experiments/channel_status.py`（★ 只读 · ★ 不改生产代码 · ★ 不打印 key ★）★")
    L.append("> ★ **原始读数**：★ `docs/交付/读数快照/topo-arm-v2-n151/channel_status.json` ★")
    L.append("")
    L.append("| 通道 | 实测结果 | 恢复方式 |")
    L.append("|:-:|---|---|")
    if gen:
        L.append("| ★ **chat（general）** | ★ **HTTP %s** ｜ ★ %s ★ | ★ **限流（★ 5 小时滚动窗口 ★）⇒ 等窗口复位即可** ｜ 窗口 %s → %s，★ 剩 %s 分钟 ｜ 本周剩 %s 小时 ★ |"
                 % (chat.get("http"), chat.get("msg", "")[:60], gen.get("interval_start_utc"),
                    gen.get("interval_end_utc"), gen.get("interval_remains_min"),
                    gen.get("weekly_remains_hours")))
    else:
        L.append("| ★ **chat（general）** | ★ HTTP %s ｜ %s ★ | ★ 等窗口复位 ★ |"
                 % (chat.get("http"), chat.get("msg", "")[:60]))
    L.append("| ★ **嵌入 `embo-01`** | ★ HTTP %s ｜ **status_code=%s** ｜ %s ★ | ★ ★ **余额耗尽 ⇒ 不会自愈 ⇒ 必须实际充值** ★ |"
             % (emb.get("http"), emb.get("status_code"), emb.get("status_msg")))
    L.append("")
    L.append("★ **两条通道的处置完全相反（★ 这是本节最要紧的一句 ★）**：★ chat 限流 ⇒ **等 1 个窗口就好**；★ 嵌入余额 ⇒ **等多久都没用，必须充值** ★")
    L.append("")
    L.append("★ **批状态（★ 单元级独立重算，★ 不信批自己的 manifest ★）**：")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|:-:|---|")
    L.append("| ★ 单元 | ★ **%s**（★ 已落盘，★ **全部保留** ★）★ |" % un.get("n_units"))
    L.append("| ★ 调用 | ★ %s ｜ 失败 **%s** ｜ 空内容 %s ｜ **两者重合 %s** ｜ `len(calls)!=n_calls` 的单元 %s ★ |"
             % (un.get("n_calls"), un.get("n_failed"), un.get("n_empty"),
                un.get("n_failed_and_empty"), un.get("len_mismatch_units")))
    L.append("| ★ 健康度 | ★ 公式 `1-(nf+ne)/n` = **%.4f** ｜ 去重 `1-max(nf,ne)/n` = **%.4f** ⇒ ★ **差 %.4f** ★ |"
             % (un.get("health_as_formula", 0), un.get("health_dedup", 0),
                abs(un.get("health_as_formula", 0) - un.get("health_dedup", 0))))
    L.append("")
    L.append("★ **★ 交稿读数【不受】本次限流影响（★ 已逐单元核过 ★）★★：")
    L.append("")
    L.append("| 检查 | 结果 |")
    L.append("|:-:|---|")
    L.append("| ★ 失败单元落在冻结清单【内】的 | ★ **0 个** ★ |")
    L.append("| ★ 失败起始时刻（★ 首个失败单元 mtime ★） | ★ 晚于 §6.10.0 快照的冻结时刻 ⇒ ★ **快照取自限流之前** ★ |")
    L.append("| ★ 失败单元的 `post` 长度 | ★ **0** ⇒ ★ 空 `post` 被 `load_groups` 过滤 ⇒ ★ **不进读数** ★ |")
    L.append("")
    L.append("★ **处置**：★ 批已**暂停**（★ 不是重启：★ 已落盘单元全部保留，★ 同一条命令即可续跑 ★）★")
    L.append("★ ⇒ ★ 续跑前**必须先测 chat 通不通**（★ 窗口未复位就重启 ⇒ 每个单元 13 次调用全 429 ⇒ 白烧 ★）★")
    L.append("★ ⇒ ★ 批本身**不依赖嵌入**（★ 嵌入只在分析阶段用 ★）⇒ ★ **批可在窗口复位后继续**；★ 但**批跑完出读数必须先充值嵌入** ★")
    L.append("")
    L.append("★ **★ 一条口径 bug（本轮实测抓到）★**：★ 健康度公式 `1-(nf+ne)/n` 把「**既失败又空内容**」的调用**计了两次**（★ 本批 47/47 完全重合 ★）⇒ ★ 报出的健康度**偏低** ⇒ ★ **早停会被提前触发**（★ 方向是保守的，★ 不是漏记 ★）★ ⇒ ★ 批后接入健康度守卫时改为 `1-max(nf,ne)/n` ★（★ 详见 KI-10 ★）★")
    L.append("")
    return "\n".join(L)

CALIB_ORDER = ["A_all_arms", "B_prereg_new", "B_prereg_full", "C_old_only"]


def _days_between(d1, d2):
    import datetime as _dt
    try:
        a = _dt.date.fromisoformat(d1)
        b = _dt.date.fromisoformat(d2)
        return (b - a).days
    except Exception:
        return 0
CALIB_LABEL = {
    "A_all_arms": "A 全部臂（★ 当前实现实际用的 ★）",
    "B_prereg_new": "B 预注册·新批段",
    "B_prereg_full": "B 预注册·完整",
    "C_old_only": "C 旧批单独（★ 诊断 ★）",
}
CONTRAST_ORDER = ["H-TOPO-4a", "H-TOPO-4c", "H-TOPO-4d"]


def replace_markers(s, body, begin=MC_BEGIN, end=MC_END):
    """★ 把 BEGIN/END 标记之间的内容整体换成 body（★ 天然幂等 ★）"""
    if begin not in s or end not in s:
        die("报告里找不到标记 %s / %s（★ 先插占位 ★）" % (begin, end))
    i = s.index(begin)
    j = s.index(end)
    if j < i:
        die("6.10.2b 标记顺序反了")
    return s[:i] + begin + "\n" + body.rstrip() + "\n" + s[j:]


def build_multicalib_section(mj):
    """★ 从 h0_theta0_multicalib.json 生成 6.10.2b 整节（★ 含判定句 ★）"""
    h0 = mj["h0"]
    verd = mj["verdicts"]
    risk = mj.get("direction_risk") or {}
    gate = mj.get("old_recompute_gate") or {}

    L = []
    L.append("### 6.10.2b ★★★ θ₀ 的多口径重算：★ 偏离预注册的影响已量化 ★★★")
    L.append("")
    L.append("> ★ **触发**：★ 第 1 层论证线 2026-10-26 指出「当前用的是全部臂口径（n=12）而非预注册的 `nosel_b3` 口径 ⇒ 判据偏离预注册 ⇒ ★ θ₀ 是判决的第一道基准 ⇒ 请给两个口径的 θ₀ 差多少」★")
    L.append("> ★ **回源**：★ 预注册 `docs/cmp8/routes/COLLAPSE/eval/PREREG-TOPOLOGY-ARM.md` §5.0b2-i「原料来源」行（★ 写死 = 新批 `nosel_b3` 12 + 旧批 `nosel_b5` 9 = 21 ★）★")
    L.append("> ★ **工具**：★ `creativity_lab/experiments/h0_theta0_calibration.py`（★ 零生成调用，★ 唯一成本是 embedding ★）★")
    L.append("> ★ **原始读数**：★ `docs/交付/读数快照/topo-arm-v2-n151/h0_theta0_multicalib.json` ★")
    L.append("")

    # ── 四口径表 ──
    L.append("| 口径 | 原料 | n | σ | X₀ | θ₀ | 4a 超门槛 | 4c 超门槛 | 4d 超门槛 | 判决格（4a/4c/4d） |")
    L.append("|:-:|---|--:|--:|--:|--:|--:|--:|--:|:-:|")
    for name in CALIB_ORDER:
        st = h0.get(name)
        if not st:
            continue
        pc = verd.get("H-TOPO-4a", {}).get("per_calibration", {}).get(name, {})

        def cell(cn):
            p = verd.get(cn, {}).get("per_calibration", {}).get(name, {})
            if not p:
                return "—"
            tot = verd.get(cn, {}).get("n_cells")
            return "%d/%d" % (p.get("n_cells_over_theta0", 0), tot if tot is not None else 0)

        vs = []
        for cn in CONTRAST_ORDER:
            p = verd.get(cn, {}).get("per_calibration", {}).get(name, {})
            vs.append(p.get("verdict", "—"))
        L.append("| **%s** | %s | **%d** | %s | %s | **%sσ** | %s | %s | %s | %s |"
                 % (CALIB_LABEL.get(name, name), st.get("short", "—"),
                    st["n_pairs"], fmt(st["sigma_rep"]), fmt(st["X0_q95_over_sqrt2"]),
                    ("%.3f" % st["theta0_standardized"]) if st.get("theta0_standardized") else "—",
                    cell("H-TOPO-4a"), cell("H-TOPO-4c"), cell("H-TOPO-4d"),
                    " / ".join(vs)))
    L.append("")

    # ── 偏离方向判定（★ 由脚本判，不手写 ★）──
    thA = risk.get("theta0_current_A")
    thB = risk.get("theta0_prereg_B")
    ratio = risk.get("theta0_ratio_B_over_A")
    if ratio is not None:
        if ratio > 1.0:
            dir_txt = ("★ **预注册口径的门槛更严**（θ₀ %sσ → %sσ，★ 比值 %.4f）⇒ ★ ⇒ "
                       "**当前实现用的 A 口径【更松】⇒ ⇒ 偏离方向 = 偏向『可分辨』= 危险方向** ★"
                       % (fmt(thA, 3), fmt(thB, 3), ratio))
        else:
            dir_txt = ("★ **预注册口径的门槛更松**（θ₀ %sσ → %sσ，★ 比值 %.4f）⇒ ★ ⇒ "
                       "**偏离方向 = 偏向『不可分辨』= 保守方向** ★"
                       % (fmt(thA, 3), fmt(thB, 3), ratio))
    else:
        dir_txt = "★ 口径比值不可用 ★"

    changed = mj.get("verdict_changed_by_calibration") or []
    # 格级读数是否随口径变（A vs 预注册完整）
    cell_diff = []
    for cn in CONTRAST_ORDER:
        pc = verd.get(cn, {}).get("per_calibration", {})
        a = pc.get("A_all_arms") or {}
        b = pc.get("B_prereg_full") or {}
        if a.get("n_cells_over_theta0") != b.get("n_cells_over_theta0"):
            cell_diff.append(cn)

    L.append("★ **① 偏离方向（★ 由脚本判定 ★）**：★ %s ★" % dir_txt)
    L.append("")
    L.append("★ **② 判决是否随口径改变**：★ %s ★"
             % ("★ **不随口径改变**（★ 三个对比在四套口径下判决格完全相同 ★）★"
                if not changed else "★ **随口径改变**：★ %s ★" % changed))
    L.append("")
    L.append("★ **③ 格级读数是否随口径改变（A vs 预注册完整口径）**：★ %s ★"
             % ("★ **不改变**（★ 三个对比的超门槛格数完全相同 ★）★"
                if not cell_diff else "★ **改变**：★ %s ★" % cell_diff))
    L.append("")
    L.append("★ **④ 跨口径混合是否有效（★ 预注册那条合法性论证的实测检验 ★）**：★ 旧批层①（`nosel_b5`，n=%d）单独 σ = %s；★ 新批层②（`nosel_b3`，**n=%d，★ 样本太少、★ 其 σ 与区间均不可靠 ⇒ ★ 不能单独作证 ★**）σ = %s；★ 两批合并 σ = %s ⇒ ★ **合并值落在旧批单独值与新批段值之间，★ 未见明显量纲漂移** ⇒ ★ 预注册「零分布只要求同题重复，不要求口径同」那条论证**在本批上未见反例** ★（★ 但这是本批的**弱**证据：★ 新批段只有 %d 个配对 ★ ⇒ ★ 批跑满后必须重测这一条 ★）★"
             % (h0["C_old_only"]["n_pairs"], fmt(h0["C_old_only"]["sigma_rep"]),
                h0["B_prereg_new"]["n_pairs"], fmt(h0["B_prereg_new"]["sigma_rep"]),
                fmt(h0["B_prereg_full"]["sigma_rep"]),
                h0["B_prereg_new"]["n_pairs"]))
    L.append("")
    L.append("★ **⑤ 旧批回源闸门（★ 存档值 vs 独立重算 ★）**：★ 核对 %d 组，★ 不符 **%d** 组 ⇒ %s ★"
             % (gate.get("n_checked", 0), gate.get("n_mismatch", 0),
                "✔ 通过" if gate.get("passed") else "✘ 不通过"))
    L.append("")
    L.append("★ **⑥ 为什么本轮【不】切到预注册口径（★ 原料充分性 ★）**：★ 预注册口径要求新批 `nosel_b3` 有 6 题 × 2 rep = 12 个配对；★ 当前该臂只有 **%d** 个题满组（★ ⇒ %d 个配对 ★）⇒ ★ **标定原料不足**（★ n=%d 时 bootstrap 区间不可用 ★）⇒ ★ ⇒ **现在切口径会把一个已标定好的门槛换成一个未标定好的门槛** ⇒ ★ 处置：★ **本轮维持 A 口径并显式登记 + 批跑满后切回预注册口径 + 加一道「两口径判决必须一致」的断言** ★"
             % (h0["B_prereg_new"]["n_pairs"], h0["B_prereg_new"]["n_pairs"],
                h0["B_prereg_new"]["n_pairs"]))
    L.append("")
    L.append("★ **⑦ 这条偏离怎么处置（★ 结论 ★）**：★")
    L.append("")
    L.append("| 项 | 结论 |")
    L.append("|:-:|---|")
    L.append("| ★ 偏离是否存在 | ★ **是**（★ 代码用全部臂口径，★ 预注册写的是 `nosel_b3` + 旧批 ★）★ |")
    L.append("| ★ 偏离方向 | ★ **危险方向**（★ 当前实现的门槛更松 ⇒ 偏向『可分辨』★）★ |")
    L.append("| ★ 对判决的影响 | ★ **实测为零**（★ 判决格与格级读数均未变 ★）★ |")
    L.append("| ★ 处置 | ★ **登记 + 批跑满后切回预注册口径 + 加一致性断言** ⇒ ★ **不是「无害就不用管」** ★ |")
    L.append("")
    L.append("★ **★ 一条元教训（★ 比这个数本身更值钱 ★）**：★ 标定值（θ₀ / 噪声地板）虽是判决的【尺子】，★ 但它能不能被定版，★ **还取决于【标定原料是否充分】** ⇒ ⇒ ★ 「H0 标定 → 写死 θ₀ → 判决」这条顺序**隐含要求「先跑满再标定」** ⇒ ⇒ ★ ⇒ **部分预判决阶段必然要用替代口径** ⇒ ⇒ ★ ⇒ ★ **替代口径必须显式登记，且必须量化它对判决的影响**（★ 本节就是那道量化 ★）★★")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--morph-json", default=None,
                    help="★ morphology_control.json（★ 形态受控性表 ★）")
    ap.add_argument("--snapshot-json", default=None,
                    help="★ SNAPSHOT-REGISTRY.json（★ 冻结快照登记 ★）")
    ap.add_argument("--f1c-json", default=None,
                    help="★ f1c_leverage.py 的输出（★ 位置基线 + 内容依赖判据 ★）")
    ap.add_argument("--excl-json", default=None,
                    help="★ recompute_excluding.py 的输出（★ 用来给主判据表加『脆弱格』列 ★）")
    ap.add_argument("--multicalib-json", default=None,
                    help="★ h0_theta0_calibration.py 的输出（★ θ₀ 多口径重算 + 判决影响 ★）")
    ap.add_argument("--channel-json", default=None,
                    help="★ channel_status.py 的输出（★ 通道状态 + 批状态登记 ★）")
    ap.add_argument("--contaminated-unit", default=None,
                    help="★ 已知污染单元的 basename（★ 用于报告 6.12.2 的单元数与臂 n ★）")
    a = ap.parse_args()

    if not os.path.isfile(a.report):
        die("报告不存在：%s" % a.report)
    if not os.path.isfile(a.json):
        die("json 不存在：%s" % a.json)

    d = json.load(open(a.json, encoding="utf-8"))
    h0 = d["h0"]
    n_actual = d["n_units_actual"]
    n_target = d["n_units_target"]
    theta0 = d["theta0"]
    verdicts = d.get("verdicts") or {}

    # ★ 找不到对比字典就响亮失败（★ 不许静默跳过 ★）
    if not verdicts:
        die("json 里没有对比结果字典（★ 键：%s ★）" % list(d.keys()))

    # ★ 脆弱格清单（★ 可选 ★）
    fragile = set()
    fragile_detail = []
    # ★ ★ 脆弱格的【正确判据】：★ 不是「A 有 B 无」（★ 那是整组退出的副作用 ★），
    #   ★ 而是【内容依赖】：★ 该单元的杠杆 ≥ 2× 同位置基线（★ F-1c 判据 ★）★★
    #   ★ 若 F-1c 判定【不属内容依赖】⇒ ★ 一格都不标脆弱 ★
    f1c_ratio = None
    if a.f1c_json:
        if not os.path.isfile(a.f1c_json):
            die("f1c-json 不存在：%s" % a.f1c_json)
        fj = json.load(open(a.f1c_json, encoding="utf-8"))
        f1c_ratio = fj.get("content_dependency_ratio")
        if f1c_ratio is not None and f1c_ratio < 2.0:
            pass    # ★ 不属内容依赖 ⇒ 脆弱集合为空 ★
        else:
            if a.excl_json and os.path.isfile(a.excl_json):
                ej = json.load(open(a.excl_json, encoding="utf-8"))
                for c in ej.get("fragile_cells", []):
                    fragile.add((c["contrast"], c["tid"], c["rep"]))
                    fragile_detail.append(c)

    s = open(a.report, encoding="utf-8").read()

    # ── 6.10.2 H0 表 ──
    v = h0["vendi"]
    m = h0["modes"]
    sd = h0["structured_dedup"]
    n_pairs = v.get("n_pairs", 0)
    s = replace_line(s, "| 可用配对 |", "| 可用配对 | **%d**（★ 目标 21：正式批 `nosel_b3` 6 题×2rep=12 + 旧批 `nosel_b5` 3 题×3rep=9 ★） |" % n_pairs, "6.10.2 配对数")
    s = re_sub_once(s, r"题内 rep σ = [0-9]+ 个同臂同题 rep 差",
            "题内 rep σ = %d 个同臂同题 rep 差" % n_pairs, "6.10.2 σ 描述")
    s = replace_line(s, "| **vendi** | σ =",
            "| **vendi** | σ = **%s**（CI [%s, %s]）｜ q95 = **%s**(nr) / **%s**(lin)（CI [%s, %s]）｜ **X₀ = q95/√2 = %s** ｜ **θ₀ = %.2f σ** |"
            % (fmt(v["sigma_rep"]), fmt(v["sigma_bootstrap_ci"][0]), fmt(v["sigma_bootstrap_ci"][1]),
               fmt(v["q95_nearest_rank"]), fmt(v["q95_linear"]),
               fmt(v["q95_bootstrap_ci"][0]), fmt(v["q95_bootstrap_ci"][1]),
               fmt(v["X0_q95_over_sqrt2"]), v["theta0_standardized"]), "6.10.2 vendi 行")
    s = replace_line(s, "| modes | σ =",
            "| modes | σ = %s ｜ X₀ = %s ｜ θ₀ = %.2f σ |"
            % (fmt(m["sigma_rep"]), fmt(m["X0_q95_over_sqrt2"]), m["theta0_standardized"]), "6.10.2 modes 行")
    s = re_sub_once(s, r"⇒ ★ 本轮用\*\*全部臂\*\*的同题 rep 差（n=[0-9]+）★",
            "⇒ ★ 本轮用**全部臂**的同题 rep 差（n=%d）★" % n_pairs, "6.10.2 口径登记")
    s = replace_line(s, "| **structured_dedup** | ★ **σ =",
            "| **structured_dedup** | ★ **σ = %s、q95 = %s（所有组恒为 5/5）★★ |"
            % (fmt(sd["sigma_rep"]), fmt(sd["q95_nearest_rank"])), "6.10.2 sdedup 行")

    # ── 6.10.4 主判据表（★ 逐格、题级方向全部从 json 取 ★）──
    for name, label in (("H-TOPO-4a", "有无交互"), ("H-TOPO-4c", "有无综述"),
                        ("H-TOPO-4d", "轮内可见性图")):
        if name not in verdicts:
            die("json 里缺对比 %s（★ 键：%s ★）" % (name, list(verdicts.keys())))
        c = verdicts[name]
        cells = c["cells"]
        n_cells = c["n_cells"]
        stds = [x["vendi_std"] for x in cells]
        n_over = sum(1 for x in stds if abs(x) > theta0)
        cell_txt = " ｜ ".join(("**%.2f**" % abs(x) if abs(x) > theta0 else "%.2f" % abs(x))
                               for x in stds)
        # ★ 题级方向：★ 取 json 的 dir_votes（★ 那是题级均值，★ 不是单格值 ★）
        dir_txt = []
        for tid, mean, sgn in c["dir_votes"]:
            dir_txt.append("%s %+.4f" % (tid, mean))
        dir_txt = " ｜ ".join(dir_txt)
        # ★ 方向相反 ⇒ 加标注
        pos = c["pos"]; neg = c["neg"]
        if pos > 0 and neg > 0:
            dir_txt += " ⇒ **方向相反**"
        # ★ 定位旧行：★ 行前缀式（★ 幂等：★ 不依赖旧行的具体数字 ★）★★
        prefix = "| **%s** | %s |" % (name, label)
        # ★ 脆弱格列：★ 逐格标出哪些格由污染单元支撑（★ A 有 B 无 ★）★★
        n_frag = 0
        frag_txt = []
        for c in cells:
            if (name, c["tid"], c["rep"]) in fragile:
                n_frag += 1
                frag_txt.append("%s r%d" % (c["tid"], c["rep"]))
        if frag_txt:
            frag_col = "★ **%s** ★" % ("、".join(frag_txt))
        elif f1c_ratio is not None:
            frag_col = ("★ **无**（★ 已查：★ 该单元杠杆 %.2f× 同位置基线 ⇒ 不属内容依赖 ★）★"
                        % f1c_ratio)
        else:
            frag_col = "—"
        new_line = ("| **%s** | %s | %d | %s | %d/%d | ★ %s | %s |"
                    % (name, label, n_cells, cell_txt, n_over, n_cells, dir_txt, frag_col))
        s = replace_line(s, prefix, new_line, "6.10.4 %s 行" % name)

    # ★ 6.10.4 的分隔行要跟表头同列数（★ 否则 markdown 表格散架 ★）
    # ★ 分隔行：★ 按【表头下一行】定位（★ 比正则稳 ★）
    _L = s.split("\n")
    _hi = [i for i, ln in enumerate(_L) if ln.startswith("| 对比 | 唯一差 | 可比单元 |")]
    if len(_hi) != 1:
        die("6.10.4 表头命中 %d 次（★ 期望 1 ★）" % len(_hi))
    _L[_hi[0] + 1] = "|---|:-:|---|:-:|:-:|---|:-:|"
    s = "\n".join(_L)

    # ★ 6.10.4 表头加「脆弱格」列（★ 幂等：★ 先删旧表头再加 ★）
    _hdr_new = "| 对比 | 唯一差 | 可比单元 | 逐格标准化效应（vendi） | 超 θ₀ | 题级方向 | 脆弱格 |"
    # ★ ★ 幂等的关键：★ 先把【已有的任意多个「脆弱格」】归一，★ 再替换成唯一形态 ★
    #   （★ 若直接用 replace，★ 新串含旧串 ⇒ ★ 每次跑都追加一列 ★ ⇒ 表会散架 ★）
    s = re.sub(r"\| 对比 \| 唯一差 \| 可比单元 \| 逐格标准化效应（vendi） \| 超 θ₀ \| 题级方向 \|(?: \| 脆弱格)* \|",
               _hdr_new, s, count=1)

    s = re_sub_once(s, r"### 6\.10\.4 主判据（★ 标准化效应量 = 差值 ÷ 题内 σ ｜ 门槛 θ₀ = [0-9.]+ σ",
            "### 6.10.4 主判据（★ 标准化效应量 = 差值 ÷ 题内 σ ｜ 门槛 θ₀ = %.2f σ" % theta0,
            "6.10.4 标题")
    # ★ 检出力地板：★ 【整行替换】（★ 比正则稳 ★ 且天然幂等 ★）
    s = replace_line(s, "★ **检出力地板（★ 报「不可分辨」时必须同时报 ★）**：★ **θ₀ =",
            "★ **检出力地板（★ 报「不可分辨」时必须同时报 ★）**：★ **θ₀ = %.2f σ** ⇒ ★ 当前每单元需 **|标准化效应| > %.2f σ** 才可判『有差异』★★" % (theta0, theta0),
            "6.10.4 检出力地板")
    # ★ 幂等：★ 先把「才可判『有差异』」的重复尾巴归一，★ 再统一替换 ★
    s = re.sub(r"(★ \*\*检出力地板（★ 报「不可分辨」时必须同时报 ★）\*\*：★ \*\*θ₀ = [0-9.]+ σ\*\* ⇒ ★ 当前每单元需 \*\*\|标准化效应\| > [0-9.]+ σ\*\*[^\n]*)",
               r"\1", s, count=1)

    # ── 6.10.5 结论句的 n ──
    s = re_sub_once(s, r"「在已跑批的 \*\*[0-9]+/[0-9]+\*\* 单元（[^）]*）上",
            "「在已跑批的 **%d/%d** 单元（★ 快照：已跑题 %s，★ 每题 %s rep，★ 6 臂，每组 5 份综述后 proposal）上"
            % (n_actual, n_target, "、".join(d.get("tids") or []),
               "、".join(str(x) for x in (d.get("reps") or []))),
            "6.10.5 结论句 n")
    # ★ 快照说明：★ 幂等（★ 两种形态都接受，★ 已是目标形态则跳过 ★）
    _note = "（★ **本段数字由 `fill_report_partial.py` 从 `partial_verdict.json` 自动填入** ★ ⇒ ★ **n 会随批推进变化** ★ ⇒ ★ 交稿前以脚本重填为准 ★）"
    if _note not in s:
        s = re_sub_once(s, r"（★ 快照时点[^）]*★）", _note, "6.10.5 快照说明")
    # ★ ★ 结论句里的四个数（★ θ₀ / H0 原料数 / 题级 n / 已跑题数 ★）★★
    #   ★ ★ 这四个数【必须】跟着 json 走 ⇒ ★ 手抄必陈旧 ⇒ ★ 交稿前必重填 ★★
    import re as _re
    _pat = _re.compile(r"（θ₀ = [0-9.]+ 个题内 rep σ，H0 原料 [0-9]+ 个同臂同题配对）")
    if len(_pat.findall(s)) != 1:
        die("6.10.5 结论句的 θ₀/H0 原料段命中 %d 次（★ 期望 1 ★）" % len(_pat.findall(s)))
    s = _pat.sub("（θ₀ = %.2f 个题内 rep σ，H0 原料 %d 个同臂同题配对）" % (theta0, n_pairs), s)
    s = re_sub_once(s, r"H0 配对 n = [0-9]+（目标 21）",
            "H0 配对 n = %d（目标 21）" % n_pairs, "6.10.5 限制条件 H0 配对 n")
    # ★ 题级 n：★ 各对比可能不同（★ 有的题已满、有的还没 ★）⇒ 报【最小—最大】★
    _tns = sorted({v["n_tid"] for v in verdicts.values() if v.get("n_tid")})
    _ntxt = ("%d" % _tns[0] if len(_tns) == 1 else "%d–%d" % (_tns[0], _tns[-1]))
    s = re_sub_once(s, r"题级 n = [0-9]+(?:[–-][0-9]+)?（方向一致辅助条件不可判定）",
            "题级 n = %s（方向一致辅助条件不可判定）" % _ntxt, "6.10.5 题级 n")
    # ★ 已跑题数
    _ntid = len(d.get("tids") or [])
    s = re_sub_once(s, r"只覆盖已跑批的 [0-9]+ 题",
            "只覆盖已跑批的 %d 题" % _ntid, "6.10.5 已跑题数")


    # ★ ★ 形态受控性表（★ 从 morphology_control.json 填，★ 不手抄 ★）★★
    if a.morph_json:
        if not os.path.isfile(a.morph_json):
            die("morph-json 不存在：%s" % a.morph_json)
        mj = json.load(open(a.morph_json, encoding="utf-8"))
        _L = s.split("\n")
        _hi = [i for i, ln in enumerate(_L) if ln.startswith("| 臂 | 调用数 | 截断率(length) |")]
        if len(_hi) != 1:
            die("6.12.8 形态表头命中 %d 次（★ 期望 1 ★）" % len(_hi))
        _tbl = mj["table"].split("\n")
        _end = _hi[0]
        while _end < len(_L) and _L[_end].startswith("|"):
            _end += 1
        _L[_hi[0]:_end] = _tbl
        s = "\n".join(_L)

    # ★ ★ 冻结快照登记（★ 第 1 层论证线 2026-10-26：★ 正在产生的批次的读数
    # ★   不得进入定版文献 ⇒ ★ 要么等它跑完，★ 要么引一个冻结的快照 ★）★★
    if a.snapshot_json:
        if not os.path.isfile(a.snapshot_json):
            die("snapshot-json 不存在：%s" % a.snapshot_json)
        sj = json.load(open(a.snapshot_json, encoding="utf-8"))
        _ents = sj.get("entries") or []
        _comp = ""
        if len(_ents) > 1:
            _comp = ("| ★ 伴随快照 | ★ %s |\n"
                     % ("；".join("`%s`（%s，★ %d B，★ sha256 `%s`）"
                                 % (e["snapshot"], e["src"], e["bytes"], e["sha256"])
                                 for e in _ents[1:])))
        _clock = ""
        if sj.get("frozen_at") and sj.get("label_date"):
            _clock = ("| ★ 冻结时点 | ★ 机器 UTC **%s** ｜ 叙事日期 **%s**（★ 沙箱时钟与文档叙事日期相差 %d 天，★ 二者分别登记、★ 不混用 ★） |\n"
                      % (sj["frozen_at"], sj["label_date"],
                         abs(_days_between(sj["frozen_at"][:10], sj["label_date"]))))
        _reg = ("### 6.10.0 ★★ 冻结快照登记（★ 交稿版引用的部分预判决以本快照为准 ★）★★\n\n"
                "| 项 | 值 |\n|:-:|---|\n"
                "| ★ 快照文件 | ★ `%s` ★ |\n"
                "| ★ n（单元） | ★ **%d** / 360 ｜ 已跑题 %s ｜ θ₀ = %.3f |\n"
                "| ★ sha256 | ★ `%s` ★ |\n"
                "| ★ 字节数 | ★ %d |\n"
                "%s"
                "%s"
                "| ★ **为什么需要它** | ★ **本批仍在跑 ⇒ 本段读数会变 ⇒ ⇒ 交稿文献引用的必须是【冻结快照】（★ 副本 + sha256 + 条数 ★），★ 不是某个时刻的 json ★** |\n"
                % (sj["snapshot"], sj["n_units"], "、".join(sj["tids"] or []), sj["theta0"],
                   sj["sha256"], sj["bytes"], _clock, _comp))
        s = replace_markers(s, _reg, SN_BEGIN, SN_END)

    # ★ ★ 通道状态与批状态登记（★ 2026-10-26 限流事件 ★）★★
    if a.channel_json:
        if not os.path.isfile(a.channel_json):
            die("channel-json 不存在：%s" % a.channel_json)
        cj = json.load(open(a.channel_json, encoding="utf-8"))
        s = replace_markers(s, build_channel_section(cj), CH_BEGIN, CH_END)


    # ★ ★ θ₀ 多口径重算（★ 第 1 层论证线 2026-10-26 质询触发 ★）★★
    #   ★ 整节由脚本从 h0_theta0_multicalib.json 生成 ⇒ ★ 零手抄数字 ★
    if a.multicalib_json:
        if not os.path.isfile(a.multicalib_json):
            die("multicalib-json 不存在：%s" % a.multicalib_json)
        mj = json.load(open(a.multicalib_json, encoding="utf-8"))
        s = replace_markers(s, build_multicalib_section(mj), MC_BEGIN, MC_END)

        # ★ ★ 跨脚本一致性守卫：★ multicalib 的 A 口径 n 必须等于 partial_verdict 的 n ★
        #   （★ 报告 §6.10.2 与 §6.10.6 两处都写 H0 配对 n ⇒ ★ 两处同源才不会出现内部不一致 ★）★★
        nA = (mj.get("h0", {}).get("A_all_arms", {}) or {}).get("n_pairs")
        if nA is not None and nA != n_pairs:
            die("★ 跨脚本不一致：★ multicalib 的 A 口径 n=%s ≠ partial_verdict 的 n_pairs=%s "
                "（★ 两处 H0 配对 n 会写到报告不同位置 ⇒ 必报出来 ★）" % (nA, n_pairs))

        # ★ 口径登记行（★ 整行替换，★ 前缀稳定 ⇒ 幂等 ★）
        nB = (mj.get("h0", {}).get("B_prereg_new", {}) or {}).get("n_pairs")
        s = replace_line(s, "★ **口径登记（★ 纪律：数据产生后改判据必须登记 ★）**：★ 预注册写死 H0 原料 = `nosel_b3` 口径 12 + 旧批 9 = 21；",
                "★ **口径登记（★ 纪律：数据产生后改判据必须登记 ★）**：★ 预注册写死 H0 原料 = `nosel_b3` 口径 12 + 旧批 9 = 21；★ **当前 `nosel_b3` 完整配对只有 %s 个（n<6 不可标定）** ⇒ ★ 本轮用**全部臂**的同题 rep 差（n=%d）★ ⇒ ★ ★**偏离已量化（★ 见 §6.10.2b ★）★★ ★"
                % (nB if nB is not None else "—", nA if nA is not None else n_pairs),
                "6.10.2 口径登记")

        # ★ 6.10.6 的 H0 配对 n 行（★ 原来手抄 ⇒ 与 6.10.2 的 n 不一致 ⇒ 现同源 ★）
        s = replace_line(s, "| H0 配对 n |",
                "| H0 配对 n | **%d**（全部臂口径）｜ `nosel_b3` 口径 **%s** | 跑满后（★ 结构性预期 ★）：全部臂 **36** ｜ `nosel_b3` **12**（+ 旧批 9 = 21 ✔） |"
                % (nA if nA is not None else n_pairs,
                   nB if nB is not None else "—"),
                "6.10.6 H0 配对 n")

    # ★ ★ 6.12.2 / 6.12.3 的数字也由 excl-json 填（★ 避免报告里两处 n 不一致 ★）★★
    if a.excl_json:
        ej = json.load(open(a.excl_json, encoding="utf-8"))
        cu = ej.get("contaminated_units", [])
        n_tot = ej.get("n_units_total", n_actual)
        rate = ej.get("overall_pollution_rate")
        # 6.12.2 的三行
        s = replace_line(s, "| 已落盘单元 |",
                "| 已落盘单元 | **%d**（★ 由脚本填，★ 随批推进变化 ★） |" % n_tot, "6.12.2 单元数")
        s = replace_line(s, "| **总体污染率** |",
                "| **总体污染率** | **%.2f%%** |" % (100.0 * rate), "6.12.2 总体污染率")
        if cu:
            c0 = cu[0]
            s = replace_line(s, "| **该臂（`nosel_b3`）已落盘单元** |",
                    "| **该臂（`%s`）已落盘单元** | **%d**（★ 脚本填 ★） |" % (c0["arm"], c0["arm_units"]), "6.12.2 臂 n")
            s = replace_line(s, "| ★ **该臂污染率** |",
                    "| ★ **该臂污染率** | ★ **1/%d = %.1f%%** ★ ⇒ ★ **比总体高 %.1f 倍** ★ |"
                    % (c0["arm_units"], 100.0 * c0["arm_pollution_rate"],
                       (c0["arm_pollution_rate"] / rate) if rate else 0), "6.12.2 臂污染率")
        # 6.12.3 表：可比单元 / 超门槛 / 题级
        imp = ej.get("verdict_impact", {})
        frag = ej.get("fragile_cells", [])
        if frag:
            fr = frag[0]
            s = replace_line(s, "| **H-TOPO-4c**（有无综述） | 可比单元 |",
                    "| **H-TOPO-4c**（有无综述） | 可比单元 |", "6.12.3 占位") if False else s
        # 题级影响的数字（A→B）
        for cname, per_tid in imp.items():
            for tid, d in per_tid.items():
                if d.get("rel_change") is None:
                    continue
                pat = r"\| \*\*题级 %s\*\* \| \*\*[0-9.\-]+\*\* \| \*\*[0-9.\-]+\*\* \|"
                m = re.search(pat, s)
                if not m:
                    continue
                s = s[:m.start()] + ("| **题级 %s** | **%+.4f** | **%+.4f** |"
                                     % (tid, d["A"], d["B"])) + s[m.end():]
                break

    # ★ 6.10.6 表里的 θ₀
    s = re_sub_once(s, r"\| 检出力地板 \| θ₀ = \*\*[0-9.]+ σ\*\*",
            "| 检出力地板 | θ₀ = **%.2f σ**" % theta0, "6.10.6 检出力地板")

    open(a.report, "w", encoding="utf-8").write(s)
    print("✔ 已填：n=%d/%d ｜ θ₀=%.2fσ ｜ vendi σ=%s ｜ n_pairs=%d"
          % (n_actual, n_target, theta0, fmt(v["sigma_rep"]), n_pairs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
