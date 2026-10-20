# -*- coding: utf-8 -*-
"""**离线**干跑：用打桩的 LLM 跑一遍路线 A，**不发任何 API 调用**。

用途：验证拓扑的控制流、预算守卫、装配与自检逻辑；也用于回归。
（本文件不产出任何实验结论；打桩输出是固定的合成文本。）
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/workspace/lab")

import route_a                                          # noqa: E402
from route_a import run_route, BudgetExceeded           # noqa: E402

ASK = "某地阶梯价：第一档 0–18 吨每吨 3.5 元，超过 18 吨的部分每吨 5 元。某户当月用水 24 吨，应缴多少元？"
EV = [
    dict(id="EV-T-01", text="第一档为每月 0–18 吨的部分，每吨 3.5 元。"),
    dict(id="EV-T-02", text="超过 18 吨的部分每吨 5 元。"),
    dict(id="EV-T-03", text="阶梯价按实际用水量分档累加计算。"),
]

GEN = ("这是一个测试用的合成回答。第一档适用 18 吨，每吨 3.5 元，"
       "18×3.5＝63 元。超过 18 吨的部分共 6 吨，每吨 5 元，合计 30 元。"
       "因此当月水费为 63＋30＝93 元。按月计费。")
CLAIMS = ("- 第一档适用 18 吨。\n- 第一档水价为每吨 3.5 元。\n"
          "- 超过 18 吨的部分每吨 5 元。\n- 18×3.5＝63 元。\n"
          "- 超过部分 6×5＝30 元。\n- 当月水费合计 93 元。")
VERD = "非主张\n支持 1\n支持 2\n支持 1\n支持 1\n支持 3"


class StubLLM:
    """不打网络的假 LLM。"""

    def __init__(self):
        self.n_api_calls = 0
        self.n_tokens = 0
        self._k = 0

    def chat(self, prompt, **kw):
        self.n_api_calls += 1
        self.n_tokens += 500
        p = kw.get("purpose", "")
        if p.startswith("A_slot") or p.startswith("A_resample"):
            return GEN
        if p.startswith("A_extract"):
            return CLAIMS
        if p == "A_split":
            return "- 第一档适用 18 吨，每吨 3.5 元。"
        if p == "A_verify":
            return VERD
        return GEN


def main() -> int:
    ok = True
    llm = StubLLM()
    log = []
    r = run_route(ASK, EV, cfg=dict(round1_facets=["FA2", "FA3"], round2_facets=["FA4"],
                                    extract_cap=5, max_claims=12, verify_batch=12,
                                    collapse_mult=99.0),
                  llm=llm, log=log)
    m = r["meta"]
    print("== 正常路径 ==")
    for k in ("n_calls", "n_tokens", "n_pool", "n_supported", "n_contradicted",
              "n_unmentioned", "n_parsefail", "trigger_fired", "trigger_kept",
              "conflict_rate_generated", "answer_chars"):
        print("  %-24s %s" % (k, m[k]))
    print("  答案:\n%s" % r["answer"])
    ok &= (m["n_calls"] <= 12)
    ok &= (m["trigger_fired"] is True)
    ok &= ("经核验成立的依据" in r["answer"] and len(r["answer"]) > 50)
    ok &= ("依据条目" not in "\n".join(r["gen_prompts"]))
    ok &= (m["evidence_prompt_checks"] >= 0)

    # ---- 预算守卫
    llm2 = StubLLM()
    try:
        run_route(ASK, EV, cfg=dict(round1_facets=["FA1", "FA2", "FA3"], max_calls=2,
                                    extract_cap=5, max_claims=12),
                  llm=StubLLM(), log=[])
        print("== 预算守卫 == FAILED（没有抛异常）")
        ok = False
    except BudgetExceeded:
        print("== 预算守卫 == OK（BudgetExceeded 已抛出）")

    # ---- 消融：去承载面 / 随机休息 / 无效用轴
    for name, cfg in (("A_minus_facet", dict(facet_enabled=False)),
                      ("A_random_rest", dict(resample_mode="random", collapse_mult=99.0)),
                      ("A_minus_utility", dict(utility_axis=False)),
                      ("A_minus_novel", dict(novel_axis=False)),
                      ("A_no_resample", dict(resample_mode="none"))):
        llm3 = StubLLM()
        rr = run_route(ASK, EV, cfg=dict(round1_facets=["FA2", "FA3"], round2_facets=["FA4"],
                                         extract_cap=5, max_claims=12, verify_batch=12,
                                         **cfg), llm=llm3, log=[])
        print("== %s == calls=%d pool=%d 答案字数=%d" %
              (name, rr["meta"]["n_calls"], rr["meta"]["n_pool"], rr["meta"]["answer_chars"]))
        ok &= (rr["meta"]["n_calls"] > 0)

    print("\n干跑结果：%s" % ("全部通过" if ok else "有失败项"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
