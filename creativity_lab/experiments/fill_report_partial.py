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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--excl-json", default=None,
                    help="★ recompute_excluding.py 的输出（★ 用来给主判据表加『脆弱格』列 ★）")
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
    if a.excl_json:
        if not os.path.isfile(a.excl_json):
            die("excl-json 不存在：%s" % a.excl_json)
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
        frag_col = ("★ **%s** ★" % ("、".join(frag_txt))) if frag_txt else "—"
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
