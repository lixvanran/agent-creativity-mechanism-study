import sys, json, urllib.request
sys.path.insert(0,"/workspace/lab/batch-U1")
import u1_lib as U, measure as M
pack=U.load_u1(); ev=U.evidence_items(pack); ct=U.conclusion_space(pack)
ans=open("runs/A_fixed/rep3.answer.md",encoding="utf-8").read()
claims=['人工智能相关专业包含人工智能（AI）专业。','人工智能相关专业包含智能科学专业。','人工智能（AI）专业存在独立设置的情况。','报考人工智能相关专业必须满足物理科目必选要求。','武汉大学是湖北省本地高校。','华中科技大学是湖北省本地高校。']
evs="\n".join("%d. %s"%(i+1,e["text"]) for i,e in enumerate(ev))
cts="\n".join("%d. %s"%(i+1,c["text"]) for i,c in enumerate(ct))
lst="\n".join("%d. %s"%(i+1,c) for i,c in enumerate(claims))
q=M.CARD_Q.format(ask=pack["ask"],ev=evs,ct=cts,claims=lst)
print("prompt 长度 %d 字符" % len(q), flush=True)
def raw_call(mt):
    req=urllib.request.Request(U.MM_BASE+"/chat/completions",
        data=json.dumps({"model":U.MM_MODEL,"messages":[{"role":"user","content":q}],
                         "temperature":0.0,"max_tokens":mt}).encode(),
        headers={"Authorization":"Bearer "+U.MM_KEY,"content-type":"application/json"})
    d=json.loads(urllib.request.urlopen(req,timeout=600).read().decode())
    ch=d["choices"][0]; u=d.get("usage") or {}
    return ch.get("finish_reason"), (ch["message"].get("content") or ""), u
for mt in (12000, 20000):
    fr,content,u = raw_call(mt)
    print("max_tokens=%-6d finish=%-8s len=%-5d usage=%s" % (mt, fr, len(content),
          {k:u.get(k) for k in ('prompt_tokens','completion_tokens')}), flush=True)
    if content.strip():
        print("内容前 600 字:", content[:600], flush=True)
        break
