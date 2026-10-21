# -*- coding: utf-8 -*-
"""`noise_floor.py` 的**跨判官版本 δ** 与**硬闸门**自检（2026-10-22 新增）。

## 为什么需要这个文件

`OPTIMIZER-NOTES.md` 自报 `δ_judge=0(n=45) "MAD 退化"`，却仍拿 `δ*=0.3481` 当
「增益 > δ ⇒ 可信」的门槛。**逻辑是断的**：

* 判官跑 `temperature=0` ⇒ **同一 `measure_version` 内判定是确定性的**
  ⇒ 「只换判官种子」的 δ_judge **恒为 0**（**定义造成的，不是仪器稳**）
* 而我们真实栽的跟头是**跨 `measure_version` 的漂移**
  （U1 实测：v1→v2 净增益 `0/+1/−1` → `+1/+4/0`）
⇒ 用一个恒为 0 的地板当门槛 ⇒ **任何非零增益都会被判为可信**。

⇒ 本文件验证三件事：
  1. `judge_variants` 能算出 `δ_judge_version`（跨判官版本/跨判官模型）
  2. **硬闸门**：种子地板退化且无 `judge_variants` ⇒ `optimization_allowed=False`
  3. 可信门槛 = `max(δ_total, δ_judge_version)` ⇒ **判官侧漂移不会被漏掉**

## 变异注入（自证有效）

* **变异①** 去掉硬闸门（`judge_noise_usable` 恒为 True）⇒ 检查 2 必须 FAIL
* **变异②** 可信门槛忽略 `δ_judge_version` ⇒ 检查 3 必须 FAIL
* **变异③** `_measure_with_variant` 静默退回同版本测量（吞掉 TypeError）⇒ 检查 4 必须 FAIL

## 纪律

* 本文件用**本地合成执行体**，**不调用任何模型 API** ⇒ 数字是合成的，**只验证机制**。
* 失败必须能被计数：不允许"跑通"等于"判通过"。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as CFG          # noqa: E402
import noise_floor as NF     # noqa: E402

DEV = "/workspace/lab/routes/DEV"


# --------------------------------------------------------------------------
# 合成执行体
# --------------------------------------------------------------------------
class VariantRunner:
    """支持 `variant` 关键字的合成执行体。

    读数规则（**刻意让不同变体给出不同读数**，用来验证 δ_judge_version 真的被算出来）：
      * variant 缺省 → 读数恒定（模拟 temperature=0 的确定性）
      * variant 给出 `bias` → 读数 = 基数 + bias（模拟跨版本漂移）
    """

    def __init__(self, tasks, *, base=2, variant_bias=None, accept_variant=True):
        self.tasks = tasks
        self.base = base
        self.variant_bias = variant_bias or {}
        self.accept_variant = accept_variant
        self.calls = []

    def generate(self, task, cfg, seed=0):
        self.calls.append(("generate", task.get("task_id"), seed))
        return {"text": "合成答案", "cost": {"calls": 1, "tokens": 100}}

    def measure(self, task, ans, seed=0, variant=None):
        if variant is not None and not self.accept_variant:
            raise TypeError("measure() got an unexpected keyword argument 'variant'")
        self.calls.append(("measure", task.get("task_id"), seed,
                           (variant or {}).get("label")))
        n = self.base + self.variant_bias.get((variant or {}).get("label"), 0)
        # ★ 卡片形状要**真实**：一张卡 = 一个结论组（生产里 `family_key` 按结论集合归并）
        #   若一张卡塞多个结论 ⇒ `vd_final` 恒为 1 ⇒ 变体差异被抹平（这正是首版测试的 bug）
        cards = [{
            "card_id": "c%d" % i,
            "verify_status": "supported",
            "load_bearing": True,
            "stage": "final",
            "supports_conclusions": ["k%d" % i],
        } for i in range(n)]
        return {"cards": cards, "cost": {"calls": 1, "tokens": 50}}


class NoVariantRunner(VariantRunner):
    """不支持 `variant` 的执行体（模拟真实 runner 还没接线）。"""

    def __init__(self, tasks, **kw):
        super().__init__(tasks, **kw)
        self.accept_variant = False


# --------------------------------------------------------------------------
# 检查框架
# --------------------------------------------------------------------------
class Check:
    def __init__(self, name):
        self.name = name
        self.ok = False
        self.detail = ""
        self.error = None


def _load_tasks():
    with open(os.path.join(DEV, "devset.json"), encoding="utf-8") as f:
        d = json.load(f)
    tasks = d["tasks"] if isinstance(d, dict) and "tasks" in d else d
    return tasks[:3]                      # 3 题足够，成本低


def _base_cfg(route="C"):
    return CFG.make_config(route)


def run_checks():
    checks = []

    def add(name, fn):
        c = Check(name)
        try:
            c.ok, c.detail = fn()
        except Exception as e:            # 失败必须能被看见
            c.ok = False
            c.error = "%s: %s" % (type(e).__name__, e)
        checks.append(c)
        return c

    tasks = _load_tasks()
    cfg = _base_cfg()
    variants = [{"label": "judge-v1", "bias": 0},
                {"label": "judge-v2", "bias": 3},
                {"label": "judge-v3", "bias": -2}]

    # 1) δ_judge_version 被算出来，且随变体变化
    def c1():
        r = VariantRunner(tasks, base=2, variant_bias={"judge-v1": 0, "judge-v2": 3, "judge-v3": -2})
        nf = NF.estimate_noise_floor(tasks, r, route="C", base_cfg=cfg, ref_cfg=cfg,
                                     r_meas=3, n_seeds=2, judge_variants=variants)
        djv = nf.get("delta_judge_version")
        if not djv:
            return False, "delta_judge_version 为空"
        if djv.get("n_variants") != 3:
            return False, "n_variants=%r，应为 3" % (djv.get("n_variants"),)
        if djv.get("value", 0) <= 0:
            return False, "δ_judge_version=%r，应 >0（变体读数不同）" % (djv.get("value"),)
        return True, "δ_judge_version=%.4f (n_variants=%d, n_samples=%d)" % (
            djv["value"], djv["n_variants"], djv["n_samples"])

    # 2) ★ 硬闸门：种子地板退化（temp=0 确定性）且无 judge_variants ⇒ 不允许优化
    def c2():
        r = VariantRunner(tasks, base=2)          # 变体缺省 ⇒ 读数恒定 ⇒ 种子地板退化
        nf = NF.estimate_noise_floor(tasks, r, route="C", base_cfg=cfg, ref_cfg=cfg,
                                     r_meas=3, n_seeds=2)
        if not nf.get("judge_noise_degenerate"):
            return False, "种子地板未被标记为退化（应退化的场景）"
        if nf.get("optimization_allowed"):
            return False, "★ 退化且无 judge_variants 却允许优化 ⇒ 闸门失效"
        v = nf.get("verdict") or ""
        if "退化" not in v:
            return False, "判决未说明退化原因：%s" % v[:80]
        return True, "退化被抓住，optimization_allowed=False"

    # 3) 可信门槛必须覆盖 δ_judge_version
    def c3():
        r = VariantRunner(tasks, base=2, variant_bias={"judge-v1": 0, "judge-v2": 3, "judge-v3": -2})
        nf = NF.estimate_noise_floor(tasks, r, route="C", base_cfg=cfg, ref_cfg=cfg,
                                     r_meas=3, n_seeds=2, judge_variants=variants)
        cred = nf.get("threshold_delta_credible")
        djv = nf.get("delta_judge_version") or {}
        djv_thr = max(djv.get("value", 0.0), djv.get("mean_abs_dev", 0.0))
        if cred is None:
            return False, "缺 threshold_delta_credible"
        if cred + 1e-9 < djv_thr:
            return False, "★ 可信门槛 %.6f < δ_judge_version 门槛 %.6f ⇒ 判官侧漂移被漏掉" % (
                cred, djv_thr)
        if abs(cred - max(nf["threshold_delta"], djv_thr)) > 1e-9:
            return False, "可信门槛 %.6f 不是 max(δ_total, δ_judge_version)=%.6f" % (
                cred, max(nf["threshold_delta"], djv_thr))
        return True, "threshold_delta_credible=%.4f ≥ δ_judge_version 门槛 %.4f" % (cred, djv_thr)

    # 4) runner 不支持 variant ⇒ 显式报错，不许静默退回同版本
    def c4():
        r = NoVariantRunner(tasks, base=2)
        try:
            NF.estimate_noise_floor(tasks, r, route="C", base_cfg=cfg, ref_cfg=cfg,
                                     r_meas=2, n_seeds=1, judge_variants=variants)
        except RuntimeError as e:
            if "variant" in str(e):
                return True, "显式报错（未被静默吞掉）：%s" % str(e)[:70]
            return False, "报错了但原因不对：%s" % str(e)[:70]
        except Exception as e:
            return False, "抛的是 %s，应为 RuntimeError" % type(e).__name__
        return False, "★ runner 不支持 variant 时竟未报错 ⇒ 静默退回同版本测量"

    add("delta_judge_version_is_computed", c1)
    add("hard_gate_blocks_degenerate_judge_noise", c2)
    add("credible_threshold_covers_judge_version", c3)
    add("unsupported_variant_raises_not_silent", c4)
    return checks


# --------------------------------------------------------------------------
# 变异注入
# --------------------------------------------------------------------------
MUTATIONS = [
    ("移除硬闸门（judge_noise_usable 恒 True）", "noise_floor.py",
     "judge_noise_usable = (not judge_noise_degenerate) or (delta_judge_version is not None)",
     "judge_noise_usable = True"),

    ("可信门槛忽略 delta_judge_version", "noise_floor.py",
     """    threshold_delta_credible = threshold_delta
    if delta_judge_version is not None:
        threshold_delta_credible = max(threshold_delta,
                                       delta_judge_version["value"],
                                       delta_judge_version["mean_abs_dev"])""",
     "    threshold_delta_credible = threshold_delta"),

    ("静默吞掉 variant 不支持的 TypeError", "noise_floor.py",
     """    try:
        return runner.measure(task, ans, seed=seed, variant=variant)
    except TypeError as e:
        raise RuntimeError(
            "runner.measure 不接受 variant 关键字，无法测跨判官版本的 δ_judge_version。"
            "（不支持 ⇒ 不许静默退回同版本测量）原始错误：%s" % e)""",
     """    try:
        return runner.measure(task, ans, seed=seed, variant=variant)
    except TypeError:
        return runner.measure(task, ans, seed=seed)"""),
]


def apply_mutation(src, old, new):
    if old not in src:
        raise RuntimeError("变异锚点找不到（源码已变？）")
    return src.replace(old, new, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutate", action="store_true", help="跑变异注入自检")
    args = ap.parse_args()

    print("=" * 72)
    print("noise_floor 跨判官版本 δ + 硬闸门 · 自检")
    print("=" * 72)

    if not args.mutate:
        checks = run_checks()
        npass = sum(1 for c in checks if c.ok)
        for c in checks:
            print("  %s %-46s %s" % ("✔" if c.ok else "✘", c.name, c.detail or ""))
            if c.error:
                print("      ↳ %s" % c.error)
        print("-" * 72)
        print("正常模式：%d/%d 通过" % (npass, len(checks)))
        return 0 if npass == len(checks) else 1

    # ── 变异注入
    # ★★★ 前置纪律：**基线必须全过**，否则「变异被抓住」可能只是抓住了**预存在的失败**
    #   （首版就栽在这：基线 3/4 过，变异报「3/3 全被抓住」，
    #     失败的全是那条本来就失败的检查 ⇒ **假阳性**）。
    here = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(here, "noise_floor.py")
    with open(src_path, encoding="utf-8") as f:
        original = f.read()

    baseline = run_checks()
    baseline_failed = [c.name for c in baseline if not c.ok]
    if baseline_failed:
        print("  ✘ ★★ **基线本身有失败** ⇒ 变异自检无意义（会假阳性）")
        for c in baseline:
            if not c.ok:
                print("      ↳ %s：%s %s" % (c.name, c.detail or "", c.error or ""))
        print("=" * 72)
        print("变异注入：**无效**（基线未通过）")
        print("=" * 72)
        return 1
    print("  ✔ 基线全过（%d/%d）⇒ 变异自检有效"
          % (len(baseline), len(baseline)))
    print("-" * 72)

    all_caught = True
    caught_n = 0
    for label, fname, old, new in MUTATIONS:
        tmp = tempfile.mkdtemp(prefix="nf_mut_")
        try:
            for fn in os.listdir(here):
                if fn.endswith(".py"):
                    shutil.copy2(os.path.join(here, fn), os.path.join(tmp, fn))
            mutated = apply_mutation(original, old, new)
            with open(os.path.join(tmp, fname), "w", encoding="utf-8") as f:
                f.write(mutated)
            # ★★★ 关键：删 sys.modules **不够** —— `run_checks()` 用的是模块顶层绑定的 `NF`，
            #   不重绑它 ⇒ **变异根本没生效** ⇒ 变异自检永远是假阳性。
            for mod in list(sys.modules):
                if mod in ("noise_floor", "config", "optimizer", "credit", "params"):
                    del sys.modules[mod]
            sys.path.insert(0, tmp)
            saved_nf = NF
            try:
                import importlib
                globals()["NF"] = importlib.import_module("noise_floor")
                checks = run_checks()
                failed = [c.name for c in checks if not c.ok]
            finally:
                globals()["NF"] = saved_nf
                sys.path.remove(tmp)
                for mod in list(sys.modules):
                    if mod in ("noise_floor", "config", "optimizer", "credit", "params"):
                        del sys.modules[mod]
                sys.path.insert(0, here)
            if failed:
                caught_n += 1
                print("  ✔ 变异被抓住：%s" % label)
                print("      ↳ 失败检查：%s" % ", ".join(failed))
            else:
                all_caught = False
                print("  ✘ ★ 变异**未被抓住**：%s" % label)
        except Exception:
            all_caught = False
            print("  ✘ ★ 变异导致自检崩溃（等于没抓住）：%s" % label)
            traceback.print_exc()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 72)
    print("变异注入：%s（%d/%d 被抓住）"
          % ("全部被抓住" if all_caught else "★有未被抓住的", caught_n, len(MUTATIONS)))
    print("=" * 72)
    return 0 if all_caught else 1


if __name__ == "__main__":
    sys.exit(main())
