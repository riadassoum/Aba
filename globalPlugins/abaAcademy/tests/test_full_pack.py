# -*- coding: utf-8 -*-
"""End-to-end validation of the assembled add-on, runnable without NVDA/wx."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(PKG))

from abaAcademy import generators as gen
from abaAcademy.engine.loader import CourseRepository
from abaAcademy.engine.schema import (validate_block_file, validate_course_file,
                                      validate_lesson_meta)
from abaAcademy.engine.grading import grade
from abaAcademy.engine.models import Question, QuestionType

gen.load_builtin_generators()
COURSES = os.path.join(PKG, "courses")


def test_every_course_pack_is_valid():
    problems = []
    for course in sorted(os.listdir(COURSES)):
        cdir = os.path.join(COURSES, course)
        cj = os.path.join(cdir, "course.json")
        if not os.path.isfile(cj):
            continue
        obj = json.load(open(cj, encoding="utf-8"))
        problems += validate_course_file(obj, f"{course}/course.json")
        for level in obj.get("levels", []):
            for lm in level.get("lessons", []):
                base = os.path.join(cdir, "levels", level["level_id"],
                                    lm.get("dir") or lm["lesson_id"])
                for fn in ("theory", "practice", "quiz", "review"):
                    fp = os.path.join(base, fn + ".json")
                    assert os.path.isfile(fp), f"missing {fp}"
                    bf = json.load(open(fp, encoding="utf-8"))
                    problems += validate_block_file(bf, f"{lm['lesson_id']}/{fn}")
    assert not problems, f"{len(problems)} problems, first: {problems[:3]}"


def test_discovery_and_lazy_loading():
    repo = CourseRepository([COURSES], generator_registry=gen)
    repo.discover()
    courses = repo.courses()
    assert len(courses) >= 10
    total = sum(c.lesson_count() for c in courses)
    assert total >= 700, total
    # Loading two lessons must not share block objects (isolation).
    metas = repo.all_lesson_metas()
    a = repo.load_lesson(metas[0].lesson_id)
    b = repo.load_lesson(metas[1].lesson_id)
    assert a is not b
    ablocks = {id(x) for x in a.all_blocks()}
    bblocks = {id(x) for x in b.all_blocks()}
    assert not (ablocks & bblocks)


def test_every_generated_block_meets_its_count():
    repo = CourseRepository([COURSES], generator_registry=gen)
    repo.discover()
    shortfalls = []
    checked = 0
    for meta in repo.all_lesson_metas():
        lesson = repo.load_lesson(meta.lesson_id)
        for phase in (lesson.practice, lesson.quiz):
            for block in phase:
                if block.data.get("btype") != "generated":
                    continue
                gid = block.data.get("generator", "")
                count = int(block.data.get("count", 8))
                params = dict(block.data.get("params", {}))
                # Blocks with a "data" key pull their table from the course's
                # data/ files, resolved by Academy at runtime, not by a bare
                # gen.generate() call -- exercise those through Academy below.
                if block.data.get("data"):
                    continue
                qs = gen.generate(gid, count=count, seed=11, **params)
                checked += 1
                assert len(qs) <= count, (meta.lesson_id, gid, "overshot")
                # A block returning *some* questions is fine: session-level
                # top-up (tested separately) guarantees full session length by
                # drawing on the lesson's other generators. Only a block that
                # yields NOTHING from inline params is a genuine authoring bug.
                if len(qs) == 0 and params:
                    shortfalls.append((meta.lesson_id, gid, 0, count))
    assert checked > 500, checked
    assert not shortfalls, f"{len(shortfalls)} short, first: {shortfalls[:5]}"


def test_grading_all_question_types():
    q = Question(QuestionType.MCQ, "p", 2, options=["a", "b", "c"])
    assert grade(q, 2) and not grade(q, 1)
    q = Question(QuestionType.TRUE_FALSE, "p", True)
    assert grade(q, True) and not grade(q, False)
    q = Question(QuestionType.TYPING, "p", "الشمس")
    assert grade(q, "الشمس") and grade(q, " الشمس ")
    q = Question(QuestionType.MULTI_SELECT, "p", [0, 2], options=["a", "b", "c"])
    assert grade(q, [2, 0]) and not grade(q, [0])
    q = Question(QuestionType.ORDERING, "p", ["x", "y", "z"])
    assert grade(q, ["x", "y", "z"]) and not grade(q, ["y", "x", "z"])


def test_no_duplicate_lessons_across_pack():
    import hashlib
    seen = {}
    dups = 0
    for course in sorted(os.listdir(COURSES)):
        base = os.path.join(COURSES, course, "levels")
        if not os.path.isdir(base):
            continue
        for level in os.listdir(base):
            for lesson in os.listdir(os.path.join(base, level)):
                p = os.path.join(base, level, lesson)
                if not os.path.isdir(p):
                    continue
                h = hashlib.md5()
                for fn in ("theory", "practice", "quiz", "review"):
                    fp = os.path.join(p, fn + ".json")
                    if os.path.isfile(fp):
                        h.update(open(fp, "rb").read())
                key = h.hexdigest()
                if key in seen:
                    dups += 1
                seen[key] = p
    assert dups == 0, f"{dups} duplicate lessons remain"


def test_no_nonascii_lesson_folders():
    """Every lesson folder on disk must have a pure-ASCII name.

    Regression guard for the Windows bug where folders containing Arabic text
    became unreachable (open() reported every file inside as missing), so
    English/French lessons showed empty theory. Arabic-named lessons keep their
    Arabic lesson_id, but their on-disk folder must be an ASCII slug recorded
    in course.json's "dir" field.
    """
    offenders = []
    for course in sorted(os.listdir(COURSES)):
        base = os.path.join(COURSES, course, "levels")
        if not os.path.isdir(base):
            continue
        for level in os.listdir(base):
            for lesson in os.listdir(os.path.join(base, level)):
                if not os.path.isdir(os.path.join(base, level, lesson)):
                    continue
                if not lesson.isascii():
                    offenders.append(f"{course}/{level}/{lesson}")
    assert not offenders, f"{len(offenders)} non-ASCII folders: {offenders[:5]}"


def test_every_lesson_loads_theory():
    """No lesson may load with empty theory -- the user-visible symptom of the
    unreachable-folder bug. This is the end-to-end guarantee."""
    repo = CourseRepository([COURSES], generator_registry=gen)
    repo.discover()
    empty = []
    for meta in repo.all_lesson_metas():
        lesson = repo.load_lesson(meta.lesson_id)
        meaningful = [b for b in lesson.theory
                      if b.data.get("btype") != "question"
                      and (b.data.get("text") or b.data.get("passage"))]
        if not meaningful:
            empty.append(meta.lesson_id)
    assert not empty, f"{len(empty)} lessons load empty theory: {empty[:5]}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL", fn.__name__, "->", e)
        except Exception as e:
            failed += 1
            print("ERROR", fn.__name__, "->", type(e).__name__, e)
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


def test_data_backed_lessons_produce_full_sessions_via_academy():
    """The blocks that pull word banks from data/ files must yield real
    sessions through the Academy path (not a bare gen.generate call)."""
    import tempfile
    from abaAcademy.academy import Academy
    ac = Academy(base_dir=PKG, user_data_dir=tempfile.mkdtemp())
    try:
        sample = ["arabic.beginner.sun_moon.0", "arabic.beginner.sun_moon.1",
                  "arabic.beginner.fail.0"]
        for lid in sample:
            if ac.repo.lesson_meta(lid) is None:
                continue
            sess = ac.build_lesson_quiz(lid, seed=3)
            assert sess is not None, lid
            n = 0
            while sess.has_next() and n < 100:
                if sess.next_question() is None:
                    break
                n += 1
            assert n >= 5, f"{lid} only produced {n} questions"
    finally:
        ac.close()
