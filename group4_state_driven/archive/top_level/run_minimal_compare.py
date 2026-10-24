#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极简对照：只输入一句话，二者输出。

★ 唯一输入（逐字，别的什么都没有）：
    你如何看待高考英语作文？写成一篇文章。

两臂：
  A      —— 直接调用 LLM（一条 user 消息，**无 system**）
  WF     —— 新工作流（第四组状态机骨架）：
              ① 立场步  从这句话生成"写作时要守住的取舍"（不注入任何手写题库内容）
              ② 写作步  用这句话 + 取舍约束写初稿
              ③ 转移步  看初稿 → 新的取舍约束 + 已排除选项
              ④ 终稿步  用这句话 + 新约束 + 初稿写终稿

★ 与第四组原 C2 臂的差别（必须知道）：
  原 C2 依赖题库里的 `dilemma` 与 `pole_a/pole_b`（**手写的两难两端**）来生成
  9 字段立场档案。本脚本**去掉了它们** —— 立场与取舍**全部由模型从那一句自己推出**。
  ⇒ 所以这是"机制本体"，不是"带手写题库装饰的 C2"。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

QUESTION = "你如何看待高考英语作文？写成一篇文章。"

# ---------------------------------------------------------------- 传输层
def chat(messages, model, base, key_env, max_tokens=4000, temperature=1.0, json_mode=False):
    import urllib.request
    import urllib.error
    key = os.environ.get(key_env, "").strip()
    if not key:
        raise RuntimeError("环境变量 %s 未设置" % key_env)
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last = None
    for attempt in range(4):
        req = urllib.request.Request(
            base + "/chat/completions", data=data,
            headers={"Authorization": "Bearer %s" % key,
                     "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=240) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            ch = d["choices"][0]
            c = (ch.get("message") or {}).get("content") or ""
            if c.strip():
                return c
            last = "empty content (finish=%s)" % ch.get("finish_reason")
        except urllib.error.HTTPError as e:
            last = "HTTP %d: %s" % (e.code, e.read().decode("utf-8", "replace")[:200])
            if e.code in (400, 401, 403, 404, 422):
                break
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError("调用失败：%s" % last)


def strip_think(raw):
    t1 = re.compile(r"<think>.*?</think>", re.S)
    t2 = re.compile(r"^.*?</think>", re.S)
    return t2.sub("", t1.sub("", raw or "")).strip()


def loose_json(raw):
    s = strip_think(raw).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    for o, c in (("[", "]"), ("{", "}")):
        i = s.find(o)
        if i < 0:
            continue
        d = False
        for j in range(i, len(s)):
            if s[j] == c:
                d = True
            if d and s[j] == c:
                try:
                    return json.loads(s[i:j + 1])
                except Exception:
                    break
            if s[j] == c:
                d = False
    # 括号配平扫描
    for o, c in (("[", "]"), ("{", "}")):
        i = s.find(o)
        if i < 0:
            continue
        depth = 0
        for j in range(i, len(s)):
            if s[j] == o:
                depth += 1
            elif s[j] == c:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[i:j + 1])
                    except Exception:
                        break
    return None


# ---------------------------------------------------------------- 工作流提示
# ★ 全部只吃 QUESTION + 机制自身指令。**不含任何手写题库内容。**

STANCE_SYS = """你是一个写作助手。你将面对下面这一个写作问题。

你要先想清楚：站在这个问题的哪一边，你的写作会**牺牲什么**。
你必须做出取舍，不许骑墙、不许"两边都有道理"。

只输出一个 JSON 对象，不要输出 JSON 以外的任何文字、不要用代码围栏。键和值用英文双引号包裹。
JSON 必须能被 JSON.parse 直接解析。

字段：
· "立场" —— 一个可以被反驳的判断。
· "不能牺牲" —— JSON 数组，恰好 3 个元素，每个是一句"不能牺牲什么"。
· "最容易失守" —— 一句话，这一轮写作最容易滑向哪里。
· "第一次反应" —— 面对这个题目，你脑子里冒出来的第一个念头是什么（一句短语）。

示例格式：
{"立场":"...","不能牺牲":["...","...","..."],"最容易失守":"...","第一次反应":"..."}"""

WRITE_SYS = """你是一个写作助手。

按给出的要求写这篇文章。直接输出文章正文，不要输出任何说明、
不要复述要求、不要写"根据要求"之类的话。"""

F_SYS = """你是同一个写作助手的内在状态调度器。写作者刚写出了初稿，你看了初稿，
现在要决定：**这一轮写作必须守住什么、必须避开什么**。

★ 你不能把立场转述给写作者，你只能输出**取舍约束**。
★ 输出必须是**叙述性自然语言**。禁止评分、等级、字段名、表格、编号列举。
★ 不要重复你自己的原句。

【你上一轮守住的取舍】
{stance}

【问题】
{question}

【初稿】
{draft}

【输出要求】恰好 3 行，每行一句「取舍约束」，分别说明：
- 这一轮要写进正文的取舍是什么（具体到这一轮，不是通则）
- 这一轮必须避开什么
- 这一轮写作者最容易失守的地方是什么

只输出这 3 行，不要任何编号、标题、解释、前后缀。

【三行】"""

G_SYS = """你是同一个写作助手的内在状态调度器。写作者刚写出了初稿，你要看初稿，
判断状态如何转移，然后决定这一轮必须守住什么、必须避开什么。

★ 输出必须是**叙述性自然语言**。禁止评分、等级、字段名、表格、编号列举。

【你上一轮守住的取舍】
{stance}

【问题】
{question}

【初稿】
{draft}

【输出要求】分三段，全部用叙述性自然语言：

第一段「未落地」：上一轮的取舍里，哪一条在初稿里其实还没有真正落地？
用你自己的话说，为什么没落地（一到两句）。

第二段「本轮约束」：因此这一轮的取舍约束应该**改成什么**。恰好 3 行，每行一句。
（要**和上一轮不同**——如果没发现需要改，就明确写"沿用上一轮"。）

第三段「已排除」：初稿已经走过、**这一轮不能再走**的路。恰好 2 行，每行一句。
（写清楚"不要再出现什么"，不要写成评分。）

【输出】"""


def parse3(text):
    """从自然语言里取 3 行约束（去掉可能的编号/空行）。"""
    lines = []
    for ln in (strip_think(text) or "").splitlines():
        ln = re.sub(r"^\s*(?:[0-9]+[.、)）]|[-*•]|第[一二三四五]段[：:]?)\s*", "", ln).strip()
        if ln:
            lines.append(ln)
    return lines


def run_workflow(question, model, base, key_env, tag):
    calls = []
    t0 = time.time()

    # ① 立场步
    raw = chat([{"role": "user", "content": question + "\n\n" + STANCE_SYS}],
               model, base, key_env, max_tokens=2000, json_mode=True)
    calls.append(("stance", len(raw)))
    st = loose_json(raw) or {}
    cons = st.get("不能牺牲") if isinstance(st.get("不能牺牲"), list) else []
    cons = [str(x).strip() for x in cons if str(x).strip()][:3]
    while len(cons) < 3:
        cons.append("把这一轮真正想说的话说清楚，不要滑回套话")
    stance_text = "· " + "\n· ".join(cons)

    # ② 写作步（初稿）
    brief1 = (question + "\n\n【这一轮要守住的取舍】\n" + stance_text +
              "\n\n直接输出文章正文。")
    d1 = chat([{"role": "user", "content": brief1}], model, base, key_env, max_tokens=4000)
    calls.append(("draft", len(d1)))
    draft = strip_think(d1)

    # ③ 转移步
    raw3 = chat([{"role": "user", "content":
                   F_SYS.format(stance=stance_text, question=question, draft=draft) +
                   "\n\n" + G_SYS.format(stance=stance_text, question=question, draft=draft)}],
                 model, base, key_env, max_tokens=2500)
    calls.append(("transfer", len(raw3)))
    lines = parse3(raw3)
    new_cons, excluded = [], []
    for ln in lines:
        if ("不再" in ln or "避开" in ln or "不要再" in ln) and len(excluded) < 2:
            excluded.append(ln)
        elif len(new_cons) < 3:
            new_cons.append(ln)
    while len(new_cons) < 3:
        new_cons.append("把这一轮真正想说的话说清楚，不要滑回套话")

    # ④ 终稿步
    brief2 = (question + "\n\n【这一轮要守住的取舍】\n" + "\n".join("· " + c for c in new_cons) +
              (("\n\n【这一轮不能再走的路】\n" + "\n".join("· " + c for c in excluded)) if excluded else "") +
              "\n\n【初稿】\n" + draft +
              "\n\n现在写出这一轮的定稿。直接输出文章正文。")
    d2 = chat([{"role": "user", "content": brief2}], model, base, key_env, max_tokens=4000)
    calls.append(("final", len(d2)))
    final = strip_think(d2)

    return {"arm": "WF", "tag": tag, "text": final, "draft": draft,
            "stance": stance_text, "constraints2": new_cons, "excluded": excluded,
            "calls": calls, "elapsed": round(time.time() - t0, 1)}


def run_direct(question, model, base, key_env, tag):
    t0 = time.time()
    txt = chat([{"role": "user", "content": question}],
               model, base, key_env, max_tokens=4000)
    return {"arm": "A", "tag": tag, "text": strip_think(txt),
            "calls": [("direct", len(txt))], "elapsed": round(time.time() - t0, 1)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="openrouter", choices=["openrouter", "minimax"])
    ap.add_argument("--model", default="x-ai/grok-4.20")
    ap.add_argument("--reps", default="1,2,3")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "min_compare.jsonl"))
    args = ap.parse_args()

    if args.api == "openrouter":
        import api_openrouter
        base, key_env = api_openrouter.DEFAULT_BASE, api_openrouter.DEFAULT_KEY_ENV
    else:
        base = os.environ.get("OPENROUTER_BASE_URL",
                               "https://api.minimaxi.com/v1").rstrip("/")
        key_env = "MINIMAX_SUBSCRIPTION_KEY"

    reps = [int(x) for x in args.reps.split(",") if x.strip()]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = []
        for s in reps:
            futs.append(ex.submit(run_direct, QUESTION, args.model, base, key_env, s))
            futs.append(ex.submit(run_workflow, QUESTION, args.model, base, key_env, s))
        for fu in as_completed(futs):
            try:
                results.append(fu.result())
            except Exception as e:
                results.append({"arm": "ERR", "tag": 0, "text": "", "error": str(e)})
    results.sort(key=lambda r: (r["arm"], r.get("tag") or 0))
    with open(args.out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 报告
    L = ["# 只输入一句话的对照", "",
         "唯一输入（逐字）：`%s`" % QUESTION, "",
         "模型 `%s`（%s）｜A 臂：一条 user 消息，无 system｜工作流臂：4 步（立场→初稿→转移→定稿）" %
         (args.model, args.api), ""]
    for arm, name in (("A", "直接调用 LLM"), ("WF", "新工作流（第四组状态机骨架）")):
        L += ["## %s · %s" % (arm, name), ""]
        for r in [x for x in results if x["arm"] == arm]:
            L += ["### 第 %s 次（%d 字）" % (r.get("tag"), len((r.get("text") or "").strip())), ""]
            if r.get("error"):
                L += ["**错误**：%s" % r["error"], ""]
                continue
            if arm == "WF":
                L += ["<details><summary>工作流中间态（取舍 / 二轮约束 / 已排除）</summary>", "",
                      "**① 立场步守住的取舍**", "", "```", r.get("stance", ""), "```", "",
                      "**② 转移步的新约束**", "", "```", "\n".join(r.get("constraints2") or []), "```", "",
                      "**③ 已排除选项**", "", "```", "\n".join(r.get("excluded") or []), "```", "",
                      "</details>", ""]
            L += [(r.get("text") or "").strip(), ""]
    txt = "\n".join(L)
    rp = args.out.replace(".jsonl", ".md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)
    print("\n[out] %s" % rp)


if __name__ == "__main__":
    main()
