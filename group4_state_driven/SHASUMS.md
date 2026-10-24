# 第四组 · 交付物校验台账（sha256 绑 commit）

**校验基准 commit**：`54e016c6293f4236b7b7dc5313976293be1c74ab`（分支 `feature/g4-arch4-state-driven`，`main` 未动）
**生成时间**：2026-10-24 12:1x（北京）

> ⚠️ **本文件存在的理由**：sha256 本身会随文件修改而失效。
> 2026-10-24 12:0x 我们把 `REPORT_arch5.md` 的旧版 sha256（`b61345b0…`，对应 `5de1a6b`）报给了主会话，
> 而该文件在 `4b90e11`（按三组「两种 0」自查的更正）已经改过 —— 远端与本地都是新版 `871aa4cf…`。
> ⇒ **同一个 sha256 在不同 commit 下指向不同内容** ⇒ ⇒ **今后一律以「sha256 + commit」为准，不许只报 sha256。**

---

| 文件 | 仓库路径 | sha256 | 基准 commit |
|---|---|---|---|
| `REPORT_arch5.md` | `group4_state_driven/reports/REPORT_arch5.md` | `871aa4cf0251a79c9cf14e33a89aadae4f49895290da77d439b981ff04a117e0` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `arch5_tables.md` | `group4_state_driven/data/arch5_tables.md` | `f8547d4fe0df185bf8b94a73da2de8c1fa12113cbf4bce5eab9b9aa78b2d1548` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `arch5_analysis.json` | `group4_state_driven/data/arch5_analysis.json` | `bc022778793b9fe398a3f9a443a4ffb0d8a43d3f22611ae605abe081ca2144a3` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `arch5_compare.jsonl` | `group4_state_driven/data/arch5_compare.jsonl` | `215d36d711b82a0d3048dbf3d47472594fbc91ac571fcc635ffa3fbba9c68e83` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `arch4_tables.md` | `group4_state_driven/data/arch4_tables.md` | `31fe8f1b8d3e13495796b39c4d9310f97445203d69f16492f1450523dedc1ef2` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `arch4_analysis.json` | `group4_state_driven/data/arch4_analysis.json` | `1a682e08261a7ea222ccc21b90c742ceb4e295bf67b07b17f39e42651ddf7bbb` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `arch4_compare.jsonl` | `group4_state_driven/data/arch4_compare.jsonl` | `31d0d566ae646301f252beb50ac3959e1afd2216d4fb3aec316d9a5d4e6b6250` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `REPORT_arch4.md` | `group4_state_driven/reports/REPORT_arch4.md` | `f4a5462128b4d8517e37c99336db7b548a50cf1fd19fc15c68056246b02af29b` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `workflow_arch5.py` | `group4_state_driven/code/workflow_arch5.py` | `f93f5f60a3add86f09786a16bdcf455ead45e09e121bacfa013c727867b878c0` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `workflow_arch4.py` | `group4_state_driven/code/workflow_arch4.py` | `8ab38ca208f17f5cbacdaa5e4a733ee2aefd0a3919ca27ab37c4c0c72a5afc89` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `PREREG_v6.md` | `group4_state_driven/prereg/PREREG_v6.md` | `2e3726827d0e7b224482d37439e470fd4ab2d9d69fe73f5f76096520bfca470f` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |
| `PREREG_v5.md` | `group4_state_driven/prereg/PREREG_v5.md` | `06a0f00e538e958ebed2dbc8626af44418e49219ef0c9e4da66ca33cdddcec89` | `54e016c6293f4236b7b7dc5313976293be1c74ab` |

## 外部复核方法（一条命令）

```bash
# 取远端文件并比对（branch 可换）
B=feature/g4-arch4-state-driven
R=lixvanran/agent-creativity-mechanism-study
for F in reports/REPORT_arch5.md data/arch5_tables.md data/arch5_analysis.json data/arch5_compare.jsonl; do
  curl -sL -H "Authorization: token \$TOKEN" \\
    "https://raw.githubusercontent.com/\$R/\$B/group4_state_driven/\$F" | sha256sum
done
```

## 自查结论（2026-10-24 12:1x）

- 四个 v5 头条读数文件：**本地 = 仓库副本 = GitHub 远端，逐字节一致**（本次已实测）。
- ⚠️ 历史更正：早前对外报的 `REPORT_arch5.md` sha256 `b61345b0…` 是 **`5de1a6b` 版（更正前）**；正确值是本表中的 `871aa4cf…`（`4b90e11` 版）。
