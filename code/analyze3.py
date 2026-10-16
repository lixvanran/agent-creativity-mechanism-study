# -*- coding: utf-8 -*-
import os, re, json, glob, itertools
import numpy as np, client2 as C
from topics4 import TOPICS4
ROOT="/workspace/exp-writing-compare/matrix3"
R={}
for f in glob.glob(f"{ROOT}/A*_r*_arm[1234].md"):
    b=os.path.basename(f)[:-3]; t,r,_=b.split("_"); v=open(f).read().strip()
    if v: R[(t,int(r[1:]),int(b[-1]))]=v
def emb(x): return C.emb(x) if x else []
def cos(a,b): return C.cos(a,b)
def mean(v): return sum(v)/len(v) if v else float('nan')
ARMS=[1,2,3,4]; L={1:"臂1 直接",2:"臂2 ADHD",3:"臂3 双轴(融合门)",4:"臂4 双轴(去融合门)"}

# ---- 用户四条判据的事后扫描（不进提示词）----
CRIT={
 "A1":{"name":"想到港澳高校",
       "pats":[r"港澳",r"香港",r"澳门",r"港校",r"港中文",r"港大",r"港理"]},
 "A2":{"name":"开局透支+套圈",
       "both":[[r"透支",r"开局",r"开跑",r"起跑",r"一开始",r"一开局",r"前\s*[一二三1-3]\s*圈",r"前段",r"先.{0,4}(拉|冲)"],
               [r"套圈",r"跟车",r"省力跟",r"借风",r"不单飞",r"贴(集团|前|住)",r"待在.{0,4}集团",r"省能量",r"跟在大集团"]]},
 "A3":{"name":"提到抄答案",
       "pats":[r"抄答案",r"抄作业",r"照抄",r"借答案",r"抄现成",r"直接抄",r"抄同学",r"网上找.{0,3}答案"]},
 "A4":{"name":"提到ADHD",
       "pats":[r"ADHD",r"A\.?D\.?H\.?D",r"注意力缺陷",r"多动",r"注意缺陷"]},
}
print("="*100); print("表0  用户四条判据的事后扫描（命中格数 / 3 次重复）"); print("="*100)
print("%-4s %-16s %-12s %-12s %-12s %-12s"%("题","判据","臂1","臂2","臂3","臂4"))
for x in TOPICS4:
    t=x["tid"]
    for k,c in CRIT.items():
        cells=[]
        for a in ARMS:
            n=0
            for r in (1,2,3):
                v=R.get((t,r,a))
                if not v: continue
                if "both" in c:
                    if all(any(re.search(p,v) for p in grp) for grp in c["both"]): n+=1
                elif any(re.search(p,v) for p in c["pats"]): n+=1
            cells.append("%d/3"%n)
        print("%-4s %-16s %-12s %-12s %-12s %-12s"%(t,c["name"],*cells))
    print("-"*100)

print("\n"+"="*100); print("表1  逃逸度（离同题臂1 三次重复质心）"); print("="*100)
print("%-4s %-22s %10s %10s %10s %10s"%("题","—","臂1","臂2","臂3","臂4"))
agg={a:[] for a in ARMS}
for x in TOPICS4:
    t=x["tid"]; base=[R.get((t,r,1)) for r in (1,2,3)]; base=[b for b in base if b]
    if len(base)<2: continue
    bv=np.array(emb(base)); bc=bv.mean(axis=0); bc=bc/max(np.linalg.norm(bc),1e-9)
    row=[]
    for a in ARMS:
        av=[R.get((t,r,a)) for r in (1,2,3)]; av=[v for v in av if v]
        if not av: row.append(float('nan')); continue
        e=mean([1-cos(np.array(v),bc) for v in emb(av)]); agg[a].append(e); row.append(e)
    print("%-4s %-22s %10.4f %10.4f %10.4f %10.4f"%(t,"",*row))
print("-"*100)
for a in ARMS: print("%-4s %-22s %10.4f  (均值)"%("ALL",L[a],mean(agg[a])))

print("\n"+"="*100); print("表2  跨重复离散度（同臂 3 次两两相似度，越低=越不重复）"); print("="*100)
print("%-4s %-22s %10s %10s %10s %10s"%("题","—","臂1","臂2","臂3","臂4"))
for x in TOPICS4:
    t=x["tid"]; row=[]
    for a in ARMS:
        av=[R.get((t,r,a)) for r in (1,2,3)]; av=[v for v in av if v]
        row.append(mean([cos(p,q) for p,q in itertools.combinations(emb(av),2)]) if len(av)>=2 else float('nan'))
    print("%-4s %-22s %10.4f %10.4f %10.4f %10.4f"%(t,"",*row))

print("\n"+"="*100); print("表3  臂间距离（同题同重复成文余弦）"); print("="*100)
D={}
for x in TOPICS4:
    t=x["tid"]
    for r in (1,2,3):
        vs={a:emb([R[(t,r,a)]])[0] for a in ARMS if (t,r,a) in R}
        for a,b in itertools.combinations(sorted(vs),2): D.setdefault((a,b),[]).append(cos(vs[a],vs[b]))
for (a,b),v in sorted(D.items()): print("  %-22s × %-22s 均值=%.4f (n=%d)"%(L[a],L[b],mean(v),len(v)))

print("\n"+"="*100); print("表4  产出可靠性"); print("="*100)
log=[json.loads(l) for l in open(f"{ROOT}/runlog.jsonl")]
for a in ARMS:
    got=sum(1 for k in R if k[2]==a)
    br=[d['branches'] for d in log if d['arm']==a and 'branches' in d]
    Ls=[len(re.findall(r'[\u4e00-\u9fff]',v)) for k,v in R.items() if k[2]==a]
    print("  %-22s 有效 %d/12  中位汉字 %d  分支 %s"%(L[a],got,int(mean(Ls)),"/".join(map(str,br))))
