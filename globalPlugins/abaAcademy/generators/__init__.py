# -*- coding: utf-8 -*-
"""
abaAcademy.generators
=====================

The procedural question engine.

A *generator* turns a small amount of structured data (a word list, a set of
grammar frames) into an effectively unlimited stream of distinct ``Question``
objects. Generators are registered under string ids so JSON lessons can
invoke them without importing Python::

    { "btype": "generated", "generator": "ar.plural", "count": 8 }

The engine core stays ignorant of what any generator *means*: it just asks the
registry for id ``"ar.plural"`` and pulls ``count`` questions. Adding a new
generator (e.g. Spanish conjugation) is a self-contained file that calls
``register()`` — no engine change, no GUI change.

Determinism & anti-repetition
-----------------------------
Each generator is seeded per-call and tracks recently produced signatures so a
single session doesn't show the same item twice in a row. The ``qid`` of a
generated question is derived from ``generator_id + signature`` so spaced
repetition and the mistake log can track the *concept* even though wording
varies.
"""

from __future__ import annotations

import hashlib
import random
from typing import Callable, Dict, Iterable, List, Optional

from ..engine.models import Question

# registry: id -> factory(count, rng, **params) -> List[Question]
_REGISTRY: Dict[str, Callable[..., List[Question]]] = {}


def register(generator_id: str):
    """Decorator to register a generator factory under a string id."""
    def _wrap(fn: Callable[..., List[Question]]):
        _REGISTRY[generator_id] = fn
        fn.generator_id = generator_id  # type: ignore[attr-defined]
        return fn
    return _wrap


def available() -> List[str]:
    return sorted(_REGISTRY)


def generate(generator_id: str, count: int = 10, seed: Optional[int] = None,
             **params) -> List[Question]:
    """Produce ``count`` questions from generator ``generator_id``.

    Returns an empty list for unknown ids (callers degrade gracefully rather
    than crashing a lesson).
    """
    fn = _REGISTRY.get(generator_id)
    if not fn:
        return []
    rng = random.Random(seed)
    return fn(count, rng, **params)


def signature_qid(generator_id: str, signature: str) -> str:
    h = hashlib.sha1(f"{generator_id}|{signature}".encode("utf-8")).hexdigest()
    return h[:12]


class Deduper:
    """Avoids emitting the same item twice in close succession.

    **Self-healing.** The original version was a plain "have I seen this?"
    filter, which quietly turned every generator into a bounded one: once a
    small data table was exhausted, ``fresh()`` returned ``False`` forever, the
    generator's guard loop spun out, and it returned fewer questions than
    asked -- often far fewer. A lesson requesting twenty items from a six-row
    table got six, and endless practice was not endless.

    Now the deduper distinguishes "recently seen" from "nothing left". After
    ``stall_limit`` consecutive rejections it concludes the pool has been
    exhausted, forgets its history and starts a new pass. Anti-repetition is
    preserved *within* a pass, which is what a learner actually notices, while
    supply becomes unlimited.
    """

    def __init__(self, avoid_last: int = 25, stall_limit: int = 12):
        self._seen: List[str] = []
        self._avoid_last = avoid_last
        self._stall_limit = stall_limit
        self._stalls = 0

    def fresh(self, signature: str) -> bool:
        if signature not in self._seen[-self._avoid_last:]:
            self._stalls = 0
            return True
        self._stalls += 1
        if self._stalls >= self._stall_limit:
            # Pool exhausted: begin a new pass rather than starving the caller.
            self.reset()
            return True
        return False

    def add(self, signature: str) -> None:
        self._seen.append(signature)

    def reset(self) -> None:
        """Forget history so the pool can be cycled again."""
        self._seen.clear()
        self._stalls = 0


def fill_to_count(builders, count: int, rng: random.Random) -> List[Question]:
    """Turn a finite list of question *builders* into exactly ``count`` questions.

    This is the mechanism behind the platform's "unlimited exercises" promise,
    and it fixes a real ceiling in the previous build: a generator would emit
    one question per distinct data row and then simply stop. A lesson whose
    frame table held two rows produced two questions no matter whether the
    block asked for eight or eighty, so "endless practice" ended after a
    couple of items and quizzes were far shorter than authored.

    ``builders`` is a list of zero-argument callables, each returning a fresh
    ``Question``. They are drawn in shuffled order; once every builder has been
    used the pool is reshuffled and drawn again. Because the builders
    re-randomise their own presentation on each call -- option order, which
    distractors are shown, which direction the question is asked in -- a second
    pass is not a repeat of the first, and the learner can drill a small table
    indefinitely without meeting the identical item twice in a row.

    Concept identity (``qid``) is preserved across passes on purpose: spaced
    repetition tracks the *idea*, not the wording.
    """
    if not builders or count <= 0:
        return []
    out: List[Question] = []
    order = list(builders)
    rng.shuffle(order)
    index = 0
    guard = 0
    limit = count * 8 + 64
    while len(out) < count and guard < limit:
        guard += 1
        if index >= len(order):
            rng.shuffle(order)
            index = 0
        try:
            question = order[index]()
        except Exception:
            question = None
        index += 1
        if question is not None:
            out.append(question)
    return out


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance between two strings (small strings only)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def word_similarity(a: str, b: str) -> float:
    """A 0..1 look/sound similarity for single words, used to pick language
    distractors that resemble the answer — words that look or sound alike and
    are therefore easy to confuse (e.g. English «desert»/«dessert», «through»/
    «thorough», or French «poisson»/«poison»). Based on edit distance plus
    shared prefix/suffix and equal length, so close spellings rank highest."""
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b or a == b:
        return 0.0
    m = max(len(a), len(b))
    score = 1 - _edit_distance(a, b) / m           # 1 == identical
    # shared prefix
    p = 0
    while p < min(len(a), len(b)) and a[p] == b[p]:
        p += 1
    score += 0.3 * (p / m)
    # shared suffix
    s = 0
    while s < min(len(a), len(b)) and a[-1 - s] == b[-1 - s]:
        s += 1
    score += 0.2 * (s / m)
    # equal length (anagrams / one-letter swaps read very alike)
    if len(a) == len(b):
        score += 0.15
    return score


def _similarity(a: str, b: str) -> float:
    """A cheap 0..1 similarity between two option strings, used to rank
    distractors so the ones most easily confused with the answer are preferred.

    It rewards options that share the answer's *shape*: the same leading word
    (e.g. a currency/title word like «الدينار» / «الريال»), overlapping words,
    a shared prefix, and a similar length. This is what turns a bland option set
    into a genuine trap — for «الجنيه السوداني» the close lures are «الدينار
    السوداني», «الريال السوداني», «الليرة السودانية» rather than an obviously
    unrelated word.
    """
    if not a or not b or a == b:
        return 0.0
    wa, wb = a.split(), b.split()
    score = 0.0
    # shared whole words (e.g. the country/qualifier word «السوداني»)
    common = set(wa) & set(wb)
    if common:
        score += 0.5 * len(common) / max(len(wa), len(wb))
    # same first word (the "kind" word: currency, capital-form, title…) — this
    # is the strongest confusability signal for "X-type of country Y" answers
    # (الريال السعودي vs الريال العُماني; الدينار الليبي vs الدينار الأردني), so
    # it is weighted heavily to keep same-family lures at the top of the ranking.
    if wa and wb and wa[0] == wb[0]:
        score += 0.5
    # same last word (shared qualifier / nationality)
    if wa and wb and wa[-1] == wb[-1]:
        score += 0.2
    # last words that share a long stem (e.g. «السوداني» vs «السودانية») — the
    # same nationality in a different grammatical form is still a strong lure
    elif wa and wb and len(wa[-1]) >= 4 and len(wb[-1]) >= 4:
        la, lb = wa[-1], wb[-1]
        k = 0
        while k < min(len(la), len(lb)) and la[k] == lb[k]:
            k += 1
        if k >= 4:
            score += 0.18
    # shared character prefix
    n = min(len(a), len(b))
    p = 0
    while p < n and a[p] == b[p]:
        p += 1
    score += 0.2 * (p / max(len(a), len(b)))
    # similar length
    score += 0.15 * (1 - abs(len(a) - len(b)) / max(len(a), len(b)))
    return score


def shuffled_options(rng: random.Random, correct: str, distractors: Iterable[str],
                     want: int = 4, hard: float = 0.6, sim=None) -> "tuple[List[str], int]":
    """Build an option list containing ``correct`` plus plausible distractors.

    Returns ``(options, correct_index)``. Distractors are chosen to be genuinely
    confusable with the answer: a share (``hard``) of the slots are filled with
    the options most *similar* to the correct answer, so the learner faces
    near-misses they must actually know apart, not obvious throwaways. The
    remaining slot(s) are sampled from the rest of the pool so repeated calls
    still vary. Duplicates and any distractor equal to the answer are dropped.

    ``sim`` is the similarity function used for ranking; it defaults to the
    phrase-shape ``_similarity`` (good for multi-word facts), but language
    generators pass ``word_similarity`` to prefer look/sound-alike single words.
    """
    sim = sim or _similarity
    pool = [d for d in dict.fromkeys(distractors) if d and d != correct]
    if not pool:
        return [correct], 0
    slots = max(1, want - 1)
    n_hard = min(len(pool), round(slots * hard))

    # rank by similarity to the answer; the closest are the trickiest lures
    ranked = sorted(pool, key=lambda d: sim(correct, d), reverse=True)
    # take a small band of the closest lures, then randomise within it so the
    # exact set still varies between reruns instead of being identical each time
    band = ranked[: max(n_hard, min(len(ranked), slots + 2))]
    rng.shuffle(band)
    chosen = band[:n_hard]

    # fill the remaining slots from whatever's left, sampled for variety
    rest = [d for d in pool if d not in chosen]
    rng.shuffle(rest)
    chosen += rest[: slots - len(chosen)]

    options = list(dict.fromkeys(chosen + [correct]))
    rng.shuffle(options)
    return options, options.index(correct)


# Importing this package registers the bundled generators as a side effect.
# Kept at the bottom to avoid circular imports during module init.
def load_builtin_generators() -> None:
    from . import generic  # noqa: F401
    from . import arabic  # noqa: F401
    from . import vocabulary  # noqa: F401
    from . import language  # noqa: F401
    from . import math  # noqa: F401
    from . import braille  # noqa: F401
    from . import knowledge  # noqa: F401
