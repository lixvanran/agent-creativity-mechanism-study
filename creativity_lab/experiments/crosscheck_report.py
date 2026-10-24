#!/usr/bin/env python3
"""**报告 ↔ 数据 交叉核对**（防转写错误）

> 落点：`creativity_lab/experiments/crosscheck_report.py`
> 用法：`python3 -B creativity_lab/experiments/crosscheck_report.py <报告.md>`
> ⇒ 从各 run 的 manifest 重算关键量，检查报告里是否**逐字**出现该数字。
> ⇒ 报不出来 = 报告里写错了，或用了别的口径 ⇒ **必须查清楚再交付**。
>
> ★ 为什么要固化：今晚我在方差分解上踩过 —— 表脚本用**均值**、报告按**均值**写，
>   而我核对时用**中位** ⇒ 比值 1.3× vs 2.1× ⇒ **同一份材料里两套口径**。
>   ⇒ ⇒ 核对必须是**脚本**，不能靠眼睛。
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ★ ★ 路径修正（★ 2026-10-24 ★）：★ 原来指向 2026-10-23（★ 那个目录【不存在】★）
#   ★ ★ ⇒ ★ 【发散层那一整块检查从来没执行过】★ ★ 而我方一直报「48/48 全绿」
#   ★ ★ ⇒ ★ 这正是「跳过检查并报绿」的最阴形态：★ 不报错、★ 不红、★ 措辞完全正常 ★★
#   ★ ★ ⇒ ★ 现指向真实存在的批目录；★ 且【必读输入缺失 ⇒ 响亮失败】已兜住 ★
DIVERGE = os.path.join(ROOT, "runs", "divergence-matrix-2026-10-24")
ENDSTEP = os.path.join(ROOT, "runs", "endstep-matrix-2026-10-23")
EVAL = os.path.join(ROOT, "runs", "evaluator-strength-2026-10-24")


def med(v: List[float]):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


# ★ ★★ 必须存在的输入登记表（★ 2026-10-24 ★）★★
#   ★ ★ 背景：★ 第 1 层论证线报「挪走 gate_alignment.json ⇒ 12 项整块静默跳过 ⇒ ★
#   ★ ★ 而退出码仍是 0、输出还写着『全部一致』」★ ⇒ ★ 我方自查：★ 本工具【同样有】★
#   ★ ★ 6 处 `if os.path.exists(...)` 包着检查块 ⇒ ★ 缺 manifest ⇒ 那组检查【整块消失】★
#   ★ ★ 而 `checked` 变少、★ 输出仍是「✔ 无缺失」★ ⇒ ★ **最阴的一种假绿** ★★
#   ★ ★ ⇒ ★ 落法（★ 两条 ★）：★
#   ★ ★   ① **必须存在的输入缺失 ⇒ 响亮失败**（★ 不再「跳过并报绿」★）★★
#   ★ ★   ② **项数断言**：★ checked < 下界 ⇒ 报红（★ 通用网：★ 任何块被跳过项数就会变 ★）★★
REQUIRED_INPUTS = {
    "DIVERGE": os.path.join(DIVERGE, "manifest.json"),
    "ENDSTEP": os.path.join(ENDSTEP, "manifest.json"),
    "EVAL": os.path.join(EVAL, "manifest.json"),
    "divergence-matrix-2026-10-24": os.path.join(ROOT, "runs", "divergence-matrix-2026-10-24", "manifest.json"),
    "divergence-pathmulti-2026-10-24": os.path.join(ROOT, "runs", "divergence-pathmulti-2026-10-24", "manifest.json"),
}

# ★ ★ 项数下界（★ 2026-10-24 实测后从 48 提到 69 ★）★★
#   ★ ★ 原来 48 是【错的】：★ 那是因为 DIVERGE 路径指错 ⇒ ★ 发散层那 21 项【从未执行】
#   ★ ★ ⇒ ★ 「48/48 全绿」里有 21 项是【不存在】的检查 ★★ ⇒ ★ 现以 69 为下界 ★
EXPECTED_MIN_CHECKS = 69

# ★ ★ 项数下界可被环境变量覆盖（★ 只给自测用 ★）★★
#   ★ ★ 用途：★ 让自测能【把它改坏】⇒ ★ 验证「项数断言真在判定路径上」★★
#   ★ ★ （★ 第 1 层论证线 2026-10-24：★ 「断言写了但没接上」⇒ ★ 表现与恒真检查项一样 ★）★★
_env_min = os.environ.get("CROSSCHECK_EXPECTED_MIN")
if _env_min:
    EXPECTED_MIN_CHECKS = int(_env_min)

# ★ ★ 模拟缺失（★ 只给 --self-test 用 ★）⇒ ★ 走【同一条代码路径】⇒ ★ 自测不是假的 ★
_SIMULATE_MISSING = os.environ.get("CROSSCHECK_SIMULATE_MISSING", "")


def _input_ok(name: str) -> bool:
    """★ 输入是否可用 ★
    ★ ★ 常态：★ 看文件在不在 ★
    ★ ★ 模拟：★ `CROSSCHECK_SIMULATE_MISSING=<name>` ⇒ ★ 强制当作【缺失】★
    ★ ★ ⇒ ★ 自测走的是【和真实缺失完全相同的分支】⇒ ★ 证明「会红」有效 ★"""
    if _SIMULATE_MISSING and name in _SIMULATE_MISSING.split(","):
        return False
    return os.path.exists(REQUIRED_INPUTS[name])


def main() -> int:
    import argparse as _ap
    _apx = _ap.ArgumentParser(add_help=False)
    _apx.add_argument("--json-out", default=None)
    _args, _rest = _apx.parse_known_args(sys.argv[1:])
    if len(_rest) < 1:
        print(__doc__)
        return 1
    rep = open(_rest[0], encoding="utf-8").read().replace("−", "-")
    missing: List[str] = []
    checked = 0

    # 报告里出现的所有数字（做**数值容差匹配** ⇒ 0.22 与 0.2222 视为一致）
    import re as _re
    _nums = set()
    for _t in _re.findall(r"-?\d+\.\d+", rep):
        try:
            f = float(_t)
        except Exception:                              # noqa: BLE001
            continue
        for _d in (0, 1, 2, 3, 4):
            _nums.add(round(f, _d))
    _ints = set()
    for _t in _re.findall(r"(?<![.\d])\d+(?![.\d])", rep):
        try:
            _ints.add(int(_t))
        except Exception:                              # noqa: BLE001
            continue

    # ★ ★ 弱检查清单（★ 2026-10-24 新增 · ★ 第 1 层论证线的反面案例逼出来的 ★）★★
    #   ★ 本检查器是【子串包含】式的 ⇒ ★ 「报告里有这个串」只证明【某处有】★
    #   ⇒ ★ 若该串在报告里出现 ≥2 次 ⇒ ★ 改一处、别处仍命中 ⇒ ★ **该项抓不到变异** ★
    #   ⇒ ★ 故：**命中时记录出现次数** ⇒ ★ 出现 ≥2 次的项标为【弱检查】★（★ 不是假绿，★ 但强度不够 ★）
    weak: List[tuple] = []

    def _note_hit(label, s):
        _c = rep.count(s)
        if _c >= 2:
            weak.append((label, s, _c))

    def need(s: str, label: str):
        nonlocal checked
        checked += 1
        if s in rep:
            _note_hit(label, s)
            return
        try:                                            # ★ 数值容差：把**待查值**舍入后
            f = float(s)                               #   看是否等于报告里出现过的数
            for d in range(5):                         #   （0.2222 ⇒ 0.22 ⇒ 命中「0.22」）
                if round(f, d) in _nums:
                    _note_hit(label, s)
                    return
            if any(abs(f - n) < 1e-9 for n in _nums):
                _note_hit(label, s)
                return
        except Exception:                              # noqa: BLE001
            pass
        missing.append("%s ⇒ 报告里找不到「%s」" % (label, s))

    # ── 发散层 ──
    if _input_ok("DIVERGE"):
        man = json.load(open(os.path.join(DIVERGE, "manifest.json"), encoding="utf-8"))
        groups = [g for g in man["groups"] if g.get("arms")]
        tids = sorted({g["tid"] for g in groups})
        arms = ["base", "same_model", "one_frame", "n3", "n8"]
        per = {}
        for arm in arms:
            for tid in tids:
                vs = [g["arms"][arm]["effective_rank_per_n"] for g in groups
                      if g["tid"] == tid and g["arms"].get(arm, {}).get("valid")]
                if vs:
                    per[(arm, tid)] = med(vs)
        for (arm, tid), v in per.items():
            need("%.3f" % v, "发散层 %s@%s 的秩/n 中位" % (arm, tid))
        # 方差分解（中位口径）
        sd_t = [statistics.pstdev([per[(a, t)] for t in tids if (a, t) in per])
                for a in ("base", "same_model", "one_frame")]
        sd_a = [statistics.pstdev([per[(a, t)] for a in ("base", "same_model", "one_frame")
                                    if (a, t) in per]) for t in tids]
        mt, ma = med(sd_t), med(sd_a)
        need("%.3f" % mt, "跨题离散（中位）")
        need("%.3f" % ma, "跨臂离散（中位）")
        need("%.1f" % (mt / ma if ma else 0), "题间/臂间 比值")
        # 基线模态数
        for tid in tids:
            ms = [g["arms"]["base"]["modes"] for g in groups if g["tid"] == tid]
            if ms:
                need("%.1f" % (sum(ms) / len(ms)), "基线模态数 %s" % tid)

    # ── 末步 4 臂 ──
    if _input_ok("ENDSTEP"):
        man = json.load(open(os.path.join(ENDSTEP, "manifest.json"), encoding="utf-8"))
        groups = [g for g in man["groups"] if g.get("valid")]
        for arm in ("end_fuse", "end_greedy", "end_sample", "end_raw"):
            cov = med([g["arms"][arm]["covered_branches"] for g in groups])
            sur = med([g["arms"][arm]["survival_rate"] for g in groups])
            ch = med([g["arms"][arm]["out_chars"] for g in groups])
            need("%.3f" % sur, "末步 %s 面深中位" % arm)
            need("%.0f" % ch, "末步 %s 字数中位" % arm)
            need("%.1f" % cov, "末步 %s 面宽中位" % arm)

    # ── 评估器强度 ──
    if _input_ok("EVAL"):
        man = json.load(open(os.path.join(EVAL, "manifest.json"), encoding="utf-8"))
        h = man["health"]
        need(str(h.get("position_consistency")), "vote 位置一致率")
        for k, v in h.get("pairwise_agreement", {}).items():
            need("%.2f" % v, "评估器一致率 %s" % k)

    # ── 结论 2.10：加支数在「模态数」口径上的重算（第六轮 + 本批）──
    for run in ("divergence-matrix-2026-10-24", "divergence-pathmulti-2026-10-24"):
        fp = os.path.join(ROOT, "runs", run, "manifest.json")
        if not _input_ok(run):
            continue
        man = json.load(open(fp, encoding="utf-8"))
        for g in man["groups"]:
            a = g.get("arms") or {}
            if "base" in a and "n8" in a and a["base"].get("valid") and a["n8"].get("valid"):
                need("%d" % (a["n8"]["modes"] - a["base"]["modes"]), "Δ模态数 %s %s r%d" % (run, g["tid"], g["rep"]))
    # 题内中位（6 题表）
    import collections
    agg = collections.defaultdict(lambda: collections.defaultdict(list))
    for run in ("divergence-matrix-2026-10-24", "divergence-pathmulti-2026-10-24"):
        fp = os.path.join(ROOT, "runs", run, "manifest.json")
        if not _input_ok(run):
            continue
        man = json.load(open(fp, encoding="utf-8"))
        for g in man["groups"]:
            a = g.get("arms") or {}
            for arm in ("base", "n8"):
                if arm in a and a[arm].get("valid"):
                    agg[g["tid"]][arm].append(a[arm]["modes"])
    for tid, d in sorted(agg.items()):
        if "base" in d and "n8" in d:
            need("%.1f" % med(d["base"]), "base 模态中位 %s" % tid)
            need("%.1f" % med(d["n8"]), "n8 模态中位 %s" % tid)

    # ── 结论 2.11：路径多样批通道健康 ──
    pm = os.path.join(ROOT, "runs", "divergence-pathmulti-2026-10-24", "manifest.json")
    if _input_ok("divergence-pathmulti-2026-10-24"):
        h = json.load(open(pm, encoding="utf-8"))["health"]
        need(str(h.get("n_calls_total")), "pathmulti 调用总数")
        need(str(h.get("n_calls_failed")), "pathmulti 失败数")

    # ★ ★ ① 必须存在的输入缺失 ⇒ 响亮失败（★ 不再「跳过并报绿」★）★★
    _missing_inputs = [k for k in REQUIRED_INPUTS if not _input_ok(k)]
    if _missing_inputs:
        print("  ✘✘ 必读输入缺失：%s" % ", ".join(sorted(_missing_inputs)))
        for _k in sorted(_missing_inputs):
            print("     - %s ⇒ %s" % (_k, REQUIRED_INPUTS[_k]))
        print("  ⇒ ★ **响亮失败**：★ 缺输入 ⇒ 检查块会被整块跳过 ⇒ 报绿是假的 ★")
        print("  ⇒ ★ 修复：★ 补齐这些输入；★ 若确实要豁免，★ 必须在 REQUIRED_INPUTS 里显式登记理由 ★")
        return 3

    print("== 交叉核对：报告 vs 数据 ==")
    print("  检查项：%d（★ 下界 %d ★）" % (checked, EXPECTED_MIN_CHECKS))
    if checked < EXPECTED_MIN_CHECKS:
        print("  ✘✘ 项数断言失败：★ 实际 %d < 下界 %d ⇒ ★ **有检查块被静默跳过** ★"
              % (checked, EXPECTED_MIN_CHECKS))
        print("  ⇒ ★ 退出码 3（★ 不用 exit 0 报绿 ★）")
        return 3
    if weak:
        print("  ★ ★ 弱检查项：%d / %d（★ 期望串在报告里出现 ≥2 次 ⇒ ★ 只能证明「某处有」⇒ ★ 改一处抓不到 ★）" % (len(weak), checked))
        print("     ★ ★ ★ 「本检查器全绿」【不是】数字正确性的证据 ★ ★ ★")
        print("     ★ 本报告的数字正确性由【脚本回填 + 逐格结构化核对 + 幂等】保证，★ 不由本检查器保证 ★")
        for _lab, _s, _c in weak:
            print("     - %-34s 期望「%s」出现 %d 次" % (_lab[:34], _s[:36], _c))
    if _args.json_out:
        import json as _json
        _out = {"checked": checked, "n_weak": len(weak),
                "weak": [{"label": l, "expect": s, "occurrences": c} for l, s, c in weak],
                "n_missing": len(missing), "missing": missing}
        with open(_args.json_out, "w", encoding="utf-8") as _f:
            _json.dump(_out, _f, ensure_ascii=False, indent=1, sort_keys=True)
        print("✔ 落盘 %s" % _args.json_out)
    if missing:
        print("  ✘ 报告里找不到 %d 项：" % len(missing))
        for m in missing:
            print("     - %s" % m)
        return 1
    print("  ✔ 无缺失（★ 但请看上面的弱检查计数：★ %d / %d 项只是【存在性检查】★）" % (len(weak), checked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
