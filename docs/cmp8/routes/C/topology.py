# -*- coding: utf-8 -*-
"""路线 C · 拓扑模板菜单 + 结构检查器 + 行动空间说明书。

**拓扑的定义**（DESIGN.md §2）：拓扑 = 「有哪些阶段、阶段顺序、信息可达性、装配策略」。
改变拓扑元素的取值**会**改变图结构；改变参数**不会**。

模板菜单在**训练开始前冻结**，且**只变结构、不变内容资产**：
冻结认知位置清单、提示词模板、装配模板、判官/抽取器在所有模板间完全一致
⇒ 「拓扑析因」实验里结构是唯一变化的因子（归因干净）。

**硬约束检查器**（H1–H6）只查**结构**，**不查任何 oracle 统计**
——这是本项目「Agent 自主提案 3 轮 5 份全被否」教训的直接修复：
把"不能违反矛盾率"从"提案者的自觉"搬进"执行器的强制 + 提案的机器可查结构约束"。
"""
from __future__ import annotations

from params import FROZEN_ASSETS

# --------------------------------------------------------------------------
# 阶段定义（冻结）
# --------------------------------------------------------------------------
STAGES = {
    "GEN": "生成草稿（可多路：直答 + 冻结认知位置）",
    "EXTRACT": "从草稿抽原子断言",
    "VERIFY": "核验断言（唯一允许接触依据包/判官的阶段）",
    "SPLIT": "拆分复合断言并回灌核验",
    "REDISTRIBUTE": "条件切换式重组（换条件分布；❌ 不允许 sleep/放空/无关闲聊）",
    "MERGE": "机械装配最终答案（不由模型重写）",
}

# --------------------------------------------------------------------------
# 拓扑模板菜单（6 个，冻结）
# --------------------------------------------------------------------------
TEMPLATES = {
    "T0": dict(
        name="单答（零假设对照）",
        stages=["GEN", "MERGE"],
        merge_strategy="verbatim",
        n_frames_fixed=1,
        uses_verify=False,
        info_access={"GEN": "prompt_only", "MERGE": "draft_only"},
        rationale="无抽取、无核验 ⇒ 生成侧与有用侧都不可控。用途：拓扑析因的零假设下界。",
    ),
    "T1": dict(
        name="生成-抽取-核验-装配（有用侧最小实现）",
        stages=["GEN", "EXTRACT", "VERIFY", "MERGE"],
        merge_strategy="union_clustered",
        n_frames_fixed=1,
        uses_verify=True,
        info_access={"GEN": "prompt_only", "EXTRACT": "drafts",
                     "VERIFY": "evidence+claims", "MERGE": "verdicts+claims"},
        rationale="只实现 Mednick 的「有用」一侧 ⇒ 用作「远不可得」消融。",
    ),
    "T2": dict(
        name="多帧生成 + 抽取 + 核验 + 聚类装配（默认拓扑）",
        stages=["GEN", "EXTRACT", "VERIFY", "MERGE"],
        merge_strategy="union_clustered",
        n_frames_fixed=None,
        uses_verify=True,
        info_access={"GEN": "prompt_only", "EXTRACT": "drafts",
                     "VERIFY": "evidence+claims", "MERGE": "verdicts+claims"},
        rationale=("单路生成时「远」在结构上不可得（候选集 = 模型众数）⇒ "
                   "Mednick 合取条件无法同时满足 ⇒ 默认拓扑必须有多帧生成。"),
    ),
    "T3": dict(
        name="T2 + 拆分回环（复合断言拆开再核验）",
        stages=["GEN", "EXTRACT", "VERIFY", "SPLIT", "VERIFY", "MERGE"],
        merge_strategy="union_clustered",
        n_frames_fixed=None,
        uses_verify=True,
        info_access={"GEN": "prompt_only", "EXTRACT": "drafts",
                     "VERIFY": "evidence+claims", "SPLIT": "claims+verdicts",
                     "MERGE": "verdicts+claims"},
        rationale="把一条复合断言拆成可分别核验的独立断言 ⇒ 可能提高可承重粒度。",
    ),
    "T4": dict(
        name="T3 + 停滞域预算重分配",
        stages=["GEN", "EXTRACT", "VERIFY", "SPLIT", "VERIFY", "STALL", "MERGE"],
        merge_strategy="union_clustered",
        n_frames_fixed=None,
        uses_verify=True,
        info_access={"GEN": "prompt_only", "EXTRACT": "drafts",
                     "VERIFY": "evidence+claims", "SPLIT": "claims+verdicts",
                     "STALL": "claims+verdicts", "MERGE": "verdicts+claims"},
        rationale=("D4 的「无判据的重分配 = 随机游走」⇒ 停滞判据必须用**可核验信号**"
                   "（窗口内无新增被支持断言），不用 embedding 相似度。"),
    ),
    "T5": dict(
        name="生成空间校准 + 条件切换式重组（多数任务 passthrough）",
        stages=["GEN", "EXTRACT", "VERIFY", "COLLAPSE", "REDISTRIBUTE", "MERGE"],
        merge_strategy="union_clustered",
        n_frames_fixed=None,
        uses_verify=True,
        info_access={"GEN": "prompt_only", "EXTRACT": "drafts",
                     "VERIFY": "evidence+claims", "COLLAPSE": "claims",
                     "REDISTRIBUTE": "drafts+claims", "MERGE": "verdicts+claims"},
        rationale=("D6 的「大多数任务应当什么都不做」+ D3 的合法形式"
                   "（改写下次采样的条件分布；❌ 不加时间/无关闲聊）。"),
    ),
}

TEMPLATE_IDS = ["T0", "T1", "T2", "T3", "T4", "T5"]

# 本路线默认（人定）拓扑 —— 选择与理由**事前登记**在 DESIGN.md §3.1
DEFAULT_TOPOLOGY = "T2"

# --------------------------------------------------------------------------
# 硬约束检查器（H1–H6）：只看结构，不看任何 oracle 统计
# --------------------------------------------------------------------------
HARD_CONSTRAINTS = [
    ("H1", "必须存在生成阶段"),
    ("H2", "若含 VERIFY 阶段，则 VERIFY 必须在 MERGE 之前"),
    ("H3", "MERGE 阶段的输入必须只含断言与判官标签，不得含题面暗示/答案键"),
    ("H4", "总调用数上限 ≤ 14（每 episode）"),
    ("H5", "必须存在装配阶段（MERGE），且装配不得由模型重写"),
    ("H6", "不得出现「无状态等待/放空/与任务无关的闲聊」阶段（模拟走神）"),
]


def structural_check(spec: dict) -> list:
    """对一份拓扑规格做结构检查。返回违规说明列表（空 = 通过）。

    spec 形如 {"id": "Tx", "stages": [...], "merge_strategy": ..., "uses_verify": bool,
               "info_access": {...}}
    """
    bad = []
    st = list(spec.get("stages") or [])
    if "GEN" not in st:
        bad.append("H1 缺生成阶段")
    if "MERGE" not in st:
        bad.append("H5 缺装配阶段")
    if "VERIFY" in st and "MERGE" in st and st.index("VERIFY") > st.index("MERGE"):
        bad.append("H2 VERIFY 在 MERGE 之后")
    ia = spec.get("info_access") or {}
    if "MERGE" in ia:
        allowed = {"verdicts+claims", "draft_only"}
        if ia["MERGE"] not in allowed:
            bad.append("H3 MERGE 的输入集合不合法：%s" % ia["MERGE"])
    if len(st) > 8:
        bad.append("H4 阶段数过多")
    for s in st:
        if s in ("SLEEP", "IDLE", "WANDER", "REST"):
            bad.append("H6 出现无状态等待/放空阶段")
    return bad


def check_template(tid: str) -> list:
    return structural_check(TEMPLATES[tid])


def template_table_markdown() -> str:
    rows = ["| ID | 名称 | 阶段序列 | 装配策略 | 核验 | 生成路数 | 用途 |",
            "|---|---|---|---|---|---|---|"]
    for tid in TEMPLATE_IDS:
        t = TEMPLATES[tid]
        rows.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            tid, t["name"], " → ".join(t["stages"]), t["merge_strategy"],
            "是" if t["uses_verify"] else "否",
            "固定 1" if t["n_frames_fixed"] else "参数 P1",
            t["rationale"]))
    return "\n".join(rows)


# --------------------------------------------------------------------------
# 行动空间说明书（受约束提案器模式的输入）—— 全文模板
# --------------------------------------------------------------------------
ACTION_SPACE_MANUAL = """\
# 行动空间说明书（架构设计者用）

你要为一个「生成 → 核验 → 装配」的 Agent 挑选**一个执行拓扑**。
你**不能**发明新的阶段、新的操作、新的信息来源——你只能从下面这份**全集**里选一个。

## 一、可选拓扑全集（穷举，无其它选项）

%(templates)s

每个模板的字段含义：
- **阶段序列**：必须按给定顺序执行，不允许跳步、不允许重排。
- **装配策略**：机械装配，不由模型重写。
- **核验**：是否存在 VERIFY 阶段（唯一允许接触依据包与判官的阶段）。
- **生成路数**：「固定 1」= 只能单路生成；「参数 P1」= 路数由训练决定，拓扑只规定"多路存在"。

## 二、硬约束（机器检查，违反即拒收）

%(constraints)s

## 三、阶段含义

%(stages)s

## 四、你可以看到的信息（仅此三类）

1. 本说明书。
2. **结构性运行日志**：每阶段被调用了几次、是否超预算、是否出现空产出、是否解析失败、
   哪些阶段**从未被执行**（阶段覆盖表）。
3. 各拓扑的**定性**描述（上一节的「用途」列）。

## 五、你**看不到**的信息（硬边界）

- 任何题面、结论空间、依据包内容；
- 判官的逐条判定，以及由它们算出的任何统计量
  （矛盾率、支持率、有效维度数、承重卡数、关键结论命中率、去重宽度）；
- 任何跨臂比较数字、任何"哪条路线更好"的指标；
- 任何一次跑批的逐任务结果。

> 理由：诊断信号一旦含有 oracle 统计，提案者就会去钻指标的空子，
> 而不是去设计一个真的能展开更多承重维度的结构。

## 六、输出格式（必须严格遵守，否则解析失败）

第一行必须是：`TOPOLOGY: <模板ID>`
第二行必须是：`REASON: <不超过 60 字，说明这一选择解决了什么结构问题>`
不要输出其它内容。
"""

MANUAL_WITH_MENU = ACTION_SPACE_MANUAL % {
    "templates": template_table_markdown(),
    "constraints": "\n".join("  - %s %s" % (c, d) for c, d in HARD_CONSTRAINTS),
    "stages": "\n".join("  - %s：%s" % (k, v) for k, v in STAGES.items()),
}


def parse_proposal(text: str) -> dict:
    """解析提案者输出。**只接受格式与结构，不看内容对错。**"""
    import re
    t = (text or "").strip()
    m = re.search(r"TOPOLOGY:\s*([A-Za-z0-9_]+)", t)
    r = re.search(r"REASON:\s*(.+)", t)
    tid = m.group(1).strip().upper() if m else None
    ok = tid in TEMPLATE_IDS
    return {
        "template_id": tid if ok else None,
        "reason": (r.group(1).strip()[:120] if r else ""),
        "format_ok": bool(m and r),
        "struct_ok": ok and not check_template(tid) if ok else False,
        "raw_head": t[:200],
    }


if __name__ == "__main__":
    print(template_table_markdown())
    print()
    for tid in TEMPLATE_IDS:
        print(tid, "structural_check ->", check_template(tid) or "PASS")
    print()
    print("manual length(chars) =", len(MANUAL_WITH_MENU))
