# -*- coding: utf-8 -*-
"""★ 打包：论文重组稿 + 复现链（自包含）
   --------------------------------------------------------------
   ★ 硬要求（来自真实事故）：
     ① 非 ASCII 文件名必须带 UTF-8 标志位（flag_bits |= 0x800）
        ⇒ 系统 zip 不设、zip -UN=UTF8 也不管用 ⇒ 必须用 Python zipfile
     ② 包内清单必须【全量】核对，不能抽样
     ③ 先建临时包 → 校验 → 再替换正式包
     ④ 中文名在解压端不能乱码 ⇒ 解压后逐字节比对
"""
import hashlib
import io
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else "/workspace/lab/治塌缩-论文重组稿与复现链-2026-10-25.zip"
STAGE = "/workspace/lab/cmp8repo/docs/cmp8"
COLL = os.path.join(STAGE, "routes/COLLAPSE")

# (包内相对路径, 源绝对路径)
ITEMS = [
    ("README-交付说明.md", "/workspace/lab/交付-三组-论文重组稿-2026-10-25.md"),
    ("论文/PAPER-三组-学习自迭代治塌缩-2026-10-25.md",
     os.path.join(STAGE, "PAPER-三组-学习自迭代治塌缩-2026-10-25.md")),
    ("论文/原稿-PAPER-2026-10-25.md",
     os.path.join(STAGE, "PAPER-2026-10-25.md")),
    ("复现链/reorg_paper.py", os.path.join(COLL, "reorg_paper.py")),
    ("复现链/reorg_patches.py", os.path.join(COLL, "reorg_patches.py")),
    ("复现链/reorg_paths.py", os.path.join(COLL, "reorg_paths.py")),
    ("复现链/verify_reorg.py", os.path.join(COLL, "verify_reorg.py")),
    ("复现链/check_patches.py", os.path.join(COLL, "check_patches.py")),
    ("复现链/check_bundle.py", os.path.join(COLL, "check_bundle.py")),
    ("复现链/test_reorg_mutations.py", os.path.join(COLL, "test_reorg_mutations.py")),
    ("复现链/test_verify_reorg_mutations.py",
     os.path.join(COLL, "test_verify_reorg_mutations.py")),
    ("复现链/test_check_patches_mutations.py",
     os.path.join(COLL, "test_check_patches_mutations.py")),
    ("复现链/test_check_bundle_mutations.py",
     os.path.join(COLL, "test_check_bundle_mutations.py")),
    ("执行记录/EXEC-LOG-三组-2026-10-25-冲刺.md",
     "/workspace/lab/cmp8repo/docs/交接/EXEC-LOG-三组-2026-10-25-冲刺.md"),
]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def main():
    missing = [d for _, d in ITEMS if not os.path.isfile(d)]
    if missing:
        raise SystemExit("✘ 源文件缺失：%s" % missing)

    tmp = OUT + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, src in ITEMS:
            # ★ 关键：非 ASCII 名必须带 UTF-8 标志位
            zi = zipfile.ZipInfo(arc, date_time=(2026, 10, 25, 12, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.flag_bits |= 0x800
            zi.external_attr = 0o644 << 16
            with open(src, "rb") as f:
                z.writestr(zi, f.read())

    # ── 校验①：清单全量核对 + UTF-8 标志位 ──────────────────────
    with zipfile.ZipFile(tmp) as z:
        names = z.namelist()
        bad = [n for n in names
               if not any(i.flag_bits & 0x800 for i in z.infolist() if i.filename == n)]
        if bad:
            raise SystemExit("✘ 缺 UTF-8 标志位的成员：%s" % bad)
        if sorted(names) != sorted(a for a, _ in ITEMS):
            raise SystemExit("✘ 清单不符：包内 %d / 期望 %d" %
                             (len(names), len(ITEMS)))
        for arc, src in ITEMS:
            a = hashlib.sha256(z.read(arc)).hexdigest()
            b = sha(src)
            if a != b:
                raise SystemExit("✘ 成员内容不一致：%s" % arc)
    print("✔ 清单全量核对通过（%d 成员，逐字节一致，UTF-8 标志位齐）" % len(ITEMS))

    # ── 校验②：解压端逐字节复现 ──────────────────────────────
    d = tempfile.mkdtemp(prefix="unz_")
    try:
        with zipfile.ZipFile(tmp) as z:
            z.extractall(d)
        for arc, src in ITEMS:
            p = os.path.join(d, arc)
            if not os.path.isfile(p):
                raise SystemExit("✘ 解压后缺文件：%s" % arc)
            if sha(p) != sha(src):
                raise SystemExit("✘ 解压后内容不一致：%s" % arc)
        print("✔ 解压后逐字节复现通过")

        # ── 校验③：在解压目录独立跑一遍复现链 ──────────────────
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(d, "复现链/check_bundle.py")],
                           capture_output=True, text=True,
                           cwd=os.path.join(d, "复现链"), timeout=900)
        out = (r.stdout or "") + (r.stderr or "")
        tail = [l for l in out.splitlines() if l.startswith("★ 重组稿收口闸门")]
        if r.returncode != 0:
            print("⚠ 解压目录内闸门未通过（rc=%d）：" % r.returncode)
            print(out[-1500:])
            raise SystemExit("✘ 解压后复现链跑不通 ⇒ 不出正式包")
        print("✔ 解压目录内独立跑复现链：%s" % (tail[0] if tail else "PASS"))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ── 校验④：先验后换 ───────────────────────────────────────
    if os.path.exists(OUT):
        os.remove(OUT)
    os.replace(tmp, OUT)
    print("✔ 正式包：%s（%d 字节）" % (OUT, os.path.getsize(OUT)))
    print("  sha256: %s" % sha(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
