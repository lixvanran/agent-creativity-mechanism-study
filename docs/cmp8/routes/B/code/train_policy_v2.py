# -*- coding: utf-8 -*-
"""路线 B v2：**训练算法参考实现**（在线策略学习，架构由训练产生）。

与旧 `creativity_lab/train_policy.py` 的关系：
  · **沿用**已修好的四件事：动作—特征成对排序、on-policy 共享 `policy_probs`、
    尺度无关温度、f[6] 索引冲突（v2 直接重定义特征，无同类坑）。
  * **改掉**特征空间：加 (op 类别 × 信息缺口) 交叉项 ⇒ 状态**能**改变偏好顺序。
    ⚠️ 纯加性的全局特征在 softmax 里是**公共常数** ⇒ 对选择行为**零作用**
    （负责人 2026-10-20 实测 3）⇒ 缺口信息**必须**做成交叉项。
  · **新加**：τ 控制器（防塌缩）、EMA 权重平均、轨迹多样性监控、代理校准闸门、
    **精确策略梯度**（标准化 softmax 的 log-π 梯度含 mean/std 的 Jacobian，
    解析近似式是有偏的 ⇒ 见 `policy_logprob_grad` 与 `test_policy_grad.py`）。

依赖：`ops_v2.py` / `evidence_index.py` / `monitor.py`（同目录）。
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ops_v2 import (CLASSES, FEAT_DIM, OPS_V2, SLOTS, STD_EPS, Graph, candidates,  # noqa: E402
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


# ───────────────────────────────────────── 精确策略梯度（修正旧实现的有偏估计）
def policy_logprob_grad(F, s, tau: float, choice: int) -> np.ndarray:
    """∇_w log π(a|s) 的**精确**表达式（π = softmax(z)，z = (s−mean(s))/(σ̃·τ)）。

    ⚠️ **为什么不能只用 `φ_a − Σ_i π_i φ_i`**（旧实现的解析式）：
       标准化（减均值、除标准差）把 s 的 **mean/std 也变成了 w 的函数**，
       所以 ∂z/∂w 除了 `F_i − F̄` 之外还有一项 `−(s_i−μ)/(τσ̃²)·∂σ̃/∂w`。
       漏掉这一项 ⇒ 估计量**有偏**（方向大体对，但不是 score function）。
       ⚠️ 旧实现是 cmp8 已修好的部分（plan 明确"不要重复发明"），
       **但本设计重新推导并公示了这条公式 ⇒ 必须标出它的偏差**；
       这里直接给出**精确**版本，并用 `test_policy_grad.py` 对拍数值梯度。

    推导（σ̃ = sqrt(σ² + STD_EPS²) 是 `ops_v2.policy_probs` 用的同一个平滑标准差）：
       μ = mean(s)，σ = std(s)，σ̃ = sqrt(σ²+ε²)，z_i = (s_i − μ)/(τσ̃)
       ∂μ/∂w = F̄                              （F̄ = 候选特征的行均值）
       ∂σ/∂w = mean((s−μ)⊙F)/σ
       ∂σ̃/∂w = (σ/σ̃)·∂σ/∂w
       ∂z_i/∂w = (F_i − F̄)/(τσ̃) − (s_i−μ)/(τσ̃²)·∂σ̃/∂w
       ∇log π_a = ∂z_a/∂w − Σ_i π_i ∂z_i/∂w
    """
    F = np.asarray(F, dtype=float)
    s = np.asarray(s, dtype=float)
    mu = float(s.mean())
    sd = float(s.std())
    sd_safe = float(np.sqrt(sd * sd + STD_EPS * STD_EPS))
    Fbar = F.mean(axis=0)
    dsigma = ((F - mu) * (s - mu)[:, None]).mean(axis=0) / sd_safe   # ∂σ̃/∂w
    dz = (F - Fbar) / (tau * sd_safe) \
        - ((s - mu)[:, None] / (tau * sd_safe * sd_safe)) * dsigma[None, :]
    p = policy_probs(s, tau)
    return dz[choice] - (p[:, None] * dz).sum(axis=0)


# ───────────────────────────────────────── 调用记录
def _last_call(llm):
    """取**最后一次尝试**的调用记录（client 每个 attempt 记一条）。"""
    rec = getattr(llm, "rec", None)
    return rec[-1] if rec else None


def _call_flags(llm):
    """返回 (truncated, empty)。

    ⚠️ 截断判定：`finish_reason == "length"` ⇒ 该次尝试**撞 max_tokens 被砍**。
    ⚠️ client 的行为：`finish_reason == "length"` 时会**用更大的预算重试**；
       若预算用尽，它把**截断的残缺内容当成正常结果返回**，空串时返回 ""
       ⇒ **该步静默变成空操作**（分母被悄悄缩小 ⇒ 协议 F8 同族风险）。
    ⇒ 因此每次逻辑调用后都要**显式**判定截断，并把它记进 episode 的账。
    """
    c = _last_call(llm)
    if c is None:
        return False, False
    return (c.finish_reason == "length"), (c.content_len == 0)


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
    """
    g = Graph()
    ask = topic["ask"]
    anchored = set(ev_index.anchored_ids)
    covered = set()               # **已覆盖的锚定依据条目**（步级奖励按它去重）
    rewards, traj = [], []
    ophist = {}
    n_verify = 0
    slot_idx = 0
    n_trunc = 0                   # 被 max_tokens 截断的步数
    n_empty = 0                   # 产出为空的步数（静默空操作）
    trunc_steps = []
    n_effs = []

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
            ne = n_eff(p)
            n_effs.append(ne)
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
            tr, em = _call_flags(llm)
            n_trunc += int(tr)
            n_empty += int(em)
            if tr:
                trunc_steps.append(op)
            if a and len(a) > 20:
                g.add("ANSWER", a, op=op)
            rewards.append(0.0)
        elif op == "EXTRACT":
            src = tgt
            t = llm.chat(EXTRACT_Q.format(t=src.text[:1200]), model=model,
                         purpose="al_ex", max_tokens=2000, budgets=(3200, 4400),
                         min_ok=15)
            if raw_log is not None:
                raw_log.append(dict(op="EXTRACT", raw=(t or "")[:1200]))
            tr, em = _call_flags(llm)
            n_trunc += int(tr)
            n_empty += int(em)
            if tr:
                trunc_steps.append("EXTRACT")
            for ln in (t or "").splitlines():
                ln = re.sub(r"^\s*[-*•]\s*", "", ln)
                ln = re.sub(r"^\s*\d+[.、)]\s*", "", ln).strip()
                if 8 <= len(ln) <= 60:
                    g.add("CLAIM", ln, parent=src.nid, op="EXTRACT")
                if sum(1 for c in g.of_kind("CLAIM")) >= 10:
                    break
            rewards.append(0.0)
        elif op == "SPLIT":
            t = llm.chat(SPLIT_Q.format(c=tgt.text), model=model,
                         purpose="al_split", max_tokens=1600, budgets=(2400, 3200),
                         min_ok=10)
            if raw_log is not None:
                raw_log.append(dict(op="SPLIT", raw=(t or "")[:1200]))
            tr, em = _call_flags(llm)
            n_trunc += int(tr)
            n_empty += int(em)
            if tr:
                trunc_steps.append("SPLIT")
            for ln in (t or "").splitlines():
                ln = re.sub(r"^\s*[-*•]\s*", "", ln)
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
            tr, em = _call_flags(llm)
            n_trunc += int(tr)
            n_empty += int(em)
            if tr:
                trunc_steps.append("VERIFY")
            n_verify += 1
            # ★ 步级奖励**按依据条目去重**（不是按核验次数）：
            #   新覆盖一个锚定条目 +1.0；重复覆盖同一条目 **+0** ⇒
            #   "把同一件事改写三遍再核验三遍" 拿不到分（修 F7）。
            r_step = 0.0
            for n in tgt_list:
                v = verd.get(n.text)
                if not v:
                    continue
                n.verdict = v["rel"]
                n.meta["items"] = v["items"]
                if v["rel"] == "支持":
                    new = (set(v["items"]) & anchored) - covered
                    covered |= new
                    r_step += 1.0 * len(new)
                elif v["rel"] == "矛盾":
                    r_step -= 2.0
            rewards.append(r_step)

    # ── 终局：机械装配 + 代理计算 ──
    claims = [c.text for c in g.of_kind("CLAIM")]
    verd = {c.text: {"rel": c.verdict or "未核验", "items": c.meta.get("items", [])}
            for c in g.of_kind("CLAIM")}
    rep = proxy_report(ev_index, verd, claims)
    fin = terminal_reward(rep, CONFLICT_CAP, ALPHA)
    rewards.append(fin)
    info = dict(topic_id=topic["topic_id"], width=len(claims), ops=dict(ophist),
                n_verify=n_verify, final_reward=fin, proxy=rep,
                steps=len(traj), signature=seq_signature([t[4] for t in traj]),
                n_eff_list=n_effs,
                # ── 截断/空产出（协议 F8 同族风险，必须单独记账）──
                n_truncated=n_trunc, n_empty=n_empty,
                truncated_rate=(n_trunc / max(len(traj), 1)),
                truncated_steps=trunc_steps)
    return g, traj, rewards, info


# ───────────────────────────────────────── 策略更新（on-policy REINFORCE）
def reinforce(w, traj, rewards, lr=0.05, gamma=0.9, baseline=0.0, l2=0.01,
              grad_clip=1.0, base_decay=0.9):
    """REINFORCE：∇log π(a|s) 的 REINFORCE 估计量。

    ⚠️ on-policy 的三个必要条件（缺一不可）：
      ① 行为分布 = 更新时假定的分布 ⇒ 用**同一个** `policy_probs`
      ② 行为端用过的 τ 必须**原样带回**（温度会随训练变动！）⇒ traj 里存了 tau_used
      ③ 分数与特征**成对排序** ⇒ F[choice] 与 s[choice] 描述同一个候选

    ⚠️ 梯度用**精确**的 `policy_logprob_grad`（标准化 softmax 的 log-π 梯度含
       mean/std 的 Jacobian；旧实现的 `φ_a − Σπφ_i` 解析式**有偏** ⇒ 见该函数 docstring）。
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
        grad = policy_logprob_grad(F, s_all, tau_used, choice)   # ★ 精确梯度
        gw += a * grad
    gw = gw / max(len(traj), 1)
    # ★ 梯度裁剪（必须有）：σ̃ 的平滑项让梯度在 w=0 附近仍**有界但很大**（≤1/STD_EPS）
    #   ⇒ 不裁剪的话第一步就把 w 推到 ~1e10（实测）。
    #   裁剪是标准的稳定性做法，且**不改变梯度的方向**（只改步长）。
    gn = float(np.linalg.norm(gw))
    if grad_clip and gn > grad_clip:
        gw = gw * (grad_clip / gn)
    w = w + lr * gw - l2 * w                      # L2 收缩：交互项参数量翻倍 ⇒ 必须加
    # 滑动基线：**运行均值**（不是"最后一个 episode 说了算"）
    gbar = float(np.mean(G))
    baseline = (1.0 - base_decay) * float(baseline) + base_decay * gbar
    return w, float(baseline)


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


# ───────────────────────────────────────── 训练循环（§3.6 伪代码的可执行版）
def run_training(topics, ev_index, *, llm=None, model="MiniMax-M3.1-Flash-Preview",
                 rounds=8, w=None, lr=0.05, gamma=0.9, l2=0.01, baseline=0.0,
                 workers=5, out_dir=None, budget=10, tau0=1.2, seed=7,
                 init="small_random", init_scale=0.01,
                 holdout=None, calibration=None, early_stop_on_fatal=True,
                 resume=True, progress=None):
    """**完整的训练循环**（DESIGN §3.6）。

    topics:    [{"topic_id", "ask"}]
    ev_index: {topic_id: EvidenceIndex}
    holdout:   可选 [{"topic_id","ask"}] ⇒ 只用于**监控**（留出纪律：绝不用于挑 checkpoint）
    calibration: 可选 {"spearman": float, "threshold": float, "subset": str}
                ⇒ §4.4 的校准闸门：低于阈值 ⇒ **停止训练**（FB6）
    返回 dict(w=..., ema=..., baseline=..., history=..., monitor=..., stopped_reason=...)

    ⚠️ `llm=None` ⇒ 用**离线 stub**（`stub_llm.StubLLM`）⇒ 0 次真实 API 调用，
       用来证明循环可执行（**不产生任何学习效果结论**）。
    """
    if llm is None:
        from stub_llm import StubLLM
        llm = StubLLM()
    say = progress or (lambda *a, **k: None)

    monitor = Monitor()
    ema = Ema(FEAT_DIM)
    # ⚠️ 训练初始权重：**小随机**（默认），**不是**全零。
    #   理由：w=0 ⇒ 所有候选同分 ⇒ σ=0 ⇒ 策略均匀且梯度的**方向**退化
    #   （实测第一步梯度范数 1.2e3，只能靠裁剪兜住）⇒ 学习信号弱且不稳。
    #   ⚠️ `w=0` 仍然是**对照臂** R_w0（含义＝"没有学习"），两者不冲突。
    if w is None:
        if init == "zeros":
            w = np.zeros(FEAT_DIM)
        else:
            w = np.random.default_rng(seed).normal(0, init_scale, FEAT_DIM)
    history = []
    ck_path = os.path.join(out_dir, "result.json") if out_dir else None
    start_round = 1
    if resume and ck_path and os.path.exists(ck_path):
        try:
            ck = json.load(open(ck_path, encoding="utf-8"))
            w = np.array(ck["w"], dtype=float)
            baseline = float(ck.get("baseline", 0.0))
            history = ck.get("history", [])
            if ck.get("ema"):
                ema.v = np.array(ck["ema"], dtype=float)
            start_round = len(history) + 1
            say("↻ 续跑：从第 %d 轮开始（‖w‖=%.4f）" % (start_round, float(np.linalg.norm(w))))
        except Exception as e:                       # pragma: no cover
            say("⚠ checkpoint 读取失败，改为从头训练：%s" % e)

    stopped_reason = ""
    for r in range(start_round, rounds + 1):
        w_prev = w.copy()
        tau_ctrl = TauController(tau=tau0)
        results = []

        def _one(pair):
            i, T = pair
            rng = random.Random((seed * 1000 + r * 97 + i) & 0x7FFFFFFF)
            return run_episode(T, ev_index[T["topic_id"]], w, rng, llm=llm,
                               model=model, budget=budget, tau_ctrl=tau_ctrl)

        pairs = list(enumerate(topics))
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                results = list(ex.map(_one, pairs))
        else:
            results = [_one(p) for p in pairs]

        # ── 逐 episode 更新（滑动基线）──
        for (g, traj, rew, info) in results:
            w, baseline = reinforce(w, traj, rew, lr=lr, gamma=gamma,
                                    baseline=baseline, l2=l2)
        ema.update(w)

        # ── 本轮汇总 ──
        op_counts = {}
        ne_all, conflicts, widths, sigs, trunc, empt = [], [], [], [], 0, 0
        for (_g, _t, _r, info) in results:
            for k, v in info["ops"].items():
                op_counts[k] = op_counts.get(k, 0) + v
            ne_all.extend(info["n_eff_list"])
            conflicts.append(info["proxy"]["conflict_rate"])
            widths.append(info["width"])
            sigs.append(info["signature"])
            trunc += info["n_truncated"]
            empt += info["n_empty"]
        rew_mean = float(np.mean([info["final_reward"] for (_g, _t, _r, info) in results]))

        # ── 留出：只做监控（**绝不**用于挑 checkpoint）──
        holdout_spear = None
        if holdout:
            holdout_spear = _holdout_spearman(w, holdout, ev_index, llm, model, budget)

        row = monitor.update_round(
            round_id=r, w=w, w_prev=w_prev, reward_mean=rew_mean, n_eff_list=ne_all,
            op_counts=op_counts, conflict_rate=float(np.mean(conflicts)) if conflicts else 0.0,
            seed_noise_floor=None, width_mean=float(np.mean(widths)) if widths else 0.0,
            holdout_spearman=holdout_spear,
            seq_signature_entropy=seq_diversity(sigs),
            proxy_spearman=(calibration or {}).get("spearman"))
        alarms = monitor.evaluate()
        row["n_truncated"] = trunc
        row["n_empty"] = empt
        row["truncated_rate"] = trunc / max(len(ne_all) + len(results), 1)
        history.append(row)
        say("轮 %d/%d  奖励 %.3f  n_eff %.2f  ops %s  宽度 %.1f  矛盾 %.1f%%  ‖w‖ %.4f  告警 %d" % (
            r, rounds, rew_mean, row["n_eff_mean"],
            " ".join("%s=%d" % kv for kv in sorted(op_counts.items(), key=lambda x: -x[1])),
            row["width_mean"], 100 * row["conflict_rate"], row["w_norm"], len(alarms)))

        if ck_path:
            os.makedirs(out_dir, exist_ok=True)
            tmp = ck_path + ".tmp"
            json.dump(dict(w=w.tolist(), ema=(ema.v.tolist() if ema.v is not None else None),
                           baseline=float(baseline), history=history,
                           monitor=monitor.report(), stopped_reason=stopped_reason),
                      open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(tmp, ck_path)

        # ── 早停闸门 ①：代理校准不过（FB6）⇒ **目标无效**，优先级最高 ──
        if calibration and calibration.get("spearman") is not None:
            if calibration["spearman"] < calibration.get("threshold", 0.5):
                stopped_reason = "calibration_failed:%.3f<%.3f" % (
                    calibration["spearman"], calibration.get("threshold", 0.5))
                say("⛔ 代理校准不过 ⇒ 停止训练：%s" % stopped_reason)
                break
        # ── 早停闸门 ②：fatal 告警（塌缩 / 权重冻结 / 矛盾越界 / 留出漂移 / 搜索闭合）──
        fatal = [a for a in alarms if a["level"] == "fatal"]
        if fatal and early_stop_on_fatal:
            stopped_reason = "fatal_alarm:" + ",".join(a["code"] for a in fatal)
            say("⛔ fatal 告警 ⇒ 停止训练：%s" % stopped_reason)
            break

    return dict(w=w.tolist(), ema=(ema.v.tolist() if ema.v is not None else None),
                baseline=float(baseline), history=history, monitor=monitor.report(),
                stopped_reason=stopped_reason)


def _holdout_spearman(w, holdout, ev_index, llm, model, budget):
    """留出题上的**排名漂移**监控量（Spearman）。

    ⚠️ 留出**只做监控**：这个数**绝不**用于挑选 checkpoint（协议 R-9/§3.6 留出纪律）。
    """
    scores = []
    for T in holdout:
        g, traj, rew, info = run_episode(T, ev_index[T["topic_id"]], w,
                                         random.Random(1234), llm=llm, model=model,
                                         budget=budget)
        scores.append(info["proxy"]["w_hat"])
    if len(scores) < 2:
        return None
    return float(_spearman(scores, scores))   # 单臂时退化为 1.0（无漂移可比）


def _spearman(a, b):
    n = len(a)
    if n < 2:
        return 1.0
    ra = {v: i for i, v in enumerate(sorted(a))}
    rb = {v: i for i, v in enumerate(sorted(b))}
    d2 = sum((ra[x] - rb[y]) ** 2 for x, y in zip(a, b))
    return 1.0 - 6.0 * d2 / (n * (n * n - 1))
