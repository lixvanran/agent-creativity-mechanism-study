#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 跨组联合检查：第四组的 K=3 候选是**真分叉**还是**假分叉**？

借用**第三组**（creativity-lab）的成熟口径：
  extract_claims（把文本里的可判真假陈述逐条列出）+ dedup_sem（语义去重 thr=0.75）
  ⇒ 并集大小 = "该组触及的不同考虑数"（第三组称"探索量"）

三档对照（分离"采样多样性"与"候选分叉多样性"）：
  ① A 臂 3 次重复        —— 完全独立采样（无状态、无候选）        ⇒ 基线
  ② 工作流臂不同 rep 各 1 个候选 —— 不同采样 + 不同状态
  ③ 工作流臂**同 rep 内**的 3 个候选 —— 同状态、提示只差"你是第几次尝试"
     ⇒ ③ − ① = **候选分叉的净增量**；若 ③ ≈ ① ⇒ K=3 是**假分叉**

⚠️ 零生成成本：复用第四组 v5 已落盘的候选正文（runs/arch5_compare.jsonl）。
"""
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
G3 = "/workspace/mech-study"                      # 第三组仓（creativity-lab）
sys.path.insert(0, G3)
sys.path.insert(0, os.path.join(G3, "creativity_lab"))

from creativity_lab.client import LLM              # noqa: E402
from creativity_lab.verify import extract_claims   # noqa: E402
from creativity_lab.metrics import _mat            # noqa: E402

SRC = os.path.join(HERE, "runs", "arch5_compare.jsonl")
OUT = os.path.join(HERE, "runs", "fork_check.json")
WORKERS = 4
THR = 0.75

llm = LLM()


def embed_rows(ts):
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    return _mat(llm.embed(uniq))[idx]


def dedup_sem(claims, thr=THR):
    """★ 第三组口径：语义去重（同一件事的不同说法只留一条）。"""
    if not claims:
        return []
    M = embed_rows(claims)
    S = M @ M.T
    keep = []
    for i in range(len(claims)):
        if all(S[i, j] < thr for j in keep):
            keep.append(i)
    return [claims[i] for i in keep]


FAIL_BOX = []          # ★ 失败必须显式记录（不许静默变成"没有 claims"）


def claims_of(text, key=None, tries=3):
    """抽 claims。★ 失败**显式记录**并重试 ⇒ 不许静默变成空列表。"""
    if not text or not text.strip():
        return []
    last = None
    for t in range(tries):
        try:
            cs = extract_claims(llm, text)
            if cs:
                return cs
            last = "empty_claims"
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
            time.sleep(4 * (t + 1))          # 退避（MiniMax 429）
    FAIL_BOX.append({"key": str(key), "error": last})
    return []


def main():
    recs = [json.loads(l) for l in open(SRC, encoding="utf-8") if l.strip()]
    # 任务表：每个 (样本, 候选idx) → 文本
    tasks = []          # (key, kind, tid, tag, arm, cand_idx, text)
    for r in recs:
        tid, tag, arm = r.get("topic_id"), r.get("tag"), r.get("arm")
        if r.get("error") or not (r.get("text") or "").strip():
            continue
        if arm == "A":
            tasks.append(((tid, tag, arm, 0), "A", tid, tag, arm, 0, r["text"]))
        else:
            for c in r.get("candidates") or []:
                if c.get("error") or not (c.get("text") or "").strip():
                    continue
                tasks.append(((tid, tag, arm, c["idx"]), "CAND", tid, tag, arm,
                              c["idx"], c["text"]))
    print("claims 抽取任务数：%d（候选 %d + A 臂 %d）"
          % (len(tasks), sum(1 for t in tasks if t[1] == "CAND"),
             sum(1 for t in tasks if t[1] == "A")))

    claims = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(claims_of, t[6]): t for t in tasks}
        done = 0
        for fu in as_completed(futs):
            t = futs[fu]
            try:
                claims[t[0]] = fu.result()
            except Exception as e:
                claims[t[0]] = []
                FAIL_BOX.append({"key": str(t[0]), "error": "%s: %s" % (type(e).__name__, e)})
                print("  ⚠️ claims 失败 %s: %s" % (t[0], e))
            done += 1
            if done % 10 == 0:
                print("  ... %d/%d" % (done, len(tasks)), flush=True)

    # ---- 三档并集 ----
    A_by_topic = defaultdict(list)          # tid -> [claims per rep]
    C_rep_by_topic = defaultdict(list)      # tid -> [claims per rep]（工作流臂，每 rep 取第 1 个候选）
    C_within = defaultdict(list)            # (tid,tag) -> [claims per candidate]
    for r in recs:
        tid, tag, arm = r.get("topic_id"), r.get("tag"), r.get("arm")
        if arm == "A" and not r.get("error"):
            A_by_topic[tid].append(claims.get((tid, tag, arm, 0), []))
        elif str(arm).startswith("WF-v5") and not r.get("error"):
            cands = [c for c in (r.get("candidates") or [])
                     if not c.get("error") and (c.get("text") or "").strip()]
            if cands:
                c0 = cands[0]
                C_rep_by_topic[tid].append(claims.get((tid, tag, arm, c0["idx"]), []))
                C_within[(tid, tag, arm)].append([claims.get((tid, tag, arm, c["idx"]), [])
                                                  for c in cands])

    rows = []
    for tid in sorted(set(list(A_by_topic) + list(C_rep_by_topic))):
        a_raw = A_by_topic.get(tid, [])
        c_raw = C_rep_by_topic.get(tid, [])
        u_a = dedup_sem([x for cs in a_raw for x in cs])
        u_c = dedup_sem([x for cs in c_raw for x in cs])
        # 同 rep 内的 3 候选
        within = []
        for (t2, tag, arm), lists in C_within.items():
            if t2 == tid:
                within.extend(dedup_sem([x for cs in lists for x in cs]) for _ in [0])
        w_lists = []
        for (t2, tag, arm), lists in C_within.items():
            if t2 == tid:
                w_lists.append(dedup_sem([x for cs in lists for x in cs]))
        u_w = dedup_sem([x for wl in w_lists for x in wl])
        rows.append({"tid": tid,
                     "A_reps": len(a_raw), "A_union": len(u_a),
                     "WF_reps": len(c_raw), "WF_rep_union": len(u_c),
                     "WF_within_union_mean": (round(sum(len(x) for x in w_lists) / len(w_lists), 2)
                                              if w_lists else None),
                     "WF_within_union_max": max([len(x) for x in w_lists], default=None)})
    res = {"threshold": THR, "n_claims_tasks": len(tasks), "rows": rows,
           "n_failed_claims": len(FAIL_BOX), "failures": FAIL_BOX,
           "per_topic_detail": {}}
    for tid in sorted(set(list(A_by_topic) + list(C_rep_by_topic))):
        det = {}
        for (t2, tag, arm), lists in sorted(C_within.items()):
            if t2 != tid:
                continue
            per = [len(dedup_sem([x for cs in lists for x in cs])) for lists in [lists]]
            # 每个候选自己的 claims 数 + 同 rep 内并集
            u = dedup_sem([x for cs in lists for x in cs])
            det["%s#%s" % (arm, tag)] = {
                "n_cand": len(lists),
                "claims_per_cand": [len(cs) for cs in lists],
                "union_within_rep": len(u),
            }
        res["per_topic_detail"][tid] = det

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 78)
    print("★ 候选分叉检查（第三组口径：claims 抽取 + 语义去重 thr=%.2f）" % THR)
    print("=" * 78)
    print("%-6s %10s %10s %14s %12s" % ("题", "①A并集", "②WF跨rep", "③WF同rep并集", "③/①"))
    for r in rows:
        ratio = (r["WF_within_union_mean"] / r["A_union"]) if r["A_union"] else None
        r["ratio_3_over_1"] = round(ratio, 3) if ratio else None
        print("%-6s %10s %10s %14s %12s" % (
            r["tid"], r["A_union"], r["WF_rep_union"],
            r["WF_within_union_mean"], r["ratio_3_over_1"]))
    print("\n(③ 越高 ⇒ 候选分叉越有效；③ ≈ ① ⇒ K=3 是**假分叉**，"
          "说明'你是第几次尝试'那个提示没起作用)")
    print("\n★ claims 抽取失败 %d / %d（显式列出，不静默归零）"
          % (len(FAIL_BOX), len(tasks)))
    for f in FAIL_BOX[:10]:
        print("   ✗ %s : %s" % (f["key"], f["error"]))
    print("\n[out] %s" % OUT)


if __name__ == "__main__":
    main()
