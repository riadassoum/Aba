# -*- coding: utf-8 -*-
"""
abaAcademy.gui.planner_view
===========================

Two planners:

* **Study planner** (مخطّط المذاكرة): exams, homework, projects and goals
  with due dates and the study time each needs; خطّة اليوم spreads what
  is left over the days remaining.
* **Khatma planner** (خطّة ختم القرآن): finish the Qur'an in a chosen number
  of days by pages, juz' or ayat, with today's portion and whether you're on
  schedule.
"""

from __future__ import annotations

import datetime

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, parse_int
from ..study_hub import planner as pl
from ..quran_engine import khatma as kh
from ..tools.ar_count import count


class PlannerDialog(ToolDialog):
    TITLE = "مخطّط المذاكرة"
    SIZE = (800, 720)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.p = pl.Planner(academy.store)
        self.items = self.add_list("المهامّ (Enter للتفاصيل)", height=150, on_activate=self._details)
        self.add_buttons([("خطّة اليوم", self._today), ("سجّل دقائق مذاكرة", self._log),
                          ("أُنجزت", self._done), ("احذف", self._delete),
                          ("إظهار المنجز", self._toggle_done)], close=False)
        self.add_text("إضافة مهمّة:")
        self.titleEntry = self.add_entry("العنوان", hint="مثل: امتحان الفيزياء")
        self._kinds = list(pl.KINDS)
        self.kindChoice = self.add_choice("النوع", [pl.KINDS[k] for k in self._kinds])
        self.subjectEntry = self.add_entry("المادّة")
        self.dueEntry = self.add_entry("الموعد", hint="مثل 2026-11-03 أو 3/11 أو عدد الأيام")
        self.minutesSpin = self.add_spin("دقائق المذاكرة المطلوبة", 0, 10000, 120)
        self.minutesLog = self.add_spin("دقائق للتسجيل", 1, 600, 25)
        self.add_buttons([("أضف", self._add), ("مذاكرة الأسبوع", self._week)])
        self.add_output("التفاصيل", height=110)
        self.finish(self.items)
        self._show_done = False
        self._refresh()

    def _visible(self):
        return self.p.items(include_done=self._show_done)

    def _refresh(self, select: int = 0) -> None:
        items = self._visible()
        self._ids = [i.id for i in items]
        lines = [self.p.describe(i) for i in items] or ["لا مهامّ بعد. أضف مهمّة من الحقول أدناه."]
        self.items.Set(lines)
        self.select_index(self.items, max(0, min(len(lines) - 1, select)))

    def _current(self):
        i = self.items.GetSelection()
        if i < 0 or i >= len(getattr(self, "_ids", [])):
            raise ValueError("اختر مهمّة من القائمة.")
        item_id = self._ids[i]
        return i, next(x for x in self.p.items(include_done=True) if x.id == item_id)

    def _add(self) -> None:
        title = self.titleEntry.GetValue().strip()
        due = pl.parse_date(self.dueEntry.GetValue())
        item = self.p.add(title, due, self._kinds[self.choice_index(self.kindChoice)],
                          self.subjectEntry.GetValue(), self.minutesSpin.GetValue())
        self.titleEntry.SetValue("")
        self.dueEntry.SetValue("")
        self._refresh()
        self.show_output(f"أُضيفت: {self.p.describe(item)}")
        self.items.SetFocus()

    def _details(self) -> None:
        _, item = self._current()
        log = "، ".join(f"{d}: {m} د" for d, m in item.log[-10:]) or "لا تسجيلات بعد"
        self.show_output(f"{self.p.describe(item)}\nالسجلّ: {log}" +
                         (f"\nملاحظات: {item.notes}" if item.notes else ""))

    def _log(self) -> None:
        i, item = self._current()
        updated = self.p.log_minutes(item.id, self.minutesLog.GetValue())
        self._refresh(i)
        if updated:
            self.show_output(f"سُجّلت {count(self.minutesLog.GetValue(), 'minute')}. {self.p.describe(updated)}")

    def _done(self) -> None:
        i, item = self._current()
        self.p.set_done(item.id, not item.done)
        self._refresh(i)
        self._say("عُلّمت منجزة." if not item.done else "أُعيدت إلى المهامّ المفتوحة.")

    def _delete(self) -> None:
        i, item = self._current()
        if wx.MessageBox(f"حذف {item.title}؟", "تأكيد", wx.YES_NO | wx.NO_DEFAULT, self) != wx.YES:
            return
        self.p.delete(item.id)
        self._refresh(i)
        self._say("حُذفت.")

    def _toggle_done(self) -> None:
        self._show_done = not self._show_done
        self._refresh()
        self._say("تُعرض المهامّ المنجزة أيضًا." if self._show_done else "تُعرض المفتوحة فقط.")

    def _today(self) -> None:
        lines = self.p.today_plan()
        self.show_output("\n".join(lines), speak=" ".join(lines))

    def _week(self) -> None:
        week = self.p.week_minutes()
        total = sum(week.values())
        lines = [f"{d}: {m} دقيقة" for d, m in week.items()]
        self.show_output(f"ذاكرت هذا الأسبوع {count(total, 'minute')}.\n" + "\n".join(lines),
                         speak=f"ذاكرت هذا الأسبوع {count(total, 'minute')}.")

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.items:
            self._safe(self._details)
            return True
        return False

    def instructions(self) -> str:
        return ("مخطّط المذاكرة: أضف امتحاناتك وواجباتك ومواعيدها ومدّة المذاكرة التي تحتاجها، "
                "وخطّة اليوم تقسّم الباقي على الأيام المتبقّية. سجّل دقائق مذاكرتك لكلّ مهمّة؛ "
                "وجلسات مؤقّت بومودورو بمادّة مسمّاة تُسجَّل تلقائيًّا.")


class KhatmaDialog(ToolDialog):
    TITLE = "خطّة ختم القرآن الكريم"
    SIZE = (780, 680)
    _index = None

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.ks = kh.KhatmaStore(academy.store)
        if type(self)._index is None:
            type(self)._index = kh.QuranIndex.load(self.resource_path("quran", "quran_data.json"))
        self.ix = type(self)._index
        self.statusText = self.add_output("حالة الختمة", height=120)
        self.add_buttons([("ورد اليوم", self._status), ("أتممت ورد اليوم", self._finish_today)],
                         close=False)
        surahs = [f"{s['n']}. {self._clean(s['name'])}" for s in self.ix.surahs]
        self.surahChoice = self.add_choice("وصلت في قراءتي إلى سورة", surahs)
        self.ayahEntry = self.add_entry("الآية", on_enter=self._mark)
        self.add_buttons([("سجّل موضع قراءتي", self._mark)], close=False)
        self.portions = self.add_list("أوراد الخطّة", height=150)
        self.add_text("خطّة جديدة:")
        self._units = list(kh.UNITS)
        self.unitChoice = self.add_choice("التقسيم", ["بالصفحات", "بالأجزاء", "بالآيات"])
        self._durations = kh.suggested_days()
        self.daysChoice = self.add_choice("المدّة", [l for _, l in self._durations] + ["مدّة أخرى"])
        self.daysSpin = self.add_spin("عدد الأيام (للمدّة الأخرى)", 1, 3650, 40)
        self.fromCurrent = self.add_check("ابدأ من موضعي الحالي لا من الفاتحة")
        self.add_buttons([("أنشئ الخطّة", self._create)])
        self.output = self.statusText
        self.finish(self.statusText)
        self._render()

    @staticmethod
    def _clean(name: str) -> str:
        for p in ("سُورَةُ ", "سورة "):
            if name.startswith(p):
                return name[len(p):]
        return name

    def _render(self) -> None:
        plan = self.ks.load()
        if plan is None:
            self.statusText.SetValue("لا توجد خطّة بعد. اختر التقسيم والمدّة ثم أنشئ الخطّة.")
            self.portions.Set([])
            return
        self.statusText.SetValue("\n".join(kh.status(self.ix, plan)))
        ps = kh.make_portions(self.ix, plan)
        self.portions.Set([kh.portion_text(self.ix, p) for p in ps])
        today = (datetime.date.today() - plan.start).days
        self.select_index(self.portions, max(0, min(len(ps) - 1, today)))

    def _status(self) -> None:
        plan = self.ks.load()
        if plan is None:
            self._say("لا توجد خطّة بعد.")
            return
        lines = kh.status(self.ix, plan)
        self._render()
        self.announce(" ".join(lines[1:]))

    def _finish_today(self) -> None:
        plan = self.ks.load()
        if plan is None:
            raise ValueError("أنشئ خطّة أولًا.")
        ps = kh.make_portions(self.ix, plan)
        day = (datetime.date.today() - plan.start).days
        if day < 0:
            raise ValueError("لم تبدأ الخطّة بعد.")
        p = ps[min(day, len(ps) - 1)]
        self.ks.mark_read(plan, p.end)
        self._render()
        self.announce(f"سُجّلت قراءتك حتى {self.ix.label(p.end)}. " + kh.status(self.ix, self.ks.load())[-1])

    def _mark(self) -> None:
        plan = self.ks.load()
        if plan is None:
            raise ValueError("أنشئ خطّة أولًا.")
        surah = self.choice_index(self.surahChoice) + 1
        try:
            ayah = parse_int(self.ayahEntry.GetValue())
        except ValueError:
            raise ValueError("اكتب رقم الآية.")
        g = self.ix.global_of(surah, ayah)
        if g is None:
            raise ValueError("رقم الآية خارج السورة المختارة.")
        self.ks.mark_read(plan, g)
        self._render()
        self.announce(f"سُجّل موضعك: {self.ix.label(g)}. " + kh.status(self.ix, self.ks.load())[-1])

    def _create(self) -> None:
        i = self.choice_index(self.daysChoice)
        days = self._durations[i][0] if i < len(self._durations) else self.daysSpin.GetValue()
        start = 1
        old = self.ks.load()
        if self.fromCurrent.GetValue() and old and old.last_read:
            start = min(self.ix.total, old.last_read + 1)
        if old and wx.MessageBox("ستحلّ الخطّة الجديدة محلّ الحالية. متابعة؟", "تأكيد",
                                 wx.YES_NO | wx.NO_DEFAULT, self) != wx.YES:
            return
        unit = self._units[self.choice_index(self.unitChoice)]
        self.ks.create(unit, days, datetime.date.today(), start)
        self._render()
        self.statusText.SetFocus()
        self.announce("أُنشئت الخطّة. " + kh.status(self.ix, self.ks.load())[2])

    def instructions(self) -> str:
        return ("خطّة الختمة: أنشئ خطّة بالمدّة والتقسيم الذي تريد، فيظهر لك ورد كلّ يوم من آية "
                "إلى آية. سجّل موضع قراءتك أو أتممت ورد اليوم، لتعرف هل أنت على الخطّة.")
