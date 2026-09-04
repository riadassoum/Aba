# -*- coding: utf-8 -*-
"""Tests for the pure-Python chess engine: move generation, special moves, check
and mate detection, and that the AI only ever returns legal moves."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.chess_engine.board import Board, WHITE, BLACK
from abaAcademy.chess_engine.arabic_notation import parse_square, square_name


def _mv(board, frm_fr, to_fr):
    fi = board.idx(*frm_fr)
    ti = board.idx(*to_fr)
    for m in board.legal_moves():
        if m.frm == fi and m.to == ti:
            return m
    return None


class TestChessRules(unittest.TestCase):
    def test_initial_move_count(self):
        self.assertEqual(len(Board().legal_moves()), 20)

    def test_turn_alternates(self):
        b = Board()
        b2 = b.apply(_mv(b, (4, 1), (4, 3)))
        self.assertEqual(b2.turn, BLACK)

    def test_no_illegal_leaves_king_in_check(self):
        # every generated move must leave own king safe
        b = Board()
        for mv in b.legal_moves():
            nb = b.apply(mv)
            self.assertFalse(nb._king_attacked(WHITE),
                             "a legal move left the white king in check")

    def test_castling_kingside(self):
        b = Board()
        b.squares[b.idx(5, 0)] = None
        b.squares[b.idx(6, 0)] = None
        castles = [m for m in b.legal_moves() if m.is_castle and m.to == b.idx(6, 0)]
        self.assertEqual(len(castles), 1)

    def test_en_passant(self):
        b = Board()
        for frm, to in [((4, 1), (4, 3)), ((0, 6), (0, 4)),
                        ((4, 3), (4, 4)), ((3, 6), (3, 4))]:
            b = b.apply(_mv(b, frm, to))
        eps = [m for m in b.legal_moves() if m.is_ep]
        self.assertEqual(len(eps), 1)

    def test_promotion_four_options(self):
        b = Board()
        b.squares = [None] * 64
        b.squares[b.idx(4, 0)] = "K"
        b.squares[b.idx(4, 7)] = "k"
        b.squares[b.idx(0, 6)] = "P"
        b.turn = WHITE
        promos = [m for m in b.legal_moves() if m.promo]
        self.assertEqual(len(promos), 4)

    def test_fools_mate_is_checkmate(self):
        b = Board()
        for frm, to in [((5, 1), (5, 2)), ((4, 6), (4, 4)),
                        ((6, 1), (6, 3)), ((3, 7), (7, 3))]:
            b = b.apply(_mv(b, frm, to))
        self.assertEqual(b.status(), "checkmate")

    def test_stalemate(self):
        b = Board()
        b.squares = [None] * 64
        b.squares[b.idx(0, 0)] = "k"
        b.squares[b.idx(2, 1)] = "Q"
        b.squares[b.idx(1, 2)] = "K"
        b.turn = BLACK
        self.assertEqual(b.status(), "stalemate")

    def test_ai_returns_legal_move(self):
        b = Board()
        for depth in (1, 2, 3):
            mv = b.best_move(depth=depth)
            self.assertIn(mv, b.legal_moves())

    def test_ai_takes_free_queen(self):
        # white to move; black queen hangs on d5, white pawn on e4 can take it
        b = Board()
        b.squares = [None] * 64
        b.squares[b.idx(4, 0)] = "K"
        b.squares[b.idx(4, 7)] = "k"
        b.squares[b.idx(4, 3)] = "P"   # e4
        b.squares[b.idx(3, 4)] = "q"   # d5 black queen, capturable by exd5
        b.turn = WHITE
        mv = b.best_move(depth=2)
        self.assertEqual(mv.to, b.idx(3, 4), "AI failed to capture a free queen")


class TestNotation(unittest.TestCase):
    def test_square_name(self):
        self.assertEqual(square_name(28), "e \u0664")   # e4

    def test_parse_square(self):
        self.assertEqual(parse_square("e4"), 28)
        self.assertEqual(parse_square("E4"), 28)
        self.assertEqual(parse_square("a1"), 0)
        self.assertIsNone(parse_square("z9"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
