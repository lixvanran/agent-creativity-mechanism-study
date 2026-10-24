#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四组 · 状态机 runner（C1 / S / R1 多步管线 + C0 对照）

═══ 为什么另起一个文件，不改 runner.py ═══
runner.py 是 A/B/C/R1/R2 五臂的**单步**实现，已经跑过、已交付。
C1 需要的是**多步 + 状态转移**，结构不同，硬改会毁掉原有可复现性。
本文件用 `import runner as R` 复用全部基础件（题库 / API 层 / 档案解析 /
断点续跑 / 防伪断言），**不修改 runner.py 一个字节**。

═══ C1 与 C0 的真区别 ═══
C0（= runner.py 的 C 臂）：立场档案 9 字段**全文**一次性进 system prompt，
                        模型自己决定怎么用。状态在**上下文里**，没有转移。
C1（���文件）：
    步1  f(S₀)  → 约束₁        agent 侧调用，读 S₀（agent 侧权威副本）
    步2  写 O₁   → 初稿          注入约束₁（**不含档案原文**）
    步3  g(S₀,O₁) → S₁, 约束₂, 追问   读 S₀ **和 O₁**（状态转移依赖观测）
    步4  写 O₂   → 终稿          注入约束₂ + O₁
    ⇒ S₁ ≠ S₀，且 S₁ 依赖 O₁。**状态历史置换因此可测。**

═══ 借 multi-mind v0.8 的教训（borrowed/BORROWED.md）═══
1. refinement 型多步链路在创作类题目上**负增益** ⇒ f/g 的输出必须是
   **叙述性自然语言**，禁止评分表 / 对比表 / 编号字段（那是体裁漂移的引擎）。
2. 必须有**等调用数**的中性臂 S，否则 C1 vs C0 的差异无法归因（可能是
   "多了 3 次调用"而不是"状态机"）。S 与 C1 步数、max_tokens 完全相同。
3. 判据必须**自检**（能抓到已知正例、能放过已知负例）⇒ 见 metrics2.py。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner as R  # noqa: E402  复用基础件（不修改）
from metrics2 import parse_sections  # noqa: E402  多段解析器（判据模块统一维护）

# ---------------------------------------------------------------- 臂定义
ARMS_ALL = ("A", "C0", "C1", "C2", "S", "R0", "R1")
MULTISTEP = ("C1", "C2", "S", "R0", "R1")   # 4 步管线
SINGLESTEP = ("A", "C0")


# ---------------------------------------------------------------- 中性简报（S 臂的"状态"）
# 长度对齐 C0 的档案块（state_chars 量级），但**不含任何立场**。
# 这是 S 臂的"等强度"来源：上下文强度相当，状态内容为零。
NEUTRAL_STATE = {
    "自选极性": "不适用",
    "立场核心": "你是一位以准确为先的写作者，尊重读者的理解力，不替读者下结论。",
    "选它的理由": "因为含糊的代价由读者承担，而清楚的代价由作者承担。",
    "来历": "你写过很多稿子，删掉过大量自己当时很得意、后来觉得站不住的段落。",
    "取舍约束": [
        "不牺牲具体：宁可写一个真实的细节，不写一句概括的漂亮话。",
        "不牺牲节奏：允许一处不解释的停顿，不为了顺滑而抹平转折。",
        "不牺牲分寸：不确定的地方就让它不确定，不替读者把话说满。",
    ],
    "拒绝": "拒绝为了看起来完整而补上自己并不确信的细节。",
    "语气": "克制的。",
    "强度封顶": "当你发现某个细节明显是为了好听而编的，就把它删掉。",
    "锚定问题": "这一稿里哪一句是真正有代价的？",
}




# ================================================================ C2（第二代状态机臂）
# C2 由信号探测数据直接推出（第四组论证 §3.6.5）：
#   ① 取舍压缩**丢事实**（C1 覆盖率显著低于 C0）⇒ 状态分两层，取舍层 + 事实层
#   ② 取舍压缩**丢极性指向**（极性 3/5 同号）⇒ f 步输出必须携带**极性锚**
#   ③ C1 与 R1 不可区分 ⇒ 必须造出**只有状态机做得到、档案全文做不到**的动作
#      ⇒ 状态转移产生**「已排除的选项」**：走过一次的路不能再走
#         （C0 是一次性注入，结构上**没有"已排除"这个概念** ⇒ 这是 C2 独有的）
# ★ 步数与调用数与 C1 完全相同（4 步）⇒ 与 C0/C1/S 直接可比，成本不变。

F2_PROMPT = """你是写作者的**内在状态调度器**。写作者自己持有一份立场档案。
你要用这份档案决定**这一轮写作必须守住什么、必须避开什么、必须用上什么**。

★ 你**不能**把档案转述给写作者。你只能输出**这一轮的写作指令**。
★ 输出必须是**叙述性自然语言**。**禁止**评分、等级、字段名、表格、对比、优缺点列举。
★ 取舍部分不要重复档案里的原句；事实部分**必须原样照抄**（见下）。

【立场档案】
{stance}

【题目】
{topic}

【输出要求】三段，顺序固定，全部用叙述性自然语言。
**每一段的第一行必须原样以对应的方括号标题开头**（`【取舍约束】`/`【极性锚】`/`【事实提示】`），
否则你的输出无法被使用。

【取舍约束】
恰好 3 行，每行一句「取舍约束」：这一轮要写进正文的取舍、必须避开什么、最容易失守的地方。
（只说"怎么取舍"，**不要**在这里列具体事实。）

【极性锚】
恰好 1 行：这一轮的写作站在档案的哪一端，以及**因此**取舍的方向是什么。
（必须是自然语言，**不要**写 pole_a / pole_b 这样的编号。）

【事实提示】
恰好 2 行，每行一条**具体可核事实**（数字、日期、专名、地点），**原样照抄**档案
「来历」与「强度封顶」里的内容。这一轮写作要用上它们。

【输出】
"""

G2_PROMPT = """你是同一个内在状态调度器。写作者刚写出了初稿，你要看初稿，判断状态如何转移。

【立场档案】
{stance}

【题目】
{topic}

【初稿】
{draft}

【输出要求】五段，顺序固定，全部用叙述性自然语言，**禁止**评分、字段名、表格、编号列表。
**每一段的第一行必须原样以对应的方括号标题开头**（`【未落地】`/`【取舍约束】`/`【极性锚】`/
`【事实提示】`/`【已排除】`），否则你的输出无法被使用。

【未落地】
档案里的哪一条取舍在初稿里其实还没有真正落地？你用自己的话说，为什么没落地（一到两句）。

【取舍约束】
因此这一轮写作的取舍约束应该**改成什么**。恰好 3 行，每行一句。
（约束要**和上一轮不同**——如果没发现需要改，就明确说"沿用上一轮"并写出沿用的三条。）

【极性锚】
这一轮仍然站在哪一端、因此取舍方向是什么。恰好 1 行。
（与上一轮**同一端**。如果初稿滑到了另一端，明确指出并说明怎么拉回来。）

【事实提示】
这一轮必须用上的具体可核事实（数字、日期、专名、地点），**原样照抄**档案里的内容。恰好 2 行。
（如果初稿漏掉了档案里的某个具体事实，在这里把它点出来。）

【已排除】
初稿已经走过、**这一轮不能再走**的路。恰好 2 行，每行一句。
（写清楚"不要再出现什么"，不要写成评分。）

【可核事实】
初稿里出现的**具体可核事实**——数字、日期、专名、地点、人名。一行一条，照抄原文里的原样写法。
没有就写「无」。

【输出】
"""

WRITE2_PROMPT = """题目：{title}
体裁：{genre}
读者：{audience}
长度：{length}
要求：{brief}

【本轮取舍约束】
{constraints}

【本轮极性锚】
{polarity}

【本轮必须用上的事实】
{facts}

【本轮不能再走的路】
{excluded}

【硬性要求】
· 全文不超过 {cap} 字。
· 不要复述上面的约束，也不要写"根据要求""本轮约束"之类的话。
· 让约束通过"你选择写什么、不写什么、按什么顺序写"体现出来。
· 直接输出作品正文。

【正文】
"""

FINAL2_PROMPT = """你刚写过一稿，现在要做最后一轮修改。

题目：{title}
体裁：{genre}
读者：{audience}
长度：{length}
要求：{brief}

【上一稿】
{draft}

【本轮取舍约束】
{constraints}

【本轮极性锚】
{polarity}

【本轮必须用上的事实】
{facts}

【本轮不能再走的路】
{excluded}

【硬性要求】
· 全文不超过 {cap} 字。
· 这一轮只改动上面这些约束指向的地方，其余部分尽量保留上一稿的样子。
· **上一稿走过的路不要再走一遍**。
· 不要复述上面的约束，不要写"根据要求"之类的话。
· 直接输出作品正文。

【正文】
"""

# ---------------------------------------------------------------- R0：无关立场（写死，不调 LLM）
# R0 的作用是**杀死 H0**：
#   若 R0（强制采用的、与题无关的立场）的产出与 A 无差异 ⇒ 说明"强制采用立场"这个
#   操作本身对模型无效（模型会忽略它）⇒ 那么 R1 的任何差异都可能只是噪声。
# ★ 因此 R0 **必须被强制采用**，不能让它"自然被忽略"——否则 H0 是被 rig 掉的。
# ★ R0 的立场必须**与任何题目都无关**，且**具体可执行**（否则"被忽略"无法区分于"无法执行"）。
R0_STATE = {
    "自选极性": "pole_a",
    "立场核心": "任何判断都要先把依赖的事实核实清楚，再下结论；顺序不能反。",
    "选它的理由": "因为反过来的时候，错的不是结论，是别人的时间和钱，而那个代价由不出主意的人承担。",
    "来历": "2023 年 3 月，一份供应商报价我未经核实就报了，采购单已经签下去。整批货到厂那天才发现规格对不上，损失由整个小组分摊。那张报价单我留着。",
    "取舍约束": [
        "不牺牲核实的时间：宁可晚一天说结论，也不在前提没查清时开口。",
        "不牺牲自己的难堪：承认「我还没查清」比给一个像样的答案更重要。",
        "不牺牲别人的时间：不用「这个你应该知道」来把核实成本转嫁出去。",
    ],
    "拒绝": "拒绝为了让进展显得更快而跳过核实；拒绝把「时间紧」当成省略依据的许可证。",
    "语气": "克制，先说依据再说判断。",
    "强度封顶": "当核实本身被证明是系统性误导时，我会停下来重新决定该不该核实。",
    "锚定问题": "这个结论依赖哪些我还没有核实的前提？",
}


# ---------------------------------------------------------------- API 层（可切换）
# 默认走 MiniMax（第四组原有设定）；`--api openrouter` 换成 OpenRouter 上的任意模型
# （实测 x-ai/grok-4.20）。业务代码一行不改。
API = {"mode": "minimax", "model": R.MODEL, "base": R.API_URL, "key_env": R.KEY_ENV}


def chat(messages: list, max_tokens: int = 1600, temperature: float = 1.0,
         timeout: int = 180, extra: dict | None = None) -> tuple:
    """统一入口：与 R.chat 同签名。"""
    if API["mode"] == "openrouter":
        import api_openrouter
        return api_openrouter.chat(messages, max_tokens, temperature, timeout, extra,
                                   model=API["model"], base_url=API["base"],
                                   key_env=API["key_env"])
    return R.chat(messages, max_tokens, temperature, timeout, extra)


# ---------------------------------------------------------------- 提示
# ★ 铁律：f/g 的输出**只能是自然语言叙述**。
#   禁止"评分/等级/字段/表格"——multi-mind 的 N2 schema 正是体裁漂移的引擎。
F_PROMPT = """你是写作者的**内在状态调度器**。写作者自己持有一份立场档案，你要用这份档案
决定**这一轮写作必须守住什么、必须避开什么**。

★ 你**不能**把档案转述给写作者。你只能输出**取舍约束**。
★ 输出必须是**叙述性自然语言**。**禁止**评分、等级、字段名、表格、对比、优缺点列举。
★ 不要重复档案里的原句。

【立场档案】
{stance}

【题目】
{topic}

【输出要求】
恰好 **3 行**，每行一句「取舍约束」，分别说明：
- 这一轮要写进正文的取舍是什么（具体到这一轮，不是通则）
- 这一轮必须避开什么
- 这一轮写作者最容易失守的地方是什么

只输出这 3 行，不要任何编号、标题、解释、前后缀。

【三行】
"""

G_PROMPT = """你是同一个内在状态调度器。写作者刚写出了初稿，你要看初稿，判断状态如何转移。

【立场档案】
{stance}

【题目】
{topic}

【初稿】
{draft}

【输出要求】分三段，**全部用叙述性自然语言**，禁止评分、字段名、表格、编号列表：

第一段「未落地」：档案里的哪一条取舍，在初稿里其实还没有真正落地？你用自己的话说，
为什么没落地（一到两句）。

第二段「本轮约束」：因此这一轮写作的取舍约束应该**改成什么**。恰好 3 行，每行一句。
（约束要**和上一轮不同**——如果没发现需要改，就明确说"沿用上一轮"并写出沿用的三条。）

第三段「可核事实」：初稿里出现的**具体可核事实**——数字、日期、专名、地点、人名。
一行一条，照抄原文里的原样写法。没有就写「无」。

【输出】
"""

WRITE_PROMPT = """题目：{title}
体裁：{genre}
读者：{audience}
长度：{length}
要求：{brief}

【本轮取舍约束】
{constraints}

【硬性要求】
· 全文不超过 {cap} 字。
· 不要复述上面的约束，也不要写"根据要求""本轮约束"之类的话。
· 让约束通过"你选择写什么、不写什么、按什么顺序写"体现出来。
· 直接输出作品正文。

【正文】
"""

FINAL_PROMPT = """你刚写过一稿，现在要做最后一轮修改。

题目：{title}
体裁：{genre}
读者：{audience}
长度：{length}
要求：{brief}

【上一稿】
{draft}

【本轮取舍约束】
{constraints}

【硬性要求】
· 全文不超过 {cap} 字。
· 这一轮只改动取舍约束指向的地方，其余部分尽量保留上一稿的样子。
· 不要复述上面的约束，不要写"根据要求"之类的话。
· 直接输出作品正文。

【正文】
"""


# ---------------------------------------------------------------- 可核锚点（D-1 CKF 载体）
# 档案的「来历」里塞一个**可核的专名+数字**（如病历编号 2048）。
# 换值测试：把锚点里的数字换掉重跑，看正文痕迹是否跟着换。
# ★ 锚点对**所有臂同一份档案**，因此 C0/C1/R1 的锚点完全相同 ⇒ 比较公平。
CKF_ANCHOR_BLOCK = """\n\n【硬性要求 · 可核事实锚点】
「来历」这一项里**必须**原样包含下面这个具体事实（含数字与专名，不得改写、不得省略）：
%s
"""


def stance_prompt_with_anchor(src_topic: dict, forced, anchor: str) -> str:
    p = R.stance_prompt(src_topic, forced)
    if anchor:
        p += CKF_ANCHOR_BLOCK % anchor
    return p


def apply_swap(text: str, swap: str) -> str:
    """把锚点里的旧值换成新值（'2048->2011' 形式，多条用**分号**分隔）。

    ★ 用分号不用逗号：逗号要留给锚点正文（"病历编号是 2048"里就可能有逗号），
      混用会把整串当成一个替换对（实测把 "2048" 换成了 "2011;7311->4402"）。
    """
    if not swap:
        return text
    for pair in swap.split(";"):
        if "->" not in pair:
            continue
        old, new = pair.split("->", 1)
        old, new = old.strip(), new.strip()
        if old and old != new:
            text = text.replace(old, new)
    return text


def _bump(calls: list, lock=None) -> None:
    """线程安全的调用计数。

    ★ 并发下 `calls[0] += 1` 有竞态会丢计数（实测 22 次只记 18）⇒
      成本闸门（--max-calls）会失效 ⇒ 成本失控。
    """
    if lock is None:
        calls[0] += 1
    else:
        with lock:
            calls[0] += 1


def with_cap(text: str, cap: int) -> str:
    """给所有臂统一加字数上限。

    ★ 为什么必须统一加：v1 冒烟里 A 写 2321 字、C0 2276、C1 1752、S 1243，
      而题面只要求 1200 字。长度差会直接污染「正文对档案的内容覆盖率」
      （长正文分母大 ⇒ 覆盖率天然低）⇒ 长度与臂混淆。
      借 multi-mind v0.8 的做法：长度在**构造时封顶**，由构造消除混淆。
    """
    if not cap:
        return text
    return (text or "").rstrip() + "\n\n【长度】全文不超过 %d 字。" % cap


def _stance_for_f(stance: dict | None) -> str:
    """渲染给调度器看的状态块（**含全文**，只给调度器，不给写作者）。"""
    if not stance:
        return "（无）"
    lines = []
    for k, _ in R.STANCE_FIELDS:
        v = stance.get(k)
        if isinstance(v, list):
            v = "；".join(str(x) for x in v)
        lines.append("【%s】%s" % (k, v if v else "（缺失）"))
    return "\n".join(lines)


def _topic_for_f(topic: dict) -> str:
    return "题目：%s\n体裁：%s\n要求：%s\n这道题的两难：%s" % (
        topic["title"], topic["genre"], topic["brief"], topic["dilemma"])


def _parse_constraints(text: str) -> list:
    """把 f/g 的输出解析成 3 条约束（叙述性文本，容忍噪声行）。"""
    out = []
    for ln in (text or "").splitlines():
        ln = re.sub(r"^\s*(?:[-*·•]|\d+[.、)])\s*", "", ln).strip()
        ln = re.sub(r"^【.*?】\s*", "", ln).strip()
        if len(ln) >= 6 and ln not in out:
            out.append(ln)
    return out[:3]


_SEC_HEAD = re.compile(
    r"^\s*[【\[]?\s*(未落地|未落地项|本轮约束|约束|可核事实|事实|第一段|第二段|第三段)\s*[】\]]?\s*[：:]?\s*")
_SEG_OF = {
    "未落地": "un", "未落地项": "un", "第一段": "un",
    "本轮约束": "cons", "约束": "cons", "第二段": "cons",
    "可核事实": "fact", "事实": "fact", "第三段": "fact",
}


def _parse_g(text: str) -> tuple:
    """解析 g 的三段输出 → (未落地, 约束列表, 可核事实列表)。

    ★ 段首必须兼容 `【本轮约束】` / `本轮约束：` / `第二段` 三种写法。
      （v1 实测模型输出的是 `【本轮约束】` 独立成行，正则漏掉 ⇒ 约束②回退成约束①
        ⇒ 状态转移事实性失效。这是必须带自检的那一类 bug。）
    """
    t = text or ""
    seg_un, seg_cons, seg_fact = "", [], []
    cur = "un"
    for ln in t.splitlines():
        s = ln.strip()
        m = _SEC_HEAD.match(s)
        if m:
            cur = _SEG_OF.get(m.group(1), cur)
            s = s[m.end():].strip()
        if not s:
            continue
        if cur == "un":
            seg_un += s + "\n"
        elif cur == "cons":
            c = re.sub(r"^\s*(?:[-*·•]|\d+[.、)])\s*", "", s).strip()
            if len(c) >= 6 and c not in seg_cons:
                seg_cons.append(c)
        else:
            f = re.sub(r"^\s*(?:[-*·•]|\d+[.、)])\s*", "", s).strip()
            if f and f not in seg_fact and f not in ("无", "（无）"):
                seg_fact.append(f)
    return seg_un.strip(), seg_cons[:3], seg_fact[:10]


# ---------------------------------------------------------------- 防伪：写作步不得含档案原文
_STATE_TAGS = tuple("【%s】" % k for k, _ in R.STANCE_FIELDS)


def assert_no_state_leak(prompt: str, stance: dict | None) -> None:
    """★ 运行时断言：写作步的 prompt 里**不得**出现档案字段标签。

    这保证 C1 的写作步拿到的是**取舍约束**，不是档案全文。
    若这条断言失效，C1 就退化成了 C0，整个实验作废。
    """
    if not stance:
        return
    for tag in _STATE_TAGS:
        if tag in prompt:
            raise AssertionError("写作步泄漏了档案字段标签：%s" % tag)
    if R.STATE_HEADER in prompt:
        raise AssertionError("写作步泄漏了状态块标记")


# ---------------------------------------------------------------- 管线
def run_multistep(arm: str, topic: dict, stance: dict | None, args, tag: str,
                  calls: list, lock=None) -> dict:
    """跑 4 步管线，返回 (正文, 中间态记录)。"""
    # S 臂用中性简报当"状态"（等强度、无立场）
    st = NEUTRAL_STATE if arm == "S" else stance
    rec = {"arm": arm, "steps": []}

    is_c2 = (arm == "C2")

    # --- 步 1：f(S₀) → 约束₁（+ C2：极性锚₁、事实提示₁）
    p1 = (F2_PROMPT if is_c2 else F_PROMPT).format(
        stance=_stance_for_f(st), topic=_topic_for_f(topic))
    _bump(calls, lock)
    c1_txt, u1, dt1, _ = chat([{"role": "user", "content": p1}],
                                max_tokens=args.f_max_tokens,
                                temperature=args.temperature, timeout=args.timeout)
    if is_c2:
        sec1 = parse_sections(c1_txt, expected=["cons", "polarity", "facts_hint"])
        if not sec1["cons"] or not sec1["polarity"] or not sec1["facts_hint"]:
            # ★ 解析失败 ⇒ **重试一次**（追加纠正指令）。实测 grok-4.20 会忽略段标题要求。
            _bump(calls, lock)
            c1b, u1b, dt1b, _ = chat(
                [{"role": "user", "content": p1 + "\n\n【纠正】你上一次的输出无法被解析："
                 "**每段的第一行必须原样以【取舍约束】/【极性锚】/【事实提示】开头**，"
                 "三段顺序固定，且不要在标题外加任何文字。"}],
                max_tokens=args.f_max_tokens, temperature=args.temperature, timeout=args.timeout)
            sec1b = parse_sections(c1b, expected=["cons", "polarity", "facts_hint"])
            if sec1b["cons"] and sec1b["polarity"] and sec1b["facts_hint"]:
                c1_txt, u1 = c1b, u1b
                sec1 = sec1b
                rec.setdefault("retries", []).append("f")
        cons1 = sec1["cons"][:3]
        pol1 = sec1["polarity"][:1]
        fh1 = sec1["facts_hint"][:2]
        rec["steps"].append({"step": "f", "constraints": cons1, "polarity": pol1,
                              "facts_hint": fh1, "raw": c1_txt,
                              "usage": u1, "latency": round(dt1, 1)})
        # ★ C2 的 f 步必须同时给出三样：约束 + 极性锚 + 事实提示
        miss = [k for k, v in (("约束", cons1), ("极性锚", pol1), ("事实提示", fh1)) if not v]
        if miss:
            rec["steps"][-1]["missing"] = miss
    else:
        cons1 = _parse_constraints(c1_txt)
        pol1, fh1 = [], []
        rec["steps"].append({"step": "f", "constraints": cons1, "raw": c1_txt,
                              "usage": u1, "latency": round(dt1, 1)})
    if not cons1:
        rec["error"] = "f_步没有解析出任何约束"
        return "", rec

    # --- 步 2：写初稿 O₁（prompt 不含档案原文）
    if is_c2:
        w1 = WRITE2_PROMPT.format(
            title=topic["title"], genre=topic["genre"], audience=topic["audience"],
            length=topic["length"], brief=topic["brief"], cap=args.wordcap,
            constraints="\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(cons1)),
            polarity=(pol1[0] if pol1 else "（未给出）"),
            facts="\n".join("- " + x for x in fh1) if fh1 else "（未给出）",
            excluded="- （无）")
    else:
        w1 = WRITE_PROMPT.format(title=topic["title"], genre=topic["genre"],
                             audience=topic["audience"], length=topic["length"],
                             brief=topic["brief"], cap=args.wordcap,
                             constraints="\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(cons1)))
    assert_no_state_leak(w1, st)
    _bump(calls, lock)
    o1, u2, dt2, _ = chat([{"role": "user", "content": w1}],
                             max_tokens=args.work_max_tokens,
                             temperature=args.temperature, timeout=args.timeout)
    rec["steps"].append({"step": "write", "draft": o1, "usage": u2, "latency": round(dt2, 1)})

    # --- 步 3：g(S₀, O₁) → 未落地 / 约束₂ /（C2：极性锚₂、事实提示₂、已排除）/ 可核事实
    p3 = (G2_PROMPT if is_c2 else G_PROMPT).format(
        stance=_stance_for_f(st), topic=_topic_for_f(topic), draft=o1)
    _bump(calls, lock)
    g_txt, u3, dt3, _ = chat([{"role": "user", "content": p3}],
                                max_tokens=args.g_max_tokens,
                                temperature=args.temperature, timeout=args.timeout)
    if is_c2:
        sec2 = parse_sections(g_txt, expected=["unlanded", "cons", "polarity",
                                               "facts_hint", "excluded", "facts"])
        if not sec2["cons"] or not sec2["excluded"]:
            _bump(calls, lock)
            g2b, u3b, dt3b, _ = chat(
                [{"role": "user", "content": p3 + "\n\n【纠正】你上一次的输出无法被解析："
                 "**每段的第一行必须原样以【未落地】/【取舍约束】/【极性锚】/【事实提示】/"
                 "【已排除】开头**（可核事实段可省略），顺序固定。"}],
                max_tokens=args.g_max_tokens, temperature=args.temperature, timeout=args.timeout)
            sec2b = parse_sections(g2b, expected=["unlanded", "cons", "polarity",
                                                  "facts_hint", "excluded", "facts"])
            if sec2b["cons"] and sec2b["excluded"]:
                g_txt, u3 = g2b, u3b
                sec2 = sec2b
                rec.setdefault("retries", []).append("g")
        un = sec2["unlanded"]
        cons2 = sec2["cons"][:3]
        pol2 = sec2["polarity"][:1]
        fh2 = sec2["facts_hint"][:2]
        exc2 = sec2["excluded"][:2]
        facts = sec2["facts"][:10]
        rec["steps"].append({"step": "g", "unlanded": un, "constraints": cons2,
                              "polarity": pol2, "facts_hint": fh2, "excluded": exc2,
                              "facts": facts, "raw": g_txt, "usage": u3, "latency": round(dt3, 1)})
        miss2 = [k for k, v in (("约束", cons2), ("极性锚", pol2),
                                ("事实提示", fh2), ("已排除", exc2)) if not v]
        if miss2:
            rec["steps"][-1]["missing"] = miss2
        if not cons2:
            cons2 = cons1
            rec["steps"][-1]["constraints_fallback"] = True
    else:
        un, cons2, facts = _parse_g(g_txt)
        rec["steps"].append({"step": "g", "unlanded": un, "constraints": cons2,
                              "facts": facts, "raw": g_txt, "usage": u3, "latency": round(dt3, 1)})
        if not cons2:
            cons2 = cons1
            rec["steps"][-1]["constraints_fallback"] = True

    # --- 步 4：终稿 O₂
    if is_c2:
        w2 = FINAL2_PROMPT.format(
            title=topic["title"], genre=topic["genre"], audience=topic["audience"],
            length=topic["length"], brief=topic["brief"], draft=o1, cap=args.wordcap,
            constraints="\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(cons2)),
            polarity=(pol2[0] if pol2 else (pol1[0] if pol1 else "（未给出）")),
            facts="\n".join("- " + x for x in (fh2 or fh1)) if (fh2 or fh1) else "（未给出）",
            excluded="\n".join("- " + x for x in exc2) if exc2 else "（无）")
    else:
        w2 = FINAL_PROMPT.format(title=topic["title"], genre=topic["genre"],
                              audience=topic["audience"], length=topic["length"],
                              brief=topic["brief"], draft=o1, cap=args.wordcap,
                              constraints="\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(cons2)))
    assert_no_state_leak(w2, st)
    _bump(calls, lock)
    o2, u4, dt4, _ = chat([{"role": "user", "content": w2}],
                             max_tokens=args.work_max_tokens,
                             temperature=args.temperature, timeout=args.timeout)
    rec["steps"].append({"step": "final", "text": o2, "usage": u4, "latency": round(dt4, 1)})
    rec["usage_sum"] = {k: sum((s.get("usage") or {}).get(k) or 0 for s in rec["steps"])
                        for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    return o2, rec


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description="第四组 Phase 0 · 状态机 runner")
    ap.add_argument("--topics", default="",
                    help="逗号分隔的题目 id，如 T01,T05。**留空 ⇒ 用当前题库的全部题**"
                         "（配合 --topics-file 时尤其需要）")
    ap.add_argument("--samples", default="1", help="采样编号，逗号分隔")
    ap.add_argument("--arms", default="A,C0,C1,S,R1")
    ap.add_argument("--out", default="runs/phase0_sm.jsonl")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--f-max-tokens", type=int, default=600)
    ap.add_argument("--g-max-tokens", type=int, default=800)
    ap.add_argument("--work-max-tokens", type=int, default=2000)
    ap.add_argument("--ckf-anchor", default="",
                    help="可核事实锚点，注入档案的「来历」字段（如：省城医院病历编号 2048）")
    ap.add_argument("--ckf-swap", default="",
                    help="锚点换值规则，如 '2048->2011'。用于 D-1 换值同步测试。")
    ap.add_argument("--wordcap", type=int, default=1200,
                    help="所有臂统一的正文字数上限（0=不加）。消除长度与臂的混淆。")
    ap.add_argument("--stance-max-tokens", type=int, default=1400)
    ap.add_argument("--max-calls", type=int, default=400)
    ap.add_argument("--topics-file", default="",
                    help="自定义题库模块名（须提供 TOPICS 列表，可选 POLARITY 词表），"
                         "如 topics_gaokao。**不修改 runner.py 的内置题库**，只在本次运行内生效。")
    ap.add_argument("--api", choices=["minimax", "openrouter"], default="minimax",
                    help="API 后端。openrouter + --model 可换模型（实测 x-ai/grok-4.20）")
    ap.add_argument("--model", default="", help="模型 id（--api openrouter 时有效），默认 x-ai/grok-4.20")
    ap.add_argument("--base-url", default="", help="OpenRouter endpoint，默认官方 chat/completions")
    ap.add_argument("--key-env", default="", help="API key 的环境变量名")
    ap.add_argument("--workers", type=int, default=4,
                    help="作品生成并发数（纯 IO 等待，串行是浪费）。"
                         "★ 不影响可比性：同一进程 ⇒ 同一 batch_id ⇒ 同批可比。"
                         "★ 但 **Token Plan 有速率限制**：实测并发 8 触发 429 大片失败 ⇒ "
                         "建议 ≤4（429 已有 20s 长退避，但重试也扛不住持续限流）。")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-pad", dest="pad", action="store_false")
    args = ap.parse_args()

    if args.api == "openrouter":
        import api_openrouter
        API.update({"mode": "openrouter",
                    "model": args.model or "x-ai/grok-4.20",
                    "base": args.base_url or api_openrouter.DEFAULT_BASE,
                    "key_env": args.key_env or api_openrouter.DEFAULT_KEY_ENV})
        print("[api] OpenRouter · model=%s" % API["model"])
    if args.topics_file:
        import importlib
        mod = importlib.import_module(args.topics_file)
        R.TOPICS = mod.TOPICS                      # 只在本次运行内覆盖
        if hasattr(mod, "POLARITY"):
            import polarity_lexicon
            polarity_lexicon.register(mod.POLARITY)
        print("[topics] 自定义题库 %s：%s" % (args.topics_file, ",".join(t["id"] for t in mod.TOPICS)))
    by_id = {t["id"]: t for t in R.TOPICS}
    arms = [R.normalize_arm(a) for a in args.arms.split(",") if a.strip()]
    for a in arms:
        if a not in ARMS_ALL:
            print("未知臂: %s（可用 %s）" % (a, ",".join(ARMS_ALL)), file=sys.stderr)
            return 2
    tids = [x.strip() for x in args.topics.split(",") if x.strip()]
    if not tids:
        # ★ 未指定 --topics ⇒ 用**当前题库**的全部题。
        #   （默认曾是 "T01"，在 --topics-file 模式下会指向别的题库的题 ⇒ 报"未知题目 id"；
        #     若再叠加上面的 elif，会导致 tids 为空 ⇒ 一次都不跑却"看起来跑完了"）
        tids = [t["id"] for t in R.TOPICS]
        print("[topics] 未指定 --topics ⇒ 用当前题库全部题：%s" % ",".join(tids))
    samples = [int(x) for x in args.samples.split(",") if x.strip()]
    bad = [t for t in tids if t not in by_id]
    if bad:
        print("未知题目 id: %s" % bad, file=sys.stderr)
        return 2

    out_path = Path(args.out)
    out_path = out_path if out_path.is_absolute() else (HERE / out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # --- 档案计划：C0 与 C1 **共用同一份**档案（同题同臂 ⇒ 比较公平）
    stance_plan = []
    if {"C0", "C1", "C2"} & set(arms):
        stance_plan.extend({"arm": "C0", "topic_id": t, "src_kind": "本题"} for t in tids)
    if "R1" in arms:
        stance_plan.extend({"arm": "R1", "topic_id": t, "src_kind": "本题·强制反极性"} for t in tids)

    gen_plan = []
    for tid in tids:
        for arm in arms:
            for s in samples:
                gen_plan.append({"arm": arm, "topic_id": tid, "sample": s})

    if args.dry_run:
        # ★ 按**实际步数**算调用数：多步臂（C1/C2/S/R0/R1）每样本 4 次，
        #   单步臂（A/C0）每样本 1 次。原版只按"作品条数"算，会把 C1 显示成 1 次
        #   ⇒ 干跑时看到的计划与真实成本对不上。
        STEPS = {"A": 1, "C0": 1, "C1": 4, "C2": 4, "S": 4, "R0": 4, "R1": 4}
        n_gen_calls = sum(STEPS.get(a, 1) for a in arms) * len(tids) * len(samples)
        print("DRY RUN  题目=%s 臂=%s 样本=%s" % (tids, arms, samples))
        print("档案调用 %d 次；作品调用 %d 次（按各臂实际步数计）；总上限 %d"
              % (len(stance_plan), n_gen_calls, args.max_calls))
        print("  每臂步数: %s" % ", ".join("%s=%d" % (a, STEPS.get(a, 1)) for a in arms))
        t = by_id[tids[0]]
        print("\n--- f(S) 提示（截断）---\n" + F_PROMPT.format(
            stance=_stance_for_f(NEUTRAL_STATE), topic=_topic_for_f(t))[:700])
        print("\n--- 写作步提示（断言不含档案标签）---\n" + WRITE_PROMPT.format(
            title=t["title"], genre=t["genre"], audience=t["audience"],
            length=t["length"], brief=t["brief"], cap=args.wordcap,
            constraints="1. 示例约束\n2. 示例约束\n3. 示例约束")[:700])
        return 0

    if not os.environ.get(R.KEY_ENV, "").strip():
        print("环境变量 %s 未设置" % R.KEY_ENV, file=sys.stderr)
        return 2

    def anchor_for(tid: str) -> str:
        """锚点：支持 'T01=xxx;T05=yyy' 逐题映射，否则全局一个。"""
        a = args.ckf_anchor or ""
        if "=" in a:
            for part in a.split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    if k.strip() == tid:
                        return apply_swap(v.strip(), args.ckf_swap)
            return ""
        return apply_swap(a, args.ckf_swap)

    done, stances = R.load_state(out_path)
    fh = out_path.open("a", encoding="utf-8")
    calls = [0]
    lock = threading.Lock()
    tok_in = tok_out = 0
    n_err = 0
    batch_id = time.strftime("%Y%m%d-%H%M%S") + "-%d" % os.getpid()
    print("[batch] batch_id=%s（所有臂必须同批）" % batch_id)

    def emit(rec):
        nonlocal tok_in, tok_out
        u = rec.get("usage") or {}
        with lock:
            tok_in += int(u.get("prompt_tokens") or 0)
            tok_out += int(u.get("completion_tokens") or 0)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()

    def guard():
        return calls[0] < args.max_calls

    try:
        # ---------- 档案
        for p in stance_plan:
            tid = p["topic_id"]
            if (tid, p["arm"]) in stances:
                continue
            if not guard():
                print("[stop] 达到调用上限")
                break
            topic = by_id[tid]
            forced = None
            if p["arm"] == "R1":
                c_pol = (stances.get((tid, "C0")) or {}).get("self_polarity")
                if not c_pol:
                    print("[skip] R1/%s：C0 档案缺失或极性无效" % tid)
                    continue
                forced = R.opposite_pole(c_pol)
            anchor = anchor_for(tid)
            prompt = stance_prompt_with_anchor(R.topic_as_src(topic), forced, anchor)
            R.assert_no_polarity_leak(prompt, topic)
            _bump(calls, lock)
            try:
                content, usage, dt, _ = chat([{"role": "user", "content": prompt}],
                                              max_tokens=args.stance_max_tokens,
                                              temperature=args.temperature, timeout=args.timeout)
                st = R.parse_stance(content)
                if not R.stance_valid(st):
                    print("  [%s/%s] 档案不可用（%s），重试" % (p["arm"], tid, st.get("_error") or st.get("_missing")))
                    if guard():
                        _bump(calls, lock)
                        c2, u2, d2, _ = chat([{"role": "user", "content": prompt + "\n\n【纠正】请重新输出严格合法的 JSON 对象。"}],
                                               max_tokens=args.stance_max_tokens,
                                               temperature=args.temperature, timeout=args.timeout)
                        st2 = R.parse_stance(c2)
                        if R.stance_valid(st2):
                            st, usage = st2, u2
                if not R.stance_valid(st):
                    print("  [FAIL] %s/%s 档案最终不可用" % (p["arm"], tid))
                    n_err += 1
                    continue
                stances[(tid, p["arm"])] = st
                emit({"kind": "stance", "arm": p["arm"], "topic_id": tid,
                      "batch_id": batch_id, "stance_profile": st, "usage": usage,
                      "ckf_anchor": anchor, "ckf_swap": args.ckf_swap,
                      "latency": round(dt, 1)})
                print("  [stance] %s/%s ok  极性=%s" % (p["arm"], tid, st.get("self_polarity")))
            except Exception as e:
                n_err += 1
                print("  [ERR] 档案 %s/%s: %s" % (p["arm"], tid, e))

        # ---------- 作品（并发）
        def do_gen(p):
            nonlocal n_err
            key = (p["arm"], p["topic_id"], p["sample"])
            if key in done:
                return None
            topic = by_id[p["topic_id"]]
            stance = stances.get((p["topic_id"], "C0")) if p["arm"] in ("C0", "C1", "C2") else None
            if p["arm"] == "R1":
                stance = stances.get((p["topic_id"], "R1"))
            if p["arm"] == "R0":
                stance = R0_STATE
            if p["arm"] in ("C0", "C1", "C2") and not stance:
                print("  [skip] %s/%s 无档案" % (p["arm"], p["topic_id"]))
                return None
            with lock:
                if not guard():
                    return None
            try:
                if p["arm"] == "A":
                    _bump(calls, lock)
                    msgs = R.build_messages("A", topic, None, "P0", args.pad)
                    msgs[-1]["content"] = with_cap(msgs[-1]["content"], args.wordcap)
                    txt, usage, dt, _ = chat(msgs, max_tokens=args.work_max_tokens,
                                              temperature=args.temperature, timeout=args.timeout)
                    mid = {"steps": []}
                elif p["arm"] == "C0":
                    _bump(calls, lock)
                    msgs = R.build_messages("C", topic, stance, "P0", args.pad)
                    msgs[-1]["content"] = with_cap(msgs[-1]["content"], args.wordcap)
                    txt, usage, dt, _ = chat(msgs, max_tokens=args.work_max_tokens,
                                              temperature=args.temperature, timeout=args.timeout)
                    mid = {"steps": []}
                else:
                    txt, mid = run_multistep(p["arm"], topic, stance, args,
                                             "%s/%s/%s" % (p["arm"], p["topic_id"], p["sample"]),
                                             calls, lock)
                    usage = mid.get("usage_sum") or {}
                    dt = sum(float(x.get("latency") or 0) for x in (mid.get("steps") or []))
                # ★ 产出有效性闸门：空/过短的正文**不算成功**。
                #   实测 grok-4.20 忽略段标题格式 ⇒ 约束解析为空 ⇒ 写作步产出 0 字，
                #   而日志打的是 "ok 0字" ⇒ 0 字产出会被静默计入统计。
                if not (txt or "").strip() or len((txt or "").strip()) < 50:
                    with lock:
                        n_err += 1
                    emit({"kind": "gen", "arm": p["arm"], "topic_id": p["topic_id"],
                          "sample": p["sample"], "batch_id": batch_id,
                          "error": "empty_or_short_output(len=%d)" % len((txt or "").strip()),
                          "text": txt, "mid": mid, "usage": usage})
                    print("  [FAIL] %s/%s#%d 产出无效（%d 字），不计入统计"
                          % (p["arm"], p["topic_id"], p["sample"], len((txt or "").strip())))
                    return None
                emit({"kind": "gen", "arm": p["arm"], "topic_id": p["topic_id"],
                      "sample": p["sample"], "batch_id": batch_id, "text": txt,
                      "mid": mid, "usage": usage, "ckf_anchor": anchor_for(p["topic_id"]),
                      "ckf_swap": args.ckf_swap, "latency": round(dt, 1)})
                with lock:
                    done.add(key)
                print("  [gen] %s/%s#%d ok  %d字" % (p["arm"], p["topic_id"], p["sample"], len(txt or "")))
            except Exception as e:
                with lock:
                    n_err += 1
                print("  [ERR] %s/%s#%d: %s" % (p["arm"], p["topic_id"], p["sample"], e))
            return True

        todo = [p for p in gen_plan
                if (p["arm"], p["topic_id"], p["sample"]) not in done]
        print("[run] 作品 %d 条，并发 %d" % (len(todo), max(1, args.workers)))
        if todo:
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
                futs = {ex.submit(do_gen, p): p for p in todo}
                for fu in as_completed(futs):
                    try:
                        fu.result()
                    except Exception as e:
                        print("  [ERR] task: %s" % e)
    finally:
        fh.close()

    print("\n[done] 调用 %d 次  错误 %d  token in=%d out=%d  批=%s"
          % (calls[0], n_err, tok_in, tok_out, batch_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
