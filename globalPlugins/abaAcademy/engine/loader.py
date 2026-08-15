# -*- coding: utf-8 -*-
"""
abaAcademy.engine.loader
========================

Reads course packs from disk into the ``models`` types.

Two responsibilities:

1. **Discovery.** Scan a set of course directories, read each ``course.json``,
   and build the ``Course -> Level -> LessonMeta`` tree *without* touching any
   lesson's teaching blocks. This is cheap and lets the GUI show the whole
   catalogue instantly. Installed content packs (see ``courses/``) are found
   automatically — dropping a new pack folder in is all it takes.

2. **Lazy, isolated lesson loading.** A lesson's theory/practice/review/quiz
   blocks are read only when that lesson is opened, via ``load_lesson``. The
   loader holds no cross-lesson block pool, so opening lesson 20 cannot leak
   state from lesson 19 — each ``Lesson`` object is freshly built and owns its
   blocks. Generated blocks are materialized here by calling into the
   generator registry, but the *questions* they produce are created lazily by
   the player, not cached globally.

The loader never imports course-specific Python. All meaning is in JSON.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .models import (
    Block,
    BlockType,
    Course,
    Lesson,
    LessonMeta,
    Level,
    Question,
    QuestionType,
)


def _read_json(path: str) -> Optional[dict]:
    """Read and parse a JSON file, returning ``None`` on any failure.

    A failure here used to be completely silent, which is exactly what turned a
    single unreadable ``theory.json`` into an empty, unexplained "لا يوجد شرح"
    screen with no way to tell why. Now the reason is written to NVDA's log
    (missing file, permission error, bad encoding, malformed JSON), so a
    problem on one machine can actually be diagnosed rather than guessed at.
    The behaviour -- return ``None`` and carry on -- is unchanged, so a single
    bad file never breaks the whole academy.
    """
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        try:
            from logHandler import log
            log.warning("abaAcademy: file not found: %r", path)
        except Exception:
            pass
        return None
    except (OSError, ValueError) as exc:
        try:
            from logHandler import log
            log.warning("abaAcademy: could not read %s (%s)", path, exc)
        except Exception:
            pass
        return None


def _question_from_json(obj: dict) -> Question:
    qtype = QuestionType(obj["qtype"])
    return Question(
        qtype=qtype,
        prompt=obj.get("prompt", ""),
        correct=obj.get("correct"),
        options=list(obj.get("options", [])),
        accepted=list(obj.get("accepted", [])),
        explanation=obj.get("explanation", ""),
        speak=obj.get("speak", ""),
        topic=obj.get("topic", ""),
        difficulty=int(obj.get("difficulty", 1)),
    )


class CourseRepository:
    """Owns the catalogue tree and knows how to lazily load lesson bodies."""

    def __init__(self, course_dirs: List[str], generator_registry=None):
        self._course_dirs = [d for d in course_dirs if d and os.path.isdir(d)]
        self._generators = generator_registry
        self._courses: Dict[str, Course] = {}
        self._meta_index: Dict[str, LessonMeta] = {}

    # -- discovery ---------------------------------------------------------

    def discover(self) -> None:
        """(Re)build the course catalogue from every installed pack."""
        self._courses.clear()
        self._meta_index.clear()
        for root in self._course_dirs:
            for entry in sorted(os.listdir(root)):
                course_path = os.path.join(root, entry)
                manifest = os.path.join(course_path, "course.json")
                if os.path.isfile(manifest):
                    self._load_course_manifest(manifest, course_path)

    def _load_course_manifest(self, manifest: str, course_path: str) -> None:
        obj = _read_json(manifest)
        if not obj or not obj.get("course_id"):
            return
        course = Course(
            course_id=obj["course_id"],
            title=obj.get("title", obj["course_id"]),
            description=obj.get("description", ""),
            order=int(obj.get("order", 0)),
            version=obj.get("version", "1.0.0"),
            path=course_path,
        )
        for lv in obj.get("levels", []):
            level = Level(
                level_id=lv["level_id"],
                title=lv.get("title", lv["level_id"]),
                course_id=course.course_id,
                order=int(lv.get("order", 0)),
            )
            for lm in lv.get("lessons", []):
                # A lesson's on-disk folder name is taken from its optional
                # "dir" field, falling back to the lesson_id. This split exists
                # because Windows cannot reliably open paths whose components
                # contain Arabic text (the folder is created by the add-on
                # installer, and on some systems those non-ASCII directory
                # names become unreachable -- every file inside reads as "not
                # found"). Lesson ids stay Arabic-friendly and human-meaningful
                # for progress tracking and cross-references; the *folder* is a
                # pure-ASCII slug. Lessons whose id is already ASCII need no
                # "dir" and are unaffected.
                folder = lm.get("dir") or lm["lesson_id"]
                lesson_dir = self._resolve_dir(
                    os.path.join(course_path, "levels", level.level_id),
                    folder)
                meta = LessonMeta(
                    lesson_id=lm["lesson_id"],
                    title=lm.get("title", lm["lesson_id"]),
                    course_id=course.course_id,
                    level_id=level.level_id,
                    order=int(lm.get("order", 0)),
                    objectives=list(lm.get("objectives", [])),
                    grammar_refs=list(lm.get("grammar_refs", [])),
                    prerequisites=list(lm.get("prerequisites", [])),
                    difficulty=int(lm.get("difficulty", 1)),
                    path=lesson_dir,
                )
                level.lesson_metas.append(meta)
                self._meta_index[meta.lesson_id] = meta
            level.lesson_metas.sort(key=lambda m: m.order)
            course.levels.append(level)
        course.levels.sort(key=lambda l: l.order)
        self._courses[course.course_id] = course

    @staticmethod
    def _resolve_dir(parent: str, name: str) -> str:
        """Return the real on-disk directory for ``name`` inside ``parent``.

        Same problem, one level up, as ``_resolve`` for files: a lesson folder
        named from an Arabic lesson id may be stored on disk in a different
        Unicode normal form (NFC vs NFD) than the id string we hold in memory.
        Building the path by naive join then points at a directory that
        ``open()`` can't find, so every file in the lesson -- theory included --
        loads empty. Resolving the directory once here, against what the
        filesystem actually contains, fixes it for the whole lesson at the
        source. ASCII names are returned unchanged with a single ``isdir``
        check; the ``listdir`` scan runs only on a miss.
        """
        direct = os.path.join(parent, name)
        if os.path.isdir(direct):
            return direct
        try:
            import unicodedata
            want = unicodedata.normalize("NFC", name).casefold()
            for entry in os.listdir(parent):
                if unicodedata.normalize("NFC", entry).casefold() == want:
                    return os.path.join(parent, entry)
        except (OSError, ValueError):
            pass
        return direct

    # -- catalogue access --------------------------------------------------

    def courses(self) -> List[Course]:
        return sorted(self._courses.values(), key=lambda c: c.order)

    def course(self, course_id: str) -> Optional[Course]:
        return self._courses.get(course_id)

    def lesson_meta(self, lesson_id: str) -> Optional[LessonMeta]:
        return self._meta_index.get(lesson_id)

    def all_lesson_metas(self) -> List[LessonMeta]:
        return list(self._meta_index.values())

    # -- lazy lesson body loading (isolated per call) ----------------------

    def _load_blocks(self, lesson_path: str, filename: str) -> List[Block]:
        obj = _read_json(self._resolve(lesson_path, filename))
        if not obj:
            return []
        blocks: List[Block] = []
        for raw in obj.get("blocks", []):
            try:
                btype = BlockType(raw["btype"])
            except (KeyError, ValueError):
                continue
            block = Block(btype=btype, data=raw)
            if btype is BlockType.QUESTION and isinstance(raw.get("question"), dict):
                block.questions = [_question_from_json(raw["question"])]
            elif btype is BlockType.EXAM and isinstance(raw.get("questions"), list):
                block.questions = [_question_from_json(q) for q in raw["questions"]]
            blocks.append(block)
        return blocks

    @staticmethod
    def _resolve(lesson_path: str, filename: str) -> str:
        """Return a path to ``filename`` inside ``lesson_path`` that actually
        opens, even when Unicode normalization differs between the stored
        path and the real directory entry.

        This is the fix for the "empty theory" report on Windows with Arabic
        folder names. The lesson folder is named from the lesson id (which
        contains Arabic), and the id string carried in memory can be in a
        different Unicode normal form (NFC vs NFD) than the bytes the
        filesystem stored. ``open()`` then raises FileNotFoundError for a file
        that plainly exists, and the lesson loads with no theory -- while other
        files that happen to match, or are reached another way, load fine.

        We first try the obvious join. If that file isn't there, we list the
        directory and match ``filename`` by normalized comparison, returning
        the real on-disk name. Pure ASCII filenames like ``theory.json`` are
        unaffected; the cost is one ``listdir`` only when the direct path
        misses, which is never in the common case.
        """
        direct = os.path.join(lesson_path, filename)
        if os.path.isfile(direct):
            return direct
        try:
            import unicodedata
            want = unicodedata.normalize("NFC", filename).casefold()
            for entry in os.listdir(lesson_path):
                if unicodedata.normalize("NFC", entry).casefold() == want:
                    return os.path.join(lesson_path, entry)
        except (OSError, ValueError):
            pass
        return direct  # let the caller's read fail and log, as before

    def load_lesson(self, lesson_id: str) -> Optional[Lesson]:
        """Read one lesson's full body. Returns a fresh, self-contained object.

        No block or question produced here is shared with any other lesson --
        this is the mechanism behind 'loading lesson 20 unloads lesson 19'.
        """
        meta = self._meta_index.get(lesson_id)
        if not meta:
            return None
        theory = self._load_blocks(meta.path, "theory.json")
        practice = self._load_blocks(meta.path, "practice.json")
        review = self._load_blocks(meta.path, "review.json")
        quiz = self._load_blocks(meta.path, "quiz.json")
        # Diagnostic: if theory came back empty but the sibling files did not,
        # the theory file specifically failed to read on this machine. Record
        # exactly what the directory actually contains so the cause (a missing
        # file after extraction, a permissions quirk, a name mismatch) is
        # visible in the NVDA log rather than left to guesswork.
        if not theory and (practice or quiz):
            try:
                from logHandler import log
                try:
                    listing = os.listdir(meta.path)
                except OSError as exc:
                    listing = ["<listdir failed: %s>" % exc]
                log.warning(
                    "abaAcademy: %r has empty theory but non-empty exercises. "
                    "path=%r contents=%r", lesson_id, meta.path, listing)
            except Exception:
                pass
        return Lesson(
            meta=meta, theory=theory, practice=practice,
            review=review, quiz=quiz,
        )
