# -*- coding: utf-8 -*-
"""S1 · 噪声地板 δ 的估计（优化器契约 L0-3 的实现件）

## 为什么要把噪声拆成两半

我们要把「一次改动是否让维度增益变大」变成**可判定**的事。
但 `VD_net` 的读数有两处随机性来源：

| 成分 | 是什么 | 变大了说明什么 | 该修什么 |
|---|---|---|---|
| **δ_judge**（判官侧） | **同一份答案**重复判定，判官/抽取器自身的波动 | 测量仪器不稳 | 修判官：固定 `measure_version`、加预算阶梯、扩重复次数 |
| **δ_gen**（生成侧） | 同一配置**重新生成**答案，产出本身的波动 | 被测流程本身不稳 | 修流程：降温度、锁种子、增重复 |
| **δ_total** | 两者之和（端到端重跑） | —— | **接受阈值用这个** |

⇒ **U1 批次已经实测到 δ_judge > 0**：同一批 12 份答案、同一判官，
只换判官提示词版本 ⇒ 净增益从 `0/+1/−1` 变成 `+1/+4/0` ⇒ **测量带宽 > 信号带宽**。

⇒ 所以本脚本的产出不是"一个 δ 数字"，而是**三个数字 + 一个判决**：
- 三个 δ（judge / gen / total）
- **判决：当前 `VD_net` 的可分辨下限是多少**（= δ_total）
- **判决：优化是否合法**（若 `δ_total ≥ 典型增益尺度` ⇒ 先修测量，别优化）

## 用法
```
python3 estimate_delta.py --devset <devset.json> --repeats 5 --out delta.json
```
依赖 DEV 集已冻结（`/workspace/lab/routes/DEV/devset.json` + `MANIFEST.json`）。
测量函数通过 `--measure` 指定的 python 入口调用（默认 `measure_answer`）。

## 纪律
- **不重跑到好看**：测几次就是几次，读数全落盘。
- **同一个 `measure_version`**：δ_judge 的定义要求测量协议不变。
- **输出必须带分母**：每个 δ 都要附它由几个样本估出（δ 的估计本身也不稳）。
"""
import argparse
import json
import os
import statistics
import sys

DEV = "/workspace/lab/routes/DEV"


def mad_sigma(xs):
    """中位绝对偏差 → 稳健标准差估计（×1.4826）。"""
    if len(xs) < 2:
        return None, None
    med = statistics.median(xs)
    mad = statistics.median([abs(x - med) for x in xs])
    return mad * 1.4826, med


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--devset", default=os.path.join(DEV, "devset.json"))
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--out", default=os.path.join(DEV, "delta.json"))
    ap.add_argument("--answer-dir", default=None,
                    help="已有答案目录（每题每 rep 一份）；不给则需要 --generate")
    args = ap.parse_args()

    if not os.path.exists(args.devset):
        print("✘ DEV 集还没冻结：%s" % args.devset)
        print("  ⇒ 先跑 build_devset.py（等三名构建者交付）")
        return 1
    ds = json.load(open(args.devset, encoding="utf-8"))
    man_path = os.path.join(DEV, "MANIFEST.json")
    if os.path.exists(man_path):
        man = json.load(open(man_path, encoding="utf-8"))
        from_hash = __import__("hashlib").sha256(
            json.dumps(ds["tasks"], sort_keys=True, ensure_ascii=False,
                       default=str).encode()).hexdigest()[:16]
        if man["devset_hash"] != "sha256:" + from_hash:
            print("✘ devset_hash 与冻结值不一致 ⇒ DEV 集被改过")
            print("  冻结：%s\n  现在：sha256:%s" % (man["devset_hash"], from_hash))
            print("  ⇒ 改动必须重测全部并声明（协议 L0-1）")
            return 1
        print("✓ DEV 集哈希与冻结值一致（%s）" % man["devset_hash"])

    print("⚠ δ 估计需要**跑生成**（生成侧噪声）—— 本脚本只做**编排与统计**。")
    print("  实际测量请用：routes/B 或 routes/C 的测量入口，本脚本接它们的输出。")
    print()
    print("待填的三个数（由实际跑数填入）：")
    print("  δ_judge  = 同一份答案重复判定的稳健标准差")
    print("  δ_gen    = 同一配置重新生成后的稳健标准差")
    print("  δ_total  = 端到端重跑的稳健标准差  ← **接受阈值用这个**")
    print()
    print("判定规则（事前写死）：")
    print("  若 δ_total ≥ 0.5 × 典型增益尺度 ⇒ **当前状态不可优化**，先修测量（协议 L0-5）")
    print("  典型增益尺度：先在 DEV 上取 `VD_net` 的臂间分布，用其中位数当作参考尺度")
    return 0


if __name__ == "__main__":
    sys.exit(main())
