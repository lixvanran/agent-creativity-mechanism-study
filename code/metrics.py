"""
新颖性度量 —— 纯 Python + numpy 实现（沙箱无 sklearn / torch / 外部 embedding）。

为什么要两个指标：
    之前的报告已经指出，语义相似度类单一指标会把「不同的废话」判成低新颖性。
    本实验不引入外部 embedding（沙箱装不上，且 API 不提供 embedding 模型），
    因此改为**双指标交叉验证**：
        M1 = TF-IDF 余弦距离   （词级，反映用词与主题分布的差异）
        M2 = 字符 4-gram Jaccard 距离（字形级，能捕捉改写/同义替换）
    两者若一致 → 结论较稳；两者背离 → 该单元的「新颖」判定不可信，分析时须标记。

    这本身就是实验的一部分：**测量工具有效性是结果之一，不是前置假设。**
"""
from __future__ import annotations
import math, re
from collections import Counter
from typing import List, Dict
import numpy as np

_CJK = re.compile(r"[一-鿿]")
_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_NUM = re.compile(r"\d+")

def tokenize(text: str) -> List[str]:
    """中文按字（无分词器），英文/数字按词。"""
    toks = list(_CJK.findall(text))
    toks += [w.lower() for w in _LATIN.findall(text)]
    toks += _NUM.findall(text)
    return toks

def char_ngrams(text: str, n: int = 4) -> set:
    s = re.sub(r"\s+", "", text)
    return {s[i:i+n] for i in range(max(len(s) - n + 1, 1))}

# ---------------------------------------------------------------- TF-IDF

def _tfidf_matrix(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0))
    docs = [Counter(tokenize(t)) for t in texts]
    N = len(docs)
    df = Counter()
    for d in docs:
        for w in d:
            df[w] += 1
    vocab = sorted(df)
    if not vocab:
        return np.zeros((N, 0))
    idx = {w: i for i, w in enumerate(vocab)}
    idf = np.zeros(len(vocab))
    for w, i in idx.items():
        idf[i] = math.log((N + 1) / (df[w] + 1)) + 1.0
    M = np.zeros((N, len(vocab)))
    for r, d in enumerate(docs):
        for w, c in d.items():
            M[r, idx[w]] = (c / max(len(d), 1)) * idf[idx[w]]
    nrm = np.linalg.norm(M, axis=1, keepdims=True)
    nrm[nrm == 0] = 1.0
    return M / nrm

def pairwise_distances(M: np.ndarray) -> np.ndarray:
    if M.shape[0] < 2:
        return np.zeros((M.shape[0], M.shape[0]))
    S = M @ M.T
    np.clip(S, -1.0, 1.0, out=S)
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)
    return D

def _mean_upper(d: np.ndarray) -> float:
    if d.shape[0] < 2:
        return 0.0
    iu = np.triu_indices(d.shape[0], k=1)
    return float(np.mean(d[iu]))

def novelty_tfidf(texts: List[str]) -> float:
    """批次内平均两两 TF-IDF 余弦距离。"""
    return _mean_upper(pairwise_distances(_tfidf_matrix(texts)))

def novelty_ngram(texts: List[str], n: int = 4) -> float:
    """批次内平均两两 字符n-gram Jaccard 距离。"""
    sets = [char_ngrams(t, n) for t in texts]
    k = len(sets)
    if k < 2:
        return 0.0
    vals = []
    for i in range(k):
        for j in range(i + 1, k):
            a, b = sets[i], sets[j]
            if not a or not b:
                vals.append(0.0); continue
            inter = len(a & b)
            union = len(a | b)
            vals.append(1.0 - inter / union)
    return float(np.mean(vals)) if vals else 0.0

# ------------------------------------------------- 选中答案的「离群度」

def winner_distances(winner: str, pool: List[str]) -> Dict[str, float]:
    """选中答案到批次质心的距离 —— 用来判断『它到底选得有多怪』。"""
    if not pool:
        return dict(tfidf=0.0, ngram=0.0)
    pool = [p for p in pool if p.strip()] or [winner]
    Mw = _tfidf_matrix([winner] + pool)[0:1]
    Mp = _tfidf_matrix([winner] + pool)[1:]
    if Mp.shape[0] == 0:
        return dict(tfidf=0.0, ngram=0.0)
    s = Mp @ Mw.T
    tf = float(np.mean(1.0 - np.clip(s.ravel(), -1, 1)))
    ws = char_ngrams(winner)
    ns = [char_ngrams(p) for p in pool]
    jl = []
    for b in ns:
        if not ws or not b:
            continue
        jl.append(1.0 - len(ws & b) / len(ws | b))
    return dict(tfidf=tf, ngram=float(np.mean(jl)) if jl else 0.0)

# ------------------------------------------------- 指标可靠性诊断

def metric_agreement(dist_a: List[float], dist_b: List[float]) -> Dict[str, float]:
    """两个指标的秩相关（Spearman，手写实现）与均值差 —— 用来判断测量本身可不可信。"""
    n = min(len(dist_a), len(dist_b))
    if n < 3:
        return dict(spearman=float('nan'), mean_a=float('nan'), mean_b=float('nan'))
    a, b = dist_a[:n], dist_b[:n]
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0]*len(v); i = 0
        while i < len(order):
            j = i
            while j+1 < len(order) and v[order[j+1]] == v[order[i]]:
                j += 1
            avg = (i+j)/2 + 1
            for k in range(i, j+1):
                r[order[k]] = avg
            i = j+1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra)/n, sum(rb)/n
    num = sum((ra[i]-ma)*(rb[i]-mb) for i in range(n))
    da = math.sqrt(sum((x-ma)**2 for x in ra)); db = math.sqrt(sum((x-mb)**2 for x in rb))
    rho = num/(da*db) if da and db else float('nan')
    return dict(spearman=rho, mean_a=sum(a)/n, mean_b=sum(b)/n)
