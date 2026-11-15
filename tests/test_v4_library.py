# -*- coding: utf-8 -*-
"""Tests for the 4.0 library: bundled hadith collections and tafsirs, Qur'an
morphology, the offline dictionary and WordNet, and the sentence bank."""

import json
import os
import random

R = os.path.join(os.path.dirname(__file__), "..", "abaAcademy", "resources")


def test_hadith_collections_bundled_with_arabic_titles():
    idx = json.load(open(os.path.join(R, "hadith", "index.json"), encoding="utf-8"))
    big = [e for e in idx if e["id"] in ("bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah", "malik")]
    assert len(big) == 7 and all(e["bundled"] for e in big)
    total = 0
    for e in big:
        d = json.load(open(os.path.join(R, "hadith", e["id"] + ".json"), encoding="utf-8"))
        assert d["books"] and all(b["title"] for b in d["books"])
        assert all(b["title"].startswith("كتاب") or b["title"] in ("المقدّمة", "أحاديث متفرّقة") for b in d["books"])
        total += sum(len(b["hadiths"]) for b in d["books"])
        assert "«" not in json.dumps(d, ensure_ascii=False)
    assert total > 35000
    bk = json.load(open(os.path.join(R, "hadith", "bukhari.json"), encoding="utf-8"))
    import re
    first = next(b for b in bk["books"] if b["no"] == 1)
    plain = re.sub("[\u064b-\u0652]", "", first["hadiths"][0]["text"])
    assert first["title"] == "كتاب بدء الوحي" and "إنما الأعمال بالنيات" in plain


def test_tafsirs_bundled():
    eds = {e["id"]: e for e in json.load(open(os.path.join(R, "quran", "editions.json"), encoding="utf-8"))}
    for eid in ("ar.saadi", "ar.ibnkathir", "ar.mukhtasar", "ar.jalalayn", "ar.baghawi", "ar.waseet"):
        assert eid in eds
        d = json.load(open(os.path.join(R, "quran", f"ed_{eid}.json"), encoding="utf-8"))
        assert len(d) == 6236 and sum(1 for x in d if x) > 6000
        for i in range(1, len(d)):
            if len(d[i]) > 80:
                assert d[i] != d[i - 1]          # grouped commentary is not repeated


def test_quran_morphology():
    from abaAcademy import quran_morph as qm
    m = qm.Morphology.get()
    assert len(m.words) == 77429
    w = m.by_ayah[(2, 3)][1]
    text = m.describe_word(w)
    assert "فعل مضارع" in text and "أ م ن" in text
    assert "ورد الجذر ع ل م" in m.root_report("علم")
    q = qm.make_question(m, "root", rng=random.Random(2))
    assert q.answer in q.options and len(set(q.options)) == 4


def test_offline_dictionary():
    from abaAcademy.offline_dict import OfflineDictionary
    d = OfflineDictionary.get()
    assert len(d.ar) > 15000 and len(d.en) > 30000
    assert any("مَدْرَسَة" in x for x in d.lookup("school"))
    assert any("book" in x for x in d.lookup("كتاب"))
    assert d.english_text("school")[0].startswith("(اسم) an educational institution")


def test_sentence_bank():
    from abaAcademy.gui.sentence_bank_view import load, search
    total = 0
    for lang in ("en", "fr", "es", "de", "it", "tr"):
        rows = load(lang)
        assert len(rows) > 10000, lang
        total += len(rows)
        assert all("\t" not in a + b for a, b in rows[:100])
    assert total > 100000
    assert search(load("en"), "school")
    assert search(load("fr"), "مدرسة")


def test_chess_rules():
    from abaAcademy.chess_game import ChessGame
    g = ChessGame()
    assert len(g.legal_moves()) == 20
    for u in ["f2f3", "e7e5", "g2g4", "d8h4"]:
        g.play(g.find(u))
    status, over = g.status()
    assert over and "كِش مات" in status
    g = ChessGame()
    for u in ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"]:
        g.play(g.find(u))
    assert any(m.text == "التبييت القصير" for m in g.legal_moves())
    assert g.find("e1g1") is not None
    mv = g.engine_move()
    assert mv is not None
