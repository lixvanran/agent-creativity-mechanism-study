# -*- coding: utf-8 -*-
"""路线 C · 受约束提案器（默认关闭，但**机制完整可执行**）。

本模块把 DESIGN.md §3.2 的两句话**变成代码**：
  ① 提案者只接收 `structural_diagnostics(episodes)` 这一个入口；
     该函数**只从白名单里取字段**，而不是"先拿全量再删" ⇒ oracle 统计**不在它的返回值结构里**。
  ② 结构检查器 H1–H6 + 修复 ≤2 次 + **强制回退**到人定默认 ⇒ 设计环节永远不会阻塞跑批。

**白名单是"结构性"的**：允许的只有**计数**与**布尔**（每阶段调用了几次、是否超预算、
是否空产出、是否解析失败、阶段覆盖表）。**任何比率/得分/命中数都不在白名单里**，
因为比率是 oracle 统计的常见载体（矛盾率/支持率/命中率/宽度）。

另设一道 `assert_no_oracle_leak(payload)`：对**序列化后**的诊断载荷做关键字扫描
（键名 + 数值型字段）⇒ 任何"看起来像指标"的字段一旦混入即抛错，而不是静默通过。
"""
from __future__ import annotations

import json
import re

from topology import (ACTION_SPACE_MANUAL, HARD_CONSTRAINTS, TEMPLATES, TEMPLATE_IDS,
                      parse_proposal, structural_check)

# ------------------------------------------------------------------ 白名单
#: 允许出现在提案者诊断里的**结构**字段（计数 / 布尔），逐个显式列出。
ALLOWED_KEYS = (
    "n_episodes",
    "stage_coverage",          # {stage: 调用次数}
    "stages_never_executed",   # [stage, ...]
    "n_over_budget",
    "n_empty_output",
    "n_parse_failed",
    "n_episode_calls_max",
    "n_episode_calls_min",
    "n_topologies_tried",
)

#: 明确**禁止**出现在提案者诊断里的词根（判定为 oracle 统计泄漏）。
FORBIDDEN_SUBSTRINGS = (
    "conflict", "support", "verdict", "judge", "accuracy", "hit_rate", "hitrate",
    "dimension", "vd_", "_vd", "width", "score", "reward", "utility", "novelty",
    "key_conclusion", "oracle", "ratio", "rate", "precision", "recall", "f1",
    "ground_bearing", "load_bearing", "n_supported", "n_claims", "claims",
)

#: 阶段名（仅用于"哪些阶段被执行过"这种结构性描述）
STAGE_NAMES = ("GEN", "EXTRACT", "VERIFY", "SPLIT", "COLLAPSE", "REDISTRIBUTE",
                "STALL", "MERGE")


# ------------------------------------------------------------------ 入口
def structural_diagnostics(episodes: list) -> dict:
    """**提案者诊断的唯一入口**。

    参数 `episodes` 是执行器产出的诊断字典列表（`executor.diagnostics` 的输出）。
    本函数**只从白名单字段里取值**：不读 claims / verdict / 冲突率 / 支持率 / 任何比率。

    返回结构（键名全部来自 ALLOWED_KEYS，值只有整数与字符串列表）。
    """
    eps = list(episodes or [])
    coverage = {s: 0 for s in STAGE_NAMES}
    over_budget = empty = parse_failed = 0
    calls = []
    for ep in eps:
        for entry in (ep.get("stage_log") or []):
            st = entry.get("stage")
            if st in coverage:
                coverage[st] += 1
        if ep.get("over_budget") or (ep.get("n_calls") or 0) > (ep.get("call_cap") or 1 << 30):
            over_budget += 1
        if (ep.get("answer_chars") or 0) < 50:
            empty += 1
        if ep.get("n_parse_failed"):
            parse_failed += 1
        calls.append(int(ep.get("n_calls") or 0))
    payload = {
        "n_episodes": len(eps),
        "stage_coverage": {k: v for k, v in coverage.items() if v > 0},
        "stages_never_executed": [s for s in STAGE_NAMES if coverage[s] == 0],
        "n_over_budget": over_budget,
        "n_empty_output": empty,
        "n_parse_failed": parse_failed,
        "n_episode_calls_max": max(calls) if calls else 0,
        "n_episode_calls_min": min(calls) if calls else 0,
        "n_topologies_tried": len(set(ep.get("topology") for ep in eps if ep.get("topology"))),
    }
    assert_no_oracle_leak(payload)
    return payload


def assert_no_oracle_leak(payload) -> None:
    """对**序列化后**的载荷做泄漏扫描：发现指标型字段即抛错。"""
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in blob:
            raise AssertionError("提案者诊断里出现被禁字段/词根：%s" % bad)
    # 值也不允许是浮点（比率的典型形态）⇒ 只允许整数与字符串列表
    def _walk(o, path="payload", parent=None):
        if isinstance(o, dict):
            for k, v in o.items():
                if parent == "stage_coverage":
                    if k not in STAGE_NAMES:
                        raise AssertionError("stage_coverage 里的非阶段键：%s.%s" % (path, k))
                elif k not in ALLOWED_KEYS:
                    raise AssertionError("白名单外的键：%s.%s" % (path, k))
                _walk(v, path + "." + k, k)
        elif isinstance(o, list):
            for v in o:
                if parent == "stages_never_executed" and v not in STAGE_NAMES:
                    raise AssertionError("stages_never_executed 里的非阶段名：%s" % v)
                _walk(v, path + "[]", parent)
        elif isinstance(o, float):
            raise AssertionError("提案者诊断里出现浮点（可能是比率）：%s" % path)
    _walk(payload)


# ------------------------------------------------------------------ 提示词
def build_proposal_prompt(diagnostics: dict) -> str:
    """说明书 + 白名单诊断 → 提案提示词。**不含任何 oracle 统计**。"""
    d = json.dumps(diagnostics, ensure_ascii=False, indent=1)
    return (ACTION_SPACE_MANUAL +
            "\n## 七、这次跑批的结构性诊断（**只有这些是允许给你看的**）\n\n```json\n%s\n```\n\n"
            "请按第六节的输出格式，选出一个模板并给出理由。\n" % d)


# ------------------------------------------------------------------ 提案流程
def run_proposal(llm, episodes=None, manual_prompt=None, max_repair=2,
                 fallback: str = "T2", repair_prompt_extra: str = "") -> dict:
    """完整提案流程：提案 → 解析 → 结构检查 → 修复(≤max_repair) → **强制回退**。

    返回：
      template_id   最终采用的拓扑（回退时 = fallback）
      accepted      是否由提案者给出（False = 走了回退）
      fell_back     是否发生回退
      attempts      用了几次调用
      reason        提案者给的理由（回退时为空）
      last_error    最后一次失败原因（供 run 元数据记录）
      diagnostics   交给提案者的白名单诊断（可审计）
    """
    assert fallback in TEMPLATE_IDS, "回退目标不在菜单内"
    diag = structural_diagnostics(episodes or [])
    prompt = manual_prompt or build_proposal_prompt(diag)
    attempts = 0
    last_error = ""
    parsed = None
    while attempts <= max_repair:
        attempts += 1
        raw = llm.chat(prompt, purpose="c_propose", max_tokens=600, min_ok=8) or ""
        parsed = parse_proposal(raw)
        if not parsed["format_ok"]:
            last_error = "输出格式不合法（缺 TOPOLOGY: 或 REASON: 行）"
        elif not parsed["struct_ok"]:
            last_error = "结构检查未通过：%s" % (
                structural_check(TEMPLATES[parsed["template_id"]])
                if parsed["template_id"] else "模板 ID 不在菜单内")
        else:
            return dict(template_id=parsed["template_id"], accepted=True, fell_back=False,
                        attempts=attempts, reason=parsed["reason"], last_error="",
                        diagnostics=diag, raw_head=parsed["raw_head"])
        # 修复：把检查器反馈喂回去（**只给结构层反馈，不给任何指标**）
        prompt = (build_proposal_prompt(diag) +
                  "\n【上一版被拒的原因】%s\n请修正后按第六节格式重新输出。\n" % last_error +
                  (repair_prompt_extra or ""))
    return dict(template_id=fallback, accepted=False, fell_back=True, attempts=attempts,
                reason="", last_error=last_error, diagnostics=diag, raw_head="")


def hard_constraint_table() -> str:
    return "\n".join("  - %s %s" % (c, d) for c, d in HARD_CONSTRAINTS)
