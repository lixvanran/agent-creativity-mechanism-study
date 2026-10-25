#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批进度巡检（★ 2026-10-25 新增）

★ 为什么有这个工具（★ 它的存在理由就是今天栽的两个坑）：
★ ① 「日志长时间没新行」≠「进程死了」——★ 单元级日志是【单元跑完才打】⇒ ⇒ 单元中途【必然】无输出
★ ② ★★ 进程探测的匹配模式【可能整个失效】⇒ ⇒ ★ 空输出会被误读成"干净了"
★    ⇒ 本工具的进程探测【必须先自证模式有效】（★ 命中数 > 0 才算可信）
★    ⇒ 两种失效形态（★ 今天各栽一次）：
★       - `ps -eo pid,etime,args` + `^ *[0-9]+ python3` ⇒ ★ etime 插在中间 ⇒ ★ 失效
★       - `ps -eo pid,args` + `$4 ~ /topo_arm/` ⇒ ★ $4 是 "-B" 不是脚本名 ⇒ ★ 失效

★ 用法：
★   python3 -B creativity_lab/experiments/check_batch_progress.py --run-dir runs/topo-arm-v2-2026-10-25
★   python3 -B ... --run-dir <dir> --expect-units 360 --expect-calls 3540 --script topo_arm.py
★
★ 退出码（★ 必须有意义，★ 便于外部判断）：
★   0 = 已完成（单元数达标）｜★ 或 正常在跑（进程活着且单元数 < 目标）
★   3 = ★★ 进程【不在】且单元数未达标 ⇒ ★ 【已死，须续跑】★★
★   4 = 数据异常（坏文件 / 重名 / n_calls 规格不符）
★   5 = 目录不存在
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

# ★ 6 臂每 run 的调用数规格（★ 与 topo_arm.py 的预注册一致）
CALLS_PER_RUN = {
    "nosel_b3_synth": 4,
    "nosel_b3": 3,
    "topo_gs_homo": 13,
    "topo_ngt_homo": 13,
    "topo_sg_homo": 13,
    "topo_ngt_hetero": 13,
}
FNAME_RE = re.compile(r"^(?P<topic>.+)_r(?P<rep>\d+)_(?P<arm>.+)_u(?P<run>\d+)\.json$")


def probe_process(script_name: str) -> tuple[list[int], bool]:
    """★ 返回 (PIDs, 模式是否可信)

    ★ 【关键】模式可信 = 命中数 > 0 OR 【能证明脚本确实不在跑】。
    ★ 不能用"空输出"直接断言"没进程"⇒ ★ 那正是今天栽的坑。
    """
    # ★★ 模式构造（★ 2026-10-25 修：★ 原写法把 ".py" 拼了两次 ⇒ ⇒ pat 变成
    # ★★ `[t]opo_arm.py\.py` ⇒ ⇒ 【永远不匹配】⇒ ⇒ 工具自己假绿了一次）
    # ★⇒⇒ 铁律：★ 模式只用【脚本名主干】+ 方括号技巧，★ 绝不再拼后缀
    stem = script_name[:-3] if script_name.endswith(".py") else script_name
    pat = re.compile(r"[" + stem[0] + r"]" + stem[1:] + r"(\.py)?\b")
    # ★★★ 【★ 2026-10-25 第二次修 ★】★★
    # ★ 方括号技巧只挡"正则源码里那个串"，★ ★ 挡不住"命令行里恰好提到脚本名字面量"的其他进程 ★
    # ★ ⇒ 今天的实测：★ 父 shell（comm=bash）的命令行里含 "--script topo_arm.py" ⇒ ⇒ 被误当成批进程
    # ★ ⇒ ★★ 正解 = 加【进程类型约束】：★ 只认 comm == "python3" ⇒ ★ bash/awk/grep 天然排除 ★★
    out = subprocess.run(
        ["ps", "-eo", "pid,comm,args"], capture_output=True, text=True, check=False
    ).stdout
    pids, n_matched = [], 0
    my_pid = os.getpid()
    for ln in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(\S+)\s+(.*)", ln)
        if not m:
            continue
        pid, comm, rest = int(m.group(1)), m.group(2), m.group(3)
        if comm != "python3":        # ★★ 进程类型约束 ★★
            continue
        if not pat.search(rest):
            continue
        n_matched += 1
        pids.append(pid)
    # ★★★ 第二套独立模式（★ 只用于【交叉提示】，★ ★ 【绝不参与 trusted 判定】）
    # ★★★ ⇒★ 理由：★ 用另一套模式做"可信"判据 = ★【用一个错模式掩盖另一个错模式】★★
    alt_n = sum(1 for ln in out.splitlines() if script_name in ln and "ps -eo" not in ln)
    # ★★ 可信 = 【同一个正则】命中过 ⇒ ★ 命中 0 ⇒ 只能说"没匹配到"，★ 不能说"没进程"
    trusted = n_matched > 0
    # ★★ 组合指纹：★ pids 空但 n_matched > 0 ⇒ ★ 说明【解析环节】坏了 ⇒ ★ 不可信
    if n_matched > 0 and not pids:
        trusted = False
    # ★★ 自匹配检查：★ 绝不能把自己的父 shell / 自身算成批进程
    pids = [p for p in pids if p != my_pid]
    return pids, trusted


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--script", default="topo_arm.py")
    ap.add_argument("--expect-units", type=int, default=0)
    ap.add_argument("--expect-calls", type=int, default=0)
    args = ap.parse_args()

    D = args.run_dir
    if not os.path.isdir(D):
        print("✘ 目录不存在：%s" % D)
        return 5
    ud = os.path.join(D, "units")
    fs = sorted(glob.glob(os.path.join(ud, "*.json"))) if os.path.isdir(ud) else []

    bad, names = [], Counter()
    calls = fails = 0
    per_arm = defaultdict(lambda: Counter())
    problems = []
    for f in fs:
        b = os.path.basename(f)
        names[b] += 1
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception as e:  # ★ 坏文件必须显式报出，★ 不能静默跳过
            bad.append((b, str(e)))
            continue
        calls += int(d.get("n_calls", 0))
        fails += int(d.get("n_failed", 0))
        m = FNAME_RE.match(b)
        if not m:
            problems.append((b, "文件名不符合 `<题>_r<rep>_<臂>_u<run>.json`"))
            continue
        arm = m.group("arm")
        per_arm[arm][(m.group("topic"), int(m.group("rep")))] += 1
        exp = CALLS_PER_RUN.get(arm)
        if exp is not None and int(d.get("n_calls", 0)) != exp:
            problems.append((b, "n_calls=%s ≠ 规格 %s" % (d.get("n_calls"), exp)))

    dup = [k for k, v in names.items() if v > 1]
    pids, trusted = probe_process(args.script)

    print("═══ 批进度：%s ═══" % D)
    print("  单元 %s ｜ 调用 %s ｜ 失败 %d ｜ 坏文件 %d ｜ 重名 %d" % (
        "%d/%d" % (len(fs), args.expect_units) if args.expect_units else len(fs),
        "%d/%d" % (calls, args.expect_calls) if args.expect_calls else calls,
        fails, len(bad), len(dup)))
    if per_arm:
        print("  每臂（题,rep → 已跑 run 数）：")
        for arm in sorted(per_arm):
            cells = ["%s r%d:%d" % (t, r, c) for (t, r), c in sorted(per_arm[arm].items())]
            print("    %-16s %s" % (arm, "  ".join(cells)))
    print("  进程：%s ｜ 模式可信=%s" % (pids if pids else "无", "是" if trusted else "★否（★ 空输出不可当'已停'）"))
    if bad:
        print("  ⚠ 坏文件：%s" % bad[:5])
    if dup:
        print("  ⚠ 重名：%s" % dup[:5])
    if problems:
        print("  ⚠ 规格问题：%s" % problems[:5])

    if bad or dup or problems:
        print("  ⇒ 判定：✘ 数据异常")
        return 4
    if args.expect_units and len(fs) >= args.expect_units:
        print("  ⇒ 判定：✔ 已完成")
        return 0
    if pids:
        print("  ⇒ 判定：✔ 正常在跑（★ 续跑只补缺口）")
        return 0
    if not trusted:
        print("  ⇒ 判定：★★ 进程探测【不可信】⇒ ★ 不能断言'已停'⇒ ★ 请用 ps -p <已知PID> 复核")
        return 3
    print("  ⇒ 判定：★★ 进程【不在】且单元数未达标 ⇒ ★ 【已死，须用同一条命令续跑】")
    return 3


if __name__ == "__main__":
    sys.exit(main())
