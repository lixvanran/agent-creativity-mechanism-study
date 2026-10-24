# -*- coding: utf-8 -*-
"""门控实验：新域（地方性政策）到底是不是**模型不饱和**的域？

这决定了整个「探索有价值」的论点能不能测。
指标：
  饱和度 = cos(直调rep1, 直调rep2) − cos(直调, 工作流)   （扣题域地板）
  宽度   = 去重并集大小（去重阈值取 0.70/0.75/0.80 报敏感度）
  质量   = 支持率    风险 = 矛盾率

对照组：法律域的饱和度均值 0.0483（18 题 × 2 采样）
判定：若新域饱和度显著高于法律域 → 说明模型在这些题上仍很确定 → 探索依然无用
      若新域饱和度接近 0 或更低 → 未饱和 → 探索可能有价值
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM                        # noqa: E402
from creativity_lab.metrics import _mat                      # noqa: E402
from creativity_lab.workflow import DEFAULT_SPEC, run_spec, spec_key  # noqa: E402
from creativity_lab.verify import (check_claims, extract_claims, score_of)  # noqa: E402

OUT = "runs/policy"
os.makedirs(OUT, exist_ok=True)
REPS = 2
ARMS = ("direct", "dual_fuse", "dual_select")
DATA = json.load(open("creativity_lab/data/policy_topics.json", encoding="utf-8"))
LAWS, TOPICS = DATA["laws"], DATA["topics"]
law_of = {t["tid"]: t["law"] for t in TOPICS}


def embed_rows(ts):
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    return _mat(LLM().embed(uniq))[idx]


def cos(a, b):
    M = embed_rows([a, b])
    return float(M[0] @ M[1])


def dedup_n(claims, thr):
    if not claims:
        return []
    M = embed_rows(claims)
    S = M @ M.T
    keep = []
    for i in range(len(claims)):
        if all(S[i, j] < thr for j in keep):
            keep.append(i)
    return [claims[i] for i in keep]


def gen(topic, arm, rep):
    llm = LLM()
    if arm == "direct":
        return llm.chat("问题：%s\n\n给出你的方案与理由，400字以内。" % topic["ask"],
                        model="MiniMax-M3", purpose="p_direct", min_ok=200)
    from creativity_lab.arms.dual import Dual
    return Dual("fuse" if arm == "dual_fuse" else "select").run(llm, topic, rep).text


def main():
    t0 = time.time()
    print("== 1. 生成 %d 题 × %d 臂 × %d 重复 ==" % (len(TOPICS), len(ARMS), REPS), flush=True)
    texts = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(gen, T, a, i): (T["tid"], a, i)
                for T in TOPICS for a in ARMS for i in range(1, REPS + 1)}
        for n, f in enumerate(as_completed(futs), 1):
            k = futs[f]
            try:
                texts["%s|%s|%d" % k] = f.result()
            except Exception as e:
                print("  ERR %s %s" % (k, str(e)[:50]), flush=True)
            if n % 8 == 0:
                print("  %d/%d (%.0fs)" % (n, len(futs), time.time() - t0), flush=True)
                json.dump(texts, open("%s/texts.json" % OUT, "w"), ensure_ascii=False, indent=1)
    json.dump(texts, open("%s/texts.json" % OUT, "w"), ensure_ascii=False, indent=1)

    print("\n== 2. 断言抽取 ==", flush=True)
    claims = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(extract_claims, LLM(), v): k for k, v in texts.items()}
        for n, f in enumerate(as_completed(futs), 1):
            claims[futs[f]] = f.result()
    json.dump(claims, open("%s/claims.json" % OUT, "w"), ensure_ascii=False, indent=1)
    print("  断言 %d 条，空抽取 %d 份" % (sum(len(v) for v in claims.values()),
                                       sum(1 for v in claims.values() if not v)), flush=True)

    print("\n== 3. 逐条核验 ==", flush=True)
    verd = {}
    for T in TOPICS:
        pool = sorted({c for k, cs in claims.items() if k.split("|")[0] == T["tid"] for c in cs})
        if not pool:
            continue
        v = check_claims(LLM(), T["ask"], LAWS[law_of[T["tid"]]]["evidence"], pool)
        verd.update(v)
        n = {x: sum(1 for y in v.values() if y == x) for x in ("支持", "矛盾", "未提及", "非主张")}
        print("  %s 断言 %2d → 支持 %2d / 矛盾 %2d / 未提及 %2d / 非主张 %2d"
              % (T["tid"], len(pool), n["支持"], n["矛盾"], n["未提及"], n["非主张"]), flush=True)
    json.dump(verd, open("%s/verdicts.json" % OUT, "w"), ensure_ascii=False, indent=1)

    print("\n== 4. 饱和度（扣题域地板）==", flush=True)
    sats = []
    for T in TOPICS:
        tid = T["tid"]
        d = sorted(k for k in texts if k.startswith(tid + "|direct"))
        s = sorted(k for k in texts if k.startswith(tid + "|dual_select"))
        if len(d) < 2 or not s:
            continue
        w_dd = cos(texts[d[0]], texts[d[1]])
        w_ds = float(np.mean([cos(texts[a], texts[b]) for a in d for b in s]))
        sats.append((tid, w_dd, w_ds, w_dd - w_ds))
        print("  %s  w_dd=%.4f  w_ds=%.4f  饱和度=%+.4f" % (tid, w_dd, w_ds, w_dd - w_ds),
              flush=True)
    if sats:
        m = float(np.mean([x[3] for x in sats]))
        print("\n  新域饱和度均值 %+.4f   （法律域 18 题对照：+0.0483）" % m, flush=True)
        print("  判定: %s" % ("**未饱和**（饱和度接近 0 或更低）→ 探索可能有价值"
                              if m < 0.03 else
                              "**仍饱和** → 该域探索依然无用，得换域"), flush=True)

    print("\n== 5. 三轴 ==", flush=True)
    by = defaultdict(lambda: defaultdict(list))
    for k, cs in claims.items():
        by[k.split("|")[0]][k.split("|")[1]].extend(cs)
    print("%-13s %8s %8s %9s %9s" % ("arm", "宽度.70", "宽度.75", "支持率", "矛盾率"))
    for a in ARMS:
        w70, w75, S, C, UN, CL, NM = [], [], 0, 0, 0, 0, 0
        for T in TOPICS:
            raw = by[T["tid"]].get(a, [])
            w70.append(len(dedup_n(raw, 0.70)))
            w75.append(len(dedup_n(raw, 0.75)))
            for c in dedup_n(raw, 0.75):
                CL += 1
                v = verd.get(c, "解析失败")
                S += v == "支持"; C += v == "矛盾"; UN += v == "未提及"; NM += v == "非主张"
        # ★★★★ 2026-10-24 更正（★ 第 1 层论证线 13:50Z 回源核出 · ★ 我方复核确认 ★★★★）★★
        # ★ 【分母口径】：★ 原来 `legal = max(CL - UN, 1)` ⇒ ★ 【排除「未提及」】★
        #   ★ ⇒ ★ 而我方【预注册 / A 篇正文 §3.7 / REPORT-DRILL-2026-10-18 第 90 行】用的
        #   ★   ★ 是【排除「非主张」】：★ `| direct | 324 | 117 | 1 | 39 | 0.4% |` ⇒ ★ 39 = 非主张数
        #   ★   ★ ⇒ 324 − 39 = 285 ⇒ ★ 1/285 = 0.35% ≈ 【0.4%】★ ★
        #   ★ ⇒ ★ 而【排除未提及】= 324 − 167 = 157 ⇒ ★ 1/157 = 0.64% ⇒ ★ ★ 【两者分母差 1.8 倍】★★ ★
        # ★ ⇒ ★ ★ 修正：★ 改为排除【非主张】⇒ ★ 与预注册与 A 篇正文【同口径】⇒ ★ 恢复跨组可比 ★★
        #   ★ ⇒ ★ ★ 【「未提及」不排除】★：★ 它是【判官没提到该断言】⇒ ★ 不在分母里【会虚高矛盾率】★★ ★
        legal = max(CL - NM, 1)
        _legal_un = max(CL - UN, 1)      # ★ 旧口径（★ 排除「未提及」）★ —— ★ 保留以便对照、★ 但【不用于判决】★★
        print("%-13s %8.2f %8.2f %8.1f%% %8.1f%%   (★ 断言 %d ｜ 分母[排除非主张] %d ｜ 旧口径[排除未提及] %d ★)"
              % (a, np.mean(w70), np.mean(w75), 100 * S / legal, 100 * C / legal,
                 CL, legal, _legal_un), flush=True)

    json.dump(dict(texts=texts, claims=claims, verdicts=verd,
                   saturation=[[t, a, b, c] for t, a, b, c in sats]),
              open("%s/summary.json" % OUT, "w"), ensure_ascii=False, indent=1)
    print("\n总耗时 %.0f 分钟" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
