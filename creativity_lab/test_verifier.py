# -*- coding: utf-8 -*-
"""核验器判别力测试（判死测试）。

构造一批**我已确定 ground truth** 的断言，分三类：
  支持   —— 依据原文明确写了
  矛盾   —— 依据原文明确写了相反的
  未提及 —— 真实但依据没讲

若核验器在「矛盾」这一类上召回为 0，整个三分类塌成两分类，
「矛盾 0 条」就不是模型没错，而是仪器坏了 → 整套指标作废。

只重跑核验，不生成任何答案。
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creativity_lab.client import LLM      # noqa: E402

OUT = "runs/train"
TOPICS = {t["tid"]: t for t in json.load(
    open("creativity_lab/data/legal_topics.json", encoding="utf-8"))["topics"]}

# 每条 = (题号, 断言, 真值)  真值由我依据依据原文确定，不由模型判断
CASES = [
    # ---- L1 存款保险（依据：50万限额 / 同一家本息合并 / 超出从清算财产受偿）----
    ("L1", "存款保险实行限额偿付，最高偿付限额为人民币50万元。", "支持"),
    ("L1", "同一存款人在同一家投保机构的本息合并计算在最高偿付限额以内实行全额偿付。", "支持"),
    ("L1", "存款保险的最高偿付限额是人民币500万元。", "矛盾"),
    ("L1", "超出最高偿付限额的部分也可以获得全额偿付。", "矛盾"),
    ("L1", "12315是全国消费者投诉举报热线电话。", "未提及"),
    ("L1", "中国人民银行是中华人民共和国的中央银行。", "未提及"),

    # ---- L2 劳动合同（依据：1月/2月/6月上限、只能约定一次、工资80%与最低工资）----
    ("L2", "劳动合同期限一年以上不满三年的，试用期不得超过二个月。", "支持"),
    ("L2", "同一用人单位与同一劳动者只能约定一次试用期。", "支持"),
    ("L2", "劳动合同期限一年以上不满三年的，试用期不得超过六个月。", "矛盾"),
    ("L2", "用人单位在试用期解除劳动合同的，不需要向劳动者说明理由。", "矛盾"),
    ("L2", "劳动者提前三日通知用人单位可以解除劳动合同。", "未提及"),
    ("L2", "劳动合同应当采用书面形式订立。", "未提及"),

    # ---- L3 消法（依据：七日无理由、四类除外、运费消费者承担、第二十四条三包）----
    ("L3", "退回商品的运费由消费者承担。", "支持"),
    ("L3", "消费者有权自收到商品之日起七日内退货，且无需说明理由。", "支持"),
    ("L3", "消费者有权自收到商品之日起十五日内退货，且无需说明理由。", "矛盾"),
    ("L3", "定制商品不适用七日无理由退货。", "支持"),
    ("L3", "经营者提供的商品不符合质量要求的应当承担修理、更换等义务。", "未提及"),

    # ---- L4 食安法（依据：价款十倍或损失三倍、首负责任制、不足一千按一千）----
    ("L4", "增加赔偿的金额不足一千元的，为一千元。", "支持"),
    ("L4", "消费者还可以要求生产者或者经营者支付价款十倍或者损失三倍的赔偿金。", "支持"),
    ("L4", "增加赔偿的金额不足一千元的，按实际损失数额计算。", "矛盾"),
    ("L4", "消费者只能要求生产者赔偿，不得向经营者要求赔偿。", "矛盾"),
    ("L4", "食品生产经营人员每年应当进行一次健康检查。", "未提及"),

    # ---- L5 个保法（依据：不得因不同意拒绝服务、同意的七种情形、撤回同意、最小必要）----
    ("L5", "个人信息处理者不得以个人不同意处理其个人信息为由，拒绝提供产品或者服务。", "支持"),
    ("L5", "个人有权撤回其同意。", "支持"),
    ("L5", "个人信息处理者可以因个人撤回同意而拒绝提供产品或者服务。", "矛盾"),
    ("L5", "收集个人信息不受处理目的最小范围的限制。", "矛盾"),
    ("L5", "自然人因个人或者家庭事务处理个人信息的，不适用个人信息保护法。", "未提及"),
]

CHECK3 = """下面是一份「依据原文」，之后列出若干条**待核验的具体做法**。

逐条判断这条与依据原文的关系，只回答一个词：
- 「支持」：依据原文明确认可或蕴含该条。
- 「矛盾」：依据原文明确讲了与之相反的内容。
- 「未提及」：依据原文没有讲到，或讲的是别的事。**不确定时一律答「未提及」。**

一条一行，顺序对应，不要解释，不要补充。

依据原文：
{ev}

待核验的具体做法：
{claims}"""


def run(llm, tid, batch):
    T = TOPICS[tid]
    lst = "\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(batch))
    t = llm.chat(CHECK3.format(ev=T["evidence"], claims=lst), model="MiniMax-M3",
                 purpose="verif_test", max_tokens=1200, budgets=(1800, 2400),
                 min_ok=len(batch) * 2) or ""
    out = []
    for ln in [x for x in t.splitlines() if x.strip()]:
        m = re.search(r"支持|矛盾|未提及", ln)
        out.append(m.group() if m else "解析失败")
    while len(out) < len(batch):
        out.append("解析失败")
    return out[:len(batch)]


def main():
    llm = LLM()
    by = {}
    for tid, c, g in CASES:
        by.setdefault(tid, []).append((c, g))

    rows = []
    for tid, items in by.items():
        got = run(llm, tid, [c for c, _ in items])
        for (c, g), p in zip(items, got):
            rows.append(dict(tid=tid, claim=c, gold=g, pred=p, ok=(g == p)))

    print("=" * 96)
    print("%-6s %-8s %-8s %s" % ("题", "真值", "预测", "断言"))
    for r in rows:
        mark = "✓" if r["ok"] else "✗"
        print("%-6s %-8s %-8s %s %s" % (r["tid"], r["gold"], r["pred"], mark, r["claim"][:48]))

    print("\n" + "=" * 96)
    print("混淆矩阵（行=真值，列=预测）")
    cats = ["支持", "矛盾", "未提及", "解析失败"]
    print("%-10s" % "" + "".join("%-10s" % c for c in cats))
    for g in cats[:3]:
        line = "%-10s" % g
        for p in cats:
            n = sum(1 for r in rows if r["gold"] == g and r["pred"] == p)
            line += "%-10s" % n
        print(line)

    print()
    for g in cats[:3]:
        tp = sum(1 for r in rows if r["gold"] == g and r["pred"] == g)
        n = sum(1 for r in rows if r["gold"] == g)
        print("  %-8s 召回 %d/%d = %.0f%%" % (g, tp, n, 100 * tp / n))
    acc = sum(r["ok"] for r in rows) / len(rows)
    print("  整体准确率 %.1f%% (%d/%d)" % (100 * acc, sum(r["ok"] for r in rows), len(rows)))

    con_tp = sum(1 for r in rows if r["gold"] == "矛盾" and r["pred"] == "矛盾")
    print("\n" + "=" * 96)
    if con_tp == 0:
        print("❌ **判死：核验器从不输出「矛盾」。**")
        print("   三分类塌成两分类，「矛盾 0 条」是仪器坏了而非模型没错。")
        print("   整套差集核验指标作废——训练信号无从产生。")
    else:
        print("✅ 核验器能判矛盾，「矛盾 0 条」是可解释的观察，不是仪器假象。")
        print("   下一步可进入：修 direct 偏置 + 扩依据包。")
    json.dump(rows, open("%s/verifier_test.json" % OUT, "w"), ensure_ascii=False, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
