#!/bin/bash
# 训练实时看板（只读，不干扰训练进程）
cd /workspace/lab/cmp8repo || exit 1
D=runs/arch_learn_fixed
echo "════ 训练实时看板  $(date '+%F %T') ════"
N=$(pgrep -f "creativity_lab/train_policy.py" | wc -l | tr -d ' ')
echo "进程: $N 个   线程: $([ -n "$N" ] && ls /proc/$(pgrep -f 'creativity_lab/train_policy.py' | head -1)/task 2>/dev/null | wc -l || echo 0)"
python3 - <<'PY'
import json, os
p = "runs/arch_learn_fixed/result.json"
if os.path.exists(p):
    d = json.load(open(p))
    h = d.get("history", []); w = d.get("w", [])
    print("进度: %d / 8 轮完成   ‖w‖=%.4f" % (len(h), (sum(x*x for x in w) ** 0.5) if w else 0))
    for i, v in enumerate(h, 1):
        print("   轮 %d ‖w‖=%.4f" % (i, (sum(x*x for x in v) ** 0.5)))
else:
    print("进度: 无 checkpoint")
PY
echo "--- 日志（最后 12 行）---"
tail -12 "$D/train.log" 2>/dev/null
