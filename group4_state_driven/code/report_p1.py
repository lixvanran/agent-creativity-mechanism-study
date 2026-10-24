#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · Phase 1 整合报告

把三块证据串成一份可交付的报告：
  ① 主对比（analyze2）        —— C2 vs C0 / C1 / S / A，题内配对 + Holm + F18
  ② D-1 换值同步（analyze_ckf）—— 「档案内容因果控制产出」
  ③ D-2 置换敏感度（analyze2 内）—— 「状态锚定 vs 跟随历史」

用法：
    python3 report_p1.py --orig runs/p2_orig.jsonl --swap runs/p2_swap.jsonl [--md out.md]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze2 as A2      # noqa: E402
import analyze_ckf as AC   # noqa: E402


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", required=True)
    ap.add_argument("--swap", required=True)
    ap.add_argument("--md", default="")
    a = ap.parse_args()
    p_o = Path(a.orig); p_o = p_o if p_o.is_absolute() else (HERE / p_o)
    p_s = Path(a.swap); p_s = p_s if p_s.is_absolute() else (HERE / p_s)

    res = A2.analyze(p_o)
    ckf = AC.analyze(p_o, p_s)
    L = []
    L.append("# 第四组 · Phase 1 判定版报告")
    L.append("")
    L.append("> **分析单元 = 题**，样本 = 题内重复测量；配对检验 + Holm 校正；"
             "α′ 按实际对比数算。")
    L.append("> **F18**：落在对照臂噪声包络内的题占比 ≥60% ⇒ 写「不可分辨」，不写「无效应」。")
    L.append("")

    # ---------- 批次
    nb = len(res["batches"])
    L.append("## 0 · 批次与规模")
    L.append("")
    L.append(md_table(["项", "值"], [
        ["产出", "%d 篇" % res["n_gen"]],
        ["题目", ", ".join(res["topics"])],
        ["臂", ", ".join(res["arms"])],
        ["批次", ", ".join(res["batches"]) + ("（**单批 ✔**）" if nb == 1 else "（**跨批 ⚠**）")],
        ["批次混用单元", len(res.get("mixed_batches") or {})],
    ]))
    L.append("")

    # ---------- 描述统计
    L.append("## 1 · 描述统计（题内均值 → 跨题汇总）")
    L.append("")
    arms = res["arms"]
    mets = [m for m in ("len", "coverage", "cov_archive", "hit_constraints",
                         "polarity", "polarity_aligned", "transfer_jaccard",
                         "n_facts", "n_excluded", "excl_hit_draft", "excl_hit_final",
                         "excl_suppressed")
            if any(k.endswith("|%s|%s" % (a, m)) for k in res["cell"] for a in arms)]
    rows = []
    for m in mets:
        row = [m]
        for arm in arms:
            vs = [v for k, v in res["cell"].items() if k.endswith("|%s|%s" % (arm, m))]
            row.append("%.4f" % (sum(vs) / len(vs)) if vs else "—")
        rows.append(row)
    L.append(md_table(["指标"] + arms, rows))
    L.append("")

    # ---------- 主对比
    L.append("## 2 · 主对比（配对检验 + Holm 校正）")
    L.append("")
    rows = []
    for c in res["contrasts"]:
        rows.append([
            c["contrast"], c["metric"],
            ("%+.4f" % c["mean_diff"]) if c.get("mean_diff") is not None else "—",
            c["n"],
            ("%.4f" % c["p_raw"]) if c.get("p_raw") is not None else "—",
            ("%.4f" % c["p_adj"]) if c.get("p_adj") is not None else "—",
            "**显著**" if c.get("reject_holm") else "不显著",
        ])
    L.append(md_table(["对比", "指标", "Δ", "n", "p_raw", "p_adj", "判定"], rows)
             if rows else "（题数不足，无法检验）")
    L.append("")

    # ---------- D-1
    L.append("## 3 · D-1 换值同步（因果证据：档案内容是否决定产出）")
    L.append("")
    rows = []
    for arm, s in sorted(ckf["summary"].items()):
        rows.append([arm, s["n"], "%.1f%%" % (s["sync_rate"] * 100),
                     "%.1f%%" % (s["new_in_new_rate"] * 100),
                     "%.1f%%" % (s["old_in_new_rate"] * 100),
                     "%.1f%%" % (s["new_in_orig_rate"] * 100)])
    L.append(md_table(["臂", "配对数", "同步率", "新值进换值版", "旧值残留", "新值进原版"], rows))
    L.append("")
    L.append("> **同步率** = 换值后正文出现新值、不含旧值、且原版不含新值。"
             "这是**因果**证据；单纯命中率高**不构成证据**。")
    L.append("")

    # ---------- D-2
    L.append("## 4 · D-2 状态历史置换敏感度（越大 = 越锚定状态而非历史）")
    L.append("")
    if res.get("n_swap"):
        sw = res["swap_cell"]
        arms2 = sorted({k.split("|")[1] for k in sw})
        rows = []
        for tid in res["topics"]:
            row = [tid]
            for arm in arms2:
                v = sw.get("%s|%s" % (tid, arm))
                row.append("%.4f" % v if v is not None else "—")
            rows.append(row)
        L.append(md_table(["题"] + arms2, rows))
        L.append("")
        for c in res.get("swap_contrasts", []):
            L.append("- `%s` swap_jaccard Δ=%+.4f n=%d p_raw=%s p_adj=%s ⇒ **%s**"
                     % (c["contrast"], c["mean_diff"], c["n"],
                        ("%.4f" % c["p_raw"]) if c.get("p_raw") is not None else "—",
                        ("%.4f" % c["p_adj"]) if c.get("p_adj") is not None else "—",
                        "显著" if c.get("reject_holm") else "不显著"))
    else:
        L.append("（无置换探针数据）")
    L.append("")

    # ---------- F18
    L.append("## 5 · F18 噪声包络")
    L.append("")
    if res.get("f18"):
        rows = [[mt, f["n_topics"], f["inside"], "%.0f%%" % (f["ratio"] * 100), f["verdict"]]
                for mt, f in res["f18"].items()]
        L.append(md_table(["指标", "题数", "落在包络内", "占比", "判定"], rows))
    else:
        L.append("（数据不足）")
    L.append("")

    # ---------- 守恒门
    L.append("## 6 · 体裁 / 对象守恒门（multi-mind 失败模式筛查）")
    L.append("")
    rows = []
    for arm in res["arms"]:
        sub = [r for r in res["rows"] if r["arm"] == arm]
        if not sub:
            continue
        rows.append([arm, len(sub),
                     "%d/%d" % (sum(1 for r in sub if r.get("genre_drift")), len(sub)),
                     "%d/%d" % (sum(1 for r in sub if r.get("subject_drift")), len(sub))])
    L.append(md_table(["臂", "n", "体裁漂移", "对象漂移"], rows))
    L.append("")

    # ---------- 长度混淆
    L.append("## 7 · 长度混淆检查")
    L.append("")
    L.append(md_table(["指标", "r(len, 指标)"],
                       [[mt, ("%+.3f" % r) + ("  ⚠" if abs(r) > 0.3 else "")]
                        for mt, r in res["len_corr"].items()]))
    L.append("")

    txt = "\n".join(L)
    print(txt)
    if a.md:
        out = Path(a.md); out = out if out.is_absolute() else (HERE / out)
        out.write_text(txt, encoding="utf-8")
        print("\n[md] -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
