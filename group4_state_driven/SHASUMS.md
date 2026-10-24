# 第四组 · 交付物校验台账（sha256 绑 commit）

**校验基准 commit**：`45903804118a93b14be683c4375d3bbaef2b757d`（分支 `feature/g4-arch4-state-driven`，`main` 未动）
**生成时间**：2026-10-24 16:1x（北京）

> ⚠️ **为什么必须有本文件**：sha256 随文件修改失效。2026-10-24 12:0x 我们把 `REPORT_arch5.md` 的
> 旧版 sha256（`b61345b0…`，对应 `5de1a6b`）报给了主会话，而该文件在 `4b90e11` 已改过 ⇒
> 远端与本地都是新版 `871aa4cf…` ⇒ ⇒ **同一个 sha256 在不同 commit 下指向不同内容**。
> ⇒ ⇒ **对外一律以「sha256 + 基准 commit」成对给，不许只报 sha256。**

---

| 文件 | 仓库路径 | sha256 | 基准 commit |
|---|---|---|---|
| `REPORT_arch5.md` | `group4_state_driven/reports/REPORT_arch5.md` | `871aa4cf0251a79c9cf14e33a89aadae4f49895290da77d439b981ff04a117e0` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `REPORT_arch4.md` | `group4_state_driven/reports/REPORT_arch4.md` | `f4a5462128b4d8517e37c99336db7b548a50cf1fd19fc15c68056246b02af29b` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `arch5_tables.md` | `group4_state_driven/data/arch5_tables.md` | `f8547d4fe0df185bf8b94a73da2de8c1fa12113cbf4bce5eab9b9aa78b2d1548` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `arch5_analysis.json` | `group4_state_driven/data/arch5_analysis.json` | `bc022778793b9fe398a3f9a443a4ffb0d8a43d3f22611ae605abe081ca2144a3` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `arch5_compare.jsonl` | `group4_state_driven/data/arch5_compare.jsonl` | `215d36d711b82a0d3048dbf3d47472594fbc91ac571fcc635ffa3fbba9c68e83` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `arch4_tables.md` | `group4_state_driven/data/arch4_tables.md` | `31fe8f1b8d3e13495796b39c4d9310f97445203d69f16492f1450523dedc1ef2` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `arch4_analysis.json` | `group4_state_driven/data/arch4_analysis.json` | `1a682e08261a7ea222ccc21b90c742ceb4e295bf67b07b17f39e42651ddf7bbb` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `arch4_compare.jsonl` | `group4_state_driven/data/arch4_compare.jsonl` | `31d0d566ae646301f252beb50ac3959e1afd2216d4fb3aec316d9a5d4e6b6250` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `v6_power.json` | `group4_state_driven/data/v6_power.json` | `58545f543eb814893d7564bfaae238518379900c397a064ed88c71989d580fa1` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `workflow_arch5.py` | `group4_state_driven/code/workflow_arch5.py` | `f93f5f60a3add86f09786a16bdcf455ead45e09e121bacfa013c727867b878c0` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `workflow_arch4.py` | `group4_state_driven/code/workflow_arch4.py` | `8ab38ca208f17f5cbacdaa5e4a733ee2aefd0a3919ca27ab37c4c0c72a5afc89` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `v6_power.py` | `group4_state_driven/code/v6_power.py` | `462b4b984a7bd6ae797ccb4d02f6f1cf5188d38f6b34f9e66098d9b07e9994b1` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `PREREG_v6.md` | `group4_state_driven/prereg/PREREG_v6.md` | `525aabd591ceabdcf6900450340d9f227c68d0485755788dc2ad0b313e5ac8d2` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `PREREG_v5.md` | `group4_state_driven/prereg/PREREG_v5.md` | `06a0f00e538e958ebed2dbc8626af44418e49219ef0c9e4da66ca33cdddcec89` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `PAPER_draft.md` | `group4_state_driven/paper/PAPER_draft.md` | `a3a0b5e867aa1648c11773a2757d612605d4653f08cfbb7510490b2440582d81` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `PAPER_draft_notes.md` | `group4_state_driven/paper/PAPER_draft_notes.md` | `a3fdeaedd3e6d24ccdffb9c701086515864d33ff0bffe2eed2f61e3a1f266bee` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `PAPER_draft.pdf` | `group4_state_driven/paper/runs/PAPER_draft.pdf` | `a8b052a6126a993575cc365eb17e56e42049061ce4b3473273130c26c0de9f73` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `build_paper_pdf.sh` | `group4_state_driven/paper/build/build_paper_pdf.sh` | `b52987c3188c5ecce006bf00c8406174c6b75afba402d509a860d8f984485fcd` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `verify_paper_pdf.py` | `group4_state_driven/paper/build/verify_paper_pdf.py` | `141fa1a7ba1e88315bf9a583753ba49283f2c855bbdca992700fa60ded898778` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `header.tex` | `group4_state_driven/paper/build/header.tex` | `c3d21799d43d363a8d43e168cf5716280e70049a289d2ff53c73188cf81030fb` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `template.latex` | `group4_state_driven/paper/build/template.latex` | `1d671ee23a46a1f10d46c9365e802506d9bf8941e76b61f5476f16bad7c2c278` | `45903804118a93b14be683c4375d3bbaef2b757d` |
| `heading_filter.lua` | `group4_state_driven/paper/build/heading_filter.lua` | `eb6de0039e6de295552300ac15d2327018593947db14d052e062486a5eaa074b` | `45903804118a93b14be683c4375d3bbaef2b757d` |

## 外部复核方法（一条命令）

```bash
B=feature/g4-arch4-state-driven; R=lixvanran/agent-creativity-mechanism-study
for F in reports/REPORT_arch5.md data/arch5_compare.jsonl data/arch5_tables.md data/arch5_analysis.json \
         prereg/PREREG_v6.md paper/PAPER_draft.md paper/runs/PAPER_draft.pdf; do
  printf "%s  " "$F"
  curl -sL -H "Authorization: token $TOKEN" \
    "https://raw.githubusercontent.com/$R/$B/group4_state_driven/$F" | sha256sum | cut -c1-64
done
```

## 自查结论（2026-10-24 16:1x）

- v4/v5 头条读数四文件：**本地 = 仓库副本 = GitHub 远端**，逐字节一致（已实测）。
- 论文 PDF：`paper/runs/PAPER_draft.pdf`（25 页 A4），机械验证 15/15 通过（`paper/build/verify_paper_pdf.py`）。
- ⚠️ 历史更正：早前对外报的 `REPORT_arch5.md` sha256 `b61345b0…` 是 **`5de1a6b` 版（更正前）**；正确值见本表。
