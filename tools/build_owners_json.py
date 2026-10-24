# -*- coding: utf-8 -*-
"""机器可读的远端归属表 OWNERS.json（可重跑；未知归属显式标 needs_confirmation，不猜）"""
import io, json, os, subprocess, urllib.request

REPO="lixvanran/agent-creativity-mechanism-study"; BRANCH="cmp8-handover-2026-10-20"
TOK=os.environ.get("GITHUB_TOKEN_LIXVANRAN","")
def api(path):
    r=urllib.request.Request("https://api.github.com"+path, headers={"Authorization":"Bearer "+TOK,"Accept":"application/vnd.github+json","User-Agent":"mavis-owner-table"})
    return json.load(urllib.request.urlopen(r, timeout=30))

# 我自己推的层：远端 sha -> (组, 本地 commit, 一句话)
MINE={
 "8934cb193cc220fd622d332f252c0b3351a31766":("三组","e483f4a","分维度偏好表 + 负对照分母真因"),
 "2055e086ad98ff444da85edfd58e55f1b2f3387e":("三组","6a48f8a","解耦帧组合seed + 论文更正nf偏好 + 留出集续跑脚本"),
 "895f7258b923731607abce1aba36feb274065e0d":("三组","548fcdc","法律域结论空间v3 + 合并反馈循环bug修复 + avg_m改2D"),
 "f101f4a94c84":("三组","8e86de5","C1 跨组对齐实验"),
}
KNOWN_OTHER={"4654245ac709":("第二组",None,"交付 2026-10-25"),"5b7fb4670320":("第二组",None,"交付 2026-10-25")}

# 拉远端叠加链（从新到旧，最多 12 层）
chain=[]; sha=api("/repos/%s/git/ref/heads/%s"%(REPO,BRANCH))["object"]["sha"]
for _ in range(12):
    c=api("/repos/%s/git/commits/%s"%(REPO,sha))
    if "commit" not in c:
        chain.append((sha,"★ API 未返回 commit 字段: %s"%str(c)[:80])); break
    msg=c["commit"]["message"].split("\n")[0]
    chain.append((sha,msg))
    if len(c["parents"])==0: break
    sha=c["parents"][0]["sha"]

layers=[]
for i,(sha,msg) in enumerate(chain):
    if sha in MINE: g,loc,one=MINE[sha]; conf=False
    elif sha in KNOWN_OTHER: g,loc,one=KNOWN_OTHER[sha]; conf=False
    else: g,loc,one=None,None,None; conf=True
    layers.append(dict(layer=len(chain)-i, sha=sha, group=g, local_commit=loc,
                       remote_message=msg, summary=one,
                       needs_confirmation=conf,
                       note=("远端 message 丢失（API 重建 commit 会丢 message）⇒ 归属与摘要见本表"
                             if msg.strip().lower() in ("update","update.","wip","tmp") else "")))
out=dict(schema="remote-ref-ownership/v1",
         repo="lixvanran/agent-creativity-mechanism-study", branch=BRANCH,
         generated_at=subprocess.check_output(["date","-u","+%Y-%m-%dT%H:%M:%SZ"]).decode().strip(),
         generator="tools/build_owners_json.py（可重跑）",
         note=("★ 远端 message 在 API 重建 commit 路径下会丢失 ⇒ 归属以本表为准。"
               "★ 未知归属一律标 needs_confirmation=true，不猜。"),
         layers=layers)
os.makedirs("cmp8repo/docs/cmp8", exist_ok=True)
p="cmp8repo/docs/cmp8/OWNERS.json"
json.dump(out, io.open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("✔ OWNERS.json 已写：%d 层，%d 层需确认"%(len(layers), sum(1 for l in layers if l["needs_confirmation"])))
for l in layers: print("   L%-2d %s  %-6s %s"%(l["layer"], l["sha"][:12], l["group"] or "?", (l["summary"] or "★待确认")[:44]))
