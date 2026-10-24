# -*- coding: utf-8 -*-
"""路线 A 的**红线自检**（协议 §8 (d) R-1…R-13 + `METHOD.md` §4 必留声明 #4）。

检查对象 = **真正会发给模型的字符串**。
理由：红线约束的是「模型看到了什么」；文档里讨论这些词是必要且合法的。

⚠️ **第二轮返工的修法（F7）**：
  旧版把 `facets.py` 的**推导注释**（第 3 列，只给复核者看）也算进「会发给模型的字符串」，
  于是 `redline_check.json` 记录 `hard_fail_total=2`（FA1/FA6 的 `why` 里有「承重」），
  而 `DESIGN.md` 却标 ✅ —— **自检产物与文档互相打架**。
  现在分成三层：
    ① `injected`   —— **会发给模型**的字符串（`facets.injected_strings()`）
                      ⇒ 评价口径词命中 = **hard fail**；
    ② `derivation` —— 只给复核者看的推导注释 ⇒ 命中**只报告、不判失败**
                      （它们从不进任何提示词：`facet_text()` 只取第 2 列）；
    ③ `prompt_level`—— **执行器实际发出去的 prompt**（用打桩 LLM 跑一遍真执行器抓取）
                      ⇒ 最强的一层：它检查的是「模型真正看到的东西」。

**任何一层为空 ⇒ 判失败**（空检查不能算通过；协议 F8 的精神）。

用法：python3 redline_check.py
退出码 0 = 全部通过；1 = 有未通过项；2 = 守卫触发（检查未真正执行）。
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

# 会发给模型的**代码**文件（字符串字面量层面的扫描）
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

# 文档里的**强断言**词（复核指出旧版 grep 漏了「保证」这类词）。
# 本项**不判失败**（语义判定不是脚本能做的），但**必须列出**给复核者逐条看。
STRONG_CLAIM_TERMS = ["保证", "必然", "确保", "不可能", "永远", "完全固定", "恒定"]


def model_facing_strings() -> list:
    """① 会发给模型的字符串：注入串 + 代码里的字符串字面量。"""
    out = [(src, s) for src, s in F.injected_strings()]
    for p in MODEL_FACING_FILES:
        if not os.path.exists(p):
            continue
        for lit in leakage.literals(p):
            out.append((os.path.basename(p), lit))
    return out


def prompt_level_strings() -> list:
    """③ 执行器**实际发出去**的 prompt（打桩 LLM 跑一遍真执行器抓取）。

    合成诊断题（**不是** U1–U4，也不含任何真实题目的实体）。
    """
    import route_a

    class _Capture:
        def __init__(self):
            self.prompts = []
            self.n_api_calls = 0
            self.n_tokens = 0
            self.rec = []

        def chat(self, prompt, **kw):
            self.prompts.append((kw.get("purpose", ""), prompt))
            self.n_api_calls += 1
            self.n_tokens += 100
            self.rec.append(type("C", (), dict(model="stub"))())
            p = kw.get("purpose", "")
            if p.startswith("A_extract"):
                return "- 合成诊断条目一，用于红线自检。\n- 合成诊断条目二，用于红线自检。"
            if p.startswith("A_verify"):
                return "未提及 1\n未提及 2"
            return "这是用于红线自检的合成回答，不含任何真实题目内容。"

    ask = "合成诊断题：某项服务每月收费 20 元，题面已给足全部条件，请给出应缴金额。"
    ev = [dict(id="EV-SYN-01", text="合成依据条目：某项服务每月收费 20 元。")]
    out = []
    for mode in ("structured", "structured_no_cover", "random"):
        cap = _Capture()
        try:
            route_a.run_route(ask, ev, cfg=dict(round1_facets=["FA1", "FA2"],
                                                round2_facets=["FA5", "FA6"],
                                                extract_cap=2, max_claims=6,
                                                resample_mode=mode),
                               llm=cap, log=[])
        except Exception as e:                      # noqa: BLE001
            out.append(("PROMPT_LEVEL:ERROR", "执行器跑不通：%r" % (e,)))
            continue
        for i, (purpose, p) in enumerate(cap.prompts):
            out.append(("PROMPT_LEVEL:%s:%d:%s" % (mode, i, purpose), p))
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
    guards = []

    # ---------------- ① 注入串
    injected = F.injected_strings()
    if len(injected) < 10:
        guards.append("injected_set_too_small: 注入串只有 %d 条（模板可能没被加载）"
                      % len(injected))
    strs = model_facing_strings()
    report["model_facing_strings_checked"] = len(strs)
    report["injected_strings_checked"] = len(injected)

    # R-2 评价口径（leakage 的权威词表）—— 注入串命中 = hard fail
    rub = []
    for src, s in injected:
        for t in leakage.RUBRIC_TERMS:
            if t in s:
                rub.append(dict(src=src, term=t, sha1=BL._h(s)))
    report["R2_rubric_term_hits"] = rub
    report["R2_width_proxy_hits"] = scan_terms(strs, WIDTH_PROXY_TERMS)
    report["R3_self_report_hits"] = scan_terms(strs, SELF_REPORT_TERMS)
    report["R5_adhd_hits"] = scan_terms(strs, ADHD_TERMS)
    report["R6_answer_hint_hits"] = scan_terms(strs, ANSWER_HINT_TERMS)

    # ② 推导注释（只给复核者看）—— 命中**只报告**，不判失败
    deriv = F.derivation_strings()
    deriv_hits = []
    for src, s in deriv:
        for t in leakage.RUBRIC_TERMS:
            if t in s:
                deriv_hits.append(dict(src=src, term=t, sha1=BL._h(s)))
    report["R2_rubric_term_hits_in_derivation_only"] = deriv_hits
    report["R2_derivation_only_note"] = (
        "这些命中只出现在**推导注释**里（facets.FACETS[*][2]），"
        "facet_text() 只取第 2 列 ⇒ 它们从不进任何提示词；故不判失败，只报告。")

    # ③ 执行器实际发出的 prompt（最强的一层）
    plev = prompt_level_strings()
    report["prompt_level_prompts_checked"] = len(plev)
    if not plev:
        guards.append("prompt_level_empty: 没能从执行器抓到任何实际 prompt")
    plev_rub = []
    for src, s in plev:
        for t in leakage.RUBRIC_TERMS:
            if t in s:
                plev_rub.append(dict(src=src, term=t, sha1=BL._h(s)))
        for t in ANSWER_HINT_TERMS:
            if t in s:
                plev_rub.append(dict(src=src, term=t, sha1=BL._h(s)))
    report["R2_prompt_level_hits"] = plev_rub
    report["R3_prompt_level_self_report_hits"] = scan_terms(plev, SELF_REPORT_TERMS)
    report["R5_prompt_level_adhd_hits"] = scan_terms(plev, ADHD_TERMS)
    # 必留声明 #4：**实际发出的生成 prompt**（N1/N4）里不得出现依据包文本
    #（核验 prompt 里有依据是**应该**的 —— 依据包只进核验侧）
    ev_text = "合成依据条目：某项服务每月收费 20 元。"
    leak = []
    for src, s in plev:
        if "A_verify" in src:          # 核验侧：有依据是设计要求
            continue
        if ev_text in s:
            leak.append(src)
    report["M4_prompt_level_evidence_leak"] = leak

    # ---------------- R-1/R-13 黑名单（提示词文件 + 文档 + 冒烟日志）
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
    report["R1_blacklist_files_scanned"] = bl["files_scanned"]
    report["R1_hit_details"] = [f for f in bl["files"] if f.get("hits")]
    if bl["files_scanned"] == 0:
        guards.append("blacklist_nothing_scanned: 黑名单检查没有扫到任何文件")
    if bl["source_files"] == 0:
        guards.append("blacklist_no_source: 找不到 U1–U4 的 user4_*.json")
    if bl["blacklist_strict"] == 0:
        guards.append("blacklist_empty: strict 黑名单为空")

    # ---------------- 必留声明 #4：模板层检查
    gen_tpl = [F.SLOT_Q, F.RESAMPLE_Q, F.RESAMPLE_Q_NC, F.EXTRACT_Q, F.SPLIT_Q]
    report["M4_generation_templates_have_no_evidence_slot"] = all(
        ("{ev}" not in t and "{evidence" not in t) for t in gen_tpl)
    report["M4_verify_template_has_evidence_slot"] = ("{ev}" in F.CHECK_Q)

    # ---------------- R-8 端点
    base = os.environ.get("OPENROUTER_BASE_URL", "")
    report["R8_endpoint"] = base
    report["R8_endpoint_ok"] = (base == "https://api.minimaxi.com/v1") and ("openrouter.ai" not in base)

    # ---------------- R-11：文档里的强断言（列出给复核者逐条看；不判失败）
    strong = []
    for p in DOC_FILES:
        if not os.path.exists(p):
            continue
        for ln_no, line in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
            for t in STRONG_CLAIM_TERMS:
                if t in line:
                    strong.append(dict(file=os.path.basename(p), line=ln_no, term=t))
    report["R11_strong_claims_in_docs"] = strong
    report["R11_strong_claims_note"] = (
        "不判失败（语义判定不是脚本能做的），但**必须**由人逐条核对："
        "每一条强断言都要有代码或产物支撑；无支撑的必须改写。")

    # ---------------- 汇总
    hard_fail = {
        "R2_rubric_term_hits": report["R2_rubric_term_hits"],
        "R2_width_proxy_hits": report["R2_width_proxy_hits"],
        "R3_self_report_hits": report["R3_self_report_hits"],
        "R5_adhd_hits": report["R5_adhd_hits"],
        "R6_answer_hint_hits": report["R6_answer_hint_hits"],
        "R2_prompt_level_hits": report["R2_prompt_level_hits"],
        "R3_prompt_level_self_report_hits": report["R3_prompt_level_self_report_hits"],
        "R5_prompt_level_adhd_hits": report["R5_prompt_level_adhd_hits"],
        "M4_prompt_level_evidence_leak": report["M4_prompt_level_evidence_leak"],
    }
    report["hard_fail_counts"] = {k: len(v) for k, v in hard_fail.items()}
    report["hard_fail_total"] = sum(report["hard_fail_counts"].values())
    report["R1_blacklist_strict_total"] = bl["strict_hits"]
    report["guards_failed"] = guards
    report["checks_skipped"] = list(guards)
    report["all_pass"] = (
        report["hard_fail_total"] == 0
        and not guards
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
    if guards:
        print("\n结论：守卫触发 ⇒ 检查**未真正执行**，不得据此声称通过", file=sys.stderr)
        for g in guards:
            print("  - %s" % g, file=sys.stderr)
        return 2
    print("\n结论：%s" % ("全部通过" if report["all_pass"] else "存在未通过项"))
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
