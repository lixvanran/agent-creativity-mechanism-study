#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 极性词表（人工盲标，零判官）

═══ 为什么要有这个 ═══
信号探测 v1 的结果：**C1 ≈ R1**（覆盖��与"反极性档案全文注入"不可区分），
且 C0 反而最高。这只能有两种解释：
  (a) C1 的产出**没有**编码"站在哪一端"；
  (b) 我们**没有能测出"站在哪一端"的指标**。
要区分 (a) 与 (b)，必须有一个能测极性方向的判据。

**从 axis 描述自动抽关键词这条路已经失败**（实测）：
两端的 2-gram 碎片化严重（"的压"/"价的"/"力来"），且**两端共享大量题面词**
（"降价/价格/压力" 同时出现在 A 端和 B 端）⇒ 词表无区分度。

═══ 本表怎么来的（盲标纪律）═══
**只依据题库的 `axis.pole_a` / `axis.pole_b` 原文与 `dilemma` 手工标注，
在看过任何模型产出之前写定**（对应 multi-mind 自承的 `blind=false` 教训）。
每端 3–5 个词，优先选**该端独有的判别性词**，回避题面共有词。

═══ 怎么用 ═══
`polarity_score(text) = hit(pole_a 词) − hit(pole_b 词)` ∈ [−1, 1]
· **符号对齐**：按档案自选极性 `self_polarity` 翻符号
  （aligned = score × (+1 if pole_a else −1)）⇒ 跨题可平均。
· **反极性检验**：R1 的档案是 C0 的**反极性** ⇒
  若机制真的在编码极性，**C1 的 aligned 应与 C0 同号、与 R1 反号**。
· **题面共有词会抬高绝对值** ⇒ 必须在**题内**做配对比较（比较臂间差，不是绝对值）。

★ 本表是**判别力筛查**，不是效标。它只回答"产出更接近哪一端"，
不回答"哪一端更好"。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import metrics2 as M  # noqa: E402

# 盲标：每题两端的判别性词（不重叠、不含题面共有词）
POLARITY_LEXICON = {
    "T01": {
        "pole_a": ["结余", "基金", "结构", "审计", "测算"],
        "pole_b": ["恩义", "私情", "亏欠", "报恩", "感情"],
    },
    "T02": {
        "pole_a": ["转移", "三角", "分摊", "转嫁", "结构"],
        "pole_b": ["佣金", "多付", "账面", "一笔", "抽成"],
    },
    "T03": {
        "pole_a": ["体面", "失语", "省下", "沉默", "承认"],
        "pole_b": ["习惯", "复健", "康复", "功能", "锻炼"],
    },
    "T04": {
        "pole_a": ["政策", "红利", "不认同", "补贴", "待遇"],
        "pole_b": ["手艺", "技艺", "活计", "行当", "本行"],
    },
    "T05": {
        "pole_a": ["签字", "合同", "制度", "免责", "担责"],
        "pole_b": ["准确率", "验证", "算法", "技术", "参数"],
    },
    "T06": {
        "pole_a": ["裁决", "宣判", "定论", "判词", "结论"],
        "pole_b": ["追忆", "纪念", "怀念", "回忆", "追思"],
    },
    "T07": {
        "pole_a": ["验收", "发现", "后果", "监控", "能力"],
        "pole_b": ["写下", "提交", "代码", "作者", "开发者"],
    },
    "T08": {
        "pole_a": ["保住", "必要", "剩下", "继续", "容忍"],
        "pole_b": ["好歹", "忘恩", "道德", "过分", "忘本"],
    },
    "T09": {
        "pole_a": ["时钟", "同一块地", "场地", "归属", "时段"],
        "pole_b": ["儿童", "备考", "价值", "排序", "优先"],
    },
    "T10": {
        "pole_a": ["同源", "翻译", "行业", "可转", "衔接"],
        "pole_b": ["污点", "洗不掉", "抹掉", "解释", "怀疑"],
    },
}


EXTRA_LEXICON = {}


def register(d: dict) -> None:
    """注册外部题库的极性词表（如 topics_gaokao.POLARITY）。"""
    EXTRA_LEXICON.update(d or {})


def lexicon_for(topic_id: str):
    return POLARITY_LEXICON.get(topic_id) or EXTRA_LEXICON.get(topic_id)


def polarity_score(text: str, topic_id: str) -> dict:
    """返回 {'score', 'a_hits', 'b_hits', 'n_a', 'n_b'}。score = hit(a) − hit(b)。"""
    lex = lexicon_for(topic_id)
    if not lex:
        return {"applicable": False}
    a, b = lex["pole_a"], lex["pole_b"]
    ha = M.hit_rate(text, a)
    hb = M.hit_rate(text, b)
    return {"applicable": True, "score": round(ha - hb, 4),
            "a_hits": M.hit_which(text, a), "b_hits": M.hit_which(text, b),
            "n_a": len(a), "n_b": len(b),
            "a_rate": round(ha, 4), "b_rate": round(hb, 4)}


def align(score: float, self_polarity: str | None) -> float | None:
    """按档案自选极性做符号对齐。"""
    if self_polarity == "pole_a":
        return score
    if self_polarity == "pole_b":
        return -score
    return None


def selftest(verbose: bool = True) -> dict:
    """自检：① 两端词表不重叠 ② 阳性/阴性可分 ③ 无题面共有词误命中。

    ★ 关键自检：**A 端文本必须打出正分，B 端文本必须打出负分**。
      如果两端都打 0，说明词表没区分度 ⇒ 整个极性判据作废。
    """
    res = {}

    def say(k, ok, detail=""):
        res[k] = {"pass": bool(ok), "detail": detail}
        if verbose:
            print("  %s %-30s %s" % ("✓" if ok else "✗", k, detail))

    # ① 词表不重叠
    overlap = []
    for tid, lex in POLARITY_LEXICON.items():
        ov = set(lex["pole_a"]) & set(lex["pole_b"])
        if ov:
            overlap.append((tid, ov))
    say("两端词表不重叠", not overlap, str(overlap[:3]))

    # ② 阳性/阴性可分（用每端词本身造阳性文本）
    bad = []
    for tid, lex in POLARITY_LEXICON.items():
        pos = "、".join(lex["pole_a"][:3])
        neg = "、".join(lex["pole_b"][:3])
        sp = polarity_score(pos, tid)
        sn = polarity_score(neg, tid)
        if not (sp["score"] > 0 and sn["score"] < 0):
            bad.append((tid, sp["score"], sn["score"]))
    say("A端文本正分 / B端文本负分", not bad, str(bad[:4]))

    # ③ 无关文本必须接近 0
    noise = "秋天的风从窗缝里钻进来，她起身去关窗，顺手把桌上的台灯拧暗了一点。"
    ns = [polarity_score(noise, tid)["score"] for tid in POLARITY_LEXICON]
    say("无关文本接近 0", max(abs(x) for x in ns) <= 0.001,
        "max|score|=%.4f" % max(abs(x) for x in ns))

    allpass = all(v["pass"] for v in res.values())
    if verbose:
        print("  === 极性词表自检: %s (%d/%d) ===" % ("全部通过" if allpass else "有未通过",
                                                sum(v["pass"] for v in res.values()), len(res)))
    return {"all_pass": allpass, "cases": res}


if __name__ == "__main__":
    out = selftest()
    sys.exit(0 if out["all_pass"] else 1)
