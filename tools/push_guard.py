# -*- coding: utf-8 -*-
"""★ 推送前【同路径不同内容 ≠ 本组要改】守卫（★ 2026-10-25 第二组事故的根治）
★ 背景：第二组的 push_overlay.py 把同路径不同内容一律当"本组要改"⇒ 覆盖了别人的 31 个文件。
★ 本守卫做同一件事的预防：推之前，比对
★   ① 远端 head 的树    ② 我上次推送时的树    ③ 我当前的树
★ 凡是【远端变了、而我没动过】的路径 ⇒ 判为冲突 ⇒ 拒绝推送（exit 3），
★ 除非显式 --allow-conflict。★ 不区分归属就一定会覆盖别人的工作。
"""
import io
import json
import os
import subprocess
import sys
import urllib.request

REPO = "lixvanran/agent-creativity-mechanism-study"
BRANCH = "cmp8-handover-2026-10-20"
TOK = os.environ.get("GITHUB_TOKEN_LIXVANRAN", "")
ROOT = "/workspace/lab/cmp8repo"
STATE = os.path.join(ROOT, ".mavis", "push_state.json")


def api(path):
    r = urllib.request.Request("https://api.github.com" + path, headers={
        "Authorization": "Bearer " + TOK,
        "Accept": "application/vnd.github+json",
        "User-Agent": "mavis-push-guard"})
    return json.load(urllib.request.urlopen(r, timeout=30))


def remote_tree_files(tree_sha):
    """远端 tree → {path: blob_sha}（递归）"""
    out = {}
    stack = [tree_sha]
    while stack:
        t = api("/repos/%s/git/trees/%s" % (REPO, stack.pop()))
        for it in t.get("tree", []):
            if it["type"] == "blob":
                out[it["path"]] = it["sha"]
            elif it["type"] == "tree" and it["sha"] not in stack:
                stack.append(it["sha"])
    return out


def local_tree_files():
    out = {}
    for line in subprocess.check_output(
            ["git", "-C", ROOT, "ls-files", "-s"], text=True).split("\n"):
        if not line.strip():
            continue
        meta, path = line.split("\t", 1)
        sha = meta.split()[1]
        out[path] = sha
    return out


def main():
    allow = "--allow-conflict" in sys.argv
    head = api("/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))["object"]["sha"]
    remote = remote_tree_files(api("/repos/%s/git/commits/%s" % (REPO, head))["tree"]["sha"])
    local = local_tree_files()
    prev = {}
    if os.path.exists(STATE):
        prev = json.load(io.open(STATE, encoding="utf-8")).get("tree_files", {})
    else:
        # 首次：没有上次状态 ⇒ 把"远端独有、我本地没有"的路径视为别人的，不动
        prev = {k: v for k, v in remote.items() if k not in local}
    mine_changed = {k for k in set(local) | set(prev) if local.get(k) != prev.get(k)}
    conflicts = []
    for p in set(remote) | set(local):
        r, l, pv = remote.get(p), local.get(p), prev.get(p)
        if r == l:
            continue
        if p not in mine_changed:            # ★ 远端变了、我没动过 ⇒ 冲突
            conflicts.append((p, r, l))
    print("  远端 head: %s" % head[:12])
    print("  我上次推的树: %d 个路径 ｜ 当前本地树: %d 个路径" % (len(prev), len(local)))
    print("  我本次改动的路径: %d 个" % len(mine_changed))
    if conflicts:
        print("  ✘ 冲突（远端改过、我没动过 ⇒ 推上去会覆盖别人的）: %d 个" % len(conflicts))
        for p, r, l in conflicts[:12]:
            print("     - %-52s 远端=%s 本地=%s" % (p[:52], (r or "-")[:8], (l or "-")[:8]))
        if not allow:
            print("  ⇒ 拒绝推送（exit 3）｜ 确认要覆盖请显式加 --allow-conflict")
            raise SystemExit(3)
        print("  ⇒ ★ --allow-conflict 已给 ⇒ 继续（★ 这次覆盖是有意的）")
    else:
        print("  ✔ 无冲突（★ 远端没有『我没动过却被改了』的路径）")
    # 记状态
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(dict(branch=BRANCH, head=head, tree_files=local),
              io.open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
    print("  ⇒ 状态已记：%s" % STATE)


if __name__ == "__main__":
    main()
