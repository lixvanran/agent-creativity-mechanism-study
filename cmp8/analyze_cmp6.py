# -*- coding: utf-8 -*-
"""跨厂商判官版分析器：7 臂 × 4 题 × 3 重复。

**与同源判官的关键差别**：被测 = MiniMax，**判官 = OpenRouter 上的 Grok**。
「判据与指标同源模型 ⇒ 判据无效」——判官和被测同厂容易对同一批错误达成一致。

**纪律：判官必须先通过自检，自检不过就拒绝出数**（不是出数了再解释）。
自检 = 已知的真断言（应判支持）+ 已知假断言（应判矛盾）。
假断言召回 <50% ⇒ 矛盾率不可信 ⇒ 整套作废。

**成本**：判官 ~170 次调用（Grok 3 Mini $0.30/$0.50 每 M）≈ $0.12；embedding ≈ $0.05。
"""
from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from creativity_lab.verify import check_claims, extract_claims   # noqa: E402
from creativity_lab import orclient                              # noqa: E402
from creativity_lab import judge_cache                           # noqa: E402

OUT = os.environ.get("CMP_OUT", "runs/cmp8")
# 答案从 ANS_DIR 读（默认 = OUT）；遍2 用 ANS_DIR=<遍1 目录>，输出仍写到 OUT
ANS_DIR = os.environ.get("ANS_DIR", OUT)
ARMS = ["A1", "A2", "A3", "A4", "A5a", "A5b", "A5c"]
ARM_NAME = {
    "A1": "① 直调", "A2": "② 开源ADHD项目(机制复现)", "A3": "③ 双轴·融合门",
    "A4": "④ 双轴·去融合门", "A5a": "⑤a 新架构·无核验(控制)",
    "A5b": "⑤b 新架构·学到的策略", "A5c": "⑤c 新架构·初始w=0(控制)",
}
TIDS = ["A1", "A2", "A3", "A4"]
QS = {
    "A1": "湖北考生，物理类620分，想学AI，应当如何选择大学？",
    "A2": "公路自行车个人比赛（无车队），单圈1.6km共计15圈，单圈由两个800m直路和两个回头弯构成，"
          "本人在大集团里处于中上等水平，该如何安排战术？",
    "A3": "今天是五一小长假的最后一天的18:00，明天就要上学了，我的作业还一笔没动，怎么办？",
    "A4": "这是一份陈会昌气质量表的最终得分：胆汁质-6，多血质23，粘液质-4，抑郁质-1。",
}
EV = {}
for _i in (1, 2, 3, 4):
    _p = os.path.join(HERE, "creativity_lab", "data", "user4_q%d.json" % _i)
    if os.path.exists(_p):
        EV["A%d" % _i] = json.load(open(_p, encoding="utf-8"))["evidence"]

SELFCHECK = {
    "A1": {"T": ["2025年湖北省普通高考首选物理类中，620分及以上的累计人数为7436人"],
           "F": ["2025年湖北省普通高考首选物理类中，620分及以上的累计人数为74360人"]},
    "A2": {"T": ["国际自行车联盟（UCI）公路赛规则第 2.3.012 条规定，比赛中任何两名车手之间都可以互相提供食物、饮品、扳手等小帮助"],
           "F": ["国际自行车联盟（UCI）公路赛规则第 2.3.012 条规定，比赛中任何两名车手之间不得互相提供食物、饮品、扳手等小帮助"]},
    "A3": {"T": ["番茄工作法由意大利人 Francesco Cirillo 在上世纪八十年代做大学生时用番茄形厨房计时器发展而来"],
           "F": ["番茄工作法规定每个番茄时段为 50 分钟，之后休息 10 分钟"]},
    "A4": {"T": ["如果四类得分中有一类得分明显高出其它三种且均高出4分以上，则可定为该类气质型",
                 "该类得分超过20分则为典型型，该类得分在10至20分则为一般型"],
           "F": ["如果四类得分中有一类得分明显高出其它三种且均高出2分以上，则可定为该类气质型",
                 "该类得分超过30分则为典型型，该类得分在20至30分则为一般型"]},
}


def dedup_with(emb, claims, thr=0.75):
    """用指定 embedding 去重（emb 需有 .embed(list) -> list[list[float]]）。"""
    if not claims:
        return []
    try:
        V = np.array(emb.embed(list(claims)), dtype=float)
        if V.ndim != 2 or V.shape[0] != len(claims):
            raise ValueError("shape %s" % (V.shape,))
        V = V / np.clip(np.linalg.norm(V, axis=1, keepdims=True), 1e-9, None)
        S = V @ V.T
        keep = []
        for i in range(len(claims)):
            if all(S[i, j] < thr for j in keep):
                keep.append(i)
        return [claims[i] for i in keep]
    except Exception as e:
        print("  [embed 失败，降级到字符bigram] %s" % str(e)[:60], flush=True)
        keep, G = [], []
        for c in claims:
            t = re.sub(r"\s", "", c or "")
            g = {t[i:i + 2] for i in range(len(t) - 1)}
            if all(len(g & g2) / max(len(g | g2), 1) < thr for g2 in G):
                keep.append(c)
                G.append(g)
        return keep


def arm_file(arm, tid, rep):
    """A5 系列的交付答案 = 合成版（与其它臂同为流式答复）；机械装配版另存。"""
    if arm.startswith("A5"):
        s = "%s/%s_r%d_%s_synth.md" % (ANS_DIR, tid, rep, arm)
        if os.path.exists(s) and os.path.getsize(s) > 40:
            return open(s, encoding="utf-8").read()
    p = "%s/%s_r%d_%s.md" % (ANS_DIR, tid, rep, arm)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def main():
    os.makedirs(OUT, exist_ok=True)
    judge = orclient.LLM()
    emb = orclient.Embedder()
    CACHE = judge_cache.load()
    _cstat = {"hit": 0, "miss": 0}

    # ---------- 第一步：判官自检（不过就停）----------
    print("【判官自检】%s" % orclient.PRIMARY, flush=True)
    tp = fn = tn = fp = 0
    sc_detail = []
    for tid in TIDS:
        for lab, want in (("T", "支持"), ("F", "矛盾")):
            claims = SELFCHECK[tid][lab]
            v = check_claims(judge, QS[tid], EV.get(tid, ""), claims)
            for c in claims:
                got = v.get(c, "解析失败")
                ok = (got == want)
                if lab == "T":
                    tp += 1 if ok else 0
                    fn += 0 if ok else 1
                else:
                    tn += 1 if ok else 0
                    fp += 0 if ok else 1
                sc_detail.append((tid, lab, got, ok, c[:50]))
                print("  %s %s → %-4s %s" % (tid, lab, got, "✓" if ok else "✗"), flush=True)
    print("自检：真断言 %d/%d ｜ 假断言 %d/%d" % (tp, tp + fn, tn, tn + fp), flush=True)
    if (tn + fp) and tn / (tn + fp) < 0.5:
        print("❌ 判官在「已知假断言」上召回不足 50% ⇒ 矛盾率不可信，**拒绝出数**。")
        json.dump(dict(detail=sc_detail, aborted=True),
                  open("%s/judge_selfcheck.json" % OUT, "w"), ensure_ascii=False, indent=1)
        return
    # ★ 补「已知真断言」侧检查（同一阈值 0.5，不新增口径；见 patch_gate.py 头注）
    if (tp + fn) and tp / (tp + fn) < 0.5:
        print("❌ 判官在「已知真断言」上召回不足 50% ⇒ 判据分不开对错，**拒绝出数**。")
        json.dump(dict(detail=sc_detail, aborted=True),
                  open("%s/judge_selfcheck.json" % OUT, "w"), ensure_ascii=False, indent=1)
        return
    json.dump(dict(detail=sc_detail, tp=tp, fn=fn, tn=tn, fp=fp, aborted=False,
                   judge=orclient.PRIMARY),
              open("%s/judge_selfcheck.json" % OUT, "w"), ensure_ascii=False, indent=1)

    # ---------- 第二步：逐份核验 ----------
    def one(arm, tid, rep):
        txt = arm_file(arm, tid, rep)
        if len(txt.strip()) < 50:
            # ★ 产出有效性闸门（项目既有纪律：< 50 字 = 产出无效 ⇒ 记 error，不入统计）。
            #   为什么必须卡长度而不只是"非空"：一个 30 字的空壳若以 conflict=0 进入均值，
            #   会把该臂的矛盾率**稀释得更好看** ⇒ 静默偏向该臂。
            #   判据与 A5 臂 synth 文件的 >40 字节门槛一致。
            return dict(arm=arm, tid=tid, rep=rep, chars=len(txt.strip()), n_raw=0, width=0,
                        sup=0, con=0, unt=0, nc=0, conflict=0.0, support=0.0,
                        n_parsefail=0, parsefail_rate=0.0,
                        claims=[], verd={}, empty=True, invalid="short_or_empty_output")
        claims = None
        j = "%s/%s_r%d_%s.json" % (ANS_DIR, tid, rep, arm)
        if arm.startswith("A5") and os.path.exists(j):
            try:
                d = json.load(open(j, encoding="utf-8"))
                if d.get("claims"):
                    claims = list(d["claims"])
            except Exception:
                pass
        # ★ 判官结果缓存：遍2 的唯一变量是 embedding 通道 ⇒ verdict 应当原样复用
        #   （否则判官成本付两遍 ⇒ 破 $1 上限）。键含原文 sha1 ⇒ 原文变了自动失效。
        with judge_cache.LOCK:
            _e = judge_cache.get(CACHE, arm, tid, rep, txt)
            if _e is not None:
                claims = _e["claims"]
                verd = {c: _e["verd"].get(c) for c in claims}
                _cstat["hit"] += 1
            else:
                if claims is None:
                    claims = extract_claims(judge, txt)
                verd = check_claims(judge, QS[tid], EV.get(tid, ""), claims) if claims else {}
                judge_cache.put(CACHE, arm, tid, rep, txt, claims, verd)
                _cstat["miss"] += 1
        n_parsefail = sum(1 for c in claims if verd.get(c) not in
                           ("支持", "矛盾", "未提及", "非主张"))
        legal = [c for c in claims if verd.get(c) in ("支持", "矛盾")]
        sup = sum(1 for c in legal if verd.get(c) == "支持")
        con = sum(1 for c in legal if verd.get(c) == "矛盾")
        unt = sum(1 for c in claims if verd.get(c) == "未提及")
        nc = sum(1 for c in claims if verd.get(c) == "非主张")
        dd = dedup_with(emb, claims, 0.75)
        return dict(arm=arm, tid=tid, rep=rep, chars=len(txt), n_raw=len(claims),
                    width=len(dd), sup=sup, con=con, unt=unt, nc=nc,
                    n_parsefail=n_parsefail,
                    parsefail_rate=(n_parsefail / max(len(claims), 1)),
                    conflict=con / max(len(legal), 1), support=sup / max(len(legal), 1),
                    claims=claims, verd=verd, txt=txt, empty=False)

    jobs = [(a, t, r) for a in ARMS for t in TIDS for r in (1, 2, 3)]
    rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(one, *j): j for j in jobs}
        done = 0
        for f, j in futs.items():
            try:
                rows.append(f.result())
            except Exception as e:
                print("ERR", j, str(e)[:80], flush=True)
            done += 1
            if done % 10 == 0:
                print("  核验 %d/%d" % (done, len(jobs)), flush=True)

    # ---------- 第三步：汇总 ----------
    summary = []
    for a in ARMS:
        rr = [r for r in rows if r["arm"] == a]
        if not rr:
            continue
        per_t = {}
        for t in TIDS:
            sub = [r for r in rr if r["tid"] == t and not r.get("empty")]
            if not sub:
                continue
            allc = []
            for r in sub:
                allc.extend(r.get("claims") or [])
            uni = dedup_with(emb, allc, 0.75) if allc else []
            texts = [r["txt"] for r in sub if r["txt"].strip()]
            disp = None
            if len(texts) >= 2:
                try:
                    V = np.array(emb.embed(texts), dtype=float)
                    V = V / np.clip(np.linalg.norm(V, axis=1, keepdims=True), 1e-9, None)
                    S = V @ V.T
                    ds = [1 - S[i, j] for i in range(len(S)) for j in range(i + 1, len(S))]
                    disp = float(np.mean(ds)) if ds else None
                except Exception:
                    disp = None
            legaln = sum(r["sup"] + r["con"] for r in sub)
            per_t[t] = dict(
                chars=float(np.mean([r["chars"] for r in sub])),
                width=float(np.mean([r["width"] for r in sub])),
                union_width=len(uni),
                n_raw=float(np.mean([r["n_raw"] for r in sub])),
                conflict=(sum(r["con"] for r in sub) / max(legaln, 1)),
                support=(sum(r["sup"] for r in sub) / max(legaln, 1)),
                unt=float(np.mean([r["unt"] for r in sub])),
                nc=float(np.mean([r["nc"] for r in sub])),
                parsefail_rate=float(np.mean([r.get("parsefail_rate", 0.0) for r in sub])),
                n_parsefail=int(sum(r.get("n_parsefail", 0) for r in sub)),
                disp=disp, n_legal=legaln,
                per_rep_conflict=[r["conflict"] for r in sub])
        n_valid = sum(1 for r in rr if not r.get("empty"))
        n_total = len(rr)
        excluded = [(r["tid"], r["rep"], r.get("chars", 0), r.get("invalid", "empty"))
                    for r in rr if r.get("empty")]
        summary.append(dict(arm=a, name=ARM_NAME.get(a, a), per_t=per_t,
                            n_valid=n_valid, n_total=n_total, excluded=excluded))

    census = dict(judge.model_used)
    jm = ",".join(sorted(judge.model_used)) or orclient.PRIMARY
    same_vendor = ("minimax" in jm.lower())     # 判官退到 MiniMax = 同源 ⇒ 必须声明
    json.dump(dict(rows=[{k: v for k, v in r.items() if k != "txt"} for r in rows],
                   summary=summary, judge=orclient.PRIMARY, judge_used=jm,
                   judge_same_vendor=same_vendor, embed=emb.used, census=census,
                   parsefail_rate={s_["arm"]: {t: pt[t].get("parsefail_rate", 0.0)
                                               for t in pt} for s_ in summary for pt in [s_["per_t"]]},
                   samples={s_["arm"]: dict(valid=s_.get("n_valid", 0), total=s_.get("n_total", 0),
                                            excluded=s_.get("excluded", [])) for s_ in summary},
                   judge_reused=(_cstat["hit"] > 0),
                   judge_cache=dict(hit=_cstat["hit"], miss=_cstat["miss"], path=judge_cache.path())),
              open("%s/analysis.json" % OUT, "w"), ensure_ascii=False, indent=1, default=str)

    try:
        judge_cache.save(CACHE)
        print("  判官缓存已写：%s（命中 %d / 未命中 %d）" % (judge_cache.path(), _cstat["hit"], _cstat["miss"]))
    except Exception as e:
        print("  [判官缓存写盘失败] %s" % str(e)[:80])

    print("\n" + "=" * 112)
    print("去重体检（判据：保留率 = width / n_raw）")
    print("%-28s %9s %9s %9s  %s" % ("臂", "n_raw", "去重宽", "保留率", "判读"))
    for s_ in summary:
        pt = s_["per_t"]
        def m(k):
            v = [x[k] for x in pt.values() if x.get(k) is not None]
            return sum(v) / max(len(v), 1)
        nr, w = m("n_raw"), m("width")
        rate = (w / nr) if nr else 0.0
        if nr and rate < 0.15:
            verdict = "⚠️ 去重几乎全合并 ⇒ 宽度轴退化"
        elif nr and rate > 0.85:
            verdict = "⚠️ 去重几乎没起作用 ⇒ 阈值太松"
        else:
            verdict = "去重在工作，宽度轴可用"
        print("%-28s %9.1f %9.1f %8.1f%%  %s" % (s_["name"], nr, w, 100 * rate, verdict))
    print("  （n_raw 不依赖 embedding，是最无争议的广度指标；width 受 embedding 通道影响）")
    print("  产出有效性闸门（<50 字 = 产出无效 ⇒ 不入统计；**必须报出丢了哪些样本**）")
    any_ex = False
    for s_ in summary:
        ex = s_.get("excluded") or []
        if ex:
            any_ex = True
            print("    %-28s 有效 %d/%d，被排除: %s"
                  % (s_["name"], s_.get("n_valid", 0), s_.get("n_total", 0),
                     ", ".join("%s/r%d(%d字,%s)" % e for e in ex)))
    if not any_ex:
        print("    （无样本被排除）")
    print("  判官解析失败率（截断/解析异常的可见症状；解析失败不进分母，但会悄悄缩小分母）")
    for s_ in summary:
        pt = s_["per_t"]
        def _mp(k):
            v = [x[k] for x in pt.values() if x.get(k) is not None]
            return sum(v) / max(len(v), 1)
        pf = _mp("parsefail_rate")
        npf = sum(x.get("n_parsefail", 0) for x in pt.values())
        flag = "⚠ 解析失败率偏高 ⇒ 该臂矛盾率的分母被悄悄缩小，结论要打折" if pf > 0.10 else ""
        print("    %-28s 解析失败 %5.1f%%（%d 条） %s" % (s_["name"], 100 * pf, npf, flag))

    print("\n" + "=" * 112)
    print("交付答案（人工判读用）　判官=%s（实际 %s）　embedding=%s"
          % (orclient.PRIMARY, jm, emb.used))
    if same_vendor:
        print("⚠️⚠️ 判官与被测**同源**（都在 MiniMax）⇒ 判据有效性下降，结论只能当弱证据")
    print("=" * 112)
    print("%-28s %7s %7s %7s %9s %9s %8s %8s" %
          ("臂", "字符", "断言数", "去重宽", "矛盾率", "支持率", "离散度", "样本"))
    for s in summary:
        pt = s["per_t"]

        def m(k):
            vals = [v[k] for v in pt.values()]
            return sum(vals) / max(len(vals), 1)
        disp = [v["disp"] for v in pt.values() if v.get("disp") is not None]
        print("%-28s %7.0f %7.1f %7.1f %8.1f%% %8.1f%% %8.3f %8s"
              % (s["name"], m("chars"), m("n_raw"), m("width"), 100 * m("conflict"),
                 100 * m("support"), sum(disp) / max(len(disp), 1) if disp else 0,
                 "%d/%d" % (s.get("n_valid", 0), s.get("n_total", 0))))
    for key, ttl in (("union_width", "并集宽度（3 份去重并集）"),
                     ("conflict", "矛盾率（按题）")):
        print("\n%s" % ttl)
        print("%-28s %s" % ("臂", "  ".join("%7s" % t for t in TIDS)))
        for s in summary:
            if key == "conflict":
                cells = "  ".join("%6.0f%%" % (100 * s["per_t"].get(t, {}).get("conflict", 0))
                                  for t in TIDS)
            else:
                cells = "  ".join("%7d" % s["per_t"].get(t, {}).get("union_width", 0) for t in TIDS)
            print("%-28s %s" % (s["name"], cells))
    print("\n【⑤b 学到的策略 vs ⑤c 初始 w=0】")
    for s in summary:
        if s["arm"] in ("A5b", "A5c"):
            per_rep = []
            for t in TIDS:
                per_rep += s["per_t"].get(t, {}).get("per_rep_conflict", []) or []
            sp = np.std(per_rep) if len(per_rep) > 1 else 0
            print("  %-22s 逐份矛盾率均值 %.3f ｜ **种子间标准差 %.3f**"
                  % (s["name"], np.mean(per_rep) if per_rep else 0, sp))
    print("\n模型用量:", json.dumps(census, ensure_ascii=False))
    print("DONE → %s/analysis.json" % OUT)


if __name__ == "__main__":
    main()
