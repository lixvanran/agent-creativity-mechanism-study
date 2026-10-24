# -*- coding: utf-8 -*-
"""把实测读数**从 JSON 程序化生成**成可进版本控制的证据表（markdown）。

> 2026-10-23 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/build_evidence_tables.py`
>
> ★ **为什么要有这个脚本**：
>   ① `runs/` 在 `.gitignore` 里 ⇒ 原始 JSON 进不了 git ⇒ 证据会随沙箱重置丢失；
>   ② 手抄读数表 = 摘要与事实不一致的经典来源 ⇒ **必须程序化生成**（协议 §4.3 的元数据纪律）。
>   ⇒ 本脚本把 `runs/` 里的 JSON **原样**渲染成 `results/*.md`（可进 git 的证据）。
>
> 用法：
>   python3 -B build_evidence_tables.py --out results
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

RUNS = os.path.join(HERE, "runs")
JV3 = os.path.join(RUNS, "dev", "judge_variants3", "judge_variants.json")
JVSC = os.path.join(RUNS, "dev", "judge_variants_sc", "judge_variants.json")
STAB = os.path.join(RUNS, "dev", "stability", "judge_variants_merged.json")
SELFTEST = os.path.join(HERE, "selftest_out_c", "selftest.json")

ANS_ORDER = ["B0_direct#D01", "B0_direct#D05", "B0_direct#D08",
             "B0_noev#D01", "B0_noev#D05", "B0_noev#D08",
             "W_div#D01", "W_div#D05", "W_div#D08"]


def _load(p: str) -> Any:
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def _variants(blob: Dict[str, Any]) -> List[Dict[str, Any]]:
    return blob.get("variants", []) if isinstance(blob, dict) else []


def table_readings(out: str) -> None:
    """跨判官读数表 + 判官自检表"""
    st = _load(STAB)
    if not st:
        print("⚠️ 没有 %s，跳过稳定性表" % STAB)
        return
    vs = st.get("variants", [])
    md: List[str] = []
    md.append("# 跨判官读数与自检（2026-10-23 终局跑批）\n")
    md.append("> **程序化生成**（`build_evidence_tables.py`）⇒ 与 `runs/dev/stability/judge_variants_merged.json` 逐字一致\n")
    md.append("> 原始 JSON 在 `runs/`（被 `.gitignore` 忽略）⇒ 本表是进版本控制的**证据副本**\n")

    md.append("\n## 1. 跨判官读数（同一批 9 份答案）\n")
    md.append("| 判官 | " + " | ".join(a.replace("#", " ") for a in ANS_ORDER) + " | 通道失败 |")
    md.append("|---|" + "---:|" * (len(ANS_ORDER) + 1))
    for v in vs:
        rs = v.get("results") or v.get("readings") or {}
        cells = []
        nfail = 0
        for a in ANS_ORDER:
            r = rs.get(a)
            if not r:
                cells.append("—")
                continue
            if r.get("channel_failed"):
                nfail += 1
            cells.append("%s / %s" % (r.get("VD_anchor_in"), r.get("VD_anchor_out")))
        md.append("| `%s` | %s | %d/%d |"
                  % (v.get("id"), " | ".join(cells), nfail, len(ANS_ORDER)))
    md.append("\n> 单元格 = `VD_anchor_in` / `VD_anchor_out`；「通道失败」= 该变体有调用失败/空的答案份数\n")

    md.append("\n## 2. 判官自检（DEV 金标，**按题分组**）\n")
    md.append("| 判官 | 真卡率 | 假卡率 | 两轮一致 | 闸门 |")
    md.append("|---|---:|---:|:-:|:-:|")
    for v in vs:
        sc = v.get("selfcheck") or {}
        t = sc.get("true_round1") or {}
        f = sc.get("false_round1") or {}
        md.append("| `%s` | %s (n=%s) | %s (n=%s) | %s | %s |"
                  % (v.get("id"), t.get("rate"), t.get("n"), f.get("rate"), f.get("n"),
                     "是" if sc.get("reproducible_2_rounds") else "**否**",
                     "通过" if sc.get("gate_pass") else "**未过**"))
    md.append("\n> 闸门 = 协议 §4.6：真卡 ≥0.75 **且** 假卡 ≥0.75 **且** 两轮一致\n")

    with open(os.path.join(out, "JUDGE-STABILITY-2026-10-23.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("✓ 落盘 JUDGE-STABILITY-2026-10-23.md")


def table_crossrun(out: str) -> None:
    """跨跑批复现性（同一判官两次独立跑批）"""
    a, b = _load(JV3), _load(JVSC)
    if not a or not b:
        print("⚠️ 缺跑批文件，跳过跨跑批表")
        return
    def idx(blob: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        d = {}
        for v in _variants(blob):
            vid = v.get("id") or ""
            if "minimax" in vid.lower() or vid.startswith("V1"):
                continue
            d[vid] = v.get("readings") or v.get("results") or {}
        return d
    A, B = idx(a), idx(b)
    md = ["# 跨跑批可复现性（同一判官 · 两次独立跑批 · 2026-10-23）\n",
          "> **程序化生成**（`build_evidence_tables.py`）\n",
          "\n| 判官 | 逐份读数完全一致 | 锚内一致 | 锚外一致 | 份数 |",
          "|---|--:|--:|--:|--:|"]
    for vid in sorted(B):
        if vid not in A:
            continue
        sa = sb = so = 0
        n = 0
        for k, v in B[vid].items():
            x = A[vid].get(k)
            if x is None:
                continue
            n += 1
            # ★ 比"读数"（IN/OUT/claims/cards），不连整个 dict（含耗时等易变字段）
            keys = ("VD_anchor_in", "VD_anchor_out", "n_claims", "n_cards")
            if all(x.get(kk) == v.get(kk) for kk in keys):
                sa += 1
            if x.get("VD_anchor_in") == v.get("VD_anchor_in"):
                sb += 1
            if x.get("VD_anchor_out") == v.get("VD_anchor_out"):
                so += 1
        md.append("| `%s` | **%d/%d** | %d/%d | %d/%d | %d |"
                  % (vid, sa, n, sb, n, so, n, n))
    md.append("\n> ★ 读数**完全一致** ⇒ 判官之间的差异是**系统偏移（严格度）**，不是测量噪声\n")
    with open(os.path.join(out, "CROSS-RUN-REPRO-2026-10-23.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("✓ 落盘 CROSS-RUN-REPRO-2026-10-23.md")


def table_selftest(out: str) -> None:
    """Tier A / Tier B 自检结果"""
    st = _load(SELFTEST)
    if not st:
        print("⚠️ 没有 %s，跳过自检表" % SELFTEST)
        return
    tb = st.get("tier_b") or {}
    sc = tb.get("judge_selfcheck") or {}
    md = ["# 自检结果（Tier A 机械层 / Tier B 判官层）\n",
          "> **程序化生成**（`build_evidence_tables.py`）｜源：`selftest_out_c/selftest.json`\n",
          "\n| 项 | 结果 |", "|---|---|"]
    md.append("| 整体 | %s（失败 %d 项） |"
              % ("✅ 通过" if st.get("overall_passed") else "❌ 未过",
                 len(st.get("failures") or tb.get("failures") or [])))
    fa = tb.get("fork_assignment") or {}
    if fa:
        md.append("| 岔口归并纯度 | **%.3f**（%s/%s） |"
                  % (fa.get("purity", 0), fa.get("purity_num"), fa.get("purity_den")))
        md.append("| 岔口归并分离度 | **%.3f**（%s/%s） |"
                  % (fa.get("separation", 0), fa.get("sep_num"), fa.get("sep_den")))
    if sc:
        md.append("| 锚外探针自检（真卡） | **%s/%s** |"
                  % (sc.get("true_pass"), sc.get("true_total")))
        md.append("| 锚外探针自检（假卡被拒） | **%s/%s**（误放行 %s） |"
                  % (sc.get("false_rejected"), sc.get("false_total"),
                     sc.get("false_wrongly_accepted")))
        md.append("| 判官 effort | `%s` |" % sc.get("effort"))
        c = sc.get("calls") or {}
        md.append("| 通道健康度（★ **尝试级**） | %.4f（%s 次调用：空 %s / 截断 %s / 错误 %s） |"
                  % (sc.get("channel_health", 0), c.get("n_calls"),
                     c.get("n_empty_content"), c.get("n_truncated"), c.get("n_error")))
    md.append("\n> 协议 F7：判官自检不过 ⇒ **拒绝出数**\n")
    with open(os.path.join(out, "SELFTEST-2026-10-23.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("✓ 落盘 SELFTEST-2026-10-23.md")


def table_effort(out: str) -> None:
    """effort 探针结果（若已跑）"""
    p = os.path.join(RUNS, "dev", "effort_probe", "effort_probe.json")
    blob = _load(p)
    if not blob:
        print("⚠️ 没有 effort_probe.json，跳过")
        return
    md = ["# effort 档位探针（判官通道可靠性 × 判官质量）\n",
          "> **程序化生成**（`build_evidence_tables.py`）｜源：`runs/dev/effort_probe/effort_probe.json`\n",
          "> 判官 `%s` ｜ 调用 `CARD_Q_OUT`（OUT 通道真实卡片调用）\n" % blob.get("meta", {}).get("judge_model"),
          "\n## 轴1 · 结果级健康\n",
          "| 答案 | effort | 调用 | 解析出卡 | 断言 | parsefail | parsefail率 |",
          "|---|---|--:|--:|--:|--:|--:|"]
    for s in blob.get("summary", []):
        rate = s["n_parsefail"] / float(max(s["n_claims"], 1))
        md.append("| %s | **%s** | %d | %d | %d | %d | **%.2f** |"
                  % (s["answer"], s["effort"], s["n_calls"], s["n_parsed"],
                     s["n_claims"], s["n_parsefail"], rate))
    md += ["\n## 轴2a · 跨轮一致\n", "| 答案 | effort | 轮 | 卡数 | 一致 |", "|---|---|--:|--:|:-:|"]
    for r in blob.get("cross_round", []):
        md.append("| %s | %s | %d | %d | %s |" % (r["answer"], r["effort"], r["round"],
                                                   r["n_cards"], "✔" if r["consistent"] else "✘"))
    md += ["\n## 轴2b · 与 max 档一致（质量有没有退化）\n",
           "| 答案 | effort | 轮 | 本档卡数 | max 卡数 | 一致 |", "|---|---|--:|--:|--:|:-:|"]
    for r in blob.get("cross_effort_vs_max", []):
        md.append("| %s | %s | %d | %d | %d | %s |" % (r["answer"], r["effort"], r["round"],
                                                        r["n_cards_this"], r["n_cards_max"],
                                                        "✔" if r["same_as_max"] else "✘"))
    with open(os.path.join(out, "EFFORT-PROBE-2026-10-23.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("✓ 落盘 EFFORT-PROBE-2026-10-23.md")


def table_measure_medium(out: str) -> None:
    """★ 通道健康后的全量读数（effort=medium）—— 今天唯一可引用的那批"""
    p = os.path.join(RUNS, "dev", "measure_medium", "anchor_readout.json")
    blob = _load(p)
    if not blob:
        print("⚠️ 没有 measure_medium，跳过")
        return
    res = blob.get("results", {})
    md = ["# 通道修复后的全量读数（effort=medium · 自适应批）\n",
          "> **程序化生成**（`build_evidence_tables.py`）｜源：`runs/dev/measure_medium/anchor_readout.json`\n",
          "> 判官 `%s` ｜ **judge_effort = `%s`**（★ 不同 effort 的读数**不可比**）\n"
          % (blob.get("judge_model"), blob.get("judge_effort")),
          "\n| 答案 | 臂 | VD_anchor_in | **VD_anchor_out** | 锚外候选数(判官层) | 断言 | 卡 | parsefail | 有效 | 通道失败 |",
          "|---|---|--:|--:|--:|--:|--:|--:|:-:|:-:|"]
    for a in ANS_ORDER:
        r = res.get(a)
        if not r:
            continue
        md.append("| %s | %s | %s | **%s** | %s | %s | %s | %s | %s | %s |"
                  % (a.replace("#", " "), r.get("arm"), r.get("VD_anchor_in"),
                     r.get("VD_anchor_out"), r.get("n_out_cand", "—"),
                     r.get("n_claims"), r.get("n_cards"), r.get("parsefail_rate"),
                     r.get("valid"), r.get("channel_failed")))
    c = blob.get("calls", {})
    md += ["\n**通道健康**：调用 %s｜空内容 %s｜截断 %s｜错误 %s｜健康度 %.2f\n"
           % (c.get("n_calls"), c.get("n_empty_content"), c.get("n_truncated"),
              c.get("n_error"),
              1.0 - (c.get("n_empty_content", 0) + c.get("n_truncated", 0))
              / float(max(c.get("n_calls", 1), 1)))]
    with open(os.path.join(out, "MEASURE-MEDIUM-2026-10-23.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("✓ 落盘 MEASURE-MEDIUM-2026-10-23.md")


def table_channel_probe(out: str) -> None:
    """通道诊断（单发不重试）"""
    p = os.path.join(RUNS, "dev", "channel_probe", "channel_probe.json")
    blob = _load(p)
    if not blob:
        print("⚠️ 没有 channel_probe，跳过")
        return
    md = ["# 判官通道诊断（单次尝试 · 不重试）\n",
          "> **程序化生成**（`build_evidence_tables.py`）｜源：`runs/dev/channel_probe/channel_probe.json`\n",
          "> 答案 `%s`（题 %s）｜max_tokens=%d｜%s\n"
          % (blob["meta"].get("answer"), blob["meta"].get("task_id"),
             blob["meta"].get("max_tokens"), blob["meta"].get("judge_model")),
          "\n| 批大小 | effort | 调用 | 截断 | 空内容 | 错误 | parsefail | 解析率 | 平均思考token | 平均完成token | 平均秒 |",
          "|---:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for s in blob.get("summary", []):
        pr = s["n_parsed"] / float(max(s["n_claims"], 1))
        md.append("| %d | **%s** | %d | %d | %d | %d | %d | **%.2f** | %d | %d | %.0f |"
                  % (s["batch"], s["effort"], s["n_calls"], s["n_truncated"],
                     s["n_empty_content"], s["n_error"], s["n_parsefail"], pr,
                     s["avg_reasoning_len"], s["avg_completion_tokens"], s["avg_secs"]))
    md.append("\n> ★ 根因：`reasoning_effort` 省略 ⇒ 官方默认 **max** ⇒ 思考块吃光 `max_tokens`\n")
    with open(os.path.join(out, "CHANNEL-PROBE-2026-10-23.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("✓ 落盘 CHANNEL-PROBE-2026-10-23.md")


def table_effort_sweep(out: str) -> None:
    """effort 敏感性（判官层 vs 闸门层）"""
    p = os.path.join(RUNS, "dev", "effort_sweep", "effort_sweep.json")
    blob = _load(p)
    if not blob:
        print("⚠️ 没有 effort_sweep，跳过")
        return
    res = blob.get("results", {})
    effs = blob.get("meta", {}).get("efforts", [])
    md = ["# effort 敏感性对照（判官层 vs 闸门层）\n",
          "> **程序化生成**（`build_evidence_tables.py`）｜源：`runs/dev/effort_sweep/effort_sweep.json`\n",
          "> 只重判 OUT 判定链（claims 取自已落盘抽取结果 ⇒ **单因子对照**）｜批=%s\n"
          % blob.get("meta", {}).get("batch"),
          "\n| 答案 | " + " | ".join("%s 候选/过闸/健康" % e for e in effs) + " |",
          "|---|" + "---|" * len(effs)]
    for a in sorted(res):
        cells = []
        for e in effs:
            r = res[a].get(e) or {}
            if r.get("error"):
                cells.append("ERR(%s)" % r["error"])
            else:
                cells.append("%s / %s / %s" % (r.get("n_out_cand"), r.get("n_pass"),
                                               r.get("channel_health")))
        md.append("| %s | %s |" % (a, " | ".join(cells)))
    md.append("\n> **候选数（判官层）对 effort 敏感；过闸数（闸门层）在 effort 下稳定**\n")
    with open(os.path.join(out, "EFFORT-SWEEP-2026-10-23.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("✓ 落盘 EFFORT-SWEEP-2026-10-23.md")


def table_calibration(out: str) -> None:
    """金标标定（可复现性 N 次）"""
    p = os.path.join(RUNS, "dev", "calib_stability", "calibration_stability.json")
    blob = _load(p)
    if not blob:
        print("⚠️ 没有 calib_stability，跳过")
        return
    s = blob["summary"]
    md = ["# 锚外闸门标定（N 次重复 · 报范围）\n",
          "> **程序化生成**（`build_evidence_tables.py`）｜源：`runs/dev/calib_stability/calibration_stability.json`\n",
          "> 判官 `%s` ｜ effort `%s` ｜ 重复 %d 次 ｜ %d 张金标卡\n"
          % (s["meta"]["judge_model"], s["meta"]["effort"], s["meta"]["repeats"],
             s["meta"]["n_gold_cards"]),
          "\n## 每次的三个读数\n",
          "| 重复 | 灵敏度 | 特异度 | 池化特异度 |", "|---:|---|---|---|"]
    for r in s["per_run"]:
        md.append("| %d | %d/%d = **%.3f** | %d/%d = **%.3f** | %d/%d = **%.3f** |"
                  % (r["rep"], r["sensitivity"]["n_hit"], r["sensitivity"]["n"],
                     r["sensitivity"]["rate"], r["specificity"]["n_hit"],
                     r["specificity"]["n"], r["specificity"]["rate"],
                     r["pooled_specificity"]["n_hit"], r["pooled_specificity"]["n"],
                     r["pooled_specificity"]["rate"]))
    sr, sp, ps = s["sensitivity_range"], s["specificity_range"], s["pooled_specificity_range"]
    md += ["\n## ★ 报范围（单次是运气）\n",
           "| 读数 | 范围 | 均值 | 分母 |", "|---|---|--:|--:|",
           "| 灵敏度 | **%.3f – %.3f** | %.3f | %d |" % (sr["min"], sr["max"], sr["mean"], sr["n"]),
           "| 特异度 | **%.3f – %.3f** | %.3f | %d |" % (sp["min"], sp["max"], sp["mean"], sp["n"]),
           "| 池化特异度 | **%.3f – %.3f** | %.3f | %d |" % (ps["min"], ps["max"], ps["mean"], ps["n"])]
    if s.get("unstable_cards"):
        md += ["\n## 失效卡（稳定失效 vs 随机翻转）\n",
               "| 卡 | 题 | 标注 | 各次判定 | 翻转率 | 类型 |", "|---|---|---|---|--:|---|"]
        for c in s["unstable_cards"]:
            kind = "★ **稳定失效**" if c["flip_rate"] == 1.0 else "随机翻转"
            md.append("| `%s` | %s | %s | %s | %.2f | %s |"
                      % (c["card_id"], c["task_id"], c["label"], c["verdicts"],
                         c["flip_rate"], kind))
    with open(os.path.join(out, "CALIBRATION-2026-10-23.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("✓ 落盘 CALIBRATION-2026-10-23.md")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    table_readings(args.out)
    table_crossrun(args.out)
    table_selftest(args.out)
    table_effort(args.out)
    table_measure_medium(args.out)
    table_channel_probe(args.out)
    table_effort_sweep(args.out)
    table_calibration(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
