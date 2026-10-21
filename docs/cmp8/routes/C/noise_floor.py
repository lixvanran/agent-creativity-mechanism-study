# -*- coding: utf-8 -*-
"""L0-3 · 噪声地板 δ 的**真实现**（优化器契约 §1.3 的 L0-3/L0-4/L0-5）。

## 为什么要把噪声拆成两半

一次「改动是否让维度增益变大」的判定，要同时扛住两种随机性：

| 成分 | 是什么 | 变大了说明什么 | 该修什么 |
|---|---|---|---|
| **δ_judge**（判官侧） | **同一份答案**重复判定，判官/抽取器自身的波动 | 测量仪器不稳 | 修判官：冻结 `measure_version`、加预算阶梯、增重复次数 |
| **δ_judge_version**（★ 判官侧·跨版本） | 同一份答案，换**判官版本 / 判官模型**判定 | 协议变更导致的读数漂移 | 冻结 `measure_version`；或把跨版本漂移纳入门槛 |
| **δ_gen**（生成侧） | 同一配置**重新生成**答案，产出本身的波动 | 被测流程本身不稳 | 修流程：降温度、锁种子、增重复 |
| **δ_total** | 两者之和（端到端重跑） | —— | **接受阈值用这个** |

⇒ 契约 L0-4：「一次改动的收益**必须 > δ** 才算变好」⇒ **δ_total 是接受阈值用的那个**。

### ★★ 为什么要单独测 δ_judge_version（2026-10-22 补）

判官跑 `temperature=0` ⇒ **同一 `measure_version` 内判定是确定性的**
⇒ 「只换判官种子」的 δ_judge **恒为 0**（**定义造成的，不是仪器稳**）。
我们真实栽的跟头恰恰是**跨 `measure_version` 的漂移**
（U1 实测：v1→v2 净增益 `0/+1/−1` → `+1/+4/0`）。
⇒ 只测种子地板 ⇒ **判官侧漂移被完全漏掉** ⇒ 拿恒为 0 的地板当「增益 > δ ⇒ 可信」门槛
⇒ **任何非零增益都会被判为可信**。
⇒ 本模块的**硬闸门**：种子地板退化且未提供 `judge_variants` ⇒ **不允许优化**。

依据文献：ToT 的**换评估模型交叉实验**（同源 74% / 换评估器 64% / 31%）；
Diversity Collapse 的**换度量/换 embedding 检查排序稳定性**。

## 「正确答案」参照：DEV 金标卡（**不依赖任何抽取器**）

DEV 集冻结时带了 `gold/Dxx_cards.json`（由结论空间机械派生，**不依赖抽取器**）
⇒ 本模块用**金标卡**当「正确答案」参照：
  * 命中金标卡 ⇒ 抽取/核验侧读到的东西是对的；
  * 金标卡的 `supports_conclusions` 决定「哪些维度是真实存在的」；
  * ⇒ δ 的估计**不依赖任何抽取器的输出质量**（否则就是"用坏尺子量尺子"）。

## 三个 δ 怎么估（事前写死）

| δ | 怎么造重复 | 每次读什么 |
|---|---|---|
| `δ_judge` | 同一份答案，**只换判官随机种子**，测 R_meas 次 | 单题 `vd_final` |
| `δ_gen` | 换生成种子重新生成，判官种子固定 | 单题 `vd_final` |
| `δ_total` | 换生成种子 + 换判官种子（端到端） | 单题 `vd_final` |

每个 δ = **中位数绝对偏差 × 1.4826**（契约 L0-3 的公式，稳健标准差估计）。

### ⚠️ 阈值用哪个数（事前写死，公开说明）

契约公式给的是 `MAD × 1.4826`。**小样本下 MAD 会退化成 0**
（过半样本相同 ⇒ 绝对偏差中位数 = 0）⇒ 单用 MAD 会把"有噪声"读成"没噪声"。
⇒ 本实现**同时**报三个数，并取**更保守**者作阈值：

```
threshold_delta = max(mad_sigma, mean_abs_dev)
```

`mad_sigma` 是契约原式；`mean_abs_dev` 对"少数样本偏出去"更敏感。
两个数都带 `n_samples`（δ 的估计本身也不稳，必须让读的人看见分母）。

## 判定：当前是否还允许优化

```
optimization_allowed = (threshold_delta < 0.5 × typical_gain_scale) and (not floor_effect)
```

* `typical_gain_scale`：**臂间 `VD_net` 差的典型尺度**（基线 config 与若干替代 config 的
  `|ΔVD_net|` 中位数）—— 这是"我们要探测的信号有多大"。
* `floor_effect`（L0-5）：该臂在多数题上**一条维度都没造出来** ⇒ 先修测量，别优化。

## 纪律

* **不重跑到好看**：测几次就是几次，**全部读数都进输出**。
* **同一个 `measure_version`**：δ_judge 的定义要求测量协议不变（否则测的是协议变更，不是噪声）。
* **输出必须带分母**：每个 δ 都附 `n_samples` / `n_tasks` / `frac_nonidentical`。
* **不产生实验结论**：本模块只报"地板估计"，不报"哪条路线更好"。
"""
from __future__ import annotations

import json
import os
import statistics

from config import config_hash, make_config, set_freedom
from optimizer import (_check_dev_only, _aggregate, floor_check, measure_arm, _task_reading)

MAD_TO_SIGMA = 1.4826


# --------------------------------------------------------------------------
# 估计量
# --------------------------------------------------------------------------
def mad_sigma(xs):
    """中位绝对偏差 → 稳健标准差估计（×1.4826）。

    返回 `(mad_sigma, mad, median, mean_abs_dev, n)`。
    """
    xs = [float(x) for x in xs]
    n = len(xs)
    if n < 2:
        return 0.0, 0.0, (xs[0] if xs else 0.0), 0.0, n
    med = statistics.median(xs)
    devs = [abs(x - med) for x in xs]
    mad = statistics.median(devs)
    mean_abs = sum(devs) / n
    return mad * MAD_TO_SIGMA, mad, med, mean_abs, n


def _vd_final(task: dict, m: dict) -> int:
    """**唯一**的「这道题得了多少维度」读数入口。

    ⚠️ 2026-10-22：原先 δ 的三个循环各自手写了一遍族归并
    （`"|".join(sups)`），**漏了 `stage == "internal"` 的过滤**
    ⇒ δ 测的是 `vd_internal` 那个量，而决策变量是 `vd_final`
    ⇒ **地板迁移不到「增益 > δ」的判定上**。
    ⇒ 现改为**直接调用生产的 `_task_reading`** ⇒ 统计量按构造一致。
    """
    cards = list(m.get("cards") or [])
    return int(_task_reading(task, cards, {}, {}).get("vd_final") or 0)


def _measure_with_variant(runner, task, ans, seed, variant=None):
    """调 `runner.measure`，可选地带上一个**判官变体**（跨版本/跨判官模型）。

    变体描述形如 `{"label": "judge-v2", "measure_version": "m2", "judge_model": "..."}`。
    runner 若不支持 `variant` 关键字 ⇒ **显式报错**（不静默忽略 ⇒ 否则"跨版本 δ"会退化成
    "同版本 δ"并冒充成真读数）。这是本项目一贯纪律：失败不许静默变成 0。
    """
    if variant is None:
        return runner.measure(task, ans, seed=seed)
    try:
        return runner.measure(task, ans, seed=seed, variant=variant)
    except TypeError as e:
        raise RuntimeError(
            "runner.measure 不接受 variant 关键字，无法测跨判官版本的 δ_judge_version。"
            "（不支持 ⇒ 不许静默退回同版本测量）原始错误：%s" % e)


def _spread(values, *, n_tasks=None, armlevel=None) -> dict:
    """把一组读数折成「一个 δ + 它的分母 + 退化诊断」。"""
    vals = [float(v) for v in values]
    ms, mad, med, mean_abs, n = mad_sigma(vals)
    frac_nonident = (sum(1 for v in vals if v != med) / n) if n else 0.0
    out = {
        "value": ms,                 # 契约原式：MAD × 1.4826
        "mad": mad,
        "median": med,
        "mean_abs_dev": mean_abs,    # 更敏感的备用估计量
        "n_samples": n,
        "n_tasks": n_tasks,
        "frac_nonidentical": frac_nonident,
        "degenerate": bool(n >= 2 and frac_nonident < 0.34),
        "samples": vals,
    }
    if armlevel is not None:
        ams, amad, amed, amean, an = mad_sigma(armlevel)
        out["armlevel"] = {"value": ams, "mad": amad, "median": amed,
                           "mean_abs_dev": amean, "n_samples": an,
                           "samples": [float(x) for x in armlevel]}
    return out


# --------------------------------------------------------------------------
# 替代 config（用来估「典型增益尺度」）
# --------------------------------------------------------------------------
def default_alternatives(route: str, base_cfg: dict, n: int = 3) -> list:
    """造几个**只差一个自由度**的替代 config（估臂间增益尺度用）。"""
    out = []
    if route == "C":
        import params as P
        topo = base_cfg.get("topology")
        live = [p for p in P.live_params(topo)]
        for p in live:
            vals = [v for v in P.alphabet(p) if v != base_cfg["params"].get(p["name"])]
            if not vals:
                continue
            out.append(set_freedom(base_cfg, "params.%s" % p["name"], vals[0]))
            if len(out) >= n:
                break
    elif route == "A":
        from config import A_PARAM_DOMAIN
        for k, dom in A_PARAM_DOMAIN.items():
            cur = base_cfg["params"].get(k)
            alt = next((v for v in dom if v != cur), None)
            if alt is None:
                continue
            out.append(set_freedom(base_cfg, "params.%s" % k, alt))
            if len(out) >= n:
                break
    else:  # B
        w = list(base_cfg.get("weights") or [])
        for i in range(min(n, len(w))):
            w2 = list(w)
            w2[i] = w2[i] + 0.1
            out.append(set_freedom(base_cfg, "weights.w%02d" % i, w2[i]))
    return out


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------
def estimate_noise_floor(devset, runner, *, route="C", base_cfg=None, ref_cfg=None,
                          r_meas=5, n_seeds=3, seed=20261021,
                          typical_gain_scale=None, n_alternatives=3,
                          judge_variants=None) -> dict:
    """在 DEV 上估噪声地板（δ_judge / δ_gen / δ_total）并给出「是否允许优化」的判决。

    参数
    ----
    devset : DEV 任务列表（必须逐题通过 `_check_dev_only` ⇒ TEST 集进不来）
    runner : 执行体（`generate` / `measure`）
    base_cfg : 被测的基线 config（默认 = 路线默认 config）
    ref_cfg : 参照臂 config（默认 = base_cfg）
    r_meas : 判官侧重复次数（②）
    n_seeds : 生成侧重复次数
    typical_gain_scale : 外部给定就用它；不给则用替代 config 扫一遍估

    返回
    ----
    dict：三个 δ（各带分母）+ 阈值 + 地板判定 + 判决 + 全部读数
    """
    _check_dev_only(devset)                       # ⑤：地板估计也不许碰 TEST 集
    base_cfg = base_cfg or make_config(route)
    ref_cfg = ref_cfg or base_cfg

    # ── 参照臂的族集合（VD_added/VD_lost 的基准）
    ref_arm = measure_arm(ref_cfg, devset, runner, r_meas=r_meas,
                          gen_seed=seed, meas_seed_base=seed)
    ref_families = {t: r.get("families_final") or [] for t, r in ref_arm["per_task"].items()}

    # ── δ_judge：同一份答案，只换判官种子
    judge_task_vals, judge_arm_vals = [], []
    judge_conflict_rates = []          # ← R1 的「种子噪声地板」：同臂同任务跨 rep 的逐份比率
    gen_answers = {}
    for ti, task in enumerate(devset):
        ans = runner.generate(task, base_cfg, seed=seed * 1000 + ti)
        gen_answers[task.get("task_id")] = ans
        per_rep = []
        for r in range(r_meas):
            m = runner.measure(task, ans, seed=seed * 1000 + r * 17 + ti)
            cards = m.get("cards") or []
            n_sup = n_con = 0
            for c in cards:
                st = c.get("verify_status")
                if st == "supported":
                    n_sup += 1
                elif st == "contradicted":
                    n_con += 1
            _vd = _vd_final(task, m)
            per_rep.append(_vd)
            judge_task_vals.append(_vd)
            den = n_sup + n_con
            judge_conflict_rates.append((n_con / den) if den else 0.0)
        judge_arm_vals.append(statistics.median(per_rep))
    # 臂级读数：每个 rep 序号一个臂级中位数
    judge_armlevel = []
    for r in range(r_meas):
        vals = []
        for ti, task in enumerate(devset):
            ans = gen_answers[task.get("task_id")]
            m = runner.measure(task, ans, seed=seed * 1000 + r * 17 + ti)
            vals.append(_vd_final(task, m))
        judge_armlevel.append(statistics.median(vals))
    delta_judge = _spread(judge_task_vals, n_tasks=len(devset), armlevel=judge_armlevel)

    # ── δ_judge_version：同一份答案，换**判官变体**（跨 measure_version / 跨判官模型）
    #
    # ★ 为什么必须单独测：判官跑 temperature=0 ⇒ **同一 measure_version 内是确定性的**
    #   ⇒ 种子地板 δ_judge 恒为 0（定义造成的，不是仪器稳）。
    #   而我们真实栽的跟头是**跨 measure_version 的漂移**（U1 实测：v1→v2 净增益 0/+1/−1 → +1/+4/0）。
    #   ⇒ 只测种子地板 ⇒ **判官侧漂移被完全漏掉** ⇒ 拿恒为 0 的地板当「增益 > δ ⇒ 可信」的门槛
    #   ⇒ **任何非零增益都会被判为可信**。这就是本模块的硬闸门要拦的东西。
    #
    # 依据文献：ToT 的**换评估模型交叉实验**（同源 74% / 换评估器 64% / 31%）；
    #           Diversity Collapse 的**换度量/换 embedding 检查排序稳定性**。
    delta_judge_version = None
    judge_variant_armlevel = []
    if judge_variants:
        v_task_vals, v_arm_vals = [], []
        for ti, task in enumerate(devset):
            ans = gen_answers[task.get("task_id")]
            per_variant = []
            for var in judge_variants:
                m = _measure_with_variant(runner, task, ans,
                                          seed=seed * 1000 + ti, variant=var)
                _vd = _vd_final(task, m)
                per_variant.append(_vd)
                v_task_vals.append(_vd)
            v_arm_vals.append(statistics.median(per_variant))
        judge_variant_armlevel = v_arm_vals
        delta_judge_version = _spread(v_task_vals, n_tasks=len(devset),
                                      armlevel=judge_variant_armlevel)
        delta_judge_version["n_variants"] = len(judge_variants)
        delta_judge_version["variant_labels"] = [
            v.get("label") if isinstance(v, dict) else str(v) for v in judge_variants]

    # 种子地板是否**有信息量**：temp=0 ⇒ 同版本确定 ⇒ frac_nonidentical≈0 ⇒ 退化
    judge_noise_degenerate = bool(delta_judge.get("degenerate")
                                   and delta_judge.get("value", 0.0) == 0.0)
    judge_noise_usable = (not judge_noise_degenerate) or (delta_judge_version is not None)

    # ── δ_gen：换生成种子，判官种子固定
    gen_task_vals, gen_arm_vals = [], []
    for s in range(n_seeds):
        gs = seed + 1000 * (s + 1)
        per_task_vals = []
        for ti, task in enumerate(devset):
            ans = runner.generate(task, base_cfg, seed=gs * 1000 + ti)
            m = runner.measure(task, ans, seed=gs * 1000 + ti)
            _vd = _vd_final(task, m)
            per_task_vals.append(_vd)
            gen_task_vals.append(_vd)
        gen_arm_vals.append(statistics.median(per_task_vals))
    delta_gen = _spread(gen_task_vals, n_tasks=len(devset), armlevel=gen_arm_vals)

    # ── δ_total：端到端（换生成种子 + 换判官种子）
    total_task_vals, total_arm_vals = [], []
    for s in range(n_seeds):
        gs = seed + 1000 * (s + 1)
        per_task_vals = []
        for ti, task in enumerate(devset):
            ans = runner.generate(task, base_cfg, seed=gs * 1000 + ti)
            reps = []
            for r in range(r_meas):
                m = runner.measure(task, ans, seed=gs * 1000 + r * 17 + ti)
                _vd = _vd_final(task, m)
                reps.append(_vd)
                total_task_vals.append(_vd)
            per_task_vals.append(statistics.median(reps))
        total_arm_vals.append(statistics.median(per_task_vals))
    delta_total = _spread(total_task_vals, n_tasks=len(devset), armlevel=total_arm_vals)

    # ── 基线臂本身的读数（地板检测用）
    base_arm = measure_arm(base_cfg, devset, runner, r_meas=r_meas,
                           gen_seed=seed, meas_seed_base=seed)
    base_agg = _aggregate(base_arm["per_task"], ref_families)
    fl = floor_check(base_agg)

    # ── 典型增益尺度（臂间）
    if typical_gain_scale is None:
        alts = default_alternatives(route, base_cfg, n=n_alternatives)
        diffs = []
        for a in alts:
            arm = measure_arm(a, devset, runner, r_meas=r_meas,
                              gen_seed=seed, meas_seed_base=seed)
            agg = _aggregate(arm["per_task"], ref_families)
            diffs.append(abs(agg["vd_net"] - base_agg["vd_net"]))
        typical_gain_scale = statistics.median(diffs) if diffs else 0.0
        scale_source = "替代 config 扫描（%d 个单自由度变体）" % len(alts)
    else:
        scale_source = "外部给定"

    threshold_delta = max(delta_total["value"], delta_total["mean_abs_dev"])
    # ── ★ 可信门槛必须**同时覆盖判官侧漂移**（跨版本），否则等于用一个恒为 0 的地板当门槛
    threshold_delta_credible = threshold_delta
    if delta_judge_version is not None:
        threshold_delta_credible = max(threshold_delta,
                                       delta_judge_version["value"],
                                       delta_judge_version["mean_abs_dev"])
    # ── R1 的「种子噪声地板」：同臂同任务跨 rep 的逐份 conflict_rate 的池化标准差
    cr_ms, cr_mad, cr_med, cr_mean, cr_n = mad_sigma(judge_conflict_rates)
    conflict_floor = max(cr_ms, cr_mean)
    allowed = (bool(threshold_delta_credible < 0.5 * typical_gain_scale)
               and not fl["floor_effect"] and judge_noise_usable)
    if not judge_noise_usable:
        verdict = ("**不允许优化**：δ_judge 种子地板退化（判官 temperature=0 ⇒ 同 measure_version "
                   "内确定性 ⇒ 种子地板恒为 0，**无信息量**），且未提供 judge_variants 做"
                   "**跨判官版本/跨判官模型**测量 ⇒ 判官侧漂移不可见 ⇒ "
                   "拿这个门槛判「增益 > δ ⇒ 可信」会把**任何非零增益都判为可信**。"
                   "⇒ 先补 judge_variants 再谈优化。")
    elif fl["floor_effect"]:
        verdict = ("**不允许优化**：%s；且 δ_可信(%.4g) ≥ 0.5×典型增益尺度(%.4g) ⇒ "
                   "先修测量/扩依据包" % (fl["verdict"], threshold_delta_credible, typical_gain_scale)
                   if threshold_delta_credible >= 0.5 * typical_gain_scale else
                   "**不允许优化**：%s" % fl["verdict"])
    elif allowed:
        verdict = ("允许优化：δ_可信(%.4g) < 0.5×典型增益尺度(%.4g)，且未见地板效应"
                   % (threshold_delta_credible, typical_gain_scale))
    else:
        verdict = ("**不允许优化**：δ_可信(%.4g) ≥ 0.5×典型增益尺度(%.4g) ⇒ "
                   "测量带宽大于信号带宽（契约 §1.2）⇒ 先修测量"
                   % (threshold_delta_credible, typical_gain_scale))

    return {
        "schema": "noise-floor/1",
        "note": "全部读数落盘；不重跑到好看；δ 的估计本身也不稳（看 n_samples）",
        "route": route,
        "r_meas": r_meas,
        "n_seeds": n_seeds,
        "seed": seed,
        "n_tasks": len(devset),
        "base_config_hash": config_hash(base_cfg),
        "measure_version": base_cfg.get("measure_version"),
        "delta_judge": delta_judge,
        "delta_judge_version": delta_judge_version,
        "judge_noise_degenerate": judge_noise_degenerate,
        "judge_noise_usable": judge_noise_usable,
        "delta_gen": delta_gen,
        "delta_total": delta_total,
        "threshold_delta": threshold_delta,
        "threshold_delta_credible": threshold_delta_credible,
        "threshold_rule": ("max(MAD×1.4826, mean_abs_dev)；"
                           "契约原式是 MAD×1.4826，小样本下 MAD 会退化成 0 ⇒ 取更保守者；"
                           "★ 可信门槛另取 max(δ_total, δ_judge_version) ⇒ 覆盖判官侧漂移"),
        "typical_gain_scale": typical_gain_scale,
        "typical_gain_scale_source": scale_source,
        "floor_check": fl,
        "floors": {
            "vd_net": threshold_delta,
            "conflict_rate": conflict_floor,
            "conflict_rate_detail": {"mad_sigma": cr_ms, "mad": cr_mad,
                                     "median": cr_med, "mean_abs_dev": cr_mean,
                                     "n_samples": cr_n,
                                     "source": "同臂同任务跨 rep 的逐份 conflict_rate（池化）"},
        },
        "base_agg": base_agg,
        "optimization_allowed": allowed,
        "verdict": verdict,
    }


def save_noise_floor(result: dict, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    return path


if __name__ == "__main__":
    print(__doc__)
    print("（主入口需要执行体；自检请跑 test_optimizer.py）")
