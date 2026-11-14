# مولّد الدورات والتحدّيات

هذه السكربتات تبني دورات اللغات المتدرّجة وتحدّيات البرمجة من مصادرها. لا تُشحن مع البرنامج.

## دورات اللغات

1. نزّل من تاتويبا (downloads.tatoeba.org/exports/per_language) ملفّات الجمل لكل لغة وملفّات الروابط ara-xxx وeng-xxx إلى `WORK/tatoeba`.
2. `python pairs.py WORK/tatoeba` ثم `python freq.py WORK/tatoeba`.
3. من kaikki.org: مرّر ملفّ ويكاموس الإنجليزي إلى `wikt.py WORK/wikt/senses.jsonl`، وملفّ كل لغة إلى `langdict.py CODE WORK/tatoeba/freq_CODE.json WORK/wikt/dict_CODE.jsonl`، واستخرج صيغ الإنجليزية إلى `WORK/wikt/en_formof.json`.
4. `python lexicon.py WORK en es tr de it fr`
5. `python build_courses.py WORK path/to/abaAcademy/courses en es tr de it fr`

`overrides.py` معاني الكلمات الأكثر شيوعًا مراجعة يدويًّا. `grammar_notes.py` شروح القواعد.

## تحدّيات البرمجة

ضع ملفّات canonical-data.json من exercism/problem-specifications في `WORK/exercism` ثم:

    python build_challenges.py path/to/abaAcademy/resources/codelab/challenges_exercism.json WORK
    python build_original.py . path/to/abaAcademy/resources/codelab/challenges_original.json

كل حالة اختبار تُتحقّق بتشغيل الحلّ المرجعي عليها قبل اعتمادها.
