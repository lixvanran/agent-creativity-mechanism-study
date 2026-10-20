#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路线 B v2 · **可执行性冒烟**（≤ 20 次 MiniMax 调用；**禁止任何 OpenRouter 调用**）。

⚠️ 冒烟**不产出任何实验结论**。它只验证四件事：
  ❶ 端到端流程能跑通（生成 → 抽断言 → 核验并归因到依据条目 → 拆分 → 代理计算 → 机械装配）
  ❷ 提示词能解析（判官输出 `关系 | 条目编号` 能被机器解析）
  ❸ **特征空间的状态可分性**（v2 vs 旧 14 维的对照，离线、0 次调用）
  ❹ 监控告警**会响**（变异注入自测，离线、0 次调用）

调用预算：硬上限 20 次（`rec` 里每一条 = 一次真实 HTTP 调用，含重试尝试）。
端点断言：`OPENROUTER_BASE_URL` 必须是 MiniMax 订阅端点，否则 **abort**。
诊断题：`data/diag_topics.json`（自造 2 道，**不是** U1–U4；已过 guard.py 黑名单检查）。
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.environ.get("CMP8_REPO", "/workspace/lab/cmp8repo")
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402

from ops_v2 import (CLASSES, FEAT_DIM, FEATURE_NAMES, OPS_V2, Graph, candidates,  # noqa: E402
                    op_features_v2, policy_probs, state_gaps)
from evidence_index import EvidenceIndex, check_claims_v2, proxy_report, terminal_reward  # noqa: E402
import guard  # noqa: E402
import monitor as mon  # noqa: E402
from train_policy_v2 import GEN_Q, run_episode  # noqa: E402

CALL_CAP = int(os.environ.get("SMOKE_CALL_CAP", "20"))
MODEL = os.environ.get("PRIMARY_MODEL", "MiniMax-M3.1-Flash-Preview")
OUTDIR = os.path.join(os.path.dirname(HERE), "smoke")
os.makedirs(OUTDIR, exist_ok=True)


def _json_default(o):
    """numpy 标量/数组 ⇒ 原生 python（避免日志里出现不可序列化对象）。"""
    if hasattr(o, "item"):
        try:
            return o.item()
        except Exception:
            pass
    if hasattr(o, "tolist"):
        return o.tolist()
    return str(o)


def jdumps(obj, **kw):
    kw.setdefault("ensure_ascii", False)
    kw.setdefault("default", _json_default)
    return json.dumps(obj, **kw)


LOG = {"t0": time.strftime("%Y-%m-%d %H:%M:%S"), "call_cap": CALL_CAP,
       "model": MODEL, "events": []}


def ev(tag, **kw):
    LOG["events"].append(dict(tag=tag, **kw))
    print("[%s] %s" % (tag, jdumps(kw)), flush=True)


class BudgetExhausted(RuntimeError):
    pass


class BudgetedLLM:
    """包住 `creativity_lab.client.LLM`：每次 chat 前检查调用预算。
    冒烟用 `budgets=()` ⇒ **1 次逻辑调用 = 1 次 HTTP 调用**（无重试）⇒ 计数确定。"""

    def __init__(self, cap):
        os.environ.setdefault("OPENROUTER_BASE_URL", "https://api.minimaxi.com/v1")
        from creativity_lab.client import LLM
        self.inner = LLM()
        self.cap = cap

    @property
    def rec(self):
        return self.inner.rec

    def chat(self, prompt, **kw):
        # 每次逻辑调用**最多 2 次尝试**（1 次重试）⇒ 计数上界可精确控制
        if len(self.rec) + 2 > self.cap:
            raise BudgetExhausted("调用预算耗尽：已达 %d 次上限" % self.cap)
        kw["budgets"] = (2000,)            # ⇒ 最多 2 次尝试
        return self.inner.chat(prompt, **kw)


# ───────────────────────────────────────────────────────── ❶ 端点断言
def check_endpoint():
    from creativity_lab.client import BASE
    ok = ("minimaxi.com" in BASE) and ("openrouter.ai" not in BASE)
    LOG["endpoint"] = dict(base_url=BASE, is_minimax=ok, openrouter_used=False)
    ev("endpoint", base_url=BASE, ok=ok)
    if not ok:
        raise SystemExit("ABORT：被测侧端点不是 MiniMax 订阅端点（%s）" % BASE)
    return BASE


# ───────────────────────────────────────────────────────── ❷ 黑名单自检
def check_blacklist():
    import train_policy_v2 as tpv
    texts = {
        "diag_ask_DS1": "", "diag_ask_DS2": "",
        "prompt_GEN": tpv.GEN_Q, "prompt_EXTRACT": tpv.EXTRACT_Q,
        "prompt_SPLIT": tpv.SPLIT_Q,
        "prompt_CHECK_V2": __import__("evidence_index").CHECK_V2,
    }
    data = json.load(open(os.path.join(HERE, "data", "diag_topics.json"), encoding="utf-8"))
    for t in data["topics"]:
        texts["diag_ask_%s" % t["topic_id"]] = t["ask"]
        texts["diag_evidence_%s" % t["topic_id"]] = json.dumps(t["items"], ensure_ascii=False)
        texts["diag_ct_%s" % t["topic_id"]] = json.dumps(t["conclusion_space"], ensure_ascii=False)
    extra = [os.path.join(HERE, f) for f in os.listdir(HERE) if f.endswith(".py")]
    for f in ("DESIGN.md", "spec.yaml"):
        p = os.path.join(os.path.dirname(HERE), f)
        if os.path.exists(p):
            extra.append(p)
    ok, det = guard.check(texts, extra)
    LOG["blacklist"] = det
    ev("blacklist", ok=ok, total_hits=det["total_hits"],
       blacklist_source_files=det["blacklist_source_files"])
    return ok


# ───────────────────────────────────────────────────────── ❸ 状态可分性（离线）
# 精确复现**负责人 2026-10-20 的三条实测**，并给出 v2 的对照：
#   实测1：同一 target 下换 op，f[7..13] 完全相同 ⇒ 策略看不见 target 的内容
#   实测2：target 造成的分差对所有 op 同时发生（纯加性）⇒ 无法表达 op×target 交互
#   实测3：加"全局缺口特征"（不作成交叉项）对选哪个 op **零作用**
# 判定用**同长度**的 target 文本 ⇒ 把 f[11]（长度）的贡献扣掉，只留 verdict 的影响。
STATES = ("none", "unmentioned", "supported", "contradicted", "unverified")
_TXT = "断言占位文本甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳"   # 14 字，**所有状态等长**


def make_graph(state):
    """每个状态一个图：1 个 ANSWER + 1 个 CLAIM（verdict 随状态变）。"""
    g = Graph()
    a1 = g.add("ANSWER", "甲答案" * 20, op="GEN_PLAIN")
    c = g.add("CLAIM", _TXT, parent=a1, op="EXTRACT")
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
    tgt = None if state == "none" else g.nodes[c]
    return g, tgt


def state_discrimination():
    from creativity_lab.ops import op_features as legacy_features
    from creativity_lab.ops import OPS as LEGACY_OPS

    out = {"states": list(STATES)}

    ck = os.path.join(REPO, "runs", "arch_learn_fixed", "result.json")
    w14 = None
    if os.path.exists(ck):
        try:
            w14 = np.array(json.load(open(ck))["w"], dtype=float)
        except Exception:
            w14 = None

    # ── L1：同一 target 下换 op ⇒ f[7..13] 是否相同（实测1）
    l1 = {}
    for st in ("unmentioned", "supported", "contradicted", "unverified"):
        g, tgt = make_graph(st)
        ex = np.asarray(legacy_features(g, "EXTRACT", tgt, 1), dtype=float)[7:14]
        ve = np.asarray(legacy_features(g, "VERIFY", tgt, 1), dtype=float)[7:14]
        l1[st] = bool(np.allclose(ex, ve))
    out["L1_legacy_same_target_same_f7_13"] = l1
    out["L1_all_true"] = all(l1.values())

    # ── L2：target 的分差是否对所有 op 同时发生（实测2，纯加性）
    #     注：分差 = w·f(state_u) − w·f(state_s)，对**每个** op 算一次
    w_probe = w14 if (w14 is not None and len(w14) == 14) else np.zeros(14)
    g_u, t_u = make_graph("unmentioned")
    g_s, t_s = make_graph("supported")
    d = {}
    for op in ("EXTRACT", "VERIFY", "SPLIT"):
        fu = np.asarray(legacy_features(g_u, op, t_u, 1), dtype=float)
        fs = np.asarray(legacy_features(g_s, op, t_s, 1), dtype=float)
        d[op] = round(float(w_probe @ (fu - fs)), 6)
    out["L2_legacy_target_delta_per_op"] = d
    out["L2_delta_is_op_independent"] = len(set(d.values())) == 1

    # ── L2b：**随机 w** 下同样成立 ⇒ 这是**特征空间的结构性质**，不是某个 w 的巧合
    rng0 = np.random.default_rng(20261020)
    w_rand = rng0.normal(0, 1, size=14)          # **同一个** w，循环外生成
    db = {}
    for op in ("EXTRACT", "VERIFY", "SPLIT"):
        fu = np.asarray(legacy_features(g_u, op, t_u, 1), dtype=float)
        fs = np.asarray(legacy_features(g_s, op, t_s, 1), dtype=float)
        db[op] = float(w_rand @ (fu - fs))
    out["L2b_random_w_delta_per_op"] = {k: round(v, 6) for k, v in db.items()}
    out["L2b_delta_is_op_independent"] = len(set(np.round(list(db.values()), 9))) == 1

    # ── L3：4 个状态 {none, 未提及, 支持, 矛盾} 的 op 分数向量是否完全相同
    out["legacy_checkpoint_w_found"] = w14 is not None
    if w14 is not None and len(w14) == 14:
        sc = {}
        for st in STATES:
            g, tgt = make_graph(st)
            sc[st] = np.array([float(w14 @ np.asarray(legacy_features(g, op, tgt, 1)))
                               for op in LEGACY_OPS])
        # L3a：**组内相对顺序**是否随状态改变（这才是"能否表达 op×target 交互"的判据）
        def rel_order(vec):
            idx = [LEGACY_OPS.index(o) for o in ("EXTRACT", "VERIFY", "SPLIT")]
            return tuple(np.argsort([-vec[i] for i in idx]))
        orders = {}
        for st in ("unverified", "unmentioned", "supported", "contradicted"):
            orders[st] = rel_order(sc[st])
        out["L3a_legacy_relative_order_of_target_ops_by_state"] = {k: list(v) for k, v in orders.items()}
        out["L3a_order_is_state_invariant"] = len(set(orders.values())) == 1
        # L3b：{未提及, 支持, 矛盾} 的**绝对**分数向量是否完全相同（当前 checkpoint 下）
        three = ("unmentioned", "supported", "contradicted")
        out["L3b_legacy_score_vectors_identical_3verdict_states"] = bool(
            all(np.allclose(sc[three[0]], sc[t]) for t in three[1:]))
        # L3c：argmax 是否随状态改变
        out["L3c_legacy_argmax_by_state"] = {st: LEGACY_OPS[int(np.argmax(sc[st]))]
                                            for st in ("unverified", "unmentioned",
                                                       "supported", "contradicted")}

    # ── L4：加"全局缺口特征"（不交叉）是否改变 argmax（实测3）
    #     做法：把一个与 op 无关的常数加到所有候选的分数上 ⇒ argmax 不变
    g, tgt = make_graph("unmentioned")
    cands = candidates(g, n_verify_done=1)
    s0 = np.array([float(w14 @ np.asarray(legacy_features(g, op, tgt, 1)))
                   for op, _t in cands]) if w14 is not None else np.zeros(len(cands))
    arg_plain = cands[int(np.argmax(s0))][0]
    arg_plus = cands[int(np.argmax(s0 + 0.37))][0]   # 全局特征 = 对所有候选同加
    out["L4_legacy_argmax_unchanged_by_global_feature"] = (arg_plain == arg_plus)

    # ── V1：v2 在同样 5 个状态下的特征向量是否不同
    v2 = {}
    for st in STATES:
        g, tgt = make_graph(st)
        rows = []
        for op in OPS_V2:
            t = tgt if op in ("VERIFY", "SPLIT", "EXTRACT") else None
            rows.append((op, op_features_v2(g, op, t)))
        v2[st] = rows
    diff = {st: sum(1 for _o, f in rows if not np.allclose(rows[0][1], f))
            for st, rows in v2.items()}
    out["V1_v2_rows_differing_per_state"] = diff
    four = ("none", "unmentioned", "supported", "contradicted")
    out["V1_v2_4states_not_all_identical"] = bool(
        not all(np.allclose(v2[four[0]][i][1], v2[s][i][1]) for s in four[1:] for i in range(len(OPS_V2))))
    out["V1_v2_unmentioned_vs_supported_differ"] = bool(
        not all(np.allclose(v2["unmentioned"][i][1], v2["supported"][i][1])
                for i in range(len(OPS_V2))))

    # ── V2：**存在性见证** —— 构造一条"状态依赖规则"，看 argmax 是否随状态改变
    #     规则：target 未核验 ⇒ VERIFY；target 依据未覆盖 ⇒ SPLIT；没有断言 ⇒ 生成
    ci = {c: i for i, c in enumerate(CLASSES)}
    w_ex = np.zeros(FEAT_DIM)
    w_ex[FEATURE_NAMES.index("%s×t1_tgt_unverified" % CLASSES[ci["VERIFY"]])] = 1.0
    w_ex[FEATURE_NAMES.index("%s×t1_tgt_unverified" % CLASSES[ci["PROCESS"]])] = -1.0
    w_ex[FEATURE_NAMES.index("%s×t2_tgt_unmentioned" % CLASSES[ci["PROCESS"]])] = 1.0
    w_ex[FEATURE_NAMES.index("%s×g1_no_claims" % CLASSES[ci["GENERATE"]])] = 0.5
    arg = {}
    for st in STATES:
        g, tgt = make_graph(st)
        cands = candidates(g, n_verify_done=1)
        s = np.array([float(w_ex @ op_features_v2(g, op, t)) for op, t in cands])
        arg[st] = cands[int(np.argmax(s))][0]
    out["V2_witness_argmax_by_state"] = arg
    out["V2_witness_argmax_varies"] = len(set(arg.values())) > 1

    # ── L6：**旧系统的状态适应住在"人写的候选规则"里，不在权重里**
    #     证据：SPLIT 只对 verdict ∈ {None, 未提及} 开放 ⇒ 在 支持/矛盾 状态下
    #     SPLIT **根本不在候选集里** ⇒ 与 w 无关。
    avail = {}
    for st in STATES:
        g, tgt = make_graph(st)
        avail[st] = sorted({op for op, _t in candidates(g, n_verify_done=1)})
    out["L6_legacy_candidate_sets_by_state"] = avail
    out["L6_split_unavailable_when_supported"] = "SPLIT" not in avail["supported"]
    out["L6_verify_unavailable_when_supported"] = "VERIFY" not in avail["supported"]

    out["feature_dim_v2"] = FEAT_DIM
    out["feature_names_len"] = len(FEATURE_NAMES)
    return out


# ───────────────────────────────────────────────────────── ❹ 代理自测（抗灌水）
def proxy_selftest():
    evi = EvidenceIndex("T", "问题", [
        {"id": "E1", "text": "依据一", "anchored": True},
        {"id": "E2", "text": "依据二", "anchored": True},
        {"id": "E3", "text": "花絮依据", "anchored": False},
    ])
    # 情形 A：覆盖 1 条锚定依据
    vA = {"c1": {"rel": "支持", "items": ["E1"]}}
    rA = proxy_report(evi, vA, ["c1"])
    # 情形 B：再加一条**覆盖同一条依据**的断言（重复）⇒ Ŵ 不应变
    vB = {"c1": {"rel": "支持", "items": ["E1"]}, "c2": {"rel": "支持", "items": ["E1"]}}
    rB = proxy_report(evi, vB, ["c1", "c2"])
    # 情形 C：再加一条**覆盖花絮依据**的断言 ⇒ Ŵ 仍不应变
    vC = dict(vB); vC["c3"] = {"rel": "支持", "items": ["E3"]}
    rC = proxy_report(evi, vC, ["c1", "c2", "c3"])
    # 情形 D：再覆盖第 2 条锚定依据 ⇒ Ŵ 应上升
    vD = dict(vC); vD["c4"] = {"rel": "支持", "items": ["E2"]}
    rD = proxy_report(evi, vD, ["c1", "c2", "c3", "c4"])
    # 情形 E：矛盾断言不贡献
    vE = dict(vD); vE["c5"] = {"rel": "矛盾", "items": ["E2"]}
    rE = proxy_report(evi, vE, ["c1", "c2", "c3", "c4", "c5"])
    out = dict(
        w_hat_A=rA["w_hat"], w_hat_B_repeat=rB["w_hat"], w_hat_C_floral=rC["w_hat"],
        w_hat_D_new_anchored=rD["w_hat"], w_hat_E_with_conflict=rE["w_hat"],
        repeat_does_not_increase=abs(rA["w_hat"] - rB["w_hat"]) < 1e-12,
        floral_does_not_increase=abs(rB["w_hat"] - rC["w_hat"]) < 1e-12,
        new_anchored_increases=rD["w_hat"] > rC["w_hat"],
        conflict_does_not_increase=abs(rD["w_hat"] - rE["w_hat"]) < 1e-12,
        conflict_rate_E=rE["conflict_rate"],
        terminal_reward_example=terminal_reward(rD),
    )
    out["all_pass"] = all(out[k] for k in
                           ("repeat_does_not_increase", "floral_does_not_increase",
                            "new_anchored_increases", "conflict_does_not_increase"))
    return out


# ───────────────────────────────────────────────────────── ❺ 端到端（MiniMax）
def _smoke_picker_factory():
    """冒烟用的**固定优先策略**（不是学习到的）：把每条管线都走一遍，且调用数可预期。

    顺序：没答案 → 生成；没抽过断言 → 抽取；有未核验 → 核验；有依据未覆盖 → 拆分；
    还剩预算 → 再生成一次；否则停止。
    """
    st = {"gen": 0, "extracted": False}

    def pick(step, g, cands):
        legal = {op for op, _t in cands}
        if not g.of_kind("ANSWER"):
            st["gen"] += 1
            return "GEN_ANGLE"
        if "EXTRACT" in legal and not st["extracted"]:
            st["extracted"] = True
            return "EXTRACT"
        if "VERIFY" in legal:
            return "VERIFY"
        if "SPLIT" in legal:
            return "SPLIT"
        if st["gen"] < 2:
            st["gen"] += 1
            return "GEN_ANGLE"
        return "STOP"

    return pick


def run_e2e(llm):
    data = json.load(open(os.path.join(HERE, "data", "diag_topics.json"), encoding="utf-8"))
    out = []
    raw_all = []
    for t in data["topics"]:
        evi = EvidenceIndex(t["topic_id"], t["ask"], t["items"])
        w = np.zeros(FEAT_DIM)
        g, traj, rewards, info = run_episode(
            {"topic_id": t["topic_id"], "ask": t["ask"]}, evi, w,
            random.Random(7), llm=llm, model=MODEL, budget=6,
            forced_picker=_smoke_picker_factory(), raw_log=raw_all)
        # 机械装配（协议 §4.5 的评分对象形态）
        from creativity_lab.ops import assemble
        final = assemble(g, t["ask"])
        row = dict(topic_id=t["topic_id"], steps=info["steps"], ops=info["ops"],
                   n_claims=info["width"], proxy=info["proxy"],
                   final_reward=info["final_reward"], signature=info["signature"],
                   answer_len=len(final),
                   answer_head=final[:220].replace("\n", " | "))
        out.append(row)
        ev("episode", **{k: v for k, v in row.items() if k != "answer_head"})
        ev("answer_head", topic_id=t["topic_id"], head=row["answer_head"])
    return out, raw_all


def main():
    check_endpoint()
    bl_ok = check_blacklist()
    disc = state_discrimination()
    ev("state_discrimination", **disc)
    pxy = proxy_selftest()
    ev("proxy_selftest", **pxy)
    mt = mon.selftest()
    ev("monitor_selftest", **mt)

    llm = BudgetedLLM(CALL_CAP)
    e2e, raw_all = run_e2e(llm)

    calls = [{"model": c.model, "purpose": c.purpose, "max_tokens": c.max_tokens,
              "finish_reason": c.finish_reason, "content_len": c.content_len,
              "ok": c.ok, "secs": round(c.secs, 2)} for c in llm.rec]
    LOG["calls"] = calls
    LOG["n_calls"] = len(calls)
    LOG["n_calls_ok"] = sum(1 for c in calls if c["ok"])
    LOG["e2e"] = e2e
    LOG["raw_outputs"] = raw_all
    LOG["state_discrimination"] = disc
    LOG["proxy_selftest"] = pxy
    LOG["monitor_selftest"] = mt
    LOG["blacklist_ok"] = bl_ok
    LOG["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG["total_secs"] = round(sum(c["secs"] for c in calls), 1)

    p = os.path.join(OUTDIR, "smoke_log.json")
    json.dump(LOG, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=_json_default)

    md = ["# 路线 B v2 · 冒烟日志", "",
          "- 时间：%s → %s" % (LOG["t0"], LOG["t_end"]),
          "- 模型：%s ｜ 端点：%s（被测侧**不走 OpenRouter**）" % (MODEL, LOG["endpoint"]["base_url"]),
          "- **调用数：%d / 上限 %d**（成功 %d）｜ 端到端耗时 %.0f s" % (
              LOG["n_calls"], CALL_CAP, LOG["n_calls_ok"], LOG["total_secs"]),
          "- 黑名单自检：%s ｜ 状态可分性对照：%s ｜ 代理自测：%s ｜ 告警自测：%s" % (
              "PASS" if bl_ok else "FAIL",
              "PASS" if disc["V1_v2_4states_not_all_identical"] else "FAIL",
              "PASS" if pxy["all_pass"] else "FAIL",
              "PASS" if mt["all_pass"] else "FAIL"),
          "", "## 调用清单（每行 = 一次真实 HTTP 调用）", "",
          "| # | purpose | model | max_tokens | finish | 内容长度 | ok | 秒 |",
          "|---:|---|---|---:|---|---:|:-:|---:|"]
    for i, c in enumerate(calls, 1):
        md.append("| %d | %s | %s | %d | %s | %d | %s | %.1f |" % (
            i, c["purpose"], c["model"], c["max_tokens"], c["finish_reason"],
            c["content_len"], c["ok"], c["secs"]))
    md += ["", "## 状态可分性对照（离线，0 次调用）", "",
           "```json", jdumps(disc, indent=1), "```",
           "", "## 代理自测（离线）", "",
           "```json", jdumps(pxy, indent=1), "```",
           "", "## 告警变异自测（离线）", "",
           "```json", jdumps(mt, indent=1), "```", ""]
    open(os.path.join(OUTDIR, "smoke_log.md"), "w", encoding="utf-8").write("\n".join(md))
    print("\n== 冒烟结束：调用 %d 次（上限 %d）→ %s" % (LOG["n_calls"], CALL_CAP, p))
    return 0 if (bl_ok and disc["V1_v2_4states_not_all_identical"]
                 and pxy["all_pass"] and mt["all_pass"]
                 and LOG["n_calls"] <= CALL_CAP) else 1


if __name__ == "__main__":
    sys.exit(main())
