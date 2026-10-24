#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路线 A 的固定拓扑流程图（8 节点）。

来源：`/workspace/lab/routes/A/DESIGN.md` §3.1「一张图」+ §3.2 伪代码。
（若路线 A 的 spec.yaml 落地，可用 build_spec_flowchart.py 改由规格驱动；
 本图与 DESIGN.md 同源，两边若不一致以 DESIGN.md 为准。）
"""
import io
import os

OUT_DIR = "/workspace/lab/visual-page/routes-flowcharts"
os.makedirs(OUT_DIR, exist_ok=True)

NODES = [
    ("N1", "槽位生成（第一轮）", "FA1 范围│FA2 依据│FA3 数量│FA4 分支", "st"),
    ("N2", "断言抽取（逐槽位）", "各 1 次调用 → 断言池（带槽位出处）", "st"),
    ("N3", "离散去冗余", "0 次调用 ｜ 两个独立实现 ⇒ strict/loose 两层", "st"),
    ("N4", "条件重采样（第二轮）", "FA5 例外│FA6 缺口 ｜ prompt 带「已覆盖清单」", "stHot"),
    ("N5", "断言抽取（第二轮）", "1 次批量调用", "st"),
    ("N6", "原子化拆分", "≤1 次调用 ｜ 长度≥40 字的条目拆开", "st"),
    ("N7", "D2 门", "效用轴=依据包逐条核验 ｜ 新颖轴=离散去冗余", "stHot"),
    ("N8", "机械装配", "0 次调用 ｜ 不由模型重写 → answer.md", "term"),
]
SIDE = [
    ("题面 P", "路线只看到 P", "io", "N1"),
    ("依据包 E", "只进核验侧", "io", "N7"),
]


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, cls="lbl", anchor="middle", size=None):
    st = ' style="font-size:%dpx"' % size if size else ""
    return ('<text x="%.1f" y="%.1f" text-anchor="%s" class="%s"%s>%s</text>'
            % (x, y, anchor, cls, st, esc(s)))


def box(x, y, w, h, label, sub=None, kind="st"):
    s = ['<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" class="%s"/>' % (
        x, y, w, h, kind)]
    if sub:
        s.append(txt(x + w / 2, y + h / 2 - 8, label, "lbl", "middle", 12.5))
        s.append(txt(x + w / 2, y + h / 2 + 12, sub, "mono"))
    else:
        s.append(txt(x + w / 2, y + h / 2 + 5, label, "lbl", "middle", 12.5))
    return "".join(s)


def para(cx, cy, w, h, label, sub=None):
    sk = 12
    p = "%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" % (
        cx - w / 2 + sk, cy - h / 2, cx + w / 2, cy - h / 2,
        cx + w / 2 - sk, cy + h / 2, cx - w / 2, cy + h / 2)
    s = ['<polygon points="%s" class="io"/>' % p]
    s.append(txt(cx, cy - 6, label, "lbl", "middle", 12.5))
    if sub:
        s.append(txt(cx, cy + 13, sub, "mono"))
    return "".join(s)


def arrow(d, cls="ln"):
    return '<path d="%s" class="%s" marker-end="url(#ah)"/>' % (d, cls)


def build():
    s = []
    W = 1000
    cx = 560
    y = 20
    bw, bh, gap = 430, 52, 30
    pos = {}
    for nid, lab, sub, kind in NODES:
        pos[nid] = (cx - bw / 2, y, bw, bh)
        y += bh + gap
    for nid, lab, sub, kind in NODES:
        x, yy, w, h = pos[nid]
        s.append(box(x, yy, w, h, "%s %s" % (nid, lab), sub, kind))
    for i in range(len(NODES) - 1):
        a = NODES[i][0]; b = NODES[i + 1][0]
        x, yy, w, h = pos[a]
        _, y2, _, _ = pos[b]
        s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (cx, yy + h, cx, y2 - 3)))
    # 侧输入
    for lab, sub, kind, target in SIDE:
        x, yy, w, h = pos[target]
        px = 120
        s.append(para(px, yy + h / 2, 180, 46, lab, sub))
        s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (px + 90, yy + h / 2, x - 3, yy + h / 2), "lnSoft"))
    H = y + 8
    return ('<svg viewBox="0 0 %d %d" class="figsvg">'
            '<defs><marker id="ah" markerWidth="9" markerHeight="7" refX="8" refY="3.5" '
            'orient="auto"><polygon points="0 0, 9 3.5, 0 7" fill="#3a4256"/></marker></defs>%s</svg>'
            % (W, H, "".join(s)))


HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>路线A · 固定拓扑流程图</title>
<style>
 :root{--bg:#f7f5f0;--card:#fff;--line:#e9e3d6;--ink:#14171e;--ink2:#3a4256;--ink3:#7c7a72;
 --primary:#2f6f5e;--mono:'JetBrains Mono',monospace;--sans:'Outfit',system-ui,sans-serif;--serif:'DM Serif Display',Georgia,serif}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.65}
 .wrap{max-width:1080px;margin:0 auto;padding:32px 24px 64px}
 h1{font-family:var(--serif);font-weight:400;font-size:30px;margin:0 0 6px}
 p{margin:0 0 10px;color:var(--ink2)}
 .meta{font-size:13px;color:var(--ink3);font-family:var(--mono);margin:0 0 20px}
 .fig{background:#fcfbf8;border:1px solid var(--line);border-radius:12px;padding:12px 8px;overflow-x:auto}
 .figsvg{display:block;min-width:820px;width:100%;height:auto}
 .cap{font-size:12.5px;color:var(--ink3);font-family:var(--mono);text-align:center;margin:10px 0 0}
 .st{fill:#fff;stroke:#3a4256;stroke-width:1.6}.stHot{fill:#eef4f1;stroke:#2f6f5e;stroke-width:1.6}
 .term{fill:#eef4f1;stroke:#2f6f5e;stroke-width:1.8}.io{fill:#fdf4ec;stroke:#c97b3f;stroke-width:1.6}
 .ln{fill:none;stroke:#3a4256;stroke-width:1.6}
 .lnSoft{fill:none;stroke:#b9b3a4;stroke-width:1.4;stroke-dasharray:4 3}
 .lbl{font-family:var(--sans);font-size:12.5px;fill:#14171e}
 .mono{font-family:var(--mono);font-size:10.5px;fill:#7c7a72}
</style></head><body><div class="wrap">
<h1>路线 A · 固定拓扑（人设计，零训练）</h1>
<p>8 个节点写死。<b>依据包只进核验侧</b>，生成侧只看到题面。
N4 的 prompt 里带「已覆盖清单」⇒ <b>改写的是下一次采样的条件分布</b>（不是 sleep、不是闲聊）。</p>
<p class="meta">由 routes/A/DESIGN.md §3.1 渲染 ｜ 2026-10-21</p>
<div class="fig">__SVG__</div>
<p class="cap">N7 是唯一接触 oracle 的节点；N8 机械装配，不��模型重写</p>
</div></body></html>"""

html = HTML.replace("__SVG__", build())
io.open(os.path.join(OUT_DIR, "routeA-flow.html"), "w", encoding="utf-8").write(html)
print("✓ routeA-flow.html 已生成（%d 字节）" % len(html))
