# -*- coding: utf-8 -*-
"""**离线**干跑：用打桩的 LLM 跑一遍路线 A，**不发任何 API 调用**。

用途：验证拓扑的控制流、预算守卫、装配与自检逻辑；也用于回归。
（本文件不产出任何实验结论；打桩输出是固定的合成文本。）

⚠️ 本文件是第二轮返工（F1/F2/F4/F9/F14）新增的**回归断言**的所在地。
   旧版只断言「调用数 > 0」⇒ 任何静默退化都看不见（复核发现
   `structured_no_cover` 与 `A_fixed` 逐字节相同却全部「通过」）。
"""
from __future__ import annotations

import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/workspace/lab")

import route_a                                          # noqa: E402
from route_a import run_route, run_b_arm, run_task, save_run, BudgetExceeded   # noqa: E402

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

    def __init__(self, token_per_call=500):
        self.n_api_calls = 0
        self.n_tokens = 0
        self.token_per_call = token_per_call
        self.rec = []
        self._k = 0

    def chat(self, prompt, **kw):
        self.n_api_calls += 1
        self.n_tokens += self.token_per_call
        p = kw.get("purpose", "")
        self.rec.append(type("C", (), dict(model="stub-model"))())
        if p.startswith("A_slot") or p.startswith("A_resample"):
            return GEN
        if p.startswith("A_extract") or p.startswith("B_extract"):
            return CLAIMS
        if p == "A_split":
            return "- 第一档适用 18 吨，每吨 3.5 元。"
        if p == "A_verify" or p.startswith("B3_judge"):
            return VERD
        return GEN


class PoolStub(StubLLM):
    """**按提示词里实际列出的条目**返回抽取结果与裁决（F4/F14 探针用）。

    ⚠️ 裁决行数必须与提示词里的条目数一一对应 ⇒ 这里从提示词里解析出
    「待核验的陈述」清单，而不是用外部列表（否则会掩盖装配口径问题）。
    """

    def __init__(self, claims, verdict_map):
        super().__init__()
        self.pool_claims = list(claims)
        self.verdict_map = dict(verdict_map)

    def _claims_in_prompt(self, prompt):
        tail = (prompt or "").split("待核验的陈述：")[-1]
        out = []
        for ln in tail.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            m = re.match(r"^(\d+)\.\s*(.+)$", ln)
            if m:
                out.append(m.group(2))
        return out

    def chat(self, prompt, **kw):
        p = kw.get("purpose", "")
        self.n_api_calls += 1
        self.n_tokens += self.token_per_call
        self.rec.append(type("C", (), dict(model="stub-model"))())
        if p.startswith("A_slot") or p.startswith("A_resample"):
            return "答案占位，用于生成断言池。"
        if p.startswith("A_extract"):
            return "\n".join("- " + c for c in self.pool_claims)
        if p.startswith("A_verify"):
            items = self._claims_in_prompt(prompt) or self.pool_claims
            return "\n".join(self.verdict_map.get(c, "未提及 1") for c in items)
        return super().chat(prompt, **kw)


def _fail(msg):
    print("  ✗ %s" % msg)
    return False


def main() -> int:
    ok = True
    print("== 正常路径 ==")
    llm = StubLLM()
    log = []
    r = run_route(ASK, EV, cfg=dict(round1_facets=["FA2", "FA3"], round2_facets=["FA4"],
                                    extract_cap=5, max_claims=12, verify_batch=12),
                  llm=llm, log=log)
    m = r["meta"]
    for k in ("n_calls", "n_tokens", "n_pool", "n_shipped", "n_supported",
              "n_contradicted", "n_unmentioned", "n_parsefail", "collapse_flag",
              "collapse_kept", "round2_executed", "conflict_rate_generated",
              "answer_chars", "answer_truncated_count", "models_used"):
        print("  %-24s %s" % (k, m[k]))
    print("  答案:\n%s" % r["answer"])
    ok &= (m["n_calls"] <= 12)
    ok &= (m["round2_executed"] is True)          # F3：N4 恒定执行
    ok &= ("经核验成立的依据" in r["answer"] and len(r["answer"]) > 50)
    ok &= ("依据条目" not in "\n".join(r["gen_prompts"]))
    ok &= (m["evidence_prompt_checks"] >= 0)
    ok &= (m["answer_chars"] <= 400)              # F14：整份答案 ≤ 400

    # ---------------------------------------------------------------- F1 回归
    print("\n== F1 回归：token 预算按任务计（连跑 3 题，第 3 题不得被中止） ==")
    llm3 = StubLLM(token_per_call=400)
    per_task = []
    try:
        for i in range(3):
            rr = run_route(ASK, EV, cfg=dict(round1_facets=["FA2"], round2_facets=["FA4"],
                                             extract_cap=3, max_claims=8, verify_batch=12,
                                             max_tokens=40000),
                           llm=llm3, log=[])
            per_task.append(rr["meta"]["n_tokens"])
            print("  任务 %d: n_calls=%d n_tokens=%d" % (i + 1, rr["meta"]["n_calls"],
                                                         rr["meta"]["n_tokens"]))
    except BudgetExceeded as e:
        ok &= _fail("第 %d 题被预算中止（这正是 F1 的症状）：%s" % (len(per_task) + 1, e))
    if len(per_task) == 3:
        ok &= (per_task[1] == per_task[0])       # 任务 2 的 token 不含任务 1
        ok &= (per_task[2] == per_task[0])
        ok &= _fail("任务 2 的 token 计数含前序任务：%r" % per_task) if per_task[1] != per_task[0] else True
        print("  三个任务的 token 计数：%r ⇒ 逐题独立" % per_task)
    else:
        ok &= _fail("连跑 3 题没有全部完成（只跑了 %d 题）" % len(per_task))

    # ---------------------------------------------------------------- F2 回归
    print("\n== F2 回归：每个消融臂的第二轮 prompt 必须与 A_fixed 逐字节不同 ==")
    base = run_route(ASK, EV, cfg=dict(round1_facets=["FA2"], round2_facets=["FA4"],
                                       extract_cap=3, max_claims=8),
                     llm=StubLLM(), log=[])
    base_prompts = [p for p in base["gen_prompts"]]
    for name, cfg in (("A_minus_D3", dict(resample_mode="structured_no_cover")),
                      ("A_random_rest", dict(resample_mode="random")),
                      ("A_minus_facet", dict(facet_enabled=False))):
        rr = run_route(ASK, EV, cfg=dict(round1_facets=["FA2"], round2_facets=["FA4"],
                                         extract_cap=3, max_claims=8, **cfg),
                       llm=StubLLM(), log=[])
        same = rr["gen_prompts"] == base_prompts
        ok &= (not same)
        if same:
            ok &= _fail("%s 的生成提示词与 A_fixed 逐字节相同 ⇒ 该臂静默退化" % name)
        else:
            print("  %-14s 与 A_fixed 的提示词不同 ✔" % name)
    # A_minus_R2：没有第二轮
    rr = run_route(ASK, EV, cfg=dict(round1_facets=["FA2"], round2_facets=["FA4"],
                                     extract_cap=3, max_claims=8, resample_mode="none"),
                   llm=StubLLM(), log=[])
    ok &= (rr["meta"]["round2_executed"] is False)
    ok &= (rr["meta"]["stage_counts"]["n4_resample"] == 0)
    print("  A_minus_R2    round2_executed=%s ✔" % rr["meta"]["round2_executed"])

    # ---------------------------------------------------------------- F3 回归
    print("\n== F3 回归：塌缩量是诊断量，不控制 N4 ==")
    for mult in (0.0, 1.0, 99.0):
        rr = run_route(ASK, EV, cfg=dict(round1_facets=["FA2"], round2_facets=["FA4"],
                                         extract_cap=3, max_claims=8, collapse_mult=mult),
                       llm=StubLLM(), log=[])
        fired = rr["meta"]["round2_executed"]
        flag = rr["meta"]["collapse_flag"]
        kept = rr["meta"]["collapse_kept"]
        thr = rr["meta"]["collapse_threshold"]
        print("  collapse_mult=%-5s ⇒ round2_executed=%s collapse_flag=%s (kept=%s thr=%s)"
              % (mult, fired, flag, kept, thr))
        ok &= (fired is True)     # 不管塌缩诊断量是多少，第二轮都执行
        # 诊断量必须与公式一致：collapse_flag ⇔ kept < mult × K₁
        ok &= (flag == (kept < thr))
        if flag != (kept < thr):
            ok &= _fail("collapse_flag 与公式不一致：kept=%s thr=%s flag=%s"
                        % (kept, thr, flag))
    rr = run_route(ASK, EV, cfg=dict(round1_facets=["FA2"], round2_facets=["FA4"],
                                     extract_cap=3, max_claims=8, collapse_mult=99.0),
                   llm=StubLLM(), log=[])
    ok &= (rr["meta"]["collapse_flag"] is True)
    print("  collapse_mult=99.0 ⇒ collapse_flag=%s（诊断量仍如实报告）"
          % rr["meta"]["collapse_flag"])

    # ---------------------------------------------------------------- F4 回归
    print("\n== F4 回归：未被支持的近似重复项不得挤掉被支持的条目 ==")
    good = "该服务每月收费 20 元整。"
    junk = "该服务每月收费 20 元。"
    vm = {good: "支持 1", junk: "未提及 1"}

    # 顺序 1：junk 在前
    r1 = run_route(ASK, EV, cfg=dict(round1_facets=["FA1"], round2_facets=[],
                                      extract_cap=5, max_claims=12),
                   llm=PoolStub([junk, good], vm), log=[])
    # 顺序 2：good 在前
    r2 = run_route(ASK, EV, cfg=dict(round1_facets=["FA1"], round2_facets=[],
                                      extract_cap=5, max_claims=12),
                   llm=PoolStub([good, junk], vm), log=[])
    print("  junk 在前 → 答案含被支持条目：%s" % (good in r1["answer"]))
    print("  good 在前 → 答案含被支持条目：%s" % (good in r2["answer"]))
    ok &= (good in r1["answer"])
    ok &= (good in r2["answer"])
    if good not in r1["answer"]:
        ok &= _fail("未支持的近似重复项把被支持的条目挤出了答案（顺序敏感）")
    if good not in r2["answer"]:
        ok &= _fail("未支持的近似重复项把被支持的条目挤出了答案")

    # F4 第二半：改写型重复**不得同时**进答案
    print("\n== F4 回归：改写型重复不得同时进答案 ==")
    a = "首档水量为每月 0 至 18 吨的部分。"
    b = "每月水量在 0 至 18 吨之间的部分属于首档。"
    r3 = run_route(ASK, EV, cfg=dict(round1_facets=["FA1"], round2_facets=[],
                                      extract_cap=5, max_claims=12),
                   llm=PoolStub([a, b], {a: "支持 1", b: "支持 1"}), log=[])
    both = (a in r3["answer"]) and (b in r3["answer"])
    print("  两条改写型重复同时进答案：%s（n_dup_suppressed=%s）"
          % (both, r3["meta"]["n_dup_suppressed"]))
    ok &= (not both)
    if both:
        ok &= _fail("改写型重复同时进了答案 ⇒ 「不冗余」的保证不成立")

    # ---------------------------------------------------------------- F14 回归
    print("\n== F14 回归：超限的条目不得把后面的短条目一起丢掉 ==")
    long_claim = "这是一条特别长的条目，" + "内容" * 25 + "。"
    short_claim = "短条目内容在这里。"
    r4 = run_route(ASK, EV, cfg=dict(round1_facets=["FA1"], round2_facets=[],
                                      extract_cap=5, max_claims=12),
                   llm=PoolStub([long_claim, short_claim],
                                {long_claim: "支持 1", short_claim: "支持 1"}), log=[])
    print("  答案字数=%d 含短条目：%s" % (r4["meta"]["answer_chars"],
                                          short_claim in r4["answer"]))
    ok &= (short_claim in r4["answer"])
    ok &= (r4["meta"]["answer_chars"] <= 400)
    if short_claim not in r4["answer"]:
        ok &= _fail("超限条目导致后面的短条目被一并丢弃（break 偏置）")

    # ---------------------------------------------------------------- F9 回归
    print("\n== F9 回归：B0/B1/B2/B3 可执行且与 A 臂同构 ==")
    for kind, kw in (("B0", {}), ("B1", dict(K=3)), ("B2", dict(T_W=2000)),
                     ("B3", dict(K=2))):
        rr = run_b_arm(ASK, EV, cfg=dict(extract_cap=3, max_claims=8),
                       llm=StubLLM(), log=[], kind=kind, **kw)
        mm = rr["meta"]
        need = ("run_id", "arm_id", "task_id", "rep", "seed", "model", "temperature",
                "prompt_version", "arm_config_hash", "n_calls", "n_tokens", "cost_usd",
                "valid", "total", "parsefail_rate", "silent_empty_count",
                "over_budget_count", "n_pool", "n_shipped", "n_supported",
                "n_contradicted", "n_unmentioned", "conflict_rate_generated",
                "support_rate_generated", "internal_parsefail_rate",
                "answer_truncated_count", "answer_fallback", "collapse_flag",
                "evidence_prompt_checks", "devset_id", "devset_hash",
                "evidence_pack_version", "evidence_hash")
        missing = [k for k in need if k not in mm]
        print("  %-4s calls=%d tokens=%d shipped=%d 缺字段=%s"
              % (kind, mm["n_calls"], mm["n_tokens"], mm["n_shipped"], missing or "无"))
        ok &= (not missing)
        if missing:
            ok &= _fail("%s 臂缺 meta 字段：%s" % (kind, missing))
    try:
        run_b_arm(ASK, EV, llm=StubLLM(), log=[], kind="B1")   # 缺 K
        ok &= _fail("B1 缺 K 时应当报错")
    except ValueError:
        print("  B1 缺 K ⇒ 报错 ✔")

    # ---------------------------------------------------------------- 输出契约
    print("\n== 输出契约：RUNS/<arm>/<task>/rep<k>.{answer.md,meta.json} ==")
    with tempfile.TemporaryDirectory() as td:
        ap, mp = save_run(td, "A_fixed", "DS-01", 1, r["answer"], r["meta"])
        exists = os.path.exists(ap) and os.path.exists(mp)
        print("  %s / %s 存在：%s" % (os.path.basename(ap), os.path.basename(mp), exists))
        ok &= exists
        if not exists:
            ok &= _fail("输出契约未实现")

    # ---------------------------------------------------------------- 预算守卫
    print("\n== 预算守卫（调用数） ==")
    try:
        run_route(ASK, EV, cfg=dict(round1_facets=["FA1", "FA2", "FA3"], max_calls=2,
                                    extract_cap=5, max_claims=12),
                  llm=StubLLM(), log=[])
        ok &= _fail("没有抛异常（预算守卫失效）")
    except BudgetExceeded:
        print("  BudgetExceeded 已抛出 ✔")

    print("\n干跑结果：%s" % ("全部通过" if ok else "有失败项"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
