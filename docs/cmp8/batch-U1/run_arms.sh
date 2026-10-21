#!/bin/bash
cd /workspace/lab/batch-U1
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY}"
export MINIMAX_SUBSCRIPTION_KEY="${MINIMAX_SUBSCRIPTION_KEY}"
export OR_BASE_URL="https://openrouter.ai/api/v1"
export OR_MODEL="x-ai/grok-4.3"
export MM_MODEL="MiniMax-M3.1-Flash-Preview"
exec python3 -u run_arms.py
