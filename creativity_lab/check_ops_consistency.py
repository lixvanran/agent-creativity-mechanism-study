#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验：训练侧与执行侧的 ops.py 必须**逐字节一致**。

为什么需要它：本项目有两份同名 ops.py（仓库根=训练侧，cmp8/ 下=执行侧）。
历史上它们漂移过 ⇒ 训练时算的"宽度"与实际交付的宽度不是一回事 ⇒ 训练目标失真。
⇒ **这个校验必须能回归**，不能靠人记得。

用法：python3 creativity_lab/check_ops_consistency.py [仓库根]
退出码 0 = 一致；1 = 不一致
"""
import os
import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
a = os.path.join(ROOT, "creativity_lab", "ops.py")
b = os.path.join(ROOT, "cmp8", "creativity_lab", "ops.py")
for p in (a, b):
    if not os.path.exists(p):
        print("✘ 缺文件：%s" % p); sys.exit(1)
sa = open(a, "rb").read(); sb = open(b, "rb").read()
if sa == sb:
    print("✅ 两份 ops.py 逐字节一致（%d 字节）" % len(sa)); sys.exit(0)
print("✘ 两份 ops.py 不一致：")
print("   训练侧 %s : %d 字节" % (a, len(sa)))
print("   执行侧 %s : %d 字节" % (b, len(sb)))
# 指出差异
import difflib
la = sa.decode("utf-8").splitlines(); lb = sb.decode("utf-8").splitlines()
for l in list(difflib.unified_diff(la, lb, "训练侧", "执行侧", lineterm=""))[:20]:
    print("   " + l)
sys.exit(1)
