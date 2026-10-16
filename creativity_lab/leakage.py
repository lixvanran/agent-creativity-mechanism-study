"""泄漏静态检查：把「不能注入作者先验」从纪律变成约束。

三层：
  A. 内容泄漏 —— 提示词/门控里出现题目专有词
  B. 口径泄漏 —— 出现评价标准的词（新颖/可检验/承重/框架转换…）
  C. 预设有词表 —— 出现「我预判的答案类别」

**自检必须先通过**：本模块提供一个 self_test()，往样例里塞已知违规，
确认检查器真的会报错，然后才允许被当作证据使用。

（这直接对应复盘里的错误 3：我的检查器禁词表有洞，却被我当成证据用了。）
"""
from __future__ import annotations
import io, re, sys, tokenize
from dataclasses import dataclass

# 评价口径：把这些词写进提示词 = 给答案打标签
RUBRIC_TERMS = ["高光", "新颖", "不寻常", "独特", "框架转换", "可检验", "立场代价",
                "承重", "洞见", "深度", "洞察", "反常识", "犀利", "精彩",
                "含金量", "有见地", "最不像套话", "最站得住", "最不像常规",
                "一站到底", "读者会停一下"]

# 答案要素：由调用方按题目注入，本模块自己不知道任何具体题目的答案
ANSWER_ELEMENTS: list[str] = []      # 由 --answer-term 传入
QUESTION_TEXTS: list[str] = []       # 由 --question 传入（白名单，题面本身不算泄漏）

TRIPLE = re.compile(r'("""|\'\'\')(?:.|\n)*?\1')
LINE = re.compile(r'#[^\n]*')
LIT = re.compile(r'"((?:[^"\\]|\\.){8,})"')


def strip_noise(path: str) -> str:
    """剥掉注释与 docstring，只留真正会发给模型的表达式。"""
    src = open(path, encoding="utf-8").read()
    src = TRIPLE.sub('""', src)
    src = LINE.sub(' ', src)
    return src


def literals(path: str) -> list[str]:
    return LIT.findall(strip_noise(path))


@dataclass
class Finding:
    path: str
    kind: str      # rubric | answer
    term: str
    where: str


def check(path: str) -> list[Finding]:
    out = []
    for lit in literals(path):
        for t in RUBRIC_TERMS:
            if t in lit:
                out.append(Finding(path, "rubric", t, lit[:70]))
        for t in ANSWER_ELEMENTS:
            if t in lit and not any(t in q for q in QUESTION_TEXTS):
                out.append(Finding(path, "answer", t, lit[:70]))
    return out


def self_test() -> bool:
    """往临时文件里塞两个已知违规，确认检查器抓得到。"""
    import tempfile, os
    ok = True
    probe = 'x = "请挑出最不寻常的一个，它一定最可检验"\n'
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(probe); p = f.name
    if not check(p):
        print("  ✗ 自检失败：检查器没抓到已知的口径违规")
        ok = False
    os.unlink(p)

    if ANSWER_ELEMENTS:
        probe2 = 'y = "记得考虑" + "%s"\n' % ANSWER_ELEMENTS[0]
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(probe2); p2 = f.name
        if not any(x.kind == "answer" for x in check(p2)):
            print("  ✗ 自检失败：检查器没抓到已知的答案要素")
            ok = False
        os.unlink(p2)
    return ok


def main(paths: list[str]) -> int:
    if not self_test():
        print("\n检查器不可信，不得作为证据使用。")
        return 2
    print("检查器自检通过（已确认能抓到已知违规）\n")
    bad = 0
    for p in paths:
        fs = check(p)
        if fs:
            bad += 1
            print(f"✗ {p}")
            for f in fs:
                print(f"    [{f.kind}] {f.term}  ::  {f.where}")
        else:
            n = len(literals(p))
            print(f"✓ {p}  （{n} 条实际提示词，零命中）")
    return 1 if bad else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    qs = [a[len("--question="):] for a in args if a.startswith("--question=")]
    at = [a[len("--answer-term="):] for a in args if a.startswith("--answer-term=")]
    paths = [a for a in args if not a.startswith("--")]
    QUESTION_TEXTS.extend(qs); ANSWER_ELEMENTS.extend(at)
    sys.exit(main(paths))
