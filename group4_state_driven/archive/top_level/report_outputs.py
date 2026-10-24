#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""产出报告：只给产出，不做评价。

★ 纪律：同批可比 ⇒ 报告前先按 batch_id 过滤，**只留一个批次**。
  （resume 跨进程会跨批次 ⇒ 混批数据不可用于比较。）
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

MEAN = {
    "A": "直接调用 LLM（无状态）",
    "C0": "立场档案全文进 system prompt",
    "C1": "取舍驱动的状态机（4 步）",
    "C2": "状态机 + 事实层 + 极性锚 + 已排除选项（4 步）",
    "S": "等调用数中性 4 步管线",
}


def load(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def pick_batch(recs, prefer_has_stance=True):
    """按 batch_id 分组，挑出**作品齐全**且（优先）含档案记录的那一批。"""
    by = {}
    for r in recs:
        by.setdefault(r.get("batch_id"), []).append(r)
    best, best_key = None, None
    for b, v in by.items():
        g = [r for r in v if r.get("kind") == "gen" and not r.get("error")]
        st = [r for r in v if r.get("kind") == "stance"]
        key = (len(st) > 0 if prefer_has_stance else True, len(g))
        if best_key is None or key > best_key:
            best, best_key = b, key
    return best, by.get(best, [])


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "runs" / "gk_orig.jsonl")
    out_path = sys.argv[2] if len(sys.argv) > 2 else str(HERE / "runs" / "gk_outputs.md")
    model = sys.argv[3] if len(sys.argv) > 3 else "x-ai/grok-4.20"
    anchor = sys.argv[4] if len(sys.argv) > 4 else "the importance of"

    recs = load(src)
    batch, kept = pick_batch(recs)
    gens = [r for r in kept if r.get("kind") == "gen" and not r.get("error")]
    arms = sorted({r["arm"] for r in gens},
                  key=lambda a: list(MEAN).index(a) if a in MEAN else 99)
    samples = sorted({r.get("sample") for r in gens})

    L = []
    L.append("# 「你如何看待高考英语作文」· 产出对照")
    L.append("")
    L.append("模型 `%s` ｜ 题 G01 ｜ 每臂 %d 次独立重复 ｜ 批次 `%s`（单批）"
             % (model, len(samples), batch))
    L.append("")
    L.append("| 臂 | 含义 |")
    L.append("|---|---|")
    for a in arms:
        L.append("| **%s** | %s |" % (a, MEAN.get(a, a)))
    L.append("")
    L.append("## 产出清单")
    L.append("")
    L.append("| 臂 | 次数 | 各次字数 | 含锚点 `%s` |" % anchor)
    L.append("|---|---|---|---|")
    for a in arms:
        sub = sorted([r for r in gens if r["arm"] == a], key=lambda r: r.get("sample") or 0)
        if not sub:
            continue
        lens = [len((r.get("text") or "").strip()) for r in sub]
        hit = sum(1 for r in sub
                  if anchor.lower() in (r.get("text") or "").lower())
        L.append("| %s | %d | %s | %d/%d |"
                 % (a, len(sub), " / ".join(str(x) for x in lens), hit, len(sub)))
    L.append("")
    L.append("---")
    L.append("")

    L.append("## 正文")
    L.append("")
    for smp in samples:
        L.append("### 第 %s 次重复" % smp)
        L.append("")
        for a in arms:
            r = next((x for x in gens if x["arm"] == a and x.get("sample") == smp), None)
            if not r:
                continue
            t = (r.get("text") or "").strip()
            L.append("#### %s · %s（%d 字）" % (a, MEAN.get(a, a), len(t)))
            L.append("")
            L.append(t)
            L.append("")
        L.append("---")
        L.append("")

    txt = "\n".join(L)
    Path(out_path).write_text(txt, encoding="utf-8")
    print("[产出] %s（%d 字）" % (out_path, len(txt)))
    print("批次 %s ｜ 作品 %d 篇 ｜ 臂 %s" % (batch, len(gens), ",".join(arms)))


if __name__ == "__main__":
    main()
