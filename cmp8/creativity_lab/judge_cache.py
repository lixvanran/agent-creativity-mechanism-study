# -*- coding: utf-8 -*-
"""判官结果缓存（跨"遍1 / 遍2"复用）。

**为什么需要**：遍2 的唯一变量是 **embedding 通道**（`EMBED_PROVIDER=minimax`）
⇒ 判官 verdict 应当**原样复用**，只重算 embedding / 去重 / 宽度。
否则判官成本要付两遍（grok-4.3 是 deepseek 的 4–5 倍）⇒ 会破 $1 成本上限。

**为什么复用是同一个量（不是改口径）**：判官模型、提示词、断言抽取三者在两遍里完全一致；
断言抽取 `extract_claims` **只吃原文、不吃 embedding** ⇒ 两遍的断言集合必须一致。

**键的设计**：
- 样本级键 `臂|题|重复` + 原文 sha1 ⇒ 原文变了自动失效
- verdict 以**断言文本**为键（不是序号）⇒ 对顺序变化也稳

**⚠️ 报告里必须写明**：遍2 复用了遍1 的判官结果（`analysis.json` 的 `judge_reused`）。
否则读报告的人会以为两遍各自独立判了一遍。
"""
from __future__ import annotations

import hashlib
import json
import os
import threading

LOCK = threading.Lock()
_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(os.path.dirname(_HERE), "runs", "judge_cache.json")


def path() -> str:
    return os.environ.get("JUDGE_CACHE") or DEFAULT_PATH


def _h(txt: str) -> str:
    return hashlib.sha1((txt or "").encode("utf-8")).hexdigest()[:16]


def key(arm: str, tid: str, rep: int) -> str:
    return "%s|%s|%s" % (arm, tid, rep)


def load() -> dict:
    p = path()
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save(cache: dict) -> None:
    p = path()
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, p)


def get(cache: dict, arm: str, tid: str, rep: int, txt: str):
    e = cache.get(key(arm, tid, rep))
    if not e or e.get("h") != _h(txt):
        return None
    return e


def put(cache: dict, arm: str, tid: str, rep: int, txt: str, claims: list, verd: dict) -> None:
    cache[key(arm, tid, rep)] = {
        "h": _h(txt),
        "claims": list(claims),
        "verd": {c: verd.get(c) for c in claims},
    }
