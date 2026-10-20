#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 GitHub REST API 推一个 commit（git 客户端的凭据/CA 有问题时用这条路线）。

★ 纪律（2026-10-20 实测踩坑）：
  ① PATCH /git/refs/heads/<branch> **可能静默失败**（不报错但 ref 没动）
     ⇒ 推完必须 `GET /git/ref/heads/<branch>` 把 SHA 与目标 commit **逐字比对**
  ② **别用 raw.githubusercontent 做校验**（有 CDN 缓存，会给你旧内容）
     ⇒ 用 /git/trees/<sha>?recursive=1 看每个文件的 size，用 /contents/<path>?ref=<sha> 精确核对内容
"""
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "lixvanran/agent-creativity-mechanism-study"
BRANCH = "cmp8-handover-2026-10-20"
TOKEN = os.environ.get("GITHUB_TOKEN_LIXVANRAN", "")
API = "https://api.github.com"
LOCAL = os.path.abspath(os.path.dirname(__file__))


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": "Bearer " + TOKEN,
                 "Accept": "application/vnd.github+json",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as f:
            return json.loads(f.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:400]
        raise SystemExit("✗ %s %s ⇒ HTTP %s: %s" % (method, path, e.code, body))


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else LOCAL
    msg = sys.argv[2] if len(sys.argv) > 2 else "update"
    os.chdir(root)

    # ① 当前分支 HEAD
    ref = req("GET", "/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))
    base = ref["object"]["sha"]
    base_commit = req("GET", "/repos/%s/git/commits/%s" % (REPO, base))
    base_tree = base_commit["tree"]["sha"]
    print("base commit : %s" % base)
    print("base tree   : %s" % base_tree)

    # ② 收集要推的文件（git status 里的）
    # ★ 文件清单来自「本地 HEAD 相对 base 的差异」——不是 git status
    #   （改动若已 commit，status 是干净的 ⇒ 会误判成"没有待推送的改动"）
    out = subprocess.check_output(
        ["git", "diff", "--name-only", base, "HEAD"], text=True)
    files = [("M", p) for p in out.splitlines() if p.strip()]
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], text=True)
    for p in untracked.splitlines():
        if p.strip():
            files.append(("A", p.strip()))
    if not files:
        print("没有待推送的改动")
        return
    print("待推 %d 个文件" % len(files))

    # ③ 逐个建 blob
    entries = []
    for st, path in files:
        raw = open(path, "rb").read()
        blob = req("POST", "/repos/%s/git/blobs" % REPO,
                   {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("  blob %-46s %s" % (path[:46], blob["sha"][:10]))

    # ④ 建 tree（基于 base tree）
    tree = req("POST", "/repos/%s/git/trees" % REPO,
               {"base_tree": base_tree, "tree": entries})
    # ⑤ 建 commit
    commit = req("POST", "/repos/%s/git/commits" % REPO,
                 {"message": msg, "tree": tree["sha"], "parents": [base]})
    print("new commit  : %s" % commit["sha"])

    # ⑥ ★ PATCH ref（响应体必须检查）
    patched = req("PATCH", "/repos/%s/git/refs/heads/%s" % (REPO, BRANCH),
                  {"sha": commit["sha"]})
    got = patched.get("object", {}).get("sha")
    print("PATCH 返回 sha: %s" % got)
    if got != commit["sha"]:
        raise SystemExit("✗ PATCH 返回的 SHA 与目标不一致 ⇒ 停")

    # ⑦ ★ 复核 ref HEAD（这一步才能抓住"静默失败"）
    check = req("GET", "/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))
    head = check["object"]["sha"]
    print("复核 ref HEAD: %s" % head)
    if head != commit["sha"]:
        raise SystemExit("✗ ref HEAD 不等于目标 commit ⇒ 推分支静默失败")
    print("✅ ref HEAD == 目标 commit")

    # ⑧ 用权威接口核对内容（不用 raw —— CDN 缓存会骗人）
    t = req("GET", "/repos/%s/git/trees/%s?recursive=1" % (REPO, commit["sha"]))
    sizes = {x["path"]: x.get("size") for x in t.get("tree", [])}
    for st, path in files:
        local = os.path.getsize(path)
        remote = sizes.get(path)
        flag = "✔" if remote == local else "✘"
        print("  %s %-46s 本地 %-8s 远端 %s" % (flag, path[:46], local, remote))
        if remote != local:
            raise SystemExit("✗ size 对不上：%s（先查 ref HEAD，再查 CDN 缓存，最后才怀疑内容）" % path)


if __name__ == "__main__":
    main()
