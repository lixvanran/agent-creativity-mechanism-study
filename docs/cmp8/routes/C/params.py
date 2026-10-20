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

★ **P12 `stop_patience` 已接上（2026-10-21，复核必修 6b 收尾）**：
复核实测该参数在 executor 里**没有任何读取点** ⇒ `stop_patience=0` 与 `=3` 产出**完全相同**
的答案 ⇒ 它是死参数。本轮**选择 (a) 接上**（而不是删掉），因为「何时停」是本路线
"搜索空间不过早闭合"这个核心命题的**可学版本**（若删掉，这条命题就只剩断言、没有旋钮）。

实现（`executor.py:Episode._deepen`，**真实存在**、有读取点、有行为差异）：
  - 「深挖步」= 换一个**已授权的认知位置**，用**深挖提示词**（冻结资产 `deep_suffix`）
    再问一次 → 抽取 → 核验。位置**不新增**（仍是 P1 授权的那几个）⇒ 不改变 P1 的语义，
    也不破坏 T1「远不可得」的消融（T1 只有「直答」一个位置，深挖只是对同一位置再问一次）。
  - 步数上限 = P12 `stop_patience`：`0` = **不深挖**（搜索空间在第一轮就闭合 ⇒ 这是
    "过早闭合"的对照臂），`k>0` = 最多再走 k 步。
  - 每步若**没有新增被支持断言**（= 没有新承重信息）⇒ 记一次「空转」；
    连续空转数 ≥ P7 `stall_window`（仅 T4）⇒ 判停滞 ⇒ 触发预算重分配并结束深挖。
  - 阶段**集合**不随 P12 变化（深挖复用已有的 GEN/EXTRACT/VERIFY 三个阶段）⇒
    分离判据仍然成立（改变 P12 不改变"有哪些阶段、谁能看到什么"）。

⚠️ **P7 `stall_window` 同轮接上**：复核只点了 P12，但接线自检（`check_wiring.py`）
把 P7 也抓出来了 —— 原实现里 `k` 只被用作 `k<=0` 的守卫，值域 {1,2,3,4} 全部行为相同
⇒ **同样是死参数**。现在 P7 是"连续空转窗口"的真参数（见上）。

（接上 P12 后的三个数：参数总数 **12**；默认拓扑 T2 下活着 **7** 个；
坐标下降评估 **68** 个配置 —— 2 轮 × 34 档，与 DESIGN §4.1/§4.5 一致。）
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
         desc=("停滞检测窗口 k（**连续空转计数**）：深挖回路里连续 k 步「无新增被支持断言」"
               "⇒ 判停滞 ⇒ 触发预算重分配（把剩余预算给未覆盖的认知位置）并结束深挖。"
               "⚠️ 只在出现空转步时才会触发（无空转 ⇒ 恒不触发），见 DESIGN §4.7 的诚实边界。")),
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
         group="stop", applies_to=["T1", "T2", "T3", "T4", "T5"],
         desc=("深挖耐心（**何时停**）：机械装配前最多再走几步「换已授权认知位置深挖 → "
               "抽取 → 核验」。0 = 不深挖 ⇒ 搜索空间在第一轮就闭合（=「过早闭合」对照臂）。")),
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
    # ★ 深挖提示词（2026-10-21 新增，冻结资产）：P12 `stop_patience` 的深挖步用它。
    #   它**不含**任何题面特征/答案暗示/评价标准，只是一句"更具体、可核验、别重复"的通用要求。
    "deep_suffix": ("再往前一步：在这个认知位置上，给出**更具体**的一条可核验的判断或做法"
                    "（要能落到具体的主体、数字、时限或条件），不要重复上面已经说过的内容。"),
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
