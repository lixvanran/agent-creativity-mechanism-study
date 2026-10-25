#!/usr/bin/env python3
"""**修复 calllog 的三字段错位 + 独立重算真实通道健康度**

> 落点：`creativity_lab/experiments/fix_calllog_fields.py`
> 2026-10-24 ｜ 第二组 · 层2
>
> ## ★ 根因（★ 仓里的真 bug，不是某次实验的）
> `client.py::Call` 的 dataclass 字段声明顺序是
> `model, purpose, max_tokens, finish_reason, content_len, ok, has_content, secs, effort`
> 而**构造时用的是位置参数**：
> `Call(model, purpose, mt, fr, len(last), False, time.time()-t0, effort, len(last)>0)`
> ⇒ ⇒ **`has_content` ← secs（秒数）｜`secs` ← effort（字符串）｜`effort` ← ok（bool）**
>
> ## ★ 后果（三条，全部静默）
> 1. **通道健康度恒为 1.0** —— `has_content` 拿到的是耗时秒数，永远 truthy
>    ⇒ ⇒ **所有历史读数里"健康度 0.9898 / 1.0"都是假的**（它们只说明"没抛异常"）
> 2. **`effort` 从未真正进过元数据** ⇒ 跨 effort 的读数不可比这件事**没有被记录**
> 3. **所有耗时是字符串** ⇒ 读数表里的 `secs` 全错
>
> ## ★ 为什么旧数据可救（错位是确定性一一映射，**完全可逆**）
> 旧 `effort`(bool) ⇒ 新 `has_content`；旧 `secs`(str) ⇒ 新 `effort`；旧 `has_content`(float) ⇒ 新 `secs`
>
> ## ★ 为什么必须「独立重算」而不是相信 manifest
> `manifest.json` 的 `health` 是**执行时算的**（用错了字段）⇒ 它**不能用来验证自己**。
> ⇒ 本脚本从 `calllog.jsonl`（原始逐次记录）**重新计算**健康度，
> 判据用 `content_len` / `finish_reason`（**这两个字段从没错位过**）⇒ ⇒ **独立于执行**。
"""
import json
import os
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = os.path.join(ROOT, "runs")


def is_broken(rec: Dict[str, Any]) -> bool:
    """判别一条记录是否处在**错位**布局（旧格式）。"""
    return (isinstance(rec.get("effort"), bool)
            and isinstance(rec.get("secs"), str)
            and isinstance(rec.get("has_content"), (int, float))
            and not isinstance(rec.get("has_content"), bool))


def fix_rec(rec: Dict[str, Any]) -> Dict[str, Any]:
    if not is_broken(rec):
        return rec
    return {"model": rec.get("model"), "purpose": rec.get("purpose"),
            "max_tokens": rec.get("max_tokens"),
            "finish_reason": rec.get("finish_reason"),
            "content_len": rec.get("content_len"), "ok": rec.get("ok"),
            "has_content": bool(rec.get("effort")),      # 旧的 effort(bool) ⇒ 真正的 has_content
            "secs": rec.get("has_content"),               # 旧的 has_content(float) ⇒ 真正的 secs
            "effort": rec.get("secs")}                    # 旧的 secs(str) ⇒ 真正的 effort


def recompute_health(path: str) -> Dict[str, Any]:
    """从 calllog **独立重算**健康度（判据用没错位过的 content_len / finish_reason）。"""
    recs: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
    n = len(recs)
    if not n:
        return {"n": 0}
    empty = sum(1 for r in recs if not (r.get("content_len") or 0))
    exc = sum(1 for r in recs if r.get("finish_reason") == "exception")
    trunc = sum(1 for r in recs if r.get("finish_reason") == "length")
    # ★ 健康度 = 传输成功（有内容 且 非 exception）
    bad = sum(1 for r in recs
              if not (r.get("content_len") or 0) or r.get("finish_reason") == "exception")
    effs = sorted({r.get("effort") for r in recs if isinstance(r.get("effort"), str)})
    return {"n": n, "n_empty": empty, "n_exception": exc, "n_truncated": trunc,
            "n_bad": bad, "channel_health": round(1 - bad / n, 4),
            "efforts_seen": effs}


def main() -> int:
    apply_fix = "--apply" in sys.argv
    rows = []
    for run in sorted(os.listdir(RUNS)):
        cl = os.path.join(RUNS, run, "calllog.jsonl")
        mf = os.path.join(RUNS, run, "manifest.json")
        if not os.path.exists(cl):
            continue
        recs = [json.loads(l) for l in open(cl, encoding="utf-8") if l.strip()]
        n_broken = sum(1 for r in recs if is_broken(r))
        recs_fixed = [fix_rec(r) for r in recs]
        if apply_fix and n_broken:
            with open(cl, "w", encoding="utf-8") as f:
                for r in recs_fixed:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        h = recompute_health(cl if not (apply_fix and n_broken) else cl)
        old = None
        if os.path.exists(mf):
            try:
                old = json.load(open(mf, encoding="utf-8")).get("health", {}).get("channel_health")
            except Exception:
                old = None
        rows.append((run, n_broken, h, old))
    print("== calllog 字段错位检查 + 独立重算健康度 ==")
    print("  %-42s %6s %8s %8s %8s %s" %
          ("run", "错位条数", "重算健康", "manifest", "差", "efforts"))
    tot_bad = 0
    for run, nb, h, old in rows:
        diff = ""
        if old is not None and h.get("n"):
            d = h["channel_health"] - old
            diff = "%+.4f" % d
            if abs(d) > 1e-6:
                tot_bad += 1
        print("  %-42s %6d %8s %8s %8s %s"
              % (run, nb, h.get("channel_health"), old, diff, ",".join(h.get("efforts_seen") or [])))
    print()
    print("  错位记录总数：%d" % sum(r[1] for r in rows))
    print("  ★ 真实健康度与 manifest 记录不一致的 run 数：%d" % tot_bad)
    if not apply_fix:
        print("  （加 --apply 才会写回修正后的 calllog；**先看清楚再改**）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
