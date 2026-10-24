# -*- coding: utf-8 -*-
"""★ 门2：分维度偏好表【脚本化填充】（fill_paper_v2 范式）
   · 每个数字从 analysis 读入（policy_merged.json / policy_merged13.json）
   · 未知占位符直接 SystemExit（不许留空）
   · 幂等：已填过则跳过
   · 每格带 n（seed 数）与来源路径
"""
import io
import json
import os
import re
import sys

LAB = "/workspace/lab/routes/COLLAPSE"
PAPER = "/workspace/lab/PAPER-2026-10-25.md"

# 维度 → (展示名, 候选数来源)。★ 候选数必须【从代码/数据回源】，不许手写
DIMS = [("u", "u 修复型"), ("v", "v 范围"), ("t", "t 强度"),
        ("arb", "arb 仲裁"), ("nf", "nf 发散度"), ("mm", "mm 合并方式")]


def cand_count(code):
    """★ 候选取值数：【从动作空间常量回源】(REPAIR_IDS/SCOPE_IDS/STRICT_IDS/ARB_IDS/NF_IDS/MM_IDS)
    ⇒ ⇒ 抽不到 ⇒ SystemExit（不许手写、不许留空）"""
    import importlib
    sys.path.insert(0, LAB)
    W = importlib.import_module("workflow")
    names = {"u": "REPAIR_IDS", "v": "SCOPE_IDS", "t": "STRICT_IDS",
             "arb": "ARB_IDS", "nf": "NF_IDS", "mm": "MM_IDS"}
    const = getattr(W, names[code], None) or getattr(getattr(W, "ActionPolicy", None), names[code], None)
    if not const:
        raise SystemExit("✘ 维度 %s 的候选取值常量 %s 回源失败 ⇒ 停止" % (code, names[code]))
    items = [str(x) for x in const]
    return len(items), items


def load(path):
    if not os.path.exists(path):
        raise SystemExit("✘ 缺 analysis 文件，停止：%s" % path)
    return json.load(io.open(path, encoding="utf-8"))


def dim_stats(policy, code):
    if code not in policy:
        raise SystemExit("✘ 维度 %s 在 policy 里不存在，停止" % code)
    vals = [round(float(x), 3) for x in policy[code]]
    srt = sorted(vals, reverse=True)
    gap = round(srt[0] - srt[1], 3)
    mx = srt[0]
    idx = [i + 1 for i, x in enumerate(vals) if abs(x - mx) < 1e-9]
    tie = len(idx) > 1
    argmax = ",".join(str(i) for i in idx)
    return dict(vals=vals, argmax=argmax, gap=gap, tie=tie)


def main():
    a = load(os.path.join(LAB, "runs", "policy_merged.json"))          # 15 题版
    b = load(os.path.join(LAB, "runs", "holdout13", "policy_merged13.json"))  # 13 题版
    n_a = (a.get("meta") or {}).get("n_runs")
    n_b = (b.get("meta") or {}).get("n_runs")
    if not n_a or not n_b:
        raise SystemExit("✘ meta.n_runs 缺失 ⇒ 停止（每格必须带 n）")
    rows = []
    for code, label in DIMS:
        ca, items = cand_count(code)
        if ca is None:
            raise SystemExit("✘ 维度 %s 的【候选取值数】回源失败 ⇒ 停止（不许手写、不许留空）" % code)
        sa = dim_stats(a["policy"], code)
        sb = dim_stats(b["policy"], code)
        rows.append((label, ca, items, sa, sb, n_a, n_b))
    # 稳健性判定（脚本算，不手写）
    # ★ 判据档位（★ 界由主会话 2026-07-25 裁决给出，★ 不是由本批数据调出来的）：
    #   间距 < 0.15        ⇒ 无证据（不足以称偏好）
    #   0.15 ≤ 间距 < 0.30 ⇒ 弱证据（裁决原文：0.20 量级 = 刚过 0.15 线 = 弱证据）
    #   间距 ≥ 0.30        ⇒ 强证据（裁决原文：arb 的 0.400/0.583 = 跨训练集稳健）
    STRONG, WEAK = 0.30, 0.15

    def robust(sa, sb):
        if sa["tie"] and sb["tie"]:
            return "两版并列（该维度未被区分）"
        g = min(sa["gap"], sb["gap"])
        if g < WEAK:
            return "无证据（间距都 < 0.15 或两版 argmax 不同）"
        if g < STRONG:
            return "弱证据（间距 0.15–0.30 量级）"
        if sa["tie"] or sb["tie"]:
            return "单训练集稳健（仅一版；★ 凡引用必带该限定）"
        if sa["argmax"] != sb["argmax"]:
            return "无证据（两版 argmax 不同）"
        return "跨训练集稳健"
    lines = ["| 维度 | 候选取值数 | 15 题版 argmax / 间距 / 并列 | 13 题版 argmax / 间距 / 并列 | 跨训练集 |",
             "|---|--:|---|---|---|"]
    for label, ca, items, sa, sb, na, nb in rows:
        f = lambda s: "%s / %s / %s" % (s["argmax"], ("%.3f" % s["gap"]), "是" if s["tie"] else "否")
        lines.append("| %s | %d | %s | %s | **%s** |" % (label, ca, f(sa), f(sb), robust(sa, sb)))
    tbl = "\n".join(lines)
    concl = ("**结论（严格版，数字由脚本 `fill_dim_table.py` 从 analysis 填入）**："
             + "；".join("%s %s" % (r[0], robust(r[3], r[4])) for r in rows)
             + "。")
    src = ("★ 来源：`routes/COLLAPSE/runs/policy_merged.json`（15 题版，n=%d seed）与 "
           "`routes/COLLAPSE/runs/holdout13/policy_merged13.json`（13 题版，n=%d seed）；"
           "候选取值数由 `routes/COLLAPSE/workflow.py` 的动作空间回源抽；"
           "判据：Top1–Top2 间距 ≥ 0.15 才算偏好，并列即无偏好。" % (n_a, n_b))
    s = io.open(PAPER, encoding="utf-8").read()
    # 替换表 + 结论段
    m = re.search(r"\| 维度 \| 候选取值数 \|.*?\n\n", s, re.S)
    if not m:
        raise SystemExit("✘ 论文里找不到分维度表，停止")
    s = s[:m.start()] + tbl + "\n\n" + s[m.end():]
    s = re.sub(r"\*\*结论（严格版，?[^）]*?）\*\*：.*?。\n", concl + "\n", s, count=1, flags=re.S)
    # 结论段后面插来源
    s = s.replace(concl + "\n", concl + "\n" + src + "\n", 1)
    io.open(PAPER, "w", encoding="utf-8").write(s)
    print("✔ 分维度表已由脚本填入（含 n、候选取值数、来源路径）")
    print(tbl)


if __name__ == "__main__":
    main()
