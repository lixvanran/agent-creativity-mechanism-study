#!/usr/bin/env python3
"""★ **改动回读断言**（★ 2026-10-25 论文簇建议采纳）

> 落点：`creativity_lab/experiments/verify_anchors.py`
> 用法：`python3 -B creativity_lab/experiments/verify_anchors.py`
> 退出码：0 = 全部锚点命中；1 = 有锚点缺失
>
> ## ★★ 为什么要有这个（★ 论文簇 2026-10-25 的建议）
> ★ 论文簇原话：★ 「你们那 29 个脚本的语法自检全过，★ 但【**语法对 ≠ 改动落盘了**】」
> ★★ **我自己的经历**：★ 本轮我写过 7 个 patch 脚本（`patch4`–`patch7`）⇒ ★ **它们全都只打印「✔ 已改」**
> ★ ★ **⇒ 但【打印成功 ≠ 改动真的落盘】** ⇒ ⇒ ★ **我的 patch 脚本当时【没有任何回读断言】**
> ★ ★ ⇒ ★ **⇒ 一条不落盘的改动会【静默通过】，★ 而上层脚本不会发现**
>
> ## ★★ 本脚本做什么
> ★ **把【必须存在】的锚点写成清单 ⇒ ★ 每次改动后跑一遍 ⇒ ★ 缺一个就退出码非零**
> ★ ⇒ ★ **它把"我以为我改了"变成"可机器核验的"**
> ★ ★ **注意：★ 语法自检（`lint_docstrings.py`）与本脚本【互补而不重叠】**
> ★ ★ **· `lint_docstrings.py` ⇒ 文件【能不能被解析】**
> ★ ★ **· 本脚本 ⇒ 改动【有没有真的落到盘上】**
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PREREG = os.path.join(ROOT, "docs/cmp8/routes/COLLAPSE/eval/PREREG-TOPOLOGY-ARM.md")
# ★★★ 报告路径（★ 2026-10-25 改：★ 原先硬编码 /workspace 下的路径 ⇒ ⇒ 报告一改名就失效）
# ★ ⇒ 改为【优先仓内 docs/交付/】，★ 再退回 /workspace，★ 最后可用 --report 覆盖
def _pick_report() -> str:
    cands = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "docs", "交付", "第二组交付报告_2026-10-25.md"),
        "/workspace/第二组交付报告_2026-10-25.md",
    ]
    for c in cands:
        if os.path.isfile(c):
            return c
    return cands[0]

REPORT = os.environ.get("SECONDGROUP_REPORT") or _pick_report()

# ★ (文件, 必须存在的锚点字符串, 这个锚点【为什么必须存在】)
ANCHORS = [
    (PREREG, "§2.0d", "★ 两因子混在一起的发现 + 2×2 分解（★ 负责人追问逼出）"),
    (PREREG, "nosel_b3_synth", "★ 第三对照臂（★ 把交互与综述拆成单因子）"),
    (PREREG, "H-TOPO-4c", "★ 综述效应判决行（★ 新增）"),
    (PREREG, "H-TOPO-4d", "★ 可见性图效应判决行（★ 新增）"),
    (PREREG, "面宽轴内部一致性门", "★ H-TOPO-5 作用域澄清（★ 质量轴不在门内）"),
    (PREREG, "§6 · 数据产生后的改动记录", "★ 判据改动登记（★ 方向只能是收紧或澄清）"),
    (PREREG, "17244d2d329c69939e88476f3a93d275ec7296a6", "★ 判据版本锚（★ 正式批启动时的 HEAD）"),
    (PREREG, "两批合并", "★ H0 原料 = 新批 12 + 旧批 9 = 21（★ 负责人裁决）"),
    (PREREG, "Wilson", "★ H0 报法 = 点估计 + 区间（★ 不报单一精确率）"),
    (REPORT, "S3 = [1,3,1]", "★ 报告更正：★ 理科题模态【中位 1 但非恒定】"),
    (REPORT, "自检门禁全绿 ≠ 内容正确", "★ 报告 §2.25 纪律 2"),
    (REPORT, "恒定性", "★ 报告 §2.25 纪律 1（★ 题级判定）"),
]

# ★ 必须存在的文件
FILES = [
    os.path.join(ROOT, "creativity_lab/state_layer.py"),
    os.path.join(ROOT, "creativity_lab/experiments/test_state_layer.py"),
    os.path.join(ROOT, "creativity_lab/experiments/check_readout_liveness.py"),
    os.path.join(ROOT, "creativity_lab/experiments/h0_calibration.py"),
    os.path.join(ROOT, "docs/交接/WORKPACK-1-evidence-entry.md"),
    os.path.join(ROOT, "docs/交接/WORKPACK-2-stem-chain.md"),
    os.path.join(ROOT, "docs/交接/WORKPACK-2-state-chain.md"),
    os.path.join(ROOT, "docs/交接/WORKPACK-3-min-architecture.md"),
    os.path.join(ROOT, "docs/交接/STATE-LAYER-ASSESSMENT.md"),
]


def main() -> int:
    missing = []
    print("== ★ 改动回读断言（★ 语法对 ≠ 改动落盘了）==")
    for path, anchor, why in ANCHORS:
        if not os.path.exists(path):
            missing.append("%s（文件不存在）" % os.path.basename(path))
            print("  ✘ 文件缺失：%s" % path)
            continue
        txt = open(path, encoding="utf-8").read()
        if anchor in txt:
            print("  ✔ %-26s ｜ %s" % (anchor[:26], why))
        else:
            missing.append("%s :: %s" % (os.path.basename(path), anchor))
            print("  ✘ 缺锚点：%-26s ｜ %s" % (anchor[:26], why))
    print("  ── 必须存在的文件 ──")
    for f in FILES:
        ok = os.path.exists(f)
        print("  %s %s" % ("✔" if ok else "✘", os.path.relpath(f, ROOT)))
        if not ok:
            missing.append(f)
    print()
    if missing:
        print("✘ 缺 %d 项 ⇒ ⇒ ★ 【有改动没落盘】⇒ 退出码非零" % len(missing))
        for m in missing:
            print("   ★", m)
        return 1
    print("✔ 全部锚点命中（★ 改动确实落盘了）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
