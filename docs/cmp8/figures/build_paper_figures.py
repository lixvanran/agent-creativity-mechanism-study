#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成论文用图（2026-10-25 投稿版）。

★ 纪律：**图与规格同源** —— 每一张图的每个框都对应代码里一个真实机制/读数，
  不得画代码里没有的东西（我们被"漂亮但不存在"的图坑过）。
"""
import io
import os

OUT_DIR = "/workspace/lab/visual-page/paper-figures"
os.makedirs(OUT_DIR, exist_ok=True)


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def txt(x, y, s, cls="lbl", anchor="middle", dy=0, fs=None):
    style = ' font-size="%dpx"' % fs if fs else ""
    return ('<text x="%.1f" y="%.1f" text-anchor="%s" class="%s"%s>%s</text>'
            % (x, y + dy, anchor, cls, style, esc(s)))


def box(x, y, w, h, label, sub=None, kind="st", fs=13):
    s = ['<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" class="%s"/>'
         % (x, y, w, h, kind)]
    if sub:
        s.append(txt(x + w / 2, y + h / 2 - 9, label, "lbl", fs=fs))
        s.append(txt(x + w / 2, y + h / 2 + 10, sub, "mono"))
    else:
        s.append(txt(x + w / 2, y + h / 2 + 5, label, "lbl", fs=fs))
    return "".join(s)


def arrow(d, cls="ln"):
    return '<path d="%s" class="%s" marker-end="url(#ah)"/>' % (d, cls)


def lbl(x, y, s, cls="mono", anchor="middle"):
    return '<text x="%.1f" y="%.1f" text-anchor="%s" class="%s">%s</text>' % (
        x, y, anchor, cls, esc(s))


# ══════════════════════════════════════════════════════════════════════
# 图 1 · 四层定位：我们做什么 / 不做什么
# ══════════════════════════════════════════════════════════════════════
def fig_layers():
    s = []
    W, H = 980, 500
    layers = [
        ("层 1", "问题描述 & 原因", "transformer 的注意力机制", "todo"),
        ("层 2", "用「设计的手段」优化", "架构先验设计，运行时不自修改", "ours"),
        ("层 3", "用「训练/自迭代」优化", "系统根据自身经验修改自己", "ours"),
        ("层 4", "Agent 的状态驱动", "由内部状态决定当下动作", "todo"),
    ]
    y = 30
    lpos = {}
    for tag, name, sub, kind in layers:
        s.append(box(30, y, 300, 78, "%s · %s" % (tag, name), sub,
                      kind="ours" if kind == "ours" else "todo", fs=14))
        lpos[tag] = y + 39
        y += 100
    # 右侧：逐层对应（箭头各自从本层出发）
    right = [
        ("层 1", 30, "层 1 · 原因（注意力机制）",
         "★ 第二组交付；本稿 §2 预留未并入", "todo"),
        ("层 2", 200, "★ 本稿交付：层 2 + 层 3",
         "层 2 = W_design_L2（evolve=False）\n层 3 = W_train_L3（evolve=True）", "ours"),
        ("层 4", 290, "层 4 · 状态驱动",
         "未做（层 3 是跨轮累积；层 4 是状态决定当下动作）", "todo"),
    ]
    for tag, ry, title, sub, kind in right:
        s.append(box(470, ry, 480, 76, title, sub, kind=kind, fs=13))
        s.append(arrow("M 332 %d C 400 %d 400 %d 466 %d"
                       % (lpos[tag], lpos[tag], ry + 38, ry + 38)))
    s.append(box(470, 392, 480, 96, "层 2 ⇄ 层 3 的关系",
                 "★ 同一个 evolve 开关 ⇒ 层 2 天然是层 3 的消融臂\n"
                 "⇒ 不是两个平行系统；消融对照不被代码分叉破坏", kind="key", fs=13))
    s.append(lbl(710, 466, "层 2 = 层 3 − 「演化」这一个自由度", "key"))
    return '<svg viewBox="0 0 %d %d" class="figsvg">%s</svg>' % (W, H, "".join(s))


# ══════════════════════════════════════════════════════════════════════
# 图 2 · W 工作流：层 2 主干 + 层 3 的分叉点
# ══════════════════════════════════════════════════════════════════════
def fig_workflow():
    s = []
    W, H = 1080, 560
    s.append(box(20, 26, 210, 58, "题面 + 依据包", "依据只进核验侧", kind="io"))
    s.append(box(20, 112, 250, 96, "① 认知帧解耦",
                 "Fisher-Yates + PRNG\n必含 1 wild 帧\n★ 槽位互不可见", kind="st", fs=12))
    s.append(arrow("M 125 84 L 125 108"))
    for i, fid in enumerate(["hardware-eyes", "ten-year-old", "ops-3am"]):
        s.append(box(280, 96 + i * 66, 215, 54, "槽位 %d · %s" % (i + 1, fid),
                     "各写各的（看不见别人）", kind="st", fs=11))
        s.append(arrow("M 270 160 C 276 160 276 %d 278 %d" % (123 + i * 66, 123 + i * 66)))
    s.append(box(280, 300, 215, 58, "② 逐槽位抽断言", "只抄原文里有的", kind="st", fs=12))
    s.append(box(530, 96, 215, 78, "③ 离散去冗余",
                 "数字指纹 + 4-gram\n★ 零 embedding", kind="st", fs=12))
    s.append(box(530, 200, 215, 78, "④ 矛盾检测",
                 "选项判定 / 数字冲突\n★ 零判官成本", kind="key", fs=12))
    s.append(box(530, 304, 215, 78, "⑤ 机械装配",
                 "去冗余后直接装配\n★ 不让模型再总结", kind="key", fs=12))
    for yy in (123, 189, 255):
        s.append(arrow("M 495 %d L 526 %d" % (yy, 135)))
    s.append(arrow("M 637 174 L 637 196"))
    s.append(arrow("M 637 278 L 637 300"))
    # 层 3 的回环（走上方，不穿框）
    s.append(box(800, 200, 250, 78, "⑥ 动作演化（层 3）",
                 "36 个可组合动作\n47 参数因子化 softmax", kind="ours", fs=12))
    s.append(arrow("M 745 239 L 796 239"))
    s.append('<path d="M 925 200 C 1000 200 1000 60 300 60 L 300 92" '
             'class="ln evo" marker-end="url(#ah)"/>')
    s.append(lbl(560, 36, "下一轮用新动作重跑 ⇒ 搜索空间在运行中变大", "key"))
    # 层2/层3 的开关
    s.append(box(800, 40, 250, 66, "层 2 / 层 3 开关",
                 "evolve = False / True", kind="ours", fs=12))
    s.append(arrow("M 800 73 C 700 73 700 130 745 135"))
    # 读数侧
    s.append(box(280, 420, 465, 82, "判官读数（承重检验 C1/C2/C3）",
                 "承重维度数 · 净维度增益（双边）· 锚外新增 VD_anchor_out",
                 kind="eval", fs=13))
    s.append(arrow("M 637 382 L 637 416"))
    s.append(box(800, 420, 250, 82, "中庸度四指标",
                 "交集率 / 边际利用率\n中庸距离 / 覆盖饱和度", kind="eval", fs=11))
    s.append(arrow("M 745 460 L 796 460"))
    s.append('<path d="M 1050 460 C 1072 460 1072 528 520 528 L 520 386" '
             'class="ln evo" marker-end="url(#ah)"/>')
    return '<svg viewBox="0 0 %d %d" class="figsvg">%s</svg>' % (W, H, "".join(s))


# ══════════════════════════════════════════════════════════════════════
# 图 3 · 度量链：什么算「维度」
# ══════════════════════════════════════════════════════════════════════
def fig_metrics():
    s = []
    W, H = 900, 400
    s.append(box(30, 30, 220, 62, "一条陈述 c", "答案里抽出的一条具体判断", kind="io"))
    s.append(box(300, 20, 250, 82, "C1 决策岔口可指名",
                 "写得出一个具体决策\n（属于预注册 C_t 或其子集）", kind="st", fs=12))
    s.append(box(600, 20, 285, 82, "C2 删除反事实成立",
                 "删掉 c ⇒ C_t 里至少一条结论\n从「可支持」变「不可支持」", kind="st", fs=12))
    s.append(box(300, 122, 250, 82, "C3 在结论空间内",
                 "⚠️ 锚外一律不算维度\n★ 这是主命题的结构性障碍", kind="warn", fs=12))
    s.append(box(600, 122, 270, 82, "承重族（family_key）",
                 "该卡支撑的结论集合\n⇒ 维度数 = 去冗余后的族数", kind="key", fs=12))
    s.append(arrow("M 250 61 L 296 61"))
    s.append(arrow("M 550 61 L 596 61"))
    s.append(arrow("M 425 102 L 425 118"))
    s.append(arrow("M 550 163 L 596 163"))
    s.append(box(20, 240, 270, 76, "净维度增益（双边）",
                 "新增 − 丢失\n★ 只报净值会掩盖「丢光基线」", kind="key", fs=12))
    s.append(box(320, 240, 250, 76, "锚外新增 VD_anchor_out",
                 "支撑的结论 ⊄ C_t 的新族数\n★ 恒为 0 ⇒ 主命题不成立", kind="ours", fs=12))
    s.append(box(610, 240, 260, 76, "中庸度四指标",
                 "交集率 / 边际利用率\n中庸距离 / 覆盖饱和度", kind="eval", fs=12))
    s.append(arrow("M 735 204 L 735 236"))
    s.append(arrow("M 610 278 L 574 278"))
    s.append(arrow("M 320 278 L 294 278"))
    s.append(lbl(450, 348, "★ 全部离散结构量：不依赖 embedding、不依赖措辞相似度", "key"))
    return '<svg viewBox="0 0 %d %d" class="figsvg">%s</svg>' % (W, H, "".join(s))


HTML = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>论文图 · 治塌缩工作流</title>
<style>
 body{font-family:-apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif;
      background:#fbfbfa;color:#1a1a1a;margin:0;padding:26px 30px}
 h1{font-size:20px;margin:0 0 4px}
 .sub{color:#666;font-size:13px;margin-bottom:22px}
 .fig{background:#fff;border:1px solid #e2e2df;border-radius:6px;
      padding:14px 16px;margin:0 0 22px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
 .cap{font-size:12px;color:#555;margin-top:8px;font-family:ui-monospace,Menlo,monospace}
 .figsvg{display:block;min-width:720px;width:100%;height:auto}
 text{font-family:-apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif;fill:#1a1a1a}
 .lbl{font-size:13px;font-weight:600}
 .mono{font-size:11px;fill:#555}
 .key{font-size:12px;fill:#9a3412;font-weight:600}
 rect.st{fill:#f6f7f9;stroke:#c9cdd4;stroke-width:1.2}
 rect.io{fill:#eef4fb;stroke:#9db8d6;stroke-width:1.2}
 rect.ours{fill:#eefaf2;stroke:#4a9a6a;stroke-width:1.6}
 rect.todo{fill:#f7f4f0;stroke:#c8bdae;stroke-width:1.2;stroke-dasharray:5 3}
 rect.key{fill:#fff6ec;stroke:#d98a3a;stroke-width:1.6}
 rect.eval{fill:#f2f0fb;stroke:#8f86c9;stroke-width:1.4}
 rect.warn{fill:#fdf0f0;stroke:#c97070;stroke-width:1.5}
 path.ln{fill:none;stroke:#7a8290;stroke-width:1.5}
 path.evo{fill:none;stroke:#d98a3a;stroke-width:2;stroke-dasharray:6 4}
 marker#ah markerWidth=9 markerHeight=9 refX=8 refY=3 orient=auto
   markerUnits=strokeWidth{path d="M0,0 L0,6 L9,3 z" fill="#7a8290"}
</style></head><body>
<h1>治塌缩工作流 · 论文图（投稿 2026-10-25）</h1>
<div class="sub">图与代码同源：每个框都对应 workflow.py / measure_answer() 里的真实机制或读数</div>

<div class="fig"><div id="f1"></div>
<div class="cap">图 1 · 四层定位。层 2 与层 3 由同一个 evolve 开关实现 ⇒ 层 2 天然是层 3 的消融臂。
层 1（注意力机制层面的原因）由第二组交付；层 4（状态驱动）未做。</div></div>

<div class="fig"><div id="f2"></div>
<div class="cap">图 2 · W 工作流。★ 槽位互不可见；矛盾检测零判官成本；机械装配不丢信息；
层 3 的回环＝用新动作重跑 ⇒ 搜索空间在运行中变大。</div></div>

<div class="fig"><div id="f3"></div>
<div class="cap">图 3 · 度量链。★ C3「锚外一律不算维度」是主命题的结构性障碍 ⇒ 因此需要
VD_anchor_out 这个会让我们自己失败的量。</div></div>

<script>
const F1 = `__F1__`, F2 = `__F2__`, F3 = `__F3__`;
document.getElementById('f1').innerHTML = F1;
document.getElementById('f2').innerHTML = F2;
document.getElementById('f3').innerHTML = F3;
</script>
</body></html>
"""

# ★ 反引号模板字符串 ⇒ SVG 里的 `</text>` 无需转义
html = (HTML.replace("__F1__", fig_layers())
            .replace("__F2__", fig_workflow())
            .replace("__F3__", fig_metrics()))

p = os.path.join(OUT_DIR, "index.html")
io.open(p, "w", encoding="utf-8").write(html)
print("✅ %s  (%d 字节)" % (p, os.path.getsize(p)))
