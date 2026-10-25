# -*- coding: utf-8 -*-
"""★ 观测：每个变异实际让【哪些检查】变红（用于登记"预期红的那一处"）

★ 为什么先观测再登记：★ 变异注入的判据必须**点名预期的那一处**（第二组 2026-10-24 的教训：
  "有红就行"只证明"脚本某处会红"，不证明"我测的那一处被测到了"）。
  ⇒ ⇒ 但"预期"不能靠猜 ⇒ ⇒ ⇒ 先跑出【实际失败集合】，再据此登记预期，最后用强判据强制。
★ 本脚本只观测，不改判据。
"""
import importlib
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import test_metrics_priorart as T   # noqa: E402

MUT = T.MUTATIONS
ALL_CHECKS = []
_orig = T.run_checks
for _c in _orig():
    ALL_CHECKS.append(_c.name)

print("全部检查（%d 个）：%s" % (len(ALL_CHECKS), ", ".join(ALL_CHECKS)))
print("=" * 78)
for label, fname, old, new in MUT:
    tmp = tempfile.mkdtemp(prefix="obs_")
    try:
        for fn in os.listdir(HERE):
            if fn.endswith(".py"):
                shutil.copy2(os.path.join(HERE, fn), os.path.join(tmp, fn))
        src = io.open(os.path.join(tmp, fname), encoding="utf-8").read()
        if old not in src:
            print("  ✘ %-34s 锚点找不到" % label)
            continue
        io.open(os.path.join(tmp, fname), "w", encoding="utf-8").write(src.replace(old, new, 1))
        for mod in list(sys.modules):
            if mod == "metrics_priorart":
                del sys.modules[mod]
        sys.path.insert(0, tmp)
        saved = T.MP
        try:
            T.MP = importlib.import_module("metrics_priorart")
            failed = [c.name for c in T.run_checks() if not c.ok]
        finally:
            T.MP = saved
            sys.path.remove(tmp)
            if "metrics_priorart" in sys.modules:
                del sys.modules["metrics_priorart"]
            sys.path.insert(0, HERE)
        print("  %-34s ⇒ 实际变红：%s" % (label, ", ".join(failed) if failed else "（无！）"))
    except Exception as e:
        print("  %-34s ⇒ 崩溃：%s: %s" % (label, type(e).__name__, e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
