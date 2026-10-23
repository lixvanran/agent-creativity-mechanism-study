#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 统一传输层（MiniMax 主力 / OpenRouter 备选）

════════════════════════════════════════════════════════════════════════
★ 三个实测出来的 API 事实（2026-10-21 复核，MiniMax-M3）
  1. **纯写作时 thinking 默认开，且 `<think>` 块被塞进 `message.content`**
     ⇒ 正文必须剥 think；`reasoning_content` 字段**不存在**。
  2. **JSON 模式下 content 干净**（无 think），且 `thinking:{type:"disabled"}` 也接受。
  3. `finish_reason=length` ⇒ 截断。★ **必须加预算重试**，不能把截断的 JSON 当结果。

★ 统一约定（保证各臂传输层完全一致 ⇒ 对照公平）
  · `json_mode=True`  → 结构化步：`thinking:{type:"disabled"}`，JSON 直出
  · `json_mode=False` → 创作步：**不传 thinking**（保留模型的推理，它是"驱动力"的一部分）
  · **返回值一律是剥掉 `<think>` 之后的干净文本**
    ⇒ 这样旧实现的 `parse3()` 不用改也能吃干净内容 ⇒ 对照臂仍与旧实现逐字同源。

★ 2026-10-21 00:35 实测：**OpenRouter 全部 401 "User not found"**（所有模型，包括
  /auth/key 与 /credits）⇒ 判官通道不可用 ⇒ 本轮**全零判官**，只跑离散结构量。
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

MINIMAX_BASE = "https://api.minimaxi.com/v1"
MINIMAX_KEY = "MINIMAX_SUBSCRIPTION_KEY"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY = "OPENROUTER_API_KEY"


class APIError(RuntimeError):
    pass


# ---------------------------------------------------------------- think 剥离
_T1 = re.compile(r"<think>.*?</think>", re.S)
_T2 = re.compile(r"^.*?</think>", re.S)


def strip_think(raw: str) -> str:
    return _T2.sub("", _T1.sub("", raw or "")).strip()


def think_unclosed(raw: str) -> bool:
    """`<think>` 开了没闭 ⇒ 大概率被 max_tokens 截断。"""
    s = raw or ""
    return "<think>" in s and "</think>" not in s


# ---------------------------------------------------------------- 底层 POST
def _post(url: str, key: str, payload: dict, timeout: int = 120, retries: int = 3) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url, data=data,
            headers={"Authorization": "Bearer %s" % key,
                     "Content-Type": "application/json",
                     "HTTP-Referer": "https://github.com/lixvanran",
                     "X-Title": "G4-agent-creativity"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            last = "HTTP %d: %s" % (e.code, body)
            if e.code in (400, 401, 403, 404, 422):
                break
            if e.code == 429:
                time.sleep(20 * (attempt + 1))     # MiniMax Token Plan 实测需长退避
                continue
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
        if attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))
    raise APIError("调用失败：%s" % last)


# ---------------------------------------------------------------- 统一 chat
#: 每次调用的流水（供成本与审计）
TRACE: list = []


def chat(messages, model, base=None, key_env=None, max_tokens=4000,
         temperature=1.0, json_mode=False, no_think=False):
    """统一入口，签名与 `run_minimal_compare.chat` 完全一致（便于 monkeypatch）。

    返回**剥掉 think 之后**的干净文本。失败抛 APIError（⇒ 调用方显式标记）。
    """
    base = base or MINIMAX_BASE
    is_mm = "minimaxi" in str(base)
    key_env = key_env or (MINIMAX_KEY if is_mm else OPENROUTER_KEY)
    key = os.environ.get(key_env, "").strip()
    if not key:
        raise APIError("环境变量 %s 未设置" % key_env)

    if is_mm:
        url = MINIMAX_BASE + "/chat/completions"
    else:
        url = OPENROUTER_URL if str(base).endswith("/chat/completions") else str(base).rstrip("/") + "/chat/completions"

    mt = max_tokens
    for attempt in range(3):        # ★ 截断 ⇒ 加预算重试（记忆铁律）
        payload = {"model": model, "messages": messages,
                   "max_tokens": mt, "temperature": temperature}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            if is_mm:
                payload["thinking"] = {"type": "disabled"}
        elif no_think and is_mm:
            # ★ 结构化中间态（自然语言但有格式约束）⇒ 关 thinking
            payload["thinking"] = {"type": "disabled"}
        t0 = time.time()
        raw = _post(url, key, payload)
        dt = time.time() - t0
        ch = (raw.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        content = msg.get("content") or ""
        usage = raw.get("usage") or {}
        fin = ch.get("finish_reason")
        TRACE.append({"model": model, "url_host": url.split("/")[2], "latency": round(dt, 2),
                      "finish": fin, "usage": usage, "json_mode": json_mode,
                      "max_tokens": mt})
        if fin == "length" or (not json_mode and think_unclosed(content)):
            # 截断：加预算重试，**不返回截断内容**
            if attempt < 2:
                mt = int(mt * 1.8)
                time.sleep(1.5)
                continue
            raise APIError("截断且重试用尽（finish=%s, max_tokens=%d）" % (fin, mt))
        if not content.strip():
            raise APIError("content 为空（finish=%s, usage=%s）" % (fin, usage))
        return strip_think(content) if not json_mode else content.strip()

    raise APIError("不可达")


def cost_estimate(trace=None) -> dict:
    """按 OpenRouter 公开价粗估（仅供成本感知，不进结论）。"""
    t = trace if trace is not None else TRACE
    pt = sum((u.get("usage") or {}).get("prompt_tokens", 0) for u in t)
    ct = sum((u.get("usage") or {}).get("completion_tokens", 0) for u in t)
    return {"calls": len(t), "prompt_tokens": pt, "completion_tokens": ct}


if __name__ == "__main__":
    import sys
    ok = True
    for mm in (True, False):
        base = MINIMAX_BASE if mm else OPENROUTER_URL
        model = "MiniMax-M3" if mm else "x-ai/grok-4.20"
        try:
            c = chat([{"role": "user", "content": "只回答：好"}], model, base,
                     max_tokens=64 if mm else 32, temperature=0.0)
            print("  ✓ %-22s %r" % (model, c[:40]))
        except Exception as e:
            ok = False
            print("  ✗ %-22s %s" % (model, str(e)[:120]))
    sys.exit(0 if ok else 1)
