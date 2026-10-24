#!/usr/bin/env python3
"""★ **第二组 `state_layer.py` rev1 应用脚本（★ 第四组自建 · ★ 三道自保护）**

★ **为什么第四组自己写而不用第二组那份**：
★ ★ 第二组直发的脚本【同样需要手抄】⇒ ⇒ ★ 抄脚本与抄 diff 是【同一类漏洞】
★ ⇒ ⇒ ★ **第四组的解法**：★ 不抄任何文本 ⇒ ⇒ ★ **直接对【已核过 sha 的旧版原文】做锚点替换**
★ ⇒ ⇒ ★ ★ **最终结果由 sha256 双向校验兜底** ⇒ ⇒ ★ 抄错了必然对不上 `69a29c506a4e4ab0` ⇒ ⇒ ★ ★ **结构上不可能静默产出一个错接口**。

★ **三条自保护**：
★ ① **锚点唯一命中**：★ 每个锚点必须**恰好命中 1 次** ⇒ 命中 0 或 >1 ⇒ **exit 2 停止**（★ 绝不盲改）
★ ② **应用后 sha 校验**：★ 必须等于 `69a29c506a4e4ab0` ⇒ ★ 否则 **exit 1 并打印「不要自行修」**
★ ③ **幂等**：★ 已是新版 ⇒ 直接 exit 0

★ **用法**：
```bash
python3 group4_state_driven/apply_state_layer_rev1.py creativity_lab/state_layer.py
```

★ **★ 这 5 处改动全部来自第二组的裁决（★ 逐条对应第二组 2026-10-25 19:5x / 20:0x 两条消息）**：
★ ① 加两个阈值常量 `DEAD_END_THRESHOLD = 3` / `SUPPORT_THRESHOLD = 2`
★ ② `Attempt` 加字段 `consecutive_no_new: int = 0`
★ ③ `record_attempt` 死路判定改成【连续】计数（有进展即清零）
★ ④ `add_evidence` 加支持性证据分支（累积到阈值 ⇒ 转 `supported` + 留痕）
★ ⑤ 新增 `detect_tie(scores)`（★ 纯函数、不改状态）
"""
from __future__ import annotations

import hashlib
import os
import sys

OLD_SHA16 = "38795bf6adfdee05"
NEW_SHA16 = "69a29c506a4e4ab0"


def sha16(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def rep(s: str, old: str, new: str, tag: str) -> str:
    """★ 唯一命中替换：★ 命中 0 或 >1 ⇒ 响亮失败（★ 默认必须是【抛错停下】，★ 不许静默跳过）"""
    n = s.count(old)
    if n != 1:
        raise SystemExit("✘ 锚点 [%s] 命中 %d 次（★ 必须恰好 1 次）⇒ 停止，不盲改" % (tag, n))
    return s.replace(old, new, 1)


# ── ① 两个阈值常量 ──
P1_OLD = 'HYP_SUPPORTED = "supported"\n'
P1_NEW = ('HYP_SUPPORTED = "supported"\n'
          '\n'
          '# ★ ★ 两个阈值（★ 第四组 2026-10-25 独立审计后新增 ⇒ ★ 都是【人写死的固定规则】）\n'
          '# ★ 死路判定看【连续】无新信息的次数（★ 不是累计）★★\n'
          'DEAD_END_THRESHOLD = 3\n'
          '# ★ 假设转 `supported` 所需的【支持性证据】条数（★ 一次不算 ⇒ 两次才算）★★\n'
          'SUPPORT_THRESHOLD = 2\n')

# ── ② Attempt 字段 ──
P2_OLD = '    """★ 已尝试方法（★ 记录尝试了什么、产生了什么新信息）"""\n'
P2_NEW = ('    """★ 已尝试方法（★ 记录尝试了什么、产生了什么新信息）\n'
          '\n'
          '    ★★ `consecutive_no_new` 与 `used` 的区别（★ 第四组 2026-10-25 独立审计发现 ⇒ ★ 真 bug）：\n'
          '    ★ **`used` 是【累计】尝试次数；★ `consecutive_no_new` 是【连续无新信息】的次数**\n'
          '    ★ ⇒ ⇒ ★ **判死路必须看【连续】而不是【累计】** ⇒ ⇒ ★\n'
          '    ★ ★ **否则 `(True, True, False)` 这种"成功过两次、最近一次没进展"的方法会被误判成死路**\n'
          '    """\n')

P3_OLD = '    produced_new: bool = False\n    dead_end: bool = False\n'
P3_NEW = ('    produced_new: bool = False\n'
          '    consecutive_no_new: int = 0     # ★ ★ 连续无新信息的次数（★ 判死路只看这个）\n'
          '    dead_end: bool = False\n')

# ── ③ record_attempt 死路判定 ──
P4_OLD = ('    # ★ 死路判定：★ 连续 3 次尝试都没有新信息 ⇒ 标记死路\n'
          '    if not produced_new and at.used >= 3:\n')
P4_NEW = ('    # ★ ★ 死路判定：★ 【连续】3 次无新信息（★ 不是累计 3 次）\n'
          '    if produced_new:\n'
          '        at.consecutive_no_new = 0          # ★ ★ 有新信息 ⇒ 连续计数【清零】\n'
          '    else:\n'
          '        at.consecutive_no_new += 1\n'
          '    if at.consecutive_no_new >= DEAD_END_THRESHOLD:\n')

# ── ④ add_evidence 支持分支 ──
P5_OLD = ('    """★ **检验**：★ 追加证据；★ 若该证据【反证】假设 ⇒ 假设被推翻"""\n')
P5_NEW = ('    """★ **检验**：★ 追加证据；★ 若该证据【反证】假设 ⇒ 假设被推翻；\n'
          '    ★ 若该证据【支持】假设 ⇒ 累积到阈值 ⇒ 假设转 `supported`（★ 第四组 2026-10-25 独立审计发现 ⇒ ★ 真 bug）\n'
          '\n'
          '    ★★ **为什么必须有 `supported` 这条路径（★ 原实现的后果）**：\n'
          '    ★ 原实现里 `add_evidence(refutes=False)` 【不改变 status】⇒ ⇒ 假设永远停在 `open`\n'
          '    ⇒ ⇒ ★ 而 `choose_action` 里 `check_hypothesis` 分支【优先于】`connect`\n'
          '    ⇒ ⇒ ★ ⇒ **分歧连接被无限期阻塞**（★ 第四组实测：10 次支持性证据 + 1 条合法分歧 ⇒ 仍返回 `check_hypothesis`）\n'
          '    ⇒ ⇒ ★★ **⇒ 修法：★ 支持性证据累积到 `SUPPORT_THRESHOLD` 条 ⇒ ⇒ 假设转 `supported` ⇒ ⇒ 不再阻塞 `connect`**\n'
          '\n'
          '    ★★ **`SUPPORT_THRESHOLD = 2` 的理由**：★ **一次支持不算"被支持"**（★ 一次可能是噪声）★ ★\n'
          '    ★ **两次独立支持才算** ⇒ ⇒ ★ ★ **但这是一个【新自由度】⇒ ⇒ 第四组接线时可在 manifest 里显式覆盖**\n'
          '    """\n')

P6_OLD = ('                h.status = HYP_REFUTED\n'
          '                s.progress.append("refuted:%s" % hid)\n'
          '            return s\n')
P6_NEW = ('                h.status = HYP_REFUTED\n'
          '                s.progress.append("refuted:%s" % hid)\n'
          '            else:\n'
          '                # ★ ★ 支持性证据也要留痕（★ 状态回放要能区分支持与反证）\n'
          '                n_sup = sum(1 for e in h.evidence if not e.get("refutes"))\n'
          '                s.progress.append("evidence:%s:support:%d" % (hid, n_sup))\n'
          '                if n_sup >= SUPPORT_THRESHOLD and h.status == HYP_OPEN:\n'
          '                    h.status = HYP_SUPPORTED\n'
          '                    s.progress.append("supported:%s" % hid)\n'
          '            return s\n')

# ── ⑤ detect_tie（★ 用第二组【补发的正确片段】）──
P7_OLD = ('def preserve_divergence(st: State, d: Dict[str, Any]) -> State:\n')
P7_NEW = ('def detect_tie(scores: List[float], tol: float = 1e-9) -> Dict[str, Any]:\n'
          '    """★ **并列检测**（★ 第四组 2026-10-25 提出 ⇒ ★ 裁决：★ 接口层提供能力，★ 接线由第四组做）\n'
          '\n'
          '    ★ **为什么放在接口层**：★ 「两个候选评分并列 ⇒ 它们是合法分歧」是【规则的一部分】，\n'
          '    ★ ★ **不该靠调用方记得去调 `preserve_divergence`** ⇒ ⇒ ★ 否则接线时一漏，分歧语义就丢了\n'
          '    ★ ★（★ 第四组已报告：★ 他们的 `Select(greedy)` 【会吃掉并列】⇒ ⇒ ★ 这正是必须补的一步）\n'
          '\n'
          '    ★ **返回**：★ 有并列 ⇒ 返回 `{"kind": "tie", "members": [...], "scores": [...]}`；\n'
          '    ★ 无并列 ⇒ 返回 `None`\n'
          '    ★ ★ **本函数【不修改状态】** ⇒ ⇒ ★ 接线方式由调用方决定（★ 通常是：\n'
          '    ★ `if detect_tie(...) is not None: st = preserve_divergence(st, detect_tie(...))`）\n'
          '    """\n'
          '    if not scores:\n'
          '        return None\n'
          '    best = max(scores)\n'
          '    members = [i for i, v in enumerate(scores) if abs(v - best) <= tol]\n'
          '    if len(members) < 2:\n'
          '        return None\n'
          '    return {"kind": "tie", "members": members,\n'
          '            "scores": [scores[i] for i in members]}\n'
          '\n'
          '\n'
          'def preserve_divergence(st: State, d: Dict[str, Any]) -> State:\n')

PATCHES = [
    ("1/5 加两个阈值常量", P1_OLD, P1_NEW),
    ("2/5 Attempt docstring", P2_OLD, P2_NEW),
    ("3/5 Attempt 加 consecutive_no_new 字段", P3_OLD, P3_NEW),
    ("4/5 record_attempt 死路判定改连续计数", P4_OLD, P4_NEW),
    ("5/5 add_evidence docstring", P5_OLD, P5_NEW),
    ("5/5 add_evidence 支持分支", P6_OLD, P6_NEW),
    ("5/5 新增 detect_tie", P7_OLD, P7_NEW),
]


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

    # ── 幂等：已是新版 ⇒ 直接退出 ──
    if cur == NEW_SHA16:
        print("✔ 已是 rev1（sha=%s）⇒ 幂等退出，无需修改" % NEW_SHA16)
        return 0

    with open(path, "r", encoding="utf-8") as f:
        s = f.read()

    if cur != OLD_SHA16:
        print("⚠ 当前 sha 既不是旧版(%s) 也不是新版(%s)" % (OLD_SHA16, NEW_SHA16))
        print("  ⇒ ★ 走【锚点唯一命中】路径（★ 仍不盲改：每个锚点必须恰好命中 1 次）")

    for tag, old, new in PATCHES:
        s = rep(s, old, new, tag)
        print("✔ 补丁 %s 已应用" % tag)

    # ── 原子写（★ 临时文件 + os.replace ⇒ 失败不会把原文件截断成 0）──
    tmp = path + ".rev1.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(s)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    print("✔ 已原子写回：%s" % path)

    # ── 应用后 sha 校验（★ 双向校验：★ 对不上就是抄错了/原文不同 ⇒ 不许自行修）──
    new_sha = sha16(path)
    print("★ 应用后 sha256 前16 = %s（期望 %s）" % (new_sha, NEW_SHA16))
    if new_sha != NEW_SHA16:
        print("=" * 70)
        print("✘✘ sha 不符 ⇒ ★ **不要自行修** ⇒ ★ 请把 diff 发回第二组")
        print("   ★ 旧版副本在 /tmp/state_layer_rev0.py（★ 可回滚）")
        print("=" * 70)
        return 1

    print("✔ 应用成功且【自验证通过】：sha256 = %s" % NEW_SHA16)
    print("★ 现在可以跑：python3 -B creativity_lab/experiments/test_state_layer.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
