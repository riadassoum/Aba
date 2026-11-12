# -*- coding: utf-8 -*-
"""
abaAcademy.display_prefs
========================

Display preferences for learners with low vision and for sighted people who
sit with a blind learner (a parent, a teacher, a caretaker): text size,
colour theme, bold text, and a highlight that shows which control has the
keyboard focus.

This module is pure data (no wx) so it can be tested anywhere; ``gui.display``
applies the preferences to the screens.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional, Tuple

RGB = Tuple[int, int, int]

FONT_SCALES = (100, 125, 150, 175, 200, 250)

# name: (Arabic label, background, foreground, focus background, focus foreground)
THEMES: Dict[str, Tuple[str, Optional[RGB], Optional[RGB], RGB, RGB]] = {
    "system": ("ألوان النظام", None, None, (255, 215, 0), (0, 0, 0)),
    "light": ("فاتح: نصّ أسود على خلفية بيضاء", (255, 255, 255), (0, 0, 0), (255, 215, 0), (0, 0, 0)),
    "dark": ("داكن: نصّ أبيض على خلفية سوداء", (0, 0, 0), (255, 255, 255), (0, 90, 200), (255, 255, 255)),
    "yellow_on_black": ("تباين عالٍ: أصفر على أسود", (0, 0, 0), (255, 255, 0), (255, 255, 255), (0, 0, 0)),
    "black_on_yellow": ("تباين عالٍ: أسود على أصفر", (255, 255, 160), (0, 0, 0), (0, 0, 160), (255, 255, 255)),
    "white_on_blue": ("أبيض على أزرق داكن", (0, 0, 110), (255, 255, 255), (255, 215, 0), (0, 0, 0)),
}

SETTING_KEYS = {
    "font_scale": "display_font_scale",
    "theme": "display_theme",
    "bold": "display_bold",
    "focus_highlight": "display_focus_highlight",
    "describe_features": "display_describe_features",
}


@dataclass
class DisplayPrefs:
    font_scale: int = 100
    theme: str = "system"
    bold: bool = False
    focus_highlight: bool = True
    describe_features: bool = True

    # -- derived values ------------------------------------------------------

    def scaled(self, base_points: int) -> int:
        """Point size for a control whose normal size is ``base_points``."""
        base = base_points if base_points and base_points > 0 else 10
        return max(6, round(base * self.font_scale / 100))

    def colours(self) -> Tuple[Optional[RGB], Optional[RGB]]:
        _, bg, fg, _, _ = THEMES.get(self.theme, THEMES["system"])
        return bg, fg

    def focus_colours(self) -> Tuple[RGB, RGB]:
        _, _, _, fbg, ffg = THEMES.get(self.theme, THEMES["system"])
        return fbg, ffg

    def is_default(self) -> bool:
        return self == DisplayPrefs()

    def describe(self) -> str:
        parts = [f"حجم الخطّ {self.font_scale}٪", THEMES.get(self.theme, THEMES["system"])[0]]
        if self.bold:
            parts.append("خطّ عريض")
        parts.append("إبراز العنصر المحدّد مفعّل" if self.focus_highlight else "إبراز العنصر المحدّد معطّل")
        return "، ".join(parts) + "."

    # -- normalisation -------------------------------------------------------

    def normalised(self) -> "DisplayPrefs":
        scale = min(FONT_SCALES, key=lambda s: abs(s - int(self.font_scale or 100)))
        theme = self.theme if self.theme in THEMES else "system"
        return DisplayPrefs(scale, theme, bool(self.bold), bool(self.focus_highlight), bool(self.describe_features))

    # -- persistence (any object with get_setting / set_setting) ---------------

    @classmethod
    def load(cls, store) -> "DisplayPrefs":
        if store is None:
            return cls()

        def get(key, default):
            try:
                return store.get_setting(SETTING_KEYS[key], default)
            except Exception:
                return default

        def flag(key, default):
            v = str(get(key, "1" if default else "0")).strip().lower()
            return v in ("1", "true", "yes", "on")

        try:
            scale = int(get("font_scale", "100") or 100)
        except (TypeError, ValueError):
            scale = 100
        return cls(scale, str(get("theme", "system") or "system"), flag("bold", False),
                   flag("focus_highlight", True), flag("describe_features", True)).normalised()

    def save(self, store) -> None:
        p = self.normalised()
        for key, value in asdict(p).items():
            if isinstance(value, bool):
                value = "1" if value else "0"
            store.set_setting(SETTING_KEYS[key], str(value))


def contrast_ratio(a: RGB, b: RGB) -> float:
    """WCAG contrast ratio between two colours (1 … 21)."""
    def lum(c):
        def ch(v):
            v = v / 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b_ = (ch(x) for x in c)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)
