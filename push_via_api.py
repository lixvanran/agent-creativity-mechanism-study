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
    # ★ 2026-10-24：缺 message 直接报错 —— 【禁止 update】由工具强制，不靠自觉
    #   （此前默认 "update" ⇒ 远端叠加层全叫 update ⇒ 归属不可查）
    if len(sys.argv) <= 2 or not sys.argv[2].strip():
        raise SystemExit("✘ 必须提供 commit message：python3 push_via_api.py <ref-or-branch> \"<message>\"")
    msg = sys.argv[2].strip()
    if msg.lower() in ("update", "update.", "wip", "tmp", "commit", "fix"):
        raise SystemExit("✘ 无信息量的 message 不允许：%r（格式：[组名] 一句话说明做了什么）" % msg)
    os.chdir(root)

    ref = req("GET", "/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))
    base = ref["object"]["sha"]
    base_commit = req("GET", "/repos/%s/git/commits/%s" % (REPO, base))
    base_tree = base_commit["tree"]["sha"]
    print("base commit : %s" % base)

    tree = req("GET", "/repos/%s/git/trees/%s?recursive=1" % (REPO, base_tree))
    remote = {t["path"]: t["sha"] for t in tree.get("tree", []) if t["type"] == "blob"}

    # 候选 = 本地所有跟踪文件 + 未跟踪文件
    # ★ 2026-10-21 修一个**静默丢文件**的 bug：
    #   `git ls-files`（不带 -z）默认把**非 ASCII 文件名加引号并转义成八进制**
    #   （如 "docs/.../fig1_\346\265\213...png"）⇒ 该路径在磁盘上不存在
    #   ⇒ os.path.isfile() 为 False ⇒ **该文件被跳过**
    #   ⇒ 而脚本还会报"没有需要推送的改动" ⇒ 看起来像成功的空操作。
    #   实测后果：**所有中文名文件从未被推上远端**（含 6 张流程图 PNG）。
    #   修法：用 `-z`（NUL 分隔、不转义）并按 \0 切分。
    def _ls(args):
        out = subprocess.check_output(["git", "ls-files", "-z"] + args)
        return [x for x in out.decode("utf-8").split("\0") if x]
    files = _ls([])
    files += _ls(["--others", "--exclude-standard"])

    changed, skipped = [], []
    for p in files:
        if not os.path.isfile(p):
            skipped.append(p)          # ★ 记下来，别再静默吞掉
            continue
        sha = local_blob_sha(p)
        if remote.get(p) != sha:
            changed.append(p)
    if skipped:
        print("⚠️ 有 %d 个跟踪文件在磁盘上不存在（已跳过，未推送）：" % len(skipped))
        for p in skipped[:10]:
            print("   - %s" % p)
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
    # ★ 防呆：远端必须包含**全部**本地跟踪文件（含中文名）。
    #   以前没有这道核对 ⇒ 中文名文件缺失时脚本仍报"成功"。
    tracked = [p for p in _ls([]) if os.path.isfile(p)]
    missing = [p for p in tracked if p not in sizes]
    if missing:
        print("❌ 远端树缺 %d 个本地跟踪文件（未推送成功）：" % len(missing))
        for p in missing[:15]:
            print("   - %s" % p)
        raise SystemExit("✗ 推送不完整")
    print("✅ 远端树含全部 %d 个本地跟踪文件（含中文名）" % len(tracked))
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
