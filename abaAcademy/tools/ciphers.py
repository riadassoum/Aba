# -*- coding: utf-8 -*-
"""
abaAcademy.tools.ciphers
========================

مختبر التشفير — the classical ciphers that open every cryptography course,
for Arabic and English alike: Caesar (with brute force), Atbash, Vigenère,
the rail fence, and letter-frequency analysis that breaks a Caesar cipher
by itself; plus the encodings a programmer meets (binary, hexadecimal,
Base64, the Arabic abjad numerals). Everything here is the textbook
algorithm, written from scratch.
"""

from __future__ import annotations

import base64
import binascii
from collections import Counter
from typing import Dict, List, Tuple

AR = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"
EN = "abcdefghijklmnopqrstuvwxyz"
# relative frequency order of letters in ordinary text
AR_FREQ = "اليمونهرتبعدسفكقحجشصطزخذثضغظ"
EN_FREQ = "etaoinshrdlcumwfgypbvkjxqz"
AR_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})


def alphabet_of(text: str) -> str:
    ar = sum(1 for c in text if c in AR or c in "أإآةىؤئ")
    en = sum(1 for c in text.lower() if c in EN)
    return AR if ar >= en else EN


def _prep(text: str, alpha: str) -> str:
    return text.translate(AR_FOLD) if alpha is AR else text


def _shift_char(c: str, k: int, alpha: str) -> str:
    low = c.lower() if alpha is EN else c
    if low not in alpha:
        return c
    out = alpha[(alpha.index(low) + k) % len(alpha)]
    return out.upper() if (alpha is EN and c.isupper()) else out


def caesar(text: str, key: int, decrypt: bool = False) -> str:
    alpha = alphabet_of(text)
    k = -key if decrypt else key
    return "".join(_shift_char(c, k, alpha) for c in _prep(text, alpha))


def atbash(text: str) -> str:
    alpha = alphabet_of(text)
    out = []
    for c in _prep(text, alpha):
        low = c.lower() if alpha is EN else c
        if low in alpha:
            r = alpha[len(alpha) - 1 - alpha.index(low)]
            out.append(r.upper() if alpha is EN and c.isupper() else r)
        else:
            out.append(c)
    return "".join(out)


def vigenere(text: str, key: str, decrypt: bool = False) -> str:
    alpha = alphabet_of(text + key)
    key = [alpha.index(c) for c in _prep(key.lower() if alpha is EN else key, alpha) if c in alpha]
    if not key:
        raise ValueError("المفتاح يجب أن يحوي حروفًا من أبجدية النصّ.")
    out, j = [], 0
    for c in _prep(text, alpha):
        low = c.lower() if alpha is EN else c
        if low in alpha:
            k = key[j % len(key)]
            out.append(_shift_char(c, -k if decrypt else k, alpha))
            j += 1
        else:
            out.append(c)
    return "".join(out)


def rail_fence(text: str, rails: int, decrypt: bool = False) -> str:
    if rails < 2 or rails >= len(text):
        return text
    pattern = list(range(rails)) + list(range(rails - 2, 0, -1))
    order = [pattern[i % len(pattern)] for i in range(len(text))]
    idx = sorted(range(len(text)), key=lambda i: (order[i], i))
    if not decrypt:
        return "".join(text[i] for i in idx)
    out = [""] * len(text)
    for c, i in zip(text, idx):
        out[i] = c
    return "".join(out)


def frequencies(text: str) -> List[Tuple[str, int]]:
    alpha = alphabet_of(text)
    t = _prep(text.lower() if alpha is EN else text, alpha)
    return Counter(c for c in t if c in alpha).most_common()


def brute_force(text: str) -> List[Tuple[int, str]]:
    alpha = alphabet_of(text)
    return [(k, caesar(text, k, decrypt=True)) for k in range(1, len(alpha))]


def crack_caesar(text: str) -> Tuple[int, str]:
    """Pick the key whose decryption best matches the language's letter
    frequencies (a simple chi-squared-like score on rank)."""
    alpha = alphabet_of(text)
    ref = AR_FREQ if alpha is AR else EN_FREQ
    weight: Dict[str, float] = {c: len(ref) - i for i, c in enumerate(ref)}
    best = (0, text, -1.0)
    for k in range(len(alpha)):
        plain = caesar(text, k, decrypt=True)
        score = sum(weight.get(c.lower(), 0) for c in plain)
        if score > best[2]:
            best = (k, plain, score)
    return best[0], best[1]


# -- encodings ---------------------------------------------------------------

def to_binary(text: str) -> str:
    return " ".join(f"{b:08b}" for b in text.encode("utf-8"))


def from_binary(bits: str) -> str:
    parts = bits.split()
    if not parts or any(set(p) - {"0", "1"} for p in parts):
        raise ValueError("اكتب بايتات ثنائية مفصولة بمسافات، مثل 01000001.")
    return bytes(int(p, 2) for p in parts).decode("utf-8", errors="replace")


def to_hex(text: str) -> str:
    return text.encode("utf-8").hex(" ")


def from_hex(h: str) -> str:
    try:
        return bytes.fromhex(h).decode("utf-8", errors="replace")
    except ValueError:
        raise ValueError("ليس هذا ترميزًا ست عشريًّا صحيحًا.")


def to_base64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def from_base64(s: str) -> str:
    try:
        return base64.b64decode(s.strip(), validate=True).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        raise ValueError("ليس هذا ترميز Base64 صحيحًا.")


# حساب الجُمَّل (abjad numerals), the Mashriqi order
ABJAD = {"ا": 1, "أ": 1, "إ": 1, "آ": 1, "ء": 1, "ب": 2, "ج": 3, "د": 4, "ه": 5, "ة": 5, "و": 6, "ؤ": 6, "ز": 7,
         "ح": 8, "ط": 9, "ي": 10, "ى": 10, "ئ": 10, "ك": 20, "ل": 30, "م": 40, "ن": 50, "س": 60, "ع": 70, "ف": 80,
         "ص": 90, "ق": 100, "ر": 200, "ش": 300, "ت": 400, "ث": 500, "خ": 600, "ذ": 700, "ض": 800, "ظ": 900,
         "غ": 1000}


def abjad(text: str) -> int:
    return sum(ABJAD.get(c, 0) for c in text)


METHODS = ["قيصر: تشفير", "قيصر: فكّ بالمفتاح", "قيصر: كسر آلي بتحليل التكرار", "قيصر: جرّب كل المفاتيح",
           "أتباش", "فيجنير: تشفير", "فيجنير: فكّ", "السياج: تشفير", "السياج: فكّ", "تكرار الحروف",
           "إلى الثنائي", "من الثنائي", "إلى الست عشري", "من الست عشري", "إلى Base64", "من Base64",
           "حساب الجُمَّل"]


def run(method: int, text: str, key: str = "") -> str:
    name = METHODS[method]
    k = key.strip()

    def num(default: int) -> int:
        try:
            return int(k.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        except ValueError:
            return default
    if name == "قيصر: تشفير":
        return caesar(text, num(3))
    if name == "قيصر: فكّ بالمفتاح":
        return caesar(text, num(3), decrypt=True)
    if name.startswith("قيصر: كسر"):
        key_found, plain = crack_caesar(text)
        return f"المفتاح المرجّح {key_found}:\n{plain}"
    if name.startswith("قيصر: جرّب"):
        return "\n".join(f"{k}: {p}" for k, p in brute_force(text))
    if name == "أتباش":
        return atbash(text)
    if name.startswith("فيجنير"):
        return vigenere(text, k or "مفتاح", decrypt=name.endswith("فكّ"))
    if name.startswith("السياج"):
        return rail_fence(text, num(3), decrypt=name.endswith("فكّ"))
    if name == "تكرار الحروف":
        f = frequencies(text)
        total = sum(n for _, n in f) or 1
        return "\n".join(f"{c}: {n} مرّة ({round(100 * n / total)}٪)" for c, n in f)
    if name == "إلى الثنائي":
        return to_binary(text)
    if name == "من الثنائي":
        return from_binary(text)
    if name == "إلى الست عشري":
        return to_hex(text)
    if name == "من الست عشري":
        return from_hex(text)
    if name == "إلى Base64":
        return to_base64(text)
    if name == "من Base64":
        return from_base64(text)
    if name == "حساب الجُمَّل":
        return f"مجموع الجُمَّل {abjad(text)}"
    raise ValueError(name)
