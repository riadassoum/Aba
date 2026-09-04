# -*- coding: utf-8 -*-
"""
abaAcademy.chess_engine.arabic_notation
=======================================

Turn board squares and moves into spoken Arabic for the accessible chess screen:
square names ("e4" -> "e ٤"), piece names, and full move descriptions with
capture / check / castle information. Squares are read with the Latin file letter
(a-h, universally used on talking chess boards) and an Arabic-Indic rank number,
which is what Arabic-speaking blind players are accustomed to.
"""

from __future__ import annotations

_FILES = "abcdefgh"
_RANK_AR = {0: "١", 1: "٢", 2: "٣", 3: "٤", 4: "٥", 5: "٦", 6: "٧", 7: "٨"}

PIECE_AR = {
    "P": "بيدق", "N": "حصان", "B": "فيل", "R": "قلعة", "Q": "وزير", "K": "ملك",
}


def square_name(idx):
    """0..63 -> 'e ٤' style spoken name."""
    f = idx % 8
    r = idx // 8
    return f"{_FILES[f]} {_RANK_AR[r]}"


def piece_name(piece):
    if piece is None:
        return "فارغة"
    name = PIECE_AR[piece.upper()]
    color = "أبيض" if piece.isupper() else "أسود"
    return f"{name} {color}"


def describe_square(board, idx):
    """What is on a square, for cursor navigation."""
    p = board.squares[idx]
    if p is None:
        return f"{square_name(idx)}: فارغة"
    return f"{square_name(idx)}: {piece_name(p)}"


def describe_move(board, mv):
    """Full spoken description of a move about to be / just played."""
    p = board.squares[mv.frm]
    captured = board.squares[mv.to]
    parts = [PIECE_AR[p.upper()]]
    parts.append(f"من {square_name(mv.frm)}")
    if mv.is_castle:
        side = "الجناح الملكي" if (mv.to % 8) == 6 else "جناح الوزير"
        return f"تبييت نحو {side}"
    if captured is not None or mv.is_ep:
        parts.append(f"يأخذ في {square_name(mv.to)}")
        if captured is not None:
            parts.append(f"({PIECE_AR[captured.upper()]})")
    else:
        parts.append(f"إلى {square_name(mv.to)}")
    if mv.promo:
        parts.append(f"ويترقّى إلى {PIECE_AR[mv.promo]}")
    # check / mate after the move
    nb = board.apply(mv)
    st = nb.status()
    if st == "checkmate":
        parts.append("كش ملك، انتهت المباراة")
    elif nb.in_check():
        parts.append("كش")
    return " ".join(parts)


def parse_square(text):
    """Parse a typed square like 'e4' / 'E4' / 'e ٤' into a 0..63 index, or None."""
    text = text.strip().lower().replace(" ", "")
    # normalise Arabic-Indic digits
    text = text.translate(str.maketrans("١٢٣٤٥٦٧٨", "12345678"))
    if len(text) < 2:
        return None
    f = text[0]
    r = text[1]
    if f not in _FILES or not r.isdigit():
        return None
    rank = int(r) - 1
    if not (0 <= rank < 8):
        return None
    return rank * 8 + _FILES.index(f)
