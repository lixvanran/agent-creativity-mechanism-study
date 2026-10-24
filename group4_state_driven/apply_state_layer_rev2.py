#!/usr/bin/env python3
"""★ **第二组 `state_layer.py` rev2 应用脚本（★ 第四组自建 · ★ sha256 双向校验）**

★ **rev2 的内容**：★ 修第 5 条差异 ⇒ ★ `detect_tie` 从【只查最高分簇】改成【返回所有并列簇】。
★ ★ **返回类型同时变了**：`Dict[str, Any]` ⇒ `List[Dict[str, Any]]`（★ 空时返回 `[]` 而非 `None`）。

★ **三道自保护**（★ 与 rev1 脚本同款）：
★ ① **锚点唯一命中**（★ 命中 0 或 >1 ⇒ exit 2，不盲改）
★ ② **应用后 sha 校验**（★ 必须等于 `b70bfb0beb2bd591` ⇒ 否则 exit 1 并打印「不要自行修」）
★ ③ **幂等**（★ 已是 rev2 ⇒ exit 0）

★ **用法**：
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

OLD_SIG = 'def detect_tie(scores: List[float], tol: float = 1e-9) -> Dict[str, Any]:'
NEW_SIG = 'def detect_tie(scores: List[float], tol: float = 1e-9) -> List[Dict[str, Any]]:'

OLD_BODY = '''    ★ **返回**：★ 有并列 ⇒ 返回 `{"kind": "tie", "members": [...], "scores": [...]}`；
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

NEW_BODY = '''    ★ ★ **rev2 语义（★ 第二组 2026-10-25 裁决第 5 条差异）**：
    ★ ★ **返回【所有】并列簇（★ 不只最大簇）** ｜★ **返回类型 `Dict` ⇒ `List[Dict]`**
    ★ ★ **空时返回 `[]`（★ 不是 `None`）⇒ ⇒ ★ 调用方不必判 None**

    ★ **返回**：★ 每个元素 = `{"kind": "tie", "members": [...], "scores": [...]}`；
    ★ 无任何并列 ⇒ 返回 `[]`
    ★ ★ **本函数【不修改状态】** ⇒ ⇒ ★ 接线方式由调用方决定（★ 通常是：
    ★ `for d in detect_tie(scores): st = preserve_divergence(st, d)`）

    ★ ★ **为什么不能只查最高分（★ rev1 的缺陷）**：
    ★ **「合法分歧」未必只发生在最高分** ⇒ ⇒ ★ 来自不同来源的【第二名并列】也是真实意见分歧
    ★ ⇒ ⇒ ★ rev1 只查 `best = max(scores)` ⇒ ⇒ ★ 会把它漏掉 ⇒ ⇒ ★ **分歧语义又丢**
    """
    if not scores:
        return []
    groups: Dict[float, List[int]] = {}
    for i, v in enumerate(scores):
        key = round(float(v), 9)
        groups.setdefault(key, []).append(i)
    out: List[Dict[str, Any]] = []
    for key in sorted(groups, reverse=True):
        members = groups[key]
        if len(members) < 2:
            continue
        out.append({"kind": "tie", "members": members,
                    "scores": [scores[i] for i in members]})
    return out
'''


def sha16(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def rep(s: str, old: str, new: str, tag: str) -> str:
    n = s.count(old)
    if n != 1:
        raise SystemExit("✘ 锚点 [%s] 命中 %d 次（★ 必须恰好 1 次）⇒ 停止，不盲改" % (tag, n))
    return s.replace(old, new, 1)


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

    s = rep(s, OLD_SIG, NEW_SIG, "1/3 签名改 List[Dict]")
    s = rep(s, OLD_BODY, NEW_BODY, "2/3 函数体与 docstring")
    print("✔ 补丁 1/3、2/3 已应用")

    # ── 原子写 ──
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
