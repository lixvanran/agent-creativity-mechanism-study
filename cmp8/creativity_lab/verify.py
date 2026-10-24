"""共享的核验层：断言抽取 + 四分类核验 + 打分。

★ 相对原版的一处修改（必须知道）：CHECK4 第一步原本问「这条陈述是不是**法律主张**」。
那个问法在非法律域（高考选校/骑行战术/学习方法/气质量表）上会误判：
含题面数字的陈述（如「620分及以上累计7436人」）会被当成「复述了题面情形」→ 判成非主张。
现已泛化为「可核验的事实性断言」，并给出可操作判据：
**只要陈述里含有超出问题本身的信息（数字/阈值/名称/规则/主体关系），就当它是断言。**
泛化后法律域回归 27/27 保住、矛盾召回仍 9/9 = 100%。
"""
from __future__ import annotations
import re
import time

ASSERT_MAIN = """把下面这段回答里的**可判真假的陈述**逐条列出来。

要求：
- 一条一个可独立核验的事实性陈述（数字、法规条文、权利义务、程序、时限、主体责任）。
- **不要**主观评价、不要「建议」「应该」这类无事实内容的句子。
- 每条 10-40 字，一行一条，最多 10 条。

文本：
{t}"""
ASSERT_LOOSE = """从下面这段文字里，逐行摘出其中**陈述事实的句子**（不是观点、不是建议）。
一行一条，最多 10 条。原文照抄，不要改写。

文字：
{t}"""
ASSERT_ONE = """从下面这段文字里，摘出**第一条**陈述事实的句子，原文照抄，不要改写。只输出这一句。

文字：
{t}"""


def _clean(t: str) -> list:
    out = []
    for ln in (t or "").splitlines():
        ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
        if 8 <= len(ln) <= 70 and ln not in out:
            out.append(ln)
    return out


def extract_claims(llm, text: str) -> list:
    """三级降级抽取。任一级拿到非空就停，避免过度抽取。"""
    for prompt, cap in ((ASSERT_MAIN, 10), (ASSERT_LOOSE, 10), (ASSERT_ONE, 1)):
        t = llm.chat(prompt.format(t=text[:1200]), purpose="assert",
                     max_tokens=1800, budgets=(2400, 3200), min_ok=12) or ""
        c = _clean(t)
        if c:
            return c[:cap]
    return []


CHECK4 = """下面是一份「依据原文」和一个「问题」，之后列出若干条**待核验的陈述**。

分两步判断：

第一步：这条陈述是不是**可核验的事实性断言**（对数值、规则、程序、期限、主体责任的
具体表述），还是**只是复述问题里已经给出的情形**（如「公司要求收取押金2000元」这种
把题面原样搬过来的描述）？
**判据：只要陈述里含有超出问题本身的信息（数字、阈值、名称、规则、主体关系），就当它是断言。**
只是复述情形，答「非主张」。

第二步：对属于断言的，判断它与依据原文的关系，只回答一个词：
- 「支持」：依据原文明确认可或蕴含该条。**改写、简称、换词但含义相同，也算支持。**
- 「矛盾」：依据原文明确讲了与之相反的内容（含数字对不上、阈值不同、方向相反）。
- 「未提及」：依据原文没有讲到，或讲的是别的事。**不确定时一律答「未提及」。**

一行一条，顺序对应，不要解释，不要补充。

问题：
{ask}

依据原文：
{ev}

待核验的陈述：
{claims}"""
BATCH = 8


def check_claims(llm, ask: str, ev: str, claims: list) -> dict:
    """逐条判定。**解析失败必须重试**——首版不重试，一次 API 抖动就静默丢掉一批断言，
    后果是分母变小、比率被抬高（实测让 direct 矛盾率显示成 15.4%，实为 59.1%）。"""
    out = {}
    for i in range(0, len(claims), BATCH):
        b = claims[i:i + BATCH]
        lst = "\n".join("%d. %s" % (j + 1, c) for j, c in enumerate(b))
        got = {}
        for attempt in range(3):
            try:
                t = llm.chat(CHECK4.format(ask=ask, ev=ev, claims=lst), purpose="check",
                             max_tokens=1600, budgets=(2400, 3200, 4000),
                             min_ok=len(b) * 2) or ""
            except Exception:
                t = ""
            lines = [x for x in t.splitlines() if x.strip()]
            got = {}
            for c, ln in zip(b, lines):
                m = re.search(r"非主张|支持|矛盾|未提及", ln)
                got[c] = m.group() if m else "解析失败"
            if "解析失败" not in got.values() and len(got) == len(b):
                break
            time.sleep(2 + attempt * 3)
        out.update(got)
    return out


def score_of(verd: dict, claims: list) -> dict:
    su = sum(1 for c in claims if verd.get(c) == "支持")
    co = sum(1 for c in claims if verd.get(c) == "矛盾")
    nm = sum(1 for c in claims if verd.get(c) == "非主张")
    un = sum(1 for c in claims if verd.get(c) == "未提及")
    return dict(n_sup=su, n_con=co, n_non=nm, n_unment=un,
                score=su - 2 * co - 0.5 * nm)
