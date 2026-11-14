import bz2, json, re, sys, collections
D=sys.argv[1]
TOK=re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.U)
for code,l in (("en","eng"),("es","spa"),("tr","tur"),("de","deu"),("it","ita"),("fr","fra")):
    c=collections.Counter()
    for line in bz2.open(f"{D}/{l}_sentences.tsv.bz2","rt",encoding="utf-8"):
        p=line.split("\t",2)
        if len(p)==3:
            for w in TOK.findall(p[2]): c[w.lower() if code!="de" else w]+=1
    json.dump([w for w,n in c.most_common(60000) if n>=3],open(f"{D}/freq_{code}.json","w",encoding="utf-8"),ensure_ascii=False)
    print(code,list(c.most_common(8)))
