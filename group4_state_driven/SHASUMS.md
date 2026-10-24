# 第四组 · 交付物校验台账（sha256 绑 commit）

**校验基准 commit**：`21984e002f209600affcaca5e2307f0d0356218d`（分支 `feature/g4-arch4-state-driven`，`main` 未动）
**生成时间**：由 `group4_state_driven/build_shasums.py` 自动生成

> ⚠️ **为什么必须有本文件**：sha256 随文件修改失效。2026-10-24 12:0x 我们把 `REPORT_arch5.md` 的
> 旧版 sha256（`b61345b0…`，对应 `5de1a6b`）报给了主会话，而该文件在 `4b90e11` 已改过 ⇒
> 远端与本地都是新版 `871aa4cf…` ⇒ ⇒ **同一个 sha256 在不同 commit 下指向不同内容**。
> ⇒ ⇒ **对外一律以「sha256 + 基准 commit」成对给，不许只报 sha256。**
>
> ★ **外部复核命令**：
> ```bash
> git fetch origin feature/g4-arch4-state-driven
> git checkout 21984e002f20
> sha256sum <路径>   # 与下表比对
> ```

---

| 文件 | 仓库路径 | sha256 | 基准 commit |
|---|---|---|---|
| Stage-1 报告 | `group4_state_driven/REPORT_arch6_stage1.md` | `c9e27b811f240134f50927615e7d4e99bbeca580d43524067bb30ca2587ceadf` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 EXEC-LOG | `group4_state_driven/EXEC_LOG_stage1.md` | `c3386d47d568411b3fd88695fa463d9d2dfb0d52e32dd68fc625327e9f5d3f83` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 原始样本 | `group4_state_driven/data/arch6_stage1.jsonl` | `ce246afc2849fa1b3ddd87a457f94cae45f0c28c009b7f1bbd899fc96edc8be3` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 分析输出 | `group4_state_driven/data/arch6_stage1_analysis.json` | `867ffc46fb5c6e033deb882263c64606ff61f9148544dc0fb93bac940a20867c` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 calllog（★ 已知不完整） | `group4_state_driven/data/calllog.jsonl` | `0001d2b8f6b77d3c0be593a36dd03aabc74bfcee42feae1cb4e098a4c0381f28` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 环境快照 | `group4_state_driven/data/env_snapshot.json` | `bf60d9aa117d251d1611546d19d0b01b30699671f5e8165a430957f62637ea07` | `21984e002f209600affcaca5e2307f0d0356218d` |
| 重复采样留痕 | `group4_state_driven/data/duplicate_resampling.json` | `bd2779862a98824c9d43c14cd335286ed3c99df5364de91a2973b9e4e05a8504` | `21984e002f209600affcaca5e2307f0d0356218d` |
| 状态层接口（★ 第二组 rev1） | `creativity_lab/state_layer.py` | `69a29c506a4e4ab0cd2595a23bfc47596709c0a184e0f833e494d27f0c28b373` | `21984e002f209600affcaca5e2307f0d0356218d` |
| 状态层规格测试（★ 第四组实现） | `creativity_lab/experiments/test_state_layer.py` | `d4f5da0d96b8b6cd5c8eac6be5585617f83548b254531ade3e2d04fc119c09d4` | `21984e002f209600affcaca5e2307f0d0356218d` |
| 状态层差异探针（★ 双版本差分） | `group4_state_driven/probe_state_layer_spec_gap.py` | `0d184c1fc8a3922438060409f578587ec99aeee37e874049f72ef2d2bfdd584c` | `21984e002f209600affcaca5e2307f0d0356218d` |
| rev1 应用脚本 | `group4_state_driven/apply_state_layer_rev1.py` | `0a8253f65a8c81d56c63406f189ddb02fb6f4021a4bedd2aa9d920cf8066552a` | `21984e002f209600affcaca5e2307f0d0356218d` |
| rev2 应用脚本 | `group4_state_driven/apply_state_layer_rev2.py` | `16becb420c41c3b562ab791249d3d9e1a482edd5ea361c3b16c699e9f51048d7` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 同步脚本 | `group4_state_driven/sync_stage1_data.py` | `5bdcea8229c92b0a56d923eb9f0dfe6d9504d0f68e8a8c3fd1703a970cbef99e` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 重复采样处置 | `group4_state_driven/fix_duplicate_resampling.py` | `cf677e812bb3db17c2100902553fb7446cccf598a48abed416df0f8e92562d25` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 报告填数（§3） | `group4_state_driven/fill_report_stage1.py` | `3b30589132aae398b1aafd7e4ef01d46d3447d35de69d0537f31d48205a0eb79` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 报告填数（§4–§6） | `group4_state_driven/fill_report_stage1_verdict.py` | `9e1b0be03bd1a2b55d647471a6583b713bbc23ca0f00489dd3a76ad7de4e5fc0` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 报告校验器 | `group4_state_driven/verify_report_stage1.py` | `cdf2a9b9d9aae76ef0a45446f9c9c64965fe80e45341a5dfeb6eb6530a67604e` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 逐步打点探针 | `group4_state_driven/probe_stage1_step_timing.py` | `61ecc07b790b0d0c4e3f983fb14d97449d75e454f9eed2dc958db50d498bbf11` | `21984e002f209600affcaca5e2307f0d0356218d` |
| 工作包三（★ 降级为实现/读数侧） | `group4_state_driven/WORKPACK3_MIN_ARCHITECTURE.md` | `4219984124649b8d3cd09cac911e970a3baa49c8d437b0ae5f350749d642aeb9` | `21984e002f209600affcaca5e2307f0d0356218d` |
| 状态层边界枚举冒烟 | `group4_state_driven/probe_select_boundary.py` | `268f1bc682743edce9a388262991b08c71e02c4a61effde7c6347bfdf55e60ba` | `21984e002f209600affcaca5e2307f0d0356218d` |
| v6 机制层实现 | `group4_state_driven/code/workflow_arch6.py` | `902e93861b99060feecc3b3ae1b476376a5225b4b2fd9f7758c9e5c8d9e8acbd` | `21984e002f209600affcaca5e2307f0d0356218d` |
| v6 Stage-1 runner | `group4_state_driven/code/run_arch6_stage1.py` | `8a17f4277bf1e1ef60ce5faffe27296f3d3eb6fee428f2caf86993f8c8133ea8` | `21984e002f209600affcaca5e2307f0d0356218d` |
| v6 Stage-1 分析 | `group4_state_driven/code/analyze_arch6.py` | `78f7b359d388219f10733ff65e3d832b9ede536348f80dd855ed0dbc312f1f00` | `21984e002f209600affcaca5e2307f0d0356218d` |
| v6 预注册 v3 | `group4_state_driven/prereg/PREREG_v6.md` | `31c81dfc8ddf68a3cf8cd777a371683f58e4106935cecaa5cd747757c2befcfb` | `21984e002f209600affcaca5e2307f0d0356218d` |
| Stage-1 实施规格 | `group4_state_driven/prereg/STAGE1_SPEC.md` | `7d4db8a2705ec07321b411df94c48e5e8a819510d27353523a3fad74f339fb19` | `21984e002f209600affcaca5e2307f0d0356218d` |
| 论文稿 | `group4_state_driven/paper/PAPER_draft.md` | `a3a0b5e867aa1648c11773a2757d612605d4653f08cfbb7510490b2440582d81` | `21984e002f209600affcaca5e2307f0d0356218d` |

---

★ **本表共 26 项**（★ 缺文件会显式标 ⚠️，★ 不会被静默跳过）

## ★ 已知缺口（★ 必须随表一起给，★ 不许只给 sha）

| ★ 项 | ★ 说明 |
|---|---|
| ★ **`calllog.jsonl` 不完整** | ★ 补跑段的调用未落盘（★ 进程在 `dump_calllog()` 之前被终止）⇒ ★ **通道健康度的分母不完整** ⇒ ★ **凡用 calllog 算健康度的结论本批不成立**（★ 详见 `EXEC_LOG_stage1.md` §1.4） |
| ★ **seed 未落盘** | ★ runner 里 `rec["seed"] = None` ⇒ ★ **本批不可按 seed 复现** |
| ★ **重复采样已处置** | ★ T10-1 出现两次（★ 两个进程并发写）⇒ ★ 后写入者重标记为 T10-2 ⇒ ★ **每题恰好 3 个重复** ⇒ ★ 留痕 `data/duplicate_resampling.json` |
| ★ **状态层接口 = rev1** | ★ sha `69a29c506a4e4ab0…`；★ **rev2（detect_tie 返回所有并列簇）尚未落地**（★ 第四组按语义重写后 sha 不符 ⇒ ★ 已回滚 rev1 ⇒ ★ **待第二组给逐字原文**） |
| ★ **`REPORT_arch6_stage1.md` 的数字** | ★ 全部由 `fill_report_stage1*.py` 从 `arch6_stage1_analysis.json` 填入 ⇒ ★ **不许手改** ⇒ ★ 改完必跑 `verify_report_stage1.py`（★ 69 项机械校验） |
