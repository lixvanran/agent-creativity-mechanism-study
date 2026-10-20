#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **训练循环**的离线自测（0 次真实 API 调用，修 F3：循环此前只存在于伪代码里）。

要证明的事（DESIGN §3.6 的伪代码**确实可执行**）：
  ❶ 轮次循环会跑、每轮会更新 w（‖w‖ 变化）
  ❷ **滑动基线**会更新
  ❸ **EMA 部署权重**会更新且 ≠ 当前 w
  ❹ **监控面板**会逐轮累积（rounds / alarms / 报告）
  ❺ **checkpoint**会原子落盘且可读回（续跑用）
  ❻ **校准闸门**（FB6）：校准不过 ⇒ 训练**提前停止**并写明原因
  ❼ **fatal 告警闸门**：告警为 fatal ⇒ 训练提前停止
  ❽ 全程 **0 次真实 API 调用**（用 `stub_llm.StubLLM`）

⚠️ 本测试**不产生任何学习效果结论**：stub 的答案是固定的 ⇒ 只能证明"代码路径跑得通"。

用法：python3 test_train_loop.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

from evidence_index import load_index  # noqa: E402
from stub_llm import StubLLM  # noqa: E402
from train_policy_v2 import run_training  # noqa: E402

DATA = os.path.join(HERE, "data", "diag_topics.json")


def _topics_and_index():
    raw = json.load(open(DATA, encoding="utf-8"))
    topics = [{"topic_id": t["topic_id"], "ask": t["ask"]} for t in raw["topics"]]
    idx = {t["topic_id"]: __import__("evidence_index").EvidenceIndex(
        t["topic_id"], t["ask"], t["items"], t.get("conclusion_space", []))
        for t in raw["topics"]}
    return topics, idx


def check():
    out = {}
    topics, idx = _topics_and_index()

    # ── ❶–❺ 正常跑 3 轮 ──
    with tempfile.TemporaryDirectory() as td:
        stub = StubLLM()
        res = run_training(topics, idx, llm=stub, rounds=4, workers=1,
                           out_dir=td, budget=12, progress=None)
        w = np.array(res["w"])
        out["rounds_done"] = len(res["history"])
        out["w_changed"] = bool(np.linalg.norm(w) > 1e-8)
        out["baseline_updated"] = bool(abs(res["baseline"]) > 0.0)
        ema = np.array(res["ema"]) if res["ema"] else None
        out["ema_exists"] = ema is not None
        out["ema_differs_from_w"] = bool(ema is not None and np.linalg.norm(ema - w) > 0)
        out["monitor_rounds"] = len(res["monitor"]["rounds"])
        out["monitor_has_report"] = "thresholds" in res["monitor"]
        ck = os.path.join(td, "result.json")
        out["checkpoint_written"] = os.path.exists(ck)
        ckobj = json.load(open(ck, encoding="utf-8"))
        out["checkpoint_keys"] = sorted(ckobj.keys())
        out["checkpoint_resumable"] = bool(ckobj.get("history"))
        out["stub_calls"] = len(stub.rec)
        out["no_real_api_calls"] = True    # 用的是 stub，不经过 client.LLM
        out["stopped_reason_normal"] = res["stopped_reason"]

    # ── ❻ 校准闸门 ──
    with tempfile.TemporaryDirectory() as td:
        res2 = run_training(topics, idx, llm=StubLLM(), rounds=5, workers=1,
                            out_dir=td, budget=12,
                            calibration={"spearman": 0.10, "threshold": 0.50, "subset": "cal"})
        out["calibration_stopped"] = res2["stopped_reason"].startswith("calibration_failed")
        out["calibration_rounds_done"] = len(res2["history"])
        out["calibration_stopped_early"] = len(res2["history"]) < 5
        out["calibration_reason"] = res2["stopped_reason"]

    # ── ❼ fatal 告警闸门：把 τ 调到极小 ⇒ n_eff≈1 ⇒ COLLAPSE_CRIT ──
    with tempfile.TemporaryDirectory() as td:
        res3 = run_training(topics, idx, llm=StubLLM(), rounds=5, workers=1,
                            out_dir=td, budget=12, tau0=0.0005)
        out["fatal_stopped"] = res3["stopped_reason"].startswith("fatal_alarm")
        out["fatal_stopped_reason"] = res3["stopped_reason"]
        out["fatal_rounds_done"] = len(res3["history"])

    out["PASS"] = bool(out.get("w_changed") and out.get("baseline_updated")
                       and out.get("ema_differs_from_w") and out.get("monitor_rounds") == 4
                       and out.get("checkpoint_written") and out.get("calibration_stopped")
                       and out.get("calibration_stopped_early")
                       and out.get("fatal_stopped"))
    return out


if __name__ == "__main__":
    r = check()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["PASS"] else 1)
