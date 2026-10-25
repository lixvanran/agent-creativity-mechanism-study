#!/usr/bin/env python3
"""★ **输入/输出隔离守卫（★ 「排除自己」必须按【真正会被比较的那个形态】去比）**

> 落点：`creativity_lab/experiments/guard_io.py`
> ★ **★ 通用形态（★ 负责人 2026-10-25 裁决）**：
> ★ **任何「输入 = 目录 / glob」的工具，在【解析输入的同一处】就要断言**
> ★ **「★ 候选输入文件列表里不含任何本次将要写出的路径 ★」**
> ★ ⇒ ⇒ ★ **而不是等跑完再查**（★ 跑完再查 = 产物已被污染）

## ★★★ ★★ 为什么必须是 realpath 级（★ 不是路径字符串相等）
★ **★ 依据：★ 「防自匹配」那条纪律（★ `pgrep -f` 会匹配到承载它的 shell 自己 ⇒ 模式串要拼接 / 要按字段精确匹配）**
★ ⇒ ⇒ ★ **推广：★ 任何"排除自己"的判断，★ 都要按【它真正会被比较的那个形态】去比，★ 而不是按你脑子里想的那个形态**
> ★ **具体三种绕过形态（本模块全部挡）**：
> ① **符号链接**：★ `/workspace/lab` 是符号链接 ⇒ 真实路径是 `/run/csi/mount-root/nas/<id>/lab`
>    ⇒ ⇒ ★ **用字符串比较 ⇒ `startswith` 会失效**（★ 这是今天实测踩到的：`SameFileError`）
> ② **`../` 相对路径**：★ `runs/../runs/x` 与 `runs/x` 是同一个文件
> ③ **大小写/尾斜杠**：★ `runs/x/` 与 `runs/x`

★ **★ ⇒⇒ 所以本模块一律用 `os.path.realpath` 归一后再比；★ 并且【不用 `startswith`】**
★ **★ （★ 因为 `/a/bc` 以 `/a/b` 开头但并不在它下面 —— ★ 这是 `startswith` 判断"是否在目录下"的经典误判）**

## ★★ 三道防线（★ 可单独用，也可叠用）
| ★ **函数** | ★ **用途** | ★ **时机** |
|---|---|---|
| ★ `real(p)` | ★ 把路径归一（realpath + 展开 `~`） | ★ 内部 |
| ★ `assert_not_self_input(input_files, output_paths, label)` | ★ **★ 核心守卫：候选输入文件集合 ∩ 将写出的路径集合 = ∅** | ★ **★ 解析输入的同一处** |
| ★ `assert_output_outside_input_dir(input_dir, output_dir, label)` | ★ **★ 目录级守卫：输入目录 ≠ 输出目录**（★ realpath 级）| ★ 解析输入目录时 |
| ★ `self_test()` | ★ **★ 负向自测：★ 故意制造 4 种绕过 ⇒ 必须逐个报错** | ★ `python3 -B guard_io.py` |
"""
import os
import sys


def real(p: str) -> str:
    """★ 路径归一：★ realpath（★ 解符号链接）+ 展开 `~` + 去掉尾斜杠。"""
    return os.path.realpath(os.path.expanduser(str(p)))


def _as_set(paths) -> set:
    if isinstance(paths, (str, bytes)):
        paths = [paths]
    return {real(p) for p in paths}


def assert_not_self_input(input_files, output_paths, label: str = "") -> None:
    """★ ★ 核心守卫：★ 解析输入的【同一处】调用。

    ★ 断言：★ **候选输入文件列表里不含任何本次将要写出的路径**（★ 按 realpath 比）
    ★ ★ 违反 ⇒ **抛 RuntimeError**（★ 响亮失败，★ 绝不静默跳过）
    """
    ins = _as_set(input_files)
    outs = _as_set(output_paths)
    clash = ins & outs
    if clash:
        raise RuntimeError(
            "★ ★ 输入/输出重叠（★ 反馈循环入口）★ %s\n   ★ 重叠路径：%s\n"
            "   ★ ⇒ 修复方向：★ 把输出路径从输入候选里【显式排除】，★ 或改写到别处"
            % (label or "", sorted(clash)))


def assert_output_outside_input_dir(input_dir: str, output_dir: str,
                                    label: str = "") -> None:
    """★ ★ 目录级守卫（★ realpath 级）：★ 输入目录 ≠ 输出目录。"""
    if real(input_dir) == real(output_dir):
        raise RuntimeError(
            "★ ★ 输入目录 == 输出目录（★ 反馈循环）★ %s\n   ★ %s\n"
            "   ★ ⇒ 修复方向：★ 输出写到别处，★ 或把输出目录从输入候选里显式排除"
            % (label or "", real(input_dir)))


def excluded_candidates(candidates, output_paths) -> list:
    """★ ★ 把【将要写出的路径】从【候选输入】里【显式剔除】（★ realpath 级）。

    ★ ★ 用法（★ 就是"解析输入的同一处"）：★
    ```python
    cands = [os.path.join(d, f) for f in os.listdir(d) if f.startswith("group_")]
    cands = excluded_candidates(cands, [os.path.join(d, "nested_calibration.json")])
    ```
    ★ ★ 注意：★ 本函数【剔除】而非【报错】⇒ ⇒ ★ 适合"输出就在输入目录里但名字不同"的常规情形；
    ★ ★ 而【真正的反馈循环】（输入目录 == 输出目录）⇒ ⇒ ★ 用 `assert_output_outside_input_dir`
    """
    outs = _as_set(output_paths)
    return [c for c in candidates if real(c) not in outs]


# ══════════════════════════════════════════════════════════════
# 负向自测（★ 证明守卫是活的）
# ══════════════════════════════════════════════════════════════

def self_test() -> int:
    print("== ★ 输入/输出隔离守卫 · 负向自测 ==")
    import tempfile
    tmp = tempfile.mkdtemp(prefix="guardio_")
    base = os.path.join(tmp, "d")
    os.makedirs(base, exist_ok=True)
    f_inside = os.path.join(base, "group_x.json")
    open(f_inside, "w").write("{}")
    out_same = os.path.join(base, "nested.json")
    out_other = os.path.join(tmp, "other", "nested.json")
    os.makedirs(os.path.dirname(out_other), exist_ok=True)

    # ① 同一文件 ⇒ 必须报错
    try:
        assert_not_self_input([f_inside], [f_inside], "case1")
        print("  ✘ ① 同文件未被拦")
        return 1
    except RuntimeError:
        print("  ✔ ① 同文件被拦")
    # ② 符号链接绕过 ⇒ 必须报错
    link = os.path.join(tmp, "link_to_d")
    try:
        os.symlink(base, link)
        made = True
    except (OSError, NotImplementedError):
        made = False
    if made:
        try:
            assert_not_self_input([os.path.join(link, "group_x.json")], [f_inside], "case2")
            print("  ✘ ② 符号链接绕过未被拦")
            return 1
        except RuntimeError:
            print("  ✔ ② 符号链接绕过被拦（★ realpath 级 ⇒ 字符串比会漏）")
    else:
        print("  · ② 符号链接不可建 ⇒ 跳过")
    # ③ `../` 绕过 ⇒ 必须报错
    try:
        assert_not_self_input([os.path.join(base, "..", "d", "group_x.json")], [f_inside], "case3")
        print("  ✘ ③ `../` 绕过未被拦")
        return 1
    except RuntimeError:
        print("  ✔ ③ `../` 绕过被拦")
    # ④ 目录级：输入目录 == 输出目录 ⇒ 必须报错
    try:
        assert_output_outside_input_dir(base, base, "case4")
        print("  ✘ ④ 输入目录==输出目录未被拦")
        return 1
    except RuntimeError:
        print("  ✔ ④ 输入目录 == 输出目录被拦")
    # ⑤ 正常情形 ⇒ 不得误报
    try:
        assert_not_self_input([f_inside], [out_other], "case5")
        assert_output_outside_input_dir(base, os.path.dirname(out_other), "case5")
        print("  ✔ ⑤ 正常情形不误报")
    except RuntimeError as e:
        print("  ✘ ⑤ 误报：", e)
        return 1
    # ⑥ 剔除函数
    cands = [f_inside, out_same]
    kept = excluded_candidates(cands, [out_same])
    ok = (len(kept) == 1 and kept[0] == f_inside)
    print("  %s ⑥ excluded_candidates 正确剔除" % ("✔" if ok else "✘"))
    if not ok:
        return 1
    print()
    print("✔ 负向自测通过（★ 守卫是活的）")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
