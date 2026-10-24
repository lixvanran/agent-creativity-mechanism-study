#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 窗口感知续跑：★ 等 chat 窗口复位 → 实测通不通 → 通了才续跑 ★

> 落点：`creativity_lab/experiments/resume_after_window.py`
> 用法：
>   python3 -B creativity_lab/experiments/resume_after_window.py \
>       --run-dir runs/topo-arm-v2-2026-10-25 \
>       --cmd "python3 -u -B creativity_lab/experiments/topo_arm.py --out ... --topics S4,S5,S6,T1,T2,T3 --reps 2 --runs-per-arm 5 --seed 20261025 --health-every 300 --min-health 0.80"
>
> ★ **为什么要有这个脚本（★ 2026-10-26 限流事件逼出来的 ★）** ★
★ chat 通道是【5 小时滚动窗口】限额 ⇒ ★ 窗口未复位就重启 ⇒ ★ 每单元 13 次调用全 429
★ ⇒ ★ **白烧配额、还产出一堆空单元** ★ ⇒ ★ 第 1 层论证线的建议是「先别重启」★
★ ⇒ ★ 本脚本把这条建议**自动化**：★ 等窗口 → **实测** → 通了才续跑 ★
★
★ ★ **三条硬纪律（★ 本脚本自己也要守 ★）★★
★ ① **实测，不猜**：★ 窗口复位时刻从配额接口读；★ 通不通用单条调用测 ⇒ ★ **两者都实测 ★**
★ ② **不通就不跑**：★ 测不通 ⇒ ★ 退出码 2 + 打印原因 ⇒ ★ **绝不「试一下看看」★★**
★ ③ **续跑必须用同一条命令**：★ 已落盘单元自动 skip ⇒ ★ **不产生重跑、不产生重复键 ★**

"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from creativity_lab.experiments.channel_status import check_chat, check_quota  # noqa: E402


def wait_until(window_end_utc: str, poll_s: int, max_wait_s: int):
    """★ 等到窗口结束（★ 从配额接口读到的时刻 ★）⇒ ★ 不是拍脑袋的 sleep ★"""
    end = dt.datetime.strptime(window_end_utc, "%Y-%m-%dT%H:%M:%SZ")
    t0 = time.time()
    while True:
        left = (end - dt.datetime.utcnow()).total_seconds()
        if left <= 0:
            return True
        if time.time() - t0 > max_wait_s:
            return False
        print("   … 等窗口：剩 %d 秒" % int(left), flush=True)
        time.sleep(min(poll_s, max(1, int(left))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--cmd", required=True, help="★ 续跑用的【原命令】★")
    ap.add_argument("--poll", type=int, default=60)
    ap.add_argument("--max-wait", type=int, default=9000)
    ap.add_argument("--no-wait", action="store_true", help="★ 不等窗口，★ 直接测 ★")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    print("== ① 配额（★ 实测 ★）==")
    q = check_quota()
    gen = None
    if q.get("ok"):
        for m in q["models"]:
            if m["model_name"] == "general":
                gen = m
        print("   窗口 %s → %s ｜ 剩 %s 分 ｜ status=%s ｜ 本周剩 %s h"
              % (gen["interval_start_utc"], gen["interval_end_utc"],
                 gen["interval_remains_min"], gen["interval_status"], gen["weekly_remains_hours"]))
    else:
        print("   读不到配额：%s" % q.get("err"))

    if gen and gen.get("current_interval_status") == 2 and not a.no_wait:
        print("== ② 等窗口复位（★ 到 %s ★）==" % gen["interval_end_utc"])
        if not wait_until(gen["interval_end_utc"], a.poll, a.max_wait):
            print("   ✘ 等超时 ⇒ 不续跑 ⇒ 退出码 2")
            return 2
        print("   ✔ 窗口时间已到")
    else:
        print("== ② 跳过等待（★ 当前 status=%s ★）==" % (gen.get("current_interval_status") if gen else "?"))

    print("== ③ 实测 chat（★ 不通就不跑 ★）==")
    c = check_chat()
    if not c.get("ok"):
        print("   ✘ chat 仍不通：HTTP %s ｜ %s" % (c.get("http"), c.get("msg")))
        print("   ⇒ ★ 不续跑（★ 续跑只会白烧 ★）⇒ 退出码 2")
        return 2
    print("   ✔ chat 通")

    if a.dry_run:
        print("== ④ --dry-run ⇒ 到此为止（★ 命令：%s ★）" % a.cmd)
        return 0

    print("== ④ 续跑（原命令，★ 已落盘单元自动 skip ★）==")
    r = subprocess.run(a.cmd, shell=True, cwd=ROOT)
    print("== ⑤ 续跑结束：exit %d ==" % r.returncode)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
