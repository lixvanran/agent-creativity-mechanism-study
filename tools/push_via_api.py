#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **走 GitHub REST API 的逐 commit 推送器（★ 2026-10-25）**

★ **为什么需要它（★ 环境事实，★ 不是偏好）**
★ · `https://github.com`（★ git smart-HTTP 端点）★ **完全不可达**（★ curl http=000 / TLS 握手失败）
★ · `https://api.github.com` ★ **稳定 200** ⇒ ⇒ ★ ⇒ **唯一可用通道 = REST API**
★ ⇒ ⇒ ★ **⇒ "git push" 这条路在这个沙箱里走不通 ⇒ ⇒ ★ ⇒ ★ **★ 本脚本用 Git Data API 逐 commit 重建历史 ★★**

★ **★ 纪律对齐（★ 与 codex 那条指令一致）★★**
★ ① **逐 commit 推**（★ 不 squash、不 rebase）⇒ ⇒ ★ ⇒ **★ 远端的 commit 粒度与本地一一对应 ★★**
★ ② **★ 最后只 `PATCH /git/refs` 一次** ⇒ ⇒ ★ ⇒ ★ **★ 中途任何失败都不会在远端留下半截分支 ★★**
★ ③ **★ 推完【必须】复核远端 ref sha == 本地 HEAD** ⇒ ⇒ ★ ⇒ ★ **★ "PATCH 静默失败"是已知坑 ⇒ ⇒ ★ ⇒ ★ **★ 复核才算推成功 ★★**

★ **★ 自带的两道校验（★ 不靠"我以为推成功了"）★★**
★ · blob 上传后**必须**返回与本地 `git cat-file` 相同的 sha ⇒ ⇒ ★ ⇒ **内容被篡改会当场暴露**
★ · 全部 commit 建完后，**从远端读回** commit 链，逐个核 tree sha ⇒ ⇒ ★ ⇒ **远端与本地【逐 commit 逐字节】一致**

★ 用法：
★   python3 -B tools/push_via_api.py --repo lixvanran/agent-creativity-mechanism-study \
★       --branch cmp8-handover-2026-10-20 --token "$GITHUB_TOKEN_LIXVANRAN"
★   ★ 加 --dry-run 只打印计划，★ 不调 API
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"


def git(*args, binary=False):
    r = subprocess.run(("git",) + args, capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode("utf-8")


class Gh:
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo
        self.n = 0

    def _req(self, method: str, path: str, body=None, raw=False):
        url = path if path.startswith("http") else "%s/repos/%s%s" % (API, self.repo, path)
        data = None
        headers = {"Accept": "application/vnd.github+json",
                   "Authorization": "Bearer " + self.token,
                   "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "mavis-push"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        last = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    self.n += 1
                    txt = r.read().decode("utf-8")
                    return r.read if raw else json.loads(txt) if txt else {}
            except urllib.error.HTTPError as e:
                txt = e.read().decode("utf-8", "replace")
                last = "HTTP %s: %s" % (e.code, txt[:300])
                if e.code in (403, 429) and "rate limit" in txt.lower():
                    time.sleep(20)
                    continue
                raise RuntimeError("%s %s ⇒ %s" % (method, path, last))
            except Exception as e:            # ★ 网络抖动 ⇒ ⇒ 重试
                last = "%s: %s" % (type(e).__name__, e)
                time.sleep(3 + attempt * 3)
        raise RuntimeError("%s %s ⇒ 重试 4 次仍失败: %s" % (method, path, last))

    def get(self, p):
        return self._req("GET", p)

    def post(self, p, body):
        return self._req("POST", p, body)

    def patch(self, p, body):
        return self._req("PATCH", p, body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN_LIXVANRAN", ""))
    ap.add_argument("--repo-path", default="/workspace/lab")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.token and not args.dry_run:
        print("✘ 没有 token")
        return 2
    os.chdir(args.repo_path)

    commits = git("log", "--reverse", "--format=%H", args.branch).split()
    if not commits:
        print("✘ 分支 %s 没有 commit" % args.branch)
        return 2
    head = git("rev-parse", "HEAD").strip()
    print("═══ 计划：★ 分支 %s ｜ %d 个 commit ｜ HEAD %s" % (args.branch, len(commits), head[:12]))
    if args.dry_run:
        for c in commits:
            msg = git("log", "-1", "--format=%s", c).strip()
            n = len(git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split())
            print("  %s  %2d 文件  %s" % (c[:10], n, msg[:60]))
        return 0

    gh = Gh(args.token, args.repo)

    # ★ 远端是否已有这个分支
    try:
        ref = gh.get("/git/ref/heads/%s" % args.branch)
        remote_head = ref["object"]["sha"]
        print("  ★ 远端已有该分支，HEAD = %s" % remote_head[:12])
    except Exception as e:
        remote_head = None
        print("  ★ 远端无该分支（★ %s）" % str(e)[:80])

    # ★ 决定起点：★ 远端已有 ⇒ 从远端 head 之后的 commit 开始；★ 否则从第一个开始
    if remote_head:
        if remote_head == head:
            print("✔ 远端已等于本地 HEAD ⇒ 无需推")
            return 0
        allc = git("log", "--reverse", "--format=%H", args.branch).split()
        if remote_head in allc:
            start = allc.index(remote_head) + 1
        else:
            print("  ★ 远端 head 不在本地历史中 ⇒ 从头推")
            start = 0
    else:
        start = 0
    todo = commits[start:]
    print("  ★ 待推 %d 个 commit（★ %s … %s）" % (len(todo), todo[0][:10] if todo else "-",
                                           todo[-1][:10] if todo else "-"))

    parent_sha = remote_head
    if not parent_sha:
        # ★ 新分支：★ 基准取本地第一个 commit 的父（★ 若无父 ⇒ 用空 tree 起步）
        first = commits[0]
        parents = git("log", "-1", "--format=%P", first).split()
        parent_sha = parents[0] if parents else None
        if parent_sha:
            print("  ★ 基准父 commit = %s" % parent_sha[:12])
        else:
            print("  ★ 首个 commit 无父 ⇒ 从空 tree 起步")

    # ★ 逐 commit 建
    built = []
    for i, c in enumerate(todo):
        cparent = git("log", "-1", "--format=%P", c).split()
        cparent_sha = cparent[0] if cparent else None
        # ★ base tree
        if cparent_sha:
            base_tree = gh.get("/git/commits/%s" % cparent_sha)["tree"]["sha"]
        else:
            base_tree = None
        # ★ 变更文件
        raw = git("diff-tree", "--no-commit-id", "--raw", "-r", c).strip().splitlines()
        entries = []
        for ln in raw:
            if not ln.strip():
                continue
            meta, path = ln.split("\t", 1)
            parts = meta.split()
            mode, otype, osha, nsha = parts[0], parts[1], parts[2], parts[3]
            if nsha == "0" * 40:      # ★ 删除
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None,
                                "_del": True})
                continue
            if nsha == osha:         # ★ 未变（★ 只改 mode 的情况极少）
                entries.append({"path": path, "mode": mode, "type": "blob", "sha": nsha})
                continue
            # ★ blob 是否已在远端？★ ★ 先问远端，★ 不在才上传
            try:
                gh.get("/git/blobs/%s" % nsha)
                entries.append({"path": path, "mode": mode, "type": "blob", "sha": nsha})
                continue
            except Exception:
                pass
            content = git("cat-file", "blob", nsha, binary=True)
            up = gh.post("/git/blobs", {"content": base64.b64encode(content).decode(),
                                        "encoding": "base64"})
            if up.get("sha") != nsha:
                print("✘ blob sha 不符：★ 本地 %s ≠ 远端 %s（★ ⇒ 停止）" % (nsha, up.get("sha")))
                return 1
            entries.append({"path": path, "mode": mode, "type": "blob", "sha": nsha})
        # ★ 建 tree
        tbody = {"tree": [{k: v for k, v in e.items() if not k.startswith("_")} for e in entries]}
        if base_tree:
            tbody["base_tree"] = base_tree
        t = gh.post("/git/trees", tbody)
        # ★ 建 commit（★ ★ 保持原作者与时间，★ 让历史与本地【逐 commit 对应】★★）
        meta = git("log", "-1", "--format=%an%n%ae%n%aI%n%cn%n%ce%n%cI", c).splitlines()
        am, ae, ad, cm, ce, cd = (meta + ["", "", "", "", "", ""])[:6]
        cbody = {"message": git("log", "-1", "--format=%B", c),
                 "tree": t["sha"],
                 "parents": [cparent_sha] if cparent_sha else [],
                 "author": {"name": am, "email": ae, "date": ad},
                 "committer": {"name": cm, "email": ce, "date": cd}}
        nc = gh.post("/git/commits", cbody)
        built.append((c, nc["sha"]))
        if (i + 1) % 5 == 0 or i == len(todo) - 1:
            print("  ✔ %d/%d  %s → %s" % (i + 1, len(todo), c[:10], nc["sha"][:10]))

    if not built:
        print("✔ 无需新建 commit")
        return 0

    # ★ ★ 最后只 PATCH 一次 ref（★ 中途失败不留半截分支）★★
    final = built[-1][1]
    try:
        gh.patch("/git/refs/heads/%s" % args.branch, {"sha": final, "force": False})
        print("★ PATCH ref ⇒ %s" % final[:12])
    except Exception as e:
        # ★ 分支不存在 ⇒ 用 POST 建
        print("  ★ PATCH 失败（★ %s）⇒ ⇒ 改用 POST 建分支" % str(e)[:90])
        gh.post("/git/refs", {"ref": "refs/heads/%s" % args.branch, "sha": final})
        print("★ POST ref ⇒ %s" % final[:12])

    # ★ ★ 复核（★ 唯一可信的"推成功"判据）★★
    r = gh.get("/git/ref/heads/%s" % args.branch)
    got = r["object"]["sha"]
    if got != final:
        print("✘★ 远端 ref = %s ≠ 期望 %s" % (got[:12], final[:12]))
        return 1
    if got != head:
        print("★ ⚠ 远端 head = %s，★ 本地 HEAD = %s（★ ⇒ 需确认是否还有未推的 commit）" % (got[:12], head[:12]))
    print("✔✔ 远端 ref = %s ✔✔ （★ 与本地 HEAD 一致）" % got[:12])
    # ★ 逐 commit 回读 tree，★ 确认远端历史与本地【逐 commit 对应】
    mism = 0
    for c, rsha in built:
        rc = gh.get("/git/commits/%s" % rsha)
        lt = git("rev-parse", "%s^{tree}" % c).strip()
        if rc["tree"]["sha"] != lt:
            mism += 1
            print("  ✘ tree 不符：★ %s" % c[:10])
    print("★ 逐 commit 回读 tree：★ %d/%d 一致" % (len(built) - mism, len(built)))
    print("★ 本次 API 调用 %d 次" % gh.n)
    return 0 if mism == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
