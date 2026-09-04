# -*- coding: utf-8 -*-
"""
abaAcademy.gui.braille_lessons_view
===================================

Interactive lessons that teach Arabic Grade-2 braille contractions step by step,
then drill them with a timed quiz. The learner writes each cell with the six dot
keys (F D S — J K L) pressed together as a chord (robust timer-based capture, so
pressing several keys "at once" registers all of them).

Two quiz modes:
* **بالوقت** — write as many words correctly as you can within a chosen time
  (30s / 1m / 2m / 5m).
* **بالعدد** — reach a chosen number of correct words as fast as you can.

Challenge words come from the ~294k-word dictionary and only ever use the
contractions the learner has reached, per :mod:`braille_challenges` /
:mod:`braille_lessons`. Records (best score per mode) are saved.
"""

from __future__ import annotations

import random
import time

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..braille_engine.arabic_braille import (
    ARABIC_LETTERS, GRADE2_WORDSIGNS, describe_dots, dots_to_unicode,
)
from ..braille_engine import braille_lessons as bl
from ..braille_engine.braille_challenges import BrailleChallengeEngine

_KEY_TO_DOT = {"F": 1, "D": 2, "S": 3, "J": 4, "K": 5, "L": 6}
_CHORD_COMMIT_MS = 180

_TIMES = [("٣٠ ثانية", 30), ("دقيقة", 60), ("دقيقتان", 120), ("٥ دقائق", 300)]
_COUNTS = [("٥ كلمات", 5), ("١٠ كلمات", 10), ("٢٠ كلمة", 20)]


class BrailleLessonsDialog(AccessibleDialog):
    TITLE = "دروس برايل التفاعلية"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(740, 600))
        self.academy = academy
        self._rng = random.Random()
        self._engine = BrailleChallengeEngine.get(academy.resource_dir)

        # chord state
        self._cap = None
        self._chord_timer = None
        self._kind = "contractions"    # contractions | letters | plain
        self._letters = list(ARABIC_LETTERS.keys())
        self._last_ctrl_r = 0.0        # for Ctrl+R once=repeat / twice=spell
        # quiz state
        self._active = False
        self._word = ""
        self._entered = []          # committed cells for the current word
        self._correct = 0
        self._time_left = 0
        self._target_count = 0
        self._mode = "time"
        self._quiz_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_second, self._quiz_timer)

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "تعلّم اختصارات برايل درسًا درسًا، ثم اختبر نفسك على كلمات حقيقية "
            "تستعمل ما تعلّمته. اكتب كل خلية بأصابعك: F=1، D=2، S=3، J=4، K=5، L=6، "
            "اضغط نقاط الخلية معًا ثم توقّف لحظة.")),
            0, wx.ALL, 6)

        # lesson chooser
        lrow = wx.BoxSizer(wx.HORIZONTAL)
        lrow.Add(wx.StaticText(panel, label="نوع التدريب:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.kindChoice = wx.Choice(panel, choices=[
            "اختصارات (دروس متدرّجة)", "حروف برايل (حرفًا حرفًا)",
            "كلمات بلا اختصارات (تهجئة)"])
        self.kindChoice.SetName("نوع التدريب")
        self.kindChoice.SetSelection(0)
        self.bind_choice(self.kindChoice, lambda e: self._on_kind())
        lrow.Add(self.kindChoice, 1)
        s.Add(lrow, 0, wx.EXPAND | wx.ALL, 6)

        # lesson chooser (for contraction mode)
        l2row = wx.BoxSizer(wx.HORIZONTAL)
        l2row.Add(wx.StaticText(panel, label="الدرس:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.lessonChoice = wx.Choice(
            panel, choices=[f"{i+1}. {t}" for i, (_, t, _) in enumerate(bl.all_lessons())])
        self.lessonChoice.SetName("اختيار الدرس")
        self.lessonChoice.SetSelection(0)
        self.bind_choice(self.lessonChoice, lambda e: self._load_lesson())
        l2row.Add(self.lessonChoice, 1)
        s.Add(l2row, 0, wx.EXPAND | wx.ALL, 6)

        # quiz settings
        qrow = wx.BoxSizer(wx.HORIZONTAL)
        qrow.Add(wx.StaticText(panel, label="نمط الاختبار:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.modeChoice = wx.Choice(panel, choices=["بالوقت", "بعدد الكلمات"])
        self.modeChoice.SetName("نمط الاختبار")
        self.modeChoice.SetSelection(0)
        self.bind_choice(self.modeChoice, lambda e: self._refresh_amounts())
        qrow.Add(self.modeChoice, 0, wx.RIGHT, 12)
        qrow.Add(wx.StaticText(panel, label="المقدار:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.amountChoice = wx.Choice(panel, choices=[n for n, _ in _TIMES])
        self.amountChoice.SetName("مقدار الاختبار")
        self.amountChoice.SetSelection(0)
        qrow.Add(self.amountChoice, 0)
        s.Add(qrow, 0, wx.EXPAND | wx.ALL, 6)

        self.info = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE,
                                size=(-1, 150))
        self.info.SetName("شرح الدرس")
        s.Add(self.info, 1, wx.EXPAND | wx.ALL, 6)

        # the chord input pad
        self.pad = wx.TextCtrl(panel, style=wx.TE_READONLY, size=(-1, 40))
        self.pad.SetName("لوح الكتابة بالبرايل")
        self.pad.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        self.pad.Bind(wx.EVT_KEY_UP, self._on_key_up)
        self.pad.Bind(wx.EVT_KEY_UP, self._on_key_up)
        s.Add(self.pad, 0, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(700)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "تعلّم الدرس", lambda e: self._teach()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "ابدأ الاختبار", lambda e: self._start_quiz()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "لمّح", lambda e: self._hint()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "أفضل نتيجة", lambda e: self._say_record()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self._init_chord()
        self.set_first_control(self.lessonChoice)
        wx.CallAfter(self._load_lesson)

    # -- lesson -----------------------------------------------------------
    def _on_kind(self):
        sel = self.kindChoice.GetSelection()
        self._kind = ["contractions", "letters", "plain"][sel]
        # the lesson chooser only applies to contractions
        self.lessonChoice.Enable(self._kind == "contractions")
        if self._kind == "letters":
            self.info.SetValue(
                "تدريب حروف برايل: ستُطلب منك كتابة حروف عربية حرفًا حرفًا "
                "بالنقاط. اضغط «ابدأ الاختبار». يمكنك سماع الحرف مجددًا بـ Ctrl+R، "
                "أو تهجئته بالضغط مرتين.")
            self._say("تدريب الحروف: اكتب كل حرف بنقاطه.")
        elif self._kind == "plain":
            self.info.SetValue(
                "تدريب الكلمات بلا اختصارات: ستُطلب منك تهجئة كلمات عربية حرفًا "
                "حرفًا من قاموس يضمّ أكثر من ٢٩٤ ألف كلمة. لا تُستعمل الاختصارات "
                "هنا. Ctrl+R يعيد الكلمة، ومرّتان يتهجّاها.")
            self._say("تدريب التهجئة: اكتب كل كلمة حرفًا حرفًا.")
        else:
            self._load_lesson()

    def _cur_lesson(self):
        return bl.all_lessons()[self.choice_index(self.lessonChoice)]

    def _refresh_amounts(self):
        by_time = self.modeChoice.GetSelection() == 0
        opts = _TIMES if by_time else _COUNTS
        self.amountChoice.Set([n for n, _ in opts])
        self.amountChoice.SetSelection(0)

    def _load_lesson(self):
        lid, title, signs = self._cur_lesson()
        lines = [f"الدرس: {title}", "", "الاختصارات في هذا الدرس:"]
        for sign in signs:
            cells = GRADE2_WORDSIGNS.get(sign, [])
            desc = "، ".join(describe_dots(c) for c in cells)
            lines.append(f"  «{sign}»: {desc}")
        lines.append("")
        lines.append("اضغط «تعلّم الدرس» لتدريب الاختصارات، ثم «ابدأ الاختبار».")
        self.info.SetValue("\n".join(lines))
        self._say(f"الدرس: {title}. عدد اختصاراته {len(signs)}.")

    def _teach(self):
        lid, title, signs = self._cur_lesson()
        bl.mark_started(self.academy.store, lid)
        # step through each sign, describing its dots
        parts = [f"اختصار «{s}» يُكتب: "
                 + "، ".join(describe_dots(c) for c in GRADE2_WORDSIGNS[s])
                 for s in signs]
        self._say("تعلّم الاختصارات: " + ". ".join(parts)
                  + ". الآن جرّبها في الاختبار.")

    # -- quiz -------------------------------------------------------------
    def _known(self):
        # everything up to and including the selected lesson
        lid, _t, _s = self._cur_lesson()
        bl.mark_started(self.academy.store, lid)
        return bl.contractions_up_to(lid)

    def _start_quiz(self):
        if self._kind == "contractions":
            known = self._known()
            if not known:
                self._say("لا اختصارات متاحة بعد.")
                return
        self._mode = "time" if self.modeChoice.GetSelection() == 0 else "count"
        opts = _TIMES if self._mode == "time" else _COUNTS
        amount = opts[self.choice_index(self.amountChoice)][1]
        self._correct = 0
        self._active = True
        if self._mode == "time":
            self._time_left = amount
            self._quiz_timer.Start(1000)
            self._say(f"بدأ الاختبار! اكتب أكبر عدد من الكلمات خلال {amount} ثانية.")
        else:
            self._target_count = amount
            self._say(f"بدأ الاختبار! اكتب {amount} كلمات بشكل صحيح.")
        self._next_word()
        wx.CallAfter(self.pad.SetFocus)

    def _next_word(self):
        if self._kind == "letters":
            ch = self._rng.choice(self._letters)
            self._word = ch
            self._entered = []
            self._say(f"اكتب حرف: {ch}.")
            return
        if self._kind == "plain":
            word = self._engine.pick_plain_word(self._rng)
            if not word:
                self._say("تعذّر إيجاد كلمة.")
                self._end_quiz()
                return
            self._word = word
            self._entered = []
            self._say(f"تهجّى كلمة: {word}. حرفًا حرفًا.")
            return
        # contraction mode
        known = self._known()
        word = self._engine.pick_word(known, self._rng)
        if not word:
            self._say("تعذّر إيجاد كلمة مناسبة.")
            self._end_quiz()
            return
        self._word = word
        self._entered = []
        self._say(f"اكتب كلمة: {word}. حرفًا حرفًا أو بالاختصارات التي تعرفها.")

    def _on_second(self, evt):
        if not self._active:
            self._quiz_timer.Stop()
            return
        self._time_left -= 1
        if self._time_left <= 0:
            self._end_quiz()
        elif self._time_left in (10, 5):
            self.announce(str(self._time_left))

    def _end_quiz(self):
        self._active = False
        self._quiz_timer.Stop()
        best = self._save_record(self._correct)
        extra = " رقم قياسي جديد!" if best else ""
        self._say(f"انتهى الاختبار! أجبت {self._correct} كلمة بشكل صحيح.{extra}")

    # -- chord capture (polling; see braille_engine/chord_input.py) --------
    def _init_chord(self):
        if getattr(self, "_cap", None) is not None:
            return
        from ..braille_engine.chord_input import PollingChordCapture, KEY_TO_DOT
        self._dot_keycodes = {ord(k): v for k, v in KEY_TO_DOT.items()}
        self._cap = PollingChordCapture(
            key_state=self._dot_held,
            on_cell=self._commit_cell,
            is_active=self._chord_active,
        )
        self._chord_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._chord_tick, self._chord_timer)
        self._chord_timer.Start(PollingChordCapture.INTERVAL_MS)

    def _dot_held(self, dot):
        for code, d in self._dot_keycodes.items():
            if d == dot:
                try:
                    return bool(wx.GetKeyState(code))
                except Exception:
                    return False
        return False

    def _chord_active(self):
        """Only capture while the quiz is running and this window is active."""
        if not self._active:
            return False
        try:
            if not self:
                return False
            top = wx.GetActiveWindow()
            return top is self or (top is not None and self.IsDescendant(top))
        except Exception:
            return True

    def _chord_tick(self, evt):
        try:
            self._cap.poll()
        except Exception:
            pass

    def on_raw_key_down(self, evt):
        code = evt.GetKeyCode()
        if code == ord("R") and evt.ControlDown():
            self._handle_ctrl_r()
            return True
        if code in getattr(self, "_dot_keycodes", {}):
            if not self._active:
                self._say("انتهى الاختبار. اضغط «ابدأ الاختبار» لجولة جديدة.")
            return True                # always swallow the dot keys
        if code == wx.WXK_SPACE and self._active:
            self._check_word()
            return True
        return False

    def _on_key_down(self, evt):
        code = evt.GetKeyCode()
        if code == ord("R") and evt.ControlDown():
            self._handle_ctrl_r()
            return
        if code in getattr(self, "_dot_keycodes", {}):
            return
        if code == wx.WXK_SPACE:
            self._check_word()
            return
        evt.Skip()

    def _on_key_up(self, evt):
        code = evt.GetKeyCode()
        if code in getattr(self, "_dot_keycodes", {}):
            return
        evt.Skip()

    def _handle_ctrl_r(self):
        """Ctrl+R once repeats the current word; pressing it again within a short
        window spells it out letter by letter."""
        if not self._word:
            self._say("لا يوجد ما يُكرَّر بعد.")
            return
        now = time.time()
        if now - self._last_ctrl_r < 1.2:
            # second press: spell it out
            spelled = " ".join(self._word)
            self._say(f"تهجئة: {spelled}.")
            self._last_ctrl_r = 0.0
        else:
            self._say(f"الكلمة: {self._word}.")
            self._last_ctrl_r = now

    def _commit_cell(self, cell):
        if not self._active:
            return
        self._entered.append(set(cell))
        glyph = dots_to_unicode(cell)
        self.announce(f"{glyph} {describe_dots(cell)}")

    def _check_word(self):
        """Called when the learner presses space to submit the current word."""
        if not self._active or not self._word:
            return
        if self._kind in ("letters", "plain"):
            # spelled letter by letter, no contractions
            from ..braille_engine.arabic_braille import ARABIC_LETTERS as AL
            want = [frozenset(AL[ch]) for ch in self._word if ch in AL]
            got = [frozenset(c) for c in self._entered]
            ok = got == want
        else:
            known = self._known()
            ok = self._engine.check(self._word, self._entered, known)
        if ok:
            self._correct += 1
            label = "الحرف" if self._kind == "letters" else "الكلمة"
            self._say(f"صحيح! «{self._word}». عدد الصحيح: {self._correct}.")
            if self._mode == "count" and self._correct >= self._target_count:
                self._end_quiz()
                return
            self._next_word()
        else:
            self._say(f"غير صحيح. حاول مجددًا أو «لمّح». المطلوب: {self._word}.")
            self._entered = []

    def _hint(self):
        if not self._word:
            self._say("ابدأ الاختبار أولًا.")
            return
        if self._kind == "letters":
            from ..braille_engine.arabic_braille import ARABIC_LETTERS as AL, describe_dots as dd
            if self._word in AL:
                self._say(f"حرف {self._word}: {dd(AL[self._word])}. ثم اضغط مسافة.")
            return
        if self._kind == "plain":
            from ..braille_engine.arabic_braille import ARABIC_LETTERS as AL, describe_dots as dd
            parts = [f"{ch}: {dd(AL[ch])}" for ch in self._word if ch in AL]
            self._say("التهجئة: " + "، ".join(parts) + ". ثم اضغط مسافة.")
            return
        known = self._known()
        self._say("طريقة الكتابة: "
                  + self._engine.canonical_hint(self._word, known)
                  + ". ثم اضغط مسافة عند الانتهاء.")

    def _record_key(self):
        if self._kind == "contractions":
            lid, _t, _s = self._cur_lesson()
            scope = lid
        else:
            scope = self._kind
        amount = (_TIMES if self._mode == "time" else _COUNTS)[
            self.choice_index(self.amountChoice)][1]
        return f"braille_quiz_{scope}_{self._mode}_{amount}"

    def _save_record(self, score):
        if self._mode != "time":
            return False           # count mode isn't a high-score
        try:
            key = self._record_key()
            prev = int(self.academy.store.get_setting(key, "0") or "0")
            if score > prev:
                self.academy.store.set_setting(key, str(score))
                return True
        except Exception:
            pass
        return False

    def _say_record(self):
        self._mode = "time" if self.modeChoice.GetSelection() == 0 else "count"
        try:
            best = int(self.academy.store.get_setting(self._record_key(), "0") or "0")
        except Exception:
            best = 0
        self._say(f"أفضل نتيجة لهذا الإعداد: {best} كلمة.")

    def on_closing(self):
        try:
            self._chord_timer.Stop()
        except Exception:
            pass
        try:
            self._quiz_timer.Stop()
            if self._chord_timer:
                self._chord_timer.Stop()
        except Exception:
            pass

    def _say(self, text):
        self.status.SetLabel(text[:200])
        self.announce(text)

    def instructions(self):
        return ("دروس برايل التفاعلية: اختر درسًا، «تعلّم الدرس» لسماع اختصاراته، ثم «ابدأ "
                "الاختبار». اكتب كل خلية بالأصابع F D S J K L مضغوطةً معًا، واضغط مسافة عند "
                "إتمام الكلمة. تُقبل كتابة الاختصارات التي تعلّمتها أو تهجئة الحروف. الاختبار "
                "إمّا بالوقت أو بعدد الكلمات، مع حفظ أفضل نتيجة. «لمّح» يوضّح طريقة الكتابة. "
                "Escape للإغلاق.")
