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

# 2) 默认模型：换成实测可用的
s = sub1(s, '''PRIMARY = os.environ.get("OR_PRIMARY", "x-ai/grok-3-mini")
FALLBACKS = [m for m in ("x-ai/grok-4-fast", "x-ai/grok-4.1-fast") if m != PRIMARY]
EMBED_MODEL = os.environ.get("OR_EMBED", "openai/text-embedding-3-small")
EMBED_FALLBACKS = ["qwen/qwen3-embedding-8b", "baai/bge-m3", "google/gemini-embedding-001"]''',
'''# ⚠️ 默认值是 2026-10-20 **实测**能出内容的模型。
#   原来的 "x-ai/grok-3-mini" 已下架（404：xAI 建议改用 grok-4.3）；
#   原来的 embedding 默认 "openai/text-embedding-3-small" 被供应商 ToS 拦（403）。
PRIMARY = os.environ.get("OR_PRIMARY", "deepseek/deepseek-chat")
FALLBACKS = [m for m in ("x-ai/grok-4.3", "qwen/qwen3.7-plus",
                         "meta-llama/llama-3.3-70b-instruct", "z-ai/glm-4.5")
             if m != PRIMARY]
EMBED_MODEL = os.environ.get("OR_EMBED", "qwen/qwen3-embedding-8b")
EMBED_FALLBACKS = ["qwen/qwen3-embedding-4b", "baai/bge-m3",
                   "sentence-transformers/all-minilm-l6-v2"]''', "默认模型")

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
