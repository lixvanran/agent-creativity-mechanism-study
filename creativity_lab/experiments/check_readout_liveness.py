#!/usr/bin/env python3
"""★ **读数项活性检查**（★ 2026-10-25 负责人要求落地）

> 落点：`creativity_lab/experiments/check_readout_liveness.py`
> 用法：`python3 -B creativity_lab/experiments/check_readout_liveness.py <run_dir>`
> 输出：`<run_dir>/liveness_check.json`（并打印人读版）
>
> ## ★★★ 为什么要有这个（★ 判死门级教训）
> ★ **本批在跑之前，`nosel_b3` 的主读数 `post_synthesis` 恒为空串** ⇒ ⇒
> ★ **主读数恒为 `valid: false` ⇒ ⇒ H-TOPO-4a 会拿一个无效读数去比 ⇒ ⇒ 3300 次调用白跑**
> ⇒ ⇒ ★ **而它没被任何"看起来正常"的检查抓���** ⇒ ⇒ ★ **因为"跑完了、文件落了、manifest 齐了"全都不代表读数有效**
> ⇒ ⇒ ★★★ **⇒ 负责人要求：★ 每个读数项都要有一条【"这个值可能恒为空 / 恒为常量 / 定义上恒等"】的活性检查**
>
> ## ★★ 本脚本检查什么（★ 五类）
> ① **非空性**：主层/辅层的 `n` 必须 > 0 且 `valid == true`（★ 抓"恒为空"）
> ② **份数相等性**：同层各臂的份数必须相等（★ 抓"份数不等 ⇒ 不可比"）
> ③ **批内区分力**：`vendi` / `modes` / `structured_dedup` 的批内 spread_range（★ 抓"恒为常量 ⇒ 零区分力"）
> ④ **定义上恒等**：`selector_consumption` / 与"选谁"无关的读数 ⇒ 标"定义上恒等，不可用于臂间比较"
> ⑤ **失败与漏记**：`n_units` / `n_failed` / `n_calls` 的分母完整性
>
> ## ★★ 边界（★ 必须写清，否则这个脚本本身会被误用）
> ★ **它是【事后质量门】，不参与任何判决** ⇒ ⇒ 它只能【否证】（"这个读数不可用"），
> ★ **不能【正证】**（"这个读数可用"）⇒ ⇒ ★ **通过 ≠ 结论成立**
> ★ **它是在正式批【已经产生读数之后】加的** ⇒ ⇒ **它不改变任何判据**
> ★ **它不修改 run 目录的任何原始产物**（只另写一个 liveness_check.json）
"""
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ★ 定义上恒等 / 与"选谁"无关的读数 ⇒ 不可用于臂间比较
DEFINITIONALLY_IDENTICAL = {
    "selector_consumption": "★ 只依赖候选集 Vendi、与【选谁】无关 ⇒ 定义上恒等",
    "rendered_vendi1": "★ 硬编码 1.0 ⇒ 从未跑通型读数",
}


def _get(d, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def check(run_dir: str) -> dict:
    mpath = os.path.join(run_dir, "manifest.json")
    if not os.path.exists(mpath):
        return {"ok": False, "fatal": "manifest 不存在：%s" % mpath}
    m = json.load(open(mpath, encoding="utf-8"))
    groups = m.get("groups") or []
    arms = m.get("arms") or []
    issues = []          # ★ 会让某个读数不可用的真问题
    notes = []           # ★ 需要标注但不致命
    stats = {}           # 臂 → 收集到的读数
    per_arm_units = {}
    per_arm_post = {}
    per_arm_pre = {}
    per_arm_failed = {}
    per_arm_calls = {}

    for g in groups:
        for arm, d in (g.get("arms") or {}).items():
            per_arm_units.setdefault(arm, []).append(d.get("n_units"))
            per_arm_post.setdefault(arm, []).append(d.get("n_post"))
            per_arm_pre.setdefault(arm, []).append(d.get("n_pre"))
            per_arm_failed.setdefault(arm, []).append(d.get("n_failed") or 0)
            per_arm_calls.setdefault(arm, []).append(d.get("n_calls") or 0)
            rp = d.get("read_post") or {}
            rq = d.get("read_pre") or {}
            # ① 非空性
            for tag, rd, exp_n in (("主层", rp, d.get("n_post")),
                                   ("辅层", rq, d.get("n_pre"))):
                if (rd.get("n") or 0) == 0:
                    issues.append("★ %s %s r%s %s：【%s 读数为空】n=0（★ 恒为空型）"
                                  % (g.get("tid"), g.get("rep"), arm, tag, tag))
                elif rd.get("valid") is False:
                    issues.append("★ %s r%s %s %s：read.valid=false（★ 读数无效）"
                                  % (g.get("tid"), g.get("rep"), arm, tag))
                if exp_n is not None and (rd.get("n") or 0) != exp_n:
                    notes.append("%s r%s %s %s：read.n=%s ≠ 声明份数 %s"
                                 % (g.get("tid"), g.get("rep"), arm, tag,
                                    rd.get("n"), exp_n))
            for key, val in (rp.items() if isinstance(rp, dict) else []):
                if key in ("valid", "n"):
                    continue
                if isinstance(val, (int, float)):
                    stats.setdefault(arm, {}).setdefault(key, []).append(val)

    # ② 份数相等性
    for tag, dd in (("主层", per_arm_post), ("辅层", per_arm_pre)):
        vals = {a: set(x for x in v if x is not None) for a, v in dd.items()}
        if len(vals) > 1:
            uniq = {a: sorted(v) for a, v in vals.items()}
            if len({tuple(v) for v in uniq.values()}) > 1:
                issues.append("★ %s 各臂份数不相等：%s ⇒ ⇒ 绝对差值不可比" % (tag, uniq))
    # n 单元数相等
    if per_arm_units:
        uniq = {a: sorted(set(x for x in v if x is not None))
                for a, v in per_arm_units.items()}
        if len({tuple(v) for v in uniq.values()}) > 1:
            issues.append("★ 各臂 n 单元数不相等：%s ⇒ ⇒ 臂间 n 不等" % uniq)

    # ③ 批内区分力（★ 恒为常量 ⇒ 零区分力）
    spread = {}
    for arm, keys in stats.items():
        for key, vals in keys.items():
            if len(vals) < 2:
                continue
            sr = max(vals) - min(vals)
            spread.setdefault(key, {})[arm] = {"spread_range": round(sr, 6),
                                               "var": round(statistics.pvariance(vals), 8),
                                               "n": len(vals)}
            if sr == 0:
                notes.append("★ %s 的 %s 批内 spread_range=0（★ 恒为常量 ⇒ 零区分力 ⇒ 不可作主读数）"
                             % (arm, key))

    # ⑤ 分母完整性
    tot_units = {a: sum(v) for a, v in per_arm_units.items()}
    tot_calls = {a: sum(v) for a, v in per_arm_calls.items()}
    tot_failed = {a: sum(v) for a, v in per_arm_failed.items()}
    for a in tot_units:
        if tot_units[a] == 0:
            issues.append("★ 臂 %s 的 n 单元总数 = 0（★ 全丢）" % a)

    return {"ok": not issues, "run_dir": run_dir,
            "manifest_arms": arms, "n_groups": len(groups),
            "n_units_per_arm": tot_units, "n_calls_per_arm": tot_calls,
            "n_failed_per_arm": tot_failed,
            "batch_spread": spread,
            "issues": issues, "notes": notes,
            "definitional_identical_readouts": DEFINITIONALLY_IDENTICAL,
            "boundary": ("★ 本脚本是【事后质量门】：只能否证，不能正证 ⇒ 通过 ≠ 结论成立"
                         "｜★ 它在正式批产生读数之后加入 ⇒ 不改变任何判据"
                         "｜★ 不修改任何原始产物")}


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python3 -B check_readout_liveness.py <run_dir>")
        return 2
    run_dir = sys.argv[1]
    res = check(run_dir)
    print("== ★ 读数项活性检查 ==")
    print("   run_dir:", run_dir)
    if res.get("fatal"):
        print("   ✘", res["fatal"])
        return 3
    print("   n_groups=%d ｜ arms=%d" % (res["n_groups"], len(res["manifest_arms"])))
    print("   n_units/臂:", res["n_units_per_arm"])
    print("   n_calls/臂:", res["n_calls_per_arm"])
    print("   n_failed/臂:", res["n_failed_per_arm"])
    print("   批内 spread（★ =0 ⇒ 零区分力）:")
    for k, v in sorted(res["batch_spread"].items()):
        s = " ｜ ".join("%s=%.4f" % (a, d["spread_range"]) for a, d in sorted(v.items()))
        print("     %-18s %s" % (k, s))
    if res["notes"]:
        print("   ── notes（%d）──" % len(res["notes"]))
        for n in res["notes"][:20]:
            print("     ·", n)
    if res["issues"]:
        print("   ── ★ issues（%d）★ ──" % len(res["issues"]))
        for n in res["issues"][:40]:
            print("     ★", n)
        print("   ⇒ 结论：★ 有读数项不可用 ⇒ 不得进入判决")
    else:
        print("   ✔ 无致命活性问题（★ 但通过 ≠ 结论成立）")
    out = os.path.join(run_dir, "liveness_check.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("   落盘:", out)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
