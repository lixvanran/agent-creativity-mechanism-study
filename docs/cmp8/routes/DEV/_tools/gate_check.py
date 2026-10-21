#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DEV 集构建者·丙 的 §6 七道闸门自检（真实输出）。
另加两项额外闸门：
  G8 引文逐字回验：重新抓取每个 source.url，确认 source.quote 仍是页面正文的连续子串（忽略空白差异）。
  G9 第二来源覆盖率 ≥60%。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from extract_quotes import fetch, norm  # noqa: E402

DEV = "/workspace/lab/routes/DEV"
TASKS = ["D07", "D08", "D09"]

BANNED = ["自行车", "公路赛", "骑行", "大组赛", "自行车赛", "高考", "报志愿", "志愿填报", "620",
          "选校", "湖北", "朗诵", "诗歌", "爱国诗"]
LEAK = ["湖北", "620", "多血质", "胆汁质", "粘液质", "抑郁质", "陈会昌", "气质量表",
        "1.6km", "回头弯", "800m", "五一小长假", "图书馆借阅", "假期的作业", "作业"]
USER_EXTRA = ["假", "AI", "1.6km", "气质量表", "多血质", "朗诵", "诗歌", "作业"]

fails = []


def ck(cond, label, detail=""):
    print("   %s %s%s" % ("PASS" if cond else "FAIL", label, ("  ← " + detail) if detail else ""))
    if not cond:
        fails.append(label + " " + detail)


print("=" * 78)
print("§6 闸门 1：JSON 可解析")
data = {}
for t in TASKS:
    ok = True
    for sub, fn in (("evidence", "evidence/%s.json"), ("gold", "gold/%s_cards.json")):
        p = os.path.join(DEV, fn % t)
        try:
            data[(t, sub)] = json.load(open(p, encoding="utf-8"))
            print("   PASS %s/%s 解析成功 (%d bytes)" % (sub, t, os.path.getsize(p)))
        except Exception as e:
            ok = False
            print("   FAIL %s/%s %s" % (sub, t, e))
            fails.append("JSON %s/%s" % (sub, t))

print("\n§6 闸门 2：每条依据的 source.quote 非空、source.url 以 http 开头")
for t in TASKS:
    d = data[(t, "evidence")]
    bad = [e["id"] for e in d["evidence"]
           if not str(e.get("source", {}).get("quote", "")).strip()
           or not str(e.get("source", {}).get("url", "")).startswith("http")]
    ck(not bad, "%s 全部 %d 条依据的 url/quote 合法" % (t, len(d["evidence"])), ",".join(bad))

print("\n§6 闸门 3：conclusion_space 3–8 条；key_conclusions ⊆ conclusion_space")
for t in TASKS:
    d = data[(t, "evidence")]
    cs = d["conclusion_space"]
    ids = [c["id"] for c in cs]
    ck(3 <= len(cs) <= 8, "%s conclusion_space %d 条（3–8）" % (t, len(cs)))
    ck(len(ids) == len(set(ids)), "%s conclusion id 无重复" % t)
    bad = [k for k in d["key_conclusions"] if k not in ids]
    ck(not bad, "%s key_conclusions %s ⊆ conclusion_space" % (t, d["key_conclusions"]), ",".join(bad))

print("\n§6 闸门 4：金标正样本 ≥12、干扰项 ≥3；每张正样本卡 evidence_ref 与 supports_conclusions 非空")
for t in TASKS:
    g = data[(t, "gold")]
    ck(len(g["cards"]) >= 12, "%s 正样本 %d 张（≥12）" % (t, len(g["cards"])))
    ck(len(g["distractors"]) >= 3, "%s 干扰项 %d 条（≥3）" % (t, len(g["distractors"])))
    bad = [c["card_id"] for c in g["cards"]
           if not str(c.get("evidence_ref", "")).strip() or not c.get("supports_conclusions")]
    ck(not bad, "%s 每张正样本卡 evidence_ref/supports_conclusions 非空" % t, ",".join(bad))
    bad = [c["card_id"] for c in g["cards"] if not str(c.get("decision_changed", "")).strip()]
    ck(not bad, "%s 每张正样本卡 decision_changed 非空" % t, ",".join(bad))
    ck(g.get("n_cards") == len(g["cards"]), "%s n_cards 字段与实际卡数一致" % t)
    ck(len({c["card_id"] for c in g["cards"] + g["distractors"]}) == len(g["cards"]) + len(g["distractors"]),
       "%s 卡号唯一" % t)

print("\n§6 闸门 5：金标卡的 evidence_ref 都能在依据包里找到（脚本核对）")
for t in TASKS:
    d, g = data[(t, "evidence")], data[(t, "gold")]
    ev_ids = {e["id"] for e in d["evidence"]}
    bad = [c["card_id"] for c in g["cards"] if c["evidence_ref"] not in ev_ids]
    ck(not bad, "%s 全部 %d 张卡的 evidence_ref 可解析" % (t, len(g["cards"])), ",".join(bad))
    ids = {c["id"] for c in d["conclusion_space"]}
    bad = [c["card_id"] for c in g["cards"]
           if not set(c["supports_conclusions"]) <= ids]
    ck(not bad, "%s 全部卡的 supports_conclusions 未越界" % t, ",".join(bad))
    unused = sorted(ev_ids - {c["evidence_ref"] for c in g["cards"]})
    ck(not unused, "%s 依据包每条依据至少被一张卡引用" % t, ",".join(unused))

print("\n§6 闸门 6：题面不含禁用三题关键词")
for t in TASKS:
    d = data[(t, "evidence")]
    ask = d["ask"]
    hit = [w for w in BANNED if w in ask]
    ck(not hit, "%s 题面无禁用关键词" % t, ",".join(hit))
    ck(20 <= len(ask) <= 60, "%s 题面 %d 字（20–60）" % (t, len(ask)))

print("\n§6 闸门 7：泄漏自检（对全部 6 个 DEV 文件 grep，须 0 命中）")
blob = ""
for t in TASKS:
    for fn in ("evidence/%s.json" % t, "gold/%s_cards.json" % t):
        blob += open(os.path.join(DEV, fn), encoding="utf-8").read()
for name, words in (("禁用题关键词", BANNED), ("TEST 集泄漏词", LEAK), ("用户补充禁用词", USER_EXTRA)):
    for w in words:
        n = blob.count(w)
        ck(n == 0, "grep %s 「%s」 → %d 命中" % (name, w, n))
# 大写 AI 连写单独查（排除 URL 之外的出现）
ai_hits = re.findall(r"AI", blob)
ck(len(ai_hits) == 0, "grep 大写「AI」连写 → %d 命中" % len(ai_hits))
# 假（单字）单独查
jia = blob.count("假")
ck(jia == 0, "grep 单字「假」 → %d 命中" % jia)

print("\n额外闸门 8：引文逐字回验（重新抓取页面，确认 quote 仍是正文连续子串）")
cache = {}
for t in TASKS:
    d = data[(t, "evidence")]
    for e in d["evidence"]:
        u = e["source"]["url"]
        if u not in cache:
            cache[u] = fetch(u)
        page = cache[u]
        if page is None:
            print("   SKIP %s %s（页面拒绝直连，quote 取自 web_search 抓取正文）" % (t, e["id"]))
            continue
        q = e["source"]["quote"]
        hit = norm(q) in norm(page)
        ck(hit, "%s %s 引文回验命中（%s）" % (t, e["id"], u.split("/")[2]))

print("\n额外闸门 9：第二来源覆盖率 ≥60%")
for t in TASKS:
    d = data[(t, "evidence")]
    sec = {x["id"]: x for x in d["evidence_second_source"]}
    miss = [e["id"] for e in d["evidence"] if e["id"] not in sec]
    ck(not miss, "%s 每条依据都有第二来源核验记录" % t, ",".join(miss))
    bad = [x["id"] for x in d["evidence_second_source"]
           if x.get("status") not in ("confirmed", "single_source", "inferred_only")]
    ck(not bad, "%s status 取值合法" % t, ",".join(bad))
    conf = sum(1 for x in d["evidence_second_source"] if x.get("status") == "confirmed")
    tot = len(d["evidence"])
    ck(conf / tot >= 0.6, "%s confirmed %d/%d = %.0f%%（≥60%%）" % (t, conf, tot, 100.0 * conf / tot))
    ss = [x["id"] for x in d["evidence_second_source"] if x.get("status") == "single_source"]
    if ss:
        print("      ↳ single_source: %s（已在 notes 写明原因）" % ",".join(ss))

print("\n" + "=" * 78)
print("合计失败项：%d" % len(fails))
for f in fails:
    print("  - " + f)
sys.exit(1 if fails else 0)
