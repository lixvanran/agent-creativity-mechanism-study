# -*- coding: utf-8 -*-
"""臂4：去融合门，改选择门。

与臂3 的唯一差异：
  臂3  分支产**判断片段** → 融合门把片段综合成一篇答复
  臂4  分支各自产**完整答复** → 末步只**选**一篇，原样输出，不重写不融合

轴A / 轴B 与臂3 完全一致。
措辞纪律同臂3：不出现评价口径词，不出现题面元素。
"""
import client2 as C
from shared import OUT_SPEC, SELECT_Q
from arm3 import FRAMES, PERSONAS, AXIS_B_MODELS, DIAG


def branch_answers(topic, n=5, workers=1):
    """每支独立写一份完整答复，互不看见。"""
    DIAG.clear()
    arts = []
    for i in range(n):
        fname, fprompt = FRAMES[i]
        p = (f"问题：{topic}\n\n"
             f"你现在从【{fname}】这个认知位置出发去看这个问题。\n{fprompt}\n\n"
             f"设定：{PERSONAS[i]}\n\n"
             f"直接写一份答复。\n"
             f"- 观点明确、承担立场\n"
             f"- 直接回答问题，给出必要依据\n"
             f"- 不要写「未来可期」「机遇与挑战并存」这类空话\n"
             f"- {OUT_SPEC}")
        o = C.chat(p, AXIS_B_MODELS[i], 1.0, 8000, min_ok=120)
        DIAG.append(dict(model=AXIS_B_MODELS[i], frame=fname,
                        ok=bool(o and len(o) >= 120), chars=len(o or "")))
        if o and len(o) >= 120:
            arts.append(o)
    return arts


def select_only(topic, arts):
    """只选不融。选择判据保持任务中性：只问『对提问者最有用』。"""
    if not arts:
        return ""
    if len(arts) == 1:
        return arts[0]
    joined = "\n\n=====\n\n".join(f"[第{i+1}篇]\n{a}" for i, a in enumerate(arts))
    r = C.chat(
        "同一个问题下有若干份**各自独立**写成的答复：\n\n" + joined
        + "\n\n" + SELECT_Q + "\n\n先写 60-120 字说明理由，然后原样贴出被选中那篇。",
        "MiniMax-M3", 1.0, 5000, min_ok=120)
    return r
