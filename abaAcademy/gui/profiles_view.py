# -*- coding: utf-8 -*-
"""
abaAcademy.gui.profiles_view
============================

Learner profiles: several learners on one copy of the academy, each with
their own progress, settings and cards. Switching restarts the academy's
main window on the chosen learner's data, without leaving the program.

The profile registry belongs to the desktop application (``abaDesktop.
profiles``); the hub only shows this screen when the application told the
academy where that registry lives (``academy.profiles_root``).
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog
from .accessible import close_all_screens


def _profiles():
    from abaDesktop import profiles
    return profiles


class ProfilesDialog(ToolDialog):
    TITLE = "ملفّات المتعلّمين"
    SIZE = (700, 560)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.root = getattr(academy, "profiles_root", "")
        self.list = self.add_list("المتعلّمون (Enter للتبديل)", height=170,
                                  on_activate=self._switch)
        self.nameEntry = self.add_entry("اسم متعلّم جديد أو الاسم الجديد عند إعادة التسمية",
                                        on_enter=self._create)
        self.add_buttons([("أضف متعلّمًا", self._create), ("بدّل إلى المحدّد", self._switch),
                          ("أعد التسمية", self._rename), ("احذف", self._delete)], close=False)
        reg = _profiles().load(self.root)
        self.askCheck = self.add_check("اسألني عن المتعلّم عند كلّ تشغيل", reg.ask_on_start,
                                       on_change=self._ask_changed)
        self.add_buttons([])
        self.add_output("ملاحظة", height=70)
        self.finish(self.list)
        self._refresh()

    def _refresh(self, select_id: str = "") -> None:
        P = _profiles()
        reg = P.load(self.root)
        self._ids = [p.id for p in reg.profiles]
        self.list.Set([P.describe(self.root, p, reg.active) for p in reg.profiles])
        idx = self._ids.index(select_id) if select_id in self._ids else self._ids.index(reg.active)
        self.select_index(self.list, idx)

    def _selected(self) -> str:
        i = self.list.GetSelection()
        if i < 0:
            raise ValueError("اختر متعلّمًا من القائمة.")
        return self._ids[i]

    def _create(self) -> None:
        p = _profiles().create(self.root, self.nameEntry.GetValue())
        self.nameEntry.SetValue("")
        self._refresh(p.id)
        self.list.SetFocus()
        self._say(f"أُضيف {p.name}. اضغط Enter عليه للتبديل إليه.")

    def _rename(self) -> None:
        pid = self._selected()
        _profiles().rename(self.root, pid, self.nameEntry.GetValue())
        self.nameEntry.SetValue("")
        self._refresh(pid)
        self._say("أُعيدت التسمية.")

    def _delete(self) -> None:
        P = _profiles()
        pid = self._selected()
        reg = P.load(self.root)
        if pid == reg.active:
            raise ValueError("بدّل إلى متعلّم آخر قبل حذف هذا الملفّ.")
        prof = P.get(reg, pid)
        if wx.MessageBox(f"حذف ملفّ {prof.name}؟ تُنقل بياناته إلى مجلّد المحذوفات ولا تُمسح.",
                         "تأكيد الحذف", wx.YES_NO | wx.NO_DEFAULT, self) != wx.YES:
            return
        P.delete(self.root, pid)
        self._refresh()
        self._say("حُذف الملفّ.")

    def _switch(self) -> None:
        P = _profiles()
        pid = self._selected()
        reg = P.load(self.root)
        if pid == reg.active:
            self._say("هذا هو المتعلّم الحالي.")
            return
        P.set_active(self.root, pid)
        name = P.get(P.load(self.root), pid).name
        # the application reopens the hub on the new profile once every
        # screen has closed
        self.academy.switch_profile_requested = pid
        self.announce(f"جارٍ التبديل إلى {name}.")
        close_all_screens()

    def _ask_changed(self) -> None:
        _profiles().set_ask_on_start(self.root, self.askCheck.GetValue())

    def instructions(self) -> str:
        return ("لكلّ متعلّم ملفّ مستقلّ بتقدّمه وإعداداته وبطاقاته. أضف متعلّمًا باسمه، "
                "واضغط Enter على اسم في القائمة للتبديل إليه.")
