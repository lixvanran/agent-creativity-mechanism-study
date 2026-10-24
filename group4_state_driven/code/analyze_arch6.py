#!/usr/bin/env python3
"""v6 Stage-1 分析：σ/D0 实测 · 排序改变率 · 目标集变化率 · Gate 诊断 · MDE。

零判官。全部读已落盘 jsonl。⚠️ 结论句按证据标签分级输出。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from v6_power import power, mde, sd, D0 as D0_V3, ALPHA   # noqa: E402


def _rank(sc):
    """★ 重算完整排序（**不读记录里的 rank**）。

    ⚠️★ BUG 记录（2026-10-24 13:5x）：三组 `Select.__call__` 里 `if k >= n: return list(range(n))`
    ⇒ ⇒ runner 用 `k=n` 取"完整排序"时**拿到的是原始顺序** ⇒ ⇒ 落盘的 rank 永远是 [1,2,3]
    ⇒ ⇒ ⇒ **"排序改变率=0"是实现假象**。⇒ ⇒ 分析一律**从 scores 重算**，不读落盘 rank。
    """
    return sorted(range(len(sc)), key=lambda i: -float(sc[i]))


def load(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "runs" / "arch6_stage1.jsonl"
    rows = load(src)
    out = HERE / "runs" / "arch6_stage1_analysis.json"

    print("=" * 74)
    print("v6 Stage-1 分析：%s" % src)
    print("=" * 74)
    print("样本行数：%d" % len(rows))
    ok = [r for r in rows if not r.get("error")]
    errs = [r for r in rows if r.get("error")]
    print("  有效 %d / 失败 %d" % (len(ok), len(errs)))
    if errs:
        for r in errs[:6]:
            print("    ✘ %s: %s" % (r.get("tag"), r.get("error")))

    # ── ① 目标集变化率（代价是否真进了状态）
    tc = [r.get("target_changed") for r in ok if r.get("target_changed") is not None]
    tcr = (sum(1 for x in tc if x) / len(tc)) if tc else None
    print("\n── ① 目标集变化率（有代价 ⇒ 状态目标集是否真的变了）")
    print("   n=%d  变化率=%s" % (len(tc), ("%.4f" % tcr) if tcr is not None else "n/a"))

    # ── ② 排序改变率（代价是否改变了选择）
    # ★ RANK_RECOMPUTED：从 scores 重算（落盘的 rank 不可信 ⇒ 见 _rank 的 BUG 记录）
    sq, sn, rq_detail = [], [], []
    for r in ok:
        bs = (r.get("B_state_nocost") or {}).get("scores") or []
        ds = (r.get("D_state_quota") or {}).get("scores") or []
        if not (bs and ds):
            continue
        rb, rd = _rank(bs), _rank(ds)
        changed = bool(rb != rd)
        sq.append(changed)
        rq_detail.append({"tag": r.get("tag"), "rank_B": [i+1 for i in rb],
                          "rank_D": [i+1 for i in rd], "changed": changed})
        # 无代价侧对照：家族最优 rank vs 状态化 B rank
        pg = ((r.get("F_family") or {}).get("per_gate") or {})
        fg = (r.get("F_family") or {}).get("gate")
        if fg and fg in pg and pg[fg].get("rank"):
            fr = pg[fg]["rank"]
            sn.append(bool(list(fr) != [i+1 for i in rb]))
    sn = [x for x in sn if x is not None]
    def _rate(xs):
        return (sum(1 for x in xs if x) / len(xs)) if xs else None
    rq, rn = _rate(sq), _rate(sn)
    print("\n── ② 排序改变率")
    print("   有代价侧（家族最优 F vs 状态化 D）：n=%d  改变率=%s" % (
        len(sq), ("%.4f" % rq) if rq is not None else "n/a"))
    print("   无代价侧（家族最优 F vs 状态化 B）：n=%d  改变率=%s" % (
        len(sn), ("%.4f" % rn) if rn is not None else "n/a"))
    verdict = None
    if rq is not None:
        if rq <= 0.05:
            verdict = ("≈0 ⇒ 代价未接入选择器 ⇒ H1c 机制上不可测 ⇒ "
                       "★ 主动终止并报「代价未接入选择器」（不是『无效应』）")
        elif rq < 0.34:
            verdict = "改变率低 ⇒ 代价接入有限 ⇒ H1c 检出力极低 ⇒ 结论降级为『不可分辨』"
        else:
            verdict = "代价确实改变了排序 ⇒ H1c 可测"
    if verdict:
        print("   ⇒ %s" % verdict)

    # ── ★★ ②b 机制诊断：代价是「常数平移」还是「区分候选」
    #     若代价对所有候选一视同仁地降低 align ⇒ 它只是常数偏移 ⇒ 排序必然不变
    #     ⇒ ⇒ "排序改变率≈0" 的机制解释就在这里（而不是"模型没接入"）。
    shift_var, shift_all = [], []
    dvar, bvar = [], []
    for r in ok:
        bs = (r.get("B_state_nocost") or {}).get("scores") or []
        ds = (r.get("D_state_quota") or {}).get("scores") or []
        if len(bs) == len(ds) and bs:
            sh = [float(d) - float(b) for b, d in zip(bs, ds)]
            shift_all.append(sh)
            if len(sh) > 1:
                shift_var.append(sd(sh))
        if len(bs) > 1:
            bvar.append(sd([float(x) for x in bs]))
        if len(ds) > 1:
            dvar.append(sd([float(x) for x in ds]))
    mean_shift = (sum(sum(sh) for sh in shift_all) / sum(len(sh) for sh in shift_all)) if shift_all else None
    print("\n── ②b ★ 机制诊断：代价是「常数平移」还是「区分候选」")
    print("   代价对 align 的平均改变量 = %s" % ("%.4f" % mean_shift if mean_shift is not None else "n/a"))
    print("   逐候选改变量的方差（样本内）n=%d 均值=%s" % (
        len(shift_var), ("%.6f" % (sum(shift_var) / len(shift_var))) if shift_var else "n/a"))
    print("   ⇒ 方差 ≈ 0 ⇒ **代价是常数平移** ⇒ 排序必然不变（机制结论，非『模型没接入』）")
    print("   状态化尺子区分力：B 档 align 方差均值=%s ／ D 档 align 方差均值=%s" % (
        ("%.4f" % (sum(bvar) / len(bvar))) if bvar else "n/a",
        ("%.4f" % (sum(dvar) / len(dvar))) if dvar else "n/a"))
    print("   ⇒ 两把尺子的区分力都要 > 0，否则 gap 无从解释")

    # ── ★★ ②c 候选池同质率：★ "选择层没有东西可选"的直接量化
    #     若同题同批的候选在"自主声明"上高度同质 ⇒ 两个打分器面对的是一批等价候选
    #     ⇒ ⇒ 任何选择器都只能取第一个 ⇒ ⇒ 排序改变率必然 0
    homo, decl_sets = 0, []
    for r in ok:
        bs = (r.get("B_state_nocost") or {}).get("scores") or []
        if len(bs) > 1:
            if len(set(round(float(x), 6) for x in bs)) == 1:
                homo += 1
    print("\n── ②c ★ 候选池同质率（★ 选择层有没有东西可选）")
    print("   B 档三候选 align **全同**的样本：%d/%d  ⇒ 同质率=%.4f" % (
        homo, len(ok), (homo / len(ok)) if ok else 0))
    print("   ⇒ 同质率高 ⇒ **候选之间没有可区分的差异** ⇒ ⇒ 任何选择器都只能取第一个")
    print("   ⇒ ⇒ 这是「排序改变率=0」的**第三个解释**（既不是『代价没接入』也不是『纯平移』）")

    # ── ③ Gate 诊断（分数方差 / 长度相关性 / 常量检测）
    print("\n── ③ Gate 诊断（★ 恒定性 = 仪器活不活）")
    gate_diag = {}
    for r in ok:
        for g, v in ((r.get("F_family") or {}).get("diag") or {}).items():
            gate_diag.setdefault(g, {"var": [], "len_corr": [], "n": 0, "ok": 0, "const": 0})
            gate_diag[g]["n"] += 1
            gate_diag[g]["ok"] += 1 if v.get("ok") else 0
            gate_diag[g]["const"] += 1 if v.get("constant") else 0
            if v.get("var") is not None:
                gate_diag[g]["var"].append(v["var"])
            if v.get("len_corr") is not None:
                gate_diag[g]["len_corr"].append(v["len_corr"])
    for g, d in sorted(gate_diag.items()):
        vv = d["var"]
        lc = d["len_corr"]
        print("   %-8s 可用 %d/%d  常量 %d  var 均值=%s  与长度相关 r=%s%s" % (
            g, d["ok"], d["n"], d["const"],
            ("%.6f" % (sum(vv) / len(vv))) if vv else "n/a",
            ("%.3f" % (sum(lc) / len(lc))) if lc else "n/a",
            ("  ⚠️ 与长度高度相关 ⇒ 对照端退化为『选最长的』" if lc and abs(sum(lc) / len(lc)) > 0.5 else "")))

    # ── ④ 家族最优选了哪个 Gate
    gates = [(r.get("F_family") or {}).get("gate") for r in ok
             if (r.get("F_family") or {}).get("gate")]
    if gates:
        from collections import Counter
        print("\n── ④ 家族最优选中的 Gate 分布")
        for g, c in Counter(gates).most_common():
            print("   %-10s %d/%d" % (g, c, len(gates)))

    # ── ⑤ σ 实测（状态化打分器在两格上的 gap）
    gaps = []
    for r in ok:
        b = (r.get("B_state_nocost") or {}).get("align")
        d = (r.get("D_state_quota") or {}).get("align")
        if b is not None and d is not None:
            gaps.append(float(d) - float(b))
    s_new = sd(gaps) if len(gaps) > 1 else None
    print("\n── ⑤ σ 实测（有代价 vs 无代价 的状态化 align 差）")
    print("   n=%d  均值=%s  σ_new=%s   （v5 外推值 σ=0.2186 仅作对照）" % (
        len(gaps), ("%.4f" % (sum(gaps) / len(gaps))) if gaps else "n/a",
        ("%.4f" % s_new) if s_new is not None else "n/a"))

    # ── ⑥ MDE 表（用实测 σ）
    mde_tbl = []
    if s_new is not None:
        print("\n── ⑥ 交互项 MDE（用实测 σ_new，双侧 α=%.2f）" % ALPHA)
        print("   %6s %10s %12s" % ("每格n", "MDE(80%)", "power@0.15"))
        for n in (3, 5, 8, 10, 15, 20, 25):
            m = mde(s_new, n)
            pw = power(0.15, s_new, n)
            mde_tbl.append({"n_per_cell": n, "mde80": round(m, 4), "power_delta015": round(pw, 3)})
            print("   %6d %10.4f %12.3f" % (n, m, pw))

    # ── ⑦ 兑现 / 违禁（区间：兑现率下界、违禁率上界）
    def _stats(key):
        fu, vi = [], []
        for r in ok:
            d = r.get(key) or {}
            if d.get("fulfill") is not None:
                fu.append(float(d["fulfill"]))
            if d.get("violation") is not None:
                vi.append(float(d["violation"]))
        return fu, vi
    print("\n── ⑦ 兑现 / 违禁（★ 兑现率是下界、违禁率是上界）")
    ful_tab = {}
    for key, label in (("ful_B", "B 状态化·无代价"), ("ful_D", "D 状态化·有代价"),
                       ("ful_F", "F 家族最优")):
        fu, vi = _stats(key)
        if fu:
            print("   %-18s n=%2d  兑现率下界=%.4f  违禁率上界=%.4f" % (
                label, len(fu), sum(fu) / len(fu), sum(vi) / len(vi) if vi else None))
            ful_tab[key] = {"n": len(fu), "fulfill_lower": round(sum(fu) / len(fu), 4),
                            "violation_upper": round(sum(vi) / len(vi), 4) if vi else None}

    # ── ⑧ 放弃占比（自然产生 vs 配额补足）
    nat = sum(1 for r in ok if (r.get("quota_meta") or {}).get("natural_quota"))
    forced = sum(1 for r in ok if (r.get("quota_meta") or {}).get("quota_forced"))
    print("\n── ⑧ 放弃占比")
    print("   自然产生含放弃：%d/%d   配额补足：%d/%d   ⇒ 自然产生率=%.4f" % (
        nat, len(ok), forced, len(ok), (nat / len(ok)) if ok else 0))

    res = {
        "src": str(src), "n_rows": len(rows), "n_ok": len(ok), "n_err": len(errs),
        "errors": [{"tag": r.get("tag"), "error": r.get("error")} for r in errs],
        "target_change_rate": tcr,
        "candidate_homogeneity_rate": (homo / len(ok)) if ok else None,
        "align_shift_mean": mean_shift,
        "align_shift_var_mean": (sum(shift_var) / len(shift_var)) if shift_var else None,
        "align_var_B": (sum(bvar) / len(bvar)) if bvar else None,
        "align_var_D": (sum(dvar) / len(dvar)) if dvar else None,
        "sel_change_quota_rate": rq, "sel_change_nocost_rate": rn,
        "rank_detail_recomputed": rq_detail,
        "RANK_RECOMPUTED": True,
        "verdict_mechanism": verdict,
        "gate_diag": {g: {"ok": d["ok"], "n": d["n"], "constant": d["const"],
                           "var_mean": (sum(d["var"]) / len(d["var"])) if d["var"] else None,
                           "len_corr_mean": (sum(d["len_corr"]) / len(d["len_corr"])) if d["len_corr"] else None}
                      for g, d in gate_diag.items()},
        "family_gate_counts": {g: gates.count(g) for g in set(gates)} if gates else {},
        "sigma_new": s_new, "sigma_v5_extrapolated": 0.2186,
        "gap_mean": (sum(gaps) / len(gaps)) if gaps else None,
        "mde_table": mde_tbl, "fulfillment": ful_tab,
        "quota_natural": nat, "quota_forced": forced,
        "D0_v3": D0_V3,
    }
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n✔ 已落盘：%s" % out)


if __name__ == "__main__":
    main()
