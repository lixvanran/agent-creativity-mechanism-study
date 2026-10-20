#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「思维面 = 有效信息维度数 · 三路线」标准程序流程图 HTML。

四张图：
  图1  有效信息维度的测量流水线（从答案到净维度增益）
  图2  维度卡片的准入流水线（承重检验 + 去冗余检验）
  图3  三条路线泳道对照（谁决定什么）
  图4  预注册 → 跑批 → 闸门 → 指标 → 否证判定

记号沿用标准流程图：胶囊=起止 矩形=处理 菱形=判断 平行四边形=输入输出。
"""
import io
import os

OUT_DIR = "/workspace/lab/visual-page/routes-flowcharts"
os.makedirs(OUT_DIR, exist_ok=True)


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, cls="lbl", anchor="middle"):
    return ('<text x="%.1f" y="%.1f" text-anchor="%s" class="%s">%s</text>'
            % (x, y, anchor, cls, esc(s)))


def box(x, y, w, h, label, sub=None, kind="st"):
    s = ['<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%s" class="%s"/>' % (
        x, y, w, h, "18" if kind == "term" else "2", kind)]
    if sub:
        s.append(txt(x + w / 2, y + h / 2 - 9, label, "lbl"))
        s.append(txt(x + w / 2, y + h / 2 + 11, sub, "mono"))
    else:
        s.append(txt(x + w / 2, y + h / 2 + 5, label, "lbl"))
    return "".join(s)


def diamond(cx, cy, w, h, label, sub=None, kind="dec"):
    p = "%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" % (
        cx, cy - h / 2, cx + w / 2, cy, cx, cy + h / 2, cx - w / 2, cy)
    s = ['<polygon points="%s" class="%s"/>' % (p, kind)]
    if sub:
        s.append(txt(cx, cy - 9, label, "lbl"))
        s.append(txt(cx, cy + 11, sub, "mono"))
    else:
        s.append(txt(cx, cy + 5, label, "lbl"))
    return "".join(s)


def para(cx, cy, w, h, label, sub=None):
    sk = 12
    p = "%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" % (
        cx - w / 2 + sk, cy - h / 2, cx + w / 2, cy - h / 2,
        cx + w / 2 - sk, cy + h / 2, cx - w / 2, cy + h / 2)
    s = ['<polygon points="%s" class="io"/>' % p]
    if sub:
        s.append(txt(cx, cy - 9, label, "lbl"))
        s.append(txt(cx, cy + 11, sub, "mono"))
    else:
        s.append(txt(cx, cy + 5, label, "lbl"))
    return "".join(s)


def arrow(d, cls="ln"):
    return '<path d="%s" class="%s" marker-end="url(#ah)"/>' % (d, cls)


def label(x, y, s, cls="mono", anchor="middle"):
    return ('<text x="%.1f" y="%.1f" text-anchor="%s" class="%s">%s</text>'
            % (x, y, anchor, cls, esc(s)))


# ═══════════════════ 图 1 · 有效信息维度的测量流水线 ═══════════════════
def fig_measure():
    s = []
    cx = 330
    y = 14
    s.append(box(cx - 66, y, 132, 34, "开始", kind="term")); y += 34
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(para(cx, y + 23, 250, 46, "输入：问题 ask", "＋ 依据包（16 条原子事实）")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 135, y, 270, 46, "生成答案（被测臂）", "直调 / 路线A / 路线B / 路线C · 等预算")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 120, y, 240, 44, "机械抽取断言", "extract_claims · 不由模型重写")); y += 44
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 135, y, 270, 46, "核验 verdict", "支持 / 矛盾 / 未提及 / 非主张")); y += 46

    # 质量闸门（菱形）
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(diamond(cx, y + 42, 330, 84, "质量闸门通过？", "parsefail · valid/total · 判官自检可复现"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(label(cx + 178, y + 26, "否 ⇒ 停该臂", "mono", "start"))
    s.append(box(cx + 178, y + 38, 168, 48, "如实报 valid/total", "不许重跑到好看", "stBad"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 166, y + 42, cx + 176, y + 42), "lnSoft"))
    y += 84

    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 150, y, 300, 48, "构造成「维度卡片」", "证据类别分层 · 原题映射 · 决策含义")); y += 48
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(diamond(cx, y + 42, 340, 84, "承重检验：改变了哪个决策/结论？",
                     "写不出来 ⇒ 不是维度，只是内容"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(label(cx + 182, y + 26, "否 ⇒ 剔除", "mono", "start"))
    s.append(box(cx + 182, y + 38, 168, 48, "剔除（不计入维度数）", None, "stBad"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 170, y + 42, cx + 180, y + 42), "lnSoft"))
    y += 84

    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(diamond(cx, y + 42, 360, 84, "去冗余：I(A,B)=D(A∪B)−D(A)−D(B)+D(∅)",
                     "≈0 ⇒ 与已有维度冗余 ⇒ 合并"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(label(cx + 192, y + 26, "是 ⇒ 合并/剔除", "mono", "start"))
    s.append(box(cx + 192, y + 38, 168, 48, "合并进已有维度", None, "stBad"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 180, y + 42, cx + 190, y + 42), "lnSoft"))
    y += 84

    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 120, y, 240, 44, "维度集合 D", "每张卡片带关系标注")); y += 44
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 150, y, 300, 48, "与基线（直调）比对",
                 "新增 = D臂 \\ D基线 ｜ 丢失 = D基线 \\ D臂")); y += 48
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 140, y, 280, 50, "净维度增益 = |新增| − |丢失|",
                 "必须同时报绝对条数与分母", "stHot")); y += 50
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 140, y, 280, 46, "反判据", "矛盾率(带分母) · 成本 · 正确答案是否丢失")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 20))); y += 20
    s.append(box(cx - 66, y, 132, 34, "结束", kind="term")); y += 34
    return '<svg viewBox="0 0 700 %d" class="figsvg">%s</svg>' % (y + 16, "".join(s))


# ═══════════════════ 图 2 · 维度卡片准入流水线 ═══════════════════
def fig_card():
    s = []
    y = 20
    bw, gap = 126, 22
    x0 = 16
    stages = [
        ("候选断言", "来自抽取", "io"),
        ("证据类别分层", "事实/推论/价值判断/建议", "st"),
        ("原题映射", "映射不回去 ⇒ 剔除", "st"),
        ("承重检验", "改变了哪个决策？", "dec"),
        ("去冗余检验", "I(A,B) > 0 ？", "dec"),
        ("维度卡片", "带关系标注", "stHot"),
    ]
    for i, (t, sub, k) in enumerate(stages):
        x = x0 + i * (bw + gap)
        s.append(box(x, y, bw, 56, t, sub, k))
        if i:
            s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (x - gap + 2, y + 28, x - 2, y + 28)))
    # 剔除分支
    for i, lab in ((2, "剔除"), (3, "剔除"), (4, "合并")):
        x = x0 + i * (bw + gap) + bw / 2
        s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (x, y + 56, x, y + 92), "lnSoft"))
        s.append(label(x, y + 106, lab, "mono"))
    # 关系标注区（标题在上、关系框在下，**不重叠**）
    total_w = 6 * bw + 5 * gap
    y2 = y + 132
    s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="92" rx="3" class="st"/>' % (
        x0, y2, total_w))
    s.append(txt(x0 + total_w / 2, y2 + 24, "关系标注（与已有卡片）", "lbl"))
    rels = ["重复", "细化", "矛盾", "互补", "条件依赖"]
    rw = (total_w - 40) / len(rels)
    for i, r in enumerate(rels):
        rx = x0 + 20 + i * rw
        s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="34" rx="2" class="st"/>'
                 % (rx, y2 + 46, rw - 12))
        s.append(txt(rx + (rw - 12) / 2, y2 + 67, r, "mono"))
    # 顶部标题框 → 关系区
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (x0 + 5 * bw + 4.5 * gap, y + 56,
                                              x0 + 5 * bw + 4.5 * gap, y2), "lnSoft"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (x0 + 5 * bw + 4.5 * gap, y2, x0 + 20, y2)))
    return '<svg viewBox="0 0 %d %d" class="figsvg">%s</svg>' % (
        x0 + total_w + 20, y2 + 112, "".join(s))


# ═══════════════════ 图 3 · 三条路线泳道对照 ═══════════════════
def fig_routes():
    s = []
    W = 660
    lanes = [
        ("路线A", "设计架构", "人定拓扑 · 零训练",
         [("人定拓扑", "可证伪的结构"), ("固定执行", "固定流程"),
          ("联合门控", "新颖-效用"), ("输出答案", "")], "stHot"),
        ("路线B", "训练架构", "操作序列由训练学出",
         [("w=0 起始", "零先验"), ("采样操作", "图状态"),
          ("奖励", "有效维度代理"), ("更新 w", "on-policy")], "st"),
        ("路线C", "先设计再训练", "人定拓扑 + 训练调参数",
         [("定拓扑", "人或受约束提案器"), ("拓扑冻结", "变量少"),
          ("训练参数", "阈值/预算/门控"), ("输出答案", "")], "st"),
    ]
    y = 16
    lane_h = 116
    for li, (tag, name, sub, steps, kind) in enumerate(lanes):
        ly = y + li * (lane_h + 16)
        s.append('<rect x="16" y="%.1f" width="%.1f" height="%.1f" rx="3" class="lane"/>'
                 % (ly, W + 16, lane_h))
        s.append('<rect x="16" y="%.1f" width="104" height="%.1f" rx="3" class="%s"/>'
                 % (ly, lane_h, kind))
        s.append(txt(68, ly + lane_h / 2 - 12, tag, "lbl"))
        s.append(txt(68, ly + lane_h / 2 + 6, name, "lbl"))
        s.append(txt(68, ly + lane_h / 2 + 24, sub, "mono"))
        sx0 = 132
        sw = (W - (sx0 - 16) - 16 - 3 * 12) / 4
        for i, (t, sb) in enumerate(steps):
            sx = sx0 + i * (sw + 12)
            s.append(box(sx, ly + 28, sw, 58, t, sb or None, "st"))
            if i:
                s.append(arrow("M%.1f,%.1f L%.1f,%.1f"
                               % (sx - 12, ly + 57, sx - 2, ly + 57)))
    # 共用层
    cy = y + 3 * (lane_h + 16) + 8
    s.append('<rect x="16" y="%.1f" width="%.1f" height="96" rx="3" class="stHot"/>' % (
        cy, W + 16))
    s.append(txt(30, cy + 22, "三条路线共用同一层（否则不可比）", "lbl", "start"))
    common = ["同一测量协议", "同一对照片", "统计单位=任务", "同一成本闸门"]
    cw = (W + 16 - 56) / len(common)
    for i, c in enumerate(common):
        cx = 32 + i * cw
        s.append(box(cx, cy + 38, cw - 14, 42, c, None, "st"))
    return '<svg viewBox="0 0 %d %d" class="figsvg">%s</svg>' % (W + 32, cy + 116, "".join(s))


# ═══════════════════ 图 4 · 预注册 → 跑批 → 否证判定 ═══════════════════
def fig_experiment():
    s = []
    cx = 320
    y = 14
    s.append(box(cx - 190, y, 380, 48, "预注册（写死）", "假设 / 对照臂 / 预算 / 统计单位 / 排除口径 / 否证条件")); y += 48
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    s.append(para(cx, y + 23, 260, 46, "跑批", "等预算 · 任务为统计单位 · 种子固定")); y += 46
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    s.append(diamond(cx, y + 42, 320, 84, "仪器闸门通过？", "判官自检可复现 · temp=0 · parsefail 率"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    s.append(label(cx + 172, y + 26, "否 ⇒ 停", "mono", "start"))
    s.append(box(cx + 172, y + 38, 168, 48, "判官不可用", "不换模型、不静默变空串", "stBad"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx + 160, y + 42, cx + 170, y + 42), "lnSoft"))
    y += 84
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    s.append(box(cx - 150, y, 300, 48, "算指标", "净维度增益(带绝对分母) · 矛盾率 · 成本")); y += 48
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    s.append(diamond(cx, y + 42, 340, 84, "与噪声地板相比？", "逐任务重复的臂内波动"))
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    outs = [("显著 ⇒ 记「观察到净增益」", "stHot"),
            ("不显著 ⇒ 记「不可分辨」", "st"),
            ("矛盾率上升 ⇒ 该臂判死", "stBad")]
    bw2, bg = 210, 10
    x_first = cx - 1.5 * (bw2 + bg) + bg / 2
    bus_y = y + 52
    s.append('<path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f" class="lnSoft" fill="none"/>' % (
        cx, y + 42, cx, bus_y, x_first + 1.5 * (bw2 + bg) - bg / 2, bus_y))
    for i, (lab, k) in enumerate(outs):
        ox = x_first + i * (bw2 + bg) + bw2 / 2
        s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (ox, bus_y, ox, bus_y + 18), "lnSoft"))
        s.append(box(ox - bw2 / 2, bus_y + 20, bw2, 44, lab, None, k))
    y += 116
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    s.append(box(cx - 150, y, 300, 48, "留出集复核（防过拟合）",
                 "训练排名 vs 留出排名的 Spearman")); y += 48
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    s.append(box(cx - 120, y, 240, 38, "否证条件逐条判定", kind="term")); y += 38
    s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, y, cx, y + 18))); y += 18
    s.append(box(cx - 100, y, 200, 44, "决策（由负责人拍板）", "指标只提供证据", "stHot")); y += 44
    return '<svg viewBox="0 0 700 %d" class="figsvg">%s</svg>' % (y + 30, "".join(s))


HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>思维面 = 有效信息维度数 · 三路线程序流程图</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Outfit:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#f7f5f0; --card:#fff; --line:#e9e3d6; --line-soft:#f0ebe0;
    --ink:#14171e; --ink2:#3a4256; --ink3:#7c7a72;
    --primary:#2f6f5e; --primary-l:#4a8e7c; --accent:#c97b3f; --warn:#b06367; --gold:#b08430;
    --mono:'JetBrains Mono',monospace; --sans:'Outfit',sans-serif; --serif:'DM Serif Display',serif;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.65;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1120px;margin:0 auto;padding:32px 24px 72px}
  h1{font-family:var(--serif);font-weight:400;font-size:33px;line-height:1.22;margin:0 0 8px}
  h2{font-family:var(--serif);font-weight:400;font-size:23px;margin:0 0 6px}
  p{margin:0 0 10px;color:var(--ink2)}
  code{font-family:var(--mono);font-size:12.5px;background:#f1ede3;padding:1px 5px;border-radius:4px;color:var(--primary)}
  .lede{font-size:16px;margin:0 0 4px}
  .meta{font-size:13px;color:var(--ink3);font-family:var(--mono);margin:0 0 22px}
  .sec{margin:0 0 44px}
  .fig{background:#fcfbf8;border:1px solid var(--line);border-radius:12px;padding:12px 8px;margin:10px 0 4px;overflow-x:auto}
  .figsvg{display:block;min-width:600px;width:100%;height:auto}
  .cap{font-size:12.5px;color:var(--ink3);font-family:var(--mono);text-align:center;margin:0 0 12px}
  .lgd{display:flex;flex-wrap:wrap;gap:14px;font-size:12.5px;color:var(--ink2);font-family:var(--mono);margin:0 0 10px}
  .lgd span{display:inline-flex;align-items:center;gap:6px}
  .sw{width:16px;height:13px;border-radius:2px;display:inline-block;border-width:1.6px;border-style:solid}
  .note{font-size:13px;color:var(--ink3);border-left:2px solid var(--line);padding-left:12px;margin:10px 0 0}
  .hl{background:rgba(47,111,94,.07);border-radius:10px;padding:13px 16px;margin:0 0 14px}
  .warnbox{background:rgba(176,99,103,.07);border-radius:10px;padding:13px 16px;margin:0 0 14px}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  table{width:100%;border-collapse:collapse;font-size:13.5px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line-soft);vertical-align:top}
  th{font-weight:600;background:#faf8f3;font-size:13px}
  .yes{color:var(--primary);font-weight:600}.no{color:var(--warn);font-weight:600}
  .foot{border-top:1px solid var(--line);padding-top:16px;font-size:12.5px;color:var(--ink3);font-family:var(--mono)}
  .st{fill:#ffffff;stroke:#3a4256;stroke-width:1.6}
  .stHot{fill:#eef4f1;stroke:#2f6f5e;stroke-width:1.6}
  .stBad{fill:#fbf0f0;stroke:#b06367;stroke-width:1.6}
  .term{fill:#eef4f1;stroke:#2f6f5e;stroke-width:1.8}
  .io{fill:#fdf4ec;stroke:#c97b3f;stroke-width:1.6}
  .dec{fill:#faf4e6;stroke:#b08430;stroke-width:1.6}
  .lane{fill:#fbfaf6;stroke:#e9e3d6;stroke-width:1.4}
  .ln{fill:none;stroke:#3a4256;stroke-width:1.6}
  .lnSoft{fill:none;stroke:#b9b3a4;stroke-width:1.4;stroke-dasharray:4 3}
  .lbl{font-family:'Outfit',sans-serif;font-size:13px;fill:#14171e}
  .mono{font-family:'JetBrains Mono',monospace;font-size:10.5px;fill:#7c7a72}
  @media(max-width:768px){.wrap{padding:24px 16px 56px}h1{font-size:27px}h2{font-size:21px}.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">

<h1>思维面 ＝ 有效信息维度数</h1>
<p class="lede">三条路线（设计架构 / 训练架构 / 先设计再训练）共用<b>同一套测量协议</b>，
否则三条路线测的不是同一个东西。全部用标准流程图记号画：
<b>胶囊＝起止</b>、<b>矩形＝处理</b>、<b>菱形＝判断</b>、<b>平行四边形＝输入输出</b>。</p>
<p class="meta">2026-10-21 ｜ 负责人拍板：思维面 = 有效信息维度数 ｜ 今晚不跑 OpenRouter</p>

<div class="hl">
  <b>图例</b>
  <div class="lgd" style="margin-top:8px">
    <span><i class="sw" style="background:#eef4f1;border-color:#2f6f5e"></i>起止（胶囊）</span>
    <span><i class="sw" style="background:#fff;border-color:#3a4256"></i>处理（矩形）</span>
    <span><i class="sw" style="background:#faf4e6;border-color:#b08430"></i>判断（菱形）</span>
    <span><i class="sw" style="background:#fdf4ec;border-color:#c97b3f"></i>输入输出</span>
    <span><i class="sw" style="background:#eef4f1;border-color:#2f6f5e"></i>关键步骤</span>
    <span><i class="sw" style="background:#fbf0f0;border-color:#b06367"></i>剔除/失败</span>
  </div>
</div>

<div class="sec">
  <h2>图 1 · 有效信息维度的测量流水线</h2>
  <p class="cap">从答案到净维度增益。承重检验与去冗余检验是两道硬闸门；质量闸门不过就停该臂，不重跑到好看。</p>
  <div class="fig">__FIG1__</div>
</div>

<div class="sec">
  <h2>图 2 · 维度卡片的准入流水线</h2>
  <p class="cap">一条断言要成为"维度"，必须依次通过：证据类别分层 → 原题映射 → 承重检验 → 去冗余检验。</p>
  <div class="fig">__FIG2__</div>
  <p class="note">⚠️ <b>U4 校准点</b>：气质量表那题的有效维度可以<b>很少</b>（一条承重规则就够），
  但必须<b>能推出结论</b>。⇒ 「维度数」绝不能退化成「条数多」。</p>
</div>

<div class="sec">
  <h2>图 3 · 三条路线泳道对照</h2>
  <p class="cap">差别只在<b>谁决定什么</b>：A 全人定；B 全学；C 人定拓扑、训练调参数。三者共用同一层。</p>
  <div class="fig">__FIG3__</div>
</div>

<div class="sec">
  <h2>图 4 · 预注册 → 跑批 → 否证判定</h2>
  <p class="cap">指标只提供证据，决策由负责人拍板。"不显著"要记成「不可分辨」，不能记成"失败"，也不能记成"成功"。</p>
  <div class="fig">__FIG4__</div>
</div>

<div class="sec">
  <h2>三条路线一句话</h2>
  <table>
    <tr><th>路线</th><th>谁决定架构</th><th>能拿到什么</th><th>最大风险</th><th>怎么被否证</th></tr>
    <tr><td><b>A 设计架构</b></td><td>人（写死拓扑）</td><td>稳定、可复现、归因清楚</td><td>人的偏见无处收敛</td><td>与等预算多次采样比，净维度增益不显著</td></tr>
    <tr><td><b>B 训练架构</b></td><td>训练（策略学出）</td><td>能适应信息缺口</td><td>样本少必过拟合；搜索空间可能闭死</td><td>留出集不优于随机/固定；或只改了行为没改内容</td></tr>
    <tr><td><b>C 先设计再训练</b></td><td>人定拓扑 + 训练调参数</td><td>A 的归因清楚 + B 的自适应性</td><td>拓扑定错 ⇒ 参数再优也救不回来</td><td>与 A/B 对比分离不出"拓扑"这一项的贡献</td></tr>
  </table>
</div>

<div class="foot">
  图为<b>设计</b>（尚未跑实验）｜ 今晚不跑 OpenRouter 真实调用 ｜ 用户四道题全程不进训练/诊断集
</div>

</div>
<script>
</script>
</body>
</html>
"""

html = (HTML.replace("__FIG1__", fig_measure())
            .replace("__FIG2__", fig_card())
            .replace("__FIG3__", fig_routes())
            .replace("__FIG4__", fig_experiment()))
io.open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8").write(html)
print("✓ %s/index.html 已生成（%d 字节）" % (OUT_DIR, len(html)))
