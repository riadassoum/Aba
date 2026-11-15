"""Convert KTouch courses and keyboard layouts (KDE, GPL-2.0-or-later) into
the academy's typing-course data (resources/typing/<id>.json).

    python build_typing.py KTOUCH_DIR path/to/abaAcademy

KTOUCH_DIR holds courses as <name>.xml and layouts as layout_<name>.xml.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

COURSES = [
    # (course file, layout file, academy id, Arabic title)
    ("ara", "ara", "ar", "العربية"),
    ("us", "us", "en_us", "الإنجليزية (لوحة أمريكية)"),
    ("gb", "gb", "en_gb", "الإنجليزية (لوحة بريطانية)"),
    ("fr", "fr", "fr", "الفرنسية (لوحة AZERTY)"),
    ("es1", "es", "es", "الإسبانية"),
    ("de1", "de", "de", "الألمانية (لوحة QWERTZ)"),
    ("it", "it", "it", "الإيطالية"),
    ("tr", "tr", "tr", "التركية (لوحة Q)"),
]


def layout_keys(path):
    root = ET.parse(path).getroot()
    keys = root.find("keys")
    rows = sorted({int(k.get("top")) for k in keys.iter("key")})
    out = {}
    for k in keys.iter("key"):
        finger = k.get("fingerIndex")
        if finger is None:
            continue
        row = rows.index(int(k.get("top")))
        left = int(k.get("left"))
        haptic = k.get("hasHapticMarker") == "true"
        for ch in k.iter("char"):
            text = ch.text or ""
            if len(text) != 1:
                continue
            shift = ch.get("modifier") or ""
            rec = {"finger": int(finger), "row": row, "left": left, "haptic": haptic,
                   "shift": shift.replace("_shift", "") if shift else ""}
            if text not in out or (out[text]["shift"] and not rec["shift"]):
                out[text] = rec
    # the two keys with a touch marker anchor the home row
    anchors = sorted((v["left"], c) for c, v in out.items() if v["haptic"] and not v["shift"])
    space = None
    for k in keys.iter("specialKey"):
        if k.get("type") == "space":
            space = True
    return out, [c for _, c in anchors], len(rows)


def course(path):
    root = ET.parse(path).getroot()
    lessons = []
    for i, les in enumerate(root.find("lessons").iter("lesson")):
        text = (les.findtext("text") or "").strip("\n")
        lines = [re.sub(r"\s+", " ", l).strip() for l in text.split("\n")]
        lines = [l for l in lines if l]
        new = (les.findtext("newCharacters") or "").strip()
        title = (les.findtext("title") or "").strip()
        if not title or re.fullmatch(r"(?i)(lesson|leçon|lektion|lección|lezione|ders)\s*\d+", title):
            title = f"الدرس {i + 1}"
        lessons.append({"title": title, "new": new, "lines": lines})
    credit = "\n".join(l for l in (root.findtext("description") or "").strip().split("\n")
                        if "@" not in l and not re.search(r"(?i)e-?mail|بريد", l))
    return {"credit": credit.strip(), "lessons": lessons}


def main(src, academy):
    dst = os.path.join(academy, "resources", "typing")
    os.makedirs(dst, exist_ok=True)
    index = []
    for cfile, lfile, cid, title in COURSES:
        cpath = os.path.join(src, f"{cfile}.xml")
        lpath = os.path.join(src, f"layout_{lfile}.xml")
        if not (os.path.isfile(cpath) and os.path.isfile(lpath)):
            print("missing", cid)
            continue
        keys, anchors, nrows = layout_keys(lpath)
        data = course(cpath)
        data.update({"id": cid, "title": title, "layout": lfile, "keys": keys, "anchors": anchors, "rows": nrows,
                     "source": f"KTouch (KDE), courses/{cfile}.xml and keyboardlayouts/{lfile}.xml, GPL-2.0-or-later"})
        with open(os.path.join(dst, f"{cid}.json"), "w", encoding="utf-8") as f:
            # no guillemets: some voices read them out by name
            text = json.dumps(data, ensure_ascii=False, indent=1).replace("«", "").replace("»", "")
            text = text.replace("تمول الجيش الإسرائيلي وتدعم", "تمول جيش الاحتلال وتدعم").replace(" Israele Italia", " Italia")
            f.write(text)
        index.append({"id": cid, "title": title, "lessons": len(data["lessons"])})
        print(cid, len(data["lessons"]), "lessons", len(keys), "keys", "anchors", anchors)
    with open(os.path.join(dst, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
