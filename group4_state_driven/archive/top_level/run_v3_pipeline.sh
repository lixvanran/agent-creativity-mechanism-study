#!/bin/bash
set -u
cd /workspace/第四组论证/experiment-design || exit 1
mkdir -p runs
{
  echo "=== START $(date '+%F %T') ==="
  echo "--- 补跑 WF-a3-NL（同批）---"
  python3 -u run_arch3_compare.py --reps 1,2,3 --arms WF-a3-NL --workers 3 \
      --batch-id arch3-20261021-221648-minimax --append --out runs/arch3_compare.jsonl
  echo "--- 探针（D0 / D2flip_NL / D3off_NL）---"
  python3 -u probe_arch3.py --workers 3
  echo "=== DONE $(date '+%F %T') ==="
} >> runs/arch3_pipeline.log 2>&1
echo "V3_PIPELINE_DONE" >> runs/arch3_pipeline.log
