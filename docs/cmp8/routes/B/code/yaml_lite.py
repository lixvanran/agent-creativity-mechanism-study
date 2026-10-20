# -*- coding: utf-8 -*-
"""极简 YAML 子集解析器（**只用于校验本路线的 spec.yaml**）。

为什么需要它：沙箱里没有 PyYAML（`pip install pyyaml` 无网络、`apt` 无包），
而"spec.yaml 能不能被机器解析"是交付要求之一 ⇒ 自己写一个可复核的解析器，
而不是**声称**文件合法。

支持的 YAML 子集（足够覆盖本仓库的 spec.yaml，且刻意保守）：
  * 2 空格缩进的块映射 / 块序列
  * 行内 flow 映射 `{k: v, ...}` 与 flow 序列 `[a, b, ...]`（**可跨行**，按括号深度合并）
  * 标量：plain / 'single' / "double"（支持 \\ \" \n 转义）
  * `#` 注释（仅当不在引号内时）
  * 空行忽略；`key:` 后无值 ⇒ 取下一层缩进的块；无下一层 ⇒ None

**不支持**（出现即报错，不静默通过）：锚点/别名（&/*）、标签（!）、多文档（---）、
块标量（| 与 >）、合并键（<<）。
"""
from __future__ import annotations

import re


class YamlLiteError(ValueError):
    pass


def _strip_comment(s: str) -> str:
    out, q = [], None
    for i, ch in enumerate(s):
        if q:
            out.append(ch)
            if ch == "\\" and q == '"' and i + 1 < len(s):
                out.append(s[i + 1])
                continue
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
            out.append(ch)
            continue
        if ch == "#" and (not out or out[-1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _depth(s: str) -> int:
    d, q = 0, None
    i = 0
    while i < len(s):
        ch = s[i]
        if q:
            if ch == "\\" and q == '"':
                i += 2
                continue
            if ch == q:
                q = None
            i += 1
            continue
        if ch in "\"'":
            q = ch
        elif ch in "[{":
            d += 1
        elif ch in "]}":
            d -= 1
        i += 1
    return d


def _logical_lines(text: str):
    """把跨行的 flow 集合合并成"逻辑行"：(indent, content, lineno)"""
    out = []
    raw = text.split("\n")
    i = 0
    while i < len(raw):
        line = raw[i]
        no = i + 1
        i += 1
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if "\t" in line[:indent]:
            raise YamlLiteError("第 %d 行含 TAB 缩进" % no)
        content = _strip_comment(line.strip())
        if not content:
            continue
        if content.startswith("---") or content.startswith("..."):
            raise YamlLiteError("第 %d 行：多文档标记不支持" % no)
        if content.startswith(("&", "*", "!")) or content.startswith("<<:"):
            raise YamlLiteError("第 %d 行：锚点/别名/标签/合并键不支持" % no)
        if re.match(r"^[|>][-+]?\d*$", content):
            raise YamlLiteError("第 %d 行：块标量不支持" % no)
        while _depth(content) > 0:
            if i >= len(raw):
                raise YamlLiteError("第 %d 行：flow 集合未闭合" % no)
            nxt = _strip_comment(raw[i].strip())
            i += 1
            content = content + " " + nxt
        if _depth(content) != 0:
            raise YamlLiteError("第 %d 行：flow 集合括号不配平" % no)
        out.append((indent, content, no))
    return out


def _split_top(s: str, sep: str = ":"):
    """在**顶层**（不在引号/括号内）找第一个 sep，返回 (左, 右) 或 None。"""
    d, q, i = 0, None, 0
    while i < len(s):
        ch = s[i]
        if q:
            if ch == "\\" and q == '"':
                i += 2
                continue
            if ch == q:
                q = None
            i += 1
            continue
        if ch in "\"'":
            q = ch
            i += 1
            continue
        if ch in "[{":
            d += 1
        elif ch in "]}":
            d -= 1
        elif ch == sep and d == 0:
            if sep == ":" and i + 1 < len(s) and s[i + 1] in " \t":
                return s[:i].strip(), s[i + 1:].strip()
            if sep == ":" and i + 1 == len(s):
                return s[:i].strip(), ""
            if sep != ":":
                return s[:i].strip(), s[i + 1:].strip()
        i += 1
    return None


def _scalar(s: str):
    s = s.strip()
    if s == "":
        return None
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        return s[1:-1].replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        return s[1:-1].replace("''", "'")
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s in ("null", "~", "Null"):
        return None
    if re.match(r"^-?\d+$", s):
        return int(s)
    if re.match(r"^-?\d*\.\d+$", s):
        return float(s)
    return s


def _flow(s: str):
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        body = s[1:-1].strip()
        out = {}
        if not body:
            return out
        for part in _split_flow_items(body):
            kv = _split_top(part, ":")
            if kv is None:
                raise YamlLiteError("flow 映射项缺少 ':'：%s" % part)
            k, v = kv
            out[_scalar(k)] = _value(v)
        return out
    if s.startswith("[") and s.endswith("]"):
        body = s[1:-1].strip()
        if not body:
            return []
        return [_value(p) for p in _split_flow_items(body)]
    return _scalar(s)


def _split_flow_items(body: str):
    items, buf, d, q = [], [], 0, None
    for ch in body:
        if q:
            buf.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
            buf.append(ch)
            continue
        if ch in "[{":
            d += 1
        elif ch in "]}":
            d -= 1
        if ch == "," and d == 0:
            items.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if q:
        raise YamlLiteError("flow 集合里引号未闭合")
    if buf:
        items.append("".join(buf).strip())
    return [x for x in items if x != ""]


def _value(s: str):
    s = s.strip()
    if s.startswith(("{", "[")):
        return _flow(s)
    return _scalar(s)


def _parse_block(lines, i, indent):
    """解析缩进 >= indent 的块，返回 (value, next_index)。"""
    if i >= len(lines):
        return None, i
    if lines[i][1].startswith("- "):
        return _parse_seq(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i, indent):
    out = {}
    while i < len(lines):
        ind, content, no = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise YamlLiteError("第 %d 行：缩进不一致（%d > %d）" % (no, ind, indent))
        if content.startswith("- "):
            break
        kv = _split_top(content, ":")
        if kv is None:
            raise YamlLiteError("第 %d 行：不是合法的映射项：%s" % (no, content))
        k, v = kv
        key = _scalar(k)
        if key in out:
            raise YamlLiteError("第 %d 行：重复键 %r" % (no, key))
        i += 1
        if v == "":
            if i < len(lines) and lines[i][0] > indent:
                val, i = _parse_block(lines, i, lines[i][0])
            else:
                val = None
        else:
            val = _value(v)
        out[key] = val
    return out, i


def _parse_seq(lines, i, indent):
    out = []
    while i < len(lines):
        ind, content, no = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise YamlLiteError("第 %d 行：序列项缩进不一致" % no)
        if not content.startswith("- "):
            break
        item = content[2:].strip()
        i += 1
        if item == "":
            if i < len(lines) and lines[i][0] > indent:
                val, i = _parse_block(lines, i, lines[i][0])
            else:
                val = None
            out.append(val)
            continue
        kv = _split_top(item, ":")
        if kv is not None and not item.startswith(("{", "[")):
            # 行内映射起始：键在 item 里，后续同缩进(indent+2)的行属于同一个映射
            k, v = kv
            d = {}
            if v == "":
                if i < len(lines) and lines[i][0] > indent + 2:
                    val, i = _parse_block(lines, i, lines[i][0])
                else:
                    val = None
            else:
                val = _value(v)
            d[_scalar(k)] = val
            if i < len(lines) and lines[i][0] == indent + 2 and not lines[i][1].startswith("- "):
                more, i = _parse_map(lines, i, indent + 2)
                d.update(more)
            out.append(d)
        else:
            out.append(_value(item))
    return out, i


def loads(text: str):
    lines = _logical_lines(text)
    if not lines:
        return None
    val, i = _parse_block(lines, 0, lines[0][0])
    if i != len(lines):
        raise YamlLiteError("第 %d 行：解析未消费完（缩进结构异常）" % lines[i][2])
    return val


def load(path: str):
    with open(path, encoding="utf-8") as f:
        return loads(f.read())


if __name__ == "__main__":
    import json
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "/workspace/lab/routes/B/spec.yaml"
    try:
        d = load(p)
    except Exception as e:
        print("YAML PARSE ERROR: %s" % e)
        sys.exit(2)
    print("YAML OK · 顶层键 %d 个：%s" % (len(d), ", ".join(list(d)[:12])))
    print(json.dumps(d, ensure_ascii=False, indent=1)[:1500])
