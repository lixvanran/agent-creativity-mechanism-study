#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""造一份**合成**运行数据（不含任何真实 API 调用），用来验证 analyze.py 的
PL / SC / 判据 / 报告全链路。合成数据仅供自检，**不得**当实验结果。

用法：python3 _selftest_analyze.py
"""
import json
import math
import random
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "runs_selftest"
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True, exist_ok=True)

rng = random.Random(7)

TOPICS = ["T%02d" % i for i in range(1, 11)]
ARMS = ["A", "B", "C", "R1", "R2"]
POLS = ["P0", "P+", "P-"]

POS = "基金 结余 统筹 盘子 预算 结构 责任 签字 合同 验收 手续 流程 规定 条款 窗口 期数 名单 账目 记录 结算 单据 条款 方案 指标 口径 阈值 区间 概率 风险 覆盖 比例 额度 指标 审批 签字 档案 记录 归档"
NEG = "恩情 亏欠 良心 人情 报答 私交 恻隐 旧情 体面 手艺 习惯 复健 追忆 纪念 温暖 从前 骄傲 童��� 喜欢 难受 舍不得 舍不得 无奈 认命 认了 算了 放弃 撒手"
NEUTRAL = "她 走 坐 站 门 窗 光 雨 街 车 药 水 饭 桌 电话 声音 时间 眼睛 手 孩子 医院 公司 主任 朋友 母亲 父亲 一天 两年 三年"


def sentence(rng, pool, k=3):
    return "，".join(rng.sample(pool, k)) + "。"


def gen_text(rng, bias):
    """bias ∈ [-1,1]：-1 偏 P−，+1 偏 P+。"""
    n = rng.randint(8, 14)
    out = []
    for _ in range(n):
        p = rng.random()
        if p < 0.45:
            pool = POS if bias > 0 else NEG
        elif p < 0.7:
            pool = NEUTRAL
        else:
            pool = POS if bias < 0 else NEG
        out.append(sentence(rng, pool, rng.randint(2, 4)))
    return "".join(out)


def embed(text, bias):
    """合成 embedding：主方向 = bias 轴，噪声 = 文本长度与随机。"""
    d = 32
    v = [0.0] * d
    for i in range(d):
        v[i] = rng.gauss(0, 1)
    n = math.sqrt(sum(x * x for x in v))
    v = [x / n for x in v]
    v[0] += 0.8 * bias          # 极性方向
    v[1] += 0.05 * len(text) / 100.0
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


records, stances, embs = [], [], {}

for tid in TOPICS:
    for arm in ARMS:
        if arm in ("C", "R1", "R2"):
            pol = "pole_a" if arm != "R1" else "pole_b"
            st = {"自选极性": pol, "立场核心": "核心判断", "选它的理由": "理由",
                  "来历": "三年前的一个具体事件", "取舍约束": ["不能牺牲体面", "不能牺牲孩子的机会", "不能牺牲自己的清白"],
                  "拒绝": "拒绝把责任推给流程", "语气": "克制", "强度封顶": "当条件改变时",
                  "锚定问题": "谁签字", "self_polarity": pol}
            stances.append({"ts": 1.0, "kind": "stance", "arm": arm, "topic_id": tid,
                            "seed": None, "polarity": None, "model": "MiniMax-M3",
                            "stance_profile": st, "output": json.dumps(st, ensure_ascii=False),
                            "stance_chars": 320, "usage": {"prompt_tokens": 700, "completion_tokens": 600}})
    for arm in ARMS:
        for seed in (1, 2, 3):
            for pol in POLS:
                if arm == "A":
                    base = rng.gauss(0, 0.12)
                elif arm == "C":
                    base = 0.45 if pol == "P+" else (-0.15 if pol == "P-" else 0.15)
                elif arm == "R1":
                    base = -0.40 if pol == "P+" else (0.10 if pol == "P-" else -0.15)
                else:
                    base = rng.gauss(0, 0.12)
                text = gen_text(rng, base)
                key = "%s|%s|%s|%s" % (arm, tid, seed, pol)
                rec = {"ts": 1.0, "kind": "gen", "arm": arm, "topic_id": tid, "seed": seed,
                       "polarity": pol, "model": "MiniMax-M3",
                       "output": text, "output_chars": len(text),
                       "system_chars": 500 if arm in ("C", "R1", "R2") else 180,
                       "stance_chars": 320 if arm in ("C", "R1", "R2") else 0,
                       "self_polarity": ("pole_a" if arm == "C" else
                                         "pole_b" if arm == "R1" else
                                         "pole_a" if arm == "R2" else None),
                       "usage": {"prompt_tokens": 1000, "completion_tokens": 1300}}
                records.append(rec)
                embs[key] = embed(text, base)

with (OUT / "selftest.jsonl").open("w", encoding="utf-8") as fh:
    for r in stances + records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
(OUT / "embeddings.json").write_text(json.dumps(embs, ensure_ascii=False), encoding="utf-8")
print("合成数据已生成：%d 立场 + %d 产出 -> %s" % (len(stances), len(records), OUT))
print("⚠️ 合成数据仅用于自检 analyze.py 的代码路径，**不是实验结果**。")
