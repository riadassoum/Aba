# -*- coding: utf-8 -*-
"""
Add the official languages of each country to abaAcademy/resources/geo/countries.json,
in Arabic: the language codes from mledoze/countries (ODbL-1.0), named with
the Arabic language names of the Unicode CLDR (Unicode licence), through
CLDR's table of language-code aliases. Berber, which CLDR names only by its
standard Moroccan form, is given its common Arabic name. Languages with no
Arabic name in CLDR are left out rather than guessed.

Usage: python3 add_country_languages.py MLEDOZE_JSON CLDR_AR_LANGUAGES_JSON CLDR_ALIASES_JSON COUNTRIES_JSON
"""

import json
import sys

EXTRA = {"ber": "الأمازيغية"}


def main(mledoze, cldr_names, cldr_aliases, target):
    names = json.load(open(cldr_names, encoding="utf-8"))["main"]["ar"]["localeDisplayNames"]["languages"]
    alias = json.load(open(cldr_aliases, encoding="utf-8"))["supplemental"]["metadata"]["alias"]["languageAlias"]
    langs = {c["cca3"]: list(c.get("languages", {})) for c in json.load(open(mledoze, encoding="utf-8"))}
    data = json.load(open(target, encoding="utf-8"))
    named = 0
    for row in data["countries"]:
        out = []
        for code in langs.get(row["iso"], []):
            key = code if code in names else alias.get(code, {}).get("_replacement", "").split("_")[0]
            name = EXTRA.get(code) or names.get(key)
            if name and name not in out:
                out.append(name)
        row["languages"] = out
        named += bool(out)
    data["source"] = data.get("source", "") + "; languages: mledoze/countries and Unicode CLDR"
    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    print(named, "countries with languages")


if __name__ == "__main__":
    main(*sys.argv[1:])
