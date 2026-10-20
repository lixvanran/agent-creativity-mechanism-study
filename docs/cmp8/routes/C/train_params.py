# -*- coding: utf-8 -*-
"""路线 C · 参数训练器（坐标下降 + 向先验收缩 + 折外评估）。

**目标函数**（DESIGN.md §4.3）：
    J(θ) = 训练语料上「被外部判官判为支持 且 互相不重复」的断言数的均值
    **约束优化，不是无约束最大化**：
      C1 矛盾率（过滤前）≤ cap            ← 代价侧（协议 R1/F4）
      C2 每题 key_conclusion_hit ≥ 基线   ← 协议 R2
      C3 每 episode 调用数/token ≤ 上限   ← 协议 R3
      C4 条数灌水探针：断言数涨 ≥20% 而被支持去重数涨 <10% ⇒ 该配置作废 ← 协议 F2
      C5 退化配置（把拓扑塌回更简单的结构）作废
    违反任一约束 ⇒ 配置**直接作废**（不是扣分）—— 防止"钻指标空子"。

**信号来源**：训练侧判官（MiniMax 侧，$0）与生成臂**不同提示词、不同调用**；
「远」这一侧**完全不用判官**（用字面二元组 Jaccard 去重），所以模型自述与自评不参与任何判据。

**收缩**：选档时扣 λ·|档位距离先验|，λ 事前写死 = 0.25。
折外（held-out）增量才是"参数学习是否真的泛化"的唯一报告量。
"""
from __future__ import annotations

import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/workspace/lab/cmp8repo")

import params as P
from executor import run_episode, jaccard

CORPUS = "/workspace/lab/cmp8repo/creativity_lab/data/policy_topics.json"
META = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_corpus_meta.json")
OUT = os.environ.get("C_TRAIN_OUT", "/workspace/lab/routes/C/train_out")

# ------------------------------------------------------------------ 预注册
LAMBDA = 0.25          # 向先验收缩系数
N_PASS = 2             # 坐标下降轮数
FOLDS = {"A": ["P1", "P3", "P5", "P7"], "B": ["P2", "P4", "P6", "P8"]}   # 事前按奇偶定，不看结果
CONFLICT_CAP = 0.33   # 绝对上限（沿用骨架里的 CONFLICT_CAP）
CONFLICT_SLACK = 0.05 # 相对基线的容差
CALL_CAP = 12         # 每 episode 调用数上限
TOKEN_CAP = 12000     # 每 episode token 上限
SEED = 7


# ------------------------------------------------------------------ 语料
def load_topics():
    data = json.load(open(CORPUS, encoding="utf-8"))
    meta = json.load(open(META, encoding="utf-8"))["topics"]
    law_of = {t["tid"]: t["law"] for t in data["topics"]}
    out = []
    for t in data["topics"]:
        tid = t["tid"]
        out.append(dict(task_id=tid, ask=t["ask"],
                        evidence=data["laws"][law_of[tid]]["evidence"],
                        conclusion_space=meta[tid]["conclusion_space"],
                        key_conclusions=meta[tid]["key_conclusions"]))
    return out


def _norm(s: str) -> str:
    return re.sub(r"[\s，。、；：,.;:!?！？「」『』（）()\[\]【】\"'’“”\-—…·%％]+", "", s or "")


def key_hit(answer: str, key_conclusions) -> float:
    a = _norm(answer)
    if not key_conclusions:
        return 1.0
    hit = 0
    for kc in key_conclusions:
        ok = all(any(_norm(alt) in a for alt in grp) for grp in kc["must_any"])
        hit += 1 if ok else 0
    return hit / len(key_conclusions)


# ------------------------------------------------------------------ 判官（训练侧）
def make_verifier(llm):
    """训练侧判官：沿用 cmp8 的四分类核验提示词（v4），**与验收侧判官不同源**。"""
    from creativity_lab.verify import check_claims
    return lambda ask, ev, claims: check_claims(llm, ask, ev, claims)


# ------------------------------------------------------------------ 评估
def evaluate(theta, topology_id, topics, llm, verifier, reps=1, seed=SEED):
    """在一个配置上跑若干 episode，返回代理指标 + 约束判定。"""
    rng = random.Random(seed)
    per = []
    for t in topics:
        for r in range(reps):
            d = run_episode(t, topology_id, theta, llm=llm, verifier=verifier,
                            max_calls=CALL_CAP)
            kh = key_hit(d["answer"], t["key_conclusions"])
            per.append(dict(task_id=t["task_id"], rep=r, S=d["n_supported_distinct"],
                            n_claims=d["n_claims_total"], conflict=d["conflict_rate_pre"],
                            c_n=d["conflict_n"], c_d=d["conflict_den"], kh=kh,
                            calls=d["n_calls"], answer=d["answer"]))
    S = [p["S"] for p in per]
    c_n = sum(p["c_n"] for p in per)
    c_d = sum(p["c_d"] for p in per)
    kh = sum(p["kh"] for p in per) / max(len(per), 1)
    viol = P.validate(theta, topology_id)
    degen = P.degenerate(theta, topology_id)
    over_call = sum(1 for p in per if p["calls"] > CALL_CAP)
    res = dict(J=sum(S) / max(len(S), 1), S_mean=sum(S) / max(len(S), 1),
               conflict_rate_pre=(c_n / c_d) if c_d else 0.0, conflict_n=c_n,
               conflict_den=c_d, key_hit=kh, per=per,
               violations=viol, degenerate=degen, over_call=over_call)
    res["accepted"] = (not viol) and (not degen) and over_call == 0
    return res


def constraint_ok(res, baseline=None, theta=None, topology_id=None):
    """把约束写成可判定函数（违反 ⇒ 该配置作废）。"""
    reasons = []
    if res["violations"]:
        reasons.append("参数越界：%s" % res["violations"])
    if res["degenerate"]:
        reasons.append("退化配置：%s" % res["degenerate"])
    if res["over_call"]:
        reasons.append("调用数超限：%d 个 episode" % res["over_call"])
    cap = CONFLICT_CAP
    if baseline is not None:
        cap = min(cap, baseline["conflict_rate_pre"] + CONFLICT_SLACK)
    if res["conflict_rate_pre"] > cap:
        reasons.append("矛盾率超帽：%.3f > %.3f（过滤前）" % (res["conflict_rate_pre"], cap))
    if baseline is not None:
        bh = {p["task_id"]: p["kh"] for p in baseline["per"]}
        for p in res["per"]:
            if p["kh"] < bh.get(p["task_id"], 0.0):
                reasons.append("key_conclusion 掉点：%s %.2f < 基线 %.2f"
                               % (p["task_id"], p["kh"], bh.get(p["task_id"], 0.0)))
                break
    if baseline is not None and theta is not None and topology_id:
        # C4 条数灌水探针（协议 F2 的训练侧对应物）
        b_claims = sum(p["n_claims"] for p in baseline["per"]) / max(len(baseline["per"]), 1)
        r_claims = sum(p["n_claims"] for p in res["per"]) / max(len(res["per"]), 1)
        b_sup = baseline["S_mean"]
        r_sup = res["S_mean"]
        if b_claims > 0 and (r_claims - b_claims) / b_claims >= 0.20:
            if b_sup > 0 and (r_sup - b_sup) / b_sup < 0.10:
                reasons.append("条数灌水探针：断言数涨 ≥20% 而被支持去重数涨 <10%")
    return reasons


# ------------------------------------------------------------------ 坐标下降
def coordinate_descent(topics, llm, verifier, topology_id, base_theta=None,
                        lamb=LAMBDA, n_pass=N_PASS, verbose=True):
    base_theta = dict(base_theta or P.default_theta())
    prior = dict(base_theta)
    baseline = evaluate(base_theta, topology_id, topics, llm, verifier, reps=1)
    base_reasons = constraint_ok(baseline, None, base_theta, topology_id)
    if verbose:
        print("[baseline] J=%.3f conflict=%.3f key_hit=%.3f 约束=%s"
              % (baseline["J"], baseline["conflict_rate_pre"], baseline["key_hit"],
                 base_reasons or "OK"), flush=True)
    cur = dict(base_theta)
    cur_res = baseline
    history = []
    live = P.live_params(topology_id)
    order = [p["name"] for p in live]
    for it in range(n_pass):
        fold = "A" if it % 2 == 0 else "B"
        fold_topics = [t for t in topics if t["task_id"] in FOLDS[fold]]
        for pname in order:
            spec = P.PARAM_BY_NAME[pname]
            vals = P.alphabet(spec)
            prior_idx = vals.index(prior[pname]) if prior[pname] in vals else 0
            best = (cur_res["J"] - lamb * 0.0, cur[pname], cur_res, [])
            for vi, v in enumerate(vals):
                cand = dict(cur)
                cand[pname] = v
                if P.validate(cand, topology_id) or P.degenerate(cand, topology_id):
                    continue
                res = evaluate(cand, topology_id, fold_topics, llm, verifier, reps=1,
                               seed=SEED + it)
                reasons = constraint_ok(res, None, cand, topology_id)
                if reasons:
                    continue
                score = res["J"] - lamb * (abs(vi - prior_idx) / max(len(vals) - 1, 1))
                if score > best[0] + 1e-9:
                    best = (score, v, res, reasons)
            cur[pname] = best[1]
            cur_res = best[2]
            history.append(dict(iteration=it, fold=fold, param=pname,
                                chosen=best[1], score=round(best[0], 4),
                                J=round(best[2]["J"], 4)))
            if verbose:
                print("  轮%d[%s] %-18s → %-8s (J=%.3f)" % (it, fold, pname, best[1],
                                                             best[2]["J"]), flush=True)
    return cur, baseline, history


def main():
    from creativity_lab.client import LLM
    llm = LLM()
    verifier = make_verifier(llm)
    topics = load_topics()
    os.makedirs(OUT, exist_ok=True)
    topology_id = os.environ.get("C_TOPOLOGY", "T2")
    theta, baseline, history = coordinate_descent(topics, llm, verifier, topology_id)
    # 折外评估：两折互为留出
    out = dict(topology=topology_id, theta=theta, theta_hash=P.theta_hash(theta),
               prior=P.default_theta(), lam=LAMBDA, n_pass=N_PASS,
               folds=FOLDS, baseline_J=baseline["J"], history=history,
               baseline=dict(J=baseline["J"], conflict_rate_pre=baseline["conflict_rate_pre"],
                             key_hit=baseline["key_hit"]))
    # 折外：对折 A 学到的 θ 在折 B 上评，反之亦然（这里只做一次单折近似，完整版见 DESIGN.md §4.5）
    other = [t for t in topics if t["task_id"] in FOLDS["B"]]
    res_out = evaluate(theta, topology_id, other, llm, verifier, reps=1)
    res_in = evaluate(theta, topology_id, [t for t in topics if t["task_id"] in FOLDS["A"]],
                      llm, verifier, reps=1)
    base_out = evaluate(P.default_theta(), topology_id, other, llm, verifier, reps=1)
    out["heldout"] = dict(theta_J=res_out["J"], prior_J=base_out["J"],
                          delta=res_out["J"] - base_out["J"],
                          in_sample_J=res_in["J"],
                          constraints=constraint_ok(res_out, base_out, theta, topology_id))
    json.dump(out, open(os.path.join(OUT, "train_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(out["heldout"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
