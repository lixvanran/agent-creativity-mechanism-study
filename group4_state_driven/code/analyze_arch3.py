#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · v3 分析器（严格按 PREREG_v3.md 的判据）

★ 判决门槛（预注册 §3.6，**在探针结果产生前**写入）
  分离   = ① 逐例 J_variant < J_D0 的比例 ≥ 2/3  且 ② 均值比 ≤ 0.70
  不可分辨 = 否则
  ⚠️ n=3 无统计效力 ⇒ 这不是显著性检验，只是判决门槛。

★ 读数
  D0     纯重跑地板（同输入同驱动整条链重跑）
  D2'    换决策（gaps/观测/实体全同，只换 depth/priority）⇒ 测**取舍内容 → 产出**
  D3     无关议题的 gaps ⇒ 盲从地板
  S-self 对照：等预算 + 取舍意识 + 无状态 ⇒ 测"状态机 vs 一次性自我说明"

★ 纪律：语言闸门先行；比率配绝对分母；失败逐个显式列出。
"""
from __future__ import annotations

import itertools
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import workflow_arch2 as WA2
import workflow_arch3 as WA3

CJK = re.compile(r"[一-鿿]")
EN = re.compile(r"[A-Za-z]")
TOPIC_WORDS = ["高考", "英语", "作文", "考试", "写作", "考生", "阅卷", "模板", "评分"]


def lang_cn(t):
    t = t or ""
    if not t.strip():
        return None
    c, e = len(CJK.findall(t)), len(EN.findall(t))
    return round(c / max(c + e, 1), 4)


def words(t):
    t = t or ""
    out = []
    for m in re.findall(r"[一-鿿]{2,}", t):
        for n in (2, 3):
            for i in range(len(m) - n + 1):
                out.append(m[i:i + n])
    for m in re.findall(r"[A-Za-z]{3,}", t):
        out.append(m.lower())
    return set(out)


def J(a, b):
    A, B = words(a), words(b)
    return round(len(A & B) / len(A | B), 4) if (A | B) else None


def topic(t):
    return round(sum(t.count(w) for w in TOPIC_WORDS) / max(len(t or "") / 100, 1), 3)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def separated(var_vals, d0_vals, thr=0.70):
    """预注册 §3.6 的分离判定。"""
    pairs = [(v, d) for v, d in zip(var_vals, d0_vals) if v is not None and d is not None]
    if not pairs:
        return {"separated": False, "why": "无有效配对", "n_pair": 0}
    lower = sum(1 for v, d in pairs if v < d)
    mv, md = mean([p[0] for p in pairs]), mean([p[1] for p in pairs])
    ratio = (mv / md) if (mv is not None and md) else None
    ok = (lower / len(pairs) >= 2 / 3 - 1e-9) and (ratio is not None and ratio <= thr)
    return {"separated": ok, "n_pair": len(pairs), "n_lower": lower,
            "lower_ratio": round(lower / len(pairs), 4),
            "mean_variant": mv, "mean_d0": md, "ratio": round(ratio, 4) if ratio else None,
            "threshold_ratio": thr}


#: v3 的决策点登记
DECISIONS_V3 = [
    {"name": "取舍陈述（措辞）", "who": "模型", "closed": False,
     "why": "取舍的**措辞**仍由模型生成（认知活动）"},
    {"name": "缺口描述（措辞）", "who": "模型", "closed": False,
     "why": "gaps 的措辞仍由模型生成"},
    {"name": "新约束（措辞）", "who": "模型", "closed": False,
     "why": "模型改写，代码只校验 gap_index 指向"},
    {"name": "★缺口相关实体", "who": "代码", "closed": True,
     "why": "逐字校验 ⊆ 初稿"},
    {"name": "★取舍表态 depth（走/略/弃）", "who": "模型·封闭枚举", "closed": True,
     "why": "取值 ∈ {深入展开, 点到为止, 放弃}；越界丢弃并标记"},
    {"name": "★优先级", "who": "模型·封闭枚举", "closed": True,
     "why": "取值 ∈ {1,2,3}；越界丢弃并标记"},
    {"name": "★必含实体（由 decisions 推导）", "who": "代码", "closed": True,
     "why": "深度=深入展开的缺口 ⇒ 其实体"},
    {"name": "★禁含实体（由 decisions 推导）", "who": "代码", "closed": True,
     "why": "深度=放弃的缺口 ⇒ 其实体"},
    {"name": "★已排除措辞（观测）", "who": "代码", "closed": True,
     "why": "从观测抽 + 逐字校验 + 长度上限"},
    {"name": "★输出语言与长度", "who": "代码", "closed": True,
     "why": "产出闸门；不合格 ⇒ 代码重试/硬闸"},
]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "runs", "arch3_compare.jsonl"))
    ap.add_argument("--probe", default=os.path.join(HERE, "runs", "arch3_probe.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch3_analysis.json"))
    args = ap.parse_args()

    rs = [json.loads(l) for l in open(args.src, encoding="utf-8") if l.strip()]
    # ★ 同批补跑 ⇒ 同一 (arm, tag) 可能有多条 ⇒ **去重**：
    #   优先取**有效**的（未 hard_gate_failed / 无 error）；若都不有效，取最后一条并标失败。
    raw_by = defaultdict(list)
    for r in rs:
        raw_by[r.get("arm")].append(r)
    by = {}
    for a, lst in raw_by.items():
        buckets = defaultdict(list)
        for r in lst:
            buckets[r.get("tag")].append(r)
        picked = []
        for tag, group in buckets.items():
            good = [r for r in group if not (r.get("gate_failed") or r.get("error"))]
            picked.append((good[-1] if good else group[-1]))
        picked.sort(key=lambda r: r.get("tag") or 0)
        by[a] = picked
    ARMS = ["A", "WF-p", "S-self", "WF-a3", "WF-a3-NO", "WF-a3-NL"]

    R = {"meta": {"n_rows_raw": len(rs),
                  "batch_ids": sorted({r.get("batch_id") for r in rs if r.get("batch_id")}),
                  "model": rs[0].get("model"), "n_questions": 1,
                  "reps": max((len(v) for v in by.values()), default=0),
                  "判据": "PREREG_v3.md §3.6：分离 = 逐例更低比例≥2/3 且 均值比≤0.70"}}

    # ---------- Q1 封闭率 ----------
    R["Q1_封闭率"] = {
        "v1_驱动相关": 0.25, "v1_全部": 0.50,
        "v2_全部": 0.70, "v2_驱动核心3项": 0.0,
        "v3_全部": round(sum(1 for d in DECISIONS_V3 if d["closed"]) / len(DECISIONS_V3), 4),
        "v3_决策点": DECISIONS_V3,
    }

    # ---------- Q2 语言闸门 ----------
    lang = {}
    for a in ARMS:
        rows = []
        for r in by.get(a, []):
            lr = lang_cn(r.get("text") or "")
            dr = lang_cn(r.get("draft") or "")
            rows.append({"tag": r.get("tag"), "final": lr, "draft": dr,
                         "drifted_final": (lr is not None and lr < 0.9),
                         "drifted_draft": (dr is not None and dr < 0.9),
                         "len": len((r.get("text") or "").strip())})
        lang[a] = {"rows": rows,
                   "n_drifted_final": sum(1 for x in rows if x["drifted_final"]),
                   "n_drifted_draft": sum(1 for x in rows if x["drifted_draft"]),
                   "n": len(rows),
                   "★硬闸失败样本（单列，不进汇总）": [
                       {"tag": r.get("tag"), "error": r.get("error")}
                       for r in by.get(a, []) if r.get("gate_failed") or r.get("error")],
                   "n_hard_gate_failed": sum(1 for r in by.get(a, [])
                                             if r.get("gate_failed") or r.get("error"))}
    R["Q2_语言闸门"] = lang

    # ---------- Q3 取舍执行（决策推导的必含/禁含）----------
    ex = {}
    for a in ("WF-a3", "WF-a3-NO"):
        rows = []
        for r in by.get(a, []):
            s1 = r.get("state1") or {}
            txt = r.get("text") or ""
            must = s1.get("must_include") or []
            forb = s1.get("forbidden") or []
            exc = s1.get("excluded") or []
            mh, mn = WA2.check_must_include(txt, must)
            fh = WA2.check_forbidden(txt, forb)
            eh = WA2.check_forbidden(txt, exc)
            decs = s1.get("decisions") or []
            rows.append({"tag": r.get("tag"),
                         "n_decisions": len(decs),
                         "depths": [d.get("depth") for d in decs],
                         "n_must": len(must), "must": must, "must_hit": mh, "must_n": mn,
                         "n_forb": len(forb), "forb": forb, "forb_hits": fh,
                         "n_exc": len(exc), "exc": exc, "exc_hits": eh,
                         "len": len(txt.strip()), "lang": lang_cn(txt)})
        nm = sum(x["n_must"] for x in rows); nmh = sum(x["must_n"] for x in rows)
        nf = sum(x["n_forb"] for x in rows); nfh = sum(len(x["forb_hits"]) for x in rows)
        ne = sum(x["n_exc"] for x in rows); neh = sum(len(x["exc_hits"]) for x in rows)
        ex[a] = {"rows": rows,
                 "must_summary": {"n_must": nm, "n_hit": nmh,
                                  "rate": round(nmh / nm, 4) if nm else None},
                 "forb_summary": {"n_forbidden": nf, "n_hit": nfh,
                                  "rate": round(nfh / nf, 4) if nf else None},
                 "exc_summary": {"n_excluded": ne, "n_hit": neh,
                                 "rate": round(neh / ne, 4) if ne else None}}
    R["Q3_取舍执行"] = ex

    # ---------- Q4 探针 ----------
    if os.path.exists(args.probe):
        pr = [json.loads(l) for l in open(args.probe, encoding="utf-8") if l.strip()]
        _arm = "WF-a3-NL" if by.get("WF-a3-NL") else "WF-a3"
        base = {r.get("tag"): r for r in by.get(_arm, [])
                if not (r.get("gate_failed") or r.get("error"))}
        rows = []
        for rec in pr:
            tag = rec.get("tag"); b = base.get(tag)
            if not b:
                continue
            l = rec.get("lang_cn_ratio")
            rows.append({"tag": tag, "variant": rec.get("variant"),
                         "J": J(b.get("text"), rec.get("text")),
                         "lang": l, "valid": (l is not None and l >= 0.9),
                         "topic": topic(rec.get("text")),
                         "must": (rec.get("state1") or {}).get("must_include") or [],
                         "must_hit": WA2.check_must_include(
                             rec.get("text"),
                             (rec.get("state1") or {}).get("must_include") or [])[0]})
        byv = defaultdict(list)
        for r in rows:
            byv[r["variant"]].append(r)
        d0 = sorted([r for r in byv.get("D0_rerun", []) if r["valid"]],
                    key=lambda x: x["tag"])
        d2 = sorted([r for r in byv.get("D2flip_NL", []) if r["valid"]],
                    key=lambda x: x["tag"])
        d3 = sorted([r for r in byv.get("D3off_NL", []) if r["valid"]],
                    key=lambda x: x["tag"])
        # 逐例配对（按 tag 对齐）
        def pair(a_list, b_list):
            bm = {x["tag"]: x for x in b_list}
            return [(x["J"], bm[x["tag"]]["J"]) for x in a_list if x["tag"] in bm]
        p_d2 = pair(d2, d0)
        p_d3 = pair(d3, d0)
        # R_tradeoff：换后"被选为深入展开"的实体出现率 − 换前同实体出现率
        rt = []
        for r in d2:
            b = base.get(r["tag"])
            if not b:
                continue
            bmust = (b.get("state1") or {}).get("must_include") or []
            b_hit, _ = WA2.check_must_include(b.get("text"), bmust)
            a_hit, _ = WA2.check_must_include(r.get("text"), r.get("must") or [])
            if b_hit is not None and a_hit is not None:
                rt.append({"tag": r["tag"], "base_must_hit": b_hit,
                           "flip_must_hit": a_hit, "delta": round(a_hit - b_hit, 4)})
        # ★★ R_NL：**不循环的驱动力读数**
        #   NL 臂**没有代码强制** ⇒ "该展开的实体出现了 / 该放弃的实体没出现"
        #   **完全是模型的选择** ⇒ 命中与否本身就是证据（不像 WF-a3 那样是恒真的）
        def ent_of(st1, depth):
            """从 state1 的 gaps+decisions 重算某 depth 对应的实体集合。"""
            gaps = {int(g.get("index") or 0): g for g in ((st1 or {}).get("gaps") or [])}
            out = []
            for d in ((st1 or {}).get("decisions") or []):
                if d.get("depth") != depth:
                    continue
                g = gaps.get(int(d.get("gap_index") or 0)) or {}
                for e in (g.get("entities") or []):
                    if e not in out:
                        out.append(e)
            return out
        r_nl = []
        for r in d2:
            b = base.get(r["tag"])
            if not b:
                continue
            b_st, f_st = b.get("state1") or {}, r.get("state1") or {}
            b_deep, f_deep = ent_of(b_st, "深入展开"), ent_of(f_st, "深入展开")
            b_drop, f_drop = ent_of(b_st, "放弃"), ent_of(f_st, "放弃")
            def hit(text, ents):
                if not ents:
                    return None
                return sum(1 for e in ents if e in (text or "")) / len(ents)
            row = {"tag": r["tag"],
                   "base_深入实体": b_deep, "flip_深入实体": f_deep,
                   "base_放弃实体": b_drop, "flip_放弃实体": f_drop,
                   "base_深入命中率": hit(b.get("text"), b_deep),
                   "flip_深入命中率": hit(r.get("text"), f_deep),
                   "base_放弃实体出现率": hit(b.get("text"), b_drop),
                   "flip_放弃实体出现率": hit(r.get("text"), f_drop),
                   # ★ 锐读数：翻转后**新增**的深入实体，在翻转产出里出现、在基线产出里少
                   "flip新增实体": [e for e in f_deep if e not in b_deep]}
            if row["flip新增实体"]:
                row["flip新增_在flip产出命中"] = [e for e in row["flip新增实体"]
                                          if e in (r.get("text") or "")]
                row["flip新增_在base产出命中"] = [e for e in row["flip新增实体"]
                                          if e in (b.get("text") or "")]
            r_nl.append(row)
        R["Q4_探针"] = {
            "rows": rows,
            "R_NL_驱动力": r_nl,
            "D0": {"vals": [x["J"] for x in d0], "mean": mean([x["J"] for x in d0])},
            "D2'": {"vals": [x["J"] for x in d2], "mean": mean([x["J"] for x in d2])},
            "D3": {"vals": [x["J"] for x in d3], "mean": mean([x["J"] for x in d3])},
            "判据_D2_vs_D0": separated([a for a, b in p_d2], [b for a, b in p_d2]),
            "判据_D3_vs_D0": separated([a for a, b in p_d3], [b for a, b in p_d3]),
            "判据_D2_vs_D3": separated([x["J"] for x in d2], [x["J"] for x in d3]),
            "R_tradeoff": rt,
        }
    else:
        R["Q4_探针"] = {"status": "探针未跑"}

    # ---------- Q5 S-self 对照 ----------
    ss = []
    for r in by.get("WF-a3", []):
        if r.get("gate_failed") or r.get("error"):
            continue
        s = [x for x in by.get("S-self", []) if x.get("tag") == r.get("tag")]
        if not s:
            continue
        s = s[0]
        l1, l2 = lang_cn(r.get("text")), lang_cn(s.get("text"))
        ss.append({"tag": r.get("tag"), "J": J(r.get("text"), s.get("text")),
                   "len_a3": len((r.get("text") or "").strip()),
                   "len_self": len((s.get("text") or "").strip()),
                   "valid": (l1 is not None and l1 >= 0.9 and l2 is not None and l2 >= 0.9)})
    R["Q5_S_self对照"] = {"rows": ss,
                          "J_mean": mean([x["J"] for x in ss if x["valid"]]),
                          "★判据：若 WF-a3 ≈ S-self ⇒ 状态机相对自我说明无增量": True}

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=2)

    # ---------- 打印 ----------
    print("=" * 78)
    print("批号 %s ｜ 模型 %s ｜ 题数 1 ｜ 每臂 %d 次"
          % (",".join(R["meta"]["batch_ids"]), R["meta"]["model"], R["meta"]["reps"]))
    print("=" * 78)
    print("\n【Q1】代码封闭率：v1 全部 50%%/驱动 25%% → v2 全部 70%%/驱动 0%% → v3 全部 %.0f%%"
          % (100 * R["Q1_封闭率"]["v3_全部"]))
    for d in DECISIONS_V3:
        print("    %s %-40s %s" % ("✔ 封闭" if d["closed"] else "✘ 开放", d["name"], d["who"]))

    print("\n【Q2】语言闸门（中文<90% = 漂移）")
    for a in ARMS:
        v = lang.get(a) or {}
        print("  %-9s 定稿漂移 %d/%s ｜ 初稿漂移 %d/%s" % (
            a, v.get("n_drifted_final"), v.get("n"), v.get("n_drifted_draft"), v.get("n")))
        if v.get("n_hard_gate_failed"):
            print("       ★失败样本（单列，不进汇总）: %s" % v.get("★硬闸失败样本（单列，不进汇总）"))

    print("\n【Q3】取舍执行")
    for a, v in ex.items():
        ms, fs, es = v["must_summary"], v["forb_summary"], v["exc_summary"]
        print("  %-9s 决策 %s ｜ 必含命中 %s/%s ｜ 禁含(决策)命中 %s/%s ｜ 禁含(观测)命中 %s/%s" % (
            a, [x["depths"] for x in v["rows"]],
            ms["n_hit"], ms["n_must"], fs["n_hit"], fs["n_forbidden"],
            es["n_hit"], es["n_excluded"]))

    print("\n【Q4】探针（判据：逐例更低≥2/3 且 均值比≤0.70）")
    q4 = R["Q4_探针"]
    if "D0" in q4:
        for r in q4["rows"]:
            print("  #%s %-14s J=%-8s 中文=%-6s %s" % (
                r["tag"], r["variant"], r["J"],
                ("%.0f%%" % (100 * r["lang"])) if r["lang"] is not None else "-",
                "" if r["valid"] else "⚠漂移(排除)"))
        print("  D0 地板  J=%s 均 %s" % (q4["D0"]["vals"], q4["D0"]["mean"]))
        print("  D2' 换决策 J=%s 均 %s" % (q4["D2'"]["vals"], q4["D2'"]["mean"]))
        print("  D3 无关  J=%s 均 %s" % (q4["D3"]["vals"], q4["D3"]["mean"]))
        for k in ("判据_D2_vs_D0", "判据_D3_vs_D0", "判据_D2_vs_D3"):
            j = q4[k]
            print("  %-16s 分离=%-5s 更低 %s/%s (%.0f%%) 均值比=%s"
                  % (k, j.get("separated"), j.get("n_lower"), j.get("n_pair"),
                     100 * (j.get("lower_ratio") or 0), j.get("ratio")))
        print("  R_tradeoff（换决策后必含实体命中率 − 换前）:")
        for r in q4["R_tradeoff"]:
            print("    #%s 基线 %.3f → 翻转 %.3f  Δ=%+.3f"
                  % (r["tag"], r["base_must_hit"], r["flip_must_hit"], r["delta"]))
    else:
        print("  ", q4.get("status"))

    print("\n【Q5】S-self 对照（WF-a3 vs 等预算自我说明）")
    for r in R["Q5_S_self对照"]["rows"]:
        print("  #%s 实词J=%s  字数 a3=%s / self=%s %s"
              % (r["tag"], r["J"], r["len_a3"], r["len_self"], "" if r["valid"] else "⚠漂移"))
    print("  均值 J = %s" % R["Q5_S_self对照"]["J_mean"])

    print("\n[out] %s" % args.out)


if __name__ == "__main__":
    main()
