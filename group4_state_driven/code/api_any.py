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
#: 每次调用的流水（供成本与审计）
TRACE: list = []

#: ★★ 完整调用日志（**含失败调用**）—— 通道健康度的正确分母。
#: 一条记录 = 一次**逻辑调用**（内部重试折叠在 attempts/errors 里）。
#: ⚠️ TRACE 只在成功时 append ⇒ 失败调用完全没进账 ⇒ 健康度会被高估
#:    （"失败漏记"是"静默归零"里最隐蔽的形态：分母变小，看起来像"通道天生不好"）。
CALL_LOG: list = []


SOCKET_TIMEOUT = 90   # ★ 单次调用硬上限（实测：某次调用挂住 30 分钟未超时）


def _post(url: str, key: str, payload: dict, timeout: int = 90, retries: int = 3,
          meta: dict | None = None) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last = None
    attempts = 0
    errors: list = []
    t0 = time.time()
    for attempt in range(retries):
        attempts += 1
        req = urllib.request.Request(
            url, data=data,
            headers={"Authorization": "Bearer %s" % key,
                     "Content-Type": "application/json",
                     "HTTP-Referer": "https://github.com/lixvanran",
                     "X-Title": "G4-agent-creativity"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                _c = (raw.get("choices") or [{}])[0]
                CALL_LOG.append({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "url": url, "model": (meta or {}).get("model") or payload.get("model"),
                    "base_url": (meta or {}).get("base_url"),
                    "kind": (meta or {}).get("kind"),
                    "prompt_chars": len(str(payload.get("messages") or "")),
                    "max_tokens": payload.get("max_tokens"),
                    "attempts": attempts, "errors": list(errors), "ok": True,
                    "latency": round(time.time() - t0, 2),
                    "finish_reason": _c.get("finish_reason"),
                    "usage": raw.get("usage"),
                })
                return raw
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            last = "HTTP %d: %s" % (e.code, body)
            errors.append(last)
            if e.code in (400, 401, 403, 404, 422):
                break
            if e.code == 429:
                time.sleep(20 * (attempt + 1))     # MiniMax Token Plan 实测需长退避
                continue
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
            errors.append(last)
        if attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))
    CALL_LOG.append({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "url": url, "model": (meta or {}).get("model") or payload.get("model"),
        "base_url": (meta or {}).get("base_url"),
        "kind": (meta or {}).get("kind"),
        "prompt_chars": len(str(payload.get("messages") or "")),
        "max_tokens": payload.get("max_tokens"),
        "attempts": attempts, "errors": list(errors), "ok": False,
        "latency": round(time.time() - t0, 2),
        "finish_reason": None, "usage": None,
    })
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
        raw = _post(url, key, payload, meta={"model": model, "base_url": base,
                                             "kind": "json" if json_mode else "text"})
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


def dump_calllog(path) -> dict:
    """把 CALL_LOG 落成 jsonl（**含失败调用**）⇒ 事后可独立重算通道健康度。

    返回健康度摘要：attempts（含重试）/ ok / failed / 成功率。
    ⚠️ 分母 = **全部逻辑调用**（失败也在内）⇒ 不用成功数当分母。
    """
    import pathlib as _pl
    p = _pl.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for rec in CALL_LOG:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tot = len(CALL_LOG)
    ok = sum(1 for r in CALL_LOG if r.get("ok"))
    attempts = sum(int(r.get("attempts") or 1) for r in CALL_LOG)
    return {"path": str(p), "calls_logical": tot, "ok": ok, "failed": tot - ok,
            "http_attempts": attempts,
            "success_rate": round(ok / tot, 4) if tot else None}


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
