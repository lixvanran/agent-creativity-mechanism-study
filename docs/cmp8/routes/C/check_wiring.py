# -*- coding: utf-8 -*-
"""路线 C · **接线自检**（params ↔ executor）+ 变异注入。

**为什么需要这个文件**（复核指出的盲区）：
  - `check_spec.py` 只对账 **spec ↔ params/topology**（规格与代码的**声明**是否一致）；
  - `test_train_loop.py` 只验**训练回路跑得通**；
  ⇒ 两边都**看不见**"某个参数在执行器里根本没有读取点"这件事。
    复核实测：`P12 stop_patience` 在 `params.py` 有定义、在 `spec.yaml` 有条目、
    在 DESIGN 里标「生效拓扑 T1–T5」，但 `executor.py` **从不读它**
    ⇒ `stop_patience=0` 与 `=3` 产出**逐字相同**的答案 ⇒ 死参数混进了交付物。

**本自检对每个参数做两件事**：
  ① **读点**（grep 级）：参数名在 `executor.py` 里有真实的读取点
     （`theta.get("<name>"` / `theta["<name>"]`）。
  ② **探针**（行为级）：**改它 ⇒ 目标函数 `J` 真的变**。
     用**假客户端 + 假判官**（0 次真实 API 调用），跑的是 `train_params.evaluate`
     （**真正的训练目标函数**，不是它的副本）⇒ 探针测的就是训练期用的那个 J。

**再加一条变异注入**（否则本自检只是摆设）：
  把某个参数的读取点从 `executor.py` 里**去掉**（在临时副本上做，不碰原件）
  ⇒ 本自检**必须 FAIL**（退出码非 0）⇒ 证明它真的能抓到"参数没接上"。

⚠️ **探针的诚实边界**：探针用**刻意构造**的假语料/假判官，证明每个参数
**能够**改变 J；它**不**证明在真实语料与真实判官上每个参数都会改变 J
（那要等真跑，且 §12 已声明本路线尚未跑任何正式测量）。

用法：
    python3 check_wiring.py                # 全量自检（含变异注入）
    python3 check_wiring.py --root DIR     # 对着别的目录跑（变异注入用）
    python3 check_wiring.py --no-mutation  # 只跑检查，不跑变异注入（变异副本里用）
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE


# ====================================================================== 假客户端
#: 每个认知位置的三种伪断言：
#:   s0   = 第 1 次采样抽出的**「支持」**断言
#:   u1   = 第 2 次采样抽出的**「未提及」**断言（⇒ 支撑 P3/P6/P8/P9 的探针）
#:   deep = **深挖步**抽出的**「支持」**断言（⇒ 深挖步是"有产出"的 ⇒ P12 的探针能测到）
#: 第 3 次及以后的采样 ⇒ 返回与第 1 次**相同**的内容 ⇒ 被去重挡掉 ⇒ 空转（⇒ 坍缩比 P10 的探针能测到）
#: 深挖步在同一位置的**第 2 次** ⇒ 同样返回重复内容 ⇒ **空转**（⇒ T4 停滞信号 P7 的探针能测到）
CLAIMS = {
    "直答": ("甲成立因为规则来源写在第一条", "乙未提及因为合同主体尚未确定", "丙成立因为执行顺序另有安排"),
    "规则来源与适用条件": ("丁成立因为程序步骤有时限要求", "戊未提及因为证据覆盖存在缺口", "己成立因为条款适用顺序已经排定"),
    "程序步骤与时限": ("庚成立因为例外情形另有规定", "辛未提及因为与前一条说法不一致", "壬成立因为时限起算点已经写明"),
    "例外情形与边界条件": ("癸成立因为数量阈值可以计算", "子未提及因为权利义务关系不明", "丑成立因为边界条件已经列明"),
    "数量阈值与计算关系": ("寅成立因为主体关系写得很清楚", "卯未提及因为信息缺口没有补上", "辰成立因为适用条件已被限定"),
    "主体之间的权利义务关系": ("巳成立因为时效是否经过存疑", "午未提及因为依据是否充分未知", "申成立因为双方权利义务已写明"),
    "证据覆盖与信息缺口": ("酉成立因为限缩解释规则另有依据", "戌未提及因为救济方式并未约定", "亥成立因为证据缺口已被指出"),
}

#: 假判官：文本里带「成立」⇒ 支持；带「矛盾」⇒ 矛盾；否则 ⇒ 未提及
def fake_verifier(ask, ev, claims):
    out = {}
    for c in claims:
        if "矛盾" in c:
            out[c] = "矛盾"
        elif "成立" in c:
            out[c] = "支持"
        else:
            out[c] = "未提及"
    return out


class FakeLLM:
    """假客户端（**0 次真实 API 调用**）：按 prompt 类型返回可区分的伪内容。

    为什么这样设计（探针要能测出**每个**参数 ⇒ 伪内容必须随这些量变化）：
      - 随**认知位置**变化 ⇒ `n_frames` / 深挖回路可测
      - 随**同位置的第几次采样**变化 ⇒ `n_cand_per_frame` 可测
      - **第 3 次采样返回重复内容** ⇒ 空转 ⇒ 坍缩比（草稿数 > 去重断言数）可测
      - **深挖步的第 2 次返回重复内容** ⇒ 空转 ⇒ T4 的连续空转窗口（P7）可测
      - 抽出来的断言**互不相同** ⇒ `theta_dist` / `m_clusters` 可测
    """

    def __init__(self):
        self.calls = 0
        self._sample = {}     # 位置 → 已采样次数
        self._deep = {}       # 位置 → 已深挖次数

    # -- 工具
    @staticmethod
    def _pos_of(prompt: str) -> str:
        m = re.search(r"【([^】]+)】", prompt)
        return m.group(1) if m else "直答"

    def _claims_for(self, pos: str, deep: bool) -> list:
        s0, u1, dp = CLAIMS.get(pos) or CLAIMS["直答"]
        if deep:
            k = self._deep.get(pos, 0)
            self._deep[pos] = k + 1
            # 第 1 次深挖 ⇒ 有产出（新断言）；第 2 次 ⇒ 重复内容 ⇒ 空转
            return [dp] if k == 0 else [s0]
        k = self._sample.get(pos, 0)
        self._sample[pos] = k + 1
        if k == 0:
            return [s0]
        if k == 1:
            return [u1]
        return [s0]            # 第 3 次采样 ⇒ 重复 ⇒ 被去重挡掉 ⇒ 空转

    # -- 接口
    def chat(self, prompt, **kw):
        self.calls += 1
        if "逐条列出" in prompt:                   # 抽取
            pos = self._pos_of(prompt)
            deep = "再往前一步" in prompt
            lines = self._claims_for(pos, deep)
            return "\n".join("- " + x for x in lines)
        if "把下面这条陈述拆" in prompt:            # 拆分（`split_prompt` 的开头）
            return "- 拆出来的子断言成立因为可分别核验"
        # 生成
        pos = self._pos_of(prompt)
        deep = "再往前一步" in prompt
        # 草稿里带上【位置】与「再往前一步」标记 ⇒ 抽取那一步能从草稿里认回位置与深挖标记
        return ("草稿【%s】%s 下面给出关于本问题的具体判断与做法。" %
                (pos, "（再往前一步）" if deep else "（浅采样）"))


# ====================================================================== 探针表
#: 每个参数在**哪个拓扑**、**哪组基线 θ**、**哪两个取值**上做探针。
#: 基线 θ 是**刻意构造**的（见模块 docstring 的诚实边界）：
#:   - 基线尽量**小**（少帧、少采样、关深挖）⇒ 不让「调用预算超限 ⇒ 截断」掩盖参数效应
#:   - 需要「空转步」的地方（停滞窗口 P7）才把 `stop_patience` 开到 2
PROBE = {
    "n_frames":         ("T2", dict(n_frames=1, n_cand_per_frame=1, stop_patience=0), 1, 3),
    "n_cand_per_frame": ("T2", dict(n_frames=1, stop_patience=0, theta_util=0.0), 1, 3),
    "theta_util":       ("T2", dict(n_frames=1, n_cand_per_frame=2, stop_patience=0), 0.0, 1.0),
    "theta_dist":       ("T2", dict(n_frames=2, n_cand_per_frame=1, stop_patience=0), 0.25, 1.0),
    "n_verify_max":     ("T2", dict(n_frames=1, n_cand_per_frame=1, stop_patience=0), 0, 12),
    "n_split_max":      ("T3", dict(n_frames=1, n_cand_per_frame=2, stop_patience=0), 0, 4),
    "stall_window":     ("T4", dict(n_frames=1, stop_patience=2, realloc_frac=0.25,
                                    theta_stall=0.0), 1, 4),
    "theta_stall":      ("T4", dict(n_frames=1, n_cand_per_frame=2, stop_patience=0,
                                    realloc_frac=0.25, stall_window=4), 0.0, 0.75),
    "realloc_frac":     ("T4", dict(n_frames=1, n_cand_per_frame=2, stop_patience=0,
                                    theta_stall=0.75, stall_window=4), 0.0, 0.25),
    "theta_collapse":   ("T5", dict(n_frames=1, n_cand_per_frame=3, stop_patience=0), 0.0, 0.75),
    "m_clusters":       ("T2", dict(n_frames=2, n_cand_per_frame=1, stop_patience=0), 1, 8),
    "stop_patience":    ("T2", dict(n_frames=1, n_cand_per_frame=1, stop_patience=0), 0, 2),
}

#: 探针用的合成任务（**不是** DEV 集、**不是** U1–U4）
TOPIC = dict(task_id="WIRE-1", ask="某项规则如何适用？", evidence="（合成）依据包",
              key_conclusions=[])

#: 探针的调用上限（**大于**训练期的 CALL_CAP=12）：
#: 目的：让「参数能不能改变 J」这件事可测；**不是**放宽训练期的预算约束
#: （训练期仍然是 C3：每 episode ≤ 12 次调用，见 `train_params.CALL_CAP`）。
PROBE_MAX_CALLS = 24


# ====================================================================== 检查
def read_points(src: str, pname: str) -> list:
    """参数名在执行器源码里的**读取点**（行号列表）。"""
    pat = re.compile(r"theta\s*\.\s*get\(\s*[\"']%s[\"']" % re.escape(pname))
    pat2 = re.compile(r"theta\s*\[\s*[\"']%s[\"']" % re.escape(pname))
    out = []
    for i, ln in enumerate(src.splitlines(), 1):
        if pat.search(ln) or pat2.search(ln):
            out.append(i)
    return out


def probe_j(root: str, pname: str, topo: str, base: dict, v1, v2):
    """跑两个取值，返回 (J1, J2, J 差值)。用**真正的**训练目标函数。"""
    sys.path.insert(0, root)
    for mod in ("params", "executor", "topology", "train_params"):
        if mod in sys.modules:
            del sys.modules[mod]
    import params as P
    import train_params as TP
    js = []
    for v in (v1, v2):
        th = P.default_theta()
        th.update(base)
        th[pname] = v
        res = TP.evaluate(th, topo, [TOPIC], llm=FakeLLM(), verifier=fake_verifier,
                          reps=1, max_calls=PROBE_MAX_CALLS)
        js.append(res["J"])
    return js[0], js[1], js[1] - js[0]


def run_checks(root: str) -> tuple:
    """返回 (results, ok)。results = [(name, executed, ok, detail)]。"""
    import params as P
    sys.path.insert(0, root)
    if "params" in sys.modules:
        del sys.modules["params"]
    import params as P  # noqa: F811  (重新按 root 载入)

    exec_path = os.path.join(root, "executor.py")
    src = open(exec_path, encoding="utf-8").read()
    results = []

    # [1] 每个参数在执行器里有读取点
    missing = []
    for p in P.PARAM_SPEC:
        if not read_points(src, p["name"]):
            missing.append("%s(%s)" % (p["id"], p["name"]))
    results.append(("参数→执行器 读点", True, not missing,
                    "12 个参数的读点：%s" % ("全部命中" if not missing
                                            else "缺 " + ", ".join(missing))))

    # [2] 每个参数：改它 ⇒ J 真的变
    for p in P.PARAM_SPEC:
        name = p["name"]
        if name not in PROBE:
            results.append(("探针 %s" % name, True, False, "**探针表里没有这个参数**"))
            continue
        topo, base, v1, v2 = PROBE[name]
        if topo not in p["applies_to"]:
            results.append(("探针 %s" % name, True, False,
                            "拓扑 %s 不在 applies_to=%s 里" % (topo, p["applies_to"])))
            continue
        try:
            j1, j2, d = probe_j(root, name, topo, base, v1, v2)
        except Exception as e:                      # 探针跑不起来 ⇒ 判失败（不吞异常）
            results.append(("探针 %s" % name, True, False, "探针异常：%r" % (e,)))
            continue
        ok = abs(d) > 1e-9
        results.append(("探针 %s" % name, True, ok,
                        "%s %s→%s：J %.4f → %.4f（Δ%+.4f）" %
                        (topo, v1, v2, j1, j2, d)))

    # [3] 探针表与参数表**一一对应**（防止加参数忘了加探针）
    extra = sorted(set(PROBE) - set(p["name"] for p in P.PARAM_SPEC))
    results.append(("探针表覆盖", True, not extra,
                    "参数 %d 个 / 探针 %d 个%s" % (len(P.PARAM_SPEC), len(PROBE),
                                                  ("；多出 " + ",".join(extra)) if extra else "")))
    return results, all(r[1] and r[2] for r in results)


def aggregate(results) -> tuple:
    """汇总：**跳过任何一项 ⇒ 整体不是 PASS**（fail-closed）。"""
    failed = [r for r in results if r[1] and not r[2]]
    skipped = [r for r in results if not r[1]]
    return failed, skipped


def print_results(title, results, ok):
    print("== %s ==" % title)
    for name, executed, good, detail in results:
        mark = "PASS" if (executed and good) else ("FAIL" if executed else "SKIP")
        print("[%-4s] %-26s %s" % (mark, name, detail))
    failed, skipped = aggregate(results)
    print("可执行项 %d / %d；失败 %d；跳过 %d" %
          (len(results) - len(skipped), len(results), len(failed), len(skipped)))
    if skipped:
        print("⚠️ 有项目**未执行**（不算通过）")
    print("结果：%s" % ("PASS" if ok else "FAIL"))
    return ok


# ====================================================================== 变异注入
#: 变异目标：把 `n_verify_max` 的读取点换成一个常量 ⇒ 该参数变成死参数
MUTATION_OLD = 'int(self.theta.get("n_verify_max", 6))'
MUTATION_NEW = "int(6)"


def mutation_test(root: str) -> tuple:
    """在**临时副本**上删掉一个参数的读取点 ⇒ 本自检必须 FAIL。

    返回 (ok, detail)。**不碰原目录**（用 shutil.copytree 到 mktemp）。
    """
    tmp = tempfile.mkdtemp(prefix="routeC_wiring_mut_")
    try:
        dst = os.path.join(tmp, "C")
        shutil.copytree(root, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        exe = os.path.join(dst, "executor.py")
        src = open(exe, encoding="utf-8").read()
        if MUTATION_OLD not in src:
            return False, "变异目标没找到（%r 不在 executor.py 里）⇒ 变异注入**没跑起来**" % MUTATION_OLD
        open(exe, "w", encoding="utf-8").write(src.replace(MUTATION_OLD, MUTATION_NEW, 1))
        # 在副本上跑本自检（不递归跑变异注入）
        p = subprocess.run([sys.executable, os.path.join(dst, "check_wiring.py"),
                            "--root", dst, "--no-mutation"],
                           capture_output=True, text=True, timeout=300)
        detail = "变异：executor.py 里把 %s 换成 %s ⇒ 变异副本自检退出码=%d" % (
            MUTATION_OLD, MUTATION_NEW, p.returncode)
        tail = [ln for ln in p.stdout.splitlines() if "读点" in ln or "探针 n_verify_max" in ln]
        if tail:
            detail += "｜" + " / ".join(t.strip() for t in tail)
        return (p.returncode != 0), detail
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ====================================================================== main
def main():
    global ROOT
    args = sys.argv[1:]
    do_mut = "--no-mutation" not in args
    if "--root" in args:
        ROOT = os.path.abspath(args[args.index("--root") + 1])

    results, ok = run_checks(ROOT)
    ok = print_results("路线 C 接线自检（params ↔ executor）", results, ok) and ok

    if do_mut:
        mut_ok, mut_detail = mutation_test(ROOT)
        print("\n== 变异注入 ==")
        print("[%-4s] %s" % ("PASS" if mut_ok else "FAIL", mut_detail))
        print("结果：%s" % ("PASS（变异被抓住了）" if mut_ok else "FAIL（变异没被抓住 ⇒ 自检是摆设）"))
        ok = ok and mut_ok

    print("\n最终：%s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
