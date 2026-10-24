#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · v2 分析器（含 v1 ↔ v2 的封闭率对比）

★ 本轮要回答的五个问题
  Q1 驱动决策的**代码封闭率**从 25% 升到多少？
  Q2 **语言漂移**是否被代码闸门治住？
  Q3 **候选集**（必含实体 / 禁含措辞）是否被执行？
  Q4 驱动内容**是否仍然有效**（换驱动内容 ⇒ 产出换向）？
  Q5 闸门重试**代价多大**（重试率 / 额外调用 / 字数膨胀）？

★ 纪律
  · 所有 n-gram 读数**先过语言闸门**（中文占比 ≥ 0.9），漂移样本单列
  · 比率必配绝对分母
  · 解析失败显式标记
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
import workflow_arch as WA
import workflow_arch2 as WA2

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


# ---------------------------------------------------------------- 封闭率
#: v2 的决策点登记（对照 v1 的 DECISIONS）
DECISIONS_V2 = [
    {"name": "驱动内容（取舍陈述）", "who": "模型", "closed": False,
     "why": "取舍的**措辞**仍由模型生成（认知活动）"},
    {"name": "观测（缺口描述）", "who": "模型", "closed": False,
     "why": "gaps 的措辞仍由模型生成"},
    {"name": "新约束（这一轮写什么）", "who": "模型", "closed": False,
     "why": "模型改写，代码只校验 gap_index 指向"},
    {"name": "★离散实体（要写进文章的具体东西）", "who": "代码", "closed": True,
     "why": "取值 ⊆ 初稿字面子串（代码逐字校验）"},
    {"name": "★必含实体（选哪些）", "who": "代码", "closed": True,
     "why": "代码按与缺口的 n-gram 关联度排序选出"},
    {"name": "★禁含措辞（不要写什么）", "who": "代码", "closed": True,
     "why": "代码从观测抽 + 逐字校验 + 长度上限"},
    {"name": "已排除（哪些路走过）", "who": "代码", "closed": True,
     "why": "同上"},
    {"name": "绑定（约束↔缺口）", "who": "代码", "closed": True,
     "why": "gap_index 结构声明"},
    {"name": "补齐", "who": "代码", "closed": True,
     "why": "确定性规则"},
    {"name": "★输出语言与长度", "who": "代码", "closed": True,
     "why": "产出闸门：不合格 ⇒ 代码重试"},
]


def closed_rate(decisions, slot_keys=None):
    ds = decisions
    if slot_keys:
        ds = [d for d in decisions if d.get("slot") in slot_keys]
    if not ds:
        return None
    return round(sum(1 for d in ds if d["closed"]) / len(ds), 4)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "runs", "arch2_compare.jsonl"))
    ap.add_argument("--probe", default=os.path.join(HERE, "runs", "arch2_probe.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch2_analysis.json"))
    args = ap.parse_args()

    rs = [json.loads(l) for l in open(args.src, encoding="utf-8") if l.strip()]
    by = defaultdict(list)
    for r in rs:
        by[r.get("arm")].append(r)
    for a in by:
        by[a].sort(key=lambda r: r.get("tag") or 0)
    ARMS = ["A", "WF-p", "WF-a2", "WF-a2-NO"]

    R = {"meta": {"batch_ids": sorted({r.get("batch_id") for r in rs if r.get("batch_id")}),
                  "model": rs[0].get("model"), "n_questions": 1,
                  "reps": max((len(v) for v in by.values()), default=0),
                  "★分析单元=题，只有 1 题 ⇒ 全部为本例描述": True}}

    # ---------- Q1 封闭率 ----------
    v1_dec = [
        {"name": "驱动内容", "closed": False}, {"name": "观测", "closed": False},
        {"name": "新约束", "closed": False}, {"name": "已排除", "closed": True},
        {"name": "绑定", "closed": True}, {"name": "补齐", "closed": True},
    ]
    R["Q1_封闭率"] = {
        "v1_全部决策": closed_rate(v1_dec),
        "v1_驱动相关(4个)": 0.25,
        "v2_全部决策": closed_rate(DECISIONS_V2),
        "v2_决策点": DECISIONS_V2,
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
                   "n": len(rows)}
    R["Q2_语言闸门"] = lang

    # ---------- Q3 候选集执行 + Q5 闸门代价 ----------
    cand = {}
    for a in ("WF-a2", "WF-a2-NO"):
        rows = []
        for r in by.get(a, []):
            s1 = r.get("state1") or {}
            txt = r.get("text") or ""
            must = s1.get("must_include") or []
            forb = s1.get("forbidden") or []
            mh, mn = WA2.check_must_include(txt, must)
            fh = WA2.check_forbidden(txt, forb)
            gates = r.get("gates") or {}
            n_retry = sum(len(v) - 1 for v in gates.values())
            rows.append({"tag": r.get("tag"),
                         "n_entities": len(s1.get("entities") or []),
                         "n_must": len(must), "must": must,
                         "n_forbidden": len(forb), "forbidden": forb,
                         "must_hit": mh, "must_n": mn,
                         "forbidden_hits": fh,
                         "n_gate_attempts": sum(len(v) for v in gates.values()),
                         "n_retry": n_retry,
                         "len": len(txt.strip()),
                         "lang": lang_cn(txt),
                         "entities_in_final": [e for e in (s1.get("entities") or [])
                                              if e in txt],
                         })
        n_m = sum(x["n_must"] for x in rows)
        n_mh = sum(x["must_n"] for x in rows)
        n_f = sum(x["n_forbidden"] for x in rows)
        n_fh = sum(len(x["forbidden_hits"]) for x in rows)
        cand[a] = {"rows": rows,
                   "must_summary": {"n_must": n_m, "n_hit": n_mh,
                                    "rate": round(n_mh / n_m, 4) if n_m else None},
                   "forbidden_summary": {"n_forbidden": n_f, "n_hit": n_fh,
                                         "rate": round(n_fh / n_f, 4) if n_f else None},
                   "gate_summary": {
                       "n_samples": len(rows),
                       "n_retry": sum(x["n_retry"] for x in rows),
                       "retry_rate": round(sum(x["n_retry"] for x in rows)
                                           / max(sum(x["n_gate_attempts"] for x in rows), 1), 4),
                       "len_mean": mean([x["len"] for x in rows])}}
    R["Q3_候选集"] = cand
    R["Q5_闸门代价"] = {a: cand[a]["gate_summary"] for a in cand}

    # ---------- Q4 探针 ----------
    if os.path.exists(args.probe):
        pr = [json.loads(l) for l in open(args.probe, encoding="utf-8") if l.strip()]
        base = {r.get("tag"): r for r in by.get("WF-a2", [])}
        rows = []
        for rec in pr:
            tag = rec.get("tag")
            b = base.get(tag)
            if not b:
                continue
            v = rec.get("variant")
            rows.append({"tag": tag, "variant": v,
                         "J": J(b.get("text"), rec.get("text")),
                         "lang": rec.get("lang_cn_ratio"),
                         "topic": topic(rec.get("text")),
                         "must_hit": (rec.get("state1") or {}).get("must_include") and
                                     WA2.check_must_include(rec.get("text"),
                                                            (rec.get("state1") or {}).get("must_include"))[0],
                         "n_must": len((rec.get("state1") or {}).get("must_include") or [])})
        # ★ D4：候选集（必含实体/禁含措辞）是否随观测整份换源
        d4_rows = []
        base_all = by.get("WF-a2", [])
        for rec in pr:
            if rec.get("variant") != "D4_swapsource":
                continue
            tag = rec.get("tag")
            idx = [i for i, r in enumerate(base_all) if r.get("tag") == tag]
            if not idx:
                continue
            i = idx[0]
            b = base_all[i]
            other = base_all[(i + 1) % len(base_all)]
            own_draft = b.get("draft") or ""
            oth_draft = other.get("draft") or ""
            must = (rec.get("state1") or {}).get("must_include") or []
            forb = (rec.get("state1") or {}).get("forbidden") or []
            d4_rows.append({
                "tag": tag,
                "必含实体逐字在【换入初稿】": sum(1 for m in must if m in oth_draft),
                "必含实体逐字在【原初稿】": sum(1 for m in must if m in own_draft),
                "n_must": len(must),
                "禁含措辞逐字在【换入初稿】": sum(1 for f in forb if f in oth_draft),
                "禁含措辞逐字在【原初稿】": sum(1 for f in forb if f in own_draft),
                "n_forb": len(forb),
            })
        R["Q4_D4_候选集换源"] = {"rows": d4_rows,
            "合计_必含_在换入": sum(x["必含实体逐字在【换入初稿】"] for x in d4_rows),
            "合计_必含_在原": sum(x["必含实体逐字在【原初稿】"] for x in d4_rows),
            "合计_禁含_在换入": sum(x["禁含措辞逐字在【换入初稿】"] for x in d4_rows),
            "合计_禁含_在原": sum(x["禁含措辞逐字在【原初稿】"] for x in d4_rows),
        }
        R["Q4_探针"] = {"rows": rows,
                        "by_variant": {v: {"n": len([x for x in rows if x["variant"] == v]),
                                           "J_mean": mean([x["J"] for x in rows if x["variant"] == v]),
                                           "topic_mean": mean([x["topic"] for x in rows if x["variant"] == v])}
                                       for v in sorted({x["variant"] for x in rows})}}
    else:
        R["Q4_探针"] = {"status": "探针未跑"}

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=2)

    # ---------- 打印 ----------
    print("=" * 78)
    print("批号 %s ｜ 模型 %s ｜ 题数 1 ｜ 每臂 %d 次"
          % (",".join(R["meta"]["batch_ids"]), R["meta"]["model"], R["meta"]["reps"]))
    print("=" * 78)

    print("\n【Q1】驱动决策的代码封闭率")
    q1 = R["Q1_封闭率"]
    print("  v1：全部 6 决策 %.0f%% ｜ **驱动相关 4 个 = 25%%**" % (100 * q1["v1_全部决策"]))
    print("  v2：全部 %d 决策 %.0f%%" % (len(DECISIONS_V2), 100 * q1["v2_全部决策"]))
    for d in DECISIONS_V2:
        print("    %s %-38s %s" % ("✔ 封闭" if d["closed"] else "✘ 开放", d["name"], d["who"]))

    print("\n【Q2】语言闸门效果（中文占比 < 90% = 漂移）")
    for a in ARMS:
        v = lang.get(a) or {}
        print("  %-9s 定稿漂移 %d/%s ｜ 初稿漂移 %d/%s"
              % (a, v.get("n_drifted_final"), v.get("n"), v.get("n_drifted_draft"), v.get("n")))

    print("\n【Q3】候选集执行")
    for a, v in cand.items():
        ms, fs = v["must_summary"], v["forbidden_summary"]
        print("  %-9s 必含命中 %d/%d (%.0f%%) ｜ 禁含命中 %d/%d (%.0f%%)" % (
            a, ms["n_hit"], ms["n_must"], 100 * (ms["rate"] or 0),
            fs["n_hit"], fs["n_forbidden"], 100 * (fs["rate"] or 0)))
        for row in v["rows"]:
            print("     #%s entities=%s must=%s hit=%s forb=%s 命中=%s 中文=%s" % (
                row["tag"], row["n_entities"], row["n_must"], row["must_hit"],
                row["n_forbidden"], row["forbidden_hits"], row["lang"]))

    print("\n【Q5】闸门代价")
    for a, g in R["Q5_闸门代价"].items():
        print("  %-9s 样本 %s ｜ 闸门重试 %s 次 ｜ 重试率 %.0f%% ｜ 字数均 %s" % (
            a, g["n_samples"], g["n_retry"], 100 * g["retry_rate"], g["len_mean"]))

    print("\n【Q4】探针")
    q4 = R["Q4_探针"]
    if "rows" in q4:
        for r in q4["rows"]:
            print("  #%s %-16s J=%s 中文=%s 话题=%s must_hit=%s" % (
                r["tag"], r["variant"], r["J"],
                ("%.0f%%" % (100 * r["lang"])) if r["lang"] is not None else "-",
                r["topic"], r["must_hit"]))
        for v, d in q4["by_variant"].items():
            print("  %-16s n=%s J均=%s 话题均=%s" % (v, d["n"], d["J_mean"], d["topic_mean"]))
    else:
        print("  ", q4.get("status"))

    d4 = R.get("Q4_D4_候选集换源")
    if d4 and d4.get("rows"):
        print("\n【Q4b】D4 候选集换源（换观测 ⇒ 候选集是否整份换源）")
        for r in d4["rows"]:
            print("  #%s 必含 %d/%d 在换入 ｜ %d 在原 ｜ 禁含 %d/%d 在换入 ｜ %d 在原" % (
                r["tag"], r["必含实体逐字在【换入初稿】"], r["n_must"],
                r["必含实体逐字在【原初稿】"],
                r["禁含措辞逐字在【换入初稿】"], r["n_forb"],
                r["禁含措辞逐字在【原初稿】"]))
        print("  合计：必含 在换入 %d / 在原 %d ｜ 禁含 在换入 %d / 在原 %d" % (
            d4["合计_必含_在换入"], d4["合计_必含_在原"],
            d4["合计_禁含_在换入"], d4["合计_禁含_在原"]))

    print("\n[out] %s" % args.out)


if __name__ == "__main__":
    main()
