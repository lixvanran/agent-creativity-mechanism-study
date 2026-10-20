#!/usr/bin/env bash
# =====================================================================
# 负向测试（故障注入）—— 证明 rebuild.sh **流程完整**，而不只是"重建是确定性的"
#
# ★ 为什么需要这个（§7 坑 27 实测）：
#   交付包里每个文件**本身已经是打过补丁的最终态**，重建时被原样拷进树里
#   ⇒ "干净解压 → rebuild → 逐字节 diff" **照样全绿**，
#     哪怕 rebuild.sh **漏了一个 patch 步骤**（实测漏过 patch_method.py）。
#   ⇒ 逐字节 diff 只证明「重建是幂等的」，**不证明「流程完整」**。
#
# ★ 本脚本干什么：
#   逐个 patch 步骤做**故障注入**：把它的**输入**故意退回未打补丁状态
#   → 跑 rebuild.sh → 断言**树里**的结果被补回来。
#   补不回来 = 该步骤没接进 rebuild.sh = 流程缺步 ⇒ 退出码非 0。
#
#   注意"输入"与"产物"的位置不同：
#     - 核心库（orclient.py 等）的输入是 **cmp8_p1.py 内嵌的原文**
#     - 三份文档的输入是**包根**的 METHOD.md / AGENT_RUNBOOK.md / HANDOVER-*.md
#     - 断言一律读**树里**的 cmp8/<文件>（那才是 rebuild.sh 真正产出的东西）
#
# 用法：cd rebuild && bash selftest_negative.sh
# 期望：4 个 case 全 PASS，退出码 0。
# =====================================================================
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
PKGROOT="$(cd "$HERE/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0
say() { printf '%s\n' "$*"; }

# ---------------------------------------------------------------- 准备干净副本
WORK="$TMP/work"
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$PKGROOT" "$WORK/pkg"
cd "$WORK/pkg"

# =====================================================================
# case 1 · patch_or.py —— 默认模型
#   注意：这一条与另外三条"形态"不同。
#   patch_or 的**输入**是 cmp8_p1.py 内嵌的原文，而 p1 本身就是"未打补丁"的源
#   （默认模型永远是已 404 的 grok-3-mini）⇒ 所以：
#     1a) 正向：从零重建 ⇒ 树内默认模型**必须**被 patch_or 换成新值
#     1b) 变异：把 rebuild.sh 里 patch_or 那一行**删掉**（= 注入"漏一步"这个故障）
#              ⇒ 树内默认模型**必须仍是旧值**（= 证明这个测试真能抓到"漏一步"）
# =====================================================================
say "--- case 1a · patch_or.py（默认模型：正向）---"
bash rebuild/rebuild.sh > "$WORK/rb1.log" 2>&1 || { say "  ✗ rebuild.sh 退出非 0"; FAIL=$((FAIL+1)); }
if python3 - <<'PY'
import io, sys
import re
s = io.open("cmp8/creativity_lab/orclient.py", encoding="utf-8").read()
m = re.search(r'^PRIMARY = .*$', s, re.M)
sys.exit(0 if (m and "x-ai/grok-4.3" in m.group(0) and "grok-3-mini" not in m.group(0)) else 1)
PY
then say "  ✔ 树内默认模型已被 patch_or 换新"; PASS=$((PASS+1))
else say "  ✗ 树内默认模型**没有**被换新 ⇒ rebuild.sh 缺 patch_or 这一步"; FAIL=$((FAIL+1)); fi

say "--- case 1b · patch_or.py（默认模型：变异注入"漏一步"）---"
cp rebuild/rebuild.sh "$WORK/rebuild.sh.bak"
python3 - <<'PY'
import io
p = "rebuild/rebuild.sh"
s = io.open(p, encoding="utf-8").read()
s = s.replace("python3 rebuild/patch_or.py cmp8\n", "# (变异注入：故意删掉 patch_or 这一步)\n", 1)
io.open(p, "w", encoding="utf-8").write(s)
print("  （已把 rebuild.sh 里 patch_or 那一步删掉）")
PY
bash rebuild/rebuild.sh > "$WORK/rb1b.log" 2>&1
if python3 - <<'PY'
import io, sys
import re
s = io.open("cmp8/creativity_lab/orclient.py", encoding="utf-8").read()
m = re.search(r'^PRIMARY = .*$', s, re.M)
sys.exit(0 if (m and "x-ai/grok-3-mini" in m.group(0)) else 1)
PY
then say "  ✔ 变异被检测到：删掉 patch_or 后树内确实回到旧默认模型 ⇒ 本测试能抓到『漏一步』"
     PASS=$((PASS+1))
else say "  ✗ 变异**没**被检测到 ⇒ 这个测试抓不到『漏一步』（测试本身失效）"; FAIL=$((FAIL+1)); fi
cp "$WORK/rebuild.sh.bak" rebuild/rebuild.sh   # 还原
say "  （已还原 rebuild.sh）"

# =====================================================================
# case 2 · patch_runbook.py —— 阶段 1 的「进对目录」
# =====================================================================
say "--- case 2 · patch_runbook.py（阶段 1 目录名）---"
python3 - <<'PY'
import io
p = "AGENT_RUNBOOK.md"
s = io.open(p, encoding="utf-8").read()
i = s.find("## 阶段 1 · 定位实验根目录 + 静态自检")
j = s.find("## 阶段 2 · 冒烟", i)
if i < 0 or j < 0:
    print("  ⚠ 找不到阶段 1 区块，跳过注入")
else:
    old = ("## 阶段 1 · 重建 + 静态自检\n\n"
           "```bash\ncd cmp8pkg && bash rebuild/rebuild.sh\n```\n\n---\n\n")
    io.open(p, "w", encoding="utf-8").write(s[:i] + old + s[j:])
    print("  （已把阶段 1 退回成 cd cmp8pkg 的旧版）")
PY
bash rebuild/rebuild.sh > "$WORK/rb2.log" 2>&1 || { say "  ✗ rebuild.sh 退出非 0"; FAIL=$((FAIL+1)); }
if python3 - <<'PY'
import io, sys
s = io.open("cmp8/AGENT_RUNBOOK.md", encoding="utf-8").read()
sys.exit(0 if ("定位实验根目录" in s and "进对目录" in s) else 1)
PY
then say "  ✔ 树内手册已被 patch_runbook 补回"; PASS=$((PASS+1))
else say "  ✗ 树内手册**没有**被补回 ⇒ rebuild.sh 缺 patch_runbook 这一步"; FAIL=$((FAIL+1)); fi

# =====================================================================
# case 3 · patch_method.py —— §4.3 + 耗时
# =====================================================================
say "--- case 3 · patch_method.py（§4.3 矛盾率分母为 0）---"
python3 - <<'PY'
import io
p = "METHOD.md"
s = io.open(p, encoding="utf-8").read()
i = s.find("### 4.3 ⚠️ 矛盾率在")
j = s.find("---", i)
if i < 0 or j < 0:
    print("  ⚠ 找不到 §4.3，跳过注入")
else:
    s = s[:i] + s[j:]
    import re as _re
    s = _re.sub(r"\*\*耗时\*\*：跑批 .*?主要来源\)。",
                "**耗时**：跑批 1.5–2 小时（`--workers 4`）。", s, flags=_re.S)
    io.open(p, "w", encoding="utf-8").write(s)
    print("  （已把 §4.3 与耗时退回旧版）")
PY
bash rebuild/rebuild.sh > "$WORK/rb3.log" 2>&1 || { say "  ✗ rebuild.sh 退出非 0"; FAIL=$((FAIL+1)); }
if python3 - <<'PY'
import io, sys
s = io.open("cmp8/METHOD.md", encoding="utf-8").read()
sys.exit(0 if ("4.3 ⚠️ 矛盾率在" in s and "实测 ≈3.5–4 小时" in s) else 1)
PY
then say "  ✔ 树内方法学已被 patch_method 补回"; PASS=$((PASS+1))
else say "  ✗ 树内方法学**没有**被补回 ⇒ rebuild.sh 缺 patch_method 这一步"; FAIL=$((FAIL+1)); fi

# =====================================================================
# case 4 · patch_handover.py —— 坑表第 26/27 行
# =====================================================================
say "--- case 4 · patch_handover.py（坑表 26/27 行）---"
python3 - <<'PY'
import io
p = "HANDOVER-cmp8-2026-10-20.md"
s = io.open(p, encoding="utf-8").read()
lines = [l for l in s.split("\n") if not (l.startswith("| 26 |") or l.startswith("| 27 |"))]
io.open(p, "w", encoding="utf-8").write("\n".join(lines))
print("  （已把坑表第 26/27 行删掉）")
PY
bash rebuild/rebuild.sh > "$WORK/rb4.log" 2>&1 || { say "  ✗ rebuild.sh 退出非 0"; FAIL=$((FAIL+1)); }
if python3 - <<'PY'
import io, sys
s = io.open("cmp8/HANDOVER-cmp8-2026-10-20.md", encoding="utf-8").read()
sys.exit(0 if ("| 27 |" in s and "| 26 |" in s) else 1)
PY
then say "  ✔ 树内交接文件已被 patch_handover 补回"; PASS=$((PASS+1))
else say "  ✗ 树内交接文件**没有**被补回 ⇒ rebuild.sh 缺 patch_handover 这一步"; FAIL=$((FAIL+1)); fi

say ""
say "=== 结果：PASS $PASS ／ FAIL $FAIL ==="
if [ "$FAIL" -ne 0 ]; then
  say "❌ 重建流程**不完整**：有 patch 步骤没接进 rebuild.sh（见上面 ✗ 的 case）"
  exit 1
fi
say "✅ 重建流程完整：每个 patch 步骤都能在故障注入后被补回"
say "   （提醒：这证明「流程完整」；「重建是幂等的」由逐字节 diff 证明 —— 两者都要做）"
exit 0
