#!/bin/bash
cd /workspace/lab/batch-U1
export MINIMAX_SUBSCRIPTION_KEY="${MINIMAX_SUBSCRIPTION_KEY}"
export MM_BASE_URL="https://api.minimaxi.com/v1"
export MM_MODEL="MiniMax-M3.1-Flash-Preview"
exec python3 -u measure.py
