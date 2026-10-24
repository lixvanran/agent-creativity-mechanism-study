#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 单测：★ `gate_policy.py` 的【判官健康度闸门】会不会红 ★（★ 2026-10-24 ★）★★

★ ★★ 为什么这个测试存在（★ 事件）★★
★ 第 1 层论证线 2026-10-24 转述：★ 「★ 若 verdicts.json 缺失或为空 ⇒ `verd.get(arm, {})` 恒为 `{}`
★   ⇒ 每条断言的判定都落默认「解析失败」⇒ ★ 矛盾分子 = 0 ⇒ ★ 矛盾率显示成 0.0% ★
★   ⇒ ★ 那不是「没有矛盾」，那是【判官没跑】★ ★」
★ ⇒ ★ ★★ 我方回源确认同族（★ `creativity_lab/gate_policy.py:151` ★）：
★   ★ `v = verd.get(c, "解析失败")` ⇒ ★ 【verd 为空 ⇒ C=0 ⇒ 矛盾率 0.0%】★★ ★
★   ★ ⇒ ★ 而且【支持率也同时是 0.0%】⇒ ★ 看着像「完美」⇒ ★ 更危险 ★★
★ ⇒ ★ ★★ 我方比对方多一处【更隐蔽】的形态 ★★ ★★
★   ★ 【只部分臂失败】时（★ 例：A 臂 100% 解析失败、B 臂健康 ★）⇒ ★ A 臂照常输出
★   ★ 「支持 0.0% / 矛盾 0.0%」⇒ ★ ★ 【只看全局解析失败率会掩盖它】★★ ★★
★ ⇒ ★ ⇒ ★ 落法：★ 闸门【按臂】分别算 + 【全局无任何真实判定】也 fail ★★
★ ⇒ ★ ★★ 闸门【不产出任何读数】：★ 它在写 summary.json 之前 exit ⇒ ★
★   ★ 「矛盾率 0.0%」永远进不了交稿读数 ★★ ★

★ ★★ 纪律：★ 变异的判据必须【点名预期的那一处】★★ ★
★   ★ ⇒ ★ 本测试不仅验「会不会红」，还验「红的是不是该红的那一处」★
★   ★ ⇒ ★ 且 T6 用【改阈值】这个真变异证明判据【有分辨力】（★ 而不是恒真 ★）★★ ★
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from selftest_kit import check, suite          # noqa: E402
import creativity_lab.gate_policy as GP         # noqa: E402


def _fixtures():
    """★ 造一份【形状与真实读数一致】的假读数 ★（★ 不造自造结构 ★）★★ ★

    ★ ⇒ ★ 断言集合直接取自【真实的 TOPICS 与真实题面】★
    ★ ⇒ ★ claims 的键形如「<tid>|<arm>|<n>」⇒ ★ 与 by 的构造一致 ★
    """
    tids = [t["tid"] for t in GP.TOPICS]
    by = {}
    claims = {}
    for i, tid in enumerate(tids):
        by[tid] = {}
        for arm in GP.ARMS:
            cs = ["断言文本-%s-%s-%d" % (tid, arm, k) for k in range(3)]
            by[tid][arm] = cs
            for k, c in enumerate(cs):
                claims["%s|%s|%d" % (tid, arm, k)] = [c]
    return by, claims


def _all_claims(by):
    out = []
    for tid, arms in by.items():
        for arm, cs in arms.items():
            out.extend(cs)
    return out


def _verd_healthy(by):
    """★ 全部断言都有【真实判定】★（★ 合法判定含「未提及」「非主张」★★ ★）"""
    v = {}
    for i, c in enumerate(_all_claims(by)):
        v[c] = ("支持", "矛盾", "未提及", "非主张")[i % 4]
    return v


def _verd_empty(by):
    return {}


def _verd_one_arm_dead(by, dead_arm):
    """★ 只有【一个臂】全落「解析失败」，★ 其余臂健康 ★（★ 最隐蔽的形态 ★）"""
    v = {}
    for tid, arms in by.items():
        for arm, cs in arms.items():
            for c in cs:
                v[c] = "解析失败" if arm == dead_arm else "支持"
    return v


def test_gate_logic():
    by, claims = _fixtures()

    # ── T1：verd 全空 ⇒ 必须不通过，且理由点名「无任何判定」──────
    ok, info = GP.judge_health_gate({a: by[GP.TOPICS[0]["tid"]][a] for a in GP.ARMS},
                                     _verd_empty(by))
    check("T1 verd 全空 ⇒ 闸门不通过", ok is False, "ok=%r" % (ok,))
    check("T1 理由点名「无任何判定」",
          any("无任何判定" in r for r in info["reasons"]),
          "reasons=%r" % (info["reasons"],))
    check("T1 给了绝对分母（总断言数 > 0）", info["total_n_claims"] > 0,
          "total_n_claims=%r" % (info["total_n_claims"],))

    # ── T2：★ 只一个臂死 ⇒ 必须不通过，且理由【点名那个臂】★★ ★
    dead = GP.ARMS[0]
    cl_by_arm = {a: by[GP.TOPICS[0]["tid"]][a] for a in GP.ARMS}
    ok, info = GP.judge_health_gate(cl_by_arm, _verd_one_arm_dead(by, dead))
    check("T2 单臂全解析失败 ⇒ 闸门不通过（★ 不被全局掩盖 ★）", ok is False, "ok=%r" % (ok,))
    check("T2 理由点名了那个臂 %s" % dead,
          any(("臂 %s" % dead) in r for r in info["reasons"]),
          "reasons=%r" % (info["reasons"],))
    rows = {r["arm"]: r for r in info["rows"]}
    check("T2 该臂 parse_fail_rate = 1.0",
          abs(rows[dead]["parse_fail_rate"] - 1.0) < 1e-9,
          "rate=%r" % (rows[dead]["parse_fail_rate"],))
    check("T2 其余臂 parse_fail_rate = 0.0",
          all(abs(rows[a]["parse_fail_rate"]) < 1e-9 for a in GP.ARMS if a != dead),
          "rows=%r" % (info["rows"],))

    # ── T3：健康 ⇒ 必须通过 ─────────────────────────────────────
    ok, info = GP.judge_health_gate(cl_by_arm, _verd_healthy(by))
    check("T3 全部已判 ⇒ 闸门通过", ok is True, "ok=%r reasons=%r" % (ok, info["reasons"]))

    # ── T4：★ 解析失败率 11%（>10%）⇒ 必须不通过；9% ⇒ 通过 ─────
    #   （★ 证明阈值【真的】在起作用，而不是恒真/恒假 ★）
    #   ★ n 必须够大：★ 否则「1 条」本身就是 12.5%（n=8）⇒ ★ 阈值两侧无法精确构造 ★
    cs = ["T4-断言-%03d" % k for k in range(100)]
    v = {c: "支持" for c in cs}
    for c in cs[:11]:                       # ★ 11/100 = 11% > 10% ★
        v[c] = "解析失败"
    ok_hi, info_hi = GP.judge_health_gate({GP.ARMS[0]: cs}, v)
    check("T4 解析失败率 11% ⇒ 不通过", ok_hi is False, "ok=%r" % (ok_hi,))
    check("T4 ★ 且红的正是那一处（★ 理由里带该臂名与绝对分母 ★）",
          any(("臂 %s" % GP.ARMS[0]) in r for r in info_hi["reasons"]),
          "reasons=%r" % (info_hi["reasons"],))
    check("T4 理由里带绝对分母 11/100",
          any("11/100" in r for r in info_hi["reasons"]),
          "reasons=%r" % (info_hi["reasons"],))
    v2 = {c: "支持" for c in cs}
    for c in cs[:9]:                        # ★ 9/100 = 9% ≤ 10% ★
        v2[c] = "解析失败"
    ok_lo, _ = GP.judge_health_gate({GP.ARMS[0]: cs}, v2)
    check("T4 解析失败率 9% ⇒ 通过（★ 阈值不是恒真 ★）", ok_lo is True, "ok=%r" % (ok_lo,))

def test_write_report_behavior():
    """★★ 行为级：★ 闸门失败 ⇒ 【summary.json 根本不写出】★★ ★"""
    by, claims = _fixtures()
    tmp = tempfile.mkdtemp(prefix="g2gate_")
    try:
        # ── T5：verd 全空 ⇒ 返回 10 且 summary.json 不存在 ────────
        rc = GP.write_report({}, claims, _verd_empty(by), [], by, tmp)
        check("T5 闸门失败 ⇒ 返回 GATE_EXIT(=10)", rc == GP.GATE_EXIT, "rc=%r" % (rc,))
        check("T5 闸门失败 ⇒ summary.json 未写出",
              not os.path.exists(os.path.join(tmp, "summary.json")),
              "exists=%r" % (os.path.exists(os.path.join(tmp, "summary.json")),))

        # ── T6：健康 ⇒ 返回 0 且 summary.json 写出 + 含绝对分母 ──
        rc = GP.write_report({}, claims, _verd_healthy(by), [], by, tmp)
        check("T6 健康 ⇒ 返回 0", rc == 0, "rc=%r" % (rc,))
        fp = os.path.join(tmp, "summary.json")
        check("T6 健康 ⇒ summary.json 已写出", os.path.exists(fp), "path=%r" % (fp,))
        if os.path.exists(fp):
            d = json.load(open(fp, encoding="utf-8"))
            den = d["denominators"][GP.ARMS[0]]
            check("T6 读数含 n_parse_failed（★ 比率必配绝对分母 ★）",
                  "n_parse_failed" in den and isinstance(den["n_parse_failed"], int),
                  "den=%r" % (den,))
            check("T6 读数含 n_judged", "n_judged" in den, "den=%r" % (den,))
            check("T6 读数含 judge_health（★ 闸门自证随读数一起交付 ★）",
                  "judge_health" in d, "keys=%r" % (list(d.keys()),))
            check("T6 judge_health 里带每臂绝对数",
                  all("n_parse_failed" in r for r in d["judge_health"]["rows"]),
                  "rows=%r" % (d["judge_health"]["rows"],))

        # ── T7：★ 单臂死 ⇒ 也必须【不落盘】（★ 行为级证明「不产出任何读数」）★★
        tmp2 = tempfile.mkdtemp(prefix="g2gate2_")
        try:
            rc = GP.write_report({}, claims, _verd_one_arm_dead(by, GP.ARMS[0]), [], by, tmp2)
            check("T7 单臂全解析失败 ⇒ 返回 10", rc == GP.GATE_EXIT, "rc=%r" % (rc,))
            check("T7 单臂全解析失败 ⇒ summary.json 未写出",
                  not os.path.exists(os.path.join(tmp2, "summary.json")),
                  "exists=%r" % (os.path.exists(os.path.join(tmp2, "summary.json")),))
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_criterion_has_discriminating_power():
    """★★ T8：★ 判据【有分辨力】的证明：★ 真变异必须改变结论 ★★
    ★ ★★ 纪律：★ 「变异注入全绿」本身也可能是假的（★ 判据恒真 ★）★★ ★
    ★ ⇒ ★ 这里用【真变异】把阈值改大 ⇒ ★ 若判据有分辨力 ⇒ ★ T2 的结论必须【翻转】★★ ★
    """
    by, _claims = _fixtures()
    cl_by_arm = {a: by[GP.TOPICS[0]["tid"]][a] for a in GP.ARMS}
    dead = GP.ARMS[0]
    verd = _verd_one_arm_dead(by, dead)
    ok_before, _ = GP.judge_health_gate(cl_by_arm, verd)
    orig = GP.MAX_PARSE_FAIL_RATE
    try:
        GP.MAX_PARSE_FAIL_RATE = 1.0        # ★ 真变异：★ 把阈值放宽到 100% ★
        ok_after, _ = GP.judge_health_gate(cl_by_arm, verd)
    finally:
        GP.MAX_PARSE_FAIL_RATE = orig
    check("T8 变异前：单臂死 ⇒ 不通过", ok_before is False, "ok=%r" % (ok_before,))
    check("T8 ★ 变异后（阈值放宽到 100%）⇒ 结论【翻转】为通过（★ 证明判据有分辨力 ★）",
          ok_after is True, "ok=%r" % (ok_after,))
    check("T8 阈值已复原", GP.MAX_PARSE_FAIL_RATE == orig,
          "now=%r orig=%r" % (GP.MAX_PARSE_FAIL_RATE, orig))


def main():
    su = suite()
    su.run("判官健康度闸门·逻辑", test_gate_logic)
    su.run("判官健康度闸门·写盘行为", test_write_report_behavior)
    su.run("判据有分辨力·真变异", test_criterion_has_discriminating_power)
    # ★ ★★ 退出码语义（★ 2026-10-24 修 ★）：★ `suite.report()` 返【0=成功 / 1=失败】★★
    #   ★ ⇒ ★ 必须【直接 return 它】★★ ⇒ ★ ★ 不能写 `0 if su.report() else 1` ★★
    #   ★   ★ ★ 因为 report()=1（失败）是 truthy ⇒ ★ `0 if 1` ⇒ 返回 0 ⇒ ★ 【失败也 exit 0】★★ ★ ★
    #   ★ ⇒ ★ 这是「★ 判据的布尔语义搞反 ⇒ ★ 恒真/恒假 ★」的同族（★ 与 KI-19 同根 ★）★★ ★
    return su.report()


if __name__ == "__main__":
    sys.exit(main())
