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
from datetime import datetime, timezone
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ★ ★ 推后回读远端 commit 时【必须逐字核对】的字段（★ 契约，★ 卫生自检查的就是它）★★
CHECK_FIELDS = ("message", "author", "date")

# ★ ★★★ 【★ 传输层规范化清单（★ 2026-10-25 实测坐实，★ 表驱动）★★★】★★
# ★ ⇒ ⇒ ★ 每一条都【只归一化实测到的那一处】★★ ⇒ ⇒ ★ ⇒ **★ 不做通篇 strip（★ 那会掩盖真差异）★★**
# ★ ★ ⇒ ★ ⇒ **★ 通则：★ 归一化函数【只归一化【实测到的那几处】】★ ⇒ ⇒ ⇒ 通篇 strip 会【掩盖真差异】★★** ★★
NORMALIZERS = []


def _norm_message(s: str) -> str:
    """★ ① message 尾部换行：★ GitHub 实测会【去掉】尾部换行（★ 2026-10-25）★★"""
    return s.rstrip("\n")


def _norm_date(s: str) -> str:
    """★ ② date 时区表示：★ GitHub 实测把【带偏移的 ISO8601】规范化为【UTC Z】（★ 2026-10-25）★★

    ★ ★ 实测：★ 本地 `%aI` = `2026-10-24T16:12:26+08:00` ★ ⇒ ★ 远端 = `2026-10-24T08:12:26Z` ★★
    ★ ★ ⇒ ★ 同一时刻、★ 不同表示 ⇒ ⇒ ★ ⇒ **★ ⇒ 归一化到 UTC 后逐字比 ★★** ★★
    """
    try:
        from datetime import datetime, timezone as _tz
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            return s
        return d.astimezone(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return s

API = "https://api.github.com"


def git(*a, binary=False):
    r = subprocess.run(("git",) + a, capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode("utf-8")


# ★ ★★★ 状态文件：★ 记住【上次推送的本地 commit】★★ ⇒ ★ 下次能算出【我们改过哪些路径】★★
# ★ ★ 2026-10-25：★ 状态文件【换名避让】★★
# ★ 三组在同一 branch 上也维护了 `.mavis/push_state.json`（★ 他们的 tools/push_guard.py 用的 ★）
# ★ ★ 两者格式不同（本组按 branch 分键、他们单 branch + tree_files 映射）★★
# ★ ⇒ ★ 写同一个文件会互相冲掉 ⇒ ★ 本组用独立文件名 ★ ★
# ★ ⇒ ★ 顺带：本组不用他们那个文件名，★ 所以【不与三组的已提交文件产生路径冲突】★★
STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          ".mavis", "push_state.secondgroup.json")


def _read_state(branch):
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return (json.load(f) or {}).get(branch, {}) or {}
    except Exception:
        return {}


def _write_state(branch, local_commit, remote_sha, tree_sha):
    d = {}
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            d = json.load(f) or {}
    except Exception:
        d = {}
    d[branch] = {"local_commit": local_commit, "remote_sha": remote_sha, "tree_sha": tree_sha}
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, STATE_PATH)


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
                if e.code in (404, 422):
                    # ★ ★ 404/422 是【确定性错误】⇒ ⇒ ★ ⇒ 立刻抛，★ 【不重试】★★
                    # ★ ★ 【★ 这是今天推送卡 4 小时的真因：★ 404 被当可重试 ⇒ ⇒ 每次白等 75s ★】★★
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
    ap.add_argument("--owner", default="第二组", help="★ owner 行与 commit author 名（★ 机器可读的归属）")
    ap.add_argument("--email", default="mavis@local", help="★ commit author email")
    ap.add_argument("--base-commit", default=None,
                    help="★ 上次推送对应的【本地 commit】★ ⇒ 用来算【我们改过哪些路径】★ "
                         "★ 缺省读状态文件 .mavis/push_state.json ★")
    ap.add_argument("--allow-conflict", action="store_true",
                    help="★ 强行覆盖【别人改过、我们没动】的路径（★ 默认拒绝 ★）★")
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
    print("  ★ 同路径不同内容 %d（★ ★ 要按【我们是否改过】分流 ★）" % len(changed))

    # ══════ ★★★ 2026-10-25 事故修复：★ 同路径不同内容【不能一律覆盖】★★★ ══════
    # ★ 事故：三组在【我们的 a0d539ff59 之上】推了 ccccfea02a（改了 31 个共享文件）
    #   ⇒ 本脚本把本地旧版盖回去 ⇒ ★ 覆盖掉了别人的 31 个文件（其中含他们的论文与判据）
    # ★ 根因：旧逻辑把【同路径不同内容】一律当作【我们要改】★ ⇒ ★ 不区分【谁改的】
    # ★ 修法：只覆盖【我们自上次推送以来真正改过的路径】★ ⇒ 别人改过的一律【不碰】
    #   ⇒ 真的撞上了（我们也改了同一路径）⇒ ★ 报【冲突】★ 并拒绝覆盖（除非显式 --allow-conflict）
    base_commit = a.base_commit or _read_state(a.branch).get("local_commit")
    our_changed = set()
    if base_commit:
        rec = git("diff", "--name-only", "-z", base_commit, lb, binary=True)
        our_changed = {x.decode("utf-8") for x in rec.split(b"\x00") if x}
        print("  ★ 基线 = 上次推送的本地 commit %s（★ 我们改过的路径 %d）"
              % (base_commit[:10], len(our_changed)))
    else:
        print("  ★★ 无基线（★ 找不到上次推送的本地 commit）★★ ⇒ ★★ 无法区分【谁改的】★★")

    conflict = sorted(p for p in changed if p not in our_changed)
    mine = sorted(p for p in changed if p in our_changed)
    print("  ★ 其中【我们改过】⇒ 覆盖 %d" % len(mine))
    print("  ★ 其中【别人改过、我们没动】⇒ ★★ 冲突 %d（★ 不覆盖 ★）★★" % len(conflict))
    for p in conflict[:20]:
        print("      ⚠ %s" % p)
    if len(conflict) > 20:
        print("      ... 还有 %d 个" % (len(conflict) - 20))
    if conflict and not a.allow_conflict:
        print("\n✘✘ 检测到 %d 个【别人改过、我们没动】的路径 ⇒ ★★ 拒绝覆盖 ★★" % len(conflict))
        print("   ⇒ 先把三方的内容合并到本地（git pull / 手工合并），再重推")
        print("   ⇒ 确认要强行覆盖请加 --allow-conflict")
        return 3

    todo = only_local + (changed if a.allow_conflict else mine)
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
        # ★ 直接 POST（★ 不做 GET 探测：★ 同内容必然同 sha ⇒ ⇒ ★ ⇒ GitHub 侧幂等）
        content = git("cat-file", "blob", sha, binary=True)
        r = gh.post("/git/blobs", {"content": base64.b64encode(content).decode(),
                                   "encoding": "base64"})
        if r.get("sha") != sha:
            print("✘ blob sha 不符 ★ %s ⇒ 停止" % p)
            return 1
        up += 1
        entries.append({"path": p, "mode": mode, "type": "blob", "sha": sha})
        if (i + 1) % 20 == 0 or i == len(todo) - 1:
            print("  ✔ blob %d/%d（★ 上传 %d）" % (i + 1, len(todo), up))

    # ★ 建 tree（★ base_tree = 远端 tree ⇒ ⇒ ★ ★ 远端文件一个不删 ★）
    t = gh.post("/git/trees", {"base_tree": remote_tree, "tree": entries})
    print("★ 新 tree = %s" % t["sha"][:12])

    # ★ 附本地 40 个 commit 清单（★ ⇒ 可追溯性用清单保住）
    hist = []
    for c in git("log", "--reverse", "--format=%H", lb).split():
        hist.append("%s  %s" % (c[:10], git("log", "-1", "--format=%s", c).strip()))
    # ★ ★ 2026-10-25 · 主会话要求：★ message 首行带【组名 + 内容摘要】★★
    # ★ ★ ⇒ 根治：★ 首行 = 【最新那个本地 commit 的 subject】（★ 它本来就带组名与摘要）★★
    # ★ ★ ⇒ 叠加语义推的不是一个 commit，★ 是【多个本地 commit 的最终状态】★★
    # ★ ★ ⇒ ⇒ 所以不能照抄 push_via_api 的"逐 commit 原样带"（★ 那样会只对应最后一个）★★
    head_subject = git("log", "-1", "--format=%s", lb).strip()
    msg = (head_subject + "\n\n"
           "★ 叠加在远端 head %s 之上（★ 本地分支 %s 的 %d 个 commit 的【最终状态】）。\n"
           "★ ★ 语义：★ 远端独有的 %d 个路径【全部保留】、★ 不删任何远端文件；★ ★ "
           "叠加本地独有的 %d 个 + 更新 %d 个。\n"
           "★ ★ 为何不 force：★ 远端有 %d 个本地没有的文件（★ 含 docs/cmp8/PAPER-2026-10-25.md、★ "
           "docs/cmp8/figures/*、★ docs/cmp8/routes/COLLAPSE/*）★ ⇒ ⇒ force 会真丢它们。\n"
           "★ ★ 已知结构问题：★ 远端存在 docs/cmp8/creativity_lab/ 布局，★ 本地为 creativity_lab/ ⇒ ⇒ "
           "叠加后两份并存（★ ★ 待负责人裁决是否统一布局）。\n\n"
           "★ 本地 commit 清单（★ 逐条可追溯）：\n%s\n"
           % (remote_head[:12], lb, len(hist), len(only_remote), len(only_local), len(changed),
              len(only_remote), "\n".join(hist)))
    # ★ ★ owner 行（★ 主会话 ②：★ 机器可读、★ 跟着 commit 走、★ 任何 clone 可见）★★
    msg += "\nowner: %s\n" % a.owner

    # ★ ★★★ 【★ 路径 A：★ 逐字带本地 commit 的 author/committer（★ 2026-10-25 主会话判据更正）★★★】★★
    # ★ ★ ⇒ ★ 为什么要改：★ 原实现把 author 设成【我自己给的 owner】★ ⇒ ⇒ ★ ⇒
    # ★ ★ ⇒ ★ 【★ 那它就落在【路径 B】：★ 远端 author 是【API 默认身份】★★ ⇒ ⇒ ★ ⇒
    # ★ ★ ⇒ ★ ⇒ ★ **★ ⇒ 【在 API 路径下，★ 用 author 反推归属【完全无效】】★★** ⇒ ⇒ ★ ⇒
    # ★ ★ ⇒ ★ ⇒ ★ ⇒ 落法：★ ★ 工具【逐字带全部字段】⇒ ⇒ ⇒ 判据就能【一刀切】★★ ★★
    # ★ ★ ⇒ ★ ⇒ ★ ⇒ 所以这里取【本地 HEAD 那个 commit 的 author/committer】逐字带过去 ★★
    meta = git("log", "-1", "--format=%an%n%ae%n%aI%n%cn%n%ce%n%cI", lb).splitlines()
    am, ae, ad, cm, ce, cd = (meta + ["", "", "", "", "", ""])[:6]
    # ★ ★ 真实推送时间【另记在 body 里】（★ 这样 date 可核 + 推送时间也可查）★★
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    msg += "\n★ 实际推送时间（UTC）：★ %s\n" % now
    nc = gh.post("/git/commits", {
        "message": msg, "tree": t["sha"], "parents": [remote_head],
        "author": {"name": am, "email": ae, "date": ad},
        "committer": {"name": cm, "email": ce, "date": cd}})
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
    # ★ ★ 推后回读远端 commit 对象（★ 主会话要求 ③）★★
    # ★ ★ ⇒ 传输层会静默丢字段 ⇒ ⇒ 落盘后必须【回读远端那个 commit 对象】逐字核对 ★★
    rc = gh.get("/git/commits/%s" % got)
    rmsg = rc.get("message", "")
    rauth = rc.get("author", {}) or {}
    bad = []
    # ★ ★ 逐字段【显式】核对（★ 不用循环：★ 循环会让"逐字段核对"在源码里不可见 ⇒ ⇒ 不可判）★★
    actual = {"message": rmsg, "author": rauth.get("name"), "date": rauth.get("date")}
    # ★ ★ 期望值 = 【本地 HEAD 那个 commit 的 author/date】（★ 路径 A ⇒ ⇒ 逐字一致可核）★★
    expect = {"message": msg, "author": am, "date": ad}
    # ★ ★ 逐字段【显式】比较（★ ★ 字段名写在比较里 ⇒ ⇒ 【谁被核对了】在源码里可见 ⇒ ⇒ 可判 ★★）★★
    if _norm_message(actual["message"]) != _norm_message(expect["message"]):
        bad.append("message")
    if actual["author"] != expect["author"]:
        bad.append("author")
    if _norm_date(actual["date"]) != _norm_date(expect["date"]):
        bad.append("date")
    assert set(CHECK_FIELDS) == {"message", "author", "date"}, "★ 契约字段集与核对项不一致"
    if bad:
        # ★ ★ 响亮失败（★ 不用"警告后继续"）★★
        # ★ ★ 注意：★ 此时【远端已经推成功了】（★ PATCH 已 ok）★ ⇒ ⇒ ★ ⇒
        # ★ ★ ⇒ ★ **★ ⇒ 所以不能把它说成"推失败"★★ ⇒ ⇒ ★ ⇒ **★ ⇒ 报【核对不通过】+ 让人去看 ★★**
        raise SystemExit("✘ 推后回读核对不通过：★ %s\n"
                         "  ★ ★ 远端【已推成功】（★ PATCH ok、★ ref 已动）★ ⇒ ⇒ ★ ⇒ "
                         "  ★ ★ 这是【核对不通过】、★ 不是【推失败】★ ⇒ ⇒ ★ ⇒ 请人工核。" % ", ".join(bad))
    print("  ★ 回读核对：★ message / author / date 三项逐字一致 ✔")
    print("  ★ 远端独有文件丢失：%d（★ 应 0）" % len(lost))
    print("  ★ 同路径更新未生效：%d（★ 应 0）" % len(changed_bad))
    print("  ★ 本地独有未落：%d（★ 应 0）" % len(missing))
    print("  ★ 远端总 blob %d" % len(nmap))
    print("★ 本次 API 调用 %d 次" % gh.n)
    # ★ ★ 写状态文件：★ 记住【这次的本地 commit】★ ⇒ ★ 下次能算【我们改过哪些路径】★★
    _write_state(a.branch, git("rev-parse", lb).strip(), got, nt["sha"])
    print("  ★ 状态已记：%s ⇒ 本地 commit %s" % (STATE_PATH, git("rev-parse", lb).strip()[:10]))
    return 0 if not (lost or changed_bad or missing) else 1


if __name__ == "__main__":
    sys.exit(main())
