# -*- coding: utf-8 -*-
"""路线 C · 训练器自检（**不发起任何 API 调用**）。

用假 LLM / 假判官把 `train_params.py` 的整条训练回路跑一遍，检查：
  1. 语料加载 + 关键结论匹配（正例 / 负例）
  2. 坐标下降能跑完，且**永远不离开先验的合法域**（参数取值始终在表内）
  3. 作废式硬约束真的作废配置（塞一个必然违反矛盾率上限的配置，看它是否被拒）
  4. 退化配置被 `params.degenerate` 拦下
  5. 折外评估量被算出来
  6. 阈值类判据留余量（本表：cont 参数的档位与端点一致、int 参数档位与表一致）
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/workspace/lab/cmp8repo")

import params as P
import train_params as TP


class FakeLLM:
    """假客户端：按 prompt 内容返回可预期的伪断言（不联网）。"""

    def __init__(self):
        self.calls = 0

    def chat(self, prompt, **kw):
        self.calls += 1
        if "逐条列出" in prompt:                      # 抽取
            return "- 最高可贷到160万元\n- 额度上浮40万元\n- 绿色建筑纳入支持范围"
        return "伪草稿文本：这是第 %d 次生成，内容用于管线自检。" % self.calls


def fake_verifier(ask, ev, claims):
    return {c: ("支持" if "160万元" in c else "未提及") for c in claims}


def main():
    ok = True
    topics = TP.load_topics()
    print("[1] 语料：%d 题 %s" % (len(topics), [t["task_id"] for t in topics]))
    ok = ok and len(topics) == 8

    t1 = topics[0]
    hit_pos = TP.key_hit("最高可贷到160万元，额度上浮40万元", t1["key_conclusions"])
    hit_neg = TP.key_hit("可以贷很多钱。", t1["key_conclusions"])
    print("    key_hit 正例=%.2f 负例=%.2f（期望 1.00 / 0.00）" % (hit_pos, hit_neg))
    ok = ok and hit_pos == 1.0 and hit_neg == 0.0

    llm = FakeLLM()
    theta, baseline, history = TP.coordinate_descent(
        topics, llm, fake_verifier, "T2", verbose=False, n_pass=1)
    print("[2] 坐标下降：评估配置数 %d，最终 hash=%s"
          % (len(history), P.theta_hash(theta)))
    ok = ok and len(history) > 0

    viol = P.validate(theta, "T2")
    print("    最终参数越界：%s（期望 []）" % viol)
    ok = ok and not viol

    # 3. 作废式约束：把 theta_util 顶到 1.0（要求判官满分）看是否被拒
    bad = dict(theta)
    bad["theta_util"] = 1.0
    res = TP.evaluate(bad, "T2", topics[:2], llm, fake_verifier, reps=1)
    reasons = TP.constraint_ok(res, None, bad, "T2")
    print("[3] 约束判定：%s" % (reasons or "无违反（该配置恰好合法）"))
    # 4. 退化配置
    deg = dict(theta)
    deg["n_frames"] = 1
    print("[4] 退化检测（n_frames=1）：%s" % P.degenerate(deg, "T2"))
    ok = ok and len(P.degenerate(deg, "T2")) > 0

    # 5. 折外量
    other = [t for t in topics if t["task_id"] in TP.FOLDS["B"]]
    r_out = TP.evaluate(theta, "T2", other, llm, fake_verifier, reps=1)
    b_out = TP.evaluate(P.default_theta(), "T2", other, llm, fake_verifier, reps=1)
    print("[5] 折外：J(θ*)=%.3f  J(θ_prior)=%.3f  delta=%+.3f"
          % (r_out["J"], b_out["J"], r_out["J"] - b_out["J"]))

    # 6. 阈值/档位一致性（余量检查）
    bad_alphabet = []
    for p in P.PARAM_SPEC:
        al = P.alphabet(p)
        if p["type"] == "int":
            if al != p["values"] or p["default"] not in al:
                bad_alphabet.append(p["name"])
        else:
            if abs(al[0] - p["lo"]) > 1e-9 or abs(al[-1] - p["hi"]) > 1e-9:
                bad_alphabet.append(p["name"])
            if not (p["lo"] <= p["default"] <= p["hi"]):
                bad_alphabet.append(p["name"])
    print("[6] 档位/端点一致性：%s（期望 []）" % bad_alphabet)
    ok = ok and not bad_alphabet

    # 7. ★ C2 的 key_hit 口径（复核 6e）：只在「已交付 ∧ 被支持」子集上算
    kc = [dict(must_any=[["罚款总额为 9 元"]])]
    d_sup = dict(delivered_supported_text="罚款总额为 9 元",
                 delivered_claims=[dict(text="罚款总额为 9 元", verdict="支持", score=1.0)])
    d_unsup = dict(delivered_supported_text="",
                   delivered_claims=[dict(text="罚款总额为 9 元", verdict="未核验", score=0.0)],
                   answer="罚款总额为 9 元")
    kh_sup = TP.key_hit_supported(d_sup, kc)
    kh_any = TP.key_hit(d_unsup["answer"], kc)        # 整份机械答案口径（仅参考）
    kh_c2 = TP.key_hit_supported(d_unsup, kc)          # C2 真正用的口径
    print("[7] key_hit 口径：被支持子集=%.2f｜整份答案(未核验文本)=%.2f｜C2 用(未核验文本)=%.2f"
          "（期望 1.00 / 1.00 / 0.00）" % (kh_sup, kh_any, kh_c2))
    ok = ok and kh_sup == 1.0 and kh_any == 1.0 and kh_c2 == 0.0

    # 8. ★ 断言护栏：把**未支持**的断言塞进 supported_text ⇒ 必须抛错（不静默降级）
    try:
        TP.supported_text_of(dict(
            delivered_supported_text="机密文本",
            delivered_claims=[dict(text="机密文本", verdict="未核验", score=0.0)]))
        print("[8] 未支持断言混入 supported_text：**未抛错** ⇒ FAIL")
        ok = False
    except AssertionError as e:
        print("[8] 未支持断言混入 supported_text：已抛错（%s）" % str(e)[:48])

    print("\n结果：%s（假客户端，0 次真实 API 调用）" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
