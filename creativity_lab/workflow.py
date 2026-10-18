"""可搜索的「思维工作流」规格。

学习对象 = 工作流的**结构规格**，不是自由文本。
规格很小、可 diff、可审计：

    n_branches : 1 | 3 | 5          发散分支数
    mode       : none | fuse | select   末步方式
    preflight  : [P1..P8]           生成前必须走过的通用程序
    selfcheck  : bool               产出后是否跑一遍自检

**preflight 目录里只有程序，没有答案。**
每条都是「该做什么」，不是「该说什么」。这是防作者先验注入的硬约束：
目录里如果出现「存款保险限额是50万」这种内容，整个方案就废了。

程序本身来自训练集上观察到的错误类型（条号错 / 数字错 / 前提错 / 绝对化），
但表述是**通用程序**，不含任何法律内容。
"""
from __future__ import annotations

# ---------------------------------------------------------------- preflight 目录
PREFLIGHT_CATALOG = {
    "P1": "先确定本题适用哪些规则来源，把要依据的条文列出来，再据此作答。",
    "P2": "凡涉及数字的结论，先逐字写出该数字出自哪一条的哪一句，再下结论。",
    "P3": "严格区分「依据明确规定了什么」与「依据没有规定什么」，后者必须明说，不要替依据补齐。",
    "P4": "给出期限、门槛或限额时，同时说明超过该界限之后会怎样处理。",
    "P5": "先给结论，再列依据，最后给可执行步骤；依据部分逐条对应结论。",
    "P6": "引用任何文件或条文前，先确认它的名称、编号与原文表述；不确定就不要引用。",
    "P7": "先列出所有可能适用的分支条件，再选定一条主线并说明为什么排除其余。",
    "P8": "如果依据不足以支撑结论，直接说明缺什么，不要用看起来合理的说法补位。",
}

# ---------------------------------------------------------------- 规格
DEFAULT_SPEC = dict(n_branches=3, mode="select", preflight=[], selfcheck=False)


def spec_key(s: dict) -> str:
    return "b%d-%s-p%s-sc%d" % (
        s["n_branches"], s["mode"],
        "".join(sorted(x[1:] for x in s["preflight"])) or "0",
        int(bool(s["selfcheck"])))


def describe(s: dict) -> str:
    return "分支%d/%s/preflight=%s/自检=%s" % (
        s["n_branches"], s["mode"],
        ",".join(sorted(s["preflight"])) or "无", s["selfcheck"])


def preflight_text(s: dict) -> str:
    ps = [PREFLIGHT_CATALOG[p] for p in sorted(s["preflight"])]
    if not ps:
        return ""
    return ("\n\n【作答前必须完成的步骤】\n" + "\n".join("%d. %s" % (i + 1, p) for i, p in enumerate(ps))
            + "\n作答时必须体现这些步骤的结论。")


# ---------------------------------------------------------------- 执行
BRANCH_Q = """问题：{ask}

{pf}

请给出你的判断与具体做法。{spec}"""

FINAL_Q = """下面是若干份针对同一问题的独立分析材料。请据此写出你自己的完整答复。

{materials}

{pf}

{ask}

{spec}"""

SELECT_Q = """下面是若干份针对同一问题的完整答复。请选出其中**最准确、最具体**的一份，
原样输出它的正文，不要合并、不要改写、不要加评论。如果有明显的法律错误，选另一份。

{materials}

{pf}

{ask}

{spec}"""

SELFCHECK_Q = """下面是一份针对某问题的答复。请逐条检查其中**每一个具体数字和每一个条文引用**：
- 条号或文件名是否与该条实际内容对应
- 数字是否与该条原文一致
- 有没有把「依据未规定」说成「依据规定」

有问题的，直接给出修正后的完整答复；没问题就原样输出。只输出答复正文。

{ans}"""

OUT_SPEC = "400字以内。"


def run_spec(llm, topic, spec: dict) -> str:
    """按规格执行一次工作流，返回答案文本。"""
    pf = preflight_text(spec)
    n = spec["n_branches"]
    if n <= 1:
        spec_mode = spec["mode"]
        ans = llm.chat(BRANCH_Q.format(ask=topic["ask"], pf=pf, spec=OUT_SPEC),
                       model="MiniMax-M3", purpose="wf_branch", min_ok=200)
    else:
        from creativity_lab.prompts import FRAMES, PERSONAS
        from creativity_lab.client import MODELS
        arts = []
        for i in range(n):
            b = llm.chat(BRANCH_Q.format(
                ask=topic["ask"], pf=pf, spec=OUT_SPEC),
                model=MODELS[i % len(MODELS)], purpose="wf_branch", min_ok=200)
            arts.append(b)
        mats = "\n\n".join("【材料%d】\n%s" % (i + 1, a) for i, a in enumerate(arts))
        if spec["mode"] == "select":
            ans = llm.chat(SELECT_Q.format(materials=mats, pf=pf, ask=topic["ask"], spec=OUT_SPEC),
                           model="MiniMax-M3", purpose="wf_select", min_ok=200)
        else:
            ans = llm.chat(FINAL_Q.format(materials=mats, pf=pf, ask=topic["ask"], spec=OUT_SPEC),
                           model="MiniMax-M3", purpose="wf_fuse", min_ok=200)
    if spec.get("selfcheck") and ans:
        fixed = llm.chat(SELFCHECK_Q.format(ans=ans), model="MiniMax-M3",
                         purpose="wf_selfcheck", min_ok=200)
        if fixed and len(fixed) > 100:
            ans = fixed
    return ans or ""
