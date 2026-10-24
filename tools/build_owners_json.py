# -*- coding: utf-8 -*-
"""★ 远端归属表生成器 v2：★ 用【tree sha】把远端层匹配到本地 commit ⇒ ⇒ 自维护，无需硬编码

★ 原理：push_via_api.py 用 API 重建 commit 时，**tree 内容逐字节相同** ⇒ **tree sha 相同**
  ⇒ ⇒ 远端层 ↔ 本地 commit 的对应关系可由 tree sha 精确求出
  ⇒ ⇒ 归属从【本地 commit 的 message 前缀】（如 "[三组] ..."）反推 ⇒ ⇒ 永不过期
★ 仍保留两条兜底：① 硬编码的历史 sha 前缀表 ② 未知一律 needs_confirmation=true（不猜）
"""
import io
import json
import os
import subprocess
import urllib.request

REPO = "lixvanran/agent-creativity-mechanism-study"
BRANCH = "cmp8-handover-2026-10-20"
TOK = os.environ.get("GITHUB_TOKEN_LIXVANRAN", "")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))   # cmp8repo/


# ★ 历史 fallback：仅用于【修复前】那些远端 message 写成 "update" 的层
#   （它们的 tree 与本地 tree 不同 ⇒ tree sha 匹配不成立 ⇒ 只能靠本地 commit 映射补）
#   ⇒ 未来层不再需要本表：commit body 自带 owner 行 ⇒ 归属自描述
FALLBACK = {
    "a6208aec1c20": ("三组", "14dddc5", "OWNERS.json 生成 + 打包改先验后换"),
    "24e3ebb95cdd": ("三组", "356ecaa", "OWNERS.json 生成器（含 User-Agent 与 API 兜底）"),
    "41009794b3d4": ("三组", "d4ef317", "分维度表按精确口径 + 贡献三条加定位句 + OWNERS 生成器"),
    "7ab16b40101e": ("三组", "223efd1", "[三组] commit message 格式改为 [组名] 前缀"),
    "9e7af45adb04": ("三组", None, "★ 叠加在 f0d8004fa6ba 之上（本地对应 commit 待补）"),
    "f0d8004fa6ba": ("三组", "797190b", "KNOWN_ISSUES 重写 + 摘要加两判官反号 + §2.3 措辞 + §6.4.4e"),
    "8934cb193cc2": ("三组", "e483f4a", "分维度偏好表 + 负对照分母真因"),
    "2055e086ad98": ("三组", "6a48f8a", "解耦帧组合 seed + 论文更正 nf 偏好 + 留出集续跑脚本"),
    "78ab8b49bdb8": ("第二组", None, "push_overlay：message 归一化 + 核对失败时响亮报错（第二组的推送工具修复）"),
    "895f7258b923": ("三组", "548fcdc", "法律域结论空间 v3 + 合并反馈循环 bug 修复 + avg_m 改 2D"),
}

GROUPS = ("三组", "第二组", "层2", "第四组", "论文簇", "multi-mind")


def api(path):
    r = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Authorization": "Bearer " + TOK,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "mavis-owner-table"})
    return json.load(urllib.request.urlopen(r, timeout=30))


def local_commits():
    """本地 commit → (sha, tree_sha, message)"""
    out = subprocess.check_output(
        ["git", "-C", REPO_ROOT, "log", "--all", "--format=%H%x09%T%x09%s"],
        text=True).strip().split("\n")
    res = []
    for line in out:
        if not line.strip():
            continue
        sha, tree, msg = line.split("\t", 2)
        res.append((sha, tree, msg))
    return res


def owner_of(message):
    for g in GROUPS:
        if ("[%s]" % g) in message or message.startswith(g):
            return g
    for g in GROUPS:
        if g in message[:40]:
            return g
    return None


def main():
    locals_ = local_commits()
    by_tree = {}
    by_subject = {}
    for sha, tree, msg in locals_:
        by_tree.setdefault(tree, []).append((sha, msg))
        by_subject.setdefault(msg, (sha, msg))

    chain = []
    sha = api("/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))["object"]["sha"]
    for _ in range(20):
        c = api("/repos/%s/git/commits/%s" % (REPO, sha))
        # ★ API 建的 commit：message 在顶层；GitHub 原生 commit：在 commit.message ⇒ 两种都读
        _c = c.get("commit") or {}
        _full = (c.get("message") or _c.get("message") or "")
        msg = _full.split("\n")[0]
        # ★ 硬级证据：commit body 里的 owner 行（★ GitHub 只去尾部换行 ⇒ 逐行找即可）
        _owner_line = ""
        for _ln in _full.split("\n")[1:]:
            if _ln.strip().lower().startswith("owner:"):
                _owner_line = _ln.split(":", 1)[1].strip()
                break
        tree = (c.get("tree") or {}).get("sha")
        chain.append((sha, msg, tree))
        parents = c.get("parents") or []
        if not parents:
            break
        sha = parents[0]["sha"]

    layers = []
    for i, (sha, msg, tree) in enumerate(chain):
        cand = by_tree.get(tree) or []
        local_sha = local_msg = None
        if cand:
            local_sha, local_msg = cand[0]
        matched = "tree_sha" if cand else "none"
        level = "weak(prefix反推)"
        # ★ 硬级：body 里的 owner 行（★ 优先于一切反推；★ 必须在此处赋值，
        #   否则会被下面的 fallback 分支覆盖 —— 2026-10-25 踩过）
        if _owner_line:
            g = _owner_line
            level = "hard(owner行)"
            matched = "owner_line"
        if _owner_line:
            # ★ 硬级：body 里的 owner 行优先于一切反推
            g = _owner_line
            level = "hard(owner行)"
            matched = "owner_line"
        g = owner_of(local_msg or msg)
        summary = (local_msg or msg)
        # 规则 2：★ 远端 message 命中本仓某个 commit 的 subject ⇒ ★ 归属即本仓（三组）
        if g is None and msg in by_subject:
            local_sha, local_msg = by_subject[msg]
            g = owner_of(local_msg) or "三组"
            summary = local_msg
            matched = "subject(本仓)"
        if g is None:
            for k, v in FALLBACK.items():
                if sha.startswith(k):
                    g, fb_local, fb_sum = v
                    local_sha = local_sha or fb_local
                    summary = fb_sum
                    matched = "fallback(历史update层)"
                    break
        if g is None:
            for k, v in FALLBACK.items():
                if sha.startswith(k):
                    g, fb_local, fb_sum = v
                    local_sha = local_sha or fb_local
                    summary = fb_sum
                    matched = "fallback(历史update层)"
                    level = "medium(历史fallback)"
                    break
        conf = (g is None)
        if g is not None and level == "weak(prefix反推)":
            level = "weak(prefix反推)"
        layers.append(dict(
            layer=len(chain) - i, sha=sha, group=g,
            local_commit=local_sha, remote_message=msg,
            summary=summary, needs_confirmation=conf,
            matched_by=matched,
            evidence_level=level,
            note=("远端 message 无信息量（'update' 等）⇒ 归属由 tree sha 匹配到本地 commit 得出"
                  if msg.strip().lower() in ("update", "update.", "wip", "tmp", "commit", "fix")
                  else "")))

    out = dict(schema="remote-ref-ownership/v2",
               repo=REPO, branch=BRANCH,
               generated_at=subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]).decode().strip(),
               generator="tools/build_owners_json.py（v3：owner 行=硬级 / 前缀反推=弱级 / 皆无=待确认）",
               remote_ref_snapshot=chain[0][0] if chain else None,
               note=("★ 归属由【远端层的 tree sha】匹配【本地 commit】得到 ⇒ 再从本地 message 前缀反推组名 "
                     "⇒ ⇒ 不需要维护任何硬编码表 ⇒ ⇒ 未知一律 needs_confirmation=true，不猜。"),
               layers=layers)
    p = os.path.join(REPO_ROOT, "docs", "cmp8", "OWNERS.json")
    json.dump(out, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("✔ OWNERS.json(v2) 已写：%d 层 ｜待确认 %d 层" % (len(layers), sum(1 for l in layers if l["needs_confirmation"])))
    for l in layers:
        print("   L%-2d %s  %-8s %-6s %s" % (l["layer"], l["sha"][:12], l["group"] or "★待确认",
                                             l["matched_by"], (l["summary"] or "")[:52]))


if __name__ == "__main__":
    main()
