# -*- coding: utf-8 -*-
"""
abaAcademy.gui.deck_import_view
===============================

Import flashcards from Anki or any CSV/TSV/text list, export a deck for
Anki or a spreadsheet, and add ready-made decks built from the academy's own
data (element symbols, Morse code, the metres of Arabic poetry).
"""

from __future__ import annotations

import io
import os

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog
from .. import deck_import
from ..tools.ar_count import count


class DeckImportDialog(ToolDialog):
    TITLE = "استيراد البطاقات وتصديرها"
    SIZE = (760, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._parsed = None
        self._path = ""
        self.add_text("يقبل ملفّات أنكي النصّية وملفّات CSV وTSV والقوائم بصيغة كلمة - معنى. "
                      "يُكتشف الترميز والفاصل تلقائيًّا.")
        self.add_buttons([("اختر ملفًّا", self._choose)], close=False)
        self.deckEntry = self.add_entry("اسم المجموعة (فارغ = من الملفّ أو مستورد)")
        self.swapCheck = self.add_check("اقلب الوجهين (الظهر يصبح سؤالًا)")
        self.preview = self.add_list("معاينة أول البطاقات", height=130)
        self.add_buttons([("استورد", self._import)], close=False)

        decks = self._decks()
        self.exportChoice = self.add_choice("مجموعة للتصدير", ["كلّ المجموعات"] + decks)
        self.add_buttons([("صدّر ملفّ TSV", self._export)], close=False)

        self._gen_keys = list(deck_import.GENERATED_DECKS)
        self.genChoice = self.add_choice("مجموعة جاهزة", [deck_import.GENERATED_DECKS[k] for k in self._gen_keys])
        self.add_buttons([("أضف المجموعة الجاهزة", self._generated)])
        self.add_output("النتيجة", height=90)
        self.finish(self.deckEntry)

    def _cards(self):
        return self.academy.flashcards

    def _decks(self):
        try:
            return self._cards().decks()
        except Exception:
            return []

    def _refresh_decks(self) -> None:
        self.exportChoice.Set(["كلّ المجموعات"] + self._decks())
        self.exportChoice.SetSelection(0)

    def _choose(self) -> None:
        with wx.FileDialog(self, "اختر ملفّ البطاقات",
                           wildcard="ملفّات البطاقات (*.txt;*.csv;*.tsv)|*.txt;*.csv;*.tsv|كلّ الملفات|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        self._parsed = deck_import.parse_file(path)
        self._path = path
        if not self.deckEntry.GetValue().strip() and not any(self._parsed.deck_names):
            self.deckEntry.SetValue(os.path.splitext(os.path.basename(path))[0])
        lines = [f"{f} ← {b}" for f, b, _ in self._parsed.cards[:50]]
        self.preview.Set(lines or ["(لا بطاقات صالحة)"])
        self.select_index(self.preview, 0)
        self.show_output(self._parsed.summary())

    def _import(self) -> None:
        if not self._parsed:
            raise ValueError("اختر ملفًّا أولًا.")
        added, dup = deck_import.import_into(self._cards(), self._parsed,
                                             self.deckEntry.GetValue().strip(),
                                             self.swapCheck.GetValue())
        msg = f"أُضيفت {count(added, 'card')}" if added else "لم تُضف بطاقات جديدة"
        if dup:
            msg += f"، وتُركت {count(dup, 'card')} موجودة من قبل"
        self.show_output(msg + ". تجدها في البطاقات التعليمية للمراجعة.")
        self._refresh_decks()

    def _export(self) -> None:
        i = self.choice_index(self.exportChoice)
        deck = None if i == 0 else self.exportChoice.GetString(i)
        cards = self._cards().all_cards()
        if not cards:
            raise ValueError("لا توجد بطاقات للتصدير.")
        name = (deck or "flashcards").replace("/", "-") + ".txt"
        with wx.FileDialog(self, "احفظ البطاقات", wildcard="نصّ مفصول بمسافات جدولة (*.txt)|*.txt",
                           defaultFile=name, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        text = deck_import.export_tsv(cards, deck)
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(text)
        n = text.count("\n") - 3
        self.show_output(f"صُدّرت {count(n, 'card')} إلى {os.path.basename(path)}؛ يفتحه أنكي وبرامج الجداول.")

    def _generated(self) -> None:
        kind = self._gen_keys[self.choice_index(self.genChoice)]
        added, dup = deck_import.add_generated(self._cards(), kind)
        self.show_output(f"أُضيفت {count(added, 'card')} إلى {deck_import.GENERATED_DECKS[kind]}"
                         + (f"، و{count(dup, 'card')} موجودة من قبل." if dup else "."))
        self._refresh_decks()

    def instructions(self) -> str:
        return ("اختر ملفّ بطاقات لتعاينه ثم استورد. ويمكنك تصدير مجموعة ملفًّا نصّيًّا، "
                "أو إضافة مجموعة جاهزة من بيانات الأكاديمية.")
