# -*- coding: utf-8 -*-
"""生成 + embedding 双通道。embedding 参数是 texts（不是 input）且必须带 type。"""
import os, re, json, time, math, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE="https://api.minimaxi.com/v1"; KEY=os.environ["MINIMAX_SUBSCRIPTION_KEY"]
MODELS=["MiniMax-M3","MiniMax-M3.1-Flash-Preview","MiniMax-M2.7","MiniMax-M2.5","MiniMax-M2.1",
        "MiniMax-M2","MiniMax-M2.7-highspeed","MiniMax-M2.5-highspeed","MiniMax-M2.1-highspeed"]
def st(t):
    t=re.sub(r"<think>.*?</think>","",t or "",flags=re.S)
    return re.sub(r"^.*?</think>","",t,flags=re.S).strip()
def chat(p, model="MiniMax-M3", temp=1.0, mt=8000, tries=(12000,16000), min_ok=300):
    """三种失败机制都要挡：
       1) M3.1-Flash 把思考放进 reasoning_content，content 可能整个缺失
       2) 弱模型档位会把预算全花在 meta 分析 persona 指令上，<think> 未闭合、无正文
       3) think 吃光预算导致 finish_reason='length' 截断
    """
    last=""
    for m in (mt,)+tries:
        try:
            req=urllib.request.Request(f"{BASE}/chat/completions",
                data=json.dumps({"model":model,"messages":[{"role":"user","content":p}],
                                "temperature":temp,"max_tokens":m}).encode(),
                headers={"Authorization":"Bearer "+KEY,"content-type":"application/json"})
            d=json.loads(urllib.request.urlopen(req,timeout=240).read().decode())
            ch=d["choices"][0]; last=ch["message"].get("content") or ""
            if ch.get("finish_reason")=="length": continue
            o=st(last)
            if o.count("<think>")>o.count("</think>"): continue   # 思考未闭合=无正文
            if len(o)>=min_ok: return o
        except Exception:
            time.sleep(2.5)
    return last

def par(p, n, models=None, temp=1.0, mt=3000, workers=5):
    models = models or ["MiniMax-M3"]*n
    out=[""]*n
    with ThreadPoolExecutor(max_workers=workers) as ex:
        f={ex.submit(chat,p,models[i],temp,mt):i for i in range(n)}
        for x in as_completed(f):
            try: out[f[x]]=x.result()
            except Exception: out[f[x]]=""
    return out
_EMB={}
def emb(texts, typ="db"):
    if not texts: return []
    req=urllib.request.Request(f"{BASE}/embeddings",
        data=json.dumps({"model":"embo-01","type":typ,"texts":texts}).encode(),
        headers={"Authorization":"Bearer "+KEY,"content-type":"application/json"})
    for _ in range(3):
        try:
            v=json.loads(urllib.request.urlopen(req,timeout=90).read().decode())["vectors"]
            for t,e in zip(texts,v): _EMB[t]=e
            return v
        except Exception: time.sleep(2)
    return []
def cos(a,b):
    n=sum(x*y for x,y in zip(a,b)); da=math.sqrt(sum(x*x for x in a)); db=math.sqrt(sum(y*y for y in b))
    return n/(da*db) if da and db else 0.0
