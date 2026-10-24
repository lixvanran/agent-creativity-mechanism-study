#!/usr/bin/env python3
"""v6 Stage-1 分析：σ/D0 实测 · 排序改变率 · 目标集变化率 · Gate 诊断 · MDE。

零判官。全部读已落盘 jsonl。⚠️ 结论句按证据标签分级输出。
"""
from __future__ import annotations

import json
import math
import os
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


# ★★★ 2026-10-25 新增：★ 目标集按【align 打分器同口径】重算 ★★★
# ★ 为什么不能信落盘的 target_*：★ 落盘时 `target_set6` 的口径是
# ★ 「depth == 放弃 ⇒ drop；★ else ⇒ deep」⇒ ⇒ **"点到为止"被算进 deep**
# ★ ⇒ 而 `score_state_alignment5` 用的是 `st.deep_set()`（★ **只收"深入展开"**）
# ★ ⇒ ⇒ **两者漂移** ⇒ ⇒ 落盘的 target_* 与打分器实际用的目标集不是一回事
# ★ ⇒ ⇒ **后果：★ ① 用它判"align 是否可打分"会判错（T07-3 就是）
# ★ ⇒ ⇒           ② 用它判"目标集是否变化"会判错**
# ★ ⇒ ⇒ 修法：★ **从落盘的 `state_meta.decisions` 按 deep_set/drop_set 重算**
# ★ ⇒ ⇒（★ decisions 是【原始数据】⇒ ⇒ 不必重跑批就能得到正确读数）
def _target_sets(r):
    """返回 (base_deep, base_drop, quota_deep, quota_drop, scorable_B, scorable_D)。

    ★ 与 `workflow_arch6.state_variants6` 同逻辑：★ base 剔除"放弃"；
    ★ quota 若无自然"放弃"则**补一条**（★ priority 最低者）⇒ ⇒ 与运行期一致。
    """
    def _prio(d):
        try:
            return int(d.get("priority") or 99)
        except (TypeError, ValueError):
            return 99

    def _dsets(decs):
        deep, drop = set(), set()
        for d in decs or []:
            gi = int(d.get("gap_index") or 0)
            if gi <= 0:
                continue
            dep = str(d.get("depth") or "").strip()
            if dep == "深入展开":
                deep.add(gi)
            elif dep == "放弃":
                drop.add(gi)
        return deep, drop

    decs = list((r.get("state_meta") or {}).get("decisions") or [])
    base = [d for d in decs if str(d.get("depth") or "").strip() != "放弃"]
    quota = list(decs)
    if not any(str(d.get("depth") or "").strip() == "放弃" for d in quota):
        cands = [d for d in quota if str(d.get("depth") or "").strip() != "放弃"] or quota
        if cands:
            nd = dict(sorted(cands, key=lambda d: (-_prio(d), int(d.get("gap_index") or 0)))[-1])
            nd["depth"] = "放弃"
            quota = quota + [nd]
    bd, bdr = _dsets(base)
    qd, qdr = _dsets(quota)
    return (bd, bdr, qd, qdr,
            bool(bd or bdr),   # ★ B 档可打分 ⇔ 状态目标集非空
            bool(qd or qdr))   # ★ D 档可打分


def load(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    # ★★★ 2026-10-25：★ 加 `--out`（★ 不再猜落盘路径）★★★
    #   ★ 为什么：★ 同步脚本曾跑本脚本（输出到 code/runs/）却去拷 experiment-design/runs/
    #   ★ ⇒ ⇒ **一直在拷陈旧 analysis** ⇒ ⇒ ★ 这就是"派生读数陈旧"的真因
    #   ★ ⇒ ⇒ **唯一可靠的同步方式 = 让产出方【自报】落盘路径** ★
    _argv = sys.argv[1:]
    out = None
    if "--out" in _argv:
        i = _argv.index("--out")
        out = Path(_argv[i + 1])
        del _argv[i:i + 2]
    src = Path(_argv[0]) if _argv else HERE / "runs" / "arch6_stage1.jsonl"
    rows = load(src)
    out = out or (HERE / "runs" / "arch6_stage1_analysis.json")

    print("=" * 74)
    print("v6 Stage-1 分析：%s" % src)
    print("=" * 74)
    print("样本行数：%d" % len(rows))
    ok = [r for r in rows if not r.get("error")]
    errs = [r for r in rows if r.get("error")]
    # ★★★ 2026-10-25：★ 建立【可打分单元】白名单 ★★★
    #   ★ 判据（★ align 打分器同口径）：★ 状态目标集全空 ⇒ align=None
    #   ★ ⇒ ⇒ 旧代码把 None 静默归零 ⇒ ⇒ 落盘成 0.0 ⇒ ⇒ **看起来像合法的 0 分**
    #   ★ ⇒ ⇒ 但它是【仪器层 0】⇒ ⇒ **不得混进任何内容层统计**（σ / 平移 / 同质率）
    scorable_tags = set()
    for r in ok:
        _bd, _bdr, _qd, _qdr, sc_b, sc_d = _target_sets(r)
        if sc_b and sc_d:
            scorable_tags.add(r.get("tag"))
    ok_sc = [r for r in ok if r.get("tag") in scorable_tags]
    print("  可打分单元（★ 状态目标集非空）：%d / %d" % (len(ok_sc), len(ok)))
    print("  有效 %d / 失败 %d" % (len(ok), len(errs)))
    if errs:
        for r in errs[:6]:
            print("    ✘ %s: %s" % (r.get("tag"), r.get("error")))

    # ── ① 目标集变化率（代价是否真进了状态）
    # ★★★ 2026-10-25 修正：★ 不再信任落盘的 `target_changed` ★★★
    #   ★ 落盘时 `target_set6` 的口径与 `score_state_alignment5` 漂移（★ "点到为止"归属不同）
    #   ★ ⇒ ⇒ 改为**从 state_meta.decisions 按打分器同口径重算**
    tc, tc_detail = [], []
    for r in ok:
        _bd, _bdr, _qd, _qdr, sc_b, sc_d = _target_sets(r)
        if not (sc_b and sc_d):
            continue          # ★ 不可打分 ⇒ 不计入分母
        ch = bool(_bd != _qd or _bdr != _qdr)
        tc.append(ch)
        tc_detail.append({"tag": r.get("tag"), "changed": ch,
                          "base": {"deep": sorted(_bd), "drop": sorted(_bdr)},
                          "quota": {"deep": sorted(_qd), "drop": sorted(_qdr)}})
    tcr = (sum(1 for x in tc if x) / len(tc)) if tc else None
    print("\n── ① 目标集变化率（有代价 ⇒ 状态目标集是否真的变了）")
    print("   ★ 口径：★ 从 state_meta.decisions 按【align 打分器同口径】重算"
          "（★ 不信任落盘的 target_changed ⇒ ★ 旧口径漂移）")
    print("   n=%d  变化率=%s" % (len(tc), ("%.4f" % tcr) if tcr is not None else "n/a"))
    for d in tc_detail:
        if not d["changed"]:
            print("      %-8s 未变：base=%s quota=%s" % (d["tag"], d["base"], d["quota"]))

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

    # ── ★★ ②a-bis 排序改变率的【分母构成】与【Wilson CI】★★
    #   ★ 为什么必须加这一段：★ 「排序改变率 = 2/7」这个数**极易被误读**为
    #   ★ 「机制有 28.6% 的效果」⇒ ⇒ ★ 实际上分母里【多数单元的对照端无区分力】
    #   ★ ⇒ ⇒ 排序改变只可能发生在【有区分力】的单元上 ⇒ ⇒ ★ **分母必须拆开报**。
    print("\n── ②a-bis ★★ 排序改变率的【分母构成】（★ 防止把改变率误读成效果量）")
    detail_rows = []
    n_with_disc = 0          # ★ 对照端（B）有区分力的单元数
    n_changed = 0
    n_unscoreable = 0
    for r in ok:
        bs = (r.get("B_state_nocost") or {}).get("scores") or []
        ds = (r.get("D_state_quota") or {}).get("scores") or []
        if not (bs and ds):
            continue
        # ★★★ 2026-10-25 新增：★ 排除【不可打分】单元 ★★★
        #   ★ 判据（★ align 打分器同口径）：★ 状态目标集全空 ⇒ 该样本无取舍代价
        #   ★ ⇒ ⇒ `score_state_alignment5` 返回 None ⇒ ★ **旧代码把 None 静默归零**
        #   ★ ⇒ ⇒ 落盘的 [0,0,0] 是【仪器层】⇒ ⇒ **不得当内容层 0** ⇒ ⇒ **不得计入分母**
        _bd, _bdr, _qd, _qdr, sc_b, sc_d = _target_sets(r)
        if not (sc_b and sc_d):
            n_unscoreable += 1
            detail_rows.append({"tag": r.get("tag"), "changed": None,
                                "unscoreable": True,
                                "reason": "状态目标集全空 ⇒ align=None ⇒ 旧代码归零",
                                "spread_B": None, "spread_D": None,
                                "control_has_discrimination": None})
            continue
        rb, rd = _rank(bs), _rank(ds)
        changed = bool(rb != rd)
        # ★ 对照端区分力：B 档三候选的 spread（max-min）与 var
        spread_b = (max(float(x) for x in bs) - min(float(x) for x in bs)) if bs else 0.0
        spread_d = (max(float(x) for x in ds) - min(float(x) for x in ds)) if ds else 0.0
        has_disc = spread_b > 1e-9
        if has_disc:
            n_with_disc += 1
        if changed:
            n_changed += 1
        detail_rows.append({"tag": r.get("tag"), "changed": changed,
                            "unscoreable": False,
                            "spread_B": round(spread_b, 6), "spread_D": round(spread_d, 6),
                            "control_has_discrimination": has_disc,
                            "target_base": {"deep": sorted(_bd), "drop": sorted(_bdr)},
                            "target_quota": {"deep": sorted(_qd), "drop": sorted(_qdr)},
                            "target_changed": bool(_bd != _qd or _bdr != _qdr),
                            "change_kind": ("真排序改变" if (changed and has_disc and spread_d > 1e-9)
                                            else ("创造区分" if (changed and not has_disc)
                                                  else "无"))})
    n_all = sum(1 for d in detail_rows if not d.get("unscoreable"))
    print("   ★ 排除不可打分单元 %d 个（★ 状态目标集全空 ⇒ align=None ⇒ 旧代码归零）"
          % n_unscoreable)
    print("   分母 n=%d   改变 %d   ⇒ 改变率=%.4f" % (n_all, n_changed, (n_changed / n_all) if n_all else 0))
    if n_all:
        p = n_changed / n_all
        z = 1.96
        den = 1 + z * z / n_all
        c = (p + z * z / (2 * n_all)) / den
        h = z * math.sqrt(p * (1 - p) / n_all + z * z / (4 * n_all * n_all)) / den
        ci = [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]
        print("   Wilson 95%% CI ≈ [%.3f, %.3f]  ⇒ ★ CI 含 0.25 ⇒ ⇒ 【不可分辨】" % (ci[0], ci[1]))
        print("   ★ 分母构成：对照端（B）**有区分力**的单元 %d/%d（%.4f）" % (
            n_with_disc, n_all, n_with_disc / n_all))
        print("   ⇒ ★ ★ 关键：★ 排序改变**只可能发生在有区分力的单元上**")
        print("   ⇒ ★ ⇒ 改变率 %d/%d 的真实分母应是 **%d**（有区分力的单元）⇒ ⇒ = %.4f" % (
            n_changed, n_all, n_with_disc, (n_changed / n_with_disc) if n_with_disc else 0))
        for d in detail_rows:
            if d.get("unscoreable"):
                print("      %-8s ★★ 不可打分（★ 排除）：%s" % (d["tag"], d.get("reason")))
                continue
            print("      %-8s changed=%-5s spread_B=%.4f spread_D=%.4f 对照端有区分力=%-5s 目标集变=%-5s %s" % (
                d["tag"], d["changed"], d["spread_B"], d["spread_D"],
                d["control_has_discrimination"], d.get("target_changed"),
                d.get("change_kind") or ""))
        # ── ★★★ 第二个口径：★ 排序改变可以来自【D 端内部重排】⇒ ⇒ 只看 B 端会漏 ★★★
        #   ★ G01-3 就是这一类：★ B 端全同（spread_B=0）⇒ 但 D 端有区分 ⇒ ⇒ 排序仍变了
        #   ⇒ ⇒ ★ **「改变」有两个来源**：★ ① B 有区分 ⇒ 代价把 B 的领先者换掉（★ 改变既有排序）
        #   ⇒ ⇒ ★                       ② B 无区分但 D 有区分 ⇒ 代价【创造】了区分（★ 更强）
        sc_rows = [d for d in detail_rows if not d.get("unscoreable")]
        n_either = sum(1 for d in sc_rows
                        if d["spread_B"] > 1e-9 or d["spread_D"] > 1e-9)
        n_changed_with_either = sum(1 for d in sc_rows
                                    if d["changed"] and (d["spread_B"] > 1e-9 or d["spread_D"] > 1e-9))
        # ★★★ 严口径（★ 2026-10-25 新增）：★ "真排序改变" = 两档【都有区分力】且顺序不同
        #   ★ ★ 为什么要单列：★ B 档全并列时 order 恒为原序 [0,1,2] ⇒ ⇒ 机械比顺序
        #   ★ ★ 会把"代价【创造】了区分"误判成"排序被改变"⇒ ⇒ ★ ⇒ 两者机制不同 ⇒ ⇒ 必须分开
        n_both_disc = sum(1 for d in sc_rows
                          if d["spread_B"] > 1e-9 and d["spread_D"] > 1e-9)
        n_true_change = sum(1 for d in sc_rows
                             if d["changed"] and d["spread_B"] > 1e-9 and d["spread_D"] > 1e-9)
        print("   ⇒ ★ ★ 严口径（★ 两档都有区分力）：★ %d/%d 单元两档都有区分力" % (n_both_disc, n_all))
        print("      ★ 其中顺序真变了的：%d ⇒ 严口径改变率 = %s" % (
            n_true_change, ("%.4f" % (n_true_change / n_both_disc)) if n_both_disc else "n/a（★ 分母为 0）"))
        n_created = sum(1 for d in sc_rows if d.get("change_kind") == "创造区分")
        print("      ★ 代价【创造】了区分的单元（★ B 全并列 ⇒ 不存在『排序改变』可谈）：%s" % (
            [d["tag"] for d in sc_rows if d.get("change_kind") == "创造区分"] or "无"))
        print("   ⇒ ★ ★ 第二口径（★ 任一端有区分力）：★ %d/%d 单元有区分力" % (n_either, n_all))
        print("      ★ 排序改变且至少一端有区分力：%d/%d ⇒ = %.4f" % (
            n_changed_with_either, n_either, (n_changed_with_either / n_either) if n_either else 0))
        print("      ★ ★ 其中【B 无区分、D 有区分】= 代价【创造】了区分的单元：%s" % (
            [d["tag"] for d in detail_rows
             if d["changed"] and d["spread_B"] <= 1e-9 and d["spread_D"] > 1e-9] or "无"))
        print("      ★ ★ 其中【B 有区分】= 代价【改变】了既有排序的单元：%s" % (
            [d["tag"] for d in detail_rows
             if d["changed"] and d["spread_B"] > 1e-9] or "无"))
        print("   ⇒ ★ ★ 判读口径：★ 改变率【不能单独解读】⇒ ⇒ 必须与「区分力」一起报")
        print("   ⇒ ★ ⇒ 若无区分力的单元占多数 ⇒ ⇒ 改变率的分母是【被稀释】的 ⇒ ⇒ 不可当作效果量")

    # ── ★★ ②a-ter 三种 0 的分类（★ 仪器层 0 / 内容层 0 / 不可打分 None）★★
    #   ★ T07-3 出现过 B=D=[0,0,0] ⇒ ⇒ 必须区分它是【内容层真 0】还是【不可打分被归零】
    #   ★ 判据：★ fulfil > 0 ⇒ 候选有可解析声明且状态目标集非空 ⇒ ⇒ 0 是【真实的 Jaccard=0】= 内容层 0
    print("\n── ②a-ter ★★ 三种 0 的分类（★ 禁止把 None 当 0）")
    zero_cls = {"content_zero": [], "unscoreable_none": [], "other": []}
    for r in ok:
        bs = (r.get("B_state_nocost") or {}).get("scores") or []
        ds = (r.get("D_state_quota") or {}).get("scores") or []
        if not (bs and ds):
            continue
        if not all(abs(float(x)) < 1e-12 for x in bs + ds):
            continue
        # ★★★ 2026-10-25 修正：★ 判"可否打分"必须用【align 打分器同口径】★★★
        #   ★ 旧判据用落盘的 `target_quota`，★ 而它的口径与打分器漂移（★ "点到为止"归属不同）
        #   ★ ⇒ ⇒ 旧判据会把"状态目标集全空"的单元判成"目标非空 ⇒ 内容层 0"
        #   ★ ⇒ ⇒ 【★ 那是把"仪器层 0"（None 被旧代码归零）伪装成"内容层 0" ★】
        _bd, _bdr, _qd, _qdr, sc_b, sc_d = _target_sets(r)
        if not (sc_b and sc_d):
            # ★ ★ 状态目标集全空 ⇒ align=None ⇒ ★ 旧代码 `0.0 if v is None else v` ⇒ 落盘成 0
            # ⇒ ⇒ 这是【不可打分 None 被旧实现归零】⇒ ⇒ **不得当内容层 0**
            zero_cls["unscoreable_none"].append(r.get("tag"))
            continue
        ful = (r.get("ful_B") or {}).get("fulfill")
        if ful is not None and float(ful) > 0:
            zero_cls["content_zero"].append(r.get("tag"))
        else:
            zero_cls["other"].append(r.get("tag"))
    print("   内容层 0（★ 候选声明与状态决策**真的**不相交 ⇒ Jaccard=0）：%s"
         % (zero_cls["content_zero"] or "无"))
    print("   不可打分 None（★ 状态目标集全空 ⇒ align=None ⇒ ★ 旧代码静默归零）：%s"
         % (zero_cls["unscoreable_none"] or "无"))
    print("   其他：%s" % (zero_cls["other"] or "无"))
    print("   ⇒ ★ 判据（★ 2026-10-25 修正）：★ 先用【align 同口径】判可否打分")
    print("     ⇒ 状态目标集全空 ⇒ **不可打分 None** ⇒ ⇒ 落盘的 0 是【仪器层】⇒ ⇒ 不得当内容层 0")
    print("     ⇒ 可打分且 fulfil>0 ⇒ 该 0 是【内容层】⇒ ⇒ 不得归为仪器层")
    print("   ⇒ ★ ★ 内容层 0 的单元：★ 候选与状态完全不相交 ⇒ ⇒ 对「平移 vs 区分」零信息量 ⇒ ⇒ 须单独标注")
    print("   ⇒ ★ ★ ★ 不可打分的单元【不进排序改变率分母】（★ 它的 0 是仪器层假象）")

    # ── ★★ ②b 机制诊断：代价是「常数平移」还是「区分候选」
    #     若代价对所有候选一视同仁地降低 align ⇒ 它只是常数偏移 ⇒ 排序必然不变
    #     ⇒ ⇒ "排序改变率≈0" 的机制解释就在这里（而不是"模型没接入"）。
    shift_var, shift_all = [], []
    dvar, bvar = [], []
    for r in ok_sc:      # ★★★ 2026-10-25：★ 排除不可打分单元（★ 其 0 是仪器层假象）★★★
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
    # ★ ALIGN_VAR_IS_SD_FIXED：★ 口径改正 —— 之前字段名 `align_var` 装的其实是**标准差**，
    #   而「同质率」对应的是**方差 = 0** ⇒ ⇒ 两者必须用同一口径才能互相算出来。
    #   ⇒ 现在同时报 var（方差）与 sd（标准差），并给"由同质率推出的期望均值"做自洽核对。
    def _v(xs):
        n = len(xs)
        if n < 2: return 0.0
        m = sum(xs) / n
        return sum((x - m) ** 2 for x in xs) / (n - 1)
    bvar_true = [_v([float(x) for x in ((r.get("B_state_nocost") or {}).get("scores") or [])])
                 for r in ok_sc if len((r.get("B_state_nocost") or {}).get("scores") or []) > 1]
    dvar_true = [_v([float(x) for x in ((r.get("D_state_quota") or {}).get("scores") or [])])
                 for r in ok_sc if len((r.get("D_state_quota") or {}).get("scores") or []) > 1]
    print("   状态化尺子区分力（★ 方差 / 标准差 两个口径都给，避免命名误导）：")
    print("     B 档：var 均值=%s ／ sd 均值=%s" % (
        ("%.4f" % (sum(bvar_true) / len(bvar_true))) if bvar_true else "n/a",
        ("%.4f" % (sum(bvar) / len(bvar))) if bvar else "n/a"))
    print("     D 档：var 均值=%s ／ sd 均值=%s" % (
        ("%.4f" % (sum(dvar_true) / len(dvar_true))) if dvar_true else "n/a",
        ("%.4f" % (sum(dvar) / len(dvar))) if dvar else "n/a"))
    if bvar_true:
        print("   ⇒ ★ 自洽核对：同质样本 var=0 ⇒ 「var 均值」= (异质样本 var 之和)/n ⇒ %.4f" % (
            sum(bvar_true) / len(bvar_true)))
        print("     而 sd 均值 = (异质样本 sd 之和)/n ⇒ %.4f  ⇒ ★ 两个口径**不可混用**" % (
            sum(bvar) / len(bvar)))

    # ── ★★ ②c 候选池同质率：★ "选择层没有东西可选"的直接量化
    #     若同题同批的候选在"自主声明"上高度同质 ⇒ 两个打分器面对的是一批等价候选
    #     ⇒ ⇒ 任何选择器都只能取第一个 ⇒ ⇒ 排序改变率必然 0
    homo, decl_sets = 0, []
    for r in ok_sc:     # ★★★ 2026-10-25：★ 排除不可打分单元 ★★★
        bs = (r.get("B_state_nocost") or {}).get("scores") or []
        if len(bs) > 1:
            if len(set(round(float(x), 6) for x in bs)) == 1:
                homo += 1
    print("\n── ②c ★ 候选池同质率（★ 选择层有没有东西可选）")
    print("   ★ 分母只算可打分单元（★ 不可打分者不是『同质』，★ 是『没被评分』）")
    print("   B 档三候选 align **全同**的样本：%d/%d  ⇒ 同质率=%.4f" % (
        homo, len(ok_sc), (homo / len(ok_sc)) if ok_sc else 0))
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
    # ★★★ 2026-10-25 修正：★ 排除【不可打分】单元 ★★★
    #   ★ 旧代码把 align=None 静默归零 ⇒ ⇒ 落盘成 0.0 ⇒ ⇒ **看起来像个合法的 0 分**
    #   ★ ⇒ ⇒ 把它算进 gap 序列 ⇒ ⇒ **σ 被假 0 污染** ⇒ ⇒ MDE 跟着偏
    #   ★ ⇒ ⇒ 这是"仪器层 0 混进内容层统计"的典型 ⇒ ⇒ 必须按【可打分性】过滤
    gaps, n_gap_excluded = [], 0
    for r in ok:
        _bd, _bdr, _qd, _qdr, sc_b, sc_d = _target_sets(r)
        if not (sc_b and sc_d):
            n_gap_excluded += 1
            continue
        b = (r.get("B_state_nocost") or {}).get("align")
        d = (r.get("D_state_quota") or {}).get("align")
        if b is not None and d is not None:
            gaps.append(float(d) - float(b))
    s_new = sd(gaps) if len(gaps) > 1 else None
    print("\n── ⑤ σ 实测（有代价 vs 无代价 的状态化 align 差）")
    print("   ★ 排除不可打分单元 %d 个（★ 其 align 是 None 被旧代码归零的假 0）" % n_gap_excluded)
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
        "target_change_detail": tc_detail,
        # ★★★ 2026-10-25：★ 分母改为【可打分单元】★★★
        "candidate_homogeneity_rate": (homo / len(ok_sc)) if ok_sc else None,
        "candidate_homogeneity_n": homo,
        "candidate_homogeneity_denominator": len(ok_sc),
        "n_scorable": len(ok_sc),
        "n_unscoreable": n_unscoreable,
        "align_shift_mean": mean_shift,
        "align_shift_var_mean": (sum(shift_var) / len(shift_var)) if shift_var else None,
        "align_sd_B": (sum(bvar) / len(bvar)) if bvar else None,
        "align_sd_D": (sum(dvar) / len(dvar)) if dvar else None,
        "align_var_B": (sum(bvar_true) / len(bvar_true)) if bvar_true else None,
        "align_var_D": (sum(dvar_true) / len(dvar_true)) if dvar_true else None,
        "ALIGN_VAR_IS_SD_FIXED": True,
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
        # ── ★★ 排序改变率的分母构成（★ 防止把改变率误读成效果量）★★
        "rank_change_detail": detail_rows,
        "rank_change_n": n_all,
        "rank_change_count": n_changed,
        "rank_change_rate": (n_changed / n_all) if n_all else None,
        "rank_change_wilson_ci95": ci if n_all else None,
        "control_has_discrimination_n": n_with_disc,
        "control_has_discrimination_rate": (n_with_disc / n_all) if n_all else None,
        "rank_change_rate_over_discriminating_only": (
            (n_changed / n_with_disc) if n_with_disc else None),
        # ── ★★ 三种 0 的分类 ★★
        "zero_classification": zero_cls,
    }
    # ── ★★ 落盘：★ 目录必须先建（★ 否则在交付包里跑会 FileNotFoundError）
    #   ★ 且用【原子写】（★ 临时文件 + os.replace）⇒ ★ 写失败不会把旧结果截断成 0 字节
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, out)
    print("\n✔ 已落盘：%s" % out)


if __name__ == "__main__":
    main()
