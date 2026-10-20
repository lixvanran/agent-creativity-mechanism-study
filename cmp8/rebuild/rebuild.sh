#!/bin/bash
# 一键重建 cmp8/ 树（与本包内文件一致）
# 用法：cd rebuild && bash rebuild.sh [目标目录]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-$HERE/..}"
cd "$DEST"
python3 rebuild/cmp8_p0.py
python3 rebuild/cmp8_p1.py
python3 rebuild/cmp8_p2.py
# p3（判官供应商切换）的功能已并入下面的 patch_or.py：重复执行是幂等的
python3 rebuild/patch_or.py cmp8
# 用包内完整版 README 覆盖 p2 里的简版（保证重建树与包内逐字节一致）
if [ -f "$DEST/README.md" ]; then cp "$DEST/README.md" cmp8/README.md; fi
# 方法文档也放进树根（用户在本地重建后同样能拿到）
for d in METHOD.md AGENT_RUNBOOK.md HANDOVER-cmp8-2026-10-20.md cmp8_fetch.py; do
  if [ -f "$DEST/$d" ]; then cp "$DEST/$d" cmp8/$d; fi
done
# 执行手册的补丁（唯一真相源，幂等）
python3 rebuild/patch_runbook.py cmp8/AGENT_RUNBOOK.md
# 方法学文档的补丁（唯一真相源，幂等）
if [ -f cmp8/METHOD.md ]; then
  python3 rebuild/patch_method.py cmp8/METHOD.md
fi
# 交接文件的两处补丁（唯一真相源，幂等）
if [ -f cmp8/HANDOVER-cmp8-2026-10-20.md ]; then
  python3 rebuild/patch_handover.py cmp8/HANDOVER-cmp8-2026-10-20.md
fi
# ⚠️ 改了这个脚本之后，"逐字节一致"不足以验收 —— 必须做负向测试：
#    把某个文件退回未打补丁状态 → 跑 rebuild.sh → 它应该被补回来。
#    （见同目录 selftest_negative.sh；§7 坑 27 实测：漏一步，逐字节 diff 照样全绿）
echo ">>> 重建完成：$DEST/cmp8"
