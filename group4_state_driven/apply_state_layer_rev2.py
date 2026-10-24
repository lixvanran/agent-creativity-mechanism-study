#!/usr/bin/env python3
"""★ **第二组 `state_layer.py` rev2 应用脚本（★ 第四组 · ★ 逐字原文 + sha 双向校验）**

★ **rev2 的内容**：★ 第 5 条差异的修订 ⇒ ★ `detect_tie` 从【只查最高分簇】改成【返回所有并列簇】，
★ ★ 返回类型 `Dict` ⇒ `List[Dict]`（★ 空时返回 `[]`）。

★ **★ 本版与 rev1 脚本的关键差别**：★ **★ 不再"按语义重写"** ⇒ ⇒ ★ **直接用第二组给的逐字原文**
★ ⇒ ⇒ ★ **★ 因为上一次按语义重写后 sha 不符（★ `946f82a9…` ≠ `b70bfb0b…`）**
★ ⇒ ⇒ ★ ★ **教训：★ docstring 措辞 / 分组实现 / 簇排序都是自由度 ⇒ ⇒ ★ 「按语义重写」不能替代「逐字节原文」**
★ ⇒ ⇒ ★ ⇒ **★ 唯一可靠手段 = sha256 双向校验**（★ 本脚本的应用后校验就是它）

★ **三道自保护**：
★ ① **锚点唯一命中**（★ 命中 0 或 >1 ⇒ exit 2，不盲改）
★ ② **应用后 sha 校验**（★ 必须等于 `b70bfb0beb2bd591` ⇒ 否则 exit 1 并打印「不要自行修」）
★ ③ **幂等**（★ 已是 rev2 ⇒ exit 0）

★ **★ 待办（★ 第二组认领的瑕疵，★ 下一版 rev3 修）**：
★ ★ **rev2 的 `tol` 参数是【死参数】** —— ★ 签名保留但函数体不引用它
★ ⇒ ⇒ ★ **实际分组依据是 `round(float(v), 12)`** ⇒ ⇒ ★ 差值 < 1e-12 判为并列，≥ 1e-12 不判
★ ⇒ ⇒ ★ **★ 第四组采纳「先按 rev2 落地」**（★ 影响面极小：★ 实际评分几乎不会落进 1e-12 区间）
★ ⇒ ⇒ ★ **★ 但本条必须随台账一起记**：★ **签名承诺与实现不符** ⇒ ⇒ ★ **rev3 会改成按 `abs` 差 ≤ `tol` 分组**

用法：
```bash
python3 group4_state_driven/apply_state_layer_rev2.py creativity_lab/state_layer.py
```
"""
from __future__ import annotations

import hashlib
import os
import sys

REV1_SHA16 = "69a29c506a4e4ab0"
REV2_SHA16 = "b70bfb0beb2bd591"

# ★ ★★ 逐字原文（★ 第二组 2026-10-25 直发 · ★ 一行未改 · ★ 含 docstring）★★
OLD_BLOCK = '''def detect_tie(scores: List[float], tol: float = 1e-9) -> Dict[str, Any]:
    """★ **并列检测**（★ 第四组 2026-10-25 提出 ⇒ ★ 裁决：★ 接口层提供能力，★ 接线由第四组做）

    ★ **为什么放在接口层**：★ 「两个候选评分并列 ⇒ 它们是合法分歧」是【规则的一部分】，
    ★ ★ **不该靠调用方记得去调 `preserve_divergence`** ⇒ ⇒ ★ 否则接线时一漏，分歧语义就丢了
    ★ ★（★ 第四组已报告：★ 他们的 `Select(greedy)` 【会吃掉并列】⇒ ⇒ ★ 这正是必须补的一步）

    ★ **返回**：★ 有并列 ⇒ 返回 `{"kind": "tie", "members": [...], "scores": [...]}`；
    ★ 无并列 ⇒ 返回 `None`
    ★ ★ **本函数【不修改状态】** ⇒ ⇒ ★ 接线方式由调用方决定（★ 通常是：
    ★ `if detect_tie(...) is not None: st = preserve_divergence(st, detect_tie(...))`）
    """
    if not scores:
        return None
    best = max(scores)
    members = [i for i, v in enumerate(scores) if abs(v - best) <= tol]
    if len(members) < 2:
        return None
    return {"kind": "tie", "members": members,
            "scores": [scores[i] for i in members]}
'''

NEW_BLOCK = '''def detect_tie(scores: List[float], tol: float = 1e-9) -> List[Dict[str, Any]]:
    """★ **并列检测**（★ 第四组 2026-10-25 提出 ⇒ ★ 裁决：★ 接口层提供能力，★ 接线由第四组做）

    ★ **为什么放在接口层**：★ 「两个候选评分并列 ⇒ 它们是合法分歧」是【规则的一部分】，
    ★ ★ **不该靠调用方记得去调 `preserve_divergence`** ⇒ ⇒ ★ 否则接线时一漏，分歧语义就丢了
    ★ ★（★ 第四组已报告：★ 他们的 `Select(greedy)` 【会吃掉并列】⇒ ⇒ ★ 这正是必须补的一步）

    ★★★ **★ rev2 修正（★ 第四组 2026-10-25 实测发现 ⇒ ★ ① 只查最大值处漏检中位并列）**：
    ★ ★ **原实现只找【最高分处】的并列 ⇒ ⇒ `detect_tie([0.9, 0.5, 0.5])` 返回 None**
    ★ ⇒ ⇒ **⇒ 但「合法分歧」【未必只发生在最高分】⇒ ⇒ 来自不同来源的【第二名并列】也是真实意见分歧**
    ★ ⇒ ⇒ ★★ **⇒ 改法：★ 返回【所有】并列簇（★ 不只最大簇）★ ⇒ 且返回类型从单个 dict 改成 List**

    ★ **返回**：★ ★ **List of clusters**，每簇 `{"kind": "tie", "members": [...], "scores": [...]}`；
    ★ 无任何并列 ⇒ 返回 **空列表 `[]`**（★ ★ 不是 None —— ★ 空列表更安全，★ 调用方不必判 None）
    ★ ★ **本函数【不修改状态】** ⇒ ⇒ ★ 接线方式由调用方决定（★ 通常是：
    ★ `for d in detect_tie(scores): st = preserve_divergence(st, d)`）
    """
    if not scores:
        return []
    # ★ ★ 按【分值分组】⇒ ⇒ 找出所有【出现 >=2 次】的分值簇
    buckets = {}
    for i, v in enumerate(scores):
        buckets.setdefault(round(float(v), 12), []).append(i)
    out = []
    for key in sorted(buckets, reverse=True):     # ★ 按分值从高到低 ⇒ ⇒ 簇的顺序稳定
        idxs = buckets[key]
        if len(idxs) < 2:
            continue
        out.append({"kind": "tie", "members": idxs,
                    "scores": [scores[i] for i in idxs]})
    return out
'''


def sha16(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    if not os.path.exists(path):
        print("✘ 文件不存在：%s" % path)
        return 2
    cur = sha16(path)
    print("★ 当前 sha256 前16 = %s" % cur)

    if cur == REV2_SHA16:
        print("✔ 已是 rev2（sha=%s）⇒ 幂等退出，无需修改" % REV2_SHA16)
        return 0

    with open(path, "r", encoding="utf-8") as f:
        s = f.read()

    if cur != REV1_SHA16:
        print("⚠ 当前 sha 既不是 rev1(%s) 也不是 rev2(%s)" % (REV1_SHA16, REV2_SHA16))
        print("  ⇒ ★ 走【锚点唯一命中】路径（★ 仍不盲改）")

    n = s.count(OLD_BLOCK)
    if n != 1:
        print("✘ 锚点命中 %d 次（★ 必须恰好 1 次）⇒ 停止，不盲改" % n)
        return 2
    s = s.replace(OLD_BLOCK, NEW_BLOCK, 1)
    print("✔ 补丁已应用（★ 逐字原文）")

    # ── 原子写（★ 临时文件 + os.replace ⇒ 失败不截断）──
    tmp = path + ".rev2.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(s)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    print("✔ 已原子写回：%s" % path)

    new_sha = sha16(path)
    print("★ 应用后 sha256 前16 = %s（期望 %s）" % (new_sha, REV2_SHA16))
    if new_sha != REV2_SHA16:
        print("=" * 70)
        print("✘✘ sha 不符 ⇒ ★ **不要自行修** ⇒ ★ 请把 diff 发回第二组")
        print("=" * 70)
        return 1

    print("✔ 应用成功且【自验证通过】：sha256 = %s" % REV2_SHA16)
    print("★ ★ 已知瑕疵（★ 第二组认领 · ★ rev3 修）：★ rev2 的 `tol` 是【死参数】")
    print("  ⇒ 实际分组依据 = round(float(v), 12) ⇒ 差值 < 1e-12 判为并列")
    return 0


if __name__ == "__main__":
    sys.exit(main())
