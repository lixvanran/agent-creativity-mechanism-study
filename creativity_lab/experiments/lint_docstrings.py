#!/usr/bin/env python3
"""★ **全仓语法自检**（★ 2026-10-24 一天犯 5 次 docstring 坑后固化为工具）

> 落点：`creativity_lab/experiments/lint_docstrings.py`
> ★ **退出码 0 = 全绿，可直接进 CI / pre-commit**（负责人已采纳为全项目交付必跑项）
>
> ## ★★ 为什么要它（★ 事件）
> ① 我连写多个带长 docstring 的文件，**多次**把模块 docstring 写成跨过 import/def
>    ⇒ 报错还指向**下一行** ⇒ **只能靠读代码才找得到** ⇒ ⇒ **写 lint 的人自己第一次尝试就在 docstring 里写了三引号，当场触发同一个 bug**
>    ⇒ ⇒ ★★ **「我以为我懂这个坑」≠「我不会犯这个坑」⇒ 唯一可靠的做法是上工具检查**
> ② ★★ **它第一次跑就抓出 `docs/cmp8/routes/COLLAPSE/eval/probe_effort.py:248` 从第一个 commit `fc4b0b7` 起的语法错误**
>    ⇒ **那个文件从来 import 不了** ⇒ ⇒ **一个从第一个 commit 就坏掉的文件能活到今天，说明当时只跑了"能跑的那几个脚本"**
>
> ## ★★ 五项检查（★ 负责人要求扩一档）
> | # | 检查 | 手段 |
> |:-:|---|---|
> | ① | 每个 `.py` 至少 `ast.parse` 通过 | `ast.parse` |
> | ② | 模块 docstring 必须在**第一条 import/def 之前**闭合 | AST 节点位置 |
> | ③ | docstring **内部**含三引号（高危：会让 docstring 提前闭合） | docstring 文本扫描 |
> | ~~④~~ | ~~行内双引号数为奇数~~ | ★ **已删**（误报 12/12 ⇒ 无判别力 ⇒ 交给 ⑤） |
> | ⑤ | ★ **全仓 `python3 -m compileall` 零语法错**（更快更底层） | `compileall -q -f` |
"""
import ast
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKIP = {".git", "__pycache__", "runs", "vendor"}


def check(path):
    """返回问题列表（空 = 通过）。"""
    try:
        src = open(path, encoding="utf-8").read()
    except Exception as e:
        # ★ ★ 2026-10-26 修：★ 原来读不了 ⇒ return [] ⇒ ★ ⇒ 【被当成「无问题」⇒ 报绿】★★
        #   ★ ⇒ ★ ★ 这正是我方 KI-16「★ 跳过检查并报绿是最阴的假绿 ★」的同族 ★★
        #   ★ ⇒ ★ 读不到输入时【必须响亮失败】，★ 不得静默跳过 ★★★ ★
        return ["%s: 读不了（★ 不许当成「无问题」★ ⇒ ★ 否则就是「跳过检查并报绿」★）：%s: %s"
                % (path, type(e).__name__, e)]
    issues = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        issues.append("%s: 语法错误（多半就是 docstring 没闭合）：%s" % (path, sys.exc_info()[1]))
        return issues
    body = tree.body
    if not body:
        return issues
    first = body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
            and isinstance(first.value.value, str):
        nxt = body[1] if len(body) > 1 else None
        if nxt is not None and hasattr(first, "end_lineno") and nxt.lineno <= first.end_lineno:
            issues.append("%s:%d 模块 docstring 与下一条语句重叠" % (path, first.lineno))
        inner = first.value.value
        if (chr(34) * 3) in inner or (chr(39) * 3) in inner:
            issues.append("%s:%d ★ docstring 内含三引号（高危：会让 docstring 提前闭合）" % (path, first.lineno))
    # ★★ ④ 「行内双引号数为奇数」—— ★ 已删除（★ 2026-10-24 实测：误报 12/12，全是
    #    `r'"..."'` / `find('"', a)` 这类【另一种引号包裹的字符串里含引号】的合法写法
    #    ⇒ ⇒ 这个判据【没有判别力】⇒ ⇒ ★ 一个误报率高的检查项比没有更糟（会让人忽略真问题）
    #    ⇒ ⇒ 「未闭合引号」的真判据交给 ⑤ compileall（编译器级检查）
    return issues


def main():
    issues = []
    n = 0
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in files:
            if f.endswith(".py"):
                n += 1
                issues += check(os.path.join(root, f))
    print("== ① ast.parse + ② docstring 闭合 + ③ 三引号嵌套（%d 个 .py）==" % n)
    r = subprocess.run([sys.executable, "-m", "compileall", "-q", "-f", ROOT],
                       capture_output=True, text=True)
    if r.returncode != 0:
        bad = [l for l in (r.stdout + r.stderr).splitlines() if "rror" in l]
        issues.append("⑤ compileall 失败：%s" % ("; ".join(bad[:5]) or r.stderr[:300]))
    else:
        print("   ⑤ compileall：全仓零语法错 ✔")
    if issues:
        print("  ✘ %d 个问题：" % len(issues))
        for i in issues:
            print("     - %s" % i)
        return 1
    print("  ✔ 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
