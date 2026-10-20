# -*- coding: utf-8 -*-
"""路线 C · 可训练参数表（参数空间的唯一定义处）。

**拓扑与参数的分离判据**（DESIGN.md §2）：
一个元素属于**参数**当且仅当它是「模板实例化时的数值」——
改变它**不会**改变「有哪些阶段、谁能看到什么」；
它的取值域是**区间或有限档位**，由训练在数据上选。

**灰区处理**：既有第三类「冻结资产」（FROZEN_ASSETS）——
它既不是拓扑也不是参数（例如冻结认知位置清单、抽取/判官提示词、装配模板），
在训练开始前冻结、所有臂共用，保证跨臂可比。

⚠️ **温度不在本表内**：共享协议 §4.3 规定生成臂 temperature 事前写死且三臂一致 ⇒
把温度当参数会破坏跨臂可比性 ⇒ 本路线显式**排除**该参数（DESIGN.md §4.2 的偏离说明）。
"""
from __future__ import annotations

import hashlib
import json

# --------------------------------------------------------------------------
# 参数表
# --------------------------------------------------------------------------
# type: int（有限档位） | cont（连续区间，端点含）
# applies_to: 只有这些拓扑里该参数才"活着"（其余拓扑下它被固定为 default）
PARAM_SPEC = [
    dict(id="P1", name="n_frames", type="int", values=[1, 2, 3, 4, 5], default=3,
         group="breadth", applies_to=["T2", "T3", "T4", "T5"],
         desc="生成路数：1 条直答 + (n_frames-1) 个冻结认知位置。仅影响生成侧多样性。"),
    dict(id="P2", name="n_cand_per_frame", type="int", values=[1, 2, 3], default=1,
         group="breadth", applies_to=["T1", "T2", "T3", "T4", "T5"],
         desc="每路采样份数。=1 时每路只采一次；>1 时取该路去重后的全部候选。"),
    dict(id="P3", name="theta_util", type="cont", lo=0.0, hi=1.0, default=0.50,
         group="gate", applies_to=["T1", "T2", "T3", "T4", "T5"],
         desc="效用门控阈值（D2 的 theta_util）。判官判「支持」=1.0；「未提及/非主张/矛盾」=0.0。"),
    dict(id="P4", name="theta_dist", type="cont", lo=0.25, hi=1.0, default=0.25,
         group="gate", applies_to=["T2", "T3", "T4", "T5"],
         desc=("远端门控下限（D1 的 d*）：新候选与已保留候选的**最小距离**"
               "（距离 = 1 − 字面二元组 Jaccard）。0.25 = 只做基础去重；越大越严。"
               "⚠️ 它是**生成侧的多样性门**，不是宽度指标。")),
    dict(id="P5", name="n_verify_max", type="int", values=[0, 2, 4, 6, 8, 12], default=6,
         group="budget", applies_to=["T1", "T2", "T3", "T4", "T5"],
         desc="VERIFY 阶段最多核验多少条断言（预算分配）。"),
    dict(id="P6", name="n_split_max", type="int", values=[0, 1, 2, 4], default=0,
         group="budget", applies_to=["T3", "T4", "T5"],
         desc="SPLIT 阶段最多拆分多少条复合断言（拆完重新核验）。"),
    dict(id="P7", name="stall_window", type="int", values=[1, 2, 3, 4], default=2,
         group="stall", applies_to=["T4"],
         desc="停滞检测窗口 k：连续 k 轮「无新增被支持断言」即判停滞。"),
    dict(id="P8", name="theta_stall", type="cont", lo=0.0, hi=1.0, default=0.50,
         group="stall", applies_to=["T4"],
         desc="停滞判定阈值：窗口内「新增被支持断言 / 已核验断言」的最小值。"),
    dict(id="P9", name="realloc_frac", type="cont", lo=0.0, hi=1.0, default=0.0,
         group="stall", applies_to=["T4"],
         desc="停滞触发后，把剩余预算的多少比例重新分配给未覆盖的认知位置。"),
    dict(id="P10", name="theta_collapse", type="cont", lo=0.0, hi=1.0, default=0.0,
         group="trigger", applies_to=["T5"],
         desc="坍缩检测阈值 tau（D6）。默认 0.0 = 关闭 ⇒ 多数任务走 passthrough（什么都不做）。"),
    dict(id="P11", name="m_clusters", type="int", values=[1, 2, 3, 4, 6, 8], default=4,
         group="assembly", applies_to=["T1", "T2", "T3", "T4", "T5"],
         desc="装配进最终答案的聚类代表数（D5 的 m）。"),
    dict(id="P12", name="stop_patience", type="int", values=[0, 1, 2, 3], default=1,
         group="budget", applies_to=["T1", "T2", "T3", "T4", "T5"],
         desc="STOP 耐心：连续多少轮无新增被支持断言后停止继续展开。"),
]

# --------------------------------------------------------------------------
# 冻结资产（既不是拓扑也不是参数；所有臂共用，训练不碰）
# --------------------------------------------------------------------------
FROZEN_ASSETS = {
    "frames": [
        "规则来源与适用条件",
        "程序步骤与时限",
        "例外情形与边界条件",
        "数量阈值与计算关系",
        "主体之间的权利义务关系",
        "证据覆盖与信息缺口",
    ],
    "gen_prompt": ("问题：{ask}\n\n{ang}\n\n给出你的判断与具体做法，{cap}字以内。"),
    "extract_prompt": (
        "从下面这段回答里，逐条列出其中**可判真假的陈述**（数字、法规、权利义务、"
        "程序、时限、主体责任、事实断言）。不要观点和建议。一行一条，最多 {n} 条。\n\n{t}"),
    "split_prompt": ("把下面这条陈述拆成可以分别核验的独立陈述（如果它含多个断言就拆开）。"
                     "一行一条，只输出拆分结果。\n\n{c}"),
    "answer_cap_chars": 400,
    "judge_prompt_version": "train-judge-v1（训练侧判官，与验收侧判官不同源）",
    "distance_metric": "char_bigram_jaccard（不依赖 embedding ⇒ 不依赖厂商）",
}

PARAM_BY_ID = {p["id"]: p for p in PARAM_SPEC}
PARAM_BY_NAME = {p["name"]: p for p in PARAM_SPEC}


def alphabet(p: dict) -> list:
    """该参数的取值档位。int → 有限档位；cont → 5 档等距采样（含端点）。"""
    if p["type"] == "int":
        return list(p["values"])
    lo, hi = p["lo"], p["hi"]
    return [round(lo + (hi - lo) * i / 4.0, 4) for i in range(5)]


def default_theta() -> dict:
    return {p["name"]: p["default"] for p in PARAM_SPEC}


def live_params(topology_id: str) -> list:
    """在该拓扑下"活着"的参数（其余参数被固定为先验默认值，不参与搜索）。"""
    return [p for p in PARAM_SPEC if topology_id in p["applies_to"]]


def validate(theta: dict, topology_id: str) -> list:
    """返回违规说明列表（空 = 合法）。"""
    bad = []
    for p in PARAM_SPEC:
        if p["name"] not in theta:
            bad.append("缺参数 %s" % p["name"])
            continue
        v = theta[p["name"]]
        if p["type"] == "int":
            if v not in p["values"]:
                bad.append("%s=%r 不在档位 %s" % (p["name"], v, p["values"]))
        else:
            if not (p["lo"] <= v <= p["hi"]):
                bad.append("%s=%r 越界 [%s,%s]" % (p["name"], v, p["lo"], p["hi"]))
    # 退化配置过滤：装配数超过可交付的断言数上限 ⇒ 退化成"灌水"配置
    if theta.get("m_clusters", 1) < 1:
        bad.append("m_clusters<1")
    if theta.get("n_frames", 1) < 1:
        bad.append("n_frames<1")
    return bad


def degenerate(theta: dict, topology_id: str) -> list:
    """退化配置检查：会让拓扑塌回更简单的结构（等价于换了拓扑）。"""
    out = []
    if topology_id in ("T2", "T3", "T4", "T5") and theta.get("n_frames", 1) == 1:
        out.append("n_frames=1 ⇒ 多帧结构塌成单路（等价于 T1）")
    if topology_id in ("T3", "T4", "T5") and theta.get("n_split_max", 0) == 0:
        out.append("n_split_max=0 ⇒ 拆分回环失效（等价于 T2）")
    if topology_id == "T4" and theta.get("realloc_frac", 0.0) == 0.0:
        out.append("realloc_frac=0 ⇒ 预算重分配失效（等价于 T3）")
    if topology_id == "T5" and theta.get("theta_collapse", 0.0) == 0.0:
        out.append("theta_collapse=0 ⇒ 条件分支永不触发（等价于 T1）")
    return out


def theta_hash(theta: dict) -> str:
    blob = json.dumps({k: theta[k] for k in sorted(theta)}, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def table_markdown() -> str:
    rows = ["| ID | 参数 | 类型 | 取值域 | 先验默认 | 生效拓扑 | 说明 |",
            "|---|---|---|---|---|---|---|"]
    for p in PARAM_SPEC:
        if p["type"] == "int":
            dom = "int {" + ", ".join(str(v) for v in p["values"]) + "}"
        else:
            dom = "cont [%s, %s]" % (p["lo"], p["hi"])
        rows.append("| %s | `%s` | %s | %s | %s | %s | %s |" % (
            p["id"], p["name"], p["type"], dom, p["default"],
            ",".join(p["applies_to"]), p["desc"]))
    return "\n".join(rows)


if __name__ == "__main__":
    print(table_markdown())
    print()
    print("default theta hash:", theta_hash(default_theta()))
    for t in ("T0", "T1", "T2", "T3", "T4", "T5"):
        print(t, "live:", [p["name"] for p in live_params(t)])
