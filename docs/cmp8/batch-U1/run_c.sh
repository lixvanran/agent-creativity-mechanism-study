#!/bin/bash
cd /workspace/lab/batch-U1
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY}"
export MINIMAX_SUBSCRIPTION_KEY="${MINIMAX_SUBSCRIPTION_KEY}"
export OR_BASE_URL="https://openrouter.ai/api/v1"
export OR_MODEL="x-ai/grok-4.3"
export U1_ONLY_ARMS="C_T2"
export U1_START_REP=2
exec python3 -u run_arms.py
