#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **rev3 变异注入自测（★ 证明 rev3 的断言【真在测东西】）**

★ 纪律：**每个断言都必须能失败** ⇒ ⇒ ★ 否则它就是假绿。
★ ⇒ 本文件对 `state_layer.detect_tie` 注入变异，★ 跑【第二组的测试文件】，★ 看它【是否报失败】。

★ 变异清单（★ 每条对应 rev3 的一处语义）：
★ m1 · tol 变回死参数（★ 按 round(v,12) 分组）⇒ ⇒ ★ 须被 rev3 ② 或 ⑦ 抓住
★ m2 · tol 忽略（★ 恒按 1e-9）⇒ ⇒ ★ 须被 rev3 ② 抓住
★ m3 · 传递闭包改成【只比首元素】（★ 非传递）⇒ ⇒ ★ 须被 rev3 ③ 或 ④ 抓住
★ m4 · 去掉 tol 必填（★ 恢复默认值）⇒ ⇒ ★ 须被 rev3 ⑤ 抓住
★ m5 · 去掉 keyword-only（★ 恢复位置传参）⇒ ⇒ ★ 须被 rev3 ⑥ 抓住
★ m6 · members 顺序改成按分值降序 ⇒ ⇒ ★ 须被 rev3 ⑧ 抓住
★ m7 · 只查最大簇（★ 回 rev1 语义）⇒ ⇒ ★ 须被「中位并列」那条抓住
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SL = os.path.join(ROOT, "creativity_lab", "state_layer.py")
TEST = os.path.join(ROOT, "creativity_lab", "experiments", "test_state_layer.py")

ORIG = open(SL, encoding="utf-8").read()

# ★ (名字, 旧片段, 新片段) —— ★ 每个旧片段必须【唯一命中】⇒ ⇒ ★ 否则报"变异没发生"
MUTS = [
    ("m1_tol_dead_param",
     "        if float(scores[i]) - float(scores[cur[-1]]) <= tol:",
     "        if round(float(scores[i]), 12) == round(float(scores[cur[-1]]), 12):"),
    ("m2_tol_ignored",
     "        if float(scores[i]) - float(scores[cur[-1]]) <= tol:",
     "        if float(scores[i]) - float(scores[cur[-1]]) <= 1e-9:"),
    ("m3_not_transitive",
     "        if float(scores[i]) - float(scores[cur[-1]]) <= tol:",
     "        if float(scores[i]) - float(scores[cur[0]]) <= tol:"),
    ("m4_tol_optional",
     "def detect_tie(scores: List[float], *, tol: float) -> List[Dict[str, Any]]:",
     "def detect_tie(scores: List[float], tol: float = 1e-9) -> List[Dict[str, Any]]:"),
    ("m5_positional_ok",
     "def detect_tie(scores: List[float], *, tol: float) -> List[Dict[str, Any]]:",
     "def detect_tie(scores: List[float], tol: float) -> List[Dict[str, Any]]:"),
    ("m6_members_desc",
     "        g_asc = sorted(g)",
     "        g_asc = sorted(g, key=lambda i: float(scores[i]), reverse=True)"),
    ("m7_only_max_cluster",
     "    groups.append(cur)\n    out: List[Dict[str, Any]] = []",
     "    groups.append(cur)\n    groups = [max(groups, key=lambda gg: max(float(scores[i]) for i in gg))]\n    out: List[Dict[str, Any]] = []"),
]


def run_tests(root: str) -> tuple[int, str]:
    p = subprocess.run([sys.executable, "-B", os.path.join(root, "creativity_lab", "experiments", "test_state_layer.py")],
                       capture_output=True, text=True, cwd=root)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="rev3_mut_")
    try:
        # ★ 先在【干净副本】上确认基线全绿（★ 否则失败无意义）
        os.makedirs(os.path.join(tmp, "creativity_lab", "experiments"), exist_ok=True)
        shutil.copy(SL, os.path.join(tmp, "creativity_lab", "state_layer.py"))
        shutil.copy(TEST, os.path.join(tmp, "creativity_lab", "experiments", "test_state_layer.py"))
        rc, out = run_tests(tmp)
        if rc != 0:
            print("✘ 基线就不绿（★ 变异测试无意义）:\n%s" % out[-1500:])
            return 1
        print("✔ 基线全绿（★ exit 0）")

        failed = []
        for name, old, new in MUTS:
            n = ORIG.count(old)
            if n != 1:
                print("  ✘ %-22s ★ 变异【没发生】（★ 锚点命中 %d 次，★ 应为 1）" % (name, n))
                failed.append(name)
                continue
            mutated = ORIG.replace(old, new, 1)
            assert mutated != ORIG, "★ 变异没改变内容"
            open(os.path.join(tmp, "creativity_lab", "state_layer.py"), "w", encoding="utf-8").write(mutated)
            rc, out = run_tests(tmp)
            if rc != 0:
                caught = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("✘")]
                print("  ✔ %-22s ★ 被抓住（★ exit %d）｜ ★ %s" % (name, rc, (caught[0][:70] if caught else "")))
            else:
                print("  ✘ %-22s ★ ★ 没被抓到（★ 假绿！）" % name)
                failed.append(name)
            open(os.path.join(tmp, "creativity_lab", "state_layer.py"), "w", encoding="utf-8").write(ORIG)

        print()
        if failed:
            print("✘ 变异注入：★ %d/%d 未被抓住 ⇒ %s" % (len(failed), len(MUTS), failed))
            return 1
        print("✔ 变异注入：★ %d/%d 全部被抓住（★ 断言是活的）" % (len(MUTS), len(MUTS)))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
