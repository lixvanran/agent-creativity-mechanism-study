"""门控抽象。

**核心约束**：Gate 只能读取候选文本和**外部传入的参照数据**。
它不允许、也不应该知道「这题的答案空间是什么」。

我此前三次犯的错都是在这里犯的：
  - 手挑认知框架（替模型指定看世界的角度）
  - 手写实体表（替模型指定答案里该出现的词）
  - 手挑选项类别（替模型指定答案空间的分类法）
三次都是**在 Gate/框架里写我的先验**。

所以 Gate 的接口被设计成只能做「度量」，度量所需的一切由调用方从
**数据**（参照集、检索结果、外部查询）传入，而不是由作者写死。
"""
from __future__ import annotations
from typing import Protocol, Sequence
from creativity_lab.client import cosine


class Gate(Protocol):
    name: str

    def score(self, candidates: Sequence[str], ref_vecs: Sequence[Sequence[float]]) -> list[float]:
        """对每个候选给出一个 [0,1] 的度量值。**不判断好坏，只度量。**"""
        ...


class EscapeGate:
    """逃逸度：候选离参照系（通常是同题的多次直接采样）有多远。

    参照系必须由调用方提供 —— 通常是臂1 的多次真实产出。
    本 Gate 内部不含任何题目内容。
    """
    name = "escape"

    def __init__(self, ref_vecs):
        self.ref = list(ref_vecs)

    def score(self, candidates, ref_vecs=None):
        ref = list(ref_vecs) if ref_vecs is not None else self.ref
        out = []
        for c in candidates:
            v = _one(c, ref)
            out.append(max(0.0, 1.0 - v))
        return out


class LexicalSpreadGate:
    """批内两两距离中位数。只看文本统计，与题目语义无关。"""
    name = "spread"

    def score(self, candidates, ref_vecs=None):
        if len(candidates) < 2:
            return [0.0] * len(candidates)
        vecs = _embed(candidates)
        ds = []
        for i in range(len(vecs)):
            for j in range(i + 1, len(vecs)):
                ds.append(1.0 - cosine(vecs[i], vecs[j]))
        ds.sort()
        return [ds[len(ds) // 2]] * len(candidates)


def _weighted_sample(rng, wts, k):
    """按权重**不放回**抽样 k 个下标（ToT method_select='sample' 的语义）。

    ★ 旧实现把抽样结果又按权重排序 ⇒ 恒返回 argmax ⇒ 随机性失效。
    ★ 本实现：每次按权重抽一个，抽出后从池中移除 ⇒ 随机性真实生效。
    """
    pool = list(range(len(wts)))
    out = []
    for _ in range(min(k, len(pool))):
        tot = sum(max(wts[i], 0.0) for i in pool)
        if tot <= 0:
            i = pool[rng.randrange(len(pool))]
        else:
            r = rng.random() * tot
            acc = 0.0
            i = pool[-1]
            for j in pool:
                acc += max(wts[j], 0.0)
                if r <= acc:
                    i = j
                    break
        pool.remove(i)
        out.append(i)
    return out


class Select:
    """选择器：**必须是纯函数**，像 ToT 的 method_select 那样可以一行切换。

    - `greedy` 取最大度量
    - `sample` 按度量做加权随机（ToT 里 method_select='sample' 的等价物）
    - `novelty_biased` 取 (1 - 逃逸度) * w + 逃逸度 * (1-w) 的加权随机

    这是我此前四臂里**完全缺失**的槽位：它们把「选择」塞进了一次 LLM 调用里，
    于是我连温度都调不了。
    """
    def __init__(self, mode: str = "greedy", w: float = 0.8, rng=None):
        if mode not in ("greedy", "sample", "novelty_biased"):
            raise ValueError(mode)
        self.mode, self.w, self.rng = mode, w, rng

    def __call__(self, scores: Sequence[float], k: int = 1) -> list[int]:
        n = len(scores)
        if n == 0: return []
        if k >= n: return list(range(n))
        if self.mode == "greedy":
            order = sorted(range(n), key=lambda i: -scores[i])
        else:
            import random
            rng = self.rng or random.Random(0)
            pool = list(range(n))
            if self.mode == "novelty_biased":
                # 把逃逸度反向加权：用 1-escape 表示"贴参照系"的程度
                wts = [s * (1 - self.w) + (1 - s) * self.w for s in scores]
            else:
                wts = [max(s, 1e-9) for s in scores]
            # ★★ 2026-10-23 修：旧实现是 `rng.sample(...)` 后又 `sorted(key=-wts)`
            #   ⇒ 排序把随机性抹掉 ⇒ **sample 恒等于 greedy**（项目的"随机选择器"
            #     从来没真正生效过）。现在改成**按权重不放回抽样**（ToT 的
            #     method_select='sample' 的正确语义）。
            return _weighted_sample(rng, wts, k)
        return order[:k]


# --- 内部：延迟注入 embed，避免循环依赖 ---
_EMBED = None
def _embed(texts):
    global _EMBED
    if _EMBED is None:
        from creativity_lab.client import LLM
        _EMBED = LLM()
    return _EMBED.embed(list(texts))

def _one(text, ref):
    vecs = _embed([text] + list(ref))
    v = vecs[0]
    return max((cosine(v, r) for r in vecs[1:]), default=0.0)
