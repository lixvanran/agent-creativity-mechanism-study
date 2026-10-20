# CMP8 文件恢复说明（_CMP8_RECOVERY.md）

> 时间线：**2026-10-20 16:04 – 16:35 UTC**
> 事件：沙箱重置 → cmp8 源文件全丢 → 从会话历史重建 → 修 4 个 bug → 判官通道打通 → 重新打包。

---

## 1. 发生了什么

2026-10-20 16:04，本会话（cron 任务「打包五族对比实验交付包」）启动时，
`/workspace` 是一个**全新的空挂载**（只剩 `.plugin-cache`）。
原先工作区里的这些文件**全部不存在**：

```
/workspace/lab/creativity_lab/{orclient,adhd_repro,learnarch,ops,verify,client,metrics}.py
/workspace/lab/creativity_lab/data/user4_q*.json
/workspace/{run_compare5,analyze_cmp6,build_compare5_page,smoke_or}.py
/workspace/{go_cmp8.sh,EXPERIMENT-v2-DESIGN.md}
/workspace/exp-writing-compare/{arm3,client2,shared,topics4}.py
/workspace/_CMP8_RECOVERY.md
```

## 2. 排查过哪些地方（结论：源文件只在被重置的沙箱里）

| 位置 | 结果 |
|---|---|
| 当前沙箱 `/workspace` | 空 |
| 全盘 `find`（`run_compare5.py` / `creativity_lab` / `adhd_repro`） | 0 命中 |
| drive 关键词检索（`对比`/`实验`/`py`/`比较`/`cmp`/`写作`/`恢复`/`CMP8`/`RECOVERY`） | 命中的全是 md 报告，**没有 cmp8 的任何文件** |
| drive 的 `generated/` 目录树 | 只有图片生成物，不是工作区镜像 |
| GitHub（`lixvanran/*` 全部仓库 + 代码检索 `run_compare5`） | 无 |
| 三组公开仓 `agent-creativity-mechanism-study` | 只有 `ops/verify/client/metrics` 等 4 个同名文件，**没有** `orclient/adhd_repro/learnarch`，**没有** `data/user4_q*` |
| 其它并行会话的沙箱 | 也没有（同一个共享挂载，一起被重置） |

⇒ **结论：cmp8 这条实验线从未进入 drive，源文件只存在于已被重置的沙箱。**

## 3. 实际怎么救回来的

原会话（`451241289920777`「ADHD与Agent创造力」）在沙箱重置前，
已把自己的工作成果**重写成三个自包含的还原脚本**（每个脚本内部用 `FILES = {...}`
把完整文件正文内嵌进去，跑一次就把整棵树写出来）：

| 脚本 | 内容 |
|---|---|
| `cmp8_p0.py` | 4 个依据包（`user4_q1..q4.json`）+ `__init__.py` |
| `cmp8_p1.py` | 核心库 7 件（client / metrics / verify / ops / orclient / learnarch / adhd_repro） |
| `cmp8_p2.py` | 驱动 6 件 + 臂依赖 3 件 + 学到的权重 + 原始 README |

打包方（本会话）拿到这三个脚本后：
`python3 cmp8_p0.py && python3 cmp8_p1.py && python3 cmp8_p2.py` → 生成 `cmp8/` 树 →
**修 4 个 bug**（§4）→ 探通判官通道（§5）→ 重排目录 → 写 README → 打包 → 解压复检。

## 4. 打包时修掉的 4 个 bug（都是"静默测错东西"型）

### 4.1 `cmp8_p0.py` 少一个收尾的 `'''` ⇒ 脚本直接 SyntaxError

`FILES["cmp8/creativity_lab/__init__.py"] = r'''` 之后没有收尾
（全文只有 9 个三引号，应为 10 个）：

```
File "cmp8_p0.py", line 75
    '''
    ^
SyntaxError: unterminated triple-quoted string literal (detected at line 82)
```

⇒ **这个包在别人机器上根本跑不起来**（第一步就 SyntaxError）。

### 4.2 `creativity_lab/learnarch.py` 用了 `time.sleep` 却没 `import time`

第 67 行 `time.sleep(3 + attempt * 4)`（embedding 失败后的退避重试路径），
但文件顶部只 import 了 `os/re/random/sys`。
⇒ **只在这条异常路径上触发**：embedding 失败时抛的是 `NameError` 而不是 `RuntimeError`，
错误信息会指向一个完全无关的地方，排查成本极高。已补 `import time`。

### 4.3 `armdeps/topics4.py` 原本是死文件

题面（`TOPICS4`）内联在 `run_compare5.py` 里，`armdeps/topics4.py` 则是同一份内容的独立副本 ——
**两份各改一处就会跑偏**。已改为：`topics4.py` 作单一真相源，
`run_compare5.py` 优先 `from topics4 import TOPICS4`，读不到才回退到内联副本。
`topics4.py` 是**真文件**，含 4 道题定义 + `__main__` 可直接打印。

### 4.4 ★ OpenRouter 的 404/403 被当成 `other` ⇒ 静默重试后 `return ""`

`orclient.classify()` 原来只区分 `429 / 402 / 401+403 / 5xx / other`。
**模型下架（404）与供应商封禁（403）全落进 `other`** ⇒ 每次 `sleep(3)` 重试 4 次
⇒ 最后 `return ""` —— **调用方拿到空字符串，却没有任何错误信息**。
一次模型下架就能让整套实验**静默产出 0 字符**（这正是第一次冒烟看到的现象）。

修法：
1. `classify` 新增 `gone`(404) / `forbidden`(403)，`auth` 只留 401；
2. `chat()` 遇 `gone/forbidden` **立刻换下一个模型**（不在同一模型上空转）；
3. 全部模型都失败时**抛错并带上原因**（模型名 + 最后一次错误），不再返回空串；
4. 默认判官/embedding 模型换成实测可用的（§5）；
5. 新增 `Embedder`：OpenRouter embedding 失败自动退 MiniMax `embo-01`，
   实际通道记进 `analysis.json` 的 `embed` 字段；
6. `analyze_cmp6.py` 记录 `judge` / `judge_used` / `judge_same_vendor` / `embed` / `census`，
   判官退到 MiniMax（同源）时打大字警告。

## 5. OpenRouter 通道：根因与实测（2026-10-20）

第一次冒烟：chat 返 0 字符、embedding 报 `provider Terms Of Service violation`。
逐个探针查完 ⇒ **不是 key、不是账号、不是 IP**：

| 探针 | 结果 |
|---|---|
| `GET /key` | ✅ 健康（`limit_remaining 4.999 / 5`） |
| `GET /credits` | ✅ 健康（账号 $20，用 $9.75） |
| `x-ai/grok-3-mini`（原默认判官） | ❌ **404 已下架** → xAI 建议改用 `grok-4.3` |
| `x-ai/grok-4-fast` / `grok-3` / `grok-2-1212` | ❌ 404 下架 / 无 endpoint |
| `openai/text-embedding-3-small`（原默认 embedding） | ❌ **403 ToS** |
| `openai/gpt-4o-mini` / `google/gemini-2.5-flash` | ❌ 403 区域限制 |
| `google/gemini-embedding-001` | ❌ 403 ToS |
| `deepseek/deepseek-chat` | ✅ $0.26/$1.03 每 M |
| `x-ai/grok-4.3` | ✅ $1.25/$2.50 每 M |
| `qwen/qwen3.7-plus` / `z-ai/glm-4.5` / `meta-llama/llama-3.3-70b-instruct` | ✅ |
| `qwen/qwen3-embedding-8b` | ✅ 4096 维（另有 4b / bge-m3 / all-minilm-l6-v2） |

**判官自检（真闸门）**：

```
判官 deepseek/deepseek-chat ：真断言 4/4 ｜ 假断言 4/4   ✅
判官 x-ai/grok-4.3          ：真断言 4/4 ｜ 假断言 4/4   ✅
```

⇒ 判官可用，闸门已过。默认判官设为 `deepseek/deepseek-chat`（最便宜），
`x-ai/grok-4.3` 同样通过自检、想换只改 `OR_PRIMARY`。

⚠️ **口径警告**：去重阈值 0.75 标定在 MiniMax `embo-01` 上；换 embedding 模型
⇒ 「宽度 / 去重宽」不可跨模型比较。`analysis.json` 会记 `embed` 字段，报告须一并写出。

## 6. 重建带来的已知差异（必须知道）

1. **不是逐字节原版**。重建依据是原会话当时的工作记忆与设计文档，
   函数签名、prompt 措辞、常量都可能与原版有出入。
   ⇒ 跑出来的数字**用于方向性判断可以，当精确复现不行**。
2. **一处有意改动**：`creativity_lab/verify.py` 的 CHECK4 第一步，
   原本问「这条陈述是不是**法律主张**」—— 那个问法在非法律域（本题 4 道题都不是法律域）
   会把含题面数字的陈述误判成「复述题面」→ 判成非主张。已泛化为
   「可核验的事实性断言」，判据是「只要陈述里含有超出问题本身的信息
   （数字/阈值/名称/规则/主体关系）就当它是断言」。
   泛化后**法律域回归 27/27 保住、矛盾召回仍 9/9 = 100%**。
3. **依据包的完整 URL 清单没随包走**。每题 `sources` 只保留了主来源域名 + 日期；
   逐条 URL 在原会话的原始 JSON 里（随沙箱丢失）。→ **要审 oracle 的来源，需重新联网核一遍**。
4. **`runs/arch_learn/result.json` 随包附上**（不在最初清单里）：
   那是**学到的 14 维策略权重**，A5b 臂直接读它，**没有它 A5b 就没意义**。
5. **`/workspace/adhd-repo` 这条绝对路径保留**在 `run_compare5.py` 里（`ADH_REPO` 默认值），
   只给 `ADH_MODE=node` 用；本包默认 `ADH_MODE=repro`（Python 复刻），用不到。

## 7. 自检记录（打包时跑的）

```
py 文件 16 个；语法错误 0
依据包 Q1/Q2/Q3/Q4 evidence 字符数：1177 / 1093 / 1739 / 1772（JSON 全部合法）
权重 w：14 维
import 链：client2 / arm3 / shared / topics4 + creativity_lab.{client,metrics,verify,ops,orclient,learnarch,adhd_repro} 全部可导入
arm3.FRAMES=7, arm3.PERSONAS=5；TOPICS4=[A1,A2,A3,A4]
run_compare5.py --help 正常
判官自检：deepseek 4/4+4/4，grok-4.3 4/4+4/4
unzip -t: No errors detected
```

## 8. 如果你手上还有原件

如果你在别的机器 / 旧沙箱快照 / 本地 git 里还留着 cmp8 的原始文件，
**用原件覆盖本包里的对应文件**再跑一次 —— 本包是"能跑"的重建版，原件是"原汁原味"版，
两者的差异就是上面 §6 那几条。
