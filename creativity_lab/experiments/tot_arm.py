#!/usr/bin/env python3
"""**ToT 原版臂 + ADHD 臂**（★ 把前人的零件接进来，不自创）

> 落点：`creativity_lab/experiments/tot_arm.py`
> 预注册：`docs/cmp8/routes/COLLAPSE/eval/PREREG-TOT-ARM.md`（**事前**写死）
> 量尺：`creativity_lab/metrics_ext.py`（Vendi / self-BLEU / Distinct-n，**照抄公开定义**）
>
> ## ★ 这份脚本的定位：**接线**，不是造零件
> - 生成侧：`arms/dual.py::_branch_specs` + `prompts.py::BRANCH_ASK`（**本仓已有**）
> - 评估侧：`prompts.py::VALUE_Q` / `VOTE_Q`（**ToT 的 value / vote 组件，注释里就写着**）
> - 选择侧：`gates/base.py::Select`（**已核 = ToT `method_select` 的等价物**）
> - 外部基线：`cmp8/creativity_lab/adhd_repro.py::run_adhd`（**A2 臂真代码**）
> ⇒ ⇒ **没有一行是"我发明的算法"**；只有 IO 的拼接与读数。
>
> ## ★ 臂（6 臂，5 个共享同一次发散 ⇒ 选择侧是唯一变量）
> | 臂 | 生成 | 评估 | 选择 | 调用数 |
> |---|---|---|---|--:|
> | `nosel_b5` | 5 支 | 无 | 无 | 5 |
> | `tot_greedy_b5` | 共享 5 支 | value | greedy | 5+5 |
> | `tot_vote_b5` | 共享 5 支 | vote | greedy | 5+1 |
> | `tot_sample_b5` | 共享 5 支 | value | sample(加权随机) | 5+5 |
> | `tot_greedy_b1` | **1 支** | value | greedy | 1+1 |
> | `adhd_b5` | ★ ADHD 真代码（30 想法 → top3） | 内置 | 内置 | 11–12 |
>
> ## ★★ 一个必须写清的口径事实（★ 我自己发现的预注册缺陷，已在跑前修正）
> `adhd_b5` 产出的是 **30 个短想法**（再选 top3 深化），其它臂是 **5 支完整答复**。
> ⇒ ⇒ **"面宽"本身跨臂不可比**（n 不同、文本长度差一个量级）
> ⇒ ⇒ ★ **可比的是「选择器消耗率」**（比值型，跨 n 可比）：
>      ToT：1 − Vendi(选后1支)/Vendi(选前5支)
>      ADHD：1 − Vendi(top3 深化后)/Vendi(30 想法)
> ⇒ ⇒ ⇒ **H-T4 改为比"选择器消耗率"，不比对"面宽"本身。**
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.arms.dual import _branch_specs          # noqa: E402
from creativity_lab.client import DEFAULT_EFFORT, LLM      # noqa: E402
from creativity_lab.gates.base import Select                # noqa: E402
from creativity_lab.metrics import effective_rank, modes    # noqa: E402
from creativity_lab.metrics_ext import (distinct_n, pick_representativeness,   # noqa: E402
                                         self_bleu, selector_consumption,
                                         vendi_score)
from creativity_lab.prompts import BRANCH_ASK, OUT_SPEC, VALUE_Q, VOTE_Q  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARMS = ["nosel_b5", "tot_greedy_b5", "tot_vote_b5", "tot_sample_b5",
        "tot_greedy_b1", "adhd_b5"]

# ── ADHD 真代码：按文件路径加载（★ 仓里有两个同名 creativity_lab 包，不能直接 import）──
def _load_adhd():
    p = os.path.join(ROOT, "cmp8", "creativity_lab", "adhd_repro.py")
    spec = importlib.util.spec_from_file_location("adhd_repro_ext", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ──────────────────────────────────────────────────────────────
# 读数：一把尺子不够 ⇒ 多把并排，让分歧暴露（★ metrics_ext 的教训）
# ──────────────────────────────────────────────────────────────
def read_set(arts: List[str], vecs: List[List[float]]) -> Dict[str, Any]:
    """一组文本/embedding 的**全部**多样性读数（全部零判官）。"""
    if len(arts) < 2:
        return {"valid": False, "reason": "too_few(%d)" % len(arts)}
    return {
        "valid": True,
        "n": len(arts),
        "vendi": round(vendi_score(vecs), 4),
        "self_bleu": round(self_bleu(arts), 4),
        "distinct_2": round(distinct_n(arts, 2), 4),
        "effective_rank": round(effective_rank(vecs), 4),
        "effective_rank_per_n": round(effective_rank(vecs) / len(arts), 4),
        "modes": modes(vecs),
    }


def lexical_sharing(arts: List[str]) -> float:
    """分支两两 2-gram Jaccard 中位数（独立性下界）。"""
    if len(arts) < 2:
        return 0.0
    from creativity_lab.metrics import keywords
    ks = [keywords(a) for a in arts]
    vals = []
    for i in range(len(arts)):
        for j in range(i + 1, len(arts)):
            u = len(ks[i] | ks[j])
            vals.append((len(ks[i] & ks[j]) / u) if u else 0.0)
    vals.sort()
    return float(vals[len(vals) // 2])


# ──────────────────────────────────────────────────────────────
# 评估器（ToT 的 value / vote）
# ──────────────────────────────────────────────────────────────
_JSON = re.compile(r"\{.*\}", re.S)


def parse_score(raw: str) -> float:
    """从 VALUE_Q 的输出里抽 score（1–10）。**抽不出记 None，不当 0。**"""
    if not raw:
        return None
    m = _JSON.search(raw)
    if not m:
        return None
    try:
        v = json.loads(m.group(0)).get("score")
        return float(v) if v is not None else None
    except Exception:
        return None


def parse_pick(raw: str, n: int) -> int:
    """从 VOTE_Q 的输出里抽 pick（1..n，1-based）。**抽不出记 None。**"""
    if not raw:
        return None
    m = _JSON.search(raw)
    if not m:
        return None
    try:
        v = json.loads(m.group(0)).get("pick")
        i = int(v) - 1
        return i if 0 <= i < n else None
    except Exception:
        return None


def eval_value(llm, arts: List[str], model: str, workers: int) -> Tuple[List[float], int]:
    """ToT 的 `get_values`：**每支一次独立调用**。返回 (分数列表, 调用数)。"""
    if not arts:
        return [], 0
    prompts = [VALUE_Q.format(cand=a) for a in arts]
    n0 = len(llm.rec)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        outs = list(ex.map(lambda p: llm.chat(p, model=model, purpose="tot_value",
                                              min_ok=20, max_tokens=1200), prompts))
    scores = [parse_score(o) for o in outs]
    # ★ 抽不出的**不当 0**（那会把"没读出来"变成"质量 0"）⇒ 用中位填补并计数
    miss = sum(1 for s in scores if s is None)
    if miss:
        good = [s for s in scores if s is not None]
        med = sorted(good)[len(good) // 2] if good else 5.0
        scores = [med if s is None else s for s in scores]
    return scores, len(llm.rec) - n0


def eval_vote(llm, arts: List[str], model: str, workers: int) -> Tuple[List[float], int]:
    """ToT 的 `vote`：**一次比较多个候选，选一个** ⇒ 返回 one-hot 分数。"""
    if not arts:
        return [], 0
    block = "\n\n".join("【%d】%s" % (i + 1, a) for i, a in enumerate(arts))
    n0 = len(llm.rec)
    raw = llm.chat(VOTE_Q.format(arts=block, n=len(arts)), model=model,
                   purpose="tot_vote", min_ok=20, max_tokens=1500)
    pick = parse_pick(raw, len(arts))
    scores = [0.0] * len(arts)
    if pick is not None:
        scores[pick] = 1.0
    else:
        scores[0] = 1.0          # ★ 解析失败 ⇒ 记"选了第 1 支"并单独报解析失败数
    return scores, len(llm.rec) - n0


# ──────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", default="creativity_lab/data/topics_2x2.json")
    ap.add_argument("--only-tid", default="")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--model", default="MiniMax-M3")
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--b", type=int, default=5, help="分支数（ToT 的 b）")
    ap.add_argument("--out", default="runs/tot-arm-2026-10-24")
    a = ap.parse_args()

    ROOTD = ROOT
    topics = json.load(open(os.path.join(ROOTD, a.topics), encoding="utf-8"))
    if isinstance(topics, dict):
        topics = topics.get("topics", topics.get("items", []))
    if a.only_tid:
        keep = set(a.only_tid.split(","))
        topics = [t for t in topics if t.get("tid") in keep]
    arms = [x for x in a.arms.split(",") if x]

    llm = LLM()
    emb_llm = LLM()
    outdir = os.path.join(ROOTD, a.out)
    os.makedirs(outdir, exist_ok=True)
    logp = os.path.join(outdir, "..", "logs", "tot-arm.log")
    os.makedirs(os.path.dirname(logp), exist_ok=True)
    logf = open(logp, "a", encoding="utf-8")

    def log(msg):
        print(msg, flush=True)
        logf.write(msg + "\n")
        logf.flush()

    log("题：%s｜rep=%d｜臂：%s｜effort=%s｜b=%d"
        % ([t["tid"] for t in topics], a.reps, arms, a.effort, a.b))

    adhd = _load_adhd() if "adhd_b5" in arms else None
    groups: List[Dict[str, Any]] = []
    t_start = time.time()

    for topic in topics:
        for rep in range(1, a.reps + 1):
            g: Dict[str, Any] = {"tid": topic["tid"], "rep": rep, "arms": {}}
            specs_all = _branch_specs()
            rng = random.Random(20261024 + rep)

            # ── 共享生成（nosel / tot_greedy / tot_vote / tot_sample 同一批分支）──
            shared: Dict[str, Any] = {}
            need_shared = any(x in arms for x in
                              ("nosel_b5", "tot_greedy_b5", "tot_vote_b5", "tot_sample_b5"))
            if need_shared:
                specs = [specs_all[i % len(specs_all)] for i in range(a.b)]
                prompts = [BRANCH_ASK.format(
                    topic=topic["ask"], frame_name=f[0]["name"], frame_text=f[0]["text"],
                    persona=f[2], spec=OUT_SPEC,
                    extra="\n直接写出**完整的答复本身**，不要写判断片段。")
                    for f in specs]
                n0 = len(llm.rec)
                t0 = time.time()
                with ThreadPoolExecutor(max_workers=a.workers) as ex:
                    outs = list(ex.map(
                        lambda i: llm.chat(prompts[i], model=specs[i][1],
                                           purpose="diverge:shared:%s" % specs[i][1]),
                        range(len(prompts))))
                arts = [o for o in outs if o.strip()]
                shared = {"arts": arts, "n_expected": len(specs), "n_arts": len(arts),
                          "n_calls": len(llm.rec) - n0,
                          "secs": round(time.time() - t0, 1),
                          "models": [s[1] for s in specs],
                          "frames": [s[0]["name"] for s in specs]}
                if len(arts) >= 2:
                    vecs = emb_llm.embed(list(arts))
                    shared["read"] = read_set(arts, vecs)
                    shared["read"]["lexical_sharing"] = round(lexical_sharing(arts), 4)
                    shared["vecs"] = vecs

            # ── 逐臂 ──
            for arm in arms:
                n0 = len(llm.rec)
                t0 = time.time()
                d: Dict[str, Any] = {}
                if arm in ("nosel_b5",) and shared:
                    d = dict(shared)
                    d["n_arts"] = len(shared.get("arts") or [])
                    d["n_calls"] = shared["n_calls"]
                    d["picked"] = None
                    d["selector_consumption"] = None      # 无选择器 ⇒ 不适用
                    d["pick_representativeness"] = None
                elif arm in ("tot_greedy_b5", "tot_sample_b5", "tot_vote_b5") and shared:
                    arts = shared["arts"]
                    if arm == "tot_vote_b5":
                        scores, nc = eval_vote(llm, arts, a.model, a.workers)
                    else:
                        scores, nc = eval_value(llm, arts, a.model, a.workers)
                    sel = Select(mode=("sample" if arm == "tot_sample_b5" else "greedy"),
                                 rng=random.Random(20261024 + rep))
                    idx = sel(scores, k=1)
                    pick = idx[0] if idx else 0
                    vecs = shared.get("vecs") or emb_llm.embed(list(arts))
                    v_cand = vendi_score(vecs)
                    d = {"arts": arts, "n_expected": shared["n_expected"],
                         "n_arts": len(arts), "n_calls": shared["n_calls"] + nc,
                         "secs": round(time.time() - t0, 1),
                         "models": shared["models"], "frames": shared["frames"],
                         "read": shared.get("read"),
                         "scores": scores, "picked": pick,
                         "picked_text": arts[pick] if arts else "",
                         "selector_consumption": round(selector_consumption(v_cand), 4),
                         "pick_representativeness": round(
                             pick_representativeness(vecs[pick],
                                                     [v for i, v in enumerate(vecs) if i != pick]), 4)}
                elif arm == "tot_greedy_b1":
                    frm, _fm, _fp = specs_all[0]      # ★ _branch_specs 返回 (frame, model, persona)
                    n0b = len(llm.rec)
                    raw = llm.chat(BRANCH_ASK.format(
                        topic=topic["ask"], frame_name=frm["name"], frame_text=frm["text"],
                        persona=_fp, spec=OUT_SPEC,
                        extra="\n直接写出**完整的答复本身**，不要写判断片段。"),
                        model=a.model, purpose="tot_b1")
                    arts = [raw] if raw and raw.strip() else []
                    scores, nc = ([], 0)
                    if arts:
                        scores, nc = eval_value(llm, arts, a.model, a.workers)
                    d = {"arts": arts, "n_expected": 1, "n_arts": len(arts),
                         "n_calls": len(llm.rec) - n0b, "secs": round(time.time() - t0, 1),
                         "scores": scores, "picked": 0,
                         "picked_text": arts[0] if arts else "",
                         "selector_consumption": 0.0,
                         "pick_representativeness": 1.0}
                elif arm == "adhd_b5" and adhd:
                    n0a = len(llm.rec)          # ★ 记账用 llm.rec 的增量（★ 不采信 meta.n_calls：
                    rendered, meta = adhd.run_adhd(topic["ask"], model=a.model, llm=llm,   #   meta 会漏掉失败路径）
                                                  frames_n=5, ideas_per_frame=6, top_k=3,
                                                  seed=20261024 + rep)
                    n_calls_real = len(llm.rec) - n0a
                    ideas = meta.get("ideas") or []
                    d = {"arts": ideas, "n_expected": 30, "n_arts": len(ideas),
                         "n_calls": n_calls_real,
                         "n_calls_meta": int(meta.get("n_calls", 0)),
                         "secs": round(time.time() - t0, 1),
                         "rendered_chars": len(rendered),
                         "frames": meta.get("frames"),
                         "picked": None,
                         "adhd_topk": 3}
                    if len(ideas) >= 2:
                        vecs = emb_llm.embed(list(ideas))
                        d["read"] = read_set(ideas, vecs)
                        d["read"]["lexical_sharing"] = round(lexical_sharing(ideas), 4)
                        d["vendi_ideas"] = d["read"]["vendi"]
                    if rendered.strip():
                        rv = emb_llm.embed([rendered])[0]
                        d["rendered_vendi1"] = 1.0
                        d["read_rendered"] = {"chars": len(rendered)}
                else:
                    d = {"valid": False, "reason": "arm_not_run"}

                d["secs"] = round(time.time() - t0, 1)
                g["arms"][arm] = d
                r = d.get("read") or {}
                log("  %s r%d %-14s 支=%s/%s Vendi=%s selfBLEU=%s 消耗率=%s 调用=%s (%.0fs)"
                    % (topic["tid"], rep, arm, d.get("n_arts"), d.get("n_expected"),
                       r.get("vendi"), r.get("self_bleu"),
                       d.get("selector_consumption"), d.get("n_calls"), d["secs"]))

            with open(os.path.join(outdir, "group_%s_r%d.json" % (topic["tid"], rep)),
                      "w", encoding="utf-8") as f:
                json.dump(g, f, ensure_ascii=False, indent=1, sort_keys=True)
            groups.append(g)

    # ── manifest ──
    tot = sum((g["arms"].get(x, {}) or {}).get("n_calls", 0) for g in groups for x in arms)
    failed = sum(1 for c in llm.rec if not getattr(c, "has_content", True) or getattr(c, "finish_reason", "") == "exception")
    empty = sum(1 for c in llm.rec if not (getattr(c, "content_len", 0) or 0))
    man = {"health": {"n_groups": len(groups), "n_arms": len(arms), "arms": arms,
                       "n_calls_total": tot, "n_calls_failed": failed,
                       "n_calls_empty": empty, "model": a.model, "effort": a.effort,
                       "n_branch_deficit": sum(
                           1 for g in groups for x in arms
                           if (g["arms"].get(x, {}) or {}).get("n_arts", 0) <
                           (g["arms"].get(x, {}) or {}).get("n_expected", 0)),
                       "channel_health": round(1 - (failed + empty) / max(tot, 1), 4),
                       "secs_total": round(time.time() - t_start, 1)},
           "groups": groups}
    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1, sort_keys=True)
    # ★★ 落盘 calllog（★ 可审计性硬要求）：
    #   没有 calllog ⇒ **无法独立于执行地重算通道健康度**（`fix_calllog_fields.py` 依赖它）
    #   ⇒ 这是我今晚抓到的教训：manifest 里的 health 是执行时算的，**不能用来验证自己**
    with open(os.path.join(outdir, "calllog.jsonl"), "w", encoding="utf-8") as f:
        for c in llm.rec:
            f.write(json.dumps(c.__dict__, ensure_ascii=False) + "\n")
    log("通道健康：%s" % json.dumps(man["health"], ensure_ascii=False))
    log("✔ manifest 落盘：%s" % os.path.join(outdir, "manifest.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
