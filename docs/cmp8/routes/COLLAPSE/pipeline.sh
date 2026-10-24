#!/bin/bash
# 层3 冲刺链：跑批 → 训练 → 验证
# 2026-10-22 ｜ 目标 2026-10-25 交论文
#
# ★ 三段全部串起来后台跑，中途不用人盯：
#   1) run8  ：B0 / 层2(查表) / 层3(查表)  —— 已在跑（等它结束）
#   2) train ：用**代理奖励**学 36 个可组合动作的策略（零判官成本）
#   3) valid ：用**完整判官**比「学出来的 vs 查表 vs 均匀」⇒ 代理奖励是否迁移
#
# ⚠️ 第 3 段若「学出来的」不优于「查表」⇒ **如实写"代理奖励未迁移 / 学到的策略无贡献"**。
set -u
cd /workspace/lab/routes/COLLAPSE
rm -rf __pycache__
LOG=/workspace/lab/routes/COLLAPSE/pipeline.log
: > "$LOG"

say() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# ── 1) 等 run8 结束
say "阶段1：等待上一批结束…"
while pgrep -f "run_dev.py" >/dev/null 2>&1; do sleep 20; done
say "阶段1 完成"

# ── 1b) 主批次：4 臂（含★等预算对照臂）+ 锚外测量
#    臂：B0_direct（1 次生成）｜B0_bestof3（3 次生成，★等预算）｜W_design_L2｜W_train_L3
say "阶段1b：主批次（2 题 × R=3 × 4 臂，含锚外测量）"
python3 -B -u run_dev.py --tasks 2 --reps 3 --slots 3 --rounds 2 \
        --arms B0_direct,B0_bestof3,W_design_L2,W_train_L3 \
        --out /workspace/lab/routes/COLLAPSE/runs/main >> "$LOG" 2>&1
say "阶段1b 完成（退出码 $?）"

# ── 2) 训练策略
say "阶段2：训练动作策略（代理奖励，8 轮 × 4 样本）"
python3 -B -u train_policy_w.py --tasks 3 --rounds 8 --samples 4 \
        --out /workspace/lab/routes/COLLAPSE/runs/policy_train >> "$LOG" 2>&1
say "阶段2 完成（退出码 $?）"

# ── 3) 验证：学出来的 vs 均匀（**完整判官**）；查表在主批次里
say "阶段3：验证（完整判官，学出来的 vs 均匀）"
python3 -B -u run_dev.py --tasks 2 --reps 2 --slots 3 --rounds 2 \
        --action-mode policy \
        --policy-file /workspace/lab/routes/COLLAPSE/runs/policy_train/policy.json \
        --arms B0_bestof3,W_train_L3 \
        --out /workspace/lab/routes/COLLAPSE/runs/valid_learned >> "$LOG" 2>&1
say "阶段3 完成（退出码 $?）"

say "阶段3b：对照 · 均匀策略（未训练基线）"
python3 -B -u run_dev.py --tasks 2 --reps 2 --slots 3 --rounds 2 \
        --action-mode policy --arms B0_bestof3,W_train_L3 \
        --out /workspace/lab/routes/COLLAPSE/runs/valid_uniform >> "$LOG" 2>&1
say "阶段3b 完成（退出码 $?）"

say "★ 全部完成。读数：runs/{main,valid_learned,valid_uniform}/"
