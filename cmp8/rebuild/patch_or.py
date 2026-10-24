#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cmp8 打包修：OpenRouter 通道修复（2026-10-20 实测驱动）。

改动：
 1. orclient.classify：404→gone（模型下架/无 endpoint）、403→forbidden（ToS/区域）、401→auth
 2. orclient.chat：gone/forbidden 立刻换下一个模型（原来会静默重试 4 次后 return ""）
 3. orclient.chat：全部失败时**抛错并带原因**（原来"0 字符不报错"就是这么来的）
 4. 默认判官改 deepseek/deepseek-chat；fallback 换成实测可用的模型
 5. 默认 embedding 改 qwen/qwen3-embedding-8b；fallback 去掉被 403 的 google
 6. 新增 Embedder：OpenRouter embedding 失败自动退 MiniMax embo-01，并记录实际用的哪个
 7. analyze_cmp6：记录 judge / judge_same_vendor / embed / census
 8. smoke_or：打印失败原因；embedding 有 MiniMax 兜底就不判死
"""
import io
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
OC = os.path.join(ROOT, "creativity_lab", "orclient.py")
AN = os.path.join(ROOT, "analyze_cmp6.py")
SM = os.path.join(ROOT, "smoke_or.py")



def sub_soft(text, old, new, alt=None, tag=""):
    """容错版 sub1：找不到 old 时不报错（视为已打过）。

    场景：同一个 edit 的"中间态"曾经存在过（v10 默认判官是 deepseek，
    v12 改成 grok-4.3）⇒ old(最老态) 与 new 都不在、但中间态在 ⇒ 必须能迁移。
    """
    if new in text:
        return text
    if old in text:
        return text.replace(old, new, 1)
    if alt and alt in text:
        return text.replace(alt, new, 1)
    print("  · %s：旧文本不在（视为已打过），跳过" % tag)
    return text

def sub1(text, old, new, tag):
    if old not in text:
        if new in text:
            print("  · 已打过，跳过: %s" % tag)
            return text
        raise SystemExit("✗ 锚点未命中: %s" % tag)
    if text.count(old) != 1:
        raise SystemExit("✗ 锚点不唯一(%d): %s" % (text.count(old), tag))
    return text.replace(old, new, 1)


# ---------------------------------------------------------------- orclient.py
s = io.open(OC, encoding="utf-8").read()

# 1) classify：把 404 / 403 从 other 里分出来
s = sub1(s, '''def classify(status: int, body: str) -> str:
    b = (body or "").lower()
    if status == 429:
        return "rate_limit"
    if status == 402:
        return "credit"
    if status in (401, 403):
        return "auth"''', '''def classify(status: int, body: str) -> str:
    b = (body or "").lower()
    if status == 429:
        return "rate_limit"
    if status == 402:
        return "credit"
    if status == 404:
        # 模型已下架 / 没有可用 endpoint（实测：grok-3-mini、grok-4-fast、grok-3 全是这个）
        return "gone"
    if status == 403:
        # 供应商 ToS / 区域限制（实测：openai/*、google/gemini-embedding-001、gpt-4o-mini）
        return "forbidden"
    if status == 401:
        return "auth"''', "classify")

# 2) 默认模型：换成实测可用的（默认判官 = grok-4.3，见下方注释）
_ALT_JUDGE = '''PRIMARY = os.environ.get("OR_PRIMARY", "deepseek/deepseek-chat")
FALLBACKS = [m for m in ("x-ai/grok-4.3", "qwen/qwen3.7-plus",
                         "meta-llama/llama-3.3-70b-instruct", "z-ai/glm-4.5")
             if m != PRIMARY]
EMBED_MODEL = os.environ.get("OR_EMBED", "qwen/qwen3-embedding-8b")
EMBED_FALLBACKS = ["qwen/qwen3-embedding-4b", "baai/bge-m3",
                   "sentence-transformers/all-minilm-l6-v2"]'''
s = sub_soft(s, '''PRIMARY = os.environ.get("OR_PRIMARY", "x-ai/grok-3-mini")
FALLBACKS = [m for m in ("x-ai/grok-4-fast", "x-ai/grok-4.1-fast") if m != PRIMARY]
EMBED_MODEL = os.environ.get("OR_EMBED", "openai/text-embedding-3-small")
EMBED_FALLBACKS = ["qwen/qwen3-embedding-8b", "baai/bge-m3", "google/gemini-embedding-001"]''',
'''# ⚠️ 默认值是 2026-10-20 **实测**能出内容、且**自检稳定**的模型。
#   原来的 "x-ai/grok-3-mini" 已下架（404：xAI 建议改用 grok-4.3）；
#   原来的 embedding 默认 "openai/text-embedding-3-small" 被供应商 ToS 拦（403）。
#   默认判官选 grok-4.3 而不是更便宜的 deepseek/deepseek-chat：
#   **演练实测 deepseek 在分析器自检上两次都只有假断言召回 2/5（<0.5）⇒ 会被拒绝出数**；
#   grok-4.3 是 5/5 + 5/5（fn=0, fp=0）。判官调用在 temperature 1.0 ⇒ 自检有采样随机性。
PRIMARY = os.environ.get("OR_PRIMARY", "x-ai/grok-4.3")
FALLBACKS = [m for m in ("deepseek/deepseek-chat", "qwen/qwen3.7-plus",
                         "meta-llama/llama-3.3-70b-instruct", "z-ai/glm-4.5")
             if m != PRIMARY]
EMBED_MODEL = os.environ.get("OR_EMBED", "qwen/qwen3-embedding-8b")
EMBED_FALLBACKS = ["qwen/qwen3-embedding-4b", "baai/bge-m3",
                   "sentence-transformers/all-minilm-l6-v2"]''', alt=_ALT_JUDGE, tag="默认模型")

# 2b) ★ 判官 temperature 1.0 → 0.0（**只动 orclient**；被测侧 client.py 不动）
#     理由：判官在 temp>0 ⇒ 矛盾率不是确定量；而「种子噪声地板」只测了**被测侧**的波动、
#     **没测判官侧**的采样噪声 ⇒ ⑤b vs ⑤c 的差异里有多少是策略信号、多少是判官噪声，
#     **目前分不开**。temp=0 是把这个混淆项直接消掉的省事办法。
#     实测（2026-10-20 18:15 演练）：deepseek 在 temp=1.0 下同一自检两次分别 5/5+2/5 与 3/5+2/5 ⇒ 都不达标。
s = sub1(s, '''    def chat(self, prompt: str, *, model: str = "", temp: float = 1.0,
             max_tokens: int = 2000, budgets=(4000, 6000), min_ok: int = 20,
             purpose: str = "") -> str:''',
         '''    def chat(self, prompt: str, *, model: str = "", temp: float = 0.0,
             max_tokens: int = 2000, budgets=(4000, 6000), min_ok: int = 20,
             purpose: str = "") -> str:''', "判官 temp=0")

# 3) chat：gone/forbidden 换模型；空产出抛错带原因
s = sub1(s, '''        model = model or PRIMARY
        last = ""
        t0 = time.time()''', '''        model = model or PRIMARY
        last = ""
        last_err = ""
        t0 = time.time()''', "chat last_err")

s = sub1(s, '''                    except ApiError as e:
                        self.rec.append(Call(mm, purpose, mt, e.kind, 0, False, time.time() - t0, e.kind))
                        if e.kind in ("credit", "auth"):
                            raise
                        if e.kind == "rate_limit":''', '''                    except ApiError as e:
                        self.rec.append(Call(mm, purpose, mt, e.kind, 0, False, time.time() - t0, e.kind))
                        last_err = "%s(%s): %s" % (e.kind, mm, str(e)[:120])
                        if e.kind in ("credit", "auth"):
                            raise
                        if e.kind in ("gone", "forbidden"):
                            # 模型下架 / 供应商封禁 ⇒ 换下一个模型，别在这里空转
                            break
                        if e.kind == "rate_limit":''', "chat gone/forbidden")

s = sub1(s, '''            if not overload_hits and not rate_hits and ci == 0:
                break
        return last''', '''            if not overload_hits and not rate_hits and ci == 0:
                break
        if not last.strip():
            # ★ 原来这里 return "" —— 调用方拿到空串却没有任何错误信息，
            #   一次 404 就能让整套实验静默产出 0 字符。现在必须炸。
            raise RuntimeError(
                "OpenRouter chat 无输出（%s）。已试模型: %s。最后原因: %s"
                % (model, [model] + [m for m in FALLBACKS if m != model], last_err or "空响应"))
        return last''', "chat 抛错")

# 4) Embedder：OpenRouter 失败自动退 MiniMax embo-01
s = sub1(s, '''    def embed(self, texts: list, typ: str = "db") -> list:
        """OpenRouter embedding。**不认** MiniMax 的 type 参数，所以不传。''',
'''    def embed(self, texts: list, typ: str = "db") -> list:
        """OpenRouter embedding。**不认** MiniMax 的 type 参数，所以不传。''', "embed 锚点")

s += '''

class Embedder:
    """去重用的 embedding 供应器：OpenRouter 优先，失败自动退 MiniMax embo-01。

    为什么要有兜底：2026-10-20 实测，OpenRouter 的 openai/* 与 google/* embedding
    被供应商 ToS 拦（403），而 MiniMax embo-01（1536 维）一直可用。

    ⚠️ **阈值警告**：去重阈值 0.75 是在 **MiniMax embo-01** 上标定的。
    换 embedding 模型会改变余弦相似度的尺度 ⇒ 同一个 0.75 在别的模型上
    含义不同 ⇒ **宽度/去重宽这类指标不可跨 embedding 模型比较**。
    `used` 会记录实际用了哪个，报告里必须一起写出来。
    """

    def __init__(self):
        self.used = None
        self._or = None
        self._mm = None
        self._cache = {}

    def embed(self, texts, typ="db"):
        if self.used is None:
            self.used = self._pick()
        if self.used.startswith("openrouter:"):
            return self._or.embed(texts)
        return self._mm.embed(texts, typ)

    def _pick(self):
        try:
            from creativity_lab.client import LLM as MM
            self._mm = MM()
        except Exception:
            self._mm = None
        try:
            self._or = LLM()
            v = self._or.embed(["探针"])
            if v and v[0]:
                return "openrouter:%s" % EMBED_MODEL
        except Exception as e:
            print("  [embed] OpenRouter 不可用（%s）→ 退 MiniMax embo-01" % str(e)[:80], flush=True)
        if self._mm is None:
            raise RuntimeError("没有可用的 embedding 通道")
        return "minimax:embo-01"
'''

# --- EMBED_PROVIDER：强制走 MiniMax embo-01（0.75 去重阈值的标定基准）---
s = sub1(s, '''    def __init__(self):
        self.used = None
        self._or = None
        self._mm = None
        self._cache = {}''', '''    def __init__(self, provider: str = ""):
        self.used = None
        self._or = None
        self._mm = None
        self._cache = {}
        # EMBED_PROVIDER=minimax 强制走 embo-01（0.75 去重阈值的标定基准）
        self._force = (provider or os.environ.get("EMBED_PROVIDER", "")).strip().lower()''', "Embedder init")
s = sub1(s, '''    def _pick(self):
        try:''', '''    def _pick(self):
        if self._force in ("minimax", "mm", "embo-01"):
            from creativity_lab.client import LLM as MM
            self._mm = MM()
            return "minimax:embo-01"
        try:''', "_pick")

io.open(OC, "w", encoding="utf-8").write(s)
print("✓ orclient.py")

# ---------------------------------------------------------------- analyze_cmp6.py
a = io.open(AN, encoding="utf-8").read()
a = sub1(a, '''    judge = orclient.LLM()
    emb = orclient.LLM()''', '''    judge = orclient.LLM()
    emb = orclient.Embedder()''', "analyze emb")

a = sub1(a, '''    census = dict(judge.model_used)
    json.dump(dict(rows=[{k: v for k, v in r.items() if k != "txt"} for r in rows],
                   summary=summary, judge=orclient.PRIMARY, census=census),
              open("%s/analysis.json" % OUT, "w"), ensure_ascii=False, indent=1, default=str)''',
'''    census = dict(judge.model_used)
    jm = ",".join(sorted(judge.model_used)) or orclient.PRIMARY
    same_vendor = ("minimax" in jm.lower())     # 判官退到 MiniMax = 同源 ⇒ 必须声明
    json.dump(dict(rows=[{k: v for k, v in r.items() if k != "txt"} for r in rows],
                   summary=summary, judge=orclient.PRIMARY, judge_used=jm,
                   judge_same_vendor=same_vendor, embed=emb.used, census=census),
              open("%s/analysis.json" % OUT, "w"), ensure_ascii=False, indent=1, default=str)''', "analyze json")

a = sub1(a, '''    print("交付答案（人工判读用）　判官=%s　embedding=OpenRouter" % orclient.PRIMARY)''',
'''    print("交付答案（人工判读用）　判官=%s（实际 %s）　embedding=%s"
          % (orclient.PRIMARY, jm, emb.used))
    if same_vendor:
        print("⚠️⚠️ 判官与被测**同源**（都在 MiniMax）⇒ 判据有效性下降，结论只能当弱证据")''', "analyze 打印")

# --- 去重体检表：保留率 = width / n_raw（判据：<0.15 退化 / >0.85 阈值太松）---
a = sub1(a, '''    print("\\n" + "=" * 112)
    print("交付答案（人工判读用）''', '''    print("\\n" + "=" * 112)
    print("去重体检（判据：保留率 = width / n_raw）")
    print("%-28s %9s %9s %9s  %s" % ("臂", "n_raw", "去重宽", "保留率", "判读"))
    for s_ in summary:
        pt = s_["per_t"]
        def m(k):
            v = [x[k] for x in pt.values() if x.get(k) is not None]
            return sum(v) / max(len(v), 1)
        nr, w = m("n_raw"), m("width")
        rate = (w / nr) if nr else 0.0
        if nr and rate < 0.15:
            verdict = "⚠️ 去重几乎全合并 ⇒ 宽度轴退化"
        elif nr and rate > 0.85:
            verdict = "⚠️ 去重几乎没起作用 ⇒ 阈值太松"
        else:
            verdict = "去重在工作，宽度轴可用"
        print("%-28s %9.1f %9.1f %8.1f%%  %s" % (s_["name"], nr, w, 100 * rate, verdict))
    print("  （n_raw 不依赖 embedding，是最无争议的广度指标；width 受 embedding 通道影响）")

    print("\\n" + "=" * 112)
    print("交付答案（人工判读用）''', "保留率表")

# --- 判官解析失败率体检（截断/解析异常的可见症状；解析失败不进分母但会悄悄缩小分母）---
a = sub1(a, '''        legal = [c for c in claims if verd.get(c) in ("支持", "矛盾")]''',
         '''        n_parsefail = sum(1 for c in claims if verd.get(c) not in
                           ("支持", "矛盾", "未提及", "非主张"))
        legal = [c for c in claims if verd.get(c) in ("支持", "矛盾")]''', "解析失败计数")
a = sub1(a, '''        return dict(arm=arm, tid=tid, rep=rep, chars=len(txt), n_raw=len(claims),
                    width=len(dd), sup=sup, con=con, unt=unt, nc=nc,''',
         '''        return dict(arm=arm, tid=tid, rep=rep, chars=len(txt), n_raw=len(claims),
                    width=len(dd), sup=sup, con=con, unt=unt, nc=nc,
                    n_parsefail=n_parsefail,
                    parsefail_rate=(n_parsefail / max(len(claims), 1)),''', "row 字段")
a = sub1(a, '''                unt=float(np.mean([r["unt"] for r in sub])),
                nc=float(np.mean([r["nc"] for r in sub])),''',
         '''                unt=float(np.mean([r["unt"] for r in sub])),
                nc=float(np.mean([r["nc"] for r in sub])),
                parsefail_rate=float(np.mean([r.get("parsefail_rate", 0.0) for r in sub])),
                n_parsefail=int(sum(r.get("n_parsefail", 0) for r in sub)),''', "per_t 汇总")
a = sub1(a, '''    print("  （n_raw 不依赖 embedding，是最无争议的广度指标；width 受 embedding 通道影响）")''',
         '''    print("  （n_raw 不依赖 embedding，是最无争议的广度指标；width 受 embedding 通道影响）")
    print("  判官解析失败率（截断/解析异常的可见症状；解析失败不进分母，但会悄悄缩小分母）")
    for s_ in summary:
        pt = s_["per_t"]
        def _mp(k):
            v = [x[k] for x in pt.values() if x.get(k) is not None]
            return sum(v) / max(len(v), 1)
        pf = _mp("parsefail_rate")
        npf = sum(x.get("n_parsefail", 0) for x in pt.values())
        flag = "⚠ 解析失败率偏高 ⇒ 该臂矛盾率的分母被悄悄缩小，结论要打折" if pf > 0.10 else ""
        print("    %-28s 解析失败 %5.1f%%（%d 条） %s" % (s_["name"], 100 * pf, npf, flag))''', "解析失败率表")
a = sub1(a, '''                   judge_same_vendor=same_vendor, embed=emb.used, census=census),''',
         '''                   judge_same_vendor=same_vendor, embed=emb.used, census=census,
                   parsefail_rate={s_["arm"]: {t: pt[t].get("parsefail_rate", 0.0)
                                               for t in pt} for s_ in summary for pt in [s_["per_t"]]}),''', "json 记解析失败率")

# --- 产出有效性闸门（<50 字 = 产出无效，不入统计）+ 样本分母 + 排除清单 ---
a = sub1(a, '''        txt = arm_file(arm, tid, rep)
        if not txt.strip():
            return dict(arm=arm, tid=tid, rep=rep, chars=0, n_raw=0, width=0,
                        sup=0, con=0, unt=0, nc=0, conflict=0.0, support=0.0,
                        claims=[], verd={}, empty=True)''',
         '''        txt = arm_file(arm, tid, rep)
        if len(txt.strip()) < 50:
            # ★ 产出有效性闸门（项目既有纪律：< 50 字 = 产出无效 ⇒ 记 error，不入统计）。
            #   为什么必须卡长度而不只是"非空"：一个 30 字的空壳若以 conflict=0 进入均值，
            #   会把该臂的矛盾率**稀释得更好看** ⇒ 静默偏向该臂。
            #   判据与 A5 臂 synth 文件的 >40 字节门槛一致。
            return dict(arm=arm, tid=tid, rep=rep, chars=len(txt.strip()), n_raw=0, width=0,
                        sup=0, con=0, unt=0, nc=0, conflict=0.0, support=0.0,
                        n_parsefail=0, parsefail_rate=0.0,
                        claims=[], verd={}, empty=True, invalid="short_or_empty_output")''', "有效性闸门")
a = sub1(a, '''        summary.append(dict(arm=a, name=ARM_NAME.get(a, a), per_t=per_t))''',
         '''        n_valid = sum(1 for r in rr if not r.get("empty"))
        n_total = len(rr)
        excluded = [(r["tid"], r["rep"], r.get("chars", 0), r.get("invalid", "empty"))
                    for r in rr if r.get("empty")]
        summary.append(dict(arm=a, name=ARM_NAME.get(a, a), per_t=per_t,
                            n_valid=n_valid, n_total=n_total, excluded=excluded))''', "summary 样本数")
a = sub1(a, '''    print("%-28s %7s %7s %7s %9s %9s %8s" %
          ("臂", "字符", "断言数", "去重宽", "矛盾率", "支持率", "离散度"))''',
         '''    print("%-28s %7s %7s %7s %9s %9s %8s %8s" %
          ("臂", "字符", "断言数", "去重宽", "矛盾率", "支持率", "离散度", "样本"))''', "表头加样本列")
a = sub1(a, '''        print("%-28s %7.0f %7.1f %7.1f %8.1f%% %8.1f%% %8.3f"''',
         '''        print("%-28s %7.0f %7.1f %7.1f %8.1f%% %8.1f%% %8.3f %8s"''', "行加样本列")
a = sub1(a, '''              % (s["name"], m("chars"), m("n_raw"), m("width"), 100 * m("conflict"),
                 100 * m("support"), sum(disp) / max(len(disp), 1) if disp else 0))''',
         '''              % (s["name"], m("chars"), m("n_raw"), m("width"), 100 * m("conflict"),
                 100 * m("support"), sum(disp) / max(len(disp), 1) if disp else 0,
                 "%d/%d" % (s.get("n_valid", 0), s.get("n_total", 0))))''', "行样本数")
a = sub1(a, '''    print("  判官解析失败率（截断/解析异常的可见症状；解析失败不进分母，但会悄悄缩小分母）")''',
         '''    print("  产出有效性闸门（<50 字 = 产出无效 ⇒ 不入统计；**必须报出丢了哪些样本**）")
    any_ex = False
    for s_ in summary:
        ex = s_.get("excluded") or []
        if ex:
            any_ex = True
            print("    %-28s 有效 %d/%d，被排除: %s"
                  % (s_["name"], s_.get("n_valid", 0), s_.get("n_total", 0),
                     ", ".join("%s/r%d(%d字,%s)" % e for e in ex)))
    if not any_ex:
        print("    （无样本被排除）")
    print("  判官解析失败率（截断/解析异常的可见症状；解析失败不进分母，但会悄悄缩小分母）")''', "排除清单")
a = sub1(a, '''                   parsefail_rate={s_["arm"]: {t: pt[t].get("parsefail_rate", 0.0)
                                               for t in pt} for s_ in summary for pt in [s_["per_t"]]}),''',
         '''                   parsefail_rate={s_["arm"]: {t: pt[t].get("parsefail_rate", 0.0)
                                               for t in pt} for s_ in summary for pt in [s_["per_t"]]},
                   samples={s_["arm"]: dict(valid=s_.get("n_valid", 0), total=s_.get("n_total", 0),
                                            excluded=s_.get("excluded", [])) for s_ in summary}),''', "json 样本数")


# ---------------------------------------------------------------- 判官结果缓存（遍2 复用）
JUDGE_CACHE_SRC = '''# -*- coding: utf-8 -*-
"""判官结果缓存（跨"遍1 / 遍2"复用）。

**为什么需要**：遍2 的唯一变量是 **embedding 通道**（`EMBED_PROVIDER=minimax`）
⇒ 判官 verdict 应当**原样复用**，只重算 embedding / 去重 / 宽度。
否则判官成本要付两遍（grok-4.3 是 deepseek 的 4–5 倍）⇒ 会破 $1 成本上限。

**为什么复用是同一个量（不是改口径）**：判官模型、提示词、断言抽取三者在两遍里完全一致；
断言抽取 `extract_claims` **只吃原文、不吃 embedding** ⇒ 两遍的断言集合必须一致。

**键的设计**：
- 样本级键 `臂|题|重复` + 原文 sha1 ⇒ 原文变了自动失效
- verdict 以**断言文本**为键（不是序号）⇒ 对顺序变化也稳

**⚠️ 报告里必须写明**：遍2 复用了遍1 的判官结果（`analysis.json` 的 `judge_reused`）。
否则读报告的人会以为两遍各自独立判了一遍。
"""
from __future__ import annotations

import hashlib
import json
import os
import threading

LOCK = threading.Lock()
_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(os.path.dirname(_HERE), "runs", "judge_cache.json")


def path() -> str:
    return os.environ.get("JUDGE_CACHE") or DEFAULT_PATH


def _h(txt: str) -> str:
    return hashlib.sha1((txt or "").encode("utf-8")).hexdigest()[:16]


def key(arm: str, tid: str, rep: int) -> str:
    return "%s|%s|%s" % (arm, tid, rep)


def load() -> dict:
    p = path()
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save(cache: dict) -> None:
    p = path()
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, p)


def get(cache: dict, arm: str, tid: str, rep: int, txt: str):
    e = cache.get(key(arm, tid, rep))
    if not e or e.get("h") != _h(txt):
        return None
    return e


def put(cache: dict, arm: str, tid: str, rep: int, txt: str, claims: list, verd: dict) -> None:
    cache[key(arm, tid, rep)] = {
        "h": _h(txt),
        "claims": list(claims),
        "verd": {c: verd.get(c) for c in claims},
    }
'''
_JC_PATH = os.path.join(ROOT, "creativity_lab", "judge_cache.py")
if not os.path.exists(_JC_PATH) or "judge_reused" not in io.open(_JC_PATH, encoding="utf-8").read():
    io.open(_JC_PATH, "w", encoding="utf-8").write(JUDGE_CACHE_SRC)
    print("✓ creativity_lab/judge_cache.py（判官结果缓存）")

a = sub1(a, '''from creativity_lab.verify import check_claims, extract_claims   # noqa: E402
from creativity_lab import orclient                              # noqa: E402''',
'''from creativity_lab.verify import check_claims, extract_claims   # noqa: E402
from creativity_lab import orclient                              # noqa: E402
from creativity_lab import judge_cache                           # noqa: E402''', "analyze import 缓存")

# 输出目录必须先建：遍2 的 CMP_OUT（runs/cmp8_mmemb）默认不存在 ⇒
# 写 judge_selfcheck.json 时 FileNotFoundError ⇒ 整遍白跑（2026-10-20 18:50 演练抓到）
# ★ 答案目录与输出目录分离：遍2 只换 embedding 通道，**答案仍在遍1 的目录**。
#   之前遍2 把 CMP_OUT 指向新目录 ⇒ 分析器在新目录里找不到任何答案 ⇒
#   遍2 全空、"两遍对比"变成假的（演练 2026-10-20 18:55 抓到）。
a = sub1(a, '''OUT = os.environ.get("CMP_OUT", "runs/cmp8")''',
         '''OUT = os.environ.get("CMP_OUT", "runs/cmp8")
# 答案从 ANS_DIR 读（默认 = OUT）；遍2 用 ANS_DIR=<遍1 目录>，输出仍写到 OUT
ANS_DIR = os.environ.get("ANS_DIR", OUT)''', "analyze ANS_DIR")

# arm_file 改读 ANS_DIR（答案目录），输出目录仍用 OUT
a = sub1(a, '''def arm_file(arm, tid, rep):
    """A5 系列的交付答案 = 合成版（与其它臂同为流式答复）；机械装配版另存。"""
    if arm.startswith("A5"):
        s = "%s/%s_r%d_%s_synth.md" % (OUT, tid, rep, arm)
        if os.path.exists(s) and os.path.getsize(s) > 40:
            return open(s, encoding="utf-8").read()
    p = "%s/%s_r%d_%s.md" % (OUT, tid, rep, arm)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""''',
'''def arm_file(arm, tid, rep):
    """A5 系列的交付答案 = 合成版（与其它臂同为流式答复）；机械装配版另存。"""
    if arm.startswith("A5"):
        s = "%s/%s_r%d_%s_synth.md" % (ANS_DIR, tid, rep, arm)
        if os.path.exists(s) and os.path.getsize(s) > 40:
            return open(s, encoding="utf-8").read()
    p = "%s/%s_r%d_%s.md" % (ANS_DIR, tid, rep, arm)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""''',
        "arm_file 读 ANS_DIR")

# A5 的 claims .json 路径也改 ANS_DIR
a = sub1(a, '''        j = "%s/%s_r%d_%s.json" % (OUT, tid, rep, arm)''',
         '''        j = "%s/%s_r%d_%s.json" % (ANS_DIR, tid, rep, arm)''', "A5 claims 读 ANS_DIR")

a = sub1(a, '''def main():
    judge = orclient.LLM()''',
'''def main():
    os.makedirs(OUT, exist_ok=True)
    judge = orclient.LLM()''', "analyze 建 OUT 目录")

a = sub1(a, '''    judge = orclient.LLM()
    emb = orclient.Embedder()''',
'''    judge = orclient.LLM()
    emb = orclient.Embedder()
    CACHE = judge_cache.load()
    _cstat = {"hit": 0, "miss": 0}''', "analyze 缓存初始化")

# analysis.json 记 judge_reused（**成本闸门**：遍2 复用 ⇒ 判官不重复付费）
a = sub1(a, '''                   samples={s_["arm"]: dict(valid=s_.get("n_valid", 0), total=s_.get("n_total", 0),
                                            excluded=s_.get("excluded", [])) for s_ in summary}),''',
         '''                   samples={s_["arm"]: dict(valid=s_.get("n_valid", 0), total=s_.get("n_total", 0),
                                            excluded=s_.get("excluded", [])) for s_ in summary},
                   judge_reused=(_cstat["hit"] > 0),
                   judge_cache=dict(hit=_cstat["hit"], miss=_cstat["miss"], path=judge_cache.path())),''',
         "analyze json 加 judge_reused")

a = sub1(a, '''        if claims is None:
            claims = extract_claims(judge, txt)
        verd = check_claims(judge, QS[tid], EV.get(tid, ""), claims) if claims else {}''',
'''        # ★ 判官结果缓存：遍2 的唯一变量是 embedding 通道 ⇒ verdict 应当原样复用
        #   （否则判官成本付两遍 ⇒ 破 $1 上限）。键含原文 sha1 ⇒ 原文变了自动失效。
        with judge_cache.LOCK:
            _e = judge_cache.get(CACHE, arm, tid, rep, txt)
            if _e is not None:
                claims = _e["claims"]
                verd = {c: _e["verd"].get(c) for c in claims}
                _cstat["hit"] += 1
            else:
                if claims is None:
                    claims = extract_claims(judge, txt)
                verd = check_claims(judge, QS[tid], EV.get(tid, ""), claims) if claims else {}
                judge_cache.put(CACHE, arm, tid, rep, txt, claims, verd)
                _cstat["miss"] += 1''', "analyze 用缓存")


a = sub1(a, '''    print("\\n" + "=" * 112)
    print("去重体检（判据：保留率 = width / n_raw）")''',
'''    try:
        judge_cache.save(CACHE)
        print("  判官缓存已写：%s（命中 %d / 未命中 %d）" % (judge_cache.path(), _cstat["hit"], _cstat["miss"]))
    except Exception as e:
        print("  [判官缓存写盘失败] %s" % str(e)[:80])

    print("\\n" + "=" * 112)
    print("去重体检（判据：保留率 = width / n_raw）")''', "analyze 写缓存")

io.open(AN, "w", encoding="utf-8").write(a)
print("✓ analyze_cmp6.py")

# ---------------------------------------------------------------- smoke_or.py
m = io.open(SM, encoding="utf-8").read()
m = sub1(m, '''    o = orclient.LLM()
    r = o.chat("用一句话说明什么是复利", purpose="smoke", max_tokens=300,
               budgets=(600,), min_ok=8)
    print("  → %d 字符，用时 %.1fs：%s" % (len(r), time.time() - t0, (r or "")[:80]), flush=True)
    if len(r) < 8:
        fails.append("OpenRouter chat 无输出")''',
'''    o = orclient.LLM()
    try:
        r = o.chat("用一句话说明什么是复利", purpose="smoke", max_tokens=300,
                   budgets=(600,), min_ok=8)
    except Exception as e:
        r = ""
        print("  ✗ 失败:", str(e)[:300], flush=True)
        fails.append("OpenRouter chat 无输出: %s" % str(e)[:80])
    print("  → %d 字符，用时 %.1fs：%s" % (len(r), time.time() - t0, (r or "")[:80]), flush=True)''', "smoke chat")

m = sub1(m, '''    print("=== ② OpenRouter embedding ===", flush=True)
    try:
        vs = o.embed(["湖北620分选AI专业", "620分的湖北考生该选哪所大学"])
        dim = len(vs[0]) if vs and vs[0] else 0
        print("  → %d 条 × %d 维" % (len(vs), dim), flush=True)
        if dim == 0:
            fails.append("OpenRouter embedding 无输出")
    except Exception as e:
        print("  ✗ 失败:", str(e)[:100], flush=True)
        fails.append("OpenRouter embedding 失败: %s" % str(e)[:60])''',
'''    print("=== ② embedding（OpenRouter 优先，失败退 MiniMax embo-01）===", flush=True)
    emb = orclient.Embedder()
    try:
        vs = emb.embed(["湖北620分选AI专业", "620分的湖北考生该选哪所大学"])
        dim = len(vs[0]) if vs and vs[0] else 0
        print("  → %d 条 × %d 维（实际通道: %s）" % (len(vs), dim, emb.used), flush=True)
        if dim == 0:
            fails.append("embedding 无输出")
    except Exception as e:
        print("  ✗ 失败:", str(e)[:140], flush=True)
        fails.append("embedding 失败: %s" % str(e)[:60])''', "smoke embed")

m = sub1(m, '''    print("=== ③ 判官自检（grok）===", flush=True)''',
'''    print("=== ③ 判官自检（%s）===" % orclient.PRIMARY, flush=True)''', "smoke 自检标题")

m = sub1(m, '''    print("  真断言 %d/%d ｜ 假断言 %d/%d" % (tp, tp + fn, tn, tn + fp), flush=True)''',
'''    print("  真断言 %d/%d ｜ 假断言 %d/%d" % (tp, tp + fn, tn, tn + fp), flush=True)
    print("  判官实际用了: %s" % (o.model_used or orclient.PRIMARY), flush=True)''', "smoke 判官模型")

io.open(SM, "w", encoding="utf-8").write(m)
print("✓ smoke_or.py")

# ---------------------------------------------------------------- topics4.py：单一真相源
import re as _re
_RC = os.path.join(ROOT, "run_compare5.py")
if os.path.exists(_RC):
    _src = io.open(_RC, encoding="utf-8").read()
    _m = _re.search(r"^TOPICS4 = \[.*?^\]\n", _src, _re.S | _re.M)
    if _m:
        _block = _m.group(0)
        _hdr = ('''# -*- coding: utf-8 -*-
"""四道题的题面定义（单一真相源）。

`run_compare5.py` 优先从这里读题；读不到时回退到它自己内联的副本
（内联副本与本文件内容一致，只是多一份保险）。

用法：
    python3 topics4.py     # 打印 4 道题
"""
from __future__ import annotations

''')
        _ftr = '''
if __name__ == "__main__":
    for t in TOPICS4:
        print("%s  %s" % (t["tid"], t["title"]))
        print("    " + t["q"])
'''
        _tp = os.path.join(ROOT, "armdeps", "topics4.py")
        if not os.path.exists(_tp) or "单一真相源" not in io.open(_tp, encoding="utf-8").read():
            os.makedirs(os.path.dirname(_tp), exist_ok=True)
            io.open(_tp, "w", encoding="utf-8").write(_hdr + _block + _ftr)
            print("✓ armdeps/topics4.py（单一真相源）")
        # 让 run_compare5 优先读 topics4
        if "from topics4 import TOPICS4" not in _src:
            _anchor = _block.rstrip("\n")
            _add = _anchor + '''

# 单一真相源：优先读 armdeps/topics4.py；读不到就用上面这份内联副本（内容一致）
try:
    from topics4 import TOPICS4  # noqa: F401,E402
except Exception:  # pragma: no cover
    pass
'''
            if _anchor in _src:
                io.open(_RC, "w", encoding="utf-8").write(_src.replace(_anchor, _add, 1))
                print("✓ run_compare5.py：topics4 单一真相源 + 内联兜底")
    else:
        print("  · run_compare5.py 里没找到 TOPICS4，跳过 topics4 补丁")


# ---------------------------------------------------------------- learnarch.py：补 import time
_LA = os.path.join(ROOT, "creativity_lab", "learnarch.py")
if os.path.exists(_LA):
    _t = io.open(_LA, encoding="utf-8").read()
    if "time.sleep" in _t and "\nimport time\n" not in _t:
        _t2 = _t.replace("import os\nimport re\nimport random\nimport sys\n",
                         "import os\nimport re\nimport random\nimport sys\nimport time\n", 1)
        if _t2 == _t:      # 兜底：插到第一处 import 之后
            _t2 = _t.replace("import os\n", "import os\nimport time\n", 1)
        io.open(_LA, "w", encoding="utf-8").write(_t2)
        print("✓ creativity_lab/learnarch.py：补 import time（embed 失败退避路径）")
    else:
        print("  · learnarch.py 的 import time 已在（或无需）")


# ---------------------------------------------------------------- go_cmp8.sh：默认判官/embedding 换新
_SH = os.path.join(ROOT, "go_cmp8.sh")
if os.path.exists(_SH):
    _g = io.open(_SH, encoding="utf-8").read()
    _g2 = _g.replace('export OR_PRIMARY="${OR_PRIMARY:-x-ai/grok-3-mini}"',
                     'export OR_PRIMARY="${OR_PRIMARY:-deepseek/deepseek-chat}"')
    if "OR_EMBED" not in _g2:
        _g2 = _g2.replace("export CMP_OUT=", 'export OR_EMBED="${OR_EMBED:-qwen/qwen3-embedding-8b}"\nexport CMP_OUT=', 1)
    if _g2 != _g:
        io.open(_SH, "w", encoding="utf-8").write(_g2)
        print("✓ go_cmp8.sh：默认判官/embedding 换成实测可用的")
    else:
        print("  · go_cmp8.sh 已是新版")

print("全部补丁应用完毕")
