#!/bin/bash
# 第四组 · 架构化实验 · 后台串行跑（主实验 → 置换探针）
#
# ★ 为什么要后台：单次 bash 工具调用约 5 分钟会被打断，而整轮约 12–15 分钟。
# ★ 为什么要 setsid：让子进程进入独立 session ⇒ 父工具调用返回后不被连带杀。
# ★ 日志一律写 workspace（绝不写 /tmp）。
set -u
cd /workspace/第四组论证/experiment-design || exit 1

LOGDIR="runs"
mkdir -p "$LOGDIR"

echo "=== START $(date '+%F %T') ===" > "$LOGDIR/arch_pipeline.log"

{
  echo "--- main experiment ---"
  python3 run_arch_compare.py \
      --reps 1,2,3 \
      --arms A,S,WF-p,WF-a,WF-a-R,WF-a-NO \
      --workers 4 \
      --out runs/arch_compare.jsonl
  echo "MAIN_EXIT=$?"
  echo "--- swap probe ---"
  python3 probe_arch.py --workers 3
  echo "PROBE_EXIT=$?"
  echo "=== DONE $(date '+%F %T') ==="
} >> "$LOGDIR/arch_pipeline.log" 2>&1

echo "PIPELINE_DONE" >> "$LOGDIR/arch_pipeline.log"
