"""MiniMax 双通道客户端：chat + embedding。

沙箱约束（已实测，见 notes/沙箱与踩坑.md）：
- embedding 参数是 `texts` 不是 `input`，且必须带 `type`（"db"/"query"）
- <think> 块会吃光 max_tokens，需检查 finish_reason == "length" 后重试加预算
- 某些档位把思考放进 reasoning_content，content 可能缺失
- 弱档位会把预算花在 meta 分析上，返回未闭合 <think> 且无正文 → 视为失败重试
"""
from __future__ import annotations
import json, os, re, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

BASE = os.environ.get("OPENROUTER_BASE_URL", "https://api.minimaxi.com/v1").rstrip("/")
_KEY = os.environ.get("MINIMAX_SUBSCRIPTION_KEY", "")

MODELS = [
    "MiniMax-M3", "MiniMax-M3.1-Flash-Preview", "MiniMax-M2.7",
    "MiniMax-M2.5", "MiniMax-M2.1", "MiniMax-M2",
    "MiniMax-M2.7-highspeed", "MiniMax-M2.5-highspeed", "MiniMax-M2.1-highspeed",
]

_T1 = re.compile(r"<think>.*?</think>", re.S)
_T2 = re.compile(r"^.*?</think>", re.S)


def strip_think(raw: str) -> str:
    return _T2.sub("", _T1.sub("", raw or "")).strip()


@dataclass
class Call:
    """一次真实调用的记录。审计只认这个对象。"""
    model: str
    purpose: str
    max_tokens: int
    finish_reason: str = ""
    content_len: int = 0
    ok: bool = False
    secs: float = 0.0


class LLM:
    def __init__(self, recorder: list | None = None):
        self.rec = recorder if recorder is not None else []

    def _post(self, url: str, payload: dict, timeout: int = 240):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {_KEY}", "content-type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())

    def chat(self, prompt: str, *, model: str = "MiniMax-M3", temp: float = 1.0,
             max_tokens: int = 8000, budgets=(12000, 16000), min_ok: int = 200,
             purpose: str = "") -> str:
        last = ""
        t0 = time.time()
        for mt in (max_tokens,) + tuple(budgets):
            try:
                d = self._post(f"{BASE}/chat/completions", {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temp, "max_tokens": mt})
                ch = d["choices"][0]
                last = strip_think(ch["message"].get("content") or "")
                fr = ch.get("finish_reason", "")
                self.rec.append(Call(model, purpose, mt, fr, len(last), False, time.time() - t0))
                if fr == "length":          # 被 think 块吃光预算 → 加预算重来
                    continue
                if last.count("<think>") > last.count("</think>"):
                    continue                  # 思考未闭合 = 没有正文
                if len(last) >= min_ok:
                    self.rec[-1].ok = True
                    return last
            except Exception:
                time.sleep(2.5)
        return last

    def chat_many(self, prompts: list[str], *, workers: int = 3, **kw) -> list[str]:
        if workers <= 1:
            return [self.chat(p, **kw) for p in prompts]
        out = [""] * len(prompts)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(self.chat, p, **kw): i for i, p in enumerate(prompts)}
            for f in as_completed(futs):
                try: out[futs[f]] = f.result()
                except Exception: out[futs[f]] = ""
        return out

    _cache: dict = {}

    def embed(self, texts: list[str], typ: str = "db") -> list[list[float]]:
        miss = [t for t in texts if t not in self._cache]
        for i in range(0, len(miss), 32):
            chunk = miss[i:i + 32]
            d = self._post(f"{BASE}/embeddings",
                           {"model": "embo-01", "type": typ, "texts": chunk})
            for t, v in zip(chunk, d["vectors"]):
                self._cache[t] = v
        return [self._cache[t] for t in texts]


def cosine(a, b) -> float:
    """对 list / tuple / numpy 向量都安全；遇到嵌套/形状不一致时返回 0 而不是抛错。"""
    if a is None or b is None:
        return 0.0
    try:
        import numpy as _np
        A = _np.asarray(a, dtype=float).ravel()
        B = _np.asarray(b, dtype=float).ravel()
    except Exception:
        return 0.0
    if A.size == 0 or B.size == 0 or A.size != B.size:
        return 0.0
    n = float(A @ B)
    na = float(_np.linalg.norm(A)); nb = float(_np.linalg.norm(B))
    return n / (na * nb) if na and nb else 0.0
