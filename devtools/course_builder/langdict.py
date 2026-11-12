import sys, json
code, freqf, outf = sys.argv[1:4]
freq=json.load(open(freqf,encoding="utf-8"))
top=set(freq[:15000]); topl={w.lower() for w in top}
out=open(outf,"w",encoding="utf-8"); n=0
for line in sys.stdin:
    try: e=json.loads(line)
    except Exception: continue
    w=e.get("word","")
    if w.lower() not in topl or e.get("pos") in ("name","character","symbol","suffix","prefix","proverb"): continue
    gl=[]
    for s in e.get("senses",[])[:4]:
        g=s.get("glosses") or []
        if g and "form-of" not in (s.get("tags") or []) and "alt-of" not in (s.get("tags") or []): gl.append(g[-1])
    formof=any("form-of" in (s.get("tags") or []) for s in e.get("senses",[])[:1])
    rec={"w":w,"pos":e.get("pos"),"gl":gl[:3],"head":[h.get("expansion","") for h in e.get("head_templates",[])[:1]]}
    if e.get("pos")=="verb" and not formof and w.lower() in set(x.lower() for x in freq[:6000]) or (e.get("pos")=="verb" and code in("tr",) and not formof):
        rec["forms"]=[[f.get("form"),f.get("tags",[])] for f in e.get("forms",[])[:220] if f.get("form")]
    if formof:
        rec["of"]=[s.get("form_of",[{}])[0].get("word") for s in e.get("senses",[])[:1] if s.get("form_of")]
        rec["gl"]=[s.get("glosses",[""])[-1] for s in e.get("senses",[])[:2]]
    out.write(json.dumps(rec,ensure_ascii=False)+"\n"); n+=1
print(code,n)
