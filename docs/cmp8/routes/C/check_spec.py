# -*- coding: utf-8 -*-
"""路线 C · spec.yaml 的**机器可读性**与**一致性**检查。

沙箱内没有 PyYAML（无 PyPI 访问）⇒ 本文件内置一个 YAML 子集解析器
（块映射 / 块序列 / 流映射 / 流序列 / 折叠块 `>-` / 标量 / 注释），
用来证明 spec.yaml 真的能被机器读，并把它与代码（params.py / topology.py）逐项对账。

对账项：
  1. 拓扑模板集合、默认拓扑、阶段序列、装配策略、生成路数、核验开关、信息可达性
  2. 结构硬约束编号集合
  3. 冻结认知位置清单
  4. 参数表（id / name / type / 取值域 / 默认 / 生效拓扑 / 描述）
  5. 默认参数向量的哈希
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as P
import topology as T

SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec.yaml")


# ------------------------------------------------------------------ 迷你 YAML
def _scalar(tok: str):
    t = tok.strip()
    if t == "":
        return None
    if t.startswith('"') and t.endswith('"') and len(t) >= 2:
        return t[1:-1]
    if t.startswith("'") and t.endswith("'") and len(t) >= 2:
        return t[1:-1]
    low = t.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    if re.fullmatch(r"-?\d+\.\d+", t):
        return float(t)
    return t


def _split_flow(s: str) -> list:
    """按顶层逗号切分流映射/流序列的内容。"""
    out, depth, cur, q = [], 0, "", None
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
            cur += ch
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _flow(tok: str):
    t = tok.strip()
    if t.startswith("{") and t.endswith("}"):
        d = {}
        for part in _split_flow(t[1:-1]):
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            d[k.strip()] = _flow(v)
        return d
    if t.startswith("[") and t.endswith("]"):
        return [_flow(p) for p in _split_flow(t[1:-1])]
    return _scalar(t)


def _strip_comment(line: str) -> str:
    out, q = "", None
    for i, ch in enumerate(line):
        if q:
            out += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
            out += ch
            continue
        if ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out += ch
    return out.rstrip()


def parse_yaml(text: str):
    # 预处理：把跨行的流集合（[...]/{...}）合并成一行
    raw_lines = text.splitlines()
    merged, buf, depth, q = [], "", 0, None
    for raw in raw_lines:
        if "\t" in raw[:len(raw) - len(raw.lstrip())]:
            raise ValueError("YAML 不允许用 tab 缩进：%r" % raw)
        s = _strip_comment(raw)
        if not s.strip():
            continue
        if buf:
            buf += " " + s.strip()
        else:
            buf = s
        for ch in s:
            if q:
                if ch == q:
                    q = None
                continue
            if ch in "\"'":
                q = ch
            elif ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
        if depth <= 0:
            merged.append(buf)
            buf, depth, q = "", 0, None
    if buf:
        merged.append(buf)
    lines = []
    for s in merged:
        lines.append((len(s) - len(s.lstrip()), s.strip(), s))
    pos = [0]

    def parse_block(indent: int):
        """解析缩进 >= indent 的块，返回 dict 或 list。"""
        # 先判断这一层是 list 还是 map
        i = pos[0]
        if i >= len(lines):
            return {}
        if lines[i][1].startswith("- "):
            return parse_list(indent)
        return parse_map(indent)

    def parse_map(indent: int):
        d = {}
        while pos[0] < len(lines):
            ind, content, raw = lines[pos[0]]
            if ind < indent:
                break
            if ind > indent:
                raise ValueError("缩进异常于 %r" % raw)
            if content.startswith("- "):
                break
            if ":" not in content:
                raise ValueError("不是 key: value 行：%r" % raw)
            key, rest = content.split(":", 1)
            key = key.strip()
            rest = rest.strip()
            pos[0] += 1
            if rest in (">-", ">", "|", "|-"):
                # 折叠/字面块
                buf = []
                while pos[0] < len(lines) and lines[pos[0]][0] > indent:
                    buf.append(lines[pos[0]][2].strip())
                    pos[0] += 1
                d[key] = " ".join(buf) if rest.startswith(">") else "\n".join(buf)
            elif rest == "":
                # 子块
                if pos[0] < len(lines) and lines[pos[0]][0] > indent:
                    d[key] = parse_block(lines[pos[0]][0])
                else:
                    d[key] = None
            else:
                d[key] = _flow(rest)
        return d

    def parse_list(indent: int):
        arr = []
        while pos[0] < len(lines):
            ind, content, raw = lines[pos[0]]
            if ind < indent or not content.startswith("- "):
                break
            item = content[2:].strip()
            pos[0] += 1
            if item == "":
                if pos[0] < len(lines) and lines[pos[0]][0] > indent:
                    arr.append(parse_block(lines[pos[0]][0]))
                else:
                    arr.append(None)
            elif ":" in item and not item.startswith(("{", "[")):
                # "- key: value" 形式 ⇒ 该项是一个 map，续行同缩进
                sub = {}
                k, v = item.split(":", 1)
                k = k.strip()
                v = v.strip()
                if v in (">-", ">", "|", "|-"):
                    buf = []
                    while pos[0] < len(lines) and lines[pos[0]][0] > indent:
                        buf.append(lines[pos[0]][2].strip())
                        pos[0] += 1
                    sub[k] = " ".join(buf)
                elif v == "":
                    sub[k] = None
                else:
                    sub[k] = _flow(v)
                while pos[0] < len(lines) and lines[pos[0]][0] == indent and \
                        not lines[pos[0]][1].startswith("- "):
                    ind2, c2, _r2 = lines[pos[0]]
                    k2, v2 = c2.split(":", 1)
                    k2, v2 = k2.strip(), v2.strip()
                    pos[0] += 1
                    if v2 == "":
                        if pos[0] < len(lines) and lines[pos[0]][0] > ind2:
                            sub[k2] = parse_block(lines[pos[0]][0])
                        else:
                            sub[k2] = None
                    else:
                        sub[k2] = _flow(v2)
                arr.append(sub)
            else:
                arr.append(_flow(item))
        return arr

    return parse_block(0)


# ------------------------------------------------------------------ 对账
def main():
    spec = parse_yaml(open(SPEC, encoding="utf-8").read())
    json.dump(spec, open(os.path.join(os.path.dirname(SPEC), "spec_parsed.json"), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=1)
    print("spec.yaml 解析成功（顶层键 %d 个）" % len(spec))
    errs = []

    st = spec["topology"]["templates"]
    if sorted(st.keys()) != sorted(T.TEMPLATE_IDS):
        errs.append("模板集合不一致：spec=%s code=%s" % (sorted(st), T.TEMPLATE_IDS))
    if spec["topology"]["default_topology"] != T.DEFAULT_TOPOLOGY:
        errs.append("默认拓扑不一致")
    for tid in T.TEMPLATE_IDS:
        c, s = T.TEMPLATES[tid], st.get(tid, {})
        if s.get("stages") != c["stages"]:
            errs.append("%s 阶段序列不一致" % tid)
        if s.get("merge_strategy") != c["merge_strategy"]:
            errs.append("%s 装配策略不一致" % tid)
        if s.get("uses_verify") != c["uses_verify"]:
            errs.append("%s 核验开关不一致" % tid)
        nf = "fixed_1" if c["n_frames_fixed"] else "parameter_P1"
        if s.get("n_frames") != nf:
            errs.append("%s 生成路数标注不一致" % tid)
        if s.get("info_access") != c["info_access"]:
            errs.append("%s 信息可达性不一致" % tid)
    ids = [h["id"] for h in spec["topology"]["structural_hard_constraints"]]
    if ids != [c for c, _ in T.HARD_CONSTRAINTS]:
        errs.append("结构硬约束编号不一致")
    if spec["frozen_assets"]["frames"] != P.FROZEN_ASSETS["frames"]:
        errs.append("冻结认知位置清单不一致")
    if spec["frozen_assets"]["answer_cap_chars"] != P.FROZEN_ASSETS["answer_cap_chars"]:
        errs.append("答案字数上限不一致")

    sp = {p["id"]: p for p in spec["parameters"]["table"]}
    if sorted(sp) != sorted(P.PARAM_BY_ID):
        errs.append("参数 id 集合不一致")
    for pid, cp in P.PARAM_BY_ID.items():
        s = sp.get(pid, {})
        if s.get("name") != cp["name"] or s.get("type") != cp["type"]:
            errs.append("%s name/type 不一致" % pid)
        if cp["type"] == "int":
            if s.get("values") != cp["values"]:
                errs.append("%s 取值域不一致" % pid)
        else:
            if s.get("lo") != cp["lo"] or s.get("hi") != cp["hi"]:
                errs.append("%s 取值域不一致" % pid)
        if s.get("default") != cp["default"]:
            errs.append("%s 默认值不一致" % pid)
        if s.get("applies_to") != cp["applies_to"]:
            errs.append("%s 生效拓扑不一致" % pid)
    if spec["parameters"]["default_hash"] != P.theta_hash(P.default_theta()):
        errs.append("默认参数向量哈希不一致")

    print("对账：%s" % ("全部一致" if not errs else "不一致 %d 项" % len(errs)))
    for e in errs:
        print("  !", e)
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
