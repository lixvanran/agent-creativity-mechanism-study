#!/bin/bash
# 批次监督器 —— 沙箱会杀长跑后台进程 ⇒ 死了自动接上（断点续跑）
# 2026-10-23 ｜ 用法：setsid nohup bash supervise_batch.sh &
set -u
cd /workspace/lab/routes/COLLAPSE
OUT=/workspace/lab/routes/COLLAPSE/runs/main
TASKS=2
REPS=2
ARMS=B0_direct,B0_bestof3,W_design_L2,W_train_L3
LOG=/workspace/lab/routes/COLLAPSE/batch_supervise.log

say() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
: > "$LOG"
mkdir -p "$OUT"

for attempt in $(seq 1 40); do
  # 完成判定：所有 (题,rep,臂) 都在 arms.jsonl 里
  n=$(python3 - <<'PY'
import json, os, itertools
jl = "/workspace/lab/routes/COLLAPSE/runs/main/arms.jsonl"
done = set()
if os.path.exists(jl):
    for ln in open(jl, encoding="utf-8"):
        try:
            d = json.loads(ln)
            done.add((d.get("task_id"), d.get("rep"), d.get("arm")))
        except Exception:
            pass
tasks = ["D01", "D02"]
arms = ["B0_direct", "B0_bestof3", "W_design_L2", "W_train_L3"]
want = {(t, r, a) for t in tasks for r in range(1, 3) for a in arms}
print(len(want & done))
PY
)
  say "尝试 #$attempt：已完成 $n / 16 个臂"
  if [ "$n" -ge 16 ]; then
    say "★ 全部完成 ⇒ 收尾出表"
    python3 -B -u analyze_batch.py --run "$OUT/w_dev_run.json" \
        --json-out "$OUT/analysis.json" >> "$LOG" 2>&1
    break
  fi
  # 跑一轮（内部按 arms.jsonl 跳过已完成的臂）
  python3 -B -u run_dev.py --tasks $TASKS --reps $REPS --slots 3 --rounds 2 \
      --arms "$ARMS" --resume --out "$OUT" >> "$LOG" 2>&1
  rc=$?
  say "一轮结束（退出码 $rc）"
  sleep 8
done
say "监督器结束"
