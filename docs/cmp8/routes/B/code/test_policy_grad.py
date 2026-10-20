#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 策略梯度的**对拍测试**（修 F4：解析式梯度与真实梯度对不上）。

要证明的事：
  ❶ `policy_logprob_grad` 给出的 ∇_w log π(a|s) 与**中心差分数值梯度**一致
     （标准化 softmax 的 log-π 梯度含 mean/std 的 Jacobian）。
  ❷ 旧实现用的解析式 `φ_a − Σ_i π_i φ_i` **不是**这个梯度（对标准化 softmax **有偏**）
     ⇒ 本设计必须用精确版；这条差异被**量化**出来而不是靠嘴说。

用法：python3 test_policy_grad.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

from ops_v2 import policy_probs  # noqa: E402
from train_policy_v2 import policy_logprob_grad  # noqa: E402

RNG = np.random.default_rng(20261020)


def build(n_cands=6, d=30, scale=0.4):
    F = RNG.normal(0, scale, size=(n_cands, d))
    w = RNG.normal(0, 0.5, size=d)
    s = F @ w
    return F, s, w


def numeric_logprob_grad(F, s, tau, choice, w, h=1e-6):
    def logpi(wv):
        return float(np.log(policy_probs(F @ wv, tau)[choice]))
    g = np.zeros(len(w))
    for j in range(len(w)):
        wp = w.copy(); wp[j] += h
        wm = w.copy(); wm[j] -= h
        g[j] = (logpi(wp) - logpi(wm)) / (2 * h)
    return g


def legacy_grad(F, s, tau, choice):
    """旧实现用的解析式（**不是**标准化 softmax 的 log-π 梯度）。"""
    p = policy_probs(s, tau)
    return F[choice] - (p[:, None] * F).sum(axis=0)


def check():
    out = {"cases": []}
    ok_exact, ok_biased = True, True
    for tau in (0.6, 1.2, 2.0, 3.5):
        for choice in range(3):
            F, s, w = build()
            ana = policy_logprob_grad(F, s, tau, choice)
            num = numeric_logprob_grad(F, s, tau, choice, w)
            leg = legacy_grad(F, s, tau, choice)
            den = max(float(np.linalg.norm(num)), 1e-12)
            d_exact = float(np.linalg.norm(ana - num) / den)
            d_leg = float(np.linalg.norm(leg - num) / den)
            out["cases"].append(dict(tau=tau, choice=choice,
                                     rel_err_exact=round(d_exact, 9),
                                     rel_err_legacy=round(d_leg, 6)))
            ok_exact &= (d_exact < 1e-5)
            ok_biased &= (d_leg > 1e-3)      # 旧式确实**不是**真梯度
    out["exact_matches_numeric"] = bool(ok_exact)
    out["legacy_form_is_biased"] = bool(ok_biased)
    out["max_rel_err_exact"] = max(c["rel_err_exact"] for c in out["cases"])
    out["min_rel_err_legacy"] = min(c["rel_err_legacy"] for c in out["cases"])
    out["PASS"] = bool(ok_exact and ok_biased)
    return out


if __name__ == "__main__":
    import json
    r = check()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["PASS"] else 1)
