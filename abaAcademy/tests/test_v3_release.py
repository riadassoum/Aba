# -*- coding: utf-8 -*-
"""Release-readiness checks for 3.0: no typographic quotes anywhere the
academy speaks from, display preferences, the learner overview, placement
tests, the main-screen catalogue, and the release zip produced by build.py."""
import gzip
import importlib.util
import json
import os
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
sys.path.insert(0, ROOT)

from abaAcademy.speakable import speakable, has_quote_marks
from abaAcademy.display_prefs import DisplayPrefs, THEMES, FONT_SCALES, contrast_ratio


class _Store:
    def __init__(self):
        self.d = {}

    def get_setting(self, k, default=""):
        return self.d.get(k, default)

    def set_setting(self, k, v):
        self.d[k] = v


def _academy():
    from abaDesktop.core import build_academy
    return build_academy(tempfile.mkdtemp())


# -- quotation marks --------------------------------------------------------

def test_no_guillemets_in_shipped_text():
    found = []
    for base in (PKG, os.path.join(ROOT, "abaDesktop")):
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "vendor", "tests")]
            for f in files:
                if f == "speakable.py":          # the filter that removes them
                    continue
                p = os.path.join(root, f)
                ext = os.path.splitext(f)[1]
                try:
                    if ext == ".gz":
                        data = gzip.open(p).read().decode("utf-8", "ignore")
                    elif ext in (".py", ".json", ".txt", ".md", ".html"):
                        data = open(p, encoding="utf-8").read()
                    else:
                        continue
                except Exception:
                    continue
                if "«" in data or "»" in data:
                    found.append(os.path.relpath(p, ROOT))
    assert not found, found[:10]


def test_speakable_removes_quote_marks():
    assert speakable("في «المغرب»: هل القارة «أوروبا وآسيا»؟") == "في المغرب: هل القارة أوروبا وآسيا؟"
    assert speakable("“quoted”  text") == "quoted text"
    assert speakable("") == "" and speakable(None) == ""
    assert has_quote_marks("«x»") and not has_quote_marks("x")


def test_speaker_filters_everything_it_speaks():
    from abaDesktop.tts import Speaker
    spoken = []

    class B:
        name = "test"

        def speak(self, t):
            spoken.append(t)

        def stop(self):
            pass

    sp = Speaker.__new__(Speaker)
    sp.log, sp.enabled = [], False
    sp.speak("قال «مرحبًا»")
    assert sp.log == ["قال مرحبًا"]


# -- display preferences ------------------------------------------------------

def test_display_prefs_round_trip_and_normalise():
    st = _Store()
    assert DisplayPrefs.load(st) == DisplayPrefs()
    DisplayPrefs(font_scale=170, theme="yellow_on_black", bold=True, focus_highlight=False).save(st)
    p = DisplayPrefs.load(st)
    assert p.font_scale == 175 and p.theme == "yellow_on_black" and p.bold and not p.focus_highlight
    st.d["display_theme"] = "nonsense"
    st.d["display_font_scale"] = "abc"
    p = DisplayPrefs.load(st)
    assert p.theme == "system" and p.font_scale == 100
    assert DisplayPrefs(font_scale=200).scaled(10) == 20 and DisplayPrefs().scaled(0) == 10
    assert "١٧٥" in DisplayPrefs(175).describe() or "175" in DisplayPrefs(175).describe()


def test_themes_have_readable_contrast():
    for key, (label, bg, fg, fbg, ffg) in THEMES.items():
        assert label
        if bg and fg:
            assert contrast_ratio(bg, fg) >= 7.0, key            # WCAG AAA for text
        assert contrast_ratio(fbg, ffg) >= 4.5, key               # focus highlight
    assert FONT_SCALES[0] == 100 and max(FONT_SCALES) >= 200


# -- catalogue ----------------------------------------------------------------

def test_catalog_is_organised():
    from abaAcademy.gui.hub_catalog import CATALOG, all_features, course_ids
    titles = [t.title for t in CATALOG]
    assert len(titles) == len(set(titles)) and len(titles) >= 12
    for tab in CATALOG:
        assert 2 <= len(tab.features) <= 12, tab.title
    labels = [f.label for f in all_features()]
    assert len(labels) == len(set(labels))
    assert {"spanish", "turkish", "german", "italian", "english_graded", "french_graded"} <= set(course_ids())
    assert any(f.handler == "_open_display" for f in all_features())
    assert any(f.handler == "_open_overview" for f in all_features())
    assert any(f.handler == "_open_placement" for f in all_features())


# -- overview -------------------------------------------------------------------

def test_overview_for_new_and_active_learner():
    from abaAcademy.study_hub import overview
    ac = _academy()
    try:
        secs = dict(overview.sections(ac))
        assert "اليوم" in secs and "الدورات" in secs and "الخطوة التالية المقترحة" in secs
        assert any("لم يبدأ" in l for l in secs["الدورات"])
        lid = "spanish.g001"
        ac.store.record_lesson_result(lid, "spanish", 90, True) if hasattr(ac.store, "record_lesson_result") else None
        page = overview.to_html(ac, "سارة")
        assert page.startswith("<!doctype html>") and 'dir="rtl"' in page and "سارة" in page
        assert "«" not in page
        assert overview.text(ac)
    finally:
        ac.close()


# -- placement --------------------------------------------------------------------

def _run(ac, cid, knows):
    from abaAcademy.engine.placement import Placement
    p = Placement(ac, cid, seed=4)
    while not p.finished:
        q = p.next_question()
        if q is None:
            break
        p.answer(q.correct if knows(p) else (q.correct + 1) % len(q.options))
    return p


def test_placement_results():
    from abaAcademy.engine.placement import saved_level, stages_of
    ac = _academy()
    try:
        n = len(stages_of(ac.course("german")))
        p = _run(ac, "german", lambda p: False)
        assert p.result().stage_index == 0 and p.asked <= 3
        p = _run(ac, "german", lambda p: True)
        assert p.result().stage_index == n - 1 and p.asked <= 3 * (n // 2 + 2)
        p = _run(ac, "german", lambda p: p.stage_index < 6)
        r = p.save()
        # stages 0, 2 and 4 pass, 6 fails: placed at the first untested stage after 4
        assert r.stage_index == 5
        assert saved_level(ac.store, "german") == r.level_id
        assert "ابدأ" in r.summary()
        import pytest
        with pytest.raises(ValueError):
            from abaAcademy.engine.placement import Placement
            Placement(ac, "english")          # the original course has no graded stages
    finally:
        ac.close()


# -- release zip --------------------------------------------------------------------

def _build_module():
    spec = importlib.util.spec_from_file_location("aba_build", os.path.join(ROOT, "build.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_release_zip_checker():
    b = _build_module()
    assert b.app_version() == "3.0"
    d = tempfile.mkdtemp()
    good = os.path.join(d, "good.zip")
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("App/run_app.py", "")
        z.writestr("App/اقرأني.txt", "x")
        z.writestr("App/abaAcademy/academy.pyc", b"")
        z.writestr("App/userdata/", "")
    assert b.check_release_zip(good, require=("run_app.py", "اقرأني.txt")) == []
    bad = os.path.join(d, "bad.zip")
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("App/abaAcademy/academy.py", "")
        z.writestr("App/abaAcademy/tests/test_x.pyc", b"")
        z.writestr("App/userdata/aba_academy.db", b"")
    problems = b.check_release_zip(bad, require=("run_app.py",))
    assert any("source file" in p for p in problems)
    assert any("should not ship" in p for p in problems)
    assert any("learner data" in p for p in problems)
    assert any("missing" in p for p in problems)
