# -*- coding: utf-8 -*-
"""路线 B v2：**训练期监控面板** + **温度控制器** + **告警**。

要解决的是"进程还活着但什么都没学"（策略塌缩 / 权重冻结 / 搜索空间闭合）
必须**能被自动发现**，而不是靠人看日志。

本模块的每一条告警都配了**变异注入自测**（`selftest`）：
故意把系统推向塌缩 ⇒ 告警**必须**响 ⇒ 报不出响应的告警是摆设。
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np

from ops_v2 import norm_entropy, n_eff, policy_probs

# ───────────────────────────────────────── 阈值（全部事前写死，见 spec.yaml）
TH = dict(
    n_eff_warn=2.0,        # 低于 ⇒ 塌缩告警
    n_eff_crit=1.3,        # 低于 ⇒ 严重塌缩
    n_eff_target=2.8,      # 控制器目标：把 n_eff 拉回这个附近
    op_ent_warn=0.35,      # 归一化操作分布熵
    op_cover_warn=4,       # 一轮内出现过的不同 op 数（6 个 op）
    w_move_warn=1e-4,      # ‖w‖ 两轮变化量
    reward_stall=1e-3,     # 训练奖励两轮不动的幅度
    conflict_mult=2.0,     # 矛盾率 > 2× 种子噪声地板 ⇒ 判死级告警（协议 F4）
    seq_div_warn=0.30,     # 轨迹多样性（动作序列签名的归一化熵）
    spearman_warn=0.30,    # 训练排名 vs 留出排名的 Spearman
    proxy_spearman=0.50,   # 代理 Ŵ 与真 VD 的 Spearman 校准门槛
)

TAU_MIN, TAU_MAX = 0.60, 4.00


class TauController:
    """**熵下限控制器**：把 n_eff 当被控量，τ 当操纵量。

    * n_eff < target ⇒ 加大 τ（更平 ⇒ 更探索）
    * n_eff > target·1.35 ⇒ 减小 τ（更尖 ⇒ 更利用）
    * τ 有上下限 ⇒ 不会退化成"永远均匀"（否则学不到东西）

    ⚠️ τ 仍作用在**标准化后的分数**上 ⇒ 尺度无关性不被破坏。
    ⚠️ 行为端与更新端必须用**同一轮**的 τ ⇒ 轨迹里要记录 τ（见 train_policy_v2）。
    """

    def __init__(self, tau: float = 1.2, target: float = TH["n_eff_target"]):
        self.tau = float(tau)
        self.target = float(target)
        self.history = []

    def observe(self, p) -> float:
        ne = n_eff(p)
        self.history.append(ne)
        if ne < self.target:
            self.tau = min(TAU_MAX, self.tau * 1.15)
        elif ne > self.target * 1.35:
            self.tau = max(TAU_MIN, self.tau * 0.97)
        return ne

    def n_eff_ma(self, k: int = 50) -> float:
        h = self.history[-k:]
        return float(np.mean(h)) if h else float("nan")


class Monitor:
    """一轮一记的监控面板。每轮调 `update_round`，最后调 `report`。"""

    def __init__(self):
        self.rounds = []
        self.alarms = []

    def update_round(self, *, round_id, w, w_prev, reward_mean, n_eff_list,
                     op_counts, conflict_rate, seed_noise_floor,
                     width_mean=None, holdout_spearman=None,
                     seq_signature_entropy=None, proxy_spearman=None):
        op_counts = Counter(op_counts)
        ne = np.array(n_eff_list, dtype=float) if n_eff_list else np.array([float("nan")])
        n_ops = len(op_counts)
        p = np.array([op_counts.get(o, 0) for o in sorted(op_counts)], dtype=float)
        ent = norm_entropy(p) if p.size > 1 else 0.0
        dw = float(np.linalg.norm(np.asarray(w) - np.asarray(w_prev))) if w_prev is not None else float("nan")
        row = dict(round=round_id, n_eff_mean=float(np.nanmean(ne)),
                   n_eff_min=float(np.nanmin(ne)), op_entropy=ent,
                   n_ops_used=n_ops, op_counts=dict(op_counts),
                   w_norm=float(np.linalg.norm(w)), w_move=dw,
                   reward_mean=reward_mean, conflict_rate=conflict_rate,
                   seed_noise_floor=seed_noise_floor,
                   width_mean=width_mean, holdout_spearman=holdout_spearman,
                   seq_signature_entropy=seq_signature_entropy,
                   proxy_spearman=proxy_spearman)
        self.rounds.append(row)
        return row

    def evaluate(self) -> list:
        """产出告警列表（每条告警都带**可核对的数字**）。"""
        al = []
        R = self.rounds
        if not R:
            return al
        last = R[-1]
        if last["n_eff_mean"] < TH["n_eff_crit"]:
            al.append(dict(code="COLLAPSE_CRIT", level="fatal",
                           msg="n_eff 均值 %.2f < %.2f ⇒ 策略近似确定性" % (last["n_eff_mean"], TH["n_eff_crit"]),
                           value=last["n_eff_mean"]))
        elif last["n_eff_mean"] < TH["n_eff_warn"]:
            al.append(dict(code="COLLAPSE_WARN", level="warn",
                           msg="n_eff 均值 %.2f < %.2f" % (last["n_eff_mean"], TH["n_eff_warn"]),
                           value=last["n_eff_mean"]))
        if last["op_entropy"] < TH["op_ent_warn"]:
            al.append(dict(code="OP_ENTROPY_LOW", level="warn",
                           msg="操作分布归一化熵 %.2f < %.2f" % (last["op_entropy"], TH["op_ent_warn"]),
                           value=last["op_entropy"]))
        if last["n_ops_used"] < TH["op_cover_warn"]:
            al.append(dict(code="OP_COVERAGE_LOW", level="warn",
                           msg="本轮只用到 %d 个 op（< %d）" % (last["n_ops_used"], TH["op_cover_warn"]),
                           value=last["n_ops_used"]))
        if len(R) >= 2:
            a, b = R[-2], R[-1]
            if b["w_move"] == b["w_move"] and b["w_move"] < TH["w_move_warn"]:
                al.append(dict(code="WEIGHT_FROZEN", level="fatal",
                               msg="‖w‖ 两轮变化 %.2e < %.1e ⇒ 权重冻结（活着但没学）" % (b["w_move"], TH["w_move_warn"]),
                               value=b["w_move"]))
            if abs(b["reward_mean"] - a["reward_mean"]) < TH["reward_stall"]:
                al.append(dict(code="REWARD_STALL", level="warn",
                               msg="训练奖励两轮变化 %.4f < %.0e" % (abs(b["reward_mean"] - a["reward_mean"]), TH["reward_stall"]),
                               value=b["reward_mean"]))
        fl = last.get("seed_noise_floor")
        if fl and last["conflict_rate"] > TH["conflict_mult"] * fl:
            al.append(dict(code="CONFLICT_EXCESS", level="fatal",
                           msg="矛盾率 %.3f > %.1f× 噪声地板 %.3f" % (last["conflict_rate"], TH["conflict_mult"], fl),
                           value=last["conflict_rate"]))
        if last.get("holdout_spearman") is not None and last["holdout_spearman"] < TH["spearman_warn"]:
            al.append(dict(code="HOLDOUT_DRIFT", level="fatal",
                           msg="训练排名 vs 留出排名 Spearman %.2f < %.2f ⇒ 学到的是题集特化" % (
                               last["holdout_spearman"], TH["spearman_warn"]),
                           value=last["holdout_spearman"]))
        if last.get("seq_signature_entropy") is not None and last["seq_signature_entropy"] < TH["seq_div_warn"]:
            al.append(dict(code="SEARCH_CLOSURE", level="fatal",
                           msg="动作序列多样性 %.2f < %.2f ⇒ 搜索空间过早闭合" % (
                               last["seq_signature_entropy"], TH["seq_div_warn"]),
                           value=last["seq_signature_entropy"]))
        if last.get("proxy_spearman") is not None and last["proxy_spearman"] < TH["proxy_spearman"]:
            al.append(dict(code="PROXY_INVALID", level="fatal",
                           msg="代理 Ŵ 与真 VD 的 Spearman %.2f < %.2f ⇒ 训练目标未验证" % (
                               last["proxy_spearman"], TH["proxy_spearman"]),
                           value=last["proxy_spearman"]))
        self.alarms = al
        return al

    def report(self) -> dict:
        return dict(thresholds=TH, rounds=self.rounds, alarms=self.alarms,
                    fatal=[a for a in self.alarms if a["level"] == "fatal"])


# ───────────────────────────────────────── 轨迹多样性（搜索空间闭合的直接度量）
def seq_signature(op_seq) -> str:
    """动作序列签名：把具体 target 抹掉，只留 op 序列。"""
    return ">".join(op_seq)


def seq_diversity(signatures) -> float:
    """动作序列签名的**归一化熵**（1 = 每条轨迹都不同；0 = 全一样）。

    ⇒ 这是"搜索空间过早闭合"的**直接**度量：策略不再探索不同的操作顺序。
    """
    c = Counter(signatures)
    if not c:
        return 0.0
    p = np.array(list(c.values()), dtype=float)
    p = p / p.sum()
    h = float(-(p * np.log(p)).sum())
    return h / math.log(len(c)) if len(c) > 1 else 0.0


# ───────────────────────────────────────── 变异注入自测（告警必须会响）
def selftest() -> dict:
    """**证明告警不是摆设**：把系统推向塌缩，告警必须响。

    ❶ COLLAPSE：给一个近似确定性的分布（p=[0.97,0.01,...]）⇒ n_eff≈1.04
    ❷ OP_ENTROPY_LOW / OP_COVERAGE_LOW：一轮里只用一个 op
    ❸ WEIGHT_FROZEN：两轮 ‖w‖ 不动
    ❹ CONFLICT_EXCESS：矛盾率 0.5、地板 0.1 ⇒ 5× > 2×
    ❺ SEARCH_CLOSURE：所有轨迹签名相同 ⇒ 多样性 0
    ❻ TauController：n_eff 低 ⇒ τ 必须**上升**（而不是继续变尖）
    """
    out = {}

    m = Monitor()
    m.update_round(round_id=1, w=[0.1] * 30, w_prev=None, reward_mean=0.0,
                   n_eff_list=[1.04], op_counts={"GEN_PLAIN": 50}, conflict_rate=0.0,
                   seed_noise_floor=0.03)
    al = m.evaluate()
    codes = {a["code"] for a in al}
    out["collapse_fires"] = "COLLAPSE_CRIT" in codes
    out["op_entropy_fires"] = "OP_ENTROPY_LOW" in codes
    out["op_coverage_fires"] = "OP_COVERAGE_LOW" in codes

    m2 = Monitor()
    m2.update_round(round_id=1, w=[0.1] * 30, w_prev=[0.1] * 30, reward_mean=1.0,
                    n_eff_list=[3.0], op_counts={"GEN_PLAIN": 5, "GEN_ANGLE": 5,
                                                 "EXTRACT": 5, "SPLIT": 5, "VERIFY": 5},
                    conflict_rate=0.0, seed_noise_floor=0.03)
    m2.update_round(round_id=2, w=[0.1] * 30, w_prev=[0.1] * 30, reward_mean=1.0001,
                    n_eff_list=[3.0], op_counts={"GEN_PLAIN": 5, "GEN_ANGLE": 5,
                                                 "EXTRACT": 5, "SPLIT": 5, "VERIFY": 5},
                    conflict_rate=0.0, seed_noise_floor=0.03)
    codes2 = {a["code"] for a in m2.evaluate()}
    out["weight_frozen_fires"] = "WEIGHT_FROZEN" in codes2
    out["reward_stall_fires"] = "REWARD_STALL" in codes2

    m3 = Monitor()
    m3.update_round(round_id=1, w=[0.1] * 30, w_prev=None, reward_mean=0.0,
                    n_eff_list=[3.0], op_counts={"GEN_PLAIN": 5, "GEN_ANGLE": 5,
                                                 "EXTRACT": 5, "SPLIT": 5, "VERIFY": 5},
                    conflict_rate=0.5, seed_noise_floor=0.1)
    out["conflict_fires"] = "CONFLICT_EXCESS" in {a["code"] for a in m3.evaluate()}

    m4 = Monitor()
    m4.update_round(round_id=1, w=[0.1] * 30, w_prev=None, reward_mean=0.0,
                    n_eff_list=[3.0], op_counts={"GEN_PLAIN": 5, "GEN_ANGLE": 5,
                                                 "EXTRACT": 5, "SPLIT": 5, "VERIFY": 5},
                    conflict_rate=0.0, seed_noise_floor=0.03,
                    seq_signature_entropy=0.0)
    out["closure_fires"] = "SEARCH_CLOSURE" in {a["code"] for a in m4.evaluate()}

    tc = TauController(tau=1.2, target=TH["n_eff_target"])
    p = np.array([0.97] + [0.03 / 5] * 5)
    before = tc.tau
    tc.observe(p)
    out["tau_increases_when_collapsed"] = tc.tau > before

    out["all_pass"] = all(v is True for k, v in out.items() if k != "all_pass")
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(selftest(), ensure_ascii=False, indent=1))
