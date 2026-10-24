# ★ 交稿读数快照（★ 拓扑臂 v2 · n=151/360 · ★ 2026-10-24 ★）

> ★ **这个目录是什么**：★ 交稿版报告 `docs/交付/第二组交付报告_2026-10-24.md` 的 §6.10–§6.12 所引用的**全部原始读数**的**逐字节副本** ★
> ★ **为什么在这里单独放一份**：★ 批的原始数据在 `runs/topo-arm-v2-2026-10-24/`（★ 被 `.gitignore` 排除 ⇒ ★ **不在交付包内** ★）⇒ ⇒ ★ 若不放副本，★ **外部拿到交付包将无法复算 §6.10 的任何一个数** ⇒ ⇒ ★ 这是「★ 交付包内引用路径必须与实际结构一致 ★」那条纪律的一个实例 ★
> ★ **副本与源的关系**：★ 逐字节一致（★ sha256 已逐个核过 ★）⇒ ★ **副本即原件的可复核凭证** ★

## 一、快照口径

| 项 | 值 |
|:-:|---|
| ★ 快照批次 | ★ 拓扑臂 v2 · ★ **n = 151 / 360** 单元（★ 题 S4、S5、S6；★ 每题 2 rep；★ 6 臂；★ 每组 5 份综述后 proposal ★）★ |
| ★ 冻结时刻 | ★ 机器 UTC **2026-10-24T10:09Z** ｜ 叙事日期 2026-10-24 |
| ★ θ₀（当前实现口径） | ★ **1.339σ**（★ vendi σ = 0.2248；★ H0 配对 n = 12 ★）★ |
| ★ **限流边界** | ★ chat 通道的 429 限流起始于 **10:14:54 UTC**，★ **晚于**本快照 ⇒ ★ **本快照不受限流影响** ★ |

## 二、文件清单（★ 每个文件的用途）

| 文件 | 用途 |
|---|---|
| ★ `partial_verdict.json` | ★ 主读数（★ 三个单因子对比的逐格标准化效应量、题级方向、★ H0 统计量 ★）★ |
| ★ `h0_theta0_multicalib.json` | ★ **θ₀ 四口径重算 + 判决影响量化**（★ §6.10.2b 的全部数字来源 ★）★ |
| ★ `f1c_leverage.json` | ★ 位置基线与「污染单元是否属内容依赖」的判据读数（★ §6.12.3 / §6.12.7 ★）★ |
| ★ `recompute_excluding.json` | ★ 剔除污染单元后的重算（★ 污染率、脆弱格、题级影响 ★）★ |
| ★ `morphology_control.json` | ★ 形态受控性表（★ 截断率 / 无内容率 / think 未闭合率 / 长度中位 ★）★ |
| ★ `channel_status.json` | ★ 通道状态与批状态（★ chat 429 / 嵌入 1008 / 单元级失败独立重算 ★）★ |
| ★ `UNITS-n151.txt` | ★ **本版读数基于哪些单元的清单**（★ 151 个 basename，★ sha256 `a3f19d35…` ★）★ |
| ★ `SNAPSHOT-partial_verdict-n151-2026-10-24.json` | ★ 主读数的冻结副本（★ sha256 `a412f4ac…` ★）★ |
| ★ `SNAPSHOT-h0_theta0_multicalib-n151-2026-10-24.json` | ★ 多口径重算的冻结副本（★ sha256 `26c4e349…` ★）★ |
| ★ `SNAPSHOT-n151-2026-10-24.json` | ★ 单元清单的冻结副本（★ sha256 `a3f19d35…` ★）★ |
| ★ `SNAPSHOT-REGISTRY.json` | ★ 快照登记簿（★ 顶层=最新，★ `history` 里是历史快照 ★）★ |

## 三、怎么独立复算（★ 三条命令，★ 全部零生成调用 ★）

```bash
# ① §6.10.2b 的逐格核对（★ 结构化核对 + 自带 3 个变异注入自测 ★）
python3 -B creativity_lab/experiments/verify_multicalib_section.py \
    --report docs/交付/第二组交付报告_2026-10-24.md \
    --json   docs/交付/读数快照/topo-arm-v2-n151/h0_theta0_multicalib.json
python3 -B creativity_lab/experiments/verify_multicalib_section.py --self-test

# ② 报告里其余数字与数据的一致性（★ 48 项 ★）
python3 -B creativity_lab/experiments/crosscheck_report.py docs/交付/第二组交付报告_2026-10-24.md

# ③ 报告的填充脚本重跑（★ 幂等：★ 两遍应逐字节一致 ★）
python3 -B creativity_lab/experiments/fill_report_partial.py \
    --report docs/交付/第二组交付报告_2026-10-24.md \
    --json           docs/交付/读数快照/topo-arm-v2-n151/partial_verdict.json \
    --morph-json     docs/交付/读数快照/topo-arm-v2-n151/morphology_control.json \
    --snapshot-json  docs/交付/读数快照/topo-arm-v2-n151/SNAPSHOT-REGISTRY.json \
    --f1c-json       docs/交付/读数快照/topo-arm-v2-n151/f1c_leverage.json \
    --excl-json      docs/交付/读数快照/topo-arm-v2-n151/recompute_excluding.json \
    --multicalib-json docs/交付/读数快照/topo-arm-v2-n151/h0_theta0_multicalib.json \
    --channel-json   docs/交付/读数快照/topo-arm-v2-n151/channel_status.json
```

★ ★ **★ 注意：★ 上面的复算【不需要嵌入通道】★（★ 只读已落盘的 json，★ 不重新算 embedding ★）★★**
★ ⇒ ★ **在 `embo-01` 余额耗尽期间，★ 交稿读数的复核仍然完全可做** ★★

## 四、★ 不在交付包内的东西（★ 透明上报 ★）

| 项 | 为什么不在 | 后果 |
|---|---|---|
| ★ `runs/topo-arm-v2-2026-10-24/units/`（★ 151 个单元的原始产出 ★） | ★ `.gitignore` 排除了 `runs/` ⇒ ★ 包按 `git ls-files` 取文件 ★ | ★ **外部无法从头重算读数**，★ 只能复核本目录里的读数副本 ⇒ ★ **交稿读数的可复核性 = 本目录的完整性** ★ |
| ★ 批的 `calllog.jsonl` | ★ **批未跑完** ⇒ ★ 该文件是【收尾聚合物】⇒ ★ 运行期不存在 ★ | ★ 健康度仍可从 `units/*.json` 内联的 `calls` **独立重算** ⇒ ★ 不影响健康度可核性 ★ |

★ ★ **★ 一条元教训（★ 值得写进交付说明 ★）★★**
> ★★★ **★ 「读数可复核」有两层：★ ①【读数本身可被独立重算】★ ②【重算所需的原料在包内】★★**
> ★ ⇒ ★ **只有第 ① 层时，★ 交付包里的数字其实是【不可复核的】★** ⇒ ⇒ ★ **交稿前必须问：★ 「外部拿到这个包，★ 能不能重跑我的分析？」★** ⇒ ⇒ ★ **答不上来 ⇒ ★ 那就要么把原料放进去，★ 要么在交付说明里明写「原料不在包内」★★**
