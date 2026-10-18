# -*- coding: utf-8 -*-
"""架构学习：在线策略学习（每步奖励），不是「在题集上挑赢家」。

与 train_agent.py（巡练）的根本差别：
  巡练：从 4608 个规格里**挑 1 个**，训练题选、留出题判 → ρ=0.166，过拟合
  本脚本：一个**策略**在每道题上跑图搜索，产生**逐步奖励**，
          策略权重在线更新，**每道题都用上** → 有效 n = 决策次数（数百），不是题数

奖励设计（来自实测）：
  VERIFY 成功   +1        ← 唯一被实测证明有效的动作
  VERIFY 矛盾   −2        ← 自信地说错，比少说一句更糟
  终局          + 交付宽度（去重并集）  ← 探索量
  终局          矛盾率超上限 → 罚      ← 硬约束
装配：机械拼装，不由模型重写 → 矛盾率构造上为 0
"""
from __future__ import annotations

import json
import os
import re
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM                        # noqa: E402
from creativity_lab.metrics import _mat                      # noqa: E402
from creativity_lab.ops import (OPS, Graph, assemble, op_features)  # noqa: E402
from creativity_lab.verify import check_claims, extract_claims  # noqa: E402

OUT = "runs/arch_learn"
os.makedirs(OUT, exist_ok=True)
DATA = json.load(open("creativity_lab/data/policy_topics.json", encoding="utf-8"))
LAWS, TOPICS = DATA["laws"], DATA["topics"]
law_of = {t["tid"]: t["law"] for t in TOPICS}
TRAIN = TOPICS[:5]
TEST = TOPICS[5:]
CONFLICT_CAP = 0.33

ANGLES = ["适用规则来源", "踩红线的做法", "办理流程与材料", "按情形分别处理",
          "时间与顺序要求", "例外与特殊情形"]
GEN_Q = "问题：{ask}\n\n{ang}\n\n给出你的判断与具体做法，400字以内。"
EXTRACT_Q = ("从下面这段回答里，逐条列出其中**可判真假的陈述**（数字、法规、权利义务、"
             "程序、时限、主体责任）。不要观点和建议。一行一条，最多 10 条。\n\n{t}")
SPLIT_Q = ("把下面这条陈述拆成可以分别核验的独立陈述（如果它含多个断言就拆开）。"
           "一行一条，只输出拆分结果。\n\n{c}")


def embed_rows(ts):
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    return _mat(LLM().embed(uniq))[idx]


def dedup_n(claims, thr=0.75):
    if not claims:
        return []
    M = embed_rows(claims)
    S = M @ M.T
    keep = []
    for i in range(len(claims)):
        if all(S[i, j] < thr for j in keep):
            keep.append(i)
    return [claims[i] for i in keep]


# ---------------------------------------------------------------- 一个 episode
def run_episode(topic, w, rng, budget=10, explore=0.25):
    """跑一遍图搜索，返回 (图, 逐步奖励列表, 最终奖励)。"""
    g = Graph()
    ev = LAWS[law_of[topic["tid"]]]["evidence"]
    ask = topic["ask"]
    rewards = []
    traj = []                     # 逐步 (候选特征矩阵, 分数, 选中下标)
    ophist = {}
    n_verify = n_hit = n_miss = 0
    step = 0
    while step < budget:
        step += 1
        # ---- 候选边 ----
        cands = []
        cands.append(("GEN_PLAIN", None))
        cands.append(("GEN_ANGLE", None))
        # **EXTRACT 必须在候选里**，否则图里永远没有 CLAIM 节点，
        # VERIFY / SPLIT 就永远不可选 —— 策略根本学不到「去核验」。
        for n in g.of_kind("ANSWER")[-1:]:
            cands.append(("EXTRACT", n))
        unverified = [n for n in g.of_kind("CLAIM") if n.verdict is None]
        for n in unverified[:2]:
            cands.append(("VERIFY", n))
        for n in g.of_kind("CLAIM")[:1]:
            if n.verdict in (None, "未提及"):
                cands.append(("SPLIT", n))
        # STOP 只在**至少核验过一次**后合法：否则 episode 在还没抽出断言时就结束，
        # 策略永远走不到 VERIFY 阶段（实测：平均 2.8 步就停，VERIFY=0）。
        # 这是 episode 的**有效性约束**，不是给某个动作加偏好。
        if n_verify >= 1:
            cands.append(("STOP", None))
        # ---- 打分（学出来的权重）----
        cand_f = []
        scored = []
        for op, tgt in cands:
            f = np.array(op_features(g, op, tgt, step))
            cand_f.append(f)
            sc = float(w @ f)
            if rng.random() < explore:          # ε-greedy
                sc += rng.random() * 2.0
            scored.append((sc, op, tgt))
        scored.sort(key=lambda x: -x[0])
        op, tgt = scored[0][1], scored[0][2]
        ophist[op] = ophist.get(op, 0) + 1
        # 存**候选特征矩阵**（按分数降序）与选中项的下标 —— softmax 的期望项要用
        order = [i for i, _ in sorted(enumerate(scored), key=lambda x: -x[1][0])]
        F = np.array([cand_f[i] for i in order])
        s_all = np.array([scored[i][0] for i in order])
        choice = 0
        traj.append((F, s_all, choice))
        op, tgt = scored[0][1], scored[0][2]

        if op == "STOP":
            break
        if op == "GEN_PLAIN":
            a = LLM().chat(GEN_Q.format(ask=ask, ang=""), model="MiniMax-M3",
                           purpose="al_gen", min_ok=150)
            if a and len(a) > 40:
                g.add("ANSWER", a, op="GEN_PLAIN")
            rewards.append(0.0)
        elif op == "GEN_ANGLE":
            ang = ANGLES[rng.randrange(len(ANGLES))]
            a = LLM().chat(GEN_Q.format(ask=ask, ang="从「%s」的角度切入。" % ang),
                           model="MiniMax-M3", purpose="al_gen", min_ok=150)
            if a and len(a) > 40:
                g.add("ANSWER", a, op="GEN_ANGLE", angle=ang)
            rewards.append(0.0)
        elif op == "EXTRACT":
            answers = g.of_kind("ANSWER")
            if not answers:
                rewards.append(0.0); continue
            src = answers[-1]
            t = LLM().chat(EXTRACT_Q.format(t=src.text[:1200]), model="MiniMax-M3",
                           purpose="al_ex", max_tokens=1400, budgets=(2000,), min_ok=15)
            got = 0
            for ln in (t or "").splitlines():
                ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
                if 8 <= len(ln) <= 60:
                    g.add("CLAIM", ln, parent=src.nid, op="EXTRACT")
                    got += 1
                if got >= 10: break
            rewards.append(0.0)
        elif op == "SPLIT":
            t = LLM().chat(SPLIT_Q.format(c=tgt.text), model="MiniMax-M3",
                           purpose="al_split", max_tokens=800, budgets=(1200,), min_ok=10)
            got = 0
            for ln in (t or "").splitlines():
                ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
                if 8 <= len(ln) <= 60 and ln != tgt.text:
                    g.add("CLAIM", ln, parent=tgt.nid, op="SPLIT")
                    got += 1
                if got >= 4: break
            rewards.append(0.0)
        elif op == "VERIFY":
            v = check_claims(LLM(), ask, ev, [tgt.text])
            vd = v.get(tgt.text, "解析失败")
            tgt.verdict = vd
            n_verify += 1
            if vd == "支持":
                n_hit += 1; rewards.append(1.0)
            elif vd == "矛盾":
                n_miss += 1; rewards.append(-2.0)
            else:
                rewards.append(0.0)
        else:
            rewards.append(0.0)

    # ---- 终局：机械装配 + 宽度 + 约束 ----
    final = assemble(g, ask)
    claims = extract_claims(LLM(), final)
    verd = check_claims(LLM(), ask, ev, claims) if claims else {}
    legal = [c for c in claims if verd.get(c) in ("支持", "矛盾")]
    ncon = sum(1 for c in legal if verd.get(c) == "矛盾")
    crate = ncon / max(len(legal), 1)
    width = len(dedup_n([c for c in claims], 0.75))
    fin = 0.0
    if crate <= CONFLICT_CAP:
        fin += width / 5.0
    else:
        fin -= 2.0
    rewards.append(fin)
    g._traj = traj
    return g, rewards, dict(width=width, conflict=crate, n_legal=len(legal),
                             n_verify=n_verify, hit=n_hit, miss=n_miss, fin=fin,
                             ops=dict(ophist))


# ---------------------------------------------------------------- 策略更新
def returns(rewards, gamma=0.9):
    R, G = 0.0, []
    for r in reversed(rewards):
        R = r + gamma * R
        G.append(R)
    G.reverse()
    return np.array(G)


def reinforce(w, traj, rewards, lr=0.05, gamma=0.9, baseline=0.0):
    """REINFORCE：∇log π(a|s) = φ(s,a) − E_{a'~π}[φ(s,a')]
    期望项用同一步候选动作的特征均值近似（采样近似）。"""
    if not traj:
        return w, baseline
    G = returns(rewards, gamma)
    adv = G - baseline
    gw = np.zeros_like(w)
    for (F, s_all, choice), a in zip(traj, adv):
        # 线性 softmax：∇log π(a*) = φ_{a*} − Σ_i π_i φ_i
        z = s_all - s_all.max()
        p = np.exp(z); p = p / p.sum()
        grad = F[choice] - (p[:, None] * F).sum(axis=0)
        gw += a * grad
    return w + lr * gw / len(traj), float(np.mean(G))


def main():
    t0 = time.time()
    rng = random.Random(7)
    np.random.seed(7)
    w = np.zeros(14)
    W = []
    print("策略学习：每题 %d 步预算，ε=0.25，终局宽度/约束奖励" % 10, flush=True)
    print("训练题 %s ｜ 测试题 %s\n" % ([t["tid"] for t in TRAIN], [t["tid"] for t in TEST]),
          flush=True)

    base = 0.0
    for ep in range(1, 9):
        tot, batch = [], []
        for T in TRAIN:
            g, rew, info = run_episode(T, w, rng)
            tot.append(info)
            batch.append((getattr(g, "_traj", []), rew))
        for (traj, rew) in batch:
            w, base = reinforce(w, traj, rew, baseline=base)
        W.append(w.copy())
        agg_ops = {}
        for x in tot:
            for k, v in x["ops"].items(): agg_ops[k] = agg_ops.get(k, 0) + v
        print("  轮%d  平均宽度 %.2f  矛盾率 %.1f%%  核验 %.2f 次(中%.2f)  终局奖 %.2f"
              % (ep, np.mean([x["width"] for x in tot]),
                 100 * np.mean([x["conflict"] for x in tot]),
                 np.mean([x["n_verify"] for x in tot]), np.mean([x["hit"] for x in tot]),
                 np.mean([x["fin"] for x in tot])), flush=True)
        print("       操作分布: " + "  ".join("%s=%d" % (k, v)
              for k, v in sorted(agg_ops.items(), key=lambda x: -x[1])), flush=True)

    # ---- 测试 ----
    print("\n== 测试（未见题）==", flush=True)
    for name, Wv in (("初始策略 w=0", np.zeros(14)), ("学到的策略", w)):
        rows = []
        for T in TEST:
            g, rew, info = run_episode(T, Wv, random.Random(99))
            rows.append(info)
        print("  %-14s 宽度 %.2f  矛盾率 %.1f%%  核验 %.2f 次(中%.2f)  终局奖 %.2f"
              % (name, np.mean([r["width"] for r in rows]),
                 100 * np.mean([r["conflict"] for r in rows]),
                 np.mean([r["n_verify"] for r in rows]), np.mean([r["hit"] for r in rows]),
                 np.mean([r["fin"] for r in rows])), flush=True)
    json.dump(dict(w=w.tolist(), history=[[x.tolist() for x in v] for v in W]),
              open("%s/result.json" % OUT, "w"), ensure_ascii=False, indent=1)
    print("\n总耗时 %.0f 分钟" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
