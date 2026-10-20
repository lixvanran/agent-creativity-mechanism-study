# -*- coding: utf-8 -*-
"""路线 B v2：动作空间 / 候选集 / **状态缺口交互特征** / 尺度无关策略分布。

设计依据与理由见 `/workspace/lab/routes/B/DESIGN.md` §1–§2。
**本文件不修改 `creativity_lab/ops.py`**（仓库里正在跑的训练进程依赖它，
且 `check_ops_consistency.py` 要求两份 ops.py 逐字节一致）⇒ v2 以新模块并存。

────────────────────────────────────────────────────────────────────────
为什么需要 v2（可核对的诊断，不是推测）
────────────────────────────────────────────────────────────────────────
旧 `op_features(g, op, target, depth)`：
  * f[0..6]  = op one-hot（7 个 op）
  * f[7..13] = **target 相关**特征，**只在 target is not None 时才填**
  * 且 f[7..13] 与 op **完全无交互**（纯加性）

⇒ 后果一（死维）：`MERGE` 从未进入候选集 ⇒ f[5] 恒 0、w[5] 永不更新
  （快照 `w[5]=0.0` 印证）。
⇒ 后果二（状态不可分）：分数 s = w·f 是**加性**的 ⇒
  「target 处于什么状态」只给**所有带 target 的 op** 加同一项偏移
  ⇒ GEN（无 target）与 target 状态之间**没有交互**
  ⇒ 快照 §3 实测：4 个不同状态的 op 分数向量**完全相同**。
  ⇒ 策略学到的是「风格」（倾向哪个 op），不是「适应」（此刻该做什么）。

v2 的修法：**把"信息缺口"做成与 op 类别（class）交互的特征**。
交互项是唯一能让「状态」改变「偏好顺序」的形式（纯加性特征做不到）。
"""
from __future__ import annotations

import os
import sys
from typing import Iterable

import numpy as np

_REPO = os.environ.get("CMP8_REPO", "/workspace/lab/cmp8repo")
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from creativity_lab.ops import Graph, Node  # noqa: E402  （复用旧图结构，只读）

# ───────────────────────────────────────────────────────────── 动作空间
# v2 去掉 MERGE：它在旧实现里**从不可达**（候选集里从不出现）⇒ 去掉不损失任何
# 可达行为，但**回收一维权重预算**。其余 6 个 op 与旧实现同名同义。
OPS_V2 = ("GEN_PLAIN", "GEN_ANGLE", "EXTRACT", "SPLIT", "VERIFY", "STOP")

# op 类别：交互项按类别聚合，避免为每个 (op, 缺口) 组合单开一维 ⇒ 参数量受控
CLASSES = ("GENERATE", "PROCESS", "VERIFY", "STOP")
_OP_CLASS = {
    "GEN_PLAIN": "GENERATE", "GEN_ANGLE": "GENERATE",
    "EXTRACT": "PROCESS", "SPLIT": "PROCESS",
    "VERIFY": "VERIFY", "STOP": "STOP",
}

# 认知位置（角度）词表：**任务无关**的通用位置，不进入特征 ⇒ 策略不能对题面取巧
SLOTS = ("适用规则来源", "踩红线的做法", "办理流程与材料",
         "按情形分别处理", "时间与顺序要求", "例外与特殊情形")

# ───────────────────────────────────────────────────────────── 特征布局
# D = 30
#   [ 0.. 5] op one-hot                       (6)
#   [ 6.. 9] class × g1  no_claims_yet        (4)
#   [10..13] class × g2  unverified_ratio     (4)
#   [14..17] class × g3  uncovered_ratio      (4)   # 依据未覆盖
#   [18..21] class × g4  zero_supported       (4)
#   [22..25] class × t1  target_unverified    (4)
#   [26..29] class × t2  target_unmentioned   (4)
FEAT_DIM = 30
_IDX_G1, _IDX_G2, _IDX_G3, _IDX_G4 = 6, 10, 14, 18
_IDX_T1, _IDX_T2 = 22, 26

# 特征名（供 spec.yaml / 监控面板对齐）
FEATURE_NAMES = (
    [f"op[{o}]" for o in OPS_V2]
    + [f"{c}×g1_no_claims" for c in CLASSES]
    + [f"{c}×g2_unverified" for c in CLASSES]
    + [f"{c}×g3_uncovered" for c in CLASSES]
    + [f"{c}×g4_zero_supported" for c in CLASSES]
    + [f"{c}×t1_tgt_unverified" for c in CLASSES]
    + [f"{c}×t2_tgt_unmentioned" for c in CLASSES]
)
assert len(FEATURE_NAMES) == FEAT_DIM

# 缺口特征的归一化上限（计数饱和点）
SAT_UNVERIFIED, SAT_UNCOVERED = 4.0, 4.0


# ───────────────────────────────────────────────────────────── 图状态摘要
def state_gaps(g: Graph) -> dict:
    """**全局信息缺口**（只读图，不含题目/题集信息 ⇒ 任务无关）。"""
    claims = g.of_kind("CLAIM")
    n_unver = sum(1 for c in claims if c.verdict is None)
    n_uncov = sum(1 for c in claims if c.verdict == "未提及")
    n_sup = sum(1 for c in claims if c.verdict == "支持")
    n_con = sum(1 for c in claims if c.verdict == "矛盾")
    return dict(
        n_answers=len(g.of_kind("ANSWER")),
        n_claims=len(claims),
        n_unverified=n_unver,
        n_uncovered=n_uncov,
        n_supported=n_sup,
        n_contradicted=n_con,
        # 缺口向量
        g1_no_claims=1.0 if len(claims) == 0 else 0.0,
        g2_unverified=min(n_unver, SAT_UNVERIFIED) / SAT_UNVERIFIED,
        g3_uncovered=min(n_uncov, SAT_UNCOVERED) / SAT_UNCOVERED,
        g4_zero_supported=1.0 if (len(claims) > 0 and n_sup == 0) else 0.0,
    )


def target_flags(g: Graph, target: Node | None) -> tuple:
    """target 的 2 维状态标记（t1 未核验 / t2 依据未覆盖）。其余一律 0。"""
    if target is None or target.kind != "CLAIM":
        return 0.0, 0.0
    t1 = 1.0 if target.verdict is None else 0.0
    t2 = 1.0 if target.verdict == "未提及" else 0.0
    return t1, t2


# ───────────────────────────────────────────────────────────── 特征函数
def op_features_v2(g: Graph, op: str, target: Node | None) -> np.ndarray:
    """**v2 特征**：op 身份 + (op 类别 × 信息缺口) 交互 + (op 类别 × target 状态) 交互。

    与旧版的**关键差别**：缺口信息**只通过交互项**进入分数。
    纯加性的缺口项在 softmax 里是**公共常数**（对所有 op 同加）⇒ 对分布无影响；
    只有交互项才能让「状态」改变「偏好顺序」⇒ 这正是 v2 要修的东西。
    """
    f = np.zeros(FEAT_DIM, dtype=float)
    f[OPS_V2.index(op)] = 1.0
    cls = _OP_CLASS[op]
    ci = CLASSES.index(cls)
    gaps = state_gaps(g)
    f[_IDX_G1 + ci] = gaps["g1_no_claims"]
    f[_IDX_G2 + ci] = gaps["g2_unverified"]
    f[_IDX_G3 + ci] = gaps["g3_uncovered"]
    f[_IDX_G4 + ci] = gaps["g4_zero_supported"]
    t1, t2 = target_flags(g, target)
    f[_IDX_T1 + ci] = t1
    f[_IDX_T2 + ci] = t2
    return f


# ───────────────────────────────────────────────────────────── 候选集
def candidates(g: Graph, n_verify_done: int = 0) -> list:
    """**候选集规则**（v2）。

    ── 分离原则（本设计的一条硬性分类）──────────────────────────────
    **人定的只有"合法性过滤"**（不合法 ⇒ 根本不该被考虑）：
      ❶ STOP 至少要有一个 ANSWER 节点（否则"交付"是空动作）
      ❷ VERIFY 只对**未核验**的断言开放（核验一条已核验过的断言 = 无信息增益的重复调用）
      ❸ SPLIT 只对 verdict ∈ {None, 未提及} 的断言开放
         （已确认"矛盾"的断言，拆分没有意义；"依据未覆盖"的断言拆分才可能挖出被覆盖的子项）
    **架构选择（要学的）**：何时生成、生成几次、抽不抽断言、先拆还是先核验、
      核验多少条、什么时候停。⇒ 这些**全部**由学习到的交互特征决定。

    ⚠️ **旧版把状态依赖写死在候选规则里**（SPLIT 只对未提及/未核验开放），
       而旧特征空间**没有任何 op×target 交互** ⇒ 旧系统的"状态适应"**全部**来自
       人写的候选规则，权重只学到一个静态偏好顺序。
       ⇒ v2 把状态依赖搬进**可学习的交叉项**（见 op_features_v2）。

    ⚠️ 目标选择规则与内容无关（按插入顺序取最早）⇒ 不会变成 best-of-N。
    """
    out = [("GEN_PLAIN", None), ("GEN_ANGLE", None)]
    ans = g.of_kind("ANSWER")
    if ans:
        out.append(("EXTRACT", ans[-1]))
    unver = [n for n in g.of_kind("CLAIM") if n.verdict is None]
    for n in unver[:2]:
        out.append(("VERIFY", n))
    for n in g.of_kind("CLAIM"):
        if n.verdict in (None, "未提及"):
            out.append(("SPLIT", n))
            break
    if ans:                       # ❶ 至少要有一个答案节点才允许 STOP
        out.append(("STOP", None))
    return out


# ───────────────────────────────────────────────────────────── 策略分布
def policy_probs(s, tau: float = 1.2) -> np.ndarray:
    """**尺度无关**的 softmax（沿用旧版已验证的修法：先标准化再除 τ）。

    · 标准化 ⇒ τ 表示**相对**锐度，与 ‖w‖ 无关 ⇒ 权重放大不会导致塌缩
    · 行为分布与更新分布**共用这一份函数** ⇒ on-policy 成立
    """
    s = np.asarray(s, dtype=float)
    if s.size <= 1:
        return np.ones(max(s.size, 1)) / max(s.size, 1)
    sd = float(s.std())
    z = (s - s.mean()) / (sd + 1e-8) / max(tau, 1e-6)
    z = z - z.max()
    p = np.exp(z)
    return p / p.sum()


def n_eff(p) -> float:
    """策略健康度：1/Σp²。1.0–1.3 塌缩 / 3–5 健康 / ≈|A| 近乎均匀。"""
    p = np.asarray(p, dtype=float)
    return float(1.0 / max((p ** 2).sum(), 1e-12))


def norm_entropy(p) -> float:
    """归一化熵 H(p)/log|A| ∈ [0,1]。"""
    p = np.asarray(p, dtype=float)
    p = p[p > 0]
    if p.size <= 1:
        return 0.0
    h = float(-(p * np.log(p)).sum())
    return h / float(np.log(len(p)))


def score_all(g: Graph, w: np.ndarray, n_verify_done: int = 0):
    """返回 (cands, 分数数组, 特征矩阵)。**分数与特征严格同序**（旧版已修的坑）。"""
    cands = candidates(g, n_verify_done)
    if not cands:
        return [], np.zeros(0), np.zeros((0, FEAT_DIM))
    F = np.stack([op_features_v2(g, op, tgt) for op, tgt in cands])
    s = F @ np.asarray(w, dtype=float)
    return cands, s, F


def pick(cands, s, F, rng, tau: float = 1.2, mode: str = "sample"):
    """按策略分布取一个候选。

    mode:
      * "sample" —— 按 π 采样（训练用；on-policy）
      * "argmax_first" —— 分数相同时取**候选表里第一个**（确定性；`w=0` 对照臂用）
      * "uniform" —— 均匀随机（随机策略对照臂用）
    """
    if not cands:
        return None
    if mode == "uniform":
        return int(rng.randrange(len(cands)))
    p = policy_probs(s, tau)
    if mode == "argmax_first":
        best = int(np.argmax(s))
        return best
    return int(rng.choices(range(len(cands)), weights=list(p))[0])


# ───────────────────────────────────────────────────────────── 工具
def flatten(nested: Iterable) -> list:
    out = []
    for x in nested:
        if isinstance(x, (list, tuple)):
            out.extend(flatten(x))
        else:
            out.append(x)
    return out
