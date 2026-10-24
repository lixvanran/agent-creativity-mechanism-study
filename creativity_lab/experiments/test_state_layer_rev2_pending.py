#!/usr/bin/env python3
"""★ **rev2 待落地断言（★ 第二组 2026-10-25 裁决第 5 条差异后 · ★ 第四组按语义实现）**

> ★★★ **【状态：★ 等第二组给 rev2 的逐字原文 ⇒ ★ 在此之前本文件【预期失败】★★★**
>
> ★ **为什么单独放一个文件（★ 而不是并进主测试）**：
> ★ ⇒ ★ **主测试文件必须保持全绿**（★ 交付一个"测试红着"的包 = 交付一个坏东西）
> ★ ⇒ ★ 而 rev2 断言的**价值恰恰在于它现在红着**（★ **红 ⇒ 证明它抓得住 rev1 的缺陷**）
> ★ ⇒ ⇒ ★ ⇒ **两者分开：★ 主文件 = 当前接口的守门；★ 本文件 = 下一个接口的守门（★ 现在红 ⇒ 到位就绿）**

★ **rev2 的语义变更（★ 第二组裁决）**：
★ ★ `detect_tie` 从【只查最高分簇】改成【返回【所有】并列簇】
★ ★ 返回类型 `Dict` ⇒ `List[Dict]`；★ 空时返回 `[]`（★ 不是 `None`）

★ **★ 接线侧的改法（★ 返回类型变了）**：
```python
# ★ 旧（rev1）
d = SL.detect_tie(scores)
if d is not None:
    st = SL.preserve_divergence(st, d)

# ★ 新（rev2）
for d in SL.detect_tie(scores):
    st = SL.preserve_divergence(st, d)
```

★ **运行**：`python3 -B creativity_lab/experiments/test_state_layer_rev2_pending.py`
★ **预期**：★ **rev1 下 exit 1 且报「中位并列漏检」**（★ 这就是它的作用）；★ rev2 落地后 exit 0。

★ ★ **★ 第四组按语义重写 rev2 后 sha256 不符（★ `946f82a9…` ≠ 期望 `b70bfb0b…`）**
★ ⇒ ⇒ ★ ⇒ **已回滚到 rev1**（★ sha `69a29c506a4e4ab0…`）
★ ⇒ ⇒ ★ ⇒ ★ **★ 教训：★ 「按语义重写」不能替代「逐字节原文」⇒ ⇒ ★ sha256 双向校验是唯一可靠手段**
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from creativity_lab import state_layer as SL  # noqa: E402


def test_rev2_returns_all_clusters(SL):
    """★ **rev2：★ 返回【所有】并列簇（★ 不只最大簇）**"""
    # ── 最高分并列 ──
    r = SL.detect_tie([0.9, 0.9, 0.2])
    assert r is not None and len(r) >= 1, "★ 最高分并列应检出，实际 %r" % (r,)
    clusters = r if isinstance(r, list) else [r]
    first = clusters[0]
    assert first.get("kind") == "tie", "kind 应为 tie，实际 %r" % (first.get("kind"),)
    assert sorted(first.get("members") or []) == [0, 1], \
        "members 应为 [0,1]，实际 %r" % (first.get("members"),)

    # ── ★★ 中位并列（★ rev1 会漏，★ rev2 必须检出）★★
    mid = SL.detect_tie([0.9, 0.5, 0.5])
    assert mid is not None and len(mid) >= 1, \
        "★★ rev2：第二名并列（0.5,0.5）也是合法分歧 ⇒ 必须检出，实际 %r" % (mid,)
    mid_clusters = mid if isinstance(mid, list) else [mid]
    members = set()
    for c in mid_clusters:
        members.update(c.get("members") or [])
    assert {1, 2} <= members, \
        "★★ rev2：中位并列成员 {1,2} 应被检出，实际 %r" % (members,)

    # ── 无并列 ⇒ 空列表（★ 不是 None）──
    empty = SL.detect_tie([0.1, 0.5, 0.9])
    assert not empty, "★ rev2：无并列应返回空列表，实际 %r" % (empty,)

    # ── ★ 纯函数：不改状态 ──
    st = SL.State(budget_remaining=5)
    before = json.dumps(st.to_dict(), ensure_ascii=False, sort_keys=True)
    SL.detect_tie([0.9, 0.5, 0.5])
    after = json.dumps(st.to_dict(), ensure_ascii=False, sort_keys=True)
    assert before == after, "★ detect_tie 是纯函数 ⇒ 不得修改状态"


def main():
    print("=" * 74)
    print("★ rev2 待落地断言（★ 第二组裁决第 5 条差异）")
    print("★ 接口 sha256 = %s" % __import__("hashlib").sha256(
        open(os.path.join(_ROOT, "creativity_lab", "state_layer.py"), "rb").read()).hexdigest()[:16])
    print("=" * 74)
    try:
        test_rev2_returns_all_clusters(SL)
    except AssertionError as e:
        print("  ✘ rev2 断言失败（★ ★ 这是【预期】的 —— ★ rev1 还没实现 rev2 语义）")
        print("     %s" % e)
        print("=" * 74)
        print("★ ★ rev2 落地后本文件应 exit 0 ⇒ ★ 到时把本文件的断言并入主测试文件")
        return 1
    except Exception as e:
        print("  ✘ %s: %s" % (type(e).__name__, e))
        return 1
    print("  ✔ rev2 断言全部通过 ⇒ ★ rev2 已落地 ⇒ ★ 可把本文件并入主测试")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
