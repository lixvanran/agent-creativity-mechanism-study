# -*- coding: utf-8 -*-
"""★ 重组稿【统一收口闸门】
   --------------------------------------------------------------
   ★★ 目的：把「重组链」上所有检查器串成【一个入口、一个退出码】：
     执行器（reorg_paper.py）→ 核验器（verify_reorg.py）→ 补丁清单检查
     （check_patches.py）→ 三组变异注入（证明检查器能红）。
   ★ 纪律：
     ① 任一项红 ⇒ 整体非零退出（★ 不用"打印了警告就算过"）
     ② 区分【判据红】（rc=2/7）与【脚本崩】（rc=1/其它）⇒ 崩不算通过
     ③ 闸门拦截用专属退出码 7，与脚本崩溃（1）可区分
   用法：python3 check_bundle.py
"""
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# (显示名, 脚本, 期望的最小红点) —— 期望值来自【人写的声明】，不是脚本自己说的
STAGES = [
    ("① 重组执行（生成 + 自检）", "reorg_paper.py", 0),
    ("② 重组稿核验", "verify_reorg.py", 0),
    ("③ 补丁清单独立检查", "check_patches.py", 0),
    ("④ 重组核验器变异注入", "test_reorg_mutations.py", 0),
    ("⑤ 核验器自身变异注入", "test_verify_reorg_mutations.py", 0),
    ("⑥ 补丁清单检查器变异注入", "test_check_patches_mutations.py", 0),
    ("⑦ 闸门自身变异注入（自证）", "test_check_bundle_mutations.py", 0),
]

GATE_RC = 7   # ★ 闸门拦截
CRASH_RC = 1  # ★ 脚本崩溃（1）≠ 判据红


def main():
    results = []
    skipped = []
    for name, script, want_rc in STAGES:
        # ★ fail-fast（★ 本轮实测踩到）：某阶段红 ⇒ 【不再跑下游】——
        #   否则 ① 失败会让 ②⑥ 因缺文件连锁崩 ⇒ 根因被掩盖，
        #   且"崩"与"判据红"无法区分（★ 这就是本轮 M1 期望落空的原因）。
        if skipped:
            skipped.append(name)
            print("[SKIP] %-30s （前序阶段已失败 ⇒ 不跑，避免连锁崩掩盖根因）" % name)
            continue
        path = os.path.join(HERE, script)
        if not os.path.exists(path):
            print("[MISS] %-30s 脚本不存在：%s" % (name, script))
            results.append((name, False, "脚本缺失：%s" % script))
            skipped.append(name)
            continue
        t0 = time.time()
        r = subprocess.run([PY, path], capture_output=True, text=True,
                           cwd=HERE, timeout=900)
        out = (r.stdout or "") + (r.stderr or "")
        dt = time.time() - t0
        ok = (r.returncode == want_rc)
        is_crash = ("Traceback (most recent call last)" in out)
        kind = "崩溃" if is_crash else (
            "判据红" if r.returncode in (2, 7) else "rc=%d" % r.returncode)
        print("[%s] %-30s rc=%-3d (%s) %.1fs" %
              ("PASS" if ok else "FAIL", name, r.returncode, kind, dt))
        if not ok:
            print("      ---- 尾部输出 ----")
            print("      " + out[-900:].replace("\n", "\n      "))
            results.append((name, False, out))
            skipped.append(name)
        else:
            results.append((name, True, out))

    n_ok = sum(1 for _, ok, _ in results if ok)
    print()
    print("★ 重组稿收口闸门：%d/%d 通过" % (n_ok, len(results)))
    if n_ok == len(results):
        print("★ 结论：全部通过（★ 注意：这只证明【机械可判的部分】；"
              "§ 引用语义 / 摘要改写区读数 / 原稿自身错指 仍属人工复核边界）")
        return 0
    # ★★★ 关键修正（★ 本轮实测踩到）：
    #   「崩」的判定必须【按阶段】做，不能按整体输出做 ——
    #   ⇒ ① 主动 SystemExit("✘ 锚点缺失") 是【判据红/主动拒绝】不是崩；
    #   ⇒ 但 ⑥ 里另一个脚本崩了会在【整体输出】里混进 Traceback ⇒ 把 ① 误判成崩。
    #   ⇒ 落法：逐阶段看输出，只把【该阶段自己】的 Traceback 算崩。
    # ★ 只看【第一个失败阶段】的输出判崩（★ 短路后不会再有连锁崩）
    first_bad = next((out for n, ok, out in results if not ok), "")
    crashed = [n for n, ok, out in results
               if not ok and out is first_bad
               and "Traceback (most recent call last)" in out]
    if crashed:
        print("✘ 其中有脚本【崩溃】（不是判据红）：%s" % crashed)
        return CRASH_RC
    print("✘ 闸门拦截：%s" % [n for n, ok, _ in results if not ok])
    return GATE_RC


if __name__ == "__main__":
    sys.exit(main())
