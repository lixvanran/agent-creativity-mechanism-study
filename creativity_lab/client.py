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

# ★ 判官/生成侧的思考深度档（2026-10-23）：官方默认 = max ⇒ 烧光预算 ⇒ 统一 medium
DEFAULT_EFFORT = os.environ.get("MM_EFFORT", "medium")


def vendor_is_minimax(model: str) -> bool:
    return str(model).lower().startswith("minimax")


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
    ok: bool = False            # 内容长度达标（>= min_ok）
    has_content: bool = False   # ★ 传输成功（content_len > 0）——健康度应该用这个
    secs: float = 0.0
    effort: str = ""


class LLM:
    def __init__(self, recorder: list | None = None):
        self.rec = recorder if recorder is not None else []

    @staticmethod
    def _payload_variants(model, temp, mt, effort, prompt=""):
        """payload 变体：先带 `reasoning_effort`，失败再退回不带。

        ★ 不是所有 MiniMax 型号都吃这个参数；带参被拒时**必须**有退路，
          否则该模型的分支会**静默变成空串**（失败路径不许静默归零）。
        """
        base = {"model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temp, "max_tokens": mt}
        out = []
        if effort and vendor_is_minimax(model):
            v = dict(base); v["reasoning_effort"] = effort
            out.append(v)
        out.append(dict(base))
        return out

    def _post(self, url: str, payload: dict, timeout: int = 90):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {_KEY}", "content-type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())

    def chat(self, prompt: str, *, model: str = "MiniMax-M3", temp: float = 1.0,
             max_tokens: int = 8000, budgets=(12000, 16000), min_ok: int = 200,
             purpose: str = "", effort: str = DEFAULT_EFFORT,
             deadline: float = 120.0) -> str:
        """★ `effort`（2026-10-23）：MiniMax 的**思考深度**档。

        ⇒ 官方文档（platform.minimax.io）：`effort` ∈ low/medium/high/xhigh/max，
          **省略时默认 = max**；且 *"Thinking cannot be turned off... To reduce the
          latency and token usage of thinking, **lower the effort level**"*。
        ⇒ ★ 实测（第二组 2026-10-23）：`max` 档在**批 ≥4** 时 100% 把 `max_tokens`
          烧光（完成 token 恰好 = 上限）⇒ 一半调用空/截断；
          `medium`/`low` **零失败**且快 2–6 倍。
        ⇒ ⇒ **本仓库统一用 `medium`**（`DEFAULT_EFFORT`），并把它写进调用记录。

        ★★ `min_ok` 的坑（2026-10-24 实测）：它是**内容长度下限**。
          评估器类输出（JSON + 短理由）天然只有 40–140 字 ⇒ 若沿用 200 的默认值
          ⇒ **每次调用都会被判"失败"** ⇒ ① 记账全 False ⇒ **通道健康度被压到 0**
          ⇒ **健康度硬闸会误杀一个有效实验**；② 每次调用白跑 3 遍预算阶梯（3× 浪费）。
          ⇒ ⇒ **短输出任务必须显式传小 `min_ok`**（如 20）；
          ⇒ ⇒ 健康度用 `has_content`（传输成功），**不要用 `ok`**（长度达标）。
        """
        last = ""
        t0 = time.time()
        rec_before = len(self.rec)
        for mt in (max_tokens,) + tuple(budgets):
          if time.time() - t0 > deadline:
            # ★ 墙钟上限：一次 chat 的**总**耗时上限（防单次挂死拖垮整批）
            break
          for payload in self._payload_variants(model, temp, mt, effort, prompt):
            try:
                d = self._post(f"{BASE}/chat/completions", payload)
                ch = d["choices"][0]
                last = strip_think(ch["message"].get("content") or "")
                fr = ch.get("finish_reason", "")
                # ★★ 2026-10-24 修：改用**关键字参数**。
                #   旧写法是位置参数，与 dataclass 字段声明顺序**不一致** ⇒
                #   has_content ← secs / secs ← effort / effort ← ok  ⇒ **三字段值全错位**。
                #   后果：① 健康度恒为 1.0（秒数永远 truthy）⇒ 所有"通道健康度"读数失真；
                #         ② effort 从未真正进过元数据；③ 所有耗时是字符串。
                #   根因修复：**位置参数 → 关键字参数**，字段增删/换序都不可能再错位。
                self.rec.append(Call(
                    model=model, purpose=purpose, max_tokens=mt, finish_reason=fr,
                    content_len=len(last), ok=False,
                    has_content=len(last) > 0, secs=time.time() - t0, effort=effort))
                if fr == "length":          # 被 think 块吃光预算 → 加预算重来
                    break
                if last.count("<think>") > last.count("</think>"):
                    break                    # 思考未闭合 = 没有正文
                if len(last) >= min_ok:
                    self.rec[-1].ok = True
                    return last
                break
            except Exception:
                # ★ 不静默吞：换下一个 payload 变体（⇒ 去掉 reasoning_effort）
                #   再不行才睡 1.5s 重试 ⇒ 失败最终会体现在 rec 里（ok=False）
                time.sleep(1.5)
                if time.time() - t0 > deadline:
                    break
        if len(self.rec) == rec_before:
            # ★ 全程抛异常 ⇒ **一条记录都没有** ⇒ 通道健康度会漏算它
            #   ⇒ 显式记一条失败（失败路径不许静默消失）
            self.rec.append(Call(
                model=model, purpose=purpose, max_tokens=max_tokens,
                finish_reason="exception", content_len=0, ok=False,
                has_content=False, secs=time.time() - t0, effort=effort))
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
        """★ 嵌入：★ **落盘缓存优先**（★ 命中即零通道消耗 ★）★★
        ★ ★ 「把【需要在通道上算的量】挪到【生成时/首次算时】算好并落盘」
        ★ ★ ⇒ ★ 事后所有分析、★ 重算、★ 复核都【不再依赖通道存续】★★ ★
        ★ ★ 缓存目录：★ 环境变量 `MM_VECTOR_CACHE_DIR`（★ 未设 ⇒ ★ 行为与原来完全一致 ★）★★
        ★ ★ 缓存键：★ 文本 sha256 + 模型 + 类型 ⇒ ★ **不降维**（★ 谱熵依赖完整谱 ★）★★
        ★ ★ 命中但文件损坏 ⇒ **响亮失败**（★ 不静默回退到通道 ★）★★"""
        cache_dir = os.environ.get("MM_VECTOR_CACHE_DIR", "").strip()
        out = []
        miss = []
        for i, t in enumerate(texts):
            hit = self._cache.get(t)
            if hit is not None:
                out.append(hit)
                continue
            if cache_dir:
                _p = _cache_path(cache_dir, t, typ)
                if os.path.isfile(_p):
                    try:
                        obj = json.load(open(_p, encoding="utf-8"))
                        v = obj.get("vector")
                        if not isinstance(v, list) or not v:
                            raise ValueError("缓存内容为空/损坏")
                        self._cache[t] = v
                        out.append(v)
                        continue
                    except Exception as e:                        # noqa: BLE001
                        raise RuntimeError("★ 向量缓存损坏（%s）：%s ★ 响亮失败，★ 不静默回退到通道" % (_p, e))
            miss.append((i, t))
            out.append(None)                                    # type: ignore[arg-type]
        if miss:
            need = [t for _i, t in miss]
            for i in range(0, len(need), 32):
                chunk = need[i:i + 32]
                d = self._post(f"{BASE}/embeddings",
                               {"model": "embo-01", "type": typ, "texts": chunk})
                for t, v in zip(chunk, d["vectors"]):
                    self._cache[t] = v
                    if cache_dir:
                        _p = _cache_path(cache_dir, t, typ)
                        os.makedirs(os.path.dirname(_p), exist_ok=True)
                        tmp = _p + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as _f:
                            json.dump({"text_sha256": _cache_key(t, typ), "model": "embo-01",
                                       "type": typ, "dim": len(v), "vector": v,
                                       "cached_at_utc": _utcnow()}, _f, ensure_ascii=False)
                        os.replace(tmp, _p)
            for i, t in miss:
                out[i] = self._cache[t]
        return out


# ── 向量落盘缓存（★ 2026-10-24 ★）────────────────────────────────────
def _utcnow() -> str:
    import datetime as _dt
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_key(text: str, typ: str) -> str:
    import hashlib as _hl
    return _hl.sha256(("embo-01\x00" + typ + "\x00" + text).encode("utf-8")).hexdigest()


def _cache_path(cache_dir: str, text: str, typ: str) -> str:
    k = _cache_key(text, typ)
    return os.path.join(cache_dir, k[:2], k + ".json")


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
