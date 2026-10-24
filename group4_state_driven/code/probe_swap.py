#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · D-2 置换探针（状态转移律的因果对照）

═══ 为什么必须单独测这个 ═══
v1 里 D-2 被写成「约束① vs 约束② 的 jaccard」。**这个判据是无效的**：
约束①（f 步的产物）与约束②（g 步的产物）本来就是两个不同步骤的输出，
jaccard 低是**平凡的**，测不出任何东西。

═══ 正确的判据 ═══
**状态历史置换**：
    同一份状态 S₀、同一个题目，只把 g 步看到的**初稿**换成另一个样本的初稿，
    重跑 g 步，看约束② 是否改变。
  · 改变 ⇒ g 步真的在读历史 ⇒ **状态转移律在起作用** ✔
  · 不变 ⇒ g 步是固定模板（"把上一稿改得更好"）⇒ **状态机是假的** ❌

g 步的输入只有 {S₀, 题面, 初稿}，所以置换后的差异**只可能**来自初稿 ⇒ 干净的因果对照。

★ 与 C1/S/R1 的对比：
  C1 臂有"状态"可转移 ⇒ 置换敏感度应高于 S 臂（中性状态，转移无内容可依）。
  若 C1 ≈ S ⇒ 所谓状态转移只是"读初稿然后改写"的通用流程，与状态无关。
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner as R          # noqa: E402
import runner2 as R2        # noqa: E402
import metrics2 as M        # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="D-2 置换探针")
    ap.add_argument("path", nargs="?", default="runs/phase0.jsonl")
    ap.add_argument("--out", default="")
    ap.add_argument("--arms", default="C1,S,R1")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--g-max-tokens", type=int, default=800)
    ap.add_argument("--max-calls", type=int, default=200)
    ap.add_argument("--workers", type=int, default=6, help="并发数（纯 IO 等待）")
    ap.add_argument("--api", choices=["minimax", "openrouter"], default="minimax",
                    help="API 后端（openrouter 需 --model）")
    ap.add_argument("--model", default="", help="模型 id（--api openrouter 时有效）")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--key-env", default="")
    ap.add_argument("--topics-file", default="",
                    help="自定义题库模块名（须提供 TOPICS 列表）。"
                         "★ 不加这个 ⇒ 探针在 R.TOPICS 里找不到自定义题 ⇒ 崩在 None 上")
    args = ap.parse_args()

    if args.topics_file:
        import importlib
        mod = importlib.import_module(args.topics_file)
        R.TOPICS = mod.TOPICS
        R2.R.TOPICS = mod.TOPICS
        if hasattr(mod, "POLARITY"):
            import polarity_lexicon
            polarity_lexicon.register(mod.POLARITY)
        print("[topics] 自定义题库 %s：%s" % (args.topics_file, ",".join(t["id"] for t in mod.TOPICS)))
    if args.api == "openrouter":
        import api_openrouter
        R2.API.update({"mode": "openrouter",
                       "model": args.model or "x-ai/grok-4.20",
                       "base": args.base_url or api_openrouter.DEFAULT_BASE,
                       "key_env": args.key_env or api_openrouter.DEFAULT_KEY_ENV})
        print("[api] OpenRouter · model=%s" % R2.API["model"])

    src = Path(args.path)
    src = src if src.is_absolute() else (HERE / src)
    # ★ R.load_state 返回 (done_keys, stances)，**不是** gens ⇒ 自己读 gens
    _done, stances = R.load_state(src)
    gens = []
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("kind") == "gen" and not r.get("error"):
            gens.append(r)
    by = {}
    for g in gens:
        if g.get("arm") in args.arms.split(","):
            by.setdefault((g["topic_id"], g["arm"]), []).append(g)

    out_path = Path(args.out) if args.out else src.with_suffix(".swap.jsonl")
    out_path = out_path if out_path.is_absolute() else (HERE / out_path)
    fh = out_path.open("a", encoding="utf-8")
    n = 0
    lock = threading.Lock()
    batch_id = time.strftime("%Y%m%d-%H%M%S") + "-swap"
    print("[batch] swap batch_id=%s" % batch_id)

    def one(tid, arm, group):
        nonlocal n
        """对 (题, 臂) 的每个样本做一次历史置换：把 g 步看到的初稿换成下一个样本的初稿。"""
        if len(group) < 2:
            print("  [skip] %s/%s 只有 %d 个样本，置换需要 >=2" % (tid, arm, len(group)))
            return None
        if arm == "S":
            st = R2.NEUTRAL_STATE
        elif arm in ("C1", "C2"):
            # ★ R.load_state 的 stances 值**已经是** stance_profile 本身
            #   （不是整条记录）⇒ 不能再 .get("stance_profile")
            st = stances.get((tid, "C0"))
        elif arm == "R0":
            st = R2.R0_STATE
        else:
            st = stances.get((tid, arm))
        if not st:
            print("  [skip] %s/%s 无状态" % (tid, arm))
            return None
        topic = next(t for t in R.TOPICS if t["id"] == tid)
        for j, sj in enumerate(group):
            k = (j + 1) % len(group)          # 环形 donor：每个样本一个置换源
            donor = group[k]
            fstep = next((s for s in (sj.get("mid") or {}).get("steps") or []
                          if s.get("step") == "f"), None)
            gstep = next((s for s in (sj.get("mid") or {}).get("steps") or []
                          if s.get("step") == "g"), None)
            if not fstep or not gstep:
                continue
            own = gstep.get("constraints") or []
            draft = next((s.get("draft") for s in (donor.get("mid") or {}).get("steps") or []
                          if s.get("step") == "write"), None)
            if not draft:
                continue
            with lock:
                if n >= args.max_calls:
                    print("[stop] 达到 max-calls")
                    return None
                n += 1
            tmpl = R2.G2_PROMPT if arm == "C2" else R2.G_PROMPT
            p3 = tmpl.format(stance=R2._stance_for_f(st),
                             topic=R2._topic_for_f(topic), draft=draft)
            try:
                txt, usage, dt, _ = R2.chat([{"role": "user", "content": p3}],
                                           max_tokens=args.g_max_tokens,
                                           temperature=args.temperature, timeout=args.timeout)
            except Exception as e:
                print("  [ERR] %s/%s#%s: %s" % (tid, arm, sj.get("sample"), e))
                continue
            if arm == "C2":
                sec = R2.parse_sections(txt)
                un = sec["unlanded"]
                cons_perm = sec["cons"][:3]
                facts_perm = sec["facts"][:10]
            else:
                un, cons_perm, facts_perm = R2._parse_g(txt)
            sens = M.transfer_sensitivity(own, cons_perm)
            with lock:
                fh.write(json.dumps({
                    "kind": "probe_swap", "topic_id": tid, "arm": arm,
                    "sample": sj.get("sample"), "donor_sample": donor.get("sample"),
                    "batch_id": batch_id,
                    "own_constraints": own, "perm_constraints": cons_perm,
                    "unlanded_perm": un, "facts_perm": facts_perm,
                    "swap_jaccard": sens["jaccard"], "swap_identical": sens["identical"],
                    "swap_changed": sens["changed"],
                    "usage": usage, "latency": round(dt, 1),
                }, ensure_ascii=False) + "\n")
                fh.flush()
            print("  [swap] %s/%s#%s donor=%s jaccard=%.4f changed=%s"
                  % (tid, arm, sj.get("sample"), donor.get("sample"),
                     sens["jaccard"], sens["changed"]))
        return True

    tasks = [(tid, arm, g) for (tid, arm), g in sorted(by.items())]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = [ex.submit(one, tid, arm, g) for tid, arm, g in tasks]
        for fu in as_completed(futs):
            try:
                fu.result()
            except Exception as e:
                print("  [ERR] task: %s" % e)
    fh.close()
    print("\n[done] 置换调用 %d 次 → %s" % (n, out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
