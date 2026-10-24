#!/usr/bin/env python3
"""★ **v6 机制层源码级变异注入（★ 2026-10-25）**

★ **★ 为什么必须是【源码级】★★**：★ 进程内变异（★ v5 那种）只能在【同一份代码】里换行为
★ ⇒ ⇒ ★ 而我们要守的正是【源码文本本身】（★ 口径写错 / 归零写错）⇒ ⇒ ★ 必须改源码再跑
★ ⇒ ⇒ ★ **自检全绿 + 变异被抓住 ⇒ 才是真绿**

★ **★ 纪律**：★ 每条【只有新实现才通过】的断言 ⇒ ⇒ 都要有一条对应的变异
★ ⇒ ⇒ ★ 否则那些断言守不住任何东西（★ 它们可能只是在测一个恰好为真的常量）

★ **用法**：
```bash
python3 -B group4_state_driven/code/mutations_arch6.py
# ★ 期望：全部变异体都【如期失败】⇒ ⇒ exit 0
```
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(_HERE, "workflow_arch6.py")

# ★ ★ ★ 变异清单（★ ★ 锚点必须【逐字】取自当前源码 ⇒ ★ 改源码时这里要同步改 ★ ★ ★）
MUTATIONS = [
    ("m1_target_set6_old_criteria",
     'return {"deep": sorted(st.deep_set()), "drop": sorted(st.drop_set())}',
     'deep, drop = set(), set()\n'
     '    for d in (st.decisions or []):\n'
     '        gi = int(d.get("gap_index") or 0)\n'
     '        if gi <= 0:\n'
     '            continue\n'
     '        if str(d.get("depth") or "").strip() == "放弃":\n'
     '            drop.add(gi)\n'
     '        else:\n'
     '            deep.add(gi)\n'
     '    return {"deep": sorted(deep), "drop": sorted(drop)}',
     "★ target_set6 回到旧口径（★ '点到为止'被算进 deep ⇒ ⇒ 与打分器漂移）"),

    ("m2_none_silently_zeroed",
     '            sc.append(None)\n        else:\n            sc.append(float(v))',
     '            sc.append(0.0)\n        else:\n            sc.append(float(v))',
     "★ align=None 被静默归零（★ 违反「不静默归零」）"),

    ("m3_align_fallback_zero",
     '"align": round(_al, 4) if _al is not None else None,',
     '"align": round(_al or 0.0, 4),',
     "★ 全部候选不可打分时 align 回退成 0.0（★ 伪装成内容层 0）"),

    ("m4_none_competes_as_zero",
     '    order_key = [(1 if x is None else 0, 0.0 if x is None else -x, i)\n'
     '                 for i, x in enumerate(sc)]',
     '    order_key = [(0, -(0.0 if x is None else x), i)\n'
     '                 for i, x in enumerate(sc)]',
     "★ 不可打分者【参与竞争】并被当成 0 分（★ 而不是排到最后）"),
]


def run_selfcheck(src_path: str) -> tuple:
    """跑一次自检 ⇒ 返回 (exit_code, stdout)"""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run([sys.executable, "-B", src_path],
                       capture_output=True, text=True, env=env,
                       cwd=os.path.dirname(os.path.abspath(src_path)))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    if not os.path.exists(TARGET):
        print("✘ 找不到 %s" % TARGET)
        return 2
    src = open(TARGET, encoding="utf-8").read()

    # ── 前提：原版必须全绿（★ 否则测的是坏了的东西）──
    rc, out = run_selfcheck(TARGET)
    if rc != 0:
        print("✘ 原版自检【不是全绿】⇒ 退出码 %d ⇒ 先修好原版再测变异" % rc)
        print(out[-2000:])
        return 2
    print("★ 前提：原版自检全绿 ✔")

    tmpdir = tempfile.mkdtemp(prefix="v6mut_")
    results = []
    try:
        for name, old, new, desc in MUTATIONS:
            cnt = src.count(old)
            if cnt != 1:
                print("✘ %s：锚点命中 %d 次（★ 期望 1）⇒ ★ 变异体构造失败 ⇒ 源码已变" % (name, cnt))
                results.append((name, False, "锚点命中 %d 次" % cnt))
                continue
            mutated = src.replace(old, new, 1)
            # ★★★ 关键修正（★ 2026-10-25）：★ 变异体【必须与原文件同目录】
            #   ⇒ ⇒ 否则 `import workflow_arch5` 会 ModuleNotFoundError
            #   ⇒ ⇒ 而那个异常【也会让退出码非零】⇒ ⇒ ★ 于是"变异体没被真正测到"
            #   ⇒ ⇒ ★ 却被报成"如期失败"⇒ ⇒ ★ ★ 假绿 ★★
            #   ⇒ ⇒ ★ 修法：把【整个 code 目录】拷到 tmpdir，★ 在副本里改
            d = os.path.join(tmpdir, name)
            shutil.copytree(_HERE, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            path = os.path.join(d, "workflow_arch6.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write(mutated)
            rc, out = run_selfcheck(path)
            bad = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("✘")]
            # ★★★ 【必须抓到断言失败行】才算数 ★★★
            #   ⇒ ⇒ 崩溃 / 异常【不算】"如期失败"（★ 那说明变异体根本没跑到断言）
            if rc == 0:
                print("✘ %s：★ 变异体竟然通过了 ⇒ ⇒ 这条断言【没在测东西】" % name)
                results.append((name, False, "变异体未失败"))
                continue
            if not bad:
                tail = [ln.strip() for ln in out.strip().splitlines()[-3:] if ln.strip()]
                print("✘ %s：★ 变异体是【崩溃】而非【断言失败】⇒ ⇒ ★ 没真正测到那条断言：%s"
                      % (name, " / ".join(tail)[:120]))
                results.append((name, False, "崩溃而非断言失败"))
                continue
            detail = bad[0][:150]
            print("  ✔ %-32s ⇒ 如期失败：%s" % (name, detail))
            results.append((name, True, detail))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    n_ok = sum(1 for _, ok, _ in results if ok)
    print("-" * 70)
    print("★ 变异注入自检：%d/%d 项全部如期失败 ⇒ ⇒ 测试是活的" % (n_ok, len(results)))
    for name, ok, detail in results:
        if not ok:
            print("   ✘ %s：%s" % (name, detail))
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
