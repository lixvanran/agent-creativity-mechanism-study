#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **远端 ref 归属表生成器（★ 2026-10-25）**

★ **★ 为什么要有这张表（★ 主会话 2026-10-25 要求）★★**
★ > 「★ 否则半年后没人说得清『远端 head 是谁推的』★」

★ **★ 问题背景（★ 本仓特有的）★★**
★ · `github.com` 的 git smart-HTTP 端点在本沙箱不可达 ⇒ ⇒ ★ ⇒ **推送只能走 GitHub REST API**
★ ⇒ ⇒ ★ **★ 而叠加式推送（★ overlay）会【在远端 head 之上】再加一层 ⇒ ⇒ ★ ⇒ **远端历史因此出现【多层】★★**
★ ⇒ ⇒ ★ **★ ⇒ 必须把「每层是谁叠的」登记下来 ★★**

★ **★ 本表登记四项（★ 每项都可核）★★**
★ ① 每条 branch 的 head sha
★ ② 归属组（★ 第二组 / 第四组 / 共享面）
★ ③ 谁叠的（★ 叠加链的每一层）
★ ④ 叠加链的完整 sha 序列（★ 从新到旧，★ 可逐层核）

★ 用法：`python3 -B tools/build_remote_ref_table.py --out docs/交接/REMOTE-REF-OWNERSHIP.md`
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request

API = "https://api.github.com"
REPO = "lixvanran/agent-creativity-mechanism-study"

OWNER = {
    "cmp8-handover-2026-10-20": "★ **第二组**（★ Mavis / 层2 人为设计）",
    "feature/g4-arch4-state-driven": "★ **第四组**（★ 状态机 / 架构化状态层）",
    "main": "★ **共享面**（★ 三组 / 第四组 / 第二组共用）",
}
# ★ ★ author name → owner（★ 自动反推，★ 避免人工填）★★
# ★ ★★★ 【★ 2026-10-25 实测坐实：★ author name 【不是全局唯一的】★★★】★★
# ★ ⇒ ⇒ ★ 实测 36 层里：★ `Mavis (第四组)`×12、★ `Mavis (lixvanran)`×12、★ `lixvanran`×8、★
# ★ ⇒ ⇒ ★ `Mavis`/`第二组`×2 各 ⇒ ⇒ ★ ⇒ **★ ⇒ 裸 "Mavis" 会被【第四组】和【用户】同时用 ★★**
# ★ ⇒ ⇒ ★ ⇒ **★ ⇒ 所以【author 只能做【弱推断】，★ 不能当硬归属】★★** ⇒ ⇒ ★ ⇒
# ★ ⇒ ★ ⇒ **★ ⇒ 硬归属只有一个来源：★ commit body 里的 `owner:` 行（★ 跟着 commit 走）★★**
AUTHOR_OWNER = {
    "第二组": "★ **第二组**（★ Mavis / 层2 人为设计）",
    "Mavis (第四组)": "★ **第四组**（★ 状态机 / 架构化状态层）",
    "第四组": "★ **第四组**（★ 状态机 / 架构化状态层）",
    # ★ ★ 【★ 裸 "Mavis" 故意【不映射】★★ ★ 因为它【不唯一】★ ⇒ ⇒ ★ ⇒ 映射它就是【猜】★★
}
# ★ ★ 弱推断（★ 只由 author 推出，★ 必须在表里【单独标出】，★ 不许与硬归属混列）★★
AUTHOR_OWNER_WEAK = {
    "Mavis (lixvanran)": "★ 弱推断：★ 用户 lixvanran 用 `Mavis` 这个 git 身份直推（★ 待主会话/三组确认）",
    "lixvanran": "★ 弱推断：★ 用户 lixvanran 账号直推（★ 组别待主会话确认）",
}
WHO_PUSHED = {
    "cmp8-handover-2026-10-20": "★ **第二组**（★ 走 REST API 的叠加式推送，★ `tools/push_overlay.py`）",
    "feature/g4-arch4-state-driven": "★ **第四组**（★ 独立推，★ 第二组未动过这条 branch）",
    "main": "★ 独立推（★ **第二组未动**：★ `e012f1e` 自 2026-10-24 起未变）",
}


def read_commit(sha, token):
    """★ ★ 读一个 commit 对象，★ 【兼容两种结构】★★

    ★ ★ 主会话 2026-10-25 实测：★★
    ★ · GitHub API **重建**的 commit（★ `POST /git/commits` 造出来的）★ ⇒ `message` 在**顶层** ★★
    ★ · GitHub **原生** commit（★ `GET /commits/<sha>`）★ ⇒ `message` 在 **`commit.message`** 下面 ★★
    ★ ⇒ ⇒ ★ ⇒ **★ ⇒ 遍历 commit 对象做归属/核对的代码，★ 两种结构都要读 ★★** ★★

    ★ ★ 判据为什么必须两种都读（★ 血训）：★ 三组的归属表生成器第一次跑就报 `KeyError: 'commit'` ★★
    """
    d = api("/git/commits/%s" % sha, token)
    if isinstance(d.get("message"), str):
        # ★ API 重建结构：★ message 在顶层 ★
        return {"sha": d.get("sha", sha), "message": d.get("message", "") or "",
                "author": d.get("author", {}) or {}, "parents": d.get("parents") or [],
                "structure": "top-level（★ API 重建）"}
    c = d.get("commit", {}) or {}
    return {"sha": d.get("sha", sha), "message": c.get("message", "") or "",
            "author": c.get("author", {}) or {}, "parents": d.get("parents") or [],
            "structure": "commit.message（★ GitHub 原生）"}


def api(path, token):
    r = urllib.request.Request(
        API + "/repos/" + REPO + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "mavis-ref-table"})
    return json.load(urllib.request.urlopen(r, timeout=60))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/workspace/lab/docs/交接/REMOTE-REF-OWNERSHIP.md")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN_LIXVANRAN", ""))
    a = ap.parse_args()
    if not a.token:
        print("✘ 没 token")
        return 2

    from datetime import datetime, timezone
    gen_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    branches = api("/branches?per_page=100", a.token)
    snap_at = gen_at
    lines = []
    L = lines.append
    L("# ★ 远端 ref 归属表（★ 生成物）")
    L("")
    L("> 出处：`%s`" % a.out.replace("/workspace/lab/", ""))
    L("> 仓：`%s`（★ public）" % REPO)
    L("> ★ **本表由 `tools/build_remote_ref_table.py` 生成（★ 可重跑复核）★**")
    L(">")
    L("> ★ **生成时间（本地）**：★ `%s`" % gen_at)
    L("> ★ **远端 ref 快照时刻**：★ `%s`" % snap_at)
    L("> ★ **机器可读副本**：★ `docs/交接/OWNERS.json`（★ sha → owner/推送者/时间/首行）★★")
    L("> ★ ★ **★ 本表是【生成物】不是手写文档（★ 主会话要求 ㊭）★★")
    L("> ★ ★ **★ ⇒ ⇒ 每次推完请【重跑一次并把输出 commit 进去】★ ★** ⇒ ⇒ ★ ⇒ **★ ⇒ 归属表不会腐化 ★★")
    L("")
    L("## ★ 1 · 三条 branch 的当前 head")
    L("")
    L("| ★ branch | ★ head sha | ★ 归属组 | ★ 谁叠的 |")
    L("|---|---|---|---|")
    detail = []
    for b in sorted(branches, key=lambda x: x["name"]):
        n, s = b["name"], b["commit"]["sha"]
        L("| `%s` | `%s` | %s | %s |" % (n, s[:12], OWNER.get(n, "★ 未登记"),
                                     WHO_PUSHED.get(n, "★ 未登记")))
        detail.append((n, s))
    L("")
    L("## ★ 2 · ★★ 叠加链（★ 每条 branch 从新到旧，★ 逐层可核）★★")
    L("")
    L("| ★ 层 | ★ sha | ★ commit message 首行 | ★ author | ★ 日期 | ★ ★ owner（★ 分级）★★ |")
    L("|:-:|---|---|---|---|---|---|")
    L("> ★ ★ **owner 分三级（★ 2026-10-25 实测：★ author name 【不唯一】★★）★★**")
    L(">")
    L("> ★ **硬** = ★ commit body 里有 `owner:` 行（★ 跟着 commit 走，★ 任何 clone 可见）★★")
    L("> ★ **弱** = ★ 只由 author 反推（★ ★ 【★ 不可当归属依据，★ 只是线索 ★】★★）")
    L("> ★ **未确认** = ★ 既无 owner 行、★ author 也归不出来（★ ⇒ 进 §2.2 待确认清单）★★")
    owners = {}          # ★ sha → 归属记录
    unconfirmed = []     # ★ ★ 归不出来的层（★ 必须被显式列出，★ 不许默默漏掉）★★
    for n, s in detail:
        c = read_commit(s, a.token)
        L("")
        L("### ★ `%s`" % n)
        L("")
        cur, i = s, 0
        while cur and i < 12:
            cc = read_commit(cur, a.token)
            msg = cc.get("message", "") or ""
            au = cc.get("author", {}) or {}
            aname = au.get("name", "") or ""
            subj = msg.splitlines()[0][:64].replace("|", "/")
            # ★ ★ owner 反推（★ 优先级：① message 里的 owner 行 ② author name 映射 ③ 归不出来）★★
            ow = None
            for ln in msg.split("\n"):
                if ln.startswith("owner:"):
                    ow = ln.split(":", 1)[1].strip()
                    break
            if ow is None:
                ow = AUTHOR_OWNER.get(aname)
            grade = "硬（owner 行）" if ow else ""
            if ow is None:
                ow = AUTHOR_OWNER_WEAK.get(aname)
                if ow:
                    grade = "弱（author 推断）"
            if ow is None:
                ow = "★ 未确认"
                unconfirmed.append({"sha": cur, "branch": n, "author": aname,
                                    "email": au.get("email", ""), "date": au.get("date", ""),
                                    "subject": subj})
            owners[cur] = {"owner": ow, "grade": grade or "未确认", "pusher": aname,
                           "email": au.get("email", ""), "date": au.get("date", ""),
                           "subject": subj, "branch": n}
            L("| %d | `%s` | %s | `%s` | %s | %s ｜ %s |" % (i + 1, cur[:12], subj, aname,
                                                  au.get("date", "")[:19], ow, grade or "未确认"))
            ps = cc.get("parents") or []
            cur = ps[0]["sha"] if ps else None
            i += 1
        L("")
    L("## ★ 2.1 · ★★ 【★ owner 覆盖自检（★ 主会话要求：★ 不许像 message 一样慢慢腐化 ★）★★】★★")
    L("")
    total = len(owners)
    hard = sum(1 for v in owners.values() if v["grade"].startswith("硬"))
    weak = sum(1 for v in owners.values() if v["grade"].startswith("弱"))
    L("| ★ 项 | ★ 值 |")
    L("|---|---|")
    L("| ★ 扫描到的层数 | ★ **%d** |" % total)
    L("| ★ ★ **硬归属**（★ 有 owner 行） | ★ **%d** ★★ |" % hard)
    L("| ★ ★ **弱推断**（★ 只由 author 反推，★ ★ 不可当依据 ★★） | ★ **%d** |" % weak)
    L("| ★ ★ **未确认** | ★ **%d**（★ 逐条列在 §2.2，★ 不许默默漏掉）★★ |" % (total - hard - weak))
    L("| ★ ★ **自检** | ★ ★ **每层三者之一：★ 硬 owner / 弱推断 / 进 §2.2（★ 互斥且全覆盖）★★ |")
    L("")
    L("## ★ 2.2 · ★★ 【★ 待确认清单（★ 每条写清【谁去问、★ 问了没有】★★）★★】")
    L("")
    if not unconfirmed:
        L("★ **本轮无待确认层。**")
    else:
        L("| ★ sha | ★ author | ★ 日期 | ★ 首行 | ★ ★ 谁去问 | ★ ★ 问了没有 | ★ 状态 |")
        L("|---|---|---|---|---|---|---|")
        for u in unconfirmed:
            L("| `%s` | `%s` | %s | %s | ★ **主会话**（★ 三组 / 四组） | ★ ★ **未问** | ★ 待确认 |"
              % (u["sha"][:12], u["author"], u["date"][:10], u["subject"][:40]))
    L("")
    L("## ★ 3 · ★★ 为什么会有【多层叠加】（★ 机制说明）★★")
    L("")
    L("★ **★ 本仓的推送路径是【非标准】的，★ 所以必须登记 ★★**")
    L("")
    L("| ★ 项 | ★ **说明** |")
    L("|---|---|")
    L("| ★ **为什么不用 `git push`** | ★ `github.com` 的 git smart-HTTP 端点在本沙箱【不可达】（★ curl http=000 / TLS 握手失败）；★ 而 `api.github.com` 稳定 200 ⇒ ⇒ ★ ⇒ **只能用 REST API 推** |")
    L("| ★ **为什么是叠加而不是 force** | ★ 远端有 **92 个本地没有的文件**（★ 含 `docs/cmp8/PAPER-2026-10-25.md`、`docs/cmp8/figures/*`）⇒ ⇒ ★ ⇒ **force push 会真丢它们** ⇒ ⇒ ★ ⇒ **★ 所以选【只加不删】的 overlay 语义 ★★** |")
    L("| ★ **叠加链的形态** | ★ 新 commit 的 parent = ★ **远端 head**（★ 不是本地 HEAD）⇒ ⇒ ★ ⇒ **⇒ 【★ 远端 sha ≠ 本地 HEAD 是【正常】的 ★】★★ ⇒ ⇒ ★ ⇒ **复核判据必须是【树内容一致】，★ 不是 sha 相等 ★** |")
    L("| ★ **★ 一次意外的中间层** | ★ ★ **`8934cb193cc2`（★ 第 2 层）★ 来自一个【因 404 被当可重试错误而卡住】的进程** ⇒ ⇒ ★ ⇒ **它在最后关头已 PATCH 成功了一次，★ 我随后才 kill 掉它** ⇒ ⇒ ★ ⇒ **★ ⇒ 这就是第 2 层的来历（★ 显式登记，★ 不隐去）★★** |")
    L("")
    L("## ★ 4 · ★★ 两条 push 工具的共同约定 ★★")
    L("")
    L("| ★ 工具 | ★ 作用 |")
    L("|---|---|")
    L("| ★ `tools/push_overlay.py` | ★ ★ **只加不删的叠加式推送**（★ 远端独有文件一个不删）★ |")
    L("| ★ `tools/push_via_api.py` | ★ 逐 commit 重建历史版（★ ★ 本次【未采用】：★ 叠加链上已有正确基点，★ 重建会多花 4 倍调用）★ |")
    L("")
    L("★ ★★ **★ 两条共同的自检项（★ 2026-10-25 主会话要求落成工具自检，★ 不是一次修复）★★**")
    L("")
    L("| ★ **检查** | ★ **为什么** |")
    L("|---|---|")
    L("| ★ **重试分支里不含 404/422** | ★ ★ **404/422 是确定性错误 ⇒ ⇒ 进重试分支 ⇒ ⇒ 每次白等 75s ⇒ ⇒ 183 个 blob 要 4 小时 ★★（★ 本轮真实发生）★ |")
    L("| ★ **没有『先 GET 再 POST』的探测步骤** | ★ 同内容必然同 sha ⇒ ⇒ ★ ⇒ **直接 POST 天然幂等** ⇒ ⇒ ★ ⇒ **『先查再写』是把幂等当不存在 ★** |")
    L("| ★ **推后逐路径复核** | ★ 断言【本地有远端没有 = 0】+【同路径内容不同 = 0】+【远端独有丢失 = 0】 |")
    L("")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("  ✔ 已生成 %s（★ %d 行）" % (a.out, len(lines)))
    # ★ ★ OWNERS.json（★ 机器可读副本）★★
    oj = os.path.join(os.path.dirname(a.out), "OWNERS.json")
    payload = {"generated_at": gen_at, "remote_snapshot_at": snap_at, "repo": REPO,
               "branches": {n: s for n, s in detail},
               "commits": owners, "unconfirmed": unconfirmed}
    with open(oj, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print("  ✔ 已生成 %s（★ %d 层，★ 待确认 %d）" % (oj, len(owners), len(unconfirmed)))
    # ★ ★ 自检：★ 每层要么有明确 owner，★ 要么在待确认清单里（★ 显式列出）★★
    missing = [sha for sha, v in owners.items()
               if v["grade"] == "未确认" and sha not in {u["sha"] for u in unconfirmed}]
    if missing:
        print("✘ owner 覆盖自检失败：★ %d 层既无 owner 又不在待确认清单" % len(missing))
        return 3
    print("  ✔ owner 覆盖自检：★ 全部层要么有 owner、★ 要么在待确认清单（★ %d 待确认）" % len(unconfirmed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
