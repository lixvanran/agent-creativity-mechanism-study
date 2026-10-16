# -*- coding: utf-8 -*-
"""泄题 + 评价口径泄漏双检。
先把三引号块（docstring）与 # 注释剥掉，剩下的才是真正发给模型的字面量。"""
import re, sys
sys.path.insert(0,'/workspace/exp-writing-compare')
from topics4 import TOPICS4
QS=''.join(t['q'] for t in TOPICS4)
A=["港澳","香港","澳门","港校","透支","套圈","猛攻","糖原","抄答案","照抄","借答案",
   "ADHD","多血质","胆汁质","粘液质","抑郁质","气质量表","620","1.6km","回头弯","五一","位次"]
B=["高光","新颖","不寻常","独特","框架转换","可检验","立场代价","承重","洞见",
   "深度","洞察","反常识","犀利","精彩","含金量","有见地","密度"]
TRIPLE=re.compile(r'("""|\'\'\')(?:.|\n)*?\1')
LINE=re.compile(r'#[^\n]*')
PAT=re.compile(r'"((?:[^"\\]|\\.){8,})"')
def scan(f):
    src=open(f,encoding="utf-8").read()
    src=TRIPLE.sub('""', src)
    src=LINE.sub(' ', src)
    lits=PAT.findall(src)
    hA=[(k,l[:60]) for l in lits for k in A if k in l and k not in QS]
    hB=[(k,l[:60]) for l in lits for k in B if k in l]
    return len(lits),hA,hB
tot=0;bad=0
for f in ("shared.py","arm3.py","arm4.py","run_q.py"):
    n,hA,hB=scan(f);tot+=n
    if hA or hB: bad+=1
    print("%s %-12s %3d 条实际提示词  题面泄漏=%d  评价口径泄漏=%d"%("✓" if not(hA or hB) else "✗",f,n,len(hA),len(hB)))
    for k,l in hA: print("      [题面] %s :: %s"%(k,l))
    for k,l in hB: print("      [口径] %s :: %s"%(k,l))
print("\n合计 %d 条真正发给模型的字符串，%s"%(tot,"✓ 全部通过" if bad==0 else "✗ %d 个文件有问题"%bad))
