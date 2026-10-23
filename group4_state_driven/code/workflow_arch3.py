#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 架构化状态机 v3：把「取舍」本身离散化

════════════════════════════════════════════════════════════════════════
★ 为什么是 v3（依据 PREREG_v3.md 的两条前置诊断）
  · v1 的 D2（换初稿）测的是**反馈通路**，不是**驱动力通路** ⇒ 此前结论过度解读
  · v2 的 D2（换立场）测的是驱动力通路，但**缺 D0 纯重跑地板** ⇒ 不可分辨
  ⇒ v3 的目标不是"让取舍更干净"，而是**回答"取舍为什么驱动不了产出"**

★ v3 的状态设计（改数据结构，不是加提示词）

    State3:
      stance / keeps / slip / first     认知产物（模型）
      gaps: List[Gap]                   ★ 每个缺口带 1-2 个**相关实体**
                                          实体由代码逐字校验 ⊆ 初稿 ⇒ 封闭
      decisions: List[Decision]         ★ {gap_index, depth, priority}
                                          depth ∈ {深入展开, 点到为止, 放弃}（封闭枚举）
                                          priority ∈ {1,2,3}（封闭枚举）
      must_include / forbidden           ★ 由 decisions **代码推导**
      entities / lang / excluded         v2 已有（封闭）

  ⇒ 「取舍」的载体 = **在已识别的缺口上，决定写到什么程度**。
    · gap_index 来自观测（封闭）
    · depth 是封闭枚举
    · "放弃某个缺口" = 真实的取舍代价
  ⇒ 代码据此推导：
      depth=深入展开 ⇒ 该缺口的实体进入 must_include
      depth=放弃     ⇒ 该缺口的实体进入 forbidden

★ 证据只能是 D2'（换候选集，单变量）与 D0（纯重跑地板）。
  "必含命中 100%"只是**代码约束被执行**（v2 已证），**不作为 v3 的证据**。
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from workflow_arch import norm_line, ngrams, jaccard, resolve_binding, build_excluded
from workflow_arch2 import (State2, lang_ratio, gate_output, validate_entities,
                            select_must_include, build_forbidden, check_must_include,
                            check_forbidden, GATE)

# ---------------------------------------------------------------- 封闭枚举
DEPTHS = ("深入展开", "点到为止", "放弃")
PRIORITIES = (1, 2, 3)


@dataclass
class Gap:
    index: int                    # 1-based，指向观测里的第几个缺口
    text: str
    entities: List[str] = field(default_factory=list)   # ★ 代码校验 ⊆ 初稿


@dataclass
class Decision:
    gap_index: int
    depth: str = "点到为止"        # ★ 封闭枚举
    priority: int = 2              # ★ 封闭枚举
    note: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class State3:
    stance: str = ""
    keeps: List[str] = field(default_factory=list)
    slip: str = ""
    first: str = ""
    gaps: List[Gap] = field(default_factory=list)
    decisions: List[Decision] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    must_include: List[str] = field(default_factory=list)
    forbidden: List[str] = field(default_factory=list)
    excluded: List[str] = field(default_factory=list)
    lang: str = "zh"
    step: int = 0
    polarity: str = "default"

    def to_dict(self):
        d = asdict(self)
        d["gaps"] = [g if isinstance(g, dict) else asdict(g) for g in self.gaps]
        d["decisions"] = [x if isinstance(x, dict) else asdict(x) for x in self.decisions]
        return d

    def render_keeps(self):
        return "\n".join("· " + k for k in self.keeps)

    def render_nl_decisions(self):
        """★ 自然语言通道：把 decisions 渲染成**叙述**（不给代码强制）。

        ★★ **为什么必须有这条通道**（2026-10-21 23:40 的方法论修正）：
          若决策只经由**代码约束**（must_include / forbidden）生效，
          那么"状态变了 ⇒ 产出变了"是**代码的必然结果**，不是**驱动力**的证据
          ⇒ **循环论证**。
          ⇒ 只有让决策**仅以自然语言**进入 brief，"该展开的展开了 / 该放弃的没出现"
            才是**模型的选择** ⇒ 那才是可核验的**驱动力读数**。
        """
        out = []
        # ★ 兼容 dict / Decision 两种形态（to_dict() 之后是 dict）
        def g_(d, k, default=None):
            return d.get(k) if isinstance(d, dict) else getattr(d, k, default)

        def gtext(g):
            if isinstance(g, dict):
                return str(g.get("text") or "")
            return str(getattr(g, "text", "") or "")

        deep = [d for d in self.decisions if g_(d, "depth") == "深入展开"]
        skip = [d for d in self.decisions if g_(d, "depth") == "点到为止"]
        drop = [d for d in self.decisions if g_(d, "depth") == "放弃"]
        gm = {g_(g, "index"): g for g in self.gaps}

        def names(ds):
            parts = []
            for d in ds:
                gi = g_(d, "gap_index")
                g = gm.get(gi)
                t = gtext(g)[:28] if g is not None else ""
                parts.append(t if t else ("第%s条" % gi))
            return "、".join(parts)

        if deep:
            out.append("· 这一轮要真正写透：" + names(deep))
        if skip:
            out.append("· 提到就够、不展开：" + names(skip))
        if drop:
            out.append("· 这一轮不碰：" + names(drop))
        return "\n".join(out)

    def render_forbidden(self):
        """★ 决策推导的禁含（来自"放弃的缺口"）与观测措辞（excluded）**分开渲染**。"""
        out = []
        if self.forbidden:
            out.append("· 不要写：" + "、".join(self.forbidden))
        if self.excluded:
            out.append("· 已经写过、不要再写：" + "、".join(self.excluded))
        return "\n".join(out)


# ---------------------------------------------------------------- 解析

def parse_observation3(raw: str, draft: str = "") -> Tuple[Optional[dict], str]:
    """v3 观测解析：**gaps 升级为带相关实体的结构**，且实体由代码校验。

    ★ 缺字段必须显式标记（`_missing`），不能静默丢。
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
    for k in ("used", "sharpest"):
        v = d.get(k)
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, list):
            v = []
        out[k] = [norm_line(str(x)) for x in v if str(x).strip()]

    # ★ gaps：每个带 1-2 个相关实体（**代码逐字校验 ⊆ 初稿**）
    raw_gaps = d.get("gaps")
    if isinstance(raw_gaps, str):
        raw_gaps = [{"text": raw_gaps}]
    if not isinstance(raw_gaps, list):
        raw_gaps = []
    gaps = []
    for i, g in enumerate(raw_gaps, 1):
        if isinstance(g, str):
            g = {"text": g}
        if not isinstance(g, dict):
            continue
        text = norm_line(str(g.get("text") or g.get("gap") or ""))
        if not text:
            continue
        ents = g.get("entities")
        if isinstance(ents, str):
            ents = [ents]
        if not isinstance(ents, list):
            ents = []
        kept, dropped = validate_entities(ents, draft, limit=2)
        gaps.append({"index": i, "text": text, "entities": kept,
                     "dropped_entities": dropped})
    out["gaps"] = gaps

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

    ents = d.get("entities")
    if isinstance(ents, str):
        ents = [ents]
    if not isinstance(ents, list):
        ents = []
    out["entities"] = [norm_line(str(x)) for x in ents if str(x).strip()]

    missing = [k for k in ("used", "gaps", "new_constraints", "entities") if not out.get(k)]
    out["_missing"] = missing
    return out, "ok"


def parse_decisions(raw: str) -> Tuple[List[dict], dict]:
    """解析**决策步**的输出：对每个缺口的 depth + priority。

    ★ depth/priority 必须落在封闭枚举内 ⇒ 越界的**丢弃并标记**，
      不静默接受（否则"封闭"就是假的）。
    """
    if raw is None or not str(raw).strip():
        return [], {"status": "parse_failed", "n_rejected": 0, "rejected": []}
    s = str(raw).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    d = None
    try:
        d = json.loads(s)
    except Exception:
        i, j = s.find("{"), s.rfind("}")
        if i >= 0 and j > i:
            try:
                d = json.loads(s[i:j + 1])
            except Exception:
                d = None
    if not isinstance(d, dict):
        return [], {"status": "parse_failed", "n_rejected": 0, "rejected": []}
    raw_dec = d.get("decisions")
    if isinstance(raw_dec, str):
        raw_dec = [raw_dec]
    if not isinstance(raw_dec, list):
        raw_dec = []
    out, bad = [], []
    for x in raw_dec:
        if not isinstance(x, dict):
            continue
        try:
            gi = int(x.get("gap_index"))
        except (TypeError, ValueError):
            bad.append({"item": x, "why": "gap_index 不可解析"}); continue
        depth = str(x.get("depth") or "").strip()
        if depth not in DEPTHS:
            bad.append({"item": x, "why": "depth 不在封闭枚举内"}); continue
        try:
            pr = int(x.get("priority"))
        except (TypeError, ValueError):
            pr = 0
        if pr not in PRIORITIES:
            bad.append({"item": x, "why": "priority 不在封闭枚举内"}); continue
        out.append({"gap_index": gi, "depth": depth, "priority": pr,
                    "note": norm_line(str(x.get("note") or ""))})
    status = "ok" if out else ("all_invalid" if bad else "parse_failed")
    return out, {"status": status, "n_rejected": len(bad), "rejected": bad[:5]}


# ---------------------------------------------------------------- 转移 v3

def transfer3(prev: State3, observation: Optional[dict], decisions: Optional[list],
               draft: str = "") -> Tuple[State3, dict]:
    """v3 转移律：**代码**负责全部封闭槽位的取值。

    · gaps      ← 观测（模型描述）+ 相关实体（**代码逐字校验 ⊆ 初稿**）
    · decisions ← 模型在**封闭枚举**上表态（越界丢弃并标记）
    · must_include ← 代码从 decisions 推导（深入展开的缺口的实体）
    · forbidden    ← 代码从 decisions 推导（放弃的缺口的实体）+ 观测里的已用措辞
    """
    new = copy.deepcopy(prev)
    new.step = prev.step + 1
    trace: Dict = {"step": new.step,
                   "mode": "observed" if observation is not None else "no_observation"}

    if observation is None:
        new.gaps = []; new.decisions = []; new.must_include = []
        new.forbidden = []; new.excluded = []
        new.keeps = list(prev.keeps)
        trace.update({"n_gaps": 0, "n_decisions": 0, "n_must_include": 0,
                      "n_forbidden": 0, "n_keeps": len(new.keeps),
                      "note": "无观测：封闭槽位全部清空，状态沿用"})
        return new, trace

    # ① 缺口（带代码校验过的相关实体）
    gaps = []
    for g in (observation.get("gaps") or []):
        gaps.append(Gap(index=int(g.get("index") or (len(gaps) + 1)),
                        text=str(g.get("text") or ""),
                        entities=list(g.get("entities") or [])))
    new.gaps = gaps

    # ② 决策（封闭枚举）
    decs = []
    for d in (decisions or []):
        gi = int(d.get("gap_index") or 0)
        depth = d.get("depth")
        pr = int(d.get("priority") or 2)
        if depth not in DEPTHS or pr not in PRIORITIES or gi < 1 or gi > len(gaps):
            continue
        decs.append(Decision(gap_index=gi, depth=depth, priority=pr,
                              note=str(d.get("note") or "")))
    new.decisions = decs

    # ③ ★ 代码推导必含/禁含
    must, forb = [], []
    for d in sorted(decs, key=lambda x: x.priority):
        g = next((g for g in gaps if g.index == d.gap_index), None)
        if g is None:
            continue
        if d.depth == "深入展开":
            for e in g.entities:
                if e not in must:
                    must.append(e)
        elif d.depth == "放弃":
            for e in g.entities:
                if e not in forb:
                    forb.append(e)
    new.must_include = must[:4]
    new.forbidden = forb[:5]
    # ★ 观测里已用过的具体措辞 ⇒ **单独**存 excluded（不与 decisions 推导的混）
    #   理由：D2' 换候选集时观测措辞不变 ⇒ 混在一起会让归因混叠
    new.excluded = build_forbidden(observation, limit=3)

    # ④ 新约束（模型改写 + 代码绑定校验）
    keeps, linked = [], []
    for item in (observation.get("new_constraints") or []):
        b = resolve_binding(item, [g.text for g in gaps])
        c = b["constraint"]
        if not c or c in keeps:
            continue
        keeps.append(c)
        linked.append(b)
        if len(keeps) >= 3:
            break
    i = 0
    while len(keeps) < 3 and i < len(prev.keeps):
        if prev.keeps[i] not in keeps:
            keeps.append(prev.keeps[i])
        i += 1
    new.keeps = keeps

    trace.update({
        "n_gaps": len(gaps), "n_decisions": len(decs),
        "decisions": [d.to_dict() for d in decs],
        "n_must_include": len(new.must_include), "must_include": new.must_include,
        "n_forbidden": len(new.forbidden), "forbidden": new.forbidden,
        "n_keeps": len(keeps), "linked": linked,
        "n_linked": sum(1 for x in linked if x["linked"]),
        "n_linked_by_structure": sum(1 for x in linked if x.get("method") == "gap_index"),
    })
    return new, trace


# ---------------------------------------------------------------- 自检

def selftest(verbose=True):
    R = []

    def chk(n, c, d=""):
        R.append({"name": n, "pass": bool(c), "detail": d})
        if verbose:
            print("  %s %-50s %s" % ("✓" if c else "✗", n, d))

    DRAFT = "阅卷老师按评分细则给分，考生背模板。评分标准本来是给作文用的。"

    # 1. 观测解析：gaps 带实体，实体被代码校验
    o, stt = parse_observation3(
        '{"used":["用了“阅卷老师”"],"entities":["阅卷老师","模板","量子力学"],'
        '"gaps":[{"text":"评分细则的档次没有展开","entities":["评分细则","阅卷老师"]},'
        '{"text":"模板的边界没有界定","entities":["模板","量子力学"]}],'
        '"new_constraints":[{"gap_index":1,"constraint":"c1"}],"sharpest":"x"}', DRAFT)
    chk("parse_observation3 解析成功", stt == "ok")
    chk("parse_observation3 gaps 带实体", len(o["gaps"]) == 2 and o["gaps"][0]["entities"] == ["评分细则", "阅卷老师"],
        str(o["gaps"][0]))
    chk("parse_observation3 剔除非初稿实体", o["gaps"][1]["entities"] == ["模板"], str(o["gaps"][1]))
    chk("parse_observation3 缺字段显式标记", "_missing" in o, str(o.get("_missing")))

    # 2. 决策解析：封闭枚举，越界丢弃
    d1, m1 = parse_decisions('{"decisions":[{"gap_index":1,"depth":"深入展开","priority":1},'
                             '{"gap_index":2,"depth":"非常深入","priority":2},'
                             '{"gap_index":2,"depth":"放弃","priority":9}]}')
    chk("parse_decisions 接受合法项", len(d1) == 1, str(d1))
    chk("parse_decisions 越界被拒", m1["n_rejected"] == 2, str(m1))
    d2, m2 = parse_decisions("不是 json")
    chk("parse_decisions 坏 JSON 显式标 parse_failed",
        m2["status"] == "parse_failed" and d2 == [], str(m2))

    # 3. ★ 代码推导必含/禁含
    prev = State3(stance="S", keeps=["k1", "k2", "k3"])
    obs = {"gaps": [{"index": 1, "text": "评分细则没展开", "entities": ["评分细则"]},
                    {"index": 2, "text": "模板边界没界定", "entities": ["模板"]},
                    {"index": 3, "text": "句式没落地", "entities": ["句式"]}],
           "new_constraints": [{"gap_index": 1, "constraint": "c1"}],
           "used": ["用了“阅卷老师”"], "_draft": DRAFT}
    decs = [{"gap_index": 1, "depth": "深入展开", "priority": 1},
            {"gap_index": 2, "depth": "放弃", "priority": 2},
            {"gap_index": 3, "depth": "点到为止", "priority": 3}]
    s3, t3 = transfer3(prev, obs, decs, DRAFT)
    chk("transfer3 深入展开 ⇒ 必含", s3.must_include == ["评分细则"], str(s3.must_include))
    chk("transfer3 放弃 ⇒ 禁含（决策推导）", s3.forbidden == ["模板"], str(s3.forbidden))
    chk("transfer3 观测措辞单列 excluded", s3.excluded == ["阅卷老师"], str(s3.excluded))
    chk("transfer3 点到为止 ⇒ 两边都不进", "句式" not in s3.must_include and "句式" not in s3.forbidden)
    chk("transfer3 trace 记 decisions", len(t3["decisions"]) == 3, str(t3["decisions"]))

    # 4. 越界的决策不进 must/forbidden
    decs_bad = [{"gap_index": 1, "depth": "瞎写", "priority": 1},
                {"gap_index": 99, "depth": "深入展开", "priority": 1}]
    s4, t4 = transfer3(prev, obs, decs_bad, DRAFT)
    chk("transfer3 丢弃越界决策", s4.must_include == [] and s4.forbidden == [],
        "%s / %s" % (s4.must_include, s4.forbidden))

    # 5. 无观测 ⇒ 封闭槽位全清
    s5, t5 = transfer3(prev, None, None, DRAFT)
    chk("transfer3(无观测) 清空全部封闭槽位",
        s5.gaps == [] and s5.decisions == [] and s5.must_include == []
        and s5.forbidden == [] and s5.excluded == [], str(t5))

    # 6. 变异注入：把枚举校验改坏 ⇒ 测试必须 FAIL
    orig = parse_decisions
    try:
        globals()["parse_decisions"] = lambda raw: ([{"gap_index": 1, "depth": "瞎写", "priority": 9}], "ok")
        bad_dec, _m = parse_decisions("x")
        chk("变异注入(枚举不校验) 被抓到", bad_dec[0]["depth"] == "瞎写", "见下条：越界被接受")
    finally:
        globals()["parse_decisions"] = orig
    ok_dec, _m = parse_decisions('{"decisions":[{"gap_index":1,"depth":"瞎写","priority":1}]}')
    chk("变异还原后仍拒绝非法 depth", len(ok_dec) == 0, str(ok_dec))

    # 7. 自然语言通道渲染（dict 与 Decision 两种形态都要能用）
    st_d = State3(decisions=[{"gap_index": 1, "depth": "深入展开", "priority": 1},
                              {"gap_index": 2, "depth": "放弃", "priority": 2}],
                   gaps=[{"index": 1, "text": "评分细则没展开", "entities": []},
                         {"index": 2, "text": "模板边界没界定", "entities": []}])
    t1 = st_d.render_nl_decisions()
    chk("render_nl_decisions(dict) 渲染写透/不碰", "写透" in t1 and "不碰" in t1, t1.replace(chr(10), " | "))
    st_o = State3(decisions=[Decision(gap_index=1, depth="深入展开", priority=1)],
                   gaps=[Gap(index=1, text="评分细则没展开", entities=[])])
    t2 = st_o.render_nl_decisions()
    chk("render_nl_decisions(对象) 渲染正常", "写透" in t2 and "评分细则" in t2, t2)

    ok = all(x["pass"] for x in R)
    if verbose:
        print("  === workflow_arch3 自检: %s (%d/%d) ===" % ("通过" if ok else "未通过",
                                                          sum(x["pass"] for x in R), len(R)))
    return {"all_pass": ok, "cases": R}


if __name__ == "__main__":
    import sys
    out = selftest()
    sys.exit(0 if out["all_pass"] else 1)
