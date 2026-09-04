# -*- coding: utf-8 -*-
"""
abaAcademy.tools.shortcuts_data
===============================

A curated directory of essential keyboard shortcuts for the apps a blind student
uses most, with Arabic descriptions. Data only — the trainer GUI and the quiz
build on this. Kept factual and conservative; these are stable, widely-documented
shortcuts.
"""

from __future__ import annotations

# category -> list of (keys, arabic_description)
SHORTCUTS = {
    "ويندوز": [
        ("Windows", "فتح قائمة ابدأ"),
        ("Windows + D", "إظهار سطح المكتب"),
        ("Windows + E", "فتح مستكشف الملفات"),
        ("Windows + L", "قفل الجهاز"),
        ("Alt + Tab", "التبديل بين النوافذ المفتوحة"),
        ("Alt + F4", "إغلاق النافذة الحالية"),
        ("Ctrl + C", "نسخ"),
        ("Ctrl + X", "قص"),
        ("Ctrl + V", "لصق"),
        ("Ctrl + Z", "تراجع"),
        ("Ctrl + Y", "إعادة"),
        ("Ctrl + A", "تحديد الكل"),
        ("Ctrl + S", "حفظ"),
        ("F2", "إعادة تسمية العنصر المحدّد"),
        ("Windows + M", "تصغير كل النوافذ"),
    ],
    "وورد": [
        ("Ctrl + B", "خط عريض"),
        ("Ctrl + I", "خط مائل"),
        ("Ctrl + U", "تسطير"),
        ("Ctrl + E", "توسيط الفقرة"),
        ("Ctrl + R", "محاذاة لليمين"),
        ("Ctrl + L", "محاذاة لليسار"),
        ("Ctrl + J", "ضبط الفقرة"),
        ("Ctrl + N", "مستند جديد"),
        ("Ctrl + P", "طباعة"),
        ("Ctrl + F", "بحث"),
        ("Ctrl + H", "استبدال"),
        ("Ctrl + Shift + <", "تصغير حجم الخط"),
        ("Ctrl + Shift + >", "تكبير حجم الخط"),
        ("Shift + F3", "تبديل حالة الأحرف"),
    ],
    "إكسل": [
        ("Ctrl + سهم", "الانتقال إلى حافة البيانات"),
        ("Ctrl + Home", "الانتقال إلى الخلية A1"),
        ("Ctrl + Space", "تحديد العمود كاملاً"),
        ("Shift + Space", "تحديد الصف كاملاً"),
        ("F2", "تحرير الخلية النشطة"),
        ("Alt + =", "الجمع التلقائي"),
        ("Ctrl + ;", "إدراج تاريخ اليوم"),
        ("Ctrl + Shift + L", "تشغيل التصفية"),
        ("Ctrl + Page Down", "الورقة التالية"),
        ("Ctrl + Page Up", "الورقة السابقة"),
    ],
    "المتصفّح": [
        ("Ctrl + T", "تبويب جديد"),
        ("Ctrl + W", "إغلاق التبويب"),
        ("Ctrl + Shift + T", "استعادة آخر تبويب مغلق"),
        ("Ctrl + Tab", "التبويب التالي"),
        ("Ctrl + L", "الانتقال إلى شريط العنوان"),
        ("Ctrl + R", "إعادة تحميل الصفحة"),
        ("Ctrl + D", "إضافة إلى المفضّلة"),
        ("Alt + سهم يسار", "الرجوع للصفحة السابقة"),
    ],
    "NVDA": [
        ("NVDA + N", "فتح قائمة NVDA"),
        ("NVDA + Q", "إنهاء NVDA"),
        ("NVDA + S", "تغيير وضع النطق"),
        ("NVDA + سهم أسفل", "قراءة الكل من الموضع الحالي"),
        ("NVDA + Tab", "قراءة العنصر الذي عليه التركيز"),
        ("NVDA + T", "قراءة عنوان النافذة"),
        ("NVDA + F7", "قائمة العناصر (الروابط والعناوين)"),
        ("NVDA + Space", "التبديل بين وضع التصفّح والتركيز"),
        ("NVDA + Ctrl + F", "البحث في النص"),
        ("NVDA + رقم", "إعلان تنسيق النص"),
    ],
}


def all_categories():
    return list(SHORTCUTS.keys())


def shortcuts_for(category):
    return SHORTCUTS.get(category, [])


def all_shortcuts():
    out = []
    for cat, items in SHORTCUTS.items():
        for keys, desc in items:
            out.append((cat, keys, desc))
    return out


def search(query):
    q = (query or "").strip()
    if not q:
        return all_shortcuts()
    return [(c, k, d) for c, k, d in all_shortcuts()
            if q in k or q in d or q in c]
