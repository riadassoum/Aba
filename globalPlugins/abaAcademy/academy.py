# -*- coding: utf-8 -*-
"""
abaAcademy.academy
==================

The application service that ties every subsystem together and exposes a small,
GUI-friendly API. Screens never touch the loader, generators, or store
directly — they go through ``Academy``. This keeps wiring in one place and
makes the whole flow unit-testable by constructing an ``Academy`` over a temp
directory + in-memory-ish SQLite file.

Responsibilities:
  * own the ``CourseRepository``, ``Store``, ``Settings``, ``SpeechManager``,
  * materialize a lesson's blocks into concrete ``Question`` lists (expanding
    ``generated`` blocks by calling the generator registry with data pulled
    from the relevant course pack's data files),
  * assemble sessions: single lesson quiz, mixed multi-lesson session, endless
    practice, and spaced-repetition review,
  * enforce lesson isolation — each session is built from a freshly loaded set
    of lessons and owns its own question list.
"""

from __future__ import annotations

import json
import os
import random
from typing import Any, Dict, List, Optional

from . import generators as gen
from .database.store import Store
from .engine.loader import CourseRepository
from .engine.models import Block, BlockType, Lesson, Question, QuestionType
from .engine.session import QuestionSession
from .settings.settings import Settings


class Academy:
    def __init__(self, base_dir: str, user_data_dir: str,
                 speech=None):
        self.base_dir = base_dir
        self.user_data_dir = user_data_dir
        self.resource_dir = os.path.join(base_dir, "resources")
        course_dirs = [
            os.path.join(base_dir, "courses"),
            os.path.join(user_data_dir, "courses"),  # user-installed packs
        ]
        gen.load_builtin_generators()
        self.repo = CourseRepository(course_dirs, generator_registry=gen)
        self.repo.discover()
        self.store = Store(os.path.join(user_data_dir, "aba_academy.db"))
        from .flashcards import FlashcardStore
        self.flashcards = FlashcardStore(self.store)
        self.settings = Settings(self.store)
        self.speech = speech
        # cache of course data files (word banks etc.), loaded lazily per course
        self._course_data: Dict[str, Dict[str, Any]] = {}

    # -- catalogue ---------------------------------------------------------

    def courses(self):
        return self.repo.courses()

    def course(self, course_id: str):
        return self.repo.course(course_id)

    def total_lessons(self, course_id: str) -> int:
        c = self.repo.course(course_id)
        return c.lesson_count() if c else 0

    def completed_lessons(self, course_id: str) -> int:
        return self.store.completed_lessons(course_id)

    # -- course data (word banks / generator params) -----------------------

    def _course_data_for(self, course_id: str) -> Dict[str, Any]:
        if course_id in self._course_data:
            return self._course_data[course_id]
        data: Dict[str, Any] = {}
        course = self.repo.course(course_id)
        if course and course.path:
            data_dir = os.path.join(course.path, "data")
            if os.path.isdir(data_dir):
                for fn in os.listdir(data_dir):
                    if fn.endswith(".json"):
                        try:
                            with open(os.path.join(data_dir, fn), encoding="utf-8") as f:
                                loaded = json.load(f)
                        except (OSError, ValueError):
                            continue
                        data[fn[:-5]] = loaded
                        # Also expose nested tables by their own key so a
                        # generated block can reference e.g. "definite_words"
                        # directly regardless of which file it lives in.
                        if isinstance(loaded, dict):
                            for k, v in loaded.items():
                                if isinstance(v, (dict, list)) and k not in data:
                                    data[k] = v
        self._course_data[course_id] = data
        return data

    # -- question materialization -----------------------------------------

    def _expand_block(self, block: Block, course_id: str,
                      seed: Optional[int]) -> List[Question]:
        """Turn one block into concrete questions."""
        if block.btype in (BlockType.QUESTION, BlockType.EXAM):
            return list(block.questions)
        if block.btype is BlockType.GENERATED:
            generator_id = block.data.get("generator", "")
            count = int(block.data.get("count", 8))
            params = dict(block.data.get("params", {}))
            # Allow a generated block to pull its data table from the course's
            # data files by name, e.g. {"data": "words"} -> data/words.json.
            data_key = block.data.get("data")
            if data_key:
                cdata = self._course_data_for(course_id)
                payload = cdata.get(data_key)
                if isinstance(payload, dict):
                    params.update(payload)
                elif isinstance(payload, list):
                    # bare list -> hand it under the most common param names
                    params.setdefault("words", payload)
                    params.setdefault("pairs", payload)
                    params.setdefault("verbs", payload)
                    params.setdefault("frames", payload)
                    params.setdefault("cases", payload)
                    params.setdefault("statements", payload)
            return gen.generate(generator_id, count=count, seed=seed, **params)
        # Non-question teaching blocks contribute nothing to a quiz pool.
        return []

    def questions_from_blocks(self, blocks: List[Block], course_id: str,
                              seed: Optional[int] = None) -> List[Question]:
        out: List[Question] = []
        for b in blocks:
            out.extend(self._expand_block(b, course_id, seed))
        return out

    @staticmethod
    def dedup_questions(questions: List[Question]) -> List[Question]:
        """Remove duplicate questions from a single session.

        Keying: a question's unique id (qid) when it has one, otherwise its
        prompt text *plus* its spoken text. This keeps the "no identical
        question twice in a test" rule while never collapsing genuinely
        different items -- e.g. dictation questions share one visible prompt
        ("type what you hear") but carry different spoken sentences, so they
        must be distinguished by the spoken text, not merged into one.
        """
        seen = set()
        result: List[Question] = []
        for q in questions:
            prompt = " ".join((q.prompt or "").split()).casefold()
            speak = " ".join((getattr(q, "speak", "") or "").split()).casefold()
            opts = tuple(q.options) if isinstance(q.options, list) else ()
            key = (prompt, speak, str(q.correct), opts)
            if key in seen:
                continue
            seen.add(key)
            result.append(q)
        return result

    def _top_up(self, pool: List[Question], refill, target: int) -> List[Question]:
        """Grow a question pool until it reaches ``target`` items.

        A lesson's authored quiz can be short -- sometimes only the two or
        three hand-written items the author had time for. Previously that was
        the whole test: the learner answered three questions and the session
        ended, no matter what session length they had configured. Now any
        shortfall is made up from the lesson's own generators, so every test is
        a real test while still being built entirely from that lesson's
        material.

        Top-up questions are deduplicated against what is already queued, and
        the loop gives up rather than spinning if a lesson genuinely has no
        generated content to draw on.
        """
        if refill is None or len(pool) >= target:
            return pool
        seen = {" ".join((q.prompt or "").split()).casefold() for q in pool}
        attempts = 0
        while len(pool) < target and attempts < 12:
            attempts += 1
            batch = refill("", (target - len(pool)) * 2) or []
            added = 0
            for q in batch:
                key = " ".join((q.prompt or "").split()).casefold()
                if key in seen:
                    continue
                seen.add(key)
                pool.append(q)
                added += 1
                if len(pool) >= target:
                    break
            if not added:
                break  # nothing generative to draw on; keep what we have
        return pool

    # -- session assembly --------------------------------------------------

    def load_lesson(self, lesson_id: str) -> Optional[Lesson]:
        return self.repo.load_lesson(lesson_id)

    def build_lesson_quiz(self, lesson_id: str,
                          seed: Optional[int] = None) -> Optional[QuestionSession]:
        lesson = self.repo.load_lesson(lesson_id)
        if not lesson:
            return None
        course_id = lesson.meta.course_id
        pool = self.questions_from_blocks(lesson.quiz or lesson.practice, course_id, seed)
        pool = self.dedup_questions(pool)
        refill = self._make_refill(course_id, [lesson_id])
        pool = self._top_up(pool, refill, self.settings.session_size)
        if not pool:
            # Never show "no exercises": fall back to the course's own material.
            pool = self._course_fallback_pool(
                course_id, lesson_id, self.settings.session_size)
        random.Random(seed).shuffle(pool)
        if not pool:
            return None
        self.store.set_setting("last_lesson", lesson_id)
        session_id = self.store.start_session(
            course_id, lesson.meta.level_id, [lesson_id], "quiz")
        return QuestionSession(
            pool, keep_diacritics=self.settings.strict_tashkeel,
            store=self.store, course_id=course_id, session_id=session_id,
            refill=refill,
        )

    def _order_by_lesson_difficulty(self, lesson_id, pool):
        """When several lessons share the same example set (ids ending .0, .1,
        .2 …), make each successive lesson harder: the first favours the easiest
        question shapes, the last the hardest. Typed recall is hardest, MCQ is
        middling, and true/false is easiest; within a tier, questions carrying a
        higher ``difficulty`` come first. The whole pool is kept (so nothing is
        lost) — only its order is biased, and the session then samples from the
        front."""
        # tier index from the trailing ".N" of the lesson id, else 0
        tier = 0
        tail = lesson_id.rsplit(".", 1)[-1]
        if tail.isdigit():
            tier = int(tail)

        from .engine.models import QuestionType

        def hardness(q):
            # base hardness of the question shape
            qt = getattr(q, "qtype", None)
            if qt == QuestionType.TYPING:
                base = 3
            elif qt == QuestionType.MCQ:
                base = 2
            else:  # true/false, ordering, etc.
                base = 1
            base += int(getattr(q, "difficulty", 1))
            return base

        # tier 0 wants easy first (ascending hardness); higher tiers want hard
        # first (descending). Ties fall back to a stable per-question key so the
        # order is deterministic for a given lesson.
        reverse = tier >= 1
        pool = sorted(pool, key=lambda q: (hardness(q), getattr(q, "qid", "")),
                      reverse=reverse)
        return pool

    def export_progress_text(self) -> str:
        """A full, human-readable progress report the learner can save or share:
        overall figures, per-course completion, earned achievements, and their
        weakest topics. Assembled from the same real data the screens show."""
        import datetime
        s = self.home_summary()
        lines = []
        lines.append("تقرير تقدّم — أكاديمية الكفيف العربي")
        lines.append("تاريخ التصدير: " + datetime.date.today().isoformat())
        lines.append("=" * 40)
        lines.append("")
        lines.append("ملخّص عام:")
        lines.append(f"  سلسلة الأيام: {s['streak']}")
        lines.append(f"  الدروس المكتملة: {s['lessons_done']} من {s['lessons_total']}")
        lines.append(f"  الأسئلة المُجابة: {s['answered']}")
        lines.append(f"  الدقة: {s['accuracy']}٪")
        lines.append(f"  وقت الدراسة: {s['minutes']} دقيقة")
        lines.append(f"  الإنجازات: {s['earned_achievements']} من {s['total_achievements']}")
        lines.append("")
        lines.append("التقدّم في الدورات:")
        for p in self.course_progress():
            mark = " (مكتملة ✓)" if p["complete"] else ""
            lines.append(f"  {p['title']}: {p['done']} من {p['total']} — {p['percent']}٪{mark}")
        lines.append("")
        try:
            weak = self.store.weakest_topics(limit=10)
            if weak:
                lines.append("أكثر المواضيع خطأً (للمراجعة):")
                for topic, wrong, right in weak:
                    lines.append(f"  {topic}: أخطأت {wrong} من {wrong + right}")
                lines.append("")
        except Exception:
            pass
        lines.append("واصل التعلّم!")
        return "\n".join(lines)

    def write_export(self, filename: str = "aba_progress.txt") -> str:
        """Write the progress report into the user's data folder and return the
        full path, so the learner has a file they can keep or send."""
        import os
        path = os.path.join(self.user_data_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.export_progress_text())
        return path

    def course_progress(self):
        """Per-course completion, for the certificates screen and progress views.
        Returns a list of dicts with the course, how many lessons are done, the
        total, the percent, and whether it is fully complete (a certificate is
        earned)."""
        out = []
        for c in self.courses():
            total = self.total_lessons(c.course_id)
            done = self.completed_lessons(c.course_id)
            pct = round(done * 100 / total) if total else 0
            out.append({
                "course_id": c.course_id,
                "title": c.title,
                "done": done,
                "total": total,
                "percent": pct,
                "complete": total > 0 and done >= total,
            })
        return out

    def build_lesson_practice(self, lesson_id: str,
                              seed: Optional[int] = None) -> Optional[QuestionSession]:
        """Full practice drill for a lesson: uses the richer practice blocks
        (every exercise type, many items) rather than the shorter quiz, deduped
        so nothing repeats within the run."""
        lesson = self.repo.load_lesson(lesson_id)
        if not lesson:
            return None
        course_id = lesson.meta.course_id
        pool = self.questions_from_blocks(lesson.practice or lesson.quiz, course_id, seed)
        pool = self.dedup_questions(pool)
        pool = self._augment_matching(lesson, course_id, pool, seed)
        pool = self._order_by_lesson_difficulty(lesson_id, pool)
        refill = self._make_refill(course_id, [lesson_id])
        # Practice is the longer drill, so aim higher than a quiz.
        pool = self._top_up(pool, refill, max(self.settings.session_size, 15))
        if not pool:
            pool = self._course_fallback_pool(
                course_id, lesson_id, max(self.settings.session_size, 15))
        random.Random(seed).shuffle(pool)
        if not pool:
            return None
        self.store.set_setting("last_lesson", lesson_id)
        session_id = self.store.start_session(
            course_id, lesson.meta.level_id, [lesson_id], "practice")
        return QuestionSession(
            pool, keep_diacritics=self.settings.strict_tashkeel,
            store=self.store, course_id=course_id, session_id=session_id,
            refill=refill,
        )


    def _lesson_word_bank(self, lesson, course_id):
        """Collect the word records a language lesson's generated blocks use, so
        we can add matching-pairs questions from the same vocabulary."""
        words = []
        for block in (lesson.practice or []):
            if getattr(block, "btype", None) is not BlockType.GENERATED:
                continue
            data = getattr(block, "data", {}) or {}
            gen_id = data.get("generator", "")
            if not gen_id.startswith("lang."):
                continue
            params = dict(data.get("params", {}))
            dkey = data.get("data")
            if dkey:
                payload = self._course_data_for(course_id).get(dkey)
                if isinstance(payload, dict) and "words" in payload:
                    params.setdefault("words", payload["words"])
                elif isinstance(payload, list):
                    params.setdefault("words", payload)
            for w in params.get("words", []):
                if isinstance(w, dict) and w.get("word") and w.get("meaning"):
                    words.append(w)
        # de-dup by word
        seen, uniq = set(), []
        for w in words:
            if w["word"] not in seen:
                seen.add(w["word"]); uniq.append(w)
        return uniq

    def _augment_matching(self, lesson, course_id, pool, seed):
        """Append a couple of matching-pairs questions to a language lesson so
        every current (and future) vocabulary lesson includes the type."""
        try:
            bank = self._lesson_word_bank(lesson, course_id)
            if len(bank) < 3:
                return pool
            lang = ""
            for block in (lesson.practice or []):
                data = getattr(block, "data", {}) or {}
                lang = (data.get("params", {}) or {}).get("lang", "") or lang
            extra = gen.generate("lang.matching", count=2, seed=seed,
                                 words=bank, lang=lang or "lang", pairs=4)
            return self.dedup_questions(pool + extra)
        except Exception:
            return pool

    def build_mixed_session(self, lesson_ids: List[str],
                            seed: Optional[int] = None) -> Optional[QuestionSession]:
        """A balanced session drawing evenly from several lessons at once."""
        if not lesson_ids:
            return None
        rng = random.Random(seed)
        per_lesson: List[List[Question]] = []
        course_id = ""
        level_id = ""
        for lid in lesson_ids:
            lesson = self.repo.load_lesson(lid)  # fresh + isolated per lesson
            if not lesson:
                continue
            course_id = lesson.meta.course_id
            level_id = lesson.meta.level_id
            qs = self.questions_from_blocks(
                lesson.practice + lesson.quiz, course_id, seed)
            rng.shuffle(qs)
            per_lesson.append(qs)
        if not per_lesson:
            return None
        # Interleave round-robin for balance across lessons.
        mixed: List[Question] = []
        idx = 0
        while any(per_lesson):
            bucket = per_lesson[idx % len(per_lesson)]
            if bucket:
                mixed.append(bucket.pop(0))
            idx += 1
            if idx > 10000:
                break
        mixed = self.dedup_questions(mixed)
        refill = self._make_refill(course_id, lesson_ids)
        mixed = self._top_up(mixed, refill,
                             max(self.settings.session_size, 4 * len(lesson_ids)))
        if not mixed:
            return None
        session_id = self.store.start_session(course_id, level_id, lesson_ids, "mixed")
        return QuestionSession(
            mixed, keep_diacritics=self.settings.strict_tashkeel,
            store=self.store, course_id=course_id, session_id=session_id,
            refill=refill,
        )

    def build_endless_practice(self, lesson_ids: List[str],
                               seed: Optional[int] = None) -> Optional[QuestionSession]:
        refill = self._make_refill(course_id_from := self._course_of(lesson_ids), lesson_ids)
        first = refill("", self.settings.get_int("endless_batch", 10))
        if not first:
            return None
        session_id = self.store.start_session(course_id_from, "", lesson_ids, "endless")
        return QuestionSession(
            first, keep_diacritics=self.settings.strict_tashkeel,
            store=self.store, course_id=course_id_from, session_id=session_id,
            refill=refill, endless=True,
        )

    def _course_of(self, lesson_ids: List[str]) -> str:
        for lid in lesson_ids:
            meta = self.repo.lesson_meta(lid)
            if meta:
                return meta.course_id
        return ""

    def _course_fallback_pool(self, course_id: str, exclude_lesson: str,
                              target: int) -> List[Question]:
        """Last-resort questions drawn from *other* lessons in the same course.

        A defence-in-depth net: if a single lesson somehow yields nothing --
        an empty block list, a data file that failed to load, a generator that
        returned nothing for its particular data -- the learner should still
        get a working session from that course's material rather than a
        dead-end "no exercises" message. In normal operation this is never
        reached, because every authored lesson produces its own questions.
        """
        siblings = [lid for lid in self._lessons_for_course(course_id)
                    if lid != exclude_lesson]
        random.shuffle(siblings)
        pool: List[Question] = []
        for lid in siblings:
            lesson = self.repo.load_lesson(lid)
            if not lesson:
                continue
            try:
                qs = self.questions_from_blocks(
                    lesson.practice + lesson.quiz, course_id,
                    seed=random.randint(0, 1 << 30))
            except Exception:
                qs = []
            pool.extend(qs)
            if len(pool) >= target:
                break
        pool = self.dedup_questions(pool)
        random.shuffle(pool)
        return pool[:target]

    def _make_refill(self, course_id: str, lesson_ids: List[str]):
        """Return a refill(topic, n) that regenerates questions on demand.

        Used both for adaptive extra-practice (topic-specific) and endless mode
        (topic empty -> pull from all the lessons' generated/practice pools).
        """
        def refill(topic: str, n: int) -> List[Question]:
            pool: List[Question] = []
            for lid in lesson_ids:
                lesson = self.repo.load_lesson(lid)
                if not lesson:
                    continue
                qs = self.questions_from_blocks(
                    lesson.practice + lesson.quiz, course_id,
                    seed=random.randint(0, 1 << 30))
                if topic:
                    qs = [q for q in qs if q.topic == topic]
                pool.extend(qs)
            random.shuffle(pool)
            return pool[:n]
        return refill

    def build_weak_topics_session(self, limit: int = 15) -> Optional[QuestionSession]:
        """A targeted drill on the topics the learner gets wrong most often. It
        reads the mistake log (``weakest_topics``) and regenerates fresh
        questions for those topics, so practice concentrates exactly where the
        learner is struggling instead of spreading evenly. Returns None when
        there aren't enough recorded mistakes yet."""
        try:
            weak = self.store.weakest_topics(limit=8)
        except Exception:
            weak = []
        if not weak:
            return None
        pool: List[Question] = []
        # find which course each topic belongs to and regenerate for it
        all_courses = [c.course_id for c in self.courses()]
        for topic, wrong, right in weak:
            for course_id in all_courses:
                refill = self._make_refill(course_id, self._lessons_for_course(course_id))
                qs = refill(topic, 3)
                if qs:
                    pool.extend(qs)
                    break
        pool = [q for q in pool if q]
        if not pool:
            return None
        random.shuffle(pool)
        pool = pool[:limit]
        session_id = self.store.start_session("", "", [], "weak")
        return QuestionSession(
            pool, keep_diacritics=self.settings.strict_tashkeel,
            store=self.store, session_id=session_id)

    def build_review_session(self, limit: int = 20) -> Optional[QuestionSession]:
        """Spaced-repetition: resurface concepts that are due.

        We regenerate fresh questions for due concepts by topic (concept
        identity is by qid/topic), so the learner re-meets the *idea* without
        memorizing a fixed string.
        """
        due = self.store.srs_due(limit=limit)
        if not due:
            return None
        # Group due items by course+topic and regenerate.
        pool: List[Question] = []
        for row in due:
            course_id = row.get("course_id", "")
            topic = row.get("topic", "")
            refill = self._make_refill(course_id, self._lessons_for_course(course_id))
            qs = refill(topic, 1)
            pool.extend(qs)
        pool = [q for q in pool if q]
        if not pool:
            return None
        random.shuffle(pool)
        session_id = self.store.start_session("", "", [], "review")
        return QuestionSession(pool, keep_diacritics=self.settings.strict_tashkeel,
                               store=self.store, session_id=session_id)

    def _lessons_for_course(self, course_id: str) -> List[str]:
        course = self.repo.course(course_id)
        if not course:
            return []
        return [m.lesson_id for lv in course.levels for m in lv.lesson_metas]

    # -- search ------------------------------------------------------------

    def search(self, query: str) -> List[Dict[str, str]]:
        """Search lessons, objectives, and grammar refs by substring."""
        q = query.strip().casefold()
        if not q:
            return []
        results: List[Dict[str, str]] = []
        for meta in self.repo.all_lesson_metas():
            hay = " ".join([meta.title] + meta.objectives + meta.grammar_refs).casefold()
            if q in hay:
                results.append({
                    "lesson_id": meta.lesson_id,
                    "title": meta.title,
                    "course_id": meta.course_id,
                    "level_id": meta.level_id,
                })
        return results

    # -- finalize ----------------------------------------------------------

    def finalize_session(self, session: QuestionSession, lesson_id: str = "",
                         level_id: str = "", course_id: str = "") -> Dict[str, Any]:
        st = session.stats
        percent = int(round(st.accuracy))
        if session._session_id:  # end DB session row
            self.store.end_session(session._session_id, st.total, st.correct,
                                   st.wrong, st.skipped)
        if lesson_id:
            mastery = st.accuracy / 100.0
            self.store.update_lesson_progress(
                lesson_id, course_id, level_id, percent, mastery, completed=percent >= 60)
        granted = self._check_achievements(st)
        return {
            "total": st.total, "correct": st.correct, "wrong": st.wrong,
            "skipped": st.skipped, "accuracy": percent,
            "avg_time": st.avg_response_time,
            "achievements": granted,
        }

    def _check_achievements(self, st) -> List[str]:
        granted = []
        ov = self.store.overall_stats()
        lifetime_correct = int(ov.get("correct", 0))
        streak = self.store.current_streak()
        total_done = sum(self.completed_lessons(c.course_id) for c in self.courses())
        checks = [
            ("first_correct", "أول إجابة صحيحة", st.correct >= 1),
            ("flawless_ten", "عشر إجابات بلا خطأ", st.total >= 10 and st.wrong == 0),
            ("correct_50", "خمسون إجابة صحيحة", lifetime_correct >= 50),
            ("correct_250", "مئتان وخمسون إجابة صحيحة", lifetime_correct >= 250),
            ("correct_1000", "ألف إجابة صحيحة", lifetime_correct >= 1000),
            ("first_lesson", "أكملت أول درس", total_done >= 1),
            ("ten_lessons", "أكملت عشرة دروس", total_done >= 10),
            ("fifty_lessons", "أكملت خمسين درساً", total_done >= 50),
            ("streak_3", "سلسلة ثلاثة أيام", streak >= 3),
            ("week_streak", "سلسلة أسبوع كامل", streak >= 7),
            ("streak_30", "سلسلة شهر كامل", streak >= 30),
            ("perfect_lesson", "درس كامل بلا خطأ", st.total >= 15 and st.wrong == 0),
        ]
        for ach_id, title, earned in checks:
            if earned and self.store.grant_achievement(ach_id, title):
                granted.append(title)
        return granted

    # Full catalogue, so the achievements screen can show earned AND remaining
    # goals (real, not placeholders — every one is reachable through study).
    ACHIEVEMENTS_CATALOG = [
        ("first_correct", "أول إجابة صحيحة", "أجب عن سؤال واحد بشكل صحيح."),
        ("first_lesson", "أكملت أول درس", "أكمل أي درس بنسبة نجاح."),
        ("flawless_ten", "عشر إجابات بلا خطأ", "أجب عن عشرة أسئلة دون خطأ في جلسة."),
        ("perfect_lesson", "درس كامل بلا خطأ", "أنهِ درساً من خمسة عشر سؤالاً فأكثر بلا خطأ."),
        ("correct_50", "خمسون إجابة صحيحة", "اجمع خمسين إجابة صحيحة إجمالاً."),
        ("correct_250", "مئتان وخمسون إجابة صحيحة", "اجمع مئتين وخمسين إجابة صحيحة."),
        ("correct_1000", "ألف إجابة صحيحة", "اجمع ألف إجابة صحيحة إجمالاً."),
        ("ten_lessons", "أكملت عشرة دروس", "أكمل عشرة دروس."),
        ("fifty_lessons", "أكملت خمسين درساً", "أكمل خمسين درساً."),
        ("streak_3", "سلسلة ثلاثة أيام", "تدرّب ثلاثة أيام متتالية."),
        ("week_streak", "سلسلة أسبوع كامل", "تدرّب سبعة أيام متتالية."),
        ("streak_30", "سلسلة شهر كامل", "تدرّب ثلاثين يوماً متتالياً."),
    ]

    def achievements_overview(self) -> List[Dict[str, Any]]:
        """Catalogue with earned/locked status for the achievements screen."""
        earned_ids = {a["ach_id"] for a in self.store.achievements()}
        return [{"id": aid, "title": title, "desc": desc, "earned": aid in earned_ids}
                for aid, title, desc in self.ACHIEVEMENTS_CATALOG]

    def home_summary(self) -> Dict[str, Any]:
        """Compact progress snapshot for the hub header — all real figures."""
        ov = self.store.overall_stats()
        total_lessons = sum(self.total_lessons(c.course_id) for c in self.courses())
        done = sum(self.completed_lessons(c.course_id) for c in self.courses())
        minutes = int(self.store.total_study_seconds() // 60)
        goal = self.settings.get_int("daily_goal", 20)
        today = self.today_answered()
        return {
            "streak": self.store.current_streak(),
            "lessons_done": done, "lessons_total": total_lessons,
            "accuracy": round(ov.get("accuracy", 0.0)),
            "answered": int(ov.get("answered", 0)),
            "minutes": minutes,
            "earned_achievements": len(self.store.achievements()),
            "total_achievements": len(self.ACHIEVEMENTS_CATALOG),
            "daily_goal": goal,
            "today_answered": today,
            "goal_met": today >= goal,
        }

    def today_answered(self) -> int:
        """How many questions the learner has answered today — for the daily
        goal. Reads the per-day activity the store already records."""
        try:
            import datetime
            today = datetime.date.today().isoformat()
            for row in self.store.daily_activity(days=3):
                if row.get("day") == today:
                    return int(row.get("answered", 0))
        except Exception:
            pass
        return 0

    def last_lesson(self) -> str:
        return self.store.get_setting("last_lesson", "") or ""

    def build_daily_session(self, seed: Optional[int] = None) -> Optional[QuestionSession]:
        """A single 'practice of the day': spaced-repetition items that are due,
        topped up with fresh questions spread across the courses the learner has
        started, so one tap gives a balanced mixed review. Deduped."""
        pool: List[Question] = []
        review = self.build_review_session(limit=12)
        if review:
            while review.has_next():
                q = review.next_question()
                if not q:
                    break
                pool.append(q)
        # top up from the most recently studied lesson + first lessons of courses
        seeds: List[str] = []
        last = self.last_lesson()
        if last:
            seeds.append(last)
        for c in self.courses():
            if c.levels and c.levels[0].lesson_metas:
                seeds.append(c.levels[0].lesson_metas[0].lesson_id)
        for lid in seeds:
            lesson = self.repo.load_lesson(lid)
            if not lesson:
                continue
            qs = self.questions_from_blocks(lesson.practice or lesson.quiz, lesson.meta.course_id, seed)
            pool.extend(qs[:4])
            if len(pool) >= 30:
                break
        pool = self.dedup_questions(pool)
        if not pool:
            return None
        random.Random(seed).shuffle(pool)
        pool = pool[:25]
        session_id = self.store.start_session("", "", seeds, "daily")
        return QuestionSession(pool, keep_diacritics=self.settings.strict_tashkeel,
                               store=self.store, session_id=session_id)

    def close(self) -> None:
        self.store.close()
