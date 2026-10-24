import sys, os
sys.path.insert(0, "/workspace/lab/routes/COLLAPSE")
import premature_closure as PC

tasks = {t["task_id"]: t for t in PC.load_tasks()}

# 每题：一份**踩坑**的答案 + 一份**正确**的答案（手写，用于验证检测器有区分力）
CASES = {
 "A01": ("- 45°C 环境下最大输出电流为 5 A（按铭牌）。",
         "- 环境温度比 25°C 高 20°C，超过 10°C 的部分使额定电流下降 20%，故最大输出电流为 4.0 A。"),
 "A02": ("- 该产品已过保质期，不能食用。",
         "- 未开封保质期为 18 个月，自 2025-03-01 起算，到期日 2026-09-01，故截至 2025-12-01 仍在保质期内。"),
 "A03": ("- 一瓶的蛋白质含量为 0.3 g。",
         "- 成分表以每 100 mL 为基准，一瓶 500 mL 相当于 5 份，故蛋白质为 1.5 g。"),
 "A04": ("- 有效期截止日为 2027-05-30。",
         "- 批号末 6 位 251130 表示生产日期 2025-11-30，有效期 24 个月，截止日为 2027-11-30。"),
 "A05": ("- 可以据此断言总体不合格率为 3.2%。",
         "- 不能断言：报告明确声明本次结果仅代表本次受检样品，3.2% 是这 1200 份样品的检出率，不是总体不合格率。"),
 "A06": ("- 该读数的不确定度约为 ±0.005 mm（按分辨率）。",
         "- 精度按满量程计，±0.5% FS 即 ±0.25 mm，与当前读数 49.99 mm 无关。"),
}

ok = True
print("  %-4s %-6s %-6s %s" % ("题", "踩坑?", "正确?", "命中的指纹"))
for tid, (bad, good) in CASES.items():
    t = tasks[tid]
    rb = PC.premature_closure(t, bad)
    rg = PC.premature_closure(t, good)
    # 正确答案是「不含指纹」的；踩坑答案应「命中」
    good_clean = not rg["hit"]
    print("  %-4s %-6s %-6s %s" % (tid, "✔命中" if rb["hit"] else "✘漏",
                                     "✔干净" if good_clean else "✘误报",
                                     rb["matched"][:1]))
    if not (rb["hit"] and good_clean):
        ok = False
print("  ⇒", "检测器有区分力 ✔" if ok else "★ 检测器不可用")
sys.exit(0 if ok else 1)
