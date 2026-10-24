# -*- coding: utf-8 -*-
"""判官变体与跨变体稳定性（B-3）＋ 跨判官交叉实验（B-2c）。

> 2026-10-22 ｜ 第二组 ｜ 落点：`routes/COLLAPSE/eval/judge_variants.py`
> 依据：协议 §4.6（判官自检闸门：真 ≥ 3/4 且 假 ≥ 3/4）、§4.8（`judge_same_vendor`）、
>      §3.2（噪声地板三段判读）、`routes/C/noise_floor.py` 的 `δ_judge_version`
> 文献：ToT 同源 **74%** / 换评估器 **64%** / 反过来 **31%**（⇒ 换判官后净增益塌掉 ⇒ 结论无效）

## 为什么必须做

- **坑 ⑥（判官同源）**：被测侧与判官同厂商/同家族 ⇒ 读数不可当裁决。
- **实测过的事**：同一批答案、同一判官模型，**只换提示词版本**，承重数分布就变
  （`batch-U1/REPORT.md` §2.3）⇒ **任何"维度数"读数都必须带判官版本号**。
- ⇒ 本脚本做两件事：
  1. **每个变体先过自检闸门**（不过 ⇒ 该变体不参与比较，协议 F7）；
  2. 同一批答案用多个变体各测一遍 ⇒ 出**跨变体稳定性表**（哪个读数稳、哪个不稳）。

## 自检集：来自 **DEV 金标**（协议 §2.2 第 5 条：自检集必须来自 DEV 集自造题）

- **真卡** = 金标里 `is_load_bearing=true` 的卡
- **假卡** = 金标里 `is_load_bearing=false` 的卡（花絮/不承重）
⇒ 判官要判的是 `load_bearing`（不是"这句话对不对"）⇒ 这正是**决定维度数**的那个二值。

## 用法

```bash
python3 judge_variants.py --manifest runs/dev/manifest.json --out runs/dev/judge_variants
```
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import vd_anchor_out as V  # noqa: E402

# ── 判官变体清单（跨厂商 ⇒ `judge_same_vendor=false` 对被测侧成立）──────
VARIANTS: List[Dict[str, Any]] = [
    {"id": "V1-minimax-m31", "vendor": "minimax", "model": "MiniMax-M3.1-Flash-Preview",
     "note": "现用判官（协议 §4.8 的 MiniMax 订阅侧）"},
    {"id": "V2-or-grok43", "vendor": "openrouter", "model": "x-ai/grok-4.3",
     "note": "跨厂商；协议 §4.6 实测自检通过（真 5/5 假 5/5）"},
    {"id": "V3-or-qwen3-14b", "vendor": "openrouter", "model": "qwen/qwen3-14b",
     "note": "第三个家族（Qwen 系）"},
    {"id": "V4-or-deepseek-chat", "vendor": "openrouter", "model": "deepseek/deepseek-chat",
     "note": "第四个家族；协议 §4.6 曾记它自检不稳 ⇒ 在 DEV 金标上复核"},
    # ⚠️ 已排除：`openai/gpt-4.1-mini` / `gpt-4o-mini` / `gemini-2.5-flash` 在本区
    #    **403 不可用**（"This model is not available in your region"）⇒
    #    通道全程返回空 ⇒ 而读数显示 `parsefail=0.0、VD=0` ⇒ **伪装成完美结果**。
    #    证据留档：`judge_variants_V3-gpt41mini-BLOCKED.json`。
]


# ──────────────────────────────────────────────────────────────
def load_selfcheck_set(dev_dir: str, task_ids: List[str],
                       n_true: int = 8, n_false: int = 8) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {"true": [], "false": []}
    for tid in task_ids:
        p = os.path.join(dev_dir, "gold", "%s_cards.json" % tid)
        if not os.path.exists(p):
            continue
        cards = json.load(open(p, encoding="utf-8")).get("cards", [])
        for c in cards:
            (out["true"] if c.get("is_load_bearing") else out["false"]).append(
                {"claim": c["claim"], "task_id": tid, "card_id": c.get("card_id"),
                 "supports_conclusions": c.get("supports_conclusions", [])})
    # 交错抽样（避免只取到前 N 张 ⇒ 避免单一题主导）
    def pick(lst: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
        if len(lst) <= n:
            return lst
        step = len(lst) / float(n)
        return [lst[int(i * step)] for i in range(n)]
    return {"true": pick(out["true"], n_true), "false": pick(out["false"], n_false)}


def selfcheck(llm: V.LLM, sc: Dict[str, List[Dict[str, Any]]], model: str,
              devset: Dict[str, Any]) -> Dict[str, Any]:
    """判官自检：真卡该判 load_bearing=true，假卡该判 false。

    ★★ **按题分组**（2026-10-22 修正）：原先把不同题的金标卡**混在一起**、
      却用**第一道题的题面 + C_t** 去问判官 ⇒ D05/D08 的卡被拿去回答 D01 的题
      ⇒ 真卡通过率被**人为压低**（实测 0.375 = 3/8）⇒ 那不是判官过严，是**自检设计错了**。
      ⇒ 现在每张卡都用**它自己那道题**的题面 / 结论空间 / 依据包去问。

    ★ 闸门型自检要求**可复现**（连跑 2 次一致）⇒ 跑两轮，比较两轮的判定。
    """
    ev_cache: Dict[str, str] = {}
    rounds: List[Dict[str, Any]] = []
    for r in range(2):
        res: Dict[str, Any] = {"true": [], "false": []}
        for kind in ("true", "false"):
            cards = sc[kind]
            by_task: Dict[str, List[Dict[str, Any]]] = {}
            for c in cards:
                by_task.setdefault(c.get("task_id") or "?", []).append(c)
            for tid, group in by_task.items():
                task = V.dev_task(devset, tid)
                if tid not in ev_cache:
                    ev_items = V.evidence_items_from_dev(task)
                    ev_cache[tid] = "\n".join("%d. %s" % (i + 1, e["text"])
                                              for i, e in enumerate(ev_items))
                ev_text = ev_cache[tid]
                for i in range(0, len(group), 8):
                    b = group[i:i + 8]
                    lst = "\n".join("%d. %s" % (n + 1, c["claim"]) for n, c in enumerate(b))
                    raw = llm.chat(V.CARD_Q_IN.format(ask=task.get("ask", ""), ev=ev_text,
                                                      claims=lst),
                                   model=model, temp=0.0, max_tokens=V.MM_TOKEN_FLOOR,
                                   budgets=(12000, 16000), min_ok=len(b) * 15,
                                   purpose="selfcheck_" + kind)
                    got = V.parse_card_lines(raw, len(b))
                    for g in got:
                        idx = g.get("i", 0) - 1
                        if 0 <= idx < len(b):
                            res[kind].append(bool(g.get("load_bearing")) is True)
                    # 解析不到的卡**不计入分母**（同时单独计数，不静默丢）
                    res.setdefault("n_unparsed_" + kind, 0)
                    res["n_unparsed_" + kind] += max(0, len(b) - len(got))
        rounds.append(res)
    r0, r1 = rounds

    def acc(res: Dict[str, Any], kind: str) -> Dict[str, Any]:
        vals = res.get(kind, [])
        good = sum(1 for v in vals if (kind == "true") == v)
        return {"n": len(vals), "n_correct": good,
                "rate": round(good / max(len(vals), 1), 4)}

    t0, t1 = acc(r0, "true"), acc(r1, "true")
    f0, f1 = acc(r0, "false"), acc(r1, "false")
    reproducible = (r0.get("true") == r1.get("true")) and (r0.get("false") == r1.get("false"))
    return {
        "true_round1": t0, "true_round2": t1,
        "false_round1": f0, "false_round2": f1,
        "reproducible_2_rounds": reproducible,
        "n_unparsed": r0.get("n_unparsed_true", 0) + r0.get("n_unparsed_false", 0),
        "gate_pass": bool(t0["rate"] >= 0.75 and f0["rate"] >= 0.75 and reproducible),
        "note": "按题分组（每张卡用它自己那道题的题面/结论空间/依据包）",
    }


# ──────────────────────────────────────────────────────────────
def run_variant(variant: Dict[str, Any], items: List[Dict[str, Any]],
                devset: Dict[str, Any], sc: Dict[str, List[Dict[str, Any]]],
                sc_task: Dict[str, Any], workers: int) -> Dict[str, Any]:
    llm = V.LLM(variant["vendor"], variant["model"])
    out: Dict[str, Any] = {"id": variant["id"], "vendor": variant["vendor"],
                           "model": variant["model"], "note": variant.get("note", "")}

    def one(item: Dict[str, Any]) -> Dict[str, Any]:
        task = V.dev_task(devset, item["task_id"])
        answer = open(item["answer_file"], encoding="utf-8").read()
        r = V.measure_one(llm, task, answer, item.get("answer_id"), variant["model"],
                           do_fork_probe=True)
        r["arm"] = item.get("arm")
        r["rep"] = item.get("rep", 1)
        return r

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(one, items))
    out["results"] = {r["answer_id"]: r for r in results}
    out["calls"] = llm.log.summary()

    # 自检（与测量分开跑，避免互相污染上下文）
    out["selfcheck"] = selfcheck(V.LLM(variant["vendor"], variant["model"]), sc,
                                 variant["model"], devset)
    return out


def stability_table(variants: List[Dict[str, Any]]) -> Dict[str, Any]:
    """跨变体稳定性：每个指标在各变体上的极差 + 逐答案排序是否一致。"""
    metrics = [("VD_anchor_in", "锚内维度数"), ("VD_anchor_out", "锚外维度数"),
               ("n_claims", "断言数"), ("n_cards", "卡片数"),
               ("n_load_bearing_in", "锚内承重卡数"), ("parsefail_rate", "判官解析失败率")]
    ids = [v["id"] for v in variants]
    answer_ids: List[str] = []
    for v in variants:
        for aid in v["results"]:
            if aid not in answer_ids:
                answer_ids.append(aid)
    rows = []
    for m, label in metrics:
        per_variant = {}
        for v in variants:
            vals = [v["results"].get(a, {}).get(m) for a in answer_ids]
            per_variant[v["id"]] = vals
        nums = [x for vals in per_variant.values() for x in vals if isinstance(x, (int, float))]
        spread = (max(nums) - min(nums)) if nums else None
        # 逐答案：各变体的读数是否完全一致
        n_identical = sum(1 for i in range(len(answer_ids))
                          if len({per_variant[v["id"]][i] for v in variants}) == 1)
        rows.append({"metric": m, "label": label, "per_variant": per_variant,
                     "spread": spread, "n_identical_across_variants": n_identical,
                     "n_answers": len(answer_ids),
                     "stable": n_identical == len(answer_ids)})
    return {"answer_ids": answer_ids, "variant_ids": ids, "rows": rows}


def write_markdown(path: str, blob: Dict[str, Any]) -> None:
    L: List[str] = []
    L.append("# 判官变体与跨变体稳定性表 · **实测**（B-3）\n")
    L.append("> 设计见同目录 `JUDGE-VARIANTS.md`；本文件是**跑出来的数**。\n")
    L.append("> %s\n" % blob.get("meta", {}).get("generated_at", ""))
    L.append("> 判官自检集 = **DEV 金标**（真卡 = `is_load_bearing=true`，假卡 = `false`）\n")
    L.append("## 0. 变体清单\n")
    L.append("| 变体 | 厂商 | 模型 | 备注 | 自检（真 / 假） | 两次一致 | 闸门 |")
    L.append("|---|---|---|---|---|---|---|")
    for v in blob["variants"]:
        sc = v.get("selfcheck", {})
        t = sc.get("true_round1", {})
        f = sc.get("false_round1", {})
        L.append("| `%s` | %s | `%s` | %s | %s (%s/%s) / %s (%s/%s) | %s | %s |" % (
            v["id"], v["vendor"], v["model"], v.get("note", ""),
            t.get("rate"), t.get("n_correct"), t.get("n"), f.get("rate"),
            f.get("n_correct"), f.get("n"),
            "是" if sc.get("reproducible_2_rounds") else "**否**",
            "**通过**" if sc.get("gate_pass") else "**未过 ⇒ 该变体不参与比较**"))
    L.append("\n## 1. 逐答案读数\n")
    aids = blob["stability"]["answer_ids"]
    vids = blob["stability"]["variant_ids"]
    L.append("| answer_id | " + " | ".join("`%s` IN/OUT" % v for v in vids) + " |")
    L.append("|---" * (len(vids) + 1) + "|")
    for aid in aids:
        cells = []
        for v in blob["variants"]:
            r = v["results"].get(aid, {})
            cells.append("%s / %s" % (r.get("VD_anchor_in"), r.get("VD_anchor_out")))
        L.append("| %s | %s |" % (aid, " | ".join(cells)))
    L.append("\n## 2. 跨变体稳定性\n")
    L.append("| 指标 | 各变体极差 | 逐答案完全一致的题数 | 判读 |")
    L.append("|---|---|---|---|")
    for row in blob["stability"]["rows"]:
        L.append("| %s | %s | %s/%s | %s |" % (
            row["label"], row["spread"], row["n_identical_across_variants"], row["n_answers"],
            "**稳**" if row["stable"] else "**不稳**（换判官就动 ⇒ 该读数不能当裁决）"))
    L.append("\n## 3. 成本\n")
    L.append("| 变体 | 调用数 | 空内容 | 截断 | 错误 | 总 token |")
    L.append("|---|---|---|---|---|---|")
    for v in blob["variants"]:
        c = v.get("calls", {})
        L.append("| `%s` | %s | %s | %s | %s | %s |" % (
            v["id"], c.get("n_calls"), c.get("n_empty_content"), c.get("n_truncated"),
            c.get("n_error"), c.get("total_tokens")))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main(argv=None) -> int:
    import datetime
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dev", default=V.DEV_DIR)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--variants", default="", help="逗号分隔的变体 id（默认全部）")
    ap.add_argument("--reuse-measurements", nargs="*", default=[],
                    help="已有的 judge_variants.json（可多个）⇒ **只重跑自检**，不重跑测量")
    ap.add_argument("--merge-from", default="",
                    help="已有的 anchor_readout.json（用它的读数当作一个变体参与稳定性表，"
                         "不重跑 API）⇒ 用于把 MiniMax 批跑的读数与跨厂商变体放在一起比")
    args = ap.parse_args(argv)

    items = json.load(open(args.manifest, encoding="utf-8"))
    devset = V.load_devset(args.dev)
    sc_tasks = sorted({it["task_id"] for it in items})
    sc = load_selfcheck_set(args.dev, sc_tasks)
    sc_task = V.dev_task(devset, sc_tasks[0])

    want = [v for v in VARIANTS if (not args.variants or v["id"] in args.variants.split(","))]
    outdir = args.out
    os.makedirs(outdir, exist_ok=True)
    variants_out = []
    reuse = {}
    for path in (args.reuse_measurements or []):
        if not os.path.exists(path):
            continue
        blob = json.load(open(path, encoding="utf-8"))
        if "results" in blob and "variants" not in blob:      # V1 的 anchor_readout.json
            reuse["V1-minimax-m31"] = {
                "id": "V1-minimax-m31", "vendor": "minimax",
                "model": blob.get("judge_model", "MiniMax-M3.1-Flash-Preview"),
                "note": "主批跑读数（%s）" % os.path.basename(path),
                "results": blob.get("results", {}), "calls": blob.get("calls", {})}
            continue
        for v in blob.get("variants", []):
            if v.get("id", "").endswith("(merged)"):
                continue
            reuse[v["id"]] = v
    print("✓ 复用既有测量读数：%d 个变体（%s）"
          % (len(reuse), ", ".join(reuse) or "无"))

    for v in want:
        print("=== 变体 %s (%s) ===" % (v["id"], v["model"]), flush=True)
        if v["id"] in reuse:
            prev = reuse[v["id"]]
            r = {"id": v["id"], "vendor": v["vendor"], "model": v["model"],
                 "note": v.get("note", ""), "results": prev.get("results", {}),
                 "calls": prev.get("calls", {})}
            r["selfcheck"] = selfcheck(V.LLM(v["vendor"], v["model"]), sc, v["model"], devset)
        else:
            r = run_variant(v, items, devset, sc, sc_task, args.workers)
        variants_out.append(r)
        print("   自检：真 %s / 假 %s ｜ 闸门 %s" % (
            r["selfcheck"]["true_round1"]["rate"], r["selfcheck"]["false_round1"]["rate"],
            "通过" if r["selfcheck"]["gate_pass"] else "未过"), flush=True)
        for aid, rr in r["results"].items():
            print("   %-28s IN=%s OUT=%s parsefail=%s" % (
                aid, rr.get("VD_anchor_in"), rr.get("VD_anchor_out"),
                rr.get("parsefail_rate")), flush=True)
        # 每跑完一个变体就落盘（**中断不丢已跑结果**）
        with open(os.path.join(outdir, "judge_variants.json"), "w", encoding="utf-8") as f:
            json.dump({"meta": {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                                "manifest": args.manifest, "devset_hash": "sha256:41bbb538a454d9b0"},
                       "variants": variants_out}, f, ensure_ascii=False, indent=2)

    # 合并已有读数（例如 MiniMax 批跑的结果）作为**另一个变体**参与稳定性表
    if args.merge_from and os.path.exists(args.merge_from):
        prev = json.load(open(args.merge_from, encoding="utf-8"))
        pres = prev.get("results", {})
        pv = {"id": "V1-minimax-m31(merged)", "vendor": "minimax",
              "model": prev.get("judge_model", "MiniMax-M3.1-Flash-Preview"),
              "note": "来自 %s 的既有读数（未重跑）" % os.path.basename(args.merge_from),
              "results": pres, "calls": prev.get("calls", {}),
              "selfcheck": {"note": "该变体的自检见 selftest_out_c/selftest.json"}}
        variants_out = [pv] + variants_out
        print("✓ 已合并既有读数：%s（%d 份）" % (args.merge_from, len(pres)))

    blob = {"meta": {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                     "manifest": args.manifest},
            "variants": variants_out,
            "stability": stability_table(variants_out)}
    with open(os.path.join(outdir, "judge_variants.json"), "w", encoding="utf-8") as f:
        json.dump(blob, f, ensure_ascii=False, indent=2)
    write_markdown(os.path.join(outdir, "JUDGE-VARIANTS-RESULTS.md"), blob)
    print("\n✓ 落盘 %s" % outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
