# -*- coding: utf-8 -*-
"""
abaAcademy.gui.chess_accessible
===============================

Accessible chess against the built-in engine. The board is explored by moving a
cursor with the arrow keys (each square announces its file, rank and any piece);
moves are entered by choosing a from-square and a to-square (Enter on the cursor
square selects it, Enter on a destination plays the move). The player can ask for
the list of legal moves for the selected piece, hear whether they are in check,
and get a threat report on the current square.

The opponent is the pure-Python engine in ``chess_engine`` — a real, legal,
beginner-to-club-strength AI (not Stockfish; the UI says so). Three levels set
the search depth.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..chess_engine.board import Board, WHITE, BLACK
from ..chess_engine.arabic_notation import (
    square_name, describe_square, describe_move, piece_name, PIECE_AR,
)


class ChessDialog(AccessibleDialog):
    TITLE = "الشطرنج الميسّر"

    LEVELS = [("مبتدئ", 1), ("متوسّط", 2), ("متقدّم", 3)]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 560))
        self.academy = academy
        self._board = Board()
        self._cursor = 12          # e2-ish start
        self._selected = None      # from-square when a piece is picked up
        self._human = WHITE
        self._thinking = False

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "تنقّل بالأسهم بين الخانات، اضغط Enter على قطعتك لاختيارها ثم Enter على "
            "الوجهة للّعب. أنت باللون الأبيض. اللاعب الآليّ محرّك مدمج بمستوى مبتدئ.")),
            0, wx.ALL, 6)

        lrow = wx.BoxSizer(wx.HORIZONTAL)
        lrow.Add(wx.StaticText(panel, label="المستوى:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.levelChoice = wx.Choice(panel, choices=[n for n, _ in self.LEVELS])
        self.levelChoice.SetSelection(0)
        self.bind_choice(self.levelChoice, lambda e: self._new_game())
        lrow.Add(self.levelChoice, 0)
        s.Add(lrow, 0, wx.ALL, 6)

        self.pad = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 70))
        self.pad.SetName("رقعة الشطرنج")
        s.Add(self.pad, 0, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(680)
        s.Add(self.status, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "حركات هذه القطعة (M)", lambda e: self._say_piece_moves()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "هل أنا في كش؟ (C)", lambda e: self._say_check()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "تهديدات هذه الخانة (T)", lambda e: self._say_threats()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "مباراة جديدة", lambda e: self._new_game()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.pad.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.set_first_control(self.pad)
        wx.CallAfter(self._new_game)

    # -- game -------------------------------------------------------------
    def _new_game(self):
        self._board = Board()
        self._cursor = 12
        self._selected = None
        self._thinking = False
        lvl = self.LEVELS[self.choice_index(self.levelChoice)][0]
        self._say(f"مباراة جديدة. أنت الأبيض وتبدأ. المستوى {lvl}. "
                  f"المؤشّر على {describe_square(self._board, self._cursor)}.")
        wx.CallAfter(self.pad.SetFocus)

    def _on_key(self, evt):
        if self._thinking:
            return
        code = evt.GetKeyCode()
        f, r = self._board.fr(self._cursor)
        if code == wx.WXK_UP and r < 7:
            self._cursor += 8; self._announce_cursor()
        elif code == wx.WXK_DOWN and r > 0:
            self._cursor -= 8; self._announce_cursor()
        elif code == wx.WXK_RIGHT and f < 7:
            self._cursor += 1; self._announce_cursor()
        elif code == wx.WXK_LEFT and f > 0:
            self._cursor -= 1; self._announce_cursor()
        elif code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._activate()
        elif code in (ord("M"), ord("m")):
            self._say_piece_moves()
        elif code in (ord("C"), ord("c")):
            self._say_check()
        elif code in (ord("T"), ord("t")):
            self._say_threats()
        else:
            evt.Skip()

    def _announce_cursor(self):
        extra = ""
        if self._selected is not None:
            extra = " (لديك قطعة مختارة، اضغط Enter للّعب هنا)"
        self.announce(describe_square(self._board, self._cursor) + extra)

    def _activate(self):
        if self._board.turn != self._human:
            self._say("ليس دورك.")
            return
        if self._selected is None:
            # pick up a piece
            p = self._board.squares[self._cursor]
            if p is None or self._board.color_of(p) != self._human:
                self._say("اختر قطعةً من قطعك أولاً.")
                return
            self._selected = self._cursor
            self._say(f"اخترت {piece_name(p)} في {square_name(self._cursor)}. "
                      f"تنقّل إلى الوجهة واضغط Enter.")
        else:
            # try to move selected -> cursor
            mv = self._find_move(self._selected, self._cursor)
            if mv is None:
                # maybe they're reselecting another of their pieces
                p = self._board.squares[self._cursor]
                if p is not None and self._board.color_of(p) == self._human:
                    self._selected = self._cursor
                    self._say(f"اخترت {piece_name(p)} في {square_name(self._cursor)}.")
                else:
                    self._say("حركة غير قانونية. اختر وجهةً صحيحة، أو قطعةً أخرى.")
                return
            desc = describe_move(self._board, mv)
            self._board = self._board.apply(mv)
            self._selected = None
            self._say(f"لعبت: {desc}.")
            wx.CallLater(400, self._after_human)

    def _after_human(self):
        st = self._board.status()
        if st != "ongoing":
            self._announce_end(st, human_moved=True)
            return
        self._ai_turn()

    def _ai_turn(self):
        self._thinking = True
        self._say("يفكّر الحاسوب…")
        depth = self.LEVELS[self.choice_index(self.levelChoice)][1]
        # run search then apply; keep UI responsive via CallAfter
        wx.CallAfter(self._do_ai_move, depth)

    def _do_ai_move(self, depth):
        mv = self._board.best_move(depth=depth)
        self._thinking = False
        if mv is None:
            self._announce_end(self._board.status(), human_moved=False)
            return
        desc = describe_move(self._board, mv)
        self._board = self._board.apply(mv)
        st = self._board.status()
        if st != "ongoing":
            self._say(f"لعب الحاسوب: {desc}.")
            self._announce_end(st, human_moved=False)
        else:
            check = " أنت في كش!" if self._board.in_check() else ""
            self._say(f"لعب الحاسوب: {desc}.{check} دورك.")

    def _announce_end(self, st, human_moved):
        if st == "checkmate":
            # side to move is checkmated
            loser = self._board.turn
            if loser == self._human:
                self._say("كش مات. فاز الحاسوب. مباراة جديدة؟")
            else:
                self._say("كش مات! فزت. أحسنت! مباراة جديدة؟")
        elif st == "stalemate":
            self._say("جمود، تعادل. مباراة جديدة؟")
        else:
            self._say("تعادل. مباراة جديدة؟")

    # -- queries ----------------------------------------------------------
    def _find_move(self, frm, to):
        for mv in self._board.legal_moves():
            if mv.frm == frm and mv.to == to:
                return mv
        return None

    def _say_piece_moves(self):
        p = self._board.squares[self._cursor]
        if p is None:
            self._say("الخانة فارغة.")
            return
        dests = [square_name(m.to) for m in self._board.legal_moves()
                 if m.frm == self._cursor]
        if not dests:
            self._say(f"{piece_name(p)}: لا حركات متاحة.")
        else:
            self._say(f"{piece_name(p)} يمكنها الذهاب إلى: " + "، ".join(dests) + ".")

    def _say_check(self):
        if self._board.in_check():
            self._say("نعم، أنت في كش. يجب أن تحمي ملكك.")
        else:
            self._say("لا، لست في كش.")

    def _say_threats(self):
        f, r = self._board.fr(self._cursor)
        p = self._board.squares[self._cursor]
        attacked = self._board._square_attacked(f, r, self._human)
        who = piece_name(p) if p else "الخانة"
        if attacked:
            self._say(f"{who} في {square_name(self._cursor)} مهدَّدة من الخصم.")
        else:
            self._say(f"{who} في {square_name(self._cursor)} غير مهدَّدة.")

    def on_closing(self):
        pass

    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def on_repeat(self):
        self._announce_cursor()

    def instructions(self):
        return ("الشطرنج الميسّر: تنقّل بين الخانات بالأسهم الأربعة؛ كل خانة تُنطق بحرفها "
                "ورقمها وما عليها. اضغط Enter على إحدى قطعك لاختيارها، ثم تنقّل إلى الوجهة "
                "واضغط Enter للّعب. حرف M يذكر حركات القطعة الحالية، C يخبرك إن كنت في كش، "
                "T يذكر تهديدات الخانة الحالية. أنت الأبيض. اللاعب الآليّ محرّك شطرنج مدمج "
                "(ليس ستوكفيش) بثلاثة مستويات. Escape للإغلاق.")
