# -*- coding: utf-8 -*-
"""
abaAcademy.gui.quiz_builder_view
================================

The teacher's quiz builder and the student's quiz screen.
"""

from __future__ import annotations

import io
import os

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog
from ..teacher import quiz_builder as qb
from ..tools.ar_count import count


class QuizBuilderDialog(ToolDialog):
    TITLE = "منشئ الاختبارات (للمعلّم)"
    SIZE = (820, 760)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.qs = qb.QuizStore(academy.store)
        self.quizzes = self.add_list("الاختبارات", height=110, on_select=self._load_quiz)
        self.titleEntry = self.add_entry("عنوان اختبار جديد", on_enter=self._new_quiz)
        self.add_buttons([("أنشئ اختبارًا", self._new_quiz), ("اختبار تجريبي جاهز", self._sample),
                          ("احذف الاختبار", self._delete_quiz), ("استورد ملفًّا", self._import),
                          ("صدّر ملفًّا", self._export)], close=False)
        self.questions = self.add_list("أسئلة الاختبار المحدّد", height=120)
        self.add_buttons([("احذف السؤال", self._delete_question), ("ابدأ الاختبار", self._take),
                          ("النتائج", self._results), ("صدّر النتائج CSV", self._export_results)],
                         close=False)
        self.add_text("إضافة سؤال:")
        self._kinds = list(qb.KINDS)
        self.kindChoice = self.add_choice("نوع السؤال", [qb.KINDS[k] for k in self._kinds])
        self.prompt = self.add_entry("نصّ السؤال")
        self.optionsEntry = self.add_entry("الخيارات (كلّ خيار في سطر، الأوّل هو الصحيح) أو الإجابات المقبولة",
                                           multiline=True, height=70)
        self.truthChoice = self.add_choice("لسؤال صح أم خطأ: الجواب", ["صح", "خطأ"])
        self.explain = self.add_entry("الشرح بعد الإجابة (اختياري)")
        self.add_buttons([("أضف السؤال", self._add_question)])
        self.add_output("ملاحظات", height=80)
        self.finish(self.quizzes)
        self._refresh()

    # -- helpers ---------------------------------------------------------
    def _refresh(self, select_id: str = "") -> None:
        self._all = self.qs.all()
        self.quizzes.Set([f"{q.title} — {count(len(q.questions), 'question')}" for q in self._all]
                         or ["لا اختبارات بعد."])
        idx = next((i for i, q in enumerate(self._all) if q.id == select_id), 0)
        self.select_index(self.quizzes, idx)
        self._load_quiz()

    def _current(self):
        i = self.quizzes.GetSelection()
        if i < 0 or i >= len(getattr(self, "_all", [])):
            raise ValueError("اختر اختبارًا أو أنشئ واحدًا.")
        return self._all[i]

    def _load_quiz(self) -> None:
        try:
            q = self._current()
        except ValueError:
            self.questions.Set([])
            return
        lines = []
        for i, x in enumerate(q.questions, 1):
            lines.append(f"{i}. ({qb.KINDS[x.kind]}) {x.prompt} — الجواب: {x.correct_text()}")
        self.questions.Set(lines or ["لا أسئلة بعد. أضفها من الحقول أدناه."])
        self.select_index(self.questions, 0)

    # -- quizzes ---------------------------------------------------------
    def _new_quiz(self) -> None:
        q = self.qs.create(self.titleEntry.GetValue(), self.setting("teacher_name", ""))
        self.titleEntry.SetValue("")
        self._refresh(q.id)
        self.prompt.SetFocus()
        self._say(f"أُنشئ {q.title}. أضف الأسئلة الآن.")

    def _sample(self) -> None:
        q = qb.sample_quiz()
        self.qs.save_quiz(q)
        self._refresh(q.id)
        self._say("أُضيف الاختبار التجريبي.")

    def _delete_quiz(self) -> None:
        q = self._current()
        if wx.MessageBox(f"حذف الاختبار {q.title}؟", "تأكيد", wx.YES_NO | wx.NO_DEFAULT, self) != wx.YES:
            return
        self.qs.delete(q.id)
        self._refresh()
        self._say("حُذف.")

    def _add_question(self) -> None:
        quiz = self._current()
        kind = self._kinds[self.choice_index(self.kindChoice)]
        lines = [l.strip() for l in self.optionsEntry.GetValue().splitlines() if l.strip()]
        q = qb.Question(kind, self.prompt.GetValue().strip(), explanation=self.explain.GetValue().strip())
        if kind == "mcq":
            q.options = lines
            q.correct = 0
        elif kind == "tf":
            q.truth = self.choice_index(self.truthChoice) == 0
        else:
            q.answers = lines
        q.validate()
        quiz.questions.append(q)
        self.qs.save_quiz(quiz)
        for c in (self.prompt, self.optionsEntry, self.explain):
            c.SetValue("")
        self._refresh(quiz.id)
        self.prompt.SetFocus()
        self._say(f"أُضيف السؤال {len(quiz.questions)}.")

    def _delete_question(self) -> None:
        quiz = self._current()
        i = self.questions.GetSelection()
        if i < 0 or i >= len(quiz.questions):
            raise ValueError("اختر سؤالًا.")
        del quiz.questions[i]
        self.qs.save_quiz(quiz)
        self._refresh(quiz.id)
        self._say("حُذف السؤال.")

    def _import(self) -> None:
        with wx.FileDialog(self, "استورد اختبارًا", wildcard=f"اختبارات (*{qb.FILE_EXT})|*{qb.FILE_EXT}|كلّ الملفات|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        with io.open(path, encoding="utf-8-sig") as f:
            quiz = self.qs.import_quiz(f.read())
        self._refresh(quiz.id)
        self._say(f"استُورد {quiz.title} وفيه {count(len(quiz.questions), 'question')}.")

    def _export(self) -> None:
        quiz = self._current()
        with wx.FileDialog(self, "صدّر الاختبار", wildcard=f"اختبارات (*{qb.FILE_EXT})|*{qb.FILE_EXT}",
                           defaultFile=quiz.title + qb.FILE_EXT,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(quiz.to_json())
        self._say(f"صُدّر إلى {os.path.basename(path)}. أرسله لطلابك ليستوردوه.")

    # -- running and results ---------------------------------------------
    def _take(self) -> None:
        quiz = self._current()
        if not quiz.questions:
            raise ValueError("أضف أسئلة أولًا.")
        self.show_child(QuizTakeDialog(self, self.academy, self.speech, quiz))
        self._refresh(quiz.id)

    def _results(self) -> None:
        quiz = self._current()
        res = self.qs.results(quiz.id)
        if not res:
            self.show_output("لا نتائج بعد لهذا الاختبار.")
            return
        lines = [f"{a.student}: {a.score:g} من {a.total:g} ({a.percent:.0f}٪)" for a in res[-30:]]
        avg = sum(a.percent for a in res) / len(res)
        lines.append(f"المتوسّط {avg:.0f}٪ من {count(len(res), 'case')}.")
        lines += self.qs.question_stats(quiz)
        self.show_output("\n".join(lines), speak=lines[-1] if len(lines) == 1 else
                         f"المتوسّط {avg:.0f}٪. التفاصيل في الملاحظات.", focus=True)

    def _export_results(self) -> None:
        quiz = self._current()
        with wx.FileDialog(self, "صدّر النتائج", wildcard="CSV (*.csv)|*.csv",
                           defaultFile=quiz.title + " - النتائج.csv",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(self.qs.results_csv(quiz.id))
        self._say("صُدّرت النتائج.")

    def instructions(self) -> str:
        return ("منشئ الاختبارات: أنشئ اختبارًا، وأضف أسئلة اختيار من متعدّد (الخيار الأوّل هو الصحيح "
                "ويُخلط عند العرض) أو صح وخطأ أو إجابة قصيرة. صدّره ملفًّا لطلابك، وتابع نتائجهم.")


class QuizTakeDialog(ToolDialog):
    TITLE = "حلّ الاختبار"
    SIZE = (720, 560)

    def __init__(self, parent, academy, speech, quiz: qb.Quiz):
        super().__init__(parent, academy, speech, title=quiz.title)
        self.quiz = quiz
        self.qs = qb.QuizStore(academy.store)
        self.runner = None
        self.nameEntry = self.add_entry("اسم الطالب", self.setting("student_name", "") or
                                        (self.academy.store.get_setting("user_name", "") or ""),
                                        on_enter=self._start)
        self.add_buttons([("ابدأ", self._start)], close=False)
        self.prompt = self.add_text(quiz.description or "اكتب اسمك ثم ابدأ.")
        self.options = self.add_list("الخيارات", height=140)
        self.answer = self.add_entry("إجابتك (للأسئلة القصيرة)", on_enter=self._submit)
        self.add_buttons([("أجب", self._submit), ("الوقت المتبقّي", self._time)])
        self.add_output("النتيجة", height=90)
        self.finish(self.nameEntry)

    def _start(self) -> None:
        name = self.nameEntry.GetValue().strip()
        if not name:
            raise ValueError("اكتب اسمك.")
        self.set_setting("student_name", name)
        self.runner = qb.Runner(self.quiz, name)
        limit = (f" مدّته {count(self.quiz.time_limit, 'minute')}." if self.quiz.time_limit else "")
        self.announce(f"يبدأ الاختبار: {count(len(self.quiz.questions), 'question')}.{limit}")
        self._show()

    def _show(self) -> None:
        r = self.runner
        if r.done:
            self._finish()
            return
        q = r.question
        n = r.pos + 1
        self.prompt.SetLabel(f"السؤال {n}: {q.prompt}")
        opts = r.shown_options()
        self.options.Set(opts)
        self.select_index(self.options, 0)
        if q.kind == "short":
            self.answer.SetValue("")
            self.answer.SetFocus()
            self.announce(f"السؤال {n} من {len(r.order)}: {q.prompt} اكتب إجابتك.")
        else:
            self.options.SetFocus()
            self.announce(f"السؤال {n} من {len(r.order)}: {q.prompt} الخيارات: " + "، ".join(opts))

    def _submit(self) -> None:
        r = self.runner
        if r is None:
            self._start()
            return
        if r.done:
            return
        q = r.question
        if q.kind == "short":
            text = self.answer.GetValue().strip()
            if not text:
                raise ValueError("اكتب إجابة.")
            ok, fb = r.answer(text)
        else:
            i = self.options.GetSelection()
            if i < 0:
                raise ValueError("اختر إجابة.")
            ok, fb = r.answer(i)
        self.announce(fb)
        self.call_later(1200, self._show)

    def _finish(self) -> None:
        a = self.runner.finish()
        self.qs.record(a)
        self.options.Set([])
        self.show_output(self.runner.summary())

    def _time(self) -> None:
        if self.runner is None:
            self._say("لم يبدأ الاختبار.")
            return
        t = self.runner.time_left()
        self._say("لا وقت محدّد لهذا الاختبار." if t is None else f"بقي {count(t // 60, 'minute')} و{count(t % 60, 'second')}.")

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.options:
            self._safe(self._submit)
            return True
        return False

    def instructions(self) -> str:
        return "اكتب اسمك وابدأ. اختر الإجابة بالأسهم وEnter، أو اكتبها في الأسئلة القصيرة."


class WeeklyReportDialog(ToolDialog):
    TITLE = "التقرير الأسبوعي"
    SIZE = (760, 600)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.add_output("التقرير", height=380)
        self.add_buttons([("حدّث", self._build), ("احفظه صفحة HTML", self._save)])
        self.finish(self.output)
        self._build(quiet=True)

    def _index(self):
        try:
            from ..quran_engine.khatma import QuranIndex
            from .planner_view import KhatmaDialog
            if KhatmaDialog._index is None:
                KhatmaDialog._index = QuranIndex.load(self.resource_path("quran", "quran_data.json"))
            return KhatmaDialog._index
        except Exception:
            return None

    def _build(self, quiet: bool = False) -> None:
        from ..study_hub import weekly_report as wr
        t = wr.text(self.academy.store, quran_index=self._index()) or "لا بيانات بعد هذا الأسبوع."
        self.output.SetValue(t)
        if not quiet:
            self.announce(t.split("\n", 2)[1] if "\n" in t else t)

    def _save(self) -> None:
        from ..study_hub import weekly_report as wr
        name = self.academy.store.get_setting("user_name", "") or ""
        with wx.FileDialog(self, "احفظ التقرير", wildcard="HTML (*.html)|*.html",
                           defaultFile="التقرير الأسبوعي.html",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(wr.to_html(self.academy.store, name, quran_index=self._index()))
        self._say("حُفظ التقرير.")

    def instructions(self) -> str:
        return ("ملخّص أسبوعك: المذاكرة والتركيز والختمة والأذكار والمهارات والاختبارات والألعاب. "
                "تنقّل في التقرير بالأسهم، واحفظه صفحة يفتحها وليّ الأمر أو المعلّم.")
