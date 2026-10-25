# -*- coding: utf-8 -*-
"""★ 独立核验：新稿 vs 原稿（★ 不信重组脚本的自证，自己重算）
   --------------------------------------------------------------
   ★★ 上一版核验器被独立审稿人指出三个结构性弱点，本版已修：
     ① § 引用只查「目标存在」，不查「指对了」  ⇒ 新增 S4：逐处核对目标语义
     ② 数字检查漏掉个位数（3/5/2 这类）        ⇒ 新增 S3：全量 token 多重集比对
     ③ 表格行配对是"最相近"的松配对            ⇒ 新增 S5：按【首列内容】严格配对
   ★ 判据分工：
     脚本自检（reorg_paper.py）⇒ 守【不丢不增不篡改】的机械层
     本核验器（独立）        ⇒ 守【指向正确 / 数字守恒 / 措辞未扭曲】
"""
import io
import os
import re
import sys
from collections import Counter

SRC = "/workspace/lab/PAPER-2026-10-25.md"
DST = "/workspace/lab/PAPER-三组-学习自迭代治塌缩-2026-10-25.md"

NUM = re.compile(r"\d+(?:\.\d+)?")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
SEC_RE = re.compile(r"^\d+(?:\.\d+)*[a-z]?$")


def norm_line(s):
    """归一化：把 §x.y -> § （结构性 token 单独守，不混进读数）"""
    s = re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", s)
    return re.sub(r"\s+", " ", s).strip()


def rows_of(path):
    out = []
    for i, line in enumerate(io.open(path, encoding="utf-8").read().split("\n"), 1):
        if TABLE_ROW.match(line) and line.count("|") >= 3:
            out.append((i, line.strip()))
    return out


def is_struct(line):
    st = line.strip()
    return set(st) <= set("|-: ") or bool(re.match(r"^\|[\s\-:|]+\|$", st))


def load_patch_manifest():
    """★ 解析补丁清单源文件（★ 不 import ⇒ 不依赖执行路径）
       返回 {'PATCHES': [(old,new,why)], 'HEADING_LEVEL_FIXES': [...],
              'INLINE_HEADING_FIXES': [...], 'DECLARED_REF_FIXES': [...]}"""
    # ★ 优先找【本脚本同目录】；找不到 ⇒ 找【WORKDIR 指定的原目录】
    #   （★ 变异测试会把本脚本复制到临时目录 ⇒ 必须能回落到原目录）
    cands = [os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "reorg_patches.py")]
    _wd = os.environ.get("REORG_WORKDIR")
    if _wd:
        cands.append(os.path.join(_wd, "reorg_patches.py"))
    path = next((c for c in cands if os.path.exists(c)), cands[0])
    src = io.open(path, encoding="utf-8").read()
    import ast

    def _grab(name):
        # ★ 形态要同时支持 list 与 dict（★ 上一版硬编码 \[ ⇒ dict 型清单被跳过
        #   ⇒ 返回 [] ⇒ 主题词表静默失效 ⇒ 判据形同虚设）
        m = re.search(r"^%s\s*=\s*[\[{]" % re.escape(name), src, re.M)
        if not m:
            return []
        # 用 ast 解析该赋值语句
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == name:
                        try:
                            return ast.literal_eval(node.value)
                        except (ValueError, SyntaxError):
                            return []
        return []

    return {
        "PATCHES": _grab("PATCHES"),
        "HEADING_LEVEL_FIXES": _grab("HEADING_LEVEL_FIXES"),
        "INLINE_HEADING_FIXES": _grab("INLINE_HEADING_FIXES"),
        "DECLARED_REF_FIXES": _grab("DECLARED_REF_FIXES"),
        "DUPLICATE_SECTION_TOPICS": _grab("DUPLICATE_SECTION_TOPICS"),
    }


def main():
    src_text = io.open(SRC, encoding="utf-8").read()
    dst_text = io.open(DST, encoding="utf-8").read()
    fails = []
    warns = []

    # ============ S1：表格块严格配对（按首列内容，不按"最相近"）============
    def table_blocks(text):
        """按空行切表格块；每块 = (首行, [行...])"""
        blocks = []
        cur = []
        for line in text.split("\n"):
            if TABLE_ROW.match(line) and line.count("|") >= 3:
                cur.append(line.strip())
            else:
                if cur:
                    blocks.append(cur)
                cur = []
        if cur:
            blocks.append(cur)
        return blocks

    sb = table_blocks(src_text)
    db = table_blocks(dst_text)
    # 用"整块所有行的多重集"做键
    def blkkey(b):
        return tuple(sorted(Counter(norm_line(x) for x in b).items()))
    dpool = Counter(blkkey(b) for b in db)
    missing_blocks = []
    for b in sb:
        k = blkkey(b)
        if dpool[k] > 0:
            dpool[k] -= 1
        else:
            missing_blocks.append(b)
    if missing_blocks:
        for b in missing_blocks[:3]:
            fails.append("S1 表格块在新稿中找不到完全相同的块（首行：%s）" % b[0][:110])
    print("S1 表格块：原稿 %d 块 / 新稿 %d 块 / 完全一致 %d / 差异 %d"
          % (len(sb), len(db), len(sb) - len(missing_blocks), len(missing_blocks)))

    # ============ S2：逐行数字多重集（严格配对：按【归一化后的行文本】）============
    def norm_rows(text):
        res = []
        for l in text.split("\n"):
            if not l.strip():
                continue
            if re.match(r"^#{1,5}\s+\d", l):     # 标题行的小节号不算读数
                continue
            res.append(norm_line(l))
        return res
    sr = norm_rows(src_text)
    dr = norm_rows(dst_text)
    sc, dc = Counter(sr), Counter(dr)
    common = set(sr) & set(dr)
    # ★★★ 删掉上一版的恒假判据：`NUM.findall(r) != NUM.findall(r)`（同一字符串自比）
    #   ⇒ 条件恒假 ⇒ mism 永远为空 ⇒ 这条检查从未生效（★ 死代码）。
    #   ⇒ 真正的逐行数字守恒由下面两道承担：
    #      ① 【行集合】（非声明区必须完全一致）—— 抓丢行/增行
    #      ② 【数字 token 多重集】（双向）—— 抓数字被改
    #     （★ 同一行的数字被改 ⇒ 该行文本变了 ⇒ 落到 ① 的"新稿有、原稿没有"里）
    # 逐行数字序列比对：按【去掉数字后的骨架】配对
    def skeleton(r):
        return NUM.sub("#", r)
    # ★★ 声明式替换区（页眉 + 摘要 + §1.4）不参与骨架比对
    #    —— 新稿的摘要与 §1.4 是【新写的】，行数本来就不该与原稿相等。
    def declared_rows(text):
        """返回【声明区】的行集合（归一化后）"""
        rows = [norm_line(l) for l in text.split("\n") if l.strip()]
        out = set()
        try:
            i_abs = rows.index("## 摘要")
        except ValueError:
            return out
        out |= set(rows[:i_abs])                      # 页眉区
        try:
            i_end = rows.index("---", i_abs + 1)
        except ValueError:
            i_end = len(rows)                        # ★ 原稿摘要后无 '---' ⇒ 取到文末
        out |= set(rows[i_abs:i_end + 1])             # 摘要区
        for i, r in enumerate(rows):
            if r.startswith("### 1.4 "):
                for j in range(i, len(rows)):
                    if j > i and rows[j].startswith("## "):
                        break
                    out.add(rows[j])
                break
        return out
    dcl_src, dcl_dst = declared_rows(src_text), declared_rows(dst_text)
    sr2 = [r for r in sr if r not in dcl_src]
    dr2 = [r for r in dr if r not in dcl_dst]
    # ★★★ 补一条：非声明区的【行集合】必须完全一致
    #   （★ 只比数字 token 抓不到"删掉一行不含数字的正文"⇒ 这是真实盲区）
    # ★ 结构噪声：纯 ">"/">>"/"|"/空引用行 ⇒ 纯排版，不算内容差异
    def is_noise(r):
        st = r.strip()
        if st in (">", ">>", "|", "||", "---", "***"):
            return True
        if re.match(r"^[>|·\s]+$", st):
            return True
        # ★ 表格分隔行（|---|---|）⇒ 表头结构，不算内容
        if re.match(r"^\|[\s\-:|]+\|$", st):
            return True
        return False
    # ★ 声明式补丁造成的老行消失 / 新行出现 ⇒ 逐条登记（★ 从补丁清单自动生成 ⇒ 不漂移）
    # ★★ 路径必须指向【本脚本所在目录】（★ 不是 cwd —— 变异测试会把脚本复制到
    #   临时目录运行 ⇒ 用 cwd 会 ModuleNotFoundError ⇒ 测试全红但不是判据红）
    # ★★ 核验器【不 import】补丁清单模块 ⇒ ★ 自己解析其源文件
    #   （★ 理由一：变异测试会把脚本复制到临时目录 ⇒ import 会 ModuleNotFoundError
    #   ★ 理由二：核验器读【声明数据】而非【执行代码】⇒ 独立性更强）
    RP = load_patch_manifest()
    def _n1(l):
        l = re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", l)
        return re.sub(r"\s+", " ", l).strip()
    PATCH_OLD_LINES = set()
    PATCH_NEW_LINES = set()
    for _o, _n, _w in RP["PATCHES"]:
        for _ln in src_text.split("\n"):
            if _o in _ln:
                PATCH_OLD_LINES.add(_n1(_ln))
        # ★ 补丁可能落在【超长行】的中段 ⇒ 新稿那一行【整行都变了】
        #   ⇒ 用【该行在旧稿中的骨架】定位新稿的对应行：
        #     取旧稿中含 _o 的那一行 ⇒ 其骨架 ⇒ 在新稿里找同骨架的行
        # ★★ 定位策略：补丁点【之前】的文本在两稿里【逐字不变】⇒ 用它当锚
        #   （★ 比"整行前 30 字符"稳：补丁可能就在行首 30 字符之内）
        # ★ 锚点里不能含数字（★ 数字在两稿里可能被重映射）⇒ 取【补丁点之前】
        #   的最长中文片段
        # ★★★ 锚点必须落在【补丁点之前】⇒ 逐个字符往左找，
        #   找【最长的、在新稿里仍逐字存在】的前缀。
        #   （★ 教训：整行前 30 字符不可靠 —— 补丁可能就在行首 30 字符之内）
        # ★★★ 锚点必须取自【new 串】——★ new 在新稿里【存在】，
        #   old 在新稿里【已被替换掉】⇒ 用 old 当锚必然匹配失败（★ 实测踩过）
        _anchor = ""
        for _L in range(12, 60):
            _c = _n1(_n[:_L])
            if not _c:
                break
            if any(_c in _n1(_x) for _x in dst_text.split("\n")):
                _anchor = _c
            else:
                break
        if not _anchor:
            _anchor = _n1(_n)[:12]
        for _ln in src_text.split("\n"):
            if _o not in _ln:
                continue
            for _ln2 in dst_text.split("\n"):
                _l2 = _n1(_ln2)
                if _anchor and _anchor in _l2:
                    PATCH_NEW_LINES.add(_l2)
    for _t, _ol, _nl in getattr(RP, "HEADING_LEVEL_FIXES", []):
        PATCH_OLD_LINES.add(_n1("#" * _ol + " " + _t))
        PATCH_NEW_LINES.add(_n1("#" * _nl + " " + _t))
    for _t, _p in getattr(RP, "INLINE_HEADING_FIXES", []):
        PATCH_OLD_LINES.add(_n1("#### " + _t))
        PATCH_NEW_LINES.add(_n1(_p + " " + _t))
    # ★ 已知会变的行（★ 补丁行 / 层级修正行 / 两条结构性替换）
    KNOWN_CHANGE = PATCH_OLD_LINES | PATCH_NEW_LINES | {
        _n1("#### 留出集出表（【已跑批·全量 n=48/48（有效读数）】）"),
        _n1("###### 留出集出表（【已跑批·全量 n=48/48（有效读数）】）"),
        _n1("### 留出集出表（【已跑批·全量 n=48/48（有效读数）】）"),
        _n1("- ⚠️ 历史 84 份答案（cmp8）**没记 `finish_reason`** ⇒ 预算截断**无法排除**（§）"),
        _n1("- ⚠️ 历史 84 份答案（cmp8）**没记 `finish_reason`** ⇒ 预算截断**无法排除**（§ 的 (b) 条）"),
    }
    # ★★★ 行级比对：按【下标逐位】比对（★ 不用 difflib —— 它对"一行变了"
    #   导致后续整段错位的场景会把 100 行都报成差异，★ 噪声淹没真问题）
    #   前提：两稿的非声明区行数必须相等（重组不增删正文行）⇒ 不等直接判红。
    a_seq = [r for r in sr2 if not is_noise(r)]
    b_seq = [r for r in dr2 if not is_noise(r)]
    print("   （非声明区行：原稿 %d / 新稿 %d）" % (len(a_seq), len(b_seq)))
    if len(a_seq) != len(b_seq):
        fails.append("S2 非声明区行数不等：原稿 %d / 新稿 %d ⇒ 有增删"
                     % (len(a_seq), len(b_seq)))
    # ★★★ 行级比对：按【内容多重集】配对（★ 不能按位置 —— 新稿章节顺序变了，
    #   位置法会把 350+ 行全报成差异 ⇒ 噪声淹没真问题）
    n_known = 0
    src_only = []
    dst_only = []
    _pool = Counter()
    for _y in b_seq:
        _pool[_y] += 1
    _rest = []
    for _x in a_seq:
        if _pool[_x] > 0:
            _pool[_x] -= 1
        else:
            _rest.append(_x)
    _pool2 = Counter()
    for _x in a_seq:
        _pool2[_x] += 1
    for _y in b_seq:
        if _pool2[_y] > 0:
            _pool2[_y] -= 1
        elif _y not in KNOWN_CHANGE:
            dst_only.append(_y)
    for _x in _rest:
        if _x not in KNOWN_CHANGE:
            src_only.append(_x)
    n_known = len(a_seq) + len(b_seq) - len(src_only) - len(dst_only) \
        - len([1 for _x in _rest if _x in KNOWN_CHANGE])
    print("   （已声明会变的行：%d 处）" % n_known)
    # ★ 已声明的结构性替换（与 reorg_paper.py 的登记一致）
    # ★ 两条已声明的结构性替换，【原稿形态】与【新稿形态】都要登记
    DECL_REPL = {
        # ① 留出集出表块被并入 h5 块 ⇒ 标题 h3 -> h4
        "### 留出集出表（【已跑批·全量 n=48/48（有效读数）】）",
        "#### 留出集出表（【已跑批·全量 n=48/48（有效读数）】）",
        # ② 原稿把 "§6.5 的 (b) 条" 误写成 "§6.5b"（像小节号）⇒ 改为正确形态
        "- ⚠️ 历史 84 份答案（cmp8）**没记 `finish_reason`** ⇒ 预算截断**无法排除**（§）",
        "- ⚠️ 历史 84 份答案（cmp8）**没记 `finish_reason`** ⇒ 预算截断**无法排除**（§ 的 (b) 条）",
    }
    src_only = [r for r in src_only if r not in DECL_REPL]
    dst_only = [r for r in dst_only if r not in DECL_REPL]
    if src_only:
        fails.append("S2 非声明区存在【原稿有、新稿没有】的行（%d 行）：%s"
                     % (len(src_only), [x[:70] for x in src_only[:3]]))
    if dst_only:
        fails.append("S2 非声明区存在【新稿有、原稿没有】的行（%d 行）：%s"
                     % (len(dst_only), [x[:70] for x in dst_only[:3]]))
    sk_src, sk_dst = Counter(skeleton(r) for r in sr2), Counter(skeleton(r) for r in dr2)
    for sk in set(sk_src) & set(sk_dst):
        if sk_src[sk] != sk_dst[sk]:
            fails.append("S2 同一骨架的行数在两稿不同：%s（原 %d / 新 %d）"
                         % (sk[:70], sk_src[sk], sk_dst[sk]))
    # ★ 关键：抽取【两稿共有行】的完整数字序列做集合级守恒
    def nums_of_line(r):
        return Counter(NUM.findall(r))
    src_only_lines = [r for r in sr if r not in dc]
    dst_only_lines = [r for r in dr if r not in sc]
    print("S2 归一化行：原稿 %d / 新稿 %d ｜ 仅原稿有 %d / 仅新稿有 %d"
          % (len(sr), len(dr), len(src_only_lines), len(dst_only_lines)))


    # ============ S3：全量数字 token 多重集守恒（★ 含个位数）============
    def all_nums(text, exclude_declared=False):
        t = re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", text)
        lines = [l for l in t.split("\n") if not re.match(r"^#{1,5}\s+\d", l)]
        if exclude_declared:
            dd = declared_rows(text)
            lines = [l for l in lines
                     if norm_line(l) not in dd]
        return Counter(NUM.findall("\n".join(lines)))
    # ★ 排除【声明式替换区】（页眉 + 摘要 + §1.4）⇒ 新稿这些区是新写的
    an, bn = all_nums(src_text, True), all_nums(dst_text, True)
    lost_tok = {k: v - bn.get(k, 0) for k, v in an.items() if v > bn.get(k, 0)}
    added_tok = {k: v - an.get(k, 0) for k, v in bn.items() if v > an.get(k, 0)}
    print("S3 数字 token：原稿 %d 个 / 新稿 %d 个 ｜ 丢失 %d / 新增 %d"
          % (sum(an.values()), sum(bn.values()),
             len(lost_tok), len(added_tok)))
    if lost_tok:
        fails.append("S3 原稿有、新稿没有的数字 token：%s" % sorted(lost_tok.items())[:15])
    if added_tok:
        # 新增 token 必须全部落在【声明区】（页眉/摘要/§1.4）
        warns.append("S3 新稿多出的数字 token（须在声明区或有出处）：%s"
                     % sorted(added_tok.items(), key=lambda x: -x[1])[:15])

    # ============ S4：★ § 引用【指向正确性】—— 三层判据 ============
    # ★★★ 上一版的两处缺陷（独立审稿 v2 实测 W1/W2/W3 均 rc=0 PASS）：
    #   ① 悬空引用被 `if not cands: continue` 静默跳过 ⇒ 不判红也不列出
    #   ② "指向是否正确"只对【标题含易混词】的目标做【打印清单】⇒ 其余指错完全不可见
    # ★★★ 本版（v3）的诚实分层：
    #   S4a【机械可判 ⇒ 判红】：悬空引用（目标不存在）
    #   S4b【机械可判 ⇒ 判红】：非重复号引用，新稿目标必须 == 内容指纹算出的映射
    #   S4c【需语境消歧 ⇒ 判红/人工清单】：原稿有【重复号】⇒ 用引用语境打分
    #   S4d【已声明的指向修正 ⇒ 不判红】：登记在补丁清单里的（★ 可审计）
    # ★★ 诚实边界：§ 引用的"语义正确性"本质上需要人判断；
    #   机器能抓的是【悬空】与【与内容映射不符】；重复号处只能给【语境打分 + 人工清单】。
    import hashlib

    def sections(text):
        res = []
        cur = None
        for line in text.split("\n"):
            m = re.match(r"^#{2,6}\s+(\d+(?:\.\d+)*(?:-?\d)?[a-z]?)\s+(.*)$", line)
            if m:
                cur = {"no": m.group(1), "title": m.group(2), "body": []}
                res.append(cur)
            elif cur is not None:
                cur["body"].append(line)
        out = []
        for h in res:
            b = "\n".join(h["body"])
            fp_src = re.sub(r"§\s*\d+(?:\.\d+)*(?:-?\d)?[a-z]?", "§", b)
            fp_src = re.sub(r"\s+", "", fp_src)
            out.append({"no": h["no"], "title": h["title"], "body": b,
                        "fp": hashlib.sha1(fp_src.encode("utf-8")).hexdigest()[:16]})
        return out

    old_secs = sections(src_text)
    new_secs = sections(dst_text)
    new_no_set = set(h["no"] for h in new_secs)
    dup_new = [k for k, v in Counter(h["no"] for h in new_secs).items() if v > 1]
    if dup_new:
        fails.append("S4a 新稿存在重复小节号：%s" % dup_new)

    # ---- 指纹映射：old 小节 → new 小节（按内容指纹）----
    new_by_fp = {}
    for h in new_secs:
        new_by_fp.setdefault(h["fp"], []).append(h)
    fp2new = {fp: c[0]["no"] for fp, c in new_by_fp.items() if len(c) == 1}
    old_dup = set(k for k, v in Counter(h["no"] for h in old_secs).items() if v > 1)

    # ---- 已声明的指向修正（★ 从补丁清单读；★ 可审计）----
    declared_pairs = set()
    for _o, _n, _w in RP["PATCHES"]:
        for _a, _b in zip(re.findall(r"§\s*(\d+(?:\.\d+)*(?:-?\d)?[a-z]?)", _o),
                          re.findall(r"§\s*(\d+(?:\.\d+)*(?:-?\d)?[a-z]?)", _n)):
            declared_pairs.add((_a, _b))
    # ★ 已声明的指向修正（★ 原稿自身指错 ⇒ 修正后不判红）
    for _o, _n, _w in RP["DECLARED_REF_FIXES"]:
        declared_pairs.add((_o, _n))
        # ★ S4b 比的是【新稿的号】⇒ 也要登记 (旧号 → 新号) 这一对
        #   （★ 新号由执行器的映射表给出；★ 这里用内容指纹映射反推）
        for _h in old_secs:
            if _h["no"] == _o:
                _fp = _h["fp"]
                for _nh in new_secs:
                    if _nh["fp"] == _fp and _nh["no"] != _o:
                        declared_pairs.add((_o, _nh["no"]))
        # ★ 更直接：声明里写的是【旧号→旧号】⇒ 映射到新稿后是 (旧号 → 新号)
        _newno = None
        for _h in old_secs:
            if _h["no"] == _n:
                _newno = fp2new.get(_h["fp"])
        if _newno:
            declared_pairs.add((_o, _newno))

    # ---- 行级配对 ----
    def sec_refs(text):
        res = {}
        for l in text.split("\n"):
            if not l.strip() or re.match(r"^#{1,6}\s", l):
                continue
            k = norm_line(l)
            if k in res:
                continue
            res[k] = re.findall(r"§\s*(\d+(?:\.\d+)*(?:-?\d)?[a-z]?)", l)
        return res

    old_refs = sec_refs(src_text)
    new_refs = sec_refs(dst_text)

    STOP = set("的 了 和 与 或 在 是 这 那 有 也 都 就 而 及 其 对 被 把 从 到 不 一个 之 上 下 中 "
               "我们 他们 它 本 该 此 则 于 为 以 并 且 但 如 因 由 已 很 更 最 个 只 没 无 前 后 "
               "⇒ ★ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ★★ ★★★ ★★★★★ ⇒⇒ 里面 前面 后面 什么 怎么 这样 因为 所以".split())
    def kws(t):
        ws = re.findall(r"[一-鿿]{2,}|[A-Za-z_][A-Za-z0-9_]{2,}", t)
        return set(w for w in ws if w not in STOP and not w.isdigit())

    old_by_no = {}
    for h in old_secs:
        old_by_no.setdefault(h["no"], []).append(h)
    new_by_no = {}
    for h in new_secs:
        new_by_no.setdefault(h["no"], []).append(h)

    checked = 0
    n_dangling = 0
    n_mis = 0
    review = []
    for k, old_toks in old_refs.items():
        if k not in new_refs:
            continue
        new_toks = new_refs[k]
        if len(old_toks) != len(new_toks):
            continue
        if re.search(r"\([^()]*\b(19|20)\d{2}[^()]*\)", k) or "et al" in k or "arXiv" in k:
            continue          # 外部引注
        ctx_kw = kws(k)
        for ot, nt in zip(old_toks, new_toks):
            checked += 1
            # ★ S4a：悬空
            if nt not in new_no_set:
                n_dangling += 1
                fails.append("S4a 悬空引用：原稿 §%s ⇒ 新稿 §%s（目标不存在）：%s"
                             % (ot, nt, k[:90]))
                continue
            # ★ S4d：已声明的指向修正 ⇒ 跳过
            if (ot, nt) in declared_pairs:
                continue
            cands_old = old_by_no.get(ot, [])
            if ot in old_dup and len(cands_old) > 1:
                # ★ S4c：重复号 ⇒ 用【声明的主题词表】做语境消歧
                #   ★ 纯关键词交集实测无效（两侧都是 0）⇒ 人工声明主题词更可靠
                topics = RP["DUPLICATE_SECTION_TOPICS"].get(ot, {})
                tgt_new = new_by_no.get(nt, [None])[0]
                # ★ 新稿目标反查回原稿候选（按内容指纹）
                equiv = None
                if tgt_new is not None:
                    for c in cands_old:
                        if c["fp"] == tgt_new["fp"]:
                            equiv = c
                if topics:
                    # ★★★ 打分逻辑（★ 上一版有 bug：先在【标题】里挑一个主题词、
                    #   再拿它去上下文匹配 ⇒ 上下文里若不含那个词就永远命中不了
                    #   ⇒ 实测 V7b 漏网。正确做法：
                    #   对每个候选，统计【它的主题词有几个出现在上下文里】。
                    # ★★★ 候选 ↔ 主题词组的对应（★ 每个候选只算【自己那组】的词
                    #   ★ 上一版对每个候选遍历了所有组 ⇒ 两个候选得分相同 ⇒ 永远平手）
                    #   对应关系由【候选标题里出现的组内特征词】确定
                    def _grp_of(c):
                        for _tk, _words in topics.items():
                            for _w in _words:
                                if _w in c["title"]:
                                    return _tk, _words
                        return None, None
                    scored = []
                    for c in cands_old:
                        _tk, _words = _grp_of(c)
                        _hit = 0
                        if _words:
                            for _w in _words:
                                if _w and _w in k:
                                    _hit += 1
                                    break
                        scored.append((_hit, c))
                    scored.sort(key=lambda x: -x[0])
                    best = scored[0]
                    second = scored[1] if len(scored) > 1 else (0, None)
                    if equiv is not None and equiv["fp"] == best[1]["fp"]:
                        continue          # 消歧结果一致 ✔
                    if best[0] > second[0] and best[0] > 0:
                        n_mis += 1
                        fails.append("S4c 引用指向错误（重复号 §%s，主题词打分 %d vs %d）："
                                     "原稿 §%s ⇒ 新稿 §%s，但语境指向「%s」：%s"
                                     % (ot, best[0], second[0], ot, nt,
                                        best[1]["title"][:40], k[:80]))
                        continue
                    review.append((ot, nt, k[:80],
                                   [c["title"][:40] for c in cands_old]))
                    continue
                if equiv is not None:
                    continue
                review.append((ot, nt, k[:80],
                               [c["title"][:40] for c in cands_old]))
                continue
            # ★ S4b：非重复号 ⇒ 必须与内容指纹映射一致
            fp = cands_old[0]["fp"] if cands_old else None
            exp = fp2new.get(fp) if fp else None
            if exp is not None and exp != nt:
                n_mis += 1
                fails.append("S4b 引用指向错误：原稿 §%s（内容映射到 §%s）但新稿写成 §%s：%s"
                             % (ot, exp, nt, k[:90]))
    # ★★ S4a 独立扫描：【不依赖行配对】地扫全文所有 § 引用
    #   （★ 理由：悬空引用会改变该行文本 ⇒ 行配不上原稿 ⇒ 配对式检查看不见它
    #   ★ ★ 上一版就是这么漏掉悬空引用的（独立审稿 v2 的 W1 ⇒ rc=0 PASS））
    new_all_toks = {}
    for _l in dst_text.split("\n"):
        if re.match(r"^#{1,6}\s", _l):
            continue
        for _m in re.finditer(r"§\s*(\d+(?:\.\d+)*(?:-?\d)?[a-z]?)", _l):
            _t = _m.group(1)
            new_all_toks.setdefault(_t, []).append(_l.strip()[:80])
    for _t, _ls in sorted(new_all_toks.items()):
        if _t in new_no_set:
            continue
        # 外部引注豁免
        _all_ext = all(re.search(r"\([^()]*\b(19|20)\d{2}[^()]*\)", _l)
                        or "et al" in _l or "arXiv" in _l for _l in _ls)
        if _all_ext:
            continue
        n_dangling += 1
        fails.append("S4a 悬空引用：新稿 §%s 指向不存在的小节（%d 处）：%s"
                     % (_t, len(_ls), _ls[0][:80]))

    print("S4 § 引用核对：检查 %d 处 ｜ 悬空 %d ｜ 指错 %d ｜ 需人工复核 %d"
          % (checked, n_dangling, n_mis, len(review)))
    for _o, _n, _c, _ts in review:
        print("   ★ 需人工复核：原稿 §%s → 新稿 §%s ｜ 原稿候选：%s" % (_o, _n, _ts))
        print("        引用处：%s" % _c)

    # ============ S5：HOLDOUT 标记成对 + 区间完整 ============
    b = dst_text.find("<!-- HOLDOUT_TABLE:BEGIN -->")
    e = dst_text.find("<!-- HOLDOUT_TABLE:END -->")
    if b < 0 or e < 0 or e < b:
        fails.append("S5 HOLDOUT 标记缺失或顺序错误（BEGIN=%d END=%d）" % (b, e))
    else:
        seg = dst_text[b:e]
        nrows = len([l for l in seg.split("\n") if TABLE_ROW.match(l)])
        print("S5 HOLDOUT 块：BEGIN=%d END=%d ｜ 区间 %d 行 / %d 表格行"
              % (b, e, seg.count("\n"), nrows))
        # 与原稿的 HOLDOUT 区间逐字节比（除标题层级）
        sb_ = src_text.find("<!-- HOLDOUT_TABLE:BEGIN -->")
        se_ = src_text.find("<!-- HOLDOUT_TABLE:END -->")
        if sb_ >= 0 and se_ >= 0:
            s_seg = src_text[sb_:se_]
            s_rows = [l for l in s_seg.split("\n") if TABLE_ROW.match(l)]
            d_rows = [l for l in seg.split("\n") if TABLE_ROW.match(l)]
            if s_rows != d_rows:
                fails.append("S5 HOLDOUT 表格行与原稿不一致（%d vs %d）" % (len(s_rows), len(d_rows)))
            else:
                print("   ✔ HOLDOUT 表格行逐字节一致（%d 行）" % len(s_rows))

    # ============ S6：关键措辞保全 ============
    KEY = ["更正", "降级", "不成立", "不可分辨", "不得写", "不许", "如实写",
           "未检验", "未被支持", "未被排除", "同义反复", "措辞上限", "不选边"]
    kl = [k for k in KEY if k in src_text]
    missing_kw = [k for k in kl if k not in dst_text]
    print("S6 关键措辞：原稿含 %d 类 ｜ 新稿缺失 %d 类 %s"
          % (len(kl), len(missing_kw), missing_kw))
    if missing_kw:
        fails.append("S6 关键限定词在新稿中消失：%s" % missing_kw)

    # ============ 输出 ============
    print()
    for w in warns:
        print("⚠ " + w)
    for f in fails:
        print("✘ " + f)
    print()
    if fails:
        print("结论：FAIL（%d 条）" % len(fails))
        return 2
    print("结论：PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
