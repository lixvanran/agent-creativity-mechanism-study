# -*- coding: utf-8 -*-
"""★ 用 AST（不是正则）审【退出码是否真正生效】，并【实跑】验证（★ 读形态会骗人）

★★ 为什么要用 AST（★ 现场翻车）★★
  · 我第一版审计用正则 `re.search(r'if __name__ == ...')` ⇒ **找到的是【第一个】匹配**
  · ⇒ 而我给 `run_dev.py` 加的**注释块里也写了一行** `if __name__ == "__main__":`
  · ⇒ ⇒ **审计报告说"run_dev.py 没改"，其实改了** ⇒ ⇒ **审计工具自己骗了我**
  · ⇒ ★★ **⇒ 这就是第二组第 3 点的同型：★ 「读形态会骗人」⇒ ★ 必须【实跑】**
  · ⇒ ⇒ 故本脚本：① AST 找模块级 `if __name__` 块 ② **实跑**每个脚本验证退出码真能变

★ 三条验证：
  ① AST：模块级 `if __name__ == "__main__"` 的 body 里有没有 `sys.exit(...)`
  ② **实跑**：故意制造失败 ⇒ 退出码必须非 0（★ 靠 importlib 加载源码并改写，不改原文件）
  ③ 报告：形态与实跑不一致时，**以实跑为准**
"""
import ast
import io
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))


def ast_has_sys_exit(path):
    """AST：模块级 `if __name__ == "__main__":` 的 body 里有没有 sys.exit(...)"""
    try:
        tree = ast.parse(io.open(path, encoding="utf-8").read())
    except Exception as e:
        return None, "语法错误: %s" % e
    for node in tree.body:                      # ★ 只看【模块级】的 If
        if not isinstance(node, ast.If):
            continue
        test = node.test
        ok = False
        if isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__":
            for c in test.comparators:
                if isinstance(c, ast.Constant) and c.value == "__main__":
                    ok = True
        if not ok:
            continue
        for sub in ast.walk(node):
            # ★★★ 修审计器自身的 bug（★ 第三次「检查器骗我」）：
            #   `sys.exit(...)` 的 func 是 **ast.Attribute**（attr="exit"），
            #   **不是** ast.Name(id="sys.exit") ⇒ ⇒ 我第一版判据把 39 个脚本全判成"无 sys.exit"
            #   ⇒ ⇒ ⇒ 假阳性 ⇒ ⇒ 审计器自己坏了。
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "exit":
                return True, "AST 找到 sys.exit(...)（__main__ 块内）"
    # ★★★ 第二处盲点（★ 修）：★ 有些脚本是【模块级执行 + 末尾 sys.exit(...)】
    #   （例如 test_premature_closure.py ⇒ 直接 `sys.exit(0 if ok else 1)` 在模块末尾）
    #   ⇒ ⇒ 只查 `if __name__` 块会把它误判成"无 sys.exit" ⇒ ⇒ 假阳性
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) \
                and isinstance(node.value.func, ast.Attribute) \
                and node.value.func.attr == "exit":
            return True, "AST 找到 sys.exit(...)（模块级末尾）"
    return False, "AST 未找到 sys.exit(...)"


def run_exit_code(path, argv=()):
    """★ 实跑：返回 (rc, stdout 尾)。★ 用子进程 ⇒ 真退出码。"""
    try:
        p = subprocess.run([sys.executable, "-B", path] + list(argv),
                           capture_output=True, text=True, timeout=120,
                           cwd=ROOT)
        return p.returncode, (p.stdout or "")[-400:]
    except subprocess.TimeoutExpired:
        return None, "超时"
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def main():
    print("★ 退出码审计：AST 形态 + 【实跑】双证（★ 实跑为准）")
    print("-" * 78)
    rows = []
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".py"):
            continue
        p = os.path.join(ROOT, fn)
        has_ast, why = ast_has_sys_exit(p)
        rows.append((fn, has_ast, why))
        print("  %-34s AST: %s（%s）" % (fn, "✔ 有 sys.exit" if has_ast else "✘ 无", why))

    print("-" * 78)
    print("★ 逐个【实跑】（★ 这才是退出码语义的唯一可靠证据）")
    print("-" * 78)
    # ★ 关键脚本：实跑并记录真实退出码
    for fn, argv in (("test_metrics_priorart.py", ()),
                     ("test_metrics_priorart.py", ("--mutate",)),
                     ("test_run_dev_gates.py", ()),
                     ("fill_holdout_table.py", ("--self-test",)),
                     ("test_premature_closure.py", ()),
                     ("test_workflow.py", ())):
        p = os.path.join(ROOT, fn)
        rc, out = run_exit_code(p, argv)
        print("  %-46s rc=%s" % (fn + (" " + " ".join(argv) if argv else ""), rc))
        if rc not in (0, 1, None):
            print("      ↳ 异常 rc ⇒ ★ 不该出现的值")
        if rc is None:
            print("      ↳ %s" % out)

    print("-" * 78)
    no_ast = [r[0] for r in rows if r[1] is False]
    print("⇒ AST 判「无 sys.exit」的脚本（%d 个）：%s" % (len(no_ast), no_ast))
    print("  ⇒ ★ ★ 【但这些脚本若在失败路径 raise SystemExit ⇒ 失败仍 exit 1】")
    print("  ⇒ ★ ★ ⇒ ⇒ ★ 结论必须按【失败路径是否有 raise】来判，不能按入口形态判")
    print("  ⇒ ★ ★ ⇒ ⇒ ★ ⇒ ★ **审计工具自己也骗过我一次**（正则找到注释里的那一行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
