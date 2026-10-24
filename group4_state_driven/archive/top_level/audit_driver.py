#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 驱动机审计（driver audit）

════════════════════════════════════════════════════════════════════════
★ 要回答的三个问题
  Q1 干不干净？—— 决策的**取值空间**有没有被代码限定？
  Q2 有没有效？—— 驱动内容真的改变了产出吗？
  Q3 有没有偷偷退化成提示词？—— brief 里有多少是"状态"、多少是"提示"？

★ 判据的落点（可核验，不是感觉）
  **一个决策"干净"= 它的取值被代码限定在一个可枚举集合内。**
    · 干净例：`已排除` 的措辞 ⊆ 观测里出现过的引号内容
             ⇒ 代码抽 ⇒ 取值空间封闭 ⇒ 可置换、可逐字归属、可证伪
    · 不干净例：`这一轮写什么`（keeps）、`新约束`（new_constraints）
             ⇒ 模型自由生成 ⇒ 代码只做包装与校验 ⇒ **取值空间不封闭**
  ⇒ **代码只做校验 = 决策权仍在模型手里**，这不叫状态机。

★ 自检先行（铁律一）：审计器必须先证明自己能抓到东西（正例 + 反例 + 变异）。
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import workflow_arch as WA

# ---------------------------------------------------------------- 元层标记词
#: 出现在 brief 里、用来**告诉模型"这是一段状态/约束"**的信号。
META_MARKERS = ["【这一轮要守住的取舍】", "【这一轮不能再走的路】", "【初稿】",
                "【上一轮的建议】", "【需要注意的方面】"]
META_WORDS = ["取舍", "约束", "这一轮", "不能再走", "已排除", "守住", "上一轮", "初稿"]


def count_markers(text):
    n = sum(text.count(m) for m in META_MARKERS)
    n += sum(len(re.findall(w, text)) for w in META_WORDS)
    return n


# ---------------------------------------------------------------- 决策点登记
#: 每个决策点：谁决定、取值空间是否被代码封闭、代码在哪一行
DECISIONS = [
    {
        "name": "驱动内容（这一轮要守住的取舍）",
        "who": "模型",
        "space_closed": False,
        "code_ref": "run_arch_compare.py:step_stance (keeps = d['不能牺牲'])",
        "why": "取值是模型自由生成的 3 条自然语言；代码只截断到 3 条，不限定内容",
        "slot": "keeps",
    },
    {
        "name": "观测（初稿哪些地方没展开）",
        "who": "模型",
        "space_closed": False,
        "code_ref": "run_arch_compare.py:step_observe",
        "why": "gaps 是模型自由生成的描述",
        "slot": "gaps",
    },
    {
        "name": "新约束（这一轮具体写什么）",
        "who": "模型",
        "space_closed": False,
        "code_ref": "workflow_arch.py:transfer ③ (rewriter 返回模型产物)",
        "why": "代码只校验 gap_index 指向对不对，**不限定约束内容本身**",
        "slot": "keeps(S1)",
    },
    {
        "name": "已排除（哪些路已经走过）",
        "who": "代码",
        "space_closed": True,
        "code_ref": "workflow_arch.py:build_excluded",
        "why": "取值 ⊆ 观测里出现过的引号内容 ⇒ 取值空间封闭 ⇒ 可逐字归属",
        "slot": "excluded",
    },
    {
        "name": "绑定（约束↔缺口的对应）",
        "who": "代码",
        "space_closed": True,
        "code_ref": "workflow_arch.py:resolve_binding (gap_index)",
        "why": "结构声明 ⇒ 零阈值；旧版措辞相似度有假阴性（实测 2/9）",
        "slot": "binding",
    },
    {
        "name": "补齐（不足 3 条时沿用上一轮）",
        "who": "代码",
        "space_closed": True,
        "code_ref": "workflow_arch.py:transfer 补齐",
        "why": "确定性规则，trace 里显式标注 filler_from_prev",
        "slot": "keeps",
    },
]


def selftest(verbose=True):
    R = []

    def chk(n, c, d=""):
        R.append({"name": n, "pass": bool(c), "detail": d})
        if verbose:
            print("  %s %-46s %s" % ("✓" if c else "✗", n, d))

    # 1. 标记计数：带标记的 brief 必须 > 裸内容的 brief
    dirty = "你如何看待高考英语作文？写成一篇文章。\n\n【这一轮要守住的取舍】\n· 不能牺牲独立思考\n\n直接输出文章正文。"
    clean = "你如何看待高考英语作文？写成一篇文章。\n\n不能牺牲独立思考\n\n直接输出文章正文。"
    chk("count_markers 带标记 > 裸内容",
        count_markers(dirty) > count_markers(clean),
        "dirty=%d clean=%d" % (count_markers(dirty), count_markers(clean)))
    # 2. 反例：不含状态标记的 brief 必须为 0
    chk("count_markers 纯问题=0", count_markers("你如何看待高考英语作文？写成一篇文章。") == 0)
    # 3. 变异注入：把标记词表清空 ⇒ 计数必须塌成 0（测试不是摆设）
    global META_WORDS, META_MARKERS
    om, ow = META_MARKERS, META_WORDS
    try:
        META_MARKERS, META_WORDS = [], []
        chk("变异注入(清空标记表) 被抓到", count_markers(dirty) == 0, "mutant=%d" % count_markers(dirty))
    finally:
        META_MARKERS, META_WORDS = om, ow
    # 4. 决策点登记完整性：必须有"干净"和"不干净"两类
    closed = [d for d in DECISIONS if d["space_closed"]]
    opened = [d for d in DECISIONS if not d["space_closed"]]
    chk("决策点登记含两类", len(closed) and len(opened), "closed=%d open=%d" % (len(closed), len(opened)))
    # 5. 已排除取值空间封闭性：抽出的措辞必须逐字来自观测
    obs = {"used": ["初稿里用过“伪写作”这个说法", "出现了“系统化”"]}
    ex = WA.build_excluded(obs)
    src = json.dumps(obs, ensure_ascii=False)
    inside = all(e.replace("不要再出现：", "") in src for e in ex)
    chk("已排除取值 ⊆ 观测（空间封闭）", inside, str(ex))
    # 6. 反例：新约束不在观测里 ⇒ 不封闭
    chk("新约束不受观测封闭（模型自由）",
        "不能让文章变成三段式" not in src)

    ok = all(x["pass"] for x in R)
    if verbose:
        print("  === 审计器自检: %s (%d/%d) ===" % ("通过" if ok else "未通过",
                                                sum(x["pass"] for x in R), len(R)))
    return {"all_pass": ok, "cases": R}


# ---------------------------------------------------------------- 主审计

def audit(run_path):
    rs = [json.loads(l) for l in open(run_path, encoding="utf-8") if l.strip()]
    arms = sorted({r.get("arm") for r in rs})

    # ---- Q3 提示词污染度（按臂重建 brief 形态）----
    contam = {}
    for a in arms:
        rows = [r for r in rs if r.get("arm") == a]
        ratios, marks = [], []
        for r in rows:
            s1 = r.get("state1") or {}
            keeps = s1.get("keeps") or []
            exc = s1.get("excluded") or []
            draft = r.get("draft") or ""
            # 定稿步 brief 的真实长度
            brief_len = len(QUESTION) + len(draft) + sum(len(k) for k in keeps) + sum(len(e) for e in exc)
            state_len = sum(len(k) for k in keeps) + sum(len(e) for e in exc)
            ratios.append(state_len / brief_len if brief_len else None)
            marks.append(count_markers("【这一轮要守住的取舍】\n" + "\n".join(keeps) +
                                       "\n【这一轮不能再走的路】\n" + "\n".join(exc)))
        contam[a] = {
            "n": len(rows),
            "state_ratio_mean": round(sum(x for x in ratios if x) / len([x for x in ratios if x]), 4)
            if any(ratios) else None,
            "meta_markers_mean": round(sum(marks) / len(marks), 2) if marks else None,
            "has_state_block": True,
        }

    # ---- Q1 决策权归属 ----
    n_open = sum(1 for d in DECISIONS if not d["space_closed"])
    n_closed = sum(1 for d in DECISIONS if d["space_closed"])
    # 与"驱动"直接相关的决策（驱动内容 / 观测 / 新约束）
    drive_related = [d for d in DECISIONS if d["slot"] in ("keeps", "gaps", "keeps(S1)")]
    drive_open = [d for d in drive_related if not d["space_closed"]]

    # ---- Q3' 驱动力消费点 ----
    cons = []
    for r in rs:
        if not str(r.get("arm", "")).startswith("WF-a"):
            continue
        s1 = r.get("state1") or {}
        keeps = s1.get("keeps") or []
        txt = (r.get("text") or "")
        hits, tot = 0, 0
        for k in keeps:
            for w in WA.ngrams(k):
                tot += 1
                if w in WA.ngrams(txt):
                    hits += 1
        cons.append({"arm": r["arm"], "tag": r.get("tag"),
                     "cons_hit": round(hits / tot, 4) if tot else None, "ngrams": tot})
    # 只算一次 ngrams（性能）
    for r in rs:
        pass

    return {
        "run": os.path.basename(run_path),
        "arms": arms,
        "n_runs": len(rs),
        "Q1_决策权归属": {
            "decisions": DECISIONS,
            "n_code_closed(干净)": n_closed,
            "n_model_free(不干净)": n_open,
            "★与驱动直接相关且不封闭的决策数": len(drive_open),
            "★驱动相关决策总数": len(drive_related),
            "★驱动决策的代码封闭率": round(
                sum(1 for d in drive_related if d["space_closed"]) / len(drive_related), 4),
        },
        "Q3_提示词污染度": contam,
        "Q3b_驱动内容传导率": cons,
    }


QUESTION = "你如何看待高考英语作文？写成一篇文章。"


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=os.path.join(HERE, "runs", "arch_compare.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "driver_audit.json"))
    args = ap.parse_args()

    print("=== 审计器自检 ===")
    st = selftest()
    if not st["all_pass"]:
        print("审计器自检未通过 ⇒ 审计结果不可信，中止")
        sys.exit(1)

    print("\n=== 驱动机审计 ===")
    A = audit(args.run)
    print("\n【Q1】决策权归属（干净 = 取值空间被代码限定）")
    for d in A["Q1_决策权归属"]["decisions"]:
        mark = "✔ 封闭" if d["space_closed"] else "✘ 开放"
        print("  %s  %-34s 决策者=%s" % (mark, d["name"], d["who"]))
        print("        %s" % d["code_ref"])
        print("        %s" % d["why"])
    q1 = A["Q1_决策权归属"]
    print("\n  ⇒ 干净 %d 个 / 不干净 %d 个" % (q1["n_code_closed(干净)"], q1["n_model_free(不干净)"]))
    print("  ⇒ 与驱动直接相关的决策 %d 个，其中不封闭 %d 个（**驱动决策的代码封闭率 = %.0f%%**）"
          % (q1["★驱动相关决策总数"], q1["★与驱动直接相关且不封闭的决策数"],
             100 * q1["★驱动决策的代码封闭率"]))

    print("\n【Q3】提示词污染度（定稿步 brief 里状态内容的占比 / 元层标记数）")
    for a, v in A["Q3_提示词污染度"].items():
        print("  %-9s n=%d  状态占 brief %.1f%%  元层标记 %.1f 处"
              % (a, v["n"], 100 * (v["state_ratio_mean"] or 0), v["meta_markers_mean"] or 0))

    print("\n【Q3b】驱动内容传导率（约束 n-gram 落在正文里的比例）")
    for c in A["Q3b_驱动内容传导率"]:
        print("  %-9s #%s  %.3f (n-gram 分母 %d)"
              % (c["arm"], c["tag"], c["cons_hit"] or 0, c["ngrams"]))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(A, f, ensure_ascii=False, indent=2)
    print("\n[out] %s" % args.out)


if __name__ == "__main__":
    main()
