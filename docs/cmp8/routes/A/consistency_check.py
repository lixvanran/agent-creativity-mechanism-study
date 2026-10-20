# -*- coding: utf-8 -*-
"""**声明 ↔ 实现**的一致性自检（0 次 API 调用，全部用打桩 LLM）。

为什么有这个文件：复核报告 §4 的第 ③ 条指出，负责人的「接线自检不适用 ⇒ 没有『声明存在
但代码不读』的死维风险」这个结论**过强**——路线 A 虽无参数表，但**确实**存在同型的落差
（`collapse_mult` 声明为诊断量、实为开关；`structured_no_cover` 声明、执行器不实现；
`max_tokens` 声明 per-rep、实为进程级；`seed` 声明、代码无且 client 不支持；20/32 个 meta 字段）。
⇒ 这个脚本把「声明 ↔ 实现」的落差变成**机器可查**的清单。

检查项
  C-1 预注册常量：`spec.yaml` ⇄ `route_a.DEFAULTS`（逐项相等）
  C-2 节点编号：`spec.yaml`（N0…N8）⇄ `DESIGN.md` §3.1 的图 ⇄ `route_a.py` 的 docstring
  C-3 对照臂：`spec.yaml` 的 `arms:`（11 条）⇄ `DESIGN.md` §5.1/§5.2 的表
  C-4 否证条件：`spec.yaml` 的 `falsification` ⇄ `DESIGN.md` §7.2（FA-1…FA-11 + FA-8a/FA-8b）
  C-5 `meta.json` 字段：`DESIGN.md` §6.4 的表 ⇄ **代码实际产出**（用打桩 LLM 真跑一遍）
  C-6 拓扑不变量：`collapse_mult` 不控制任何分支；N4 恒定执行（除臂级常量 `resample_mode`）
  C-7 输出契约：`save_run()` 真的写出协议 §8 (a2) 要求的两个文件
  C-8 消融臂不静默退化：每个消融臂的生成提示词必须与 `A_fixed` **逐字节不同**
  C-9 `spec.yaml` 能被**两种 YAML 解析器**读出同样的结构（极简解析器 vs PyYAML，若有）

用法：python3 consistency_check.py
退出码 0 = 全部一致。
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/workspace/lab")

import route_a                                          # noqa: E402
import facets as F                                      # noqa: E402

OK = True
NOTES = []


def chk(name, cond, extra=""):
    global OK
    cond = bool(cond)
    OK &= cond
    print("  [%s] %-44s %s" % ("OK " if cond else "FAIL", name, extra))
    return cond


def mini_yaml(path):
    """用 `build_spec_flowchart.py` 自带的极简解析器读 spec（与流程图渲染器同款）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_bsf", "/workspace/lab/build_spec_flowchart.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.load_yaml(path)


class StubLLM:
    """打桩 LLM：**0 次 API 调用**。"""

    def __init__(self):
        self.n_api_calls = 0
        self.n_tokens = 0
        self.rec = []

    def chat(self, prompt, **kw):
        self.n_api_calls += 1
        self.n_tokens += 100
        self.rec.append(type("C", (), dict(model="stub"))())
        p = kw.get("purpose", "")
        if p.startswith("A_extract"):
            return "- 合成断言一，用于一致性自检。\n- 合成断言二，用于一致性自检。"
        if p.startswith("A_verify"):
            return "支持 1\n支持 2"
        if p == "A_split":
            return "- 合成断言一，用于一致性自检。"
        return "合成回答内容，用于一致性自检。"


ASK = "合成诊断题：某项服务每月收费 20 元，题面已给足全部条件。"
EV = [dict(id="EV-S-01", text="合成依据条目：某项服务每月收费 20 元。")]


def main() -> int:
    design = io.open(os.path.join(HERE, "DESIGN.md"), encoding="utf-8").read()
    y = mini_yaml(os.path.join(HERE, "spec.yaml"))
    const = y.get("constants") or {}

    print("== C-1 预注册常量：spec.yaml ⇄ route_a.DEFAULTS ==")
    D = route_a.DEFAULTS
    chk("round1_facets", const.get("round1_facets") == D["round1_facets"])
    chk("round2_facets", const.get("round2_facets") == D["round2_facets"])
    chk("max_calls_per_rep", const.get("max_calls_per_rep") == D["max_calls"])
    chk("max_tokens_per_rep", const.get("max_tokens_per_rep") == D["max_tokens"])
    chk("max_claims", const.get("max_claims") == D["max_claims"])
    chk("extract_cap_per_slot", const.get("extract_cap_per_slot") == D["extract_cap"])
    chk("verify_batch", const.get("verify_batch") == D["verify_batch"])
    chk("answer_char_cap", const.get("answer_char_cap") == D["answer_char_cap"])
    chk("lex_thr", const.get("lex_thr") == D["lex_thr"])
    chk("struct_thr", const.get("struct_thr") == D["struct_thr"])
    chk("collapse_mult", const.get("collapse_mult") == D["collapse_mult"])
    chk("temperature", const.get("temperature") == D["temp"])
    chk("prompt_version", const.get("prompt_version") == F.PROMPT_VERSION)
    chk("seed_policy 声明存在", bool(const.get("seed_policy")))
    chk("seed_policy 写明不可复现", "NOT_reproducible" in (const.get("seed_policy") or ""))

    print("== C-2 节点编号：spec ⇄ DESIGN 图 ⇄ 代码 docstring ==")
    ids = [n["id"] for n in (y.get("nodes") or [])]
    chk("spec 节点 = N0…N8", ids == ["N%d" % i for i in range(9)], str(ids))
    doc = io.open(os.path.join(HERE, "route_a.py"), encoding="utf-8").read().split('"""')[1]
    for nid in ids:
        chk("DESIGN 图含 %s" % nid, (nid + " ") in design)
        chk("代码 docstring 含 %s" % nid, nid in doc)
    chk("DESIGN 的 §3.1 声明 N0…N8", "N0…N8" in design)

    print("== C-3 对照臂：spec.arms ⇄ DESIGN §5 ==")
    arms = [a["id"] for a in (y.get("arms") or [])]
    need = ["A_fixed", "B0_direct", "B1_eq_calls", "B2_eq_token", "B3_best_of_n",
            "A_minus_facet", "A_minus_D3", "A_random_rest", "A_minus_R2",
            "A_minus_utility", "A_minus_novel"]
    chk("spec arms = 11 条且齐全", arms == need, str(len(arms)))
    for a in need:
        chk("DESIGN 提到 %s" % a, a in design)
    chk("B0–B3 都有实现入口", hasattr(route_a, "run_b_arm"))

    print("== C-4 否证条件：spec.falsification ⇄ DESIGN §7.2 ==")
    fa = [f["id"] for f in (y.get("falsification") or {}).get("route_specific", [])]
    chk("FA-1…FA-11 + FA-8a/FA-8b", fa == ["FA-%d" % i for i in range(1, 8)]
        + ["FA-8a", "FA-8b", "FA-9", "FA-10", "FA-11"], str(fa))
    for fid in fa:
        chk("DESIGN 提到 %s" % fid, fid in design)
    chk("没有裸 FA-8（已拆成 a/b）", "FA-8" not in fa)

    print("== C-5 meta.json 字段：DESIGN §6.4 ⇄ 代码实际产出 ==")
    r = route_a.run_route(ASK, EV, cfg=dict(round1_facets=["FA1"], round2_facets=["FA2"],
                                            extract_cap=2, max_claims=6),
                          llm=StubLLM(), log=[])
    need_fields = ["run_id", "arm_id", "task_id", "rep", "seed", "seed_policy",
                   "seed_effective", "reproducibility", "run_nonce", "model",
                   "model_requested", "models_used", "models_tier", "temperature",
                   "prompt_version", "prompt_hash", "arm_config_hash", "n_calls",
                   "n_tokens", "cost_usd", "cost_basis", "valid", "total",
                   "valid_samples", "total_samples", "over_budget_count",
                   "parsefail_rate", "internal_parsefail_rate", "silent_empty_count",
                   "n_silent_empty", "n_empty_retry", "n_pool", "n_shipped",
                   "n_supported", "n_contradicted", "n_unmentioned", "n_unverified",
                   "n_parsefail", "conflict_rate_generated", "support_rate_generated",
                   "answer_truncated_count", "answer_truncated_denominator",
                   "answer_fallback", "answer_chars", "n_dup_suppressed",
                   "collapse_flag", "evidence_prompt_checks", "devset_id",
                   "devset_hash", "evidence_pack_version", "evidence_hash",
                   "protocol_a4_not_produced", "metadata_missing", "stage_counts",
                   "scope_kind", "round2_executed", "collapse_kept", "collapse_threshold"]
    miss = [f for f in need_fields if f not in r["meta"]]
    chk("meta 字段齐全（%d 项）" % len(need_fields), not miss, str(miss))
    for f in need_fields:
        if f in ("n_pool", "n_shipped", "n_supported", "n_contradicted", "n_unmentioned",
                 "n_parsefail", "n_unverified", "conflict_rate_generated",
                 "support_rate_generated", "internal_parsefail_rate",
                 "answer_truncated_count", "answer_fallback", "collapse_flag",
                 "evidence_prompt_checks", "n_calls", "n_tokens", "silent_empty_count",
                 "n_silent_empty", "n_empty_retry", "n_dup_suppressed", "answer_chars"):
            chk("DESIGN §6.4 列了 %s" % f, f in design)

    print("== C-6 拓扑不变量 ==")
    for mult in (0.0, 1.0, 99.0):
        rr = route_a.run_route(ASK, EV, cfg=dict(round1_facets=["FA1"],
                                                  round2_facets=["FA2"],
                                                  extract_cap=2, max_claims=6,
                                                  collapse_mult=mult),
                                llm=StubLLM(), log=[])
        chk("collapse_mult=%s ⇒ N4 仍执行" % mult, rr["meta"]["round2_executed"] is True)
        chk("collapse_mult=%s ⇒ 诊断量与公式一致" % mult,
            rr["meta"]["collapse_flag"] == (rr["meta"]["collapse_kept"]
                                            < rr["meta"]["collapse_threshold"]))
    rr = route_a.run_route(ASK, EV, cfg=dict(round1_facets=["FA1"], round2_facets=["FA2"],
                                              extract_cap=2, max_claims=6,
                                              resample_mode="none"),
                            llm=StubLLM(), log=[])
    chk("resample_mode=none（臂级常量）⇒ 不做第二轮",
        rr["meta"]["round2_executed"] is False)
    try:
        route_a.run_route(ASK, EV, cfg=dict(resample_mode="structured_no_cover_typo"),
                          llm=StubLLM(), log=[])
        chk("非法 resample_mode ⇒ 报错", False)
    except ValueError:
        chk("非法 resample_mode ⇒ 报错", True)

    print("== C-7 输出契约 ==")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        ap, mp = route_a.save_run(td, "A_fixed", "DS-X", 1, r["answer"], r["meta"])
        chk("answer.md 写出", os.path.exists(ap))
        chk("meta.json 写出", os.path.exists(mp))
        try:
            d = json.load(open(mp, encoding="utf-8"))
            chk("meta.json 可解析且含 arm_id", d.get("arm_id") == "A_fixed")
        except Exception as e:                            # noqa: BLE001
            chk("meta.json 可解析", False, repr(e))

    print("== C-8 消融臂不静默退化（与 A_fixed 逐字节不同） ==")
    base = route_a.run_route(ASK, EV, cfg=dict(round1_facets=["FA1"], round2_facets=["FA2"],
                                               extract_cap=2, max_claims=6),
                             llm=StubLLM(), log=[])["gen_prompts"]
    for name, cfg in (("A_minus_D3", dict(resample_mode="structured_no_cover")),
                      ("A_random_rest", dict(resample_mode="random")),
                      ("A_minus_facet", dict(facet_enabled=False))):
        rr = route_a.run_route(ASK, EV, cfg=dict(round1_facets=["FA1"],
                                                 round2_facets=["FA2"],
                                                 extract_cap=2, max_claims=6, **cfg),
                                llm=StubLLM(), log=[])
        chk("%s 与 A_fixed 的 prompt 不同" % name, rr["gen_prompts"] != base)

    print("== C-9 spec 可被两种 YAML 解析器读出同样结构 ==")
    try:
        import yaml
        y2 = yaml.safe_load(io.open(os.path.join(HERE, "spec.yaml"), encoding="utf-8"))
        chk("PyYAML 可解析", True)
        chk("节点数一致", len(y2.get("nodes") or []) == len(ids))
        chk("边数一致", len(y2.get("edges") or []) == len(y.get("edges") or []))
        chk("臂数一致", len(y2.get("arms") or []) == len(arms))
        chk("常量一致", (y2.get("constants") or {}) == const)
    except ImportError:
        NOTES.append("PyYAML 未安装 ⇒ 只用极简解析器验证（该解析器比 PyYAML 更严："
                     "行内 `{…}` 会被解析坏，所以 spec 全部用块状写法）")
        print("  [NOTE] PyYAML 未安装（用极简解析器验证）")

    print("\n一致性自检结果：%s" % ("全部一致" if OK else "有不一致"))
    for n in NOTES:
        print("  NOTE: %s" % n)
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
