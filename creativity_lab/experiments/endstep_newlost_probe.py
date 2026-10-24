#!/usr/bin/env python3
"""★ **末步输出的【新增 / 丢失】信息实例分析**（★ 零 API · 纯文本比对）

> 落点：`creativity_lab/experiments/endstep_newlost_probe.py`
> 数据：`runs/endstep-matrix-2026-10-23/group_*.json`（★ 顶层 `arts` = 5 条分支原文）
> 输出：`runs/endstep-matrix-2026-10-23/newlost_probe.json` + 人读版
>
> ## ★★ 它回答什么（★ 工作包二 · 文科链路要的那一栏）
> ★ **同一个候选池下，不同末步（fuse / greedy / sample / raw）**
> ★ **① 末步输出【丢】了分支里的哪些信息？**
> ★ **② 末步输出【新增】了哪些分支里没有的信息？**
>
> ## ★★ 方法（★ 必须写清口径，★ 否则这个数会被误读）
> ★ **片段单位 = 字符 4-gram**（★ 不用 embedding ⇒ **零 API**）
> ★ **「丢失」定义**：★ **分支原文里的 4-gram，在末步输出中【不出现】** ⇒ ⇒ ★
> ★ 　　　⇒ 报「该支的 4-gram 覆盖率」= 出现在末步里的比例 ⇒ ★ **覆盖率低 = 丢得多**
> ★ **「新增」定义**：★ **末步输出里的 4-gram，在【任何一支】分支原文中都不出现** ⇒ ⇒ ★
> ★ 　　　⇒ 报「末步独有 4-gram 占比」⇒ ★ **这是末步【自己生成】的、候选池里没有的内容**
> ★★★ **★ 边界（★ 必须写死）**：
> ★ **这是【词面近似】，不是语义判定** ⇒ ⇒ ★ **"覆盖率低"只能读作"词面被丢弃"，★ 不能读作"信息被丢弃"**
> ★ **（同「structured_dedup 是词面近似」那条纪律）**
> ★ **★ 且【不同臂的末步长度不同】⇒ ⇒ 覆盖率天然受长度影响 ⇒ ⇒ ★ **必报各臂末步字数**
"""
import json
import os
import re
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.experiments import guard_io  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN = os.path.join(ROOT, "runs", "endstep-matrix-2026-10-23")
N = 4


def norm(t: str) -> str:
    """★ 归一化：★ 去空白 + 去标点（★ 只保留中英文字数字）⇒ ★ 让 4-gram 不被标点切断"""
    t = re.sub(r"[^0-9A-Za-z一-鿿]+", "", t or "")
    return t


def grams(t: str, n: int = N):
    t = norm(t)
    return set(t[i:i + n] for i in range(max(0, len(t) - n + 1)))


def main() -> int:
    # ★★★ 输入/输出隔离（★ 2026-10-24 统一形态：★ 在【解析输入的同一处】剔除将写出的路径）
    _OUT = os.path.join(RUN, "newlost_probe.json")
    _cands = [os.path.join(RUN, f) for f in os.listdir(RUN)
              if f.startswith("group_") and f.endswith(".json")]
    _cands = guard_io.excluded_candidates(_cands, [_OUT])
    files = sorted(os.path.basename(p) for p in _cands)
    if not files:
        print("★ 无 group_*.json ⇒ 退出")
        return 2
    per_arm = {}
    rows = []
    for fn in files:
        d = json.load(open(os.path.join(RUN, fn), encoding="utf-8"))
        arts = d.get("arts") or []
        if not arts:
            continue
        pool = [grams(a) for a in arts]
        pool_union = set().union(*pool) if pool else set()
        picked = d.get("picked") or {}
        row = {"tid": d.get("tid"), "rep": d.get("rep"),
               "n_pool": len(arts), "arts_chars": d.get("arts_chars"),
               "arms": {}}
        for arm, a in (d.get("arms") or {}).items():
            txt = a.get("text") or ""
            g = grams(txt)
            out_chars = len(norm(txt))
            # 覆盖率：每支的 4-gram 有多少出现在末步里
            cov = [round(len(p & g) / max(1, len(p)), 4) for p in pool]
            # 末步独有：不在任何支里
            novel = len(g - pool_union)
            novel_rate = round(novel / max(1, len(g)), 4)
            # 被选中的那一支的覆盖率（★ "选中却丢得最多" = 最刺眼的实例）
            p_idx = picked.get(arm)
            cov_picked = cov[p_idx] if (isinstance(p_idx, int) and 0 <= p_idx < len(cov)) else None
            row["arms"][arm] = {
                "out_chars_raw": a.get("out_chars"), "out_chars_norm": out_chars,
                "covered_branches": a.get("covered_branches"),
                "survival_rate": a.get("survival_rate"),
                "picked_idx": p_idx,
                "coverage_per_branch": cov,
                "coverage_mean": round(statistics.mean(cov), 4) if cov else None,
                "coverage_min": round(min(cov), 4) if cov else None,
                "coverage_of_picked": cov_picked,
                "novel_4gram_rate": novel_rate,
                "n_4gram": len(g),
            }
            pa = per_arm.setdefault(arm, {"cov_mean": [], "cov_min": [], "novel": [],
                                          "out_chars": [], "picked_cov": []})
            pa["cov_mean"].append(row["arms"][arm]["coverage_mean"])
            pa["cov_min"].append(row["arms"][arm]["coverage_min"])
            pa["novel"].append(novel_rate)
            pa["out_chars"].append(out_chars)
            if cov_picked is not None:
                pa["picked_cov"].append(cov_picked)
        rows.append(row)

    summary = {}
    for arm, v in per_arm.items():
        summary[arm] = {
            "n_groups": len(v["cov_mean"]),
            "coverage_mean_of_mean": round(statistics.mean(v["cov_mean"]), 4),
            "coverage_mean_of_min": round(statistics.mean(v["cov_min"]), 4),
            "novel_4gram_rate_mean": round(statistics.mean(v["novel"]), 4),
            "out_chars_mean": round(statistics.mean(v["out_chars"]), 1),
            "coverage_of_picked_mean": (round(statistics.mean(v["picked_cov"]), 4)
                                        if v["picked_cov"] else None),
        }

    print("== ★ 末步输出的【新增 / 丢失】信息实例（★ 零 API · 4-gram 词面近似）==")
    print("   ★ 覆盖率 = 分支原文的 4-gram 有多少出现在末步输出里（★ 低 = 丢得多）")
    print("   ★ 新增率 = 末步输出里【任何分支都没有】的 4-gram 占比")
    print()
    print("   %-12s %-6s %-12s %-12s %-12s %-12s" % (
        "臂", "组数", "覆盖均值", "覆盖最差", "选中支覆盖", "新增率"))
    for arm, s in summary.items():
        print("   %-12s %-6d %-12s %-12s %-12s %-12s" % (
            arm, s["n_groups"], s["coverage_mean_of_mean"], s["coverage_mean_of_min"],
            s["coverage_of_picked_mean"], s["novel_4gram_rate_mean"]))
    print()
    print("   ★ 各臂末步字数（★ 覆盖率天然受长度影响 ⇒ 必须一起看）:")
    for arm, s in summary.items():
        print("     %-12s 均值 %s 字" % (arm, s["out_chars_mean"]))
    # ★ 找最刺眼的实例：★ 选中了一支，但那一支的覆盖率最低
    print()
    print("   ★★ 最刺眼实例（★ 选中该支、但该支内容在末步中丢得最多）:")
    worst = []
    for r in rows:
        for arm, a in r["arms"].items():
            cp = a.get("coverage_of_picked")
            if cp is not None and a.get("coverage_min") is not None and cp <= a["coverage_min"] + 1e-9:
                worst.append((cp, r["tid"], r["rep"], arm, a["picked_idx"],
                              a["coverage_per_branch"], a["out_chars_norm"]))
    worst.sort()
    for w in worst[:6]:
        print("     %s r%s %-12s ｜ 选中第 %s 支 ｜ 该支覆盖 %.3f ｜ 各支覆盖 %s ｜ 末步 %s 字"
              % (w[1], w[2], w[3], w[4], w[0], w[5], w[6]))
    if not worst:
        print("     （本批无「选中即丢尽」的极端实例 ⇒ ★ 说明末步至少保住了选中支的骨架）")

    out = os.path.join(RUN, "newlost_probe.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"method": "★ 字符 4-gram 词面近似（★ 零 API）",
                   "boundary": ("★ 词面近似 ≠ 语义判定 ⇒ 覆盖率低只可读作『词面被丢弃』"
                                "｜★ 各臂末步长度不同 ⇒ 覆盖率受长度影响 ⇒ 必须与字数一起看"),
                   "n": N, "summary": summary, "rows": rows},
                  f, ensure_ascii=False, indent=1, sort_keys=True)
    print("\n   落盘:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
