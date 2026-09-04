# -*- coding: utf-8 -*-
"""
abaAcademy.gui.pack_manager
===========================

The screen where a student imports a ``.abapack`` course pack a teacher shared,
and where a teacher can export one of the installed courses as a shareable pack.

Import flow: pick a file, hear a spoken summary of what it contains, then confirm
installation (with an explicit choice about overwriting existing content).
Export flow: pick an installed course, choose where to save, get a ``.abapack``.

All file dialogs are standard wx dialogs (keyboard accessible). Nothing is
installed without confirmation, and existing content is never overwritten
silently.
"""

from __future__ import annotations

import os

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..packformat.abapack import PackReader, PackBuilder, PackError


class PackManagerDialog(AccessibleDialog):
    TITLE = "حزم الدورات (استيراد وتصدير)"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(700, 500))
        self.academy = academy
        self._pending = None       # (PackReader, path) awaiting confirm

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "استورد حزمة دورة شاركها معك معلّم (ملف بامتداد abapack)، "
            "أو صدّر إحدى دوراتك لمشاركتها.")), 0, wx.ALL, 8)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(660)
        s.Add(self.status, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "استيراد حزمة…", lambda e: self._choose_import()), 0, wx.ALL, 3)
        self.confirmBtn = self.button(panel, "تأكيد التثبيت", lambda e: self._do_install(False))
        self.confirmBtn.Disable()
        row.Add(self.confirmBtn, 0, wx.ALL, 3)
        self.overwriteBtn = self.button(panel, "تثبيت مع الاستبدال", lambda e: self._do_install(True))
        self.overwriteBtn.Disable()
        row.Add(self.overwriteBtn, 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALL, 4)

        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(self.button(panel, "تصدير دورة…", lambda e: self._choose_export()), 0, wx.ALL, 3)
        row2.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row2, 0, wx.ALL, 4)

        panel.SetSizer(s)
        self.set_first_control(panel.GetChildren()[-1])
        wx.CallAfter(self._say, "اختر «استيراد حزمة» لفتح ملف، أو «تصدير دورة» لمشاركة دورة.")

    # -- import -----------------------------------------------------------
    def _choose_import(self):
        with wx.FileDialog(self, "اختر حزمة abapack",
                           wildcard="حزم الأكاديمية (*.abapack)|*.abapack",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        try:
            reader = PackReader(path)
        except PackError as exc:
            self._say(str(exc))
            return
        self._pending = (reader, path)
        self.confirmBtn.Enable()
        self.overwriteBtn.Enable()
        self._say(reader.summary() + " اضغط «تأكيد التثبيت» للمتابعة، "
                  "أو «تثبيت مع الاستبدال» إذا كانت موجودة وتريد تحديثها.")
        self.confirmBtn.SetFocus()

    def _do_install(self, overwrite):
        if not self._pending:
            self._say("اختر حزمة أولاً.")
            return
        reader, path = self._pending
        try:
            report = reader.install(self.academy.user_data_dir, overwrite=overwrite)
        except PackError as exc:
            self._say(str(exc))
            return
        finally:
            pass
        self._say(report + " أعد فتح قائمة الدورات لرؤية المحتوى الجديد.")
        self.confirmBtn.Disable()
        self.overwriteBtn.Disable()
        self._pending = None

    # -- export -----------------------------------------------------------
    def _choose_export(self):
        courses = self._installed_courses()
        if not courses:
            self._say("لا توجد دورات قابلة للتصدير.")
            return
        names = [c["title"] for c in courses]
        with wx.SingleChoiceDialog(self, "اختر دورة للتصدير", "تصدير", names) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            course = courses[dlg.GetSelection()]
        with wx.FileDialog(self, "احفظ الحزمة",
                           defaultFile=f"{course['course_id']}.abapack",
                           wildcard="حزم الأكاديمية (*.abapack)|*.abapack",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            out = dlg.GetPath()
        try:
            self._export_course(course, out)
        except Exception as exc:
            self._say(f"تعذّر التصدير: {exc}")
            return
        self._say(f"تم تصدير «{course['title']}» إلى الملف. يمكنك الآن مشاركته.")

    def _installed_courses(self):
        """Courses that live in the user data dir (teacher-authored / imported),
        which are the ones it makes sense to re-export."""
        out = []
        root = os.path.join(self.academy.user_data_dir, "courses")
        if not os.path.isdir(root):
            return out
        import json
        for name in os.listdir(root):
            cj = os.path.join(root, name, "course.json")
            if os.path.isfile(cj):
                try:
                    d = json.load(open(cj, encoding="utf-8"))
                    d.setdefault("course_id", name)
                    out.append(d)
                except Exception:
                    continue
        return out

    def _export_course(self, course, out_path):
        import json
        root = os.path.join(self.academy.user_data_dir, "courses", course["course_id"])
        builder = PackBuilder(course["course_id"], course.get("title", course["course_id"]),
                              author=course.get("author", ""))
        lessons = {}
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                if fn == "course.json":
                    continue
                if fn.endswith(".json"):
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, root).replace("\\", "/")
                    try:
                        lessons[rel] = json.load(open(full, encoding="utf-8"))
                    except Exception:
                        continue
        builder.add_course(course, lessons=lessons)
        builder.write(out_path)

    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def instructions(self):
        return ("حزم الدورات: لاستيراد دورة شاركها معلّم، اختر «استيراد حزمة» وحدّد ملف "
                "abapack، فتُسمع وصفاً لمحتواه ثم تضغط «تأكيد التثبيت». لن يُستبدل أي محتوى "
                "موجود إلا إذا اخترت «تثبيت مع الاستبدال». لتصدير دورة ومشاركتها، اختر "
                "«تصدير دورة» ثم اختر الدورة ومكان الحفظ. Escape للإغلاق.")
