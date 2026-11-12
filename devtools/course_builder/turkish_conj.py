# -*- coding: utf-8 -*-
"""Rule-based Turkish conjugation (present continuous, its negative, the
definite past and the future) with vowel harmony and consonant softening."""

BACK, FRONT = set("aıou"), set("eiöü")
VOW = BACK | FRONT
VOICELESS = set("çfhkpsşt")
SOFTEN = {"et": "ed", "git": "gid", "tat": "tad", "güt": "güd"}
PERSONS = ["ben", "sen", "o", "biz", "siz", "onlar"]


def last_vowel(s):
    for ch in reversed(s):
        if ch in VOW:
            return ch
    return "e"


def h4(s):
    return {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}[last_vowel(s)]


def h2(s):
    return "a" if last_vowel(s) in BACK else "e"


def stem(inf):
    return inf[:-3]


def _soft(st):
    for k, v in SOFTEN.items():
        if st == k or st.endswith(" " + k):
            return st[: len(st) - len(k)] + v
    return st


def present_cont(inf):
    st = stem(inf)
    if st in ("ye", "de"):
        base = st[0] + "iyor"
    elif st[-1] in VOW:
        cut = st[:-1]
        base = cut + h4(cut) + "yor"
    else:
        base = _soft(st) + h4(st) + "yor"
    return dict(zip(PERSONS, [base + "um", base + "sun", base, base + "uz", base + "sunuz", base + "lar"]))


def present_cont_neg(inf):
    st = stem(inf)
    base = st + "m" + h4(st) + "yor"
    return dict(zip(PERSONS, [base + "um", base + "sun", base, base + "uz", base + "sunuz", base + "lar"]))


def past(inf):
    st = stem(inf)
    d = "t" if st[-1] in VOICELESS else "d"
    base = st + d + h4(st)
    v = h4(st)
    return dict(zip(PERSONS, [base + "m", base + "n", base, base + "k", base + "n" + v + "z", base + "l" + h2(st) + "r"]))


def future(inf):
    st = stem(inf)
    if st in ("ye", "de"):
        st2 = st[0] + "iy"
        a = "e"
    else:
        st2 = (st + "y") if st[-1] in VOW else _soft(st)
        a = h2(st)
    suf = "ecek" if a == "e" else "acak"
    soft = suf[:-1] + "ğ"
    v = "i" if a == "e" else "ı"
    return dict(zip(PERSONS, [st2 + soft + v + "m", st2 + suf + "s" + v + "n", st2 + suf,
                              st2 + soft + v + "z", st2 + suf + "s" + v + "n" + v + "z", st2 + suf + "l" + a + "r"]))


VERBS = [
    ("gelmek", "أتى"), ("gitmek", "ذهب"), ("yapmak", "فعل"), ("olmak", "كان، صار"), ("istemek", "أراد"),
    ("bilmek", "عرف"), ("görmek", "رأى"), ("almak", "أخذ، اشترى"), ("vermek", "أعطى"), ("demek", "قال"),
    ("yemek", "أكل"), ("içmek", "شرب"), ("okumak", "قرأ"), ("yazmak", "كتب"), ("konuşmak", "تكلّم"),
    ("anlamak", "فهم"), ("sevmek", "أحبّ"), ("çalışmak", "عمل، درس"), ("oturmak", "جلس، سكن"), ("bakmak", "نظر"),
    ("beklemek", "انتظر"), ("düşünmek", "فكّر"), ("söylemek", "قال، أخبر"), ("başlamak", "بدأ"), ("bitirmek", "أنهى"),
    ("öğrenmek", "تعلّم"), ("öğretmek", "علّم"), ("uyumak", "نام"), ("kalmak", "بقي"), ("koşmak", "ركض"),
    ("açmak", "فتح"), ("kapatmak", "أغلق"), ("satmak", "باع"), ("tanımak", "عرف (شخصًا)"), ("unutmak", "نسي"),
    ("hatırlamak", "تذكّر"), ("sormak", "سأل"), ("getirmek", "أحضر"), ("binmek", "ركب"), ("inmek", "نزل"),
    ("çıkmak", "خرج"), ("girmek", "دخل"), ("aramak", "بحث، اتّصل"), ("bulmak", "وجد"), ("duymak", "سمع"),
    ("dinlemek", "استمع"), ("gülmek", "ضحك"), ("ağlamak", "بكى"), ("yürümek", "مشى"), ("oynamak", "لعب"),
    ("etmek", "فعل (مع الأسماء)"), ("yaşamak", "عاش"), ("sevinmek", "فرح"), ("giymek", "لبس"), ("göndermek", "أرسل"),
]

TENSES = [
    ("present_cont", "المضارع المستمرّ (‎-iyor‎)", present_cont),
    ("present_neg", "نفي المضارع المستمرّ (‎-miyor‎)", present_cont_neg),
    ("past", "الماضي الشهودي (‎-di‎)", past),
    ("future", "المستقبل (‎-ecek‎)", future),
]

if __name__ == "__main__":
    for inf in ("gelmek", "gitmek", "istemek", "okumak", "yemek", "etmek", "başlamak", "görmek", "yapmak"):
        print(inf, present_cont(inf)["ben"], present_cont_neg(inf)["o"], past(inf)["biz"], past(inf)["onlar"],
              future(inf)["ben"], future(inf)["siz"])
