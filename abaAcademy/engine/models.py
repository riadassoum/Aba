# -*- coding: utf-8 -*-
"""
abaAcademy.engine.models
========================

Core data structures for the ABA Academy platform.

These dataclasses are the shared vocabulary that every subsystem speaks:
the lesson engine, the GUI, the generators, and the database layer all
exchange instances of these types. They are deliberately *content-neutral*:
nothing here knows what Arabic grammar is, what a "hamza" is, or how French
verbs conjugate. A block is a block; a question is a question. All meaning
lives in JSON course packs and in pluggable generators.

Design notes
------------
* Everything is a ``@dataclass`` with type hints, so the shapes are
  self-documenting and cheap to construct in tests.
* ``BlockType`` and ``QuestionType`` are the two extension points the lesson
  player switches on. Adding a new interaction means adding an enum member
  and a renderer in the GUI + (optionally) a loader in the engine — never
  touching course content.
* ``Question`` is the single currency the GUI's exercise runner consumes,
  regardless of whether it came from a static JSON block or a procedural
  generator. This is what lets "one generator produce thousands of
  questions" flow through the same accessible UI as hand-written items.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class BlockType(enum.Enum):
    """The kinds of teaching blocks a lesson player can execute in order."""

    TEXT = "text"                 # a short spoken explanation
    DIALOGUE = "dialogue"         # a back-and-forth exchange, spoken line by line
    EXAMPLE = "example"           # a worked example with optional translation
    QUESTION = "question"         # a single embedded question (any QuestionType)
    TYPING = "typing"             # learner types an exact answer
    MATCHING = "matching"         # match items from column A to column B
    SORTING = "sorting"           # put shuffled items into the correct order
    LISTENING = "listening"       # spoken prompt, then a question about it
    READING = "reading"           # a passage, then comprehension questions
    FILL_BLANK = "fill_blank"     # complete the blank in a sentence
    SENTENCE_BUILD = "sentence_build"  # assemble a sentence from parts
    MINI_GAME = "mini_game"       # a small timed / gamified drill
    REVIEW = "review"             # revisit earlier items (may pull from SRS)
    EXAM = "exam"                 # a scored block of mixed questions
    GENERATED = "generated"       # delegate to a procedural generator by id


class QuestionType(enum.Enum):
    """The concrete answerable forms the exercise runner knows how to grade."""

    MCQ = "mcq"                   # choose one option
    MULTI_SELECT = "multi_select"  # choose all that apply
    TRUE_FALSE = "true_false"     # boolean
    TYPING = "typing"             # free-text exact / normalized match
    MATCHING = "matching"         # pair A-items with B-items
    ORDERING = "ordering"         # arrange items into a sequence


@dataclass
class Question:
    """A single answerable item, whatever its origin (static or generated).

    ``correct`` is interpreted per ``qtype``:
      * MCQ           -> index (int) into ``options``
      * MULTI_SELECT  -> list[int] of indices into ``options``
      * TRUE_FALSE    -> bool
      * TYPING        -> str (compared after normalization); ``accepted`` may
                         hold additional acceptable strings
      * MATCHING      -> dict mapping left-item -> right-item
      * ORDERING      -> list giving the correct order of ``options``
    """

    qtype: QuestionType
    prompt: str
    correct: Any
    options: List[str] = field(default_factory=list)
    accepted: List[str] = field(default_factory=list)
    explanation: str = ""
    # For dictation/listening: text to SPEAK that differs from the visible
    # prompt. When set, the exercise runner voices this (so the learner types
    # what they hear) while the on-screen prompt stays a neutral instruction.
    speak: str = ""
    # Free-form provenance so statistics can attribute mistakes to a topic
    # ("kana_akhawatuha", "vocab:food", "generator:plural") without the engine
    # knowing what those strings mean.
    topic: str = ""
    difficulty: int = 1
    # An optional graded hint the learner can request before answering. When
    # empty, the exercise runner derives a sensible fallback hint from the
    # answer itself (a category nudge, then the first letter, then length).
    hint: str = ""
    # Stable identity so spaced-repetition and mistake logs can reference an
    # item across sessions. Generated questions get a deterministic id from
    # their generator + seed so the *concept* is tracked even though the exact
    # wording changes.
    qid: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def normalized_options(self) -> List[str]:
        return list(self.options)


@dataclass
class Block:
    """One teaching step in a lesson. The player executes blocks in order."""

    btype: BlockType
    # Raw payload straight from JSON (or synthesized for generated blocks).
    # The GUI renderer for each BlockType knows how to read this.
    data: Dict[str, Any] = field(default_factory=dict)
    # Present only for BlockType.QUESTION / EXAM etc. once materialized.
    questions: List[Question] = field(default_factory=list)
    block_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class LessonMeta:
    """Everything about a lesson *except* its teaching blocks."""

    lesson_id: str
    title: str
    course_id: str
    level_id: str
    order: int = 0
    objectives: List[str] = field(default_factory=list)
    grammar_refs: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    difficulty: int = 1
    # Where on disk this lesson's pack lives, so the loader can lazy-read
    # theory/practice/quiz files only when the lesson is actually opened
    # (this is what enforces lesson isolation — see engine.loader).
    path: str = ""


@dataclass
class Lesson:
    """A fully materialized lesson: metadata + ordered blocks by phase."""

    meta: LessonMeta
    theory: List[Block] = field(default_factory=list)
    practice: List[Block] = field(default_factory=list)
    review: List[Block] = field(default_factory=list)
    quiz: List[Block] = field(default_factory=list)

    def all_blocks(self) -> List[Block]:
        return self.theory + self.practice + self.review + self.quiz


@dataclass
class Level:
    level_id: str
    title: str
    course_id: str
    order: int = 0
    lesson_metas: List[LessonMeta] = field(default_factory=list)


@dataclass
class Course:
    course_id: str
    title: str
    description: str = ""
    order: int = 0
    version: str = "1.0.0"
    levels: List[Level] = field(default_factory=list)
    path: str = ""

    def lesson_count(self) -> int:
        return sum(len(lv.lesson_metas) for lv in self.levels)


@dataclass
class AnswerResult:
    """Outcome of grading one answer — the unit statistics are built from."""

    question: Question
    correct: bool
    given: Any
    elapsed: float = 0.0
    skipped: bool = False


@dataclass
class SessionStats:
    """Live tally for one exercise/lesson session."""

    total: int = 0
    correct: int = 0
    wrong: int = 0
    skipped: int = 0
    started_at: float = field(default_factory=time.time)
    per_topic: Dict[str, Dict[str, int]] = field(default_factory=dict)
    response_times: List[float] = field(default_factory=list)

    def record(self, result: AnswerResult) -> None:
        self.total += 1
        if result.skipped:
            self.skipped += 1
        elif result.correct:
            self.correct += 1
        else:
            self.wrong += 1
        if result.elapsed:
            self.response_times.append(result.elapsed)
        topic = result.question.topic or "عام"
        bucket = self.per_topic.setdefault(topic, {"correct": 0, "wrong": 0})
        if not result.skipped:
            bucket["correct" if result.correct else "wrong"] += 1

    @property
    def accuracy(self) -> float:
        answered = self.correct + self.wrong
        return (self.correct / answered * 100.0) if answered else 0.0

    @property
    def avg_response_time(self) -> float:
        return (sum(self.response_times) / len(self.response_times)
                if self.response_times else 0.0)


# A generator is any callable that yields Question objects on demand. The
# registry (generators/__init__.py) maps a string id -> GeneratorFn so JSON
# lessons can say {"btype": "generated", "generator": "ar.plural", "count": 8}
# without importing anything.
GeneratorFn = Callable[..., Question]
