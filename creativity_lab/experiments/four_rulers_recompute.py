#!/usr/bin/env python3
"""★ **四把尺子在已有数据上并排重算**（★ 严格零 API 调用）

> 落点：`creativity_lab/experiments/four_rulers_recompute.py`
> 输出：`runs/four-rulers-2026-10-24/four_rulers.json`
> 触发：负责人审查回执 ① —— 「四把尺子在已有数据上零成本并排重算，把『分歧来源可指认』写成独立一节」
>
> ## ★★ 什么叫"零成本"（★ 严格版）
> - `Vendi` / `modes` / `self_bleu` / `distinct_2` ⇒ ★ **直接读 manifest 里已缓存的读数** ⇒ **不重新 embed**
> - `structured_dedup` ⇒ ★ **零 embedding / 零阈值 / 零聚类** ⇒ 新算也不花钱
> - ⇒ ⇒ **全程 0 次 API 调用**
>
> ## ★★ 要报的东西
> ① 四把尺子并排（family_key 留作**第五把·待补**，需判官额度）
> ② ★ **分歧来源可指认**：哪几把同向、哪几把反向；打平的那两把**各自测的是什么维度**
> ③ ★ **换分组口径后的浮动范围**（负责人新加的通则：倍数型读数必须报这个）
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.metrics_ext import structured_dedup_count  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = [("tot", "runs/tot-arm-2026-10-24"),
        ("adhd", "runs/tot-arm-adhd-2026-10-24")]
OUT = os.path.join(ROOT, "runs", "four-rulers-2026-10-24", "four_rulers.json")


def main() -> int:
    rows = []
    for tag, rel in RUNS:
        d = os.path.join(ROOT, rel)
        if not os.path.isdir(d):
            print("(缺) %s" % rel)
            continue
        mf = os.path.join(d, "manifest.json")
        if not os.path.exists(mf):
            continue
        m = json.load(open(mf, encoding="utf-8"))
        for g in m.get("groups", []):
            for arm, a in (g.get("arms") or {}).items():
                arts = a.get("arts") or []
                if len(arts) < 2:
                    continue
                r = a.get("read") or {}
                sd = structured_dedup_count(arts)          # ★ 零 embedding ⇒ 新算也免费
                rows.append(dict(
                    batch=tag, tid=g["tid"], rep=g["rep"], arm=arm,
                    n=len(arts), n_expected=a.get("n_expected"),
                    vendi=r.get("vendi"), modes=r.get("modes"),
                    self_bleu=r.get("self_bleu"), distinct_2=r.get("distinct_2"),
                    structured_dedup=sd,
                    effective_rank=r.get("effective_rank"),
                ))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"rows": rows, "n_calls_api": 0}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)

    print("== 四把尺子并排（★ 0 次 API 调用）==")
    print("%-6s %-4s %-3s %-12s %-9s %-6s %-9s %-9s %-8s" %
          ("批次", "题", "rep", "臂", "n", "Vendi", "modes", "selfBLEU", "去重"))
    for r in rows:
        print("%-6s %-4s r%-2d %-12s %-9s %-6.3f %-9s %-9.3f %-8s" %
              (r["batch"], r["tid"], r["rep"], r["arm"], "%d/%s" % (r["n"], r["n_expected"]),
               r["vendi"] if r["vendi"] is not None else -1,
               r["modes"], r["self_bleu"] if r["self_bleu"] is not None else -1,
               r["structured_dedup"]))

    # ── ③ 换分组口径后的浮动范围（倍数型读数）──
    print()
    print("== ★ 倍数型读数：换分组口径后的浮动范围（新通则）==")
    for batch in ("tot", "adhd"):
        sel = [r for r in rows if r["batch"] == batch and r["n"] and r["vendi"]]
        if len(sel) < 2:
            continue
        # 口径 A：按臂内读数的中位；口径 B：按题内读数的中位
        by_arm = {}
        by_tid = {}
        for r in sel:
            by_arm.setdefault(r["arm"], []).append(r["vendi"])
            by_tid.setdefault(r["tid"], []).append(r["vendi"])
        import statistics
        ma = statistics.median([statistics.median(v) for v in by_arm.values()])
        mt = statistics.median([statistics.median(v) for v in by_tid.values()])
        print("  %-6s 按臂中位=%.3f ｜ 按题中位=%.3f ｜ ★ 换口径浮动 %+.1f%%"
              % (batch, ma, mt, (mt - ma) / ma * 100 if ma else 0))

    # ── ② 分歧来源可指认 ──
    print()
    print("== ★ 分歧来源：ADHD@同n vs ToT@同n，四把尺子各说各的什么 ==")
    print("  （详细判决见报告结论 2.20b；此处只列各尺子的【测量维度】）")
    for k, v in (("Vendi", "谱熵 / 有效模态数（结构层）"),
                 ("modes", "embedding + 阈值聚类的簇数（结构层，对改写敏感）"),
                 ("structured_dedup", "词面近似去重数（词面层，对改写最敏感）"),
                 ("self_bleu", "两两 n-gram 重复度（措辞层，★ 不是『多样』）")):
        print("   %-18s → %s" % (k, v))
    print("  family_key          → ★ 语义级（判官 + 题级结论空间）⇒ ★ 第五把·待补（需额度）")
    print()
    print("✔ 落盘：%s（%d 行）" % (OUT, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
