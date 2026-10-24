#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 架构化对照实验的分析器（全零判官）

════════════════════════════════════════════════════════════════════════
★ 纪律
  1. **比率必配绝对分母**（"约束传导率 62%（分母 8 条约束）"）
  2. **差值必须对噪声地板**：同臂重复之间的差异 = 种子噪声地板
     ⇒ 臂间差值 < 地板 ⇒ 写"不可分辨"
  3. **分析单元是题**：本轮**只有 1 题** ⇒ 所有读数只是"本例描述"，
     **不构成任何一般化统计结论**。报告里必须写死这一条。
  4. 高命中不构成证据 ⇒ "约束传导率"只作描述，证据看置换探针。

★ 指标（全部可复现、零判官、无外部依赖）
  · char_len            正文字符数
  · title_dup           同臂标题重复（"模板化"的粗信号）
  · sent_jaccard        句级集合 Jaccard（臂内 vs 臂间）
  · n_linked / n_cons   状态约束**绑定在观测缺口上**的比例（机制层）
  · cons_hit            约束关键 n-gram 在定稿正文里的命中率（传导层）
  · excl_hit            已排除项的关键 n-gram 在定稿正文里的命中率（**应当低**：
                        排除了还出现 ⇒ 排除没起作用）
"""
from __future__ import annotations

import itertools
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import workflow_arch as WA

ARMS = ["A", "S", "WF-p", "WF-a", "WF-a-R", "WF-a-NO"]
ARM_CN = {
    "A": "直接调用（1 步）",
    "S": "等调用数中性管线（4 步，无状态）",
    "WF-p": "提示词式状态机（4 步）",
    "WF-a": "架构化状态机（4 步）",
    "WF-a-R": "架构化 + 反极性立场（5 步）",
    "WF-a-NO": "架构化 · 消融：无观测（3 步）",
}
_SENT_SPLIT = re.compile(r"[。！？!?；;\n]+")
_CJK = re.compile(r"[一-鿿]")
_EN = re.compile(r"[A-Za-z]")


def lang_ratio(text):
    """产出语言构成（中文占比）。

    ★★ **判据跑之前必须先验这个**：混排/外文产出会静默污染所有
       基于字符 n-gram 的判据（传导率、相似度），且 n-gram 集��与中文集
       **完全不相交** ⇒ 命中率归零、相似度归零 ⇒ 看起来像"信号消失"，
       实际是"语言变了"。
    """
    t = text or ""
    if not t.strip():
        return None          # ★ 空文本不是"漂移"，是"没有"（A 臂无 draft 字段）
    c = len(_CJK.findall(t)); e = len(_EN.findall(t))
    return round(c + e, 1) and round(c / max(c + e, 1), 4)


def sents(text):
    out = set()
    for s in _SENT_SPLIT.split(text or ""):
        s = (s or "").strip()
        s = re.sub(r"^[\s\-*·•>#\d\.\、]+", "", s)
        if len(s) >= 6:
            out.add(s)
    return out


def ngset(text, n=3):
    """字符 n-gram 集合（不要求整句一致）——本轮实测句级 Jaccard 全 0，零分辨力。"""
    t = re.sub(r"\s+", "", text or "")
    return set(t[i:i + n] for i in range(len(t) - n + 1))


_CONTENT_STOP = set("的了是在和与也就都而及其之或一个这那我你他她它们不很更最我我们这那什么怎么哪些"
                     "因为所以但是而且如果就是可以能够需要应该没有这个那个一种一些对于关于"
                     "不能只是不要不能也不没有并且然后因为所以这那每一任何具体需要写作文章初稿"
                     "必须这一轮本轮内容表达方式地方方面问题时候能够")


def content_words(text):
    """实词（≥2 字的汉字词 + 英文词），去停用词。

    ★ 用途：**来源归属测试** —— 约束里的实词到底来自**哪一份**初稿。
      比 n-gram 粗，比单字准；短词撞车率低。
    """
    t = (text or "")
    out = []
    for m in re.findall(r"[一-鿿]{2,}", t):
        # 中文：滑窗 2 字 + 3 字
        for n in (2, 3):
            for i in range(len(m) - n + 1):
                w = m[i:i + n]
                if w not in _CONTENT_STOP:
                    out.append(w)
    for m in re.findall(r"[A-Za-z]{3,}", t):
        if m.lower() not in _CONTENT_STOP:
            out.append(m.lower())
    return out


def jacc_ng(a, b, n=3):
    A, B = ngset(a, n), ngset(b, n)
    if not A or not B:
        return None
    return len(A & B) / len(A | B)


def jacc(a, b):
    A, B = set(a), set(b)
    if not A or not B:
        return None
    return len(A & B) / len(A | B)


def title_of(text):
    t = (text or "").strip().splitlines()
    for ln in t:
        ln = ln.strip().strip("*# ").strip()
        if ln:
            return ln
    return ""


def hit_rate(constraint, text):
    """约束的关键 n-gram 有多少出现在正文里。返回 (命中率, 约束的 n-gram 数)"""
    g = WA.ngrams(constraint)
    if not g:
        return None, 0
    tg = WA.ngrams(text)
    if not tg:
        return None, 0
    return len(g & tg) / len(g), len(g)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "runs", "arch_compare.jsonl"))
    ap.add_argument("--probe", default=os.path.join(HERE, "runs", "arch_probe.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "arch_analysis.json"))
    args = ap.parse_args()

    rs = load(args.src)
    by = defaultdict(list)
    for r in rs:
        by[r.get("arm")].append(r)
    for a in by:
        by[a].sort(key=lambda r: r.get("tag") or 0)

    R = {"meta": {
        "src": os.path.basename(args.src),
        "batch_ids": sorted({r.get("batch_id") for r in rs if r.get("batch_id")}),
        "n_questions": 1,
        "reps_per_arm": max((len(v) for v in by.values()), default=0),
        "★ 分析单元=题，本轮只有 1 题 ⇒ 全部读数为本例描述，不构成一般化统计结论": True,
    }}

    # ---------- 1. 基本读数 ----------
    basic = {}
    for a in ARMS:
        rows = []
        for r in by.get(a, []):
            txt = (r.get("text") or "").strip()
            calls = r.get("calls") or []
            ncall = len([c for c in calls if not (c[0] == "transfer" and c[1] == 0)])
            rows.append({
                "tag": r.get("tag"), "len": len(txt), "n_calls": ncall,
                "title": title_of(txt),
                "n_sent": len(sents(txt)),
                "error": r.get("error"),
                "elapsed": r.get("elapsed"),
            })
        basic[a] = rows
    R["basic"] = basic
    # ---------- 1b. 语言有效性闸门（判据前置条件） ----------
    lang = {}
    for a in ARMS:
        rows = []
        for r in by.get(a, []):
            txt = (r.get("text") or "")
            lr = lang_ratio(txt) or 0.0
            dr = lang_ratio(r.get("draft") or "")
            rows.append({"tag": r.get("tag"), "lang_cn_ratio_final": lr,
                         "lang_cn_ratio_draft": dr,
                         "drifted_final": (lr is not None and lr < 0.9),
                         "drifted_draft": (dr is not None and dr < 0.9),
                         "len": len(txt.strip())})
        lang[a] = {"rows": rows,
                   "n_drifted_final": sum(1 for x in rows if x["drifted_final"]),
                   "n_drifted_draft": sum(1 for x in rows if x["drifted_draft"]),
                   "n": len(rows)}
    R["language_gate"] = lang
    R["basic_summary"] = {
        a: {
            "n": len(basic.get(a, [])),
            "len_mean": mean([x["len"] for x in basic.get(a, [])]),
            "len_min": min([x["len"] for x in basic.get(a, [])], default=None),
            "len_max": max([x["len"] for x in basic.get(a, [])], default=None),
            "calls_per_run": sorted({x["n_calls"] for x in basic.get(a, [])}),
            "errors": [x["error"] for x in basic.get(a, []) if x["error"]],
            "titles": [x["title"] for x in basic.get(a, [])],
            "title_dup_rate": (1 - len({x["title"] for x in basic.get(a, [])})
                               / len(basic[a])) if basic.get(a) else None,
        } for a in ARMS
    }

    # ---------- 2. 句级集合距离：臂内(噪声地板) vs 臂间 ----------
    def pair_jac(list_a, list_b, same_arm):
        vals = []
        for x, y in itertools.combinations(list_a + list_b, 2):
            ax = x.get("arm"); ay = y.get("arm")
            if (ax == ay) != same_arm:
                continue
            v = jacc(sents(x.get("text")), sents(y.get("text")))
            if v is not None:
                vals.append(v)
        return vals

    within = {}
    for a in ARMS:
        v = pair_jac(by.get(a, []), [], True)
        within[a] = {"pairs": len(v), "mean": mean(v)}
    cross = {}
    for a, b in itertools.combinations(ARMS, 2):
        v = pair_jac(by.get(a, []), by.get(b, []), False)
        cross["%s|%s" % (a, b)] = {"pairs": len(v), "mean": mean(v)}
    R["sent_jaccard"] = {"within_arm(噪声地板)": within, "cross_arm": cross}

    # ---------- 2b. 字符 3-gram Jaccard（更细的相似度） ----------
    def pair_ng(list_a, list_b, same_arm):
        vals = []
        for x, y in itertools.combinations(list_a + list_b, 2):
            if ((x.get("arm") == y.get("arm")) != same_arm):
                continue
            v = jacc_ng(x.get("text"), y.get("text"))
            if v is not None:
                vals.append(v)
        return vals
    ng_within, ng_cross = {}, {}
    for a in ARMS:
        v = pair_ng(by.get(a, []), [], True)
        ng_within[a] = {"pairs": len(v), "mean": mean(v)}
    for a, b in itertools.combinations(ARMS, 2):
        v = pair_ng(by.get(a, []), by.get(b, []), False)
        ng_cross["%s|%s" % (a, b)] = {"pairs": len(v), "mean": mean(v)}
    R["ng_jaccard"] = {"within_arm(噪声地板)": ng_within, "cross_arm": ng_cross}

    # ---------- 2c. 只用"同语言"样本（中文占比≥0.9）重算 ----------
    def ok_lang(r):
        lr = lang_ratio(r.get("text") or "")
        return lr is not None and lr >= 0.9
    def pair_ng2(list_a, list_b, same_arm):
        vals = []
        for x, y in itertools.combinations(list_a + list_b, 2):
            if not (ok_lang(x) and ok_lang(y)):
                continue
            if ((x.get("arm") == y.get("arm")) != same_arm):
                continue
            v = jacc_ng(x.get("text"), y.get("text"))
            if v is not None:
                vals.append(v)
        return vals
    ng_within_cn, ng_cross_cn = {}, {}
    for a in ARMS:
        v = pair_ng2(by.get(a, []), [], True)
        ng_within_cn[a] = {"pairs": len(v), "mean": mean(v)}
    for a, b in itertools.combinations(ARMS, 2):
        v = pair_ng2(by.get(a, []), by.get(b, []), False)
        ng_cross_cn["%s|%s" % (a, b)] = {"pairs": len(v), "mean": mean(v)}
    R["ng_jaccard_仅同语言"] = {"within_arm(噪声地板)": ng_within_cn, "cross_arm": ng_cross_cn}

    # ---------- 3. 机制层：绑定率 / 传导率 / 排除命中率 ----------
    mech = {}
    for a in ("WF-a", "WF-a-R"):
        rows = []
        for r in by.get(a, []):
            tr = r.get("trace") or {}
            li = tr.get("linked") or []
            n_cons = len(tr.get("linked") or []) or len((r.get("state1") or {}).get("keeps") or [])
            n_linked = sum(1 for x in li if x.get("linked"))
            n_struct = sum(1 for x in li if x.get("method") == "gap_index")
            n_lex_ok = sum(1 for x in li if x.get("method") == "lexical_fallback" and x.get("linked"))
            n_lex_no = sum(1 for x in li if x.get("method") == "lexical_fallback" and not x.get("linked"))
            scores = [x.get("score") for x in li if x.get("score") is not None]
            cons = (r.get("state1") or {}).get("keeps") or []
            exc = (r.get("state1") or {}).get("excluded") or []
            txt = (r.get("text") or "")
            lr = lang_ratio(txt) or 0.0
            ch = [hit_rate(c, txt) for c in cons]
            ch = [(h, n) for h, n in ch if h is not None]
            eh = [hit_rate(e, txt) for e in exc]
            eh = [(h, n) for h, n in eh if h is not None]
            rows.append({
                "tag": r.get("tag"),
                "n_constraints": n_cons, "n_linked": n_linked,
                "n_linked_by_structure": n_struct,
                "n_linked_by_lexical": n_lex_ok, "n_linked_unknown": n_lex_no,
                "link_scores_all": [x.get("score") for x in li if x.get("score") is not None],
                "link_rate": (n_linked / n_cons) if n_cons else None,
                "link_scores": scores,
                "n_gaps": tr.get("n_gaps"), "n_excluded": tr.get("n_excluded"),
                "no_new_constraints": tr.get("no_new_constraints"),
                "obs_missing": tr.get("observation_missing_fields"),
                "lang_cn_ratio": lr,
                "lang_valid": lr >= 0.9,
                "cons_hit_mean": mean([h for h, _ in ch]),
                "cons_hit_mean_仅同语言": mean([h for h, _ in ch] if lr >= 0.9 else []),
                "cons_hit_n": len(ch),
                "excl_hit_mean": mean([h for h, _ in eh]),
                "excl_hit_n": len(eh),
            })
        tot_c = sum(x["n_constraints"] for x in rows)
        tot_l = sum(x["n_linked"] for x in rows)
        tot_s = sum(x["n_linked_by_structure"] for x in rows)
        tot_lo = sum(x["n_linked_by_lexical"] for x in rows)
        tot_ln = sum(x["n_linked_unknown"] for x in rows)
        mech[a] = {"rows": rows,
                   "link_summary": {"n_linked": tot_l, "n_constraints": tot_c,
                                    "rate": (tot_l / tot_c) if tot_c else None,
                                    "n_by_structure": tot_s, "n_by_lexical": tot_lo,
                                    "n_unknown": tot_ln}}
    R["mechanism"] = mech

    # ---------- 4. 消融：WF-a vs WF-a-NO ----------
    no = by.get("WF-a-NO", [])
    ab = []
    for r in by.get("WF-a", []):
        match = [x for x in no if x.get("tag") == r.get("tag")]
        if not match:
            continue
        n = match[0]
        ab.append({
            "tag": r.get("tag"),
            "len_with_obs": len((r.get("text") or "").strip()),
            "len_no_obs": len((n.get("text") or "").strip()),
            "sent_jaccard": jacc(sents(r.get("text")), sents(n.get("text"))),
            "with_obs_n_excluded": len((r.get("state1") or {}).get("excluded") or []),
            "no_obs_n_excluded": len((n.get("state1") or {}).get("excluded") or []),
        })
    R["ablation_obs_vs_noobs"] = ab

    # ---------- 5. 置换探针 ----------
    if os.path.exists(args.probe):
        pr = load(args.probe)
        idx = defaultdict(dict)
        for r in pr:
            idx[r.get("src_index")][r.get("kind")] = r
        swap_rows = []
        for i in sorted(idx):
            d = idx[i]
            if "same" not in d or "swap" not in d:
                continue
            base = None
            for r in by.get("WF-a", []):
                if r.get("tag") == d["same"].get("src_tag"):
                    base = r
            if base is None:
                continue
            st0 = WA.State(**base["state0"])
            s_base = WA.State(**base["state1"])
            s_same = WA.State(**d["same"]["state1"])
            s_swap = WA.State(**d["swap"]["state1"])
            orig_draft = base.get("draft") or ""
            swap_draft = (by.get("WF-a") or [{}])[(i + 1) % max(len(by.get("WF-a", [])), 1)].get("draft") or ""
            # ★ 来源归属：约束里的实词，到底来自**哪一份**初稿？
            def prov(keeps, src_draft, other_draft):
                tot = hit = 0
                for c in keeps:
                    for w in content_words(c):
                        tot += 1
                        if w in src_draft and w not in other_draft:
                            hit += 1
                return (hit / tot) if tot else None, tot
            p_swap, n_swap = prov(s_swap.keeps, swap_draft, orig_draft)
            p_same, n_same = prov(s_same.keeps, orig_draft, swap_draft)

            # ★★ 最锐的读数：「已排除」的措辞是**代码从观测里逐字抽的引号内容**
            #    ⇒ 它必然逐字来自**某一份初稿的原文** ⇒ 零阈值、零歧义。
            def excl_literal(excluded, d1, d2):
                hits1 = hits2 = n = 0
                for e in (excluded or []):
                    w = e.replace("不要再出现：", "").strip().strip("“”\"'")
                    if len(w) < 2:
                        continue
                    n += 1
                    if w in d1:
                        hits1 += 1
                    if w in d2:
                        hits2 += 1
                return (hits1, hits2, n)
            e_same_1, e_same_2, e_n = excl_literal(s_same.excluded, orig_draft, swap_draft)
            e_swap_1, e_swap_2, _ = excl_literal(s_swap.excluded, swap_draft, orig_draft)
            # gap（对初稿的**描述**）的实词来源
            def gprov(gaps, d1, d2):
                tot = hit = 0
                for g in (gaps or []):
                    for w in content_words(g):
                        tot += 1
                        if w in d1 and w not in d2:
                            hit += 1
                return (hit / tot) if tot else None, tot
            g_swap, g_n = gprov(d["swap"]["observation"].get("gaps"), swap_draft, orig_draft)
            g_same, _ = gprov(d["same"]["observation"].get("gaps"), orig_draft, swap_draft)
            swap_rows.append({
                "tag": d["same"].get("src_tag"),
                "★换历史后状态变化(keep_jaccard)": WA.state_diff(s_base, s_swap)["keep_jaccard"],
                "★同历史重跑状态变化(种子噪声地板)": WA.state_diff(s_base, s_same)["keep_jaccard"],
                "★换历史后已排除变化(excl_jaccard)": WA.state_diff(s_base, s_swap)["excluded_jaccard"],
                "★同历史重跑已排除变化": WA.state_diff(s_base, s_same)["excluded_jaccard"],
                # ★★ 排除项逐字归属
                "★★同历史:排除措辞逐字在【原初稿】": e_same_1,
                "★★同历史:排除措辞逐字在【别处初稿】": e_same_2,
                "★★同历史:排除措辞条数": e_n,
                "★★换历史:排除措辞逐字在【换入初稿】": e_swap_1,
                "★★换历史:排除措辞逐字在【原初稿】": e_swap_2,
                # gap 实词来源
                "★换历史:gap实词来自换入初稿": g_swap,
                "★同历史:gap实词来自原初稿": g_same,
                # 约束实词来源（辅助）
                "★换历史:约束实词来自换入初稿的比例": p_swap,
                "★换历史:约束实词来自原初稿的比例": prov(s_swap.keeps, orig_draft, swap_draft)[0],
                "★同历史:约束实词来自原初稿的比例": p_same,
                "★同历史:约束实词来自别处初稿的比例": prov(s_same.keeps, swap_draft, orig_draft)[0],
                "实词分母(换)": n_swap, "实词分母(同)": n_same,
                "正文句级差异(换历史)": jacc(sents(base.get("text")), sents(d["swap"].get("text"))),
                "正文句级差异(同历史)": jacc(sents(base.get("text")), sents(d["same"].get("text"))),
                "n_linked_swap": (d["swap"].get("trace") or {}).get("n_linked"),
                "n_linked_same": (d["same"].get("trace") or {}).get("n_linked"),
            })
        R["swap_probe"] = {
            "rows": swap_rows,
            "mean_keep_jaccard_swap": mean([x["★换历史后状态变化(keep_jaccard)"] for x in swap_rows]),
            "mean_keep_jaccard_same(地板)": mean([x["★同历史重跑状态变化(种子噪声地板)"] for x in swap_rows]),
            "mean_excl_jaccard_swap": mean([x["★换历史后已排除变化(excl_jaccard)"] for x in swap_rows]),
            "mean_excl_jaccard_same(地板)": mean([x["★同历史重跑已排除变化"] for x in swap_rows]),
            "★来源归属_换历史_来自换入初稿": mean([x["★换历史:约束实词来自换入初稿的比例"] for x in swap_rows]),
            "★来源归属_换历史_来自原初稿": mean([x["★换历史:约束实词来自原初稿的比例"] for x in swap_rows]),
            "★来源归属_同历史_来自原初稿": mean([x["★同历史:约束实词来自原初稿的比例"] for x in swap_rows]),
            "★来源归属_同历史_来自别处初稿": mean([x["★同历史:约束实词来自别处初稿的比例"] for x in swap_rows]),
            "n": len(swap_rows),
        }
    else:
        R["swap_probe"] = {"status": "probe 文件不存在，未跑"}

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=2)

    # ---------- 控制台摘要 ----------
    print("=" * 78)
    print("批号 %s ｜ 模型 %s ｜ 题数 1 ｜ 每臂 %d 次" %
          (",".join(R["meta"]["batch_ids"]), rs[0].get("model", "?"),
           R["meta"]["reps_per_arm"]))
    print("=" * 78)
    print("\n【1】基本读数")
    print("  %-9s %-4s %-9s %-7s %-9s %s" % ("臂", "n", "字数(均)", "调用", "标题重复", "错误"))
    for a in ARMS:
        s = R["basic_summary"].get(a) or {}
        print("  %-9s %-4s %-9s %-7s %-9s %s" % (
            a, s.get("n"), s.get("len_mean"),
            ",".join(map(str, s.get("calls_per_run") or [])),
            ("%.2f" % s["title_dup_rate"]) if s.get("title_dup_rate") is not None else "-",
            ";".join(s.get("errors") or []) or "无"))
    print("\n【2】句级 Jaccard（臂内=种子噪声地板）")
    for a in ARMS:
        w = within.get(a) or {}
        print("  臂内 %-9s pairs=%-3s mean=%s" % (a, w.get("pairs"), w.get("mean")))
    print("  臂间（部分）：")
    for k, v in list(cross.items())[:8]:
        print("    %-18s pairs=%-3s mean=%s" % (k, v["pairs"], v["mean"]))
    print("\n【1b】语言有效性闸门（中文占比<90% = 漂移）")
    for a in ARMS:
        v = lang.get(a) or {}
        print("  %-9s 定稿漂移 %d/%s ｜ 初稿漂移 %d/%s" % (
            a, v.get("n_drifted_final"), v.get("n"), v.get("n_drifted_draft"), v.get("n")))
    print("\n【2b】字符 3-gram Jaccard")
    for a in ARMS:
        w = ng_within.get(a) or {}
        print("  臂内 %-9s pairs=%-3s mean=%s" % (a, w.get("pairs"), w.get("mean")))
    for k, v in list(ng_cross.items())[:6]:
        print("    臂间 %-18s pairs=%-3s mean=%s" % (k, v["pairs"], v["mean"]))
    print("\n【2c】字符 3-gram Jaccard（**只用同语言样本**）")
    for a in ARMS:
        w = ng_within_cn.get(a) or {}
        print("  臂内 %-9s pairs=%-3s mean=%s" % (a, w.get("pairs"), w.get("mean")))
    print("\n【3】机制层（WF-a / WF-a-R）")
    for a, m in mech.items():
        s = m["link_summary"]
        print("  %-8s 绑定 %d/%d (%.0f%%) ｜ 结构声明 %d ｜ 字面 %d ｜ 未定 %d" % (
            a, s["n_linked"], s["n_constraints"], 100 * (s["rate"] or 0),
            s.get("n_by_structure", 0), s.get("n_by_lexical", 0), s.get("n_unknown", 0)))
        for row in m["rows"]:
            print("     #%s 中文%%=%3d %s gaps=%s excluded=%s 约束传导=%s(分母%s) 同语言版=%s 排除命中=%s(分母%s) %s" % (
                row["tag"], 100 * (row.get("lang_cn_ratio") or 0),
                "★漂移" if not row.get("lang_valid") else "      ",
                row["n_gaps"], row["n_excluded"],
                ("%.2f" % row["cons_hit_mean"]) if row["cons_hit_mean"] is not None else "-",
                row["cons_hit_n"],
                ("%.2f" % row["cons_hit_mean_仅同语言"]) if row.get("cons_hit_mean_仅同语言") is not None else "-",
                ("%.2f" % row["excl_hit_mean"]) if row["excl_hit_mean"] is not None else "-",
                row["excl_hit_n"],
                ("缺字段:" + ",".join(row["obs_missing"])) if row.get("obs_missing") else ""))
    print("\n【4】消融：WF-a（有观测） vs WF-a-NO（无观测）")
    for r in ab:
        print("  #%s  字数 %s→%s  句级J=%.3f  已排除 %s→%s" % (
            r["tag"], r["len_with_obs"], r["len_no_obs"],
            r["sent_jaccard"] if r["sent_jaccard"] is not None else -1,
            r["with_obs_n_excluded"], r["no_obs_n_excluded"]))
    print("\n【5】状态历史置换探针")
    sp = R.get("swap_probe") or {}
    if "rows" in sp:
        for r in sp["rows"]:
            print("  #%s  换历史 keep-J=%.3f  同历史(地板) keep-J=%.3f  |  换历史 excl-J=%.3f 同历史 excl-J=%.3f" %
                  (r["tag"], r["★换历史后状态变化(keep_jaccard)"],
                   r["★同历史重跑状态变化(种子噪声地板)"],
                   r["★换历史后已排除变化(excl_jaccard)"], r["★同历史重跑已排除变化"]))
        print("  均值：换历史 keep-J=%s  地板 keep-J=%s  (n=%d)" %
              (sp.get("mean_keep_jaccard_swap"), sp.get("mean_keep_jaccard_same(地板)"), sp.get("n")))
        print("  ★来源归属（约束实词来自哪份初稿）")
        for r in sp["rows"]:
            print("    #%s 换历史: 来自换入=%.3f / 来自原=%.3f (实词分母%d) ｜ 同历史: 来自原=%.3f / 来自别处=%.3f (分母%d)" %
                  (r["tag"], r["★换历史:约束实词来自换入初稿的比例"],
                   r["★换历史:约束实词来自原初稿的比例"], r["实词分母(换)"],
                   r["★同历史:约束实词来自原初稿的比例"],
                   r["★同历史:约束实词来自别处初稿的比例"], r["实词分母(同)"]))
        print("  均值：换历史→来自换入=%.3f 来自原=%.3f ｜ 同历史→来自原=%.3f 来自别处=%.3f" %
              (sp.get("★来源归属_换历史_来自换入初稿"), sp.get("★来源归属_换历史_来自原初稿"),
               sp.get("★来源归属_同历史_来自原初稿"), sp.get("★来源归属_同历史_来自别处初稿")))
        print("  ★★ 排除措辞逐字归属（零阈值，代码从观测逐字抽取）")
        ts = [0, 0, 0, 0]
        for r in sp["rows"]:
            print("    #%s 同历史: 在原初稿 %d / 在别处 %d（共 %d 条） ｜ 换历史: 在换入 %d / 在原 %d" %
                  (r["tag"], r["★★同历史:排除措辞逐字在【原初稿】"], r["★★同历史:排除措辞逐字在【别处初稿】"],
                   r["★★同历史:排除措辞条数"], r["★★换历史:排除措辞逐字在【换入初稿】"],
                   r["★★换历史:排除措辞逐字在【原初稿】"]))
            ts[0] += r["★★同历史:排除措辞逐字在【原初稿】"]; ts[1] += r["★★同历史:排除措辞逐字在【别处初稿】"]
            ts[2] += r["★★换历史:排除措辞逐字在【换入初稿】"]; ts[3] += r["★★换历史:排除措辞逐字在【原初稿】"]
        print("    合计：同历史→在原 %d / 在别处 %d ｜ 换历史→在换入 %d / 在原 %d" % tuple(ts))
    else:
        print("  ", sp.get("status"))
    print("\n[out] %s" % args.out)


if __name__ == "__main__":
    main()
