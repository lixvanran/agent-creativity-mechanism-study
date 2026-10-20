#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 GitHub REST API 推改动（git 客户端的 CA/凭据/网络都不可靠时的唯一路线）。

★ 不依赖 git fetch：远端 tree 的 blob sha 用 API 拿，本地 sha 用 `git hash-object` 算，
  只有**真正变了**的文件才建 blob。⇒ 幂等、无网络 git 依赖、不会漏。

★ 纪律（2026-10-20 实测踩坑）：
  ① PATCH /git/refs/heads/<branch> **可能静默失败**（不报错但 ref 没动）
     ⇒ 推完必须 `GET /git/ref/heads/<branch>` 把 SHA 与目标 commit **逐字比对**
  ② **别用 raw.githubusercontent 做校验**（有 CDN 缓存，会给你旧内容）
     ⇒ 用 /git/trees/<sha>?recursive=1 看 size，用 /contents/<path>?ref=<sha> 精确核对内容
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
        raise SystemExit("✗ %s %s ⇒ HTTP %s: %s" % (method, path, e.code, e.read().decode()[:300]))


def local_blob_sha(path):
    return subprocess.check_output(["git", "hash-object", path], text=True).strip()


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    msg = sys.argv[2] if len(sys.argv) > 2 else "update"
    os.chdir(root)

    ref = req("GET", "/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))
    base = ref["object"]["sha"]
    base_commit = req("GET", "/repos/%s/git/commits/%s" % (REPO, base))
    base_tree = base_commit["tree"]["sha"]
    print("base commit : %s" % base)

    tree = req("GET", "/repos/%s/git/trees/%s?recursive=1" % (REPO, base_tree))
    remote = {t["path"]: t["sha"] for t in tree.get("tree", []) if t["type"] == "blob"}

    # 候选 = 本地所有跟踪文件 + 未跟踪文件
    files = [p for p in subprocess.check_output(["git", "ls-files"], text=True).splitlines() if p]
    files += [p for p in subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], text=True).splitlines() if p]

    changed = []
    for p in files:
        if not os.path.isfile(p):
            continue
        sha = local_blob_sha(p)
        if remote.get(p) != sha:
            changed.append(p)
    if not changed:
        print("没有需要推送的改动（与远端逐 blob 比对一致）")
        return
    print("待推 %d 个文件（其余 %d 个与远端逐字节一致）" % (len(changed), len(files) - len(changed)))

    entries = []
    for p in changed:
        raw = open(p, "rb").read()
        blob = req("POST", "/repos/%s/git/blobs" % REPO,
                   {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
        entries.append({"path": p, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("  blob %-46s %s" % (p[:46], blob["sha"][:10]))

    new_tree = req("POST", "/repos/%s/git/trees" % REPO,
                   {"base_tree": base_tree, "tree": entries})
    commit = req("POST", "/repos/%s/git/commits" % REPO,
                 {"message": msg, "tree": new_tree["sha"], "parents": [base]})
    print("new commit  : %s" % commit["sha"])

    patched = req("PATCH", "/repos/%s/git/refs/heads/%s" % (REPO, BRANCH),
                  {"sha": commit["sha"], "force": False})
    got = patched.get("object", {}).get("sha")
    if got != commit["sha"]:
        print("  PATCH 返回 sha=%s ≠ 目标 ⇒ 换 force 重试" % got)
        patched = req("PATCH", "/repos/%s/git/refs/heads/%s" % (REPO, BRANCH),
                      {"sha": commit["sha"], "force": True})
        got = patched.get("object", {}).get("sha")
    print("PATCH 返回 sha: %s" % got)

    head = req("GET", "/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))["object"]["sha"]
    print("复核 ref HEAD: %s" % head)
    if head != commit["sha"]:
        raise SystemExit("✗ ref HEAD 不等于目标 commit ⇒ 推分支静默失败")

    t = req("GET", "/repos/%s/git/trees/%s?recursive=1" % (REPO, commit["sha"]))
    sizes = {x["path"]: x.get("size") for x in t.get("tree", [])}
    bad = 0
    for p in changed:
        loc, rem = os.path.getsize(p), sizes.get(p)
        if loc != rem:
            print("  ✘ %-46s 本地 %s 远端 %s" % (p[:46], loc, rem))
            bad += 1
    if bad:
        raise SystemExit("✗ 有 %d 个文件 size 对不上" % bad)
    print("✅ ref HEAD == 目标 commit ｜ %d 个文件 size 全部对上" % len(changed))
    print("COMMIT=%s" % commit["sha"])


if __name__ == "__main__":
    main()
