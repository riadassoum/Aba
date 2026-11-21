# -*- coding: utf-8 -*-
"""Tests for the 4.0 touch-typing course and the liblouis Arabic braille engine."""

import pytest

from abaAcademy import typing_course as tc
from abaAcademy.braille_engine import louis


class FakeStore:
    def __init__(self):
        self.d = {}

    def get_setting(self, k, default=None):
        return self.d.get(k, default)

    def set_setting(self, k, v):
        self.d[k] = v


# -- typing ------------------------------------------------------------------

def test_all_courses_load_with_lessons():
    idx = tc.available()
    ids = {c["id"] for c in idx}
    assert {"ar", "en_us", "fr"} <= ids
    for c in idx:
        course = tc.Course.load(c["id"])
        assert course.lessons, c["id"]
        assert all(l.lines for l in course.lessons)


def test_arabic_home_keys_described_by_touch():
    ar = tc.Course.load("ar")
    d = ar.describe("ب")
    assert "سبابة" in d
    assert "سبابة اليد اليسرى" in d or "سبابة اليد اليمنى" in d
    assert ar.home_position()
    assert ar.lesson_intro(0)


def test_grading_counts_skipped_letter_once():
    r = tc.grade_line("كتب الولد", "كب الولد", 10)
    assert len(r.errors) == 1
    assert r.errors[0][0] == "del"
    perfect = tc.grade_line("abc def", "abc  def", 3)
    assert perfect.accuracy == 100 and perfect.passed
    assert "دون أخطاء" in perfect.feedback()


def test_session_flow_and_progress():
    course = tc.Course.load("en_us")
    s = tc.Session(course, 0, lines=["fff jjj", "fj fj"])
    for line in list(s.lines):
        s.start_line(now=0.0)
        assert s.submit(line, now=5.0).passed
    assert s.finished
    store = FakeStore()
    acc, wpm = s.stats()
    tc.save_lesson_result(store, course.id, 0, acc, wpm)
    tc.save_lesson_result(store, course.id, 0, 50, 1)
    p = tc.load_progress(store, course.id)
    assert p["lessons"]["0"]["accuracy"] == 100 and p["lessons"]["0"]["passed"]


def test_drill_lines_use_only_known_and_new_chars():
    lines = tc.drill_lines("جح", "بتنم", seed=1)
    assert lines
    assert set("".join(lines)) <= set("جحبتنم ")


# -- braille -------------------------------------------------------------------

pytestmark_braille = pytest.mark.skipif(not louis.available(), reason="no tables")

SENTENCES = ["ذهب الولد إلى المدرسة", "كتب المعلم الدرس على السبورة", "هذا كتاب جديد",
             "في البيت شجرة كبيرة", "قال المعلم (اكتبوا الدرس)", "من أين أنت؟"]


@pytestmark_braille
@pytest.mark.parametrize("grade", [1, 2])
@pytest.mark.parametrize("text", SENTENCES)
def test_round_trip(text, grade):
    cells = louis.translate(text, grade)
    assert all(0x2800 <= ord(c) <= 0x28FF or c in " \n" for c in cells)
    assert louis.back_translate(cells, grade) == text


@pytestmark_braille
def test_grade2_is_shorter():
    t = "ذهب الولد إلى المدرسة في الصباح"
    assert len(louis.translate(t, 2)) < len(louis.translate(t, 1))


@pytestmark_braille
def test_dots_and_brf():
    assert louis.cell_dots(louis.dots_to_cells("12")) == "12"
    b = louis.translate("باب", 1)
    assert louis.describe_cells(b)
    brf = louis.to_brf(b)
    assert brf.isascii() and brf.strip()
