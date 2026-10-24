"""★ **状态层最小接口规格（层4 方向的可执行草案）**

> 出处：`creativity_lab/state_layer.py`（★ 工作包三的代码形态）
> ★ **零 API、零依赖、纯函数** ⇒ ⇒ **可离线测试、可直接被第四组取用**
>
> ## ★★ 它是什么
> ★ **外部指导助手那封信提的「保留—检验—换路」最小架构 + 子目标形成/撤销**的可执行化。
> ★ **第二组是层2（人为设计）路线，★ 本文件不改变第二组任何臂** ——
> ★ ★ 它是**给层4（状态驱动）用的接口规格**，★ 第二组只出规格与测试，★ 实现与读数归第四组。
>
> ## ★★ 三条设计红线
> ★ **① 状态是【可序列化的纯数据】** ⇒ ⇒ 单元测试不需要任何外部依赖
> ★ **② 更新规则是【纯函数】**（★ 旧状态 → 新状态，★ 不就地改）⇒ ⇒ 每次更新可回放、可 diff
> ★ **③ 失败调用【必须计入已用预算】且【不得静默归零】** ⇒ ⇒ 同「失败路径不许静默归零」通则
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

# ══════════════════════════════════════════════════════════════
# 状态 schema
# ══════════════════════════════════════════════════════════════

# ★ 动作空间（★ 对应外部那封信：独立探索 / 检查假设 / 连接两组信息 / 回退 / 切换方法 / 组织交付 / 停止）
ACTIONS = ("explore", "check_hypothesis", "connect", "rollback", "switch_method",
           "deliver", "stop")

# ★ 子目标状态
SUBGOAL_ACTIVE = "active"
SUBGOAL_REVOKED = "revoked"
SUBGOAL_DONE = "done"

# ★ 假设状态
HYP_OPEN = "open"
HYP_REFUTED = "refuted"
HYP_SUPPORTED = "supported"


@dataclass
class Hypothesis:
    """★ 检验中的假设（★ 第二组现有臂【没有】这个槽位 ⇒ ★ 这是真正的增量）"""
    hid: str
    statement: str
    status: str = HYP_OPEN
    evidence: List[Dict[str, Any]] = field(default_factory=list)   # ★ 证据（含反证）

    def add_evidence(self, ev: Dict[str, Any]) -> None:
        self.evidence.append(dict(ev))


@dataclass
class Subgoal:
    """★ 子目标（★ 由系统提出；★ 可依据反馈修订与撤销）"""
    sid: str
    statement: str
    status: str = SUBGOAL_ACTIVE
    proposed_by: str = "system"          # ★ 「系统提出」——★ 不是人写死的
    revision: int = 0
    revocation_reason: str = ""
    parent_sid: str = ""


@dataclass
class Attempt:
    """★ 已尝试方法（★ 记录尝试了什么、产生了什么新信息）"""
    method: str
    used: int = 0
    produced_new: bool = False
    dead_end: bool = False


@dataclass
class KeepPoint:
    """★ 保留项（★ 条件与关系）——★ 一个可回退到的检查点"""
    kp_id: str
    label: str
    note: str = ""


@dataclass
class State:
    """★ **完整状态**（★ 全部可 JSON 序列化 ⇒ ⇒ 单元测试零依赖）"""
    # ── 保留（条件与关系）──
    keep: List[KeepPoint] = field(default_factory=list)
    current_kp: str = ""                 # ★ 当前所在的检查点（★ 回退的目标）
    # ── 检验（假设与证据）──
    hypotheses: List[Hypothesis] = field(default_factory=list)
    # ── 换路（回退与切换方法）──
    attempts: List[Attempt] = field(default_factory=list)
    # ── 已尝试方法 / 进展记录 / 剩余预算 ──
    progress: List[str] = field(default_factory=list)
    budget_remaining: int = 0
    budget_used: int = 0
    # ── 子目标（★ 形成 / 修订 / 撤销）──
    subgoals: List[Subgoal] = field(default_factory=list)
    # ── 合法分歧（★ 不得压平成一个）──
    divergences: List[Dict[str, Any]] = field(default_factory=list)
    # ── 失败记账（★ 分母完整性）──
    n_failed_calls: int = 0
    n_calls_total: int = 0
    exhausted: bool = False
    stop_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def clone(self) -> "State":
        import copy
        return copy.deepcopy(self)


# ══════════════════════════════════════════════════════════════
# 更新规则（★ 全部是纯函数：★ 旧状态 → 新状态）
# ══════════════════════════════════════════════════════════════

def propose_subgoal(st: State, sid: str, statement: str,
                    parent_sid: str = "") -> State:
    """★ **子目标由系统提出**（★ 状态里新增一条 active 子目标；★ 父目标可指定）"""
    s = st.clone()
    s.subgoals.append(Subgoal(sid=sid, statement=statement, parent_sid=parent_sid))
    return s


def revoke_subgoal(st: State, sid: str, reason: str) -> State:
    """★ **子目标撤销**（★ 依据反馈撤销；★ ★ 撤销后仍保留在历史里可回查 ⇒ 不得物理删除）"""
    s = st.clone()
    for g in s.subgoals:
        if g.sid == sid and g.status == SUBGOAL_ACTIVE:
            g.status = SUBGOAL_REVOKED
            g.revocation_reason = reason
            s.progress.append("revoke_subgoal:%s:%s" % (sid, reason))
            return s
    return s


def revise_subgoal(st: State, sid: str, statement: str) -> State:
    """★ **子目标修订**（★ 依据反馈改写，但保留 revision 计数）"""
    s = st.clone()
    for g in s.subgoals:
        if g.sid == sid and g.status == SUBGOAL_ACTIVE:
            g.statement = statement
            g.revision += 1
            s.progress.append("revise_subgoal:%s" % sid)
            return s
    return s


def add_evidence(st: State, hid: str, ev: Dict[str, Any], refutes: bool = False) -> State:
    """★ **检验**：★ 追加证据；★ 若该证据【反证】假设 ⇒ 假设被推翻"""
    s = st.clone()
    for h in s.hypotheses:
        if h.hid == hid:
            h.add_evidence(ev)
            if refutes:
                h.status = HYP_REFUTED
                s.progress.append("refuted:%s" % hid)
            return s
    return s


def rollback(st: State, reason: str) -> State:
    """★ **反证触发回退**（★ 回到最近一个保留点；★ 换路）"""
    s = st.clone()
    s.progress.append("rollback:%s" % reason)
    s.keep.append(KeepPoint(kp_id="kp_%d" % (len(s.keep) + 1),
                             label="回退到 %s" % (s.current_kp or "起点"),
                             note=reason))
    s.current_kp = s.keep[-1].kp_id if s.keep else ""
    return s


def record_attempt(st: State, method: str, produced_new: bool) -> State:
    """★ **记录已尝试方法**（★ 连续 N 次无新信息 ⇒ 标记为【死路】⇒ 不可再选）"""
    s = st.clone()
    at = next((a for a in s.attempts if a.method == method), None)
    if at is None:
        at = Attempt(method=method)
        s.attempts.append(at)
    at.used += 1
    at.produced_new = produced_new
    # ★ 死路判定：★ 连续 3 次尝试都没有新信息 ⇒ 标记死路
    if not produced_new and at.used >= 3:
        at.dead_end = True
        s.progress.append("dead_end:%s" % method)
    return s


def record_call(st: State, ok: bool) -> State:
    """★ **预算与失败记账**（★ ★ 失败调用【必须计入已用预算】，★ 且【不得静默归零】）"""
    s = st.clone()
    s.n_calls_total += 1
    s.budget_used += 1
    s.budget_remaining = max(0, s.budget_remaining - 1)
    if not ok:
        s.n_failed_calls += 1          # ★ 失败【记进分母】，★ 不丢
    if s.budget_remaining <= 0:
        s.exhausted = True
        s.stop_reason = "budget_exhausted"
    return s


def preserve_divergence(st: State, d: Dict[str, Any]) -> State:
    """★ **合法分歧保留**（★ 不同 agent 的不同结论【不得压平成一个】）"""
    s = st.clone()
    s.divergences.append(dict(d))
    return s


# ══════════════════════════════════════════════════════════════
# 状态 → 动作（★ 决策规则；★ 人写死的固定规则，★ 不用 LLM）
# ══════════════════════════════════════════════════════════════

def choose_action(st: State) -> Tuple[str, str]:
    """★ **状态决定下一个动作**（★ 这才是层4 的核心：★ 动作由【当下状态】决定）

    ★ 优先级（★ 人写死，★ 与外部那封信的动作空间对应）：
    ★ ① 预算用尽 / 已 stop            ⇒ `stop`
    ★ ② 有被反证的假设               ⇒ `rollback`（★ 反证触发回退）
    ★ ③ 当前方法已判定死路           ⇒ `switch_method`
    ★ ④ 有 open 的假设                ⇒ `check_hypothesis`
    ★ ⑤ 有合法分歧                    ⇒ `connect`（★ 连接两组信息，★ ★ 但【不许压平】）
    ★ ⑥ 仍有预算                      ⇒ `explore`
    """
    if st.exhausted or st.stop_reason:
        return "stop", st.stop_reason or "stopped"
    if any(h.status == HYP_REFUTED for h in st.hypotheses):
        return "rollback", "counter_evidence"
    live = [a for a in st.attempts if a.dead_end]
    if live:
        return "switch_method", live[0].method
    if any(h.status == HYP_OPEN for h in st.hypotheses):
        return "check_hypothesis", next(h.hid for h in st.hypotheses if h.status == HYP_OPEN)
    if st.divergences:
        return "connect", "divergence"
    if st.budget_remaining > 0:
        return "explore", "budget_left"
    return "stop", "no_budget"
