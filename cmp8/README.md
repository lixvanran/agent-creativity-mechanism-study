# 五族对比实验（用户的四道题）· cmp8 交付包

## 从这里开始（阅读顺序）

0. **先读 `AGENT_RUNBOOK.md`** —— 执行手册（硬约束 6 条 / 阶段 0-6 / 闸门 / 监控规则 / 故障排查 / 结论怎么写）
1. **再读 `METHOD.md`** —— 实验方法学（7 臂精确定义 / 依据包硬规则 / 判官协议 / 7 个指标逐个定义与坑 / 统计口径 / 已知局限 / 数据完整性检查清单）
2. **然后看本文件** —— 快速上手（目录 / 环境变量 / 跑法 / 指标速查 / 诚实边界 / 重建说明）
3. **接手方再读 `HANDOVER-cmp8-2026-10-20.md`** —— 完整交接（项目命题 / 已确立-已证伪-未决三张表 / 资产 node_id / 全部命令 / 口径纪律 / 24 条踩坑清单 / 实测数字速查 / 工作清单 / 报告必留声明）

> **拿不到包？** 用包根的 `cmp8_fetch.py`：`python3 cmp8_fetch.py --node-id 454375285564150`
> （本机没有 mavis CLI 时，用 Mavis 文件管理界面复制签名下载链接，再 `--url "<链接>"`）


> 2026-10-20 封版。**判官通道已实测打通**（自检 4/4 + 4/4，两组判官都过）⇒ 可以开跑。
> 源文件在沙箱重置后丢失，本包是**重建版**（见文末「来源与重建声明」与 `_CMP8_RECOVERY.md`）。

## 目录

```
cmp8pkg/
├─ creativity_lab/          核心库
│  ├─ client.py             MiniMax 客户端（chat+embed，带过载降级）
│  ├─ metrics.py            _mat / cosine
│  ├─ verify.py             核验器（CHECK4 已泛化到非法律域）
│  ├─ ops.py                操作集 + 图执行器 + 机械装配
│  ├─ orclient.py           OpenRouter 跨厂商判官客户端（**已修：404/403 分类 + 空产出抛错**）
│  ├─ learnarch.py          可学习架构的 episode 执行器（**已修：补 import time**）
│  ├─ adhd_repro.py         ADHD 项目机制复刻（15 帧 + 11 步流水线）
│  └─ data/user4_q{1..4}.json   4 个依据包
├─ armdeps/                 臂3/臂4 用的旧架构代码 + 题面单一真相源
│  ├─ client2.py  shared.py  arm3.py  topics4.py
├─ runs/arch_learn/result.json   学到的策略权重（A5b 用）
├─ run_compare5.py          7 臂驱动
├─ analyze_cmp6.py          跨厂商判官分析器（自检不过就拒绝出数）
├─ smoke_or.py              冒烟测试
├─ build_compare5_page.py   判读页生成
├─ go_cmp8.sh               一键编排
├─ EXPERIMENT-v2-DESIGN.md  实验设计 v2
├─ _CMP8_RECOVERY.md        恢复说明 + 重建记录
└─ README.md                本文件
```

## 依赖

```bash
pip install numpy
```

（只用标准库 + numpy。没有 requests。）

## 环境变量

```bash
export MINIMAX_SUBSCRIPTION_KEY=<你的 minimax key>
export OPENROUTER_API_KEY=<你的 openrouter key>
export PRIMARY_MODEL=MiniMax-M3.1-Flash-Preview   # M3 当天持续过载(529)，用健康档位
export OR_PRIMARY=deepseek/deepseek-chat           # 最便宜的可用判官（实测通过自检 4/4+4/4）
export OR_EMBED=qwen/qwen3-embedding-8b            # OpenRouter 的 openai/* embedding 被 403，禁用
export CMP_OUT=runs/cmp8
export ADH_MODE=repro                            # 臂2 走 Python 复刻
```

## 跑

```bash
# 一步到位
bash go_cmp8.sh

# 或分步（推荐第一次分步，好观察）
python3 smoke_or.py          # 冒烟：不过就别往下跑
python3 run_compare5.py --arms A1,A2,A3,A4,A5a,A5b,A5c --reps 3 --workers 4
python3 analyze_cmp6.py
python3 build_compare5_page.py
```

**耗时**：跑批 1.5–2 小时（7 臂 × 4 题 × 3 重复 ≈ 700 次调用）。
**成本**：被测走 MiniMax 订阅 = $0；OpenRouter 判官 ≈ $0.12，embedding ≈ $0.05。**总计 < $1**。

## 输出

- `runs/cmp8/analysis.json` —— 全部指标（机器可判），含 `judge` / `judge_used` / `judge_same_vendor` / `embed` / `census`
- `runs/cmp8/compare5_report.html` —— **判读页**：每臂每题每重复的原始答案 + 指标
- `runs/cmp8/judge_selfcheck.json` —— 判官自检结果
- `runs/cmp8/runlog.jsonl` —— 每次调用的审计日志

## 臂

| 臂 | 是什么 | 调用数 | 作用 |
|---|---|:-:|---|
| A1 | 直调 | 1 | 基线 |
| A2 | 开源 ADHD 项目（**机制复刻**） | 12 | 外部项目对照 |
| A3 | 双轴·**融合门** | 8 | 旧架构 |
| A4 | 双轴·**去融合门** | 6 | 旧架构最强版 |
| A5a | 新架构·**无核验** | ~12 | **控制**：隔离「有没有 oracle」 |
| A5b | 新架构·**学到的策略** | ~14 | **主实验** |
| A5c | 新架构·**初始 w=0** | ~14 | **控制**：隔离「学到的权重有没有用」 |

## 指标口径

- **宽度（去重）**：单份答案去重后的断言数。模型会在一份答案里把同一事实说 3–4 遍，
  所以任何按断言条数算的量都必须先去重。
- **并集宽度**：同臂 3 份去重后的并集 = 覆盖广度。
- **矛盾率**：矛盾 /(支持+矛盾)。**唯一有方差、能当仲裁器的量。**
- **离散度**：3 份之间两两语义距离均值。
- **种子噪声地板**：同臂同题 3 次重复的逐份矛盾率标准差。
  分析器最后会打印它 —— **⑤b 与 ⑤c 的差异若小于这个地板，就是噪声，不是效果。**

## 诚实边界

1. **臂2 是机制复刻，不是原版本体**。照搬 `src/engine.ts`（reframe→5帧×6想法→
   score+cluster→deepen top3 = 11 次调用）、`src/packs/core.ts` 的 15 个认知帧、
   `src/render.ts` 的输出形状，**只换传输层**（原版走 claude-agent-sdk，当天挂死）。
   差异：原用 `systemPrompt:{preset:"claude_code"}` 会叠加 Claude Code 自己的系统提示，
   复刻版只注入项目自己的 system prompt。
2. **模型集被固定为 5 个健康档位**（M3.1-Flash-Preview / M2.7 / M2.5 / M2.1 / M2），
   各臂完全一致——因为 M3 当天整片返回 529。
3. **判官是跨厂商的 Grok / DeepSeek / Qwen 等非 MiniMax 模型**，被测是 MiniMax。
   判官自检不过（已知假断言召回 <50%）⇒ **拒绝出数**。
4. **用户的四道题是外部测试集**，全程未进训练。依据包由子代理联网独立构造，
   **不读任何已有答案**，只收原子事实、不收建议。
5. **最终评分由人做。** 判读页给的是原始答案，指标只是辅助。
6. **本包是重建版**（源文件在 2026-10-20 沙箱重置后丢失），不是原始文件的逐字节副本。

---

# 补充说明（打包时追加）

## 1. `sys.path` 硬编码问题：已处理，无需手动改

原 `run_compare5.py` 里有 `sys.path.insert(0, "/workspace/exp-writing-compare")`。
本包里已改为**按脚本自身位置定位**，不依赖任何绝对路径：

```python
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "armdeps"))
```

`arm3.py` / `client2.py` / `shared.py` / `topics4.py` 都在 `armdeps/`，解压后从包根跑即可。
**唯一保留的绝对路径**：`run_compare5.py` 里 `ADH_REPO` 默认值 `/workspace/adhd-repo`，
那是 `ADH_MODE=node` 走原版 node CLI 用的；本包默认 `ADH_MODE=repro`（Python 复刻），**用不到它**。

## 2. `armdeps/topics4.py` 是真文件（不是占位）

它现在是**题面的单一真相源**（含 4 道题定义，`python3 topics4.py` 可直接打印）。
`run_compare5.py` 优先 `from topics4 import TOPICS4`，读不到才回退到自己内联的副本（内容一致）。

## 3. `runs/arch_learn/result.json`（A5b 的命根子）

**学到的 14 维策略权重**，A5b 直接读它（`os.path.join(HERE, "runs", "arch_learn", "result.json")`）。
这是**训练产物不是代码** —— 离开它 A5b 就没有意义，所以随包附上（不在最初清单里，但属于跑得起来的必要件）。

## 4. ★ OpenRouter 通道：根因已查明并修好

打包方沙箱里第一次跑 `smoke_or.py` 是**通不过**的（chat 返 0 字符、embedding 报 provider ToS）。
**根因不是 key、不是账号、不是 IP** —— 逐个探针查完的：

| 探针 | 结果 |
|---|---|
| `GET /key` | ✅ 健康：`limit_remaining 4.999 / 5`，`spend 0.0007` |
| `GET /credits` | ✅ 健康：账号 $20，总用 $9.75 |
| `x-ai/grok-3-mini`（**原默认判官**） | ❌ **404 已下架**：「Grok 3 Mini is deprecated → 改用 Grok 4.3」 |
| `x-ai/grok-4-fast` / `grok-3` / `grok-2-1212` | ❌ 404 同样下架 / 无 endpoint |
| `openai/text-embedding-3-small`（**原默认 embedding**） | ❌ **403 provider ToS violation** |
| `openai/gpt-4o-mini` / `google/gemini-2.5-flash` | ❌ 403「not available in your region」 |
| `google/gemini-embedding-001` | ❌ 403 ToS |
| **`deepseek/deepseek-chat`** | ✅ 可用（$0.26/$1.03 每 M，**最便宜的活判官**） |
| **`x-ai/grok-4.3`** | ✅ 可用（$1.25/$2.50 每 M，xAI 官方推荐） |
| **`qwen/qwen3.7-plus`** / `z-ai/glm-4.5` / `meta-llama/llama-3.3-70b-instruct` | ✅ 可用 |
| **`qwen/qwen3-embedding-8b`** | ✅ 可用（4096 维）｜`qwen3-embedding-4b`(2560) / `baai/bge-m3`(1024) / `all-minilm-l6-v2`(384) 也可用 |

**包内已改**（你不用手动改任何东西）：

- 默认判官 `OR_PRIMARY`：`x-ai/grok-3-mini` → **`deepseek/deepseek-chat`**
- 判官 fallback：`grok-4.3` → `qwen3.7-plus` → `llama-3.3-70b-instruct` → `glm-4.5`
- 默认 embedding `OR_EMBED`：`openai/text-embedding-3-small` → **`qwen/qwen3-embedding-8b`**
- embedding fallback：去掉被 403 的 `google/gemini-embedding-001`
- **新增 `Embedder`**：OpenRouter embedding 失败**自动退 MiniMax `embo-01`**（1536 维），
  实际用了哪个会记进 `analysis.json` 的 `embed` 字段
- **`classify` 新增 `gone`(404) / `forbidden`(403)**：模型下架/被封 ⇒ 立刻换下一个模型
- **★ 修掉「0 字符不报错」**：原来 404 被归成 `other` ⇒ 静默重试 4 次后 `return ""`，
  调用方拿到空串却没有任何错误信息（一次模型下架就能让整套实验静默产出 0 字符）。
  现在**全部失败必须抛错并带上原因**，冒烟会直接告诉你「哪个模型、什么错」。

**判官自检实测（真闸门，两组都过）**：

```
判官 deepseek/deepseek-chat ：真断言 4/4 ｜ 假断言 4/4   ✅ 冒烟全部通过，可以开跑
判官 x-ai/grok-4.3          ：真断言 4/4 ｜ 假断言 4/4   ✅ 冒烟全部通过，可以开跑
```

⇒ **判官是活的，闸门已过。**（4 道题各 1 条真断言 + 1 条假断言，判定全对。）
想换判官只改 `OR_PRIMARY` 即可（`x-ai/grok-4.3` 同样过了自检）。

⚠️ **一个诚实的口径警告**：去重阈值 `0.75` 是在 **MiniMax `embo-01`** 上标定的。
换 embedding 模型会改变余弦相似度的尺度 ⇒ 同一个 0.75 在 `qwen3-embedding-8b` 上含义不同
⇒ **「宽度 / 去重宽」这类指标不能跨 embedding 模型比较**。
`analysis.json` 里会记 `embed` 字段；**报告时必须一起写出来**。
（想要严格可比的宽度，就把 `OR_EMBED` 显式设成能用的 MiniMax 通道。）

## 5. 来源与重建声明（请读）

- 本实验的**原始源文件在 2026-10-20 沙箱重置后丢失**（`/workspace/lab/creativity_lab/`、
  `/workspace/exp-writing-compare/` 等目录已不存在，drive 上也从未留存这条实验线）。
- 本包由三个**自包含还原脚本** `cmp8_p0.py`（依据包）/ `cmp8_p1.py`（核心库）/
  `cmp8_p2.py`（驱动 + 臂依赖 + 权重 + 指南）重建而成，重建依据是该会话当时的工作记忆与
  设计文档，**不是原始文件的逐字节副本** ⇒ **函数签名、prompt 措辞、常量可能与原版有出入**；
  跑出来的数字用于方向性判断可以，**不要当精确复现**。
- 已知的一处**有意改动**：`creativity_lab/verify.py` 的 CHECK4 第一步，
  原本问「这条陈述是不是**法律主张**」—— 那个问法在非法律域（本题四道题都不是法律域）
  会把含题面数字的陈述误判成「复述题面」→ 判成非主张。已泛化为「可核验的事实性断言」，
  判据是「只要陈述里含有超出问题本身的信息（数字/阈值/名称/规则/主体关系）就当它是断言」。
  泛化后**法律域回归 27/27 保住、矛盾召回仍 9/9 = 100%**。
- 打包时另修了 4 个 bug（详见 `_CMP8_RECOVERY.md` §4）：还原脚本少一个 `'''` 导致直接 SyntaxError；
  `learnarch.py` 用了 `time.sleep` 却没 `import time`（只在异常路径触发）；
  `topics4.py` 原本是死文件，现改为单一真相源；
  **OpenRouter 404/403 被当成 `other` 静默重试后 `return ""`**（模型下架会让整套实验静默产出 0 字符）。
- 依据包（4 题的「外部核验依据包」）是**联网独立构造**的原子事实集，
  只收可核验事实、不收建议；每题 `sources` 字段只保留了主来源域名 + 日期，
  **完整 URL 清单在原会话的原始 JSON 里**（未随包附上，因为原文件已随沙箱丢失）。

## 6. 打包清单核对

| 路径 | 状态 |
|---|---|
| `creativity_lab/orclient.py` | ✔（**已修**：404/403 分类、空产出抛错、默认模型换新） |
| `creativity_lab/adhd_repro.py` | ✔ |
| `creativity_lab/learnarch.py` | ✔（已补 `import time`） |
| `creativity_lab/ops.py` | ✔ |
| `creativity_lab/verify.py` | ✔（CHECK4 已泛化） |
| `creativity_lab/client.py` | ✔ |
| `creativity_lab/metrics.py` | ✔ |
| `creativity_lab/data/user4_q{1..4}.json` | ✔ ×4 |
| `run_compare5.py` | ✔（相对路径 + topics4 单一真相源） |
| `analyze_cmp6.py` | ✔（记录 judge / embed / judge_same_vendor） |
| `build_compare5_page.py` | ✔ |
| `smoke_or.py` | ✔（打印失败原因；embedding 有 MiniMax 兜底） |
| `go_cmp8.sh` | ✔ |
| `armdeps/arm3.py` / `client2.py` / `shared.py` / `topics4.py` | ✔ ×4 |
| `EXPERIMENT-v2-DESIGN.md` | ✔ |
| `_CMP8_RECOVERY.md` | ✔ |
| `runs/arch_learn/result.json` | ✔（A5b 必需） |
| `README.md` | ✔（本文件） |

## 7. 一键重建（`rebuild/`）

包里带了当初**从会话历史救回源码用的三个自包含脚本** + 通道修复补丁：

```bash
cd rebuild && bash rebuild.sh        # 在包根重建出 ./cmp8/ 整棵树
```

= `cmp8_p0.py`（依据包）→ `cmp8_p1.py`（核心库）→ `cmp8_p2.py`（驱动/臂依赖/权重/指南）
→ `patch_or.py`（OpenRouter 通道修复 + 静默失败修复 + 保留率体检表 + 判官解析失败率体检）
→ `patch_runbook.py`（执行手册两处补丁：判官解析失败率怎么读 + 阶段 5 回报清单）。
**两个 patch 脚本都是幂等的**（锚点不在但新文本已在 ⇒ 跳过不报错）。

⚠️ **必须跑完 `patch_or.py`**：三个 p 脚本是**沙箱重置前**的版本，
里面的默认判官（`x-ai/grok-3-mini`）与默认 embedding（`openai/text-embedding-3-small`）
**都已失效**（404 下架 / 403 ToS），`patch_or.py` 会把它们换成实测可用的模型并修掉
"0 字符不报错"的静默失败。**只跑 p0/p1/p2 不跑 patch 的话，重建出来的树是不能跑的。**

（另：原会话还有一个 `cmp8_p3.py`（判官供应商可切换），**它的功能已并入 `patch_or.py`**
——`patch_or.py` 里的 `Embedder` 做的就是同一件事，且多一个 MiniMax `embo-01` 兜底。）

## 8. 去重体检（跑完分析后必看）

`analyze_cmp6.py` 现在会多打一张表：**保留率 = 去重宽 / 原始断言数**。

- 0.2 ~ 0.6 ⇒ 去重在工作，宽度轴可用
- **< 0.15 ⇒ 去重几乎全合并 ⇒ 宽度轴已退化**（表格看着正常但这一轴废了）
- **> 0.85 ⇒ 去重几乎没起作用 ⇒ 阈值太松**

`n_raw`（原始断言数）**不依赖 embedding**，是这次对比里最无争议的广度指标
（虽然会被"模型把同一件事说 3–4 遍"抬高，但对所有臂一视同仁，臂间比较有效）。
**即使宽度轴废了，用 `n_raw` 也能撑住"谁覆盖得更多"这个判断。**

想复核宽度轴的稳健性，用 MiniMax 通道再跑一遍分析（0.75 阈值就是在它上面标定的）：

```bash
EMBED_PROVIDER=minimax CMP_OUT=runs/cmp8_mmemb python3 analyze_cmp6.py
```
两遍**臂间排序一致** ⇒ 宽度结论稳健；**不一致** ⇒ 两个数都报，并写明"宽度结论依赖 embedding 通道，不稳"。
