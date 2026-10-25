#!/usr/bin/env python3
"""**跨批可复现性**：同参数跑两遍，读数一致吗？

> 落点：`creativity_lab/experiments/compare_batches.py`
> 用法：`python3 -B creativity_lab/experiments/compare_batches.py <runA> <runB>`
> （两个 run 目录都必须是 `divergence_matrix.py` 的输出）
>
> ★ 为什么必须做：论文里的读数要能说"我跑了两遍，结论一样"。
> ⇒ 本脚本给出**逐组逐臂**的差值 + **结论级别**的一致性判定
>   （"判决结论是否在两批之间翻转"）—— 这比"平均差多少"更贴近论文要回答的问题。
>
> ★ 口径：
> 1. **同题内比**（有效秩跨题不可比）
> 2. 报**差值范围**与**符号一致率**（不是 p 值）
> 3. 判决规则沿用 `PREREG-DIVERGENCE.md`（差值 > 0.05 且 ≥2/3 题同向）
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "cmp8", "routes", "COLLAPSE", "eval", "results")
ARMS = ["base", "same_model", "one_frame", "n3", "n8"]
LABEL = {"base": "基线", "same_model": "同型号", "one_frame": "单框架", "n3": "3 支", "n8": "8 支"}
DIFF_THR = 0.05


def load(run: str) -> Dict[str, Any]:
    p = os.path.join(ROOT, run, "manifest.json")
    if not os.path.exists(p):
        p = os.path.join(run, "manifest.json")
    man = json.load(open(p, encoding="utf-8"))
    idx: Dict[Any, Dict[str, Any]] = {}
    for g in man["groups"]:
        for arm, d in g["arms"].items():
            if d.get("valid"):
                idx[(g["tid"], g["rep"], arm)] = d
    return {"health": man["health"], "idx": idx}


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    A, B = load(sys.argv[1]), load(sys.argv[2])
    keys = sorted(set(A["idx"]) & set(B["idx"]))
    print("可比组次：%d" % len(keys))

    # ---- 逐组逐臂差值 ----
    diffs: Dict[str, List[float]] = {a: [] for a in ARMS}
    rows = []
    for k in keys:
        for a in ARMS:
            if k[2] != a:
                continue
            d1 = A["idx"][k]["effective_rank_per_n"]
            d2 = B["idx"][k]["effective_rank_per_n"]
            diffs[a].append(d2 - d1)
            rows.append((k[0], k[1], a, d1, d2, d2 - d1))

    md = ["# 跨批可复现性（同参数跑两遍）\n",
          "\n> A = `%s`｜B = `%s`\n" % (sys.argv[1], sys.argv[2]),
          "\n| 指标 | A 通道健康 | B 通道健康 |\n|---|--:|--:|",
          "| channel_health | %s | %s |" % (A["health"].get("channel_health"), B["health"].get("channel_health")),
          "\n## 1. 逐组逐臂的有效秩/n 差值（B − A）\n",
          "\n| 组 | 臂 | A | B | 差值 |\n|---|---|--:|--:|--:|"]
    for tid, rep, a, d1, d2, df in rows:
        md.append("| %s r%d | %s | %.3f | %.3f | %+.3f |" % (tid, rep, LABEL.get(a, a), d1, d2, df))

    md.append("\n## 2. 各臂差值汇总\n")
    md.append("\n| 臂 | n | 差值中位 | 差值范围 | 符号一致率(Δ>0) | 全部同号? |\n|---|--:|--:|--:|--:|:--:|")
    for a in ARMS:
        v = diffs[a]
        if not v:
            continue
        srt = sorted(v)
        m = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1] + srt[len(srt) // 2]) / 2
        pos = sum(1 for x in v if x > 0) / len(v)
        same = "✔" if (all(x > 0 for x in v) or all(x < 0 for x in v)) else ("✘" if any(x > 0 for x in v) and any(x < 0 for x in v) else "—")
        md.append("| %s | %d | %+.3f | %+.3f ~ %+.3f | %.2f | %s |"
                  % (LABEL.get(a, a), len(v), m, min(v), max(v), pos, same))

    # ---- 结论级一致性：判决是否翻转 ----
    def per_tid(run, arm):
        out = {}
        for (tid, rep, a), d in run["idx"].items():
            if a != arm:
                continue
            out.setdefault(tid, []).append(d["effective_rank_per_n"])
        return {t: (sorted(v)[len(v) // 2] if len(v) % 2
                    else (sorted(v)[len(v) // 2 - 1] + sorted(v)[len(v) // 2]) / 2)
                for t, v in out.items()}

    def verdict(run):
        base = per_tid(run, "base")
        res = {}
        for arm, direction in (("same_model", "lower"), ("one_frame", "lower"), ("n8", "higher")):
            v = per_tid(run, arm)
            n_ok = 0
            for tid in base:
                if tid not in v:
                    continue
                diff = v[tid] - base[tid]
                if (diff < -DIFF_THR) if direction == "lower" else (diff > DIFF_THR):
                    n_ok += 1
            res[arm] = n_ok
        return res

    va, vb = verdict(A), verdict(B)
    md.append("\n## 3. ★ 结论级一致性（**判决有没有翻转**）\n")
    md.append("\n> ★ **翻转的定义要说清**：论文要回答的是「这条假说**成不成立**」⇒ "
              "⇒ 翻转 = **「支持」与「不支持」之间的变化**。"
              "「否证」与「低于分辨率」**都属不支持** ⇒ 措辞不同但**结论相同** ⇒ 不算翻转。\n")
    md.append("\n| 假说 | A 批（超阈值题数） | A 措辞 | B 批（超阈值题数） | B 措辞 | 实质翻转? | 措辞差别? |\n"
              "|---|--:|---|--:|---|:--:|:--:|")
    hyp = {"same_model": "H-D1（同型号 ⇒ 秩/n 更低）", "one_frame": "H-D2（单框架 ⇒ 更低）",
           "n8": "H-D3（8 支 ⇒ 更高）"}
    flips = 0
    for arm, name in hyp.items():
        sa = "支持" if va[arm] >= 2 else ("否证" if va[arm] == 0 else "低于分辨率")
        sb = "支持" if vb[arm] >= 2 else ("否证" if vb[arm] == 0 else "低于分辨率")
        sub_a = (va[arm] >= 2)          # 是否构成支持
        sub_b = (vb[arm] >= 2)
        real_flip = sub_a != sub_b
        if real_flip:
            flips += 1
        md.append("| %s | %d/3 | %s | %d/3 | %s | %s | %s |"
                  % (name, va[arm], sa, vb[arm], sb,
                     "★ **翻转**" if real_flip else "一致（都不支持）",
                     "—" if sa == sb else "措辞不同（否证 vs 低于分辨率）"))
    md.append("\n**实质判决翻转数：%d / 3** ⇒ %s\n"
              % (flips, "★ 三个判决在两批之间**都稳定**" if flips == 0 else "⚠️ 有实质翻转，引用前要查原因"))
    md.append("\n### ★ 附带一条**关于方法本身**的结论\n")
    md.append("「否证」与「低于分辨率」在**题级 n=3** 下**无法区分**："
              "前者是 0/3 题超阈值、后者是 1/3 题超阈值 ⇒ "
              "⇒ **n=3 只能支持「不成立」，不能支持「确定无效应」**。\n")
    md.append("⇒ ★ 引用纪律：这类假说只能写「**未观察到支持**」，**不能**写「已证明无效应」。\n")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "REPRODUCIBILITY-2026-10-24.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n== 跨批可复现性 ==")
    for a in ARMS:
        v = diffs[a]
        if v:
            print("  %-11s 差值中位 %+.3f 范围 %+.3f~%+.3f" % (LABEL.get(a, a), sorted(v)[len(v) // 2], min(v), max(v)))
    print("  判决翻转数：%d/3" % flips)
    print("\n✓ 落盘 %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
