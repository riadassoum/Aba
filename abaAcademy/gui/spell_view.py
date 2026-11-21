# -*- coding: utf-8 -*-
"""
abaAcademy.gui.spell_view
=========================

The spell-check screen. It walks through a text control word by word: each
unknown word is read with its sentence and spelled letter by letter, the
suggestions are in a list, and the learner replaces, ignores, or adds the
word to a personal list. Opened with F7 from the homework editor, or on its
own from the hub to check pasted text.
"""

from __future__ import annotations

import wx

from .. import spell
from .tool_base import ToolDialog


def _spell_out(word: str) -> str:
    return "، ".join(word)


class SpellCheckDialog(ToolDialog):
    TITLE = "المدقّق الإملائي"
    SIZE = (760, 560)

    def __init__(self, parent, academy, speech, target: "wx.TextCtrl" = None):
        super().__init__(parent, academy, speech)
        self.target = target
        self.add_text("يدقّق الكلمات العربية بقاموس أيّاسبل، والإنجليزية أو الفرنسية بقواميس ليبر أوفيس، دون اتصال. "
                      "لكل كلمة غير معروفة تسمع جملتها واقتراحات التصحيح.")
        if target is None:
            self.text = self.add_entry("النصّ المراد تدقيقه", multiline=True, height=150)
        else:
            self.text = target
        latin = self.setting("latin", "en")
        self.latinChoice = self.add_choice("لغة الكلمات اللاتينية", ["الإنجليزية", "الفرنسية"],
                                           1 if latin == "fr" else 0, on_change=self._latin_changed)
        self.wordOut = self.add_output("الكلمة غير المعروفة وجملتها", height=70)
        self.sugList = self.add_list("الاقتراحات (Enter للاستبدال)", [], height=130,
                                     on_activate=self._replace)
        self.add_buttons([("استبدل", self._replace), ("تجاهل", self._skip), ("تجاهل في كل النصّ", self._ignore_all),
                          ("أضف إلى قاموسي", self._add_word), ("تهجئة الكلمة", self._spell_word)], close=False)
        self.add_buttons([("ابدأ التدقيق من البداية", self._restart)])
        self.checker = spell.Checker("fr" if latin == "fr" else "en", spell.load_personal(self.academy.store))
        self.current = None
        self.pos = 0
        self.fixed = 0
        self.finish(self.sugList if target is not None else self.text)
        if target is not None:
            wx.CallAfter(self._next)

    def instructions(self) -> str:
        return ("لكل كلمة غير معروفة: اختر اقتراحًا بالأسهم واضغط Enter للاستبدال، أو تجاهل، أو أضفها إلى قاموسك "
                "إن كانت صحيحة (اسم علم مثلًا). القاموس العربي يُحمّل في ثوانٍ عند أوّل استعمال.")

    def _latin_changed(self, evt=None):
        lang = "fr" if self.latinChoice.GetSelection() == 1 else "en"
        self.set_setting("latin", lang)
        self.checker.latin = lang

    def _restart(self):
        self.pos = 0
        self.fixed = 0
        self._next()

    def _next(self):
        text = self.text.GetValue()
        if not text.strip():
            self._say("لا يوجد نصّ للتدقيق.")
            return
        lang = self.checker.lang_for(text[self.pos:] or "a")
        if spell.dictionary(lang) is None and spell.dictionary("ar") is None:
            self._say("القواميس غير موجودة في هذه النسخة.")
            return
        err = self.checker.next_error(text, self.pos)
        if err is None:
            self.current = None
            self.wordOut.SetValue("")
            self.sugList.Set([])
            done = f"انتهى التدقيق. صُحّحت {self.fixed} كلمة." if self.fixed else "انتهى التدقيق، لا أخطاء أخرى."
            self._say(done)
            return
        s, e, w = err
        self.current = err
        a = max(text.rfind(".", 0, s), text.rfind("\n", 0, s), text.rfind("؟", 0, s)) + 1
        b = min([k for k in (text.find(".", e), text.find("\n", e), text.find("؟", e)) if k >= 0] or [len(text)])
        sentence = text[a:b].strip()
        sugg = self.checker.suggest(w)
        self.wordOut.SetValue(f"{w}\n{sentence}")
        self.sugList.Set(sugg)
        if sugg:
            self.select_index(self.sugList, 0)
        if self.target is not None:
            self.target.SetSelection(s, e)
        self.sugList.SetFocus()
        tail = ("الاقتراحات: " + "، ".join(sugg[:5])) if sugg else "لا اقتراحات."
        self._say(f"كلمة غير معروفة: {w}. في الجملة: {sentence}. {tail}")

    def _replace(self):
        if not self.current:
            return
        i = self.sugList.GetSelection()
        if i < 0:
            self._say("اختر اقتراحًا أوّلًا.")
            return
        new = self.sugList.GetString(i)
        s, e, w = self.current
        text = self.text.GetValue()
        self.text.SetValue(text[:s] + new + text[e:])
        self.pos = s + len(new)
        self.fixed += 1
        self._say(f"استُبدلت بـ {new}.")
        self._next()

    def _skip(self):
        if self.current:
            self.pos = self.current[1]
            self._next()

    def _ignore_all(self):
        if self.current:
            self.checker.ignored.add(self.current[2])
            self._skip()

    def _add_word(self):
        if self.current:
            w = self.current[2]
            spell.add_personal(self.academy.store, w)
            self.checker.personal.add(w)
            self._say(f"أُضيفت {w} إلى قاموسك.")
            self._skip()

    def _spell_word(self):
        if self.current:
            self._say(_spell_out(self.current[2]))

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.sugList:
            self._replace()
            return True
        return False
