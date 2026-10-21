# -*- coding: utf-8 -*-
"""DEV 集装配器：把三名构建者交回的 `evidence/Dxx.json` + `gold/Dxx_cards.json`
合并成 `devset.json` + `MANIFEST.json`，并跑**冻结前闸门**。

**为什么要有这一步**：三份并行产物必须**同构、同一把尺子**才能当同一份 DEV 集用；
且**冻结（MANIFEST + 哈希）之后**任何改动都会被发现 ⇒ DEV 集才是"可复现的地基"。

用法：
  python3 build_devset.py [--check-only]
"""
import glob
import hashlib
import json
import os
import re
import sys
import datetime

DEV = "/workspace/lab/routes/DEV"
BANNED_TOPIC_WORDS = [
    "自行车", "公路赛", "骑行", "大组赛", "自行车赛",
    "高考", "报志愿", "志愿填报", "620", "选校", "湖北",
    "朗诵", "诗歌", "爱国诗",
]
TEST_LEAK_WORDS = [
    "湖北", "620", "多血质", "胆汁质", "粘液质", "抑郁质", "陈会昌", "气质量表",
    "1.6km", "回头弯", "800m", "五一小长假", "图书馆借阅", "假期的作业",
]
VERDICT_ENUMS = ("支持", "矛盾", "未提及", "非主张")


def sha(obj):
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()[:16]


def main():
    check_only = "--check-only" in sys.argv
    ev_files = sorted(glob.glob(os.path.join(DEV, "evidence", "D*.json")))
    gold_files = sorted(glob.glob(os.path.join(DEV, "gold", "D*_cards.json")))
    print("找到 evidence %d 份 ／ gold %d 份" % (len(ev_files), len(gold_files)))
    if not ev_files:
        print("✘ 还没有 evidence ⇒ 装配器无事可做（等构建者交付）")
        return 1

    problems, tasks, golds = [], [], []
    for fp in ev_files:
        tid = os.path.basename(fp).split(".")[0]
        d = json.load(open(fp, encoding="utf-8"))
        gp = os.path.join(DEV, "gold", "%s_cards.json" % tid)
        g = json.load(open(gp, encoding="utf-8")) if os.path.exists(gp) else None

        # ── 闸门 1：字段齐全
        for k in ("task_id", "ask", "conclusion_space", "key_conclusions",
                  "evidence", "evidence_second_source"):
            if k not in d:
                problems.append("%s 缺字段 %s" % (tid, k))
        if d.get("task_id") != tid:
            problems.append("%s task_id 与文件名不符（%s）" % (tid, d.get("task_id")))

        # ── 闸门 2：结论空间 3–8 条；key_conclusions ⊆ conclusion_space
        cs = d.get("conclusion_space") or []
        ids = {c.get("id") for c in cs}
        if not (3 <= len(cs) <= 8):
            problems.append("%s conclusion_space %d 条（应 3–8）" % (tid, len(cs)))
        for kc in d.get("key_conclusions") or []:
            if kc not in ids:
                problems.append("%s key_conclusion %s 不在 conclusion_space 里" % (tid, kc))

        # ── 闸门 3：每条依据要有 url + quote + date
        ev = d.get("evidence") or []
        if not ev:
            problems.append("%s 没有依据条目" % tid)
        for e in ev:
            src = e.get("source") or {}
            if not str(src.get("url", "")).startswith("http"):
                problems.append("%s %s 的 source.url 不合法" % (tid, e.get("id")))
            if not str(src.get("quote", "")).strip():
                problems.append("%s %s 缺 source.quote（不可逐字引用）" % (tid, e.get("id")))

        # ── 闸门 4：第二来源核验覆盖所有主依据条目
        sec = {x.get("id"): x for x in (d.get("evidence_second_source") or [])}
        for e in ev:
            if e.get("id") not in sec:
                problems.append("%s %s 没有第二来源核验记录" % (tid, e.get("id")))
            elif sec[e["id"]].get("status") not in ("confirmed", "single_source", "inferred_only"):
                problems.append("%s %s 第二来源 status 非法" % (tid, e.get("id")))

        # ── 闸门 5：禁用题 + TEST 集泄漏
        blob = json.dumps(d, ensure_ascii=False) + (json.dumps(g, ensure_ascii=False) if g else "")
        for w in BANNED_TOPIC_WORDS:
            if w in blob:
                problems.append("%s 命中禁用题关键词「%s」" % (tid, w))
        for w in TEST_LEAK_WORDS:
            if w in blob:
                problems.append("%s 命中 TEST 集泄漏词「%s」" % (tid, w))

        # ── 闸门 6：金标
        if not g:
            problems.append("%s 没有金标卡组" % tid)
        else:
            cards = g.get("cards") or []
            dist = g.get("distractors") or []
            if len(cards) < 12:
                problems.append("%s 金标正样本 %d 张（应 ≥12）" % (tid, len(cards)))
            if len(dist) < 3:
                problems.append("%s 干扰项 %d 条（应 ≥3）" % (tid, len(dist)))
            ev_ids = {e.get("id") for e in ev}
            for c in cards:
                if c.get("evidence_ref") not in ev_ids:
                    problems.append("%s 金标卡 %s 的 evidence_ref %r 不在依据包里"
                                    % (tid, c.get("card_id"), c.get("evidence_ref")))
                if not c.get("supports_conclusions"):
                    problems.append("%s 金标卡 %s 的 supports_conclusions 为空"
                                    % (tid, c.get("card_id")))
                elif not set(c["supports_conclusions"]) <= ids:
                    problems.append("%s 金标卡 %s 的 supports_conclusions 越界"
                                    % (tid, c.get("card_id")))
                if not str(c.get("decision_changed", "")).strip():
                    problems.append("%s 金标卡 %s 缺 decision_changed（承重声明）"
                                    % (tid, c.get("card_id")))

        t = dict(d)
        t["evidence_hash"] = sha([(e.get("id"), e.get("text")) for e in ev])
        t["gold_hash"] = sha(g) if g else None
        tasks.append(t)
        if g:
            golds.append(g)

    # ── 交叉闸门：题目之间不能高度重复（防"9 道题其实是 1 道"）
    for i in range(len(tasks)):
        for j in range(i + 1, len(tasks)):
            a = set(tasks[i].get("conclusion_space") and
                    [c["text"] for c in tasks[i]["conclusion_space"]] or [])
            b = set(tasks[j].get("conclusion_space") and
                    [c["text"] for c in tasks[j]["conclusion_space"]] or [])
            if a and b:
                jac = len(a & b) / len(a | b)
                if jac > 0.6:
                    problems.append("%s 与 %s 的结论空间过于相似（Jaccard=%.2f）"
                                    % (tasks[i]["task_id"], tasks[j]["task_id"], jac))

    print("\n【冻结前闸门】")
    if problems:
        print("✘ %d 条问题：" % len(problems))
        for p in problems:
            print("   - %s" % p)
        return 1
    print("✅ 全部闸门通过（%d 题）" % len(tasks))

    if check_only:
        return 0

    # ── 冻结
    devset = dict(
        devset_id="DEV-2026-10-21",
        built_at=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        n_tasks=len(tasks),
        tasks=tasks,
    )
    with open(os.path.join(DEV, "devset.json"), "w", encoding="utf-8") as f:
        json.dump(devset, f, ensure_ascii=False, indent=2)
    manifest = dict(
        devset_id=devset["devset_id"],
        devset_hash=sha(devset["tasks"]),
        per_task={t["task_id"]: dict(evidence_hash=t["evidence_hash"],
                                     gold_hash=t["gold_hash"]) for t in tasks},
        builder="3 名独立构建者（甲/乙/丙）并行 + 装配器闸门",
        frozen_at=devset["built_at"],
        spec=os.path.join(DEV, "DEV-SPEC.md"),
        note="冻结后任何改动都会使 devset_hash 变化 ⇒ 改动必须重测全部并声明。",
    )
    with open(os.path.join(DEV, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("\n✓ devset.json + MANIFEST.json 已冻结")
    print("  devset_hash = %s" % manifest["devset_hash"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
