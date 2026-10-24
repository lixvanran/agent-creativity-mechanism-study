#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · D-1 换值同步分析器

═══ 这是什么 ═══
把**同一份档案里的可核锚点**换掉（2048 → 2011），其余一切不变，重跑生成。
然后问一个**因果问题**：

    正文的可核痕迹，是不是由档案的内容**决定**的？

判据（全部机械、零判官）：
    new_in_new   换值版正文里出现**新**值      —— 期望高
    old_in_new   换值版正文里还出现**旧**值    —— 期望低
    new_in_orig  原版正文里出现**新**值        —— 期望低（对照）
    synchronized = new_in_new 且 ¬old_in_new 且 ¬new_in_orig

═══ 为什么"锚点命中"单独不够 ═══
主控的硬约束（第四组论证 §3.4f）：
> 「一个精心设计的提示词也能做到。C0 臂里若写着"请务必提到 2048"，换值后模型同样会提到新值。」
⇒ **命中率高不构成证据**，**换值同步才是**。
而 D-1 的绝对命中对 C1 天然不利（C1 的取舍压缩会丢事实）⇒
**同步率比命中率更公平**：它问的是"档案内容变了，产出跟没跟"，而不是"档案落地了多少"。

═══ 必须成对读 ═══
换值同步是**配对**测量：同题同臂同样本编号下，原版 vs 换值版。
绝不能把"原版命中率"和"换值版命中率"当独立样本比。
"""
from __future__ import annotations

import argparse
import json
import sys
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import metrics2 as M  # noqa: E402


# ---------------------------------------------------------------- 统计（纯标准库）
def binom_test_two_sided(k: int, n: int, p: float = 0.5) -> float:
    """精确二项检验（双尾）。"""
    if n == 0:
        return 1.0
    probs = [comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(n + 1)]
    pk = probs[k]
    return min(1.0, sum(x for x in probs if x <= pk * (1 + 1e-9)))


def mcnemar_exact(b: int, c: int) -> float:
    """McNemar 精确检验（双尾）：b = 两臂都真，c = 只有 A 真。"""
    n = b + c
    if n == 0:
        return 1.0
    probs = [comb(n, i) * 0.5 ** n for i in range(n + 1)]
    pk = probs[min(b, c)]
    return min(1.0, sum(x for x in probs if x <= pk * (1 + 1e-9)))


def load(path: Path) -> tuple:
    stances, gens = {}, []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("kind") == "stance":
            stances[(r["topic_id"], r["arm"])] = r
        elif r.get("kind") == "gen" and not r.get("error"):
            gens.append(r)
    return stances, gens


def analyze(orig_path: Path, swap_path: Path) -> dict:
    _so, go = load(orig_path)
    _ss, gs = load(swap_path)
    # 原版锚点 / 换值版锚点
    def anchors(gens):
        m = {}
        for g in gens:
            a = g.get("ckf_anchor")
            if a:
                m[(g["topic_id"], g["arm"], g.get("sample"))] = a
        return m
    ao, as_ = anchors(go), anchors(gs)
    idx_o = {(g["topic_id"], g["arm"], g.get("sample")): g for g in go}
    idx_s = {(g["topic_id"], g["arm"], g.get("sample")): g for g in gs}

    rows = []
    for key, go_ in idx_o.items():
        tid, arm, smp = key
        gs_ = idx_s.get(key)
        if not gs_:
            continue
        a_old = ao.get(key, "")
        a_new = as_.get(key, "")
        if not a_old or not a_new:
            continue
        r = M.ckf_swap_synchrony(go_.get("text") or "", gs_.get("text") or "", a_old, a_new)
        if not r.get("applicable"):
            continue
        r.update({"topic_id": tid, "arm": arm, "sample": smp,
                  "anchor_old": a_old, "anchor_new": a_new,
                  "old_in_orig": M.ckf_anchor_hit(go_.get("text") or "", a_old).get("hit"),
                  "new_in_swap": M.ckf_anchor_hit(gs_.get("text") or "", a_new).get("hit")})
        rows.append(r)

    # 汇总
    by_arm = {}
    for r in rows:
        by_arm.setdefault(r["arm"], []).append(r)
    summary = {}
    for arm, rs in by_arm.items():
        n = len(rs)
        summary[arm] = {
            "n": n,
            "sync_rate": round(sum(1 for r in rs if r["synchronized"]) / n, 4) if n else 0.0,
            "new_in_new_rate": round(sum(1 for r in rs if r["new_in_new"]) / n, 4) if n else 0.0,
            "old_in_new_rate": round(sum(1 for r in rs if r["old_in_new"]) / n, 4) if n else 0.0,
            "new_in_orig_rate": round(sum(1 for r in rs if r["new_in_orig"]) / n, 4) if n else 0.0,
            "old_in_orig_rate": round(sum(1 for r in rs if r["old_in_orig"]) / n, 4) if n else 0.0,
        }
    # ---- 统计：各臂 vs 基线 0.5（精确二项）+ 臂间 McNemar（配对）
    stats = {}
    for arm, rs in by_arm.items():
        k = sum(1 for r in rs if r["synchronized"])
        n = len(rs)
        stats[arm] = {"k": k, "n": n,
                      "p_vs_half": binom_test_two_sided(k, n, 0.5)}
    # 臂间 McNemar：按 (题,臂,样本) 配对
    idx = {(r["topic_id"], r["arm"], r["sample"]): r["synchronized"] for r in rows}
    keys = sorted({(r["topic_id"], r["sample"]) for r in rows})
    mcn = {}
    arms_all = sorted(by_arm)
    for i in range(len(arms_all)):
        for j in range(i + 1, len(arms_all)):
            a1, a2 = arms_all[i], arms_all[j]
            b = c = 0
            for tid, smp in keys:
                v1 = idx.get((tid, a1, smp)); v2 = idx.get((tid, a2, smp))
                if v1 is None or v2 is None:
                    continue
                if v1 and v2:
                    b += 1
                elif v1 and not v2:
                    c += 1
            # 还需要 a2-only 的个数
            d = 0
            for tid, smp in keys:
                v1 = idx.get((tid, a1, smp)); v2 = idx.get((tid, a2, smp))
                if v1 is None or v2 is None:
                    continue
                if (not v1) and v2:
                    d += 1
            mcn["%s vs %s" % (a1, a2)] = {"both": b, "a1": a1, "a2": a2,
                                          "only_a1": c, "only_a2": d,
                                          "p": mcnemar_exact(c, d)}
    return {"rows": rows, "summary": summary, "stats": stats, "mcnemar": mcn,
            "topics": sorted({r["topic_id"] for r in rows}),
            "n_pairs": len(rows)}


def report(res: dict) -> str:
    L = []
    L.append("=" * 78)
    L.append("第四组 · D-1 换值同步报告")
    L.append("=" * 78)
    L.append("配对数 %d | 题目 %s" % (res["n_pairs"], ",".join(res["topics"])))
    L.append("")
    L.append("臂      n    同步率   新值进换值版  旧值残留  新值进原版  旧值进原版")
    for arm, s in sorted(res["summary"].items()):
        L.append("%-6s %3d  %6.1f%%   %6.1f%%      %6.1f%%    %6.1f%%     %6.1f%%"
                 % (arm, s["n"], s["sync_rate"] * 100, s["new_in_new_rate"] * 100,
                    s["old_in_new_rate"] * 100, s["new_in_orig_rate"] * 100,
                    s["old_in_orig_rate"] * 100))
    L.append("")
    L.append("")
    L.append("统计（精确二项，各臂 vs 基线 0.5）：")
    for arm, st in sorted(res.get("stats", {}).items()):
        L.append("  %-4s %d/%d 同步   p = %.4f" % (arm, st["k"], st["n"], st["p_vs_half"]))
    if res.get("mcnemar"):
        L.append("")
        L.append("臂间 McNemar 精确检验（配对，同题同样本）：")
        for k, v in sorted(res["mcnemar"].items()):
            L.append("  %-14s 共同同步=%d  仅%s=%d  仅%s=%d   p = %.4f"
                     % (k, v["both"], v["a1"], v["only_a1"], v["a2"], v["only_a2"], v["p"]))
    L.append("")
    L.append("读法：**同步率** = 换值后正文出现新值、不含旧值、且原版不含新值。")
    L.append("      这是「产出由档案内容决定」的**因果**证据；单纯命中率高**不构成证据**。")
    L.append("")
    L.append("逐条：")
    L.append("题     臂    样本  新值进换值版  旧值残留  新值进原版  同步")
    for r in res["rows"]:
        L.append("%-6s %-5s %-5s %-12s %-10s %-10s %s"
                 % (r["topic_id"], r["arm"], r["sample"],
                    "✓" if r["new_in_new"] else "✗",
                    "✓" if r["old_in_new"] else "✗",
                    "✓" if r["new_in_orig"] else "✗",
                    "✔" if r["synchronized"] else "·"))
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("orig")
    ap.add_argument("swap")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    p1 = Path(a.orig); p1 = p1 if p1.is_absolute() else (HERE / p1)
    p2 = Path(a.swap); p2 = p2 if p2.is_absolute() else (HERE / p2)
    res = analyze(p1, p2)
    print(report(res))
    if a.json:
        out = Path(a.json); out = out if out.is_absolute() else (HERE / out)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n[json] -> %s" % out)
