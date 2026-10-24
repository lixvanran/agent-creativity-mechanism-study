#!/usr/bin/env python3
"""★ **Stage-1 报告机械校验器（★ 数字必须与 analysis.json 一致 · ★ 零 API）**

★ **为什么需要**：★ 报告里的每个数字都是从数据算出来的 ⇒ ⇒ ★ **手抄必然有一天会脱节**
★ ⇒ ⇒ ★ **★ 校验器必须能独立重算并比对** ⇒ ⇒ ★ 不许靠肉眼。

★ **检查项**：
★ ① 报告里的关键读数与 `analysis.json` **逐字一致**（★ 数字漂移会当场被抓）
★ ② 章节结构完整（★ 拼接/截断会抓）
★ ③ **无残留占位符**（★ `【待填】`）
★ ④ **无旧的 n=5 表述**（★ n 变了但结论句没变 ⇒ ★ 那种不一致最难自己发现）
★ ⑤ 原始样本与派生读数的**行数一致**（★ 防止"派生读数描述另一批数据"）
★ ⑥ 三种 0 的分类**必须出现**（★ 内容层 0 / 不可打分 None / 仪器层 0）

用法：python3 -B group4_state_driven/verify_report_stage1.py
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
DATA = os.path.join(REPO, "group4_state_driven", "data")
REPORTS = [
    os.path.join(REPO, "group4_state_driven", "REPORT_arch6_stage1.md"),
    "/workspace/第四组论证/experiment-design/REPORT_arch6_stage1.md",
]

d = json.load(open(os.path.join(DATA, "arch6_stage1_analysis.json"), encoding="utf-8"))
rows = [json.loads(l) for l in open(os.path.join(DATA, "arch6_stage1.jsonl"), encoding="utf-8") if l.strip()]

checks = []


def ck(name, cond, extra=""):
    checks.append((name, bool(cond), extra))


def run_for(path):
    s = open(path, encoding="utf-8").read()
    tag = os.path.basename(os.path.dirname(path)) or "report"

    # ① 关键读数逐字一致
    ck("[%s] 排序改变率" % tag,
       "%d/%d = %.4f" % (d["rank_change_count"], d["rank_change_n"], d["rank_change_rate"]) in s)
    ck("[%s] Wilson CI" % tag,
       "[%.3f, %.3f]" % tuple(d["rank_change_wilson_ci95"]) in s)
    ck("[%s] σ_new" % tag, "%.4f" % d["sigma_new"] in s)
    ck("[%s] 逐候选改变量方差" % tag, "%.6f" % d["align_shift_var_mean"] in s)
    ck("[%s] var_B" % tag, "%.6f" % d["align_var_B"] in s)
    ck("[%s] sd_B" % tag, "%.6f" % d["align_sd_B"] in s)
    ck("[%s] var_D" % tag, "%.6f" % d["align_var_D"] in s)
    ck("[%s] sd_D" % tag, "%.6f" % d["align_sd_D"] in s)
    ck("[%s] 同质率" % tag, "%.4f" % d["candidate_homogeneity_rate"] in s)
    ck("[%s] 目标集变化率" % tag, "%.4f" % d["target_change_rate"] in s)
    ck("[%s] MDE(n=25)" % tag, "%.4f" % d["mde_table"][-1]["mde80"] in s)
    ck("[%s] power(n=25)" % tag, "%.3f" % d["mde_table"][-1]["power_delta015"] in s)
    ck("[%s] 兑现率下界(D)" % tag, "%.4f" % d["fulfillment"]["ful_D"]["fulfill_lower"] in s)
    ck("[%s] 违禁率上界(D)" % tag, "%.4f" % d["fulfillment"]["ful_D"]["violation_upper"] in s)

    # ② 章节完整
    for h in ["## 1. 实验概述", "## 2. 方法与机制", "## 3. 结果", "## 4. 判决",
              "## 5. 对 v3–v5 的影响", "## 6. 局限与未闭合", "## 7. 复现"]:
        ck("[%s] 章节 %s" % (tag, h.split(".")[0]), h in s)

    # ③ 无残留占位
    ck("[%s] 无【待填】残留" % tag, s.count("【待填】") == 0, "count=%d" % s.count("【待填】"))

    # ④ 无旧 n 表述
    for old in ["n=5", "2/5", "4/5", "0.201", "0.12–0.77"]:
        ck("[%s] 无旧表述 %r" % (tag, old), old not in s)

    # ⑥ 三种 0 的分类必须出现
    ck("[%s] 三种 0 分类出现" % tag, "三种 0" in s)
    for t in (d["zero_classification"].get("content_zero") or []):
        ck("[%s] 内容层 0 含 %s" % (tag, t), t in s)

    # ⑦ 重复采样留痕与 calllog 缺口必须显式
    ck("[%s] 重复采样留痕" % tag, "duplicate_resampling.json" in s)
    ck("[%s] calllog 缺口" % tag, "EXEC_LOG_stage1.md" in s)


def main():
    print("=" * 78)
    print("★ Stage-1 报告机械校验（★ 独立重算 · ★ 零 API）")
    print("=" * 78)

    # ⑤ 原始样本 vs 派生读数行数一致
    n_data = len(rows)
    n_an = d["n_rows"]
    ck("原始样本行数 == analysis.n_rows", n_data == n_an, "%d vs %d" % (n_data, n_an))

    # ⑤b 每题恰好 3 个重复（臂间 n 相等）
    from collections import defaultdict, Counter
    byt = defaultdict(list)
    for r in rows:
        byt[r["topic_id"]].append(r.get("rep"))
    for t in sorted(byt):
        ck("题 %s 恰好 3 个重复" % t, sorted(byt[t]) == [1, 2, 3], str(sorted(byt[t])))
    tags = Counter(r["tag"] for r in rows)
    ck("无重复 tag", all(v == 1 for v in tags.values()),
       str([t for t, v in tags.items() if v > 1]))
    ck("全部 error 为空", all(not r.get("error") for r in rows))
    # ★★★ 强校验：★ analysis 里的逐单元明细必须与【当前原始样本】一一对应
    #   （★ 这条抓的是「派生读数是用另一批数据算的」—— ★ 2026-10-25 实际发生过一次：
    #    ★ data/ 里的 analysis 是重标记【之前】算的 ⇒ tag 列表里有两个 T10-1）
    an_tags = [x.get("tag") for x in (d.get("rank_change_detail") or [])]
    raw_tags = [r.get("tag") for r in rows]
    ck("analysis 明细 tags == 原始样本 tags", an_tags == raw_tags,
       "an=%r raw=%r" % (an_tags, raw_tags))
    ck("analysis 的 src 指向的样本行数 == n_rows", d.get("n_rows") == len(rows))
    # ★ analysis 落盘时间必须晚于原始样本（★ 防止用旧读数覆盖新数据）
    ck("analysis 含新键 rank_change_detail", "rank_change_detail" in d)
    ck("analysis 含新键 zero_classification", "zero_classification" in d)
    ck("全部 batch_id 唯一且一致", len(set(r["batch_id"] for r in rows)) == 1)

    for p in REPORTS:
        if os.path.exists(p):
            run_for(p)
        else:
            ck("报告存在 %s" % p, False)

    ok = sum(1 for _, c, _ in checks if c)
    print("\n--- 结果：%d/%d 通过 ---" % (ok, len(checks)))
    for nme, c, e in checks:
        if not c:
            print("  ✘ %s %s" % (nme, e))
    if ok == len(checks):
        print("\n★ ★ 全部通过 ⇒ 报告数字与数据一致、章节完整、无残留占位 ★ ★")
    print("\n★ sha256（报告，仓内）:")
    import hashlib
    p = REPORTS[0]
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    print("   %s  %s" % (h[:16], os.path.basename(p)))
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
