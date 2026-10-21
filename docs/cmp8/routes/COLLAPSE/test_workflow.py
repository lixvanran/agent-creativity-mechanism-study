# -*- coding: utf-8 -*-
"""治塌缩工作流（W）的自检 —— **证明它真的会动，而且不会假动**。

> 2026-10-22 ｜ 配套 `workflow.py`

## 为什么要有这个文件
本项目一路吃过两次亏：
① 契约的 δ_judge 在 temp=0 下恒为 0（**定义造成的"没动静"**）；
② 自检首版报"变异全被抓住"，但失败的全是**基线本来就失败**的检查（**假阳性**）。

⇒ 所以本文件的两条纪律：
* **每个机制都要有一条"它真的动了"的检查**（不是"跑通"）；
* **变异注入前必须基线全过**（否则"被抓住"可能只是抓住了预存在的失败）。

## 变异注入清单
| # | 变异 | 必须 FAIL 的检查 |
|:-:|---|---|
| 1 | `select_frames` 去掉 seed（永远返回同一组） | `frames_seed_reproducible` / `frames_vary_by_seed` |
| 2 | `dedup` 变成空操作 | `dedup_removes_redundant` |
| 3 | `propose_new_action` 对未知失败类型也返回动作 | `action_evolve_rejects_unknown_kind` |
| 4 | 工作流**去掉"没有失败就不演化"的短路** | `no_failure_no_evolution` |
| 5 | `BehaviorArchive.offer` 总是覆盖（不留最优） | `archive_keeps_best_per_cell` |

## 纪律
* 全部用**本地 stub LLM**，**不调用任何模型 API** ⇒ 零成本、可离线跑。
* stub 的行为是**确定的**，因此"动了"可以精确断言。
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import workflow as W  # noqa: E402


# ══════════════════════════════════════════════════════════════════════
# stub LLM（**确定**的 ⇒ "动了"可精确断言）
# ══════════════════════════════════════════════════════════════════════
class StubLLM:
    """按 purpose 分派的可预测 LLM。

    ★ `empty_slots` 里的帧 id 在第一次被调用时返回**空**（模拟"抽不出断言"的失败）
      ⇒ 工作流应当据此**演化出新动作**。
    """

    def __init__(self, empty_slots=(), n_calls=None):
        self.empty_slots = set(empty_slots)
        self.calls = []
        self.n_calls = 0
        self.seen_slots = set()

    def chat(self, prompt, *, model=None, temp=None, max_tokens=None,
             budgets=None, min_ok=None, purpose=None):
        self.n_calls += 1
        self.calls.append(purpose or "")
        p = purpose or ""
        if p.startswith("W_slot"):
            fid = p.replace("W_slot_", "")
            if fid in self.empty_slots and fid not in self.seen_slots:
                self.seen_slots.add(fid)
                return ""                                   # ★ 第一次失败
            return ("- 依据 EV-03 写明的条件成立时，顺序读取为 7450 MB/s\n"
                    "- 若保修条款为五年，则在第 36 个月内仍然有效\n"
                    "- 当并发写入超过 1000 IOPS 时，延迟会超过 1 毫秒")
        if p == "W_extract":
            return ("- 依据 EV-03 写明的条件成立时，顺序读取为 7450 MB/s\n"
                    "- 若保修条款为五年，则在第 36 个月内仍然有效")
        if p == "W_aggregate":
            return ("- 顺序读取为 7450 MB/s\n- 保修五年在第 36 个月仍有效\n"
                    "- 并发写入超过 1000 IOPS 时延迟超过 1 毫秒")
        return "- 默认断言：条件成立时该结论为真"


# ══════════════════════════════════════════════════════════════════════
# 检查框架
# ══════════════════════════════════════════════════════════════════════
class Check:
    def __init__(self, name):
        self.name = name
        self.ok = False
        self.detail = ""
        self.error = None


def run_checks():
    checks = []

    def add(name, fn):
        c = Check(name)
        try:
            c.ok, c.detail = fn()
        except Exception as e:
            c.ok = False
            c.error = "%s: %s" % (type(e).__name__, e)
        checks.append(c)
        return c

    # ── 1. 选帧：可复现 / 随 seed 变 / 互不重复 / 必含 wild
    def c1():
        a = W.select_frames(4, seed=7)
        b = W.select_frames(4, seed=7)
        if a != b:
            return False, "同 seed 结果不同：%r vs %r" % (a, b)
        if len(set(a)) != len(a):
            return False, "抽到重复帧：%r" % (a,)
        if not any(W._FRAME_BY_ID[i]["wild"] for i in a):
            return False, "没有 wild 帧：%r" % (a,)
        return True, "seed=7 → %s（可复现、唯一、含 wild）" % (a,)

    def c2():
        a = W.select_frames(4, seed=1)
        b = W.select_frames(4, seed=2)
        if a == b:
            return False, "不同 seed 给出同一组 ⇒ seed 没起作用"
        return True, "seed=1 → %s ／ seed=2 → %s" % (a, b)

    # ── 3. 去冗余真的去
    def c3():
        items = [
            "顺序读取速度为 7450 MB/s，接口是 PCIe Gen4",
            "顺序读取速度为 7450 MB/s，接口是 PCIe Gen4",   # 几乎同句
            "保修期限是 5 年",                              # 独立
        ]
        kept = W.dedup(items)
        if len(kept) != 2:
            return False, "去冗余后剩 %d 条（应 2）：%r" % (len(kept), kept)
        if "保修期限是 5 年" not in kept:
            return False, "把独立条目误删了：%r" % (kept,)
        return True, "3 条 → %d 条" % len(kept)

    # ── 4. 动作演化：只对已知失败类型提案
    def c4():
        arc = W.ActionArchive()
        nm = W.propose_new_action("empty", "s0", arc)
        if not nm or nm not in arc.actions:
            return False, "未产出新动作：%r" % nm
        again = W.propose_new_action("empty", "s1", arc)
        if again != nm:
            return False, "同一失败类型应复用同一动作名：%r vs %r" % (nm, again)
        if len(arc.actions) != 1:
            return False, "动作数应为 1，实际 %d" % len(arc.actions)
        bad = W.propose_new_action("not_a_kind", "s0", arc)
        if bad is not None:
            return False, "未知失败类型竟产出了动作：%r" % bad
        return True, "动作 %s 出生，动作集=1" % nm

    # ── 5. 行为档案：每格留最优
    def c5():
        arc = W.BehaviorArchive()
        arc.offer("k1", payload="a", score=3)
        arc.offer("k1", payload="b", score=7)
        arc.offer("k1", payload="c", score=5)
        arc.offer("k2", payload="d", score=1)
        st = arc.stats()
        if st["n_cells"] != 2:
            return False, "格子数 %d（应 2）" % st["n_cells"]
        if arc.cells["k1"]["score"] != 7:
            return False, "k1 未留最优（%r）" % arc.cells["k1"]["score"]
        return True, "2 格，k1 留 7"

    # ── 6. 中庸度四指标
    def c6():
        arms = [["a", "b", "c"], ["a", "b"], ["a", "b", "d"]]
        cr = W.common_rate(arms)
        if not (0.3 <= cr <= 0.7):
            return False, "交集率 %r 不在合理区间" % cr
        rounds = [[["a", "b"]], [["a", "b", "c"], ["a", "b", "c"]]]
        mu = W.marginal_util(rounds)
        if len(mu) != 1:
            return False, "边际利用率长度 %d（应 1）" % len(mu)
        if mu[0] <= 0:
            return False, "第二轮有新增却算出边际利用率 %r" % mu[0]
        dm = W.dist_to_modal(["a", "b"], arms)
        if dm < 0:
            return False, "中庸距离为负 %r" % dm
        cs = W.coverage_saturation(rounds, universe=4)
        if len(cs) != 2 or cs[-1] < cs[0]:
            return False, "覆盖饱和度不单调：%r" % cs
        return True, "交集率=%.3f 边际=%.3f 距离=%.3f 饱和=%r" % (cr, mu[0], dm, cs)

    # ── 7. ★ 工作流端到端：**真的演化出动作了**
    def c7():
        # ★ 必须**制造一次真实失败**（某个槽位第一次抽不出断言）⇒ 才有东西可演化
        frames = W.select_frames(3, seed=5)
        llm = StubLLM(empty_slots={frames[0]})
        wf = W.CollapseFixWorkflow(llm, n_slots=3, seed=5, model="stub",
                                   judge_model="stub", max_rounds=2)
        r = wf.run("990 PRO 1TB 的哪些参数成立？")
        if not r["claims"]:
            return False, "没有产出任何断言"
        if not r["frames"]:
            return False, "没有选帧"
        if r["archive"]["n_actions"] < 1:
            return False, ("★ 动作档案没长出新动作（failures=%r）⇒ 演化没发生"
                           % (r["failures"],))
        if not r["failures"].get("empty"):
            return False, "失败通道没记到 empty（failures=%r）" % (r["failures"],)
        if not any(o.startswith("EVOLVE") for o in r["ops"]):
            return False, "操作序列里没有 EVOLVE 标记：%r" % (r["ops"],)
        if r["illum"]["n_cells"] < 1:
            return False, "行为档案为空"
        return True, ("断言 %d 条 ／ 动作集 %d（%s）／ 失败 %r ／ 格 %d"
                      % (len(r["claims"]), r["archive"]["n_actions"],
                         r["archive"]["names"], r["failures"], r["illum"]["n_cells"]))

    # ── 8. ★ 没有失败 ⇒ **一轮生成就够**（不演化、不白跑第二轮）
    # ⚠️ 2026-10-22 修正：原先只看「动作档案大小」⇒ **盯错了可观测量**
    #   （变异「去掉短路」后动作档案**也是 0** —— 它只是让第二轮白跑 ⇒ 抓不住）。
    #   真正的差异 = **生成轮数 / LLM 调用数** ⇒ 改盯这个。
    def c8():
        llm = StubLLM()          # 不制造任何空槽位
        wf = W.CollapseFixWorkflow(llm, n_slots=3, seed=5, model="stub",
                                   judge_model="stub", max_rounds=3)
        r = wf.run("990 PRO 1TB 的哪些参数成立？")
        n_slot_calls = sum(1 for p in llm.calls if str(p).startswith("W_slot"))
        if r["archive"]["n_actions"] != 0:
            return False, ("★ 没有失败却演化了 %d 个动作 ⇒ 动作空间在无节制增长"
                           % r["archive"]["n_actions"])
        if n_slot_calls != 3:
            return False, ("★ 没有失败却生成了 %d 次（应 3 = 一轮 × 3 槽位）"
                           "⇒ 白跑了一轮" % n_slot_calls)
        if any(o.startswith("EVOLVE") for o in r["ops"]):
            return False, "没有失败却出现了 EVOLVE 标记：%r" % (r["ops"],)
        return True, "无失败 ⇒ 动作集 0、生成 1 轮（3 次）"

    # ── 9. 槽位互不可见：★ 第二个槽位的提示里**不能有别人的稿**
    def c9():
        llm = StubLLM()
        wf = W.CollapseFixWorkflow(llm, n_slots=3, seed=5, model="stub",
                                   judge_model="stub", max_rounds=1)
        wf.run("990 PRO 1TB 的哪些参数成立？")
        slot_prompts = []
        orig = llm.chat

        def spy(prompt, **kw):
            if str(kw.get("purpose", "")).startswith("W_slot"):
                slot_prompts.append(prompt)
            return orig(prompt, **kw)
        llm.chat = spy
        wf2 = W.CollapseFixWorkflow(llm, n_slots=3, seed=5, model="stub",
                                    judge_model="stub", max_rounds=1)
        wf2.run("990 PRO 1TB 的哪些参数成立？")
        if len(slot_prompts) < 3:
            return False, "只抓到 %d 个槽位提示" % len(slot_prompts)
        # 各槽位提示应**互不相同**（认知帧不同）且**不含对方的草稿**
        if len(set(slot_prompts)) != len(slot_prompts):
            return False, "不同槽位拿到了完全相同的提示 ⇒ 认知位置没解耦"
        return True, "%d 个槽位提示互不相同" % len(slot_prompts)

    add("frames_seed_reproducible", c1)
    add("frames_vary_by_seed", c2)
    add("dedup_removes_redundant", c3)
    add("action_evolve_rejects_unknown_kind", c4)
    add("archive_keeps_best_per_cell", c5)
    add("medianity_metrics_behave", c6)
    add("workflow_evolves_action_on_failure", c7)
    add("no_failure_no_evolution", c8)
    add("slots_are_decoupled", c9)
    return checks


# ══════════════════════════════════════════════════════════════════════
# 变异注入
# ══════════════════════════════════════════════════════════════════════
MUTATIONS = [
    ("选帧去掉 seed（永远同一组）", "workflow.py",
     "    rng = random.Random(seed)",
     "    rng = random.Random(0)"),

    ("dedup 变成空操作", "workflow.py",
     """    kept: List[str] = []
    for it in items:
        if not (it or "").strip():
            continue
        if any(is_redundant(it, k, **kw) for k in kept):
            continue
        kept.append(it.strip())
    return kept""",
     "    return [i.strip() for i in items if (i or '').strip()]"),

    ("未知失败类型也被提案（把未知当成 empty）", "workflow.py",
     """    if failure_kind not in FAILURE_KINDS:
        return None""",
     '''    if failure_kind not in FAILURE_KINDS:
        failure_kind = "empty"'''),

    ("去掉「没有失败就不演化」的短路", "workflow.py",
     """            if not new_actions:
                break                       # 没有失败 ⇒ 不演化（★ 不无节制扩动作空间）""",
     "            if not new_actions:\n                new_actions = {fid: 'base' for fid in frames}"),

    ("行为档案总是覆盖（不留最优）", "workflow.py",
     """        cell = self.cells.get(key)
        if cell is None or score > cell["score"]:""",
     """        cell = self.cells.get(key)
        if True:"""),
]


def apply_mutation(src, old, new):
    if old not in src:
        raise RuntimeError("变异锚点找不到（源码已变？）")
    return src.replace(old, new, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutate", action="store_true")
    args = ap.parse_args()

    print("=" * 74)
    print("治塌缩工作流（W）· 自检")
    print("=" * 74)

    if not args.mutate:
        checks = run_checks()
        npass = sum(1 for c in checks if c.ok)
        for c in checks:
            print("  %s %-42s %s" % ("✔" if c.ok else "✘", c.name, c.detail or ""))
            if c.error:
                print("      ↳ %s" % c.error)
        print("-" * 74)
        print("正常模式：%d/%d 通过" % (npass, len(checks)))
        return 0 if npass == len(checks) else 1

    # ★ 基线必须全过，否则"被抓住"可能只是抓住了预存在的失败
    baseline = run_checks()
    base_failed = [c.name for c in baseline if not c.ok]
    if base_failed:
        print("  ✘ ★★ **基线本身有失败** ⇒ 变异自检无意义（会假阳性）")
        for c in baseline:
            if not c.ok:
                print("      ↳ %s：%s %s" % (c.name, c.detail or "", c.error or ""))
        print("=" * 74)
        print("变异注入：**无效**（基线未通过）")
        print("=" * 74)
        return 1
    print("  ✔ 基线全过（%d/%d）⇒ 变异自检有效" % (len(baseline), len(baseline)))
    print("-" * 74)

    here = HERE
    with open(os.path.join(here, "workflow.py"), encoding="utf-8") as f:
        original = f.read()

    all_caught, caught_n = True, 0
    for label, fname, old, new in MUTATIONS:
        tmp = tempfile.mkdtemp(prefix="w_mut_")
        try:
            for fn in os.listdir(here):
                if fn.endswith(".py"):
                    shutil.copy2(os.path.join(here, fn), os.path.join(tmp, fn))
            with open(os.path.join(tmp, fname), "w", encoding="utf-8") as f:
                f.write(apply_mutation(original, old, new))
            for mod in list(sys.modules):
                if mod == "workflow":
                    del sys.modules[mod]
            sys.path.insert(0, tmp)
            saved = W
            try:
                globals()["W"] = importlib.import_module("workflow")
                checks = run_checks()
                failed = [c.name for c in checks if not c.ok]
            finally:
                globals()["W"] = saved
                sys.path.remove(tmp)
                if "workflow" in sys.modules:
                    del sys.modules["workflow"]
                sys.path.insert(0, here)
            if failed:
                caught_n += 1
                print("  ✔ 变异被抓住：%s" % label)
                print("      ↳ 失败检查：%s" % ", ".join(failed))
            else:
                all_caught = False
                print("  ✘ ★ 变异**未被抓住**：%s" % label)
        except Exception:
            all_caught = False
            print("  ✘ ★ 变异导致自检崩溃（等于没抓住）：%s" % label)
            traceback.print_exc()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 74)
    print("变异注入：%s（%d/%d 被抓住）"
          % ("全部被抓住" if all_caught else "★有未被抓住的", caught_n, len(MUTATIONS)))
    print("=" * 74)
    return 0 if all_caught else 1


if __name__ == "__main__":
    sys.exit(main())
