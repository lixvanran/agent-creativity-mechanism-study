#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ v2 特征空间的**回归断言**（"仪器自身要被验"）。

要证明的事：
  ❶ **存在性见证**成立：用一条显式的"状态依赖规则"构造出的 w，其 argmax **随图状态改变**
     （none→VERIFY / unmentioned→SPLIT / supported·contradicted→GEN_PLAIN / unverified→VERIFY）。
     ⇒ v2 的特征空间**能表达**"当 target 处于状态 K 就做 op X"这类规则。
  ❷ **旧 14 维空间做不到**：三个"带 target 的 op"的相对顺序在 4 个状态下**恒定**
     ⇒ 任何这样的规则都**不可表达**（对任意 w）。
  ❸ v2 的特征向量在 5 个状态下**互不相同**。

**测试自身也必须被验过** ⇒ 提供 `--mutate` 模式：把 v2 的交互项清零（退化成纯加性）
⇒ ❶ 必须 FAIL、❷ 仍然成立 ⇒ 报不出 FAIL ⇒ 这个测试是摆设。

用法：
  python3 test_v2_witness.py            # 正常跑（应当 PASS）
  python3 test_v2_witness.py --mutate   # 变异注入（应当 FAIL）
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.environ.get("CMP8_REPO", "/workspace/lab/cmp8repo")
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402

from ops_v2 import CLASSES, FEAT_DIM, FEATURE_NAMES, OPS_V2, candidates, op_features_v2  # noqa: E402

STATES = ("none", "unmentioned", "supported", "contradicted", "unverified")
TXT = "断言占位文本甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳"      # 等长 ⇒ 把 f[11]（长度）扣掉
EXPECTED = {"none": "VERIFY", "unmentioned": "SPLIT", "supported": "GEN_PLAIN",
            "contradicted": "GEN_PLAIN", "unverified": "VERIFY"}


def make_graph(state):
    from creativity_lab.ops import Graph
    g = Graph()
    a1 = g.add("ANSWER", "甲答案" * 20, op="GEN_PLAIN")
    c = g.add("CLAIM", TXT, parent=a1, op="EXTRACT")
    if state == "unmentioned":
        g.nodes[c].verdict = "未提及"
    elif state == "supported":
        g.nodes[c].verdict = "支持"
    elif state == "contradicted":
        g.nodes[c].verdict = "矛盾"
    elif state == "unverified":
        g.nodes[c].verdict = None
    elif state != "none":
        raise ValueError(state)
    return g, (None if state == "none" else g.nodes[c])


def witness_w(mutate=False):
    """显式构造"状态依赖规则"：target 未核验⇒VERIFY；依据未覆盖⇒SPLIT；没有断言⇒生成。"""
    ci = {c: i for i, c in enumerate(CLASSES)}
    w = np.zeros(FEAT_DIM)
    w[FEATURE_NAMES.index("%s×t1_tgt_unverified" % CLASSES[ci["VERIFY"]])] = 1.0
    w[FEATURE_NAMES.index("%s×t1_tgt_unverified" % CLASSES[ci["PROCESS"]])] = -1.0
    w[FEATURE_NAMES.index("%s×t2_tgt_unmentioned" % CLASSES[ci["PROCESS"]])] = 1.0
    w[FEATURE_NAMES.index("%s×g1_no_claims" % CLASSES[ci["GENERATE"]])] = 0.5
    if mutate:
        # 变异：把**所有交叉项**清零 ⇒ 退化成"纯加性"（= 旧 14 维的性质）
        for i, nm in enumerate(FEATURE_NAMES):
            if "×" in nm:
                w[i] = 0.0
    return w


def argmax_by_state(w):
    out = {}
    for st in STATES:
        g, tgt = make_graph(st)
        cands = candidates(g, n_verify_done=1)
        s = np.array([float(w @ op_features_v2(g, op, t)) for op, t in cands])
        out[st] = cands[int(np.argmax(s))][0]
    return out


def legacy_order_invariant():
    """旧 14 维：三个"带 target 的 op"的相对顺序在 4 个状态下必须恒定。

    ⚠️ 检查方式：**对每个 w 分别**看它在 4 个状态下的顺序是否一致
       （不是把不同 w 的顺序混在一起比 —— 那样当然会不同）。
    """
    from creativity_lab.ops import op_features as legacy_features
    rng = np.random.default_rng(20261020)
    bad = 0
    for _rep in range(50):
        w = rng.normal(0, 1, size=14)
        orders = set()
        for st in ("unverified", "unmentioned", "supported", "contradicted"):
            g, tgt = make_graph(st)
            sc = {op: float(w @ np.asarray(legacy_features(g, op, tgt, 1)))
                  for op in ("EXTRACT", "VERIFY", "SPLIT")}
            orders.add(tuple(sorted(sc, key=lambda k: -sc[k])))
        if len(orders) != 1:
            bad += 1
    return bad == 0


def v2_features_differ():
    vecs = {}
    for st in STATES:
        g, tgt = make_graph(st)
        vecs[st] = np.stack([op_features_v2(g, op, tgt if op in ("VERIFY", "SPLIT", "EXTRACT") else None)
                              for op in OPS_V2])
    diff = 0
    for st in STATES:
        if st == STATES[0]:
            continue
        if not np.allclose(vecs[st], vecs[STATES[0]]):
            diff += 1
    return diff == len(STATES) - 1


def check(mutate=False):
    res = {}
    got = argmax_by_state(witness_w(mutate))
    res["argmax_by_state"] = got
    res["witness_holds"] = (got == EXPECTED)
    res["argmax_varies"] = len(set(got.values())) > 1
    res["legacy_order_state_invariant"] = legacy_order_invariant()
    res["v2_features_differ_across_states"] = v2_features_differ()
    res["PASS"] = bool(res["witness_holds"] and res["argmax_varies"]
                       and res["legacy_order_state_invariant"]
                       and res["v2_features_differ_across_states"])
    return res


if __name__ == "__main__":
    import json
    mut = "--mutate" in sys.argv
    r = check(mut)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    if mut:
        print("\n[变异模式] 期望 FAIL：交互项被清零 ⇒ 见证不成立")
        sys.exit(0 if not r["PASS"] else 1)
    sys.exit(0 if r["PASS"] else 1)
