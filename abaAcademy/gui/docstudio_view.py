# -*- coding: utf-8 -*-
"""
abaAcademy.gui.docstudio_view
=============================

A streamlined accessible editor for homework and notes. The student writes in a
small Markdown subset (with quick shortcuts for headings and lists) and exports
to a properly styled RTL Word ``.docx`` or to an RTL HTML file — both produced
with no external libraries.

Shortcuts inside the editor:
* Ctrl+1 / Ctrl+2 / Ctrl+3 — make the current line a heading of that level
* Ctrl+L — turn the current line into a bullet item
* Ctrl+Q — turn the current line into a blockquote
"""

from __future__ import annotations

import os

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..docstudio.docx_exporter import export_markdown_to_docx
from ..docstudio.html_exporter import export_markdown_to_html


class DocStudioDialog(AccessibleDialog):
    TITLE = "محرّر الواجبات والملاحظات"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(760, 600))
        self.academy = academy

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "اكتب واجبك بتنسيق ماركداون البسيط. استخدم # للعنوان الرئيسي، و## للفرعي، "
            "و- للنقاط. اختصارات: Ctrl+1/2/3 للعناوين، Ctrl+L لنقطة، Ctrl+Q لاقتباس. "
            "ثم صدّر إلى وورد أو HTML بترتيب من اليمين لليسار.")),
            0, wx.ALL, 6)

        trow = wx.BoxSizer(wx.HORIZONTAL)
        trow.Add(wx.StaticText(panel, label="العنوان:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.titleEntry = wx.TextCtrl(panel)
        self.titleEntry.SetName("عنوان المستند")
        trow.Add(self.titleEntry, 1, wx.RIGHT, 8)
        trow.Add(wx.StaticText(panel, label="الاسم:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.authorEntry = wx.TextCtrl(panel)
        self.authorEntry.SetName("اسم الطالب")
        trow.Add(self.authorEntry, 1)
        s.Add(trow, 0, wx.EXPAND | wx.ALL, 6)

        self.editor = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_RICH2,
                                  size=(-1, 340))
        self.editor.SetName("محرّر النص")
        self.editor.Bind(wx.EVT_KEY_DOWN, self._on_key)
        s.Add(self.editor, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(720)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "صدّر إلى وورد", lambda e: self._export("docx")), 0, wx.ALL, 3)
        row.Add(self.button(panel, "صدّر إلى HTML", lambda e: self._export("html")), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.titleEntry)

    def _on_key(self, evt):
        if evt.ControlDown():
            code = evt.GetKeyCode()
            prefix = {ord("1"): "# ", ord("2"): "## ", ord("3"): "### ",
                      ord("L"): "- ", ord("Q"): "> "}.get(code)
            if prefix:
                self._prefix_current_line(prefix)
                return
        evt.Skip()

    def _prefix_current_line(self, prefix):
        ins = self.editor.GetInsertionPoint()
        col, row = self.editor.PositionToXY(ins)[1:] if False else (None, None)
        # find line start
        text = self.editor.GetValue()
        line_start = text.rfind("\n", 0, ins) + 1
        # strip any existing marker
        rest = text[line_start:]
        stripped = rest
        for m in ("# ", "## ", "### ", "- ", "> "):
            if stripped.startswith(m):
                stripped = stripped[len(m):]
                break
        new_text = text[:line_start] + prefix + stripped
        self.editor.SetValue(new_text)
        self.editor.SetInsertionPoint(line_start + len(prefix))
        self._say("طُبّق التنسيق على السطر.")

    def _export(self, kind):
        md = self.editor.GetValue()
        if not md.strip():
            self._say("اكتب بعض النص أولاً.")
            return
        title = self.titleEntry.GetValue().strip() or None
        author = self.authorEntry.GetValue().strip() or None
        ext = "docx" if kind == "docx" else "html"
        wildcard = (f"مستند وورد (*.docx)|*.docx" if kind == "docx"
                    else "صفحة ويب (*.html)|*.html")
        with wx.FileDialog(self, "احفظ المستند", defaultFile=f"واجب.{ext}",
                           wildcard=wildcard,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        try:
            if kind == "docx":
                export_markdown_to_docx(md, path, title=title, author=author)
            else:
                export_markdown_to_html(md, path, title=title, author=author)
            self._say(f"تم التصدير بنجاح إلى {os.path.basename(path)}.")
        except Exception as exc:
            self._say(f"تعذّر التصدير: {exc}")

    def _say(self, text):
        self.status.SetLabel(text[:200])
        self.announce(text)

    def instructions(self):
        return ("محرّر الواجبات: اكتب نصك بماركداون البسيط (# عنوان، ## فرعي، - نقطة، "
                "> اقتباس، **عريض**، *مائل*). اختصارات: Ctrl+1/2/3 عناوين، Ctrl+L نقطة، "
                "Ctrl+Q اقتباس. اكتب العنوان واسمك، ثم «صدّر إلى وورد» أو «صدّر إلى HTML» "
                "لملف بترتيب صحيح من اليمين لليسار. Escape للإغلاق.")
