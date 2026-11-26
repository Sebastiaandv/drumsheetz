"""Ingebouwde bibliotheek met grooves en fills, geschreven in het .drum-formaat zelf.

Gebruik ze in een nummer gewoon bij naam:   [Couplet] 16 rock fill tom34
Bekijk ze met:  python3 drums.py bibliotheek       (of maak een PDF: --pdf)
Eigen patronen voor al je nummers: zet ze in bibliotheek.drum in de hoofdmap.
"""

BUILTIN = r"""
# ======================================================================
# GROOVES 4/4
# ======================================================================
groove rock:
  info: Basis rockbeat in 8sten
  HH: *8
  SD: 2 4
  BD: 1 3

groove rock2:
  info: Rock met extra bassdrum op 3-en
  HH: *8
  SD: 2 4
  BD: 1 3 3&

groove rock16:
  info: Rock met 16den op de hi-hat
  HH: *16
  SD: 2 4
  BD: 1 3

groove rockride:
  info: Rock op de ride
  RD: *8
  SD: 2 4
  BD: 1 3

groove rockopen:
  info: Rock met halfopen hi-hat (refrein-sound)
  HH: *8:h
  SD: 2 4
  BD: 1 3

groove kwart:
  info: Hi-hat in kwarten
  HH: *4
  SD: 2 4
  BD: 1 3

groove pop:
  info: Popbeat met syncope in de bassdrum
  HH: *8
  SD: 2 4
  BD: 1 2& 3

groove ballad:
  info: Ballad met cross stick
  HH: *8
  XS: 2 4
  BD: 1 3

groove ballad16:
  info: Ballad met 16den op de hi-hat en cross stick
  HH: *16
  XS: 2 4
  BD: 1 2a 3

groove halftime:
  info: Half-time: snare op 3
  HH: *8
  SD: 3
  BD: 1 2&

groove doubletime:
  info: Double-time: snare op elke &
  HH: *8
  SD: *&
  BD: *4

groove disco:
  info: Disco: bassdrum op elke tel, open hi-hat op de &
  HH: *8 *&:o
  SD: 2 4
  BD: *4

groove fotf:
  info: Four on the floor (house/dance)
  HH: *&
  CL: 2 4
  BD: *4

groove motown:
  info: Motown: snare op alle tellen, accent op 2 en 4
  HH: *8
  SD: *4 2:X 4:X
  BD: 1 2& 3

groove funk:
  info: 16den-funk met ghost notes
  HH: *16
  SD: 2 4 1a:g 2e:g 3a:g
  BD: 1 1& 2a 3&

groove funk8:
  info: Funk in 8sten met accent-hi-hat
  HH: *8 *4:X
  SD: 2 4 2a:g 4e:g
  BD: 1 1& 3&

groove hiphop:
  info: Boom-bap
  HH: *8
  SD: 2 4
  BD: 1 1a 3&

groove shuffle:
  info: Shuffle (triolen zonder de middelste)
  HH: *4 *l
  SD: 2 4
  BD: 1 3

groove halftimeshuffle:
  info: Half-time shuffle met ghost notes
  HH: *4 *l
  SD: 3 1t:g 2t:g 2l:g 4t:g
  BD: 1 1l 3l

groove swing:
  info: Jazz-swing op de ride, hi-hat voet op 2 en 4
  RD: 1 2 2l 3 4 4l
  HF: 2 4

groove triool:
  info: 8ste triolen op de hi-hat (12/8-gevoel in 4/4)
  HH: *8t
  SD: 2 4
  BD: 1 3

groove train:
  info: Trein-beat: snare 16den met accenten op 2 en 4
  SD: *16:g 2:X 4:X
  BD: 1 3

groove punk:
  info: Punk/polka: bassdrum op de tellen, snare op de &
  HH: *8
  SD: *&
  BD: *4

groove blast:
  info: Hammer blast (alles samen in 8sten)
  RD: *8
  SD: *8
  BD: *8

groove metal:
  info: Dubbele bassdrum in 16den
  CR: *4
  SD: 2 4
  BD: *8
  BD2: *e *a

groove onedrop:
  info: Reggae one drop: alleen op 3
  HH: *8
  XS: 3
  BD: 3

groove steppers:
  info: Reggae steppers: bassdrum op elke tel
  HH: *8
  XS: 3
  BD: *4

groove rockers:
  info: Reggae rockers
  HH: *8
  XS: 3
  BD: 1 3

groove bossa:
  info: Bossa nova (2 maten, cross-stick clave)
  maten: 2
  HH: *8
  XS: 1 2& 4 || 2& 4
  BD: 1 2& 3 4&

groove samba:
  info: Samba
  HH: *16
  XS: 1e 2 2& 3e 4
  BD: 1 1a 2 3 3a 4

groove jungle:
  info: Toms in de 'jungle'-stijl
  FT: 1 2 2& 3 4 4&
  BD: *4

# ======================================================================
# GROOVES andere maatsoorten
# ======================================================================
groove ballad68:
  info: 6/8 ballad
  maat: 6/8
  HH: *8
  SD: 4
  BD: 1 6

groove rock68:
  info: 6/8 rock
  maat: 6/8
  HH: *8
  SD: 4
  BD: 1 3

groove blues128:
  info: 12/8 slow blues op de ride
  maat: 12/8
  RD: *8
  SD: 4 10
  BD: 1 7

groove wals:
  info: 3/4 wals
  maat: 3/4
  HH: *8
  SD: 2 3
  BD: 1

groove jazzwals:
  info: 3/4 jazzwals
  maat: 3/4
  RD: 1 2 2l 3
  HF: 2

groove rock54:
  info: 5/4 rock
  maat: 5/4
  HH: *8
  SD: 2 4
  BD: 1 3 5

groove rock78:
  info: 7/8 rock (2+2+3)
  maat: 7/8 (2+2+3)
  HH: *8
  SD: 3 6
  BD: 1 5

# ======================================================================
# FILLS 4/4  (een fill vervangt de laatste maat; groove-slagen vóór de fill blijven staan.
#             Zonder BD-rij loopt de bassdrum van de groove door.)
# ======================================================================
fill sd4:
  info: 16den op de snare op tel 4
  SD: ------------xxxx
  BD: x-------x-------

fill pick8:
  info: 8sten-oppikker op 4 en 4&
  SD: ------------x-x-
  BD: x-------x-------

fill bal4:
  info: Snare op 4, floor tom op 4&
  SD: ------------xx--
  FT: --------------xx
  BD: x-------x-------

fill tom34:
  info: Dalend over de toms, tel 3-4
  SD: --------xx------
  T1: ----------xx----
  T2: ------------xx--
  FT: --------------xx
  BD: x-------x-------

fill sd34:
  info: Snare 16den over 3-4 met accenten
  SD: --------xxxxxXxX
  BD: x-------x-------

fill tomfull:
  info: Hele maat rond de toms
  SD: xxxx------------
  T1: ----xxxx--------
  T2: --------xxxx----
  FT: ------------xxxx
  BD: x---x---x---x---

fill soft4:
  info: Zachte ballad-oppikker: cross stick + floor tom
  XS: ------------x---
  FT: --------------x-
  BD: x-------x-------

fill sd16:
  info: Hele maat 16den op de snare, crescendo-accenten op 4
  SD: *16 4:X 4&:X
  BD: *4

fill sd8:
  info: Hele maat 8sten op de snare
  SD: *8

fill trip4:
  info: Snare-triool op tel 4
  SD: 4 4t 4l

fill trip34:
  info: Triolen over 3-4: snare, tom, floor
  SD: 3 3t 3l
  T1: 4
  T2: 4t
  FT: 4l
  BD: 1

fill tom4:
  info: Toms op tel 4 (16den)
  T1: 4 4e
  T2: 4&
  FT: 4a

fill flam4:
  info: Flams op 4 en 4&
  SD: 4:f 4&:f

fill lin4:
  info: Lineaire fill op tel 4
  SD: 4
  T1: 4e
  FT: 4&
  BD: 4a

fill crash4:
  info: Crash + bassdrum op 4& (anticipatie)
  CR: 4&
  BD: 4&
  SD: 4

fill opbouw:
  info: 8sten → 16den op de snare (opbouw naar refrein)
  SD: 1 1& 2 2& 3-4*16 4:X 4a:X
  BD: *4

# ======================================================================
# FILLS andere maatsoorten
# ======================================================================
fill trip68:
  info: 6/8: snare op 4-5-6
  maat: 6/8
  SD: ---xxx
  BD: x-----

fill tom68:
  info: 6/8: hele maat over de toms
  maat: 6/8
  SD: xx----
  T1: --xx--
  FT: ----xx
  BD: x--x--

fill fill128:
  info: 12/8: snare op de laatste tel
  maat: 12/8
  SD: 10 11 12
  BD: 1 7

# ======================================================================
# SLOTSLAGEN en STOPS
# ======================================================================
groove hit:
  info: Slotslag: crash + bassdrum op 1
  CR: 1
  BD: 1

groove stop:
  info: Stop: crash + bassdrum op 1, daarna stilte
  CR: 1
  BD: 1

groove hitsd:
  info: Slotslag met snare
  CR: 1
  SD: 1:X
  BD: 1

groove choke:
  info: Crash op 1, direct afgeknepen
  CR: 1:k
  BD: 1
"""

LEGACY_FILLS_44 = ["sd4", "pick8", "bal4", "tom34", "sd34", "tomfull", "soft4"]

_BOOK = None


def builtin_book():
    global _BOOK
    if _BOOK is None:
        from .parser import Parser
        p = Parser(BUILTIN, "<bibliotheek>")
        _, book = p.parse_patterns_only()
        _BOOK = book
    return _BOOK
