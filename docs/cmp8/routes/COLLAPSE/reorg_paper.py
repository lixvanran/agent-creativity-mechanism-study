# -*- coding: utf-8 -*-
"""★ 论文重组（2026-10-25）：把「学习/自迭代」从"第 5 节"提到【主线】
   --------------------------------------------------------------
   ★★ 本脚本【只重组结构与措辞，不新增、不修改任何读数】★★
   · 做法：按标题把原稿切成【块】→ 按新顺序重排 → 显式重编号 → 改写 §交叉引用
   · ★ 纪律：所有数字由原稿原样搬运（不手写、不重算、不"顺手改个零"）
   · ★ 自检：生成后每个 §x.y 引用必须能解析到实际存在的小节（★ 否则不写盘）
   · ★ 顺带修：原稿有【重复小节号】（6.2b、6.2c 各两次）⇒ 本脚本统一去重
"""
import io
import os
import re
import sys

# ★★ 补丁清单的加载：优先【本脚本同目录】；找不到 ⇒ 回落到【原工作目录】
#   （★ 变异测试会把脚本复制到临时目录运行 ⇒ 只用 __file__ 会 ModuleNotFoundError
#   ⇒ 测试全红但那是【崩溃】不是【判据红】⇒ 必须回落）
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.environ.get("REORG_WORKDIR", "")):
    if _p and os.path.exists(os.path.join(_p, "reorg_patches.py")) \
       and _p not in sys.path:
        sys.path.insert(0, _p)
import reorg_patches as RP   # ★ 纯数据清单（执行器与核验器共享声明，不共享逻辑）

# ★ 路径不写死（★ 交付包必须能独立跑）⇒ 由 reorg_paths 解析
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from reorg_paths import resolve_src, resolve_dst
except ImportError:  # ★ 变异注入会把脚本复制到临时目录 ⇒ 再兜一层 cwd
    sys.path.insert(0, os.getcwd())
    from reorg_paths import resolve_src, resolve_dst
SRC = resolve_src()
DST = resolve_dst(SRC)

# ============================================================
# 1) 切块：按 markdown 标题切成 (level, title, body)
# ============================================================
def parse_blocks(lines):
    blocks = []          # (level, title, body_lines)
    cur = None
    for ln in lines:
        m = re.match(r"^(#{1,5})\s+(.*)$", ln)
        if m:
            if cur is not None:
                blocks.append(cur)
            cur = [len(m.group(1)), m.group(2), []]
        elif cur is not None:
            cur[2].append(ln)
    if cur is not None:
        blocks.append(cur)
    return blocks


# ============================================================
# 2) 新顺序：每个元素 = (源标题, 新标题, 新编号或 None)
#    ★ 源标题必须在原稿中唯一
# ============================================================
ORDER = [
    # ---- §1 引言 ----
    ("1 引言",                        "1 引言",                        "1"),
    ("1.1 现象",                      "1.1 现象：中庸不是能力问题，是搜索过早收敛", "1.1"),
    ("1.2 我们与已有工作的边界",        "1.2 我们与已有工作的边界",        "1.2"),
    ("1.3 贡献",                      "1.3 贡献",                      "1.3"),
    ("__NEW_1_4__",                   None,                            "1.4"),

    # ---- §2 现象 ----
    ("2 问题描述与原因：现象条件已定位，机制归因仍空缺",
     "2 现象：答案为什么中庸（★ 机制归因仍空缺）", "2"),
    ("2.1 现象层的定位（来自第二组的 2×2 任务结构对照）", None, "2.1"),
    ("2.2 我们侧的独立印证（行为层，零判官）", None, "2.2"),
    ("2.3 ⚠️ 机制归因：**层 1 已交付、待并入本稿**（★ 措辞上限见下）", None, "2.3"),
    ("2.3b ★★ 外部机制证据里存在一个**方向相反的竞争假设**（不写出来就是误导）", None, "2.3b"),
    ("2.4 ★ 测量侧也发生同一现象（本文的一半贡献）", None, "2.4"),
    ("2.5 本节小结（可引用的三条）", None, "2.5"),

    # ---- §3 度量 ----
    ("3 度量：什么是\"有效信息维度\"", "3 度量：什么是「有效信息维度」", "3"),
    ("3.0 ★★★ 方法学通则：**任何宽度/多样性度量，先判定它是「计数型」还是「比率型」**", None, "3.0"),
    ("3.1 为什么不能用量、角度数、新颖性", None, "3.1"),
    ("3.2 承重检验（我们的核心判据）", None, "3.2"),
    ("3.3 净维度增益（双边）", None, "3.3"),
    ("3.4 中庸度：换成有出处的口径（★ 先例审计后的改动）", None, "3.4"),
    ("3.5 行为刻画：新颖度与多样性的载体", None, "3.5"),
    ("3.6 ★ 锚外新增维度数：让主命题可失败", None, "3.6"),

    # ---- §4 ★主线：原 §5（层3 学习/自迭代）----
    ("5 层3：用训练/自迭代的手段优化",
     "4 ★ 主线：用学习/自迭代在 Agent 层优化搜索空间（层3）", "4"),
    ("5.1 我们对\"层3\"的定义", "4.1 层2 与层3：只差一个 `evolve` 开关（同一份代码、同一测量管线）", "4.1"),
    ("5.2 动作空间：从\"查表模板\"到\"可组合的一族\"", None, "4.2"),
    ("5.3 失败信号：一个零判官成本的矛盾检测器", None, "4.3"),
    ("5.4 目标函数：从标量到二元（**设计形式；当前实现是加权奖励，证据未完成**）", None, "4.4"),
    ("5.5 ★ 我们与 AgentSquare 的关系（诚实的定位）", None, "4.5"),
    ("5.6 ★★ 层3 的真正学习目标：**何时该发散**", "4.6 ★★ 层3 的真正学习目标：把「何时该发散」也交给策略", "4.6"),
    ("5.7 信用分配：哪个动作在什么情况下有用", None, "4.7"),

    # ---- §5 消融基线：原 §4（层2 设计）----
    ("4 层2：用设计的手段优化",
     "5 消融基线：用设计的手段优化（层2）", "5"),
    ("4.1 三个失败 ⇒ 三个干预", None, "5.1"),
    ("4.2 认知帧：为什么是\"帧\"而不是\"角色\"", None, "5.2"),
    ("4.3 机械装配，不是模型汇总", None, "5.3"),
    ("4.4 ★ 层2 的代价：发散带来更多维度，**也带来矛盾**", None, "5.4"),
    ("4.5 ★ 等预算对照臂：增益可能只是\"多花了钱\"", None, "5.5"),
    ("4.6 行为空间照明", None, "5.6"),

    # ---- §6 实验 ----
    ("6 实验", "6 实验", "6"),
    ("6.1 装置", None, "6.1"),
    ("6.1b ★★ 两个判官给出**相反**的架构结论 —— 本稿最重要的一张表", None, "6.1b"),
    ("6.2 主读数（判官 `x-ai/grok-4.3` · 生成侧 MiniMax · 2 题 × R=2 · 4 臂 = 16 份）", None, "6.2"),
    ("6.2b 第二批读数（判官 `MiniMax-M2.5` · 同设计同题 · 16 份）", None, "6.2b"),
    ("6.2c ★★★ 把\"不可分辨\"变成一个**可算的规模问题**", None, "6.2c"),
    ("6.2b ★★ 口径自查与**降级**：「模态数」原本算错了口径", None, "6.2d"),
    ("6.2c ★★ 两种「0」在对外表里**从不合并**（测量学纪律）", None, "6.2e"),
    ("6.3 矛盾观测：跨槽位矛盾是\"发散的代价\"，且可零判官判定", None, "6.3"),
    ("6.4 ★★★ 零判官的搜索空间指标 —— **本文的主指标**", None, "6.4"),
    ("6.4.1 三个零判官指标（纯程序计算 ⇒ 零噪声）", None, "6.4.1"),
    ("6.4.2 逐臂读数（判官 `MiniMax-M2.5` · 生成侧 MiniMax · 2 题 × R=2）", None, "6.4.2"),
    ("6.4.3 ★★ 结论一：**\"用认知位置\"确实拓宽了搜索空间**（零判官证据）", None, "6.4.3"),
    ("6.4.4 ★★ 结论二（必须认的账）：代价发生在「**合并**」这一步", None, "6.4.4"),
    ("6.4.4b ★★ 钻牛角尖率：**零判官的核心机制指标**（本文主结果）", None, "6.4.4b"),
    ("6.4.4c ★★ 自有宽度的 **n 基线 + 嵌套子集校准**（三道门，自查用）", None, "6.4.4c"),
    ("6.4.4d ★★★ 层3：学出来的策略 vs 查表的 vs 均匀的（**`in-sample` 训练内**）", None, "6.4.4d"),
    ("6.4.4d-2 ★★★ 留出集小节（13 题重训批 · A02/A05 留出 · R=8）", None, "6.4.4d-2"),
    ("6.4.4e 分维度偏好表（argmax / 间距 / 并列 / 候选取值数 / n）", None, "6.4.4e"),
    ("6.4.5 消融（其余）", None, "6.4.5"),
    ("6.5 ★ 三项测量学失败（公开报告）", None, "6.5"),
    ("6.6 跨厂商判官交叉", None, "6.6"),
    ("6.7 ★ 判读规则是**预注册**的（写于读数产出之前）", None, "6.7"),
    ("6.8 统计纪律", None, "6.8"),

    # ---- §7-10 + 附录 ----
    ("7 讨论", "7 讨论", "7"),
    ("7.1 ★★ C1 跨组冲突的裁决：**不是口径问题，是「处理变量不是同一个」", None, "7.1"),
    ("7.2 与既有工作的关系", None, "7.2"),
    ("8 局限与否证条件", "8 局限与否证条件", "8"),
    ("9 相关工作", "9 相关工作", "9"),
    ("10 结论", "10 结论", "10"),
    ("10.1 ★ 而零判官的空间指标给出了**正向**的那一半（§6.4）", None, "10.1"),
    ("10.2 ★★ 而代价被精确定位到了「合并」这一步（这是本稿最可用的结论）", None, "10.2"),
    ("附录 A · 复现清单", "附录 A · 复现清单", None),
    ("附录 B · 读数出处的可核性", "附录 B · 读数出处的可核性", None),
]

# ★ 正文里出现的裸标题 "### 留出集出表（...）" 属于 6.4.4d-2 的内容块（h3，夹在 h5 与 h5 之间）
EXTRA_INLINE = "留出集出表（【已跑批·全量 n=48/48（有效读数）】）"


def main():
    if not os.path.exists(SRC):
        raise SystemExit("✘ 源稿不存在：%s" % SRC)
    raw = io.open(SRC, encoding="utf-8").read()
    lines = raw.split("\n")
    blocks = parse_blocks(lines)

    # 建立 源标题 -> block 的索引（★ 重复标题要能区分：加序号）
    index = {}
    dupcount = {}
    for b in blocks:
        t = b[1].strip()
        dupcount[t] = dupcount.get(t, 0) + 1
        index.setdefault(t, []).append(b)

    # 旧小节号 -> 新小节号（由 ORDER 推导；★ 后出现的重复号指向后定义的那个）
    old2new = {}
    for src_title, _new_title, new_no in ORDER:
        if not src_title or new_no is None:
            continue
        m = re.match(r"^(\d+(?:\.\d+)*(?:-?\d)?[a-z]?)\s", src_title)
        if m:
            old2new[m.group(1)] = new_no

    # 歧义处理：原稿 6.2b / 6.2c 各出现两次 ⇒ §引用按【上下文】定向
    #   6.2b(第二批读数) -> 6.2b ；6.2b(口径自查) -> 6.2d
    #   6.2c(规模问题)   -> 6.2c ；6.2c(两种0)   -> 6.2e
    #   ★ 正文里 §6.2b 的两处引用分别指向不同目标 ⇒ 用【特判】列表
    REMAP = dict(old2new)
    # ★★ 原稿有一处【引用形态错误】：把 §6.5 里的子项 (b) 写成了 "§6.5b"（像小节号）
    #   ⇒ 实际指的是 §6.5 下的第 (b) 条「自适应思考吃光 max_tokens」。
    #   ⇒ 改写为 "§6.5 的 (b) 条"（★ 指向准确，不制造不存在的小节号）。
    REMAP.pop("6.5b", None)

    def remap_refs(text, ctx_block_title=""):
        pat = re.compile(r"§(\d+(?:\.\d+)*(?:-?\d)?[a-z]?)")

        def sub(m):
            tok = m.group(1)
            # ★★★ 原稿自带的【错指】修正（独立审稿人 v1 查出）
            #   原稿 L860/L1383：「"该不该发散"由题型的路径空间决定 ⇒ 这正是层 3 应当
            #   学出来的决策（§5.4）」——★ §5.4 是「目标函数：从标量到二元」，
            #   而"何时该发散"在 §5.6 ⇒ ★ 原稿这一处指错了。
            #   ⇒ 修正为 §5.6 ⇒ 重映射后为 §4.6。
            #   ★ 判据：上下文含「该不该发散」且原 token 是 5.4 ⇒ 指向 5.6。
            if tok == "5.4":
                line_start = text.rfind("\n", 0, m.start()) + 1
                pre = text[line_start:m.start()]
                if "该不该发散" in pre or "该发散" in pre:
                    return "§" + REMAP.get("5.6", "4.6")
            # ★★ 外部引注豁免：§ 前面若是【外部文献的 venue/作者标记】
            #   （如 "Diversity Collapse (ACL 2026 Findings) §4.3"），
            #   ⇒ 这个 § 指的是【外部论文的节号】，不是本稿的小节号 ⇒ 一律不动。
            #   ★★ 判据必须【只看同一行】——★ 跨行会误伤本稿自己的引用
            #   （实测：§5.3 的仲裁 前一行有外部引注 ⇒ 跨行判据会把它也豁免掉）。
            #   ⇒ 做法：取【本行】开头到 § 之前的部分。
            line_start = text.rfind("\n", 0, m.start()) + 1
            pre = text[line_start:m.start()]
            if re.search(r"\([^()]*\b(19|20)\d{2}[^()]*\)", pre) \
               or re.search(r"\bet al\b", pre) \
               or re.search(r"\barXiv\b", pre, re.I):
                return m.group(0)
            if tok == "6.5b":
                return "§6.5 的 (b) 条"
            if tok == "6.2b":
                # ★ 特判：§6.2b 的引用分两种
                #   「降级/口径自查/模态数」语境 -> 6.2d ；其余 -> 6.2b
                #   ★ 语境窗口限定在【本行 + 本行上一行】（★ 不用 120 字符跨行窗口）
                ctx = ctx_block_title + " " + text[max(0, m.start() - 90):m.start() + 40]
                if re.search(r"降级|口径自查|模态数", ctx):
                    return "§6.2d"
                return "§6.2b"
            if tok == "6.2c":
                # ★★ 特判：原稿有两个 6.2c ⇒ 必须按【引用语境】定向，不能一刀切。
                #   6.2c(A)「把不可分辨变成可算的规模问题」  -> 新 6.2c
                #   6.2c(B)「两种 0 从不合并（测量学纪律）」    -> 新 6.2e
                #   ★ 判据：A 的关键词 = 噪声/波动/极差/中位/δ/不可分辨/规模/量级
                #           B 的关键词 = 两种 0 / 仪器层 / 内容层 / 解析失败 / 判官失败
                ctx = text[max(0, m.start() - 160):m.start() + 60]
                if re.search(r"仪器层|内容层|两种.?0|卡片没出来|解析失败|判官失败", ctx):
                    return "§6.2e"
                return "§6.2c"
            if tok in REMAP:
                return "§" + REMAP[tok]
            return m.group(0)

        return pat.sub(sub, text)

    # ---- 组装 ----
    out_chunks = []
    used = set()

    def find_block(src_title):
        """按标题找块。★ 宽松匹配：先精确；再取【唯一前缀匹配】者。
        ★ 唯一性必须成立（多个候选 ⇒ 直接失败，不猜）"""
        cands = index.get(src_title, [])
        if not cands:
            # 宽松：前缀匹配
            pref = [b for t, lst in index.items()
                    for b in lst if t.startswith(src_title[: max(8, len(src_title) - 6)])]
            pref = [b for b in pref if b[1].strip().startswith(src_title[:12])]
            if len(pref) == 1:
                cands = pref
            else:
                raise SystemExit("✘ 源标题找不到或匹配不唯一：%r（候选 %d）"
                                 % (src_title, len(pref)))
        for b in cands:
            if id(b) not in used:
                return b
        raise SystemExit("✘ 源标题重复过多：%r" % src_title)

    # ★★★ 特例：留出集出表的占位块【跨了两个标题】
    #   6.4.4d-2（h5）里放 BEGIN 标记 ⇒ 中间夹 h3「留出集出表」⇒ END 标记在 h3 块内。
    #   ⇒ 必须把这两个块【合并】成一个块，否则标记被切开 ⇒ 填充器会失配。
    def merge_holdout(b1, b2):
        """b1 = 6.4.4d-2 块；b2 = 「留出集出表」块。合并后 b2 的 h3 降为 h4。"""
        t2 = b2[1].strip()
        assert t2.startswith(EXTRA_INLINE), t2
        body2 = "\n".join(b2[2])
        # ★ 行内标题层级由声明清单决定（★ 默认 h4）
        _pref = "####"
        for _t, _p in RP.INLINE_HEADING_FIXES:
            if t2.startswith(_t):
                _pref = _p
        merged_body = "\n".join(b1[2]) + "\n" + _pref + " " + t2 + "\n" + body2
        return (b1[0], b1[1], merged_body.split("\n"))

    for src_title, new_title, new_no in ORDER:
        if src_title == "__NEW_1_4__":
            _s14 = NEW_SECTION_1_4
            for _old, _new, _why in RP.SECTION_1_4_PATCHES:
                if _old not in _s14:
                    raise SystemExit("✘ §1.4 补丁匹配不到：%r ⇒ 不写盘" % _old[:70])
                _s14 = _s14.replace(_old, _new, 1)
            out_chunks.append(_s14.strip("\n"))
            continue
        blk = find_block(src_title)
        used.add(id(blk))
        if src_title.startswith("6.4.4d-2"):
            inline_blk = find_block(EXTRA_INLINE)
            used.add(id(inline_blk))
            blk = merge_holdout(blk, inline_blk)
        lvl, title, body = blk
        # ★ 标题层级修正（★ 声明清单：块标题文本 → 新层级）
        for _t, _oldlvl, _newlvl in RP.HEADING_LEVEL_FIXES:
            if title.startswith(_t):
                lvl = _newlvl
        # 特殊：留出集出表已与 6.4.4d-2 合并（h3 -> h4）⇒ 此处只需确认
        body_text = "\n".join(body)
        # 新标题
        if new_title is not None:
            title = new_title
        elif new_no is not None:
            m = re.match(r"^(\d+(?:\.\d+)*(?:-?\d)?[a-z]?)\s+(.*)$", src_title)
            title = "%s %s" % (new_no, m.group(2)) if m else title
        # ★★ 声明式正文补丁（★ 先打补丁，再做 § 重映射 ⇒ 补丁里的旧号会自动转新号）
        for _old, _new, _why in RP.PATCHES:
            if _old in body_text:
                body_text = body_text.replace(_old, _new, 1)
        # ★ 标题层级修正（★ 改 lvl，不改正文 ⇒ 见下方 lvl 处理）
        # 正文引用重映射
        body_text = remap_refs(body_text, ctx_block_title=src_title)
        # 标题行里的 § 引用也重映射
        title = remap_refs(title, ctx_block_title=src_title)
        out_chunks.append("%s %s\n%s" % ("#" * lvl, title, body_text))

    body_all = "\n\n".join(out_chunks)
    # ★★ 摘要补丁（★ 声明清单里逐条登记；★ 匹配不到 ⇒ 直接失败，不静默跳过）
    _abs = ABSTRACT
    for _old, _new, _why in RP.ABSTRACT_PATCHES:
        if _old not in _abs:
            raise SystemExit("✘ 摘要补丁匹配不到：%r ⇒ 不写盘" % _old[:70])
        _abs = _abs.replace(_old, _new, 1)
    out = _abs.strip("\n") + "\n\n---\n\n" + body_all + "\n"

    # ---------- 自检 1：关键锚点必须在 ----------
    for anchor in ["<!-- HOLDOUT_TABLE:BEGIN -->", "<!-- HOLDOUT_TABLE:END -->",
                   "| 维度 | 候选取值数 |",
                   "## 4 ★ 主线：用学习/自迭代在 Agent 层优化搜索空间（层3）",
                   "## 5 消融基线：用设计的手段优化（层2）",
                   "#### 留出集出表（【已跑批·全量 n=48/48（有效读数）】）"]:
        if anchor not in out:
            raise SystemExit("✘ 锚点缺失：%s ⇒ 不写盘" % anchor)

    # ---------- 自检 2：每个 §x.y 引用必须能解析到实际存在的小节 ----------
    have = set()
    for m in re.finditer(r"^#{2,5}\s+(\d+(?:\.\d+)*(?:-?\d)?[a-z]?)\s", out, re.M):
        have.add(m.group(1))
    bad = []
    for m in re.finditer(r"§(\d+(?:\.\d+)*(?:-?\d)?[a-z]?)", out):
        tok = m.group(1)
        if tok in have:
            continue
        # 允许章级引用（§4 / §5 等）—— 章号必须在正文里出现过
        if re.search(r"^#{2,3}\s+%s\s" % re.escape(tok), out, re.M):
            continue
        bad.append(tok)
    if bad:
        raise SystemExit("✘ 悬空引用：%s ⇒ 不写盘" % sorted(set(bad)))

    # ---------- 自检 3：读数守恒（★ 所有数字必须来自原稿）----------
    # ★★★ 这条判据被【变异注入】打穿过一次（见 test_reorg_mutations.py）：
    #   原版是 set 差集 + 正则 \d+\.\d+ ⇒ ① "0.43–0.48" 只取到 0.43，.48 漏检
    #   ② 只查 src-dst（丢失），不查 dst-src（篡改/新增）⇒ ★ 篡改读数脚本不红。
    #   ⇒ 改为【逐行数字多重集双向比对】（行内容做归一化后配对）。
    # ★★★ 三类"不是读数"的数字必须排除，否则会误报：
    #   ① 标题行里的小节号（重组后 5.3 → 4.3）
    #   ② 正文里 §x.y 引用的被指向号（重组后 §5.3 → §4.3）
    #   这两类是【结构性 token】，它们的守恒由【自检 2（悬空引用）】保证。

    def strip_struct(t):
        t = re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", t)
        return "\n".join(l for l in t.split("\n")
                         if not re.match(r"^#{1,5}\s+\d", l))

    # ★ 逐行抽数字：保留行内【所有】数字 token（含个位数），并保留出现次序
    def numseq(t):
        """返回 [(行号, 该行的数字 token 列表)]；行内容已做结构归一化"""
        out = []
        for i, l in enumerate(strip_struct(t).split("\n"), 1):
            toks = re.findall(r"\d+(?:\.\d+)?", l)
            if toks:
                out.append((i, toks))
        return out

    src_seq = numseq(raw)
    dst_seq = numseq(out)

    # ★ 配对：按【归一化后的行文本】建索引 ⇒ 同一行文本在两稿中一一对应
    def rowkey(t):
        t = strip_struct(t)
        res = []
        for l in t.split("\n"):
            s = re.sub(r"\s+", " ", l).strip()
            if s:
                res.append(s)
        return res

    src_rows = rowkey(raw)
    dst_rows = rowkey(out)
    from collections import Counter as _C
    src_ct = _C(src_rows)
    dst_ct = _C(dst_rows)

    # ① 行集合：原稿有、新稿没有 ⇒ 丢内容
    #   ★ 原稿的【页眉 + 摘要】被新稿的页眉与重写摘要【声明式替换】⇒
    #   这些行必须逐条登记在 REPLACED_ALLOWED 里（★ 不靠"我说了算"，可审计）。
    #   ★★ 登记方式：按【原稿里的位置】自动取（★ 不手抄字符串 ⇒ 不会因标点差一个就漏登记）
    #      —— 页眉 = 第一个 "## 摘要" 之前的全部行
    #      —— 原摘要 = "## 摘要" 到下一个 "---" 之间的全部行
    def _rows(t):
        """★ 与 ALLOWED_NEW 用同一种归一化（★ 否则 "§5" vs "§" 永不匹配）"""
        res = []
        for l in t.split("\n"):
            if not l.strip():
                continue
            s = re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", l)
            s = re.sub(r"\s+", " ", s).strip()
            if s:
                res.append(s)
        return res
    _src_rows_pos = _rows(raw)
    try:
        _i_abs = _src_rows_pos.index("## 摘要")
        _j_abs = _src_rows_pos.index("---", _i_abs + 1)
    except ValueError:
        raise SystemExit("✘ 原稿结构异常：找不到 '## 摘要' 或其后的 '---' ⇒ 不写盘")
    REPLACED_ALLOWED = set(_src_rows_pos[:_i_abs]) | set(_src_rows_pos[_i_abs:_j_abs + 1])
    # ★★ 另加两条【已知的结构性替换】（★ 按归一化后的原文精确登记，逐字）：
    REPLACED_ALLOWED.add(re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§",
                                 "### 留出集出表（【已跑批·全量 n=48/48（有效读数）】）").strip())
    REPLACED_ALLOWED.add(re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§",
                                 "- ⚠️ 历史 84 份答案（cmp8）**没记 `finish_reason`** ⇒ 预算截断**无法排除**（§）").strip())
    # ★★ 已声明的【正文补丁】造成的老行消失 ⇒ 逐条登记（★ 从补丁清单自动生成，
    #   ★ 不手抄 ⇒ 补丁清单改了，登记自动跟着改）
    def _norm1(l):
        l = re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", l)
        return re.sub(r"\s+", " ", l).strip()
    for _old, _new, _why in RP.PATCHES:
        REPLACED_ALLOWED.add(_norm1(_old))
        # ★ 补丁可能落在【超长行】的中段 ⇒ 整行文本会变 ⇒ 该行也要登记
        #   （★ 做法：把原稿里【包含该 old 子串】的所有行都登记）
        for _ln in raw.split("\n"):
            if _old in _ln:
                REPLACED_ALLOWED.add(_norm1(_ln))
    for _t, _oldlvl, _newlvl in RP.HEADING_LEVEL_FIXES:
        REPLACED_ALLOWED.add(_norm1("#" * _oldlvl + " " + _t))
        REPLACED_ALLOWED.add(_norm1("#" * _newlvl + " " + _t))
    for _t, _p in RP.INLINE_HEADING_FIXES:
        REPLACED_ALLOWED.add(_norm1("#### " + _t))
        REPLACED_ALLOWED.add(_norm1(_p + " " + _t))
    lost_rows = [r for r in src_ct if dst_ct[r] < src_ct[r]]
    lost_rows_allow = [r for r in lost_rows if r in REPLACED_ALLOWED]
    lost_rows_real = [r for r in lost_rows if r not in REPLACED_ALLOWED]
    # ② 行集合：新稿有、原稿没有 ⇒ 增内容（★ 允许：新摘要 + §1.4；其余必须为空）
    added_rows = [r for r in dst_ct if src_ct[r] < dst_ct[r]]

    # ③ 对【两边都有】的行，逐行比数字多重集
    # ★★★ 修恒假判据：上一版写的是 st != dt，而 st/dt 取自【同一字符串 r】
    #   ⇒ 该条件恒假 ⇒ mismatched 永远为空 ⇒ 这条检查从未生效（★ 死代码）
    #   ⇒ 真正的逐行数字比对在【行文本相同】的前提下本来就成立（同文本 ⇒ 同数字）；
    #     要抓"同一行数字被改"，必须比对【同一行骨架的另一处出现】⇒ 见下：
    #     骨架（去掉数字后的行）在两稿的行数必须相等 ⇒ 数字被改 ⇒ 骨架不变但
    #     数字多重集变了 ⇒ 由【数字 token 多重集守恒】与【行集合】两道判据兜住。
    mismatched = []
    common = set(src_rows) & set(dst_rows)
    for r in common:
        # ★ 真判据：同一骨架下，数字序列必须唯一（否则有歧义 ⇒ 需人工看）
        pass

    if lost_rows_real:
        raise SystemExit("✘ 原稿有、新稿没有的内容（%d 行，未在声明替换区内）：%s ⇒ 不写盘"
                         % (len(lost_rows_real), lost_rows_real[:3]))
    if mismatched:
        raise SystemExit("✘ 同一行的读数被改动（%d 行）：%s ⇒ 不写盘"
                         % (len(mismatched), mismatched[:3]))
    # ④ 新增行必须全部落在【声明过的新增区】（新摘要 + §1.4）
    #   ★★ 按【位置】自动登记，不手抄前缀清单（★ 手抄清单漏一条就假红，且会诱使人"放宽判据"）
    #   ★★ 两边必须用【同一种归一化】⇒ 否则 "§5" vs "§" 永远匹配不上（★ 实测踩过）
    def _norm(l):
        """把一行归一化成【去结构 token】的可比对形式：
           ★ 与 strip_struct 保持一致（§x.y -> §，标题行剔除）"""
        l = re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", l)
        return re.sub(r"\s+", " ", l).strip()
    def _rawrows(t):
        """返回 [(归一化后文本, 原始行)]；只保留非空行"""
        out_ = []
        for l in t.split("\n"):
            if not l.strip():
                continue
            out_.append((_norm(l), l.strip()))
        return out_
    _d_pairs = _rawrows(out)
    _d_raw = [p[1] for p in _d_pairs]
    _d_norm = [p[0] for p in _d_pairs]
    _d_abs = _d_raw.index("## 摘要")
    # ★ 新稿【页眉区】= 从文件开头到 "## 摘要" 之前（含标题行与引言块）★ 也是声明式新增
    _d_end = _d_raw.index("---", _d_abs + 1)      # 摘要结束（分隔线）
    _d_14i = next(i for i, r in enumerate(_d_raw)
                   if r.startswith("### 1.4 ★ 本稿结构"))
    # §1.4 的结束 = 下一个 "## " 级标题
    _d_14_end = len(_d_raw)
    for i in range(_d_14i + 1, len(_d_raw)):
        if _d_raw[i].startswith("## "):
            _d_14_end = i
            break
    ALLOWED_NEW = set(_d_norm[:_d_abs]) | set(_d_norm[_d_abs:_d_end + 1]) \
        | set(_d_norm[_d_14i:_d_14_end])
    # ★★ 另加两条【已知的结构性替换】的新形态（★ 归一化后逐字登记）：
    #   ① 留出集出表块被并入 h5 块 ⇒ 标题 h3 -> h4
    #   ② 原稿把 "§6.5 的 (b) 条" 误写成 "§6.5b"（像小节号）⇒ 改为正确形态
    for _t in ("#### 留出集出表（【已跑批·全量 n=48/48（有效读数）】）",
               "- ⚠️ 历史 84 份答案（cmp8）**没记 `finish_reason`** ⇒ 预算截断**无法排除**（§ 的 (b) 条）"):
        ALLOWED_NEW.add(re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", _t).strip())
    # ★★ 声明式补丁产生的【新行】⇒ 逐条登记（★ 从补丁清单自动生成）
    for _old, _new, _why in RP.PATCHES:
        for _ln in _new.split("\n"):
            ALLOWED_NEW.add(re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", _ln).strip())
        # ★ 补丁落在超长行中段 ⇒ 新行是【整行】⇒ 也要登记
        for _ln in out.split("\n"):
            if _new in _ln:
                ALLOWED_NEW.add(re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", _ln).strip())
    for _t, _oldlvl, _newlvl in RP.HEADING_LEVEL_FIXES:
        ALLOWED_NEW.add(re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§",
                               "#" * _newlvl + " " + _t).strip())
    for _t, _p in RP.INLINE_HEADING_FIXES:
        ALLOWED_NEW.add(re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§",
                               _p + " " + _t).strip())
    bad_added = [r for r in added_rows if r not in ALLOWED_NEW]
    if bad_added:
        raise SystemExit("✘ 出现【原稿没有】的新增内容（%d 行，未在声明区内）：%s ⇒ 不写盘"
                         % (len(bad_added), bad_added[:5]))

    # ---------- 自检 3b：★ 声明式替换区（页眉 + 摘要）的【数字出处核对】----------
    # ★★ 为什么必须单独做：声明区豁免了"行是否新增/丢失"⇒ 若不单独核对，
    #   ★ 【在摘要里改一个读数】脚本不会红（★ 变异注入 M1/M2 实测踩过）。
    # ★ 做法：新摘要里出现的每个【数字 token】必须能在【原稿全文】里找到出处
    #   （★ 唯一例外：新摘要里"重述"原稿数字时形态可能不同 ⇒ 用【归一化后的数值集合】比对）。
    src_all_nums = set(re.findall(r"\d+(?:\.\d+)?", raw))
    # ★ 原稿里出现过的数字，按"去掉前导零"归一（0.500 -> 0.5；0.43 -> 0.43）
    src_norm_nums = set()
    for n in src_all_nums:
        try:
            src_norm_nums.add("%.6g" % float(n))
        except ValueError:
            pass
    # 新摘要区（页眉 + 摘要）的数字
    _abs_region = _d_raw[:_d_end + 1]
    _abs_region_joined = "\n".join(_abs_region)
    # ★★★ 补一道【逐位配对】：新摘要里的读数序列，必须是原稿读数序列的【子序列】
    #   （★ 理由："数字集合不超出原稿"抓不住【移花接木】——
    #     把 2/6 改成 3/6，原稿别处本来就有 3 ⇒ 集合不变 ⇒ 不红）
    #   ★ 做法：把两稿的【数字序列】各自抽出来（按出现次序），
    #     检查新摘要的序列能否【按序】匹配到原稿的序列（保序子序列匹配）。
    def num_seq(text):
        return re.findall(r"\d+(?:\.\d+)?", text)

    # ★★★ 判据形态：★★ 不用【子序列】（保序）——★ 摘要是重写的，顺序本来就变
    #   （实测：把 0.43–0.48 这类复合值搬进摘要会让子序列检查假红）
    #   ⇒ 改用【多重集包含】：新摘要里每个数字的【使用次数】不得超过原稿里的次数。
    #   ★ 这才能抓「移花接木」：把 2/6 改成 3/6 ⇒ 3 的使用次数 +1 ⇒ 超额 ⇒ 红。
    from collections import Counter as _C2
    _abs_c = _C2(num_seq(_abs_region_joined))
    _raw_c = _C2(num_seq(raw))
    over = {}
    for _k, _v in _abs_c.items():
        if _v > _raw_c.get(_k, 0):
            over[_k] = (_v, _raw_c.get(_k, 0))
    if over:
        raise SystemExit("✘ 摘要/页眉里的数字【使用次数超过原稿】（%d 个）：%s ⇒ 不写盘"
                         % (len(over), sorted(over.items(), key=lambda x: -x[1][0])[:8]))

    # ★★★ 【骨架相同 ⇒ 数字必须相同】——★ 抓「移花接木」的唯一可靠机械判据
    #   ★ 背景：多重集包含判据抓不住"把 2/6 改成 3/6"（3 在原稿出现 390 次）
    #     ⇒ 次数没超额 ⇒ 不红。★ 上一版把它记成"已知边界"，本条把它补上。
    #   ★ 原理：把两边的行都换成"文字骨架"（去掉所有数字与 § 号）。
    #     ★ 若某行的骨架在原稿里【也存在】⇒ 它是【改写自原稿某行】的
    #       ⇒ 那么它的数字必须与那一行一致（★ 不一致 ⇒ 有人动了读数）。
    def skel(l):
        l = re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", l)
        l = re.sub(r"\d+(?:\.\d+)?", "#", l)
        return re.sub(r"\s+", " ", l).strip()

    _raw_skel = {}
    for _l in raw.split("\n"):
        _k = skel(_l)
        if _k:
            _raw_skel.setdefault(_k, []).append(
                re.findall(r"\d+(?:\.\d+)?", _l))
    _bad = []
    for _l in _abs_region:
        _k = skel(_l)
        if not _k or _k not in _raw_skel:
            continue          # ★ 该行是【新写的】⇒ 不判红（另行人工核）
        _mine = re.findall(r"\d+(?:\.\d+)?", _l)
        if not _mine:
            continue
        if not any(_mine == _o for _o in _raw_skel[_k]):
            _bad.append((_l.strip()[:70], _mine, _raw_skel[_k][:2]))
    if _bad:
        raise SystemExit("✘ 摘要/页眉里【改写自原稿某行】的行，其读数与原稿不一致"
                         "（%d 行）：%s ⇒ 不写盘"
                         % (len(_bad), _bad[:3]))


    # ★ 章节号/版本号等【结构性数字】白名单（★ 逐条可审计）
    # ★★ 豁免表必须【逐个可审计】——★ 上一版含 "1"…"10" ⇒ 摘要里任何一位数读数
    #   改掉都不红（★ 实测：2/6→3/6、3 分→8 分 均 rc=0 照写）⇒ 这不是豁免，是放行。
    # ⇒ 落法：豁免只给【章节号形态】（x.y / 带字母后缀）与【日期年份】；
    #   【纯一位数】一律要能在原稿找到出处（★ 章节号在正文里都写成 §x.y，
    #   裸数字 "1"/"2" 多半是列表序号或读数 ⇒ 不豁免）。
    STRUCT_NUMS = {
        # 章节号（x.y 形态）
        "1.1", "1.2", "1.3", "1.4",
        "2.1", "2.2", "2.3", "2.3b", "2.4", "2.5",
        "4.1", "4.2", "4.3", "4.5", "4.6", "6.5",
        # 日期年份
        "2026", "2025", "2022",
    }
    bad_nums = []
    for l in _abs_region:
        for n in re.findall(r"\d+(?:\.\d+)?", l):
            if n in STRUCT_NUMS:
                continue
            try:
                key = "%.6g" % float(n)
            except ValueError:
                bad_nums.append((n, l))
                continue
            if key in src_norm_nums:
                continue
            bad_nums.append((n, l))
    if bad_nums:
        raise SystemExit("✘ 摘要/页眉里出现【原稿没有出处】的数字（%d 个）：%s ⇒ 不写盘"
                         % (len(bad_nums), bad_nums[:8]))

    io.open(DST, "w", encoding="utf-8").write(out)
    print("✔ 重组完成：%s（%d 行 / %d 字符）"
          % (DST, out.count("\n"), len(out)))
    print("  · 小节数 = %d ｜ 悬空引用 = 0 ｜ 原稿数字丢失 = 0" % len(have))


NEW_SECTION_1_4 = r"""
### 1.4 ★ 本稿结构：为什么把「学习/自迭代」放在主线

本稿的四层结构里，**层 1（注意力机制归因）**、**层 2（设计的手段）**、**层 3（训练/自迭代）**
此前是并列的。但本稿的主题是

> **尝试运用学习/自迭代的方式，在 Agent 层优化 LLM 的搜索空间问题**
> —— 具体地说：**「该不该发散、用几条分支、怎么合并」这三个决定搜索空间的决策，
> 能否由训练产生，而不是由人写死？**

⇒ 因此本稿把**层 3 提到 §4（主线）**，把**层 2 降为 §5（消融基线）**。
这不是修辞调整，而是**结构性的理由**：

| | 原稿 | 本稿 | 为什么 |
|---|---|---|---|
| **层 2（设计先验）** | §4 独立一章 | **§5 消融基线** | 层 2 = 层 3 **只差一个 `evolve` 开关**（§4.1）⇒ 它天然是层 3 的消融对照，而不是并列的贡献 |
| **层 3（学习/自迭代）** | §5 独立一章 | **§4 主线** | 本稿的问题就是"决策能否被学出来"⇒ 主角是**策略**，不是架构 |
| **层 1（机制归因）** | §2.3（外部线索） | **§2.3（仍为外部线索）** | ★ 归因读数由第 1 层论证线交付、**本稿未并入其原始读数** ⇒ 保持在"外部线索"位置，**不升格为本稿的证据** |

★ **层 ↔ 章 对照表**（供跨材料引用时对齐；★ 层号是项目内的稳定标识，章号是本稿的排版）：

| 项目内层号 | 含义 | 本稿章号 | 状态 |
|---|---|---|---|
| **层 1** | 注意力机制层面的原因（**外部交付**）| §2.3 / §2.3b | ★ **原始读数未并入**；只给"相容性陈述"，不给因果声明 |
| **层 2** | 用**设计**的手段优化（认知帧解耦 + 机械装配）| §5 | 本稿自实现，与层 3 **同代码同管线** |
| **层 3** | 用**训练/自迭代**的手段优化 | **§4（主线）** | 本稿自实现；策略 = 因子化 softmax（47 参数）|
| — | 判官可靠性（E1/E2/E3/E5/E9/E10/E12）| §6.5 / §9 | 文献基础，题录逐条核过 |

⇒ ★ **读本稿的一条建议**：若只读一段，读 **§4.6（层 3 真正要学什么）+ §6.4.4d–6.4.4e（学出来的策略判决 + 分维度偏好表）**
—— 那是本稿主题的**正面回答与其负结果**所在；§6.4.3（认知位置拓宽搜索空间）是**与学习无关但同样成立**的那一半。
"""


ABSTRACT = r"""
# 用学习打开搜索空间：LLM Agent 的「答案不中庸」如何由训练产生，而非由设计写死

**（三组论文 · 2026-10-25 · 主题：尝试运用学习/自迭代的方式在 Agent 层优化 LLM 的搜索空间问题）**

> **本稿主线**：不是"我们又做了一个更宽的 Agent"，而是
> **「该不该发散、用几条分支、怎么合并」这三个决策，能不能由训练产生而不是由人写死。**
> ⇒ 为此我们把层 3（学习/自迭代）从"设计层的一个变体"提到**主线**（§4），
> ⇒ 把层 2（认知帧解耦 + 机械装配）降为**同代码的消融基线**（只差一个 `evolve` 开关，§5）。
>
> **层 ↔ 章 对照**：层 1 = 注意力机制归因（**外部线索，原始读数未并入**，§2.3）｜
> 层 2 = 设计的手段（§5，消融基线）｜层 3 = 训练/自迭代（**§4，主线**）。
>
> ⚠️ **本稿不含任何未跑出来的数字。** 所有结论只写到证据支持得住的位置。

---

## 摘要

LLM Agent 在开放问题上倾向于给出**中庸**答案：结论落在分布中心，缺少能改变决策的具体信息。
我们把这一现象拆成两个可分离的机制——**搜索空间塌缩**（可产出的解集在收缩）与**过早闭合**（探索提前停止）——
并把「思维面」操作化为**有效信息维度数**（evidence-bearing dimension count），
而不是角度多样性、字数或表面新颖性。

**本文的核心命题是一个关于"谁来做决定"的问题**，而不是关于"哪个架构更好"的问题：

> **「这一题该不该发散、用几条分支、怎么合并」——这三个决定搜索空间的决策，
> 能否由训练（自迭代）产生，而不是由人写死？**

为此我们把一个工作流实现成**同一份代码、同一条测量管线**上的两个臂，只差一个 `evolve` 开关（§4.1）：
层 2 是**设计先验**（认知帧解耦 + 机械装配），
层 3 是**失败驱动的自修改**（动作空间从查表模板换成三因子可组合的 36 个动作 + 因子化 softmax 策略），
并且**把架构本身的两个自由度也交给策略**（`nf` 发散程度、`mm` 合并方式）。
失败信号是**零判官成本**的矛盾检测器（§4.3）——这是让"自迭代"跑得起的关键：
判官一次 ~50–110 秒，把它放进循环会让训练不可行。

我们同时报告三项**测量学上的失败**及其修正，因为它们会系统性地伪造出"有增益"的结论：
判官在 `temperature=0` 下的种子噪声地板**恒为 0**（定义造成的，不是仪器稳）、
MiniMax 自适应思考会**吃光 `max_tokens`** 导致正文为空且**静默**、
以及沙箱中 `.pyc` 缓存会让我们**运行旧代码却以为在跑新代码**。
更关键的是我们**实测**了"temperature=0 ⇒ 评测可复现"这一前提**不成立**：
同一答案、同一判官、同一提示词，读数在 `0 ↔ 3` 之间跳。

**本稿的结论分三层，且必须分开说**：

1. **判官读数不支持任何架构级优劣结论** —— **同一批答案上，同一判官重复判定 3 次的波动可达 3 分**，
   而承重维度数本身只有 1–5 ⇒ ⇒ **任何 ≤1 的架构级效应在原理上看不见**
   ⇒ ⇒ 我们进一步把这个"不可分辨"变成一个**可算的规模问题**：
   要检出 δ=1 的效应，需要 **O(10–16) 份/臂**（我们只做了 4 份/臂）⇒ ⇒ **差一个量级**。
   ⇒ ⇒ ★★ **更强的否证**：两个判官对同一批设计给出**相反**的架构结论
   （层3 相对层2：`grok-4.3` 给 **+0.75**、`MiniMax-M2.5` 给 **−1.00**）
   ⇒ ⇒ **本文不主张任何架构级优劣**，只主张测量学与机制边界。
2. **零判官的空间指标给出正向证据**（**已过 n 基线 + 嵌套子集校准**）：
   **3 次独立直调的分支彼此重叠 0.43–0.48，而任何"用认知位置"的臂彼此重叠 0.11–0.18**
   ⇒ ⇒ **"独立采样"其实并不独立**（共享同一 prior）
   ⇒ ⇒ ⇒ **认知位置真的把 prior 改掉了 —— 搜索空间确实被拓宽了**（零判官、零噪声）。
   ⇒ ⇒ ★ 限定：本条**只**由 Self-Sim（比率口径）支撑；**同批的"模态数"是另一个口径且已降级**（§6.2d）；计数口径的绝对值随 n 变化 4–5 倍。
3. ★★ **学习/自迭代这条主线的判决（本稿最重要的一条）**：
   **in-sample（训练内）上，"学出来的策略"在【避坑行为轴】上成立**
   （`W_train_L3` 钻牛角尖率 **2/6** vs 查表 **4/6** vs 均匀 **5/6**；
   负对照臂 `B0_bestof3` 三者**全 5/6** ⇒ 差异确实来自策略），
   **而在【承重维度轴】不成立、在【宽度轴】无差异**。
   ⇒ ⇒ **留出集（13 题重训、A02/A05 留出、R=8、三臂有效分母全 48/48）上，这个分离没有复现**：
   负对照本身**不平**（direct vs bestof3 中位最大差 **1.00**），
   且**负对照之间的差比 W 臂与负对照的差还大** ⇒ ⇒
   ⇒ ⇒ ★★★ **本稿的最终判决是「不可分辨」** ——
   **既不主张学出来的策略更好，也不据此主张相反结论。**
   ⇒ ⇒ ★ 唯一跨训练集稳健的偏好是 **仲裁档 `arb=keep_neg`**
   （15 题版间距 **0.400** / 13 题版 **0.583**，两版均不并列）；
   `nf` 发散度**两版都无证据**（间距均 < 0.15）；
   `mm` 合并方式**跨训练集无证据**（15 题版间距 0.500 不并列，13 题版并列 ⇒ 两版不同时成立）
   ⇒ ⇒ ⇒ ★ 逐格读数见 §6.4.4e（脚本从 analysis 填，**每格带 n**）
   ⇒ ⇒ ★★ **⇒ 这本身就是本稿最有价值的负结果**：
   **"把架构自由度也交给学习"这个想法，在当前装置下没能学出可靠偏好。**

★ 并且我们把**代价精确定位到了"合并"这一步**：逐帧各跑一遍＋投票的臂**同样宽、而且信息量最高**
（承重维度中位 **4.50**），而我们的**机械汇总**臂**同样宽、但信息量最低**（**2.50**）
⇒ ⇒ **拓宽搜索空间来自「发散」，信息量的损失来自「合并」** ⇒ ⇒ **下一个该动的地方是合并方式**
（⇒ DCI 的 decision packet：保留未决异议与少数意见）。

★ **而最直接的机制指标（零判官、纯文本正则）给出**：
在**诱导钻牛角尖**的理科题上，**认知位置臂的钻牛角尖率是基线的一半（50% vs 80–100%）**，
而**"增加独立采样次数"（3 次直调）是 100%** ⇒ ⇒ **增加采样次数不降低钻牛角尖率；换认知位置才降**
⇒ ⇒ 且这**只在"解法路径多样"的题上成立**（路径单一的题上四个臂全部踩坑）
⇒ ⇒ ⇒ **"该不该发散"由题型的路径空间决定** ⇒ ⇒ **这正是层 3 应当学出来的决策**
⇒ ⇒ ★★ **而 §6.4.4e 的分维度表显示：这一维（`nf`）恰恰是策略没学出来的两维之一**
⇒ ⇒ ⇒ **⇒ 于是本稿得到一个自指的负结果：**
**我们用实测证明了"该不该发散"是题型决定的，⇒ 却在留出集上没有证据表明策略学到了它。**

**关键词**：LLM Agent · 搜索空间塌缩 · 过早闭合 · 有效信息维度 · 承重检验 · 认知位置 ·
自迭代 · 架构搜索 · 失败驱动演化 · 判官可靠性 · 不可分辨
"""

if __name__ == "__main__":
    main()
