"""度量。**全部只吃数据，不吃作者先验。**

关键约束（对应复盘错误 2）：参照系必须由调用方从**真实产出**构造。
本模块不含任何题目专有的关键词。
"""
from __future__ import annotations
import itertools, math
import numpy as np
from creativity_lab.client import cosine


def _mat(emb):
    M = np.array(emb, dtype=float)
    return M / np.maximum(np.linalg.norm(M, axis=1, keepdims=True), 1e-12)


def escape(cand_vecs: list, ref_vecs: list) -> float:
    """候选离参照系质心有多远。参照系通常是同题的直接采样。"""
    if not cand_vecs or not ref_vecs: return 0.0
    r = _mat(ref_vecs)
    c = _mat([cand_vecs]).mean(axis=0)
    c = c / max(float(np.linalg.norm(c)), 1e-12)
    return float(1.0 - np.mean([cosine(v, c) for v in r]))


def spread(cand_vecs: list) -> float:
    """批内两两距离中位数。"""
    if len(cand_vecs) < 2: return 0.0
    ds = [1.0 - cosine(a, b) for a, b in itertools.combinations(cand_vecs, 2)]
    ds.sort()
    return ds[len(ds) // 2]


def effective_rank(cand_vecs: list) -> float:
    """PCA 谱的参与比 (Σλ)²/Σλ²。一个模态≈1，K 个互异模态≈K。"""
    if len(cand_vecs) < 2: return 1.0
    s = np.linalg.svd(_mat(cand_vecs), compute_uv=False)
    s2 = s ** 2
    return float(s2.sum() ** 2 / max((s2 ** 2).sum(), 1e-12))


def modes(cand_vecs: list, r: float = 0.05) -> int:
    """余弦距离阈值 r 下的连通分量数 —— 字面意义的「分成了几块」。"""
    n = len(cand_vecs)
    if n == 0: return 0
    par = list(range(n))
    def f(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for i, j in itertools.combinations(range(n), 2):
        if 1.0 - cosine(cand_vecs[i], cand_vecs[j]) < r:
            a, b = f(i), f(j)
            if a != b: par[a] = b
    return len({f(i) for i in range(n)})


def dispersion(emb_list: list) -> float:
    """同臂多次重复之间的两两相似度均值（越低=越不重复）。"""
    if len(emb_list) < 2: return float("nan")
    return float(np.mean([cosine(a, b) for a, b in itertools.combinations(emb_list, 2)]))
