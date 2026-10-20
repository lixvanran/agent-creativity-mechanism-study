# -*- coding: utf-8 -*-
"""路线 B v2：**编号化依据包** + **协议合规判官** + **训练奖励代理**。

设计理由见 `/workspace/lab/routes/B/DESIGN.md` §3–§4。

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

代理与目标的**已知差距**（DESIGN.md §4.3 有完整表格）：
  * 代理**高估**：协议按"删除反事实"归族 ⇒ 两条不同依据条目若支撑同一结论，
    协议算 1 个维度、代理算 2 个 ⇒ 代理系统性地**偏大**。
  * 代理**只实现 Mednick 合取中的"有用/承重"一半**；"远"（去冗余）由协议 VD
    在**验收层**强制 ⇒ 代理的偏离由 FB6 判死（DESIGN.md §4.6 自查行）。
  * ⇒ 代理是**方向性**训练信号；其与真 VD 的关系必须用**预注册的校准**检验。

**红旗（不可违反）**：本模块读到的 `anchored` 标记与条目总数**只进奖励计算**，
**绝不允许**进入策略特征、绝不进生成侧提示词（DESIGN.md §4.5）。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

REL = ("支持", "矛盾", "未提及", "非主张")

# ───────────────────────────────────────── 依据索引
@dataclass
class EvidenceIndex:
    """一个主题的编号化依据包。

    items: [{id, text, anchored}]，`anchored=True` 表示该条**承载某条结论**
           （对应协议 C1/C3：删掉它 ⇒ 某条结论从可支持变不可支持）
    conclusion_space: 该题的结论空间 C_t（协议 §4.6：**判官必须拿到**）
    """
    topic_id: str
    ask: str
    items: list = field(default_factory=list)
    conclusion_space: list = field(default_factory=list)

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

    def ct_text(self) -> str:
        if not self.conclusion_space:
            return "（本题未提供结论空间）"
        return "\n".join("- %s" % c for c in self.conclusion_space)


def load_index(path: str) -> dict:
    """{topic_id: EvidenceIndex}"""
    raw = json.load(open(path, encoding="utf-8"))
    out = {}
    for t in raw["topics"]:
        out[t["topic_id"]] = EvidenceIndex(t["topic_id"], t["ask"], t["items"],
                                           t.get("conclusion_space", []))
    return out


# ───────────────────────────────────────── 判官（协议 §4.6 合规 + 带条目归因）
# ⚠️ 三句强制条款（协议 §4.6:522-524）**逐字写死**，不得改写、不得删减：
#   ① 只要陈述里含有超出问题本身的信息（数字/阈值/名称/规则/主体关系/比较/归类），就当它是断言
#   ② 由题面数值 + 依据包规则推导出的结论，是断言，不是复述
#   ③ 不确定时一律答『未提及』
# ⚠️ 示例**只能是协议 §4.6 给的两条合成示例**（禁止写入 U1–U4 的任何内容）。
# ⚠️ 判官**必须拿到题面与结论空间 C_t**（协议 §4.6:526）⇒ 提示词里也**逐字**写死这一句，
#    且 C_t 通过 `{ct}` 槽**真的**传进去（`check_claims_v2` 传 `ev_index.ct_text()`）。
#
# ★ 2026-10-21（F5 修复）：第 ① 句改成与协议**同一个 markdown 强调位置**，
#   使「去掉 markdown 标记后逐字相同」与「带标记逐字相同」两种判法都成立；
#   并补上协议 §4.6:526 的「判官必须拿到题面（prompt）与结论空间 C_t」一句。
#   ⇒ 判官提示词版本变更 ⇒ **判官缓存身份变化**（DESIGN §2.4 第 4 行）。
CHECK_V2_VERSION = "routeB-judge-v2-protocol-4.6-2026-10-21"
CHECK_V2 = """下面是一份**编号的依据条目**、一个**问题（题面 prompt）**、一份**结论空间 `C_t`**，
之后列出若干条**待核验的陈述**。

判官**必须拿到题面**（`prompt`）与结论空间 `C_t`：缺了题面或 C_t 就无法判断"是不是复述"
⇒ 判官必须拿到题面（prompt）与结论空间 `C_t`，二者缺一不可。
（本题的题面见「问题」一节，结论空间见「结论空间」一节；两者都已完整给出。）

分两步判断。

第一步：这条陈述是不是**断言**？
- 只要陈述里含有**超出问题本身**的信息（数字/阈值/名称/规则/主体关系/比较/归类），就当它是断言。
- **由题面数值 + 依据包规则推导出的结论，是断言，不是复述**。
- 只有「纯复述题面且不产生任何超出题面的推论」才不是断言（关系填「非主张」）。
- 如果这条陈述与下面**结论空间**中的某一条有关，**它就是断言**（哪怕措辞像在复述题面）。
- 示例（合成示例，与任何真实题目无关）：
  「每件包裹运费 8 元、满 3 件每件减 2 元 ⇒ 3 件应付 18 元」这种由题面数值 + 规则推得的
  算术结论是**断言**，不是复述；
  「评分表规定 ≥ 80 为优 ⇒ 本项 92 分应归为优」这种推导型归类也是**断言**。

第二步：对是断言的陈述，判断它与依据条目的关系，只回答一个词：
- 「支持」：依据条目明确认可或蕴含该条。**改写、简称、换词但含义相同，也算支持。**
- 「矛盾」：依据条目明确讲了与之相反的内容。
- 「未提及」：依据条目没有讲到，或讲的是别的事。**不确定时一律答『未提及』。**

一共输出**{n} 行**（与待核验陈述的条数相同），每行格式固定为：`关系 | 条目编号`。
- 关系为「支持」或「矛盾」时，条目编号填依据条目里真正对应的那一条的编号
  （一条陈述可能被多条支持，用逗号分隔，如 `支持 | E1,E3`）。
- 关系为「未提及」或「非主张」时，条目编号填 `-1`。
- **不要加编号、不要写解释、不要写任何其它文字。**

问题：
{ask}

结论空间（本题允许成立的结论清单）：
{ct}

依据条目：
{ev}

待核验的陈述：
{claims}"""

# 严格解析：**分隔符必需**；未知编号 ⇒ 解析失败；尾部垃圾 ⇒ 解析失败
_LINE = re.compile(r"^\s*(非主张|支持|矛盾|未提及)\s*([|｜:：/])\s*(.*?)\s*$")
_IDS = re.compile(r"[A-Za-z]+\d+")
_EMPTY_OK = {"-1", "-", "无", "none", "None", ""}


def _parse_verdict_lines(t: str, blk: list, known: set) -> dict:
    """**严格**逐行解析。

    严格在哪（DESIGN.md §10.1 / F8 修复）：
      ❶ 分隔符 `|` **必需** ⇒ 「支持 E1」（无分隔符）判**解析失败**，不静默接受
      ❷ 「支持 | E99」（引用不存在的条目）判**解析失败** ⇒ 不会让
         `n_supported` / `support_rate` 虚高、`conflict_rate` 被压低
      ❸ 尾部垃圾（「支持 | E1 blah blah」）判**解析失败**
      ❹ 前言/解释行**不会**被误配（只认「行首是关系词 + 分隔符」的行）
    ⚠️ 解析失败**不计入**任何分子/分母，但**必须**计入 `parsefail_rate`（协议 E1/F8）。
    """
    got, order = {}, []
    for ln in (t or "").splitlines():
        m = _LINE.match(ln)
        if not m:
            continue
        rel, _sep, tail = m.group(1), m.group(2), m.group(3)
        if rel in ("支持", "矛盾"):
            ids = _IDS.findall(tail)
            if not ids:
                continue                      # 没有编号 ⇒ 不是合法行（交由行数不符触发重试）
            if any(i not in known for i in ids):
                # 引用了不存在的条目 ⇒ **判解析失败**（不得当作"支持但没归因"）
                order.append(("解析失败", []))
                continue
            # 尾部垃圾检查：去掉合法编号与分隔符后不应剩下别的 token
            if _IDS.sub("", tail).strip(" ,，;；"):
                order.append(("解析失败", []))
                continue
            order.append((rel, list(dict.fromkeys(ids))))
        else:
            if tail.strip() not in _EMPTY_OK:
                order.append(("解析失败", []))
                continue
            order.append((rel, []))
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
    ⚠️ 判官**必须拿到题面与 C_t**（协议 §4.6:526）⇒ 这里传 `ev_index.conclusion_space`。
    """
    known = {it["id"] for it in ev_index.items}
    out = {}
    for i in range(0, len(claims), batch):
        blk = claims[i:i + batch]
        lst = "\n".join("%d. %s" % (j + 1, c) for j, c in enumerate(blk))
        got = {}
        for attempt in range(max_attempts):
            try:
                t = llm.chat(CHECK_V2.format(n=len(blk), ask=ask, ct=ev_index.ct_text(),
                                            ev=ev_index.numbered_text(), claims=lst),
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
