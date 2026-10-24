#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 pilot 数据估计"题内抽样噪声 σ"，并给出采样数 N 的检出力曲线。

σ 的定义：单条产出在**极性轴 v** 上的投影的题内标准差。
  SE(δ̂) = σ·√(2/N)      （P+ 与 P− 各 N 个样本）
v 由该题的 P+ / P− 产出均值差得到（与 analyze.py 的口径一致）。

用法：python3 _pilot_sigma.py [--runs runs/pilot.jsonl] [--n-topics 5]
"""
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze  # noqa: E402
import runner  # noqa: E402


def main() -> int:
    runs = HERE / "runs"
    path = runs / "pilot.jsonl"
    gens, stances = analyze.load_records(runs)
    if not gens:
        print("pilot 无数据")
        return 1
    print("pilot 记录：%d 条（%s）" % (len(gens), path.name))
    emb = analyze.embed_all(gens, runs / "embeddings.json")
    print("embedding：%d 条" % len(emb))

    # 按臂/极性分组，算投影
    by = {}
    for f in gens:
        v = emb.get("%s|%s|%s|%s" % (f.get("arm"), f.get("topic_id"), f.get("seed"),
                                     f.get("polarity")))
        if not v:
            continue
        by.setdefault((f.get("arm"), f.get("polarity")), []).append(v)
    topics = sorted({f.get("topic_id") for f in gens})
    print("题：%s" % topics)

    rows = []
    for tid in topics:
        sub = [f for f in gens if f.get("topic_id") == tid]
        ep = [emb.get("%s|%s|%s|%s" % (f.get("arm"), f.get("topic_id"), f.get("seed"), "P+"))
              for f in sub if f.get("polarity") == "P+"]
        en = [emb.get("%s|%s|%s|%s" % (f.get("arm"), f.get("topic_id"), f.get("seed"), "P-"))
              for f in sub if f.get("polarity") == "P-"]
        ep = [x for x in ep if x]
        en = [x for x in en if x]
        if not ep or not en:
            continue
        v = analyze.vnorm(analyze.vsub(analyze.vmean(ep), analyze.vmean(en)))
        for arm in sorted({f.get("arm") for f in sub}):
            for pol in ("P0", "P+", "P-"):
                vs = [emb.get("%s|%s|%s|%s" % (f.get("arm"), f.get("topic_id"), f.get("seed"), pol))
                      for f in sub if f.get("arm") == arm and f.get("polarity") == pol]
                vs = [x for x in vs if x]
                if len(vs) < 2:
                    continue
                proj = [analyze.cos(x, v) for x in vs]
                rows.append({"tid": tid, "arm": arm, "pol": pol, "n": len(vs),
                             "mean": sum(proj) / len(proj),
                             "sd": statistics.pstdev(proj) if len(proj) > 1 else 0.0})
    print("\n各组在极性轴上的投影：")
    for r in rows:
        print("  %s %s %s n=%d mean=%+.4f sd=%.4f" % (r["tid"], r["arm"], r["pol"], r["n"],
                                                     r["mean"], r["sd"]))
    sds = [r["sd"] for r in rows if r["sd"] > 0]
    sigma = statistics.pstdev(sds) if sds else 0.0
    # 更保守：取各组 sd 的最大值
    sigma_max = max(sds) if sds else 0.0
    print("\nσ（各组 sd 的均方根）= %.5f ；σ（各组 sd 的最大值，保守）= %.5f" % (sigma, sigma_max))
    for sd in (sigma, sigma_max):
        print("\n── 检出力曲线（sd=%.5f）" % sd)
        for n_topics in (5, 10):
            for shift in (0.02, 0.05, 0.10):
                curve = analyze.power_curve(sd, n_topics, shift)
                need = next((r["N"] for r in curve if r["power"] >= 0.8), None)
                print("  n_topics=%2d  shift=%.2f  →  达到 80%% 检出力所需 N = %s"
                      % (n_topics, shift, need if need else ">20"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
