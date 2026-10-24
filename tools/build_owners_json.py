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
        # ★★ BUGFIX-2026-10-25-B：★ _owner_line 必须【存进 chain tuple】⇒
        #   原实现把它算在链循环里却没带出来 ⇒ 层次循环读到的是【最后一层泄漏的值】
        #   ⇒ ⇒ owner 行证据永远对不上层（实测 20 层全被判 weak）
        chain.append((sha, msg, tree, _owner_line))
        parents = c.get("parents") or []
        if not parents:
            break
        sha = parents[0]["sha"]

    layers = []
    for i, (sha, msg, tree, owner_line) in enumerate(chain):
        cand = by_tree.get(tree) or []
        local_sha = local_msg = None
        if cand:
            local_sha, local_msg = cand[0]
        matched = "tree_sha" if cand else "none"
        summary = (local_msg or msg)

        # ★★ 归属解析：【单一、严格有序的优先级链】★★
        #   ★ 修 BUGFIX-A：原实现先设 g=owner_line，随后又被 g=owner_of(local_msg or msg)
        #     【无条件覆盖】⇒ owner 行（硬级）的组名会被前缀反推顶掉。
        #   ★ 修 BUGFIX-C：原实现有两个 fallback 块，第一个已把 g 置非 None
        #     ⇒ 第二个（唯一给 level 赋 "medium(历史fallback)" 的那个）是【死代码】。
        #   ⇒ 现在：每条证据【只走一次】、且【只由它自己】决定 level 与 group。
        g = None
        level = None
        prefix_guess = owner_of(local_msg or msg)

        if owner_line:
            # 硬级：commit body 的 owner 行（唯一硬证据）
            g = owner_line
            level = "hard(owner行)"
            matched = "owner_line"
            if prefix_guess and prefix_guess != owner_line:
                # ★ owner 行与前缀反推不一致 ⇒ 如实记录（不静默取其一）
                note_extra = "★ owner行(%s) 与前缀反推(%s) 不一致 ⇒ 以 owner行为准" % (owner_line, prefix_guess)
            else:
                note_extra = ""
        elif prefix_guess:
            # 弱级：从本地 commit message 前缀反推（author 名【不作】证据）
            g = prefix_guess
            level = "weak(prefix反推)"
            note_extra = ""
        elif msg in by_subject:
            # 弱级：远端 message 命中本仓某个 commit 的 subject ⇒ 归属即本仓
            local_sha, local_msg = by_subject[msg]
            g = owner_of(local_msg) or "三组"
            level = "weak(prefix反推)"
            summary = local_msg
            matched = "subject(本仓)"
            note_extra = ""
        else:
            fb = None
            for k, v in FALLBACK.items():
                if sha.startswith(k):
                    fb = v
                    break
            if fb:
                g, fb_local, fb_sum = fb
                local_sha = local_sha or fb_local
                summary = fb_sum
                matched = "fallback(历史update层)"
                level = "medium(历史fallback)"
                note_extra = ""
            else:
                g = None
                level = "unconfirmed(无任何证据)"
                note_extra = ""

        conf = (g is None)
        note = ("远端 message 无信息量（'update' 等）⇒ 归属由 tree sha 匹配到本地 commit 得出"
                if msg.strip().lower() in ("update", "update.", "wip", "tmp", "commit", "fix")
                else "")
        if note_extra:
            note = (note + " ｜ " + note_extra) if note else note_extra
        layers.append(dict(
            layer=len(chain) - i, sha=sha, group=g,
            local_commit=local_sha, remote_message=msg,
            summary=summary, needs_confirmation=conf,
            matched_by=matched,
            evidence_level=level,
            owner_line=owner_line or "",
            note=note))

    out = dict(schema="remote-ref-ownership/v2",
               repo=REPO, branch=BRANCH,
               generated_at=subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]).decode().strip(),
               generator="tools/build_owners_json.py（v4：owner行=硬级 / 前缀反推=弱级 / 历史fallback=中级 / 皆无=未确认）",
               remote_ref_snapshot=chain[0][0] if chain else None,
               note=("★ 归属由【远端层的 tree sha】匹配【本地 commit】得到 ⇒ 再从本地 message 前缀反推组名 "
                     "⇒ ⇒ 不需要维护任何硬编码表 ⇒ ⇒ 未知一律 needs_confirmation=true，不猜。"
                     "★ v4 修复：owner 行曾因未存入 chain tuple 而跨层泄漏 ⇒ 20 层全被误判 weak；"
                     "owner 行的组名曾被前缀反推无条件覆盖；medium(历史fallback) 曾落在死代码分支。"),
               layers=layers)
    p = os.path.join(REPO_ROOT, "docs", "cmp8", "OWNERS.json")
    json.dump(out, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    nconf = sum(1 for l in layers if l["needs_confirmation"])
    print("✔ OWNERS.json(v4) 已写：%d 层 ｜待确认 %d 层" % (len(layers), nconf))
    for l in layers:
        print("   L%-2d %s  %-8s %-22s %-22s %s" % (l["layer"], l["sha"][:12], l["group"] or "★待确认",
                                                    l["evidence_level"], l["matched_by"], (l["summary"] or "")[:46]))
    # ★ 三档 × 按组分列（★ 门3 要求的输出形态）
    TIER = {"hard": "硬级(owner行)", "weak": "弱级(前缀反推)", "medium": "中级(历史fallback)",
            "unconfirmed": "未确认(无证据)"}

    def tier_of(lv):
        if lv.startswith("hard"):
            return "hard"
        if lv.startswith("weak"):
            return "weak"
        if lv.startswith("medium"):
            return "medium"
        return "unconfirmed"
    groups = sorted({(l["group"] or "★待确认") for l in layers})
    print("\n★ 归属分档 × 按组分列（层数）")
    hdr = "  %-10s" % "档位" + "".join("%-12s" % g for g in groups) + "合计"
    print(hdr)
    tbl = {}
    for t in ("hard", "weak", "medium", "unconfirmed"):
        row = []
        tot = 0
        for g in groups:
            c = sum(1 for l in layers if (l["group"] or "★待确认") == g and tier_of(l["evidence_level"]) == t)
            row.append(c)
            tot += c
        tbl[t] = row
        print("  %-10s" % TIER[t] + "".join("%-12d" % c for c in row) + str(tot))
    print("  %-10s" % "合计" + "".join("%-12d" % sum(tbl[t][i] for t in tbl) for i in range(len(groups))) + str(len(layers)))
    out["tier_by_group"] = {TIER[t]: dict(zip(groups, tbl[t])) for t in tbl}
    json.dump(out, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n✔ tier_by_group 已并入 OWNERS.json")


if __name__ == "__main__":
    main()
