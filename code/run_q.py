# -*- coding: utf-8 -*-
"""4 个实际问题 × 4 臂 × 3 重复。输出=可执行答复(≤400字)，不是散文。"""
import os, re, json, time, subprocess
import client2 as C, arm3, arm4
from topics4 import TOPICS4
ROOT="/workspace/exp-writing-compare/matrix3"; os.makedirs(ROOT, exist_ok=True)
REPS=int(os.environ.get("REPS","3"))
def append(d):
    with open(ROOT+"/runlog.jsonl","a") as f: f.write(json.dumps(d,ensure_ascii=False)+"\n")

ART = "给出一份 400 字以内、可直接执行的答复。观点明确、给出具体动作与依据，不要罗列各方观点，不要写空话。只输出答复正文。"

def run_topic(T):
    tid,q=T["tid"],T["q"]; t0=time.time()
    for rep in range(1,REPS+1):
        a1=C.chat(f"{q}\n\n{ART}","MiniMax-M3",1.0,4000,min_ok=120)
        open(f"{ROOT}/{tid}_r{rep}_arm1.md","w").write(a1)
        append(dict(tid=tid,rep=rep,arm=1,calls=1,chars=len(a1))); print(f"[{tid} r{rep}] 臂1 ✓{len(a1)}B",flush=True)

        t=time.time(); env=dict(os.environ)
        env["ANTHROPIC_BASE_URL"]="https://api.minimaxi.com/anthropic"; env["ANTHROPIC_API_KEY"]=C.KEY
        try:
            r=subprocess.run(["node","dist/cli.js",q,"--model","MiniMax-M3"],cwd="/workspace/adhd-repo",
                             capture_output=True,text=True,env=env,timeout=1800)
            raw=re.sub(r'\x1b\[[0-9;]*m','',r.stdout)
        except Exception as e: raw=""; print("  臂2:",str(e)[:70],flush=True)
        open(f"{ROOT}/{tid}_r{rep}_arm2raw.txt","w").write(raw)
        ideas=[i[:300] for i in re.findall(r'^\s*-\s*(.+)',raw,re.M) if len(i)>12][:24]
        a2=""
        if ideas:
            a2=C.chat(f"{q}\n\n以下是若干个认知位置下产出的独立想法：\n"+"\n".join(f"- {i}" for i in ideas)+
                      f"\n\n{ART}","MiniMax-M3",1.0,4000,min_ok=120)
        open(f"{ROOT}/{tid}_r{rep}_arm2.md","w").write(a2)
        append(dict(tid=tid,rep=rep,arm=2,calls=11,ideas=len(ideas),chars=len(a2))); print(f"[{tid} r{rep}] 臂2 {'✓' if a2 else '✗'}{len(a2)}B",flush=True)

        t=time.time()
        cands=[c for c in arm3.diverge(5,workers=1,topic=q+"\n\n"+ART) if c and len(c)>60]
        a3=""
        if len(cands)>=2:
            deep=arm3.deep_validate(cands,topic=q); dec=arm3.deception_check(cands,deep,topic=q)
            st=arm3.archive_stats(cands,a1)
            a3=C.chat("主题："+q+"\n\n以下是若干个独立位置上产出的判断：\n"+"\n\n---\n".join(f"[{i+1}] {c[:400]}" for i,c in enumerate(cands))+
                      "\n\n对它们差异与成立条件的分析：\n"+deep[:700]+
                      "\n\n对评价标准本身的反诘：\n"+dec[:500]+
                      f"\n\n请综合以上，{ART}","MiniMax-M3",1.0,4000,min_ok=120)
        open(f"{ROOT}/{tid}_r{rep}_arm3.md","w").write(a3)
        append(dict(tid=tid,rep=rep,arm=3,calls=8,branches=len(cands),chars=len(a3))); print(f"[{tid} r{rep}] 臂3 {'✓' if a3 else '✗'}{len(a3)}B 分支{len(cands)}/5",flush=True)

        t=time.time()
        arts=[]
        for i in range(5):
            fname,fp=arm3.FRAMES[i]; m=arm3.AXIS_B_MODELS[i]; pe=arm3.PERSONAS[i]
            p=(f"问题：{q}\n\n你现在从【{fname}】这个认知位置出发。\n{fp}\n\n设定：{pe}\n\n{ART}")
            o=C.chat(p,m,1.0,8000,min_ok=120)
            if o and len(o)>=120: arts.append(o)
        a4=""
        if arts:
            if len(arts)==1: a4=arts[0]
            else:
                a4=C.chat("同一个问题下有若干篇**各自独立**写成的答复：\n\n"+
                    "\n\n=====\n\n".join(f"[第{i+1}篇]\n{a}" for i,a in enumerate(arts))+
                    "\n\n请挑出**其中一篇原样输出**。判据（不要重写、不要融合、不要拼接）："
                    "① 哪一篇与常规建议最不同？② 哪一篇给出的具体判断最站得住——说清它在什么条件下成立？"
                    "③ 哪一篇最不像套话？先写 60-120 字说明，然后**原样贴出被选中那篇的全文**。",
                    "MiniMax-M3",1.0,5000,min_ok=120)
        open(f"{ROOT}/{tid}_r{rep}_arm4.md","w").write(a4)
        json.dump(arts,open(f"{ROOT}/{tid}_r{rep}_arm4arts.json","w"),ensure_ascii=False,indent=1)
        append(dict(tid=tid,rep=rep,arm=4,calls=6,branches=len(arts),chars=len(a4)))
        print(f"[{tid} r{rep}] 臂4 {'✓' if a4 else '✗'}{len(a4)}B 分支{len(arts)}/5",flush=True)
    print(f"[{tid}] 完成 {time.time()-t0:.0f}s",flush=True)

if __name__=="__main__":
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as ex:
        for f in [ex.submit(run_topic,t) for t in TOPICS4]: f.result()
    print("ALL DONE",flush=True)
