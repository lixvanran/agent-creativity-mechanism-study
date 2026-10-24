#!/usr/bin/env python3
"""★ **接口修订 rev2 应用脚本（★ 自验证 · 第四组 2026-10-24 实测发现第 5 条差异）**

> 落点：`creativity_lab/experiments/apply_state_layer_rev2.py`
> 目标：★ `state_layer.py` 从 rev1（`69a29c506a4e4ab0`）升级到 rev2（`b70bfb0beb2bd591`）

## ★★ rev2 改什么（★ 一处，★ 语义级）
★ **`detect_tie` 只查【最高分处】⇒ ⇒ 中位并列漏检**
★ ⇒ 第四组实测 `detect_tie([0.9, 0.5, 0.5])` 返回 None
★ ⇒ ⇒ ★ **改法：★ 返回【所有】并列簇（★ 不只最大簇）★ 且返回类型从单个 dict 改成 `List[Dict]`**
★ ⇒ ⇒ ★ **语义理由：★ 「合法分歧」【未必只发生在最高分】⇒ ⇒ 来自不同来源的【第二名并列】也是真实意见分歧**

## ★★★ ★ 三条自保护（★ 与 rev1 同款）
① **锚点唯一命中**（命中 0 或 >1 ⇒ 停止，exit 2）② **应用后 sha256 校验**（不符 ⇒ exit 1）③ **幂等**

## ★★ 为什么还是"脚本"而不是"diff"（★ 2026-10-24 教训）
★ 第四组实测：★ 我手抄的 diff【hunk 头被截断（`refutes: bool = Fals`）⇒ ⇒ `git apply` 报 `corrupt patch`】
★ ⇒ ⇒ ★ **⇒ "用 diff 代替全文"只换了抄的对象，★ 漏洞没堵** ⇒ ⇒ ★ **⇒ 真正堵住的是【输出可被 sha256 证伪】**
"""
import hashlib
import os
import sys

EXPECT_SHA = "b70bfb0beb2bd591"
OLD_SHA = "69a29c506a4e4ab0"

OLD_SIG = "def detect_tie(scores: List[float], tol: float = 1e-9) -> Dict[str, Any]:"
NEW_SIG = "def detect_tie(scores: List[float], tol: float = 1e-9) -> List[Dict[str, Any]]:"

# ★ docstring 修订（★ 也要进脚本 ⇒ ⇒ 仓内文件必须等于【脚本输出】⇒ ⇒ sha 唯一）
OLD_DOC = (
    "    ★ **返回**：★ 有并列 ⇒ 返回 `{\"kind\": \"tie\", \"members\": [...], \"scores\": [...]}`；\n"
    "    ★ 无并列 ⇒ 返回 `None`\n"
    "    ★ ★ **本函数【不修改状态】** ⇒ ⇒ ★ 接线方式由调用方决定（★ 通常是：\n"
    "    ★ `if detect_tie(...) is not None: st = preserve_divergence(st, detect_tie(...))`）"
)
NEW_DOC = (
    "    ★★★ **★ rev2 修正（★ 第四组 2026-10-24 实测发现 ⇒ ★ ① 只查最大值处漏检中位并列）**：\n"
    "    ★ ★ **原实现只找【最高分处】的并列 ⇒ ⇒ `detect_tie([0.9, 0.5, 0.5])` 返回 None**\n"
    "    ★ ⇒ ⇒ **⇒ 但「合法分歧」【未必只发生在最高分】⇒ ⇒ 来自不同来源的【第二名并列】也是真实意见分歧**\n"
    "    ★ ⇒ ⇒ ★★ **⇒ 改法：★ 返回【所有】并列簇（★ 不只最大簇）★ ⇒ 且返回类型从单个 dict 改成 List**\n"
    "\n"
    "    ★ **返回**：★ ★ **List of clusters**，每簇 `{\"kind\": \"tie\", \"members\": [...], \"scores\": [...]}`；\n"
    "    ★ 无任何并列 ⇒ 返回 **空列表 `[]`**（★ ★ 不是 None —— ★ 空列表更安全，★ 调用方不必判 None）\n"
    "    ★ ★ **本函数【不修改状态】** ⇒ ⇒ ★ 接线方式由调用方决定（★ 通常是：\n"
    "    ★ `for d in detect_tie(scores): st = preserve_divergence(st, d)`）"
)

OLD_BODY = (
    "    if not scores:\n"
    "        return None\n"
    "    best = max(scores)\n"
    "    members = [i for i, v in enumerate(scores) if abs(v - best) <= tol]\n"
    "    if len(members) < 2:\n"
    "        return None\n"
    "    return {\"kind\": \"tie\", \"members\": members,\n"
    "            \"scores\": [scores[i] for i in members]}"
)

NEW_BODY = (
    "    if not scores:\n"
    "        return []\n"
    "    # ★ ★ 按【分值分组】⇒ ⇒ 找出所有【出现 >=2 次】的分值簇\n"
    "    buckets = {}\n"
    "    for i, v in enumerate(scores):\n"
    "        buckets.setdefault(round(float(v), 12), []).append(i)\n"
    "    out = []\n"
    "    for key in sorted(buckets, reverse=True):     # ★ 按分值从高到低 ⇒ ⇒ 簇的顺序稳定\n"
    "        idxs = buckets[key]\n"
    "        if len(idxs) < 2:\n"
    "            continue\n"
    "        out.append({\"kind\": \"tie\", \"members\": idxs,\n"
    "                    \"scores\": [scores[i] for i in idxs]})\n"
    "    return out"
)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python3 apply_state_layer_rev2.py <state_layer.py>")
        return 2
    p = sys.argv[1]
    if not os.path.exists(p):
        print("X 文件不存在: %s" % p)
        return 2
    before = sha256_of(p)
    print("== ★ 接口修订 rev2（★ 自验证）==")
    print("   修订前 sha256: %s" % before[:16])
    if before.startswith(EXPECT_SHA):
        print("   ★ 已经是新版（%s）⇒ 无需修改" % EXPECT_SHA)
        print("   OK sha256 = %s" % EXPECT_SHA)
        return 0
    if not before.startswith(OLD_SHA):
        print("   ★★ 不是 rev1（%s）⇒ ★ 走【锚点唯一命中】路径" % before[:16])
    s = open(p, encoding="utf-8").read()
    for i, (a, b) in enumerate([(OLD_SIG, NEW_SIG), (OLD_DOC, NEW_DOC), (OLD_BODY, NEW_BODY)], 1):
        cnt = s.count(a)
        if cnt != 1:
            print("   X 补丁 %d 锚点命中 %d 次（★ 期望恰好 1 次）⇒ 停止" % (i, cnt))
            return 2
        s = s.replace(a, b)
        print("   OK 补丁 %d/3 已应用" % i)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(s)
    os.replace(tmp, p)
    after = sha256_of(p)
    print("   修订后 sha256: %s" % after[:16])
    if not after.startswith(EXPECT_SHA):
        print("   X sha256 不等于预期 %s ⇒ ★ 【应用失败】⇒ ★ 不要自行「修」⇒ ★ 请把文件 diff 回来" % EXPECT_SHA)
        return 1
    print()
    print("OK 应用成功且【自验证通过】：sha256 = %s" % EXPECT_SHA)
    print("★ 接线侧注意：★ detect_tie 现在返回【List】★ ⇒ 循环改成：")
    print("      for d in detect_tie(scores): st = preserve_divergence(st, d)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
