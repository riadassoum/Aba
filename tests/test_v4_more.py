# -*- coding: utf-8 -*-
"""Tests for the later 4.0 additions: foreign verb conjugation, country
languages, the solar system, English irregulars, the symbolic maths lab and
the bundled Qur'an translations."""

import json
import os
import random

import pytest

R = os.path.join(os.path.dirname(__file__), "..", "abaAcademy", "resources")


def test_foreign_verbs():
    from abaAcademy import verb_tables as vt
    assert vt.table_text("fr", "aller", "Indicatif/présent").split("\n")[0] == "je vais"
    assert vt.table_text("fr", "aimer", "Indicatif/présent").split("\n")[0] == "j'aime"
    assert "tuvimos" in vt.table_text("es", "tener", "Indicativo/pretérito-perfecto-simple")
    assert "siamo" in vt.table_text("it", "essere", "Indicativo/presente")
    assert vt.conjugate("fr", "nimportequoi") is None
    for lang in vt.LANGS:
        assert len(vt.load(lang)["verbs"]) > 6000
        assert set(vt.tenses(lang)) <= set(vt.TENSE_NAMES)
        q = vt.make_question(lang, random.Random(1))
        assert q.answer in q.options and len(set(q.options)) == 4


def test_country_languages():
    from abaAcademy import geo_countries as g
    by = {c["iso"]: c for c in g.load()}
    assert by["MAR"]["languages"] == ["العربية", "الأمازيغية"]
    assert "اللغات الرسمية" in g.describe(by["LBN"])
    q = g.make_question(g.load(), "language", rng=random.Random(2))
    assert q.answer in q.options and len(set(q.options)) == 4


def test_solar_system():
    from abaAcademy.science import solar_system as s
    b = {x["id"]: x for x in s.load()}
    assert len(b) == 12 and b["Q405"]["name"] == "القمر"
    assert 1.4e11 < b["Q2"]["distance_m"] < 1.6e11 and 9.7 < b["Q2"]["gravity"] < 9.9
    assert "يدور حول الشمس في نحو 1.88 سنة" in s.describe(b["Q111"], list(b.values()))
    rng = random.Random(4)
    for _ in range(20):
        q = s.make_question(list(b.values()), rng)
        assert q.answer in q.options


def test_english_irregulars():
    from abaAcademy import english_irregulars as ei
    d = ei.data()
    go = next(v for v in d["verbs"] if v["base"] == "go")
    assert (go["past"], go["part"]) == ("went", "gone")
    assert not any(v["base"] == "want" for v in d["verbs"])
    assert any(n["sing"] == "child" and n["pl"] == "children" for n in d["nouns"])
    rng = random.Random(5)
    for _ in range(30):
        q = ei.make_question(rng)
        assert q.answer in q.options and len(set(q.options)) == len(q.options)


@pytest.mark.skipif(not __import__("abaAcademy.math_lab", fromlist=["x"]).AVAILABLE, reason="no sympy")
def test_math_lab():
    from abaAcademy import math_lab as m
    assert m.solve("س^2 - 5س + 6 = 0")[0] == "س = 2 أو س = 3"
    assert "حلّان" in m.solve("x^2 = 4")[1]
    assert m.solve("x+y=5, x-y=1")[0] == "س = 3، ص = 2"
    assert m.expand("(س+3)^2")[1] == "س تربيع زائد ستة س زائد تسعة"
    assert m.differentiate("x^3")[0] == "3×س^2"
    assert m.integrate("2x")[0] == "س^2 + C"
    assert m.factor("360")[0] == "2^3 × 3^2 × 5"
    assert m.limit("جا(x)/x", "0")[0] == "1"
    for bad in ('__import__("os")', "open('x')", "x.__class__"):
        with pytest.raises(m.MathError):
            m.parse(bad)


def test_bundled_translations():
    for e in ("es.cortes", "de.bubenheim", "it.piccardo", "tr.diyanet", "en.sahih", "fr.hamidullah"):
        d = json.load(open(os.path.join(R, "quran", f"ed_{e}.json"), encoding="utf-8"))
        assert len(d) == 6236 and all(d[:7])


def test_mishkal_diacritizer():
    from abaAcademy.arabic_lab import diacritizer as d
    assert d.available()
    out = d.diacritize("ذهب الولد إلى المدرسة\nالعلم نور")
    assert out.split("\n")[0] == "ذَهَبَ الْوَلَدُ إِلَى الْمَدْرَسَةِ"
    assert out.split("\n")[1].startswith("الْعِلْمُ")
