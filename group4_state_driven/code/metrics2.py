#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 离散结构量判据（主判据）+ 判据自检

═══ 为什么主判据是离散结构量而不是几何量 ═══
机制组实测：句级集合距离 臂内 0.3896 vs 臂间 0.3569 —— 臂间比臂内还小。
「组织取舍」在几何上表现为**产出收窄到子空间**（臂内距离变小），
而臂间距离衡量的是**整体位置分离** ⇒ 几何量对不上机制。
离散结构量测的是「**内容里有什么**」，不是「内容在哪里」。

═══ 三个判据 ═══
D-1 CKF 锚点落地率 / 换值同步
    档案里的可核事实（数字/专名/日期）有没有真的进正文；换值后正文痕迹是否跟着换。
    ★ 「档案被复述」不算通过 —— 换值同步才是。
D-2 状态转移敏感度（置换探针）
    同一档案、同一题，让 g 步看到**不同的初稿**（历史置换），
    看约束₂ 是否改变。⇒ 直接测「状态转移律 ≠ 末端选择器」。
D-3 约束关键词命中差
    档案 3 条「取舍约束」的关键词命中率 − 「拒绝」字段关键词命中率。
    ★ 「拒绝」字段是**干扰项**（distractor），借 multi-mind v0.8 的设计：
      判据里放应当被无视的条目，防止无脑复述刷分。

═══ 铁律 ═══
判据必须**先证明自己能抓到东西**：每个判据配阳性/阴性自检，
自检不过 ⇒ 该判据作废，不是「没测到效应」。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import runner as R
    STANCE_FIELDS = R.STANCE_FIELDS
except Exception:                                   # 独立使用时兜底
    STANCE_FIELDS = [("自选极性", ""), ("立场核心", ""), ("选它的理由", ""), ("来历", ""),
                     ("取舍约束", ""), ("拒绝", ""), ("语气", ""), ("强度封顶", ""), ("锚定问题", "")]

# ---------------------------------------------------------------- 文本工具
_CJK = re.compile(r"[一-鿿]")
_KEEP_CJK = re.compile(r"[^一-鿿]")          # 只保留中文（用于关键词抽取）
_KEEP_TXT = re.compile(r"[^一-鿿A-Za-z0-9]")  # 保留中文+数字+字母（用于覆盖率/锚点）
_PUNCT = re.compile(r"[^\w一-鿿]+", re.U)

STOP2 = set("""
的 了 是 在 和 与 也 就 都 不 要 没 你 我 他 她 它 们 这 那 个 一 种 能 能 可 须
必 禁 止 说 有 为 对 从 到 上 下 中 里 外 前 后 之 其 所 而 但 因 所 以 如 果
什 么 怎 样 如 果 已 还 又 再 更 最 很 太 非 常 把 被 让 给 向 由 于 以 及 或
自 己 我 们 他 们 这 些 那 些 每 各 别 另 其 它 某 某 个 一 些 点 条 件 次
""".split())


def norm(text: str) -> str:
    """归一化：去标点、压空白。用于子串匹配。"""
    return _PUNCT.sub("", text or "")


def keywords(text: str, topk: int = 10, ngram: int = 2) -> list:
    """抽中文关键词（无分词库：用字符 n-gram + 停用词过滤）。

    ★ ngram 默认 2 而非 3：中文三字滑窗在「约束」与「正文」之间几乎不可能
      字面对齐（"医保目" vs 正文里的"医保谈判"），命中���几乎为 0；
      双字 gram 对表达差异鲁棒得多。严格命中另用 3-gram 单独报告。
    """
    t = _KEEP_CJK.sub("", text or "")
    if not t:
        return []
    cand = []
    for n in (ngram, ngram - 1):
        for i in range(len(t) - n + 1):
            g = t[i:i + n]
            if any(b in STOP2 for b in (g[:2], g[-2:])):
                continue
            cand.append(g)
    c = Counter(cand)
    out = []
    for g, cnt in c.most_common(topk * 4):
        if any(g != o and g in o for o in out):
            continue
        out.append(g)
        if len(out) >= topk:
            break
    return out


def gram_set(text: str, n: int = 2) -> set:
    """正文字符 n-gram 集合（去空白/标点，**保留数字与字母**）。

    ★ 数字必须保留：可核事实的主体就是数字（"病历编号 2048"、"四十八万"）。
      v1 实测 bug：只保留中文 ⇒ 数字被滤掉 ⇒ 覆盖率恒为 0。
    """
    t = _KEEP_TXT.sub("", text or "")
    return {t[i:i + n] for i in range(len(t) - n + 1)} if len(t) >= n else set()


def hit_rate(text: str, kws: list) -> float:
    """关键词命中率：命中数 / 总数。"""
    if not kws:
        return 0.0
    n = norm(text)
    return sum(1 for k in kws if norm(k) in n) / len(kws)


def hit_which(text: str, kws: list) -> list:
    n = norm(text)
    return [k for k in kws if norm(k) in n]


# ---------------------------------------------------------------- D-1 CKF
def anchor_keys(anchor: str) -> list:
    """从锚点里抽**可核标识**：优先数字/字母数字串（"2048"），否则用整句。

    ★ v1 实测 bug：注入档案用的是整句（"她在省城省立医院看病时的病历编号是 2048"），
      但正文里模型只写 "2048" ⇒ 用整句去正文里找，**永远匹配不上**，
      ckf_hit 恒为 0 且会被误读成"锚点没落地"。
    """
    if not anchor:
        return []
    ids = re.findall(r"[A-Za-z]*\d+[A-Za-z]*", anchor)
    if ids:
        return list(dict.fromkeys(ids))
    # 无数字 ⇒ 短语型锚点（观点文里常是"模板句"这类自然短语）。
    # 返回 [小写, 原形] 两个候选 ⇒ 匹配时**任一命中**即算 ⇒ 大小写不敏感。
    a = anchor.strip()
    return [a.lower(), a] if a.lower() != a else [a]


def ckf_anchor_hit(text: str, anchor: str) -> dict:
    """锚点落地：档案里的可核事实在正文里出现了吗（按 anchor_keys 判定）。"""
    if not anchor:
        return {"applicable": False}
    n = norm(text)
    keys = anchor_keys(anchor)
    hit = [k for k in keys if _hit_any(n, [k])]
    return {"applicable": True, "anchor": anchor, "keys": keys,
            "hit": bool(hit), "hit_keys": hit}


def _hit_any(text_norm: str, keys: list) -> bool:
    """任一候选键命中即算。

    ★ 数字型锚点：精确匹配（含数字，是身份标识）。
    ★ 短语型锚点（无数字，如模板句 "the importance of"）：**大小写不敏感**。
      理由：正文里写的是 "The importance of..."，而锚点是小写 ⇒ 不转小写就永远不匹配。
    """
    if any(any(ch.isdigit() for ch in k) for k in keys):
        return any(norm(k) in text_norm for k in keys)
    tl = text_norm.lower()
    return any(norm(k).lower() in tl for k in keys)


def ckf_swap_synchrony(text_orig: str, text_swap: str, anchor_old: str, anchor_new: str) -> dict:
    """换值同步：档案里锚点从 old 换成 new，正文痕迹是否跟着换。

    判定（全部机械，零判官）：
      new_in_new   新值出现在换值版正文里   —— 期望高
      old_in_new   旧值出现在换值版正文里   —— 期望低
      new_in_orig  新值出现在原版正文里     —— 期望低（对照）
    「同步」要求 new_in_new 高 **且** old_in_new / new_in_orig 低。
    """
    if not (anchor_old and anchor_new):
        return {"applicable": False}
    no, ns = norm(text_orig), norm(text_swap)
    # ★ 用**检测键**（数字/字母数字串），不是整句锚点。
    #   与 ckf_anchor_hit 保持一致 —— v1 的 bug 修了一处漏了一处：
    #   ckf_anchor_hit 用了 anchor_keys，ckf_swap_synchrony 还在用整句
    #   ⇒ 27 个样本整齐地报 0%，而人工核明明看到 62300 出现了 4 次。
    ko, kn = anchor_keys(anchor_old), anchor_keys(anchor_new)
    if not ko or not kn:
        return {"applicable": False, "note": "锚点里抽不出检测键"}
    r = {
        "applicable": True,
        "keys_old": ko, "keys_new": kn,
        "new_in_new": _hit_any(ns, kn),
        "old_in_new": _hit_any(ns, ko),
        "new_in_orig": _hit_any(no, kn),
        "old_in_orig": _hit_any(no, ko),
    }
    # 严格同步：换值版里新值在、旧值不在，且原版里新值不在
    r["synchronized"] = bool(r["new_in_new"] and not r["old_in_new"] and not r["new_in_orig"])
    return r


# ---------------------------------------------------------------- C2 专属：已排除选项的抑制
def excluded_suppression(draft: str, final: str, excluded: list) -> dict:
    """★ C2 独有的可测判据：状态转移是否真的**改变了可选项集合**。

    C2 的 g 步输出「已排除的选项」——"这一轮不能再走���路"。
    这些选项**来自初稿 O₁**，所以：
        hit(O₁, kw_excluded) 应该**高**（初稿确实走过）
        hit(O₂, kw_excluded) 应该**低**（终稿不再走）
    ⇒ suppressed = hit(O₁) − hit(O₂) 应为**正**。

    ★ 这是 C0 结构上**无法表达**的检验：C0 是一次性注入，
      根本没有"已排除"这个概念，也就无从检验"转移是否改变了可选项集合"。
    """
    if not excluded:
        return {"applicable": False}
    # ★ 先剥掉指令性外壳再抽词：否则"不要再出现…"里的"不要/要再/出现"会被当成
    #   内容词（实测抽出 '不要','职','要再'…）⇒ 命中假高、抑制量假低。
    txt = "；".join(str(x) for x in excluded)
    for shell in ("不要再出现", "不要再", "不再", "不要", "别再", "不能", "不得",
                  "避免", "禁止", "这一轮不能再走", "已经走过", "写出", "写清楚"):
        txt = txt.replace(shell, "")
    kw = keywords(txt, topk=8)
    if not kw:
        return {"applicable": False}
    h1 = hit_rate(draft, kw)
    h2 = hit_rate(final, kw)
    return {"applicable": True, "kw": kw,
            "hit_draft": round(h1, 4), "hit_final": round(h2, 4),
            "suppressed": round(h1 - h2, 4),
            "suppressed_ok": bool(h1 > h2)}


# 多段标题 → 归属键。兼容 `【标题】` / `标题：` / `第N段` 三种写法。
_SECTION_MAP = {
    "未落地": "unlanded", "未落地项": "unlanded",
    "取舍约束": "cons", "约束": "cons", "本轮约束": "cons",
    "极性锚": "polarity", "极性": "polarity",
    "事实提示": "facts_hint", "事实": "facts_hint",
    "已排除": "excluded", "排除": "excluded",
    "可核事实": "facts", "事实清单": "facts",
}
_SEC_HEAD2 = re.compile(
    r"^\s*[【\[]?\s*(未落地|未落地项|取舍约束|约束|本轮约束|极性锚|极性|"
    r"事实提示|事实|已排除|排除|可核事实|事实清单)\s*[】\]]?\s*[：:]?\s*")
_SEC_KEY = {
    "未落地": "unlanded", "未落地项": "unlanded",
    "取舍约束": "cons", "约束": "cons", "本轮约束": "cons",
    "极性锚": "polarity", "极性": "polarity",
    "事实提示": "facts_hint", "事实": "facts_hint",
    "已排除": "excluded", "排除": "excluded",
    "可核事实": "facts", "事实清单": "facts",
}


def parse_sections(text: str, expected: list | None = None) -> dict:
    """把多段输出解析成 {段名: [行, ...]}。

    ★ 所有段落都必须能被识别：任一段缺失 ⇒ 显式标记 fallback（**不静默**）。
      v1 教训：`_parse_g` 不认 `【本轮约束】` ⇒ 约束②静默回退成约束①
      ⇒ 状态转移事实性失效，而单看 C1 的绝对值反而"很漂亮"。
    """
    out = {k: [] for k in ("unlanded", "cons", "polarity", "facts_hint", "excluded", "facts")}
    cur = None
    titled = False
    for ln in (text or "").splitlines():
        s_ = ln.strip()
        m = _SEC_HEAD2.match(s_)
        if m:
            cur = _SEC_KEY[m.group(1)]
            titled = True
            s_ = s_[m.end():].strip()
            if not s_:
                continue
        if not s_:
            continue
        s_ = re.sub(r"^\s*(?:[-*·•]|\d+[.、)])\s*", "", s_).strip()
        if not s_:
            continue
        if cur is None:
            # 没识别出段 ⇒ 归到 unlanded（第一段通常是它）
            cur = "unlanded"
        if cur == "unlanded":
            out["unlanded"].append(s_)
        elif cur == "facts":
            if s_ not in ("无", "（无）"):
                out["facts"].append(s_)
        else:
            if s_ not in out[cur]:
                out[cur].append(s_)
    # ★ 无段标题兜底：实测 grok-4.20 会**忽略**"【段名】"格式要求，直接输出多段正文。
    #   ⇒ 若一个标题都没识别出来，按**空行分段**并按 expected 的顺序映射。
    if not titled and expected:
        paras = [pp.strip() for pp in re.split(r"\n\s*\n", text or "") if pp.strip()]
        if len(paras) >= len(expected):
            for key, para in zip(expected, paras):
                out[key] = [l.strip() for l in para.split("\n") if l.strip()]
    out["unlanded"] = "\n".join(out["unlanded"])
    return out




# ---------------------------------------------------------------- 产出健康度
def repetition_ratio(text: str, stance: dict, n: int = 12) -> float:
    """正文有多大比例是**档案原文的复制**（n-gram 命中率）。

    ★ 为什么必须测：C0（档案全文注入）有可能**把档案复述一遍**。
      那样的话，"覆盖率更高"就是**复述的假象**，不是"状态被使用"的证据。
      ⇒ 凡 repetition_ratio 高的样本，其 coverage 读数**不可与其它臂直接比较**。
    """
    A = _KEEP_CJK.sub("", stance_text(stance) or "")
    if len(A) < n:
        return 0.0
    grams = {A[i:i + n] for i in range(len(A) - n + 1)}
    if not grams:
        return 0.0
    t = _KEEP_CJK.sub("", text or "")
    hit = sum(1 for g in grams if g in t)
    return round(hit / len(grams), 4)


def language_drift(text: str, min_cjk: float = 0.3) -> dict:
    """语言漂移：题面是中文题，产出却主要是外文。

    ★ 实测 grok-4.20 在 C0 臂（档案全文注入）下**整篇用英文写** ⇒
      这就是 multi-mind 记录的"体裁漂移"在语言维度上的表现。
    """
    t = re.sub(r"\s+", "", text or "")
    if not t:
        return {"applicable": False}
    cjk = len(_CJK.findall(t))
    ratio = cjk / len(t)
    return {"cjk_ratio": round(ratio, 4), "drift": ratio < min_cjk}


# ---------------------------------------------------------------- D-2 状态转移
def _bigrams(s: str) -> set:
    s = norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else set()


def jaccard(a: str, b: str) -> float:
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def transfer_sensitivity(cons_a: list, cons_b: list) -> dict:
    """置换敏感度：两份约束（来自不同历史）的差异度。

    值越大 ⇒ 状态对历史越敏感 ⇒ 状态转移律真的在起作用。
    值接近 0 ⇒ 约束是固定的模板，跟写出来的东西无关 ⇒ 是末端选择器，不是状态机。
    """
    ja = jaccard("\n".join(cons_a or []), "\n".join(cons_b or []))
    same = [norm(x) for x in (cons_a or [])] == [norm(x) for x in (cons_b or [])]
    return {"jaccard": round(ja, 4), "identical": same,
            "changed": (not same) and ja < 0.98}


# ---------------------------------------------------------------- D-3 约束关键词
def d3_scores(text: str, stance: dict) -> dict:
    """约束关键词命中 − 拒绝关键词命中（干扰项差）。

    ★ 正式形式是 **archive_coverage**（正文对档案的内容覆盖率）：
      长度归一（除以正文 gram 数）、题目归一（差分时减去同题基线），
      比「关键词命中率」鲁棒得多。
    关键词命中率保留为辅助读数。
    """
    cons = stance.get("取舍约束") or []
    if isinstance(cons, str):
        cons = [cons]
    cons_txt = "；".join(str(x) for x in cons)
    kw_cons = keywords(cons_txt, topk=10)
    kw_rej = keywords(str(stance.get("拒绝") or ""), topk=4)
    h_c = hit_rate(text, kw_cons)
    h_r = hit_rate(text, kw_rej)
    return {
        "kw_constraints": kw_cons,
        "kw_reject": kw_rej,
        "hit_constraints": round(h_c, 4),
        "hit_reject": round(h_r, 4),
        "diff": round(h_c - h_r, 4),
        "hit_which_constraints": hit_which(text, kw_cons),
        "coverage": archive_coverage(text, stance),
    }


def archive_coverage(text: str, stance: dict, n: int = 2) -> dict:
    """正文与档案的**双向**覆盖率。

    cov_text    = |正文gram ∩ 档案gram| / |正文gram|   ← 正文有多少来自档案
    cov_archive = |正文gram ∩ 档案gram| / |档案gram|   ← 档案有多少进了正文

    ★ 为什么必须双向：只看 cov_text 时**长度是强混淆**。
      v1 冒烟里 len 与 cov_text 的 Pearson r = −0.82（长正文分母大 ⇒ 覆盖率天然低），
      与 hit_constraints 的 r = −0.99。⇒ 臂间差异可能全是长度效应。
      **cov_archive 对长度不敏感**（分母是档案，固定）⇒ 作为主读数。
    ★ 两个方向一起报，方向冲突时以 cov_archive 为准并如实标注分歧。
    """
    A = gram_set(stance_text(stance), n)
    B = gram_set(text, n)
    if not A or not B:
        return {"cov_text": 0.0, "cov_archive": 0.0}
    inter = len(A & B)
    return {"cov_text": round(inter / len(B), 4), "cov_archive": round(inter / len(A), 4)}


def stance_text(stance: dict) -> str:
    """档案全文（用于覆盖率基线）。"""
    if not stance:
        return ""
    parts = []
    for k, _ in STANCE_FIELDS:
        v = stance.get(k)
        if isinstance(v, list):
            v = "；".join(str(x) for x in v)
        parts.append(str(v or ""))
    return "\n".join(parts)


# ---------------------------------------------------------------- 判据自检
def selftest(verbose: bool = True) -> dict:
    """★ 判别力自检：阳性（该抓到）必须抓到，��性（不该抓）必须放过。

    借 multi-mind v0.8 的做法（阳性 9/9 · 阴性 6/6，含同义改写组）。
    自检不过 ⇒ 该判据作废，**不是**「没测到效应」。
    """
    res = {}

    def say(k, ok, detail=""):
        res[k] = {"pass": bool(ok), "detail": detail}
        if verbose:
            print("  %s %-28s %s" % ("✓" if ok else "✗", k, detail))

    print("=== D-3 判据自检（判别力口径：阳性须显著高于阴性）===")
    stance = {"取舍约束": ["不牺牲医保目录里罕见病药的可及性", "不牺牲谈判代表的职业底线"],
              "拒绝": "拒绝用煽情个案替代结构性的药价机制",
              "立场核心": "医保谈判代表坚持降价不是出于恩义而是出于基金结余结构",
              "来历": "三年前她靠这款药活下来", "语气": "克制", "强度封顶": "她被撤职时",
              "锚定问题": "降价和竞标是同一件事吗"}
    # 阳性：正文改写自档案（用不同措辞）
    pos = "医保谈判代表坚持降价不是出于恩义，而是出于医保基金明年的结余结构。"
    d3 = d3_scores(pos, stance)
    # 阴性：无关正文
    neg = "秋天的风从窗缝里钻进来，她起身去关窗，顺手把桌上的台灯拧暗了一点。"
    d3n = d3_scores(neg, stance)
    # 判别力：覆盖率必须显著高于阴性
    dca = d3["coverage"]["cov_archive"]; nca = d3n["coverage"]["cov_archive"]
    delta = dca - nca
    say("D-3 覆盖率判别力(cov_archive 长度不敏感)", delta >= 0.05 and dca > nca * 1.5,
        "pos=%.4f neg=%.4f Δ=%.4f" % (dca, nca, delta))
    dct = d3["coverage"]["cov_text"]; nct = d3n["coverage"]["cov_text"]
    say("D-3 覆盖率判别力(cov_text)", dct > nct,
        "pos=%.4f neg=%.4f" % (dct, nct))
    # 关键词命中率：判别力（不设绝对门槛，因为创作类文本字面差异天然大）
    say("D-3 关键词判别力", d3["hit_constraints"] > d3n["hit_constraints"],
        "pos=%.2f neg=%.2f" % (d3["hit_constraints"], d3n["hit_constraints"]))
    # 干扰项：正文含约束但不含拒绝项 ⇒ diff 应为正
    say("D-3 干扰项(拒绝项不误命中)", d3n["hit_reject"] <= d3n["hit_constraints"],
        "拒绝命中=%.2f 约束命中=%.2f" % (d3n["hit_reject"], d3n["hit_constraints"]))

    print("=== D-1 判据自检 ===")
    r1 = ckf_swap_synchrony("他在 2048 年签了这份协议。", "他在 2011 年签了这份协议。", "2048 年", "2011 年")
    say("D-1 阳性(换值同步)", r1.get("synchronized") is True, json.dumps(r1, ensure_ascii=False))
    r2 = ckf_swap_synchrony("他在 2048 年签了这份协议。", "他在 2048 年签了这份协议。", "2048 年", "2011 年")
    say("D-1 阴性(未同步)", r2.get("synchronized") is False, json.dumps(r2, ensure_ascii=False))
    r3 = ckf_swap_synchrony("他在 2048 年签了这份协议。", "他在 2011 年签了这份协议。", "2048年", "2011年")
    say("D-1 同义写法(无空格)", r3.get("synchronized") is True, "空格差异不应影响判定")
    # ★ 长锚点（带前后文）：正文只会写数字，不会写整句
    r4 = ckf_swap_synchrony("年治疗费用是 48200 元，她记下了。", "年治疗费用是 62300 元，她记下了。",
                            "这款罕见病药的年治疗费用是 48200 元", "这款罕见病药的年治疗费用是 62300 元")
    say("D-1 长锚点(正文只写数字)", r4.get("synchronized") is True,
        "new_in_new=%s old_in_new=%s" % (r4.get("new_in_new"), r4.get("old_in_new")))

    print("=== D-2 判据自检 ===")
    t1 = transfer_sensitivity(["这一轮要写降价是她自己孩子岗位上的事", "避开结构性的宏观解释", "失守点是把药写成救命的道德符号"],
                               ["这一轮要写她三年前是靠这个药活下来的", "避开宏观结构分析", "失守点是同情替代了判断"])
    say("D-2 阳性(应判为改变)", t1["changed"] is True, json.dumps(t1, ensure_ascii=False))
    t2 = transfer_sensitivity(["约束一", "约束二", "约束三"], ["约束一", "约束二", "约束三"])
    say("D-2 阴性(相同应判未变)", t2["changed"] is False, json.dumps(t2, ensure_ascii=False))

    print("=== C2 已排除选项抑制 判据自检 ===")
    d1 = "她用审计数字压住报价，说出了结余率。孩子递交离职信那晚，她哭了。"
    f1 = "她用审计数字压住报价，说出了结余率。她坐在桌前，没有哭。"
    r1 = excluded_suppression(d1, f1, ["不要再出现孩子递交离职信便撤回降价幅度这一条件"])
    say("抑制判别力(终稿应低于初稿)", r1.get("suppressed_ok") is True,
        "初稿=%.3f 终稿=%.3f Δ=%+.3f" % (r1.get("hit_draft", 0), r1.get("hit_final", 0), r1.get("suppressed", 0)))
    f2 = "她用审计数字压住报价，说出了结余率。孩子递交离职信那晚，她哭了。"
    r2 = excluded_suppression(d1, f2, ["不要再出现孩子递交离职信便撤回降价幅度这一条件"])
    say("未抑制对照(应判为未抑制)", r2.get("suppressed_ok") is False,
        "初稿=%.3f 终稿=%.3f" % (r2.get("hit_draft", 0), r2.get("hit_final", 0)))
    r3 = excluded_suppression(d1, f1, [])
    say("空排除项(不适用)", r3.get("applicable") is False, "")

    allpass = all(v["pass"] for v in res.values())
    print("\n=== 自检总结: %s (%d/%d) ===" % ("全部通过" if allpass else "存在未通过", sum(v["pass"] for v in res.values()), len(res)))
    return {"all_pass": allpass, "cases": res}


if __name__ == "__main__":
    out = selftest()
    sys.exit(0 if out["all_pass"] else 1)
