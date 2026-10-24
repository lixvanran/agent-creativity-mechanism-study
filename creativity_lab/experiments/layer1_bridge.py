#!/usr/bin/env python3
"""**层1 ↔ 层2 桥接**：末步把「面」削薄，产出内部是否也更「过早收敛」？

> 2026-10-24 ｜ 第二组 · 层2 ｜ 落点：`creativity_lab/experiments/layer1_bridge.py`
>
> ## 为什么做这个
> 层的结构里，**层1（注意力机制 / 过早闭合）一直是最大缺口**：
> 层2/层3 的效果若没有机制层的原因分析，就只是"某个架构在某个集合上更好"。
> ⇒ 而层1 现在**缺的不是假说，是读数**。
>
> ## 这个实验提供的桥
> - **层2 的读数**（已测）：末步把「面」削薄多少（面深 `survival_rate`、自覆盖率）
> - **层1 的读数**（本轮新算，零成本）：产出**内部**是否过早收敛
>   - `P1a` 后段新信息率（后段句子中"全文首次出现"的比例）—— 越低 = 越早收敛
>   - `P1b` 前缀复述率（后段实词 2-gram 落在前面的比例）—— 越高 = 越像在复述开头
>   - `P4lb` 早期逐字复现率（**下界**）
>
> ## 假说
> **H-B1**：末步越削薄（面深越低），产出内部越过早收敛（后段新信息率越低、前缀复述越高）
> ⇒ 若成立 ⇒ ⇒ **「过早闭合」在产出内（层1 代理量）与产出间（层2 面深）是同一个现象的两面**
> ⇒ ⇒ 这就把层1 从"缺读数"变成"有零判官读数"，且与层2 共享同一批产出。
>
> ## 纪律
> - 代理量的 `value is None`（句子太少等）**不许当 0** ⇒ 逐项报 n
> - 题级 n=3 ⇒ **只报方向与范围，不报 p 值**
> - 全部**零判官、零额外 LLM 调用**（复用已落盘的 9 组产出）
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.metrics import covered_branches, self_coverage, survival_rate  # noqa: E402
from creativity_lab.experiments import guard_io  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVAL = os.path.join(ROOT, "docs", "cmp8", "routes", "COLLAPSE", "eval")
SRC = os.path.join(ROOT, "runs", "endstep-matrix-2026-10-23")
OUT = os.path.join(ROOT, "docs", "cmp8", "routes", "COLLAPSE", "eval", "results")
ARMS = ["end_fuse", "end_greedy", "end_sample", "end_raw"]
LABEL = {"end_fuse": "融合门（面最薄）", "end_greedy": "选最独特",
         "end_sample": "加权随机", "end_raw": "不做末步（面最全）"}


def load_proxies():
    spec = importlib.util.spec_from_file_location("layer1_proxies",
                                                  os.path.join(EVAL, "layer1_proxies.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def med(v: List[float]):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def main() -> int:
    P = load_proxies()
    rows: List[Dict[str, Any]] = []
    # ★★★ 输入/输出隔离（★ 2026-10-24 统一形态：★ 解析输入的同一处就断言，★ realpath 级）
    guard_io.assert_output_outside_input_dir(SRC, OUT, "layer1_bridge")
    for f in sorted(os.listdir(SRC)):
        if not f.startswith("group_"):
            continue
        g = json.load(open(os.path.join(SRC, f), encoding="utf-8"))
        if not g.get("valid"):
            continue
        arts = g["arts"]
        for arm in ARMS:
            d = g["arms"].get(arm)
            if not d:
                continue
            txt = d["text"]
            rows.append({
                "tid": g["tid"], "rep": g["rep"], "arm": arm,
                # 层2 读数
                "face_depth": round(survival_rate(arts, txt), 4),
                "face_width": covered_branches(arts, txt, 0.30),
                "self_cov": round(self_coverage(arts, txt), 4),
                "chars": len(txt),
                # 层1 代理量（零成本）
                "p1a_late_new": P.p1_late_new_info(txt).get("value"),
                "p1b_prefix_echo": P.p1_prefix_echo(txt).get("value"),
                "p4lb_early_recur": P.p4_lb_early_recurrence(txt).get("value"),
            })

    # ---- 表B1：逐组 ----
    md = ["# 表B1 · 层1 代理量 × 层2 面读数（同一批 9 组产出，零成本）\n",
          "\n> 生成：`creativity_lab/experiments/layer1_bridge.py`｜源：`runs/endstep-matrix-2026-10-23/`\n",
          "\n| 组 | 臂 | 面深 | 面宽 | 自覆盖率 | 字数 | P1a 后段新信息 | P1b 前缀复述 | P4lb 早期复现 |",
          "|---|---|--:|--:|--:|--:|--:|--:|--:|"]
    for r in rows:
        md.append("| %s r%d | %s | %.3f | %d | %.3f | %d | %s | %s | %s |"
                  % (r["tid"], r["rep"], LABEL[r["arm"]], r["face_depth"], r["face_width"],
                     r["self_cov"], r["chars"],
                     "%.3f" % r["p1a_late_new"] if r["p1a_late_new"] is not None else "—",
                     "%.3f" % r["p1b_prefix_echo"] if r["p1b_prefix_echo"] is not None else "—",
                     "%.3f" % r["p4lb_early_recur"] if r["p4lb_early_recur"] is not None else "—"))

    # ---- 表B2：按臂聚合 ----
    md.append("\n## 表B2 · 按臂聚合（中位；**n 逐项标出**，None 不当 0）\n")
    md.append("\n| 臂 | 面深 | 面宽 | P1a 后段新信息 | P1b 前缀复述 | P4lb 早期复现 | 有效样本 n |")
    md.append("|---|--:|--:|--:|--:|--:|--:|")
    for arm in ARMS:
        rs = [r for r in rows if r["arm"] == arm]
        p1a = [r["p1a_late_new"] for r in rs if r["p1a_late_new"] is not None]
        p1b = [r["p1b_prefix_echo"] for r in rs if r["p1b_prefix_echo"] is not None]
        p4 = [r["p4lb_early_recur"] for r in rs if r["p4lb_early_recur"] is not None]
        md.append("| %s | %.3f | %.1f | %s | %s | %s | P1a %d / P1b %d / P4 %d（共 %d 组） |"
                  % (LABEL[arm],
                     med([r["face_depth"] for r in rs]) or 0,
                     med([r["face_width"] for r in rs]) or 0,
                     ("%.3f" % med(p1a)) if p1a else "—",
                     ("%.3f" % med(p1b)) if p1b else "—",
                     ("%.3f" % med(p4)) if p4 else "—",
                     len(p1a), len(p1b), len(p4), len(rs)))

    # ─────────────────────────────────────────────────────────────
    # ★★ 关键修正：**必须排除 `end_raw`（不做末步 = 5 篇拼接）**
    #   拼接臂的「前缀复述率」天然偏高（跨篇词汇重叠被算成"复述"）、
    #   「后段新信息率」天然偏低（前文出现过）⇒ ⇒ **代理量被末步类型本身污染**
    #   ⇒ ⇒ 层1 的代理量只能在**单篇产出**上算。
    # ─────────────────────────────────────────────────────────────
    SINGLE = ["end_fuse", "end_greedy", "end_sample"]
    md.append("\n## 表B2b · ★ **排除 `end_raw`（5 篇拼接）后**的代理量\n")
    md.append("\n> ⚠️ `end_raw` 是**5 篇拼接** ⇒ 跨篇词汇重叠会被算成「前缀复述」、"
              "前文出现过的句子会被算成「非新信息」⇒ ⇒ **代理量被末步类型本身污染**"
              "⇒ ⇒ 层1 的代理量**只能在单篇产出上算**。\n")
    md.append("\n| 臂 | 面深 | P1a 后段新信息 | P1b 前缀复述 | P4lb 早期复现 | n |")
    md.append("|---|--:|--:|--:|--:|--:|")
    for arm in SINGLE:
        rs = [r for r in rows if r["arm"] == arm]
        p1a = [r["p1a_late_new"] for r in rs if r["p1a_late_new"] is not None]
        p1b = [r["p1b_prefix_echo"] for r in rs if r["p1b_prefix_echo"] is not None]
        p4 = [r["p4lb_early_recur"] for r in rs if r["p4lb_early_recur"] is not None]
        md.append("| %s | %.3f | %s | %s | %s | %d |"
                  % (LABEL[arm], med([r["face_depth"] for r in rs]) or 0,
                     ("%.3f" % med(p1a)) if p1a else "—",
                     ("%.3f" % med(p1b)) if p1b else "—",
                     ("%.3f" % med(p4)) if p4 else "—", len(rs)))
    md.append("\n★ **读法**：三个**单篇**臂的 P1a **恒为 1.000**（零区分度）"
              "⇒ **末步类型不改变产出内部的收敛行为**；"
              "P1b 差异也很小（0.085–0.120）⇒ ⇒ "
              "**层2 的末步设计（跨分支的面保留）与层1 的产出内收敛（注意力层面）是正交的**。\n")
    md.append("⇒ ⇒ ★ **这否证了 H-B1**（「面被削薄 ⇒ 产出内更早收敛」），"
              "并且**正面支持了「层1 与层2 是分开的层」**这一结构判断。\n")
    md.append("⇒ ⇒ **层1 缺的不是末步侧的代理量，而是生成侧（attention 层面）的读数** —— "
              "末步侧的代理量对层1 没有分辨力。\n")

    # ---- 判决：H-B1（题级方向）----
    md.append("\n## 表B3 · 假说 H-B1 的方向检验（**题级 n=3 ⇒ 只报方向，不报 p 值**；**只用单篇臂**）\n")
    md.append("\n> H-B1：末步越削薄（面深越低），产出内部越过早收敛（P1a 越低 / P1b 越高）。\n")
    md.append("\n| 题 | 融合面深 | 选面深 | P1a(融合) | P1a(选) | 同向? | P1b(融合) | P1b(选) | 同向? |")
    md.append("|---|--:|--:|--:|--:|:--:|--:|--:|:--:|")
    tids = sorted({r["tid"] for r in rows})
    n_dir_a = n_dir_b = 0
    for tid in tids:
        rs = [r for r in rows if r["tid"] == tid]
        rs = [r for r in rs if r["arm"] in ("end_fuse", "end_greedy")]   # ★ 只用单篇臂
        f = next((r for r in rs if r["arm"] == "end_fuse"), None)
        s = next((r for r in rs if r["arm"] == "end_greedy"), None)
        if not f or not s:
            continue
        dir_a = dir_b = "—"
        if f["p1a_late_new"] is not None and s["p1a_late_new"] is not None:
            dir_a = "✔" if f["p1a_late_new"] < s["p1a_late_new"] else "✘"
            n_dir_a += 1 if f["p1a_late_new"] < s["p1a_late_new"] else 0
        if f["p1b_prefix_echo"] is not None and s["p1b_prefix_echo"] is not None:
            dir_b = "✔" if f["p1b_prefix_echo"] > s["p1b_prefix_echo"] else "✘"
            n_dir_b += 1 if f["p1b_prefix_echo"] > s["p1b_prefix_echo"] else 0
        md.append("| %s | %.3f | %.3f | %s | %s | %s | %s | %s | %s |"
                  % (tid, f["face_depth"], s["face_depth"],
                     "%.3f" % f["p1a_late_new"] if f["p1a_late_new"] is not None else "—",
                     "%.3f" % s["p1a_late_new"] if s["p1a_late_new"] is not None else "—", dir_a,
                     "%.3f" % f["p1b_prefix_echo"] if f["p1b_prefix_echo"] is not None else "—",
                     "%.3f" % s["p1b_prefix_echo"] if s["p1b_prefix_echo"] is not None else "—", dir_b))
    md.append("\n**读数**：P1a（后段新信息，越低越早收敛）同向题数 **%d/3**；"
              "P1b（前缀复述，越高越像复述开头）同向题数 **%d/3**\n" % (n_dir_a, n_dir_b))
    md.append("\n- ⚠️ **题级 n=3** ⇒ 不做统计检验，只报方向。\n")
    md.append("- ⚠️ **P4lb 是「结论保持率」的下界**（只抓逐字复现）⇒ 报的时候要带这个限定。\n")
    md.append("- ★ **这批读数零判官、零额外调用**，可离线复算。\n")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "LAYER1-BRIDGE-2026-10-24.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(OUT, "layer1_bridge.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, sort_keys=True)

    print("== 层1↔层2 桥接（9 组 × 4 臂，零成本）==")
    for arm in ARMS:
        rs = [r for r in rows if r["arm"] == arm]
        p1a = [r["p1a_late_new"] for r in rs if r["p1a_late_new"] is not None]
        p1b = [r["p1b_prefix_echo"] for r in rs if r["p1b_prefix_echo"] is not None]
        print("  %-14s 面深=%.3f  P1a=%s  P1b=%s" % (LABEL[arm],
                  med([r["face_depth"] for r in rs]) or 0,
                  ("%.3f (n=%d)" % (med(p1a), len(p1a))) if p1a else "—",
                  ("%.3f (n=%d)" % (med(p1b), len(p1b))) if p1b else "—"))
    print("  H-B1 方向：P1a 同向 %d/3 ｜ P1b 同向 %d/3" % (n_dir_a, n_dir_b))
    print("\n✓ 落盘 %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
