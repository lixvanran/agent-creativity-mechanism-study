# -*- coding: utf-8 -*-
"""路线 A 的固定拓扑执行器（**人设计的 DAG，零训练**）。

与 `creativity_lab/learnarch.py` 的区别（这是本文件存在的理由）：
- learnarch 跑的是**学出来的策略**（在图上按 14 维权重选下一条边）——那是路线 B/C 的事；
- 本文件跑的是**写死的 DAG**：节点、边、条件、预算上限全部在 `spec.yaml` 里事前声明，
  执行器里没有任何权重、没有 policy、没有「哪条边更值钱」的判断。

拓扑（固定，见 spec.yaml）：

    N1  槽位生成（第一轮，FA1–FA4）        4 次调用
    N2  断言抽取（逐槽位）                  4 次调用
    N3  塌缩检测（**离散**：去冗余后存活断言数）  0 次调用
    N4  条件重采样（第二轮，FA5–FA6）       ≤3 次调用（仅在 N3 触发时）
    N5  原子化拆分                          ≤1 次调用
    N6  D2 门：新颖轴（离散冗余）+ 效用轴（依据核验）  ≤4 次调用
    N7  机械装配（不调用模型）                0 次调用

⚠️ **依据包只出现在 N6 的核验提示词里**（`/workspace/lab/METHOD.md` §4 必留声明 #4：
「依据包只进判官/核验侧，不进被测臂的提示词」）。本文件在运行时**断言**这一点：
所有生成类提示词（N1/N4）都不含依据包文本 —— 断言失败即 abort。

⚠️ **路线内部不使用 embedding**：本项目的实测（`embo-01` 句级集合距离在两臂上
SEP≈0.002）表明该几何量在句级没有分辨率；用它做「重复/不重复」判定会把 27 条断言
压成 1 条（本次冒烟实测，见 smoke_log.txt），**等于把路线自己的宽度指标毁掉**。
⇒ 冗余判定改用**离散结构量**：数字指纹（`net_dimension_gain.hard_tokens`）
+ 4 字中文 n-gram 覆盖率（`net_dimension_gain.cjk_ngrams`）—— 这两套与协议 §1.7
的跨臂对齐口径同源。
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, "/workspace/lab")            # creativity_lab 包（client/verify/ops/metrics）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from creativity_lab.client import LLM            # noqa: E402
import facets as F                               # noqa: E402
sys.path.insert(0, "/workspace/lab")
from net_dimension_gain import hard_tokens, cjk_ngrams   # noqa: E402

# ---------------------------------------------------------------- 预注册常量
# ⚠️ 全部事前写死，见 DESIGN.md §2「预注册常量表」。事后不得调整（协议 R-9）。
DEFAULTS = dict(
    # --- 拓扑 ---
    round1_facets=list(F.ROUND1_FACETS),
    round2_facets=list(F.ROUND2_FACETS),
    facet_enabled=True,          # False ⇒ 槽位不带承载面指令（消融臂 A_minus_facet）
    resample_mode="structured",  # structured | random | none
    novel_axis=True,             # False ⇒ 不去冗余（消融臂 A_minus_novel）
    utility_axis=True,           # False ⇒ 不做外部核验（消融臂 A_minus_utility）
    # --- 预算 ---
    max_calls=24,                # 每 (臂,任务,rep) 的模型调用上限
    max_tokens=40000,            # 协议 §4.4 的 T_max
    max_claims=48,               # 断言池上限（事前写死，内容无关的截断）
    extract_cap=8,               # 每个槽位最多抽 8 条
    verify_batch=12,             # 核验批大小
    answer_char_cap=400,         # 答案正文字数上限（三臂一致）
    # --- 判据 ---
    lex_thr=0.75,                # 实现 1：char-bigram Jaccard 阈值（近乎逐字重复）
    struct_thr=0.70,             # 实现 2：4-gram 覆盖率阈值（改写型重复）
    collapse_mult=1.0,           # 塌缩判据：存活断言数 < collapse_mult × K₁ ⇒ 触发
    # --- 采样 ---
    temp=0.7,                    # 协议 §4.3 三臂一致
    max_out_tokens=6000,
)

# 断言抽取的行过滤（沿用项目既有口径：8–70 字）
_CLEAN = re.compile(r"^\s*[-*\d.、)）]+\s*")
VERDICT_RE = re.compile(r"(非主张|支持|矛盾|未提及)")
REF_RE = re.compile(r"\b(\d{1,3})\b")

# 消融对照臂专用：与任务无关的占位上下文（**只在 random_rest 对照臂里出现**）
RANDOM_REST_TEXT = (
    "（以下内容与本任务无关，只作占位）清晨的街道很安静，"
    "早点摊的蒸汽在冷空气里散开，远处传来第一班公交车的引擎声。"
)


class BudgetExceeded(RuntimeError):
    pass


class MeteredLLM(LLM):
    """给 `creativity_lab.client.LLM` 加一个 usage 计量（**不改共享包**）。

    共享 client 的 `rec` 里没有 token 数（只有 max_tokens 与 content_len），
    而协议的 R3 / §4.4 要求报 `n_tokens` ⇒ 这里在 `_post` 里把 API 返回的
    `usage` 抄下来。不改原文件 ⇒ 其它两条路线不受影响。
    """

    def __init__(self, recorder=None):
        super().__init__(recorder=recorder)
        self.usage_log: list = []

    def _post(self, url, payload, timeout=240):
        d = super()._post(url, payload, timeout)
        u = d.get("usage") or {}
        self.usage_log.append(dict(
            url=url,
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


def redundancy(texts: list, lex_thr: float, struct_thr: float):
    """两个**独立实现**判冗余，返回 (strict_keep, loose_keep, impl1_keep, impl2_keep)。

    实现 1 · 词法：char-bigram Jaccard ≥ lex_thr  ⇒ 近乎逐字重复
    实现 2 · 结构：数字指纹互为子集（且都非空）+ 4-gram 覆盖率 ≥ struct_thr ⇒ 改写型重复

    组合方式（**不取更严的删除**，理由见 DESIGN §4.3）：
      strict_keep = 两实现都认为「不重复」的条目  → 优先占用答案字数预算
      loose_keep  = 至少一个实现认为「不重复」的条目 → 填剩余预算
    ⇒ 任何单实现都**不能**把一条断言完全赶出答案（避免假阳性毁掉宽度）；
      而字数预算优先给「两实现都同意不重复」的条目（避免重复吃掉预算）。
    """
    n = len(texts)
    if n == 0:
        return [], [], [], []
    BG = [_char_bigrams(t) for t in texts]
    HT = [set(hard_tokens(t)) for t in texts]
    NG = [set(cjk_ngrams(t)) for t in texts]

    def impl1_red(i, j):
        return _jaccard(BG[i], BG[j]) >= lex_thr

    def impl2_red(i, j):
        ha, hb = HT[i], HT[j]
        if not ha or not hb:                 # 没有硬指纹 ⇒ 不判改写型重复（避免假阳性）
            return False
        if not (ha <= hb or hb <= ha):
            return False
        def cov(x, y):
            return len(NG[x] & NG[y]) / max(len(NG[x]), 1)
        return max(cov(i, j), cov(j, i)) >= struct_thr

    keep1, keep2 = [], []
    for i in range(n):
        if not any(impl1_red(i, j) for j in keep1):
            keep1.append(i)
    for i in range(n):
        if not any(impl2_red(i, j) for j in keep2):
            keep2.append(i)
    s = set(keep1) & set(keep2)
    l = set(keep1) | set(keep2)
    strict = [i for i in range(n) if i in s]
    loose = [i for i in range(n) if i in l]
    return strict, loose, keep1, keep2


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


# ---------------------------------------------------------------- 主流程
def run_route(ask: str, evidence_items: list, cfg: dict = None, llm=None,
              log: list = None) -> dict:
    """跑一遍路线 A 的固定拓扑。

    参数
    ----
    ask            题面（**路线只能看到这个；依据包只在核验侧**）
    evidence_items [{"id": "EV-...", "text": "..."}, ...]  只进核验提示词
    cfg            预注册常量（覆盖 DEFAULTS）
    llm            MeteredLLM（或任何有 .chat / .n_api_calls 的对象）
    log            可选：调用日志（每条含 prompt / 出参 / purpose）

    返回
    ----
    dict: answer / meta / pool / verdicts / gen_prompts
    """
    C = dict(DEFAULTS)
    C.update(cfg or {})
    llm = llm or MeteredLLM()
    log = log if log is not None else []

    ev_text = "\n".join("%d. %s" % (i + 1, it["text"]) for i, it in enumerate(evidence_items))
    ev_ids = [it.get("id") for it in evidence_items]

    gen_prompts: list = []          # 生成类提示词（末尾断言依据包不在其中）

    _calls_at_start = getattr(llm, "n_api_calls", 0)

    def _calls():
        """**本次 route 调用内**已用的调用数（预算守卫按任务计，不按进程计）。"""
        return getattr(llm, "n_api_calls", 0) - _calls_at_start

    def _tokens():
        return getattr(llm, "n_tokens", 0)

    # ⚠️ budgets=() ⇒ **不交给共享 client 兜底**。client 的默认 budgets=(12000,16000)
    #    会在 finish_reason=="length" 时重试 2 次，代价是双倍的 token 与调用数
    #    （本项目 client 文档已记「<think> 块会吃光 max_tokens」）。
    #    本函数自己管升级：空输出 ⇒ 加预算重来**一次**（上限 2 次尝试）。
    n_empty_retry = [0]
    n_silent_empty = [0]

    def _est_call_cost(prompt, mt):
        """本次调用的预计 token 成本：prompt 长度 + max(实测均值×1.5, 1500)，上限 mt。"""
        avg = (_tokens() / max(_calls(), 1)) if _calls() else 1500
        return len(prompt) + int(max(1500, min(avg * 1.5, mt)))

    def call(prompt, purpose, max_tokens=None, min_ok=10, budgets=()):
        mt = max_tokens or C["max_out_tokens"]
        out = ""
        for attempt in range(2):
            if _calls() >= C["max_calls"]:
                raise BudgetExceeded("调用数超过上限 %d" % C["max_calls"])
            if _tokens() + _est_call_cost(prompt, mt) > C["max_tokens"]:
                raise BudgetExceeded("token 预算不足：已用 %d / 上限 %d" % (_tokens(), C["max_tokens"]))
            out = llm.chat(prompt,
                           model=os.environ.get("PRIMARY_MODEL", "MiniMax-M3.1-Flash-Preview"),
                           temp=C["temp"], max_tokens=mt, budgets=budgets,
                           purpose=purpose, min_ok=min_ok)
            log.append(dict(purpose=purpose, prompt=prompt, output=out,
                            n_api_calls=_calls(), n_tokens=_tokens(),
                            attempt=attempt + 1))
            if (out or "").strip():
                return out
            # 空输出：思考块吃光了预算（E3「疑似静默空」）⇒ 记一次并加预算重来
            n_silent_empty[0] += 1
            if attempt == 0:
                n_empty_retry[0] += 1
                mt = min(mt * 2, 16000)
        return out

    def gen_call(prompt, purpose, min_ok=40):
        gen_prompts.append(prompt)
        return call(prompt, purpose, min_ok=min_ok)

    meta = dict(stage_counts={}, trigger_fired=False, trigger_kept=None,
                facet_enabled=C["facet_enabled"], resample_mode=C["resample_mode"],
                novel_axis=C["novel_axis"], utility_axis=C["utility_axis"])

    # ---------------- N1 槽位生成（第一轮）
    slot_answers, slot_facets = [], []
    for fid in C["round1_facets"]:
        if C["facet_enabled"]:
            p = F.SLOT_Q.format(ask=ask, facet_name=F.facet_name(fid),
                                facet_text=F.facet_text(fid), out_spec=F.OUT_SPEC)
        else:
            p = "问题：%s\n\n%s" % (ask, F.OUT_SPEC)
        a = gen_call(p, "A_slot_%s" % fid, min_ok=40)
        slot_answers.append(a or "")
        slot_facets.append(fid)
    meta["stage_counts"]["n1_gen"] = len(slot_answers)

    # ---------------- N2 断言抽取（逐槽位）
    slot_claims = []
    for fid, a in zip(slot_facets, slot_answers):
        if not a:
            slot_claims.append([])
            continue
        t = call(F.EXTRACT_Q.format(t=a[:1200]), "A_extract_%s" % fid, max_tokens=6000)
        slot_claims.append(_lines(t, cap=C["extract_cap"]))
    meta["stage_counts"]["n2_claims"] = sum(len(x) for x in slot_claims)

    # ---------------- N3 塌缩检测（离散：去冗余后存活断言数 < mult × K₁）
    round1_pool = _roundrobin(slot_claims)
    r1_strict, r1_loose, _, _ = redundancy(round1_pool, C["lex_thr"], C["struct_thr"])
    kept_r1 = len(r1_strict)
    meta["trigger_kept"] = kept_r1
    thr_keep = C["collapse_mult"] * len(C["round1_facets"])
    fire = bool(C["resample_mode"] != "none" and kept_r1 < thr_keep
                and _calls() + 4 <= C["max_calls"])
    meta["trigger_fired"] = fire

    # ---------------- N4 条件重采样（第二轮）
    r2_answers, r2_facets = [], []
    if fire:
        ctx = RANDOM_REST_TEXT if C["resample_mode"] == "random" else \
            "\n".join("- " + c for c in round1_pool[:24])
        for fid in C["round2_facets"]:
            if _calls() + 2 > C["max_calls"]:
                break
            p = F.RESAMPLE_Q.format(ask=ask, covered=ctx, facet_name=F.facet_name(fid),
                                    facet_text=F.facet_text(fid), out_spec=F.OUT_SPEC)
            a = gen_call(p, "A_resample_%s" % fid, min_ok=40)
            r2_answers.append(a or "")
            r2_facets.append(fid)
    meta["stage_counts"]["n4_resample"] = len(r2_answers)

    # 第二轮的断言抽取（一次批量调用）
    r2_claims: list = []
    if r2_answers:
        t = call(F.EXTRACT_Q.format(t="\n\n".join(r2_answers)[:2000]), "A_extract_r2",
                 max_tokens=6000)
        got = _lines(t, cap=C["extract_cap"] * len(r2_answers))
        per = max(1, len(got) // max(len(r2_answers), 1))
        r2_claims = [got[i * per:(i + 1) * per] for i in range(len(r2_answers))]
    meta["stage_counts"]["n4_claims"] = sum(len(x) for x in r2_claims)

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
    meta["stage_counts"]["pool_pre_split"] = len(pool)
    pool = pool[:C["max_claims"]]                        # 定容：按轮转序截，内容无关
    split_cands = [c for c in pool if len(c) >= 40]      # 长度是格式属性，不是内容判断
    room = max(0, C["max_claims"] - len(pool))
    meta["stage_counts"]["pool_truncated"] = meta["stage_counts"]["pool_pre_split"] - len(pool)

    # ---------------- N5 原子化拆分
    split_out: list = []
    if split_cands and room > 0 and _calls() + 1 <= C["max_calls"]:
        t = call(F.SPLIT_Q.format(t="\n".join(split_cands[:10])), "A_split", max_tokens=6000)
        exist = set(pool)
        split_out = [g for g in _lines(t, cap=min(room, 16)) if g not in exist][:room]
    pool = pool + split_out
    meta["stage_counts"]["n5_split"] = len(split_out)
    meta["stage_counts"]["pool_total"] = len(pool)

    # ---------------- N6 D2 门
    # 6a 新颖轴（去冗余）：两个离散实现，strict 优先占预算、loose 填尾
    strict_idx, loose_idx, keep1, keep2 = redundancy(pool, C["lex_thr"], C["struct_thr"])
    if not C["novel_axis"]:
        strict_idx, loose_idx = list(range(len(pool))), list(range(len(pool)))
    meta["stage_counts"]["n6_dedup_strict"] = len(strict_idx)
    meta["stage_counts"]["n6_dedup_loose"] = len(loose_idx)
    meta["stage_counts"]["n6_impl1_lex"] = len(keep1)
    meta["stage_counts"]["n6_impl2_struct"] = len(keep2)

    # 6b 效用轴（依据核验）—— **唯一接触 oracle 的地方**
    verdicts: dict = {}
    if C["utility_axis"]:
        for i in range(0, len(pool), C["verify_batch"]):
            if _calls() + 1 > C["max_calls"]:
                break
            b = pool[i:i + C["verify_batch"]]
            lst = "\n".join("%d. %s" % (n + 1, b[n]) for n in range(len(b)))
            t = call(F.CHECK_Q.format(ask=ask, ev=ev_text, claims=lst), "A_verify",
                     max_tokens=8000, min_ok=len(b))
            lines = [x for x in (t or "").splitlines() if x.strip()]
            for n, ln in enumerate(lines[:len(b)]):
                m = VERDICT_RE.search(ln)
                vd = m.group() if m else "解析失败"
                ref = None
                if vd in ("支持", "矛盾"):
                    mm = REF_RE.search(ln[m.end():])
                    if mm:
                        k = int(mm.group(1)) - 1
                        if 0 <= k < len(ev_ids):
                            ref = ev_ids[k]
                verdicts[b[n]] = dict(verdict=vd, evidence_ref=ref, raw=ln.strip())
    else:
        # 消融臂 A_minus_utility：不做外部核验（⚠️ 预期会掉 F2/G2/R1）
        for c in pool:
            verdicts[c] = dict(verdict="未核验", evidence_ref=None, raw="")

    n_sup = sum(1 for v in verdicts.values() if v["verdict"] == "支持")
    n_bad = sum(1 for v in verdicts.values() if v["verdict"] == "矛盾")
    n_un = sum(1 for v in verdicts.values() if v["verdict"] in ("未提及", "非主张"))
    n_par = sum(1 for v in verdicts.values() if v["verdict"] == "解析失败")
    n_nv = sum(1 for v in verdicts.values() if v["verdict"] == "未核验")

    # ---------------- N7 机械装配（不调用模型）
    order = list(strict_idx) + [i for i in loose_idx if i not in set(strict_idx)]
    lines, used = [], 0
    for i in order:
        c = pool[i]
        if verdicts.get(c, {}).get("verdict") != "支持":
            continue
        ref = verdicts.get(c, {}).get("evidence_ref")
        item = ("- [%s] %s" % (ref, c)) if ref else ("- %s" % c)
        if used + len(item) + 1 > C["answer_char_cap"]:
            break
        lines.append(item)
        used += len(item) + 1
    fallback = False
    if not lines:
        # 兜底（沿用本项目既有先例 learnarch.run_episode）：一条都没被支持时，
        # 退回「依据未覆盖」的条目，避免产出空壳；**必须如实标注 fallback**。
        for i in order:
            c = pool[i]
            if verdicts.get(c, {}).get("verdict") in ("未提及", "非主张", "未核验"):
                item = "- %s" % c
                if used + len(item) + 1 > C["answer_char_cap"]:
                    break
                lines.append(item)
                used += len(item) + 1
        fallback = bool(lines)
    if fallback:
        answer = "# %s\n\n## 依据未覆盖、仅供参考的事项\n\n%s" % (ask, "\n".join(lines))
    else:
        answer = "# %s\n\n## 经核验成立的依据\n\n%s" % (ask, "\n".join(lines) if lines else "- （无）")

    # ---------------- 自检：依据包**超出题面的部分**不得出现在生成提示词里
    # ⚠️ 只检查「不在题面里的依据条目」：题面本身可能与依据包有字面重合
    #    （例如题面自己写了阶梯价，依据包把同一条规则重述一遍），
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
    meta["evidence_prompt_checks"] = checked

    meta.update(
        n_calls=_calls(),
        n_tokens=_tokens(),
        n_pool=len(pool),
        n_supported=n_sup, n_contradicted=n_bad, n_unmentioned=n_un,
        n_parsefail=n_par, n_unverified=n_nv,
        internal_parsefail_rate=(n_par / max(len(verdicts), 1)),
        conflict_rate_generated=(n_bad / max(n_sup + n_bad, 1)),
        support_rate_generated=(n_sup / max(n_sup + n_bad, 1)),
        n_slots=len(slot_answers) + len(r2_answers),
        answer_chars=len(answer),
        answer_truncated_count=max(0, n_sup - len(lines)),
        answer_fallback=fallback,
        n_empty_retry=n_empty_retry[0],
        n_silent_empty=n_silent_empty[0],
    )
    return dict(answer=answer, meta=meta, pool=pool, verdicts=verdicts,
                gen_prompts=gen_prompts, log=log)
