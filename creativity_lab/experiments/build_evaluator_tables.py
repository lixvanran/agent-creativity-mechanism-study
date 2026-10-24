#!/usr/bin/env python3
"""**评估器强度实验的证据表**（程序化生成）。

> 落点：`creativity_lab/experiments/build_evaluator_tables.py`
> 输入：`runs/evaluator-strength-2026-10-24/manifest.json` + 组文件
> 输出：`docs/cmp8/routes/COLLAPSE/eval/results/EVALUATOR-*.md`
>
> ★ 读数纪律：
> 1. **三种一致率分开**（见 `METHOD.md`）：判官—金标 / 位置 / 评估器—评估器。
> 2. **位置一致率 <0.5 ⇒ vote 读数不可用** ⇒ 不得计入任何结论（只作"vote 不可用"的证据）。
> 3. 跨评估器一致率**低就是发现本身**（它是本实验的因变量），不是"对比不可用"。
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.metrics import self_coverage      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN = os.path.join(ROOT, "runs", "evaluator-strength-2026-10-24")
OUT = os.path.join(ROOT, "docs", "cmp8", "routes", "COLLAPSE", "eval", "results")
EVLABEL = {"lex": "词块独特度（弱）", "value": "LLM value（ToT 式）", "vote": "LLM vote（ToT 式）"}
# ★ 位置一致率 ≥0.5 才算可用（第四组定的硬闸）
POS_GATE = 0.5


def med(v: List[float]):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def main() -> int:
    man = json.load(open(os.path.join(RUN, "manifest.json"), encoding="utf-8"))
    h = dict(man["health"])
    # ★ 离线重算健康度：manifest 里那版把"内容长度未达标"当成"传输失败"
    #   （min_ok=200 的坑）⇒ 实际传输成功率要用 calllog 的 content_len 重算
    cl_p = os.path.join(RUN, "calllog.jsonl")
    if os.path.exists(cl_p):
        cl = [json.loads(l) for l in open(cl_p, encoding="utf-8")]
        if cl:
            h["n_calls_total"] = len(cl)
            h["n_calls_failed"] = sum(1 for c in cl if c.get("content_len", 0) == 0)
            h["n_calls_empty"] = h["n_calls_failed"]
            h["channel_health"] = round(1 - h["n_calls_failed"] / len(cl), 4)
            h["_note"] = "健康度已用 calllog 离线重算（传输成功 = content_len>0）"
    groups = man["groups"]
    # arts 不在 manifest ⇒ 从组文件补
    for g in groups:
        gp = os.path.join(RUN, "group_%s_r%d.json" % (g["tid"], g["rep"]))
        if os.path.exists(gp):
            g["arts"] = json.load(open(gp, encoding="utf-8")).get("arts")

    # ---- 表1：通道 + 一致性 ----
    t1 = ["# 表E1 · 通道健康与一致性（**三种一致率分开**）\n",
          "\n| 项 | 值 | 含义 |\n|---|---:|---|",
          "| 组数 | %d | |" % h["n_groups"],
          "| 调用总数 | %d | |" % h["n_calls_total"],
          "| 调用失败 | %d | |" % h["n_calls_failed"],
          "| **通道健康度** | **%s** | ≥0.9 ⇒ 读数生效 |" % h["channel_health"],
          "| **位置一致率**（vote，两排列） | **%s** | ★ 硬闸 ≥0.5；低于 ⇒ **vote 读数不可用** |" % h["position_consistency"],
          ]
    for k, v in h.get("pairwise_agreement", {}).items():
        a, b = k.split("|")
        t1.append("| 评估器—评估器 一致率 `%s` | %s | ★ **低就是发现本身**（本实验的因变量） |" % (k, v))
    t1.append("\n> ★ **判官同源**：评估器与被评产出同属 MiniMax ⇒ 按纪律**只作交叉验证的一端**，"
              "**不得作主判据**；跨厂商复核本轮**未做**（OpenRouter 额度 `limit_remaining=0`）。\n")
    t1.append("> ★ **vote 不可用**时，**只用 `lex` 与 `value`** 参与跨评估器一致率计算。\n")

    # ---- 表2：逐组 ----
    t2 = ["# 表E2 · 逐组：各评估器选了哪一支 + 读数\n",
          "\n| 组 | lex | value | vote(两排列) | 位置一致 | lex 读数 | value 读数 | vote 读数 |",
          "|---|--:|--:|---|:--:|---|---|---|"]
    for g in groups:
        e = g["evaluators"]
        cells = []
        for ev in ("lex", "value", "vote"):
            r = g["readings"].get(ev, {})
            if not r.get("valid"):
                cells.append("**不可用**")
            else:
                cells.append("w=%d 深=%.3f 自覆盖=%.3f"
                             % (r["covered_branches"], r["survival_rate"],
                                self_coverage(g.get("arts") or [], r["text"])))
        t2.append("| %s r%d | %d | %d | %s | %s | %s | %s | %s |"
                  % (g["tid"], g["rep"], e["lex"]["pick"], e["value"]["pick"],
                     "/".join(str(x) for x in e["vote"]["picks"]),
                     "✔" if e["vote"]["position_consistent"] else "✘",
                     cells[0], cells[1], cells[2]))

    # ---- 表3：聚合读数对评估器敏感吗？ ----
    t3 = ["# 表E3 · 换评估器，**聚合读数**变不变？\n",
          "\n> ★ 这张表决定第三轮报告里「融合门是双输」那句结论**稳不稳**。\n",
          "\n| 评估器 | 选中支 自覆盖率 | 选中支 面宽@0.3 | 选中支 面深 | 语义面深 | 可用组数 |\n",
          "|---|--:|--:|--:|--:|--:|"]
    for ev in ("lex", "value", "vote"):
        sc, w, dep, sd, n = [], [], [], [], 0
        for g in groups:
            r = g["readings"].get(ev, {})
            if not r.get("valid"):
                continue
            n += 1
            sc.append(self_coverage(g.get("arts") or [], r["text"]))
            w.append(r["covered_branches"]); dep.append(r["survival_rate"])
            sd.append((r.get("emb") or {}).get("mean_inc"))
        t3.append("| %s | %.3f | %.1f | %.3f | %.3f | %d |"
                  % (EVLABEL[ev], med(sc) or 0, med(w) or 0, med(dep) or 0, med(sd) or 0, n))

    # ---- 表4：跨评估器一致率（可用评估器之间）----
    t4 = ["# 表E4 · 跨评估器一致率（**只用可用评估器**）\n",
          "\n| 对比 | 一致组数 | 一致率 | 读法 |\n|---|--:|--:|---|"]
    for ev in ("lex", "value"):
        for ev2 in ("lex", "value"):
            if ev >= ev2:
                continue
            c = 0
            for g in groups:
                p1 = g["evaluators"][ev].get("pick", -1)
                p2 = g["evaluators"][ev2].get("pick", -1)
                if p1 >= 0 and p2 >= 0 and p1 == p2:
                    c += 1
            rate = c / max(len(groups), 1)
            t4.append("| `%s` vs `%s` | %d/%d | **%.2f** | %s |"
                      % (ev, ev2, c, len(groups), rate,
                         "★ **极不稳定** ⇒ 「选哪支」这件事本身在开放任务上不可靠"
                         if rate < 0.5 else "尚可"))
    t4.append("\n> ★ **注意逻辑**：这里的一致率**低就是发现本身**（因变量），"
              "不能用「一致率低 ⇒ 不可用」那条硬闸否定自己——那条硬闸针对的是"
              "**判官—金标**与**位置**一致率（见 `METHOD.md`）。\n")

    for name, body in (("EVALUATOR-1-CHANNEL.md", t1), ("EVALUATOR-2-PER-GROUP.md", t2),
                       ("EVALUATOR-3-AGGREGATE.md", t3), ("EVALUATOR-4-AGREEMENT.md", t4)):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")
        print("✓ %s" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
