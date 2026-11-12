# -*- coding: utf-8 -*-
"""
abaAcademy.tools.praytimes
==========================

Offline prayer times, Qibla direction and distance to Makkah.

The times are computed from the sun's position with the standard astronomical
formulas (equation of time and solar declination from the Astronomical
Almanac's low-precision solar coordinates), using the twilight angles of the
recognised calculation authorities. No network is needed, so the times work in
a classroom or on a plane.

Supported conventions: Muslim World League, Egyptian General Authority, Umm
al-Qura (Makkah), University of Islamic Sciences Karachi, ISNA (North America),
Kuwait, Qatar, Dubai, Singapore, Turkey (Diyanet) and the Gulf region. Asr can
follow the majority (shadow = 1) or the Hanafi school (shadow = 2). High
latitudes are handled with the angle-based, middle-of-night or one-seventh
rules.

Local mosques sometimes add a minute or two of caution (تمكين) to these
values; the screen lets the learner set a per-prayer adjustment.
Pure standard library.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

KAABA = (21.422487, 39.826206)

PRAYER_KEYS = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")
PRAYER_NAMES = {
    "imsak": "الإمساك", "fajr": "الفجر", "sunrise": "الشروق", "dhuhr": "الظهر",
    "asr": "العصر", "maghrib": "المغرب", "isha": "العشاء", "midnight": "منتصف الليل",
    "last_third": "الثلث الأخير",
}


@dataclass(frozen=True)
class Method:
    key: str
    name: str
    fajr: float                     # degrees below horizon
    isha: float = 0.0               # degrees, or 0 when isha_minutes is used
    isha_minutes: int = 0           # fixed minutes after maghrib
    isha_minutes_ramadan: int = 0
    maghrib_minutes: int = 0


METHODS: Dict[str, Method] = {m.key: m for m in (
    Method("mwl", "رابطة العالم الإسلامي", 18.0, 17.0),
    Method("egypt", "الهيئة المصرية العامة للمساحة", 19.5, 17.5),
    Method("makkah", "تقويم أم القرى (مكّة المكرّمة)", 18.5, 0.0, 90, 120),
    Method("karachi", "جامعة العلوم الإسلامية بكراتشي", 18.0, 18.0),
    Method("isna", "الجمعية الإسلامية لأمريكا الشمالية", 15.0, 15.0),
    Method("kuwait", "الكويت", 18.0, 17.5),
    Method("qatar", "قطر", 18.0, 0.0, 90, 90),
    Method("gulf", "منطقة الخليج", 19.5, 0.0, 90, 90),
    Method("dubai", "دبي", 18.2, 18.2),
    Method("singapore", "سنغافورة", 20.0, 18.0),
    Method("turkey", "رئاسة الشؤون الدينية التركية", 18.0, 17.0),
)}

ASR_SCHOOLS = {"standard": ("الجمهور (ظلّ الشيء مثله)", 1),
               "hanafi": ("الحنفي (ظلّ الشيء مثلاه)", 2)}

HIGH_LAT_RULES = {"angle": "حسب الزاوية", "middle": "منتصف الليل",
                  "seventh": "سُبع الليل", "none": "بلا تعديل"}


@dataclass(frozen=True)
class City:
    key: str
    name: str
    country: str
    lat: float
    lon: float
    tz: str                         # IANA zone
    std_offset: float               # hours, used when the zone database is missing
    method: str
    elevation: float = 0.0


CITIES: Tuple[City, ...] = (
    City("makkah", "مكّة المكرّمة", "السعودية", 21.3891, 39.8579, "Asia/Riyadh", 3, "makkah", 277),
    City("madinah", "المدينة المنوّرة", "السعودية", 24.5247, 39.5692, "Asia/Riyadh", 3, "makkah", 608),
    City("riyadh", "الرياض", "السعودية", 24.7136, 46.6753, "Asia/Riyadh", 3, "makkah", 612),
    City("jeddah", "جدّة", "السعودية", 21.4858, 39.1925, "Asia/Riyadh", 3, "makkah", 12),
    City("kuwait", "الكويت", "الكويت", 29.3759, 47.9774, "Asia/Kuwait", 3, "kuwait"),
    City("doha", "الدوحة", "قطر", 25.2854, 51.5310, "Asia/Qatar", 3, "qatar"),
    City("manama", "المنامة", "البحرين", 26.2285, 50.5860, "Asia/Bahrain", 3, "gulf"),
    City("abudhabi", "أبو ظبي", "الإمارات", 24.4539, 54.3773, "Asia/Dubai", 4, "dubai"),
    City("dubai", "دبي", "الإمارات", 25.2048, 55.2708, "Asia/Dubai", 4, "dubai"),
    City("muscat", "مسقط", "عُمان", 23.5880, 58.3829, "Asia/Muscat", 4, "mwl"),
    City("sanaa", "صنعاء", "اليمن", 15.3694, 44.1910, "Asia/Aden", 3, "mwl", 2250),
    City("aden", "عدن", "اليمن", 12.7855, 45.0187, "Asia/Aden", 3, "mwl"),
    City("baghdad", "بغداد", "العراق", 33.3152, 44.3661, "Asia/Baghdad", 3, "mwl"),
    City("damascus", "دمشق", "سوريا", 33.5138, 36.2765, "Asia/Damascus", 3, "egypt", 680),
    City("aleppo", "حلب", "سوريا", 36.2021, 37.1343, "Asia/Damascus", 3, "egypt", 380),
    City("beirut", "بيروت", "لبنان", 33.8938, 35.5018, "Asia/Beirut", 2, "mwl"),
    City("tripoli_lb", "طرابلس (لبنان)", "لبنان", 34.4367, 35.8497, "Asia/Beirut", 2, "mwl"),
    City("amman", "عمّان", "الأردن", 31.9454, 35.9284, "Asia/Amman", 3, "mwl", 780),
    City("jerusalem", "القدس", "فلسطين", 31.7683, 35.2137, "Asia/Hebron", 2, "mwl", 754),
    City("gaza", "غزّة", "فلسطين", 31.5017, 34.4668, "Asia/Gaza", 2, "mwl"),
    City("cairo", "القاهرة", "مصر", 30.0444, 31.2357, "Africa/Cairo", 2, "egypt"),
    City("alexandria", "الإسكندرية", "مصر", 31.2001, 29.9187, "Africa/Cairo", 2, "egypt"),
    City("khartoum", "الخرطوم", "السودان", 15.5007, 32.5599, "Africa/Khartoum", 2, "egypt"),
    City("tripoli", "طرابلس (ليبيا)", "ليبيا", 32.8872, 13.1913, "Africa/Tripoli", 2, "egypt"),
    City("tunis", "تونس", "تونس", 36.8065, 10.1815, "Africa/Tunis", 1, "mwl"),
    City("algiers", "الجزائر", "الجزائر", 36.7538, 3.0588, "Africa/Algiers", 1, "mwl"),
    City("rabat", "الرباط", "المغرب", 34.0209, -6.8416, "Africa/Casablanca", 1, "mwl"),
    City("casablanca", "الدار البيضاء", "المغرب", 33.5731, -7.5898, "Africa/Casablanca", 1, "mwl"),
    City("nouakchott", "نواكشوط", "موريتانيا", 18.0735, -15.9582, "Africa/Nouakchott", 0, "mwl"),
    City("mogadishu", "مقديشو", "الصومال", 2.0469, 45.3182, "Africa/Mogadishu", 3, "mwl"),
    City("djibouti", "جيبوتي", "جيبوتي", 11.5721, 43.1456, "Africa/Djibouti", 3, "mwl"),
    City("moroni", "موروني", "جزر القمر", -11.7172, 43.2473, "Indian/Comoro", 3, "mwl"),
    City("istanbul", "إسطنبول", "تركيا", 41.0082, 28.9784, "Europe/Istanbul", 3, "turkey"),
    City("london", "لندن", "المملكة المتحدة", 51.5074, -0.1278, "Europe/London", 0, "mwl"),
    City("paris", "باريس", "فرنسا", 48.8566, 2.3522, "Europe/Paris", 1, "mwl"),
    City("berlin", "برلين", "ألمانيا", 52.5200, 13.4050, "Europe/Berlin", 1, "mwl"),
    City("newyork", "نيويورك", "الولايات المتحدة", 40.7128, -74.0060, "America/New_York", -5, "isna"),
    City("toronto", "تورونتو", "كندا", 43.6532, -79.3832, "America/Toronto", -5, "isna"),
    City("kualalumpur", "كوالالمبور", "ماليزيا", 3.1390, 101.6869, "Asia/Kuala_Lumpur", 8, "singapore"),
    City("jakarta", "جاكرتا", "إندونيسيا", -6.2088, 106.8456, "Asia/Jakarta", 7, "singapore"),
    City("karachi", "كراتشي", "باكستان", 24.8607, 67.0011, "Asia/Karachi", 5, "karachi"),
)

CITY_BY_KEY = {c.key: c for c in CITIES}


# ---------------------------------------------------------------------------
# degree trigonometry
# ---------------------------------------------------------------------------

def _dsin(d): return math.sin(math.radians(d))
def _dcos(d): return math.cos(math.radians(d))
def _dtan(d): return math.tan(math.radians(d))
def _darcsin(x): return math.degrees(math.asin(max(-1.0, min(1.0, x))))
def _darccos(x): return math.degrees(math.acos(max(-1.0, min(1.0, x))))
def _darctan2(y, x): return math.degrees(math.atan2(y, x))
def _darccot(x): return math.degrees(math.atan(1.0 / x))


def _fix(a, b):
    a = a - b * math.floor(a / b)
    return a + b if a < 0 else a


def _fix_angle(a): return _fix(a, 360.0)
def _fix_hour(a): return _fix(a, 24.0)


def julian_day(year: int, month: int, day: int) -> float:
    if month <= 2:
        year -= 1
        month += 12
    a = math.floor(year / 100)
    b = 2 - a + math.floor(a / 4)
    return (math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1))
            + day + b - 1524.5)


def sun_position(jd: float) -> Tuple[float, float]:
    """(declination in degrees, equation of time in hours)."""
    d = jd - 2451545.0
    g = _fix_angle(357.529 + 0.98560028 * d)
    q = _fix_angle(280.459 + 0.98564736 * d)
    l = _fix_angle(q + 1.915 * _dsin(g) + 0.020 * _dsin(2 * g))
    e = 23.439 - 0.00000036 * d
    ra = _darctan2(_dcos(e) * _dsin(l), _dcos(l)) / 15.0
    eqt = q / 15.0 - _fix_hour(ra)
    decl = _darcsin(_dsin(e) * _dsin(l))
    return decl, eqt


# ---------------------------------------------------------------------------
# the calculator
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    method: str = "mwl"
    asr: str = "standard"
    high_lat: str = "angle"
    adjust: Dict[str, int] = field(default_factory=dict)   # minutes per prayer
    ramadan: bool = False


class PrayerCalculator:
    def __init__(self, lat: float, lon: float, elevation: float = 0.0,
                 settings: Optional[Settings] = None):
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("coordinates out of range")
        self.lat = lat
        self.lon = lon
        self.elevation = max(0.0, elevation)
        self.settings = settings or Settings()
        self._jd = 0.0

    # -- astronomy -------------------------------------------------------
    def _mid_day(self, t):
        _, eqt = sun_position(self._jd + t)
        return _fix_hour(12 - eqt)

    def _sun_angle_time(self, angle, t, ccw=False):
        decl, _ = sun_position(self._jd + t)
        noon = self._mid_day(t)
        cos_h = ((-_dsin(angle) - _dsin(decl) * _dsin(self.lat))
                 / (_dcos(decl) * _dcos(self.lat)))
        if cos_h > 1 or cos_h < -1:
            return float("nan")        # the sun never reaches that angle today
        h = _darccos(cos_h) / 15.0
        return noon + (-h if ccw else h)

    def _asr_time(self, factor, t):
        decl, _ = sun_position(self._jd + t)
        angle = -_darccot(factor + _dtan(abs(self.lat - decl)))
        return self._sun_angle_time(angle, t)

    def _rise_set_angle(self):
        return 0.833 + 0.0347 * math.sqrt(self.elevation)

    # -- main ------------------------------------------------------------
    def compute(self, date: datetime.date, tz_hours: float) -> Dict[str, float]:
        """Times as fractional hours of local clock time (may exceed 24 for
        a time after midnight). Missing values are NaN."""
        m = METHODS.get(self.settings.method, METHODS["mwl"])
        factor = ASR_SCHOOLS.get(self.settings.asr, ASR_SCHOOLS["standard"])[1]
        self._jd = julian_day(date.year, date.month, date.day) - self.lon / (15 * 24.0)

        # initial guesses as day portions, refined once
        guess = {"fajr": 5, "sunrise": 6, "dhuhr": 12, "asr": 13,
                 "sunset": 18, "isha": 18}
        t = dict(guess)
        for rnd in range(2):
            p = {k: v / 24.0 for k, v in t.items()}
            t = {
                "fajr": self._sun_angle_time(m.fajr, p["fajr"], ccw=True),
                "sunrise": self._sun_angle_time(self._rise_set_angle(), p["sunrise"], ccw=True),
                "dhuhr": self._mid_day(p["dhuhr"]),
                "asr": self._asr_time(factor, p["asr"]),
                "sunset": self._sun_angle_time(self._rise_set_angle(), p["sunset"]),
                "isha": (self._sun_angle_time(m.isha, p["isha"]) if m.isha
                         else float("nan")),
            }
            if rnd == 0:
                # a time the sun never reaches keeps its guess for the refinement
                t = {k: (guess[k] if math.isnan(v) else v) for k, v in t.items()}

        # to local clock time
        shift = tz_hours - self.lon / 15.0
        out = {k: (v + shift if not math.isnan(v) else v) for k, v in t.items()}
        out["maghrib"] = out["sunset"] + m.maghrib_minutes / 60.0
        if not m.isha:
            mins = m.isha_minutes_ramadan if (self.settings.ramadan and m.isha_minutes_ramadan) else m.isha_minutes
            out["isha"] = out["maghrib"] + mins / 60.0

        self._adjust_high_latitudes(out, m)

        out["imsak"] = out["fajr"] - 10 / 60.0 if not math.isnan(out["fajr"]) else float("nan")
        # the night runs from sunset to the next fajr (sunrise for midnight per
        # the majority convention)
        if not math.isnan(out["sunset"]) and not math.isnan(out["sunrise"]):
            night = _time_diff(out["sunset"], out["sunrise"])
            out["midnight"] = out["sunset"] + night / 2.0
        else:
            out["midnight"] = float("nan")
        if not math.isnan(out["sunset"]) and not math.isnan(out["fajr"]):
            night_f = _time_diff(out["sunset"], out["fajr"])
            out["last_third"] = out["sunset"] + night_f * 2.0 / 3.0
        else:
            out["last_third"] = float("nan")

        for k, v in (self.settings.adjust or {}).items():
            if k in out and not math.isnan(out[k]):
                out[k] += v / 60.0
        del out["sunset"]
        return out

    def _adjust_high_latitudes(self, times, m):
        rule = self.settings.high_lat
        if rule == "none" or math.isnan(times["sunrise"]) or math.isnan(times["sunset"]):
            return
        night = _time_diff(times["sunset"], times["sunrise"])

        def portion(angle):
            if rule == "middle":
                return night / 2.0
            if rule == "seventh":
                return night / 7.0
            return night * angle / 60.0

        fajr_limit = times["sunrise"] - portion(m.fajr)
        if math.isnan(times["fajr"]) or _time_diff(times["fajr"], times["sunrise"]) > portion(m.fajr):
            times["fajr"] = fajr_limit
        if m.isha:
            isha_limit = times["sunset"] + portion(m.isha)
            if math.isnan(times["isha"]) or _time_diff(times["sunset"], times["isha"]) > portion(m.isha):
                times["isha"] = isha_limit


def _time_diff(a, b):
    return _fix_hour(b - a)


# ---------------------------------------------------------------------------
# time zones
# ---------------------------------------------------------------------------

def utc_offset_hours(tz_name: str, date: datetime.date, fallback: float) -> float:
    """The zone's offset on that date (DST-aware) when the zone database is
    available, otherwise the city's standard offset."""
    try:
        from zoneinfo import ZoneInfo
        noon = datetime.datetime(date.year, date.month, date.day, 12, 0,
                                 tzinfo=ZoneInfo(tz_name))
        off = noon.utcoffset()
        if off is not None:
            return off.total_seconds() / 3600.0
    except Exception:
        pass
    return float(fallback)


def local_offset_hours(date: Optional[datetime.date] = None) -> float:
    """This computer's offset from UTC on that date."""
    date = date or datetime.date.today()
    stamp = datetime.datetime(date.year, date.month, date.day, 12, 0).astimezone()
    off = stamp.utcoffset()
    return off.total_seconds() / 3600.0 if off else 0.0


# ---------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------

def format_time(hours: float, twelve_hour: bool = True) -> str:
    if hours is None or math.isnan(hours):
        return "غير متاح"
    total = int(round(_fix_hour(hours) * 60)) % (24 * 60)
    h, mnt = divmod(total, 60)
    if not twelve_hour:
        return f"{h:02d}:{mnt:02d}"
    suffix = "صباحًا" if h < 12 else "مساءً"
    h12 = h % 12 or 12
    return f"{h12}:{mnt:02d} {suffix}"


def day_table(lat, lon, date, tz_hours, settings=None, elevation=0.0,
              include_extra=True, twelve_hour=True) -> List[Tuple[str, str, float]]:
    """[(key, spoken line, hours)] in the day's order."""
    calc = PrayerCalculator(lat, lon, elevation, settings)
    t = calc.compute(date, tz_hours)
    keys = (["imsak"] if include_extra else []) + list(PRAYER_KEYS)
    if include_extra:
        keys += ["midnight", "last_third"]
    return [(k, f"{PRAYER_NAMES[k]}: {format_time(t[k], twelve_hour)}", t[k]) for k in keys]


def next_prayer(lat, lon, now: datetime.datetime, tz_hours, settings=None,
                elevation=0.0) -> Tuple[str, float, int]:
    """(key, clock hours, minutes from now) of the next of the five prayers."""
    calc = PrayerCalculator(lat, lon, elevation, settings)
    cur = now.hour + now.minute / 60.0 + now.second / 3600.0
    today = calc.compute(now.date(), tz_hours)
    for k in ("fajr", "dhuhr", "asr", "maghrib", "isha"):
        v = today[k]
        if not math.isnan(v) and v > cur:
            return k, v, int(round((v - cur) * 60))
    tomorrow = calc.compute(now.date() + datetime.timedelta(days=1), tz_hours)
    v = tomorrow["fajr"]
    return "fajr", v, int(round((24 - cur + v) * 60))


# ---------------------------------------------------------------------------
# Qibla
# ---------------------------------------------------------------------------

def qibla_bearing(lat: float, lon: float) -> float:
    """Initial great-circle bearing from the location to the Kaaba, in degrees
    clockwise from true north."""
    phi1, phi2 = math.radians(lat), math.radians(KAABA[0])
    dl = math.radians(KAABA[1] - lon)
    y = math.sin(dl) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def distance_to_makkah_km(lat: float, lon: float) -> float:
    r = 6371.0088
    phi1, phi2 = math.radians(lat), math.radians(KAABA[0])
    dphi = phi2 - phi1
    dl = math.radians(KAABA[1] - lon)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


_COMPASS = ["الشمال", "الشمال الشرقي", "الشرق", "الجنوب الشرقي",
            "الجنوب", "الجنوب الغربي", "الغرب", "الشمال الغربي"]


def compass_word(bearing: float) -> str:
    return _COMPASS[int(((bearing % 360) + 22.5) // 45) % 8]


def clock_direction(bearing: float) -> int:
    """The bearing as a clock hour (12 = north, 3 = east), which many blind
    learners find easier to turn to than degrees."""
    h = int(round((bearing % 360) / 30.0)) % 12
    return 12 if h == 0 else h


def qibla_description(lat: float, lon: float) -> str:
    b = qibla_bearing(lat, lon)
    d = distance_to_makkah_km(lat, lon)
    if d < 0.5:
        return "أنت عند الكعبة المشرّفة."
    return (f"اتجاه القبلة {round(b)} درجة من الشمال الحقيقي باتجاه عقارب الساعة، "
            f"أي نحو {compass_word(b)}، وهو اتجاه الساعة {clock_direction(b)} "
            f"إذا كانت الساعة ١٢ أمامك نحو الشمال. "
            f"المسافة إلى مكّة المكرّمة نحو {round(d):,} كيلومتر.")
