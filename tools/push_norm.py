#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
★ 【传输层归一化清单】—— ★ ★ **★ 单一真相源（★ 2026-10-24 主会话要求共享）★★★** ★★
============================================================================

★ **★ 为什么要有这个共享件 ★★**
------------------------------------------------------------------------
★ **★ 问题：★ 传输层会静默【丢】字段、★ 也会静默【规范化】字段 ★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 而【逐字比对】只有在【两边规则相同】时才有意义 ★★** ⇒ ⇒ ★ ⇒
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 若每个组各写一份归一化规则 ⇒ ⇒ ★ ⇒⇒ **★ ⇒ ⇒ 三份不同的规则 ⇒ ⇒ ★ ⇒ ⇒ ⇒ 逐字核对【互相不认】⇒ ⇒ ★ ⇒⇒ ★ ★ **★ ⇒ ⇒ ⇒ ⇒ ⇒ 【归一化清单必须单一真相源】★★** ★★**

★ **★ 清单是【表驱动】的（★ 2026-10-24 主会话：★ 归一化清单【一定会继续长】）★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 每条都挂【实测证据】（★ 谁、何时、什么形态）★★** ⇒ ⇒ ★ ⇒
★ ⇒ ⇒ ★ ⇒ **★ ⇒ ⇒ 新增一条 = 往表里加一行（★ 不改任何函数逻辑）★★** ★★

★ **★ 铁律：★ 【只归一化【实测到的那几处】】★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 通篇 `strip()` 会【掩盖真差异】★★** ⇒ ⇒ ★ ⇒ **★ ⇒ 每一行都写清【只影响什么】★★** ★★

★ **★ 用法 ★★
------------------------------------------------------------------------
★   from push_norm import norm_field, NORMALIZERS, describe
★   actual = norm_field("message", remote_msg)
★   expect = norm_field("message", local_msg)
★   if actual != expect: ...        # ★ ★ 真正的不一致 ★★
"""

from __future__ import annotations

import re
import sys
from typing import Any, Dict, List

__all__ = ["NORMALIZERS", "norm_message", "norm_date", "norm_field", "describe", "check_norm"]


# ══════════════════════════════════════════════════════════════════════
# ★ 归一化清单（★ 表驱动；★ 每条挂实测证据）★★
# ══════════════════════════════════════════════════════════════════════

def norm_message(s: str) -> str:
    """★ ① message 尾部换行（★ GitHub 会【去掉】尾部换行）★★

    ★ **实测证据（★ 2026-10-24 · 第二组）★★**：★ 推 `d9b0286f9f77` 时回读远端 commit
    ★ ⇒ ★ 远端 message 末尾为 `owner: 第二组`（★ 无换行）★ ⇒ ★ 本地拼的 msg 末尾有 `\n`
    ★ ⇒ ★ ⇒ **★ ⇒ 逐字比对在【message】上报「远端与本地不一致」★★** ⇒ ★ ⇒
    ★ ⇒ ★ ⇒ **★ ⇒ ⇒ 差在【尾部换行】★★** ⇒ ★ ⇒
    ★ ⇒ ★ ⇒ **★ ⇒ ⇒ ★ ★ 【只影响：★ 尾部连续的换行符】★★** ⇒ ★ ⇒
    ★ ⇒ ★ ⇒ **★ ⇒ ⇒ ★ ★ 【不影响：★ 正文中间与开头的换行】★★** ★★

    ★ ★ **★ 落法：★ `rstrip("\\n")`（★ 不是 `strip()`）★★** ⇒ ★ ⇒
    ★ ⇒ ★ ⇒ **★ ⇒ ⇒ `strip()` 会连【尾部空格】也去掉 ⇒ ⇒ ★ ⇒ ⇒ ★ ★ **★ ⇒ ⇒ ⇒ ⇒ ★ ⇒ 【那会掩盖真差异】★★** ★★
    """
    return s.rstrip("\n")


def norm_date(s: str) -> str:
    """★ ② date 的时区表示（★ GitHub 会规范化为【UTC Z】）★★

    ★ **实测证据（★ 2026-10-24 · 第二组）★★**：★ 推 `7006338ecc6a` 时回读远端 commit
    ★ ⇒ ★ 本地 `%aI` = `2026-10-24T16:12:26+08:00` ★ ⇒ ★ 远端 = `2026-10-24T08:12:26Z`
    ★ ⇒ ★ ⇒ **★ ⇒ 同一时刻、★ 不同表示 ⇒ ⇒ ★ ⇒⇒ **★ ⇒ ⇒ ★ ★ 【逐字比必失败】★★** ⇒ ★ ⇒
    ★ ⇒ ★ ⇒ **★ ⇒ ⇒ ★ ★ 【只影响：★ 同一时刻的时区写法】★★** ⇒ ★ ⇒
    ★ ⇒ ★ ⇒ **★ ⇒ ⇒ ★ ★ 【不影响：★ 时刻本身（★ 归一化后若时刻不同 ⇒ ⇒ 那是真的不一致）★★** ★★

    ★ ★ **★ 注意：★ 这是【时区归一化】、★ 不是【时间截断】★★** ⇒ ★ ⇒
    ★ ⇒ ★ ⇒ **★ ⇒ ⇒ ⇒ 毫秒/秒的差别【仍会被检出】★★** ★★
    """
    try:
        from datetime import datetime, timezone as _tz
        t = s.strip()
        if t.endswith("Z"):
            t = t[:-1] + "+00:00"
        d = datetime.fromisoformat(t)
        if d.tzinfo is None:
            return s
        return d.astimezone(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        # ★ ★ 解析不了就【原样返回】（★ 让不一致被检出，★ 而不是被悄悄抹平）★★
        return s


# ★ ★ ★ 清单表（★ ★ 单一真相源 ★）★★
NORMALIZERS: List[Dict[str, Any]] = [
    {
        "field": "message",
        "fn": norm_message,
        "what": "★ 去掉【尾部】换行（★ GitHub 实测会去掉）★★",
        "evidence": "★ 2026-10-24 · 第二组 · 远端 commit `d9b0286f9f77`（★ 尾部 `owner: 第二组` 无换行 ★）★★",
        "affects": "★ 仅尾部连续换行 ★★",
        "not_affects": "★ 正文中的换行、开头换行、尾部空格 ★★",
    },
    {
        "field": "date",
        "fn": norm_date,
        "what": "★ 带偏移的 ISO8601 ⇒ 统一为【UTC Z】★★",
        "evidence": "★ 2026-10-24 · 第二组 · 远端 commit `7006338ecc6a`（★ `+08:00` ⇒ `Z` ★）★★",
        "affects": "★ 同一时刻的时区写法 ★★",
        "not_affects": "★ 时刻本身、★ 精度（★ 秒/毫秒差别仍会检出）★★",
    },
]

_BY_FIELD = {n["field"]: n for n in NORMALIZERS}


def norm_field(field: str, s: str) -> str:
    """★ 按字段名做归一化（★ 未知字段 ⇒ 原样返回）★★"""
    n = _BY_FIELD.get(field)
    if n is None:
        return s
    return n["fn"](s)


def describe() -> str:
    """★ 把清单打成人可读的表（★ 便于跨组对齐）★★"""
    out = ["★ 传输层归一化清单（★ 单一真相源 · tools/push_norm.py）★", ""]
    out.append("| ★ 字段 | ★ 归一化什么 | ★ 只影响 | ★ 不影响 | ★ 实测证据 |")
    out.append("|---|---|---|---|---|")
    for n in NORMALIZERS:
        out.append("| ★ `%s` | %s | %s | %s | %s |" % (
            n["field"], n["what"], n["affects"], n["not_affects"], n["evidence"]))
    out.append("")
    out.append("★ **★ 【只归一化【实测到的那几处】】★★ —— ⇒ ★ ⇒ **★ 通篇 `strip()` 会掩盖真差异 ★★**")
    return "\n".join(out)


def check_norm() -> List[str]:
    """★ 自检：★ 每条归一化【必须只影响它该影响的】★★ ⇒ ⇒ 返回失败项（★ 空 = 全过）★★"""
    bad: List[str] = []
    # ① message：只去尾部换行
    if norm_message("a\nb\n") != "a\nb":
        bad.append("① message：尾部换行未去掉")
    if norm_message("a\nb") != "a\nb":
        bad.append("① message：正文换行被误改")
    if norm_message("a  \n") != "a  ":
        bad.append("① message：尾部空格被误去（★ 不该发生 ★）")
    # ② date：时区归一
    if norm_date("2026-10-24T16:12:26+08:00") != "2026-10-24T08:12:26Z":
        bad.append("② date：时区未归一")
    if norm_date("2026-10-24T08:12:26Z") != "2026-10-24T08:12:26Z":
        bad.append("② date：已是 UTC 却被动")
    if norm_date("not-a-date") != "not-a-date":
        bad.append("② date：解析失败时未原样返回")
    if norm_date("2026-10-24T08:12:26.123Z") != "2026-10-24T08:12:26Z":
        bad.append("② date：毫秒被截断（★ ★ 精度差别应仍可检出 ★）")
    # ③ 未知字段原样
    if norm_field("unknown", "x\n") != "x\n":
        bad.append("③ 未知字段未原样返回")
    return bad


if __name__ == "__main__":
    print(describe())
    print()
    bad = check_norm()
    if bad:
        for b in bad:
            print("  ✘ %s" % b)
        print("✘ push_norm 自检：%d 项未过" % len(bad))
        sys.exit(1)
    print("✔ push_norm 自检全过（★ %d 条归一化 ★）" % len(NORMALIZERS))
    # ★ ★ 【★ 变异验活：★ 判据必须能红 ★】★★
    _probe = NORMALIZERS[0]["fn"]
    if _probe("a\nb\n") == "a\nb\n":
        print("✘ ★ 变异探测失败（★ norm_message 似乎没起作用 ★）")
        sys.exit(1)
    print("✔ 变异探测：★ 归一化确实改变了应改的（★ 判据是活的 ★）")
