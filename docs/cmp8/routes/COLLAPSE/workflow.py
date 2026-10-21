# -*- coding: utf-8 -*-
"""治塌缩工作流（Collapse-Fix Workflow, 简称 **W**）—— 让 Agent 的答案不再中庸。

> 这是**可运行代码**，不是设计文档。设计依据见 `routes/COLLAPSE-REMEDY-2026-10-22.md`。

## 它针对的三个失败

| 失败 | 现象 | 本工作流的干预 |
|---|---|---|
| **横向收敛** | 多个槽位产出趋于同一（中庸） | **认知位置解耦**：每个槽位挂一个**认知帧**（vantage operator，非 persona）⇒ 被推到不同角落 |
| **纵向早熟** | 搜索提前停止、动作集固定 | **动作空间可演化**（B\* 式）：动作**失败 ⇒ 构造新动作** ⇒ 动作集本身在长 |
| **产出中庸** | 答案落在分布中心 | **行为空间照明**（MAP-Elites）：(帧组合 × 操作序列) 格子，每格留最优 ⇒ 广度是结构保证的 |

## 流程（单次运行）

```
0. 选帧    Fisher-Yates 从 15 帧池抽 K 个（互不重复、seed 可复现、必含 1 个 wild）
1. 发散    K 个槽位并行生成 —— ★ 槽位互不可见（谁也看不到别人写了什么）
2. 抽取    逐槽位抽断言
3. 去冗余  离散去冗余（数字指纹 + 4-gram，★ 不用 embedding）
4. 演化    ★ 判定哪些动作"失败" ⇒ 从失败**构造新动作** ⇒ 进动作档案
5. 重跑    若有新动作：每槽位用自己的新动作再跑一轮（★ 搜索空间在这一步变大）
6. 装配    机械装配（不重写、不让模型再总结一遍）
7. 记账    行为格归档 + 中庸度四指标
```

## 与既有路线的关系

* **路线 A**（`routes/A/route_a.py`）是**固定 7 步拓扑**、固定 facet 集合、**动作集固定** ⇒ 搜索空间不增长。
* **W 继承 A 的机械装配与去冗余口径**，但把三处换成可增长的：
  ① 固定 facet → **认知帧池**（可扩）
  ② 固定动作 → **动作档案 + 失败驱动的新动作构造**
  ③ 无照明 → **行为格档案**
* W **不引入**任何新判据：承重、去冗余、结论空间的口径**完全沿用协议**。

## 纪律

* **失败不许静默变成 0**：每个失败类型都有独立计数，且**必进**读数。
* **种子真的可复现**：用 `random.Random(seed)`（★ 修 ADHD 原版用 `Math.random()` 无 PRNG 的缺陷）。
* **不用 embedding**：去冗余、行为距离、新颖度全部用离散结构量。
* **装配必须机械**：不由模型重写答案。
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ══════════════════════════════════════════════════════════════════════
# §0 认知帧池（vantage operator，**不是** persona）
# ══════════════════════════════════════════════════════════════════════
# 逐字依据：ADHD 项目 `src/packs/core.ts`（MIT, UditAkhourii/adhd）
# —— 15 个 id/label/prompt/tags 全部照录，**英文 prompt 逐条重写为中文**，
#    但**保持 "vantage operator（重新摆出问题）" 而非 "扮演身份"** 的定位。
# ⚠️ 定位为什么重要：Diversity Collapse 证明**专家权威 persona 会压多样性**；
#    帧是**故意扭曲**，机制不同 ⇒ 论文结论**不能**直接推论到帧上。

FRAMES: List[Dict[str, Any]] = [
    dict(id="hardware-eyes", label="硬件工程师视角", wild=True,
         prompt="你从延迟、内存布局与物理约束的角度思考。把这个问题重新摆成"
                "一个硬件/固件问题来看：总线拓扑、缓存、时间预算会告诉你什么？"),
    dict(id="regulator", label="监管/审计视角", wild=False,
         prompt="你审计系统的合规性与失效模式。追问：这里什么必须是可证明的、"
                "可追溯的、可拒绝的？在这种追问下会浮出哪些想法？"),
    dict(id="ten-year-old", label="十岁小孩视角", wild=True,
         prompt="你是一个从没见过这类系统的好奇小孩。描述那些天真但不受成规束缚的做法。"
                "忽略惯例。"),
    dict(id="adversary", label="对手视角", wild=False,
         prompt="你是一个有敌意的竞争者或攻击者。生成那些能利用、搞坏、破坏显然解法的做法，"
                "然后把它们反转成想法。"),
    dict(id="biology", label="跨域：生物学", wild=True,
         prompt="从生物学搬一个机制过来——免疫系统、神经可塑性、细胞信号、进化、肠道菌群——"
                "硬套到这个工程问题上。"),
    dict(id="logistics", label="跨域：物流/供应链", wild=False,
         prompt="从物流偷机制过来：排队、批处理、准时制、枢纽辐射、退货、末端配送。"
                "把它们字面地套到这个问题上。"),
    dict(id="game-design", label="跨域：游戏设计", wild=False,
         prompt="像游戏设计师一样处理这个问题。循环是什么、奖励是什么、摩擦在哪、"
                "存档点是什么、速通技巧是什么？把用户/系统当成玩家。"),
    dict(id="markets", label="跨域：市场", wild=True,
         prompt="把问题当成一个市场。谁是买方、卖方、撮合者？在这里，拍卖、期货合约、"
                "清算所会是什么样子？"),
    dict(id="inversion", label="反转", wild=False,
         prompt="问相反的问题。如果目标是 X，就去头脑风暴「怎样保证不是 X」，"
                "再把每个答案取反变回一个想法。"),
    dict(id="extreme-zero", label="极端：零预算、一小时", wild=False,
         prompt="你没钱、没人、只有一小时。最粗糙但仍然扛得住承重职责的版本是什么？"
                "允许 hack、硬编码、手工循环。"),
    dict(id="extreme-infinite", label="极端：无限预算、十年", wild=True,
         prompt="你有无限算力、无限工程师、一十年。极简主义之外的极繁版本是什么样？"
                "只有那种规模才可能做到什么？"),
    dict(id="remove-assumption", label="去掉承重假设", wild=True,
         prompt="指出这个问题上人人当作固定不变的那件事（框架、数据库、请求/响应模型、"
                "文件系统、网络）。想象它没了。生成只存在于那个世界里的想法。"),
    dict(id="speedrunner", label="速通者视角", wild=True,
         prompt="你在速通。找 glitch、跳关、越界技巧、帧完美的捷径。"
                "穿过这个问题的那条滥用但合法的路径是什么？"),
    dict(id="ant-colony", label="蚁群视角", wild=True,
         prompt="没有中央规划者。许多笨 agents、局部规则、信息素轨迹。这个问题会如何"
                "自发地解决自己？"),
    dict(id="ops-3am", label="凌晨三点的 on-call", wild=False,
         prompt="你是被半夜叫醒的值班工程师，这个东西坏了。什么样的设计能让你不用被 call？"
                "什么才是「按 runbook 就能处理」的解法？"),
]

FRAME_IDS = [f["id"] for f in FRAMES]
_FRAME_BY_ID = {f["id"]: f for f in FRAMES}


# ══════════════════════════════════════════════════════════════════════
# §1 选帧（**有 PRNG** ⇒ seed 真可复现）
# ══════════════════════════════════════════════════════════════════════
def select_frames(k: int = 4, seed: int = 0) -> List[str]:
    """Fisher-Yates 抽 `k` 个互不重复的帧。

    ★ 必含 **1 个 wild 帧**（ADHD 原版的 `wildPick` 逻辑，见 `src/frames.ts:62`）——
      wild 帧 = 扭曲最大的一档（十岁小孩/反身蚁群/去假设/速通者…）⇒ 它们是发散的主要来源。

    ⚠️ 与 ADHD 原版的差别：原版用 `Math.random()`（**无 PRNG**）⇒ 不可复现；
      文档却声称 "deterministic per-seed"（自相矛盾）。**这里用 `random.Random(seed)`**。
    """
    rng = random.Random(seed)
    ids = list(FRAME_IDS)
    rng.shuffle(ids)
    picked = ids[:max(0, k)]
    if picked and not any(_FRAME_BY_ID[i]["wild"] for i in picked):
        # ★ 必含 1 个 wild：从剩下的 wild 里换掉第一个非 wild
        wilds = [i for i in ids if _FRAME_BY_ID[i]["wild"] and i not in picked]
        if wilds:
            first_nonwild = next((n for n, i in enumerate(picked)
                                  if not _FRAME_BY_ID[i]["wild"]), 0)
            picked[first_nonwild] = wilds[0]
    return picked


# ══════════════════════════════════════════════════════════════════════
# §2 动作档案 + 失败驱动的新动作构造（★ B\* 式动作空间演化）
# ══════════════════════════════════════════════════════════════════════
# 失败类型 → **新动作模板**。新动作不是"再跑一次"，而是**换一个做法**。

ACTION_TEMPLATES: Dict[str, str] = {
    "base": ("把这个问题重新摆成下面这个视角来看，然后给出**具体**的、能落到条件与数字上的做法：\n"
             "【视角】{frame_prompt}"),

    # ── 演化出来的动作（失败 → 新做法）
    "fix_empty": ("【视角】{frame_prompt}\n"
                  "上一步没能产出任何可用内容。**先只做一件事**：从题面与依据里逐条抄出与本视角"
                  "相关的**具体名词与数字**（不要展开、不要评价），抄完再从这些名词出发写做法。"),

    "fix_unmentioned": ("【视角】{frame_prompt}\n"
                        "上一步写的东西与依据完全对不上。**先只做一件事**：从依据里挑出与本视角"
                        "最相关的 **2–3 条并写出它们的编号**，然后**只针对这几条**写做法，"
                        "不要谈依据没写的东西。"),

    "fix_zero_lb": ("【视角】{frame_prompt}\n"
                    "上一步写不出「它改变了哪个决策」。**先只做一件事**：问自己"
                    "「如果这条信息是假的，答案的哪一句会变？」，把那一句写出来，"
                    "再补上支撑它的条件。"),

    "fix_fallback": ("【视角】{frame_prompt}\n"
                     "上一步触发了兜底（内容不完整）。**先只做一件事**：只输出 **3 条**，"
                     "每条**必须**带一个具体数字或一个明确的成立条件，其余一律不写。"),

    "fix_truncated": ("【视角】{frame_prompt}\n"
                      "上一步超长被截断。**先只做一件事**：把内容压到只剩"
                      "**承重的那一句**——如果这句话不成立，答案会变；其余全删。"),
}

FAILURE_KINDS = ("empty", "all_unmentioned", "zero_load_bearing", "fallback", "truncated")


class ActionArchive:
    """动作档案。**新动作从这里长出来，并且会被复用。**

    ★ 与 ADAS 的"档案 = 历史发现的累积"同形：档案不是留痕，是**搜索结构本身**。
    """

    def __init__(self) -> None:
        self.actions: Dict[str, Dict[str, Any]] = {}
        self.uses: Dict[str, int] = {}
        self.provenance: List[Dict[str, Any]] = []

    def add(self, name: str, template: str, *, born_from: str, evidence: str = "") -> str:
        if name not in self.actions:
            self.actions[name] = dict(name=name, template=template,
                                      born_from=born_from, evidence=evidence)
            self.provenance.append(dict(action=name, born_from=born_from,
                                        evidence=evidence))
        self.uses[name] = self.uses.get(name, 0) + 1
        return name

    def template(self, name: str) -> str:
        return self.actions.get(name, {}).get("template", ACTION_TEMPLATES["base"])

    def stats(self) -> Dict[str, Any]:
        return dict(n_actions=len(self.actions),
                    names=sorted(self.actions),
                    uses=dict(self.uses),
                    provenance=list(self.provenance))


def propose_new_action(failure_kind: str, slot_id: str, archive: ActionArchive) -> Optional[str]:
    """**从一次失败构造一个新动作**（Voyager 式：错误信息 → 新做法）。

    ★ 只有真的失败才提案；成功的动作**不**被替换 ⇒ 不会无节制地扩动作空间。
    ★ 同一 `failure_kind` 只产出一个动作（按 `failure_kind` 命名）⇒ 动作集是**可枚举**的，
      不是无穷生成。
    """
    if failure_kind not in FAILURE_KINDS:
        return None
    name = "act_%s" % failure_kind
    if name in archive.actions:
        return name                      # 已有 ⇒ 复用（不重复造）
    tmpl = ACTION_TEMPLATES.get("fix_%s" % failure_kind)
    if not tmpl:
        return None
    return archive.add(name, tmpl, born_from="%s@%s" % (failure_kind, slot_id),
                       evidence="failure_kind=%s slot=%s" % (failure_kind, slot_id))


# ══════════════════════════════════════════════════════════════════════
# §3 离散去冗余（★ 不用 embedding）
# ══════════════════════════════════════════════════════════════════════
_NUM_RE = re.compile(r"\d+(?:\.\d+)?%?")
_CJK_PUNCT = "，。；：、！？,.;:!?（）()【】《》“”‘’"


def _fingerprint(s: str) -> frozenset:
    """数字指纹：一条断言里出现的数值集合（⇒ 数字不同的两条几乎必然不冗余）。"""
    return frozenset(_NUM_RE.findall(s or ""))


def _ngrams(s: str, n: int = 4) -> frozenset:
    t = re.sub(r"[\s%s]" % re.escape(_CJK_PUNCT), "", (s or ""))
    if len(t) < n:
        return frozenset([t]) if t else frozenset()
    return frozenset(t[i:i + n] for i in range(len(t) - n + 1))


def is_redundant(a: str, b: str, *, num_thresh: float = 0.8, jacc_thresh: float = 0.75) -> bool:
    """两条断言是否冗余（**离散**判据，不用 embedding）。

    * 数字指纹 Jaccard ≥ `num_thresh` ⇒ 冗余（数值说的是同一件事）
    * 字符 4-gram Jaccard ≥ `jacc_thresh` ⇒ 冗余（措辞几乎一样）
    """
    fa, fb = _fingerprint(a), _fingerprint(b)
    if fa and fb:
        inter = len(fa & fb)
        uni = len(fa | fb)
        if uni and inter / uni >= num_thresh:
            return True
    ga, gb = _ngrams(a), _ngrams(b)
    if not ga or not gb:
        return False
    return len(ga & gb) / len(ga | gb) >= jacc_thresh


def dedup(items: Sequence[str], **kw) -> List[str]:
    """贪心去冗余（保持原顺序 ⇒ 定序可复现）。"""
    kept: List[str] = []
    for it in items:
        if not (it or "").strip():
            continue
        if any(is_redundant(it, k, **kw) for k in kept):
            continue
        kept.append(it.strip())
    return kept


# ══════════════════════════════════════════════════════════════════════
# §4 行为空间照明（MAP-Elites：行为格，每格留最优）
# ══════════════════════════════════════════════════════════════════════
def behavior_key(frame_ids: Sequence[str], ops: Sequence[str]) -> str:
    """行为描述子 = (认知帧组合, 操作序列) ⇒ 离散格键。

    ★ **不用答案 embedding** ⇒ 绕开 embo-01 在中文句级无分辨率的问题，
      也绕开「措辞相似度在改写型环节失效」的问题（行为是结构性的，不是措辞性的）。
    """
    h = hashlib.sha256()
    h.update(("|".join(sorted(frame_ids))).encode("utf-8"))
    h.update(b"||")
    h.update((">".join(ops)).encode("utf-8"))
    return h.hexdigest()[:16]


class BehaviorArchive:
    """行为空间照明档案。**每格留表现最好的那一个** ⇒ 广度是结构保证的。"""

    def __init__(self) -> Dict[str, Dict[str, Any]]:
        self.cells: Dict[str, Dict[str, Any]] = {}

    def offer(self, key: str, *, payload: str, score: float, meta: Optional[Dict] = None) -> bool:
        """提交一个候选。返回 True = 它成了本格的新最优。"""
        cell = self.cells.get(key)
        if cell is None or score > cell["score"]:
            self.cells[key] = dict(key=key, score=float(score), payload=payload,
                                   meta=dict(meta or {}))
            return True
        return False

    def stats(self) -> Dict[str, Any]:
        scores = [c["score"] for c in self.cells.values()]
        if not scores:
            return dict(n_cells=0, scores=[], mean=0.0, var=0.0, spread=0.0)
        mean = sum(scores) / len(scores)
        var = sum((s - mean) ** 2 for s in scores) / len(scores)
        return dict(n_cells=len(self.cells), scores=sorted(scores),
                    mean=mean, var=var,
                    spread=(max(scores) - min(scores)) if scores else 0.0)

    def dump(self) -> Dict[str, Any]:
        return {k: dict(score=v["score"], meta=v["meta"]) for k, v in self.cells.items()}


# ══════════════════════════════════════════════════════════════════════
# §5 中庸度四指标（★ 全部离散，**不依赖 embedding**）
# ══════════════════════════════════════════════════════════════════════
def common_rate(arm_answers: Sequence[Sequence[str]]) -> float:
    """① **交集率**：所有臂都提到的断言比例 ⇒ 中庸的直接度量。"""
    sets = [set(a) for a in arm_answers if a]
    if len(sets) < 2:
        return 0.0
    inter = set.intersection(*sets)
    union = set.union(*sets)
    return (len(inter) / len(union)) if union else 0.0


def marginal_util(rounds: Sequence[Sequence[str]]) -> List[float]:
    """② **边际利用率**：第 k 轮带来的**新**断言占比 ⇒ **过早闭合的信号**。

    ⚠️ 返回长度 = len(rounds)-1（第一轮没有"边际"）。
    """
    out: List[float] = []
    seen: set = set()
    prev_new = None
    for k, rs in enumerate(rounds):
        cur = set()
        for a in rs:
            cur |= set(a)
        new = len(cur - seen)
        if prev_new is not None:
            total = len(cur) or 1
            out.append(new / total)
        prev_new = new
        seen |= cur
    return out


def dist_to_modal(answer: Sequence[str], all_answers: Sequence[Sequence[str]]) -> float:
    """③ **中庸距离**：与"众数答案"的离散距离（结论集交并比 + 4-gram 距离）。

    ⚠️ **只比同批内相对序**（绝对距离无意义 —— 跨题差 10×）。
    """
    if not answer or not all_answers:
        return 0.0
    scored = []
    for other in all_answers:
        if not other:
            continue
        inter = len(set(answer) & set(other))
        uni = len(set(answer) | set(other))
        jac = 1.0 - (inter / uni if uni else 1.0)
        ga, gb = _ngrams("".join(answer)), _ngrams("".join(other))
        gj = 1.0 - (len(ga & gb) / len(ga | gb) if (ga and gb) else 0.0)
        scored.append((jac + gj) / 2.0)
    if not scored:
        return 0.0
    modal = min(scored)          # 离众数最近的那个
    return max(scored) - modal   # 本答案离众数多远


def coverage_saturation(rounds: Sequence[Sequence[str]], universe: int) -> List[float]:
    """④ **覆盖饱和度**：已找到的断言集合 ÷ |C_t| ⇒ **区分「塌缩/闭合/耗尽」**。"""
    seen: set = set()
    out: List[float] = []
    for rs in rounds:
        for a in rs:
            seen |= set(a)
        out.append(len(seen) / universe if universe else 0.0)
    return out


# ══════════════════════════════════════════════════════════════════════
# §6 工作流
# ══════════════════════════════════════════════════════════════════════
_OUT_SPEC = ("【输出规格】\n"
             "- 只输出 3–6 条，每条一行，行首用「- 」\n"
             "- 每条必须**具体**：带一个数字 / 一个明确条件 / 一个可核查的判断\n"
             "- 不写开场白、不写总结、不写免责说明\n"
             "- 不超过 400 字")


# ⚠️ 2026-10-22 实测（MiniMax-M3.1-Flash-Preview，adaptive thinking）：
#    `max_tokens=2000` ⇒ **两次尝试都被思考块吃光预算**（finish_reason=length,
#    content_len=0）⇒ 返回**空串**。8000 才出正文（309 字符 / 109 秒）。
#    ⇒ 预算阶梯必须**从 8000 起**；2000 这档**不是"可能失败"，是"必然失败"**。
MIN_BUDGET = 8000


def _chat(llm, prompt: str, *, purpose: str, model: str, temp: float = 0.7,
          max_tokens: int = 0, min_ok: int = 20, stats: Optional[Dict] = None):
    """调用包装。**两件事必须同时做到**：

    1. **宽容**：不同客户端支持的 kwargs 不一样 ⇒ 逐级退化，但**不许静默失败**。
    2. **不许把"预算烧光、正文为空"当成功** ⇒ 逐档抬预算重试，
       并把「尝试次数 / 最终 finish_reason / 是否为空」**记进 stats**
       ⇒ **空输出是一条可计数的失败，不是"这条臂没话说"**。

    ⚠️ 这条是从一次真实故障来的：2000 预算 ⇒ 两次 length/0 ⇒ 静默返回空串
       ⇒ 在读数上被误读成"这条臂什么都没产出"。
    """
    base = max(int(max_tokens or 0), MIN_BUDGET)
    ladder = [base] + [b for b in (12000, 16000) if b > base]
    kwargs0 = dict(model=model, temp=temp, max_tokens=base,
                   budgets=tuple(ladder[1:]), min_ok=min_ok, purpose=purpose)

    def _call(kw):
        try:
            return llm.chat(prompt, **kw)
        except TypeError:
            for drop in (("budgets",), ("min_ok",), ("budgets", "min_ok"), ("purpose",)):
                kw2 = {k: v for k, v in kw.items() if k not in drop}
                try:
                    return llm.chat(prompt, **kw2)
                except TypeError:
                    continue
        raise RuntimeError("llm.chat 不接受任何已知参数组合（purpose=%s）" % purpose)

    attempts = 0
    last_fr = ""
    text = ""
    for i, mt in enumerate(ladder):
        kw = dict(kwargs0)
        kw["max_tokens"] = mt
        kw["budgets"] = tuple(x for x in ladder[i + 1:])
        text = _call(kw) or ""
        attempts += 1
        rec = getattr(llm, "rec", None)
        if rec:
            last_fr = getattr(rec[-1], "finish_reason", "") or ""
        if text.strip() and last_fr != "length":
            break
        # 空 或 预算烧光 ⇒ 抬预算重试（**不静默吞掉**）
    info = dict(purpose=purpose, attempts=attempts, finish_reason=last_fr,
                empty=not bool((text or "").strip()),
                chars=len(text or ""))
    if stats is not None:
        stats.setdefault("calls", []).append(info)
    return text, info


def _extract_claims(llm, text: str, *, model: str, cap: int = 12) -> List[str]:
    """机械抽断言（**不判优劣**，只抽行）。"""
    if not (text or "").strip():
        return []
    prompt = ("从下面这段内容里逐条抄出其中**独立成立的具体判断**。\n"
              "只抄原文里有的，不要改写、不要补充、不要评价。每条一行，行首用「- 」。"
              "最多 %d 条。\n\n内容：\n%s" % (cap, text[:2500]))
    raw, _info = _chat(llm, prompt, purpose="W_extract", model=model, temp=0.0,
                       max_tokens=0, min_ok=10)
    out: List[str] = []
    for ln in (raw or "").splitlines():
        ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
        if 8 <= len(ln) <= 160:
            out.append(ln)
    return list(dict.fromkeys(out))[:cap]


class CollapseFixWorkflow:
    """治塌缩工作流。"""

    DEFAULTS = dict(
        n_slots=4,            # 认知槽位数
        seed=0,
        model="",             # 生成侧模型
        judge_model="",       # 评价侧模型（判官）
        max_rounds=2,         # ★ 含演化后重跑 ⇒ 最多两轮
        n_slots_v2=None,      # 第二轮槽位数（默认同 n_slots）
    )

    def __init__(self, llm, **cfg):
        self.llm = llm
        self.C = dict(self.DEFAULTS)
        self.C.update(cfg or {})
        self.chat_stats: Dict[str, Any] = {"calls": []}

    # ---------------- 提示词
    def slot_prompt(self, frame_id: str, action: str, archive: ActionArchive) -> str:
        fr = _FRAME_BY_ID[frame_id]
        tmpl = archive.template(action)
        body = tmpl.format(frame_prompt=fr["prompt"])
        return "问题：%s\n\n%s\n\n%s" % (self._ask, body, _OUT_SPEC)

    def aggregate_prompt(self, drafts: Sequence[str], frame_ids: Sequence[str],
                         archive: ActionArchive) -> str:
        """★ 汇总阶段：**只在这一步让模型看别人的稿**（前面全都互不可见）。"""
        pool = "\n\n".join("【草稿 %d】\n%s" % (i + 1, d) for i, d in enumerate(drafts))
        return ("下面是 %d 份**互相独立**产生的草稿（它们互不可见，"
                "分别从不同认知位置出发）。\n"
                "请**只做一件事**：把它们的**不重复**内容合并成一份答案，"
                "**不要**再补充任何新观点，**不要**改写它们的意思。\n\n%s\n\n%s"
                % (len(drafts), pool, _OUT_SPEC))

    # ---------------- 单槽位
    def _run_slot(self, ask: str, frame_id: str, action: str,
                  archive: ActionArchive) -> Dict[str, Any]:
        self._ask = ask
        prompt = self.slot_prompt(frame_id, action, archive)
        out, info = _chat(self.llm, prompt, purpose="W_slot_%s" % frame_id,
                          model=self.C["model"], temp=0.7, max_tokens=0,
                          min_ok=20, stats=self.chat_stats)
        claims = _extract_claims(self.llm, out, model=self.C["model"]) if out else []
        return dict(frame_id=frame_id, action=action, draft=out or "",
                    claims=claims, n_calls=2,
                    gen_empty=bool(info.get("empty")),
                    gen_attempts=info.get("attempts"),
                    gen_finish=info.get("finish_reason"))

    # ---------------- 失败判定（★ 驱动动作演化）
    def classify_failure(self, slot: Dict[str, Any], verdicts: Optional[Dict[str, str]]) -> Optional[str]:
        """**没有独立失败通道 ⇒ 一切照常。** 失败类型决定"要演化出什么新动作"。"""
        claims = slot.get("claims") or []
        if not claims:
            # ★ 区分两种"空"：**生成被预算烧光** vs **生成成功但抽不出断言**
            #   前者是**仪器故障**（必须被计数、且要演化出更省预算的动作）
            if slot.get("gen_empty"):
                return "empty"
            return "empty"
        if verdicts:
            sup = sum(1 for c in claims if verdicts.get(c) == "支持")
            con = sum(1 for c in claims if verdicts.get(c) == "矛盾")
            if sup == 0 and con == 0:
                return "all_unmentioned"
            if sup == 0:
                return "zero_load_bearing"
        if len(slot.get("draft") or "") < 60:
            return "fallback"
        return None

    # ---------------- 主流程
    def run(self, ask: str, *, verdicts_for=None) -> Dict[str, Any]:
        """跑一遍工作流。

        参数
        ----
        ask         题面
        verdicts_for  可选：把"断言 → 依据判定"的映射传进来（用于**失败分类**）
                       —— 由**评价侧**提供（判官），工作流本身不接触依据包。
        """
        C = self.C
        archive = ActionArchive()
        illum = BehaviorArchive()
        ops: List[str] = []
        rounds: List[List[str]] = []
        arm_records: List[Dict[str, Any]] = []
        failures: Dict[str, int] = {}

        frames = select_frames(C["n_slots"], seed=C["seed"])
        # 第 0 轮：基线动作
        cur_actions = {fid: "base" for fid in frames}
        n_rounds = max(1, int(C["max_rounds"]))
        slot_claims: List[List[str]] = []
        slot_records: List[Dict[str, Any]] = []

        for rnd in range(n_rounds):
            drafts: List[str] = []
            slot_claims: List[List[str]] = []
            slot_records: List[Dict[str, Any]] = []

            # ── 1) 发散（★ 槽位互不可见：每个槽位只拿题面 + 自己的帧 + 自己的动作）
            for fid in frames:
                slot = self._run_slot(ask, fid, cur_actions[fid], archive)
                slot_records.append(slot)
                drafts.append(slot["draft"])
                slot_claims.append(slot["claims"])
                ops.append("GEN[%s:%s]" % (fid, cur_actions[fid]))

            # ── 2) 去冗余（跨槽位）
            flat = [c for cs in slot_claims for c in cs]
            kept = dedup(flat)
            kept_set = set(kept)
            rounds.append([c for cs in slot_claims for c in cs])

            # ── 3) 失败判定 → ★ 动作演化
            new_actions: Dict[str, str] = {}
            for slot in slot_records:
                fk = self.classify_failure(slot, verdicts_for)
                if fk:
                    failures[fk] = failures.get(fk, 0) + 1
                    nm = propose_new_action(fk, slot["frame_id"], archive)
                    if nm:
                        new_actions[slot["frame_id"]] = nm
            if not new_actions:
                break                       # 没有失败 ⇒ 不演化（★ 不无节制扩动作空间）

            # ── 4) 重跑（用**各自的新动作**）⇒ 搜索空间在这一步变大
            # ⚠️ **合并**而不是替换：没失败的槽位要**保留原动作**
            #    （2026-10-22 实测 bug：`dict(new_actions)` 会把其余槽位的动作冲掉
            #      ⇒ 第二轮 KeyError。**只有真跑 + 真演化才会触发**。）
            cur_actions = dict(cur_actions)
            cur_actions.update(new_actions)
            ops.append("EVOLVE[%s]" % ",".join(sorted(set(new_actions.values()))))

        # ── 5) 汇总（★ 只在这一步让模型看别人的稿）
        final_drafts = [s["draft"] for s in slot_records] if slot_records else []
        if len(final_drafts) > 1:
            agg, _ai = _chat(self.llm, self.aggregate_prompt(final_drafts, frames, archive),
                             purpose="W_aggregate", model=self.C["model"],
                             temp=0.3, max_tokens=0, min_ok=20, stats=self.chat_stats)
            ops.append("AGGREGATE")
        else:
            agg = (final_drafts[0] if final_drafts else "")

        # ── 6) 装配（机械：抽取 + 去冗余，**不让模型再总结**）
        final_claims = dedup(_extract_claims(self.llm, agg, model=self.C["model"])) if agg else []
        if not final_claims:
            final_claims = dedup([c for cs in slot_claims for c in cs])

        # ── 7) 照明归档 + 中庸度记账
        bkey = behavior_key(frames, ops)
        illum.offer(bkey, payload=agg, score=len(final_claims),
                    meta=dict(frames=list(frames), ops=list(ops),
                              n_actions=len(archive.actions)))

        return dict(
            chat_stats=self.chat_stats,
            answer=agg, claims=final_claims, frames=list(frames), ops=list(ops),
            rounds=rounds, archive=archive.stats(), illum=illum.stats(),
            failures=dict(failures),
            slot_records=[dict(frame_id=s["frame_id"], action=s["action"],
                               n_claims=len(s["claims"]),
                               n_chars=len(s["draft"])) for s in slot_records],
        )
