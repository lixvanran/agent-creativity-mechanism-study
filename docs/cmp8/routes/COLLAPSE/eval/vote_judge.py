# -*- coding: utf-8 -*-
"""逐条对照表判官（vote 式集合比较）—— B-2a 的判官侧实现。

> 2026-10-22 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/vote_judge.py`
> 设计：`routes/COLLAPSE/eval/NOAUTH-ARMS.md` §4
> 依据：协议 §4.4（B3：best-of-N 只能由**外部核验器**选）、§1.7（族签名跨臂匹配）、
#      ToT 的 value/vote 之分（vote = 集合比较，value = 打分）

## 为什么要做"集合比较"而不是"打分"

- 我们的主判据是**维度数**（集合的大小）⇒ 臂间比较就该是**集合差**，
  不是两个分数相减。
- **打分会把集合差压回单一分数**：一旦给分，"多了一个维度"和"少了一个维度"
  可以互相抵消 ⇒ **看起来没差**。⇒ 净增益必须是**双边**（`A_only` 与 `B_only` 分别报）。

## 两种模式（都要报，差异本身是信息）

| 模式 | 做法 | 风险 |
|---|---|---|
| **`independent`（默认）** | 两臂**分别**跑卡片判定 ⇒ 集合比较在代码里做 | 无跨臂传播；但**两臂的判官是同一次调用链**（提示词相同）|
| **`joint`** | 一次调用同时看两份答案，让它分别列出再比较 | ★ **跨臂传播风险**：判官看到 A 之后可能对 B 放宽/收紧 |

⇒ ⇒ **两个模式都跑**：若 `joint` 的净增益与 `independent` **不一致** ⇒ 差异来自
"同时看到两份" ⇒ 说明**跨臂传播确实存在** ⇒ 报告必须以 `independent` 为准。

## K 票版本（可选）

同一份答案独立判定 K 次（每次**打乱断言顺序**），每条结论按**票数**入集：
≥ 2/3 票才入集。⇒ **单次裁定**与**多数投票**并列报：
- 一致 ⇒ 读数稳；
- 单次裁定高、投票后塌 ⇒ **判官是权威在起作用**，不是维度在起作用。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import vd_anchor_out as V  # noqa: E402

JOINT_Q = """下面有两份**各自独立**的答案（A、B），以及一份「依据条目 / 结论空间」清单。

问题：
{ask}

依据条目与结论空间（编号即结论编号）：
{ev}

答案 A：
{a}

答案 B：
{b}

请**分别**列出 A 与 B 各自承重的结论（每条写出它支撑的结论编号），
然后做**集合比较**。不要比较哪份"更好"，不要给分。

输出（严格 JSON，不要别的内容）：
{{"a": [{{"c": <结论编号>, "text": "<该结论的一句话>"}}],
 "b": [{{"c": <结论编号>, "text": "<该结论的一句话>"}}]}}

随后按下列口径输出计数（全部给绝对值，不要比率）：
{{"A_n": <A 的承重结论数>, "B_n": <B 的承重结论数>,
 "inter_n": <两者都有的结论数>,
 "A_only": [<只 A 有的结论编号>...], "B_only": [<只 B 有的结论编号>...],
 "net": <|A_only| - |B_only|>,
 "note": "一句说明：两臂对同一批结论的承重是否不同"}}

注意：
- **不许打分**（不要 0-10 分、不要"更好/更差"）。
- **不许跨臂传播**：先各自列完，再做比较；A 的判定不许影响 B 的判定。
"""


def _conclusion_set(llm: V.LLM, task: Dict[str, Any], answer: str,
                    judge_model: str) -> Dict[str, Any]:
    """单臂的承重结论集合（走**原判据**，与 `measure.py` 等价 ⇒ 读数可比）。"""
    ev_items = V.evidence_items_from_dev(task)
    ev_text = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev_items))
    claims = V.extract_claims(llm, answer, judge_model)
    if not claims:
        return {"claims": [], "conclusions": set(), "n_cards": 0, "n_dimensions": 0}
    r = V.judge_in_channel(llm, task.get("ask", ""), ev_text, claims, judge_model)
    return {"claims": claims, "conclusions": set(r["conclusions_supported"]),
            "n_cards": r["n_cards"], "n_dimensions": r["n_dimensions"],
            "cards_kept": r["cards_kept"]}


def set_compare(a: Sequence[Any], b: Sequence[Any]) -> Dict[str, Any]:
    """集合比较（**双边**，不合并成一个净值了事）。"""
    sa, sb = set(a), set(b)
    only_a, only_b = sorted(sa - sb), sorted(sb - sa)
    return {
        "A_n": len(sa), "B_n": len(sb), "inter_n": len(sa & sb),
        "union_n": len(sa | sb),
        "A_only": only_a, "B_only": only_b,
        "net": len(only_a) - len(only_b),
        "net_two_sided": {"added": len(only_a), "lost": len(only_b)},
        "jaccard": round(len(sa & sb) / max(len(sa | sb), 1), 4),
    }


def independent_compare(llm: V.LLM, task: Dict[str, Any], ans_a: str, ans_b: str,
                        judge_model: str) -> Dict[str, Any]:
    ra = _conclusion_set(llm, task, ans_a, judge_model)
    rb = _conclusion_set(llm, task, ans_b, judge_model)
    cmp_res = set_compare(sorted(ra["conclusions"]), sorted(rb["conclusions"]))
    cmp_res["mode"] = "independent"
    cmp_res["A_n_cards"] = ra["n_cards"]
    cmp_res["B_n_cards"] = rb["n_cards"]
    cmp_res["A_n_dims"] = ra["n_dimensions"]
    cmp_res["B_n_dims"] = rb["n_dimensions"]
    return cmp_res


def joint_compare(llm: V.LLM, task: Dict[str, Any], ans_a: str, ans_b: str,
                  judge_model: str) -> Dict[str, Any]:
    ev_items = V.evidence_items_from_dev(task)
    ev_text = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev_items))
    raw = llm.chat(JOINT_Q.format(ask=task.get("ask", ""), ev=ev_text,
                                  a=ans_a[:3000], b=ans_b[:3000]),
                   model=judge_model, temp=0.0, max_tokens=V.MM_TOKEN_FLOOR,
                   budgets=(12000, 16000), min_ok=20, purpose="vote_joint")
    obj: Dict[str, Any] = {}
    for ln in (raw or "").splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            d = json.loads(ln)
        except Exception:                          # noqa: BLE001
            continue
        if isinstance(d, dict) and ("a" in d or "A_n" in d):
            obj = d
    a_set = {x.get("c") for x in (obj.get("a") or []) if isinstance(x, dict)}
    b_set = {x.get("c") for x in (obj.get("b") or []) if isinstance(x, dict)}
    a_set = {x for x in a_set if x is not None}
    b_set = {x for x in b_set if x is not None}
    cmp_res = set_compare(sorted(a_set), sorted(b_set))
    cmp_res["mode"] = "joint"
    cmp_res["parse_ok"] = bool(obj)
    cmp_res["reported"] = {k: obj.get(k) for k in
                            ("A_n", "B_n", "inter_n", "A_only", "B_only", "net", "note")}
    return cmp_res


def vote_k(llm: V.LLM, task: Dict[str, Any], answer: str, judge_model: str,
           k: int = 3, seed: int = 0) -> Dict[str, Any]:
    """K 票：每次**打乱断言顺序**独立判定 ⇒ 每条结论按票数入集。"""
    ev_items = V.evidence_items_from_dev(task)
    ev_text = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev_items))
    claims = V.extract_claims(llm, answer, judge_model)
    votes: Dict[Any, int] = {}
    rounds: List[Dict[str, Any]] = []
    rng = random.Random(seed)
    for r in range(k):
        order = list(claims)
        rng.shuffle(order)
        res = V.judge_in_channel(llm, task.get("ask", ""), ev_text, order, judge_model)
        cs = set(res["conclusions_supported"])
        rounds.append({"round": r + 1, "n_dims": res["n_dimensions"],
                       "conclusions": sorted(cs)})
        for c in cs:
            votes[c] = votes.get(c, 0) + 1
    thresh = (k // 2) + 1
    kept = sorted([c for c, v in votes.items() if v >= thresh])
    return {"mode": "vote_k", "k": k, "threshold": thresh,
            "votes": {str(c): v for c, v in sorted(votes.items())},
            "conclusions_kept": kept, "n_kept": len(kept),
            "rounds": rounds,
            "single_round_dims": rounds[0]["n_dims"] if rounds else 0,
            "note": "单次裁定 vs 多数投票：若投票后塌 ⇒ 判官是权威在起作用"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default=V.DEV_DIR)
    ap.add_argument("--task", required=True)
    ap.add_argument("--a", required=True, help="答案 A 的文件")
    ap.add_argument("--b", required=True, help="答案 B 的文件")
    ap.add_argument("--judge-vendor", default="minimax")
    ap.add_argument("--judge-model", default="MiniMax-M3.1-Flash-Preview")
    ap.add_argument("--vote-k", type=int, default=0, help=">0 则额外跑 K 票版本")
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    devset = V.load_devset(args.dev)
    task = V.dev_task(devset, args.task)
    a = open(args.a, encoding="utf-8").read()
    b = open(args.b, encoding="utf-8").read()
    llm = V.LLM(args.judge_vendor, args.judge_model)

    rep: Dict[str, Any] = {"task_id": args.task, "judge_model": args.judge_model,
                            "judge_vendor": args.judge_vendor,
                            "a_file": args.a, "b_file": args.b}
    rep["independent"] = independent_compare(llm, task, a, b, args.judge_model)
    rep["joint"] = joint_compare(llm, task, a, b, args.judge_model)
    rep["mode_agreement"] = {
        "net_independent": rep["independent"]["net"],
        "net_joint": rep["joint"]["net"],
        "same_sign": (rep["independent"]["net"] == 0 and rep["joint"]["net"] == 0) or
                     (rep["independent"]["net"] * rep["joint"]["net"] > 0),
        "same_value": rep["independent"]["net"] == rep["joint"]["net"],
        "note": "不一致 ⇒ 存在跨臂传播 ⇒ 以 independent 为准",
    }
    if args.vote_k > 0:
        rep["vote_a"] = vote_k(llm, task, a, args.judge_model, args.vote_k)
        rep["vote_b"] = vote_k(llm, task, b, args.judge_model, args.vote_k)
    rep["calls"] = llm.log.summary()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
