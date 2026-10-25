#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ **叠加式推送（★ 2026-10-25）—— 不丢远端任何文件**

★ **★ 为什么是"叠加"而不是"覆盖"（★ 硬判据）★**
★ · 远端 `cmp8-handover-2026-10-20` head = `895f7258b923`（★ 810 个 blob）
★ · 本地 HEAD = 821 个 blob
★ · ★★ **逐路径比对：★ 远端【独有 105 个】、本地【独有 166 个】、同路径不同内容 30 个** ★★
★ ⇒ ⇒ ★ **★ ⇒ force push 会【真丢那 105 个文件】★★ ⇒ ⇒ ★ ⇒ ★ **★ 绝不 force ★★**

★ **★ 本脚本的语义 ★★**
★ ① base = ★ **远端 head 的 tree**（★ 原样保留，★ 不删任何远端路径）
★ ② 叠加层 = ★ **本地独有的 166 个 + 同路径内容不同的 30 个**（★ ★ ★ 只加/改，★ ★ 不删 ★）
★ ③ 新 commit 的 parent = ★ **远端 head** ⇒ ⇒ ★ ⇒ **★ 远端历史【完整保留】，★ 不 force ★**
★ ④ `PATCH /git/refs` 带 `force: false` ⇒ ⇒ ★ ⇒ **★ 不快进会被 GitHub 直接拒（★ 双保险）★★**

★ **★ 可追溯性（★ 替掉"逐 commit 推"的粒度）★★**
★ · commit message 里写明：★ "★ 本地分支 N 个 commit 的最终状态，★ 叠加在远端 head 之上 ★"
★ · 并附【本地 40 个 commit 的 sha + 标题】清单 ⇒ ⇒ ★ ⇒ ★ **★ 逐条可追溯 ★★**

★ **★ 自带校验 ★★**
★ · 每个上传的 blob：★ 远端返回的 sha 必须 == 本地 sha
★ · 推完：★ 回读远端 ref sha，★ 并核【远端那 105 个独有文件仍全部在】★ ★⇒ ⇒ ★ ⇒ **★ 证明没丢东西 ★★**
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


def git(*a, binary=False):
    r = subprocess.run(("git",) + a, capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode("utf-8")


class Gh:
    def __init__(self, token, repo):
        self.token, self.repo, self.n = token, repo, 0

    def _req(self, method, path, body=None):
        url = "%s/repos/%s%s" % (API, self.repo, path)
        data = json.dumps(body).encode() if body is not None else None
        h = {"Accept": "application/vnd.github+json", "Authorization": "Bearer " + self.token,
             "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "mavis-push"}
        if data:
            h["Content-Type"] = "application/json"
        last = None
        for k in range(5):
            try:
                req = urllib.request.Request(url, data=data, headers=h, method=method)
                with urllib.request.urlopen(req, timeout=60) as r:
                    self.n += 1
                    t = r.read().decode()
                    return json.loads(t) if t else {}
            except urllib.error.HTTPError as e:
                txt = e.read().decode("utf-8", "replace")
                last = "HTTP %s %s" % (e.code, txt[:200])
                if e.code == 422:
                    raise RuntimeError("%s %s ⇒ %s" % (method, path, last))
                time.sleep(5 + k * 5)
            except Exception as e:
                last = "%s: %s" % (type(e).__name__, e)
                time.sleep(3 + k * 3)
        raise RuntimeError("%s %s ⇒ 重试耗尽: %s" % (method, path, last))

    def get(self, p):
        return self._req("GET", p)

    def post(self, p, b):
        return self._req("POST", p, b)

    def patch(self, p, b):
        return self._req("PATCH", p, b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN_LIXVANRAN", ""))
    ap.add_argument("--repo-path", default="/workspace/lab")
    ap.add_argument("--local-branch", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    os.chdir(a.repo_path)
    lb = a.local_branch or a.branch

    gh = Gh(a.token, a.repo)
    ref = gh.get("/git/ref/heads/%s" % a.branch)
    remote_head = ref["object"]["sha"]
    rc = gh.get("/git/commits/%s" % remote_head)
    remote_tree = rc["tree"]["sha"]   # ★ GET /git/commits/<sha> ⇒ git commit 对象 ⇒ tree 在顶层
    print("═══ 远端 head = %s ｜ tree = %s" % (remote_head[:12], remote_tree[:12]))

    # ★ 远端 tree 全量
    rt = gh.get("/git/trees/%s?recursive=1" % remote_tree)
    rmap = {e["path"]: e["sha"] for e in rt.get("tree", []) if e["type"] == "blob"}
    # ★ 本地 tree 全量
    lmap = {}
    # ★ ★ 必须用 -z（★ 记忆里那条纪律：★ git ls-files/ls-tree 对非 ASCII 路径会【转义】⇒ ⇒
    # ★ ★ 不加 -z ⇒ ⇒ 路径变成 \\344\\272... ⇒ ⇒ 传到远端就是乱码文件名 ★★）
    for rec in git("ls-tree", "-r", "-z", lb, binary=True).split(b"\x00"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        lmap[path.decode("utf-8")] = meta.decode().split()[2]
    only_remote = sorted(set(rmap) - set(lmap))
    only_local = sorted(set(lmap) - set(rmap))
    changed = sorted(p for p in set(rmap) & set(lmap) if rmap[p] != lmap[p])
    print("  远端 blob %d ｜ 本地 blob %d" % (len(rmap), len(lmap)))
    print("  ★ 远端独有 %d（★ ★ 全部保留，★ 不删）" % len(only_remote))
    print("  ★ 本地独有 %d（★ 要叠加）" % len(only_local))
    print("  ★ 同路径不同内容 %d（★ 要覆盖）" % len(changed))
    todo = only_local + changed
    if a.dry_run:
        print("  ── 将上传 %d 个 blob ──" % len(todo))
        for p in todo[:20]:
            print("     ", p)
        if len(todo) > 20:
            print("      ... 还有 %d 个" % (len(todo) - 20))
        return 0

    # ★ 逐个上传 blob（★ ★ 远端返回 sha 必须 == 本地 sha ⇒ ⇒ ★ 内容篡改当场暴露）
    entries = []
    up = 0
    skipped = 0
    for i, p in enumerate(todo):
        sha = lmap[p]
        # ★ 单文件查 mode ⇒ 也要 -z（★ 否则中文路径查不到 ⇒ ⇒ mode 退化成 100644）
        rec = git("ls-tree", "-z", lb, "--", p, binary=True)
        mode = "100644"
        for r in rec.split(b"\x00"):
            if r:
                mode = r.split(b"\t", 1)[0].decode().split()[0]
                break
        try:
            gh.get("/git/blobs/%s" % sha)
            skipped += 1
        except Exception:
            content = git("cat-file", "blob", sha, binary=True)
            r = gh.post("/git/blobs", {"content": base64.b64encode(content).decode(),
                                       "encoding": "base64"})
            if r.get("sha") != sha:
                print("✘ blob sha 不符 ★ %s ⇒ 停止" % p)
                return 1
            up += 1
        entries.append({"path": p, "mode": mode, "type": "blob", "sha": sha})
        if (i + 1) % 25 == 0:
            print("  ✔ blob %d/%d（★ 新上传 %d / 远端已有 %d）" % (i + 1, len(todo), up, skipped))

    # ★ 建 tree（★ base_tree = 远端 tree ⇒ ⇒ ★ ★ 远端文件一个不删 ★）
    t = gh.post("/git/trees", {"base_tree": remote_tree, "tree": entries})
    print("★ 新 tree = %s" % t["sha"][:12])

    # ★ 附本地 40 个 commit 清单（★ ⇒ 可追溯性用清单保住）
    hist = []
    for c in git("log", "--reverse", "--format=%H", lb).split():
        hist.append("%s  %s" % (c[:10], git("log", "-1", "--format=%s", c).strip()))
    msg = ("第二组 · 交付 2026-10-25（★ 叠加在远端 head %s 之上）\n\n"
           "★ 本地分支 %s 的 %d 个 commit 的【最终状态】，★ 以【叠加】方式接在远端 head 之后。\n"
           "★ ★ 语义：★ 远端独有的 %d 个路径【全部保留】、★ 不删任何远端文件；★ ★ "
           "叠加本地独有的 %d 个 + 更新 %d 个。\n"
           "★ ★ 为何不 force：★ 远端有 %d 个本地没有的文件（★ 含 docs/cmp8/PAPER-2026-10-25.md、★ "
           "docs/cmp8/figures/*、★ docs/cmp8/routes/COLLAPSE/*）★ ⇒ ⇒ force 会真丢它们。\n"
           "★ ★ 已知结构问题：★ 远端存在 docs/cmp8/creativity_lab/ 布局，★ 本地为 creativity_lab/ ⇒ ⇒ "
           "叠加后两份并存（★ ★ 待负责人裁决是否统一布局）。\n\n"
           "★ 本地 commit 清单（★ 逐条可追溯）：\n%s\n"
           % (remote_head[:12], lb, len(hist), len(only_remote), len(only_local), len(changed),
              len(only_remote), "\n".join(hist)))

    nc = gh.post("/git/commits", {
        "message": msg, "tree": t["sha"], "parents": [remote_head],
        "author": {"name": "Mavis", "email": "mavis@local", "date": "2026-10-25T00:00:00Z"},
        "committer": {"name": "Mavis", "email": "mavis@local", "date": "2026-10-25T00:00:00Z"}})
    print("★ 新 commit = %s" % nc["sha"][:12])

    # ★ ★ 非 force PATCH（★ 不快进会被 GitHub 直接拒 ⇒ ⇒ 双保险）★★
    gh.patch("/git/refs/heads/%s" % a.branch, {"sha": nc["sha"], "force": False})
    print("★ PATCH ref（非 force）⇒ ok")

    # ★ ★ 复核：★ 远端 ref == 新 commit，★ 且【远端那 105 个独有文件仍全部在】★★
    got = gh.get("/git/ref/heads/%s" % a.branch)["object"]["sha"]
    assert got == nc["sha"], "远端 ref 不符"
    nt = gh.get("/git/trees/%s?recursive=1" % gh.get("/git/commits/%s" % got)["tree"]["sha"])
    nmap = {e["path"]: e["sha"] for e in nt.get("tree", []) if e["type"] == "blob"}
    lost = [p for p in only_remote if p not in nmap]
    changed_bad = [p for p in changed if nmap.get(p) != lmap[p]]
    missing = [p for p in only_local if p not in nmap]
    print("★ 复核：★ 远端 ref = %s ✔" % got[:12])
    print("  ★ 远端独有文件丢失：%d（★ 应 0）" % len(lost))
    print("  ★ 同路径更新未生效：%d（★ 应 0）" % len(changed_bad))
    print("  ★ 本地独有未落：%d（★ 应 0）" % len(missing))
    print("  ★ 远端总 blob %d" % len(nmap))
    print("★ 本次 API 调用 %d 次" % gh.n)
    return 0 if not (lost or changed_bad or missing) else 1


if __name__ == "__main__":
    sys.exit(main())
