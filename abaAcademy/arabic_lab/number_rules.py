# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.number_rules
==================================

Two rule-based Arabic drills:

**العدد والمعدود** — writing a number with the thing counted, in the
nominative (عندي … ):

* 1 and 2 follow the noun as adjectives and agree with it:
  كتابٌ واحدٌ، قصّتان اثنتان.
* 3–10 take the opposite gender of the noun's *singular*, and the noun is
  a genitive plural: ثلاثةُ كتبٍ، ثلاثُ قصصٍ (ثماني قصصٍ).
* 11 and 12 agree in both parts: أحدَ عشرَ كتابًا، إحدى عشرةَ قصّةً؛
  اثنا عشرَ، اثنتا عشرةَ.
* 13–19: the units part takes the opposite gender, عشر agrees:
  ثلاثةَ عشرَ كتابًا، ثلاثَ عشرةَ قصّةً.
* 20, 30 … 90 do not change; 21–99 join units and tens with و, the units
  following the rules above. From 11 to 99 the noun is a singular accusative
  (تمييز منصوب).
* 100, 200, 300 … 900 and 1000 do not change for gender, and the noun is a
  singular genitive: مئةُ كتابٍ، مئتا قصّةٍ، ثلاثُمئةِ كتابٍ، ألفُ قصّةٍ.

**اللام الشمسية والقمرية** — the lam of ال is silent and the next letter
doubled before the fourteen sun letters, and pronounced before the
fourteen moon letters.

Nouns are written without short vowels except the tanween of the
accusative, as in ordinary print.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Noun:
    singular: str
    plural: str
    feminine: bool
    accusative: str          # indefinite accusative singular, e.g. كتابًا / قصةً


NOUNS: Tuple[Noun, ...] = (
    Noun("كتاب", "كتب", False, "كتابًا"),
    Noun("قلم", "أقلام", False, "قلمًا"),
    Noun("طالب", "طلاب", False, "طالبًا"),
    Noun("رجل", "رجال", False, "رجلًا"),
    Noun("بيت", "بيوت", False, "بيتًا"),
    Noun("يوم", "أيام", False, "يومًا"),
    Noun("شهر", "أشهر", False, "شهرًا"),
    Noun("سؤال", "أسئلة", False, "سؤالًا"),
    Noun("درس", "دروس", False, "درسًا"),
    Noun("باب", "أبواب", False, "بابًا"),
    Noun("ولد", "أولاد", False, "ولدًا"),
    Noun("جبل", "جبال", False, "جبلًا"),
    Noun("نهر", "أنهار", False, "نهرًا"),
    Noun("سطر", "أسطر", False, "سطرًا"),
    Noun("حاسوب", "حواسيب", False, "حاسوبًا"),
    Noun("صديق", "أصدقاء", False, "صديقًا"),
    Noun("معلم", "معلمين", False, "معلمًا"),
    Noun("فصل", "فصول", False, "فصلًا"),
    Noun("قصة", "قصص", True, "قصةً"),
    Noun("شجرة", "أشجار", True, "شجرةً"),
    Noun("سيارة", "سيارات", True, "سيارةً"),
    Noun("مدرسة", "مدارس", True, "مدرسةً"),
    Noun("ورقة", "أوراق", True, "ورقةً"),
    Noun("طالبة", "طالبات", True, "طالبةً"),
    Noun("ساعة", "ساعات", True, "ساعةً"),
    Noun("دقيقة", "دقائق", True, "دقيقةً"),
    Noun("سنة", "سنوات", True, "سنةً"),
    Noun("غرفة", "غرف", True, "غرفةً"),
    Noun("مدينة", "مدن", True, "مدينةً"),
    Noun("نافذة", "نوافذ", True, "نافذةً"),
    Noun("بنت", "بنات", True, "بنتًا"),
    Noun("رسالة", "رسائل", True, "رسالةً"),
    Noun("لغة", "لغات", True, "لغةً"),
    Noun("كلمة", "كلمات", True, "كلمةً"),
    Noun("صفحة", "صفحات", True, "صفحةً"),
    Noun("جملة", "جمل", True, "جملةً"),
)

# 3–10: (form used with a masculine noun, form used with a feminine noun)
_UNITS = {3: ("ثلاثة", "ثلاث"), 4: ("أربعة", "أربع"), 5: ("خمسة", "خمس"),
          6: ("ستة", "ست"), 7: ("سبعة", "سبع"), 8: ("ثمانية", "ثماني"),
          9: ("تسعة", "تسع"), 10: ("عشرة", "عشر")}
_TENS = {20: "عشرون", 30: "ثلاثون", 40: "أربعون", 50: "خمسون", 60: "ستون",
         70: "سبعون", 80: "ثمانون", 90: "تسعون"}
_HUNDREDS = {100: "مئة", 200: "مئتا", 300: "ثلاثمئة", 400: "أربعمئة", 500: "خمسمئة",
             600: "ستمئة", 700: "سبعمئة", 800: "ثمانمئة", 900: "تسعمئة", 1000: "ألف"}

SUPPORTED = list(range(1, 100)) + sorted(_HUNDREDS)


def _unit(n: int, feminine_noun: bool) -> str:
    """3–9 with opposite gender."""
    m, f = _UNITS[n]
    return f if feminine_noun else m


def number_phrase(n: int, noun: Noun) -> str:
    """The correct nominative phrase for ``n`` of ``noun``."""
    fem = noun.feminine
    if n == 1:
        return f"{noun.singular} {'واحدة' if fem else 'واحد'}"
    if n == 2:
        dual = (noun.singular[:-1] + "تان") if noun.singular.endswith("ة") else noun.singular + "ان"
        return f"{dual} {'اثنتان' if fem else 'اثنان'}"
    if 3 <= n <= 10:
        return f"{_unit(n, fem)} {noun.plural}"
    if n == 11:
        return f"{'إحدى عشرة' if fem else 'أحد عشر'} {noun.accusative}"
    if n == 12:
        return f"{'اثنتا عشرة' if fem else 'اثنا عشر'} {noun.accusative}"
    if 13 <= n <= 19:
        return f"{_unit(n - 10, fem)} {'عشرة' if fem else 'عشر'} {noun.accusative}"
    if 20 <= n <= 99:
        tens, units = (n // 10) * 10, n % 10
        if units == 0:
            return f"{_TENS[tens]} {noun.accusative}"
        if units == 1:
            u = "إحدى" if fem else "واحد"
        elif units == 2:
            u = "اثنتان" if fem else "اثنان"
        else:
            u = _unit(units, fem)
        return f"{u} و{_TENS[tens]} {noun.accusative}"
    if n in _HUNDREDS:
        return f"{_HUNDREDS[n]} {noun.singular}"
    raise ValueError(n)


def rule_for(n: int, noun: Noun) -> str:
    g = "مؤنّث" if noun.feminine else "مذكّر"
    if n in (1, 2):
        return (f"العددان ١ و٢ يأتيان بعد المعدود صفةً له ويطابقانه في التذكير والتأنيث، "
                f"و{noun.singular} {g}.")
    if 3 <= n <= 10:
        return (f"الأعداد من ٣ إلى ١٠ تخالف المعدود في التذكير والتأنيث (بحسب مفرده)، "
                f"والمعدود جمع مجرور. مفرد المعدود {noun.singular} {g}، فيكون العدد "
                f"{'مذكّرًا بلا تاء' if noun.feminine else 'مؤنّثًا بالتاء'}.")
    if n in (11, 12):
        return ("العددان ١١ و١٢ يطابقان المعدود في جزأيهما، والمعدود مفرد منصوب (تمييز).")
    if 13 <= n <= 19:
        return ("من ١٣ إلى ١٩: الجزء الأول يخالف المعدود، والجزء الثاني (عشر) يطابقه، "
                "والمعدود مفرد منصوب.")
    if 20 <= n <= 99:
        tail = "" if n % 10 == 0 else (" والآحاد قبلها تتبع قاعدتها: ١ و٢ تطابقان، ومن ٣ إلى ٩ تخالف."
                                       if n % 10 > 2 or n % 10 in (1, 2) else "")
        return "ألفاظ العقود (عشرون إلى تسعين) لا تتغيّر، والمعدود مفرد منصوب." + tail
    return "المئة والألف ومضاعفاتهما لا تتغيّر بالتذكير والتأنيث، والمعدود بعدها مفرد مجرور."


def _wrong_gender(n: int, noun: Noun) -> str:
    flipped = Noun(noun.singular, noun.plural, not noun.feminine, noun.accusative)
    return number_phrase(n, flipped)


def distractors(n: int, noun: Noun) -> List[str]:
    """The mistakes learners really make for this number."""
    right = number_phrase(n, noun)
    out = []
    if n not in _HUNDREDS:
        out.append(_wrong_gender(n, noun))
    if 3 <= n <= 10:
        out.append(f"{_unit(n, noun.feminine)} {noun.singular}")
        out.append(f"{_unit(n, not noun.feminine)} {noun.singular}")
    elif 11 <= n <= 99:
        num = right.rsplit(" ", 1)[0]
        out.append(f"{num} {noun.plural}")
        out.append(f"{num} {noun.singular}")
    elif n in _HUNDREDS:
        out.append(f"{_HUNDREDS[n]} {noun.plural}")
        out.append(f"{_HUNDREDS[n]} {noun.accusative}")
    else:   # 1, 2
        out.append(f"{'واحد' if n == 1 else 'اثنان'} {noun.singular}" if noun.feminine
                   else f"{'واحدة' if n == 1 else 'اثنتان'} {noun.singular}")
    seen, uniq = {right}, []
    for d in out:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq[:3]


_AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


@dataclass
class Question:
    kind: str
    prompt: str
    answer: str
    options: List[str]
    explanation: str


def number_question(rng: Optional[random.Random] = None,
                    band: str = "all") -> Question:
    rng = rng or random.Random()
    bands = {"1-10": list(range(1, 11)), "11-19": list(range(11, 20)),
             "20-99": list(range(20, 100)), "100+": sorted(_HUNDREDS), "all": SUPPORTED}
    n = rng.choice(bands.get(band, SUPPORTED))
    noun = rng.choice(NOUNS)
    right = number_phrase(n, noun)
    opts = [right] + distractors(n, noun)
    rng.shuffle(opts)
    return Question("number", f"عندي ({str(n).translate(_AR)}) {noun.singular}. اختر الكتابة الصحيحة:",
                    right, opts, f"الصواب: عندي {right}. {rule_for(n, noun)}")


# ---------------------------------------------------------------------------
# sun and moon letters
# ---------------------------------------------------------------------------

SUN_LETTERS = "تثدذرزسشصضطظلن"
MOON_LETTERS = "ءأإآابجحخعغفقكمهوي"

_WORDS_AFTER_AL = (
    "الشمس", "القمر", "التلميذ", "الثوب", "الدرس", "الذهب", "الرجل", "الزيت", "السماء",
    "الشجرة", "الصبر", "الضوء", "الطريق", "الظهر", "الليل", "النور", "الأرض", "الباب",
    "الجبل", "الحديقة", "الخبز", "العين", "الغيم", "الفجر", "القلم", "الكتاب", "الماء",
    "الهلال", "الوقت", "اليوم", "التاريخ", "الدواء", "الرسالة", "السيارة", "الصديق",
    "الطالب", "النهر", "الإنسان", "البحر", "الجمل", "الحب", "الخير", "العلم", "الفصل",
    "المدرسة", "الولد", "اليد", "الثلج", "الذكرى", "الزهرة", "الشارع", "الضيف", "الظل",
)


def is_sun(letter: str) -> bool:
    return letter in SUN_LETTERS


def lam_kind(word: str) -> str:
    w = word.strip()
    for p in ("وال", "فال", "بال", "كال"):
        if w.startswith(p):
            w = "ال" + w[len(p):]
    if not w.startswith("ال") or len(w) < 3:
        raise ValueError("الكلمة لا تبدأ بـ ال.")
    return "sun" if is_sun(w[2]) else "moon"


def lam_explanation(word: str) -> str:
    kind = lam_kind(word)
    w = word[word.index("ال"):] if "ال" in word else word
    letter = w[2]
    if kind == "sun":
        return (f"{word}: اللام شمسية، تُكتب ولا تُنطق، ويُشدّد الحرف بعدها ({letter}ّ)، "
                f"لأنّ {letter} من الحروف الشمسية.")
    return (f"{word}: اللام قمرية، تُكتب وتُنطق ساكنة، لأنّ {letter} من الحروف القمرية "
            f"(ابغِ حجّك وخف عقيمه).")


def lam_question(rng: Optional[random.Random] = None,
                 words: Optional[Sequence[str]] = None) -> Question:
    rng = rng or random.Random()
    pool = list(words) if words else list(_WORDS_AFTER_AL)
    word = rng.choice(pool)
    kind = lam_kind(word)
    right = "شمسية" if kind == "sun" else "قمرية"
    return Question("lam", f"اللام في {word}: شمسية أم قمرية؟", right, ["شمسية", "قمرية"],
                    lam_explanation(word))


def dictionary_al_words(words: Sequence[str], limit: int = 400,
                        rng: Optional[random.Random] = None) -> List[str]:
    """Words from the word list that start with ال followed by a letter,
    for a wider pool of lam questions."""
    rng = rng or random.Random(7)
    cand = [w for w in words if w.startswith("ال") and 4 <= len(w) <= 9
            and (w[2] in SUN_LETTERS or w[2] in MOON_LETTERS) and w[2] != "ل" or
            (w.startswith("الل") and len(w) >= 5)]
    rng.shuffle(cand)
    return cand[:limit]
