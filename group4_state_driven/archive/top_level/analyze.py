#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
第四组 · Phase 0 分析器（analyze.py）
================================================================================

【定位】
按《测量方案裁决》(/workspace/第四组论证/测量方案裁决.md) §2 实现：
在被测模型 = MiniMax-M3、**跨家族判官不可用**、**人类盲评昂贵**、**logprobs 不返回**
的四个约束同时成立时，第四组还能测什么、怎么测、测不到什么。

【A 类指标（无需判官）】
  PL · 极性位移   主判据：δ_臂 = mean(emb(臂,P+))·v − mean(emb(臂,P−))·v，v 为该题极性轴
  SC · 塌缩度     主判据：同臂同题 N 次采样的产出两两平均余弦距离
  KWH · 约束关键词命中率  辅助：排除"直接复述句"后的取舍约束关键词命中率
  FS · 功能词签名 辅助：中文句法/功能词分布 20–40 维（不依赖英文 Biber 工具链）
  RARE · n-gram 稀有度  诊断（需参照语料）
  LEX · MTLD / TTR  诊断（TTR 受长度污染 ⇒ 必配长度）
  FREQ · 词频偏移   诊断（需参照语料）
  LEN · 长度      **必须配报**（混淆控制）

【B 类指标（需外部判官）· 本轮不做】
  ESFP 式 SCD/CPC/AR/PSI、RES 抵抗性、ERR-DIR 错误方向性、人类盲评
  （见裁决 §2.5 / §3；降级路径：同家族 M2.7 + family-cross 矩阵；本轮不启用）

【C 类指标 · 已作废】
  typicality / NLL / perplexity / PMI / CPMI —— 依赖 logprobs，
  而 MiniMax-M3 **静默忽略** logprobs（请求不报错，choices[0].logprobs 字段不存在）；
  且本 sandbox 无 GPU / 2 核 3GB / 无 vllm ⇒ **自托管打分器物理不可行**。
  ⇒ 「相对被测模型自身的非最优」在无 logprobs 时**无法直接测量**，这是本轮的天花板，
    不是可以绕过的小问题（裁决 §5-3）。

【硬规则】
  1. **空数据不崩**：没有 runs/*.jsonl 时打印"无数据"并正常退出。
  2. **参照语料缺失 ⇒ RARE/FREQ 显式标"未计算"**，绝不用未经证实的替代品冒充。
  3. **零第三方依赖**：Wilcoxon 符号秩检验自带精确实现（n≤25 精确 DP）。
  4. **判据先跑、数据门先过**：F0 数据门不过 ⇒ 只报"数据不足"，不解读。

怎么跑
  python3 analyze.py --runs runs                 # 出报告（markdown 到 stdout）
  python3 analyze.py --runs runs --embed         # 先补 embedding（需 API key），再出报告
  python3 analyze.py --runs runs --out report.md # 落盘
  python3 analyze.py --power                     # 采样数 N 的检出力曲线
================================================================================
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API_URL = "https://api.minimaxi.com/v1/embeddings"
EMB_MODEL = "embo-01"
KEY_ENV = "MINIMAX_SUBSCRIPTION_KEY"

# ================================================================= 文本工具
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
SENT_SPLIT = re.compile(r"[。！？!?；;\n]+|(?<=[。！？!?；;])\s*")
PUNCT = "，。！？；：、（）《》〈〉「」『』【】“”‘’…—－,.;:!?()[]\"'~·"


def norm_text(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()


def sentences(text: str) -> list:
    out = []
    for s in SENT_SPLIT.split(text or ""):
        s = (s or "").strip()
        if s:
            out.append(s)
    return out


def cjk_ratio(t: str) -> float:
    if not t:
        return 0.0
    n = len(t)
    return sum(1 for c in t if CJK_RE.match(c)) / n


# ---------------------------------------------------------------- 分词
try:  # jieba 可选：有则用，没有则退化为字符 n-gram（结果不可跨环境比较，故报告会标注）
    import jieba  # type: ignore
    jieba.setLogLevel(60)
    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    _HAS_JIEBA = False

STOPWORDS = set(
    "的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 那 "
    "什么 怎么 这个 那个 因为 所以 但是 但 而且 如果 一下 一些 什么 我们 他们 它们 可以 已经 还是 "
    "被 让 把 给 对 与 及 或 而 并 之 其 它 她 他 时 里 后 前 中 大 小 多 少 没 吗 呢 吧 啊 呀 嘛".split()
)

_FALLBACK_RE = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z]+|\d+")


def tokenize(text: str) -> list:
    """中文分词。有 jieba 用 jieba；否则用「中文 2-gram + 拉丁词」的退化方案。"""
    if not text:
        return []
    if _HAS_JIEBA:
        return [t.strip() for t in jieba.lcut(text) if t.strip()]
    out = []
    for m in _FALLBACK_RE.finditer(text):
        s = m.group(0)
        if CJK_RE.match(s):
            if len(s) == 1:
                out.append(s)
            else:
                out.extend(s[i:i + 2] for i in range(len(s) - 1))
        else:
            out.append(s.lower())
    return out


def content_tokens(text: str) -> list:
    toks = [t for t in tokenize(text) if len(t) >= 2 and t not in STOPWORDS]
    return [t for t in toks if not t.isdigit() or len(t) >= 3]


def char_ngrams(text: str, n: int = 3) -> set:
    t = re.sub(r"\s+", "", text or "")
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / float(len(a) + len(b) - inter)


# ================================================================= 统计
def wilcoxon_signed_rank(diffs: list, alternative: str = "greater") -> dict:
    """Wilcoxon 符号秩检验（自带实现）。

    · n ≤ 25：精确分布（对子集和做 DP，零假设下子集均匀）
    · n > 25：正态近似 + 连续性校正
    · 零差值剔除（Wilcoxon 标准做法），并报告剔除数
    返回 {n, n_used, stat, p, p_two_sided, method, zeros}
    """
    d = [float(x) for x in diffs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    zeros = sum(1 for x in d if x == 0.0)
    d = [x for x in d if x != 0.0]
    n = len(d)
    out = {"n": len(diffs), "n_used": n, "zeros": zeros, "stat": None,
           "p": None, "p_two_sided": None, "method": None, "alternative": alternative}
    if n < 5:
        out["method"] = "样本不足（n<5）"
        out["p"] = 1.0
        out["p_two_sided"] = 1.0
        return out
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    w_minus = sum(r for r, x in zip(ranks, d) if x < 0)
    out["stat"] = round(w_plus, 3)
    out["w_plus"] = round(w_plus, 3)
    out["w_minus"] = round(w_minus, 3)
    if n <= 25:
        # 精确分布：counts[s] = 和为 s 的子集个数
        total_rank = int(round(sum(ranks)))
        counts = [0] * (total_rank + 1)
        counts[0] = 1
        for r in ranks:
            ri = int(round(r))
            for s in range(total_rank, ri - 1, -1):
                counts[s] += counts[s - ri]
        total = 1 << n
        wi = int(round(w_plus))
        ge = sum(counts[wi:])          # P(W+ >= w)
        le = sum(counts[:wi + 1])      # P(W+ <= w)
        out["method"] = "精确（n=%d）" % n
        if alternative == "greater":
            p = ge / float(total)
        elif alternative == "less":
            p = le / float(total)
        else:
            p = min(1.0, 2.0 * min(ge, le) / float(total))
    else:
        mu = n * (n + 1) / 4.0
        var = n * (n + 1) * (2 * n + 1) / 24.0
        sd = math.sqrt(var)
        out["method"] = "正态近似（n=%d）" % n
        if alternative == "greater":
            z = (w_plus - mu - 0.5) / sd
            p = 1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2)))
        elif alternative == "less":
            z = (mu - w_plus - 0.5) / sd
            p = 1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2)))
        else:
            z = (abs(w_plus - mu) - 0.5) / sd
            p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2))))
        p = min(1.0, max(0.0, p))
    out["p"] = p
    out["p_two_sided"] = min(1.0, 2.0 * p) if alternative != "two-sided" else p
    return out


def sign_test(diffs: list) -> dict:
    """符号检验（Wilcoxon 的稳健性对照）。"""
    d = [x for x in diffs if x is not None and x != 0]
    n = len(d)
    if n == 0:
        return {"n": 0, "p": 1.0}
    k = sum(1 for x in d if x > 0)
    # 单侧二项检验（用 math.comb）
    tail = sum(math.comb(n, i) for i in range(k, n + 1)) / float(2 ** n)
    return {"n": n, "pos": k, "p": min(1.0, tail), "p_two_sided": min(1.0, 2 * tail)}


def holm(pairs: list, alpha: float = 0.05) -> list:
    """Holm-Bonferroni 多重比较校正。pairs = [(name, p), ...]"""
    idx = sorted(range(len(pairs)), key=lambda i: pairs[i][1])
    m = len(pairs)
    out = [None] * m
    prev = 0.0
    for rank, i in enumerate(idx):
        adj = min(1.0, (m - rank) * pairs[i][1])
        adj = max(adj, prev)
        prev = adj
        out[i] = {"name": pairs[i][0], "p_raw": pairs[i][1], "p_holm": round(adj, 5),
                  "reject": adj < alpha}
    return out


def mdl_measure(values: list, threshold: float) -> float:
    """MTLD 词汇多样性（McCarthy & Jarvis 2010；唯一不随文本长度变化的指标）。"""
    factors, ttr = 0.0, 1.0
    types, tokens = set(), 0
    for v in values:
        tokens += 1
        if v not in types:
            types.add(v)
            ttr = len(types) / float(tokens)
        else:
            ttr = len(types) / float(tokens)
        if ttr <= threshold:
            factors += 1
            types, tokens = set(), 0
            ttr = 1.0
    if tokens > 0:
        factors += (1.0 - ttr) / (1.0 - threshold)
    if factors == 0:
        return float("nan")
    return len(values) / factors


def ttr(values: list) -> float:
    if not values:
        return float("nan")
    return len(set(values)) / float(len(values))


# ================================================================= A 类指标
FS_DEFS = [
    ("sent_len_mean", lambda S, t: _mean([len(x) for x in S])),
    ("sent_len_std", lambda S, t: _sd([len(x) for x in S])),
    ("sent_len_median", lambda S, t: _median([len(x) for x in S])),
    ("long_sent_ratio", lambda S, t: _ratio([len(x) for x in S], 30, 10 ** 9)),
    ("short_sent_ratio", lambda S, t: _ratio([len(x) for x in S], 0, 10)),
    ("question_ratio", lambda S, t: _punct_ratio(S, "？?")),
    ("exclaim_ratio", lambda S, t: _punct_ratio(S, "！!")),
    ("comma_density", lambda S, t: _punct_ratio(S, "，,")),
    ("dun_density", lambda S, t: _punct_ratio(S, "、")),
    ("semicolon_density", lambda S, t: _punct_ratio(S, "；;")),
    ("dash_density", lambda S, t: _punct_ratio(S, "—－-–")),
    ("quote_density", lambda S, t: _punct_ratio(S, "“”「」『』\"'")),
    ("bracket_density", lambda S, t: _punct_ratio(S, "（）()《》【】")),
    ("ellipsis_density", lambda S, t: _punct_ratio(S, "……")),
    ("causal_conn", lambda S, t: _kw_ratio(S, ["因为", "所以", "因此", "由于", "于是", "故而", "正因为"])),
    ("turning_conn", lambda S, t: _kw_ratio(S, ["但是", "但", "却", "然而", "不过", "虽然", "尽管"])),
    ("progressive_conn", lambda S, t: _kw_ratio(S, ["而且", "并且", "甚至", "更", "还", "以及"])),
    ("conditional_conn", lambda S, t: _kw_ratio(S, ["如果", "假如", "只要", "除非", "一旦", "倘若"])),
    ("modal_density", lambda S, t: _kw_ratio(S, ["能", "会", "要", "可以", "应该", "必须", "可能", "或许", "愿意", "不肯"])),
    ("negation_density", lambda S, t: _kw_ratio(S, ["不", "没", "没有", "无", "非", "别", "无法", "不能"])),
    ("first_person", lambda S, t: _kw_ratio(S, ["我", "我们", "我的", "咱们"])),
    ("second_person", lambda S, t: _kw_ratio(S, ["你", "您", "你们", "你的"])),
    ("passive_marker", lambda S, t: _kw_ratio(S, ["被", "受到", "遭到", "得以", "加以"])),
    ("psych_verb", lambda S, t: _kw_ratio(S, ["想", "觉得", "知道", "明白", "相信", "担心", "希望", "以为", "记得", "忘了"])),
    ("perception_verb", lambda S, t: _kw_ratio(S, ["看", "听", "见", "摸", "尝", "闻", "盯", "盯住", "端详"])),
    ("body_word", lambda S, t: _kw_ratio(S, ["手", "眼", "心", "头", "背", "腿", "呼吸", "疼", "累", "肩", "喉咙", "指尖"])),
    ("time_marker", lambda S, t: _kw_ratio(S, ["昨天", "今天", "明天", "后来", "那时", "以前", "之后", "当年", "三年前", "十年前", "那年"])),
    ("quantity", lambda S, t: _kw_ratio(S, ["一", "两", "三", "四", "五", "六", "七", "八", "九", "十", "半", "几"])),
    ("concrete_noun", lambda S, t: _kw_ratio(S, ["门", "桌", "椅", "灯", "路", "车", "药", "杯", "盒", "楼", "街", "窗", "锅", "伞", "盒", "车", "纸", "手机"])),
    ("abstract_noun", lambda S, t: _kw_ratio(S, ["事情", "问题", "意义", "价值", "精神", "状态", "层面", "维度", "关系", "机制", "原则", "意义"])),
    ("nominalization", lambda S, t: _kw_ratio(S, ["性", "化", "感", "度", "主义", "化"])),
    ("modal_neg_cooccur", lambda S, t: _ratio2(S, ["能", "会", "要", "必须", "应该"], ["不", "没", "无法", "不能"])),
    ("imperative_ratio", lambda S, t: _imperative(S)),
    ("line_break_density", lambda S, t: (t or "").count("\n") / max(1, len(t or "")) * 100),
    ("dialogue_density", lambda S, t: _punct_ratio(S, "“”「」『』")),
    ("exposition_ratio", lambda S, t: _ratio2(S, ["因为", "所以", "因此", "由于"], ["我", "你", "他", "她"])),
]


def _mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return sum(xs) / len(xs) if xs else 0.0


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return 0.0
    m = len(xs) // 2
    return float(xs[m]) if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2.0


def _sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    return statistics.pstdev(xs)


def _ratio(xs, lo, hi):
    if not xs:
        return 0.0
    return sum(1 for x in xs if lo < x <= hi) / float(len(xs))


def _punct_ratio(sents, chars):
    n = sum(len(s) for s in sents) or 1
    return sum(s.count(c) for s in sents for c in chars) / float(n) * 100


def _kw_ratio(sents, words):
    n = sum(len(s) for s in sents) or 1
    return sum(s.count(w) for s in sents for w in words) / float(n) * 100


def _ratio2(sents, a, b):
    na = sum(s.count(w) for s in sents for w in a)
    nb = sum(s.count(w) for s in sents for w in b)
    return (na / float(nb)) if nb else 0.0


def _imperative(sents):
    if not sents:
        return 0.0
    n = 0
    for s in sents:
        head = s[:2]
        if not any(p in head for p in ("我", "你", "他", "她", "它", "咱")) and len(s) <= 18:
            n += 1
    return n / float(len(sents))


def fs_signature(text: str) -> dict:
    """FS · 功能词签名：中文句法/功能词分布的多维向量（不依赖英文 Biber 工具链）。"""
    S = sentences(text)
    return {name: round(float(fn(S, text)), 4) for name, fn in FS_DEFS}


def len_stats(text: str) -> dict:
    S = sentences(text)
    return {
        "chars": len(re.sub(r"\s+", "", text or "")),
        "sentences": len(S),
        "mean_sent_len": round(_mean([len(x) for x in S]), 2),
    }


def lex_stats(text: str) -> dict:
    toks = content_tokens(text)
    return {
        "mtld": round(mdl_measure(toks, 0.72), 3) if len(toks) > 5 else None,
        "ttr": round(ttr(toks), 4) if toks else None,
        "n_content_tokens": len(toks),
    }


def restatement_filter(out_text: str, stance: dict, thresh: float = 0.6) -> list:
    """把"直接复述立场档案"的句子剔除，返回剩下的句子。

    判据（裁决 §2.3 判据 4 的前置）：与立场档案任一字段句子的字符 3-gram Jaccard ≥ thresh
    ⇒ 视为复述句，不计入 KWH 的分子与分母。
    """
    st_sents = []
    for k, _ in STANCE_FIELDS_LOCAL:
        v = stance.get(k)
        if isinstance(v, list):
            v = "；".join(str(x) for x in v)
        if v:
            st_sents.extend(sentences(str(v)))
    st_ng = [char_ngrams(s, 3) for s in st_sents if s]
    keep, dropped = [], 0
    for s in sentences(out_text):
        g = char_ngrams(s, 3)
        if st_ng and max((jaccard(g, x) for x in st_ng), default=0.0) >= thresh:
            dropped += 1
            continue
        keep.append(s)
    return keep, dropped


def kwh_stats(out_text: str, stance: dict) -> dict:
    """KWH · 取舍约束关键词命中率（排除直接复述句）。"""
    if not stance:
        return {"kwh": None, "restate_ratio": None, "n_keywords": 0}
    raw = stance.get("取舍约束") or ""
    if isinstance(raw, list):
        raw = "；".join(str(x) for x in raw)
    kws = [k for k in content_tokens(str(raw)) if len(k) >= 2]
    kws = list(dict.fromkeys(kws))
    keep, dropped = restatement_filter(out_text, stance)
    if not kws:
        return {"kwh": None, "restate_ratio": None, "n_keywords": 0}
    joined = "".join(keep)
    hit = sum(1 for k in kws if k in joined)
    all_sents = sentences(out_text)
    return {
        "kwh": round(hit / float(len(kws)), 4),
        "kwh_hit": hit,
        "n_keywords": len(kws),
        "restate_ratio": round(dropped / float(len(all_sents)), 4) if all_sents else 0.0,
    }


# 立场字段名（与 runner.py 保持一致；analyze.py 不 import runner 以免带 API 依赖）
STANCE_FIELDS_LOCAL = [
    ("自选极性", "只能是 pole_a 或 pole_b。"),
    ("立场核心", ""), ("选它的理由", ""), ("来历", ""), ("取舍约束", ""),
    ("拒绝", ""), ("语气", ""), ("强度封顶", ""), ("锚定问题", ""),
]


# ================================================================= embedding
def embed(texts: list, timeout: int = 120) -> list:
    """调用 MiniMax embo-01 取 embedding。返回 [[float]*1536, ...]。"""
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise RuntimeError("环境变量 %s 未设置，无法调用 embedding 接口。" % KEY_ENV)
    payload = {"model": EMB_MODEL, "texts": texts, "type": "db"}
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer %s" % key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    vecs = raw.get("vectors") or raw.get("data") or []
    out = []
    for v in vecs:
        if isinstance(v, dict):
            v = v.get("embedding") or []
        out.append([float(x) for x in v])
    return out


def embed_all(records: list, cache_path: Path, batch: int = 8) -> dict:
    """给所有产出取 embedding，带缓存。返回 {record_key: vector}"""
    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    todo = []
    for r in records:
        k = r["key"]
        if k in cache or not r.get("output"):
            continue
        if k not in todo:
            todo.append(k)
    if todo:
        by_key = {r["key"]: r for r in records}
        print("[embed] 需要 %d 条新 embedding（embo-01）…" % len(todo), file=sys.stderr)
        for i in range(0, len(todo), batch):
            chunk = todo[i:i + batch]
            texts = [by_key[k]["output"][:6000] for k in chunk]
            try:
                vecs = embed(texts)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:200]
                print("[embed] HTTP %d: %s（**失败不算结论**）" % (e.code, body), file=sys.stderr)
                break
            except Exception as e:
                print("[embed] 失败: %s（**失败不算结论**）" % e, file=sys.stderr)
                break
            for k, v in zip(chunk, vecs):
                cache[k] = v
            time.sleep(0.2)
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return cache


def cos(a, b) -> float:
    if not a or not b:
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return num / (na * nb)


def vsub(a, b):
    return [x - y for x, y in zip(a, b)]


def vmean(vs):
    if not vs:
        return []
    n = len(vs)
    return [sum(v[i] for v in vs) / float(n) for i in range(len(vs[0]))]


def vnorm(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else v


# ================================================================= 数据装载
def load_records(runs_dir: Path) -> tuple:
    """读 runs/*.jsonl → (产出记录 list, 立场档案 dict)"""
    gens, stances = [], {}
    files = sorted(runs_dir.glob("*.jsonl")) if runs_dir.exists() else []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("error"):
                continue
            if r.get("kind") == "stance":
                sp = r.get("stance_profile") or {}
                if sp:
                    stances[(r.get("topic_id"), r.get("arm"))] = sp
            elif r.get("kind") == "gen":
                r["key"] = "%s|%s|%s|%s" % (r.get("arm"), r.get("topic_id"),
                                            r.get("seed"), r.get("polarity"))
                r["_file"] = f.name
                gens.append(r)
    return gens, stances


def load_reference_corpus(path: Path) -> dict:
    """参照语料 → {词频 dict, 字符 2-gram 频次 dict, 总词数, 元信息}"""
    if not path or not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    toks = content_tokens(text)
    from collections import Counter
    tf = Counter(toks)
    n = len(text)
    # 字符 2-gram
    flat = re.sub(r"\s+", "", text)
    cg = Counter(flat[i:i + 2] for i in range(max(0, len(flat) - 1)))
    return {"tf": dict(tf), "cg": dict(cg), "n_tokens": len(toks),
            "n_chars": n, "path": str(path),
            "sha256": _sha256_file(path)}


def _sha256_file(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()[:16]


# ================================================================= 主分析
def analyze(gens: list, stances: dict, emb: dict, corpus: dict, alpha: float = 0.05) -> dict:
    rep = {"n_records": len(gens), "arms": {}, "topics": {}, "criteria": [], "data_gates": []}

    # ---------- 批次检查（主控实测：embedding 绝对距离跨批差 3.9 倍 ⇒ 只有同批内可比）
    batches = {}
    for r in gens:
        b = r.get("batch_id") or "(未记录)"
        batches.setdefault(b, []).append(r)
    rep["batches"] = {b: len(v) for b, v in batches.items()}
    cross = []
    for tid in sorted({r.get("topic_id") for r in gens}):
        bs = {r.get("batch_id") or "(未记录)" for r in gens if r.get("topic_id") == tid}
        if len(bs) > 1:
            cross.append({"topic_id": tid, "batches": sorted(bs)})
    rep["cross_batch_topics"] = cross

    # ---------- 每条记录的特征
    feats = []
    for r in gens:
        txt = r.get("output") or ""
        st = r.get("stance_profile") or stances.get((r.get("topic_id"), r.get("arm"))) or {}
        f = {"key": r["key"], "arm": r.get("arm"), "topic_id": r.get("topic_id"),
             "seed": r.get("seed"), "polarity": r.get("polarity"),
             "self_polarity": r.get("self_polarity") or st.get("self_polarity"),
             "len": len_stats(txt), "lex": lex_stats(txt), "fs": fs_signature(txt),
             "system_chars": r.get("system_chars"), "stance_chars": r.get("stance_chars")}
        f["kwh"] = kwh_stats(txt, st) if st else {"kwh": None, "restate_ratio": None,
                                                  "n_keywords": 0}
        if corpus:
            f["rare"], f["freq"] = corpus_metrics(txt, corpus)
        feats.append(f)

    # ---------- 臂级汇总
    for arm in sorted({f["arm"] for f in feats if f["arm"]}):
        sub = [f for f in feats if f["arm"] == arm]
        rep["arms"][arm] = {
            "n": len(sub),
            "n_topics": len({f["topic_id"] for f in sub}),
            "chars_mean": round(_mean([f["len"]["chars"] for f in sub]), 1),
            "sentences_mean": round(_mean([f["len"]["sentences"] for f in sub]), 1),
            "mtld_mean": round(_mean([f["lex"]["mtld"] for f in sub]), 2),
            "ttr_mean": round(_mean([f["lex"]["ttr"] for f in sub]), 4),
            "kwh_mean": (round(_mean([f["kwh"]["kwh"] for f in sub]), 4)
                         if sub and sub[0]["kwh"].get("kwh") is not None else None),
            "restate_ratio_mean": (round(_mean([f["kwh"]["restate_ratio"] for f in sub]), 4)
                                   if sub and sub[0]["kwh"].get("restate_ratio") is not None else None),
            "system_chars_mean": round(_mean([f["system_chars"] for f in sub]), 1)
            if any(f["system_chars"] for f in sub) else None,
            "stance_chars_mean": round(_mean([f["stance_chars"] for f in sub]), 1)
            if any(f["stance_chars"] for f in sub) else None,
            "rare_mean": round(_mean([f.get("rare", 0) for f in sub]), 4) if corpus else None,
            "freq_mean": round(_mean([f.get("freq", 0) for f in sub]), 4) if corpus else None,
        }

    # ---------- PL · 极性位移（主判据）
    by_topic = {}
    for f in feats:
        by_topic.setdefault(f["topic_id"], []).append(f)
    pl = {}
    for tid, fs_ in by_topic.items():
        # 极性轴 v：裁决版 = 全部臂池化；基线版 = 仅 A/B（无立场/弱立场臂）
        # ⚠️ C 与 R1 持有**相反**的立场：若模型是"锚定"型的，它们的响应会互相抵消，
        #    把池化轴拉向噪声 ⇒ 同时给两版，并在两者不一致时告警。
        v = v_base = None
        epos = [emb.get(f["key"]) for f in fs_ if f["polarity"] == "P+" and emb.get(f["key"])]
        eneg = [emb.get(f["key"]) for f in fs_ if f["polarity"] == "P-" and emb.get(f["key"])]
        if epos and eneg:
            v = vnorm(vsub(vmean(epos), vmean(eneg)))
        bp = [emb.get(f["key"]) for f in fs_ if f["polarity"] == "P+" and f["arm"] in ("A", "B")
              and emb.get(f["key"])]
        bn = [emb.get(f["key"]) for f in fs_ if f["polarity"] == "P-" and f["arm"] in ("A", "B")
              and emb.get(f["key"])]
        if bp and bn:
            v_base = vnorm(vsub(vmean(bp), vmean(bn)))
        axis_agree = (round(cos(v, v_base), 4) if (v and v_base) else None)
        row = {"v_available": bool(v), "axis_cos_all_vs_base": axis_agree,
               "axis_warning": (axis_agree is not None and axis_agree < 0.8)}
        for arm in ("A", "B", "C", "R1", "R2"):
            ep = [emb.get(f["key"]) for f in fs_ if f["arm"] == arm and f["polarity"] == "P+"
                  and emb.get(f["key"])]
            en = [emb.get(f["key"]) for f in fs_ if f["arm"] == arm and f["polarity"] == "P-"
                  and emb.get(f["key"])]
            e0 = [emb.get(f["key"]) for f in fs_ if f["arm"] == arm and f["polarity"] == "P0"
                  and emb.get(f["key"])]
            pols = {f["self_polarity"] for f in fs_
                    if f["arm"] == arm and f.get("self_polarity")}
            entry = {"n_p": len(ep), "n_m": len(en), "self_polarity": sorted(pols) or None}
            if v and ep and en:
                delta = cos(vmean(ep), v) - cos(vmean(en), v)
                entry["delta"] = round(delta, 5)
                if v_base and ep and en:
                    entry["delta_base_axis"] = round(
                        cos(vmean(ep), v_base) - cos(vmean(en), v_base), 5)
                if len(pols) == 1:
                    p = sorted(pols)[0]
                    entry["aligned"] = round(delta if p == "pole_a" else -delta, 5)
                    if "delta_base_axis" in entry:
                        entry["aligned_base"] = round(
                            entry["delta_base_axis"] if p == "pole_a" else -entry["delta_base_axis"], 5)
            else:
                entry["delta"] = None
                entry["aligned"] = None
            row[arm] = entry
        # δ_state：臂间直接位移（沿极性轴），P0 条件，不依赖"锚定 vs 放大"的机制假设
        a0 = [emb.get(f["key"]) for f in fs_ if f["arm"] == "A" and f["polarity"] == "P0"
              and emb.get(f["key"])]
        for arm in ("B", "C", "R1", "R2"):
            e0 = [emb.get(f["key"]) for f in fs_ if f["arm"] == arm and f["polarity"] == "P0"
                  and emb.get(f["key"])]
            entry = row.get(arm) or {}
            if v and a0 and e0:
                d = cos(vmean(e0), v) - cos(vmean(a0), v)
                entry["delta_state"] = round(d, 5)
                if len(entry.get("self_polarity") or []) == 1:
                    p = entry["self_polarity"][0]
                    entry["delta_state_aligned"] = round(d if p == "pole_a" else -d, 5)
            else:
                entry["delta_state"] = None
                entry["delta_state_aligned"] = None
            row[arm] = entry
        pl[tid] = row
    rep["pl"] = pl

    # ---------- SC · 塌缩度（主判据）
    sc = {}
    sc_between = {}
    for arm in ("A", "B", "C", "R1", "R2"):
        for tid in sorted(by_topic):
            keys = [f["key"] for f in feats if f["arm"] == arm and f["topic_id"] == tid
                    and f["polarity"] == "P0"]
            vs = [emb.get(k) for k in keys]
            vs = [v for v in vs if v]
            if len(vs) < 2:
                continue
            ds = [1.0 - cos(a, b) for a, b in itertools.combinations(vs, 2)]
            sc.setdefault(arm, {})[tid] = {"n": len(vs),
                                           "mean_pairwise_distance": round(_mean(ds), 5)}
    # 臂间距离矩阵（P0）：SC_between(X,Y) = 两臂产出两两平均 1−cos
    for x, y in itertools.combinations(("A", "B", "C", "R1", "R2"), 2):
        for tid in sorted(by_topic):
            vx = [emb.get(f["key"]) for f in feats if f["arm"] == x and f["topic_id"] == tid
                  and f["polarity"] == "P0" and emb.get(f["key"])]
            vy = [emb.get(f["key"]) for f in feats if f["arm"] == y and f["topic_id"] == tid
                  and f["polarity"] == "P0" and emb.get(f["key"])]
            if not vx or not vy:
                continue
            ds = [1.0 - cos(a, b) for a in vx for b in vy]
            sc_between.setdefault("%s-%s" % (x, y), {})[tid] = {
                "n": len(vx) * len(vy), "mean_distance": round(_mean(ds), 5)}
    # SC_gap：臂间距离 − 臂内采样噪声（主控的 if-then）
    sc_gap = {}
    for tid in sorted(by_topic):
        bc = sc_between.get("A-C", {}).get(tid)
        wi = sc.get("A", {}).get(tid)
        if bc and wi:
            sc_gap[tid] = round(bc["mean_distance"] - wi["mean_pairwise_distance"], 5)
    rep["sc"] = sc
    rep["sc_between"] = sc_between
    rep["sc_gap"] = sc_gap

    # ---------- FS 随立场的变化（判据 4 后半句）
    fs_var = {}
    for arm in ("A", "B", "C", "R1", "R2"):
        vp = [f["fs"] for f in feats if f["arm"] == arm and f["polarity"] == "P+"]
        vm = [f["fs"] for f in feats if f["arm"] == arm and f["polarity"] == "P-"]
        if not vp or not vm:
            continue
        mp = {k: _mean([d[k] for d in vp]) for k in vp[0]}
        mm = {k: _mean([d[k] for d in vm]) for k in vm[0]}
        diff = {k: abs(mp[k] - mm[k]) for k in mp}
        # 归一化：除以该维在两极内部的平均离散度
        base = {}
        for k in mp:
            base[k] = _mean([d[k] for d in vp] + [d[k] for d in vm])
        fs_var[arm] = {"fs_p_minus_m_abs_mean": round(_mean(list(diff.values())), 5),
                       "fs_dim_changed_ratio": round(
                           sum(1 for k in diff if diff[k] > 1e-9) / float(len(diff)), 3),
                       "normalized_shift": round(_mean(
                           [diff[k] / base[k] if base[k] else 0.0 for k in diff]), 5)}
    rep["fs_variation"] = fs_var

    # ---------- 判据判定（裁决 §2.3）
    rep["criteria"] = judge_criteria(rep, pl, sc, feats, alpha)
    return rep


def corpus_metrics(text: str, corpus: dict) -> tuple:
    """RARE · n-gram 稀有度 与 FREQ · 词频偏移（均需参照语料）。"""
    from collections import Counter
    toks = content_tokens(text)
    if not toks:
        return 0.0, 0.0
    tf = corpus["tf"]
    total = max(1, corpus["n_tokens"])
    floor = 1.0
    rare = 0.0
    for t in toks:
        c = tf.get(t, 0)
        p = max(c, floor) / float(total)
        rare += -math.log2(p)
    rare = rare / len(toks)
    ct = Counter(toks)
    keys = set(ct) | set(tf)
    dot = sum((ct.get(k, 0) / len(toks)) * (tf.get(k, 0) / total) for k in keys)
    na = math.sqrt(sum((ct.get(k, 0) / len(toks)) ** 2 for k in keys))
    nb = math.sqrt(sum((tf.get(k, 0) / total) ** 2 for k in keys))
    freq = (1.0 - dot / (na * nb)) if na and nb else 0.0
    return round(rare, 4), round(freq, 4)


def judge_criteria(rep: dict, pl: dict, sc: dict, feats: list, alpha: float = 0.05) -> list:
    """按裁决 §2.3 的判据 1–5 判定（每条给 if-then + 实测值 + 判决）。"""
    out = []
    tids = sorted(pl.keys())

    def deltas(arm, key="aligned"):
        vals = []
        for t in tids:
            row = pl[t].get(arm)
            if row and row.get(key) is not None:
                vals.append((t, row[key]))
        return vals

    # 判据 1（主）：δ_C^aligned > δ_A
    dC = dict(deltas("C"))
    dA = dict((t, v) for t, v in deltas("A", "delta"))
    common = [t for t in dC if t in dA]
    if len(common) >= 5:
        diffs = [dC[t] - dA[t] for t in common]
        w = wilcoxon_signed_rank(diffs, "greater")
        out.append({"id": "判据1", "name": "δ_C^aligned > δ_A（状态确实组织了取舍）",
                    "n": len(common), "mean_C": round(_mean([dC[t] for t in common]), 5),
                    "mean_A": round(_mean([dA[t] for t in common]), 5),
                    "test": w, "sign": sign_test(diffs),
                    "verdict": ("通过" if (w["p"] is not None and w["p"] < alpha
                                           and _mean([dC[t] for t in common])
                                           > _mean([dA[t] for t in common]))
                                else "不通过")})
    else:
        out.append({"id": "判据1", "name": "δ_C^aligned > δ_A", "n": len(common),
                    "verdict": "数据不足（n<5 题）",
                    "note": "极性轴需要 P+/P− 两种极性的产出；先用 --cf 跑出配对数据"})

    # 判据 2（对照）：δ_R2^aligned ≈ 0
    dR2 = dict(deltas("R2"))
    common2 = [t for t in dR2 if t in dA]
    if len(common2) >= 5:
        w0 = wilcoxon_signed_rank([dR2[t] for t in common2], "greater")
        wA = wilcoxon_signed_rank([abs(dA[t]) for t in common2], "greater")
        out.append({"id": "判据2", "name": "δ_R2^aligned ≈ 0（无关立场不应产生位移）",
                    "n": len(common2), "mean_R2": round(_mean([dR2[t] for t in common2]), 5),
                    "mean_abs_A": round(_mean([abs(dA[t]) for t in common2]), 5),
                    "test_vs_0": w0,
                    "verdict": ("通过" if (w0["p"] is None or w0["p"] >= alpha) else "不通过")})
    else:
        out.append({"id": "判据2", "name": "δ_R2^aligned ≈ 0", "n": len(common2),
                    "verdict": "数据不足（n<5 题）"})

    # 判据 3（塌缩）：C 臂采样间距离 > A 臂
    tsc = [t for t in sc.get("C", {}) if t in sc.get("A", {})]
    if len(tsc) >= 5:
        diffs = [sc["C"][t]["mean_pairwise_distance"] - sc["A"][t]["mean_pairwise_distance"]
                 for t in tsc]
        w = wilcoxon_signed_rank(diffs, "greater")
        out.append({"id": "判据3", "name": "SC_C > SC_A（C 臂不是模板化复现）",
                    "n": len(tsc),
                    "mean_C": round(_mean([sc["C"][t]["mean_pairwise_distance"] for t in tsc]), 5),
                    "mean_A": round(_mean([sc["A"][t]["mean_pairwise_distance"] for t in tsc]), 5),
                    "test": w,
                    "verdict": ("通过" if (w["p"] is not None and w["p"] < alpha) else "不通过")})
    else:
        out.append({"id": "判据3", "name": "SC_C > SC_A", "n": len(tsc),
                    "verdict": "数据不足（n<5 题或采样数不足）"})

    # 判据 4（排除复述）：KWH_C > KWH_A，且 FS 签名随立场变化（C 变、A 不变）
    kw = {}
    for arm in ("A", "B", "C", "R1", "R2"):
        vals = [f["kwh"]["kwh"] for f in feats if f["arm"] == arm and f["kwh"].get("kwh") is not None]
        if vals:
            kw[arm] = _mean(vals)
    kwh_ok = (kw.get("C") is not None and kw.get("A") is not None and kw["C"] > kw["A"])
    fsv = rep.get("fs_variation", {})
    fs_c = fsv.get("C", {}).get("normalized_shift")
    fs_a = fsv.get("A", {}).get("normalized_shift")
    fs_ok = (fs_c is not None and fs_a is not None and fs_c > fs_a)
    out.append({"id": "判据4", "name": "KWH_C > KWH_A 且 FS 随立场变化（C 变、A 不变）",
                "kwh": {k: round(v, 4) for k, v in kw.items()},
                "fs_normalized_shift": {k: fsv.get(k, {}).get("normalized_shift")
                                        for k in ("A", "C", "R1", "R2")},
                "verdict": ("通过" if (kwh_ok and fs_ok) else "不通过"),
                "note": "两半都要满足：只满足 KWH 仍可能只是复述"})

    # 判据 3b（主控的 if-then）：C 与 A 的臂间距离 > A 臂内部采样噪声
    tg = [t for t in rep.get("sc_gap", {}) if t in sc.get("A", {})]
    if len(tg) >= 5:
        diffs = [rep["sc_gap"][t] for t in tg]
        w = wilcoxon_signed_rank(diffs, "greater")
        out.append({"id": "判据3b", "name": "SC_gap(A↔C) > SC_within(A)（C 不是采样噪声）",
                    "n": len(tg), "mean_gap": round(_mean(diffs), 5),
                    "mean_between_AC": round(_mean([rep["sc_between"]["A-C"][t]["mean_distance"]
                                                    for t in tg]), 5),
                    "mean_within_A": round(_mean([sc["A"][t]["mean_pairwise_distance"]
                                                 for t in tg]), 5),
                    "test": w,
                    "verdict": ("通过" if (w["p"] is not None and w["p"] < alpha) else "不通过")})
    else:
        out.append({"id": "判据3b", "name": "SC_gap(A↔C) > SC_within(A)", "n": len(tg),
                    "verdict": "数据不足（n<5 题）"})

    # 判据 6（**符号稳健**，本轮新增）：δ_state^C(对齐) > 0
    # 含义：状态把内容**往自己那一侧**推了（不依赖"锚定 vs 放大"的机制假设）。
    dsC = {}
    dsA = {}
    for t in tids:
        r = pl[t].get("C") or {}
        if r.get("delta_state_aligned") is not None:
            dsC[t] = r["delta_state_aligned"]
        ra = pl[t].get("A") or {}
        if ra.get("delta_state") is not None:
            dsA[t] = ra["delta_state"]
    common6 = [t for t in dsC if t in dsA]
    if len(common6) >= 5:
        w = wilcoxon_signed_rank([dsC[t] for t in common6], "greater")
        out.append({"id": "判据6", "name": "δ_state^C(对齐) > 0（状态把内容往自己那侧推）",
                    "n": len(common6), "mean_C_aligned": round(_mean([dsC[t] for t in common6]), 5),
                    "mean_A_raw": round(_mean([dsA[t] for t in common6]), 5),
                    "test": w,
                    "verdict": ("通过" if (w["p"] is not None and w["p"] < alpha) else "不通过"),
                    "note": "与判据1 互补：判据1 的方向依赖'锚定 vs 放大'的机制假设，"
                            "本判据不依赖该假设（臂间直接位移）"})
    else:
        out.append({"id": "判据6", "name": "δ_state^C(对齐) > 0", "n": len(common6),
                    "verdict": "数据不足（n<5 题）"})

    # 判据 5（负结果）：δ_C^aligned ≈ δ_A ⇒ 状态未组织取舍
    j1 = next((c for c in out if c["id"] == "判据1"), None)
    if j1 and j1.get("test"):
        p = j1["test"].get("p")
        if p is not None and p >= alpha:
            out.append({"id": "判据5", "name": "δ_C^aligned ≈ δ_A ⇒ 负结果：状态未组织取舍",
                        "verdict": "**负结果**（C 臂文本读起来再有思想也不改变这个判决）",
                        "detail": "判据1 未通过（p=%.4f ≥ α=%.2f）" % (p, alpha)})
        else:
            out.append({"id": "判据5", "name": "δ_C^aligned ≈ δ_A ⇒ 负结果",
                        "verdict": "不适用（判据1 已通过）"})
    else:
        out.append({"id": "判据5", "name": "δ_C^aligned ≈ δ_A ⇒ 负结果",
                    "verdict": "数据不足"})
    return out


# ================================================================= 检出力
def power_curve(sd_within: float, n_topics: int, shift: float, n_grid=None) -> list:
    """模拟法检出力曲线：给定题内抽样噪声 sd_within、题数 n_topics、真实位移 shift，
    求每臂每题采样数 N 达到 80% 检出力所需的 N。"""
    n_grid = n_grid or [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20]
    rng = __import__("random").Random(20261020)
    rows = []
    for N in n_grid:
        reps = 2000
        hits = 0
        for _ in range(reps):
            diffs = []
            for _t in range(n_topics):
                dc = rng.gauss(shift, sd_within / math.sqrt(N))
                da = rng.gauss(0.0, sd_within / math.sqrt(N))
                diffs.append(dc - da)
            w = wilcoxon_signed_rank(diffs, "greater")
            if w["p"] is not None and w["p"] < 0.05:
                hits += 1
        rows.append({"N": N, "power": round(hits / float(reps), 3),
                     "se_delta": round(sd_within / math.sqrt(N), 5)})
    return rows


# ================================================================= 报告
def render_report(rep: dict, meta: dict) -> str:
    L = []
    A = L.append
    A("# 第四组 · Phase 0 分析报告")
    A("")
    A("生成时间：%s ｜ 模型：%s" % (meta.get("ts"), meta.get("model")))
    A("")
    A("> 口径：**无判官**（跨家族 judge 401 不可用、人类盲评本轮不做）⇒ 全部结论只来自")
    A("> 纯统计 + embedding 几何。**不测「好不好」，只测「状态是否组织了取舍」。**")
    A("")
    A("## 0. 运行元信息")
    A("")
    for k, v in meta.items():
        if k in ("ts", "model"):
            continue
        A("- **%s**：%s" % (k, v))
    A("")
    if not rep.get("n_records"):
        A("## ⚠️ 无数据")
        A("")
        A("`runs/` 下没有可用的产出记录（jsonl 为空或全部带 error）。")
        A("**本报告不含任何效果性结论**；先跑 `python3 runner.py --scope phase0` 再回来看。")
        A("")
        return "\n".join(L)

    A("## 0b. 批次检查（**同批内才可相对比较**）")
    A("")
    A("- 批次数：**%d**（%s）" % (len(rep.get("batches", {})),
                                  "、".join("%s:%d 条" % (k, v)
                                            for k, v in sorted(rep.get("batches", {}).items()))))
    cb = rep.get("cross_batch_topics") or []
    if cb:
        A("- ⚠️ **跨批题**：%s —— 这些题的各臂数据来自不同批次，"
          "**绝对距离/塌缩度的比较无效**（实测跨批差 3.9 倍），"
          "只能作题内相对排序，或重新同批跑。" % "、".join(c["topic_id"] for c in cb))
    else:
        A("- ✅ 无跨批题：所有题的所有臂在**同一批**内产出，绝对距离可比。")
    A("")

    A("## 1. 四臂 L1 对比表（描述性，不作判据）")
    A("")
    A("| 臂 | n | 题数 | 字数均值 | 句数均值 | MTLD | TTR | KWH | 复述句比例 | system 字数 | 状态字数 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for arm, d in rep["arms"].items():
        A("| %s | %d | %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            arm, d["n"], d["n_topics"], d["chars_mean"], d["sentences_mean"],
            d["mtld_mean"], d["ttr_mean"], d["kwh_mean"], d["restate_ratio_mean"],
            d["system_chars_mean"], d["stance_chars_mean"]))
    A("")
    A("> 长度配平检查：system 字数是**唯一**的臂间长度差来源，必须与所有主判据一起读。")
    A("")

    A("## 2. PL · 极性位移（主判据）")
    A("")
    A("| 题 | v 可用 | A δ | B δ | C δ | C δ(对齐) | R1 δ | R1 δ(对齐) | R2 δ | R2 δ(对齐) | C 自选极性 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for tid, row in sorted(rep.get("pl", {}).items()):
        def g(arm, k):
            v = row.get(arm)
            if not v:
                return "—"
            return v.get(k) if v.get(k) is not None else "—"
        pols = set()
        for arm in ("C", "R1", "R2"):
            v = row.get(arm)
            if v and v.get("self_polarity"):
                pols.add(v["self_polarity"][0])
        A("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            tid, "是" if row.get("v_available") else "否",
            g("A", "delta"), g("B", "delta"), g("C", "delta"), g("C", "aligned"),
            g("R1", "delta"), g("R1", "aligned"), g("R2", "delta"), g("R2", "aligned"),
            ",".join(sorted(pols)) or "—"))
    A("")
    A("> 对齐规则：`δ_aligned = δ × (+1 if self_polarity==pole_a else −1)`（裁决 §2.2 防伪②）。")
    A("> A/B 臂无立场档案 ⇒ 无自选极性 ⇒ 只报原始 δ。")
    A("")
    A("### 2b. δ_state · 臂间直接位移（符号稳健，判据 6 用）")
    A("")
    A("| 题 | 极性轴一致性 cos(v_all, v_base) | A δ_state | C δ_state | C δ_state(对齐) | R1 δ_state(对齐) | R2 δ_state(对齐) |")
    A("|---|---|---|---|---|---|---|")
    for tid, row in sorted(rep.get("pl", {}).items()):
        def gs(arm, k):
            v = row.get(arm) or {}
            return v.get(k) if v.get(k) is not None else "—"
        A("| %s | %s | %s | %s | %s | %s | %s |" % (
            tid, row.get("axis_cos_all_vs_base", "—"),
            gs("A", "delta_state"), gs("C", "delta_state"),
            gs("C", "delta_state_aligned"), gs("R1", "delta_state_aligned"),
            gs("R2", "delta_state_aligned")))
    A("")
    warn = [t for t, r in rep.get("pl", {}).items() if r.get("axis_warning")]
    if warn:
        A("> ⚠️ **极性轴稀释告警**：题 %s 上 `cos(v_all, v_base) < 0.8` —— "
          "把 C/R1（相反立场）也池化进轴估计会互相抵消，δ 会被噪声淹没。"
          % "、".join(sorted(warn)))
        A("> ⇒ 这类题应改用基线轴（仅 A/B）重算：`delta_base_axis` 列。")
        A("")
    A("## 2c. 臂间距离矩阵（SC_between，P0 条件）")
    A("")
    sb = rep.get("sc_between", {})
    tids_sc = sorted({t for d in sb.values() for t in d})
    if sb:
        A("| 臂对 | " + " | ".join(tids_sc) + " | 均值 |")
        A("|---" * (len(tids_sc) + 2) + "|")
        for k in sorted(sb):
            vals = [sb[k][t]["mean_distance"] for t in tids_sc if t in sb[k]]
            A("| %s | %s | %s |" % (k, " | ".join(str(sb[k][t]["mean_distance"])
                                                  for t in tids_sc if t in sb[k]),
                                    round(_mean(vals), 5)))
        A("")
    if rep.get("sc_gap"):
        A("**SC_gap = SC_between(A↔C) − SC_within(A)**（主控的 if-then：C 必须显著超出采样噪声）")
        A("")
        A("| " + " | ".join(sorted(rep["sc_gap"])) + " | 均值 |")
        A("|---" * (len(rep["sc_gap"]) + 2) + "|")
        vals = list(rep["sc_gap"].values())
        A("| " + " | ".join(str(rep["sc_gap"][t]) for t in sorted(rep["sc_gap"]))
          + " | %s |" % round(_mean(vals), 5))
        A("")

    A("## 3. SC · 塌缩度（主判据）")
    A("")
    A("| 臂 | " + " | ".join(sorted(rep.get("sc", {}).get("A", {}).keys()) or ["—"]) + " | 均值 |")
    A("|---" * (len(rep.get("sc", {}).get("A", {})) + 2) + "|")
    for arm, per in rep.get("sc", {}).items():
        tids = sorted(per.keys())
        A("| %s | %s | %s |" % (arm, " | ".join(str(per[t]["mean_pairwise_distance"]) for t in tids),
                                round(_mean([per[t]["mean_pairwise_distance"] for t in tids]), 5)))
    A("")

    A("## 4. 判据判定（裁决 §2.3）")
    A("")
    for c in rep.get("criteria", []):
        A("### %s · %s" % (c.get("id"), c.get("name")))
        A("")
        for k, v in c.items():
            if k in ("id", "name", "verdict"):
                continue
            A("- %s：%s" % (k, v))
        A("- **判决：%s**" % c.get("verdict"))
        A("")

    A("## 5. 未计算 / 不可算的指标（诚实清单）")
    A("")
    for line in meta.get("not_computed", []):
        A("- %s" % line)
    A("")
    return "\n".join(L)


# ================================================================= 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description="第四组 Phase 0 分析器")
    ap.add_argument("--runs", default="runs", help="runs 目录（默认 runs）")
    ap.add_argument("--embed", action="store_true", help="先补 embedding（需 API key）")
    ap.add_argument("--ref", default="", help="参照语料（纯文本，中文）")
    ap.add_argument("--out", default="", help="报告落盘路径")
    ap.add_argument("--json", default="", help="机器可读结果落盘路径")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--power", action="store_true", help="只打印采样数 N 的检出力曲线")
    ap.add_argument("--sd-within", type=float, default=0.0,
                    help="题内抽样噪声 sd（做 --power 时用；0 = 用默认值）")
    ap.add_argument("--n-topics", type=int, default=10, help="--power 用的题数")
    ap.add_argument("--shift", type=float, default=0.02, help="--power 用的真实位移")
    args = ap.parse_args()

    if args.power:
        sd = args.sd_within or 0.02
        rows = power_curve(sd, args.n_topics, args.shift)
        print("检出力曲线（sd_within=%.4f, n_topics=%d, shift=%.4f, α=0.05 单侧）"
              % (sd, args.n_topics, args.shift))
        print("%6s %10s %12s" % ("N", "power", "se(δ)"))
        for r in rows:
            print("%6d %10.3f %12.5f" % (r["N"], r["power"], r["se_delta"]))
        need = next((r["N"] for r in rows if r["power"] >= 0.8), None)
        print("\n达到 80%% 检出力所需 N = %s" % (need if need else ">20（需更多题数或更大效应）"))
        return 0

    runs_dir = Path(args.runs)
    if not runs_dir.is_absolute():
        runs_dir = HERE / runs_dir
    gens, stances = load_records(runs_dir)
    print("[load] %s：产出 %d 条，立场档案 %d 份" % (runs_dir, len(gens), len(stances)), file=sys.stderr)

    emb = {}
    if args.embed and gens:
        emb = embed_all(gens, runs_dir / "embeddings.json")
    elif (runs_dir / "embeddings.json").exists():
        try:
            emb = json.loads((runs_dir / "embeddings.json").read_text(encoding="utf-8"))
        except Exception:
            emb = {}

    corpus = load_reference_corpus(Path(args.ref)) if args.ref else {}
    not_computed = []
    if not corpus:
        not_computed.append("**RARE / FREQ 未计算**：参照语料缺失（`--ref <中文语料>`）。"
                            "按铁律，宁可显示未计算，也不用未经证实的替代品冒充。")
    if not emb:
        not_computed.append("**PL / SC 未计算**：embedding 缺失（`--embed` 补齐；"
                            "embo-01 接口：POST https://api.minimaxi.com/v1/embeddings，"
                            "{model:embo-01, texts:[...], type:db}）。")
    not_computed.append("**typicality / NLL / perplexity / PMI / CPMI 已作废**："
                        "MiniMax-M3 静默忽略 logprobs（请求不报错，choices[0].logprobs 不存在），"
                        "且 sandbox 无 GPU / 2 核 3GB / 无 vllm ⇒ 自托管打分器物理不可行。")
    not_computed.append("**ESFP 式 SCD/CPC/AR/PSI、RES、ERR-DIR、人类盲评**：需外部判官，"
                        "跨家族 judge（OpenRouter）401 不可用 ⇒ 本轮不做（裁决 §2.5）。")

    rep = analyze(gens, stances, emb, corpus, alpha=args.alpha)
    meta = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "MiniMax-M3",
        "分词器": "jieba" if _HAS_JIEBA else "退化方案（中文 2-gram）——**跨环境不可比**",
        "参照语料": (corpus.get("path") + " sha256=" + corpus.get("sha256", "")
                     + " 字符数=%d" % corpus.get("n_chars", 0)) if corpus else "**未提供**",
        "embedding": ("%d 条（%s）" % (len(emb), "embo-01") if emb else "**未提供**"),
        "产出记录数": rep.get("n_records", 0),
        "立场档案数": len(stances),
        "not_computed": not_computed,
    }
    text = render_report(rep, meta)
    print(text)
    if args.out:
        p = Path(args.out)
        if not p.is_absolute():
            p = HERE / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print("\n[write] %s" % p, file=sys.stderr)
    if args.json:
        p = Path(args.json)
        if not p.is_absolute():
            p = HERE / p
        p.write_text(json.dumps({"report": rep, "meta": {k: v for k, v in meta.items()
                                                         if k != "not_computed"}},
                                ensure_ascii=False, indent=2), encoding="utf-8")
        print("[write] %s" % p, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
