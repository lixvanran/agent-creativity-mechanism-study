#!/usr/bin/env python3
"""★ **第二组 `state_layer.py` 规格-实现差异探针（★ 零 API · ★ 只读不改 · ★ 双版本差分）**

★ **为什么是双版本**：★ rev1 修掉了 rev0 的 4 条差异 ⇒ ⇒ **旧探针会继续报"已修复的 bug"**
★ ⇒ ⇒ ★ 那就是【过期工具】⇒ ⇒ ★ **探针必须跟着接口版本走**，★ 否则它比没有更坏（★ 让人以为还有 bug）。
★ ⇒ ⇒ ★ 本探针**同时加载 rev0 与 rev1**，★ 对每条差异给出【两版各自的判定】⇒ ⇒
★ ★ **「已修复」与「仍存在」必须一眼分开**。

★ **三条纪律**：
★ ① **只读**：★ 不写任何一版 `state_layer.py`（★ 接口归属第二组）。
★ ② **差异不是缺陷判决**：★ 差异 = 「规格与实现的口径分歧」⇒ ⇒ **由第二组裁决**，★ 第四组不单方面改。
★ ③ **每条差异都有可复现的执行轨迹**（★ 命令 + 输出），★ 不是文字描述。

★ **用法**：
```bash
# ★ 默认：探 rev1（现行）
python3 group4_state_driven/probe_state_layer_spec_gap.py
# ★ 对照：同时探 rev0
python3 group4_state_driven/probe_state_layer_spec_gap.py --both
```
"""
from __future__ import annotations

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

REV0_PATH = "/tmp/state_layer_rev0.py"          # ★ rev0（sha 38795bf6adfdee05）
REV1_PATH = os.path.join(_ROOT, "creativity_lab", "state_layer.py")   # ★ rev1（sha 69a29c506a4e4ab0）


def _load(path: str, name: str):
    """★ 按路径加载指定版本（★ 不走包 import ⇒ rev0 不污染 `creativity_lab.state_layer`）"""
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # ★ 必须先注册进 sys.modules ⇒ dataclass 解析字符串注解时要查 sys.modules[cls.__module__].__dict__
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════════════
# 五条差异的探针（★ 每条返回 (是否成立, 轨迹)）
# ══════════════════════════════════════════════════════════════

def gap1_supported_unreachable(SL):
    """★ **差异 1：`HYP_SUPPORTED` 可达吗？"""
    st = SL.State(budget_remaining=9, hypotheses=[SL.Hypothesis(hid="h2", statement="命题")])
    for i in range(10):
        st = SL.add_evidence(st, "h2", {"kind": "support", "i": i}, refutes=False)
    st = SL.preserve_divergence(st, {"id": "d1", "claim": "分歧"})
    act, arg = SL.choose_action(st)
    status = st.hypotheses[0].status
    # ★ 差异成立 ⇔ 两次支持后仍 open（⇒ supported 不可达 ⇒ connect 被阻塞）
    holds = (status == SL.HYP_OPEN)
    return holds, ("status=%r；choose_action=(%r,%r)" % (status, act, arg))


def gap2_deadend_cumulative(SL):
    """★ **差异 2：死路判定是累计还是连续？"""
    st = SL.State(budget_remaining=9)
    for ok in (True, True, False):
        st = SL.record_attempt(st, "m", produced_new=ok)
    a = next(x for x in st.attempts if x.method == "m")
    # ★ 差异成立 ⇔ (True,True,False) 被判死路（⇒ 累计语义）
    holds = bool(a.dead_end)
    return holds, ("(True,True,False) ⇒ dead_end=%r；used=%r" % (a.dead_end, a.used))


def gap3_support_no_trace(SL):
    """★ **差异 3：支持性证据进 progress 吗？"""
    st = SL.State(budget_remaining=9, hypotheses=[SL.Hypothesis(hid="h", statement="命题")])
    st = SL.add_evidence(st, "h", {"kind": "support", "text": "S"}, refutes=False)
    has = any(p.startswith("evidence:h:support:") for p in st.progress)
    # ★ 差异成立 ⇔ 不留痕
    holds = not has
    return holds, ("progress=%r" % (st.progress,))


def gap4_no_tie_mechanism(SL):
    """★ **差异 4：有并列自动保留分歧的机制吗？"""
    has_fn = hasattr(SL, "detect_tie")
    if has_fn:
        st = SL.State(budget_remaining=9)
        d = SL.detect_tie([0.9, 0.9, 0.2])
        return (d is None), ("detect_tie 存在；并列检出=%r" % (d,))
    st = SL.State(budget_remaining=9)
    return True, ("无 detect_tie；divergences=%r" % (st.divergences,))


def gap5_tie_only_at_max(SL):
    """★ **差异 5（★ rev1 新增）：`detect_tie` 只查【最大值处】的并列 ⇒ 中位并列漏检**

    ★ ★ 第四组在实现 rev1 接线时发现的：★ 「合法分歧」未必只发生在最高分
    ★ ⇒ ⇒ 若候选 [0.9, 0.5, 0.5] 的两个 0.5 是真实分歧（★ 来自不同来源的第二好方案），
    ★ ⇒ ⇒ 则 `detect_tie` 会漏掉它 ⇒ ⇒ 分歧语义又丢了。
    """
    if not hasattr(SL, "detect_tie"):
        return False, "（rev0 无 detect_tie ⇒ 本条不适用）"
    mid = SL.detect_tie([0.9, 0.5, 0.5])
    top = SL.detect_tie([0.9, 0.9, 0.2])
    # ★ 差异成立 ⇔ 最高分并列能检出，但中位并列检不出
    holds = (top is not None) and (mid is None)
    return holds, ("最高分并列检出=%r；中位并列检出=%r" % (top is not None, mid is not None))


GAPS = [
    ("① HYP_SUPPORTED 不可达 ⇒ connect 被无限阻塞",
     "T2 负向①「支持性证据不触发回退」",
     "refutes=False ⇒ status 保持 open ⇒ 假设永不变 supported",
     "已支持假设仍触发 check_hypothesis ⇒ connect 分支被阻塞",
     gap1_supported_unreachable),
    ("② 死路判定为「累计」而非规格所写「连续」",
     "T1「同一方法连续 3 次无新信息 ⇒ dead_end=True」",
     "not produced_new and at.used >= 3 ⇒ 非连续序列也会判死路",
     "成功过的方法可能被判死路 ⇒ switch_method 触发更早",
     gap2_deadend_cumulative),
    ("③ 支持性证据不写 progress ⇒ 回放无法区分支持与反证",
     "★ 规格表未涉及（★ 属「可回放」红线②的延伸关切）",
     "add_evidence 只在 refutes=True 时 append progress",
     "回放时支持证据只能靠 h.evidence 内容判断 ⇒ 与反证不同构",
     gap3_support_no_trace),
    ("④ 「并列 ⇒ 自动保留分歧」无机制",
     "T3 输入「两个候选评分并列（0.5,0.5）且来自不同来源」",
     "无并列检测；分歧必须由调用方显式写入",
     "★ 第四组 v6 的 Select(greedy) 会吃掉并列 ⇒ 接线时必须显式补",
     gap4_no_tie_mechanism),
    ("⑤ ★ detect_tie 只查【最大值处】⇒ 中位并列漏检（★ rev1 新增）",
     "★ 规格表未涉及（★ 第四组接线时发现）",
     "best = max(scores) ⇒ 只在最高分处找并列",
     "★ 第二名并列（来自不同来源的真实分歧）会被漏掉 ⇒ 分歧语义又丢",
     gap5_tie_only_at_max),
]


def probe(tag, mod):
    print("\n===== %s =====" % tag)
    out = []
    for name, spec_row, impl, conseq, fn in GAPS:
        try:
            holds, trace = fn(mod)
        except Exception as e:
            holds, trace = None, "★ 探针异常：%s: %s" % (type(e).__name__, e)
        verdict = "★ 差异成立" if holds else ("✔ 已修复" if holds is False else "★ 探针异常")
        print("  [%s] %s" % (verdict, name))
        print("        · 轨迹：%s" % (trace,))
        out.append((name, holds, spec_row, impl, conseq))
    return out


def main():
    argv = sys.argv[1:]
    rev1 = _load(REV1_PATH, "sl_rev1")
    if rev1 is None:
        print("✘ 找不到 rev1：%s" % REV1_PATH)
        return 2

    r1 = probe("★ rev1（现行 · sha 69a29c506a4e4ab0）", rev1)

    r0 = None
    if "--both" in argv:
        rev0 = _load(REV0_PATH, "sl_rev0")
        if rev0 is not None:
            r0 = probe("★ rev0（对照 · sha 38795bf6adfdee05）", rev0)

    print("\n" + "-" * 78)
    print("★ 差异汇总（以 rev1 为准）")
    still = [x for x in r1 if x[1] is True]
    fixed = [x for x in r1 if x[1] is False]
    errs = [x for x in r1 if x[1] is None]
    for i, (name, holds, spec_row, impl, conseq) in enumerate(r1, 1):
        print("  %d) %s" % (i, name))
        print("     · 判定：%s" % ("★ 仍存在 ⇒ 待第二组裁决" if holds is True
                                   else ("✔ 已修复" if holds is False else "★ 探针异常")))
        print("     · 规格依据：%s" % spec_row)
        print("     · 实现行为：%s" % impl)
        print("     · 后果    ：%s" % conseq)
    print("-" * 78)
    print("★ 仍存在 %d 条 / 已修复 %d 条 / 异常 %d 条" % (len(still), len(fixed), len(errs)))
    if r0 is not None:
        n0 = sum(1 for x in r0 if x[1] is True)
        print("★ rev0 对照：仍存在 %d 条 ⇒ ★ 与 rev1 差 %d 条（★ 修订覆盖了这些）"
              % (n0, n0 - len(still)))
    print("★ ★ 本探针【不改任何一版 state_layer.py】⇒ ⇒ 差异上报第二组裁决 ⇒ 第四组不单方面改规则。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
