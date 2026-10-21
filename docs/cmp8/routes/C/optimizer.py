# -*- coding: utf-8 -*-
"""L3 · 更新规则：**优化器契约执行器**（契约 §4.1 的 8 条纪律）。

## 这个文件是什么

契约 §4.1 把「优化策略」写成了 8 条纪律。这里把它们**逐条变成可执行的代码**：

| 契约小节 | 纪律 | 实现位置 |
|---|---|---|
| §4.1 ① | 一次只改一个自由度 | `_check_single_freedom()` + `Optimizer.run()` |
| §4.1 ② | 改动后重复测量 R_meas 次取中位数 | `measure_arm()` |
| §4.1 ③ | **接受条件**：`VD_net(θ') − VD_net(θ) > δ` 且所有反判据不劣化 | `_accept_decision()` + `counter_criteria()` |
| §4.1 ④ | 预算上限 K | `Optimizer.run()` |
| §4.1 ⑤ | **禁止在 TEST 集上做改动决策** | `_check_dev_only()`（代码层守卫） |
| §4.1 ⑥ | **禁止改 measure_version** | `_check_measure_version()`（代码层守卫） |
| §4.1 ⑦ | 每次改动的 (θ, θ', VD_net, 反判据, δ, 接受/回退) 全部落盘 | `JsonlLog`（append-only + fsync） |
| §4.1 ⑧ | 连续 3 次收益 ≤ δ ⇒ 停 | `Optimizer.run()` |

外加 **L0-5 地板检测**：被优化量长期贴 0 ⇒ 先修测量再谈优化 ⇒ `FloorEffectError`。

## 测量语义（本模块采用的**简化版**协议口径，务必看清）

协议 §1.7 的「族（family）跨臂匹配」是完整实现；本模块用**可机械复算的简化口径**：

- **维度 = 族** = 「承重 ∧ 被依据支持」的卡片按 `supports_conclusions` 集合归并后的组；
  族键 = `"|".join(sorted(supports_conclusions))`（协议里族键是
  `sort(conclusion_set) + "|" + decision_point`；DEV 金标卡没有 `decision_point` 字段，
  故此处只取前半段 —— **这是简化，不是协议原文**）。
- `VD_net(t) = VD_added(t) − VD_lost(t)`，双边；`VD_net(arm) = 任务级 VD_net 的中位数`（协议 §3.1）。
- `VD_added / VD_lost` 的参照系 = **参照臂**（`ref_cfg`）的同题族集合。
- 反判据按协议 §3.2 的 R1–R4 实现；**R1 用协议的三段判读**（≤1×地板 / 1–2×地板 warning / >2×地板 失败），
  R4 是描述量（只报 warning，不判死）。

⚠️ **本文件不产生任何实验结论**。所有读数都由调用方传入的 runner 产生；
自带自检用的是**假客户端**（`test_optimizer.py`），读数是**合成读数**。
"""
from __future__ import annotations

import json
import os
import statistics
import time

from config import (MultiFreedomChangeError, NoFreedomChanged, UnknownFreedom,
                    config_hash, diff_configs, free_degrees, is_placeholder_measure,
                    set_freedom)

# --------------------------------------------------------------------------
# 异常（契约违反一律 fail-closed：抛异常，不静默放行）
# --------------------------------------------------------------------------
class ContractViolation(Exception):
    """契约违反的基类。"""


class TestSetLeakError(ContractViolation):
    """⑤ 违反：拿 TEST 集做改动决策。"""


class MeasureVersionChangeError(ContractViolation):
    """⑥ 违反：为了让读数好看而改 `measure_version`。"""


class FloorEffectError(ContractViolation):
    """L0-5：被优化量长期贴 0 ⇒ 当前状态**不允许优化**（先修测量）。"""


#: TEST 集的任务号形态（协议里 TEST 侧是 U1–U4；DEV 侧是 D01…）
TEST_TASK_ID_RE = r"^U\d+$"
DEV_TASK_ID_RE = r"^D\d+$"


# --------------------------------------------------------------------------
# 测量内核
# --------------------------------------------------------------------------
def family_key(card: dict) -> str:
    """族键 = `supports_conclusions` 排序后用 `|` 连接。"""
    return "|".join(sorted(card.get("supports_conclusions") or []))


def _read_cards(cards) -> list:
    out = []
    for c in cards or []:
        out.append({
            "card_id": c.get("card_id"),
            "supports_conclusions": list(c.get("supports_conclusions") or []),
            "load_bearing": bool(c.get("load_bearing")),
            "verify_status": c.get("verify_status") or "unverifiable",
            "stage": c.get("stage") or "final",
            "tokens": int(c.get("tokens") or 0),
        })
    return out


def _task_reading(task: dict, cards: list, gen_cost: dict, meas_cost: dict) -> dict:
    """把一串卡片折成单题读数。

    ⚠️ **生成成本与测量成本分开记账**（契约 §2 的成本结构：
    「消融贵在生成，测量是免费的」⇒ 两本账必须能分开报）。
    """
    key_concl = list(task.get("key_conclusions") or [])
    fam_final, fam_internal, fam_unver = set(), set(), set()
    n_total = n_lb = n_sup = n_con = n_unm = n_pf = 0
    hit = set()
    for c in cards:
        n_total += 1
        st = c.get("verify_status")
        if c.get("load_bearing"):
            n_lb += 1
        if st == "supported":
            n_sup += 1
            if c.get("load_bearing"):
                k = family_key(c)
                if k:
                    if c.get("stage") == "internal":
                        fam_internal.add(k)
                    else:
                        fam_final.add(k)
            for s in (c.get("supports_conclusions") or []):
                if s in key_concl:
                    hit.add(s)
        elif st == "contradicted":
            n_con += 1
        elif st == "parse_failed":
            n_pf += 1
        else:  # unmentioned / unverifiable
            n_unm += 1
            if c.get("load_bearing"):
                fam_unver.add(family_key(c))
    den = n_sup + n_con
    return {
        "task_id": task.get("task_id"),
        "vd_final": len(fam_final),
        "vd_internal": len(fam_internal | fam_final),
        "families_final": sorted(fam_final),
        "families_internal": sorted(fam_internal | fam_final),
        "families_unverified": sorted(fam_unver),
        "vd_unverified": len(fam_unver),
        "n_cards_total": n_total,
        "n_cards_loadbearing": n_lb,
        "n_cards_nonloadbearing": n_total - n_lb,
        "n_supported": n_sup,
        "n_contradicted": n_con,
        "n_unmentioned": n_unm,
        "n_parse_failed": n_pf,
        "conflict_num": n_con,
        "conflict_den": den,
        "key_hit_ids": sorted(hit),
        "n_key_hit": len(hit),
        "n_key_total": len(key_concl),
        "cost_gen": dict(gen_cost or {}),
        "cost_meas": dict(meas_cost or {}),
        "cost": {k: float((gen_cost or {}).get(k, 0) or 0) + float((meas_cost or {}).get(k, 0) or 0)
                 for k in ("n_calls", "n_tokens", "cost_usd")},
    }


def _median_rep_index(values) -> int:
    """中位数那一 rep 的下标（偶数个取下中位数 ⇒ 确定性）。"""
    order = sorted(range(len(values)), key=lambda i: values[i])
    return order[(len(order) - 1) // 2]


def measure_arm(cfg: dict, devset: list, runner, *, r_meas: int = 5,
                gen_seed: int = 20261021, meas_seed_base: int = 20261021) -> dict:
    """在 DEV 上测量一个 config（契约 ②：同一份答案测 R_meas 次，取中位数）。

    流程（每题）：
      1. **生成一次**（种子固定 ⇒ 可复现；θ 与 θ' 共用同一批种子 ⇒ 配对比较）
      2. **测量 R_meas 次**（每次换一个判官随机种子）⇒ 逐 rep 读数
      3. 取**中位数那一 rep** 作为该题读数（族集合、分子分母都取它）

    返回
    ----
    dict：`per_task`（逐题读数）/`agg`（聚合）/`reps`（逐 rep 读数，供审计）
    """
    if r_meas < 1:
        raise ValueError("r_meas 必须 ≥1")
    per_task, reps = {}, {}
    for ti, task in enumerate(devset):
        ans = runner.generate(task, cfg, seed=gen_seed * 1000 + ti)
        gen_cost = ans.get("cost") or {}
        rep_reads = []
        for r in range(r_meas):
            m = runner.measure(task, ans, seed=meas_seed_base * 1000 + r * 17 + ti)
            cards = _read_cards(m.get("cards"))
            rep_reads.append(_task_reading(task, cards, gen_cost, m.get("cost") or {}))
        reps[task.get("task_id")] = [
            {"rep": i, "vd_final": rr["vd_final"], "n_supported": rr["n_supported"],
             "n_contradicted": rr["n_contradicted"], "n_key_hit": rr["n_key_hit"],
             "n_cards_total": rr["n_cards_total"]}
            for i, rr in enumerate(rep_reads)
        ]
        idx = _median_rep_index([rr["vd_final"] for rr in rep_reads])
        chosen = dict(rep_reads[idx])
        chosen["rep_used"] = idx
        chosen["n_reps"] = r_meas
        per_task[task.get("task_id")] = chosen
    return {"config_hash": config_hash(cfg), "measure_version": cfg.get("measure_version"),
            "per_task": per_task, "reps": reps}


def _aggregate(per_task: dict, ref_families: dict) -> dict:
    """把逐题读数聚成臂级读数，并算 `VD_net`（双边，对参照臂）。"""
    per = {}
    added_total = lost_total = 0
    vd_net_vals = []
    for tid, r in sorted(per_task.items()):
        ref = set((ref_families or {}).get(tid) or [])
        cur = set(r.get("families_final") or [])
        added = sorted(cur - ref)
        lost = sorted(ref - cur)
        vd_net = len(added) - len(lost)
        added_total += len(added)
        lost_total += len(lost)
        vd_net_vals.append(vd_net)
        per[tid] = {"vd_net": vd_net, "added": added, "lost": lost,
                    "vd_final": r.get("vd_final"), "vd_internal": r.get("vd_internal"),
                    "vd_entry_rate": (r["vd_final"] / r["vd_internal"]) if r.get("vd_internal") else None,
                    "n_key_hit": r.get("n_key_hit"), "n_key_total": r.get("n_key_total"),
                    "conflict_num": r.get("conflict_num"), "conflict_den": r.get("conflict_den"),
                    "n_cards_total": r.get("n_cards_total"),
                    "n_cards_loadbearing": r.get("n_cards_loadbearing"),
                    "n_parse_failed": r.get("n_parse_failed"),
                    "vd_unverified": r.get("vd_unverified")}
    n_sup = sum(r.get("n_supported", 0) for r in per_task.values())
    n_con = sum(r.get("n_contradicted", 0) for r in per_task.values())
    n_lb = sum(r.get("n_cards_loadbearing", 0) for r in per_task.values())
    n_tot = sum(r.get("n_cards_total", 0) for r in per_task.values())
    n_pf = sum(r.get("n_parse_failed", 0) for r in per_task.values())
    den = n_sup + n_con
    hits = sum(r.get("n_key_hit", 0) for r in per_task.values())
    key_tot = sum(r.get("n_key_total", 0) for r in per_task.values())
    cost_gen = {"n_calls": 0, "n_tokens": 0, "cost_usd": 0.0}
    cost_meas = {"n_calls": 0, "n_tokens": 0, "cost_usd": 0.0}
    for r in per_task.values():
        for k in ("n_calls", "n_tokens", "cost_usd"):
            cost_gen[k] += float((r.get("cost_gen") or {}).get(k, 0) or 0)
            cost_meas[k] += float((r.get("cost_meas") or {}).get(k, 0) or 0)
    cost = {k: cost_gen[k] + cost_meas[k] for k in ("n_calls", "n_tokens", "cost_usd")}
    return {
        "vd_net": statistics.median(vd_net_vals) if vd_net_vals else 0,
        "vd_net_per_task": vd_net_vals,
        "vd_added_total": added_total,
        "vd_lost_total": lost_total,
        "n_cards_total": n_tot,
        "n_cards_loadbearing": n_lb,
        "n_cards_nonloadbearing": n_tot - n_lb,
        "floral_rate": ((n_tot - n_lb) / n_tot) if n_tot else None,
        "dimension_per_card": None,
        "conflict_rate": (n_con / den) if den else 0.0,
        "conflict_num": n_con,
        "conflict_den": den,
        "support_rate": (n_sup / den) if den else 0.0,
        "n_supported": n_sup,
        "n_contradicted": n_con,
        "key_hit": hits,
        "key_total": key_tot,
        "key_hit_rate": (hits / key_tot) if key_tot else None,
        "parsefail_rate": (n_pf / n_tot) if n_tot else 0.0,
        "n_parse_failed": n_pf,
        "cost": cost,
        "cost_gen": cost_gen,
        "cost_meas": cost_meas,
        "per_task": per,
    }


def floor_check(agg: dict) -> dict:
    """L0-5 地板检测：被优化量的**绝对值**是否长期贴着 0。

    判据（事前写死）：**中位 `vd_final` == 0**（= 该臂在多数题上**一条维度都没造出来**）
    且 **≥50% 的题 `vd_final` == 0** ⇒ 判为地板效应
    ⇒ 当前状态不允许优化（先放宽判据 / 扩依据包，协议 L0-5）。

    ⚠️ **为什么看 `vd_final` 而不是 `VD_net`**：
    `VD_net` 是**相对参照臂的净增益**，优化起点上它本来就是 0
    （"这一版和基线一样" 是正常的起点，不是"造不出东西"）
    ⇒ 用 `VD_net == 0` 当地板判据会让优化器**永远无法起步**。
    契约 L0-5 说的"绝对值"指的是维度数本身（U1 批次"9/12 份 D=0"）。
    `net_at_zero` 仍会一并报出（描述量），但**不**用来拦优化。
    """
    vals = []
    for tid, pr in sorted((agg.get("per_task") or {}).items()):
        vals.append(pr.get("vd_final") or 0)
    n = len(vals)
    zeros = sum(1 for v in vals if v == 0)
    med = statistics.median(vals) if vals else 0
    frac = (zeros / n) if n else 1.0
    blocked = bool(n and med == 0 and frac >= 0.5)
    net = list(agg.get("vd_net_per_task") or [])
    net_zeros = sum(1 for v in net if v == 0)
    return {"floor_effect": blocked, "median_vd_final": med,
            "frac_zero_tasks": frac, "n_tasks": n,
            "net_at_zero": bool(net and statistics.median(net) == 0),
            "frac_zero_net_tasks": (net_zeros / len(net)) if net else None,
            "verdict": ("被优化量长期贴 0（该臂多数题一条维度都没造出来）"
                        "⇒ **先修测量/扩依据包，再谈优化**（L0-5）"
                        if blocked else "未见地板效应")}


# --------------------------------------------------------------------------
# 守卫（契约 ①⑤⑥）—— 全部是模块级函数 ⇒ 可被变异注入替换
# --------------------------------------------------------------------------
def _is_dev_task(task: dict) -> bool:
    split = str(task.get("split") or "").lower()
    if split:
        return split == "dev"
    tid = str(task.get("task_id") or "")
    return bool(tid) and tid[0] == "D" and tid[1:].isdigit()


def _check_dev_only(dataset) -> bool:
    """⑤ **禁止在 TEST 集上做改动决策**（代码层守卫）。

    协议 §4.1 已分 DEV/TEST：TEST 只在最后跑一次。
    ⇒ 任何进入「改动决策」路径的数据集都必须**逐题**通过 DEV 判定。
    """
    bad = []
    for t in dataset or []:
        if not _is_dev_task(t):
            bad.append(str(t.get("task_id")))
    if bad:
        raise TestSetLeakError(
            "⑤ 违反：改动决策不得使用 TEST 集（发现非 DEV 题：%s）"
            % ", ".join(bad[:8]))
    return True


def _check_single_freedom(a: dict, b: dict) -> str:
    """① **一次只改一个自由度**（可归因）。

    变了 >1 个 ⇒ `MultiFreedomChangeError`；完全没变 ⇒ `NoFreedomChanged`。
    """
    return diff_configs(a, b)


def _check_measure_version(a: dict, b: dict) -> str:
    """⑥ **禁止改 measure_version**（改它 ⇒ 带宽变 ⇒ 全部重测并声明）。

    这条守卫拦的是「换个判官提示词版本，读数就涨」这种 reward hacking。
    """
    if a.get("measure_version") != b.get("measure_version"):
        raise MeasureVersionChangeError(
            "⑥ 违反：不得在优化过程中修改 measure_version"
            "（%s → %s）⇒ 测量带宽变了，全部历史读数作废并须重测"
            % (a.get("measure_version"), b.get("measure_version")))
    return "measure_version"


def _accept_decision(gain: float, delta: float, counter_ok: bool, warnings) -> bool:
    """③ **接受条件**（契约的核心）。

    `VD_net(θ') − VD_net(θ) > δ` **且** 所有反判据不劣化 ⇒ 接受；否则回退。
    """
    return bool(gain > delta and counter_ok)


# --------------------------------------------------------------------------
# 反判据（协议 §3.2 的 R1–R4）
# --------------------------------------------------------------------------
def counter_criteria(new_agg: dict, old_agg: dict, *, floors=None, caps=None) -> dict:
    """比较两个臂的反判据（R1–R4）。

    * **R1 矛盾率不上升**：差值 >2×地板 ⇒ 失败；1×<差值≤2× ⇒ warning（不判死，协议三段判读）
    * **R2 正确答案不丢**：任一题 `key_conclusion_hit` 低于原臂 ⇒ 失败
    * **R3 成本可接受**：超预注册预算上限 ⇒ 失败
    * **R4 依据支持率不下降**：描述量 ⇒ 只报 warning，不判死
    """
    floors = dict(floors or {})
    caps = dict(caps or {})
    warnings, out = [], {}

    # ── R1
    old_rate, new_rate = old_agg.get("conflict_rate", 0.0), new_agg.get("conflict_rate", 0.0)
    d = new_rate - old_rate
    floor = float(floors.get("conflict_rate", 0.0))
    if d <= floor:
        band, ok = "ok", True
    elif d <= 2 * floor:
        band, ok = "warning", True
        warnings.append("R1 矛盾率方向不利但不可分辨（%.4f → %.4f，地板 %.4f）" % (old_rate, new_rate, floor))
    else:
        band, ok = "fail", False
    out["R1"] = {"ok": ok, "band": band, "metric": "conflict_rate",
                 "old": old_rate, "new": new_rate, "diff": d, "floor": floor,
                 "old_num": old_agg.get("conflict_num"), "old_den": old_agg.get("conflict_den"),
                 "new_num": new_agg.get("conflict_num"), "new_den": new_agg.get("conflict_den"),
                 "note": "旧臂分母为空时比率无意义（协议 §3.1 禁止无分母比率）"
                 if not old_agg.get("conflict_den") else ""}

    # ── R2
    regressed = []
    for tid, pr in sorted((old_agg.get("per_task") or {}).items()):
        npr = (new_agg.get("per_task") or {}).get(tid) or {}
        if (npr.get("n_key_hit", 0) or 0) < (pr.get("n_key_hit", 0) or 0):
            regressed.append({"task_id": tid, "old": pr.get("n_key_hit"), "new": npr.get("n_key_hit")})
    out["R2"] = {"ok": not regressed, "metric": "key_conclusion_hit",
                 "old": old_agg.get("key_hit"), "new": new_agg.get("key_hit"),
                 "regressed_tasks": regressed,
                 "note": "逐题比；任一题低于原臂 ⇒ 失败（协议 R2）"}

    # ── R3
    over = []
    for k in ("n_calls", "n_tokens", "cost_usd"):
        cap = caps.get(k)
        if cap is None:
            continue
        val = float((new_agg.get("cost") or {}).get(k, 0) or 0)
        if val > float(cap):
            over.append({"metric": k, "value": val, "cap": cap})
    out["R3"] = {"ok": not over, "metric": "cost", "cost": new_agg.get("cost"),
                 "caps": caps, "over_budget": over,
                 "note": "超预算 ⇒ 该样本作废（协议 R3）"}

    # ── R4（描述量）
    old_sup, new_sup = old_agg.get("support_rate", 0.0), new_agg.get("support_rate", 0.0)
    r4_ok = new_sup >= old_sup
    if not r4_ok:
        warnings.append("R4 依据支持率下降（%.4f → %.4f）；描述量，不判死（与 R1 联合看）"
                        % (old_sup, new_sup))
    out["R4"] = {"ok": r4_ok, "metric": "support_rate", "old": old_sup, "new": new_sup,
                 "note": "描述量（协议 §3.2）"}

    out["all_ok"] = bool(out["R1"]["ok"] and out["R2"]["ok"] and out["R3"]["ok"])
    out["warnings"] = warnings
    return out


# --------------------------------------------------------------------------
# 落盘（契约 ⑦：append-only + fsync）
# --------------------------------------------------------------------------
class JsonlLog:
    """追加式 JSONL 日志（每写一条立即 flush + fsync ⇒ 崩溃不丢已记录的改动）。"""

    def __init__(self, path: str):
        self.path = path
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)

    def append(self, record: dict) -> dict:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return record

    def read_all(self) -> list:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out


# --------------------------------------------------------------------------
# 优化器本体
# --------------------------------------------------------------------------
class Optimizer:
    """契约 §4.1 的执行器。

    参数
    ----
    devset : DEV 任务列表（**必须**逐题通过 `_check_dev_only`）
    ref_cfg : 参照臂 config（`VD_added/VD_lost` 的基准）
    runner : 执行体，须实现 `generate(task, cfg, seed)` 与 `measure(task, answer, seed)`
    delta : 接受阈值 δ（**用 δ_total**，见 `noise_floor.py`）
    budget : 改动预算 K（④）
    r_meas : 重复测量次数（②）
    floors : `{"conflict_rate": float}`（R1 的地板）
    caps : `{"n_calls":…, "n_tokens":…, "cost_usd":…}`（R3 的预算上限）
    """

    def __init__(self, *, devset, ref_cfg, runner, delta, budget=8, r_meas=5,
                 log_path=None, floors=None, caps=None, seed=20261021,
                 devset_hash=None, allow_floor_effect=False):
        _check_dev_only(devset)                      # ⑤（构造时）
        self.devset = list(devset)
        self.runner = runner
        self.delta = float(delta)
        self.budget = int(budget)
        self.r_meas = int(r_meas)
        self.floors = dict(floors or {})
        self.caps = dict(caps or {})
        self.seed = int(seed)
        self.devset_hash = devset_hash
        self.allow_floor_effect = bool(allow_floor_effect)
        self.log = JsonlLog(log_path) if log_path else None
        self.ref_cfg = ref_cfg
        self.ref_families = None
        self.ref_agg = None

    # ── 测量
    def measure(self, cfg: dict, *, gen_seed=None) -> dict:
        """在 DEV 上测一个 config（② 重复测量取中位数）。"""
        _check_dev_only(self.devset)                 # ⑤（每次测量都查，不只构造时）
        gs = self.seed if gen_seed is None else int(gen_seed)
        arm = measure_arm(cfg, self.devset, self.runner, r_meas=self.r_meas,
                          gen_seed=gs, meas_seed_base=gs)
        if self.ref_families is None:
            # 首次测量：先把参照臂测出来（同样 R_meas 次取中位数 ⇒ 配对）
            ref_arm = measure_arm(self.ref_cfg, self.devset, self.runner,
                                  r_meas=self.r_meas, gen_seed=gs, meas_seed_base=gs)
            self.ref_families = {t: r.get("families_final") or []
                                 for t, r in ref_arm["per_task"].items()}
            self.ref_agg = _aggregate(ref_arm["per_task"], self.ref_families)
        agg = _aggregate(arm["per_task"], self.ref_families)
        arm["agg"] = agg
        arm["ref_agg"] = self.ref_agg
        return arm

    # ── 一次改动
    def _record(self, rec: dict) -> dict:
        rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        rec["measure_version"] = rec.get("measure_version")
        if self.log:
            self.log.append(rec)
        return rec

    def evaluate(self, theta: dict, theta_agg: dict, cand: dict):
        """评估一个候选 config（③/⑦）。返回 `(落盘记录, 新臂聚合读数, 是否接受)`。"""
        new = self.measure(cand)
        new_agg = new["agg"]
        gain = new_agg["vd_net"] - theta_agg["vd_net"]
        cc = counter_criteria(new_agg, theta_agg, floors=self.floors, caps=self.caps)
        accept = _accept_decision(gain, self.delta, cc["all_ok"], cc.get("warnings"))
        rec = {
            "kind": "change",
            "theta": theta,
            "theta_prime": cand,
            "changed_freedom": None,
            "vd_net_theta": theta_agg["vd_net"],
            "vd_net_theta_prime": new_agg["vd_net"],
            "vd_net_theta_per_task": theta_agg.get("vd_net_per_task"),
            "vd_net_theta_prime_per_task": new_agg.get("vd_net_per_task"),
            "gain": gain,
            "delta": self.delta,
            "delta_source": "delta_total",
            "r_meas": self.r_meas,
            "reps": new.get("reps"),
            "counter_criteria": cc,
            "decision": "accept" if accept else "rollback",
            "reason": ("接受：VD_net 上升 %.4g > δ %.4g 且反判据不劣化" % (gain, self.delta))
                      if accept else
                      ("回退：VD_net 上升 %.4g 未超过 δ %.4g" % (gain, self.delta)
                       if gain <= self.delta else
                       "回退：反判据劣化（R1 %s / R2 %s / R3 %s）"
                       % (cc["R1"]["band"], cc["R2"]["ok"], cc["R3"]["ok"])),
            "config_hash_theta": config_hash(theta),
            "config_hash_theta_prime": config_hash(cand),
            "measure_version": cand.get("measure_version"),
            "devset_hash": self.devset_hash,
            "floor_check": floor_check(new_agg),
            "measure_placeholder": is_placeholder_measure(cand.get("measure") or {}),
        }
        return rec, new_agg, accept

    # ── 主循环
    def run(self, cfg0: dict, proposals) -> dict:
        """跑一串提案（每次一个自由度），返回轨迹。

        停止原因（`halt_reason`）：
          * `budget_exhausted`     —— ④ 预算 K 用完
          * `converged_no_gain_3`  —— ⑧ 连续 3 次收益 ≤ δ
          * `proposals_exhausted`  —— 提案跑完
          * `floor_effect`         —— L0-5 地板效应（被优化量长期贴 0）
        """
        cur = cfg0
        cur_arm = self.measure(cur)
        cur_agg = cur_arm["agg"]
        fl = floor_check(cur_agg)
        if fl["floor_effect"] and not self.allow_floor_effect:
            raise FloorEffectError(
                "L0-5：%s（median vd_final=%s，零值题占比 %.2f）"
                % (fl["verdict"], fl["median_vd_final"], fl["frac_zero_tasks"]))

        records, n_changes, no_gain, step = [], 0, 0, 0
        halt = "proposals_exhausted"
        it = proposals if isinstance(proposals, (list, tuple)) else list(proposals)
        for prop in it:
            if n_changes >= self.budget:
                halt = "budget_exhausted"
                break
            if callable(prop):
                prop = prop(cur, step)
            if not prop:
                continue
            step += 1
            if isinstance(prop, dict) and prop.get("config") is not None:
                # 提案者直接交来一整份 config ⇒ 守卫 ① 才有牙齿（否则「一次只改一个」
                # 只是 set_freedom 的副产品，拦不住乱改的提案者）
                cand = prop["config"]
            else:
                try:
                    cand = set_freedom(cur, prop["freedom"], prop["value"])
                except UnknownFreedom as e:
                    self._record({"kind": "guard_reject", "guard": "unknown_freedom",
                                  "proposal": prop, "detail": str(e), "step": step})
                    continue

            # ── 守卫 ①
            try:
                changed = _check_single_freedom(cur, cand)
            except (MultiFreedomChangeError, NoFreedomChanged) as e:
                self._record({"kind": "guard_reject", "guard": "single_freedom",
                              "proposal": prop, "detail": str(e), "step": step,
                              "theta": cur, "theta_prime": cand})
                continue
            # ── 守卫 ⑥
            try:
                _check_measure_version(cur, cand)
            except MeasureVersionChangeError as e:
                self._record({"kind": "guard_reject", "guard": "measure_version",
                              "proposal": prop, "detail": str(e), "step": step,
                              "theta": cur, "theta_prime": cand})
                continue
            # ── 死参数守卫（改动不产生行为差异 ⇒ 没有归因价值）
            if changed not in free_degrees(cur):
                self._record({"kind": "guard_reject", "guard": "dead_freedom",
                              "proposal": prop, "detail": "%s 在当前 config 下不是活自由度" % changed,
                              "step": step, "theta": cur, "theta_prime": cand})
                continue

            rec, new_agg, accept = self.evaluate(cur, cur_agg, cand)
            rec["step"] = step
            rec["changed_freedom"] = changed
            rec["proposal"] = prop
            self._record(rec)
            records.append(rec)
            n_changes += 1
            if accept:
                cur, cur_agg = cand, new_agg
            no_gain = 0 if rec["gain"] > self.delta else no_gain + 1
            if no_gain >= 3:
                halt = "converged_no_gain_3"
                break
        if halt == "proposals_exhausted" and n_changes >= self.budget:
            halt = "budget_exhausted"
        return {"final_config": cur, "records": records, "halt_reason": halt,
                "n_changes": n_changes, "no_gain_streak_end": no_gain,
                "final_agg": cur_agg, "ref_agg": self.ref_agg}
