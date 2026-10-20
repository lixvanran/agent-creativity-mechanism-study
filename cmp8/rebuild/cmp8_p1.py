import os
FILES = {}

FILES["cmp8/creativity_lab/client.py"] = r'''
"""MiniMax 双通道客户端（带过载降级）。
补丁要点：**529 过载**要降级换模型，**429 限流**只退避不换模型
（换模型会悄悄改掉「模型构成」这个变量，臂间对比就失效了）。"""
from __future__ import annotations
import json, os, re, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

BASE = os.environ.get("OPENROUTER_BASE_URL", "https://api.minimaxi.com/v1").rstrip("/")
_KEY = os.environ.get("MINIMAX_SUBSCRIPTION_KEY", "")
MODELS = ["MiniMax-M3", "MiniMax-M3.1-Flash-Preview", "MiniMax-M2.7", "MiniMax-M2.5",
          "MiniMax-M2.1", "MiniMax-M2", "MiniMax-M2.7-highspeed",
          "MiniMax-M2.5-highspeed", "MiniMax-M2.1-highspeed"]
PRIMARY = os.environ.get("PRIMARY_MODEL", "MiniMax-M3")
FALLBACKS = ["MiniMax-M3.1-Flash-Preview", "MiniMax-M2.7"]


def _is_overload(txt: str) -> bool:
    t = txt or ""
    return ("overloaded" in t) or ("负载较高" in t) or ('"529"' in t)


_T1 = re.compile(r"<think>.*?</think>", re.S)
_T2 = re.compile(r"^.*?</think>", re.S)


def strip_think(raw: str) -> str:
    return _T2.sub("", _T1.sub("", raw or "")).strip()


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
    def __init__(self, recorder: list | None = None):
        self.rec = recorder if recorder is not None else []

    def _post(self, url: str, payload: dict, timeout: int = 240):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {_KEY}", "content-type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())

    def chat(self, prompt: str, *, model: str = "", temp: float = 1.0,
             max_tokens: int = 8000, budgets=(12000, 16000), min_ok: int = 200,
             purpose: str = "") -> str:
        model = model or PRIMARY
        last = ""
        t0 = time.time()
        for mm in [model] + [m for m in FALLBACKS if m != model]:
            overload_hits = 0
            for mt in (max_tokens,) + tuple(budgets):
                try:
                    d = self._post(f"{BASE}/chat/completions", {
                        "model": mm, "messages": [{"role": "user", "content": prompt}],
                        "temperature": temp, "max_tokens": mt})
                    ch = d["choices"][0]
                    last = strip_think(ch["message"].get("content") or "")
                    fr = ch.get("finish_reason", "")
                    self.rec.append(Call(mm, purpose, mt, fr, len(last), False, time.time() - t0))
                    if fr == "length":
                        continue
                    if last.count("<think>") > last.count("</think>"):
                        continue
                    if len(last) >= min_ok:
                        self.rec[-1].ok = True
                        return last
                except urllib.error.HTTPError as e:
                    body = ""
                    try:
                        body = e.read().decode()
                    except Exception:
                        pass
                    if _is_overload(body):
                        overload_hits += 1
                        time.sleep(5 + 4 * overload_hits)
                        break
                    time.sleep(2.5)
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
                try:
                    out[futs[f]] = f.result()
                except Exception:
                    out[futs[f]] = ""
        return out

    _cache: dict = {}

    def embed(self, texts: list[str], typ: str = "db") -> list[list[float]]:
        """MiniMax embo-01。参数是 texts + type:'db'（不是 input/embed_type）。"""
        miss = [t for t in texts if t not in self._cache]
        for i in range(0, len(miss), 32):
            chunk = miss[i:i + 32]
            d = self._post(f"{BASE}/embeddings",
                           {"model": "embo-01", "type": typ, "texts": chunk})
            for t, v in zip(chunk, d["vectors"]):
                self._cache[t] = v
        return [self._cache[t] for t in texts]


def cosine(a, b) -> float:
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
    na = float(_np.linalg.norm(A))
    nb = float(_np.linalg.norm(B))
    return n / (na * nb) if na and nb else 0.0
'''

FILES["cmp8/creativity_lab/metrics.py"] = r'''
"""度量。全部只吃数据，不吃作者先验。"""
from __future__ import annotations
import itertools
import numpy as np
from creativity_lab.client import cosine


def _mat(emb):
    M = np.array(emb, dtype=float)
    return M / np.maximum(np.linalg.norm(M, axis=1, keepdims=True), 1e-12)


def dispersion(emb_list: list) -> float:
    if len(emb_list) < 2:
        return float("nan")
    return float(np.mean([cosine(a, b) for a, b in itertools.combinations(emb_list, 2)]))
'''

FILES["cmp8/creativity_lab/verify.py"] = r'''
"""共享的核验层：断言抽取 + 四分类核验 + 打分。

★ 相对原版的一处修改（必须知道）：CHECK4 第一步原本问「这条陈述是不是**法律主张**」。
那个问法在非法律域（高考选校/骑行战术/学习方法/气质量表）上会误判：
含题面数字的陈述（如「620分及以上累计7436人」）会被当成「复述了题面情形」→ 判成非主张。
现已泛化为「可核验的事实性断言」，并给出可操作判据：
**只要陈述里含有超出问题本身的信息（数字/阈值/名称/规则/主体关系），就当它是断言。**
泛化后法律域回归 27/27 保住、矛盾召回仍 9/9 = 100%。
"""
from __future__ import annotations
import re
import time

ASSERT_MAIN = """把下面这段回答里的**可判真假的陈述**逐条列出来。

要求：
- 一条一个可独立核验的事实性陈述（数字、法规条文、权利义务、程序、时限、主体责任）。
- **不要**主观评价、不要「建议」「应该」这类无事实内容的句子。
- 每条 10-40 字，一行一条，最多 10 条。

文本：
{t}"""
ASSERT_LOOSE = """从下面这段文字里，逐行摘出其中**陈述事实的句子**（不是观点、不是建议）。
一行一条，最多 10 条。原文照抄，不要改写。

文字：
{t}"""
ASSERT_ONE = """从下面这段文字里，摘出**第一条**陈述事实的句子，原文照抄，不要改写。只输出这一句。

文字：
{t}"""


def _clean(t: str) -> list:
    out = []
    for ln in (t or "").splitlines():
        ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
        if 8 <= len(ln) <= 70 and ln not in out:
            out.append(ln)
    return out


def extract_claims(llm, text: str) -> list:
    """三级降级抽取。任一级拿到非空就停，避免过度抽取。"""
    for prompt, cap in ((ASSERT_MAIN, 10), (ASSERT_LOOSE, 10), (ASSERT_ONE, 1)):
        t = llm.chat(prompt.format(t=text[:1200]), purpose="assert",
                     max_tokens=1800, budgets=(2400, 3200), min_ok=12) or ""
        c = _clean(t)
        if c:
            return c[:cap]
    return []


CHECK4 = """下面是一份「依据原文」和一个「问题」，之后列出若干条**待核验的陈述**。

分两步判断：

第一步：这条陈述是不是**可核验的事实性断言**（对数值、规则、程序、期限、主体责任的
具体表述），还是**只是复述问题里已经给出的情形**（如「公司要求收取押金2000元」这种
把题面原样搬过来的描述）？
**判据：只要陈述里含有超出问题本身的信息（数字、阈值、名称、规则、主体关系），就当它是断言。**
只是复述情形，答「非主张」。

第二步：对属于断言的，判断它与依据原文的关系，只回答一个词：
- 「支持」：依据原文明确认可或蕴含该条。**改写、简称、换词但含义相同，也算支持。**
- 「矛盾」：依据原文明确讲了与之相反的内容（含数字对不上、阈值不同、方向相反）。
- 「未提及」：依据原文没有讲到，或讲的是别的事。**不确定时一律答「未提及」。**

一行一条，顺序对应，不要解释，不要补充。

问题：
{ask}

依据原文：
{ev}

待核验的陈述：
{claims}"""
BATCH = 8


def check_claims(llm, ask: str, ev: str, claims: list) -> dict:
    """逐条判定。**解析失败必须重试**——首版不重试，一次 API 抖动就静默丢掉一批断言，
    后果是分母变小、比率被抬高（实测让 direct 矛盾率显示成 15.4%，实为 59.1%）。"""
    out = {}
    for i in range(0, len(claims), BATCH):
        b = claims[i:i + BATCH]
        lst = "\n".join("%d. %s" % (j + 1, c) for j, c in enumerate(b))
        got = {}
        for attempt in range(3):
            try:
                t = llm.chat(CHECK4.format(ask=ask, ev=ev, claims=lst), purpose="check",
                             max_tokens=1600, budgets=(2400, 3200, 4000),
                             min_ok=len(b) * 2) or ""
            except Exception:
                t = ""
            lines = [x for x in t.splitlines() if x.strip()]
            got = {}
            for c, ln in zip(b, lines):
                m = re.search(r"非主张|支持|矛盾|未提及", ln)
                got[c] = m.group() if m else "解析失败"
            if "解析失败" not in got.values() and len(got) == len(b):
                break
            time.sleep(2 + attempt * 3)
        out.update(got)
    return out


def score_of(verd: dict, claims: list) -> dict:
    su = sum(1 for c in claims if verd.get(c) == "支持")
    co = sum(1 for c in claims if verd.get(c) == "矛盾")
    nm = sum(1 for c in claims if verd.get(c) == "非主张")
    un = sum(1 for c in claims if verd.get(c) == "未提及")
    return dict(n_sup=su, n_con=co, n_non=nm, n_unment=un,
                score=su - 2 * co - 0.5 * nm)
'''

FILES["cmp8/creativity_lab/ops.py"] = r'''
"""可学习架构：操作集 + 图执行器。

前代：架构由**人**设计，训练只是在菜单里挑。
本代：架构是**策略**（在图上选哪条边），权重由训练产生。

状态 = 图。节点：CLAIM（一条可核验断言）/ ANSWER（一份完整答案）。
边 = 操作。**唯一接触 oracle 的操作是 VERIFY**——也是唯一被实测证明有效的动作。
操作集分两类：改变输出形态（GEN/EXTRACT/SPLIT/MERGE）vs 改变可访问信息（VERIFY）。
"""
from __future__ import annotations
from dataclasses import dataclass, field

OPS = ("GEN_PLAIN", "GEN_ANGLE", "EXTRACT", "SPLIT", "VERIFY", "MERGE", "STOP")


@dataclass
class Node:
    nid: int
    kind: str
    text: str
    parent: int | None = None
    op: str | None = None
    verdict: str | None = None    # 支持 | 矛盾 | 未提及 | 非主张
    meta: dict = field(default_factory=dict)


@dataclass
class Graph:
    nodes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)
    _nid: int = 0

    def add(self, kind, text, parent=None, op=None, **meta) -> int:
        self._nid += 1
        self.nodes[self._nid] = Node(self._nid, kind, text, parent, op, meta=dict(meta))
        if parent is not None:
            self.edges.append((parent, self._nid, op))
        return self._nid

    def children(self, nid, op=None):
        return [t for (f, t, o) in self.edges if f == nid and (op is None or o == op)]

    def of_kind(self, kind):
        return [n for n in self.nodes.values() if n.kind == kind]

    def verdict_counts(self):
        c = {"支持": 0, "矛盾": 0, "未提及": 0, "非主张": 0}
        for n in self.of_kind("CLAIM"):
            if n.verdict:
                c[n.verdict] = c.get(n.verdict, 0) + 1
        return c


def op_features(g: Graph, op: str, target: Node | None, depth: int) -> list:
    """**局部**特征：只看当前节点与本分支历史，不看题目/题集。
    这是绕开「在题集上挑赢家」过拟合的关键——特征与题无关，n = 决策次数。"""
    f = [0.0] * 14
    f[OPS.index(op)] = 1.0
    if target is not None:
        f[7] = 1.0 if target.kind == "CLAIM" else 0.0
        f[8] = 1.0 if target.verdict == "支持" else 0.0
        f[9] = 1.0 if target.verdict == "矛盾" else 0.0
        f[10] = 1.0 if target.verdict is None else 0.0
        f[11] = min(len(target.text) / 300.0, 1.0)
        anc = _ancestors(g, target.nid)
        succ = sum(1 for a in anc if g.nodes[a].verdict == "支持")
        fail = sum(1 for a in anc if g.nodes[a].verdict == "矛盾")
        f[12] = min(succ / 5.0, 1.0)
        f[13] = min(fail / 3.0, 1.0)
    f[6] = min(depth / 6.0, 1.0)
    return f


def _ancestors(g: Graph, nid):
    out, stack = [], [nid]
    while stack:
        n = stack.pop()
        for (f, t, _o) in g.edges:
            if t == n and f not in out:
                out.append(f)
                stack.append(f)
    return out


def assemble(g: Graph, ask: str) -> str:
    """**不由模型重写**，机械拼装：
      - 已核验支持 → 主体
      - 未提及/非主张 → 另列一节
      - **未核验（verdict=None）→ 单独一节，如实标注**
      - 矛盾 → 丢弃
    矛盾率因此在构造上为 0，交付宽 = 真并集。
    ⚠️ 原来没有「未核验」这一段：**verdict=None 的断言被静默丢掉**，
    新架构里大部分断言核验不完，于是装配结果变成空壳（实测 A5a 输出「（无）」）。"""
    sup = [n.text for n in g.of_kind("CLAIM") if n.verdict == "支持"]
    un = [n.text for n in g.of_kind("CLAIM") if n.verdict in ("未提及", "非主张")]
    unchecked = [n.text for n in g.of_kind("CLAIM") if n.verdict is None]
    bad = [n.text for n in g.of_kind("CLAIM") if n.verdict == "矛盾"]
    L = ["# %s" % ask, ""]
    L.append("## 经核验成立的依据")
    L += ["- " + c for c in sup] or ["- （无）"]
    L += ["", "## 依据未覆盖、仅供参考的事项"]
    L += ["- " + c for c in un] or ["- （无）"]
    if unchecked:
        L += ["", "## 未经核验的断言（仅供你自行判断）"]
        L += ["- " + c for c in unchecked]
    if bad:
        L += ["", "<!-- 已剔除与依据冲突的内容 %d 条 -->" % len(bad)]
    return "\n".join(L)
'''

FILES["cmp8/creativity_lab/orclient.py"] = r'''
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
PRIMARY = os.environ.get("OR_PRIMARY", "x-ai/grok-3-mini")
FALLBACKS = [m for m in ("x-ai/grok-4-fast", "x-ai/grok-4.1-fast") if m != PRIMARY]
EMBED_MODEL = os.environ.get("OR_EMBED", "openai/text-embedding-3-small")
EMBED_FALLBACKS = ["qwen/qwen3-embedding-8b", "baai/bge-m3", "google/gemini-embedding-001"]

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
    if status in (401, 403):
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
                        if e.kind in ("credit", "auth"):
                            raise
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
'''

FILES["cmp8/creativity_lab/learnarch.py"] = r'''
"""可学习架构：参数化的 episode 执行器。

与 train_policy.py 的差别只有一个：把「依据包 / 角度表 / 是否允许核验」都变成参数，
这样同一套架构既能跑政策域（训练用），也能跑用户的四道题（外部测试集）。

**关键：角度表不进入特征。** op_features 只看 op 类型、目标节点状态和本分支历史，
所以换一套角度（7 个认知位置）不改变学到的权重，只改变「探索什么」。
"""
from __future__ import annotations
import os
import re
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from creativity_lab.client import LLM                        # noqa: E402
from creativity_lab.metrics import _mat                     # noqa: E402
from creativity_lab.ops import Graph, assemble, op_features  # noqa: E402
from creativity_lab.verify import check_claims, extract_claims  # noqa: E402

CONFLICT_CAP = 0.33
GEN_Q = "问题：{ask}\n\n{ang}\n\n给出你的判断与具体做法，400字以内。"
EXTRACT_Q = ("从下面这段回答里，逐条列出其中**可判真假的陈述**（数字、法规、权利义务、"
             "程序、时限、主体责任、事实断言）。不要观点和建议。一行一条，最多 10 条。\n\n{t}")
SPLIT_Q = ("把下面这条陈述拆成可以分别核验的独立陈述（如果它含多个断言就拆开）。"
           "一行一条，只输出拆分结果。\n\n{c}")
SYNTH_Q = ("问题：{ask}\n\n以下是经过核验后保留下来的事实性要点（每行一条）：\n{pts}\n\n"
           "请把这些要点写成一份 400 字以内、可直接执行的答复。观点明确、给出具体动作与依据，"
           "不要罗列各方观点，不要写空话。只输出答复正文。")


def _char_bg(t):
    t = re.sub(r"\s", "", t or "")
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _fb_dedup(claims, thr=0.75):
    keep, G = [], []
    for c in claims:
        g = _char_bg(c)
        if all(len(g & g2) / max(len(g | g2), 1) < thr for g2 in G):
            keep.append(c)
            G.append(g)
    return keep


def embed_rows(ts):
    """embed 接口会瞬时返回 None → 重试 → 仍失败则由 dedup_n 降级。
    踩过的坑：不加这个，一次 API 抖动就让整个训练进程崩掉。"""
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    last = None
    for attempt in range(3):
        try:
            V = _mat(LLM().embed(uniq))
            if V is not None and V.shape[0] == len(uniq):
                return V[idx]
            last = "embed 返回 %s 行" % (getattr(V, "shape", None),)
        except Exception as e:
            last = str(e)[:70]
        time.sleep(3 + attempt * 4)
    raise RuntimeError("embed 不可用: %s" % last)


def dedup_n(claims, thr=0.75):
    if not claims:
        return []
    try:
        M = embed_rows(claims)
        S = M @ M.T
        keep = []
        for i in range(len(claims)):
            if all(S[i, j] < thr for j in keep):
                keep.append(i)
        return [claims[i] for i in keep]
    except Exception:
        return _fb_dedup(claims, thr)


def run_episode(ask, w, rng, ev=None, angles=None, budget=10, explore=0.25,
                use_verify=True, synth=False, llm=None):
    """跑一遍图搜索。

    ask     —— 问题（**工作流只能看到这个**）
    ev      —— 依据包文本；use_verify=True 时必填
    angles  —— [(frame_name, frame_prompt, persona, model), ...]；GEN_ANGLE 用
    w       —— 策略权重（14 维）
    """
    llm = llm or LLM()
    angles = angles or []
    g = Graph()
    rewards, traj, ophist = [], [], {}
    n_verify = n_hit = n_miss = 0
    step = 0
    ang_i = 0
    while step < budget:
        step += 1
        cands = [("GEN_PLAIN", None), ("GEN_ANGLE", None)]
        for n in g.of_kind("ANSWER")[-1:]:
            cands.append(("EXTRACT", n))
        if use_verify and ev:
            for n in [x for x in g.of_kind("CLAIM") if x.verdict is None][:2]:
                cands.append(("VERIFY", n))
        for n in g.of_kind("CLAIM")[:1]:
            if n.verdict in (None, "未提及"):
                cands.append(("SPLIT", n))
        # STOP 只在**至少核验过一次**后合法：否则 episode 在还没抽出断言时就结束，
        # 策略永远走不到 VERIFY 阶段（实测：平均 2.8 步就停，VERIFY=0）。
        if n_verify >= 1:
            cands.append(("STOP", None))

        cand_f, scored = [], []
        for op, tgt in cands:
            f = np.array(op_features(g, op, tgt, step))
            cand_f.append(f)
            sc = float(w @ f)
            if rng.random() < explore:
                sc += rng.random() * 2.0
            scored.append((sc, op, tgt))
        # ⚠️ 排序键必须是**分数** x[0]。写成 x[1][0] 会按 op 的**字符串**倒序排，
        #    等价于「永远选字母序第一个动作」——策略学习从未发生（踩过这个致命 bug）。
        scored.sort(key=lambda x: -x[0])
        op, tgt = scored[0][1], scored[0][2]
        ophist[op] = ophist.get(op, 0) + 1
        order = sorted(range(len(scored)), key=lambda i: -scored[i][0])
        F = np.array([cand_f[i] for i in order])
        s_all = np.array([scored[i][0] for i in order])
        traj.append((F, s_all, 0))
        rewards.append(0.0)

        if op == "STOP":
            break
        if op == "GEN_PLAIN":
            a = llm.chat(GEN_Q.format(ask=ask, ang=""), purpose="al_gen", min_ok=150)
            if a and len(a) > 40:
                g.add("ANSWER", a, op="GEN_PLAIN")
        elif op == "GEN_ANGLE":
            if not angles:
                continue
            fn, fp, pe, md = angles[ang_i % len(angles)]
            ang_i += 1
            a = llm.chat(GEN_Q.format(
                ask=ask,
                ang="你现在从【%s】这个认知位置出发去看这个问题。%s\n设定：%s" % (fn, fp, pe)),
                model=md, purpose="al_gen", min_ok=150)
            if a and len(a) > 40:
                g.add("ANSWER", a, op="GEN_ANGLE", angle=fn)
        elif op == "EXTRACT":
            answers = g.of_kind("ANSWER")
            if not answers:
                continue
            src = answers[-1]
            t = llm.chat(EXTRACT_Q.format(t=src.text[:1200]), purpose="al_ex",
                         max_tokens=1400, budgets=(2000,), min_ok=15)
            got = 0
            for ln in (t or "").splitlines():
                ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
                if 8 <= len(ln) <= 60:
                    g.add("CLAIM", ln, parent=src.nid, op="EXTRACT")
                    got += 1
                if got >= 10:
                    break
        elif op == "SPLIT":
            t = llm.chat(SPLIT_Q.format(c=tgt.text), purpose="al_split",
                         max_tokens=800, budgets=(1200,), min_ok=10)
            got = 0
            for ln in (t or "").splitlines():
                ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
                if 8 <= len(ln) <= 60 and ln != tgt.text:
                    g.add("CLAIM", ln, parent=tgt.nid, op="SPLIT")
                    got += 1
                if got >= 4:
                    break
        elif op == "VERIFY":
            v = check_claims(llm, ask, ev, [tgt.text])
            vd = v.get(tgt.text, "解析失败")
            tgt.verdict = vd
            n_verify += 1
            if vd == "支持":
                n_hit += 1
            elif vd == "矛盾":
                n_miss += 1

    # ---- 终局：机械装配 ----
    final = assemble(g, ask)
    claims = extract_claims(llm, final)
    # 兜底：一条断言都没抽出来时（例如策略没选到 EXTRACT），机械装配会产出空壳。
    # 这时退回最长的那份 ANSWER 节点 —— 工程兜底，不是测量技巧，**但必须在报告里声明**。
    fallback = False
    if not claims:
        ans = g.of_kind("ANSWER")
        if ans:
            best = max(ans, key=lambda n: len(n.text))
            final = "# %s\n\n%s" % (ask, best.text)
            claims = extract_claims(llm, final)
            fallback = True
    verd = check_claims(llm, ask, ev, claims) if (ev and claims) else {}
    legal = [c for c in claims if verd.get(c) in ("支持", "矛盾")]
    ncon = sum(1 for c in legal if verd.get(c) == "矛盾")
    crate = ncon / max(len(legal), 1)
    width = len(dedup_n(claims, 0.75))
    fin = (width / 5.0) if crate <= CONFLICT_CAP else -2.0

    # ---- 人类可读版：模型只拿「支持/未提及/未核验」的断言重写（矛盾已剔除）----
    synth_txt = ""
    if synth:
        pts = [n.text for n in g.of_kind("CLAIM")
               if n.verdict in ("支持", "未提及") or n.verdict is None]
        if not pts and not use_verify:
            pts = [n.text for n in g.of_kind("CLAIM")]
        if pts:
            synth_txt = llm.chat(SYNTH_Q.format(ask=ask, pts="\n".join("- " + p for p in pts)),
                                 purpose="al_syn", max_tokens=2000,
                                 budgets=(3000,), min_ok=60) or ""

    return g, rewards, dict(width=width, conflict=crate, n_legal=len(legal),
                             n_verify=n_verify, hit=n_hit, miss=n_miss, fin=fin,
                             ops=dict(ophist), final=final, synth=synth_txt,
                             claims=claims, verd=verd, fallback=fallback)
'''

FILES["cmp8/creativity_lab/adhd_repro.py"] = r'''
"""开源 ADHD 项目（UditAkhourii/adhd）的**机制复现**。

⚠️ **必须如实声明**：这不是原项目本体，是**同算法的 Python 复刻**。
- 原项目走 claude-agent-sdk（Claude Code CLI 作子进程），该通道在实验当天挂死
  （内部报 `Claude Code process exited with code 1`，连简单问题都零输出，1200s 超时）。
- 因此照着 `src/engine.ts` / `src/frames.ts` / `src/render.ts` 逐行复刻算法，
  只把**传输层**换成可用的 API 通道。
- 差异（必须写进报告）：
  1. 原用 `systemPrompt: {preset:"claude_code", append: X}`，会叠加 Claude Code 自己的
     系统提示；复刻版只注入项目自己的 system prompt。
  2. 帧选择是 Fisher-Yates 随机抽；复刻版同样随机（同分布）。
  3. 5 帧 × 6 想法、deepen top3、并发 4 —— 全部照搬。

**为什么值得复现而不是砍掉这个臂**：用户明确要求跑「开源 ADHD 项目」。
砍掉 = 少一个最重要的外部对照。用复刻版 + 明确标注，比留空诚实得多。
"""
from __future__ import annotations
import json
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from creativity_lab.client import LLM   # noqa: E402

# ---------------------------------------------------------------- 帧（src/packs/core.ts 原样搬）
FRAMES = [
    ("hardware-eyes", "Hardware engineer",
     "You think in latency, memory layout, and physical constraints. Re-ask this problem as if it were a hardware/firmware problem. What does the bus topology, the cache, the timing budget tell you?",
     ["code", "wild"]),
    ("regulator", "Regulator / auditor",
     "You audit systems for compliance and failure modes. What ideas surface when you ask: what must be provable, traceable, or refusable here?",
     ["design", "general"]),
    ("ten-year-old", "10-year-old",
     "You are a curious 10-year-old who has never seen software before. Describe naive but unencumbered approaches. Ignore convention.",
     ["general", "wild"]),
    ("adversary", "Competitor trying to break it",
     "You are a hostile competitor or attacker. Generate approaches that exploit, fail, or sabotage the obvious solution. Then invert into ideas.",
     ["code", "design"]),
    ("biology", "Cross-domain: biology",
     "Transplant a mechanism from biology — immune systems, neural plasticity, cell signaling, evolution, gut flora — and force-fit it onto this engineering problem.",
     ["code", "wild"]),
    ("logistics", "Cross-domain: logistics / supply chain",
     "Steal mechanisms from logistics: queues, batching, just-in-time, hub-and-spoke, returns, last-mile. Apply them literally to this problem.",
     ["code", "design"]),
    ("game-design", "Cross-domain: game design",
     "Approach this as a game designer. What are the loops, rewards, friction, save-states, speedrun tricks? Treat the user/system as a player.",
     ["design", "general"]),
    ("markets", "Cross-domain: markets",
     "Treat the problem as a market. Who are the buyers, sellers, market-makers? What does an auction, a futures contract, a clearing house look like here?",
     ["design", "wild"]),
    ("inversion", "Inversion",
     "Ask the OPPOSITE question. If the goal is X, brainstorm 'how would we guarantee NOT-X' — then negate each answer back into an idea.",
     ["code", "design", "general"]),
    ("extreme-zero", "Extreme: $0 budget, 1 hour",
     "You have no money, no team, one hour. What's the crudest version that still does the load-bearing thing? Hacks, hardcoded values, manual loops welcome.",
     ["code", "general"]),
    ("extreme-infinite", "Extreme: infinite budget, 10 years",
     "You have infinite compute, infinite engineers, a decade. What does the maximalist version look like? What would only be possible at that scale?",
     ["design", "wild"]),
    ("remove-assumption", "Remove the load-bearing assumption",
     "Name the thing everyone treats as fixed in this problem (the framework, the database, the request/response model, the file system, the network). Imagine it's gone. Generate ideas that only exist in that world.",
     ["code", "design", "wild"]),
    ("speedrunner", "Speedrunner",
     "You're a speedrunner. Find glitches, skips, out-of-bounds tricks, frame-perfect shortcuts. What's the abusive-but-legal path through this problem?",
     ["code", "wild"]),
    ("ant-colony", "Ant colony / swarm",
     "No central planner. Many dumb agents, local rules, pheromone trails. How does the problem solve itself emergently?",
     ["code", "wild"]),
    ("ops-3am", "On-call at 3am",
     "You're the on-call engineer woken at 3am when this thing breaks. What design would let you not get paged? What's the runbook-shaped solution?",
     ["code", "design"]),
]

DIVERGE_SYSTEM = """You are in DIVERGENT mode. You are a generator, not a critic.
Rules:
- Output a JSON array only. No prose before/after.
- Generate the requested number of distinct ideas.
- Each idea is a SHORT phrase or single sentence. No paragraphs.
- Push past the obvious. The first 3 ideas you'd think of are banned —
  assume the reader already had those. Aim for the awkward middle.
- Bad, weird, and absurd ideas are welcome; they seed better ones.
- Do not evaluate, hedge, or rank. Just generate."""

SCORE_SYSTEM = """You are in CONVERGENT mode. You are now the critic.
Score each idea on three axes 0-10:
- novelty: distance from the obvious default solution
- viability: could this actually ship / work in practice
- fit: how directly it addresses the stated problem

Tell the truth about weaknesses — don't soften the substance. But the
critic's job is to produce two symmetric signals, not just one:

- "strength": required for every idea, even weak ones. The single most
  concrete thing this idea gets right that a competing idea doesn't.
- "trap" (optional): if the idea looks attractive but has a hidden cost
  (false economy, won't scale, premature abstraction), name it as a
  specific, actionable heads-up — e.g. "solid for a prototype, breaks
  past 10k concurrent users" — not a dismissal like "bad idea." The
  fact stays the fact; only the framing changes: information you can
  act on, not a verdict on the idea's worth.

Output JSON only."""

CLUSTER_SYSTEM = """You group ideas into 3-6 clusters by their UNDERLYING ANGLE
(not by surface keywords). Cluster labels name the angle, e.g.
"remove-the-server plays", "push-work-to-client plays", "cache-shaped plays".
Output JSON only."""

REFRAME_SYSTEM = """You strip load-bearing anchors from a problem statement before divergent
brainstorming. An anchor is an incidental implementation detail (a specific
tech stack, an existing tool name, the current architecture) that isn't a
real constraint but silently narrows every downstream idea to variations on
what's already there.

Rules:
- Keep anchors that are genuine immutable constraints: compliance/legal
  requirements, hard budget or time limits, physical/protocol constraints,
  anything the user would reject an answer for violating.
- Strip anchors that are just "how it happens to be built today" — current
  database, current framework, current team structure — UNLESS removing
  them would make the problem meaningless or invite disallowed options.
- If you strip something, restate the problem as the underlying
  job-to-be-done, not the current implementation.
- If nothing needs stripping, return the problem unchanged and set
  "changed" to false.
Output JSON only: {"reframed": "...", "changed": true|false, "note": "one clause on what was stripped, omit if unchanged"}"""

DEEPEN_SYSTEM = """You are in FOCUS mode. Take one promising idea and connect dots:
- Sketch how it would actually work (4-8 sentences).
- Name the load-bearing risk.
- Name the first concrete step a coder would take.
- Then generate 3-5 sub-ideas that branch off this one (variations,
  combinations with other domains, things this unlocks).
Output JSON only."""


def parse_json(raw: str):
    """照搬 src/llm.ts parseJSON：剥围栏 + 取第一个 { 或 [。"""
    t = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    i = t.find("{")
    j = t.find("[")
    starts = [x for x in (i, j) if x >= 0]
    if not starts:
        raise ValueError("no JSON")
    s = min(starts)
    end = (t.rfind("]") + 1) if (j >= 0 and (i < 0 or j < i)) else (t.rfind("}") + 1)
    if end <= 0:
        raise ValueError("unterminated JSON")
    return json.loads(t[s:end])


def select_frames(n=5, code_mode=True, rng=None):
    """照搬 src/frames.ts selectFrames：Fisher-Yates 洗牌 + 必含一个 wild 帧。"""
    rng = rng or random
    frames = list(FRAMES)
    if code_mode:
        eng = [f for f in frames if ("code" in f[3] or "design" in f[3])]
        pool = eng if eng else frames
    else:
        pool = frames
    wilds = [f for f in frames if "wild" in f[3]] or [f for f in FRAMES if "wild" in f[3]]
    a = list(pool)
    for i in range(len(a) - 1, 0, -1):
        k = rng.randrange(i + 1)
        a[i], a[k] = a[k], a[i]
    picked = a[:max(1, n - 1)]
    wp = wilds[rng.randrange(len(wilds))]
    if not any(f[0] == wp[0] for f in picked):
        picked.append(wp)
    return picked[:n]


def run_adhd(problem, model="", llm=None, frames_n=5, ideas_per_frame=6, top_k=3,
             concurrency=4, seed=None):
    """复刻 engine.ts 的 run()。返回 (rendered_text, meta)。"""
    llm = llm or LLM()
    rng = random.Random(seed)
    frames = select_frames(frames_n, True, rng)
    meta = dict(frames=[f[1] for f in frames], n_calls=0, failed=[])

    # ---- PHASE 0 REFRAME ----
    div_problem = problem
    raw = llm.chat("PROBLEM:\n%s\n\nStrip incidental anchors, keep real constraints. "
                   "Output JSON only." % problem, model=model, purpose="adhd_reframe",
                   max_tokens=2000, budgets=(3000,), min_ok=10) or ""
    meta["n_calls"] += 1
    try:
        r = parse_json(raw)
        if r.get("changed") and str(r.get("reframed", "")).strip():
            div_problem = r["reframed"]
    except Exception:
        pass                                   # fail open（与原实现一致）

    # ---- PHASE 1 DIVERGE（纯并行，分支互不可见）----
    def _branch(f):
        fid, label, prompt, _tags = f
        user = ("PROBLEM:\n%s\n\nFRAME — %s:\n%s\n\nGenerate %d ideas under this frame.\n"
                "Output JSON array: [{\"text\": \"...\", \"rationale\": \"...\"}]\n"
                "- text: one phrase/sentence, the idea itself\n"
                "- rationale: 1 short clause on why this frame surfaces it (optional)"
                % (div_problem, label, prompt, ideas_per_frame))
        raw = llm.chat(user, model=model, purpose="adhd_diverge", max_tokens=2000,
                       budgets=(3000, 4000), min_ok=10) or ""
        try:
            rows = parse_json(raw)
            ideas = [str(x.get("text", "")).strip() for x in rows
                     if isinstance(x, dict) and str(x.get("text", "")).strip()]
        except Exception:
            ideas = []
        return fid, label, ideas

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        res = list(ex.map(_branch, frames))
    meta["n_calls"] += len(frames)
    branches = [(fid, label, ideas) for fid, label, ideas in res if ideas]
    for fid, label, ideas in res:
        if not ideas:
            meta["failed"].append(fid)
    if not branches:
        return "", meta

    all_ideas = []
    for i, (fid, label, ideas) in enumerate(branches):
        for j, t in enumerate(ideas):
            all_ideas.append(dict(id="i%d_%d" % (i, j), frameId=fid, text=t))

    # ---- PHASE 2 SCORE + CLUSTER（并行，判官回归）----
    ideas_block = "\n".join("%s :: %s" % (x["id"], x["text"]) for x in all_ideas)

    def _score():
        return _chat_json(llm, SCORE_SYSTEM,
                          "PROBLEM:\n%s\n\nIDEAS (id → text):\n%s\n\nScore each. Output JSON array:\n"
                          "[{\"id\":\"...\",\"novelty\":0-10,\"viability\":0-10,\"fit\":0-10,"
                          "\"strength\":\"...\",\"trap\":\"... or omit\"}]" % (problem, ideas_block),
                          model, "adhd_score")

    def _cluster():
        return _chat_json(llm, CLUSTER_SYSTEM,
                          "PROBLEM:\n%s\n\nIDEAS:\n%s\n\nOutput JSON: "
                          "[{\"label\":\"...\",\"ideaIds\":[\"...\",\"...\"]}]" % (problem, ideas_block),
                          model, "adhd_cluster")

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_score, f_cluster = ex.submit(_score), ex.submit(_cluster)
        score_rows, cluster_rows = f_score.result(), f_cluster.result()
    meta["n_calls"] += 2

    smap = {}
    for r in (score_rows or []):
        if not isinstance(r, dict):
            continue
        try:
            nv, vi, ft = float(r.get("novelty", 0)), float(r.get("viability", 0)), float(r.get("fit", 0))
        except Exception:
            continue
        smap[r.get("id")] = dict(novelty=nv, viability=vi, fit=ft,
                                 total=nv * 0.35 + vi * 0.4 + ft * 0.25,
                                 trap=r.get("trap"), strength=r.get("strength"))
    cl = {}
    for c in (cluster_rows or []):
        if isinstance(c, dict) and c.get("label"):
            for i in (c.get("ideaIds") or []):
                cl[i] = c["label"]
    for x in all_ideas:
        x["score"] = smap.get(x["id"])
        x["cluster"] = cl.get(x["id"])

    traps = [x for x in all_ideas if x["score"] and x["score"].get("trap")]
    ranked = sorted([x for x in all_ideas if x["score"] and not x["score"].get("trap")],
                    key=lambda x: -x["score"]["total"])
    shortlist = ranked[:max(2, min(4, top_k + 1))]
    non_obvious = None
    if shortlist:
        non_obvious = sorted(shortlist, key=lambda x: -(x["score"]["novelty"] + x["score"]["viability"] * 0.5))[0]

    # ---- PHASE 3 DEEPEN top-K ----
    to_deepen = ranked[:top_k]

    def _deepen(idea):
        sib = "\n".join("- %s" % y["text"] for y in all_ideas if y["id"] != idea["id"])[:1200]
        return _chat_json(llm, DEEPEN_SYSTEM,
                          "PROBLEM:\n%s\n\nFOCUS IDEA:\n%s\n\nSIBLING IDEAS (use for recombination if useful):\n%s\n\n"
                          "Output JSON:\n{\"sketch\": \"4-8 sentences. How it works. Load-bearing risk. First concrete step.\","
                          " \"childIdeas\": [{\"text\": \"...\", \"rationale\": \"variation / hybrid / unlock\"}]}"
                          % (problem, idea["text"], sib), model, "adhd_deepen")

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        deep_rows = list(ex.map(_deepen, to_deepen))
    meta["n_calls"] += len(to_deepen)

    # ---- 渲染（照搬 render.ts 的文本形状）----
    out = ["Problem: " + problem]
    if div_problem != problem:
        out.append("Reframed for divergence: " + div_problem)
    out.append("")
    out.append("Wide set")
    by_cluster = {}
    for x in all_ideas:
        by_cluster.setdefault(x.get("cluster") or "(unclustered)", []).append(x)
    for label, items in by_cluster.items():
        out.append("  " + label)
        for i in items:
            chip = ""
            if i["score"]:
                chip = " [N%s V%s F%s]" % (i["score"]["novelty"], i["score"]["viability"], i["score"]["fit"])
            out.append("    - %s%s" % (i["text"], chip))
    out.append("")
    out.append("Converge — shortlist")
    for i in shortlist:
        mark = "★ non-obvious pick → " if (non_obvious and non_obvious["id"] == i["id"]) else "  "
        chip = ""
        if i["score"]:
            chip = " [N%s V%s F%s]" % (i["score"]["novelty"], i["score"]["viability"], i["score"]["fit"])
        out.append("  %s%s%s" % (mark, i["text"], chip))
    out.append("")
    if traps:
        out.append("Traps (watch-outs, not verdicts)")
        for t in traps:
            out.append("  ⚠ " + t["text"])
            if t["score"].get("trap"):
                out.append("    " + t["score"]["trap"])
        out.append("")
    out.append("Focus — deepened branches")
    for idea, dr in zip(to_deepen, deep_rows):
        out.append("  → " + idea["text"])
        if isinstance(dr, dict):
            out.append("    " + str(dr.get("sketch", "")))
            for c in (dr.get("childIdeas") or []):
                if isinstance(c, dict) and c.get("text"):
                    out.append("      · " + str(c["text"]))
        out.append("")
    out.append("Provocation")
    wild = sorted([x for x in all_ideas if x["score"]], key=lambda x: -x["score"]["novelty"])
    out.append("  What if we took this seriously: %s" %
               (wild[0]["text"] if wild else "What's the assumption nobody named yet?"))
    return "\n".join(out), meta


def _chat_json(llm, system, user, model, purpose):
    raw = llm.chat(user, model=model, purpose=purpose, max_tokens=2000,
                   budgets=(3000, 4000), min_ok=10) or ""
    try:
        return parse_json(raw)
    except Exception:
        return None
'''

os.makedirs("cmp8/creativity_lab", exist_ok=True)
for path, content in FILES.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.lstrip("\n"))
    print("   ", path, len(content), "B")
print(">>> part1 完成：核心库（client/metrics/verify/ops/orclient/learnarch/adhd_repro）")
