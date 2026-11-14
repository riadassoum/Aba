# -*- coding: utf-8 -*-
"""
abaAcademy.gui.puzzles_view
===========================

Puzzle screens played entirely by keyboard and ear:

* **Sudoku** (٩×٩ or ٤×٤): arrows move, a digit writes, 0 or Delete
  erases, N toggles pencil-mark mode, H gives a hint that explains its
  reasoning, Ctrl+Z undoes; R, C and B read the row, column and box.
* **Minesweeper**: arrows move, Space or Enter opens, F flags, D describes
  the eight neighbours, H finds a cell logic proves safe.
* **2048**: arrows slide; every move reports merges and the new tile.
* **Sliding puzzle**: arrows slide a tile into the gap; H suggests the next
  move of an optimal solution (3×3).
"""

from __future__ import annotations

import random
import time

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from .games import GridGameDialog, save_score, ar
from ..puzzles import sudoku, minesweeper, tiles
from ..tools.ar_count import count

_DIGIT_KEYS = {}
if wx is not None:
    for _d in range(10):
        _DIGIT_KEYS[ord(str(_d))] = _d
        _DIGIT_KEYS[getattr(wx, f"WXK_NUMPAD{_d}")] = _d


def _elapsed(start: float) -> str:
    s = int(time.monotonic() - start)
    m, s = divmod(s, 60)
    return f"{count(m, 'minute')} و{count(s, 'second')}" if m else count(s, "second")


# ---------------------------------------------------------------------------
# Sudoku
# ---------------------------------------------------------------------------

class SudokuDialog(GridGameDialog):
    ROWS = COLS = 9
    COL_LABELS = sudoku.COL_LETTERS
    _LEVELS = list(sudoku.DIFFICULTIES)

    def __init__(self, parent, academy, speech, size_n: int = 9):
        super().__init__(parent, academy, speech, "سودوكو", size=(720, 640))
        self._set_size(size_n)
        self._rng = random.Random()
        self._notes_mode = False
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label="الصعوبة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.levelChoice = wx.Choice(panel, choices=[sudoku.DIFFICULTIES[k][0] for k in self._LEVELS])
        self.levelChoice.SetName("الصعوبة")
        self.levelChoice.SetSelection(1)
        row.Add(self.levelChoice, 0, wx.RIGHT, 12)
        row.Add(wx.StaticText(panel, label="الحجم:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.sizeChoice = wx.Choice(panel, choices=["٩×٩", "٤×٤ للمبتدئين"])
        self.sizeChoice.SetName("حجم اللوح")
        self.sizeChoice.SetSelection(0 if size_n == 9 else 1)
        row.Add(self.sizeChoice, 0)
        s.Add(row, 0, wx.ALL, 6)
        self.build_grid(panel, s)
        self.grid.Unbind(wx.EVT_KEY_DOWN)
        self.grid.Bind(wx.EVT_KEY_DOWN, self._on_key)
        btns = wx.BoxSizer(wx.HORIZONTAL)
        for label, h in (("لعبة جديدة", self._new), ("تلميح (H)", self._hint),
                         ("تراجع (Ctrl+Z)", self._undo), ("تحقّق", self._check),
                         ("إغلاق", self.close_screen)):
            btns.Add(self.button(panel, label, lambda e, f=h: f()), 0, wx.ALL, 3)
        s.Add(btns, 0, wx.ALL, 4)
        panel.SetSizer(s)
        self.set_first_control(self.grid)
        self.game = None
        self.call_after(self._new, True)

    def _set_size(self, n: int) -> None:
        # instance attributes shadow the class defaults GridGameDialog reads
        self.ROWS = self.COLS = n
        self._labels = sudoku.COL_LETTERS[:n]
        self._n = n

    def cell_word(self, r, c):
        if self.game is None:
            return ""
        text = self.game.describe_cell(r, c)
        return text.split(": ", 1)[1] if ": " in text else text

    def activate(self, r, c):
        self.announce(self.game.describe_cell(r, c) if self.game else "")

    def _new(self, quiet: bool = False) -> None:
        n = 9 if self.choice_index(self.sizeChoice) == 0 else 4
        if n != self._n:
            self._set_size(n)
        level = self._LEVELS[self.choice_index(self.levelChoice, 1)]
        self.say("أُنشئ اللغز…")
        self.game = sudoku.Game.new(n, level, self._rng)
        self._start = time.monotonic()
        self._row = self._col = 0
        self.refresh_grid()
        self.grid.SetFocus()
        empties = self.game.empty_count()
        if not quiet:
            self.say(f"لغز {sudoku.DIFFICULTIES[level][0]} جديد، فيه {count(empties, 'cell')} فارغة.")
        else:
            self.status.SetLabel(f"فيه {count(empties, 'cell')} فارغة.")

    def _put(self, v: int) -> None:
        g = self.game
        r, c = self._row, self._col
        if self._notes_mode and v:
            on = g.toggle_note(r, c, v)
            if on is False and g.grid[r][c]:
                self.announce("الخانة فيها رقم.")
            else:
                self.announce(f"ملاحظة {v} {'أُضيفت' if on else 'حُذفت'}.")
            self.refresh_grid()
            return
        res = g.place(r, c, v)
        self.refresh_grid()
        if res == "given":
            self.announce("هذه خانة معطاة لا تتغيّر.")
        elif res == "conflict":
            self.announce(f"{v} يتعارض مع رقم في الصفّ أو العمود أو المربّع.")
        elif res == "solved":
            took = _elapsed(self._start)
            self.say(f"أحسنت! حللت اللغز في {took}" + (f"، واستعنت بـ{count(g.hints_used, 'hint')}." if g.hints_used else " دون تلميحات."))
            key = f"sudoku_{self._n}"
            secs = int(time.monotonic() - self._start)
            if save_score(self.academy, key, secs, higher_is_better=False):
                self.announce("رقم قياسي جديد في السرعة!")
        else:
            self.announce(f"{v}" if v else "مُسحت.")

    def _on_key(self, evt) -> None:
        code = evt.GetKeyCode()
        if self.game is None:
            evt.Skip()
            return
        if code in _DIGIT_KEYS and not evt.ControlDown():
            v = _DIGIT_KEYS[code]
            if v <= self._n:
                self._put(v)
            return
        if code in (wx.WXK_DELETE, wx.WXK_BACK):
            self._put(0)
            return
        if evt.ControlDown() and code in (ord("Z"), ord("z")):
            self._undo()
            return
        if not evt.ControlDown() and code in (ord("N"), ord("n")):
            self._notes_mode = not self._notes_mode
            self.announce("وضع الملاحظات مفعّل." if self._notes_mode else "وضع الأرقام.")
            return
        if not evt.ControlDown() and code in (ord("H"), ord("h")):
            self._hint()
            return
        for letter, kind in (("R", "row"), ("C", "col"), ("B", "box")):
            if not evt.ControlDown() and code in (ord(letter), ord(letter.lower())):
                self.announce(self.game.describe_unit(kind, self._row, self._col))
                return
        self._on_grid_key(evt)

    def _hint(self) -> None:
        step = self.game.hint() if self.game else None
        if step is None:
            self.announce("لا تلميح الآن.")
            return
        self.set_cursor(step.row, step.col)
        self.announce(step.reason + (" اكتب الرقم لتثبيته." if step.value else ""))

    def _undo(self) -> None:
        if self.game and self.game.undo():
            self.refresh_grid()
            self.announce("تراجعت. " + self.game.describe_cell(self._row, self._col))
        else:
            self.announce("لا شيء للتراجع.")

    def _check(self) -> None:
        g = self.game
        wrong = [(r, c) for r in range(self._n) for c in range(self._n)
                 if g.grid[r][c] and g.grid[r][c] != g.solution[r][c]]
        if wrong:
            names = "، ".join(sudoku.cell_name(r, c) for r, c in wrong[:6])
            self.announce(f"أرقام خاطئة في: {names}.")
        else:
            self.announce(f"لا أخطاء حتى الآن. بقيت {count(g.empty_count(), 'cell')}.")

    def instructions(self) -> str:
        return ("سودوكو: الأسهم للتنقّل، الرقم للكتابة، صفر أو Delete للمسح. N لوضع الملاحظات، "
                "H لتلميح يشرح السبب، R وC وB لقراءة الصفّ والعمود والمربّع، Ctrl+Z للتراجع. "
                "الأعمدة بالحروف أ ب ج والصفوف بالأرقام.")


# ---------------------------------------------------------------------------
# Minesweeper
# ---------------------------------------------------------------------------

class MinesweeperDialog(GridGameDialog):
    ROWS = COLS = 8
    _LEVELS = list(minesweeper.LEVELS)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech, "كاسحة الألغام", size=(700, 620))
        self._rng = random.Random()
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label="المستوى:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.levelChoice = wx.Choice(panel, choices=[minesweeper.LEVELS[k][0] for k in self._LEVELS])
        self.levelChoice.SetName("المستوى")
        self.levelChoice.SetSelection(1)
        row.Add(self.levelChoice, 0)
        s.Add(row, 0, wx.ALL, 6)
        self.build_grid(panel, s)
        self.grid.Unbind(wx.EVT_KEY_DOWN)
        self.grid.Bind(wx.EVT_KEY_DOWN, self._on_key)
        btns = wx.BoxSizer(wx.HORIZONTAL)
        for label, h in (("لعبة جديدة", self._new), ("تلميح (H)", self._hint),
                         ("الألغام الباقية", self._remaining), ("إغلاق", self.close_screen)):
            btns.Add(self.button(panel, label, lambda e, f=h: f()), 0, wx.ALL, 3)
        s.Add(btns, 0, wx.ALL, 4)
        panel.SetSizer(s)
        self.set_first_control(self.grid)
        self.field = None
        self.call_after(self._new, True)

    def addr(self, r, c):
        return f"صفّ {r + 1} عمود {c + 1}"

    def cell_word(self, r, c):
        return self.field.cell_word(r, c) if self.field else ""

    def _new(self, quiet: bool = False) -> None:
        key = self._LEVELS[self.choice_index(self.levelChoice, 1)]
        self.field = minesweeper.Minefield.level(key, self._rng)
        self.ROWS, self.COLS = self.field.rows, self.field.cols
        self._row = self._col = self.field.rows // 2
        self._start = time.monotonic()
        self.refresh_grid()
        self.grid.SetFocus()
        msg = (f"لوح {self.field.rows} في {self.field.cols} فيه {count(self.field.mines, 'mine')}. "
               f"أول خانة تفتحها آمنة دائمًا.")
        if quiet:
            self.status.SetLabel(msg)
        else:
            self.say(msg)

    def activate(self, r, c):
        f = self.field
        if f.lost or f.won:
            self.announce("انتهت اللعبة. اضغط لعبة جديدة.")
            return
        if (r, c) in f.open:
            res = f.chord(r, c)
        else:
            res = f.reveal(r, c)
        self.refresh_grid()
        if res == "boom":
            self.say("انفجر لغم! خسرت. " + self.addr(r, c))
        elif res == "won":
            secs = int(time.monotonic() - self._start)
            self.say(f"فزت! كشفت كلّ الخانات الآمنة في {_elapsed(self._start)}.")
            key = f"mines_{self._LEVELS[self.choice_index(self.levelChoice, 1)]}"
            if save_score(self.academy, key, secs, higher_is_better=False):
                self.announce("رقم قياسي جديد!")
        elif res == "flagged":
            self.announce("عليها علم. أزله بـ F أولًا.")
        elif res == "already":
            self.announce(self.cell_word(r, c))
        else:
            opened = len(f.open)
            self.announce(f"{self.cell_word(r, c)}. المفتوح {count(opened, 'cell')}.")

    def _on_key(self, evt) -> None:
        code = evt.GetKeyCode()
        if self.field is None:
            evt.Skip()
            return
        if code in (ord("F"), ord("f")) and not evt.ControlDown():
            res = self.field.toggle_flag(self._row, self._col)
            if res is None:
                self.announce("لا يمكن وضع علم هنا.")
            else:
                self.refresh_grid()
                self.announce(("وُضع علم. " if res else "أُزيل العلم. ") +
                              f"الباقي {ar(self.field.remaining())}.")
            return
        if code in (ord("D"), ord("d")) and not evt.ControlDown():
            self.announce(self.field.describe_neighbourhood(self._row, self._col))
            return
        if code in (ord("H"), ord("h")) and not evt.ControlDown():
            self._hint()
            return
        self._on_grid_key(evt)

    def _hint(self) -> None:
        h = self.field.safe_hint() if self.field else None
        if not h:
            self.announce("لا أستطيع استنتاج خانة مؤكّدة الآن؛ قد تحتاج إلى مخاطرة.")
            return
        r, c, kind = h
        self.set_cursor(r, c)
        self.announce(f"{self.addr(r, c)}: " + ("آمنة بالتأكيد، افتحها." if kind == "safe"
                                                else "فيها لغم بالتأكيد، ضع عليها علمًا."))

    def _remaining(self) -> None:
        if self.field:
            self.announce(f"الألغام غير المعلّمة: {ar(self.field.remaining())}.")

    def instructions(self) -> str:
        return ("كاسحة الألغام: الأسهم للتنقّل، المسافة أو Enter لفتح خانة، F لوضع علم، "
                "D لوصف الخانات الثماني المجاورة، H لتلميح منطقي. الرقم في الخانة يعني عدد "
                "الألغام حولها. فتح رقم اكتملت أعلامه يفتح ما حوله.")


# ---------------------------------------------------------------------------
# 2048 and the sliding puzzle
# ---------------------------------------------------------------------------

_ARROWS = {}
if wx is not None:
    _ARROWS = {wx.WXK_UP: "up", wx.WXK_DOWN: "down", wx.WXK_LEFT: "left", wx.WXK_RIGHT: "right"}


class _BoardDialog(AccessibleDialog):
    TITLE = ""

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(640, 520))
        self.academy = academy
        self._rng = random.Random()
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(panel, label="")
        s.Add(self.status, 0, wx.ALL, 8)
        self._extra(panel, s)
        self.board = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.board.SetName("اللوح: الأسهم للتحريك")
        self.board.Bind(wx.EVT_KEY_DOWN, self._on_key)
        s.Add(self.board, 1, wx.EXPAND | wx.ALL, 6)
        btns = wx.BoxSizer(wx.HORIZONTAL)
        for label, h in self._buttons():
            btns.Add(self.button(panel, label, lambda e, f=h: f()), 0, wx.ALL, 3)
        btns.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(btns, 0, wx.ALL, 4)
        panel.SetSizer(s)
        self.set_first_control(self.board)
        self.call_after(self._new, True)

    def _extra(self, panel, sizer) -> None:
        pass

    def _buttons(self):
        return [("لعبة جديدة", self._new)]

    def _lines(self):
        return []

    def _show(self) -> None:
        lines = self._lines()
        sel = self.board.GetSelection()
        self.board.Set(lines)
        self.select_index(self.board, sel if 0 <= sel < len(lines) else 0)

    def say(self, text) -> None:
        self.status.SetLabel(text)
        self.announce(text)

    def _on_key(self, evt) -> None:
        d = _ARROWS.get(evt.GetKeyCode())
        if d and not evt.ControlDown():
            self._move(d)
            return
        if evt.GetKeyCode() in (ord("R"), ord("r")):
            self.announce("، ".join(self._lines()))
            return
        if evt.GetKeyCode() in (ord("H"), ord("h")):
            self._hint()
            return
        if evt.ControlDown() and evt.GetKeyCode() in (ord("Z"), ord("z")):
            self._undo()
            return
        evt.Skip()

    def _move(self, d) -> None:
        pass

    def _hint(self) -> None:
        self.announce("لا تلميح في هذه اللعبة.")

    def _undo(self) -> None:
        self.announce("لا تراجع في هذه اللعبة.")

    def _new(self, quiet: bool = False) -> None:
        pass


class Game2048Dialog(_BoardDialog):
    TITLE = "٢٠٤٨"

    def _buttons(self):
        return [("لعبة جديدة", self._new), ("اقرأ اللوح (R)", lambda: self.announce("، ".join(self._lines()))),
                ("تراجع (Ctrl+Z)", self._undo)]

    def _new(self, quiet: bool = False) -> None:
        self.game = tiles.Game2048(rng=self._rng)
        self._show()
        self.board.SetFocus()
        msg = "لعبة جديدة. حرّك بالأسهم لدمج الأرقام المتساوية حتى تصل إلى ٢٠٤٨. R لقراءة اللوح."
        if quiet:
            self.status.SetLabel(msg)
        else:
            self.say(msg)

    def _lines(self):
        g = getattr(self, "game", None)
        if g is None:
            return []
        return [f"الصفّ {r + 1}: {g.row_text(r)}" for r in range(g.size)] + \
               [f"النقاط {g.score}، أكبر رقم {g.best_tile}"]

    def _move(self, d) -> None:
        g = self.game
        had_target = g.reached_target
        res = g.move(d)
        self._show()
        msg = g.describe_move(d, res)
        if g.reached_target and not had_target:
            msg += " وصلت إلى ٢٠٤٨! أحسنت، يمكنك المتابعة."
        if not g.can_move():
            msg += f" لا حركات متبقّية. انتهت اللعبة بـ {g.score} نقطة."
            if save_score(self.academy, "g2048", g.score, True):
                msg += " رقم قياسي جديد!"
        self.announce(msg)

    def _undo(self) -> None:
        if self.game.undo():
            self._show()
            self.announce("تراجعت. " + "، ".join(self._lines()[:-1]))
        else:
            self.announce("لا شيء للتراجع.")

    def instructions(self) -> str:
        return ("٢٠٤٨: الأسهم تحرّك كلّ البلاطات، والمتساوية تندمج. يُعلن بعد كلّ حركة ما اندمج "
                "وأين ظهرت البلاطة الجديدة. R لقراءة اللوح، Ctrl+Z للتراجع.")


class SlidingPuzzleDialog(_BoardDialog):
    TITLE = "لغز الأرقام المنزلقة"

    def _extra(self, panel, sizer) -> None:
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label="الحجم:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.sizeChoice = wx.Choice(panel, choices=["٣×٣ (ثمانية أرقام)", "٤×٤ (خمسة عشر رقمًا)"])
        self.sizeChoice.SetName("حجم اللغز")
        self.sizeChoice.SetSelection(0)
        row.Add(self.sizeChoice, 0)
        sizer.Add(row, 0, wx.ALL, 6)

    def _buttons(self):
        return [("لعبة جديدة", self._new), ("أين الفراغ؟", lambda: self.announce(self.p.gap_text())),
                ("تلميح (H)", self._hint)]

    def _new(self, quiet: bool = False) -> None:
        n = 3 if self.choice_index(self.sizeChoice) == 0 else 4
        self.p = tiles.SlidingPuzzle(n, self._rng)
        self._start = time.monotonic()
        self._show()
        self.board.SetFocus()
        msg = (f"رتّب الأرقام من ١ إلى {n * n - 1} صفًّا صفًّا والفراغ في الأخير. "
               f"السهم يحرّك البلاطة المجاورة إلى الفراغ. {self.p.gap_text()}")
        if quiet:
            self.status.SetLabel(msg)
        else:
            self.say(msg)

    def _lines(self):
        p = getattr(self, "p", None)
        if p is None:
            return []
        return [f"الصفّ {r + 1}: {p.row_text(r)}" for r in range(p.size)] + \
               [f"الحركات {p.moves}، في غير مكانها {p.misplaced()}"]

    def _move(self, d) -> None:
        tile = self.p.move(d)
        if tile is None:
            self.announce("لا بلاطة في هذا الاتجاه. " + self.p.gap_text())
            return
        self._show()
        if self.p.solved():
            secs = int(time.monotonic() - self._start)
            self.say(f"حللت اللغز في {count(self.p.moves, 'move')} و{_elapsed(self._start)}!")
            save_score(self.academy, f"sliding_{self.p.size}", self.p.moves, higher_is_better=False)
            return
        self.announce(f"حُرّك {tile}. {self.p.gap_text()}")

    def _hint(self) -> None:
        d = self.p.suggest()
        if d is None:
            self.announce("التلميح متاح للوح ٣×٣ فقط." if self.p.size > 3 else "اللغز محلول.")
            return
        from ..puzzles.tiles import ARROW_WORDS
        self.announce(f"اضغط السهم {ARROW_WORDS[d]}.")

    def instructions(self) -> str:
        return ("لغز الأرقام المنزلقة: السهم يحرّك البلاطة المجاورة للفراغ نحوه. R لقراءة اللوح، "
                "H لتلميح الحركة التالية في الحلّ الأقصر (للوح ٣×٣).")
