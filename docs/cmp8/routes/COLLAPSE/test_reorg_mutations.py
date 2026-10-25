# -*- coding: utf-8 -*-
"""★ 变异注入：验证 reorg_paper.py 的三条自检【还能红，且红在预期处】
   --------------------------------------------------------------
   ★★ 背景：守恒检查刚被放宽（排除结构性 token）⇒ 必须证明它没有变成恒绿。
   ★ 做法：复制源码 → 注入一处【具体违规】→ 跑 → 看是否红、退出码是几、红在哪条。
   ★ 判据：每条变异必须 (a) 退出码非 0 且 (b) 报错信息点名【预期的那一处】。
   ★★ 「有红就行」只证明「脚本某处会红」⇒ 必须点名预期处。
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "reorg_paper.py")
ORIG = io.open(SRC, encoding="utf-8").read()


def run_variant(name, old, new, expect_kw, target="SRC", accept=None):
    """注入 old->new，跑，看是否红 + 报错是否点名 expect_kw

    ★ target="SRC"：改【原稿副本】（★ 测"原稿被改坏时，产出是否还是对"）
    ★ target="SELF"：改【重组脚本自身】（★ 测"判据被改坏时是否还会红"）
    ★ accept：额外的可接受报错关键词（★ 同一处违规可能先被更早一道拦下
      ⇒ 【拦在哪一道不重要，重要的是它红，且红在一个语义相关的理由上】）
    """
    if target == "SRC":
        base = io.open(os.path.join(HERE, "..", "..", "PAPER-2026-10-25.md"),
                       encoding="utf-8").read()
        assert old in base, "★ 原稿锚点不存在：%r" % old[:60]
    else:
        assert old in ORIG, "★ 脚本锚点不存在：%r" % old[:60]
    d = tempfile.mkdtemp(prefix="mut_")
    try:
        if target == "SRC":
            src_copy = os.path.join(d, "src.md")
            io.open(src_copy, "w", encoding="utf-8").write(
                io.open(os.path.join(HERE, "..", "..", "PAPER-2026-10-25.md"),
                        encoding="utf-8").read().replace(old, new, 1))
            code = ORIG.replace(
                'SRC = "/workspace/lab/PAPER-2026-10-25.md"',
                'SRC = %r' % src_copy)
            code = code.replace('DST = "/workspace/lab/', 'DST = "%s/' % d)
            p = os.path.join(d, "reorg_paper.py")
            io.open(p, "w", encoding="utf-8").write(code)
        else:
            p = os.path.join(d, "reorg_paper.py")
            io.open(p, "w", encoding="utf-8").write(ORIG.replace(old, new, 1))
        env = dict(os.environ)
        env["REORG_WORKDIR"] = HERE
        r = subprocess.run([sys.executable, p], capture_output=True, text=True,
                           cwd=HERE, timeout=180, env=env)
        out = (r.stdout or "") + (r.stderr or "")
        red = r.returncode != 0
        _acc = [accept] if isinstance(accept, str) else (accept or [])
        named = (expect_kw in out) or any(a in out for a in _acc)
        if "Traceback" in out:
            print("      ★ 注意：脚本【崩溃】而非判据红（★ 崩溃与判据红必须可区分）")
        status = "PASS" if (red and named) else "FAIL"
        print("[%s] %-28s rc=%-3s 红=%-5s 点名预期处=%-5s" %
              (status, name, r.returncode, red, named))
        if not (red and named):
            print("      期望报错含 %r（或 %r）；实际输出前 400 字：" % (expect_kw, accept))
            print("      " + out[:400].replace("\n", "\n      "))
        return status == "PASS"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    results = []

    # M1：把一个读数改掉（0.43-0.48 -> 0.43-0.99）⇒ 数字集合核对必须红
    #   ★ 局限（如实记录）："数字在原稿某处出现过"抓不住【移花接木】——
    #     原稿别处本来就有 0.99 ⇒ 若被替换的值恰好原稿也有 ⇒ 本判据不红。
    #   ⇒ 这不是判据失效，是【判据能力边界】：摘要数字的"逐个定位到同一处出处"
    #     只能由独立核验脚本（verify_reorg.py）+ 人工逐个追溯来保证。
    #   ⇒ 本条变异用【原稿里没有的新数字】来测判据本身的有效性。
    results.append(run_variant(
        "M1 摘要引入新数字",
        '**3 次独立直调的分支彼此重叠 0.43–0.48',
        '**3 次独立直调的分支彼此重叠 0.43–0.777',
        "没有出处", target="SELF", accept="使用次数超过原稿"))

    # M1b：把摘要里一个读数改成一个【原稿别处也有】的数（移花接木）
    #   ⇒ 本判据【预期不红】⇒ 记录为【已知能力边界】，不计入通过项
    print("★ 反向变异 M1b（移花接木 ⇒ 预期【不红】⇒ 已知能力边界，不计入通过项）：")
    d = tempfile.mkdtemp(prefix="mut1b_")
    try:
        p = os.path.join(d, "reorg_paper.py")
        io.open(p, "w", encoding="utf-8").write(ORIG.replace(
            '**3 次独立直调的分支彼此重叠 0.43–0.48',
            '**3 次独立直调的分支彼此重叠 0.43–0.99', 1))
        r = subprocess.run([sys.executable, p], capture_output=True, text=True,
                           cwd=HERE, timeout=180)
        print("  M1b 0.48 -> 0.99（原稿别处有 0.99）⇒ rc=%s" % r.returncode)
        print("  ⇒ ★ 确认边界：脚本只能守『数字集合不超出原稿』，"
              "『逐个定位到同一处出处』须由独立核验 + 人工追溯保证")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print()

    # M2：★ 在【自检之前】篡改产出的一个读数 ⇒ 守恒必须红
    #   ★★ 关键：改【原稿】时输出会跟着变 ⇒ 两边同步 ⇒ 守恒必然一致 ⇒ 不红；
    #     改【写盘之后】时自检早已跑完 ⇒ 也不红。
    #     ⇒ 注入点必须在【out 组装完成、自检开始之前】。
    results.append(run_variant(
        "M2 产出读数被篡改",
        '    # ---------- 自检 1：关键锚点必须在 ----------',
        '    out = out.replace("承重维度中位 **4.50**", "承重维度中位 **4.75**")\n'
        '    # ---------- 自检 1：关键锚点必须在 ----------',
        "读数被改动", target="SELF",
        accept=["没有出处", "使用次数超过原稿", "读数被改动"]))

    # ★★ M1c：【原理性抓不到】⇒ 记为已知边界（★ 不假装能抓）
    #   这一处把摘要里的 2/6 改成 3/6 ⇒ ① "3" 在原稿出现 390 次 ⇒ 多重集超额判据不红
    #   ② 摘要那行是【重写】的 ⇒ 文字骨架与原稿任何行都不同 ⇒ "骨架相同⇒数字必同"也不红
    #   ⇒ 结论：【重写区】里的读数，机械判据只能守两档（数字不超出原稿 / 骨架相同的改写行）；
    #     ★ 真正的逐个定位到同一处出处，只能靠【人】核（⇒ 交付时附出处清单）。
    print()
    print("★ 已知边界 M1c（摘要重写区 ⇒ 改一位数读数 ⇒ 机械判据抓不到）：")
    print("  ⇒ 已在交付说明里如实登记；并附『摘要数字出处清单』供人工核对")

    # M2b：★ 在【自检之前】删掉产出的一行正文 ⇒ 行集合核对必须红
    results.append(run_variant(
        "M2b 产出少一行正文",
        '    # ---------- 自检 1：关键锚点必须在 ----------',
        '    out = out.replace("> ⇒ ⇒ **认知位置真的把 prior 改掉了。**\\n", "", 1)\n'
        '    # ---------- 自检 1：关键锚点必须在 ----------',
        "原稿有、新稿没有的内容", target="SELF"))

    # M3：把【正文里】的一个 § 引用指向不存在的小节 ⇒ 悬空检查必须红
    #   ★ 注入点必须在【自检 1（锚点）不会先拦】的位置。
    results.append(run_variant(
        "M3 制造悬空 § 引用",
        "失败信号是**零判官成本**的矛盾检测器（§4.3）",
        "失败信号是**零判官成本**的矛盾检测器（§9.9）",
        "悬空引用", target="SELF"))

    # M4：破坏关键锚点（HOLDOUT 标记）⇒ 锚点检查必须红
    results.append(run_variant(
        "M4 破坏 HOLDOUT 锚点",
        '"<!-- HOLDOUT_TABLE:BEGIN -->"',
        '"<!-- HOLDOUT_TABLE:BEGAN -->"',
        "锚点缺失", target="SELF"))

    # M5：把 §6.2c 特判删掉（退回一刀切）⇒ 应当【不红】（因为特判缺失时结果仍自洽）
    #     ★ 这条是【反向】变异：验证判据不会对"改回旧行为"误报。
    #     ★ 实际上 §6.2c 一刀切会指向 6.2e —— 那是"指错"，但本脚本不检查语义。
    #     ⇒ 预期：脚本仍 rc=0（因为 §6.2e 存在）⇒ 暴露【本脚本查不出指错】。
    print()
    print("★ 反向变异 M5（暴露判据盲区，不计入通过项）：")
    d = tempfile.mkdtemp(prefix="mut5_")
    try:
        p = os.path.join(d, "reorg_paper.py")
        io.open(p, "w", encoding="utf-8").write(ORIG.replace(
            'if re.search(r"仪器层|内容层|两种.?0|卡片没出来|解析失败|判官失败", ctx):\n                    return "§6.2e"',
            'if False:\n                    return "§6.2e"', 1))
        r = subprocess.run([sys.executable, p], capture_output=True, text=True,
                           cwd=HERE, timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
        print("  M5 删掉 6.2c 语境特判 ⇒ rc=%s" % r.returncode)
        print("  ⇒ ★ 判据盲区已确认：脚本只查「引用目标是否存在」，【不查指向是否正确】")
        print("  ⇒ ★ 语义正确性必须由【独立核验脚本】保证（这正是 verify_reorg 的职责）")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    ok = sum(1 for r in results if r)
    print("★ 变异注入：%d/%d 红在预期处" % (ok, len(results)))
    return 0 if ok == len(results) else 2


if __name__ == "__main__":
    sys.exit(main())
