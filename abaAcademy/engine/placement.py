# -*- coding: utf-8 -*-
"""
abaAcademy.engine.placement
===========================

Placement test for the graded language courses: someone who already knows
some Spanish should not start at lesson one.

The test climbs the course's stages in steps of ``stride`` (every second
stage by default, so a course of 25 stages takes at most about 40
questions). At each tested stage it asks ``per_stage`` multiple-choice
questions drawn from that stage's exam (real sentences of that stage's
vocabulary). With ``pass_mark`` or more right, it moves up; otherwise it
stops, and the learner is placed at the first stage after the last one they
passed. Passing every tested stage places them at the last stage.

The result is stored as a setting (``placement_<course_id>``) that the course
browser reads to open at the right stage. No lesson is marked complete, so the
learner's statistics stay honest.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from .models import Question, QuestionType

SETTING = "placement_{}"


@dataclass
class Stage:
    level_id: str
    title: str
    exam_lesson: str


@dataclass
class PlacementResult:
    stage_index: int
    level_id: str
    title: str
    asked: int
    correct: int
    passed_stages: int
    total_stages: int

    def summary(self) -> str:
        if self.passed_stages == 0:
            return (f"ابدأ من أوّل الدورة: {self.title}. أجبت عن {self.correct} من {self.asked} "
                    f"إجابة صحيحة.")
        if self.passed_stages >= self.total_stages:
            return (f"اجتزت كل المراحل ({self.total_stages}). ابدأ من آخر مرحلة للمراجعة، "
                    f"ثم انتقل إلى القراءة المتقدّمة: {self.title}.")
        return (f"اجتزت {self.passed_stages} من {self.total_stages} مراحل. ابدأ من: {self.title}. "
                f"أجبت عن {self.correct} من {self.asked} إجابة صحيحة.")


def stages_of(course) -> List[Stage]:
    out = []
    for lv in course.levels:
        if not lv.level_id.startswith("stage"):
            continue
        exam = next((m.lesson_id for m in lv.lesson_metas if m.lesson_id.rsplit(".", 1)[-1].startswith("exam")), None)
        if exam:
            out.append(Stage(lv.level_id, lv.title, exam))
    return out


def has_placement(course) -> bool:
    return len(stages_of(course)) >= 2


@dataclass
class Placement:
    academy: object
    course_id: str
    per_stage: int = 3
    pass_mark: int = 2
    stride: int = 2
    seed: Optional[int] = None
    stages: List[Stage] = field(default_factory=list)
    stage_index: int = 0
    _queue: List[Question] = field(default_factory=list)
    _stage_right: int = 0
    _stage_asked: int = 0
    asked: int = 0
    correct: int = 0
    passed_stages: int = 0
    finished: bool = False
    current: Optional[Question] = None

    def __post_init__(self):
        course = self.academy.course(self.course_id)
        if course is None:
            raise ValueError("لا توجد هذه الدورة.")
        self.stages = stages_of(course)
        if len(self.stages) < 2:
            raise ValueError("لا يوجد اختبار تحديد مستوى لهذه الدورة.")
        self._rng = random.Random(self.seed)
        n = len(self.stages)
        self.ladder = sorted(set(list(range(0, n, max(1, self.stride))) + [n - 1]))
        self._rung = 0
        self.stage_index = self.ladder[0]
        self._last_passed = -1
        self._place_at = 0
        self._load_stage()

    # -- question flow -----------------------------------------------------

    def _load_stage(self) -> None:
        st = self.stages[self.stage_index]
        qs: List[Question] = []
        for attempt in range(3):
            try:
                sess = self.academy.build_lesson_quiz(st.exam_lesson, seed=self._rng.randint(0, 1 << 30))
            except Exception:
                sess = None
            while sess is not None and sess.has_next():
                q = sess.next_question()
                if q is None:
                    break
                if q.qtype == QuestionType.MCQ and q.options and len(q.options) >= 3:
                    qs.append(q)
            if len(qs) >= self.per_stage:
                break
        self._rng.shuffle(qs)
        self._queue = qs[: self.per_stage]
        self._stage_right = self._stage_asked = 0
        if not self._queue:
            # an exam that yields no multiple-choice questions cannot be judged:
            # treat it as passed rather than trapping the learner
            self._advance(passed=True)

    def next_question(self) -> Optional[Question]:
        if self.finished:
            return None
        if not self._queue:
            return None
        self.current = self._queue.pop(0)
        return self.current

    def answer(self, option_index: int) -> bool:
        if self.current is None or self.finished:
            raise RuntimeError("لا يوجد سؤال حالي.")
        ok = option_index == self.current.correct
        self.asked += 1
        self._stage_asked += 1
        if ok:
            self.correct += 1
            self._stage_right += 1
        self.current = None
        remaining = len(self._queue)
        needed = self.pass_mark - self._stage_right
        if self._stage_right >= self.pass_mark:
            self._advance(passed=True)
        elif needed > remaining:
            self._advance(passed=False)
        return ok

    def _advance(self, passed: bool) -> None:
        if passed:
            self._last_passed = self.stage_index
            self.passed_stages = self.stage_index + 1
            if self._rung + 1 < len(self.ladder):
                self._rung += 1
                self.stage_index = self.ladder[self._rung]
                self._load_stage()
                return
            self._place_at = len(self.stages) - 1
        else:
            self._place_at = self._last_passed + 1
        self.finished = True
        self._queue = []

    @property
    def stage(self) -> Stage:
        return self.stages[self.stage_index]

    def progress_text(self) -> str:
        return (f"اختبار المرحلة {self.stage_index + 1} من {len(self.stages)}، "
                f"السؤال {self._stage_asked + 1} من {self.per_stage}.")

    # -- result ----------------------------------------------------------

    def result(self) -> PlacementResult:
        idx = min(self._place_at if self.finished else self.stage_index, len(self.stages) - 1)
        st = self.stages[idx]
        return PlacementResult(idx, st.level_id, st.title, self.asked, self.correct,
                               self.passed_stages, len(self.stages))

    def save(self) -> PlacementResult:
        r = self.result()
        try:
            self.academy.store.set_setting(SETTING.format(self.course_id), r.level_id)
        except Exception:
            pass
        return r


def saved_level(store, course_id: str) -> str:
    try:
        return store.get_setting(SETTING.format(course_id), "") or ""
    except Exception:
        return ""
