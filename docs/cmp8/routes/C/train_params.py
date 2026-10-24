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
from topology import TEMPLATES, TEMPLATE_IDS, DEFAULT_TOPOLOGY

CORPUS = "/workspace/lab/cmp8repo/creativity_lab/data/policy_topics.json"
META = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_corpus_meta.json")
OUT = os.environ.get("C_TRAIN_OUT", "/workspace/lab/routes/C/train_out")

# ------------------------------------------------------------------ 预注册
LAMBDA = 0.25          # 向先验收缩系数
LAMBDA_P = 0.5         # 精度惩罚：每条"已交付但未被支持"的断言扣多少（事前预注册）
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


def key_hit(text: str, key_conclusions) -> float:
    """关键结论命中率（**在给定的子集文本上**计算）。

    ★ **口径（2026-10-21 修正 · 复核 6e）**：训练侧约束 C2 只在**被支持子集**
      （`executor.diagnostics["delivered_supported_text"]`，即判官判为「支持」
      **且**已进机械答案的断言）上计算。
      原因：若在**整份答案**上算，一个从未核验、或被明确判为「未提及」的断言里
      偶然出现答案词就会拿命中分 ⇒ 优化器会因此学到"多写几个可能含答案词的断言"，
      这正是协议 R-3/R-4 要防的（用未核验内容冒充正确）。
      协议层的 R2 仍按协议在**机械答案**上度量（不改协议）；
      这里改的是**本路线自己的训练约束**，方向上更严。
    """
    a = _norm(text)
    if not key_conclusions:
        return 1.0
    hit = 0
    for kc in key_conclusions:
        ok = all(any(_norm(alt) in a for alt in grp) for grp in kc["must_any"])
        hit += 1 if ok else 0
    return hit / len(key_conclusions)


#: 判官的「支持」标签（与 executor.SUPPORT 同字面）
SUPPORT_V = "支持"


def supported_text_of(d: dict) -> str:
    """从诊断字典里取**被支持子集**的文本，**并断言**它不含任何未被支持的断言。

    这是 6e 修复的**回归护栏**：C2 的命中率必须由这个函数产出，
    因此「整份机械答案」（含「依据未覆盖」「未经核验」两节）**不可能**再被用于 C2。
    断言失败 ⇒ 直接抛 AssertionError（**不静默降级**）。
    """
    sup_text = d.get("delivered_supported_text", "") or ""
    claims = d.get("delivered_claims") or []
    bad = [c.get("text") for c in claims
           if c.get("verdict") != SUPPORT_V and (c.get("text") or "")
           and c.get("text") in sup_text]
    if bad:
        raise AssertionError("key_hit 的输入里混入了未被支持的断言：%r" % (bad[:3],))
    allowed = set(c.get("text") for c in claims if c.get("verdict") == SUPPORT_V)
    for line in (sup_text.split("\n") if sup_text else []):
        if line and line not in allowed:
            raise AssertionError(
                "key_hit 的输入里出现了不在「被支持子集」里的行：%r" % (line[:40],))
    return sup_text


def key_hit_supported(d: dict, key_conclusions) -> float:
    """C2 用的命中率：**只在被支持（且已交付）子集上计算**（见 `supported_text_of`）。"""
    return key_hit(supported_text_of(d), key_conclusions)


# ------------------------------------------------------------------ 判官（训练侧）
def make_verifier(llm):
    """训练侧判官：沿用 cmp8 的四分类核验提示词（v4），**与验收侧判官不同源**。"""
    from creativity_lab.verify import check_claims
    return lambda ask, ev, claims: check_claims(llm, ask, ev, claims)


# ------------------------------------------------------------------ 评估
def evaluate(theta, topology_id, topics, llm, verifier, reps=1, seed=SEED,
             max_calls=CALL_CAP):
    """在一个配置上跑若干 episode，返回代理指标 + 约束判定。

    `max_calls` 默认 = CALL_CAP（训练期的调用上限，C3 约束的对象）。
    ⚠️ 只有**接线自检**（`check_wiring.py` 的探针）会把它调大：探针要测的是
    「参数能不能改变 J」这件事本身，**不能**让「调用预算超限 ⇒ 配置被截断」
    把参数效应掩盖掉（那是 C3 约束在起作用，是另一件事）。
    """
    rng = random.Random(seed)
    per = []
    for t in topics:
        for r in range(reps):
            d = run_episode(t, topology_id, theta, llm=llm, verifier=verifier,
                            max_calls=max_calls)
            # ★ key_conclusion_hit 只在**「已交付 ∧ 被支持」**的子集上算
            #   （比"被支持子集"更严：没进答案的断言不算命中）；
            #   `key_hit_supported` 内部带断言 ⇒ 口径漂移会直接抛错。
            kh = key_hit_supported(d, t["key_conclusions"])
            kh_any = key_hit(d["answer"], t["key_conclusions"])   # 整份答案口径：仅作描述性参考
            per.append(dict(task_id=t["task_id"], rep=r, S=d["n_supported_distinct"],
                            n_claims=d["n_claims_total"], conflict=d["conflict_rate_pre"],
                            c_n=d["conflict_n"], c_d=d["conflict_den"], kh=kh,
                            kh_any=kh_any,
                            # --- 交付集口径 ---
                            d_supp=d.get("n_delivered_supported_distinct", 0),
                            d_unsupp=d.get("n_delivered_unsupported_distinct", 0),
                            d_total=d.get("n_delivered_total", 0),
                            prec=(d.get("n_delivered_supported", 0) /
                                  max(d.get("n_delivered_total", 0), 1)),
                            calls=d["n_calls"], answer=d["answer"]))
    S = [p["S"] for p in per]
    c_n = sum(p["c_n"] for p in per)
    c_d = sum(p["c_d"] for p in per)
    d_supp = sum(p["d_supp"] for p in per) / max(len(per), 1)
    d_unsupp = sum(p["d_unsupp"] for p in per) / max(len(per), 1)
    kh = sum(p["kh"] for p in per) / max(len(per), 1)
    viol = P.validate(theta, topology_id)
    degen = P.degenerate(theta, topology_id)
    over_call = sum(1 for p in per if p["calls"] > CALL_CAP)
    kh_any = sum(p["kh_any"] for p in per) / max(len(per), 1)
    # ★ J 算在**已交付答案**上：交付且被支持且互不重复的条数，减去精度惩罚。
    #   为什么必须算在交付集上：若算在"内部产生"上，J 对装配旋钮
    #   （theta_util / m_clusters）**恒定不变** ⇒ 训练学不动它们（复核必修 2）。
    J = d_supp - LAMBDA_P * d_unsupp
    res = dict(J=J, S_mean=sum(S) / max(len(S), 1),
               d_supported_distinct=d_supp, d_unsupported_distinct=d_unsupp,
               precision=sum(p["prec"] for p in per) / max(len(per), 1),
               conflict_rate_pre=(c_n / c_d) if c_d else 0.0, conflict_n=c_n,
               conflict_den=c_d, key_hit=kh, key_hit_any=kh_any, per=per,
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
        # C4 条数灌水探针（协议 F2 的训练侧对应物）—— 用**交付集**口径
        b_claims = baseline.get("d_supported_distinct", 0.0)
        r_claims = res.get("d_supported_distinct", 0.0)
        b_uns = baseline.get("d_unsupported_distinct", 0.0)
        r_uns = res.get("d_unsupported_distinct", 0.0)
        if b_claims > 0 and (r_claims - b_claims) / b_claims >= 0.20:
            if b_uns > 0 and (r_uns - b_uns) / b_uns < 0.10:
                reasons.append("条数灌水探针：交付的支持条数涨 ≥20% 而交付的未支持条数涨 <10%")
        # C7 精度约束（协议 R4 的训练侧对应物）：交付答案里的"支持占比"不得低于基线
        if res.get("precision", 0.0) < baseline.get("precision", 0.0) - 1e-9:
            reasons.append("精度约束：交付答案支持占比 %.3f < 基线 %.3f"
                           % (res.get("precision", 0.0), baseline.get("precision", 0.0)))
    return reasons



# ------------------------------------------------------------------ 拓扑析因
def pick_random_topology(seed: int = 11) -> str:
    """零假设对照：从菜单里**随机**抽一个模板（种子预注册，可复现）。"""
    import random as _r
    return _r.Random(seed).choice(list(TEMPLATE_IDS))


def run_factorial(topics, llm, verifier, topologies=None, null_seed=11,
                  out_dir=None, verbose=True):
    """把「拓扑」做成实验因子：同一训练程序跑在多个模板上。

    这是 DESIGN.md §5 的**可执行实现**：拓扑 × 参数策略 的析因，
    用于分离"拓扑"这一项的贡献（并给出随机拓扑的零假设对照）。
    """
    out_dir = out_dir or OUT
    os.makedirs(out_dir, exist_ok=True)
    topologies = list(topologies or TEMPLATE_IDS)
    null_tid = pick_random_topology(null_seed)
    rows = []
    for tid in topologies:
        if verbose:
            print("== 拓扑 %s（%s）==" % (tid, TEMPLATES[tid]["name"]), flush=True)
        theta, baseline, history = coordinate_descent(
            topics, llm, verifier, tid, verbose=verbose)
        # 折外：两折互为留出，各跑一次，取平均
        out_res, in_res, base_out = [], [], []
        for fold, other in (("A", "B"), ("B", "A")):
            other_topics = [t for t in topics if t["task_id"] in FOLDS[other]]
            base_out.append(evaluate(P.default_theta(), tid, other_topics, llm, verifier))
            out_res.append(evaluate(theta, tid, other_topics, llm, verifier))
            in_res.append(evaluate(theta, tid, [t for t in topics
                                               if t["task_id"] in FOLDS[fold]],
                                  llm, verifier))
        rows.append(dict(
            topology=tid, name=TEMPLATES[tid]["name"],
            is_default=(tid == DEFAULT_TOPOLOGY), is_random_null=(tid == null_tid),
            theta=theta, theta_hash=P.theta_hash(theta),
            live_params=[p["name"] for p in P.live_params(tid)],
            n_configs_evaluated=len(history),
            in_fold_J=sum(r["J"] for r in in_res) / len(in_res),
            out_fold_J=sum(r["J"] for r in out_res) / len(out_res),
            prior_out_fold_J=sum(r["J"] for r in base_out) / len(base_out),
            out_fold_delta=(sum(r["J"] for r in out_res) - sum(r["J"] for r in base_out))
            / len(out_res),
            prior_out_fold_conflict=sum(r["conflict_rate_pre"] for r in base_out) / len(base_out),
            out_fold_conflict=sum(r["conflict_rate_pre"] for r in out_res) / len(out_res),
            out_fold_key_hit_supported=sum(r["key_hit"] for r in out_res) / len(out_res),
            out_fold_key_hit_whole_answer=sum(r["key_hit_any"] for r in out_res) / len(out_res),
        ))
    best = max(rows, key=lambda r: r["out_fold_J"])
    default_row = next((r for r in rows if r["is_default"]), None)
    null_row = next((r for r in rows if r["is_random_null"]), None)
    result = dict(
        note=("拓扑析因：同一训练程序 × 多个模板。**这不是路线比较**，"
              "而是检验『人定拓扑这一步有没有贡献』（DESIGN.md §5）。"),
        null_seed=null_seed, random_null_topology=null_tid,
        folds=FOLDS, lamb=LAMBDA, n_pass=N_PASS,
        rows=rows,
        best_topology=best["topology"],
        default_vs_null_delta=(None if (not default_row or not null_row)
                               else default_row["out_fold_J"] - null_row["out_fold_J"]),
        default_is_best=(bool(default_row and best["topology"] == default_row["topology"])),
    )
    json.dump(result, open(os.path.join(out_dir, "factorial.json"), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=1)
    return result

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
    if topology_id == "all":
        # 拓扑析因模式（DESIGN.md §5）：同一训练程序跑在全部模板上
        res = run_factorial(topics, llm, verifier)
        print(json.dumps({k: v for k, v in res.items() if k != "rows"},
                         ensure_ascii=False, indent=1))
        for r in res["rows"]:
            print("  %-3s %-22s 折外J=%.3f 先验折外J=%.3f Δ=%+.3f  随机零假设=%s"
                  % (r["topology"], r["name"], r["out_fold_J"],
                     r["prior_out_fold_J"], r["out_fold_delta"], r["is_random_null"]))
        return
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
                          key_hit_supported=res_out["key_hit"],
                          key_hit_whole_answer=res_out["key_hit_any"],
                          key_hit_note="约束 C2 用「被支持子集」口径；整份答案口径仅作参考",
                          constraints=constraint_ok(res_out, base_out, theta, topology_id))
    json.dump(out, open(os.path.join(OUT, "train_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(out["heldout"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
