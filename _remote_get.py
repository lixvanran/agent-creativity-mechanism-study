# -*- coding: utf-8 -*-
"""★ 从 GitHub API 取远端文件内容（★ 本地 git 没有 API 建的 commit 对象时用）
   用法：python3 _remote_get.py <path> [ref] > 本地临时文件
"""
import base64
import json
import os
import sys
import urllib.parse
import urllib.request

REPO = "lixvanran/agent-creativity-mechanism-study"
TOKEN = os.environ.get("GITHUB_TOKEN_LIXVANRAN", "")
if not TOKEN:
    raise SystemExit("✘ 没有 GITHUB_TOKEN_LIXVANRAN")


def req(path):
    u = "https://api.github.com" + path
    r = urllib.request.Request(u, headers={
        "Authorization": "Bearer " + TOKEN,
        "User-Agent": "mavis-g3",
        "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.load(f)


def get_file(path, ref):
    """★ 优先用 blob API（大文件 contents API 不内联）"""
    try:
        b = req("/repos/%s/contents/%s?ref=%s"
                % (REPO, urllib.parse.quote(path), ref))
        if b.get("encoding") == "base64" and b.get("content"):
            return base64.b64decode(b["content"])
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    # 回退：按 tree 找 blob
    head = req("/repos/%s/git/ref/heads/%s" % (REPO, ref))["object"]["sha"]
    c = req("/repos/%s/git/commits/%s" % (REPO, head))
    t = req("/repos/%s/git/trees/%s?recursive=1" % (REPO, c["tree"]["sha"]))
    sha = None
    for e in t.get("tree", []):
        if e.get("path") == path and e.get("type") == "blob":
            sha = e["sha"]
            break
    if not sha:
        raise SystemExit("✘ 远端没有这个路径：%s" % path)
    blob = req("/repos/%s/git/blobs/%s" % (REPO, sha))
    return base64.b64decode(blob["content"])


if __name__ == "__main__":
    p = sys.argv[1]
    ref = sys.argv[2] if len(sys.argv) > 2 else "cmp8-handover-2026-10-20"
    data = get_file(p, ref)
    sys.stdout.buffer.write(data)
