# ABA Academy — Developer Documentation

ABA Academy (أكاديمية الكفيف العربي) is a modular educational platform that runs as an NVDA add-on. It is built so that **content is data, the engine is code, and the two never mix**: you can add whole courses, levels, and thousands of questions without touching Python, and you can add new interaction types or generators without touching content.

This document describes the architecture and the extension points.

## 1. Layout

```
addon/
  manifest.ini
  doc/
  globalPlugins/
    abaAcademy/                # this package *is* the NVDA global plugin
      __init__.py              # GlobalPlugin shim (Tools-menu item)
      app.py                   # GUI lifecycle entry (open_academy)
      bootstrap.py             # wires Academy + SpeechManager, resolves paths
      academy.py               # application service tying subsystems together
      engine/
        models.py              # dataclasses/enums (Block, Question, Lesson…)
        grading.py             # normalization + grading, all question types
        schema.py              # JSON contract + validator
        loader.py              # course discovery + lazy, isolated lesson loading
        session.py             # QuestionSession: stats, skip, adaptive, endless
      generators/
        __init__.py            # registry (id -> factory), Deduper, seeding
        generic.py             # content-neutral (frame, truefalse)
        arabic.py              # procedural (sun_moon, plural, conjugate, hamza)
        vocabulary.py          # word-DB driven (meaning, synonym, spelling…)
      database/
        schema.py              # SQLite DDL (single source of truth)
        store.py               # data-access layer (sessions, mistakes, mastery…)
        srs.py                 # spaced-repetition scheduler (SM-2 variant)
      gui/
        accessible.py          # AccessibleDialog base (announce-on-show + keys)
        exercise_runner.py     # accessible one-question-at-a-time runner
        lesson_player.py       # teacher-like block playback
        main_window.py         # courses/levels/lessons navigation + multi-select
        statistics_view.py     # stats report
        keyboard_trainer.py    # typing speed/accuracy challenges
        hub.py                 # top-level hub
      settings/settings.py     # typed settings facade over the DB
      audio/speech.py          # SpeechManager (cancel-before-speak, braille)
      teacher/editor.py        # authoring API + pack validation
      courses/                 # bundled course packs (pure JSON data)
        arabic/ …
        computer/ …
      tests/test_engine.py     # engine unit tests (no NVDA/wx needed)
tools/
  build_arabic_pack.py         # offline authoring scripts (not shipped)
  build_computer_pack.py
```

## 2. Data model (engine/models.py)

Everything flows in a few dataclasses. `Course → Level → LessonMeta` is the catalogue; `Lesson` holds ordered `Block`s in four phases (theory/practice/ review/quiz); a `Block` may carry `Question`s. `Question` is the single currency the exercise runner consumes, whether it came from static JSON or a generator.

`BlockType` and `QuestionType` are the two switch points. Adding an interaction type = add an enum member + a renderer in the GUI (+ optional loader support). No content changes.

## 3. Course pack format

A pack is a folder under `courses/` (bundled) or under the user data dir (installed later). See `engine/schema.py` for the full contract. Minimal shape:

```
courses/<course_id>/
  course.json               # {course_id, title, levels:[{level_id,title,lessons:[…]}]}
  data/*.json               # optional generator data tables / word banks
  levels/<level_id>/<lesson_id>/
    lesson.json             # metadata (objectives, grammar_refs, order)
    theory.json practice.json review.json quiz.json    # {"blocks":[…]}
    media/                  # optional
```

A block is `{"btype": "...", ...}`. Examples:

```json
{"btype": "text", "text": "شرح المفهوم"}
{"btype": "example", "text": "الشمس", "note": "لام شمسية"}
{"btype": "question", "question": {"qtype": "mcq", "prompt": "…",
    "options": ["أ","ب"], "correct": 1, "explanation": "…", "topic": "ar.x"}}
{"btype": "generated", "generator": "ar.sun_moon", "data": "definite_words", "count": 8}
```

The engine auto-discovers any pack folder — dropping a new pack in `courses/` (or the user's `abaAcademy/courses/`) makes it appear with no code change.

### IMPORTANT: all file and folder names must be ASCII

`course_id`, `level_id`, `lesson_id`, and every file/folder name inside a pack **must use only ASCII characters** (a–z, 0–9, `_`, `-`). Do **not** use Arabic (or any non-ASCII) text as a file or folder name. NVDA's bundled Python reads add-on files with an encoding that mangles non-ASCII names (the so-called "Askie" problem), so a lesson folder named e.g. `الدرس‑الأول/` will silently fail to load on many users' machines.

Put the Arabic name **inside** the JSON instead, where it belongs:

```
levels/nvda/computer.objnav.0/          ✅ ASCII folder name
    theory.json  →  {"title": "التنقّل بالكائنات", ...}   ✅ Arabic in the JSON
```

```
levels/التنقّل_بالكائنات/               ❌ non-ASCII folder name — will break
```

The build script verifies this: every release checks that the packaged add-on contains **zero** non-ASCII file names. If you add a pack, keep all ids and paths ASCII and this check will pass.

## 4. Generators (procedural question engine)

A generator is a factory registered under a string id:

```python
from abaAcademy.generators import register, signature_qid
@register("mylang.something")
def gen(count, rng, **params):
    ...  # return List[Question]
```

`params` come from the JSON block's `params`, optionally merged with a named `data` table from the pack's `data/` folder. Use the `Deduper` to avoid immediate repeats, and set `q.qid = signature_qid(id, signature)` so spaced repetition tracks the *concept* across wording changes. Generators are the mechanism behind "one generator → thousands of questions".

## 5. Sessions & adaptivity (engine/session.py, academy.py)

`Academy` assembles sessions: `build_lesson_quiz`, `build_mixed_session` (round-robin balance across several selected lessons), `build_endless_practice` (refills forever), and `build_review_session` (pulls SRS-due concepts and regenerates fresh questions for them). `QuestionSession` grades, records stats, logs attempts, updates SRS, and — on a wrong answer — injects extra practice for the missed topic (adaptive).

Lesson isolation: every session is built from freshly `load_lesson`-ed objects; there is no shared global question pool, so opening one lesson cannot leak into another.

## 6. Persistence (database/)

One SQLite file under the NVDA user config dir (survives add-on updates). The `Store` class is the only place that runs SQL. `srs.py` implements an SM-2 variant keyed by `qid`. Statistics (accuracy, weak/strong topics, streak, daily activity) are all queries on this DB.

## 7. Accessibility framework (gui/accessible.py, audio/speech.py)

`AccessibleDialog` enforces, on show: focus the dialog, speak title + instructions + first control in one **cancel-before-speak** announcement, and install the global shortcut table (Enter/Backspace/Ctrl+R/Ctrl+H/Ctrl+P/Ctrl+S/ Ctrl+M/Escape/F1). Screens carry the question prompt on the *focused control's accessible name* so moving focus reads the whole prompt, and put post-answer feedback on the Next button's name so focusing it announces the result. Controls are created through helpers that always assign a name — so "no unlabeled controls" holds structurally. `SpeechManager` centralizes speech + braille and degrades to an in-memory log outside NVDA (for tests).

## 8. Authoring (teacher/editor.py)

`LessonBuilder` and `CoursePackEditor` build the exact on-disk layout the engine loads, validating via `engine.schema` before writing. `validate_pack(path)` checks a whole pack and returns Arabic problem strings. This is the basis for a future in-app teacher-mode UI; today it's a clean programmatic API and powers the `tools/build_*_pack.py` authoring scripts.

## 9. Testing

`tests/test_engine.py` runs without NVDA or wx (the engine/GUI split makes this possible). It covers grading, generators (determinism + computed answers), session flow (stats/skip/adaptive/endless), SRS progression, and teacher validation. Run: `python tests/test_engine.py`.

## 10. Extending

* **New course**: author JSON under `courses/…` (or script it like `tools/build_arabic_pack.py`). No code.
* **New generator**: one file in `generators/` calling `register()`; reference it from JSON. No engine/GUI change.
* **New interaction type**: add a `BlockType`/`QuestionType` member, a grader branch, and a renderer in `exercise_runner`/`lesson_player`.
* **Future (cloud sync, marketplace, AI tutor, speech recognition, human audio, competitions, teacher dashboards)**: these attach at the `Academy` service boundary or as new packs; the engine core does not need rewriting.
