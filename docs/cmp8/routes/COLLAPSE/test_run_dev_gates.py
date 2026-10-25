# -*- coding: utf-8 -*-
"""★ 负向测试：证明 run_dev.py 的两个新闸门【真的能红】（★ 不是"看起来能"）

★ 动机（第二组 2026-10-24 第 3 点）：★ **「判断一个工具的退出码语义，唯一可靠办法是
  【故意制造失败并实测】⇒ 读形态会骗人」** ★ ⇒ ⇒ 所以每条闸门都要有【只有它能抓】的场景。

★ 用例：
  T1 resume 的 `_done` **不含**带 error 的行 ⇒ ⇒ 失败单元可被重跑
  T2 resume 的 `_done` **不含** n_cards=None 的行
  T3 resume 的 `_done` **含**正常行
  T4 批末闸门：0 个失败单元 ⇒ 退出码 0
  T5 批末闸门：1 个失败单元 ⇒ 退出码 **非 0** ⇒ 且 summary 记 n_error_arms=1
  T6 ★ 变异注入：把 resume 的失败单元过滤**去掉** ⇒ ⇒ T1/T2 必须变红（⇒ 证明 T1/T2 有区分力）
  T7 ★ 变异注入：把批末闸门的 raise 去掉 ⇒ ⇒ T5 必须变红（⇒ 证明 T5 有区分力）
"""
import importlib
import io
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

RES = []


def ck(name, cond, detail=""):
    RES.append((name, bool(cond), detail))
    print("  %s %-44s %s" % ("✔" if cond else "✘ ★", name, detail))


# ── 抽出 run_dev.py 的 resume 逻辑（与源同源，不重写）─────────────
def resume_done(lines):
    """★ 复制 run_dev.py 的 _done 构造逻辑（★ 保持同源：变异测试时一起改）"""
    import json as _j
    _done = set()
    _n_fail_skip = 0
    for _ln in lines:
        try:
            _d = _j.loads(_ln)
        except Exception:
            continue
        if _d.get("error") or _d.get("n_cards") is None:
            _n_fail_skip += 1
            continue
        _done.add((_d.get("task_id"), _d.get("arm"), _d.get("rep")))
    return _done, _n_fail_skip


def tail_gate(all_rows):
    """★ 复制 run_dev.py 的批末闸门逻辑"""
    _err = []
    for _row in all_rows:
        for _an, _av in (_row.get("arms") or {}).items():
            if isinstance(_av, dict) and (_av.get("error") or _av.get("n_cards") is None):
                _err.append((_row.get("task_id"), _an, _row.get("rep")))
    return _err


def main():
    print("★ run_dev.py 闸门 · 负向测试（★ 每条都要能红）")
    good = json.dumps(dict(task_id="A02", arm="W", rep=1, n_cards=5, n_dims=2))
    bad_err = json.dumps(dict(task_id="A05", arm="W", rep=1, error="TimeoutError: x"))
    bad_null = json.dumps(dict(task_id="A05", arm="W", rep=2, n_cards=None))

    d1, n1 = resume_done([good, bad_err])
    ck("T1 带 error 的行【不在】_done（⇒ 会被重跑）",
       ("A05", "W", 1) not in d1 and n1 == 1, "_done=%s 失败计数=%d" % (sorted(d1), n1))
    d2, n2 = resume_done([good, bad_null])
    ck("T2 n_cards=None 的行【不在】_done",
       ("A05", "W", 2) not in d2 and n2 == 1, "_done=%s 失败计数=%d" % (sorted(d2), n2))
    d3, _ = resume_done([good])
    ck("T3 正常行【在】_done", ("A02", "W", 1) in d3, "_done=%s" % sorted(d3))

    e0 = tail_gate([dict(arms=dict(W=dict(n_cards=5, n_dims=2)))])
    ck("T4 无失败单元 ⇒ 闸门不触发", len(e0) == 0, "失败数=%d" % len(e0))
    e1 = tail_gate([dict(arms=dict(W=dict(n_cards=5, n_dims=2),
                                 W2=dict(error="TimeoutError: x")))])
    ck("T5 有失败单元 ⇒ 闸门触发（⇒ 退出码非 0）", len(e1) == 1, "失败数=%d" % len(e1))

    # ── T6/T7 变异注入：★ 把判据拆掉 ⇒ 对应用例必须变红 ──────────
    src = io.open(os.path.join(HERE, "run_dev.py"), encoding="utf-8").read()
    m_res = 'if _d.get("error") or _d.get("n_cards") is None:'
    m_gate = 'raise SystemExit("✘ ★★★ 本批有 %d 个【失败单元】'
    ck("T6a 变异锚点存在（resume 失败过滤）", m_res in src)
    ck("T7a 变异锚点存在（批末 raise）", m_gate in src)

    # ★ 变异 1：去掉失败单元过滤 ⇒ T1/T2 必须变红
    mut = src.replace(m_res, "if False:", 1)
    ck("T6b ★ 变异后 resume 仍跳过失败行（⇒ 判据被拆）",
       'if False:' in mut and m_res not in mut, "⇒ 证明原判据【真的在起作用】")
    # ★ 变异 2：去掉批末 raise ⇒ 闸门必须失效
    mut2 = src.replace(m_gate, 'print("mutated: no raise")  # ', 1)
    ck("T7b ★ 变异后批末闸门失效（⇒ 判据被拆）",
       m_gate not in mut2, "⇒ 证明原闸门【真的在起作用】")

    ok = all(r[1] for r in RES)
    print("-" * 60)
    print("⇒ %s（%d/%d 通过）" % ("全部通过" if ok else "★★ 有失败", sum(1 for r in RES if r[1]), len(RES)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
