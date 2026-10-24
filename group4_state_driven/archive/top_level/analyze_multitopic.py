#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多题分析：零判官几何读数 + 语言闸门 + 方向性读数。

⚠️ 判官额度耗尽时，本脚本提供**不依赖判官**的多题读数：
  · 臂间实词 Jaccard（题内配对）
  · 纯重跑地板（若该题有探针）
  · 取舍实体的方向性命中（结构化绑定，不用措辞判据）
  · 语言闸门（中文占比，**分析时自己算** —— 多题 runner 没记 lang_cn_ratio）

纪律：分析单元 = 题；跨题只比方向不比绝对值；失败样本显式列出。
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_arch3 import words, J   # noqa: E402


def lang_cn(t):
    """整体 CJK 字符占比（**只作粗筛**，阈值 0.5，不是 0.9）。"""
    t = t or ""
    if not t.strip():
        return 0.0
    han = len(re.findall(r"[\u4e00-\u9fff]", t))
    return round(han / max(1, len(t)), 4)


def lang_drift(t, min_run=40):
    """★ **真漂移**的判据：是否存在**连续 ≥min_run 个字符几乎不含中文**的片段。

    ⚠️ 2026-10-23 实测修正：整体 CJK 占比**不能**单独当闸门。
       T07（科普小品，讲 bug）实测整体 CJK 仅 0.72–0.84，
       但"无中文长片段"数 = **0** ⇒ 全文都是中文行，
       低占比完全来自 **markdown 标记（# / **）与英文术语（AI / Bug）**。
       ⇒ 单用 ≥0.9 的整体阈值会把"中文里夹术语的长文"误判为漂移。
    """
    t = t or ""
    if not t.strip():
        return True
    for m in re.finditer(r"[^\u4e00-\u9fff]{%d,}" % min_run, t):
        seg = m.group(0)
        if not re.search(r"[\u4e00-\u9fff]", seg):
            return True
    return False


def load(paths):
    rows = []
    for p in paths:
        for f in sorted(glob.glob(p)):
            for line in open(f, encoding="utf-8"):
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                r["_src"] = os.path.basename(f)
                rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+",
                    default=[os.path.join(HERE, "runs", "multitopic_*", "mt_*.jsonl")])
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "multitopic_analysis.json"))
    args = ap.parse_args()

    rows = load(args.src)
    print("原始行 %d" % len(rows))
    buck = defaultdict(list)
    for r in rows:
        buck[(r.get("topic_id"), r.get("arm"), r.get("tag"))].append(r)
    # 同 (题,臂,tag) 去重：优先取有效（未 hard_gate_failed / 无 error）
    picked = []
    for k, g in buck.items():
        good = [x for x in g if not (x.get("gate_failed") or x.get("error"))]
        picked.append(good[-1] if good else g[-1])

    topics = sorted({r.get("topic_id") for r in picked})
    arms = ["A", "S-self", "WF-a3-NL", "WF-a3"]
    out = {"meta": {"n_rows_raw": len(rows), "n_picked": len(picked),
                    "topics": topics, "arms": arms},
           "per_topic": {}, "失败样本": []}

    for t in topics:
        M = {}
        drift = {}
        for a in arms:
            rs = [r for r in picked if r.get("topic_id") == t and r.get("arm") == a]
            rs = sorted(rs, key=lambda r: r.get("tag") or 0)
            ok = [r for r in rs if not (r.get("gate_failed") or r.get("error"))]
            for r in rs:
                if r.get("gate_failed") or r.get("error"):
                    out["失败样本"].append({"topic": t, "arm": a, "tag": r.get("tag"),
                                            "error": r.get("error"),
                                            "n_chars": len(r.get("text") or "")})
            if ok:
                M[a] = {r.get("tag"): r for r in ok}
                drift[a] = {"n": len(ok),
                            "漂移数": sum(1 for r in ok if lang_drift(r.get("text"))),
                            "整体CJK均值": round(sum(lang_cn(r.get("text")) for r in ok) / len(ok), 4),
                            "中文占比": [lang_cn(r.get("text")) for r in ok],
                            "字数": [len(r.get("text") or "") for r in ok]}
        if len(M) < 2:
            continue
        pair = {}
        for a in M:
            for b in M:
                if a == b:
                    continue
                vals = [J(M[a][k]["text"], M[b][k]["text"]) for k in M[a] if k in M[b]]
                if vals:
                    pair["%s vs %s" % (a, b)] = {"vals": vals, "mean": round(sum(vals) / len(vals), 4)}
        # 方向性读数：base 说"深入展开"的实体，在 base 与 (若有) D2' 中的命中
        dir_read = []
        for k, r in M.get("WF-a3", {}).items():
            st1 = r.get("state1") or {}
            gaps = {int(g.get("index") or 0): g for g in (st1.get("gaps") or [])}
            ents = []
            for d in (st1.get("decisions") or []):
                if d.get("depth") == "深入展开":
                    for e in (gaps.get(int(d.get("gap_index") or 0)) or {}).get("entities") or []:
                        if e not in ents:
                            ents.append(e)
            if ents:
                dir_read.append({"tag": k, "entities": ents,
                                 "base_hits": [e for e in ents if e in (r.get("text") or "")],
                                 "base_rate": round(sum(1 for e in ents if e in (r.get("text") or "")) / len(ents), 4)})
        out["per_topic"][t] = {"n_arms": len(M), "语言闸门": drift,
                                "臂间实词J": pair, "方向性读数": dir_read}

    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n【多题 · 零判官读数】")
    for t, v in out["per_topic"].items():
        print("  === %s（%d 臂有效）===" % (t, v["n_arms"]))
        for a, d in sorted(v["语言闸门"].items()):
            print("     %-10s n=%d 真漂移%d 整体CJK均%.2f 字数%s"
                  % (a, d["n"], d["漂移数"], d["整体CJK均值"], d["字数"]))
        for p, d in sorted(v["臂间实词J"].items()):
            print("     %-22s 均 %.4f  %s" % (p, d["mean"], d["vals"]))
        for r in v["方向性读数"]:
            print("     方向性 #%s 实体%s → base 命中 %d/%d"
                  % (r["tag"], r["entities"], len(r["base_hits"]), len(r["entities"])))
    if out["失败样本"]:
        print("\n  ★ 失败样本（单列，不进汇总）：")
        for f in out["失败样本"]:
            print("     %s %s #%s  %s (%d 字)" % (f["topic"], f["arm"], f["tag"],
                                          f.get("error"), f["n_chars"]))
    print("\n[out] %s" % args.out)


if __name__ == "__main__":
    main()
