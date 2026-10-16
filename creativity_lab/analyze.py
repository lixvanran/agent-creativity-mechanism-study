"""分析。**只读 runs 目录里的真实产出与调用日志。**"""
from __future__ import annotations
import glob, json, os
from collections import defaultdict
from creativity_lab.client import LLM
from creativity_lab import metrics as M

LABEL = {"direct": "直接调用", "dual_fuse": "双轴+融合门", "dual_select": "双轴+只选不融"}


def load_run(run: str):
    out = {}
    for f in glob.glob(os.path.join(run, "*_arm*.md")) + glob.glob(os.path.join(run, "*_*.md")):
        b = os.path.basename(f)[:-3]
        parts = b.split("_")
        if len(parts) < 3 or not parts[-1]: continue
        tid, rep, arm = parts[0], parts[1], "_".join(parts[2:])
        if not rep.startswith("r"): continue
        t = open(f, encoding="utf-8").read().strip()
        if t: out[(tid, int(rep[1:]), arm)] = t
    return out


def analyze(run: str):
    R = load_run(run)
    if not R: print("没有可分析的产出"); return
    llm = LLM()
    arms = sorted({a for (_, _, a) in R})
    tids = sorted({t for (t, _, _) in R})
    reps = sorted({r for (_, r, _) in R})

    print("=" * 86)
    print(f"分析 {run}  |  {len(R)} 份产出  |  题 {tids}  |  臂 {arms}  |  重复 {reps}")
    print("=" * 86)

    # 1) 可靠性（来自调用日志，不是 arm 自述）
    lg = os.path.join(run, "_calllog.jsonl")
    if os.path.exists(lg):
        print("\n[1] 调用可靠性（审计只认日志）")
        agg = defaultdict(lambda: [0, 0, 0])
        for line in open(lg, encoding="utf-8"):
            d = json.loads(line)
            a = agg[d["arm"]]; a[0] += 1; a[1] += d["calls_ok"]; a[2] += d["calls"]
        for arm, (n, ok, tot) in agg.items():
            print(f"    {LABEL.get(arm, arm):<16} 单元 {n:>3}  调用成功 {ok}/{tot}"
                  f"  ({100*ok/max(tot,1):.0f}%)")

    # 2) 逃逸度：参照系 = 同题 direct 的多次真实产出
    print("\n[2] 逃逸度（参照系 = 同题 direct 的多次真实产出）")
    for t in tids:
        ref = [llm.embed([R[(t, r, "direct")]])[0] for r in reps if (t, r, "direct") in R]
        if not ref: continue
        line = f"    {t:<4}"
        for a in arms:
            if a == "direct": continue
            cs = [llm.embed([R[(t, r, a)]])[0] for r in reps if (t, r, a) in R]
            if cs: line += f"  {LABEL.get(a,a)}={M.escape(cs, ref):.4f}"
        print(line)

    # 3) 跨重复离散度
    print("\n[3] 跨重复离散度（同臂多次两两相似度，越低=越不重复）")
    for t in tids:
        for a in arms:
            cs = [llm.embed([R[(t, r, a)]])[0] for r in reps if (t, r, a) in R]
            if len(cs) >= 2:
                print(f"    {t:<4} {LABEL.get(a,a):<16} {M.dispersion(cs):.4f}")

    # 4) 批内结构（仅双轴臂：分支池）
    print("\n[4] 批内结构")
    for t in tids:
        for a in arms:
            if not a.startswith("dual"): continue
            cs = [llm.embed([R[(t, r, a)]])[0] for r in reps if (t, r, a) in R]
            if cs:
                print(f"    {t:<4} {LABEL.get(a,a):<16} PR={M.effective_rank(cs):.2f} "
                      f"模态数={M.modes(cs):.0f}/{len(cs)}")
