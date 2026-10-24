#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **运行期健康度守卫（★ 2026-10-24 · ★ 修「早停机制在实现上未生效」那个缺口）★★**

★★★ **★ 为什么要单独一个模块（★ 而不是就地改 topo_arm.py）★★**
★ **★ 「不改正在跑的批代码」—— ★ ★ 理由是【可追溯性】而不是"改了会坏"★★**
★ ⇒ ⇒ ★ **★ ⇒ 当前批（★ `runs/topo-arm-v2-2026-10-24`）正在跑 ⇒ ⇒ ★ ⇒ **★ 本模块先落地 + 自证它活着，★ ★ 批结束后再一行接入 ★★**
★ ⇒ ⇒ ★ **★ ⇒ 接入方式（★ 批结束后）：★ 在 `topo_arm.py` 的单元循环里，★ 每 N 次调用后调一次 `guard.maybe_abort(...)` ★★**

★★★★ **★ ★★ 核心语义（★ 与旧实现的差别在"★ 什么时候算 ★"）★★**
| ★ | ★ **旧（★ 有代码但挂在收尾 ⇒ 运行期不生效）** | ★ **本模块** |
|---|---|---|
| ★ **检查时机** | ★ 全部单元跑完后 | ★ ★ **运行期，每 N 次调用** ★★ |
| ★ **触发后** | ★ 无（只是记录 checkpoint） | ★ ★ **抛 `HealthAbort` ⇒ ⇒ 调用方中止批** ★★ |
| ★ **分母** | ★ `llm.rec` 全部 | ★ ★ **迄今所有调用（★ 失败与空内容都进分母）★★** |

★★★ **★ 为什么「空内容」也要进分母（★ 这条是"失败路径不许静默归零"的直接应用）★★**
> ★★★ **★ 一次"成功返回但内容为空"的调用，★ 在通道健康的意义上【等同于失败】★★**
> ⇒ ⇒ ★ **★ ⇒ 若把它排除出分母，★ 健康度就会被【系统性高估】★★**

★★★★ **★ 一个刻意的设计：★ 分母与失败计数【由调用方传进来】，★ 本模块【不自己读任何东西】★★**
> ★★★ **★ 理由：★ 「健康度必须可独立重算」—— ★ ★ 如果本模块自己数，★ ★ 那它就成了【唯一信源】，★ ★ 而独立重算需要一个【与它无关】的第二实现 ★★**
> ⇒ ⇒ ★ **★ ⇒ 所以本模块只做【判定】，★ 【计数由调用方给】（★ 而我们的独立重算直接数 `units/*.json` 的 `calls` 字段，★ ★ 那是第三条路）★★**

★ 用法：
```python
from creativity_lab.experiments.health_guard import HealthGuard, HealthAbort
g = HealthGuard(every=300, min_health=0.80)
...
g.maybe_abort(n_calls=len(llm.rec), n_failed=nf, n_empty=ne)   # ★ 运行期每 N 次调
```

★ **自测**：`python3 -B creativity_lab/experiments/health_guard.py`
"""

from __future__ import annotations

import sys
from typing import NamedTuple


class HealthAbort(RuntimeError):
    """★ **健康度低于阈值 ⇒ ⇒ 抛这个 ⇒ ⇒ 批必须中止（★ 不是警告、★ 不是继续跑）**"""


class Health(NamedTuple):
    n: int
    n_failed: int
    n_empty: int
    channel_health: float


class HealthGuard:
    """★ 运行期健康度守卫（★ 每 `every` 次调用真正检查一次）"""

    def __init__(self, every: int = 300, min_health: float = 0.80):
        if every < 1:
            raise ValueError("every 必须 >= 1")
        if not (0.0 < min_health <= 1.0):
            raise ValueError("min_health 必须落在 (0, 1]")
        self.every = int(every)
        self.min_health = float(min_health)
        self.checkpoints = []          # ★ 落盘用：★ 每次真正检查都记一条

    # ── 纯函数：★ 算健康度（★ 失败与空内容【都进分母】）──
    @staticmethod
    def health(n: int, n_failed: int, n_empty: int) -> Health:
        if n <= 0:
            return Health(0, 0, 0, 1.0)
        bad = int(n_failed) + int(n_empty)
        return Health(int(n), int(n_failed), int(n_empty), round(1.0 - bad / n, 4))

    # ── 运行期检查：★ 到了检查点才真的判（★ 不是每 N 次都判，★ 也不是只在收尾判）──
    def maybe_abort(self, n_calls: int, n_failed: int, n_empty: int) -> Health:
        h = self.health(n_calls, n_failed, n_empty)
        if n_calls <= 0:
            return h
        if (n_calls // self.every) != ((n_calls - 1) // self.every):
            # ★ ★ 到点了 ⇒ ⇒ 真正检查一次 ⇒ ⇒ ★ 【★ 这是旧实现缺的那一步 ★】★
            self.checkpoints.append({
                "n_calls": h.n, "n_failed": h.n_failed, "n_empty": h.n_empty,
                "channel_health": h.channel_health, "min_health": self.min_health,
            })
            if h.channel_health < self.min_health:
                raise HealthAbort(
                    "★ 健康度 %.4f < 阈值 %.4f（★ n=%d ｜ 失败=%d ｜ 空=%d）★ ⇒ 【★ 批中止 ★】"
                    % (h.channel_health, self.min_health, h.n, h.n_failed, h.n_empty))
        return h

    # ── 收尾：★ 记一条（★ 与旧实现同款，★ 但【不】取代运行期检查）──
    def final(self, n_calls: int, n_failed: int, n_empty: int) -> Health:
        h = self.health(n_calls, n_failed, n_empty)
        self.checkpoints.append({
            "n_calls": h.n, "n_failed": h.n_failed, "n_empty": h.n_empty,
            "channel_health": h.channel_health, "min_health": self.min_health,
            "phase": "final",
        })
        return h


_SELFTEST_FAILED = []


def _check(name, cond, detail=""):
    """★ ★ 【★ 关键：★ 断言失败必须有【具体形态】（★ `✘` 前缀）★】★★
    ★ ⇒ ⇒ ★ 理由：★ 裸 `assert` 失败只抛 AssertionError（★ 没有可抓的形态）⇒ ⇒ ★ ⇒
    ★ ⇒ ★ ★ **负向测试的"失败"必须能被【抓出来】，★ 否则会被误判成"崩溃"⇒ ⇒ ★ ⇒ ★ ★
    ★ ⇒ ★ **⇒ 而"崩溃"在负向测试里【不算数】（★ 见 test_health_guard_mutations.py）★★**
    """
    if cond:
        print("  ✔ %s" % name)
    else:
        print("  ✘ %s  %s" % (name, detail))
        _SELFTEST_FAILED.append(name)


def _selftest() -> int:
    print("== ★ health_guard 自测 ==")
    # ① 健康度算对（★ 失败与空内容都进分母）
    h = HealthGuard.health(100, 5, 5)
    _check("① 健康度：★ n=100 失败=5 空=5 ⇒ %.2f（★ 空内容进分母）" % h.channel_health,
           h.channel_health == 0.9, "got %s" % (h,))
    # ② 不到检查点 ⇒ 不判（★ 哪怕健康度已经很低）
    g = HealthGuard(every=300, min_health=0.80)
    g.maybe_abort(299, 100, 100)          # ★ 健康度 0.33，★ 但不到点
    _check("② 未到检查点（★ 299 < 300）⇒ 不检查、★ 不中止",
           not g.checkpoints, str(g.checkpoints))
    # ③ 到检查点且健康 ⇒ 通过并留痕
    g2 = HealthGuard(every=300, min_health=0.80)
    g2.maybe_abort(300, 0, 0)
    _check("③ 到检查点（★ 300）且健康 ⇒ 检查并留痕",
           len(g2.checkpoints) == 1, str(g2.checkpoints))
    # ④ 到检查点且不健康 ⇒ ★ 抛
    g3 = HealthGuard(every=300, min_health=0.80)
    try:
        g3.maybe_abort(300, 100, 100)     # ★ 健康度 0.33
        _check("④ 到检查点且健康度 0.33 < 0.80 ⇒ 中止", False, "★ 没抛 HealthAbort")
    except HealthAbort as e:
        _check("④ 到检查点且健康度 0.33 < 0.80 ⇒ 中止（★ %s）" % str(e)[:52], True)
    # ⑤ 边界：★ 恰好等于阈值 ⇒ 不中止（★ 判据是 <，★ 不是 <=）
    g4 = HealthGuard(every=300, min_health=0.80)
    g4.maybe_abort(300, 20, 0)           # ★ 健康度正好 0.80
    _check("⑤ 健康度恰等于阈值 0.80 ⇒ 不中止（★ 判据是严格小于）",
           len(g4.checkpoints) == 1, str(g4.checkpoints))
    # ⑥ ★ 失败数进分母（★ 变异 m3 的钉子）
    h6 = HealthGuard.health(100, 20, 0)
    _check("⑥ 失败数进分母：★ n=100 失败=20 ⇒ %.2f（★ 应 0.80）" % h6.channel_health,
           abs(h6.channel_health - 0.80) < 1e-9, "got %s" % (h6,))
    # ⑦ ★ 空内容进分母（★ 变异 m2 的钉子）
    h7 = HealthGuard.health(100, 0, 20)
    _check("⑦ 空内容进分母：★ n=100 空=20 ⇒ %.2f（★ 应 0.80）" % h7.channel_health,
           abs(h7.channel_health - 0.80) < 1e-9, "got %s" % (h7,))
    if _SELFTEST_FAILED:
        print("✘ health_guard 自测失败 %d 项：%s" % (len(_SELFTEST_FAILED), _SELFTEST_FAILED))
        return 1
    print("✔ health_guard 自测全过")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
