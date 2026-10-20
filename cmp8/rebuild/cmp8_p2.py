import os
FILES = {}

# ==================================================================
# armdeps/client2.py —— 旧项目的生成+embedding 双通道（带过载降级）
# ==================================================================
FILES["cmp8/armdeps/client2.py"] = r'''
"""生成 + embedding 双通道（臂 3/臂 4 用）。
embedding 参数是 texts（不是 input）且必须带 type:db。
**529 过载要降级换模型；429 限流只退避不换模型**（换模型会改掉「模型构成」这个变量）。"""
import os, re, json, time, math, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.environ.get("OPENROUTER_BASE_URL", "https://api.minimaxi.com/v1")
KEY = os.environ.get("MINIMAX_SUBSCRIPTION_KEY", "")
MODELS = ["MiniMax-M3", "MiniMax-M3.1-Flash-Preview", "MiniMax-M2.7", "MiniMax-M2.5",
          "MiniMax-M2.1", "MiniMax-M2", "MiniMax-M2.7-highspeed",
          "MiniMax-M2.5-highspeed", "MiniMax-M2.1-highspeed"]
PRIMARY = os.environ.get("PRIMARY_MODEL", "MiniMax-M3")
FALLBACKS = ["MiniMax-M3.1-Flash-Preview", "MiniMax-M2.7"]
MODEL_LOG = {}


def _is_overload(t):
    t = t or ""
    return ("overloaded" in t) or ("负载较高" in t) or ('"529"' in t)


def st(t):
    t = re.sub(r"<think>.*?</think>", "", t or "", flags=re.S)
    return re.sub(r"^.*?</think>", "", t, flags=re.S).strip()


def chat(p, model=None, temp=1.0, mt=8000, tries=(12000, 16000), min_ok=300):
    """三种失败机制都要挡：
       1) M3.1-Flash 把思考放进 reasoning_content，content 可能整个缺失
       2) 弱模型档位会把预算全花在 meta 分析 persona 指令上，<think> 未闭合、无正文
       3) think 吃光预算导致 finish_reason='length' 截断
       4) **服务端过载 529** → 退避重试，仍不通则降级到健康档位
    """
    model = model or PRIMARY
    last = ""
    for mm in [model] + [m for m in FALLBACKS if m != model]:
        for m in (mt,) + tries:
            try:
                req = urllib.request.Request(f"{BASE}/chat/completions",
                    data=json.dumps({"model": mm, "messages": [{"role": "user", "content": p}],
                                    "temperature": temp, "max_tokens": m}).encode(),
                    headers={"Authorization": "Bearer " + KEY, "content-type": "application/json"})
                raw = urllib.request.urlopen(req, timeout=240).read().decode()
                if _is_overload(raw):
                    time.sleep(5)
                    break
                d = json.loads(raw)
                ch = d["choices"][0]
                last = ch["message"].get("content") or ""
                if ch.get("finish_reason") == "length":
                    continue
                o = st(last)
                if o.count("<think>") > o.count("</think>"):
                    continue
                if len(o) >= min_ok:
                    MODEL_LOG[mm] = MODEL_LOG.get(mm, 0) + 1
                    return o
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode()
                except Exception:
                    pass
                if _is_overload(body):
                    time.sleep(5)
                    break
                time.sleep(2.5)
            except Exception:
                time.sleep(2.5)
    return last


def par(p, n, models=None, temp=1.0, mt=3000, workers=5):
    models = models or [PRIMARY] * n
    out = [""] * n
    with ThreadPoolExecutor(max_workers=workers) as ex:
        f = {ex.submit(chat, p, models[i], temp, mt): i for i in range(n)}
        for x in as_completed(f):
            try:
                out[f[x]] = x.result()
            except Exception:
                out[f[x]] = ""
    return out


_EMB = {}


def emb(texts, typ="db"):
    if not texts:
        return []
    req = urllib.request.Request(f"{BASE}/embeddings",
        data=json.dumps({"model": "embo-01", "type": typ, "texts": texts}).encode(),
        headers={"Authorization": "Bearer " + KEY, "content-type": "application/json"})
    for _ in range(3):
        try:
            v = json.loads(urllib.request.urlopen(req, timeout=90).read().decode())["vectors"]
            for t, e in zip(texts, v):
                _EMB[t] = e
            return v
        except Exception:
            time.sleep(2)
    return []


def cos(a, b):
    n = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(x * x for x in b))
    return n / (da * db) if da and db else 0.0
'''

# ==================================================================
# armdeps/shared.py —— 各臂共享的输出规格与措辞约束
# ==================================================================
FILES["cmp8/armdeps/shared.py"] = r'''
"""各臂共享的输出规格与措辞约束。

放在这里而不是由调用方传入，是为了让「输出长什么样」成为**工作流的一部分**，
而不是外部加在所有臂头上的一层统一话术——后者等于替所有臂统一加分。

措辞保持任务中性：只说「回答问题」，不说「要可执行/要新颖/要可检验」，
因为那些是**评价口径**，写进提示词等于给答案打标签。
"""
OUT_SPEC = "控制在 400 字以内。只输出答复本身。"

VALIDATE_Q = ("请逐一说明：每个判断依赖哪些前提？"
              "如果其中一个前提不成立，它会怎样？哪一条前提最脆弱？"
              "只按问题本身的重要性回答，不要为了显得深刻而拔高。")

SELECT_Q = ("请选出**对提问者最有用**的一份，说明理由，然后**原样输出**它的全文。"
            "不要重写、不要融合、不要拼接。")
'''

# ==================================================================
# armdeps/arm3.py —— 双轴架构（帧 / persona / 模型轮换）
# ==================================================================
FILES["cmp8/armdeps/arm3.py"] = r'''
"""臂3/臂4 共享的双轴发散架构。

两轴都在代码里，不是提示词里的叙述：
  轴A VARIANCE → 治 fixation：5 个完全隔离的调用，各自一个认知框架
  轴B PARTITION → 治无知识分区：跨 MiniMax 5 个规模档位 + 5 个普通 persona

措辞纪律：框架 / persona / 提问里**不出现**评价口径的词（新颖、可检验、框架转换、
高光、立场代价……），也不出现任何题面元素。那等于给答案打标签。
"""
import client2 as C
from shared import OUT_SPEC, VALIDATE_Q

# 认知框架：vantage operator（换一个提问位置），不是身份、不是专家人设
FRAMES = [
    ("长时段尺度", "把时间尺度拉到数十年到数百年。同一类现象在更长周期里反复出现过什么形态？它这次的量级和结构有什么不同？"),
    ("系统承载力", "把规模推到极限。这个系统在什么量级上会开始失稳？先崩的是哪一环？承载力由什么决定？"),
    ("反面案例", "找做对的事后来是怎么崩的。当时没人看见的信号是什么？事后能看清、事前看不见的是什么？"),
    ("无利害观察者", "假设你对这件事没有任何利害关系，既不受益也不受损。你会怎么描述它？"),
    ("亲历者视角", "如果这件事真的发生，一个生活被它直接改变的人会怎么过一天？他的具体动作和妥协是什么？"),
    ("硬约束", "先不谈趋势，只谈硬边界：物理的、资源的、制度的。哪些东西是不管多想都不可能变的？"),
    ("二阶效应", "假设第一阶效果已经被普遍接受并内化了。那剩下的那个让人不满意的第二阶问题是什么？"),
]

# 普通 persona：只给身份与生活状态，**不含任何任务线索**。
PERSONAS = [
    "你是一名 1962 年出生、在国营机械厂车间干了三十一年的退休工人。",
    "你是一名 1998 年出生、在城市做零工、租住在城中村的年轻人，识字不多但对街面上的事极其敏感。",
    "你是一名 1975 年出生、在县城开了一家小诊所的家庭医生，一辈子处理的是人和身体。",
    "你是一名 2003 年出生、刚工作两年的年轻人，关心自己这一代会被定义成什么。",
    "你是一名 1955 年出生、在报社做了四十年国际新闻的退休编辑，见证过三次技术乐观主义的落空。",
]

# 轴B 的模型轮换：跨规模档位（不同训练 → 部分不同的知识分布）
AXIS_B_MODELS = ["MiniMax-M3", "MiniMax-M3.1-Flash-Preview", "MiniMax-M2.7",
                 "MiniMax-M2.5", "MiniMax-M2.1"]

DIAG = []


def diverge(n=5, workers=1, topic=None):
    """轴A × 轴B 的联合扇出：5 个完全隔离的调用。"""
    DIAG.clear()
    prompts, models = [], []
    for i in range(n):
        fname, fprompt = FRAMES[i]
        prompts.append(
            f"问题：{topic}\n\n"
            f"你现在从【{fname}】这个认知位置出发去看这个问题。\n{fprompt}\n\n"
            f"设定：{PERSONAS[i]}\n\n"
            f"直接写出你的判断和依据，200-400字。\n- {OUT_SPEC}"
        )
        models.append(AXIS_B_MODELS[i])
    outs = C.par(prompts, n, models=models, workers=workers)
    for i, o in enumerate(outs):
        DIAG.append(dict(model=models[i], frame=FRAMES[i][0],
                        ok=bool(o and len(o) > 60), chars=len(o or "")))
    return [o for o in outs if o and len(o) > 60]


def deep_validate(cands, topic=None):
    """前提审查。中性措辞：不问『是否不寻常』，只问『依赖什么前提』。"""
    joined = "\n\n---\n".join(f"[{i+1}] {c[:400]}" for i, c in enumerate(cands))
    return C.chat("下面是若干份关于同一问题的独立判断。\n\n" + joined +
                  "\n\n" + VALIDATE_Q + "\n\n150-250字。")


def deception_check(cands, deep, topic=None):
    """反诘：这套判断隐含的『什么算好』是什么，它会把人带到哪个死胡同。"""
    return C.chat(
        "你刚才在这些判断中隐含了一个『什么算好』的标准。\n\n"
        "这些判断：\n" + "\n".join(f"[{i+1}] {c[:180]}" for i, c in enumerate(cands)) +
        "\n\n对它们前提的分析：\n" + deep[:400] +
        "\n\n请明确回答：你隐含的『好』是什么？沿着这个标准走下去，最可能把判断带进哪个死胡同？"
        "有没有一个它系统性高估、但其实不成立的东西？100-200字。")
'''

# ==================================================================
# run_compare5.py —— 7 臂驱动
# ==================================================================
FILES["cmp8/run_compare5.py"] = r'''
# -*- coding: utf-8 -*-
"""五族对比实验：用户的四道题（A1–A4）× 多臂 × 多重复。

臂清单
  A1  直调（1 次调用）
  A2  开源 ADHD 项目（**机制复现**，11 步流水线 + 汇总重写）
  A3  双轴·融合门（5 分支 → 前提审查 → 反诘 → 融合重写）
  A4  双轴·去融合门（5 分支各写完整答复 → 只选不融）
  A5a 新架构·**无核验**（只 GEN/EXTRACT/SPLIT，机械装配）   ← 控制：有没有 oracle
  A5b 新架构·**学到的策略**·有核验（依据包）                  ← 主实验
  A5c 新架构·**初始策略 w=0**·有核验                          ← 控制：学到的权重有没有用

为什么要 A5a / A5c：
  A5b 唯一接触 oracle 的操作是 VERIFY。若只报 A5b，无法区分
    (i) 架构本身更强   vs   (ii) 它拿到了别人没有的事实核验器。
  A5a 隔离 (ii)；A5c 隔离「学到的权重」是否真的有用。

新架构的认知位置（FRAME/PERSONA/模型轮换）与 A3/A4 **完全一致**，
差异只在架构机制本身 —— 这样对比才公平。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "armdeps"))

import client2 as C                       # noqa: E402
import arm3                              # noqa: E402
from creativity_lab.learnarch import run_episode  # noqa: E402
from creativity_lab.client import LLM     # noqa: E402

OUT = os.environ.get("CMP_OUT", "runs/cmp8")
os.makedirs(OUT, exist_ok=True)
PRIMARY = os.environ.get("PRIMARY_MODEL", "MiniMax-M3.1-Flash-Preview")

TOPICS4 = [
    dict(tid="A1", title="湖北 620 分选 AI 专业",
         q="湖北考生，物理类620分，想学AI，应当如何选择大学？"),
    dict(tid="A2", title="公路自行车个人赛战术",
         q="公路自行车个人比赛（无车队），单圈1.6km共计15圈，单圈由两个800m直路和两个回头弯构成，"
           "本人在大集团里处于中上等水平，该如何安排战术？"),
    dict(tid="A3", title="假期最后一天作业没动",
         q="今天是五一小长假的最后一天的18:00，明天就要上学了，我的作业还一笔没动，怎么办？"),
    dict(tid="A4", title="解读一份气质量表得分",
         q="这是一份陈会昌气质量表的最终得分：胆汁质-6，多血质23，粘液质-4，抑郁质-1。"),
]
# 依据包（联网独立构造，不含任何答案暗示）
EV = {}
for _i in (1, 2, 3, 4):
    _p = os.path.join(HERE, "creativity_lab", "data", "user4_q%d.json" % _i)
    if os.path.exists(_p):
        EV["A%d" % _i] = json.load(open(_p, encoding="utf-8"))["evidence"]

# ---- 模型集：本轮因 M3 持续过载(529)而固定。轴B 的设计意图是「跨 5 个不同规模档位」，
# M3 挂掉时若让它的位置自动降级到 M3.1-Flash-Preview，就会与轮换里的
# M3.1-Flash-Preview 撞档 → 轴B 的多样性被悄悄削掉一半。所以显式指定 5 个互不相同的档位。
MODELS_5 = ["MiniMax-M3.1-Flash-Preview", "MiniMax-M2.7", "MiniMax-M2.5",
            "MiniMax-M2.1", "MiniMax-M2"]
arm3.AXIS_B_MODELS = MODELS_5
# 新架构的认知位置：与 A3/A4 逐条一致
ANGLES5 = [(arm3.FRAMES[i][0], arm3.FRAMES[i][1], arm3.PERSONAS[i], arm3.AXIS_B_MODELS[i])
           for i in range(5)]

ART = ("给出一份 400 字以内、可直接执行的答复。观点明确、给出具体动作与依据，"
       "不要罗列各方观点，不要写空话。只输出答复正文。")
A2_MODEL_USED = {}


def log(d):
    with open("%s/runlog.jsonl" % OUT, "a") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def save(arm, tid, rep, text, extra=None):
    open("%s/%s_r%d_%s.md" % (OUT, tid, rep, arm), "w", encoding="utf-8").write(text or "")
    if extra is not None:
        json.dump(extra, open("%s/%s_r%d_%s.json" % (OUT, tid, rep, arm), "w"),
                  ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ 旧四臂
def arm_direct(q):
    return C.chat(f"{q}\n\n{ART}", PRIMARY, 1.0, 4000, min_ok=120)


def arm_adhd(q, seed=0):
    """开源 ADHD 项目臂（**机制复现**：creativity_lab/adhd_repro.py，
    照搬 engine.ts / frames.ts / render.ts，只换传输层）。
    原版 node CLI 通道在实验当天彻底挂死（Claude Code process exited with code 1），
    保留 ADH_MODE=node 入口以便通道恢复时直接用原版。"""
    mode = os.environ.get("ADH_MODE", "repro")
    raw, used = "", ""
    if mode == "node":
        env = dict(os.environ)
        env["ANTHROPIC_BASE_URL"] = "https://api.minimaxi.com/anthropic"
        env["ANTHROPIC_API_KEY"] = C.KEY
        of = "%s/.a2_out.txt" % OUT
        try:
            with open(of, "w") as fo:
                subprocess.run(["node", "dist/cli.js", q, "--model", PRIMARY],
                               cwd=os.environ.get("ADH_REPO", "/workspace/adhd-repo"),
                               stdout=fo, stderr=subprocess.STDOUT,
                               env=env, timeout=int(os.environ.get("A2_TIMEOUT", "1200")))
            raw = re.sub(r"\x1b\[[0-9;]*m", "", open(of, encoding="utf-8", errors="ignore").read())
        except Exception as e:
            print("  A2 node err:", str(e)[:60], flush=True)
        if len(raw) < 400:
            print("  A2 node 通道不可用 → 退回 repro", flush=True)
            raw = ""
    if not raw:
        from creativity_lab.adhd_repro import run_adhd
        raw, meta = run_adhd(q, model=PRIMARY, llm=LLM(), seed=seed)
        used = "repro:" + PRIMARY
    A2_MODEL_USED[used or "none"] = A2_MODEL_USED.get(used or "none", 0) + 1
    ideas = [i[:300] for i in re.findall(r"^\s*-\s*(.+)", raw, re.M) if len(i) > 12][:24]
    a = ""
    if ideas:
        a = C.chat(f"{q}\n\n以下是若干个认知位置下产出的独立想法：\n" + "\n".join(f"- {i}" for i in ideas)
                   + f"\n\n{ART}", PRIMARY, 1.0, 4000, min_ok=120)
    return a, raw, len(ideas), used


def arm_fuse(q):
    cands = [c for c in arm3.diverge(5, workers=4, topic=q + "\n\n" + ART) if c and len(c) > 60]
    a = ""
    if len(cands) >= 2:
        deep = arm3.deep_validate(cands, topic=q)
        dec = arm3.deception_check(cands, deep, topic=q)
        a = C.chat("主题：" + q + "\n\n以下是若干个独立位置上产出的判断：\n"
                   + "\n\n---\n".join(f"[{i+1}] {c[:400]}" for i, c in enumerate(cands))
                   + "\n\n对它们差异与成立条件的分析：\n" + deep[:700]
                   + "\n\n对评价标准本身的反诘：\n" + dec[:500]
                   + f"\n\n请综合以上，{ART}", PRIMARY, 1.0, 4000, min_ok=120)
    return a, len(cands)


def arm_select(q):
    arts = []

    def _branch(i):
        fname, fp = arm3.FRAMES[i]
        m = arm3.AXIS_B_MODELS[i]
        pe = arm3.PERSONAS[i]
        p = (f"问题：{q}\n\n你现在从【{fname}】这个认知位置出发。\n{fp}\n\n设定：{pe}\n\n{ART}")
        return C.chat(p, m, 1.0, 8000, min_ok=120)

    with ThreadPoolExecutor(max_workers=4) as ex:
        for o in ex.map(_branch, range(5)):
            if o and len(o) >= 120:
                arts.append(o)
    a = ""
    if arts:
        if len(arts) == 1:
            a = arts[0]
        else:
            a = C.chat("同一个问题下有若干篇**各自独立**写成的答复：\n\n"
                       + "\n\n=====\n\n".join(f"[第{i+1}篇]\n{x}" for i, x in enumerate(arts))
                       + "\n\n请挑出**其中一篇原样输出**。判据（不要重写、不要融合、不要拼接）："
                       "① 哪一篇与常规建议最不同？② 哪一篇给出的具体判断最站得住——说清它在什么条件下成立？"
                       "③ 哪一篇最不像套话？先写 60-120 字说明，然后**原样贴出被选中那篇的全文**。",
                       PRIMARY, 1.0, 5000, min_ok=120)
    return a, arts


# ------------------------------------------------------------------ 新架构臂
def run_learnarm(q, tid, w, use_verify, seed):
    llm = LLM()
    ev = EV.get(tid, "") if use_verify else None
    if use_verify and not ev:
        return None
    rng = random.Random(seed)
    g, rew, info = run_episode(q, w, rng, ev=ev, angles=ANGLES5, budget=10,
                                explore=0.25, use_verify=use_verify, synth=True, llm=llm)
    return g, info


# ------------------------------------------------------------------ 主流程
def run_topic(T, arms, reps):
    tid, q = T["tid"], T["q"]
    for rep in range(1, reps + 1):
        for arm in arms:
            t0 = time.time()
            try:
                if arm == "A1":
                    a = arm_direct(q)
                    save(arm, tid, rep, a)
                    log(dict(tid=tid, rep=rep, arm=arm, chars=len(a), calls=1,
                             secs=round(time.time() - t0)))
                elif arm == "A2":
                    sd = 1000 * rep + int(hashlib.md5(tid.encode()).hexdigest()[:8], 16) % 97
                    a, raw, ni, a2m = arm_adhd(q, seed=sd)
                    save(arm, tid, rep, a)
                    open("%s/%s_r%d_A2raw.txt" % (OUT, tid, rep), "w").write(raw)
                    log(dict(tid=tid, rep=rep, arm=arm, chars=len(a), ideas=ni, calls=12,
                             model=a2m, secs=round(time.time() - t0)))
                elif arm == "A3":
                    a, nb = arm_fuse(q)
                    save(arm, tid, rep, a)
                    log(dict(tid=tid, rep=rep, arm=arm, chars=len(a), branches=nb, calls=8,
                             secs=round(time.time() - t0)))
                elif arm == "A4":
                    a, arts = arm_select(q)
                    save(arm, tid, rep, a)
                    json.dump(arts, open("%s/%s_r%d_A4arts.json" % (OUT, tid, rep), "w"),
                              ensure_ascii=False, indent=1)
                    log(dict(tid=tid, rep=rep, arm=arm, chars=len(a), branches=len(arts), calls=6,
                             secs=round(time.time() - t0)))
                elif arm in ("A5a", "A5b", "A5c"):
                    use_verify = arm != "A5a"
                    w = np.zeros(14)
                    if arm == "A5b":
                        w = np.array(json.load(open(
                            os.path.join(HERE, "runs", "arch_learn", "result.json"),
                            encoding="utf-8"))["w"])
                    # 种子必须可复现：Python 字符串 hash 带进程随机盐，不能直接用
                    seed = 1000 * rep + int(hashlib.md5(tid.encode()).hexdigest()[:8], 16) % 97
                    r = run_learnarm(q, tid, w, use_verify, seed=seed)
                    if r is None:
                        print(f"  [{tid} r{rep}] {arm} 跳过（依据包缺失）", flush=True)
                        continue
                    g, info = r
                    save(arm, tid, rep, info["final"])
                    if info.get("synth"):
                        open("%s/%s_r%d_%s_synth.md" % (OUT, tid, rep, arm), "w",
                             encoding="utf-8").write(info["synth"])
                    json.dump(dict(ops=info["ops"], width=info["width"], conflict=info["conflict"],
                                   n_legal=info["n_legal"], n_verify=info["n_verify"],
                                   hit=info["hit"], miss=info["miss"], fallback=info["fallback"],
                                   claims=info["claims"], verd=info["verd"]),
                              open("%s/%s_r%d_%s.json" % (OUT, tid, rep, arm), "w"),
                              ensure_ascii=False, indent=1)
                    log(dict(tid=tid, rep=rep, arm=arm, chars=len(info["final"]),
                             synth_chars=len(info.get("synth") or ""),
                             width=info["width"], conflict=info["conflict"],
                             n_verify=info["n_verify"], ops=info["ops"],
                             fallback=info["fallback"], secs=round(time.time() - t0)))
                print(f"[{tid} r{rep}] {arm} ✓ {time.time()-t0:.0f}s", flush=True)
            except Exception as e:
                print(f"[{tid} r{rep}] {arm} ERR {str(e)[:90]}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="A1,A2,A3,A4,A5a,A5b,A5c")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    arms = a.arms.split(",")
    print("臂:", arms, "｜重复:", a.reps, "｜依据包:", {k: len(v) for k, v in EV.items()}, flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in [ex.submit(run_topic, T, arms, a.reps) for T in TOPICS4]:
            f.result()
    print("ALL DONE %.0f 分钟" % ((time.time() - t0) / 60), flush=True)
'''

# ==================================================================
# analyze_cmp6.py —— 跨厂商判官分析器
# ==================================================================
FILES["cmp8/analyze_cmp6.py"] = r'''
# -*- coding: utf-8 -*-
"""跨厂商判官版分析器：7 臂 × 4 题 × 3 重复。

**与同源判官的关键差别**：被测 = MiniMax，**判官 = OpenRouter 上的 Grok**。
「判据与指标同源模型 ⇒ 判据无效」——判官和被测同厂容易对同一批错误达成一致。

**纪律：判官必须先通过自检，自检不过就拒绝出数**（不是出数了再解释）。
自检 = 已知的真断言（应判支持）+ 已知假断言（应判矛盾）。
假断言召回 <50% ⇒ 矛盾率不可信 ⇒ 整套作废。

**成本**：判官 ~170 次调用（Grok 3 Mini $0.30/$0.50 每 M）≈ $0.12；embedding ≈ $0.05。
"""
from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from creativity_lab.verify import check_claims, extract_claims   # noqa: E402
from creativity_lab import orclient                              # noqa: E402

OUT = os.environ.get("CMP_OUT", "runs/cmp8")
ARMS = ["A1", "A2", "A3", "A4", "A5a", "A5b", "A5c"]
ARM_NAME = {
    "A1": "① 直调", "A2": "② 开源ADHD项目(机制复现)", "A3": "③ 双轴·融合门",
    "A4": "④ 双轴·去融合门", "A5a": "⑤a 新架构·无核验(控制)",
    "A5b": "⑤b 新架构·学到的策略", "A5c": "⑤c 新架构·初始w=0(控制)",
}
TIDS = ["A1", "A2", "A3", "A4"]
QS = {
    "A1": "湖北考生，物理类620分，想学AI，应当如何选择大学？",
    "A2": "公路自行车个人比赛（无车队），单圈1.6km共计15圈，单圈由两个800m直路和两个回头弯构成，"
          "本人在大集团里处于中上等水平，该如何安排战术？",
    "A3": "今天是五一小长假的最后一天的18:00，明天就要上学了，我的作业还一笔没动，怎么办？",
    "A4": "这是一份陈会昌气质量表的最终得分：胆汁质-6，多血质23，粘液质-4，抑郁质-1。",
}
EV = {}
for _i in (1, 2, 3, 4):
    _p = os.path.join(HERE, "creativity_lab", "data", "user4_q%d.json" % _i)
    if os.path.exists(_p):
        EV["A%d" % _i] = json.load(open(_p, encoding="utf-8"))["evidence"]

SELFCHECK = {
    "A1": {"T": ["2025年湖北省普通高考首选物理类中，620分及以上的累计人数为7436人"],
           "F": ["2025年湖北省普通高考首选物理类中，620分及以上的累计人数为74360人"]},
    "A2": {"T": ["国际自行车联盟（UCI）公路赛规则第 2.3.012 条规定，比赛中任何两名车手之间都可以互相提供食物、饮品、扳手等小帮助"],
           "F": ["国际自行车联盟（UCI）公路赛规则第 2.3.012 条规定，比赛中任何两名车手之间不得互相提供食物、饮品、扳手等小帮助"]},
    "A3": {"T": ["番茄工作法由意大利人 Francesco Cirillo 在上世纪八十年代做大学生时用番茄形厨房计时器发展而来"],
           "F": ["番茄工作法规定每个番茄时段为 50 分钟，之后休息 10 分钟"]},
    "A4": {"T": ["如果四类得分中有一类得分明显高出其它三种且均高出4分以上，则可定为该类气质型",
                 "该类得分超过20分则为典型型，该类得分在10至20分则为一般型"],
           "F": ["如果四类得分中有一类得分明显高出其它三种且均高出2分以上，则可定为该类气质型",
                 "该类得分超过30分则为典型型，该类得分在20至30分则为一般型"]},
}


def dedup_with(emb, claims, thr=0.75):
    """用指定 embedding 去重（emb 需有 .embed(list) -> list[list[float]]）。"""
    if not claims:
        return []
    try:
        V = np.array(emb.embed(list(claims)), dtype=float)
        if V.ndim != 2 or V.shape[0] != len(claims):
            raise ValueError("shape %s" % (V.shape,))
        V = V / np.clip(np.linalg.norm(V, axis=1, keepdims=True), 1e-9, None)
        S = V @ V.T
        keep = []
        for i in range(len(claims)):
            if all(S[i, j] < thr for j in keep):
                keep.append(i)
        return [claims[i] for i in keep]
    except Exception as e:
        print("  [embed 失败，降级到字符bigram] %s" % str(e)[:60], flush=True)
        keep, G = [], []
        for c in claims:
            t = re.sub(r"\s", "", c or "")
            g = {t[i:i + 2] for i in range(len(t) - 1)}
            if all(len(g & g2) / max(len(g | g2), 1) < thr for g2 in G):
                keep.append(c)
                G.append(g)
        return keep


def arm_file(arm, tid, rep):
    """A5 系列的交付答案 = 合成版（与其它臂同为流式答复）；机械装配版另存。"""
    if arm.startswith("A5"):
        s = "%s/%s_r%d_%s_synth.md" % (OUT, tid, rep, arm)
        if os.path.exists(s) and os.path.getsize(s) > 40:
            return open(s, encoding="utf-8").read()
    p = "%s/%s_r%d_%s.md" % (OUT, tid, rep, arm)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def main():
    judge = orclient.LLM()
    emb = orclient.LLM()

    # ---------- 第一步：判官自检（不过就停）----------
    print("【判官自检】%s" % orclient.PRIMARY, flush=True)
    tp = fn = tn = fp = 0
    sc_detail = []
    for tid in TIDS:
        for lab, want in (("T", "支持"), ("F", "矛盾")):
            claims = SELFCHECK[tid][lab]
            v = check_claims(judge, QS[tid], EV.get(tid, ""), claims)
            for c in claims:
                got = v.get(c, "解析失败")
                ok = (got == want)
                if lab == "T":
                    tp += 1 if ok else 0
                    fn += 0 if ok else 1
                else:
                    tn += 1 if ok else 0
                    fp += 0 if ok else 1
                sc_detail.append((tid, lab, got, ok, c[:50]))
                print("  %s %s → %-4s %s" % (tid, lab, got, "✓" if ok else "✗"), flush=True)
    print("自检：真断言 %d/%d ｜ 假断言 %d/%d" % (tp, tp + fn, tn, tn + fp), flush=True)
    if (tn + fp) and tn / (tn + fp) < 0.5:
        print("❌ 判官在「已知假断言」上召回不足 50% ⇒ 矛盾率不可信，**拒绝出数**。")
        json.dump(dict(detail=sc_detail, aborted=True),
                  open("%s/judge_selfcheck.json" % OUT, "w"), ensure_ascii=False, indent=1)
        return
    json.dump(dict(detail=sc_detail, tp=tp, fn=fn, tn=tn, fp=fp, aborted=False,
                   judge=orclient.PRIMARY),
              open("%s/judge_selfcheck.json" % OUT, "w"), ensure_ascii=False, indent=1)

    # ---------- 第二步：逐份核验 ----------
    def one(arm, tid, rep):
        txt = arm_file(arm, tid, rep)
        if not txt.strip():
            return dict(arm=arm, tid=tid, rep=rep, chars=0, n_raw=0, width=0,
                        sup=0, con=0, unt=0, nc=0, conflict=0.0, support=0.0,
                        claims=[], verd={}, empty=True)
        claims = None
        j = "%s/%s_r%d_%s.json" % (OUT, tid, rep, arm)
        if arm.startswith("A5") and os.path.exists(j):
            try:
                d = json.load(open(j, encoding="utf-8"))
                if d.get("claims"):
                    claims = list(d["claims"])
            except Exception:
                pass
        if claims is None:
            claims = extract_claims(judge, txt)
        verd = check_claims(judge, QS[tid], EV.get(tid, ""), claims) if claims else {}
        legal = [c for c in claims if verd.get(c) in ("支持", "矛盾")]
        sup = sum(1 for c in legal if verd.get(c) == "支持")
        con = sum(1 for c in legal if verd.get(c) == "矛盾")
        unt = sum(1 for c in claims if verd.get(c) == "未提及")
        nc = sum(1 for c in claims if verd.get(c) == "非主张")
        dd = dedup_with(emb, claims, 0.75)
        return dict(arm=arm, tid=tid, rep=rep, chars=len(txt), n_raw=len(claims),
                    width=len(dd), sup=sup, con=con, unt=unt, nc=nc,
                    conflict=con / max(len(legal), 1), support=sup / max(len(legal), 1),
                    claims=claims, verd=verd, txt=txt, empty=False)

    jobs = [(a, t, r) for a in ARMS for t in TIDS for r in (1, 2, 3)]
    rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(one, *j): j for j in jobs}
        done = 0
        for f, j in futs.items():
            try:
                rows.append(f.result())
            except Exception as e:
                print("ERR", j, str(e)[:80], flush=True)
            done += 1
            if done % 10 == 0:
                print("  核验 %d/%d" % (done, len(jobs)), flush=True)

    # ---------- 第三步：汇总 ----------
    summary = []
    for a in ARMS:
        rr = [r for r in rows if r["arm"] == a]
        if not rr:
            continue
        per_t = {}
        for t in TIDS:
            sub = [r for r in rr if r["tid"] == t and not r.get("empty")]
            if not sub:
                continue
            allc = []
            for r in sub:
                allc.extend(r.get("claims") or [])
            uni = dedup_with(emb, allc, 0.75) if allc else []
            texts = [r["txt"] for r in sub if r["txt"].strip()]
            disp = None
            if len(texts) >= 2:
                try:
                    V = np.array(emb.embed(texts), dtype=float)
                    V = V / np.clip(np.linalg.norm(V, axis=1, keepdims=True), 1e-9, None)
                    S = V @ V.T
                    ds = [1 - S[i, j] for i in range(len(S)) for j in range(i + 1, len(S))]
                    disp = float(np.mean(ds)) if ds else None
                except Exception:
                    disp = None
            legaln = sum(r["sup"] + r["con"] for r in sub)
            per_t[t] = dict(
                chars=float(np.mean([r["chars"] for r in sub])),
                width=float(np.mean([r["width"] for r in sub])),
                union_width=len(uni),
                n_raw=float(np.mean([r["n_raw"] for r in sub])),
                conflict=(sum(r["con"] for r in sub) / max(legaln, 1)),
                support=(sum(r["sup"] for r in sub) / max(legaln, 1)),
                unt=float(np.mean([r["unt"] for r in sub])),
                nc=float(np.mean([r["nc"] for r in sub])),
                disp=disp, n_legal=legaln,
                per_rep_conflict=[r["conflict"] for r in sub])
        summary.append(dict(arm=a, name=ARM_NAME.get(a, a), per_t=per_t))

    census = dict(judge.model_used)
    json.dump(dict(rows=[{k: v for k, v in r.items() if k != "txt"} for r in rows],
                   summary=summary, judge=orclient.PRIMARY, census=census),
              open("%s/analysis.json" % OUT, "w"), ensure_ascii=False, indent=1, default=str)

    print("\n" + "=" * 112)
    print("交付答案（人工判读用）　判官=%s　embedding=OpenRouter" % orclient.PRIMARY)
    print("=" * 112)
    print("%-28s %7s %7s %7s %9s %9s %8s" %
          ("臂", "字符", "断言数", "去重宽", "矛盾率", "支持率", "离散度"))
    for s in summary:
        pt = s["per_t"]

        def m(k):
            vals = [v[k] for v in pt.values()]
            return sum(vals) / max(len(vals), 1)
        disp = [v["disp"] for v in pt.values() if v.get("disp") is not None]
        print("%-28s %7.0f %7.1f %7.1f %8.1f%% %8.1f%% %8.3f"
              % (s["name"], m("chars"), m("n_raw"), m("width"), 100 * m("conflict"),
                 100 * m("support"), sum(disp) / max(len(disp), 1) if disp else 0))
    for key, ttl in (("union_width", "并集宽度（3 份去重并集）"),
                     ("conflict", "矛盾率（按题）")):
        print("\n%s" % ttl)
        print("%-28s %s" % ("臂", "  ".join("%7s" % t for t in TIDS)))
        for s in summary:
            if key == "conflict":
                cells = "  ".join("%6.0f%%" % (100 * s["per_t"].get(t, {}).get("conflict", 0))
                                  for t in TIDS)
            else:
                cells = "  ".join("%7d" % s["per_t"].get(t, {}).get("union_width", 0) for t in TIDS)
            print("%-28s %s" % (s["name"], cells))
    print("\n【⑤b 学到的策略 vs ⑤c 初始 w=0】")
    for s in summary:
        if s["arm"] in ("A5b", "A5c"):
            per_rep = []
            for t in TIDS:
                per_rep += s["per_t"].get(t, {}).get("per_rep_conflict", []) or []
            sp = np.std(per_rep) if len(per_rep) > 1 else 0
            print("  %-22s 逐份矛盾率均值 %.3f ｜ **种子间标准差 %.3f**"
                  % (s["name"], np.mean(per_rep) if per_rep else 0, sp))
    print("\n模型用量:", json.dumps(census, ensure_ascii=False))
    print("DONE → %s/analysis.json" % OUT)


if __name__ == "__main__":
    main()
'''

# ==================================================================
# smoke_or.py —— 开跑前冒烟
# ==================================================================
FILES["cmp8/smoke_or.py"] = r'''
# -*- coding: utf-8 -*-
"""开跑前冒烟：**任何一项不过就不该开跑**。

1. OpenRouter chat 通不通（grok-3-mini）
2. OpenRouter embedding 通不通、维度多少
3. 判官在 4 个依据包上的自检：真断言该支持、假断言该矛盾
4. MiniMax（被测侧）还活着吗

第 3 项不过 ⇒ 矛盾率不可信 ⇒ 整套实验作废 ⇒ 立刻停。
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from creativity_lab import orclient                       # noqa: E402
from creativity_lab.client import LLM as MM              # noqa: E402
from creativity_lab.verify import check_claims            # noqa: E402

EV = {}
for _i in (1, 2, 3, 4):
    _p = os.path.join(HERE, "creativity_lab", "data", "user4_q%d.json" % _i)
    if os.path.exists(_p):
        EV["A%d" % _i] = json.load(open(_p, encoding="utf-8"))["evidence"]

Q = {
    "A1": "湖北考生，物理类620分，想学AI，应当如何选择大学？",
    "A2": "公路自行车个人比赛（无车队），单圈1.6km共计15圈，单圈由两个800m直路和两个回头弯构成，"
          "本人在大集团里处于中上等水平，该如何安排战术？",
    "A3": "今天是五一小长假的最后一天的18:00，明天就要上学了，我的作业还一笔没动，怎么办？",
    "A4": "这是一份陈会昌气质量表的最终得分：胆汁质-6，多血质23，粘液质-4，抑郁质-1。",
}
T_F = {
    "A1": ("2025年湖北省普通高考首选物理类中，620分及以上的累计人数为7436人",
           "2025年湖北省普通高考首选物理类中，620分及以上的累计人数为74360人"),
    "A2": ("国际自行车联盟（UCI）公路赛规则第 2.3.012 条规定，比赛中任何两名车手之间都可以互相提供食物、饮品、扳手等小帮助",
           "国际自行车联盟（UCI）公路赛规则第 2.3.012 条规定，比赛中任何两名车手之间不得互相提供食物、饮品、扳手等小帮助"),
    "A3": ("番茄工作法由意大利人 Francesco Cirillo 在上世纪八十年代做大学生时用番茄形厨房计时器发展而来",
           "番茄工作法规定每个番茄时段为 50 分钟，之后休息 10 分钟"),
    "A4": ("如果四类得分中有一类得分明显高出其它三种且均高出4分以上，则可定为该类气质型",
           "如果四类得分中有一类得分明显高出其它三种且均高出2分以上，则可定为该类气质型"),
}
fails = []


def main():
    print("=== ① OpenRouter chat (%s) ===" % orclient.PRIMARY, flush=True)
    t0 = time.time()
    o = orclient.LLM()
    r = o.chat("用一句话说明什么是复利", purpose="smoke", max_tokens=300,
               budgets=(600,), min_ok=8)
    print("  → %d 字符，用时 %.1fs：%s" % (len(r), time.time() - t0, (r or "")[:80]), flush=True)
    if len(r) < 8:
        fails.append("OpenRouter chat 无输出")
    print("  模型用量:", o.model_used, flush=True)

    print("=== ② OpenRouter embedding ===", flush=True)
    try:
        vs = o.embed(["湖北620分选AI专业", "620分的湖北考生该选哪所大学"])
        dim = len(vs[0]) if vs and vs[0] else 0
        print("  → %d 条 × %d 维" % (len(vs), dim), flush=True)
        if dim == 0:
            fails.append("OpenRouter embedding 无输出")
    except Exception as e:
        print("  ✗ 失败:", str(e)[:100], flush=True)
        fails.append("OpenRouter embedding 失败: %s" % str(e)[:60])

    print("=== ③ 判官自检（grok）===", flush=True)
    tp = fn = tn = fp = 0
    for tid in ("A1", "A2", "A3", "A4"):
        tt, ff = T_F[tid]
        v = check_claims(o, Q[tid], EV.get(tid, ""), [tt, ff])
        gt, gf = v.get(tt, "解析失败"), v.get(ff, "解析失败")
        ok_t, ok_f = gt == "支持", gf == "矛盾"
        tp += 1 if ok_t else 0
        fn += 0 if ok_t else 1
        tn += 1 if ok_f else 0
        fp += 0 if ok_f else 1
        print("  %s 真→%-4s %s ｜ 假→%-4s %s" % (tid, gt, "✓" if ok_t else "✗",
                                                 gf, "✓" if ok_f else "✗"), flush=True)
    print("  真断言 %d/%d ｜ 假断言 %d/%d" % (tp, tp + fn, tn, tn + fp), flush=True)
    if (tn + fp) and tn / (tn + fp) < 0.5:
        fails.append("判官在已知假断言上召回 <50%（矛盾率不可信）")

    print("=== ④ MiniMax（被测侧）===", flush=True)
    mm = MM()
    r2 = mm.chat("用一句话说明什么是复利", purpose="smoke", max_tokens=300,
                 budgets=(600,), min_ok=8)
    print("  → %d 字符：%s" % (len(r2), (r2 or "")[:60]), flush=True)
    if len(r2) < 8:
        fails.append("MiniMax 无输出")

    print("\n" + ("❌ 冒烟未通过：%s" % "；".join(fails) if fails else "✅ 冒烟全部通过，可以开跑"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
'''

# ==================================================================
# go_cmp8.sh —— 一键编排
# ==================================================================
FILES["cmp8/go_cmp8.sh"] = r'''#!/bin/bash
# 对比实验编排：冒烟 → 跑批 → 跨厂商判官核验 → 判读页
cd "$(dirname "$0")"
export PRIMARY_MODEL="${PRIMARY_MODEL:-MiniMax-M3.1-Flash-Preview}"
export OR_PRIMARY="${OR_PRIMARY:-x-ai/grok-3-mini}"
export OR_BASE_URL="${OR_BASE_URL:-https://openrouter.ai/api/v1}"
export CMP_OUT="${CMP_OUT:-runs/cmp8}"
export ADH_MODE="${ADH_MODE:-repro}"
mkdir -p "$CMP_OUT"

echo "===== 0. 冒烟 ====="
python3 smoke_or.py || { echo "冒烟未过，不开跑"; exit 1; }

echo "===== 1. 跑批（7 臂 × 4 题 × 3 重复）====="
python3 run_compare5.py --arms A1,A2,A3,A4,A5a,A5b,A5c --reps 3 --workers 4

echo "===== 2. 跨厂商判官核验 ====="
python3 analyze_cmp6.py

echo "===== 3. 判读页 ====="
python3 build_compare5_page.py

echo "===== 完成 ====="
echo "对比表在 $CMP_OUT/analysis.json ；判读页在 $CMP_OUT/compare5_report.html"
'''

# ==================================================================
# build_compare5_page.py —— 判读页
# ==================================================================
FILES["cmp8/build_compare5_page.py"] = r'''
# -*- coding: utf-8 -*-
"""生成判读页：7 臂 × 4 题 × 3 重复的原始答案 + 机器指标。

用户是最终裁判（模型自测不能替代人工基准），所以这一页的设计目标是
**让人能逐条看完并下判断**，而不是替用户下结论。
"""
from __future__ import annotations

import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("CMP_OUT", "runs/cmp8")
ARMS = ["A1", "A2", "A3", "A4", "A5a", "A5b", "A5c"]
ARM_NAME = {
    "A1": "① 直调", "A2": "② 开源ADHD项目(机制复现)", "A3": "③ 双轴·融合门",
    "A4": "④ 双轴·去融合门", "A5a": "⑤a 新架构·无核验(控制)",
    "A5b": "⑤b 新架构·学到的策略", "A5c": "⑤c 新架构·初始w=0(控制)",
}
ARM_ROLE = {
    "A1": "基线", "A2": "外部项目（机制复现，非原版本体）", "A3": "旧架构",
    "A4": "旧架构（最强）", "A5a": "控制：隔离「有没有 oracle」",
    "A5b": "主实验", "A5c": "控制：隔离「学到的权重有没有用」",
}
TIDS = ["A1", "A2", "A3", "A4"]
QNAME = {"A1": "湖北620分选AI专业", "A2": "公路赛个人赛战术",
         "A3": "假期最后一天作业没动", "A4": "解读气质量表得分"}


def read(p):
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def main():
    an = json.load(open("%s/analysis.json" % OUT, encoding="utf-8"))
    summ = {s["arm"]: s for s in an["summary"]}
    H = []
    H.append("""<!doctype html><meta charset="utf-8">
<title>五族对比实验 · 用户的四道题</title>
<style>
:root{--bg:#0f1115;--fg:#e6e6e6;--dim:#9aa4b2;--line:#252a33;--acc:#7cc4fa;--warn:#ffb86b;--ok:#7ee787;--card:#161a21}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.75 -apple-system,"PingFang SC","Noto Sans CJK SC",Segoe UI,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:32px 22px 80px}
h1{font-size:25px;margin:0 0 6px}h2{font-size:19px;margin:40px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
h3{font-size:16px;margin:26px 0 10px;color:var(--acc)}
.sub{color:var(--dim);font-size:13.5px;margin-bottom:8px}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:13.5px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:right;vertical-align:top}
th{background:#1b2029;color:var(--dim);font-weight:600;text-align:right}
td:first-child,th:first-child{text-align:left}
tr:hover td{background:#1a1f27}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
.ans{white-space:pre-wrap;font-size:14px;line-height:1.8}
details{border:1px solid var(--line);border-radius:9px;margin:9px 0;background:#12161d}
summary{cursor:pointer;padding:10px 14px;font-size:14px;color:var(--acc);user-select:none}
summary:hover{background:#181d25}
details .inner{padding:4px 16px 14px}
.tag{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:20px;border:1px solid var(--line);color:var(--dim);margin-left:8px}
.tag.main{color:#0f1115;background:var(--ok);border-color:var(--ok)}
.tag.ctrl{color:#0f1115;background:var(--warn);border-color:var(--warn)}
.box{border-left:3px solid var(--acc);background:#141922;padding:12px 16px;margin:14px 0;border-radius:0 8px 8px 0}
.box.warn{border-left-color:var(--warn)}
.kv{font-size:13.5px;color:var(--dim)} .kv b{color:var(--fg)}
pre{background:#0b0e13;border:1px solid var(--line);padding:10px;border-radius:8px;overflow:auto;font-size:12.5px}
</style><div class="wrap">""")
    H.append("<h1>五族对比实验 · 用户的四道题</h1>")
    H.append('<div class="sub">7 臂 × 4 题 × 3 重复 ｜ 每臂用同一模型集、同一判官、同一批依据包 ｜ '
             '判官 = %s（跨厂商）｜ embedding = OpenRouter</div>'
             % an.get("judge", "OpenRouter"))
    H.append('<div class="box warn"><b>臂2 是机制复现</b>（照搬 ADHD 项目的 engine.ts/frames.ts/render.ts，'
             '只换传输层；原版走 claude-agent-sdk 的通道当天挂死）。'
             '<b>最终评分仍由人做</b>：下面的指标只是辅助。</div>')

    H.append("<h2>一、机器指标</h2>")
    H.append('<div class="sub">width=去重后断言数（模型会在一份答案里把同一事实说 3–4 遍，'
             '任何按断言条数算的量都必须先去重）；union=3 份去重并集宽度；'
             '矛盾率=矛盾/(支持+矛盾)——唯一有方差、能当仲裁器的量；离散度=3 份两两语义距离均值</div>')
    H.append("<table><tr><th>臂</th><th>角色</th><th>字符</th><th>去重宽</th><th>并集宽</th>"
             "<th>矛盾率</th><th>支持率</th><th>离散度</th><th>未提及</th></tr>")
    for a in ARMS:
        s = summ.get(a)
        if not s:
            continue
        pt = s["per_t"]

        def m(k):
            vals = [v[k] for v in pt.values()]
            return sum(vals) / max(len(vals), 1)
        disp = [v["disp"] for v in pt.values() if v.get("disp") is not None]
        tag = ('<span class="tag main">主实验</span>' if a == "A5b"
               else ('<span class="tag ctrl">控制</span>' if a in ("A5a", "A5c") else ""))
        H.append("<tr><td>%s%s</td><td style='text-align:left;color:#9aa4b2'>%s</td>"
                 "<td>%.0f</td><td>%.1f</td><td>%.1f</td><td>%.1f%%</td><td>%.1f%%</td>"
                 "<td>%.3f</td><td>%.1f</td></tr>"
                 % (ARM_NAME[a], tag, ARM_ROLE[a], m("chars"), m("width"), m("union_width"),
                    100 * m("conflict"), 100 * m("support"),
                    sum(disp) / max(len(disp), 1) if disp else 0, m("unt")))
    H.append("</table>")

    H.append("<h2>二、逐题</h2>")
    for t in TIDS:
        H.append("<h3>%s（题号 %s）</h3>" % (QNAME[t], t))
        H.append("<table><tr><th>臂</th><th>字符</th><th>去重宽</th><th>并集宽</th>"
                 "<th>矛盾</th><th>支持</th><th>未提及</th><th>非主张</th></tr>")
        for a in ARMS:
            s = summ.get(a, {}).get("per_t", {}).get(t)
            if not s:
                continue
            H.append("<tr><td style='text-align:left'>%s</td><td>%.0f</td><td>%.1f</td><td>%d</td>"
                     "<td>%d</td><td>%d</td><td>%.1f</td><td>%.1f</td></tr>"
                     % (ARM_NAME[a], s["chars"], s["width"], s["union_width"],
                        s["conflict"] * s.get("n_legal", 0), s["support"] * s.get("n_legal", 0),
                        s["unt"], s["nc"]))
        H.append("</table>")

    H.append("<h2>三、原始答案（人工判读）</h2>")
    H.append('<div class="sub">每一格都是模型真实输出。⑤a/b/c 展示的是<b>合成版</b>'
             '（与其它臂同为流式答复）；机械装配版另附在每格末尾。</div>')
    for t in TIDS:
        H.append("<h3>%s</h3>" % QNAME[t])
        for a in ARMS:
            H.append("<details><summary>%s</summary><div class='inner'>" % ARM_NAME[a])
            any_txt = False
            for rep in (1, 2, 3):
                p = "%s/%s_r%d_%s_synth.md" % (OUT, t, rep, a)
                txt = read(p)
                if not txt.strip():
                    txt = read("%s/%s_r%d_%s.md" % (OUT, t, rep, a))
                if not txt.strip():
                    continue
                any_txt = True
                H.append("<div class='card'><div class='kv' style='margin-bottom:6px'>"
                         "<b>重复 %d</b> · %d 字符</div><div class='ans'>%s</div></div>"
                         % (rep, len(txt), html.escape(txt)))
            if not any_txt:
                H.append("<div class='card'><div class='ans' style='color:#ff6b6b'>"
                         "（该臂在此题无输出）</div></div>")
            if a.startswith("A5"):
                mech = read("%s/%s_r%d_%s.md" % (OUT, t, 1, a))
                if mech:
                    H.append("<details><summary>机械装配版（架构原生输出，重复1）</summary>"
                             "<div class='inner'><pre>%s</pre></div></details>"
                             % html.escape(mech[:2500]))
            H.append("</div></details>")
    H.append("</div>")
    open("%s/compare5_report.html" % OUT, "w", encoding="utf-8").write("\n".join(H))
    print("→ %s/compare5_report.html" % OUT)


if __name__ == "__main__":
    main()
'''

# ==================================================================
# runs/arch_learn/result.json —— 学到的策略权重（A5b 臂的命根子）
# ==================================================================
FILES["cmp8/runs/arch_learn/result.json"] = r'''{
 "w": [
  -0.016200537627320113,
  0.009925351042044093,
  0.015447812411331094,
  0.015376806043443974,
  0.006567440208581627,
  0.0,
  -6.6061295517914726e-18,
  0.021944246252025606,
  0.0,
  0.0,
  0.046767314847413824,
  0.016918815741257497,
  0.0,
  0.0
 ],
 "note": "第 5 维 = STOP 的 one-hot；第 6 维 = 深度；第 7 维 = 目标是 CLAIM；第 8/9/10 = 目标已支持/已矛盾/未核验；第 11 = 目标文本长度；第 12/13 = 本分支支持数/失败数。特征与题无关，所以换题换域不用重训。"
}
'''

# ==================================================================
# README.md —— 操作指南
# ==================================================================
FILES["cmp8/README.md"] = r'''# 五族对比实验（用户的四道题）

## 目录
```
cmp8/
├─ creativity_lab/          核心库
│  ├─ client.py             MiniMax 客户端（chat+embed，带过载降级）
│  ├─ metrics.py            _mat / cosine
│  ├─ verify.py             核验器（CHECK4 已泛化到非法律域）
│  ├─ ops.py                操作集 + 图执行器 + 机械装配
│  ├─ orclient.py           OpenRouter 跨厂商判官客户端
│  ├─ learnarch.py          可学习架构的 episode 执行器
│  ├─ adhd_repro.py         ADHD 项目机制复刻（15 帧 + 11 步流水线）
│  └─ data/user4_q{1..4}.json   4 个依据包
├─ armdeps/                 臂3/臂4 用的旧架构代码
│  ├─ client2.py  shared.py  arm3.py
├─ run_compare5.py          7 臂驱动
├─ analyze_cmp6.py          跨厂商判官分析器（自检不过就拒绝出数）
├─ smoke_or.py              冒烟测试
├─ build_compare5_page.py   判读页生成
├─ go_cmp8.sh               一键编排
└─ runs/arch_learn/result.json   学到的策略权重（A5b 用）
```

## 依赖
```bash
pip install numpy
```
（只用标准库 + numpy。没有 requests。）

## 环境变量
```bash
export MINIMAX_SUBSCRIPTION_KEY=<你的 minimax key>
export OPENROUTER_API_KEY=<你的 openrouter key>
export PRIMARY_MODEL=MiniMax-M3.1-Flash-Preview   # M3 当天持续过载(529)，用健康档位
export OR_PRIMARY=x-ai/grok-3-mini               # 最便宜的可用判官
export CMP_OUT=runs/cmp8
export ADH_MODE=repro                            # 臂2 走 Python 复刻
```

## 跑
```bash
# 一步到位
bash go_cmp8.sh

# 或分步（推荐第一次分步，好观察）
python3 smoke_or.py          # 冒烟：不过就别往下跑
python3 run_compare5.py --arms A1,A2,A3,A4,A5a,A5b,A5c --reps 3 --workers 4
python3 analyze_cmp6.py
python3 build_compare5_page.py
```

**耗时**：跑批 1.5–2 小时（7 臂 × 4 题 × 3 重复 ≈ 700 次调用）。
**成本**：被测走 MiniMax 订阅 = $0；OpenRouter 判官 ≈ $0.12，embedding ≈ $0.05。**总计 < $1**。

## 输出
- `runs/cmp8/analysis.json` —— 全部指标（机器可判）
- `runs/cmp8/compare5_report.html` —— **判读页**：每臂每题每重复的原始答案 + 指标
- `runs/cmp8/judge_selfcheck.json` —— 判官自检结果
- `runs/cmp8/runlog.jsonl` —— 每次调用的审计日志

## 臂
| 臂 | 是什么 | 调用数 | 作用 |
|---|---|:-:|---|
| A1 | 直调 | 1 | 基线 |
| A2 | 开源 ADHD 项目（**机制复现**） | 12 | 外部项目对照 |
| A3 | 双轴·**融合门** | 8 | 旧架构 |
| A4 | 双轴·**去融合门** | 6 | 旧架构最强版 |
| A5a | 新架构·**无核验** | ~12 | **控制**：隔离「有没有 oracle」 |
| A5b | 新架构·**学到的策略** | ~14 | **主实验** |
| A5c | 新架构·**初始 w=0** | ~14 | **控制**：隔离「学到的权重有没有用」 |

## 指标口径
- **宽度（去重）**：单份答案去重后的断言数。模型会在一份答案里把同一事实说 3–4 遍，
  所以任何按断言条数算的量都必须先去重。
- **并集宽度**：同臂 3 份去重后的并集 = 覆盖广度。
- **矛盾率**：矛盾 /(支持+矛盾)。**唯一有方差、能当仲裁器的量。**
- **离散度**：3 份之间两两语义距离均值。
- **种子噪声地板**：同臂同题 3 次重复的逐份矛盾率标准差。
  分析器最后会打印它 —— **⑤b 与 ⑤c 的差异若小于这个地板，就是噪声，不是效果。**

## 诚实边界
1. **臂2 是机制复现，不是原版本体**。照搬 `src/engine.ts`（reframe→5帧×6想法→
   score+cluster→deepen top3 = 11 次调用）、`src/packs/core.ts` 的 15 个认知帧、
   `src/render.ts` 的输出形状，**只换传输层**（原版走 claude-agent-sdk，当天挂死）。
   差异：原用 `systemPrompt:{preset:"claude_code"}` 会叠加 Claude Code 自己的系统提示，
   复刻版只注入项目自己的 system prompt。
2. **模型集被固定为 5 个健康档位**（M3.1-Flash-Preview / M2.7 / M2.5 / M2.1 / M2），
   各臂完全一致——因为 M3 当天整片返回 529。
3. **判官是跨厂商的 Grok**，被测是 MiniMax。判官自检不过（已知假断言召回 <50%）
   ⇒ **拒绝出数**。
4. **用户的四道题是外部测试集**，全程未进训练。依据包由子代理联网独立构造，
   **不读任何已有答案**，只收原子事实、不收建议。
5. **最终评分由人做。** 判读页给的是原始答案，指标只是辅助。
'''

for path, content in FILES.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.lstrip("\n"))
    print("   ", path, len(content), "B")
print(">>> part2 完成：驱动 + 臂依赖 + 权重 + 指南")
