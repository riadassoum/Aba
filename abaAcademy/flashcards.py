# -*- coding: utf-8 -*-
"""
abaAcademy.flashcards
=====================

A lightweight, Anki-style flashcard system for the academy — built for Arab
learners: the interface, prompts and feedback are all in Arabic and right-to-
left, and cards are ideal for Arabic vocabulary, Qur'an memorisation, foreign-
language words, or any fact the learner wants to drill.

Cards are the learner's own (they add/edit/delete them). Storage lives in the
persistent the application's data folder (via the same settings store as the rest of the
academy), so cards and their review schedule survive add-on reinstalls. Review
timing is driven by the academy's FSRS scheduler, so mastered cards fade out and
weak ones return soon — exactly like the lesson review, but for personal cards.

Each card: {id, front, back, deck, hint}. Scheduling state is kept by the SRS
store keyed on the card id (prefixed ``card:`` so it never collides with lesson
concept ids).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from .database import srs

_CARDS_KEY = "flashcards"
_CARD_PREFIX = "card:"


class FlashcardStore:
    def __init__(self, store):
        self.store = store

    # -- persistence -------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.store.get_setting(_CARDS_KEY, "[]") or "[]")
        except Exception:
            return []

    def _save(self, cards: List[Dict[str, Any]]) -> None:
        try:
            self.store.set_setting(_CARDS_KEY, json.dumps(cards, ensure_ascii=False))
        except Exception:
            pass

    # -- CRUD --------------------------------------------------------------

    def all_cards(self) -> List[Dict[str, Any]]:
        return self._load()

    def decks(self) -> List[str]:
        seen = []
        for c in self._load():
            d = c.get("deck") or "عام"
            if d not in seen:
                seen.append(d)
        return seen

    def add(self, front: str, back: str, deck: str = "عام", hint: str = "") -> Dict[str, Any]:
        cards = self._load()
        card = {"id": uuid.uuid4().hex[:12], "front": front.strip(),
                "back": back.strip(), "deck": (deck or "عام").strip(),
                "hint": (hint or "").strip(), "created": time.time()}
        cards.append(card)
        self._save(cards)
        return card

    def update(self, card_id: str, **fields) -> bool:
        cards = self._load()
        for c in cards:
            if c["id"] == card_id:
                for k in ("front", "back", "deck", "hint"):
                    if k in fields and fields[k] is not None:
                        c[k] = str(fields[k]).strip()
                self._save(cards)
                return True
        return False

    def delete(self, card_id: str) -> bool:
        cards = self._load()
        new = [c for c in cards if c["id"] != card_id]
        if len(new) != len(cards):
            self._save(new)
            # drop its schedule too
            try:
                self.store.srs_upsert(_CARD_PREFIX + card_id, "flashcard", "flashcards",
                                      2.5, 0.0, 0, time.time())
            except Exception:
                pass
            return True
        return False

    # -- review (FSRS) -----------------------------------------------------

    def _card_by_id(self, card_id: str, cards=None):
        cards = cards if cards is not None else self._load()
        return next((c for c in cards if c["id"] == card_id), None)

    def due_cards(self, deck: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Cards whose review is due now (plus brand-new, never-seen cards)."""
        cards = self._load()
        if deck:
            cards = [c for c in cards if (c.get("deck") or "عام") == deck]
        by_id = {c["id"]: c for c in cards}
        seen_ids = set()
        due: List[Dict[str, Any]] = []
        now = time.time()
        # scheduled-and-due
        for row in self.store.srs_due(now=now, limit=limit * 2):
            qid = row.get("qid", "")
            if qid.startswith(_CARD_PREFIX):
                cid = qid[len(_CARD_PREFIX):]
                if cid in by_id:
                    due.append(by_id[cid])
                    seen_ids.add(cid)
        # brand-new cards (never reviewed) come next
        for c in cards:
            if c["id"] not in seen_ids and self.store.srs_get(_CARD_PREFIX + c["id"]) is None:
                due.append(c)
            if len(due) >= limit:
                break
        return due[:limit]

    def grade(self, card_id: str, correct: bool, elapsed: float = 6.0) -> None:
        srs.schedule_review(self.store, _CARD_PREFIX + card_id, "flashcard",
                            "flashcards", correct, elapsed)

    # -- starter decks (bundled, built from the courses) -------------------

    def _starter_dir(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "resources", "flashcards")

    def starter_index(self) -> List[Dict[str, Any]]:
        try:
            with open(os.path.join(self._starter_dir(), "index.json"), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def loaded_starter_ids(self) -> List[str]:
        try:
            return json.loads(self.store.get_setting("flashcards_loaded_decks", "[]") or "[]")
        except Exception:
            return []

    def load_starter_deck(self, deck_id: str, deck_name: str) -> int:
        """Add all cards of a bundled deck into the learner's collection (once)."""
        loaded = self.loaded_starter_ids()
        if deck_id in loaded:
            return 0
        path = os.path.join(self._starter_dir(), f"{deck_id}.json")
        try:
            with open(path, encoding="utf-8") as f:
                cards = json.load(f)
        except Exception:
            return 0
        existing = self._load()
        have = {(c["front"], c["back"]) for c in existing}
        added = 0
        for c in cards:
            key = (c.get("front", "").strip(), c.get("back", "").strip())
            if key[0] and key[1] and key not in have:
                existing.append({"id": uuid.uuid4().hex[:12], "front": key[0], "back": key[1],
                                 "deck": deck_name, "hint": c.get("hint", ""), "created": time.time()})
                have.add(key)
                added += 1
        self._save(existing)
        loaded.append(deck_id)
        try:
            self.store.set_setting("flashcards_loaded_decks", json.dumps(loaded, ensure_ascii=False))
        except Exception:
            pass
        return added

    def stats(self) -> Dict[str, int]:
        cards = self._load()
        due = len(self.due_cards(limit=10 ** 6))
        return {"total": len(cards), "due": due, "decks": len(self.decks())}
