# -*- coding: utf-8 -*-
"""
abaAcademy.chess_game
=====================

الشطرنج المسموع — chess against the sunfish engine (Thomas Ahle, GPL-3.0,
bundled in abaAcademy/thirdparty/sunfish), described entirely in Arabic for
a learner who plays by ear: every legal move is listed in words, the board
can be read square by square, rank by rank or piece by piece, and every
move, capture, check and the end of the game is announced.

The engine thinks from the side to move, with the board turned round when
it is black's turn; this module keeps every square name from white's side.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

_TP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thirdparty")
if _TP not in sys.path:
    sys.path.insert(0, _TP)

from sunfish import sunfish as sf  # noqa: E402

NAMES = {"P": "البيدق", "N": "الحصان", "B": "الفيل", "R": "الرخّ", "Q": "الوزير", "K": "الملك"}
BARE = {"P": "بيدق", "N": "حصان", "B": "فيل", "R": "رخّ", "Q": "وزير", "K": "ملك"}
PROMO = {"Q": "وزير", "R": "رخّ", "B": "فيل", "N": "حصان"}
LEVELS = [("مبتدئ", 0.15), ("متوسّط", 0.6), ("قويّ", 2.0)]


def square(i: int) -> str:
    return sf.render(i)


@dataclass
class MoveInfo:
    move: "sf.Move"
    text: str
    uci: str


class ChessGame:
    def __init__(self, human_white: bool = True, level: int = 0):
        self.hist = [sf.Position(sf.initial, 0, (True, True), (True, True), 0, 0)]
        self.human_white = human_white
        self.level = level
        self.log: List[str] = []
        self.searcher = sf.Searcher()

    @property
    def pos(self):
        return self.hist[-1]

    @property
    def white_to_move(self) -> bool:
        return len(self.hist) % 2 == 1

    @property
    def human_to_move(self) -> bool:
        return self.white_to_move == self.human_white

    def _abs(self, i: int) -> int:
        return i if self.white_to_move else 119 - i

    def white_board(self) -> str:
        return self.pos.board if self.white_to_move else self.pos.board[::-1].swapcase()

    def legal_moves(self) -> List[MoveInfo]:
        out = []
        board = self.pos.board
        for m in self.pos.gen_moves():
            if self.pos.move(m).king_capture() is not None:
                continue
            out.append(MoveInfo(m, self.describe(m), self.uci(m)))
        out.sort(key=lambda x: ("KQRBNP".index(board[x.move.i]), x.uci))
        return out

    def uci(self, m) -> str:
        return square(self._abs(m.i)) + square(self._abs(m.j)) + m.prom.lower()

    def describe(self, m) -> str:
        b = self.pos.board
        p, q = b[m.i], b[m.j]
        a, z = square(self._abs(m.i)), square(self._abs(m.j))
        if p == "K" and abs(m.j - m.i) == 2:
            text = "التبييت القصير" if z[0] == "g" else "التبييت الطويل"
        else:
            text = f"{NAMES[p]} من {a} إلى {z}"
            if q in "pnbrqk":
                text += f" ويأخذ {NAMES[q.upper()]}"
            elif p == "P" and m.j == self.pos.ep:
                text += " ويأخذ البيدق بالمرور"
            if m.prom:
                text += f" ويترقّى إلى {PROMO[m.prom]}"
        after = self.pos.move(m)
        if after.rotate(nullmove=True).king_capture() is not None:
            text += "، كِش"
        return text

    def find(self, text: str) -> Optional[MoveInfo]:
        t = text.strip().lower().replace(" ", "").replace("-", "")
        for mv in self.legal_moves():
            if mv.uci == t or (len(t) == 4 and mv.uci[:4] == t and mv.move.prom in ("", "Q")):
                return mv
        return None

    def play(self, mv: MoveInfo) -> str:
        who = "الأبيض" if self.white_to_move else "الأسود"
        self.log.append(f"{who}: {mv.text}")
        self.hist.append(self.pos.move(mv.move))
        return mv.text

    def undo(self) -> bool:
        """Take back the last full move (the engine's reply and yours)."""
        n = 2 if len(self.hist) >= 3 else 0
        if not n:
            return False
        del self.hist[-n:]
        del self.log[-n:]
        return True

    def status(self) -> Tuple[str, bool]:
        side = "الأبيض" if self.white_to_move else "الأسود"
        in_check = self.pos.rotate(nullmove=True).king_capture() is not None
        if not self.legal_moves():
            if in_check:
                winner = "الأسود" if self.white_to_move else "الأبيض"
                return f"كِش مات. فاز {winner}.", True
            return f"تعادل بالجمود: لا حركة قانونية لـ{side} وملكه غير مهدّد.", True
        if sum(1 for c in self.pos.board if c in "PNBRQpnbrq") == 0:
            return "تعادل: لم يبقَ إلا الملكان.", True
        return (f"دور {side}" + ("، وملكه في كِش." if in_check else "."), False)

    def engine_move(self) -> Optional[MoveInfo]:
        budget = LEVELS[self.level][1]
        start = time.time()
        legal = {(m.move.i, m.move.j, m.move.prom): m for m in self.legal_moves()}
        if not legal:
            return None
        best = None
        for depth, gamma, score, move in self.searcher.search(self.hist):
            if move is not None and (move.i, move.j, move.prom) in legal:
                best = legal[(move.i, move.j, move.prom)]
            if time.time() - start > budget and best is not None:
                break
        return best or next(iter(legal.values()))

    def piece_at(self, sq: str) -> str:
        sq = sq.strip().lower()
        if len(sq) != 2 or sq[0] not in "abcdefgh" or sq[1] not in "12345678":
            return "اكتب مربّعًا مثل e4."
        c = self.white_board()[sf.parse(sq)]
        if c == ".":
            return f"{sq}: فارغ."
        return f"{sq}: {BARE[c.upper()]} {'أبيض' if c.isupper() else 'أسود'}."

    def pieces(self, white: bool) -> str:
        b = self.white_board()
        groups = {}
        for i, c in enumerate(b):
            if (c in "PNBRQK") if white else (c in "pnbrqk"):
                groups.setdefault(c.upper(), []).append(square(i))
        side = "الأبيض" if white else "الأسود"
        parts = [f"{NAMES[k]} على {'، '.join(sorted(groups[k]))}" for k in "KQRBNP" if k in groups]
        return f"قطع {side}: " + "؛ ".join(parts) + "."

    def rank(self, n: int) -> str:
        b = self.white_board()
        cells = []
        for f in "abcdefgh":
            c = b[sf.parse(f"{f}{n}")]
            cells.append(f"{f}{n} " + ("فارغ" if c == "." else f"{BARE[c.upper()]} {'أبيض' if c.isupper() else 'أسود'}"))
        return f"الصفّ {n}: " + "، ".join(cells) + "."
