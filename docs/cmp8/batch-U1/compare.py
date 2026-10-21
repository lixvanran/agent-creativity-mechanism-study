# -*- coding: utf-8 -*-
"""批次 U1-2026-10-21 · **两套测量机制的对照**。

读 measurement.json（我的流水线 + 人肉标准），按 PREREG 的事前预测逐条核对。

⚠️ 本批**只比两套测量机制**，不比臂的优劣（PREREG §8）。
"""
import json
import os
import sys

sys.path.insert(0, "/workspace/lab/batch-U1")
import u1_lib as U

BATCH = U.BATCH


def spearman(xs, ys):
    n = len(xs)
    if n < 2:
        return None

    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def main():
    M = json.load(open(os.path.join(BATCH, "measurement.json"), encoding="utf-8"))
    res = M["results"]
    arms = ["B0_direct", "B1_eq_calls", "A_fixed", "C_T2"]

    def get(arm, rep):
        return res.get("%s#rep%d" % (arm, rep))

    print("=" * 88)
    print("批次 U1-2026-10-21 ｜ 两套测量机制对照")
    print("判官（测量侧）= %s ｜ 被测（工作流侧）= %s ｜ judge_same_vendor=%s"
          % (M["judge_model"], M.get("tested_model", "x-ai/grok-4.3"),
             M["judge_same_vendor"]))
    print("=" * 88)

    # ── 1. 逐份读数 ────────────────────────────────────────
    print("\n【1. 逐份读数】")
    hdr = ("%-14s %4s %6s %6s %6s %6s %8s %7s %7s %8s %6s"
           % ("臂", "rep", "断言", "卡片", "承重", "冗余", "维度D", "新增", "丢失", "净增益", "人肉"))
    print(hdr); print("-" * len(hdr))
    for arm in arms:
        for rep in (1, 2, 3):
            v = get(arm, rep)
            if not v:
                continue
            h = v.get("human", {})
            print("%-14s %4d %6d %6d %6d %6d %8d %7s %7s %8s %6.1f"
                  % (arm, rep, v.get("n_claims_extracted", 0), v.get("n_cards", 0),
                     v.get("n_load_bearing_cards", 0), v.get("n_redundant_merged", 0),
                     v.get("D", 0),
                     len(v.get("added_conclusions", [])),
                     len(v.get("lost_conclusions", [])),
                     v.get("net_dimension_gain", 0),
                     h.get("score", 0)))
    print("（人肉 = 主口径「分级」；per-name 变体见下）")

    # ── 2. 臂级汇总 ────────────────────────────────────────
    print("\n【2. 臂级汇总（3 次重复的中位数）】")
    def med(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else None
    agg = {}
    for arm in arms:
        vs = [get(arm, r) for r in (1, 2, 3)]
        vs = [v for v in vs if v]
        if not vs:
            continue
        agg[arm] = dict(
            D=med([v.get("D", 0) for v in vs]),
            cards=med([v.get("n_cards", 0) for v in vs]),
            lb=med([v.get("n_load_bearing_cards", 0) for v in vs]),
            net=med([v.get("net_dimension_gain", 0) for v in vs]),
            human=med([v.get("human", {}).get("score", 0) for v in vs]),
            human_pername=med([v.get("human", {}).get("score_pername", 0) for v in vs]),
            parsefail=med([v.get("parsefail_rate", 0) for v in vs]),
        )
        a = agg[arm]
        print("  %-14s 维度D=%-4s 卡片=%-4s 承重=%-4s 净增益=%-4s 人肉=%.1f "
              "per-name=%.1f parsefail=%.2f"
              % (arm, a["D"], a["cards"], a["lb"], a["net"], a["human"],
                 a["human_pername"], a["parsefail"]))

    # ── 3. 两套测量的相关 ──────────────────────────────────
    print("\n【3. 两套测量的秩相关（逐份，n=12）】")
    pairs = [(v.get("D", 0), v.get("human", {}).get("score", 0))
             for v in res.values()]
    rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
    print("  流水线 D（维度数） × 人肉标准 = Spearman ρ = %s" % ("%.3f" % rho if rho is not None else "n/a"))
    pairs2 = [(v.get("net_dimension_gain", 0), v.get("human", {}).get("score", 0))
              for v in res.values()]
    rho2 = spearman([p[0] for p in pairs2], [p[1] for p in pairs2])
    print("  流水线 净增益 × 人肉标准    = Spearman ρ = %s" % ("%.2f" % rho2 if rho2 is not None else "n/a"))
    # 提到港校的份 vs 没提到的份
    mh = [v for v in res.values() if v.get("human", {}).get("specific_named")
          or v.get("human", {}).get("generic_mentioned")]
    nh = [v for v in res.values() if not (v.get("human", {}).get("specific_named")
                                          or v.get("human", {}).get("generic_mentioned"))]
    def avg(xs):
        return sum(xs) / len(xs) if xs else None
    if mh and nh:
        print("\n  提及港校/港校名的 %d 份：流水线 D 均值 = %.2f ｜ 未提及的 %d 份：D 均值 = %.2f"
              % (len(mh), avg([v.get("D", 0) for v in mh]),
                 len(nh), avg([v.get("D", 0) for v in nh])))
        print("  ⇒ 差值 = %+.2f 维度" % (avg([v.get("D", 0) for v in mh])
                                        - avg([v.get("D", 0) for v in nh])))

    # ── 4. 事前预测的核对 ──────────────────────────────────
    print("\n【4. 事前预测核对（PREREG §4）】")
    if mh and nh:
        delta = avg([v.get("D", 0) for v in mh]) - avg([v.get("D", 0) for v in nh])
        print("  P-1（两套测量的方向预期相反）：")
        print("     人肉标准对「提及港校」的区分度 = %.2f - %.2f = %+.2f"
              % (avg([v.get("human", {}).get("score", 0) for v in mh]),
                 avg([v.get("human", {}).get("score", 0) for v in nh]),
                 avg([v.get("human", {}).get("score", 0) for v in mh])
                 - avg([v.get("human", {}).get("score", 0) for v in nh])))
        print("     流水线 D 对「提及港校」的区分度 = %+.2f" % delta)
        print("     ⇒ %s" % ("符合 P-1：两套测量的区分方向相反"
                              if delta <= 0 else "★ 不符合 P-1：流水线对提及港校反而更宽"))
    print("  P-4（若 ρ ≥ 0.8 则 P-1 被否证）：ρ = %s ⇒ %s"
          % ("%.3f" % rho if rho is not None else "n/a",
             "P-4 触发 ⇒ P-1 被否证" if (rho is not None and rho >= 0.8)
             else "P-4 未触发 ⇒ P-1 站得住"))

    # ── 5. 否证条件 ────────────────────────────────────────
    print("\n【5. 否证条件核对（PREREG §5）】")
    # R1：提及港校的臂，流水线 D 显著更高 ⇒ 流水线的承重检验失效
    if mh and nh:
        delta = avg([v.get("D", 0) for v in mh]) - avg([v.get("D", 0) for v in nh])
        print("  R1（提及港校的臂 D 更高 ⇒ 判流水线的错）：差值 %+.2f ⇒ %s"
              % (delta, "★ 触发" if delta > 0.5 else "未触发"))
    # R2/R3
    pf = max((v.get("parsefail_rate", 0) or 0) for v in res.values()) if res else 0
    nvalid = sum(1 for v in res.values() if v.get("valid"))
    ntot = len(res)
    print("  R2（parsefail_rate > 10%%）：最高 %.3f ⇒ %s" % (pf, "★ 触发" if pf > 0.10 else "未触发"))
    print("  R3（valid/total < 2/3）：%d/%d ⇒ %s" % (nvalid, ntot, "★ 触发" if nvalid < ntot * 2 / 3 else "未触发"))
    # R5：生成侧污染
    cont = []
    for arm in arms:
        d = os.path.join(BATCH, "runs", arm)
        for rep in (1, 2, 3):
            mp = os.path.join(d, "rep%d.meta.json" % rep)
            if os.path.exists(mp):
                m = json.load(open(mp, encoding="utf-8"))
                c = m.get("contamination_generation_side")
                if c:
                    cont.append((arm, rep, c))
    print("  R5（生成侧提示词含港校关键词）：%s ⇒ %s"
          % (cont or "零命中", "★ 触发" if cont else "未触发"))
    # R6：C_t
    print("  R6（C_t 非空且与依据包事实数相等）：C_t=%d 事实=%d ⇒ %s"
          % (M["ct_len"], M["facts"], "★ 触发" if M["ct_len"] != M["facts"] else "未触发"))

    with open(os.path.join(BATCH, "comparison.json"), "w", encoding="utf-8") as f:
        json.dump(dict(agg=agg, rho=rho, rho_net=rho2,
                       parsefail_max=pf, valid=nvalid, total=ntot,
                       contamination=cont), f, ensure_ascii=False, indent=2)
    print("\n✓ comparison.json 已落盘")


if __name__ == "__main__":
    main()
