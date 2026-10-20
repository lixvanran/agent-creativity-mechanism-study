#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **判官解析器行为表**（2026-10-21 独立复核 F8：解析器不是"严格"的）。

F8 的原话：`DESIGN.md` §10.1 ❷ 写"被**严格**逐行解析器识别"，但代码（当时的正则）
接受「支持 E1」（无分隔符）、「支持 | E99」（伪造编号）、「支持 | E1 blah blah」（尾部垃圾）。
现在 `evidence_index._parse_verdict_lines` 已改成**严格**版本；本脚本把它的**确切行为**
逐条打出来（含**仍然存在**的已知弱点），供 DESIGN §4.6 直接引用。

用法：python3 test_judge_parser.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from evidence_index import _parse_verdict_lines  # noqa: E402

KNOWN = {"E1", "E2", "E3"}


def _one(text, block=("c1",)):
    got = _parse_verdict_lines(text, list(block), KNOWN)
    return {k: v["rel"] + (("/" + ",".join(v["items"])) if v["items"] else "") for k, v in got.items()}


CASES = [
    # (输入, 期望, 说明)
    ("支持 | E1", "支持/E1", "标准格式：接受"),
    ("支持 | E1,E3", "支持/E1,E3", "多条目归因：接受（去重保序）"),
    ("支持｜E1", "支持/E1", "全角分隔符：接受"),
    ("支持 : E1", "支持/E1", "冒号分隔符：接受"),
    ("未提及 | -1", "未提及", "未提及 + 占位编号：接受"),
    ("非主张 | -1", "非主张", "非主张 + 占位编号：接受"),
    ("支持 E1", "解析失败", "**无分隔符 ⇒ 判解析失败**（不静默接受）"),
    ("支持 | E99", "解析失败", "**引用不存在的条目 ⇒ 判解析失败**（不让 support_rate 虚高）"),
    ("支持 | E1 blah blah", "解析失败", "**尾部垃圾 ⇒ 判解析失败**"),
    ("大概支持 | E2", "解析失败", "**未知关系词 ⇒ 整行丢弃**（不是判成「支持」）"),
    ("未提及 | E3", "解析失败", "未提及却给了条目编号 ⇒ 判解析失败"),
]


def check():
    out = {"cases": [], "known_ids": sorted(KNOWN)}
    ok = True
    for text, expect, why in CASES:
        got = _one(text)
        val = list(got.values())[0] if len(got) == 1 else json.dumps(got, ensure_ascii=False)
        passed = (val == expect)
        ok &= passed
        out["cases"].append(dict(input=text, got=val, expect=expect, pass_=passed, why=why))

    # ── 已知弱点：行被丢弃 ⇒ **位置配对错位**（但必定产生一个"解析失败"⇒ 触发重试）──
    mis = _parse_verdict_lines("大概支持 | E2\n支持 | E1", ["c1", "c2"], KNOWN)
    out["known_weakness_mispairing"] = {
        "input": "大概支持 | E2\\n支持 | E1",
        "c1": mis["c1"]["rel"], "c2": mis["c2"]["rel"],
        "note": ("第一行被丢弃 ⇒ 第二行的判定被**配给 c1**（错位）；"
                 "但 c2 被标成『解析失败』⇒ check_claims_v2 会**重试**（max_attempts=3），"
                 "重试仍失败则该批计入 parsefail_rate、**不进**任何分子/分母（协议 E1/F8）"),
        "has_parsefail_guard": mis["c2"]["rel"] == "解析失败",
    }
    out["PASS"] = bool(ok)
    return out


if __name__ == "__main__":
    r = check()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["PASS"] else 1)
