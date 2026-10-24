# 工作包一 · 第四组证据入口表

| 方向 | 代码指纹（sha256 前 16） | 实际执行版本 | 数据路径 | 分析入口 | 当前报告 |
|---|---|---|---|---|---|
| ① 正式论证（第四组论证） | `（无代码，文档型）` | feature/g4-arch4-state-driven @ 738669a | group4_state_driven/evidence-check/ | — | group4_state_driven/第四组论证.md / 第四组论证.pdf |
| ② C1/C2 状态机（Phase 0/1） | `code/runner2.py@MISSING`<br>`code/metrics2.py@MISSING`<br>`code/gates.py@MISSING`<br>`code/probe_swap.py@MISSING`<br>`code/analyze2.py@MISSING`<br>`code/analyze_ckf.py@MISSING`<br>`code/report_p1.py@MISSING` | feature/g4-arch4-state-driven @ 738669a | group4_state_driven/data/ | group4_state_driven/code/analyze2.py | group4_state_driven/reports/REPORT_p1.md |
| ③ 架构化状态机 v1–v3 | `code/workflow_arch.py@MISSING`<br>`code/workflow_arch2.py@MISSING`<br>`code/workflow_arch3.py@e9b24fea3815906c` | feature/g4-arch4-state-driven @ 738669a | group4_state_driven/data/arch3_compare.jsonl | group4_state_driven/code/analyze_arch3.py | group4_state_driven/reports/REPORT_arch3.md |
| ④ 架构化状态机 v4（状态进选择层） | `code/workflow_arch4.py@8ab38ca208f17f5c`<br>`code/run_arch4_compare.py@0290f5ffc8e7c9dc`<br>`code/analyze_arch4.py@4c5536b9481c0fc7` | feature/g4-arch4-state-driven @ 738669a | group4_state_driven/data/arch4_compare.jsonl | group4_state_driven/code/analyze_arch4.py | group4_state_driven/reports/REPORT_arch4.md |
| ⑤ 架构化状态机 v5（编号化声明） | `code/workflow_arch5.py@f93f5f60a3add86f`<br>`code/run_arch5_compare.py@75ed693b20a04607`<br>`code/analyze_arch5.py@152038ba48887dbe` | feature/g4-arch4-state-driven @ 738669a | group4_state_driven/data/arch5_compare.jsonl | group4_state_driven/code/analyze_arch5.py | group4_state_driven/reports/REPORT_arch5.md |
| ⑥ v6 Stage-1（2×2，两阶段） | `code/workflow_arch6.py@902e93861b99060f`<br>`code/run_arch6_stage1.py@8a17f4277bf1e1ef`<br>`code/analyze_arch6.py@78f7b359d388219f`<br>`code/v6_power.py@462b4b984a7bd6ae` | feature/g4-arch4-state-driven @ 738669a | group4_state_driven/data/arch6_stage1.jsonl | group4_state_driven/code/analyze_arch6.py | group4_state_driven/reports/REPORT_arch6_stage1.md |
| ⑦ 论文（终稿 + PDF） | `paper/PAPER_draft.md@a3a0b5e867aa1648`<br>`paper/build/build_paper_pdf.sh@b52987c3188c5ecc`<br>`paper/build/verify_paper_pdf.py@141fa1a7ba1e8831` | feature/g4-arch4-state-driven @ 738669a | group4_state_driven/paper/runs/PAPER_draft.pdf | group4_state_driven/paper/build/verify_paper_pdf.py | group4_state_driven/paper/PAPER_draft.md |
| ⑧ 预注册（判据唯一来源） | `prereg/PREREG_v5.md@06a0f00e538e958e`<br>`prereg/PREREG_v6.md@31c81dfc8ddf68a3` | feature/g4-arch4-state-driven @ 738669a | — | — | group4_state_driven/prereg/PREREG_v6.md |
| ⑨ 校验台账（sha256 绑 commit） | `SHASUMS.md@656596d978ac4c80` | feature/g4-arch4-state-driven @ 738669a | — | — | group4_state_driven/SHASUMS.md |

**更正记录**：历史原件保留；报告与更正记录分开（更正写在报告的更正节，不删旧表述）。v4 的「两种 0」更正见 REPORT_arch4.md §3.3b；v3/v4/v5 根因收窄见 PAPER_draft.md §7.9 与摘要⑥。

**校验**：`group4_state_driven/SHASUMS.md`（sha256 绑 commit + 外部复核命令）
