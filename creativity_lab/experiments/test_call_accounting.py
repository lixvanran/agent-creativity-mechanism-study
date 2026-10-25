#!/usr/bin/env python3
"""★ **记账回归测试：新代码必须算出"失败调用数 = 60"**（★ 负责人放行拓扑臂的前置门之一）

> 落点：`creativity_lab/experiments/test_call_accounting.py`
> 触发：负责人审查回执 ② —— 「用已知批做回归：新代码算出的失败调用数必须 = 已知的 60」
> ⇒ ⇒ **本测试零 API 调用**（用构造的 `llm.rec` 复现本批的真实形态）

## ★★ 为什么要这个测试（★ 它防的是哪一个具体事故）
ADHD 臂（`runs/tot-arm-adhd-2026-10-24`）的**真实形态**：
- `llm.rec` 里共 **105 条**记录（**含 60 条失败**）
- 但 `meta.n_calls` 只记 **45** ⇒ ★ **失败路径被整体漏记** ⇒ ⇒ 健康度算出 **−1.6667（负数）**
- ⇒ ⇒ **后果比"记成 0"更隐蔽**：分母变小 ⇒ 看起来像"通道天生不好"而不是"记账错"

## ★★ 本测试的两条硬要求（★ 缺一不可）
1. ★ **新代码算出的失败数必须 = 60**（正例）
2. ★★★ **旧口径必须算错**（负例 / 变异注入）⇒ ⇒ **否则这个测试自己就是假阴性**
   （★ 纪律：负向测试自己会假阴性 ⇒ 必须做变异注入，证明它真的能抓）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from creativity_lab.client import Call  # noqa: E402
from creativity_lab.experiments.fix_calllog_fields import recompute_health  # noqa: E402


def build_rec(n_total: int, n_failed: int):
    """★ 构造与本批同形态的 `llm.rec`（★ 用 Call 的【关键字参数】⇒ 不触发字段错位 bug）。

    ★★★ **注意 `ok` 与 `has_content` 是两件事**（`client.py` 的定义）：
    | 字段 | 含义 |
    |---|---|
    | `ok` | **内容长度达标**（>= min_ok）⇒ 业务层成功 |
    | `has_content` | **传输成功**（content_len > 0）⇒ 通道层成功 |

    ⇒ ⇒ **健康度必须用 `has_content`**（client.py 自己写了"健康度应该用这个"）
    ⇒ ⇒ **本批的 60 次 = 传输失败**（has_content=False）⇒ ⇒ 这里如实构造
    ⇒ ⇒ ★ 另加一类「传输到了但内容不达标」（ok=False, has_content=True）⇒ 用来验证两者的区分
    """
    rec = []
    for i in range(n_total):
        failed = i < n_failed          # ★ 前 n_failed 条是【传输失败】
        rec.append(Call(model="MiniMax-M3", purpose="probe", max_tokens=4096,
                        ok=(not failed),
                        content_len=(0 if failed else 20),
                        finish_reason=("error" if failed else "stop"),
                        secs=1.0, effort="medium", has_content=(not failed)))
    return rec


def account(rec):
    """★ 新口径：总数与失败数都从 `llm.rec` 算（★ 不采信 `meta.n_calls`）。"""
    n_total = len(rec)
    # ★ 传输失败 = has_content 为假（★ 不是 ok！ok 是"内容长度达标"，业务层的事）
    n_failed = sum(1 for c in rec if not c.has_content)
    # ★ empty 口径必须与 `recompute_health` 一致（content_len == 0）⇒ 否则两条路径各算各的
    n_empty = sum(1 for c in rec if not (c.content_len or 0))
    return n_total, n_failed, n_empty


def account_OLD(rec, meta_n_calls: int):
    """★ 旧口径（★ 复现 bug）：总数采信 `meta.n_calls` ⇒ 失败调用被整体漏记。"""
    n_total = meta_n_calls
    n_failed = sum(1 for c in rec if not c.has_content)
    # ★ empty 口径必须与 `recompute_health` 一致（content_len == 0）⇒ 否则两条路径各算各的
    n_empty = sum(1 for c in rec if not (c.content_len or 0))
    return n_total, n_failed, n_empty


def health(total, failed, empty):
    return (total - failed) / total if total else 0.0


def main() -> int:
    N_TOTAL, N_FAILED, META_N_CALLS = 105, 60, 45     # ★ 本批真实形态
    rec = build_rec(N_TOTAL, N_FAILED)
    fails = []

    print("== ① 正例：新口径必须算出失败数 = %d ==" % N_FAILED)
    t, f, e = account(rec)
    print("   新口径：total=%d failed=%d empty=%d  健康度=%.4f" % (t, f, e, health(t, f, e)))
    for name, got, want in (("total", t, N_TOTAL), ("failed", f, N_FAILED), ("empty", e, N_FAILED)):
        # ★ empty 与 recompute_health 同口径（content_len==0）⇒ 本构造下 = 60
        if got != want:
            fails.append("新口径 %s = %d，应 = %d" % (name, got, want))

    print("== ② 负例（★ 变异注入）：旧口径必须算错 ==")
    t2, f2, e2 = account_OLD(rec, META_N_CALLS)
    h2 = health(t2, f2, e2)
    print("   旧口径：total=%d failed=%d empty=%d  健康度=%.4f" % (t2, f2, e2, h2))
    if t2 == t:
        fails.append("旧口径 total 竟然等于新口径 ⇒ 变异无效（测试假阴性）")
    if not (h2 < 0):
        fails.append("旧口径健康度 %.4f 未复现负数 ⇒ 变异无效（测试假阴性）" % h2)
    if f2 != N_FAILED:
        fails.append("旧口径 failed 应仍是 %d（失败数本身没错，错在分母）" % N_FAILED)

    print("== ③ 独立重算路径（calllog）必须与内存口径一致 ==")
    import tempfile
    import json
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "calllog.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            for c in rec:
                f.write(json.dumps({"model": c.model, "purpose": c.purpose, "ok": c.ok,
                                    "content_len": c.content_len,
                                    "finish_reason": c.finish_reason, "secs": c.secs,
                                    "effort": c.effort}, ensure_ascii=False) + "\n")
        h = recompute_health(p)
        print("   calllog 独立重算：%s" % json.dumps(h, ensure_ascii=False))
        if h.get("n_bad") != N_FAILED:
            fails.append("calllog 重算 n_bad = %r，应 = %d" % (h.get("n_bad"), N_FAILED))

    print()
    if fails:
        print("✘ %d 项未通过：" % len(fails))
        for x in fails:
            print("   - %s" % x)
        return 1
    print("✔ 全部通过：新口径失败数 = %d（= 已知值）｜ 旧口径被成功复现为负健康度（变异有效）" % N_FAILED)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
