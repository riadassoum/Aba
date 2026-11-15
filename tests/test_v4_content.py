# -*- coding: utf-8 -*-
"""Tests for the 4.0 content engines: tajweed, spell checking, the NVDA
course and the world atlas."""

import json
import random

import pytest

from abaAcademy import geo_countries as geo
from abaAcademy import nvda_course as nc
from abaAcademy import spell
from abaAcademy import tajweed as tjm


# -- tajweed -------------------------------------------------------------------

@pytest.fixture(scope="module")
def tj():
    return tjm.Tajweed.get()


def test_tajweed_coverage_and_alignment(tj):
    assert len(tj.marks) > 5800                  # of 6236 ayat
    expect = {"hamzat_wasl": "ٱ", "lam_shamsiyyah": "ل", "qalqalah": "قطبجد", "iqlab": "نًٌٍ",
              "ikhfa_shafawi": "م", "idghaam_shafawi": "م"}
    for (s, a), rows in tj.marks.items():
        text = tj.text[(s, a)]
        for rule, start, end in rows:
            assert 0 <= start < end <= len(text)
            if rule in expect:
                assert any(c in expect[rule] for c in text[start:end]), (s, a, rule)


def test_tajweed_fatiha(tj):
    out = tj.describe_ayah(1, 7)
    assert "المدّ اللازم في كلمة الضالين" in out
    assert "اللام الشمسيّة في كلمة الضالين" in out


def test_tajweed_every_rule_explained_and_grouped():
    grouped = {r for _, rs in tjm.GROUPS for r in rs}
    assert grouped == set(tjm.RULES)
    for r in tjm.RULES:
        assert tjm.rule_text(r).endswith(".")
        assert "«" not in tjm.rule_text(r)


def test_tajweed_quiz(tj):
    rng = random.Random(5)
    for _ in range(20):
        q = tjm.make_question(tj, rng=rng)
        assert q.answer in q.options and len(set(q.options)) == 4


def test_unverified_ayah_says_so(tj):
    missing = [k for k in tj.text if not tj.verified(*k)]
    if missing:
        assert "لا تتوفّر" in tj.describe_ayah(*missing[0])


# -- spell ---------------------------------------------------------------------

@pytest.mark.skipif(not spell.available("ar"), reason="dictionaries not bundled")
def test_spell_arabic():
    c = spell.Checker()
    for w in ["كتاب", "والكتاب", "بالمدرسة", "يكتبون", "مدرستهم"]:
        assert c.check(w), w
    assert not c.check("المدرسه")
    assert c.suggest("المدرسه")[0] == "المدرسة"
    assert "ذهبوا" in c.suggest("ذهبو")[:2]
    errs = c.errors("ذهبت الى المدرسه صباحا")
    assert [w for _, _, w in errs] == ["الى", "المدرسه"]


@pytest.mark.skipif(not spell.available("en"), reason="dictionaries not bundled")
def test_spell_english_french_and_personal():
    c = spell.Checker("en", personal=["Assoum"])
    assert c.check("children") and c.check("unhappiness") and c.check("Assoum")
    assert c.suggest("recieve")[0] == "receive"
    c.latin = "fr"
    assert c.check("mangeons") and c.check("l'homme")
    assert "beaucoup" in c.suggest("beaucop")


# -- NVDA ----------------------------------------------------------------------

def test_nvda_commands():
    lessons = nc.load()
    assert len(lessons) >= 10
    all_cmds = {c.script: c for l in lessons for c in l.commands}
    assert len(all_cmds) > 150
    say_all = all_cmds["sayAll"]
    assert say_all.keys_text("laptop") == "NVDA+A"
    assert "السهم الأسفل" in say_all.keys_text("desktop")
    assert all(any("؀" <= ch <= "ۿ" for ch in c.ar) for c in all_cmds.values())
    rng = random.Random(1)
    for i in range(30):
        q = nc.make_question(lessons, "desktop" if i % 2 else "laptop", None, rng)
        assert q.answer in q.options and len(set(q.options)) == len(q.options)


# -- world atlas ---------------------------------------------------------------

def test_countries():
    cs = geo.load()
    assert len(cs) == 194
    by = {c["iso"]: c for c in cs}
    assert by["MAR"]["capital"] == "الرباط" and "درهم" in by["MAR"]["currency"]
    assert by["IRQ"]["capital"] == "بغداد"
    assert by["PSE"]["capital"] == "القدس" and "ISR" not in by
    assert "إسرائيل" not in json.dumps(cs, ensure_ascii=False)
    assert len([c for c in cs if c["iso"] in geo.ARAB_LEAGUE]) == 22
    for c in cs:
        for b in c["borders"]:
            other = next(x for x in cs if x["name"] == b)
            assert c["name"] in other["borders"], (c["name"], b)
    rng = random.Random(2)
    for k in geo.KINDS:
        q = geo.make_question(cs, k, rng=rng)
        assert q and q.answer in q.options


# -- morphology, i'rab, maths braille, programming challenges -----------------

def test_sarf_lookup_and_quiz():
    from abaAcademy.arabic_lab import sarf as sf
    s = sf.Sarf.get()
    assert len(s.words) > 25000 and len(s.verbs) > 7000
    found = "\n".join(s.lookup("مدرسة"))
    assert "مَدَارِس" in found
    assert any("كتب" in x or "كَتَبَ" in x for x in s.root_family("ك ت ب"))
    assert sf.present_tense({"v": "نَصَرَ", "bab": 1}) == "يَنْصُرُ"
    assert sf.present_tense({"v": "ضَرَبَ", "bab": 2}) == "يَضْرِبُ"
    assert sf.present_tense({"v": "قَالَ", "bab": 1}) == ""        # weak verbs are not guessed
    t = sf.Trainer(s, random.Random(1))
    for k, _ in sf.KINDS:
        q = t.question(k)
        assert q and q.answer in q.options and len(set(q.options)) == len(q.options), k


def test_irab_items_are_the_books_words():
    from abaAcademy.arabic_lab import irab
    ir = irab.Irab.get()
    assert len(ir.items) > 10000
    for it in ir.items[:500]:
        assert irab.role_of(it.text) == it.role
    rng = random.Random(3)
    for _ in range(30):
        q = irab.make_question(ir, rng=rng)
        assert q.answer in q.options and len(set(q.options)) == 4


def test_math_braille_round_trip():
    from abaAcademy.braille_engine import louis
    for s in ["3 + 4 = 7", "5 × 6 = 30", "8 ÷ 2 ≠ 5", "∞ π"]:
        assert louis.back_translate(louis.translate(s, 1), 1) == s
    signs = louis.math_signs()
    assert len(signs) > 30 and all(name and cells for _, name, cells in signs)


def test_new_challenges_pass_with_reference():
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "devtools", "course_builder"))
    from exercism_spec_v4 import SPECS_V4
    from abaAcademy.codelab.challenges import check_solution, tracks
    ref = {f"ex_{s['fn']}": s["ref"] for s in SPECS_V4}
    seen = 0
    cids = [c.cid for _, _, chs in tracks() for c in chs]
    assert len(cids) == len(set(cids))
    for _, _, chs in tracks():
        for c in chs:
            if c.cid in ref:
                ok, msg = check_solution(c, ref[c.cid])
                assert ok, (c.cid, msg)
                seen += 1
    assert seen == len(SPECS_V4)
