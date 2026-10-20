# -*- coding: utf-8 -*-
"""路线 A 的可执行性冒烟（**只验证流程能跑通、提示词能解析，不产出任何实验结论**）。

约束（任务书原文）：
- MiniMax 订阅端点，`OPENROUTER_BASE_URL=https://api.minimaxi.com/v1`；
  `PRIMARY_MODEL=MiniMax-M3.1-Flash-Preview`；
- **禁止任何 OpenRouter 调用**（本脚本启动即断言 base url 不含 openrouter.ai）；
- **总调用数 ≤ 20**（chat + embedding 都算；超过即 abort）；
- **不得使用用户四道题**（U1–U4）—— 本脚本用**自造**的两道诊断题；
- 冒烟不产出任何实验结论：日志里不写任何"哪条臂更好"的判断。

用法：
    MINIMAX_SUBSCRIPTION_KEY=... OPENROUTER_BASE_URL=https://api.minimaxi.com/v1 \
    PRIMARY_MODEL=MiniMax-M3.1-Flash-Preview python3 smoke_a.py
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

from route_a import MeteredLLM, run_route, BudgetExceeded   # noqa: E402

# ---------------------------------------------------------------- 自造诊断题（非 U1–U4）
DIAG = [
    dict(
        tid="DS-01",
        ask="某市居民用水阶梯价：第一档每月 0–18 吨，每吨 3.5 元；超过 18 吨的部分每吨 5 元。"
            "某户当月用水 24 吨，应缴水费多少元？",
        evidence=[
            dict(id="EV-DS01-01", text="阶梯价第一档为每月 0–18 吨的部分，每吨 3.5 元。"),
            dict(id="EV-DS01-02", text="超过 18 吨的部分，每吨按 5 元计收。"),
            dict(id="EV-DS01-03", text="阶梯价按实际用水量分档累加计算，不是全部水量都适用最高档单价。"),
        ],
        cfg=dict(round1_facets=["FA2", "FA3"], round2_facets=["FA4"], max_calls=12,
                 extract_cap=5, max_claims=12, verify_batch=12,
                 collapse_mult=99.0),   # 强制触发第二轮：只为覆盖代码路径
    ),
    dict(
        tid="DS-02",
        ask="某快递规定：普通件 10 公斤以内每件 12 元；超出部分每公斤加收 3 元。"
            "生鲜件不得保价，含液体时另付 20 元包装费。"
            "寄一件 8 公斤的生鲜件（含液体）应付多少元？该件是否可以保价？",
        evidence=[
            dict(id="EV-DS02-01", text="普通件在 10 公斤以内按每件 12 元计收。"),
            dict(id="EV-DS02-02", text="超过 10 公斤的部分，每公斤加收 3 元。"),
            dict(id="EV-DS02-03", text="生鲜件不得办理保价。"),
            dict(id="EV-DS02-04", text="生鲜件内含液体时，应另付 20 元包装费。"),
        ],
        cfg=dict(round1_facets=["FA1", "FA2"], round2_facets=[], max_calls=12,
                 extract_cap=5, max_claims=12, verify_batch=12),
    ),
]

GLOBAL_CALL_CAP = 20


def main() -> int:
    out_dir = os.path.join(HERE)
    log_path = os.path.join(out_dir, "smoke_calls.jsonl")
    summary_path = os.path.join(out_dir, "smoke_log.json")
    txt_path = os.path.join(out_dir, "smoke_log.txt")

    llm = MeteredLLM()
    log: list = []
    started = time.time()
    results = []

    for t in DIAG:
        if llm.n_api_calls >= GLOBAL_CALL_CAP:
            print("!! 达到全局调用上限 %d，停止" % GLOBAL_CALL_CAP)
            break
        print("== 诊断题 %s ==" % t["tid"], flush=True)
        try:
            r = run_route(t["ask"], t["evidence"], cfg=t["cfg"], llm=llm, log=log)
            results.append(dict(tid=t["tid"], answer=r["answer"], meta=r["meta"],
                                pool=r["pool"], verdicts=r["verdicts"]))
            print("   calls=%d tokens=%d pool=%d 支持=%d 矛盾=%d 未提及=%d 解析失败=%d"
                  % (r["meta"]["n_calls"], r["meta"]["n_tokens"], r["meta"]["n_pool"],
                     r["meta"]["n_supported"], r["meta"]["n_contradicted"],
                     r["meta"]["n_unmentioned"], r["meta"]["n_parsefail"]), flush=True)
            print("   trigger_fired=%s modes=%s" % (r["meta"]["trigger_fired"],
                                                    r["meta"]["trigger_modes"]), flush=True)
            print("   --- 答案 ---", flush=True)
            print(r["answer"], flush=True)
        except BudgetExceeded as e:
            print("   !! 预算中止：%s" % e, flush=True)
        except Exception as e:
            print("   !! 异常：%r" % (e,), flush=True)

    total_calls = llm.n_api_calls
    total_tokens = llm.n_tokens
    elapsed = time.time() - started

    # ---------------- 写日志
    usage = [dict(i=i + 1, **u) for i, u in enumerate(llm.usage_log)]
    with open(os.path.join(out_dir, "smoke_usage.json"), "w", encoding="utf-8") as f:
        json.dump(usage, f, ensure_ascii=False, indent=1)

    with open(log_path, "w", encoding="utf-8") as f:
        for i, e in enumerate(log, 1):
            f.write(json.dumps(dict(i=i, purpose=e["purpose"], prompt=e["prompt"],
                                    output=e["output"], n_api_calls=e["n_api_calls"],
                                    n_tokens=e["n_tokens"]), ensure_ascii=False) + "\n")

    summary = dict(
        purpose="可执行性冒烟（不产出任何实验结论）",
        endpoint=BASE, primary_model=os.environ.get("PRIMARY_MODEL"),
        openrouter_used=False,
        global_call_cap=GLOBAL_CALL_CAP,
        total_api_calls=total_calls, total_tokens=total_tokens,
        n_prompts=len(log), elapsed_sec=round(elapsed, 1),
        usage=usage,
        tasks=[dict(tid=r["tid"], meta=r["meta"], n_pool_items=len(r["pool"]),
                    n_claims_extracted=len(r["pool"]),
                    answer=r["answer"]) for r in results],
        checks={},
    )
    # ---- 自检项
    all_prompts = [e["prompt"] for e in log]
    summary["checks"]["prompts_parse_all_nonempty"] = all(len(p.strip()) > 0 for p in all_prompts)
    summary["checks"]["no_openrouter_in_prompts_or_endpoints"] = (
        "openrouter.ai" not in BASE
        and not any("openrouter.ai" in p for p in all_prompts))
    ev_leak = 0
    for t in DIAG:
        for it in t["evidence"]:
            for p in all_prompts:
                if it["text"] in p and "依据条目" not in p:
                    ev_leak += 1
    summary["checks"]["evidence_not_in_generation_prompts"] = (ev_leak == 0)
    summary["checks"]["evidence_leak_count"] = ev_leak
    summary["checks"]["every_task_produced_nonempty_answer"] = all(
        len(r["answer"].strip()) >= 50 for r in results)
    summary["checks"]["every_task_has_parsed_verdicts"] = all(
        r["meta"]["n_pool"] == 0 or r["meta"]["n_parsefail"] < r["meta"]["n_pool"]
        for r in results)
    summary["checks"]["within_global_call_cap"] = (total_calls <= GLOBAL_CALL_CAP)

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("路线 A · 可执行性冒烟日志\n")
        f.write("（本文件只记录「流程能否跑通、提示词能否解析」，**不含任何实验结论**）\n\n")
        f.write("端点        : %s\n" % BASE)
        f.write("主模型      : %s\n" % os.environ.get("PRIMARY_MODEL"))
        f.write("OpenRouter  : 未使用（已断言）\n")
        f.write("总调用数    : %d / 上限 %d\n" % (total_calls, GLOBAL_CALL_CAP))
        f.write("总 token    : %d\n" % total_tokens)
        f.write("耗时        : %.1f s\n" % elapsed)
        f.write("提示词条数  : %d\n" % len(log))
        f.write("\n逐次 API 调用的 token 分解（prompt / completion）：\n")
        for u in usage:
            f.write("  #%-3d prompt=%-7d completion=%-7d total=%-7d\n"
                    % (u["i"], u["prompt_tokens"], u["completion_tokens"], u["total_tokens"]))
        f.write("\n")
        f.write("自检：\n")
        for k, v in summary["checks"].items():
            f.write("  - %-42s %s\n" % (k, v))
        f.write("\n逐题结果：\n")
        for r in results:
            f.write("\n---- %s ----\n" % r["tid"])
            f.write(json.dumps(r["meta"], ensure_ascii=False, indent=2))
            f.write("\n答案：\n%s\n" % r["answer"])
        f.write("\n---- 逐次调用（prompt / output）----\n")
        for i, e in enumerate(log, 1):
            f.write("\n===== call %d · %s =====\n" % (i, e["purpose"]))
            f.write("--- prompt ---\n%s\n" % e["prompt"])
            f.write("--- output ---\n%s\n" % (e["output"] or "(空)"))

    print("\n总调用数 %d / %d，总 token %d，耗时 %.1fs" %
          (total_calls, GLOBAL_CALL_CAP, total_tokens, elapsed))
    print("自检：%s" % json.dumps(summary["checks"], ensure_ascii=False))
    return 0 if summary["checks"]["within_global_call_cap"] else 2


if __name__ == "__main__":
    sys.exit(main())
