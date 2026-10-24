#!/usr/bin/env python3
"""★ **报告基线化 + 块标记迁移**（★ 一次性，★ 2026-10-25）

★ **★ 为什么需要它（★ 真问题，★ 不是整理癖）★★**：
★ `fill_report_stage1.py` 的基底选择要求【含 `<!-- 待填：xxx -->` 的原始未填版】★
★ ⇒ ⇒ ★ **该基底被首次填充后就被覆盖了** ⇒ ⇒ ★ **脚本第二次就 `SystemExit`（EXIT=1）★★**
★ ⇒ ⇒ ★ ⇒ **「报告数字由脚本填」这条纪律【无法持续执行】** ★ ★
★ ⇒ ⇒ ★ **⇒ 修法：★ ① 固化一份【基线】（含块标记）★ ② 脚本从基线重填 ★ ③ 块级幂等替换 ★★**

★ **★ 为什么用【行内块标记】而不是【标题切段】★★**：
★ 标题切段会把 §0 的整张更正表也卷进来（★ 纯文字、★ 不含数据、★ 不必每次重生成）
★ ⇒ ⇒ ★ 行内块**只圈住真正需要脚本生成的部分** ⇒ ⇒ ★ 其余文字留在基线里原样保留

★ **★ 本脚本的三个动作 ★**：
★ ① **★ 固化基线**：★ 当前已填版 → `REPORT_arch6_stage1.base.md`（★ 入 git）★★
★ ② **★ 加块标记**：★ ① §3.5 的 Gate 区分力表 ② §0 的【降级条目】★★
★ ③ **★ 幂等**：★ 重复跑不产生差异

★ **★ 用法 ★★：
```bash
python3 -B group4_state_driven/migrate_report_base.py
```
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
CUR = os.path.join(REPO, "group4_state_driven", "REPORT_arch6_stage1.md")
BASE = os.path.join(REPO, "group4_state_driven", "REPORT_arch6_stage1.base.md")

# ★ ★ 块标记清单（★ 与 fill_report_stage1.py 里的 FILL_BLOCKS 对应）★★
BLOCKS = [
    # (tag, 该块在报告里的【定位锚点】——★ 必须是块首行里唯一的字符串)
    ("3.5-gates", "**★ 各 Gate 批内区分力（★ 连续量口径）**"),
]

# ★ ★ ★ 【§0 降级记录】：★ 这段【本轮新增】⇒ ★ 迁移脚本负责【插入】★ ★ ★
DEGRADE_BLOCK = """
**⑤ ★ 降级记录（★ 2026-10-25 · ★ 主会话裁决一/二 + 本轮回源核查）★★★**

> ★ **★ 为什么单列「降级」而不并入「修正」★★**：★ 外部读者看到「修正」会以为只是改了个数字；
> ★ 看到「降级」才会知道**有一条推理链被撤了**。★ ⇒ **作废的是哪一句、哪些结论受影响、哪些明确不受影响、依据在哪**，★ 逐条写死。

**★ 降级 1：`len_corr = 1.000` 作「对照端退化为『选最长的』」的证据 ⇒ ⇒ 【作废】**

| 项 | 内容 |
|---|---|
| ★ **哪一句作废**（逐字） | ★ §3.5 表中 `length` 行的读法：「⚠️ **与长度完全相关 ⇒ 对照端退化为「选最长的」**」 |
| ★ **为什么作废** | ★ `length` Gate 的 score = `len_i / max_len`（★ **批内相对长度**）⇒ ⇒ 分母是**批内常数** ⇒ ⇒ 它是绝对长度的**严格单调变换** ⇒ ⇒ **Pearson(score, 绝对长度) 在定义上恒为 1** ⇒ ⇒ 该读数**零信息量**，★ 不能支撑任何结论 |
| ★ **依据（回源）** | ★ ① 实现：`group4_state_driven/code/workflow_arch6.py:167-180`（`_length`）★ ② 读数：`group4_state_driven/data/arch6_gate_semantics.json` ① 证据 A（★ **构造性**：造 10 个长度各异的候选 ⇒ Pearson = **1.0**，★ 与本批数据无关）③ 证据 B（★ **观测**：本批 n=9，**9/9 = 1.0**）④ 反例（★ 旧封顶口径 `min(1.0, len/900)` ⇒ Pearson = **0.9789** ⇒ ★ **正因如此旧口径才有信息量，★ 改成批内相对后它【必然恒为 1】**） |
| ★ **哪些结论受影响** | ★ ① 「对照端退化为『选最长的』」⇒ ⇒ **该结论在本批【不成立】**：★ 家族最优 **9/9 由 `escape` 赢**，★ `length` **赢 0 次**（读数见 §3.5）★ ② 任何以 `len_corr` 为依据的退化推断 |
| ★ **哪些明确不受影响** | ★ ① **排序改变率 3/8**（★ `analyze_arch6.py:146` 明确【从 scores 重算】、★ **不读落盘 rank/len_corr**）★ ② 「创造区分」2 例（★ G01-3 / T10-2）★ ③ 目标集变化率 1.0000 ★ ④ σ / 平移 / 同质率（★ 均不含 `len_corr`）★ ⑤ 主判决【不可分辨】 |
| ★ **结论是否改变** | ★ **不改变，且【变强】**：★ 主判决不依赖 `len_corr`；★ 而对照端**不是长度代理** ⇒ ⇒ 状态化选择器 vs 家族最优的对比**更干净**（★ 少了一个共同混淆因子） |

**★ 降级 2：`escape` 的 `len_corr` 读数 ⇒ ⇒ 【降为「不报告」】**

| 项 | 内容 |
|---|---|
| ★ **哪一句作废** | ★ §3.5 表中 `escape` 行的「与长度相关 r = {esc_r}」★ ⇒ **本报告不再引用该值** |
| ★ **为什么** | ★ 本轮回源核查发现：★ **`escape` 的 `len_corr` 与它自己的排序读数在 4/9 个样本上【不自洽】**（★ 详证见 `KNOWN_ISSUES.md`「待 Mavis 裁决」段）⇒ ⇒ ★ 两者至少有一个不可信 ⇒ ⇒ ★ **未定位根因前，★ 该读数一律不报告**（★ **不猜、不用**） |
| ★ **依据** | ★ ① 穷举检验（★ 6 个约束：min/max/var/len_corr/escape.rank/length.rank）⇒ **无解** ★ ② 实现层同构实验（★ 真实 `family_pick6` + 构造分数）⇒ **自洽** ⇒ ⇒ ★ **不是 `family_pick6` 的逻辑 bug** ★ ③ 逐样本表见 `KNOWN_ISSUES.md` |
| ★ **哪些结论受影响** | ★ **仅** §3.5 表中 `escape` 行的 r 值 ★ ⇒ **无任何结论依赖它**（★ 排序改变率、align 读数、兑现/违禁率均不含它） |
| ★ **哪些明确不受影响** | ★ ★ 全部主读数（★ 见降级 1 的"不受影响"清单，★ 且本项影响面更小） |
| ★ **结论是否改变** | ★ **不改变**（★ 该值此前**未被任何结论使用**） |

"""



def locate(s: str, anchor: str) -> tuple:
    """★ 返回 (块首行起点, 块尾行终点) 的行号区间（★ 含端点）★"""
    lines = s.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if anchor in ln:
            start = i
            break
    if start is None:
        raise SystemExit("✘ 找不到锚点：%r ⇒ 停止（★ 不许静默跳过）" % anchor)
    # ★ 块尾 = 下一个空行后紧跟的【非表格、非列表】段落之前 ⇒ ★ 用"下一个以 ★ ** 或 **★ 开头的独立段"判定
    end = None
    for j in range(start + 1, len(lines)):
        ln = lines[j]
        if ln.startswith("**") and not ln.startswith("**★") is False:
            pass
        # ★ 块尾判定：★ 下一个空行 + 非表格行 的顶层段首
        if ln.strip() == "" and j + 1 < len(lines):
            nxt = lines[j + 1]
            if nxt.startswith("**") and "|" not in nxt and not nxt.startswith("**★"):
                # ★ ★ 但要排除块内的小节（★ 例如「★ 状态化 align 的区分力」也是 ** 开头）★★
                if "区分力" not in nxt and "Gate" not in nxt:
                    end = j
                    break
    if end is None:
        end = min(start + 12, len(lines))
    return start, end


def main() -> int:
    if not os.path.exists(CUR):
        print("✘ 找不到当前报告：%s" % CUR)
        return 2
    s = open(CUR, encoding="utf-8").read()

    # ── ① 固化基线（★ 幂等：★ 已存在且内容一致就不动）──
    if os.path.exists(BASE):
        old = open(BASE, encoding="utf-8").read()
        if old == s:
            print("✔ 基线已是最新（★ 幂等跳过）")
        else:
            print("★ 基线存在但与当前报告不同 ⇒ ★ 【不覆盖】（★ 需人工确认）")
            print("  ★ 请人工 diff 后决定；★ 本脚本不自动覆盖基线")
            return 1
    else:
        with open(BASE, "w", encoding="utf-8") as f:
            f.write(s)
        print("✔ 已固化基线：%s" % BASE)

    # ── ①b 插入 §0 降级记录（★ 带 FILL 标记，★ 数字由脚本填）──
    out = s
    DEG_HEAD = "**⑤ ★ 降级记录"
    if DEG_HEAD in out:
        print("  · §0 降级记录已存在（★ 幂等跳过）")
    else:
        # ★ 插到 §0 的末尾（★ §0 后面是第一个 ## 标题）
        lines = out.split("\n")
        ins = None
        for i, ln in enumerate(lines):
            if ln.startswith("## ") and not ln.startswith("### "):
                ins = i
                break
        if ins is None:
            print("✘ 找不到 §0 的结束位置（★ 第一个 ## 标题）⇒ 停止")
            return 2
        blk = DEGRADE_BLOCK.strip("\n").split("\n")
        blk = ["<!-- FILL:0-degrade -->"] + blk + ["<!-- /FILL:0-degrade -->"]
        lines = lines[:ins] + [""] + blk + [""] + lines[ins:]
        out = "\n".join(lines)
        print("  ✔ §0 降级记录已插入（★ 行 %d）" % (ins + 2))

    # ── ② 加块标记 ──
    for tag, anchor in BLOCKS:
        beg = "<!-- FILL:%s -->" % tag
        end = "<!-- /FILL:%s -->" % tag
        if beg in out:
            print("  · 块 %s 已存在（★ 幂等跳过）" % tag)
            continue
        if anchor not in out:
            print("✘ 找不到锚点：%r ⇒ 停止" % anchor)
            return 2
        # ★ 在锚点【所在行之前】插块首，★ 在该段【结束后】插块尾
        lines = out.split("\n")
        st = None
        for i, ln in enumerate(lines):
            if anchor in ln:
                st = i
                break
        # ★ 找块尾：★ 从 st 起，★ 找下一个空行后接【非表格、非本块小节】的行
        en = None
        for j in range(st + 1, len(lines)):
            if lines[j].strip() == "" and j + 1 < len(lines):
                nxt = lines[j + 1]
                if nxt.startswith("|") or nxt.startswith(">") or nxt.strip() == "":
                    continue
                if nxt.startswith("**") and ("区分力" in nxt or "Gate" in nxt or "状态化" in nxt
                                            or "标准化效应量" in nxt or "算得出来" in nxt):
                    continue      # ★ 本块内部的小节 ⇒ 不算块尾
                en = j
                break
        if en is None:
            en = min(st + 14, len(lines))
        new_lines = (lines[:st] + [beg] + lines[st:en] + [end] + lines[en:])
        out = "\n".join(new_lines)
        print("  ✔ 块 %s 已加标记（★ 行 %d–%d）" % (tag, st + 1, en + 1))

    if out != s:
        for path in (BASE, CUR):
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(out)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        print("✔ 已写入（基线 + 当前报告）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
