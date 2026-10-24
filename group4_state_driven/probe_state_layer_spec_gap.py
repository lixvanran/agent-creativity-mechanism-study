#!/usr/bin/env python3
"""★ **第二组 `state_layer.py` 的规格-实现差异探针（★ 零 API，★ 只读不改）**

★ **为什么有这个文件**：★ 第二组直发的 `creativity_lab/state_layer.py` 是逐字节原文
（sha256 = `38795bf6adfdee05…`，★ 已核）。★ 但**逐字节一致 ≠ 语义无歧义** ⇒ ⇒
★ 本探针用【机械执行】把「规格表写的语义」与「代码实际做的语义」逐条对照 ⇒ ⇒
★ **差异必须显式上报**，★ 不许靠肉眼放过去，也**不许私自改第二组的文件**。

★ **三条纪律**：
★ ① **只读**：★ 本探针不写 `state_layer.py`，★ 一行都不改（★ 接口归属第二组）。
★ ② **差异不是缺陷判决**：★ 差异 = 「规格与实现的口径分歧」⇒ ⇒ **由第二组裁决**，★ 不由第四组单方面改。
★ ③ **每条差异都有可复现的执行轨迹**（★ 命令 + 输出），★ 不是文字描述。

用法：python3 group4_state_driven/probe_state_layer_spec_gap.py
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from creativity_lab import state_layer as SL  # noqa: E402

OUT = []


def emit(tag, msg):
    line = "[%s] %s" % (tag, msg)
    OUT.append(line)
    print(line)


def gap1_supported_unreachable():
    """★ **差异 1：`HYP_SUPPORTED` 是不可达常量**"""
    emit("GAP1", "★ 差异 1：`HYP_SUPPORTED` 定义了，但代码里没有任何路径能到达它")
    # ── 机械证据 1a：全仓 grep 赋值点 ──
    src_path = os.path.join(_ROOT, "creativity_lab", "state_layer.py")
    with open(src_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    assign_lines = [(i + 1, ln.strip()) for i, ln in enumerate(lines)
                    if "HYP_SUPPORTED" in ln and not ln.strip().startswith("#")]
    define_lines = [(i + 1, ln.strip()) for i, ln in enumerate(lines)
                    if ln.strip().startswith("HYP_SUPPORTED")]
    emit("GAP1", "  · 含 HYP_SUPPORTED 的行：定义 %r / 其他 %r"
         % (define_lines, assign_lines))
    # ── 机械证据 1b：跑遍所有公开更新函数，看 status 能不能变成 supported ──
    reached = False
    st = SL.State(budget_remaining=9, hypotheses=[SL.Hypothesis(hid="h1", statement="命题")])
    st = SL.add_evidence(st, "h1", {"kind": "support"}, refutes=False)
    if st.hypotheses[0].status == SL.HYP_SUPPORTED:
        reached = True
    emit("GAP1", "  · 执行轨迹：add_evidence(refutes=False) 后 status = %r"
         % (st.hypotheses[0].status,))
    emit("GAP1", "  ⇒ HYP_SUPPORTED 可达？%s" % (reached,))

    # ── 机械证据 1c：更严重的后果 —— open 假设永不变 supported ⇒ choose_action 永久卡在 check_hypothesis ──
    st2 = SL.State(budget_remaining=9,
                   hypotheses=[SL.Hypothesis(hid="h2", statement="命题")])
    for i in range(10):
        st2 = SL.add_evidence(st2, "h2", {"kind": "support", "i": i}, refutes=False)
    st2 = SL.preserve_divergence(st2, {"id": "d1", "claim": "分歧"})
    act, arg = SL.choose_action(st2)
    emit("GAP1", "  · 执行轨迹：连续 10 次支持性证据 + 1 条分歧 ⇒ choose_action = (%r, %r)"
         % (act, arg))
    emit("GAP1", "  ⇒ ★ 后果：支持性证据【不改变状态】⇒ 假设永远 open ⇒")
    emit("GAP1", "  ⇒   `check_hypothesis` 分支永久优先于 `connect` ⇒ ⇒ 分歧连接被无限期阻塞")
    return {
        "gap": "HYP_SUPPORTED 不可达 + 支持性证据不改变状态",
        "spec_table_row": "T2 负向①「支持性证据不触发回退」（★ 规格未规定支持后进入 supported）",
        "impl_behavior": "refutes=False ⇒ status 保持 open，HYP_SUPPORTED 永不出现",
        "consequence": "已支持假设仍触发 check_hypothesis ⇒ connect 分支被阻塞",
        "evidence": "add_evidence(refutes=False) ×10 后 status=%r；choose_action=(%r,%r)"
                    % (st2.hypotheses[0].status, act, arg),
        "decision_owner": "第二组",
    }


def gap2_deadend_cumulative_not_consecutive():
    """★ **差异 2：死路判定是「累计」而非「连续」**"""
    emit("GAP2", "★ 差异 2：死路判定的注释写「连续 3 次」，代码写的是 `at.used >= 3`")
    # ── 机械证据 2a：规格语义（连续 3 次都无新信息）──
    st = SL.State(budget_remaining=9)
    for _ in range(3):
        st = SL.record_attempt(st, "m", produced_new=False)
    a = next(x for x in st.attempts if x.method == "m")
    emit("GAP2", "  · 规格语义轨迹（False,False,False）⇒ dead_end=%r  ⇒ ★ 与规格一致"
         % (a.dead_end,))

    # ── 机械证据 2b：非连续序列也被判死路 ⇒ 实现是「累计」──
    st2 = SL.State(budget_remaining=9)
    for ok in (True, True, False):        # 只有最后一次无新信息
        st2 = SL.record_attempt(st2, "m2", produced_new=ok)
    a2 = next(x for x in st2.attempts if x.method == "m2")
    emit("GAP2", "  · 实现语义轨迹（True,True,False）⇒ dead_end=%r  ⇒ ★ 【与「连续」规格不符】"
         % (a2.dead_end,))
    emit("GAP2", "  · 同一方法第 3 次尝试中，只有 1 次无新信息 ⇒ 仍被判死路")

    # ── 机械证据 2c：影响面 —— 一次成功也能把方法推下阈值 ──
    st3 = SL.State(budget_remaining=9)
    st3 = SL.record_attempt(st3, "m3", produced_new=True)   # 有新信息
    st3 = SL.record_attempt(st3, "m3", produced_new=True)   # 有新信息
    st3 = SL.record_attempt(st3, "m3", produced_new=False)  # 无新信息
    a3 = next(x for x in st3.attempts if x.method == "m3")
    act, arg = SL.choose_action(st3)
    emit("GAP2", "  · 执行轨迹：m3 = (True,True,False) ⇒ dead_end=%r ⇒ choose_action=(%r,%r)"
         % (a3.dead_end, act, arg))
    emit("GAP2", "  ⇒ ★ 影响：成功过的方法会被判死路 ⇒ ⇒ 触发 switch_method ⇒ ⇒ 【比规格更激进】")

    # ── 机械证据 2d：produced_new 每次覆盖而非累积 ──
    st4 = SL.State(budget_remaining=9)
    st4 = SL.record_attempt(st4, "m4", produced_new=True)
    st4 = SL.record_attempt(st4, "m4", produced_new=False)
    a4 = next(x for x in st4.attempts if x.method == "m4")
    emit("GAP2", "  · `at.produced_new` 是【每次覆盖】而非累积：m4=(True,False) 后 produced_new=%r"
         % (a4.produced_new,))
    return {
        "gap": "死路判定为「累计 used>=3 且本次无新信息」，非规格所写「连续 3 次无新信息」",
        "spec_table_row": "T1「同一方法连续 3 次无新信息 ⇒ dead_end=True」",
        "impl_behavior": "not produced_new and at.used >= 3 ⇒ 非连续序列也会判死路",
        "consequence": "成功过的方法可能被判死路 ⇒ switch_method 触发更早 ⇒ 比规格更激进",
        "evidence": "(True,True,False) ⇒ dead_end=%r, choose_action=(%r,%r)"
                    % (a3.dead_end, act, arg),
        "decision_owner": "第二组",
    }


def gap3_support_evidence_no_progress_trace():
    """★ **差异 3：支持性证据在 progress 里无痕**"""
    emit("GAP3", "★ 差异 3：支持性证据不进 progress ⇒ 回放时无法区分支持与反证")
    st = SL.State(budget_remaining=9, hypotheses=[SL.Hypothesis(hid="h", statement="命题")])
    st = SL.add_evidence(st, "h", {"kind": "support", "text": "S"}, refutes=False)
    emit("GAP3", "  · 支持后 progress = %r  ⇒ ★ 无任何条目" % (st.progress,))
    emit("GAP3", "  · 但 evidence 列表 = %r  ⇒ ★ 证据本身在（★ 只有反证进 progress）"
         % (st.hypotheses[0].evidence,))
    st = SL.add_evidence(st, "h", {"kind": "counter", "text": "C"}, refutes=True)
    emit("GAP3", "  · 反证后 progress = %r" % (st.progress,))
    return {
        "gap": "支持性证据不写 progress ⇒ 状态回放无法区分「支持证据」与「反证证据」",
        "spec_table_row": "★ 规格表未涉及（★ 属第四组「可回放」红线 ② 的延伸关切）",
        "impl_behavior": "add_evidence 只在 refutes=True 时 append progress",
        "consequence": "回放/审计时，支持证据只能靠 h.evidence 的内容判断 ⇒ 与反证证据不同构",
        "evidence": "support 后 progress=%r；counter 后 progress=%r" % ([], st.progress),
        "decision_owner": "第二组（★ 若认为该留痕，★ 属规则变更 ⇒ 须重过预注册）",
    }


def gap4_no_tie_preservation_mechanism():
    """★ **差异 4：分歧保留是「显式调用」，没有「并列自动保留」机制**"""
    emit("GAP4", "★ 差异 4：分歧只靠 preserve_divergence 显式写入 ⇒ 无「并列自动保留」")
    emit("GAP4", "  · 规格表 T3 的输入写的是「两个候选评分并列且来自不同来源」")
    emit("GAP4", "  · 但代码里没有并列检测/自动保留的路径 ⇒ ⇒ 必须由调用方显式调用 preserve_divergence")
    st = SL.State(budget_remaining=9)
    emit("GAP4", "  · 空状态的 divergences = %r ⇒ 没有并列概念" % (st.divergences,))
    act, arg = SL.choose_action(st)
    emit("GAP4", "  · 空状态 choose_action = (%r, %r)" % (act, arg))
    return {
        "gap": "「并列 ⇒ 自动保留分歧」在代码里没有机制；只有显式 preserve_divergence",
        "spec_table_row": "T3 输入「两个候选评分并列（0.5,0.5）且来自不同来源」",
        "impl_behavior": "无并列检测；分歧必须由调用方显式写入",
        "consequence": "★ 第四组 v6 的 Select(greedy) 会吃掉并列 ⇒ 接线时必须显式补这一步，★ 否则分歧语义丢失",
        "evidence": "State().divergences=%r ⇒ 无自动来源" % (st.divergences,),
        "decision_owner": "第二组（接口层）+ 第四组（接线层，★ 归第四组实现与读数侧）",
    }


def main():
    print("=" * 78)
    print("★ 第二组 state_layer.py · 规格-实现差异探针（★ 零 API / ★ 只读不改）")
    print("=" * 78)
    gaps = [gap1_supported_unreachable(),
            gap2_deadend_cumulative_not_consecutive(),
            gap3_support_evidence_no_progress_trace(),
            gap4_no_tie_preservation_mechanism()]
    print("-" * 78)
    print("★ 差异汇总：%d 条" % len(gaps))
    for i, g in enumerate(gaps, 1):
        print("  %d) %s" % (i, g["gap"]))
        print("     · 规格依据：%s" % g["spec_table_row"])
        print("     · 实现行为：%s" % g["impl_behavior"])
        print("     · 后果    ：%s" % g["consequence"])
        print("     · 裁决方  ：%s" % g["decision_owner"])
    print("-" * 78)
    print("★ ★ 本探针【不改第二组文件】⇒ ⇒ 差异上报第二组裁决 ⇒ 第四组不单方面改规则。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
