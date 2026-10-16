"""接收端测量层。

**只测行为输出，绝不测「你觉得有启发吗」**——后者测的是谄媚。

本模块的实测结论见 `REPORT-2026-10-17.md`。要点：

已验证 ✅
  `check_claims` 闭合式枚举：阳性对照 1.00 / 阴性对照 0.00，是本轮唯一通过验证的工具。
  理由：任务是逐条打「是/否」，**没有任何可被奉承的评价维度**，谄媚无处着力。

已证伪 ❌
  一切基于「字面内容相似度」的度量（文档级余弦、片段级余弦、概念采纳）：
  **接收端是重新推导而非复制**，字面相似度与采纳呈反向相关。
  抽得具体 → 接收端不照抄 → 命中 0；抽得原则 → 任何称职回答都满足 → 无区分度。
  分辨率窗口是空的。见报告 §3。

差值形式（`净 = 真实 − 对照`）本身成立：纯风格增益会同时抬高各项而在差值中相消。
本轮两次倒挂（占位 1.000 / 真实 0.200）之所以醒目，正是因为有对照。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from creativity_lab.metrics import _mat

_NUM = re.compile(r"\d+(?:\.\d+)?")


def _clip(t: str) -> str:
    """不做截断。首版 CLIP=260 把 593 字的 donor 答案截断，
    恰好截掉了它与接收端输出差异最大的部分，信号自毁。
    长度改由提示词控制，并由 G5 事后检验。"""
    return t or ""


def _bg(t: str) -> set:
    t = re.sub(r"\s", "", t or "")
    return {t[k:k + 2] for k in range(len(t) - 1)}


def _sents(t: str) -> list:
    return [x for x in re.split(r"[。！？；\n]", re.sub(r"\s+", "", t or "")) if len(x) >= 8]


# ---------------------------------------------------------------- 抽取


def mechanisms(llm, ans: str, model: str = "MiniMax-M3") -> list:
    """抽取**原则级**做法（抽象式）。

    粒度教训：首版抽到「只选本田雅马哈铃木」这类品牌级条目，
    接收端永远不会照抄，采纳率恒为 0。
    """
    from creativity_lab.prompts import EXTRACT_MECH
    t = llm.chat(EXTRACT_MECH.format(ans=_clip(ans)[:900]), model=model,
                 purpose="extract", max_tokens=1000, budgets=(1600, 2200), min_ok=4) or ""
    out = []
    for ln in t.splitlines():
        ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
        if 4 <= len(ln) <= 32 and ln not in out:
            out.append(ln)
    return out[:6]


def quote_spans(llm, ans: str, n: int = 6, model: str = "MiniMax-M3") -> list:
    """抽取式：一字不改地摘抄原文连续字串，**接地由构造保证**，无需事后过滤。

    抽象式抽取无法兼顾接地与容错——「标称续航需打折」覆盖原文仅 0.10，
    但它忠实。字面摘抄没有这个问题。
    """
    from creativity_lab.prompts import QUOTE_SPANS
    t = llm.chat(QUOTE_SPANS.format(n=n, ans=_clip(ans)[:900]), model=model,
                 purpose="quote", max_tokens=1400, budgets=(2000,), min_ok=20) or ""
    a = re.sub(r"\s+", "", ans or "")
    out = []
    for ln in t.splitlines():
        ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
        ln = re.sub(r"\s+", "", ln)
        if 10 <= len(ln) <= 60 and ln in a and ln not in out:
            out.append(ln)
    return out[:n]


# ---------------------------------------------------------------- 接地与采纳


def grounded(mechs: list, ans: str) -> list:
    """接地校验：**只拦数字矛盾**，不拦忠实改写。

    两类情况必须区别对待：
      「标称续航需打折，实测为准」 ← 原文是这么讲的，只是抽象了一层。改写。
      「预算3000到6000元」         ← 原文说两万。**数字与原文矛盾**，是幻觉。

    首版用二元组覆盖率一刀切，把前者也误杀（覆盖率 0.10-0.42），抽取产出归零。
    """
    A = _bg(ans)
    nums = set(_NUM.findall(ans or ""))
    out = []
    for m in mechs:
        m2 = re.sub(r"\s", "", m)
        if set(_NUM.findall(m2)) - nums:      # 引入了原文没有的数字
            continue
        G = _bg(m2)
        if G and len(G & A) / len(G) < 0.12:  # 几乎完全不沾原文
            continue
        out.append(m2)
    return out


def adopt(mechs: list, text: str, thr: float = 0.7) -> float:
    """字面采纳率（二元组覆盖率）。

    ⚠️ 实测在「原则被重新推导」的场景下是**反向指标**，仅作诊断，不作主度量。
    """
    if not mechs:
        return 0.0
    T = _bg(text)
    if not T:
        return 0.0
    hit = 0
    for m in mechs:
        G = _bg(re.sub(r"\s", "", m))
        if G and len(G & T) / len(G) >= thr:
            hit += 1
    return round(hit / len(mechs), 4)


# ---------------------------------------------------------------- 已验证的主度量


def check_claims(llm, claims: list, out: str, model: str = "MiniMax-M3") -> tuple:
    """闭合式枚举：判断若干条具体做法是否出现在回答中。

    **为什么这不是谄媚陷阱**：模型看到的是一份文本和一组具体条目，
    任务是逐条打「是/否」，**没有任何可以被奉承的评价维度**。
    谄媚需要「被夸」的诱因，这里没有。

    实测：阳性对照（确实在文中）1.00，阴性对照（确实不在）0.00。

    返回 (命中率, 逐条判定)。
    """
    if not claims:
        return 0.0, []
    from creativity_lab.prompts import CHECK_CLAIMS
    lst = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))
    t = llm.chat(CHECK_CLAIMS.format(out=_clip(out)[:1400], claims=lst), model=model,
                 purpose="check", max_tokens=900, budgets=(1400, 2000),
                 min_ok=len(claims) * 2) or ""
    verdicts = []
    for ln in t.splitlines():
        m = re.search(r"[是否]", ln)
        if m:
            verdicts.append(1 if m.group() == "是" else 0)
    verdicts = verdicts[:len(claims)]
    while len(verdicts) < len(claims):
        verdicts.append(0)
    return (round(sum(verdicts) / len(claims), 4) if verdicts else 0.0), verdicts


def net_check(llm, claims: list, y_real: str, y_ph: str, y_wrong: str) -> dict:
    """净采纳 = 读了 A 之后 claim 被采纳的比例，减去读了占位、读了错误自信之后的同一比例。

    差值形式：纯风格增益相消。
    ⚠️ 报告 §4.1：**X2 占位不得从 A 派生**，否则话题重叠导致假阳性天花板（实测 1.000）。
    """
    a, va = check_claims(llm, claims, y_real)
    b, vb = check_claims(llm, claims, y_ph)
    c, vc = check_claims(llm, claims, y_wrong)
    return dict(adm_real=a, adm_ph=b, adm_wrong=c,
                net=round(a - b - c, 4), net_style=round(a - b, 4),
                verdicts=dict(real=va, ph=vb, wrong=vc))


# ---------------------------------------------------------------- 已证伪（保留作诊断）


def spans(ans: str, n: int = 5) -> list:
    a = re.sub(r"\s+", "", ans or "")
    if not a:
        return []
    step = max(40, len(a) // n)
    out, i = [], 0
    while i < len(a) and len(out) < n:
        out.append(a[i:i + step])
        i += step
    return [x for x in out if len(x) >= 20]


def recognised(llm, span: str, out: str) -> float:
    """片段与输出各句的最大余弦。⚠️ 实测为反向指标，见模块文档。"""
    S, O = _sents(span), _sents(out)
    if not S or not O:
        return 0.0
    M = _mat(llm.embed(S + O))
    k = len(S)
    return float(max(M[i] @ M[j] for i in range(k) for j in range(k, k + len(O))))


def net_recognition(llm, spans_: list, y_real: str, y_ph: str, y_wrong: str) -> dict:
    """⚠️ 实测反向：字面相似度在「重新推导」场景下与采纳负相关。仅作诊断。"""
    if not spans_:
        return dict(rec=0.0, rec_style=0.0, n=0, per=[])
    per = []
    for sp in spans_:
        a, b, c = (recognised(llm, sp, t) for t in (y_real, y_ph, y_wrong))
        per.append(dict(a=round(a, 4), b=round(b, 4), c=round(c, 4),
                        net=round(a - b - c, 4)))
    n = len(per)
    return dict(rec=round(sum(x["net"] for x in per) / n, 5),
                rec_style=round(sum(x["a"] - x["b"] for x in per) / n, 5), n=n, per=per)


# ---------------------------------------------------------------- 接收端


@dataclass
class Turn:
    text: str


class Receiver:
    def __init__(self, llm, model: str, spec: str = "请控制在 250-350 字之间。"):
        self.llm, self.model, self.spec = llm, model, spec

    def _gen(self, ask: str, ans: str | None = None) -> str:
        from creativity_lab.prompts import ASK_ANSWER, ASK_BASELINE
        p = (ASK_ANSWER.format(ask=ask, ans=_clip(ans), spec=self.spec) if ans is not None
             else ASK_BASELINE.format(ask=ask, spec=self.spec))
        return self.llm.chat(p, model=self.model, purpose="receiver", min_ok=60) or ""

    def baseline(self, ask: str) -> str:
        return self._gen(ask)

    def condition(self, ask: str, ans: str) -> str:
        return self._gen(ask, ans)

    def selfscore(self, ans: str) -> float:
        s = self.llm.chat("给下面这份回答打一个 0-10 的信息量分，只输出数字。\n\n"
                          + _clip(ans)[:600], model=self.model,
                          purpose="selfscore", min_ok=1) or "0"
        m = _NUM.findall(s)
        return float(m[0]) if m else 0.0

    def retention(self, ask: str, ans: str, claims: list | None = None) -> str:
        """M3：无关追问之后，原答案是否仍影响接收端。"""
        from creativity_lab.prompts import ASK_RECALL, FILLERS
        cur = self.condition(ask, ans)
        for f in FILLERS:
            cur = self.llm.chat(_clip(cur) + "\n\n" + f, model=self.model,
                                purpose="filler", min_ok=15) or cur
        return self.llm.chat(ASK_RECALL.format(ask=ask, spec=self.spec),
                             model=self.model, purpose="recall", min_ok=60) or ""
