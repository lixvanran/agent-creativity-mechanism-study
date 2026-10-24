# -*- coding: utf-8 -*-
"""路线 C · 拓扑执行器（stage machine）。

一个 episode = 给定 (任务, 拓扑模板, 参数向量) ⇒ 跑出：
  - 内部产生的断言流 + 判官标签（stage=internal）
  - 机械装配的最终答案（stage=final）
  - 训练侧代理指标（不含任何"维度数"结论）

⚠️ **谁能看到什么**由拓扑的 `info_access` 决定：
  - GEN 只能看题面（+ 冻结认知位置），**看不到**依据包；
  - VERIFY 是唯一接触依据包与判官的阶段；
  - MERGE 只看断言 + 标签，**看不到**题面以外的东西，更看不到结论空间/答案键。

⚠️ **装配不由模型重写**（协议 §4.5：机械答案 = 唯一评分对象）。
"""
from __future__ import annotations

import re

from params import FROZEN_ASSETS, default_theta, degenerate, validate
from topology import TEMPLATES

ANSWER_CAP = FROZEN_ASSETS["answer_cap_chars"]


# ---------------------------------------------------------------- 文本工具
def _norm(s: str) -> str:
    return re.sub(r"[\s，。、；：,.;:!?！？「」『』（）()\[\]【】\"'’“”\-—…·]+", "", s or "")


def _bigrams(s: str) -> set:
    t = _norm(s)
    return {t[i:i + 2] for i in range(len(t) - 1)} or {t}


def jaccard(a: str, b: str) -> float:
    ga, gb = _bigrams(a), _bigrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / max(len(ga | gb), 1)


def _split_lines(t: str) -> list:
    out = []
    for ln in (t or "").splitlines():
        ln = re.sub(r"^\s*[-*\d.、)）]+\s*", "", ln).strip()
        if 8 <= len(ln) <= 70 and ln not in out:
            out.append(ln)
    return out


# ---------------------------------------------------------------- 判官标签
SUPPORT, CONTRADICT, UNMENTIONED, NONCLAIM, UNVERIFIED = (
    "支持", "矛盾", "未提及", "非主张", "未核验")


#: 效用刻度（D2 的 utility）：门控按这张刻度把"信息"分级。
#: 关键点：**支持(1.0) 永远 ≥ 任何 theta_util(≤1.0)** ⇒ 支持的断言不会被门控挡掉；
#: 门控真正挡的是"依据未覆盖/非主张/未核验"这些**不该冒充成立**的内容。
UTILITY_SCALE = {
    SUPPORT: 1.00,      # 被依据支持
    UNMENTIONED: 0.25,  # 依据没覆盖（不一定错，但没有被支持）
    NONCLAIM: 0.10,     # 非主张（连可核验的命题都不是）
    UNVERIFIED: 0.00,   # 未经核验
    CONTRADICT: 0.00,   # 矛盾：**永不交付**（且单独计数）
}


def support_score(v: str) -> float:
    return UTILITY_SCALE.get(v, 0.0)


# ---------------------------------------------------------------- 执行器
class Episode:
    def __init__(self, topic: dict, topology_id: str, theta: dict, llm, verifier,
                 max_calls: int = 14):
        self.topic = topic
        self.tid = topology_id
        self.spec = TEMPLATES[topology_id]
        self.theta = theta
        self.llm = llm
        self.verifier = verifier
        self.max_calls = max_calls
        self.claims: list[dict] = []          # {text, verdict, origin_op, frame}
        self.drafts: list[dict] = []
        self.stage_log: list[dict] = []
        self.n_calls = 0
        self.n_tokens = 0
        self.degeneracies = degenerate(theta, topology_id)
        self.violations = validate(theta, topology_id)

    # ---------------------------------------------------------- 基础工具
    def _call(self, prompt: str, purpose: str, max_tokens: int = 1200,
              min_ok: int = 20) -> str:
        if self.n_calls >= self.max_calls:
            self.stage_log.append(dict(stage="BUDGET_STOP", purpose=purpose, ok=False))
            return ""
        self.n_calls += 1
        out = self.llm.chat(prompt, purpose=purpose, max_tokens=max_tokens,
                            budgets=(max_tokens + 800,), min_ok=min_ok) or ""
        return out

    def _log(self, stage: str, **kw):
        self.stage_log.append(dict(stage=stage, calls=self.n_calls, **kw))

    def _frames(self) -> list:
        n = self.spec.get("n_frames_fixed")
        if n is None:
            n = int(self.theta.get("n_frames", 1))
        n = max(1, min(n, len(FROZEN_ASSETS["frames"]) + 1))
        fr = [("直答", "")]
        for f in FROZEN_ASSETS["frames"][:n - 1]:
            fr.append((f, "你现在从【%s】这个认知位置出发去看这个问题。" % f))
        return fr

    # ---------------------------------------------------------- 阶段实现
    def _gen(self, frames=None, tag="GEN") -> list:
        """生成阶段：每个认知位置采样 n_cand 份草稿。"""
        outs = []
        frames = frames if frames is not None else self._frames()
        nc = int(self.theta.get("n_cand_per_frame", 1))
        cap = FROZEN_ASSETS["answer_cap_chars"]
        for fname, ang in frames:
            for k in range(nc):
                p = FROZEN_ASSETS["gen_prompt"].format(
                    ask=self.topic["ask"], ang=ang, cap=cap)
                txt = self._call(p, purpose="c_gen", min_ok=60)
                if txt:
                    self.drafts.append(dict(text=txt, frame=fname))
                    outs.append(txt)
        self._log(tag, drafts=len(self.drafts), frames=len(frames))
        return outs

    def _extract(self, drafts=None) -> list:
        """抽取阶段：每个草稿抽原子断言（**每份草稿恰好一次调用**）。"""
        drafts = drafts if drafts is not None else self.drafts
        min_dist = float(self.theta.get("theta_dist", 0.25))
        got = []
        for d in drafts:
            p = FROZEN_ASSETS["extract_prompt"].format(t=d["text"][:1200], n=10)
            txt = self._call(p, purpose="c_ex", min_ok=10)
            lines = _split_lines(txt)
            if not lines:                       # 兜底：不额外调用，退回句子切分
                lines = _split_lines(d["text"])
            for ln in lines[:10]:
                pool = self.claims + got
                if all((1.0 - jaccard(ln, c["text"])) >= min_dist - 1e-9 for c in pool):
                    got.append(dict(text=ln, verdict=UNVERIFIED, origin_op="EXTRACT",
                                    frame=d["frame"]))
        self.claims.extend(got)
        self._log("EXTRACT", new_claims=len(got), total=len(self.claims))
        return got

    def _verify(self, tag="VERIFY") -> int:
        """核验阶段：把未核验的断言送去判官。唯一接触依据包的阶段。"""
        todo = [c for c in self.claims if c["verdict"] == UNVERIFIED]
        budget = int(self.theta.get("n_verify_max", 6))
        todo = todo[:max(0, budget)]
        if not todo:
            self._log(tag, verified=0)
            return 0
        verd = self.verifier(self.topic["ask"], self.topic.get("evidence", ""),
                             [c["text"] for c in todo]) or {}
        n = 0
        for c in todo:
            v = verd.get(c["text"])
            c["verdict"] = v if v in (SUPPORT, CONTRADICT, UNMENTIONED, NONCLAIM) else UNVERIFIED
            if c["verdict"] != UNVERIFIED:
                n += 1
        self._log(tag, verified=n, of=len(todo))
        return n

    def _split(self) -> int:
        """拆分阶段：把复合断言拆开并回灌核验。"""
        k = int(self.theta.get("n_split_max", 0))
        if k <= 0:
            return 0
        cand = [c for c in self.claims if c["verdict"] in (UNVERIFIED, UNMENTIONED)][:k]
        min_dist = float(self.theta.get("theta_dist", 0.25))
        added = 0
        for c in cand:
            p = FROZEN_ASSETS["split_prompt"].format(c=c["text"])
            txt = self._call(p, purpose="c_split", min_ok=8)
            for ln in _split_lines(txt)[:4]:
                if all((1.0 - jaccard(ln, x["text"])) >= min_dist - 1e-9 for x in self.claims):
                    self.claims.append(dict(text=ln, verdict=UNVERIFIED,
                                            origin_op="SPLIT", frame=c["frame"]))
                    added += 1
        self._log("SPLIT", added=added)
        return added

    def _collapse_ratio(self) -> float:
        """坍缩近似：去重后断言数 / 草稿数（1.0 = 完全不塌缩）。"""
        if not self.drafts:
            return 1.0
        uniq = []
        for c in self.claims:
            if all(jaccard(c["text"], u) < 0.75 for u in uniq):
                uniq.append(c["text"])
        return min(len(uniq) / max(len(self.drafts), 1), 1.0)

    def _stall(self) -> bool:
        """停滞检测（**进展率**信号，P8 `theta_stall`）：用可核验信号，不用 embedding。

        进展率 = 被支持断言数 / 已核验断言数（全 episode 口径）。
        低于阈值 ⇒ 判停滞 ⇒ 调用方触发预算重分配。
        """
        th = float(self.theta.get("theta_stall", 0.5))
        if not self.claims:
            return False
        sup = [c for c in self.claims if c["verdict"] == SUPPORT]
        # 用「被支持断言数 / 已核验断言数」作为窗口内的进展率
        verified = [c for c in self.claims if c["verdict"] != UNVERIFIED]
        if not verified:
            return False
        rate = len(sup) / max(len(verified), 1)
        stalled = rate < th
        self._log("STALL", signal="progress_rate", rate=round(rate, 3), th=th, stalled=stalled)
        return stalled

    # ---------------------------------------------------------- 深挖回路（P12）
    def _n_supported(self) -> int:
        return sum(1 for c in self.claims if c["verdict"] == SUPPORT)

    def _deepen(self, stages) -> int:
        """**深挖回路**（P12 `stop_patience`）：在机械装配前最多再走几步。

        ★ 这是 P12 的**真实读取点**（复核 6b：`stop_patience` 原本是死参数）。
        - **一步** = 换一个**已授权的认知位置**（P1 授权的那几个，**不新增位置**），
          用**深挖提示词**（冻结资产 `deep_suffix`）再问一次 → 抽取 → 核验。
          ⇒ 不改变 P1 的语义；T1（只有「直答」一个位置）深挖只是对同一位置再问一次，
          **不破坏 T1「远不可得」的消融**。
        - **步数上限 = P12 `stop_patience`**：`0` = 不深挖 ⇒ 搜索空间在第一轮就闭合
          （这是「过早闭合」的对照臂）；`k>0` = 最多再走 k 步。
        - 每步「**没有新增被支持断言**」= 一次**空转**（= 没有新承重信息）；
          连续空转 ≥ P7 `stall_window`（**仅 T4 生效**）⇒ 判停滞 ⇒ 预算重分配 + 结束深挖。
        - 预算（`max_calls`）耗尽 ⇒ 立即结束（记 `BUDGET_STOP`）。

        ⚠️ 阶段**集合**不随 P12 改变：深挖只是把已有的 GEN/EXTRACT/VERIFY **再执行一遍**
        ⇒ 分离判据仍然成立（改变 P12 不改变「有哪些阶段、谁能看到什么」）。
        """
        patience = int(self.theta.get("stop_patience", 0))
        if patience <= 0:
            self._log("DEEPEN", steps=0, patience=patience,
                      reason="patience=0 ⇒ 不深挖（搜索空间立即闭合）")
            return 0
        positions = self._frames()            # 已授权位置（不新增）
        if not positions:
            return 0
        k = int(self.theta.get("stall_window", 0))    # ← P7 的真实读取点（无条件读）
        if "STALL" not in stages:
            k = 0                                    # 只在 T4（唯一含 STALL 阶段的模板）生效
        stall = 0
        steps = 0
        new_sup_total = 0
        for i in range(patience):
            if self.n_calls >= self.max_calls:
                self.stage_log.append(dict(stage="BUDGET_STOP", purpose="deepen", ok=False))
                break
            fname, ang = positions[i % len(positions)]
            deep_ang = ("%s\n%s" % (ang, FROZEN_ASSETS["deep_suffix"])).strip()
            before = self._n_supported()
            n0 = len(self.drafts)
            self._gen(frames=[(fname, deep_ang)], tag="DEEPEN")
            self._extract(self.drafts[n0:])
            self._verify("VERIFY_DEEP")
            new_sup = self._n_supported() - before
            new_sup_total += new_sup
            steps += 1
            stall = 0 if new_sup > 0 else stall + 1
            if k and stall >= k:
                # P7（连续空转窗口）⇒ 判停滞 ⇒ 预算重分配（与 P8 互补的第二个停滞信号）
                self._log("STALL", signal="consecutive_empty_steps", k=k, stall=stall,
                          steps=steps, stalled=True)
                self._reallocate()
                break
        self._log("DEEPEN", steps=steps, patience=patience, stall=stall,
                  new_supported=new_sup_total)
        return steps

    def _reallocate(self) -> int:
        """预算重分配：把剩余预算的 realloc_frac 比例给**未用过的认知位置**。"""
        frac = float(self.theta.get("realloc_frac", 0.0))
        if frac <= 0:
            return 0
        used = {d["frame"] for d in self.drafts}
        rest = [f for f in FROZEN_ASSETS["frames"] if f not in used]
        if not rest:
            return 0
        take = rest[:max(1, int(round(frac * len(rest))))]
        n0 = len(self.drafts)
        self._gen(frames=[(f, "你现在从【%s】这个认知位置出发去看这个问题。" % f)
                          for f in take], tag="REALLOC")
        self._extract(self.drafts[n0:])
        self._verify("VERIFY2")
        return len(self.drafts) - n0

    def _redistribute(self) -> int:
        """条件切换式重组：换**采样条件**（换认知位置），❌ 不加时间/放空/无关闲聊。"""
        used = {d["frame"] for d in self.drafts}
        rest = [f for f in FROZEN_ASSETS["frames"] if f not in used]
        if not rest:
            return 0
        n0 = len(self.drafts)
        self._gen(frames=[(rest[0], "你现在从【%s】这个认知位置出发去看这个问题。" % rest[0])],
                  tag="REDISTRIBUTE")
        self._extract(self.drafts[n0:])
        self._verify("VERIFY2")
        self._log("REDISTRIBUTE", drafts_added=len(self.drafts) - n0)
        return len(self.drafts) - n0

    # ---------------------------------------------------------- 装配
    def _cluster(self, claims):
        """贪心聚类（字面二元组 Jaccard ≥ 0.75 视为同族）。"""
        clusters = []
        for c in claims:
            for cl in clusters:
                if jaccard(c["text"], cl[0]["text"]) >= 0.75:
                    cl.append(c)
                    break
            else:
                clusters.append([c])
        return clusters

    def _merge(self) -> str:
        strat = self.spec["merge_strategy"]
        if strat == "verbatim":
            best = max(self.drafts, key=lambda d: len(d["text"])) if self.drafts else None
            body = best["text"] if best else "（无产出）"
            self._log("MERGE", strategy=strat, delivered=1)
            return body[:ANSWER_CAP]
        m = int(self.theta.get("m_clusters", 4))
        th = float(self.theta.get("theta_util", 0.0))
        # ★ 效用门控（D2）：**低于阈值的内容不交付**（不是换个分节塞进去）。
        #   理由：若低效用内容照样进答案，门控就只是"换个标签"，对指标零影响 ⇒
        #   它既学不动、也防不住"降门控换宽度"。这里让门控**真的减内容**。
        #   挡掉的条数在 n_claims_below_gate 里计数上报（不丢账）。
        main, other, unv, bad, below = [], [], [], [], []
        for c in self.claims:
            if c["verdict"] == CONTRADICT:
                bad.append(c)
                continue
            if support_score(c["verdict"]) >= th:
                if c["verdict"] == SUPPORT:
                    main.append(c)
                elif c["verdict"] == UNVERIFIED:
                    unv.append(c)
                else:
                    other.append(c)
            else:
                below.append(c)
        sup = main
        clusters = self._cluster(sup)
        clusters.sort(key=lambda cl: (-len(cl), -len(cl[0]["text"])))
        picked = [cl[0] for cl in clusters][:m]
        if strat == "top_m_support":
            picked = sorted(sup, key=lambda c: (-support_score(c["verdict"]), -len(c["text"])))[:m]
        if strat == "pareto_frontier":
            picked = self._frontier(sup, m)
        lines = ["# 依据与判断", ""]
        lines += ["- " + c["text"] for c in picked] or ["- （无）"]
        if other:
            lines += ["", "## 依据未覆盖、仅供参考的事项"]
            lines += ["- " + c["text"] for c in other[:m]]
        if unv:
            lines += ["", "## 未经核验的断言（仅供你自行判断）"]
            lines += ["- " + c["text"] for c in unv[:m]]
        if bad:
            lines += ["", "<!-- 已剔除与依据冲突的内容 %d 条 -->" % len(bad)]
        out = "\n".join(lines)
        self._log("MERGE", strategy=strat, delivered=len(picked), dropped_conflict=len(bad),
                  below_gate=len(below), theta_util=th, m_clusters=m)
        self._merge_state = dict(main=picked, other=other[:m], unv=unv[:m],
                                 bad=bad, below=below, th=th, m=m)
        return out[:ANSWER_CAP]

    def _frontier(self, claims, m):
        """二维前沿：支持度 × 与其它候选的最大距离（不做加权求和）。"""
        if not claims:
            return []
        keep = []
        for c in claims:
            d = max([jaccard(c["text"], o["text"]) for o in claims if o is not c] or [0.0])
            keep.append((support_score(c["verdict"]), 1.0 - d, c))
        keep.sort(key=lambda x: (-x[0], -x[1]))
        return [x[2] for x in keep[:m]]

    # ---------------------------------------------------------- 主流程
    def run(self) -> dict:
        stages = self.spec["stages"]
        # GEN
        self._gen()
        # EXTRACT
        if "EXTRACT" in stages:
            self._extract()
        # VERIFY（含拆分的二次核验）
        if "VERIFY" in stages:
            self._verify()
        if "SPLIT" in stages:
            if self._split():
                self._verify("VERIFY2")
        # ★ 深挖回路（P12 stop_patience）：在装配前最多再走几步（何时停 = 可学）
        if "VERIFY" in stages:
            self._deepen(stages)
        # 停滞 → 预算重分配
        if "STALL" in stages and self._stall():
            self._reallocate()
        # 坍缩 → 条件切换式重组
        if "COLLAPSE" in stages:
            ratio = self._collapse_ratio()
            tau = float(self.theta.get("theta_collapse", 0.0))
            self._log("COLLAPSE", ratio=round(ratio, 3), tau=tau,
                      triggered=bool(tau > 0 and ratio < tau))
            if tau > 0 and ratio < tau:
                self._redistribute()
        # MERGE
        answer = self._merge()
        return self.diagnostics(answer)

    # ---------------------------------------------------------- 训练侧代理指标
    def diagnostics(self, answer: str) -> dict:
        sup = [c for c in self.claims if c["verdict"] == SUPPORT]
        con = [c for c in self.claims if c["verdict"] == CONTRADICT]
        unv = [c for c in self.claims if c["verdict"] == UNVERIFIED]
        legal = len(sup) + len(con)
        # 去重后的「被支持的不同断言数」= 训练侧宽度的代理量
        uniq = []
        for c in sup:
            if all(jaccard(c["text"], u) < 0.75 for u in uniq):
                uniq.append(c["text"])
        # ★ 被支持子集的文本：训练侧的正确性约束（key_conclusion_hit）**只在这上面算**，
        #   避免"未核验 / 未提及"的断言里偶然出现答案词就拿命中分（DESIGN.md §4.3）。
        supported_text = "\n".join(c["text"] for c in sup)
        # ★ 交付集（真正进了机械答案的断言）——训练目标 J 算在**交付集**上，
        #   这样装配旋钮（theta_util / m_clusters）才对 J 可见（DESIGN.md §4.3）。
        ms = getattr(self, "_merge_state", None) or {}
        delivered = list(ms.get("main") or []) + list(ms.get("other") or []) + \
            list(ms.get("unv") or [])
        # ★ 深挖回路的实际步数（P12 的可观测读数）：取最后一条 DEEPEN 汇总记录的 steps
        _deep = [e for e in self.stage_log if e.get("stage") == "DEEPEN"]
        n_deepen = int(_deep[-1].get("steps") or 0) if _deep else 0
        d_supp = [c for c in delivered if c["verdict"] == SUPPORT]
        d_unsupp = [c for c in delivered if c["verdict"] != SUPPORT]
        d_supp_u, d_unsupp_u = [], []
        for c in d_supp:
            if all(jaccard(c["text"], u) < 0.75 for u in d_supp_u):
                d_supp_u.append(c["text"])
        for c in d_unsupp:
            if all(jaccard(c["text"], u) < 0.75 for u in d_unsupp_u):
                d_unsupp_u.append(c["text"])
        return dict(
            topology=self.tid,
            theta=dict(self.theta),
            n_calls=self.n_calls,
            n_tokens=self.n_tokens,
            n_claims_total=len(self.claims),
            n_claims_supported=len(sup),
            n_claims_conflict=len(con),
            n_claims_unverified=len(unv),
            n_supported_distinct=len(uniq),
            conflict_rate_pre=(len(con) / legal) if legal else 0.0,
            conflict_n=len(con), conflict_den=legal,
            support_rate=(len(sup) / legal) if legal else 0.0,
            answer_chars=len(answer),
            answer=answer,
            supported_text=supported_text,
            # --- 交付集口径（训练目标 J 的输入）---
            n_delivered_total=len(delivered),
            n_delivered_supported=len(d_supp),
            n_delivered_unsupported=len(d_unsupp),
            n_delivered_supported_distinct=len(d_supp_u),
            n_delivered_unsupported_distinct=len(d_unsupp_u),
            n_claims_below_gate=len(ms.get("below") or []),
            n_deepen_steps=n_deepen,
            delivered_supported_text="\n".join(d_supp_u),
            delivered_claims=[dict(text=c["text"], verdict=c["verdict"],
                                    score=support_score(c["verdict"]))
                               for c in delivered],
            claims=[dict(text=c["text"], verdict=c["verdict"], origin_op=c["origin_op"],
                         frame=c["frame"]) for c in self.claims],
            stage_log=self.stage_log,
            degeneracies=self.degeneracies,
            violations=self.violations,
        )


def run_episode(topic, topology_id, theta=None, llm=None, verifier=None,
                max_calls: int = 14) -> dict:
    theta = dict(theta or default_theta())
    ep = Episode(topic, topology_id, theta, llm, verifier, max_calls=max_calls)
    return ep.run()
