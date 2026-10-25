# -*- coding: utf-8 -*-
"""★ 查远端 head 与基线 tree 的【路径级】blob sha（用于三方比对）
   用法：python3 _remote_probe.py <ref>
   ★ 只读，不改远端。
"""
import json
import os
import sys
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


def tree_blobs(tree_sha):
    out = {}
    t = req("/repos/%s/git/trees/%s?recursive=1" % (REPO, tree_sha))
    for e in t.get("tree", []):
        if e.get("type") == "blob":
            out[e["path"]] = e["sha"]
    return out


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "cmp8-handover-2026-10-20"
    h = req("/repos/%s/git/ref/heads/%s" % (REPO, ref))
    head = h["object"]["sha"]
    c = req("/repos/%s/git/commits/%s" % (REPO, head))
    tree = c["tree"]["sha"]
    print("HEAD  : %s" % head)
    print("TREE  : %s" % tree)
    print("MSG   : %s" % (c.get("message", "")[:120].replace("\n", " ")))
    bl = tree_blobs(tree)
    print("BLOBS : %d" % len(bl))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "_remote_tree.json")
    io = open  # noqa
    with open(out, "w", encoding="utf-8") as f:
        json.dump(bl, f, ensure_ascii=False, indent=0, sort_keys=True)
    print("写出  : %s" % out)


if __name__ == "__main__":
    main()
