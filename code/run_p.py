# -*- coding: utf-8 -*-
"""3 题 × 4 臂 × 3 重复 = 36 份。题级 3 并行，题内串行。"""
import os, re, json, time, subprocess
import client2 as C, arm3, arm4
from topics import TOPICS2
ROOT="/workspace/exp-writing-compare/matrix2"; os.makedirs(ROOT, exist_ok=True)
REPS=int(os.environ.get("REPS","3"))
def append(d):
    with open(ROOT+"/runlog.jsonl","a") as f: f.write(json.dumps(d,ensure_ascii=False)+"\n")

def run_topic(T):
    tid,q=T["tid"],T["q"]; t0=time.time()
    for rep in range(1,REPS+1):
        t=time.time()
        a1=C.chat(f"{q}\n\n700-900字。观点要明确、承担立场。只输出文章正文。","MiniMax-M3",1.0,4000,min_ok=300)
        open(f"{ROOT}/{tid}_r{rep}_arm1.md","w").write(a1)
        append(dict(tid=tid,rep=rep,arm=1,calls=1,chars=len(a1))); print(f"[{tid} r{rep}] 臂1 ✓{len(a1)}B",flush=True)

        t=time.time(); env=dict(os.environ)
        env["ANTHROPIC_BASE_URL"]="https://api.minimaxi.com/anthropic"; env["ANTHROPIC_API_KEY"]=C.KEY
        try:
            r=subprocess.run(["node","dist/cli.js",q,"--model","MiniMax-M3"],cwd="/workspace/adhd-repo",
                             capture_output=True,text=True,env=env,timeout=1800)
            raw=re.sub(r'\x1b\[[0-9;]*m','',r.stdout)
        except Exception as e: raw=""; print("  臂2 CLI:",str(e)[:70],flush=True)
        open(f"{ROOT}/{tid}_r{rep}_arm2raw.txt","w").write(raw)
        ideas=[i[:300] for i in re.findall(r'^\s*-\s*(.+)',raw,re.M) if len(i)>12][:24]
        a2=""
        if ideas:
            a2=C.chat(f"{q}\n\n以下是若干个认知框架下产出的独立想法：\n"+"\n".join(f"- {i}" for i in ideas)+
                      "\n\n请综合这些想法，写成一篇**最终文章**。观点明确、承担立场，不要罗列各方观点，"
                      "不要写「机遇与挑战并存」这类空话，不要预测具体年份数字。700-900字。只输出文章正文。",
                      "MiniMax-M3",1.0,4000,min_ok=300)
        open(f"{ROOT}/{tid}_r{rep}_arm2.md","w").write(a2)
        append(dict(tid=tid,rep=rep,arm=2,calls=11,ideas=len(ideas),chars=len(a2))); print(f"[{tid} r{rep}] 臂2 ✓{len(a2)}B",flush=True)

        t=time.time()
        cands=[c for c in arm3.diverge(5,workers=1,topic=q) if c and len(c)>60]
        a3=""
        if len(cands)>=2:
            deep=arm3.deep_validate(cands,topic=q); dec=arm3.deception_check(cands,deep,topic=q)
            st=arm3.archive_stats(cands,a1); a3=arm3.compose(cands,deep,dec,st,topic=q)
        open(f"{ROOT}/{tid}_r{rep}_arm3.md","w").write(a3)
        append(dict(tid=tid,rep=rep,arm=3,calls=8,branches=len(cands),chars=len(a3))); print(f"[{tid} r{rep}] 臂3 {'✓' if a3 else '✗'}{len(a3)}B 分支{len(cands)}/5",flush=True)

        t=time.time()
        arts=arm4.branch_articles(q,5)
        a4=arm4.select_only(q,arts) if arts else ""
        open(f"{ROOT}/{tid}_r{rep}_arm4.md","w").write(a4)
        json.dump(arts,open(f"{ROOT}/{tid}_r{rep}_arm4arts.json","w"),ensure_ascii=False,indent=1)
        append(dict(tid=tid,rep=rep,arm=4,calls=6,branches=len(arts),chars=len(a4),diag=arm4.DIAG))
        print(f"[{tid} r{rep}] 臂4 {'✓' if a4 else '✗'}{len(a4)}B 分支{len(arts)}/5",flush=True)
    print(f"[{tid}] 完成 {time.time()-t0:.0f}s",flush=True)

if __name__=="__main__":
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in [ex.submit(run_topic,t) for t in TOPICS2]: f.result()
    print("ALL DONE",flush=True)
