# 历史跑批可信度核查（机械判定）

> 生成：`creativity_lab/experiments/audit_history.py`｜源：`data/historical-runs/`


## 1. 结论

- **可直接引用：12 / 21 组**（57%）

- 不可用：**%d 组** ⇒ 标记如下。**不修正数字**：归档不可信时「修正」就是编造。


| 标记 | 组数 | 含义 | 还能用吗 |
|---|--:|---|:--:|
| `topic_renamed` | 13 | 文件名题号 ≠ 内容题号，但**组内一致** ⇒ 只是**命名不同源** | ✔ 可用（换题号即可） |
| `internal_mismatch` | 8 | **组内各臂指向不同题** ⇒ 配对本身错了 | ✘ 不可用 |
| `branch_deficit` | 1 | 分支数 < 5 ⇒ 型号下架导致死分支被静默丢弃 ⇒ **分母漂移** | ⚠ 比率要改分母 |

## 2. 题号映射（历史 → 当前）

| 历史组 | 当前题 |
|---|---|
| practical-4q/A1 | T2 |
| practical-4q/A2 | T3 |
| practical-4q/A4 | T1 |
| writing-3q4arm/P1 | T1 |
| writing-3q4arm/P2 | T2 |
| writing-3q4arm/P3 | T1 |

## 3. 逐组明细


| 数据集 | 组 | 文件题号 | 内容题号 | 分支数 | 各臂内容 | 标记 | 可用 |

|---|---|--:|--:|--:|---|---|:--:|
| practical-4q | A1_r1 | A1 | T2 | 5 | arm1→T2；arm2→T2；arm3→—；arm4→T1/T2 | topic_renamed(A1→T2) | ✔ |
| practical-4q | A1_r2 | A1 | T2 | 5 | arm1→T2；arm2→T2；arm3→T2；arm4→T2 | topic_renamed(A1→T2) | ✔ |
| practical-4q | A1_r3 | A1 | T2 | 5 | arm1→T2；arm2→T2；arm3→—；arm4→T2 | topic_renamed(A1→T2) | ✔ |
| practical-4q | A2_r1 | A2 | T3 | 4 | arm1→—；arm2→—；arm3→T3；arm4→— | branch_deficit(1)；topic_renamed(A2→T3) | ✘ |
| practical-4q | A2_r2 | A2 | T3 | 5 | arm1→—；arm2→—；arm3→—；arm4→T3 | topic_renamed(A2→T3) | ✔ |
| practical-4q | A2_r3 | A2 | T3 | 5 | arm1→T3；arm2→T3；arm3→—；arm4→T3 | topic_renamed(A2→T3) | ✔ |
| practical-4q | A3_r1 | A3 | — | 5 | arm1→—；arm2→—；arm3→—；arm4→— | internal_mismatch | ✘ |
| practical-4q | A3_r2 | A3 | — | 5 | arm1→—；arm2→—；arm3→—；arm4→— | internal_mismatch | ✘ |
| practical-4q | A3_r3 | A3 | — | 5 | arm1→—；arm2→—；arm3→—；arm4→— | internal_mismatch | ✘ |
| practical-4q | A4_r1 | A4 | — | 5 | arm1→—；arm2→—；arm3→—；arm4→— | internal_mismatch | ✘ |
| practical-4q | A4_r2 | A4 | T1 | 5 | arm1→—；arm2→—；arm3→—；arm4→— | topic_renamed(A4→T1) | ✔ |
| practical-4q | A4_r3 | A4 | — | 5 | arm1→—；arm2→—；arm3→—；arm4→— | internal_mismatch | ✘ |
| writing-3q4arm | P1_r1 | P1 | T1 | 5 | arm1→T2；arm2→T1；arm3→T1；arm4→— | topic_renamed(P1→T1) | ✔ |
| writing-3q4arm | P1_r2 | P1 | T1 | 5 | arm1→T1；arm2→—；arm3→T2；arm4→T1 | topic_renamed(P1→T1) | ✔ |
| writing-3q4arm | P1_r3 | P1 | — | 5 | arm1→T1；arm2→—；arm3→T1；arm4→T2 | internal_mismatch | ✘ |
| writing-3q4arm | P2_r1 | P2 | T2 | 5 | arm1→—；arm2→—；arm3→—；arm4→— | topic_renamed(P2→T2) | ✔ |
| writing-3q4arm | P2_r2 | P2 | T1 | 5 | arm1→—；arm2→—；arm3→T1；arm4→— | topic_renamed(P2→T1) | ✔ |
| writing-3q4arm | P2_r3 | P2 | T2 | 5 | arm1→—；arm2→—；arm3→—；arm4→— | topic_renamed(P2→T2) | ✔ |
| writing-3q4arm | P3_r1 | P3 | T1 | 5 | arm1→T1；arm2→T1；arm3→T1；arm4→T1/T2 | topic_renamed(P3→T1) | ✔ |
| writing-3q4arm | P3_r2 | P3 | — | 5 | arm1→T1；arm2→—；arm3→T1；arm4→T2 | internal_mismatch | ✘ |
| writing-3q4arm | P3_r3 | P3 | — | 5 | arm1→T1；arm2→—；arm3→—；arm4→— | internal_mismatch | ✘ |

## 4. 使用规则

1. **凡引用历史 run 的读数，先查本表**。

2. `branch_deficit` 的组：所有**比率**的分母改成实际分支数，**不能沿用 5**。

3. `internal_mismatch` 的组：任何**跨文件配对分析**都不成立。

4. `topic_renamed` 的组**照常可用**，只需用 §2 的映射换题号。

5. ★ **修正第三轮报告的说法**：历史归档**不是全废**——**题号不同源**（A1–A4/P1–P3 vs T1–T3）≠ **配对错位**；真正错位的只有组内各臂指向不同题的少数组。

6. 新跑批一律走**结构化 manifest 配对**（不用文件名约定）。

