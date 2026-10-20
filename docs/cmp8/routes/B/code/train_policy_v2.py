# -*- coding: utf-8 -*-
"""路线 B v2：**训练算法参考实现**（在线策略学习，架构由训练产生）。

与旧 `creativity_lab/train_policy.py` 的关系：
  · **沿用**已修好的四件事：动作—特征成对排序、on-policy 共享 `policy_probs`、
    尺度无关温度、f[6] 索引冲突（v2 直接重定义特征，无同类坑）。
  · **改掉**特征空间：加 (op 类别 × 信息缺口) 交叉项 ⇒ 状态**能**改变偏好顺序。
    ⚠️ 纯加性的全局特征在 softmax 里是**公共常数** ⇒ 对选择行为**零作用**
    （负责人 2026-10-20 实测 3）⇒ 缺口信息**必须**做成交叉项。
  · **新加**：τ 控制器（防塌缩）、EMA 权重平均、轨迹多样性监控、代理校准闸门。

依赖：`ops_v2.py` / `evidence_index.py` / `monitor.py`（同目录）。
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ops_v2 import (CLASSES, FEAT_DIM, OPS_V2, SLOTS, Graph, candidates,  # noqa: E402
                    n_eff, op_features_v2, pick, policy_probs, score_all, state_gaps)
from evidence_index import (EvidenceIndex, check_claims_v2, proxy_report,  # noqa: E402
                            terminal_reward)
from monitor import Monitor, TauController, seq_diversity, seq_signature  # noqa: E402

# ───────────────────────────────────────── 生成侧提示词（**不含**任何答案暗示/评价标准）
GEN_Q = ("问题：{ask}\n\n请从「{ang}」的角度切入回答。\n\n"
         "给出你的判断与具体做法，写明适用的规则、期限、材料或数值，400字以内。")
EXTRACT_Q = ("从下面这段回答里，逐条列出其中**可判真假的陈述**"
             "（数字、法规、权利义务、程序、时限、主体责任、事实断言）。"
             "不要观点和建议。一行一条，最多 10 条。\n\n{t}")
SPLIT_Q = ("把下面这条陈述拆成可以分别核验的独立陈述（如果它含多个断言就拆开）。"
           "一行一条，只输出拆分结果。\n\n{c}")

CONFLICT_CAP = 0.33
ALPHA = 3.0


# ───────────────────────────────────────── 一个 episode
def run_episode(topic: dict, ev_index: EvidenceIndex, w, rng, *, llm=None,
                model="MiniMax-M3.1-Flash-Preview", budget=10,
                tau_ctrl: TauController | None = None, forced_schedule=None,
                forced_picker=None, raw_log=None, tau: float = 1.2):
    """跑一遍图搜索。

    topic: {"topic_id", "ask"}
    forced_schedule: 仅冒烟用（按预定 op 序列走，控制调用数）⇒ 训练时为 None。
    forced_picker:  仅冒烟用（可调用对象 `fn(step, g, cands) -> op 名`）⇒ 训练时为 None。
    raw_log:        可选列表 ⇒ 把每次模型调用的原始输出截断存进去（诊断用）。

    返回 (graph, traj, rewards, info)
    traj: [(F, s_all, choice, tau_used, op)]  ← **记录当步的 τ**（行为端与更新端必须同 τ）
    """
    g = Graph()
    ask = topic["ask"]
    rewards, traj = [], []
    ophist = {}
    n_verify = 0
    slot_idx = 0
    for step in range(budget):
        cands, s, F = score_all(g, w, n_verify)
        if not cands:
            break
        if forced_picker is not None:
            want = forced_picker(step, g, cands)
            choice = next((i for i, (op, _t) in enumerate(cands) if op == want), None)
            if choice is None:                      # 预定动作此刻不合法 ⇒ 取第一个候选
                choice = 0
        elif forced_schedule is not None:
            want = forced_schedule[step] if step < len(forced_schedule) else "STOP"
            choice = next((i for i, (op, _t) in enumerate(cands) if op == want), None)
            if choice is None:                      # 预定动作此刻不合法 ⇒ 退回均匀
                choice = rng.randrange(len(cands))
        else:
            p = policy_probs(s, tau)
            if tau_ctrl is not None:
                tau_ctrl.observe(p)
                tau = tau_ctrl.tau
            choice = pick(cands, s, F, rng, tau=tau, mode="sample")
        op, tgt = cands[choice]
        tau_used = tau
        ophist[op] = ophist.get(op, 0) + 1
        traj.append((F, s, choice, tau_used, op))

        if op == "STOP":
            break
        if op in ("GEN_PLAIN", "GEN_ANGLE"):
            ang = "" if op == "GEN_PLAIN" else "从「%s」的角度切入。" % SLOTS[slot_idx % len(SLOTS)]
            slot_idx += 1
            a = llm.chat(GEN_Q.format(ask=ask, ang=ang), model=model,
                         purpose="al_gen", min_ok=60)
            if raw_log is not None:
                raw_log.append(dict(op=op, raw=(a or "")[:1200]))
            if a and len(a) > 20:
                g.add("ANSWER", a, op=op)
            rewards.append(0.0)
        elif op == "EXTRACT":
            src = tgt
            t = llm.chat(EXTRACT_Q.format(t=src.text[:1200]), model=model,
                         purpose="al_ex", max_tokens=1400, budgets=(2000,),
                         min_ok=15)
            if raw_log is not None:
                raw_log.append(dict(op="EXTRACT", raw=(t or "")[:1200]))
            for ln in (t or "").splitlines():
                ln = re.sub(r"^\s*[-*\u2022]\s*", "", ln)
                ln = re.sub(r"^\s*\d+[.、)]\s*", "", ln).strip()
                if 8 <= len(ln) <= 60:
                    g.add("CLAIM", ln, parent=src.nid, op="EXTRACT")
                if sum(1 for c in g.of_kind("CLAIM")) >= 10:
                    break
            rewards.append(0.0)
        elif op == "SPLIT":
            t = llm.chat(SPLIT_Q.format(c=tgt.text), model=model,
                         purpose="al_split", max_tokens=800, budgets=(1200,), min_ok=10)
            if raw_log is not None:
                raw_log.append(dict(op="SPLIT", raw=(t or "")[:1200]))
            for ln in (t or "").splitlines():
                ln = re.sub(r"^\s*[-*\u2022]\s*", "", ln)
                ln = re.sub(r"^\s*\d+[.、)]\s*", "", ln).strip()
                if 8 <= len(ln) <= 60 and ln != tgt.text:
                    g.add("CLAIM", ln, parent=tgt.nid, op="SPLIT")
                if sum(1 for c in g.of_kind("CLAIM")) >= 12:
                    break
            rewards.append(0.0)
        elif op == "VERIFY":
            # 一次最多核验 2 条（与候选集一致）
            tgt_list = [tgt]
            others = [n for n in g.of_kind("CLAIM") if n.verdict is None and n.nid != tgt.nid]
            tgt_list += others[:1]
            verd = check_claims_v2(llm, ask, ev_index, [n.text for n in tgt_list],
                                   model=model, raw_log=raw_log)
            for n in tgt_list:
                v = verd.get(n.text)
                if not v:
                    continue
                n.verdict = v["rel"]
                n.meta["items"] = v["items"]
            n_verify += 1
            rels = [verd.get(n.text, {}).get("rel", "解析失败") for n in tgt_list]
            if "矛盾" in rels:
                rewards.append(-2.0)
            elif "支持" in rels:
                rewards.append(1.0)
            else:
                rewards.append(0.0)

    # ── 终局：机械装配 + 代理计算 ──
    claims = [c.text for c in g.of_kind("CLAIM")]
    verd = {c.text: {"rel": c.verdict or "未核验", "items": c.meta.get("items", [])}
            for c in g.of_kind("CLAIM")}
    rep = proxy_report(ev_index, verd, claims)
    fin = terminal_reward(rep, CONFLICT_CAP, ALPHA)
    rewards.append(fin)
    info = dict(topic_id=topic["topic_id"], width=len(claims), ops=dict(ophist),
                n_verify=n_verify, final_reward=fin, proxy=rep,
                steps=len(traj), signature=seq_signature([t[4] for t in traj]))
    return g, traj, rewards, info


# ───────────────────────────────────────── 策略更新（on-policy REINFORCE）
def reinforce(w, traj, rewards, lr=0.05, gamma=0.9, baseline=0.0, l2=0.01):
    """REINFORCE：∇log π(a|s) = φ_a − E_{a'~π}[φ_{a'}]。

    ⚠️ on-policy 的三个必要条件（缺一不可）：
      ① 行为分布 = 更新时假定的分布 ⇒ 用**同一个** `policy_probs`
      ② 行为端用过的 τ 必须**原样带回**（温度会随训练变动！）⇒ traj 里存了 tau_used
      ③ 分数与特征**成对排序** ⇒ F[choice] 与 s[choice] 描述同一个候选
    """
    if not traj:
        return w, baseline
    R, G = 0.0, []
    for r in reversed(rewards):
        R = r + gamma * R
        G.append(R)
    G.reverse()
    adv = np.array(G) - baseline
    gw = np.zeros_like(w)
    for (F, s_all, choice, tau_used, _op), a in zip(traj, adv):
        p = policy_probs(s_all, tau_used)          # ← 用**行为时**的 τ
        grad = F[choice] - (p[:, None] * F).sum(axis=0)
        gw += a * grad
    gw = gw / max(len(traj), 1)
    w = w + lr * gw - l2 * w                      # L2 收缩：交互项参数量翻倍 ⇒ 必须加
    return w, float(np.mean(G))


class Ema:
    """EMA（Polyak）权重平均 ⇒ 部署策略不用挑 checkpoint（避免"在留出上挑赢家"）。"""

    def __init__(self, dim, beta=0.9):
        self.beta = beta
        self.v = None
        self.dim = dim

    def update(self, w):
        if self.v is None:
            self.v = np.array(w, dtype=float)
        else:
            self.v = self.beta * self.v + (1 - self.beta) * np.array(w, dtype=float)
        return self.v
