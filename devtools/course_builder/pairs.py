import bz2, json, sys, re, collections
D=sys.argv[1]
def sents(l):
    d={}
    for line in bz2.open(f"{D}/{l}_sentences.tsv.bz2","rt",encoding="utf-8"):
        p=line.rstrip("\n").split("\t")
        if len(p)>=3: d[int(p[0])]=p[2]
    return d
def links(a,b):
    m=collections.defaultdict(list)
    for line in bz2.open(f"{D}/{a}-{b}_links.tsv.bz2","rt"):
        x,y=line.split()[:2]; m[int(x)].append(int(y))
    return m
ara=sents("ara"); eng=sents("eng")
ae=links("ara","eng")
def ok_ar(s): return 2<=len(s.split())<=18 and re.search("[؀-ۿ]",s) and not re.search("[A-Za-z]",s)
def ok_f(s): return 1<=len(s.split())<=18
res={}
# english
pairs=[]
for a,es in ae.items():
    if a in ara and ok_ar(ara[a]):
        for e in es[:1]:
            if e in eng and ok_f(eng[e]): pairs.append({"t":eng[e],"ar":ara[a],"src":"direct"})
res["en"]=pairs
for code,l in (("es","spa"),("tr","tur"),("de","deu"),("it","ita"),("fr","fra")):
    try: tg=sents(l)
    except FileNotFoundError: print("no",l); continue
    seen=set(); pairs=[]
    for a,ts in links("ara",l).items():
        if a in ara and ok_ar(ara[a]):
            for t in ts[:1]:
                if t in tg and ok_f(tg[t]) and tg[t] not in seen:
                    seen.add(tg[t]); pairs.append({"t":tg[t],"ar":ara[a],"src":"direct"})
    et=links("eng",l)
    for a,es in ae.items():
        if a not in ara or not ok_ar(ara[a]): continue
        for e in es[:1]:
            for t in et.get(e,[])[:1]:
                if t in tg and ok_f(tg[t]) and tg[t] not in seen:
                    seen.add(tg[t]); pairs.append({"t":tg[t],"ar":ara[a],"src":"pivot","en":eng.get(e,"")})
    res[code]=pairs; del tg
for k,v in res.items():
    print(k,len(v),sum(p["src"]=="direct" for p in v))
    json.dump(v,open(f"{D}/pairs_{k}.json","w",encoding="utf-8"),ensure_ascii=False)
