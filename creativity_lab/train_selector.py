# -*- coding: utf-8 -*-
"""S2：训练纯函数 selector 的小权重。

学习对象：从候选池里挑一份答案的**打分函数**。一组可审计的权重，不是自由文本架构。
**特征全部可从答案文本算出，不含任何作者硬编码的「洞见类目」。**

判决方式（唯一重要的）：在**留出题目**上，selector 选出的候选，其实际奖励
是否超过平凡基线？基线：恒选某臂 / 选最长 / 选断言最多 / 随机。

两种奖励分开跑：
  【方法定义】差分奖励 = 相对同题直调的新增已核验断言（方法的核心）
  【诊断】绝对奖励   = 已支持断言密度（**不是方法定义的奖励**，
                      单独跑只为回答「候选池内部到底有没有可学的方差」）
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM        # noqa: E402
from creativity_lab.metrics import _mat      # noqa: E402

OUT = "runs/train2"
FEATS = ["len", "n_claims", "claim_digits", "claim_legal_ref", "claim_money",
         "list_struct", "legal_density", "avg_claim_len", "consistency"]
ARMS = ("direct", "dual_fuse", "dual_select")


def embed_rows(ts):
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    return _mat(LLM().embed(uniq))[idx]


def features(text, claims, consistency):
    n = max(len(claims), 1)
    digits = sum(1 for c in claims if re.search(r"\d", c))
    legal = sum(1 for c in claims if re.search(r"第[一二三四五六七八九十百零\d]+条|条例|办法|规定|司法解释|法[第]", c))
    money = sum(1 for c in claims if re.search(r"[¥￥$%]|元|万|千|百分", c))
    struct = len(re.findall(r"^\s*\d+[\.、）)]", text or "", re.M))
    avg = sum(len(c) for c in claims) / n
    return [len(text), len(claims), digits, legal, money, struct, legal / n, avg, consistency]


def consistency(text, others):
    if not others:
        return 0.0
    M = embed_rows([text] + list(others))
    return float(np.mean([M[0] @ M[i] for i in range(1, M.shape[0])]))


def ridge(X, y, lam=1.0):
    mu, sd = X.mean(0), X.std(0)
    sd = np.where(sd == 0, 1.0, sd)
    Z = np.hstack([np.ones((Z_ := ((X - mu) / sd).shape[0], 1)), ((X - mu) / sd)])
    w = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ y)
    return dict(mu=mu.tolist(), sd=sd.tolist(), w=w.tolist())


def score(model, X):
    mu, sd, w = np.array(model["mu"]), np.array(model["sd"]), np.array(model["w"])
    Z = np.hstack([np.ones((X.shape[0], 1)), (X - mu) / sd])
    return Z @ w


def main():
    recs = json.load(open("%s/records.json" % OUT, encoding="utf-8"))
    texts = json.load(open("%s/texts.json" % OUT, encoding="utf-8"))
    claims = json.load(open("%s/claims.json" % OUT, encoding="utf-8"))
    recs = [r for r in recs if not r["dead"]]
    if not recs:
        print("无有效记录，训练不启动")
        return

    print("== 特征提取 ==", flush=True)
    rows = []
    for r in recs:
        k = r["key"]
        same = [texts[k2] for k2 in texts
                if k2.split("|")[0] == k.split("|")[0]
                and k2.split("|")[1] == k.split("|")[1] and k2 != k]
        rows.append((features(texts[k], claims[k], consistency(texts[k], same)),
                     r["tid"], r["arm"]))
    X = np.array([r[0] for r in rows], dtype=float)
    groups = np.array([r[1] for r in rows])
    arms = np.array([r[2] for r in rows])
    y_diff = np.array([r["reward"] for r in recs], dtype=float)
    y_abs = np.array([r["n_sup"] / max(r["length"], 1) * 100 for r in recs], dtype=float)
    print("  样本 %d  特征 %d  题 %d" % (X.shape[0], X.shape[1], len(set(groups))))

    tids = sorted(set(groups))
    hold = set(tids[-4:])
    tr = np.array([g not in hold for g in groups])
    te = ~tr
    print("  训练题 %d，留出题 %d：%s" % (len(set(groups[tr])), len(hold), sorted(hold)))

    def group_pick(mask, pick):
        """对留出集每题按 pick(候选下标数组) 选一个，返回选中的奖励列表。"""
        out = []
        for g in sorted(set(groups[mask])):
            idx = np.where(mask & (groups == g))[0]
            if len(idx):
                out.append(int(idx[pick(idx)]))
        return out

    def run_reward(tag, yv, show_weights):
        print("\n" + "=" * 78)
        print(tag)
        print("=" * 78)
        print("  留出集奖励 std=%.5f  非零比例 %.1f%%"
              % (float(yv[te].std()), 100 * float((yv[te] != 0).mean())))
        res = {}
        for a in ARMS:
            p = group_pick(te, lambda idx, a=a: int(np.where(arms[idx] == a)[0][0])
                           if (arms[idx] == a).any() else 0)
            if p: res["恒选 " + a] = float(np.mean([yv[i] for i in p]))
        res["选最长"] = float(np.mean([yv[i] for i in group_pick(
            te, lambda idx: int(np.argmax([X[i, 0] for i in idx])))]))
        res["选断言最多"] = float(np.mean([yv[i] for i in group_pick(
            te, lambda idx: int(np.argmax([X[i, 1] for i in idx])))]))
        rng = np.random.default_rng(0)
        res["随机"] = float(np.mean([np.mean([yv[i] for i in group_pick(
            te, lambda idx: int(rng.integers(len(idx))))]) for _ in range(50)]))
        model = ridge(X[tr], yv[tr], lam=1.0)
        sc = score(model, X)
        res["训练出的 selector"] = float(np.mean([yv[i] for i in group_pick(
            te, lambda idx: int(np.argmax([sc[i] for i in idx])))]))
        for name, v in sorted(res.items(), key=lambda x: -x[1]):
            print("  %-18s 留出集 %.5f" % (name, v))
        sel = res["训练出的 selector"]
        others = max(v for n, v in res.items() if n != "训练出的 selector")
        win = sel > others
        print("  → selector 超过所有平凡基线: %s" % ("是" if win else "否"))
        if show_weights:
            print("\n  学到的权重（标准化后）:")
            w = np.array(model["w"])
            for i, f in enumerate(["截距"] + FEATS):
                print("    %-16s %+.4f" % (f, w[i]))
        return res, model, win

    res_d, model_d, win_d = run_reward("【方法定义】差分奖励：相对同题直调的新增已核验断言", y_diff, False)
    res_a, model_a, win_a = run_reward("【诊断】绝对奖励：已支持断言密度（非方法定义）", y_abs, True)

    print("\n" + "=" * 78)
    print("总结")
    print("=" * 78)
    print("  方法定义奖励（差分）：selector 胜出 = %s" % ("是" if win_d else "否"))
    print("  诊断奖励（绝对）  ：selector 胜出 = %s" % ("是" if win_a else "否"))
    json.dump(dict(features=FEATS, holdout=list(hold),
                   diff=res_d, abs=res_a, win_diff=win_d, win_abs=win_a,
                   model_abs=model_a),
              open("%s/selector.json" % OUT, "w"), ensure_ascii=False, indent=1)
    print("\n模型已存 %s/selector.json" % OUT)


if __name__ == "__main__":
    main()
