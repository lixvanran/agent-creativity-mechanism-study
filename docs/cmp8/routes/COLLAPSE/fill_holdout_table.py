# -*- coding: utf-8 -*-
"""★ 门2：留出集出表器【可插拔】（fill_paper_v2 范式）

★ 为什么可插拔：
  · 读数没到齐也能跑（--allow-partial）⇒ 每次跑批增量都能出一次表
  · 表头永远标【已跑批·部分 n=X/目标】⇒ 读者不会把半批当全批
  · 必需量算不出来 ⇒ SystemExit（不许留空、不许填 0、不许事后手补）

★ 判读顺序【写死】（与 PREREG-HOLDOUT-2026-10-24 一致）：
  ① 分母是否相等 → ② 负对照是否平 → ③ 差值 → ④ 题内 rep σ
  → ⑤ W 臂 → ⑥ A05 题级明细 → ⑦ 判官状态
  ★ ② 不过 ⇒ 只报读数 + 噪声地板，不报"架构更优"。

★ 每个数字都带：绝对分母 n、来源文件路径。
★ 结论句由本脚本生成 ⇒ 标【产出方自算】。

用法:
  python3 fill_holdout_table.py                       # 默认目录，自动 partial
  python3 fill_holdout_table.py --expect 48 --strict  # 不足 48 直接 SystemExit
  python3 fill_holdout_table.py --inject PAPER.md     # 同时注入论文占位块
"""
import argparse
import io
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import premature_closure as PC   # noqa: E402
import space as SP               # noqa: E402
import metrics_priorart as MP    # noqa: E402

STRATEGIES = ("merged13", "lookup", "uniform")
ARMS = ("B0_direct", "B0_bestof3", "W_train_L3")
NEG_ARMS = ("B0_direct", "B0_bestof3")
TASKS = ("A02", "A05")


def die(msg):
    raise SystemExit("✘ " + msg)


def load_rows(d, strategy):
    """读一个策略臂的全部读数；文件不存在 ⇒ 返回 []（不是错误：允许部分）"""
    p = os.path.join(d, "valid_%s" % strategy, "arms.jsonl")
    if not os.path.exists(p):
        return [], p
    rows = []
    for i, line in enumerate(io.open(p, encoding="utf-8")):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception as e:
            die("读数文件 %s 第 %d 行 JSON 解析失败（%s）⇒ 停止，不静默跳过" % (p, i + 1, e))
    return rows, p


def cell_stats(rs):
    """一批读数（同一 task+arm）⇒ 汇总量。

    ★★ 三种"缺失"必须分开（本脚本的核心纪律）：
      ① 失败单元：n_cards is None ⇒ ★ 判官/生成整段没跑出东西
         ⇒ 【计为失败】+ 【不进统计分母】+ 【每表显式报失败数】⇒ 绝不记 0、绝不静默丢
      ② 仪器层零：n_cards == 0 且 n_load_bearing == 0 ⇒ ★ 判官跑了但没解析出卡片
         ⇒ 这是【有效读数】，与 ① 分开统计
      ③ 内容层空：n_cards > 0 且 n_load_bearing == 0 ⇒ 有效读数，卡片都在但没有承重的
    """
    if not rs:
        return None
    failed = [r for r in rs if r.get("n_cards") is None]
    good = [r for r in rs if r.get("n_cards") is not None]
    if not good:
        return dict(n=0, n_fail=len(failed), n_total=len(rs), lb_median=None, lb_sd=None,
                    lb_vals=[], dm_median=None, dm_sd=None, dm_vals=[],
                    pc_hit=0, pc_n=0, sim_median=None, sim_n=0,
                    zero_inst=0, parsefail_pos=0, calls=0, judge_models=[], same_vendor=[])
    lb = [r.get("n_load_bearing") for r in good]
    if any(x is None for x in lb):
        die("有效读数里 n_load_bearing 仍缺失 ⇒ 停止（不许留空/填0）")
    # ★★ 主指标 = n_dims（有效信息维度数）★★
    #   负责人裁定（2026-10-24）："思维面" = 有效信息维度数 ⇒ n_dims 才是主读数。
    #   ⚠ 既有《三策略表.txt》里标着"承重维度中位"的那一列实际取的是 n_dims
    #     ⇒ 本脚本【两个都报】，并把 n_dims 标为主指标，避免口径混淆。
    dm = [r.get("n_dims") for r in good]
    if any(x is None for x in dm):
        die("有效读数里 n_dims 仍缺失 ⇒ 停止（不许留空/填0）")
    hit = [bool((r.get("pc") or {}).get("hit")) for r in good]
    sims = []
    for r in good:
        ps = [p for p in (r.get("paths") or []) if p.get("claims")]
        if len(ps) >= 2:
            s = SP.MP.self_sim([list(p["claims"]) for p in ps], mode="bigram")
            if s is not None:
                sims.append(s)
    zero_inst = sum(1 for r in good if (r.get("n_cards") or 0) == 0)
    pf = [r.get("parsefail_rate") for r in good]
    return dict(
        n=len(good), n_fail=len(failed), n_total=len(rs),
        lb_median=statistics.median(lb),
        lb_sd=(statistics.stdev(lb) if len(lb) >= 2 else 0.0),
        lb_vals=lb,
        dm_median=statistics.median(dm),
        dm_sd=(statistics.stdev(dm) if len(dm) >= 2 else 0.0),
        dm_vals=dm,
        pc_hit=sum(hit), pc_n=len(hit),
        sim_median=(statistics.median(sims) if sims else None),
        sim_n=len(sims),
        zero_inst=zero_inst,
        parsefail_pos=sum(1 for x in pf if x),
        calls=sum(c for c in (r.get("calls") for r in good) if isinstance(c, int)),
        judge_models=sorted({r.get("judge_model") for r in good if r.get("judge_model")}),
        same_vendor=sorted({r.get("judge_same_vendor") for r in good if r.get("judge_same_vendor") is not None}),
    )


def fmt(x, nd=2, dash="—"):
    if x is None:
        return dash
    return ("%." + str(nd) + "f") % x


def build(d, expect):
    """⇒ 收集全部读数 + 分母统计。★ 不做任何判读结论。"""
    data = {}
    for st in STRATEGIES:
        rows, path = load_rows(d, st)
        by = {}
        for r in rows:
            tid = r.get("task_id")
            arm = r.get("arm")
            if tid is None or arm is None:
                die("读数缺 task_id/arm ⇒ 停止：%s" % path)
            by.setdefault((tid, arm), []).append(r)
        data[st] = dict(path=path, total=len(rows), by=by)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout-dir", default=os.path.join(HERE, "runs", "holdout13"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--expect", type=int, default=48)
    ap.add_argument("--strict", action="store_true", help="不足 expect 直接 SystemExit")
    ap.add_argument("--inject", default=None, help="同时注入该 md 文件的占位块")
    a = ap.parse_args()

    d = a.holdout_dir
    data = build(d, a.expect)
    tot = {st: data[st]["total"] for st in STRATEGIES}
    full = all(v >= a.expect for v in tot.values())
    partial = [st for st in STRATEGIES if tot[st] < a.expect]

    if a.strict and not full:
        die("读数未到齐（%s）且 --strict ⇒ 停止" %
            ", ".join("%s=%d/%d" % (st, tot[st], a.expect) for st in STRATEGIES))

    tag = ("【已跑批·全量 n=%d/%d】" % (a.expect, a.expect)) if full else \
          ("【已跑批·部分 n=%s】" % " / ".join("%s=%d/%d" % (st, tot[st], a.expect) for st in STRATEGIES))
    if partial:
        tag += "　★ 未跑满 ⇒ 缺份是【单元尚未生成】，不是解析失败（分母不等时只报读数 + 噪声地板）"

    L = []
    P = L.append
    P("### 留出集出表（%s）" % tag)
    P("")
    P("> 来源目录：`%s`　｜　★ 判读顺序：分母 → 负对照 → 差值 → 题内 rep σ → W 臂 → A05 题级 → 判官状态" % d)
    P("> ★ 全部数字由 `routes/COLLAPSE/fill_holdout_table.py` 从 `arms.jsonl` 直接计算，**无手写、无占位符**。")
    P("")

    # ── ① 分母 ──────────────────────────────────────────────
    P("**① 分母（绝对分母，先相等才继续）**")
    P("")
    P("| 策略 | 文件 | 总份数 | A02: B0_direct / B0_bestof3 / W_train_L3 | A05: B0_direct / B0_bestof3 / W_train_L3 | 分母齐? |")
    P("|---|---|--:|---|---|:--:|")
    denoms = {}
    for st in STRATEGIES:
        by = data[st]["by"]
        cells = []
        per = []
        for t in TASKS:
            row = []
            for arm in ARMS:
                k = (t, arm)
                row.append(len(by.get(k, [])))
            per.append(row)
            cells.append(" / ".join(str(x) for x in row))
        denoms[st] = per
        # 齐 = 每题三臂 rep 数相等 且 三臂之间相等
        ok = all(len(set(r)) == 1 for r in per) and all(r[0] == r[1] == r[2] for r in per)
        P("| %s | `%s` | %d | %s | %s | %s |" %
          (st, os.path.relpath(data[st]["path"], HERE), tot[st], cells[0], cells[1], "✔" if ok else "✘"))
    P("")
    P("> ★ 判官状态：%s" % judge_status(data))
    P("")

    # ── ② 负对照 ────────────────────────────────────────────
    P("**② 负对照是否平（B0_direct / B0_bestof3）**")
    P("")
    P("| 策略 | 臂 | 题 | n(有效) | 失败单元 | **有效信息维度数中位(主)** | 题内 rep σ(主) | 承重卡片数中位 | 钻牛角尖 | 路径 Self-Sim 中位 |")
    P("|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    neg_rows = {}
    for st in STRATEGIES:
        by = data[st]["by"]
        for arm in NEG_ARMS:
            for t in TASKS:
                rs = by.get((t, arm), [])
                if not rs:
                    P("| %s | %s | %s | 0 | 0 | **缺** | — | — | — | — |" % (st, arm, t))
                    continue
                s = cell_stats(rs)
                neg_rows[(st, arm, t)] = s
                P("| %s | %s | %s | %d | %d | %s | %s | %s | %d/%d | %s |" %
                  (st, arm, t, s["n"], s["n_fail"], fmt(s["dm_median"]), fmt(s["dm_sd"]),
                   fmt(s["lb_median"]), s["pc_hit"], s["pc_n"], fmt(s["sim_median"], 3)))
    P("")
    P("> ★ **主读数 = `n_dims`（有效信息维度数）**：负责人 2026-10-24 裁定「思维面」= 有效信息维度数。")
    P("> ★ `n_load_bearing`（承重卡片数）为**辅助**读数；⚠ 既有《三策略表.txt》标「承重维度中位」的那列实际取的是 `n_dims` ⇒ 两表不可混引。")
    P("")

    # ── ③ 差值 + ④ 题内 rep σ ───────────────────────────────
    P("**③ 差值（W_train_L3 − 负对照）与 ④ 题内 rep σ**")
    P("")
    P("| 策略 | 题 | 对照臂 | **Δ有效信息维度数中位** | Δ钻牛角尖 | 题内 σ(对照,主) | 题内 σ(W,主) | 差值/合并σ | 判读 |")
    P("|---|---|---|--:|--:|--:|--:|--:|---|")
    diffs = {}
    for st in STRATEGIES:
        by = data[st]["by"]
        for t in TASKS:
            wrs = by.get((t, "W_train_L3"), [])
            if not wrs:
                P("| %s | %s | — | **缺** | — | — | — | — | 不可读（W 臂无读数）|" % (st, t))
                continue
            w = cell_stats(wrs)
            if w["n"] == 0:
                P("| %s | %s | — | **缺** | — | — | — | — | 不可读（W 臂 %d 份全失败，**不记 0**）|" % (st, t, w["n_fail"]))
                continue
            for arm in NEG_ARMS:
                rs = by.get((t, arm), [])
                if not rs:
                    P("| %s | %s | %s | **缺** | — | — | — | — | 不可读（对照无读数）|" % (st, t, arm))
                    continue
                c = cell_stats(rs)
                if c["n"] == 0:
                    P("| %s | %s | %s | **缺** | — | — | — | — | 不可读（对照 %d 份全失败，**不记 0**）|" % (st, t, arm, c["n_fail"]))
                    continue
                dlb = w["dm_median"] - c["dm_median"]
                dpc = (w["pc_hit"] / w["pc_n"]) - (c["pc_hit"] / c["pc_n"])
                pooled = ((c["dm_sd"] ** 2 / max(c["n"], 1)) + (w["dm_sd"] ** 2 / max(w["n"], 1))) ** 0.5
                z = (dlb / pooled) if pooled > 0 else None
                if z is None:
                    verdict = "不可读（σ=0）"
                elif abs(z) < 1.0:
                    verdict = "不可分辨（|Δ/合并σ|<1.0）"
                elif abs(z) < 2.0:
                    verdict = "弱分离（1.0–2.0 σ）"
                else:
                    verdict = "分离（≥2.0 σ）"
                diffs[(st, t, arm)] = dict(dlb=dlb, dpc=dpc, z=z, verdict=verdict,
                                           w=w, c=c)
                P("| %s | %s | %s | %+0.2f | %+0.2f | %s | %s | %s | %s |" %
                  (st, t, arm, dlb, dpc, fmt(c["dm_sd"]), fmt(w["dm_sd"]),
                   fmt(z, 2) if z is not None else "—", verdict))
    P("")

    # ── ⑤ W 臂 ─────────────────────────────────────────────
    P("**⑤ W 臂总览（承重维度中位 / 钻牛角尖 / 路径 Self-Sim）**")
    P("")
    P("| 策略 | 题 | n(有效) | 失败单元 | **有效信息维度数中位(主)** | 承重卡片数中位 | 钻牛角尖 | 路径 Self-Sim 中位 | 调用数 |")
    P("|---|---|--:|--:|--:|--:|--:|--:|--:|")
    for st in STRATEGIES:
        by = data[st]["by"]
        for t in TASKS:
            rs = by.get((t, "W_train_L3"), [])
            if not rs:
                P("| %s | %s | 0 | 0 | **缺** | — | — | — | — |" % (st, t))
                continue
            s = cell_stats(rs)
            P("| %s | %s | %d | %d | %s | %s | %d/%d | %s | %d |" %
              (st, t, s["n"], s["n_fail"], fmt(s["dm_median"]), fmt(s["lb_median"]),
               s["pc_hit"], s["pc_n"], fmt(s["sim_median"], 3), s["calls"]))
    P("")

    # ── ⑥ A05 题级明细 ──────────────────────────────────────
    P("**⑥ A05 题级明细（逐 rep）**")
    P("")
    P("| 策略 | 臂 | rep | 承重维度 | 卡片数 | 钻牛角尖 | 解析失败率 | 调用数 | 状态 |")
    P("|---|---|--:|--:|--:|:--:|--:|--:|---|")
    for st in STRATEGIES:
        by = data[st]["by"]
        for arm in ARMS:
            for r in sorted(by.get(("A05", arm), []), key=lambda x: x.get("rep", 0)):
                failed = r.get("n_cards") is None
                P("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" %
                  (st, arm, r.get("rep"),
                   "**失败**" if failed else r.get("n_load_bearing"),
                   "**失败**" if failed else r.get("n_cards"),
                   "—" if failed else ("✔" if (r.get("pc") or {}).get("hit") else "·"),
                   "—" if failed else r.get("parsefail_rate"),
                   "—" if failed else r.get("calls"),
                   "★失败单元（判官/生成无输出，**不记 0**）" if failed else "有效"))
    P("")

    # ── ⑦ 判官状态 ─────────────────────────────────────────
    P("**⑦ 判官状态**")
    P("")
    P("| 策略 | 判官模型 | 同厂商 | 有效份 | 失败单元 | 卡片0(仪器层) | parsefail>0 | 总份 |")
    P("|---|---|:--:|--:|--:|--:|--:|--:|")
    for st in STRATEGIES:
        by = data[st]["by"]
        allr = [r for v in by.values() for r in v]
        if not allr:
            P("| %s | — | — | 0 | 0 | — | — | 0 |" % st)
            continue
        good = [r for r in allr if r.get("n_cards") is not None]
        zero = sum(1 for r in good if (r.get("n_cards") or 0) == 0)
        pf = sum(1 for r in good if r.get("parsefail_rate"))
        P("| %s | %s | %s | %d | %d | %d | %d | %d |" %
          (st, "/".join(sorted({str(r.get("judge_model")) for r in allr})),
           "/".join(str(x) for x in sorted({str(r.get("judge_same_vendor")) for r in allr})),
           len(good), len(allr) - len(good), zero, pf, len(allr)))
    P("")
    P("> ★ `卡片0(仪器层)` = 判官解析不出卡片（仪器坏了）；`n_load_bearing=0 但 n_cards>0` 才是内容层空。两者必须分开看。")
    P("")

    # ── 结论（脚本生成，标【产出方自算】）────────────────────
    concl = build_conclusion(data, tot, a.expect, full, diffs)
    P("**结论【产出方自算】**")
    P("")
    P(concl)
    P("")

    text = "\n".join(L)
    outp = a.out or os.path.join(d, "holdout_table.md")
    io.open(outp, "w", encoding="utf-8").write(text)
    print("✔ 留出集表已写：%s" % outp)
    print("   分母：%s" % (" / ".join("%s=%d" % (s, tot[s]) for s in STRATEGIES)))
    print("   状态：%s" % tag)
    print(text)

    if a.inject:
        inject(a.inject, text)


def judge_status(data):
    parts = []
    for st in STRATEGIES:
        by = data[st]["by"]
        allr = [r for v in by.values() for r in v]
        if not allr:
            parts.append("%s: 无读数" % st)
            continue
        parts.append("%s: %s / 同厂商=%s" % (st,
                                            "/".join(sorted({str(r.get("judge_model")) for r in allr})),
                                            "/".join(str(x) for x in sorted({str(r.get("judge_same_vendor")) for r in allr}))))
    return "　｜　".join(parts)


def build_conclusion(data, tot, expect, full, diffs):
    lines = []
    if not full:
        lines.append("★ 读数【未跑满】（%s）⇒ 本节结论只覆盖已生成单元，**不构成全量判决**。"
                     % " / ".join("%s=%d/%d" % (s, tot[s], expect) for s in STRATEGIES))
    # 负对照是否平：同一题、同一策略下 两个负对照臂的 Δ 承重维度
    neg_flat = []
    for st in STRATEGIES:
        by = data[st]["by"]
        for t in TASKS:
            a1 = by.get((t, "B0_direct"), [])
            a2 = by.get((t, "B0_bestof3"), [])
            if not a1 or not a2:
                continue
            s1, s2 = cell_stats(a1), cell_stats(a2)
            neg_flat.append((st, t, abs(s1["dm_median"] - s2["dm_median"])))
    if neg_flat:
        worst = max(neg_flat, key=lambda x: x[2])
        lines.append("负对照（direct vs bestof3）有效信息维度数中位最大差 = %s（%s/%s）⇒ %s"
                     % (fmt(worst[2]), worst[0], worst[1],
                        "负对照基本持平（可继续读差值）" if worst[2] < 0.5 else
                        "★ 负对照不平 ⇒ 按预注册只报读数 + 噪声地板，不报架构优劣"))
    # W 臂分离
    sep = [v for v in diffs.values() if v["z"] is not None and abs(v["z"]) >= 1.0]
    nsep = [v for v in diffs.values() if v["z"] is not None and abs(v["z"]) < 1.0]
    if diffs:
        lines.append("W 臂 vs 负对照：%d 个(策略×题×对照)对比中，|Δ/合并σ|≥1.0 的 %d 个、<1.0 的 %d 个"
                     % (len(diffs), len(sep), len(nsep)))
    if not full:
        lines.append("★ 读满后必须【重跑本脚本】再据以改稿；当前表不得作为最终判决引用。")
    return "\n".join("- " + x for x in lines)


def inject(paper_path, text):
    s = io.open(paper_path, encoding="utf-8").read()
    begin = "<!-- HOLDOUT_TABLE:BEGIN -->"
    end = "<!-- HOLDOUT_TABLE:END -->"
    if begin not in s or end not in s:
        die("论文里找不到占位块 %s ... %s ⇒ 不注入（不猜位置）" % (begin, end))
    i = s.index(begin) + len(begin)
    j = s.index(end)
    s = s[:i] + "\n\n" + text + "\n\n" + s[j:]
    io.open(paper_path, "w", encoding="utf-8").write(s)
    print("✔ 已注入 %s" % paper_path)


if __name__ == "__main__":
    main()
