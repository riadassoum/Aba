# -*- coding: utf-8 -*-
"""
abaAcademy.engine.session
=========================

The model-side driver for one run of questions. The GUI's exercise window is a
thin view over a ``QuestionSession``: it asks for the next question, submits an
answer, and reads back feedback. All bookkeeping — grading, stats, mistake
logging, spaced-repetition updates, adaptive re-weighting — happens here, so
the same logic is reused by lesson quizzes, mixed multi-lesson sessions, and
endless practice, and is unit-testable without wx.

Adaptivity: after each answer the session can inject extra practice for weak
topics by asking a provider for more questions tagged with the missed topic.
Endless mode simply keeps pulling from the provider until stopped.
"""

from __future__ import annotations

import time
from typing import Callable, List, Optional

from .grading import grade
from .models import AnswerResult, Question, SessionStats


class QuestionSession:
    """Drives an ordered (optionally endless) stream of questions."""

    def __init__(self, questions: List[Question], *,
                 keep_diacritics: bool = False,
                 store=None, course_id: str = "", session_id: Optional[int] = None,
                 refill: Optional[Callable[[str, int], List[Question]]] = None,
                 endless: bool = False):
        self._queue: List[Question] = list(questions)
        self._keep_diacritics = keep_diacritics
        self._store = store
        self._course_id = course_id
        self._session_id = session_id
        self._refill = refill
        self._endless = endless
        self.stats = SessionStats()
        self._current: Optional[Question] = None
        self._shown_at: float = 0.0
        self._history: List[AnswerResult] = []

    # -- iteration ---------------------------------------------------------

    def has_next(self) -> bool:
        if self._queue:
            return True
        if self._endless and self._refill:
            more = self._refill("", 10)
            if more:
                self._queue.extend(more)
                return True
        return False

    def next_question(self) -> Optional[Question]:
        if not self._queue and self._endless and self._refill:
            self._queue.extend(self._refill("", 10) or [])
        if not self._queue:
            self._current = None
            return None
        self._current = self._queue.pop(0)
        self._shown_at = time.time()
        return self._current

    @property
    def current(self) -> Optional[Question]:
        return self._current

    def remaining(self) -> int:
        return len(self._queue)

    # -- answering ---------------------------------------------------------

    def submit(self, given) -> AnswerResult:
        q = self._current
        assert q is not None, "submit() called with no current question"
        elapsed = time.time() - self._shown_at
        correct = grade(q, given, keep_diacritics=self._keep_diacritics)
        result = AnswerResult(question=q, correct=correct, given=given, elapsed=elapsed)
        self._finish(result)
        return result

    def skip(self) -> AnswerResult:
        q = self._current
        assert q is not None
        result = AnswerResult(question=q, correct=False, given=None,
                              elapsed=time.time() - self._shown_at, skipped=True)
        self._finish(result)
        return result

    def _finish(self, result: AnswerResult) -> None:
        self.stats.record(result)
        self._history.append(result)
        q = result.question
        if self._store is not None:
            self._store.log_attempt(
                self._session_id or 0, q.qid, q.topic, self._course_id,
                result.correct, result.skipped, result.elapsed,
            )
            try:
                from ..database import srs
                if not result.skipped:
                    srs.schedule_review(self._store, q.qid, q.topic, self._course_id,
                                        result.correct, result.elapsed)
            except Exception:
                pass
        # Adaptive: on a miss, pull a little extra practice for that topic.
        if (not result.correct and not result.skipped
                and self._refill and q.topic and not self._endless):
            extra = self._refill(q.topic, 1)
            if extra:
                self._queue.extend(extra)
        # Mastery loop: re-ask the *exact* missed item a few questions later, and
        # again if still wrong, up to a small cap — so a mistake is retried and
        # cemented within the same run instead of only being logged. A correct
        # answer clears it; skips don't trigger a re-ask.
        if not result.skipped:
            retried = getattr(q, "_retry_count", 0)
            if not result.correct and retried < 3:
                q._retry_count = retried + 1
                # reinsert a few slots ahead (or at the end if the queue is short)
                pos = min(len(self._queue), 3 + retried)
                self._queue.insert(pos, q)

    def history(self) -> List[AnswerResult]:
        return list(self._history)
