# -*- coding: utf-8 -*-
"""
abaAcademy.gui.flashcards_view
==============================

The flashcard screens (Arabic, right-to-left, self-voicing):

* a home screen showing how many cards are due and letting the learner start a
  review, manage cards, or add a new one;
* a review screen — the front is announced, Space/Enter reveals the back, then
  the learner rates recall (تذكرت / بصعوبة / نسيت) and FSRS schedules the next
  showing;
* a simple manager to add, edit and delete cards.

Designed for Arab students: every label and message is Arabic, decks default to
عام, and cards suit Arabic vocabulary, Qur'an, or foreign-word study.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog


class _CardEditor(AccessibleDialog):
    def __init__(self, parent, speech, decks, card=None):
        super().__init__(parent, "بطاقة جديدة" if card is None else "تعديل البطاقة",
                         speech, size=(560, 420))
        self.result = None
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)

        s.Add(wx.StaticText(panel, label="الوجه الأمامي (السؤال/الكلمة):"), 0, wx.ALL, 4)
        self.front = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 60),
                                 value=(card or {}).get("front", ""))
        self.front.SetName("الوجه الأمامي")
        s.Add(self.front, 0, wx.EXPAND | wx.ALL, 4)

        s.Add(wx.StaticText(panel, label="الوجه الخلفي (الجواب/المعنى):"), 0, wx.ALL, 4)
        self.back = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 60),
                                value=(card or {}).get("back", ""))
        self.back.SetName("الوجه الخلفي")
        s.Add(self.back, 0, wx.EXPAND | wx.ALL, 4)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label="المجموعة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.deck = wx.ComboBox(panel, choices=decks or ["عام"],
                                value=(card or {}).get("deck", "عام"))
        self.deck.SetName("اسم المجموعة")
        row.Add(self.deck, 1, wx.ALL, 4)
        s.Add(row, 0, wx.EXPAND)

        s.Add(wx.StaticText(panel, label="تلميح (اختياري):"), 0, wx.ALL, 4)
        self.hint = wx.TextCtrl(panel, value=(card or {}).get("hint", ""))
        self.hint.SetName("تلميح اختياري")
        s.Add(self.hint, 0, wx.EXPAND | wx.ALL, 4)

        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "حفظ", self._on_save), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إلغاء", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(b, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.front)

    def _on_save(self, evt):
        f, bk = self.front.GetValue().strip(), self.back.GetValue().strip()
        if not f or not bk:
            self.announce("يجب تعبئة الوجهين الأمامي والخلفي.")
            return
        self.result = {"front": f, "back": bk,
                       "deck": self.deck.GetValue().strip() or "عام",
                       "hint": self.hint.GetValue().strip()}
        self.close_screen()

    def instructions(self):
        return "اكتب الوجه الأمامي والخلفي واسم المجموعة، ثم احفظ. Escape للإلغاء."


class ReviewScreen(AccessibleDialog):
    def __init__(self, parent, academy, speech, cards, deck_label):
        super().__init__(parent, f"مراجعة البطاقات — {deck_label}", speech, size=(620, 460))
        self.academy = academy
        self.cards = cards
        self.i = 0
        self.revealed = False
        self._start_t = None

        panel = wx.Panel(self)
        self._panel = panel
        s = wx.BoxSizer(wx.VERTICAL)
        self.progress = wx.StaticText(panel, label="")
        s.Add(self.progress, 0, wx.ALL, 6)
        self.card_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
                                     size=(-1, 200))
        self.card_text.SetName("نص البطاقة")
        try:
            self.card_text.SetLayoutDirection(wx.Layout_RightToLeft)
        except Exception:
            pass
        s.Add(self.card_text, 1, wx.EXPAND | wx.ALL, 6)

        self.revealBtn = self.button(panel, "أظهر الجواب (مسافة)", lambda e: self._reveal())
        s.Add(self.revealBtn, 0, wx.EXPAND | wx.ALL, 4)

        self.rateBox = wx.BoxSizer(wx.HORIZONTAL)
        self.gotBtn = self.button(panel, "تذكّرت (1)", lambda e: self._rate(True, 3.0))
        self.hardBtn = self.button(panel, "بصعوبة (2)", lambda e: self._rate(True, 10.0))
        self.missBtn = self.button(panel, "نسيت (3)", lambda e: self._rate(False, 12.0))
        for b in (self.gotBtn, self.hardBtn, self.missBtn):
            self.rateBox.Add(b, 0, wx.ALL, 4)
            b.Enable(False)
        s.Add(self.rateBox, 0, wx.ALIGN_RIGHT)
        s.Add(self.button(panel, "إنهاء", lambda e: self.close_screen()), 0, wx.ALIGN_RIGHT | wx.ALL, 4)

        panel.SetSizer(s)
        self.card_text.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.set_first_control(self.card_text)
        self._show()

    def _current(self):
        return self.cards[self.i] if self.i < len(self.cards) else None

    def _show(self):
        import time
        c = self._current()
        if not c:
            self.announce("انتهت مراجعة البطاقات المستحقة. أحسنت!")
            self.card_text.SetValue("انتهت المراجعة.")
            self.revealBtn.Enable(False)
            for b in (self.gotBtn, self.hardBtn, self.missBtn):
                b.Enable(False)
            return
        self.revealed = False
        self._start_t = time.time()
        self.progress.SetLabel(f"البطاقة {self.i + 1} من {len(self.cards)}")
        front = c["front"] + (f"\n(تلميح: {c['hint']})" if c.get("hint") else "")
        self.card_text.SetValue(front)
        self.card_text.SetInsertionPoint(0)
        self.revealBtn.Enable(True)
        for b in (self.gotBtn, self.hardBtn, self.missBtn):
            b.Enable(False)
        self.announce(c["front"])
        self.card_text.SetFocus()

    def _reveal(self):
        c = self._current()
        if not c or self.revealed:
            return
        self.revealed = True
        self.card_text.SetValue(f"{c['front']}\n\nالجواب: {c['back']}")
        self.card_text.SetInsertionPoint(0)
        for b in (self.gotBtn, self.hardBtn, self.missBtn):
            b.Enable(True)
        self.announce(f"الجواب: {c['back']}. قيّم تذكّرك: تذكّرت، بصعوبة، أو نسيت.")

    def _rate(self, correct, elapsed):
        import time
        c = self._current()
        if not c or not self.revealed:
            return
        el = time.time() - (self._start_t or time.time())
        # use the button's implied difficulty but cap by real elapsed
        self.academy.flashcards.grade(c["id"], correct, min(max(el, 1.0), elapsed))
        self.i += 1
        self._show()

    def _on_key(self, evt):
        code = evt.GetKeyCode()
        if not self.revealed and code in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._reveal()
        elif self.revealed and code in (ord('1'), wx.WXK_NUMPAD1):
            self._rate(True, 3.0)
        elif self.revealed and code in (ord('2'), wx.WXK_NUMPAD2):
            self._rate(True, 10.0)
        elif self.revealed and code in (ord('3'), wx.WXK_NUMPAD3):
            self._rate(False, 12.0)
        else:
            evt.Skip()

    def instructions(self):
        return ("يُقرأ وجه البطاقة. اضغط المسافة لإظهار الجواب، ثم قيّم تذكّرك: 1 تذكّرت، "
                "2 بصعوبة، 3 نسيت. تُجدوَل البطاقة تلقائياً حسب تذكّرك. Escape للإنهاء.")


class ManageScreen(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "إدارة البطاقات", speech, size=(680, 520))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.listBox.SetName("قائمة البطاقات")
        s.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 6)
        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "إضافة", lambda e: self._add()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "تعديل", lambda e: self._edit()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "حذف", lambda e: self._delete()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(b, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self._reload()
        self.set_first_control(self.listBox)

    def _reload(self):
        self._cards = self.academy.flashcards.all_cards()
        self.listBox.Set([f"[{c.get('deck','عام')}] {c['front']} ← {c['back']}" for c in self._cards])
        if self._cards:
            self.select_index(self.listBox, 0)

    def _sel(self):
        i = self.listBox.GetSelection()
        return self._cards[i] if i != wx.NOT_FOUND else None

    def _add(self):
        dlg = _CardEditor(self, self.speech, self.academy.flashcards.decks())
        self.show_child(dlg)
        if dlg.result:
            self.academy.flashcards.add(**dlg.result)
            self.announce("تمت الإضافة.")
            self._reload()

    def _edit(self):
        c = self._sel()
        if not c:
            return
        dlg = _CardEditor(self, self.speech, self.academy.flashcards.decks(), card=c)
        self.show_child(dlg)
        if dlg.result:
            self.academy.flashcards.update(c["id"], **dlg.result)
            self.announce("تم التعديل.")
            self._reload()

    def _delete(self):
        c = self._sel()
        if not c:
            return
        if wx.MessageBox(f"حذف البطاقة: {c['front']}؟", "تأكيد",
                         wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.academy.flashcards.delete(c["id"])
            self.announce("تم الحذف.")
            self._reload()

    def instructions(self):
        return "تصفّح البطاقات بالأسهم. أضف، عدّل، أو احذف. Escape للإغلاق."


class LibraryScreen(AccessibleDialog):
    """Browse bundled starter decks (built from the courses) and add them."""

    def __init__(self, parent, academy, speech):
        super().__init__(parent, "مكتبة البطاقات الجاهزة", speech, size=(700, 540))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label="بطاقات جاهزة مبنية من دروسك (اللغات والمواد). "
                                        "اختر مجموعة وأضِفها إلى بطاقاتك."), 0, wx.ALL, 8)
        self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.listBox.SetName("قائمة المجموعات الجاهزة")
        s.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 6)
        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "أضِف هذه المجموعة", lambda e: self._add_one()), 0, wx.ALL, 4)
        self._courses = [(cid, label) for cid, label in self.COURSE_LABELS
                         if any(d.get("course") == cid for d in self.academy.flashcards.starter_index())]
        self.courseChoice = wx.Choice(panel, choices=[label for _, label in self._courses])
        self.courseChoice.SetName("المادّة أو اللغة لإضافة كل مجموعاتها")
        if self._courses:
            self.courseChoice.SetSelection(0)
        b.Add(self.courseChoice, 0, wx.ALL, 4)
        b.Add(self.button(panel, "أضِف كل مجموعات المختار", lambda e: self._add_selected_course()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(b, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self._reload()
        self.set_first_control(self.listBox)

    def _reload(self):
        self._decks = self.academy.flashcards.starter_index()
        loaded = set(self.academy.flashcards.loaded_starter_ids())
        self.listBox.Set([f"{d['name']} — {d['count']} بطاقة"
                          + ("  (مُضافة)" if d["id"] in loaded else "")
                          for d in self._decks])
        if self._decks:
            self.select_index(self.listBox, 0)

    def _add_one(self):
        i = self.listBox.GetSelection()
        if i == wx.NOT_FOUND:
            return
        d = self._decks[i]
        n = self.academy.flashcards.load_starter_deck(d["id"], d["name"])
        self.announce(f"أُضيفت {n} بطاقة من {d['name']}." if n else "هذه المجموعة مُضافة مسبقاً.")
        self._reload()

    COURSE_LABELS = [
        ("english", "الإنجليزية"), ("english_graded", "الإنجليزية بالجمل"), ("french", "الفرنسية"),
        ("french_graded", "الفرنسية بالجمل"), ("spanish", "الإسبانية"), ("turkish", "التركية"),
        ("german", "الألمانية"), ("italian", "الإيطالية"), ("science", "العلوم"), ("geography", "الجغرافيا"),
        ("arabic", "العربية"), ("history", "التاريخ"), ("general", "معلومات عامة"), ("computer", "الحاسوب"),
    ]

    def _add_selected_course(self):
        i = self.courseChoice.GetSelection()
        if i == wx.NOT_FOUND or not self._courses:
            return
        self._add_course(self._courses[i][0])

    def _add_course(self, course):
        total = 0
        for d in self._decks:
            if d.get("course") == course:
                total += self.academy.flashcards.load_starter_deck(d["id"], d["name"])
        label = dict(self.COURSE_LABELS).get(course, course)
        self.announce(f"أُضيفت {total} بطاقة من مجموعات {label}." if total
                      else f"كل مجموعات {label} مُضافة مسبقاً.")
        self._reload()

    def instructions(self):
        return ("تصفّح المجموعات الجاهزة بالأسهم وأضِف ما تريد إلى بطاقاتك، أو اختر لغة أو مادّة "
                "وأضِف كل مجموعاتها دفعةً واحدة. Escape للإغلاق.")


class FlashcardsHome(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "البطاقات التعليمية (المراجعة الذكية)", speech, size=(600, 440))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        self.summary = wx.StaticText(panel, label=self._summary())
        self.summary.Wrap(560)
        s.Add(self.summary, 0, wx.ALL, 10)

        s.Add(wx.StaticText(panel, label="اختر مجموعة للمراجعة:"), 0, wx.LEFT | wx.TOP, 8)
        self.deckChoice = wx.Choice(panel, choices=["كل المجموعات"] + self.academy.flashcards.decks())
        self.deckChoice.SetSelection(0)
        self.deckChoice.SetName("اختيار المجموعة")
        s.Add(self.deckChoice, 0, wx.EXPAND | wx.ALL, 8)

        self.startBtn = self.button(panel, "ابدأ المراجعة", lambda e: self._start())
        self.startBtn.SetDefault()
        s.Add(self.startBtn, 0, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "إضافة بطاقة", lambda e: self._quick_add()), 0, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "مكتبة البطاقات الجاهزة (اللغات والمواد)", lambda e: self._library()), 0, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "إدارة البطاقات", lambda e: self._manage()), 0, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        self.set_first_control(self.startBtn)

    def _summary(self):
        st = self.academy.flashcards.stats()
        if st["total"] == 0:
            return ("لا توجد بطاقات بعد. افتح مكتبة البطاقات الجاهزة لإضافة آلاف البطاقات "
                    "المبنية من دروسك (إنجليزي، فرنسي، ومواد)، أو أنشئ بطاقاتك بنفسك.")
        return (f"لديك {st['total']} بطاقة في {st['decks']} مجموعة، "
                f"منها {st['due']} مستحقّة للمراجعة الآن.")

    def _refresh(self):
        self.summary.SetLabel(self._summary())
        self.deckChoice.Set(["كل المجموعات"] + self.academy.flashcards.decks())
        self.deckChoice.SetSelection(0)

    def _start(self):
        i = self.deckChoice.GetSelection()
        deck = None if i <= 0 else self.deckChoice.GetString(i)
        cards = self.academy.flashcards.due_cards(deck=deck, limit=60)
        if not cards:
            self.announce("لا توجد بطاقات مستحقّة للمراجعة الآن. أضف بطاقات أو عد لاحقاً.")
            return
        self.show_child(ReviewScreen(self, self.academy, self.speech, cards,
                                     deck or "كل المجموعات"))
        self._refresh()

    def _quick_add(self):
        dlg = _CardEditor(self, self.speech, self.academy.flashcards.decks())
        self.show_child(dlg)
        if dlg.result:
            self.academy.flashcards.add(**dlg.result)
            self.announce("تمت إضافة البطاقة.")
            self._refresh()

    def _library(self):
        self.show_child(LibraryScreen(self, self.academy, self.speech))
        self._refresh()

    def _manage(self):
        self.show_child(ManageScreen(self, self.academy, self.speech))
        self._refresh()

    def instructions(self):
        return ("راجع بطاقاتك بنظام التكرار المتباعد الذكي: البطاقات التي تنساها تعود قريباً، "
                "والتي تتقنها تبتعد. اختر مجموعة وابدأ المراجعة، أو أضف بطاقات جديدة وأدرها. "
                "Escape للإغلاق.")
