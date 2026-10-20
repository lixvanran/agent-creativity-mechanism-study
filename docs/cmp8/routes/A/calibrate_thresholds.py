# -*- coding: utf-8 -*-
"""**离线**标定 `lex_thr` / `struct_thr` 两个离散冗余判据的阈值。

⚠️ 纪律（协议 R-9 / R-1 / R-13）：
- 标定集是**本文件自造**的合成断言语料（虚构的仓储配送计费规则），
  **不是** DEV 集、**不是** U1–U4、**不含**任何真实题目的实体；
- 标定**只跑离散判据**（0 次 API 调用），不跑模型；
- 阈值在**看任何真实数据之前**冻结；本脚本的输出是**证据**，不是调参机会：
  若读数显示预注册值有明显问题，必须**如实写进日志**并在 `DESIGN.md` 登记
  （改值属于**预注册期**的修正，必须写明「改前值 / 改后值 / 依据」）。

用法：python3 calibrate_thresholds.py
输出：calibration_log.json（机读）+ calibration_log.txt（人读），都在本目录。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/workspace/lab")

from route_a import RedundancyJudge, DEFAULTS     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 合成标定语料
# 27 条**基础断言**（互不冗余）+ 5 条**近逐字重复** + 5 条**改写型重复** = 37 条。
# 语料内容 = 虚构的「仓储配送计费规则」；不含任何真实题目的实体。
BASE = [
    "基础配送费为每单 12 元。",
    "基础配送费不含装卸费。",
    "续重部分每公斤加收 3 元。",
    "单件上限为 30 公斤。",
    "超过 30 公斤的订单需人工预约。",
    "夜间派送附加费为每单 8 元。",
    "夜间派送仅覆盖 22 时至次日 6 时。",
    "代收货款服务费率为货值的 1%。",
    "代收货款单笔上限为 5000 元。",
    "货值超过 5000 元的部分需另行报价。",
    "同一收货地址每月前 3 单免收基础配送费。",
    "免收优惠不适用于续重费。",
    "预约配送的时段可选上午或下午。",
    "预约配送需提前 1 个工作日。",
    "偏远区域附加费为每单 15 元。",
    "偏远区域定义由仓库所在区县划定。",
    "大件商品需走货运专线。",
    "货运专线不提供代收货款。",
    "保温箱租赁费为每次 5 元。",
    "保温箱押金为 50 元。",
    "押金在归还时全额退还。",
    "退货取件费为每单 10 元。",
    "退货取件需原包装。",
    "换货服务免费。",
    "换货仅限同型号商品。",
    "取消订单在发货前免费。",
    "改约需在上门前 2 小时完成。",
]
# 近逐字重复（只差空格/标点）—— 期望实现 1（词法）命中
NEAR_VERBATIM = [
    "基础配送费为每单12元。",
    "续重部分每公斤加收3元。",
    "单件上限为30公斤。",
    "夜间派送附加费为每单8元。",
    "代收货款服务费率为货值的1%。",
]
# 改写型重复（数字指纹相同、措辞不同）—— 期望实现 2（结构）命中
REWRITTEN = [
    "续重部分按每公斤加收 3 元。",
    "单件重量上限为 30 公斤。",
    "夜间派送附加费按每单收 8 元。",
    "代收货款的服务费率为货值的 1%。",
    "偏远区域附加费按每单收 15 元。",
]

CLAIMS = list(BASE) + list(NEAR_VERBATIM) + list(REWRITTEN)

# 标注：重复对（base下标, 变体下标, 类型）。类型 ∈ {lexical, structural}
# ⚠️ 显式写死对应关系（不靠下标推算）⇒ 标注可被人逐条核对。
DUP_PAIRS = [
    (0, len(BASE) + 0, "lexical"),        # 基础配送费为每单12元。
    (2, len(BASE) + 1, "lexical"),        # 续重部分每公斤加收3元。
    (3, len(BASE) + 2, "lexical"),        # 单件上限为30公斤。
    (5, len(BASE) + 3, "lexical"),        # 夜间派送附加费为每单8元。
    (7, len(BASE) + 4, "lexical"),        # 代收货款服务费率为货值的1%。
    (2, len(BASE) + len(NEAR_VERBATIM) + 0, "structural"),   # 续重部分按每公斤加收 3 元。
    (3, len(BASE) + len(NEAR_VERBATIM) + 1, "structural"),   # 单件重量上限为 30 公斤。
    (5, len(BASE) + len(NEAR_VERBATIM) + 2, "structural"),   # 夜间派送附加费按每单收 8 元。
    (7, len(BASE) + len(NEAR_VERBATIM) + 3, "structural"),   # 代收货款的服务费率为货值的 1%。
    (14, len(BASE) + len(NEAR_VERBATIM) + 4, "structural"),  # 偏远区域附加费按每单收 15 元。
]
# 标注：**非重复**对照对（必须不被判冗余）—— 数字指纹不同或语义不同
NON_DUP_PAIRS = [
    (0, 1), (2, 3), (5, 6), (7, 8), (10, 11), (14, 15), (18, 19), (21, 22), (23, 24), (25, 26),
]

LEX_GRID = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
STRUCT_GRID = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]


def evaluate(lex_thr: float, struct_thr: float) -> dict:
    j = RedundancyJudge(lex_thr, struct_thr)
    hits = {}
    for (i, k, kind) in DUP_PAIRS:
        hits[(i, k)] = (j.impl1(CLAIMS[i], CLAIMS[k]), j.impl2(CLAIMS[i], CLAIMS[k]))
    fp = []
    for (i, k) in NON_DUP_PAIRS:
        h1, h2 = j.impl1(CLAIMS[i], CLAIMS[k]), j.impl2(CLAIMS[i], CLAIMS[k])
        if h1 or h2:
            fp.append(dict(i=i, k=k, text_i=CLAIMS[i], text_k=CLAIMS[k],
                           impl1=h1, impl2=h2))
    strict, loose, keep1, keep2 = j.keep_sets(CLAIMS)
    lex_pairs = [d for d in DUP_PAIRS if d[2] == "lexical"]
    st_pairs = [d for d in DUP_PAIRS if d[2] == "structural"]
    lex_by_impl1 = sum(1 for d in lex_pairs if hits[(d[0], d[1])][0])
    lex_by_any = sum(1 for d in lex_pairs if any(hits[(d[0], d[1])]))
    st_by_impl2 = sum(1 for d in st_pairs if hits[(d[0], d[1])][1])
    st_by_any = sum(1 for d in st_pairs if any(hits[(d[0], d[1])]))
    impl1_hits = sum(1 for v in hits.values() if v[0])
    impl2_hits = sum(1 for v in hits.values() if v[1])
    any_caught = sum(1 for v in hits.values() if v[0] or v[1])
    return dict(
        lex_thr=lex_thr, struct_thr=struct_thr,
        n_claims=len(CLAIMS),
        lex_pairs_total=len(lex_pairs),
        struct_pairs_total=len(st_pairs),
        lex_pairs_caught_by_impl1=lex_by_impl1,
        lex_pairs_caught_by_any=lex_by_any,
        struct_pairs_caught_by_impl2=st_by_impl2,
        struct_pairs_caught_by_any=st_by_any,
        impl1_hits_all_pairs=impl1_hits,
        impl2_hits_all_pairs=impl2_hits,
        any_pairs_caught=any_caught,
        false_positive_pairs=len(fp), false_positive_detail=fp,
        n_kept_strict=len(strict), n_kept_loose=len(loose),
        n_kept_impl1=len(keep1), n_kept_impl2=len(keep2),
        missed_pairs=[dict(i=i, k=k, kind=kind,
                           impl1=hits[(i, k)][0], impl2=hits[(i, k)][1])
                      for (i, k, kind) in DUP_PAIRS if not (hits[(i, k)][0] or hits[(i, k)][1])],
    )


def main() -> int:
    base = dict(lex_thr=DEFAULTS["lex_thr"], struct_thr=DEFAULTS["struct_thr"])
    at_pre = evaluate(base["lex_thr"], base["struct_thr"])
    lex_sweep = [evaluate(t, base["struct_thr"]) for t in LEX_GRID]
    struct_sweep = [evaluate(base["lex_thr"], t) for t in STRUCT_GRID]

    out = dict(
        purpose="标定 lex_thr / struct_thr 两个离散冗余判据阈值（**离线，0 次 API 调用**）",
        calibration_set="本文件自造的合成断言语料（虚构仓储配送计费规则），"
                        "**不是** DEV 集、**不是** U1–U4",
        n_claims=len(CLAIMS),
        n_base=len(BASE), n_near_verbatim=len(NEAR_VERBATIM), n_rewritten=len(REWRITTEN),
        claims=CLAIMS,
        dup_pairs=[dict(i=i, k=k, kind=kind, text_i=CLAIMS[i], text_k=CLAIMS[k])
                   for (i, k, kind) in DUP_PAIRS],
        non_dup_pairs=[dict(i=i, k=k, text_i=CLAIMS[i], text_k=CLAIMS[k])
                       for (i, k) in NON_DUP_PAIRS],
        preregistered=base,
        reading_at_preregistered=at_pre,
        lex_sweep=lex_sweep, struct_sweep=struct_sweep,
    )
    p = os.path.join(HERE, "calibration_log.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    t = os.path.join(HERE, "calibration_log.txt")
    with open(t, "w", encoding="utf-8") as f:
        f.write("路线 A · 冗余判据阈值标定日志（离线，0 次 API 调用）\n")
        f.write("标定集：%s\n\n" % out["calibration_set"])
        f.write("语料规模：%d 条断言（基础 %d / 近逐字重复 %d / 改写型重复 %d）\n"
                % (len(CLAIMS), len(BASE), len(NEAR_VERBATIM), len(REWRITTEN)))
        f.write("标注：近逐字重复对 %d 组、改写型重复对 %d 组、非重复对照对 %d 组\n\n"
                % (at_pre["lex_pairs_total"], at_pre["struct_pairs_total"],
                   len(NON_DUP_PAIRS)))
        f.write("【预注册值读数】lex_thr=%.2f  struct_thr=%.2f\n" % (base["lex_thr"], base["struct_thr"]))
        f.write("  近逐字重复对被实现1（词法）命中：%d / %d；被任一实现命中：%d / %d\n"
                % (at_pre["lex_pairs_caught_by_impl1"], at_pre["lex_pairs_total"],
                   at_pre["lex_pairs_caught_by_any"], at_pre["lex_pairs_total"]))
        f.write("  改写型重复对被实现2（结构）命中：%d / %d；被任一实现命中：%d / %d\n"
                % (at_pre["struct_pairs_caught_by_impl2"], at_pre["struct_pairs_total"],
                   at_pre["struct_pairs_caught_by_any"], at_pre["struct_pairs_total"]))
        f.write("  全部标注重复对被任一实现命中：%d / %d\n"
                % (at_pre["any_pairs_caught"],
                   at_pre["lex_pairs_total"] + at_pre["struct_pairs_total"]))
        f.write("  **误杀**（非重复对被判冗余）：%d 组\n" % at_pre["false_positive_pairs"])
        for fp in at_pre["false_positive_detail"]:
            f.write("      - %s  ||  %s  (impl1=%s impl2=%s)\n"
                    % (fp["text_i"], fp["text_k"], fp["impl1"], fp["impl2"]))
        f.write("  漏掉的重复对：%d 组\n" % len(at_pre["missed_pairs"]))
        for m in at_pre["missed_pairs"]:
            f.write("      - %s  ||  %s  (impl1=%s impl2=%s)\n"
                    % (CLAIMS[m["i"]], CLAIMS[m["k"]], m["impl1"], m["impl2"]))
        f.write("  贪心 keep 集：strict=%d / loose=%d / impl1=%d / impl2=%d（语料共 %d 条）\n\n"
                % (at_pre["n_kept_strict"], at_pre["n_kept_loose"],
                   at_pre["n_kept_impl1"], at_pre["n_kept_impl2"], len(CLAIMS)))
        f.write("【lex_thr 扫描】（struct_thr 固定在预注册值）\n")
        f.write("  %-6s %-12s %-12s %-8s %-12s %-8s\n"
                % ("lex", "词法命中词法对", "结构命中改写对", "误杀", "kept_strict", "kept_loose"))
        for s in lex_sweep:
            f.write("  %-6.2f %-12d %-12d %-8d %-12d %-8d\n"
                    % (s["lex_thr"], s["lex_pairs_caught_by_impl1"],
                       s["struct_pairs_caught_by_impl2"],
                       s["false_positive_pairs"], s["n_kept_strict"], s["n_kept_loose"]))
        f.write("\n【struct_thr 扫描】（lex_thr 固定在预注册值）\n")
        f.write("  %-8s %-12s %-12s %-8s %-12s %-8s\n"
                % ("struct", "词法命中词法对", "结构命中改写对", "误杀", "kept_strict", "kept_loose"))
        for s in struct_sweep:
            f.write("  %-8.2f %-12d %-12d %-8d %-12d %-8d\n"
                    % (s["struct_thr"], s["lex_pairs_caught_by_impl1"],
                       s["struct_pairs_caught_by_impl2"],
                       s["false_positive_pairs"], s["n_kept_strict"], s["n_kept_loose"]))
        f.write("\n结论（人读）：阈值是**工程默认值**，在本合成语料上验证过读数；\n")
        f.write("  语料规模小、领域单一 ⇒ 不能声称「已最优标定」。真实数据上的表现未知。\n")

    print("标定完成：%s / %s" % (p, t))
    print("预注册值读数：近逐字对 impl1 命中 %d/%d；改写对 impl2 命中 %d/%d；"
          "全部重复对命中 %d/%d；误杀 %d 组；kept_strict=%d/%d"
          % (at_pre["lex_pairs_caught_by_impl1"], at_pre["lex_pairs_total"],
             at_pre["struct_pairs_caught_by_impl2"], at_pre["struct_pairs_total"],
             at_pre["any_pairs_caught"],
             at_pre["lex_pairs_total"] + at_pre["struct_pairs_total"],
             at_pre["false_positive_pairs"], at_pre["n_kept_strict"], len(CLAIMS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
