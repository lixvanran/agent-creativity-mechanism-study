# -*- coding: utf-8 -*-
"""★ 变异注入：验证 verify_reorg.py 的各条检查【还能红，且红在预期处】
   --------------------------------------------------------------
   ★★ 为什么必须做：S2/S3 刚刚被【放宽】（排除声明式替换区）⇒ 必须证明没变成恒绿。
   ★ 做法：复制新稿 → 注入一处具体违规 → 跑核验器 → 看是否红 + 报错点名预期处。
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VER = os.path.join(HERE, "verify_reorg.py")
# ★ 目标稿路径不写死（★ 与 reorg_paths 同源解析）
sys.path.insert(0, HERE)
from reorg_paths import resolve_src, resolve_dst
DST = resolve_dst(resolve_src())
ORIG = io.open(VER, encoding="utf-8").read()


def run(name, old, new, expect_kw):
    """在新稿副本上注入 old->new，跑核验器"""
    base = io.open(DST, encoding="utf-8").read()
    assert old in base, "★ 新稿锚点不存在：%r" % old[:60]
    d = tempfile.mkdtemp(prefix="vmut_")
    try:
        bad = os.path.join(d, "bad.md")
        io.open(bad, "w", encoding="utf-8").write(base.replace(old, new, 1))
        code = ORIG  # ★ 不再靠字符串替换重定向 ⇒ 改用环境变量接口（更稳）
        p = os.path.join(d, "verify_reorg.py")
        io.open(p, "w", encoding="utf-8").write(code)
        env = dict(os.environ)
        env["REORG_WORKDIR"] = HERE
        env["REORG_DST"] = bad   # ★ 显式接口：核验器读这个被变异的副本
        r = subprocess.run([sys.executable, p], capture_output=True, text=True,
                           cwd=HERE, timeout=180, env=env)
        out = (r.stdout or "") + (r.stderr or "")
        red = r.returncode != 0
        named = expect_kw in out
        status = "PASS" if (red and named) else "FAIL"
        print("[%s] %-30s rc=%-3s 红=%-5s 点名预期处=%-5s" %
              (status, name, r.returncode, red, named))
        if not (red and named):
            print("      期望报错含 %r；实际输出尾部：" % expect_kw)
            print("      " + out[-500:].replace("\n", "\n      "))
        return status == "PASS"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    res = []

    # V1：篡改一个【正文】读数（表格里）⇒ S1/S2/S3 必须红
    res.append(run("V1 正文读数被篡改",
                   "| 3 次独立直调 | 0.461（窄）| 4.00 |",
                   "| 3 次独立直调 | 0.471（窄）| 4.00 |",
                   "S1"))

    # V2：删掉一整行正文 ⇒ S2/S3 必须红
    res.append(run("V2 删掉一行正文",
                   "> ⇒ ⇒ **认知位置真的把 prior 改掉了。**\n",
                   "",
                   "S2"))

    # V3：制造重复小节号 ⇒ S4 必须红
    res.append(run("V3 制造重复小节号",
                   "### 6.5 ★ 三项测量学失败（公开报告）",
                   "### 6.5 ★ 三项测量学失败（公开报告）\n\n### 6.5 重复号测试节",
                   "S4"))

    # V4：破坏 HOLDOUT 标记 ⇒ S5 必须红
    res.append(run("V4 破坏 HOLDOUT 标记",
                   "<!-- HOLDOUT_TABLE:BEGIN -->",
                   "<!-- HOLDOUT_TABLE:BEGAN -->",
                   "S5"))

    # V5：删掉一个关键限定词 ⇒ S6 必须红
    res.append(run("V5 关键限定词消失",
                   "★ 也不得写「我们证明不是注意力机制」",
                   "★ 就这样吧",
                   "S6"))

    # ★★ V7：独立审稿 v2 实测的三个【假绿】变异 ⇒ 本核验器必须能抓住
    #   （★ 这三个在上一版核验器里全部 rc=0 PASS）
    res.append(run("V7a 悬空 § 引用（§4.3→§9.9）",
                   "失败信号是**零判官成本**的矛盾检测器（§4.3）",
                   "失败信号是**零判官成本**的矛盾检测器（§9.9）",
                   "S4a"))

    res.append(run("V7b 指错 § 引用（§6.2c→§6.2e）",
                   "（§6.2c）⇒ **不能用来证明",
                   "（§6.2e）⇒ **不能用来证明",
                   "S4c"))

    # ★★ V7c：【原理性抓不到】⇒ 记为已知边界（★ 不假装能抓）
    #   这一处原稿本身就指错（§5.4=目标函数 ⇒ 已按 P6 修正为 §4.6）。
    #   ★ 把它改回 §4.4 之后，机器看到的仍与【原稿那处的内容映射】一致
    #   （§4.4 恰是"目标函数"节的映射）⇒ 机器没有"正确意图"的基准 ⇒ 原理上抓不到。
    #   ★ 这类只能靠【独立审稿人】看 ⇒ 已列入交付时的复核清单。
    print()
    print("★ 已知边界 V7c（原稿自身错指处 ⇒ 机器无基准 ⇒ 原理上抓不到）：")
    print("  ⇒ 这类只能由独立审稿人逐条看；已在交付说明里列为【必读复核项】")

    # V6：★ 反向 —— 篡改一个【声明区】（页眉/摘要/§1.4）里的数字
    #    ⇒ 本核验器【预期不红】（声明区被显式排除）⇒ 记录为【已知边界】
    print()
    print("★ 反向变异 V6（声明区数字被篡改 ⇒ 预期【不红】⇒ 已知边界）：")
    base = io.open(DST, encoding="utf-8").read()
    d = tempfile.mkdtemp(prefix="vmut6_")
    try:
        bad = os.path.join(d, "bad.md")
        io.open(bad, "w", encoding="utf-8").write(
            base.replace("0.43–0.48", "0.43–0.99", 1))
        code = ORIG  # ★ 不再靠字符串替换重定向 ⇒ 改用环境变量接口（更稳）
        p = os.path.join(d, "verify_reorg.py")
        io.open(p, "w", encoding="utf-8").write(code)
        env = dict(os.environ)
        env["REORG_WORKDIR"] = HERE
        env["REORG_DST"] = bad   # ★ 显式接口：核验器读这个被变异的副本
        r = subprocess.run([sys.executable, p], capture_output=True, text=True,
                           cwd=HERE, timeout=180, env=env)
        print("  V6 摘要里 0.48 -> 0.99 ⇒ rc=%s" % r.returncode)
        print("  ⇒ ★ 确认边界：声明区（页眉/摘要/§1.4）的数字守恒【不】由本核验器保证")
        print("  ⇒ ★ 它由 reorg_paper.py 的『自检 3b（摘要数字出处核对）』保证")
        print("  ⇒ ★ 且【逐个定位到同一处出处】只能由人工追溯保证（M1b 已实测该边界）")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    ok = sum(1 for r in res if r)
    print("★ 核验器变异注入：%d/%d 红在预期处" % (ok, len(res)))
    return 0 if ok == len(res) else 2


if __name__ == "__main__":
    sys.exit(main())
