#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ `spec.yaml` 的**可渲染性自检**（双解析 + 变异注入）。

要证明的事（2026-10-21 独立复核的判死项：路线 B 的 spec 渲染出来是**空页**）：

  ❶ **双解析**：本 spec 同时能被两条解析器读懂 ——
     ① 实验室的渲染器 `/workspace/lab/build_spec_flowchart.py`（自带极简 YAML），
     ② 本路线自带的 `code/yaml_lite.py`（沙箱无 PyYAML 且装不上）。
     两边对 `nodes` / `edges` 的读数必须**一致**（id 集合、边数、kind 集合）。
  ❷ **渲染非空**：渲染产物 `index.html` 必须满足
     `rects ≥ 5` 且 `paths ≥ 4`，且**不含**渲染器的"没有可渲染的节点"告警页。
  ❸ **变异注入（必须有）**：把 `nodes:` / `edges:` 从 spec 里拿掉 ⇒
     本自检**必须 FAIL**。⇒ 报不出 FAIL ⇒ 这个自检是摆设。

用法：python3 test_spec_flowchart.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SPEC = os.path.join(os.path.dirname(HERE), "spec.yaml")
RENDERER = os.environ.get("SPEC_FLOWCHART", "/workspace/lab/build_spec_flowchart.py")

import yaml_lite  # noqa: E402

KINDS = ("process", "decision", "io", "terminal")
MIN_RECTS = 5
MIN_PATHS = 4


# ───────────────────────────────────────── 渲染器（按 importlib 加载，避免污染 sys.path）
def _load_renderer():
    spec = importlib.util.spec_from_file_location("_bld_spec_flowchart", RENDERER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def strip_block(text: str, key: str) -> str:
    """**文本级**删掉一个顶层块（`key:` 起到下一个顶层键为止）⇒ 用于变异注入。"""
    lines = text.split("\n")
    out, i, removed = [], 0, False
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^%s\s*:" % re.escape(key), ln):
            removed = True
            i += 1
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                i += 1
            continue
        out.append(ln)
        i += 1
    if not removed:
        raise AssertionError("spec.yaml 里找不到顶层块：%s" % key)
    return "\n".join(out)


def render(spec_path: str, out_dir: str):
    """跑真正的渲染器 CLI（与交付命令完全一致），返回 (html, 统计)。"""
    r = subprocess.run([sys.executable, RENDERER, spec_path, out_dir, "路线B", "自检"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError("渲染器退出码 %d：%s" % (r.returncode, r.stderr[-400:]))
    html = open(os.path.join(out_dir, "index.html"), encoding="utf-8").read()
    stat = dict(
        bytes=len(html),
        rects=len(re.findall(r"<rect", html)),
        paths=len(re.findall(r"<path", html)),
        texts=len(re.findall(r"<text", html)),
        polygons=len(re.findall(r"<polygon", html)),
        empty_page_warning=("没有可渲染的节点" in html),
    )
    return html, stat


def check_spec(spec_path: str):
    """对一份 spec 做全部检查；返回 dict（**不抛异常**，由调用方判定 PASS/FAIL）。"""
    out = {"spec": spec_path, "checks": {}, "errors": []}

    # ── ❶ 双解析 ──
    try:
        d = yaml_lite.load(spec_path)
        out["yaml_lite_ok"] = True
    except Exception as e:                                   # pragma: no cover
        out["yaml_lite_ok"] = False
        out["errors"].append("yaml_lite 解析失败：%s" % e)
        return out

    nodes = d.get("nodes")
    edges = d.get("edges")
    out["top_level_keys"] = len(d)
    out["n_nodes"] = len(nodes) if isinstance(nodes, list) else 0
    out["n_edges"] = len(edges) if isinstance(edges, list) else 0

    ids, kinds = [], []
    if not isinstance(nodes, list) or not nodes:
        out["errors"].append("顶层 nodes 缺失或为空")
    else:
        for n in nodes:
            if not isinstance(n, dict) or "id" not in n or "label" not in n:
                out["errors"].append("节点缺 id/label：%r" % (n,))
                continue
            ids.append(str(n["id"]))
            kinds.append(str(n.get("kind", "st")))
    if not isinstance(edges, list) or not edges:
        out["errors"].append("顶层 edges 缺失或为空")
    else:
        for e in edges:
            if not isinstance(e, dict) or "from" not in e or "to" not in e:
                out["errors"].append("边缺 from/to：%r" % (e,))
    if len(set(ids)) != len(ids):
        out["errors"].append("节点 id 重复")
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        out["errors"].append("非法 kind：%s" % sorted(set(bad)))
    dangling = []
    for e in (edges if isinstance(edges, list) else []):
        if isinstance(e, dict) and (str(e.get("from")) not in ids or str(e.get("to")) not in ids):
            dangling.append(e)
    if dangling:
        out["errors"].append("悬空边（端点不在 nodes 里）：%d 条，例如 %r"
                             % (len(dangling), dangling[:2]))

    # ── ❷ 渲染（用实验室渲染器自己的解析器）──
    try:
        mod = _load_renderer()
        rspec = mod.load_yaml(spec_path)
        rnodes = mod.normalize(rspec)[0]
        out["renderer_n_nodes"] = len(rnodes)
        out["renderer_n_edges"] = len(mod.normalize(rspec)[1])
        out["renderer_node_ids"] = sorted(str(n["id"]) for n in rnodes)
        out["two_parsers_agree_ids"] = (out["renderer_node_ids"] == sorted(ids))
        if not out["two_parsers_agree_ids"]:
            out["errors"].append("两个解析器读到的节点 id 集合不一致")
        with tempfile.TemporaryDirectory() as td:
            _html, stat = render(spec_path, td)
        out["render"] = stat
        if stat["empty_page_warning"]:
            out["errors"].append("渲染出的是空页告警")
        if stat["rects"] < MIN_RECTS:
            out["errors"].append("rects=%d < %d（图太空）" % (stat["rects"], MIN_RECTS))
        if stat["paths"] < MIN_PATHS:
            out["errors"].append("paths=%d < %d（图太空）" % (stat["paths"], MIN_PATHS))
    except Exception as e:
        out["errors"].append("渲染失败：%s" % e)

    out["PASS"] = not out["errors"]
    return out


def main():
    report = {"real": check_spec(SPEC)}

    # ── ❸ 变异注入：拿掉 nodes/edges ⇒ **必须 FAIL** ──
    text = open(SPEC, encoding="utf-8").read()
    mutations = {}
    with tempfile.TemporaryDirectory() as td:
        m1 = os.path.join(td, "mut_no_nodes_edges.yaml")
        open(m1, "w", encoding="utf-8").write(strip_block(strip_block(text, "nodes"), "edges"))
        mutations["remove_nodes_and_edges"] = check_spec(m1)

        m2 = os.path.join(td, "mut_no_nodes.yaml")
        open(m2, "w", encoding="utf-8").write(strip_block(text, "nodes"))
        mutations["remove_nodes_only"] = check_spec(m2)

    report["mutations"] = {k: {"PASS": v["PASS"], "errors": v["errors"][:3],
                               "n_nodes": v.get("n_nodes"), "n_edges": v.get("n_edges"),
                               "render": v.get("render")} for k, v in mutations.items()}
    mut_ok = all((not v["PASS"]) for v in mutations.values())
    report["mutations_all_fail_as_expected"] = mut_ok
    report["PASS"] = bool(report["real"]["PASS"] and mut_ok)

    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
