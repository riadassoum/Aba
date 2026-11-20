Third-party Arabic libraries, used unchanged except for a few regular
expressions rewritten as raw strings (newer Python warns about them) and
unused modules left out:

pyarabic 0.6.15 by Taha Zerrouki (GPL) - https://github.com/linuxscout/pyarabic
  araby.py, araby_const.py, stack.py
libqutrub 1.2.4.1 by Taha Zerrouki (GPL) - https://github.com/linuxscout/libqutrub
  Qutrub, the Arabic verb conjugator. The command-line scripts were left out.

They are imported through abaAcademy.arabic_lab.qutrub, which adds this
folder to the import path.

sunfish by Thomas Ahle and contributors (GPL-3.0) - https://github.com/thomasahle/sunfish
  The classic chess engine, sunfish.py, unchanged; its UCI loop is not used.

Mishkal 0.4.1, the Arabic diacritizer, by Taha Zerrouki (GPL) - https://github.com/linuxscout/mishkal
  with the libraries it needs, as published on PyPI and bundled unchanged:
  qalsadi 0.5.1 (morphological analyzer), asmai 0.1, arramooz-pysqlite 0.4.2 (dictionary),
  maskouk-pysqlite 0.1 (collocations), sylajone 0.3.1 (syntax), naftawayh 0.4 (word tagger),
  tashaphyne 0.3.6 (stemmer), alyahmor 0.2 (affixes), mysam-tagmanager 0.4.1, Arabic-Stopwords 0.4.3,
  all by Taha Zerrouki and contributors (GPL); pickledb 1.6 (BSD), aiofiles (Apache-2.0),
  codernitydb3 0.6.0 (Apache-2.0) and six (MIT). PyArabic is now the complete package.
  They are imported through abaAcademy.arabic_lab.diacritizer.
  From naftawayh, two Python 2 helper scripts that nothing imports (create_verbstamp.py, ar_ctype.py) were left out.
