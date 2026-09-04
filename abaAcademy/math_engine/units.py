# -*- coding: utf-8 -*-
"""
abaAcademy.math_engine.units
============================

A small, offline units converter with Arabic unit names — a practical everyday
tool. It converts within families (length, mass, volume, temperature, time,
speed, area, digital storage) by expressing each unit as a factor relative to a
base unit; temperature is handled specially because it is affine, not linear.

No network, no data files — the factors are constants. Values are returned as
numbers; the GUI speaks them. This is a feature added on top of the requested
V2.0 set because unit conversion is a constant need in study and daily life.
"""

from __future__ import annotations


# family -> { unit_key: (arabic_name, factor_to_base) }
# factor_to_base: value_in_base = value * factor
_FAMILIES = {
    "length": {
        "mm": ("مليمتر", 0.001), "cm": ("سنتيمتر", 0.01), "m": ("متر", 1.0),
        "km": ("كيلومتر", 1000.0), "inch": ("إنش", 0.0254),
        "foot": ("قدم", 0.3048), "mile": ("ميل", 1609.344),
    },
    "mass": {
        "mg": ("مليغرام", 1e-6), "g": ("غرام", 0.001), "kg": ("كيلوغرام", 1.0),
        "ton": ("طن", 1000.0), "lb": ("رطل", 0.45359237),
        "oz": ("أونصة", 0.028349523),
    },
    "volume": {
        "ml": ("مليلتر", 0.001), "l": ("لتر", 1.0), "m3": ("متر مكعب", 1000.0),
        "cup": ("كوب", 0.24), "gallon": ("غالون", 3.785411784),
    },
    "time": {
        "s": ("ثانية", 1.0), "min": ("دقيقة", 60.0), "h": ("ساعة", 3600.0),
        "day": ("يوم", 86400.0), "week": ("أسبوع", 604800.0),
    },
    "speed": {
        "mps": ("متر/ثانية", 1.0), "kmh": ("كم/ساعة", 0.2777777778),
        "mph": ("ميل/ساعة", 0.44704),
    },
    "area": {
        "m2": ("متر مربع", 1.0), "km2": ("كم مربع", 1e6),
        "hectare": ("هكتار", 10000.0), "cm2": ("سم مربع", 1e-4),
    },
    "storage": {
        "byte": ("بايت", 1.0), "kb": ("كيلوبايت", 1024.0),
        "mb": ("ميغابايت", 1048576.0), "gb": ("غيغابايت", 1073741824.0),
        "tb": ("تيرابايت", 1099511627776.0),
    },
}

# family display names in Arabic
FAMILY_NAMES = {
    "length": "الطول", "mass": "الكتلة", "volume": "الحجم", "time": "الزمن",
    "speed": "السرعة", "area": "المساحة", "storage": "التخزين الرقمي",
    "temperature": "الحرارة",
}


def families():
    """List of (family_key, arabic_name)."""
    keys = list(_FAMILIES.keys()) + ["temperature"]
    return [(k, FAMILY_NAMES[k]) for k in keys]


def units_in(family):
    """List of (unit_key, arabic_name) for a family."""
    if family == "temperature":
        return [("c", "مئوية"), ("f", "فهرنهايت"), ("k", "كلفن")]
    return [(k, v[0]) for k, v in _FAMILIES[family].items()]


def convert(family, from_unit, to_unit, value):
    """Convert ``value`` from one unit to another within a family. Raises
    ValueError on unknown units."""
    if family == "temperature":
        return _convert_temp(from_unit, to_unit, value)
    fam = _FAMILIES.get(family)
    if fam is None:
        raise ValueError("فئة غير معروفة.")
    if from_unit not in fam or to_unit not in fam:
        raise ValueError("وحدة غير معروفة.")
    base = value * fam[from_unit][1]
    return base / fam[to_unit][1]


def _convert_temp(from_unit, to_unit, value):
    # to celsius first
    if from_unit == "c":
        c = value
    elif from_unit == "f":
        c = (value - 32) * 5.0 / 9.0
    elif from_unit == "k":
        c = value - 273.15
    else:
        raise ValueError("وحدة حرارة غير معروفة.")
    # celsius to target
    if to_unit == "c":
        return c
    if to_unit == "f":
        return c * 9.0 / 5.0 + 32
    if to_unit == "k":
        return c + 273.15
    raise ValueError("وحدة حرارة غير معروفة.")


def unit_name(family, unit):
    for k, name in units_in(family):
        if k == unit:
            return name
    return unit
