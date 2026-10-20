"""OpenRouter 客户端：**跨厂商判官**通道。

为什么必须有：之前所有实验里，被测模型（MiniMax）和判官（核验器）同源。
「判据与指标同源模型 ⇒ 判据无效」——判官和被测同厂，容易对同一批错误达成一致。

**成本纪律**：主力生成走 MiniMax 订阅（$0），OpenRouter 只当**判官 + embedding**。
实测预算：判官 ~170 次调用（Grok 3 Mini $0.30/$0.50 每 M）≈ $0.12，embedding ≈ $0.05。

**失败必须分类**：429 限流 → 退避重试**同一模型**（换模型会改掉「模型构成」这个变量）；
529 过载 → 退避，连续过载才降级；402/401 → 立刻停，不要空转烧时间。
"""
from __future__ import annotations
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

BASE = os.environ.get("OR_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
_KEY = os.environ.get("OPENROUTER_API_KEY", "")
# ⚠️ 默认值是 2026-10-20 **实测**能出内容的模型。
#   原来的 "x-ai/grok-3-mini" 已下架（404：xAI 建议改用 grok-4.3）；
#   原来的 embedding 默认 "openai/text-embedding-3-small" 被供应商 ToS 拦（403）。
PRIMARY = os.environ.get("OR_PRIMARY", "deepseek/deepseek-chat")
FALLBACKS = [m for m in ("x-ai/grok-4.3", "qwen/qwen3.7-plus",
                         "meta-llama/llama-3.3-70b-instruct", "z-ai/glm-4.5")
             if m != PRIMARY]
EMBED_MODEL = os.environ.get("OR_EMBED", "qwen/qwen3-embedding-8b")
EMBED_FALLBACKS = ["qwen/qwen3-embedding-4b", "baai/bge-m3",
                   "sentence-transformers/all-minilm-l6-v2"]

_T1 = re.compile(r"<think>.*?</think>", re.S)
_T2 = re.compile(r"^.*?</think>", re.S)


def strip_think(raw: str) -> str:
    return _T2.sub("", _T1.sub("", raw or "")).strip()


class ApiError(Exception):
    def __init__(self, kind: str, msg: str = ""):
        self.kind = kind
        super().__init__("%s: %s" % (kind, msg[:120]))


def classify(status: int, body: str) -> str:
    b = (body or "").lower()
    if status == 429:
        return "rate_limit"
    if status == 402:
        return "credit"
    if status == 404:
        # 模型已下架 / 没有可用 endpoint（实测：grok-3-mini、grok-4-fast、grok-3 全是这个）
        return "gone"
    if status == 403:
        # 供应商 ToS / 区域限制（实测：openai/*、google/gemini-embedding-001、gpt-4o-mini）
        return "forbidden"
    if status == 401:
        return "auth"
    if status >= 500:
        return "overloaded" if ("overloaded" in b or "负载" in b) else "server"
    if "overloaded" in b or "负载" in b:
        return "overloaded"
    if "rate limit" in b or "too many requests" in b or "quota" in b:
        return "rate_limit"
    return "other"


@dataclass
class Call:
    model: str
    purpose: str
    max_tokens: int
    finish_reason: str = ""
    content_len: int = 0
    ok: bool = False
    secs: float = 0.0
    err: str = ""


class LLM:
    """与 creativity_lab.client.LLM **同接口**，可互换注入核验器。"""

    def __init__(self, recorder: list | None = None):
        self.rec = recorder if recorder is not None else []
        self.model_used: dict = {}

    def _post(self, url: str, payload: dict, timeout: int = 240):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + _KEY,
                     "content-type": "application/json",
                     "HTTP-Referer": "https://github.com/lixvanran/agent-creativity-mechanism-study",
                     "X-Title": "creativity-lab"})
        try:
            raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()
            except Exception:
                pass
            raise ApiError(classify(e.code, body), body or str(e))
        except Exception as e:
            raise ApiError("network", str(e))
        if not raw.strip():
            raise ApiError("empty", raw)
        d = json.loads(raw)
        if isinstance(d, dict) and d.get("error"):
            raise ApiError(classify(d.get("code", 0) or 500, json.dumps(d, ensure_ascii=False)),
                           json.dumps(d.get("error"), ensure_ascii=False))
        return d

    def chat(self, prompt: str, *, model: str = "", temp: float = 1.0,
             max_tokens: int = 2000, budgets=(4000, 6000), min_ok: int = 20,
             purpose: str = "") -> str:
        model = model or PRIMARY
        last = ""
        last_err = ""
        t0 = time.time()
        for ci, mm in enumerate([model] + [m for m in FALLBACKS if m != model]):
            overload_hits = rate_hits = 0
            for mt in (max_tokens,) + tuple(budgets):
                for attempt in range(4):
                    try:
                        d = self._post(f"{BASE}/chat/completions", {
                            "model": mm,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": temp, "max_tokens": mt})
                        ch = d["choices"][0]
                        out = strip_think(ch["message"].get("content") or "")
                        fr = ch.get("finish_reason", "")
                        self.rec.append(Call(mm, purpose, mt, fr, len(out), False, time.time() - t0))
                        if fr == "length":
                            break
                        if out.count("<think>") > out.count("</think>"):
                            break
                        if len(out) >= min_ok:
                            self.rec[-1].ok = True
                            self.model_used[mm] = self.model_used.get(mm, 0) + 1
                            return out
                        last = out
                        break
                    except ApiError as e:
                        self.rec.append(Call(mm, purpose, mt, e.kind, 0, False, time.time() - t0, e.kind))
                        last_err = "%s(%s): %s" % (e.kind, mm, str(e)[:120])
                        if e.kind in ("credit", "auth"):
                            raise
                        if e.kind in ("gone", "forbidden"):
                            # 模型下架 / 供应商封禁 ⇒ 换下一个模型，别在这里空转
                            break
                        if e.kind == "rate_limit":
                            rate_hits += 1
                            time.sleep(12 + 8 * attempt)
                            continue          # 同一模型同一预算重试，**不换模型**
                        if e.kind == "overloaded":
                            overload_hits += 1
                            time.sleep(5 + 4 * overload_hits)
                            break             # 换下一个预算；全过载则换模型
                        time.sleep(3)
                        continue
                    except Exception as e:
                        self.rec.append(Call(mm, purpose, mt, "exc", 0, False, time.time() - t0, str(e)[:60]))
                        time.sleep(3)
                        continue
            if rate_hits and not overload_hits and ci == 0:
                print("  [orclient] %s 持续限流，已等待较久，放弃重试" % mm, flush=True)
                break
            if not overload_hits and not rate_hits and ci == 0:
                break
        if not last.strip():
            # ★ 原来这里 return "" —— 调用方拿到空串却没有任何错误信息，
            #   一次 404 就能让整套实验静默产出 0 字符。现在必须炸。
            raise RuntimeError(
                "OpenRouter chat 无输出（%s）。已试模型: %s。最后原因: %s"
                % (model, [model] + [m for m in FALLBACKS if m != model], last_err or "空响应"))
        return last

    _cache: dict = {}

    def embed(self, texts: list, typ: str = "db") -> list:
        """OpenRouter embedding。**不认** MiniMax 的 type 参数，所以不传。
        ⚠️ 返回必须按 index 排序：顺序不保证与输入一致，错位会静默污染去重。"""
        miss = [t for t in texts if t not in self._cache]
        for i in range(0, len(miss), 32):
            chunk = miss[i:i + 32]
            for t, v in zip(chunk, self._embed_chunk(chunk)):
                self._cache[t] = v
        return [self._cache.get(t) for t in texts]

    def _embed_chunk(self, chunk: list) -> list:
        last = None
        for model in [EMBED_MODEL] + EMBED_FALLBACKS:
            try:
                d = self._post(f"{BASE}/embeddings", {"model": model, "input": chunk})
                data = d.get("data")
                if not data:
                    raise ApiError("empty", "no data")
                data = sorted(data, key=lambda x: x.get("index", 0))
                vs = [x["embedding"] for x in data]
                if len(vs) != len(chunk):
                    raise ApiError("empty", "count mismatch")
                if not vs[0] or not isinstance(vs[0], (list, tuple)):
                    raise ApiError("empty", "bad vector")
                self.model_used["embed:" + model] = self.model_used.get("embed:" + model, 0) + 1
                return vs
            except ApiError as e:
                last = e
                if e.kind in ("credit", "auth"):
                    raise
                time.sleep(3)
            except Exception as e:
                last = e
                time.sleep(3)
        raise RuntimeError("OpenRouter embedding 不可用: %s" % (last,))


class Embedder:
    """去重用的 embedding 供应器：OpenRouter 优先，失败自动退 MiniMax embo-01。

    为什么要有兜底：2026-10-20 实测，OpenRouter 的 openai/* 与 google/* embedding
    被供应商 ToS 拦（403），而 MiniMax embo-01（1536 维）一直可用。

    ⚠️ **阈值警告**：去重阈值 0.75 是在 **MiniMax embo-01** 上标定的。
    换 embedding 模型会改变余弦相似度的尺度 ⇒ 同一个 0.75 在别的模型上
    含义不同 ⇒ **宽度/去重宽这类指标不可跨 embedding 模型比较**。
    `used` 会记录实际用了哪个，报告里必须一起写出来。
    """

    def __init__(self, provider: str = ""):
        self.used = None
        self._or = None
        self._mm = None
        self._cache = {}
        # EMBED_PROVIDER=minimax 强制走 embo-01（0.75 去重阈值的标定基准）
        self._force = (provider or os.environ.get("EMBED_PROVIDER", "")).strip().lower()

    def embed(self, texts, typ="db"):
        if self.used is None:
            self.used = self._pick()
        if self.used.startswith("openrouter:"):
            return self._or.embed(texts)
        return self._mm.embed(texts, typ)

    def _pick(self):
        if self._force in ("minimax", "mm", "embo-01"):
            from creativity_lab.client import LLM as MM
            self._mm = MM()
            return "minimax:embo-01"
        try:
            from creativity_lab.client import LLM as MM
            self._mm = MM()
        except Exception:
            self._mm = None
        try:
            self._or = LLM()
            v = self._or.embed(["探针"])
            if v and v[0]:
                return "openrouter:%s" % EMBED_MODEL
        except Exception as e:
            print("  [embed] OpenRouter 不可用（%s）→ 退 MiniMax embo-01" % str(e)[:80], flush=True)
        if self._mm is None:
            raise RuntimeError("没有可用的 embedding 通道")
        return "minimax:embo-01"
