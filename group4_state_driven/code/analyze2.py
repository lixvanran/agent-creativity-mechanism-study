#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · Phase 0 分析器

═══ 统计纪律（来自第四组裁决，别改）═══
· **分析单元 = 题**，样本 = 题内重复测量。
  绝不能把「同 prompt 跑两次」当配对。
· 每题内先算臂均值，再跨题做配对比较。
· α 按**实际对比数**算（Holm 校正），不硬编码。
· **F18**：若 ≥60% 的题上，被测臂的题内均值落在对照臂的
  `min−s ~ max+s` 噪声包络内 ⇒ 写「**不可分辨**」，
  **不得**写「无效应」（"无效应"与"无检出力"必须分开）。
· 长度必须**报告**，且长度与指标的相关必须查（长度混淆是本项目的经典坑）。
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import metrics2 as M  # noqa: E402
import gates as G      # noqa: E402
import polarity_lexicon as PL  # noqa: E402

try:
    import runner as R
    NEUTRAL = None
except Exception:
    NEUTRAL = None

# S 臂的"状态"是中性简报，覆盖率基线要用它（否则 S 的覆盖率恒为 0，是分析 bug）
S_STATE = {
    "自选极性": "不适用",
    "立场核心": "你是一位以准确为先的写作者，尊重读者的理解力，不替读者下结论。",
    "选它的理由": "因为含糊的代价由读者承担，而清楚的代价由作者承担。",
    "来历": "你写过很多稿子，删掉过大量自己当时很得意、后来觉得站不住的段落。",
    "取舍约束": ["不牺牲具体：宁可写一个真实的细节，不写一句概括的漂亮话。",
                  "不牺牲节奏：允许一处不解释的停顿，不为了顺滑而抹平转折。",
                  "不牺牲分寸：不确定的地方就让它不确定，不替读者把话说满。"],
    "拒绝": "拒绝为了看起来完整而补上自己并不确信的细节。",
    "语气": "克制的。", "强度封顶": "当你发现某个细节明显是为了好听而编的，就把它删掉。",
    "锚定问题": "这一稿里哪一句是真正有代价的？",
}


# ---------------------------------------------------------------- 统计工具
def holm(pvals: dict, alpha: float = 0.05) -> dict:
    """Holm-Bonferroni 校正。返回 {key: (p_raw, p_adj, reject)}。"""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out = {}
    for i, (k, p) in enumerate(items):
        adj = min(1.0, p * (m - i))
        out[k] = (p, adj, adj < alpha)
    return out


def paired_t(xs: list, ys: list) -> dict:
    """配对 t 检验（题为配对单元）。样本太少时明确说不可用。"""
    d = [a - b for a, b in zip(xs, ys)]
    n = len(d)
    if n < 3:
        return {"n": n, "mean_diff": (sum(d) / n if n else None), "p": None,
                "note": "题数 n<3，检验不可用；只报描述统计"}
    mu = sum(d) / n
    sd = st.stdev(d)
    se = sd / math.sqrt(n)
    if se == 0:
        t = 0.0 if mu == 0 else float("inf")
        p = 1.0 if mu == 0 else 0.0
    else:
        t = mu / se
        # 双尾 p：用不完全 beta 近似（避免引入 scipy）
        p = _t_sf2(t, n - 1)
    return {"n": n, "mean_diff": round(mu, 4), "sd_diff": round(sd, 4),
            "t": round(t, 3) if math.isfinite(t) else None, "p": p,
            "cohen_dz": round(mu / sd, 3) if sd else None,
            "note": "" if n >= 5 else "题数 n<5，功效很低，只能当方向性观察"}


def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 200, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def _betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1 - x))
    bt = math.exp(lbeta)
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def _t_sf2(t, df):
    """双尾 p 值。"""
    if t is None or not math.isfinite(t):
        return 0.0 if (t and abs(t) == float("inf")) else 1.0
    x = df / (df + t * t)
    return _betai(df / 2.0, 0.5, x)


def noise_envelope(values: list, s_mult: float = 1.0) -> tuple:
    """对照臂的噪声包络 (min−s, max+s)。"""
    if not values:
        return (None, None)
    s = st.stdev(values) if len(values) > 1 else 0.0
    return (min(values) - s_mult * s, max(values) + s_mult * s)


# ---------------------------------------------------------------- 主分析
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


def analyze(path: Path) -> dict:
    stances, gens = load(path)
    by_tid = {}
    for g in gens:
        by_tid.setdefault(g["topic_id"], []).append(g)

    rows = []
    for g in gens:
        arm, tid, txt = g["arm"], g["topic_id"], g.get("text") or ""
        if arm in ("C0", "C1", "C2"):
            sp = (stances.get((tid, "C0")) or {}).get("stance_profile")
        elif arm == "R1":
            sp = (stances.get((tid, "R1")) or {}).get("stance_profile")
        elif arm == "S":
            sp = S_STATE
        elif arm == "R0":
            try:
                import runner2 as _R2
                sp = _R2.R0_STATE
            except Exception:
                sp = None
        else:
            sp = None
        anchor = g.get("ckf_anchor") or ""
        topic = next((t for t in R.TOPICS if t["id"] == tid), {"id": tid, "genre": ""}) \
            if "R" in dir() else {"id": tid, "genre": ""}
        try:
            import runner as _R
            topic = next((t for t in _R.TOPICS if t["id"] == tid), {"id": tid, "genre": ""})
        except Exception:
            pass
        # 极性分（人工盲标词表，零判官）
        pol = PL.polarity_score(txt, tid)
        _sp = None
        # ★ analyze2 的 stances 存的是**整条记录**（不是 stance_profile）⇒ 路径不同
        if arm in ("C0", "C1", "C2"):
            _sp = ((stances.get((tid, "C0")) or {}).get("stance_profile") or {}).get("self_polarity")
        elif arm == "R1":
            _sp = ((stances.get((tid, "R1")) or {}).get("stance_profile") or {}).get("self_polarity")
        rec_pol = {"polarity": pol.get("score"),
                   "polarity_aligned": PL.align(pol.get("score", 0.0), _sp),
                   "self_polarity": _sp}
        gt = G.run_gates(txt, topic)
        rec_gate = {"genre_drift": bool(gt["genre_gate"].get("drift")),
                    "subject_drift": bool(gt["subject_gate"].get("drift")),
                    "any_drift": bool(gt["any_drift"]),
                    "genre_markers": gt["genre_gate"].get("markers", [])[:4],
                    "meta_markers": gt["subject_gate"].get("meta_markers", [])[:3],
                    "subjects_present": gt["subject_gate"].get("present", [])}
        rec = {
            "topic_id": tid, "arm": arm, "sample": g.get("sample"),
            "len": len(txt), "batch_id": g.get("batch_id"),
            "ckf_anchor": anchor,
            "ckf_hit": (M.ckf_anchor_hit(txt, anchor).get("hit") if anchor else None),
        }
        if sp:
            d3 = M.d3_scores(txt, sp)
            rec["coverage"] = d3["coverage"]["cov_text"]
            rec["cov_archive"] = d3["coverage"]["cov_archive"]
            rec["hit_constraints"] = d3["hit_constraints"]
            rec["hit_reject"] = d3["hit_reject"]
            rec["diff"] = d3["diff"]
        # D-2 状态转移（C1/S/R1 有中间态）
        steps = (g.get("mid") or {}).get("steps") or []
        f = next((s for s in steps if s.get("step") == "f"), None)
        gg = next((s for s in steps if s.get("step") == "g"), None)
        if f and gg:
            t = M.transfer_sensitivity(f.get("constraints") or [], gg.get("constraints") or [])
            rec["transfer_jaccard"] = t["jaccard"]
            rec["transfer_changed"] = t["changed"]
            rec["transfer_fallback"] = bool(gg.get("constraints_fallback"))
            rec["n_facts"] = len(gg.get("facts") or [])
            rec["n_excluded"] = len(gg.get("excluded") or [])
            rec["has_polarity_anchor"] = bool(gg.get("polarity"))
            rec["has_facts_hint"] = bool(gg.get("facts_hint"))
            # ★ C2 专属：已排除选项在终稿里是否真的消失了
            draft = next((x.get("draft") for x in (g.get("mid") or {}).get("steps") or []
                          if x.get("step") == "write"), "")
            fin = next((x.get("text") for x in (g.get("mid") or {}).get("steps") or []
                        if x.get("step") == "final"), "")
            ex = gg.get("excluded") or []
            sup = M.excluded_suppression(draft or "", fin or "", ex)
            if sup.get("applicable"):
                rec["excl_hit_draft"] = sup["hit_draft"]
                rec["excl_hit_final"] = sup["hit_final"]
                rec["excl_suppressed"] = sup["suppressed"]
                rec["excl_suppressed_ok"] = sup["suppressed_ok"]
            rec["n_cons_f"] = len(f.get("constraints") or [])
            rec["n_cons_g"] = len(gg.get("constraints") or [])
        rec.update(rec_gate); rec.update(rec_pol)
        # ★ 产出健康度：复述率（覆盖率读数是否可信）＋ 语言漂移
        if sp:
            rec["repetition"] = M.repetition_ratio(txt, sp)
        rec["lang_drift"] = bool(M.language_drift(txt).get("drift"))
        rows.append(rec)

    # ---- 题内均值
    metrics = ["len", "coverage", "cov_archive", "hit_constraints", "diff", "ckf_hit",
               "polarity", "polarity_aligned", "n_excluded", "excl_hit_draft",
               "excl_hit_final", "excl_suppressed", "repetition",
               "transfer_jaccard", "transfer_changed", "n_facts"]
    tids = sorted(by_tid)
    arms = sorted({r["arm"] for r in rows})
    cell = {}   # (tid, arm, metric) -> 题内均值
    for tid in tids:
        for arm in arms:
            sub = [r for r in rows if r["topic_id"] == tid and r["arm"] == arm]
            if not sub:
                continue
            for mt in metrics:
                vs = [r[mt] for r in sub if r.get(mt) is not None]
                if vs:
                    cell[(tid, arm, mt)] = sum(vs) / len(vs)
                    cell[(tid, arm, mt + "_n")] = len(vs)

    # ---- 对比
    contrasts = []
    # ★ 对**每一个多步状态机臂**都做主对比（C1 是历史对照，C2 是本轮主角）
    for TEST in [t for t in ("C2", "C1") if t in arms]:
        for other in [a for a in ("C0", "A", "S", "R1") if a in arms]:
            for mt in ("coverage", "cov_archive", "hit_constraints", "ckf_hit", "len",
                   "polarity", "polarity_aligned", "n_excluded",
                   "excl_hit_draft", "excl_hit_final", "excl_suppressed", "repetition"):
                xs, ys = [], []
                for tid in tids:
                    a1 = cell.get((tid, TEST, mt))
                    a2 = cell.get((tid, other, mt))
                    if a1 is not None and a2 is not None:
                        xs.append(a1); ys.append(a2)
                if len(xs) < 2:
                    continue
                tt = paired_t(xs, ys)
                contrasts.append({"contrast": "%s - %s" % (TEST, other), "metric": mt, **tt})
        # D-2 只在多步臂之间比（swap_jaccard 的正式对比见 swap_contrasts）
        for other in [a for a in ("S", "R1") if a in arms]:
            for mt in ("n_facts", "n_excluded", "excl_suppressed"):
                xs, ys = [], []
                for tid in tids:
                    a1 = cell.get((tid, "C2", mt)); a2 = cell.get((tid, other, mt))
                    if a1 is not None and a2 is not None:
                        xs.append(a1); ys.append(a2)
                if len(xs) < 2:
                    continue
                contrasts.append({"contrast": "C2 - %s" % other, "metric": mt, **paired_t(xs, ys)})

    # Holm 校正
    withp = {("%s|%s" % (c["contrast"], c["metric"])): c["p"] for c in contrasts if c.get("p") is not None}
    adj = holm(withp) if withp else {}
    for c in contrasts:
        key = "%s|%s" % (c["contrast"], c["metric"])
        if key in adj:
            c["p_raw"], c["p_adj"], c["reject_holm"] = adj[key]

    # ---- H4：C2 的「已排除选项抑制」题内均值 vs 0（单样本配对 t）
    h4 = None
    if "C2" in arms:
        vs = [cell.get((tid, "C2", "excl_suppressed")) for tid in tids]
        vs = [v for v in vs if v is not None]
        if len(vs) >= 3:
            tt = paired_t(vs, [0.0] * len(vs))
            h4 = {"metric": "excl_suppressed", "n": len(vs),
                  "mean": round(sum(vs) / len(vs), 4), **tt}

    # ---- F18 噪声包络：C1 题内均值是否落在 A 臂包络内
    f18 = {}
    for TESTF in [t for t in ("C2", "C1") if t in arms]:
      if "A" in arms:
        for mt in ("coverage", "cov_archive", "hit_constraints", "ckf_hit"):
            inside = 0
            tot = 0
            detail = []
            for tid in tids:
                av = [r[mt] for r in rows if r["topic_id"] == tid and r["arm"] == "A" and r.get(mt) is not None]
                cv = cell.get((tid, "C1", mt))
                if not av or cv is None:
                    continue
                lo, hi = noise_envelope(av)
                tot += 1
                ok = (lo is not None and lo <= cv <= hi)
                inside += 1 if ok else 0
                detail.append({"topic": tid, "C1": round(cv, 4),
                               "A_env": [round(lo, 4), round(hi, 4)], "inside": bool(ok)})
            if tot:
                ratio = inside / tot
                f18[mt] = {"n_topics": tot, "inside": inside, "ratio": round(ratio, 3),
                           "verdict": ("不可分辨（C1 落在 A 臂噪声包络内的题占比 %.0f%%）" % (ratio * 100))
                           if ratio >= 0.6 else "可分辨",
                           "detail": detail}

    # ---- 长度混淆检查：长度与各指标的相关
    len_corr = {}
    for mt in ("coverage", "cov_archive", "hit_constraints", "ckf_hit"):
        xs = [r["len"] for r in rows if r.get(mt) is not None]
        ys = [r[mt] for r in rows if r.get(mt) is not None]
        if len(xs) >= 3:
            len_corr[mt] = round(_pearson(xs, ys), 3)

    # ---- D-2 置换探针（读 <same>.swap.jsonl）
    swap = []
    sp = path.with_suffix(".swap.jsonl")
    if sp.exists():
        for line in sp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("kind") == "probe_swap":
                swap.append(r)
    swap_cell = {}
    for arm in sorted({r["arm"] for r in swap}):
        for tid in tids:
            vs = [r["swap_jaccard"] for r in swap if r["arm"] == arm and r["topic_id"] == tid]
            if vs:
                swap_cell[(tid, arm)] = sum(vs) / len(vs)
    swap_contrasts = []
    # ★ 对每个多步臂都做，且**必须用 swap_cell**（置换探针的数据），
    #   不能用 cell 里的 transfer_jaccard（那是「约束① vs 约束②」，
    #   两个不同步骤的产物，jaccard 低是平凡的 ⇒ 无效判据）。
    for TEST in [t for t in ("C2", "C1") if t in arms]:
        for other in [a for a in ("S", "R1", "C0") if a in arms and a != TEST]:
            xs, ys = [], []
            for tid in tids:
                a1 = swap_cell.get((tid, TEST)); a2 = swap_cell.get((tid, other))
                if a1 is not None and a2 is not None:
                    xs.append(a1); ys.append(a2)
            if len(xs) >= 2:
                swap_contrasts.append({"contrast": "%s - %s" % (TEST, other),
                                        "metric": "swap_jaccard", **paired_t(xs, ys)})
    if swap_contrasts:
        withp = {"%s|%s" % (c["contrast"], c["metric"]): c["p"] for c in swap_contrasts if c.get("p") is not None}
        adj = holm(withp) if withp else {}
        for c in swap_contrasts:
            k = "%s|%s" % (c["contrast"], c["metric"])
            if k in adj:
                c["p_raw"], c["p_adj"], c["reject_holm"] = adj[k]

    # 批次混用检测：同一 (题, 臂) 的样本是否来自不同批
    batch_by_cell = {}
    for r in rows:
        batch_by_cell.setdefault((r["topic_id"], r["arm"]), set()).add(r.get("batch_id"))
    mixed = {k: sorted(v) for k, v in batch_by_cell.items() if len(v) > 1}

    return {"file": str(path), "n_gen": len(gens), "topics": tids, "arms": arms,
            "mixed_batches": mixed, "h4": h4,
            "swap_cell": {"%s|%s" % k: v for k, v in swap_cell.items()},
            "swap_contrasts": swap_contrasts, "n_swap": len(swap),
            "rows": rows, "cell": {"%s|%s|%s" % k: v for k, v in cell.items()},
            "contrasts": contrasts, "f18": f18, "len_corr": len_corr,
            "batches": sorted({r.get("batch_id") for r in rows if r.get("batch_id")})}


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return num / (dx * dy) if dx and dy else 0.0


def report(res: dict) -> str:
    L = []
    L.append("=" * 78)
    L.append("第四组 · Phase 0 分析报告")
    L.append("=" * 78)
    L.append("文件: %s" % res["file"])
    L.append("产出 %d 篇 | 题目 %s | 臂 %s" % (res["n_gen"], ",".join(res["topics"]), ",".join(res["arms"])))
    nb = len(res["batches"])
    if nb == 1:
        L.append("批: %s  ✔ 全部同批（题内跨臂比较有效）" % res["batches"][0])
    else:
        L.append("批: %s  ⚠ **跨 %d 批**——题内跨臂比较**不得**直接使用" % (", ".join(res["batches"]), nb))
    L.append("      （依据：embedding 绝对距离跨批差 3.9 倍；几何量一律不可跨批比）")
    L.append("")
    if res.get("mixed_batches"):
        L.append("⚠ **批次混用**：%d 个 (题,臂) 单元的样本跨批次 ⇒ 相关比较作废" % len(res["mixed_batches"]))
        for k, v in list(res["mixed_batches"].items())[:6]:
            L.append("    %s/%s → %s" % (k[0], k[1], v))
    L.append("")
    L.append("── 描述统计（题内均值 → 跨题汇总）──")
    arms = res["arms"]
    hdr = "指标".ljust(22) + "".join(a.rjust(12) for a in arms)
    L.append(hdr)
    for mt in ("len", "coverage", "cov_archive", "hit_constraints", "ckf_hit",
               "polarity", "polarity_aligned", "transfer_jaccard", "n_facts",
               "n_excluded", "excl_hit_draft", "excl_hit_final", "excl_suppressed",
               "repetition"):
        line = mt.ljust(22)
        for a in arms:
            vs = [v for k, v in res["cell"].items() if k.endswith("|%s|%s" % (a, mt))]
            line += ("%.4f" % (sum(vs) / len(vs))).rjust(12) if vs else "—".rjust(12)
        L.append(line)
    L.append("")
    L.append("── 对比（分析单元=题，配对）──")
    if res["contrasts"]:
        L.append("对比".ljust(26) + "指标".ljust(18) + "Δ".rjust(10) + "n".rjust(4)
                 + "p_raw".rjust(9) + "p_adj".rjust(9) + "判定".rjust(10))
        for c in res["contrasts"]:
            L.append((c["contrast"] + " vs").ljust(26) + c["metric"].ljust(18)
                     + ("%.4f" % c["mean_diff"]).rjust(10) + str(c["n"]).rjust(4)
                     + ("%.4f" % c["p_raw"] if c.get("p_raw") is not None else "—").rjust(9)
                     + ("%.4f" % c["p_adj"] if c.get("p_adj") is not None else "—").rjust(9)
                     + ("显著" if c.get("reject_holm") else "不显著").rjust(10))
            if c.get("note"):
                L.append("    ⚠ " + c["note"])
    else:
        L.append("（题数不足，无法做对比检验）")
    L.append("")
    L.append("── D-2 状态历史置换敏感度（jaccard 越小 = 越依赖历史）──")
    if res.get("n_swap"):
        sw = res["swap_cell"]
        arms2 = sorted({k.split("|")[1] for k in sw})
        L.append("  题".ljust(8) + "".join(a.rjust(10) for a in arms2))
        for tid in res["topics"]:
            line = "  " + tid.ljust(6)
            for a in arms2:
                v = sw.get("%s|%s" % (tid, a))
                line += ("%.4f" % v).rjust(10) if v is not None else "—".rjust(10)
            L.append(line)
        for c in res.get("swap_contrasts", []):
            L.append("  %s swap_jaccard Δ=%+.4f n=%d p_raw=%s p_adj=%s ⇒ %s"
                     % (c["contrast"], c["mean_diff"], c["n"],
                        ("%.4f" % c["p_raw"]) if c.get("p_raw") is not None else "—",
                        ("%.4f" % c["p_adj"]) if c.get("p_adj") is not None else "—",
                        "显著" if c.get("reject_holm") else "不显著"))
    else:
        L.append("  （无置换探针数据）")
    L.append("")
    L.append("── 极性反号检验（人工盲标词表）──")
    def _al(arm, tid):
        vs = [r["polarity_aligned"] for r in res["rows"]
              if r["arm"] == arm and r["topic_id"] == tid and r.get("polarity_aligned") is not None]
        return sum(vs) / len(vs) if vs else None
    tids2 = res["topics"]
    for TEST in [t for t in ("C2", "C1") if t in res["arms"]]:
        L.append("  【%s】题  %s  | 与C0同号? 与R1反号?" % (TEST, "C0".ljust(8)))
        ok_same = ok_opp = 0
        for tid in tids2:
            c0 = _al("C0", tid); ct = _al(TEST, tid); r1 = _al("R1", tid)
            if c0 is None or ct is None:
                continue
            same = (c0 * ct) > 0
            opp = (ct * r1) < 0 if r1 is not None else None
            ok_same += 1 if same else 0
            ok_opp += 1 if (opp is True) else 0
            L.append("  %-6s %s %s %s | %-9s %s"
                     % (tid, ("%+.3f" % c0), ("%+.3f" % ct),
                        ("%+.3f" % r1) if r1 is not None else "  —  ",
                        "是" if same else "★否",
                        ("是" if opp else "★否") if opp is not None else "—"))
        L.append("  ⇒ %s 与 C0 同号 %d/%d 题 | 与 R1 反号 %d/%d 题"
                 % (TEST, ok_same, len(tids2), ok_opp, len(tids2)))
        L.append("")
    L.append("── H4 · C2「已排除选项抑制」题内均值 vs 0 ──")
    h4 = res.get("h4")
    if h4:
        _p = h4.get("p")
        L.append("  mean=%+.4f  n=%d  p=%s  ⇒ %s"
                 % (h4["mean"], h4["n"],
                    ("%.4f" % _p) if _p is not None else "—",
                    "**抑制成立**" if (_p is not None and _p < 0.05 and h4["mean"] > 0)
                    else "未达显著"))
        L.append("  （C1 / S / C0 **结构上没有**「已排除」这个量 ⇒ 该判据无法被提示词伪造）")
    else:
        L.append("  （数据不足）")
    L.append("")
    L.append("── F18 噪声包络（C1 vs A）──")
    if res["f18"]:
        for mt, f in res["f18"].items():
            L.append("  %-18s 落在包络内 %d/%d（%.0f%%）⇒ %s"
                     % (mt, f["inside"], f["n_topics"], f["ratio"] * 100, f["verdict"]))
    else:
        L.append("  （数据不足）")
    L.append("")
    L.append("── 产出健康度（复述率 / 语言漂移）──")
    for arm in res["arms"]:
        sub = [r for r in res["rows"] if r["arm"] == arm]
        if not sub:
            continue
        reps = [r["repetition"] for r in sub if r.get("repetition") is not None]
        ld = sum(1 for r in sub if r.get("lang_drift"))
        L.append("  %-4s 复述率 %s   语言漂移 %d/%d" % (
            arm, ("%.4f" % (sum(reps) / len(reps))) if reps else "—", ld, len(sub)))
    L.append("  ★ 复述率高 ⇒ 该臂的「覆盖率」读数**不可与其它臂直接比较**（那是复述，不是使用）")
    L.append("")
    L.append("── 体裁 / 对象守恒门筛查（multi-mind 失败模式）──")
    for arm in res["arms"]:
        sub = [r for r in res["rows"] if r["arm"] == arm]
        if not sub:
            continue
        gd = sum(1 for r in sub if r.get("genre_drift"))
        sd = sum(1 for r in sub if r.get("subject_drift"))
        ad = sum(1 for r in sub if r.get("any_drift"))
        L.append("  %-4s 体裁漂移 %d/%d   对象漂移 %d/%d   任一 %d/%d"
                 % (arm, gd, len(sub), sd, len(sub), ad, len(sub)))
    L.append("")
    L.append("── 长度混淆检查（长度与指标的 Pearson r）──")
    for mt, r in res["len_corr"].items():
        flag = "  ⚠ 需做长度校正" if abs(r) > 0.3 else ""
        L.append("  %-18s r = %+.3f%s" % (mt, r, flag))
    L.append("")
    L.append("── 判据自检 ──")
    st = M.selftest(verbose=False)
    L.append("  %s（%d/%d）" % ("全部通过" if st["all_pass"] else "有未通过",
                              sum(v["pass"] for v in st["cases"].values()), len(st["cases"])))
    return "\n".join(L)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="runs/phase0.jsonl")
    ap.add_argument("--json", default="", help="同时输出 JSON 到该路径")
    a = ap.parse_args()
    p = Path(a.path)
    p = p if p.is_absolute() else (HERE / p)
    res = analyze(p)
    print(report(res))
    if a.json:
        out = Path(a.json)
        out = out if out.is_absolute() else (HERE / out)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n[json] -> %s" % out)
