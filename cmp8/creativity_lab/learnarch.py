"""可学习架构：参数化的 episode 执行器。

与 train_policy.py 的差别只有一个：把「依据包 / 角度表 / 是否允许核验」都变成参数，
这样同一套架构既能跑政策域（训练用），也能跑用户的四道题（外部测试集）。

**关键：角度表不进入特征。** op_features 只看 op 类型、目标节点状态和本分支历史，
所以换一套角度（7 个认知位置）不改变学到的权重，只改变「探索什么」。
"""
from __future__ import annotations
import os
import re
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from creativity_lab.client import LLM                        # noqa: E402
from creativity_lab.metrics import _mat                     # noqa: E402
from creativity_lab.ops import Graph, assemble, op_features  # noqa: E402
from creativity_lab.verify import check_claims, extract_claims  # noqa: E402

CONFLICT_CAP = 0.33
GEN_Q = "问题：{ask}\n\n{ang}\n\n给出你的判断与具体做法，400字以内。"
EXTRACT_Q = ("从下面这段回答里，逐条列出其中**可判真假的陈述**（数字、法规、权利义务、"
             "程序、时限、主体责任、事实断言）。不要观点和建议。一行一条，最多 10 条。\n\n{t}")
SPLIT_Q = ("把下面这条陈述拆成可以分别核验的独立陈述（如果它含多个断言就拆开）。"
           "一行一条，只输出拆分结果。\n\n{c}")
SYNTH_Q = ("问题：{ask}\n\n以下是经过核验后保留下来的事实性要点（每行一条）：\n{pts}\n\n"
           "请把这些要点写成一份 400 字以内、可直接执行的答复。观点明确、给出具体动作与依据，"
           "不要罗列各方观点，不要写空话。只输出答复正文。")


def _char_bg(t):
    t = re.sub(r"\s", "", t or "")
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _fb_dedup(claims, thr=0.75):
    keep, G = [], []
    for c in claims:
        g = _char_bg(c)
        if all(len(g & g2) / max(len(g | g2), 1) < thr for g2 in G):
            keep.append(c)
            G.append(g)
    return keep


def embed_rows(ts):
    """embed 接口会瞬时返回 None → 重试 → 仍失败则由 dedup_n 降级。
    踩过的坑：不加这个，一次 API 抖动就让整个训练进程崩掉。"""
    uniq, idx, seen = [], [], {}
    for t in ts:
        if t not in seen:
            seen[t] = len(uniq)
            uniq.append(t)
        idx.append(seen[t])
    last = None
    for attempt in range(3):
        try:
            V = _mat(LLM().embed(uniq))
            if V is not None and V.shape[0] == len(uniq):
                return V[idx]
            last = "embed 返回 %s 行" % (getattr(V, "shape", None),)
        except Exception as e:
            last = str(e)[:70]
        time.sleep(3 + attempt * 4)
    raise RuntimeError("embed 不可用: %s" % last)


def dedup_n(claims, thr=0.75):
    if not claims:
        return []
    try:
        M = embed_rows(claims)
        S = M @ M.T
        keep = []
        for i in range(len(claims)):
            if all(S[i, j] < thr for j in keep):
                keep.append(i)
        return [claims[i] for i in keep]
    except Exception:
        return _fb_dedup(claims, thr)


def run_episode(ask, w, rng, ev=None, angles=None, budget=10, explore=0.25,
                use_verify=True, synth=False, llm=None):
    """跑一遍图搜索。

    ask     —— 问题（**工作流只能看到这个**）
    ev      —— 依据包文本；use_verify=True 时必填
    angles  —— [(frame_name, frame_prompt, persona, model), ...]；GEN_ANGLE 用
    w       —— 策略权重（14 维）
    """
    llm = llm or LLM()
    angles = angles or []
    g = Graph()
    rewards, traj, ophist = [], [], {}
    n_verify = n_hit = n_miss = 0
    step = 0
    ang_i = 0
    while step < budget:
        step += 1
        cands = [("GEN_PLAIN", None), ("GEN_ANGLE", None)]
        for n in g.of_kind("ANSWER")[-1:]:
            cands.append(("EXTRACT", n))
        if use_verify and ev:
            for n in [x for x in g.of_kind("CLAIM") if x.verdict is None][:2]:
                cands.append(("VERIFY", n))
        for n in g.of_kind("CLAIM")[:1]:
            if n.verdict in (None, "未提及"):
                cands.append(("SPLIT", n))
        # STOP 只在**至少核验过一次**后合法：否则 episode 在还没抽出断言时就结束，
        # 策略永远走不到 VERIFY 阶段（实测：平均 2.8 步就停，VERIFY=0）。
        if n_verify >= 1:
            cands.append(("STOP", None))

        cand_f, scored = [], []
        for op, tgt in cands:
            f = np.array(op_features(g, op, tgt, step))
            cand_f.append(f)
            sc = float(w @ f)
            if rng.random() < explore:
                sc += rng.random() * 2.0
            scored.append((sc, op, tgt))
        # ⚠️ 排序键必须是**分数** x[0]。写成 x[1][0] 会按 op 的**字符串**倒序排，
        #    等价于「永远选字母序第一个动作」——策略学习从未发生（踩过这个致命 bug）。
        scored.sort(key=lambda x: -x[0])
        op, tgt = scored[0][1], scored[0][2]
        ophist[op] = ophist.get(op, 0) + 1
        order = sorted(range(len(scored)), key=lambda i: -scored[i][0])
        F = np.array([cand_f[i] for i in order])
        s_all = np.array([scored[i][0] for i in order])
        traj.append((F, s_all, 0))
        rewards.append(0.0)

        if op == "STOP":
            break
        if op == "GEN_PLAIN":
            a = llm.chat(GEN_Q.format(ask=ask, ang=""), purpose="al_gen", min_ok=150)
            if a and len(a) > 40:
                g.add("ANSWER", a, op="GEN_PLAIN")
        elif op == "GEN_ANGLE":
            if not angles:
                continue
            fn, fp, pe, md = angles[ang_i % len(angles)]
            ang_i += 1
            a = llm.chat(GEN_Q.format(
                ask=ask,
                ang="你现在从【%s】这个认知位置出发去看这个问题。%s\n设定：%s" % (fn, fp, pe)),
                model=md, purpose="al_gen", min_ok=150)
            if a and len(a) > 40:
                g.add("ANSWER", a, op="GEN_ANGLE", angle=fn)
        elif op == "EXTRACT":
            answers = g.of_kind("ANSWER")
            if not answers:
                continue
            src = answers[-1]
            t = llm.chat(EXTRACT_Q.format(t=src.text[:1200]), purpose="al_ex",
                         max_tokens=1400, budgets=(2000,), min_ok=15)
            got = 0
            for ln in (t or "").splitlines():
                ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
                if 8 <= len(ln) <= 60:
                    g.add("CLAIM", ln, parent=src.nid, op="EXTRACT")
                    got += 1
                if got >= 10:
                    break
        elif op == "SPLIT":
            t = llm.chat(SPLIT_Q.format(c=tgt.text), purpose="al_split",
                         max_tokens=800, budgets=(1200,), min_ok=10)
            got = 0
            for ln in (t or "").splitlines():
                ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
                if 8 <= len(ln) <= 60 and ln != tgt.text:
                    g.add("CLAIM", ln, parent=tgt.nid, op="SPLIT")
                    got += 1
                if got >= 4:
                    break
        elif op == "VERIFY":
            v = check_claims(llm, ask, ev, [tgt.text])
            vd = v.get(tgt.text, "解析失败")
            tgt.verdict = vd
            n_verify += 1
            if vd == "支持":
                n_hit += 1
            elif vd == "矛盾":
                n_miss += 1

    # ---- 终局：机械装配 ----
    final = assemble(g, ask)
    claims = extract_claims(llm, final)
    # 兜底：一条断言都没抽出来时（例如策略没选到 EXTRACT），机械装配会产出空壳。
    # 这时退回最长的那份 ANSWER 节点 —— 工程兜底，不是测量技巧，**但必须在报告里声明**。
    fallback = False
    if not claims:
        ans = g.of_kind("ANSWER")
        if ans:
            best = max(ans, key=lambda n: len(n.text))
            final = "# %s\n\n%s" % (ask, best.text)
            claims = extract_claims(llm, final)
            fallback = True
    verd = check_claims(llm, ask, ev, claims) if (ev and claims) else {}
    legal = [c for c in claims if verd.get(c) in ("支持", "矛盾")]
    ncon = sum(1 for c in legal if verd.get(c) == "矛盾")
    crate = ncon / max(len(legal), 1)
    width = len(dedup_n(claims, 0.75))
    fin = (width / 5.0) if crate <= CONFLICT_CAP else -2.0

    # ---- 人类可读版：模型只拿「支持/未提及/未核验」的断言重写（矛盾已剔除）----
    synth_txt = ""
    if synth:
        pts = [n.text for n in g.of_kind("CLAIM")
               if n.verdict in ("支持", "未提及") or n.verdict is None]
        if not pts and not use_verify:
            pts = [n.text for n in g.of_kind("CLAIM")]
        if pts:
            synth_txt = llm.chat(SYNTH_Q.format(ask=ask, pts="\n".join("- " + p for p in pts)),
                                 purpose="al_syn", max_tokens=2000,
                                 budgets=(3000,), min_ok=60) or ""

    return g, rewards, dict(width=width, conflict=crate, n_legal=len(legal),
                             n_verify=n_verify, hit=n_hit, miss=n_miss, fin=fin,
                             ops=dict(ophist), final=final, synth=synth_txt,
                             claims=claims, verd=verd, fallback=fallback)
