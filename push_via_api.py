#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 GitHub REST API 推改动（git 客户端的 CA/凭据/网络都不可靠时的唯一路线）。

★ 不依赖 git fetch：远端 tree 的 blob sha 用 API 拿，本地 sha 用 `git hash-object` 算，
  只有**真正变了**的文件才建 blob。⇒ 幂等、无网络 git 依赖、不会漏。

★ 纪律（2026-10-20 实测踩坑）：
  ① PATCH /git/refs/heads/<branch> **可能静默失败**（不报错但 ref 没动）
     ⇒ 推完必须 `GET /git/refs/heads/<branch>` 把 SHA 与目标 commit **逐字比对**
  ② **别用 raw.githubusercontent 做校验**（有 CDN 缓存，会给你旧内容）
     ⇒ 用 /git/trees/<sha>?recursive=1 看 size，用 /contents/<path>?ref=<sha> 精确核对内容

★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
★ ★★ 2026-10-25 新增 `--only` 白名单模式（★ 治本，不是止血）★★
★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
★ **起因**：★ 共享 branch 上「本地树陈旧」时，★ **本脚本推的是【所有本地 blob 与远端不同】
  的文件** ⇒ ⇒ ⇒ **它【也会】把陈旧的本地版本推上去、覆盖别人** ⇒ ⇒ ⇒
  ⇒ ⇒ **⇒ 守卫只能拦住我，拦不住工具 ⇒ ⇒ ⇒ 必须从工具层改。**
★ **实测事故**：远端 blob 938 / 本地 773 / **同路径不同内容 11**（其中 7 处是我本轮没改、
  且本地比远端旧的文件）⇒ ⇒ 推上去就是第二组那次覆盖事故的同型形态。

★ **三条硬要求（负责人 2026-10-25 裁决）**：
  ① ★ **白名单之外的任何文件在结构上不可能被写** ⇒ ⇒ 只显式写白名单 blob，
     tree **以远端 base_tree 为底**（overlay 语义）⇒ ⇒ **绝不能"先写远端 tree 再改几个"**
     （★ 那是新一层覆盖风险）。
  ② ★ **推后必须逐 blob 核【远端有没有被别人更新过】** ⇒ ⇒ 拿【基线 tree】逐路径比 blob sha
     ⇒ ⇒ ★ 只核"远端独有丢失 = 0"不够（★ 那只证明没删文件，不证明没覆盖）。
  ③ ★ **远端 head 在复核与推送之间可能又变** ⇒ ⇒ **推前重读远端 head**，
     ★ 与做基线时的 head 不一致就**中止重取基线**（不推、不 force）。

★ **`--only` 模式下【绝不 force】**：★ 旧代码在 PATCH 失败时会改用 `force: true` 重试
  ⇒ ⇒ ⇒ **在共享 branch 上 force = 覆盖别人的全部工作** ⇒ ⇒ ⇒ **本模式直接禁掉 force**。
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


def remote_tree_of(sha):
    t = req("GET", "/repos/%s/git/trees/%s?recursive=1" % (REPO, sha))
    return {x["path"]: x["sha"] for x in t.get("tree", []) if x["type"] == "blob"}


def parse_args(argv):
    """→ (root, message, only_list, expect_base, dry_run)"""
    root = argv[0] if len(argv) > 0 else os.getcwd()
    msg = argv[1] if len(argv) > 1 else ""
    only, expect_base, dry_run = [], None, False
    i = 2
    while i < len(argv):
        a = argv[i]
        if a == "--only":
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                only.append(argv[i])
                i += 1
            continue
        if a == "--expect-base":
            i += 1
            expect_base = argv[i]
            i += 1
            continue
        if a == "--dry-run":
            dry_run = True
            i += 1
            continue
        raise SystemExit("✘ 未知参数 %r" % a)
    return root, msg, only, expect_base, dry_run


def main():
    root, msg, only, expect_base, dry_run = parse_args(sys.argv[1:])
    # ★ 2026-10-25：缺 message 直接报错 —— 【禁止 update】由工具强制，不靠自觉
    if not msg.strip():
        raise SystemExit("✘ 必须提供 commit message：python3 push_via_api.py <root> \"<message>\" [--only p1 p2 ...]")
    if msg.lower() in ("update", "update.", "wip", "tmp", "commit", "fix"):
        raise SystemExit("✘ 无信息量的 message 不允许：%r（格式：[组名] 一句话说明做了什么）" % msg)
    os.chdir(root)

    # ── 基线：远端 head + 远端 tree ────────────────────────────────
    ref = req("GET", "/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))
    base = ref["object"]["sha"]
    base_commit = req("GET", "/repos/%s/git/commits/%s" % (REPO, base))
    base_tree = base_commit["tree"]["sha"]
    remote = remote_tree_of(base_tree)
    print("base commit : %s" % base)
    print("base tree   : %s（%d 个 blob）" % (base_tree, len(remote)))

    if expect_base and not base.startswith(expect_base):
        raise SystemExit("✘ ★ 基线不符：--expect-base %s 但远端 head 是 %s ⇒ 中止（③：重取基线）"
                         % (expect_base, base))

    # ── 待推集合 ────────────────────────────────────────────────
    def _ls(args):
        out = subprocess.check_output(["git", "ls-files", "-z"] + args)
        return [x for x in out.decode("utf-8").split("\0") if x]

    if only:
        # ★★ ① 结构保证：只处理白名单路径 ⇒ ⇒ 白名单外的文件**根本不会进入 entries**
        missing = [p for p in only if not os.path.isfile(p)]
        if missing:
            raise SystemExit("✘ 白名单里有本地不存在的文件：%s" % missing)
        candidates = list(dict.fromkeys(only))
        mode = "only"
    else:
        candidates = _ls([]) + _ls(["--others", "--exclude-standard"])
        mode = "all"

    changed, skipped = [], []
    for p in candidates:
        if not os.path.isfile(p):
            skipped.append(p)
            continue
        if remote.get(p) != local_blob_sha(p):
            changed.append(p)
    if skipped:
        print("⚠️ 有 %d 个路径在磁盘上不存在（已跳过）：%s" % (len(skipped), skipped[:10]))
    if not changed:
        print("没有需要推送的改动（与远端逐 blob 比对一致）")
        return
    print("模式：%s ｜ 待推 %d 个文件" % ("★ --only 白名单" if only else "全量（★ 不推荐，共享 branch 上会回退陈旧本地）", len(changed)))

    # ── 建 blob + tree（★ base_tree = 远端 tree ⇒ overlay）────────
    entries = []
    for p in changed:
        raw = open(p, "rb").read()
        blob = req("POST", "/repos/%s/git/blobs" % REPO,
                   {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
        entries.append({"path": p, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("  blob %-46s %s" % (p[:46], blob["sha"][:10]))

    # ★★ 硬要求 ③：★ 推前【重读远端 head】★ 与基线不一致 ⇒ 中止（不 force、不推）
    head_now = req("GET", "/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))["object"]["sha"]
    if head_now != base:
        raise SystemExit("✘ ★★★ 远端 head 在【基线 → 现在】之间变了：%s → %s\n"
                         "    ⇒ 中止推分支，**不 force**（③：重取基线后重跑）\n"
                         "    ⇒ 共享 branch 上 force = 覆盖别人的全部工作。" % (base[:12], head_now[:12]))

    new_tree = req("POST", "/repos/%s/git/trees" % REPO,
                   {"base_tree": base_tree, "tree": entries})
    # ★★ ① 结构保证的【自证】：★ 新 tree 里凡不在白名单的路径，blob sha 必须与基线 tree **逐字相同**
    newt = remote_tree_of(new_tree["sha"])
    touched = set(changed)
    drift = [(p, remote.get(p), newt.get(p)) for p in newt
             if p not in touched and remote.get(p) != newt.get(p)]
    if drift:
        raise SystemExit("✘ ★★★ 白名单外有 %d 个路径的 blob 变了 ⇒ 结构保证被破坏 ⇒ 中止：%s"
                         % (len(drift), drift[:5]))
    print("✔ 结构保证自证：白名单外 %d 个路径的 blob sha 与基线 tree 逐字相同"
          % (len([p for p in newt if p not in touched])))

    if dry_run:
        print("")
        print("═══ --dry-run：到此为止，【不建 commit、不 PATCH ref】═══")
        print("将推 %d 个文件：%s" % (len(changed), changed))
        print("白名单外 %d 个路径的 blob sha 与基线 tree 逐字相同 ⇒ ★ 结构上不可能被写"
              % len([p for p in newt if p not in touched]))
        print("远端 head：%s（%s）" % (base, base[:12]))
        return

    commit = req("POST", "/repos/%s/git/commits" % REPO,
                 {"message": msg, "tree": new_tree["sha"], "parents": [base]})
    print("new commit  : %s" % commit["sha"])

    # ★★ 绝不 force（★ 共享 branch 上 force = 覆盖别人）
    patched = req("PATCH", "/repos/%s/git/refs/heads/%s" % (REPO, BRANCH),
                  {"sha": commit["sha"], "force": False})
    got = patched.get("object", {}).get("sha")
    if got != commit["sha"]:
        raise SystemExit("✘ PATCH 返回 sha=%s ≠ 目标 ⇒ **不 force**（共享 branch 上 force 会覆盖别人）" % got)

    head = req("GET", "/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))["object"]["sha"]
    if head != commit["sha"]:
        raise SystemExit("✗ ref HEAD 不等于目标 commit ⇒ 推分支静默失败")
    print("✔ ref HEAD == 目标 commit")

    # ★★ 硬要求 ②：★ 逐 blob 核【远端有没有被别人更新过】★★
    #   ★ 与【基线 tree】逐路径比 blob sha ⇒ ⇒ 白名单外的必须【逐字未变】
    final = remote_tree_of(commit["sha"])
    outside_changed = [p for p in final if p not in touched and remote.get(p) != final.get(p)]
    if outside_changed:
        print("❌ 白名单外有 %d 个路径被改了：%s" % (len(outside_changed), outside_changed[:10]))
        raise SystemExit("✗ 推送越界 ⇒ 立即回滚：把 ref 拨回 %s" % base)
    print("✔ 逐 blob 核：白名单外 %d 个路径全部逐字未变（不是只核「远端独有丢失=0」）"
          % len([p for p in final if p not in touched]))
    # 白名单内也要对得上本地
    bad = [p for p in changed if final.get(p) != local_blob_sha(p)]
    if bad:
        raise SystemExit("✗ 白名单内 %d 个文件远端 blob 与本地不一致：%s" % (len(bad), bad[:5]))
    print("✔ 白名单内 %d 个文件与本地逐字节一致" % len(changed))
    # 远端独有必须全保留
    lost = [p for p in remote if p not in final]
    if lost:
        raise SystemExit("✗ 远端独有 %d 个路径丢失" % len(lost))
    print("✔ 远端原有 %d 个路径全部保留" % len(remote))
    print("COMMIT=%s" % commit["sha"])


if __name__ == "__main__":
    main()
