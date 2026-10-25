# -*- coding: utf-8 -*-
"""格式对称化审计（B-2d）—— 跨路线比较之前，先确认三臂的"机械答案"是同一种东西。

> 2026-10-22 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/audit_format_symmetry.py`
> 依据：协议 §4.5「机械答案（mechanical answer）」——**事前选定**的评分对象必须是
>      「所有臂**同一模板**、**同一依据包引用格式**、**同一字数上限**」的产物。
> 出处：组 4 在 ADHD 源码里的发现（体裁/对象漂移 ⇒ 先审对称性再比结果）。

## 为什么这个审计排在"跑实验"之前

跨路线比较里，**格式差异会直接改写读数**，而且方向是**可预测的**：

| 格式差异 | 对读数的方向性影响（可推，不必猜）|
|---|---|
| 答案里**回显题面** | 判官更容易把条目判成「复述」⇒ `is_claim=false` ⇒ 断言数↓、维度数↓ |
| 条目**带 `[EV-xx]` 引用** | 判官更容易对齐依据 ⇒ `evidence_ref` 命中率↑、`unverifiable`↓ ⇒ 维度数↑ |
| **代码级**字数截断 | 长的条目被机械丢弃 ⇒ 尾部内容永远进不了读数 |
| 标题/段落结构不同 | 判官的"段"假设与结构化抽取的切分点不同 ⇒ 同一内容切出的断言条数不同 |

⇒ 所以：**如果三臂格式不对称，维度数的差异里就混着格式的贡献**，
⇒ 任何「路线 A 比路线 C 宽」的说法都**不可归因**。

## 用法

```bash
# 静态审计（代码级，不需要任何答案或 API）
python3 audit_format_symmetry.py --static

# 动态审计（给定三臂的答案文件，逐份算实际结构）
python3 audit_format_symmetry.py --answers A:/path/a1.md,C:/path/c1.md,B0:/path/b0.md
```
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
COLLAPSE_DIR = os.path.dirname(HERE)
ROUTES_DIR = os.path.dirname(COLLAPSE_DIR)
CMP8_DIR = os.path.dirname(ROUTES_DIR)
REPO = os.path.dirname(CMP8_DIR)


# ── 静态审计：把三条臂的"答案装配路径"抽成可比字段 ──────────────────
def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def static_audit() -> Dict[str, Any]:
    a_py = _read(os.path.join(ROUTES_DIR, "A", "route_a.py"))
    wf_py = _read(os.path.join(COLLAPSE_DIR, "workflow.py"))
    c_cfg = _read(os.path.join(ROUTES_DIR, "C", "config.py"))
    b_measure = _read(os.path.join(CMP8_DIR, "batch-U1", "measure.py"))

    def grab(pat: str, text: str, flags=0) -> Optional[str]:
        m = re.search(pat, text, flags)
        return m.group(0) if m else None

    rows = [
        {
            "field": "答案是否回显题面",
            "A": "是（`# {ask}` 标题）" if '"# %s\\n\\n##' in a_py else "否",
            "C": "否（机械汇总只拼 `- ` 列表）" if 'agg = "\\n".join("- " + c' in wf_py else "见代码",
            "B0": "由模型自由决定（无模板）",
            "symmetric": False,
            "readout_impact": "A 臂的答案里带题面 ⇒ 判官更易判「复述」⇒ 断言数与维度数被系统性压低",
        },
        {
            "field": "依据引用格式",
            "A": "条目带 `[EV-xx]` 前缀",
            "C": "无引用前缀（裸断言）" if 'agg = "\\n".join("- " + c' in wf_py else "见代码",
            "B0": "无（自由文本）",
            "symmetric": False,
            "readout_impact": "C 臂的 `evidence_ref` 更易为 null ⇒ `unverifiable`↑ ⇒ 维度数被系统性压低",
        },
        {
            "field": "字数上限在哪里强制",
            "A": "**代码级**截断（`answer_char_cap=400`，整份答案含题面与标题）",
            "C": "**提示词级**（`_OUT_SPEC` 要求 ≤400 字）＋ **最终装配不截断**",
            "B0": "无上限",
            "symmetric": False,
            "readout_impact": "只有 A 臂的尾部内容会被机械丢弃 ⇒ C/B0 的长尾条目仍参与读数",
        },
        {
            "field": "标题结构",
            "A": "`# 题面` + `## 经核验成立的依据`（或 `## 依据未覆盖、仅供参考的事项`）",
            "C": "无标题（纯 `- ` 列表）",
            "B0": "模型自定",
            "symmetric": False,
            "readout_impact": "结构化抽取的切分点随标题不同而不同 ⇒ 同一内容切出的断言条数不同",
        },
        {
            "field": "条目前缀",
            "A": "`- `（+ 可选 `[EV-xx]`）",
            "C": "`- `",
            "B0": "模型自定",
            "symmetric": "部分",
            "readout_impact": "C 与 A 的行前缀一致 ⇒ 抽取侧影响较小；B0 不一致",
        },
        {
            "field": "判官是否拿到题面",
            "A": "是（`CARD_Q` 带 `{ask}`）",
            "C": "是（同上）",
            "B0": "是（同上）",
            "symmetric": True,
            "readout_impact": "判官侧一致（这一项没问题）",
        },
    ]

    # 硬证据：把关键代码行抓出来当证据（可复核）
    evidence = {
        "A_assembly": grab(r'"# %s\\n\\n## [^"]+"', a_py) or "",
        "A_cap": grab(r'answer_char_cap[=:]\s*\d+', a_py) or "",
        "A_item_format": grab(r'item = \([^\n]+\) if ref else \([^\n]+\)', a_py) or "",
        "C_assembly": grab(r'agg = "\\n"\.join\("- " \+ c for c in final_claims\)', wf_py) or "",
        "C_out_spec": grab(r'"- 不超过 \d+ 字"', wf_py) or "",
        "C_cap_in_code": "有" if re.search(r"answer\[:\s*C\[.answer_char_cap.\]\]|answer_char_cap", wf_py) else "无",
        "B0_direct": "直接调用，无模板（batch-U1/measure.py 只做测量）",
        "measure_card_q_has_ask": '"问题：\\n{ask}"' in b_measure or "{ask}" in b_measure,
    }

    n_asym = sum(1 for r in rows if not r["symmetric"])
    return {
        "rows": rows,
        "evidence": evidence,
        "n_asymmetric_fields": n_asym,
        "verdict": ("★ 三臂的机械答案**不是同一模板** ⇒ 协议 §4.5 的前提不成立 ⇒ "
                    "当前跨臂维度数比较**混着格式的贡献**，不可归因"
                    if n_asym >= 3 else
                    "格式基本对称（逐条复核后再下结论）"),
    }


# ── 动态审计：逐份答案算实际结构 ──────────────────────────────────
CJK = re.compile(r"[\u4e00-\u9fff]")
HEADING = re.compile(r"^#{1,6}\s+", re.M)
EVREF = re.compile(r"\[(EV-\d+)\]")
BULLET = re.compile(r"^\s*[-*]\s+", re.M)


def dynamic_audit(pairs: List[Dict[str, str]]) -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    for p in pairs:
        arm, path = p["arm"], p["path"]
        if not os.path.exists(path):
            out.append({"arm": arm, "path": path, "error": "文件不存在"})
            continue
        txt = _read(path)
        heads = HEADING.findall(txt)
        lines = [ln for ln in txt.splitlines() if ln.strip()]
        bullets = [ln for ln in lines if BULLET.match(ln)]
        evrefs = EVREF.findall(txt)
        cjk = len(CJK.findall(txt))
        out.append({
            "arm": arm,
            "path": path,
            "n_chars": len(txt),
            "n_lines": len(lines),
            "n_bullets": len(bullets),
            "bullet_ratio": round(len(bullets) / max(len(lines), 1), 3),
            "n_headings": len(heads),
            "heading_texts": [h.strip() for h in re.findall(r"^#{1,6}\s+.*$", txt, re.M)][:6],
            "n_ev_refs": len(evrefs),
            "ev_ref_ids": sorted(set(evrefs))[:12],
            "cjk_ratio": round(cjk / max(sum(1 for ch in txt if ch.isalpha()), 1), 3),
            "echoes_prompt": bool(heads) and len(heads[0].strip()) > 6,
        })
    return {"answers": out}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", action="store_true")
    ap.add_argument("--answers", nargs="*", default=[],
                    help="形如 ARM:/path/to/answer.md")
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    report: Dict[str, Any] = {}
    if args.static or not args.answers:
        report["static"] = static_audit()
    if args.answers:
        pairs = []
        for a in args.answers:
            arm, _, path = a.partition(":")
            pairs.append({"arm": arm, "path": path})
        report["dynamic"] = dynamic_audit(pairs)

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
