# -*- coding: utf-8 -*-
"""★ 路径解析（★ 交付包必须能独立跑 ⇒ 禁止硬编码 /workspace/lab）

★★ 硬编码绝对路径的毛病：第三方拿到 zip 解压后，脚本直接报「源稿不存在」
   ⇒ 整个复现链断在第一步 ⇒ 交付物名存实亡。

★ 解析顺序（★ 先环境变量、再相对脚本、再沙箱兜底）：
  ① 环境变量 REORG_SRC / REORG_DST（显式覆盖优先）
  ② 脚本同目录
  ③ 脚本的上级目录（仓库布局：<repo>/docs/cmp8/routes/COLLAPSE/ ⇒ 上溯到 docs/cmp8/）
  ④ /workspace/lab/（当前沙箱的兜底）

★ ★ 为什么【路径解析可以共享】而【判定逻辑绝不共享】：
  ★ 执行器与核验器共享**判定逻辑**会「一起错」⇒ 核验失效 ⇒ 那是红线。
  ★ 而路径解析只决定【能否打开哪个文件】⇒ 失败会**立刻显式报错**，
  ★ 不会静默读到错误内容 ⇒ 共享它不产生「一起错」的风险。
  ★ ⇒ 边界：共享【定位】，隔离【判定】。
"""
import os


def resolve_src(name="PAPER-2026-10-25.md", env="REORG_SRC"):
    v = os.environ.get(env)
    if v:
        if not os.path.exists(v):
            raise SystemExit("✘ 环境变量 %s 指向不存在的文件：%s" % (env, v))
        return os.path.abspath(v)
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [
        os.path.join(here, name),
        os.path.join(os.path.dirname(os.path.dirname(here)), name),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(here))), name),
        os.path.join("/workspace/lab", name),
    ]
    for c in cands:
        if os.path.exists(c):
            return os.path.abspath(c)
    raise SystemExit(
        "✘ 找不到源稿 %s\n  已试：\n%s\n"
        "  ⇒ 用环境变量 %s 显式指定即可。" %
        (name, "\n".join("    - " + c for c in cands), env))


def resolve_dst(src_path, name="PAPER-三组-学习自迭代治塌缩-2026-10-25.md",
                env="REORG_DST"):
    v = os.environ.get(env)
    if v:
        return os.path.abspath(v)
    return os.path.join(os.path.dirname(os.path.abspath(src_path)), name)
