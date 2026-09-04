# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.conjugator
================================

Conjugate Arabic triliteral verbs across the personal pronouns for the past
(الماضي) and present (المضارع) tenses, plus the imperative (الأمر).

Honest scope — read this
------------------------
Arabic conjugation is only fully regular for the **sound verb** (الفعل الصحيح
السالم): a triliteral root whose three letters are all consonants, none of them
hamza, and the second and third not identical. For those, the rules are
deterministic and this module is reliable.

For the irregular families — the hollow verb (الأجوف, middle letter و/ي like
قال/باع), the defective (الناقص, last letter و/ي like دعا/رمى), the assimilated
(المثال, first letter و/ي like وصل), the doubled (المضعّف like مدّ), and the
hamzated (المهموز like أكل/سأل) — the surface form changes in ways a short rule
set gets wrong (vowel shifts, letter deletion, hamza seat changes). Rather than
print confident but wrong conjugations for those, this module **detects** the
verb type and, for the irregular families, returns a clear note that they need a
specialised treatment instead of guessing. That honesty matters: a student
learning صرف must not memorise a wrong form.

So: correct, complete tables for sound verbs; an honest "not supported yet"
for the irregular types, with the reason. The GUI states this plainly.
"""

from __future__ import annotations


# the 13 pronouns in the traditional order
PRONOUNS = [
    ("أنا", "1s"), ("نحن", "1p"),
    ("أنتَ", "2ms"), ("أنتِ", "2fs"), ("أنتما", "2d"),
    ("أنتم", "2mp"), ("أنتنّ", "2fp"),
    ("هو", "3ms"), ("هي", "3fs"), ("هما_م", "3md"), ("هما_ف", "3fd"),
    ("هم", "3mp"), ("هنّ", "3fp"),
]

_WEAK = set("وي")
_HAMZA = set("ءأإؤئآ")

_FATHA = "\u064E"
_DAMMA = "\u064F"
_KASRA = "\u0650"
_SUKUN = "\u0652"
_SHADDA = "\u0651"


def classify(root):
    """Classify a 3-letter Arabic verb (past 3ms surface form, e.g. كَتَبَ, قال,
    دعا). Returns (type_key, arabic_name).

    Note: users type the surface past form, not the abstract root. A middle or
    final ``ا`` in that surface form signals a hollow or defective verb (قال from
    ق-و-ل, دعا from د-ع-و), which we must NOT treat as sound."""
    letters = [c for c in root if c.strip() and c not in
               (_FATHA, _DAMMA, _KASRA, _SUKUN, _SHADDA)]
    if len(letters) != 3:
        return ("invalid", "غير ثلاثي")
    f, a, l = letters
    weak_or_alef = _WEAK | {"ا", "ى"}
    if f in _HAMZA or a in _HAMZA or l in _HAMZA:
        return ("hamzated", "مهموز")
    if a in weak_or_alef:
        return ("hollow", "أجوف")
    if l in weak_or_alef:
        return ("defective", "ناقص")
    if f in _WEAK:
        return ("assimilated", "مثال")
    if a == l:
        return ("doubled", "مضعّف")
    return ("sound", "صحيح سالم")


# past-tense suffixes for a sound verb (attached to the 3 root letters, the
# first two carrying fatحة, e.g. كَتَبَ). We work at the consonant-skeleton level
# and add the standard vowels as harakat.


def conjugate_past(root):
    """Full past-tense table for a sound triliteral root. Returns a list of
    (pronoun, form) or raises ValueError with an Arabic note if unsupported."""
    kind, name = classify(root)
    if kind != "sound":
        raise ValueError(f"هذا الفعل «{name}»؛ تصريفه يحتاج معالجة خاصة غير مدعومة "
                         f"بعد لضمان الصحّة.")
    f, a, l = list(root)
    # base: فَعَلَ  -> f+fatha, a+fatha, l (+ ending)
    base = f + _FATHA + a + _FATHA + l
    endings = {
        "1s": _SUKUN + "تُ", "1p": _SUKUN + "نا",
        "2ms": _SUKUN + "تَ", "2fs": _SUKUN + "تِ", "2d": _SUKUN + "تُما",
        "2mp": _SUKUN + "تُم", "2fp": _SUKUN + "تُنَّ",
        "3ms": _FATHA, "3fs": _FATHA + "تْ", "3md": _FATHA + "ا",
        "3fd": _FATHA + "تا", "3mp": _DAMMA + "وا", "3fp": _SUKUN + "نَ",
    }
    out = []
    for pr, code in PRONOUNS:
        end = endings[code]
        # for 3ms the last letter just takes fatha (فَعَلَ)
        form = base + end
        out.append((pr.replace("_م", " (مذكّر)").replace("_ف", " (مؤنّث)"), form))
    return out


def conjugate_present(root):
    """Full present-tense table for a sound triliteral root (بابه يَفعُل by
    default vowel), with the standard prefixes/suffixes. Each form is built
    explicitly from the root letters and harakat, so nothing is truncated."""
    kind, name = classify(root)
    if kind != "sound":
        raise ValueError(f"هذا الفعل «{name}»؛ تصريفه يحتاج معالجة خاصة غير مدعومة "
                         f"بعد لضمان الصحّة.")
    f, a, l = list(root)
    # the shared stem body after the prefix: فْعُ + last letter
    body = f + _SUKUN + a + _DAMMA + l          # فْعُل
    def pref(p):
        return p + _FATHA + body                 # e.g. يَفْعُل

    forms = {
        # singular
        "1s": "أَ" + body,
        "1p": "نَ" + body,
        "3ms": pref("ي"),
        "3fs": pref("ت"),
        "2ms": pref("ت"),
        # 2fs: تَفْعُلِينَ (drop final sukun on last letter, add kasra + ينَ)
        "2fs": "تَ" + f + _SUKUN + a + _DAMMA + l + _KASRA + "ينَ",
        # duals: ...َانِ
        "2d": "تَ" + f + _SUKUN + a + _DAMMA + l + _FATHA + "انِ",
        "3md": "يَ" + f + _SUKUN + a + _DAMMA + l + _FATHA + "انِ",
        "3fd": "تَ" + f + _SUKUN + a + _DAMMA + l + _FATHA + "انِ",
        # masc plural: ...ُونَ
        "2mp": "تَ" + f + _SUKUN + a + _DAMMA + l + _DAMMA + "ونَ",
        "3mp": "يَ" + f + _SUKUN + a + _DAMMA + l + _DAMMA + "ونَ",
        # fem plural: ...ْنَ
        "2fp": "تَ" + f + _SUKUN + a + _DAMMA + l + _SUKUN + "نَ",
        "3fp": "يَ" + f + _SUKUN + a + _DAMMA + l + _SUKUN + "نَ",
    }
    out = []
    for pr, code in PRONOUNS:
        out.append((pr.replace("_م", " (مذكّر)").replace("_ف", " (مؤنّث)"),
                    forms[code]))
    return out


def conjugate_imperative(root):
    """Imperative (أمر) for the addressee pronouns of a sound verb."""
    kind, name = classify(root)
    if kind != "sound":
        raise ValueError(f"هذا الفعل «{name}»؛ صيغة الأمر تحتاج معالجة خاصة غير "
                         f"مدعومة بعد لضمان الصحّة.")
    f, a, l = list(root)
    # form: اُفْعُلْ (hamzat wasl + f sukun + a damma + l sukun)
    stem = f + _SUKUN + a + _DAMMA + l
    forms = {
        "2ms": "ا" + stem + _SUKUN,
        "2fs": "ا" + f + _SUKUN + a + _DAMMA + l + _KASRA + "ي",
        "2d": "ا" + f + _SUKUN + a + _DAMMA + l + _FATHA + "ا",
        "2mp": "ا" + f + _SUKUN + a + _DAMMA + l + _DAMMA + "وا",
        "2fp": "ا" + f + _SUKUN + a + _DAMMA + l + _SUKUN + "نَ",
    }
    order = [("أنتَ", "2ms"), ("أنتِ", "2fs"), ("أنتما", "2d"),
             ("أنتم", "2mp"), ("أنتنّ", "2fp")]
    return [(pr, forms[code]) for pr, code in order]


def conjugate(root, tense):
    """Dispatch by tense: 'past' | 'present' | 'imperative'."""
    if tense == "past":
        return conjugate_past(root)
    if tense == "present":
        return conjugate_present(root)
    if tense == "imperative":
        return conjugate_imperative(root)
    raise ValueError("زمن غير معروف.")
