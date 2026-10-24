#!/usr/bin/env python3
"""**模型可用性探测**（结果缓存到 `runs/model_probe.json`）。

> 2026-10-23 ｜ 为什么需要：分支档位里有**已下架**的型号（`MiniMax-M2.1` 实测 404）
> ⇒ 发散层**静默从 5 支变 4 支** ⇒ 分母被改、指标被污染，而表���看不出来。
> ⇒ 纪律：**失败路径不许静默归零** ⇒ 型号可用性必须**先探测、显式记录**。
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.client import MODELS, LLM  # noqa: E402

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "runs", "model_probe.json")


def probe(force: bool = False) -> dict:
    if os.path.exists(CACHE) and not force:
        try:
            d = json.load(open(CACHE, encoding="utf-8"))
            if d.get("models"):
                return d
        except Exception:                      # noqa: BLE001
            pass
    llm = LLM()
    res = {}
    for m in MODELS:
        t0 = time.time()
        txt = llm.chat("回复一个字：好", model=m, max_tokens=200, budgets=(),
                       purpose="probe_model", effort="low")
        res[m] = {"alive": bool(txt.strip()), "secs": round(time.time() - t0, 1)}
        print("  %-30s %s (%.1fs)" % (m, "ALIVE" if res[m]["alive"] else "**DEAD**",
                                      res[m]["secs"]), flush=True)
    out = {"models": res, "alive": [m for m, v in res.items() if v["alive"]],
           "dead": [m for m, v in res.items() if not v["alive"]],
           "probed_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True)
    return out


if __name__ == "__main__":
    d = probe(force="--force" in sys.argv)
    print("\n可用：%s\n下架：%s" % (d["alive"], d["dead"]))
