#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
★ 【自测默认模板】—— ★ 新写测试/变异测试时【必须】用它，不要再自己复制一份 check() ★
============================================================================

★ **★ 为什么有这个模块（★ 2026-10-25 实测坐实）★★**
------------------------------------------------------------------------
★ 我这个仓里有 **5 份各自复制的 `check()`**（★ `test_state_layer.py` /
★ `test_endstep_metrics.py` / `test_endstep_newlost_mutations.py` /
★ `test_health_guard_mutations.py` / `lint_docstrings.py`）★★
★ ⇒ **★ AST 归一化后实测：★ 它们已经漂成了【3 种不同结构】★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 这就是「复制粘贴的默认模板会烂」的【硬证据】★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 所以本模块【不是洁癖】：★ 是【有实证的收敛】★★**

★ **★ 两条硬规则（★ 主会话 2026-10-25 明文要求）★★**
------------------------------------------------------------------------
★ **R1 · 自测一律用 `check()`，★ 不用裸 `assert`。**
★   ⇒ ★ 理由：★ 裸 `assert` 抛 `AssertionError`（★ **没有 `✘` 前缀**）
★   ⇒ ⇒ ★ ⇒ 变异失败时【无法与崩溃区分】⇒ ⇒ ★ ⇒ **变异注入会假绿** ★★

★ **R2 · 变异失败必须被【断言失败】分类；★ 崩溃单独算【没测到东西】。**
★   ⇒ ★ **★ 关键区分（★ 极易搞错）★★**：
★   ⇒   - `AssertionError` 抛在【测试脚本】里 ⇒ ⇒ **我方断言失败 ⇒ 算抓住** ★★
★   ⇒   - `AssertionError` 抛在【被测代码】里 ⇒ ⇒ **被测代码自己崩了 ⇒ 不算抓住** ★★
★   ⇒ ⇒ ★ ⇒ **★ ⇒ 光看"是不是 AssertionError"是不够的，★ ⇒ ⇒ ★ ⇒ ★ ★ **★ ⇒ 必须看【traceback 最后一帧在哪个文件】★★**

★ **★ 第三条（★ 从 2026-10-25 的自首里长出来的）★★**
------------------------------------------------------------------------
★ **R3 · 任何自检判据，★ 都必须【变异一下被测逻辑】证明它会红。**
★   ⇒ ★ 否则"自检全绿"只是"没人改"。
★   ⇒ ★ 本模块提供 `classify_failure()` 就是为了让【"红"这件事本身可判定】。

★ **★ 用法（★ 新工具的默认模板）★★**
------------------------------------------------------------------------
★   from selftest_kit import check, suite, classify_failure, AssertionFailure
★
★   def main():
★       with suite() as s:
★           s.run("① 某某检查", lambda: check("某某", cond, detail))
★       return s.exit_code
★
★   ★ 变异侧：
★   rc, out = run_mutant(...)
★   kind = classify_failure(out, tested_files=[TARGET])
★   assert kind == "assertion", "★ 只崩了（★ 崩溃不算 ⇒ ⇒ 【没测到东西】）"
"""

from __future__ import annotations

import sys
import traceback
from typing import Callable, Iterable, List, Optional, Sequence

__all__ = [
    "check",
    "suite",
    "AssertionFailure",
    "classify_failure",
    "last_traceback_frame",
]

# ★ ★ 「✘」是【断言失败】的唯一【可打印标记】★★
# ★ ⇒ ⇒ ★ 任何脚本只要打这个前缀行，★ 变异侧就能无歧义地识别它 ★★
FAIL_MARK = "✘"


class AssertionFailure(Exception):
    """★ 【我方断言失败】的显式类型（★ 比裸 AssertionError 更可读）★。"""


def check(name: str, cond: bool, detail: str = "") -> bool:
    """★ 打印一行检查结果；★ 失败时抛 `AssertionFailure`（★ **不是裸 assert**）★★。

    ★ **R1 的执行点**：★ 失败时抛的是**带 `✘` 前缀打印 + 显式类型**，
    ★ ⇒ ⇒ ★ ⇒ 变异侧可以无歧义地把它归到【断言失败】而不是【崩溃】。

    ★ ★★★ **R11（★ 2026-10-26 补 · ★ 两组各踩一次的同一个坑 ★）★★**
    ★ **`cond` 必须是【立即求值】的布尔值，★ 绝不接受 lambda。★★**
    ★ ⇒ 因为 `bool(cond)` 会把**函数对象**也判成 True ⇒ ★ **传 lambda ⇒ 恒绿假绿 ★**
    ★ ⇒ ★ **断言从来没被求值过，★ 却看起来全过** ★ ⇒ ★ **这是最危险的一类假绿** ★
    ★ ⇒ ★ **正确写法**：`check("x", len(a) == 3)` ｜ `check("x", f(a) > 0)`
    ★ ⇒ ★ **错误写法**：`check("x", lambda: len(a) == 3)`
    ★ ⇒ ★ **★ 若确实要传惰性条件，★ 请自己先求值：`check("x", bool(fn()))` ★**
    ★ ★ **两条同型案例**：★ ① 本组 2026-10-26：★ `check(name, cond)` 传 lambda
    ★ ⇒ 15 条断言全在空转 ★ ⇒ ★ 改掉后测试立刻抓出两个真问题 ★
    ★ ② 第 1 层论证线 2026-10-26 独立踩同一个坑（★ 他们的 `check()` 同款 ★）★
    ★ ⇒ ★ **⇒ 通则：★ 「判据的载体不对，★ 于是判据从没被求值过」★★
    """
    ok = bool(cond)
    if ok:
        print("  ✔ %s" % name)
    else:
        print("  %s %s  %s" % (FAIL_MARK, name, detail))
        raise AssertionFailure("%s  %s" % (name, detail))
    return True


class suite:
    """★ 极简自测套件：★ 收集失败、★ 统一退出一对。

    ★ **★ 为什么不做成 pytest（★ 2026-10-25）★★**
    ------------------------------------------------------------------
    ★ 本仓的自测要能在【任意 cwd】下被 `python3 -B <file>` 直接跑起来（★ 变异注入
    ★ 侧要 subprocess 调它并抓 stdout）⇒ ⇒ ★ ⇒ 依赖 pytest 会引入【环境假设】★★
    ★ ⇒ ⇒ ★ ⇒ 所以保持【零依赖 + 逐项打印 + exit code 语义】★★
    """

    def __init__(self, title: str = "自测") -> None:
        self.title = title
        self.passed = 0
        self.failed: List[str] = []
        self._stack: List[str] = []

    # ── 上下文管理：★ 让失败可归组 ──
    def __enter__(self) -> "suite":
        print("== ★ %s ==" % self.title)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # ★ ★★ 2026-10-26 修：★ 统一退出码 ★★
        #   ★ 原实现只收集失败、★ 但【不决定退出码】⇒ ⇒ ★ 调用方普遍写
        #   `return 0` ⇒ ⇒ ★ **任何失败都 exit 0** ⇒ ⇒ ★ **退出码在撒谎** ★
        #   ⇒ ⇒ ★ 本仓 10 个测试文件全都犯了这一条（★ 2026-10-26 实测 ★）
        #   ⇒ ⇒ ★ 修法（★ 在工具里一次修好，★ 10 个文件零改动 ★）：
        #   ★ 退出前先打印汇总；★ 有失败 ⇒ ★ `sys.exit(1)`。
        #   ★ 为何用 `sys.exit` 而不是 raise：★ raise 会打出 traceback ⇒
        #   ★ 变异侧要靠 traceback 最后一帧分类 ⇒ ★ 而 SystemExit 不打 traceback ⇒
        #   ★ ★ 且分类器的第一条规则是「有 ✘ 前缀行 ⇒ assertion」⇒ ⇒ ★ 不受影响 ★★
        if exc_type is not None:
            return False  # ★ 不吞异常 ⇒ ★ 让 traceback 打出来（★ 变异侧要分类它）★★
        code = self.report()
        if code:
            sys.exit(code)
        return False

    def group(self, name: str) -> None:
        self._stack.append(name)
        print("-- ★ %s --" % name)

    def run(self, name: str, fn: Callable[[], bool]) -> bool:
        full = " / ".join(self._stack + [name])
        try:
            fn()
        except AssertionFailure as e:
            self.failed.append(full)
            print("  %s %s" % (FAIL_MARK, full))
            return False
        except Exception as e:  # ★ ★ 崩溃（★ 不算断言失败）★★
            self.failed.append(full)
            print("  %s %s  ★ 崩溃：%s: %s" % (FAIL_MARK, full, type(e).__name__, e))
            traceback.print_exc()
            return False
        self.passed += 1
        return True

    def report(self) -> int:
        print()
        if self.failed:
            print("%s %s：★ %d 项失败 ⇒ %d/%d" % (
                FAIL_MARK, self.title, len(self.failed), self.passed, self.passed + len(self.failed)))
            for f in self.failed:
                print("   - %s" % f)
            return 1
        print("✔ %s：★ 全部通过（%d 项）" % (self.title, self.passed))
        return 0


# ══════════════════════════════════════════════════════════════════════
# ★ 变异侧的分类器（★ R2 的执行点）★★
# ══════════════════════════════════════════════════════════════════════

def last_traceback_frame(text: str) -> Optional[str]:
    """★ 从一段输出文本里抽出【traceback 最后一帧的文件路径】★★。

    ★ Python 的 traceback 末行形如：★ `  File "/path/to/file.py", line 42, in f` ★
    ★ ⇒ ⇒ ★ 取**最后**出现的那一行（★ 最深的栈帧）★★
    """
    last = None
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith('File "') and ", line " in s:
            last = s
    if last is None:
        return None
    # ★ 抽出路径部分
    try:
        return last.split('File "', 1)[1].split('"', 1)[0]
    except Exception:
        return None


def classify_failure(
    out: str,
    *,
    tested_files: Sequence[str] = (),
    stderr: str = "",
) -> str:
    """★ 把一次失败的输出分类成：**assertion** / **crash** / **none** ★★。

    ★ **★ 判据顺序（★ 不可颠倒）★★**
    ------------------------------------------------------------------
    ★ 1) **有 `✘` 前缀行** ⇒ ⇒ **"assertion"**
    ★    ⇒ ★ 理由：★ `✘` 是我方 `check()` 的【唯一标记】⇒ ⇒ ★ ⇒ 无歧义 ★★
    ★ 2) **无 `✘` 行、但有 `AssertionError`** ⇒ ⇒ 【看 traceback 最后一帧】：
    ★    - 最后一帧落在**被测文件**里 ⇒ ⇒ **"crash"**
    ★      （★ 被测代码自己抛的 ⇒ ★ 变异引入了崩溃 ⇒ ★ **不算抓住**）★★
    ★    - 最后一帧落在**测试脚本**里（或不在被测文件里）⇒ ⇒ **"assertion"**
    ★      （★ 裸 `assert` 抛在我方脚本里 ⇒ ★ 那也是我方断言失败）★★
    ★ 3) **其他（ImportError / 其它异常 / 无输出）** ⇒ ⇒ **"crash"**

    ★ **★ 已知的历史坑（★ 2026-10-25 自首）★★**
    ------------------------------------------------------------------
    ★ 我写 `health_guard` 的第一版自测用了**裸 `assert`** ⇒ ⇒ ★ ⇒
    ★ 变异失败时抛 `AssertionError`（★ **没有 `✘` 前缀**）⇒ ⇒ ★ ⇒
    ★ 被我的检查归类成【崩溃】⇒ ⇒ ★ ⇒ **3/5 变异"只崩了"** ★★
    ★ ⇒ ⇒ ★ ⇒ **修法就是本模块：★ 自测改用 `check()`（★ 打 `✘`）★★**
    """
    combined = (out or "") + ("\n" + (stderr or "") if stderr else "")
    if any(ln.strip().startswith(FAIL_MARK) for ln in combined.splitlines()):
        return "assertion"

    if "AssertionError" in combined:
        frame = last_traceback_frame(combined)
        if frame is None:
            # ★ 没有 traceback 帧可查 ⇒ ⇒ ★ ⇒ **按"我方断言"处理**（★ 保守方向：★ 不放过失败）★★
            return "assertion"
        norm = frame.replace("\\", "/")
        for tf in tested_files:
            tfn = str(tf).replace("\\", "/")
            if tfn in norm or norm.endswith(tfn):
                # ★ ★ 最后一帧在【被测文件】里 ⇒ ⇒ ★ ⇒ 被测代码自己抛的 ⇒ ⇒ 崩溃 ★★
                return "crash"
        return "assertion"

    # ★ ★ 4) 【★ 无任何失败特征 ⇒ ⇒ "none"（★ 不是 crash）★★】★★
    # ★ ★ 顺序很重要：★ ★ 这条必须【在 "其他 ⇒ crash" 之前】★★
    # ★ ★ ⇒ ★ 否则 "all good" 会被归成 crash（★ ★ 我第一版就犯了这个 ⇒ 已被自测抓到）★★
    if "Traceback" not in combined and "Error" not in combined and "error" not in combined:
        return "none"
    return "crash"


if __name__ == "__main__":  # ★ 自检（★ 本模块自己也必须是活的）★★
    _s = suite("selftest_kit 自检")
    with _s:
        _s.run("① check() 成功时不抛", lambda: check("① ok", True))
        try:
            check("② check() 失败时抛 AssertionFailure", False, "detail")
            _s.failed.append("② check() 失败时抛 AssertionFailure")
        except AssertionFailure:
            _s.passed += 1
        _s.run("③ 断言失败分类器：✘ 前缀 ⇒ assertion",
                lambda: check("③", classify_failure("  ✘ 某检查") == "assertion"))
        _s.run("④ 断言失败分类器：测试脚本里的 AssertionError ⇒ assertion",
                lambda: check("④", classify_failure(
                    'Traceback (most recent call last):\n  File "/x/test_foo.py", line 9, in f\n'
                    '    assert False\nAssertionError\n',
                    tested_files=["/x/target_foo.py"]) == "assertion"))
        _s.run("⑤ 断言失败分类器：被测代码里的 AssertionError ⇒ crash",
                lambda: check("⑤", classify_failure(
                    'Traceback (most recent call last):\n  File "/x/target_foo.py", line 9, in f\n'
                    '    assert False\nAssertionError\n',
                    tested_files=["/x/target_foo.py"]) == "crash"))
        _s.run("⑥ 断言失败分类器：ImportError ⇒ crash",
                lambda: check("⑥", classify_failure("ImportError: no module", tested_files=["/x/t.py"]) == "crash"))
        _s.run("⑦ 断言失败分类器：无失败 ⇒ none",
                lambda: check("⑦", classify_failure("all good", tested_files=["/x/t.py"]) == "none"))
    sys.exit(_s.report())
