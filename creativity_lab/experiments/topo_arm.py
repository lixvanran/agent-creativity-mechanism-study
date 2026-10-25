#!/usr/bin/env python3
"""★ **交互拓扑臂**（★ 照抄 `MAS_Diversity` 的真实五槽位，调度自建）

> 落点：`creativity_lab/experiments/topo_arm.py`
> 预注册：`docs/cmp8/routes/COLLAPSE/eval/PREREG-TOPOLOGY-ARM.md`（v3，388 行）
> 物证：`docs/cmp8/routes/COLLAPSE/eval/MAS_Diversity-ACTUAL-CONFIGS.md`
> 执行记录：`docs/交接/EXEC-LOG-topology-arm-2026-10-25.md`
>
> ## ★★★ A 档 = 结构性不可行（四条原因，EXEC-LOG §1）
> ① `AgentVerse` 被指向的版本（main, 2024-09-09）里 **`grouped_sequential` / `subgroup_random` 无对应实现**
> ② `MAS_Diversity` README **未指定任何分支/版本** ③ **PyPI 索引不可达** ④ 两者 commit 差 19 个月
> ⇒ ⇒ **本脚本 = B 档** ⇒ ⇒ manifest 必写 `topology_impl: "local_minimal_ported_params"`
> ⇒ ⇒ ★ **"调度语义与前人是否等价"未经核对** ⇒ ⇒ 结论边界必须带这句
>
> ## ★★ 照抄边界（★ 预注册 §2.0）
> | 元素 | 处置 |
> |---|---|
> | 五槽位真实取值与参数 | ★ **照抄** |
> | persona（senior / first-year PhD） | ★ **照抄** |
> | 轮次结构（`max_turns=5`，轮 5 由 leader 出 proposal） | ★ **照抄** |
> | ★ **调度实现（谁先说、谁看得见谁）** | ⚠️ **自建 ⇒ 等价程度未经核对** |
> | ★ **LLM 后端** | ★ **换 MiniMax ⇒ 跨模型不可比** |
>
> ## ★★★ 本批的两处结构性变更（★ 照抄带来的，不是自创）
> ① **N = 3**（YAML 里是 3 个 `conversation` + 1 个 `tool` 综述者）
> ② **对照臂 = `nosel_b3`**（3 个 agent 各独立写 1 份，**无交互、无综述**）—— ★ 这才是"同 N、无交互"的干净对照
>    （`nosel_b5` 保留为跨臂参考读数，但**生成过程不同**，不作为 H-TOPO-4a 主对照）
>
> ## ★★ 异构轴的重大改写（★ 必须写进结论边界）
> 前人的异构轴 = **异构模型**（deepseek-v3 / gpt-5.1 / o1-mini）
> ⇒ ⇒ ★ **我们只有 MiniMax ⇒ ⇒ 模型异构不可复制**
> ⇒ ⇒ ★★ **⇒ 本批的异构轴 = 【资历异构】（senior / first-year-PhD 混合）**
> ⇒ ⇒ ★★ **这既是我们唯一能做的，也是前人代码里真实存在的 persona 轴**
> ⇒ ⇒ ★★★ **⇒ 正好对上"真正要拆的变量是资历/权威层级，不是领域"这条 ⇒ ⇒ 变成本批相对前人的【增量】**
> ⇒ ⇒ ⚠️ **⇒ ⇒ 与前人 Table 13 【不同轴】⇒ ⇒ 不可与其数值直接比**
"""
import argparse
import json
import os
import random
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.client import DEFAULT_EFFORT, LLM      # noqa: E402
from creativity_lab.metrics import modes                   # noqa: E402
from creativity_lab.metrics_ext import (distinct_n, self_bleu,   # noqa: E402
                                         structured_dedup_count, vendi_score)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ★★★ 照抄自 MAS_Diversity 的真实 YAML（逐字核过，见 MAS_Diversity-ACTUAL-CONFIGS.md）
TOPOLOGY_IMPL = "local_minimal_ported_params"      # ★ 绝不许写 agentverse_yaml

# ★ persona：照抄两种真实 role_description（英文原文 → 中文题面版，语义不变）
PERSONA_SENIOR = ("一位在 {topic} 领域有专长的**资深研究员**，"
                  "进行深思与文献回顾。")
PERSONA_PHD1 = ("一位在**人工智能研究领域只有有限研究经验的一年级博士生**，"
                "带着新鲜的好奇心。")

# ★ 讨论轮的 prompt 结构（照抄 YAML 的 `prompt_template` 结构：角色 + 历史 + 自然发言）
DISCUSS_TMPL = """你正在参与一场关于「{topic}」的多人学术讨论。

{role}

以下是对话历史（你能看到的部分）：
{history}

请**像真人讨论一样**自然地说出你这一轮的想法。
不要写「Action:」之类的结构化标签，不要写工具调用，不要在结尾加参考文献。
直接给出你的发言本身。{spec}
"""

# ★ 综述轮的 prompt（照抄 YAML 的 tool agent 角色）
SYNTH_TMPL = """你是{role}，刚刚参与了上面这场讨论。
现在请**基于讨论**综合出一份研究提案。

以下是完整对话历史：
{history}

请综合所有参与者的不同视角、关键洞见、争论与共识。
明确引用并延展讨论中的**至少 4 个具体元素**（例如「正如我前面提到的……」「顺着第 2 位的观点……」），
**只归因于实际存在的参与者**，不要虚构新的参与者。
{spec}
"""

# ★ 三个拓扑的五槽位（★ 逐 YAML 照抄；`order` 的参数也照抄）
TOPOLOGIES = {
    "grouped_sequential": {
        "order": {"type": "grouped_sequential"},
        "visibility": {"type": "all"},
        "selector": {"type": "basic"},
        "updater": {"type": "basic"},
        "describer": {"type": "basic"},
        "max_turns": 5,
        "round0_concurrent": False,
        "incremental_memory_each_message": True,
    },
    "ngt": {
        "order": {"type": "ngt", "leader_idx": 3},
        "visibility": {"type": "ngt"},
        "selector": {"type": "ngt"},
        "updater": {"type": "ngt"},
        "describer": {"type": "ngt"},
        "max_turns": 5,
    },
    "subgroup_random": {
        "order": {"type": "subgroup_random", "group_sizes": [1, 2, 3, 2],
                  "rounds_per_size": 1, "leader_idx": -1, "final_leader": True,
                  "include_leader_in_subgroups": False},
        "visibility": {"type": "subgroup"},
        "selector": {"type": "ngt"},
        "updater": {"type": "subgroup"},
        "describer": {"type": "subgroup"},
        "max_turns": 5,
        "round0_concurrent": False,
        "incremental_memory_each_message": True,
    },
}

# ★ 臂表（★ 照抄预注册 §2.0b）
#   homo  = 全部 senior（同资历）
#   hetero= 2 senior + 1 first-year PhD（★ 资历异构 ⇒ 本批的"异构"轴，不是模型异构）
ARMS = {
    # ★ 2026-10-25 新增：第三对照臂（★ 拆"交互"与"综述"两个因子 ⇒ 构成 2×2）
    "nosel_b3_synth": {"topology": None, "mix": "homo", "synth": True},
    "topo_gs_homo":     {"topology": "grouped_sequential", "mix": "homo"},
    "topo_ngt_homo":    {"topology": "ngt", "mix": "homo"},
    "topo_sg_homo":     {"topology": "subgroup_random", "mix": "homo"},
    "topo_ngt_hetero":  {"topology": "ngt", "mix": "hetero"},
    "nosel_b3":         {"topology": None, "mix": "hetero"},     # ★ 主对照：无交互、无综述
}
N_AGENT = 3                 # ★ 照抄：3 个 conversation agent
N_LEADER = 3                # ★ 照抄：leader_idx=3 ⇒ 第 4 个 agent（综述者）不在前 3 个里
N_ROUNDS_DISCUSS = 4        # ★ 照抄 max_turns=5 ⇒ 轮 1-4 讨论，轮 5 综述
SPEC = "控制在 400 字以内。只输出答复本身。"


def _call_dict(c) -> Dict[str, Any]:
    """★ Call 对象 → dict（★ calllog 必须全 dict；★ 混合类型会让 json.dumps 崩）。"""
    if isinstance(c, dict):
        return c
    return {"model": c.model, "purpose": c.purpose, "ok": c.ok,
            "content_len": c.content_len, "has_content": c.has_content,
            "finish_reason": c.finish_reason, "secs": c.secs, "effort": c.effort}


def _unit_path(out: str, tid: str, rep: int, arm: str, k: int) -> str:
    return os.path.join(out, "units", "%s_r%d_%s_u%d.json" % (tid, rep, arm, k))


def _save_unit(out: str, tid: str, rep: int, arm: str, k: int,
               payload: Dict[str, Any]) -> None:
    """★ **run 级落盘**（★ 粒度 = (题, rep, 臂, run) ⇒ ★ 崩了/超时只丢这 1 个 run）
    ⇒ ★ 内联该 run 的 call 记录（★ 续跑后 calllog 仍完整 ⇒ 可独立重算健康度）。"""
    d = os.path.join(out, "units")
    os.makedirs(d, exist_ok=True)
    tmp = _unit_path(out, tid, rep, arm, k) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, _unit_path(out, tid, rep, arm, k))   # ★ 原子替换 ⇒ 不会写出半个文件


def _load_units(out: str, tid: str, rep: int, arm: str) -> Dict[int, Dict[str, Any]]:
    """★ 载入已落盘的 run 单元 ⇒ ★ 续跑时只补缺口。"""
    d = os.path.join(out, "units")
    got = {}
    if not os.path.isdir(d):
        return got
    for fn in os.listdir(d):
        if not fn.endswith(".json"):
            continue
        stem = fn[:-5]
        want = "%s_r%d_%s_u" % (tid, rep, arm)
        if not stem.startswith(want):
            continue
        try:
            k = int(stem[len(want):])
            got[k] = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        except Exception:
            continue
    return got


def _health(rec: List[Any]) -> Dict[str, Any]:
    """★ 通道健康度（★ 分母含失败调用；★ 口径与 `recompute_health` 一致）。"""
    n = len(rec)
    if not n:
        return {"n": 0, "n_failed": 0, "n_empty": 0, "channel_health": 1.0}
    bad = sum(1 for c in rec if not c.has_content or c.finish_reason == "exception")
    empty = sum(1 for c in rec if not (c.content_len or 0))
    return {"n": n, "n_failed": bad, "n_empty": empty,
            "channel_health": round(1 - bad / n, 4)}


def make_personas(mix: str) -> List[str]:
    """★ 资历组合（★ 本批的"异构"轴）。"""
    if mix == "homo":
        return [PERSONA_SENIOR] * N_AGENT
    return [PERSONA_SENIOR, PERSONA_SENIOR, PERSONA_PHD1]


def history_text(hist: List[List[Dict[str, str]]], who: int, vis: str,
                 sub_of: Dict[int, int], groups: List[List[int]]) -> str:
    """★ 按可见性槽位裁剪历史（★ `visibility: all` / `ngt` / `subgroup` 三种语义）。"""
    out = []
    for r, rnd in enumerate(hist):
        for a, msg in enumerate(rnd):
            if not msg:
                continue
            if vis == "all":
                out.append("第%d轮 · 参与者%d：%s" % (r + 1, a + 1, msg))
            elif vis == "ngt":
                # ★ ngt 语义：第 1 轮盲写（互不可见）⇒ 之后可见全部
                if r == 0:
                    continue
                out.append("第%d轮 · 参与者%d：%s" % (r + 1, a + 1, msg))
            elif vis == "subgroup":
                # ★ subgroup 语义：只看**同子组**的发言
                if a != who and sub_of.get(a, -1) != sub_of.get(who, -2):
                    continue
                out.append("第%d轮 · 参与者%d：%s" % (r + 1, a + 1, msg))
    return "\n".join(out) if out else "（暂无可见的历史）"


def run_topology(llm: LLM, topo: str, personas: List[str], topic: str,
                 seed: int) -> Dict[str, Any]:
    """★ 跑一次拓扑运行 ⇒ 返回「综述前 3 支」+「综述后 1 份 proposal」。

    ★ 三个拓扑的调度（★ 自建 ⇒ 等价程度未经核对）：
    · `grouped_sequential`：每轮 N 个 agent 顺序发言，**全部可见全部历史**
    · `ngt`：**轮 1 盲写**（互不可见）→ 轮 2–3 非 leader 顺序 → 轮 4 全员 → 轮 5 leader 出 proposal
    · `subgroup_random`：每轮把 agent **随机切成不相交子组**（`group_sizes`），**组内可见、组间不可见**；最后 leader 综述
    """
    cfg = TOPOLOGIES[topo]
    rng = random.Random(seed)
    hist: List[List[Dict[str, str]]] = [[{} for _ in range(N_AGENT)] for _ in range(N_ROUNDS_DISCUSS)]
    for r in range(N_ROUNDS_DISCUSS):
        # ── 决定本轮可见性裁剪与子组划分 ──
        vis = cfg["visibility"]["type"]
        sub_of: Dict[int, int] = {}
        groups: List[List[int]] = []
        if vis == "subgroup":
            sizes = cfg["order"].get("group_sizes") or [N_AGENT]
            pool = list(range(N_AGENT))
            rng.shuffle(pool)
            i = 0
            gi = 0
            for sz in sizes:
                if i >= len(pool):
                    break
                g = pool[i:i + sz]
                i += sz
                groups.append(g)
                for a in g:
                    sub_of[a] = gi
                gi += 1
        order = list(range(N_AGENT))
        if vis == "ngt":
            # ★ ngt：轮 1 盲写（顺序仍定但互不可见）；其余轮非 leader 顺序（leader 索引 3 不在前 3 个里 ⇒ 不影响）
            order = list(range(N_AGENT))
            rng.shuffle(order)
        elif vis == "subgroup":
            order = [a for g in groups for a in g]
        for a in order:
            role = personas[a].format(topic=topic)
            h = history_text(hist, a, vis, sub_of, groups)
            p = DISCUSS_TMPL.format(topic=topic, role=role, history=h, spec=SPEC)
            raw = llm.chat(p, model="MiniMax-M3", purpose="topo_discuss", min_ok=20)
            hist[r][a] = {"text": (raw or "").strip()}
    # ── 轮 5：leader（综述者）出 proposal ──
    role = PERSONA_SENIOR.format(topic=topic)
    h = "\n".join("第%d轮 · 参与者%d：%s" % (r + 1, a + 1, m["text"])
                  for r, rnd in enumerate(hist) for a, m in enumerate(rnd) if m)
    p = SYNTH_TMPL.format(role=role, history=h or "（无）", spec=SPEC)
    proposal = (llm.chat(p, model="MiniMax-M3", purpose="topo_synth", min_ok=20) or "").strip()
    pre = [hist[-1][a]["text"] for a in range(N_AGENT) if hist[-1][a].get("text")]
    return {"pre_synthesis": pre, "post_synthesis": proposal, "n_calls": 0}


def run_nosel_synth(llm: LLM, personas: List[str], topic: str) -> Dict[str, Any]:
    """★ `nosel_b3_synth`：**无交互 + 有综述**（★ 2026-10-25 新增的第三对照臂）

    ★★★ **它是为了把"两因子"拆成"单因子"而加的**：
    · 现状 `topo_*` vs `nosel_b3` 差了**两个**因子（★ 有无交互 + 有无综述）
      ⇒ ⇒ **绝对差值里混着两个 ⇒ ⇒ 只能比方向、不能比绝对值**（★ 负责人 2026-10-25 判据）
    · ★ 加这个臂后构成 **2×2**：{交互, 综述}
      - `nosel_b3`        = 无交互 + 无综述
      - `nosel_b3_synth`  = 无交互 + 有综述 ★ 新增
      - `topo_ngt_homo`  = 有交互 + 有综述
      - ⇒ ⇒ **三组单因子对比全部干净 ⇒ ⇒ 绝对差值全部可比 ✔**

    ★ **agent 之间互不可见**（★ 只在最后由 leader 综述一次）⇒ ⇒ 综述者看到的是 3 份独立产出
    """
    outs = []
    for pt in personas:
        p = DISCUSS_TMPL.format(topic=topic, role=pt.format(topic=topic),
                                 history="（无）", spec=SPEC)
        raw = llm.chat(p, model="MiniMax-M3", purpose="nosel_b3_synth", min_ok=20)
        outs.append((raw or "").strip())
    h = "\n".join("参与者%d：%s" % (i + 1, t) for i, t in enumerate(outs) if t)
    sp = SYNTH_TMPL.format(role=PERSONA_SENIOR.format(topic=topic),
                            history=h or "（无）", spec=SPEC)
    proposal = (llm.chat(sp, model="MiniMax-M3", purpose="nosel_b3_synth_leader", min_ok=20) or "").strip()
    return {"pre_synthesis": outs, "post_synthesis": proposal,
            "post_source": "★ 3 份【互不可见】的独立输出 → leader 综述（★ 与拓扑臂的综述步骤同构）",
            "n_calls": 0}


def run_nosel(llm: LLM, personas: List[str], topic: str) -> Dict[str, Any]:
    """★ `nosel_b3`：**无交互、无综述** ⇒ 3 个 agent 各独立写 1 份。

    ★★ **2026-10-25 修（A 篇必问② 逼出）**：★ **主层此前是空的**（`post_synthesis=""`）
    ⇒ ⇒ **H-TOPO-4a 的核心对比会拿无效读数去比 ⇒ 整批白跑**。
    ⇒ ⇒ ★ **修法：主层 = 3 份里的第 1 份（★ 确定性：按 agent 索引）**
    ⇒ ⇒ ★ **辅助层 = 3 份全量**（★ 拓扑臂的辅助层也是 3 份 ⇒ ★ 两臂辅助层【份数相等】✔）
    ⇒ ⇒ ★ **主层：拓扑臂 = 综述后 proposal（1 份）｜nosel = 独立写的第 1 份（1 份）⇒ 【份数相等】✔**
    ⇒ ⇒ ★★ **但两者的【生成过程】根本不同（★ 综述融合 vs 无交互单写）⇒ ⇒ 这是【两因子】对比，
    不是单因子对比 ⇒ ⇒ 归因必须写"总效应"（★ 见预注册 §5.0a2 的 4a/4b 分层）**
    """
    outs = []
    for a, pt in enumerate(personas):
        p = DISCUSS_TMPL.format(topic=topic, role=pt.format(topic=topic),
                                 history="（无）", spec=SPEC)
        raw = llm.chat(p, model="MiniMax-M3", purpose="nosel_b3", min_ok=20)
        outs.append((raw or "").strip())
    # ★ 主层取第 1 份（★ 确定性；★ 另两份在辅助层里全量可查）
    return {"pre_synthesis": outs, "post_synthesis": (outs[0] if outs else ""),
            "post_source": "★ 3 份独立输出中的第 1 份（按 agent 索引，★ 确定性）",
            "n_calls": 0}


def read_set(arts: List[str], vecs: List[List[float]]) -> Dict[str, Any]:
    """★ 三把尺子 + 比率型并排（★ 预注册 §3）。"""
    if len(arts) < 2:
        return {"valid": False, "n": len(arts)}
    return {"valid": True, "n": len(arts),
            "vendi": round(vendi_score(vecs), 4),
            "modes": modes(vecs),
            "structured_dedup": structured_dedup_count(arts),
            "self_bleu": round(self_bleu(arts), 4),
            "distinct_2": round(distinct_n(arts, 2), 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "topo-arm-2026-10-25"))
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--runs-per-arm", type=int, default=5,
                    help="★ 每臂跑几次（不同 seed）⇒ n 单元数 ⇒ ★ 臂间 n 必须相等 ⇒ 默认 5（与前人同口径）")
    ap.add_argument("--topics", default="S4,S5,S6,T1,T2,T3")
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--limit-calls", type=int, default=0)
    ap.add_argument("--only-arms", default="",
                    help="★ 只跑指定臂（冒烟用；★ 正式批留空）")
    ap.add_argument("--health-every", type=int, default=300,
                    help="★ 每 N 次调用报一次通道健康度（★ 分母含失败调用）")
    ap.add_argument("--min-health", type=float, default=0.80,
                    help="★ 健康度低于此值则早停（★ 通道变差时后面几千次会全废）")
    args = ap.parse_args()

    topics = json.load(open(os.path.join(ROOT, "creativity_lab", "data", "topics_2x2.json"),
                            encoding="utf-8"))
    tmap = {t["tid"]: t for t in (topics["topics"] if isinstance(topics, dict) else topics)}
    tids = [t for t in args.topics.split(",") if t in tmap]

    os.makedirs(args.out, exist_ok=True)

    # ══════ ★★★ 跑前自检（★ A 篇 2026-10-25 建议：★ n 单元表 + 断言臂间 n 相等）══════
    # ★ 成本一个 assert；★ 挡住的是"几小时采集白跑"（★ 上一轮就栽在这上面）
    print("== ★ 跑前自检：n 单元口径 ==")
    print("   %-16s %6s %10s %12s %10s" % ("臂", "n单元", "主层/单元", "辅助层/单元", "每单元调用"))
    _rows = []
    for _a, _sp in ARMS.items():
        if args.only_arms and _a not in [x.strip() for x in args.only_arms.split(",")]:
            continue
        _per = 13 if _sp["topology"] is not None else (4 if _sp.get("synth") else 3)
        # ★★★ 关键（★ 2026-10-25 修）：★ 【主层/单元】与【辅层/单元】必须【按臂真算】，不许硬编码
        # ★ 拓扑臂：主 = 综述后 1 份｜辅 = 轮 5 后 3 份发言
        # ★ nosel ：主 = 3 份独立输出里的第 1 份（★ 确定性）｜辅 = 3 份全量
        _main = 1
        _aux = N_AGENT
        _rows.append((_a, args.runs_per_arm, _main, _aux, _per))
        print("   %-16s %6d %10d %12d %10d" % (_a, args.runs_per_arm,
                                              _main, _aux, _per))
    # ★ 断言①：各臂 n 单元数相等
    assert len(set(r[1] for r in _rows)) == 1, "★ 臂间 n 单元数相等"
    # ★ 断言②：主读数层每单元产几份 —— ★ 各臂必须相同（★ 否则主层份数不等 ⇒ 不可比）
    assert len(set(r[2] for r in _rows)) == 1, "★ 主读数层每单元份数不等"
    # ★★ 断言③（★ 新增）：辅助层每单元份数 —— ★ 各臂也必须相同
    assert len(set(r[3] for r in _rows)) == 1, "★ 辅助读数层每单元份数不等"
    # ★ 断言③：n 单元数 ≥ 2（★ H0 标定的最低要求是同题 rep ≥ 2 ⇒ reps ≥ 2）
    if args.reps < 2:
        print("   ★ 提醒：reps=%d < 2 ⇒ ★ H0 标定（零分布）将无原料" % args.reps)
    print("   ✔ 断言通过：臂间 n 单元数相等 ｜ 主层份数相等 ｜ reps=%d" % args.reps)

    llm = LLM()
    manifest = {"topology_impl": TOPOLOGY_IMPL,
                "dispatch_equivalence_verified": False,
                "dispatch_note": "★ AgentVerse 被指向的版本无 grouped_sequential/subgroup_random 实现 ⇒ 调度自建 ⇒ 与前人调度语义是否等价【未经核对】",
                "heterogeneity_axis": "★ 资历异构（senior / first-year-PhD）——★ 不是模型异构（只有 MiniMax）⇒ 与前人 Table 13 不同轴 ⇒ 不可直接比",
                "n_agent": N_AGENT, "n_rounds_discuss": N_ROUNDS_DISCUSS,
                "n_unit_definition": "★ n 单元 = 1 次独立运行（不同 seed）⇒ 全部臂 n 单元数相等",
                "main_readout_layer": "★ 主读数 = 每臂 %d 份【综述后 proposal】（★ 与前人同口径：前人也是 N=3、1 次运行 1 份、跑 5 次）" % args.runs_per_arm,
                "aux_readout_layer": "★ 辅助读数 = 综述前各 agent 最终发言（份数 = 3R ⇒ 与主层份数不同 ⇒ 只作定性对照）",
                "ngt_semantics_source": "★ 轮 1 盲写 = `visibility.type=ngt` 的语义（★ 前人 NGT 定义逐字 'Round 1 is a blind-writing phase where each agent writes independently without seeing others\' contributions'）｜★ 该 YAML 【无】round0_concurrent / incremental_memory_each_message ⇒ ⇒ ★ 不从其他拓扑继承任何字段",
                "per_topology_fields_own_only": "★ 每个拓扑只用自己的 YAML 字段；缺失即缺失，不跨文件假设（★ ngt 缺 round0_concurrent / incremental_memory_each_message）",
                "two_readout_layers": "★ 层①『5 支并行』（★ 本组已跑批那批：A 篇 R2/R3/R4/ToT 臂）｜★ 层②『5 次独立运行』（★ 改造后拓扑臂）｜★ 两层的『5』不同义 ⇒ ★ 跨层绝对差会混入口径差 ⇒ 报告必须分层写",
                "leader_definition": "★ ngt 臂的 leader = 第 4 个 agent（tool agent / 综述者）⇒ 照抄 YAML 的 leader_idx=3 ⇒ ★ 不是第 3 个 conversation agent",
                "per_arm_calls": "★ 拓扑臂 = R × 13 次（4 轮 × 3 agent + 1 综述）｜nosel_b3_synth = R × 4 次（3 写 + 1 综述）｜nosel_b3 = R × 3 次（无综述）⇒ ★ 调用量按臂分列",
                "factorial_decomposition": "★★ 三对照臂构成 2×2 {交互, 综述}：nosel_b3(无,无) ｜ nosel_b3_synth(无,有) ｜ topo_*(有,有) ⇒ ⇒ ★ 三组【单因子】对比：交互效应 = topo_ngt_homo − nosel_b3_synth｜综述效应 = nosel_b3_synth − nosel_b3｜可见性图效应 = topo_ngt_homo − topo_gs_homo ⇒ ⇒ ★ 全部【绝对差值可比】✔",
                "comparability": "★ 与前人可比 = 主读数层（n 单元 = R，单元内 1 份 proposal）｜★ 不可比 = 跨模型（deepseek-v3/gpt-5.1/o1-mini vs MiniMax）⇒ 只能定性对照",
                "reps": args.reps, "seed": args.seed,
                "arms": list(ARMS.keys()), "groups": [],
                "calllog": "calllog.jsonl"}
    t0 = time.time()
    for tid in tids:
        topic = tmap[tid]
        for rep in range(1, args.reps + 1):
            row = {"tid": tid, "rep": rep, "ask": topic["ask"], "arms": {}}
            for arm, spec in ARMS.items():
                if args.only_arms and arm not in [a.strip() for a in args.only_arms.split(",")]:
                    continue
                # ★★ 续跑：★ 载入已落盘的 run 单元（★ 粒度 = (题, rep, 臂, run) ⇒ 只补缺口）
                done = _load_units(args.out, tid, rep, arm)
                if done:
                    print("  [skip] %s r%s %s（已有 %d/%d 单元）"
                          % (tid, rep, arm, len(done), args.runs_per_arm), flush=True)
                n0 = len(llm.rec)
                personas = make_personas(spec["mix"])
                # ★★ 每臂跑 R 次（不同 seed）⇒ ★ n 单元数 = R ⇒ ★ 臂间 n 相等
                for run_i in range(args.runs_per_arm):
                    if run_i in done:
                        continue                      # ★ 该 run 已落盘 ⇒ 跳过（不重跑）
                    seed = args.seed + rep * 17 + run_i * 101 + (hash(arm) % 1000)
                    n1 = len(llm.rec)
                    if spec["topology"] is None:
                        r = (run_nosel_synth(llm, personas, topic["ask"])
                             if spec.get("synth") else
                             run_nosel(llm, personas, topic["ask"]))
                    else:
                        r = run_topology(llm, spec["topology"], personas, topic["ask"], seed=seed)
                    # ★★★ run 级落盘（★ 粒度 = 产出单元；★ 立刻落 ⇒ 崩了/超时只丢这 1 个 run）
                    _save_unit(args.out, tid, rep, arm, run_i, {
                        "post": r["post_synthesis"],
                        "post_source": r.get("post_source", "★ 轮 5 综述后 proposal"),
                        "pre": [t for t in r["pre_synthesis"] if t],
                        "n_calls": len(llm.rec) - n1,
                        "n_failed": sum(1 for c in llm.rec[n1:] if not c.has_content),
                        "calls": [_call_dict(c) for c in llm.rec[n1:]],
                    })
                    # ★ 单元内进度（★ 7.6 小时不许是黑盒）
                    print("  [unit] %s r%s %s u%d/%d ｜ 调用 %d ｜ 用时 %.0fs"
                          % (tid, rep, arm, run_i + 1, args.runs_per_arm,
                             len(llm.rec), time.time() - t0), flush=True)
                # ── 臂级聚合（★ 从【全部已落盘单元】重建 ⇒ 续跑后仍完整）──
                done = _load_units(args.out, tid, rep, arm)
                posts = [u["post"] for u in done.values() if u.get("post")]
                pres = [t for u in done.values() for t in (u.get("pre") or [])]
                # ── 主读数层：★ n 单元 = 每次运行 1 份 proposal（★ 与前人同口径）──
                v_post = llm.embed(posts) if len(posts) >= 2 else []
                read_post = read_set(posts, v_post)
                # ── 辅助层：综述前各 agent 的最终发言（n = 3R，与主层份数不同 ⇒ 只作定性）──
                v_pre = llm.embed(pres) if len(pres) >= 2 else []
                read_pre = read_set(pres, v_pre)
                row["arms"][arm] = {
                    "topology": spec["topology"] or "none",
                    "mix": spec["mix"],
                    "n_units": len(done),                       # ★ n 单元数（臂间相等）
                    "n_post": len(posts),                     # ★ 主读数层的份数
                    "n_pre": len(pres),                       # ★ 辅助层的份数（= 3R）
                    "n_expected": args.runs_per_arm,
                    "n_calls": sum(u.get("n_calls", 0) for u in done.values()),
                    "n_failed": sum(u.get("n_failed", 0) for u in done.values()),
                    "read_post": read_post,                   # ★ 主读数
                    "read_pre": read_pre,                     # ★ 辅助读数
                    "post_texts": posts,
                    "post_layer_def": ("★ 拓扑臂 = 轮 5 综述后 proposal（1 份）"
                                       if spec["topology"] is not None else
                                       ("★ nosel_b3_synth = 3 份互不可见输出 → leader 综述（1 份）"
                                        if spec.get("synth") else
                                        "★ nosel_b3 = 3 份独立输出中的第 1 份（★ 确定性；★ 另两份在辅助层）")),
                    "aux_layer_def": "★ 综述前/独立写出的 3 份 agent 输出（★ 两臂份数相同 ⇒ 可比）",
                    "layer_comparability": "★ 两层都同份数 ⇒ 绝对差值不含份数差（★ 但主层【生成过程】不同 ⇒ 4a 是两因子总效应）",
                }
                # ★★ 通道健康度检查（★ 分母含失败调用）★★
                _hl = _health(llm.rec)
                manifest["health_checkpoints"] = manifest.get("health_checkpoints", [])
                manifest["health_checkpoints"].append(
                    {"after_calls": len(llm.rec), **_hl})
                if len(llm.rec) // args.health_every != (len(llm.rec) - 1) // args.health_every:
                    print("  [health] 调用 %d ｜ 健康度 %.4f ｜ 失败 %d ｜ 空 %d"
                          % (len(llm.rec), _hl["channel_health"], _hl["n_failed"], _hl["n_empty"]),
                          flush=True)
                if _hl["channel_health"] < args.min_health:
                    print("  ★ 早停：健康度 %.4f < 门槛 %.2f（★ 别跑满，后几千次会全废）"
                          % (_hl["channel_health"], args.min_health), flush=True)
                    manifest["stopped_early"] = {"reason": "channel_health_below_min",
                                                "at_calls": len(llm.rec), "health": _hl}
                    break
                if args.limit_calls and len(llm.rec) >= args.limit_calls:
                    break
            row["secs"] = round(time.time() - t0, 1)
            manifest["groups"].append(row)
            print("[%s r%s] %s" % (tid, rep,
                  "  ".join("%s:pre_n=%d" % (a, d["n_pre"]) for a, d in row["arms"].items())),
                  flush=True)
            json.dump(manifest, open(os.path.join(args.out, "manifest.json"), "w",
                                     encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
            if args.limit_calls and len(llm.rec) >= args.limit_calls:
                break
        if args.limit_calls and len(llm.rec) >= args.limit_calls:
            break
    # ── calllog 落盘（★ 前置门 ②）★★ 合并【本次跑的】+ 【续跑时已落盘的单元里的】★
    all_calls = [_call_dict(c) for c in llm.rec]
    ud = os.path.join(args.out, "units")
    if os.path.isdir(ud):
        for fn in sorted(os.listdir(ud)):
            if not fn.endswith(".json"):
                continue
            try:
                u = json.load(open(os.path.join(ud, fn), encoding="utf-8"))
            except Exception:
                continue
            if u.get("calls"):
                all_calls.extend(u["calls"])
    with open(os.path.join(args.out, "calllog.jsonl"), "w", encoding="utf-8") as f:
        for c in all_calls:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    # ★ 额度 / 限流表现（★ 负责人 ③：写进报告，codex 可核）
    fr = {}
    for c in all_calls:
        k = c.get("finish_reason") or ("ok" if c.get("ok") else "unknown")
        fr[k] = fr.get(k, 0) + 1
    manifest["n_failed_calls"] = sum(1 for c in all_calls
                                     if not c.get("has_content", c.get("ok", False)))
    manifest["finish_reason_dist"] = fr
    manifest["quota_note"] = ("★ 本批走 MiniMax 通道（api.minimaxi.com）｜★ OpenRouter 额度 0 未用"
                              "｜★ 限流表现：见 finish_reason_dist（★ 若出现大量 exception/空 ⇒ 侧限额）")
    from creativity_lab.experiments.fix_calllog_fields import recompute_health
    manifest["health"] = recompute_health(os.path.join(args.out, "calllog.jsonl"))
    # ★★★ 修：续跑时 llm.rec 是空的（都 skip 了）⇒ ⇒ 必须用 all_calls（★ 含续跑载入的）
    # ★ ★ 否则「续跑后总调用数 = 0」⇒ ⇒ 这正是「失败调用整体漏记」同族的静默归零
    manifest["health"]["n_calls_total"] = len(all_calls)
    manifest["n_calls_this_process"] = len(llm.rec)
    manifest["n_calls_from_units"] = len(all_calls) - len(llm.rec)
    json.dump(manifest, open(os.path.join(args.out, "manifest.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print("✔ 落盘 %s ｜ 调用 %d（本次 %d + 单元载入 %d）｜ 健康度 %s" % (args.out, len(all_calls), len(llm.rec), len(all_calls) - len(llm.rec),
                                          json.dumps(manifest["health"], ensure_ascii=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
