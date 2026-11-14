# -*- coding: utf-8 -*-
"""The graded language courses (bundled lessons, sentence generators, verb
tables) and the programming challenge tracks."""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(PKG))

from abaAcademy import generators as gen
from abaAcademy.engine.grading import grade
from abaAcademy.generators.phrases import plain

gen.load_builtin_generators()
COURSES = os.path.join(PKG, "courses")
GRADED = ["english_graded", "french_graded", "spanish", "turkish", "german", "italian"]

PAIRS = [{"t": "Tengo un perro.", "ar": "عندي كلب."}, {"t": "¿Dónde está la casa?", "ar": "أين البيت؟"},
         {"t": "Me gusta el café.", "ar": "يعجبني البنّ."}, {"t": "Ella habla español.", "ar": "هي تتكلّم الإسبانية."}]


def _academy():
    from abaAcademy.academy import Academy
    return Academy(base_dir=PKG, user_data_dir=tempfile.mkdtemp())


def test_graded_courses_are_long_and_structured():
    for cid in GRADED:
        c = json.load(open(os.path.join(COURSES, cid, "course.json"), encoding="utf-8"))
        lessons = [l for lv in c["levels"] for l in lv["lessons"]]
        assert len(lessons) >= 600, (cid, len(lessons))
        ids = [lv["level_id"] for lv in c["levels"]]
        assert ids[0] == "intro" and "stage01" in ids and "grammar" in ids and any(i.startswith("reading") for i in ids), ids
        assert sum(1 for l in lessons if l["dir"].startswith("exam")) >= 20


def test_bundle_lessons_load_with_shared_data():
    ac = _academy()
    try:
        L = ac.load_lesson("spanish.g050")
        assert L and L.theory and L.practice and L.quiz and L.review
        gen_blocks = [b for b in L.practice if b.btype.value == "generated"]
        assert gen_blocks and all("sentences" in b.data.get("params", {}) for b in gen_blocks)
        assert "data" not in gen_blocks[0].data
        sess = ac.build_lesson_quiz("turkish.g120", seed=2)
        n = 0
        while sess.has_next() and n < 40:
            if sess.next_question() is None:
                break
            n += 1
        assert n >= 8
    finally:
        ac.close()


def test_phrase_generators():
    common = dict(sentences=PAIRS, lang="es", lang_name="الإسبانية", focus=["perro", "casa"])
    for g in ("phr.translate", "phr.reverse", "phr.build", "phr.cloze", "phr.dictation", "phr.write"):
        qs = gen.generate(g, count=3, seed=4, **common)
        assert qs, g
        for q in qs:
            assert q.prompt and q.explanation
    q = gen.generate("phr.translate", count=1, seed=1, **common)[0]
    assert q.options[q.correct] in {p["ar"] for p in PAIRS}
    q = gen.generate("phr.cloze", count=1, seed=3, **common)[0]
    assert "-----" in q.prompt and len(set(q.options)) == len(q.options)


def test_typed_answers_accept_plain_letters():
    assert plain("¿Dónde está?") == "¿Donde esta?"
    assert plain("Gülüyorsun, değil mi?") == "Guluyorsun, degil mi?"
    assert plain("Straße") == "Strasse" and plain("ılık") == "ilik"
    q = [x for x in gen.generate("phr.dictation", count=4, seed=1, sentences=PAIRS, lang="es") if "Dónde" in x.correct]
    if q:
        assert grade(q[0], "Donde esta la casa") and grade(q[0], "¿Dónde está la casa?")


def test_verb_tables():
    def verbs(cid, lv="conjugation"):
        base = os.path.join(COURSES, cid, "levels", lv)
        out = {}
        for d in sorted(os.listdir(base)):
            b = json.load(open(os.path.join(base, d, "bundle.json"), encoding="utf-8"))
            for v in b["data"]["verbs"]:
                out[(v["tense"], v["infinitive"])] = v["forms"]
        return out
    es = verbs("spanish")
    ser = next(f for (t, inf), f in es.items() if inf == "ser" and "presente" in t)
    assert ser == {"yo": "soy", "tú": "eres", "él/ella/usted": "es", "nosotros": "somos",
                   "vosotros": "sois", "ellos/ustedes": "son"}
    tr = verbs("turkish")
    gel = next(f for (t, inf), f in tr.items() if inf == "gelmek" and "-iyor" in t and "نفي" not in t)
    assert gel["ben"] == "geliyorum" and gel["onlar"] == "geliyorlar"
    git_past = next(f for (t, inf), f in tr.items() if inf == "gitmek" and "-di" in t)
    assert git_past["ben"] == "gittim" and git_past["siz"] == "gittiniz"
    et_fut = next(f for (t, inf), f in tr.items() if inf == "etmek" and "-ecek" in t)
    assert et_fut["ben"] == "edeceğim" and et_fut["o"] == "edecek"
    de = verbs("german")
    sein = next(f for (t, inf), f in de.items() if inf == "sein" and "Präsens" in t)
    assert sein["ich"] == "bin" and sein["ihr"] == "seid"


def test_starter_flashcard_decks_for_every_language():
    idx = json.load(open(os.path.join(PKG, "resources", "flashcards", "index.json"), encoding="utf-8"))
    courses = {d["course"] for d in idx}
    assert set(GRADED) <= courses
    d = next(x for x in idx if x["course"] == "turkish")
    cards = json.load(open(os.path.join(PKG, "resources", "flashcards", d["id"] + ".json"), encoding="utf-8"))
    assert len(cards) >= 50 and all(c["front"] and c["back"] for c in cards)


def test_challenge_tracks():
    from abaAcademy.codelab.challenges import tracks, all_challenges, check_solution, get_challenge
    ts = tracks()
    assert len(ts) == 10 and len(all_challenges()) >= 150
    assert len({c.cid for c in all_challenges()}) == len(all_challenges())
    for _, _, items in ts:
        for c in items:
            ok, _ = check_solution(c, c.starter or "pass")
            assert not ok, c.cid
    good = {
        "ex_leap_year": "def leap_year(year):\n    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)\n",
        "ex_roman": "def roman(n):\n    v=[(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]\n    s=''\n    for a,r in v:\n        while n>=a:\n            s+=r; n-=a\n    return s\n",
        "ex_rle_encode": "from itertools import groupby\ndef rle_encode(t):\n    return ''.join((str(len(list(g))) if False else '') for _ in [0]) or ''.join((lambda n,ch:(str(n) if n>1 else '')+ch)(len(list(g)),ch) for ch,g in groupby(t))\n",
        "o_f10": "def frequencies(items):\n    out={}\n    for x in items:\n        out[x]=out.get(x,0)+1\n    return out\n",
        "o_k03": "class Stack:\n    def __init__(self): self.items=[]\n    def push(self,x): self.items.append(x)\n    def pop(self): return self.items.pop() if self.items else None\n    def peek(self): return self.items[-1] if self.items else None\n    def size(self): return len(self.items)\n    def is_empty(self): return not self.items\n",
        "o_o22": "for i in range(1, 31):\n    print('FizzBuzz' if i % 15 == 0 else 'Fizz' if i % 3 == 0 else 'Buzz' if i % 5 == 0 else i)\n",
    }
    for cid, src in good.items():
        ok, msg = check_solution(get_challenge(cid), src)
        assert ok, (cid, msg)
    ok, msg = check_solution(get_challenge("ex_leap_year"), "def leap_year(y):\n    return y % 4 == 0\n")
    assert not ok and "False" in msg
