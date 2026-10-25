# -*- coding: utf-8 -*-
"""`VD_anchor_out` · 锚外新增维度数 —— 立论的第一个可失败量。

> 2026-10-22 ｜ 第二组（设计路线 / 层2 + 层1）｜ 实现落点：`routes/COLLAPSE/eval/`
> 依据：`routes/RESEARCH-BOUNDARY-2026-10-22.md` §2（生成侧不设限，判定侧分两路）、
>      `routes/PROTOCOL.md` §1.3–§1.7（承重检验 / 去冗余 / 族签名）、§4.6–§4.8（核验器 / 成本闸门）
> 禁止范围：**不改** `routes/COLLAPSE/workflow.py`、**不改** `batch-U1/measure.py` 的判据、
>      **不改** `routes/DEV/`、**不碰** `routes/COLLAPSE/runs/` 既有结果。

---

## 0. 这个数是什么，为什么必须存在

我们协议 §1.3 的 **C3** 写死：「结论空间 `C_t` 之外的一切，一律不算维度」。
`C_t` 是**人事前写死**的 ⇒ 所以我们现在做的不是"发现原先未被纳入的问题空间"，
是"在人事前划好的答案空间里检索得更全" ⇒ 评审一句「你只是填空」，立论就废。

⇒ **解法**（`RESEARCH-BOUNDARY-2026-10-22.md` §2）：
**`C_t` 从"发现空间的边界"降级为"锚（anchor）"** —— 生成侧本来就不受 `C_t` 约束
（`C_t` 只进判官），所以要动的只有**判定侧**：

| 通道 | 判据 | 读数 |
|---|---|---|
| **IN（锚内）** | **原封不动**沿用 `measure.py` 的判官提示与判定流水线 | `VD_anchor_in`（历史可比） |
| **OUT（锚外）** | 锚内全部条件 **+** 岔口可指名（**两个独立探针**）**+** leave-one-out 独立（族级）**+** 影响矩阵被引用 | `VD_anchor_out` |

> ★ **`VD_anchor_out` 是立论的可检验量。若它在所有臂 / 所有题上恒为 0 ⇒
> 立论当场不成立**（我们做的是检索，不是发现）。本文件把这条写成**代码里的硬闸门**，
> 不是文档里的一句话。

---

## 1. 为什么要开**两条独立通道**（而不是一条判官同时判锚内锚外）

1. **锚内读数必须与历史可比**：改判官提示 ⇒ 全部历史读数作废（`REPORT-cmp8-2026-10-20.md` §2.3
   实测：同一批答案换提示词版本，承重数分布就变）。⇒ 锚内通道**必须**逐字沿用
   `batch-U1/measure.py` 的 `CARD_Q` 与判定流水线，**一个字节都不改**。
2. **同源同判会污染**：一条判官提示同时问"它在不在锚内"和"它在不在锚外"，两个条件会互相污染
   （锚外的宽松口径会抬高锚内计数，锚内的严格口径会压低锚外计数）。
   ⇒ **两条通道用两个提示、两次独立判定**，互不可见。
3. **成本**：抽取（EXTRACT）只做一次，两条通道复用同一批断言 ⇒ 判官调用 = 2×，抽取 = 1×。

---

## 2. 锚外闸门（AO-GATE）—— 锚外的门槛必须**严于**锚内

一条卡要算作**一个锚外维度**，必须**同时**满足：

| # | 条件 | 判定方式 | 为什么 |
|:-:|---|---|---|
| **A1** | 是断言（不是复述题面） | 判官 `is_claim` | 花絮不是维度 |
| **A2** | 承重：改变了一个**具体**决策 | 判官 `load_bearing` + `decision_changed` | 承重检验的本体 |
| **A3** | 那个决策**不在** `C_t` 里 | 判官 `anchor=out` **且** 机械复核：`decision_point_out` 不含任何 `C_t` 编号 | C3 的反向：**要出界，但不能乱出界** |
| **A4** | 岔口**可指名** | ★ **独立第二次判官调用**（只看这条卡 + `C_t` 清单）：它是否改变了一个具体决策？该决策是否确实不在清单里？ | 防"锚外闸门被钻空子"（`RESEARCH-BOUNDARY` R1） |
| **A5** | **leave-one-out 独立** | ① 卡片级（机械、零成本）：同一岔口归族后**只算 1 个维度**（协议 §1.4 族语义）⇒ 删掉整族，决策集合变小；② 证据级（可选）：从生成侧移除它引用的依据条目后重生成，该决策是否随之消失 | ⚠️ **归因更正（2026-10-22 文献核证）**：「某条信息 = 独立维度 = 拿掉它之后结论是否改变」**不是** Curiosity Search / Novelty Search 的定义（两篇全文都没有这个概念，也没有 "leave-one-out" 这个词）。可借的只是 Curiosity Search §"Do Doors Represent Distinct Skills?" 的**反事实范式**（PMC5010182）。⇒ **本判据是本项目自造的**，引用时必须自己承担，不得挂在论文名下 |
| **A6** | 影响矩阵里**被引用** | 它引用了依据包里真实存在的 `EV-xx`，**或** 它 `self_contained=true`（自带推理链） | ⚠️ **归因更正（2026-10-22 文献核证）**：MAME（EAAI 2026 164:113126）可读正文是 **agent×agent** 的 *dynamic confidence matrix* + *answer credibility score*，**"依据 ID" 与 "agent×依据" 在 MAME 里查不到**（且它**保留**自报置信度，与我们"换成依据 ID"的说法相反）。⇒ 本矩阵是**本项目自造**；可借的只是 MAME 的**矩阵形态**与"用离散引用 ID 做归因、而不是用自报置信度"这个方向 |
| **A7** | **不是矛盾卡** | `verdict != 矛盾` | 矛盾进 R1 分子，不进维度数（协议 §2.3） |
| **A8** | 判官**解析成功** | `parse_ok` | 解析失败必须独立计数（协议 §4.7 E1） |

> ⚠️ **A5② 的诚实边界**：锚外卡常常 `basis=model`（模型自生知识，**没有** `EV` 可引）。
> 这时证据级 leave-one-out **不适用** ⇒ 只能做卡片级 ⇒ 读数必须**分栏报**
> （`VD_anchor_out` 里 `basis=evidence` 与 `basis=model` 各多少），
> **不许把卡片级的结果说成"通过了 leave-one-out"**。

### 2.1 结构性绑定：为什么不用措辞相似度

leave-one-out 要判断"两条卡是不是在讲同一个岔口"。**本项目已实测：措辞级相似度不可用**
（keep-Jaccard 地板 0.000；2-gram Jaccard 判 9 条有 2 条假阴性）⇒ **禁止用字符 n-gram 绑定岔口**。

⇒ 本实现用**结构化绑定**：
1. 判官在每条卡上写 `decision_point_out`（自由文本，描述岔口）；
2. **第二次独立调用**做**岔口归并**：把这些自由文本归并成 `K1/K2/...` 的**封闭枚举**；
3. 同一 `K` ⇒ 同一个岔口 ⇒ 归族 ⇒ **一族 = 1 个维度**（与协议 §1.4 同构）。

⇒ 归并是**分类任务**（不是质量判断）⇒ 循环污染风险显著低于"让判官直接评好不好"。

---

## 3. 读数（两栏 + 绝对分母，缺任一项 ⇒ 该臂结果无效）

```
VD_anchor_in   锚内承重族数（与 measure.py 等价，历史可比）
VD_anchor_out  锚外维度数（通过 AO-GATE 的岔口数）
VD_net_in / VD_net_out   相对基线臂、**同 rep 配对**的双边净增益
```

必带的绝对条数（协议 §3.1 + §4.9）：
`n_claims` / `n_cards` / `n_load_bearing_in` / `n_load_bearing_out` /
`n_anchor_out_gated` / `n_rejected_by_gate`（**按 A1–A8 逐条分解**） /
`D_in` / `parsefail_rate` / `valid/total` / `silent_empty_count` / `judge_same_vendor` /
`measure_version` / `judge_model` / `judge_prompt_version` / `judge_temp`

> ★ **比率一律配绝对分母**（协议 §3.1 末段：本项目踩过"矛盾率 0% 其实分母为空"）。
> ★ **失败不许静默变 0**（协议 §4.7）：解析失败 / 空串 / 预算截断**各自独立计数并落盘**。

---

## 4. 用法

```bash
# 4.1 自检闸门（不过 ⇒ 拒绝出数，协议 F7）
python3 vd_anchor_out.py selftest --dev routes/DEV

# 4.2 与 measure.py 的锚内通道**逐字段等价**校验（不改 measure.py，只调用它）
python3 vd_anchor_out.py verify-equivalence --answer <answer.md> --task D01

# 4.3 单份答案 → 两栏读数
python3 vd_anchor_out.py measure --task D01 --answer <answer.md>

# 4.4 一批答案 → 读数表 + 影响矩阵
python3 vd_anchor_out.py batch --manifest <manifest.json> --out <outdir>

# 4.5 影响矩阵导出（agent×依据 / 臂×依据）
python3 vd_anchor_out.py matrix --out <outdir>
```

## 5. 依赖
- 只用 Python 标准库 + 两个 HTTP 端点（MiniMax 订阅 / OpenRouter）。
- `batch-U1/measure.py` **只被 import 调用**（`CARD_Q` / `EXTRACT_Q` / `measure_answer`），
  **不被修改**。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ──────────────────────────────────────────────────────────────
# 0. 路径
# ──────────────────────────────────────────────────────────────
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
COLLAPSE_DIR = os.path.dirname(EVAL_DIR)          # routes/COLLAPSE
ROUTES_DIR = os.path.dirname(COLLAPSE_DIR)         # routes
CMP8_DIR = os.path.dirname(ROUTES_DIR)             # docs/cmp8
BATCH_U1_DIR = os.path.join(CMP8_DIR, "batch-U1")
DEV_DIR = os.path.join(ROUTES_DIR, "DEV")

if BATCH_U1_DIR not in sys.path:
    sys.path.insert(0, BATCH_U1_DIR)

# `measure.py` 被 import（只读，不改）；它的 import 依赖 `u1_lib`。
import measure as MEASURE  # noqa: E402  (必须在 sys.path 设置之后)

# ──────────────────────────────────────────────────────────────
# 1. 版本与不变量
# ──────────────────────────────────────────────────────────────
VD_VERSION = "vd_anchor_out-v1-2026-10-22"
IN_CHANNEL_VERSION = "in-channel ≡ measure.py@" + MEASURE.MEAS_VERSION
OUT_PROMPT_VERSION = "anchor-card-v1-2026-10-22"
FORK_PROMPT_VERSION = "anchor-fork-v1-2026-10-22"

# 协议 §4.2：MiniMax-M3.1-Flash-Preview 强制 adaptive thinking，
# `max_tokens=2000/4000` **必然失败**（思考块吃光预算 ⇒ 正文空 ⇒ 静默返回空串）。
# ⇒ 阶梯必须从 8000 起。
MM_TOKEN_FLOOR = 8000
#: 判官预算阶梯（2026-10-22 实测修正）：
#: 8000 起步是协议 §4.2 的硬规定（2000/4000 **必然失败**）。
#: 但**长提示词**（12 条依据 + 10 条断言 + 锚外提示词）会让 MiniMax 的
#: adaptive thinking **烧光 8000/12000/16000 三档** ⇒ 卡片解析 **100% 失败**
#: （实测 `W_div#D05`：claims=10、cards=0、parsefail=1.0）⇒
#: ⇒ 阶梯必须**再加两档**，否则长题会整片作废。
JUDGE_BUDGETS = (12000, 20000, 28000)
MIN_CLAIM_LEN = 8
MAX_CLAIM_LEN = 120
MAX_CLAIMS = 12
JUDGE_BATCH = 8

# 岔口归并纯度（在 DEV 金标上实测，见 selftest_fixtures.tier_b）：
# 同标签的卡被归到同一岔口的比例。纯度 < 1 ⇒ **存在碎片化** ⇒
# 同一个维度被拆成多个岔口 ⇒ `VD_anchor_out` **偏高**（高估）。
# ⇒ 修正估计 = 原始值 × 纯度（★ 这是从锚内卡**外推**到锚外卡的估计，不是实测）。
FORK_PURITY_EST = 0.808


# ──────────────────────────────────────────────────────────────
# 2. 双厂商 LLM 客户端（零依赖；失败必须可计数）
# ──────────────────────────────────────────────────────────────
class CallLog:
    """逐次调用的账本。协议 §4.3：必须记 `finish_reason` + 完成 token 数，
    否则事后**无法区分"臂写得短"与"预算烧光被截断"。**"""

    def __init__(self) -> None:
        self.rows: List[Dict[str, Any]] = []

    def add(self, **kw: Any) -> None:
        self.rows.append(kw)

    def summary(self) -> Dict[str, Any]:
        n = len(self.rows)
        empty = sum(1 for r in self.rows if r.get("content_len", 0) == 0)
        trunc = sum(1 for r in self.rows if r.get("finish_reason") == "length")
        err = sum(1 for r in self.rows if str(r.get("finish_reason", "")).startswith("error"))
        return {
            "n_calls": n,
            "n_empty_content": empty,          # ★ 静默返回空串（§4.7 E3）
            "n_truncated": trunc,              # ★ 预算烧光被截断（§4.7 E4）
            "n_error": err,
            "total_tokens": sum(int(r.get("total_tokens") or 0) for r in self.rows),
            "completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in self.rows),
            "n_with_reasoning": sum(1 for r in self.rows if int(r.get("reasoning_len") or 0) > 0),
        }


class LLM:
    """统一接口 `chat(prompt, model=, temp=, max_tokens=, budgets=, min_ok=, purpose=)`
    —— 与 `batch-U1/u1_lib.py` 的 `_BaseLLM.chat` **同签名**，
    以便直接喂给 `measure.measure_answer` 做等价性校验。"""

    def __init__(self, vendor: str, model: str, log: Optional[CallLog] = None,
                 effort: Optional[str] = None) -> None:
        self.vendor = vendor
        self.model = model
        self.log = log or CallLog()
        # ★ 实例级默认 effort（2026-10-23）：让**整条管线**用同一档，
        #   而不是"卡片调用低档、探针调用默认 max"这种半低半高（那会让标定不可比）。
        self.effort = effort
        self._cache: Dict[Tuple[str, str, float, int], str] = {}
        if vendor == "minimax":
            self.base = os.environ.get("MM_BASE_URL", "https://api.minimaxi.com/v1").rstrip("/")
            self.key = os.environ.get("MINIMAX_SUBSCRIPTION_KEY", "")
        elif vendor == "openrouter":
            self.base = os.environ.get("OR_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
            self.key = os.environ.get("OPENROUTER_API_KEY", "")
        else:
            raise ValueError("unknown vendor: %s" % vendor)
        if not self.key:
            raise RuntimeError("缺少密钥：%s" % vendor)

    # ---- 传输层 ----
    def _post(self, url: str, payload: Dict[str, Any], timeout: int = 240) -> Dict[str, Any]:
        import urllib.error
        import urllib.request

        headers = {"Authorization": "Bearer " + self.key, "content-type": "application/json"}
        if self.vendor == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/lixvanran/agent-creativity-mechanism-study"
            headers["X-Title"] = "vd-anchor-out-2026-10-22"
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())

    def chat(self, prompt: str, *, model: Optional[str] = None, temp: float = 0.0,
             max_tokens: int = MM_TOKEN_FLOOR, budgets: Sequence[int] = (),
             min_ok: int = 20, purpose: str = "",
             effort: Optional[str] = None) -> str:
        """★ `effort`（2026-10-23 加）：MiniMax 的**思考深度**档位。

        ⇒ 官方文档（platform.minimax.io）：`effort` ∈ low/medium/high/xhigh/max，
          **省略时默认 = max**；且 *"Thinking cannot be turned off... To reduce the
          latency and token usage of thinking, **lower the effort level**"*。
        ⇒ 之前我们用**加 max_tokens 阶梯**去救截断（方向错）⇒ 44% 调用空内容。
        ⇒ 正确解法是**降 effort**。★ 本参数只影响 minimax；openrouter 忽略。
        """
        m = model or self.model
        key = (m, prompt, temp, max_tokens, effort)
        if key in self._cache:
            return self._cache[key]
        ladder = [max_tokens] + [b for b in budgets]
        if self.vendor == "minimax":
            # §4.2：2000/4000 必然失败 ⇒ 阶梯从 8000 起
            ladder = [max(x, MM_TOKEN_FLOOR) for x in ladder]
        last = ""
        t0 = time.time()
        for mt in ladder:
            try:
                payload: Dict[str, Any] = {
                    "model": m,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temp,
                    "max_tokens": mt,
                }
                eff = effort or self.effort
                if eff and self.vendor == "minimax":
                    # ★ 官方参数名：OpenAI 兼容路径用 reasoning_effort
                    payload["reasoning_effort"] = eff
                d = self._post(self.base + "/chat/completions", payload)
                ch = (d.get("choices") or [{}])[0]
                msg = ch.get("message") or {}
                raw = msg.get("content") or ""
                # ★ 思考块单独长度（OpenAI 兼容协议：思考在 reasoning_content）
                rc_len = len(msg.get("reasoning_content") or "")
                last = self._strip(raw)
                fr = ch.get("finish_reason", "")
                u = d.get("usage") or {}
                self.log.add(vendor=self.vendor, model=m, purpose=purpose, max_tokens=mt,
                             finish_reason=fr, content_len=len(last),
                             reasoning_len=rc_len, effort=eff or "(default=max)",
                             prompt_tokens=int(u.get("prompt_tokens") or 0),
                             completion_tokens=int(u.get("completion_tokens") or 0),
                             total_tokens=int(u.get("total_tokens") or 0),
                             secs=round(time.time() - t0, 2))
                if fr == "length":
                    continue                       # 预算烧光 ⇒ 升档重来（**不静默**）
                if len(last) < min_ok:
                    continue                       # 空/过短 ⇒ 升档重来（**不静默**）
                self._cache[key] = last
                return last
            except Exception as e:                  # noqa: BLE001
                code = getattr(e, "code", None)
                body = ""
                try:
                    body = e.read().decode()[:200]  # type: ignore[attr-defined]
                except Exception:                   # noqa: BLE001
                    pass
                self.log.add(vendor=self.vendor, model=m, purpose=purpose, max_tokens=mt,
                             finish_reason="error:%s" % type(e).__name__, content_len=0,
                             status=code, body=body, secs=round(time.time() - t0, 2))
                # 429 属于可重试（第四组实测：并发 8 触发 429 ⇒ 36 次调用整片失败）
                if code == 429:
                    for wait in (20, 40, 60):
                        time.sleep(wait)
                        continue
                    last = ""
                    break
                time.sleep(2.0)
        return last

    @staticmethod
    def _strip(raw: str) -> str:
        raw = raw or ""
        raw = re.sub(r"^.*?</think>", "", raw, flags=re.S)
        return raw.strip()


# ──────────────────────────────────────────────────────────────
# 3. 提示词
# ──────────────────────────────────────────────────────────────
# 锚内通道：**逐字使用** `measure.CARD_Q`（不重写、不改一个字）⇒ 锚内读数历史可比。
CARD_Q_IN = MEASURE.CARD_Q
EXTRACT_Q = MEASURE.EXTRACT_Q

# 锚外通道：判据一/二/三与锚内**逐字相同**，只**追加**「锚内还是锚外」与
# 「依据来源 / 是否自带推理链」两个字段。锚内卡在本通道里**不用于** VD_anchor_in。
CARD_Q_OUT = """下面是一份「依据条目 / 结论空间」清单（**同一份事实，编号即结论编号**）、一个问题，
以及若干条候选陈述。请对**每条**候选陈述逐条判断。

问题：
{ask}

依据条目与结论空间（编号即结论编号）：
{ev}

候选陈述：
{claims}

对每条候选陈述，输出**一行 JSON**，字段如下（不要输出别的任何内容）：

{{"i": <候选编号>,
 "is_claim": true/false,          ← 只复述了问题里给出的情形 ⇒ false
 "verdict": "支持"/"矛盾"/"未提及"/"非主张",
 "evidence_ref": "EV-07",          ← verdict 为 支持/矛盾 时必填（依据条目编号）；否则填 null
 "evidence_class": "事实"/"推论"/"价值判断"/"建议",
 "load_bearing": true/false,       ← 见下方承重检验
 "decision_changed": "<它改变了哪个决策/结论；写不出来就填空字符串>",
 "supports_conclusions": [<结论编号>...],   ← 该陈述支撑清单里哪几条结论；支撑不了就填 []
 "maps_to_question": true/false,
 "anchor": "in"/"out",             ← 它改变的决策**在**清单里 ⇒ in；**不在**清单里 ⇒ out
 "decision_point_out": "",         ← anchor=out 时必填：清单外的那个**具体**决策到底是什么（写成可复述的岔口）
 "basis": "evidence"/"prompt"/"model",  ← 支撑来源：依据条目 / 题面已给 / 模型自生
 "self_contained": true/false}}    ← anchor=out 时：这条陈述是否**自带推理链**（给了原因/条件/后果），不靠读者自己补

**判据一 · 是不是断言**：只要陈述里含有**超出问题本身**的信息（数字/阈值/名称/规则/主体关系/比较/归类），
就当它是断言；**由问题里的数值加上依据规则推导出的结论，是断言，不是复述**。只复述情形的，is_claim=false。

**判据二 · 关系**：依据条目明确认可或蕴含该条 ⇒「支持」（改写、简称、换词但含义相同也算支持）；
依据条目明确讲了相反的内容（数字对不上、阈值不同、方向相反）⇒「矛盾」；
依据没讲到或讲的是别的事 ⇒「未提及」。**不确定时一律答「未提及」。**

**判据三 · 承重检验（最重要）**：这条陈述**改变了一个决策或结论**吗？
- 它必须能指向上面清单里的**某一条具体结论编号**，并说明「没有它，结论就不成立/就不同」；
- **写不出「改变了哪个决策/结论」⇒ load_bearing=false**（哪怕它是真的、哪怕依据支持它）。
- 复述、铺陈、寒暄、免责、延伸感想 ⇒ load_bearing=false。

**判据三之补 · 锚内还是锚外（只针对承重陈述）**：清单里没有写这个决策，**不等于**它不承重。
- 如果它改变的是清单里已有的某条结论 ⇒ `anchor="in"`，`supports_conclusions` 填对应编号，`decision_point_out` 留空。
- 如果它改变的是**清单之外**的一个决策（清单漏掉的那个岔口）⇒ `anchor="out"`，
  `supports_conclusions` 填 `[]`，并且**必须**在 `decision_point_out` 里把这个岔口写具体：
  「在什么前提下、做什么动作、做成什么样 / 判成哪一类」——写不具体就判 `load_bearing=false`。
- **只有**泛泛的建议、铺陈、感想、免责声明才是 `load_bearing=false`；清单没覆盖 **不构成** 非承重的理由。

**判据四 · 证据类别**：陈述本身是「事实」（可核验的既有信息）/「推论」（由事实推出）/「价值判断」（好坏取舍）/「建议」（行动提议）。

一行一条 JSON，顺序对应，不要解释，不要补充。
"""

# 岔口归并（结构化绑定，替代措辞相似度）
FORK_Q = """下面是一份**同一份答案**里抽出的若干条陈述。每条都声称自己改变了一个「决策岔口」。
请把这些岔口**归并**：改变的是**同一个岔口**的陈述归到同一个岔口；不同的岔口分开。

陈述列表：
{claims}

输出**若干行 JSON**（每行一个岔口），不要输出别的内容：
{{"fork": "K1", "cards": [<陈述编号>...], "label": "这个岔口到底是什么（一句，20 字以内）"}}

规则：
- 每条陈述**必须**且**只能**属于一个岔口；一个陈述都不许漏。
- 编号沿用上面的陈述编号。
- 宁可多合也不要拆：只有在**做的决策根本不同**时才分成不同岔口。
"""


# ──────────────────────────────────────────────────────────────
# 4. 基础工具
# ──────────────────────────────────────────────────────────────
def cjk_ratio(text: str) -> float:
    """中文占比（协议附录式语言闸门：任何基于字符 n-gram 的判据，跑前先过语言闸门）。"""
    if not text:
        return 0.0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    letters = sum(1 for ch in text if ch.isalpha())
    return cjk / max(letters, 1)


def norm_id(x: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "", str(x or "")).upper()


def norm_ref(x: Any) -> str:
    """**编号归一化（数字部分不补零）**。

    ⚠️ 这是踩过的坑：依据包里的 id 是 `EV-01`，而模型在答案里常写 `EV-1` / `EV-2` / `EV-02`
    ⇒ 直接做字符串比较 ⇒ `EV-2 ≠ EV-02` ⇒ **A6 闸门会把"已引用依据"误判成"没引用"** ⇒
    锚外维度被静默清零（而且**读数看起来正常**）。
    ⇒ 所以编号一律拆成「前缀 + 数字」再比：`EV-2` / `EV-02` ⇒ `EV:2`。
    """
    s = str(x or "").strip()
    if not s:
        return ""
    m = re.match(r"^\s*([A-Za-z]{0,4})\s*[-_#]?\s*(\d+)\s*$", s)
    if m:
        return "%s:%d" % (m.group(1).upper(), int(m.group(2)))
    return norm_id(s)


def sha(obj: Any) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()[:16]


def load_devset(dev_dir: str = DEV_DIR) -> Dict[str, Any]:
    with open(os.path.join(dev_dir, "devset.json"), encoding="utf-8") as f:
        return json.load(f)


def dev_task(devset: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    for t in devset.get("tasks", []):
        if t.get("task_id") == task_id:
            return t
    raise KeyError("DEV 里没有题 %s" % task_id)


def evidence_items_from_dev(task: Dict[str, Any]) -> List[Dict[str, str]]:
    """DEV 集的依据包。

    ⚠️ 两种形态都要认：
    - **list**（DEV 现状）：`[{"id": "EV-01", "text": ..., "source": {...}}]` ⇒ **原样取用**
      （条目 id 已经与金标卡的 `evidence_ref` 对齐 ⇒ 不重新编号）；
    - **str**（U1 批次的形态）：一整段文本 ⇒ 按中文句末标点切成原子事实（与
      `u1_lib.split_facts` 同口径），id 形如 `EV-01`。
    """
    ev = task.get("evidence")
    if isinstance(ev, list):
        out = []
        for i, e in enumerate(ev):
            if isinstance(e, dict):
                out.append({"id": e.get("id") or ("EV-%02d" % (i + 1)),
                            "text": (e.get("text") or "").strip()})
            else:
                out.append({"id": "EV-%02d" % (i + 1), "text": str(e).strip()})
        return [e for e in out if e["text"]]
    parts = re.split(r"(?<=[。！？；])", ev or "")
    out = []
    for i, p in enumerate(parts):
        p = (p or "").strip()
        if p:
            out.append({"id": "EV-%02d" % (i + 1), "text": p})
    return out


def ct_of_dev(task: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"id": c["id"], "text": c["text"]} for c in task.get("conclusion_space", [])]


# ──────────────────────────────────────────────────────────────
# 5. 抽取（与 measure.py 同口径：同提示、同过滤、同上限）
# ──────────────────────────────────────────────────────────────
def extract_claims(llm: LLM, answer: str, model: str) -> List[str]:
    raw = llm.chat(EXTRACT_Q.format(t=(answer or "")[:3000]), model=model, temp=0.0,
                   max_tokens=MM_TOKEN_FLOOR, budgets=JUDGE_BUDGETS, min_ok=10, purpose="extract")
    claims: List[str] = []
    for ln in (raw or "").splitlines():
        ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
        if MIN_CLAIM_LEN <= len(ln) <= MAX_CLAIM_LEN:
            claims.append(ln)
    return list(dict.fromkeys(claims))[:MAX_CLAIMS]


def parse_card_lines(raw: str, n_expected: int) -> List[Dict[str, Any]]:
    """解析判官返回的 JSONL。★ 解析失败**独立计数**（协议 §4.7 E1），
    绝不让它静默变成"0 张卡 ⇒ 这条臂没有维度"。"""
    out: List[Dict[str, Any]] = []
    n_bad = 0
    for i, ln in enumerate((raw or "").splitlines()):
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            d = json.loads(ln)
        except Exception:                        # noqa: BLE001
            n_bad += 1
            continue
        if not isinstance(d, dict):
            n_bad += 1
            continue
        # ★ 索引容错（2026-10-23 修）：判官偶尔把 "i" 写成**字符串**（如 "3"）
        #   ⇒ 原先 `int(d.get("i"))` 直接抛 ValueError ⇒ **整份答案的测量全灭**
        #   （实测：effort_sweep 27 个作业里 2 个这样死掉 ⇒ 7% 作业失败率）
        # ⇒ 现在：能转就转；转不了就**按行序兜底**并**标记**（不静默）。
        try:
            d["i"] = int(d.get("i"))
        except (TypeError, ValueError):
            d["i"] = i + 1
            d["i_fallback"] = True
        sc = d.get("supports_conclusions") or []
        d["supports_conclusions"] = [int(x) if str(x).strip().isdigit() else str(x) for x in sc]
        out.append(d)
    for d in out:
        d["parse_ok"] = True
    return out


# ──────────────────────────────────────────────────────────────
# 6. 锚内通道（等价于 measure.py 的判定流水线）
# ──────────────────────────────────────────────────────────────
def _batch_size(ev_text: str, n_claims: int) -> int:
    """**自适应批大小**：提示词越长、批越小 ⇒ 降低"思考块吃光预算"的概率。

    ★ 2026-10-22 实测：12 条依据 + 10 条断言用批 8 ⇒ 解析 100% 失败；
      同一批拆成 4 ⇒ 正常。⇒ 批大小是**成本/可靠性的旋钮**，不是常数。
    """
    budget = len(ev_text) + n_claims * 60
    if budget > 2600:
        return 4
    if budget > 1600:
        return 6
    return JUDGE_BATCH


def judge_in_channel(llm: LLM, ask: str, ev_text: str, claims: List[str],
                     model: str) -> Dict[str, Any]:
    """**逐字复刻** `measure.measure_answer` 的第 2–3 步：同一 `CARD_Q`、同批大小 8、
    同一承重过滤、同一贪心去冗余 ⇒ 读数与 `measure.py` 等价（由 `verify-equivalence` 实证）。"""
    cards: List[Dict[str, Any]] = []
    n_parsefail = 0
    bs = _batch_size(ev_text, len(claims))
    for i in range(0, len(claims), bs):
        b = claims[i:i + bs]
        lst = "\n".join("%d. %s" % (n + 1, b[n]) for n in range(len(b)))
        got: List[Dict[str, Any]] = []
        for mt, buds in ((MM_TOKEN_FLOOR, JUDGE_BUDGETS),):
            r = llm.chat(CARD_Q_IN.format(ask=ask, ev=ev_text, claims=lst),
                         model=model, temp=0.0, max_tokens=mt, budgets=buds,
                         min_ok=len(b) * 15, purpose="card_in")
            got = parse_card_lines(r, len(b))
            if len(got) >= len(b):
                break
        n_parsefail += max(0, len(b) - len(got))
        for g in got:
            g["claim"] = b[g["i"] - 1] if 1 <= g["i"] <= len(b) else ""
            cards.append(g)

    lb = [c for c in cards
          if c.get("is_claim") and c.get("load_bearing") is True
          and c.get("decision_changed") and c.get("supports_conclusions")]
    kept, seen = [], set()
    n_redundant = 0
    for c in lb:
        new = set(c["supports_conclusions"]) - seen
        if new:
            kept.append(c)
            seen |= new
        else:
            n_redundant += 1
    return {
        "n_cards": len(cards),
        "n_parsefail": n_parsefail,
        "parsefail_rate": n_parsefail / max(len(claims), 1),
        "n_load_bearing_cards": len(lb),
        "n_redundant_merged": n_redundant,
        "n_dimensions": len(kept),              # ← VD_anchor_in
        "conclusions_supported": sorted(seen),
        "D": len(seen),
        "cards_kept": kept,
        "cards_all": cards,
    }


# ──────────────────────────────────────────────────────────────
# 7. 锚外通道
# ──────────────────────────────────────────────────────────────
def judge_out_channel(llm: LLM, ask: str, ev_text: str, claims: List[str],
                       model: str) -> Dict[str, Any]:
    cards: List[Dict[str, Any]] = []
    n_parsefail = 0
    bs = _batch_size(ev_text, len(claims))
    for i in range(0, len(claims), bs):
        b = claims[i:i + bs]
        lst = "\n".join("%d. %s" % (n + 1, b[n]) for n in range(len(b)))
        got: List[Dict[str, Any]] = []
        for mt, buds in ((MM_TOKEN_FLOOR, JUDGE_BUDGETS),):
            r = llm.chat(CARD_Q_OUT.format(ask=ask, ev=ev_text, claims=lst),
                         model=model, temp=0.0, max_tokens=mt, budgets=buds,
                         min_ok=len(b) * 15, purpose="card_out")
            got = parse_card_lines(r, len(b))
            if len(got) >= len(b):
                break
        n_parsefail += max(0, len(b) - len(got))
        for g in got:
            g["claim"] = b[g["i"] - 1] if 1 <= g["i"] <= len(b) else ""
            cards.append(g)
    return {"cards_all": cards, "n_cards": len(cards),
            "n_parsefail": n_parsefail,
            "parsefail_rate": n_parsefail / max(len(claims), 1)}


def assign_forks(llm: LLM, cards: List[Dict[str, Any]], model: str) -> Dict[str, Any]:
    """岔口归并（结构化绑定）。★ 归并失败 ⇒ 不得静默当成"每个卡一个独立维度"，
    也不得静默当成 0 ⇒ 两种都记为 `fork_assign_failed`。"""
    cand = [c for c in cards
            if c.get("is_claim") and c.get("load_bearing") is True
            and c.get("decision_changed")]
    if not cand:
        return {"forks": [], "fork_assign_failed": False, "n_candidates": 0}
    lines = []
    for i, c in enumerate(cand, 1):
        dp = c.get("decision_point_out") or c.get("decision_changed") or ""
        lines.append("%d. 陈述：%s\n   它改变的岔口：%s" % (i, c.get("claim", ""), dp))
    raw = llm.chat(FORK_Q.format(claims="\n".join(lines)), model=model, temp=0.0,
                   max_tokens=MM_TOKEN_FLOOR, budgets=JUDGE_BUDGETS, min_ok=20, purpose="fork")
    forks: List[Dict[str, Any]] = []
    for ln in (raw or "").splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            d = json.loads(ln)
        except Exception:                        # noqa: BLE001
            continue
        if not isinstance(d, dict) or "cards" not in d:
            continue
        members = [int(x) for x in (d.get("cards") or []) if str(x).strip().isdigit()]
        if not members:
            continue
        forks.append({"fork": str(d.get("fork") or "K%d" % (len(forks) + 1)),
                      "cards": members, "label": (d.get("label") or "")[:60]})
    covered = {m for f in forks for m in f["cards"]}
    expected = set(range(1, len(cand) + 1))
    failed = bool(forks) and covered != expected
    if not forks and cand:
        failed = True
    return {"forks": forks, "fork_assign_failed": failed,
            "n_candidates": len(cand),
            "fork_cover_missing": sorted(expected - covered)}


def _ct_token_hit(dpo: str, ct_ids: Sequence[str]) -> bool:
    """机械复核：岔口描述里若出现了 `C_t` 的编号（形如 `C2` / `结论3`）⇒ 它其实还在锚内。"""
    ct_norm = {norm_ref(c) for c in ct_ids if c}
    for tok in re.findall(r"[A-Za-z]{0,3}\d{1,3}", dpo or ""):
        if norm_ref(tok) in ct_norm:
            return True
    return False


def anchor_out_gate(cards: List[Dict[str, Any]], forks: Dict[str, Any],
                    ct_ids: Sequence[str], ev_ids: Sequence[str],
                    fork_probe: Optional[Dict[int, bool]] = None,
                    fork_probe2: Optional[Dict[int, bool]] = None) -> Dict[str, Any]:
    """AO-GATE（§2 的 A1–A8）。逐条给出**拒绝原因**，不做二分判定。

    ★ **A5 的语义（2026-10-22 修正）**：leave-one-out 的"独立"是**族级**的
    （协议 §1.4：同族 ⇒ 计 1 个维度）⇒
    - 同一岔口（fork）里的多张卡是**同一维度��不同表述** ⇒ 归族，**计 1 个维度**，
      多出来的记 `n_merged_variants`（**不单独计维度**）；
    - 卡片级的 leave-one-out 在这里的作用是**选代表**（同族里谁是最强支撑），
      而不是"有兄弟就作废"（那会把整族一起作废，与协议的族语义冲突）。
    - **证据级 leave-one-out**（`--loo-regenerate`）是强版本，见 `loo_evidence_effect`。
    """
    ev_norm = {norm_ref(e) for e in ev_ids}
    cand = [c for c in cards
            if c.get("is_claim") and c.get("load_bearing") is True
            and c.get("decision_changed")]
    # 岔口 → 候选卡下标（1-based，与 assign_forks 的编号一致）
    fork_of: Dict[int, str] = {}
    fork_label: Dict[str, str] = {}
    fork_members: Dict[str, List[int]] = {}
    if not forks.get("fork_assign_failed"):
        for f in forks.get("forks", []):
            fork_label[f["fork"]] = f.get("label", "")
            fork_members[f["fork"]] = f["cards"]
            for m in f["cards"]:
                fork_of[m] = f["fork"]

    # ★ 判官层锚外候选数（闸门之前）—— 供"并列报"用
    n_out_cand = sum(1 for c in cand
                      if str(c.get("anchor", "")).lower() == "out")
    counters: Dict[str, int] = {k: 0 for k in
                                ("A1_not_claim", "A2_not_load_bearing", "A3_still_in_anchor",
                                 "A3_fork_covered_by_anchor", "A4_fork_not_named",
                                 "A5_merged_variant", "A6_not_cited",
                                 "A7_contradicted", "A8_parse_failed", "A9_fork_assign_failed")}
    rejected: List[Dict[str, Any]] = []
    passing: List[Dict[str, Any]] = []          # 通过 A1–A8 的卡（还没归族）

    # ★ A3′（族级锚外判定）：如果某张**锚内**卡（判官判它指向 `C_t`）与锚外卡落在**同一个岔口**
    #   ⇒ 那个决策**其实已被 `C_t` 覆盖** ⇒ 锚外卡必须拒。
    #   （没有这一条 ⇒ 同一个决策可以"锚内算一次、锚外再算一次"⇒ 两栏都被灌水。）
    fork_has_anchor_in: Dict[str, bool] = {}
    for idx, c in enumerate(cand, 1):
        fid = fork_of.get(idx)
        if fid is None:
            continue
        if str(c.get("anchor", "")).lower() != "out" and c.get("supports_conclusions"):
            fork_has_anchor_in[fid] = True

    for idx, c in enumerate(cand, 1):
        # A8：解析失败
        if c.get("parse_ok") is False:
            counters["A8_parse_failed"] += 1
            rejected.append({"claim": c.get("claim", ""), "gate": "A8_parse_failed"})
            continue
        dpo = str(c.get("decision_point_out") or "")
        # A3：判官说是锚外 **且** 机械复核不命中 C_t 编号
        if str(c.get("anchor", "")).lower() != "out" or _ct_token_hit(dpo, ct_ids):
            counters["A3_still_in_anchor"] += 1
            rejected.append({"claim": c.get("claim", ""), "gate": "A3_still_in_anchor"})
            continue
        # A4：岔口可指名（写得出）+ **独立复核**（第二次判官调用）
        if not dpo.strip():
            counters["A4_fork_not_named"] += 1
            rejected.append({"claim": c.get("claim", ""), "gate": "A4_fork_not_named"})
            continue
        if fork_probe is None:
            counters["A4_fork_not_named"] += 1
            rejected.append({"claim": c.get("claim", ""), "gate": "A4_fork_not_named",
                             "note": "未做独立复核 ⇒ 不放行（默认拒绝）"})
            continue
        if not fork_probe.get(idx, False):
            counters["A4_fork_not_named"] += 1
            rejected.append({"claim": c.get("claim", ""), "gate": "A4_fork_not_named",
                             "note": "独立复核①（是否具体/是否出界）未通过"})
            continue
        # A4′：**第二个独立探针**（是"做决定"还是"给建议"）⇒ 两个探针 AND
        if fork_probe2 is not None and not fork_probe2.get(idx, False):
            counters["A4_fork_not_named"] += 1
            rejected.append({"claim": c.get("claim", ""), "gate": "A4_fork_not_named",
                             "note": "独立复核②（是决策还是建议/泛论）未通过"})
            continue
        # A5 前置：必须被归到某个岔口（归并失败 ⇒ 不放行）
        fid = fork_of.get(idx)
        if fid is None:
            counters["A9_fork_assign_failed"] += 1
            rejected.append({"claim": c.get("claim", ""), "gate": "A9_fork_assign_failed"})
            continue
        # A3′：同岔口里若有锚内卡 ⇒ 这个决策其实在 `C_t` 里 ⇒ 锚外不成立
        if fork_has_anchor_in.get(fid):
            counters["A3_fork_covered_by_anchor"] += 1
            rejected.append({"claim": c.get("claim", ""), "gate": "A3_fork_covered_by_anchor",
                             "fork": fid, "note": "同岔口存在锚内卡 ⇒ 该决策已被 C_t 覆盖"})
            continue
        # A6：影响矩阵里被引用（引了真实存在的 EV，或自带推理链）
        ref = norm_ref(c.get("evidence_ref"))
        cited = bool(ref) and ref in ev_norm
        self_cont = bool(c.get("self_contained"))
        if not (cited or self_cont):
            counters["A6_not_cited"] += 1
            rejected.append({"claim": c.get("claim", ""), "gate": "A6_not_cited"})
            continue
        # A7：矛盾卡不进维度（进 R1 分子）
        if str(c.get("verdict", "")).strip() == "矛盾":
            counters["A7_contradicted"] += 1
            rejected.append({"claim": c.get("claim", ""), "gate": "A7_contradicted"})
            continue
        passing.append({
            "card_index": idx,
            "claim": c.get("claim", ""),
            "decision_point_out": dpo,
            "fork": fid,
            "fork_label": fork_label.get(fid, ""),
            "basis": c.get("basis", ""),
            "evidence_ref": c.get("evidence_ref"),
            "self_contained": self_cont,
            "verdict": c.get("verdict"),
            "evidence_class": c.get("evidence_class"),
            "loo_level": "card+evidence" if cited else "card_only",
        })

    # ── 归族：一族 = 1 个维度（协议 §1.4）────────────────────────
    basis_rank = {"evidence": 0, "prompt": 1, "model": 2}
    by_fork: Dict[str, List[Dict[str, Any]]] = {}
    for p in passing:
        by_fork.setdefault(p["fork"], []).append(p)
    dimensions: List[Dict[str, Any]] = []
    n_merged_variants = 0
    for fid, members in by_fork.items():
        members = sorted(members, key=lambda p: (basis_rank.get(p["basis"], 3),
                                                 -len(p["claim"] or "")))
        rep = members[0]
        variants = members[1:]
        n_merged_variants += len(variants)
        for v in variants:
            counters["A5_merged_variant"] += 1
            rejected.append({"claim": v["claim"], "gate": "A5_merged_variant",
                             "fork": fid, "note": "与同族代表卡同岔口 ⇒ 归族后不计独立维度"})
        dimensions.append({
            "fork": fid,
            "fork_label": rep["fork_label"],
            "decision_point_out": rep["decision_point_out"],
            "representative_claim": rep["claim"],
            "n_members": len(members),
            "members": [m["claim"] for m in members],
            "basis": rep["basis"],
            "evidence_ref": rep["evidence_ref"],
            "self_contained": rep["self_contained"],
            "verdict": rep["verdict"],
            "loo_level": rep["loo_level"],
            "loo_evidence_effect": "not_run",
        })

    return {
        "n_candidates": len(cand),
        "kept": dimensions,
        "n_anchor_out": len(dimensions),
        "n_merged_variants": n_merged_variants,
        "n_anchor_out_model_basis": sum(1 for k in dimensions if k["basis"] == "model"),
        "n_anchor_out_evidence_basis": sum(1 for k in dimensions if k["basis"] == "evidence"),
        "n_anchor_out_card_only_loo": sum(1 for k in dimensions if k["loo_level"] == "card_only"),
        "rejected": rejected,
        "gate_counters": counters,
        # ★ 判官层锚外候选数（闸门之前）⇒ 与"闸门后"的维度数**并列报**（稳定性规程 R2）
        "n_out_cand": n_out_cand,
        "fork_assign_failed": bool(forks.get("fork_assign_failed")),
    }


# ──────────────────────────────────────────────────────────────
# 8. 读数与报表
# ──────────────────────────────────────────────────────────────
def measure_one(llm: LLM, task: Dict[str, Any], answer: str, answer_id: str,
                 judge_model: str, do_fork_probe: bool = True) -> Dict[str, Any]:
    """对**一份**答案跑完整两栏测量。"""
    ev_items = evidence_items_from_dev(task)
    ct = ct_of_dev(task)
    ev_text = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev_items))
    _log_before = len(llm.log.rows)
    res: Dict[str, Any] = {
        "answer_id": answer_id,
        # ★ judge_effort 必须留痕（2026-10-23）：**不同 effort 的读数不可比**
        #   （channel_probe 实测：max 档在批≥4 时 100% 截断；
        #    effort_probe 实测：同一答案的 anchor=out 判定随 effort 变）
        "judge_effort": getattr(llm, "effort", None) or "(default=max)",
        "task_id": task.get("task_id"),
        "vd_version": VD_VERSION,
        "judge_model": judge_model,
        "judge_temp": 0.0,
        "in_channel_version": IN_CHANNEL_VERSION,
        "out_prompt_version": OUT_PROMPT_VERSION,
        "fork_prompt_version": FORK_PROMPT_VERSION,
        "n_chars": len(answer or ""),
        "cjk_ratio": round(cjk_ratio(answer or ""), 4),
    }
    if not (answer or "").strip():
        # ★ 失败不许静默变 0（协议 §4.7 E2/E3）
        res.update(valid=0, reason="empty_answer", silent_empty_count=1,
                   n_claims=0, n_cards=0, VD_anchor_in=0, VD_anchor_out=0)
        return res
    if res["cjk_ratio"] < 0.5:
        res["language_drift_warning"] = "中文占比 %.2f < 0.5 ⇒ 先查语言漂移再谈读数" % res["cjk_ratio"]

    claims = extract_claims(llm, answer, judge_model)
    res["n_claims"] = len(claims)
    if not claims:
        # ★★ 2026-10-22 实测修正（"坏掉的通道长得像赢家"）：
        #   判官/抽取**调用失败**时，`parsefail_rate` 仍是 **0.0**（没有可解析的东西），
        #   而 `VD_anchor_in` 也是 0 ⇒ 读数**看起来像"这条臂没有维度"**。
        #   实测：V3 变体在 OpenRouter 上 403（本区不可用）⇒ 9/9 份 `n_claims=0`、
        #   `parsefail=0.0`、`VD=0` ⇒ **一个坏通道伪装成了一个完美的结果**。
        #   ⇒ 修复：**抽取为空 ⇒ 样本作废**（不是"0 个维度"），并独立计数。
        res.update(valid=0, reason="extraction_empty", channel_failed=True,
                   silent_empty_count=1, n_cards=0, VD_anchor_in=0, VD_anchor_out=0,
                   n_parsefail=0, parsefail_rate=0.0,
                   n_load_bearing_in=0, n_load_bearing_out=0)
        return res

    inr = judge_in_channel(llm, task.get("ask", ""), ev_text, claims, judge_model)
    res.update({
        "n_cards": inr["n_cards"],
        "n_parsefail": inr["n_parsefail"],
        "parsefail_rate": inr["parsefail_rate"],
        "n_load_bearing_in": inr["n_load_bearing_cards"],
        "n_redundant_merged": inr["n_redundant_merged"],
        "VD_anchor_in": inr["n_dimensions"],
        "D_in": inr["D"],
        "conclusions_supported": inr["conclusions_supported"],
        "cards_kept_in": inr["cards_kept"],
    })

    outr = judge_out_channel(llm, task.get("ask", ""), ev_text, claims, judge_model)
    fork = assign_forks(llm, outr["cards_all"], judge_model)
    probe = None
    probe2 = None
    if do_fork_probe:
        targets = probe_targets(outr["cards_all"], fork)
        probe = fork_probe(llm, task, outr["cards_all"], judge_model, targets)
        probe2 = fork_probe2(llm, task, outr["cards_all"], judge_model, targets)
    gate = anchor_out_gate(outr["cards_all"], fork, [c["id"] for c in ct],
                           [e["id"] for e in ev_items], fork_probe=probe,
                           fork_probe2=probe2)
    res.update({
        "fork_purity_est": FORK_PURITY_EST,
        "VD_anchor_out_purity_adj": round(gate["n_anchor_out"] * FORK_PURITY_EST, 3),
        "n_cards_out": outr["n_cards"],
        "n_load_bearing_out": gate["n_candidates"],
        # ★ n_out_cand（2026-10-23）：**判官层**判成 anchor=out 的候选数（闸门之前）
        #   ⇒ 必须与 VD_anchor_out（**闸门层**）**并列报**
        #   （稳定性规程 R2：只报闸门后的数 ⇒ 看不到中间发生了什么 ⇒ 读数一变就查不出原因）
        "n_out_cand": gate.get("n_out_cand", 0),
        "VD_anchor_out": gate["n_anchor_out"],
        "VD_anchor_out_model_basis": gate["n_anchor_out_model_basis"],
        "VD_anchor_out_evidence_basis": gate["n_anchor_out_evidence_basis"],
        "VD_anchor_out_card_only_loo": gate["n_anchor_out_card_only_loo"],
        "anchor_out_cards": gate["kept"],
        "anchor_out_rejected": gate["rejected"],
        "gate_counters": gate["gate_counters"],
        "fork_assign_failed": gate["fork_assign_failed"],
        "forks": fork.get("forks", []),
        # ★ 落盘**原始** OUT 卡 + 两个探针的逐条结果 ⇒ **判据可离线复算**
        "cards_out_all": outr["cards_all"],
        "fork_assign": fork,
        "probe_specific": probe,
        "probe_decision": probe2,
    })
    _rows = llm.log.rows[_log_before:]
    res["calls"] = {
        "n_calls": len(_rows),
        "n_error": sum(1 for r in _rows if str(r.get("finish_reason", "")).startswith("error")),
        "n_empty_content": sum(1 for r in _rows if r.get("content_len", 0) == 0),
        "n_truncated": sum(1 for r in _rows if r.get("finish_reason") == "length"),
        "statuses": sorted({str(r.get("status")) for r in _rows if r.get("status")}),
    }
    res["channel_failed"] = bool(res["calls"]["n_error"] or res["calls"]["n_empty_content"])
    if res["channel_failed"] and res.get("valid") == 1:
        # 有调用失败 ⇒ 该份读数**降级为描述性**（协议 F8 精神）
        res["valid"] = 0
        res["reason"] = "channel_failed"
    res["valid"] = res.get("valid", 1)
    return res


FORK_PROBE_Q = """问题：
{ask}

结论空间清单（**这就是全部**）：
{ct}

候选陈述：
{claim}

它声称改变的决策（不在清单里）：
{dpo}

请**只**依据上面三样东西回答这一行 JSON（不要输出别的任何内容）：
{{"specific": true/false,   ← 它改变的是不是一个**具体**的决策/判断（能写出"在什么前提下做什么、做成什么样"）？泛泛的建议/铺陈/感想 ⇒ false
  "outside": true/false,    ← 那个决策是否**确实不在**上面的结论空间清单里？
  "note": "一句理由"}}

「具体」的含义：能写成"在____前提下，应当____（具体到动作或判类）"。写不出 ⇒ specific=false。
"""

FORK_PROBE2_Q = """问题：
{ask}

结论空间清单（**这就是全部**）：
{ct}

候选陈述：
{claim}

它声称改变的决策（不在清单里）：
{dpo}

请**只**依据上面三样东西回答这一行 JSON（不要输出别的任何内容）：
{{"is_decision": true/false,   ← 它是在**改变一个具体的决策/岔口**，还是在**给建议、泛论、复述、感想**？
                              泛泛的建议、铺陈、感想、免责、"需要综合考虑" ⇒ false
  "is_checkable": true/false,  ← 别人能不能**独立核对**这个决策？
                              （能写成"在____前提下应当____（具体到动作或判类）"⇒ true；只能靠读者自己补 ⇒ false）
  "note": "一句理由"}}
"""


def fork_probe2(llm: LLM, task: Dict[str, Any], cards: List[Dict[str, Any]],
                judge_model: str, targets: Optional[Sequence[int]] = None) -> Dict[int, bool]:
    """A4′ 的**第二个独立探针**：这条陈述是在**做决定**还是在**给建议/泛论**？

    ★ 为什么加它（2026-10-22 实测）：只用一个探针时，判官在 3 张"假锚外卡"里
      **放行了 1 张**（"建议在实施前充分沟通…"这类）⇒ 单探针闸门会被钻空子
      ⇒ 协议 F7 下**不得出数**。⇒ 加**第二个、不同问法**的探针，两个都过才放行（AND）。
    """
    out: Dict[int, bool] = {}
    cand_all = [c for c in cards
                if c.get("is_claim") and c.get("load_bearing") is True
                and c.get("decision_changed")]
    if not cand_all:
        return out
    ct_text = "\n".join("%s. %s" % (c["id"], c["text"]) for c in ct_of_dev(task))
    tset = set(targets) if targets is not None else None
    for i, c in enumerate(cand_all, 1):
        if str(c.get("anchor", "")).lower() != "out":
            continue
        if tset is not None and i not in tset:
            continue
        r = llm.chat(FORK_PROBE2_Q.format(ask=task.get("ask", ""), ct=ct_text,
                                          claim=c.get("claim", ""),
                                          dpo=c.get("decision_point_out", "")),
                     model=judge_model, temp=0.0, max_tokens=MM_TOKEN_FLOOR,
                     budgets=JUDGE_BUDGETS, min_ok=10, purpose="fork_probe2")
        ok = False
        for ln in (r or "").splitlines():
            ln = ln.strip()
            if not ln.startswith("{"):
                continue
            try:
                d = json.loads(ln)
            except Exception:                    # noqa: BLE001
                continue
            if isinstance(d, dict) and d.get("is_decision") is True \
                    and d.get("is_checkable") is True:
                ok = True
                break
        out[i] = ok
    return out


def probe_targets(cards: List[Dict[str, Any]], forks: Dict[str, Any]) -> List[int]:
    """**只对真正的锚外候选**发探针（省调用）：承重 ∧ anchor=out ∧ 不在"已被锚内卡覆盖"的岔口里。

    ★ 与 `anchor_out_gate` 的候选编号**必须一致**（同一个 1-based 下标空间）。
    """
    cand = [c for c in cards
            if c.get("is_claim") and c.get("load_bearing") is True
            and c.get("decision_changed")]
    fork_of: Dict[int, str] = {}
    for f in forks.get("forks", []) if not forks.get("fork_assign_failed") else []:
        for m in f["cards"]:
            fork_of[m] = f["fork"]
    covered: set = set()
    for idx, c in enumerate(cand, 1):
        fid = fork_of.get(idx)
        if fid is None:
            continue
        if str(c.get("anchor", "")).lower() != "out" and c.get("supports_conclusions"):
            covered.add(fid)
    out = []
    for idx, c in enumerate(cand, 1):
        if str(c.get("anchor", "")).lower() != "out":
            continue
        if fork_of.get(idx) in covered:
            continue
        out.append(idx)
    return out


def fork_probe(llm: LLM, task: Dict[str, Any], cards: List[Dict[str, Any]],
               judge_model: str, targets: Optional[Sequence[int]] = None) -> Dict[int, bool]:
    """A4 的**独立复核**：只看这条卡 + `C_t` 清单 ⇒ 它是否改变了一个**具体**决策，
    且该决策**确实不在** `C_t` 里？⇒ 两个都是 yes 才放行。

    ★ 这是与主判官**分离的一次调用**（不同提示、不同输入面）⇒ 防"同一判官自问自答"。
    """
    out: Dict[int, bool] = {}
    # ★ 索引必须与 `anchor_out_gate` 的候选编号**完全一致**
    #   （闸门的候选 = 承重且非复述的全部卡，含锚内卡；这里只对锚外卡发问，
    #     但返回的键仍是**全体候选里的下标**）⇒ 否则探针与闸门会张冠李戴。
    cand_all = [c for c in cards
                if c.get("is_claim") and c.get("load_bearing") is True
                and c.get("decision_changed")]
    if not cand_all:
        return out
    ct_text = "\n".join("%s. %s" % (c["id"], c["text"]) for c in ct_of_dev(task))
    tset = set(targets) if targets is not None else None
    for i, c in enumerate(cand_all, 1):
        if str(c.get("anchor", "")).lower() != "out":
            out[i] = False          # 锚内卡：闸门会在 A3 直接拒，不消耗探针预算
            continue
        if tset is not None and i not in tset:
            out[i] = False          # 非目标（已被锚内卡覆盖的岔口）⇒ 不发问
            continue
        r = llm.chat(FORK_PROBE_Q.format(ask=task.get("ask", ""), ct=ct_text,
                                     claim=c.get("claim", ""),
                                     dpo=c.get("decision_point_out", "")),
                     model=judge_model, temp=0.0, max_tokens=MM_TOKEN_FLOOR,
                     budgets=JUDGE_BUDGETS, min_ok=10, purpose="fork_probe")
        ok = False
        for ln in (r or "").splitlines():
            ln = ln.strip()
            if not ln.startswith("{"):
                continue
            try:
                d = json.loads(ln)
            except Exception:                    # noqa: BLE001
                continue
            if isinstance(d, dict) and d.get("specific") is True and d.get("outside") is True:
                ok = True
                break
        out[i] = ok
    return out


# ──────────────────────────────────────────────────────────────
# 9. 影响矩阵
# ──────────────────────────────────────────────────────────────
def influence_matrix(results: List[Dict[str, Any]], ev_ids: Sequence[str]) -> Dict[str, Any]:
    """卡 × 依据 的引用矩阵 + 臂 × 依据 的覆盖矩阵（离散，不依赖 embedding）。"""
    cols = list(ev_ids)
    card_x_ev: List[Dict[str, Any]] = []
    for r in results:
        for c in (r.get("cards_kept_in") or []) + (r.get("anchor_out_cards") or []):
            ref = norm_ref(c.get("evidence_ref"))
            card_x_ev.append({
                "answer_id": r.get("answer_id"),
                "task_id": r.get("task_id"),
                "claim": (c.get("claim") or "")[:80],
                "kind": "anchor_in" if c in (r.get("cards_kept_in") or []) else "anchor_out",
                "evidence_ref": c.get("evidence_ref"),
                "cited": bool(ref) and ref in {norm_id(x) for x in cols},
            })
    arm_x_ev: Dict[str, List[str]] = {}
    for r in results:
        arm = str(r.get("arm") or r.get("answer_id"))
        got = set()
        for c in (r.get("cards_kept_in") or []) + (r.get("anchor_out_cards") or []):
            ref = norm_ref(c.get("evidence_ref"))
            if ref:
                got.add(ref)
        arm_x_ev.setdefault(arm, [])
        arm_x_ev[arm] = sorted(set(arm_x_ev[arm]) | got)
    coverage = {arm: len(v) for arm, v in arm_x_ev.items()}
    return {
        "columns": cols,
        "card_x_evidence": card_x_ev,
        "arm_x_evidence": arm_x_ev,
        "arm_coverage_count": coverage,
        "note": "cell = 该卡/该臂是否以该依据条目为支撑；离散、可复算，不依赖 embedding",
    }


# ──────────────────────────────────────────────────────────────
# 10. CLI
# ──────────────────────────────────────────────────────────────
def _judge_model_from_env() -> str:
    return os.environ.get("VD_JUDGE_MODEL", "MiniMax-M3.1-Flash-Preview")


def cmd_measure(args: argparse.Namespace) -> int:
    devset = load_devset(args.dev)
    task = dev_task(devset, args.task)
    answer = open(args.answer, encoding="utf-8").read()
    llm = LLM(args.judge_vendor, args.judge_model)
    res = measure_one(llm, task, answer, os.path.basename(args.answer),
                      args.judge_model, do_fork_probe=not args.no_probe)
    res["calls"] = llm.log.summary()
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """manifest: [{"answer_id","task_id","answer_file","arm"}...]"""
    import concurrent.futures as cf

    devset = load_devset(args.dev)
    # ★ effort 整条管线统一（2026-10-23）：不传 ⇒ 默认（官方 = max）
    llm = LLM(args.judge_vendor, args.judge_model, effort=getattr(args, "effort", None))
    items = json.load(open(args.manifest, encoding="utf-8"))
    out: Dict[str, Any] = {}

    def one(item: Dict[str, Any]) -> Dict[str, Any]:
        task = dev_task(devset, item["task_id"])
        answer = open(item["answer_file"], encoding="utf-8").read()
        r = measure_one(llm, task, answer, item.get("answer_id") or item["answer_file"],
                        args.judge_model, do_fork_probe=not args.no_probe)
        r["arm"] = item.get("arm")
        r["rep"] = item.get("rep", 1)
        return r

    # ★ 并发：MiniMax 侧并发 8 会触发 429（第四组实测：36 次调用整片失败）⇒ 默认 3
    workers = max(1, int(getattr(args, "workers", 3)))
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(one, items):
            out[r["answer_id"]] = r
            print("%-28s IN=%s OUT=%s  claims=%s cards=%s parsefail=%s" % (
                r["answer_id"], r.get("VD_anchor_in"), r.get("VD_anchor_out"),
                r.get("n_claims"), r.get("n_cards"), r.get("parsefail_rate")), flush=True)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "anchor_readout.json"), "w", encoding="utf-8") as f:
        json.dump({"vd_version": VD_VERSION, "judge_model": args.judge_model,
                   "judge_vendor": args.judge_vendor,
                   "judge_effort": getattr(llm, "effort", None) or "(default=max)",
                   "results": out, "calls": llm.log.summary()},
                  f, ensure_ascii=False, indent=2)
    # 读数表
    n_total = len(out)
    n_valid = sum(1 for v in out.values() if v.get("valid") == 1)
    n_chfail = sum(1 for v in out.values() if v.get("channel_failed"))
    eff = getattr(llm, "effort", None) or "(default=max)"
    rows = ["| answer_id | arm | VD_anchor_in | VD_anchor_out | OUT(evidence) | OUT(model) | 仅卡片级LOO | claims | cards | 承重 | parsefail | 有效 | 通道失败 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in out.items():
        rows.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            k, v.get("arm"), v.get("VD_anchor_in"), v.get("VD_anchor_out"),
            v.get("VD_anchor_out_evidence_basis"), v.get("VD_anchor_out_model_basis"),
            v.get("VD_anchor_out_card_only_loo"), v.get("n_claims"), v.get("n_cards"),
            v.get("n_load_bearing_in"), v.get("parsefail_rate"), v.get("valid"),
            v.get("channel_failed")))
    table = "\n".join(rows)
    table += ("\n\n**判官 effort = `%s`**（★ 不同 effort 的读数**不可比**）" % eff)
    table += ("\n\n**valid/total = %d/%d**｜**通道失败样本 = %d**"
              "（通道失败 ⇒ 该份读数作废，**不许**读成\"这条臂没有维度\"）"
              % (n_valid, n_total, n_chfail))
    with open(os.path.join(args.out, "READOUT.md"), "w", encoding="utf-8") as f:
        f.write("# VD_anchor_out 读数表\n\n" + table + "\n")
    print("\n" + table)
    # ★ 立论可失败闸门 —— **必须先过通道健康检查**
    #   （2026-10-22 实测踩过：73 次判官调用里 36 次空内容、34 次截断
    #     ⇒ 锚外通道"什么都没产出" ⇒ OUT=0 与"通道坏了"**混淆**
    #     ⇒ 此时说"立论不成立"是**误判**。）
    outs = [v.get("VD_anchor_out", 0) for v in out.values()]
    calls = llm.log.summary()
    n_call = max(calls.get("n_calls", 0), 1)
    bad = calls.get("n_empty_content", 0) + calls.get("n_truncated", 0)
    health = 1.0 - (bad / float(n_call))
    n_invalid = sum(1 for v in out.values() if v.get("valid") != 1)
    healthy = (health >= 0.9) and (n_invalid == 0)
    if not healthy:
        verdict = ("⚠️ **通道不健康 ⇒ 理论闸门不生效**：判官调用 %d 次中 %d 次空内容/被截断"
                   "（健康度 %.2f），%d/%d 份样本无效 ⇒ **不能**据此说立论成立或不成立"
                   % (calls.get("n_calls", 0), bad, health, n_invalid, len(out)))
    elif all(o == 0 for o in outs):
        verdict = ("★ 立论不成立：VD_anchor_out 在所有样本上恒为 0 ⇒ 我们做的是检索，不是发现"
                   "（通道健康度 %.2f，无效样本 %d）" % (health, n_invalid))
    else:
        verdict = ("VD_anchor_out > 0 ⇒ 立论未被当场否证（仍需跨重复稳定；通道健康度 %.2f）"
                   % health)
    print("\n[通道健康] 调用 %d 次｜空内容 %d｜截断 %d｜错误 %d｜健康度 %.2f｜无效样本 %d/%d"
          % (calls.get("n_calls", 0), calls.get("n_empty_content", 0),
             calls.get("n_truncated", 0), calls.get("n_error", 0), health, n_invalid, len(out)))
    print("[理论闸门] " + verdict)
    with open(os.path.join(args.out, "READOUT.md"), "a", encoding="utf-8") as f:
        f.write("\n\n**通道健康**：调用 %d 次｜空内容 %d｜截断 %d｜错误 %d｜健康度 %.2f｜无效样本 %d/%d\n"
                % (calls.get("n_calls", 0), calls.get("n_empty_content", 0),
                   calls.get("n_truncated", 0), calls.get("n_error", 0), health, n_invalid, len(out)))
        f.write("\n[理论闸门] " + verdict + "\n")
    return 0


def cmd_matrix(args: argparse.Namespace) -> int:
    with open(os.path.join(args.out, "anchor_readout.json"), encoding="utf-8") as f:
        blob = json.load(f)
    results = list(blob.get("results", {}).values())
    ev_ids: List[str] = []
    for r in results:
        for c in (r.get("cards_kept_in") or []) + (r.get("anchor_out_cards") or []):
            ref = c.get("evidence_ref")
            if ref and ref not in ev_ids:
                ev_ids.append(ref)
    mx = influence_matrix(results, ev_ids)
    with open(os.path.join(args.out, "influence_matrix.json"), "w", encoding="utf-8") as f:
        json.dump(mx, f, ensure_ascii=False, indent=2)
    print(json.dumps(mx, ensure_ascii=False, indent=2)[:4000])
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    from selftest_fixtures import run_selftest          # noqa: WPS433
    return run_selftest(args)


def cmd_verify_equivalence(args: argparse.Namespace) -> int:
    """把锚内通道与 `batch-U1/measure.py` **逐字段**对拍（只调用它，不改它）。"""
    devset = load_devset(args.dev)
    task = dev_task(devset, args.task)
    answer = open(args.answer, encoding="utf-8").read()
    llm = LLM(args.judge_vendor, args.judge_model)
    ev_items = evidence_items_from_dev(task)
    ev_text = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev_items))
    mine = judge_in_channel(llm, task.get("ask", ""), ev_text,
                             extract_claims(llm, answer, args.judge_model), args.judge_model)
    ref = MEASURE.measure_answer(llm, task.get("ask", ""), ev_items,
                                 ct_of_dev(task), answer, args.answer,
                                 judge_model=args.judge_model)
    cmp_res = {
        "VD_anchor_in_mine": mine["n_dimensions"],
        "VD_anchor_in_measure_py": ref.get("n_dimensions"),
        "D_mine": mine["D"],
        "D_measure_py": ref.get("D"),
        "n_cards_mine": mine["n_cards"],
        "n_cards_measure_py": ref.get("n_cards"),
        "conclusions_equal": sorted(mine["conclusions_supported"]) == sorted(
            ref.get("conclusions_supported", [])),
        "n_load_bearing_equal": mine["n_load_bearing_cards"] == ref.get("n_load_bearing_cards"),
    }
    cmp_res["equivalent"] = bool(
        cmp_res["VD_anchor_in_mine"] == cmp_res["VD_anchor_in_measure_py"]
        and cmp_res["D_mine"] == cmp_res["D_measure_py"]
        and cmp_res["conclusions_equal"])
    print(json.dumps(cmp_res, ensure_ascii=False, indent=2))
    return 0 if cmp_res["equivalent"] else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="VD_anchor_out · 锚外新增维度数")
    ap.add_argument("--dev", default=DEV_DIR, help="DEV 集目录")
    ap.add_argument("--judge-vendor", default="minimax", choices=["minimax", "openrouter"])
    ap.add_argument("--judge-model", default=_judge_model_from_env())
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("measure", help="单份答案")
    p.add_argument("--task", required=True)
    p.add_argument("--answer", required=True)
    p.add_argument("--out")
    p.add_argument("--no-probe", action="store_true")
    p.set_defaults(func=cmd_measure)

    p = sub.add_parser("batch", help="一批答案")
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--no-probe", action="store_true")
    p.add_argument("--workers", type=int, default=3, help="并发数（>4 会触发 MiniMax 429）")
    p.add_argument("--effort", default=None,
                   help="MiniMax 思考深度档（max/medium/low/…）★ 官方：不传默认=max，"
                        "且 max 在批≥4 时 100%% 截断（见 EFFORT-PRE-REG.md）")
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser("matrix", help="影响矩阵导出")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_matrix)

    p = sub.add_parser("selftest", help="自检闸门（协议 F7）")
    p.add_argument("--out", default=os.path.join(EVAL_DIR, "selftest_out"))
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser("verify-equivalence", help="与 measure.py 对拍")
    p.add_argument("--task", required=True)
    p.add_argument("--answer", required=True)
    p.set_defaults(func=cmd_verify_equivalence)

    args = ap.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
