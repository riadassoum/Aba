Third-party Arabic libraries, used unchanged except for a few regular
expressions rewritten as raw strings (newer Python warns about them) and
unused modules left out:

pyarabic 0.6.15 by Taha Zerrouki (GPL) - https://github.com/linuxscout/pyarabic
  araby.py, araby_const.py, stack.py
libqutrub 1.2.4.1 by Taha Zerrouki (GPL) - https://github.com/linuxscout/libqutrub
  Qutrub, the Arabic verb conjugator. The command-line scripts were left out.

They are imported through abaAcademy.arabic_lab.qutrub, which adds this
folder to the import path.
