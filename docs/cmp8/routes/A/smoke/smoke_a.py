# -*- coding: utf-8 -*-
"""路线 A 的可执行性冒烟（**只验证流程能跑通、提示词能解析，不产出任何实验结论**）。

约束（任务书原文）：
- MiniMax 订阅端点，`OPENROUTER_BASE_URL=https://api.minimaxi.com/v1`；
  `PRIMARY_MODEL=MiniMax-M3.1-Flash-Preview`；
- **禁止任何 OpenRouter 调用**（本脚本启动即断言 base url 不含 openrouter.ai）；
- **总调用数 ≤ 20**（chat + embedding 都算；超过即 abort）；
- **不得使用用户四道题**（U1–U4）—— 本脚本用**自造**的诊断题；
- 冒烟不产出任何实验结论：日志里不写任何"哪条臂更好"的判断。

⚠️ **第二轮返工的改动**（对应复核报告）：
- **F12**：跑的是**预注册拓扑**（第一轮 4 个承载面 + 第二轮 2 个承载面，
  `collapse_mult=1.0`）⇒ FA5/FA6 第一次对活模型跑过；另加一道**小题**（1 槽位、无第二轮），
  在**活体**上验证「多任务共享同一个 LLM 对象时，预算按任务计」（F1）。
- **F13**：`openrouter_used` 由**实际调用 URL** 计算（不再硬编码字面量）。
- **F15**：日志记录**实际使用的模型**（共享 client 会按 FALLBACKS 静默降级 —— 实测确实降级过）。
- **F7**：日志里的自检项**不许**因为一个任务作废就崩掉（第一版就是在这里崩的）。

⚠️ **本次冒烟的 token 预算用的是「修订前」的 40 000**（= 实测发现预注册拓扑装不下的那个值）：
   一个 rep 实测用掉 46 217 token ⇒ 超过 40 000 ⇒ **DS-01 样本作废**（协议 E4）。
   ⇒ 这条**如实记在日志里**；修订后的 60 000 **未经活体验证**（本轮 API 预算已用尽），
     详见 `DESIGN.md` §3.5 的「预注册修订记录」与 §10。

用法：
    # 跑活体冒烟（会发起 API 调用）
    MINIMAX_SUBSCRIPTION_KEY=... OPENROUTER_BASE_URL=https://api.minimaxi.com/v1 \
    PRIMARY_MODEL=MiniMax-M3.1-Flash-Preview python3 smoke_a.py
    # 只从**已落盘的记录**重建日志（**0 次 API 调用**；脚本修好之后补齐日志产物）
    python3 smoke_a.py --summarize-only
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))      # route_a / facets 在上一级目录
sys.path.insert(0, "/workspace/lab")

# ---------------------------------------------------------------- 端点断言（硬约束）
BASE = os.environ.get("OPENROUTER_BASE_URL", "").rstrip("/")
assert BASE == "https://api.minimaxi.com/v1", \
    "被测侧端点必须是 MiniMax 订阅端点，当前=%r" % BASE
assert "openrouter.ai" not in BASE, "禁止 OpenRouter"
os.environ.setdefault("PRIMARY_MODEL", "MiniMax-M3.1-Flash-Preview")

from route_a import MeteredLLM, run_task, save_run    # noqa: E402

# ---------------------------------------------------------------- 自造诊断题（非 U1–U4）
# DS-01 跑**预注册拓扑**：第一轮 FA1–FA4（4 个承载面）+ 第二轮 FA5–FA6（2 个承载面），
#        collapse_mult = 1.0（预注册值；N4 **恒定执行**，该值只做诊断量）。
# DS-02 跑**小题**（1 槽位、无第二轮）：在活体上验证「共享 LLM 对象的多任务不被卡死」。
DIAG = [
    dict(
        tid="DS-01",
        topology="preregistered_4plus2",
        ask="某市居民用水阶梯价：第一档每月 0–18 吨，每吨 3.5 元；超过 18 吨的部分每吨 5 元。"
            "某户当月用水 24 吨，应缴水费多少元？",
        evidence=[
            dict(id="EV-DS01-01", text="阶梯价第一档为每月 0–18 吨的部分，每吨 3.5 元。"),
            dict(id="EV-DS01-02", text="超过 18 吨的部分，每吨按 5 元计收。"),
            dict(id="EV-DS01-03", text="阶梯价按实际用量分档累加计算，不是全部水量都适用最高档单价。"),
        ],
        # ⚠️ max_tokens=40000 = **修订前**的预注册值（本次跑的就是它 ⇒ DS-01 作废）
        cfg=dict(round1_facets=["FA1", "FA2", "FA3", "FA4"],
                 round2_facets=["FA5", "FA6"],
                 max_calls=24, max_tokens=40000, max_claims=48,
                 extract_cap=8, verify_batch=12, collapse_mult=1.0),
    ),
    dict(
        tid="DS-02",
        topology="small_1slot_no_round2",
        ask="某快递规定：普通件 10 公斤以内每件 12 元；超出部分每公斤加收 3 元。"
            "生鲜件不得保价，含液体时另付 20 元包装费。"
            "寄一件 8 公斤的生鲜件（含液体）应付多少元？该件是否可以保价？",
        evidence=[
            dict(id="EV-DS02-01", text="普通件在 10 公斤以内按每件 12 元计收。"),
            dict(id="EV-DS02-02", text="超过 10 公斤的部分，每公斤加收 3 元。"),
            dict(id="EV-DS02-03", text="生鲜件不得办理保价。"),
            dict(id="EV-DS02-04", text="生鲜件内含液体时，应另付 20 元包装费。"),
        ],
        cfg=dict(round1_facets=["FA1"], round2_facets=[],
                 max_calls=24, max_tokens=40000, max_claims=48,
                 extract_cap=8, verify_batch=12, collapse_mult=1.0),
    ),
]

GLOBAL_CALL_CAP = 20
RUNS_ROOT = "/workspace/lab/routes/RUNS"


def _read_runs():
    """从 RUNS 目录读回各题的产物（`--summarize-only` 用；**0 次 API 调用**）。"""
    out = []
    for t in DIAG:
        ap = os.path.join(RUNS_ROOT, "A_fixed", t["tid"], "rep1.answer.md")
        mp = os.path.join(RUNS_ROOT, "A_fixed", t["tid"], "rep1.meta.json")
        if not (os.path.exists(ap) and os.path.exists(mp)):
            continue
        meta = json.load(open(mp, encoding="utf-8"))
        answer = open(ap, encoding="utf-8").read()
        out.append(dict(tid=t["tid"], topology=t["topology"], meta=meta,
                        answer=answer, pool=[], verdicts={},
                        cfg=t["cfg"], runs=(ap, mp)))
    return out


def build_summary(results, usage, log, elapsed, total_calls, total_tokens, written):
    summary = dict(
        purpose="可执行性冒烟（不产出任何实验结论）",
        endpoint=BASE, primary_model=os.environ.get("PRIMARY_MODEL"),
        # ⚠️ F13：由**实际调用 URL** 计算，不是硬编码字面量
        openrouter_used=any("openrouter.ai" in (u.get("url") or "") for u in usage),
        endpoints_seen=sorted(set(u.get("url") or "" for u in usage)),
        models_seen=sorted(set(u.get("model") or "" for u in usage)),
        model_fallback_observed=sorted(set(u.get("model") or "" for u in usage)
                                       - {os.environ.get("PRIMARY_MODEL")}),
        global_call_cap=GLOBAL_CALL_CAP,
        total_api_calls=total_calls, total_tokens=total_tokens,
        n_logical_calls=len(log), elapsed_sec=round(elapsed, 1),
        usage=usage,
        tasks=[dict(tid=r["tid"], topology=r["topology"], cfg=r.get("cfg"),
                    meta=r["meta"], n_pool_items=len(r.get("pool", [])),
                    n_claims_extracted=len(r.get("pool", [])),
                    answer=r["answer"]) for r in results],
        runs_written=[list(w) for w in written],
        checks={},      # 只放**布尔**自检项（便于「全部为真」判定）
        counters={},    # 数值型读数
        invalidated_samples=[],
    )
    # ---- 自检项
    all_prompts = [e["prompt"] for e in log]
    summary["checks"]["prompts_parse_all_nonempty"] = all(len(p.strip()) > 0 for p in all_prompts)
    summary["checks"]["no_openrouter_in_prompts_or_endpoints"] = (
        "openrouter.ai" not in BASE
        and not any("openrouter.ai" in p for p in all_prompts)
        and not summary["openrouter_used"])
    summary["checks"]["all_api_urls_are_minimax"] = all(
        (u.get("url") or "").startswith("https://api.minimaxi.com/v1") for u in usage)
    ev_leak = 0
    for t in DIAG:
        for it in t["evidence"]:
            for p in all_prompts:
                if it["text"] in p and "依据条目" not in p:
                    ev_leak += 1
    summary["checks"]["evidence_not_in_generation_prompts"] = (ev_leak == 0)
    summary["counters"]["evidence_leak_count"] = ev_leak
    # 作废样本（协议 E4：超预算 ⇒ 样本作废并计数）
    import re as _re
    for r in results:
        m = r["meta"]
        if m.get("over_budget_count"):
            reason = m.get("budget_error") or "预算溢出"
            mm = _re.search(r"已用\s*(\d+)\s*/\s*上限\s*(\d+)", reason)
            summary["invalidated_samples"].append(dict(
                tid=r["tid"], reason=reason,
                tokens_used=int(mm.group(1)) if mm else m.get("n_tokens"),
                token_cap=int(mm.group(2)) if mm else m.get("max_tokens"),
                n_calls=m.get("n_calls"), n_tokens=m.get("n_tokens"),
                note="预算溢出的样本**作废并计数**（协议 E4）；不是被截断后照常算"))
        elif len((r["answer"] or "").strip()) < 50:
            summary["invalidated_samples"].append(
                dict(tid=r["tid"], reason="答案 < 50 字（协议 E2）",
                     n_calls=m.get("n_calls"), n_tokens=m.get("n_tokens")))
    summary["checks"]["no_sample_invalidated"] = (not summary["invalidated_samples"])
    summary["checks"]["every_task_has_parsed_verdicts"] = all(
        (r["meta"].get("n_pool") or 0) == 0
        or (r["meta"].get("n_parsefail") or 0) < (r["meta"].get("n_pool") or 0)
        for r in results)
    summary["checks"]["within_global_call_cap"] = (total_calls <= GLOBAL_CALL_CAP)
    # F1：第二题（共享同一个 LLM 对象）不得被前序题的 token 用量卡死
    summary["checks"]["multitask_budget_is_per_task"] = (
        len(results) < 2
        or all(r["meta"].get("over_budget_count", 0) == 0 for r in results[1:]))
    # F12：预注册拓扑的**第二轮**必须真的发生了（FA5/FA6 对活模型跑过）
    # ⚠️ 判据取自**调用日志**（而不是 meta）：样本若因预算作废，meta 里没有 round2_executed，
    #    但 A_resample_FA5/FA6 这两次调用**确实对活模型发生过**。
    purposes = [e.get("purpose", "") for e in log]
    summary["checks"]["preregistered_topology_fa5_fa6_called"] = (
        "A_resample_FA5" in purposes and "A_resample_FA6" in purposes)
    summary["counters"]["n_resample_fa5_fa6_calls"] = sum(
        1 for p in purposes if p in ("A_resample_FA5", "A_resample_FA6"))
    prereg = [r for r in results if r["topology"] == "preregistered_4plus2"]
    summary["checks"]["preregistered_topology_round2_executed_in_meta"] = (
        bool(prereg) and all(r["meta"].get("round2_executed") is True for r in prereg))
    # F14：整份答案的字数上限
    summary["checks"]["every_answer_within_char_cap"] = all(
        (r["meta"].get("answer_chars") or 0) <= 400 for r in results)
    # F5：输出契约（RUNS/…）必须真的写了
    summary["checks"]["runs_outputs_written"] = all(
        os.path.exists(a) and os.path.exists(b) for a, b in written) and bool(written)
    return summary


def write_outputs(summary, log, usage, out_dir):
    with open(os.path.join(out_dir, "smoke_usage.json"), "w", encoding="utf-8") as f:
        json.dump(usage, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "smoke_calls.jsonl"), "w", encoding="utf-8") as f:
        for i, e in enumerate(log, 1):
            f.write(json.dumps(dict(i=i, purpose=e["purpose"], prompt=e["prompt"],
                                    output=e["output"], n_api_calls=e["n_api_calls"],
                                    n_tokens=e["n_tokens"]), ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "smoke_log.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "smoke_log.txt"), "w", encoding="utf-8") as f:
        f.write("路线 A · 可执行性冒烟日志\n")
        f.write("（本文件只记录「流程能否跑通、提示词能否解析」，**不含任何实验结论**）\n\n")
        f.write("端点        : %s\n" % BASE)
        f.write("主模型      : %s\n" % os.environ.get("PRIMARY_MODEL"))
        f.write("实际用到的模型: %s\n" % (summary["models_seen"] or "（无）"))
        if summary["model_fallback_observed"]:
            f.write("⚠️ 发生过降级（共享 client 的 FALLBACKS）: %s\n"
                    % summary["model_fallback_observed"])
        f.write("OpenRouter  : %s（由 %d 条实际调用 URL 计算，非硬编码）\n"
                % ("未使用" if not summary["openrouter_used"] else "**被使用**", len(usage)))
        f.write("总调用数    : %d / 上限 %d\n" % (summary["total_api_calls"], GLOBAL_CALL_CAP))
        f.write("总 token    : %d\n" % summary["total_tokens"])
        if summary.get("elapsed_sec"):
            f.write("耗时        : %.1f s\n" % summary["elapsed_sec"])
        else:
            f.write("耗时        : （重建模式：不测耗时）\n")
        f.write("逻辑调用数  : %d\n" % summary["n_logical_calls"])
        f.write("写出的产物  : %s\n" % ("；".join("%s, %s" % (w[0], w[1]) for w in summary["runs_written"]) or "（无）"))
        f.write("\n逐次 API 调用的 token 分解（prompt / completion / model）：\n")
        for u in usage:
            f.write("  #%-3d prompt=%-7d completion=%-7d total=%-7d model=%s\n"
                    % (u["i"], u["prompt_tokens"], u["completion_tokens"], u["total_tokens"],
                       u.get("model")))
        f.write("\n")
        f.write("自检：\n")
        for k, v in summary["checks"].items():
            f.write("  - %-42s %s\n" % (k, v))
        f.write("\n读数（数值）：\n")
        for k, v in summary["counters"].items():
            f.write("  - %-42s %s\n" % (k, v))
        if summary["invalidated_samples"]:
            f.write("\n⚠️ 作废样本（协议 E2/E4）：\n")
            for s in summary["invalidated_samples"]:
                f.write("  - %s：%s（calls=%s tokens=%s）\n"
                        % (s["tid"], s["reason"], s["n_calls"], s["n_tokens"]))
        f.write("\n逐题结果：\n")
        for r in summary["tasks"]:
            f.write("\n---- %s（%s）----\n" % (r["tid"], r["topology"]))
            f.write("cfg: %s\n" % json.dumps(r.get("cfg"), ensure_ascii=False))
            f.write(json.dumps(r["meta"], ensure_ascii=False, indent=2))
            f.write("\n答案：\n%s\n" % r["answer"])
        f.write("\n---- 逐次调用（prompt / output）----\n")
        for i, e in enumerate(log, 1):
            f.write("\n===== call %d · %s =====\n" % (i, e["purpose"]))
            f.write("--- prompt ---\n%s\n" % e["prompt"])
            f.write("--- output ---\n%s\n" % (e["output"] or "(空)"))


def main() -> int:
    out_dir = HERE
    summarize_only = "--summarize-only" in sys.argv
    written = []
    results = []
    log = []
    usage = []
    total_calls = 0
    total_tokens = 0
    elapsed = 0.0
    started = time.time()

    if summarize_only:
        # ---- 从**已落盘的记录**重建（0 次 API 调用）
        up = os.path.join(out_dir, "smoke_usage.json")
        cp = os.path.join(out_dir, "smoke_calls.jsonl")
        usage = json.load(open(up, encoding="utf-8")) if os.path.exists(up) else []
        if os.path.exists(cp):
            log = [json.loads(l) for l in open(cp, encoding="utf-8") if l.strip()]
        total_calls = len(usage)
        total_tokens = sum(u.get("total_tokens", 0) for u in usage)
        results = _read_runs()
        written = [r["runs"] for r in results]
        print("== summarize-only：从落盘记录重建（0 次 API 调用） ==")
    else:
        llm = MeteredLLM()
        for t in DIAG:
            if llm.n_api_calls >= GLOBAL_CALL_CAP:
                print("!! 达到全局调用上限 %d，停止" % GLOBAL_CALL_CAP)
                break
            print("== 诊断题 %s（%s）==" % (t["tid"], t["topology"]), flush=True)
            try:
                r = run_task(t["ask"], t["evidence"], cfg=t["cfg"], llm=llm, log=log,
                             ctx=dict(arm_id="A_fixed", task_id=t["tid"], rep=1, seed="S1",
                                      seed_policy="api_seed_unsupported__label_only__NOT_reproducible",
                                      devset_id="NOT_PROVIDED", devset_hash="NOT_PROVIDED",
                                      evidence_pack_version="smoke-local-v2"))
                r["cfg"] = t["cfg"]
                results.append(r)
                ap, mp = save_run(RUNS_ROOT, "A_fixed", t["tid"], 1, r["answer"], r["meta"])
                written.append((ap, mp))
                m = r["meta"]
                print("   calls=%s tokens=%s pool=%s shipped=%s 支持=%s 矛盾=%s 未提及=%s 解析失败=%s"
                      % (m.get("n_calls"), m.get("n_tokens"), m.get("n_pool"),
                         m.get("n_shipped"), m.get("n_supported"), m.get("n_contradicted"),
                         m.get("n_unmentioned"), m.get("n_parsefail")), flush=True)
                print("   over_budget=%s round2_executed=%s collapse_flag=%s（诊断量）"
                      % (m.get("over_budget_count"), m.get("round2_executed"),
                         m.get("collapse_flag")), flush=True)
                print("   models_used=%s" % (m.get("models_used"),), flush=True)
                print("   --- 答案 ---", flush=True)
                print(r["answer"], flush=True)
            except Exception as e:                          # noqa: BLE001
                print("   !! 异常：%r" % (e,), flush=True)
        total_calls = llm.n_api_calls
        total_tokens = llm.n_tokens
        usage = [dict(i=i + 1, **u) for i, u in enumerate(llm.usage_log)]
        elapsed = time.time() - started

    summary = build_summary(results, usage, log, elapsed, total_calls, total_tokens, written)
    write_outputs(summary, log, usage, out_dir)

    print("\n总调用数 %d / %d，总 token %d，逻辑调用 %d"
          % (total_calls, GLOBAL_CALL_CAP, total_tokens, len(log)))
    print("自检：%s" % json.dumps(summary["checks"], ensure_ascii=False))
    print("读数：%s" % json.dumps(summary["counters"], ensure_ascii=False))
    if summary["invalidated_samples"]:
        print("作废样本：%s" % json.dumps(summary["invalidated_samples"], ensure_ascii=False))
    # 退出码：调用数超限 ⇒ 2；**作废样本不判脚本失败**（它是**被如实记录**的实验事实）
    if total_calls > GLOBAL_CALL_CAP:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
