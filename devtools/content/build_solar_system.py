# -*- coding: utf-8 -*-
"""
Build abaAcademy/resources/science/solar_system.json from Wikidata (CC0):
the Sun, the eight planets, the Moon, Pluto and Ceres, with their Arabic
names, mass, mean radius, surface gravity, orbital period and mean distance
from the Sun (semi-major axis). Wikidata holds several values for some of
these (equatorial and polar radius, different estimates); the median of the
non-deprecated values in SI units is kept, so no single odd figure decides.

Usage: python3 build_solar_system.py RESULTS_DIR OUT_JSON
RESULTS_DIR holds P2067.json (mass), P2120 (radius), P7015 (gravity),
P2146 (orbital period) and P2233 (semi-major axis): SPARQL results with
?b ?bLabel ?amount over normalised (psn:) values.
"""

import json
import os
import statistics
import sys

ORDER = ["Q525", "Q308", "Q313", "Q2", "Q405", "Q111", "Q596", "Q319", "Q193", "Q324", "Q332", "Q339"]
KIND = {"Q525": "نجم", "Q405": "قمر الأرض", "Q596": "كوكب قزم", "Q339": "كوكب قزم"}
FIELDS = {"P2067": "mass_kg", "P2120": "radius_m", "P7015": "gravity", "P2146": "period_s", "P2233": "distance_m"}


def main(src, out):
    bodies = {q: {"id": q, "kind": KIND.get(q, "كوكب")} for q in ORDER}
    for prop, field in FIELDS.items():
        vals = {}
        for r in json.load(open(os.path.join(src, f"{prop}.json"), encoding="utf-8"))["results"]["bindings"]:
            q = r["b"]["value"].rsplit("/", 1)[1]
            bodies[q]["name"] = r["bLabel"]["value"]
            vals.setdefault(q, []).append(float(r["amount"]["value"]))
        for q, v in vals.items():
            bodies[q][field] = statistics.median(v)
    rows = [bodies[q] for q in ORDER if "name" in bodies[q]]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"source": "Wikidata (CC0)", "bodies": rows}, f, ensure_ascii=False, indent=1)
    print(len(rows), "bodies")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
