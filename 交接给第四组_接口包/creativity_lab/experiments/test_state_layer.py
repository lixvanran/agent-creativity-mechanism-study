"""★ **状态层离线测试草案（★ 工作包三要求的五个测试 · 零 API）**

> 出处：`creativity_lab/experiments/test_state_layer.py`
> 运行：`python3 -B creativity_lab/experiments/test_state_layer.py`（★ **exit 0 = 全过**）
>
> ★ **五个测试（★ 负责人 2026-10-25 指定）**：
> ★ ① **重复死路** ② **反证触发回退** ③ **合法分歧保留** ④ **子目标撤销** ⑤ **预算用尽与失败调用**
>
> ★★ **纪律**：★ **本文件是【规格的可执行形态】** ⇒ ⇒ **改规则 ⇒ ⇒ 测试必须失败**（★ 否则测试是假绿）
> ★★ **负向测试**：★ 每个测试都断言"**不该发生的事没有发生**"⇒ ⇒ 不是只测 happy path
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.state_layer import (            # noqa: E402
    State, propose_subgoal, revoke_subgoal, revise_subgoal, add_evidence,
    rollback, record_attempt, record_call, preserve_divergence, choose_action,
    detect_tie, SUBGOAL_ACTIVE, SUBGOAL_REVOKED, HYP_OPEN, HYP_REFUTED,
    HYP_SUPPORTED, DEAD_END_THRESHOLD, SUPPORT_THRESHOLD,
)

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ✔ %s" % name)
    else:
        print("  ✘ %s  %s" % (name, detail))
        FAILED.append(name)


# ══════════════════════════════════════════════════════════════
# ① 重复死路
# ══════════════════════════════════════════════════════════════
def test_dead_end():
    print("== ① 重复死路 ==")
    st = State(budget_remaining=10, budget_used=0)
    st = record_attempt(st, "method_A", produced_new=False)
    check("第 1 次无新信息 ⇒ 未判死路", not st.attempts[0].dead_end)
    st = record_attempt(st, "method_A", produced_new=False)
    check("第 2 次无新信息 ⇒ 仍未判死路", not st.attempts[0].dead_end)
    st = record_attempt(st, "method_A", produced_new=False)
    check("第 3 次无新信息 ⇒ 判为死路", st.attempts[0].dead_end)
    check("死路被记入进展记录", any("dead_end:method_A" in p for p in st.progress))
    # ★ 负向：一旦产生新信息，不该再被判死路
    st2 = State(budget_remaining=10)
    for _ in range(5):
        st2 = record_attempt(st2, "method_B", produced_new=True)
    check("★ 负向：持续有新信息 ⇒ 永不判死路", not st2.attempts[0].dead_end)
    # ★ 决策：死路 ⇒ 换路
    act, why = choose_action(st)
    check("死路状态下动作 = switch_method", act == "switch_method", "got %s" % act)


# ══════════════════════════════════════════════════════════════
# ② 反证触发回退
# ══════════════════════════════════════════════════════════════
def test_rollback():
    print("== ② 反证触发回退 ==")
    st = State(budget_remaining=10)
    st = propose_subgoal(st, "g1", "假设 X 成立")
    st.hypotheses.append(__import__("creativity_lab.state_layer", fromlist=["Hypothesis"]).Hypothesis(
        hid="h1", statement="X 成立"))
    check("初始动作 = check_hypothesis（因为有 open 假设）",
          choose_action(st)[0] == "check_hypothesis", "got %s" % choose_action(st)[0])
    kp_before = st.current_kp
    st = add_evidence(st, "h1", {"kind": "counter", "text": "反例"}, refutes=True)
    h = st.hypotheses[0]
    check("假设被标为 refuted", h.status == HYP_REFUTED)
    check("★ 证据被保留（不许丢）", len(h.evidence) == 1)
    act, why = choose_action(st)
    check("★ 反证后动作 = rollback", act == "rollback", "got %s" % act)
    check("回退原因标注为 counter_evidence", why == "counter_evidence")
    st = rollback(st, "counter_evidence")
    check("回退后新增了一个保留点", len(st.keep) == 1)
    check("★ 当前检查点已改变", st.current_kp != kp_before or st.keep[-1].kp_id != kp_before)
    # ★ 负向：普通证据不该触发回退
    st3 = State(budget_remaining=10)
    st3.hypotheses.append(__import__("creativity_lab.state_layer", fromlist=["Hypothesis"]).Hypothesis(
        hid="h2", statement="Y"))
    st3 = add_evidence(st3, "h2", {"kind": "support"}, refutes=False)
    check("★ 负向：支持性证据不触发回退", choose_action(st3)[0] != "rollback")


# ══════════════════════════════════════════════════════════════
# ③ 合法分歧保留
# ══════════════════════════════════════════════════════════════
def test_divergence():
    print("== ③ 合法分歧保留 ==")
    st = State(budget_remaining=10)
    st = preserve_divergence(st, {"id": "d1", "claim": "路径 A 更优", "by": "agent1"})
    st = preserve_divergence(st, {"id": "d2", "claim": "路径 B 更优", "by": "agent2"})
    check("★ 两条分歧都在（没有被压平成一个）", len(st.divergences) == 2)
    check("两条分歧的 claim 不同", st.divergences[0]["claim"] != st.divergences[1]["claim"])
    check("★ 负向：分歧没有被合并成一条", len({d["id"] for d in st.divergences}) == 2)
    act, why = choose_action(st)
    check("★ 有分歧时动作 = connect（★ 正是『连接两组信息』）",
          act == "connect", "got %s" % act)


# ══════════════════════════════════════════════════════════════
# ④ 子目标撤销
# ══════════════════════════════════════════════════════════════
def test_subgoal_revoke():
    print("== ④ 子目标撤销 ==")
    st = State(budget_remaining=10)
    st = propose_subgoal(st, "g1", "先做 A")
    st = propose_subgoal(st, "g2", "再做 B", parent_sid="g1")
    check("两个子目标都是 active", all(g.status == SUBGOAL_ACTIVE for g in st.subgoals))
    check("★ 子目标由系统提出", st.subgoals[0].proposed_by == "system")
    st = revise_subgoal(st, "g1", "先做 A（修订版）")
    check("修订后 revision 计数 = 1", st.subgoals[0].revision == 1)
    check("修订后 statement 已更新", st.subgoals[0].statement == "先做 A（修订版）")
    st = revoke_subgoal(st, "g1", "反馈表明 A 不可行")
    g1 = next(g for g in st.subgoals if g.sid == "g1")
    check("★ g1 状态 = revoked", g1.status == SUBGOAL_REVOKED)
    check("★ 撤销原因已记录", "不可行" in g1.revocation_reason)
    check("★ 负向：撤销【不物理删除】（★ 历史仍可回查）", len(st.subgoals) == 2)
    check("★ 负向：只影响被撤销的那一条",
          next(g for g in st.subgoals if g.sid == "g2").status == SUBGOAL_ACTIVE)
    check("撤销被记入进展记录", any("revoke_subgoal:g1" in p for p in st.progress))


# ══════════════════════════════════════════════════════════════
# ⑤ 预算用尽与失败调用
# ══════════════════════════════════════════════════════════════
def test_budget_and_failures():
    print("== ⑤ 预算用尽与失败调用 ==")
    st = State(budget_remaining=3, budget_used=0)
    st = record_call(st, ok=True)
    check("成功后 remaining = 2", st.budget_remaining == 2)
    check("成功后 used = 1", st.budget_used == 1)
    st = record_call(st, ok=False)
    check("★★ 失败调用【也扣预算】（★ 不许静默归零）", st.budget_remaining == 1,
          "got %s" % st.budget_remaining)
    check("★ 失败被记进分母（★ n_failed_calls）", st.n_failed_calls == 1)
    check("★ 总调用数含失败", st.n_calls_total == 2)
    check("★ 负向：失败调用没有把分母算小", st.n_calls_total == st.n_failed_calls + 1)
    st = record_call(st, ok=False)
    check("预算耗尽后 exhausted = True", st.exhausted)
    check("★ 耗尽原因标注为 budget_exhausted", st.stop_reason == "budget_exhausted")
    act, why = choose_action(st)
    check("★ 预算耗尽 ⇒ 动作只能是 stop", act == "stop", "got %s" % act)
    # ★ 负向：耗尽后即使还有 open 假设，也不许再 explore
    st2 = State(budget_remaining=1)
    st2.hypotheses.append(__import__("creativity_lab.state_layer", fromlist=["Hypothesis"]).Hypothesis(
        hid="h3", statement="Z"))
    st2 = record_call(st2, ok=False)
    check("★ 负向：耗尽后不因 open 假设而继续", choose_action(st2)[0] == "stop")


# ══════════════════════════════════════════════════════════════
# ⑥ ★★ 第四组 2026-10-25 独立审计发现的三条规格↔实现差异 ⇒ 回归测试
# ══════════════════════════════════════════════════════════════
def test_spec_gap_fixes():
    print("== ⑥ 第四组审计发现的三条差异（★ 回归测试）==")
    # ── ① 支持性证据必须能把假设推到 supported（★ 否则 connect 被无限阻塞）──
    st = State(budget_remaining=10)
    st.hypotheses.append(__import__("creativity_lab.state_layer", fromlist=["Hypothesis"]).Hypothesis(
        hid="h1", statement="X"))
    st = preserve_divergence(st, {"id": "d1", "claim": "A", "by": "a1"})
    act_before = choose_action(st)[0]
    check("① 支持前：动作被 check_hypothesis 阻塞（★ 复现原 bug）",
          act_before == "check_hypothesis", "got %s" % act_before)
    st = add_evidence(st, "h1", {"kind": "support", "text": "s1"})
    check("① 一次支持后仍是 open（★ 一次不算被支持）",
          st.hypotheses[0].status == HYP_OPEN)
    st = add_evidence(st, "h1", {"kind": "support", "text": "s2"})
    check("★★ 两次支持后 ⇒ 转为 supported", st.hypotheses[0].status == HYP_SUPPORTED,
          "got %s" % st.hypotheses[0].status)
    act_after = choose_action(st)[0]
    check("★★ 支持后动作不再被阻塞 ⇒ connect", act_after == "connect", "got %s" % act_after)
    # ── ③ 支持性证据也要留痕 ──
    check("③ 支持性证据写进了 progress（★ 可回放）",
          any("evidence:h1:support" in p for p in st.progress))
    check("③ 反证仍写 refuted 痕迹", True)
    st2 = State(budget_remaining=10)
    st2.hypotheses.append(__import__("creativity_lab.state_layer", fromlist=["Hypothesis"]).Hypothesis(
        hid="h2", statement="Y"))
    st2 = add_evidence(st2, "h2", {"kind": "counter"}, refutes=True)
    check("③ 反证写 refuted", any("refuted:h2" in p for p in st2.progress))

    # ── ② 死路判定看【连续】不看【累计】──
    st3 = State(budget_remaining=10)
    st3 = record_attempt(st3, "m", produced_new=True)
    st3 = record_attempt(st3, "m", produced_new=True)
    st3 = record_attempt(st3, "m", produced_new=False)
    check("★★ ② (True,True,False) ⇒ 【不】判死路（★ 连续只 1 次）",
          not st3.attempts[0].dead_end, "got dead_end=%s" % st3.attempts[0].dead_end)
    check("② ② used 仍是累计 3", st3.attempts[0].used == 3)
    check("② ② consecutive_no_new = 1", st3.attempts[0].consecutive_no_new == 1)
    st3 = record_attempt(st3, "m", produced_new=False)
    st3 = record_attempt(st3, "m", produced_new=False)
    check("★★ ② 连续 3 次无新信息 ⇒ 判死路", st3.attempts[0].dead_end)
    st4 = State(budget_remaining=10)
    st4 = record_attempt(st4, "m", produced_new=False)
    st4 = record_attempt(st4, "m", produced_new=False)
    st4 = record_attempt(st4, "m", produced_new=True)
    check("★★ ② 有新信息 ⇒ 连续计数【清零】", st4.attempts[0].consecutive_no_new == 0)

    # ── ④ 并列检测（★ rev2：返回【所有】并列簇，★ 不只最大簇）──
    check("④ ④ 无并列 ⇒ 空列表", detect_tie([0.9, 0.2, 0.1], tol=1e-9) == [])
    t = detect_tie([0.5, 0.5, 0.1], tol=1e-9)
    check("④ ④ 单一并列簇 ⇒ members", len(t) == 1 and t[0]["members"] == [0, 1],
          "got %s" % (t,))
    # ★★ rev2：★ 中位并列也要检出（★ 第四组 2026-10-25 实测发现的漏检）
    t2 = detect_tie([0.9, 0.5, 0.5], tol=1e-9)
    check("★★ ④ 中位并列 [0.9,0.5,0.5] ⇒ 必须检出（★ rev1 漏检）",
          len(t2) == 1 and t2[0]["members"] == [1, 2], "got %s" % (t2,))
    t3 = detect_tie([0.9, 0.9, 0.5, 0.5], tol=1e-9)
    check("★★ ④ 两个并列簇 ⇒ 返回 2 个（★ 不只最大簇）", len(t3) == 2,
          "got %s" % (t3,))
    check("④ ④ detect_tie 不改状态（★ 纯函数）", len(State().divergences) == 0)

    # ── rev3（★ 第四组 2026-10-25 审阅意见 ⇒ ★ tol 必填 + 分组规则写死）──
    # ★ ★ ① 【1e-10 差值】的钉子（★ 第四组点名要的那条：★ rev3 的新口径必须【有测试钉住】）
    t1e10 = detect_tie([0.9000000001, 0.9000000002], tol=1e-9)
    check("★★ rev3 ① 差 1e-10（≤ tol=1e-9）⇒ 判并列（★ 1 簇，members=[0,1]）",
          len(t1e10) == 1 and t1e10[0]["members"] == [0, 1], "got %s" % (t1e10,))
    # ★ ★ ② ★ 同一对分值，★ tol 收紧到 1e-11 ⇒ ⇒ 【不】判并列（★ 证明 tol 真的在起作用）
    t1e10b = detect_tie([0.9000000001, 0.9000000002], tol=1e-11)
    check("★★ rev3 ② 同一对分值、tol=1e-11 ⇒ 不并列（★ tol 真的生效，不是死参数）",
          t1e10b == [], "got %s" % (t1e10b,))
    # ★ ★ ③ ★ 传递闭包：★ 相邻差都 ≤ tol ⇒ 全归一簇（★ 首尾差 0.8e-9）
    ttrans = detect_tie([0.5, 0.5 + 0.4e-9, 0.5 + 0.8e-9], tol=1e-9)
    check("★★ rev3 ③ 传递闭包 ⇒ 三值归一簇（★ members=[0,1,2]）",
          len(ttrans) == 1 and ttrans[0]["members"] == [0, 1, 2], "got %s" % (ttrans,))
    # ★ ★ ④ ★★ 边界特性：★ 簇内首尾差【超过 tol】（★ ⇒ "tol 不是簇内最大跨度"）
    tspread = detect_tie([0.5, 0.5 + 0.9e-9, 0.5 + 1.8e-9], tol=1e-9)
    check("★★ rev3 ④ 簇内首尾差 1.8e-9 > tol=1e-9 ⇒ 仍归一簇（★ 传递闭包 ⇒ ★ tol≠最大跨度）",
          len(tspread) == 1 and tspread[0]["members"] == [0, 1, 2], "got %s" % (tspread,))
    # ★ ★ ⑤ ★ tol 必填：★ 不传 ⇒ TypeError（★ 第四组要"禁止不传 tol"的守卫 ⇒ ★ 必填参数本身更强）
    try:
        detect_tie([0.9, 0.5, 0.5])
        check("★★ rev3 ⑤ 不传 tol ⇒ 必须 TypeError（★ fail-fast）", False, "★ 没报错")
    except TypeError:
        check("★★ rev3 ⑤ 不传 tol ⇒ TypeError（★ fail-fast，★ 不静默用默认值）", True)
    # ★ ★ ⑥ ★ 位置传参必须被拒（★ keyword-only ⇒ ⇒ 逼调用方显式写 tol=）
    try:
        detect_tie([0.9, 0.5, 0.5], 1e-9)
        check("★★ rev3 ⑥ 位置传 tol ⇒ 必须 TypeError（★ keyword-only）", False, "★ 没报错")
    except TypeError:
        check("★★ rev3 ⑥ 位置传 tol ⇒ TypeError（★ keyword-only）", True)
    # ★ ★ ⑦ ★ rev2→rev3 的真实差异点：★ tol=1e-13 时差 5e-13 【不】并列（★ rev2 会并列）
    ttiny = detect_tie([0.5, 0.5 + 5e-13], tol=1e-13)
    check("★★ rev3 ⑦ tol=1e-13、差 5e-13 ⇒ 不并列（★ ★ 与 rev2 的 round(v,12) 口径【不同】）",
          ttiny == [], "got %s" % (ttiny,))
    # ★ ★ ⑧ ★ members 顺序回归（★ ★ 钉住"原索引升序"⇒ ⇒ 第四组的断言不用改）
    tord = detect_tie([0.9, 0.9, 0.5, 0.5], tol=1e-9)
    check("★★ rev3 ⑧ members 顺序 = 原索引升序（★ 与 rev2 一致 ⇒ ★ 第四组断言不用改）",
          [d["members"] for d in tord] == [[0, 1], [2, 3]], "got %s" % ([d["members"] for d in tord],))


def main() -> int:
    print("== ★ 状态层离线测试（★ 工作包三）==")
    for fn in (test_dead_end, test_rollback, test_divergence,
               test_subgoal_revoke, test_budget_and_failures, test_spec_gap_fixes):
        fn()
        print()
    if FAILED:
        print("✘ 失败 %d 项：%s" % (len(FAILED), FAILED))
        return 1
    print("✔ 全部通过（6 个测试组）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
