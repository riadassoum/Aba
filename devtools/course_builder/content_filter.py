# -*- coding: utf-8 -*-
"""Drops sentence pairs that mention music (a standing rule of the academy:
no music anywhere), alcohol, drugs, sexual or romantic content, self-harm,
pork, and Christmas/Easter greetings. Applied to both the foreign sentence and
its Arabic translation."""
import re

MUSIC = {
    "en": "music musical musically musician musicians song songs sing sings singing sang sung singer singers piano pianist "
          "guitar guitars guitarist violin violinist drum drums drummer concert concerts orchestra melody melodies tune tunes "
          "lyrics album albums opera jazz band bands flute trumpet saxophone cello harp choir karaoke hymn rap rapper dj "
          "composer composed symphony dance dances dancing danced dancer dancers ballet beethoven mozart bach chopin beatles "
          "instrument instruments radio",
    "es": "música musical músico músicos canción canciones cantar canta cantas canto cantó cantan cantando cantante cantantes "
          "piano pianista guitarra violín tambor concierto conciertos orquesta melodía banda ópera flauta trompeta coro "
          "bailar baila bailan bailando bailó baile bailarín bailarina instrumento instrumentos sinfonía radio",
    "fr": "musique musical musicien musicienne musiciens chanson chansons chanter chante chantes chantent chanté chantait "
          "chanteur chanteuse chanteurs piano pianiste guitare violon tambour batterie concert concerts orchestre mélodie "
          "groupe opéra flûte trompette chorale danser danse dansent dansé dansait danseur danseuse ballet instrument "
          "instruments symphonie radio",
    "de": "musik musikalisch musiker musikerin lied lieder liedes singen singt sang gesungen singe sänger sängerin klavier "
          "pianist gitarre geige violine trommel schlagzeug konzert konzerte orchester melodie band oper flöte trompete chor "
          "tanzen tanzt tanzte getanzt tanz tänzer tänzerin ballett instrument instrumente sinfonie radio",
    "it": "musica musicale musicista musicisti canzone canzoni cantare canta canto cantato cantava cantano cantante cantanti "
          "pianoforte pianista chitarra violino tamburo batteria concerto concerti orchestra melodia band opera flauto tromba "
          "coro ballare balla ballano ballato ballo ballerino ballerina danza strumento strumenti sinfonia radio",
    "tr": "müzik müziği müziğe müzisyen şarkı şarkıyı şarkılar şarkıcı şarkıcısı piyano piyanist gitar gitarı keman davul "
          "konser konseri konsere orkestra melodi grup opera flüt trompet koro dans dansı dansçı bale enstrüman radyo",
}
OTHER = {
    "en": "sex sexy sexual naked nude kiss kissed kisses kissing girlfriend boyfriend dating beer beers wine wines drunk "
          "vodka whiskey whisky alcohol alcoholic liquor booze drugs drug cocaine heroin marijuana weed suicide rape raped "
          "prostitute porn condom pork bacon gay lesbian bra underwear sleep-with christmas easter santa hell damn bitch "
          "bastard shit fuck crap cigarette cigarettes smoke smoking smokes cigar",
    "es": "sexo sexual desnudo desnuda beso besó besar besos novia novio cerveza vinos borracho borracha alcohol "
          "drogas droga cocaína marihuana suicidio violación prostituta cerdo jamón navidad pascua cigarrillo cigarrillos "
          "fumar fuma fumo fumas fuman mierda puta",
    "fr": "sexe sexuel nu nue baiser embrassé embrasser bisou copine copain petite-amie petit-ami bière vin vins ivre "
          "saoul alcool drogue drogues cocaïne suicide viol prostituée porc jambon noël pâques cigarette cigarettes "
          "fumer fume fumes fument merde putain",
    "de": "sex sexuell nackt kuss küsste küssen bier wein betrunken alkohol drogen droge kokain "
          "selbstmord vergewaltigung prostituierte schwein schweinefleisch schinken weihnachten ostern zigarette "
          "zigaretten rauchen raucht rauche scheiße",
    "it": "sesso sessuale nudo nuda bacio baciato baciare fidanzata fidanzato birra vino vini ubriaco ubriaca "
          "alcol droga droghe cocaina suicidio stupro prostituta maiale prosciutto natale pasqua sigaretta sigarette "
          "fumare fuma fumo fumi fumano merda cazzo",
    "tr": "seks çıplak öptü öpmek öpücük sevgili sevgilisi kız-arkadaşı erkek-arkadaşı bira şarap sarhoş alkol "
          "uyuşturucu esrar intihar tecavüz fahişe domuz noel paskalya sigara içki rakı bok",
}
AR = ("موسيق", "أغني", "اغني", "أغان", "اغان", "غناء", "يغن", "تغن", "نغن", "أغن", "مغني", "مطرب", "بيانو", "غيتار",
      "قيتار", "جيتار", "الكمان", "كمنج", "طبل", "عزف", "يعزف", "تعزف", "نعزف", "أعزف", "طبول", "يغني", "تغني", "نغني", "أغني", "يغنون", "تغنين", "غنى", "غنّى", "غنت", "غنّت", "غنوا", "غنّوا", "لحن", "ألحان", "أوركسترا", "اوركسترا",
      "فرقة", "رقص", "يرقص", "ترقص", "راقص", "ألبوم", "أوبرا", "اوبرا", "جاز", "راديو", "مذياع", "حفلة موسيقية",
      "كونسرت", "كورال", "سيمفوني", "آلة موسيقية",
      "خمر", "نبيذ", "جعة", "سكران", "سكير", "كحول", "مخدر", "حشيش", "كوكايين", "انتحار", "اغتصاب", "عاهرة",
      "عارٍ", "عارية", "قبّل", "قبلها", "قبلته", "حبيبت", "حبيبه", "عشيق", "خنزير",
      "لحم الخنزير", "الميلاد المجيد", "عيد الميلاد", "الفصح", "سيجار", "سجائر", "تدخين", "يدخن", "تدخن", "دخّن", "اللعنة", "لعين")

_AR_RE = re.compile(r"(?:^|[\s\"(،.؟!:\-])(?:و|ف|ب|ل|ك)?(?:س|ل)?(?:ال)?(?:" + "|".join(sorted(map(re.escape, AR), key=len, reverse=True)) + ")")
_TOK = re.compile(r"[^\W\d_]+", re.U)
STEMS = {
    "en": r"sing(?:s|ing|er|ers)?|sang|sung|song\w*|music\w*|guitar\w*|violin\w*|danc\w*|concert\w*|piano\w*|drum\w*",
    "es": r"cant(?:ar|o|as|a|amos|áis|an|é|aste|ó|aron|aba\w*|ando|ante\w*|ará\w*|aría\w*|ad[oa]s?)|canci[oó]n\w*|m[uú]sic\w*|guitarr\w*|bail\w*|danz\w*|tambor\w*|violín|concierto\w*",
    "fr": r"chant(?:e|es|ent|er|é|ée|ais|ait|aient|ons|ez|eur|euse|eurs|erai\w*|erait|ions)?|chanson\w*|musi\w*|guitar\w*|dans(?:e|es|ent|er|é|ait|eur|euse)|violon\w*|concert\w*",
    "it": r"cant(?:are|o|i|a|iamo|ate|ano|ato|ava\w*|ando|ante\w*|erò|erai|erà|eremo|erete|eranno|erei\w*)|canzon\w*|music\w*|chitarr\w*|ball(?:are|o|a|ano|iamo|ato|ava\w*)|violin\w*|concert[oi]\w*|pianofort\w*",
    "de": r"musik\w*|sing(?:e|st|t|en)|sang(?:en|st)?|gesungen|sänger\w*|lied(?:er|ern)|gitarr\w*|klavier\w*|geige\w*|tanz\w*|tänz\w*|getanzt|konzert\w*",
    "tr": r"şarkı\w*|müzi\w*|dans\w*|piyano\w*|gitar\w*|keman\w*|konser\w*|davul\w*|çaldı\w*|çalıyor\w*|çalabil\w*",
}
_STEM_RE = {c: re.compile(r"(?<![^\W\d_])(?:" + p + r")(?![^\W\d_])", re.I) for c, p in STEMS.items()}
_SETS = {c: set((MUSIC.get(c, "") + " " + OTHER.get(c, "")).split()) for c in set(MUSIC) | set(OTHER)}
_SETS["en"] |= set()


def blocked(lang: str, foreign: str, arabic: str) -> bool:
    if _STEM_RE.get(lang) and _STEM_RE[lang].search(foreign):
        return True
    if lang != "en" and _STEM_RE["en"].search(foreign) and lang in ("de",):
        pass
    toks = {t.lower() for t in _TOK.findall(foreign)}
    bad = _SETS.get(lang, set()) | _SETS["en"] if lang != "en" else _SETS["en"]
    if toks & bad:
        return True
    if lang == "tr":
        low = foreign.lower()
        if any(low.find(p) >= 0 for p in ("şarkı", "müzik", "piyano", "gitar", "dans ", "dans.", "konser", "şarap", "bira ",
                                            "sigara", "sarhoş", "öptü", "öpüş")):
            return True
    if lang == "de":
        low = foreign.lower()
        if any(p in low for p in ("musik", "klavier", "gitarre", "konzert", "tänz")):
            return True
    return bool(_AR_RE.search(arabic))


def trigger(lang, foreign, arabic):
    toks = {t.lower() for t in _TOK.findall(foreign)}
    hit = toks & (_SETS.get(lang, set()) | _SETS["en"])
    m = _AR_RE.search(arabic)
    return sorted(hit), (m.group(0) if m else "")
