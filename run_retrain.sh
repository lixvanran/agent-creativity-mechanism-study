#!/bin/bash
cd /workspace/lab/cmp8repo
export OPENROUTER_BASE_URL="https://api.minimaxi.com/v1"
export PRIMARY_MODEL=MiniMax-M3.1-Flash-Preview
export POLICY_ROUNDS=8
export POLICY_WORKERS=5
export POLICY_TAU=1.2
export POLICY_RESUME=1
export POLICY_OUT=runs/arch_learn_fixed
python3 -u creativity_lab/train_policy.py &
echo $! > runs/arch_learn_fixed/train.pid
wait $!
