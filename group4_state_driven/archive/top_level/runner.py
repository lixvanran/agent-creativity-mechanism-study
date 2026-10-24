#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
第四组 · 实验原型 runner（Phase 0 最小可运行版）
================================================================================

【这版实现了什么】
  1. 直接打 MiniMax API（urllib.request，无第三方依赖；沙箱里没装 requests）
     · base_url = https://api.minimaxi.com/v1   · model = MiniMax-M3
     · key 从环境变量 MINIMAX_SUBSCRIPTION_KEY 读（不落盘、不进日志）
     · 每次请求都带 thinking: {type: "disabled"}(实测：reasoning_tokens=0、content 非空)
  2. 四个臂各自真实构造提示并调用：
       A 直接调用 / B 弱 role 标签 / C 立场档案（真立场）/ R 随机立场（与题无关）
  3. C / R 的立场档案是 **模型自己生成的**（单独的 API 调用），不是我们写的提示词
  4. 支持 SWAY 式「只翻转预设极性」配对（P+ / P− / P0）
  5. 产出 JSONL（每行含 arm/topic/seed/output/usage/stance_profile），可断点续跑
  6. 成本核算：按 MiniMax M3 官方按量价（≤512K 档）折算 ¥，同时给「五折价」和「标准价」
  7. --dry-run：0 次调用，打印所有将要发出的请求体（用来做人工 review）

【这版没实现什么】
  · 没有 LLM 评委、没有人类盲评、没有 MAUVE、没有 Biber 66 维 —— Phase 0 只出自动指标
  · 没有采样间复跑逻辑的并行化（串行，怕把配额打爆）
  · 没有断点续跑的状态文件（JSONL 本身可续：已存在的 arm/topic/seed/极性组合会跳过）
  · 没有 logit_bias 的验证探针（需要 token id 与平台 tokenizer，缺）
  · 没有温度/方差扫掠（L2 替代方案在设计文档里，未实现为代码）

【已知限制】
  · R 臂的立场来自「同域异题」，天然与本题不适配；R 的不适配是设计特征而非缺陷，
    但它意味着 **不能用 R 的"可读性差"来论证 C 更好**，只能比内容层指标。
  · --pad（长度配平）用的是一段固定「写作工艺说明」，只能把 A/B 的 prompt 长度
    拉近到 C/R 的量级，不能逐 token 等长；残余差异由 analyze.py 报告。
  · 立场档案的 JSON 解析是宽松解析（去围栏 + 抓首个 {...}），可能拿到缺字段的对象；
    analyze.py 会把缺字段标出来，不会静默补默认值。
  · 本文件在会话中已被真实调用验证：3 次探针调用 + 1 次冒烟调用。

================================================================================
怎么跑 / 预计花多少钱与时间
================================================================================
  导出密钥：
      export MINIMAX_SUBSCRIPTION_KEY=sk-xxxx        # 已有环境变量就不用导

  ① 0 成本：先看要发什么（不调用 API）
      python3 runner.py --dry-run

  ② 最小冒烟：1 次调用，确认链路通（推荐第一次跑这个）
      python3 runner.py --smoke
      → 产出 runs/smoke.jsonl，1 次调用，约 ¥0.005，约 15–30 秒

  ③ 默认规模（题目给了 ≤12 次的硬上限）
      python3 runner.py
      → T01 一题 × 4 臂 × 1 seed = 4 次生成 + 2 次立场生成 = 6 次调用
      → 约 ¥0.05，约 2–4 分钟

  ④ Phase 0 建议规模（最省的可行规模，5 题 ≥ benchmark 5 的下限）
      python3 runner.py --scope phase0
      → 5 题 × 4 臂 × 2 seed = 40 次生成 + 10 次立场生成 = 50 次调用
      → 约 ¥0.5（标准价约 ¥1.0），约 15–25 分钟

  ⑤ 完整规模
      python3 runner.py --scope full
      → 10 题 × 4 臂 × 3 seed = 120 次生成 + 20 次立场生成 = 140 次调用
      → 约 ¥1.3（标准价约 ¥2.6），约 45–70 分钟

  ⑥ 加 SWAY 配对（每臂多出 P+ / P− / P0 三版，Phase 1 才需要）
      python3 runner.py --scope phase0 --cf
      → 调用数 ×3

  预算护栏：--max-calls 是硬上限（默认 12），超了直接停，不会偷偷多花。
  断点续跑：同一条 JSONL 重复跑，已有的 (arm, topic, seed, polarity) 会跳过。
================================================================================
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------- 配置
API_URL = "https://api.minimaxi.com/v1/chat/completions"
MODEL = "MiniMax-M3"
KEY_ENV = "MINIMAX_SUBSCRIPTION_KEY"

# MiniMax M3 按量价（≤512K 上下文档），单位：元 / 百万 tokens
# 来源：MiniMax 官方按量计费页（发布期五折价）与标准价两个口径都保留
PRICE_IN_PROMO = 2.10
PRICE_OUT_PROMO = 8.40
PRICE_IN_LIST = 4.20
PRICE_OUT_LIST = 16.80

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"

# ---------------------------------------------------------------- 题目库
# 每道题带 5 类信息：
#   brief   —— 发给模型的题面（体裁/题目/读者/长度）  ← A/B/C/R 拿到的是**同一段**
#   dilemma —— 真实两难（不出现在 brief 里，只写在本文件与设计文档里）
#   link    —— 可被穿透的非显然关联（**不给模型**，是事后评分用的探针来源）
#   axis    —— 方向轴的两极（配对提示与探针评分都用它）
#   pp      —— SWAY 式预设极性对：P+ 预设 pole_a，P− 预设 pole_b，内容不变
#   role    —— B 臂的弱 role 标签（与题目同域，但没有任何立场）
#   rsrc    —— R 臂的立场来源题（同域、异题、张力正交）
#   tension —— 本题的张力标签（用于校验 R 来源题的张力是否正交）

TOPICS = [
    {
        "id": "T01",
        "title": "医保谈判现场",
        "genre": "现实主义短篇小说片段（约 1200 字）",
        "audience": "《收获》风格的读者",
        "length": "1200 字左右",
        "brief": (
            "写一个现实主义短篇小说片段。场景：医保目录调整的谈判室。一个医保谈判代表必须在两小时内"
            "说服厂家把一款罕见病药降价 60%，否则患者明年全部自费。她自己三年前也是靠这款药活下来的，"
            "而她的孩子正在同一家公司做研发。故事停在她做出决定的那一刻之前。"
        ),
        "dilemma": "她要争取的是别人的命，而降价会威胁自己孩子的工作；两条都是她真实承担的东西。",
        "link": (
            "降价的真正变量不是药，而是医保基金明年的结余结构；她孩子所在的岗位恰好在仿制药专利到期的"
            "竞标线上——降价 60% 与这家公司是否活下来，是同一件事。只有同时承担'我欠这份药'和'我不能毁掉"
            "孩子'的人才会去找这个连接。"
        ),
        "axis": {
            "pole_a": "降价的压力来自医保基金的结余结构（外部结构决定）",
            "pole_b": "降价的压力来自谈判者个人的恩义（私人情感决定）",
        },
        "pp": {
            "P+": "背景：读者已经知道，这场谈判的真正压力不在药厂愿不愿意让利，而在医保基金明年的结余结构。",
            "P-": "背景：读者仍然以为，这场谈判的真正问题只是药厂该不该为了患者多让一点利。",
        },
        "role": "你是一个在行业里跑了十二年的医保政策记者。",
        "rsrc": "R01",
        "tension": "私人恩义/结构约束",
    },
    {
        "id": "T02",
        "title": "双向抽佣",
        "genre": "观点短文（800 字，财经媒体专栏体）",
        "audience": "关心商业与公共政策的城市读者",
        "length": "800 字左右",
        "brief": (
            "写一篇 800 字左右的观点短文。议题：外卖平台是否应当被允许对同一笔订单同时向商家和骑手"
            "收取佣金。写给一个既不骑手也不开店、但天天点外卖的读者。不要写成论文，不要罗列数据。"
        ),
        "dilemma": "效率与议价权的分配：多收一笔钱可能降低总成本，也可能把成本转嫁给最没有退出权的一方。",
        "link": (
            "双向抽佣的真正博弈不在平台和商家之间，而在骑手：平台向骑手收费，会通过'单均配送时长'这条"
            "约束把成本推回商家，商家再压价给骑手——抽佣结构是同一个三角形的三个内角，而'多接单补偿'"
            "会反向加大骑手承担的成本。不穿透这一层，多数人会答成'平台该不该抽两遍钱'。"
        ),
        "axis": {
            "pole_a": "成本是在平台/商家/骑手三角内被转移（结构性）",
            "pole_b": "成本就是多付了一笔佣金（账面性）",
        },
        "pp": {
            "P+": "背景：读者已经知道，双向抽佣的真正成本会通过'单均配送时长'这条约束绕回到商家身上。",
            "P-": "背景：读者仍然以为，双向抽佣的真正成本只是平台多收一笔钱、商家多让一点利。",
        },
        "role": "你是一个长期跑消费与平台经济的财经记者。",
        "rsrc": "R02",
        "tension": "效率/公平",
    },
    {
        "id": "T03",
        "title": "散步路线",
        "genre": "歌曲歌词（主歌两段 + 副歌一段）",
        "audience": "听民谣与city pop的听众",
        "length": "歌词，含两段主歌与一段副歌",
        "brief": (
            "写一首歌的歌词：主歌两段、副歌一段。主题是一位母亲在丈夫确诊阿尔茨海默后，仍然每天下午"
            "带他散步。不要出现'疾病'二字，不要煽情，不要写'我会照顾你'这类承诺句。"
        ),
        "dilemma": "温柔的记叙 vs 无法粉饰的疲惫；歌要么骗人，要么太沉。",
        # 修正记录（2026-10-20）：原 link/axis/pp 写的是"儿子当年上学的路""替孩子保存"，与题面
        # （母亲带确诊阿尔茨海默的丈夫散步）自相矛盾——连接不成立。题目/体裁/人物/两难一律不动，
        # 只把连接改成与"丈夫"一致且更可穿透的版本（见 deliverable.md §1.3）。
        "link": (
            "散步的路线不是随机的：母亲每天绕远的那条路，恰好经过两人当年送孩子上学的那个路口。"
            "丈夫的病正在吃掉他的记忆，走到那里他会问'这是哪'——绕远，是母亲用体力换来的一个"
            "不用回答'这是哪'的早晨。不同立场会选出完全不同的细节（路口/扶手/药盒/电梯口）。"
        ),
        "axis": {
            "pole_a": "那条路线是母亲为丈夫省下的一个不必承认失语的早晨（体面性）",
            "pole_b": "那条路线只是习惯或复健的一部分（功能性）",
        },
        "pp": {
            "P+": "背景：读者已经知道，母亲每天绕远的那条路，恰好经过两人当年送孩子上学的那个路口——他每次走到那里都会问'这是哪'。",
            "P-": "背景：读者仍然以为，母亲每天散步只是因为坚持某种习惯。",
        },
        "role": "你是一个写过很多城市民谣的词作者。",
        "rsrc": "R03",
        "tension": "记忆/遗忘",
    },
    {
        "id": "T04",
        "title": "关门返乡",
        "genre": "散文（1000 字）",
        "audience": "《单读》式的读者",
        "length": "1000 字左右",
        "brief": (
            "写一篇 1000 字左右的散文。主角 45 岁，在县城经营一家殡仪店，十几年没离开过；现在要关门，"
            "带着老婆孩子返乡。不要写成'小城青年'式的怀旧，不要用'时代洪流'这类词。"
        ),
        "dilemma": "这篇散文到底该是关于尊严的，还是关于被时代抛下的？两种写法都成立，取舍不同。",
        "link": (
            "这家店近十年最稳定的客源，来自火化政策变化后涌入的外地客户——也就是说他的'体面收入'来自一项"
            "他自己也不认同的政策红利。返乡不是失败，是把一个说不出口的手艺带回不需要它的家。"
        ),
        "axis": {
            "pole_a": "他的体面收入来自他自己也不认同的政策红利（道德性）",
            "pole_b": "他的体面来自这门手艺本身（技艺性）",
        },
        "pp": {
            "P+": "背景：读者已经知道，这家殡仪店近十年最稳定的客源，来自他自己也不认同的一项政策变化。",
            "P-": "背景：读者仍然以为，殡仪店是一门被时代淘汰的手艺。",
        },
        "role": "你是一个写了二十年非虚构的专栏作家。",
        "rsrc": "R04",
        "tension": "尊严/生计",
    },
    {
        "id": "T05",
        "title": "争取试点",
        "genre": "商务邮件（300 字，创业公司联合创始人发给医院信息科主任）",
        "audience": "一位谨慎的医院信息科主任",
        "length": "300 字左右",
        "brief": (
            "写一封 300 字左右的商务邮件。发件人是一家做 AI 病历摘要创业公司的联合创始人，"
            "收件人是某三甲医院信息科主任。目的是争取一个为期半年的院内试点。不要写产品介绍式的罗列，"
            "不要写'赋能'这类词。"
        ),
        "dilemma": "产品要数据，医院怕担责——两者的诉求真实冲突，而邮件必须同时推进两件相反的事。",
        "link": (
            "试点真正的卡点不是准确率，是'谁签字'：医疗责任落在医生身上，所以医院要的不是更强的模型，"
            "而是一个把责任移交给机器的合同结构。只谈准确率的创业者会被主任直接忽略。"
        ),
        "axis": {
            "pole_a": "卡点是责任的签字与合同结构（制度性）",
            "pole_b": "卡点是技术的准确率（技术性）",
        },
        "pp": {
            "P+": "背景：读者已经知道，医院真正卡住的不是准确率，而是'谁签字'——责任落在医生身上。",
            "P-": "背景：读者仍然以为，医院拒绝试点只是因为对新工具不信任。",
        },
        "role": "你是一个做过十二年医疗信息化售前的客户经理。",
        "rsrc": "R05",
        "tension": "责任/免责",
    },
    {
        "id": "T06",
        "title": "葬礼上读的悼词",
        "genre": "悼词（400 字，由女儿在父亲葬礼上宣读）",
        "audience": "前来送葬的亲友",
        "length": "400 字左右",
        "brief": (
            "写一段 400 字左右的悼词，由女儿在父亲的葬礼上宣读。父亲与女儿决裂三年，最后也没有和好。"
            "不要写成和解的故事，不要出现'在天之灵'。"
        ),
        "dilemma": "诚实 vs 抚慰：悼词天然是要抚慰的，但女儿有权不原谅，而且她大概不想撒谎。",
        "link": (
            "女儿坚持在葬礼上读这篇悼词，本身就是最后一次裁决——悼词里每一个肯定句都在替父亲认错，"
            "而不是在纪念他。这两件事只有在承认'女儿有资格不原谅'的前提下才不冲突。"
        ),
        "axis": {
            "pole_a": "悼词是女儿替父亲做的最后一次裁决（裁决性）",
            "pole_b": "悼词只是对父亲的追忆（纪念性）",
        },
        "pp": {
            "P+": "背景：读者已经知道，女儿坚持在葬礼上读这篇悼词，是在替父亲完成一次他始终没做的认错。",
            "P-": "背景：读者仍然以为，这只是一篇追忆父亲的悼词。",
        },
        "role": "你是一个写过很多人物特稿的记者。",
        "rsrc": "R06",
        "tension": "忠诚/背叛",
    },
    {
        "id": "T07",
        "title": "谁为 bug 负责",
        "genre": "科普小品（1200 字，面向理工科背景但非专业的读者）",
        "audience": "关心技术与法律的普通读者",
        "length": "1200 字左右",
        "brief": (
            "写一篇 1200 字左右的科普小品，解释：当 AI 生成的代码出了 bug，程序员要不要负责。"
            "可以有比喻，可以有例子，但不要写成法律意见书，也不要罗列各国条文。"
        ),
        "dilemma": "责任归属的技术现实 vs 法律现实，两者目前对不上。",
        "link": (
            "责任不按'谁写出了代码'划分，而按'谁有能力在交付前发现它、并承担不发现的后果'划分。AI 把'写'"
            "变便宜了，但'验收'没有变便宜，所以责任会向验收方移动。多数人会答成'程序员因为审阅所以要负责'，"
            "这不完整。"
        ),
        "axis": {
            "pole_a": "责任向'有能力发现并承担后果'的验收方移动（能力论）",
            "pole_b": "责任仍在'写下并提交代码'的那个人（作者论）",
        },
        "pp": {
            "P+": "背景：读者已经知道，责任不会跟着'写作变便宜'一起变便宜，它会向'验收方'移动。",
            "P-": "背景：读者仍然以为，程序员该为 AI 生成的代码负责，是因为代码是他'提交'的。",
        },
        "role": "你是一个做过十年技术科普的编辑。",
        "rsrc": "R07",
        "tension": "权力/责任",
    },
    {
        "id": "T08",
        "title": "葬礼上的那句话",
        "genre": "微信对话（8–12 条，气泡形式）",
        "audience": "当事人自己",
        "length": "8 到 12 条气泡",
        "brief": (
            "写一段 8 到 12 条的微信对话。场景：朋友的父亲葬礼上，朋友当着作者的面说，"
            "当年是作者的一句话让她活下来的。作者既感激，又愤怒——两样都是真的，且无法调和。"
            "不要让任何一方把话说完。"
        ),
        "dilemma": "把对方的话当作救助（进入感激框架）还是当作规训（进入被规训框架）；进入哪个框架决定了整段关系的走向。",
        "link": (
            "这句话的功能由它出现的时刻决定：在葬礼上说出来，接受感激的代价被抬到最高（你怎么能在这种时候"
            "计较）。所以'愤怒'不是不识好歹，而是唯一能保住这段关系剩余部分的东西。"
        ),
        "axis": {
            "pole_a": "愤怒是保住这段关系剩余部分的必要条件（关系性）",
            "pole_b": "愤怒是不知好歹（道德性）",
        },
        "pp": {
            "P+": "背景：读者已经知道，这句话被选在葬礼上说出口，恰好把接受感激的代价抬到了最高。",
            "P-": "背景：读者仍然以为，朋友说这句话只是为了报恩。",
        },
        "role": "你是一个擅长写双人对话的编剧。",
        "rsrc": "R08",
        "tension": "亲密/边界",
    },
    {
        "id": "T09",
        "title": "图书馆的预算",
        "genre": "决策说明（600 字，提交给馆务会）",
        "audience": "区级图书馆馆务会成员",
        "length": "600 字左右",
        "brief": (
            "写一份 600 字左右的决策说明，提交给区图书馆馆务会。议题：有限的一笔预算，是扩大儿童绘本区，"
            "还是建一个安静自习区（现有读者中备考者占六成）。不要罗列优劣清单，要给一个明确建议。"
        ),
        "dilemma": "面向少数的公平 vs 面向多数的需求；两个选项都正当。",
        "link": (
            "两者争夺的其实是同一个资源——空间与安静；而且绘本区会吃掉自习区的家长陪同需求。真正的判据不是"
            "'这块地属于谁'，而是'这块地在下午四点到九点属于谁'——这是时间分配问题，不是空间分配问题。"
        ),
        "axis": {
            "pole_a": "争的是同一块地在不同时钟的归属（时空性）",
            "pole_b": "争的是'儿童优先'与'备考优先'的价值排序（价值性）",
        },
        "pp": {
            "P+": "背景：读者已经知道，绘本区和自习区真正争的是同一块地在不同钟点的归属。",
            "P-": "背景：读者仍然以为，这是'儿童优先'还是'备考优先'的价值排序之争。",
        },
        "role": "你是一个在公共文化机构做了十多年行政的人。",
        "rsrc": "R09",
        "tension": "公平/效率",
    },
    {
        "id": "T10",
        "title": "带班岗自述",
        "genre": "求职自述（800 字，应聘殡葬服务公司的带班岗）",
        "audience": "人力资源负责人",
        "length": "800 字左右",
        "brief": (
            "写一段 800 字左右的求职自述。应聘者 28 岁，连续三年被裁员，最后在殡仪馆做了一年半殡葬师，"
            "现在应聘同一家殡葬服务公司的带班岗。不要写成励志故事，不要美化失业经历。"
        ),
        "dilemma": "诚实地讲三年失业史 vs 保住求职时的尊严；两种写法都有代价。",
        "link": (
            "在殡葬行业里'流动'是常态，他那三年被裁员的经历与这行的文化是同源的——他的'黑历史'和'专业性'"
            "来自同一个文化。只寻找'连续性'叙事的 HR 会被这个反套路打动。"
        ),
        "axis": {
            "pole_a": "空窗期与行业文化同源，可以被翻译（可转化性）",
            "pole_b": "空窗期是简历上洗不掉的污点（污点论）",
        },
        "pp": {
            "P+": "背景：读者已经知道，在殡葬行业里'流动'是常态，他那三年被裁员的经历与这行的文化是同源的。",
            "P-": "背景：读者仍然以为，简历上的三段空窗期只会让他被直接淘汰。",
        },
        "role": "你是一个做过十年招聘的 HR。",
        "rsrc": "R10",
        "tension": "尊严/生计",
    },
]

# R 臂的立场来源题池（**扩到 10 条，与 TOPICS 一一对应**）
# 这些题**只**用来生成立位档案，作品本身永远不会被要求写它们。
# 每条都带完整三件套：brief / dilemma / axis（立场档案生成需要"两难"与"两端"）。
#
# ⚠️ 张力正交由代码强制断言（见 canonical_tension / pick_r_source）：
#    `R_POOL[src]["tension"]` 必须与目标题 `tension` 正交（两侧排序后比较，
#    避免 "效率/公平" 与 "公平/效率" 被误判为不同）。不满足就换来源并记录。
R_POOL = {
    "R01": {
        "genre": "调查报道（1200 字）",
        "audience": "关心医保与药价问题的城市读者",
        "length": "1200 字左右",
        "title": "药进了目录，却没进病房",
        "brief": "某种罕见病药已经进了医保目录，进了之后患者仍然负担不起——因为限定适应症、"
                 "因为医院药房不配、因为要去特药药房自费。写一段调查见闻。",
        "dilemma": "是让药进目录（哪怕很多人用不上），还是承认它在现实里到不了病人手里。",
        "axis": {
            "pole_a": "进目录本身就是进展，哪怕当下覆盖率低（形式性）",
            "pole_b": "进目录而到不了人手里，等于没进（实效性）",
        },
        "tension": "承诺/执行",
    },
    "R02": {
        "genre": "观点短文（800 字，财经媒体专栏体）",
        "audience": "关心平台经济与劳动保障的读者",
        "length": "800 字左右",
        "title": "骑手的保险该由平台统一买吗",
        "brief": "外卖平台开始统一为骑手购买商业意外险，费用从每单抽成里扣。写一段关于这件事的观察。",
        "dilemma": "平台统一投保降低了单个骑手的一次意外风险，但成本被摊到所有骑手身上。",
        "axis": {
            "pole_a": "统一投保是平台本来就该负的责任（责任论）",
            "pole_b": "统一投保是平台把自己的成本转嫁给了骑手（转嫁论）",
        },
        "tension": "雇佣/保障",
    },
    "R03": {
        "genre": "纪实特写（1000 字）",
        "audience": "关心失智照护的读者",
        "length": "1000 字左右",
        "title": "要不要告诉失智的父亲他曾经的工作",
        "brief": "父亲确诊阿尔茨海默后，仍然每天问起自己退休了二十年的工作。家人每次都告诉他'你在家休息'。",
        "dilemma": "继续骗他让他安心，还是告诉他真相让他痛苦。",
        "axis": {
            "pole_a": "重复告知是必要的确认，不是欺骗（必要性）",
            "pole_b": "重复告知是温柔的欺骗（欺骗性）",
        },
        "tension": "诚实/保护",
    },
    "R04": {
        "genre": "人物特写（1000 字）",
        "audience": "关心手艺与年轻一代选择的读者",
        "length": "1000 字左右",
        "title": "手艺人该不该把手艺传给孩子",
        "brief": "一位修表师傅的儿子在城里做设计，不愿意回镇上接他的手艺行当。写一段关于这件事的记录。",
        "dilemma": "把手艺传下去是手艺的保存；不传是孩子的自由。",
        "axis": {
            "pole_a": "不传是对手艺本身的不尊重（保存论）",
            "pole_b": "不传是对孩子选择的尊重（自由论）",
        },
        "tension": "传承/自由",
    },
    "R05": {
        "genre": "决策简报（600 字，提交给采购会）",
        "audience": "医院设备采购负责人",
        "length": "600 字左右",
        "title": "医院设备采购要不要接受厂商免费赠送",
        "brief": "一家三甲医院被多家医疗器械厂商提出免费赠送设备，条件是设备进院后优先采用该厂商的耗材。",
        "dilemma": "白拿设备能省预算，但会把未来的采购和耗材一起绑死。",
        "axis": {
            "pole_a": "免费赠送是以长期绑定换短期让利（绑定性）",
            "pole_b": "设备本身没有错，绑定才是问题（分离性）",
        },
        "tension": "利益/合规",
    },
    "R06": {
        "genre": "散文（1000 字）",
        "audience": "《单读》式的读者",
        "length": "1000 字左右",
        "title": "要不要把母亲的遗物原样留着",
        "brief": "父亲去世后，母亲把她用了几十年的搪瓷杯、账本、旧毛衣一件不少地留着，家里已经放不下了。",
        "dilemma": "留着是纪念，放下是继续生活。",
        "axis": {
            "pole_a": "留着是给她留了一个位置（位置性）",
            "pole_b": "留着是父亲不肯走出来的借口（停滞性）",
        },
        "tension": "保存/放下",
    },
    "R07": {
        "genre": "科普小品（1200 字，面向理工科背景但非专业的读者）",
        "audience": "关心技术与法律的普通读者",
        "length": "1200 字左右",
        "title": "维护者要不要为不属于自己的模块背锅",
        "brief": "一个开源项目的核心模块由一位长期维护者承担，出问题时用户追问的是'项目'，"
                 "而能改这段代码的只有他。",
        "dilemma": "维护者该不该为整个项目负责，包括他没写的那部分。",
        "axis": {
            "pole_a": "维护者该为整个项目负责（整体性）",
            "pole_b": "维护者只对他写的和接手的部分负责（边界性）",
        },
        "tension": "范围/义务",
    },
    "R08": {
        "genre": "纪实特写（900 字）",
        "audience": "关心家庭关系与边界的读者",
        "length": "900 字左右",
        "title": "要不要在朋友圈屏蔽父母",
        "brief": "一个三十岁的人把父母从自己的朋友圈里屏蔽了，只在家庭群里说话。写一段记录。",
        "dilemma": "屏蔽是保护自己的边界，还是切断一种联系。",
        "axis": {
            "pole_a": "屏蔽是在保护还能继续说话的那部分关系（保护性）",
            "pole_b": "屏蔽是在把父母排除在自己的生活之外（排除性）",
        },
        "tension": "联系/隐私",
    },
    "R09": {
        "genre": "观点短文（800 字）",
        "audience": "关心小区治理与业主权益的读者",
        "length": "800 字左右",
        "title": "停车位该归业主还是先到先得",
        "brief": "一个小区把一部分地面停车位改成公共收费停车场，业主抱怨'我们买的车位反而比外来的车难停'。",
        "dilemma": "车位是业主的财产，还是社区的公共资源。",
        "axis": {
            "pole_a": "车位首先是业主的财产（私有性）",
            "pole_b": "车位首先是公共资源的使用问题（公共性）",
        },
        "tension": "公共/私有",
    },
    "R10": {
        "genre": "人物特写（1000 字）",
        "audience": "关心小厂与老员工处境的读者",
        "length": "1000 字左右",
        "title": "要不要接住一个可能被裁的老同事",
        "brief": "一家小厂准备裁掉一位跟了老板十二年的老同事，老板在考虑要不要自己扛下他的工资。",
        "dilemma": "扛下来是情义，扛下来也是风险。",
        "axis": {
            "pole_a": "扛下来是把十二年的情义一次性结清（结清性）",
            "pole_b": "扛下来是让一个快倒的厂多背一个人的重量（承担性）",
        },
        "tension": "情义/风险",
    },
}

# ---------------------------------------------------------------- 提示构造
NEUTRAL_CRAFT = (
    "【写作工艺说明】\n"
    "· 句子长短交替，允许有一处不解释的停顿。\n"
    "· 只写你确定的东西；不确定的地方就让它不确定，不要用概括性的词把它盖住。\n"
    "· 不要用'总而言之''在这个时代''不仅……而且……'这类套话。\n"
    "· 写完检查一遍：有没有哪句话是你自己也不相信的，有就删掉或改掉。\n"
    "· 直接输出作品正文。"
)

STATE_HEADER = "【内在状态 · 持续在场】"
STATE_FOOTER = (
    "【本状态影响本次写作的唯一方式】\n"
    "· 不要在正文里复述上面任何一条，也不要出现'我的立场是''我认为'这类声明。\n"
    "· 让这些约束通过'你选择写什么、不写什么、按什么顺序写'体现出来。\n"
    "· 如果某条约束在本任务里无法被满足，不要假装它不存在：写出一个具体的、有代价的折中，并说明代价是什么。\n"
    "· 直接输出作品正文。"
)

STANCE_FIELDS = [
    # ★ 防伪 ②（测量方案裁决 §2.2）：模型必须**自选**极性，且只能二选一。
    #   测量时按 self_polarity 做符号对齐：δ_aligned = δ * (+1 if pole_a else -1)
    ("自选极性", "只能是 pole_a 或 pole_b，二选一，不许写'两者兼顾''都要''看情况'。"),
    ("立场核心", "一句话，可被反驳。必须落在你自选的那一端上，是对本题中某个具体取舍的判断；"
                "不能是'要平衡''要重视'这类无立场的话。"),
    ("选它的理由", "为什么是这一端而不是另一端：一到两句，必须针对本题的具体代价，不得空谈。"),
    ("来历", "一个具体事件，含时间、地点和一个可追问的细节。说明你为什么会持有这个立场。"),
    ("取舍约束", "恰好 3 条'不能牺牲'的东西。每条写'不能牺牲什么'，不要写'必须说什么'。"),
    ("拒绝", "这条立场拒绝做什么、不肯接受什么结果。"),
    ("语气", "克制的、什么程度的语气。"),
    ("强度封顶", "在什么条件下这条立场会被推翻。必须是本题里真实可能发生的条件。"),
    ("锚定问题", "这条立场能回答、而一个没有立场的通用回答答不出的那一个问题。"),
]

POLE_NAMES = ("pole_a", "pole_b")

STANCE_PROMPT_TMPL = """你现在要为下面这道写作题生成一份「立场档案」。
这份档案将由写作者自己承担，并贯穿整个写作过程；它不是给别人看的说明。

题目：{title}
体裁：{genre}
读者：{audience}
长度：{length}
要求：{brief}

这道题的两难：{dilemma}

两难的两端（你**必须**在两端里选一端，不许骑墙）：
· pole_a —— {pole_a}
· pole_b —— {pole_b}

【档案必须包含 9 项，字段名照抄】
{fields}
{forced_block}【硬性要求】
· "自选极性"只能填 "pole_a" 或 "pole_b"，必须是这两个字符串之一。
· 立场核心必须是一个可以被反驳的判断，并且它必须在本题里做出取舍。
· 取舍约束写的是"不能牺牲"，不是"必须说什么"。
· 强度必须封顶：第 8 项写明的条件下，你的立场会被推翻。不得写成不可证伪的绝对立场。
· 不要写"既要……又要……""要平衡各方"这类没有取舍的话。
· 只输出一个 JSON 对象，不要输出 JSON 以外的任何文字、不要用代码围栏。
· **"取舍约束"必须是 JSON 数组**，形如 ["不能牺牲甲", "不能牺牲乙", "不能牺牲丙"]，
  恰好 3 个元素；不要写成"甲","乙","丙"这样缺括号的写法。
· 整个输出必须能被 JSON.parse 直接解析：所有键和值用英文双引号包裹，键不重复，
  数组带方括号，字符串内部的引号要转义。
"""

# R1（同题·反极性·强度相当）的强制对照块。
# 目的：让 R1 与 C 臂在**题面/模板/强度/结构**上完全相同，只翻转"站在哪一极"，
#      从而把"极性"与"强度"两个混淆从 C vs R 的比较里排除出去。
FORCED_POLE_BLOCK = """【本次对照要求（必须遵守）】
· 另一个人会在这道题上持有 {other_pole} 这一端：{other_pole_text}
  你要持有的是 {forced_pole} 这一端：{forced_pole_text}
· 你的立场强度必须与该端的标准强度相当——同样具体、同样有来历、同样不可轻易推翻、
  同样不许和稀泥。不要用"温和一点""留有余地""双方都有道理"来降低强度。
· "自选极性"必须填 "{forced_pole}"。
"""


def forced_block(forced_pole: str | None) -> str:
    if not forced_pole:
        return ""
    other = opposite_pole(forced_pole)
    return FORCED_POLE_BLOCK


def opposite_pole(pole: str) -> str:
    return "pole_b" if pole == "pole_a" else "pole_a"

def topic_as_src(topic: dict) -> dict:
    """把一道题转成"立场档案生成源"（只含题面 + 两难 + 两端；**不含 pp**）。"""
    return {
        "title": topic["title"],
        "genre": topic["genre"],
        "audience": topic["audience"],
        "length": topic["length"],
        "brief": topic["brief"],
        "dilemma": topic["dilemma"],
        "axis": topic["axis"],
    }


def stance_prompt(src_topic: dict, forced_pole: str | None = None) -> str:
    """生成立场档案提示。

    ⚠️ 防伪 ①：本题的 `pp`（P+/P− 极性陈述）**绝不**进入这个提示。
       否则测到的是"档案里的极性被复述到输出"，不是"状态组织了取舍"。
       下面的 assert_no_polarity_leak 在运行时强制这一点。
    """
    fields = "\n".join("%d. %s —— %s" % (i + 1, k, d) for i, (k, d) in enumerate(STANCE_FIELDS))
    axis = src_topic["axis"]
    fb = ""
    if forced_pole:
        other = opposite_pole(forced_pole)
        fb = FORCED_POLE_BLOCK.format(
            forced_pole=forced_pole,
            forced_pole_text=axis[forced_pole],
            other_pole=other,
            other_pole_text=axis[other],
        )
    return STANCE_PROMPT_TMPL.format(
        title=src_topic["title"], genre=src_topic["genre"],
        audience=src_topic["audience"], length=src_topic["length"],
        brief=src_topic["brief"], dilemma=src_topic["dilemma"],
        pole_a=axis["pole_a"], pole_b=axis["pole_b"],
        fields=fields, forced_block=fb,
    )


def assert_no_polarity_leak(prompt: str, topic: dict) -> None:
    """防伪 ① 的运行时断言：立场档案提示里不得出现 P+/P− 极性陈述句。"""
    for pol in ("P+", "P-"):
        s = (topic.get("pp") or {}).get(pol, "")
        if s and s in prompt:
            raise AssertionError("立场档案提示泄漏了 %s 极性陈述：%s" % (pol, s[:40]))


def canonical_tension(tension: str) -> frozenset:
    """把 '效率/公平' 与 '公平/效率' 归一成同一个集合（避免正交校验被绕过）。"""
    return frozenset(p.strip() for p in str(tension).split("/") if p.strip())


def pick_r_source(topic: dict) -> tuple:
    """挑一个与目标题**张力正交**的 R 来源题（Bug 5：不再是注释里的口号）。

    优先用题目**指定**的 rsrc（10 题 ↔ 10 条的一一对应，是人为挑过的对照设计），
    只有当它张力不正交时才回退到扫描 —— 保证"每次跑到的 R 来源题"稳定可复现。
    """
    t = canonical_tension(topic["tension"])
    designated = topic.get("rsrc")
    if designated in R_POOL and canonical_tension(R_POOL[designated]["tension"]) != t:
        return designated, R_POOL[designated]
    cands = [(k, v) for k, v in R_POOL.items()
             if canonical_tension(v["tension"]) != t]
    if not cands:
        raise ValueError("R_POOL 里没有与 %s 张力正交的来源题" % topic["id"])
    cands.sort(key=lambda kv: kv[0])
    return cands[0]


def topic_brief(topic: dict) -> str:
    return (
        "题目：%s\n体裁：%s\n读者：%s\n长度：%s\n要求：%s\n直接输出作品正文。"
        % (topic["title"], topic["genre"], topic["audience"], topic["length"], topic["brief"])
    )


def state_block(stance: dict) -> str:
    lines = [STATE_HEADER]
    for k, _ in STANCE_FIELDS:
        v = stance.get(k)
        if isinstance(v, list):
            v = "；".join(str(x) for x in v)
        lines.append("【%s】%s" % (k, v if v else "（缺失）"))
    lines.append(STATE_FOOTER)
    return "\n".join(lines)


def state_chars(stance: dict) -> int:
    """状态块注入的实际字数（用于长度配平分析）。"""
    n = 0
    for k, _ in STANCE_FIELDS:
        v = stance.get(k)
        if isinstance(v, list):
            v = "；".join(str(x) for x in v)
        n += len(str(v or ""))
    return n


def system_chars(messages: list) -> int:
    return sum(len(m.get("content") or "") for m in messages if m.get("role") == "system")


def build_messages(arm: str, topic: dict, stance: dict | None, polarity: str, pad: bool) -> list:
    """构造某个臂的 messages。brief 部分在所有臂之间逐字相同。"""
    brief = topic_brief(topic)
    if polarity in ("P+", "P-"):
        brief = brief + "\n" + topic["pp"][polarity]

    if arm == "A":
        sys = "你是一个写作助手。" + ("\n\n" + NEUTRAL_CRAFT if pad else "")
        return [{"role": "system", "content": sys}, {"role": "user", "content": brief}]

    if arm == "B":
        sys = topic["role"] + ("\n\n" + NEUTRAL_CRAFT if pad else "")
        return [{"role": "system", "content": sys}, {"role": "user", "content": brief}]

    if arm in ("C", "R1", "R2"):
        sys = "你是一个写作助手。\n\n" + state_block(stance or {})
        return [{"role": "system", "content": sys}, {"role": "user", "content": brief}]

    raise ValueError("unknown arm: %r" % arm)


# ---------------------------------------------------------------- API 层
class MiniMaxError(RuntimeError):
    pass


def _post(payload: dict, timeout: int, retries: int = 5) -> dict:
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise MiniMaxError(
            "环境变量 %s 未设置。先 export %s=<your key>" % (KEY_ENV, KEY_ENV))
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            API_URL, data=data,
            headers={"Authorization": "Bearer %s" % key,
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:400]
            last = "HTTP %d: %s" % (e.code, body)
            if e.code in (400, 401, 403, 404):
                break  # 参数/鉴权类错误，重试没有意义
            if e.code == 429:
                # ★ 速率限制：必须**长退避**。
                #   通用退避是 2/4 秒（2**attempt），对 Token Plan 限流远远不够
                #   ⇒ Phase 1 实测并发 8 时 36 次调用整片失败
                #   （"已达到 Token Plan 速率限制"）⇒ 退避基数提到 20s。
                time.sleep(20 * (attempt + 1))
                continue
        except Exception as e:  # 网络抖动、超时
            last = "%s: %s" % (type(e).__name__, e)
        if attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))
    raise MiniMaxError("API 调用失败：%s" % last)


def chat(messages: list, max_tokens: int = 1600, temperature: float = 1.0,
         timeout: int = 180, extra: dict | None = None) -> tuple:
    """返回 (content, usage, latency_s, raw_choice)。"""
    payload = {
        "model": MODEL,
        "thinking": {"type": "disabled"},   # 用户硬规则：结构化输出必须关 thinking
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if extra:
        payload.update(extra)
    t0 = time.time()
    raw = _post(payload, timeout=timeout)
    dt = time.time() - t0
    ch = (raw.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    content = msg.get("content") or ""
    if not content.strip():
        raise MiniMaxError(
            "返回 content 为空（finish_reason=%s, usage=%s）。检查 max_tokens 是否被 reasoning 吃光。"
            % (ch.get("finish_reason"), raw.get("usage")))
    return content, raw.get("usage") or {}, dt, ch


# ---------------------------------------------------------------- 立场档案解析
def parse_stance(text: str) -> dict:
    """宽松解析：去围栏 → 抓第一个 {...} → 尝试 json.loads。失败返回带 error 的 dict。"""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()
    start = t.find("{")
    if start < 0:
        return {"_error": "no_json_object", "_raw": text[:2000]}
    depth = 0
    end = -1
    in_str = False
    esc = False
    for i in range(start, len(t)):
        c = t[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        return {"_error": "unbalanced_json", "_raw": text[:2000]}
    blob = t[start:end]
    try:
        obj = json.loads(blob)
    except Exception as e:
        # ⚠️ 实测：模型会输出**伪 JSON**（数组少方括号 / 键重复 / 末尾缺右括号）。
        #    直接判死会让整轮数据作废 ⇒ 走兜底抽取器，尽量把字段捞出来。
        out = _salvage_fields(blob)
        out["_raw"] = blob[:4000]
        out["_error"] = "json_decode:%s" % e
        out["_parsed"] = "salvage"
        return _finalize_stance(out)
    if not isinstance(obj, dict):
        return {"_error": "not_an_object", "_raw": blob[:2000]}
    out = {}
    for k, _ in STANCE_FIELDS:
        for cand in (k, k.encode("utf-8").decode("utf-8")):
            if cand in obj:
                out[k] = obj[cand]
                break
    out["_raw"] = blob
    missing = [k for k, _ in STANCE_FIELDS if k not in out]
    if missing:
        out["_missing"] = missing
    # ★ 防伪 ②：自选极性必须严格是 pole_a / pole_b，否则该档案判为无效
    pol = out.get("自选极性")
    if isinstance(pol, str):
        pol = pol.strip().strip("\"'").lower()
        if pol in ("pole_a", "a", "极a", "a端"):
            pol = "pole_a"
        elif pol in ("pole_b", "b", "极b", "b端"):
            pol = "pole_b"
    if pol not in POLE_NAMES:
        out["_invalid_polarity"] = str(out.get("自选极性"))[:60]
        out["self_polarity"] = None
    else:
        out["self_polarity"] = pol
    return out


def _read_json_string(text: str, i: int):
    """从 text[i]（应是 '"'）开始读一个 JSON 字符串，返回 (值, 下一个位置)。"""
    if i >= len(text) or text[i] != '"':
        return None, i
    i += 1
    buf = []
    while i < len(text):
        c = text[i]
        if c == "\\":
            if i + 1 < len(text):
                buf.append(text[i + 1])
                i += 2
                continue
            i += 1
            continue
        if c == '"':
            return "".join(buf), i + 1
        buf.append(c)
        i += 1
    return "".join(buf), i


def _salvage_fields(blob: str) -> dict:
    """从**伪 JSON**里逐字段抽取（实测场景：数组缺方括号、键重复、末尾缺右括号）。

    做法：对每个字段名找 `"字段"\s*:\s*`，然后按值的形态取值：
      · '[' → 平衡括号截取，json.loads
      · '{' → 平衡括号截取，json.loads（失败就当字符串）
      · '"' → 读 JSON 字符串；**若后面紧跟 `","`**，说明这是"缺括号的数组"，
        继续读并合成列表（这正是实测踩到的坑）
    """
    out = {}
    for k, _ in STANCE_FIELDS:
        m = re.search(r'"%s"\s*:\s*' % re.escape(k), blob)
        if not m:
            continue
        i = m.end()
        if i >= len(blob):
            continue
        c = blob[i]
        if c == "[":
            depth, j = 0, i
            while j < len(blob):
                if blob[j] == "[":
                    depth += 1
                elif blob[j] == "]":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            try:
                out[k] = json.loads(blob[i:j])
            except Exception:
                out[k] = blob[i + 1:j - 1] if j > i else ""
        elif c == "{":
            depth, j = 0, i
            while j < len(blob):
                if blob[j] == "{":
                    depth += 1
                elif blob[j] == "}":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            try:
                out[k] = json.loads(blob[i:j])
            except Exception:
                out[k] = blob[i:j]
        elif c == '"':
            val, j = _read_json_string(blob, i)
            # 缺括号的数组：`"a","b","c"`
            items = [val] if val is not None else []
            # 缺括号的数组有三种写法：`"a","b"` / `","` 链 / `, "b"`
            while j < len(blob):
                if blob[j:j + 3] == '","':
                    j += 2
                elif blob[j:j + 2] == ',"':
                    j += 1
                else:
                    break
                if j < len(blob) and blob[j] == '"':
                    v2, j2 = _read_json_string(blob, j)
                    if v2 is None:
                        break
                    # 下一个是**键**（后面跟着 ':'）⇒ 数组到此为止（实测：伪 JSON 里
                    # `"约束1","约束2","拒绝":"拒绝……"` 会把键吞进数组）
                    if blob[j2:j2 + 1] == ":":
                        break
                    items.append(v2)
                    j = j2
                else:
                    break
            out[k] = items if len(items) > 1 else items[0]
    return out


def _finalize_stance(out: dict) -> dict:
    """统一收尾：补 _missing、校验自选极性。

    ★ 兜底抽取**成功**（字段齐全 + 极性合法）时，清掉 _error —— 否则档案会被误判作废，
      实测这是"模型输出伪 JSON"场景下的必要容错（记 _salvaged 以留痕）。
    """
    missing = [k for k, _ in STANCE_FIELDS if k not in out or out.get(k) in (None, "", [])]
    if missing:
        out["_missing"] = missing
    pol = out.get("自选极性")
    if isinstance(pol, str):
        pol = pol.strip().strip("\"'").lower()
        if pol in ("pole_a", "a", "极a", "a端"):
            pol = "pole_a"
        elif pol in ("pole_b", "b", "极b", "b端"):
            pol = "pole_b"
    if pol not in POLE_NAMES:
        out["_invalid_polarity"] = str(out.get("自选极性"))[:60]
        out["self_polarity"] = None
    else:
        out["self_polarity"] = pol
    if (not missing) and out.get("self_polarity") and out.get("_error"):
        out.pop("_error")
        out["_salvaged"] = True
    return out


def stance_valid(st: dict) -> bool:
    """档案有效性闸门（F14）：缺字段 / 解析错误 / 极性无效 ⇒ 不可用于生成。"""
    if not st:
        return False
    if st.get("_error"):
        return False
    if st.get("_missing"):
        return False
    if st.get("self_polarity") not in POLE_NAMES:
        return False
    return True


# ---------------------------------------------------------------- 运行
def load_state(path: Path) -> tuple:
    """读回已有记录。

    ★ Bug 3 修复：立场档案**也**进断点续跑。
      同题同臂只生成一次档案，跨 seed / 跨极性（P0/P+/P−）复用同一份，
      采样间差异里才**不含"档案本身的采样噪声"**。
      （MiniMax 无 seed，temp=0 也非确定 ⇒ 档案重生成会把"换了状态"混进"采样方差"。）

    返回 (已完成的 gen 键集合, {(topic_id, arm): stance_profile})。
    """
    done, stances = set(), {}
    if not path.exists():
        return done, stances
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("error"):
            continue
        if r.get("kind") == "stance":
            sp = r.get("stance_profile")
            if sp:
                stances[(r.get("topic_id"), r.get("arm"))] = sp
        else:
            done.add((r.get("arm"), r.get("topic_id"), r.get("seed"), r.get("polarity")))
    return done, stances


def normalize_arm(a: str) -> str:
    """臂名归一：R 是 R2 的兼容别名。"""
    a = a.strip().upper()
    return "R2" if a == "R" else a


def main() -> int:
    ap = argparse.ArgumentParser(
        description="第四组 Phase 0 runner（MiniMax-M3 / 五臂 / 立场档案）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--scope", choices=["smoke", "default", "phase0", "full"],
                    default="default",
                    help="规模：smoke=1题1样本 / default=T01 1样本 / phase0=5题2样本 / full=10题3样本")
    ap.add_argument("--topics", default="", help="逗号分隔的题目 id，如 T01,T05")
    ap.add_argument("--seeds", default="",
                    help="采样编号，逗号分隔，如 1,2,3。**不是** API seed：MiniMax 不支持 seed，"
                         "temp=0 也不确定，编号仅作独立样本的标签")
    ap.add_argument("--arms", default="A,B,C,R1,R2",
                    help="逗号分隔的臂：A 基线 / B role 标签 / C 立场档案 / R1 同题反极性 / R2 异题立场"
                         "（R 是 R2 的别名）")
    ap.add_argument("--cf", action="store_true", help="加 SWAY 配对：P+ / P-（再加 P0）")
    ap.add_argument("--no-pad", dest="pad", action="store_false",
                    help="不给 A/B 臂加长度配平文本（默认加）")
    ap.add_argument("--out", default="", help="输出 JSONL 路径，默认 runs/phase0.jsonl")
    ap.add_argument("--max-calls", type=int, default=12, help="硬性调用上限（默认 12）")
    ap.add_argument("--max-tokens", type=int, default=1800, help="单次作品生成的 max_tokens")
    ap.add_argument("--stance-max-tokens", type=int, default=1400,
                    help="立场档案 JSON 的 max_tokens（9 字段，900 会截断）")
    ap.add_argument("--temperature", type=float, default=1.0,
                    help="**所有臂必须一致**（预注册：不得让某臂温度更低）")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--dry-run", action="store_true", help="只打印请求体，不调用 API")
    ap.add_argument("--smoke", action="store_true", help="= --scope smoke")
    args = ap.parse_args()

    if args.smoke:
        args.scope = "smoke"

    by_id = {t["id"]: t for t in TOPICS}
    arms = [normalize_arm(a) for a in args.arms.split(",") if a.strip()]
    for a in arms:
        if a not in ("A", "B", "C", "R1", "R2"):
            print("未知臂: %s（可用: A,B,C,R1,R2）" % a, file=sys.stderr)
            return 2
    if not arms:
        print("--arms 为空", file=sys.stderr)
        return 2

    # --- 规模 -> (题目列表, 采样编号列表)
    if args.scope == "smoke":
        tids, samples = ["T01"], [1]
    elif args.scope == "default":
        tids, samples = ["T01"], [1]
    elif args.scope == "phase0":
        tids, samples = [t["id"] for t in TOPICS[:5]], [1, 2]
    else:
        tids, samples = [t["id"] for t in TOPICS], [1, 2, 3]
    if args.topics:
        tids = [x.strip() for x in args.topics.split(",") if x.strip()]
    if args.seeds:
        samples = [int(x) for x in args.seeds.split(",") if x.strip()]
    bad = [t for t in tids if t not in by_id]
    if bad:
        print("未知题目 id: %s（可用: %s）" % (bad, ",".join(by_id)), file=sys.stderr)
        return 2

    RUNS.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else (
        RUNS / ("smoke.jsonl" if args.scope == "smoke" else "phase0.jsonl"))
    out_path = out_path if out_path.is_absolute() else (HERE / out_path)

    # --- 调用计划：**先立场档案，后作品**
    # 顺序原因：R1（同题反极性）必须先知道 C 臂自选了哪一极，才能强制它站到对面。
    stance_plan = []
    gen_plan = []
    for tid in tids:
        topic = by_id[tid]
        if "C" in arms or "R1" in arms:
            stance_plan.append({"kind": "stance", "arm": "C", "topic_id": tid, "src": topic_as_src(topic),
                                "src_kind": "本题"})
        if "R1" in arms:
            stance_plan.append({"kind": "stance", "arm": "R1", "topic_id": tid, "src": topic_as_src(topic),
                                "src_kind": "本题·强制反极性", "depends_on": "C"})
        if "R2" in arms:
            key, rsrc = pick_r_source(topic)
            stance_plan.append({"kind": "stance", "arm": "R2", "topic_id": tid, "src": topic_as_src(rsrc),
                                "src_kind": "同域异题：%s" % rsrc["title"], "rsrc_key": key})
        for arm in arms:
            for s in samples:
                for pol in (["P0", "P+", "P-"] if args.cf else ["P0"]):
                    gen_plan.append({"kind": "gen", "arm": arm, "topic_id": tid,
                                     "seed": s, "polarity": pol})
    plan = stance_plan + gen_plan

    if args.dry_run:
        print("=" * 72)
        print("DRY RUN —— 不会发出任何请求")
        print("=" * 72)
        print("题目: %s   臂: %s   采样编号: %s   配对: %s"
              % (",".join(tids), ",".join(arms), samples, "开" if args.cf else "关"))
        print("计划调用数: %d（其中立场档案 %d、作品 %d）  (上限 --max-calls=%d)\n"
              % (len(plan), len(stance_plan), len(gen_plan), args.max_calls))
        stances = {}
        for i, p in enumerate(plan):
            if p["kind"] != "stance":
                st = stances.get((p["topic_id"], p["arm"]))
                msgs = build_messages(p["arm"], by_id[p["topic_id"]], st, p["polarity"], args.pad)
                print("--- [%d/%d] 生成作品  arm=%s topic=%s 样本=%s 极性=%s"
                      % (i + 1, len(plan), p["arm"], p["topic_id"], p["seed"], p["polarity"]))
                for m in msgs:
                    print("    [%s] %s" % (m["role"], m["content"][:600].replace("\n", "\n    ")))
                if p["arm"] in ("C", "R1", "R2") and st is None:
                    print("    (立场档案此时还没生成，dry-run 里显示的是占位块)")
                print()
                continue
            forced = None
            if p["arm"] == "R1":
                forced = "<执行时由 C 臂档案的 self_polarity 决定>"
            print("--- [%d/%d] 生成立场档案  arm=%s topic=%s  来源: %s"
                  % (i + 1, len(plan), p["arm"], p["topic_id"], p["src_kind"]))
            if p["arm"] == "R1":
                print("    (强制极性: %s —— 执行时用 C 臂档案的 self_polarity 决定；"
                      "下面的对照块会随之填入)" % forced)
                blk = FORCED_POLE_BLOCK.format(
                    forced_pole="<执行时确定>", forced_pole_text="<执行时确定>",
                    other_pole="<执行时确定>", other_pole_text="<执行时确定>")
                print("    对照块: %s" % blk.replace("\n", "\n    "))
            prompt = stance_prompt(p["src"], None)
            # 防伪 ① 的静态检查：本题的 pp 不得出现在立场档案提示里
            try:
                assert_no_polarity_leak(prompt, by_id[p["topic_id"]])
                print("    [防伪①检查] 通过：提示中不含 P+/P- 极性陈述")
            except AssertionError as e:
                print("    [防伪①检查] 失败：%s" % e)
            print("    user: %s" % prompt.replace("\n", "\n    "))
            print()
        return 0

    # --- 真实执行
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        print("环境变量 %s 未设置，无法调用 API。" % KEY_ENV, file=sys.stderr)
        return 2

    done, stances = load_state(out_path)
    if stances:
        print("[resume] 复用已存在的立场档案 %d 份：%s"
              % (len(stances), sorted({k[0] + "/" + k[1] for k in stances})))
    fh = out_path.open("a", encoding="utf-8")
    n_calls = 0
    tok_in = tok_out = 0
    n_err = 0
    n_stance = 0
    n_retry = 0
    n_stance_invalid = 0
    t_start = time.time()
    # ★ 批次约束（主控实测）：embedding 的绝对距离跨题差 10 倍、**跨批差 3.9 倍**
    #   ⇒ 只有**同批内**的相对比较有效 ⇒ 每条记录写 batch_id，analyze.py 检查跨批。
    batch_id = time.strftime("%Y%m%d-%H%M%S") + "-%d" % os.getpid()
    print("[batch] batch_id=%s（**所有臂必须在同一批内跑完**）" % batch_id)

    def emit(rec: dict):
        nonlocal tok_in, tok_out
        u = rec.get("usage") or {}
        tok_in += int(u.get("prompt_tokens") or 0)
        tok_out += int(u.get("completion_tokens") or 0)
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()

    def guard_calls() -> bool:
        return n_calls < args.max_calls

    try:
        # ---------- 第一段：立场档案（每个 (题, 臂) 只生成一次）
        for p in stance_plan:
            tid = p["topic_id"]
            if (tid, p["arm"]) in stances:
                continue
            if not guard_calls():
                print("[stop] 达到 --max-calls=%d，剩余立场档案未生成" % args.max_calls)
                break
            topic = by_id[tid]
            forced = None
            if p["arm"] == "R1":
                c_st = stances.get((tid, "C"))
                c_pol = (c_st or {}).get("self_polarity")
                if not c_pol:
                    print("[skip] R1/%s：C 臂档案缺失或自选极性无效，无法确定对照极性" % tid)
                    continue
                forced = opposite_pole(c_pol)
            prompt = stance_prompt(p["src"], forced)
            # 防伪 ① 运行时断言
            assert_no_polarity_leak(prompt, topic)
            n_calls += 1
            tag = "[%d/%d call=%d]" % (len(plan), len(plan), n_calls)
            try:
                content, usage, dt, _ = chat(
                    [{"role": "user", "content": prompt}],
                    max_tokens=args.stance_max_tokens,
                    temperature=args.temperature, timeout=args.timeout)
                st = parse_stance(content)
                # 解析失败 ⇒ **重试一次**（追加纠正指令）。实测：模型会输出伪 JSON。
                if not stance_valid(st):
                    retry_prompt = (prompt + "\n\n【纠正】你上一次的输出无法被 JSON.parse 解析"
                                    "（常见原因：取舍约束写成了\"甲\",\"乙\",\"丙\"这样缺方括号、"
                                    "或键名重复）。请重新输出一个**严格合法**的 JSON 对象："
                                    "所有键和值用英文双引号，\"取舍约束\"用带方括号的数组，键不重复，"
                                    "对象以外不要有任何字符。")
                    print("%s 档案不可用（%s），重试一次" % (tag, st.get("_error") or st.get("_missing")))
                    if guard_calls():
                        n_calls += 1
                        content2, usage2, dt2, _ = chat(
                            [{"role": "user", "content": retry_prompt}],
                            max_tokens=args.stance_max_tokens,
                            temperature=args.temperature, timeout=args.timeout)
                        st2 = parse_stance(content2)
                        if stance_valid(st2):
                            content, usage, dt, st = content2, usage2, dt2, st2
                            n_retry += 1
                    if not stance_valid(st):
                        print("%s ⚠️ 档案仍不可用：%s / 缺字段 %s / 极性 %s"
                              % (tag, st.get("_error"), st.get("_missing"), st.get("self_polarity")),
                              file=sys.stderr)
                stances[(tid, p["arm"])] = st
                n_stance += 1
                emit({
                    "ts": time.time(), "batch_id": batch_id,
                    "kind": "stance", "arm": p["arm"],
                    "topic_id": tid, "seed": None, "polarity": None,
                    "model": MODEL, "stance_source": p["src"]["title"],
                    "stance_source_kind": p["src_kind"],
                    "forced_polarity": forced,
                    "self_polarity": st.get("self_polarity"),
                    "stance_profile": st, "output": content,
                    "stance_chars": state_chars(st),
                    "usage": usage, "latency_s": round(dt, 2),
                })
                miss = st.get("_missing")
                bad_pol = st.get("_invalid_polarity")
                print("%s stance arm=%s topic=%s 极性=%s  %.1fs  %s%s"
                      % (tag, p["arm"], tid, st.get("self_polarity"), dt,
                         "OK" if not miss else "缺字段 %s" % miss,
                         "" if not bad_pol else "  ⚠️自选极性无效: %s" % bad_pol))
            except MiniMaxError as e:
                n_err += 1
                print("%s 失败: %s" % (tag, e), file=sys.stderr)
                emit({
                    "ts": time.time(), "kind": "stance", "arm": p["arm"],
                    "topic_id": tid, "seed": None, "polarity": None, "model": MODEL,
                    "output": "", "error": str(e)[:500], "usage": {}, "latency_s": 0,
                })

        # ---------- 第二段：作品生成
        for i, p in enumerate(gen_plan):
            if not guard_calls():
                print("[stop] 达到 --max-calls=%d，剩余 %d 个生成未执行"
                      % (args.max_calls, len(gen_plan) - i))
                break
            topic = by_id[p["topic_id"]]
            key_tuple = (p["arm"], p["topic_id"], p.get("seed"), p.get("polarity"))
            if key_tuple in done:
                continue
            st = stances.get((p["topic_id"], p["arm"]))
            if p["arm"] in ("C", "R1", "R2") and not stance_valid(st):
                # ★ F14 闸门：**绝不用残缺档案生成作品**（那会静默污染数据）
                n_stance_invalid += 1
                print("[skip] %s/%s：立场档案不可用（缺失/解析错误/极性无效）——该 (题,臂) 数据作废"
                      % (p["arm"], p["topic_id"]), file=sys.stderr)
                continue
            n_calls += 1
            tag = "[%d/%d call=%d]" % (i + 1, len(plan), n_calls)
            try:
                msgs = build_messages(p["arm"], topic, st, p["polarity"], args.pad)
                content, usage, dt, _ = chat(
                    msgs, max_tokens=args.max_tokens,
                    temperature=args.temperature, timeout=args.timeout)
                emit({
                    "ts": time.time(), "batch_id": batch_id,
                    "kind": "gen", "arm": p["arm"],
                    "topic_id": p["topic_id"], "topic_title": topic["title"],
                    "genre": topic["genre"], "seed": p["seed"],
                    "polarity": p["polarity"], "model": MODEL,
                    "stance_profile": st,
                    "self_polarity": (st or {}).get("self_polarity"),
                    "stance_chars": state_chars(st) if st else 0,
                    "system_chars": system_chars(msgs),
                    "user_chars": sum(len(m.get("content") or "") for m in msgs
                                      if m.get("role") == "user"),
                    "output": content, "output_chars": len(content),
                    "usage": usage, "latency_s": round(dt, 2),
                    "sys_sha256": hashlib.sha256(
                        json.dumps([m for m in msgs if m["role"] == "system"],
                                   ensure_ascii=False).encode()).hexdigest()[:16],
                    "user_sha256": hashlib.sha256(
                        json.dumps([m for m in msgs if m["role"] == "user"],
                                   ensure_ascii=False).encode()).hexdigest()[:16],
                    "prompt_sha256": hashlib.sha256(
                        json.dumps(msgs, ensure_ascii=False).encode()).hexdigest()[:16],
                })
                print("%s gen   arm=%s topic=%s 样本=%s %s  %.1fs  out=%d字  in=%s out_tok=%s"
                      % (tag, p["arm"], p["topic_id"], p["seed"], p["polarity"], dt,
                         len(content), (usage or {}).get("prompt_tokens"),
                         (usage or {}).get("completion_tokens")))
            except MiniMaxError as e:
                n_err += 1
                print("%s 失败: %s" % (tag, e), file=sys.stderr)
                emit({
                    "ts": time.time(), "kind": p["kind"], "arm": p["arm"],
                    "topic_id": p["topic_id"], "seed": p.get("seed"),
                    "polarity": p.get("polarity"), "model": MODEL,
                    "output": "", "error": str(e)[:500],
                    "usage": {}, "latency_s": 0,
                })
    finally:
        fh.close()

    dt_total = time.time() - t_start
    cost_promo = (tok_in / 1e6) * PRICE_IN_PROMO + (tok_out / 1e6) * PRICE_OUT_PROMO
    cost_list = (tok_in / 1e6) * PRICE_IN_LIST + (tok_out / 1e6) * PRICE_OUT_LIST
    cost = {
        "calls": n_calls, "errors": n_err, "stance_calls": n_stance,
        "stance_retries": n_retry, "stance_invalid": n_stance_invalid,
        "prompt_tokens": tok_in, "completion_tokens": tok_out,
        "cost_cny_promo": round(cost_promo, 4),
        "cost_cny_list": round(cost_list, 4),
        "price_note": "M3 ≤512K 档：五折价 输入¥2.10/百万 输出¥8.40/百万；标准价 ¥4.20/¥16.80",
        "wall_time_s": round(dt_total, 1),
        "model": MODEL,
        "note": "MiniMax 无 seed / temp=0 非确定 ⇒ 采样数 N 需按检出力定，重复采样是设计的一部分",
    }
    (RUNS / "cost.json").write_text(
        json.dumps(cost, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 72)
    print("完成：调用 %d 次（立场 %d，失败 %d）  用时 %.1f 分钟"
          % (n_calls, n_stance, n_err, dt_total / 60))
    print("tokens: in=%d out=%d   成本: ¥%.4f（五折）/ ¥%.4f（标准）"
          % (tok_in, tok_out, cost_promo, cost_list))
    print("输出: %s" % out_path)
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
