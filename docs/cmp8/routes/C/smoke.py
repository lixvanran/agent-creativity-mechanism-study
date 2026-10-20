# -*- coding: utf-8 -*-
"""路线 C · 可执行性冒烟（**不产出任何实验结论**）。

目的：验证「流程能跑通、提示词能解析」。
验证项：
  1. 参数表可导入、默认向量可序列化、可哈希、可校验
  2. 拓扑菜单 6 个模板全部通过结构检查器
  3. 行动空间说明书可渲染；受约束提案器的输出**格式可解析**（1 次调用）
  4. 执行器在 2 个参数配置下各跑 2 道**自造诊断题**（每 episode 4 次调用）
  5. 训练侧代理指标 + 反投机检查（条数灌水探针）可计算
  6. 全程只走 MiniMax 端点（断言 base_url 不含 openrouter）

⚠️ 冒烟**不得**使用用户四道题（U1–U4）⇒ 这里用 2 道自造诊断题（SMOKE_Q*）。
⚠️ 冒烟里的"核验"是**词法桩**，不是判官 ⇒ 它的输出不构成任何指标结论。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import params as P
import topology as T
from executor import run_episode, jaccard

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_JSON = os.path.join(OUT_DIR, "smoke_log.json")
LOG_TXT = os.path.join(OUT_DIR, "smoke_log.txt")
LOG_CALLS = os.path.join(OUT_DIR, "smoke_calls.jsonl")   # 增量落盘：每次 POST 立即写一行

BASE = os.environ.get("OPENROUTER_BASE_URL", "https://api.minimaxi.com/v1").rstrip("/")
MODEL = os.environ.get("PRIMARY_MODEL", "MiniMax-M3.1-Flash-Preview")
KEY = os.environ.get("MINIMAX_SUBSCRIPTION_KEY", "")
CALL_CAP = 20                      # 硬上限：超出即中止

# --------------------------------------------------------------------------
# 严格客户端：每次 chat() 恰好 1 次 HTTP POST（不做 length 重试），
# 全局计数；超过 CALL_CAP 立即抛错。⇒ 调用数可审计。
# --------------------------------------------------------------------------
class SmokeBudgetExceeded(RuntimeError):
    pass


class StrictLLM:
    def __init__(self, cap: int = CALL_CAP):
        self.cap = cap
        self.n_posts = 0
        self.log: list[dict] = []
        # 增量落盘：进程被杀也能逐条核对调用数
        try:
            os.remove(LOG_CALLS)
        except OSError:
            pass

    def _append(self, rec: dict):
        with open(LOG_CALLS, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def chat(self, prompt, *, model=None, temp=0.7, max_tokens=1200,
             budgets=(), min_ok=20, purpose=""):
        if self.n_posts >= self.cap:
            raise SmokeBudgetExceeded("调用数已达上限 %d" % self.cap)
        payload = {"model": model or MODEL,
                   "messages": [{"role": "user", "content": prompt}],
                   "temperature": temp, "max_tokens": max_tokens}
        t0 = time.time()
        self.n_posts += 1
        rec = {"seq": self.n_posts, "purpose": purpose, "model": payload["model"],
               "max_tokens": max_tokens, "url": BASE + "/chat/completions",
               "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            req = urllib.request.Request(
                BASE + "/chat/completions", data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer %s" % KEY,
                         "content-type": "application/json"})
            d = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
            ch = d["choices"][0]
            raw = ch["message"].get("content") or ""
            txt = re.sub(r"^.*?</think>", "", re.sub(r"<think>.*?</think>", "", raw, flags=re.S),
                         flags=re.S).strip()
            u = d.get("usage") or {}
            rec.update(ok=True, finish_reason=ch.get("finish_reason", ""),
                       content_len=len(txt), prompt_tokens=u.get("prompt_tokens", 0),
                       completion_tokens=u.get("completion_tokens", 0),
                       secs=round(time.time() - t0, 2))
        except Exception as e:
            txt = ""
            rec.update(ok=False, error="%s: %s" % (type(e).__name__, str(e)[:120]),
                       secs=round(time.time() - t0, 2))
        self.log.append(rec)
        self._append(rec)
        return txt

    def tokens(self) -> int:
        return sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0)
                   for r in self.log)


# --------------------------------------------------------------------------
# 词法桩核验器（**不是判官**）：只用来把流水线接起来，不产生任何指标结论
# --------------------------------------------------------------------------
def stub_verifier(ask, evidence, claims):
    facts = [f for f in re.split(r"\n\s*-\s*", evidence or "") if f.strip()]
    out = {}
    for c in claims:
        best = max([jaccard(c, f) for f in facts] or [0.0])
        out[c] = "支持" if best >= 0.35 else "未提及"
    return out


# --------------------------------------------------------------------------
# 2 道自造诊断题（**不使用 U1–U4**；结论空间只作 schema 完整性占位）
# --------------------------------------------------------------------------
SMOKE_TASKS = [
    dict(
        task_id="SMOKE-S1",
        ask=("社区图书室的借阅规则如下：每人每次最多借 3 册，借期 14 天；"
             "逾期罚金按每册每天 0.5 元计算，单次借阅的罚款总额上限为 20 元。"
             "小林一次借了 3 册书，在第 20 天把 3 册全部归还。"
             "请回答：他需要支付多少罚款？请写出计算过程与所依据的规则。"),
        evidence=("- 每册图书的借期为 14 天，自应还日次日起计逾期。\n"
                  "- 逾期罚金按每册每天 0.5 元计算。\n"
                  "- 单次借阅的罚款总额上限为 20 元。\n"
                  "- 每人每次最多借阅 3 册。"),
        conclusion_space=["罚款总额为 9 元", "逾期天数按 6 天计", "未触及 20 元封顶上限",
                          "3 册全部逾期", "无法判定"],
        key_conclusions=["罚款总额为 9 元"],
    ),
    dict(
        task_id="SMOKE-S2",
        ask=("一个社区服务站有一笔 2 万元的年度改造预算，只能投向下列一项："
             "①延长夜间开放时间；②更新消防设施；③增设自助借还设备。"
             "请给出你的选择与理由，并分别说明另外两项各自的主要代价。"),
        evidence=("- 服务站现有消防设备上次年检为 3 年前，期间无故障记录。\n"
                  "- 夜间时段（20:00 之后）近三个月的使用人数为每晚 12 人次。\n"
                  "- 服务站目前没有自助借还设备；附近两所学校共 480 名学生使用该服务站。\n"
                  "- 服务站本年度可动用的改造预算余额为 2 万元。"),
        conclusion_space=["选择延长夜间开放时间", "选择更新消防设施", "选择增设自助借还设备",
                          "三项都不可行", "无法判定"],
        key_conclusions=[],
    ),
]

# 两个参数配置：故意让它们在"装配条数"与"效用门控"上不同 ⇒ 冒烟能看出参数起作用
CFG_A = dict(P.default_theta())
CFG_A.update(n_frames=1, n_cand_per_frame=1, theta_util=0.5, m_clusters=3,
              n_verify_max=6, theta_dist=0.25)
CFG_B = dict(P.default_theta())
CFG_B.update(n_frames=1, n_cand_per_frame=1, theta_util=0.0, m_clusters=1,
              n_verify_max=6, theta_dist=0.25)


def main():
    assert "openrouter" not in BASE.lower(), "冒烟禁止 OpenRouter：%s" % BASE
    assert BASE == "https://api.minimaxi.com/v1", "被测侧端点不符：%s" % BASE
    llm = StrictLLM(CALL_CAP)
    report = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "base_url": BASE, "model": MODEL, "call_cap": CALL_CAP,
              "verifier": "STUB_LEXICAL_NOT_A_JUDGE（词法桩，不是判官）",
              "tasks": [t["task_id"] for t in SMOKE_TASKS],
              "note": "冒烟只验证流程可跑通与提示词可解析，不产出任何实验结论"}
    lines = []

    def say(s):
        print(s, flush=True)
        lines.append(s)

    # --- 1. 参数表 ---
    th0 = P.default_theta()
    report["params"] = dict(default_hash=P.theta_hash(th0), n_params=len(P.PARAM_SPEC),
                            validate_empty=P.validate(th0, "T2"),
                            live_T2=[p["name"] for p in P.live_params("T2")])
    say("[1] 参数表：%d 个参数，默认向量 hash=%s，校验=%s"
        % (len(P.PARAM_SPEC), P.theta_hash(th0), P.validate(th0, "T2") or "OK"))

    # --- 2. 拓扑菜单结构检查 ---
    checks = {tid: T.check_template(tid) for tid in T.TEMPLATE_IDS}
    report["topology_checks"] = checks
    say("[2] 拓扑菜单：%s" % ("全部 PASS" if not any(checks.values())
                              else ("FAIL " + json.dumps(checks, ensure_ascii=False))))
    say("    手册长度 %d 字符" % len(T.MANUAL_WITH_MENU))

    # --- 3. 受约束提案器（1 次调用；只验格式可解析）---
    prop_prompt = (T.MANUAL_WITH_MENU +
                   "\n请按第六节的输出格式，选出一个模板并给出理由。\n")
    raw = llm.chat(prop_prompt, purpose="c_propose", max_tokens=600, min_ok=10)
    parsed = T.parse_proposal(raw)
    report["proposer"] = dict(raw_head=parsed["raw_head"], parsed=parsed)
    say("[3] 提案器：format_ok=%s struct_ok=%s → %s"
        % (parsed["format_ok"], parsed["struct_ok"], parsed["template_id"]))
    say("    原始输出：%s" % parsed["raw_head"].replace("\n", " | ")[:160])

    # --- 4. 执行器：2 配置 × 2 题（对称，单路）+ 1 次多路探针 ---
    # 调用预算规划：提案 1 + (2 题 × 2 配置 × 2 调用) 8 + 多路探针 4 = 13 ≤ 20
    eps = []
    plan = [("CFG_A", SMOKE_TASKS[0], CFG_A, "main"),
            ("CFG_A", SMOKE_TASKS[1], CFG_A, "main"),
            ("CFG_B", SMOKE_TASKS[0], CFG_B, "main"),
            ("CFG_B", SMOKE_TASKS[1], CFG_B, "main")]
    probe_cfg = dict(CFG_A)
    probe_cfg["n_frames"] = 2
    plan.append(("PROBE_multiframe", SMOKE_TASKS[0], probe_cfg, "probe"))
    for cid, task, cfg, kind in plan:
        try:
            d = run_episode(task, T.DEFAULT_TOPOLOGY, cfg, llm=llm,
                            verifier=stub_verifier, max_calls=6)
        except SmokeBudgetExceeded as e:
            say("!! 预算中止：%s" % e)
            d = None
        if d is None:
            continue
        d["config"] = cid
        d["task_id"] = task["task_id"]
        d["kind"] = kind
        eps.append(d)
        say("[4] %s / %s：calls=%d claims=%d 支持=%d 冲突=%d 去重支持=%d "
            "conflict_rate_pre=%.3f 答案字符=%d 阶段=%s"
            % (cid, task["task_id"], d["n_calls"], d["n_claims_total"],
               d["n_claims_supported"], d["n_claims_conflict"],
               d["n_supported_distinct"], d["conflict_rate_pre"],
               d["answer_chars"],
               ",".join(s["stage"] for s in d["stage_log"])))
    report["episodes"] = [
        {k: v for k, v in d.items() if k not in ("claims", "answer")}
        for d in eps]
    report["answers"] = [{"config": d["config"], "task": "SMOKE", "answer": d["answer"]}
                         for d in eps]

    # --- 5. 反投机探针（条数灌水）+ 参数是否真的改变了行为 ---
    probe = []
    for cid in ("CFG_A", "CFG_B"):
        ds = [d for d in eps if d["config"] == cid and d.get("kind") == "main"]
        if not ds:
            continue
        tot = sum(d["n_claims_total"] for d in ds)
        sup = sum(d["n_supported_distinct"] for d in ds)
        probe.append(dict(config=cid, n_claims_total=tot, n_supported_distinct=sup,
                          f2_growth=None))
    a = next((p for p in probe if p["config"] == "CFG_A"), None)
    b = next((p for p in probe if p["config"] == "CFG_B"), None)
    if a and b and a["n_claims_total"]:
        g_tot = (b["n_claims_total"] - a["n_claims_total"]) / a["n_claims_total"]
        g_sup = ((b["n_supported_distinct"] - a["n_supported_distinct"])
                 / max(a["n_supported_distinct"], 1))
        a["f2_growth"] = dict(claims_growth=round(g_tot, 3), supported_growth=round(g_sup, 3),
                              suspicious=bool(g_tot >= 0.20 and g_sup < 0.10))
    report["spec_probe"] = probe
    say("[5] 反投机探针：%s" % json.dumps(probe, ensure_ascii=False))

    beh = {}
    for d in eps:
        if d.get("kind") == "main":
            beh.setdefault(d["config"], []).append(d["answer_chars"])
    report["param_effect"] = dict(answer_chars_by_config=beh,
                                  distinct=bool(len(set(map(tuple, beh.values()))) > 1))
    say("[6] 参数是否改变了行为：%s" % json.dumps(beh, ensure_ascii=False))

    # --- 7. 调用账 ---
    report["calls"] = dict(n_posts=llm.n_posts, cap=CALL_CAP,
                            tokens=llm.tokens(), log=llm.log)
    say("[7] 调用账：HTTP POST %d 次（上限 %d），tokens=%d"
        % (llm.n_posts, CALL_CAP, llm.tokens()))
    assert llm.n_posts <= CALL_CAP, "超出调用上限"
    assert "openrouter" not in json.dumps(report).lower(), "报告里出现 OpenRouter 字样"

    report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(LOG_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n日志：%s\n      %s" % (LOG_JSON, LOG_TXT))


if __name__ == "__main__":
    main()
