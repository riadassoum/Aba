# -*- coding: utf-8 -*-
"""
Bundle the hadith collections of the fawazahmed0 hadith-api (Unlicense,
https://github.com/fawazahmed0/hadith-api) into abaAcademy/resources/hadith
in the reader's shape: {"id", "name", "books": [{"no", "title", "hadiths": [{"n", "text"}]}]}.
The same conversion the reader applies when it downloads a collection.

Usage: python3 build_hadith.py RAW_DIR RESOURCES_HADITH_DIR
RAW_DIR holds ara-<id>.json files as downloaded from the dataset.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hadith_titles import TITLES  # noqa: E402


def main(raw_dir, out_dir):
    index_path = os.path.join(out_dir, "index.json")
    index = json.load(open(index_path, encoding="utf-8"))
    for entry in index:
        src = os.path.join(raw_dir, f"ara-{entry['id']}.json")
        if not os.path.exists(src):
            continue
        d = json.load(open(src, encoding="utf-8"))
        sections = d.get("metadata", {}).get("sections", {})
        books = {}
        for h in d.get("hadiths", []):
            text = (h.get("text") or "").replace("«", "").replace("»", "").strip()
            if not text:
                continue
            bno = h.get("reference", {}).get("book", 0)
            books.setdefault(bno, []).append({"n": h.get("hadithnumber"), "text": text})
        ar = TITLES.get(entry["id"], {})
        booklist = []
        for b in sorted(books):
            # book 0 holds the hadiths the dataset did not assign to a book
            title = ar.get(b) or ("أحاديث متفرّقة" if b == 0 else sections.get(str(b), "") or f"كتاب {b}")
            booklist.append({"no": b, "title": title, "hadiths": books[b]})
        payload = {"id": entry["id"], "name": entry["name"], "books": booklist}
        with open(os.path.join(out_dir, f"{entry['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        entry["bundled"] = True
        entry["hadiths"] = sum(len(b["hadiths"]) for b in booklist)
        entry["books"] = len(booklist)
        print(entry["id"], entry["books"], entry["hadiths"], sum(1 for b in books if b in ar), "Arabic titles")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
