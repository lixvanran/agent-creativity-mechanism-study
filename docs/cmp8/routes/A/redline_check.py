# -*- coding: utf-8 -*-
"""路线 A 的**红线自检**（协议 §8 (d) R-1…R-12 + `METHOD.md` §4 必留声明 #4）。

检查对象 = **会发给模型的字符串**（提示词模板与注入文本）。
理由：红线约束的是「模型看到了什么」；文档里讨论这些词是必要且合法的。

检查项：
  R-1/R-13  U1–U4 的内容不进任何提示词/诊断集     → 委托 blacklist_check
  R-2       不用字数/断言条数/角色数/表面新颖性当宽度 → 评价口径词零命中
  R-3       不用模型自述                            → 自述类指令零命中
  R-5       不写 ADHD/多动/跳脱人格                → 相关词零命中
  R-6       不写答案暗示/正确答案/题目实体          → 答案暗示类短语零命中
  必留声明#4 依据包不进生成提示词                    → 运行时断言（route_a.py）+ 模板层检查
  R-8       不用 OpenRouter                        → 端点断言

用法：python3 redline_check.py
退出码 0 = 全部通过。
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/workspace/lab")

from creativity_lab import leakage                # noqa: E402
import facets as F                                # noqa: E402
import blacklist_check as BL                      # noqa: E402

# 协议 §8 (d) R-2 相关的「宽度替代物」与 R-5 的人格词、R-3 的自述、R-6 的答案暗示
WIDTH_PROXY_TERMS = [
    "字数", "长度", "条数", "断言数", "角色数", "新颖度", "新颕", "多样性", "表面", "字数上限",
]
SELF_REPORT_TERMS = [
    "我的思路", "我考虑了", "我首先", "我认为我", "我尝试了", "我的分析过程", "我一共考虑",
]
ADHD_TERMS = [
    "ADHD", "多动", "跳脱", "不受约束", "注意力缺陷", "过动", "冲动型人格",
]
ANSWER_HINT_TERMS = [
    "正确答案", "标准答案", "参考答案", "应当选", "应该选", "答案就是", "题目答案", "预期答案",
    "示例答案", "范例答案",
]
# 提示词里**允许**出现的词（这些是协议/项目本身的合法术语，不是红线）
ALLOW_IN_PROMPTS = ["宽度", "有效维度"]      # 提示词里其实不出现，仅作占位说明

# 会发给模型的字符串：facets.py 的全部模板 + route_a.py 的字符串字面量
MODEL_FACING_FILES = [
    os.path.join(HERE, "facets.py"),
    os.path.join(HERE, "route_a.py"),
    os.path.join(HERE, "smoke", "smoke_a.py"),
]
# 文档（也扫黑名单，但不扫评价口径词 —— 文档讨论这些词是合法的）
DOC_FILES = [
    os.path.join(HERE, "DESIGN.md"),
    os.path.join(HERE, "spec.yaml"),
]


def model_facing_strings() -> list:
    out = [(src, s) for src, s in F.all_prompt_strings()]
    for p in MODEL_FACING_FILES:
        if not os.path.exists(p):
            continue
        for lit in leakage.literals(p):
            out.append((os.path.basename(p), lit))
    return out


def scan_terms(strings, terms, allow=()):
    hits = []
    for src, s in strings:
        for t in terms:
            if t in allow:
                continue
            if t in s:
                hits.append(dict(src=src, term=t, sha1=BL._h(s), len=len(s)))
    return hits


def main() -> int:
    report = {}
    strs = model_facing_strings()
    report["model_facing_strings_checked"] = len(strs)

    # R-2 评价口径（leakage 的权威词表）
    rub = []
    for src, s in strs:
        for t in leakage.RUBRIC_TERMS:
            if t in s:
                rub.append(dict(src=src, term=t, sha1=BL._h(s)))
    report["R2_rubric_term_hits"] = rub
    report["R2_width_proxy_hits"] = scan_terms(strs, WIDTH_PROXY_TERMS)
    report["R3_self_report_hits"] = scan_terms(strs, SELF_REPORT_TERMS)
    report["R5_adhd_hits"] = scan_terms(strs, ADHD_TERMS)
    report["R6_answer_hint_hits"] = scan_terms(strs, ANSWER_HINT_TERMS)

    # R-1/R-13 黑名单（提示词文件 + 文档 + 冒烟日志）
    scan_targets = [p for p in MODEL_FACING_FILES + DOC_FILES if os.path.exists(p)]
    smoke_dir = os.path.join(HERE, "smoke")
    for n in ("smoke_log.txt", "smoke_calls.jsonl", "smoke_log.json"):
        p = os.path.join(smoke_dir, n)
        if os.path.exists(p):
            scan_targets.append(p)
    bl = BL.scan(scan_targets)
    report["R1_blacklist_strict_hits"] = bl["strict_hits"]
    report["R1_blacklist_hint_hits"] = bl["hint_hits"]
    report["R1_blacklist_source_files"] = bl["source_files"]
    report["R1_blacklist_files_scanned"] = len(scan_targets)
    report["R1_hit_details"] = [f for f in bl["files"] if f.get("hits")]

    # 必留声明 #4：模板层检查（生成模板里不得有依据包占位符）
    gen_tpl = [F.SLOT_Q, F.RESAMPLE_Q, F.EXTRACT_Q, F.SPLIT_Q]
    report["M4_generation_templates_have_no_evidence_slot"] = all(
        ("{ev}" not in t and "{evidence" not in t) for t in gen_tpl)
    # 核验模板**必须**有依据槽
    report["M4_verify_template_has_evidence_slot"] = ("{ev}" in F.CHECK_Q)

    # R-8 端点
    base = os.environ.get("OPENROUTER_BASE_URL", "")
    report["R8_endpoint"] = base
    report["R8_endpoint_ok"] = (base == "https://api.minimaxi.com/v1") and ("openrouter.ai" not in base)

    # 汇总
    hard_fail = {
        "R2_rubric_term_hits": report["R2_rubric_term_hits"],
        "R2_width_proxy_hits": report["R2_width_proxy_hits"],
        "R3_self_report_hits": report["R3_self_report_hits"],
        "R5_adhd_hits": report["R5_adhd_hits"],
        "R6_answer_hint_hits": report["R6_answer_hint_hits"],
    }
    report["hard_fail_counts"] = {k: len(v) for k, v in hard_fail.items()}
    report["hard_fail_total"] = sum(report["hard_fail_counts"].values())
    report["R1_blacklist_strict_total"] = bl["strict_hits"]
    report["all_pass"] = (
        report["hard_fail_total"] == 0
        and report["R1_blacklist_strict_total"] == 0
        and report["M4_generation_templates_have_no_evidence_slot"]
        and report["M4_verify_template_has_evidence_slot"]
        and report["R8_endpoint_ok"]
    )

    out = os.path.join(HERE, "redline_check.json")
    with open(out, "w", encoding="utf-8") as f:
        import json
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(__import__("json").dumps({k: v for k, v in report.items()
                                   if k not in ("R1_hit_details",)},
                                  ensure_ascii=False, indent=1))
    if report["R1_hit_details"]:
        print("\n命中明细（只给位置与长度，不打印黑名单字符串本身）：")
        for fd in report["R1_hit_details"]:
            for h in fd["hits"][:20]:
                print("  %s:%s cls=%s len=%d" % (fd["path"], h["line"], h["cls"], h["len"]))
    print("\n结论：%s" % ("全部通过" if report["all_pass"] else "存在未通过项"))
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
