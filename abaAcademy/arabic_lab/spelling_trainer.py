# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.spelling_trainer
======================================

Drills for the Arabic spelling pitfalls that trip up writers, especially
screen-reader users who can't rely on the visual shape: hamzat al-wasl vs
al-qat', the medial/terminal hamza seat, alif maqsura vs ya', and ta' marbuta vs
ha'. Each drill is a curated item with the correct spelling, the plausible wrong
spelling, and a short Arabic explanation of the *rule* that decides it.

Honest scope
------------
Arabic orthography has real exceptions and some genuinely debated cases. Rather
than a rule engine that would be confidently wrong on edge cases, this ships a
*curated, verified* set of clear items — each one a word whose correct spelling
is not in dispute, paired with the rule that governs it. It's a teaching drill,
not an automatic spell-checker. The set is plain data, easy to extend.
"""

from __future__ import annotations


class SpellingItem:
    def __init__(self, correct, wrong, rule, category):
        self.correct = correct
        self.wrong = wrong
        self.rule = rule
        self.category = category


# category keys
HAMZA_WASL_QAT = "hamza_wasl_qat"
HAMZA_SEAT = "hamza_seat"
ALIF_MAQSURA = "alif_maqsura"
TAA_MARBUTA = "taa_marbuta"

CATEGORY_NAMES = {
    HAMZA_WASL_QAT: "همزة الوصل والقطع",
    HAMZA_SEAT: "الهمزة المتوسطة والمتطرفة",
    ALIF_MAQSURA: "الألف المقصورة والياء",
    TAA_MARBUTA: "التاء المربوطة والهاء",
}


ITEMS = [
    # hamzat al-wasl vs al-qat'
    SpellingItem("استقبال", "إستقبال",
                 "مصدر الفعل الخماسي استقبل يبدأ بهمزة وصل، فلا تُكتب عليها همزة.",
                 HAMZA_WASL_QAT),
    SpellingItem("ابن", "إبن",
                 "ابن تبدأ بهمزة وصل، فلا همزة فوقها.",
                 HAMZA_WASL_QAT),
    SpellingItem("إكرام", "اكرام",
                 "إكرام مصدر الفعل الرباعي أكرم، وهمزته همزة قطع تُكتب.",
                 HAMZA_WASL_QAT),
    SpellingItem("أحمد", "احمد",
                 "أحمد عَلَم يبدأ بهمزة قطع، فتُكتب الهمزة.",
                 HAMZA_WASL_QAT),
    SpellingItem("انطلق", "إنطلق",
                 "الفعل الخماسي انطلق يبدأ بهمزة وصل بلا همزة مكتوبة.",
                 HAMZA_WASL_QAT),
    SpellingItem("إسلام", "اسلام",
                 "إسلام مصدر أسلم الرباعي، وهمزته همزة قطع.",
                 HAMZA_WASL_QAT),

    # hamza seat (medial / terminal)
    SpellingItem("سأل", "سئل",
                 "الهمزة المتوسطة المفتوحة بعد فتح تُكتب على ألف.",
                 HAMZA_SEAT),
    SpellingItem("مسؤول", "مسئول",
                 "الهمزة المتوسطة المضمومة بعد ضمّ تُكتب على واو.",
                 HAMZA_SEAT),
    SpellingItem("بئر", "بأر",
                 "الهمزة المتوسطة الساكنة بعد كسر تُكتب على نبرة (ياء).",
                 HAMZA_SEAT),
    SpellingItem("شيء", "شيئ",
                 "الهمزة المتطرفة بعد ساكن (ياء) تُكتب على السطر.",
                 HAMZA_SEAT),
    SpellingItem("دفء", "دفئ",
                 "الهمزة المتطرفة بعد ساكن تُكتب مفردة على السطر.",
                 HAMZA_SEAT),
    SpellingItem("قارئ", "قارىء",
                 "الهمزة المتطرفة بعد كسر تُكتب على نبرة.",
                 HAMZA_SEAT),

    # alif maqsura vs ya'
    SpellingItem("مستشفى", "مستشفي",
                 "مستشفى تنتهي بألف مقصورة؛ الاسم المقصور رابعًا فأكثر يُكتب بألف مقصورة.",
                 ALIF_MAQSURA),
    SpellingItem("رمى", "رمي",
                 "الفعل رمى أصل ألفه ياء، فتُكتب ألفًا مقصورة.",
                 ALIF_MAQSURA),
    SpellingItem("دعا", "دعى",
                 "الفعل دعا أصل ألفه واو، فتُكتب ألفًا طويلة.",
                 ALIF_MAQSURA),
    SpellingItem("إلى", "إلي",
                 "حرف الجر إلى يُكتب بألف مقصورة دائمًا.",
                 ALIF_MAQSURA),
    SpellingItem("هدى", "هدي",
                 "هدى اسم أصل ألفه ياء، فيُكتب بألف مقصورة.",
                 ALIF_MAQSURA),
    SpellingItem("على", "علي",
                 "حرف الجر على بألف مقصورة، بخلاف الاسم عليّ.",
                 ALIF_MAQSURA),

    # ta' marbuta vs ha'
    SpellingItem("مدرسة", "مدرسه",
                 "مدرسة تنتهي بتاء مربوطة تُنطق تاءً عند الوصل.",
                 TAA_MARBUTA),
    SpellingItem("كتابه", "كتابة",
                 "كتابه (كتابُهُ) تنتهي بهاء ضمير، لا تاء مربوطة.",
                 TAA_MARBUTA),
    SpellingItem("رحمة", "رحمه",
                 "رحمة اسم مؤنث بتاء مربوطة.",
                 TAA_MARBUTA),
    SpellingItem("فيه", "فية",
                 "فيه تنتهي بهاء، فهي حرف جر مع ضمير.",
                 TAA_MARBUTA),
    SpellingItem("شجرة", "شجره",
                 "شجرة اسم مؤنث بتاء مربوطة.",
                 TAA_MARBUTA),
    SpellingItem("له", "لة",
                 "له تنتهي بهاء ضمير، لا تاء مربوطة.",
                 TAA_MARBUTA),
]


def categories():
    return [(k, CATEGORY_NAMES[k]) for k in CATEGORY_NAMES]


def items_for(category=None):
    if category is None or category == "all":
        return list(ITEMS)
    return [it for it in ITEMS if it.category == category]


def check(item, typed):
    """Compare the learner's typed word to the correct spelling. Returns
    (correct: bool, message: str) with the rule shown either way."""
    typed = (typed or "").strip()
    if typed == item.correct:
        return True, f"صحيح! {item.rule}"
    return False, (f"غير صحيح. الصواب {item.correct} وليس {typed or '—'}. "
                   f"القاعدة: {item.rule}")
