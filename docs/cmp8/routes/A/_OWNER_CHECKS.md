# 负责人对路线 A 的实测核对（2026-10-21 02:55）

> ⚠️ 以下是**负责人自己跑的命令与读数**，不是路线 A 的自述。
> 复核者请**独立重做**，不要直接采信结论。

## 1｜`spec.yaml` 能否被规范渲染器吃（硬契约）
```
$ python3 /workspace/lab/build_spec_flowchart.py /workspace/lab/routes/A/spec.yaml $T "路线A" "t"
  bytes=4443 rects=9 paths=16 texts=9
$ grep -c '^nodes:' A/spec.yaml  → 1     （20 个节点：N0–N8 流程节点 + 10 条对照臂）
$ grep -c '^edges:' A/spec.yaml  → 1     （内联映射 {from:…, to:…, label:…}）
```
⇒ ✅ **满足**。对照：路线 B/C 的 spec 在补图前渲染为 **0 rects / 0 paths / 0 texts**（被判死项）。

## 2｜接线自检是否适用
```
$ grep -rn "PARAM|可训练|trainable" A/*.py  →  （空）
```
⇒ ✅ **不适用**：路线 A 零训练，**没有参数表** ⇒ 不存在"声明存在但代码不读"的死维风险
（这正是路线 C 被抓的那类问题：P12 死代码 + theta_util/m_clusters 对 J 不变）。

## 3｜自检是不是「橡皮图章」
```
$ python3 A/blacklist_check.py
  {"source_files": 8, "blacklist_strict": 5644, "blacklist_hint": 104,
   "files": [], "strict_hits": 0, "hint_hits": 0}      退出码 0
$ grep -n 'sys.exit' A/blacklist_check.py
  129:    sys.exit(1 if out["strict_hits"] else 0)
$ grep -n 'user4' A/blacklist_check.py
  31:    "/workspace/lab/creativity_lab/data/user4_q*.json",
  32:    "/workspace/lab/cmp8repo/cmp8/creativity_lab/data/user4_q*.json",
```
⇒ ✅ **不是橡皮图章**：`source_files=8` ⇒ **没有跳过**（对比路线 C：glob 指向不存在路径 ⇒ 跳过 [1]/[3]/[6]
却仍打印 PASS 并 exit 0）；**退出码只在真有 strict 命中时才非零**。

## 4｜「embo-01 无分辨率」这条实测写进去了吗
```
$ grep -n 'embo\|余弦\|27 条' A/DESIGN.md
  102:  …本项目自己的实测结论是 embo-01 的句级几何没有分辨率（SEP≈0.002）…会把 27 条断言压成 1 条——本次冒烟实际观测到
  299:  | lex_thr | 0.75（char-bigram Jaccard）| …冒烟实测：27 条断言保留 27 条（不误杀）|
  300:  | struct_thr | 0.70（4-gram 覆盖率…）| 校准：27 条断言 → 保留 25 条，被删的 2 条经人工确认确为改写型重复；
        **校准集不是 DEV 集、更不是 U1–U4** |
  592:  1. 用 embedding 余弦做去冗余会毁掉宽度：27 条断言被压成 1 条 ⇒ 改用离散结构判据…
```
⇒ ✅ **已写进三处**（组件选型理由 / 预注册常量表含**人工校准**与校准集声明 / 独立结论节）。

## 5｜有无「结构上不可能」这类无代码支撑的断言
```
$ grep -n '不可能|确保|必然|永远' A/DESIGN.md   →  （0 命中）
```
⇒ ✅ **没有**（路线 C 的「白名单化 ⇒ 泄漏在结构上不可能发生」被判死）。

## 结论
路线 A 的**五项负责人收尾要求全部满足**，唯一缺的是 `deliverable.md`（执行任务被 50 分钟上限杀，
负责人已补写于 `/workspace/.mavis/plans/plan_9e024318/outputs/t1-routeA/deliverable.md`）。
⇒ **仍需一次独立复核**（与 B/C 同规格）—— 路线 A 的代码从未被独立复核者审过。
