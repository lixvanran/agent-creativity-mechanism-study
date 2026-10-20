#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把路线 C 的拓扑菜单（6 个模板）画成标准程序流程图。

**为什么单独写**：通用渲染器（build_spec_flowchart.py）画的是 nodes/edges 列表，
而路线 C 的 spec 是「6 个模板，每个模板一条阶段链 + 每个阶段的信息可达性」。
⇒ 这个图要表达的是**六条链的对照**（谁多一个阶段、谁能看到什么），
   通用渲染器表达不了。

读的是路线 C 自己产出的机读版 spec_parsed.json（不是手抄）⇒ 图与规格同源。
"""
import io
import json
import os

SRC = "/workspace/lab/routes/C/spec_parsed.json"
OUT_DIR = "/workspace/lab/visual-page/routes-flowcharts"
os.makedirs(OUT_DIR, exist_ok=True)

STAGE_CN = {
    "GEN": "生成", "EXTRACT": "抽取", "VERIFY": "核验", "SPLIT": "拆分",
    "MERGE": "机械装配", "COLLAPSE": "坍缩检测", "REDISTRIBUTE": "条件重组",
    "STALL": "停滞检测",
}
ACCESS_CN = {
    "prompt_only": "只见题面", "drafts": "+草稿", "evidence+claims": "+依据包+断言",
    "verdicts+claims": "+判官+断言", "claims": "+断言", "drafts+claims": "+草稿+断言",
    "claims+verdicts": "+断言+判官", "draft_only": "仅草稿",
}


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
        s.append(txt(x + w / 2, y + h / 2 - 7, label, "lbl"))
        s.append(txt(x + w / 2, y + h / 2 + 12, sub, "mono"))
    else:
        s.append(txt(x + w / 2, y + h / 2 + 5, label, "lbl"))
    return "".join(s)


def arrow(d, cls="ln"):
    return '<path d="%s" class="%s" marker-end="url(#ah)"/>' % (d, cls)


def build():
    spec = json.load(io.open(SRC, encoding="utf-8"))
    tpl = spec["topology"]["templates"]
    default = spec["topology"].get("default_topology", "T2")
    s = []
    W = 1230
    x0, y0 = 28, 56
    rowh = 112
    bw, bh, gap = 92, 46, 28
    label_w = 300
    maxn = max(len(t["stages"]) for t in tpl.values())
    for i, (tid, t) in enumerate(sorted(tpl.items())):
        y = y0 + i * rowh
        is_def = (tid == default)
        # 左侧：模板名 + 用途
        s.append('<rect x="%d" y="%.1f" width="%d" height="%.1f" rx="3" class="%s"/>' % (
            x0, y, label_w, 76, "stHot" if is_def else "st"))
        nm = t["name"]
        head = nm if len(nm) <= 22 else nm[:21] + "…"
        s.append(txt(x0 + 10, y + 18, "%s · %s" % (tid, head), "lbl", "start", 12))
        s.append(txt(x0 + 10, y + 34, ("★ 默认 ｜ " if is_def else "") +
                     "%s ｜ 帧数 %s" % (t.get("merge_strategy", "-"), t.get("n_frames", "-")),
                     "mono", "start"))
        pur = (t.get("purpose", "") or "").replace("：", ":")
        s.append(txt(x0 + 10, y + 50, "目的：" + (pur[:22] + "…" if len(pur) > 22 else pur),
                     "mono", "start"))
        s.append(txt(x0 + 10, y + 66, "核验:%s" % ("有" if t.get("uses_verify") else "无"),
                     "mono", "start"))
        # 阶段链
        sx = x0 + label_w + 26
        stages = t["stages"]
        for j, st_name in enumerate(stages):
            bx = sx + j * (bw + gap)
            acc = (t.get("info_access") or {}).get(st_name, "")
            kind = "stHot" if (st_name == "VERIFY") else "st"
            s.append(box(bx, y + 8, bw, bh, STAGE_CN.get(st_name, st_name),
                         ACCESS_CN.get(acc, acc or ""), kind))
            if j:
                s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (
                    bx - gap + 3, y + 8 + bh / 2, bx - 3, y + 8 + bh / 2)))

    # 底部：硬约束
    hb = tpl and spec["topology"].get("structural_hard_constraints", [])
    by = y0 + len(tpl) * rowh + 6
    s.append('<rect x="%d" y="%.1f" width="%d" height="%.1f" rx="3" class="st"/>' % (
        x0, by, W - 2 * x0, 26 + len(hb) * 20))
    s.append(txt(x0 + 12, by + 20, "拓扑结构硬约束（结构检查器 H1–H6 · 不读任何 oracle 统计）", "lbl", "start"))
    for k, h in enumerate(hb):
        s.append(txt(x0 + 12, by + 42 + k * 20, "%s  %s" % (h.get("id", ""), h.get("rule", "")), "mono", "start"))
    H = by + 34 + len(hb) * 20
    return ('<svg viewBox="0 0 %d %d" class="figsvg">'
            '<defs><marker id="ah" markerWidth="9" markerHeight="7" refX="8" refY="3.5" '
            'orient="auto"><polygon points="0 0, 9 3.5, 0 7" fill="#3a4256"/></marker></defs>%s</svg>'
            % (W, H, "".join(s)))


HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>路线C · 六个拓扑模板对照</title>
<style>
 :root{--bg:#f7f5f0;--card:#fff;--line:#e9e3d6;--ink:#14171e;--ink2:#3a4256;--ink3:#7c7a72;
 --primary:#2f6f5e;--mono:'JetBrains Mono',monospace;--sans:'Outfit',system-ui,sans-serif;--serif:'DM Serif Display',Georgia,serif}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.65}
 .wrap{max-width:1240px;margin:0 auto;padding:32px 24px 64px}
 h1{font-family:var(--serif);font-weight:400;font-size:30px;margin:0 0 6px}
 p{margin:0 0 10px;color:var(--ink2)}
 .meta{font-size:13px;color:var(--ink3);font-family:var(--mono);margin:0 0 20px}
 .fig{background:#fcfbf8;border:1px solid var(--line);border-radius:12px;padding:12px 8px;overflow-x:auto}
 .figsvg{display:block;min-width:900px;width:100%;height:auto}
 .cap{font-size:12.5px;color:var(--ink3);font-family:var(--mono);text-align:center;margin:10px 0 0}
 .lgd{display:flex;flex-wrap:wrap;gap:14px;font-size:12.5px;color:var(--ink2);font-family:var(--mono);margin:0 0 12px}
 .lgd span{display:inline-flex;align-items:center;gap:6px}
 .sw{width:16px;height:13px;border-radius:2px;display:inline-block;border-width:1.6px;border-style:solid}
 .st{fill:#fff;stroke:#3a4256;stroke-width:1.6}.stHot{fill:#eef4f1;stroke:#2f6f5e;stroke-width:1.6}
 .ln{fill:none;stroke:#3a4256;stroke-width:1.6}
 .lbl{font-family:var(--sans);font-size:12.5px;fill:#14171e}
 .mono{font-family:var(--mono);font-size:10px;fill:#7c7a72}
</style></head><body><div class="wrap">
<h1>路线 C · 六个拓扑模板对照</h1>
<p>「拓扑 = 有哪些阶段、阶段顺序、信息可达性、装配策略」。模板在<b>训练开始前冻结</b>，
成为实验因子。★ 是默认模板 <b>T2</b>（同时给出 Mednick 的「远」与「有用」两侧）。</p>
<p class="meta">由 spec_parsed.json 自动渲染 ｜ 图与规格同源 ｜ 2026-10-21</p>
<div class="lgd">
 <span><i class="sw" style="background:#eef4f1;border-color:#2f6f5e"></i>核验阶段（唯一接触依据包/判官）</span>
 <span><i class="sw" style="background:#fff;border-color:#3a4256"></i>其他阶段</span>
 <span>框内小字 = 该阶段<b>能看到什么</b>（信息可达性）</span>
</div>
<div class="fig">__SVG__</div>
<p class="cap">T0 是零假设下界；T1 只实现「有用」一侧；T2 加多帧以给「远」；T3–T5 逐层加阶段</p>
</div></body></html>"""

html = HTML.replace("__SVG__", build())
io.open(os.path.join(OUT_DIR, "routeC-topologies.html"), "w", encoding="utf-8").write(html)
print("✓ routeC-topologies.html 已生成（%d 字节）" % len(html))
