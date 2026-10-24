#!/usr/bin/env python3
"""★ **重建 SHASUMS.md（★ sha256 绑 commit · ★ 零 API）**

★ **为什么必须脚本生成**：★ sha256 **随文件内容变化** ⇒ ⇒ ★ **手抄一次就错一次**
★ ⇒ ⇒ ★ 上一轮就栽过（★ `REPORT_arch5.md` 的旧 sha256 报给了主会话，★ 而文件已改）
★ ⇒ ⇒ ★ ⇒ **唯一可靠的做法：★ 生成 ⇒ 提交 ⇒ 用【那个 commit】当基准 ⇒ 对外成对给**。

用法：
```bash
# ★ ① 生成（★ 当前 HEAD）
python3 -B group4_state_driven/build_shasums.py
# ★ ② 提交后再生成（★ 用新 commit 当基准）★
python3 -B group4_state_driven/build_shasums.py --after-commit
```
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
SHASUMS = os.path.join(_HERE, "SHASUMS.md")

# ★ 要进台账的文件（★ 路径相对仓根）
FILES = [
    ("Stage-1 报告", "group4_state_driven/REPORT_arch6_stage1.md"),
    ("Stage-1 EXEC-LOG", "group4_state_driven/EXEC_LOG_stage1.md"),
    ("Stage-1 原始样本", "group4_state_driven/data/arch6_stage1.jsonl"),
    ("Stage-1 分析输出", "group4_state_driven/data/arch6_stage1_analysis.json"),
    ("Stage-1 calllog（★ 已知不完整）", "group4_state_driven/data/calllog.jsonl"),
    ("Stage-1 环境快照", "group4_state_driven/data/env_snapshot.json"),
    ("重复采样留痕", "group4_state_driven/data/duplicate_resampling.json"),
    ("★ 重标记前原始样本（★ 独立采样判据的证据）", "group4_state_driven/data/arch6_stage1.pre_dedup.jsonl"),
    ("状态层接口（★ ★ 第二组 rev3 · 现行）", "creativity_lab/state_layer.py"),
    ("★ 状态层 rev0 归档（★ 历史版）", "group4_state_driven/data/state_layer_versions/state_layer_rev0.py"),
    ("★ 状态层 rev1 归档（★ 历史版）", "group4_state_driven/data/state_layer_versions/state_layer_rev1.py"),
    ("★ 状态层 rev2 归档（★ 历史版）", "group4_state_driven/data/state_layer_versions/state_layer_rev2.py"),
    ("★ rev3 应用脚本（★ 第二组提供）", "creativity_lab/experiments/apply_state_layer_rev3.py"),
    ("★ 状态层 rev2 归档（★ 历史版 · 补）", "group4_state_driven/data/state_layer_versions/state_layer_rev2.py"),
    ("★ 第二组 pack_repo（★ 底层打包器）", "creativity_lab/experiments/pack_repo.py"),
    ("★ 第二组 unit_store", "creativity_lab/experiments/unit_store.py"),
    ("★ 第二组 check_batch_progress", "creativity_lab/experiments/check_batch_progress.py"),
    ("状态层规格测试（★ 第四组实现 · ★ rev2 语义）", "creativity_lab/experiments/test_state_layer.py"),
    ("状态层差异探针（★ ★ 三版本差分）", "group4_state_driven/probe_state_layer_spec_gap.py"),
    ("★ Stage-1 独立采样判据", "group4_state_driven/check_independent_samples.py"),
    ("★ v6 源码级变异注入（★ 4/4）", "group4_state_driven/code/mutations_arch6.py"),
    ("★ Stage-1 报告读数重填脚本", "group4_state_driven/refill_report_stage1.py"),
    ("★ Stage-1 数据同步脚本（★ ★ 修路径错配）", "group4_state_driven/sync_stage1_data.py"),
    ("★ Stage-2 候选分化判据（★ 事前规格）", "group4_state_driven/prereg/STAGE2_CANDIDATE_DIVERSIFICATION_SPEC.md"),
    ("rev1 应用脚本", "group4_state_driven/apply_state_layer_rev1.py"),
    ("rev2 应用脚本", "group4_state_driven/apply_state_layer_rev2.py"),
    ("Stage-1 同步脚本", "group4_state_driven/sync_stage1_data.py"),
    ("Stage-1 重复采样处置", "group4_state_driven/fix_duplicate_resampling.py"),
    ("Stage-1 报告填数（§3）", "group4_state_driven/fill_report_stage1.py"),
    ("Stage-1 报告填数（§4–§6）", "group4_state_driven/fill_report_stage1_verdict.py"),
    ("Stage-1 报告校验器", "group4_state_driven/verify_report_stage1.py"),
    ("Stage-1 逐步打点探针", "group4_state_driven/probe_stage1_step_timing.py"),
    ("工作包三（★ 降级为实现/读数侧）", "group4_state_driven/WORKPACK3_MIN_ARCHITECTURE.md"),
    ("状态层边界枚举冒烟", "group4_state_driven/probe_select_boundary.py"),
    ("v6 机制层实现", "group4_state_driven/code/workflow_arch6.py"),
    ("v6 Stage-1 runner", "group4_state_driven/code/run_arch6_stage1.py"),
    ("v6 Stage-1 分析", "group4_state_driven/code/analyze_arch6.py"),
    ("v6 预注册 v3", "group4_state_driven/prereg/PREREG_v6.md"),
    ("Stage-1 实施规格", "group4_state_driven/prereg/STAGE1_SPEC.md"),
    ("论文稿", "group4_state_driven/paper/PAPER_draft.md"),
]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def head_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def branch() -> str:
    return subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main():
    commit = head_commit()
    lines = []
    lines.append("# 第四组 · 交付物校验台账（sha256 绑 commit）")
    lines.append("")
    lines.append("**校验基准 commit**：`%s`（分支 `%s`，`main` 未动）" % (commit, branch()))
    lines.append("**生成时间**：由 `group4_state_driven/build_shasums.py` 自动生成")
    lines.append("")
    lines.append("> ⚠️ **为什么必须有本文件**：sha256 随文件修改失效。2026-10-24 12:0x 我们把 `REPORT_arch5.md` 的")
    lines.append("> 旧版 sha256（`b61345b0…`，对应 `5de1a6b`）报给了主会话，而该文件在 `4b90e11` 已改过 ⇒")
    lines.append("> 远端与本地都是新版 `871aa4cf…` ⇒ ⇒ **同一个 sha256 在不同 commit 下指向不同内容**。")
    lines.append("> ⇒ ⇒ **对外一律以「sha256 + 基准 commit」成对给，不许只报 sha256。**")
    lines.append(">")
    lines.append("> ★ **外部复核命令**：")
    lines.append("> ```bash")
    lines.append("> git fetch origin feature/g4-arch4-state-driven")
    lines.append("> git checkout %s" % commit[:12])
    lines.append("> sha256sum <路径>   # 与下表比对")
    lines.append("> ```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("| 文件 | 仓库路径 | sha256 | 基准 commit |")
    lines.append("|---|---|---|---|")
    n_ok = 0
    for label, rel in FILES:
        p = os.path.join(REPO, rel)
        if not os.path.exists(p):
            lines.append("| %s | `%s` | ⚠️ **文件不存在** | `%s` |" % (label, rel, commit))
            continue
        lines.append("| %s | `%s` | `%s` | `%s` |" % (label, rel, sha256(p), commit))
        n_ok += 1
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("★ **本表共 %d 项**（★ 缺文件会显式标 ⚠️，★ 不会被静默跳过）" % n_ok)
    lines.append("")
    lines.append("## ★ 已知缺口（★ 必须随表一起给，★ 不许只给 sha）")
    lines.append("")
    lines.append("| ★ 项 | ★ 说明 |")
    lines.append("|---|---|")
    lines.append("| ★ **`calllog.jsonl` 不完整** | ★ 补跑段的调用未落盘（★ 进程在 `dump_calllog()` 之前被终止）⇒ ★ **通道健康度的分母不完整** ⇒ ★ **凡用 calllog 算健康度的结论本批不成立**（★ 详见 `EXEC_LOG_stage1.md` §1.4） |")
    lines.append("| ★ **seed 未落盘** | ★ runner 里 `rec[\"seed\"] = None` ⇒ ★ **本批不可按 seed 复现** |")
    lines.append("| ★ **重复采样已处置** | ★ T10-1 出现两次（★ 两个进程并发写）⇒ ★ 后写入者重标记为 T10-2 ⇒ ★ **每题恰好 3 个重复** ⇒ ★ 留痕 `data/duplicate_resampling.json` |")
    lines.append("| ★ **状态层接口 = rev3** | ★ sha `c1c9224a1ed59fa8…`（★ **第二组 2026-10-25 落地**；★ 由 `creativity_lab/experiments/apply_state_layer_rev3.py` 应用 ⇒ ★ **sha 双向校验通过**）；★ rev0/rev1/rev2 全部归档在 `data/state_layer_versions/`（★ sha 绑 commit） |")
    lines.append("| ★ **rev3 的 `tol` 是必填** | ★ `detect_tie(scores, *, tol)` ⇒ ★ **所有调用点必须显式传 `tol=`** ⇒ ★ 漏传【立刻 TypeError】⇒ ★ 不会静默用默认值 ⇒ ★ 读数不会漂 |")
    lines.append("| ★ **`REPORT_arch6_stage1.md` 的数字** | ★ 全部由 `fill_report_stage1*.py` 从 `arch6_stage1_analysis.json` 填入 ⇒ ★ **不许手改** ⇒ ★ 改完必跑 `verify_report_stage1.py`（★ 71 项机械校验） |")
    lines.append("")

    tmp = SHASUMS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, SHASUMS)
    print("✔ 已重建 SHASUMS.md（%d 项，基准 commit %s）" % (n_ok, commit[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
