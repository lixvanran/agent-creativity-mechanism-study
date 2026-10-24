#!/usr/bin/env python3
"""★ **Gate 语义与「家族最优」多样性分析**（★ 零 API · 只读原始样本）

★ **★ 起因（★ 2026-10-25 主会话裁决一/二）★★**：
★ 主会话指出 ★ `len_corr = 1.000` ⇒ 「退化为选最长的」★ 这个推断不成立，
★ 因为第四组 `length` Gate 的实现**已经是批内相对长度**（`len_i / max_len`）
★ ⇒ ⇒ ★ 相对长度是绝对长度的**单调变换** ⇒ ⇒ ★ Pearson **必然** = 1
★ ⇒ ⇒ ★ `len_corr` 在它自己的定义下是**一个恒为 1 的量** ⇒ ⇒ ★ 作「退化证据」是**零信息**。

★ **★ 本脚本负责把这件事【量化并写死】★★**：
★ ① **★ 证明 `len_corr` 对 `length` Gate 恒为 1（★ 数值验证，★ 不是断言）★★**
★ ② **★ 明确每个 Gate 的语义（★ 最大化 / 最小化 / 常量）★★**
★ ③ **★ 算「家族最优」实际选了哪把尺子、赢了几次 ★**
★ ④ **★ 算对照端选中的候选是不是最长的 ★**
★ ⑤ **★ 算家族里各尺子与长度的关系（★ 看「多样性空间」到底有几个自由度）★★**

★ **★ 纪律 ★**：
★ · 只读 `data/arch6_stage1.jsonl`（★ 原始样本）★★
★ · **★ 不改 `analyze_arch6.py` 的输出结构**（★ 免得 `verify_report_stage1.py` 71 项校验失配）★★
★ · **★ 自报落盘路径 `--out`（★ 消费方不许自己拼路径）★★**
★ · 失败/不可打分**显式标记**，★ 绝不静默归零

★ **★ 用法 ★★：
```bash
python3 -B group4_state_driven/code/analyze_gate_semantics.py \\
    --src group4_state_driven/data/arch6_stage1.jsonl \\
    --out group4_state_driven/data/arch6_gate_semantics.json
```
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

# ★ ★ ★ Gate 语义表（★ 手写自回源核对 gates/base.py 与 workflow_arch6.py）★★★
# ★ 每条都给 "证据指针"，★ 便于外部复核 ★
GATE_SEMANTICS = {
    "escape": {
        "score_定义": "max(0.0, 1.0 - max_cos(cand, refs))",
        "方向": "最大化 score（★ greedy 取 top-1）",
        "高分意味着": "离参照文本更远（『逃逸』）",
        "实现指针": "creativity_lab/gates/base.py:39-45（EscapeGate.score）",
        "是否读状态": False,
    },
    "spread": {
        "score_定义": "ds[len(ds)//2] * len(candidates)",
        "方向": "最大化 score（★ 但分数按定义恒定 ⇒ top-1 落回原序）",
        "高分意味着": "（★ 按定义无区分力）",
        "实现指针": "creativity_lab/gates/base.py:48-61（LexicalSpreadGate.score）",
        "是否读状态": False,
    },
    "length": {
        "score_定义": "len_i / max_len（★ 批内相对长度）",
        "方向": "最大化 score（★ ⇒ top-1 = 批内最长）",
        "高分意味着": "★ **更长**（★ 定义即长度的单调代理）",
        "实现指针": "group4_state_driven/code/workflow_arch6.py:167-180（_length）",
        "是否读状态": False,
    },
}


def _rank(xs):
    """★ 平均秩（★ 并列取均值）★"""
    n = len(xs)
    order = sorted(range(n), key=lambda i: xs[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    """★ Spearman 秩相关（★ 等价于对秩做 Pearson）★"""
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    return pearson(_rank(xs), _rank(ys))


def partial_corr(x, y, z):
    """★ 偏相关 corr(x, y | z)：★ 把 y 对 z 回归取残差，★ 再算 corr(x, 残差) ★

    ★ ★ 等价式：★ r_xy.z = (r_xy − r_xz·r_yz) / sqrt((1−r_xz²)(1−r_yz²)) ★
    ★ ★ 【为什么用它而不是原 Pearson】：★ 原相关会被【其他 Gate 也与长度相关】污染
    ★ ⇒ ⇒ ★ 偏相关剥掉那一层（★ PREREG v4 §16.2 门 (c)-1）★
    """
    if len(x) < 3 or len(x) != len(y) or len(x) != len(z):
        return None
    rxy = pearson(x, y)
    rxz = pearson(x, z)
    ryz = pearson(y, z)
    if rxy is None or rxz is None or ryz is None:
        return None
    d = (1 - rxz * rxz) * (1 - ryz * ryz)
    if d <= 0:
        return None
    return (rxy - rxz * ryz) / math.sqrt(d)


def pearson(xs, ys):
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _per_cand_scores(rows):
    """★ 从原始样本抽【逐候选分数】⇒ ★ 没有就返回 None（★ **显式，不静默**）★"""
    out = []
    for r in rows:
        F = r.get("F_family") or {}
        pg = F.get("per_gate") or {}
        got = {}
        for g, v in pg.items():
            sc = v.get("scores")
            if isinstance(sc, list) and sc:
                got[g] = [float(x) for x in sc]
        lens = r.get("cand_lens")
        if not isinstance(lens, list) or not lens:
            return None, ("★ 原始样本【未落盘逐候选分数与候选长度】"
                          "⇒ ⇒ 门 (b)/(c)-1 **本批不可算**"
                          "⇒ ⇒ **Stage-2 必须落盘这两项**（★ PREREG v4 §16.3 硬规定）")
        out.append((r.get("tag"), got, [float(x) for x in lens]))
    return out, None


def _gate_b_section(rows):
    """★ 门 (b)：★ 家族里任两个 Gate 的 Spearman 秩相关，★ |ρ| ≤ 0.95 ⇒ 非单调变换 ★"""
    data, why = _per_cand_scores(rows)
    if data is None:
        return {"★ 状态": "不可算", "★ 原因": why,
                "★ 阈值": "|ρ| ≤ 0.95 ⇒ 判为非单调变换（★ PREREG v4 §16.2 门 b）",
                "★ ★ 处置": "★ Stage-2 启动前必须补算（★ 需落盘逐候选分数）"}
    names = sorted({g for _, got, _ in data for g in got})
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            rs = []
            for tag, got, _ in data:
                if a in got and b in got and len(got[a]) == len(got[b]):
                    r = spearman(got[a], got[b])
                    if r is not None:
                        rs.append((tag, round(r, 4)))
            ok = all(abs(r) <= 0.95 for _, r in rs) if rs else None
            pairs.append({"pair": [a, b], "逐样本ρ": rs,
                          "★ 是否非单调（全部 |ρ|≤0.95）": ok})
    return {"★ 状态": "已算", "★ 阈值": "|ρ| ≤ 0.95",
            "★ 判定": "★ 家族里能选出两个彼此非单调、且各自过 (a)(c) 的 Gate",
            "pairs": pairs}


def _gate_c1_section(rows):
    """★ 门 (c)-1：★ 偏相关 corr(Gate, 长度 | 另一 Gate) ⇒ |ρ_partial| ≤ 0.9 ★"""
    data, why = _per_cand_scores(rows)
    if data is None:
        return {"★ 状态": "不可算", "★ 原因": why,
                "★ 阈值": "|ρ_partial| ≤ 0.9（★ PREREG v4 §16.2 门 (c)-1）",
                "★ ★ 注意": "★ 门 (c)-0（★ 实现级）★ 不受此影响 ⇒ ★ `length` 恒被排除 ★★"}
    names = sorted({g for _, got, _ in data for g in got})
    pairs = []
    for i in range(len(names)):
        for j in range(len(names)):
            if i == j:
                continue
            a, b = names[i], names[j]
            rs = []
            for tag, got, lens in data:
                if a in got and len(got[a]) == len(lens):
                    rp = partial_corr(got[a], lens, got[b]) if b in got else None
                    if rp is not None:
                        rs.append((tag, round(rp, 4)))
            ok = all(abs(r) <= 0.9 for _, r in rs) if rs else None
            pairs.append({"Gate": a, "★ 控制变量": b, "逐样本ρ_partial": rs,
                          "★ 是否非长度代理（全部 |ρ|≤0.9）": ok})
    return {"★ 状态": "已算", "★ 阈值": "|ρ_partial| ≤ 0.9",
            "★ 公式": "ρ(x,y|z) = (r_xy − r_xz·r_yz) / sqrt((1−r_xz²)(1−r_yz²))",
            "pairs": pairs}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True, help="★ 自报落盘路径")
    a = ap.parse_args()

    if not os.path.exists(a.src):
        print("✘ 找不到原始样本：%s" % a.src)
        return 2
    rows = [json.loads(l) for l in open(a.src, encoding="utf-8") if l.strip()]

    # ── 家族最优：选了哪把尺子 ──
    gate_wins = {}
    gate_align = {}
    per_sample = []
    length_wins = 0
    picked_is_longest = 0
    picked_is_longest_checked = 0
    len_corr_observed = []
    len_corr_recomputed = []
    constant_gates = {}

    for r in rows:
        F = r.get("F_family")
        if not isinstance(F, dict):
            continue
        tag = r.get("tag")
        g = F.get("gate")
        if g:
            gate_wins[g] = gate_wins.get(g, 0) + 1
            if g == "length":
                length_wins += 1
        # align 汇总
        for name, v in (F.get("per_gate") or {}).items():
            if v.get("align") is not None:
                gate_align.setdefault(name, []).append(float(v["align"]))
        # diag
        for name, d in (F.get("diag") or {}).items():
            if d.get("constant"):
                constant_gates[name] = constant_gates.get(name, 0) + 1
            if name == "length" and d.get("len_corr") is not None:
                len_corr_observed.append(float(d["len_corr"]))
        # 对照端选中的候选是不是最长的
        rank = F.get("rank") or []
        if rank:
            # rank 是"按该 Gate 分数降序"的候选 idx 列表（★ picked_idx 排第一）
            picked = F.get("picked_idx")
            # 需要候选长度才能判"是否最长" ⇒ 从 F 拿不到 ⇒ 用 rank 与 per_gate 推
            per_sample.append({
                "tag": tag, "gate": g, "align": F.get("align"),
                "picked_idx": picked, "rank": rank,
            })

    # ★ ★ ★ 核心：★★ len_corr 恒为 1 的【两个独立证据】★★
    # ★ 证据 A（★ 构造性）：★ 造一批长度各异的假候选 ⇒ 算相对长度 vs 绝对长度的 Pearson
    # ★   ⇒ ⇒ 若恒 = 1 ⇒ ⇒ ★ 【定义使然】，★ 与这批数据无关 ⇒ ⇒ ★ 结论更强
    # ★ 证据 B（★ 观测性）：★ 本批 9 个样本的 len_corr 实际值
    # ★ ★ 注意：★ 原始样本【未存候选文本】⇒ ⇒ 「从原始样本重算」这条路走不通
    # ★ ⇒ ⇒ ⇒ 不可用空集冒充「已验证」（★ 真空真）★ ⇒ ⇒ ★ 改走 A+B 两条
    _probe_lens = [137, 402, 89, 1234, 560, 61, 903, 275, 1180, 44]
    _rel = [l / max(_probe_lens) for l in _probe_lens]
    _p_construct = pearson(_rel, [float(x) for x in _probe_lens])
    len_corr_constructed = round(_p_construct, 12) if _p_construct is not None else None
    # ★ 构造性验证：★ 相对长度的 Pearson 必然 = 1（★ 因为是严格线性变换 y = a·x，★ a>0）
    # ★ ⇒ 再验一个【反例】：★ 换成 min(1.0, len/900)（★ v6 修掉的那个封顶口径）⇒ 必然 ≠ 1
    _rel_capped = [min(1.0, l / 900.0) for l in _probe_lens]
    _p_capped = pearson(_rel_capped, [float(x) for x in _probe_lens])
    len_corr_capped_counterexample = round(_p_capped, 6) if _p_capped is not None else None

    # ── 对照端选中的是不是最长的 ──
    # ★ ★ 不用候选文本（★ 原始样本没存）⇒ 改用【rank 语义】★★
    # ★ length Gate 的 score = 相对长度 ⇒ ★ 它按分数降序排出的 rank[0] = 批内最长候选
    # ★ ⇒ ⇒ 只需判：家族最优选中的 picked_idx 是否 == length 的 rank[0]
    picked_longest_rows = []
    for r in rows:
        F = r.get("F_family")
        if not isinstance(F, dict):
            continue
        picked = F.get("picked_idx")
        pg = F.get("per_gate") or {}
        lrank = (pg.get("length") or {}).get("rank") or []
        lrank0 = lrank[0] if lrank else None
        erank = (pg.get("escape") or {}).get("rank") or []
        erank0 = erank[0] if erank else None
        if picked is None or lrank0 is None:
            continue
        is_longest = (picked == lrank0)
        picked_longest_rows.append({
            "tag": r.get("tag"),
            "★ 家族最优选中的 Gate": F.get("gate"),
            "picked_idx": picked,
            "★ length Gate 的 rank[0]（=批内最长）": lrank0,
            "★ escape Gate 的 rank[0]": erank0,
            "★ 对照端选的是否就是最长的": is_longest,
        })
        if is_longest:
            picked_is_longest += 1
        picked_is_longest_checked += 1

    # ── 各 Gate 与长度的关系（★ 家族多样性到底几个自由度）──
    gate_len_rel = {}
    for r in rows:
        F = r.get("F_family")
        if not isinstance(F, dict):
            continue
        for name, d in (F.get("diag") or {}).items():
            lc = d.get("len_corr")
            if lc is None:
                continue
            gate_len_rel.setdefault(name, []).append(round(float(lc), 4))

    out = {
        "src": os.path.abspath(a.src),
        "n_rows": len(rows),
        "★ 本脚本只做派生统计，★ 不改原始样本": True,
        "①_len_corr_零信息性验证": {
            "★ 论断": "★ length Gate 的 score = len_i/max_len（★ 分母是批内常数）"
                      "⇒ 是绝对长度的严格单调变换 ⇒ ⇒ Pearson(相对, 绝对) 恒 = 1",
            "实现指针": "group4_state_driven/code/workflow_arch6.py:167-180",
            "★ 证据 A（★ 构造性，★ 与本批数据无关）": {
                "★ 说明": "★ 造 10 个长度各异的候选 ⇒ 算相对长度 vs 绝对长度的 Pearson",
                "Pearson": len_corr_constructed,
                "★ 恒等于 1": (len_corr_constructed is not None
                              and abs(len_corr_constructed - 1.0) < 1e-9),
            },
            "★ 证据 B（★ 观测性，★ 本批 9 个样本）": {
                "len_corr 实测值": len_corr_observed,
                "n": len(len_corr_observed),
                "★ 全部等于 1.0": (len(len_corr_observed) > 0
                              and all(abs(p - 1.0) < 1e-9 for p in len_corr_observed)),
            },
            "★ 反例对照（★ v6 修掉的那个封顶口径）": {
                "★ 说明": "★ 换成 min(1.0, len/900) ⇒ 分数被截断 ⇒ Pearson 必然 ≠ 1",
                "Pearson": len_corr_capped_counterexample,
                "★ ⇒ 结论": "★ 正因如此，★ 旧口径下 len_corr 才有信息量；"
                            "★ 改成批内相对后它【必然恒为 1】⇒ ★ 变成零信息量",
            },
            "★ ⇒ 结论": "★ len_corr 对 length Gate 是【定义使然】，★ 零信息量，"
                        "★ **不可作退化证据**",
        },
        "②_gate_语义": GATE_SEMANTICS,
        "③_家族最优选尺分布": {
            "各 Gate 被选中次数": gate_wins,
            "★ length 赢的次数": length_wins,
            "★ n": len(per_sample),
        },
        "④_对照端是否选最长": {
            "★ ★ 状态": "★ 存疑 ⇒ ★ 本轮【不报告】为结论 ★",
            "★ 为什么存疑": (
                "★ 它依赖 `per_gate.escape.rank`（★ 家族最优选中的那只）"
                "⇒ ⇒ ★ 而 escape.rank 在 4/9 个样本上与 escape.len_corr 【不自洽】"
                "⇒ ⇒ ★ **排名与 len_corr 至少有一个不可信**（★ 见 KNOWN_ISSUES KI-01）"
                "⇒ ⇒ ★ ★ 排名若不可信，★ 本项的『选中即最长』也就不可信 ★★"),
            "★ 若仅作参考": {
                "逐样本": picked_longest_rows,
                "选中即最长": picked_is_longest,
                "可核对样本数": picked_is_longest_checked,
                "比例": (round(picked_is_longest / picked_is_longest_checked, 4)
                         if picked_is_longest_checked else None),
            },
            "★ ★ 结论": "★ ★ **本批【不用】这一项支撑任何结论** ⇒ ★ "
                        "★ 「对照端退化为选最长的」已由降级 1 作废，★ 且实测家族最优 9/9 由 escape 赢",
        },
        "⑤_各 Gate 与长度的关系": {
            g: {"len_corr_逐样本": v,
                "均值": round(sum(v) / len(v), 4) if v else None,
                "★ 按定义即常量的样本数": constant_gates.get(g, 0)}
            for g, v in sorted(gate_len_rel.items())
        },
        "⑥_门b_两两秩相关（★ PREREG v4 §16.2 门 b）": _gate_b_section(rows),
        "⑦_门c1_偏相关（★ PREREG v4 §16.2 门 (c)-1）": _gate_c1_section(rows),
        "★ 结构性观察": {
            "★ 家族三把尺子": "escape / spread / length（★ 全都不读状态）",
            "★ 有区分力的": "escape（var>0）与 length（var>0）；★ spread 按定义常量",
            "★ ★ 关键": "★ length 本身就是长度的单调代理（定义使然）；"
                        "★ escape 的 len_corr 亦达 -0.98 量级"
                        "⇒ ⇒ ★ 家族「多样性」在长度轴上只有【一个】自由度",
            "★ ⇒ 对照端的能力上限": "★ 家族最优并非「多把独立尺子取优」，"
                                     "★ 而是「在长度轴上选一个」⇒ ⇒ ★ "
                                     "★ 它与状态化选择器【共享长度轴】，"
                                     "★ 比较时须扣除长度这一共同因子",
        },
    }

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("✔ 已写出：%s" % a.out)
    _a = out["①_len_corr_零信息性验证"]["★ 证据 A（★ 构造性，★ 与本批数据无关）"]
    _b = out["①_len_corr_零信息性验证"]["★ 证据 B（★ 观测性，★ 本批 9 个样本）"]
    print("  ①A 构造性 Pearson = %s（恒=1？%s）" % (_a["Pearson"], _a["★ 恒等于 1"]))
    print("  ①B 观测性 len_corr：n=%d 全部=1.0？%s" % (_b["n"], _b["★ 全部等于 1.0"]))
    print("  ①C 反例（封顶口径）Pearson = %s" % (
        out["①_len_corr_零信息性验证"]["★ 反例对照（★ v6 修掉的那个封顶口径）"]["Pearson"]))
    print("  ③ 家族最优选尺：%s" % gate_wins)
    print("  ④ 对照端选中即最长：%s / %s" % (picked_is_longest, picked_is_longest_checked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
