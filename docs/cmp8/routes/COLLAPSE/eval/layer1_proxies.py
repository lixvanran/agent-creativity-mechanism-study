# -*- coding: utf-8 -*-
"""层1 代理量 · 零成本三件套（P1a / P1b / P3a + P4 下界）。

> 2026-10-22 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/layer1_proxies.py`
> 假说与判决式：`routes/LAYER1-ATTENTION-ANALYSIS.md` §1（H1 / H3 / H4）
> 纪律：**只用文本层代理**（API 后拿不到 attention / logprobs）⇒ 每个代理都写明它在测什么、
>       以及**它不能证明什么**。

## 三个代理

| 代理 | 对应假说 | 定义 | 判决式（见层1 §2）|
|---|---|---|---|
| **P1a 后段新信息率** | H1 前缀自洽 | 答案后 70% 的断言里，"**全文首次出现**"的比例 | 臂内单调降 **且** 臂间与步数负相关 ⇒ H1 成立 |
| **P1b 前缀复述率** | H1 | 答案后 30% 的**实词 2-gram** 落在前 70% 的比例 | 与 P1a 同向 ⇒ 局部自洽确实在累积 |
| **P3a 视角间 Jaccard** | H3 头间冗余 | 多个视角/槽位产出的**断言集合**两两 Jaccard | 去权威化臂显著低于基线 ⇒ 多样性来自结构 |
| **P4lb 早期逐字复现率**（P4a 的**下界**）| H4 早期锁定 | 答案前 1/3 出现的断言，在后 2/3 里**逐字**再次出现的比例 | 与答案长度/早期结论数正相关 ⇒ 早期锁定 |

### ⚠️ 四条纪律（踩过的坑）

1. **语言闸门**：任何基于字符 n-gram 的代理，跑之前先过语言闸门。
   ⚠️ **口径修正（2026-10-22 实测）**：原口径是"中文占比 ≥ 90%"（中英 n-gram 集完全不相交），
   但**中文答案里含 `MB/s`、`IOPS`、`EV-03` 这类术语** ⇒ 整体占比只有 0.53–0.71
   ⇒ **该口径会把 3/9 份中文答案误判成"漂移"**。
   ⇒ 改用**两道**闸门：
   ① 整体 `CJK 字母 / 全部字母 ≥ 0.5`（区分"中文答案"与"英文答案"）；
   ② **段间稳定性** `|head 占比 − tail 占比| ≤ 0.25`（区分"答案内部漂移"）。
   ⇒ ★ 只要**被比较的两臂**语言配比可比即可（报告里必须给配比）。
2. **比率必须配绝对分母**（协议 §3.1）：每个代理都同时报分子/分母。
3. **P4lb 是下界**：它只抓**逐字**复现 ⇒ 真实的"结论保持"更高（换措辞就不算）。
   ⇒ 读数**只能**用于**同条件比较**（同题、同臂型），**不能**当绝对值。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import vd_anchor_out as V  # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff]")
#: 实词 2-gram：先去掉标点与空白，再取相邻二字
PUNCT = re.compile(r"[\s，。、；：？！（）()\[\]{}「」『』《》〈〉—…·\"'`~@#$%^&*+=|\\/]+")


def cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk = len(CJK.findall(text))
    letters = sum(1 for ch in text if ch.isalpha())
    return cjk / max(letters, 1)


def language_gate(answer: str) -> Dict[str, Any]:
    """语言闸门（两道）：整体中文占比 + 段间稳定性。"""
    sents = split_sentences(answer)
    n = len(sents)
    overall = round(cjk_ratio(answer), 4)
    head_r = tail_r = None
    if n >= 4:
        cut = int(n * 0.7)
        head_r = round(cjk_ratio(" ".join(sents[:cut])), 4)
        tail_r = round(cjk_ratio(" ".join(sents[cut:])), 4)
    seg_gap = (abs(head_r - tail_r)
               if head_r is not None and tail_r is not None else None)
    ok_overall = overall >= 0.5
    ok_seg = (seg_gap is None) or (seg_gap <= 0.25)
    return {"cjk_overall": overall, "cjk_head": head_r, "cjk_tail": tail_r,
            "segment_gap": seg_gap,
            "gate_overall_pass": ok_overall, "gate_segment_pass": ok_seg,
            "pass": bool(ok_overall and ok_seg),
            "note": "两臂比较时**必须**同时看配比；配比不同 ⇒ n-gram 代理不可跨臂比"}


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[。！？；\n])", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def bigrams(text: str) -> set:
    t = PUNCT.sub("", text or "")
    if len(t) < 2:
        return set()
    return {t[i:i + 2] for i in range(len(t) - 1)}


# ──────────────────────────────────────────────────────────────
def p1_late_new_info(answer: str, late_frac: float = 0.7) -> Dict[str, Any]:
    """P1a 后段新信息率：后 `late_frac` 的断言里，"全文首次出现"的比例。"""
    sents = split_sentences(answer)
    n = len(sents)
    if n < 4:
        return {"n_sentences": n, "value": None, "note": "句子太少 ⇒ 不算（不许当 0）"}
    cut = int(n * (1 - late_frac))
    head, late = sents[:cut], sents[cut:]
    seen = set()
    first_pos: List[int] = []
    for i, s in enumerate(sents):
        key = s.strip()
        if key not in seen:
            seen.add(key)
            first_pos.append(i)
    new_late = sum(1 for p in first_pos if p >= cut)
    return {
        "n_sentences": n, "cut_index": cut,
        "n_head": len(head), "n_late": len(late),
        "n_new_in_late": new_late,
        "value": round(new_late / max(len(late), 1), 4),
        "note": "分母 = 后段句子数；分子 = 全文首次出现的句子数落在后段",
    }


def p1_prefix_echo(answer: str, tail_frac: float = 0.3) -> Dict[str, Any]:
    """P1b 前缀复述率：后 `tail_frac` 的实词 2-gram 落在前面的比例。"""
    sents = split_sentences(answer)
    n = len(sents)
    if n < 4:
        return {"n_sentences": n, "value": None, "note": "句子太少 ⇒ 不算"}
    cut = int(n * (1 - tail_frac))
    head_g = bigrams(" ".join(sents[:cut]))
    tail_g = bigrams(" ".join(sents[cut:]))
    if not tail_g:
        return {"n_sentences": n, "value": None, "note": "后段无实词 2-gram"}
    hit = len(tail_g & head_g)
    return {"n_sentences": n, "cut_index": cut,
            "n_tail_bigrams": len(tail_g), "n_hit": hit,
            "value": round(hit / len(tail_g), 4)}


EVREF = re.compile(r"\[(EV[-\s]?\d+)\]")


def p3b_view_evidence_jaccard(drafts: Sequence[str]) -> Dict[str, Any]:
    """P3b 视角间**依据引用集合**的 Jaccard（结构性、离散、零成本）。

    ★ 为什么要有它：措辞级 P3a 在实测里**恒为 0**（语义重合但措辞不同就记 0）
      ⇒ 措辞级指标**不可作判据**（地板 0）⇒ 必须换成**结构化绑定**：
      这里用"这个视角引用了哪些依据条目"⇒ 离散、可复算、不依赖措辞。
    """
    sets = []
    for d in drafts:
        ids = {m.replace(" ", "").upper() for m in EVREF.findall(d or "")}
        sets.append(ids)
    pairs = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            u = sets[i] | sets[j]
            pairs.append((len(sets[i] & sets[j]) / max(len(u), 1), i, j))
    if not pairs:
        return {"n_views": len(sets), "value": None, "note": "少于 2 个视角 或 没有 [EV-xx] 标记"}
    vals = sorted(p[0] for p in pairs)
    return {"n_views": len(sets), "n_pairs": len(pairs),
            "median_jaccard": round(vals[len(vals) // 2], 4),
            "min_jaccard": round(vals[0], 4), "max_jaccard": round(vals[-1], 4),
            "per_view_ev": [sorted(s) for s in sets],
            "per_pair": [{"i": i, "j": j, "jaccard": round(v, 4)} for v, i, j in pairs]}


def p3_view_jaccard(views: Sequence[Sequence[str]]) -> Dict[str, Any]:
    """P3a 视角/槽位间 Jaccard（**措辞级** ⇒ 只当下界，不可作判据）。"""
    sets = [set(v) for v in views]
    pairs: List[Tuple[float, int, int]] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            u = sets[i] | sets[j]
            pairs.append((len(sets[i] & sets[j]) / max(len(u), 1), i, j))
    if not pairs:
        return {"n_views": len(sets), "value": None, "note": "少于 2 个视角 ⇒ 不算"}
    vals = sorted(p[0] for p in pairs)
    med = vals[len(vals) // 2]
    return {"n_views": len(sets), "n_pairs": len(pairs),
            "median_jaccard": round(med, 4),
            "min_jaccard": round(vals[0], 4), "max_jaccard": round(vals[-1], 4),
            "mean_jaccard": round(sum(vals) / len(vals), 4),
            "per_pair": [{"i": i, "j": j, "jaccard": round(v, 4)} for v, i, j in pairs]}


def p4_lb_early_recurrence(answer: str, head_frac: float = 0.333) -> Dict[str, Any]:
    """P4lb 早期逐字复现率（P4a 的**下界**）。"""
    sents = split_sentences(answer)
    n = len(sents)
    if n < 4:
        return {"n_sentences": n, "value": None, "note": "句子太少 ⇒ 不算"}
    cut = max(1, int(n * head_frac))
    head, late = sents[:cut], sents[cut:]
    late_set = set(late)
    rep = sum(1 for s in head if s in late_set)
    return {"n_sentences": n, "cut_index": cut,
            "n_head": len(head), "n_repeated_verbatim": rep,
            "value": round(rep / max(len(head), 1), 4),
            "note": "只抓**逐字**复现 ⇒ 这是「结论保持率」的**下界**，不是它本身"}


def analyze_answer(path: str, extra_views: Optional[List[List[str]]] = None) -> Dict[str, Any]:
    txt = open(path, encoding="utf-8").read()
    out: Dict[str, Any] = {"path": path, "n_chars": len(txt),
                            "cjk_ratio": round(cjk_ratio(txt), 4)}
    out["P1a_late_new_info"] = p1_late_new_info(txt)
    out["P1b_prefix_echo"] = p1_prefix_echo(txt)
    out["P4lb_early_verbatim_recurrence"] = p4_lb_early_recurrence(txt)
    out["language_gate"] = language_gate(txt)
    if extra_views:
        out["P3a_view_jaccard_lexical"] = p3_view_jaccard(extra_views)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", nargs="+", required=True,
                    help="形如 ARM:/path/answer.md（ARM 形如 B0_direct#D01）")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    rows: List[Dict[str, Any]] = []
    for a in args.answers:
        arm, _, path = a.partition(":")
        extra = None
        meta_path = os.path.join(os.path.dirname(path), "%s.meta.json"
                                 % os.path.basename(path).split(".")[0])
        if os.path.exists(meta_path):
            meta = json.load(open(meta_path, encoding="utf-8"))
            drafts = meta.get("drafts") or []
            if drafts:
                extra = [split_sentences(d) for d in drafts]
        r = analyze_answer(path, extra)
        r["arm"] = arm
        r["n_views"] = len(extra or [])
        meta = None
        if os.path.exists(meta_path):
            meta = json.load(open(meta_path, encoding="utf-8"))
        if meta and meta.get("drafts"):
            r["P3b_view_evidence_jaccard"] = p3b_view_evidence_jaccard(meta["drafts"])
        rows.append(r)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"rows": rows}, f, ensure_ascii=False, indent=2)

    L = ["# 层1 代理量 · 零成本三件套（P1a / P1b / P3a / P4lb）\n",
         "| answer | 字数 | 中文占比 | 语言闸门 | P1a 后段新信息率 | P1b 前缀复述率 | P4lb 早期逐字复现 | P3a 措辞级(下界) | P3b 依据级 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        p1a = r["P1a_late_new_info"].get("value")
        p1b = r["P1b_prefix_echo"].get("value")
        p4 = r["P4lb_early_verbatim_recurrence"].get("value")
        p3 = (r.get("P3a_view_jaccard_lexical") or {}).get("median_jaccard")
        p3b = (r.get("P3b_view_evidence_jaccard") or {}).get("median_jaccard")
        lg = r.get("language_gate", {})
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["arm"], r["n_chars"], r["cjk_ratio"],
            ("✅" if lg.get("pass") else "**❌ 漂移**"),
            "-" if p1a is None else "%.3f" % p1a,
            "-" if p1b is None else "%.3f" % p1b,
            "-" if p4 is None else "%.3f" % p4,
            "-" if p3 is None else "%.3f" % p3,
            "-" if p3b is None else "%.3f" % p3b))
    md = "\n".join(L) + "\n"
    with open(os.path.splitext(args.out)[0] + ".md", "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
