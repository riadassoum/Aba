import sys, json, re
DIAL={'Levantine','Egyptian','Gulf','Moroccan','Iraqi','Hijazi','Najdi','Tunisian','Algerian','Libyan','Sudanese','colloquial','dialectal','Lebanese','Syrian','Palestinian','Jordanian','North-Levantine','South-Levantine','Maghrebi','Classical','archaic','obsolete'}
LANGS={"Arabic":"ar","Spanish":"es","Turkish":"tr","German":"de","Italian":"it","French":"fr"}
out=open(sys.argv[1],"w",encoding="utf-8")
n=0
for line in sys.stdin:
    if '"Arabic"' not in line: continue
    try: e=json.loads(line)
    except Exception: continue
    if e.get("lang_code")!="en": continue
    groups={}
    allt=[(t, t.get("sense") or "") for t in (e.get("translations") or [])]
    for i,sn in enumerate(e.get("senses",[]) or []):
        gl=(sn.get("glosses") or [""])[-1]
        allt+= [(t, t.get("sense") or gl or str(i)) for t in (sn.get("translations") or [])]
    for t,key in allt:
        c=LANGS.get(t.get("lang"))
        if not c or not t.get("word"): continue
        tags=t.get("tags") or []
        if c=="ar":
            if any(("Arabic" in x) or x in DIAL for x in tags): continue
            w0=re.split(r"\s+(?:imperfective|perfective|plural|feminine|masculine|dual|verbal noun)", t["word"])[0].strip()
            if not w0 or re.search("[A-Za-z:]", w0): continue
            t=dict(t, word=w0)
        elif any(x in ("archaic","obsolete","dialectal","rare","slang","vulgar") for x in tags): continue
        g=groups.setdefault(key,{})
        g.setdefault(c,[])
        if t["word"] not in g[c] and len(g[c])<3: g[c].append(t["word"])
    for sense,g in groups.items():
        if "ar" in g and len(g)>1:
            gl=""
            out.write(json.dumps({"en":e["word"],"pos":e.get("pos"),"sense":sense,"tr":g},ensure_ascii=False)+"\n"); n+=1
print(n)
