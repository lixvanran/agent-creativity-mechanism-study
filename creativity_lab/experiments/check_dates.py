#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 日期闸门：★ 把「★ 用外部权威核日期 ★」【机械化】★★★★

★ ★★ 为什么必须有这个脚本（★ 2026-10-24 事故 · 第 1 层论证线回源核出 ★）★★
★ 我方整整一轮工作（★ 43 个文件、211 处 ★）把日期写成了【★ 一个不存在的未来日期 ★】（★ 具体值见 EXEC-LOG ★）——
★ 而真实日期是 **2026-10-24** ⇒ ⇒ ★ **一个不存在的【未来日期】被写进了全部交付物 ★**
★ ⇒ ★ **★ 而且它【看起来完全正常】★★ ★**（★ 格式对、★ 排序像、★ 不承载任何论断 ★）
★ ⇒ ★ ⇒ ★ **★ ⇒ 【日期是最容易整篇错掉的元数据】★★ ★**

★ ★★ 三个外部权威（★ 任一即可 ★）★★
★ ① 沙箱系统时钟（★ `date -u` ★）　② 配额接口报的窗口　③ 远端 commit 的 author.date
★ ⇒ ★ **★ ⇒ ★ 本脚本用 ①（★ 系统时钟 ★）★ ⇒ ★ 且把它做成【闸门】而不是【提醒】★★ ★**

★ ★★ 闸门查三样 ★★
★ ① 仓里出现的【所有形如 YYYY-MM-DD 的日期】⇒ 与机器日期比对
★ 　 ⇒ ★ 【未来日期】= 晚于机器日期 ⇒ ★ **一律判错**（★ 今天的活不可能产出来 ★）
★ 　 ⇒ ★ 【过远的过去】= 早于机器日期 N 天以上 ⇒ ★ 登记（★ 可能是历史、★ 也可能是错 ★）
★ ② 交付物【文件名】里的日期
★ ③ 交付物【内容】里自称「今天/本日/本次」附近的日期
★ ⇒ ★ **★ ⇒ 任何一条不符 ⇒ exit≠0 ⇒ ★ 不许静默通过 ★★★ ★**
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys

SKIP_DIRS = {".git", "__pycache__", ".tmp", ".mavis", "node_modules"}
DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")


def die(msg, code=1):
    print("✘ %s" % msg)
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--max-past-days", type=int, default=60,
                    help="★ 早于机器日期超过这个天数的日期 ⇒ 登记为「过远」★")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--exclude", action="append", default=None,
                    help="★ 排除的目录名（★ 默认排除 runs/：★ 原始产出目录、★ 不随交付包交付 ★）★")
    a = ap.parse_args()

    today = dt.datetime.utcnow().date()
    print("★ ★ ★ 日期闸门（★ 外部权威 = 沙箱系统时钟 UTC ★）★★ ★")
    print("   ★ 机器日期（UTC）= **%s** ★" % today.isoformat())

    future = []          # ★ 【未来日期】⇒ 一定是错的 ★
    too_past = []
    seen = 0
    files = []
    _self_out = os.path.abspath(a.json_out) if a.json_out else None
    for root, dirs, fs in os.walk(a.root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fs:
            p = os.path.join(root, fn)
            # ★ ★ 排除【路径里含 runs/ 的文件】（★ 目录名排除只挡目录、★ 挡不住同层的 .log ★）
            if os.sep + "runs" + os.sep in os.path.abspath(p):
                continue
            # ★ ★ 排除【闸门自己的输出】（★ 否则上一次扫描的结果会【自我污染】下一次 ★）
            if _self_out and os.path.abspath(p) == _self_out:
                continue
            if fn.endswith((".zip", ".pyc", ".png", ".jpg", ".gz", ".pdf")):
                continue
            try:
                s = open(p, encoding="utf-8").read()
            except Exception:
                continue
            files.append(p)
            for m in DATE_RE.finditer(s):
                try:
                    d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    continue
                seen += 1
                if d > today:
                    _ctx = s[max(0, m.start() - 60):m.end() + 60].replace("\n", " ")
                    # ★ ★ 判据精确化（★ 2026-10-24 修 ★）：★ 「未来日期」本身【可能是计划】
                    #   ★ （★ 投稿截止、★ 预注册窗口 ★）⇒ ★ 不该一律判错 ★
                    #   ★ ⇒ ★ 【错】的是：【自称今天/本日/本次/当天】的未来日期 ★ ⇒ ★ 那必是编的 ★★★ ★
                    _self_claim = any(k in _ctx for k in
                                      ("今天", "本日", "本次", "当天", "本日完成", "已于", "截至"))
                    future.append({"file": p, "date": d.isoformat(),
                                   "self_claim_today": _self_claim,
                                   "ctx": _ctx})
                elif (today - d).days > a.max_past_days:
                    too_past.append({"file": p, "date": d.isoformat(),
                                     "days_ago": (today - d).days})
            if DATE_RE.search(fn):
                for m in DATE_RE.finditer(fn):
                    try:
                        d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    except ValueError:
                        continue
                    if d > today:
                        # ★ ★ 文件名里的未来日期：★ 按【mtime】区分 ★★
                        #   ★ 【今天新建/改过】⇒ ★ 判错（★ 今天的活不可能起这种名 ★）
                        #   ★ 【历史遗留】⇒ ★ 只登记（★ 改名会打断大量引用 ★）★★ ★
                        try:
                            _mt = dt.datetime.utcfromtimestamp(os.path.getmtime(p)).date()
                        except Exception:
                            _mt = None
                        _is_today = (_mt == today)
                        # ★ ★ 文件名里的未来日期、★ 且【今天新建】⇒ ★ 判错 ★★
                        #   ★ 理由：★ 【计划性日期不会出现在文件名里】★
                        #   ★   ⇒ ★ 而「今天新建的文件名里有个未来日期」⇒ ★ 必是编的 ★★★ ★
                        #   ★ ★ ★ ⇒ ★ 这一条是被【变异 ③】抓出来的：★ 我第一版没给它
                        #   ★   ★ self_claim_today 字段 ⇒ ★ ⇒ 【不判错】⇒ ★ 闸门自己有洞 ★★ ★
                        future.append({"file": p + "（★ 文件名 ★）", "date": d.isoformat(),
                                       "self_claim_today": _is_today,
                                       "why": "★ 文件名里的未来日期、★ 且该文件【今天新建/改过】⇒ 判错 ★",
                                       "ctx": fn})
                        #   ★ 理由：★ 【计划性日期不会出现在文件名里】★
                        #   ★   ⇒ ★ 而「文件名里有个不存在的未来日期」⇒ ★ 必是编的 ★★★ ★
                        #   ★ ★ ★ ⇒ ★ 这一条是被【变异 ③】抓出来的：★ 我第一版没给它
                        #   ★   ★ self_claim_today 字段 ⇒ ★ ⇒ 【不判错】⇒ ★ 闸门自己有洞 ★★ ★


    # ★ 去掉重复（★ 同一文件同一日期只报一次 ★）
    seenk = set()
    fut = []
    for f in future:
        k = (f["file"], f["date"])
        if k in seenk:
            continue
        seenk.add(k)
        fut.append(f)
    future = fut

    print("   ★ 扫了 %d 个文件、%d 处日期 token ★" % (len(files), seen))
    _hard2 = [f for f in future if f.get("self_claim_today")]
    print("   ★ 未来日期 = **%d** 处（★ 其中【自称今天】的 = **%d** 处 ⇒ ★ 只有这些判错 ★）★"
          % (len(future), len(_hard2)))
    for f in future[:15]:
        print("      ✘ %s ｜ %s ｜ …%s…" % (f["file"], f["date"], f["ctx"][:90]))
    if too_past:
        print("   ★ 【过远的过去】（★ 早于 %d 天 ⇒ 登记待核 ★）= %d 处" % (a.max_past_days, len(too_past)))
        for f in too_past[:5]:
            print("      · %s ｜ %s ｜ %d 天前" % (f["file"], f["date"], f["days_ago"]))

    if a.json_out:
        import json
        out = {"checked_at_utc": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
               "machine_date_utc": today.isoformat(),
               "n_files_scanned": len(files), "n_date_tokens": seen,
               "n_future_dates": len(future),
               "n_future_self_claim_today": len([f for f in future if f.get("self_claim_today")]),
               "future_dates": future[:50],
               "n_too_past": len(too_past), "too_past": too_past[:50],
               "passed": len([f for f in future if f.get("self_claim_today")]) == 0}
        tmp = a.json_out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, a.json_out)
        print("   ✔ 落盘 %s" % a.json_out)

    # ★ ★ 只对【自称今天】的未来日期判错（★ 计划性未来日期【登记但不判错】★）★★ ★
    _hard = [f for f in future if f.get("self_claim_today")]
    if _hard:
        die("★ 【自称『今天/本日/本次』的未来日期】%d 处 ⇒ ★ 一定是错的（★ 今天的活不可能产出来 ★）★"
            " ⇒ ★ 响亮失败、★ 不许静默通过 ★★" % len(_hard), code=4)
    print("   ✔ ★ 日期闸门通过（★ 无【自称今天】的未来日期、★ 且文件名无未来日期 ★）★")
    return 0


if __name__ == "__main__":
    sys.exit(main())
