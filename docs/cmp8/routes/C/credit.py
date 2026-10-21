# -*- coding: utf-8 -*-
"""L1 · 信用分配：**消融式** `Δ(component)`（契约 §2 的可执行件）。

## 契约说的缺口

`VD_net` 是**终局标量**。维度卡片有 `stage` 字段，但它只用来区分「探索了但没输出」，
**没有用于把增益归因到「哪个步骤」**。⇒ 缺的是「贡献度分解」：

| 概念 | 定义 | 用途 |
|---|---|---|
| 边际贡献 `Δ(component)` | 去掉该组件后 `VD_net` 下降多少 | 哪个组件真的在造维度 |
| 冗余组件 | `Δ ≈ 0` | **可删**（路线 A 缺优化器时最该做的事） |
| 反向组件 | `Δ < 0` | 该组件在**挤掉**别的维度 |
| stage 分解 | 增益按产生阶段归因 | 让 B 的 op 分布、C 的参数、A 的节点同台可比 |

## 为什么用**消融臂**而不是反事实推理

契约 §2 的可执行性判据：「`Δ(step)` 的估计必须**便宜**
⇒ 用消融臂（去掉一步再测一遍）而不是反事实推理 ——
消融贵在**生成**，而**测量是免费的**（MiniMax 订阅 $0）⇒ **成本结构天然支持消融式信用分配**。

⇒ 本模块**把两本账分开记**并分别报：
  * `cost_gen`  ：消融臂那一趟**重新生成**的代价（贵）；
  * `cost_meas` ：同一趟的**重复测量**代价（便宜 ⇒ 记 0 并记测量次数）。

## Δ 的符号约定（事前写死）

```
Δ(component) = VD_net(完整 config) − VD_net(消融掉该组件的 config)
```

| Δ | 判词 | 含义 |
|---|---|---|
| `Δ > δ` | **contributing** | 去掉它就掉维度 ⇒ 它在造维度 |
| `|Δ| ≤ δ` | **redundant** | 去掉它没变化 ⇒ **可删** |
| `Δ < −δ` | **reverse** | 去掉它**反而涨** ⇒ 该组件在**挤掉**别的维度（路线 A 复核 F4 抓到过） |

⚠️ **δ 用 `noise_floor` 的 `threshold_delta`**：Δ 小于噪声地板时，
"contributing / redundant" 的区分没有意义 ⇒ 一律归到 redundant（并标 `below_floor`）。

## 纪律

* 消融臂与完整臂**共用同一批生成种子与判官种子** ⇒ 配对比较，消融的差值里不含生成噪声的独立项。
* 每次消融都**落盘**（含两本账）。
* **不产生实验结论**：这里报的是「组件贡献表」，不是「哪条路线更好」。
"""
from __future__ import annotations

import json
import os

from config import config_hash, set_freedom
from optimizer import Optimizer, _check_dev_only

#: 默认消融注册表：component 名 → (说明, 消融函数)
#: 消融函数的语义一律是「**把这个组件拿掉**」，不是「把它调成另一个值」。
ABLATIONS = {
    # ── 路线 C：阶段级（换拓扑 ⇒ 拿掉某个阶段）
    "stage:SPLIT": ("T3/T4/T5 的复合断言拆分回环", "T2"),
    "stage:STALL": ("T4 的停滞检测与预算重分配", "T3"),
    "stage:COLLAPSE": ("T5 的生成空间校准/条件切换重组", "T2"),
    # ── 路线 C：参数级（拿掉 ⇒ 退到"关掉"档）
    "params:n_split_max": ("每路采样份数回环关掉", 0),
    "params:stop_patience": ("深挖步关掉（不再开第二认知位置）", 0),
    "params:n_frames": ("多帧生成退成单路", 1),
    "params:n_cand_per_frame": ("每路多份采样退成单份", 1),
    "params:m_clusters": ("聚类装配退成一个代表", 1),
    # ── 路线 A：臂级常量
    "params:facet_enabled": ("承载面指令关掉", False),
    "params:novel_axis": ("去冗余关掉", False),
    "params:utility_axis": ("外部核验关掉", False),
    "params:resample_mode": ("第二轮重采样关掉", "none"),
}

#: 不可消融的 component（消融它等于把整个臂拿掉 ⇒ 无意义）
NON_ABLATABLE = ("topology", "route", "measure_version", "prompt_version")


def _default_ablate(cfg: dict, component: str):
    """默认消融：返回消融后的 config；不可消融则返回 None。"""
    if component in NON_ABLATABLE:
        return None
    if component in ABLATIONS:
        _desc, target = ABLATIONS[component]
        if component.startswith("stage:"):
            topo = cfg.get("topology")
            if topo == target:
                return None                      # 该拓扑本来就没有这个阶段
            if component == "stage:SPLIT" and topo not in ("T3", "T4", "T5"):
                return None
            if component == "stage:STALL" and topo != "T4":
                return None
            if component == "stage:COLLAPSE" and topo != "T5":
                return None
            return set_freedom(cfg, "topology", target)
        return set_freedom(cfg, component.replace(":", ".", 1), target)
    if component.startswith("weights."):
        return set_freedom(cfg, component, 0.0)
    return None


def delta_component(cfg: dict, component: str, *, devset, runner, ref_cfg=None,
                    r_meas=5, delta=0.0, ablate=None, seed=20261021,
                    floors=None, caps=None) -> dict:
    """消融掉 `component`，算它的边际贡献 `Δ(component) → VD_net`。

    返回里**必须**含：
      * `delta_vd_net`（Δ 本身）、`verdict`（contributing / redundant / reverse）
      * `vd_net_full` / `vd_net_ablated`（两端的原始读数）
      * `cost_gen` / `cost_meas`（**两本账分开**）+ `n_measurements`
    """
    _check_dev_only(devset)                      # ⑤：消融臂同样不许碰 TEST 集
    ref_cfg = ref_cfg or cfg
    ab = ablate or _default_ablate
    ablated = ab(cfg, component)
    if ablated is None:
        return {"component": component, "ablatable": False,
                "verdict": "not_ablatable",
                "note": "该组件在当前 config 下不存在（或消融它等于把整个臂拿掉）⇒ 不做消融",
                "delta_vd_net": None, "cost_gen": None, "cost_meas": None,
                "n_measurements": 0}

    opt = Optimizer(devset=devset, ref_cfg=ref_cfg, runner=runner, delta=delta,
                    r_meas=r_meas, floors=floors, caps=caps, seed=seed,
                    allow_floor_effect=True)
    # ⚠️ `allow_floor_effect=True`：信用分配是**描述性**的（算完贡献表再谈地板），
    #    不像优化器那样在地板上直接拒绝开工。地板判定由 `noise_floor.py` 单独给。
    full = opt.measure(cfg)
    abl = opt.measure(ablated)
    d = full["agg"]["vd_net"] - abl["agg"]["vd_net"]
    if d > delta:
        verdict = "contributing"
    elif d < -delta:
        verdict = "reverse"
    else:
        verdict = "redundant"
    n_meas = len(devset) * r_meas * 2          # 完整臂 + 消融臂，各 R_meas 次
    return {
        "component": component,
        "ablatable": True,
        "delta_vd_net": d,
        "verdict": verdict,
        "below_floor": bool(abs(d) <= delta),
        "threshold": delta,
        "vd_net_full": full["agg"]["vd_net"],
        "vd_net_ablated": abl["agg"]["vd_net"],
        "vd_net_full_per_task": full["agg"].get("vd_net_per_task"),
        "vd_net_ablated_per_task": abl["agg"].get("vd_net_per_task"),
        "config_hash_full": config_hash(cfg),
        "config_hash_ablated": config_hash(ablated),
        "cost_gen": abl["agg"].get("cost_gen"),
        "cost_meas": abl["agg"].get("cost_meas"),
        "n_measurements": n_meas,
        "cost_note": ("消融的代价在**生成**（上表 cost_gen 是消融臂那一趟重新生成的账单）；"
                      "**测量是免费的**（cost_meas 的 cost_usd 记 0，只记次数）"),
    }


def credit_table(cfg: dict, components, *, devset, runner, ref_cfg=None, r_meas=5,
                 delta=0.0, ablate=None, seed=20261021, floors=None, caps=None) -> dict:
    """对一组组件逐个做消融，产出「组件贡献表」+ 冗余/反向清单。"""
    rows = []
    for c in components:
        rows.append(delta_component(cfg, c, devset=devset, runner=runner,
                                    ref_cfg=ref_cfg, r_meas=r_meas, delta=delta,
                                    ablate=ablate, seed=seed, floors=floors, caps=caps))
    contributing = [r["component"] for r in rows if r.get("verdict") == "contributing"]
    redundant = [r["component"] for r in rows if r.get("verdict") == "redundant"]
    reverse = [r["component"] for r in rows if r.get("verdict") == "reverse"]
    not_abl = [r["component"] for r in rows if r.get("verdict") == "not_ablatable"]
    gen = {"n_calls": 0, "n_tokens": 0, "cost_usd": 0.0}
    meas = {"n_calls": 0, "n_tokens": 0, "cost_usd": 0.0}
    n_meas = 0
    for r in rows:
        for k in gen:
            gen[k] += float(((r.get("cost_gen") or {}).get(k, 0)) or 0)
            meas[k] += float(((r.get("cost_meas") or {}).get(k, 0)) or 0)
        n_meas += int(r.get("n_measurements") or 0)
    return {
        "schema": "credit/1",
        "config_hash": config_hash(cfg),
        "threshold_delta": delta,
        "components": rows,
        "contributing": contributing,
        "redundant": redundant,
        "reverse": reverse,
        "not_ablatable": not_abl,
        "billing": {"cost_gen": gen, "cost_meas": meas, "n_measurements": n_meas,
                    "note": ("**生成与测量分开计费**：消融的贵处在生成（cost_gen），"
                             "测量免费（cost_meas.cost_usd = 0，只记次数）")},
    }


def save_credit_table(table: dict, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=2, default=str)
    return path
