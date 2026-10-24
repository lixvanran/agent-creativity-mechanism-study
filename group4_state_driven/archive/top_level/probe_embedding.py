#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax `embo-01` embedding 探针（第四组）。

为什么需要它：MiniMax-M3 **不返回 logprobs**，所以 typicality / NLL / perplexity / PMI
全部算不了；而第四组判据 1 / 3 / 3b / 6（极性位移、塌缩度、臂间距离、状态位移）
全部建立在 **embedding 几何**上。⇒ 这个接口是本轮实验的**命脉**，必须单独探一次。

接口（实测可用；注意是 `type` 而不是 `embed_type`，且 `api.minimax.io` 那个域名
不认这个 key，只有 `api.minimaxi.com` 行）：

    POST https://api.minimaxi.com/v1/embeddings
    {"model": "embo-01", "texts": ["..."], "type": "db"}
    → {"vectors": [[...1536 维...]], "total_tokens": N}

怎么跑
    python3 probe_embedding.py                 # 探 1 次（1 条文本）
    python3 probe_embedding.py --texts 4      # 探 4 条
    python3 probe_embedding.py --selfcheck    # 额外做一次"同文本两次 embedding"的余弦检查
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import cos, embed  # noqa: E402

SAMPLES = [
    "她把笔停在纸上，窗外的雨声没有停。三分钟里她没有说一个字。",
    "The surgeon signed the last form and walked out without looking back.",
    "医保目录调整的谈判室里，桌面上摊着两套测算。",
    "母亲绕远的那条路，经过当年送孩子上学的那个路口。",
]


def main() -> int:
    ap = argparse.ArgumentParser(description="MiniMax embo-01 embedding 探针")
    ap.add_argument("--texts", type=int, default=1, help="探几条文本（默认 1）")
    ap.add_argument("--selfcheck", action="store_true", help="同一文本取两次 embedding，算余弦")
    args = ap.parse_args()

    if not os.environ.get("MINIMAX_SUBSCRIPTION_KEY"):
        print("环境变量 MINIMAX_SUBSCRIPTION_KEY 未设置。", file=sys.stderr)
        return 2

    texts = (SAMPLES * 4)[:max(1, args.texts)]
    t0 = time.time()
    try:
        vecs = embed(texts)
    except Exception as e:
        print("embedding 调用失败：%s" % e, file=sys.stderr)
        print("**失败不算结论**（MiniMax 高负载会返 HTTP 529）。", file=sys.stderr)
        return 1
    dt = time.time() - t0
    print("成功：%d 条，%.1fs" % (len(vecs), dt))
    for t, v in zip(texts, vecs):
        print("  dim=%d  |v|=%.4f  %s" % (len(v), math.sqrt(sum(x * x for x in v)), t[:28]))
    if len(vecs) >= 2:
        print("\n两两余弦（应为 0.3–0.9；接近 1 说明接口在返回常量向量 ⇒ 不可用）：")
        for i in range(min(3, len(vecs))):
            for j in range(i + 1, min(3, len(vecs))):
                print("  cos(%d,%d) = %.4f" % (i, j, cos(vecs[i], vecs[j])))
    if args.selfcheck:
        v2 = embed([texts[0]])
        print("\n同文本两次 embedding 余弦 = %.6f（1.0 = 接口确定性）" % cos(vecs[0], v2[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
