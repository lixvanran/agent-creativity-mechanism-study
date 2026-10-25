# -*- coding: utf-8 -*-
"""★ 变异注入：验证 check_patches.py 能抓住【补丁清单里的违规】
   --------------------------------------------------------------
   ★★ 这一道是第三道防线（独立审稿 v3 的 A1，判为【严重】）：
     执行器与核验器【共享同一份补丁清单】⇒ 两者会一起错 ⇒ 互相印证不成立。
     ⇒ 所以清单本身必须被【独立】校验。
   ★ 变异：
     E1 补丁改读数数字（1.00 -> 9.99）⇒ 必须红
     E2 补丁删掉已有读数 ⇒ 必须红
     E3 补丁的 old 串在原稿里不存在（失效补丁）⇒ 必须红
     E4 补丁的 old 串在原稿里多处匹配（可能改错对象）⇒ 必须红
     E5 补丁引入原稿没有的新读数 ⇒ 必须红
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "reorg_patches.py")
CHK = os.path.join(HERE, "check_patches.py")
ORIG = io.open(MANIFEST, encoding="utf-8").read()


def run(name, old, new, expect_kw):
    assert old in ORIG, "★ 清单锚点不存在：%r" % old[:60]
    d = tempfile.mkdtemp(prefix="pmut_")
    try:
        # 复制清单 + 检查器到临时目录（检查器靠 __file__ 找清单 ⇒ 同目录即可）
        m2 = os.path.join(d, "reorg_patches.py")
        io.open(m2, "w", encoding="utf-8").write(ORIG.replace(old, new, 1))
        shutil.copy2(CHK, os.path.join(d, "check_patches.py"))
        # ★ 检查器要读 reorg_paper.py 的【基准常量】⇒ 必须一起复制
        shutil.copy2(os.path.join(HERE, "reorg_paper.py"),
                     os.path.join(d, "reorg_paper.py"))
        # ★ 检查器还要 import reorg_paths（路径解析）⇒ 一并复制
        shutil.copy2(os.path.join(HERE, "reorg_paths.py"),
                     os.path.join(d, "reorg_paths.py"))
        r = subprocess.run([sys.executable, os.path.join(d, "check_patches.py")],
                           capture_output=True, text=True, cwd=d, timeout=120)
        out = (r.stdout or "") + (r.stderr or "")
        red = r.returncode != 0
        named = expect_kw in out
        status = "PASS" if (red and named) else "FAIL"
        print("[%s] %-34s rc=%-3s 红=%-5s 点名预期处=%-5s" %
              (status, name, r.returncode, red, named))
        if not (red and named):
            print("      期望报错含 %r；实际输出：" % expect_kw)
            print("      " + out[-500:].replace("\n", "\n      "))
        return status == "PASS"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    res = []

    # E1：★ 补丁【改读数】（★ 必须改【new 串】—— old 串是基准，改它会被
    #     "old 找不到"更早的判据抓住 ⇒ 测不到数字判据）
    res.append(run("E1 补丁改读数",
                    '"`mm=vote`（间距 0.500、不并列）**（★ **本句的「稳健」限定在',
                    '"`mm=vote`（间距 9.999、不并列）**（★ **本句的「稳健」限定在',
                    "新造了读数"))

    # E2：补丁删掉已有读数
    res.append(run("E2 补丁删读数",
                    '"`mm=vote`（间距 0.500、不并列）**（★ **本句的「稳健」限定在',
                    '"`mm=vote`（间距、不并列）**（★ **本句的「稳健」限定在',
                    "删改/减少了已有读数"))

    # E3：old 串不存在（失效补丁）
    res.append(run("E3 补丁 old 不存在",
                    '"⇒ ⇒ **唯一稳健的偏好是 15 题版的 `mm=vote`（间距 0.500、不并列）**"',
                    '"⇒ ⇒ **唯一稳健的偏好是 16 题版的 `mm=vote`（间距 0.500、不并列）**"',
                    "找不到"))

    # E4：old 串多处匹配（改错对象）—— ★ 用一个原稿里出现 ≥2 次的串
    #   （★ "**不可分辨**" 在原稿里出现 4 次 ⇒ 触发"可能改错对象"判据）
    res.append(run("E4 old 多处匹配",
                    '"⇒ ⇒ **唯一稳健的偏好是 15 题版的 `mm=vote`（间距 0.500、不并列）**"',
                    '"**不可分辨**"',
                    "匹配"))

    # E5：补丁引入原稿没有的新读数
    res.append(run("E5 引入新读数",
                    '限定在【本段这三个维度】内**；"',
                    '限定在【本段这三个维度】内（口径 7.77）**；"',
                    "新造了读数"))

    print()
    ok = sum(1 for r in res if r)
    print("★ 补丁清单变异注入：%d/%d 红在预期处" % (ok, len(res)))
    return 0 if ok == len(res) else 2


if __name__ == "__main__":
    sys.exit(main())
