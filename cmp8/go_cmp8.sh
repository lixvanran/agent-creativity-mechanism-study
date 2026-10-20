#!/bin/bash
# 对比实验编排：冒烟 → 跑批 → 跨厂商判官核验 → 判读页
cd "$(dirname "$0")"
export PRIMARY_MODEL="${PRIMARY_MODEL:-MiniMax-M3.1-Flash-Preview}"
export OR_PRIMARY="${OR_PRIMARY:-deepseek/deepseek-chat}"
export OR_BASE_URL="${OR_BASE_URL:-https://openrouter.ai/api/v1}"
export OR_EMBED="${OR_EMBED:-qwen/qwen3-embedding-8b}"
export CMP_OUT="${CMP_OUT:-runs/cmp8}"
export ADH_MODE="${ADH_MODE:-repro}"
mkdir -p "$CMP_OUT"

echo "===== 0. 冒烟 ====="
python3 smoke_or.py || { echo "冒烟未过，不开跑"; exit 1; }

echo "===== 1. 跑批（7 臂 × 4 题 × 3 重复）====="
python3 run_compare5.py --arms A1,A2,A3,A4,A5a,A5b,A5c --reps 3 --workers 4

echo "===== 2. 跨厂商判官核验 ====="
python3 analyze_cmp6.py

echo "===== 3. 判读页 ====="
python3 build_compare5_page.py

echo "===== 完成 ====="
echo "对比表在 $CMP_OUT/analysis.json ；判读页在 $CMP_OUT/compare5_report.html"
