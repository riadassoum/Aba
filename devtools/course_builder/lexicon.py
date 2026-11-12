"""Build {form: {ar, lemma, note}} per language from aligned Wiktionary senses."""
import json, re, sys, collections

S = sys.argv[1]
W = f"{S}/wikt"
T = f"{S}/tatoeba"

TAGS_AR = [
    ("third-person singular simple present", "المضارع مع الغائب المفرد"),
    ("simple past and past participle", "الماضي واسم المفعول"),
    ("simple past", "الماضي"), ("past participle", "اسم المفعول (التصريف الثالث)"),
    ("present participle", "صيغة -ing"), ("gerund", "صيغة المصدر الجاري"),
    ("plural", "الجمع"), ("feminine", "المؤنث"), ("masculine", "المذكّر"),
    ("comparative", "صيغة التفضيل"), ("superlative", "صيغة التفضيل العليا"),
    ("first-person", "المتكلّم"), ("second-person", "المخاطب"), ("third-person", "الغائب"),
    ("preterite", "الماضي التامّ"), ("imperfect", "الماضي المستمرّ"),
    ("future", "المستقبل"), ("conditional", "الشرطي"), ("subjunctive", "صيغة الالتماس (الشرطية)"),
    ("imperative", "الأمر"), ("present", "المضارع"), ("past", "الماضي"), ("infinitive", "المصدر"),
    ("participle", "اسم المفعول"), ("diminutive", "التصغير"), ("genitive", "حالة الإضافة"),
    ("dative", "حالة المفعول غير المباشر"), ("accusative", "حالة المفعول به"),
    ("negative", "النفي"), ("interrogative", "الاستفهام"), ("possessive", "الملكية"),
]


def tags_ar(gloss: str) -> str:
    g = gloss.lower()
    out = []
    for k, v in TAGS_AR:
        if k in g and not any(k in done for done in out):
            out.append(k)
    labels = [dict(TAGS_AR)[k] for k in out][:3]
    return "، ".join(labels)


senses = [json.loads(l) for l in open(f"{W}/senses.jsonl", encoding="utf-8")]
freq_en = {w: i for i, w in enumerate(json.load(open(f"{T}/freq_en.json", encoding="utf-8")))}
POS_RANK = {"noun": 0, "verb": 0, "adj": 1, "adv": 1, "pron": 0, "prep": 1, "conj": 1, "det": 1,
            "num": 1, "intj": 2, "phrase": 3}


def clean_ar(a: str) -> str:
    return a.strip()


def best_sense_for(lang_code, word):
    """Candidates where ``word`` is a translation of an English sense."""
    return BY_FOREIGN.get(lang_code, {}).get(word.lower(), [])


BY_FOREIGN = collections.defaultdict(lambda: collections.defaultdict(list))
BY_EN = collections.defaultdict(list)
for order, s in enumerate(senses):
    ar = s["tr"].get("ar")
    if not ar:
        continue
    rank = (freq_en.get(s["en"].lower(), 99999), POS_RANK.get(s["pos"], 2), order)
    BY_EN[s["en"].lower()].append((order, s))
    for c, ws in s["tr"].items():
        if c == "ar":
            continue
        for pos_i, w in enumerate(ws):
            BY_FOREIGN[c][w.lower()].append(((pos_i,) + rank, s))


def meaning_foreign(c, w):
    cands = BY_FOREIGN[c].get(w.lower())
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    s = cands[0][1]
    alts = [clean_ar(s["tr"]["ar"][0])]
    for _, s2 in cands[1:4]:
        a = clean_ar(s2["tr"]["ar"][0])
        if s2["en"] == s["en"] and s2["pos"] == s["pos"] and a not in alts:
            alts.append(a)
    return {"ar": "، ".join(alts[:2]), "en": s["en"]}


def meaning_en(w):
    cands = BY_EN.get(w.lower())
    if not cands:
        return None
    cands.sort(key=lambda x: (POS_RANK.get(x[1]["pos"], 2), x[0]))
    first = cands[0][1]
    alts = [clean_ar(first["tr"]["ar"][0])]
    for _, s in cands[1:4]:
        a = clean_ar(s["tr"]["ar"][0])
        if s["pos"] == first["pos"] and a not in alts:
            alts.append(a)
    return {"ar": "، ".join(alts[:2])}


def gloss_word_ar(gloss: str):
    g = re.sub(r"\(.*?\)", "", gloss).strip().lower()
    g = re.sub(r"^(to|a|an|the) ", "", g)
    if re.fullmatch(r"[a-z]+", g):
        m = meaning_en(g)
        if m:
            return m["ar"]
    return None


def build(c):
    lex = {}
    if c == "en":
        formof = json.load(open(f"{W}/en_formof.json", encoding="utf-8"))
        freq = json.load(open(f"{T}/freq_en.json", encoding="utf-8"))[:20000]
        for w in freq:
            m = meaning_en(w)
            if m:
                lex[w] = {"ar": m["ar"]}
                continue
            for lemma, gl in sorted(formof.get(w, []), key=lambda x: ("person" not in x[1] and "past" not in x[1] and "participle" not in x[1])):
                lm = meaning_en(lemma)
                if lm:
                    lex[w] = {"ar": lm["ar"], "lemma": lemma, "note": tags_ar(gl)}
                    break
        return lex
    dic = {}
    for l in open(f"{W}/dict_{c}.jsonl", encoding="utf-8"):
        r = json.loads(l)
        dic.setdefault(r["w"].lower(), []).append(r)
    freq = json.load(open(f"{T}/freq_{c}.json", encoding="utf-8"))[:20000]
    for w in freq:
        key = w.lower()
        m = meaning_foreign(c, key)
        if m:
            lex[key] = {"ar": m["ar"]}
            continue
        done = False
        for r in dic.get(key, []):
            if r.get("of"):
                lemma = r["of"][0]
                if not lemma:
                    continue
                lm = meaning_foreign(c, lemma)
                ar = lm["ar"] if lm else None
                if not ar:
                    for r2 in dic.get(lemma.lower(), []):
                        for g in r2.get("gl", []):
                            ar = gloss_word_ar(g)
                            if ar:
                                break
                        if ar:
                            break
                if ar:
                    lex[key] = {"ar": ar, "lemma": lemma, "note": tags_ar((r.get("gl") or [""])[0])}
                    done = True
                    break
            else:
                for g in r.get("gl", []):
                    ar = gloss_word_ar(g)
                    if ar:
                        lex[key] = {"ar": ar}
                        done = True
                        break
            if done:
                break
    return lex


import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from overrides import O
AR_STRIP = re.compile("[ً-ْٰـ]")
WEAK = set("اويىءأإآةؤئ")


def skel(a):
    a = AR_STRIP.sub("", a)
    a = re.sub(r"^ال", "", a.strip())
    return "".join(ch for ch in a if ch not in WEAK and "ء" <= ch <= "ي")


def evidence(c, lex):
    """For words that also have a dictionary inflection (form-of) reading, keep
    whichever Arabic meaning's consonant skeleton appears in the human
    translations of sentences that contain the word."""
    pairs = json.load(open(f"{T}/pairs_{c}.json", encoding="utf-8"))
    TOKR = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.U)
    occ = collections.defaultdict(list)
    for p in pairs:
        a = AR_STRIP.sub("", p["ar"])
        for w in set(x.lower() for x in TOKR.findall(p["t"])):
            if len(occ[w]) < 150:
                occ[w].append(a)
    return occ


def score(cands_ar, ars):
    best, bs = None, -1
    for a in cands_ar:
        k = skel(a.split("،")[0])
        if len(k) < 2:
            continue
        n = sum(1 for s in ars if k in "".join(ch for ch in s if ch not in WEAK))
        if n > bs:
            best, bs = a, n
    return best, bs


for c in sys.argv[2:]:
    lex = build(c)
    if c != "en":
        occ = evidence(c, lex)
        dic = collections.defaultdict(list)
        for l in open(f"{W}/dict_{c}.jsonl", encoding="utf-8"):
            r = json.loads(l)
            dic[r["w"].lower()].append(r)
        changed = 0
        for w, info in list(lex.items()):
            alts = []
            for r in dic.get(w, []):
                if r.get("of") and r["of"][0]:
                    lm = meaning_foreign(c, r["of"][0])
                    if lm:
                        alts.append((lm["ar"], r["of"][0], tags_ar((r.get("gl") or [""])[0])))
            if not alts or info.get("lemma"):
                continue
            ars = occ.get(w, [])
            if len(ars) < 3:
                continue
            _, s_direct = score([info["ar"]], ars)
            a_best, s_alt = score([a for a, _, _ in alts], ars)
            if a_best and s_alt > max(1, 2 * s_direct):
                lemma, note = next((l, n) for a, l, n in alts if a == a_best)
                lex[w] = {"ar": a_best, "lemma": lemma, "note": note}
                changed += 1
        print(c, "evidence switched", changed)
    for w, a in O.get(c, {}).items():
        lex[w.lower()] = {"ar": a}
    json.dump(lex, open(f"{W}/lex_{c}.json", "w", encoding="utf-8"), ensure_ascii=False)
    freq = json.load(open(f"{T}/freq_{c}.json", encoding="utf-8"))
    cov = sum(1 for w in freq[:3000] if w.lower() in lex)
    print(c, len(lex), "top3000 coverage", cov,
          [(w, lex.get(w.lower())) for w in freq[:400:40]])
