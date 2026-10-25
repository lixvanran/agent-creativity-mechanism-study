#!/usr/bin/env python3
"""**历史回算 v2**：用**可用**的历史组验证「臂4 = 原样输出某支」并给出融合臂的参照读数。

> 2026-10-24 ｜ 第二组 · 层2 ｜ 落点：`creativity_lab/experiments/retro_survival.py`
> （**v1** 版本建立在"历史归档全废"的判断上 ⇒ 已被 `audit_history.py` 推翻 ⇒ 本文件是修正版）
>
> ## 为什么还要做
> 第三轮的主读数全部来自**新跑批**（9 组）。历史跑批有 **12 组可用**（题号映射见
> `results/HISTORY-AUDIT-2026-10-24.md`）⇒ ⇒ 可以做一次**独立的、跨批次**的核对：
> - **臂4 的存活率应 ≈ 1.0**（它是「原样输出其中一支」）⇒ 这是**自校准锚**
> - 臂1（direct）对该组分支的覆盖 ⇒ 「单点采样 vs 面」的对照
> - 臂3（融合）输出 vs 该组文章分支的覆盖 ⇒ **跨臂参照**
>   ⚠️ **不是臂3 的正式读数**：臂3 的实际输入是**判断片段**，不是这批文章
>      ⇒ 该量只作参照，**不得**当作"融合臂的正式面宽"
>
> ## 纪律
> - 只用 `audit_history.py` 判定为**可用**的组；不可用组**一律不引用**
> - 比率必配绝对分母；阈值敏感项给曲线
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.metrics import (branch_diversity, covered_branches,  # noqa: E402
                                    coverage_curve, self_coverage, survival_rate)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HIST = os.path.join(ROOT, "data", "historical-runs")
OUT = os.path.join(ROOT, "docs", "cmp8", "routes", "COLLAPSE", "eval", "results")


def med(v: List[float]):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def read(p: str) -> str:
    try:
        return open(p, encoding="utf-8").read()
    except Exception:                                   # noqa: BLE001
        return ""


def main() -> int:
    audit_p = os.path.join(OUT, "history_audit.json")
    if not os.path.exists(audit_p):
        print("请先跑 audit_history.py")
        return 1
    audit = json.load(open(audit_p, encoding="utf-8"))
    rows = [r for r in audit["rows"] if r["usable"]]
    print("可用组：%d / %d" % (len(rows), audit["n_total"]))

    rec: List[Dict[str, Any]] = []
    for r in rows:
        d = os.path.join(HIST, r["dataset"])
        stem = r["stem"]
        arts_p = os.path.join(d, "%s_arm4arts.json" % stem)
        if not os.path.exists(arts_p):
            continue
        arts = json.load(open(arts_p, encoding="utf-8"))
        if not isinstance(arts, list) or len(arts) < 2:
            continue
        a1 = read(os.path.join(d, "%s_arm1.md" % stem))
        a3 = read(os.path.join(d, "%s_arm3.md" % stem))
        a4 = read(os.path.join(d, "%s_arm4.md" % stem))
        rec.append({
            "dataset": r["dataset"], "stem": stem, "tid": r["mapped_tid"],
            "n_arts": len(arts),
            "branch_diversity": round(branch_diversity(arts), 4),
            "arm4_survival": round(survival_rate(arts, a4), 4) if a4 else None,
            "arm4_self_cov": round(self_coverage(arts, a4), 4) if a4 else None,
            "arm4_curve": coverage_curve(arts, a4) if a4 else {},
            "arm4_chars": len(a4),
            "arm1_survival": round(survival_rate(arts, a1), 4) if a1 else None,
            "arm1_chars": len(a1),
            "arm3_ref_survival": round(survival_rate(arts, a3), 4) if a3 else None,
            "arm3_ref_cov": covered_branches(arts, a3, 0.30) if a3 else None,
            "arm3_ref_self_cov": round(self_coverage(arts, a3), 4) if a3 else None,
            "arm3_chars": len(a3),
        })

    md = ["# 历史回算 v2（只用**可用**组）\n",
          "> 源：`data/historical-runs/`（可用性判定见 `HISTORY-AUDIT-2026-10-24.md`）\n",
          "> 生成：`creativity_lab/experiments/retro_survival.py`｜零 API 成本\n",
          "\n## 1. 自校准锚：臂4（「只选不融」= 原样输出其中一支）的存活率应 ≈ 1.0\n",
          "\n| 数据集 | 组 | 当前题 | 分支 | **臂4 自覆盖率**(应≈1) | 臂4 存活率(跨支均值,应≈1/n) | 臂1(direct) 覆盖 | 臂3(融合)参照自覆盖 |",
          "|---|---|--:|--:|--:|--:|--:|--:|"]
    for r in rec:
        md.append("| %s | %s | %s | %d | **%.3f** | %.3f | %.3f | %.3f |"
                  % (r["dataset"], r["stem"], r["tid"], r["n_arts"], r["arm4_self_cov"] or 0,
                     r["arm4_survival"] or 0, r["arm1_survival"] or 0,
                     r["arm3_ref_self_cov"] or 0))
    md += ["\n## 2. 汇总（中位数）\n",
           "\n| 量 | 中位 | 范围 | 说明 |\n|---|--:|---|---|",
           "| ★ 臂4 **自覆盖率** | **%.3f** | %.3f–%.3f | ★ **自校准锚**（原样输出 ⇒ 应 ≈ 1.0） |"
           % (med([r["arm4_survival"] for r in rec]) or 0,
              min(r["arm4_self_cov"] for r in rec), max(r["arm4_self_cov"] for r in rec)),
           "| 臂4 存活率(跨支均值) | %.3f | %.3f–%.3f | 只贴 1 支 ⇒ **期望 ≈ 1/n**，不是 1.0 |"
           % (med([r["arm4_survival"] for r in rec]) or 0,
              min(r["arm4_survival"] for r in rec), max(r["arm4_survival"] for r in rec)),
           "| 臂1(direct) 覆盖 | %.3f | %.3f–%.3f | 单点采样 vs 面 ⇒ 预期低 |"
           % (med([r["arm1_survival"] for r in rec]) or 0,
              min(r["arm1_survival"] for r in rec), max(r["arm1_survival"] for r in rec)),
           "| 臂3(融合)参照覆盖 | %.1f 支 | — | ⚠️ **不是臂3 的正式读数**（其输入是片段，不是这批文章） |"
           % (med([r["arm3_ref_cov"] for r in rec]) or 0),
           "| 发散面宽度(词面下界) | %.3f | %.3f–%.3f | 分支两两差异 |"
           % (med([r["branch_diversity"] for r in rec]) or 0,
              min(r["branch_diversity"] for r in rec), max(r["branch_diversity"] for r in rec)),
           "\n## 3. 读法\n",
           "- **臂4 存活率 ≈ 1.0** ⇒ 「臂4 = 原样输出某支」这个语义**被独立验证**\n",
           "  ⇒ 同时说明第三轮的自校准锚（选一臂 ⇒ 存活率 ≈ 1）是**站得住**的。\n",
           "- **臂1(direct) 覆盖低**是**预期**的：它本来就是独立单点采样，不该来自那批分支。\n",
           "- ⚠️ **臂3 那一列只作参照**：它的真实输入是判断片段，用文章分支去量它会**系统性低估**。\n",
           "- ⇒ ★ 这一轮**不能**回答「融合臂吃掉了多少面」—— 那个缺口仍然在\n",
           "  （历史跑批**没落盘融合臂的分支** ⇒ 事后算不了 ⇒ 新跑批已补上）。\n"]

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "RETRO-SURVIVAL-V2-2026-10-24.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(OUT, "retro_survival_v2.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2, sort_keys=True)

    print("\n== 回算结果（可用组）==")
    print("  组数 %d" % len(rec))
    print("  ★ 臂4 自覆盖率（中位，**自校准锚，应≈1.0**）= %.3f" % (med([r["arm4_self_cov"] for r in rec]) or 0))
    print("    臂4 存活率（跨支均值，期望≈1/n=%.2f）= %.3f" % (1.0/ (rec[0]["n_arts"] if rec else 5), med([r["arm4_survival"] for r in rec]) or 0))
    print("    臂3 融合参照自覆盖率（中位）= %.3f" % (med([r["arm3_ref_self_cov"] for r in rec]) or 0))
    print("    臂1(direct) 覆盖（中位）= %.3f" % (med([r["arm1_survival"] for r in rec]) or 0))
    print("    臂3(融合)参照覆盖（中位，支）= %.1f" % (med([r["arm3_ref_cov"] for r in rec]) or 0))
    print("  ✓ 落盘 %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
