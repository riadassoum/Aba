# -*- coding: utf-8 -*-
"""
abaAcademy.database.srs
=======================

Spaced-repetition scheduling, an SM-2 variant adapted to a binary
correct/incorrect signal (we don't ask the learner to self-rate; we infer a
grade from correctness and response speed).

Concepts are tracked by ``qid`` (which, for generated questions, is stable per
*concept* even as wording varies — see the generators layer). After each
review:

* A correct, quick answer raises the interval and ease (concept fading out).
* A correct but slow answer advances more gently.
* A wrong answer resets repetitions and makes the concept return soon.

``due_concepts`` returns what the adaptive/review blocks should resurface. This
is what makes "forgotten concepts return more frequently, mastered concepts
appear less often" concrete.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

_DAY = 86400.0
MIN_EASE = 1.3


# --- FSRS-6 style scheduler (adapted from the open-source FSRS algorithm;
# see COPYING) -------------------------------------------------------------
# Default FSRS-6 weights (w0..w20).
_W = (0.2172, 1.1771, 3.2602, 16.1507, 7.0114, 0.57, 2.0966, 0.0069, 1.5261,
      0.112, 1.0178, 1.849, 0.1133, 0.3127, 2.2934, 0.2191, 3.0004, 0.7536,
      0.3332, 0.1437, 0.2)
_DECAY = -0.5
_FACTOR = 0.9 ** (1.0 / _DECAY) - 1.0
TARGET_RETENTION = 0.9


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _grade_from(correct: bool, elapsed: float) -> int:
    """Map (correct, elapsed) to an FSRS rating: 1=Again, 2=Hard, 3=Good, 4=Easy."""
    if not correct:
        return 1
    if elapsed <= 4.0:
        return 4
    if elapsed <= 9.0:
        return 3
    return 2


def _init_stability(g):
    return max(0.1, _W[g - 1])


def _init_difficulty(g):
    return _clamp(_W[4] - __import__("math").exp(_W[5] * (g - 1)) + 1.0, 1.0, 10.0)


def _next_interval(stability):
    import math
    ivl = (stability / _FACTOR) * ((TARGET_RETENTION ** (1.0 / _DECAY)) - 1.0)
    return _clamp(round(ivl), 1, 3650) if ivl >= 1 else max(0.02, ivl)


def _retrievability(elapsed_days, stability):
    if stability <= 0:
        return 0.0
    return (1.0 + _FACTOR * elapsed_days / stability) ** _DECAY


def _next_difficulty(d, g):
    dd = d - _W[6] * (g - 3)
    # mean reversion toward the "easy" difficulty
    d0_4 = _clamp(_W[4] - __import__("math").exp(_W[5] * (4 - 1)) + 1.0, 1.0, 10.0)
    dd = _W[7] * d0_4 + (1 - _W[7]) * dd
    return _clamp(dd, 1.0, 10.0)


def _next_stability(d, s, r, g):
    import math
    if g == 1:  # forgot -> post-lapse stability
        s_forget = (_W[11] * (d ** -_W[12]) * (((s + 1) ** _W[13]) - 1.0)
                    * math.exp(_W[14] * (1.0 - r)))
        return max(0.1, min(s_forget, s))
    # recalled -> stability increase
    hard_penalty = _W[15] if g == 2 else 1.0
    easy_bonus = _W[16] if g == 4 else 1.0
    s_rec = s * (1.0 + math.exp(_W[8]) * (11.0 - d) * (s ** -_W[9])
                 * (math.exp(_W[10] * (1.0 - r)) - 1.0) * hard_penalty * easy_bonus)
    return max(0.1, s_rec)


def schedule_review(store, qid: str, topic: str, course_id: str,
                    correct: bool, elapsed: float, now: float = None) -> None:
    now = now if now is not None else time.time()
    g = _grade_from(correct, elapsed)
    prev = store.srs_get(qid)
    if not prev or prev.get("repetitions", 0) == 0:
        stability = _init_stability(g)
        difficulty = _init_difficulty(g)
        reps = 1
    else:
        difficulty = prev["ease"]           # we store difficulty in 'ease'
        last_ivl = max(0.0, prev["interval_days"])
        last_review = prev.get("last_review", now - last_ivl * _DAY)
        elapsed_days = max(0.0, (now - last_review) / _DAY)
        stability = prev.get("stability", max(0.1, last_ivl or 1.0))
        r = _retrievability(elapsed_days, stability)
        difficulty = _next_difficulty(difficulty, g)
        stability = _next_stability(difficulty, stability, r, g)
        reps = prev["repetitions"] + 1

    interval = 0.02 if g == 1 else _next_interval(stability)
    due_at = now + interval * _DAY
    store.srs_upsert(qid, topic, course_id, difficulty, interval, reps, due_at,
                     stability=stability, last_review=now)


def due_concepts(store, limit: int = 50, now: float = None) -> List[Dict[str, Any]]:
    return store.srs_due(now=now, limit=limit)
