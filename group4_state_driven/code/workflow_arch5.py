#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · v5：编号化取舍声明 + 结构化绑定（解 v4 的两难）。

★★★ v4 的两难与 v5 的破法 ★★★
v4：打分对象 = 「候选正文命中了状态实体」
  · 候选**看到**缺口内容 ⇒ 照做就能命中 ⇒ **打分接近恒真**
  · 候选**看不到**缺口内容 ⇒ 产出没有状态指纹 ⇒ **打分无处发力**

v5：**打分对象从"内容"换成"候选的自主声明"**
  · 候选看到**缺口内容（编号 1..N）** ⇒ 状态真的影响候选
  · 候选**绝不知道状态的决定**（哪个该写透、哪个该放弃）⇒ 声明是**自主判断** ⇒ **非恒真**
  · 声明用**编号**（离散结构）⇒ 状态化打分 = 「声明的编号集」vs「状态决策的编号集」
    ⇒ **零措辞依赖**（第四组已确立的纪律：绑定必须结构化）
  · 再核验**兑现**：声明写透 k ⇒ 正文是否真写了 gap_k 的实体

⚠️ 本模块**不联网、不调模型**，纯判据与状态定义，可独立自检。
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

# ---------------------------------------------------------------- 状态
@dataclass
class State5:
    stance: str = ""
    keeps: List[str] = field(default_factory=list)
    # gaps: [{"index": 1, "text": "...", "entities": [...]}]
    gaps: List[dict] = field(default_factory=list)
    # decisions: [{"gap_index": 1, "depth": "深入展开"|"点到为止"|"放弃", "priority": 1..3, "note": "..."}]
    decisions: List[dict] = field(default_factory=list)

    # ---- 派生视图（代码封闭，不交给模型决定） ----
    def gap_map(self) -> Dict[int, dict]:
        return {int(g.get("index") or 0): g for g in self.gaps}

    def deep_set(self) -> Set[int]:
        """状态决定「写透」的缺口编号集。"""
        return {int(d.get("gap_index") or 0) for d in self.decisions
                if d.get("depth") == "深入展开"}

    def drop_set(self) -> Set[int]:
        """状态决定「放弃」的缺口编号集。"""
        return {int(d.get("gap_index") or 0) for d in self.decisions
                if d.get("depth") == "放弃"}

    def all_indices(self) -> Set[int]:
        return {int(g.get("index") or 0) for g in self.gaps if g.get("index")}

    def entities_of(self, idx: int) -> List[str]:
        g = self.gap_map().get(int(idx)) or {}
        return list(g.get("entities") or [])

    def to_dict(self) -> dict:
        return {"stance": self.stance, "keeps": self.keeps, "gaps": self.gaps,
                "decisions": self.decisions}

    @staticmethod
    def from_dict(d: dict) -> "State5":
        d = d or {}
        return State5(stance=d.get("stance", ""), keeps=list(d.get("keeps") or []),
                       gaps=list(d.get("gaps") or []),
                       decisions=list(d.get("decisions") or []))


# ---------------------------------------------------------------- 候选
@dataclass
class Candidate5:
    idx: int
    text: str = ""
    # 自主声明（解析结果）
    decl_write: Set[int] = field(default_factory=set)
    decl_drop: Set[int] = field(default_factory=set)
    decl_raw: str = ""
    decl_parsed: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {"idx": self.idx, "text": self.text,
                "decl_write": sorted(self.decl_write), "decl_drop": sorted(self.decl_drop),
                "decl_raw": self.decl_raw, "decl_parsed": self.decl_parsed,
                "error": self.error}


# ---------------------------------------------------------------- 声明解析
# 约定格式（唯一一行，出现在正文**之前**）：
#   【取舍】写透：2,4；放弃：1,3
# ⚠️ 解析必须**容错但显式**：解析不了 ⇒ decl_parsed=False（不静默当成"没声明"）
DECL_RE = re.compile(
    r"【\s*取舍\s*】\s*写透\s*[:：]\s*([0-9,\s，、]*)\s*[;；]?\s*放弃\s*[:：]\s*([0-9,\s，、]*)")
DECL_LOOSE_RE = re.compile(
    r"写透\s*[:：]\s*([0-9,\s，、]+).*?放弃\s*[:：]\s*([0-9,\s，、]*)")


def _ints(s: str) -> Set[int]:
    out = set()
    for tok in re.findall(r"\d+", s or ""):
        try:
            out.add(int(tok))
        except ValueError:
            pass
    return out


def parse_declaration(text: str) -> Tuple[Set[int], Set[int], str, bool]:
    """解析候选的取舍声明。
    返回 (写透集, 放弃集, 原始行, 是否解析成功)。
    ⚠️ **解析失败必须显式**（返回 parsed=False）⇒ 不得静默当成"没有声明"，
       否则"不声明"与"声明解析失败"两种情况会被混为一谈（v4 的教训：失败不许静默归零）。"""
    t = text or ""
    for line in t.splitlines():
        line = line.strip()
        if not line:
            continue
        m = DECL_RE.search(line)
        if m:
            return _ints(m.group(1)), _ints(m.group(2)), line, True
    m = DECL_LOOSE_RE.search(t)
    if m:
        return _ints(m.group(1)), _ints(m.group(2)), (m.group(0)[:120]), True
    return set(), set(), "", False


# ---------------------------------------------------------------- 行为抽取
NEG_MARKERS = ("不写", "不要写", "不再写", "不碰", "不展开", "不谈", "不提",
               "不打算", "放弃", "避开", "略过", "无需", "没必要", "暂且不",
               "不在这一轮", "留到以后", "暂不", "不作为", "不铺开")


def _entity_mentions(text: str, entity: str) -> List[dict]:
    t = text or ""
    out, start = [], 0
    while True:
        i = t.find(entity, start)
        if i < 0:
            break
        window = t[max(0, i - 14):i]
        out.append({"pos": i, "negated": any(m in window for m in NEG_MARKERS)})
        start = i + max(1, len(entity))
    return out


def extract_entities(text: str, allowed: Sequence[str]) -> Tuple[List[str], List[str]]:
    """从正文抽**实际行为**：哪些实体**真正写到了**、哪些**没写到**。
    ★ 否定语境：实体前 14 字窗口含否定标记 ⇒ 该处计为**回避**（v4 的教训：
      纯逐字包含会把"提到了但放弃了"算成命中）。"""
    t = text or ""
    hit, missed = [], []
    for e in allowed or []:
        if not e:
            continue
        ms = _entity_mentions(t, e)
        if not ms:
            missed.append(e)
        elif any(not m["negated"] for m in ms):
            hit.append(e)
        else:
            missed.append(e)
    return hit, missed


# ---------------------------------------------------------------- 打分
def _jacc(a: Set[int], b: Set[int]) -> Optional[float]:
    if not a and not b:
        return None
    u = a | b
    return len(a & b) / len(u) if u else None


def score_state_alignment5(cand: Candidate5, st: State5) -> Optional[float]:
    """★ 状态化打分：**候选的自主声明** vs **状态的决定**（完全结构化）。

    ⚠️ 与 v4 的关键差别：v4 打分的是「正文命中实体」（候选看到缺口就能照做 ⇒ 恒真）；
       v5 打分的是「声明的编号 vs 状态的决策编号」⇒ 候选**不知道答案** ⇒ **非恒真**。

    构成（两项等权）：
      ① 写透一致度 = Jaccard(候选声明写透, 状态决定写透)
      ② 放弃一致度 = Jaccard(候选声明放弃, 状态决定放弃)

    ⚠️★ 修正（v5 冒烟后）：**每一项只在"状态对该项真有决策"时才计入**
      （deep_set 非空才比写透；drop_set 非空才比放弃）。
      理由：若状态本就不打算放弃任何东西，"放弃"就不是一个**有代价的选择**，
      拿它去惩罚候选（当 0 分）是错的 —— 只会把所有候选一起拉低，掩盖真实差异。
      ⚠️ 两项都空 ⇒ align=None（该样本无取舍代价 ⇒ 显式排除，不静默当 0）。
    ⚠️ 候选**没声明**或**解析失败** ⇒ 返回 None（**不是 0**）⇒ 不得静默归零。
    """
    if not cand.decl_parsed:
        return None
    vals = []
    if st.deep_set():
        jw = _jacc(cand.decl_write, st.deep_set())
        if jw is not None:
            vals.append(jw)
    if st.drop_set():
        jd = _jacc(cand.decl_drop, st.drop_set())
        if jd is not None:
            vals.append(jd)
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def score_fulfillment5(cand: Candidate5, st: State5) -> Optional[float]:
    """★ 兑现率：候选**声明写透**的缺口，正文是否**真的写了**它的实体。

    ⚠️ 这是「承诺 vs 行为」的结构化版本：绑定靠**编号**（离散），不靠措辞相似度。
    ⚠️ 声明了但没写 ⇒ 不计入兑现（不算作失败，只是没兑现）。
    """
    if not cand.decl_parsed or not cand.decl_write:
        return None
    ents: List[str] = []
    for i in cand.decl_write:
        ents.extend(st.entities_of(i))
    ents = [e for e in ents if e]
    if not ents:
        return None
    hit, _ = extract_entities(cand.text, ents)
    return round(len(hit) / len(ents), 4)


def score_violation5(cand: Candidate5, st: State5) -> Optional[float]:
    """★ 违禁率：候选**声明放弃**的缺口，正文却**写了**它的实体（弃而不舍）。
    ⚠️ 只看"声明放弃"的那些 ⇒ 与状态决策无关 ⇒ 纯行为核验。"""
    if not cand.decl_parsed or not cand.decl_drop:
        return None
    ents: List[str] = []
    for i in cand.decl_drop:
        ents.extend(st.entities_of(i))
    ents = [e for e in ents if e]
    if not ents:
        return None
    hit, _ = extract_entities(cand.text, ents)
    return round(len(hit) / len(ents), 4)


def score_generic5(cand: Candidate5, st: State5) -> float:
    """通用打分：长度 + 覆盖（**完全不看状态**）⇒ H3′ 的对照端。

    ⚠️ 覆盖项用状态实体的"总体出现量"是**弱状态依赖** ⇒ 为保持纯通用，
      这里只用**长度 + 段落数**（两者与状态无关）⇒ 通用打分是真正的"不看状态"基线。
    """
    t = (cand.text or "").strip()
    if not t:
        return 0.0
    len_s = min(1.0, len(t) / 900.0)
    para_s = min(1.0, max(0, t.count("\n\n")) / 6.0)
    return round(0.7 * len_s + 0.3 * para_s, 4)


# ---------------------------------------------------------------- 选择
def select5(cands: List[Candidate5], scorer, tiebreak=None
             ) -> Tuple[Optional[Candidate5], List[dict]]:
    """按 scorer 选候选。★ 并列时用 tiebreak（可传状态信息）；再并列取第一个（确定性）。"""
    scored = []
    for c in cands:
        if c.error or not (c.text or "").strip():
            continue
        sc = scorer(c)
        if sc is None:
            continue                      # ⚠️ 打不出分（无声明/解析失败）⇒ 排除，不当 0
        tb = tiebreak(c) if tiebreak else 0.0
        scored.append({"idx": c.idx, "score": sc, "tiebreak": tb, "text": c.text})
    if not scored:
        return None, []
    best = max(scored, key=lambda r: (r["score"], r["tiebreak"], -r["idx"]))
    return next(c for c in cands if c.idx == best["idx"]), scored


# ---------------------------------------------------------------- 提示渲染
CAND5_PROMPT = """你要写一篇中文文章。

这一轮的处境（你自己决定怎么用）：
- 你的立场：{stance}
- 你不能放弃的：{keeps}
- 你看到的几个缺口（编号 {idx_list}，每个附带它涉及的具体词）：
{gaps}

**这一轮要你自己决定两件事**（用编号说）：
1. 你**重点写透**哪几个缺口（不必全写）；
2. 你**明确放弃**哪几个缺口（写了就散了）。

**第一行必须严格写成这个格式**（只写一行，后面紧接正文）：
【取舍】写透：<编号,编号>；放弃：<编号,编号>

然后直接写出这一轮的文章正文（{lo}–{hi} 字）。
不要写"我将写什么"之类的话，直接写文章。
"""


def render_candidate_prompt5(st: State5, lo: int, hi: int, blind: bool = False,
                            cand_no: int = 0, k: int = 0) -> str:
    """渲染候选提示。

    ★★ 两条铁律（缺一则实验无效）：
      ① 提示里**绝不能**出现状态的决定（哪个该写透、哪个该放弃）⇒
         否则候选"照做就能声明对" ⇒ 状态化打分**恒真**；
      ② blind=True ⇒ 连缺口的**内容与实体**都不给（只给编号）⇒ 判决臂用。
    ⚠️ 编号**必须给**（否则"自主声明"无法结构化绑定）。
    """
    idxs = sorted(st.all_indices())
    if blind:
        gl = "\n".join("%d. （内容未公开）" % i for i in idxs) or "（无）"
    else:
        gl = "\n".join("%d. %s（涉及：%s）" % (
            i, (st.gap_map().get(i) or {}).get("text", ""),
            "、".join((st.gap_map().get(i) or {}).get("entities") or []) or "（无）")
            for i in idxs) or "（无）"
    p = CAND5_PROMPT.format(
        stance=st.stance or "（未明确）",
        keeps="；".join(st.keeps) or "（未明确）",
        gaps=gl, idx_list="、".join(str(i) for i in idxs) or "（无）",
        lo=lo, hi=hi)
    # ★★ 让 K 个候选给出**互不相同**的取舍方案
    # ⚠️ 只给"你是第几次尝试"，**不给任何关于哪个该写透/放弃的信息**
    #    ⇒ 候选之间的差异来自模型自己 ⇒ 不引入状态泄漏 ⇒ 非恒真保持
    if k and k > 1:
        p += ("\n（这是你的第 %d 次尝试，共 %d 次。请给出一个**与其它次明显不同**的取舍方案，"
              "不要重复常见的选择。）\n" % (cand_no, k))
    return p


# ---------------------------------------------------------------- 自检
def _selfcheck(verbose=True):
    res = []

    def chk(name, cond, detail=""):
        res.append((bool(cond), name, detail))

    st = State5(
        stance="立场甲", keeps=["保留甲"],
        gaps=[{"index": 1, "text": "缺口一涉及甲乙", "entities": ["甲", "乙"]},
              {"index": 2, "text": "缺口二涉及丙", "entities": ["丙"]},
              {"index": 3, "text": "缺口三涉及丁", "entities": ["丁"]}],
        decisions=[{"gap_index": 1, "depth": "深入展开", "priority": 1, "note": "n"},
                   {"gap_index": 2, "depth": "点到为止", "priority": 3, "note": "n"},
                   {"gap_index": 3, "depth": "放弃", "priority": 2, "note": "n"}])

    # 1. 派生集合
    chk("deep_set = {1}", st.deep_set() == {1}, st.deep_set())
    chk("drop_set = {3}", st.drop_set() == {3}, st.drop_set())
    chk("entities_of(1) = 甲乙", st.entities_of(1) == ["甲", "乙"], st.entities_of(1))

    # 2. 声明解析
    w, d, raw, ok = parse_declaration("【取舍】写透：1,2；放弃：3\n正文……")
    chk("声明解析：写透 {1,2}", ok and w == {1, 2}, w)
    chk("声明解析：放弃 {3}", ok and d == {3}, d)
    w2, d2, _, ok2 = parse_declaration("写透: 1 ; 放弃: 2,3")
    chk("宽松解析可容错", ok2 and w2 == {1} and d2 == {2, 3}, (ok2, w2, d2))
    w3, d3, _, ok3 = parse_declaration("这里没有声明")
    chk("★ 无声明 ⇒ parsed=False（不静默当'没声明'）", (not ok3) and w3 == set(),
        (ok3, w3))

    # 3. ★ 否定语境
    hit, missed = extract_entities("这篇写甲不写丙", ["甲", "丙", "丁"])
    chk("否定语境：丙算回避不算命中", hit == ["甲"] and missed == ["丙", "丁"],
        (hit, missed))

    # 4. 状态化打分 = 声明 vs 决策（结构化）
    c_good = Candidate5(1, "正文写到甲乙丙丁", {1}, {3}, "", True)
    c_bad = Candidate5(2, "正文写到甲乙丙丁", {2}, {1}, "", True)
    c_none = Candidate5(3, "正文写到甲乙丙丁", set(), set(), "", False)
    s_good = score_state_alignment5(c_good, st)
    s_bad = score_state_alignment5(c_bad, st)
    chk("★ 声明对 ⇒ 状态化分高", s_good is not None and s_good > 0.5, s_good)
    chk("★ 声明错 ⇒ 状态化分低", s_bad is not None and s_bad < s_good, (s_bad, s_good))
    chk("★ 无声明 ⇒ 打分 None（不是 0）", score_state_alignment5(c_none, st) is None)

    # 5. ★ 恒真风险检验：候选**不知道**状态决定时，声明不可能"自动对齐"
    #    —— 用一个"随机声明"在 50 次上模拟，其对齐分应明显低于"正确声明"
    import random
    rnd = random.Random(0)
    scores = []
    for _ in range(200):
        w_ = {rnd.choice([1, 2, 3])}
        d_ = {rnd.choice([1, 2, 3])} - w_
        c = Candidate5(1, "x", w_, d_, "", True)
        s = score_state_alignment5(c, st)
        if s is not None:
            scores.append(s)
    mean_rnd = sum(scores) / len(scores)
    chk("★ 随机声明的对齐分明显低于正确声明（⇒ 非恒真的必要条件）",
        mean_rnd < s_good - 0.2, (round(mean_rnd, 3), s_good))

    # 6. 兑现 / 违禁
    c_f = Candidate5(1, "文章里认真讨论了甲和乙", {1}, set(), "", True)
    chk("★ 兑现率：声明写透 1 且正文写了 甲乙 ⇒ 1.0",
        score_fulfillment5(c_f, st) == 1.0, score_fulfillment5(c_f, st))
    c_v = Candidate5(1, "文章里还是讲了丁", set(), {3}, "", True)
    chk("★ 违禁率：声明放弃 3 却写了丁 ⇒ 1.0",
        score_violation5(c_v, st) == 1.0, score_violation5(c_v, st))

    # 7. 通用打分与状态无关
    c_x = Candidate5(1, "短", set(), set(), "", True)
    c_y = Candidate5(2, "长" + "内容" * 400, set(), set(), "", True)
    chk("通用打分与状态无关（同样文本同分）",
        score_generic5(c_x, st) == score_generic5(c_x, st))
    chk("通用打分偏好更长文本", score_generic5(c_y, st) > score_generic5(c_x, st))

    # 8. select：排除打不出分的候选
    chosen, scored = select5([c_none, c_good, c_bad], lambda c: score_state_alignment5(c, st))
    chk("★ select 排除无声明候选（不当作 0 分）",
        chosen is not None and chosen.idx == c_good.idx and len(scored) == 2,
        (chosen.idx if chosen else None, len(scored)))

    # 9. ★ 提示**不得泄漏状态决定**
    p = render_candidate_prompt5(st, 600, 900, blind=False)
    leak = ("深入展开" in p) or ("放弃第" in p) or ("写透第" in p)
    chk("★ 候选提示不含状态决定（深入展开/放弃第/写透第）", not leak)
    chk("★ 候选提示含缺口编号", "1." in p and "2." in p and "3." in p)
    chk("★ 候选提示含缺口内容（非 blind）", "缺口一涉及甲乙" in p)

    # 10. ★ blind：只给编号，不给内容与实体
    pb = render_candidate_prompt5(st, 600, 900, blind=True)
    chk("★ blind 提示不含缺口内容与缺口实体",
        all(x not in pb for x in ("缺口一涉及甲乙", "缺口二涉及丙", "缺口三涉及丁",
                                  "丙", "丁")), pb[:120])
    chk("★ blind 提示仍含编号（结构化绑定需要）", "1." in pb and "2." in pb)

    # 10b. ★ 多候选差异化提示：不得泄漏状态决定
    pm = render_candidate_prompt5(st, 600, 900, blind=False, cand_no=2, k=3)
    chk("★ 多候选提示含尝试序号", "第 2 次尝试" in pm)
    chk("★ 多候选提示仍不含状态决定",
        ("深入展开" not in pm) and ("放弃第" not in pm) and ("写透第" not in pm))

    # 10b. ★ 多候选差异化提示：不得泄漏状态决定
    pm = render_candidate_prompt5(st, 600, 900, blind=False, cand_no=2, k=3)
    chk("★ 多候选提示含尝试序号", "第 2 次尝试" in pm)
    chk("★ 多候选提示仍不含状态决定",
        ("深入展开" not in pm) and ("放弃第" not in pm) and ("写透第" not in pm))

    # 10b. ★ 多候选差异化提示：不得泄漏状态决定
    pm = render_candidate_prompt5(st, 600, 900, blind=False, cand_no=2, k=3)
    chk("★ 多候选提示含尝试序号", "第 2 次尝试" in pm)
    chk("★ 多候选提示仍不含状态决定",
        ("深入展开" not in pm) and ("放弃第" not in pm) and ("写透第" not in pm))

    # 11. ★ 变异注入：把状态化打分换成通用打分 ⇒ 必须被检测到
    cA = Candidate5(1, "短", {1}, {3}, "", True)     # 声明对但文本短
    cB = Candidate5(2, "长" + "内容" * 400, {2}, {1}, "", True)  # 声明错但文本长
    pick_state, _ = select5([cA, cB], lambda c: score_state_alignment5(c, st))
    pick_generic, _ = select5([cA, cB], lambda c: score_generic5(c, st))
    chk("变异注入前提：两个打分器选出不同的候选",
        pick_state.idx != pick_generic.idx, (pick_state.idx, pick_generic.idx))
    mutated, _ = select5([cA, cB], lambda c: score_generic5(c, st))
    chk("★ 变异注入：打分器退化为通用打分时被抓到",
        mutated.idx != pick_state.idx,
        ("变异体 idx=%s，应为 %s" % (mutated.idx, pick_state.idx)))

    # 11b. ★ 状态无"放弃"决策时，放弃维度不计入（不当 0 惩罚）
    st_nodrop = State5(stance=st.stance, keeps=st.keeps, gaps=st.gaps,
                        decisions=[{"gap_index": 1, "depth": "深入展开", "priority": 1, "note": "n"}])
    c_drop3 = Candidate5(1, "正文写到甲乙丙丁", {1}, {3}, "", True)
    s_nd = score_state_alignment5(c_drop3, st_nodrop)
    chk("★ 状态无放弃决策 ⇒ 放弃维度不计入（对齐分=写透维度）",
        s_nd is not None and abs(s_nd - 1.0) < 1e-6, s_nd)
    st_alldrop = State5(stance=st.stance, keeps=st.keeps, gaps=st.gaps, decisions=[])
    chk("★ 状态两项都无决策 ⇒ align=None（不静默当 0）",
        score_state_alignment5(c_drop3, st_alldrop) is None)

    # 12. 往返
    chk("State5 to_dict/from_dict 往返一致",
        State5.from_dict(st.to_dict()).to_dict() == st.to_dict())

    if verbose:
        for okk, name, det in res:
            print("  %s %-52s %s" % ("✓" if okk else "✗", name, det if det != "" else ""))
        npass = sum(1 for o, _, _ in res if o)
        print("=== workflow_arch5 自检: %s (%d/%d) ==="
              % ("通过" if npass == len(res) else "失败", npass, len(res)))
    return all(o for o, _, _ in res), res


if __name__ == "__main__":
    ok, _ = _selfcheck()
    raise SystemExit(0 if ok else 1)
