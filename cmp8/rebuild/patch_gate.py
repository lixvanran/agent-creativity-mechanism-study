#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判官闸门：补「已知真断言」侧检查（行级插入，幂等）。

为什么必须补：旧版闸门**只查假断言侧**（`tn/(tn+fp) < 0.5`）
⇒ 一个「什么都答矛盾」的判官（真召回 0/5）能穿过闸门
⇒ 每个臂矛盾率都变 100% ⇒ **七臂数值完全相同**
⇒ ⑤b vs ⑤c 自动判「不可分辨」
⇒ **产出一份「看起来干净、读起来像结论」的假零结果**。

声明（交接文件 §0.5 第 5 步 / §5.3 / RUNBOOK 阶段 2）写的就是
「**真 ≥3/4 且 假 ≥3/4**」⇒ 这里只是把**已经声明过**的那一侧补上，
**阈值仍是 0.5，不新增口径**。

用法：python3 patch_gate.py <analyze_cmp6.py 路径>
"""
import io
import sys

ANCHOR = '    if (tp + fn) and tp / (tp + fn) < 0.5:'

BLOCK = '''    # ★ 补「已知真断言」侧检查（同一阈值 0.5，不新增口径；见 patch_gate.py 头注）
    if (tp + fn) and tp / (tp + fn) < 0.5:
        print("❌ 判官在「已知真断言」上召回不足 50% ⇒ 判据分不开对错，**拒绝出数**。")
        json.dump(dict(detail=sc_detail, aborted=True),
                  open("%s/judge_selfcheck.json" % OUT, "w"), ensure_ascii=False, indent=1)
        return
'''


def apply(path):
    s = io.open(path, encoding="utf-8").read()
    if ANCHOR in s:
        print("  · 已在，跳过：%s" % path)
        return False
    # 插在「假断言侧检查」那块之后（它的 return 之后、真侧 json.dump 之前）
    lines = s.split("\n")
    out = []
    done = False
    for i, l in enumerate(lines):
        out.append(l)
        if not done and l.strip() == "return" and i > 3 and "aborted=True" in lines[i - 2]:
            # 找到 abort 分支的 return ⇒ 在其后插入真侧检查
            out.append(BLOCK.rstrip("\n"))
            done = True
    if not done:
        print("  ✗ %s：找不到闸门 abort 分支" % path)
        return False
    io.open(path, "w", encoding="utf-8").write("\n".join(out))
    print("  ✓ %s：判官闸门补真侧检查" % path)
    return True


if __name__ == "__main__":
    for p in (sys.argv[1:] or ["analyze_cmp6.py"]):
        apply(p)
    print("done")
