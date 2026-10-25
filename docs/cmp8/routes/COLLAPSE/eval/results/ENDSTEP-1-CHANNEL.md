# 表1 · 通道健康（分母齐全）

> 源：`runs/endstep-matrix-2026-10-23/manifest.json`｜生成：`creativity_lab/experiments/build_endstep_tables.py`


| 项 | 值 |
|---|---:|
| n_groups | 9 |
| n_valid | 9 |
| n_channel_failed | 0 |
| n_calls_total | 58 |
| n_calls_failed | 3 |
| n_calls_truncated | 2 |
| n_calls_empty | 3 |
| channel_health | 0.9483 |
| model | MiniMax-M3 |
| effort | medium |
| thr | 0.3 |
| seed_base | 20261023 |
| 分支型号池 | MiniMax-M3, MiniMax-M3.1-Flash-Preview, MiniMax-M2.7, MiniMax-M2.5, MiniMax-M2.7-highspeed, MiniMax-M2.5-highspeed |
| **已下架型号（被剔除）** | MiniMax-M2.1, MiniMax-M2, MiniMax-M2.1-highspeed |

> ★ **下架型号必须显式剔除**：M2.1 / M2 / M2.1-highspeed 实测 404 ⇒
> 死分支会被**静默丢弃** ⇒ 发散层 5 支变 4 支 ⇒ **分母漂移而表看不出来**。

