# -*- coding: utf-8 -*-
"""优化器契约的**自检 + 变异注入**测试。

## 为什么要有变异注入

「测试通过」本身不能证明测试有用：一个把所有改动都接受的优化器，
在「只测它会不会跑」的自检里也会全绿。
⇒ 本文件对**被测源码**做**源码级变异**，再跑**同一套**自检，
要求自检**必须报出 FAIL**。**报不出 FAIL ⇒ 这套自检是摆设。**

| 变异 | 改坏什么 | 自检必须 FAIL 在哪 |
|---|---|---|
| ① | 接受规则改成「接受一切」 | `accept_rule_gain_below_delta` / `accept_rule_counter_regression` |
| ② | 去掉 TEST 守卫 | `guard_dev_only` / `optimizer_rejects_test_dataset` |
| ③ | 去掉「一次只改一个自由度」守卫 | `guard_single_freedom` / `optimizer_rejects_two_freedom` |
| ④（附加） | 去掉 `measure_version` 守卫 | `guard_measure_version` / `optimizer_rejects_measure_version` |

## 假客户端说明（⚠️ 必读）

本文件里的 `FakeRunner`（合成读数）与 `ScriptedRunner`（钉死的读数）都是
**本地合成件**，用 DEV 的**金标卡**当「正确答案」参照，**不调用任何模型 API**
（不调 OpenRouter、不调 MiniMax）。
⇒ 本文件产出的所有数字都是**合成读数**，只证明「契约的机械逻辑跑得通」，
**不是实验结论**，也不能用来比较任何路线/臂/配置。

## 用法

```
python3 test_optimizer.py            # 正常自检 + 3(4) 个变异注入
python3 test_optimizer.py --json     # 机器可读输出
```
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import config as CFG                                    # noqa: E402
from config import (config_hash, diff_configs,  # noqa: E402
                    make_config, set_freedom)

DEV = "/workspace/lab/routes/DEV"
DEVSET_PATH = os.path.join(DEV, "devset.json")
MANIFEST_PATH = os.path.join(DEV, "MANIFEST.json")
GOLD_DIR = os.path.join(DEV, "gold")
OUT_DIR = os.path.join(HERE, "optimizer_out")
SELFCHECK_JSON = os.path.join(OUT_DIR, "selfcheck_readings.json")


# ==========================================================================
# 假客户端 ①：合成响应（用 DEV 金标卡当「正确答案」）
# ==========================================================================
class FakeRunner:
    """合成执行体：**不调任何 API**。

    响应模型（**合成**，不是对任何真实系统的拟合）：

    * 该臂在某题上能造出多少个「族」= 拓扑基数 − 门控惩罚 ± 帧数/份数修正
      （再被 `m_clusters` / `n_verify_max` 截断）；
    * **生成侧噪声**：按 (题, 种子, config) 有一定概率丢掉最后一个族 ⇒ δ_gen；
    * **判官侧噪声**：按 (题, 种子) 有一定概率把「支持」翻成「矛盾」/「未提及」
      ⇒ δ_judge；
    * **假阳性**：偶尔塞一条金标里的干扰项（支撑集为空 ⇒ 不产生维度，但抬高卡片数）。

    ⚠️ 目的是**把契约的机械逻辑跑通**，不是模拟任何真实臂的行为。
    """

    TOPO_BASE = {"T0": 1, "T1": 2, "T2": 2, "T3": 2, "T4": 2, "T5": 2}

    def __init__(self, tasks, *, judge_noise=0.10, gen_noise=0.15, false_pos=0.10):
        self.tasks = {t["task_id"]: t for t in tasks}
        self.gold = {}
        for tid in self.tasks:
            with open(os.path.join(GOLD_DIR, "%s_cards.json" % tid), encoding="utf-8") as f:
                self.gold[tid] = json.load(f)
        self.judge_noise = judge_noise
        self.gen_noise = gen_noise
        self.false_pos = false_pos
        self.n_generate = 0
        self.n_measure = 0

    # ── 内部
    def _families(self, tid):
        g = self.gold[tid]
        fams = []
        for c in g["cards"]:
            k = "|".join(sorted(c.get("supports_conclusions") or []))
            if k and k not in fams:
                fams.append(k)
        return fams

    def _n_families(self, task, cfg):
        p = cfg.get("params") or {}
        topo = cfg.get("topology") or "T2"
        n = self.TOPO_BASE.get(topo, 2)
        n -= int(round((float(p.get("theta_util", 0.5)) - 0.5) * 8))
        n += int(p.get("n_frames", 3)) - 3
        n -= 2 * (int(p.get("n_cand_per_frame", 1)) - 1)
        n_avail = len(self._families(task["task_id"]))
        return max(0, min(n, n_avail))

    # ── 执行体接口
    def generate(self, task, cfg, seed=0):
        tid = task["task_id"]
        self.n_generate += 1
        rng = random.Random("gen|%s|%s|%s" % (tid, seed, config_hash(cfg)))
        fams = self._families(tid)
        n = self._n_families(task, cfg)
        if n > 0 and rng.random() < self.gen_noise:
            n -= 1                                   # ← 生成侧噪声（δ_gen）
        p = cfg.get("params") or {}
        n_final = max(1, min(n, int(p.get("m_clusters", 4)))) if n else 0
        n_verify = int(p.get("n_verify_max", 6))
        gold = self.gold[tid]
        cards = []
        for i, fam in enumerate(fams[:n]):
            members = [c for c in gold["cards"]
                       if "|".join(sorted(c.get("supports_conclusions") or [])) == fam]
            for c in members[:2]:
                cards.append({
                    "card_id": c["card_id"],
                    "supports_conclusions": list(c.get("supports_conclusions") or []),
                    "load_bearing": bool(c.get("is_load_bearing")),
                    "verify_status": None,          # ← 由 measure 侧判定
                    "stage": "final" if i < n_final else "internal",
                    "tokens": 30,
                })
        # 超出核验预算的卡片 ⇒ 「承重但未核验」（协议 §2.3 的 vd_unverified 路径）
        for c in cards[n_verify:]:
            c["verify_status"] = "unverifiable"
        return {"cards": cards,
                "cost": {"n_calls": 3, "n_tokens": 1200, "cost_usd": 0.0042}}

    def measure(self, task, answer, seed=0):
        self.n_measure += 1
        tid = task["task_id"]
        rng = random.Random("judge|%s|%s" % (tid, seed))
        cards = []
        for c in answer.get("cards") or []:
            c2 = dict(c)
            if c2.get("verify_status") is None:
                r = rng.random()
                if r < self.judge_noise:
                    c2["verify_status"] = "contradicted"      # ← 判官侧噪声
                elif r < self.judge_noise * 1.6:
                    c2["verify_status"] = "unmentioned"
                else:
                    c2["verify_status"] = "supported"
            cards.append(c2)
        if rng.random() < self.false_pos:
            d = self.gold[tid].get("distractors") or []
            if d:
                dist = d[rng.randrange(len(d))]
                cards.append({"card_id": dist.get("card_id"),
                              "supports_conclusions": [],
                              "load_bearing": False,
                              "verify_status": "supported",
                              "stage": "final", "tokens": 20})
        return {"cards": cards,
                "cost": {"n_calls": 1, "n_tokens": 400, "cost_usd": 0.0},  # 测量免费
                "measure_version": None}


# ==========================================================================
# 假客户端 ②：钉死的读数（把接受规则的判定钉死）
# ==========================================================================
class ScriptedRunner:
    """按 config 哈希返回**预先写死**的读数 ⇒ 判定完全确定、无噪声。

    spec 形如 `{"<config_hash>": {"<task_id>": {"n_fam": 2, "n_con": 0, "key_hit": True}}}`
    """

    def __init__(self, tasks, spec):
        self.tasks = {t["task_id"]: t for t in tasks}
        self.spec = spec
        self.n_generate = 0
        self.n_measure = 0

    def _cards_for(self, task, s):
        tid = task["task_id"]
        all_concl = [c["id"] for c in (task.get("conclusion_space") or [])]
        keys = list(task.get("key_conclusions") or [])
        # 族键只用**非关键结论**（不足则用合成 id 补齐）⇒ 关键结论只能被「命中卡」命中
        # ⇒ `key_hit=False` 时必定掉命中数（R2 退化可被稳定复现）
        nonkey = [c for c in all_concl if c not in keys]
        pad = ["SYN%d" % (i + 1) for i in range(8)]
        ordered = nonkey + pad
        cards = []
        for i in range(int(s.get("n_fam", 0))):
            cid = ordered[i % len(ordered)]
            cards.append({"card_id": "S%02d" % i, "supports_conclusions": [cid],
                          "load_bearing": True, "verify_status": "supported",
                          "stage": "final", "tokens": 20})
        for i in range(int(s.get("n_con", 0))):
            cid = ordered[-(i + 1) % len(ordered)]
            cards.append({"card_id": "X%02d" % i, "supports_conclusions": [cid],
                          "load_bearing": True, "verify_status": "contradicted",
                          "stage": "final", "tokens": 20})
        if s.get("key_hit") and keys:
            # 关键结论命中卡：**internal** ⇒ 不进最终族集合（只影响 R2 命中数）
            cards.append({"card_id": "K00", "supports_conclusions": [keys[0]],
                          "load_bearing": True, "verify_status": "supported",
                          "stage": "internal", "tokens": 20})
        return cards

    def generate(self, task, cfg, seed=0):
        self.n_generate += 1
        h = config_hash(cfg)
        s = (self.spec.get(h) or {}).get(task["task_id"]) or {}
        return {"cards": self._cards_for(task, s),
                "cost": {"n_calls": 2, "n_tokens": 800, "cost_usd": 0.003}}

    def measure(self, task, answer, seed=0):
        self.n_measure += 1
        return {"cards": list(answer.get("cards") or []),
                "cost": {"n_calls": 1, "n_tokens": 300, "cost_usd": 0.0},
                "measure_version": None}


# ==========================================================================
# 变异注入（源码级）
# ==========================================================================
def mutate_function(src: str, fname: str, new_body: str) -> str:
    """把源码里 `def fname(...)` 的**整个函数体**换成 `new_body`。"""
    lines = src.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("def %s(" % fname):
            start = i
            break
    if start is None:
        raise RuntimeError("源码里找不到函数 %s" % fname)
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith(("def ", "class ", "@")):
            end = j
            break
    new = new_body.rstrip("\n").split("\n")
    return "\n".join(lines[:start] + new + [""] + lines[end:])


def load_mutant(src: str, name: str):
    tmpdir = tempfile.mkdtemp(prefix="optmut_")
    path = os.path.join(tmpdir, "%s.py" % name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod, tmpdir


# ==========================================================================
# 自检套件（对 `mod` 跑 ⇒ 真实模块与变异模块共用同一套检查）
# ==========================================================================
class Check:
    def __init__(self):
        self.items = []

    def add(self, name, ok, detail=""):
        self.items.append({"name": name, "ok": bool(ok), "detail": str(detail)})
        return ok

    def expect_raise(self, name, exc, fn, detail=""):
        try:
            fn()
        except exc as e:
            return self.add(name, True, "如期抛出 %s：%s" % (exc.__name__, e))
        except Exception as e:                        # noqa: BLE001
            return self.add(name, False, "抛的是 %s 而不是 %s：%s"
                            % (type(e).__name__, exc.__name__, e))
        return self.add(name, False, "**没有抛异常**（期望 %s）%s" % (exc.__name__, detail))

    @property
    def failed(self):
        return [i for i in self.items if not i["ok"]]

    @property
    def ok(self):
        return not self.failed


def _devset_hash(tasks):
    blob = json.dumps(tasks, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()[:16]


def selfcheck(mod, tasks, tmpdir) -> Check:
    """跑全套自检（`mod` = 被测的 optimizer 模块：真实的或变异的）。"""
    ck = Check()
    credit = sys.modules.get("credit")
    noise = sys.modules.get("noise_floor")

    # ------------------------------------------------------------------ config
    base = make_config("C")
    ck.add("config_hash_stable",
           config_hash(base) == config_hash(make_config("C")),
           "同 config 两次哈希相同：%s" % config_hash(base))
    c2 = set_freedom(base, "params.n_frames", 4)
    ck.add("config_hash_changes_on_param",
           config_hash(c2) != config_hash(base),
           "改一个参数 ⇒ 哈希变：%s vs %s" % (config_hash(c2), config_hash(base)))
    ck.add("diff_single_freedom",
           diff_configs(base, c2) == "params.n_frames",
           "单自由度改动 ⇒ 报出 'params.n_frames'")
    c3 = set_freedom(c2, "params.n_cand_per_frame", 2)
    ck.expect_raise("diff_multi_freedom_raises", CFG.MultiFreedomChangeError,
                    lambda: diff_configs(base, c3))
    ck.expect_raise("diff_no_change_raises", CFG.NoFreedomChanged,
                    lambda: diff_configs(base, make_config("C")))
    # L0-1：四项绑定任一变动 ⇒ measure_version 变
    mv_ok = True
    mv_detail = []
    for f in CFG.MEASURE_BINDING_FIELDS:
        m = dict(base["measure"])
        m[f] = str(m[f]) + "-changed"
        c = make_config("C", measure=m)
        same = c["measure_version"] == base["measure_version"]
        reported = None
        try:
            reported = diff_configs(base, c)
        except CFG.MultiFreedomChangeError:
            reported = "MULTI"
        mv_ok = mv_ok and (not same) and reported == "measure_version"
        mv_detail.append("%s→version变=%s diff报=%s" % (f, not same, reported))
    ck.add("measure_version_binding", mv_ok, "；".join(mv_detail))

    # A 的预注册常量镜像不漂移（spec ↔ code 对账）
    a_keys = set(CFG.A_PARAMS)
    src_a = open("/workspace/lab/routes/A/route_a.py", encoding="utf-8").read()
    blk = src_a[src_a.index("DEFAULTS = dict("):]
    blk = blk[:blk.index("\n)\n")]
    a_src_keys = set()
    for ln in blk.split("\n")[1:]:                 # 第 0 行是 "DEFAULTS = dict("
        ln = ln.split("#")[0].strip()
        if "=" in ln and ln:
            a_src_keys.add(ln.split("=")[0].strip())
    ck.add("a_params_mirror_in_sync", a_keys == a_src_keys,
           "config.A_PARAMS %d 项 vs route_a.py DEFAULTS %d 项；差集=%s"
           % (len(a_keys), len(a_src_keys), sorted(a_keys ^ a_src_keys)))

    # ------------------------------------------------------------------ 守卫
    dev_task = dict(tasks[0])
    test_task = {"task_id": "U1", "ask": "", "conclusion_space": [], "key_conclusions": []}
    ck.expect_raise("guard_dev_only", mod.TestSetLeakError,
                    lambda: mod._check_dev_only([dev_task, test_task]))
    ck.add("guard_dev_only_accepts_dev", mod._check_dev_only([dev_task]) is True,
           "DEV 题通过 ⑤ 守卫")
    ck.expect_raise("guard_single_freedom", CFG.MultiFreedomChangeError,
                    lambda: mod._check_single_freedom(base, c3))
    m2 = dict(base["measure"])
    m2["judge_prompt_version"] = "judge-v9"
    c_mv = make_config("C", measure=m2)
    ck.expect_raise("guard_measure_version", mod.MeasureVersionChangeError,
                    lambda: mod._check_measure_version(base, c_mv))

    # ------------------------------------------------------------------ 接受规则（钉死读数）
    gain_cfg = set_freedom(base, "params.theta_util", 0.25)
    flat_cfg = set_freedom(base, "params.n_cand_per_frame", 2)
    r2_cfg = set_freedom(base, "params.n_cand_per_frame", 3)
    spec = {}
    for cfg, s in ((base, {"n_fam": 2, "n_con": 0, "key_hit": True}),
                   (gain_cfg, {"n_fam": 4, "n_con": 0, "key_hit": True}),
                   (flat_cfg, {"n_fam": 2, "n_con": 0, "key_hit": True}),
                   (r2_cfg, {"n_fam": 4, "n_con": 0, "key_hit": False})):
        spec[config_hash(cfg)] = {t["task_id"]: dict(s) for t in tasks}
    runner = ScriptedRunner(tasks, spec)
    opt = mod.Optimizer(devset=tasks, ref_cfg=base, runner=runner, delta=0.5,
                         budget=5, r_meas=3, seed=7,
                         log_path=os.path.join(tmpdir, "accept.jsonl"))

    res = opt.run(base, [{"freedom": "params.theta_util", "value": 0.25,
                          "reason": "合成读数：+2 个族"}])
    ck.add("accept_rule_gain_above_delta",
           len(res["records"]) == 1 and res["records"][0]["decision"] == "accept",
           "增益 %.3g > δ ⇒ 接受（实测 %.3g）"
           % (res["records"][0]["gain"] if res["records"] else float("nan"),
              res["records"][0]["gain"] if res["records"] else float("nan")))

    opt2 = mod.Optimizer(devset=tasks, ref_cfg=base, runner=runner, delta=0.5,
                          budget=5, r_meas=3, seed=7,
                          log_path=os.path.join(tmpdir, "flat.jsonl"))
    res2 = opt2.run(base, [{"freedom": "params.n_cand_per_frame", "value": 2,
                            "reason": "合成读数：读数不变"}])
    ck.add("accept_rule_gain_below_delta",
           len(res2["records"]) == 1 and res2["records"][0]["decision"] == "rollback",
           "增益 %.3g ≤ δ ⇒ 回退" % (res2["records"][0]["gain"] if res2["records"] else float("nan")))

    opt3 = mod.Optimizer(devset=tasks, ref_cfg=base, runner=runner, delta=0.5,
                          budget=5, r_meas=3, seed=7,
                          log_path=os.path.join(tmpdir, "r2.jsonl"))
    res3 = opt3.run(base, [{"freedom": "params.n_cand_per_frame", "value": 3,
                            "reason": "合成读数：关键结论命中掉了"}])
    ok3 = (len(res3["records"]) == 1 and res3["records"][0]["decision"] == "rollback"
           and res3["records"][0]["counter_criteria"]["R2"]["ok"] is False)
    ck.add("accept_rule_counter_regression", ok3,
           "增益 %.3g > δ 但 R2 退化 ⇒ 回退" % (res3["records"][0]["gain"] if res3["records"] else float("nan")))

    # ------------------------------------------------------------------ 预算 K（④）
    K = 3
    cur = base
    chain = []
    spec2 = {config_hash(base): {t["task_id"]: {"n_fam": 2, "n_con": 0, "key_hit": True}
                                 for t in tasks}}
    for i in range(K + 1):            # 多给一个提案 ⇒ 预算用尽时会被 ④ 拦下
        cand = set_freedom(cur, "params.theta_util", round(0.25 - i * 0.01, 4))
        spec2[config_hash(cand)] = {t["task_id"]: {"n_fam": 4, "n_con": 0, "key_hit": True}
                                    for t in tasks}
        chain.append({"freedom": "params.theta_util", "value": round(0.25 - i * 0.01, 4),
                      "reason": "预算测试 #%d" % (i + 1)})
        cur = cand
    r2 = ScriptedRunner(tasks, spec2)
    opt4 = mod.Optimizer(devset=tasks, ref_cfg=base, runner=r2, delta=0.5,
                          budget=K, r_meas=3, seed=7,
                          log_path=os.path.join(tmpdir, "budget.jsonl"))
    res4 = opt4.run(base, chain)
    ck.add("optimizer_budget_K",
           res4["n_changes"] == K and res4["halt_reason"] == "budget_exhausted",
           "K=%d ⇒ 实际改动 %d 次，停止原因 %s" % (K, res4["n_changes"], res4["halt_reason"]))

    # ------------------------------------------------------------------ 收敛判据（⑧）
    spec3 = {config_hash(base): {t["task_id"]: {"n_fam": 2, "n_con": 0, "key_hit": True}
                                 for t in tasks}}
    flat_chain = []
    cur = base
    for i in range(4):
        cand = set_freedom(cur, "params.theta_util", round(0.5 - i * 0.05, 4))
        spec3[config_hash(cand)] = {t["task_id"]: {"n_fam": 2, "n_con": 0, "key_hit": True}
                                    for t in tasks}
        flat_chain.append({"freedom": "params.theta_util", "value": round(0.5 - i * 0.05, 4),
                           "reason": "连续无增益 #%d" % (i + 1)})
        cur = cand
    r3 = ScriptedRunner(tasks, spec3)
    opt5 = mod.Optimizer(devset=tasks, ref_cfg=base, runner=r3, delta=0.5,
                          budget=9, r_meas=3, seed=7,
                          log_path=os.path.join(tmpdir, "conv.jsonl"))
    res5 = opt5.run(base, flat_chain)
    ck.add("optimizer_convergence_3",
           res5["halt_reason"] == "converged_no_gain_3" and res5["n_changes"] == 3,
           "连续 3 次收益 ≤ δ ⇒ 停；实际改动 %d 次，停止原因 %s"
           % (res5["n_changes"], res5["halt_reason"]))

    # ------------------------------------------------------------------ 噪声地板（δ）
    nf = None
    if noise is not None:
        nf = noise.estimate_noise_floor(tasks, FakeRunner(tasks), route="C",
                                         base_cfg=make_config("C"), ref_cfg=make_config("C"),
                                         r_meas=5, n_seeds=3, seed=20261021)
        ok_nf = all(k in nf for k in ("delta_judge", "delta_gen", "delta_total",
                                      "threshold_delta", "optimization_allowed", "verdict"))
        ok_ns = all(nf[k].get("n_samples", 0) >= 2 for k in ("delta_judge", "delta_gen", "delta_total"))
        ck.add("noise_floor_estimates", ok_nf and ok_ns,
               "δ_judge=%.4g(n=%d) δ_gen=%.4g(n=%d) δ_total=%.4g(n=%d) 阈值=%.4g 允许优化=%s"
               % (nf["delta_judge"]["value"], nf["delta_judge"]["n_samples"],
                  nf["delta_gen"]["value"], nf["delta_gen"]["n_samples"],
                  nf["delta_total"]["value"], nf["delta_total"]["n_samples"],
                  nf["threshold_delta"], nf["optimization_allowed"]))
        ck.add("noise_floor_has_r1_floor", "conflict_rate" in nf.get("floors", {}),
               "R1 种子噪声地板 = %.4g（n=%d）"
               % (nf["floors"]["conflict_rate"],
                  nf["floors"]["conflict_rate_detail"]["n_samples"]))
    floors = (nf or {}).get("floors") or {}

    # ------------------------------------------------------------------ 端到端（合成 runner）
    log_e2e = os.path.join(tmpdir, "e2e.jsonl")
    fake = FakeRunner(tasks)
    base2 = make_config("C")
    floor_cfg = set_freedom(base2, "params.theta_util", 0.75)   # 合成模型下造不出维度
    opt6 = mod.Optimizer(devset=tasks, ref_cfg=base2, runner=fake, delta=0.2,
                          budget=6, r_meas=5, seed=11, floors=floors,
                          log_path=log_e2e)
    props = [
        {"freedom": "params.theta_util", "value": 0.25, "reason": "合成：放宽门控"},
        {"freedom": "params.theta_util", "value": 0.75, "reason": "合成：收紧门控"},
        {"freedom": "params.n_frames", "value": 1, "reason": "合成：退成单路"},
        {"freedom": "params.n_frames", "value": 5, "reason": "合成：加帧"},
    ]
    res6 = opt6.run(base2, props)
    decisions = [r["decision"] for r in res6["records"]]
    ck.add("optimizer_end_to_end",
           res6["n_changes"] == 4 and decisions[0] == "accept"
           and res6["halt_reason"] == "converged_no_gain_3",
           "改动 %d 次，决策序列 %s，停止原因 %s"
           % (res6["n_changes"], decisions, res6["halt_reason"]))

    # 落盘（⑦）：每条记录字段齐全 + JSONL 追加
    recs = [json.loads(l) for l in open(log_e2e, encoding="utf-8") if l.strip()]
    need = ("theta", "theta_prime", "vd_net_theta", "vd_net_theta_prime", "gain",
            "delta", "counter_criteria", "decision", "reason", "measure_version")
    miss = [k for k in need if any(k not in r for r in recs if r.get("kind") == "change")]
    ck.add("optimizer_log_fields", (not miss) and len(recs) == 4,
           "落盘 %d 条（改动 4 条），缺字段：%s" % (len(recs), miss or "无"))
    # 追加式：再跑一次，文件应变长
    n_before = len(recs)
    opt6b = mod.Optimizer(devset=tasks, ref_cfg=base2, runner=fake, delta=0.2,
                           budget=2, r_meas=5, seed=11, log_path=log_e2e)
    opt6b.run(base2, props[:1])
    recs2 = [json.loads(l) for l in open(log_e2e, encoding="utf-8") if l.strip()]
    ck.add("optimizer_log_append_only", len(recs2) == n_before + 1,
           "同一日志文件：%d 条 → %d 条（追加而非覆盖）" % (n_before, len(recs2)))

    # 双自由度候选：必须被守卫拦下（且不得进入「改动」）
    log_2dof = os.path.join(tmpdir, "two.jsonl")
    opt7 = mod.Optimizer(devset=tasks, ref_cfg=base2, runner=fake, delta=0.2,
                          budget=3, r_meas=3, seed=11, floors=floors, log_path=log_2dof)
    two = set_freedom(set_freedom(base2, "params.n_frames", 4), "params.theta_util", 0.3)
    res7 = opt7.run(base2, [{"config": two, "reason": "同时改两个自由度（应被 ① 拦下）"}])
    allrec = [json.loads(l) for l in open(log_2dof, encoding="utf-8") if l.strip()]
    guards = [r.get("guard") for r in allrec if r.get("kind") == "guard_reject"]
    multi_change = []
    for r in allrec:
        if r.get("kind") == "change":
            try:
                diff_configs(r["theta"], r["theta_prime"])
            except CFG.MultiFreedomChangeError:
                multi_change.append(r)
            except CFG.NoFreedomChanged:
                pass
    raised = False
    try:
        mod._check_single_freedom(base2, two)
    except CFG.MultiFreedomChangeError:
        raised = True
    ck.add("optimizer_rejects_two_freedom",
           raised and "single_freedom" in guards and not multi_change,
           "双自由度候选：守卫抛出=%s，落盘守卫标签=%s，进入「改动」的多自由度记录=%d 条"
           % (raised, guards, len(multi_change)))

    # measure_version 候选：必须被拦下
    log_mv = os.path.join(tmpdir, "mv.jsonl")
    opt8 = mod.Optimizer(devset=tasks, ref_cfg=base2, runner=fake, delta=0.2,
                          budget=3, r_meas=3, seed=11, log_path=log_mv)
    mv_cfg = make_config("C", measure=dict(base2["measure"],
                                            judge_prompt_version="judge-v-hacked"))
    opt8.run(base2, [{"freedom": "prompt_version", "value": "ROUTE-C-prompt-v1.1",
                      "reason": "改提示版本（允许）"}])
    try:
        mod._check_measure_version(base2, mv_cfg)
        raised = False
    except mod.MeasureVersionChangeError:
        raised = True
    ck.add("optimizer_rejects_measure_version", raised,
           "改 measure_version 的候选被守卫拦下=%s" % raised)

    # TEST 集守卫（端到端）
    ck.expect_raise("optimizer_rejects_test_dataset", mod.TestSetLeakError,
                    lambda: mod.Optimizer(devset=tasks + [test_task], ref_cfg=base2,
                                          runner=fake, delta=0.2, budget=1, r_meas=1))

    # 地板检测（L0-5）：造不出维度的臂 ⇒ 不许优化
    opt9 = mod.Optimizer(devset=tasks, ref_cfg=floor_cfg, runner=fake, delta=0.2,
                          budget=2, r_meas=3, seed=11,
                          log_path=os.path.join(tmpdir, "floor.jsonl"))
    raised_floor = False
    try:
        opt9.run(floor_cfg, [])
    except mod.FloorEffectError as e:
        raised_floor = True
        floor_msg = str(e)
    ck.add("optimizer_floor_effect_blocks", raised_floor,
           "地板臂触发 FloorEffectError=%s %s" % (raised_floor, floor_msg if raised_floor else ""))

    # ------------------------------------------------------------------ 噪声地板（δ）已在上方算完

    # ------------------------------------------------------------------ 信用分配（L1）
    if credit is not None:
        comps = ["params:n_frames", "params:stop_patience", "params:m_clusters"]
        tbl = credit.credit_table(base2, comps, devset=tasks, runner=FakeRunner(tasks),
                                   ref_cfg=base2, r_meas=3, delta=0.2, seed=5)
        ok_credit = all(k in tbl for k in ("components", "contributing", "redundant",
                                           "reverse", "billing"))
        ck.add("credit_table_shape", ok_credit,
               "contributing=%s redundant=%s reverse=%s"
               % (tbl["contributing"], tbl["redundant"], tbl["reverse"]))
        ck.add("credit_billing_split",
               "cost_gen" in tbl["billing"] and "cost_meas" in tbl["billing"]
               and tbl["billing"]["n_measurements"] > 0,
               "生成账 %s ／ 测量账 %s ／ 测量次数 %d"
               % (tbl["billing"]["cost_gen"], tbl["billing"]["cost_meas"],
                  tbl["billing"]["n_measurements"]))
        del tbl

        # 「反向组件」（Δ<0 ⇒ 拿掉它反而涨）必须能被判出来 ⇒ 用钉死读数构造
        abl_cfg = set_freedom(base2, "params.m_clusters", 1)
        spec_rev = {
            config_hash(base2): {t["task_id"]: {"n_fam": 2, "n_con": 0, "key_hit": True}
                                 for t in tasks},
            config_hash(abl_cfg): {t["task_id"]: {"n_fam": 4, "n_con": 0, "key_hit": True}
                                   for t in tasks},
        }
        row = credit.delta_component(base2, "params:m_clusters", devset=tasks,
                                     runner=ScriptedRunner(tasks, spec_rev),
                                     ref_cfg=base2, r_meas=3, delta=0.2, seed=5)
        ck.add("credit_reverse_component", row.get("verdict") == "reverse",
               "钉死读数下 Δ=%s（完整 %s → 消融 %s）⇒ 判词 %s"
               % (row.get("delta_vd_net"), row.get("vd_net_full"),
                  row.get("vd_net_ablated"), row.get("verdict")))

    return ck


# ==========================================================================
# 主流程
# ==========================================================================
MUTATIONS = [
    ("① 接受规则改成「接受一切」", "_accept_decision",
     "def _accept_decision(gain, delta, counter_ok, warnings):\n"
     "    return True\n",
     ["accept_rule_gain_below_delta", "accept_rule_counter_regression"]),
    ("② 去掉 TEST 守卫", "_check_dev_only",
     "def _check_dev_only(dataset):\n"
     "    return True\n",
     ["guard_dev_only", "optimizer_rejects_test_dataset"]),
    ("③ 去掉「一次只改一个自由度」守卫", "_check_single_freedom",
     "def _check_single_freedom(a, b):\n"
     "    return None\n",
     ["guard_single_freedom", "optimizer_rejects_two_freedom"]),
    ("④（附加）去掉 measure_version 守卫", "_check_measure_version",
     "def _check_measure_version(a, b):\n"
     "    return 'measure_version'\n",
     ["guard_measure_version", "optimizer_rejects_measure_version"]),
]


def demo(tasks):
    """跑一次**完整**契约（L0 → L3 → L1），落盘三份产物。

    ⚠️ 用的是**合成执行体**（`FakeRunner`）⇒ 产物里的数字是**合成读数**，
    只证明「契约的三个件能串起来跑」，**不是实验结论**。
    """
    import optimizer as OPT
    import noise_floor as NF
    import credit as CR

    os.makedirs(OUT_DIR, exist_ok=True)
    base = make_config("C")
    ref = make_config("C")

    # ── L0：噪声地板 δ
    nf = NF.estimate_noise_floor(tasks, FakeRunner(tasks), route="C",
                                 base_cfg=base, ref_cfg=ref,
                                 r_meas=5, n_seeds=3, seed=20261021)
    NF.save_noise_floor(nf, os.path.join(OUT_DIR, "noise_floor.json"))
    print("【L0 噪声地板】δ_judge=%.4g(n=%d) δ_gen=%.4g(n=%d) δ_total=%.4g(n=%d)"
          % (nf["delta_judge"]["value"], nf["delta_judge"]["n_samples"],
             nf["delta_gen"]["value"], nf["delta_gen"]["n_samples"],
             nf["delta_total"]["value"], nf["delta_total"]["n_samples"]))
    print("            阈值 δ*=%.4g ｜ 典型增益尺度=%.4g ｜ 允许优化=%s"
          % (nf["threshold_delta"], nf["typical_gain_scale"], nf["optimization_allowed"]))
    print("            判决：%s" % nf["verdict"])

    # ── L3：优化轨迹
    traj = os.path.join(OUT_DIR, "trajectory.jsonl")
    if os.path.exists(traj):
        os.remove(traj)
    opt = OPT.Optimizer(devset=tasks, ref_cfg=ref, runner=FakeRunner(tasks),
                        delta=nf["threshold_delta"], budget=6, r_meas=5, seed=11,
                        floors=nf["floors"], log_path=traj,
                        devset_hash=json.load(open(MANIFEST_PATH, encoding="utf-8"))["devset_hash"])
    props = [{"freedom": "params.theta_util", "value": 0.25, "reason": "放宽效用门控"},
             {"freedom": "params.n_frames", "value": 4, "reason": "多一帧生成"},
             {"freedom": "params.n_cand_per_frame", "value": 2, "reason": "每路采两份"},
             {"freedom": "params.m_clusters", "value": 2, "reason": "装配只留两个代表"}]
    res = opt.run(base, props)
    print("\n【L3 优化轨迹】改动 %d 次，停止原因 %s" % (res["n_changes"], res["halt_reason"]))
    for r in res["records"]:
        print("   #%d %-24s VD_net %s → %s（Δ=%+.3g，δ=%.3g）⇒ %s"
              % (r["step"], r["changed_freedom"], r["vd_net_theta"], r["vd_net_theta_prime"],
                 r["gain"], r["delta"], r["decision"]))
        if r["counter_criteria"]["warnings"]:
            for w in r["counter_criteria"]["warnings"]:
                print("        ⚠ %s" % w)

    # ── L1：信用分配
    tbl = CR.credit_table(base, ["params:n_frames", "params:stop_patience",
                                 "params:m_clusters", "params:n_cand_per_frame"],
                          devset=tasks, runner=FakeRunner(tasks), ref_cfg=ref,
                          r_meas=5, delta=nf["threshold_delta"], seed=5)
    CR.save_credit_table(tbl, os.path.join(OUT_DIR, "credit_table.json"))
    print("\n【L1 信用分配】")
    for row in tbl["components"]:
        print("   %-28s Δ=%+.3g ⇒ %s" % (row["component"], row.get("delta_vd_net") or 0.0,
                                          row.get("verdict")))
    print("   冗余=%s ｜ 反向=%s" % (tbl["redundant"], tbl["reverse"]))
    print("   生成账 %s ｜ 测量账 %s（测量次数 %d）"
          % (tbl["billing"]["cost_gen"], tbl["billing"]["cost_meas"],
             tbl["billing"]["n_measurements"]))
    print("\n产物落盘：%s/{noise_floor.json,trajectory.jsonl,credit_table.json}" % OUT_DIR)
    return {"noise_floor": nf, "trajectory": res, "credit": tbl}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--keep", action="store_true", help="保留临时目录")
    ap.add_argument("--demo", action="store_true", help="只跑一次完整契约（L0→L3→L1）并落盘")
    args = ap.parse_args()

    with open(DEVSET_PATH, encoding="utf-8") as f:
        ds = json.load(f)
    tasks = ds["tasks"]
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        man = json.load(f)
    h = _devset_hash(tasks)
    frozen_ok = (man.get("devset_hash") == h)
    print("DEV 集：%d 题，冻结哈希 %s（现算 %s）⇒ %s"
          % (len(tasks), man.get("devset_hash"), h,
             "一致" if frozen_ok else "**不一致**"))

    os.makedirs(OUT_DIR, exist_ok=True)
    import optimizer as OPT            # 被测模块（真实）
    import noise_floor as NF            # noqa: F401
    import credit as CR                 # noqa: F401

    if args.demo:
        demo(tasks)
        return 0

    results = {"devset_hash_frozen": frozen_ok, "devset_hash": h, "runs": []}

    # ── 正常模式
    tmpdir = tempfile.mkdtemp(prefix="optself_")
    try:
        ck = selfcheck(OPT, tasks, tmpdir)
    finally:
        if not args.keep:
            shutil.rmtree(tmpdir, ignore_errors=True)
    normal = {"mode": "normal", "passed": ck.ok, "n_checks": len(ck.items),
              "failed": [i["name"] for i in ck.failed], "checks": ck.items}
    results["runs"].append(normal)
    print("\n【正常模式】%d 项检查，%s" % (len(ck.items), "全部通过" if ck.ok else
                                          "**失败 %d 项**" % len(ck.failed)))
    for i in ck.items:
        if not i["ok"]:
            print("   ✘ %s：%s" % (i["name"], i["detail"]))
    for i in ck.items:
        if i["ok"]:
            print("   ✓ %s：%s" % (i["name"], i["detail"]))

    # ── 变异注入
    src = open(os.path.join(HERE, "optimizer.py"), encoding="utf-8").read()
    for label, fname, body, expect_fail in MUTATIONS:
        mutated = mutate_function(src, fname, body)
        mod, mtmp = load_mutant(mutated, "optimizer_mut_%s" % fname.strip("_"))
        tdir = tempfile.mkdtemp(prefix="optmut_run_")
        try:
            ck2 = selfcheck(mod, tasks, tdir)
        finally:
            shutil.rmtree(tdir, ignore_errors=True)
            shutil.rmtree(mtmp, ignore_errors=True)
        failed_names = [i["name"] for i in ck2.failed]
        hit = [n for n in expect_fail if n in failed_names]
        detected = bool(failed_names) and bool(hit)
        results["runs"].append({"mode": "mutation", "label": label, "function": fname,
                                "detected": detected, "expect_failed_at_least": expect_fail,
                                "hit": hit, "failed": failed_names, "checks": ck2.items})
        print("\n【变异 %s】%s" % (label, "**自检报出 FAIL（变异被抓住）**" if detected
                                  else "❌ 自检仍然全绿 ⇒ 这套自检抓不住这个变异（摆设！）"))
        for i in ck2.failed:
            print("   ✘ %s：%s" % (i["name"], i["detail"]))
        if not detected:
            print("   ⚠ 期望失败的检查：%s；实际失败：%s" % (expect_fail, failed_names))

    # ── 总结
    all_detected = all(r.get("detected") for r in results["runs"] if r["mode"] == "mutation")
    normal_ok = normal["passed"]
    print("\n" + "=" * 72)
    print("正常模式：%s" % ("PASS" if normal_ok else "FAIL"))
    print("变异注入：%s" % ("全部被抓住（%d/%d）" % (
        sum(1 for r in results["runs"] if r["mode"] == "mutation" and r.get("detected")),
        sum(1 for r in results["runs"] if r["mode"] == "mutation"))
        if all_detected else "**有变异未被抓住**"))
    print("=" * 72)

    with open(SELFCHECK_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print("读数落盘：%s" % SELFCHECK_JSON)

    if args.json:
        print(json.dumps({k: v for k, v in results.items() if k != "runs"},
                         ensure_ascii=False, indent=2))
    return 0 if (normal_ok and all_detected) else 1


if __name__ == "__main__":
    sys.exit(main())
