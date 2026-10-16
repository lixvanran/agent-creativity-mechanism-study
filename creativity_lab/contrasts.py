"""自动构造两个对照，不经人手，不含作者先验。

X2 占位：**从真实答案机械抽象**出的同口吻、同长度、零本题信息的版本。
   首版让模型「回答一个泛化问题」当占位，实测失败：它照样输出「只选本田、雅马哈、
   铃木」「认准五羊本田UY」这类品牌级建议——比真答案还具体。占位必须由真答案导出，
   否则对照无效。

X3 错误自信：**同域另一道题的答案**。同口吻、同样长、对本题确定错误。
"""
from __future__ import annotations

ABSTRACT = """把下面这段话**改写成同样口吻、同样长度、同样自信度、同样具体程度的空话**：
保留句式、节奏和「笃定」的语气，但把其中**所有具体内容**（判断、机制、数字、做法）
替换成不针对任何具体情境的泛泛表述。不要新增任何信息，不要解释，只输出改写后的文本。

原文：
{ans}"""


def placeholder(llm, ans: str, model="MiniMax-M3") -> str:
    """从真实答案导出等风格、零内容的占位。
    长度按原文动态设下限，否则模型会把 300 字压成 89 字，对照就同时变了风格和长度。"""
    n = len(ans or "")
    lo = max(60, int(n * 0.55))
    return llm.chat(ABSTRACT.format(ans=ans), model=model, purpose="abstract",
                    max_tokens=max(3000, n * 4), budgets=(5000, 7000),
                    min_ok=lo) or ""


def confidently_wrong(llm, topic, pool, model="MiniMax-M3"):
    """同域另一道题的答案当本题的错误自信对照。返回 (文本, 来源题号)。"""
    if not pool:
        return "", ""
    tid, t = max(pool, key=lambda x: len(x[1]))
    return t, tid
