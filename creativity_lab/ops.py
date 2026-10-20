"""可学习架构：操作集 + 图执行器。

前代：架构由**人**设计，训练只是在菜单里挑。
本代：架构是**策略**（在图上选哪条边），权重由训练产生。

状态 = 图。节点：CLAIM（一条可核验断言）/ ANSWER（一份完整答案）。
边 = 操作。**唯一接触 oracle 的操作是 VERIFY**——也是唯一被实测证明有效的动作。
操作集分两类：改变输出形态（GEN/EXTRACT/SPLIT/MERGE）vs 改变可访问信息（VERIFY）。
"""
from __future__ import annotations
from dataclasses import dataclass, field

OPS = ("GEN_PLAIN", "GEN_ANGLE", "EXTRACT", "SPLIT", "VERIFY", "MERGE", "STOP")


@dataclass
class Node:
    nid: int
    kind: str
    text: str
    parent: int | None = None
    op: str | None = None
    verdict: str | None = None    # 支持 | 矛盾 | 未提及 | 非主张
    meta: dict = field(default_factory=dict)


@dataclass
class Graph:
    nodes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)
    _nid: int = 0

    def add(self, kind, text, parent=None, op=None, **meta) -> int:
        self._nid += 1
        self.nodes[self._nid] = Node(self._nid, kind, text, parent, op, meta=dict(meta))
        if parent is not None:
            self.edges.append((parent, self._nid, op))
        return self._nid

    def children(self, nid, op=None):
        return [t for (f, t, o) in self.edges if f == nid and (op is None or o == op)]

    def of_kind(self, kind):
        return [n for n in self.nodes.values() if n.kind == kind]

    def verdict_counts(self):
        c = {"支持": 0, "矛盾": 0, "未提及": 0, "非主张": 0}
        for n in self.of_kind("CLAIM"):
            if n.verdict:
                c[n.verdict] = c.get(n.verdict, 0) + 1
        return c


def op_features(g: Graph, op: str, target: Node | None, depth: int) -> list:
    """**局部**特征：只看当前节点与本分支历史，不看题目/题集。
    这是绕开「在题集上挑赢家」过拟合的关键——特征与题无关，n = 决策次数。"""
    f = [0.0] * 14
    f[OPS.index(op)] = 1.0
    if target is not None:
        f[7] = 1.0 if target.kind == "CLAIM" else 0.0
        f[8] = 1.0 if target.verdict == "支持" else 0.0
        f[9] = 1.0 if target.verdict == "矛盾" else 0.0
        f[10] = 1.0 if target.verdict is None else 0.0
        f[11] = min(len(target.text) / 300.0, 1.0)
        anc = _ancestors(g, target.nid)
        succ = sum(1 for a in anc if g.nodes[a].verdict == "支持")
        fail = sum(1 for a in anc if g.nodes[a].verdict == "矛盾")
        f[12] = min(succ / 5.0, 1.0)
        f[13] = min(fail / 3.0, 1.0)
    f[6] = min(depth / 6.0, 1.0)
    return f


def _ancestors(g: Graph, nid):
    out, stack = [], [nid]
    while stack:
        n = stack.pop()
        for (f, t, _o) in g.edges:
            if t == n and f not in out:
                out.append(f)
                stack.append(f)
    return out


def assemble(g: Graph, ask: str) -> str:
    """**不由模型重写**，机械拼装：
      - 已核验支持 → 主体
      - 未提及/非主张 → 另列一节
      - **未核验（verdict=None）→ 单独一节，如实标注**
      - 矛盾 → 丢弃
    矛盾率因此在构造上为 0，交付宽 = 真并集。
    ⚠️ 原来没有「未核验」这一段：**verdict=None 的断言被静默丢掉**，
    新架构里大部分断言核验不完，于是装配结果变成空壳（实测 A5a 输出「（无）」）。"""
    sup = [n.text for n in g.of_kind("CLAIM") if n.verdict == "支持"]
    un = [n.text for n in g.of_kind("CLAIM") if n.verdict in ("未提及", "非主张")]
    unchecked = [n.text for n in g.of_kind("CLAIM") if n.verdict is None]
    bad = [n.text for n in g.of_kind("CLAIM") if n.verdict == "矛盾"]
    L = ["# %s" % ask, ""]
    L.append("## 经核验成立的依据")
    L += ["- " + c for c in sup] or ["- （无）"]
    L += ["", "## 依据未覆盖、仅供参考的事项"]
    L += ["- " + c for c in un] or ["- （无）"]
    if unchecked:
        L += ["", "## 未经核验的断言（仅供你自行判断）"]
        L += ["- " + c for c in unchecked]
    if bad:
        L += ["", "<!-- 已剔除与依据冲突的内容 %d 条 -->" % len(bad)]
    return "\n".join(L)
