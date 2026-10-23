import json, os, sys, statistics
sys.path.insert(0, "/workspace/lab/routes/COLLAPSE")
import space as SP

BASE = "/workspace/lab/routes/COLLAPSE/runs"

def load(path):
    out = []
    if not os.path.exists(path):
        return out
    for l in open(path, encoding="utf-8"):
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out

rows = load(os.path.join(BASE, "main_big", "arms.jsonl"))
# ★ frames_vote 用**修好投票后**的那批（fv2）替换旧读数
fv_fixed = load(os.path.join(BASE, "fv2", "arms.jsonl"))
key = lambda d: (d.get("task_id"), d.get("rep"), d.get("arm"))
old = {key(d): d for d in rows}
new = {key(d): d for d in fv_fixed}
replaced = [k for k in new if k[2] == "B0_frames_vote"]
merged = []
for d in rows:
    k = key(d)
    merged.append(new.get(k, d) if k in new else d)
for k in replaced:
    if not any(key(d) == k for d in rows):
        merged.append(new[k])
print("合并：主批次 %d 臂 + 修复投票 %d 臂（替换 %d 条）"
      % (len(rows), len(fv_fixed), len(replaced)))
print("code_version =", (merged[0].get("code_version") if merged else "—"))

print("\n【A】逐臂（判官读数 + n_cards + 零判官空间指标）")
hdr = "  %-4s %-3s %-16s %5s %6s %8s %10s %7s"
print(hdr % ("题", "rep", "臂", "维度", "承重卡", "n_cards", "路径间Sim", "帧覆盖"))
agg = {}
for d in sorted(merged, key=lambda x: (x.get("task_id") or "", x.get("rep") or 0, x.get("arm") or "")):
    r = SP.space_report(d); pd = r["path_diversity"]
    sim = pd.get("pair_self_sim")
    print(hdr % (d.get("task_id"), d.get("rep"), d.get("arm"), d.get("n_dims"),
                 d.get("n_load_bearing"), d.get("n_cards"),
                 ("%.3f" % sim) if sim is not None else "—",
                 r["frame_coverage"].get("n_distinct")))
    agg.setdefault(d.get("arm"), []).append((d.get("n_dims"), sim))

print("\n【B】逐臂汇总（承重维度：题内中位；路径间Sim：全体中位）")
print("  %-16s %10s %12s %8s" % ("臂", "维度中位", "路径间Sim", "份数"))
for a, v in agg.items():
    dims = [x[0] for x in v if x[0] is not None]
    sims = [x[1] for x in v if x[1] is not None]
    print("  %-16s %10.2f %12s %8d" % (
        a, statistics.median(dims) if dims else 0,
        ("%.3f" % statistics.median(sims)) if sims else "—", len(v)))

print("\n【C】★ 关键对照：搜索空间拓展（路径间Sim 越低越宽）")
for a in ("B0_direct", "B0_bestof3", "B0_frames_vote", "W_design_L2", "W_train_L3"):
    if a not in agg:
        continue
    v = agg[a]
    dims = [x[0] for x in v if x[0] is not None]
    sims = [x[1] for x in v if x[1] is not None]
    print("  %-16s 维度中位=%5.2f  路径间Sim=%s" % (
        a, statistics.median(dims) if dims else 0,
        ("%.3f" % statistics.median(sims)) if sims else "—（单分支）"))
