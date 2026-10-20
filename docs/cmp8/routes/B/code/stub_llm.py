# -*- coding: utf-8 -*-
"""**离线 stub 模型**（0 次真实 API 调用）。

用途：证明**训练循环是可执行的**（轮次 / 滑动基线 / EMA 部署 / 早停 / 校准闸门），
而不需要任何外呼、也不需要任何预算。
⚠️ **它不产生任何学习效果结论**：stub 的答案是固定的、判官的归因是固定的
   ⇒ 只能验证"代码路径跑得通、量会动、闸门会响"，**不能**用来评价策略好坏。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass


@dataclass
class StubCall:
    model: str
    purpose: str
    max_tokens: int
    finish_reason: str = "stop"
    content_len: int = 0
    ok: bool = False
    secs: float = 0.0


_ANSWER = ("根据现行规则，第一项规定的适用条件是连续满足十二个月以上。"
            "第二项规定的办理时限是自受理之日起十五个工作日。"
            "第三项规定的金额上限为每次三千元，且需一次结清。"
            "具体以主管部门最新公示为准。")

_CLAIMS = ["规则要求的适用条件是连续满足十二个月以上。",
           "办理时限为自受理之日起十五个工作日。",
           "金额上限为每次三千元且需一次结清。"]

_SUBCLAIMS = ["适用条件是连续满足十二个月以上。",
              "办理时限为十五个工作日。"]


class StubLLM:
    """按提示词内容返回固定文本的假模型。接口与 `creativity_lab.client.LLM` 一致。"""

    def __init__(self, model="stub-offline"):
        self.rec = []
        self.model = model

    def chat(self, prompt: str, *, model=None, purpose: str = "", max_tokens: int = 8000,
             budgets=(), min_ok: int = 0, **kw) -> str:
        t0 = time.time()
        p = prompt or ""
        if "待核验的陈述" in p and "依据条目" in p:
            n = len(re.findall(r"^\s*\d+\.\s", p, flags=re.M))
            out = "\n".join(["支持 | E1"] + ["未提及 | -1"] * max(n - 1, 0))
        elif "逐条列出其中" in p:
            out = "\n".join("- " + c for c in _CLAIMS)
        elif "拆成可以分别核验" in p:
            out = "\n".join("- " + c for c in _SUBCLAIMS)
        else:
            out = _ANSWER
        self.rec.append(StubCall(model or self.model, purpose, max_tokens, "stop",
                                  len(out), len(out) >= min_ok, time.time() - t0))
        return out
