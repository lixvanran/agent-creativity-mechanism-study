# -*- coding: utf-8 -*-
"""★ 闸门自身的证伪：把重组链搞坏 ⇒ 闸门必须红
   --------------------------------------------------------------
   ★★★ 纪律（本轮血买来的）：
     「所有检查都 PASS」本身**不能证明**闸门有效 —— 闸门可能因为
     脚本路径错了 / 异常被吞 / 退出码被忽略而**恒绿**。
     ⇒ 必须【故意制造失败并实测】。
     ★ 同族：★ 「有红就行」只证明「脚本某处会红」，不证明「我测的那一处被测到了」
       ⇒ 判据必须**点名预期的那一处**。
   用法：python3 test_check_bundle_mutations.py
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# 闸门要跑的全部脚本（复制到临时目录时必须一起复制）
NEEDED = [
    "reorg_paper.py", "reorg_patches.py", "verify_reorg.py",
    "check_patches.py", "test_reorg_mutations.py",
    "test_verify_reorg_mutations.py", "test_check_patches_mutations.py",
    "check_bundle.py",
]


def stage():
    d = tempfile.mkdtemp(prefix="bmut_")
    for f in NEEDED:
        src = os.path.join(HERE, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(d, f))
    return d


def case(name, mutate, expect_kw=None, want_gate_rc=7):
    """★ mutate: 在临时目录上做的破坏动作；返回是否红在预期处"""
    d = stage()
    try:
        mutate(d)
        r = subprocess.run([PY, os.path.join(d, "check_bundle.py")],
                           capture_output=True, text=True, cwd=d, timeout=900)
        out = (r.stdout or "") + (r.stderr or "")
        red = r.returncode != 0
        # ★ 闸门拦截码 = 7（脚本崩 = 1）⇒ 崩不算"红在预期处"
        right_rc = (r.returncode == want_gate_rc)
        named = (expect_kw in out) if expect_kw else True
        ok = red and right_rc and named
        print("[%s] %-36s rc=%-3d 红=%-5s 码对=%-5s 点名=%-5s" %
              ("PASS" if ok else "FAIL", name, r.returncode, red, right_rc, named))
        if not ok:
            print("      期望 rc=%d 且输出含 %r；实际尾部：" %
                  (want_gate_rc, expect_kw))
            print("      " + out[-700:].replace("\n", "\n      "))
        return ok
    finally:
        shutil.rmtree(d, ignore_errors=True)


def m_corrupt_manifest(d):
    """★ 破坏补丁清单 ⇒ ③ 必须红（而且要点名）"""
    p = os.path.join(d, "reorg_patches.py")
    s = io.open(p, encoding="utf-8").read()
    s = s.replace("`mm=vote`（间距 0.500、不并列）**（★ **本句的「稳健」限定在",
                  "`mm=vote`（间距 8.888、不并列）**（★ **本句的「稳健」限定在", 1)
    io.open(p, "w", encoding="utf-8").write(s)


def m_always_green(d):
    """★★ M3'：把 ③ 换成【恒真版】（永远返回 0）——
       ★ 这测的是【自证机制必须有独立证伪手段】：
         ③ 自己说 PASS 没用 ⇒ 必须由 ⑥（对 ③ 的变异注入）抓出来。
       ★ 若没有 ⑥，恒真版 ③ 会让整个闸门绿 ⇒ 闸门形同虚设。
    """
    p = os.path.join(d, "check_patches.py")
    io.open(p, "w", encoding="utf-8").write(
        "# -*- coding: utf-8 -*-\n"
        "import sys\n"
        "print('★ 补丁清单检查：PASS（★ 恒真版，故意造）')\n"
        "sys.exit(0)\n")


def m_corrupt_output(d):
    """★ 破坏【核验器本身】⇒ ② 崩 ⇒ 闸门必须报崩（rc=1）"""
    p = os.path.join(d, "verify_reorg.py")
    s = io.open(p, encoding="utf-8").read()
    s = s.replace("def main(", "def main():\n    raise RuntimeError('★ 故意崩溃')\n\n\ndef _unused(", 1)
    io.open(p, "w", encoding="utf-8").write(s)


def m_crash_stage(d):
    """★ 让 ① 崩溃 ⇒ 闸门必须【报崩】而不是当成"红" ⇒ rc=1"""
    p = os.path.join(d, "reorg_paper.py")
    s = io.open(p, encoding="utf-8").read()
    s = s.replace("def main(", "def main():\n    raise RuntimeError('★ 故意崩溃')\n\n\ndef _unused(", 1)
    io.open(p, "w", encoding="utf-8").write(s)


def m_kill_checker(d):
    """★ 删掉 ③ ⇒ 闸门必须报【脚本缺失】而不是静默跳过"""
    os.remove(os.path.join(d, "check_patches.py"))


def main():
    res = []
    # ★ M1：清单里塞一个新读数 ⇒ ① 会因锚点/数字校验拒绝（判据红）⇒ 闸门 rc=7
    #   ★ 实测：被 ② 核验器【更早】抓到（"原稿有、新稿没有的数字 token"）
    #     ⇒ 比 ③ 先红 ⇒ 这更好（关卡更靠前），关键词按实际改。
    res.append(case("M1 补丁清单改读数 ⇒ 闸门拦截(rc=7)",
                    m_corrupt_manifest, "数字 token", want_gate_rc=7))
    # ★ M2：核验器崩 ⇒ 闸门【报崩】rc=1（★ 与"判据红"可区分）
    res.append(case("M2 核验器崩 ⇒ 闸门报崩(rc=1)",
                    m_corrupt_output, "崩溃", want_gate_rc=1))
    # ★ M3：① 崩 ⇒ 闸门【报崩】rc=1
    res.append(case("M3 执行器崩 ⇒ 闸门报崩(rc=1)",
                    m_crash_stage, "崩溃", want_gate_rc=1))
    # ★ M4：③ 被换成恒真版 ⇒ ③ 自己说 PASS ⇒ 必须由 ⑥ 抓出来 ⇒ 闸门 rc=7
    #   （★★ 这条是"自证机制必须有独立证伪手段"的实测）
    res.append(case("M4 检查器恒真版 ⇒ 被 ⑥ 抓出(rc=7)",
                    m_always_green, "变异", want_gate_rc=7))
    # ★ M5：删掉检查器 ⇒ ③ 报 MISS ⇒ 短路 ⇒ rc=7
    res.append(case("M5 删掉检查器 ⇒ 报缺失(rc=7)",
                    m_kill_checker, "MISS", want_gate_rc=7))
    print()
    ok = sum(1 for r in res if r)
    print("★ 闸门变异注入：%d/%d 红在预期处" % (ok, len(res)))
    return 0 if ok == len(res) else 2


if __name__ == "__main__":
    sys.exit(main())
