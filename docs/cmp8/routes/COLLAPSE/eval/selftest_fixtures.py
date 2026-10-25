# -*- coding: utf-8 -*-
"""`vd_anchor_out` 的自检闸门（协议 §3.3 F7 / §2.2 抽取器自检）。

> 2026-10-22 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/selftest_fixtures.py`
> 配套：`vd_anchor_out.py`

## 为什么自检要自带**变异注入**

第四组踩过的坑（`g4-argumentation`）：
**负向测试自己会假阴性** —— 一个"坏实现"也可能通过你写的负向测试。
⇒ 所以这里不只断言"闸门会拒绝坏卡"，还要断言**"把闸门的某一条拆掉，测试必须变红"**。
拆不掉 ⇒ 这个条件根本没被测到 ⇒ 报红，不许放过。

## 两层自检

| 层 | 要不需要 API | 查什么 |
|:-:|:-:|---|
| **A · 机械层** | **不要** | AO-GATE 的 8 条判定逻辑 + 变异注入敏感性 + 失败不许静默变 0 |
| **B · 判官层** | 要 | ① 岔口归并与 DEV 金标的一致性（纯度/分离度）② 判官自检（真锚外卡 / 假锚外卡）|

⇒ **B 层不过 ⇒ 拒绝出数**（协议 F7）。B 层需要 `MINIMAX_SUBSCRIPTION_KEY`（或 `--judge-vendor openrouter`）。
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import vd_anchor_out as V  # noqa: E402


# ──────────────────────────────────────────────────────────────
# 合成夹具：一段"假的答案"，带**已知**的锚外卡与已知缺陷
# ──────────────────────────────────────────────────────────────
def _card(idx: int, claim: str, *, anchor: str = "out", dpo: str = "", lb: bool = True,
          is_claim: bool = True, verdict: str = "支持", ev: str = "EV-01",
          self_cont: bool = False, basis: str = "evidence") -> Dict[str, Any]:
    return {
        "i": idx, "claim": claim, "is_claim": is_claim, "verdict": verdict,
        "evidence_ref": ev, "evidence_class": "推论", "load_bearing": lb,
        "decision_changed": dpo or ("它决定了 " + claim),
        "supports_conclusions": [] if anchor == "out" else [1],
        "maps_to_question": True, "anchor": anchor, "decision_point_out": dpo,
        "basis": basis, "self_contained": self_cont, "parse_ok": True,
    }


#: 夹具里的岔口归属（**已知**）⇒ 直接构造，不走判官。
#:   K1={1,2}（同族：①是代表，②是变体）｜K2={3,4}（两个都被拒）｜K3={6}
#:   K4={7}（矛盾）｜K5={8,9}（同族：⑧代表，⑨变体）｜K6={10}（独立复核否）
#:   K7={5}（锚内卡）｜K8={11,12}（⑪锚外、⑫锚内 ⇒ 族级锚外判定应当拒掉⑪）
FORK_MEMBERS: Dict[str, List[int]] = {
    "K1": [1, 2], "K2": [3, 4], "K3": [6], "K4": [7],
    "K5": [8, 9], "K6": [10], "K7": [5], "K8": [11, 12], "K9": [13],
}

#: 独立复核探针①（是否具体 / 是否出界）的答案（**已知**）：⑩ 被否掉。
PROBE: Dict[int, bool] = {1: True, 2: True, 3: True, 4: True, 5: False, 6: True,
                          7: True, 8: True, 9: True, 10: False, 11: True, 12: False,
                          13: True}
#: 独立复核探针②（是"做决定"还是"给建议/泛论"）的答案（**已知**）：⑬ 被否掉
#: （⑬ 过探针①、不过探针② ⇒ 专门测**双探针 AND** 是否真的在起作用）。
PROBE2: Dict[int, bool] = {1: True, 2: True, 3: True, 4: True, 5: False, 6: True,
                           7: True, 8: True, 9: True, 10: True, 11: True, 12: False,
                           13: False}


#: (卡片, 期望是否通过 AO-GATE, 期望的拒绝原因)
FIXTURE: List[Tuple[Dict[str, Any], bool, str]] = [
    # ① 正例：锚外、岔口可指名、无兄弟卡、引了真实 EV ⇒ 放行（K1 的代表）
    (_card(1, "在多租户场景下应当按租户隔离限流，而不是全局限流", dpo="限流粒度选租户级还是全局级"), True, ""),
    # ② 同岔口的第二张卡 ⇒ 归族（A5），**不计独立维度**（K1 仍只算 1 个维度）
    (_card(2, "多租户限流应当以租户为维度隔离配额", dpo="限流粒度选租户级还是全局级"), False, "A5_merged_variant"),
    # ③ 岔口没写具体 ⇒ A4
    (_card(3, "还要注意一些别的方面", dpo=""), False, "A4_fork_not_named"),
    # ④ 岔口描述里其实指向了 C_t 里的编号 ⇒ A3（机械复核）
    (_card(4, "本题应当落在 C2 上", dpo="对应结论 C2 的判定口径要不要改"), False, "A3_still_in_anchor"),
    # ⑤ 判官说它是锚内 ⇒ A3
    (_card(5, "题干里的 ① 成立", anchor="in", dpo=""), False, "A3_still_in_anchor"),
    # ⑥ 既没引依据也不自含推理链 ⇒ A6
    (_card(6, "建议再补充一些部署细节", dpo="部署细节要不要补充到运维手册里", ev=None, self_cont=False), False, "A6_not_cited"),
    # ⑦ 矛盾卡 ⇒ A7
    (_card(7, "限流粒度应当按全局计", dpo="限流粒度选全局还是租户", verdict="矛盾"), False, "A7_contradicted"),
    # ⑧ 正例：模型自生知识 + 自带推理链 ⇒ 放行，但 LOO 只到卡片级（K5 的代表）
    (_card(8, "应当把限流阈值下沉到租户画像层，因为租户流量分布差异可达数十倍",
           dpo="限流阈值下沉到租户画像层还是全局静态值", ev=None, self_cont=True, basis="model"), True, ""),
    # ⑨ ⑧ 的同族变体 ⇒ 归族
    (_card(9, "限流阈值应当按租户画像动态调整，而非全局静态值",
           dpo="限流阈值下沉到租户画像层还是全局静态值", ev=None, self_cont=True, basis="model"), False, "A5_merged_variant"),
    # ⑩ 其它条件都过，但**独立复核**否掉 ⇒ A4（探针是独立的一次调用，不是橡皮章）
    (_card(10, "灰度发布应当先放 5% 流量观察再全量", dpo="灰度比例先 5% 还是直接全量"), False, "A4_fork_not_named"),
    # ⑪ 锚外卡，但它所在的岔口里还有一张**锚内**卡 ⇒ 那个决策其实已被 C_t 覆盖 ⇒ A3′
    (_card(11, "回滚策略应当按依赖图逆序执行", dpo="回滚要不要按依赖图逆序"), False, "A3_fork_covered_by_anchor"),
    # ⑫ 与 ⑪ 同岔口的锚内卡 ⇒ A3（自身在锚内）
    (_card(12, "本题的 C1 结论成立", anchor="in", dpo=""), False, "A3_still_in_anchor"),
    # ⑬ 过探针①（具体、出界）但**不过探针②**（是建议/泛论，不是做决定）⇒ A4′
    (_card(13, "建议在实施前充分沟通各方需求后再推进", dpo="要不要先沟通再推进"), False, "A4_fork_not_named"),
]


def _forks_for(cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """夹具里的岔口是**已知**的 ⇒ 直接构造（不走判官）。"""
    forks = [{"fork": fid, "cards": list(members), "label": "夹具岔口 " + fid}
             for fid, members in FORK_MEMBERS.items()]
    covered = {m for f in forks for m in f["cards"]}
    cand_n = sum(1 for c in cards if c.get("is_claim") and c.get("load_bearing")
                 and c.get("decision_changed"))
    return {"forks": forks, "fork_assign_failed": bool(forks) and covered != set(range(1, cand_n + 1)),
            "n_candidates": cand_n}


def tier_a() -> Dict[str, Any]:
    """机械层：AO-GATE 判定逻辑 + 变异注入。**不需要 API。**"""
    cards = [c for c, _, _ in FIXTURE]
    forks = _forks_for(cards)
    probe = dict(PROBE)
    probe2 = dict(PROBE2)
    gate = V.anchor_out_gate(cards, forks, ["C1", "C2", "C3"], ["EV-01", "EV-02"],
                              fork_probe=probe, fork_probe2=probe2)
    kept_claims = {k["representative_claim"] for k in gate["kept"]}
    rejected = {r["claim"]: r["gate"] for r in gate["rejected"]}

    failures: List[str] = []
    for card, should_pass, why in FIXTURE:
        claim = card["claim"]
        if should_pass:
            if claim not in kept_claims:
                failures.append("正例被误拒：%s（期望 %s）" % (claim[:24], why or "放行"))
        else:
            if claim in kept_claims:
                failures.append("负例被误放：%s（期望拒绝 %s）" % (claim[:24], why))
            elif rejected.get(claim) != why:
                failures.append("拒绝原因不符：%s ⇒ 实际 %s，期望 %s"
                                % (claim[:24], rejected.get(claim), why))

    # ── ★ 回归测试（2026-10-23）：判官把 "i" 写成字符串 ⇒ 原先 `int()` 抛
    #    ValueError ⇒ **整份答案的测量全灭**（实测 2/27 作业这样死掉）⇒
    #    ⇒ 必须**按行序兜底**且**标记**，不许崩、不许静默。
    _raw_bad_i = ('{"i": "3", "load_bearing": true, "is_claim": true}\n'
                  '{"i": null, "load_bearing": false, "is_claim": true}\n'
                  '{"i": 1, "load_bearing": true, "is_claim": true}')
    try:
        _got = V.parse_card_lines(_raw_bad_i, 3)
    except Exception as _e:                     # noqa: BLE001
        failures.append("★ parse_card_lines 遇到非数字 i 就崩（%s）⇒ 整份测量会全灭"
                        % type(_e).__name__)
        _got = []
    if len(_got) != 3:
        failures.append("★ parse_card_lines 对非数字 i 丢卡：解析 %d/3" % len(_got))
    else:
        if _got[0].get("i") != 3:
            failures.append("★ 字符串 i 未被正确转成整数：%r" % _got[0].get("i"))
        if not _got[1].get("i_fallback"):
            failures.append("★ 非数字 i 兜底后未被标记（i_fallback 缺失）⇒ 静默了")
    # 变异注入：把兜底改回会崩的写法 ⇒ 上面两条断言必须变红
    _mutations_probe_i = {
        "name": "parse_card_lines 去掉索引容错",
        "expect_fail": "parse_card_lines 遇到非数字 i 就崩",
    }

    # ── 族语义：VD_anchor_out 数的是**族**，不是卡 ──────────────────
    if gate["n_anchor_out"] != 2:
        failures.append("★ 族计数错：VD_anchor_out = %s，期望 2（K1、K5 各一族）"
                        % gate["n_anchor_out"])
    if gate.get("n_merged_variants") != 2:
        failures.append("★ 归族计数错：n_merged_variants = %s，期望 2"
                        % gate.get("n_merged_variants"))

    # ── 变异注入：拆掉某一条 ⇒ 对应断言必须变红 ──────────────────
    mutations: List[Dict[str, Any]] = []

    def mutate(name: str, fn) -> None:
        mcards = [dict(c) for c in cards]
        mforks = json.loads(json.dumps(forks))
        mprobe = dict(probe)
        mprobe2 = dict(probe2)
        fn(mcards, mforks, mprobe, mprobe2)
        mgate = V.anchor_out_gate(mcards, mforks, ["C1", "C2", "C3"], ["EV-01", "EV-02"],
                                  fork_probe=mprobe, fork_probe2=mprobe2)
        mkept = {k["representative_claim"] for k in mgate["kept"]}
        mrej = {r["claim"]: r["gate"] for r in mgate["rejected"]}
        target = _MUT_EXPECT[name]
        base_kept = target in kept_claims
        mut_kept = target in mkept
        base_reason = rejected.get(target)
        mut_reason = mrej.get(target)
        flipped = (base_kept != mut_kept) or (base_reason != mut_reason)
        mutations.append({"mutation": name, "target": target[:28],
                          "base": ("kept" if base_kept else base_reason),
                          "mutated": ("kept" if mut_kept else mut_reason),
                          "flipped": flipped,
                          "note": "若 flipped=False ⇒ 该条件根本没被测到 ⇒ 自检无效"})
        if not flipped:
            failures.append("★ 变异注入失效：%s —— 拆掉该条件后判定完全没变 ⇒ 这条判定没被测到" % name)

    mutate("A3_机械复核",
           lambda c, f, p, p2: c[3].__setitem__("decision_point_out", "某个不含结论编号的具体岔口"))
    mutate("A4_空岔口",
           lambda c, f, p, p2: c[2].__setitem__("decision_point_out", "限流策略要不要分租户配置"))
    mutate("A5_归族",
           lambda c, f, p, p2: (f["forks"][0].__setitem__("cards", [1]),
                                f["forks"].append({"fork": "K9b", "cards": [2], "label": "独立岔口"})))
    mutate("A6_影响矩阵被引用",
           lambda c, f, p, p2: c[5].__setitem__("evidence_ref", "EV-02"))
    mutate("A7_矛盾卡",
           lambda c, f, p, p2: c[6].__setitem__("verdict", "支持"))
    mutate("A4_独立复核",
           lambda c, f, p, p2: p.__setitem__(10, True))
    mutate("A3_族级锚外",
           lambda c, f, p, p2: f["forks"][-1].__setitem__("cards", [11]))
    mutate("A4_第二探针",
           lambda c, f, p, p2: p2.__setitem__(13, True))   # 把探针②的"否"改成"是" ⇒ ⑬ 应被放行

    # ── 失败不许静默变 0 ────────────────────────────────────────
    class _FakeLLM:
        """假客户端：返回空串 ⇒ 用来验证"失败必须被记账"而不是静默变 0。"""
        def __init__(self):
            self.log = V.CallLog()
        def chat(self, *a, **k):
            self.log.add(finish_reason="stop", content_len=0)
            return ""
    r = V.measure_one(_FakeLLM(), {"task_id": "D00", "ask": "x", "evidence": "y。",
                                    "conclusion_space": [{"id": "C1", "text": "t"}]},
                      "", "empty-case", "MiniMax-M3.1-Flash-Preview", do_fork_probe=False)
    if r.get("valid") != 0 or r.get("silent_empty_count") != 1:
        failures.append("★ 失败静默：空答案没有报 valid=0 / silent_empty_count=1")

    # ── 提示词模板自检（2026-10-22 实测踩过：JSON 花括号没转义 ⇒ .format() 崩
    #    ⇒ 整批任务全灭、而日志是空的）────────────────────────────────
    templates = {
        "CARD_Q_IN": (V.CARD_Q_IN, {"ask": "A", "ev": "E", "claims": "C"}),
        "CARD_Q_OUT": (V.CARD_Q_OUT, {"ask": "A", "ev": "E", "claims": "C"}),
        "FORK_Q": (V.FORK_Q, {"claims": "C"}),
        "EXTRACT_Q": (V.EXTRACT_Q, {"t": "T"}),
    }
    tmpl_report = {}
    for name, (tpl, kwargs) in templates.items():
        try:
            out = tpl.format(**kwargs)
            ok = bool(out.strip())
            tmpl_report[name] = {"ok": ok, "n_chars": len(out)}
            if not ok:
                failures.append("★ 提示词模板 %s 格式化后为空" % name)
        except Exception as e:                        # noqa: BLE001
            tmpl_report[name] = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
            failures.append("★ 提示词模板 %s 格式化崩溃：%s ⇒ 这一批会全灭"
                             % (name, type(e).__name__))

    return {"tier": "A", "n_fixtures": len(FIXTURE), "n_mutations": len(mutations),
            "mutations": mutations, "prompt_templates": tmpl_report,
            "failures": failures, "passed": not failures}


_MUT_EXPECT = {
    "A3_机械复核": FIXTURE[3][0]["claim"],
    "A4_空岔口": FIXTURE[2][0]["claim"],
    "A5_归族": FIXTURE[1][0]["claim"],
    "A6_影响矩阵被引用": FIXTURE[5][0]["claim"],
    "A7_矛盾卡": FIXTURE[6][0]["claim"],
    "A4_独立复核": FIXTURE[9][0]["claim"],
    "A3_族级锚外": FIXTURE[10][0]["claim"],
    "A4_第二探针": FIXTURE[12][0]["claim"],
}


# ──────────────────────────────────────────────────────────────
# B 层：判官层（需要 API）
# ──────────────────────────────────────────────────────────────
def tier_b(judge_vendor: str, judge_model: str, dev_dir: str,
           effort: Optional[str] = None) -> Dict[str, Any]:
    """① 岔口归并 vs DEV 金标的一致性；② 判官自检（真锚外卡 / 假锚外卡）。"""
    failures: List[str] = []
    out: Dict[str, Any] = {"tier": "B", "judge_vendor": judge_vendor, "judge_model": judge_model}
    try:
        llm = V.LLM(judge_vendor, judge_model)
    except Exception as e:                        # noqa: BLE001
        return {"tier": "B", "skipped": True, "reason": "无法建立客户端：%s" % e,
                "passed": False, "failures": ["判官层未跑 ⇒ 不得出数"]}

    # ① 岔口归并 vs 金标（DEV 金标卡的 supports_conclusions 就是"同一个岔口"的标签）
    devset = V.load_devset(dev_dir)
    purity_num = purity_den = sep_num = sep_den = 0
    n_task = 0
    for t in devset.get("tasks", []):
        gold_path = os.path.join(dev_dir, "gold", "%s_cards.json" % t["task_id"])
        if not os.path.exists(gold_path):
            continue
        gold = json.load(open(gold_path, encoding="utf-8"))
        gcards = gold.get("cards", [])
        cands = [c for c in gcards if c.get("is_load_bearing")]
        if not cands:
            continue
        n_task += 1
        probe_cards = [{
            "i": i + 1, "claim": c["claim"], "is_claim": True, "verdict": "支持",
            "evidence_ref": c.get("evidence_ref"), "evidence_class": c.get("evidence_class", "事实"),
            "load_bearing": True, "decision_changed": c.get("decision_changed", ""),
            "supports_conclusions": c.get("supports_conclusions", []),
            "anchor": "in", "decision_point_out": "", "basis": "evidence",
            "self_contained": False, "parse_ok": True,
        } for i, c in enumerate(cands)]
        fk = V.assign_forks(llm, probe_cards, judge_model)
        if fk.get("fork_assign_failed"):
            failures.append("岔口归并在 %s 上失败（漏卡 %s）" % (t["task_id"], fk.get("fork_cover_missing")))
            continue
        lab = {i + 1: (cands[i].get("supports_conclusions") or ["?"])[0] for i in range(len(cands))}
        fk_of = {}
        for f in fk["forks"]:
            for m in f["cards"]:
                fk_of[m] = f["fork"]
        idxs = sorted(lab)
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                ia, ib = idxs[a], idxs[b]
                same_lab = lab[ia] == lab[ib]
                same_fk = fk_of.get(ia) == fk_of.get(ib)
                if same_lab:
                    purity_den += 1
                    purity_num += 1 if same_fk else 0
                else:
                    sep_den += 1
                    sep_num += 1 if not same_fk else 0
    out["fork_assignment"] = {
        "n_tasks": n_task,
        "purity": (purity_num / purity_den) if purity_den else None,
        "purity_num": purity_num, "purity_den": purity_den,
        "separation": (sep_num / sep_den) if sep_den else None,
        "sep_num": sep_num, "sep_den": sep_den,
    }
    if purity_den and (purity_num / purity_den) < 0.75:
        failures.append("岔口归并纯度 %.2f < 0.75 ⇒ 锚外的 leave-one-out 绑定不可信"
                        % (purity_num / purity_den))
    if sep_den and (sep_num / sep_den) < 0.75:
        failures.append("岔口归并分离度 %.2f < 0.75 ⇒ 把不同岔口混在一起了"
                        % (sep_num / sep_den))

    # ② 判官自检：真锚外卡 vs 假锚外卡（协议 §4.6 的形状：真 ≥ 3/4 且 假 ≥ 3/4）
    # ★★ 2026-10-23 **修正自检集**（重要）：
    #   原前两张"真锚外卡"分别是「应当按租户隔离限流」与「应当先灰度 5% 流量再全量」
    #   ⇒ 而自检用的 `C_t` 正是「C1. 限流按租户维度隔离 / C2. 发布先灰度再全量」
    #   ⇒ ★ **这两张卡就是 C1/C2 本身** ⇒ 判官判它们"在锚内"是**对的**
    #   ⇒ ⇒ 于是"真卡 2/4"反映的是**自检集错了**，不是判官不行
    #   ⇒ ⇒ 而昨天报出的"真卡 3/4 ⇒ 过 F7"里**有一张是误判通过** ⇒ 那是**运气**。
    #   ⇒ ★ 换掉这两张（保留后两张：SLO 错误预算分级、限流阈值按租户画像动态调整 —— 二者确实在 C1/C2 之外）。
    true_cards = [
        "限流触发时应当按响应体里的 retry_after_seconds 让客户端按秒退避，"
        "而不是在网关侧统一改写成固定 1 秒",
        "发布前应当先跑一次影子流量并比对错误率与延迟差异，确认无回归后再切灰度流量",
        "监控告警应当按 SLO 错误预算烧尽率分级，而不是按单次错误数",
        "限流阈值应当按租户画像动态调整，而不是全局静态值",
    ]
    # ── ★ 自检集自身的机械检查（2026-10-23）
    #   「真锚外卡」**不得复述 C_t** ⇒ 否则判官判它"在锚内"是**对的**，
    #   ⇒ 自检集会**测判官有没有犯本该由标注犯的错** ⇒ 昨天的"真 3/4 过 F7"是**运气**。
    #
    #   ⚠️ 第一版用**最长公共子串** ⇒ **抓不到**（坏卡是*改写*不是复制，公共子串只有 3 字）
    #      ⇒ 那是装饰性的检查（自己会假阴性）⇒ 换成**核心词重合数**。
    #   ⇒ 核心词由人写（可控、可审计）：与任一 C_t 重合 ≥3 ⇒ 判自检集无效。
    _CT_KEYWORDS = {
        "C1 限流按租户维度隔离": ["限流", "租户", "隔离", "维度"],
        "C2 发布先灰度再全量": ["发布", "灰度", "全量"],
    }

    def _ct_overlap(card: str) -> int:
        return max(sum(1 for kw in kws if kw in card) for kws in _CT_KEYWORDS.values())

    for _c in true_cards:
        if _ct_overlap(_c) >= 3:
            failures.append("★ **自检集无效**：真锚外卡复述了 C_t（核心词重合 %d）⇒ %s"
                            % (_ct_overlap(_c), _c[:34]))
    if _ct_overlap(true_cards[3]) >= 3:
        failures.append("★ 自检集**过度修正**：连'限流阈值按租户画像动态调整'这张公认的真锚外卡"
                        "都被判成复述 C_t ⇒ 核心词表过宽")

    false_cards = [
        "综上所述，限流策略的选择需要综合考虑业务实际情况。",
        "这是一个非常有意思的问题，值得我们进一步探讨。",
        "建议在实施前充分沟通，确认各方需求后再推进。",
        "实施过程中要注意做好沟通与协调。",
        "限流阈值应当根据实际情况灵活调整。",
        "需要进一步评估限流方案对业务的影响。",
    ]
    probe = V.FORK_PROBE_Q
    probe2 = V.FORK_PROBE2_Q
    # 两个探针模板需要 `ask` 与 `ct`（与实现同口径 ⇒ 不漂移）
    sc_ask = "如何为一个多租户 SaaS 平台设计限流与发布策略？"
    sc_ct = "C1. 限流按租户维度隔离\nC2. 发布先灰度再全量"
    # ★ 并行：自检有 (真4+假6) × 2 探针 × 2 轮 = 40 次判官调用
    #   （MiniMax 单次 ~100–195s ⇒ 串行要 1 小时以上）⇒ 并发 4（>4 会触发 429）。
    import concurrent.futures as cf

    sc_ask = "如何为一个多租户 SaaS 平台设计限流与发布策略？"
    sc_ct = "C1. 限流按租户维度隔离\nC2. 发布先灰度再全量"
    DPO = "清单外的一个具体决策：该不该这样做、做到什么程度"

    def _probe(card: str, tmpl) -> bool:
        r = llm.chat(tmpl.format(ask=sc_ask, ct=sc_ct, claim=card, dpo=DPO),
                     model=judge_model, temp=0.0, max_tokens=V.MM_TOKEN_FLOOR,
                     budgets=V.JUDGE_BUDGETS, min_ok=10, purpose="selfcheck")
        return _probe_positive(r)

    jobs = []
    for c in true_cards:
        jobs.append((c, "true"))
    for c in false_cards:
        jobs.append((c, "false"))
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {}
        for c, kind in jobs:
            for tmpl in (probe, probe2):
                futs[(c, kind, id(tmpl))] = ex.submit(_probe, c, tmpl)
        passed = {}
        for (c, kind, _tid), fut in futs.items():
            ok = fut.result()
            passed.setdefault((c, kind), True)
            if not ok:
                passed[(c, kind)] = False
    t_ok = sum(1 for c in true_cards if passed.get((c, "true"), False))
    f_rej = sum(1 for c in false_cards if not passed.get((c, "false"), True))
    _calls = llm.log.summary()
    _ncall = max(_calls.get("n_calls", 0), 1)
    _bad = _calls.get("n_empty_content", 0) + _calls.get("n_truncated", 0)
    _health = round(1.0 - _bad / float(_ncall), 4)
    out["judge_selfcheck"] = {
        # ★ 通道健康度（2026-10-23）：**自检必须在健康通道上跑**
        #   ⇒ 通道坏时自检数字反映的是**通道**，不是判官
        "effort": effort or "(default=max)",
        "channel_health": _health,
        "calls": _calls,"true_pass": t_ok, "true_total": len(true_cards),
                              "false_rejected": f_rej, "false_total": len(false_cards),
                              "false_wrongly_accepted": len(false_cards) - f_rej}
    if t_ok < 3:
        failures.append("判官自检：真锚外卡 %d/%d < 3/4（★ 通道健康度 %s，effort %s ⇒ "
                        "先看通道再看判官）"
                        % (t_ok, len(true_cards), _health, effort or "(default=max)"))
    if f_rej < 3:
        failures.append("判官自检：假锚外卡只被拒 %d/%d < 3/4（放行太多 ⇒ 锚外闸门被钻空子）"
                        % (f_rej, len(false_cards)))
    out["failures"] = failures
    out["passed"] = not failures
    return out


def _probe_positive(raw: str) -> bool:
    """探针①②的**肯定**条件任一满足即算通过（两类探针的字段不同）。"""
    for ln in (raw or "").splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            d = json.loads(ln)
        except Exception:                            # noqa: BLE001
            continue
        if not isinstance(d, dict):
            continue
        if d.get("specific") is True and d.get("outside") is True:
            return True
        if d.get("is_decision") is True and d.get("is_checkable") is True:
            return True
    return False


# ──────────────────────────────────────────────────────────────
def run_selftest(args: Any) -> int:
    a = tier_a()
    print("── Tier A（机械层）────────────────────────────")
    print(json.dumps(a, ensure_ascii=False, indent=2))
    out_dir = getattr(args, "out", os.path.join(HERE, "selftest_out"))
    os.makedirs(out_dir, exist_ok=True)
    report: Dict[str, Any] = {"tier_a": a}

    if not getattr(args, "no_api", False):
        b = tier_b(getattr(args, "judge_vendor", "minimax"),
                   getattr(args, "judge_model", "MiniMax-M3.1-Flash-Preview"),
                   getattr(args, "dev", V.DEV_DIR),
                   effort=getattr(args, "effort", None))
        print("── Tier B（判官层）────────────────────────────")
        print(json.dumps(b, ensure_ascii=False, indent=2))
        report["tier_b"] = b
    else:
        report["tier_b"] = {"skipped": True, "reason": "--no-api"}

    tb = report.get("tier_b", {})
    passed = bool(a.get("passed")) and bool(tb.get("passed", False))
    report["overall_passed"] = passed
    if tb.get("skipped"):
        print("\n※ Tier B 未跑（--no-api）⇒ 按协议 F7，**不得出数**；上面的 Tier A 只证明机械闸门本身可用。")
    with open(os.path.join(out_dir, "selftest.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n=== 自检总判：%s ===" % ("通过" if passed else "不通过 ⇒ 按协议 F7 拒绝出数"))
    return 0 if passed else 1


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default=V.DEV_DIR)
    ap.add_argument("--judge-vendor", default="minimax")
    ap.add_argument("--judge-model", default="MiniMax-M3.1-Flash-Preview")
    ap.add_argument("--out", default=os.path.join(HERE, "selftest_out"))
    ap.add_argument("--no-api", action="store_true")
    ap.add_argument("--effort", default=None,
                    help="MiniMax 思考深度档（★ 自检必须在**健康通道**上跑 ⇒ 建议 medium；"
                         "不传 = max = 批≥4 时可能 100%% 截断）")
    ns = ap.parse_args()
    sys.exit(run_selftest(ns))
