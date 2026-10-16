# 源码级核实记录

> 这一份只记**我亲自下载源码 / 抓取原文核对过**的东西。
> 摘要级了解与推断，全部明确标注。

---

## 1. `princeton-nlp/tree-of-thought-llm`（★6078，Python）

**已下载源码核验。** 关键片段（`src/tot/models.py` 与 `src/tot/methods/bfs.py`）：

```python
def get_samples(task, x, y, n_generate_sample, prompt_sample, stop):
    ...
    return [y + _ for _ in samples]              # 生成

def get_values(task, x, ys, n_evaluate_sample, cache_value=True):
    for y in ys:
        if y in local_value_cache: value = 0   # 评估（带缓存）
        else: value = get_value(task, x, y, ...)

# solve() 里的三段：
new_ys    = [get_samples(task, x, y, ...)]              # ← 独立 gpt() 调用
values    = get_values(task, x, new_ys, ...)             # ← 独立 gpt() 调用
select_ids = sorted(ids, key=lambda x: values[x])[:n]   # ← 纯 Python
```

### 四个可插拔槽位

| 参数 | 可选值 |
|---|---|
| `method_generate` | `sample` / `propose` |
| `method_evaluate` | `vote` / `value` |
| `method_select` | **`sample`（按价值加权随机）** / `greedy` |
| 搜索 | BFS / DFS |

`method_select == 'sample'` 的实现：

```python
ps = np.array(values) / sum(values)
select_ids = np.random.choice(ids, size=args.n_select_sample, p=ps).tolist()
```

**探索项就在这里**——ToT 的选择器自带随机化，本包的 `Select` 是它的等价物。

### 状态外置

`y` 是一个 Python 字符串，步与步之间累积。**搜索不发生在模型的上下文窗口里。**

---

## 2. 一处需要更正的转述

某篇 preprint（原话）称 ToT：

> *"interleaves generator and evaluator within the same model call"*

**源码不支持这句话。** 生成与评估是两个独立的 `gpt()` 调用，评估甚至有自己的 `local_value_cache`。

那篇 preprint 用它来确立「与 ToT 有承重差异」。**第三条论据在代码层面不成立。**
（它的另外两条——分支共享上下文、分支驱动是下一步变化——尚未逐条核验。）

---

## 3. 其余仓库的实时状态（GitHub API，2026-10-16）

| 仓库 | ★ | 最近 push | 备注 |
|---|:-:|---|---|
| `UditAkhourii/adhd` | 4412 | 2026-10-05 | **唯一完整读过 preprint 全文 + 源码 + 7 个 issue 的** |
| `icaros-usc/pyribs` | 268 | **2026-07-22** | 唯一仍在活跃维护的 QD 库 |
| `icaros-usc/map-elites` | — | — | **不存在**（我最初给的链接是错的） |
| `deeplearning-wisc/mace` | 9 | 2026-07-11 | **只有一行 README**：「code will be released soon」；至今未放 |
| `uber-research/poet` | 269 | **2022-03-23** | 停更 4 年；且其「问题」是可参数化环境，与人生类问题不同构 |
| `Xtra-Computing/MAS_Diversity` | 14 | 2026-04-23 | 有真实分析代码（拓扑/轨迹/交互景观） |
| `MineDojo/Voyager` | 7266 | 2024-04-03 | 停更 2 年 |
| `spcl/graph-of-thoughts` | 2842 | 2026-03-24 | 活跃 |

### POET 的迁移性存疑

POET 的核心能力是**自动生成新问题**，因为它的「问题」是环境参数（地形、速度、障碍）——
**一个低维、可枚举、可突变的空间**。

「620 分选大学」没有这种结构。**POET 的前提在目标场景里可能根本不成立。**

---

## 4. 沙箱访问路径（全部实测）

| 目标 | 结论 |
|---|---|
| `gh` | 不存在 |
| `git clone` GitHub | 失败（TLS 代理）；**修法** `git config --global http.sslCAInfo $SSL_CERT_FILE` |
| GitHub REST API | ✅ |
| `codeload.github.com` tarball | ✅ |
| `aclanthology.org` | 页面可 curl（`web_fetch` 失败） |
| `doi.org` 页面 | 失败 → 改用 Crossref API |
| `pubmed.ncbi.nlm.nih.gov` | 失败 → 改用 NCBI E-utilities |
| arXiv PDF 直连 | 超时 → 改用 `export.arxiv.org/api/query` |
| `registry.npmjs.org` | ✅（pip 全部索引不通） |
| `hf-mirror.com` | ✅（huggingface.co 不通） |
| Claude Agent SDK | 指 `https://api.minimaxi.com/anthropic` 可用 |

---

## 5. MiniMax 接口的三个坑

1. **embedding 参数是 `texts` 不是 `input`**，且必须带 `type: "db"`（`document` 报错）
2. **`<think>` 块会吃光 `max_tokens`** → 需 8000 起，并检查 `finish_reason == "length"` 后加预算重试
3. **弱档位（M2.5 / M2.1）会把预算花在 meta 分析 persona 指令上**，返回未闭合 `<think>` 且无正文 → 判据：未闭合即视为失败重试
4. **M3.1-Flash-Preview 把思考放进 `reasoning_content`**（实测 17081 字符），`content` 可能整个缺失
