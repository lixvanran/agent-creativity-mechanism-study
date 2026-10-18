"""共享的核验层：断言抽取 + 四分类核验 + 打分。

核验器版本 v4（带题目语境 + 「非主张」类 + 同义改写算支持），
回归测试对更新后的金标 27/27。

打分函数（巡练的裁判）：

    score = n支持 − 2·n矛盾 − 0.5·n非主张

- **绝对计数，不除长度**：上一轮密度奖励被长度劫持（dual_fuse 最短所以得分最高）。
  长度改为在构造时封顶（所有变体同样 400 字上限），由构造消除混淆。
- 矛盾权重 2：自信地说错比少说一句更糟。
- 非主张轻罚：复述题面是填充物。
"""
from __future__ import annotations

import re
import time

# ---------------------------------------------------------------- 断言抽取
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
    for prompt, cap in ((ASSERT_MAIN, 10), (ASSERT_LOOSE, 10), (ASSERT_ONE, 1)):
        t = llm.chat(prompt.format(t=text[:1200]), model="MiniMax-M3", purpose="assert",
                     max_tokens=1800, budgets=(2400, 3200), min_ok=12) or ""
        c = _clean(t)
        if c:
            return c[:cap]
    return []


# ---------------------------------------------------------------- 四分类核验
CHECK4 = """下面是一份「依据原文」和一个「问题」，之后列出若干条**待核验的陈述**。

分两步判断：

第一步：这条陈述是**法律主张**（对权利义务、程序、期限、数值标准的规范性表述），
还是只是**复述了问题里的情形**（如「公司要求收取押金2000元」这种对事实的描述）？
如果只是复述情形，答「非主张」。

第二步：对属于法律主张的，判断它与依据原文的关系，只回答一个词：
- 「支持」：依据原文明确认可或蕴含该条。**改写、简称、换词但含义相同，也算支持。**
- 「矛盾」：依据原文明确讲了与之相反的内容。
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
                t = llm.chat(CHECK4.format(ask=ask, ev=ev, claims=lst), model="MiniMax-M3",
                             purpose="check", max_tokens=1600, budgets=(2400, 3200, 4000),
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


# ---------------------------------------------------------------- 打分
def score_of(verd: dict, claims: list) -> dict:
    su = sum(1 for c in claims if verd.get(c) == "支持")
    co = sum(1 for c in claims if verd.get(c) == "矛盾")
    nm = sum(1 for c in claims if verd.get(c) == "非主张")
    un = sum(1 for c in claims if verd.get(c) == "未提及")
    return dict(n_sup=su, n_con=co, n_non=nm, n_unment=un,
                score=su - 2 * co - 0.5 * nm)
