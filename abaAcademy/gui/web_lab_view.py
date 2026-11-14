# -*- coding: utf-8 -*-
"""
abaAcademy.gui.web_lab_view
===========================

The accessible web lab (مختبر صفحات الويب): write HTML, have it checked for
the problems screen-reader users actually meet, and walk the page as a
screen reader presents it — in reading order, or by headings, landmarks,
links and form fields — without leaving the academy. Short lessons explain
each rule. Pages can be saved to and opened from disk.
"""

from __future__ import annotations

import io
import os

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog
from ..codelab import web_sandbox as ws
from ..tools.ar_count import count


class WebLabDialog(ToolDialog):
    TITLE = "مختبر صفحات الويب الميسّرة"
    SIZE = (820, 720)
    _VIEWS = [("reading", "ترتيب القراءة (كما في وضع التصفّح)"), ("headings", "العناوين"),
              ("landmarks", "المعالم"), ("links", "الروابط"), ("forms", "حقول النماذج")]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        saved = self.setting("web_lab_page", "")
        self.editor = self.add_entry("محرّر HTML", saved or ws.STARTER_PAGE, multiline=True, height=200)
        self.add_buttons([("افحص إمكانية الوصول", self._audit), ("صفحة البداية", self._starter),
                          ("افتح ملفًّا", self._open), ("احفظ ملفًّا", self._save_file)], close=False)
        self.viewChoice = self.add_choice("طريقة العرض", [l for _, l in self._VIEWS],
                                          on_change=self._preview)
        self.view = self.add_list("الصفحة كما يقرؤها قارئ الشاشة", height=150)
        self.add_buttons([("حدّث المعاينة", self._preview), ("الدروس", self._lessons)])
        self.add_output("نتيجة الفحص", height=140)
        self.finish(self.editor)

    def _html(self) -> str:
        return self.editor.GetValue()

    def _remember(self) -> None:
        self.set_setting("web_lab_page", self._html())

    def _audit(self) -> None:
        self._remember()
        issues = ws.audit(self._html())
        if not issues:
            self.show_output("لم أجد مشكلات. أحسنت!", speak="لا مشكلات في إمكانية الوصول.")
            return
        errors = sum(1 for i in issues if i.severity == "error")
        warns = len(issues) - errors
        text = "\n".join(i.spoken() for i in issues)
        summary = "، ".join(x for x in (count(errors, "error") if errors else "", count(warns, "warning") if warns else "") if x)
        self.show_output(f"{summary}:\n{text}",
                         speak=f"{summary}. أوّلها: {issues[0].spoken()}")

    def _preview(self) -> None:
        self._remember()
        kind = self._VIEWS[self.choice_index(self.viewChoice)][0]
        html = self._html()
        if kind == "reading":
            lines = ws.reading_order(html)
        elif kind == "headings":
            lines = ws.headings(html)
        elif kind == "landmarks":
            lines = ws.landmarks(html)
        elif kind == "links":
            lines = ws.links(html)
        else:
            lines = ws.form_fields(html)
        if not lines:
            lines = ["(لا شيء)"]
        self.view.Set(lines)
        self.select_index(self.view, 0)
        self.view.SetFocus()
        self.announce(f"{count(len(lines), 'item')}. {lines[0]}")

    def _starter(self) -> None:
        self.editor.SetValue(ws.STARTER_PAGE)
        self.editor.SetFocus()
        self._say("وُضعت صفحة البداية في المحرّر.")

    def _lessons(self) -> None:
        text = "\n\n".join(f"{t}\n{body}" for t, body in ws.LESSONS)
        self.show_output(text, speak="الدروس في مربّع النتيجة؛ انتقل إليه لقراءتها.", focus=True)

    def _open(self) -> None:
        with wx.FileDialog(self, "افتح صفحة HTML", wildcard="HTML (*.html;*.htm)|*.html;*.htm|كلّ الملفات|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        with open(path, "rb") as f:
            data = f.read()
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1256", errors="replace")
        self.editor.SetValue(text)
        self.editor.SetFocus()
        self._say(f"فُتح {os.path.basename(path)}.")

    def _save_file(self) -> None:
        with wx.FileDialog(self, "احفظ الصفحة", wildcard="HTML (*.html)|*.html",
                           defaultFile="page.html",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(self._html())
        self._say(f"حُفظت في {os.path.basename(path)}.")

    def instructions(self) -> str:
        return ("اكتب صفحة HTML في المحرّر، ثم افحص لتسمع مشكلات إمكانية الوصول وأرقام أسطرها، "
                "واختر طريقة العرض لتمشي في صفحتك كما يقدّمها قارئ الشاشة. الدروس تشرح كل قاعدة.")
