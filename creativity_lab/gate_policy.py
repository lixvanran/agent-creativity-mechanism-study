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


# ★★★★ 2026-10-24 · ★ 判官健康度闸门（★ G-judge）★★★★ ★★
# ★ 起因：★ 第 1 层论证线 2026-10-24 转述 ⇒ ★ 「★ 若 verdicts.json 缺失或为空 ⇒ ★
# ★   每条断言的判定都落默认「解析失败」⇒ ★ 矛盾分子 = 0 ⇒ ★ 矛盾率显示成 0.0% ★
# ★   ⇒ ★ 那不是「没有矛盾」，那是【判官没跑】★ ★」
# ★ ⇒ ★ ★★ 我方同族确认（★ 回源 gate_policy.py:151 ★）：★ `v = verd.get(c, "解析失败")` ★
# ★   ★ ⇒ ★ 【verd 为空 ⇒ C=0 ⇒ 矛盾率 0.0%、且【支持率也 0.0%】⇒ ★ 看着像「完美」★★ ★★
# ★ ⇒ ★ ⇒ ★ ★★ 我方比对方多一处【更隐蔽】的形态 ★★ ★★
# ★   ★ 【只部分臂失败】时（★ 例：A 臂 100% 解析失败、B 臂健康 ★）⇒ ★ A 臂照常输出
# ★   ★ 「支持 0.0% / 矛盾 0.0%」⇒ ★ ★ 只看【全局】解析失败率会掩盖它 ★★★ ★★★
# ★ ⇒ ★ ⇒ ★ 落法：★ 闸门【按臂】分别算 + 【全局无任何真实判定】也 fail ★ ★
# ★ ⇒ ★ ★★ 闸门【不产出任何读数】：★ 它在写 summary.json 之前 exit ⇒ ★
# ★   ★ summary.json 根本不写出 ⇒ ★ 「矛盾率 0.0%」永远进不了交稿读数 ★★ ★
MAX_PARSE_FAIL_RATE = 0.10      # ★ 沿用本项目「通道健康度 ≥ 0.9」的既有约定 ★
GATE_EXIT = 10                   # ★ 专属退出码：★ 与「跑批失败」区分开 ★


def judge_health_gate(cl_by_arm, verd):
    """★ 判官健康度闸门（★ 纯函数 · ★ 不碰网络 · ★ 不读文件 ★）

    ★ 输入：
    ★   cl_by_arm : {arm: [该臂去重后的断言文本, ...]}   ★ 分母按【臂】给 ★
    ★   verd      : {断言文本: 判定}   ★ ★ 「未提及」「非主张」都是【合法判定】★★
    ★   ★ ⇒ ★ 只有「解析失败」才是【没判】⇒ ★ 闸门只锁在它上面 ★★ ★
    ★ 返回：(ok, rows)
    ★   ok   : bool   ★ False ⇒ 必须 exit(GATE_EXIT) 且【不产出任何读数】★
    ★   rows : 每臂一行的绝对数与比率（★ 一切比率必配绝对分母 ★）
    """
    rows, total_judged, total_n = [], 0, 0
    for arm in sorted(cl_by_arm):
        cs = cl_by_arm[arm]
        n = len(cs)
        n_pf = sum(1 for c in cs if verd.get(c, "解析失败") == "解析失败")
        n_judged = n - n_pf
        total_n += n
        total_judged += n_judged
        rows.append({"arm": arm, "n_claims": n, "n_judged": n_judged,
                     "n_parse_failed": n_pf,
                     "parse_fail_rate": (n_pf / n) if n else None,
                     "n_verd_keys": len(verd)})
    # ── 闸门三问（★ 逐条可核 · ★ 每条都有绝对分母 ★）──────────────────
    reasons = []
    if total_n == 0:
        reasons.append("★ 无任何断言 ⇒ 判官根本没跑（或断言抽取为空）★")
    if total_n > 0 and total_judged == 0:
        reasons.append("★ 无任何判定（★ 全部落「解析失败」★）⇒ 那是【判官没跑】，"
                        "不是「没有矛盾」★")
    for r in rows:
        if r["n_claims"] == 0:
            reasons.append("★ 臂 %s 断言数为 0 ⇒ 不能报该臂的矛盾率★" % r["arm"])
        elif r["parse_fail_rate"] > MAX_PARSE_FAIL_RATE:
            reasons.append("★ 臂 %s 解析失败率 %.1f%% > %.0f%%（★ %d/%d 条 ★）"
                           % (r["arm"], 100 * r["parse_fail_rate"],
                              100 * MAX_PARSE_FAIL_RATE, r["n_parse_failed"], r["n_claims"]))
    return (not reasons), {"rows": rows, "reasons": reasons,
                            "max_parse_fail_rate": MAX_PARSE_FAIL_RATE,
                            "total_n_claims": total_n, "total_n_judged": total_judged}


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
    rc = write_report(texts, claims, verd, sats, by, OUT)
    print("\n总耗时 %.0f 分钟" % ((time.time() - t0) / 60))
    return rc


def write_report(texts, claims, verd, sats, by, out_dir):
    """★ 三轴读数 + 落盘（★ ★ 闸门在这里之前 ⇒ 失败则【不产出任何读数】★★）

    ★ 返回：0 = 正常；GATE_EXIT = 判官健康度不达标（★ summary.json 未写出 ★）
    """
    print("%-13s %8s %8s %9s %9s" % ("arm", "宽度.70", "宽度.75", "支持率", "矛盾率"))
    # ── ★★ 判官健康度闸门（★ 必须在【任何读数】产出之前 ★）★★ ──────────
    #   ★ 落法：★ ① 收集各臂去重断言集（★ 只算集合、不算任何率 ★）
    #   ★        ② 跑闸门 ⇒ 不达标 ⇒ 打印 + return GATE_EXIT（★ summary.json 不写出 ★）
    #   ★        ③ 通过后才进入读数计算 ★
    _cl_probe = {}
    for _a in ARMS:
        _probe = []
        for _T in TOPICS:
            for _c in dedup_n(by[_T["tid"]].get(_a, []), 0.75):
                _probe.append(_c)
        _cl_probe[_a] = _probe
    _ok, _gate = judge_health_gate(_cl_probe, verd)
    if not _ok:
        print("\n✘✘ 判官健康度闸门不通过（★ GATE_EXIT=%d ★）⇒ 【不产出任何读数】★★ ★" % GATE_EXIT)
        for _r in _gate["reasons"]:
            print("   · %s" % _r)
        for _r in _gate["rows"]:
            print("   · %-13s 断言 %d ｜ 已判 %d ｜ 解析失败 %d ｜ 失败率 %s"
                  % (_r["arm"], _r["n_claims"], _r["n_judged"], _r["n_parse_failed"],
                     ("%.1f%%" % (100 * _r["parse_fail_rate"])) if _r["parse_fail_rate"] is not None else "n/a"))
        print("   ⇒ ★ 那不是「没有矛盾」⇒ ★ 那是【判官没跑 / 没判全】★★ ★")
        return GATE_EXIT
    print("\n✔ 判官健康度闸门通过（★ 已判 %d / 断言 %d ｜ 各臂解析失败率 ≤ %.0f%% ★）"
          % (_gate["total_n_judged"], _gate["total_n_claims"], 100 * MAX_PARSE_FAIL_RATE))

    _denoms = {}
    for a in ARMS:
        w70, w75, S, C, UN, CL, NM = [], [], 0, 0, 0, 0, 0
        _cl_arm = []
        for T in TOPICS:
            raw = by[T["tid"]].get(a, [])
            w70.append(len(dedup_n(raw, 0.70)))
            w75.append(len(dedup_n(raw, 0.75)))
            for c in dedup_n(raw, 0.75):
                CL += 1
                _cl_arm.append(c)
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
        # ★ ★★★ 2026-10-24 · 改成【两个口径都报 + 各自标注】★★ ★★★
        #   ★ 起因：★ 第 1 层论证线 14:20Z ⇒ ★ 「★ 口径修正本身【也是一次口径变更】★ ⇒ ★
        #   ★   ★ 若只报一个数，★ 读者【无法判断用的是哪个】⇒ ★ ⇒ 那个数【无法被复核】★★ ★
        #   ★   ★ ⇒ ★ ★ 两个都报，★ 读者【至少能自己判断这个数来自哪个口径】★★ ★★
        # ★ 口径 A = 断言数 − 非主张（★ A 篇 §3.7 / DRILL §4c / 预注册 ★）⇒ ★ 【判决用、★ 外部可比】★★
        # ★ 口径 B = 断言数 − 未提及（★ 旧 gate_policy:152 ★）⇒ ★ 【对照用、★ 与历史批连续】★★
        _legal_B = max(CL - UN, 1)
        print("%-13s %8.2f %8.2f %8.1f%% %8.1f%%   (★ 断言 %d ｜ A[排除非主张] %d ｜ B[排除未提及] %d ★)"
              % (a, np.mean(w70), np.mean(w75), 100 * S / legal, 100 * C / legal,
                 CL, legal, _legal_B), flush=True)
        _n_pf = sum(1 for c in _cl_arm if verd.get(c, "解析失败") == "解析失败")
        _denoms.setdefault(a, {"n_claims": CL, "n_support": S, "n_contradiction": C,
                               "n_unmentioned": UN, "n_nonclaim": NM,
                               "n_parse_failed": _n_pf, "n_judged": CL - _n_pf,
                               "parse_fail_rate": (_n_pf / CL) if CL else None,
                               "legal_denominator_A": legal, "legal_denominator_B": _legal_B,
                               "denominator_A_spec": "★ 断言数 − 非主张（★ A 篇 §3.7 / DRILL §4c / 预注册 ★）★",
                               "denominator_B_spec": "★ 断言数 − 未提及（★ 旧 gate_policy:152 ★）★",
                               "support_rate_A": 100 * S / legal, "contradiction_rate_A": 100 * C / legal,
                               "support_rate_B": 100 * S / _legal_B, "contradiction_rate_B": 100 * C / _legal_B,
                               "caveat": "★ 二者差 ~1.8 倍 ⇒ ★ 引用时【必须写清用的是哪个】★ ⇒ ★ 判决用 A ★"})

    json.dump(dict(texts=texts, claims=claims, verdicts=verd,
                   saturation=[[t, a, b, c] for t, a, b, c in sats],
                   denominators=_denoms,
                   judge_health=_gate,
                   denominators_note="★ ★ 两个口径都报：★ A=排除非主张（★ 判决用 ★）｜ ★ B=排除未提及（★ 对照用 ★）★ ★ ⇒ ★ 引用时必须写清用的是哪个 ★★ ★"),
              open("%s/summary.json" % out_dir, "w"), ensure_ascii=False, indent=1)
    return 0            # ★ ★ 0 = 正常产出（★ 闸门通过 ⇒ 有读数 ★）★★


if __name__ == "__main__":
    sys.exit(main() or 0)
