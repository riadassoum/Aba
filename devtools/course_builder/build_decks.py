"""Starter flashcard decks: one deck per stage of each graded language course,
built from the lessons' dictionary-form words. Run after build_courses.py:

    python build_decks.py path/to/abaAcademy
"""
import glob
import json
import os
import sys

NAMES = {"english_graded": "الإنجليزية بالجمل", "spanish": "الإسبانية", "turkish": "التركية",
         "german": "الألمانية", "italian": "الإيطالية", "french_graded": "الفرنسية بالجمل"}
_QUOTES = str.maketrans({"«": "", "»": "", "“": "", "”": ""})


def main(academy):
    fd = os.path.join(academy, "resources", "flashcards")
    index_path = os.path.join(fd, "index.json")
    idx = [d for d in json.load(open(index_path, encoding="utf-8")) if not d["id"].startswith("g_")]
    for f in glob.glob(os.path.join(fd, "g_*.json")):
        os.remove(f)
    for cid, name in NAMES.items():
        course_dir = os.path.join(academy, "courses", cid)
        c = json.load(open(os.path.join(course_dir, "course.json"), encoding="utf-8"))
        for lv in c["levels"]:
            if not lv["level_id"].startswith("stage"):
                continue
            cards, seen = [], set()
            for l in lv["lessons"]:
                b = json.load(open(os.path.join(course_dir, "levels", lv["level_id"], l["dir"], "bundle.json"),
                                   encoding="utf-8"))
                for w in b["data"].get("words", []):
                    if w["word"] in seen:
                        continue
                    seen.add(w["word"])
                    hint = f"{w['example']} — {w['translation']}" if w.get("example") else ""
                    cards.append({"front": w["word"], "back": w["meaning"], "hint": hint})
            if cards:
                did = f"g_{cid}_{lv['level_id']}"
                text = json.dumps(cards, ensure_ascii=False, separators=(",", ":")).translate(_QUOTES)
                open(os.path.join(fd, did + ".json"), "w", encoding="utf-8").write(text)
                idx.append({"id": did, "name": f"{name}: {lv['title'].split(':')[0]}", "course": cid,
                            "count": len(cards)})
    json.dump(idx, open(index_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    decks = [d for d in idx if d["id"].startswith("g_")]
    print(len(decks), "decks,", sum(d["count"] for d in decks), "cards")


if __name__ == "__main__":
    main(sys.argv[1])
