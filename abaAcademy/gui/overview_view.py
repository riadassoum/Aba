# -*- coding: utf-8 -*-
"""
abaAcademy.gui.overview_view
============================

نظرة عامة على المتعلّم — the overview page for parents, teachers and
caretakers (see ``study_hub.overview``). A list of sections on the right; the
selected section's lines in large text beside it. The whole page can be saved
as a large-print web page or opened in the browser to print.
"""

from __future__ import annotations

import io
import os
import tempfile

import wx

from .tool_base import ToolDialog


class OverviewDialog(ToolDialog):
    TITLE = "نظرة عامة على المتعلّم"
    SIZE = (820, 620)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._sections = []
        self.add_text("صفحة واحدة لوليّ الأمر والمعلّم ومن يرافق المتعلّم: نشاط اليوم، والتقدّم في كل دورة، "
                      "ونقاط الضعف، والخطوة التالية، وملخّص الأسبوع.")
        self.sectionList = self.add_list("الأقسام", [], height=150, on_select=self._show_section,
                                         on_activate=self._show_section)
        self.output = self.add_output("التفاصيل", height=300)
        f = self.output.GetFont()
        f.SetPointSize(f.GetPointSize() + 3)
        self.output.SetFont(f)
        self.add_buttons([("حدّث", self._build), ("اقرأ كل الصفحة", self._read_all),
                          ("احفظها صفحة للطباعة", self._save), ("افتحها في المتصفّح", self._open_browser)])
        self.finish(self.sectionList)
        self._build(quiet=True)

    def instructions(self) -> str:
        return ("نظرة عامة على المتعلّم. تنقّل بين الأقسام بالأسهم، وتظهر تفاصيل كل قسم بخطّ كبير. "
                "يمكنك حفظ الصفحة كاملة للطباعة أو فتحها في المتصفّح.")

    def _index(self):
        try:
            from ..quran_engine.khatma import QuranIndex
            from .planner_view import KhatmaDialog
            if KhatmaDialog._index is None:
                KhatmaDialog._index = QuranIndex.load(self.resource_path("quran", "quran_data.json"))
            return KhatmaDialog._index
        except Exception:
            return None

    def _build(self, quiet: bool = False) -> None:
        from ..study_hub import overview
        self._sections = overview.sections(self.academy, quran_index=self._index())
        self.sectionList.Set([f"{t} ({len(ls)})" for t, ls in self._sections])
        if self._sections:
            self.sectionList.SetSelection(0)
            self._show_section(quiet=quiet)

    def _show_section(self, evt=None, quiet: bool = False) -> None:
        i = self.sectionList.GetSelection()
        if not (0 <= i < len(self._sections)):
            return
        title, lines = self._sections[i]
        self.output.SetValue("\n".join(lines))
        if not quiet and evt is None:
            self.announce(f"{title}: " + " ".join(lines[:2]))

    def _read_all(self) -> None:
        from ..study_hub import overview
        self.announce(overview.text(self.academy, quran_index=self._index()).replace("\n", " "))

    def _html(self) -> str:
        from ..study_hub import overview
        name = self.academy.store.get_setting("user_name", "") or ""
        return overview.to_html(self.academy, name, quran_index=self._index())

    def _save(self) -> None:
        with wx.FileDialog(self, "احفظ الصفحة", wildcard="HTML (*.html)|*.html",
                           defaultFile="نظرة عامة على المتعلّم.html",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(self._html())
        self._say("حُفظت الصفحة. افتحها في أيّ متصفّح واطبعها بخطّ كبير.")

    def _open_browser(self) -> None:
        import webbrowser
        path = os.path.join(tempfile.gettempdir(), "aba_overview.html")
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(self._html())
        try:
            webbrowser.open("file://" + path)
            self._say("فُتحت الصفحة في المتصفّح.")
        except Exception:
            self._say("تعذّر فتح المتصفّح. احفظ الصفحة وافتحها يدويًّا.")
