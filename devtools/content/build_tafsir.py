# -*- coding: utf-8 -*-
"""
Bundle tafsirs from spa5k/tafsir_api (MIT, https://github.com/spa5k/tafsir_api)
as abaAcademy/resources/quran/ed_<id>.json: one string per ayah, 6236 in
mushaf order, the shape the academy's Qur'an editions use. Where the tafsir
explains several ayat together (the source repeats that text on each of
them), the following ayat point back to the first.

Usage: python3 build_tafsir.py RAW_DIR QURAN_RESOURCE_DIR
"""

import json
import os
import sys

TAFSIRS = [
    ("ar-tafsir-as-saadi", "ar.saadi", "Tafsir As-Saadi", "تفسير السعدي (تيسير الكريم الرحمن)"),
    ("ar-tafsir-ibn-kathir", "ar.ibnkathir", "Tafsir Ibn Kathir", "تفسير ابن كثير"),
    ("ar-tafsir-al-mukhtasar", "ar.mukhtasar", "Al-Mukhtasar fi Tafsir al-Quran", "المختصر في التفسير"),
    ("ar-tafsir-al-jalalayn", "ar.jalalayn", None, None),
    ("ar-tafsir-al-baghawi", "ar.baghawi", None, None),
    ("ar-tafsir-al-wasit", "ar.waseet", None, None),
]


def main(raw, qdir):
    q = json.load(open(os.path.join(qdir, "quran_data.json"), encoding="utf-8"))
    counts = {int(s["number"]) if "number" in s else i + 1: int(s["count"]) for i, s in enumerate(q["surahs"])}
    eds = json.load(open(os.path.join(qdir, "editions.json"), encoding="utf-8"))
    for slug, eid, name, arname in TAFSIRS:
        out = []
        filled = 0
        for s in range(1, 115):
            rows = json.load(open(os.path.join(raw, slug, f"{s}.json"), encoding="utf-8"))
            by = {}
            for r in rows:
                t = (r.get("text") or "").replace("«", "").replace("»", "").strip()
                if t:
                    by[int(r["ayah"])] = by.get(int(r["ayah"]), "") + ("\n" if int(r["ayah"]) in by else "") + t
            last = None
            for a in range(1, counts[s] + 1):
                if a in by and last is not None and by[a] == by.get(last):
                    out.append(f"فُسّرت هذه الآية مع الآية {last}.")
                elif a in by:
                    out.append(by[a])
                    last = a
                    filled += 1
                elif last is not None:
                    out.append(f"فُسّرت هذه الآية مع الآية {last}.")
                else:
                    out.append("")
        assert len(out) == 6236, (slug, len(out))
        with open(os.path.join(qdir, f"ed_{eid}.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        if name and not any(e["id"] == eid for e in eds):
            eds.append({"id": eid, "type": "tafsir", "lang": "ar", "name": name, "arname": arname, "dir": "rtl",
                        "bundled": True})
        print(eid, filled, "ayat with their own text")
    with open(os.path.join(qdir, "editions.json"), "w", encoding="utf-8") as f:
        json.dump(eds, f, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
