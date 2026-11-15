# -*- coding: utf-8 -*-
"""
abaAcademy.tajweed
==================

معلّم التجويد — the tajweed rules of every ayah, read aloud word by word.

The annotations come from the quran-tajweed project by Collin Fair
(https://github.com/cpfair/quran-tajweed, CC BY 4.0), which marks each
tajweed rule (riwayat Hafs) with exact character positions in the Tanzil
Uthmani text. The academy's own Qur'an text is the same Tanzil text but in a
later edition with a few extra marks (small low meem, small iqlab meem, pause
and hizb signs), so devtools mapped the positions onto it ayah by ayah and
kept an ayah only where every checkable annotation fell on the letter its
rule requires. About 95 per cent of ayat pass; for the rest the screen says
plainly that no verified annotation is available. Nothing is guessed.

The Arabic explanation of each rule is the standard definition taught in
tajweed primers for the riwayah of Hafs from 'Asim by way of al-Shatibiyyah.
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
QURAN = os.path.join(HERE, "resources", "quran")

# name, short explanation, how long / what to do
RULES: Dict[str, Tuple[str, str]] = {
    "ghunnah": ("الغنّة",
                "صوت أغنّ يخرج من الخيشوم، ويظهر كاملًا في النون والميم المشدّدتين، ومقداره حركتان."),
    "idghaam_ghunnah": ("الإدغام بغنّة",
                        "إذا جاء بعد النون الساكنة أو التنوين حرف من حروف ينمو (الياء والنون والميم والواو) "
                        "في كلمتين، أُدخلت النون في الحرف التالي فصارا حرفًا واحدًا مشدّدًا مع غنّة بمقدار حركتين."),
    "idghaam_no_ghunnah": ("الإدغام بلا غنّة",
                           "إذا جاء بعد النون الساكنة أو التنوين اللام أو الراء، أُدغمت النون فيهما إدغامًا كاملًا "
                           "دون غنّة."),
    "iqlab": ("الإقلاب",
              "إذا جاء بعد النون الساكنة أو التنوين حرف الباء، قُلبت النون ميمًا مخفاة مع غنّة بمقدار حركتين، "
              "وتُرسم فوقها ميم صغيرة في المصحف."),
    "ikhfa": ("الإخفاء الحقيقي",
              "إذا جاء بعد النون الساكنة أو التنوين أحد خمسة عشر حرفًا (ص ذ ث ك ج ش ق س د ط ز ف ت ض ظ)، "
              "نُطقت النون بين الإظهار والإدغام عارية من التشديد مع غنّة بمقدار حركتين."),
    "ikhfa_shafawi": ("الإخفاء الشفوي",
                      "إذا جاء بعد الميم الساكنة حرف الباء، أُخفيت الميم عند الباء مع غنّة بمقدار حركتين."),
    "idghaam_shafawi": ("الإدغام الشفوي (إدغام المثلين الصغير)",
                        "إذا جاء بعد الميم الساكنة ميم متحرّكة، أُدغمت الأولى في الثانية فصارتا ميمًا مشدّدة "
                        "مع غنّة بمقدار حركتين."),
    "idghaam_mutajanisayn": ("إدغام المتجانسين",
                             "حرفان اتّفقا في المخرج واختلفا في الصفة والأوّل ساكن، فيُدغم الأوّل في الثاني، "
                             "مثل التاء في الطاء، والدال في التاء، والذال في الظاء، والباء في الميم."),
    "idghaam_mutaqaribayn": ("إدغام المتقاربين",
                             "حرفان تقاربا في المخرج والأوّل ساكن، فيُدغم الأوّل في الثاني، مثل اللام في الراء، "
                             "والقاف في الكاف."),
    "madd_2": ("المدّ الطبيعي",
               "حرف مدّ (ألف قبلها فتح، أو واو ساكنة قبلها ضمّ، أو ياء ساكنة قبلها كسر) لا يليه همز ولا سكون، "
               "يُمدّ حركتين."),
    "madd_246": ("المدّ العارض للسكون أو مدّ اللين",
                 "حرف مدّ أو لين بعده حرف سُكّن لأجل الوقف، يجوز مدّه حركتين أو أربعًا أو ستًّا عند الوقف."),
    "madd_muttasil": ("المدّ المتّصل",
                      "حرف مدّ بعده همزة في الكلمة نفسها، يجب مدّه أربع حركات أو خمسًا."),
    "madd_munfasil": ("المدّ المنفصل",
                      "حرف مدّ في آخر كلمة وبعده همزة في أوّل الكلمة التالية، يُمدّ أربع حركات أو خمسًا "
                      "في رواية حفص من طريق الشاطبية."),
    "madd_6": ("المدّ اللازم",
               "حرف مدّ بعده سكون أصليّ ثابت وصلًا ووقفًا، يُمدّ ستّ حركات لزومًا، ومنه مدّ حروف فواتح السور "
               "مثل الم."),
    "qalqalah": ("القلقلة",
                 "اضطراب الصوت عند النطق بأحد حروف قطب جد (القاف والطاء والباء والجيم والدال) ساكنًا، "
                 "حتى تُسمع له نبرة قويّة، وتكون أقوى عند الوقف."),
    "hamzat_wasl": ("همزة الوصل",
                    "همزة يُنطق بها عند الابتداء بالكلمة وتسقط في وصل الكلام بما قبلها، وتُرسم في المصحف "
                    "ألفًا عليها رأس صاد صغيرة."),
    "lam_shamsiyyah": ("اللام الشمسيّة",
                       "لام التعريف قبل أحد الحروف الشمسيّة تُكتب ولا تُنطق، ويُشدّد الحرف الذي بعدها."),
    "silent": ("حرف لا يُنطق",
               "حرف يُكتب في المصحف ولا يُنطق في الوصل، مثل الألف بعد واو الجماعة، وتعلوه دائرة صغيرة."),
}

GROUPS = [
    ("أحكام النون الساكنة والتنوين", ["idghaam_ghunnah", "idghaam_no_ghunnah", "iqlab", "ikhfa"]),
    ("أحكام الميم الساكنة", ["ikhfa_shafawi", "idghaam_shafawi"]),
    ("الغنّة", ["ghunnah"]),
    ("المدود", ["madd_2", "madd_246", "madd_muttasil", "madd_munfasil", "madd_6"]),
    ("الإدغام بين الحروف", ["idghaam_mutajanisayn", "idghaam_mutaqaribayn"]),
    ("القلقلة", ["qalqalah"]),
    ("ما يُكتب ولا يُنطق", ["hamzat_wasl", "lam_shamsiyyah", "silent"]),
]

SOURCE = ("علامات التجويد من مشروع quran-tajweed لكولن فير برخصة المشاع الإبداعي (CC BY 4.0)، "
          "على نصّ المصحف العثماني من مشروع تنزيل.")

_HARAKAT = re.compile("[\u064b-\u065f\u0670\u06d6-\u06ed]")
_DAGGER = re.compile("(?<!\u0649)\u0670")


def rule_name(rule: str) -> str:
    return RULES.get(rule, (rule, ""))[0]


def rule_text(rule: str) -> str:
    name, text = RULES.get(rule, (rule, ""))
    return f"{name}: {text}"


def bare(text: str) -> str:
    """Letters only, for spoken output and answer matching."""
    text = _DAGGER.sub("ا", text)
    return " ".join(_HARAKAT.sub("", text).replace("ٱ", "ا").split())


@dataclass
class Mark:
    rule: str
    start: int
    end: int
    word: str
    letters: str
    word_index: int

    @property
    def name(self) -> str:
        return rule_name(self.rule)


class Tajweed:
    def __init__(self, quran_path: Optional[str] = None, tajweed_path: Optional[str] = None):
        qp = quran_path or os.path.join(QURAN, "quran_data.json")
        tp = tajweed_path or os.path.join(QURAN, "tajweed.json")
        with open(qp, encoding="utf-8") as f:
            q = json.load(f)
        self.surahs = q["surahs"]
        self.text: Dict[Tuple[int, int], str] = {(a[0], a[1]): a[6] for a in q["ayat"]}
        self.marks: Dict[Tuple[int, int], List[List]] = {}
        if os.path.exists(tp):
            with open(tp, encoding="utf-8") as f:
                for row in json.load(f):
                    self.marks[(row["s"], row["a"])] = row["r"]

    _instance = None

    @classmethod
    def get(cls) -> "Tajweed":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def surah_name(self, n: int) -> str:
        name = bare(self.surahs[n - 1]["name"])
        return name[5:] if name.startswith("سورة ") else name

    def ayah_count(self, n: int) -> int:
        return int(self.surahs[n - 1]["count"])

    def verified(self, s: int, a: int) -> bool:
        return (s, a) in self.marks

    def ayah_marks(self, s: int, a: int) -> List[Mark]:
        text = self.text.get((s, a), "")
        out = []
        for rule, start, end in self.marks.get((s, a), []):
            ws = text.rfind(" ", 0, start) + 1
            we = text.find(" ", max(end - 1, start))
            we = len(text) if we < 0 else we
            word = text[ws:we]
            if end > we:            # a rule that spans two words (idghaam, munfasil)
                nxt = text.find(" ", end)
                word = text[ws:len(text) if nxt < 0 else nxt]
            out.append(Mark(rule, start, end, word, text[start:end], text.count(" ", 0, start)))
        return out

    def describe_ayah(self, s: int, a: int) -> str:
        text = self.text.get((s, a))
        if text is None:
            return "لا توجد هذه الآية."
        if not self.verified(s, a):
            return (f"{bare(text)}\nلا تتوفّر لهذه الآية علامات تجويد محقّقة في هذه النسخة، "
                    "فلم نعرض شيئًا حتى لا نخطئ.")
        marks = self.ayah_marks(s, a)
        lines = [bare(text)]
        if not marks:
            lines.append("لا تحوي هذه الآية حكمًا معلَّمًا.")
        for k, m in enumerate(marks, 1):
            lines.append(f"{k}. {m.name} في كلمة {bare(m.word)}")
        return "\n".join(lines)

    def counts(self, s: int, a: Optional[int] = None) -> Dict[str, int]:
        res: Dict[str, int] = {}
        keys = [(s, a)] if a else [(s, k) for k in range(1, self.ayah_count(s) + 1)]
        for key in keys:
            for rule, _, _ in self.marks.get(key, []):
                res[rule] = res.get(rule, 0) + 1
        return res

    def examples(self, rule: str, n: int = 5, surah: Optional[int] = None,
                 rng: Optional[random.Random] = None) -> List[Tuple[int, int, Mark]]:
        rng = rng or random.Random()
        keys = [k for k in self.marks if surah is None or k[0] == surah]
        rng.shuffle(keys)
        out = []
        for key in keys:
            for m in self.ayah_marks(*key):
                if m.rule == rule:
                    out.append((key[0], key[1], m))
                    break
            if len(out) >= n:
                break
        return out


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


def make_question(tj: Tajweed, surah: Optional[int] = None, rng: Optional[random.Random] = None,
                  rules: Optional[List[str]] = None) -> Optional[Question]:
    """Pick a verified mark and ask which rule it is. Wrong options come from
    the same group first (the confusions that matter), then from the rest."""
    rng = rng or random.Random()
    keys = [k for k in tj.marks if surah is None or k[0] == surah]
    for _ in range(50):
        if not keys:
            return None
        s, a = rng.choice(keys)
        marks = [m for m in tj.ayah_marks(s, a) if m.rule != "hamzat_wasl" and (not rules or m.rule in rules)]
        if not marks:
            continue
        m = rng.choice(marks)
        group = next((g for _, g in GROUPS if m.rule in g), [])
        pool = [r for r in group if r != m.rule]
        rng.shuffle(pool)
        rest = [r for r in RULES if r != m.rule and r not in pool]
        rng.shuffle(rest)
        wrong = (pool + rest)[:3]
        options = [rule_name(r) for r in wrong + [m.rule]]
        rng.shuffle(options)
        prompt = (f"في سورة {tj.surah_name(s)}، الآية {a}: {bare(tj.text[(s, a)])}\n"
                  f"ما الحكم في كلمة {bare(m.word)} عند {' '.join(bare(m.letters)) or 'الحرف المعلَّم'}؟")
        return Question(prompt, options, rule_name(m.rule), rule_text(m.rule))
    return None
