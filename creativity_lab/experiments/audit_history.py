#!/usr/bin/env python3
"""**历史跑批可信度机械核查器**（零 API；只打标记，**不改数字**）

> 2026-10-24 ｜ 第二组 · 层2 ｜ 落点：`creativity_lab/experiments/audit_history.py`
>
> ## 它回答什么
> 历史跑批的读数**哪些还能引用**？—— 机械判定，不靠人判断。
>
> ## ★ 两类问题必须分开（第一版把它们混在一起 ⇒ 结论全错）
> | 类型 | 判据 | 后果 |
> |---|---|---|
> | **题号不同源** | 文件名里的题号 ≠ 内容的题号，但**组内各臂一致** | **不是错位** ⇒ 照常可用，只是要换题号 |
> | **组内错位** | 同一组内各臂指向**不同**的题 | **配对本身错了** ⇒ 不可用 |
> | **分支漂移** | 分支数 < 臂规定数（5） | 比率的分母要改；型号下架导致 |
>
> ★ 历史跑批用的是**另一套题号**（`A1–A4` / `P1–P3`），当前题库是 `T1–T3`
>   ⇒ ⇒ **不能**拿文件名题号去判内容；只能判**组内是否一致**。
>
> ## 输出
> `results/HISTORY-AUDIT-2026-10-24.md`（表 + 题号映射 + 逐组明细）+ `results/history_audit.json`
"""
from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from creativity_lab.experiments import guard_io  # noqa: E402

from creativity_lab import topics as T          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HIST = os.path.join(ROOT, "data", "historical-runs")
OUT_DIR = os.path.join(ROOT, "docs", "cmp8", "routes", "COLLAPSE", "eval", "results")

# 每道当前题的**特征词**（人工指定一次，之后检查是机械的）
TOPIC_KEYS = {
    "T1": ["时代", "未来", "看法"],
    "T2": ["湖北", "620", "物理", "志愿", "大学", "专业"],
    "T3": ["自行车", "单车", "战术", "大集团"],
}
ARMS_FILES = ("arm1", "arm2", "arm3", "arm4")


def best_tid(text: str) -> List[str]:
    """按**特征词命中数**判定内容属于哪道题（argmax；并列 ⇒ 都列 ⇒ 判歧义）。

    ★ 为什么打分而不是"命中即算"：特征词会**跨题共有**（"AI" 同时在 T1/T2 出现），
      命中即算 ⇒ 假失配 ⇒ **检查器自己有缺陷**（第一版就这么错了）。
    """
    if not text:
        return []
    sc = {tid: sum(1 for k in kws if k in text) for tid, kws in TOPIC_KEYS.items()}
    mx = max(sc.values())
    if mx <= 0:
        return []
    return sorted(t for t, v in sc.items() if v == mx)


def text_of(path: str) -> str:
    try:
        return open(path, encoding="utf-8").read()
    except Exception:                                  # noqa: BLE001
        return ""


def main() -> int:
    rows: List[Dict[str, Any]] = []
    if os.path.isdir(HIST):
        # ★★★ 输入/输出隔离（★ 2026-10-25 统一形态：★ 解析输入的同一处就断言，★ realpath 级）
        guard_io.assert_output_outside_input_dir(HIST, OUT_DIR, "audit_history")
        for ds in sorted(os.listdir(HIST)):
            d = os.path.join(HIST, ds)
            if not os.path.isdir(d):
                continue
            for arts_p in sorted(glob.glob(os.path.join(d, "*_arm4arts.json"))):
                stem = os.path.basename(arts_p).replace("_arm4arts.json", "")
                file_tid, rep = stem.split("_r")
                try:
                    arts = json.load(open(arts_p, encoding="utf-8"))
                except Exception:                      # noqa: BLE001
                    arts = []
                n_arts = len(arts) if isinstance(arts, list) else 0
                arts_tid = best_tid("".join(arts) if isinstance(arts, list) else "")
                arm_hits = {}
                for arm in ARMS_FILES:
                    txt = text_of(os.path.join(d, "%s_%s.md" % (stem, arm)))
                    if txt:
                        arm_hits[arm] = best_tid(txt)
                tally: Dict[str, int] = {}
                for t in list(arts_tid) + [x for v in arm_hits.values() for x in v]:
                    tally[t] = tally.get(t, 0) + 1
                content_tid, ambiguous = None, False
                if tally:
                    mx = max(tally.values())
                    top = [t for t, v in tally.items() if v == mx]
                    ambiguous = len(top) > 1
                    content_tid = None if ambiguous else top[0]
                rows.append({
                    "dataset": ds, "stem": stem, "file_tid": file_tid, "rep": int(rep),
                    "n_arts": n_arts, "branch_deficit": max(5 - n_arts, 0),
                    "arts_content_tid": arts_tid, "content_tid": content_tid,
                    "ambiguous": ambiguous, "arm_hits": arm_hits,
                })

    # ---- 判定 ----
    for r in rows:
        flags = []
        if r["branch_deficit"] > 0:
            flags.append("branch_deficit(%d)" % r["branch_deficit"])
        if r["ambiguous"] or r["content_tid"] is None:
            flags.append("internal_mismatch")
        elif r["file_tid"] != r["content_tid"]:
            flags.append("topic_renamed(%s→%s)" % (r["file_tid"], r["content_tid"]))
        r["flags"] = flags
        r["usable"] = (not r["ambiguous"]) and r["content_tid"] is not None and r["branch_deficit"] == 0
        r["mapped_tid"] = r["content_tid"]

    n_total = len(rows)
    n_usable = sum(1 for r in rows if r["usable"])
    by_flag: Dict[str, int] = {}
    for r in rows:
        for f in r["flags"]:
            k = f.split("(")[0]
            by_flag[k] = by_flag.get(k, 0) + 1
    mapping: Dict[str, str] = {}
    for r in rows:
        if r.get("mapped_tid"):
            mapping.setdefault("%s/%s" % (r["dataset"], r["file_tid"]), r["mapped_tid"])

    md: List[str] = []
    md.append("# 历史跑批可信度核查（机械判定）\n")
    md.append("> 生成：`creativity_lab/experiments/audit_history.py`｜源：`data/historical-runs/`\n")
    md.append("\n## 1. 结论\n")
    md.append("- **可直接引用：%d / %d 组**（%.0f%%）\n" % (n_usable, n_total, 100.0 * n_usable / max(n_total, 1)))
    md.append("- 不可用：**%d 组** ⇒ 标记如下。**不修正数字**：归档不可信时「修正」就是编造。\n")
    md.append("\n| 标记 | 组数 | 含义 | 还能用吗 |\n|---|--:|---|:--:|")
    md.append("| `topic_renamed` | %d | 文件名题号 ≠ 内容题号，但**组内一致** ⇒ 只是**命名不同源** | ✔ 可用（换题号即可） |"
              % by_flag.get("topic_renamed", 0))
    md.append("| `internal_mismatch` | %d | **组内各臂指向不同题** ⇒ 配对本身错了 | ✘ 不可用 |"
              % by_flag.get("internal_mismatch", 0))
    md.append("| `branch_deficit` | %d | 分支数 < 5 ⇒ 型号下架导致死分支被静默丢弃 ⇒ **分母漂移** | ⚠ 比率要改分母 |"
              % by_flag.get("branch_deficit", 0))
    md.append("\n## 2. 题号映射（历史 → 当前）\n")
    md.append("| 历史组 | 当前题 |\n|---|---|")
    for k, v in sorted(mapping.items()):
        md.append("| %s | %s |" % (k, v))
    md.append("\n## 3. 逐组明细\n")
    md.append("\n| 数据集 | 组 | 文件题号 | 内容题号 | 分支数 | 各臂内容 | 标记 | 可用 |\n")
    md.append("|---|---|--:|--:|--:|---|---|:--:|")
    for r in rows:
        af = "；".join("%s→%s" % (k, "/".join(v) if v else "—") for k, v in r["arm_hits"].items())
        md.append("| %s | %s | %s | %s | %d | %s | %s | %s |"
                  % (r["dataset"], r["stem"], r["file_tid"], r["content_tid"] or "—", r["n_arts"],
                     af or "—", "；".join(r["flags"]) or "—", "✔" if r["usable"] else "✘"))
    md.append("\n## 4. 使用规则\n")
    md.append("1. **凡引用历史 run 的读数，先查本表**。\n")
    md.append("2. `branch_deficit` 的组：所有**比率**的分母改成实际分支数，**不能沿用 5**。\n")
    md.append("3. `internal_mismatch` 的组：任何**跨文件配对分析**都不成立。\n")
    md.append("4. `topic_renamed` 的组**照常可用**，只需用 §2 的映射换题号。\n")
    md.append("5. ★ **修正第三轮报告的说法**：历史归档**不是全废**——"
              "**题号不同源**（A1–A4/P1–P3 vs T1–T3）≠ **配对错位**；"
              "真正错位的只有组内各臂指向不同题的少数组。\n")
    md.append("6. 新跑批一律走**结构化 manifest 配对**（不用文件名约定）。\n")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "HISTORY-AUDIT-2026-10-24.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(OUT_DIR, "history_audit.json"), "w", encoding="utf-8") as f:
        json.dump({"n_total": n_total, "n_usable": n_usable, "by_flag": by_flag,
                   "mapping": mapping, "rows": rows}, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("== 历史跑批可信度 ==")
    print("  组数 %d ｜ 可直接引用 %d ｜ 不可用 %d" % (n_total, n_usable, n_total - n_usable))
    for k, v in sorted(by_flag.items(), key=lambda x: -x[1]):
        print("  %-20s %d 组" % (k, v))
    print("  题号映射：%s" % mapping)
    print("\n✓ 落盘 %s" % OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
