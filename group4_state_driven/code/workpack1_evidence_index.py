#!/usr/bin/env python3
"""工作包一 · 第四组证据入口表（程序化生成 ⇒ 可复核）。

一行 = 一个方向：代码指纹 → 实际执行版本 → 数据路径 → 分析入口 → 当前报告。
⚠️ **历史原件保留；报告与更正记录分开**（不许靠删旧表述来证明修复）。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path("/workspace/mech-study")
G = "group4_state_driven"
BRANCH = "feature/g4-arch4-state-driven"

DIRECTIONS = [
    ("① 正式论证（第四组论证）", [], "evidence-check/", "—",
     "第四组论证.md / 第四组论证.pdf"),
    ("② C1/C2 状态机（Phase 0/1）", ["code/runner2.py", "code/metrics2.py", "code/gates.py",
                                     "code/probe_swap.py", "code/analyze2.py", "code/analyze_ckf.py",
                                     "code/report_p1.py"], "data/", "code/analyze2.py",
     "reports/REPORT_p1.md"),
    ("③ 架构化状态机 v1–v3", ["code/workflow_arch.py", "code/workflow_arch2.py",
                              "code/workflow_arch3.py"], "data/arch3_compare.jsonl",
     "code/analyze_arch3.py", "reports/REPORT_arch3.md"),
    ("④ 架构化状态机 v4（状态进选择层）", ["code/workflow_arch4.py", "code/run_arch4_compare.py",
                                          "code/analyze_arch4.py"], "data/arch4_compare.jsonl",
     "code/analyze_arch4.py", "reports/REPORT_arch4.md"),
    ("⑤ 架构化状态机 v5（编号化声明）", ["code/workflow_arch5.py", "code/run_arch5_compare.py",
                                        "code/analyze_arch5.py"], "data/arch5_compare.jsonl",
     "code/analyze_arch5.py", "reports/REPORT_arch5.md"),
    ("⑥ v6 Stage-1（2×2，两阶段）", ["code/workflow_arch6.py", "code/run_arch6_stage1.py",
                                     "code/analyze_arch6.py", "code/v6_power.py"],
     "data/arch6_stage1.jsonl", "code/analyze_arch6.py", "reports/REPORT_arch6_stage1.md"),
    ("⑦ 论文（终稿 + PDF）", ["paper/PAPER_draft.md", "paper/build/build_paper_pdf.sh",
                              "paper/build/verify_paper_pdf.py"], "paper/runs/PAPER_draft.pdf",
     "paper/build/verify_paper_pdf.py", "paper/PAPER_draft.md"),
    ("⑧ 预注册（判据唯一来源）", ["prereg/PREREG_v5.md", "prereg/PREREG_v6.md"], "—", "—",
     "prereg/PREREG_v6.md"),
    ("⑨ 校验台账（sha256 绑 commit）", ["SHASUMS.md"], "—", "—", "SHASUMS.md"),
]


def sh(cmd: list) -> str:
    try:
        return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:
        return "ERR:%s" % e


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else "MISSING"


def main() -> None:
    head = sh(["git", "rev-parse", "HEAD"])
    branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    main_sha = sh(["git", "rev-parse", "origin/main"]) or "n/a"
    dirty = sh(["git", "status", "--short"])
    rows = []
    for name, files, datapath, entry, report in DIRECTIONS:
        fps = []
        for f in files:
            p = REPO / G / f
            fps.append("%s@%s" % (f, sha(p)) if p.exists() else "%s@MISSING" % f)
        dp = REPO / G / datapath if datapath not in ("—",) else None
        rows.append({
            "方向": name,
            "代码指纹": fps or ["（无代码，文档型）"],
            "实际执行版本": "%s @ %s" % (branch, head[:7]),
            "数据路径": ("group4_state_driven/" + datapath) if datapath != "—" else "—",
            "数据存在": ("✔" if dp and dp.exists() else ("—" if dp is None else "✘")),
            "分析入口": ("group4_state_driven/" + entry) if entry != "—" else "—",
            "当前报告": ("group4_state_driven/" + report) if report != "—" else "—",
            "报告指纹": sha(REPO / G / report) if report != "—" and (REPO / G / report).exists() else "—",
        })

    out = {
        "生成时间": subprocess.run(["date", "+%Y-%m-%d %H:%M:%S %Z"], capture_output=True,
                               text=True).stdout.strip(),
        "仓库": "lixvanran/agent-creativity-mechanism-study",
        "分支": BRANCH,
        "HEAD": head,
        "main": main_sha,
        "工作区是否干净": "是" if not dirty else "否（%d 项）" % len(dirty.splitlines()),
        "更正记录约定": "历史原件保留；报告与更正记录分开（更正写在报告的更正节，"
                        "不删旧表述）。v4 的「两种 0」更正见 REPORT_arch4.md §3.3b；"
                        "v3/v4/v5 根因收窄见 PAPER_draft.md §7.9 与摘要⑥。",
        "方向": rows,
    }
    p = Path("/workspace/第四组论证/experiment-design/WORKPACK1_EVIDENCE_INDEX.json")
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("\n✔ 已落盘：%s" % p)

    # 同时出一份可直接贴的 markdown 表
    md = ["# 工作包一 · 第四组证据入口表", "",
          "| 方向 | 代码指纹（sha256 前 16） | 实际执行版本 | 数据路径 | 分析入口 | 当前报告 |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| %s | %s | %s | %s | %s | %s |" % (
            r["方向"], "<br>".join("`%s`" % x for x in r["代码指纹"]),
            r["实际执行版本"], r["数据路径"], r["分析入口"], r["当前报告"]))
    md += ["", "**更正记录**：%s" % out["更正记录约定"], "",
           "**校验**：`group4_state_driven/SHASUMS.md`（sha256 绑 commit + 外部复核命令）"]
    Path("/workspace/第四组论证/experiment-design/WORKPACK1_EVIDENCE_INDEX.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8")
    print("✔ 已落盘 markdown 版")


if __name__ == "__main__":
    main()
