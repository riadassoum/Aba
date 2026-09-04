# -*- coding: utf-8 -*-
"""
abaAcademy.gui.games
====================

A section of accessible, keyboard-and-speech brain-training games for the
students — a place to play and sharpen memory, arithmetic, logic and language,
alongside the Qur'an, Hadith and learning sections. Every game here is an
original implementation of a public-domain game *concept* (memory spans,
number puzzles, tic-tac-toe, hangman, …); no third-party game code or content
is used.

Games are Arabic/RTL, fully driven by the keyboard, and announce everything
through the screen reader. Some are solo (beat your own best), others play
against a simple built-in AI. Scores persist in the the application's data folder.

The GamesHome screen lists every game grouped by the skill it trains; each game
is its own AccessibleDialog.
"""

from __future__ import annotations

import json
import random

from .accessible import AccessibleDialog


def _maze_cls():
    """Lazy import of the spatial maze so games.py has no hard dependency on the
    spatial audio package at import time."""
    from .spatial_maze import SpatialMazeDialog
    return SpatialMazeDialog


def _chess_cls():
    """Lazy import of accessible chess (keeps the chess engine out of games.py's
    import path until the game is actually opened)."""
    from .chess_accessible import ChessDialog
    return ChessDialog


def _multiplayer_cls():
    """Lazy import of the LAN multiplayer quiz."""
    from .multiplayer_quiz import MultiplayerQuizDialog
    return MultiplayerQuizDialog

try:
    import wx
except Exception:
    wx = None

AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def ar(n):
    return str(n).translate(AR)


class GamesHome(AccessibleDialog):
    """The games arcade: pick a game. Grouped by the skill it strengthens."""

    def __init__(self, parent, academy, speech):
        super().__init__(parent, "الألعاب الذهنية", speech, size=(640, 620))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label="اختر لعبة لتقوية ذهنك:"), 0, wx.ALL, 8)

        # (label, factory) — factory(parent, academy, speech) -> dialog
        from . import games_more as gm
        from .millionaire import MillionaireGame, TrainingGround
        groups = [
            ("مسابقات", [
                ("من سيربح المليون", MillionaireGame),
                ("ساحة التدريب (تدرّب باختيار التصنيف، بلا خسارة)", TrainingGround),
                ("مسابقة عبر الشبكة المحلية (لاعبون متعدّدون)", _multiplayer_cls()),
            ]),
            ("الذاكرة", [
                ("تذكّر الأرقام (مدى الأرقام)", MemoryDigits),
                ("تسلسل الأصوات/الأرقام (سايمون)", SimonSequence),
                ("لعبة كِم (تذكّر الأشياء)", KimGame),
                ("أزواج متطابقة (ذاكرة)", gm.PairsMemory),
            ]),
            ("الحساب والأرقام", [
                ("حساب سريع", QuickMath),
                ("خمّن الرقم (ضد الحاسوب)", GuessNumber),
                ("أكمل المتتالية", gm.SequenceGame),
                ("٢٤: اجمع للوصول", gm.MakeTarget),
                ("زوجيّ أم فرديّ", gm.OddEven),
                ("الرقم الناقص", gm.MissingNumber),
                ("عُدّ وركّز", gm.CountingGame),
                ("الواحد والعشرون (٢١)", gm.TwentyOne),
            ]),
            ("المنطق والتفكير", [
                ("الشطرنج الميسّر (ضد محرّك مدمج)", _chess_cls()),
                ("إكس-أو (ضد الذكاء الاصطناعي)", TicTacToe),
                ("أربعة على التوالي (ضد الحاسوب)", gm.ConnectFour),
                ("عكس / أوثيلو (ضد الحاسوب)", gm.Reversi),
                ("النقاط والصناديق (ضد الحاسوب)", gm.DotsAndBoxes),
                ("نيم: آخر من يأخذ (ضد الحاسوب)", gm.NimGame),
                ("بحر السفن الصغير (ضد الحاسوب)", gm.MiniBattleship),
                ("ماستر مايند بالأرقام", gm.Mastermind),
                ("ثيران وأبقار", gm.BullsAndCows),
                ("صح أم خطأ سريع", gm.TrueFalseBlitz),
            ]),
            ("اللغة والكلمات", [
                ("المشنقة (خمّن الكلمة)", Hangman),
                ("الكلمات المبعثرة (أناغرام، بمؤقّت)", gm.Anagrams),
                ("كوّن كلمات من حروف", gm.WordScramble),
                ("عكس الكلمة", gm.ReverseWord),
                ("أول حرف آخر حرف", gm.WordChain),
                ("كلمات بحرف", gm.RhymeOrStart),
            ]),
            ("الصوت والفضاء", [
                ("المتاهة الصوتية (تنقّل بالسمع)", _maze_cls()),
            ]),
        ]
        for title, games in groups:
            s.Add(wx.StaticText(panel, label=f"— {title} —"), 0, wx.TOP | wx.LEFT, 6)
            for label, cls in games:
                s.Add(self.button(panel, label,
                                  lambda e, c=cls: self._open(c)),
                      0, wx.EXPAND | wx.ALL, 3)
        s.Add(self.button(panel, "أفضل نتائجي", lambda e: self._scores()),
              0, wx.EXPAND | wx.ALL, 3)
        s.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
              0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        self.set_first_control(panel.GetChildren()[1])

    def _open(self, cls):
        self.show_child(cls(self, self.academy, self.speech))

    def _scores(self):
        self.show_child(HighScores(self, self.academy, self.speech))

    def instructions(self) -> str:
        return ("قائمة الألعاب الذهنية، مصنّفة حسب المهارة: الذاكرة، الحساب، المنطق، "
                "واللغة. اختر لعبة بالأسهم وEnter. Escape للإغلاق.")


# --------------------------------------------------------------------------
# score persistence
# --------------------------------------------------------------------------

def load_scores(academy):
    try:
        return json.loads(academy.store.get_setting("game_scores", "") or "{}")
    except Exception:
        return {}


def save_score(academy, game_key, score, higher_is_better=True):
    """Record a score; returns True if it's a new best."""
    scores = load_scores(academy)
    prev = scores.get(game_key)
    is_best = (prev is None or (score > prev if higher_is_better else score < prev))
    if is_best:
        scores[game_key] = score
        try:
            academy.store.set_setting("game_scores", json.dumps(scores, ensure_ascii=False))
        except Exception:
            pass
    return is_best


class HighScores(AccessibleDialog):
    NAMES = {
        "memory_digits": "تذكّر الأرقام", "simon": "تسلسل سايمون",
        "kim": "لعبة كِم", "pairs": "أزواج متطابقة",
        "quick_math": "حساب سريع", "guess_number": "خمّن الرقم",
        "sequence": "أكمل المتتالية", "make_target": "٢٤ اجمع للوصول",
        "odd_even": "زوجيّ أم فرديّ", "tictactoe": "إكس-أو",
        "nim": "نيم", "battleship": "بحر السفن", "mastermind": "ماستر مايند",
        "tf_blitz": "صح أم خطأ سريع", "hangman": "المشنقة",
        "scramble": "كوّن كلمات", "reverse": "عكس الكلمة", "chain": "أول وآخر حرف",
        "bulls_cows": "ثيران وأبقار", "twenty_one": "الواحد والعشرون",
        "counting": "عُدّ وركّز", "missing_number": "الرقم الناقص",
        "letter_words": "كلمات بحرف", "anagrams": "الكلمات المبعثرة",
        "connect_four": "أربعة على التوالي", "millionaire": "من سيربح المليون",
        "reversi": "عكس (أوثيلو)", "dots_boxes": "النقاط والصناديق",
    }

    def __init__(self, parent, academy, speech):
        super().__init__(parent, "أفضل نتائجي", speech, size=(520, 480))
        scores = load_scores(academy)
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        if not scores:
            body = "لا توجد نتائج بعد. العب لتسجّل أرقامك القياسية!"
        else:
            lines = []
            for key, val in scores.items():
                lines.append(f"{self.NAMES.get(key, key)}: {ar(val)}")
            body = "\n".join(lines)
        t = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY, value=body)
        t.SetName("أفضل النتائج")
        s.Add(t, 1, wx.EXPAND | wx.ALL, 8)
        s.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
              0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        self.set_first_control(t)

    def instructions(self) -> str:
        return "أفضل نتائجك في كل لعبة. Escape للإغلاق."


# --------------------------------------------------------------------------
# a small base class for a single-input game screen
# --------------------------------------------------------------------------

class GridGameDialog(AccessibleDialog):
    """Reusable base for board games played on a 2-D grid navigated with the four
    arrow keys, with hard edges (no wrapping): the cursor stops at the boundary
    and announces "حافة اللوح" rather than jumping to the opposite side. Cells are
    addressed like a spreadsheet — a column letter then a row number (A1..).

    Subclasses set ``ROWS``/``COLS`` (and optionally ``COL_LABELS`` for Arabic
    column letters), implement ``cell_word(r, c)`` to describe a cell, and
    ``activate(r, c)`` for Enter/Space on a cell. They call ``refresh_grid()``
    after changing the board and ``set_cursor(r, c)`` to move the announced
    focus. This is the same navigation model as the tic-tac-toe board, shared so
    every board game feels identical."""

    ROWS = 3
    COLS = 3
    COL_LABELS = None      # e.g. "ABC" or "أبجده"; default derives from COLS

    def __init__(self, parent, academy, speech, title, size=(600, 520)):
        super().__init__(parent, title, speech, size=size)
        self.academy = academy
        self._row = 0
        self._col = 0
        self._labels = self.COL_LABELS or "ABCDEFGH"[:self.COLS]

    def build_grid(self, panel, sizer):
        """Create the shared status line + grid listbox. Call from the subclass's
        __init__ after making its own panel/sizer, then add controls + call
        ``self.set_first_control(self.grid)``."""
        self.status = wx.StaticText(panel, label="")
        sizer.Add(self.status, 0, wx.ALL, 8)
        self.grid = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.grid.SetName("اللوح، تنقّل بأسهم الاتجاهات الأربعة، Enter للتفعيل")
        self.grid.Bind(wx.EVT_KEY_DOWN, self._on_grid_key)
        sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 6)

    def say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def addr(self, r, c):
        return f"{self._labels[c]}{r + 1}"

    def cell_word(self, r, c):    # override
        return "فارغة"

    def activate(self, r, c):     # override
        pass

    def refresh_grid(self, keep_cursor=True):
        items = [f"{self.addr(r, c)}: {self.cell_word(r, c)}"
                 for r in range(self.ROWS) for c in range(self.COLS)]
        self.grid.Set(items)
        if keep_cursor:
            self._select_cursor()

    def set_cursor(self, r, c):
        self._row = max(0, min(self.ROWS - 1, r))
        self._col = max(0, min(self.COLS - 1, c))
        self._select_cursor()

    def _select_cursor(self):
        """Move the listbox selection to the cursor, safely.

        Callers sometimes place the cursor before the grid has been filled (a
        game setting its starting position, then drawing). wxListBox raises on a
        selection index it doesn't have yet, so we only select once the item
        exists — the next refresh_grid() puts the highlight where it belongs.
        """
        index = self._row * self.COLS + self._col
        try:
            if 0 <= index < self.grid.GetCount():
                self.grid.SetSelection(index)
        except Exception:
            pass

    def announce_cell(self):
        self.announce(f"{self.addr(self._row, self._col)}، "
                      f"{self.cell_word(self._row, self._col)}")

    def on_enter_key(self):
        """The base dialog intercepts Enter globally; route it to activating the
        current cell (Space also works via the grid's own key handler). When a
        button has focus, return False so wx activates that button natively."""
        focus = self.FindFocus()
        if isinstance(focus, wx.Button):
            return False
        self.activate(self._row, self._col)
        return True

    def _on_grid_key(self, evt):
        code = evt.GetKeyCode()
        if code == wx.WXK_SPACE:
            self.activate(self._row, self._col)
            return
        moved = at_edge = False
        if code == wx.WXK_UP:
            if self._row > 0:
                self._row -= 1; moved = True
            else:
                at_edge = True
        elif code == wx.WXK_DOWN:
            if self._row < self.ROWS - 1:
                self._row += 1; moved = True
            else:
                at_edge = True
        elif code == wx.WXK_LEFT:
            if self._col > 0:
                self._col -= 1; moved = True
            else:
                at_edge = True
        elif code == wx.WXK_RIGHT:
            if self._col < self.COLS - 1:
                self._col += 1; moved = True
            else:
                at_edge = True
        else:
            evt.Skip()
            return
        if moved:
            self._select_cursor()
            self.announce_cell()
        elif at_edge:
            self.announce("حافة اللوح. " + self.addr(self._row, self._col) +
                          "، " + self.cell_word(self._row, self._col))


class _GameBase(AccessibleDialog):
    """Common scaffold: a status line, a text entry, and an action button.
    Subclasses implement ``start()`` and ``handle(text)``.

    Games that should run against a clock set ``TIME_LIMIT`` (seconds). When set,
    a countdown starts on the first move; when it runs out the round ends, the
    final score is announced and recorded, and further input is ignored until the
    learner starts a new game. Games leave ``TIME_LIMIT = 0`` to stay untimed
    (memory-span games, turn-based games vs the computer, etc.)."""

    TITLE = "لعبة"
    GAME_KEY = ""
    HIGHER_BETTER = True
    TIME_LIMIT = 0          # seconds; 0 = untimed

    def __init__(self, parent, academy, speech, size=(560, 420)):
        super().__init__(parent, self.TITLE, speech, size=size)
        self.academy = academy
        panel = wx.Panel(self)
        self._panel = panel
        s = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(panel, label="")
        s.Add(self.status, 0, wx.ALL, 8)
        self._extra_controls(panel, s)
        self.entry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.entry.SetName("اكتب هنا ثم اضغط Enter")
        self.entry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._submit())
        s.Add(self.entry, 0, wx.EXPAND | wx.ALL, 6)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "إرسال", lambda e: self._submit()), 0, wx.ALL, 4)
        row.Add(self.button(panel, "لعبة جديدة", lambda e: self._restart()), 0, wx.ALL, 4)
        if self.TIME_LIMIT:
            row.Add(self.button(panel, "الوقت المتبقّي", lambda e: self._announce_time()), 0, wx.ALL, 4)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(row, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.entry)
        self._timer = None
        self._time_left = 0
        self._timed_out = False
        if wx is not None and self.TIME_LIMIT:
            self._timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._on_tick, self._timer)
        wx.CallAfter(self.start)

    def say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def _extra_controls(self, panel, sizer):
        """Hook: games that need extra choosers (rule/level dropdowns) override
        this to insert them just under the status line. Default: nothing."""
        pass

    # -- timer support ----------------------------------------------------
    def _begin_timer(self):
        """Start (or restart) the countdown; called by timed games in start()."""
        if not self.TIME_LIMIT:
            return
        self._time_left = self.TIME_LIMIT
        self._timed_out = False
        if self._timer:
            self._timer.Stop()
            self._timer.Start(1000)

    def _on_tick(self, evt):
        self._time_left -= 1
        # gentle spoken warnings near the end
        if self._time_left in (10, 5):
            self.announce(f"بقي {ar(self._time_left)} ثوانٍ.")
        if self._time_left <= 0:
            if self._timer:
                self._timer.Stop()
            self._timed_out = True
            self._time_up()

    def _announce_time(self):
        if self.TIME_LIMIT and not self._timed_out:
            self.announce(f"الوقت المتبقّي: {ar(max(0, self._time_left))} ثانية.")
        else:
            self.announce("لا يوجد مؤقّت في هذه اللعبة." if not self.TIME_LIMIT
                          else "انتهى الوقت.")

    def _time_up(self):
        """Default end-of-time behaviour: announce and record the score. Games
        that track a running score expose it via ``self._score``."""
        score = getattr(self, "_score", 0)
        self.record(score)
        self.say(f"انتهى الوقت! نتيجتك النهائية {ar(score)}. اضغط «لعبة جديدة» لجولة أخرى.")

    def on_closing(self):
        # make sure the timer never fires after the screen is gone
        if self._timer:
            self._timer.Stop()

    def _submit(self):
        if self._timed_out:
            self.announce("انتهى الوقت. اضغط «لعبة جديدة».")
            return
        text = self.entry.GetValue().strip()
        self.entry.SetValue("")
        self.entry.SetFocus()
        self.handle(text)

    def _restart(self):
        self._timed_out = False
        self.start()

    def record(self, score):
        if self.GAME_KEY and save_score(self.academy, self.GAME_KEY, score, self.HIGHER_BETTER):
            self.announce(f"رقم قياسي جديد: {ar(score)}!")

    # subclasses override:
    def start(self):
        pass

    def handle(self, text):
        pass


# --------------------------------------------------------------------------
# MEMORY GAMES
# --------------------------------------------------------------------------

class MemoryDigits(_GameBase):
    """Digit span: memorise a growing sequence of digits and type it back."""
    TITLE = "تذكّر الأرقام"
    GAME_KEY = "memory_digits"

    def start(self):
        self._len = 3
        self._new_round()

    def _new_round(self):
        self._seq = [random.randint(0, 9) for _ in range(self._len)]
        spoken = "، ".join(ar(d) for d in self._seq)
        self.say(f"احفظ هذه الأرقام ثم اكتبها متتابعة بلا فواصل: {spoken}")

    def handle(self, text):
        digits = [int(c) for c in text if c.isdigit()]
        # also accept Arabic-Indic digits
        for c in text:
            if c in "٠١٢٣٤٥٦٧٨٩":
                digits.append("٠١٢٣٤٥٦٧٨٩".index(c))
        # rebuild from the raw text in order
        digits = []
        for c in text:
            if c.isdigit():
                digits.append(int(c))
            elif c in "٠١٢٣٤٥٦٧٨٩":
                digits.append("٠١٢٣٤٥٦٧٨٩".index(c))
        if digits == self._seq:
            self.record(self._len)
            self._len += 1
            self.say(f"أحسنت! الآن {ar(self._len)} أرقام.")
            self.call_later(900, self._new_round)
        else:
            correct = "، ".join(ar(d) for d in self._seq)
            self.say(f"خطأ. كان التسلسل: {correct}. وصلت إلى {ar(self._len)} أرقام. "
                     f"اضغط «لعبة جديدة» للمحاولة ثانية.")

    def instructions(self):
        return ("تُنطق لك أرقام؛ احفظها ثم اكتبها بالترتيب واضغط Enter. مع كل نجاح "
                "يزداد طولها. Ctrl+R لإعادة سماع الأرقام. Escape للإغلاق.")

    def on_repeat(self):
        self.say("الأرقام: " + "، ".join(ar(d) for d in self._seq))


class SimonSequence(_GameBase):
    """Simon: a growing sequence of four named tones/colours to echo back."""
    TITLE = "تسلسل سايمون"
    GAME_KEY = "simon"
    ITEMS = ["أحمر", "أخضر", "أزرق", "أصفر"]

    def start(self):
        self._seq = []
        self._extend()

    def _extend(self):
        self._seq.append(random.choice(self.ITEMS))
        spoken = "، ".join(self._seq)
        self.say(f"كرّر التسلسل ({ar(len(self._seq))}): {spoken} — اكتبها مفصولة بمسافة أو فاصلة.")

    def handle(self, text):
        given = [w.strip() for w in text.replace("،", " ").split()]
        if given == self._seq:
            self.record(len(self._seq))
            self.say("صحيح!")
            self.call_later(800, self._extend)
        else:
            self.say(f"خطأ. كان: {'، '.join(self._seq)}. طولك {ar(len(self._seq) - 1)}. "
                     f"«لعبة جديدة» للإعادة.")

    def on_repeat(self):
        self.say("التسلسل: " + "، ".join(self._seq))

    def instructions(self):
        return ("يكبر التسلسل بلونٍ في كل جولة (أحمر/أخضر/أزرق/أصفر)؛ اكتب التسلسل كاملاً "
                "مفصولاً بمسافات. Ctrl+R لإعادة سماعه. Escape للإغلاق.")


class KimGame(_GameBase):
    """Kim's game: memorise a set of objects, then recall them."""
    TITLE = "لعبة كِم"
    GAME_KEY = "kim"
    OBJECTS = ["كتاب", "قلم", "مفتاح", "ساعة", "كوب", "خاتم", "هاتف", "مقص",
               "ملعقة", "حذاء", "قبعة", "مشط", "نظارة", "محفظة", "مصباح",
               "وسادة", "مظلة", "فرشاة", "صابون", "منديل"]

    def start(self):
        self._n = 4
        self._new_round()

    def _new_round(self):
        self._items = random.sample(self.OBJECTS, self._n)
        self.say(f"احفظ هذه الأشياء ({ar(self._n)}): " + "، ".join(self._items) +
                 " — ثم اكتبها كلها مفصولة بفواصل.")

    def handle(self, text):
        given = {w.strip() for w in text.replace("،", ",").split(",") if w.strip()}
        want = set(self._items)
        if given == want:
            self.record(self._n)
            self._n = min(self._n + 1, len(self.OBJECTS))
            self.say(f"ممتاز! تذكّرت كلها. الآن {ar(self._n)} أشياء.")
            self.call_later(900, self._new_round)
        else:
            missed = want - given
            self.say("لم تكمل. الأشياء كانت: " + "، ".join(self._items) +
                     (". نسيتَ: " + "، ".join(missed) if missed else "") +
                     ". «لعبة جديدة» للإعادة.")

    def on_repeat(self):
        self.say("الأشياء: " + "، ".join(self._items))

    def instructions(self):
        return ("تُعرض أشياء لتحفظها، ثم اكتبها كلها مفصولة بفواصل. مع كل نجاح يزيد عددها. "
                "Ctrl+R لسماعها ثانية. Escape للإغلاق.")


# --------------------------------------------------------------------------
# MATH / NUMBER GAMES
# --------------------------------------------------------------------------

class QuickMath(_GameBase):
    """Quick arithmetic against the clock: answer as many as you can in 60
    seconds. A wrong answer doesn't end the game — it just doesn't score — so the
    challenge is how many you get right before time runs out."""
    TITLE = "حساب سريع"
    GAME_KEY = "quick_math"
    TIME_LIMIT = 60

    def start(self):
        self._score = 0
        self._begin_timer()
        self.say("لديك ٦٠ ثانية. أجب عن أكبر عددٍ من المسائل. اضغط «الوقت المتبقّي» لمعرفة الوقت.")
        self._ask()

    def _ask(self):
        op = random.choice(["+", "-", "×"])
        if op == "×":
            a, b = random.randint(2, 9), random.randint(2, 9)
            self._answer = a * b
        elif op == "+":
            a, b = random.randint(2, 50), random.randint(2, 50)
            self._answer = a + b
        else:
            a = random.randint(10, 60)
            b = random.randint(1, a)
            self._answer = a - b
        self.say(f"كم يساوي {ar(a)} {op} {ar(b)}؟ (النتيجة: {ar(self._score)})")

    def handle(self, text):
        try:
            val = int(text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        except ValueError:
            self.say("اكتب رقماً.")
            return
        if val == self._answer:
            self._score += 1
            self._ask()
        else:
            self.say(f"خطأ، الصواب {ar(self._answer)}. تابع! (النتيجة {ar(self._score)})")
            self._ask()

    def instructions(self):
        return ("أجب عن مسائل الحساب بأسرع ما يمكن؛ كل إجابة صحيحة تزيد نتيجتك، والخطأ "
                "ينهي الجولة. Escape للإغلاق.")


class GuessNumber(_GameBase):
    """Guess the computer's number 1..100 with higher/lower hints."""
    TITLE = "خمّن الرقم"
    GAME_KEY = "guess_number"
    HIGHER_BETTER = False   # fewer guesses is better

    def start(self):
        self._secret = random.randint(1, 100)
        self._tries = 0
        self.say("خمّنتُ رقماً بين ١ و١٠٠. حاول أن تجده بأقل عدد من المحاولات.")

    def handle(self, text):
        try:
            g = int(text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        except ValueError:
            self.say("اكتب رقماً بين ١ و١٠٠.")
            return
        self._tries += 1
        if g == self._secret:
            self.say(f"أصبت! الرقم {ar(self._secret)} في {ar(self._tries)} محاولة.")
            self.record(self._tries)
        elif g < self._secret:
            self.say(f"أكبر من {ar(g)}. المحاولات: {ar(self._tries)}.")
        else:
            self.say(f"أصغر من {ar(g)}. المحاولات: {ar(self._tries)}.")

    def instructions(self):
        return ("الحاسوب اختار رقماً بين ١ و١٠٠؛ اكتب تخمينك وسيقول أكبر أم أصغر. "
                "حاول بأقل عدد محاولات. Escape للإغلاق.")


# --------------------------------------------------------------------------
# LOGIC GAMES
# --------------------------------------------------------------------------

class TicTacToe(AccessibleDialog):
    """Tic-tac-toe on a real, arrow-navigable 3x3 grid.

    The board is addressed like a spreadsheet: columns A, B, C and rows 1, 2, 3,
    so cells run A1 (top-left) to C3 (bottom-right). The learner moves a cursor
    with the arrow keys; each cell announces its address and whose piece is in it
    ("A1، فارغة" / "B2، لك" / "C3، للحاسوب"). Enter or Space plays the current
    cell.

    The AI has three levels so it feels like a real, human-like opponent rather
    than an always-perfect wall:
      * سهل (easy): mostly random — a beginner can win.
      * متوسّط (medium, the default): plays sensibly — takes a winning move,
        blocks your winning move, likes the centre and corners — but isn't
        perfect, so a thoughtful player can out-fork it. This is the most
        human-like level.
      * صعب (hard): perfect minimax — cannot be beaten, only drawn.
    Difficulty is chosen from a drop-down and remembered.
    """

    TITLE = "إكس-أو"
    GAME_KEY = "tictactoe"
    COLS = "ABC"
    WINS = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7),
            (2, 5, 8), (0, 4, 8), (2, 4, 6)]
    LEVELS = ["سهل", "متوسّط", "صعب"]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(560, 480))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(panel, label="")
        s.Add(self.status, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label="المستوى:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.levelChoice = wx.Choice(panel, choices=self.LEVELS)
        self.levelChoice.SetSelection(1)   # medium: the human-like default
        self.bind_choice(self.levelChoice, lambda e: self._restart())
        row.Add(self.levelChoice, 0, wx.RIGHT, 8)
        s.Add(row, 0, wx.ALL, 6)

        # the 3x3 grid — navigated in two dimensions with the arrow keys, with
        # NO wrapping: A1 has nothing above or to its left, C3 nothing below or
        # to its right, and so on. We keep an explicit (row, col) cursor and
        # clamp it at the edges, so the arrows behave like a real board rather
        # than a list that wraps around.
        self.grid = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.grid.SetName("لوح إكس-أو، تنقّل بأسهم الاتجاهات الأربعة، Enter للّعب")
        self.grid.Bind(wx.EVT_KEY_DOWN, self._on_grid_key)
        s.Add(self.grid, 1, wx.EXPAND | wx.ALL, 6)

        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(self.button(panel, "العب هنا (Enter)", lambda e: self._play_cursor()), 0, wx.ALL, 4)
        brow.Add(self.button(panel, "قراءة اللوح (Ctrl+R)", lambda e: self.on_repeat()), 0, wx.ALL, 4)
        brow.Add(self.button(panel, "لعبة جديدة", lambda e: self._restart()), 0, wx.ALL, 4)
        brow.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(brow, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.grid)
        wx.CallAfter(self.start)

    # -- helpers ----------------------------------------------------------
    def say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def _addr(self, i):
        return f"{self.COLS[i % 3]}{i // 3 + 1}"

    def _cell_word(self, i):
        v = self._b[i]
        return "لك" if v == self._human else "للحاسوب" if v == self._ai else "فارغة"

    def _cursor_index(self):
        return self._row * 3 + self._col

    def _refresh_grid(self, keep=None):
        items = [f"{self._addr(i)}: {self._cell_word(i)}" for i in range(9)]
        self.grid.Set(items)
        if keep is not None:
            self._row, self._col = keep // 3, keep % 3
        self.select_index(self.grid, self._cursor_index())

    def _announce_cell(self):
        i = self._cursor_index()
        self.announce(f"{self._addr(i)}، {self._cell_word(i)}")

    # -- game flow --------------------------------------------------------
    def start(self):
        self._b = [" "] * 9
        self._human, self._ai = "X", "O"
        self._over = False
        self._row, self._col = 0, 0
        self._refresh_grid(keep=0)
        lvl = self.LEVELS[self.choice_index(self.levelChoice)]
        self.say(f"لوح جديد. أنت (X) تبدأ. المستوى: {lvl}. تنقّل بأسهم الاتجاهات الأربعة "
                 f"بين الخانات A1 إلى C3، واضغط Enter أو مسافة للّعب في الخانة المختارة.")
        wx.CallAfter(self.grid.SetFocus)

    def _restart(self):
        self.start()

    def on_enter_key(self):
        """Route the globally-intercepted Enter to playing the current cell; when
        a button has focus, return False so wx activates it natively."""
        focus = self.FindFocus()
        if isinstance(focus, wx.Button):
            return False
        self._play_cursor()
        return True

    def _on_grid_key(self, evt):
        # Two-dimensional movement with hard edges (no wrapping): Up/Down change
        # the row, Left/Right the column, each clamped so you cannot move past
        # the board. Space plays the current cell (Enter is handled by
        # on_enter_key since the base dialog intercepts it globally).
        code = evt.GetKeyCode()
        if code == wx.WXK_SPACE:
            self._play_cursor()
            return
        moved = False
        at_edge = False
        if code == wx.WXK_UP:
            if self._row > 0:
                self._row -= 1; moved = True
            else:
                at_edge = True
        elif code == wx.WXK_DOWN:
            if self._row < 2:
                self._row += 1; moved = True
            else:
                at_edge = True
        elif code == wx.WXK_LEFT:
            if self._col > 0:
                self._col -= 1; moved = True
            else:
                at_edge = True
        elif code == wx.WXK_RIGHT:
            if self._col < 2:
                self._col += 1; moved = True
            else:
                at_edge = True
        else:
            evt.Skip()
            return
        if moved:
            self.select_index(self.grid, self._cursor_index())
            self._announce_cell()
        elif at_edge:
            # announce the edge so the learner knows the board ended here
            self.announce("حافة اللوح. " + self._addr(self._cursor_index()) +
                          "، " + self._cell_word(self._cursor_index()))

    def _play_cursor(self):
        if self._over:
            self.say("انتهت اللعبة. اضغط «لعبة جديدة».")
            return
        i = self._cursor_index()
        if self._b[i] != " ":
            self.say(f"{self._addr(i)} مشغولة. اختر خانة فارغة.")
            return
        self._b[i] = self._human
        if self._winner() or " " not in self._b:
            self._refresh_grid(keep=i)
            return self._end()
        mv = self._ai_move()
        self._b[mv] = self._ai
        # keep the cursor where the human just played, not on the AI's cell
        self._refresh_grid(keep=i)
        if self._winner() or " " not in self._b:
            return self._end()
        self.say(f"لعبتَ في {self._addr(i)}. لعب الحاسوب في {self._addr(mv)}. "
                 f"دورك؛ تنقّل بالأسهم واختر خانة.")

    def _end(self):
        self._over = True
        w = self._winner()
        if w == self._human:
            self.say("فزت! أحسنت اللعب. اضغط «لعبة جديدة» لجولة أخرى.")
            self.record(1)
        elif w == self._ai:
            self.say("فاز الحاسوب هذه المرة. اضغط «لعبة جديدة» للمحاولة ثانية.")
        else:
            self.say("تعادل! اضغط «لعبة جديدة» لجولة أخرى.")

    def record(self, n):
        if save_score(self.academy, self.GAME_KEY, n, True):
            self.announce("سجّلت فوزاً جديداً!")

    # -- rules & AI -------------------------------------------------------
    def _winner(self, b=None):
        b = b if b is not None else self._b
        for a, c, d in self.WINS:
            if b[a] != " " and b[a] == b[c] == b[d]:
                return b[a]
        return None

    def _empties(self, b):
        return [i for i in range(9) if b[i] == " "]

    def _winning_move(self, b, player):
        for i in self._empties(b):
            b2 = list(b)
            b2[i] = player
            if self._winner(b2) == player:
                return i
        return None

    def _ai_move(self):
        """Choose the AI's move according to the selected difficulty."""
        level = self.choice_index(self.levelChoice)   # 0 easy, 1 medium, 2 hard
        empties = self._empties(self._b)
        if level == 0:
            # easy: occasional sensible move, mostly random -> quite beatable
            if random.random() < 0.35:
                w = self._winning_move(self._b, self._ai)
                if w is not None:
                    return w
            return random.choice(empties)
        if level == 1:
            # medium (human-like): win if you can, block if you must, prefer the
            # centre then corners — but don't look ahead for forks, so a sharp
            # player can still beat it, and occasionally it plays a little loose.
            w = self._winning_move(self._b, self._ai)
            if w is not None:
                return w
            block = self._winning_move(self._b, self._human)
            if block is not None:
                return block
            # 15% of the time, play a plain random move (a human lapse)
            if random.random() < 0.15:
                return random.choice(empties)
            if 4 in empties:
                return 4
            corners = [i for i in (0, 2, 6, 8) if i in empties]
            if corners:
                return random.choice(corners)
            return random.choice(empties)
        # hard: perfect minimax
        return self._best_move()

    def _best_move(self):
        best, mv = -10, None
        for i in self._empties(self._b):
            self._b[i] = self._ai
            sc = self._minimax(False)
            self._b[i] = " "
            if sc > best:
                best, mv = sc, i
        return mv if mv is not None else random.choice(self._empties(self._b))

    def _minimax(self, maximizing):
        w = self._winner()
        if w == self._ai:
            return 1
        if w == self._human:
            return -1
        if " " not in self._b:
            return 0
        if maximizing:
            best = -10
            for i in self._empties(self._b):
                self._b[i] = self._ai
                best = max(best, self._minimax(False))
                self._b[i] = " "
            return best
        best = 10
        for i in self._empties(self._b):
            self._b[i] = self._human
            best = min(best, self._minimax(True))
            self._b[i] = " "
        return best

    def on_repeat(self):
        rows = []
        for r in range(3):
            cells = [f"{self._addr(r * 3 + c)} {self._cell_word(r * 3 + c)}" for c in range(3)]
            rows.append("، ".join(cells))
        self.say("اللوح: " + "؛ ".join(rows))

    def instructions(self):
        return ("إكس-أو على لوح ثنائي الأبعاد. تنقّل بأسهم الاتجاهات الأربعة (لأعلى وأسفل بين الصفوف، لليمين واليسار بين الأعمدة) بلا التفاف عند الحواف. الخانات معنونة A1 إلى C3 (الأعمدة "
                "A B C والصفوف ١ ٢ ٣). كل خانة تنطق عنوانها وصاحبها. Enter أو مسافة للّعب. "
                "اختر المستوى من القائمة: سهل، متوسّط (شبيه بلاعب حقيقي)، أو صعب (لا يُهزم). "
                "Ctrl+R لقراءة اللوح. Escape للإغلاق.")


    def instructions(self):
        return ("إكس-أو ضد الحاسوب. الخانات مرقّمة ١ إلى ٩ من أعلى اليسار إلى أسفل اليمين. "
                "اكتب رقم خانتك. Ctrl+R أو اكتب «لوح» لسماع الوضع. Escape للإغلاق.")


# --------------------------------------------------------------------------
# WORD GAMES
# --------------------------------------------------------------------------

class Hangman(_GameBase):
    """Hangman: guess the Arabic word letter by letter."""
    TITLE = "المشنقة"
    GAME_KEY = "hangman"

    WORDS = ["مدرسة", "كتاب", "قلم", "شمس", "قمر", "بحر", "جبل", "نهر",
             "وردة", "شجرة", "طائر", "سمكة", "حصان", "مفتاح", "نافذة",
             "حديقة", "مطبخ", "سحاب", "مطر", "ثلج", "عصفور", "فراشة"]

    def start(self):
        self._word = random.choice(self.WORDS)
        self._letters = set(self._word)
        self._guessed = set()
        self._wrong = 0
        self._max_wrong = 7
        self._announce_state()

    def _mask(self):
        return " ".join(c if c in self._guessed else "_" for c in self._word)

    def _announce_state(self):
        self.say(f"الكلمة: {self._mask()} — عدد الحروف {ar(len(self._word))}، "
                 f"المحاولات الخاطئة المتبقية {ar(self._max_wrong - self._wrong)}. "
                 f"اكتب حرفاً.")

    def handle(self, text):
        t = text.strip()
        if not t:
            self._announce_state()
            return
        # allow guessing the whole word
        if len(t) > 1:
            if t == self._word:
                self._guessed = set(self._word)
                return self._win()
            self._wrong += 1
            return self._after_wrong(f"«{t}» ليست الكلمة.")
        ch = t[0]
        if ch in self._guessed:
            self.say("جرّبت هذا الحرف. اكتب حرفاً آخر.")
            return
        self._guessed.add(ch)
        if ch in self._letters:
            if self._letters <= self._guessed:
                return self._win()
            self.say(f"صحيح! {self._mask()}")
        else:
            self._wrong += 1
            self._after_wrong(f"الحرف «{ch}» ليس فيها.")

    def _after_wrong(self, msg):
        if self._wrong >= self._max_wrong:
            self.say(f"{msg} انتهت المحاولات. الكلمة كانت «{self._word}». «لعبة جديدة».")
        else:
            self.say(f"{msg} {self._mask()}. متبقٍّ {ar(self._max_wrong - self._wrong)}.")

    def _win(self):
        self.say(f"أحسنت! الكلمة «{self._word}». «لعبة جديدة» لكلمة أخرى.")
        self.record(1)

    def on_repeat(self):
        self._announce_state()

    def instructions(self):
        return ("خمّن الكلمة العربية حرفاً حرفاً؛ لديك سبع محاولات خاطئة. يمكنك كتابة الكلمة "
                "كاملة إن عرفتها. Ctrl+R لسماع الوضع. Escape للإغلاق.")
