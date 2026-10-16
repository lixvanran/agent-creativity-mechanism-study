"""
任务库 —— 每个任务的「效用」都由确定性程序判定，不含任何 LLM 裁判。

设计约束（决定了整个实验是否可信）：
1. 效用必须是 [0,1] 的连续量，且判定函数完全确定、可复现。
2. 新颖性不由本文件负责（见 metrics.py），与效用正交测量。
3. 温度由 runner 锁死；本文件不涉及采样参数。
"""
from __future__ import annotations
import re, ast, json, subprocess, tempfile, os
from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any

# ----------------------------------------------------------------------------
# 任务族 1：CODE —— 效用 = 隐藏单元测试通过率
# ----------------------------------------------------------------------------

CODE_SPECS = [
    dict(
        tid="CODE_01",
        spec=(
            "实现函数 `longest_run(s: str) -> str`：返回 s 中最长的连续重复字符子串。"
            "若最长长度并列，返回**最先出现**的那个。空串返回空串。"
        ),
        tests=[
            ("longest_run('aabbbcc')", "'bbb'"),
            ("longest_run('abc')", "'a'"),
            ("longest_run('')", "''"),
            ("longest_run('zzzzaz')", "'zzzz'"),
            ("longest_run('abbbba')", "'bbbb'"),
        ],
        style="实现应尽量简洁",
    ),
    dict(
        tid="CODE_02",
        spec=(
            "实现函数 `merge_intervals(iv: list) -> list`：把一批闭区间按起点排序后合并重叠或相邻的区间，"
            "返回 `[(start, end), ...]` 形式的列表。要求输入非法时抛 ValueError（end < start）。"
        ),
        tests=[
            ("merge_intervals([(1,3),(2,6),(8,10),(15,18)])", "[(1, 6), (8, 10), (15, 18)]"),
            ("merge_intervals([])", "[]"),
            ("merge_intervals([(1,4),(4,5)])", "[(1, 5)]"),
            ("merge_intervals([(1,9),(2,3),(4,8)])", "[(1, 9)]"),
        ],
        style="注意边界",
    ),
    dict(
        tid="CODE_03",
        spec=(
            "实现函数 `caesar(text: str, k: int) -> str`：对**只含字母和空格**的字符串做凯撒移位，"
            "保留大小写与空格，其余字符抛 ValueError。k 可为负。"
        ),
        tests=[
            ("caesar('abc xyz', 2)", "'cde zab'"),
            ("caesar('ABC', -1)", "'zAB'"),
            ("caesar('a b', 0)", "'a b'"),
        ],
        style="注意非字母字符处理",
    ),
    dict(
        tid="CODE_04",
        spec=(
            "实现函数 `second_largest(nums: list) -> int`：返回严格次大元素（第二大且与最大值不同）。"
            "若不存在严格次大元素则抛 ValueError。空列表抛 ValueError。"
        ),
        tests=[
            ("second_largest([3,1,4,4,5])", "4"),
            ("second_largest([7,7])", "ValueError"),
            ("second_largest([-1,-3,-1,-2])", "-2"),
            ("second_largest([2,1])", "1"),
        ],
        style="注意『严格』二字",
    ),
]

_CODE_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S | re.I)

def _extract_code(text: str) -> str:
    """从模型输出里抽出纯代码。
    判定器必须自己做这件事 —— 否则调用方忘了剥离 think 块和 markdown 围栏时，
    每一份代码都会被判 0 分（本实验踩过这个坑：CODE 族四臂全 0）。"""
    text = text or ""
    m = _CODE_FENCE.findall(text)
    if m:
        return m[0]
    return text

def _code_score(spec: Dict[str, Any], solution_src: str) -> float:
    """跑隐藏测试，返回通过率 [0,1]。无法解析/运行记 0。"""
    solution_src = _extract_code(solution_src)
    if "def " not in solution_src:
        return 0.0
    harness = solution_src + "\n\n__RESULTS__ = []\n"
    for expr, expected in spec["tests"]:
        harness += (
            f"try:\n"
            f"    __v = {expr}\n"
            f"    __ok = (__v == {expected})\n"
            f"except Exception as __e:\n"
            f"    __ok = (type(__e).__name__ == {expected!r})\n"
            f"__RESULTS__.append(__ok)\n"
        )
    harness += "print(__RESULTS__)\n"
    try:
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "h.py")
            with open(p, "w") as f:
                f.write(harness)
            r = subprocess.run(["python3", p], capture_output=True, text=True, timeout=12)
        # 子进程 stdout 形如 "[True, False, ...]"，直接 ast.literal_eval
        res = ast.literal_eval(r.stdout.strip())
        if not isinstance(res, list) or not res:
            return 0.0
        return sum(1 for x in res if x) / len(res)
    except Exception:
        return 0.0

# ----------------------------------------------------------------------------
# 任务族 2：CONSTRAIN —— 效用 = 硬约束满足率
# ----------------------------------------------------------------------------

CONSTRAIN_TASKS = [
    dict(
        tid="CON_01",
        topic="城市里的夜间照明",
        must_include=["磷光", "潮汐", "手写"],
        must_avoid=["LED"],
        min_words=55, max_words=90,
    ),
    dict(
        tid="CON_02",
        topic="给小学生解释为什么秋天树叶会变黄",
        must_include=["会计", "焊接", "屋顶"],
        must_avoid=["叶绿素"],
        min_words=55, max_words=90,
    ),
    dict(
        tid="CON_03",
        topic="一家只在深夜营业的面包店",
        must_include=["卫星", "钢琴", "债务"],
        must_avoid=["烤箱"],
        min_words=55, max_words=90,
    ),
    dict(
        tid="CON_04",
        topic="如何向一只猫解释『税』",
        must_include=["冰川", "缝纫", "回声"],
        must_avoid=["政府"],
        min_words=55, max_words=90,
    ),
]

_CJK = re.compile(r"[一-鿿]")
_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z\-']*")

def _constrain_score(task: Dict[str, Any], text: str) -> float:
    checks = []
    # 1) 必须包含的罕见词
    for w in task["must_include"]:
        checks.append(1.0 if w in text else 0.0)
    # 2) 必须回避的词
    for w in task["must_avoid"]:
        checks.append(0.0 if w in text else 1.0)
    # 3) 长度区间（用中文按字计，英文按词计）
    cjk = len(_CJK.findall(text))
    latin = len(_LATIN_WORD.findall(text))
    approx = cjk + latin
    checks.append(1.0 if task["min_words"] <= approx <= task["max_words"] else 0.0)
    return sum(checks) / len(checks)

# ----------------------------------------------------------------------------
# 任务族 3：REMOTE —— 远联想 + 映射。效用 = 可验证的映射完备性
#   刻意把「远」（陌生源域）与「有用」（真正把源属性映射到目标）做成两个独立计分项。
# ----------------------------------------------------------------------------

REMOTE_TASKS = [
    dict(
        tid="REM_01",
        target="设计一个更公平的代码评审流程",
        source="交响乐团",
        source_attrs=["声部", "指挥", "合奏", "平衡", "层次", "预备", "定音"],
        n_attrs=3,
    ),
    dict(
        tid="REM_02",
        target="让长期项目的知识不流失",
        source="养蜂",
        source_attrs=["采蜜", "蜂巢", "群体", "分蜂", "越冬", "巢室", "工蜂"],
        n_attrs=3,
    ),
    dict(
        tid="REM_03",
        target="设计一套针对 Agent 的回归测试",
        source="登山",
        source_attrs=["路线", "补给", "结组", "海拔", "天气", "撤退", "营地"],
        n_attrs=3,
    ),
    dict(
        tid="REM_04",
        target="让团队的技术债可见化",
        source="地质断层",
        source_attrs=["位移", "应力", "累积", "地震", "断层", "监测", "缓慢"],
        n_attrs=3,
    ),
]

_REMOTE_PROMPT_HEAD = (
    "从源域『{source}』中挑出 {n_attrs} 个不同的属性，对每一个说清它是什么，"
    "然后指出这个属性如何被迁移到目标场景『{target}』并起作用。"
)

_ATTR_HDR = re.compile(r"(?:源域属性|源属性|属性)\s*[：:]")
_MAP_HDR = re.compile(r"(?:映射|迁移|应用|如何迁移)\s*[：:]")

def _remote_parts(text: str) -> tuple:
    """把输出拆成『源属性列举』与『映射论证』两段。

    实际观察到两种格式，都必须支持：
      (A) 单块式：源域属性：\\n1. ... 2. ... 3. ...\\n映射：\\n...
      (B) 重复式：源域属性：X\\n映射：Y\\n\\n源域属性：Z\\n映射：W ...
    做法是按标题切段，逐段配对；若找不到任何标题，则整段都算映射文本。
    """
    marks = []
    for m in _ATTR_HDR.finditer(text):
        marks.append((m.start(), m.end(), "attr"))
    for m in _MAP_HDR.finditer(text):
        marks.append((m.start(), m.end(), "map"))
    if not marks:
        return "", text
    marks.sort()
    attrs, maps = [], []
    for i, (st, en, kind) in enumerate(marks):
        seg_end = marks[i+1][0] if i+1 < len(marks) else len(text)
        seg = text[en:seg_end].strip()
        (attrs if kind == "attr" else maps).append(seg)
    return ("\n".join(attrs), "\n".join(maps))

def _remote_score(task: Dict[str, Any], text: str) -> Dict[str, float]:
    """返回 {'novel_distinct': 属性去重率, 'useful': 映射论证完备率, 'utility': 几何均值}"""
    head, tail = _remote_parts(text)
    # --- 远：源属性的覆盖与去重（越不重复、覆盖越广越"远"）
    hits = [a for a in task["source_attrs"] if a in head]
    uniq_hits = list(dict.fromkeys(hits))
    cover = len(uniq_hits) / task["n_attrs"]
    # 重复惩罚
    dup_ratio = 1.0 - (len(hits) - len(uniq_hits)) / max(len(hits), 1)
    # --- 有用：目标场景被真正触及 + 映射论证成段 + 长度合理
    #     用字符二元组（bigram）而不是分词：中文分词会把"设计一个更公平的代码评审流程"
    #     切成整块，导致"代码评审流程"这种真实提及被判为未命中。
    target = task["target"]
    bigrams = [target[i:i+2] for i in range(len(target) - 1)]
    # 丢弃高频虚词 bigram
    _STOP_BG = {"一个", "一套", "一条", "针对", "如何", "怎么", "的代", "和与", "在的", "的代"}
    bigrams = [b for b in bigrams if b not in _STOP_BG]
    t_hit = sum(1 for b in bigrams if b in tail) / max(len(bigrams), 1)
    length_ok = 1.0 if len(tail) >= 30 else 0.0
    useful = (0.6 * t_hit + 0.4 * length_ok)
    novel = max(0.0, min(1.0, cover)) * dup_ratio
    return dict(novel_distinct=novel, useful=useful,
                utility=round((max(useful, 1e-6) * max(novel, 1e-6)) ** 0.5, 4))

# ----------------------------------------------------------------------------
# 统一封装
# ----------------------------------------------------------------------------

@dataclass
class Task:
    family: str
    tid: str
    prompt: str
    scorer: Callable[[str], Any]
    meta: dict = field(default_factory=dict)


def build_task_bank() -> List[Task]:
    tasks: List[Task] = []

    for spec in CODE_SPECS:
        p = (
            f"请实现下面的 Python 函数。只输出一个 ```python 代码块，块内包含完整实现。\n\n"
            f"规格：{spec['spec']}\n提示：{spec['style']}。"
        )
        tasks.append(Task("CODE", spec["tid"], p, lambda s, sp=spec: _code_score(sp, s), dict(spec)))

    for t in CONSTRAIN_TASKS:
        p = (
            f"请就主题『{t['topic']}』写一段 {t['min_words']}–{t['max_words']} 字的中文短文。\n"
            f"硬性约束（必须全部满足）：\n"
            f"1. 必须原样出现这三个词：{'、'.join(t['must_include'])}\n"
            f"2. 不得出现这个词：{'、'.join(t['must_avoid'])}\n"
            f"3. 长度在 {t['min_words']}–{t['max_words']} 字之间。\n"
            f"只输出短文本身，不要任何解释。"
        )
        tasks.append(Task("CONSTRAIN", t["tid"], p, lambda s, tt=t: _constrain_score(tt, s), dict(t)))

    for t in REMOTE_TASKS:
        p = _REMOTE_PROMPT_HEAD.format(**t) + (
            f"\n\n严格按以下格式输出（不要有多余内容）：\n"
            f"源域属性：\n"
            f"映射：\n"
        )
        tasks.append(Task("REMOTE", t["tid"], p, lambda s, tt=t: _remote_score(tt, s), dict(t)))

    return tasks


if __name__ == "__main__":
    tb = build_task_bank()
    print(f"任务库构建完成：{len(tb)} 个任务")
    from collections import Counter
    print(Counter(t.family for t in tb))
    # 自检：空输入
    #   CODE 必须是 0（无 def 即无实现）
    #   REMOTE 必须 < 0.05（无属性无映射）
    #   CONSTRAIN 有一个**结构性地板**：空串天然满足「不得出现禁词」，
    #   因此得分 = 1/(3必含 + 1禁词 + 1长度) = 0.2。这不是 bug，是该任务的性质，
    #   但意味着 CONSTRAIN 的真实区分度来自「长度」与「必含词」，分析时须注意。
    for t in tb:
        s = t.scorer("")
        if t.family == "CODE":
            assert s == 0.0, (t.tid, s)
        elif t.family == "REMOTE":
            assert s["utility"] < 0.05, (t.tid, s)
        else:
            assert abs(s - 0.2) < 1e-6, (t.tid, s)
    print("空输入自检通过（CONSTRAIN 结构性地板 = 0.2，已记录）")
