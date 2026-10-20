#!/bin/bash
# 一键重建 cmp8/ 树（与本包内文件一致）
#
# ★ 两种布局都支持（2026-10-20 修）：
#   包布局：  <pkg>/rebuild/rebuild.sh        ⇒ 树在 <pkg>/cmp8/      ⇒ DEST=<pkg>
#   仓库布局：<repo>/cmp8/rebuild/rebuild.sh  ⇒ 树在 <repo>/cmp8/     ⇒ DEST=<repo>
#   旧写法 DEST=$HERE/.. + 相对路径 rebuild/xxx.py ⇒ **仓库布局下路径错位**
#   （树会建到 cmp8/cmp8/，而且"逐字节 diff"看起来全绿 —— 假象）
#
# 用法：
#   bash rebuild.sh            # 自动识别布局
#   bash rebuild.sh <目标目录>  # 显式指定 DEST（树会建到 <目标目录>/cmp8/）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ -n "${1:-}" ]; then
  DEST="$1"
elif [ -d "$HERE/../cmp8" ]; then
  DEST="$HERE/.."          # 包布局：<pkg>/rebuild/  ⇒ 树在 <pkg>/cmp8/
else
  DEST="$HERE/../.."       # 仓库布局：<repo>/cmp8/rebuild/ ⇒ 树在 <repo>/cmp8/
fi
cd "$DEST"

# ★ 备份树内的文档（重建会重写整棵树；仓库布局下 METHOD/AGENT_RUNBOOK 只存在于树里，
#   不备份就会被删掉 —— 这就是"重建后文件变少"的那类静默损坏）
BACKUP="$(mktemp -d)"
trap 'rm -rf "$BACKUP"' EXIT
DOCS="METHOD.md AGENT_RUNBOOK.md HANDOVER-cmp8-2026-10-20.md cmp8_fetch.py README.md"
for d in $DOCS; do
  if [ -f "cmp8/$d" ]; then cp "cmp8/$d" "$BACKUP/$d"; fi
done

# ---- 生成（脚本一律用 $HERE 绝对路径 ⇒ 两种布局都对）----
python3 "$HERE/cmp8_p0.py"
python3 "$HERE/cmp8_p1.py"
python3 "$HERE/cmp8_p2.py"
# p3（判官供应商切换）的功能已并入下面的 patch_or.py：重复执行是幂等的
python3 "$HERE/patch_or.py" cmp8
# 判官闸门补「已知真断言」侧检查（行级、幂等）
[ -f cmp8/analyze_cmp6.py ] && python3 "$HERE/patch_gate.py" cmp8/analyze_cmp6.py

# ---- 文档回填 ----
#   HANDOVER：**包根的是源**（树里那份由它派生）⇒ 包根优先
#   其余（METHOD / AGENT_RUNBOOK / cmp8_fetch / README）：**树里的是权威**
#     ⇒ 仓库布局下它们本来就只存在于树里（仓库根那份 README 是旧的仓库 README）⇒ 树里优先
for d in METHOD.md AGENT_RUNBOOK.md cmp8_fetch.py README.md; do
  if [ -f "$BACKUP/$d" ]; then
    cp "$BACKUP/$d" "cmp8/$d"
  elif [ -f "$DEST/$d" ]; then
    cp "$DEST/$d" "cmp8/$d"
  fi
done
if [ -f "$DEST/HANDOVER-cmp8-2026-10-20.md" ]; then
  cp "$DEST/HANDOVER-cmp8-2026-10-20.md" "cmp8/HANDOVER-cmp8-2026-10-20.md"
elif [ -f "$BACKUP/HANDOVER-cmp8-2026-10-20.md" ]; then
  cp "$BACKUP/HANDOVER-cmp8-2026-10-20.md" "cmp8/HANDOVER-cmp8-2026-10-20.md"
fi

# ---- 补丁（唯一真相源，幂等）----
# 执行手册的补丁
[ -f cmp8/AGENT_RUNBOOK.md ] && python3 "$HERE/patch_runbook.py" cmp8/AGENT_RUNBOOK.md
# 方法学文档的补丁
[ -f cmp8/METHOD.md ] && python3 "$HERE/patch_method.py" cmp8/METHOD.md
# 交接文件的补丁
[ -f cmp8/HANDOVER-cmp8-2026-10-20.md ] && python3 "$HERE/patch_handover.py" cmp8/HANDOVER-cmp8-2026-10-20.md
# 最后一批文档修订（判官 temp=0 / 遍2 复用 / 坑 29 / METHOD 3b）
for d in HANDOVER-cmp8-2026-10-20.md METHOD.md; do
  [ -f "cmp8/$d" ] && python3 "$HERE/patch_docs_final.py" "cmp8/$d"
done
# 收官修订：§5.7/§5.8 浓缩版 + 坑 30 + 清陈旧残留（唯一真相源，幂等）
# ★ 根目录那份也要打 —— 否则 root 与 cmp8/ 树内会不一致（root 是被拷进树里的源）
for d in HANDOVER-cmp8-2026-10-20.md METHOD.md; do
  [ -f "cmp8/$d" ] && python3 "$HERE/patch_docs_mine.py" "cmp8/$d"
  [ -f "$d" ] && python3 "$HERE/patch_docs_mine.py" "$d"
done

echo ">>> 重建完成：$DEST/cmp8"
echo ">>> ⚠️ 改了这个脚本之后，\"逐字节一致\"不足以验收 —— 必须做负向测试："
echo ">>>    把某个文件退回未打补丁状态 → 跑 rebuild.sh → 它应该被补回来。"
echo ">>>    （见同目录 selftest_negative.sh；§7 坑 27 实测：漏一步，逐字节 diff 照样全绿）"
