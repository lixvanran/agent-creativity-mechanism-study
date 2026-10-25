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
WHO_PUSHED = {
    "cmp8-handover-2026-10-20": "★ **第二组**（★ 走 REST API 的叠加式推送，★ `tools/push_overlay.py`）",
    "feature/g4-arch4-state-driven": "★ **第四组**（★ 独立推，★ 第二组未动过这条 branch）",
    "main": "★ 独立推（★ **第二组未动**：★ `e012f1e` 自 2026-10-24 起未变）",
}


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

    branches = api("/branches?per_page=100", a.token)
    lines = []
    L = lines.append
    L("# ★ 远端 ref 归属表（★ 2026-10-25 生成）")
    L("")
    L("> 出处：`%s`" % a.out.replace("/workspace/lab/", ""))
    L("> 仓：`%s`（★ public）" % REPO)
    L("> ★ **本表由 `tools/build_remote_ref_table.py` 生成（★ 可重跑复核）★**")
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
    for n, s in detail:
        c = api("/git/commits/%s" % s, a.token)
        L("### ★ `%s`" % n)
        L("")
        L("| ★ 层 | ★ sha | ★ commit message | ★ 日期 |")
        L("|:-:|---|---|---|")
        cur, i = s, 0
        while cur and i < 12:
            cc = api("/git/commits/%s" % cur, a.token)
            L("| %d | `%s` | %s | %s |" % (i + 1, cur[:12],
                                         cc.get("message", "").splitlines()[0][:64].replace("|", "/"),
                                         cc.get("author", {}).get("date", "")[:10]))
            ps = cc.get("parents") or []
            cur = ps[0]["sha"] if ps else None
            i += 1
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
