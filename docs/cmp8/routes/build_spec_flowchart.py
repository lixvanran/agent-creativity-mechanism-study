#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把路线的 spec.yaml 渲染成标准程序流程图（SVG→HTML）。

**为什么要自动渲染**：三条路线各自的拓扑不同，手画三张图既慢又容易出错
（上一轮就出现过文字溢出框、虚线穿框、框被裁掉）。
⇒ 路线只负责交出**机器可读规格**，图由脚本按规格生成 ⇒ 图和规格**不可能不一致**。

用法：
  python3 build_spec_flowchart.py <spec.yaml> <输出目录> <标题> <副标题>
"""
import io
import os
import sys

OUT_DIR = "/workspace/lab/visual-page/spec-flowcharts"


# ────────────────────────── YAML（极简，够用即可） ──────────────────────────
def load_yaml(path):
    """极简 YAML 读取：支持嵌套 dict / list / 标量，够读 spec 用。"""
    try:
        import yaml  # type: ignore
        with io.open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        pass
    return _mini_yaml(io.open(path, encoding="utf-8").read().split("\n"))


def _scalar(tok):
    tok = tok.strip()
    if tok in ("true", "True"):
        return True
    if tok in ("false", "False"):
        return False
    if tok in ("null", "~", ""):
        return None
    if tok.startswith("[") and tok.endswith("]"):
        inner = tok[1:-1].strip()
        if not inner:
            return []
        return [_scalar(x) for x in inner.split(",")]
    if tok.startswith("{") and tok.endswith("}"):
        inner = tok[1:-1].strip()
        d = {}
        if inner:
            for part in inner.split(","):
                if ":" in part:
                    k, v = part.split(":", 1)
                    d[k.strip()] = _scalar(v)
        return d
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
        return tok[1:-1]
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return tok


def _mini_yaml(lines):
    root = {}
    stack = [(-1, root)]
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            stack = [(-1, root)]
        parent = stack[-1][1]
        if line.startswith("- "):
            item = line[2:].strip()
            if not isinstance(parent, list):
                continue
            if ":" in item and not item.startswith("["):
                k, v = item.split(":", 1)
                obj = {}
                obj[k.strip()] = _scalar(v)
                parent.append(obj)
                stack.append((indent, obj))
            else:
                parent.append(_scalar(item))
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v == "":
                nxt = lines[i] if i < len(lines) else ""
                child = []
                if nxt.strip().startswith("- "):
                    parent[k] = child
                    stack.append((indent, child))
                else:
                    d = {}
                    parent[k] = d
                    stack.append((indent, d))
            else:
                parent[k] = _scalar(v)
    return root


# ────────────────────────── SVG 记号（同主流程图那套） ──────────────────────────
def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, cls="lbl", anchor="middle", size=None):
    st = ' style="font-size:%dpx"' % size if size else ""
    return ('<text x="%.1f" y="%.1f" text-anchor="%s" class="%s"%s>%s</text>'
            % (x, y, anchor, cls, st, esc(s)))


def box(x, y, w, h, label, sub=None, kind="st"):
    s = ['<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%s" class="%s"/>' % (
        x, y, w, h, "18" if kind == "term" else "2", kind)]
    if sub:
        s.append(txt(x + w / 2, y + h / 2 - 8, label, "lbl"))
        s.append(txt(x + w / 2, y + h / 2 + 12, sub, "mono"))
    else:
        s.append(txt(x + w / 2, y + h / 2 + 5, label, "lbl"))
    return "".join(s)


def diamond(cx, cy, w, h, label, sub=None):
    p = "%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" % (
        cx, cy - h / 2, cx + w / 2, cy, cx, cy + h / 2, cx - w / 2, cy)
    s = ['<polygon points="%s" class="dec"/>' % p]
    if sub:
        s.append(txt(cx, cy - 8, label, "lbl"))
        s.append(txt(cx, cy + 12, sub, "mono"))
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
        s.append(txt(cx, cy - 8, label, "lbl"))
        s.append(txt(cx, cy + 12, sub, "mono"))
    else:
        s.append(txt(cx, cy + 5, label, "lbl"))
    return "".join(s)


def arrow(d, cls="ln"):
    return '<path d="%s" class="%s" marker-end="url(#ah)"/>' % (d, cls)


def label(x, y, s, cls="mono", anchor="middle"):
    return ('<text x="%.1f" y="%.1f" text-anchor="%s" class="%s">%s</text>'
            % (x, y, anchor, cls, esc(s)))


# ────────────────────────── spec → 流程图 ──────────────────────────
def pick(spec, *keys, default=None):
    for k in keys:
        if isinstance(spec, dict) and k in spec and spec[k] is not None:
            return spec[k]
    return default


def normalize(spec):
    """把不同写法的 spec 归一成 {nodes:[{id,label,sub,kind}], edges:[(from,to,label)]}。"""
    nodes = pick(spec, "nodes", "steps", "stages", "phases", default=[]) or []
    edges = pick(spec, "edges", "transitions", "links", default=[]) or []
    out_nodes, out_edges, order = [], [], []
    for i, n in enumerate(nodes):
        if isinstance(n, str):
            nid, lab, sub, kind = "n%d" % i, n, None, "st"
        elif isinstance(n, dict):
            nid = str(pick(n, "id", "name", "key", default="n%d" % i))
            lab = str(pick(n, "label", "title", "name", "action", "op", default=nid))
            sub = pick(n, "sub", "subtitle", "desc", "description", "note")
            sub = str(sub) if sub else None
            kind = str(pick(n, "kind", "type", "shape", default="st"))
        else:
            nid, lab, sub, kind = "n%d" % i, str(n), None, "st"
        if kind in ("decision", "dec", "cond", "condition", "if", "gate"):
            kind = "dec"
        elif kind in ("io", "input", "output", "start", "end", "term", "terminal"):
            kind = "io" if kind in ("io", "input", "output") else "term"
        else:
            kind = "st"
        out_nodes.append({"id": nid, "label": lab, "sub": sub, "kind": kind})
        order.append(nid)
    for e in edges:
        if isinstance(e, (list, tuple)) and len(e) >= 2:
            out_edges.append((str(e[0]), str(e[1]), str(e[2]) if len(e) > 2 else None))
        elif isinstance(e, dict):
            a = pick(e, "from", "src", "source", "a")
            b = pick(e, "to", "dst", "target", "dest", "b")
            if a is not None and b is not None:
                out_edges.append((str(a), str(b), pick(e, "label", "cond", "condition", "text")))
    # 没给 edges ⇒ 按 nodes 顺序串成一条链
    if not out_edges and len(order) > 1:
        for a, b in zip(order, order[1:]):
            out_edges.append((a, b, None))
    return out_nodes, out_edges


def render(spec, title, subtitle):
    nodes, edges = normalize(spec)
    if not nodes:
        return "<p>（spec 里没有可渲染的节点）</p>"
    W = 760
    # 布局：按"最浅层"分行（简化：拓扑序分层）
    level = {n["id"]: 0 for n in nodes}
    for _ in range(len(nodes) + 1):
        changed = False
        for a, b, _l in edges:
            if level.get(b, 0) < level.get(a, 0) + 1:
                level[b] = level[a] + 1
                changed = True
        if not changed:
            break
    rows = {}
    for n in nodes:
        rows.setdefault(level[n["id"]], []).append(n)
    # 同一层里若有连线，横向排
    s = []
    y = 16
    pos = {}
    for lv in sorted(rows):
        group = rows[lv]
        # 找出该层内部的连线，把有连线的排成一行
        bw, bh, gap = 190, 54, 26
        roww = len(group) * bw + (len(group) - 1) * gap
        x = max(20, (W - roww) / 2)
        for n in group:
            pos[n["id"]] = (x, y, bw, bh)
            x += bw + gap
        y += bh + 34
    for n in nodes:
        x, yy, bw, bh = pos[n["id"]]
        if n["kind"] == "dec":
            s.append(diamond(x + bw / 2, yy + bh / 2, bw + 40, bh + 26, n["label"], n["sub"]))
        elif n["kind"] == "io":
            s.append(para(x + bw / 2, yy + bh / 2, bw, bh, n["label"], n["sub"]))
        elif n["kind"] == "term":
            s.append(box(x + bw / 2 - 80, yy + 6, 160, 38, n["label"], n["sub"], "term"))
        else:
            s.append(box(x, yy, bw, bh, n["label"], n["sub"], "st"))
    for a, b, lb in edges:
        if a not in pos or b not in pos:
            continue
        ax, ay, aw, ah = pos[a]
        bx, by, bw, bh = pos[b]
        acx, acy = ax + aw / 2, ay + ah
        bcx, bcy = bx + bw / 2, by
        if abs(acy - bcy) < 1:
            s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (acx, acy + 4, bcx, bcy - 4)))
        else:
            s.append(arrow("M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f"
                           % (acx, acy, acx, (acy + bcy) / 2, bcx, (acy + bcy) / 2)))
            s.append(arrow("M%.1f,%.1f L%.1f,%.1f" % (bcx, (acy + bcy) / 2, bcx, bcy - 2), "ln"))
        if lb:
            s.append(label((acx + bcx) / 2, (acy + bcy) / 2 - 6, lb, "mono", "start"))
    svg = ('<svg viewBox="0 0 %d %d" class="figsvg">'
           '<defs><marker id="ah" markerWidth="9" markerHeight="7" refX="8" refY="3.5" '
           'orient="auto"><polygon points="0 0, 9 3.5, 0 7" fill="#3a4256"/></marker></defs>%s</svg>'
           % (W, y + 10, "".join(s)))
    return svg


HTML_TMPL = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
 :root{--bg:#f7f5f0;--card:#fff;--line:#e9e3d6;--ink:#14171e;--ink2:#3a4256;--ink3:#7c7a72;
 --primary:#2f6f5e;--accent:#c97b3f;--warn:#b06367;--gold:#b08430;
 --mono:'JetBrains Mono',monospace;--sans:'Outfit',system-ui,sans-serif;--serif:'DM Serif Display',Georgia,serif}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.65}
 .wrap{max-width:1100px;margin:0 auto;padding:32px 24px 64px}
 h1{font-family:var(--serif);font-weight:400;font-size:30px;margin:0 0 6px}
 p{margin:0 0 10px;color:var(--ink2)}
 .meta{font-size:13px;color:var(--ink3);font-family:var(--mono);margin:0 0 20px}
 .fig{background:#fcfbf8;border:1px solid var(--line);border-radius:12px;padding:12px 8px;overflow-x:auto}
 .figsvg{display:block;min-width:620px;width:100%;height:auto}
 .cap{font-size:12.5px;color:var(--ink3);font-family:var(--mono);text-align:center;margin:10px 0 0}
 .st{fill:#fff;stroke:#3a4256;stroke-width:1.6}.term{fill:#eef4f1;stroke:#2f6f5e;stroke-width:1.8}
 .io{fill:#fdf4ec;stroke:#c97b3f;stroke-width:1.6}.dec{fill:#faf4e6;stroke:#b08430;stroke-width:1.6}
 .ln{fill:none;stroke:#3a4256;stroke-width:1.6}
 .lbl{font-family:var(--sans);font-size:13px;fill:#14171e}
 .mono{font-family:var(--mono);font-size:10.5px;fill:#7c7a72}
</style></head><body><div class="wrap">
<h1>__TITLE__</h1><p>__SUB__</p><p class="meta">由 spec.yaml 自动渲染 ｜ 2026-10-21</p>
<div class="fig">__SVG__</div>
<p class="cap">图与规格同源：改规格即改图，不会出现图与设计不一致</p>
</div></body></html>"""


def main():
    spec_path, out_dir = sys.argv[1], sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else "路线流程图"
    sub = sys.argv[4] if len(sys.argv) > 4 else "思维面 = 有效信息维度数"
    os.makedirs(out_dir, exist_ok=True)
    spec = load_yaml(spec_path)
    svg = render(spec, title, sub)
    html = (HTML_TMPL.replace("__TITLE__", title).replace("__SUB__", sub)
            .replace("__SVG__", svg))
    p = os.path.join(out_dir, "index.html")
    io.open(p, "w", encoding="utf-8").write(html)
    print("✓ %s 已生成（%d 字节）" % (p, len(html)))


if __name__ == "__main__":
    main()
