# -*- coding: utf-8 -*-
"""
abaAcademy.braille_engine.braille_lessons
=========================================

A progressive curriculum for Arabic Grade-2 braille contractions. Contractions
are taught a few at a time; each lesson introduces new signs and then drills them
on real dictionary words that contain the contractions taught *so far* (via
:mod:`braille_challenges`). This enforces the teaching rule that a learner is
only ever challenged on contractions they've reached.

Progress (which lessons are done) is stored through the academy store, so the
"known contractions" set grows as the learner advances.
"""

from __future__ import annotations

from .arabic_braille import GRADE2_WORDSIGNS


def _build_lessons():
    """Build the full lesson ladder covering EVERY contraction in the table.

    The first lessons are hand-ordered because those signs are the most common
    and make the best introduction. Everything else is then grouped
    automatically, four signs per lesson, in a stable order (by cell count then
    alphabetically) so lesson ids never shift between runs. This way the ladder
    covers all 200+ contractions without anyone having to curate hundreds of
    entries by hand.
    """
    curated = [
        ("الاختصارات الأساسية (1)", ["من", "في", "ال"]),
        ("الاختصارات الأساسية (2)", ["على", "إلى", "قد"]),
        ("أدوات الربط", ["أو", "بل", "ثم", "كل"]),
        ("الأسماء الموصولة", ["الذي", "التي"]),
        ("الإشارة والحروف", ["هذا", "ذلك", "حتى", "حيث"]),
    ]
    used = {s for _t, signs in curated for s in signs if s in GRADE2_WORDSIGNS}
    curated = [(t, [s for s in signs if s in GRADE2_WORDSIGNS]) for t, signs in curated]

    # everything not curated, in a stable order
    rest = sorted((s for s in GRADE2_WORDSIGNS if s not in used),
                  key=lambda w: (len(GRADE2_WORDSIGNS[w]), len(w), w))

    lessons = []
    for i, (title, signs) in enumerate(curated, start=1):
        lessons.append((f"bl{i}", title, signs))
    n = len(curated)
    for j in range(0, len(rest), 4):
        batch = rest[j:j + 4]
        idx = n + (j // 4) + 1
        lessons.append((f"bl{idx}", f"اختصارات إضافية ({j // 4 + 1})", batch))
    return lessons


LESSONS = _build_lessons()


def all_lessons():
    return LESSONS


def get_lesson(lid):
    for l in LESSONS:
        if l[0] == lid:
            return l
    return None


def contractions_up_to(lesson_id):
    """The set of contractions taught in this lesson and all earlier ones —
    i.e. everything the learner knows once they reach this lesson."""
    known = []
    for lid, _title, signs in LESSONS:
        known.extend(signs)
        if lid == lesson_id:
            break
    return [c for c in known if c in GRADE2_WORDSIGNS]


def known_from_progress(store):
    """Read the learner's completed braille lessons from the store and return
    the union of contractions they've learned. A lesson counts as known once
    started (so its signs are available in challenges) — completion is tracked
    separately for progress."""
    known = []
    for lid, _title, signs in LESSONS:
        try:
            flag = store.get_setting(f"braille_lesson_{lid}", "")
        except Exception:
            flag = ""
        if flag in ("started", "done"):
            known.extend(signs)
    return [c for c in known if c in GRADE2_WORDSIGNS]


def mark_started(store, lesson_id):
    try:
        cur = store.get_setting(f"braille_lesson_{lesson_id}", "")
        if cur != "done":
            store.set_setting(f"braille_lesson_{lesson_id}", "started")
    except Exception:
        pass


def mark_done(store, lesson_id):
    try:
        store.set_setting(f"braille_lesson_{lesson_id}", "done")
    except Exception:
        pass


def lesson_status(store, lesson_id):
    try:
        return store.get_setting(f"braille_lesson_{lesson_id}", "") or "new"
    except Exception:
        return "new"
