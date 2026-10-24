# -*- coding: utf-8 -*-
"""批次 U1-2026-10-21 · 被测侧跑批（**全部走 OpenRouter**）。

臂：B0_direct / B1_eq_calls / A_fixed / C_T2 ｜ 题：U1 ｜ R=3
⚠️ **路线 B 不在本批**（v2 的 30 维权重尚未训练 ⇒ 跑 w=0 无意义）⇒ 如实声明缺席。
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, "/workspace/lab")
sys.path.insert(0, "/workspace/lab/routes/A")
sys.path.insert(0, "/workspace/lab/routes/C")
sys.path.insert(0, "/workspace/lab/batch-U1")

import u1_lib as U

# ★ 路线 A 的执行器用 PRIMARY_MODEL 决定模型 ⇒ 被测侧必须是 OpenRouter 的模型
os.environ["PRIMARY_MODEL"] = U.OR_MODEL

from route_a import run_route, run_b_arm            # noqa: E402
from executor import run_episode                    # noqa: E402
import params as CP                                 # noqa: E402


C_JUDGE_Q = """下面是一份「依据条目列表」、一份「结论空间」、一个问题，以及若干条待核验的陈述。

第一步：这条陈述是**只复述了问题里已经给出的情形**，还是**断言**？
判据：只要陈述里含有**超出问题本身**的信息（数字/阈值/名称/规则/主体关系/比较/归类），
就当它是断言；**由问题里的数值加上依据规则推导出的结论，是断言，不是复述**。
只复述情形的，答「非主张」。

第二步：对断言，判断它与依据条目的关系，只回答一个词：
- 「支持」：依据条目明确认可或蕴含该条。改写、简称、换词但含义相同，也算支持。
- 「矛盾」：依据条目明确讲了与之相反的内容（含数字对不上、阈值不同、方向相反）。
- 「未提及」：依据条目没有讲到，或讲的是别的事。**不确定时一律答「未提及」。**

第三步：若第二步判为「支持」或「矛盾」，在同一个词后面用一个空格写出
支持它的那一条依据的**编号**（如：支持 3）。若有多条支持，写第一个即可。

一行一条，顺序对应，不要解释，不要补充。

问题：
{ask}

依据条目：
{ev}

结论空间（本题可支撑的结论清单）：
{ct}

待核验的陈述：
{claims}
"""

OUT = os.path.join(U.BATCH, "runs")
R_REPS = 3
# ★ 成本闸门：整批 OpenRouter token 上限（事前写死）⇒ 超了**停**，不降级、不换模型
TOKEN_CAP = int(os.environ.get("U1_TOKEN_CAP", "900000"))


_TOK = {"n": 0}


def tok_guard(llm):
    """累计 token 超上限 ⇒ 抛停。"""
    _TOK["n"] += llm.n_tokens
    if _TOK["n"] > TOKEN_CAP:
        raise SystemExit("★ 成本闸门：累计 token %d > 上限 %d ⇒ 停止（不降级、不换模型）"
                         % (_TOK["n"], TOKEN_CAP))


def save(arm, rep, answer, meta, extra=None):
    d = os.path.join(OUT, arm)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "rep%d.answer.md" % rep), "w", encoding="utf-8") as f:
        f.write(answer)
    m = dict(meta or {})
    if extra:
        m.update(extra)
    with open(os.path.join(d, "rep%d.meta.json" % rep), "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2, sort_keys=True)


def main():
    ONLY = os.environ.get("U1_ONLY_ARMS", "").split(",") if os.environ.get("U1_ONLY_ARMS") else None
    START_REP = int(os.environ.get("U1_START_REP", "1"))
    pack = U.load_u1()
    ask = pack["ask"]
    ev_items = U.evidence_items(pack)
    ct = U.conclusion_space(pack)
    print("题：%s" % ask)
    print("依据包：%d 条原子事实 ｜ C_t：%d 条 ｜ 依据包哈希 %s"
          % (len(ev_items), len(ct), U.sha([e["text"] for e in ev_items])))
    print("被测模型：%s @ %s" % (U.OR_MODEL, U.OR_BASE))
    print("=" * 70)

    results = {}

    # ── 路线 A（先跑，用来定 B1 的 K）────────────────────────────
    for rep in range(1, R_REPS + 1):
        if ONLY and "A_fixed" not in ONLY: break
        llm = U.OpenRouterLLM()
        log = []
        ctx = dict(arm_id="A_fixed", task_id="U1", rep=rep, run_id="U1-2026-10-21",
                   prompt_version="routeA-v1-2026-10-21",
                   model_requested=U.OR_MODEL,
                   devset_id="TEST-U1", devset_hash=U.sha([e["text"] for e in ev_items]),
                   evidence_pack_version="user4-q1-v1")
        r = run_route(ask, ev_items, llm=llm, log=log, ctx=ctx)
        cont = U.generation_prompt_contamination(r["gen_prompts"])
        meta = dict(r["meta"])
        meta["contamination_generation_side"] = cont
        meta["contamination_ok"] = (len(cont) == 0)
        meta["vendor_side"] = "openrouter"
        meta["judge_same_vendor"] = False
        save("A_fixed", rep, r["answer"], meta,
             dict(n_api_calls_llm=llm.n_api_calls, n_tokens_llm=llm.n_tokens,
                  usage=llm.usage, gen_prompt_count=len(r["gen_prompts"]),
                  pool_size=len(r["pool"])))
        tok_guard(llm)
        print("A_fixed rep%d: calls=%d tokens=%d chars=%d 污染=%s"
              % (rep, llm.n_api_calls, llm.n_tokens, len(r["answer"]),
                 "无" if not cont else cont))
        results.setdefault("A_fixed", []).append(dict(
            n_calls=llm.n_api_calls, n_tokens=llm.n_tokens, answer=r["answer"]))

    if results.get("A_fixed"):
        K = sorted(x["n_calls"] for x in results["A_fixed"])[len(results["A_fixed"]) // 2]
        print("⇒ B1 的 K = 路线A 三次调用数的中位数 = %d" % K)
    else:
        K = int(os.environ.get("U1_B1_K", "16"))
        print("⇒ 跳过 A ⇒ B1 的 K 用预置值 %d" % K)

    # ── B0 直调 / B1 等调用数 ──────────────────────────────────
    for kind, arm in ([("B0", "B0_direct"), ("B1", "B1_eq_calls")] if not ONLY else []):
        for rep in range(1, R_REPS + 1):
            llm = U.OpenRouterLLM()
            log = []
            ctx = dict(arm_id=arm, task_id="U1", rep=rep, run_id="U1-2026-10-21",
                       prompt_version="routeA-v1-2026-10-21",
                       model_requested=U.OR_MODEL,
                       devset_id="TEST-U1", devset_hash=U.sha([e["text"] for e in ev_items]))
            r = run_b_arm(ask, ev_items, llm=llm, log=log, ctx=ctx, kind=kind,
                          K=K if kind == "B1" else None)
            meta = dict(r["meta"])
            meta["contamination_generation_side"] = []
            meta["contamination_ok"] = True
            meta["vendor_side"] = "openrouter"
            meta["judge_same_vendor"] = False
            meta["b1_K"] = K if kind == "B1" else None
            save(arm, rep, r["answer"], meta,
                 dict(n_api_calls_llm=llm.n_api_calls, n_tokens_llm=llm.n_tokens,
                      usage=llm.usage, pool_size=len(r["pool"])))
            tok_guard(llm)
            print("%s rep%d: calls=%d tokens=%d chars=%d"
                  % (arm, rep, llm.n_api_calls, llm.n_tokens, len(r["answer"])))

    # ── C_T2（路线 C 默认拓扑）─────────────────────────────────
    theta = CP.default_theta()
    for rep in range(START_REP, R_REPS + 1):
        if ONLY and "C_T2" not in ONLY: break
        llm = U.OpenRouterLLM()

        def verifier(ask_, evidence, claims, _llm=None):
            """C 的**臂内**核验（工作流的一部分 ⇒ 走 OpenRouter，与生成同厂商）。

            ⚠️ 提示词含**结论空间 `C_t`**（核验侧看得到结论空间是允许的；MERGE 看不到）。
            ⇒ 与路线 A 的臂内判官**不同**（A 的 CHECK_Q 不含 `C_t`，它自己承认是 A-1）
            ⇒ **两臂的「经核验成立」节口径不同** ⇒ 这正是**测量必须独立于工作流**的原因。
            """
            if not claims:
                return {}
            lst = "\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(claims))
            evs = "\n".join("%d. %s" % (i + 1, e["text"]) for i, e in enumerate(ev_items))
            cts = "\n".join("%d. %s" % (i + 1, c["text"]) for i, c in enumerate(ct))
            q = C_JUDGE_Q.format(ask=ask_, ev=evs, ct=cts, claims=lst)
            raw = llm.chat(q, model=U.OR_MODEL, temp=0.0, max_tokens=4000,
                           budgets=(6000,), min_ok=len(claims), purpose="C_judge")
            out = {}
            lines = [x.strip() for x in (raw or "").splitlines() if x.strip()]
            for i, c in enumerate(claims):
                ln = lines[i] if i < len(lines) else ""
                m = re.search(r"(非主张|支持|矛盾|未提及)", ln)
                out[c] = m.group() if m else "未核验"
            return out

        topic = dict(task_id="U1", ask=ask,
                     evidence="\n".join("%d. %s" % (i + 1, e["text"])
                                        for i, e in enumerate(ev_items)),
                     tid="U1")
        res = run_episode(topic, "T2", theta, llm=llm, verifier=verifier, max_calls=14)
        ans = res.get("answer") or ""
        save("C_T2", rep, ans,
             dict(arm_id="C_T2", task_id="U1", rep=rep, run_id="U1-2026-10-21",
                  model_requested=U.OR_MODEL, vendor_side="openrouter",
                  judge_same_vendor=False, n_api_calls=llm.n_api_calls,
                  n_tokens=llm.n_tokens, stage_log=res.get("stage_log"),
                  n_claims_internal=len(res.get("claims", [])),
                  theta=theta, topology="T2",
                  contamination_generation_side=[], contamination_ok=True,
                  internal_verifier="lexical_stub__NOT_the_measurement"),
             dict(usage=llm.usage))
        tok_guard(llm)
        print("C_T2 rep%d: calls=%d tokens=%d chars=%d"
              % (rep, llm.n_api_calls, llm.n_tokens, len(ans)))

    print("=" * 70)
    print("被测侧完成。产物在 %s" % OUT)
    with open(os.path.join(U.BATCH, "arms_done.json"), "w", encoding="utf-8") as f:
        json.dump(dict(b1_K=K, R=R_REPS, model=U.OR_MODEL, base=U.OR_BASE,
                       total_tokens=_TOK["n"], token_cap=TOKEN_CAP,
                       ct_len=len(ct), facts=len(ev_items),
                       evidence_hash=U.sha([e["text"] for e in ev_items])),
                  f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print("耗时 %.1f 分钟" % ((time.time() - t0) / 60))
