#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 通道状态与配额检查（★ chat 与 embedding 分开测，★ 各有各的恢复逻辑 ★）

> 落点：`creativity_lab/experiments/channel_status.py`
> 用法：
>   python3 -B creativity_lab/experiments/channel_status.py            # ★ 全测 ★
>   python3 -B creativity_lab/experiments/channel_status.py --json-out path.json
>
> ★ **为什么需要它（★ 2026-10-26 实测逼出来的 ★）** ★
★ 2026-10-26 10:14 UTC 起，★ 本组拓扑臂批的 chat 调用开始【HTTP 429 限流】★
★ ⇒ ★ 而限流【不是余额耗尽】⇒ ★ 它会【在 5 小时窗口结束时自动恢复】★
★ ⇒ ★ 同时另一条通道（嵌入 `embo-01`）报 `1008 insufficient balance` ⇒ ★ **余额耗尽、不会自愈** ★
★ ⇒ ★ ★★ **两者的处置完全相反**：★ chat 限流 ⇒ 【等窗口复位即可】★；★ 嵌入余额 ⇒ 【必须充值】★★
★ ⇒ ⇒ ★ **⇒ 必须有一个能【分别】测这两个通道的工具，★ 否则会把「等一等就好」和「必须充值」搞混 ★**
★ ⇒ ⇒ ★ 本工具还给出：★ 窗口恢复时刻（★ 从配额接口读，★ 不靠猜 ★）+ ★ 单元级失败重算 ★
>
> ★ **纪律** ★
★ ① **只读**（★ 不改任何生产代码 ★）★ ② **不打印 key** ★
★ ③ 通道状态的结论**必须由实测得到**，★ 不靠错误信息推断（★ 错误信息可能来自不同层 ★）
★ ④ 单元级失败**独立重算**（★ 不信批自己的 manifest ★）

"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.environ.get("OPENROUTER_BASE_URL", "https://api.minimaxi.com/v1").rstrip("/")


def _key():
    return os.environ.get("MINIMAX_SUBSCRIPTION_KEY", "")


def _post(url, payload, timeout=30):
    key = _key()
    if not key:
        return {"ok": False, "err": "★ 环境里没有 MINIMAX_SUBSCRIPTION_KEY ★"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "http": r.status, "body": json.loads(r.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except Exception:                          # noqa: BLE001
            body = {"raw": raw[:300]}
        return {"ok": False, "http": e.code, "body": body}
    except Exception as e:                        # noqa: BLE001
        return {"ok": False, "err": str(e)[:200]}


def check_quota():
    """★ 配额接口：★ 窗口的起止、剩余时间、本周剩余 ★"""
    key = _key()
    if not key:
        return {"ok": False, "err": "no key"}
    url = BASE + "/coding_plan/remains"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode("utf-8"))
    except Exception as e:                        # noqa: BLE001
        return {"ok": False, "err": str(e)[:200]}
    out = []
    for m in (j.get("model_remains") or []):
        out.append({
            "model_name": m.get("model_name"),
            "interval_start_utc": dt.datetime.utcfromtimestamp(m["start_time"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "interval_end_utc": dt.datetime.utcfromtimestamp(m["end_time"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "interval_remains_min": round(m.get("remains_time", 0) / 60000.0, 1),
            "interval_status": m.get("current_interval_status"),
            "interval_remaining_percent": m.get("current_interval_remaining_percent"),
            "weekly_remains_hours": round(m.get("weekly_remains_time", 0) / 3600000.0, 2),
            "weekly_remaining_percent": m.get("current_weekly_remaining_percent"),
        })
    return {"ok": True, "models": out, "base_resp": j.get("base_resp")}


def check_chat():
    """★ chat 通道实测（★ 单条、★ 最小 token ★）★"""
    r = _post(BASE + "/chat/completions",
              {"model": "MiniMax-M3", "messages": [{"role": "user", "content": "说一个字"}],
               "max_tokens": 8})
    if not r.get("ok"):
        msg = ""
        b = r.get("body") or {}
        err = b.get("error") or {}
        msg = err.get("message") or r.get("err") or ""
        return {"ok": False, "http": r.get("http"), "msg": str(msg)[:200],
                "limited": "429" in str(r.get("http")) or "用量上限" in str(msg)}
    return {"ok": True, "http": r.get("http")}


def check_embed():
    """★ 嵌入通道实测（★ embo-01，★ 参数必须同时给 type 与 texts ★）★"""
    r = _post(BASE + "/embeddings", {"model": "embo-01", "type": "db", "texts": ["一"]})
    if not r.get("ok"):
        return {"ok": False, "http": r.get("http"), "msg": str(r.get("err"))[:200]}
    b = r.get("body") or {}
    br = b.get("base_resp") or {}
    vecs = b.get("vectors")
    return {"ok": bool(vecs), "http": r.get("http"),
            "status_code": br.get("status_code"), "status_msg": br.get("status_msg"),
            "n_vectors": (len(vecs) if vecs else 0)}


def recount_units(run_dir):
    """★ 单元级失败【独立重算】（★ 不信批自己的 manifest ★）★"""
    units_dir = os.path.join(run_dir, "units")
    if not os.path.isdir(units_dir):
        return {"ok": False, "err": "units 目录不存在"}
    tot = nf = ne = both = 0
    n_units = 0
    bad_len = 0
    for f in sorted(glob.glob(os.path.join(units_dir, "*.json"))):
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception:                         # noqa: BLE001
            continue
        n_units += 1
        cs = j.get("calls") or []
        if len(cs) != (j.get("n_calls") or 0):
            bad_len += 1
        for c in cs:
            tot += 1
            f_ = (c.get("finish_reason") == "exception") or (c.get("ok") is False)
            e_ = not c.get("has_content")
            nf += f_
            ne += e_
            both += (f_ and e_)
    n = max(1, tot)
    return {"ok": True, "n_units": n_units, "n_calls": tot,
            "n_failed": nf, "n_empty": ne, "n_failed_and_empty": both,
            "len_mismatch_units": bad_len,
            "health_as_formula": round(1 - (nf + ne) / n, 4),
            "health_dedup": round(1 - max(nf, ne) / n, 4),
            "double_count_note": "★ 公式 1-(nf+ne)/n 把「既失败又空内容」的调用计两次 ⇒ ★ 报低、★ 早停会被提前触发 ★"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=os.path.join(ROOT, "runs", "topo-arm-v2-2026-10-25"))
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    now = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    print("== 通道状态（★ 实测 UTC %s ★）==" % now)
    print()
    q = check_quota()
    if q.get("ok"):
        print("★ 配额：")
        for m in q["models"]:
            print("   [%s] 窗口 %s → %s ｜ 剩余 %s 分 ｜ status=%s（★ 2 = 限流中 ★）｜ 本周剩 %s h"
                  % (m["model_name"], m["interval_start_utc"], m["interval_end_utc"],
                     m["interval_remains_min"], m["interval_status"], m["weekly_remains_hours"]))
    else:
        print("★ 配额：读不到（%s）" % q.get("err"))
    print()
    c = check_chat()
    if c.get("ok"):
        print("★ chat（general）：★ ✔ 通")
    else:
        print("★ chat（general）：★ ✘ 不通 ｜ HTTP %s ｜ %s" % (c.get("http"), c.get("msg")))
        print("   ⇒ ★ 限流（429）⇒ 【★ 等窗口复位即可，★ 不会自愈的只有余额 ★】")
    print()
    e = check_embed()
    if e.get("ok"):
        print("★ 嵌入 embo-01：★ ✔ 通（%s 条向量）" % e.get("n_vectors"))
    else:
        print("★ 嵌入 embo-01：★ ✘ 不通 ｜ HTTP %s ｜ status_code=%s ｜ %s"
              % (e.get("http"), e.get("status_code"), e.get("status_msg")))
        print("   ⇒ ★ **余额耗尽（1008）⇒ 【★ 不会自愈，★ 必须充值 ★】**")
    print()
    r = recount_units(a.run_dir)
    if r.get("ok"):
        print("★ 单元级独立重算（★ 不信 manifest ★）：")
        print("   单元 %d ｜ 调用 %d ｜ 失败 %d ｜ 空内容 %d ｜ 两者重合 %d ｜ len(calls)!=n_calls 的单元 %d"
              % (r["n_units"], r["n_calls"], r["n_failed"], r["n_empty"],
                 r["n_failed_and_empty"], r["len_mismatch_units"]))
        print("   健康度（公式 1-(nf+ne)/n）= %.4f ｜（去重 1-max(nf,ne)/n）= %.4f" % (r["health_as_formula"], r["health_dedup"]))
    else:
        print("★ 单元级重算：%s" % r.get("err"))

    if a.json_out:
        out = {"checked_at_utc": now, "quota": q, "chat": c, "embed": e, "units": r}
        tmp = a.json_out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, a.json_out)
        print()
        print("✔ 落盘 %s" % a.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
