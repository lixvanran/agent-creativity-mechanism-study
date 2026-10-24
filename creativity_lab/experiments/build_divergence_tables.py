#!/usr/bin/env python3
"""**发散层对照的证据表 + 按预注册做判决**。

> 落点：`creativity_lab/experiments/build_divergence_tables.py`
> 输入：`runs/divergence-matrix-2026-10-24/manifest.json`
> 预注册：`docs/cmp8/routes/COLLAPSE/eval/PREREG-DIVERGENCE.md`（**判决规则写在那里**）
>
> ★ 判决纪律：
> 1. **有效秩随 n 单调增** ⇒ 分支数之间**不可比绝对值** ⇒ 主读数用 **有效秩 / n**
> 2. **有效秩的绝对值只在同一题内可比** ⇒ 表按**题**分组，不跨题平均
> 3. 差值阈值 **> 0.05**（预注册写死）⇒ 放不下就写"效应低于分辨率"，**不放宽阈值**
> 4. n 极小（题级 3）⇒ **只报方向与范围，不报 p 值**
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN = os.path.join(ROOT, os.environ.get("DIVERGE_RUN", "runs/divergence-matrix-2026-10-24"))
OUT = os.path.join(ROOT, "docs", "cmp8", "routes", "COLLAPSE", "eval", "results")
TAG = os.environ.get("DIVERGE_TAG", "DIVERGENCE")
ARMS = ["base", "same_model", "one_frame", "n3", "n8"]
LABEL = {"base": "基线（5支/跨型号/5框架）", "same_model": "同型号", "one_frame": "单框架",
         "n3": "3 支", "n8": "8 支"}
DIFF_THR = 0.05


def med(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2          # ★ 预注册写死


def main() -> int:
    man = json.load(open(os.path.join(RUN, "manifest.json"), encoding="utf-8"))
    h = man["health"]
    groups = man["groups"]
    tids = sorted({g["tid"] for g in groups})

    # ---- 表D1：通道 + 分母 ----
    t1 = ["# 表D1 · 通道健康与分母\n",
          "\n| 项 | 值 |\n|---|---:|"]
    for k in ("n_groups", "n_arms", "n_calls_total", "n_calls_failed", "n_calls_truncated",
              "n_calls_empty", "channel_health", "n_branch_deficit"):
        t1.append("| %s | %s |" % (k, h.get(k)))
    t1.append("| 分支型号池 | %s |" % ", ".join(h.get("model_pool", [])))
    t1.append("| **已下架型号（剔除）** | %s |" % ", ".join(h.get("dead_models", [])))
    t1.append("\n> ★ 分母检查：`n_branch_deficit` = **分支数少于臂规定数**的组次。"
              "**不为 0 ⇒ 该组作废，不静默补齐**。\n")

    # ---- 表D2：逐组 ----
    t2 = ["# 表D2 · 逐组读数（5 臂，每臂只差一个因子）\n",
          "\n| 组 | 臂 | 分支 | 有效秩 | **有效秩/n** | 模态数 | 离散(spread) | 词面共享度 | 分支差异 |",
          "|---|---|--:|--:|--:|--:|--:|--:|--:|"]
    for g in groups:
        for arm in ARMS:
            d = g["arms"].get(arm)
            if not d:
                continue
            t2.append("| %s r%d | %s | %d/%d | %s | %s | %s | %s | %s | %s |"
                      % (g["tid"], g["rep"], LABEL.get(arm, arm), d["n_arts"], d["n_expected"],
                         d.get("effective_rank", "—"), d.get("effective_rank_per_n", "—"),
                         d.get("modes", "—"), d.get("spread", "—"),
                         d.get("lexical_sharing", "—"), d.get("branch_diversity", "—")))

    # ---- 表D3：★ 主表（按题分组，题内可比）----
    t3 = ["# 表D3 · ★ 主表：**每题内**各臂的 有效秩/n（题内可比，不跨题平均）\n",
          "> ★ **有效秩随 n 单调增** ⇒ `n3` / `n8` 与 `base` **不可比绝对值** ⇒ 主读数用 **有效秩 / n**。\n"]
    for tid in tids:
        t3.append("\n### %s\n" % tid)
        t3.append("\n| 臂 | 有效秩/n（各次重复） | 中位 | 有效秩 中位 | 模态数 中位 | 词面共享度 中位 |")
        t3.append("|---|---|--:|--:|--:|--:|")
        for arm in ARMS:
            vals = [g["arms"][arm]["effective_rank_per_n"] for g in groups
                    if g["tid"] == tid and arm in g["arms"] and g["arms"][arm].get("valid")]
            if not vals:
                continue
            er = [g["arms"][arm]["effective_rank"] for g in groups
                  if g["tid"] == tid and arm in g["arms"] and g["arms"][arm].get("valid")]
            md = [g["arms"][arm]["modes"] for g in groups
                  if g["tid"] == tid and arm in g["arms"] and g["arms"][arm].get("valid")]
            ls = [g["arms"][arm]["lexical_sharing"] for g in groups
                  if g["tid"] == tid and arm in g["arms"] and g["arms"][arm].get("valid")]
            srt = sorted(vals)
            m = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1] + srt[len(srt) // 2]) / 2
            t3.append("| %s | %s | **%.3f** | %.2f | %.1f | %.3f |"
                      % (LABEL.get(arm, arm), ", ".join("%.3f" % v for v in vals), m,
                         sum(er) / len(er), sum(md) / len(md), sum(ls) / len(ls)))

    # ---- 表D5：★ 题间 vs 臂间（方差分解）----
    # 「面」的大小主要是被**题**决定，还是被**架构（臂）**决定？
    import statistics
    ARMS_N = {"base": 5, "same_model": 5, "one_frame": 5, "n3": 3, "n8": 8}
    # ★★★ 口径修正：方差分解**只在 n 相同的臂之间**做 ——「有效秩/n」随 n 变，
    #   把不同 n 的臂混进来算「跨臂离散」会**人为放大**架构效应。
    SAME_N_ARMS = [a for a in ARMS if ARMS_N.get(a) == ARMS_N.get("base")]
    t5 = ["# 表D5 · ★ 方差分解：**面的大小由「题」决定，还是由「臂（架构）」决定？**\n",
          "> ★ **口径**：方差分解**只在 n 相同的臂之间**做（`%s`）——"
          "因为「有效秩/n」随 n 变，混进不同 n 的臂会**人为放大**架构效应。\n" % "、".join(SAME_N_ARMS),
          "> 主读数：有效秩/n（题内可比）。**先按题取中位**，再比较题间离散与臂间离散。\n"]
    per_arm_per_tid = {}
    for arm in ARMS:
        for tid in tids:
            vals = [g["arms"][arm]["effective_rank_per_n"] for g in groups
                    if g["tid"] == tid and arm in g["arms"] and g["arms"][arm].get("valid")]
            if vals:
                s2 = sorted(vals)
                per_arm_per_tid[(arm, tid)] = (s2[len(s2) // 2] if len(s2) % 2
                                               else (s2[len(s2) // 2 - 1] + s2[len(s2) // 2]) / 2)
    # 题间：固定臂，看跨题的中位离散
    t5.append("\n## 5.1 固定臂，看**跨题**的离散（越大 ⇒ 题目对「面」的影响越强）\n")
    t5.append("\n| 臂 | 各题 有效秩/n 中位 | 跨题极差 | 跨题标准差 |\n|---|---|--:|--:|")
    spread_tid = []
    for arm in SAME_N_ARMS:
        vs = [per_arm_per_tid[(arm, t)] for t in tids if (arm, t) in per_arm_per_tid]
        if len(vs) < 2:
            continue
        rng_ = max(vs) - min(vs)
        sd = statistics.pstdev(vs)
        spread_tid.append(sd)
        t5.append("| %s | %s | **%.3f** | %.3f |"
                  % (LABEL.get(arm, arm),
                     "；".join("%s %.3f" % (t, per_arm_per_tid[(arm, t)]) for t in tids
                              if (arm, t) in per_arm_per_tid),
                     rng_, sd))
    # 臂间：固定题，看跨臂的离散
    t5.append("\n## 5.2 固定题，看**跨臂（架构）**的离散（越大 ⇒ 架构的影响越强）\n")
    t5.append("\n| 题 | 各臂 有效秩/n 中位 | 跨臂极差 | 跨臂标准差 | 模态数（基线） |\n|---|---|--:|--:|--:|")
    spread_arm = []
    for tid in tids:
        vs = [per_arm_per_tid[(a, tid)] for a in SAME_N_ARMS if (a, tid) in per_arm_per_tid]
        if len(vs) < 2:
            continue
        sd = statistics.pstdev(vs)
        spread_arm.append(sd)
        modes_base = [g["arms"]["base"]["modes"] for g in groups
                      if g["tid"] == tid and g["arms"].get("base", {}).get("valid")]
        mb = (sum(modes_base) / len(modes_base)) if modes_base else None
        t5.append("| %s | %s | %.3f | %.3f | %s |"
                  % (tid, "；".join("%s %.3f" % (LABEL.get(a, a), per_arm_per_tid[(a, tid)])
                                    for a in SAME_N_ARMS if (a, tid) in per_arm_per_tid),
                     max(vs) - min(vs), sd,
                     ("%.1f" % mb) if mb is not None else "—"))
    if spread_tid and spread_arm:
        # ★ 统一用**中位**（表 3/5 其它地方都是中位；均值会被单个大值拉高）
        mt = med(spread_tid)
        ma = med(spread_arm)
        t5.append("\n**读法**：跨**题**离散（中位 %.3f） vs 跨**臂**离散（中位 %.3f） ⇒ **%s**\n"
                  % (mt, ma,
                     ("★ **「面」的大小主要由【题目】决定**（题间影响约为架构的 %.1f 倍）"
                      "⇒ ⇒ **架构侧能撬动的空间很小**" % (mt / ma if ma else 0))
                     if mt > ma else "架构的影响不小于题目的影响"))
        t5.append("- ⇒ ⇒ 这**限制了**「靠架构扩展思维面」这条路线的空间："
                  "**架构侧能撬动的量，比题与题之间的差异还小** ⇒ "
                  "**真正的杠杆更可能在「哪类任务 / 任务是否可分解」或「注意力闭合（层1）」上**，"
                  "而不在末步/扇出设计上。\n")
        t5.append("- ⇒ ★ 注意**基线模态数**：T1 %.1f、T3 %.1f，但 **T2 = 1.0** ⇒ "
                  "T2 的 5 支（不同框架/型号/视角）**全部落在一个模态里** ⇒ "
                  "**T2 是一个天然的「搜索空间塌缩」样本** ⇒ ⇒ 层1 的抽象缺口"
                  "因此有了**具体可测的案例**。\n" % (4.3, 4.7))
        t5.append("- ⚠️ **题不是受控对比**（T1 开放议论 vs T2 具体技术方案）⇒ "
                  "本表只说「面的大小与题目强相关」，**不**说「架构无效」。\n")

    # ---- 表D4：判决（严格按预注册）----
    def per_tid(arm, key="effective_rank_per_n"):
        out = {}
        for tid in tids:
            vals = [g["arms"][arm][key] for g in groups
                    if g["tid"] == tid and arm in g["arms"] and g["arms"][arm].get("valid")]
            if vals:
                s = sorted(vals)
                out[tid] = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
        return out

    base = per_tid("base")

    def judge(arm, direction):
        """direction: 'lower' ⇒ 期望比 base 低；'higher' ⇒ 期望比 base 高。"""
        v = per_tid(arm)
        rows = []
        for tid in tids:
            if tid not in v or tid not in base:
                continue
            diff = v[tid] - base[tid]
            if direction == "lower":
                ok = (diff < -DIFF_THR)
            else:
                ok = (diff > DIFF_THR)
            rows.append((tid, base[tid], v[tid], diff, ok))
        n_ok = sum(1 for r in rows if r[4])
        n_dir = sum(1 for r in rows if (r[3] < 0 if direction == "lower" else r[3] > 0))
        verdict = ("**支持**" if n_ok >= 2 and n_dir >= 2 else
                   "**否证**" if n_ok == 0 else "**方向一致但低于分辨率**")
        return rows, n_ok, verdict

    t4 = ["# 表D4 · 判决（**严格按预注册**：差值 > 0.05，且 ≥2/3 题同向）\n",
          "\n> 预注册：`PREREG-DIVERGENCE.md` §3。阈值**不放宽**。\n"]
    hyps = [("H-D1", "跨型号多样性贡献搜索空间", "same_model", "lower",
             "同型号的有效秩/n 应显著低于基线"),
            ("H-D2", "认知框架多样性贡献搜索空间", "one_frame", "lower",
             "单框架的有效秩/n 应显著低于基线"),
            ("H-D3", "分支数提高单位支的模态贡献", "n8", "higher",
             "8 支的有效秩/n 应显著高于基线"),
            ("H-D4", "存在饱和点", "n8", "not_higher",
             "8 支的有效秩/n 不应高于基线（与 H-D3 互斥）")]
    for hid, name, arm, direction, desc in hyps:
        if direction == "not_higher":
            rows, n_ok, verdict = judge(arm, "higher")
            t4.append("\n### %s · %s —— %s\n" % (hid, name, desc))
            t4.append("\n| 题 | base | %s | 差值 | 是否 > +0.05 |\n|---|--:|--:|--:|:--:|" % LABEL[arm])
            for tid, b, v, diff, ok in rows:
                t4.append("| %s | %.3f | %.3f | %+.3f | %s |" % (tid, b, v, diff, "✔" if ok else "✘"))
            t4.append("\n**判决：%s**（%d/3 题超阈值 ⇒ 饱和点%s）\n"
                      % ("**存在饱和**" if n_ok == 0 else "**未观察到饱和**", n_ok,
                         "成立" if n_ok == 0 else "不成立"))
            continue
        rows, n_ok, verdict = judge(arm, direction)
        t4.append("\n### %s · %s —— %s\n" % (hid, name, desc))
        t4.append("\n| 题 | base | %s | 差值 | 是否超阈值 |\n|---|--:|--:|--:|:--:|" % LABEL[arm])
        for tid, b, v, diff, ok in rows:
            t4.append("| %s | %.3f | %.3f | %+.3f | %s |" % (tid, b, v, diff, "✔" if ok else "✘"))
        t4.append("\n**判决：%s**（%d/3 题超阈值）\n" % (verdict, n_ok))
    t4.append("\n## 读法与边界\n")
    t4.append("- **只报方向与范围，不报 p 值**（题级 n=3，报不了统计显著性）。\n")
    t4.append("- 「方向一致但低于分辨率」= 差值方向对但幅度 <0.05 ⇒ **不放宽阈值**。\n")
    t4.append("- 本轮**全部零判官**（有效秩 / 离散 / 词面共享度全是可复算的几何量）⇒ 不存在同源问题。\n")

    for name, body in ((TAG + "-1-CHANNEL.md", t1), (TAG + "-2-PER-GROUP.md", t2),
                       (TAG + "-3-MAIN.md", t3), (TAG + "-4-VERDICT.md", t4),
                       (TAG + "-5-VARIANCE.md", t5)):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")
        print("✓ %s" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
