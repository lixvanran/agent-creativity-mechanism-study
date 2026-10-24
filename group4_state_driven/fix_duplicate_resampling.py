#!/usr/bin/env python3
"""★ **Stage-1 重复采样处置（★ T10-1 出现两次 ⇒ ★ 重标记为 T10-2 · ★ 留痕 · ★ 零 API）**

★ **背景**：★ 补跑期间，★ 一个被 kill 的进程在退出前已把 **T10-1** 写盘
★ ⇒ ⇒ ★ 正式补跑又写了第二条 **T10-1** ⇒ ⇒ ★ **同一 (题, rep) 有两条记录**。

★ **★ 这不是文件损坏**：★ 两条都是**完整合法的独立采样**
★ （★ 各 9 次调用 / 0 错误 / 同批号 `v6s1-main-001` / ★ 决策内容措辞不同 ⇒ **确实是两次独立采样**）。

★ **★ 处置原则（★ 分析单元 = 题 ⇒ ★ 每题必须恰好 3 个重复）**：
★ ① **两条都保留**（★ 都是有效数据，★ 丢掉一条是浪费）
★ ② 把**后写入的那条**重标记为 **T10-2**（★ 它本就承担"第 2 次重复"的角色）
★ ③ ⇒ ★ **每题恰好 3 个重复 ⇒ ★ 臂间 n 相等**
★ ④ ★★ **必须留痕**：★ 重标记写进 `duplicate_resampling.json` ⇒ ★ 第三方可核对

★ **★★ 为什么不能静默去重或静默保留两条**：
★ ⇒ **① 静默去重** ⇒ ★ 丢掉一次有效采样 ⇒ ★ **样本量悄悄变小**
★ ⇒ **② 静默保留两条** ⇒ ★ T10 计权 4 次、G01/T07 各 3 次 ⇒ ★ **臂间 n 不等**
★ ⇒ ⇒ ★ **两种"不吭声"都会把缺口藏起来** ⇒ ⇒ ★ **⇒ 必须显式处置 + 留痕**。

用法：python3 -B group4_state_driven/fix_duplicate_resampling.py
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
EXP = "/workspace/第四组论证/experiment-design"
RUNS = os.path.join(EXP, "runs")
DATA = os.path.join(REPO, "group4_state_driven", "data")

SRC = os.path.join(RUNS, "arch6_stage1.jsonl")


def load():
    out = []
    with open(SRC, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            d = json.loads(line)
            d["_line"] = i
            out.append(d)
    return out


def main():
    rows = load()
    print("★ 原始行数 = %d" % len(rows))

    from collections import Counter, defaultdict
    tags = Counter(r["tag"] for r in rows)
    dups = [t for t, n in tags.items() if n > 1]
    if not dups:
        print("✔ 没有重复 tag ⇒ 无需处置")
        return 0
    print("★ 重复 tag：%s" % dups)

    # ── 找每题缺失的 rep ──
    by_topic = defaultdict(list)
    for r in rows:
        by_topic[r["topic_id"]].append(r)
    print("\n★ 处置前每题采样：")
    for t in sorted(by_topic):
        print("   %-6s %s" % (t, sorted(x["tag"] for x in by_topic[t])))

    log = {"duplicate_resampling": [], "rule":
           "同一 (题,rep) 出现两条完整独立采样 ⇒ 保留两条 ⇒ 后写入者重标记为该题缺失的 rep ⇒ "
           "⇒ 每题恰好 3 个重复 ⇒ 臂间 n 相等 ⇒ ★ 显式留痕，不静默去重、不静默重复计权"}

    # ── 对每个重复 tag：把后出现的重标为该题缺失的 rep ──
    for dup in sorted(dups):
        same = [r for r in rows if r["tag"] == dup]
        topic = same[0]["topic_id"]
        have = set()
        for r in rows:
            if r["topic_id"] == topic:
                have.add(r["rep"])
        missing = sorted(set(range(1, 4)) - have)
        if not missing:
            print("★ %s 没有缺失的 rep ⇒ 无法重标记（★ 需人工裁决）" % topic)
            return 1
        new_rep = missing[0]
        # ★ 后写入的那条（行号大的）承担新 rep
        target = max(same, key=lambda r: r["_line"])
        old_tag = target["tag"]
        old_rep = target.get("rep")
        target["tag"] = "%s-%d" % (topic, new_rep)
        # ★ ★ rep 字段【必须一起改】⇒ ★ 否则按 rep 分组时仍会被当重复计权
        #   （★ 上一次只改 tag ⇒ 核验报「reps=[1,1,3] 不等」⇒ ⇒ ★ 这就是「改一半」的形态）
        target["rep"] = new_rep
        target["_retagged_from"] = old_tag
        target["_retagged_from_rep"] = old_rep
        target["_retag_reason"] = "duplicate_resampling: 同 (题,rep) 第二次独立采样 ⇒ 重标记为缺失的 rep"
        log["duplicate_resampling"].append({
            "topic_id": topic, "original_tag": old_tag, "original_rep": old_rep,
            "new_tag": target["tag"], "new_rep": new_rep,
            "source_line": target["_line"],
            "elapsed": target.get("elapsed"),
            "n_calls": len(target.get("calls") or []),
            "evidence": "两条均为完整独立采样（决策 note 措辞不同 ⇒ 非重复写盘）",
        })
        print("★ %s（行%d，rep=%r）⇒ 重标记为 %s（rep=%d）"
              % (old_tag, target["_line"], old_rep, target["tag"], new_rep))

    # ── 写回（★ 原子写）──
    tmp = SRC + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            r.pop("_line", None)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, SRC)
    print("\n✔ 已原子写回：%s" % SRC)

    # ── 留痕 ──
    out_log = os.path.join(RUNS, "duplicate_resampling.json")
    tmp = out_log + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, out_log)
    print("✔ 留痕：%s" % out_log)

    # ── 核验 ──
    rows2 = load()
    c2 = Counter(r["tag"] for r in rows2)
    by_topic2 = defaultdict(list)
    for r in rows2:
        by_topic2[r["topic_id"]].append(r)
    print("\n★ 处置后每题采样：")
    ok = True
    for t in sorted(by_topic2):
        reps = sorted(x["rep"] for x in by_topic2[t])
        print("   %-6s reps=%s %s" % (t, reps, "✔" if reps == [1, 2, 3] else "★ 不等"))
        if reps != [1, 2, 3]:
            ok = False
    print("\n★ 唯一 tag 数 = %d ／ 总行数 = %d ⇒ %s"
          % (len(c2), len(rows2), "✔ 无重复" if len(c2) == len(rows2) else "★ 仍有重复"))
    return 0 if ok and len(c2) == len(rows2) else 1


if __name__ == "__main__":
    sys.exit(main())
