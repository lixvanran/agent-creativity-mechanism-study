# 第四组 · 交付物校验台账（sha256 绑 commit）

**校验基准 commit**：`8aea548494612ff62451291e6d9eac44d2c4f4ab`（分支 `feature/g4-arch4-state-driven`，`main` 未动）
**生成时间**：由 `group4_state_driven/build_shasums.py` 自动生成

> ⚠️ **为什么必须有本文件**：sha256 随文件修改失效。2026-10-24 12:0x 我们把 `REPORT_arch5.md` 的
> 旧版 sha256（`b61345b0…`，对应 `5de1a6b`）报给了主会话，而该文件在 `4b90e11` 已改过 ⇒
> 远端与本地都是新版 `871aa4cf…` ⇒ ⇒ **同一个 sha256 在不同 commit 下指向不同内容**。
> ⇒ ⇒ **对外一律以「sha256 + 基准 commit」成对给，不许只报 sha256。**
>
> ★ **外部复核命令**：
> ```bash
> git fetch origin feature/g4-arch4-state-driven
> git checkout 8aea54849461
> sha256sum <路径>   # 与下表比对
> ```

---

| 文件 | 仓库路径 | sha256 | 基准 commit |
|---|---|---|---|
| Stage-1 报告 | `group4_state_driven/REPORT_arch6_stage1.md` | `c9e27b811f240134f50927615e7d4e99bbeca580d43524067bb30ca2587ceadf` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 EXEC-LOG | `group4_state_driven/EXEC_LOG_stage1.md` | `18585e34c0a15a53f46fd81bea1884d4b26d86f6810ce6eec5902d3e8751f526` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 原始样本 | `group4_state_driven/data/arch6_stage1.jsonl` | `ce246afc2849fa1b3ddd87a457f94cae45f0c28c009b7f1bbd899fc96edc8be3` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 分析输出 | `group4_state_driven/data/arch6_stage1_analysis.json` | `c8d1d7f69440c1217407cd732b35f5058b9b8eb3c0fdd02e65e46f749c05fab5` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 calllog（★ 已知不完整） | `group4_state_driven/data/calllog.jsonl` | `0001d2b8f6b77d3c0be593a36dd03aabc74bfcee42feae1cb4e098a4c0381f28` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 环境快照 | `group4_state_driven/data/env_snapshot.json` | `bf60d9aa117d251d1611546d19d0b01b30699671f5e8165a430957f62637ea07` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| 重复采样留痕 | `group4_state_driven/data/duplicate_resampling.json` | `bd2779862a98824c9d43c14cd335286ed3c99df5364de91a2973b9e4e05a8504` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| ★ 重标记前原始样本（★ 独立采样判据的证据） | `group4_state_driven/data/arch6_stage1.pre_dedup.jsonl` | `bdcc36f3f7a6ff5cdbc47674b4d2e1ba66e7eecd6c9f9876f12ba577dbc17935` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| 状态层接口（★ ★ 第二组 rev2 · 现行） | `creativity_lab/state_layer.py` | `b70bfb0beb2bd591dd2795e109788dc85bcf306ef68ed25b64da17e0c5a41d0e` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| ★ 状态层 rev0 归档（★ 历史版） | `group4_state_driven/data/state_layer_versions/state_layer_rev0.py` | `38795bf6adfdee05d5a2588294399d844c6a99cc14d5ce2fa32c1662a6afa37e` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| ★ 状态层 rev1 归档（★ 历史版） | `group4_state_driven/data/state_layer_versions/state_layer_rev1.py` | `69a29c506a4e4ab0cd2595a23bfc47596709c0a184e0f833e494d27f0c28b373` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| 状态层规格测试（★ 第四组实现 · ★ rev2 语义） | `creativity_lab/experiments/test_state_layer.py` | `8eb57ed8e30a49364b915528adff5dcfa2a101c1cc9ab41fb95d9646d1d1c360` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| 状态层差异探针（★ ★ 三版本差分） | `group4_state_driven/probe_state_layer_spec_gap.py` | `7ec4c7b95ccb07c2bab2897aabbcfc50464522f2dbf10c0f357956012fe1bb49` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| ★ Stage-1 独立采样判据 | `group4_state_driven/check_independent_samples.py` | `215f02a3546c68ec18a10ddc485afba7edeb458670bb042d5e3bbe62b9ac23ba` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| ★ Stage-2 候选分化判据（★ 事前规格） | `group4_state_driven/prereg/STAGE2_CANDIDATE_DIVERSIFICATION_SPEC.md` | `307f8d936331b94b320f0fc75574690b59073f78728222f475946266f34b7719` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| rev1 应用脚本 | `group4_state_driven/apply_state_layer_rev1.py` | `0a8253f65a8c81d56c63406f189ddb02fb6f4021a4bedd2aa9d920cf8066552a` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| rev2 应用脚本 | `group4_state_driven/apply_state_layer_rev2.py` | `7578a00dd94bb8a86dcecc1a35953596eb20d6492eb161b4d32876dc143e1826` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 同步脚本 | `group4_state_driven/sync_stage1_data.py` | `5bdcea8229c92b0a56d923eb9f0dfe6d9504d0f68e8a8c3fd1703a970cbef99e` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 重复采样处置 | `group4_state_driven/fix_duplicate_resampling.py` | `cf677e812bb3db17c2100902553fb7446cccf598a48abed416df0f8e92562d25` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 报告填数（§3） | `group4_state_driven/fill_report_stage1.py` | `3b30589132aae398b1aafd7e4ef01d46d3447d35de69d0537f31d48205a0eb79` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 报告填数（§4–§6） | `group4_state_driven/fill_report_stage1_verdict.py` | `9e1b0be03bd1a2b55d647471a6583b713bbc23ca0f00489dd3a76ad7de4e5fc0` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 报告校验器 | `group4_state_driven/verify_report_stage1.py` | `1746be23f4b3af78c236d1e8c67c19707d46b5111bd84ca0623ec37aeb92f433` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 逐步打点探针 | `group4_state_driven/probe_stage1_step_timing.py` | `61ecc07b790b0d0c4e3f983fb14d97449d75e454f9eed2dc958db50d498bbf11` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| 工作包三（★ 降级为实现/读数侧） | `group4_state_driven/WORKPACK3_MIN_ARCHITECTURE.md` | `78083285565bf452b21828de474cc41e2a5f6f6f5ba15af6c2eae754fddea158` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| 状态层边界枚举冒烟 | `group4_state_driven/probe_select_boundary.py` | `268f1bc682743edce9a388262991b08c71e02c4a61effde7c6347bfdf55e60ba` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| v6 机制层实现 | `group4_state_driven/code/workflow_arch6.py` | `902e93861b99060feecc3b3ae1b476376a5225b4b2fd9f7758c9e5c8d9e8acbd` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| v6 Stage-1 runner | `group4_state_driven/code/run_arch6_stage1.py` | `8a17f4277bf1e1ef60ce5faffe27296f3d3eb6fee428f2caf86993f8c8133ea8` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| v6 Stage-1 分析 | `group4_state_driven/code/analyze_arch6.py` | `10740413dc108f1fd8928aad5d1ced4b91eeddbacb07551adbf0e7d6f3b55d63` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| v6 预注册 v3 | `group4_state_driven/prereg/PREREG_v6.md` | `31c81dfc8ddf68a3cf8cd777a371683f58e4106935cecaa5cd747757c2befcfb` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| Stage-1 实施规格 | `group4_state_driven/prereg/STAGE1_SPEC.md` | `7d4db8a2705ec07321b411df94c48e5e8a819510d27353523a3fad74f339fb19` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |
| 论文稿 | `group4_state_driven/paper/PAPER_draft.md` | `a3a0b5e867aa1648c11773a2757d612605d4653f08cfbb7510490b2440582d81` | `8aea548494612ff62451291e6d9eac44d2c4f4ab` |

---

★ **本表共 31 项**（★ 缺文件会显式标 ⚠️，★ 不会被静默跳过）

## ★ 已知缺口（★ 必须随表一起给，★ 不许只给 sha）

| ★ 项 | ★ 说明 |
|---|---|
| ★ **`calllog.jsonl` 不完整** | ★ 补跑段的调用未落盘（★ 进程在 `dump_calllog()` 之前被终止）⇒ ★ **通道健康度的分母不完整** ⇒ ★ **凡用 calllog 算健康度的结论本批不成立**（★ 详见 `EXEC_LOG_stage1.md` §1.4） |
| ★ **seed 未落盘** | ★ runner 里 `rec["seed"] = None` ⇒ ★ **本批不可按 seed 复现** |
| ★ **重复采样已处置** | ★ T10-1 出现两次（★ 两个进程并发写）⇒ ★ 后写入者重标记为 T10-2 ⇒ ★ **每题恰好 3 个重复** ⇒ ★ 留痕 `data/duplicate_resampling.json` |
| ★ **状态层接口 = rev1** | ★ sha `69a29c506a4e4ab0…`；★ **rev2（detect_tie 返回所有并列簇）尚未落地**（★ 第四组按语义重写后 sha 不符 ⇒ ★ 已回滚 rev1 ⇒ ★ **待第二组给逐字原文**） |
| ★ **`REPORT_arch6_stage1.md` 的数字** | ★ 全部由 `fill_report_stage1*.py` 从 `arch6_stage1_analysis.json` 填入 ⇒ ★ **不许手改** ⇒ ★ 改完必跑 `verify_report_stage1.py`（★ 69 项机械校验） |
