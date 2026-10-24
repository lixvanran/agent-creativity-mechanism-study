# -*- coding: utf-8 -*-
"""开跑前冒烟：**任何一项不过就不该开跑**。

1. OpenRouter chat 通不通（grok-3-mini）
2. OpenRouter embedding 通不通、维度多少
3. 判官在 4 个依据包上的自检：真断言该支持、假断言该矛盾
4. MiniMax（被测侧）还活着吗

第 3 项不过 ⇒ 矛盾率不可信 ⇒ 整套实验作废 ⇒ 立刻停。
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from creativity_lab import orclient                       # noqa: E402
from creativity_lab.client import LLM as MM              # noqa: E402
from creativity_lab.verify import check_claims            # noqa: E402

EV = {}
for _i in (1, 2, 3, 4):
    _p = os.path.join(HERE, "creativity_lab", "data", "user4_q%d.json" % _i)
    if os.path.exists(_p):
        EV["A%d" % _i] = json.load(open(_p, encoding="utf-8"))["evidence"]

Q = {
    "A1": "湖北考生，物理类620分，想学AI，应当如何选择大学？",
    "A2": "公路自行车个人比赛（无车队），单圈1.6km共计15圈，单圈由两个800m直路和两个回头弯构成，"
          "本人在大集团里处于中上等水平，该如何安排战术？",
    "A3": "今天是五一小长假的最后一天的18:00，明天就要上学了，我的作业还一笔没动，怎么办？",
    "A4": "这是一份陈会昌气质量表的最终得分：胆汁质-6，多血质23，粘液质-4，抑郁质-1。",
}
T_F = {
    "A1": ("2025年湖北省普通高考首选物理类中，620分及以上的累计人数为7436人",
           "2025年湖北省普通高考首选物理类中，620分及以上的累计人数为74360人"),
    "A2": ("国际自行车联盟（UCI）公路赛规则第 2.3.012 条规定，比赛中任何两名车手之间都可以互相提供食物、饮品、扳手等小帮助",
           "国际自行车联盟（UCI）公路赛规则第 2.3.012 条规定，比赛中任何两名车手之间不得互相提供食物、饮品、扳手等小帮助"),
    "A3": ("番茄工作法由意大利人 Francesco Cirillo 在上世纪八十年代做大学生时用番茄形厨房计时器发展而来",
           "番茄工作法规定每个番茄时段为 50 分钟，之后休息 10 分钟"),
    "A4": ("如果四类得分中有一类得分明显高出其它三种且均高出4分以上，则可定为该类气质型",
           "如果四类得分中有一类得分明显高出其它三种且均高出2分以上，则可定为该类气质型"),
}
fails = []


def main():
    print("=== ① OpenRouter chat (%s) ===" % orclient.PRIMARY, flush=True)
    t0 = time.time()
    o = orclient.LLM()
    try:
        r = o.chat("用一句话说明什么是复利", purpose="smoke", max_tokens=300,
                   budgets=(600,), min_ok=8)
    except Exception as e:
        r = ""
        print("  ✗ 失败:", str(e)[:300], flush=True)
        fails.append("OpenRouter chat 无输出: %s" % str(e)[:80])
    print("  → %d 字符，用时 %.1fs：%s" % (len(r), time.time() - t0, (r or "")[:80]), flush=True)
    print("  模型用量:", o.model_used, flush=True)

    print("=== ② embedding（OpenRouter 优先，失败退 MiniMax embo-01）===", flush=True)
    emb = orclient.Embedder()
    try:
        vs = emb.embed(["湖北620分选AI专业", "620分的湖北考生该选哪所大学"])
        dim = len(vs[0]) if vs and vs[0] else 0
        print("  → %d 条 × %d 维（实际通道: %s）" % (len(vs), dim, emb.used), flush=True)
        if dim == 0:
            fails.append("embedding 无输出")
    except Exception as e:
        print("  ✗ 失败:", str(e)[:140], flush=True)
        fails.append("embedding 失败: %s" % str(e)[:60])

    print("=== ③ 判官自检（%s）===" % orclient.PRIMARY, flush=True)
    tp = fn = tn = fp = 0
    for tid in ("A1", "A2", "A3", "A4"):
        tt, ff = T_F[tid]
        v = check_claims(o, Q[tid], EV.get(tid, ""), [tt, ff])
        gt, gf = v.get(tt, "解析失败"), v.get(ff, "解析失败")
        ok_t, ok_f = gt == "支持", gf == "矛盾"
        tp += 1 if ok_t else 0
        fn += 0 if ok_t else 1
        tn += 1 if ok_f else 0
        fp += 0 if ok_f else 1
        print("  %s 真→%-4s %s ｜ 假→%-4s %s" % (tid, gt, "✓" if ok_t else "✗",
                                                 gf, "✓" if ok_f else "✗"), flush=True)
    print("  真断言 %d/%d ｜ 假断言 %d/%d" % (tp, tp + fn, tn, tn + fp), flush=True)
    print("  判官实际用了: %s" % (o.model_used or orclient.PRIMARY), flush=True)
    if (tn + fp) and tn / (tn + fp) < 0.5:
        fails.append("判官在已知假断言上召回 <50%（矛盾率不可信）")

    print("=== ④ MiniMax（被测侧）===", flush=True)
    mm = MM()
    r2 = mm.chat("用一句话说明什么是复利", purpose="smoke", max_tokens=300,
                 budgets=(600,), min_ok=8)
    print("  → %d 字符：%s" % (len(r2), (r2 or "")[:60]), flush=True)
    if len(r2) < 8:
        fails.append("MiniMax 无输出")

    print("\n" + ("❌ 冒烟未通过：%s" % "；".join(fails) if fails else "✅ 冒烟全部通过，可以开跑"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
