# -*- coding: utf-8 -*-
"""路线 B v2：**编号化依据包** + **可归因到条目**的核验 + **训练奖励代理**。

设计理由见 `/workspace/lab/routes/B/DESIGN.md` §3（奖励函数）。

────────────────────────────────────────────────────────────────────────
为什么要有"编号化依据包"
────────────────────────────────────────────────────────────────────────
协议的主判据是**有效信息维度数 VD**（承重族个数），但 VD 需要
「独立抽取器 + 判官 + 归族」三层，成本高、不能塞进训练循环的每一步。
⇒ 训练需要一个**可在循环内算出来**的代理。
本模块给的代理是 **Ŵ = 被"经核验成立"的断言覆盖到的、且**承载结论**的依据条目数
          ÷ 承载结论的依据条目总数**（分母固定、每题事先写死）。

为什么这个代理贴近 VD（而不是"条数/宽度"）：
  * 协议 §4.7 **E6** 规定：依据包里没有可核条目的卡**不计入主判据**
    ⇒ 协议自己的 VD 已经是**"依据锚定"**的 ⇒ 代理与主判据同族。
  * 分母是**事先写死的条目数** ⇒ 写多少字、说多少句都不影响 Ŵ（抗"灌水"）。
  * 只有判官判**支持**的卡才贡献 ⇒ 说错（矛盾）不涨分、未核验不涨分。
  * 去重按**依据条目**做（硬划分，无阈值）⇒ 同一件事说三遍不涨分（抗"重复"）。
  * `anchored` 标记把「与结论无关的花絮依据」排除在分母外 ⇒ 对齐协议的 C1/C3。

代理与目标的**已知差距**（DESIGN.md §3.3 有完整表格）：
  * 代理**高估**：协议按"删除反事实"归族 ⇒ 两条不同依据条目若支撑同一结论，
    协议算 1 个维度、代理算 2 个 ⇒ 代理系统性地**偏大**。
  * 代理**可能漏**：结论空间 C_t 之外的维度协议也测不到（协议 L1 同款局限）。
  * ⇒ 代理是**方向性**训练信号；其与真 VD 的关系必须用**预注册的校准**检验。

**红旗（不可违反）**：本模块读到的 `anchored` 标记与条目总数**只进奖励计算**，
**绝不允许**进入策略特征、绝不进生成侧提示词（DESIGN.md §3.4）。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

REL = ("支持", "矛盾", "未提及", "非主张")

# ───────────────────────────────────────── 依据索引
@dataclass
class EvidenceIndex:
    """一个主题的编号化依据包。

    items: [{id, text, anchored}]，`anchored=True` 表示该条**承载某条结论**
           （对应协议 C1/C3：删掉它 ⇒ 某条结论从可支持变不可支持）
    """
    topic_id: str
    ask: str
    items: list = field(default_factory=list)

    @property
    def anchored_ids(self) -> list:
        return [it["id"] for it in self.items if it.get("anchored")]

    @property
    def n_anchored(self) -> int:
        return len(self.anchored_ids)

    def numbered_text(self) -> str:
        return "\n".join("[%s] %s" % (it["id"], it["text"]) for it in self.items)

    def plain_text(self) -> str:
        return "\n".join(it["text"] for it in self.items)


def load_index(path: str) -> dict:
    """{topic_id: EvidenceIndex}"""
    raw = json.load(open(path, encoding="utf-8"))
    out = {}
    for t in raw["topics"]:
        out[t["topic_id"]] = EvidenceIndex(t["topic_id"], t["ask"], t["items"])
    return out


# ───────────────────────────────────────── 判官（带条目归因）
CHECK_V2 = """下面是一份**编号的依据条目**和一个**问题**，之后列出若干条**待核验的陈述**。

分两步判断。

第一步：这条陈述是**法律主张**（对权利义务、程序、期限、数值标准的规范性表述），
还是只是**复述了问题里的情形**（如「公司要求收取押金2000元」这种对事实的描述）？
如果只是复述情形，关系填「非主张」。

第二步：对属于法律主张的，判断它与依据条目的关系：
- 「支持」：某个依据条目明确认可或蕴含该条。**改写、简称、换词但含义相同，也算支持。**
- 「矛盾」：某个依据条目明确讲了与之相反的内容。
- 「未提及」：依据条目没有讲到，或讲的是别的事。**不确定时一律答「未提及」。**

一共输出**{n} 行**（与待核验陈述的条数相同），每行格式固定为：`关系 | 条目编号`。
**不要加编号、不要写解释、不要写任何其它文字。**
- 关系为「支持」或「矛盾」时，条目编号填**依据条目里真正对应的那一条的编号**
  （一条陈述可能被多条支持，用逗号分隔，如 `支持 | E1,E3`）。
- 关系为「未提及」或「非主张」时，条目编号填 `-1`。
- 不要解释，不要补充。

问题：
{ask}

依据条目：
{ev}

待核验的陈述：
{claims}"""


def _parse_verdict_lines(t: str, blk: list, known: set) -> dict:
    """**严格逐行解析**：只认「行首是关系词」的行 ⇒ 前言/解释不会被误配。

    ⚠️ 旧版用 `zip(claims, lines)` **按位置**配对 ⇒ 模型多打一行前言就整体错位。
    这里改成：先筛出合法行，再按顺序配对；数量对不上 ⇒ 缺的判「解析失败」并重试。
    """
    got, order = {}, []
    for ln in (t or "").splitlines():
        m = re.match(r"^\s*(非主张|支持|矛盾|未提及)\s*[|｜:：/]?\s*(.*)$", ln)
        if not m:
            continue
        rel, tail = m.group(1), m.group(2)
        ids = []
        for tok in re.findall(r"[A-Za-z]+\d+", tail):
            if tok in known and tok not in ids:
                ids.append(tok)
        order.append((rel, ids))
    for i, c in enumerate(blk):
        if i < len(order):
            got[c] = {"rel": order[i][0], "items": order[i][1]}
        else:
            got[c] = {"rel": "解析失败", "items": []}
    return got


def check_claims_v2(llm, ask: str, ev_index: EvidenceIndex, claims: list,
                    batch: int = 4, model: str = "MiniMax-M3.1-Flash-Preview",
                    max_attempts: int = 3, raw_log: list | None = None) -> dict:
    """逐条判定，**并归因到依据条目编号**。

    返回 {claim: {"rel": 支持/矛盾/未提及/非主张/解析失败, "items": ["E1", ...]}}
    ⚠️ 解析失败必须重试（旧版踩坑：一次 API 抖动静默丢掉一批断言 ⇒ 分母变小、比率被抬高）。
    """
    known = {it["id"] for it in ev_index.items}
    out = {}
    for i in range(0, len(claims), batch):
        blk = claims[i:i + batch]
        lst = "\n".join("%d. %s" % (j + 1, c) for j, c in enumerate(blk))
        got = {}
        for attempt in range(max_attempts):
            try:
                t = llm.chat(CHECK_V2.format(n=len(blk), ask=ask,
                                            ev=ev_index.numbered_text(),
                                            claims=lst),
                             model=model, purpose="check2",
                             max_tokens=1200, budgets=(1800, 2400),
                             min_ok=len(blk) * 3) or ""
            except Exception:
                t = ""
            if raw_log is not None:
                raw_log.append(dict(batch=blk, attempt=attempt, raw=(t or "")[:1500]))
            got = _parse_verdict_lines(t, blk, known)
            if "解析失败" not in {v["rel"] for v in got.values()} and len(got) == len(blk):
                break
        out.update(got)
    return out


# ───────────────────────────────────────── 奖励代理
def proxy_report(ev_index: EvidenceIndex, verd: dict, claims: list) -> dict:
    """算 **Ŵ** 及其配套记账量。

    返回字段：
      w_hat            代理值 ∈ [0,1]（分母 = 承载结论的依据条目数）
      n_anchored       分母
      covered_anchored 分子的锚定条目数
      covered_any      被覆盖的全部条目数（含非锚定，只作记账）
      n_supported      支持的断言条数（**只作记账**，不进奖励）
      n_contradicted   矛盾的断言条数
      conflict_rate    矛盾率 = 矛盾 / (支持 + 矛盾)
      support_rate
      unverified       未核验条数
    """
    anchored = set(ev_index.anchored_ids)
    covered, n_sup, n_con, n_un = set(), 0, 0, 0
    for c in claims:
        v = verd.get(c)
        if not v:
            n_un += 1
            continue
        rel = v["rel"]
        if rel == "支持":
            n_sup += 1
            covered.update(v["items"])
        elif rel == "矛盾":
            n_con += 1
        else:
            n_un += 1
    den = max(len(anchored), 1)
    cov_a = len(covered & anchored)
    legal = n_sup + n_con
    return dict(
        w_hat=cov_a / den,
        n_anchored=len(anchored),
        covered_anchored=cov_a,
        covered_any=len(covered),
        n_supported=n_sup,
        n_contradicted=n_con,
        conflict_rate=(n_con / legal) if legal else 0.0,
        support_rate=(n_sup / legal) if legal else 0.0,
        unverified=n_un,
    )


def terminal_reward(rep: dict, conflict_cap: float = 0.33, alpha: float = 3.0) -> float:
    """终局奖励：Ŵ 的线性映射 **减去** 矛盾率越界的硬罚。

    · Ŵ 有界 ∈[0,1] ⇒ 写更多字不会涨分
    · 矛盾率 > cap ⇒ 罚 2.0（"广度买自错误" ⇒ 代价侧，协议 R1/F4）
    """
    r = alpha * rep["w_hat"]
    if rep["conflict_rate"] > conflict_cap:
        r -= 2.0
    return float(r)
