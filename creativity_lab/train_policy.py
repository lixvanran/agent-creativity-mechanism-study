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

# ★ 修正：这里必须插**仓库根**（脚本所在目录的上一级），
#   否则 `from creativity_lab.client import ...` 找不到模块（脚本不能直接跑）。
_PKG_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PKG_PARENT)
sys.path.insert(0, os.path.join(_PKG_PARENT, "creativity_lab"))
from creativity_lab.client import LLM                        # noqa: E402
from creativity_lab.metrics import _mat                      # noqa: E402
from creativity_lab.ops import (OPS, Graph, assemble, op_features)  # noqa: E402
from creativity_lab.verify import check_claims, extract_claims  # noqa: E402

OUT = os.environ.get("POLICY_OUT", "runs/arch_learn_fixed")


def ckpt(obj):
    """原子写：先写 .tmp 再 os.replace ⇒ 进程被杀不会留下半个 json。"""
    p = "%s/result.json" % OUT
    json.dump(obj, open(p + ".tmp", "w"), ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)
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
# softmax 温度（**作用于标准化后的分数** ⇒ 相对锐度，与 ‖w‖ 无关）
# 旧默认 0.02 是在**未标准化**分数上用的 ⇒ 实测 n_eff=1.19 ⇒ 策略塌成确定性 ⇒ 权重冻结
TAU = float(os.environ.get("POLICY_TAU", "1.2"))

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


# ---------------------------------------------------------------- 候选选择（可测）
def policy_probs(s):
    """★ 尺度无关的策略分布（行为采样与梯度更新**共用这一份** ⇒ 仍然 on-policy）。

    **为什么必须标准化分数**（2026-10-21 实测）：
      softmax(s/τ) 的锐度取决于 **s 的绝对跨度**，而 s = w·f 的跨度随 ‖w‖ 增长。
      实测：τ=0.02、‖w‖=0.11 时 n_eff 已只剩 **1.19**（≈确定性）⇒ 轨迹无方差
            ⇒ 优势≈0 ⇒ 梯度≈0 ⇒ **权重冻结**（实测轮1→轮2 ‖w‖ 一点没变）。
      ⇒ 固定 τ 只会把塌缩往后推几轮。
    **修法**：先把分数标准化（减均值除标准差），再除以 τ ⇒
      τ 表示的是**相对**锐度，与 ‖w‖ 无关 ⇒ 全程保持探索。
      副带好处：π 对 ‖w‖ 缩放不变 ⇒ 梯度始终与 w 正交 ⇒ 不会"越长越锐"。
    """
    s = np.asarray(s, dtype=float)
    if s.size <= 1:
        return np.ones(max(s.size, 1)) / max(s.size, 1)
    sd = float(s.std())
    z = (s - s.mean()) / (sd + 1e-8) / max(TAU, 1e-6)
    z = z - z.max()
    p = np.exp(z)
    return p / p.sum()


def rank_and_pick(cands, g, w, step, rng, explore=0.25):
    """给候选打分、排序、采样。**返回的 F 与 s_all 严格同序，choice 是真实下标。**

    ★ 2026-10-20 审计修复的三个点都在这里：
      1) 分数与特征**成对**排序 ⇒ F[i] 与 s_all[i] 描述的是**同一个候选**
      2) s_all 是**干净分**（探索噪声不混进来）
      3) 行为分布 = softmax(s/τ) = 更新时假定的分布 ⇒ **on-policy**
    """
    pairs = []
    for op, tgt in cands:
        f = np.array(op_features(g, op, tgt, step))
        pairs.append((float(w @ f), op, tgt, f))
    if not pairs:
        return None, None, None, None, None, []
    pairs.sort(key=lambda p: -p[0])
    s_clean = np.array([p[0] for p in pairs])
    F = np.array([p[3] for p in pairs])              # ★ 与 s_all 同序
    s_all = s_clean                                   # ★ 干净分
    if explore > 0:
        p = policy_probs(s_clean)          # ★ 尺度无关（与更新端同一份函数）
        choice = int(rng.choices(range(len(pairs)), weights=list(p))[0])
    else:
        choice = 0
    sc, op, tgt, _f = pairs[choice]
    return op, tgt, F, s_all, choice, pairs


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
            # ★ 修复（2026-10-20 审计）：**特征必须与分数同序、且 choice 必须是真实下标**。
        #   旧实现：scored 先排序、cand_f 却是原始顺序 ⇒ order 索引错位
        #          ⇒ F[choice] 记功给了**错的特征行** ⇒ 梯度归因是错的。
        #   另一处旧实现：探索噪声直接加进 sc ⇒ s_all 被污染 ⇒ softmax 建立在噪声上，
        #          且行为策略(带噪 argmax) 与更新假定的分布(线性 softmax) **不一致**。
        # 现在：**分数与特征成对排序**；**s_all 是干净分**；**从同一 softmax 采样**
        #        ⇒ 行为策略 == 更新时假定的策略 ⇒ on-policy。
        op, tgt, F, s_all, choice, _pairs = rank_and_pick(cands, g, w, step, rng, explore)
        if op is None:
            break
        ophist[op] = ophist.get(op, 0) + 1
        traj.append((F, s_all, choice))              # ★ choice 是真实下标

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
        # ★ s_all 现在是**干净分**（探索噪声不再混进来）⇒ π 就是真实的行为策略
        p = policy_probs(s_all)             # ★ 与行为端**同一个函数** ⇒ on-policy
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
    NROUND = int(os.environ.get("POLICY_ROUNDS", "8"))
    # ★ 断点续跑：每个 episode 的 rng 按 (轮号, 题号) 派生 ⇒ **续跑与不续跑逐字等价**
    ck_path = "%s/result.json" % OUT
    start_ep = 1
    if os.environ.get("POLICY_RESUME", "1") == "1" and os.path.exists(ck_path):
        try:
            ck = json.load(open(ck_path))
            if ck.get("history"):
                w = np.array(ck["w"], dtype=float); base = float(ck.get("base", 0.0))
                W = [np.array(v, dtype=float) for v in ck["history"]]
                start_ep = len(W) + 1
                print("↻ 续跑：已完成 %d 轮，从第 %d 轮继续（‖w‖=%.4f）"
                      % (len(W), start_ep, float(np.linalg.norm(w))), flush=True)
        except Exception as e:
            print("⚠ checkpoint 读取失败，改为从头训练：%s" % e, flush=True)
    for ep in range(start_ep, NROUND + 1):
        tot, batch = [], []
        # ★ 同一轮内的各个 episode **相互独立**（共用同一个 w）⇒ 可以并行。
        #   每个 episode 用**自己派生的 rng** ⇒ 并行不改变随机序列的可复现性。
        def _run(pair):
            i, T = pair
            r = random.Random((7 * 1000 + ep * 97 + i) & 0x7fffffff)
            return run_episode(T, w, r)
        def _run_safe(pair):
            g, rew, info = _run(pair)
            try:
                print("     · 轮%d 完成 %s ｜ 宽度 %s ｜ 步数 %s"
                      % (ep, pair[1].get("tid", "?"), info.get("width", "?"),
                         info.get("steps", "?")), flush=True)
            except Exception:
                pass
            return g, rew, info
        with ThreadPoolExecutor(max_workers=int(os.environ.get("POLICY_WORKERS", "5"))) as ex:
            results = list(ex.map(_run_safe, list(enumerate(TRAIN))))
        for g, rew, info in results:
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
        ckpt(dict(w=w.tolist(), base=float(base),
                  history=[[x.tolist() for x in v] for v in W]))
        print("       [checkpoint] 轮 %d/%d 已落盘" % (ep, NROUND), flush=True)

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
