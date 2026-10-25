#!/usr/bin/env python3
"""★ **题级预注册结论空间**（`conclusion_space`）—— 事前写死，零读数依赖

> 落点：`creativity_lab/data/conclusion_spaces.json`（**由本脚本生成，内容是人工写死的**）
> 规范文档：`docs/cmp8/routes/COLLAPSE/eval/PREREG-CONCLUSION-SPACE.md`
> 生成器：`creativity_lab/experiments/build_conclusion_spaces.py`
>
> ## ★★★ 为什么要它
> 三组（`routes/C/optimizer.py:75`）的 `family_key(card)` = `"|".join(sorted(card["supports_conclusions"]))`
> ⇒ **它只是 3 行字符串操作**；★ **归并的语义在判官那一半** ⇒ **复现这套口径 = 复现判官那一半**
> ⇒ ⇒ ★ **硬前提**：每题必须有**题级预注册的结论空间**（`C1..Cn`）⇒ **不是自动的**
> ⇒ ⇒ ★ **「两派相反答案」能否被识别，取决于结论空间里是否同时列了这两派** ⇒ **报读数时必须写明**
>
> ## ★★★ 与旧版的区别（★ 负责人前置门 ③）
> | | 旧版（已废） | ★ **本版** |
> |---|---|---|
> | 理科题结论空间 | ★ **事后从各支产出导出** | ★ **事前人工写死** |
> | 结论形式 | 具体数值 | ★ **互斥的命题形式** |
> | 依赖读数 | ❌ 是 | ✅ **完全零读数依赖** |
>
> ## ★★ 为什么用「互斥命题」而不是「具体数值」
> ① **数值容易算错**（我自己都可能算错 ⇒ 会把错答案写进预注册 ⇒ 污染）
> ② ★★ **判官判的本来就是「这条陈述支持哪条结论」** ⇒ 命题形式才是判官能对齐的东西
> ③ ★★★ **互斥命题天然分成两族** ⇒ ⇒ **正面命中 Vendi 的盲点**（Vendi 把「2 同向 + 2 反向」判成 1.00）
> ④ ⇒ **与题目的"答案唯一"性质一致**：S1/S2/S3 是「推导唯一」，它们的唯一性在**命题**上，不在数值书写上
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "creativity_lab", "data", "conclusion_spaces.json")

# ══════════════════════════════════════════════════════════════
# ★★★ 人工写死的互斥命题集合（★ 事前 / 零读数依赖 / 不随读数变化）
# ══════════════════════════════════════════════════════════════
SPACES = {
    # ── S1 理科·唯一解：木板 + 弹簧（2020 高考物理原创压轴）──
    "S1": {
        "source": "topics_2x2.json · S1",
        "note": "★ 结论写成【互斥命题】而非数值：① 避免把算错的数值写进预注册 ② 判官判的是「支持哪条命题」③ 互斥命题天然分两族",
        "conclusions": [
            {"id": "C1", "text": "施力瞬间**物块的加速度小于木板**（物块被摩擦力拖慢，未达整体加速度）"},
            {"id": "C2", "text": "施力瞬间**物块与木板加速度相等**（当作整体处理，忽略相对滑动）"},
            {"id": "C3", "text": "施力瞬间**物块的加速度大于木板**（物块被弹簧拉住或摩擦方向判断相反）"},
            {"id": "C4", "text": "物块在木板上**相对木板滑动**（因此滑动摩擦恒定，物块加速度恒定）"},
            {"id": "C5", "text": "物块的**最大速度出现在其与木板相对静止的瞬间**（而不是随时间无界增长）"},
        ],
        "key_conclusions": ["C1", "C4", "C5"],
        "mutual_exclusion_groups": [["C1", "C2", "C3"], ["C4"], ["C5"]],
    },
    # ── S2 理科·唯一解：弹簧弹力冲量（2018 江苏卷）──
    "S2": {
        "source": "topics_2x2.json · S2",
        "note": "★ 同上：互斥命题",
        "conclusions": [
            {"id": "C1", "text": "弹簧弹力冲量大小为 **2mv + mgt**（由「动量定理 + 冲量定义」直接得到）"},
            {"id": "C2", "text": "弹簧弹力冲量大小为 **2mv − mgt**（把重力冲量的符号取反）"},
            {"id": "C3", "text": "弹力冲量与**重力冲量合并**处理（写成总冲量再分解）"},
            {"id": "C4", "text": "弹力冲量为 **0**（认为全过程弹力与重力抵消 ⇒ 速度不变）"},
        ],
        "key_conclusions": ["C1"],
        "mutual_exclusion_groups": [["C1", "C2", "C4"], ["C3"]],
    },
    # ── S3 理科·唯一解·陷阱：弹簧释放与平板车（2020 高考物理原创压轴）──
    "S3": {
        "source": "topics_2x2.json · S3",
        "note": "★ 同上：互斥命题",
        "conclusions": [
            {"id": "C1", "text": "弹簧释放瞬间 A、B **分开**（弹簧只对 A 做正功 ⇒ 分离）"},
            {"id": "C2", "text": "弹簧释放瞬间 A、B **不分开**（认为弹簧对 A、B 对称作用）"},
            {"id": "C3", "text": "B 落地前的运动可分解为**水平匀速 + 竖直自由落体**（水平不受力）"},
            {"id": "C4", "text": "B 落地时间由**车面高度与自由落体**决定（与水平速度无关）"},
            {"id": "C5", "text": "系统产生的热量由**摩擦生热 = f · 相对位移**给出**（相对位移，不是某支的位移）"},
        ],
        "key_conclusions": ["C1", "C3", "C4", "C5"],
        "mutual_exclusion_groups": [["C1", "C2"], ["C3"], ["C4"], ["C5"]],
    },
    # ── S4 文科·唯一解：三段材料 ⇒ 唯一必然结论 ──
    "S4": {
        "source": "topics_2x2.json · S4（★ 本组自编题）",
        "note": "★ 唯一自编题；结论空间 = 互斥的「材料能否支持 + 缺什么」",
        "conclusions": [
            {"id": "C1", "text": "结论 X **不能被材料支持**（相关不能推出因果）"},
            {"id": "C2", "text": "结论 X **能被材料支持**（同期共变足以支持因果）"},
            {"id": "C3", "text": "缺的是**时间先后**（不能排除巧合与共同原因）"},
            {"id": "C4", "text": "缺的是**混杂变量**（如该市同期其它政策/区位变化）"},
            {"id": "C5", "text": "缺的是**反事实**（若无园区新增，公共交通分担率是否仍会上升）"},
        ],
        "key_conclusions": ["C1"],
        "mutual_exclusion_groups": [["C1", "C2"], ["C3"], ["C4"], ["C5"]],
    },
    # ── S5 理科·答案唯一但路径多样：证明不等式（真实数学题）──
    "S5": {
        "source": "topics_2x2.json · S5（真实题，非自编）",
        "note": "★ 路径多样题：结论少但【路径】多 ⇒ ★ 这题正是 family_key 该显出本事的地方",
        "conclusions": [
            {"id": "C1", "text": "不等式**成立**（由 (x−y)² ≥ 0 得）"},
            {"id": "C2", "text": "等号成立**当且仅当 x = y**"},
            {"id": "C3", "text": "等号成立条件被答成**其它等价形式**（如 x²=y² / x 与 y 同号且 |x|=|y|）"},
        ],
        "key_conclusions": ["C1", "C2"],
        "mutual_exclusion_groups": [["C1"], ["C2", "C3"]],
    },
    # ── S6 文科·答案唯一但路径多样：三份方案中哪份可行（自编）──
    "S6": {
        "source": "topics_2x2.json · S6（★ 本组自编题）",
        "note": "★ 路径多样题：唯一可行路线 = 丙（造价 19≤30 / 工期 1≤2.5 / 拆迁 50≤5000）",
        "conclusions": [
            {"id": "C1", "text": "**路线丙是唯一可行**（三项硬约束全部满足）"},
            {"id": "C2", "text": "路线甲**不可行**（造价 42 亿 > 30 亿 且 工期 3 年 > 2.5 年）"},
            {"id": "C3", "text": "路线乙**不可行**（工期 2 年 ≤ 2.5 年、造价 27 ≤ 30、拆迁 200 ≤ 5000 ⇒ ★ 须指出**还需补什么**才能排除）"},
            {"id": "C4", "text": "答成**「多条可行」或「无法判定」**"},
        ],
        "key_conclusions": ["C1"],
        "mutual_exclusion_groups": [["C1", "C4"], ["C2"], ["C3"]],
    },
    # ── T1/T2/T3 开放题：★ 这个口径最弱（结论空间本身事后化）──
    "T1": {
        "source": "topics.json · T1",
        "note": "★ 开放题：只能写「主要论断维度」⇒ ★ 本口径在开放题上最弱，报读数必须标",
        "open_ended": True,
        "conclusions": [
            {"id": "C1", "text": "主要论断落在**能力边界**（AI 能做什么/不能做什么）"},
            {"id": "C2", "text": "主要论断落在**教育与职业结构改变**"},
            {"id": "C3", "text": "主要论断落在**风险与治理**（伦理、监管、失业）"},
            {"id": "C4", "text": "主要论断落在**人机关系 / 协作方式**"},
        ],
        "key_conclusions": [],
        "mutual_exclusion_groups": [["C1", "C2", "C3", "C4"]],
    },
    "T2": {
        "source": "topics.json · T2",
        "note": "★ 开放题：主要建议维度",
        "open_ended": True,
        "conclusions": [
            {"id": "C1", "text": "院校层级建议（985 / 强 985 / 省属强校）"},
            {"id": "C2", "text": "专业建议（AI 相关的具体方向）"},
            {"id": "C3", "text": "城市 / 就业导向（留在湖北 vs 出省）"},
            {"id": "C4", "text": "分数-位次口径的使用（620 分对应位次）"},
        ],
        "key_conclusions": [],
        "mutual_exclusion_groups": [["C1", "C2", "C3", "C4"]],
    },
    "T3": {
        "source": "topics.json · T3",
        "note": "★ 开放题：战术核心维度",
        "open_ended": True,
        "conclusions": [
            {"id": "C1", "text": "战术核心在**前段跟车 / 抢位**"},
            {"id": "C2", "text": "战术核心在**保留体力 / 后段冲刺**"},
            {"id": "C3", "text": "战术核心在**利用回头弯 / 弯道超越**"},
            {"id": "C4", "text": "战术核心在**落单 / 单飞 / 挂车**"},
        ],
        "key_conclusions": [],
        "mutual_exclusion_groups": [["C1", "C2", "C3", "C4"]],
    },
}


def main() -> int:
    payload = {
        "_meta": {
            "what": "★ 题级【预注册】结论空间（人工写死的互斥命题集合）",
            "why": "family_key 语义级尺子的硬前提：判官要给每条陈述打 supports_conclusions = 结论编号 ⇒ 必须先有编号清单",
            "source_of_truth": "★ 本文件（人工写死，事前，零读数依赖）——★ **不是**从任何跑批产出导出",
            "form": "★ 互斥【命题】而非数值：① 避免把算错的数值写进预注册 ② 判官判的就是命题 ③ 互斥命题天然分两族 ⇒ 正面命中 Vendi 盲点",
            "two_family_count_calibers": "★ 承重口径（主读数：空族不算路径） vs 全卡口径（含空族 `''`）⇒ **必须分开报**",
            "open_ended_topics": "★ T1/T2/T3 为开放题 ⇒ 本口径最弱 ⇒ 读数必须标「开放题」",
            "label": "★ 组内人工标注 ⇒ **待独立核验**",
            "reuse": "★ 这套规范可在【层3 法律域 18 题 × 944 断言】上复用 ⇒ 见 PREREG-CONCLUSION-SPACE.md",
        },
        "spaces": SPACES,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("✔ 落盘：%s（%d 题）" % (OUT, len(SPACES)))
    for tid, sp in sorted(SPACES.items()):
        n_ex = sum(len(g) for g in sp["mutual_exclusion_groups"])
        print("  %-3s %d 条结论 / %d 个互斥组 %s%s"
              % (tid, len(sp["conclusions"]), n_ex,
                 "  ★开放题" if sp.get("open_ended") else "",
                 "  ★互斥组覆盖全部" if n_ex == len(sp["conclusions"]) else ""))
    print()
    print("★ 提醒：① 全部「组内标注，待独立核验」② 承重/全卡双口径 ③ 跑批需判官额度")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
