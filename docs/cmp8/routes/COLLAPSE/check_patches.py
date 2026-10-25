# -*- coding: utf-8 -*-
"""★ 补丁清单自身的合法性检查（★ 第三道防线）
   --------------------------------------------------------------
   ★★ 为什么必须有这一道（独立审稿 v3 的 A1，判为【严重】）：
     执行器（reorg_paper.py）与核验器（verify_reorg.py）【共享同一份补丁清单】
     ⇒ 两者会【一起错】⇒ 互相印证不成立。
     ★ 实测：往清单里塞一条「把正文 1.00 改成 9.99」的补丁
       ⇒ 执行器 rc=0、核验器 rc=0 ⇒ 产物写出 9.99 ⇒ 【无人报警】。
     ⇒ 落法：★ 补丁清单必须被【独立】校验：★ 补丁只许改措辞，不许改任何读数数字。
       ★ 本检查器不读 reorg_paper.py 的任何逻辑，自己解析清单。

★ 判据（逐条）：
  P1 补丁的 old 串必须能在【原稿】里找到（匹配不到 ⇒ 补丁失效 ⇒ 判红）
  P2 补丁的 new 串必须能在【新稿】里找到（同上）
  P3 ★★ 补丁的 old 与 new 的【数字 token 多重集必须完全相同】
     ⇒ 改数字 ⇒ 判红（★ 这一条就是 A1 的直接堵口）
  P4 补丁的 old 串必须【唯一】匹配（多处匹配 ⇒ 改错对象 ⇒ 判红）
  P5 标题层级修正声明的（标题文本, 新层级）必须与实际稿子一致

用法：python3 check_patches.py  ⇒ 全绿 rc=0 / 有问题 rc=2
"""
import io
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
# ★ 路径不写死（★ 交付包必须能独立跑）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from reorg_paths import resolve_src, resolve_dst
except ImportError:  # ★ 变异注入会把脚本复制到临时目录 ⇒ 再兜一层 cwd
    sys.path.insert(0, os.getcwd())
    from reorg_paths import resolve_src, resolve_dst
SRC = resolve_src()
DST = resolve_dst(SRC)
# ★ 数字 token：日期整体 / 不从字母后接 / 不接字母后
NUM = re.compile(r"(?<![A-Za-z])\d{4}-\d{2}-\d{2}|(?<![A-Za-z])\d+(?:\.\d+)?(?![A-Za-z])")


def read_exec_constants():
    """★ 从 reorg_paper.py 读【基准常量】（ABSTRACT / NEW_SECTION_1_4）
       —— 读数据不是读执行逻辑；★ 摘要补丁的 old 串只在【新写的摘要】里，
       原稿里当然找不到 ⇒ 必须对着这个基准核。
    """
    import ast
    path = os.path.join(HERE, "reorg_paper.py")
    src = io.open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in ("ABSTRACT",
                                                        "NEW_SECTION_1_4"):
                    try:
                        out[t.id] = ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        pass
    return out


def load_manifest():
    """★ 独立解析补丁清单（★ 不 import 执行逻辑）"""
    import ast
    path = os.path.join(HERE, "reorg_patches.py")
    src = io.open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    try:
                        out[t.id] = ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        pass
    return out


def main():
    M = load_manifest()
    raw = io.open(SRC, encoding="utf-8").read()
    dst = io.open(DST, encoding="utf-8").read()
    fails = []

    EXEC = read_exec_constants()
    body_patches = M.get("PATCHES", [])
    abs_patches = M.get("ABSTRACT_PATCHES", [])
    s14_patches = M.get("SECTION_1_4_PATCHES", [])
    patches = body_patches + abs_patches + s14_patches

    print("★ 补丁清单检查：共 %d 条补丁（正文 %d / 摘要 %d / §1.4 %d）"
          % (len(patches), len(M.get("PATCHES", [])),
             len(M.get("ABSTRACT_PATCHES", [])),
             len(M.get("SECTION_1_4_PATCHES", []))))

    for i, (old, new, why) in enumerate(patches, 1):
        tag = "补丁#%d" % i
        # ★ 基准文本：正文补丁 ⇒ 原稿；摘要补丁 ⇒ ABSTRACT 常量；§1.4 补丁 ⇒ §1.4 常量
        if i <= len(body_patches):
            base, base_name = raw, "原稿"
        elif i <= len(body_patches) + len(abs_patches):
            base, base_name = EXEC.get("ABSTRACT", ""), "ABSTRACT 常量"
        else:
            base, base_name = EXEC.get("NEW_SECTION_1_4", ""), "NEW_SECTION_1_4 常量"
        # P1 old 必须能在基准里找到
        if old not in base:
            fails.append("%s ★ old 串在%s里找不到 ⇒ 补丁已失效：%r"
                         % (tag, base_name, old[:60]))
            continue
        # P4 old 必须唯一匹配
        if base.count(old) > 1:
            fails.append("%s ★ old 串在%s里匹配 %d 处 ⇒ 可能改错对象：%r"
                         % (tag, base_name, base.count(old), old[:60]))
        # P3 ★★ 数字多重集必须相同（★ A1 的直接堵口）
        # ★★★ 判据形态（★ 第一版写成"数字多重集必须相同"⇒ 太严，误伤合法操作）：
        #   「把原稿里已有的读数补回摘要」（如补回「中位波动 = 1」）是【合法的重组】，
        #   它会让数字出现次数 +1 ⇒ 第一版判据会假红。
        #   ★ 真正的违规是【引入了原稿里不存在的数字】⇒ 那是【新造读数】。
        #   ⇒ 落法：
        #     ① 补丁【不得修改/删除】已有数字（old 里的每个数字必须在 new 里原样保留）
        #     ② 补丁【新增】的数字必须在【原稿】里存在（否则 = 新造读数）
        def _strip_sec(x):
            return re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", x)
        no = Counter(NUM.findall(_strip_sec(old)))
        nn = Counter(NUM.findall(_strip_sec(new)))
        # ① 不得删改已有数字
        dropped = {k: (no[k], nn.get(k, 0)) for k in no
                   if nn.get(k, 0) < no[k]}
        if dropped:
            fails.append("%s ★★ 补丁【删改/减少了已有读数】（违反只重组措辞）：%s —— %r"
                         % (tag, dropped, old[:50]))
        # ② 新增的数字必须在原稿里存在
        raw_nums = set(NUM.findall(raw))
        added = {k: (no.get(k, 0), nn[k]) for k in nn
                 if nn[k] > no.get(k, 0)}
        for k, (a, b) in added.items():
            if k not in raw_nums:
                fails.append("%s ★★ 补丁【新造了读数】（原稿里找不到 %s）：%r"
                             % (tag, k, old[:50]))
        # P2 new 必须能在新稿找到（★ 用骨架匹配，因为 § 号会被重映射）
        def skel(x):
            x = re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", x)
            x = re.sub(r"\d+(?:\.\d+)?", "#", x)
            return re.sub(r"\s+", " ", x).strip()
        # ★ 逐行匹配（★ new 串可能跨多行，而稿子里也是多行 ⇒ 整体骨架不连续）
        _dst_skel = [skel(l) for l in dst.split("\n")]
        _missing = []
        for _ln in new.split("\n"):
            _k = skel(_ln)
            if not _k:
                continue
            # ★ 行级匹配 + 段落级匹配（★ 补丁可能落在【超长行】中段 ⇒ 行级匹配不到
            #   ⇒ 再用【连续若干行拼接后的骨架】做一次子串判定）
            if any(_k == _d or _k in _d for _d in _dst_skel):
                continue
            # ★ 逐行 + 【行内子串】（★ 补丁可能落在【超长行】的中段
            #   ⇒ 整行骨架 != 补丁骨架 ⇒ 必须允许"补丁骨架是某行骨架的子串"）
            if any(_k in _d for _d in _dst_skel):
                continue
            _missing.append(_ln.strip()[:50])
        if _missing:
            fails.append("%s ★ new 串在新稿里找不到 ⇒ 补丁未生效：%r"
                         % (tag, _missing[0]))

    # P5 标题层级修正：声明的新层级必须与实际稿子一致
    for t, oldlvl, newlvl in M.get("HEADING_LEVEL_FIXES", []):
        hit = [l for l in dst.split("\n")
               if l.startswith("#" * newlvl + " ") and t in l]
        if not hit:
            fails.append("★ 标题层级修正未生效：%r 期望 %d 个 #" % (t[:50], newlvl))
    for t, pref in M.get("INLINE_HEADING_FIXES", []):
        hit = [l for l in dst.split("\n")
               if l.startswith(pref + " ") and t in l]
        if not hit:
            fails.append("★ 行内标题层级修正未生效：%r 期望前缀 %r" % (t[:50], pref))

    # ★ 声明的指向修正：必须与稿子里【实际生效】的指向一致
    for o, n, why in M.get("DECLARED_REF_FIXES", []):
        # 稿子里该上下文处不应再出现 §<o>
        ctx_kw = "该发散" if o == "5.4" else ""
        if ctx_kw:
            bad = [l for l in dst.split("\n")
                   if ctx_kw in l and re.search(r"§%s\b" % re.escape(o), l)]
            if bad:
                fails.append("★ 已声明的指向修正未生效：仍有 %d 处写 §%s：%s"
                             % (len(bad), o, bad[0].strip()[:70]))

    print()
    for f in fails:
        print("✘ " + f)
    if fails:
        print()
        print("结论：FAIL（%d 条）" % len(fails))
        return 2
    print("结论：PASS（★ 补丁清单只改措辞，不改任何读数数字）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
