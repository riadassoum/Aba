# -*- coding: utf-8 -*-
"""Tests for the 4.0 tools: analyser, collocations, ciphers, SQL lab,
inheritance, solutions, distributions and the new math-lab operations."""

from fractions import Fraction as F

import pytest

from abaAcademy.tools import ciphers, mawarith
from abaAcademy.codelab import sql_lab
from abaAcademy.science import solutions
from abaAcademy.math_engine import distributions as dist
from abaAcademy.arabic_lab import collocations


def shares(h):
    return {s.key: s.fraction for s in mawarith.compute(h).shares}


@pytest.mark.parametrize("heirs,expect", [
    ({"wife": 1, "son": 1, "daughter": 1}, {"wife": F(1, 8), "son": F(7, 12), "daughter": F(7, 24)}),
    ({"husband": 1, "full_sister": 2, "mother": 1}, {"husband": F(3, 8), "full_sister": F(1, 2), "mother": F(1, 8)}),
    ({"husband": 1, "father": 1, "mother": 1}, {"mother": F(1, 6), "father": F(1, 3)}),
    ({"wife": 1, "father": 1, "mother": 1}, {"mother": F(1, 4), "father": F(1, 2)}),
    ({"daughter": 1, "sons_daughter": 1, "full_sister": 1}, {"sons_daughter": F(1, 6), "full_sister": F(1, 3)}),
    ({"daughter": 2, "mother": 1}, {"daughter": F(4, 5), "mother": F(1, 5)}),
    ({"wife": 1, "daughter": 2, "father": 1, "mother": 1}, {"wife": F(1, 9), "daughter": F(16, 27)}),
    ({"husband": 1, "mother": 1, "mat_brother": 2, "full_brother": 1}, {"full_brother": 0, "mat_brother": F(1, 3)}),
    ({"father": 1, "daughter": 1}, {"father": F(1, 2)}),
    ({"son": 1, "full_brother": 2}, {"full_brother": 0, "son": 1}),
    ({"full_uncle": 2, "wife": 2}, {"full_uncle": F(3, 4), "wife": F(1, 4)}),
    ({"daughter": 2, "sons_daughter": 1, "sons_son": 1}, {"sons_son": F(2, 9), "sons_daughter": F(1, 9)}),
])
def test_mawarith(heirs, expect):
    got = shares(heirs)
    for k, v in expect.items():
        assert got[k] == v, (k, got[k], v)
    assert sum(got.values()) == 1


def test_mawarith_errors():
    with pytest.raises(ValueError):
        mawarith.compute({"husband": 1, "wife": 1})
    with pytest.raises(ValueError):
        mawarith.compute({})


def test_ciphers():
    e = ciphers.caesar("العلم نور", 3)
    assert ciphers.caesar(e, 3, decrypt=True) == "العلم نور"
    assert ciphers.crack_caesar(ciphers.caesar("Attack at dawn, the enemy is near the river", 7))[0] == 7
    assert ciphers.vigenere("Hello World", "key") == "Rijvs Uyvjn"
    assert ciphers.rail_fence("WEAREDISCOVERED", 3) == "WECRERDSOEEAIVD"
    assert ciphers.rail_fence("WECRERDSOEEAIVD", 3, decrypt=True) == "WEAREDISCOVERED"
    assert ciphers.from_base64(ciphers.to_base64("سلام")) == "سلام"
    assert ciphers.from_binary(ciphers.to_binary("ab")) == "ab"
    assert ciphers.abjad("محمد") == 92
    assert ciphers.atbash(ciphers.atbash("abc")) == "abc"
    for i in range(len(ciphers.METHODS)):
        ciphers.run(i, "abc" if "من" not in ciphers.METHODS[i] else "YWJj" if "Base64" in ciphers.METHODS[i]
                    else ("01100001" if "الثنائي" in ciphers.METHODS[i] else "61"),
                    "key" if "فيجنير" in ciphers.METHODS[i] else "3")


def test_sql_lab():
    con = sql_lab.new_db()
    assert sql_lab.run(con, "select count(*) from students").rows == [(10,)]
    for ex in sql_lab.EXERCISES:
        assert sql_lab.check(ex, ex.answer)[0], ex.title
    assert not sql_lab.check(sql_lab.EXERCISES[2], "select name from students")[0]
    with pytest.raises(sql_lab.SQLError):
        sql_lab.run(con, "attach database 'x.db' as y")
    with pytest.raises(sql_lab.SQLError):
        sql_lab.run(con, "with recursive r(n) as (select 1 union all select n+1 from r) select count(*) from r")
    with pytest.raises(sql_lab.SQLError):
        sql_lab.run(con, "select 1; select 2")
    assert "إسرائيل" not in repr(sql_lab.STUDENTS + sql_lab.BOOKS)


def test_solutions():
    assert solutions.ph_strong_acid(0.01)[0] == pytest.approx(2)
    assert solutions.ph_weak_acid(0.1, 1.8e-5)[0] == pytest.approx(2.875, abs=1e-3)
    assert solutions.ph_strong_base(0.001)[0] == pytest.approx(11)
    assert solutions.dilution(2, 0.5, 0, 2)[0] == pytest.approx(0.5)
    assert solutions.ideal_gas(1, 0, 1, 273.15)[0] == pytest.approx(22.41, abs=0.01)
    with pytest.raises(ValueError):
        solutions.dilution(1, 0, 0, 2)


def test_distributions():
    assert dist.probability("ذات الحدّين", 10, 0.5, "يساوي", 5)[0] == pytest.approx(0.24609375)
    assert dist.probability("بواسون", 3, 0, "أقلّ من أو يساوي", 2)[0] == pytest.approx(0.42319, abs=1e-5)
    assert dist.probability("الطبيعي", 100, 15, "بين قيمتين (شاملًا)", 85, 115)[0] == pytest.approx(0.6827, abs=1e-4)
    assert dist.probability("الهندسي", 0.5, 0, "يساوي", 2)[0] == pytest.approx(0.25)
    assert dist.t_cdf(2.228, 10) == pytest.approx(0.975, abs=1e-3)
    lo, hi, _ = dist.confidence_interval(50, 10, 16)
    assert (lo, hi) == pytest.approx((44.67, 55.33), abs=0.01)


def test_collocations():
    if not collocations.available():
        pytest.skip("maskouk data missing")
    assert collocations.count() > 20000
    assert collocations.search("صلاة")
    q = collocations.make_question()
    assert q and q.answer in q.options and len(q.options) == 4
    assert not any("اللَّهُ الْيَهُودَ" == c.vocalized for c in collocations.search("اليهود", 500))


def test_math_lab_new():
    from abaAcademy import math_lab as ml
    if not ml.AVAILABLE:
        pytest.skip("sympy missing")
    w, s = ml.study("س^3-3س")
    assert "نهاية عظمى محلّية" in s and "نقاط الانعطاف" in s
    assert "خطّ تقارب رأسي" in ml.study("1/(س-1)")[1]
    assert "مائل" in ml.study("(س^2+1)/س")[1]
    assert ml.taylor("جا(س)", "0", 5)[0].startswith("س^5/120")
    assert ml.summation("ك^2", "1", "ن")[0] == "ن×(2×ن^2 + 3×ن + 1)/6"
    assert ml.summation("1/2^ك", "1", "∞")[0] == "1"
    assert "سالب ما لا نهاية" in ml.study("س^3")[1]


def test_analyzer():
    from abaAcademy.arabic_lab import analyzer, diacritizer
    if not diacritizer.available():
        pytest.skip("mishkal missing")
    rs = analyzer.analyse("المدرسة")
    assert rs and rs[0].root == "درس"
    assert analyzer.lemmas("ذهب الطلاب إلى المدارس") == ["ذهب", "طالب", "إلى", "مدارس"]
    with pytest.raises(ValueError):
        analyzer.analyse("كلمتان هنا")


@pytest.mark.parametrize("n,lang,expect", [
    (21, "fr", "vingt et un"), (71, "fr", "soixante et onze"), (80, "fr", "quatre-vingts"),
    (80000, "fr", "quatre-vingt mille"), (200, "fr", "deux cents"), (201, "fr", "deux cent un"),
    (2000000, "fr", "deux millions"), (21000, "es", "veintiún mil"), (500, "es", "quinientos"),
    (100, "es", "cien"), (101, "es", "ciento uno"), (1984, "de", "eintausendneunhundertvierundachtzig"),
    (1, "de", "eins"), (101, "de", "einhunderteins"), (28, "it", "ventotto"), (23, "it", "ventitré"),
    (108, "it", "centotto"), (2000, "it", "duemila"), (1984, "tr", "bin dokuz yüz seksen dört"),
    (100, "tr", "yüz"), (2001, "en", "two thousand and one"), (3021508, "es", "tres millones veintiún mil quinientos ocho"),
])
def test_num_words(n, lang, expect):
    from abaAcademy.tools import num_words
    assert num_words.words(n, lang) == expect


def test_num_words_quiz():
    from abaAcademy.tools import num_words
    import random
    r = random.Random(3)
    for lang in num_words.LANGS:
        for d in ("to_number", "to_words"):
            q = num_words.make_question(lang, 2, r, d)
            assert q.answer in q.options and len(set(q.options)) == 4
    with pytest.raises(ValueError):
        num_words.en(-1)


def test_english_pron():
    from abaAcademy import english_pron as ep
    if not ep.available():
        pytest.skip("cmudict missing")
    p = ep.lookup("photography")
    assert p.syllables == 4 and p.stress == 1 and p.ipa() == "/fətˈɑɡrəfi/"
    assert "k في kn" in ep.lookup("knight").describe()
    assert "night" in ep.rhymes("light")
    import random
    r = random.Random(1)
    for k, _ in [(k, 0) for _, k in ep.QUIZ_KINDS]:
        q = ep.make_question(k, r)
        assert q and q.answer in q.options
