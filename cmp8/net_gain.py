#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""净维度增益（用户口径）—— 多档匹配器 + 双向自检（假阳性 + 召回）。

★ 上一版犯的错：自检只查"跨题误匹配率"，结果匹配器过严、什么都匹配不到，
  跨题误匹配也是 0 ⇒ **自检全绿而结论全是 0**。⇒ **自检必须同时查召回。**

召回校验：用判官判「支持」的 claim —— 既然判官说这条断言被依据包支持，
  那它所在的答案**必然命中 ≥1 条事实** ⇒ 用"支持 claim 所在答案的事实命中数"当召回下界。

四档匹配器：
  V1 全部硬指纹(数字/专名)命中 且 CJK 4-gram 覆盖 ≥0.45     （过严）
  V2 全部硬指纹命中 且 CJK 2-gram 覆盖 ≥0.35
  V3 每个数字都必须以「数字+紧邻实义字」的形式出现在答案里
  V4 任一「数字+紧邻实义字」锚点命中
选：跨题误匹配 ≈0 **且** 召回最高的那一档。
"""
import collections
import io
import json
import os
import re
import sys

REPO = "/workspace/lab/cmp8repo"
RUNS = os.path.join(REPO, "cmp8", "runs", "cmp8")
DATA = os.path.join(REPO, "cmp8", "creativity_lab", "data")
TIDS = ["A1", "A2", "A3", "A4"]
ARMS = ["A1", "A2", "A3", "A4", "A5a", "A5b", "A5c"]
NAME = {"A1": "① 直调(基线)", "A2": "② ADHD项目", "A3": "③ 融合门", "A4": "④ 去融合门",
        "A5a": "⑤a 无核验", "A5b": "⑤b 学到的策略", "A5c": "⑤c 初始w=0"}
STOP = set("的了是在和与及对为以也都就不有我你他她它们这那个些中上下前后将会能可要说到时候可能因为所以如果虽然但而且或者以及等等以及一二三四五每个各自之其中")


def facts_of(tid):
    d = json.load(open(os.path.join(DATA, "user4_q%d.json" % int(tid[1:])), encoding="utf-8"))
    return [p.strip() for p in re.split(r"[。；;\n]", d["evidence"]) if len(p.strip()) >= 8]


def hard(s):
    out = set()
    for m in re.finditer(r"\d+(?:\.\d+)?%?", s):
        out.add(m.group(0))
    for m in re.finditer(r"[《「【（(][^》」】）)]{2,}[》」】）)]", s):
        out.add(m.group(0))
    for m in re.finditer(r"[A-Za-z]{3,}", s):
        out.add(m.group(0))
    return out


def grams(s, n):
    g = set()
    for i in range(len(s) - n + 1):
        t = s[i:i + n]
        if not (set(t) & STOP):
            g.add(t)
    return g


def anchors(fact):
    """「数字+紧邻实义字」锚点：数字后 0-2 个汉字，或前 2 个汉字+数字。"""
    out = set()
    for m in re.finditer(r"\d+(?:\.\d+)?%?", fact):
        i, j = m.start(), m.end()
        num = m.group(0)
        after = fact[j:j + 2]
        before = fact[max(0, i - 2):i]
        if after:
            out.add(num + after)
        if before:
            out.add(before + num)
        out.add(num)
    return out


def prof(fact):
    return hard(fact), grams(fact, 4), grams(fact, 2), anchors(fact)


def match(fact, pr, ans, ap, ver):
    ah, a4, a2, aa = ap
    fh, f4, f2, fa = pr
    if ver == 1:
        if fh and not all(h in ah for h in fh):
            return False
        if not f4:
            return bool(fh)
        return len(f4 & a4) / len(f4) >= 0.45
    if ver == 2:
        if fh and not all(h in ah for h in fh):
            return False
        if not f2:
            return bool(fh)
        return len(f2 & a2) / len(f2) >= 0.35
    if ver == 3:
        if not fa:
            return bool(fh) and all(h in ah for h in fh)
        for a in fa:
            if len(a) > 2 and a in ans:      # 数字+邻字，必须带上下文
                return True
        return False
    if ver == 4:
        return any(a in ans for a in fa if len(a) > 2)
    return False


def answer_of(tid, rep, arm):
    syn = os.path.join(RUNS, "%s_r%d_%s_synth.md" % (tid, rep, arm))
    plain = os.path.join(RUNS, "%s_r%d_%s.md" % (tid, rep, arm))
    p = syn if (os.path.exists(syn) and os.path.getsize(syn) > 40) else plain
    return io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def aprof(text):
    return hard(text), grams(text, 4), grams(text, 2), anchors(text)


def main():
    facts = {t: facts_of(t) for t in TIDS}
    profs = {t: [(f, prof(f)) for f in facts[t]] for t in TIDS}
    ansp = {}
    for t in TIDS:
        for rep in (1, 2, 3):
            for a in ARMS:
                ansp[(t, rep, a)] = (answer_of(t, rep, a), aprof(answer_of(t, rep, a)))

    # 判官「支持」的 claim → 它的答案应当命中 ≥1 条事实 ⇒ 召回下界
    d = json.load(open(os.path.join(RUNS, "analysis.json"), encoding="utf-8"))
    sup_keys = []
    for r in d["rows"]:
        for c, v in (r.get("verd") or {}).items():
            if v == "支持":
                sup_keys.append((r["arm"], r["tid"], r["rep"]))
    print("判官判「支持」的断言：%d 条（分布在 %d 个臂-题-重复组合）" % (
        len(sup_keys), len(set(sup_keys))))

    print("\n=== 四档匹配器：跨题误匹配（要≈0） + 召回（要高）===")
    best = None
    for ver in (1, 2, 3, 4):
        fp = tot = 0
        for t1 in TIDS:
            for t2 in TIDS:
                if t1 == t2:
                    continue
                for rep in (1, 2, 3):
                    txt, ap = ansp[(t2, rep, "A1")]
                    if not txt:
                        continue
                    for f, pr in profs[t1]:
                        tot += 1
                        if match(f, pr, txt, ap, ver):
                            fp += 1
        # 召回：支持 claim 所在答案是否命中 ≥1 条事实
        hit = 0
        for arm, t, rep in sup_keys:
            txt, ap = ansp[(t, rep, arm)]
            if not txt:
                continue
            if any(match(f, pr, txt, ap, ver) for f, pr in profs[t]):
                hit += 1
        fpr = fp / max(tot, 1)
        rec = hit / max(len(sup_keys), 1)
        print("  V%d  跨题误匹配 %.4f%%   召回(支持claim所在答案命中事实) %.1f%%" % (
            ver, 100 * fpr, 100 * rec))
        if fpr < 0.02 and (best is None or rec > best[1]):
            best = (ver, rec, fpr)
    if not best:
        print("  ⚠️ 没有一档同时满足「误匹配≈0」和「有召回」")
        return 1
    ver, rec, fpr = best
    print("\n  ★ 选定 V%d（误匹配 %.4f%%，召回 %.1f%%）" % (ver, 100 * fpr, 100 * rec))

    print("\n=== 净维度增益（基线 = 同题同重复的 A1 直调）===")
    print("  臂                  题       命中/16  新增   丢失    净")
    agg = collections.defaultdict(lambda: dict(add=0, lose=0, hit=0, n=0))
    for arm in ARMS:
        for t in TIDS:
            add = lose = hit = 0
            n = 0
            for rep in (1, 2, 3):
                btxt, bap = ansp[(t, rep, "A1")]
                ctxt, cap = ansp[(t, rep, arm)]
                if not ctxt:
                    continue
                n += 1
                B = {f for f, pr in profs[t] if match(f, pr, btxt, bap, ver)}
                W = {f for f, pr in profs[t] if match(f, pr, ctxt, cap, ver)}
                hit += len(W)
                if arm != "A1":
                    add += len(W - B); lose += len(B - W)
            if not n:
                continue
            agg[arm]["n"] += n; agg[arm]["add"] += add
            agg[arm]["lose"] += lose; agg[arm]["hit"] += hit
            if arm == "A1":
                print("  %-18s %-4s %8.2f %6s %6s %6s" % (NAME[arm], t, hit / n, "—", "—", "—"))
            else:
                print("  %-18s %-4s %8.2f %6.2f %6.2f %+6.2f" % (
                    NAME[arm], t, hit / n, add / n, lose / n, (add - lose) / n))

    print("\n=== 汇总（12 份/臂）===")
    print("  臂                  命中事实/份  新增/份  丢失/份   净/份")
    for arm in ARMS:
        a = agg[arm]
        if not a["n"]:
            continue
        n = a["n"]
        print("  %-18s %10.2f  %7.2f  %7.2f  %+6.2f" % (
            NAME[arm], a["hit"] / n, a["add"] / n, a["lose"] / n, (a["add"] - a["lose"]) / n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
