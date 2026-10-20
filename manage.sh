#!/bin/bash
# 训练进程管理：start / stop / status / restart
# ⚠️ 为什么单独写文件：把 pkill/pgrep 的**模式放到脚本内容里**，
#    而不是在调用它的命令行里 ⇒ 调用方的 cmdline 不含模式 ⇒ 不会自匹配、不会自杀。
#    （本项目已经连续 3 次被这个坑打中：pkill -f "watchdog.sh" 杀掉了自己所在的 shell。）
cd /workspace/lab/cmp8repo || exit 1
D=runs/arch_learn_fixed
PAT="creativity_lab/train_policy.py"
WD="bash watchdog.sh"

# 只统计**真正的**进程：排除掉当前脚本自身及其父 shell
count_train() { pgrep -f "$PAT" 2>/dev/null | grep -v "^$$\$" | wc -l | tr -d ' '; }
count_wd()    { pgrep -f "$WD"    2>/dev/null | grep -v "^$$\$" | wc -l | tr -d ' '; }

cmd_start() {
  if [ "$(count_train)" -ge 1 ]; then echo "已经在跑（$(count_train) 个），不重复启动"; return 0; fi
  mkdir -p "$D"
  setsid nohup bash run_retrain.sh > "$D/train.log" 2>&1 < /dev/null &
  disown 2>/dev/null || true
  sleep 12
  n=$(count_train)
  echo "启动后训练进程数 = $n"
  [ "$n" -ge 1 ] || { echo "✘ 启动失败"; tail -5 "$D/train.log"; return 1; }
}

cmd_stop() {
  pkill -9 -f "$PAT" 2>/dev/null
  pkill -9 -f "$WD"  2>/dev/null
  sleep 2
  echo "停止后：训练 $(count_train) 个 / 看门狗 $(count_wd) 个"
}

cmd_status() {
  echo "训练进程数: $(count_train)"
  ps -eo pid,sid,etime,cmd | grep "[t]rain_policy" | grep -v "bash -l -c" | head -5
  echo "看门狗数  : $(count_wd)"
  echo "--- 日志尾部 ---"
  tail -8 "$D/train.log" 2>/dev/null
  echo "--- checkpoint ---"
  python3 - <<'PY'
import json, os
p = "runs/arch_learn_fixed/result.json"
if os.path.exists(p):
    d = json.load(open(p))
    w = d.get("w", [])
    print("  %d 轮 ｜ ‖w‖=%.4f" % (len(d.get("history", [])),
          (sum(x * x for x in w) ** 0.5) if w else 0))
else:
    print("  无")
PY
}

case "$1" in
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  status)  cmd_status ;;
  restart) cmd_stop; sleep 2; cmd_start ;;
  wd)      # 只启动看门狗
    if [ "$(count_wd)" -ge 1 ]; then echo "看门狗已在跑"; else
      setsid nohup bash watchdog.sh > "$D/watchdog.log" 2>&1 < /dev/null &
      disown 2>/dev/null || true
      sleep 2; echo "看门狗启动后数量 = $(count_wd)"
    fi ;;
  *) echo "用法: bash manage.sh {start|stop|status|restart|wd}"; exit 2 ;;
esac
