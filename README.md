# Arab Blind Academy — أكاديمية الكفيف العربي

An NVDA add-on: a complete learning academy inside the screen reader, for
Arabic-speaking blind students. The interface is always in Arabic (RTL),
keyboard-only, and screen-reader-first.

> The user interface and all lessons are in Arabic, because the add-on is built
> for Arabic-speaking blind learners. This English README is a courtesy summary.

## What it includes

- **Courses** — Arabic (grammar and spelling up to the Ājurrūmiyya level),
  English, French, Braille, computer skills (NVDA, Windows, Office), maths,
  science, history, geography, and general knowledge. 700+ lessons on a real
  progressive path, with a modular JSON lesson engine, an unlimited procedural
  question generator, spaced repetition, statistics, and typing challenges.
- **The Qur'an Mushaf** — one ayah per line, per-ayah recitation, multiple
  scripts, dozens of tafsirs and 124 translations, i'rab, reasons for
  revelation, **word-by-word morphology** (root, lemma, part of speech),
  bookmarks, search, a **multi-surah memorisation (hifz)** mode with three
  repeat styles, and a precise surah+ayah go-to.
- **Full-surah player** — whole-surah recitations (separate from the ayah
  player), 22 well-known reciters, with offline download.
- **Hadith** — eight collections, browsed book-by-book, downloaded on demand.
- **Flashcards** — an Anki-style spaced-repetition system (FSRS), with 82
  ready-made starter decks built from the lessons.
- **Islamic tools** — the 99 Names of Allah with Arabic meanings, prayer times
  and the Hijri date, an adhkar list, and a persistent tasbih counter.
- **English dictionary** — definitions, pronunciation, and one-tap flashcards.
- **Accessible downloads** — a download window with on-demand status keys
  (Space / 1 / 2 / 3) and automatic skipping of already-downloaded content.

No external Python libraries need to be installed: the database is bundled
(SQLite when available, otherwise a pure-Python fallback), and audio plays
fully in-process.

## Requirements

- NVDA 2019.3 or newer, on Windows.

## Building the add-on

The add-on is a standard NVDA add-on package (a zip renamed to
`.nvda-addon`). To build it from this repository:

```
python build.py
```

This produces `abaAcademy.nvda-addon`, which the user installs from NVDA
(Tools → Manage add-ons → Install). The script verifies that every packaged
file name is ASCII (see the "Askie" note in `doc/DEVELOPER.md`), that all
bundled JSON is valid, and that the test suite passes before packaging.

## Layout

```
manifest.ini                  add-on manifest (name, version, NVDA compat)
globalPlugins/abaAcademy/      the add-on itself
  academy.py bootstrap.py …    orchestrator and engine
  engine/ generators/ database/  lesson engine, question generators, storage
  gui/                         all screens (academy, Mushaf, hadith, tools…)
  courses/                     the course packs (JSON) — 11 courses
  resources/                   bundled data (Qur'an, reciters, flashcards…)
  lib/                         bundled audio player (miniaudio + cffi)
  COPYING.txt CREDITS.txt      third-party licences, attributions, contributors
doc/                           readmes (ar/en) and the developer guide
LICENSE                        GPL-3.0
```

## Contributing courses

New course packs are just folders of JSON under `courses/`. See
[`doc/DEVELOPER.md`](doc/DEVELOPER.md) for the lesson format — **and note the
requirement that all file and folder names be ASCII** (Arabic names go inside
the JSON, never as file names).

## Licence

GPL-3.0. See [`LICENSE`](LICENSE). Third-party data and adapted components,
including work from the al-bayan project, NVDA Coach, the Quranic Arabic Corpus,
and the AlAdhan and dictionary APIs, are credited in
[`globalPlugins/abaAcademy/COPYING.txt`](globalPlugins/abaAcademy/COPYING.txt)
and [`CREDITS.txt`](globalPlugins/abaAcademy/CREDITS.txt).

## Credits

Created by Riad. With thanks to **Muhammad Hajjar**, who fixed the SQLite
problem that prevented the add-on from running when the user has no separate
Python installation, improved several courses, and fixed the non-ASCII
("Askie") lesson-file-name problem — work that was essential to making the
add-on run reliably.
