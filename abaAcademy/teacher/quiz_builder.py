# -*- coding: utf-8 -*-
"""
abaAcademy.teacher.quiz_builder
===============================

The quiz builder (منشئ الاختبارات): a teacher writes a quiz — multiple
choice, true/false or short-answer questions — saves it, shares it as a
``.abaquiz`` file (plain JSON), and students take it in the academy. Each
attempt records the student's name, score, time taken and every answer, and
the results export as CSV for a gradebook.

Short answers are compared after removing diacritics and folding alif and
ta-marbuta forms, and a question may list several accepted answers.
"""

from __future__ import annotations

import csv
import io
import json
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

KEY = "teacher_quizzes"
RESULTS_KEY = "teacher_quiz_results"
FILE_EXT = ".abaquiz"
FORMAT_VERSION = 1

KINDS = {"mcq": "اختيار من متعدّد", "tf": "صح أم خطأ", "short": "إجابة قصيرة"}

_TASHKEEL = set("ًٌٍَُِّْٰـ")


def fold(text: str) -> str:
    t = "".join(ch for ch in (text or "") if ch not in _TASHKEEL).strip().lower()
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي")):
        t = t.replace(a, b)
    return " ".join(t.split())


@dataclass
class Question:
    kind: str
    prompt: str
    options: List[str] = field(default_factory=list)   # mcq
    correct: int = 0                                    # mcq index
    truth: bool = True                                  # tf
    answers: List[str] = field(default_factory=list)    # short: accepted answers
    explanation: str = ""
    points: float = 1.0

    def validate(self) -> None:
        if self.kind not in KINDS:
            raise ValueError("نوع سؤال غير معروف.")
        if not self.prompt.strip():
            raise ValueError("نصّ السؤال فارغ.")
        if self.kind == "mcq":
            opts = [o for o in self.options if o.strip()]
            if len(opts) < 2:
                raise ValueError("سؤال الاختيار يحتاج خيارين على الأقلّ.")
            if not 0 <= self.correct < len(opts):
                raise ValueError("حدّد الخيار الصحيح.")
            if len(set(fold(o) for o in opts)) != len(opts):
                raise ValueError("في الخيارات تكرار.")
            self.options = opts
        if self.kind == "short" and not [a for a in self.answers if a.strip()]:
            raise ValueError("اكتب إجابة مقبولة واحدة على الأقلّ.")
        if self.points <= 0:
            raise ValueError("درجة السؤال يجب أن تكون موجبة.")

    def correct_text(self) -> str:
        if self.kind == "mcq":
            return self.options[self.correct]
        if self.kind == "tf":
            return "صح" if self.truth else "خطأ"
        return self.answers[0]

    def check(self, answer) -> bool:
        if self.kind == "mcq":
            if isinstance(answer, int):
                return answer == self.correct
            return fold(str(answer)) == fold(self.options[self.correct])
        if self.kind == "tf":
            if isinstance(answer, bool):
                return answer == self.truth
            a = fold(str(answer))
            return (a in ("صح", "صحيح", "نعم", "true", "t")) == self.truth and \
                a in ("صح", "صحيح", "نعم", "true", "t", "خطا", "خطأ", "لا", "false", "f")
        return fold(str(answer)) in {fold(x) for x in self.answers if x.strip()}


@dataclass
class Quiz:
    id: str
    title: str
    author: str = ""
    description: str = ""
    questions: List[Question] = field(default_factory=list)
    shuffle: bool = True
    time_limit: int = 0          # minutes, 0 = none
    pass_mark: float = 50.0      # percent
    created: float = 0.0

    @property
    def total_points(self) -> float:
        return sum(q.points for q in self.questions)

    def to_json(self) -> str:
        d = asdict(self)
        d["format"] = FORMAT_VERSION
        return json.dumps(d, ensure_ascii=False, indent=1)

    @classmethod
    def from_dict(cls, d: dict) -> "Quiz":
        qs = []
        for q in d.get("questions", []):
            qs.append(Question(**{k: v for k, v in q.items() if k in Question.__dataclass_fields__}))
        fields = {k: v for k, v in d.items() if k in cls.__dataclass_fields__ and k != "questions"}
        quiz = cls(questions=qs, **fields)
        if not quiz.id:
            quiz.id = uuid.uuid4().hex[:10]
        return quiz

    @classmethod
    def from_json(cls, text: str) -> "Quiz":
        try:
            d = json.loads(text)
        except ValueError:
            raise ValueError("الملفّ ليس اختبارًا صالحًا.")
        if not isinstance(d, dict) or "questions" not in d:
            raise ValueError("الملفّ ليس اختبارًا من منشئ الاختبارات.")
        quiz = cls.from_dict(d)
        for q in quiz.questions:
            q.validate()
        return quiz


@dataclass
class Attempt:
    quiz_id: str
    quiz_title: str
    student: str
    started: float
    finished: float = 0.0
    answers: List[Tuple[int, str, bool]] = field(default_factory=list)   # (question index, answer, ok)
    score: float = 0.0
    total: float = 0.0
    timed_out: bool = False

    @property
    def percent(self) -> float:
        return 100.0 * self.score / self.total if self.total else 0.0

    @property
    def seconds(self) -> int:
        return int((self.finished or time.time()) - self.started)


class QuizStore:
    def __init__(self, store):
        self.store = store

    def _load(self) -> List[Quiz]:
        try:
            raw = json.loads(self.store.get_setting(KEY, "[]") or "[]")
            return [Quiz.from_dict(d) for d in raw]
        except Exception:
            return []

    def _save(self, quizzes: Sequence[Quiz]) -> None:
        self.store.set_setting(KEY, json.dumps([asdict(q) for q in quizzes], ensure_ascii=False))

    def all(self) -> List[Quiz]:
        return self._load()

    def get(self, quiz_id: str) -> Optional[Quiz]:
        return next((q for q in self._load() if q.id == quiz_id), None)

    def create(self, title: str, author: str = "") -> Quiz:
        title = " ".join((title or "").split())
        if not title:
            raise ValueError("اكتب عنوانًا للاختبار.")
        q = Quiz(uuid.uuid4().hex[:10], title, author, created=time.time())
        items = self._load()
        items.append(q)
        self._save(items)
        return q

    def save_quiz(self, quiz: Quiz) -> None:
        items = [q for q in self._load() if q.id != quiz.id]
        items.append(quiz)
        items.sort(key=lambda q: q.created)
        self._save(items)

    def delete(self, quiz_id: str) -> bool:
        items = self._load()
        new = [q for q in items if q.id != quiz_id]
        if len(new) == len(items):
            return False
        self._save(new)
        return True

    def import_quiz(self, text: str) -> Quiz:
        quiz = Quiz.from_json(text)
        existing = {q.id for q in self._load()}
        if quiz.id in existing:
            quiz.id = uuid.uuid4().hex[:10]
            quiz.title += " (نسخة)"
        quiz.created = time.time()
        self.save_quiz(quiz)
        return quiz

    # -- results ---------------------------------------------------------
    def results(self, quiz_id: Optional[str] = None) -> List[Attempt]:
        try:
            raw = json.loads(self.store.get_setting(RESULTS_KEY, "[]") or "[]")
        except Exception:
            raw = []
        out = []
        for d in raw:
            a = Attempt(**{k: v for k, v in d.items() if k in Attempt.__dataclass_fields__})
            a.answers = [tuple(x) for x in a.answers]
            if quiz_id is None or a.quiz_id == quiz_id:
                out.append(a)
        return out

    def record(self, attempt: Attempt) -> None:
        try:
            raw = json.loads(self.store.get_setting(RESULTS_KEY, "[]") or "[]")
        except Exception:
            raw = []
        raw.append(asdict(attempt))
        self.store.set_setting(RESULTS_KEY, json.dumps(raw[-2000:], ensure_ascii=False))

    def results_csv(self, quiz_id: Optional[str] = None) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["الطالب", "الاختبار", "الدرجة", "من", "النسبة", "الزمن بالثواني", "التاريخ"])
        for a in self.results(quiz_id):
            w.writerow([a.student, a.quiz_title, f"{a.score:g}", f"{a.total:g}", f"{a.percent:.1f}",
                        a.seconds, time.strftime("%Y-%m-%d %H:%M", time.localtime(a.started))])
        return buf.getvalue()

    def question_stats(self, quiz: Quiz) -> List[str]:
        """How often each question was answered correctly — where the class
        struggles."""
        attempts = self.results(quiz.id)
        lines = []
        for i, q in enumerate(quiz.questions):
            seen = [ok for a in attempts for (qi, _ans, ok) in a.answers if qi == i]
            if seen:
                pct = 100 * sum(seen) / len(seen)
                lines.append(f"السؤال {i + 1} ({q.prompt[:40]}): أجاب عنه صوابًا {pct:.0f}٪ من {len(seen)}.")
        return lines


class Runner:
    """One student taking one quiz."""

    def __init__(self, quiz: Quiz, student: str, rng: Optional[random.Random] = None):
        if not quiz.questions:
            raise ValueError("الاختبار بلا أسئلة.")
        self.quiz = quiz
        self.rng = rng or random.Random()
        self.order = list(range(len(quiz.questions)))
        if quiz.shuffle:
            self.rng.shuffle(self.order)
        self.pos = 0
        self.attempt = Attempt(quiz.id, quiz.title, student.strip() or "طالب", time.time(),
                               total=quiz.total_points)
        # options shown in a shuffled order for MCQ, mapped back on answer
        self._opt_order: Dict[int, List[int]] = {}

    @property
    def done(self) -> bool:
        return self.pos >= len(self.order)

    @property
    def index(self) -> int:
        return self.order[self.pos]

    @property
    def question(self) -> Question:
        return self.quiz.questions[self.index]

    def shown_options(self) -> List[str]:
        q = self.question
        if q.kind == "mcq":
            if self.index not in self._opt_order:
                order = list(range(len(q.options)))
                if self.quiz.shuffle:
                    self.rng.shuffle(order)
                self._opt_order[self.index] = order
            return [q.options[i] for i in self._opt_order[self.index]]
        if q.kind == "tf":
            return ["صح", "خطأ"]
        return []

    def time_left(self) -> Optional[int]:
        if not self.quiz.time_limit:
            return None
        return max(0, self.quiz.time_limit * 60 - self.attempt.seconds)

    def answer(self, value) -> Tuple[bool, str]:
        """``value``: shown-option index for mcq/tf, text for short answers."""
        if self.done:
            raise ValueError("انتهى الاختبار.")
        q = self.question
        if self.time_left() == 0:
            self.attempt.timed_out = True
            self.pos = len(self.order)
            return False, "انتهى الوقت."
        if q.kind == "mcq":
            real = self._opt_order.get(self.index, list(range(len(q.options))))[int(value)]
            ok = q.check(real)
            given = q.options[real]
        elif q.kind == "tf":
            ok = q.check(int(value) == 0)
            given = "صح" if int(value) == 0 else "خطأ"
        else:
            ok = q.check(str(value))
            given = str(value)
        if ok:
            self.attempt.score += q.points
        self.attempt.answers.append((self.index, given, ok))
        self.pos += 1
        fb = "صحيح." if ok else f"خطأ. الصواب: {q.correct_text()}."
        if q.explanation:
            fb += " " + q.explanation
        return ok, fb

    def finish(self) -> Attempt:
        self.attempt.finished = time.time()
        return self.attempt

    def summary(self) -> str:
        a = self.attempt
        verdict = "ناجح" if a.percent >= self.quiz.pass_mark else "لم يبلغ درجة النجاح"
        m, s = divmod(a.seconds, 60)
        return (f"{a.student}: {a.score:g} من {a.total:g} ({a.percent:.0f}٪) — {verdict}. "
                f"الزمن {m} د {s} ث." + (" انتهى الوقت قبل إكمال الأسئلة." if a.timed_out else ""))


def sample_quiz() -> Quiz:
    """A small ready quiz so a teacher can see every question type."""
    q = Quiz(uuid.uuid4().hex[:10], "اختبار تجريبي: العواصم والقواعد", "أكاديمية الكفيف العربي",
             "مثال يوضّح أنواع الأسئلة الثلاثة.", created=time.time())
    q.questions = [
        Question("mcq", "ما عاصمة جيبوتي؟", ["جيبوتي", "مقديشو", "موروني", "الخرطوم"], 0,
                 explanation="عاصمة جيبوتي مدينة جيبوتي."),
        Question("tf", "اللام في كلمة الشمس قمرية.", truth=False,
                 explanation="الشين حرف شمسي، فاللام شمسية."),
        Question("short", "اكتب جمع كلمة كتاب.", answers=["كتب", "كُتُب"],
                 explanation="جمع كتاب: كتب."),
        Question("mcq", "أيّ الكتابات صحيحة؟", ["ثلاثة كتب", "ثلاث كتب", "ثلاثة كتاب"], 0,
                 explanation="العدد من ٣ إلى ١٠ يخالف المعدود، وكتاب مذكّر."),
    ]
    return q
