#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「标准程序流程图」HTML —— 用脚本算多边形坐标，避免手写 SVG 出错。"""
import io
import os

OUT_DIR = "/workspace/lab/visual-page/arch-flowcharts"
os.makedirs(OUT_DIR, exist_ok=True)


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def txt(x, y, s, cls="lbl", anchor="middle", dy=0):
    return '<text x="%.1f" y="%.1f" text-anchor="%s" class="%s" %s>%s</text>' % (
        x, y + dy, anchor, cls, 'dominant-baseline="middle"' if False else '', esc(s))


def box(x, y, w, h, label, sub=None, kind="st", fs=13):
    """矩形/终止符/输入输出。返回 (svg, 中心x, 底部y)。"""
    s = ['<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%s" class="%s"/>' % (
        x, y, w, h, "18" if kind == "term" else ("2" if kind == "st" else "2"), kind)]
    if sub:
        s.append(txt(x + w / 2, y + h / 2 - 9, label, "lbl"))
        s.append(txt(x + w / 2, y + h / 2 + 10, sub, "mono"))
    else:
        s.append(txt(x + w / 2, y + h / 2 + 5, label, "lbl"))
    return "".join(s)


def diamond(cx, cy, w, h, label, sub=None, kind="dec"):
    p = "%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" % (
        cx, cy - h / 2, cx + w / 2, cy, cx, cy + h / 2, cx - w / 2, cy)
    s = ['<polygon points="%s" class="%s"/>' % (p, kind)]
    if sub:
        s.append(txt(cx, cy - 9, label, "lbl"))
        s.append(txt(cx, cy + 10, sub, "mono"))
    else:
        s.append(txt(cx, cy + 5, label, "lbl"))
    return "".join(s)


def para(cx, cy, w, h, label, sub=None):
    """平行四边形（输入/输出）。"""
    sk = 12
    p = "%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" % (
        cx - w / 2 + sk, cy - h / 2, cx + w / 2, cy - h / 2,
        cx + w / 2 - sk, cy + h / 2, cx - w / 2, cy + h / 2)
    s = ['<polygon points="%s" class="io"/>' % p]
    if sub:
        s.append(txt(cx, cy - 9, label, "lbl"))
        s.append(txt(cx, cy + 10, sub, "mono"))
    else:
        s.append(txt(cx, cy + 5, label, "lbl"))
    return "".join(s)


def arrow(d, cls="ln"):
    return '<path d="%s" class="%s" marker-end="url(#ah)"/>' % (d, cls)


def label(x, y, s, cls="mono", anchor="middle"):
    return '<text x="%.1f" y="%.1f" text-anchor="%s" class="%s">%s</text>' % (x, y, anchor, cls, esc(s))


# ══════════════════════════ 图 1 · A1 直调 ══════════════════════════
def fig_a1():
    s = []
    cx = 300
    y = 14
    s.append(box(cx - 70, y, 140, 34, "开始", kind="term")); y += 34
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(para(cx, y + 23, 220, 46, "输入：问题 ask", "用户原题")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - 110, y, 220, 46, "LLM 生成", "1 次调用 · 不喂依据包")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(para(cx, y + 23, 220, 46, "输出：答案", "≤400 字")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 70, y, 140, 34, "结束", kind="term")); y += 34
    return '<svg viewBox="0 0 600 %d" class="figsvg">%s</svg>' % (y + 16, "".join(s))


# ══════════════════════════ 图 2 · 双轴（A3/A4） ══════════════════════════
def fig_dual():
    s = []
    cx = 330
    s.append(box(cx - 70, 14, 140, 34, "开始", kind="term"))
    s.append(arrow("M%.1f,48 L%.1f,72" % (cx, cx)))
    s.append(para(cx, 72, 230, 46, "输入：问题 ask", "用户原题"))

    # 扇出
    s.append(arrow("M%.1f,118 L%.1f,146" % (cx, cx)))
    s.append(box(cx - 130, 146, 260, 46, "扇出：i = 1 … 5", "框架[i] / 模型[i] / persona[i] 错位绑定"))
    s.append(arrow("M%.1f,192 L%.1f,212" % (cx, cx)))

    # 5 分支
    bx, bw, bh, gap = 210, 300, 40, 10
    bus = bx - 34                     # 竖干（分发总线）
    for i in range(5):
        y = 212 + i * (bh + gap)
        hot = (i == 2)
        s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" class="%s"/>' % (
            bx, y, bw, bh, "stHot" if hot else "st"))
        s.append(txt(bx + 14, y + bh / 2 + 4, "分支 %d" % (i + 1), "lbl", "start"))
        s.append(txt(bx + 78, y + bh / 2 + 4, "独立调用 · 零共享上下文", "mono", "start"))
        # 水平入箭头：从竖干指向分支框左边
        s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (bus, y + bh / 2, bx - 2, y + bh / 2),
                        "ln" if hot else "lnSoft"))
    # 竖干：从扇出框底部 → 竖干顶端；竖干贯穿 5 个分支
    ytop = 212 + bh / 2
    ybot = 212 + 4 * (bh + gap) + bh / 2
    s.append('<path d="M%.1f,192 L%.1f,192 L%.1f,%.1f" class="lnSoft" fill="none"/>' % (cx, bus, bus, ytop))
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (bus, ytop, bus, ybot))
    yend = 212 + 5 * (bh + gap) + 6
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, yend, cx, yend + 26)))

    # mode 判定
    s.append(diamond(cx, yend + 62, 230, 72, "mode == fuse ?", "构造时确定，不是运行时判断"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx - 115, yend + 62, 150, yend + 62)))
    s.append(label(120, yend + 52, "是"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 115, yend + 62, 520, yend + 62)))
    s.append(label(556, yend + 52, "否"))

    # 左路 fuse
    s.append(box(60, yend + 96, 190, 44, "premise", "逐条说明依赖哪些前提"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (150, yend + 62, 150, yend + 96)))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (155, yend + 140, 155, yend + 166)))
    s.append(box(60, yend + 166, 190, 44, "fuse 融合门", "把 5 段综合成一篇"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (155, yend + 210, 155, yend + 250)))

    # 右路 select
    s.append(box(430, yend + 96, 190, 44, "select 去融合门", "各分支已各自成篇，末步只挑一篇"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (520, yend + 62, 520, yend + 96)))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (525, yend + 140, 525, yend + 250)))

    # 汇合
    s.append('<path d="M155,%.1f L155,%.1f L525,%.1f L525,%.1f" class="lnSoft" fill="none"/>' % (
        yend + 250, yend + 278, yend + 278, yend + 250))
    s.append('<path d="M525,%.1f L525,%.1f" class="lnSoft" fill="none"/>' % (yend + 140, yend + 250))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (330, yend + 278, 330, yend + 300)))
    s.append(para(cx, yend + 300, 230, 46, "输出：答案", "A3=7 次调用 ｜ A4=6 次"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, yend + 346, cx, yend + 372)))
    s.append(box(cx - 70, yend + 372, 140, 34, "结束", kind="term"))
    h = yend + 420
    return '<svg viewBox="0 0 700 %d" class="figsvg">%s</svg>' % (h, "".join(s))


# ══════════════════════════ 图 3 · A5 新架构 ══════════════════════════
def fig_a5():
    s = []
    cx = 200          # 主干中心
    W = 250           # 主干框宽
    R = 470           # 右侧处理区中心
    y = 14
    s.append(box(cx - 70, y, 140, 34, "开始", kind="term")); y += 34
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(para(cx, y + 23, 240, 46, "输入：ask + 依据包 ev", "工作流只看到 ask")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - W / 2, y, W, 40, "建立空图 G")); y += 40
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - W / 2, y, W, 46, "枚举合法候选操作", "共 7 个候选操作"))
    y_enum = y + 23
    y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - W / 2, y, W, 46, "算 14 维局部特征 f", "只看当前节点 + 本分支历史，与题无关")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - W / 2, y, W, 40, "score = w · f", "w = 训练学出的 14 维权重")); y += 40

    # ε 探索
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(diamond(cx, y + 36, 190, 72, "ε 随机探索 ?", "ε = 0.25"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 95, y + 36, R - 110, y + 36)))
    s.append(label(cx + 130, y + 26, "是"))
    s.append(box(R - 110, y + 14, 220, 44, "score += U(0, 2)", "加随机分"))
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (R, y + 36, R + 40, y + 36))
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (R + 40, y + 36, R + 40, y + 96))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (R + 40, y + 96, cx + 80, y + 96)))
    s.append(label(cx + 106, y + 113, "否（原分）"))
    y += 72

    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - W / 2, y, W, 40, "取 score 最大的候选 (op*, target*)")); y += 40

    # STOP?
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(diamond(cx, y + 34, 190, 68, "op* == STOP ?")); y += 68
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 24)))
    s.append(label(cx + 42, y + 14, "是"))
    y += 24

    # op 分派
    ops = [
        ("op* == VERIFY ?", "拿依据包核验该断言 → verdict", "VERIFY"),
        ("op* == GEN_PLAIN / GEN_ANGLE ?", "LLM 生成 → 加一个 ANSWER 节点", "GEN"),
        ("op* == EXTRACT ?", "从 ANSWER 抽断言 → 加 CLAIM 节点", "EXTRACT"),
        ("op* == SPLIT ?", "拆成两条 → 加 CLAIM′ 节点", "SPLIT"),
    ]
    for i, (dl, hl, tag) in enumerate(ops):
        s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18)))
        s.append(label(cx + 40, y + 12, "否"))
        y += 18
        s.append(diamond(cx, y + 32, 200, 64, dl))
        s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 100, y + 32, R - 115, y + 32)))
        s.append(label(cx + 128, y + 24, "是"))
        s.append(box(R - 115, y + 10, 230, 46, hl))
        s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (R, y + 32, R + 60, y + 32))
        s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (R + 60, y + 32, R + 60, y + 96))
        s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (R + 60, y + 96, cx + 78, y + 96)))
        s.append(label(cx + 118, y + 88, "回到图上一步"))
        y += 64

    # MERGE
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    s.append(diamond(cx, y + 30, 190, 60, "op* == MERGE ?"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 95, y + 30, R - 115, y + 30)))
    s.append(label(cx + 122, y + 22, "是"))
    s.append(box(R - 115, y + 8, 230, 44, "合并 ANSWER 节点"))
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (R, y + 30, R + 60, y + 30))
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (R + 60, y + 30, R + 60, y + 90))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (R + 60, y + 90, cx + 78, y + 90)))
    y += 60

    # 步数
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    s.append(diamond(cx, y + 32, 190, 64, "步数 < budget(10) ?"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y + 64, cx, y + 88)))
    s.append(label(cx + 46, y + 78, "是"))
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (cx - 95, y + 32, 40, y + 32))
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (40, y + 32, 40, y_enum))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (40, y_enum, cx - 132, y_enum)))
    s.append(label(52, y_enum - 9, "继续下一步"))
    y += 88
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 130, y, 260, 46, "机械装配 assemble", "不由模型重写")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(para(cx, y + 23, 240, 46, "输出：交付答案", "支持→主体 / 未核验→单列")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 70, y, 140, 34, "结束", kind="term")); y += 34
    return '<svg viewBox="0 0 800 %d" class="figsvg">%s</svg>' % (y + 20, "".join(s))


# ══════════════════════════ 图 4 · 训练（REINFORCE） ══════════════════════════
def fig_train():
    s = []
    cx = 300
    y = 14
    s.append(box(cx - 70, y, 140, 34, "开始", kind="term")); y += 34
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(para(cx, y + 23, 260, 46, "输入：训练题集", "政策域 8 题 · 不碰用户四道题")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - 130, y, 260, 46, "初始化 w = 0（14 维）", "策略 = 局部线性")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - 130, y, 260, 46, "跑一个 episode", "按当前 w 走一遍图搜索（ε=0.25）"))
    y_rollout = y + 23
    y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - 130, y, 260, 46, "算 reward", "max 宽度 s.t. 矛盾率 ≤ 最优基线")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(diamond(cx, y + 32, 210, 64, "约束满足 ?", "矛盾率没超基线"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 105, y + 32, 560, y + 32)))
    s.append(label(cx + 150, y + 24, "否"))
    s.append(box(470, y + 10, 200, 44, "惩罚 reward", "约束违规 → 扣分"))
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (
        570, y + 32, 660, y + 32, 660, y_rollout, cx + 132, y_rollout))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 132, y_rollout, cx + 132, y_rollout)))
    s.append(label(628, y_rollout - 12, "回到 rollout（重跑）"))
    y += 64
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 130, y, 260, 46, "policy gradient 更新 w", "∇J ≈ Σ (R − b) ∇log π(a|s)")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(diamond(cx, y + 32, 200, 64, "轮数够了 ?"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y + 64, cx, y + 90)))
    s.append(label(cx + 40, y + 78, "否"))
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (cx - 100, y + 32, 60, y + 32))
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (60, y + 32, 60, 258))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (60, 258, cx - 130, 258)))
    s.append(label(92, 250, "下一个 episode"))
    y += 90
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 130, y, 260, 44, "输出 w", "runs/arch_learn/result.json")); y += 44
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 70, y, 140, 34, "结束", kind="term")); y += 34
    return '<svg viewBox="0 0 720 %d" class="figsvg">%s</svg>' % (y + 20, "".join(s))


# ══════════════════════════ 图 5 · 评估（判官闸门） ══════════════════════════
def fig_eval():
    s = []
    cx = 290
    y = 14
    s.append(box(cx - 70, y, 140, 34, "开始", kind="term")); y += 34
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(para(cx, y + 23, 240, 46, "输入：84 份答案", "runs/cmp8/*.md")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - 130, y, 260, 46, "判官自检", "已知真断言 / 已知假断言")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(diamond(cx, y + 34, 230, 68, "真 ≥3/4 且 假 ≥3/4 ?", "不过就拒绝出数"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 115, y + 34, 540, y + 34)))
    s.append(label(cx + 132, y + 26, "否"))
    s.append(box(450, y + 12, 190, 44, "拒绝出数", "整套数据作废"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (545, y + 56, 545, y + 100)))
    s.append(box(450, y + 100, 190, 34, "结束", kind="term"))
    y += 68
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(label(cx + 52, y + 14, "是"))
    s.append(box(cx - 130, y, 260, 46, "逐条核验", "支持 / 矛盾 / 未提及 / 非主张")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - 130, y, 260, 46, "去重（embedding，阈值 0.75）", "算去重宽 width")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(box(cx - 130, y, 260, 46, "统计", "矛盾率 / 支持率 / 离散度 / 噪声地板")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 22))); y += 22
    s.append(para(cx, y + 23, 240, 46, "输出：analysis.json + 判读页", "原样回报，不改写")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 70, y, 140, 34, "结束", kind="term")); y += 34
    return '<svg viewBox="0 0 700 %d" class="figsvg">%s</svg>' % (y + 20, "".join(s))


# ══════════════════════════ 装配规则（附图） ══════════════════════════
def fig_assemble():
    s = []
    # 顶部：图上所有 CLAIM 节点
    s.append(box(250, 14, 260, 44, "图上所有 CLAIM 节点", "每个都带一个 verdict"))
    rows = [("verdict = 支持", "主体「经核验成立的依据」", "Hot"),
            ("verdict = 未提及 / 非主张", "另列「依据未覆盖、仅供参考」", ""),
            ("verdict = None（未核验）", "单列「未经核验的断言」", ""),
            ("verdict = 矛盾", "丢弃", "Bad")]
    y = 86
    bus = 96
    for lab, res, k in rows:
        s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" class="st%s"/>' % (
            20, y, 200, 36, k))
        s.append(txt(120, y + 22, lab, "mono"))
        s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (222, y + 18, 300, y + 18)))
        s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" class="st"/>' % (
            302, y, 300, 36))
        s.append(txt(452, y + 22, res, "mono"))
        y += 48
    # 顶部框 → 左侧竖干 → 每一行
    s.append('<path d="M380,58 L%.1f,58 L%.1f,%.1f" class="lnSoft" fill="none"/>' % (bus, bus, y - 30))
    for i in range(len(rows)):
        yy = 86 + i * 48 + 18
        s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (bus, yy, 18, yy), "lnSoft"))
    # 右侧汇合 → 拼成最终答复
    s.append('<path d="M602,104 L626,104 L626,%d L%.1f,%d" class="lnSoft" fill="none"/>' % (
        y - 6, 452, y - 6))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (452, y - 6, 452, y + 18)))
    s.append(box(320, y + 18, 264, 44, "拼成最终答复", "机械拼装，不由模型重写"))
    return '<svg viewBox="0 0 700 %d" class="figsvg">%s</svg>' % (y + 80, "".join(s))


# ══════════════════════════ 页面 ══════════════════════════
HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>标准程序流程图 · 三种架构与训练 / 评估闭环</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Outfit:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#f7f5f0; --card:#fff; --line:#e9e3d6; --line-soft:#f0ebe0;
    --ink:#14171e; --ink2:#3a4256; --ink3:#7c7a72;
    --primary:#2f6f5e; --primary-l:#4a8e7c; --accent:#c97b3f; --warn:#b06367; --gold:#b08430;
    --mono:'JetBrains Mono',monospace; --sans:'Outfit',sans-serif; --serif:'DM Serif Display',serif;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1100px;margin:0 auto;padding:32px 24px 72px}
  h1{font-family:var(--serif);font-weight:400;font-size:33px;line-height:1.22;margin:0 0 8px}
  h2{font-family:var(--serif);font-weight:400;font-size:24px;margin:0 0 4px}
  h3{font-size:15.5px;font-weight:600;margin:0 0 8px;display:flex;align-items:center;gap:8px}
  p{margin:0 0 10px;color:var(--ink2)}
  code{font-family:var(--mono);font-size:12.5px;background:#f1ede3;padding:1px 5px;border-radius:4px;color:var(--primary)}
  .lede{font-size:16px;margin:0 0 4px}
  .meta{font-size:13px;color:var(--ink3);font-family:var(--mono);margin:0 0 22px}
  .sec{margin:0 0 44px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px;box-shadow:0 2px 8px rgba(0,0,0,.04)}
  .fig{background:#fcfbf8;border:1px solid var(--line);border-radius:12px;padding:12px 8px;margin:10px 0 4px;overflow-x:auto}
  .figsvg{display:block;min-width:560px;width:100%;height:auto}
  .cap{font-size:12.5px;color:var(--ink3);font-family:var(--mono);text-align:center;margin:0 0 12px}
  .lgd{display:flex;flex-wrap:wrap;gap:14px;font-size:12.5px;color:var(--ink2);font-family:var(--mono);margin:0 0 10px}
  .lgd span{display:inline-flex;align-items:center;gap:6px}
  .sw{width:16px;height:13px;border-radius:2px;display:inline-block;border-width:1.6px;border-style:solid}
  .note{font-size:13px;color:var(--ink3);border-left:2px solid var(--line);padding-left:12px;margin:10px 0 0}
  .hl{background:rgba(47,111,94,.07);border-radius:10px;padding:13px 16px;margin:0 0 14px}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  table{width:100%;border-collapse:collapse;font-size:13.5px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line-soft);vertical-align:top}
  th{font-weight:600;background:#faf8f3;font-size:13px}
  .yes{color:var(--primary);font-weight:600}.no{color:var(--warn);font-weight:600}
  .kv{display:grid;grid-template-columns:100px 1fr;font-size:13.5px}
  .kv>div{padding:7px 0;border-bottom:1px dashed var(--line)}
  .kv>div:nth-child(odd){color:var(--ink3);font-family:var(--mono);font-size:12.5px}
  .foot{border-top:1px solid var(--line);padding-top:16px;font-size:12.5px;color:var(--ink3);font-family:var(--mono)}
  /* ── 标准流程图记号 ── */
  .st{fill:#ffffff;stroke:#3a4256;stroke-width:1.6}
  .stHot{fill:#eef4f1;stroke:#2f6f5e;stroke-width:1.6}
  .stBad{fill:#fbf0f0;stroke:#b06367;stroke-width:1.6}
  .term{fill:#eef4f1;stroke:#2f6f5e;stroke-width:1.8}
  .io{fill:#fdf4ec;stroke:#c97b3f;stroke-width:1.6}
  .dec{fill:#faf4e6;stroke:#b08430;stroke-width:1.6}
  .ln{fill:none;stroke:#3a4256;stroke-width:1.6}
  .lnSoft{fill:none;stroke:#b9b3a4;stroke-width:1.4;stroke-dasharray:4 3}
  .lbl{font-family:'Outfit',sans-serif;font-size:13px;fill:#14171e}
  .mono{font-family:'JetBrains Mono',monospace;font-size:10.5px;fill:#7c7a72}
  @media(max-width:768px){.wrap{padding:24px 16px 56px}h1{font-size:27px}h2{font-size:21px}.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">

<h1>标准程序流程图</h1>
<p class="lede">三种架构 + 训练闭环 + 评估闭环，全部用标准流程图记号画：<b>胶囊形＝起止</b>、<b>矩形＝处理</b>、<b>菱形＝判断</b>、<b>平行四边形＝输入输出</b>。</p>
<p class="meta">数据 commit 20e167207ebb ｜ 实验 cmp8 ｜ 2026-10-20</p>

<div class="hl">
  <b>图例</b>
  <div class="lgd" style="margin-top:8px">
    <span><i class="sw" style="background:#eef4f1;border-color:#2f6f5e"></i>起止（胶囊）</span>
    <span><i class="sw" style="background:#fff;border-color:#3a4256"></i>处理（矩形）</span>
    <span><i class="sw" style="background:#faf4e6;border-color:#b08430"></i>判断（菱形）</span>
    <span><i class="sw" style="background:#fdf4ec;border-color:#c97b3f"></i>输入/输出（平行四边形）</span>
    <span><i class="sw" style="background:#eef4f1;border-color:#2f6f5e"></i>学到的策略在起作用</span>
  </div>
</div>

<div class="sec">
  <h2>图 1 · 直调（A1）</h2>
  <p>没有结构：一次调用出答案，不接触依据包。</p>
  <div class="fig">__FIG_A1__</div>
  <p class="cap">图 1　A1 直调：无分支、无判断、无依据包</p>
</div>

<div class="sec">
  <h2>图 2 · 双轴（A3 融合门 / A4 去融合门）—— 人设计的树形</h2>
  <p>5 路扇出后，<b>末步模式在构造时就定了</b>（<code>mode</code> 参数），不是运行时判断。</p>
  <div class="fig">__FIG_DUAL__</div>
  <p class="cap">图 2　双轴：扇出 5 路 → 末步二选一 → 一篇答案</p>
</div>

<div class="sec">
  <h2>图 3 · 新架构（A5）—— 链式执行 + 图状态</h2>
  <p>主循环每一步<b>枚举候选 → 打分 → 选一条边执行</b>；<code>VERIFY</code> 是唯一接触依据包的操作；
     <code>STOP</code> 需要先核验过一次才合法（否则策略永远走不到 VERIFY）。</p>
  <div class="fig">__FIG_A5__</div>
  <p class="cap">图 3　A5：while 步数 &lt; 10 的主循环，操作由 w · f 选出</p>
  <div class="grid2" style="margin-top:14px">
    <div class="card">
      <h3>装配规则（机械拼装，不由模型重写）</h3>
      <div class="fig">__FIG_ASM__</div>
    </div>
    <div class="card">
      <h3>这一步的代价</h3>
      <div class="kv">
        <div>候选枚举</div><div>每步 7 个操作，其中 VERIFY 最多取 2 条未核验断言</div>
        <div>特征</div><div>14 维，<b>与题目无关</b> ⇒ n = 决策次数</div>
        <div>探索</div><div>ε = 0.25，随机加分 <b>0–2.0</b></div>
        <div>策略信号</div><div>w·f 最大仅 ~0.09 ⇒ <b>被噪声压过 20 倍</b></div>
        <div>装配产出</div><div>⑤a 3/12 ｜ ⑤c 5/12 ｜ ⑤b 9/12 有装配版</div>
      </div>
      <p class="note">⇒ ⑤a/⑤c 多数<b>没产出装配版</b>（没有 VERIFY 就没有"经核验成立的依据"），
        分析器回退到<b>裸答案</b> ⇒ A5 三臂交付的不是同一种东西。</p>
    </div>
  </div>
</div>

<div class="sec">
  <h2>图 4 · 训练闭环（REINFORCE）—— 那个"训练出来的流程"是怎么来的</h2>
  <p>人只定「7 个操作」和「14 维特征」，<b>走法由训练产出</b>。目标函数是<b>约束优化</b>：<code>max 宽度 s.t. 矛盾率 ≤ 最优基线</code>。</p>
  <div class="fig">__FIG_TRAIN__</div>
  <p class="cap">图 4　训练：rollout → 约束判定 → policy gradient → 更新 w</p>
</div>

<div class="sec">
  <h2>图 5 · 评估闭环（判官闸门）</h2>
  <p>判官是跨厂商的（被测 MiniMax / 判官 <code>x-ai/grok-4.3</code>，temperature 0.0）。<b>自检不过就拒绝出数</b>，不是出完数再解释。</p>
  <div class="fig">__FIG_EVAL__</div>
  <p class="cap">图 5　评估：自检闸门 → 逐条核验 → 去重 → 统计</p>
</div>

<div class="sec">
  <h2>三个生成器：谁在决定答案</h2>
  <table>
    <thead><tr><th style="width:150px">层</th><th>A1 直调</th><th>A3 / A4 双轴</th><th>A5 新架构</th></tr></thead>
    <tbody>
      <tr><td>谁定"问什么"</td><td>人</td><td>人</td><td>人</td></tr>
      <tr><td>谁定"怎么搜"</td><td>—</td><td class="yes">人（树形：扇出 + 门）</td><td>人定操作集，<b>训练定走法</b></td></tr>
      <tr><td>谁定"用哪条依据"</td><td>没人用</td><td>没人用</td><td class="yes">只有 VERIFY 用</td></tr>
      <tr><td>搜索形态</td><td>无</td><td><b>树形</b>（深度 2）</td><td><b>链式</b>（≤10 步）+ <b>图</b>状态</td></tr>
      <tr><td>embedding</td><td class="no">搜索中不用</td><td class="no">搜索中不用</td><td class="no">搜索中不用</td></tr>
      <tr><td>embedding 用在哪</td><td colspan="3" class="yes">只在<b>评估侧</b>：算去重宽 width（阈值 0.75）与离散度 disp；embed 失败降级到字符 bigram</td></tr>
      <tr><td>调用数</td><td>1</td><td>6–7</td><td>≤10 步 × 1 调/步</td></tr>
    </tbody>
  </table>
  <p class="note">⚠️ A5 里"链式"和"图"不冲突：每步只走一条边（链式），但这条边可以从任意已有节点长出（图的性质）⇒ 实际轨迹是<b>图上的一条路径</b>，不是固定形状的树。</p>
</div>

<div class="foot">
  对照源码：creativity_lab/arms/dual.py · creativity_lab/ops.py · cmp8/creativity_lab/learnarch.py · cmp8/analyze_cmp6.py · creativity_lab/train_policy.py
</div>

</div>
</body>
</html>
"""

html = (HTML
        .replace("__FIG_A1__", fig_a1())
        .replace("__FIG_DUAL__", fig_dual())
        .replace("__FIG_A5__", fig_a5())
        .replace("__FIG_ASM__", fig_assemble())
        .replace("__FIG_TRAIN__", fig_train())
        .replace("__FIG_EVAL__", fig_eval()))

p = os.path.join(OUT_DIR, "index.html")
io.open(p, "w", encoding="utf-8").write(html)
print("✅ %s  (%d 字节)" % (p, os.path.getsize(p)))
