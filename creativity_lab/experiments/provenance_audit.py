#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 报告读数的【出处覆盖率审计】★：★ 分档 + 未核对区显式列出 ★

> 落点：`creativity_lab/experiments/provenance_audit.py`
> 用法：
>   python3 -B creativity_lab/experiments/provenance_audit.py \
>       --report docs/交付/第二组交付报告_2026-10-25.md \
>       --dump   docs/交付/读数快照/topo-arm-v2-n151/generated \
>       --coverage docs/交付/读数快照/topo-arm-v2-n151/verify_coverage.json
>
> ★ ★★ 为什么要有这个（★ 2026-10-26 · 第 1 层论证线的两条硬发现逼出来的 ★）★★
★ ① **「43/43 全绿」的覆盖率只有 54.8%**（★ 125/228 ★）⇒ ★ **「全绿」只证明【被覆盖的那部分对】，
★    绝不等于【全文每个数都验过】★★ ⇒ ⇒ ★ 本工具算的是**覆盖率**，★ 不是「全绿」★
★ ② ★★ **「靠数值出现去推断某个数来自哪个数据源」不可靠**★★
★    （★ json 是全精度 `0.07059805724397743`、★ 正文是舍入值 `0.0705` ⇒ ★ 匹配不上；★★
★      ★★ 更糟：**同值 ≠ 同源** ——★ 那个 `0.0705` 在 json 里命中的是【另一个指标】的巧合值 ★★）
★    ⇒ ⇒ ★ **★ 本工具【绝不】做「数值 → 来源」的自动推断 ★★**
★    ⇒ ⇒ ★ 它只做三件【不会错】的事：★
★       Ⅰ **位置归属**：★ 每个数值落在【哪个段】★（★ 不是「它来自哪个 json」★）★
★       Ⅱ **构造性核**：★ 生成段与【生成器落盘的片段文件】★ **逐字节**一致 ★
★           ⇒ ★ 人直接改【产物】也会被抓 ★（★ 对方的「反向盲区」★）
★       Ⅲ **缺口显式化**：★ 【未核对区】的数值清单 ★ **每次运行都打印** ★ ⇒ ★ 不隐藏 ★
>
> ★ ★★ 三档（★ 与第 1 层论证线的 DATA_PROVENANCE 四档同构 ★★）：★
★ | 档 | 含义 | 判据 |
★ |:-:|---|---|
★ | **A** | ★ **逐位核对覆盖** | ★ 被 `verify_report_numbers.py` 逐位·逐格核对过 ★（★ 按【值】匹配 ⇒ ★ **上界** ★）★ |
★ | **B** | ★ **构造性覆盖** | ★ 落在生成段内 ★ ⇒ ★ 与生成器片段**逐字节**一致 ★ ⇒ ★ **但未被逐位核对** ★ |
★ | **C** | ★ ★ **未核对区** | ★ **不在生成段内** ⇒ ★ **出处必须由人显式登记** ★ ⇒ ★ **本工具不推断** ★ |
>
> ★ ★★ 精确口径只有一个：★ **verify 实际逐位核对了多少个期望值**（★ 见主指标 ★）★★
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ★ 生成段 marker → 片段文件名（★ 与 fill_report_partial 的常量对应 ★）
MARKERS = [
    ("<!-- BEGIN:6.10.0 -->", "<!-- END:6.10.0 -->", "6.10.0"),
    ("<!-- BEGIN:6.10.0b -->", "<!-- END:6.10.0b -->", "6.10.0b"),
    ("<!-- BEGIN:6.10.0c -->", "<!-- END:6.10.0c -->", "6.10.0c"),
    ("<!-- BEGIN:6.10.0d -->", "<!-- END:6.10.0d -->", "6.10.0d"),
    ("<!-- BEGIN:6.10.2b -->", "<!-- END:6.10.2b -->", "6.10.2b"),
    ("<!-- BEGIN:6.10.5 -->", "<!-- END:6.10.5 -->", "6.10.5"),
]

# ★ ★ 自身排除：★ §6.10.0d 是【覆盖率报告本身】⇒ ★ 它不计入自己的分档（★ 避免递归 ★）
SELF = "6.10.0d"

# ★ 数值 token：★ 可选负号 + 整数 + 可选小数（★ 覆盖 σ 系数与百分比基数 ★）
NUM = re.compile(r"-?\d+(?:\.\d{1,3})?")


def norm_tok(t: str) -> str:
    """★ 数值 token 归一化：★ 只去符号（★ 不改数值本身 ★）"""
    t = t.replace("−", "-")
    if t.startswith("-"):
        t = t[1:]
    try:
        f = float(t)
    except ValueError:
        return t
    return ("%.2f" % f).rstrip("0").rstrip(".") or "0"


def section_of(pos: int, spans):
    for a, b, name in spans:
        if a <= pos < b:
            return name
    return None


def short_label(title: str) -> str:
    """★ 章节标题 → 短标签：★ 截到「|」或「（」之前 ⇒ ★ 不含管道符 ⇒ 不破坏 markdown 表格 ★
    ★ ★ 这条不是洁癖：★ 含「|」的表格行会把整个表结构打散 ★ ★"""
    t = re.split(r"[|（|]", title)[0].strip()
    return t[:40] or "(无名段)"


def audit(rep: str, dump_dir: str, covered=None):
    errs = []
    covered = covered or set()
    # ── Ⅰ 生成段区间 + 构造性逐字节核 ──
    spans = []
    for beg, end, name in MARKERS:
        if rep.count(beg) != 1 or rep.count(end) != 1:
            errs.append("生成段 %s 的 marker 命中 %d/%d 次（★ 必须各 1 次 ★）"
                        % (name, rep.count(beg), rep.count(end)))
            continue
        i = rep.index(beg)
        j = rep.index(end)
        spans.append((i, j, name))
    for a, b, name in spans:
        body = rep[rep.index("\n", a) + 1:b].rstrip("\n")
        fp = os.path.join(dump_dir, "%s.md" % name)
        if not os.path.isfile(fp):
            errs.append("生成片段文件缺失：%s（★ 先跑 fill_report_partial --dump-generated ★）" % fp)
            continue
        dumped = open(fp, encoding="utf-8").read().rstrip("\n")
        if body != dumped:
            errs.append("生成段 %s 与生成器片段【逐字节不一致】（★ 人改过产物？★）" % name)
    # ── Ⅱ 数值分档 ──
    counts = {"A": 0, "B": 0, "C": 0}
    unverified = []
    for m in NUM.finditer(rep):
        sec = section_of(m.start(), spans)
        if sec == SELF:
            continue                      # ★ 自身不计入（★ 递归 ★）★
        if sec is not None and norm_tok(m.group(0)) in covered:
            counts["A"] += 1
            continue
        if sec is None:
            head = rep.rfind("\n### ", 0, m.start())
            lab = short_label(rep[head + 1:].split("\n", 1)[0]) if head >= 0 else "(文首)"
            counts["C"] += 1
            unverified.append({"value": m.group(0), "section": lab})
        else:
            counts["B"] += 1
    total = sum(counts.values())
    by_sec = {}
    for u in unverified:
        by_sec.setdefault(u["section"], set()).add(u["value"])
    gap = {k: sorted(v) for k, v in sorted(by_sec.items())}
    return errs, counts, total, gap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--dump", required=True)
    ap.add_argument("--coverage", default=None,
                    help="★ verify_report_numbers.py --json-out 的输出（★ A 档的覆盖集合 ★）")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()
    rep = open(a.report, encoding="utf-8").read()
    covered = set()
    if a.coverage and os.path.isfile(a.coverage):
        covered = set(json.load(open(a.coverage, encoding="utf-8")).get("covered") or [])
    errs, counts, total, gap = audit(rep, a.dump, covered)

    print("== ★ 读数出处覆盖率审计（★ 2026-10-26 ★）==")
    print("   ★★★ 主指标（★ 唯一精确的口径 ★）：★ verify 实际逐位核对的期望值 = ★ %d 个 ★" % len(covered))
    print("   ★ ★ ★ 下面的 A/B/C 计数是【段级 + 值级】的近似：★ A 档按【值】匹配 ⇒ ★ **是上界** ★")
    print("   ★ ★ ★ 因为【同值 ≠ 同源】（★ 第 1 层论证线 2026-10-26 实证 ★）⇒ ★ 不可当精确覆盖率 ★")
    print("   A 档（★ 逐位核对覆盖·上界 ★）: %5d  (%.1f%%)" % (counts["A"], 100.0 * counts["A"] / max(total, 1)))
    print("   B 档（★ 构造性覆盖·逐字节 ★） : %5d  (%.1f%%)" % (counts["B"], 100.0 * counts["B"] / max(total, 1)))
    print("   C 档（★ ★ 未核对区 ★）        : %5d  (%.1f%%)" % (counts["C"], 100.0 * counts["C"] / max(total, 1)))
    print("   合计数值 token                : %5d" % total)
    print("   ★ ★ 段级+值级覆盖（★ 上界 ★）= (A+B)/合计 = %.1f%% ★ ★"
          % (100.0 * (counts["A"] + counts["B"]) / max(total, 1)))
    print("   ★ ★ 精确口径：★ 逐位核对了 %d 个期望值，★ 全文数值 token %d 个 ★" % (len(covered), total))
    print("   ★ ★ 「全绿」≠「全文每个数都验过」★ ★ ⇒ ★ 缺口在上面，★ 不隐藏 ★")
    print()
    print("== ★ C 档：未核对区的数值（★ 按段汇总 · 去重 · 短标签 ★）==")
    for sec, vals in gap.items():
        print("   · %-42s %3d 个：%s" % (sec[:42], len(vals), ", ".join(vals[:16]) + (" …" if len(vals) > 16 else "")))
    print("   ★ C 档合计 %d 个数值 token ⇒ ★ **出处必须由人显式登记，★ 本工具不推断** ★" % counts["C"])
    print()
    print("== ★ 配套告警：用「数值出现」推断出处的检查项 ★")
    print("   ★ 我方 `crosscheck_report.py` 48 项**全部**是这种 ⇒ ★ **它们不证明出处** ★")
    print("   ★ 其中 44 项是【弱检查】（★ 期望串在报告里出现 ≥2 次 ⇒ ★ 改一处仍命中 ★）★")
    print("   ★ ⇒ ★ 处置：★ 报告 §6.10.0c / §6.10.0d 已写明「全绿证明什么 / 没证明什么」★")
    print()
    if errs:
        print("✘ 审计失败 %d 项：" % len(errs))
        for e in errs:
            print("   - %s" % e)
    else:
        print("✔ 全部生成段与生成器片段逐字节一致（★ 人改产物也会被抓 ★）")
    if a.json_out:
        out = {"n_verified_values": len(covered), "counts": counts, "total": total,
               "coverage_upper_pct": 100.0 * (counts["A"] + counts["B"]) / max(total, 1),
               "gap_C": gap, "errors": errs,
               "caveat": "★ A/B 计数是上界（★ 同值 ≠ 同源 ★）★ 精确口径见 n_verified_values"}
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        print("✔ 落盘 %s" % a.json_out)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
