#!/usr/bin/env python3
"""工作包三 · 五个离线测试（★ 纯函数、无 LLM 调用）。

★ **这些测试只证明"规则落实"，不证明"能力提高"**（外部来信原话：
  「接口自检通过只证明设计落实，不证明能力提高」）。

用法：python3 workpack3_tests.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# ─────────────────────────────────────────────────────────────
# 状态与动作接口（与 WORKPACK3_MIN_ARCHITECTURE.md 一一对应）
# ─────────────────────────────────────────────────────────────
ACTIONS = ("explore", "check", "connect", "rollback", "switch", "organize", "stop")


@dataclass
class SubGoal:
    text: str
    index: int
    origin: str                      # ★ "它怎么来的"
    evidence: List[str] = field(default_factory=list)
    revoked_by: Optional[str] = None


@dataclass
class Hypothesis:
    claim: str
    evidence: List[str] = field(default_factory=list)
    status: str = "open"             # open | confirmed | refuted
    refuted_by: Optional[str] = None


@dataclass
class SwitchPoint:
    frm: str
    to: str
    trigger: str
    cost: int = 1


@dataclass
class State4:
    keeps: List[str] = field(default_factory=list)
    hypotheses: List[Hypothesis] = field(default_factory=list)
    switch_points: List[SwitchPoint] = field(default_factory=list)
    subgoal: Optional[SubGoal] = None
    budget: dict = field(default_factory=lambda: {"calls_left": 10, "tokens_left": 100000})
    history: List[dict] = field(default_factory=list)
    # 运行期
    last_action: Optional[str] = None
    last_fail_sig: Optional[str] = None
    fail_streak: int = 0
    method_id: str = "M0"
    kept_candidates: List[dict] = field(default_factory=list)

    def log(self, **kw):
        self.history.append(kw)


# ─────────────────────────────────────────────────────────────
# 更新规则（纯函数）
# ─────────────────────────────────────────────────────────────
DEADLOCK_N = 3


def r1_set_subgoal(st: State4, text: str, evidence: List[str], origin: str = "model") -> SubGoal:
    """R1 子目标生成（★ 取值必须由模型给；代码只结构化 + 记账）。"""
    sg = SubGoal(text=text, index=len(st.history) + 1, origin=origin, evidence=list(evidence))
    st.subgoal = sg
    st.log(event="subgoal_set", index=sg.index, origin=origin, text=text[:40], evidence=list(evidence))
    return sg


def r2_check_hypothesis(st: State4, claim: str, new_evidence: List[str], refuted: bool) -> Hypothesis:
    """R2 假设检验与反证 ⇒ 若 refuted 则撤销由它支撑的 subgoal。"""
    h = next((x for x in st.hypotheses if x.claim == claim), None)
    if h is None:
        h = Hypothesis(claim=claim)
        st.hypotheses.append(h)
    h.evidence.extend(new_evidence)
    if refuted:
        h.status = "refuted"
        h.refuted_by = new_evidence[0] if new_evidence else "no_evidence"
        if st.subgoal is not None and st.subgoal.revoked_by is None:
            st.subgoal.revoked_by = "hypothesis_refuted:%s" % claim
            st.log(event="subgoal_revoked", by="refuted", claim=claim)
        st.log(event="hypothesis_refuted", claim=claim, evidence=list(new_evidence))
    else:
        h.status = "confirmed"
        st.log(event="hypothesis_confirmed", claim=claim, evidence=list(new_evidence))
    return h


def r3_deadlock(st: State4, action: str, fail_sig: str) -> Optional[str]:
    """R3 重复死路：连续 N 次同动作 + 同失败签名 ⇒ 强制打断（不许继续同动作）。"""
    if action == st.last_action and fail_sig == st.last_fail_sig:
        st.fail_streak += 1
    else:
        st.fail_streak = 1
    st.last_action, st.last_fail_sig = action, fail_sig
    if st.fail_streak >= DEADLOCK_N:
        # 优先 rollback（若有换路点），否则 switch
        if st.switch_points:
            sp = st.switch_points[0]
            st.log(event="deadlock_break", mode="rollback", to=sp.to)
            return "rollback"
        st.log(event="deadlock_break", mode="switch")
        return "switch"
    return None


def r4_rollback(st: State4) -> str:
    """R4 回退：撤销本段 subgoal + 换方法标识 + 动作类型改变。"""
    if st.subgoal is not None and st.subgoal.revoked_by is None:
        st.subgoal.revoked_by = "rollback"
        st.log(event="subgoal_revoked", by="rollback")
    sp = st.switch_points[0] if st.switch_points else SwitchPoint("explore", "check", "manual")
    st.method_id = "M1"
    st.log(event="rollback", frm=sp.frm, to=sp.to)
    return sp.to


def r5_switch(st: State4, new_method_id: str) -> bool:
    """R5 换路：★ 方法标识必须**实质不同**（否则只是重新措辞 ⇒ 不算换路）。"""
    if new_method_id == st.method_id:
        return False
    old = st.method_id
    st.method_id = new_method_id
    st.log(event="switch", frm=old, to=new_method_id)
    return True


def r6_stop(st: State4, reason: str) -> None:
    st.log(event="stop", reason=reason)


def r7_account_call(st: State4, ok: bool) -> None:
    """R7 预算记账：★ **失败调用同样扣预算**（不静默）。"""
    st.budget["calls_left"] = max(0, int(st.budget["calls_left"]) - 1)
    st.log(event="call_accounted", ok=bool(ok), calls_left=st.budget["calls_left"])


def keep_candidates_ties(cands: List[dict], scores: List[float], keep_ties: bool = True) -> List[dict]:
    """T3：合法分歧保留 ⇒ **并列全留**（不因 greedy 取一而丢）。"""
    if not cands:
        return []
    mx = max(scores)
    if keep_ties:
        return [c for c, s in zip(cands, scores) if abs(s - mx) < 1e-12]
    return [cands[scores.index(mx)]]


# ─────────────────────────────────────────────────────────────
# 五个离线测试
# ─────────────────────────────────────────────────────────────
def t1_deadlock():
    st = State4(switch_points=[SwitchPoint("explore", "check", "deadlock")])
    forced = None
    for _ in range(DEADLOCK_N):
        forced = r3_deadlock(st, "explore", "err:timeout|same_target")
    assert forced in ("rollback", "switch"), forced
    assert st.history[-1]["event"] == "deadlock_break", st.history[-1]
    nxt = "rollback" if forced == "rollback" else "switch"
    assert nxt != "explore"
    return "✔ T1 重复死路 → 强制打断（动作类型改变）"


def t2_refutation_rollback():
    st = State4()
    r1_set_subgoal(st, "把 X 写清楚", ["gap1"])
    r2_check_hypothesis(st, "X 值得写", ["gap1 已消失"], refuted=True)
    ev = [h["event"] for h in st.history]
    assert "subgoal_revoked" in ev, ev
    assert st.subgoal.revoked_by is not None
    return "✔ T2 反证触发撤销（假设被推翻 ⇒ 子目标撤销 + 留痕）"


def t3_ties_kept():
    cands = [{"src": "a"}, {"src": "b"}]
    kept = keep_candidates_ties(cands, [0.5, 0.5], keep_ties=True)
    assert len(kept) == 2, kept
    one = keep_candidates_ties(cands, [0.5, 0.5], keep_ties=False)
    assert len(one) == 1
    return "✔ T3 合法分歧保留（并列全留 ⇒ 2 个，不被贪心吃掉）"


def t4_subgoal_revoke():
    st = State4()
    r1_set_subgoal(st, "先做 A", ["gap1"])
    st.subgoal.revoked_by = "evidence_invalid"
    st.log(event="subgoal_revoked", by="evidence_invalid")
    r1_set_subgoal(st, "改做 B", ["gap2"], origin="rollback")
    assert st.subgoal is not None and st.subgoal.origin == "rollback"
    ev = [h["event"] for h in st.history]
    assert "subgoal_set" in ev and "subgoal_revoked" in ev, ev
    assert st.subgoal.origin == "rollback"          # ★ "它怎么来的"必须被记录
    return "✔ T4 子目标撤销（撤销留痕 + 新 subgoal 的 origin 被记录）"


def t5_budget_and_failed_calls():
    st = State4(budget={"calls_left": 1, "tokens_left": 1000})
    r7_account_call(st, ok=False)                   # ★ 失败调用也扣预算
    assert st.budget["calls_left"] == 0, st.budget
    if st.budget["calls_left"] == 0:
        r6_stop(st, "budget_exhausted")
    ev = [h["event"] for h in st.history]
    assert "stop" in ev and st.history[-1]["reason"] == "budget_exhausted"
    assert any(h.get("ok") is False for h in st.history), "失败调用必须留痕"
    return "✔ T5 预算用尽与失败调用（失败同样扣预算 ⇒ 0，且留痕不删）"


def main():
    print("=" * 74)
    print("工作包三 · 五个离线测试")
    print("★ 只证明【规则落实】，不证明【能力提高】")
    print("=" * 74)
    res = []
    for fn in (t1_deadlock, t2_refutation_rollback, t3_ties_kept,
               t4_subgoal_revoke, t5_budget_and_failed_calls):
        try:
            res.append((True, fn()))
        except AssertionError as e:
            res.append((False, "✘ %s 失败：%s" % (fn.__name__, e)))
    for ok, msg in res:
        print("  " + msg)
    n = sum(1 for o, _ in res if o)
    print("-" * 74)
    print("  %d/%d 通过" % (n, len(res)))
    print("  ⚠️ 全绿只意味着规则被落实；★ 不构成任何能力结论。")
    raise SystemExit(0 if n == len(res) else 1)


if __name__ == "__main__":
    main()
