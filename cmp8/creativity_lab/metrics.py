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
