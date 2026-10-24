# -*- coding: utf-8 -*-
"""路线 C · 提案者机制自检（**假 LLM，0 次真实 API 调用**）。

检验 DESIGN.md §3.2 的三条声明是否真的由代码实现：
  ① `structural_diagnostics` 是**唯一入口**，且返回结构里**不含任何 oracle 统计**
     （白名单投影 + 序列化后关键字扫描 + 浮点禁止 + 白名单外键禁止）。
  ② 结构检查器 H1–H6 真的会把"越界模板"判不合格。
  ③ 修复 ≤2 次后**强制回退**到人定默认，且回退这件事**被记录**（不隐藏）。
另测：诊断载荷里塞进 oracle 字段 ⇒ `assert_no_oracle_leak` 必须抛错（不是静默通过）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proposer as PR
from topology import TEMPLATES, TEMPLATE_IDS


class FakeLLM:
    """按预设脚本返回提案文本。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.prompts = []

    def chat(self, prompt, **kw):
        self.calls += 1
        self.prompts.append(prompt)
        return self.script[min(self.calls - 1, len(self.script) - 1)]


def fake_episodes(n=2):
    eps = []
    for i in range(n):
        eps.append(dict(
            topology="T2", n_calls=6, answer_chars=200, n_parse_failed=0,
            stage_log=[dict(stage="GEN"), dict(stage="EXTRACT"),
                       dict(stage="VERIFY"), dict(stage="MERGE")],
            # ⚠️ 下面这些字段**必须不出现在**提案者的诊断里
            conflict_rate_pre=0.5, support_rate=0.5, n_supported_distinct=7,
            n_claims_total=9, claims=[dict(text="秘密", verdict="支持")],
            key_conclusion_hit=1.0))
    return eps


def main():
    ok = True
    eps = fake_episodes()

    # ① 白名单投影
    diag = PR.structural_diagnostics(eps)
    print("[1] 白名单诊断：%s" % diag)
    ok = ok and set(diag) <= set(PR.ALLOWED_KEYS)
    blob = str(diag)
    for bad in ("conflict", "support", "verdict", "claims", "key_conclusion"):
        if bad in blob.lower():
            print("    ! 泄漏：%s" % bad)
            ok = False
    print("    泄漏词扫描：%s" % ("干净" if ok else "**有泄漏**"))

    # ② oracle 字段混入必须抛错
    try:
        PR.assert_no_oracle_leak(dict(diag, conflict_rate=0.5))
        print("[2] oracle 字段混入：未抛错 ⇒ **FAIL**")
        ok = False
    except AssertionError as e:
        print("[2] oracle 字段混入：已抛错（%s）" % str(e)[:60])

    # ③ 浮点（比率形态）必须抛错
    try:
        PR.assert_no_oracle_leak(dict(diag, n_episode_calls_max=1.5))
        print("[3] 浮点比率：未抛错 ⇒ **FAIL**")
        ok = False
    except AssertionError as e:
        print("[3] 浮点比率：已抛错（%s）" % str(e)[:60])

    # ④ 正常提案：一次通过
    llm = FakeLLM(["TOPOLOGY: T3\nREASON: 拆分回环提高可承重粒度"])
    r = PR.run_proposal(llm, eps)
    print("[4] 正常提案：template=%s accepted=%s fell_back=%s attempts=%d"
          % (r["template_id"], r["accepted"], r["fell_back"], r["attempts"]))
    ok = ok and r["template_id"] == "T3" and r["accepted"] and r["attempts"] == 1

    # ⑤ 格式错 → 修复 → 通过
    llm = FakeLLM(["随便说点什么",
                   "TOPOLOGY: T4\nREASON: 停滞重分配把预算给未覆盖的认知位置"])
    r = PR.run_proposal(llm, eps)
    print("[5] 修一次后通过：template=%s accepted=%s attempts=%d last_error=%s"
          % (r["template_id"], r["accepted"], r["attempts"], r["last_error"]))
    ok = ok and r["accepted"] and r["attempts"] == 2

    # ⑥ 一直不合格 → 修复 ≤2 次后**强制回退**到 T2
    llm = FakeLLM(["TOPOLOGY: T99\nREASON: 不存在的模板"])
    r = PR.run_proposal(llm, eps, max_repair=2)
    print("[6] 强制回退：template=%s accepted=%s fell_back=%s attempts=%d last_error=%s"
          % (r["template_id"], r["accepted"], r["fell_back"], r["attempts"],
             r["last_error"][:50]))
    ok = ok and r["fell_back"] and r["template_id"] == "T2" and r["attempts"] == 3

    # ⑦ 提示词里**不得**含 oracle 统计（检查嵌入的诊断 JSON 块，而不是说明书里
    #    "禁止出现矛盾率/支持率"这类**否定式列举**——那不是泄漏）
    import json as _json
    import re as _re
    llm = FakeLLM(["TOPOLOGY: T0\nREASON: x"])
    PR.run_proposal(llm, eps)
    prompt = llm.prompts[0]
    m = _re.search(r"```json\n(.*?)\n```", prompt, _re.S)
    block = m.group(1) if m else ""
    leaked = [w for w in ("conflict_rate", "support_rate", "vd_net", "key_conclusion_hit",
                          "n_supported", "n_claims", "claims", "verdict", "0.5", "1.0",
                          "秘密")
              if w in block]
    same = (_json.loads(block) == diag) if block else False
    print("[7] 提示词内诊断块：%s｜与白名单载荷逐字相同=%s"
          % ("干净" if not leaked else "**泄漏 %s**" % leaked, same))
    ok = ok and not leaked and same

    # ⑧ 结构检查器对全部模板的判定
    bad = [t for t in TEMPLATE_IDS if PR.structural_check(TEMPLATES[t])]
    print("[8] 菜单内 %d 个模板全部通过结构检查：%s" % (len(TEMPLATE_IDS), not bad))
    ok = ok and not bad

    # ⑨ ★ 变异注入（复核 6c 的要求）：把一个 oracle 统计塞进**源 episode 字典** ⇒
    #    提案者看到的诊断载荷必须**逐字不变**（= 白名单把它彻底挡掉，不是"过滤后仍被看见"）
    import copy as _copy
    polluted = _copy.deepcopy(eps)
    for e in polluted:
        e["conflict_rate_pre"] = 0.99          # 典型的 oracle 统计
        e["n_supported_distinct"] = 42
        e["key_conclusion_hit"] = 1.0
        e["verdicts"] = [{"text": "机密", "verdict": "支持"}]
    diag2 = PR.structural_diagnostics(polluted)
    same = (diag2 == diag)
    print("[9] 变异注入（源 episode 塞进 oracle 统计）：载荷逐字不变=%s%s"
          % (same, "" if same else " ⇒ **FAIL**"))
    ok = ok and same

    # ⑩ ★ 变异注入（直接塞进载荷）⇒ 白名单**必须拒掉**（抛错，不是静默通过）
    for injected in (dict(conflict_rate=0.5), dict(key_conclusion_hit=1.0),
                     dict(n_supported_distinct=7)):
        try:
            PR.assert_no_oracle_leak(dict(diag, **injected))
            print("[10] 注入 %s：未抛错 ⇒ **FAIL**" % list(injected)[0])
            ok = False
        except AssertionError:
            pass
    print("[10] 变异注入（直接塞进载荷）：3/3 都被拒掉 ⇒ PASS")

    # ⑪ 提案流程**真的**经过白名单入口（不是只在文档里）
    llm = FakeLLM(["TOPOLOGY: T1\nREASON: x"])
    r = PR.run_proposal(llm, eps)
    same_entry = (r.get("diagnostics") == diag)
    ok = ok and same_entry
    print("[11] run_proposal 走的是白名单入口（返回的 diagnostics == structural_diagnostics）：%s"
          % same_entry)

    print("\n结果：%s（假 LLM，0 次真实 API 调用）" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
