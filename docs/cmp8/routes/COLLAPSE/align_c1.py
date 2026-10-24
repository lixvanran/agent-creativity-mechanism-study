import json, os, sys, statistics
sys.path.insert(0, "/workspace/lab/routes/COLLAPSE")
import space as SP, metrics_priorart as MP

def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []

FILES = ["/workspace/lab/routes/COLLAPSE/runs/main_big/arms.jsonl",
         "/workspace/lab/routes/COLLAPSE/runs/fv2/arms.jsonl",
         "/workspace/lab/routes/COLLAPSE/runs/adv/arms.jsonl"]

print("══ ★ C1 对齐实验：同一批读数上同时算【两个量】 ══")
print("   量1 = 分支间同质度（路径间 Self-Sim，越低越分散）  ← 我测的")
print("   量2 = 分支的结论族数（模态数，越多越宽）            ← 层2 测的")
print()
agg = {}
for f in FILES:
    for d in load(f):
        paths = [p for p in (d.get("paths") or []) if p.get("claims")]
        if len(paths) < 2:
            continue
        sim = MP.self_sim([list(p["claims"]) for p in paths], mode="bigram") or 0.0
        # ★ 量2：把各分支的断言合并成族，看**分支合起来覆盖多少个不同结论**
        fams = set()
        for p in paths:
            for c in p["claims"]:
                fams.add("|".join(sorted([c])))
        # ★ 各分支**各自**的族数（用来算"分支的模态数"）
        per = [len(set("|".join(sorted([c])) for c in p["claims"])) for p in paths]
        agg.setdefault(d.get("arm"), []).append((sim, len(fams), statistics.mean(per),
                                                 len(paths), d.get("n_dims")))
print("  %-16s %6s %12s %14s %10s %8s" % ("臂", "份数", "量1 同质度", "量2 族数(合)",
                                        "量2 分支均值", "判官维度"))
for a, v in sorted(agg.items(), key=lambda kv: -statistics.mean([x[0] for x in kv[1]])):
    s1 = statistics.mean([x[0] for x in v])
    s2 = statistics.mean([x[1] for x in v])
    s3 = statistics.mean([x[2] for x in v])
    s4 = statistics.mean([x[3] for x in v])
    d4 = statistics.mean([x[4] for x in v if x[4] is not None])
    print("  %-16s %6d %12.3f %14.1f %10.1f %8.2f" % (a, len(v), s1, s2, s3, d4))

print()
print("  ★ 读法：量1 低 = 分支彼此不同（我测的）；量2 高 = 合起来覆盖的结论多（层2 测的）")
print("  ⇒ 若某臂 量1 低但 量2 不高 ⇒ 它把 prior 改掉了，但**没有**拓宽输出面")
print()
print("══ 我方代码是否受影响于「型号池 5→4」下架 ══")
import subprocess
for pat in ("MODELS[", "M2.1", "型号池", "model_pool"):
    r = subprocess.run(["grep", "-rn", pat, "/workspace/lab/routes/COLLAPSE/",
                        "/workspace/lab/batch-U1/"], capture_output=True, text=True)
    hits = [h for h in r.stdout.splitlines() if h.strip()][:3]
    print("  %-12s %d 处 %s" % (pat, len(r.stdout.splitlines()), hits[:1]))
