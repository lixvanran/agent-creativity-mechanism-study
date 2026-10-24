#!/bin/bash
# 看门狗：训练进程死了就从 checkpoint 续跑。
# ⚠️ 检测进程**不能靠 grep cmdline**（会匹配到包含该字符串的父 shell）⇒ 用 pidfile。
cd /workspace/lab/cmp8repo
LOG=runs/arch_learn_fixed/train.log
WD_PID=$(cat runs/arch_learn_fixed/watchdog.pid 2>/dev/null)
while true; do
  TRAIN_PID=$(cat runs/arch_learn_fixed/train.pid 2>/dev/null)
  if [ -n "$TRAIN_PID" ] && kill -0 "$TRAIN_PID" 2>/dev/null; then
    :   # 训练还活着
  else
    echo "[$(date '+%F %T')] 训练进程不在了（pid=${TRAIN_PID:-空}）⇒ 从 checkpoint 续跑" >> "$LOG"
    setsid nohup bash run_retrain.sh >> "$LOG" 2>&1 < /dev/null &
    disown 2>/dev/null || true
    sleep 12
    echo $! > runs/arch_learn_fixed/train.pid
  fi
  sleep 40
done
