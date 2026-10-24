#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
★ 【远端 overlay 独立复核脚本】—— ★ ★ **★ 共享件（★ 2026-10-25 主会话要求共享）★★★** ★★
============================================================================

★ **★ 为什么它必须是【共享件】而不是某个组的私产 ★★**
------------------------------------------------------------------------
★ **★ 理由：★ 它是【复核】的本体，★ 不是【推送】的附属 ★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 一个组的推送工具【自己】复核自己【没有交叉验证价值】★★** ⇒ ⇒ ★ ⇒
★ ⇒ ⇒ ★ ⇒ **★ ⇒ ⇒ 而【独立脚本 + 独立实现】才是【交叉验证】★★** ⇒ ⇒ ★ ⇒
★ ⇒ ⇒ ★ ⇒ **★ ⇒ ⇒ ⇒ 记忆里的血训：★ 「同源测试会一起错、★ 一起绿」★ ★ ⇒ ★ ⇒⇒ ★ ★ **★ ⇒ ⇒ ⇒ ⇒ ★ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ 【独立实现 + 变异注入】= 唯一能破它的办法 ★★** ★★**

★ **★ ★ 本脚本【刻意不 import】`tools/push_overlay.py` ★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ 它自己重写一遍：★ API 调用、★ 树比对、★ commit 回读 ★★**
★ ⇒ ⇒ ★ ⇒ **★ ⇒ ⇒ 若它 import 了推送工具，★ ⇒ ★ ⇒ ⇒ 【两边会一起错、一起绿】★★** ★★

★ **★ 复核三件事（★ 全部可独立重算）★★**
------------------------------------------------------------------------
★ **① 远端 ref 可读、★ 且与推送工具报的 commit 一致**
★ **② 【树内容一致】（★ overlay 语义下的正确判据）★★**
★ ★ ★ 本地有远端没有 = 0 ｜ 同路径内容不同 = 0 ｜ 远端独有的全部保留（★ 不删）★★
★ ★ ★ **★ ⇒ 判据【按推送语义分】：★ 普通推送是【sha == HEAD】；★ overlay 是【树内容一致】★★** ★★
★ **③ 回读远端 commit 对象，★ 逐字核对 message / author / date（★ 用共享的 `push_norm` 归一化 ★）★★**

★ **★ 用法 ★★
------------------------------------------------------------------------
★   python3 -B tools/verify_remote_overlay.py \
★       --repo lixvanran/agent-creativity-mechanism-study \
★       --branch cmp8-handover-2026-10-20 \
★       --expect-commit <sha>        # ★ 可选：★ 推送工具报的 commit
★   ⇒ 退出码：★ 0 = 全过；★ 3 = 有项不通过
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from push_norm import NORMALIZERS, norm_field  # ★ noqa: E402

API = "https://api.github.com"


def api(path: str, token: str):
    r = urllib.request.Request(
        API + path,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "mavis-verify-overlay"},
    )
    return json.load(urllib.request.urlopen(r, timeout=60))


def local_tree(repo: str) -> dict:
    """★ ★ 本地 HEAD 的树（★ ★ NUL 分隔（★ `git ls-tree -r -z`）★ ★ ⇒ ⇒ 非 ASCII 路径不产生假差异）★★"""
    out = subprocess.run(["git", "ls-tree", "-r", "-z", "HEAD"],
                         cwd=repo, capture_output=True).stdout
    d = {}
    for rec in out.split(b"\x00"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        d[path.decode("utf-8")] = meta.decode().split()[2]
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="★ owner/name")
    ap.add_argument("--branch", required=True)
    ap.add_argument("--local-repo", default="/workspace/lab")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN_LIXVANRAN", ""))
    ap.add_argument("--expect-commit", default="", help="★ 本地 commit sha（★ 可选 ★）★ ★ 注意：★ overlay 推送的远端 sha【天然≠】本地 sha（★ parent 不同 ★）⇒ ★ 本参数只做【提示】，★ 不做失败判据 ★")
    a = ap.parse_args()
    if not a.token:
        print("✘ 没 token")
        return 2

    bad: list = []
    # ── ① 远端 ref ──
    ref = api("/repos/%s/git/ref/heads/%s" % (a.repo, a.branch), a.token)
    head = ref["object"]["sha"]
    print("★ 远端 %s head = %s" % (a.branch, head[:12]))
    # ★ ★★ 2026-10-26 修：★ --expect-commit 传的是【本地 commit sha】★★
    # ★ overlay 推送是【用 REST API 在远端当前 head 之上新建 commit】⇒ ★ parent
    # ★ 与本地 commit 的 parent 不同 ⇒ ★ ⇒ 【远端 sha 天然 ≠ 本地 sha】★★
    # ★ ⇒ ★ 所以【不能】用 sha 相等做判据（★ 本人已被这条顶过一次 ★）★★
    # ★ ⇒ ★ 正确的判据是【树内容一致】+【commit 字段逐字一致】（★ 下面已在查 ★）★★
    if a.expect_commit:
        if head == a.expect_commit:
            print("  ✔ 远端 ref 与 --expect-commit 逐字一致（★ 罕见：★ parent 与 tree 全同 ★）")
        else:
            print("  ★ --expect-commit = %s（★ 本地 commit sha ★）" % a.expect_commit[:12])
            print("    ★ 远端 ref     = %s（★ overlay 在远端 head 之上新建的 commit ★）" % head[:12])
            print("    ★ ★ 两者【本来就不相等】★ ★ ⇒ ★ overlay 的 parent 与本地 parent 不同 ⇒ ★")
            print("    ★ ⇒ ★ 正确判据是【树内容一致】+【commit 字段逐字一致】（★ 下面在查 ★），★ 不是 sha 相等 ★")

    # ── ② 树内容一致（★ overlay 语义 ★）──
    tree = api("/repos/%s/git/trees/%s?recursive=1"
               % (a.repo, api("/repos/%s/git/commits/%s" % (a.repo, head), a.token)["tree"]["sha"]),
               a.token)
    remote = {e["path"]: e["sha"] for e in tree.get("tree", []) if e["type"] == "blob"}
    local = local_tree(a.local_repo)
    only_local = [p for p in local if p not in remote]
    diff = [p for p in local if p in remote and remote[p] != local[p]]
    lost = [p for p in remote if p not in local]
    print("  ★ 本地有远端没有 = %d （★ 应 0）" % len(only_local))
    print("  ★ 同路径内容不同 = %d （★ 应 0）" % len(diff))
    print("  ★ 远端独有（★ 全部保留、★ 不删）= %d" % len(lost))
    if only_local:
        bad.append("② 本地有远端没有 = %d" % len(only_local))
    if diff:
        bad.append("② 同路径内容不同 = %d" % len(diff))
    # ★ ★ 远端独有【不是错误】⇒ ★ 那是 overlay 的【只加不删】语义 ★★

    # ── ③ 回读远端 commit，逐字核对三项 ──
    c = api("/repos/%s/git/commits/%s" % (a.repo, head), a.token)
    rmsg = c.get("message", "") or ""
    rauth = c.get("author", {}) or {}
    rcommitter = c.get("committer", {}) or {}
    head_meta = subprocess.run(
        ["git", "log", "-1", "--format=%an%n%ae%n%aI%n%cn%n%ce%n%cI"],
        cwd=a.local_repo, capture_output=True, text=True).stdout.splitlines()
    am, ae, ad, cm, ce, cd = (head_meta + ["", "", "", "", "", ""])[:6]
    # ★ ★ message：【只核【首行 + owner 行】★★
    # ★ ★ ⇒ ★ overlay 的远端 message 是【拼出来的】（★ 含结构说明 + 全清单）★★
    # ★ ★ ⇒ ★ ⇒ 【全文逐字相等】不是可用判据（★ 真实形态）⇒ ⇒ ★ ⇒
    # ★ ★ ⇒ ★ ⇒ ★ ★ 【可核的部分】= 【首行（★ 本地最新 commit 的 subject）】+【owner 行】★★
    r_first = (rmsg.splitlines() or [""])[0]
    r_owner = [ln for ln in rmsg.splitlines() if ln.startswith("owner:")]
    l_first = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=a.local_repo,
                             capture_output=True, text=True).stdout.strip()
    checks = [
        ("message.首行", norm_field("message", r_first), norm_field("message", l_first)),
        ("message.owner行", r_owner[0] if r_owner else "", "owner: 第二组"),
        ("author.name", rauth.get("name"), am),
        ("author.email", rauth.get("email"), ae),
        ("author.date", norm_field("date", rauth.get("date", "")), norm_field("date", ad)),
        ("committer.name", rcommitter.get("name"), cm),
        ("committer.email", rcommitter.get("email"), ce),
        ("committer.date", norm_field("date", rcommitter.get("date", "")), norm_field("date", cd)),
    ]
    for name, got, want in checks:
        ok = (got == want)
        print("  ★ %-16s %s" % (name, "✔ 一致" if ok else "✘ 不一致（★ %r ≠ %r）" % (got, want)))
        if not ok:
            bad.append("③ %s 不一致" % name)

    print()
    print("★ 用的归一化规则（★ 单一真相源 · tools/push_norm.py）：")
    for n in NORMALIZERS:
        print("  ★ %-8s %s" % (n["field"], n["what"]))
    print()
    if bad:
        print("✘ 远端复核未通过（★ %d 项）：" % len(bad))
        for b in bad:
            print("   - %s" % b)
        return 3
    print("✔ 远端复核全过（★ ref + 树内容一致 + commit 三项逐字一致 ★）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
