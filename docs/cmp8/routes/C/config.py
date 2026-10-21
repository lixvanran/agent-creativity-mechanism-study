# -*- coding: utf-8 -*-
"""L2 · 统一 config 对象（优化器契约 §3「搜索空间」的可执行件）。

## 为什么要有这个模块

三条路线的自由度形状完全不同：

| 路线 | 自由度 | 数量 | 契约 §3 的说法 |
|---|---|---|---|
| **A** | 预注册常量（可动但默认不动） | 见 `A_PARAMS` | 「A 在 L2 上是空的 ⇒ 它没有优化策略」 |
| **B** | 权重 `w` | 30 | 训练 |
| **C** | 参数 `θ` + 拓扑 | 12（默认拓扑下活 7）+ 6 选 1 | 训练 / 人 |

⇒ 本模块把三者映射成**同一个** config dict，于是三条路线第一次能落在
**同一张「改进步」表**上（契约 §3 的落脚句）。

## config 结构（JSON 可序列化，键序无关）

```python
{
  "route": "A" | "B" | "C",
  "topology": str | None,        # A/B 固定（None）；C 可枚举 6
  "params": {name: value},        # A 的预注册常量 / C 的 12 参数
  "weights": [float] | None,      # B 的 30 维
  "prompt_version": str,          # 生成侧提示词版本（协议 §5 缓存身份）
  "measure": {4 项},              # L0-1 绑定：判官提示 / 抽取器 / 卡片 schema / 依据包哈希
  "measure_version": str,         # = bind_measure_version(measure)
}
```

## 三条纪律落在这个模块里

1. **L0-1 测量版本冻结**：`measure_version` 由 `measure` 的**四项**绑定哈希而来；
   改任一项 ⇒ `measure_version` 变 ⇒ 全部历史读数作废（由 `optimizer.py` 的守卫 ⑥ 强制）。
2. **① 一次只改一个自由度**：`diff_configs()` 在变了 >1 个自由度时**抛异常**，
   不给「顺手多改一个」留缝。
3. **L2 搜索空间统一**：`free_degrees()` 给出「本 config 有哪些可动量」，
   A/B/C 走同一套接口。

## ⚠️ 本模块**不含**任何实验结论

`config.py` 只做「表示与判别」；所有读数都在 `optimizer.py` / `noise_floor.py` 里产生，
且必须由调用方显式传入测量实现。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys

ROUTES = ("A", "B", "C")

ROUTES_DIR = "/workspace/lab/routes"
ROUTE_A_PY = os.path.join(ROUTES_DIR, "A", "route_a.py")
ROUTE_B_OPS = os.path.join(ROUTES_DIR, "B", "code", "ops_v2.py")
C_DIR = os.path.dirname(os.path.abspath(__file__))

#: L0-1 的四项绑定（改任一项 ⇒ 测量带宽变 ⇒ 全部历史读数作废）
MEASURE_BINDING_FIELDS = (
    "judge_prompt_version",     # 判官提示词版本
    "extractor_version",        # 抽取器版本
    "card_schema_version",      # 卡片 schema 版本
    "evidence_hash",            # 依据包哈希（聚合）
)

#: ⚠️ **占位**绑定。真实 `measure_version` 必须由负责人在跑批前冻结；
#: `optimizer.py` 会把占位绑定标成 `measure_placeholder: true` 落进每条日志记录。
PLACEHOLDER_MEASURE = {
    "judge_prompt_version": "PLACEHOLDER-judge-v0",
    "extractor_version": "PLACEHOLDER-extractor-v0",
    "card_schema_version": "PLACEHOLDER-card-schema-v0",
    "evidence_hash": "PLACEHOLDER-evidence-hash",
}


class ConfigError(Exception):
    """config 层的基类错误。"""


class UnknownFreedom(ConfigError):
    """引用了不存在的自由度名。"""


class NoFreedomChanged(ConfigError):
    """两个 config 完全相同 ⇒ 没有任何可归因的改动。"""


class MultiFreedomChangeError(ConfigError):
    """两个 config 差了 >1 个自由度 ⇒ 归因不干净 ⇒ 拒绝（契约 ①）。

    :param changes: 全部变化的自由度名列表。
    """

    def __init__(self, changes):
        self.changes = list(changes)
        super().__init__("一次改了 %d 个自由度（%s）⇒ 违反契约 ①「一次只改一个自由度」"
                         % (len(self.changes), ", ".join(self.changes)))


class InvalidConfig(ConfigError):
    """config 不满足该路线的结构约束。"""


# --------------------------------------------------------------------------
# 路线 A：预注册常量（镜像自 A/route_a.py 的 DEFAULTS，§3.5 预注册常量表）
# --------------------------------------------------------------------------
# ⚠️ 契约 §0/§7 说 A 有「12 个预注册常量」；A/route_a.py 的 DEFAULTS **实际是 17 项**
#    （15 个标量 + 2 个 facet 列表）。本模块**不擅自裁剪成 12**（裁剪＝丢自由度），
#    而是暴露全部 17 项，并由 `test_optimizer.py` 的对账项保证「镜像不漂移」。
A_PARAMS = {
    "round1_facets": ["FA1", "FA2", "FA3", "FA4"],
    "round2_facets": ["FA5", "FA6"],
    "facet_enabled": True,
    "resample_mode": "structured",
    "novel_axis": True,
    "utility_axis": True,
    "max_calls": 24,
    "max_tokens": 60000,
    "max_claims": 48,
    "extract_cap": 8,
    "verify_batch": 12,
    "answer_char_cap": 400,
    "lex_thr": 0.75,
    "struct_thr": 0.70,
    "collapse_mult": 1.0,
    "temp": 0.7,
    "max_out_tokens": 6000,
}

#: A 的数值型（可连续/离散搜索）常量 —— 「12 vs 17」口径差异的定位用
A_NUMERIC_PARAMS = [k for k, v in A_PARAMS.items() if isinstance(v, (int, float))
                    and not isinstance(v, bool)]

#: A 的可枚举常量（离散档位）
A_ENUM_PARAMS = {
    "resample_mode": ("structured", "structured_no_cover", "random", "none"),
    "facet_enabled": (True, False),
    "novel_axis": (True, False),
    "utility_axis": (True, False),
}

#: A 的预注册常量**取值域**（用于生成候选）；列表型常量只能整体替换
A_PARAM_DOMAIN = {
    "max_calls": (8, 12, 16, 24, 32),
    "max_tokens": (20000, 40000, 60000, 80000),
    "max_claims": (24, 32, 48, 64),
    "extract_cap": (4, 6, 8, 12),
    "verify_batch": (6, 12, 16, 24),
    "answer_char_cap": (200, 300, 400, 500),
    "lex_thr": (0.60, 0.70, 0.75, 0.80, 0.90),
    "struct_thr": (0.50, 0.60, 0.70, 0.80, 0.90),
    "collapse_mult": (0.8, 0.9, 1.0, 1.1),
    "temp": (0.0, 0.3, 0.5, 0.7),
    "max_out_tokens": (3000, 4000, 6000, 8000),
    "facet_enabled": (True, False),
    "novel_axis": (True, False),
    "utility_axis": (True, False),
    "resample_mode": ("structured", "structured_no_cover", "random", "none"),
}

#: A 的 prompt 版本（与 A/spec.yaml 的 constants 段同源）
A_PROMPT_VERSION = "ROUTE-A-prompt-v2.0"
B_PROMPT_VERSION = "ROUTE-B-prompt-v2.0"
C_PROMPT_VERSION = "ROUTE-C-prompt-v1.0"

#: B 的权重维数（与 B/code/ops_v2.py 的 FEAT_DIM 同源，见 `b_weight_names`）
B_WEIGHT_DIM = 30


# --------------------------------------------------------------------------
# 路线 B：30 维权重的名字（从 ops_v2.py 的**源码**静态取出，不 import cmp8repo）
# --------------------------------------------------------------------------
def _literal_assignments(path: str, names) -> dict:
    """用 AST 取模块顶层的字面量赋值（不执行模块 ⇒ 无副作用、不碰 cmp8repo）。"""
    out = {}
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id in names:
                try:
                    out[tgt.id] = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    pass
    return out


def b_weight_names(path: str = ROUTE_B_OPS) -> list:
    """B 的 30 维权重名（复刻 ops_v2.py 头部的特征布局注释）。

    ⚠️ **刻意不 import `ops_v2`**：它会 import `cmp8repo/creativity_lab/ops`，
    而 cmp8repo 有正在跑的进程依赖（硬约束：不得改动它）。
    这里用 AST 只取 `OPS_V2` 与 `CLASSES` 两个**字面量元组**，再按
    ops_v2.py 头部注释里写明的布局重算名字（与 `FEATURE_NAMES` 逐项同序）。
    """
    got = _literal_assignments(path, {"OPS_V2", "CLASSES"})
    ops = list(got.get("OPS_V2") or [])
    classes = list(got.get("CLASSES") or [])
    if not ops or not classes:
        raise ConfigError("无法从 %s 静态取出 OPS_V2/CLASSES" % path)
    names = ["op[%s]" % o for o in ops]
    for g in ("g1_no_claims", "g2_unverified", "g3_uncovered", "g4_zero_supported"):
        names += ["%s×%s" % (c, g) for c in classes]
    for t in ("t1_tgt_unverified", "t2_tgt_unmentioned"):
        names += ["%s×%s" % (c, t) for c in classes]
    if len(names) != B_WEIGHT_DIM:
        raise ConfigError("重建出的权重名 %d 个 ≠ %d" % (len(names), B_WEIGHT_DIM))
    return names


# --------------------------------------------------------------------------
# 路线 C：12 参数 + 6 拓扑（**唯一来源是 C/params.py 与 C/topology.py**）
# --------------------------------------------------------------------------
def _c_params_module():
    if C_DIR not in sys.path:
        sys.path.insert(0, C_DIR)
    import params as P  # noqa: E402  （C/params.py：无副作用）
    return P


def _c_topology_module():
    if C_DIR not in sys.path:
        sys.path.insert(0, C_DIR)
    import topology as T  # noqa: E402
    return T


# --------------------------------------------------------------------------
# L0-1：measure_version 绑定
# --------------------------------------------------------------------------
def bind_measure_version(measure: dict) -> str:
    """把四项绑定哈希成一个 `measure_version`（契约 L0-1）。

    改任一项 ⇒ 本函数输出变 ⇒ 全部历史读数作废（由 optimizer 的守卫 ⑥ 强制）。
    """
    missing = [f for f in MEASURE_BINDING_FIELDS if f not in (measure or {})]
    if missing:
        raise InvalidConfig("measure 绑定缺字段：%s" % ", ".join(missing))
    blob = json.dumps({f: measure[f] for f in MEASURE_BINDING_FIELDS},
                      sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def is_placeholder_measure(measure: dict) -> bool:
    """绑定里是否还带着占位值（⇒ `measure_version` 未真正冻结）。"""
    return any(str((measure or {}).get(f, "")).startswith("PLACEHOLDER")
               for f in MEASURE_BINDING_FIELDS)


def dev_measure_binding(devset_path: str = os.path.join(ROUTES_DIR, "DEV", "devset.json"),
                        judge_prompt_version: str = "PLACEHOLDER-judge-v0",
                        extractor_version: str = "PLACEHOLDER-extractor-v0",
                        card_schema_version: str = "PLACEHOLDER-card-schema-v0") -> dict:
    """给 DEV 集拼一份 measure 绑定（依据包哈希取自冻结的 devset.json）。"""
    with open(devset_path, encoding="utf-8") as f:
        ds = json.load(f)
    per = [(t.get("task_id"), t.get("evidence_hash")) for t in ds.get("tasks") or []]
    blob = json.dumps(per, sort_keys=True, ensure_ascii=False, default=str)
    ev_hash = "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return {
        "judge_prompt_version": judge_prompt_version,
        "extractor_version": extractor_version,
        "card_schema_version": card_schema_version,
        "evidence_hash": ev_hash,
    }


# --------------------------------------------------------------------------
# 造 config
# --------------------------------------------------------------------------
def make_config(route: str, *, topology=None, params=None, weights=None,
                prompt_version=None, measure=None) -> dict:
    """造一个统一格式的 config。

    参数
    ----
    route : "A" | "B" | "C"
    topology : 覆盖默认拓扑（C：默认 T2）
    params : 覆盖路线默认参数
    weights : 覆盖 B 的 30 维权重
    prompt_version : 覆盖生成侧提示版本
    measure : 四项绑定；不给 ⇒ 用**占位**绑定（⇒ `measure_version` 未冻结）
    """
    if route not in ROUTES:
        raise InvalidConfig("route 必须是 %s 之一，收到 %r" % (ROUTES, route))

    if route == "A":
        p = dict(A_PARAMS)
        topo = None
        w = None
        pv = prompt_version or A_PROMPT_VERSION
    elif route == "B":
        p = {}
        topo = None
        w = list(weights) if weights is not None else [0.0] * B_WEIGHT_DIM
        if len(w) != B_WEIGHT_DIM:
            raise InvalidConfig("B 的权重必须是 %d 维，收到 %d" % (B_WEIGHT_DIM, len(w)))
        pv = prompt_version or B_PROMPT_VERSION
    else:  # C
        P = _c_params_module()
        T = _c_topology_module()
        p = P.default_theta()
        topo = topology or T.DEFAULT_TOPOLOGY
        w = None
        pv = prompt_version or C_PROMPT_VERSION

    if params:
        p.update(params)
    if topology is not None and route == "C":
        topo = topology
    if weights is not None and route == "B":
        w = list(weights)

    m = dict(measure) if measure else dict(PLACEHOLDER_MEASURE)
    cfg = {
        "route": route,
        "topology": topo,
        "params": p,
        "weights": w,
        "prompt_version": pv,
        "measure": {f: m[f] for f in MEASURE_BINDING_FIELDS},
    }
    cfg["measure_version"] = bind_measure_version(cfg["measure"])
    return cfg


def config_hash(cfg: dict) -> str:
    """整个 config 的稳定哈希（JSON 规范化 ⇒ 键序无关）。"""
    blob = json.dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# 自由度：列出 / 读 / 写 / 比对
# --------------------------------------------------------------------------
def _measure_changed(a: dict, b: dict) -> bool:
    return any((a.get("measure") or {}).get(f) != (b.get("measure") or {}).get(f)
               for f in MEASURE_BINDING_FIELDS)


def free_degrees(cfg: dict) -> list:
    """本 config **可动**的自由度名（`measure_version` 不在其中：它被 L0-1 冻结）。

    ⚠️ 路线 C：只列**当前拓扑下活着**的参数（契约 §3：「12（默认拓扑下活 7）」）
    —— 死参数改动不产生行为差异（`params.degenerate()` 的同一判据），动它没有归因价值。
    """
    out = []
    route = cfg.get("route")
    pmap = cfg.get("params") or {}
    if route == "C":
        P = _c_params_module()
        topo = cfg.get("topology")
        live = {p["name"] for p in P.live_params(topo)} if topo else set(pmap)
        for k in sorted(pmap):
            if k in live:
                out.append("params.%s" % k)
    else:
        for k in sorted(pmap):
            out.append("params.%s" % k)
    w = cfg.get("weights")
    if w:
        out += ["weights.w%02d" % i for i in range(len(w))]
    if cfg.get("topology") is not None:
        out.append("topology")
    out.append("prompt_version")
    return out


def get_freedom(cfg: dict, name: str):
    if name.startswith("params."):
        k = name.split(".", 1)[1]
        if k not in (cfg.get("params") or {}):
            raise UnknownFreedom("没有这个参数自由度：%s" % name)
        return cfg["params"][k]
    if name.startswith("weights."):
        idx = name.split(".", 1)[1]
        if not idx.startswith("w"):
            raise UnknownFreedom("权重自由度名应是 weights.wNN：%s" % name)
        i = int(idx[1:])
        w = cfg.get("weights") or []
        if not (0 <= i < len(w)):
            raise UnknownFreedom("权重维度越界：%s" % name)
        return w[i]
    if name == "topology":
        return cfg.get("topology")
    if name == "prompt_version":
        return cfg.get("prompt_version")
    raise UnknownFreedom("未知自由度名：%s" % name)


def set_freedom(cfg: dict, name: str, value):
    """返回**新** config（不改原对象），只动一个自由度。"""
    out = json.loads(json.dumps(cfg, ensure_ascii=False, default=str))
    if name.startswith("params."):
        k = name.split(".", 1)[1]
        if k not in (out.get("params") or {}):
            raise UnknownFreedom("没有这个参数自由度：%s" % name)
        out["params"][k] = value
    elif name.startswith("weights."):
        idx = name.split(".", 1)[1]
        if not idx.startswith("w"):
            raise UnknownFreedom("权重自由度名应是 weights.wNN：%s" % name)
        i = int(idx[1:])
        w = out.get("weights") or []
        if not (0 <= i < len(w)):
            raise UnknownFreedom("权重维度越界：%s" % name)
        w[i] = value
    elif name == "topology":
        out["topology"] = value
    elif name == "prompt_version":
        out["prompt_version"] = value
    else:
        raise UnknownFreedom("未知自由度名：%s" % name)
    return out


def diff_configs(a: dict, b: dict) -> str:
    """两个 config 之间**唯一**变化的自由度名。

    ⚠️ 契约 ①：一次只改一个自由度。
      * 0 处变化 ⇒ 抛 `NoFreedomChanged`（没有可归因的改动）
      * >1 处变化 ⇒ 抛 `MultiFreedomChangeError`（归因不干净 ⇒ 拒绝）
      * `measure_version` 是**逻辑自由度**：四项绑定里任意一项变了都算它变（仍是 1 个）
    """
    changes = []
    if a.get("route") != b.get("route"):
        changes.append("route")
    if a.get("topology") != b.get("topology"):
        changes.append("topology")
    if a.get("prompt_version") != b.get("prompt_version"):
        changes.append("prompt_version")
    if _measure_changed(a, b):
        changes.append("measure_version")

    ka, kb = a.get("params") or {}, b.get("params") or {}
    for k in sorted(set(ka) | set(kb)):
        if ka.get(k) != kb.get(k):
            changes.append("params.%s" % k)

    wa, wb = a.get("weights") or [], b.get("weights") or []
    for i in range(max(len(wa), len(wb))):
        x = wa[i] if i < len(wa) else None
        y = wb[i] if i < len(wb) else None
        if x != y:
            changes.append("weights.w%02d" % i)

    if not changes:
        raise NoFreedomChanged("两个 config 完全相同 ⇒ 没有可归因的改动")
    if len(changes) > 1:
        raise MultiFreedomChangeError(changes)
    return changes[0]


# --------------------------------------------------------------------------
# 结构校验
# --------------------------------------------------------------------------
def validate_config(cfg: dict) -> list:
    """返回违规说明列表（空 = 合法）。"""
    bad = []
    route = cfg.get("route")
    if route not in ROUTES:
        bad.append("route 非法：%r" % route)
        return bad
    if route == "C":
        P = _c_params_module()
        T = _c_topology_module()
        topo = cfg.get("topology")
        if topo not in T.TEMPLATE_IDS:
            bad.append("拓扑 %r 不在 %s 里" % (topo, T.TEMPLATE_IDS))
        else:
            bad += ["C 参数：%s" % x for x in P.validate(cfg.get("params") or {}, topo)]
    if route == "B":
        w = cfg.get("weights")
        if not w or len(w) != B_WEIGHT_DIM:
            bad.append("B 权重必须是 %d 维" % B_WEIGHT_DIM)
    if route == "A":
        for k in A_PARAMS:
            if k not in (cfg.get("params") or {}):
                bad.append("A 缺预注册常量 %s" % k)
    return bad


def route_default_config(route: str, **kw) -> dict:
    """某路线的默认 config（= 搜索的起点）。"""
    return make_config(route, **kw)


if __name__ == "__main__":
    for r in ROUTES:
        c = make_config(r)
        print("%s  hash=%s  自由度 %d 个  measure_version=%s"
              % (r, config_hash(c), len(free_degrees(c)), c["measure_version"]))
    c = make_config("C")
    c2 = set_freedom(c, "params.n_frames", 5)
    print("单自由度改动 →", diff_configs(c, c2))
    c3 = set_freedom(c2, "params.n_cand_per_frame", 2)
    try:
        diff_configs(c, c3)
    except MultiFreedomChangeError as e:
        print("双自由度改动 → 正确拒绝：%s" % e)
    print("B 的权重名（静态取出）：", b_weight_names()[:3], "...")
