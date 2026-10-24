#!/usr/bin/env python3
"""第四组 · v6 Stage-1 机制层。

**复用 v5，不重造**：状态/候选/声明解析/打分/选择全部 import v5；
新增的只有三样：
  ① **同一 gaps 上的两个状态版本**（无代价 / 有代价）⇒ ⇒ 候选池可四格共享；
  ② **家族最优·非状态化选择器**（三组 `gates/base.py`：EscapeGate / LexicalSpreadGate / length）；
  ③ **代价进入选择器的机制门**（排序改变率 / 目标集变化率）的支撑读数。

⚠️ 设计规格见 `STAGE1_SPEC.md`（事前写死，跑批前）。
"""
from __future__ import annotations

import copy
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

# ─────────────────────────────────────────────────────────────────────
# ★★ G0-1：环境变量当隐式配置 ⇒ 必须**先钉后 import**。
#    `creativity_lab/client.py:14` 的 BASE 是**模块级常量**（import 时求值），
#    所以只要环境里 OPENROUTER_BASE_URL 被别的组设成 openrouter.ai，
#    embedding 就会打到 OpenRouter（无 /embeddings 端点）⇒ 两个 Gate 直接不可用。
#    ⇒ 这里强制钉住，并**把原值记下来**供落盘（事后可核"跑的时候是哪个"）。
# ─────────────────────────────────────────────────────────────────────
G4_ENV_ORIG = {
    "OPENROUTER_BASE_URL": os.environ.get("OPENROUTER_BASE_URL"),
    "MINIMAX_SUBSCRIPTION_KEY_set": bool(os.environ.get("MINIMAX_SUBSCRIPTION_KEY")),
}
os.environ["OPENROUTER_BASE_URL"] = "https://api.minimaxi.com/v1"

G4REF = os.environ.get("G4_REF_DIR", "/workspace/g4_ref")
if G4REF not in sys.path:
    sys.path.insert(0, G4REF)

from creativity_lab.gates.base import (          # noqa: E402  ← 三组的，md5 400d27894a7716085c594ef5e603065b
    EscapeGate, LexicalSpreadGate, Select,
)
from creativity_lab.client import LLM as _LLM, cosine as _cosine   # noqa: E402

import workflow_arch5 as WA5                     # noqa: E402  ← v5 复用
from workflow_arch5 import State5, Candidate5    # noqa: E402

State5.from_dict = State5.from_dict  # 明确暴露

K = 3
CAND_LO, CAND_HI = 600, 900
DECISION_DEPTHS = ("深入展开", "点到为止", "放弃")


# ─────────────────────────────────────────────────────────────────────
# ① 状态：同一 gaps 上的两个版本（无代价 / 有代价）
# ─────────────────────────────────────────────────────────────────────
def _dec_depth(d: dict) -> str:
    return str(d.get("depth") or "").strip()


def state_variants6(st: State5) -> Tuple[State5, State5, dict]:
    """从**同一个**状态构造两个版本：

    - ``st_base``  = **无代价**：decisions 里**剔除**任何 depth=="放弃" 的条目。
    - ``st_quota`` = **有代价**：decisions 里**必须**含 ≥1 个 depth=="放弃"；
      若模型没给出 ⇒ **代码补一个**（选 priority 最低者）并标 ``quota_forced=True``。

    ★ 两者的 ``gaps`` **完全相同** ⇒ ⇒ **候选提示（blind 模式只给编号）完全相同**
      ⇒ ⇒ **四格共享同一批候选** ⇒ ⇒ "代价改变了排序"才可归因（STAGE1_SPEC §1.1）。
    """
    base = copy.deepcopy(st)
    quota = copy.deepcopy(st)
    meta = {"n_decisions": len(st.decisions or []),
            "natural_quota": 0, "dropped_quota": 0, "quota_forced": False}

    # ---- 无代价：剔除"放弃"
    kept = []
    for d in (st.decisions or []):
        if _dec_depth(d) == "放弃":
            meta["dropped_quota"] += 1
        else:
            kept.append(d)
    base.decisions = kept

    # ---- 有代价：保留 + 必要时补一个
    qd = list(st.decisions or [])
    n_nat = sum(1 for d in qd if _dec_depth(d) == "放弃")
    meta["natural_quota"] = n_nat
    if n_nat == 0:
        # 补一个：选 priority 最低者（priority 越小越不重要 ⇒ 越该被放弃）
        cands = [d for d in qd if _dec_depth(d) != "放弃"] or list(qd)
        if cands:
            def _prio(d):
                try:
                    return int(d.get("priority") or 99)
                except (TypeError, ValueError):
                    return 99
            tgt = sorted(cands, key=lambda d: (-_prio(d), int(d.get("gap_index") or 0)))[-1]
            nd = dict(tgt)
            nd["depth"] = "放弃"
            nd["quota_forced"] = True
            qd = qd + [nd]
            meta["quota_forced"] = True
    quota.decisions = qd
    return base, quota, meta


def target_set6(st: State5) -> dict:
    """状态化打分器的**真实目标集**（★ 必须与 `score_state_alignment5` 同口径）。

    ★ 修正记录（2026-10-24 冒烟后、正式批前）：
      v6 初版把"目标集"定义成"所有决策涉及的编号"⇒ ⇒ 补配额（把某个 gap 的
      depth 改成"放弃"）**不改变**那个集合 ⇒ ⇒ 误报"目标集没变、代价没进状态"。
      而 `score_state_alignment5` 实际用的是 **deep_set / drop_set 两项**
      （写透目标 / 放弃目标）⇒ ⇒ 补配额**确实**改变目标（实测 align 0.3333 → 0.6667）。
      ⇒ ⇒ 本函数改为返回两项的真实集合。
    """
    deep, drop = set(), set()
    for d in (st.decisions or []):
        gi = int(d.get("gap_index") or 0)
        if gi <= 0:
            continue
        if str(d.get("depth") or "").strip() == "放弃":
            drop.add(gi)
        else:
            deep.add(gi)
    return {"deep": sorted(deep), "drop": sorted(drop)}


# ─────────────────────────────────────────────────────────────────────
# ② 家族最优·非状态化选择器（三组的 Gate，零自创算法）
# ─────────────────────────────────────────────────────────────────────
class FamilyScorers6:
    """家族打分器集合：escape / spread / length（**都不读状态**）。

    - ``escape``：``EscapeGate``（三组）—— 候选离**同题多次直接采样参照系**的距离；
      参照系由**调用方**传入（Gate 内部无题目内容）✅
    - ``spread``：``LexicalSpreadGate``（三组）—— 批内两两距离中位数
    - ``length``：字数（v5 的 ``score_generic5`` 同源口径，但这里取**纯长度**，
      并单独报它与长度的相关性 ⇒ 若它主导选择，对照端即退化为"选最长的"）

    ⚠️ 每个打分器都会记录：分数、方差（>0 才算活的）、与长度的 Pearson 相关。
    """

    def __init__(self, ref_texts=None, embedder=None):
        # ★★ 三组 `EscapeGate.__init__(ref_vecs)` 的**参数名有误导**：
        #    它的 `_one(text, ref)` 走的是 `_embed([text] + list(ref))`
        #    ⇒ ⇒ **ref 里放的是"文本"，不是向量**（向量会被当文本送去 embed ⇒
        #    报 TypeError: unhashable type: 'list'）。
        #    ⇒ 这是"照抄 IO 前必须读实现"的又一例（2026-10-24 冒烟抓到）。
        self.ref_texts = list(ref_texts or [])
        self._embedder = embedder
        self.diag: Dict[str, dict] = {}

    # ---- embedding（走 MiniMax 通道，**不占已耗尽的 OpenRouter 额度**）
    def embed(self, texts: List[str]) -> List[List[float]]:
        if self._embedder is None:
            self._embedder = _LLM()
        return self._embedder.embed(list(texts))

    def _escape(self, cands: Sequence[Candidate5]) -> List[float]:
        if not self.ref_texts:
            return []
        g = EscapeGate(self.ref_texts)
        return g.score([c.text or "" for c in cands])

    def _spread(self, cands: Sequence[Candidate5]) -> List[float]:
        g = LexicalSpreadGate()
        return g.score([c.text or "" for c in cands])

    def _length(self, cands: Sequence[Candidate5]) -> List[float]:
        """★ **批内相对长度**（不是 `min(1.0, len/900)`）。

        ⚠️ 修正记录（2026-10-24 冒烟后、正式批前）：初版用 `min(1.0, len/900)`
        ⇒ ⇒ 候选全部 ≥900 字 ⇒ ⇒ **分数全部封顶到 1.0** ⇒ ⇒ **零区分力**
        （G0-4 实测 min=max=1.0、var=0）⇒ ⇒ **这不是"仪器坏了"，是口径本身没有区分力**
        ⇒ ⇒ 而"家族最优"若只有一把瞎尺子 ⇒ ⇒ **对照端退化**
        ⇒ ⇒ **同一个坑 v5 的 `score_generic5` 也踩了**（0.7 权重给 length、同样封顶）
        ⇒ ⇒ ★ **这意味着 v5 的 gap +0.0741 可能是"通用尺子瞎"造成的假正效应**。
        ⇒ ⇒ 修法：改用**批内相对长度**（len_i / max_len）⇒ 有区分力。
        """
        lens = [len((c.text or "").strip()) for c in cands]
        mx = max(lens) if lens else 0
        return [(l / mx if mx else 0.0) for l in lens]

    def score_all(self, cands: Sequence[Candidate5]) -> Dict[str, List[float]]:
        """返回 {gate_name: [每个候选的分数]}；失败的 gate 返回空列表（**显式，不静默**）。"""
        res: Dict[str, List[float]] = {}
        for name, fn in (("escape", self._escape), ("spread", self._spread),
                         ("length", self._length)):
            try:
                res[name] = fn(cands)
            except Exception as e:
                res[name] = []
                self.diag[name] = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
                continue
            sc = [x for x in res[name] if x is not None]
            self.diag[name] = {
                "ok": bool(sc),
                "n": len(sc),
                "var": round(_var(sc), 6) if len(sc) > 1 else 0.0,
                "min": round(min(sc), 4) if sc else None,
                "max": round(max(sc), 4) if sc else None,
                # ★ 区分力：批内极差（max-min）⇒ 尺子能不能区分同批候选
                "spread_range": round(max(sc) - min(sc), 6) if sc else None,
                "constant": (len(sc) > 1 and _var(sc) < 1e-12),
            }
        return res


def _rank_by_score6(scores: Sequence[float]) -> List[int]:
    """★ 自己算完整排序（**不要用 Select(mode="greedy")(scores, k=len(scores))**）。

    ⚠️★ BUG 记录（2026-10-24 13:5x 抓到）：三组 `Select.__call__` 里有
        `if k >= n: return list(range(n))` ⇒ ⇒ **k == n 时直接返回原始顺序**，
        而我为了拿"完整排序"正好传了 k=n ⇒ ⇒ ⇒ **rank 永远是 [1,2,3]**（原序）
        ⇒ ⇒ **"排序改变率 = 0" 是实现假象，不是数据事实**（T07-2 的 B=[0.3333,1.0,0.5]
        本应排成 [2,1,3]，却被记成 [1,2,3]）。
    ⇒ ⇒ 正确做法：按 Select.greedy 的同一逻辑排序（`-scores[i]`，并列保持原序 ⇒ 稳定）。
    """
    n = len(scores)
    return sorted(range(n), key=lambda i: -float(scores[i]))


def _var(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / (n - 1)


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def family_pick6(cands: Sequence[Candidate5], fam: FamilyScorers6,
                 align_scorer, sel: Optional[Select] = None) -> dict:
    """**家族最优**：在家族（escape / spread / length）里选 align 最高的那一个，
    用它选候选。

    ★ 与 v5 的差别：v5 的对照端是**一个**弱基线（``score_generic5``，与长度耦合 r=0.747）；
      这里改为**逐个 Gate 各选一次**，再按 align 取最好的 ⇒ ⇒ **"家族最优"是量出来的，不是指定的**。
    ★ 选择一律 ``Select(mode="greedy")``（确定性、可复现；G0-3）。
    """
    sel = sel or Select(mode="greedy")
    ok = [c for c in cands if not c.error and (c.text or "").strip()]
    if not ok:
        return {"gate": None, "picked": None, "per_gate": {}, "reason": "no_valid_candidate"}
    scores = fam.score_all(ok)
    per_gate = {}
    best = {"gate": None, "align": -1.0, "idx": None}
    best_rank = []
    for name, sc in scores.items():
        if not sc:
            per_gate[name] = {"n": len(sc), "picked": None, "align": None}
            continue
        # ★ 完整排序（**自己算**，见 _rank_by_score6 的 BUG 记录）
        full = _rank_by_score6(list(sc))
        idxs = full[:1]
        if not idxs:
            continue
        c = ok[idxs[0]]
        al = align_scorer(c)
        al = 0.0 if al is None else al
        per_gate[name] = {"n": len(sc), "picked": c.idx, "align": round(al, 4),
                          "rank": [ok[i].idx for i in full]}
        if al > best["align"]:
            best = {"gate": name, "align": al, "idx": c.idx,
                    "rank": [ok[i].idx for i in full]}
    if best["idx"] is None:
        return {"gate": None, "picked": None, "per_gate": per_gate, "reason": "no_score"}
    picked = next(c for c in ok if c.idx == best["idx"])
    # 长度相关性（主会话硬要求 2：每个打分器都要报与长度的相关性）
    lens = [len((c.text or "").strip()) for c in ok]
    for name, sc in scores.items():
        if sc and len(sc) == len(lens):
            r = _pearson([float(x) for x in sc], [float(x) for x in lens])
            fam.diag.setdefault(name, {})["len_corr"] = r
            fam.diag[name]["len_corr"] = r
    return {"gate": best["gate"], "align": round(best["align"], 4), "picked": picked,
            "picked_idx": picked.idx, "per_gate": per_gate, "rank": best.get("rank") or [],
            "diag": {k: dict(v) for k, v in fam.diag.items()}}


def state_pick6(cands: Sequence[Candidate5], st: State5,
                sel: Optional[Select] = None) -> dict:
    """**状态化选择器**：state-align（候选自主声明的编号 vs 状态决策编号）。"""
    sel = sel or Select(mode="greedy")
    ok = [c for c in cands if not c.error and (c.text or "").strip()]
    if not ok:
        return {"picked": None, "picked_idx": None, "reason": "no_valid_candidate"}
    # ★ NO_SILENT_ZERO_FIXED：`score_state_alignment5` 返回 None（候选无有效声明 /
    #   状态两格皆空）时**不得当 0**（v5 铁律：打不出分 ≠ 0 分）⇒ ⇒ **排除该候选**。
    #   ⚠️ 旧实现写成 `0.0 if v is None else v` ⇒ ⇒ **静默归零**（2026-10-24 T07-3 实测
    #   scores=[0.0,0.0,0.0] ⇒ 其实是"三个候选都打不出分"）。
    sc, idx_ok = [], []
    for c in ok:
        v = WA5.score_state_alignment5(c, st)
        if v is None:
            sc.append(None)
            continue
        sc.append(float(v))
        idx_ok.append(c)
    if not idx_ok:
        return {"picked": None, "picked_idx": None, "reason": "no_scorable_candidate",
                "scores": None, "rank": []}
    full = _rank_by_score6([x for x in sc if x is not None])
    idxs = full[:1]
    if not idxs:
        return {"picked": None, "picked_idx": None, "reason": "no_score"}
    c = idx_ok[idxs[0]]
    pos = [j for j, x in enumerate(idx_ok) if x.idx == c.idx][0]
    return {"picked": c, "picked_idx": c.idx, "align": round(sc[pos], 4),
            "scores": [None if x is None else round(x, 4) for x in sc],
            "rank": [idx_ok[i].idx for i in full],
            "n_scorable": len(idx_ok), "n_candidates": len(ok)}


# ─────────────────────────────────────────────────────────────────────
# ③ 机制读数：排序改变率 / 目标集变化率
# ─────────────────────────────────────────────────────────────────────
def selection_change(a_idx: Optional[int], b_idx: Optional[int]) -> Optional[bool]:
    """top-1 是否改变（保留作辅助读数）。

    ⚠️ ★ **已知缺陷**：并列时 `Select(greedy)` 永远取 idx 最小的 ⇒ ⇒ **top-1 指标对
    并列不敏感，会系统性低估"代价改变了排序"**（2026-10-24 冒烟实测：
    D 档 align = [0.6667, 0.6667, 0.1667] ⇒ 候选 1/2 并列第一 ⇒ top-1 恒为 1）。
    ⇒ ⇒ **主读数改用 `rank_change6`（完整排序）**，本函数只作辅助。
    """
    if a_idx is None or b_idx is None:
        return None
    return bool(a_idx != b_idx)


def rank_change6(rank_a: Sequence[int], rank_b: Sequence[int]) -> dict:
    """★ 主读数：**完整排序**是否因代价而变。

    返回：
      ``changed``     —— 排序序列是否不同（哪怕只是次序交换）
      ``kendall_tau`` —— 两个排序的秩相关（1 = 完全同序，0 = 无关，-1 = 反序）
      ``top1_set_same`` —— top-1 的**候选集合**是否相同（并列时用集合而非单点）
      ``n``           —— 可比的候选数

    ⚠️ 理由：top-1 单点指标在并列时恒定 ⇒ 会把"代价把候选从最后提到并列第一"
      这种**真实排序变化**读成"没变"。
    """
    a = [int(x) for x in (rank_a or [])]
    b = [int(x) for x in (rank_b or [])]
    common = [x for x in a if x in b]
    if len(common) < 2:
        return {"changed": None, "kendall_tau": None, "top1_set_same": None, "n": len(common)}
    pos_b = {x: i for i, x in enumerate(b)}
    conc = disc = 0
    for i in range(len(common)):
        for j in range(i + 1, len(common)):
            if pos_b[common[i]] < pos_b[common[j]]:
                conc += 1
            else:
                disc += 1
    tot = conc + disc
    tau = (conc - disc) / tot if tot else None
    ta = set(a[:1])
    tb = set(b[:1])
    top_a = {x for x in a if x in tb} if len(b) > 1 else ta
    top_b = {x for x in b if x in ta} if len(a) > 1 else tb
    return {"changed": bool(a != b), "kendall_tau": round(tau, 4) if tau is not None else None,
            "top1_set_same": bool(top_a == top_b), "n": len(common)}


# ─────────────────────────────────────────────────────────────────────
# 自检
# ─────────────────────────────────────────────────────────────────────
_TOT = [0]


def _selfcheck(verbose=True) -> int:
    res = []

    def chk(name, cond, detail=""):
        res.append((bool(cond), name, detail))

    # 1) 状态变体：gaps 相同、decisions 不同
    st = State5(stance="S", keeps=["k1"], gaps=[
        {"index": 1, "text": "g1", "entities": ["甲"], "priority": 1},
        {"index": 2, "text": "g2", "entities": ["乙"], "priority": 2},
        {"index": 3, "text": "g3", "entities": ["丙"], "priority": 3},
    ], decisions=[
        {"gap_index": 1, "depth": "深入展开", "priority": 1},
        {"gap_index": 2, "depth": "点到为止", "priority": 2},
    ])
    base, quota, meta = state_variants6(st)
    chk("无代价：剔除放弃后无 depth==放弃",
        all(d.get("depth") != "放弃" for d in base.decisions))
    chk("有代价：补足到 ≥1 个放弃",
        sum(1 for d in quota.decisions if d.get("depth") == "放弃") >= 1, str(meta))
    chk("补配额时标 quota_forced", meta["quota_forced"] is True)
    chk("两版 gaps 完全相同", base.gaps == quota.gaps and base.gaps == st.gaps)
    chk("两版 stance/keeps 相同", base.stance == quota.stance and base.keeps == quota.keeps)
    tb, tq = target_set6(base), target_set6(quota)
    chk("★ 目标集（deep/drop）随代价改变", tb != tq,
        "base=%s quota=%s" % (tb, tq))
    chk("无代价版 drop 为空", tb["drop"] == [])
    chk("有代价版 drop 非空", len(tq["drop"]) >= 1, str(tq["drop"]))
    chk("有代价版 deep 变小", len(tq["deep"]) <= len(tb["deep"]),
        "%d vs %d" % (len(tq["deep"]), len(tb["deep"])))

    # 2) 自然产生放弃时：不强制补、且 base 剔除它
    st2 = State5(stance="S", keeps=[], gaps=[
        {"index": 1, "text": "g1", "entities": [], "priority": 1},
    ], decisions=[{"gap_index": 1, "depth": "放弃", "priority": 1}])
    b2, q2, m2 = state_variants6(st2)
    chk("自然放弃：base 剔除", len(b2.decisions) == 0)
    chk("自然放弃：quota 保留", len(q2.decisions) == 1)
    chk("自然放弃：不标 forced", m2["quota_forced"] is False and m2["natural_quota"] == 1)

    # 3) 候选池共享：blind 提示在两版下完全相同
    p1 = WA5.render_candidate_prompt5(base, CAND_LO, CAND_HI, blind=True, cand_no=1, k=K)
    p2 = WA5.render_candidate_prompt5(quota, CAND_LO, CAND_HI, blind=True, cand_no=1, k=K)
    chk("★ blind 提示在两版下逐字相同 ⇒ 候选池可共享", p1 == p2)

    # 4) 非 blind 提示必须给状态内容（否则无法做"看得见状态"的对照）
    pn = WA5.render_candidate_prompt5(quota, CAND_LO, CAND_HI, blind=False, cand_no=1, k=K)
    chk("非 blind 提示含缺口内容（对照臂需要）", "（内容未公开）" not in pn)

    # 5) 家族打分器诊断：常量检测
    fam = FamilyScorers6(ref_texts=None)
    cs = [Candidate5(idx=1, text="甲乙丙" * 10), Candidate5(idx=2, text="丁戊" * 3)]
    sc = fam.score_all(cs)
    chk("无参照系时 escape 返回空（显式失败，不静默）", sc.get("escape") == [])
    chk("escape 失败被记录", fam.diag.get("escape", {}).get("ok") is False)
    chk("length 有分数且非常量", fam.diag.get("length", {}).get("constant") is False)
    chk("★ length 不封顶（批内相对）", (fam.diag.get("length", {}).get("max") or 0) <= 1.0)
    chk("★ 区分力读数存在（spread_range）",
        "spread_range" in (fam.diag.get("length") or {}))
    chk("spread 存在（批内距离）", "spread" in sc and len(sc["spread"]) == 2)

    # 6) 状态化选择器：打不出分的候选被排除（不当 0）
    cbad = Candidate5(idx=1, text="x", decl_parsed=False, error="no_declaration")
    cgood = Candidate5(idx=2, text="甲乙", decl_write={1}, decl_drop=set(), decl_parsed=True)
    sp = state_pick6([cbad, cgood], base, Select(mode="greedy"))
    chk("状态化选择器跳过坏候选", sp.get("picked_idx") == 2, str(sp.get("picked_idx")))

    # 6b) ★ None 不当 0（★ 静默归零的防线）
    # ★ 用【无 error 但 decl_parsed=False】的候选 ⇒ 才能走到"打不出分"这一步
    c_none = Candidate5(idx=1, text="x", decl_parsed=False)
    sp_none = state_pick6([c_none], base, Select(mode="greedy"))
    chk("★ align 打不出 ⇒ 排除候选而非当 0",
        sp_none.get("picked_idx") is None
        and sp_none.get("reason") in ("no_scorable_candidate", "no_valid_candidate"),
        str(sp_none.get("reason")))

    # 7) 排序改变率：None 不当作 False
    chk("selection_change(None,1) 是 None", selection_change(None, 1) is None)
    chk("selection_change(1,2) 是 True", selection_change(1, 2) is True)
    chk("selection_change(1,1) 是 False", selection_change(1, 1) is False)

    # 8) ★ 完整排序读数（top-1 对并列不敏感 ⇒ 主读数用 rank）
    chk("rank_change6：同序 ⇒ changed=False",
        rank_change6([1, 2, 3], [1, 2, 3])["changed"] is False)
    chk("rank_change6：换序 ⇒ changed=True",
        rank_change6([1, 2, 3], [3, 1, 2])["changed"] is True)
    chk("rank_change6：τ=1 时 top1_set_same=True",
        rank_change6([1, 2, 3], [1, 2, 3])["top1_set_same"] is True)
    chk("rank_change6：候选不足 ⇒ None（不当作 False）",
        rank_change6([1], [2])["changed"] is None)

    # 8b) ★ rank 计算（**曾经踩过的坑**：Select(k=n) 返回原序）
    chk("rank_by_score6 正确（按分数降序）",
        _rank_by_score6([0.3333, 1.0, 0.5]) == [1, 2, 0],
        str(_rank_by_score6([0.3333, 1.0, 0.5])))
    chk("rank_by_score6 并列时保持原序",
        _rank_by_score6([0.5, 0.5, 0.2]) == [0, 1, 2])
    chk("★ Select(k=n) 会返回原序（故不可用于取完整排序）",
        Select(mode="greedy")([0.3333, 1.0, 0.5], k=3) == [0, 1, 2],
        "这正是 bug 的来源")

    # 9) Select 只用 greedy（确定性）
    sel = Select(mode="greedy")
    chk("greedy 选最大", sel([0.1, 0.9, 0.5], k=1) == [1])

    if verbose:
        ok = 0
        for good, name, detail in res:
            print("  %s %s%s" % ("✔" if good else "✘", name,
                                 ("  — " + detail) if detail else ""))
            ok += good
        print("  ---- %d/%d" % (ok, len(res)))
    _TOT[0] = len(res)
    return sum(1 for g, _, _ in res if g)


if __name__ == "__main__":
    import sys as _s
    n = _selfcheck(verbose=True)
    print("  （共 %d 项）" % _TOT[0])
    _s.exit(0 if n == _TOT[0] else 1)
