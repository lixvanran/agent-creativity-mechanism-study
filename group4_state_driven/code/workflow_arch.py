#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 架构化状态机（arch）

════════════════════════════════════════════════════════════════════════
★ 为什么有这个模块
  `run_minimal_compare.py` 里的 "WF" 臂，**不是架构，是提示词**：
  转移律（"第一段写未落地 / 第二段恰好 3 行约束 / 第三段恰好 2 行已排除"）
  是硬编码在 `F_SYS` / `G_SYS` 提示词模板里的。
  ⇒ 它能不能工作，取决于模型**自觉遵守格式**；
     格式一崩就静默降级（上一轮实测：解析器把"未落地"诊断段当成了写作约束）。
  ⇒ 这是"预制提示词"路线：题面特殊性被写进了提示词，**过拟合风险高**。

  本模块把状态机**搬进代码**：
  · 状态 = `State` 数据结构（字段固定、类型明确、序列化稳定）
  · 转移律 = `transfer(prev, observation)` **函数**
      - `observation` 是**显式参数** ⇒ 天然可做置换探针 / 消融（no-observation）
      - 「已排除」由**代码从模型对初稿的描述中机械抽取**（模型不负责自述已排除）
      - 「新约束」由代码**强制绑定到观测缺口**（gap → constraint 的链路在代码里）
  · 提示词只负责"描述事实"，不负责"格式纪律"和"转移逻辑"

════════════════════════════════════════════════════════════════════════
★ 铁律落地
  1. 判据/解析先自检：`selftest()` 必须先证明自己能抓到东西（正例 + 反例 + 变异）
  2. 解析失败**显式标记**（`parse_failed`），不静默回退
  3. 比率必配绝对分母
  4. 状态机**不依赖被测模型同源**：全部走 OpenRouter，模型可换
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------- 状态

@dataclass
class State:
    """状态 = 代码里的对象。字段固定 ⇒ 可差分、可序列化、可做单元测试。"""
    stance: str = ""                       # 立场（一个可被反驳的判断）
    keeps: List[str] = field(default_factory=list)   # 不能牺牲的取舍（3 条）
    slip: str = ""                         # 最容易失守的地方
    first: str = ""                        # 第一次反应
    excluded: List[str] = field(default_factory=list)  # 已排除的路（只有看过产出后才存在）
    gaps: List[str] = field(default_factory=list)      # 缺口：哪些取舍还没落地
    step: int = 0                          # 状态转移次数
    polarity: str = "default"             # default | reversed（反极性臂）

    def to_dict(self) -> dict:
        return asdict(self)

    def render_keeps(self) -> str:
        return "\n".join("· " + k for k in self.keeps)

    def render_excluded(self) -> str:
        return "\n".join("· " + k for k in self.excluded)


# ---------------------------------------------------------------- 文本工具

_CJK = re.compile(r"[一-鿿]")
_STOP = set("的了是在和与也就都而及其之或一个这那我你他她它们不很更最我我们这那什么怎么"
            "哪些因为所以但是而且如果就是可以能够需要应该没有这个那个一种一些对于关于")


def ngrams(text: str, n: int = 2) -> set:
    """中文取字符 2-gram；英文取 word。用于轻量关联度（零成本、可复现）。"""
    t = (text or "").strip()
    if not t:
        return set()
    if _CJK.search(t):
        cs = [c for c in t if not c.isspace()]
        return set("".join(cs[i:i + n]) for i in range(len(cs) - n + 1))
    ws = re.findall(r"[a-zA-Z]{3,}", t.lower())
    return set(ws)


def jaccard(a: str, b: str) -> float:
    A, B = ngrams(a), ngrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def norm_line(s: str) -> str:
    s = re.sub(r"^\s*(?:[0-9]+[.、)）]|[-*•·]|第[一二三四五六七八九十]+[段条]?[：:]?)\s*", "", s or "")
    return s.strip()


# ---------------------------------------------------------------- 机械抽取

#: 「初稿里已被用过的措辞」→ 排除项。**纯代码，不问模型"你排除了什么"。**
_EXCLUDE_PREFIX = "不要再出现："

#: 观测字段里，具体措辞最可能藏在这些标记里
_QUOTE_RE = re.compile(r"[「」『』“”\"']([^「」『』“”\"']{1,40})[「」『』“”\"']")


def build_excluded(observation: dict, limit: int = 3) -> List[str]:
    """从"模型对初稿的客观描述"里**机械抽取**已用过的措辞 → 排除项。

    ★ 这里不做任何语义判断：模型说初稿里已经出现过"X"，代码就转成
      "不要再出现：X"。**"已排除"因此在结构上依赖观测**，
      而不是靠提示词请求模型自己写一段"已排除"。
    """
    out: List[str] = []
    used = observation.get("used") or []
    if isinstance(used, str):
        used = [used]
    for item in used:
        if not isinstance(item, str):
            item = str(item)
        item = item.strip()
        if not item:
            continue
        # ① 先剥"初稿已经用过"这类前缀
        t = re.sub(r"^(?:初稿|上文|这篇|文章|正文)?(?:里|中)?(?:已经)?"
                   r"(?:用过|用了|出现(?:过)?|写(?:过|了)|反复(?:使用|出现)|大量使用)"
                   r"[了]?[:：]?\s*", "", item).strip() or item
        # ② 再取引号里的具体措辞（最短、最可核验）
        cands = [c.strip() for c in _QUOTE_RE.findall(t) if c.strip()]
        if cands:
            pick = sorted(set(cands), key=len)[0]
        else:
            pick = t
        if pick and len(pick) <= 80:
            e = _EXCLUDE_PREFIX + pick
            if e not in out:
                out.append(e)
        if len(out) >= limit:
            break
    return out


def link_check(constraint: str, gaps: List[str]) -> Tuple[bool, float, str]:
    """新约束是否**真的**绑在某个观测缺口上？

    返回 (linked, score, 绑定到的 gap)。
    ★ 这是零成本的结构校验：若模型只是把上一轮的取舍换个说法复述，
      它与 gap 的关联度会低 ⇒ 标记 `unlinked` ⇒ **显式暴露**，不静默。

    ⚠️ **实测教训（2026-10-21）**：字面 2-gram Jaccard **有假阴性**。
      模型写的约束常明写"对应第一个缺口"，语义上明确绑定，
      但措辞不同 ⇒ score 只有 0.03–0.15 ⇒ 布尔阈值会乱切。
      ⇒ 绑定判据**必须以结构声明为准**（`gap_index`），
        字面相似度只能当**辅助信号**，不能当判据。
    """
    best, bi = 0.0, ""
    for g in gaps:
        s = jaccard(constraint, g)
        if s > best:
            best, bi = s, g
    return (best >= 0.06), round(best, 4), bi


def resolve_binding(item, gaps: List[str]) -> dict:
    """解析一条新约束与缺口之间的绑定关系。

    item 可以是：
      · {"gap_index": 2, "constraint": "..."}  ⇒ **结构声明**（首选）
      · "..."（纯字符串）                     ⇒ 退回字面相似度（辅助信号）

    返回 {"constraint","linked","score","gap","method"}。
    ★ method 会被记进 trace ⇒ 读者能看出有多少绑定是"声明的"、多少是"猜的"。
    """
    if isinstance(item, dict):
        c = norm_line(str(item.get("constraint") or item.get("text") or ""))
        gi = item.get("gap_index")
        try:
            gi = int(gi) if gi is not None else None
        except (TypeError, ValueError):
            gi = None
        if c and gi is not None and 1 <= gi <= len(gaps):
            return {"constraint": c, "linked": True, "score": None,
                    "gap": gaps[gi - 1], "method": "gap_index", "gap_index": gi}
        if c:
            ok, sc, g = link_check(c, gaps)
            return {"constraint": c, "linked": ok, "score": sc, "gap": g,
                    "method": "lexical_fallback", "gap_index": None}
        return {"constraint": "", "linked": False, "score": None, "gap": "",
                "method": "empty", "gap_index": None}
    c = norm_line(str(item))
    if not c:
        return {"constraint": "", "linked": False, "score": None, "gap": "",
                "method": "empty", "gap_index": None}
    ok, sc, g = link_check(c, gaps)
    return {"constraint": c, "linked": ok, "score": sc, "gap": g,
            "method": "lexical_fallback", "gap_index": None}


# ---------------------------------------------------------------- 转移律

def transfer(prev: State,
             observation: Optional[dict],
             rewriter: Optional[Callable[[List[str], State, List[str]], List[str]]] = None
             ) -> Tuple[State, dict]:
    """状态转移律。**纯函数**（rewriter 注入）⇒ 可用假实现做单元测试。

    observation is None ⇒ **消融模式**：没有观测就没有"已排除"、没有新约束，
    状态只能沿用。⇒ "状态依赖观测"由**代码**保证，不是提示词祈祷。

    返回 (new_state, trace)。trace 记录本步做了什么，用于事后审计。
    """
    new = copy.deepcopy(prev)
    new.step = prev.step + 1
    trace: Dict = {"step": new.step, "mode": "observed" if observation is not None else "no_observation"}

    if observation is None:
        new.gaps = []
        new.excluded = []
        new.keeps = list(prev.keeps)
        trace.update({"n_gaps": 0, "n_excluded": 0, "n_keeps": len(new.keeps),
                      "linked": [], "note": "无观测：状态沿用，不产生新约束/已排除"})
        return new, trace

    # ① 缺口：来自模型对初稿的客观描述
    gaps = observation.get("gaps") or []
    if isinstance(gaps, str):
        gaps = [gaps]
    gaps = [norm_line(g) for g in gaps if isinstance(g, str) and norm_line(g)]
    new.gaps = gaps[:4]

    # ② 已排除：**代码机械抽取**（模型不负责自述）
    new.excluded = build_excluded(observation, limit=3)

    # ③ 新约束：由 gap 触发，模型改写，代码做绑定校验
    if gaps and rewriter is not None:
        cand = rewriter(gaps, prev, new.excluded)
    else:
        # ★ fallback **不用 gap 原文**（否则绑定校验自我循环、指标失真）
        cand = []
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
    # 补齐：不足 3 条时，代码用"沿用上一轮"补（**显式标注来源**）
    filler_src = []
    i = 0
    while len(keeps) < 3 and i < len(prev.keeps):
        if prev.keeps[i] not in keeps:
            keeps.append(prev.keeps[i])
            filler_src.append(prev.keeps[i])
        i += 1
    new.keeps = keeps

    n_struct = sum(1 for x in linked if x.get("method") == "gap_index")
    trace.update({
        "no_new_constraints": (len(cand) == 0),
        "n_gaps": len(gaps), "n_excluded": len(new.excluded),
        "n_keeps": len(keeps),
        "linked": linked,
        "n_linked": sum(1 for x in linked if x["linked"]),
        "n_linked_by_structure": n_struct,      # ★ 结构声明的绑定数
        "n_linked_by_lexical": sum(1 for x in linked if x.get("method") == "lexical_fallback" and x["linked"]),
        "n_binding_unknown": sum(1 for x in linked if x.get("method") == "lexical_fallback" and not x["linked"]),
        "filler_from_prev": filler_src,
    })
    return new, trace


def state_diff(a: State, b: State) -> dict:
    """两个状态的结构化差分（置换探针的读数基础）。"""
    def as_set(xs):
        return {norm_line(x) for x in (xs or []) if norm_line(x)}
    ka, kb = as_set(a.keeps), as_set(b.keeps)
    ea, eb = as_set(a.excluded), as_set(b.excluded)
    inter = len(ka & kb)
    union = len(ka | kb) or 1
    return {
        "keep_jaccard": round(inter / union, 4),
        "keep_changed": sorted(ka - kb),
        "keep_added": sorted(kb - ka),
        "excluded_jaccard": round(len(ea & eb) / (len(ea | eb) or 1), 4),
        "excluded_changed": sorted(ea - eb),
        "excluded_added": sorted(eb - ea),
        "stance_same": (a.stance.strip() == b.stance.strip()),
        "step": [a.step, b.step],
    }


# ---------------------------------------------------------------- 解析

def parse_observation(raw: str) -> Tuple[Optional[dict], str]:
    """解析观测步的 JSON。**失败必须显式标记**，不静默回退。

    返回 (obs, status)；status ∈ {ok, parse_failed}
    """
    if raw is None or not str(raw).strip():
        return None, "parse_failed"
    s = str(raw).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    try:
        d = json.loads(s)
    except Exception:
        d = None
        # 宽松：截到最后一个完整的 } 或 ]
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
                            d = json.loads(s[i:j + 1])
                            break
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
    # ★ new_constraints 特殊：可以是 list[dict{gap_index, constraint}]（**结构声明**）
    #   也可以是 list[str]（退回字面相似度）。两种都保留，不丢信息。
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
    # ★ 显式记录缺字段（不静默）：new_constraints 缺了 ⇒ 上层会退化成"直接用 gap"
    missing = [k for k in ("used", "gaps", "new_constraints") if not out.get(k)]
    out["_missing"] = missing
    return out, "ok"


# ---------------------------------------------------------------- 自检
# ★ 铁律一：检查器必须先证明自己能抓到东西（正例 + 反例 + 变异注入）

def selftest(verbose: bool = True) -> dict:
    R = []

    def chk(name, cond, detail=""):
        R.append({"name": name, "pass": bool(cond), "detail": detail})
        if verbose:
            print("  %s %-42s %s" % ("✓" if cond else "✗", name, detail))

    # 1. build_excluded：能从描述里抽出具体措辞
    obs = {"used": ["初稿里已经用过“伪写作”这种说法", "文中反复出现“系统化”"]}
    ex = build_excluded(obs)
    chk("build_excluded 抽出引号内措辞",
        any("伪写作" in e for e in ex) and any("系统化" in e for e in ex), str(ex))
    chk("build_excluded 输出带排除前缀", all(e.startswith(_EXCLUDE_PREFIX) for e in ex))

    # 2. 反例：没有措辞时不应凭空造排除项
    ex2 = build_excluded({"used": []})
    chk("build_excluded 空输入不造假", ex2 == [], str(ex2))

    # 3. 转移律：有观测 ⇒ 产生 excluded；无观测 ⇒ 绝不产生
    prev = State(stance="S", keeps=["k1", "k2", "k3"])
    s1, t1 = transfer(prev, {"used": ["用过“甲”"], "gaps": ["第二段没有回应取舍"]},
                      rewriter=lambda gaps, p, e: ["要让第二段真正回应取舍"])
    chk("transfer(有观测) 产生 excluded", len(s1.excluded) > 0, str(s1.excluded))
    chk("transfer(有观测) 产生新约束", s1.keeps[0] != "k1", str(s1.keeps))
    chk("transfer(有观测) trace 记 n_linked", "n_linked" in t1)

    s2, t2 = transfer(prev, None, rewriter=lambda g, p, e: ["x"])
    chk("transfer(无观测) 不产生 excluded", s2.excluded == [], str(s2.excluded))
    chk("transfer(无观测) 不产生新约束", s2.keeps == prev.keeps, str(s2.keeps))
    chk("transfer(无观测) mode 正确", t2["mode"] == "no_observation")

    # 4. 链接校验：复述上一轮 ⇒ 判 unlinked；真正改写 ⇒ linked
    ok_rep, sc_rep, _ = link_check("要让第二段真正回应取舍", ["第二段没有回应取舍"])
    ok_fake, sc_fake, _ = link_check("写得更有文采一些", ["第二段没有回应取舍"])
    chk("link_check 认得出真绑定", ok_rep, "score=%s" % sc_rep)
    chk("link_check 认得出复述/无关", not ok_fake, "score=%s" % sc_fake)

    # 5. 解析：好 JSON / 坏 JSON / 空
    o1, st1 = parse_observation('{"used":["a"],"gaps":["b"],"new_constraints":["c"],"sharpest":"d"}')
    chk("parse_observation 解析正常 JSON", st1 == "ok" and o1["gaps"] == ["b"])
    chk("parse_observation 取到 new_constraints", o1["new_constraints"] == ["c"], str(o1.get("new_constraints")))
    chk("parse_observation 缺字段被显式记录",
        parse_observation('{"used":["a"]}')[0]["_missing"] == ["gaps", "new_constraints"],
        str(parse_observation('{"used":["a"]}')[0]["_missing"]))
    # 5b. 结构声明的绑定（gap_index）
    o1b, _ = parse_observation('{"used":["a"],"gaps":["g1","g2"],'
                               '"new_constraints":[{"gap_index":2,"constraint":"c2"}]}')
    chk("parse_observation 保留 gap_index 结构声明",
        o1b["new_constraints"] == [{"constraint": "c2", "gap_index": 2}],
        str(o1b["new_constraints"]))
    b1 = resolve_binding(o1b["new_constraints"][0], o1b["gaps"])
    chk("resolve_binding 用结构声明判定", b1["linked"] and b1["method"] == "gap_index"
        and b1["gap"] == "g2", str(b1))
    b2 = resolve_binding({"constraint": "完全不同的话", "gap_index": 9}, ["g1"])
    chk("resolve_binding 越界 gap_index 退回字面", b2["method"] == "lexical_fallback", str(b2))
    b3 = resolve_binding("纯字符串约束", ["g1"])
    chk("resolve_binding 纯字符串走字面", b3["method"] == "lexical_fallback", str(b3))
    o2, st2 = parse_observation("这不是 JSON")
    chk("parse_observation 坏 JSON 显式标 parse_failed", st2 == "parse_failed", str(o2))
    o3, st3 = parse_observation("")
    chk("parse_observation 空输入显式标 parse_failed", st3 == "parse_failed")

    # 6. 变异注入：把 build_excluded 改坏 ⇒ 测试必须 FAIL（证明测试不是摆设）
    orig = build_excluded
    try:
        globals()["build_excluded"] = lambda observation, limit=3: []   # 变异
        s3, _ = transfer(prev, {"used": ["用过“甲”"], "gaps": ["g"]},
                         rewriter=lambda g, p, e: ["y"])
        chk("变异注入(抽不出excluded) 被测试抓到", len(s3.excluded) == 0)
    finally:
        globals()["build_excluded"] = orig
    s4, _ = transfer(prev, {"used": ["用过“甲”"], "gaps": ["g"]},
                     rewriter=lambda g, p, e: ["y"])
    chk("变异还原后恢复正常", len(s4.excluded) > 0)

    # 7. state_diff
    d = state_diff(s1, s2)
    chk("state_diff 能测出 keep 变化", d["keep_jaccard"] < 1.0, "j=%.3f" % d["keep_jaccard"])
    chk("state_diff 能测出 excluded 变化", d["excluded_jaccard"] < 1.0)

    ok = all(x["pass"] for x in R)
    if verbose:
        print("  === workflow_arch 自检: %s (%d/%d) ===" %
              ("通过" if ok else "未通过", sum(x["pass"] for x in R), len(R)))
    return {"all_pass": ok, "cases": R}


if __name__ == "__main__":
    import sys
    out = selftest()
    sys.exit(0 if out["all_pass"] else 1)
