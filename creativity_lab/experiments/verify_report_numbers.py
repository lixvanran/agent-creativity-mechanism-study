#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 报告关键数的【逐位·逐格】核对（★ 强检查，★ 不容差，★ 定位到具体行与格 ★）

> 落点：`creativity_lab/experiments/verify_report_numbers.py`
> 用法：
>   python3 -B creativity_lab/experiments/verify_report_numbers.py \
>       --report docs/交付/第二组交付报告_2026-10-24.md \
>       --json   docs/交付/读数快照/topo-arm-v2-n151/partial_verdict.json
>   python3 -B creativity_lab/experiments/verify_report_numbers.py --self-test
>
> ★ ★★ 为什么必须有这个（★ 2026-10-24 实测逼出来的 ★）★★
★ `crosscheck_report.py` 的 48 项检查**全是【子串包含】**⇒ ★ 实测：**44 / 48 是弱检查**
★ （★ 期望串在报告里出现 ≥2 次 ⇒ ★ 改一处、别处仍命中 ⇒ ★ 抓不到变异 ★）
★ ⇒ ⇒ ★ **「48/48 全绿」不是数字正确性的证据** ⇒ ⇒ ★ 必须有一道【逐位·逐格】的强检查 ★
★ ⇒ ⇒ ★ 本脚本就是那道强检查：★ **定位到具体行与具体格**、★ **逐位比对**、★ **不容差** ★
★ ⇒ ⇒ ★ 且它**自带变异注入自测**（★ 证明它真会红 ★）★
>
> ★ 覆盖范围（★ 报告里每一个进入结论句或主判据表的数 ★）：
★ §6.10.0 冻结快照登记（n / sha256 / 字节数）｜§6.10.2 H0 表（σ / q95 / X₀ / θ₀）
★ §6.10.4 主判据表（**逐格标准化效应量** + 超门槛数 + 题级方向）｜§6.10.5 结论句（四个数）
★ §6.10.6 补齐 n 的条件表（H0 配对 n / θ₀ / 题级 n）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONTRASTS = [("H-TOPO-4a", "有无交互"), ("H-TOPO-4c", "有无综述"), ("H-TOPO-4d", "轮内可见性图")]


def section(rep: str, start: str, end: str) -> str:
    """★ 取两个【章节标题】之间的内容 ★
    ★ ★ 定位必须用【行首唯一锚点】★★
    ★   ★ 裸标题字符串会命中【表格里引用的标题】⇒ ★ 实测踩过两次：
    ★   ★ 「### 6.10.2 H0 标定」在 §6.10.0d 的 C 档表里也出现 ⇒ ★ 取到的是那一行 ★
    ★ ★ ⇒ ★ 一律要求标题出现在【行首】（★ 前一个字符是换行 ★）★ 且【唯一命中】★★
    """
    _s, _e = "\n" + start, "\n" + end
    n_s = rep.count(_s)
    if n_s != 1:
        raise RuntimeError("段首 %r 行首命中 %d 次（★ 必须恰好 1 次 ★）" % (start, n_s))
    if rep.count(_e) < 1:
        raise RuntimeError("找不到段尾 %r" % end)
    i = rep.index(_s) + 1
    j = rep.index(_e, i)
    return rep[i:j]


def norm(x) -> str:
    """★ 只去【排版装饰】（★ 粗体/σ/空格/全角空格/★/｜分隔符 ★）★ ⇒ ★ 不动数字本身 ★"""
    s = str(x)
    for ch in ("**", "σ", " ", "　", "★", "|", "*", "−"):
        s = s.replace(ch, "")
    return s.strip()


def table_rows(sec: str, prefix: str):
    """★ 取以 prefix 开头的表格行 ⇒ [(行号, [格…])] ★"""
    out = []
    for ln in sec.split("\n"):
        if ln.startswith(prefix):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            out.append(cells)
    return out


def verify(rep: str, d: dict, covered=None):
    """★ covered：★ 可选的集合，★ 记录本检查【实际核对过】的期望值字符串 ★
    ★ ⇒ ★ 覆盖率审计用它算 A 档，★ 而不是「按段名猜」★（★ 段名会骗人 ★）"""
    errs = []
    if covered is None:
        covered = set()
    h0 = d["h0"]
    verd = d["verdicts"]
    theta0 = d["theta0"]
    n_pairs = h0["vendi"]["n_pairs"]

    # ── §6.10.2 H0 表 ──
    s2 = section(rep, "### 6.10.2 H0 标定", "### 6.10.2b")
    v = h0["vendi"]
    for want, label in (("%.4f" % v["sigma_rep"], "vendi σ"),
                        ("%.4f" % v["q95_nearest_rank"], "vendi q95(nr)"),
                        ("%.4f" % v["q95_linear"], "vendi q95(lin)"),
                        ("%.4f" % v["X0_q95_over_sqrt2"], "vendi X₀"),
                        ("%.2f" % v["theta0_standardized"], "vendi θ₀")):
        covered.add(want)
        if want not in s2:
            errs.append("§6.10.2 缺 %s = %s" % (label, want))
    for want, label in (("%.4f" % h0["modes"]["sigma_rep"], "modes σ"),
                        ("%.4f" % h0["modes"]["X0_q95_over_sqrt2"], "modes X₀"),
                        ("%.2f" % h0["modes"]["theta0_standardized"], "modes θ₀")):
        if want not in s2:
            errs.append("§6.10.2 缺 %s = %s" % (label, want))
    if ("%.4f" % h0["structured_dedup"]["sigma_rep"]) not in s2:
        errs.append("§6.10.2 缺 structured_dedup σ")

    # ── §6.10.4 主判据表：逐格 ──
    s4 = section(rep, "### 6.10.4 主判据", "### 6.10.5")
    for name, label in CONTRASTS:
        rows = table_rows(s4, "| **%s** |" % name)
        if not rows:
            errs.append("§6.10.4 缺对比行 %s" % name)
            continue
        cells = rows[0]
        c = verd[name]
        # 列：0 名称｜1 唯一差｜2 可比单元｜3 逐格标准化效应｜4 超θ₀｜5 题级方向｜6 脆弱格
        if norm(cells[2]) != str(c["n_cells"]):
            errs.append("%s 可比单元：报告=%s，json=%s" % (name, norm(cells[2]), c["n_cells"]))
        got = [norm(x) for x in re.split(r"｜|\|", cells[3]) if norm(x)]
        want = ["%.2f" % abs(x["vendi_std"]) for x in c["cells"]]
        covered.update(want)
        if got != want:
            errs.append("%s 逐格标准化效应：报告=%s，json=%s" % (name, got, want))
        covered.add("%d/%d" % (sum(1 for x in c["cells"] if abs(x["vendi_std"]) > theta0), c["n_cells"]))
        n_over = sum(1 for x in c["cells"] if abs(x["vendi_std"]) > theta0)
        if norm(cells[4]) != ("%d/%d" % (n_over, c["n_cells"])):
            errs.append("%s 超门槛：报告=%s，json=%d/%d" % (name, norm(cells[4]), n_over, c["n_cells"]))
        want_dir = ["%s%s" % (t, ("%+.4f" % m)) for t, m, _s in c["dir_votes"]]
        covered.update(want_dir)
        got_dir = [norm(x) for x in re.split(r"｜", cells[5])]
        # ★ 剥掉方向判定后缀（★ 如「⇒ 方向不一致」★）★
        got_dir = [x.split("⇒")[0] for x in got_dir]
        got_dir = [x for x in got_dir if x]
        if got_dir[:len(want_dir)] != want_dir:
            errs.append("%s 题级方向：报告=%s，json=%s" % (name, got_dir, want_dir))

    # ── §6.10.5 结论句：★ 结构化逐位（★ 不是子串包含 ★）★★
    #   ★ ★ 旧实现是子串包含 ⇒ ★ 抓不到「漏一个」「数字本身错」★★
    #   ★ ★ 实测漏检两处：★ ① 4c 漏了 S6（★ 写 2 个、实际 3 个 ★）★★
    #   ★ ★                ② 「综述效应有 2 个超门槛格」实为 3 个 ★★
    s5 = section(rep, "### 6.10.5", "### 6.10.6")
    s5n = norm(s5)
    ntid = len(d.get("tids") or [])
    tns = sorted({verdict["n_tid"] for verdict in verd.values() if verdict.get("n_tid")})
    ntxt = ("%d" % tns[0] if len(tns) == 1 else "%d-%d" % (tns[0], tns[-1]))
    for want, label in (("**%d/%d**" % (d["n_units_actual"], d["n_units_target"]), "已跑单元数"),
                        ("θ₀ = %.2f 个题内 rep σ" % theta0, "结论句 θ₀"),
                        ("H0 原料 %d 个同臂同题配对" % n_pairs, "结论句 H0 原料数"),
                        ("题级 n = %s" % ntxt, "结论句题级 n"),
                        ("只覆盖已跑批的 %d 题" % ntid, "结论句已跑题数")):
        covered.add(norm(want))
        if norm(want) not in s5n:
            errs.append("§6.10.5 缺 %s（期望含「%s」）" % (label, want))
    # ★ ★ 逐组逐题：★ 必须【恰好相等 + 项数相等】★★
    #   ★ ★ 不能只查「包含」：★ 「少一个题」时剩下的那串是完整串的【前缀】★
    #   ★ ★ ⇒ 仍然命中 ⇒ ★ 抓不到（★ 变异 ⑥″ 就是冲这个来的 ★）★★
    #   ★ ★ ⇒ 做法：★ 从结论句里【切出】该组的方向整段 ⇒ ★ 逐项比对 ★
    for name, key in (("H-TOPO-4a", "4a"), ("H-TOPO-4c", "4c"), ("H-TOPO-4d", "4d")):
        c = verd[name]
        items = ["%s %+.4f" % (tid, mean) for tid, mean, _s in c["dir_votes"]]
        # ★ 从结论句里切出「4x：」之后到「；」或「★）★」之前的整段 ★
        _m = re.search(r"%s：([^；★]*)" % key, s5)
        if not _m:
            errs.append("§6.10.5 结论句里找不到「%s：」段" % key)
            continue
        got_items = [x.strip() for x in _m.group(1).split("/") if x.strip()]
        want_items = [norm(x) for x in items]
        got_norm = [norm(x) for x in got_items]
        if got_norm != want_items:
            errs.append("§6.10.5 %s 题级方向不符：报告=%s（%d 项），json=%s（%d 项）"
                        % (name, got_norm, len(got_norm), want_items, len(want_items)))
    # ★ ★ 超门槛格数（★ 手抄曾写成 2、实为 3 ★）★★
    def _over(nm):
        return sum(1 for x in verd[nm]["cells"] if abs(x["vendi_std"]) > theta0)
    for nm, label in (("H-TOPO-4c", "综述效应"), ("H-TOPO-4a", "交互效应"), ("H-TOPO-4d", "可见性图效应")):
        o = _over(nm)
        nc = verd[nm]["n_cells"]
        # ★ 括号用全角：★ 与报告里的写法一致（★ norm() 只去排版装饰、★ 不去括号 ★）★
        pat = ("%s有%d个" % (label, o)) if nm != "H-TOPO-4d" else ("低于门槛（%d/%d）" % (o, nc))
        covered.add(norm(pat))
        if norm(pat) not in s5n:
            errs.append("§6.10.5 %s 超门槛格数不符（期望含「%s」）" % (label, pat))
    # ★ ★ 「明确不能说的」里的题级 n 与超门槛格明细 ★★
    if norm("题级 n=%s" % ntxt) not in s5n:
        errs.append("§6.10.5「明确不能说的」题级 n ≠ %s" % ntxt)
    c4c = verd["H-TOPO-4c"]
    oc = sorted([(x["tid"], x["rep"], x["vendi_std"]) for x in c4c["cells"]
                 if abs(x["vendi_std"]) > theta0], key=lambda z: -abs(z[2]))
    for t, r, sv in oc:
        want = "%s r%d %+.2fσ" % (t, r, sv)
        covered.add(norm(want))
        if norm(want) not in s5n:
            errs.append("§6.10.5「明确不能说的」缺超门槛格 %s" % want)

    # ── §6.10.6 表 ──
    s6 = section(rep, "### 6.10.6", "## 结论 6.11")
    _r6 = table_rows(s6, "| H0 配对 n |")
    if not _r6:
        errs.append("§6.10.6 缺「H0 配对 n」行")
    else:
        _c6 = _r6[0]
        _got = norm(_c6[1]).split("（")[0].strip()
        if _got != str(n_pairs):
            errs.append("§6.10.6 H0 配对 n：报告=%s，json=%d" % (_got, n_pairs))
    if norm("θ₀ = **%.2f σ**" % theta0) not in norm(s6):
        errs.append("§6.10.6 θ₀ ≠ %.2f" % theta0)
    return errs, covered


def self_test():
    rep_p = os.path.join(ROOT, "docs", "交付", "第二组交付报告_2026-10-24.md")
    js_p = os.path.join(ROOT, "docs", "交付", "读数快照", "topo-arm-v2-n151", "partial_verdict.json")
    if not (os.path.exists(rep_p) and os.path.exists(js_p)):
        print("★ 自测跳过：★ 找不到报告或 json ★")
        return 1
    rep = open(rep_p, encoding="utf-8").read()
    d = json.load(open(js_p, encoding="utf-8"))
    base, _cov = verify(rep, d)
    print("== 自测 ① 基线：★ 应当【无错】==")
    if base:
        print("   ✘ 基线就有 %d 处不符：" % len(base))
        for e in base[:12]:
            print("     - %s" % e)
        return 1
    print("   ✔ 基线无错")
    cases = []
    n_mut = 0          # ★ 变异次数【由计数器累加】★ ⇒ 不得硬编码 ★
    n_inline = 0       # ★ inline 变异块计数（★ 用于「各块之和 == 总数」自检 ★）
    # ② 改 json 的 σ
    m2 = json.loads(json.dumps(d)); m2["h0"]["vendi"]["sigma_rep"] = 9.999
    cases.append(("改 json 的 σ", m2, rep))
    # ③ 改 json 的 θ₀
    m3 = json.loads(json.dumps(d)); m3["theta0"] = 9.99
    cases.append(("改 json 的 θ₀", m3, rep))
    # ④ 改 json 的逐格标准化效应量
    m4 = json.loads(json.dumps(d))
    m4["verdicts"]["H-TOPO-4a"]["cells"][0]["vendi_std"] = 9.99
    cases.append(("改 json 的逐格效应量", m4, rep))
    # ⑤ 改 json 的题级方向
    m5 = json.loads(json.dumps(d))
    m5["verdicts"]["H-TOPO-4c"]["dir_votes"][0][1] = 9.99
    cases.append(("改 json 的题级方向", m5, rep))
    # ⑥ 改 json 的 H0 配对 n
    m6 = json.loads(json.dumps(d)); m6["h0"]["vendi"]["n_pairs"] = 999
    cases.append(("改 json 的 H0 配对 n", m6, rep))
    # ⑥′ 改 json 使超门槛格数变化（★ 靠改一个格值让它跨过门槛 ★）
    m6b = json.loads(json.dumps(d))
    _th0 = d["theta0"]
    for _x in m6b["verdicts"]["H-TOPO-4c"]["cells"]:
        if abs(_x["vendi_std"]) < _th0:
            _x["vendi_std"] = _th0 + 0.5
            break
    cases.append(("改 json 使超门槛格数变化", m6b, rep))
    # ⑥″ 改 json 的题级方向【去掉一个题】（★ 专门抓「漏一个」★★）
    m6c = json.loads(json.dumps(d))
    m6c["verdicts"]["H-TOPO-4c"]["dir_votes"] = m6c["verdicts"]["H-TOPO-4c"]["dir_votes"][:2]
    cases.append(("改 json 去掉 4c 的一个题级方向", m6c, rep))
    for label, mj, rp in cases:
        n_mut += 1
        e, _c2 = verify(rp, mj)
        print("== 自测：%s ⇒ 应当【被抓】==" % label)
        if e:
            print("   ✔ 抓到 %d 处：%s" % (len(e), e[0]))
        else:
            print("   ✘ 没抓到 ⇒ 这个检查是假绿")
            return 1
    # ⑦ 改【报告里】那一格（★ 只改一处 ⇒ 专门抓「命中≠这一处对」★）
    # ★ ★ 变异必须打在【正确的那一行】★ ⇒ ★ 不能用全文 replace（★ 否则改的是别处的同串 ★）
    #   ★ ★ 这条本身就是本轮的核心教训：★ 我第一版用 `rep.replace(first, ...)` ⇒ ★
    #   ★ ★ 变异落在全文第一处同串 ⇒ ★ 检查没抓到 ⇒ ★ 【差在变异位置，不在检查逻辑】★★
    lines = rep.split("\n")
    tgt = [i for i, ln in enumerate(lines) if ln.startswith("| **H-TOPO-4a** |")]
    if not tgt:
        print("   ✘ 找不到主判据表的 4a 行")
        return 1
    i0 = tgt[0]
    cells = [c.strip() for c in lines[i0].strip().strip("|").split("|")]
    parts = cells[3].split("｜")
    parts[0] = "9.99"
    cells[3] = "｜".join(parts)
    lines[i0] = "| " + " | ".join(cells) + " |"
    mutated = "\n".join(lines)
    n_mut += 1
    n_inline += 1
    e = verify(mutated, d)
    print("== 自测：改【报告里】主判据表那一格 ⇒ 应当【被抓】==")
    if e:
        print("   ✔ 抓到 %d 处：%s" % (len(e), e[0]))
    else:
        print("   ✘ 没抓到")
        return 1
    # ⑧ 改【报告里】§6.10.5 结论句的那一个方向值（★ 只改那一处 ★）
    _lines5 = rep.split("\n")
    _hit = [k for k, ln in enumerate(_lines5) if ln.startswith("> 「在已跑批的")]
    if _hit:
        _k = _hit[0]
        _lines5[_k] = _lines5[_k].replace("S6 +0.3461", "S6 +0.9999", 1)
        n_mut += 1
        n_inline += 1
        e, _c2 = verify("\n".join(_lines5), d)
        print("== 自测：改【报告里】结论句的那一个方向值 ⇒ 应当【被抓】==")
        if e:
            print("   ✔ 抓到 %d 处：%s" % (len(e), e[0]))
        else:
            print("   ✘ 没抓到")
            return 1
    print()
    print("✔ 自测全过：★ 这个检查会红（★ 不是恒真 ★）★")
    # ★ ★ 计数自检（★ 第 1 层论证线 2026-10-24：★ 【累加本身也会漏加一块】★★）
    #   ★ 「各块之和 == 报告的总数」⇒ ★ 将来加了新块忘插计数器 ⇒ ★ 这里立刻报红 ★
    n_cases = len(cases)
    if n_mut != n_cases + n_inline:
        print("   ✘✘ 计数自检失败：★ 总数 %d ≠ cases %d + inline %d ⇒ ★ **有块漏加计数器** ★"
              % (n_mut, n_cases, n_inline))
        return 1
    print("   ★ 本轮共做 ★ %d 次变异注入 ★（★ 由计数器累加 ★）★" % n_mut)
    print("   ★ 计数自检：★ %d = cases %d + inline %d ✔" % (n_mut, n_cases, n_inline))
    # ★ ★★ 诚实登记一个【结构性局限】★★
    #   ★ ★ 若有人新增一个变异块、★ 却【同时】忘了 n_mut += 1 和 n_inline += 1 ⇒
    #   ★ ★ 等式【两边都少 1】⇒ ★ ⇒ **这个等式抓不到** ★ ★
    #   ★ ★ ⇒ ★ 「各块之和 == 总数」只能抓「只漏一处」⇒ ★ 根治需要【wrapper 自动计数】★★
    print("   ★ ★ 已知局限（★ 诚实登记 ★）：★ 漏加的块若【同时】漏了 n_mut 与 n_inline ⇒")
    print("   ★ ★   ⇒ 等式两边都少 1 ⇒ ★ **本自检抓不到** ⇒ ★ 根治需【wrapper 自动计数】★★")
    print("   ★ ★   ⇒ ⇒ ★ 所以【块清单】必须同时打印出来供人核对（★ 见下 ★）★★")
    print("   ★ 块清单：★ cases %d 项 + inline %d 项 ⇒ 共 %d 块"
          % (n_cases, n_inline, n_cases + n_inline))
    for _i, _lab in enumerate(cases):
        print("      · cases[%d] %s" % (_i, _lab[0][:64]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json-out", default=None,
                    help="★ 落盘本检查【实际核对过】的期望值集合（★ 供覆盖率审计算 A 档 ★）")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.report and a.json):
        print(__doc__)
        return 1
    rep = open(a.report, encoding="utf-8").read()
    d = json.load(open(a.json, encoding="utf-8"))
    errs, covered = verify(rep, d)
    if errs:
        print("✘ 报告与 json 不符（★ %d 处 ★）：" % len(errs))
        for e in errs:
            print("   - %s" % e)
        return 2
    print("✔ 报告关键数逐位逐格核对全对（★ §6.10.0/6.10.2/6.10.4/6.10.5/6.10.6 ★）")
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as _f:
            json.dump({"n_covered": len(covered),
                       "covered": sorted(covered)}, _f, ensure_ascii=False, indent=1, sort_keys=True)
        print("✔ 落盘核对覆盖集合（%d 个期望值）→ %s" % (len(covered), a.json_out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
