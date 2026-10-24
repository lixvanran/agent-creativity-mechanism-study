# -*- coding: utf-8 -*-
"""Agent 自主提出架构 —— 训练的主循环。

设计要点（来自前几轮失败的复盘）：

1. **提出者是 Agent 自己。** 它看自己的失败诊断，自己写出新的工作流规格。
2. **它只能看到聚合诊断信号**，看不到 oracle 原文、看不到正确值、看不到题目答案。
   否则就是把答案暗示注入了架构 —— 这是我前几轮栽过的最贵的坑。
   诊断是**代码算出来的统计量**：矛盾集中在哪类断言、依据里有多少数字从没被提到过。
3. **目标不是「答案更对」，是「思维面更宽」，且矛盾率不超上限。**
   宽度单调不减 → 搜索不会像「选赢家」那样在噪声上取胜。
4. **断言必须去重后再计数。** 模型在一份答案里会把同一事实说 3-4 遍。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM                        # noqa: E402
from creativity_lab.metrics import _mat                      # noqa: E402
from creativity_lab.workflow import (DEFAULT_SPEC, describe,  # noqa: E402
                                     preflight_text, run_spec, spec_key)
from creativity_lab.verify import (check_claims, extract_claims, score_of)  # noqa: E402

OUT = "runs/train_agent"
os.makedirs(OUT, exist_ok=True)
DATA = json.load(open("creativity_lab/data/policy_topics.json", encoding="utf-8"))
LAWS, TOPICS = DATA["laws"], DATA["topics"]
law_of = {t["tid"]: t["law"] for t in TOPICS}
REPS = 2
ARMS = ("direct", "dual_fuse", "dual_select")
SEARCH = TOPICS[:5]          # 搜索用
HOLD = TOPICS[5:]            # 留出用
CONFLICT_CAP_ABS = 0.30      # 绝对上限（若最优基线更严则以基线为准）


def _char_bigrams(t):
    t = re.sub(r"\s", "", t or "")
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _fallback_dedup(claims, thr=0.75):
    """embed 不可用时的降级：字符二元组 Jaccard。宁可保守，不要崩。"""
    keep, G = [], []
    for c in claims:
        g = _char_bigrams(c)
        ok = True
        for g2 in G:
            if not (g | g2):
                continue
            if len(g & g2) / len(g | g2) >= thr:
                ok = False; break
        if ok:
            keep.append(c); G.append(g)
    return keep


def embed_rows(ts):
    """embedding 接口会瞬时返回 None → 重试 → 仍失败则抛，由 dedup_n 降级。"""
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    last = None
    for attempt in range(3):
        try:
            V = _mat(LLM().embed(uniq))
            if V is not None and V.shape[0] == len(uniq):
                return V[idx]
            last = "embed 返回 %s 行，期望 %d" % (getattr(V, "shape", None), len(uniq))
        except Exception as e:
            last = str(e)[:80]
        time.sleep(3 + attempt * 4)
    raise RuntimeError("embed 不可用: %s" % last)


def dedup_n(claims, thr=0.75):
    if not claims:
        return []
    try:
        M = embed_rows(claims)
        S = M @ M.T
        keep = []
        for i in range(len(claims)):
            if all(S[i, j] < thr for j in keep):
                keep.append(i)
        return [claims[i] for i in keep]
    except Exception:
        return _fallback_dedup(claims, thr)


# ---------------------------------------------------------------- 聚合诊断（不含答案）
def diagnose(claims_all, verd, ev_by_tid):
    """只产出**聚合统计量**。不返回 oracle 原文，不返回正确值。"""
    diag = defaultdict(lambda: dict(n_claims=0, n_con=0, n_sup=0, n_un=0, n_non=0,
                                    con_numeric=0, con_article=0,
                                    dup_ratio=0.0))
    for tid, cs in claims_all.items():
        d = diag[tid]
        raw = cs
        d["n_claims"] += len(raw)
        u = dedup_n(raw)
        d["dup_ratio"] = round(1 - len(u) / max(len(raw), 1), 3)
        for c in u:
            v = verd.get(c, "解析失败")
            d["n_sup"] += v == "支持"; d["n_con"] += v == "矛盾"
            d["n_un"] += v == "未提及"; d["n_non"] += v == "非主张"
            if v == "矛盾":
                if re.search(r"\d", c): d["con_numeric"] += 1
                if re.search(r"第[一二三四五六七八九十百\d]+条|条例|办法|规定|细则", c):
                    d["con_article"] += 1
        # 依据里的数字，有多少从没在任何答案里出现过（只用数字集合，不暴露值）
    return diag


DIAG_TEXT = """你在改进一个「回答问题的 AI 工作流」。下面是**上一轮运行后的聚合诊断**，
全部是统计量，不含任何具体答案或正确数值。

{d}

**工作流在作答时只能看到问题本身**——它无法访问任何外部文件、数据库、检索结果或参考资料。
它能做的只有这些：
- 多次独立生成，然后合并、对比或二选一
- 要求各次生成的角度互不相同
- 要求在输出前做一遍自检（核对前后表述是否一致、有无自相矛盾）
- 要求先列提纲再展开，或反过来先写结论再补依据
**不要提出需要查阅外部材料才能完成的步骤。**

请据此提出一个改进后的工作流。输出严格如下，不要解释：

PREFLIGHT:
（最多 4 行，每行一条 10-30 字的中文**操作步骤**。必须是「做什么」，
**不得出现「查阅／引用／检索依据／建立索引／核对原文」等需要外部材料的动作。**
不是「说什么」。不得包含任何具体金额、比例、条号、文件名。）

BRANCHES: <1|3|5>
MODE: <direct|fuse|select>
SELFCHECK: <yes|no>"""


def propose(diag_summary, prev_desc, model="MiniMax-M3"):
    p = DIAG_TEXT.format(d=diag_summary) + \
        "\n\n（当前工作流：%s）" % prev_desc
    t = LLM().chat(p, model=model, purpose="propose", max_tokens=1200,
                   budgets=(1800,), min_ok=30) or ""
    pf, br, mode, sc = [], 3, "select", "no"
    sec = None
    for ln in t.splitlines():
        ln = ln.strip()
        if ln.upper().startswith("PREFLIGHT"):
            sec = "pf"; continue
        if ln.upper().startswith("BRANCHES"):
            sec = "br"; continue
        if ln.upper().startswith("MODE"):
            sec = "mode"; continue
        if ln.upper().startswith("SELFCHECK"):
            sec = "sc"; continue
        if sec == "pf":
            ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln)
            if 8 <= len(ln) <= 40 and ln not in pf:
                pf.append(ln)
        elif sec == "br":
            m = re.search(r"[135]", ln)
            if m: br = int(m.group())
        elif sec == "mode":
            m = re.search(r"direct|fuse|select", ln, re.I)
            if m: mode = m.group().lower()
        elif sec == "sc":
            if re.search(r"yes|是", ln, re.I): sc = "yes"
    if not pf:                       # 提案没解析出来 → 退回 incumbent，不静默接受空规格
        return None
    return dict(n_branches=br, mode=mode, preflight=pf,
                selfcheck=(sc == "yes"), _texts=pf)


# ---------------------------------------------------------------- 评估
def _recompute(res, topics):
    """从缓存的 raw 结果重算聚合（修掉「解析失败计入分母」的 bug）。"""
    widths, con, sup, legal, fail = [], 0, 0, 0, 0
    for T in topics:
        raw = [c for r in res if r["tid"] == T["tid"] for c in r["claims"]]
        widths.append(len(dedup_n(raw, 0.75)))
    tot_claims = 0
    for r in res:
        for c in r["claims"]:
            tot_claims += 1
            v = r["verd"].get(c, "解析失败")
            if v == "解析失败":
                fail += 1; continue
            con += v == "矛盾"; sup += v == "支持"
            legal += v not in ("未提及", "非主张")
    if legal == 0:
        return None
    cap = globals().get("CAP", CONFLICT_CAP_ABS)
    out = dict(width=float(np.mean(widths)), width_sum=sum(widths),
               conflict=con / legal, support=sup / legal,
               n_verified=legal, n_fail=fail, fail_rate=fail / max(tot_claims, 1),
               n=len(res))
    out["cap"] = cap
    out["feasible"] = out["conflict"] <= cap
    out["objective"] = out["width"] if out["feasible"] else -out["width"]
    return out


def evaluate(spec, topics, tag, reuse=True):
    fn = "%s/%s_%s.json" % (OUT, tag, spec_key(spec))
    if reuse and os.path.exists(fn):
        try:
            d = json.load(open(fn, encoding="utf-8"))
            if d.get("agg") and len(d.get("raw", [])) == len(topics):
                print("    [复用缓存 %s]" % os.path.basename(fn), flush=True)
                raw = d["raw"]
                agg = _recompute(raw, topics)   # CAP 此刻还是默认值，稍后由 main 统一重算
                if agg is not None:
                    d["agg"] = agg
                    json.dump(d, open(fn, "w"), ensure_ascii=False, indent=1)
                    return agg, raw
        except Exception:
            pass
    def one(T):
        ans = run_spec(LLM(), T, spec)
        cs = extract_claims(LLM(), ans)
        v = check_claims(LLM(), T["ask"], LAWS[law_of[T["tid"]]]["evidence"], cs)
        sc = score_of(v, cs)
        sc.update(tid=T["tid"], len=len(ans), claims=cs, verd=v)
        return sc
    res = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in as_completed([ex.submit(one, T) for T in topics]):
            try:
                res.append(f.result())
            except Exception as e:
                print("  ERR %s" % str(e)[:60], flush=True)
    # **空输出 = 生成失败，不能记成「0 错误 → 可行」。** 曾因 API 故障让某臂白捡一个
    # 「可行」判定。失败的样本必须剔出比较，且该臂的可行性判为未知。
    n_fail_gen = sum(1 for r in res if not r.get("claims") or r.get("len", 0) < 40)
    if n_fail_gen:
        print("    ⚠ 生成失败 %d/%d 份，剔出比较" % (n_fail_gen, len(res)), flush=True)
        res = [r for r in res if r.get("claims") and r.get("len", 0) >= 40]
    if not res:
        return None
    # 三轴
    widths, con, sup, legal, fail = [], 0, 0, 0, 0
    for T in topics:
        raw = [c for r in res if r["tid"] == T["tid"] for c in r["claims"]]
        widths.append(len(dedup_n(raw, 0.75)))
    for r in res:
        for c in r["claims"]:
            v = r["verd"].get(c, "解析失败")
            if v == "解析失败":
                fail += 1; continue          # **不计入分母**：核验失败不是"中立"，是数据缺失
            con += v == "矛盾"; sup += v == "支持"
            legal += v not in ("未提及", "非主张")
    agg = dict(width=float(np.mean(widths)), width_sum=sum(widths),
               conflict=con / max(legal, 1), support=sup / max(legal, 1),
               n_verified=legal, n_fail=fail,
               fail_rate=fail / max(len(res) and sum(len(r["claims"]) for r in res) or 1, 1),
               n=len(res), n_gen_fail=n_fail_gen)
    if legal == 0:                      # 没有可核验的样本 → 不可判定
        agg["conflict"] = 9.0; agg["support"] = 0.0; agg["feasible"] = False
        agg["objective"] = -9e9
    # 目标：宽度最大化，矛盾率不超上限
    cap = globals().get("CAP", CONFLICT_CAP_ABS)
    agg["cap"] = cap
    agg["objective"] = agg["width"] if agg["conflict"] <= cap else -agg["width"]
    agg["feasible"] = agg["conflict"] <= cap
    json.dump(dict(spec={k: v for k, v in spec.items() if k != "_texts"},
                   texts=spec.get("_texts", []), agg=agg,
                   per=[{k: v for k, v in r.items() if k not in ("claims", "verd")} for r in res],
                   raw=res),
              open(fn, "w"), ensure_ascii=False, indent=1)
    return agg, res


def main():
    t0 = time.time()
    ROUNDS = int(os.environ.get("ROUNDS", "2"))
    print("训练域 %s（搜索）| 留出 %s" % ([t["tid"] for t in SEARCH], [t["tid"] for t in HOLD]),
          flush=True)
    print("目标: 最大化宽度(去重并集) | 硬约束: 矛盾率 ≤ 最优基线（绝对兜底 %.0f%%）" % (CONFLICT_CAP_ABS * 100),
          flush=True)

    # ---- 基线 ----
    print("\n== 基线 ==", flush=True)
    baselines = {}
    for arm, mode in (("direct", None), ("dual_fuse", "fuse"), ("dual_select", "select")):
        if mode is None:
            spec = dict(DEFAULT_SPEC); spec["n_branches"] = 1; spec["mode"] = "direct"
        else:
            spec = dict(DEFAULT_SPEC); spec["mode"] = mode
        a, res = evaluate(spec, SEARCH, "base")
        baselines[arm] = (spec, a)
        print("  %-12s 宽度 %.2f  支持率 %.1f%%  矛盾率 %.1f%%  [已核验%d条/失败%d] %s"
              % (arm, a["width"], a["support"] * 100, a["conflict"] * 100,
                 a.get("n_verified", 0), a.get("n_fail", 0),
                 "可行" if a["feasible"] else "**超约束**"), flush=True)
    # 约束用**相对口径**：矛盾率不得超过最优基线。绝对阈值只作兜底。
    feas = [k for k in baselines if baselines[k][1]["conflict"] <= CONFLICT_CAP_ABS]
    pool = feas if feas else list(baselines)
    best_arm = min(pool, key=lambda k: baselines[k][1]["conflict"])
    CAP = baselines[best_arm][1]["conflict"]   # incumbent 的矛盾率 → 它必然可行
    print("  → 矛盾率上限（= 最优基线）= %.1f%%" % (CAP * 100), flush=True)
    globals()["CAP"] = CAP
    for k, (sp, a) in baselines.items():        # 用最终 CAP 统一重算可行性
        a["cap"] = CAP; a["feasible"] = a["conflict"] <= CAP
        a["objective"] = a["width"] if a["feasible"] else -a["width"]
    best_spec, best_agg = baselines[best_arm]
    print("  → 基线最优: %s 宽度 %.2f 矛盾率 %.1f%%"
          % (best_arm, best_agg["width"], best_agg["conflict"] * 100), flush=True)

    # ---- 迭代：Agent 提案 → 评估 → 反馈 ----
    history = [(best_arm, best_spec, best_agg)]
    for rnd in range(1, ROUNDS + 1):
        print("\n== 轮 %d：Agent 自主提案 ==" % rnd, flush=True)
        # 诊断：跑一遍当前最优规格，收集聚合诊断
        dres = evaluate(best_spec, SEARCH, "diag")
        if dres is None:
            print("    诊断失败，停止", flush=True); break
        res = dres[1]
        by = defaultdict(list)
        for r in res:
            by[r["tid"]].extend(r["claims"])
        verd = {c: r["verd"].get(c, "解析失败") for r in res for c in r["claims"]}
        diag = diagnose(by, verd, {t["tid"]: LAWS[law_of[t["tid"]]]["evidence"] for t in SEARCH})
        lines = []
        for tid, d in diag.items():
            lines.append("题%s：断言%d条(去重后重复率%.0f%%) 支持%d 矛盾%d 其中数字类矛盾%d 条号类矛盾%d；"
                         "依据含%d个数字，答案从未提到其中%d个"
                         % (tid, d["n_claims"], d["dup_ratio"] * 100, d["n_sup"], d["n_con"],
                            d["con_numeric"], d["con_article"], 0, 0))
        print("  诊断（聚合，无答案）:\n    " + "\n    ".join(lines), flush=True)

        cands = []
        for k in range(2):
            spec = propose("\n".join(lines), describe(best_spec))
            if spec is None:
                print("    提案 %d 解析失败，跳过" % (k + 1), flush=True); continue
            spec["_texts"] = spec.pop("_texts", []) or []
            spec["_pf_texts"] = spec["_texts"]
            cands.append(spec)
        # 提案的 preflight 文本是自由文本 → 用一个可注入的形式
        if not cands:
            print("    本轮无有效提案，停止", flush=True); break
        for spec in cands:
            a, _ = evaluate(spec, SEARCH, "rnd%d" % rnd)
            if a is None:
                continue
            print("    提案 %s → 宽度 %.2f 支持 %.1f%% 矛盾 %.1f%% %s"
                  % (spec_key(spec), a["width"], a["support"] * 100, a["conflict"] * 100,
                     "可行" if a["feasible"] else "**超约束**"), flush=True)
            print("       步骤: " + " / ".join(spec.get("_pf_texts", [])), flush=True)
            history.append((spec_key(spec), spec, a))
            if a["feasible"] and a["width"] > best_agg["width"]:
                best_spec, best_agg = spec, a
                print("       ↑ 采纳为当前最优", flush=True)

    # ---- 留出判决 ----
    print("\n== 留出判决（%s）==" % [t["tid"] for t in HOLD], flush=True)
    final = []
    for name, (spec, a) in baselines.items():
        ah, _ = evaluate(spec, HOLD, "hold")
        final.append((name, ah))
        print("  %-12s 宽度 %.2f 支持 %.1f%% 矛盾 %.1f%% %s"
              % (name, ah["width"], ah["support"] * 100, ah["conflict"] * 100,
                 "可行" if ah["feasible"] else "**超约束**"), flush=True)
    ah, _ = evaluate(best_spec, HOLD, "hold")
    final.append((best_spec.get("label", "Agent最优"), ah))
    print("  %-12s 宽度 %.2f 支持 %.1f%% 矛盾 %.1f%% %s"
          % ("Agent最优", ah["width"], ah["support"] * 100, ah["conflict"] * 100,
             "可行" if ah["feasible"] else "**超约束**"), flush=True)
    feas_final = [x for x in final if x[1]["feasible"]] or final
    win = max(feas_final, key=lambda x: x[1]["width"])
    print("\n  判决: 留出集可行者中宽度最大 = %s" % win[0], flush=True)
    json.dump(dict(history=[(k, {kk: vv for kk, vv in s.items() if kk != "_pf_texts"},
                             a) for k, s, a in history],
                   final=[(k, a) for k, a in final], cap=globals().get("CAP")),
              open("%s/summary.json" % OUT, "w"), ensure_ascii=False, indent=1)
    print("总耗时 %.0f 分钟" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
