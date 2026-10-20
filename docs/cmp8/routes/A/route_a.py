# -*- coding: utf-8 -*-
"""路线 A 的固定拓扑执行器（**人设计的 DAG，零训练**）。

与 `creativity_lab/learnarch.py` 的区别（这是本文件存在的理由）：
- learnarch 跑的是**学出来的策略**（在图上按 14 维权重选下一条边）——那是路线 B/C 的事；
- 本文件跑的是**写死的 DAG**：节点、边、预算上限全部在 `spec.yaml` 里事前声明，
  执行器里没有任何权重、没有 policy、没有「哪条边更值钱」的判断。

拓扑（**统一编号 N0…N8**，与 `DESIGN.md` §3.1 的图、`spec.yaml` 的 `nodes:` 一一对应）：

    N0  读题 / 装配输入                 0 次调用
    N1  槽位生成（第一轮，FA1–FA4）      4 次调用
    N2  断言抽取（逐槽位）               4 次调用
    N3  离散去冗余（**塌缩诊断量**）      0 次调用
    N4  条件重采样（第二轮，FA5–FA6）    2 次调用   ← 恒定执行（无数据依赖开关）
    N5  断言抽取（第二轮，批量）          1 次调用
    N6  原子化拆分                      ≤1 次调用
    N7  D2 门：效用轴（依据核验）+ 新颖轴（装配顺序）  ≤4 次调用
    N8  机械装配 + 自检与记账            0 次调用

⚠️ **本轮（第二轮返工）改动的三处语义**，每处都对应复核报告的一条发现：
1. **预算按任务计**（F1）：`max_tokens` / `max_calls` 的作用域 = **本次 route 调用**，
   不是进程累计。LLM 对象在多任务间共享 ⇒ 必须用**本地增量**计数。
2. **N4 恒定执行**（F3）：塌缩量 `collapse_mult` 是**纯诊断量**，不控制任何分支。
   旧版把 `kept_r1 < mult × K₁` 当开关 ⇒ 拓扑数据依赖 ⇒ 与路线 A 的定义冲突
   （本文件 §2.7 正是以这个理由弃用 D6 的）。
3. **效用轴先于新颖轴**（F4）：D2 门先做依据核验，**再**在**可交付子集**上做去冗余；
   装配阶段对**已装入**的条目保留冗余否决权（否则改写型重复会同时进答案）。

⚠️ **依据包只出现在 N7 的核验提示词里**（`/workspace/lab/METHOD.md` §4 必留声明 #4：
「依据包只进判官/核验侧，不进被测臂的提示词」）。本文件在运行时**断言**这一点：
所有生成类提示词（N1/N4）都不含依据包文本 —— 断言失败即 abort。

⚠️ **路线内部不使用 embedding**：本项目的实测（`embo-01` 句级集合距离在两臂上
SEP≈0.002）表明该几何量在句级没有分辨率 ⇒ 冗余判定用**离散结构量**：
数字指纹（`net_dimension_gain.hard_tokens`）+ 4 字中文 n-gram 覆盖率
（`net_dimension_gain.cjk_ngrams`）—— 这两套与协议 §1.7 的跨臂对齐口径同源。

⚠️ **种子**：共享 client 的 `chat()` **没有 seed 参数**（本文件不改共享包）
⇒ 本路线**没有 API 级种子**。`meta.json` 里的 `seed` 只是**运行标签**，
`seed_policy` 如实写明「API 不支持种子 ⇒ 不可复现」，详见 `FIX-NOTES.md` F5。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

sys.path.insert(0, "/workspace/lab")            # creativity_lab 包（client/verify/ops/metrics）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from creativity_lab.client import LLM            # noqa: E402
import facets as F                               # noqa: E402
from net_dimension_gain import hard_tokens, cjk_ngrams   # noqa: E402

# ---------------------------------------------------------------- 预注册常量
# ⚠️ 全部事前写死，见 DESIGN.md §3「预注册常量表」。事后不得调整（协议 R-9）。
DEFAULTS = dict(
    # --- 拓扑 ---
    round1_facets=list(F.ROUND1_FACETS),
    round2_facets=list(F.ROUND2_FACETS),
    facet_enabled=True,          # False ⇒ 槽位不带承载面指令（消融臂 A_minus_facet）
    # structured = 第二轮带已覆盖清单；structured_no_cover = 第二轮**不带**清单（消融臂
    # A_minus_D3）；random = 第二轮带与任务无关的占位文本（消融臂 A_random_rest）；
    # none = 没有第二轮（消融臂 A_minus_R2）。**这四个值都是臂级常量，与数据无关。**
    resample_mode="structured",
    novel_axis=True,             # False ⇒ 不去冗余（消融臂 A_minus_novel）
    utility_axis=True,           # False ⇒ 不做外部核验（消融臂 A_minus_utility）
    # --- 预算（作用域 = 每 (臂, 任务, rep)，**不是进程累计**，见 F1）---
    max_calls=24,                # 每 (臂,任务,rep) 的模型调用上限
    # ⚠️ **预注册修订（DEV 数据之前）**：原值 40 000 → 现值 60 000。
    #    依据：预注册拓扑（4+2 承载面）**一个 rep** 的实测用量 46 217 token
    #    （`smoke/smoke_log.json` 的 `invalidated_samples`）⇒ 40 000 **装不下**该拓扑。
    #    ⚠️ 60 000 **未经活体验证**（本轮 API 预算已用尽）⇒ 见 DESIGN §3.5「预注册修订记录」。
    max_tokens=60000,            # 协议 §4.4 的 T_max（建议 40k；本路线按实测上修）
    max_claims=48,               # 断言池上限（事前写死，内容无关的截断）
    extract_cap=8,               # 每个槽位最多抽 8 条
    verify_batch=12,             # 核验批大小
    answer_char_cap=400,         # **整份答案**的字数上限（三臂一致）
    # --- 判据 ---
    lex_thr=0.75,                # 实现 1：char-bigram Jaccard 阈值（近乎逐字重复）
    struct_thr=0.70,             # 实现 2：4-gram 覆盖率阈值（改写型重复）
    collapse_mult=1.0,           # 塌缩**诊断量**（存活断言数 < mult × K₁ ⇒ 塌缩）
    # --- 采样 ---
    temp=0.7,                    # 协议 §4.3 三臂一致
    max_out_tokens=6000,
)

RESAMPLE_MODES = ("structured", "structured_no_cover", "random", "none")

# 断言抽取的行过滤（沿用项目既有口径：8–70 字）
_CLEAN = re.compile(r"^\s*[-*\d.、)）]+\s*")
VERDICT_RE = re.compile(r"(非主张|支持|矛盾|未提及)")
REF_RE = re.compile(r"\b(\d{1,3})\b")

# 消融对照臂专用：与任务无关的占位上下文（**只在 random_rest 对照臂里出现**）
RANDOM_REST_TEXT = (
    "（以下内容与本任务无关，只作占位）清晨的街道很安静，"
    "早点摊的蒸汽在冷空气里散开，远处传来第一班公交车的引擎声。"
)

# 协议 §8 (a4) 要求的跨臂可比元数据中，**不属于本路线**的字段（协议侧产出）。
# 本路线**不代填**（协议 §8 (a3)/(e)：抽取器/判官/对齐器由协议侧独立流程产出）；
# 这里列出来是为了让 `meta.json` 显式登记「缺哪些、为什么缺」，而不是留空。
PROTOCOL_SIDE_FIELDS = [
    "judge_model", "judge_prompt_version", "judge_temp", "judge_same_vendor",
    "judge_selfcheck", "embedding_model", "aligner_version", "extractor_version",
    "extractor_f1", "lexical_baseline_f1",
]

# 协议 §4.7 的排除口径（E2：产出 < 50 字 ⇒ 该**样本**作废）
MIN_VALID_CHARS = 50


class BudgetExceeded(RuntimeError):
    pass


# ---------------------------------------------------------------- 计量
class MeteredLLM(LLM):
    """给 `creativity_lab.client.LLM` 加一个 usage 计量（**不改共享包**）。

    共享 client 的 `rec` 里没有 token 数（只有 max_tokens 与 content_len），
    而协议的 R3 / §4.4 要求报 `n_tokens` ⇒ 这里在 `_post` 里把 API 返回的
    `usage` 抄下来。不改原文件 ⇒ 其它两条路线不受影响。

    ⚠️ `client.chat()` 会按 `FALLBACKS` **静默换模型**（过载时降级），
    而**实际用的模型**记在 `client.rec[i].model` 里 ⇒ 本类把它透出来（F15）。
    """

    def __init__(self, recorder=None):
        super().__init__(recorder=recorder)
        self.usage_log: list = []

    def _post(self, url, payload, timeout=240):
        d = super()._post(url, payload, timeout)
        u = d.get("usage") or {}
        self.usage_log.append(dict(
            url=url,
            model=payload.get("model"),
            prompt_tokens=int(u.get("prompt_tokens") or 0),
            completion_tokens=int(u.get("completion_tokens") or 0),
            total_tokens=int(u.get("total_tokens") or 0),
        ))
        return d

    @property
    def n_tokens(self) -> int:
        return sum(x["total_tokens"] or (x["prompt_tokens"] + x["completion_tokens"])
                   for x in self.usage_log)

    @property
    def n_api_calls(self) -> int:
        return len(self.usage_log)


# ---------------------------------------------------------------- 冗余判定（离散）
def _char_bigrams(t: str) -> set:
    t = re.sub(r"\s", "", t or "")
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / max(len(a | b), 1)


class RedundancyJudge:
    """两个**独立实现**的冗余判据（离散，无 embedding）。

    实现 1 · 词法：char-bigram Jaccard ≥ `lex_thr`  ⇒ 近乎逐字重复
    实现 2 · 结构：数字指纹互为子集（且都非空）+ 4-gram 覆盖率 ≥ `struct_thr`
                   ⇒ 改写型重复

    组合方式（**不取更严的删除**，理由见 DESIGN §4.3）：
      strict = 两实现都认为「不重复」的条目  → 优先占用答案字数预算
      loose  = 至少一个实现认为「不重复」的条目 → 填剩余预算
    ⇒ **池层面**任何单实现都**不能**把一条断言彻底删掉（避免假阳性毁掉宽度）；
      但**装配层面**对**已装入答案**的条目，冗余判定有**一票否决权**
      （否则改写型重复会同时进答案 —— 这是 F4 修复的一半）。
    """

    def __init__(self, lex_thr: float = 0.75, struct_thr: float = 0.70):
        self.lex_thr = lex_thr
        self.struct_thr = struct_thr
        self._cache: dict = {}

    def _feat(self, t: str):
        if t not in self._cache:
            self._cache[t] = (set(hard_tokens(t)), set(cjk_ngrams(t)))
        return self._cache[t]

    def impl1(self, a: str, b: str) -> bool:
        """词法：近乎逐字重复。"""
        return _jaccard(_char_bigrams(a), _char_bigrams(b)) >= self.lex_thr

    def impl2(self, a: str, b: str) -> bool:
        """结构：改写型重复（数字指纹互为子集 + 4-gram 覆盖率）。"""
        ha, _ = self._feat(a)
        hb, _ = self._feat(b)
        if not ha or not hb:                 # 没有硬指纹 ⇒ 不判改写型重复（避免假阳性）
            return False
        if not (ha <= hb or hb <= ha):
            return False
        na, nb = self._feat(a)[1], self._feat(b)[1]

        def cov(x, y):
            return len(x & y) / max(len(x), 1)
        return max(cov(na, nb), cov(nb, na)) >= self.struct_thr

    def any_impl(self, a: str, b: str) -> bool:
        """任一实现判冗余（**装配期否决**用）。"""
        return self.impl1(a, b) or self.impl2(a, b)

    def keep_sets(self, texts: list):
        """返回 (strict, loose, keep1, keep2)，都是**下标列表**。

        性质（装配期否决不会伤到 strict）：两个下标同属 `keep1` ⇒ 实现 1 不判冗余；
        同属 `keep2` ⇒ 实现 2 不判冗余；strict = keep1 ∩ keep2 ⇒
        **strict 内部两两在两实现下都不冗余** ⇒ strict 条目永不被装配期否决。
        """
        n = len(texts)
        if n == 0:
            return [], [], [], []
        keep1, keep2 = [], []
        for i in range(n):
            if not any(self.impl1(texts[i], texts[j]) for j in keep1):
                keep1.append(i)
        for i in range(n):
            if not any(self.impl2(texts[i], texts[j]) for j in keep2):
                keep2.append(i)
        s = set(keep1) & set(keep2)
        l = set(keep1) | set(keep2)
        strict = [i for i in range(n) if i in s]
        loose = [i for i in range(n) if i in l]
        return strict, loose, keep1, keep2


def redundancy(texts: list, lex_thr: float, struct_thr: float):
    """兼容旧调用点：返回 (strict_keep, loose_keep, impl1_keep, impl2_keep)。"""
    j = RedundancyJudge(lex_thr, struct_thr)
    return j.keep_sets(texts)


# ---------------------------------------------------------------- 小工具
def _lines(txt: str, lo=8, hi=70, cap=0) -> list:
    out, seen = [], set()
    for ln in (txt or "").splitlines():
        ln = _CLEAN.sub("", ln).strip()
        if lo <= len(ln) <= hi and ln not in seen:
            seen.add(ln)
            out.append(ln)
        if cap and len(out) >= cap:
            break
    return out


def _roundrobin(groups: list) -> list:
    """轮转合并各槽位的条目（**内容无关**的顺序规则）。

    为什么不用「按重要性排」：路线不知道结论空间 `C_t`，任何按内容挑序的规则
    都要靠模型自评 ⇒ 协议 R-4 禁止。轮转是确定性且与内容无关的。
    """
    out, i = [], 0
    while True:
        added = False
        for g in groups:
            if i < len(g):
                out.append(g[i])
                added = True
        if not added:
            break
        i += 1
    return out


def _sha256(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- 执行器核心
class _Runner:
    """一次 route 调用的执行上下文：预算计数、调用、抽取、核验、装配。

    ⚠️ **预算作用域**：`calls()` / `tokens()` 返回的都是**本次 route 调用内**的增量，
    不是进程累计（LLM 对象在多任务之间共享 ⇒ 进程累计会把第 2 题卡死，F1）。
    """

    def __init__(self, ask, evidence_items, C, llm, log, ctx):
        self.ask = ask
        self.evidence_items = evidence_items
        self.C = C
        self.llm = llm
        self.log = log
        self.ctx = ctx
        self.judge = RedundancyJudge(C["lex_thr"], C["struct_thr"])
        self.models_used: list = []
        self.n_empty_retry = 0
        self.n_silent_empty = 0
        self.pool: list = []
        self._calls_at_start = getattr(llm, "n_api_calls", 0)
        self._tokens_at_start = getattr(llm, "n_tokens", 0)
        self.ev_text = "\n".join("%d. %s" % (i + 1, it["text"])
                                 for i, it in enumerate(evidence_items))
        self.ev_ids = [it.get("id") for it in evidence_items]

    # ---------------- 预算
    def calls(self) -> int:
        return getattr(self.llm, "n_api_calls", 0) - self._calls_at_start

    def tokens(self) -> int:
        return getattr(self.llm, "n_tokens", 0) - self._tokens_at_start

    def _est_call_cost(self, prompt, mt) -> int:
        """本次调用的预计 token 成本：prompt 长度 + max(实测均值×1.5, 1500)，上限 mt。"""
        avg = (self.tokens() / max(self.calls(), 1)) if self.calls() else 1500
        return len(prompt) + int(max(1500, min(avg * 1.5, mt)))

    def _models_since(self, idx) -> list:
        rec = getattr(self.llm, "rec", None) or []
        return [getattr(c, "model", "") for c in rec[idx:]]

    # ---------------- 调用
    def call(self, prompt, purpose, max_tokens=None, min_ok=10, budgets=()):
        """发一次调用。**自带预算守卫**（调用数 + token，作用域 = 本次 route 调用）。"""
        C = self.C
        mt = max_tokens or C["max_out_tokens"]
        out = ""
        rec0 = len(getattr(self.llm, "rec", None) or [])
        for attempt in range(2):
            if self.calls() >= C["max_calls"]:
                raise BudgetExceeded("调用数超过上限 %d" % C["max_calls"])
            if self.tokens() + self._est_call_cost(prompt, mt) > C["max_tokens"]:
                raise BudgetExceeded(
                    "token 预算不足：已用 %d / 上限 %d" % (self.tokens(), C["max_tokens"]))
            out = self.llm.chat(prompt,
                                 model=os.environ.get("PRIMARY_MODEL",
                                                      "MiniMax-M3.1-Flash-Preview"),
                                 temp=C["temp"], max_tokens=mt, budgets=budgets,
                                 purpose=purpose, min_ok=min_ok)
            for m in self._models_since(rec0):
                if m and m not in self.models_used:
                    self.models_used.append(m)
            self.log.append(dict(purpose=purpose, prompt=prompt, output=out,
                                 n_api_calls=self.calls(), n_tokens=self.tokens(),
                                 attempt=attempt + 1))
            if (out or "").strip():
                return out
            # 空输出：思考块吃光了预算（E3「疑似静默空」）⇒ 记一次并加预算重来
            self.n_silent_empty += 1
            if attempt == 0:
                self.n_empty_retry += 1
                mt = min(mt * 2, 16000)
        return out

    def gen_call(self, prompt, purpose, min_ok=40):
        return self.call(prompt, purpose, min_ok=min_ok)

    # ---------------- 提示词
    def slot_prompt(self, fid) -> str:
        if self.C["facet_enabled"]:
            return F.SLOT_Q.format(ask=self.ask, facet_name=F.facet_name(fid),
                                   facet_text=F.facet_text(fid), out_spec=F.OUT_SPEC)
        return "问题：%s\n\n%s" % (self.ask, F.OUT_SPEC)

    def resample_prompt(self, fid, round1_pool) -> str:
        """第二轮 prompt。**四种模式各自独立**（F2：`structured_no_cover` 必须真的不带清单）。"""
        mode = self.C["resample_mode"]
        if mode == "random":
            covered = RANDOM_REST_TEXT
            return F.RESAMPLE_Q.format(ask=self.ask, covered=covered,
                                       facet_name=F.facet_name(fid),
                                       facet_text=F.facet_text(fid), out_spec=F.OUT_SPEC)
        if mode == "structured_no_cover":
            # 第二轮**不带**已覆盖清单（track-d §4.3 的 no_rest_structured）
            return F.RESAMPLE_Q_NC.format(ask=self.ask, facet_name=F.facet_name(fid),
                                          facet_text=F.facet_text(fid), out_spec=F.OUT_SPEC)
        covered = "\n".join("- " + c for c in round1_pool[:24])
        return F.RESAMPLE_Q.format(ask=self.ask, covered=covered,
                                   facet_name=F.facet_name(fid),
                                   facet_text=F.facet_text(fid), out_spec=F.OUT_SPEC)

    def direct_prompt(self) -> str:
        """**无承载面指令**的直调（B0/B1/B2/B3 的生成端）。"""
        return "问题：%s\n\n%s" % (self.ask, F.OUT_SPEC)

    # ---------------- 抽取 / 拆分
    def extract(self, text, purpose, cap) -> list:
        if not text:
            return []
        t = self.call(F.EXTRACT_Q.format(t=text[:1200]), purpose, max_tokens=6000)
        return _lines(t, cap=cap)

    def split(self, pool, room) -> list:
        """N6 原子化拆分：只拆**长度 ≥ 40 字**的条目（格式属性，不是内容判断）。"""
        cands = [c for c in pool if len(c) >= 40]
        if not cands or room <= 0 or self.calls() + 1 > self.C["max_calls"]:
            return []
        t = self.call(F.SPLIT_Q.format(t="\n".join(cands[:10])), "A_split", max_tokens=6000)
        exist = set(pool)
        return [g for g in _lines(t, cap=min(room, 16)) if g not in exist][:room]

    # ---------------- N7 效用轴（唯一接触 oracle 的地方）
    def verify(self, pool) -> dict:
        C = self.C
        verdicts: dict = {}
        if not C["utility_axis"]:
            for c in pool:
                verdicts[c] = dict(verdict="未核验", evidence_ref=None, raw="")
            return verdicts
        for i in range(0, len(pool), C["verify_batch"]):
            if self.calls() + 1 > C["max_calls"]:
                break
            b = pool[i:i + C["verify_batch"]]
            lst = "\n".join("%d. %s" % (n + 1, b[n]) for n in range(len(b)))
            t = self.call(F.CHECK_Q.format(ask=self.ask, ev=self.ev_text, claims=lst),
                          "A_verify", max_tokens=8000, min_ok=len(b))
            lines = [x for x in (t or "").splitlines() if x.strip()]
            for n, ln in enumerate(lines[:len(b)]):
                m = VERDICT_RE.search(ln)
                vd = m.group() if m else "解析失败"
                ref = None
                if vd in ("支持", "矛盾"):
                    mm = REF_RE.search(ln[m.end():])
                    if mm:
                        k = int(mm.group(1)) - 1
                        if 0 <= k < len(self.ev_ids):
                            ref = self.ev_ids[k]
                verdicts[b[n]] = dict(verdict=vd, evidence_ref=ref, raw=ln.strip())
        return verdicts

    # ---------------- N7 新颖轴 + N8 装配
    def d2_and_assemble(self, pool, verdicts) -> dict:
        """D2 门（效用 → 新颖）与机械装配。

        **顺序**：先效用（核验），再新颖（去冗余）—— 去冗余**只在可交付子集上做**
        ⇒ 未被依据支持的近似重复项**不可能**把被支持的条目挤出答案（F4）。
        """
        C = self.C
        n_sup = sum(1 for v in verdicts.values() if v["verdict"] == "支持")
        n_bad = sum(1 for v in verdicts.values() if v["verdict"] == "矛盾")
        n_un = sum(1 for v in verdicts.values() if v["verdict"] in ("未提及", "非主张"))
        n_par = sum(1 for v in verdicts.values() if v["verdict"] == "解析失败")
        n_nv = sum(1 for v in verdicts.values() if v["verdict"] == "未核验")

        # 可交付子集：优先「被支持」；若一条都没有 ⇒ 走兜底（依据未覆盖）
        supported_idx = [i for i, c in enumerate(pool)
                         if verdicts.get(c, {}).get("verdict") == "支持"]
        fallback_eligible = [i for i, c in enumerate(pool)
                             if verdicts.get(c, {}).get("verdict")
                             in ("未提及", "非主张", "未核验")]
        if supported_idx:
            scope_idx, scope_kind = supported_idx, "supported"
            allowed = {"支持"}
        else:
            scope_idx, scope_kind = fallback_eligible, "fallback"
            allowed = {"未提及", "非主张", "未核验"}

        scope_texts = [pool[i] for i in scope_idx]
        if C["novel_axis"]:
            s_loc, l_loc, keep1, keep2 = self.judge.keep_sets(scope_texts)
        else:
            s_loc = list(range(len(scope_texts)))
            l_loc = list(range(len(scope_texts)))
            keep1, keep2 = [], []
        strict_idx = [scope_idx[k] for k in s_loc]
        loose_idx = [scope_idx[k] for k in l_loc]
        strict_set = set(strict_idx)
        order = strict_idx + [i for i in loose_idx if i not in strict_set]

        # ---- 字数上限：**整份答案**（含题面回显与段标题）≤ answer_char_cap
        section = ("## 依据未覆盖、仅供参考的事项" if scope_kind == "fallback"
                   else "## 经核验成立的依据")
        fixed = len("# %s\n\n%s\n\n" % (self.ask, section))
        item_budget = max(0, C["answer_char_cap"] - fixed)

        lines, used, shipped_texts = [], 0, []
        n_dup_suppressed = 0
        for i in order:
            c = pool[i]
            if verdicts.get(c, {}).get("verdict") not in allowed:
                continue
            # 装配期冗余否决：与**已装入**的条目在**任一实现**下冗余 ⇒ 不再装入
            # （strict 内部两两不冗余 ⇒ strict 永不被这条规则挤掉）
            # ⚠️ 消融臂 A_minus_novel 关闭的是**整个新颖轴** ⇒ 否决权也一并关闭。
            if C["novel_axis"] and any(self.judge.any_impl(c, s) for s in shipped_texts):
                n_dup_suppressed += 1
                continue
            ref = verdicts.get(c, {}).get("evidence_ref")
            item = ("- [%s] %s" % (ref, c)) if ref else ("- %s" % c)
            if used + len(item) + 1 > item_budget:
                continue          # ⚠️ continue 而不是 break：后面的短条目不该被一起丢掉（F14）
            lines.append(item)
            shipped_texts.append(c)
            used += len(item) + 1

        fallback = (scope_kind == "fallback" and bool(lines))
        body = "\n".join(lines) if lines else "- （无）"
        if scope_kind == "fallback":
            answer = "# %s\n\n## 依据未覆盖、仅供参考的事项\n\n%s" % (self.ask, body)
        else:
            answer = "# %s\n\n## 经核验成立的依据\n\n%s" % (self.ask, body)

        # 截断计数：分子分母**同源**（主路径 = 被支持条目；兜底路径 = 可兜底条目）（F14）
        if scope_kind == "fallback":
            trunc_den, trunc_pop = "n_fallback_eligible", len(scope_idx)
        else:
            trunc_den, trunc_pop = "n_supported", n_sup
        return dict(
            answer=answer, lines=lines, order=order, scope_idx=scope_idx,
            scope_kind=scope_kind, strict_idx=strict_idx, loose_idx=loose_idx,
            n_dup_suppressed=n_dup_suppressed, fallback=fallback,
            answer_truncated_count=max(0, trunc_pop - len(lines)),
            answer_truncated_denominator=trunc_den,
            n_sup=n_sup, n_bad=n_bad, n_un=n_un, n_par=n_par, n_nv=n_nv,
            n_dedup_strict=len(strict_idx), n_dedup_loose=len(loose_idx),
            n_impl1=len(keep1), n_impl2=len(keep2),
        )


# ---------------------------------------------------------------- meta 组装
def _build_meta(R: _Runner, C: dict, ctx: dict, res: dict, meta_extra: dict) -> dict:
    """把**实际产出**的字段装配成 `meta.json` 的内容（F5：声明有、代码也要有）。"""
    answer = res["answer"]
    n_verdicts = max(res["n_sup"] + res["n_bad"] + res["n_un"]
                      + res["n_par"] + res["n_nv"], 1)
    meta = dict(meta_extra)
    meta.update(
        # ---- 跨臂可比的身份字段
        run_id=ctx.get("run_id") or ("%s_%s" % (ctx.get("arm_id", "A_fixed"), _now_iso())),
        arm_id=ctx.get("arm_id", "A_fixed"),
        task_id=ctx.get("task_id", "UNKNOWN"),
        rep=ctx.get("rep", 1),
        seed=ctx.get("seed"),                 # 只是**运行标签**（见 seed_policy）
        seed_policy=ctx.get("seed_policy",
                            "api_seed_unsupported__label_only__NOT_reproducible"),
        seed_effective=None,                  # API 不支持种子 ⇒ 没有有效种子
        reproducibility="not_reproducible__no_api_seed_parameter",
        run_nonce=ctx.get("run_nonce") or _now_iso(),
        prompt_version=ctx.get("prompt_version", F.PROMPT_VERSION),
        prompt_hash=_sha256([s for _src, s in F.injected_strings()]),
        arm_config_hash=ctx.get("arm_config_hash") or _sha256(C),
        temperature=C["temp"],
        model=ctx.get("model_requested") or os.environ.get("PRIMARY_MODEL",
                                                            "MiniMax-M3.1-Flash-Preview"),
        model_requested=ctx.get("model_requested") or os.environ.get(
            "PRIMARY_MODEL", "MiniMax-M3.1-Flash-Preview"),
        models_used=list(R.models_used),      # ⚠️ 实际用过的模型（F15：client 会静默降级）
        models_tier=ctx.get("models_tier", ["MiniMax-M3.1-Flash-Preview"]),
        # ---- 预算与成本
        n_calls=R.calls(),
        n_tokens=R.tokens(),
        cost_usd=0.0,
        cost_basis="minimax_subscription",
        # ---- 样本有效性（协议 §4.7 E2/E4）
        valid=1 if len(answer.strip()) >= MIN_VALID_CHARS else 0,
        total=1,
        valid_samples=1 if len(answer.strip()) >= MIN_VALID_CHARS else 0,
        total_samples=1,
        over_budget_count=0,
        parsefail_rate=res["n_par"] / n_verdicts,
        internal_parsefail_rate=res["n_par"] / n_verdicts,
        silent_empty_count=R.n_silent_empty,
        n_silent_empty=R.n_silent_empty,
        n_empty_retry=R.n_empty_retry,
        # ---- 内容与诊断量
        n_pool=len(R.pool),
        n_shipped=len(res["lines"]),
        n_supported=res["n_sup"],
        n_contradicted=res["n_bad"],
        n_unmentioned=res["n_un"],
        n_unverified=res["n_nv"],
        n_parsefail=res["n_par"],
        conflict_rate_generated=res["n_bad"] / max(res["n_sup"] + res["n_bad"], 1),
        support_rate_generated=res["n_sup"] / max(res["n_sup"] + res["n_bad"], 1),
        answer_truncated_count=res["answer_truncated_count"],
        answer_truncated_denominator=res["answer_truncated_denominator"],
        answer_fallback=res["fallback"],
        answer_chars=len(answer),
        n_dup_suppressed=res["n_dup_suppressed"],
        collapse_flag=meta_extra.get("collapse_flag", False),
        evidence_prompt_checks=meta_extra.get("evidence_prompt_checks", 0),
        # ---- 依据包 / DEV 集身份
        devset_id=ctx.get("devset_id", "NOT_PROVIDED"),
        devset_hash=ctx.get("devset_hash", "NOT_PROVIDED"),
        evidence_pack_version=ctx.get("evidence_pack_version", "routeA-local-v1"),
        evidence_hash=ctx.get("evidence_hash") or _sha256(
            [[it.get("id"), it.get("text")] for it in R.evidence_items]),
    )
    meta["protocol_a4_not_produced"] = list(PROTOCOL_SIDE_FIELDS)
    meta["metadata_missing"] = [
        f for f in ("devset_id", "devset_hash")
        if meta.get(f) == "NOT_PROVIDED"
    ] + list(PROTOCOL_SIDE_FIELDS)
    return meta


# ---------------------------------------------------------------- 公开入口：A 臂
def run_route(ask: str, evidence_items: list, cfg: dict = None, llm=None,
              log: list = None, ctx: dict = None) -> dict:
    """跑一遍路线 A 的固定拓扑（N0…N8）。

    参数
    ----
    ask            题面（**路线只能看到这个；依据包只在核验侧**）
    evidence_items [{"id": "EV-...", "text": "..."}, ...]  只进核验提示词
    cfg            预注册常量（覆盖 DEFAULTS）
    llm            MeteredLLM（或任何有 .chat / .n_api_calls 的对象）
    log            可选：调用日志（每条含 prompt / 出参 / purpose）
    ctx            可选：运行上下文（arm_id / task_id / rep / seed / devset…）

    返回
    ----
    dict: answer / meta / pool / verdicts / gen_prompts
    """
    C = dict(DEFAULTS)
    C.update(cfg or {})
    if C["resample_mode"] not in RESAMPLE_MODES:
        raise ValueError("resample_mode 必须是 %s 之一（收到 %r）"
                         % (RESAMPLE_MODES, C["resample_mode"]))
    llm = llm or MeteredLLM()
    log = log if log is not None else []
    ctx = dict(ctx or {})
    R = _Runner(ask, evidence_items, C, llm, log, ctx)
    gen_prompts: list = []

    def _gen(prompt, purpose, min_ok=40):
        gen_prompts.append(prompt)
        return R.gen_call(prompt, purpose, min_ok=min_ok)

    meta_extra = dict(stage_counts={}, collapse_flag=False, collapse_kept=None,
                       collapse_threshold=None, round2_executed=False,
                       evidence_prompt_checks=0,
                       facet_enabled=C["facet_enabled"], resample_mode=C["resample_mode"],
                       novel_axis=C["novel_axis"], utility_axis=C["utility_axis"])

    # ---------------- N0 读题 / 装配输入
    # （路由与预算初始化；不产生任何模型输出）

    # ---------------- N1 槽位生成（第一轮）
    slot_answers, slot_facets = [], []
    for fid in C["round1_facets"]:
        a = _gen(R.slot_prompt(fid), "A_slot_%s" % fid, min_ok=40)
        slot_answers.append(a or "")
        slot_facets.append(fid)
    meta_extra["stage_counts"]["n1_gen"] = len(slot_answers)

    # ---------------- N2 断言抽取（逐槽位）
    slot_claims = []
    for fid, a in zip(slot_facets, slot_answers):
        slot_claims.append(R.extract(a, "A_extract_%s" % fid, C["extract_cap"]))
    meta_extra["stage_counts"]["n2_claims"] = sum(len(x) for x in slot_claims)

    # ---------------- N3 离散去冗余（**塌缩诊断量**，不控制任何分支）
    round1_pool = _roundrobin(slot_claims)
    r1_strict, r1_loose, _, _ = R.judge.keep_sets(round1_pool)
    kept_r1 = len(r1_strict)
    thr = C["collapse_mult"] * len(C["round1_facets"])
    meta_extra["collapse_kept"] = kept_r1
    meta_extra["collapse_threshold"] = thr
    meta_extra["collapse_flag"] = bool(kept_r1 < thr)
    meta_extra["stage_counts"]["n3_dedup_strict"] = kept_r1
    meta_extra["stage_counts"]["n3_dedup_loose"] = len(r1_loose)

    # ---------------- N4 条件重采样（第二轮）—— **恒定执行**
    # ⚠️ 塌缩量**不再**是开关（F3）。是否做第二轮由**臂级常量** resample_mode 决定，
    #    与数据无关；`resample_mode == "none"` 是消融臂 A_minus_R2 的**固定规格**。
    r2_answers, r2_facets = [], []
    if C["resample_mode"] != "none" and C["round2_facets"]:
        for fid in C["round2_facets"]:
            if R.calls() + 2 > C["max_calls"]:
                break                       # 预算守卫（不是数据依赖的拓扑开关）
            a = _gen(R.resample_prompt(fid, round1_pool), "A_resample_%s" % fid, min_ok=40)
            r2_answers.append(a or "")
            r2_facets.append(fid)
    meta_extra["round2_executed"] = bool(r2_answers)
    meta_extra["stage_counts"]["n4_resample"] = len(r2_answers)

    # ---------------- N5 断言抽取（第二轮，批量一次）
    r2_claims: list = []
    if r2_answers:
        got = R.extract("\n\n".join(r2_answers)[:2000], "A_extract_r2",
                        C["extract_cap"] * len(r2_answers))
        per = max(1, len(got) // max(len(r2_answers), 1))
        r2_claims = [got[i * per:(i + 1) * per] for i in range(len(r2_answers))]
    meta_extra["stage_counts"]["n5_claims"] = sum(len(x) for x in r2_claims)

    # ---------------- 断言池（内容无关的定序 + 定容）
    groups = []
    for i in range(max(len(slot_claims), len(r2_claims))):
        g = []
        if i < len(slot_claims):
            g += slot_claims[i]
        if i < len(r2_claims):
            g += [x for x in r2_claims[i] if x]
        if g:
            groups.append(g)
    pool = _roundrobin(groups)
    meta_extra["stage_counts"]["pool_pre_split"] = len(pool)
    pool = pool[:C["max_claims"]]
    meta_extra["stage_counts"]["pool_truncated"] = \
        meta_extra["stage_counts"]["pool_pre_split"] - len(pool)

    # ---------------- N6 原子化拆分
    room = max(0, C["max_claims"] - len(pool))
    split_out = R.split(pool, room)
    pool = pool + split_out
    meta_extra["stage_counts"]["n6_split"] = len(split_out)
    meta_extra["stage_counts"]["pool_total"] = len(pool)
    R.pool = pool

    # ---------------- N7 D2 门（效用轴 → 新颖轴）
    verdicts = R.verify(pool)
    res = R.d2_and_assemble(pool, verdicts)
    meta_extra["stage_counts"]["n7_dedup_strict"] = res["n_dedup_strict"]
    meta_extra["stage_counts"]["n7_dedup_loose"] = res["n_dedup_loose"]
    meta_extra["stage_counts"]["n7_impl1_lex"] = res["n_impl1"]
    meta_extra["stage_counts"]["n7_impl2_struct"] = res["n_impl2"]
    meta_extra["stage_counts"]["n7_scope"] = len(res["scope_idx"])
    meta_extra["stage_counts"]["n8_shipped"] = len(res["lines"])
    meta_extra["scope_kind"] = res["scope_kind"]

    # ---------------- N8 自检：依据包（题面之外的部分）不得出现在生成提示词里
    # ⚠️ 只检查「不在题面里的依据条目」：题面本身可能与依据包有字面重合，
    #    那不是泄漏；真正的泄漏是「模型没见过的依据内容被塞进了生成提示词」。
    checked = 0
    for p in gen_prompts:
        for it in evidence_items:
            t = (it["text"] or "").strip()
            if len(t) >= 6 and t not in ask:
                checked += 1
                if t in p:
                    raise RuntimeError(
                        "依据包条目（题面之外的部分）出现在生成提示词里 ⇒ 违反必留声明 #4，abort"
                        "（evidence_ref=%s）" % (it.get("id"),))
    meta_extra["evidence_prompt_checks"] = checked

    meta = _build_meta(R, C, ctx, res, meta_extra)
    return dict(answer=res["answer"], meta=meta, pool=pool, verdicts=verdicts,
                gen_prompts=gen_prompts, log=log)


# ---------------------------------------------------------------- 公开入口：B0–B3
def _b_tail(R: _Runner, raw_answers: list, C: dict):
    """B 臂的**共用尾**：抽取 → 拆分 → D2 门 → 装配（与 A 臂完全同一条尾）。"""
    claims = [R.extract(a, "B_extract_%d" % i, C["extract_cap"])
              for i, a in enumerate(raw_answers)]
    pool = _roundrobin(claims)[:C["max_claims"]]
    room = max(0, C["max_claims"] - len(pool))
    pool = pool + R.split(pool, room)
    R.pool = pool
    verdicts = R.verify(pool)
    res = R.d2_and_assemble(pool, verdicts)
    res["pool"] = pool
    res["claims"] = claims
    return res


def run_b_arm(ask: str, evidence_items: list, cfg: dict = None, llm=None,
              log: list = None, ctx: dict = None, kind: str = "B0",
              K: int = None, T_W: int = None, selector=None) -> dict:
    """协议 §8 (c) 强制的**等预算对照臂** B0 / B1 / B2 / B3（本次返工补实现，F9）。

    - **B0 直调基线**：1 次**无承载面指令**的直调生成 + 与 A 臂完全相同的尾。
    - **B1 等调用数**：内部采样 K 次直调（K = A 臂本任务本 rep 的**生成类调用数**），
      **固定取最后一份**（内容无关的选择规则，协议 §4.4）。
    - **B2 等 token**：采样直到本 rep 的 token 用量 ≥ T_W（T_W = A 臂本任务本 rep 的
      实际 token），**固定取最后一份**。
    - **B3 best-of-N（可选）**：在 K 份里由**外部核验器**挑矛盾最少的一份。
      ⚠️ 默认 selector 用**本路线的依据包核验**（判官与生成臂**不是同一个调用**，
      但**同厂商**）⇒ 跨厂商判官属协议侧，本轮不发起 OpenRouter 调用（F15/§8 R-8）。

    返回的 meta 与 A 臂同构（同样的字段、同样的口径），可直接跨臂比较。
    """
    C = dict(DEFAULTS)
    C.update(cfg or {})
    llm = llm or MeteredLLM()
    log = log if log is not None else []
    ctx = dict(ctx or {})
    ctx.setdefault("arm_id", kind)
    R = _Runner(ask, evidence_items, C, llm, log, ctx)
    meta_extra = dict(stage_counts={}, collapse_flag=False, collapse_kept=None,
                       collapse_threshold=None, round2_executed=False,
                       evidence_prompt_checks=0, arm_kind=kind,
                       facet_enabled=False, resample_mode="none",
                       novel_axis=C["novel_axis"], utility_axis=C["utility_axis"])

    raw: list = []
    if kind == "B0":
        raw = [R.gen_call(R.direct_prompt(), "B_direct_0", min_ok=40)]
    elif kind == "B1":
        if not K:
            raise ValueError("B1 需要 K（A 臂本任务本 rep 的生成类调用数）")
        for i in range(int(K)):
            raw.append(R.gen_call(R.direct_prompt(), "B_direct_%d" % i, min_ok=40))
        raw = [raw[-1]]                      # 固定取最后一份（内容无关）
    elif kind == "B2":
        if not T_W:
            raise ValueError("B2 需要 T_W（A 臂本任务本 rep 的实际 token）")
        if C["max_tokens"] < T_W:
            raise ValueError("B2 的 max_tokens（%d）必须 ≥ T_W（%d）"
                             % (C["max_tokens"], T_W))
        i = 0
        while R.tokens() < T_W and i < 64:
            raw.append(R.gen_call(R.direct_prompt(), "B_direct_%d" % i, min_ok=40))
            i += 1
        if not raw:
            raw = [R.gen_call(R.direct_prompt(), "B_direct_0", min_ok=40)]
        raw = [raw[-1]]                      # 固定取最后一份（内容无关）
    elif kind == "B3":
        if not K:
            raise ValueError("B3 需要 K")
        cands = [R.gen_call(R.direct_prompt(), "B_direct_%d" % i, min_ok=40)
                 for i in range(int(K))]
        if selector is None:
            selector = _default_best_of_n_selector(R, cands, C)
        pick = int(selector(cands))
        meta_extra["b3_candidates"] = len(cands)
        meta_extra["b3_selected"] = pick
        raw = [cands[pick]]
    else:
        raise ValueError("未知的对照臂 kind=%r" % kind)

    meta_extra["stage_counts"]["n1_gen"] = len(raw)
    res = _b_tail(R, raw, C)
    meta_extra["stage_counts"]["n2_claims"] = sum(len(x) for x in res.get("claims", []))
    meta_extra["stage_counts"]["pool_total"] = len(res["pool"])
    meta_extra["stage_counts"]["n7_dedup_strict"] = res["n_dedup_strict"]
    meta_extra["stage_counts"]["n7_dedup_loose"] = res["n_dedup_loose"]
    meta_extra["stage_counts"]["n7_impl1_lex"] = res["n_impl1"]
    meta_extra["stage_counts"]["n7_impl2_struct"] = res["n_impl2"]
    meta_extra["stage_counts"]["n8_shipped"] = len(res["lines"])
    meta_extra["scope_kind"] = res["scope_kind"]
    meta_extra["b1_K"] = K
    meta_extra["b2_T_W"] = T_W
    meta = _build_meta(R, C, ctx, res, meta_extra)
    return dict(answer=res["answer"], meta=meta, pool=res["pool"],
                verdicts={}, gen_prompts=[], log=log)


def _default_best_of_n_selector(R: _Runner, cands: list, C: dict):
    """B3 的默认外部核验器择优：按**依据包核验出的矛盾数**最少挑一份。

    ⚠️ 这**不是**生成臂自评（协议 R-4 / track-d §5.4）：判据来自**外部文本**
    （依据包），择优发生在生成之后，且调用的是**另一个**提示词（CHECK_Q）。
    ⚠️ 但它与生成臂**同厂商** ⇒ 跨厂商判官属协议侧，本轮不发起（§8 R-8）。
    """
    def select(cands):
        best, best_i = None, 0
        for i, cand in enumerate(cands):
            claims = R.extract(cand, "B3_judge_%d" % i, C["extract_cap"])
            pool = _roundrobin([claims])[:C["max_claims"]]
            v = R.verify(pool)
            n_bad = sum(1 for x in v.values() if x["verdict"] == "矛盾")
            if best is None or n_bad < best:
                best, best_i = n_bad, i
        return best_i
    return select


# ---------------------------------------------------------------- 输出契约
def save_run(out_root: str, arm_id: str, task_id: str, rep: int,
             answer: str, meta: dict) -> tuple:
    """写出协议 §8 (a2) 要求的 `rep<k>.answer.md` + `rep<k>.meta.json`。"""
    d = os.path.join(out_root, arm_id, task_id)
    os.makedirs(d, exist_ok=True)
    ap = os.path.join(d, "rep%d.answer.md" % rep)
    mp = os.path.join(d, "rep%d.meta.json" % rep)
    with open(ap, "w", encoding="utf-8") as f:
        f.write(answer)
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
    return ap, mp


def run_task(ask: str, evidence_items: list, cfg: dict = None, llm=None,
             log: list = None, ctx: dict = None, runner=run_route, **kw) -> dict:
    """包一层：预算溢出（协议 §4.7 E4）⇒ 该样本**作废并计数**，不抛出到调用方。

    返回的 dict 里 `meta["over_budget_count"]` 必为 1（作废）或 0（正常）。
    """
    try:
        r = runner(ask, evidence_items, cfg=cfg, llm=llm, log=log, ctx=ctx, **kw)
        r["meta"]["over_budget_count"] = 0
        return r
    except BudgetExceeded as e:
        C = dict(DEFAULTS)
        C.update(cfg or {})
        ctx = dict(ctx or {})
        meta = dict(
            run_id=ctx.get("run_id"), arm_id=ctx.get("arm_id", "A_fixed"),
            task_id=ctx.get("task_id", "UNKNOWN"), rep=ctx.get("rep", 1),
            seed=ctx.get("seed"), seed_policy="api_seed_unsupported__label_only__NOT_reproducible",
            prompt_version=ctx.get("prompt_version", F.PROMPT_VERSION),
            temperature=C["temp"], n_calls=0, n_tokens=0, cost_usd=0.0,
            valid=0, total=1, valid_samples=0, total_samples=1,
            over_budget_count=1, budget_error=str(e),
            answer_chars=0, answer_fallback=False, n_shipped=0, n_pool=0,
            n_supported=0, n_contradicted=0, n_unmentioned=0, n_unverified=0,
            n_parsefail=0, n_dup_suppressed=0, scope_kind=None,
            answer_truncated_count=0, answer_truncated_denominator="n_supported",
            collapse_kept=None, collapse_threshold=None, round2_executed=False,
            parsefail_rate=None, internal_parsefail_rate=None,
            silent_empty_count=0, collapse_flag=False,
            protocol_a4_not_produced=list(PROTOCOL_SIDE_FIELDS),
            metadata_missing=list(PROTOCOL_SIDE_FIELDS),
        )
        return dict(answer="", meta=meta, pool=[], verdicts={}, gen_prompts=[], log=log)
