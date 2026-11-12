# -*- coding: utf-8 -*-
"""
abaAcademy.gui.daily_tools_view
===============================

Screens for the Arab countries explorer, school arithmetic (fractions,
percentages, Roman numerals, English number words), the times-tables drill
and the tasbih counter.
"""

from __future__ import annotations

import random
import time

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, ChoiceQuiz, parse_float, parse_int
from ..science import arab_countries as ac
from ..math_engine import arithmetic as ar
from ..tools import tasbih
from ..tools.ar_count import count


class CountriesDialog(ToolDialog):
    TITLE = "الدول العربية (العواصم والعملات)"
    SIZE = (780, 660)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._regions = ["كلّ الدول"] + ac.regions()
        self.regionChoice = self.add_choice("الإقليم", self._regions, on_change=self._fill)
        self.list = self.add_list("الدول (Enter للبطاقة)", height=170, on_activate=self._card)
        self.searchEntry = self.add_entry("ابحث بالدولة أو العاصمة", on_enter=self._search)
        self._kinds = list(ac.QUIZ_KINDS)
        self.kindChoice = self.add_choice("نوع السؤال", [ac.QUIZ_KINDS[k] for k in self._kinds] + ["متنوّع"],
                                          len(self._kinds))
        self.prompt = self.add_text("اضغط سؤال جديد.")
        self.options = self.add_list("الخيارات", height=100)
        self._rng = random.Random()
        self.quiz = ChoiceQuiz(self, self.options, self._make, prompt_ctrl=self.prompt)
        self.add_buttons([("سؤال جديد", self.quiz.next), ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.add_output("البطاقة", height=80)
        self.finish(self.list)
        self._fill()

    def _pool(self):
        i = self.choice_index(self.regionChoice)
        return list(ac.COUNTRIES) if i == 0 else ac.in_region(self._regions[i])

    def _fill(self) -> None:
        self._shown = self._pool()
        self.list.Set([f"{c.name}: {c.capital}" for c in self._shown])
        self.select_index(self.list, 0)

    def _card(self) -> None:
        i = self.list.GetSelection()
        if 0 <= i < len(self._shown):
            self.show_output(ac.describe(self._shown[i]))

    def _search(self) -> None:
        c = ac.find(self.searchEntry.GetValue())
        if c is None:
            raise ValueError("لم أجد دولة عربية بهذا الاسم أو العاصمة.")
        self.regionChoice.SetSelection(0)
        self._fill()
        self.select_index(self.list, self._shown.index(c))
        self.list.SetFocus()
        self.show_output(ac.describe(c))

    def _make(self):
        k = self.choice_index(self.kindChoice)
        kind = self._kinds[k] if k < len(self._kinds) else self._rng.choice(self._kinds)
        return ac.make_question(kind, self._rng, self._pool())

    def on_enter_key(self) -> bool:
        f = self.FindFocus()
        if f is self.list:
            self._card()
            return True
        if f is self.options:
            self.quiz.answer()
            return True
        return False

    def instructions(self) -> str:
        return ("الدول العربية الاثنتان والعشرون: تنقّل في القائمة واضغط Enter لبطاقة الدولة بعاصمتها "
                "وإقليمها وعملتها ورمز اتصالها. واختبر نفسك بالأسئلة، مع إمكان حصرها في إقليم.")


class ArithmeticDialog(ToolDialog):
    TITLE = "الكسور والنسب المئوية والأرقام الرومانية"
    SIZE = (780, 700)
    _OPS = [("+", "جمع"), ("-", "طرح"), ("×", "ضرب"), ("÷", "قسمة")]
    _PCT = [("of", "نسبة من عدد"), ("what", "كم نسبة الأوّل من الثاني"), ("change", "نسبة التغيّر"),
            ("discount", "السعر بعد الخصم"), ("simple", "الفائدة البسيطة (العدد، النسبة، السنوات)"),
            ("compound", "الفائدة المركّبة (العدد، النسبة، السنوات)")]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.fa = self.add_entry("الكسر الأول (مثل 3/4 أو 2 1/3)", "2 1/3")
        self.opChoice = self.add_choice("العملية", [l for _, l in self._OPS])
        self.fb = self.add_entry("الكسر الثاني", "3/4", on_enter=self._fraction)
        self.add_buttons([("احسب الكسرين", self._fraction)], close=False)
        self.pctChoice = self.add_choice("حساب النسبة", [l for _, l in self._PCT])
        self.p1 = self.add_entry("العدد الأول", "200")
        self.p2 = self.add_entry("العدد الثاني", "15")
        self.p3 = self.add_entry("العدد الثالث (للفائدة)", "2")
        self.add_buttons([("احسب النسبة", self._percent)], close=False)
        self.numEntry = self.add_entry("عدد أو رقم روماني", "2026", on_enter=self._roman)
        self.add_buttons([("حوّل روماني", self._roman), ("بالكلمات الإنجليزية", self._english)])
        self.add_output("الخطوات", height=150)
        self.finish(self.fa)

    def _fraction(self) -> None:
        op = self._OPS[self.choice_index(self.opChoice)][0]
        res, steps = ar.fraction_op(self.fa.GetValue(), op, self.fb.GetValue())
        self.show_output("\n".join(steps), speak=f"الناتج {ar.speak(res)}.")

    def _nums(self, n):
        out = []
        for ctrl in (self.p1, self.p2, self.p3)[:n]:
            try:
                out.append(parse_float(ctrl.GetValue()))
            except ValueError:
                raise ValueError("اكتب الأعداد المطلوبة أرقامًا.")
        return out

    def _percent(self) -> None:
        kind = self._PCT[self.choice_index(self.pctChoice)][0]
        if kind == "of":
            a, b = self._nums(2)
            text = ar.percent_of(b, a)
        elif kind == "what":
            a, b = self._nums(2)
            text = ar.what_percent(a, b)
        elif kind == "change":
            a, b = self._nums(2)
            text = ar.change(a, b)
        elif kind == "discount":
            a, b = self._nums(2)
            text = ar.discount(a, b)
        else:
            a, b, c = self._nums(3)
            text = ar.interest(a, b, c, kind == "compound")
        self.show_output(text)

    def _roman(self) -> None:
        t = self.numEntry.GetValue().strip()
        if t and t[0].isalpha():
            n = ar.from_roman(t)
            self.show_output(f"{t.upper()} = {n}")
        else:
            n = parse_int(t)
            self.show_output("\n".join(ar.roman_steps(n)), speak=f"{n} بالرومانية {' '.join(ar.to_roman(n))}")

    def _english(self) -> None:
        n = parse_int(self.numEntry.GetValue())
        self.show_output(f"{n}: {ar.english_words(n)}\nالترتيبي: {ar.english_ordinal(n)}")

    def instructions(self) -> str:
        return ("احسب بالكسور والأعداد الكسرية مع الخطوات، والنسب المئوية والخصومات والفوائد، "
                "وحوّل بين الأعداد والأرقام الرومانية، واكتب الأعداد بالكلمات الإنجليزية.")


class TimesTablesDialog(ToolDialog):
    TITLE = "تدريب جدول الضرب"
    SIZE = (680, 520)
    SETTINGS_PREFIX = "times_"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        import json
        try:
            weights = json.loads(self.setting("weights", "{}") or "{}")
        except Exception:
            weights = {}
        self._tables = [list(range(2, 10)), list(range(2, 6)), list(range(6, 10)), list(range(2, 13))]
        self.tableChoice = self.add_choice("الجداول", ["من ٢ إلى ٩", "من ٢ إلى ٥", "من ٦ إلى ٩", "من ٢ إلى ١٢"],
                                           on_change=self._reset)
        self.tt = ar.TimesTables(self._tables[0], weights=weights)
        self.q = self.add_text("اضغط ابدأ.")
        self.answer = self.add_entry("الجواب", on_enter=self._check)
        self.add_buttons([("ابدأ", self._next), ("أضعف الحقائق عندي", self._weak)])
        self.add_output("النتيجة", height=90)
        self.finish(self.tableChoice)
        self._right = self._total = 0
        self._t0 = 0.0

    def _reset(self) -> None:
        self.tt.tables = self._tables[self.choice_index(self.tableChoice)]

    def _next(self) -> None:
        a, b = self.tt.next()
        self.q.SetLabel(f"{a} × {b} = ؟")
        self.answer.SetValue("")
        self.answer.SetFocus()
        self._t0 = time.monotonic()
        self.announce(f"{a} في {b}")

    def _check(self) -> None:
        if self.tt.current is None:
            self._next()
            return
        secs = time.monotonic() - self._t0
        ok, right = self.tt.answer(self.answer.GetValue(), secs)
        self._total += 1
        self._right += ok
        import json
        self.set_setting("weights", json.dumps(self.tt.weights))
        msg = ("صحيح. " if ok else f"الجواب {right}. ") + f"{self._right} من {self._total}."
        self.output.SetValue(msg)
        self.announce(msg)
        self._next()

    def _weak(self) -> None:
        w = self.tt.weakest()
        self._say("أضعف الحقائق: " + "، ".join(w) if w else "لا حقائق ضعيفة بعد. أحسنت!")

    def instructions(self) -> str:
        return ("اكتب ناتج الضرب واضغط Enter، فيأتيك السؤال التالي. الحقائق التي تخطئ فيها أو تبطئ "
                "تعود أكثر حتى تتقنها، ويُحفظ ذلك بين الجلسات.")


class TasbihDialog(ToolDialog):
    TITLE = "المسبحة"
    SIZE = (640, 480)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.c = tasbih.load(academy.store)
        self._seqs = list(tasbih.SEQUENCES)
        self.seqChoice = self.add_choice("الذكر", [tasbih.SEQUENCES[k][0] for k in self._seqs],
                                         self._seqs.index(self.c.sequence), on_change=self._change)
        self.add_text("اضغط المسافة أو Enter على زرّ العدّ لكلّ تسبيحة. يُعلن كلّ عشر وقرب الهدف.")
        self.status = self.add_text(self.c.status())
        self.tapBtn = self.add_buttons([("سبّح", self._tap), ("تراجع", self._undo), ("من جديد", self._restart),
                                        ("مجموع اليوم", self._today)])[0]
        self.finish(self.tapBtn)

    def _save(self) -> None:
        try:
            tasbih.save(self.academy.store, self.c)
        except Exception:
            pass

    def _tap(self) -> None:
        msg = self.c.tap()
        self.status.SetLabel(self.c.status())
        if msg:
            self.announce(msg)
        self._save()

    def _undo(self) -> None:
        self.c.undo()
        self.status.SetLabel(self.c.status())
        self._say(self.c.status())
        self._save()

    def _restart(self) -> None:
        self.c.reset()
        self.status.SetLabel(self.c.status())
        self._say(self.c.status())
        self._save()

    def _change(self) -> None:
        self.c.reset(self._seqs[self.choice_index(self.seqChoice)])
        self.status.SetLabel(self.c.status())
        self._save()

    def _today(self) -> None:
        self._say(f"سبّحت اليوم {count(self.c.today_total(), 'time')}.")

    def on_enter_key(self) -> bool:
        return False

    def instructions(self) -> str:
        return ("المسبحة: اختر الذكر، ثم اضغط زرّ سبّح بالمسافة لكلّ مرّة. أذكار ما بعد الصلاة "
                "تنتقل تلقائيًّا من التسبيح إلى التحميد إلى التكبير ثم تمام المئة.")


class ClockDialog(ToolDialog):
    TITLE = "الساعة الناطقة والمؤقّتات"
    SIZE = (740, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from ..tools import clock
        self.clock = clock
        self.sw = clock.Stopwatch()
        self.cd = clock.Countdown()
        self.add_buttons([("كم الساعة؟", self._time), ("ما التاريخ؟", self._date),
                          ("الوقت في المدن", self._world)], close=False)
        self.twelve = self.add_check("نظام الاثنتي عشرة ساعة", True)
        self.add_text("ساعة الإيقاف:")
        self.swText = self.add_text("00:00")
        self.add_buttons([("ابدأ/أوقف", self._sw_toggle), ("لفّة", self._lap), ("كم مضى؟", self._sw_say),
                          ("صفّر", self._sw_reset)], close=False)
        self.add_text("العدّ التنازلي:")
        self.cdEntry = self.add_entry("المدّة (دقائق، أو د:ث مثل 1:30)", "5", on_enter=self._cd_start)
        self.cdText = self.add_text("")
        self.add_buttons([("ابدأ", self._cd_start), ("أوقف مؤقّتًا", self._cd_pause), ("كم بقي؟", self._cd_say)])
        self.add_output("التفاصيل", height=150)
        self.finish(self.cdEntry)
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._tick, self._timer)
        self._timer.Start(250)

    def _tick(self, evt) -> None:
        self.swText.SetLabel(self.clock.clock_text(self.sw.elapsed()))
        if self.cd.running or self.cd.remaining() > 0:
            self.cdText.SetLabel(self.clock.clock_text(self.cd.remaining()))
        msg = self.cd.tick()
        if msg:
            self.announce(msg)
            if msg == "انتهى الوقت!":
                self.play_tones([(880, 0.2, 0.1), (880, 0.2, 0.1), (1175, 0.4, 0)])

    def _time(self) -> None:
        import datetime
        self._say(self.clock.spoken_time(datetime.datetime.now(), self.twelve.GetValue()))

    def _date(self) -> None:
        import datetime
        self._say(self.clock.spoken_date(datetime.date.today()))

    def _world(self) -> None:
        self.show_output("\n".join(self.clock.world_times()), speak="الأوقات في مربّع التفاصيل.", focus=True)

    def _sw_toggle(self) -> None:
        if self.sw.running:
            self.sw.stop()
            self._say("أوقفت. " + self.clock.spoken_duration(self.sw.elapsed(), True))
        else:
            self.sw.start()
            self._say("بدأت ساعة الإيقاف.")

    def _lap(self) -> None:
        n, lap, total = self.sw.lap()
        line = f"اللفّة {n}: {self.clock.spoken_duration(lap, True)}، والمجموع {self.clock.spoken_duration(total, True)}."
        self.output.AppendText(line + "\n")
        self._say(line)

    def _sw_say(self) -> None:
        self._say(self.clock.spoken_duration(self.sw.elapsed(), True))

    def _sw_reset(self) -> None:
        self.sw.reset()
        self.swText.SetLabel("00:00")
        self._say("صُفّرت.")

    def _cd_start(self) -> None:
        if not self.cd.running and self.cd.remaining() <= 0 or self.cdEntry.IsModified():
            self.cd.set(self.clock.parse_duration(self.cdEntry.GetValue()))
            self.cdEntry.SetModified(False)
        self.cd.start()
        self._say("بدأ العدّ: " + self.clock.spoken_duration(self.cd.remaining()))

    def _cd_pause(self) -> None:
        self.cd.pause()
        self._say("أُوقف العدّ مؤقّتًا. " + self.clock.spoken_duration(self.cd.remaining()))

    def _cd_say(self) -> None:
        self._say("بقي " + self.clock.spoken_duration(self.cd.remaining()))

    def on_closing(self) -> None:
        try:
            self._timer.Stop()
        except Exception:
            pass
        super().on_closing()

    def instructions(self) -> str:
        return ("الساعة الناطقة: اسأل عن الوقت والتاريخ بالميلادي والهجري. ساعة إيقاف بلفّات، "
                "وعدّ تنازلي يعلن الدقائق الأخيرة والثواني الخمس ويصدر تنبيهًا عند انتهائه.")


class ResistorsDialog(ToolDialog):
    TITLE = "دوائر المقاومات (توالٍ وتوازٍ)"
    SIZE = (720, 560)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.rs = self.add_entry("المقاومات بالأوم (مفصولة بمسافات، تُقبل k)", "100 200 1k")
        self.arrChoice = self.add_choice("طريقة التوصيل", ["على التوالي", "على التوازي"])
        self.volt = self.add_entry("جهد المصدر بالفولت", "12", on_enter=self._calc)
        self.add_buttons([("احسب", self._calc)])
        self.add_output("الحلّ", height=200)
        self.finish(self.rs)

    def _calc(self) -> None:
        from ..science import physics as ph
        rs = ph.parse_resistors(self.rs.GetValue())
        try:
            v = parse_float(self.volt.GetValue())
        except ValueError:
            raise ValueError("اكتب الجهد رقمًا.")
        arr = "series" if self.choice_index(self.arrChoice) == 0 else "parallel"
        lines = ph.circuit_report(rs, v, arr)
        self.show_output("\n".join(lines), speak=" ".join(lines[:3]))

    def instructions(self) -> str:
        return ("اكتب قيم المقاومات واختر التوصيل والجهد، لتسمع المقاومة المكافئة والتيار والجهد "
                "على كلّ مقاومة والقدرة.")
