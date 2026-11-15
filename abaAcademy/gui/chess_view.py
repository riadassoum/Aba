# -*- coding: utf-8 -*-
"""
abaAcademy.gui.chess_view
=========================

الشطرنج المسموع — play chess against the sunfish engine by ear. The legal
moves are a list read in Arabic (Enter plays one), or type a move such as
e2e4. Read the board by piece, by rank or by square at any time; hear the
engine's reply, captures, check and the end of the game.
"""

from __future__ import annotations

import threading

import wx

from ..chess_game import LEVELS, ChessGame
from .tool_base import ToolDialog


class ChessDialog(ToolDialog):
    TITLE = "الشطرنج المسموع"
    SIZE = (820, 660)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.add_text("العب الشطرنج بالسمع ضدّ محرّك sunfish المفتوح. كل حركة قانونية مكتوبة بالعربية في القائمة، "
                      "أو اكتب الحركة بالمربّعين مثل e2e4. والرقعة تُقرأ بالقطع أو بالصفوف أو بالمربّع.")
        self.levelChoice = self.add_choice("المستوى", [n for n, _ in LEVELS], int(self.setting("level", 0) or 0))
        self.colorChoice = self.add_choice("ألعب بـ", ["الأبيض (أبدأ)", "الأسود"], 0)
        self.add_buttons([("لعبة جديدة", self._new)], close=False)
        self.moveList = self.add_list("حركاتك القانونية (Enter للعب)", [], height=170, on_activate=self._play_selected)
        self.moveEntry = self.add_entry("أو اكتب الحركة، مثل e2e4، ثم Enter", on_enter=self._play_typed)
        self.squareEntry = self.add_entry("اسأل عن مربّع أو صفّ: e4 أو 7، ثم Enter", on_enter=self._ask)
        self.add_buttons([("قطعي", lambda: self._say(self.game.pieces(self.game.human_white))),
                          ("قطع الخصم", lambda: self._say(self.game.pieces(not self.game.human_white))),
                          ("آخر الحركات", self._history), ("تراجع عن حركة", self._undo),
                          ("الحالة", lambda: self._say(self.game.status()[0]))], close=False)
        self.out = self.add_output("سير اللعبة", height=110)
        self.add_buttons([])
        self.thinking = False
        self.finish(self.moveList)
        self._new(speak=False)

    def instructions(self) -> str:
        return ("تنقّل في قائمة الحركات بالأسهم واضغط Enter لتلعب الحركة، أو اكتبها بالمربّعين مثل g1f3. "
                "اكتب مربّعًا مثل d4 لتعرف ما عليه، أو رقم صفّ من 1 إلى 8 لتسمع الصفّ كله. "
                "زرّ قطعي وقطع الخصم يقرأ مواضع القطع.")

    # -- game flow -------------------------------------------------------------

    def _new(self, speak=True):
        level = self.levelChoice.GetSelection()
        self.set_setting("level", level)
        self.game = ChessGame(human_white=self.colorChoice.GetSelection() == 0, level=level)
        self.out.SetValue("")
        if self.game.human_to_move:
            self._refresh(("لعبة جديدة. أنت بالأبيض، دورك." if speak else None))
        else:
            self._refresh("لعبة جديدة. أنت بالأسود، والمحرّك يفكّر." if speak else None)
            self._engine()

    def _refresh(self, say=None):
        moves = self.game.legal_moves() if self.game.human_to_move else []
        self._moves = moves
        self.moveList.Set([m.text for m in moves])
        if moves:
            self.moveList.SetSelection(0)
        self.out.SetValue("\n".join(self.game.log[-12:]))
        if say:
            self._say(say)

    def _after_move(self, text, by_engine):
        status, over = self.game.status()
        prefix = "المحرّك: " if by_engine else ""
        if over:
            self._refresh(f"{prefix}{text}. {status}")
            return
        if by_engine:
            self._refresh(f"{prefix}{text}. دورك.")
        else:
            self._refresh(None)
            self._engine()

    def _play(self, mv):
        if self.thinking or not self.game.human_to_move:
            self._say("انتظر، المحرّك يفكّر.")
            return
        text = self.game.play(mv)
        self._say(text)
        self._after_move(text, False)

    def _play_selected(self, evt=None):
        i = self.moveList.GetSelection()
        if 0 <= i < len(self._moves):
            self._play(self._moves[i])

    def _play_typed(self):
        t = self.moveEntry.GetValue()
        mv = self.game.find(t)
        self.moveEntry.SetValue("")
        if mv is None:
            self._say("ليست حركة قانونية. اكتب المربّعين مثل e2e4.")
            return
        self._play(mv)

    def _engine(self):
        if self.game.status()[1]:
            return
        self.thinking = True

        def work():
            mv = self.game.engine_move()
            wx.CallAfter(self._engine_done, mv)
        threading.Thread(target=work, daemon=True).start()

    def _engine_done(self, mv):
        self.thinking = False
        if not self or mv is None:
            return
        text = self.game.play(mv)
        self._after_move(text, True)

    # -- reading ---------------------------------------------------------------

    def _ask(self):
        t = self.squareEntry.GetValue().strip()
        self.squareEntry.SetValue("")
        if t.isdigit() and 1 <= int(t) <= 8:
            self._say(self.game.rank(int(t)))
        else:
            self._say(self.game.piece_at(t))

    def _history(self):
        log = self.game.log[-6:]
        self._say("، ثم ".join(log) if log else "لم تبدأ اللعبة بعد.")

    def _undo(self):
        if self.thinking:
            return
        if self.game.undo():
            self._refresh("تراجعت عن آخر حركة لك وردّ المحرّك عليها.")
        else:
            self._say("لا حركة للتراجع عنها.")

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.moveList:
            self._play_selected()
            return True
        if focus is self.moveEntry:
            self._play_typed()
            return True
        if focus is self.squareEntry:
            self._ask()
            return True
        return False
