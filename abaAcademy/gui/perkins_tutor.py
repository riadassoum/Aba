# -*- coding: utf-8 -*-
"""
abaAcademy.gui.perkins_tutor
============================

An interactive Arabic braille tutor built on a **Perkins-style 6-key simulator**.
A Perkins brailler enters a whole cell at once: the writer holds down the keys
for the dots they want and releases them together. We reproduce that on a normal
QWERTY keyboard using the standard finger mapping:

    dot 3 = S     dot 6 = J
    dot 2 = D     dot 5 = K
    dot 1 = F     dot 4 = L

(space bar = a blank cell / space). The learner presses the combination for a
cell; when all keys are released the cell is "committed" and the tutor announces
which letter it formed and whether it matches the target.

Three practice modes:

* **تعلّم الحروف** — the tutor names a letter, the learner types its cell.
* **اكتب كلمة** — the tutor gives a short word; the learner types it cell by cell.
* **استكشاف حر** — free typing: type any cell and hear what letter it is.

Everything is offline and needs no braille display hardware, though it maps
cleanly onto one if present. It is a *teaching aid*; the UI states that the
letter cells follow the Unified Arabic Braille standard.
"""

from __future__ import annotations

import random

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..braille_engine.arabic_braille import (
    ArabicBraille, ARABIC_LETTERS, GRADE2_WORDSIGNS, dots_to_unicode, describe_dots,
)

# QWERTY key -> braille dot
_KEY_TO_DOT = {
    "F": 1, "D": 2, "S": 3, "J": 4, "K": 5, "L": 6,
}

# a compact teaching order (common letters first)
_LETTER_ORDER = list("ابتثجحخدذرزسشصضطظعغفقكلمنهوي")

_PRACTICE_WORDS = [
    "باب", "بيت", "قلم", "كتاب", "سلام", "ماء", "شمس", "قمر",
    "علم", "نور", "ورد", "بحر", "جبل", "نهر", "ولد", "بنت",
]


class PerkinsTutorDialog(AccessibleDialog):
    TITLE = "معلّم برايل التفاعلي (محاكي بيركنز)"

    MODE_LETTERS = 0
    MODE_WORD = 1
    MODE_FREE = 2
    MODE_CONTRACTIONS = 3

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 560))
        self.academy = academy
        self.ab = ArabicBraille()
        # chord capture state lives in the shared accumulator
        self._target_letter = None
        self._word = ""
        self._word_pos = 0
        self._contraction = None
        self._contraction_pos = 0
        self._score = 0
        self._asked = 0

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)

        s.Add(wx.StaticText(panel, label=(
            "محاكي بيركنز: النقاط تُكتب بالأصابع — "
            "F=1، D=2، S=3، J=4، K=5، L=6. "
            "اضغط نقاط الخلية معاً (أو بتتابع سريع) ثم توقّف لحظة لتُدخَل.")),
            0, wx.ALL, 6)

        mrow = wx.BoxSizer(wx.HORIZONTAL)
        mrow.Add(wx.StaticText(panel, label="النمط:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.modeChoice = wx.Choice(panel, choices=[
            "تعلّم الحروف", "اكتب كلمة", "استكشاف حر", "الاختصارات العربية"])
        self.modeChoice.SetSelection(0)
        self.bind_choice(self.modeChoice, lambda e: self._start_mode())
        mrow.Add(self.modeChoice, 0)
        s.Add(mrow, 0, wx.ALL, 6)

        # the typing surface: a text control we use only to capture key events
        self.pad = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE,
                               size=(-1, 80))
        self.pad.SetName("لوح الكتابة")
        s.Add(self.pad, 0, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(680)
        s.Add(self.status, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "أعد السؤال (Ctrl+R)", lambda e: self.on_repeat()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "لمّح للنقاط", lambda e: self._hint()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "سؤال جديد", lambda e: self._new_prompt()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        # capture key down/up on the pad for chord entry
        self.pad.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        self.pad.Bind(wx.EVT_KEY_UP, self._on_key_up)
        self._cap = None
        self._init_chord()
        self.set_first_control(self.pad)
        self.call_after(self._start_mode)

    # -- chord capture (polling; see braille_engine/chord_input.py) --------
    # Correctness does not depend on key events arriving: a timer samples which
    # dot keys are physically held, and the cell is whatever was held when the
    # last finger lifts. The key events are still consumed so the letters never
    # leak into a text field or fire a menu shortcut.

    def _init_chord(self):
        if getattr(self, "_cap", None) is not None:
            return
        from ..braille_engine.chord_input import PollingChordCapture, KEY_TO_DOT
        self._dot_keycodes = {ord(k): v for k, v in KEY_TO_DOT.items()}
        self._cap = PollingChordCapture(
            key_state=self._dot_held,
            on_cell=self._commit,
            is_active=self._chord_active,
        )
        self._chord_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._chord_tick, self._chord_timer)
        self._chord_timer.Start(PollingChordCapture.INTERVAL_MS)

    def _dot_held(self, dot):
        """Is this dot's key physically down right now?"""
        for code, d in self._dot_keycodes.items():
            if d == dot:
                try:
                    return bool(wx.GetKeyState(code))
                except Exception:
                    return False
        return False

    def _chord_active(self):
        """Capture only while this screen is the active window, so the dot keys
        never interfere with the rest of the application."""
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
        """Swallow the dot keys so they don't reach other controls or shortcuts.

        The cell itself is assembled by the poller, not here.
        """
        code = evt.GetKeyCode()
        if code in getattr(self, "_dot_keycodes", {}):
            return True
        if code == wx.WXK_SPACE and self._chord_active():
            self._commit(frozenset())
            return True
        return False

    def _on_key_down(self, evt):
        code = evt.GetKeyCode()
        if code in getattr(self, "_dot_keycodes", {}):
            return          # consumed; the poller builds the cell
        if code == wx.WXK_SPACE:
            self._commit(frozenset())
            return
        evt.Skip()

    def _on_key_up(self, evt):
        code = evt.GetKeyCode()
        if code in getattr(self, "_dot_keycodes", {}):
            return
        evt.Skip()

    def _commit(self, dots):
        mode = self.choice_index(self.modeChoice)
        name = self.ab.name_for_cell(dots)
        glyph = dots_to_unicode(dots)
        if mode == self.MODE_FREE:
            self._say(f"{glyph}  {name}. {describe_dots(dots)}.")
            return
        if mode == self.MODE_LETTERS:
            self._check_letter(dots, name)
            return
        if mode == self.MODE_WORD:
            self._check_word_cell(dots, name)
            return
        if mode == self.MODE_CONTRACTIONS:
            self._check_contraction_cell(dots, name)

    def _check_contraction_cell(self, dots, name):
        """Check the learner's cell against the current contraction's cell
        sequence, one cell at a time (some signs are more than one cell)."""
        cells = GRADE2_WORDSIGNS.get(self._contraction, [])
        if self._contraction_pos >= len(cells):
            return
        expected = cells[self._contraction_pos]
        if dots == expected:
            self._contraction_pos += 1
            if self._contraction_pos >= len(cells):
                self._score += 1
                self._asked += 1
                self._say(f"ممتاز! هذا اختصار كلمة {self._contraction}. "
                          f"نتيجتك {self._score} من {self._asked}. اختصار جديد قادم.")
                self.call_later(1100, self._new_prompt)
            else:
                self._say(f"صحيح، الخلية الأولى. أكمل بقية خلايا الاختصار.")
        else:
            self._say(f"ليس بعد. أدخلت {name}. "
                      f"هذا اختصار {self._contraction}. اضغط لمّح للنقاط لمعرفة خلاياه.")

    def _check_letter(self, dots, name):
        target = ARABIC_LETTERS.get(self._target_letter)
        if dots == target:
            self._score += 1
            self._asked += 1
            self._say(f"أحسنت! {name} صحيح. "
                      f"نتيجتك {self._score} من {self._asked}. سؤال جديد قادم.")
            self.call_later(900, self._new_prompt)
        else:
            self._say(f"ليس بعد. أدخلت {name}. "
                      f"المطلوب حرف {self._target_letter}. "
                      f"جرّب مرة أخرى، أو اضغط لمّح للنقاط.")

    def _check_word_cell(self, dots, name):
        cells = self.ab.text_to_cells(self._word)
        # flatten to (char, cell) at letter granularity
        flat = [(src, c) for src, cs in cells for c in cs]
        if self._word_pos >= len(flat):
            return
        expected_char, expected_cell = flat[self._word_pos]
        if dots == expected_cell:
            self._word_pos += 1
            if self._word_pos >= len(flat):
                self._score += 1
                self._asked += 1
                self._say(f"ممتاز! أكملت كلمة {self._word}. "
                          f"نتيجتك {self._score} من {self._asked}. كلمة جديدة قادمة.")
                self.call_later(1000, self._new_prompt)
            else:
                nxt = flat[self._word_pos][0]
                self._say(f"صحيح: حرف {expected_char}. الحرف التالي: {nxt}.")
        else:
            self._say(f"ليس بعد. أدخلت {name}. "
                      f"المطلوب حرف {expected_char}. جرّب مجدداً.")

    # -- prompts ----------------------------------------------------------
    def _start_mode(self):
        self._score = 0
        self._asked = 0
        self._new_prompt()
        self.call_after(self.pad.SetFocus)

    def _new_prompt(self):
        mode = self.choice_index(self.modeChoice)
        self._cap.reset()
        if mode == self.MODE_LETTERS:
            self._target_letter = random.choice(_LETTER_ORDER)
            self._say(f"اكتب حرف: {self._target_letter}. "
                      f"استخدم أصابعك على F D S J K L لإدخال نقاط الخلية.")
        elif mode == self.MODE_WORD:
            self._word = random.choice(_PRACTICE_WORDS)
            self._word_pos = 0
            first = self._word[0]
            self._say(f"اكتب كلمة: {self._word}. "
                      f"حرفاً حرفاً. ابدأ بحرف {first}.")
        elif mode == self.MODE_CONTRACTIONS:
            self._contraction = random.choice(list(GRADE2_WORDSIGNS.keys()))
            self._contraction_pos = 0
            ncells = len(GRADE2_WORDSIGNS[self._contraction])
            self._say(f"اكتب اختصار كلمة {self._contraction} بلغة برايل. "
                      f"عدد خلاياه {ncells}. اضغط لمّح للنقاط إن احتجت.")
        else:
            self._say("استكشاف حر: اكتب أي خلية بالأصابع لتسمع أيّ حرف هي. "
                      "المسافة لخلية فارغة.")

    def _hint(self):
        mode = self.modeChoice.GetSelection()
        if mode == self.MODE_LETTERS and self._target_letter:
            dots = ARABIC_LETTERS[self._target_letter]
            self._say(f"حرف {self._target_letter}: {describe_dots(dots)}.")
        elif mode == self.MODE_WORD and self._word:
            cells = self.ab.text_to_cells(self._word)
            flat = [(src, c) for src, cs in cells for c in cs]
            if self._word_pos < len(flat):
                ch, dots = flat[self._word_pos]
                self._say(f"حرف {ch}: {describe_dots(dots)}.")
        elif mode == self.MODE_CONTRACTIONS and self._contraction:
            cells = GRADE2_WORDSIGNS.get(self._contraction, [])
            if self._contraction_pos < len(cells):
                dots = cells[self._contraction_pos]
                pos_word = "الأولى" if self._contraction_pos == 0 else "التالية"
                self._say(f"اختصار {self._contraction}، الخلية {pos_word}: "
                          f"{describe_dots(dots)}.")
        else:
            self._say("في الاستكشاف الحر، جرّب أي تركيبة نقاط.")

    def on_repeat(self):
        mode = self.modeChoice.GetSelection()
        if mode == self.MODE_LETTERS and self._target_letter:
            self._say(f"اكتب حرف: {self._target_letter}.")
        elif mode == self.MODE_WORD and self._word:
            self._say(f"اكتب كلمة: {self._word}. الحرف الحالي رقم {self._word_pos + 1}.")
        elif mode == self.MODE_CONTRACTIONS and self._contraction:
            self._say(f"اكتب اختصار كلمة {self._contraction}.")
        else:
            self._say("استكشاف حر: اكتب أي خلية.")

    def on_closing(self):
        try:
            self._chord_timer.Stop()
        except Exception:
            pass
        try:
            if getattr(self, "_chord_timer", None):
                self._chord_timer.Stop()
        except Exception:
            pass

    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def instructions(self):
        return ("معلّم برايل التفاعلي بمحاكي بيركنز: تُدخل خلية برايل كاملةً بالضغط على "
                "نقاطها معاً بالأصابع ثم رفعها. الأصابع: F للنقطة 1، D للنقطة 2، S للنقطة 3، "
                "J للنقطة 4، K للنقطة 5، L للنقطة 6، والمسافة لخلية فارغة. اختر النمط: تعلّم "
                "الحروف، أو اكتب كلمة، أو استكشاف حر، أو الاختصارات العربية لتعلّم اختصارات "
                "برايل للكلمات الشائعة. لمّح للنقاط يخبرك بنقاط الحرف أو الاختصار المطلوب. "
                "الحروف تتبع معيار برايل العربي الموحّد. Escape للإغلاق.")
