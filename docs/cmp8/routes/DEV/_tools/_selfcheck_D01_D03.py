# -*- coding: utf-8 -*-
"""DEV-SPEC §6 的 7 条质量闸门（只查甲的 D01–D03）+ 用户追加的泄漏词表。"""
import json, os, re, sys, glob

DEV = "/workspace/lab/routes/DEV"
MINE = ["D01", "D02", "D03"]

BANNED_TOPIC = ["自行车", "公路赛", "骑行", "大组赛", "自行车赛",
                "高考", "报志愿", "志愿填报", "620", "选校", "湖北",
                "朗诵", "诗歌", "爱国诗"]
TEST_LEAK = ["湖北", "620", "多血质", "胆汁质", "粘液质", "抑郁质", "陈会昌", "气质量表",
             "1.6km", "回头弯", "800m", "五一小长假", "图书馆借阅", "假期的作业"]
# 用户在本轮追加的硬禁词（含单字"假"与大写连写"AI"）
EXTRA_LEAK = ["湖北", "620", "自行车", "骑行", "1.6km", "气质量表", "多血质", "朗诵", "诗歌",
              "作业", "假", "AI"]
AI_RE = re.compile(r"[A-Za-z]*AI[A-Za-z]*")

ok = True
def fail(msg):
    global ok
    ok = False
    print("   ✘ " + msg)

for tid in MINE:
    ev_path = os.path.join(DEV, "evidence", "%s.json" % tid)
    gd_path = os.path.join(DEV, "gold", "%s_cards.json" % tid)
    print("=" * 78)
    print("【%s】" % tid)
    # 闸门 1：JSON 可解析
    try:
        d = json.load(open(ev_path, encoding="utf-8"))
        g = json.load(open(gd_path, encoding="utf-8"))
        print("   闸门1 JSON 可解析：OK（evidence %d bytes, gold %d bytes）"
              % (os.path.getsize(ev_path), os.path.getsize(gd_path)))
    except Exception as e:
        fail("闸门1 JSON 解析失败：%s" % e); continue

    # 闸门 2：每条依据 url/quote/date 非空，url 以 http 开头
    bad = []
    for e in d["evidence"]:
        s = e.get("source", {})
        if not str(s.get("url", "")).startswith("http"):
            bad.append(e["id"] + " url")
        if not str(s.get("quote", "")).strip():
            bad.append(e["id"] + " quote")
        if not str(s.get("date", "")).strip():
            bad.append(e["id"] + " date")
        if len(s.get("quote", "")) > 120:
            bad.append(e["id"] + " quote>120")
    if bad:
        fail("闸门2 依据字段问题：%s" % ", ".join(bad))
    else:
        print("   闸门2 每条依据 url(http开头)/quote/date 非空，quote≤120字：OK（%d 条）" % len(d["evidence"]))

    # 闸门 3：conclusion_space 3–8；key_conclusions ⊆ ids
    ids = [c["id"] for c in d["conclusion_space"]]
    if not (3 <= len(ids) <= 8):
        fail("闸门3 conclusion_space %d 条（应 3–8）" % len(ids))
    if not set(d["key_conclusions"]) <= set(ids):
        fail("闸门3 key_conclusions 越界")
    else:
        print("   闸门3 conclusion_space %d 条，key_conclusions %s ⊆ ids：OK"
              % (len(ids), ",".join(d["key_conclusions"])))

    # 闸门 4：正样本≥12、干扰项≥3、每卡 evidence_ref/supports_conclusions 非空
    cards, dist = g["cards"], g["distractors"]
    if len(cards) < 12:
        fail("闸门4 正样本 %d 张（应 ≥12）" % len(cards))
    if len(dist) < 3:
        fail("闸门4 干扰项 %d 条（应 ≥3）" % len(dist))
    for c in cards:
        if not c.get("evidence_ref"):
            fail("闸门4 卡 %s 缺 evidence_ref" % c.get("card_id"))
        if not c.get("supports_conclusions"):
            fail("闸门4 卡 %s supports_conclusions 为空" % c.get("card_id"))
        if not str(c.get("decision_changed", "")).strip():
            fail("闸门4 卡 %s 缺 decision_changed" % c.get("card_id"))
        if not set(c.get("supports_conclusions", [])) <= set(ids):
            fail("闸门4 卡 %s supports_conclusions 越界" % c.get("card_id"))
    print("   闸门4 正样本 %d 张 / 干扰项 %d 条 / 每卡 evidence_ref+supports_conclusions+decision_changed 齐备：OK"
          % (len(cards), len(dist)))

    # 闸门 5：金标卡 evidence_ref 都在依据包里
    ev_ids = {e["id"] for e in d["evidence"]}
    miss = [c["card_id"] for c in cards if c["evidence_ref"] not in ev_ids]
    if miss:
        fail("闸门5 卡 %s 的 evidence_ref 不在依据包" % miss)
    else:
        print("   闸门5 全部 %d 张卡的 evidence_ref 均在依据包内：OK" % len(cards))

    # 第二来源覆盖 + 比例
    sec = {x["id"]: x for x in d["evidence_second_source"]}
    nosec = [e["id"] for e in d["evidence"] if e["id"] not in sec]
    badst = [e["id"] for e in d["evidence"] if sec.get(e["id"], {}).get("status") not in
              ("confirmed", "single_source", "inferred_only")]
    conf = sum(1 for e in d["evidence"] if sec.get(e["id"], {}).get("status") == "confirmed")
    if nosec: fail("第二来源缺记录：%s" % nosec)
    if badst: fail("第二来源 status 非法：%s" % badst)
    pct = 100.0 * conf / len(d["evidence"])
    print("   第二来源：%d/%d 条 confirmed（%.0f%%，要求 ≥60%%）；无遗漏、status 合法：%s"
          % (conf, len(d["evidence"]), pct, "OK" if pct >= 60 else "FAIL"))
    if pct < 60: fail("第二来源 confirmed 比例不足 60%")

    # 题面长度
    n = len(d["ask"])
    if not (20 <= n <= 60):
        fail("题面 %d 字，超出 20–60" % n)
    else:
        print("   题面 %d 字（20–60 区间内）：OK" % n)

    # (evidence_ref, supports_conclusions) 不重复
    pairs = [(c["evidence_ref"], tuple(c["supports_conclusions"])) for c in cards]
    if len(pairs) != len(set(pairs)):
        dup = [p for p in set(pairs) if pairs.count(p) > 1]
        fail("存在重复的 (evidence_ref, supports_conclusions) 组合：%s" % dup)
    else:
        print("   %d 张卡的 (evidence_ref, supports_conclusions) 组合互不重复：OK" % len(cards))
    used = {c["evidence_ref"] for c in cards}
    unused = sorted(ev_ids - used)
    if unused:
        print("   注：%d 条依据未被正样本卡直接引用（只用于干扰项判否）：%s" % (len(unused), ",".join(unused)))

    # 闸门 6：题面不含禁用三题关键词
    hit6 = [w for w in BANNED_TOPIC if w in d["ask"]]
    if hit6:
        fail("闸门6 题面命中禁用题关键词：%s" % hit6)
    else:
        print("   闸门6 题面不含禁用三题关键词（自行车/公路赛/高考/620/朗诵/诗歌 等）：OK")

    print("   题面：%s" % d["ask"])
    print("   抽 1 条 source.quote 原文 → %s\n     「%s」" % (d["evidence"][0]["source"]["url"], d["evidence"][0]["source"]["quote"]))

print("=" * 78)
print("【闸门7 泄漏自检】对甲的 6 个文件做 grep（用户追加词表 + TEST 泄漏词 + 大写连写 AI）")
blob = ""
for tid in MINE:
    for p in (os.path.join(DEV, "evidence", "%s.json" % tid), os.path.join(DEV, "gold", "%s_cards.json" % tid)):
        blob += open(p, encoding="utf-8").read()
hits = []
for w in sorted(set(EXTRA_LEAK) | set(TEST_LEAK) | set(BANNED_TOPIC)):
    if w in blob:
        hits.append((w, blob.count(w)))
ai_hits = set(AI_RE.findall(blob))
if hits:
    fail("闸门7 命中：%s" % hits)
if ai_hits:
    fail("闸门7 命中大写连写 AI：%s" % sorted(ai_hits))
if not hits and not ai_hits:
    print("   闸门7 0 命中（词表 %d 项 + AI 正则）：OK" % len(set(EXTRA_LEAK) | set(TEST_LEAK) | set(BANNED_TOPIC)))
    print("   词表：%s" % "、".join(sorted(set(EXTRA_LEAK) | set(TEST_LEAK))))

print("=" * 78)
print("闸门总结果：%s" % ("全部通过 ✅" if ok else "存在失败项 ❌"))
sys.exit(0 if ok else 1)
