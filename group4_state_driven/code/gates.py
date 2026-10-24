#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 体裁守恒门 / 对象守恒门

═══ 为什么必须有这两个门 ═══
multi-mind v0.8 实测出的失败模式（原文）：

> 「工作流的『生成 + 对抗 + 递进约束』结构，会强迫模型产出一个比原始输入更『高级』的叙事 ——
> 于是它把用户的问题降格成了一个待分析的对象。」

两张脸：
1. **体裁漂移**：T3 要的是"一个焦虑的学生今晚怎么办"，工作流给的是
   「## 在候选之间怎么选」/「不可逆代价是真实比赛中最贵的成本」——**体裁被换成了决策文档**。
   根因在 **N2 的 schema**（强制每个候选给出「综合价值 = 收益 − 技术代价 − 合规代价 − …」）。
2. **对象漂移**：用户问"我可能是什么样"，工作流答"这组数据可能出自什么情境"——
   **分析对象从用户本人换成了数据**。

C1 状态机臂是**多步 + 递进约束**结构 ⇒ **正处在这个失败模式的射程内**。
⇒ 必须有自动门能发现"内容被换掉了"，否则 C1 的任何"效果"都可能是**体裁漂移的假象**。

═══ 本模块的性质 ═══
门是**机械代理**，不是判官：
· **体裁门**：产出里是否出现了"决策文档化"的特征词，而题面体裁是创作/表达类。
· **对象门**：题面主体词是否还在产出里；是否出现"元对象化"指代（这组数据 / 分析对象）。
零 LLM 参与、可复现、可审计。
★ 门只做**筛查**：报出"疑似漂移"并给出证据片段，**不自动判负**。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import runner as R
    TOPICS = {t["id"]: t for t in R.TOPICS}
except Exception:
    TOPICS = {}

# ---------------------------------------------------------------- 决策文档化特征
# ★ 分强弱两级 —— v1 实测假阳性："项目里程碑奖金"这类**正常中文**触发了弱标记，
#   把 S 臂误判成体裁漂移。**筛查器自己会骗人**，这是本项目的老主题。
# 强标记：单独出现即足以判定（都是决策文档的专有构造）
STRONG_MARKERS = [
    "综合价值", "决策树", "决策矩阵", "备选方案", "最优解", "次优解",
    "方案一", "方案二", "方案三", "方案1", "方案2", "方案3",
    "成本收益", "投入产出", "权衡利弊", "利弊分析",
    "以下是从三个角度",
]
# 弱标记：须 **≥2 个同时出现**（或带结构性上下文）才判定
WEAK_MARKERS = [
    "风险评估", "收益评估", "评分标准", "权重分配", "风险与收益",
    "可行性分析", "实施路径", "里程碑", "KPI", "ROI", "方案", "候选",
]
DECISION_DOC_MARKERS = STRONG_MARKERS + WEAK_MARKERS
# 元对象化指代（把"用户/当事人"换成"数据/材料"）
META_OBJECT_MARKERS = [
    "这组数据", "上述数据", "该数据", "这份数据", "这批数据", "该组数据",
    "分析对象", "研究对象", "材料显示", "数据表明", "样本中",
    "原始输入", "输入数据", "该样本",
]

# 题面主体词（题面里"是谁/是什么"，产出必须还以它为对象）
SUBJECT = {
    "T01": ["医保谈判代表", "谈判代表", "她"],
    "T02": ["平台", "商家", "商户", "骑手"],
    "T03": ["散步", "那条路", "走"],
    "T04": ["父亲", "他", "回家"],
    "T05": ["我们", "医院", "产品"],
    "T06": ["女儿", "父亲", "她"],
    "T07": ["bug", "工程师", "我"],
    "T08": ["他", "她", "我们"],
    "T09": ["图书馆", "预算"],
    "T10": ["我", "失业"],
}

# 体裁类别：创作/表达类 vs 事务/决策类
CREATIVE_GENRES = ("小说", "散文", "歌词", "悼词", "自述", "对话", "小品", "短文")


def is_creative_genre(topic: dict) -> bool:
    g = str(topic.get("genre") or "")
    return any(k in g for k in CREATIVE_GENRES)


def genre_gate(text: str, topic: dict) -> dict:
    """体裁守恒门：创作类题目里是否被漂移成了决策文档。"""
    if not is_creative_genre(topic):
        return {"applicable": False, "note": "非创作类体裁，不适用"}
    t = text or ""
    strong = [m for m in STRONG_MARKERS if m in t]
    weak = [m for m in WEAK_MARKERS if m in t]
    # 弱标记去重计数："方案"命中一次只算一次
    hits = strong + (weak if len(weak) >= 2 else [])
    # 决策文档的结构指纹：多行列表 + 编号
    numbered = len(re.findall(r"(?m)^\s*(?:[1-9][.、)]|[-*])\s*\S", text or ""))
    md_head = len(re.findall(r"(?m)^#{1,3}\s+\S", text or ""))
    drift = bool(strong) or len(weak) >= 2 or numbered >= 5 or md_head >= 2
    ev = ""
    if drift:
        i = min([(text or "").find(m) for m in hits if m in (text or "")] or [0])
        ev = (text or "")[max(0, i - 40):i + 90].replace("\n", " ")
    return {"applicable": True, "drift": drift, "markers": (strong + weak)[:6],
            "strong": strong[:4], "weak": weak[:4],
            "numbered_lines": numbered, "md_headings": md_head, "evidence": ev}


def subject_gate(text: str, topic: dict) -> dict:
    """对象守恒门：主体是否还在；是否被换成了"数据/材料"。"""
    tid = topic.get("id")
    subs = SUBJECT.get(tid, [])
    t = text or ""
    present = [s for s in subs if s in t]
    meta = [m for m in META_OBJECT_MARKERS if m in t]
    lost = bool(subs) and not present
    meta_hit = bool(meta)
    drift = lost or meta_hit
    ev = ""
    if meta_hit:
        i = t.find(meta[0])
        ev = t[max(0, i - 40):i + 90].replace("\n", " ")
    elif lost:
        ev = "主体词 %s 全部未出现" % "/".join(subs)
    return {"applicable": bool(subs), "drift": drift, "subjects": subs,
            "present": present, "lost": lost, "meta_markers": meta[:4],
            "evidence": ev}


def run_gates(text: str, topic: dict) -> dict:
    g = genre_gate(text, topic)
    s = subject_gate(text, topic)
    return {"genre_gate": g, "subject_gate": s,
            "any_drift": bool(g.get("drift")) or bool(s.get("drift"))}


# ---------------------------------------------------------------- 自检
def selftest(verbose: bool = True) -> dict:
    """门的自检：阳性（真的漂移了）必须被抓到，��性（正常创作）必须放过。"""
    res = {}

    def say(k, ok, detail=""):
        res[k] = {"pass": bool(ok), "detail": detail}
        if verbose:
            print("  %s %-30s %s" % ("✓" if ok else "✗", k, detail))

    t_creative = TOPICS.get("T01", {"id": "T01", "genre": "现实主义短篇小说片段"})
    t_business = TOPICS.get("T05", {"id": "T05", "genre": "商务邮件"})

    # 阳性1：决策文档化的正文
    bad = ("## 方案一：立即降价\n综合价值 = 收益 − 技术代价 − 合规代价\n"
           "1. 风险评估已完成\n2. 备选方案成本较低\n3. 最优解是暂不调整\n")
    g1 = genre_gate(bad, t_creative)
    say("体裁门阳性(创作题被写成决策文档)", g1["drift"], "markers=%s" % g1["markers"][:3])

    # 阴性1：正常的创作正文
    good = "十二点整，录音设备亮起红灯。谈判室里坐了九个人。她把报价单翻到第三页，\n指着一行数字停了很久。"
    g2 = genre_gate(good, t_creative)
    say("体裁门阴性(正常创作)", not g2["drift"], "markers=%s" % g2["markers"][:3])

    # 阳性2：对象被换成数据
    g3 = subject_gate("这组数据的分布呈现出明显的偏态，分析对象指向一个未标注的群体。", t_creative)
    say("对象门阳性(换成数据对象)", g3["drift"], "meta=%s lost=%s" % (g3["meta_markers"], g3["lost"]))

    # 阴性2：主体还在
    g4 = subject_gate(good, t_creative)
    say("对象门阴性(主体还在)", not g4["drift"], "present=%s" % g4["present"])

    # 阴性2b：**单个弱标记**（正常中文）不得误报
    g2b = genre_gate("桌上摆着一排矿泉水。她把笔帽拔下来，又盖回去。项目里程碑奖金发下来了。", t_creative)
    say("体裁门不误报单个弱标记", not g2b["drift"],
        "strong=%s weak=%s" % (g2b.get("strong"), g2b.get("weak")))

    # 阴性3：事务类体裁不适用体裁门
    g5 = genre_gate(bad, t_business)
    say("体裁门不误伤事务类体裁", not g5.get("drift"), "applicable=%s" % g5.get("applicable"))

    allpass = all(v["pass"] for v in res.values())
    if verbose:
        print("  === 守恒门自检: %s (%d/%d) ===" % ("全部通过" if allpass else "有未通过",
                                                sum(v["pass"] for v in res.values()), len(res)))
    return {"all_pass": allpass, "cases": res}


if __name__ == "__main__":
    out = selftest()
    sys.exit(0 if out["all_pass"] else 1)
