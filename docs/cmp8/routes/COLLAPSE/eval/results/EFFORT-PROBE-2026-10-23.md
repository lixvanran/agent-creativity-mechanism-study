# effort 档位探针（判官通道可靠性 × 判官质量）

> **程序化生成**（`build_evidence_tables.py`）｜源：`runs/dev/effort_probe/effort_probe.json`

> 判官 `MiniMax-M3.1-Flash-Preview` ｜ 调用 `CARD_Q_OUT`（OUT 通道真实卡片调用）


## 轴1 · 结果级健康

| 答案 | effort | 调用 | 解析出卡 | 断言 | parsefail | parsefail率 |
|---|---|--:|--:|--:|--:|--:|
| B0_direct#D01 | **low** | 2 | 7 | 14 | 7 | **0.50** |
| B0_direct#D01 | **max** | 2 | 14 | 14 | 0 | **0.00** |
| B0_direct#D01 | **medium** | 2 | 14 | 14 | 0 | **0.00** |
| W_div#D01 | **low** | 2 | 16 | 16 | 0 | **0.00** |
| W_div#D01 | **max** | 2 | 8 | 16 | 8 | **0.50** |
| W_div#D01 | **medium** | 2 | 16 | 16 | 0 | **0.00** |

## 轴2a · 跨轮一致

| 答案 | effort | 轮 | 卡数 | 一致 |
|---|---|--:|--:|:-:|
| B0_direct#D01 | low | 1 | 7 | ✔ |
| B0_direct#D01 | low | 2 | 0 | ✔ |
| B0_direct#D01 | max | 1 | 7 | ✔ |
| B0_direct#D01 | max | 2 | 7 | ✔ |
| B0_direct#D01 | medium | 1 | 7 | ✔ |
| B0_direct#D01 | medium | 2 | 7 | ✔ |
| W_div#D01 | low | 1 | 8 | ✔ |
| W_div#D01 | low | 2 | 8 | ✔ |
| W_div#D01 | max | 1 | 0 | ✔ |
| W_div#D01 | max | 2 | 8 | ✔ |
| W_div#D01 | medium | 1 | 8 | ✔ |
| W_div#D01 | medium | 2 | 8 | ✔ |

## 轴2b · 与 max 档一致（质量有没有退化）

| 答案 | effort | 轮 | 本档卡数 | max 卡数 | 一致 |
|---|---|--:|--:|--:|:-:|
| B0_direct#D01 | low | 1 | 7 | 7 | ✔ |
| B0_direct#D01 | low | 2 | 0 | 7 | ✘ |
| B0_direct#D01 | medium | 1 | 7 | 7 | ✔ |
| B0_direct#D01 | medium | 2 | 7 | 7 | ✔ |
| W_div#D01 | low | 1 | 8 | 0 | ✘ |
| W_div#D01 | low | 2 | 8 | 8 | ✘ |
| W_div#D01 | medium | 1 | 8 | 0 | ✘ |
| W_div#D01 | medium | 2 | 8 | 8 | ✘ |
