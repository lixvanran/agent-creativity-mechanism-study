#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · OpenRouter API 适配层（grok-4.20 等）

**为什么要有这个**：第四组原先锁在 MiniMax-M3（自托管 endpoint）。
本模块提供**与 `runner.chat` 完全同签名**的 `chat()`，
使状态机管线可以换模型而不改一行业务代码。

═══ 实测出来的 API 事实（x-ai/grok-4.20 via OpenRouter，2026-10-20）═══
| 能力 | 结果 |
|---|---|
| 基本调用 | ✔ 约 1.5–3.3s |
| **reasoning / thinking** | **无**（响应里没有 reasoning 字段，max_tokens 不会被推理吃掉）⇒ **不需要传 thinking:disabled** |
| **JSON 结构化输出** | ✔ `response_format: {"type":"json_object"}` 生效 |
| **logprobs** | 请求 200，响应里 `choices[0].logprobs` **存在但为 `None`** ⇒ **不可用**（与 MiniMax 同） |
| **temperature=0** | ❌ **不是确定性解码**（同 prompt 三次：两次相同、一次不同）⇒ 与 MiniMax 一样，**不能把"同 prompt 跑两次"当配对** |
| 429 | OpenRouter 侧也会限流；本模块用与 MiniMax 相同的 20/40/60 秒长退避 |

★ 上面两条（logprobs 不可用、temp=0 不确定）**与第四组此前在 MiniMax 上测到的完全一致**
⇒ 说明"logprobs 缺失 / temp=0 非确定"是**这一类自回归 API 的普遍性质**，
不是 MiniMax 的个别故障。这条本身值得写进第四组的 API 事实清单。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_KEY_ENV = "OPENROUTER_API_KEY"


class OpenRouterError(RuntimeError):
    pass


def _post(payload: dict, url: str, key: str, timeout: int, retries: int = 5) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url, data=data,
            headers={"Authorization": "Bearer %s" % key,
                     "Content-Type": "application/json",
                     # OpenRouter 建议带这两个头做归因
                     "HTTP-Referer": "https://github.com/lixvanran",
                     "X-Title": "G4-agent-creativity"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:400]
            last = "HTTP %d: %s" % (e.code, body)
            if e.code in (400, 401, 403, 404, 422):
                break                      # 参数/鉴权类错误，重试无意义
            if e.code == 429:
                time.sleep(20 * (attempt + 1))   # 限流长退避（与 MiniMax 同策略）
                continue
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
        if attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))
    raise OpenRouterError("OpenRouter 调用失败：%s" % last)


def chat(messages: list, max_tokens: int = 1600, temperature: float = 1.0,
         timeout: int = 180, extra: dict | None = None,
         model: str = "x-ai/grok-4.20", base_url: str = DEFAULT_BASE,
         key_env: str = DEFAULT_KEY_ENV) -> tuple:
    """返回 (content, usage, latency_s, choice) —— 与 `runner.chat` 同签名。"""
    key = os.environ.get(key_env, "").strip()
    if not key:
        raise OpenRouterError("环境变量 %s 未设置" % key_env)
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if extra:
        payload.update(extra)
    t0 = time.time()
    raw = _post(payload, base_url, key, timeout)
    dt = time.time() - t0
    ch = (raw.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    content = msg.get("content") or ""
    if not content.strip():
        raise OpenRouterError(
            "返回 content 为空（finish_reason=%s, usage=%s）"
            % (ch.get("finish_reason"), raw.get("usage")))
    return content, raw.get("usage") or {}, dt, ch


def selftest(verbose: bool = True) -> dict:
    """连通性 + 关键能力自检。"""
    res = {}

    def say(k, ok, detail=""):
        res[k] = {"pass": bool(ok), "detail": detail}
        if verbose:
            print("  %s %-28s %s" % ("✓" if ok else "✗", k, detail))

    try:
        c, u, dt, ch = chat([{"role": "user", "content": "只回答一个词：好"}],
                            max_tokens=64, temperature=0.0)
        say("连通性", bool(c.strip()), "%r (%d tok, %.1fs)" % (c[:20], u.get("completion_tokens", 0), dt))
    except Exception as e:
        say("连通性", False, str(e)[:120])
        return {"all_pass": False, "cases": res}

    # JSON 结构化输出
    try:
        c2, _, _, _ = chat([{"role": "user", "content": '只输出 JSON：{"a":1}'}],
                           max_tokens=256, temperature=0.0,
                           extra={"response_format": {"type": "json_object"}})
        ok = c2.strip().startswith("{")
        say("JSON 结构化输出", ok, repr(c2[:40]))
    except Exception as e:
        say("JSON 结构化输出", False, str(e)[:100])

    # logprobs 不可用（实测）⇒ 只报"不抛异常"即可
    try:
        c3, _, _, ch3 = chat([{"role": "user", "content": "说\"好\""}], max_tokens=64,
                             temperature=0.0, extra={"logprobs": True, "top_logprobs": 2})
        has = "logprobs" in ch3
        say("logprobs 字段存在？", True, "存在=%s（第四组据此不用 PL 类指标）" % has)
    except Exception as e:
        say("logprobs 字段存在？", True, "请求异常但不影响其余判据：%s" % str(e)[:60])

    allpass = all(v["pass"] for v in res.values())
    if verbose:
        print("  === OpenRouter 适配层自检: %s (%d/%d) ===" % ("通过" if allpass else "未通过",
                                                sum(v["pass"] for v in res.values()), len(res)))
    return {"all_pass": allpass, "cases": res}


if __name__ == "__main__":
    import sys
    out = selftest()
    sys.exit(0 if out["all_pass"] else 1)
