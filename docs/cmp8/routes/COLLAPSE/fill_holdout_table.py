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
# ★ 判官健康度阈值：失败率 > 10% ⇒ 拦截（★ 沿用第二组健康度 ≥ 0.9 的口径）
FAIL_RATE_MAX = 0.10
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
        calls=(sum([c for c in (r.get("calls") for r in good) if isinstance(c, int)])
               if any(isinstance(c, int) for c in (r.get("calls") for r in good)) else None),
        judge_models=sorted({r.get("judge_model") for r in good if r.get("judge_model")}),
        same_vendor=sorted({r.get("judge_same_vendor") for r in good if r.get("judge_same_vendor") is not None}),
    )


def fmt(x, nd=2, dash="—"):
    if x is None:
        return dash
    return ("%." + str(nd) + "f") % x


def judge_health(by):
    """★ 按 (task, arm) 算判官健康度 ⇒ **按臂分别算**（★ 全局率会掩盖单臂失败）

    ★ 三问（★ 沿用第二组口径：只锁「解析失败」，「未提及」「非主张」是合法判定）：
      ① 仪器层零：`n_cards == 0` ⇒ 该臂的 n_dims=0 **不可信**（★ 看着像"极端塌缩"）
      ② `parsefail_rate > 0` ⇒ 解析有失败
      ③ 有效读数为 0 ⇒ 该臂没读数
    """
    out = {}
    for (t, arm), rs in by.items():
        good = [r for r in rs if r.get("n_cards") is not None]
        zero = sum(1 for r in good if (r.get("n_cards") or 0) == 0)
        pf = sum(1 for r in good if r.get("parsefail_rate"))
        n_failed = len(rs) - len(good)
        out[(t, arm)] = dict(n_total=len(rs), n_valid=len(good), n_failed=n_failed,
                              fail_rate=(n_failed / float(len(rs))) if rs else None,
                              cards0=zero, parsefail=pf,
                              parsefail_rate=(pf / len(good)) if good else None,
                              healthy=(len(good) > 0 and zero == 0 and pf == 0))
    return out


def health_gate(health, label=""):
    """★ 闸门：不通过 ⇒ SystemExit（★ 不出表 ⇒ 坏读数进不了交稿）
    ★ 阈值 = 0（★ 即"一个都不许有"）⇒ ⇒ 因为【仪器层零】与【任一 parse 失败】
      都会让该臂的 n_dims 变成【不可信的 0】⇒ ⇒ 这不是"可接受的噪声"。
    ★ 「阈值不是恒真」的自检在 --self-test 里（★ 第二组 T4 的做法）。"""
    bad = []
    for _k, h in health.items():
        t, arm = _k[-2], _k[-1]
        if h["n_valid"] == 0:
            bad.append("%s/%s：有效读数 0" % (t, arm))
        elif h["cards0"]:
            bad.append("%s/%s：仪器层零 %d 份（★ n_dims=0 不可信）" % (t, arm, h["cards0"]))
        elif h["parsefail"]:
            bad.append("%s/%s：解析失败 %d 份（率 %.1f%%）"
                       % (t, arm, h["parsefail"], 100.0 * h["parsefail_rate"]))
        # ★★★ 失败单元（n_cards=None）：★ 它们【不在 good 里】⇒ ⇒ 原闸门完全看不见
        #   ⇒ ⇒ **分母悄悄变小** ⇒ ⇒ 必须单独判（★ 阈值 10%，沿用第二组健康度 ≥0.9）
        elif h["n_failed"] and h["fail_rate"] is not None and h["fail_rate"] > FAIL_RATE_MAX:
            bad.append("%s/%s：失败单元 %d/%d（率 %.1f%% > %.0f%% ⇒ 判官健康度 < 0.9）"
                       % (t, arm, h["n_failed"], h["n_total"], 100.0 * h["fail_rate"],
                          100.0 * FAIL_RATE_MAX))
    if bad:
        # ★★ 专属退出码 7（★ 第二组也用 7 表示"静默消失"）
        #   ★ **闸门拦截(7) 与 脚本崩溃(1) 必须可区分** ⇒ ⇒ 只看退出码 1 会把崩溃当拦截
        print("✘ ★★★ 判官健康度闸门不通过%s ⇒ 【不出表】\n    ⇒ %s\n"
                         "    ⇒ ★ 「n_dims=0」既可能是【极端塌缩】，也可能是【判官没跑】\n"
                         "    ⇒ ★ 本项目内 logits 不可得 ⇒ 这两种在读数上【无法区分】\n"
                         "    ⇒ ⇒ ⇒ 只能先排除后者 ⇒ ⇒ ⇒ 故拒绝出表。"
              % (("（" + label + "）") if label else "", "\n    ⇒ ".join(bad)), file=sys.stderr)
        raise SystemExit(7)


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
    ap.add_argument("--self-test", action="store_true", help="★ 闸门自检：阈值不是恒真")
    a = ap.parse_args()
    if a.self_test:
        print("★ 判官健康度闸门 · 自检")
        return _self_test()

    d = a.holdout_dir
    data = build(d, a.expect)
    tot = {st: data[st]["total"] for st in STRATEGIES}
    # ★★ "跑满"必须按【有效读数】判，不能按【文件行数】判 ——
    #   否则一个死单元会被行数掩盖 ⇒ 表头写"全量"而实际缺份。
    valid = {}
    for st in STRATEGIES:
        valid[st] = sum(1 for v in data[st]["by"].values() for r in v
                         if r.get("n_cards") is not None)
    nfail_all = {st: tot[st] - valid[st] for st in STRATEGIES}
    full = all(valid[st] >= a.expect for st in STRATEGIES)
    partial = [st for st in STRATEGIES if valid[st] < a.expect]

    if a.strict and not full:
        die("读数未到齐（%s）且 --strict ⇒ 停止" %
            ", ".join("%s=%d/%d" % (st, valid[st], a.expect) for st in STRATEGIES))

    if full:
        tag = "【已跑批·全量 n=%d/%d（有效读数）】" % (a.expect, a.expect)
    else:
        tag = "【已跑批·部分 n=%s（有效读数）】" % " / ".join(
            "%s=%d/%d" % (st, valid[st], a.expect) for st in STRATEGIES)
    if any(nfail_all.values()):
        tag += "　★ 失败单元（判官/生成整段无输出，**不记 0、不进统计分母**）：%s" % " / ".join(
            "%s=%d" % (st, nfail_all[st]) for st in STRATEGIES if nfail_all[st])
    if partial:
        tag += "　★ 未跑满 ⇒ 缺份是【单元尚未生成】，不是解析失败（分母不等时只报读数 + 噪声地板）"

    # ★★★ 闸门（★ 放在【出表之前】⇒ 不通过 ⇒ 连表都不写）
    all_health = {}
    for st in STRATEGIES:
        all_health.update({(st, t, arm): h
                           for (t, arm), h in judge_health(data[st]["by"]).items()})
    health_gate(all_health, label="留出集三臂")

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
    P("| 策略 | 文件 | 总行数 | A02: B0_direct / B0_bestof3 / W_train_L3 | A05: B0_direct / B0_bestof3 / W_train_L3 | **有效读数相等?** |")
    P("|---|---|--:|---|---|:--:|")
    denoms = {}
    for st in STRATEGIES:
        by = data[st]["by"]
        cells = []
        per = []
        per_valid = []
        for t in TASKS:
            row = []
            row_valid = []
            for arm in ARMS:
                rs = by.get((t, arm), [])
                row.append(len(rs))
                row_valid.append(sum(1 for r in rs if r.get("n_cards") is not None))
            per.append(row)
            per_valid.append(row_valid)
            cells.append(" / ".join("%d(%d)" % (v, raw) for v, raw in zip(row_valid, row)))
        denoms[st] = per_valid
        # ★★ 「分母齐」必须按【有效读数】判，不能按【原始行数】判 ——
        #   否则一个死单元（n_cards=None）会被行数掩盖 ⇒ 伪装成"分母齐"。
        ok = all(len(set(r)) == 1 for r in per_valid) and all(r[0] == r[1] == r[2] for r in per_valid)
        nfail = sum(1 for v in by.values() for r in v if r.get("n_cards") is None)
        P("| %s | `%s` | %d | %s | %s | %s |" %
          (st, os.path.relpath(data[st]["path"], HERE), tot[st], cells[0], cells[1],
             "✔" if ok else "✘"))
        if nfail:
            P("")
            P("> ⚠ **%s 有 %d 份【失败单元】**（`n_cards=None`）⇒ ⇒ 上表每格写作「有效(原始)」⇒ ⇒ "
              "**该臂的真实统计分母 = 有效读数，不是行数** ⇒ ⇒ 行数相等 ≠ 有效分母相等。" % (st, nfail))
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
    concl = build_conclusion(data, tot, a.expect, full, diffs, valid)
    P("**结论【产出方自算】**")
    P("")
    P(concl)
    P("")

    text = "\n".join(L)
    outp = a.out or os.path.join(d, "holdout_table.md")
    io.open(outp, "w", encoding="utf-8").write(text)
    print("✔ 留出集表已写：%s" % outp)
    print("   分母（有效读数 / 文件行数）：%s" % (" / ".join("%s=%d/%d" % (s, valid[s], tot[s]) for s in STRATEGIES)))
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


def build_conclusion(data, tot, expect, full, diffs, valid=None):
    lines = []
    if not full:
        lines.append("★ 读数【未跑满】（有效读数 %s）⇒ 本节结论只覆盖已生成单元，**不构成全量判决**。"
                     % " / ".join("%s=%d/%d" % (s, valid[s], expect) for s in STRATEGIES))
    nf = {s: tot[s] - valid[s] for s in STRATEGIES}
    if any(nf.values()):
        lines.append("★ **失败单元（不计 0、不进统计分母）**：%s ⇒ ⇒ 对应臂的真实统计分母 = 有效读数，**不是文件行数**。"
                     % " / ".join("%s=%d" % (s, nf[s]) for s in STRATEGIES if nf[s]))
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


def _self_test():
    """★ 「阈值不是恒真」的自检（★ 第二组 T4 的做法：精确构造 11% / 9% ⇒ 必须翻转）"""
    import copy

    def mk(n, n_fail, n_cards_zero=0, n_valid=None):
        rs = []
        for i in range(n):
            if i < n_fail:
                rs.append(dict(task_id="T", arm="A", rep=i, n_cards=None,
                                n_dims=None, n_load_bearing=None, parsefail_rate=None,
                                calls=None))
            elif i < n_fail + n_cards_zero:
                rs.append(dict(task_id="T", arm="A", rep=i, n_cards=0, n_dims=0,
                                n_load_bearing=0, parsefail_rate=0.0, calls=2))
            else:
                rs.append(dict(task_id="T", arm="A", rep=i, n_cards=5, n_dims=2,
                                n_load_bearing=3, parsefail_rate=0.0, calls=2))
        return {("T", "A"): rs}

    cases = [
        ("健康批（0 失败）", mk(100, 0), True),
        ("★ 11 份失败（11%）⇒ 闸门必须闭", mk(100, 11), False),
        ("★ 9 份失败（9%）⇒ 闸门必须开", mk(100, 9), True),
        ("★ 1 份仪器层零 ⇒ 闸门必须闭", mk(100, 0, n_cards_zero=1), False),
    ]
    ok = True
    for label, by, want_pass in cases:
        try:
            health_gate(judge_health(by), label=label)
            got = True
            why = ""
        except SystemExit as e:
            got = False
            why = str(e).split("\n")[0]
        mark = "✔" if got == want_pass else "✘ ★"
        if got != want_pass:
            ok = False
        print("  %s %-28s 期望 %s ／ 实得 %s %s"
              % (mark, label, "通过" if want_pass else "拦截", "通过" if got else "拦截", why))
    print("  ⇒ 阈值自检：%s" % ("全部符合预期（⇒ 阈值不是恒真）" if ok else "★★ 有反例（⇒ 阈值恒真！）"))
    return 0 if ok else 1


if __name__ == "__main__":
    # ★★ 关键：`sys.exit(main())` ⇒ ★ main() 的返回值【真正成为进程退出码】
    #   ★ 旧写法 `main()` ⇒ ★ 返回值被丢弃 ⇒ ★★ **无论成功失败退出码都是 0**
    #   ★★ ⇒ ⇒ 我在 EXEC-LOG 里报过的"退出码 0"因此【毫无意义】⇒ ⇒ 已作废并重测
    sys.exit(main() or 0)
