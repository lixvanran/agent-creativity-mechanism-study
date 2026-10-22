# -*- coding: utf-8 -*-
"""锚外判定 + 等预算对照臂。

> 2026-10-22 ｜ 配套 `workflow.py` / `batch-U1/measure.py`

## 为什么需要「锚外判定」

普通判官**拿着 `C_t` 打分** ⇒ 它只能标"支撑 `C_t` 第几条"
⇒ ⇒ **锚外维度在普通判据下永远不可见** ⇒ `VD_anchor_out` 恒为 0
⇒ ⇒ **那是判据设计的必然，不是"我们没发现"。**

⇒ 所以必须换一个**不知道 `C_t`** 的判官（`measure_anchor_out`）：
只给依据，让它自己说「这句话改变了哪个决策」⇒ 然后**由我们**去比这个岔口在不在 `C_t` 里。

★ 这是 Curiosity Search 的 leave-one-out 精神：**判定靠"拿掉它结论是否改变"，
  不靠任何事前白名单。**

## 怎么机械地判「这个岔口在不在 C_t 里」

★ **离散、零 embedding**（与全项目的度量纪律一致）：
把 `C_t` 每条结论与判官给的 `decision_changed` 都压成**「决策指纹」**：
① 选项标记（①②③④ / (1)(2)）② 数值集合 ③ 2-gram 内容词集合
⇒ 指纹有交集 ⇒ **锚内**（已被 `C_t` 覆盖）⇒ 无交集 ⇒ **锚外**。

## 等预算对照臂 `B0_bestofN`

★ 我们的 B0 直调只花 **1 次生成调用**，而 W 花 **6 次**（3 槽位 × 生成+抽取）
⇒ ⇒ **任何"增益"都可能只是"多花了钱"** ⇒ ToT 的同预算 best-of-k 对照是必答项。

⇒ `B0_bestofN`：**N 次独立直调**（temp 0.7，可并行）+ 机械去冗余
⇒ **调用数与 W 完全相同** ⇒ 差集恰好是 {认知帧解耦 + 机械汇总 + 动作演化}
⇒ ⇒ **一臂同时解决「等预算」与「ToT 同预算 best-of-k」两个必问项**。
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Sequence, Tuple

import workflow as W

_OPT_MARK = W._OPT_MARK
_NUM_UNIT = W._NUM_UNIT
_CN_CONTENT = W._CN_CONTENT


def decision_fingerprint(text: str) -> Tuple[frozenset, frozenset, frozenset]:
    """把一段"决策描述"压成指纹：(选项标记, 数值集合, 内容词集合)。"""
    if not text:
        return frozenset(), frozenset(), frozenset()
    opts = frozenset(m.group(0) for m in _OPT_MARK.finditer(text))
    nums = frozenset(m.group(0).strip() for m in _NUM_UNIT.finditer(text))
    words = frozenset(_CN_CONTENT.findall(text))
    return opts, nums, words


def _fingerprint_match(a, b) -> bool:
    """两个指纹是否**指向同一个决策**。"""
    a_opts, a_nums, a_words = a
    b_opts, b_nums, b_words = b
    if a_opts and b_opts and (a_opts & b_opts):
        return True
    if a_nums and b_nums and (a_nums & b_nums):
        return True
    if a_words and b_words and len(a_words & b_words) >= 2:
        return True
    return False


def decide_anchor_out(cards: Sequence[Dict[str, Any]],
                       ct: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """判定哪些承重陈述是**锚外**的（其决策岔口不在 `C_t` 里）。

    ★ 判据：承重 ∧ 被依据支持 ∧ 写得出岔口 ∧ **岔口不匹配任何 `C_t` 结论**
    ⇒ **锚外**（= 事前没人写进 C_t 的问题维度）
    ⇒ ⚠️ **锚外 ≠ 一定对**：锚外陈述仍需被依据支持（`verdict=支持`），
      否则只是"依据没覆盖的猜测"。
    """
    ct_fps = [decision_fingerprint(c.get("text") or "") for c in (ct or [])]
    anchored, anchor_out, unknown = [], [], []
    for c in (cards or []):
        if not c.get("load_bearing"):
            continue
        if c.get("verdict") not in ("支持", "supported"):
            continue
        dc = (c.get("decision_changed") or "").strip()
        if not dc or dc.lower() == "null":
            unknown.append(c.get("claim"))
            continue
        fp = decision_fingerprint(dc)
        if any(_fingerprint_match(fp, t) for t in ct_fps):
            anchored.append(c.get("claim"))
        else:
            anchor_out.append(c.get("claim"))
    return dict(
        n_anchor_out=len(anchor_out),
        n_anchored=len(anchored),
        n_unknown=len(unknown),
        anchor_out_claims=anchor_out,
        anchored_claims=anchored,
    )


# ══════════════════════════════════════════════════════════════════════
# 等预算对照臂：N 次独立直调 + 机械去冗余
# ══════════════════════════════════════════════════════════════════════
def best_of_n_direct(llm, task: Dict[str, Any], model: str, n: int = 3,
                      *, seed: int = 0, temp: float = 0.7) -> Dict[str, Any]:
    """**N 次独立直调**（可并行）+ 机械去冗余 ⇒ **调用数与 W 相同**。

    ★ 这是 ToT "同预算 best-of-k" 在我们设定里的对应物：
      ToT 的轴是"节点数"，我们的轴是**调用数**（更接近成本）。
    """
    ask = task.get("ask") or ""
    prompt = "问题：%s\n\n%s" % (ask, W._OUT_SPEC)

    def _one(i):
        out, _i2 = W._chat(llm, prompt, purpose="B0_multi_%d" % i,
                            model=model, temp=temp, max_tokens=0, min_ok=20)
        cl = W._extract_claims(llm, out, model=model) if out else []
        return out, cl

    if n > 1:
        with ThreadPoolExecutor(max_workers=min(n, 4)) as ex:
            rs = list(ex.map(_one, range(n)))
    else:
        rs = [_one(0)]
    drafts = [r[0] for r in rs]
    all_claims = [c for _o, cl in rs for c in cl]
    kept = W.dedup(all_claims)                 # ★ 机械去冗余（与 W 同一口径）
    answer = "\n".join("- " + c for c in kept)
    return dict(answer=answer, claims=kept, drafts=drafts,
                ops=["BESTOF%d[direct]" % n], frames=[], archive={},
                failures={}, illum={}, rounds=[all_claims])
