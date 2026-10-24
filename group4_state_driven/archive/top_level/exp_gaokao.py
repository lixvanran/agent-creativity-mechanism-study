#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 「你如何看待高考英语作文」对比实验（grok-4.20 via OpenRouter）

═══ 实验是什么 ═══
同一道题、同一模型、同一批档案，比较**四种产出**：
    A  = 直接调用 LLM（无状态）
    C0 = 立场档案全文进 system prompt（= 等强度提示词对照 ≈ "模板"）
    C1 = 取舍驱动的状态机（4 步管线）
    C2 = C1 + 事实层 + 极性锚 + 「已排除选项」（4 步管线）
    S  = 等调用数的中性 4 步管线（剥离"管线深度"这个混淆）
**3 次独立重复**（题内重复测量；分析单元=题 ⇒ 本题 n=1 样本=3）。

═══ 为什么这题是"模板 vs 状态"的天然战场 ═══
高考英语作文本身就是**模板化写作的极致**（外部指令注入内容的极端形态），
⇒ C0 与 C2 的对比在这里不是隐喻，是字面对手。

═══ 诚实的局限（随结果一起给）═══
· **单题 n=1，样本 3** ⇒ 只能看**方向**，**不能**做统计判定。
  依 F18：这是「检出力不足」，**不是「无效应」」。要判定必须加题。
· **观点文**，与第四组前 5 题（小说/歌词/散文/邮件/对话）**不同体裁** ⇒ 不可合并统计。
· **不做人类评分**（无判官路线）。观点文本有成熟评分标准（TEM-8/雅思 Task 2），
  但本项目已证人类评分受来源标签与流畅度污染 ⇒ 不作效标。
· **不做体裁漂移门**（门是为创作类体裁写的）⇒ 改由报告里的人工检查呈现。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import metrics2 as M        # noqa: E402
import gates as G           # noqa: E402
import polarity_lexicon as PL  # noqa: E402
import topics_gaokao as TG  # noqa: E402


def run(cmd: list, label: str) -> None:
    print("\n" + "=" * 76)
    print("▶ %s" % label)
    print("=" * 76)
    r = subprocess.run(cmd, cwd=str(HERE))
    if r.returncode != 0:
        print("[!] %s 返回码 %d" % (label, r.returncode))


def load_jsonl(p: Path):
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _emit_outputs(p_orig, a, anchor):
    """只给产出：单批过滤 + 正文并列（评价不在此文件内）。"""
    import report_outputs as RO
    import sys as _s
    argv = list(_s.argv)
    out = Path(p_orig).parent / ("%s_outputs.md" % a.tag)
    _s.argv = ["report_outputs", str(p_orig), str(out), a.model, anchor]
    try:
        RO.main()
    finally:
        _s.argv = argv
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default="1,2,3", help="独立重复次数（默认 3）")
    ap.add_argument("--arms", default="A,C0,C1,C2,S")
    ap.add_argument("--api", default="openrouter")
    ap.add_argument("--model", default="x-ai/grok-4.20")
    ap.add_argument("--workers", default="4")
    ap.add_argument("--tag", default="gk")
    ap.add_argument("--skip-run", action="store_true", help="只分析已有数据")
    a = ap.parse_args()

    samples = ",".join(str(i) for i in range(1, len(a.samples.split(",")) + 1))
    d = HERE / "runs"
    d.mkdir(parents=True, exist_ok=True)
    p_orig = d / ("%s_orig.jsonl" % a.tag)
    p_swap = d / ("%s_swap.jsonl" % a.tag)
    p_swp = d / ("%s_orig.swap.jsonl" % a.tag)
    anchor = TG.CKF_ANCHOR

    if not a.skip_run:
        base = [sys.executable, "runner2.py", "--topics-file", "topics_gaokao",
                "--api", a.api, "--model", a.model, "--workers", a.workers,
                "--samples", samples, "--arms", a.arms]
        run(base + ["--out", str(p_orig), "--ckf-anchor", anchor,
                    "--max-calls", "200"], "① 原版（锚点=%s）" % anchor)
        run(base + ["--out", str(p_swap), "--ckf-anchor", anchor,
                    "--ckf-swap", TG.CKF_SWAP, "--max-calls", "200"],
            "② 换值版（%s → %s）" % (anchor, TG.CKF_SWAP))
        run([sys.executable, "probe_swap.py", str(p_orig), "--arms", "C1,C2,S",
             "--out", str(p_swp), "--workers", a.workers, "--max-calls", "60"],
            "③ D-2 状态历史置换探针")

    # ---------------- 产出（只给产出，不做评价） ----------------
    import report_outputs as RO
    return _emit_outputs(p_orig, a, anchor)




if __name__ == "__main__":
    sys.exit(main())
