# -*- coding: utf-8 -*-
"""
Build abaAcademy/resources/geo/countries.json: the member states of the
United Nations and the two observer states, with Arabic names, capitals,
currencies, region, area, population, neighbours and calling code.

Sources:
* mledoze/countries (ODbL-1.0): names (with the Arabic translation),
  region, area, borders, currency codes, calling codes, landlocked.
* Wikidata (CC0): Arabic labels of capitals and currencies, and population.

Where a capital is disputed internationally the entry says so instead of
naming one.

Usage: python3 build_countries.py SRC_DIR OUT_JSON
SRC_DIR holds countries.json (mledoze) and wd.json (the Wikidata query result).
"""

from __future__ import annotations

import json
import os
import sys

REGIONS = {"Africa": "أفريقيا", "Americas": "الأمريكتان", "Asia": "آسيا", "Europe": "أوروبا",
           "Oceania": "أوقيانوسيا", "Antarctic": "القارة القطبية الجنوبية"}
SUBREGIONS = {
    "Northern Africa": "شمال أفريقيا", "Western Africa": "غرب أفريقيا", "Eastern Africa": "شرق أفريقيا",
    "Middle Africa": "وسط أفريقيا", "Southern Africa": "جنوب أفريقيا", "Western Asia": "غرب آسيا",
    "Central Asia": "آسيا الوسطى", "Southern Asia": "جنوب آسيا", "Eastern Asia": "شرق آسيا",
    "South-Eastern Asia": "جنوب شرق آسيا", "Northern Europe": "شمال أوروبا", "Western Europe": "غرب أوروبا",
    "Eastern Europe": "شرق أوروبا", "Southern Europe": "جنوب أوروبا", "Central Europe": "وسط أوروبا",
    "Southeast Europe": "جنوب شرق أوروبا", "North America": "أمريكا الشمالية", "South America": "أمريكا الجنوبية",
    "Central America": "أمريكا الوسطى", "Caribbean": "الكاريبي", "Australia and New Zealand": "أستراليا ونيوزيلندا",
    "Melanesia": "ميلانيزيا", "Micronesia": "ميكرونيزيا", "Polynesia": "بولينيزيا",
}
OBSERVERS = {"PSE", "VAT"}
DISPUTED_CAPITAL = {"ISR", "PSE"}
# Wikidata also lists Aden, the temporary seat of government since 2015; the
# constitutional capital is Sanaa
CAPITAL_OVERRIDE = {"YEM": "صنعاء"}


def main(src, out):
    mledoze = json.load(open(os.path.join(src, "countries.json"), encoding="utf-8"))
    wd = json.load(open(os.path.join(src, "wd.json"), encoding="utf-8"))["results"]["bindings"]
    by_iso = {}
    for r in wd:
        v = {k: x["value"] for k, x in r.items()}
        e = by_iso.setdefault(v["iso"], {"capitals": [], "currencies": {}, "pop": 0, "label": v.get("countryLabel")})
        cap = v.get("capitalLabel")
        if cap and not cap.startswith("Q") and cap not in e["capitals"]:
            e["capitals"].append(cap)
        if v.get("ccode") and v.get("currencyLabel") and not v["currencyLabel"].startswith("Q"):
            e["currencies"][v["ccode"]] = v["currencyLabel"]
        if v.get("pop"):
            try:
                e["pop"] = max(e["pop"], int(float(v["pop"])))
            except ValueError:
                pass
    keep = [c for c in mledoze if c.get("unMember") or c["cca3"] in OBSERVERS]
    names = {c["cca3"]: c["translations"].get("ara", {}).get("common") or by_iso.get(c["cca3"], {}).get("label")
             for c in keep}
    rows = []
    for c in keep:
        iso = c["cca3"]
        w = by_iso.get(iso, {"capitals": [], "currencies": {}, "pop": 0})
        name = names[iso]
        if not name:
            continue
        cur = []
        for code in c.get("currencies", {}):
            if code in w["currencies"]:
                cur.append(w["currencies"][code])
        idd = c.get("idd", {})
        calling = idd.get("root", "") + (idd["suffixes"][0] if len(idd.get("suffixes", [])) == 1 else "")
        rows.append({
            "iso": iso,
            "name": name,
            "official": c["translations"].get("ara", {}).get("official", name),
            "capital": None if iso in DISPUTED_CAPITAL else CAPITAL_OVERRIDE.get(iso) or ("، ".join(w["capitals"][:2]) or None),
            "capital_note": "عاصمتها موضع نزاع دولي." if iso in DISPUTED_CAPITAL else "",
            "currency": "، ".join(cur),
            "region": REGIONS.get(c.get("region", ""), ""),
            "subregion": SUBREGIONS.get(c.get("subregion", ""), ""),
            "area": c.get("area"),
            "population": w["pop"] or None,
            "borders": [names[b] for b in c.get("borders", []) if b in names and names[b]],
            "landlocked": bool(c.get("landlocked")),
            "calling": calling if len(calling) > 1 else "",
            "un_member": bool(c.get("unMember")),
        })
    # a land border is shared, so keep only borders both sides list (the
    # source has a few one-sided ones, such as Sri Lanka and India)
    nb = {r["name"]: set(r["borders"]) for r in rows}
    for r in rows:
        r["borders"] = [b for b in r["borders"] if r["name"] in nb.get(b, ())]
    rows.sort(key=lambda r: r["name"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"source": "mledoze/countries (ODbL-1.0) and Wikidata (CC0)", "countries": rows}, f,
                  ensure_ascii=False, indent=0)
    print(len(rows), "countries;", sum(1 for r in rows if r["capital"]), "with capital;",
          sum(1 for r in rows if r["currency"]), "with currency;", sum(1 for r in rows if r["population"]), "with population")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
