#!/bin/bash
# ★ 速率采样器：每 30s 记一次三臂行数 + 时间戳 ⇒ 得到【实测速率】（不外推）
D=/workspace/lab/routes/COLLAPSE/runs/holdout13
OUT=$D/rate_samples.tsv
for i in $(seq 1 120); do
  m=$(wc -l < $D/valid_merged13/arms.jsonl 2>/dev/null || echo 0)
  l=$(wc -l < $D/valid_lookup/arms.jsonl 2>/dev/null || echo 0)
  u=$(wc -l < $D/valid_uniform/arms.jsonl 2>/dev/null || echo 0)
  echo -e "$(date +%s)\t$(date +%H:%M:%S)\t$m\t$l\t$u" >> $OUT
  sleep 30
done
