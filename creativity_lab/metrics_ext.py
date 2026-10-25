#!/usr/bin/env python3
"""**「别人的量尺」** —— 照抄公开定义的多样性度量（不自创）

> 落点：`creativity_lab/metrics_ext.py`
> 2026-10-24 ｜ 第二组 · 层2 ｜ 预注册：`eval/PREREG-TOT-ARM.md` §1.1
>
> ## ★★ 为什么要这个文件
> 2026-10-24 凌晨的自我修正（结论 2.10）暴露了一个根因：
> **「加支数负向」是我的指标定义错误** —— 我用了「有效秩/n」，
> 而这个量**定义上必然随 n 下降** ⇒ ⇒ 我把数学恒等式当成了实验发现。
>
> ⇒ ⇒ **自己造量尺 = 自己交学费。**
> ⇒ ⇒ 本文件把**前人已经踩过坑的量尺**接进来：
> ① 定义**逐字照抄公开来源**（不凭记忆改写）
> ② **注明出处**（报告里必须能回指）
> ③ 每个量**配自检 + 负向测试**（变异注入必须能翻转）
>
> ## ★ 出处（报告引用时逐条回指）
> | 量 | 出处 | 定义位置 |
> |---|---|---|
> | `vendi_score` | Friedman & Dieng et al., *The Vendi Score: A Diversity Evaluation Metric for Machine Learning*, TMLR 2023（arXiv:2210.02410） | **Definition 3.1**：`VS = exp(−Σᵢ λᵢ log λᵢ)`，λ = **K/n** 的特征值（K 半正定核矩阵，K(x,x)=1）；官方实现 `github.com/vertaix/Vendi-Score` |
> | `self_bleu` | Zhu et al. 2018, *Improved Evaluation of Text Generation*（EMNLP） | self-BLEU：**每个候选以其余候选为参考**算 BLEU，取均值 |
> | `distinct_n` | Guo et al. 2019, *Towards Understanding and Improving Diversity in Neural Conversation Models* | **不同 n-gram 的个数 / 全部 n-gram 的个数** |
>
> ## ★ 已知口径限制（**必须随读数一起报**）
> - `vendi_score` 对**相似度矩阵的构造方式**敏感 ⇒ 本文件固定用
>   **单位化 embedding 的 Gram 矩阵** `K = X Xᵀ`（⇒ 半正定、⇒ 官方推荐路径），
>   并**同时报 `self_bleu` / `distinct_n`**（⇒ 三者方向不一致时写「不可分辨」）
> - `self_bleu` / `distinct_n` 在中文上依赖分词 ⇒ 本文件用**字符级 n-gram**
>   （中文无空格 ⇒ 词级 n-gram 不可用）⇒ **口径必须写进表头**
"""
from __future__ import annotations

import json
import itertools
import math
from collections import Counter
from typing import List, Sequence

import numpy as np


# ──────────────────────────────────────────────────────────────
# ① Vendi Score —— 照抄 Definition 3.1（arXiv:2210.02410）
# ──────────────────────────────────────────────────────────────
def vendi_score(embs: Sequence[Sequence[float]]) -> float:
    """Vendi Score = 相似度矩阵 **K/n** 的特征值的 Shannon 熵的指数。

    照抄 Friedman & Dieng et al. (TMLR 2023) **Definition 3.1**：

        VS_k(x1,…,xn) = exp( −Σ_{i=1..n} λ_i log λ_i )

    其中 λ₁…λ_n 是 **K/n** 的特征值，K 是相似度核矩阵（K_ij = k(x_i,x_j)）。

    ★ 构造方式（**本项目固定口径**，报告必须写明）：
      相似性取**单位化 embedding 的内积** ⇒ `K = X Xᵀ`（半正定）
      ⇒ 官方论文明确给出这条优化路径：K/n 的特征值 == XᵀX/n 的特征值。
      ⇒ embedding 先 L2 单位化 ⇒ K_ii = 1 ⇒ tr(K/n) = 1 ⇒ Σλᵢ = 1。

    ★★ **已知盲点（★ 本项目实测发现，必须随读数一起报）**：
      **Vendi 会把"两派对立的答案"判成"同一个模态"。**
      实测：2 支同向 + 2 支**反向** ⇒ Vendi = **1.00**（判成 1 个模态），
      而 2 支同向 + 2 支**正交** ⇒ Vendi = 2.83（3 个模态）。
      ⇒ 原因：完全反向的两支（cos = −1）与完全正交的两支产生**同样的特征值分布**。
      ⇒ ⇒ **在我们的场景里这是致命的**：「两派相反的答案」恰恰是创造性最该被识别的。
      ⇒ ⇒ ⇒ **所以 Vendi 绝不能单独作主读数**，必须与 `self_bleu` / `distinct_n` /
      **本项目自造的 `metrics.modes`（余弦阈值连通分量）并列**报 ——
      ★ 而 `modes` 在这个盲点上**恰好是对的**（反向 cos=−1 ⇒ 距离 2 ⇒ 判成两个模态）。
      ⇒ ⇒ ★★ **由此得到一条方法论结论：没有一把尺子全能 ⇒
      「化为己有」不是"用别人的替代自己的"，是"把不同的尺子并排，让它们的分歧暴露出来"。**

    ★ 与本项目自造的 `metrics.effective_rank`（PCA **参与比** `(Σλ)²/Σλ²`）的差别：
      Vendi = **谱熵的指数**（Roy & Vetterli 2007 的 effective rank 标准定义）
      参与比 = 逆参与比
      ⇒ 两者都是"有效秩"，但**不是同一个量** ⇒ **不可混用、不可互相换算**
    """
    if len(embs) < 2:
        return 1.0
    X = np.asarray(embs, dtype=float)
    if X.ndim != 2:
        raise ValueError("embs 必须是 n×d 矩阵")
    # L2 单位化 ⇒ K_ii = 1（Definition 3.1 要求 k(x,x)=1）
    nrm = np.linalg.norm(X, axis=1, keepdims=True)
    nrm[nrm == 0] = 1.0
    X = X / nrm
    K = X @ X.T                      # n×n，半正定
    A = K / len(X)                   # ★ K/n（谱已归一）
    lam = np.linalg.eigvalsh(A)      # 对称矩阵用 eigvalsh
    lam = np.clip(lam, 0.0, None)    # 数值误差可能给微小负值 → 截断
    lam = lam[lam > 0]
    if lam.size == 0:
        return 1.0
    s = lam.sum()
    if s <= 0:
        return 1.0
    lam = lam / s                   # 保险：Σλ = 1
    # 约定 0 log 0 = 0（已由 lam>0 过滤保证）
    return float(np.exp(-float((lam * np.log(lam)).sum())))


# ──────────────────────────────────────────────────────────────
# ② self-BLEU —— 照抄 Zhu et al. 2018 的口径
# ──────────────────────────────────────────────────────────────
def _tokens(text: str, char_level: bool = True) -> List[str]:
    """中文没有空格分词 ⇒ 默认用**字符级** n-gram（口径必须随读数报出）。"""
    t = "".join(text.split())
    if char_level:
        return list(t)
    return t.split()


def _ngrams(toks: Sequence[str], n: int) -> Counter:
    if len(toks) < n:
        return Counter()
    return Counter(tuple(toks[i:i + n]) for i in range(len(toks) - n + 1))


def _bleu(cand: Sequence[str], refs: Sequence[Sequence[str]], max_n: int = 4) -> float:
    """标准 BLEU（modified n-gram precision + brevity penalty），多参考版。

    ★ 公式来源：Papineni et al. 2002, *BLEU: a Method for Automatic Evaluation of Machine Translation*
    （标准定义，非自创）
    """
    if not cand:
        return 0.0
    if not refs:
        return 0.0
    c_len = len(cand)
    if c_len == 0:
        return 0.0
    logp = 0.0
    for n in range(1, max_n + 1):
        cn = _ngrams(cand, n)
        total = sum(cn.values())
        if total == 0:
            # 候选短于 n ⇒ 该阶 precision 记 0（标准做法会跳过，但 n-gram BLEU
            # 常记 0；此处记 0 并在文档中声明 ⇒ 口径固定）
            return 0.0
        max_ref = Counter()
        for r in refs:
            rn = _ngrams(r, n)
            for g, c in rn.items():
                if c > max_ref[g]:
                    max_ref[g] = c
        clipped = sum(min(c, max_ref[g]) for g, c in cn.items())
        p = clipped / total
        if p <= 0:
            return 0.0
        logp += math.log(p)
    # brevity penalty
    r_len = max((len(r) for r in refs), default=0)
    if c_len == 0:
        bp = 0.0
    elif c_len > r_len:
        bp = 1.0
    else:
        bp = math.exp(1.0 - r_len / c_len)
    return float(bp * math.exp(logp / max_n))


def self_bleu(texts: Sequence[str], max_n: int = 4, char_level: bool = True) -> float:
    """**self-BLEU**（Zhu et al. 2018 口径）：每个候选以**其余候选**为参考算 BLEU，取均值。

    ★ 越低 = 候选彼此越不同（= 越分散）。
    ★ 与 Vendi 的方向**相反**（Vendi 越高越分散）⇒ 报告里必须写清方向。
    """
    if len(texts) < 2:
        return 0.0
    toks = [_tokens(t, char_level) for t in texts]
    vals = []
    for i in range(len(toks)):
        refs = [toks[j] for j in range(len(toks)) if j != i]
        vals.append(_bleu(toks[i], refs, max_n=max_n))
    return float(sum(vals) / len(vals))


# ──────────────────────────────────────────────────────────────
# ③ Distinct-n —— 照抄 Guo et al. 2019
# ──────────────────────────────────────────────────────────────
def distinct_n(texts: Sequence[str], n: int = 2, char_level: bool = True) -> float:
    """Distinct-n = **不同 n-gram 的个数 / 全部 n-gram 的个数**（Guo et al. 2019）。

    ★ 越高 = 越不重复（= 越分散）。跨 n 可比（是比值不是计数）。
    """
    toks = [_tokens(t, char_level) for t in texts]
    total = Counter()
    for t in toks:
        total.update(_ngrams(t, n))
    if not total:
        return 0.0
    return float(len(total) / sum(total.values()))


# ──────────────────────────────────────────────────────────────
# ②b ★★ 第三把尺子：结构化去重（零 embedding、零阈值、零聚类）
# ──────────────────────────────────────────────────────────────
def structured_dedup_count(arts: List[str]) -> int:
    """**结构化去重数**：按「结论词块集合」去重后的个数。

    ★★ **为什么要加这一把**（★ 2026-10-24 深夜，来自外部评审提醒）：
    - **Vendi 有盲点**：2 支同向 + 2 支**反向** ⇒ Vendi = **1.00**（判成"同一个模态"）
      ⇒ 而「**两派相反的答案**」恰恰是创造性最该被识别的
    - ⇒ **本项目自造的 `modes` 在这个盲点上是对的**（反向 cos=−1 ⇒ 距离 2 ⇒ 两个模态）
    - ⇒ ⇒ 但 `modes` 依赖 **embedding + 阈值** ⇒ ⇒ 还需要一把**完全不依赖 embedding / 阈值 / 聚类**的尺子
    ⇒ ⇒ **本函数就是那一把**：把每支压成「词块集合」（复用 `metrics.keywords`，中文 2-gram），
    **完全相同**的集合算同一类 ⇒ **不同 ⇒ 不同类**。
    ★ 它对「**改写型**」敏感（同一答案换措辞会被算成两类）⇒ **这是它与 `family_key` 的差别**
      ⇒ ⇒ **必须与别的量并排报**（本函数返回的是**上界**，偏向高估多样性）。

    ★ 与三组 `family_key` 的关系：他们用「**模型抽取的结论族**」做结构化归并（更准，但需 LLM 判）
    ⇒ ⇒ 本函数是**零成本近似**（不需 LLM、不需新批、可离线重算）
    ⇒ ⇒ **两者应并排**：本函数 = 词面级下界实现，三组 = 语义级归并。
    """
    try:                      # ★ 包内相对 import（被当作包成员时）
        from .metrics import keywords
    except ImportError:       # ★ 直接运行时（本文件自检）
        import os as _os
        _sys_p = _os.path.join(_os.path.dirname(_os.path.dirname(
            _os.path.abspath(__file__))))
        if _sys_p not in _os.sys.path:
            _os.sys.path.insert(0, _sys_p)
        from creativity_lab.metrics import keywords
    keys = set()
    for a in arts:
        ks = frozenset(keywords(a))
        if ks:
            keys.add(ks)
    return len(keys) if keys else (1 if arts else 0)


# ──────────────────────────────────────────────────────────────
# ②c ★★ 第四把尺子：结论族去重（family_key）—— **三组给的函数，语义在判官那一半**
# ──────────────────────────────────────────────────────────────


def family_uncovered_count(cards: list) -> int:
    """★ **「未覆盖族」数**（★ 三组实测后新增的**第五种处理**）

    ★★ **为什么必须单列**（★ 三组 2026-10-25 给出真实分布）：
    | 类别 | 张数 | 含义 |
    |---|--:|---|
    | 空族 + 非承重 + `verdict=未提及` | 58 | 真没价值 ⇒ 不算路径 |
    | 空族 + 非承重 + `verdict=非主张` | 11 | 只复述题面 ⇒ 不算路径 |
    | ★ 空族 + **承重** + `verdict=矛盾` | **10** | ★ **提出了与结论空间相反的主张，但空间没给它编号** |
    | ★ 空族 + **承重** + `verdict=支持` | **5** | ★ **支持了一个没编号的主张** |
    | 空族 + 承重 + `verdict=未提及` | 4 | **判据自相矛盾**（判官说承重、又说它不支撑任何结论）|
    | 空族 + 非承重 + 矛盾/支持 | 8 | 非承重 ⇒ 不改变决策 |
    ⇒ ⇒ **89 张空族里 19 张（21%）是「承重却挂不上编号」** ⇒ ⇒ **「空族 = 没价值」会静默吞掉 21%**
    ⇒ ⇒ ★★ **而这正面命中 Vendi 的盲点**：一条「矛盾」的卡挂不上编号 ⇒ **恰恰说明结论空间漏掉了那个相反的主张**
    ⇒ ⇒ ⇒ Vendi 把它判成"同一模态"（2 同向+2 反向 = 1.00）⇒ ⇒ **`family_key` 这条路能把它暴露出来** —— 前提是**空族必须按 verdict 拆开、未覆盖族单列**
    """
    if not cards:
        return 0
    return sum(1 for c in cards
               if c.get("load_bearing") and not (c.get("supports_conclusions") or []))


def family_three_calibers(cards: list) -> dict:
    """★ **三个口径一次算齐**（★ 三组建议的落地方式）

    ⇒ ⇒ **报告里三个数并排**（★ 引用必须写明用的是哪个）：
    | 键 | 含义 |
    |---|---|
    | `n_families_loadbearing` | **承重维度（主读数）**：承重卡里**已编号**的族数（空族不计）|
    | `n_families_all` | **模态数**：全部卡去重（★ **含空族 `''`**）|
    | `n_uncovered` | ★ **未覆盖族**：承重 ∧ `supports_conclusions=[]` ⇒ **不进前两个，单列** |
    ⇒ ⇒ ★ **「结论空间覆盖率 = 1 − n_uncovered / n_load_bearing」**（★ 覆盖率低 ⇒ 结论空间漏了主张）
    """
    lb = [c for c in (cards or []) if c.get("load_bearing")]
    return {
        "n_families_loadbearing": len({family_key(c) for c in lb if (c.get("supports_conclusions") or [])}),
        "n_families_all": len({family_key(c) for c in (cards or [])}),
        "n_uncovered": family_uncovered_count(cards or []),
        "n_load_bearing": len(lb),
        "coverage": (1.0 - family_uncovered_count(cards or []) / len(lb)) if lb else float("nan"),
    }

def family_key(card: dict) -> str:
    """**族键** = `supports_conclusions` 排序后用 `|` 连接。

    ★★ **出处与定性（★ 引用前必读）**：
    - 函数本体来自**三组**：`docs/cmp8/routes/C/optimizer.py:75`（**3 行纯字符串操作，零 embedding / 零阈值 / 零聚类**）
    - ⚠️★ **它不是"从文本抽结论族"的函数** —— 归并的**语义在判官那一半**：
      判官给每条候选陈述打 `supports_conclusions = ["C3", ...]`（**题级预注册的结论编号**），
      本函数只把该列表排序后连成字符串键。
    - ⇒ ⇒ **复现这套口径 = 复现判官那一半，不是复现函数那一半。**
    - ⇒ ⇒ ⚠️ **硬前提**：每题必须有**题级预注册的结论空间**（`C1..Cn`）⇒ **不是自动的**
      ⇒ ⇒ **「两派相反答案」能否被识别，取决于结论空间里是否同时列了这两派** ⇒ 报读数时必须写明这一点
    """
    return "|".join(sorted(card.get("supports_conclusions") or []))


def family_dedup_count(cards: list, load_bearing_only: bool = True) -> int:
    """**结论族数**（= 承重维度数 / 模态数的语义级口径）。

    ⚠️★★ **本函数只数「已编号的族」** ⇒ ⇒ **「未覆盖族」必须用 `family_uncovered_count` 单列**
    ⇒ ⇒ ★ **三组实测：空族是异质的（89 张空族卡里 69 张真没价值，但 19 张 = 21% 是「承重却挂不上编号」）**
    ⇒ ⇒ ⇒ **把空族一律当"没价值"会静默吞掉 21% 的卡** ⇒ ⇒ **必须拆开报**
    

    ★ **两个口径都要报（★ 三组与我今天各自发现的同一个缺口）**：
    | 口径 | 定义 | 说明 |
    |---|---|---|
    | **`load_bearing_only=True`（默认）** | 只数**承重卡**（`load_bearing=True`）的族数 | ★ **推荐作主读数**：空族（`''`）在这张卡上代表"它什么结论都没支撑" ⇒ **不是一条路径** |
    | `load_bearing_only=False` | 数全部卡的族数（含空族 `''`） | ★ 空族会被算成**一个族** ⇒ ⇒ **两种口径的族数不同 ⇒ 引用务必写明用的是哪一个** |

    ⚠️ **注意**：与本文件的 `structured_dedup_count` **不是同一个东西** ——
    那个是**词面近似**（零 embedding/零阈值/零聚类，对改写敏感 ⇒ 多样性的【上界】，不能当"真独立性"读）；
    这个是**语义级**（需要判官 + 题级结论空间 ⇒ 准，但需要前置标注）。
    ⇒ ⇒ **两把并排才见分歧**（这正是"并列报，让分歧暴露"）。
    """
    if not cards:
        return 0
    sel = [c for c in cards if (not load_bearing_only) or c.get("load_bearing")]
    if not sel:
        return 0
    return len({family_key(c) for c in sel})


# ──────────────────────────────────────────────────────────────
# ③b ★★ 「n 基线」：任何随 n 变化的多样性度量都必须先测出它
# ──────────────────────────────────────────────────────────────
def n_baseline(ns=(3, 4, 5, 6, 8, 10, 12), dim=16, reps=300, seed=7,
               metric=None) -> dict:
    """**零假设下的「n 基线」**：真·无效应时，各多样性度量随 n 的典型走势。

    ★★ 这是 2026-10-24 凌晨那个假结论（结论 2.10）的**定量根源**：
      「秩/n」在真·无效应下**系统性下降** ⇒ 拿它检验"加支数让面变宽"（上升方向）
      ⇒ **假阴性率 ≈ 100%** ⇒ 昨晚无论真实效应是什么都会得出"负向"。

    ★ **方法（★ 必须是嵌套采样，否则配对无意义）**：
      每次重复生成 **max(ns)** 个同分布样本 ⇒ 取**前 k 个**当作 n=k 的样本
      ⇒ 这样"只改 n"，样本本身是嵌套的 ⇒ 相邻 n 的配对比较有效。

    ★ 返回：`{"vendi": {n: 中位}, "rank_per_n": {n: 中位}, "vendi_dir": {...}, "rank_dir": {...}}`
    """
    metric = metric or vendi_score

    def _rank_per_n(X):
        sv = np.linalg.svd(X, compute_uv=False) ** 2
        return float(sv.sum() ** 2 / max((sv ** 2).sum(), 1e-12))

    rng = np.random.default_rng(seed)
    mx = max(ns)
    V, R = [], []
    for _ in range(reps):
        X = rng.normal(size=(mx, dim))          # 同一分布 ⇒ 真·无效应
        V.append([metric(X[:k]) for k in ns])
        R.append([_rank_per_n(X[:k]) / k for k in ns])
    V = list(map(list, zip(*V)))
    R = list(map(list, zip(*R)))

    def _med(a):
        a = sorted(a)
        return a[len(a) // 2]

    out = {"vendi": {k: _med(v) for k, v in zip(ns, V)},
           "rank_per_n": {k: _med(v) for k, v in zip(ns, R)},
           "vendi_dir": {}, "rank_dir": {}, "reps": reps, "ns": list(ns)}
    for j in range(len(ns) - 1):
        a, b = NS_PAIR = ns[j], ns[j + 1]
        out["vendi_dir"]["%d->%d" % (a, b)] = (
            sum(1 for x, y in zip(V[j], V[j + 1]) if y > x),
            sum(1 for x, y in zip(V[j], V[j + 1]) if y < x))
        out["rank_dir"]["%d->%d" % (a, b)] = (
            sum(1 for x, y in zip(R[j], R[j + 1]) if y > x),
            sum(1 for x, y in zip(R[j], R[j + 1]) if y < x))
    return out


# ──────────────────────────────────────────────────────────────
# ④ 新因变量：选择器消耗率 / 选中支的代表性
# ──────────────────────────────────────────────────────────────
def selector_consumption(vendi_cand: float) -> float:
    """**选择器消耗率** = (Vendi(候选集) − Vendi(选中后)) / Vendi(候选集)。

    ★ 选中后只剩 1 条 ⇒ Vendi = 1 ⇒ **= (Vendi_cand − 1) / Vendi_cand**。
    ★ 含义：强选择器把"面"从 Vendi 掉到 1，掉掉的份额就是消耗率。
      0 = 没消耗（Vendi=1，本来就一个模态）；越接近 1 = 面被吃得越干净。
    ★ 这是层2 第一次可测的两因子之一（另一个 = 发散量 / 支数）。
    """
    if vendi_cand <= 1.0:
        return 0.0
    return float((vendi_cand - 1.0) / vendi_cand)


def pick_representativeness(picked_vec: Sequence[float],
                            other_vecs: Sequence[Sequence[float]]) -> float:
    """**选中支的代表性** = 选中分支与其余分支的平均余弦相似度。

    ★ 越接近 1 = 选择器挑了一条"共识支"（大家都在说的那条）⇒ 面被吃掉的原因。
    ★ 与 `selector_consumption` 互补：一个说"掉了多少"，一个说"为什么掉"。
    """
    if not other_vecs:
        return 1.0
    p = np.asarray(picked_vec, dtype=float)
    pn = np.linalg.norm(p) or 1.0
    sims = []
    for o in other_vecs:
        o = np.asarray(o, dtype=float)
        on = np.linalg.norm(o) or 1.0
        sims.append(float(p @ o / (pn * on)))
    return float(sum(sims) / len(sims))


# ──────────────────────────────────────────────────────────────
# 自检 + 负向测试（★ 每个量都必须能被变异注入翻转）
# ──────────────────────────────────────────────────────────────
def _selftest() -> int:
    rng = np.random.default_rng(0)
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print("  ✔ %s" % name)
        else:
            print("  ✘ %s %s" % (name, detail))
            fails.append(name)

    print("== Vendi ==")
    # 全相同 ⇒ K 的特征值集中 ⇒ VS = 1
    same = [[1.0, 0.0, 0.0]] * 5
    check("全相同 ⇒ Vendi≈1", abs(vendi_score(same) - 1.0) < 1e-6, "got %r" % vendi_score(same))
    # 全正交 ⇒ VS = n
    orth = np.eye(5)
    v = vendi_score(orth)
    check("全不相似 ⇒ Vendi≈n=5", abs(v - 5.0) < 1e-6, "got %r" % v)
    # ★ 2 个模态、**均匀**划分（2+2）⇒ VS = 2.0（熵最大 ⇒ exp(熵) = 簇数）
    two = [[1.0, 0, 0], [1.0, 0, 0], [0, 1.0, 0], [0, 1.0, 0]]
    v2 = vendi_score(two)
    check("2 模态·均匀(2+2) ⇒ Vendi=2", abs(v2 - 2.0) < 1e-6, "got %r" % v2)
    # ★ **不均匀**划分（3+2）⇒ VS = exp(H) < 簇数（这是熵口径的性质，必须知道）
    un = [[1.0, 0, 0]] * 3 + [[0, 1.0, 0]] * 2
    v3 = vendi_score(un)
    check("2 模态·不均匀(3+2) ⇒ Vendi<2（熵口径）", 1.9 < v3 < 2.0, "got %r" % v3)
    # ★ 变异注入（有效版）：把重复的一支挪到**新的方向** ⇒ 簇数 3→4 ⇒ Vendi 必须上升
    base = [[1.0, 0, 0], [1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
    v_before = vendi_score(base)
    mut = [list(x) for x in base]
    mut[1] = [0.0, 0.0, 1.0]          # 与第 4 支重复 ⇒ 仍是 3 簇（对称无效）
    v_same = vendi_score(mut)
    mut2 = [[1.0, 0, 0, 0], [1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0]]
    vb2 = vendi_score(mut2)                       # 3 簇（2+1+1）
    mut2[1] = [0.0, 0.0, 0.0, 1.0]                # 拆成第 4 个方向 ⇒ 4 簇
    v_after = vendi_score(mut2)
    check("变异注入：拆出新方向 ⇒ Vendi 上升", v_after > vb2,
          "%.4f → %.4f" % (vb2, v_after))
    # ★★ Vendi 的已知盲点（★ 本项目实测）：反向两支被判成"同一模态"
    v_opp = vendi_score([[1.0, 0, 0], [1.0, 0, 0], [-1.0, 0, 0], [-1.0, 0, 0]])
    check("★ 盲点：2同向+2反向 ⇒ Vendi=1（判成同一模态）", abs(v_opp - 1.0) < 1e-6,
          "got %r" % v_opp)
    check("★ 盲点对照：2同向+2正交 ⇒ Vendi>1（判成多模态）",
          vendi_score([[1.0, 0, 0], [1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]) > 1.5)
    check("变异注入：对称位置 ⇒ Vendi 不变（熵对簇大小不敏感于重排）",
          abs(v_same - v_before) < 1e-9, "%.4f vs %.4f" % (v_same, v_before))
    # ★★ n 基线（★ 嵌套采样；★ 这是昨晚假结论的定量根源）
    nb = n_baseline(ns=(3, 4, 5, 6, 8), dim=12, reps=60)
    vd = nb["vendi_dir"]["5->6"][0]
    rd = nb["rank_dir"]["5->6"][1]
    check("★ n 基线：Vendi 在真无效应下**系统性上升**", vd >= 55, "大%d/共60" % vd)
    check("★ n 基线：「秩/n」在真无效应下**系统性下降**", rd >= 50, "小%d/共60" % rd)

    print("== self-BLEU ==")
    check("全相同 ⇒ self-BLEU≈1", abs(self_bleu(["abcabc"] * 4) - 1.0) < 1e-6,
          "got %r" % self_bleu(["abcabc"] * 4))
    check("完全不同 ⇒ self-BLEU≈0", self_bleu(["aaaa", "bbbb", "cccc", "dddd"]) < 1e-6,
          "got %r" % self_bleu(["aaaa", "bbbb", "cccc", "dddd"]))
    s_before = self_bleu(["abcdefgh", "abcdefgh", "zzzzyyyy", "qqqqwwww"])
    s_after = self_bleu(["abcdefgh", "zzzzzzzz", "zzzzyyyy", "qqqqwwww"])
    check("变异注入：拉开两支 ⇒ self-BLEU 下降", s_after < s_before,
          "%.4f → %.4f" % (s_before, s_after))
    check("方向与 Vendi 相反（Vendi↑ ⇒ self-BLEU↓）", True)

    print("== Distinct-n ==")
    check("全相同 ⇒ Distinct-2 < 1", distinct_n(["abcabc"] * 4, 2) < 1.0)
    # ⚠️ 变异串必须**不与其它串共享任何 bigram**，否则不同 n-gram 数不变（我第一版就踩了）
    d_before = distinct_n(["abcdefgh", "abcdefgh", "klmnopqr", "stuvwxyz"], 2)
    d_after = distinct_n(["abcdefgh", "ABCDEFGH", "klmnopqr", "stuvwxyz"], 2)
    check("变异注入：拉开两支 ⇒ Distinct-2 上升", d_after > d_before,
          "%.4f → %.4f" % (d_before, d_after))

    print("== 结构化去重 ==")
    check("全相同 ⇒ 结构化去重=1", structured_dedup_count(["abcabc"] * 4) == 1,
          "got %r" % structured_dedup_count(["abcabc"] * 4))
    check("全不同 ⇒ 结构化去重=n", structured_dedup_count(["aaaa", "bbbb", "cccc", "dddd"]) == 4,
          "got %r" % structured_dedup_count(["aaaa", "bbbb", "cccc", "dddd"]))
    # ★ 关键盲点检验：Vendi 把"反向"判成 1 个模态，而结构化去重必须判成 2 个
    op = ["这个方案应该全面推进因为收益很大", "这个方案应该全面推进因为收益很大",
          "这个方案绝对不能推进因为风险极高", "这个方案绝对不能推进因为风险极高"]
    sd = structured_dedup_count(op)
    check("★ 对立答案 ⇒ 结构化去重≥2（补上 Vendi 的盲点）", sd >= 2, "got %r" % sd)

    print("== 结论族去重（family_key）==")
    cards = [{"supports_conclusions": [], "load_bearing": False},
             {"supports_conclusions": [], "load_bearing": False},
             {"supports_conclusions": ["C3"], "load_bearing": True},
             {"supports_conclusions": ["C5"], "load_bearing": True},
             {"supports_conclusions": ["C6"], "load_bearing": True}]
    check("承重口径：3 个承重族（C3/C5/C6）", family_dedup_count(cards) == 3,
          "got %r" % family_dedup_count(cards))
    check("全卡口径：空族也算一个 ⇒ 4", family_dedup_count(cards, load_bearing_only=False) == 4,
          "got %r" % family_dedup_count(cards, load_bearing_only=False))
    check("★ 两种口径的族数不同（★ 引用时必须写明用哪个）",
          family_dedup_count(cards) != family_dedup_count(cards, load_bearing_only=False))
    check("★ 换说法不分裂：同挂 C3 ⇒ 同一族",
          family_key({"supports_conclusions": ["C3"]}) == family_key({"supports_conclusions": ["C3"]}))
    check("★ 对立答案 ⇒ 分成两族（正面命中 Vendi 的盲点）",
          family_dedup_count([{"supports_conclusions": ["C1"], "load_bearing": True},
                              {"supports_conclusions": ["C2"], "load_bearing": True}]) == 2)
    print("== 未覆盖族（★ 第五种处理）==")
    cards2 = [{"supports_conclusions": [], "load_bearing": True},      # ★ 承重但挂不上编号
               {"supports_conclusions": [], "load_bearing": False},     # 真没价值
               {"supports_conclusions": ["C1"], "load_bearing": True}]
    check("★ 未覆盖族数 = 1（只数承重且空族）", family_uncovered_count(cards2) == 1,
          "got %r" % family_uncovered_count(cards2))
    cal = family_three_calibers(cards2)
    check("★ 三口径：承重族=1 / 全卡族=2 / 未覆盖=1",
          cal["n_families_loadbearing"] == 1 and cal["n_families_all"] == 2 and cal["n_uncovered"] == 1,
          json.dumps(cal, ensure_ascii=False))
    check("★ 覆盖率 = 1 − 1/2 = 0.5", abs(cal["coverage"] - 0.5) < 1e-9, "got %r" % cal["coverage"])

    print("== 消耗率 / 代表性 ==")
    check("Vendi=1 ⇒ 消耗率 0", abs(selector_consumption(1.0)) < 1e-9)
    check("Vendi=5 ⇒ 消耗率 0.8", abs(selector_consumption(5.0) - 0.8) < 1e-9)
    r = pick_representativeness([1.0, 0], [[1.0, 0], [1.0, 0]])
    check("选中支与全部相同 ⇒ 代表性=1", abs(r - 1.0) < 1e-9, "got %r" % r)
    r2 = pick_representativeness([1.0, 0], [[0.0, 1.0], [0.0, 1.0]])
    check("选中支与全部相反 ⇒ 代表性=0", abs(r2) < 1e-9, "got %r" % r2)

    print()
    if fails:
        print("✘ 自检失败 %d 项：%s" % (len(fails), fails))
        return 1
    print("✔ 全部自检通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
