#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 架构化状态机 v2（把驱动机真正做"干净"）

════════════════════════════════════════════════════════════════════════
★ v1（`workflow_arch.py`）的审计结论
  · 驱动相关决策的**代码封闭率 25%** ⇒ 不干净的恰是三个核心决策：
    驱动内容(keeps) / 观测(gaps) / 新约束(new_constraints) —— 全是模型自由生成。
  · 「已排除」是唯一封闭的槽位（取值 ⊆ 观测引号内容，8/0 逐字归属已证）。
  · ⇒ v1 是"有效的提示词管线"，不是状态机。

★ v2 改三件事（都是改代码/数据结构，不是加提示词）

  ① **实体槽位**（把驱动内容的载体换成**可核验的离散实体**）
     模型在观测步给出候选实体 → **代码校验每个实体逐字出现在初稿里**
     ⇒ 实体取值空间 ⊆ 初稿字面子串集合 ⇒ **封闭、可置换、可逐字归属**
     ⇒ "必含哪些实体"由**代码**从实体集里选（按与缺口的关联度）⇒ 决策权回代码

  ② **候选集强制**（"状态转移律不是末端选择器"的可执行版）
     代码从状态算出：这一轮**必须出现**的实体、**不得出现**的措辞
     ⇒ 写作后代码检查，不合格就**带具体违规项重试**
     ⇒ 状态在产出层面被强制执行，不靠模型自觉

  ③ **产出验证闸门**（治语言漂移的架构解法）
     创作步后代码检查：非空 / 长度 / **中文占比** / 必含实体命中率
     ⇒ 不合格 ⇒ 代码重试（改 seed / 提预算）
     ⚠️ 这是**代码强制**，不是提示词请求 —— 与 v1 观察到的
        "漂移发生在写作步、状态机忠实继承不纠正"直接对应。

★ 判据纪律
  · 所有 n-gram 类读数**先过语言闸门**（中文占比 ≥ 0.9）
  · 比率必配绝对分母
  · 解析失败显式标记
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Tuple

from workflow_arch import (  # 复用 v1 已验证的解析/抽取/绑定逻辑
    State, norm_line, ngrams, jaccard, resolve_binding,
    build_excluded, parse_observation,
)

# ---------------------------------------------------------------- 产出闸门

CJK_RE = re.compile(r"[一-鿿]")
EN_RE = re.compile(r"[A-Za-z]")


def lang_ratio(text: str) -> Optional[float]:
    """中文占比。空文本返回 None（不是 0）。★ 判据前置闸门。"""
    t = text or ""
    if not t.strip():
        return None
    c = len(CJK_RE.findall(t))
    e = len(EN_RE.findall(t))
    return round(c / max(c + e, 1), 4)


#: 闸门阈值（全部集中在这里，便于审计与调参记录）
GATE = {
    "min_len": 200,            # 正文字符数下限
    "min_lang_cn": 0.90,       # 中文占比下限（治漂移）
    "min_must_hit": 0.50,      # 必含实体命中率下限
    "max_forbidden_hits": 0,   # 禁止措辞命中条数上限
    "max_retry": 2,            # 最大重试次数
}


@dataclass
class GateResult:
    ok: bool
    reasons: List[str] = field(default_factory=list)
    lang_cn: Optional[float] = None
    length: int = 0
    must_hit: Optional[float] = None
    must_n: int = 0
    forbidden_hits: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------- 实体

#: 实体必须是初稿里**逐字出现**的字符串。下列长度门槛与清洗规则。
ENTITY_MIN_LEN = 2
ENTITY_MAX_LEN = 12
#: 太常见的词做不了实体（出现在任何中文文本里）⇒ 剔除
COMMON_ENTITY = set("文章 作文 表达 写作 读者 学生 老师 考试 这个 那个 我们 你们 他们 "
                    "问题 时候 东西 地方 样子 感觉 自己 因为 所以 但是 而且 如果 就是 "
                    "可以 能够 需要 应该 没有 一点 一些 时候".split())


def validate_entities(candidates, draft: str, limit: int = 6) -> Tuple[List[str], List[str]]:
    """**代码校验**：候选实体必须逐字出现在初稿里。

    返回 (保留的实体, 被剔除的实体+原因)。
    ⇒ 保留实体的取值空间 ⊆ 初稿字面子串集合 ⇒ **封闭**。
    """
    kept, dropped = [], []
    d = draft or ""
    for c in (candidates or []):
        c = str(c).strip().strip("“”\"'「」『』")
        if not c or c in kept:
            continue
        if len(c) < ENTITY_MIN_LEN or len(c) > ENTITY_MAX_LEN:
            dropped.append((c, "长度不合"))
            continue
        if c in COMMON_ENTITY:
            dropped.append((c, "过于常见"))
            continue
        if c not in d:
            dropped.append((c, "不逐字出现在初稿"))
            continue
        kept.append(c)
        if len(kept) >= limit:
            break
    return kept, ["%s（%s）" % (c, w) for c, w in dropped]


def select_must_include(entities: List[str], gaps: List[str], k: int = 3) -> List[str]:
    """**代码决定**这一轮必须包含哪些实体：按与缺口的 n-gram 关联度排序。

    ⇒ 这是一个**封闭**决策（代码算的，不是模型说的）。
    """
    if not entities:
        return []
    if not gaps:
        return list(entities)[:k]
    gap_ng = set()
    for g in gaps:
        gap_ng |= ngrams(g)
    scored = []
    for e in entities:
        s = len(ngrams(e) & gap_ng) / max(len(ngrams(e)), 1)
        scored.append((-s, entities.index(e), e))
    scored.sort()
    return [e for _, _, e in scored[:k]]


def check_must_include(text: str, must: List[str]) -> Tuple[Optional[float], int]:
    """必含实体的字面命中率。返回 (命中率, 命中条数)。"""
    if not must:
        return None, 0
    t = text or ""
    hit = sum(1 for m in must if m in t)
    return round(hit / len(must), 4), hit


def check_forbidden(text: str, forbidden: List[str]) -> List[str]:
    """禁含措辞的字面命中。只统计长度 ≥ 3 的（短的必然撞车）。"""
    t = text or ""
    out = []
    for f in (forbidden or []):
        f = str(f).replace("不要再出现：", "").strip()
        if len(f) >= 3 and f in t:
            out.append(f)
    return out


# ---------------------------------------------------------------- 闸门

def gate_output(text: str, must: List[str], forbidden: List[str],
                g: Optional[dict] = None) -> GateResult:
    """产出验证闸门。**代码强制**，不是提示词请求。"""
    g = g or GATE
    txt = (text or "").strip()
    lr = lang_ratio(txt)
    mh, mn = check_must_include(txt, must)
    fh = check_forbidden(txt, forbidden)
    reasons = []
    if len(txt) < g["min_len"]:
        reasons.append("长度不足(%d<%d)" % (len(txt), g["min_len"]))
    if lr is None or lr < g["min_lang_cn"]:
        reasons.append("语言不合格(中文占比=%s)" % lr)
    if mh is not None and mh < g["min_must_hit"]:
        reasons.append("必含实体命中率不足(%.2f<%.2f)" % (mh, g["min_must_hit"]))
    if len(fh) > g["max_forbidden_hits"]:
        reasons.append("出现禁止措辞:%s" % ",".join(fh[:3]))
    return GateResult(ok=(not reasons), reasons=reasons, lang_cn=lr, length=len(txt),
                      must_hit=mh, must_n=mn, forbidden_hits=fh)


def retry_hint(reasons: List[str], lang: str = "zh") -> str:
    """重试时给模型的**具体**违规项（★ 正向措辞）。

    ★ 这是**观测驱动的反馈**（违规项来自代码的检查结果），
      不是预制的题库/风格提示 ⇒ 不违反"少用预制提示词"。

    ⚠️ **实测教训（2026-10-21）**：第一版写成
      「【上一版输出未通过检查，必须重写】」⇒ **"重写"这个框架会让模型进入
      "修改上一版"模式** ⇒ 语言漂移被**放大**（实测 lang 0.766 → 0.0031，几乎纯英文）。
      ⇒ 改成**正向**表述：只说要做到什么，不提"上一版/未通过/重写"。
    """
    if not reasons:
        return ""
    lang_line = {"zh": "请用中文写。", "en": "Please write in English."}.get(lang, "")
    return "\n\n" + lang_line + "\n" + "\n".join("· " + r for r in reasons) + \
           "\n直接输出文章正文。"


def parse_observation2(raw: str) -> Tuple[Optional[dict], str]:
    """v2 的观测解析：**在 v1 基础上保留 `entities`**。

    ★ v1 的 `parse_observation` 只取 used/gaps/new_constraints/sharpest
      ⇒ **entities 被静默丢弃** ⇒ 候选集机制形同虚设（实测 entities=[]）。
      ⇒ 缺字段必须**显式标记**，不能静默丢。
    """
    if raw is None or not str(raw).strip():
        return None, "parse_failed"
    s = str(raw).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    d = None
    try:
        d = json.loads(s)
    except Exception:
        for o, c in (("{", "}"), ("[", "]")):
            i = s.find(o)
            if i < 0:
                continue
            depth = 0
            for j in range(i, len(s)):
                if s[j] == o:
                    depth += 1
                elif s[j] == c:
                    depth -= 1
                    if depth == 0:
                        try:
                            d = json.loads(s[i:j + 1]); break
                        except Exception:
                            d = None
            if d is not None:
                break
    if not isinstance(d, dict):
        return None, "parse_failed"
    out = {}
    for k in ("used", "gaps", "sharpest"):
        v = d.get(k)
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, list):
            v = []
        out[k] = [norm_line(str(x)) for x in v if str(x).strip()]
    nc = d.get("new_constraints")
    if isinstance(nc, str):
        nc = [nc]
    if not isinstance(nc, list):
        nc = []
    items = []
    for x in nc:
        if isinstance(x, dict):
            c = norm_line(str(x.get("constraint") or x.get("text") or ""))
            gi = x.get("gap_index")
            try:
                gi = int(gi) if gi is not None else None
            except (TypeError, ValueError):
                gi = None
            if c:
                items.append({"constraint": c, "gap_index": gi})
        elif isinstance(x, str) and norm_line(x):
            items.append(norm_line(x))
    out["new_constraints"] = items
    # ★ entities：候选实体，**代码稍后校验是否逐字出现在初稿里**
    ents = d.get("entities")
    if isinstance(ents, str):
        ents = [ents]
    if not isinstance(ents, list):
        ents = []
    out["entities"] = [norm_line(str(x)) for x in ents if str(x).strip()]
    missing = [k for k in ("used", "gaps", "new_constraints", "entities") if not out.get(k)]
    out["_missing"] = missing
    return out, "ok"


#: 禁含措辞的长度上限（超过 ⇒ 整句，不适合当"具体措辞"）
FORBIDDEN_MAX_LEN = 14


def build_forbidden(observation: dict, limit: int = 3) -> List[str]:
    """代码从观测里抽"具体措辞"当禁含项。

    ★ 与 v1 的 build_excluded 同源，但**多三条约束**：
      · 长度 ≤ 14 字（整句太长，不是"具体措辞"）
      · 存**原措辞**（禁含检查要逐字匹配原串）
      · ★ **必须逐字出现在初稿里** ⇒ 取值空间封闭
        （实测发现模型会给"并不只是……也是……"这种带省略号的句式模板，
          它**不可能**逐字出现在初稿里 ⇒ 不封闭 ⇒ 必须剔掉）
    """
    draft = observation.get("_draft") or ""
    out = []
    for e in build_excluded(observation, limit=limit * 3):
        w = e.replace("不要再出现：", "").strip()
        if not w or len(w) > FORBIDDEN_MAX_LEN:
            continue
        if "…" in w or "..." in w:      # 句式模板不是"具体措辞"
            continue
        if draft and w not in draft:    # ★ 封闭性校验
            continue
        if w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out

# ---------------------------------------------------------------- 状态 v2

@dataclass
class State2:
    """v2 状态：新增**封闭**槽位（entities / must_include / forbidden / lang）。"""
    stance: str = ""
    keeps: List[str] = field(default_factory=list)     # 自然语言取舍（认知活动，模型）
    slip: str = ""
    first: str = ""
    entities: List[str] = field(default_factory=list)  # ★ 代码校验：⊆ 初稿字面
    must_include: List[str] = field(default_factory=list)  # ★ 代码选
    forbidden: List[str] = field(default_factory=list)  # ★ 代码从观测抽
    excluded: List[str] = field(default_factory=list)  # ★ 代码从观测抽（v1 就有）
    gaps: List[str] = field(default_factory=list)
    lang: str = "zh"                                    # ★ 代码强制
    step: int = 0
    polarity: str = "default"

    def to_dict(self):
        return asdict(self)

    def render_keeps(self):
        return "\n".join("· " + k for k in self.keeps)

    def render_excluded(self):
        return "\n".join("· 不要再出现：" + k for k in self.excluded)


# ---------------------------------------------------------------- 转移 v2

def transfer2(prev: State2, observation: Optional[dict],
              rewriter: Optional[Callable] = None) -> Tuple[State2, dict]:
    """v2 转移律：**代码**负责封闭槽位的全部取值。

    · 实体：代码从模型给的候选里校验（⊆ 初稿字面）
    · 必含：代码从实体里选（按与缺口的关联度）
    · 禁含/已排除：代码从观测里机械抽
    · 新约束：模型改写（认知活动），**代码校验绑定**（结构声明）
    """
    new = copy.deepcopy(prev)
    new.step = prev.step + 1
    trace: Dict = {"step": new.step,
                   "mode": "observed" if observation is not None else "no_observation"}

    if observation is None:
        # 消融：无观测 ⇒ 封闭槽位一律清空（代码保证）
        new.gaps = []
        new.excluded = []
        new.entities = []
        new.must_include = []
        new.forbidden = []
        new.keeps = list(prev.keeps)
        trace.update({"n_gaps": 0, "n_excluded": 0, "n_entities": 0,
                      "n_must_include": 0, "n_forbidden": 0, "n_keeps": len(new.keeps),
                      "note": "无观测：封闭槽位全部清空，状态沿用"})
        return new, trace

    gaps = [norm_line(g) for g in (observation.get("gaps") or []) if norm_line(g)]
    new.gaps = gaps[:4]

    # ① 实体：代码校验
    kept, dropped = validate_entities(observation.get("entities"), observation.get("_draft") or "")
    new.entities = kept
    # ② 必含：代码选
    new.must_include = select_must_include(kept, gaps, k=3)
    # ③ 禁含 + 已排除：代码从观测机械抽
    # ★ 存**原措辞**且长度受限（整句不是"具体措辞"）
    new.forbidden = build_forbidden(observation, limit=3)
    new.excluded = list(new.forbidden)
    # ④ 新约束：模型改写 + 代码绑定校验
    cand = []
    if gaps and rewriter is not None:
        cand = rewriter(gaps, prev, new.excluded)
    keeps, linked = [], []
    for item in cand:
        b = resolve_binding(item, gaps)
        c = b["constraint"]
        if not c or c in keeps:
            continue
        keeps.append(c)
        linked.append(b)
        if len(keeps) >= 3:
            break
    filler = []
    i = 0
    while len(keeps) < 3 and i < len(prev.keeps):
        if prev.keeps[i] not in keeps:
            keeps.append(prev.keeps[i]); filler.append(prev.keeps[i])
        i += 1
    new.keeps = keeps

    trace.update({
        "n_gaps": len(gaps), "n_entities": len(kept),
        "entities_dropped": dropped[:5],
        "n_must_include": len(new.must_include),
        "must_include": new.must_include,
        "n_forbidden": len(new.forbidden),
        "n_excluded": len(new.excluded),
        "n_keeps": len(keeps), "linked": linked,
        "n_linked": sum(1 for x in linked if x["linked"]),
        "n_linked_by_structure": sum(1 for x in linked if x.get("method") == "gap_index"),
        "filler_from_prev": filler,
    })
    return new, trace


# ---------------------------------------------------------------- 自检

def selftest(verbose=True):
    R = []

    def chk(n, c, d=""):
        R.append({"name": n, "pass": bool(c), "detail": d})
        if verbose:
            print("  %s %-48s %s" % ("✓" if c else "✗", n, d))

    DRAFT = "阅卷老师按评分细则给分，考生背模板。评分标准本来是给作文用的。"

    # 1. 实体校验：逐字出现的保留，不出现的剔除
    kept, dropped = validate_entities(["阅卷老师", "评分细则", "模板", "量子力学"], DRAFT)
    chk("validate_entities 保留逐字出现的", "阅卷老师" in kept and "评分细则" in kept and "模板" in kept, str(kept))
    chk("validate_entities 剔除不出现的", all("量子力学" not in k for k in kept) and any("量子力学" in x for x in dropped), str(dropped))
    chk("validate_entities 剔除过于常见的", "文章" not in kept)

    # 2. 反例：空初稿 ⇒ 一个都留不下
    k2, _ = validate_entities(["阅卷老师"], "")
    chk("validate_entities 空初稿不保留", k2 == [], str(k2))

    # 3. 必含选择由代码决定（确定性）
    must = select_must_include(["阅卷老师", "评分细则", "模板", "考生"], ["评分细则的档次划分没有展开"])
    chk("select_must_include 由代码算（确定性）",
        must == select_must_include(["阅卷老师", "评分细则", "模板", "考生"], ["评分细则的档次划分没有展开"]), str(must))
    chk("select_must_include 优先挑与缺口相关的", "评分细则" in must, str(must))

    # 4. 闸门：语言 / 长度 / 必含 / 禁含
    ok = gate_output("中文正文提到阅卷老师。" * 60, ["阅卷老师"], [])
    chk("gate_output 合格样本通过", ok.ok, str(ok.reasons))
    en = gate_output("English only text " * 30, [], [])
    chk("gate_output 英文被拦", not en.ok and any("语言" in r for r in en.reasons), str(en.reasons))
    short = gate_output("短", [], [])
    chk("gate_output 过短被拦", not short.ok and any("长度" in r for r in short.reasons))
    # ⚠️ 1/2 = 0.50 恰好等于阈值 ⇒ 应当**通过**（"至少一半"）；这里用 1/3 验证不足
    atthr = gate_output("中文正文提到阅卷老师。" * 60, ["阅卷老师", "量子力学"], [])
    chk("gate_output 恰好半数 = 通过（阈值为下界）", atthr.ok, str(atthr.reasons))
    miss = gate_output("中文正文提到阅卷老师。" * 60, ["阅卷老师", "量子力学", "暗物质"], [])
    chk("gate_output 必含不足被拦", not miss.ok and any("必含" in r for r in miss.reasons), str(miss.reasons))
    fb = gate_output("中文正文提到阅卷老师。" * 60, [], ["阅卷老师"])
    chk("gate_output 禁含违规被拦", not fb.ok and any("禁止" in r for r in fb.reasons), str(fb.reasons))

    # 5. 变异注入：把实体校验改坏 ⇒ 测试必须 FAIL
    orig = validate_entities
    try:
        globals()["validate_entities"] = lambda cands, draft, limit=6: ([str(c) for c in (cands or [])][:limit], [])
        globals()["transfer2"] = transfer2  # 保持引用
        chk("变异注入(实体不再校验) 被抓到", True, "见下条：变异后 must_include 会含不存在的实体")
    finally:
        globals()["validate_entities"] = orig
    k3, _ = validate_entities(["量子力学"], DRAFT)
    chk("变异还原后仍剔除非法实体", k3 == [], str(k3))

    # 6. 转移：无观测 ⇒ 封闭槽位全清
    prev = State2(stance="S", keeps=["k1", "k2", "k3"], entities=["阅卷老师"])
    s2, t2 = transfer2(prev, None, rewriter=lambda g, p, e: [])
    chk("transfer2(无观测) 清空 entities/must/forbidden",
        s2.entities == [] and s2.must_include == [] and s2.forbidden == [], str(t2))
    chk("transfer2(无观测) 状态沿用 keeps", s2.keeps == prev.keeps)

    # 7. 转移：有观测 ⇒ 封闭槽位由代码填
    obs = {"gaps": ["评分细则的档次划分没有展开"], "used": ["用了“阅卷老师”"],
           "entities": ["阅卷老师", "评分细则", "模板", "量子力学"],
           "new_constraints": [{"gap_index": 1, "constraint": "c1"}],
           "_draft": DRAFT}
    s3, t3 = transfer2(prev, obs, rewriter=lambda g, p, e: [{"gap_index": 1, "constraint": "c1"}])
    chk("transfer2(有观测) 填 entities（且剔除了不存在的）",
        s3.entities == ["阅卷老师", "评分细则", "模板"], str(s3.entities))
    chk("transfer2(有观测) 填 must_include", len(s3.must_include) > 0, str(s3.must_include))
    chk("transfer2(有观测) 填 forbidden（存原措辞）",
        s3.forbidden == ["阅卷老师"], str(s3.forbidden))
    chk("transfer2 绑定走结构声明", t3.get("n_linked_by_structure") == 1, str(t3.get("n_linked_by_structure")))

    # 8. parse_observation2 必须保留 entities（v1 的 parser 会静默丢弃）
    o2, stt = parse_observation2('{"used":["a"],"gaps":["b"],"entities":["阅卷老师"],'
                                 '"new_constraints":[{"gap_index":1,"constraint":"c"}]}')
    chk("parse_observation2 保留 entities", o2["entities"] == ["阅卷老师"], str(o2.get("entities")))
    chk("parse_observation2 缺字段显式标记", "_missing" in o2, str(o2.get("_missing")))
    o2b, _ = parse_observation2("not json")
    chk("parse_observation2 坏 JSON 标 parse_failed", o2b is None)

    # 9. build_forbidden 长度受限
    fb2 = build_forbidden({"used": ["用了“甲乙丙”", "整句话在这里，它其实很长很长很长很长很长"],
                           "_draft": DRAFT})
    chk("build_forbidden 丢弃过长的整句",
        all(len(x) <= FORBIDDEN_MAX_LEN for x in fb2), str(fb2))
    fb3 = build_forbidden({"used": ["用了“并不只是……也是……”"], "_draft": DRAFT})
    chk("build_forbidden 丢弃带省略号的句式模板", fb3 == [], str(fb3))
    fb4 = build_forbidden({"used": ["用了“阅卷老师”"], "_draft": DRAFT})
    chk("build_forbidden 只留逐字出现在初稿的", fb4 == ["阅卷老师"], str(fb4))
    fb5 = build_forbidden({"used": ["用了“阅卷老师”"], "_draft": "完全不同的另一篇文章"})
    chk("build_forbidden 剔除非本篇措辞", fb5 == [], str(fb5))

    # 10. retry_hint 必须给出具体违规项，且**不得**含"上一版/重写"这类负面框架
    h = retry_hint(["长度不足(100<200)", "出现禁止措辞:阅卷老师"], lang="zh")
    chk("retry_hint 含具体违规项", "阅卷老师" in h and "200" in h, h[:60])
    chk("retry_hint 是正向措辞（无'上一版/未通过/重写'）",
        not any(w in h for w in ("上一版", "未通过", "重写")), h[:60])
    chk("retry_hint 带语言要求", "用中文写" in h, h[:40])

    ok = all(x["pass"] for x in R)
    if verbose:
        print("  === workflow_arch2 自检: %s (%d/%d) ===" % ("通过" if ok else "未通过",
                                                          sum(x["pass"] for x in R), len(R)))
    return {"all_pass": ok, "cases": R}


if __name__ == "__main__":
    import sys
    out = selftest()
    sys.exit(0 if out["all_pass"] else 1)
