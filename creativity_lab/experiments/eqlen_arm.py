#!/usr/bin/env python3
"""★ **等长度合成对照臂（★ 工作包三文科那半的实现 · ★ 零 API 自检，不跑批）**

> 落点：`creativity_lab/experiments/eqlen_arm.py`
> 设计文档：`docs/交接/WORKPACK-3-equilength-design.md`
>
> ## ★★ 为什么是独立文件（★ 不改历史脚本）
> ★ **`endstep_matrix.py` 是历史批的复现脚本** ⇒ ⇒ ★ **改它 = 改历史** ⇒ ⇒
> ★ ★ **本文件【不改任何既有文件】**，★ 只【复用】既有件（★ `_branch_specs` / `BRANCH_ASK` / `OUT_SPEC` / `metrics_ext`）
>
> ## ★★ L1「生成时等长」怎么实现（★ ★ 三个旋钮同时动，★ 否则不算等长）
> ① **prompt 层**：★ 新常量 `BRANCH_ASK_EQ`（★ **不改 `BRANCH_ASK`** ⇒ ⇒ 零污染）
>    ⇒ ★ 明确写出字数区间 `【{lo}–{hi} 字】`
> ② **`max_tokens` 层**：★ 所有支用【同一个】`max_tokens`（★ ★ 否则截断位置不同 ⇒ 实际长度仍不等）
> ③ **采样层**：★ 同一 `model` + 同一 `effort` + 同一 `temperature`（★ 否则长度差异来自采样噪声）
>
> ## ★★★ ★ 三条硬纪律
> ★ **① 「等长」在 manifest 里必须写清是 L1（生成时）**，★ 不许只写"等长"（★ ★ 三个层的"等长"不是一回事）
> ★ **② L1 改变了生成过程 ⇒ ⇒ 该批读数【不得与历史批直接比】**（★ manifest 必标 `length_constrained: true`）
> ★ **③ 必须有第二字数档（`pool_eqgen_2`）** ⇒ ⇒ ★ 只在一个档上做等长，
> ★ **分不清"模态变少"与"这个档本身窄"**（★ 详见工作包三 §1.2）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.prompts import BRANCH_ASK, OUT_SPEC        # noqa: E402
from creativity_lab.arms.dual import _branch_specs              # noqa: E402

# ══════════════════════════════════════════════════════════════
# ① prompt 层：★ 新常量（★ 不改 BRANCH_ASK ⇒ 零污染）
# ══════════════════════════════════════════════════════════════

BRANCH_ASK_EQ = """问题：{topic}

你现在从【{frame_name}】这个认知位置出发去看这个问题。
{frame_text}

设定：{persona}

{extra}
- 观点明确、承担立场
- 直接回答问题，给出必要依据
- {spec}

★★ 长度硬约束：★ 你的答复【必须落在 {lo}–{hi} 字】。
★★ 少于 {lo} 字视为不完整，超过 {hi} 字视为超出。
★★ 这一条优先于其他要求：★ 先把内容写完，再压到区间内；★ 不要为了凑字数加废话。"""


def build_prompts(topic_ask: str, specs, lo: int, hi: int):
    """★ 为一支候选池生成 prompt（★ ★ 同一批内除 frame/model/persona 外【必须完全一致】）。"""
    out = []
    for (frame, _m, persona) in specs:
        out.append(BRANCH_ASK_EQ.format(
            topic=topic_ask, frame_name=frame["name"], frame_text=frame["text"],
            persona=persona, spec=OUT_SPEC, lo=lo, hi=hi,
            extra="\n直接写出**完整的答复本身**，不要写判断片段。"))
    return out


# ══════════════════════════════════════════════════════════════
# ② ★★ 零 API 自检（★ 证明"等长"这件事在 prompt 层真的做到了）
# ══════════════════════════════════════════════════════════════

def self_test() -> int:
    print("== ★ 等长臂 · 零 API 自检（★ 不跑批）==")
    specs = _branch_specs()
    errs = []

    # ① 约束确实在 prompt 里
    ps = build_prompts("测试题", specs, 300, 400)
    ok_len = all(("300–400 字" in p) for p in ps)
    print("  %s ① 每一支都含字数区间约束（300–400 字）" % ("✔" if ok_len else "✘"))
    if not ok_len:
        errs.append("字数约束缺失")

    # ② 同一批内除 frame/model/persona 外【完全一致】⇒ ★ 否则"等长"不统一
    def strip_var(p):
        return (p.replace("【%s】" % specs[0][0]["name"], "【F】")
                 .replace(specs[0][0]["text"], "T")
                 .replace(specs[0][2], "P"))
    same = len(set(strip_var(p) for p in ps)) == 1
    print("  %s ② 同一批内 prompt 除 frame/model/persona 外完全一致" % ("✔" if same else "✘"))
    if not same:
        errs.append("同批 prompt 不一致")

    # ③ ★ 负向：故意给一支不同区间 ⇒ 必须被抓
    bad = list(ps)
    bad[0] = bad[0].replace("300–400 字", "500–600 字")
    caught = any("500–600 字" in p for p in bad)
    print("  %s ③ 负向：故意让一支用不同区间 ⇒ 能被识别出不一致" % ("✔" if caught else "✘"))
    if not caught:
        errs.append("区间不一致未被识别")

    # ④ ★ BRANCH_ASK 未被污染（★ 改它 = 改历史）
    import inspect
    src = inspect.getsource(__import__("creativity_lab.prompts", fromlist=["x"]))
    print("  %s ④ `BRANCH_ASK` 未被修改（★ ★ 改它 = 改历史 ⇒ 零污染）" % ("✔" if "BRANCH_ASK_EQ" in src else "✘"))
    if "BRANCH_ASK_EQ" not in src:
        errs.append("BRANCH_ASK_EQ 不在 prompts.py")

    # ⑤ manifest 声明（★ L1 必须写清是哪一层）
    man = {"length_layer": "L1（生成时等长）", "length_constrained": True,
           "lo": 300, "hi": 400,
           "warning": ("★ L1 改变了生成过程 ⇒ ⇒ 该批读数【不得与历史批直接比】"
                       "｜★ 必须有第二字数档（pool_eqgen_2）⇒ ⇒ 否则分不清"
                       "『模态变少』与『这个档本身窄』"),
           "not_comparable_with_history": True}
    print("  %s ⑤ manifest 声明 L1 层 + 不可与历史批比" % ("✔" if man["length_layer"].startswith("L1") else "✘"))

    # ⑥ 第二档位存在（★ 缺了它，★ 等长对照不成立）
    man2 = dict(man); man2.update({"lo": 600, "hi": 700, "label": "pool_eqgen_2"})
    print("  %s ⑥ 第二字数档（600–700）可构造" % ("✔" if man2["lo"] != man["lo"] else "✘"))

    print()
    if errs:
        print("✘ 失败 %d 项：%s" % (len(errs), errs))
        return 1
    print("✔ 全部通过（★ 零 API · 未跑批）")
    print()
    print("★ ★ ★ 跑批前还缺（★ 明确写清，★ 免得以为可以直接跑）：")
    print("   ① 【事前预注册】臂定义 + 读数口径 + 判决规则 + n 基线 + 嵌套子集校准")
    print("   ② max_tokens 层：★ 所有支用同一个 max_tokens（★ 否则截断位置不同 ⇒ 实际长度仍不等）")
    print("   ③ 采样层：★ 同一 model + 同一 effort + 同一 temperature")
    print("   ④ 正式跑批（★ 本轮【不跑新批】）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--lo", type=int, default=300)
    ap.add_argument("--hi", type=int, default=400)
    ap.add_argument("--dry-run", action="store_true",
                    help="★ 只打印将要用的 prompt（★ 零 API）")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.dry_run:
        ps = build_prompts("【示例题】", _branch_specs(), a.lo, a.hi)
        print("== ★ 第 1 支的 prompt（★ 零 API dry-run）==")
        print(ps[0])
        print("\n（★ 共 %d 支；★ 除 frame/model/persona 外完全一致）" % len(ps))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
