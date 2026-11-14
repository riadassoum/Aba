# -*- coding: utf-8 -*-
"""Write the graded language courses into the academy's courses/ folder."""
import json, os, random, re, shutil, sys, unicodedata, collections

S = sys.argv[1]
OUT = sys.argv[2]
LANGS = sys.argv[3:]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grade as G
from grammar_notes import NOTES
import turkish_conj as TC

TOK = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.U)

CONF = {
    "en": dict(cid="english_graded", title="الإنجليزية بالجمل: من الصفر إلى الإتقان", name="الإنجليزية",
               desc="مئات الدروس المتدرّجة: كل درس يعلّمك الكلمات الأكثر شيوعًا التالية، وكل جملة فيه مبنية مما تعلّمته، بترجمات بشرية حقيقية، مع القواعد والقراءة المتقدّمة.", order=2),
    "fr": dict(cid="french_graded", title="الفرنسية بالجمل: من الصفر إلى الإتقان", name="الفرنسية",
               desc="مئات الدروس المتدرّجة بجمل حقيقية مترجمة، مع القواعد وتصريف الأفعال والقراءة المتقدّمة.", order=2),
    "es": dict(cid="spanish", title="اللغة الإسبانية", name="الإسبانية",
               desc="دورة كاملة للناطقين بالعربية: النطق، ثم مئات الدروس المتدرّجة بجمل حقيقية، والقواعد، وتصريف الأفعال في ستة أزمنة، والقراءة المتقدّمة.", order=3),
    "tr": dict(cid="turkish", title="اللغة التركية", name="التركية",
               desc="دورة كاملة للناطقين بالعربية: الحروف والتوافق الصوتي، ثم مئات الدروس المتدرّجة بجمل حقيقية، واللواحق والأزمنة، والقراءة المتقدّمة.", order=3),
    "de": dict(cid="german", title="اللغة الألمانية", name="الألمانية",
               desc="دورة كاملة للناطقين بالعربية: النطق، ثم مئات الدروس المتدرّجة بجمل حقيقية، والحالات الأربع، وتصريف الأفعال، والقراءة المتقدّمة.", order=3),
    "it": dict(cid="italian", title="اللغة الإيطالية", name="الإيطالية",
               desc="دورة كاملة للناطقين بالعربية: النطق، ثم مئات الدروس المتدرّجة بجمل حقيقية، والقواعد، وتصريف الأفعال، والقراءة المتقدّمة.", order=3),
}

INTRO = {
    "es": ["الإسبانية تُكتب كما تُنطق تقريبًا، فإذا عرفت قواعد النطق قرأت أيّ كلمة.",
           "حروف العلّة خمسة صافية قصيرة: a (فتحة)، e (كسرة ممالة)، i (كسرة)، o (ضمّة ممالة)، u (ضمّة).",
           "j تُنطق خاءً: joven (شاب). وg قبل e وi خاء أيضًا: gente. وh لا تُنطق أبدًا: hola = أولا.",
           "ñ تُنطق نيـ: España. وll وy تُنطقان ياءً في أغلب البلاد: llamar.",
           "c قبل e وi، وz، تُنطق ثاءً في إسبانيا وسينًا في أمريكا اللاتينية: gracias. وqu = ك: queso.",
           "r في وسط الكلمة نقرة واحدة، وrr أو r في أوّل الكلمة راء مكرّرة قوية: pero (لكن) وperro (كلب).",
           "النبر: يقع على المقطع قبل الأخير إذا انتهت الكلمة بحرف علّة أو n أو s، وعلى الأخير في غير ذلك، وإلّا كُتبت علامة: café، teléfono."],
    "tr": ["تُكتب التركية بالحروف اللاتينية منذ ١٩٢٨، وكل حرف له صوت واحد ثابت.",
           "حروف خاصة: ç = تش، ş = ش، c = ج، ğ = لا تُنطق تقريبًا وتمدّ الحرف قبلها، ı (بلا نقطة) = صوت بين الكسرة والضمّة، ö وü = صوتا الواو والياء المضمومتان كما في الألمانية.",
           "حروف العلّة ثمانية في مجموعتين: خلفية a ı o u، وأمامية e i ö ü، وهذا أساس التوافق الصوتي الذي ستتعلّمه في الدروس الأولى.",
           "النبر غالبًا على المقطع الأخير.",
           "ستجد كلمات عربية كثيرة في التركية: kitap (كتاب)، saat (ساعة)، hayat (حياة)، dünya (دنيا)، merhaba (مرحبًا)، مع تغيّر في النطق أحيانًا."],
    "de": ["الألمانية تُنطق بانتظام كبير بعد معرفة قواعدها.",
           "ä تقارب فتحة ممالة، وö وü صوتان مضمومان مقدّمان، وß = ss.",
           "ch بعد a o u تُنطق خاءً (Buch)، وبعد e i وغيرها تُنطق كالهمس بين الشين والياء (ich).",
           "w تُنطق ڤاء، وv غالبًا فاء، وz = تس، وj = ياء، وsch = ش، وsp وst في أوّل الكلمة = شب وشت.",
           "ei = آي (mein)، ie = ياء طويلة (Liebe)، eu وäu = أوي (heute).",
           "كل الأسماء تبدأ بحرف كبير، ولكلّ اسم جنس من ثلاثة: der، die، das."],
    "it": ["الإيطالية تُقرأ كما تُكتب تقريبًا، وحروف العلّة الخمسة صافية.",
           "c وg قبل e وi تُنطقان تش وج: ciao، gelato. وقبل a o u أو مع h تُنطقان ك وغ: casa، chiesa، spaghetti.",
           "gn = نيـ (gnocchi)، وgli = لـيـ (famiglia)، وsc قبل e وi = ش (scienza).",
           "الحروف المضاعفة تُنطق مشدّدة كالشدّة العربية: pala (مجرفة) وpalla (كرة).",
           "h لا تُنطق أبدًا: ho = أو."],
    "fr": ["في الفرنسية حروف كثيرة لا تُنطق، خاصة في آخر الكلمة: petit = بُتي، parlent = بارل.",
           "ou = واو (vous)، oi = وا (moi)، au وeau = أو، ai = إ ممالة، é = إي، è وê = إ مفتوحة.",
           "الأصوات الأنفية: an/en، on، in، un تُنطق من الأنف دون نون واضحة.",
           "r تُنطق من الحلق قريبة من الغين، وj وg قبل e وi = ج معطّشة، وch = ش.",
           "الوصل (liaison): يُنطق الحرف الأخير الصامت إذا تلته كلمة تبدأ بحرف علّة: les amis = ليزامي."],
    "en": ["الإنجليزية لا تُقرأ دائمًا كما تُكتب، لذلك تسمع كل جملة في هذه الدورة وتكتبها.",
           "th لها صوتان: ث (think) وذ (this). وw = واو، وv = ڤ، وp ≠ b: pen (قلم) وBen (اسم).",
           "حروف العلّة القصيرة والطويلة تغيّر المعنى: ship (سفينة) وsheep (خروف)، full (ممتلئ) وfool (أحمق).",
           "e في آخر الكلمة لا تُنطق غالبًا وتطيل حرف العلّة قبلها: hat (قبعة) وhate (يكره)."],
}

METHOD = ("طريقة هذه الدورة: كل درس يقدّم الكلمات الأكثر شيوعًا التالية في اللغة، وكل جملة في الدرس مبنية "
          "من كلمات تعلّمتها فيه أو قبله، فتفهم كل ما تسمعه وتتقدّم خطوة خطوة. الجمل حقيقية ترجمها متطوّعون "
          "في مشروع تاتويبا. في التمارين: تختار المعنى، وتختار الجملة الصحيحة، وتكمل الفراغ، وترتّب الكلمات، "
          "وتكتب ما تسمعه. إذا لم تستطع كتابة الحروف الخاصة مثل á أو ş فاكتب الحرف دون علامته وتُقبل إجابتك، "
          "ويُعرض لك الإملاء الصحيح.")

PRON = {
    "es": [("first-person", "singular", "yo"), ("second-person", "singular", "tú"), ("third-person", "singular", "él/ella/usted"),
           ("first-person", "plural", "nosotros"), ("second-person", "plural", "vosotros"), ("third-person", "plural", "ellos/ustedes")],
    "it": [("first-person", "singular", "io"), ("second-person", "singular", "tu"), ("third-person", "singular", "lui/lei"),
           ("first-person", "plural", "noi"), ("second-person", "plural", "voi"), ("third-person", "plural", "loro")],
    "fr": [("first-person", "singular", "je"), ("second-person", "singular", "tu"), ("third-person", "singular", "il/elle"),
           ("first-person", "plural", "nous"), ("second-person", "plural", "vous"), ("third-person", "plural", "ils/elles")],
    "de": [("first-person", "singular", "ich"), ("second-person", "singular", "du"), ("third-person", "singular", "er/sie/es"),
           ("first-person", "plural", "wir"), ("second-person", "plural", "ihr"), ("third-person", "plural", "sie/Sie")],
}
TENSES = {
    "es": [({"present", "indicative"}, "المضارع (presente)"), ({"preterite", "indicative"}, "الماضي البسيط (pretérito)"),
           ({"imperfect", "indicative"}, "الماضي المستمرّ (imperfecto)"), ({"future", "indicative"}, "المستقبل (futuro)"),
           ({"conditional"}, "الشرطي (condicional)"), ({"present", "subjunctive"}, "صيغة الالتماس (subjuntivo)")],
    "it": [({"present", "indicative"}, "المضارع (presente)"), ({"imperfect", "indicative"}, "الماضي المستمرّ (imperfetto)"),
           ({"future", "indicative"}, "المستقبل (futuro)"), ({"conditional"}, "الشرطي (condizionale)"),
           ({"present", "subjunctive"}, "صيغة الالتماس (congiuntivo)")],
    "fr": [({"present", "indicative"}, "المضارع (présent)"), ({"imperfect", "indicative"}, "الماضي الناقص (imparfait)"),
           ({"future", "indicative"}, "المستقبل (futur)"), ({"conditional"}, "الشرطي (conditionnel)"),
           ({"present", "subjunctive"}, "صيغة الالتماس (subjonctif)")],
    "de": [({"present", "indicative"}, "المضارع (Präsens)"), ({"preterite", "indicative"}, "الماضي البسيط (Präteritum)"),
           ({"subjunctive-ii"}, "صيغة التمنّي الثانية (Konjunktiv II)")],
}
BAD_TAGS = {"vos-form", "multiword-construction", "archaic", "dialectal", "rare", "obsolete", "error", "negative",
            "imperative", "perfect", "pluperfect", "progressive", "romanization", "table-tags", "inflection-template",
            "participle", "gerund", "infinitive", "auxiliary", "subordinate-clause", "with-zu", "formal", "informal-plural"}
MOODS = {"subjunctive", "conditional", "imperative", "subjunctive-i", "subjunctive-ii"}
FORM_OK = re.compile(r"^[A-Za-zÀ-ÿœæŒÆß'’ -]+$")


def strip_it_accent(f):
    if not f:
        return f
    body, last = f[:-1], f[-1]
    body = "".join(unicodedata.normalize("NFD", ch)[0] if ch in "àèìòùáéíóú" else ch for ch in body)
    return body + last


def clean(t):
    return re.sub(r"\s+", " ", t.replace(" ", " ").replace("\xa0", " ")).strip()


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def cefr(n):
    for lim, lab in ((500, "A1 — مبتدئ"), (1200, "A2 — أساسي"), (2500, "B1 — متوسط"), (4000, "B2 — فوق المتوسط")):
        if n <= lim:
            return lab
    return "C1 — متقدّم"


def detect_names(pairs):
    cap, tot = collections.Counter(), collections.Counter()
    for p in pairs:
        toks = TOK.findall(p["t"])
        for i, w in enumerate(toks):
            lw = re.split(r"['’]", w.lower())[0]
            tot[lw] += 1
            if i > 0 and w[:1].isupper():
                cap[lw] += 1
    return {w for w, n in tot.items() if n >= 3 and cap[w] / n >= 0.95}


def word_rec(w, lex, lesson_no, sentences, stage):
    info = lex.get(w.lower()) or lex.get(w)
    ex = next((s for s in sentences if re.search(r"(?<![^\W\d_])" + re.escape(w) + r"(?![^\W\d_])", s["t"], re.I)), None)
    rec = {"word": w, "topic": f"L{lesson_no}", "difficulty": stage}
    rules = G.local_rules()
    if info and rules is not None and rules.blocked(CUR_LANG[0], w, info["ar"]):
        info = None
    if info:
        rec["meaning"] = info["ar"]
        if info.get("lemma"):
            rec["lemma"] = info["lemma"]
            rec["note"] = info.get("note", "")
    if ex:
        rec["example"], rec["translation"] = ex["t"], ex["ar"]
    return rec


def theory_for_words(words):
    blocks = []
    for r in words:
        head = f"{r['word']} = {r['meaning']}" if r.get("meaning") else r["word"]
        note = []
        if r.get("lemma"):
            note.append(f"صيغة من {r['lemma']}" + (f" ({r['note']})" if r.get("note") else ""))
        if r.get("example"):
            note.append(f"مثال: {r['example']} — {r['translation']}")
        blocks.append({"btype": "example", "text": head, "note": "؛ ".join(note)})
    return blocks


def note_blocks(n):
    out = [{"btype": "text", "text": f"قاعدة: {n['title']}"}]
    out += [{"btype": "text", "text": p} for p in n["text"]]
    out += [{"btype": "example", "text": a, "note": b} for a, b in n["examples"]]
    return out


def practice_blocks(kind="graded", n_words=0):
    B = lambda g, c: {"btype": "generated", "generator": g, "count": c, "data": "@bundle"}
    if kind == "graded":
        practice = ([B("lang.translate", 4)] if n_words >= 3 else []) + [
            B("phr.translate", 5), B("phr.reverse", 3), B("phr.cloze", 4), B("phr.build", 3)]
        quiz = [B("phr.translate", 3), B("phr.reverse", 2), B("phr.cloze", 2), B("phr.write", 2)] + (
            [B("lang.listen", 2)] if n_words >= 3 else [])
        review = [B("phr.dictation", 3), B("phr.build", 2)] + ([B("lang.truefalse", 2)] if n_words >= 3 else [])
    elif kind == "exam":
        practice = [B("phr.translate", 6), B("phr.reverse", 4), B("phr.cloze", 4)]
        quiz = [B("phr.translate", 6), B("phr.reverse", 5), B("phr.cloze", 5), B("phr.write", 4), B("phr.build", 4)]
        review = [B("phr.dictation", 5)]
    elif kind == "reading":
        practice = [B("phr.translate", 6), B("phr.reverse", 3), B("phr.cloze", 3)]
        quiz = [B("phr.translate", 4), B("phr.reverse", 3), B("phr.build", 3)]
        review = [B("phr.dictation", 3)]
    else:  # conj
        practice = [B("lang.conjugate", 10)]
        quiz = [B("lang.conjugate", 10)]
        review = [B("lang.conjugate", 6)]
    return practice, quiz, review


def _toks(t):
    return t.strip().rstrip(".!?؟…").replace("¿", "").replace("¡", "").split()


def feasible(g, data):
    ss = data.get("sentences", [])
    if g in ("phr.translate", "phr.reverse"):
        return len(ss) >= 2
    if g == "phr.build":
        return any(3 <= len(_toks(x["t"])) <= 9 and len(set(_toks(x["t"]))) == len(_toks(x["t"])) for x in ss)
    if g == "phr.cloze":
        return any(len(w) > 2 for x in ss for w in TOK.findall(x["t"]))
    if g == "phr.dictation":
        return any(len(x["t"]) <= 80 for x in ss)
    if g == "phr.write":
        return any(len(_toks(x["t"])) <= 7 for x in ss)
    if g.startswith("lang.") and g != "lang.conjugate":
        return len([w for w in data.get("words", []) if w.get("meaning")]) >= 3
    if g == "lang.conjugate":
        return bool(data.get("verbs"))
    return True


class Course:
    def __init__(self, c):
        self.c, self.conf = c, CONF[c]
        self.root = os.path.join(OUT, self.conf["cid"])
        self.levels = []
        self.count = 0

    def level(self, lid, title):
        lv = {"level_id": lid, "title": title, "order": len(self.levels) + 1, "lessons": []}
        self.levels.append(lv)
        return lv

    def lesson(self, lv, key, title, objectives, difficulty, theory, data, kind, n_words=0):
        lid = f"{self.conf['cid']}.{key}"
        practice, quiz, review = [[b for b in blocks if feasible(b["generator"], data)]
                                  for blocks in practice_blocks(kind, n_words)]
        if not (practice and quiz):
            raise SystemExit(f"lesson {lid} has no usable drills")
        bundle = {"theory": {"blocks": theory}, "practice": {"blocks": practice},
                  "quiz": {"blocks": quiz}, "review": {"blocks": review}, "data": data}
        write_json(os.path.join(self.root, "levels", lv["level_id"], key, "bundle.json"), bundle)
        lv["lessons"].append({"lesson_id": lid, "title": title, "order": len(lv["lessons"]),
                              "objectives": objectives, "grammar_refs": [], "difficulty": difficulty, "dir": key})
        self.count += 1

    def finish(self):
        write_json(os.path.join(self.root, "course.json"),
                   {"course_id": self.conf["cid"], "title": self.conf["title"], "description": self.conf["desc"],
                    "order": self.conf["order"], "version": "3.0.0", "levels": self.levels})


def conj_verbs(c, lex):
    if c == "tr":
        out = {}
        for key, label, fn in TC.TENSES:
            out[label] = [{"infinitive": inf, "meaning": ar, "tense": label, "forms": fn(inf), "difficulty": 2}
                          for inf, ar in TC.VERBS]
        return out
    if c not in TENSES:
        return {}
    freq = json.load(open(f"{S}/tatoeba/freq_{c}.json", encoding="utf-8"))
    rank = {w.lower(): i for i, w in enumerate(freq)}
    cands = []
    for line in open(f"{S}/wikt/dict_{c}.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("pos") != "verb" or not r.get("forms") or r.get("of"):
            continue
        inf = r["w"]
        meaning = (lex.get(inf.lower()) or {}).get("ar")
        if not meaning or " " in inf:
            continue
        forms = [(strip_it_accent(f) if c == "it" else f, set(t)) for f, t in r["forms"]]
        best = min([rank.get(f.lower(), 10 ** 6) for f, _ in forms] + [rank.get(inf.lower(), 10 ** 6)])
        cands.append((best, inf, meaning, forms))
    cands.sort(key=lambda x: x[0])
    seen, verbs = set(), []
    for best, inf, meaning, forms in cands:
        if inf in seen:
            continue
        seen.add(inf)
        verbs.append((inf, meaning, forms))
        if len(verbs) >= 60:
            break
    out = {}
    for need, label in TENSES[c]:
        recs = []
        for inf, meaning, forms in verbs:
            table = {}
            for person, number, pron in PRON[c]:
                for f, tags in forms:
                    if (need <= tags and person in tags and number in tags and not (tags & BAD_TAGS)
                            and not ((tags & MOODS) - need) and FORM_OK.match(f)
                            and not ("preterite" in tags and "preterite" not in need)
                            and not ("imperfect" in tags and "imperfect" not in need)
                            and not ("future" in tags and "future" not in need)
                            and not ("past" in tags and "preterite" not in need and "imperfect" not in need)):
                        table[pron] = f
                        break
            if len(table) == 6:
                recs.append({"infinitive": inf, "meaning": meaning, "tense": label, "forms": table, "difficulty": 2})
        out[label] = recs
    return out


CUR_LANG = ["en"]


def build(c):
    CUR_LANG[0] = c
    conf = CONF[c]
    pairs, freq, lex = G.load(S, c)
    for p in pairs:
        p["t"], p["ar"] = clean(p["t"]), clean(p["ar"])
    en_pairs = json.load(open(f"{S}/tatoeba/pairs_en.json", encoding="utf-8"))
    G.NAMES |= detect_names(en_pairs) | (detect_names(pairs) if c != "de" else set())
    lessons, reading, vocab = G.grade(c, pairs, freq, lex, per_lesson=10, max_vocab=5000, cap=30, min_sent=8)
    # split an overloaded first lesson so no lesson teaches more than 15 new words
    fixed = []
    for L in lessons:
        if len(L["new"]) > 15 and not fixed:
            words, sents = L["new"], L["sentences"]
            for i in range(0, len(words), 12):
                fixed.append({"new": words[i:i + 12], "sentences": [], "vocab_end": L["vocab_end"]})
            known = set()
            for part in fixed:
                known |= {w.lower() for w in part["new"]}
                part["sentences"] = [s for s in sents if {w.lower() for w in TOK.findall(s["t"]) if not G.is_name(w)} <= known
                                     and not any(s in q["sentences"] for q in fixed if q is not part)]
        else:
            fixed.append(L)
    lessons = fixed
    # top up sparse early lessons with short sentences that add at most one new word
    used = {s["t"] for L in lessons for s in L["sentences"]}
    rank = {}
    for i_, w_ in enumerate(freq):
        rank.setdefault(w_.lower(), i_)
    pool = []
    for p in pairs:
        if p["t"] in used or len(p["t"].split()) > 6:
            continue
        f = {w.lower() for w in TOK.findall(p["t"]) if not G.is_name(w)}
        if f:
            pool.append((len(p["t"]), p, f))
    pool.sort(key=lambda x: x[0])
    known = set()
    for L in lessons:
        known |= {w.lower() for w in L["new"]}
        if len(L["sentences"]) >= 10:
            continue
        extra = []
        for _, p, f in pool:
            if p["t"] in used:
                continue
            unknown = f - known
            if len(unknown) <= 1 and all(rank.get(u, 10 ** 6) < 3000 for u in unknown):
                extra.append(p)
                used.add(p["t"])
                for u in unknown:
                    if u not in {w.lower() for w in L["new"]}:
                        L["new"].append(u)
                known |= unknown
                if len(L["sentences"]) + len(extra) >= 12:
                    break
        L["sentences"] += [{"t": p["t"], "ar": p["ar"]} for p in extra]
    # display each word in its usual spelling (German nouns, English "I")
    casing = collections.defaultdict(collections.Counter)
    for p in pairs:
        for k_, w in enumerate(TOK.findall(p["t"])):
            if k_:
                casing[w.lower()][w] += 1
    disp = lambda w: casing[w.lower()].most_common(1)[0][0] if casing.get(w.lower()) else w.lower()
    for L in lessons:
        L["new"] = [disp(w) for w in L["new"]]
    for R in reading:
        R["new"] = [disp(w) for w in R["new"]]
    if os.path.isdir(os.path.join(OUT, conf["cid"])):
        shutil.rmtree(os.path.join(OUT, conf["cid"]))
    C = Course(c)
    notes = {n["id"]: n for n in NOTES.get(c, [])}
    trig = {}
    for n in NOTES.get(c, []):
        for t in n["triggers"]:
            trig.setdefault(t.lower(), n["id"])
    used_notes = set()
    base = {"lang": c, "lang_name": conf["name"]}

    # 0. introduction
    lv = C.level("intro", "قبل البدء: النطق وطريقة الدورة")
    th = [{"btype": "text", "text": METHOD}] + [{"btype": "text", "text": t} for t in INTRO[c]]
    first = lessons[0]["sentences"][:10]
    if len(first) < 6:
        first = [{"t": p["t"], "ar": p["ar"]} for p in sorted(pairs, key=lambda p: len(p["t"]))[:10]]
    th += [{"btype": "example", "text": s["t"], "note": s["ar"]} for s in first[:6]]
    C.lesson(lv, "intro", "النطق وطريقة الدورة", ["معرفة نطق الحروف", "فهم طريقة التعلّم المتدرّج"], 1, th,
             dict(base, sentences=first), "reading")

    # 1. graded stages
    per_stage = 20
    stage_no = 0
    exam_pool = []
    for i, L in enumerate(lessons):
        if i % per_stage == 0:
            stage_no += 1
            a = sum(len(x["new"]) for x in lessons[:i]) + 1
            b = sum(len(x["new"]) for x in lessons[:i + per_stage])
            lv = C.level(f"stage{stage_no:02d}", f"المرحلة {stage_no} ({cefr(b)}): الكلمات {a}–{b}")
            exam_pool = []
        n = i + 1
        stage = min(5, 1 + i // 80)
        words = [word_rec(w, lex, n, L["sentences"], stage) for w in L["new"]]
        th = [{"btype": "text", "text": f"الدرس {n}. الكلمات الجديدة: " + "، ".join(L["new"]) + "."}]
        th += theory_for_words(words)
        for w in L["new"]:
            nid = trig.get(w.lower())
            if nid and nid not in used_notes:
                used_notes.add(nid)
                th += note_blocks(notes[nid])
        if L["sentences"]:
            th.append({"btype": "text", "text": "جمل الدرس:"})
            th += [{"btype": "example", "text": s["t"], "note": s["ar"]} for s in L["sentences"][:10]]
        meaning_words = [w for w in words if w.get("meaning") and not w.get("lemma")]
        data = dict(base, sentences=L["sentences"], focus=L["new"], words=meaning_words, difficulty=stage)
        title = f"الدرس {n}: " + " · ".join(L["new"][:3])
        C.lesson(lv, f"g{n:03d}", title, [f"تعلّم {len(L['new'])} كلمات جديدة", "فهم جمل الدرس وكتابتها"],
                 stage, th, data, "graded", len(meaning_words))
        exam_pool += L["sentences"]
        if (i + 1) % per_stage == 0 or i == len(lessons) - 1:
            rnd = random.Random(f"{c}{stage_no}")
            pool = rnd.sample(exam_pool, min(80, len(exam_pool)))
            C.lesson(lv, f"exam{stage_no:02d}", f"اختبار المرحلة {stage_no}",
                     ["مراجعة شاملة لكلمات المرحلة وجملها"], stage,
                     [{"btype": "text", "text": f"اختبار شامل للمرحلة {stage_no}: جمل من كل دروسها. انجح فيه قبل الانتقال."}],
                     dict(base, sentences=pool, difficulty=stage), "exam")

    # 2. grammar reference
    if NOTES.get(c):
        lv = C.level("grammar", "القواعد: مرجع وتطبيق")
        for k, nt in enumerate(NOTES[c]):
            trg = [t.lower() for t in nt["triggers"]]
            sents = []
            for p in pairs:
                toks = {w.lower() for w in TOK.findall(p["t"])}
                low = p["t"].lower()
                if any((t in toks) if " " not in t else (t in low) for t in trg) and len(p["t"]) < 70:
                    sents.append({"t": p["t"], "ar": p["ar"]})
                if len(sents) >= 40:
                    break
            sents += [{"t": a, "ar": b} for a, b in nt["examples"]]
            C.lesson(lv, f"gr{k + 1:02d}", nt["title"], ["فهم القاعدة", "تطبيقها على جمل حقيقية"], 2,
                     note_blocks(nt), dict(base, sentences=sents), "reading")

    # 3. conjugation
    tables = conj_verbs(c, lex)
    if tables:
        lv = C.level("conjugation", "تصريف الأفعال")
        k = 0
        for label, recs in tables.items():
            for j in range(0, len(recs), 10):
                grp = recs[j:j + 10]
                if len(grp) < 3:
                    continue
                k += 1
                th = [{"btype": "text", "text": f"{label}: " + "، ".join(f"{r['infinitive']} ({r['meaning']})" for r in grp) + "."}]
                for r in grp[:4]:
                    th.append({"btype": "example", "text": r["infinitive"],
                               "note": "، ".join(f"{p} {f}" for p, f in r["forms"].items())})
                C.lesson(lv, f"cj{k:02d}", f"{label} — الأفعال {j + 1}–{j + len(grp)}",
                         ["حفظ تصريف الأفعال الشائعة"], 3, th, dict(base, verbs=grp), "conj")

    # 4. advanced reading
    if reading:
        reading = [r for r in reading if len(r["sentences"]) >= 8][:160]
        for i, R in enumerate(reading):
            if i % per_stage == 0:
                lv = C.level(f"reading{i // per_stage + 1:02d}", f"القراءة المتقدّمة {i // per_stage + 1}")
            n = i + 1
            words = [word_rec(w, lex, 9000 + n, R["sentences"], 5) for w in R["new"][:12]]
            th = [{"btype": "text", "text": "جمل أطول ومفردات أقلّ شيوعًا. الكلمات الجديدة في معظمها مشروحة أدناه."}]
            th += theory_for_words([w for w in words if w.get("meaning")])
            th += [{"btype": "example", "text": s["t"], "note": s["ar"]} for s in R["sentences"][:12]]
            C.lesson(lv, f"r{n:03d}", f"قراءة {n}", ["فهم جمل متقدّمة"], 5, th,
                     dict(base, sentences=R["sentences"], focus=R["new"], difficulty=5), "reading")
    C.finish()
    print(c, conf["cid"], "lessons", C.count, "levels", len(C.levels), "graded", len(lessons),
          "notes used", len(used_notes), "/", len(NOTES.get(c, [])),
          "conj", {k: len(v) for k, v in tables.items()})


for c in LANGS:
    build(c)
