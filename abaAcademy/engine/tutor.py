# -*- coding: utf-8 -*-
"""
abaAcademy.engine.tutor
=======================

A smart study companion that decides *what* to put in front of the learner *now*,
and *how much* of each kind, based on how they've been doing. It is not an AI
model and needs no network — it is a transparent, rule-based planner over the
data the app already records (per-topic right/wrong counts, spaced-repetition due
dates, streak, recent accuracy). Being deterministic means it is testable and its
choices are explainable to the learner ("راجعنا هذا لأنك أخطأت فيه أمس").

What it does
------------
* **Interleaving for durable memory.** A session isn't only the current unit.
  The planner blends: new items from the current topic, *due* spaced-repetition
  items from earlier units, and a small slice of already-learned material to keep
  it fresh. Research on learning (spacing + interleaving + retrieval practice)
  says this mix remembers far better than massed repetition — so the planner
  builds that mix by default.
* **Adapts to the learner.** As accuracy on a topic rises, its share of the
  session shrinks and harder/newer material grows; when accuracy falls, the
  planner pulls that topic back in and slows down. The difficulty target rises
  and falls with a rolling estimate of the learner's success rate.
* **Explains itself and encourages.** For any plan it can say, in Arabic, why it
  chose what it did, and it surfaces streaks and improvements so studying feels
  rewarding rather than opaque.

The planner returns a *recipe* (counts per source); a provider callback turns the
recipe into actual questions, so this module stays free of question generation.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple


# target overall session size when the tutor plans a mixed review
DEFAULT_SESSION_SIZE = 12


class MasteryEstimate:
    """A simple, explainable mastery read for one topic."""

    def __init__(self, topic, right, wrong):
        self.topic = topic
        self.right = right
        self.wrong = wrong

    @property
    def attempts(self):
        return self.right + self.wrong

    @property
    def accuracy(self):
        if self.attempts == 0:
            return None
        return self.right / self.attempts

    @property
    def level(self):
        """A coarse label: new / struggling / learning / strong / mastered."""
        a = self.accuracy
        if a is None:
            return "new"
        if self.attempts < 3:
            return "learning"
        if a < 0.5:
            return "struggling"
        if a < 0.8:
            return "learning"
        if a < 0.95:
            return "strong"
        return "mastered"

    def label_ar(self):
        return {
            "new": "جديد",
            "struggling": "يحتاج تدعيمًا",
            "learning": "قيد التعلّم",
            "strong": "جيّد",
            "mastered": "متقَن",
        }[self.level]


class SessionPlan:
    """The recipe the tutor produces for one study session."""

    def __init__(self):
        self.new_count = 0
        self.review_due_count = 0
        self.weak_count = 0
        self.interleave_count = 0
        self.difficulty_target = 1
        self.reasons: List[str] = []
        self.weak_topics: List[str] = []

    @property
    def total(self):
        return (self.new_count + self.review_due_count
                + self.weak_count + self.interleave_count)

    def explain_ar(self):
        return " ".join(self.reasons) if self.reasons else "جلسة تدريب متوازنة."


class Tutor:
    """Plans adaptive sessions from the store's history."""

    def __init__(self, store):
        self.store = store

    # -- reading the learner ---------------------------------------------
    def mastery(self, topic) -> Optional[MasteryEstimate]:
        try:
            for t, wrong, right in self.store.weakest_topics(limit=200):
                if t == topic:
                    return MasteryEstimate(topic, right, wrong)
            for t, wrong, right in self.store.strongest_topics(limit=200):
                if t == topic:
                    return MasteryEstimate(topic, right, wrong)
        except Exception:
            pass
        return None

    def recent_accuracy(self, default=0.7) -> float:
        """A rolling success estimate across all topics, used to set difficulty
        and pacing. Falls back to a neutral value when there's little history."""
        try:
            weak = self.store.weakest_topics(limit=100)
            total_r = sum(r for _, _, r in weak)
            total_w = sum(w for _, w, _ in weak)
            strong = self.store.strongest_topics(limit=100)
            total_r += sum(r for _, _, r in strong)
            total_w += sum(w for _, w, _ in strong)
            if total_r + total_w < 5:
                return default
            return total_r / (total_r + total_w)
        except Exception:
            return default

    def due_reviews(self, limit=20):
        """Spaced-repetition items that are due, via the SRS module."""
        try:
            from ..database import srs
            return srs.due_concepts(self.store, limit=limit)
        except Exception:
            return []

    # -- planning ---------------------------------------------------------
    def plan_session(self, current_topic=None, size=DEFAULT_SESSION_SIZE,
                     difficulty_override=None) -> SessionPlan:
        """Produce a mixed recipe: new material + due reviews + weak-topic
        reinforcement + a little interleaving, sized to ``size`` and tuned to the
        learner's recent accuracy. ``difficulty_override`` ('easy'/'medium'/'hard')
        forces the difficulty target instead of deriving it from accuracy, for a
        learner who wants manual control."""
        plan = SessionPlan()
        acc = self.recent_accuracy()

        # difficulty target rises with success (1 easy .. 3 hard), unless the
        # learner has chosen a fixed level in settings.
        override_map = {"easy": 1, "medium": 2, "hard": 3}
        if difficulty_override in override_map:
            plan.difficulty_target = override_map[difficulty_override]
            plan.reasons.append("ثبّتَّ مستوى الصعوبة يدويًا.")
        elif acc >= 0.85:
            plan.difficulty_target = 3
            plan.reasons.append("أداؤك ممتاز، فرفعنا مستوى الصعوبة.")
        elif acc >= 0.65:
            plan.difficulty_target = 2
        else:
            plan.difficulty_target = 1
            plan.reasons.append("سنركّز على الأساسيات لتثبيتها أولًا.")

        due = self.due_reviews(limit=size)
        weak = []
        try:
            weak = [t for t, w, r in self.store.weakest_topics(limit=5)
                    if w > r]           # more misses than hits = genuinely weak
        except Exception:
            pass
        plan.weak_topics = weak

        # --- allocate the session --------------------------------------
        # base split: ~40% new, ~30% due review, ~20% weak, ~10% interleave.
        # shift toward review/weak when accuracy is low; toward new when high.
        if acc < 0.6:
            new_share, due_share, weak_share, il_share = 0.20, 0.35, 0.35, 0.10
            plan.reasons.append("زدنا المراجعة لأن بعض الموضوعات تحتاج تدعيمًا.")
        elif acc < 0.8:
            new_share, due_share, weak_share, il_share = 0.40, 0.30, 0.20, 0.10
        else:
            new_share, due_share, weak_share, il_share = 0.55, 0.20, 0.10, 0.15
            plan.reasons.append("أضفنا مواد جديدة ومسائل متنوّعة من دروس سابقة "
                                "لتبقى راسخة.")

        plan.review_due_count = min(len(due), round(size * due_share))
        plan.weak_count = round(size * weak_share) if weak else 0
        plan.interleave_count = round(size * il_share)
        # new material fills the rest
        used = plan.review_due_count + plan.weak_count + plan.interleave_count
        plan.new_count = max(0, size - used)

        if plan.review_due_count:
            plan.reasons.append(
                f"راجعنا {plan.review_due_count} بندًا حان موعد تكراره.")
        if plan.interleave_count:
            plan.reasons.append("خلطنا أسئلة من دروس سابقة ليدوم أثر التعلّم.")

        return plan

    def build_session_questions(self, plan: SessionPlan, current_topic,
                                provider: Callable[[str, int], List],
                                interleave_provider: Callable[[int], List] = None):
        """Turn a plan into an ordered, de-duplicated question list using the
        given providers. ``provider(topic, n)`` yields questions for a topic (or
        endless when topic==''); ``interleave_provider(n)`` yields questions from
        earlier learned material. Ordering interleaves sources so the learner
        doesn't get all-review-then-all-new."""
        buckets = []
        # new material from the current topic (or general if none)
        if plan.new_count:
            buckets.append(provider(current_topic or "", plan.new_count) or [])
        # weak-topic reinforcement
        weak_each = 0
        if plan.weak_count and plan.weak_topics:
            weak_each = max(1, plan.weak_count // len(plan.weak_topics))
            wq = []
            for t in plan.weak_topics:
                wq.extend(provider(t, weak_each) or [])
            buckets.append(wq)
        # interleaving from earlier material
        if plan.interleave_count and interleave_provider:
            buckets.append(interleave_provider(plan.interleave_count) or [])
        elif plan.interleave_count:
            buckets.append(provider("", plan.interleave_count) or [])

        # round-robin merge so sources are interleaved, then dedup by qid
        merged = []
        seen = set()
        i = 0
        while any(i < len(b) for b in buckets):
            for b in buckets:
                if i < len(b):
                    q = b[i]
                    qid = getattr(q, "qid", None)
                    if qid and qid in seen:
                        continue
                    if qid:
                        seen.add(qid)
                    merged.append(q)
            i += 1
        return merged

    # -- encouragement ----------------------------------------------------
    def encouragement_ar(self) -> str:
        """A short, honest, encouraging line based on real progress signals."""
        bits = []
        try:
            streak = self.store.current_streak()
            if streak >= 2:
                bits.append(f"واصلت الدراسة {streak} أيّامًا متتالية — أحسنت!")
        except Exception:
            pass
        try:
            strong = self.store.strongest_topics(limit=1)
            if strong and strong[0][2] >= 5:
                bits.append("أتقنت موضوعًا بجدارة.")
        except Exception:
            pass
        if not bits:
            bits.append("كل جلسة تقرّبك خطوة. لنبدأ!")
        return " ".join(bits)
