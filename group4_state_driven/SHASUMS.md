# 第四组 · 交付物校验台账（sha256 绑 commit）

**校验基准 commit**：`2fb12c9bd674e379631b0629bbfc29fd26584ded`（分支 `feature/g4-arch4-state-driven`，`main` 未动）
**生成时间**：由 `group4_state_driven/build_shasums.py` 自动生成

> ⚠️ **为什么必须有本文件**：sha256 随文件修改失效。2026-10-24 12:0x 我们把 `REPORT_arch5.md` 的
> 旧版 sha256（`b61345b0…`，对应 `5de1a6b`）报给了主会话，而该文件在 `4b90e11` 已改过 ⇒
> 远端与本地都是新版 `871aa4cf…` ⇒ ⇒ **同一个 sha256 在不同 commit 下指向不同内容**。
> ⇒ ⇒ **对外一律以「sha256 + 基准 commit」成对给，不许只报 sha256。**
>
> ★ **外部复核命令**：
> ```bash
> git fetch origin feature/g4-arch4-state-driven
> git checkout 2fb12c9bd674
> sha256sum <路径>   # 与下表比对
> ```

---

| 文件 | 仓库路径 | sha256 | 基准 commit |
|---|---|---|---|
| Stage-1 报告 | `group4_state_driven/REPORT_arch6_stage1.md` | `d52cd51afc01d885058f30a3cc7164f5599fc1dc7b6e307a56e3a36f88bcd49c` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 EXEC-LOG | `group4_state_driven/EXEC_LOG_stage1.md` | `18585e34c0a15a53f46fd81bea1884d4b26d86f6810ce6eec5902d3e8751f526` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 原始样本 | `group4_state_driven/data/arch6_stage1.jsonl` | `ce246afc2849fa1b3ddd87a457f94cae45f0c28c009b7f1bbd899fc96edc8be3` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 分析输出 | `group4_state_driven/data/arch6_stage1_analysis.json` | `5f58ded35bcf379a5e84fbde00eecfe98bc64dc57635c920a080b821b6d032d6` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 calllog（★ 已知不完整） | `group4_state_driven/data/calllog.jsonl` | `0001d2b8f6b77d3c0be593a36dd03aabc74bfcee42feae1cb4e098a4c0381f28` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 环境快照 | `group4_state_driven/data/env_snapshot.json` | `bf60d9aa117d251d1611546d19d0b01b30699671f5e8165a430957f62637ea07` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| 重复采样留痕 | `group4_state_driven/data/duplicate_resampling.json` | `bd2779862a98824c9d43c14cd335286ed3c99df5364de91a2973b9e4e05a8504` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ 重标记前原始样本（★ 独立采样判据的证据） | `group4_state_driven/data/arch6_stage1.pre_dedup.jsonl` | `bdcc36f3f7a6ff5cdbc47674b4d2e1ba66e7eecd6c9f9876f12ba577dbc17935` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| 状态层接口（★ ★ 第二组 rev3 · 现行） | `creativity_lab/state_layer.py` | `c1c9224a1ed59fa8ca710713460df50c663236b345bcd2d138ca870d3bfd1c73` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ 状态层 rev0 归档（★ 历史版） | `group4_state_driven/data/state_layer_versions/state_layer_rev0.py` | `38795bf6adfdee05d5a2588294399d844c6a99cc14d5ce2fa32c1662a6afa37e` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ 状态层 rev1 归档（★ 历史版） | `group4_state_driven/data/state_layer_versions/state_layer_rev1.py` | `69a29c506a4e4ab0cd2595a23bfc47596709c0a184e0f833e494d27f0c28b373` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ 状态层 rev2 归档（★ 历史版） | `group4_state_driven/data/state_layer_versions/state_layer_rev2.py` | `b70bfb0beb2bd591dd2795e109788dc85bcf306ef68ed25b64da17e0c5a41d0e` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ rev3 应用脚本（★ 第二组提供） | `creativity_lab/experiments/apply_state_layer_rev3.py` | `f97d6fd40692c695fa1d2f863bdae3e0b34144ec674ab80567ad01b2cd55af7e` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ 状态层 rev2 归档（★ 历史版 · 补） | `group4_state_driven/data/state_layer_versions/state_layer_rev2.py` | `b70bfb0beb2bd591dd2795e109788dc85bcf306ef68ed25b64da17e0c5a41d0e` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ 第二组 pack_repo（★ 底层打包器） | `creativity_lab/experiments/pack_repo.py` | `4cc46c7864799e64c39c25c652f089e92cb59fe6bdb80162b7a588f41825976b` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ 第二组 unit_store | `creativity_lab/experiments/unit_store.py` | `25385ba6f991eb577f2592ca635955b7e4a2eaf418016b084516ec2a6f7966a7` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ 第二组 check_batch_progress | `creativity_lab/experiments/check_batch_progress.py` | `9c67e734b537772f591fab3fcee984a39b737ac2e649607343a0f9ba775f9e48` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ ★ 归档清单（★ 177 项全量 sha，★ 不抽样） | `group4_state_driven/archive/MANIFEST.sha256` | `82a4da56bd0e88f059f5b1701b9bf592dc43b9fc9c67524a48fac388dcb3d471` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ ★ 归档说明（★ 含三个坑） | `group4_state_driven/archive/README.md` | `d4d1b3282cb505940b5a9f4f35c619777c8b39c649900c39d2aaca3f5d8b027f` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ ★ 归档校验器 | `group4_state_driven/verify_archive.py` | `b0f100c7910faaea04c4b0101d174cefd798ee8a02e4bebd941408d334ff6e42` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ ★ Gate 语义与家族最优分析（★ 零 API） | `group4_state_driven/code/analyze_gate_semantics.py` | `c7eb371fa875f524da457e2a5e4d3bff7760642e565a26b7fc2b71a1416057a4` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ ★ 报告基线化 + 块标记迁移 | `group4_state_driven/migrate_report_base.py` | `7d8566f21e1a947cbafddd49cb01792c855191bbed2605bcdd1c1254782ec468` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ ★ 论文第二版填数（★ 数字全部由脚本填） | `group4_state_driven/fill_paper_v2.py` | `22710636016be40c720527a3b08ceca3087afcff78d9cd18845b17aafe8f9465` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ ★ 已知问题与待裁决项 | `group4_state_driven/KNOWN_ISSUES.md` | `4faa3577255d7d7d07a58a508214edab69a69bd91abc246717c339700a8c6cfb` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ ★ 预注册 v4（★ 含新读数端门） | `group4_state_driven/PREREG_v6.md` | `e99bc9898f024a633a4c6c8e5dc6cc2cc6482b5a41c2c0e727382a6b4d5899b7` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ ★ 报告基线（★ 含 FILL 块标记） | `group4_state_driven/REPORT_arch6_stage1.base.md` | `72d820d8c99ba210faa011790a6ea1bbc155122b8c2f3f39e1f06f3ee9e4c933` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ ★ 论文第二版 PDF（★ 28 页） | `group4_state_driven/PAPER_v2.pdf` | `311c2a07e2ba0afb1a8a2019b1dab2a7919be53be69f29d1c94b128278b5dc52` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| 状态层规格测试（★ 第四组实现 · ★ rev2 语义） | `creativity_lab/experiments/test_state_layer.py` | `82ad467c4c9af5290a8f112ce8ea0e6b6f9d48238cc003ece366b2a3d05a099e` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| 状态层差异探针（★ ★ 三版本差分） | `group4_state_driven/probe_state_layer_spec_gap.py` | `2f1798991f0fd73179baf916b3f5f3c4db6f13614c8990a770761584c6355846` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ Stage-1 独立采样判据 | `group4_state_driven/check_independent_samples.py` | `215f02a3546c68ec18a10ddc485afba7edeb458670bb042d5e3bbe62b9ac23ba` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ v6 源码级变异注入（★ 4/4） | `group4_state_driven/code/mutations_arch6.py` | `c9a79e8176d2563883e9732c77028a6417ce33632ad482dfc53b6ecc0a246f55` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ Stage-1 报告读数重填脚本 | `group4_state_driven/refill_report_stage1.py` | `6e53348e84ed7640e447d1d05bdbf49f87f9ed86007055291d6fa769bbf3668e` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ Stage-1 数据同步脚本（★ ★ 修路径错配） | `group4_state_driven/sync_stage1_data.py` | `f1558a86d13666131c97906ddf1b369804c59411689adca05d52a3558652498f` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| ★ Stage-2 候选分化判据（★ 事前规格） | `group4_state_driven/prereg/STAGE2_CANDIDATE_DIVERSIFICATION_SPEC.md` | `5a989e9dad30dfae25670b405dbe9b4026ee1728a71b4e5d7ae0e2f88a14651e` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| rev1 应用脚本 | `group4_state_driven/apply_state_layer_rev1.py` | `0a8253f65a8c81d56c63406f189ddb02fb6f4021a4bedd2aa9d920cf8066552a` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| rev2 应用脚本 | `group4_state_driven/apply_state_layer_rev2.py` | `7578a00dd94bb8a86dcecc1a35953596eb20d6492eb161b4d32876dc143e1826` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 同步脚本 | `group4_state_driven/sync_stage1_data.py` | `f1558a86d13666131c97906ddf1b369804c59411689adca05d52a3558652498f` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 重复采样处置 | `group4_state_driven/fix_duplicate_resampling.py` | `cf677e812bb3db17c2100902553fb7446cccf598a48abed416df0f8e92562d25` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 报告填数（§3） | `group4_state_driven/fill_report_stage1.py` | `f3667467e9f8e5c2d70e1dcdd7769121ec062e50f958c980031639ddfa1d12a6` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 报告填数（§4–§6） | `group4_state_driven/fill_report_stage1_verdict.py` | `9e1b0be03bd1a2b55d647471a6583b713bbc23ca0f00489dd3a76ad7de4e5fc0` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 报告校验器 | `group4_state_driven/verify_report_stage1.py` | `5ca5680b57027b03854d55b69cdf22a31adc9c278f6d7ac3880733fefe4d18e9` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 逐步打点探针 | `group4_state_driven/probe_stage1_step_timing.py` | `61ecc07b790b0d0c4e3f983fb14d97449d75e454f9eed2dc958db50d498bbf11` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| 工作包三（★ 降级为实现/读数侧） | `group4_state_driven/WORKPACK3_MIN_ARCHITECTURE.md` | `78083285565bf452b21828de474cc41e2a5f6f6f5ba15af6c2eae754fddea158` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| 状态层边界枚举冒烟 | `group4_state_driven/probe_select_boundary.py` | `268f1bc682743edce9a388262991b08c71e02c4a61effde7c6347bfdf55e60ba` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| v6 机制层实现 | `group4_state_driven/code/workflow_arch6.py` | `591421a2cabec649b41f97a29e761587bf0cc28febb5cf134a5a9eedcb8f794f` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| v6 Stage-1 runner | `group4_state_driven/code/run_arch6_stage1.py` | `8a17f4277bf1e1ef60ce5faffe27296f3d3eb6fee428f2caf86993f8c8133ea8` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| v6 Stage-1 分析 | `group4_state_driven/code/analyze_arch6.py` | `7979f9507706dd3010f3aaf230261095b0cee825dc6f5c8e85c464fdfacf9f4d` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| v6 预注册 v3 | `group4_state_driven/prereg/PREREG_v6.md` | `31c81dfc8ddf68a3cf8cd777a371683f58e4106935cecaa5cd747757c2befcfb` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| Stage-1 实施规格 | `group4_state_driven/prereg/STAGE1_SPEC.md` | `7d4db8a2705ec07321b411df94c48e5e8a819510d27353523a3fad74f339fb19` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |
| 论文稿 | `group4_state_driven/paper/PAPER_draft.md` | `a3a0b5e867aa1648c11773a2757d612605d4653f08cfbb7510490b2440582d81` | `2fb12c9bd674e379631b0629bbfc29fd26584ded` |

---

★ **本表共 50 项**（★ 缺文件会显式标 ⚠️，★ 不会被静默跳过）

## ★ 已知缺口（★ 必须随表一起给，★ 不许只给 sha）

| ★ 项 | ★ 说明 |
|---|---|
| ★ **`calllog.jsonl` 不完整** | ★ 补跑段的调用未落盘（★ 进程在 `dump_calllog()` 之前被终止）⇒ ★ **通道健康度的分母不完整** ⇒ ★ **凡用 calllog 算健康度的结论本批不成立**（★ 详见 `EXEC_LOG_stage1.md` §1.4） |
| ★ **seed 未落盘** | ★ runner 里 `rec["seed"] = None` ⇒ ★ **本批不可按 seed 复现** |
| ★ **重复采样已处置** | ★ T10-1 出现两次（★ 两个进程并发写）⇒ ★ 后写入者重标记为 T10-2 ⇒ ★ **每题恰好 3 个重复** ⇒ ★ 留痕 `data/duplicate_resampling.json` |
| ★ **状态层接口 = rev3** | ★ sha `c1c9224a1ed59fa8…`（★ **第二组 2026-10-25 落地**；★ 由 `creativity_lab/experiments/apply_state_layer_rev3.py` 应用 ⇒ ★ **sha 双向校验通过**）；★ rev0/rev1/rev2 全部归档在 `data/state_layer_versions/`（★ sha 绑 commit） |
| ★ **rev3 的 `tol` 是必填** | ★ `detect_tie(scores, *, tol)` ⇒ ★ **所有调用点必须显式传 `tol=`** ⇒ ★ 漏传【立刻 TypeError】⇒ ★ 不会静默用默认值 ⇒ ★ 读数不会漂 |
| ★ **历史批次原始产物已归档** | ★ v1–v5 的全部 `runs/`（★ 177 个文件 / 12.4 MB）★ **已入 git**（★ `group4_state_driven/archive/`）⇒ ★ 沙箱挂掉不再丢证据链；★ 全量清单见 `archive/MANIFEST.sha256`（★ **不抽样**）⇒ ★ 校验：`python3 -B group4_state_driven/verify_archive.py` |
| ★ **`REPORT_arch6_stage1.md` 的数字** | ★ 全部由 `fill_report_stage1*.py` 从 `arch6_stage1_analysis.json` 填入 ⇒ ★ **不许手改** ⇒ ★ 改完必跑 `verify_report_stage1.py`（★ 71 项机械校验） |
