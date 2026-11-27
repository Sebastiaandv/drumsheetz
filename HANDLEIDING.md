# Drumsheetz — handleiding

Drumsheetz maakt nette drum sheets (PDF) van een simpel tekstbestand. Je schrijft per nummer een
`.drum`-bestand; het programma maakt er MusicXML van en laat MuseScore er een PDF (en een
MuseScore-bestand) van maken, met precies dezelfde opmaak als de oude sheets: elke sectie op een
nieuwe regel in een **kader met de naam** ("blokjes met tekst"), herhaalde maten als **%** met
**N×** erboven, en maatnummers die gewoon doortellen.

Daarnaast: setlists (met voorblad, podiumlijst en één compleet PDF-boek), MIDI om mee te oefenen,
een bibliotheek met kant-en-klare grooves en fills, en een tekstweergave in de terminal.

---

## Inhoud

1. [Snel beginnen](#1-snel-beginnen)
2. [Mappen](#2-mappen)
   - [De Studio (editor in je browser)](#de-studio-editor-in-je-browser)
3. [Alle opdrachten](#3-alle-opdrachten)
4. [Een nummer schrijven: het .drum-formaat](#4-een-nummer-schrijven-het-drum-formaat)
   1. [De kop](#41-de-kop)
   2. [Patronen: grooves en fills](#42-patronen-grooves-en-fills)
   3. [Instrumenten](#43-instrumenten)
   4. [Rasternotatie](#44-rasternotatie)
   5. [Telnotatie](#45-telnotatie)
   6. [Aanslagtekens (accent, ghost, flam, open hi-hat, ...)](#46-aanslagtekens)
   7. [Sticking (R/L)](#47-sticking-rl)
   8. [Triolen, kwintolen en andere verdelingen](#48-triolen-kwintolen-en-andere-verdelingen)
   9. [Patronen van meer maten](#49-patronen-van-meer-maten)
   10. [Patronen afleiden en aanpassen](#410-patronen-afleiden-en-aanpassen)
   11. [De opbouw: secties en regels](#411-de-opbouw-secties-en-regels)
   12. [Crash en fills](#412-crash-en-fills)
   13. [Dynamiek en crescendo](#413-dynamiek-en-crescendo)
   14. [Tempo, tempowisselingen en fermate](#414-tempo-tempowisselingen-en-fermate)
   15. [Maatsoorten en maatwisselingen](#415-maatsoorten-en-maatwisselingen)
   16. [Herhalingen: %, herhaaltekens en volta's](#416-herhalingen--herhaaltekens-en-voltas)
   17. [Segno, Coda, D.S., D.C. en Fine](#417-segno-coda-ds-dc-en-fine)
   18. [Rust, vrij spelen en ensemble-hits](#418-rust-vrij-spelen-en-ensemble-hits)
   19. [Patronen direct in de regel](#419-patronen-direct-in-de-regel)
   20. [Opmaak: regels en pagina's](#420-opmaak-regels-en-paginas)
   21. [Aftellen](#421-aftellen)
   22. [Eigen instrumenten en notenbalkposities](#422-eigen-instrumenten-en-notenbalkposities)
   23. [Commentaar](#423-commentaar)
5. [De bibliotheek](#5-de-bibliotheek)
6. [Setlists](#6-setlists)
7. [Versies en forScore op de iPad](#7-versies-en-forscore-op-de-ipad)
   - [Versiebeheer](#versiebeheer)
   - [forScore](#forscore)
8. [MIDI: oefenen met een meespeelbestand](#8-midi-oefenen-met-een-meespeelbestand)
9. [Archief](#9-archief)
10. [Het geavanceerde Python-formaat](#10-het-geavanceerde-python-formaat)
11. [Automatisch transcriberen uit een opname](#11-automatisch-transcriberen-uit-een-opname)
12. [Instellingen](#12-instellingen)
13. [Foutmeldingen en tips](#13-foutmeldingen-en-tips)
14. [Spiekbrief](#14-spiekbrief)

---

## 1. Snel beginnen

**Nodig:**

- Python 3.8 of nieuwer (`python3 --version`)
- [MuseScore 4](https://musescore.org) voor de PDF's. Wordt automatisch gevonden op Mac, Windows en Linux.
  Zonder MuseScore krijg je alleen MusicXML (die je in elk notatieprogramma kunt openen).
- Optioneel voor setlists: `pip3 install pypdf reportlab` (voor het complete boek, het voorblad en de podiumlijst).

**Eerste nummer:**

```bash
python3 drums.py nieuw "Mijn Nummer" "De Band" --tempo 120
```

Dat maakt `nummers/mijnnummer.drum` met een sjabloon. Open het, pas het aan, en:

```bash
python3 drums.py toon mijnnummer
```

laat het nummer direct als drumtab in de terminal zien (handig om te controleren, geen MuseScore nodig).

```bash
python3 drums.py maak mijnnummer
```

maakt `uitvoer/pdf/mijnnummer.pdf` en `uitvoer/mscz/mijnnummer.mscz`.

**Het kortste nummer** dat je kunt schrijven gebruikt alleen ingebouwde grooves en fills:

```
titel: Mijn Eerste Nummer
artiest: De Band
tempo: 120

[Intro]    4 rock crash fill sd4
[Couplet]  16 rock mf fill pick8
[Refrein]  8 rockride crash f fill tom34
[Outro]    1 hit fermata
```

Zie ook `voorbeelden/simpel.drum` en `voorbeelden/alles.drum` (dat laatste gebruikt bijna alle notatie).

### De Studio (editor in je browser)

Liever niet in de terminal werken? Start de Studio:

```bash
python3 drums.py studio
```

Je browser opent dan `http://127.0.0.1:8765` (alleen bereikbaar vanaf je eigen computer; stoppen met
Ctrl+C in de terminal). Je typt nog steeds gewoon in de `.drum`-bestanden, maar met alles erbij:

| Plek | Wat |
|---|---|
| **Links** | Bestanden: nummers, setlists, voorbeelden, `bibliotheek.drum`, `instellingen.txt`, de handleiding. Met zoekveld. |
| **Midden** | De editor met kleuren (secties, patronen, instrumenten, accenten, ghost notes, teksten, opties) en regelnummers. Fouten worden **tijdens het typen** gevonden en de regel kleurt rood. |
| **Onder** | *Drumtab* (het nummer als tekst, live bijgewerkt), *Problemen* (klik om naar de regel te gaan), *PDF* (de gemaakte PDF), *Log*. |
| **Rechts** | *Document*: alle eigenschappen van het nummer (titel, ondertitel, vermelding, tempo, maat, stijl, aftellen, stemmen, tekstgrootte, accenten, vorken, duur, …) als invulvelden. Wat je invult komt direct bovenin het bestand; leeg = standaard uit `instellingen.txt` (staat er grijs bij). *Gereedschap*: klik om in te voegen: blokken (groove, fill, sectie, volta's, segno/coda, …), opties (crash, fill, mf, cresc, …), tekens (accent, ghost, flam, …), tellen (`*8`, `2&`, …) en instrumenten. *Bibliotheek*: alle grooves en fills doorzoeken, met voorbeeld. *Help*: doorzoek deze handleiding. |
| **Boven** | Nieuw nummer, nieuwe setlist, Document (eigenschappen), opslaan, controleren, **Maak PDF** (of setlist), PDF openen, MIDI (tempo %, aftellen, klik), alles maken, archiveren, instellingen, help. |

**Bestanden en mappen beheren** (links, tabblad *Bestanden*): ga met de muis over een map of bestand
voor de knopjes: **＋♩** nieuw nummer in deze map, **＋▤** nieuwe map, **▶** alle nummers in deze map
maken, **✎** hernoemen (of dubbelklikken, of **F2**), **🗑** naar het archief (nummers) of een lege map
weghalen. **Sleep** een nummer of map naar een andere map om het te verplaatsen. Bij hernoemen en
verplaatsen gaan de PDF's en MuseScore-bestanden mee, en worden setlists die naar het nummer verwijzen
automatisch aangepast.

Sneltoetsen: **⌘/Ctrl+S** opslaan, **⌘/Ctrl+Enter** PDF maken, **⌘/Ctrl+Z** ongedaan maken en
**⌘/Ctrl+Shift+Z** (of Ctrl+Y) opnieuw (werkt ook na opslaan en na wijzigingen via het Document-paneel of
het gereedschap), **⌘/Ctrl+F** zoeken en vervangen (met *Alle bestanden* zoek je in al je nummers en
setlists; klik op een resultaat om er naartoe te gaan), **Tab** = 2 spaties, **Enter** houdt de inspringing aan.

Patronen die je hebt gemaakt maar nergens in de opbouw gebruikt, staan **grijs en doorgestreept** in
de editor, zodat je ze makkelijk kunt opruimen. De panelen kun je breder/smaller slepen. Andere poort: `python3 drums.py studio --poort 9000`.

---

## 2. Mappen

| Map / bestand | Wat staat er |
|---|---|
| `nummers/` | Je nummers: `.drum` (nieuw formaat) of `.py` (oud/geavanceerd formaat). Namen mogen alles bevatten wat een gewoon bestand mag (hoofdletters, spaties, `&`, haakjes, …). Submappen mogen; de uitvoer krijgt dezelfde mappenstructuur (`uitvoer/pdf/Hatikwa/The River.pdf`). Een map die met `_` begint (bv. `_Ideeën`) is **geparkeerd**: die wordt niet meegenomen bij *alles maken*, `lijst` en het forScore-overzicht. |
| `setlists/` | Setlists als `.txt`. |
| `uitvoer/pdf/` | De PDF's. |
| `uitvoer/mscz/` | MuseScore-bestanden (om in MuseScore nog iets met de hand te verschuiven). |
| `uitvoer/xml/` | MusicXML (tussenstap; opent ook in Sibelius, Dorico, Guitar Pro, ...). |
| `uitvoer/midi/` | MIDI-oefenbestanden. |
| `uitvoer/setlists/` | Alles wat een setlist oplevert. |
| `bibliotheek.drum` | Je eigen grooves en fills, bruikbaar in álle nummers. |
| `instellingen.txt` | Je naam (voor "Drum sheet: …"), pad naar MuseScore, enz. |
| `voorbeelden/` | Voorbeeldnummers. |
| `archief/` | Alles van vóór deze versie, plus wat je later archiveert. |
| `tools/auto.py` | Automatisch transcriberen uit een opname. |
| `drumsheetz/` | Het programma zelf. |
| `drums.py` | Hiermee start je alles. |

---

## 3. Alle opdrachten

Alle opdrachten beginnen met `python3 drums.py`. Een *nummer* mag je aanduiden met de bestandsnaam
zonder extensie (`letlove`), de titel (`"Let Love Rule"`), een stuk ervan (`kravitz`), of een pad
(`voorbeelden/alles.drum`). Kleine typfouten worden vaak begrepen. Engelse namen werken ook
(`build`, `show`, `list`, ...).

| Opdracht | Wat het doet |
|---|---|
| `maak` | Maak PDF's van **alle gewijzigde** nummers. Ongewijzigde worden overgeslagen. |
| `maak letlove crime` | Alleen deze nummers. |
| `maak "nummers/Hatikwa"` | Alle nummers in die map (ook als hij geparkeerd is). |
| `maak -a` | Alles opnieuw, ook als er niets veranderd is. |
| `maak --xml` | Alleen MusicXML (geen MuseScore nodig). |
| `maak --midi` | Ook een MIDI-bestand maken. |
| `maak letlove --open` | Maak en open de PDF. |
| `toon letlove` | Nummer als drumtab in de terminal, met maatnummers, %-tekens en opties. |
| `lijst` | Tabel met alle nummers: tempo, maatsoort, aantal maten, geschatte duur, status, PDF ja/nee. |
| `lijst --zoek queen` | Alleen nummers waar "queen" in zit. |
| `controleer` | Controleert alle nummers op fouten en geeft waarschuwingen (bv. een rasterrij met 15 tekens). |
| `nieuw "Titel" "Artiest"` | Nieuw nummer uit sjabloon (bestandsnaam = titel). Opties: `--maat 6/8`, `--tempo 72`, `--stijl "..."`, `--map Hatikwa`, `--id bestandsnaam`. |
| `midi letlove` | MIDI-oefenbestand. Opties: `--tempo 80` (procent), `--klik`, `--aftellen 2`. |
| `bibliotheek` | Alle ingebouwde en eigen grooves en fills als drumtab. |
| `bibliotheek funk` | Eén patroon bekijken. |
| `bibliotheek --pdf` | Catalogus van alle patronen als PDF (`uitvoer/bibliotheek.pdf`). |
| `instrumenten` | Alle instrumentcodes, hun plek op de balk, en alle aanslagtekens. |
| `archiveer letlove` | Verplaats nummer + PDF/MuseScore/XML/MIDI naar `archief/<datum>/`. |
| `herstel letlove` | Haal een gearchiveerd nummer terug naar `nummers/`. |
| `converteer oud.py` | Zet een nummer in het oude Python-formaat om naar `.drum`. |
| `kijk` | Blijft draaien en maakt een nummer opnieuw zodra je het opslaat. `kijk --xml` is sneller. |
| `setlist lijst` | Alle setlists. |
| `setlist nieuw bruiloft always crime scene` | Nieuwe setlist met deze nummers. |
| `setlist toon bruiloft` | Overzicht met tempo, maatsoort, duur, subtotalen per set. |
| `setlist maak bruiloft` | Alle PDF's, genummerde kopieën, compleet boek, voorblad, podiumlijst. |
| `forscore` | forScore gelijk maken aan Drumsheetz: nieuwe nummers, nieuwe versies, setlists (zie hoofdstuk 7). |
| `forscore letlove --notitie "nieuwe intro"` | Alleen dit nummer, met een notitie bij de nieuwe versie. |
| `versies` | Overzicht: welke versie elk nummer heeft en of het sindsdien gewijzigd is. |
| `versies letlove` | Alle versies van één nummer, met datum, notitie en naam in forScore. |
| `versies letlove --nieuw "notitie"` | Nu een versie vastleggen (met PDF). |
| `versies letlove --verschil 2` | Wat er veranderd is sinds V2 (`--verschil 2 4`: tussen V2 en V4). |
| `versies letlove --terug 2` | V2 terugzetten (wat er stond wordt eerst als reservekopie bewaard). |
| `versies --controleer` | Controleer of alle versiebestanden er nog zijn en niet veranderd zijn. |
| `studio` | Open de Studio: editor met bestanden, gereedschap en help in je browser. |
| `help` | Overzicht van de opdrachten. `python3 drums.py maak -h` geeft de opties van één opdracht. |

---

## 4. Een nummer schrijven: het .drum-formaat

Een `.drum`-bestand is gewone tekst met drie soorten onderdelen:

```
titel: Let Love Rule            ← 1. de kop (gegevens over het nummer)
artiest: Lenny Kravitz
tempo: 90

groove couplet:                 ← 2. patronen (grooves en fills)
  HH: *8 4&:o
  SD: 2 4
  BD: 1 2a 3 3&

[Intro] 8 couplet fill sd4      ← 3. de opbouw (secties met maten)
[Couplet 1] 16 couplet
```

Hoofdletters maken bij instrumentcodes en opties niet uit. Lege regels en inspringen zijn vrij
(behalve dat de rijen van een patroon ingesprongen of met een instrumentcode moeten beginnen).

### 4.1 De kop

Bovenaan, als `sleutel: waarde`. Alleen `titel` is eigenlijk nodig.

| Sleutel | Betekenis | Voorbeeld |
|---|---|---|
| `titel` | Titel bovenaan de PDF | `titel: Fields Of Gold` |
| `artiest` | Rechtsboven | `artiest: Sting` |
| `ondertitel` | Kleinere regel onder de titel (leeg = geen) | `ondertitel: Drum partituur t.b.v. het koor` |
| `vermelding` | Tekst rechtsboven onder de artiest; `{naam}` = je naam uit `instellingen.txt`; meerdere regels met `\n`. Leeg = niets | `vermelding: Drum sheet: {naam}` |
| `tempo` | Tempo; in 6/8, 9/8, 12/8 is dat de gepunteerde kwart | `tempo: 92` |
| | Met eenheid: `noot=getal` (4 = kwart, 4. = gepunteerde kwart, 8 = achtste, 2 = halve) | `tempo: 8=210` |
| `maat` | Maatsoort (standaard 4/4), eventueel met groepering | `maat: 6/8`, `maat: 7/8 (2+2+3)` |
| `stijl` | Cursieve regel onder het tempo (feel) | `stijl: Laid back shuffle` |
| `notitie` | Extra cursieve regel | `notitie: Brushes in het eerste couplet` |
| `door` | Naam die voor `{naam}` in de vermelding wordt ingevuld (in plaats van die uit de instellingen) | `door: Jan Jansen` |
| `swing` | Zet "Swing" bij de stijl én laat de MIDI swingen. `ja` of `8` = 8sten, `16` = 16den | `swing: ja` |
| `aftellen` | Aantal maten aftellen met stokken (staat op het blad én in de MIDI) | `aftellen: 1` |
| `stemmen` | `1` = alles (ook bassdrum en hi-hat-voet) in één stem met de stokken omhoog, zonder losse rusten; `2` = handen omhoog, voeten omlaag (de oude opmaak). Standaard uit `instellingen.txt` | `stemmen: 2` |
| `herhaalteller` | Waar de `N×` bij een %-maat staat: `binnen` (in de balk, rechts naast het %-teken; standaard), `links` (in de balk, aan het begin van de maat) of `boven` (boven de maat, zoals vroeger) | `herhaalteller: boven` |
| `vorken` / `dynamiek` | Vorken (met hun letters) en losse dynamiektekens `onder` of `boven` de balk; standaard vorken onder, losse letters boven | `vorken: boven` |
| `accenten` | Waar accenten (`>`, `^`) en open/dicht-tekens staan: `boven` (boven de noten, standaard), `onder`, of `auto` (MuseScore kiest, meestal bij de nootkop) | `accenten: auto` |
| `tekstgrootte` | Grootte van de cursieve teksten bij de maten (lyrics, aanwijzingen): `klein` (8), `normaal` (10), `groot` (12), `heelklein`, `heelgroot` of een getal in punten. Standaard uit `instellingen.txt` | `tekstgrootte: 9` |
| `stijlgrootte` | Hetzelfde voor de `stijl`- en `notitie`-regel bovenaan | `stijlgrootte: klein` |
| `layout` | `secties` (standaard: elke sectie op een nieuwe regel) of `doorlopend` | `layout: doorlopend` |
| `maten-per-regel` | Forceer een vast aantal maten per regel | `maten-per-regel: 4` |
| `herhaaltekens` | `nee` = nooit %-maten, alles uitschrijven | `herhaaltekens: nee` |
| `duur` | Duur voor de setlist (anders berekend uit maten en tempo) | `duur: 4:32` |
| `pdf` | Gebruik in setlists deze (gekochte) PDF in plaats van de eigen sheet | `pdf: archief/pdf-gekocht/x.pdf` |
| `componist`, `album`, `jaar`, `toonsoort`, `bron`, `status` | Komen **linksboven** op het blad (bv. "Muziek: …", "Album · 1999", "Toonsoort: F", "Bron: …", "Status: concept"), alleen wat je invult | `toonsoort: F` |
| `tags`, `audio` | Niet op het blad: `tags` om op te zoeken (`lijst --zoek`), `audio` als verwijzing naar een opname | `tags: ballad koor` |

### 4.2 Patronen: grooves en fills

Een patroon is één (of meer) maten. Je geeft het een naam en zet er per instrument een rij onder:

```
groove rock:
  HH: x-x-x-x-x-x-x-x-
  SD: ----x-------x---
  BD: x-------x-------
```

- `groove` en `fill` werken hetzelfde; het verschil is alleen hoe je ze gebruikt (zie [4.12](#412-crash-en-fills)).
  `patroon` mag ook.
- De naam mag letters, cijfers, `_` en `-` bevatten (geen spaties).
- Rijen beginnen met een instrumentcode en een dubbele punt. Elke rij is **raster** ([4.4](#44-rasternotatie))
  of **tellen** ([4.5](#45-telnotatie)); dat mag je per rij kiezen en mengen.
- Op één regel kan ook, rijen gescheiden door `;`:

```
groove rock: HH *8; SD 2 4; BD 1 3
```

Extra regels in een patroon:

| Regel | Betekenis |
|---|---|
| `info: tekst` | Beschrijving (zichtbaar in `bibliotheek`). |
| `maten: 2` | Patroon van 2 (of meer) maten, zie [4.9](#49-patronen-van-meer-maten). |
| `maat: 6/8` | Dit patroon is in een andere maatsoort dan het nummer (zie [4.15](#415-maatsoorten-en-maatwisselingen)). |

### 4.3 Instrumenten

| Code | Instrument | Plek op de balk | Nootkop | Ook te schrijven als |
|---|---|---|---|---|
| `BD` | bassdrum | 1e vak (F4) | normaal | `KICK`, `BASS`, `K` |
| `BD2` | bassdrum 2 / linkervoet dubbele pedaal | onderste lijn (E4) | normaal | `KICK2` |
| `HF` | hi-hat met de voet | onder de balk (D4) | kruis | `HP`, `HHF`, `PEDAL`, `VOET` |
| `HS` | hi-hat voet-splash | onder de balk (D4) | kruis + rondje | `HHS` |
| `SD` | snare | 3e vak (C5) | normaal | `S`, `SN`, `SNARE` |
| `XS` | cross stick / side stick | 3e vak (C5) | kruis | `CS`, `RS`, `SS`, `SIDESTICK` |
| `RIM` | rimshot | 3e vak (C5) | omcirkeld kruis | `RIMSHOT` |
| `CL` | handclap | 3e vak (C5) | driehoek | `CLAP` |
| `T1` | tom 1 (hoog) | 4e vak (E5) | normaal | `HT`, `TOM1` |
| `T2` | tom 2 (midden) | 4e lijn (D5) | normaal | `MT`, `TOM2` |
| `T3` | tom 3 (laag) | middelste lijn (B4) | normaal | `LT`, `TOM3` |
| `FT` | floor tom | 2e vak (A4) | normaal | `F`, `FLOOR` |
| `FT2` | floor tom 2 (laag) | 2e lijn (G4) | normaal | `LFT`, `FLOOR2` |
| `HH` | hi-hat (dicht, met stok) | boven de balk (G5) | kruis | `H`, `HIHAT` |
| `HO` | hi-hat open | boven de balk (G5) | kruis + rondje | `OH` |
| `RD` | ride | bovenste lijn (F5) | kruis | `R`, `RIDE` |
| `RB` | ride bell | bovenste lijn (F5) | ruit | `BELL` |
| `CR` | crash | 1e hulplijn (A5) | kruis | `C`, `CRASH` |
| `CR2` | crash 2 | boven 1e hulplijn (B5) | kruis | `C2`, `CRASH2` |
| `SP` | splash | 2e hulplijn (C6) | kruis | `SPLASH` |
| `CH` | china | 2e hulplijn (C6) | omcirkeld kruis | `CHINA` |
| `STK` | stack | B5 | omcirkeld kruis | `STACK` |
| `CB` | cowbell | A5 | driehoek | `COWBELL` |
| `TAMB` | tamboerijn | B5 | ruit | `TB`, `TAMBOURINE` |
| `TRI` | triangel | B5 | driehoek | `TRIANGLE` |
| `SHK` | shaker | G5 | driehoek | `SHAKER` |
| `CLV` | claves | F5 | driehoek | `CLAVES` |
| `WB` / `WBL` | woodblock hoog / laag | E5 / D5 | driehoek | `WOODBLOCK` |
| `AGH` / `AGL` | agogo hoog / laag | A5 / G5 | ruit | `AGOGO` |
| `CGH` / `CGL` | conga hoog / laag | E5 / D5 | ruit | `CONGA` |
| `BGH` / `BGL` | bongo hoog / laag | E5 / D5 | plus | `BONGO` |
| `TBH` / `TBL` | timbale hoog / laag | E5 / D5 | vierkant | `TIMBALE` |
| `CK` | stokken tegen elkaar (aftellen) | middelste lijn | kruis | `STICKS`, `CLICK` |
| `SL` | ritme-slash (ensemble-figuur, klinkt niet) | middelste lijn | slash | `SLASH`, `HITS` |
| `ST` | sticking-rij (geen instrument, zie [4.7](#47-sticking-rl)) | onder de balk | tekst | `STICKING` |

Met `stemmen: 1` (zo staat het in `instellingen.txt`) staan álle noten in één stem met de stok
omhoog, zonder losse rusten voor de voeten. Met `stemmen: 2` staan de voeten (`BD`, `BD2`, `HF`,
`HS`) met de stok omlaag en de rest omhoog, zoals op de oude sheets. Per nummer in te stellen in de kop. Je kunt plek, nootkop en MIDI-geluid aanpassen of eigen
instrumenten toevoegen: zie [4.22](#422-eigen-instrumenten-en-notenbalkposities).

Tip: `python3 drums.py instrumenten` laat deze lijst altijd actueel zien.

### 4.4 Rasternotatie

Eén teken per tijdstap. `x` = slag, `-` = niets (`.` en `_` mogen ook voor niets).

```
HH: x-x-x-x-x-x-x-x-      16 tekens in 4/4 = 16den
SD: ----x-------x---
BD: x-------x-x-----
```

**De lengte bepaalt de verdeling.** De hele rij wordt gelijk over de maat verdeeld:

| Maatsoort | Tekens | Verdeling |
|---|---|---|
| 4/4 | 4 | kwarten |
| 4/4 | 8 | 8sten |
| 4/4 | 12 | 8ste triolen |
| 4/4 | 16 | 16den |
| 4/4 | 24 | 16de triolen (sextolen) |
| 4/4 | 32 | 32sten |
| 3/4 | 6 / 9 / 12 | 8sten / 8ste triolen / 16den |
| 6/8 | 6 / 12 | 8sten / 16den |
| 12/8 | 12 / 24 | 8sten / 16den |
| 7/8 | 7 / 14 | 8sten / 16den |

Elke rij mag een eigen lengte hebben: `HH: x-x-x-x-` (8sten) en `SD: ----x-------x---` (16den) gaan prima samen.

**Stukken met `|` of spaties.** Deel de rij op in stukken; elk stuk krijgt een gelijk deel van de
maat, met zijn eigen verdeling. Zo kun je per tel wisselen:

```
HH: x-x-|xxx|x-x-x-|xxxxx       tel 1: 8sten, tel 2: triool, tel 3: sextool (3 slagen), tel 4: kwintool
SD: x-x- x-x- x-x- x-x-          spaties mogen ook, alleen voor de leesbaarheid
```

**Meerdere maten met `||`:**

```
XS: x-----x-----x---||------x-----x---
```

Alle tekens die je in een raster kunt gebruiken staan in [4.6](#46-aanslagtekens).

### 4.5 Telnotatie

In plaats van een raster schrijf je de tellen op waar een slag valt. Dit is vaak het makkelijkst.

```
SD: 2 4              op 2 en 4
BD: 1 2& 3 3a        op 1, 2-en, 3 en 3-a
```

| Schrijfwijze | Positie | Voorbeeld |
|---|---|---|
| `1` `2` `3` … | op de tel | `SD: 2 4` |
| `1e` | 2e 16de ("één-e") | `BD: 1 1e` |
| `1&` (of `1+`, `1en`) | 8ste na de tel ("één-en") | `HH: 1& 2& 3& 4&` |
| `1a` | 4e 16de ("één-a") | `BD: 2a` |
| `1t` (of `1trip`) | 2e triool-noot | `SD: 4 4t 4l` |
| `1l` (of `1let`) | 3e triool-noot | `RD: 1 2 2l 3 4 4l` (swing-ride) |
| `2.25`, `2.5` | decimale positie (2.5 = 2&) | `SD: 3.75` |
| `1+1/6`, `4+5/6` | breuk: elke verdeling die je maar wilt | `T1: 4 4+1/6 4+2/6` (sextool) |

De tel is de noemer van de maatsoort: in 4/4 een kwart, in 6/8 en 7/8 een **achtste** (dus in 6/8
tel je 1 t/m 6, en is `2&` de 16de na de tweede achtste).

**Reeksen met `*`** (alle … van de maat):

| Schrijfwijze | Betekenis |
|---|---|
| `*4` | alle kwarten |
| `*8` | alle 8sten |
| `*16` | alle 16den |
| `*32` | alle 32sten |
| `*8t` | alle 8ste triolen |
| `*16t` | alle 16de triolen |
| `*&` | alle "en"-tellen (offbeats) |
| `*e`, `*a` | alle e's, alle a's |
| `*t`, `*l` | alle 2e of 3e triool-noten |
| `3-4*16` | 16den op tel 3 t/m 4 |
| `1-2*8t` | 8ste triolen op tel 1 t/m 2 |

**Weghalen met `!`**:

```
HH: *8 !4&          alle 8sten behalve 4&
HH: *16 !2e !4e
```

**Aanslag na `:`** (zie [4.6](#46-aanslagtekens); meerdere tekens mogen):

```
HH: *8 4&:o          open op 4&
SD: 2 4 2a:g 3e:g    ghost notes
SD: *16 4:X 4&:X     accenten
HH: *8:h             alles half open
CR: 1:Xk             crash met accent, direct afknijpen
```

Later in de rij overschrijft eerder: `HH: *8 *&:o` = alle 8sten, en de en-tellen open (disco).

**Meerdere maten met `||`:** `XS: 1 2& 4 || 2& 4`

### 4.6 Aanslagtekens

Deze tekens gebruik je als teken in een raster (`SD: ----X---g---x---`) of na de dubbele punt in
telnotatie (`SD: 2:X 3e:g`). Hoofdletter = met accent.

| Teken | Betekenis | Op het blad | Raster-voorbeeld | Tel-voorbeeld |
|---|---|---|---|---|
| `x` | gewone slag | noot | `SD: ----x---` | `SD: 2` |
| `X` | accent | `>` | `SD: ----X---` | `SD: 2:X` |
| `^` | marcato (zwaar accent) | `^` | `SD: ----^---` | `SD: 2:^` |
| `g` | ghost note | noot tussen haakjes | `SD: --g-x---` | `SD: 1&:g` |
| `f` / `F` | flam (met accent) | voorslag met streepje | `SD: f-------` | `SD: 1:f` |
| `d` / `D` | drag (met accent) | twee voorslagen | `SD: d-------` | `SD: 1:d` |
| `r` | ruff / 4-stroke ruff | drie voorslagen | `SD: r-------` | `SD: 1:r` |
| `z` / `Z` | buzz roll / press (met accent) | Z op de stok | `SD: z-------` | `SD: 4:z` |
| `t` / `T` | roffel (met accent) | drie streepjes door de stok | `SD: t-------` | `SD: 4:t` |
| `o` / `O` | open (met accent) | rondje boven de noot; op `HH` wordt het de open hi-hat | `HH: x-x-x-o-` | `HH: 4&:o` |
| `h` | half open hi-hat | half rondje | `HH: h-h-h-h-` | `HH: *8:h` |
| `+` | dicht (na open hi-hat) | plusje | `HH: o-+-` | `HH: 1:o 1&:+` |
| `c` | cross stick (in de snare-rij) | kruisje op de snare | `SD: ----c---` | `SD: 2:c` |
| `@` | rimshot (in de snare-rij; op een tom: omcirkelde kop) | omcirkeld kruis | `SD: ----@---` | `SD: 2:@` |
| `b` / `B` | bell (in de ride-rij wordt het `RB`; anders ruitvormige kop) | ruit | `RD: b-x-b-x-` | `RD: 1:b` |
| `k` / `K` | choke: bekken direct afknijpen (met accent) | komma na de noot | `CR: k-------` | `CR: 1:k` |
| `-` `.` `_` | niets | | | |

Combinaties in telnotatie: `2:Xf` (flam met accent), `1:Xk` (crash, accent, choke), `4&:Oz`, enz.

> **Let op MuseScore-versies:** open (`o`), half open (`h`), buzz (`z`) en de %-herhaalmaten worden
> door MuseScore 4 goed weergegeven. Oudere versies (3.x) laten sommige tekens of de %-tekens weg.

### 4.7 Sticking (R/L)

Een rij `ST` (of `STICKING`) zet tekst onder de noten:

```
groove paradiddle:
  SD: *16 1:X 2:X 3:X 4:X
  ST: RLRRLRLLRLRRLRLL          raster: elk teken is één sticking
```

```
groove fill16:
  SD: 4 4e 4& 4a
  ST: 4:R 4e:L 4&:R 4a:R       tellen: tekst na de dubbele punt
```

Elk teken mag: `R`, `L`, `B` (beide), `K` (kick), `r`/`l` (zacht), ...
In telnotatie mag de tekst langer zijn: `1:RL`.

### 4.8 Triolen, kwintolen en andere verdelingen

Drumsheetz schrijft automatisch de juiste notatie (met haak en getal). Je hoeft alleen te zeggen
wáár de slagen vallen. Alle manieren:

```
HH: xxxxxxxxxxxx            12 tekens in 4/4: 8ste triolen over de hele maat
HH: *8t                     hetzelfde in telnotatie
SD: 4 4t 4l                 triool op tel 4
HH: x-x-|xxx|x-x-|x-x-      alleen tel 2 een triool
SD: xxxxx|x-|x-|x-          kwintool op tel 1
SD: 1 1+2/3 2+1/3           kwartnoot-triolen (over twee tellen)
T1: 4 4+1/6 4+2/6 4+3/6 4+4/6 4+5/6   sextool op tel 4
HH: x-x-x-x-|xxx|xxx         7 tekens? Gebruik liever stukken met |
```

Hoe het werkt: per tel (in 6/8 per gepunteerde kwart) kijkt het programma welke verdeling nodig is.
Valt alles op een 8ste/16de/32ste-raster, dan gewone noten. Anders een tuplet: 3 (triool), 5
(kwintool), 6 (sextool), 7 (septool), … Kwartnoot-triolen over twee tellen worden herkend en als
één haak geschreven.

Wil je in 4/4 een **shuffle** of **swing** schrijven, dan zijn er twee manieren:

1. Echt als triolen: `HH: *4 *l` (de ingebouwde `shuffle`) — zo staat het op het blad.
2. Gewone 8sten schrijven en `swing: ja` in de kop: het blad krijgt "Swing" bij de stijl en de MIDI swingt.

### 4.9 Patronen van meer maten

```
groove bossa:
  maten: 2
  HH: *8                      geldt voor beide maten
  XS: 1 2& 4 || 2& 4          || = volgende maat
  BD: 1 2& 3 4&
```

Of in raster: zonder `||` wordt een lange rij gelijk verdeeld over het aantal `maten`:

```
groove clave:
  maten: 2
  XS: x--x--x---x-x-------x-x---x--x--    (32 tekens = 2 maten 16den)
```

Een rij met minder maten dan het patroon wordt herhaald (handig voor de hi-hat).

Op het blad: een patroon van **2 of 4 maten** wordt geschreven als de maten zelf, gevolgd door een
**2-maats (of 4-maats) %-teken** met "N×" erboven.

### 4.10 Patronen afleiden en aanpassen

Maak een variant van een bestaand patroon (eigen of uit de bibliotheek) met `= basis`. Alleen de
rijen die je noemt veranderen:

```
groove couplet:
  HH: *8
  SD: 2 4
  BD: 1 3 3&

groove refrein = couplet:     zelfde snare en bassdrum ...
  HH: -                       ... hi-hat eruit (- of 'weg')
  RD: *8 *4:b                 ... ride erin, bell op de tellen

groove mijnfunk = funk:       variant op de ingebouwde funk
  BD: 1 1& 3 3a
```

### 4.11 De opbouw: secties en regels

Een **sectie** begint met de naam tussen vierkante haken; die naam komt in het kader op het blad.
Daaronder (of er direct achter) komen **regels** van de vorm

```
aantal  patroon  opties...
```

```
[Intro] 4 rock crash fill sd4            sectie met één regel, op dezelfde regel

[Couplet 1]                              sectie met meerdere regels
  8 rock mf
  7 rock2
  1 rock fill tom34

[]  8 rock                               sectie zonder kader
```

- `8x` of `8 maten` mag ook in plaats van `8`.
- Laat je het patroon weg, dan wordt het vorige patroon gebruikt: `8 crash` = nog 8 maten hetzelfde, met crash.
- Een sectie begint op het blad op een **nieuwe regel** (net als vroeger), tenzij je `layout: doorlopend` gebruikt.
- Na elke sectie komt een dubbele maatstreep, aan het eind een slotstreep.

Alle **opties**, op een regel of achter de sectienaam:

| Optie | Betekenis |
|---|---|
| `crash` | crash op tel 1 van de eerste maat (vervangt de hi-hat/ride op die tel) |
| `crash=CR2`, `china`, `splash`, `crash2`, `stack` | ander bekken op tel 1 |
| `fill naam` (of `fill=naam`) | fill in de laatste maat |
| `fill a,b` | fills in de laatste twee maten |
| `ppp` `pp` `p` `mp` `mf` `f` `ff` `fff` `sfz` `sf` `fp` `sfp` `rfz` | dynamiek |
| `cresc` (of `<`) / `dim` (of `>`, `decresc`) | vork over deze regel |
| `p<f`, `f>p`, `cresc p-f`, `dim=f-pp` | vork van de ene naar de andere letter |
| `"tekst"` | cursieve tekst boven de eerste maat |
| `klein`, `normaal`, `groot`, `heelklein`, `heelgroot`, `grootte=7` | grootte van de tekst op deze regel (of sectie) |
| `tempo=120`, `tempo 120`, `tempo=4.=60` | nieuw tempo (metronoomteken) |
| `rit` `rall` `accel` `a-tempo` `tempo-primo` | tempotekst |
| `halftime`, `doubletime` | groove op halve/dubbele snelheid, met tekst (zie hieronder) |
| `fermata` | fermate op het laatste slag van de laatste maat |
| `maat=7/8`, `maat=7/8(2+2+3)` | maatwissel (blijft gelden tot de volgende) |
| `uitgeschreven` | geen %-maten: elke maat uitschrijven |
| `herhaal 2` (of `2x` achter een sectienaam) | herhaaltekens, N keer spelen |
| `volta 1`, `volta 2`, `volta 1,2` | 1e/2e eindigt (volta's) |
| `segno`, `coda` | teken aan het begin |
| `fine`, `naar-coda`, `ds`, `ds-al-coda`, `ds-al-fine`, `dc`, `dc-al-coda`, `dc-al-fine` | aan het eind |
| `nieuweregel` / `nieuwepagina` | forceer een nieuwe regel / pagina |
| `doorlopen` | (achter een sectienaam) deze sectie niet op een nieuwe regel beginnen |
| `einde` | slotstreep na deze sectie |

**Tekstgrootte.** Teksten tussen aanhalingstekens (korte lyrics, aanwijzingen) krijgen de grootte uit
`tekstgrootte:` (kop van het nummer, anders `instellingen.txt`). Per regel kun je dat overrulen:

```
tekstgrootte: klein                      in de kop: alle teksten in dit nummer klein

[Intro] 8 tacet "We're going down..." groot    deze tekst groot
[Couplet]
  8 rock "Like a tide..." grootte=7      7 punten
  8 rock "1. I know a place..." normaal  normale grootte
```

Patroonnamen die ook een optie zijn (zoals `p`, `f`, `fill`, `coda`) kun je beter vermijden.

### 4.12 Crash en fills

**Crash** zet een crash op tel 1 van de eerste maat van de regel en haalt daar de hi-hat/ride weg:

```
[Refrein] 8 rock crash
[Refrein] 8 rock crash=CR2       andere crash
[Refrein] 8 rock china
```

**Fill** vervangt het eind van de **laatste maat**: alles van de groove vóór de eerste handslag van
de fill blijft staan, vanaf daar speel je de fill.

```
fill mijnfill:
  SD: 4 4e 4& 4a                 fill begint op tel 4 → tel 1-3 blijft gewoon groove
```

- Heeft de fill **geen voeten** (`BD`, `HF`, …), dan loopt de bassdrum van de groove gewoon door.
- Heeft de fill wél een `BD`-rij, dan bepaalt de fill de bassdrum vanaf het begin van de fill.
- Begint de fill op tel 1, dan is de hele maat fill (bv. `tomfull`).
- Twee fills achter elkaar: `fill opbouw,tomfull` (voorlaatste en laatste maat).
- Een fill van 2 maten (`maten: 2`) vult vanzelf de laatste twee maten.

Op het blad zie je dus: groove — % N× — fill. Precies zoals de oude sheets.

### 4.13 Dynamiek en crescendo

```
[Couplet] 16 rock mp
[Brug]
  4 halftime p cresc            vork over deze 4 maten
  4 halftime f
[Outro] 8 rock ff dim
```

**Van welke letter naar welke letter.** Geef begin en eind van de vork aan; de beginletter komt
aan het begin, de eindletter op de eerste tel ná de vork:

```
  4 rock p<f                    crescendo van p naar f
  4 rock f>p                    diminuendo van f naar p
  4 rock cresc p-ff             zelfde, andere schrijfwijze
  4 rock cresc=mp-f
  4 rock dim ff-pp
  4 rock mp cresc -f            alleen de eindletter (begin = mp)
```

Heeft de regel ná de vork zelf een dynamiekteken, dan wint dat. Staat de vork aan het eind van het
nummer, dan komt de eindletter aan het eind van de laatste maat. In de MIDI wordt het per maat
geleidelijk harder of zachter.

**Boven of onder de balk.** Vorken (en de letters die erbij horen) staan standaard **onder** de
balk, losse dynamiektekens (`mf`) standaard boven. Aan te passen in `instellingen.txt` of in de kop:

```
vorken: onder        # of boven
dynamiek: boven      # of onder (losse letters)
```

Dynamiek telt ook mee in de MIDI (zachter/harder).

### 4.14 Tempo, tempowisselingen en fermate

```
tempo: 92                       kop: begintempo (in 6/8 = gepunteerde kwart)
tempo: 4=92                     expliciet: kwart = 92
tempo: 8=210                    achtste = 210 (bv. voor 7/8)

[Brug] tempo=80                 nieuw tempo voor de hele sectie
  8 halftime
[Outro]
  4 rock rit                    "rit." boven de maat
  1 hit fermata                 fermate op het laatste slag
```

### Halftime en doubletime

Speel een groove in **halftime** of **doubletime** zonder hem opnieuw uit te schrijven:

```
[Brug] 8 rock halftime         snare op 3, bassdrum op halve snelheid, met "Half time" erboven
[Solo] 8 rock doubletime       snare op elke &, bassdrum op elke tel, met "Double time" erboven
```

Wat er gebeurt: **snare, toms, clap en bassdrum** gaan op halve (of dubbele) snelheid; **bekkens,
hi-hat en hi-hat-voet blijven gelijk**. Bij halftime wordt de eerste helft van de maat over een hele
maat uitgerekt en de tweede helft over de volgende maat (een groove van 1 maat wordt er dus 2). Bij
doubletime wordt de maat in de helft van de tijd gespeeld, twee keer per maat.

| Groove | Normaal | `halftime` | `doubletime` |
|---|---|---|---|
| `rock` | SD 2 4 · BD 1 3 | SD 3 · BD 1 | SD op elke & · BD op elke tel |

Werkt met alle grooves (ook je eigen), fills blijven gewoon zoals ze zijn. Wil je alleen de tekst
zonder dat de groove verandert, gebruik dan `halftime-tekst` of `doubletime-tekst`. (De ingebouwde
groove die `halftime` heet gebruik je zoals altijd: `8 halftime`.)

### 4.15 Maatsoorten en maatwisselingen

- Standaard 4/4; zet `maat:` in de kop voor iets anders: `maat: 6/8`, `maat: 5/4`, `maat: 7/8 (2+2+3)`.
- De groepering tussen haakjes bepaalt hoe rusten en tellen worden ingedeeld (op het blad staat gewoon 7/8).
- Wisselen kan per sectie of regel met `maat=...`; dat blijft gelden tot de volgende wissel:

```
[Brug] maat=7/8
  4 rock78
[Refrein] maat=4/4
  8 rock
```

- Een patroon met een eigen `maat:` (bv. de ingebouwde `wals` in 3/4) zet die maat(en) vanzelf in
  die maatsoort, zonder de rest van het nummer te veranderen.
- In de telnotatie is een tel de noemer: in 6/8 tel je 1 t/m 6, in 7/8 1 t/m 7.

### 4.16 Herhalingen: %, herhaaltekens en volta's

**%-maten (automatisch).** Opeenvolgende gelijke maten binnen een regel worden één %-maat met
"N×" erboven, en de maatnummers tellen gewoon door. Een crash op de eerste maat telt niet als
verschil (net als vroeger). Wil je dat niet:

```
[Solo] 8 funk uitgeschreven       deze regel volledig uitschrijven
herhaaltekens: nee                (in de kop) nergens %-maten
```

**Herhaaltekens** (`|: … :|`):

```
[Couplet] herhaal 2               hele sectie tussen herhaaltekens
  8 rock
  8 rock2 fill sd4

[Riff]
  2 funk herhaal 4                alleen deze regel, "4×" bij het herhaalteken
```

**Volta's** (1e en 2e eindigt):

```
[Refrein]
  6 rock
  2 rock volta 1 fill sd4         1e keer
  2 rock volta 2 fill tomfull     2e keer
```

Er komt automatisch een herhaalteken aan het begin van de sectie. Bij `volta 1,2` en `volta 3`
wordt het stuk drie keer gespeeld. In de MIDI en de duurberekening worden alle herhalingen
uitgerold.

### 4.17 Segno, Coda, D.S., D.C. en Fine

```
[Couplet] segno
  8 rock
[Refrein]
  6 rock
  2 rock naar-coda                "To Coda" + codateken aan het eind
[Brug] 8 halftime ds-al-coda      "D.S. al Coda" aan het eind
[Coda] coda                       codateken aan het begin
  4 rock
  1 hit fermata
```

Mogelijk: `segno`, `coda` (begin) en `fine`, `naar-coda`, `ds`, `ds-al-coda`, `ds-al-fine`, `dc`,
`dc-al-coda`, `dc-al-fine` (eind). Let op: in de MIDI worden sprongen (D.S./D.C.) niet gevolgd.

### 4.18 Rust, vrij spelen en ensemble-hits

```
[Intro] 8 tacet "piano solo"      rustmaten (één balk met "8")
[Intro] 8 -                       hetzelfde; ook: rust, stil, pauze
[Solo] 16 tijd "gitaarsolo · vrij spelen"   ritme-slashes (/ / / /), zonder stokken
[Solo] 16 vrij                    hetzelfde (ook: time, slash, /)
```

**Ensemble-hits** (de figuren die de band samen speelt) met de `SL`-rij: slashes mét stokken,
op de middelste lijn, die je kunt combineren met gewone noten:

```
groove hits:
  SL: 1 2& 4:X
  CR: 1 2& 4
  BD: 1 2& 4
```

**Stops**: de ingebouwde `hit`/`stop` (crash + bassdrum op 1), `hitsd` (met snare) en `choke`
(crash direct afgeknepen).

### 4.19 Patronen direct in de regel

Voor een eenmalige maat hoef je geen patroon te maken: zet het tussen accolades, rijen gescheiden
door `;`:

```
[Break]
  1 {SD: *16 4:X; BD: 1}
  1 {CR: 1; BD: 1; basis: rock}         'basis:' werkt ook hier
```

### 4.20 Opmaak: regels en pagina's

- Standaard begint elke sectie op een nieuwe regel (zoals de oude sheets).
- `layout: doorlopend` in de kop: alles achter elkaar, MuseScore verdeelt zelf.
- `maten-per-regel: 4` in de kop: na elke 4 geschreven maten een nieuwe regel.
- `nieuweregel` of `nieuwepagina` op een regel; `doorlopen` achter een sectienaam.
- De extra ruimte tussen de regels (zodat dynamiek bij de bovenste balk hoort) staat in
  `instellingen.txt` als `regelafstand: 12`.

### 4.21 Aftellen

```
aftellen: 1          in de kop
```

Zet één (of meer) maten met tikkende stokken (`CK`) op elke tel vóór het nummer, met de tekst
"aftellen", en ze tellen mee in de MIDI. In 6/8 tikt het op 1 en 4. Alleen in de MIDI aftellen
kan ook: `python3 drums.py midi letlove --aftellen 2`.

### 4.22 Eigen instrumenten en notenbalkposities

Werkt jouw docent of jouw boek met een andere notatie? Pas het per nummer aan (of voor alles, in
`bibliotheek.drum`):

```
instrument CB: E6 triangle 56 "cowbell"          cowbell op E6 met driehoekskop
instrument PAD: A5 square 39 "sample pad"        nieuw instrument
instrument KICK3: E4 normal 35 voet               nieuw voetinstrument (stok omlaag)
```

Volgorde: plek (`C5`, `F4`, `G5`, …), nootkop, MIDI-nummer, naam tussen aanhalingstekens, en
`voet` voor stok omlaag. Nootkoppen: `normal`, `x`, `circle-x`, `diamond`, `triangle`, `slash`,
`cross`, `square` (of Nederlands: `normaal`, `kruis`, `rondje-kruis`, `ruit`, `driehoek`, `vierkant`, `plus`).

### 4.23 Commentaar

Alles na `#` is commentaar (behalve binnen "aanhalingstekens"):

```
groove a:          # het couplet
  HH: *8           # licht spelen
```

---

## 5. De bibliotheek

Deze patronen kun je overal bij naam gebruiken. Bekijk ze met `python3 drums.py bibliotheek`
(of als PDF: `python3 drums.py bibliotheek --pdf`).

**Grooves 4/4**

| Naam | Omschrijving |
|---|---|
| `rock` | basis rockbeat in 8sten |
| `rock2` | rock met extra bassdrum op 3& |
| `rock16` | rock met 16den op de hi-hat |
| `rockride` | rock op de ride |
| `rockopen` | rock met halfopen hi-hat |
| `kwart` | hi-hat in kwarten |
| `pop` | popbeat met syncope (BD 1 2& 3) |
| `ballad` | ballad met cross stick |
| `ballad16` | ballad met 16den en cross stick |
| `halftime` | snare op 3 |
| `doubletime` | snare op elke & |
| `disco` | BD op elke tel, open hi-hat op de & |
| `fotf` | four on the floor (house) met clap |
| `motown` | snare op alle tellen, accent op 2 en 4 |
| `funk` | 16den-funk met ghost notes |
| `funk8` | funk in 8sten met accent-hi-hat |
| `hiphop` | boom-bap |
| `shuffle` | shuffle (triolen) |
| `halftimeshuffle` | half-time shuffle met ghosts |
| `swing` | jazz-swing op de ride, hi-hat voet op 2 en 4 |
| `triool` | 8ste triolen op de hi-hat |
| `train` | trein-beat (snare 16den, accent 2 en 4) |
| `punk` | BD op de tel, SD op de & |
| `blast` | hammer blast |
| `metal` | dubbele bassdrum in 16den |
| `onedrop` / `steppers` / `rockers` | reggae |
| `bossa` | bossa nova (2 maten) |
| `samba` | samba |
| `jungle` | tom-groove |

**Grooves andere maatsoorten:** `ballad68`, `rock68` (6/8), `blues128` (12/8), `wals`,
`jazzwals` (3/4), `rock54` (5/4), `rock78` (7/8).

**Fills 4/4**

| Naam | Omschrijving |
|---|---|
| `sd4` | 16den op de snare op tel 4 |
| `pick8` | 8sten-oppikker op 4 en 4& |
| `bal4` | snare op 4, floor tom op 4& |
| `tom34` | dalend over de toms, tel 3-4 |
| `sd34` | snare 16den over 3-4 met accenten |
| `tomfull` | hele maat rond de toms |
| `soft4` | zachte ballad-oppikker (cross stick + floor tom) |
| `sd16` | hele maat 16den op de snare |
| `sd8` | hele maat 8sten op de snare |
| `trip4` | snare-triool op tel 4 |
| `trip34` | triolen over 3-4: snare, tom, floor |
| `tom4` | toms op tel 4 |
| `flam4` | flams op 4 en 4& |
| `lin4` | lineaire fill op tel 4 |
| `crash4` | crash + BD op 4& (anticipatie) |
| `opbouw` | 8sten naar 16den (opbouw naar refrein) |

**Fills andere maatsoorten:** `trip68`, `tom68` (6/8), `fill128` (12/8).

**Slotslagen:** `hit`, `stop`, `hitsd`, `choke`.

### Eigen bibliotheek

Zet grooves en fills die je vaker gebruikt in **`bibliotheek.drum`** in de hoofdmap. Ze zijn dan in
elk nummer bruikbaar. Een patroon met dezelfde naam als een ingebouwd patroon vervangt het
ingebouwde; een patroon in een nummer zelf gaat weer vóór de bibliotheek.

```
# bibliotheek.drum
groove purdie:
  info: Purdie shuffle
  HH: *4 *l
  SD: 3 1t:g 1l:g 2t:g 2l:g 3l:g 4t:g 4l:g
  BD: 1 2l 3l
```

---

## 6. Setlists

Een setlist is een tekstbestand in `setlists/`, bijvoorbeeld `setlists/bruiloft.txt`:

```
titel: Bruiloft Anna & Tom
datum: 12 juni 2026
plaats: De Boerderij, Utrecht
band: De Huisband
notitie: In-ears mee!

[Set 1]
always                       | rustig beginnen, brushes
crime
Iedereen is van de wereld    | lang uitspelen
archief/pdf-gekocht/Somebody-To-Love_Queen.pdf = Queen - Somebody To Love [4:56]

[Pauze 20 min]

[Set 2]
letlove                      | segue naar volgende
annihilator [5:10]
```

- **Elke regel is een nummer**: id, titel of een stuk ervan (zoals overal).
- `| tekst` = notitie (komt op het voorblad).
- `[4:56]` = duur (anders berekend uit maten × tempo, of uit `duur:` in het nummer).
- **Gekochte/andere PDF's**: geef het pad naar het `.pdf`-bestand, eventueel met `= Artiest - Titel`.
  Of zet in een nummer `pdf: pad/naar/bestand.pdf` om die PDF te gebruiken in plaats van de eigen sheet.
- `[Naam]` of `--- Naam ---` = een tussenkop (Set 1, Pauze, Toegift, …), met subtotaal per set.
- `#` = commentaar.

**Opdrachten:**

```bash
python3 drums.py setlist nieuw bruiloft always crime letlove   # nieuwe setlist
python3 drums.py setlist toon bruiloft                         # overzicht + duur in de terminal
python3 drums.py setlist maak bruiloft                         # alles maken
python3 drums.py setlist lijst                                 # alle setlists
```

`setlist maak` maakt eerst de PDF's van alle nummers die nog niet bestaan of veranderd zijn, en
dan in `uitvoer/setlists/`:

| Bestand | Wat |
|---|---|
| `bruiloft/01 Dolly Parton - I Will Always Love You.pdf`, `02 …` | genummerde losse PDF's (zoals de oude map `set/`) |
| `bruiloft - compleet.pdf` | één boek: voorblad + alle sheets, met **bladwijzers** per nummer (handig op de iPad) |
| `bruiloft - overzicht.pdf` | voorblad: #, titel, artiest, tempo, maatsoort, duur, notitie, subtotalen, totaal |
| `bruiloft - podium.pdf` | één pagina met **grote letters** om op de grond te leggen, met tempo's |
| `bruiloft.md` | hetzelfde overzicht als tekst |

Voor `compleet`, `overzicht` en `podium` is `pip3 install pypdf reportlab` nodig; de rest werkt altijd.

Een voorbeeld staat in `setlists/voorbeeld.txt` (de volgorde van de oude map `archief/set/`).

---

## 7. Versies en forScore op de iPad

### Versiebeheer

Elk nummer heeft versies: **V1, V2, V3, …** Een versie is een vaste momentopname van het nummer (de
`.drum`-tekst én de PDF), bewaard in de map `versies/`. In forScore is elke versie een **eigen stuk**:
"Lean on Me - Bill Withers **V2**". Zo wordt er in forScore nooit iets overschreven: je aantekeningen
met de Apple Pencil op V1 blijven gewoon op V1 staan.

**Hoe ontstaat een versie?**

- Automatisch bij **⇅ forScore**: is het nummer *muzikaal* veranderd sinds de vorige versie, dan wordt
  het de volgende versie en gaat het als nieuw stuk naar forScore.
- Zelf, met **Nieuwe versie** in het tabblad *Versies* (of `drums.py versies letlove --nieuw "notitie"`).
  Handig als je een tussenstand wilt vastleggen, met een notitie erbij.

**Wat telt als verandering?** Alles wat op het blad komt (tempo, patronen, opbouw, teksten, ...).
Wat alleen voor forScore is telt **niet**: `labels:`, `genre:`, `tags:`, `waardering:`,
`moeilijkheid:`, `referentie:`, `forscore-naam:`, en ook geen extra spaties of lege regels.

**Het tabblad Versies** (rechts in de Studio) laat voor het open nummer zien:

| Onderdeel | Wat |
|---|---|
| Bovenaan | "Het nummer is gelijk aan V3", of "Gewijzigd sinds V3: wordt V4" met wat er veranderd is (bv. *+2 −1 regels: deel Refrein*). |
| **Nieuwe versie** | Leg nu een versie vast (met PDF). Typ eventueel eerst een notitie. |
| Per versie | Datum, notitie (klik erop om hem te veranderen), wat er veranderd was, en de naam in forScore. |
| **Verschil met nu** | Laat regel voor regel zien wat er sinds die versie veranderd is (rood weg, groen erbij). |
| **PDF** | Open de PDF van die versie, precies zoals hij toen was. |
| **Terugzetten** | Zet die versie terug in het nummer. Wat er stond wordt eerst als **reservekopie** bewaard. |
| **Reservekopieën** | Onderaan: wat er stond vóór elk terugzetten. Ook die kun je terugzetten. |

**Terugzetten is veilig.** De geschiedenis loopt altijd door: zet je V1 terug terwijl je al op V3
zat, dan wordt het bij de volgende ⇅ forScore **V4 (= V1)**. Staat V1 nog in forScore, dan wordt
dat stuk gewoon weer gebruikt (met je aantekeningen), en er komt niets dubbel in.

**In de boom** staat achter elk nummer zijn versie: `V3`, of `V3*` (oranje) als het sindsdien
gewijzigd is. Op het blad zelf staat linksboven **Versie V3**, zodat je op papier ook ziet welke
versie het is (uitzetten: `versie-op-blad: nee` in `instellingen.txt`).

**Waterdicht:**

- Versiebestanden zijn alleen-lezen en hebben een controlesom. `drums.py versies --controleer` (of het
  tabblad Versies) meldt het als er iets ontbreekt of is veranderd. Drumsheetz gooit nooit een versie weg.
- Hernoem of verplaats je een nummer in de Studio, dan gaat de geschiedenis mee. Doe je het buiten de
  Studio om (Finder), dan wordt de geschiedenis teruggevonden aan de inhoud of aan titel + artiest.
- Setlists hebben ook versies (zie hieronder).
- `versies/` is jouw geschiedenis: gooi die map niet weg en neem hem mee in je back-up (Time Machine).
  `uitvoer/` mag je altijd weggooien; `versies/` niet.

### forScore

Je maakt de nummers op de Mac; Drumsheetz zet ze in **forScore voor Mac**, en de
**iCloud-synchronisatie** van forScore zet ze op je iPad.

### Eenmalig instellen

1. Installeer **forScore voor Mac** (Mac App Store, zelfde Apple-ID als op de iPad) en open hem één keer.
2. Zet in forScore op de Mac én op de iPad **Sync with iCloud** aan (menu → Sync with iCloud).
3. `pip3 install pypdf` (voor titel en componist in de PDF).
4. Draai één keer de **zelftest** (zie hieronder). macOS vraagt misschien of de Terminal "gegevens van
   andere apps" mag lezen: sta dat toe. Daarmee kan Drumsheetz in de forScore-bibliotheek **kijken**
   (alleen lezen) of alles echt is aangekomen.

### Hoe het werkt

Er is maar **één boom**: je gewone Drumsheetz-mappen in `nummers/`. forScore volgt die.

- **De map is het label.** `nummers/Hatikwa/The River.drum` krijgt in forScore het label *Hatikwa*.
  Submappen geven meerdere labels (`Kerk/Kerst/…` → *Kerk* en *Kerst*). Mappen die met `_` beginnen
  (geparkeerd) gaan niet naar forScore. Wil je nog een label erbij, zet dan `labels: …` in het nummer.
- **Eén knop: ⇅ forScore** (in de Studio, rechtsboven) of `python3 drums.py forscore` in de Terminal.
  Die maakt forScore gelijk aan Drumsheetz: PDF's maken waar nodig, nieuwe nummers erin (V1),
  gewijzigde nummers als nieuwe versie erin (V2, V3, …), setlists erin. Het getal op de knop is hoeveel
  er nog moet. Voor hij begint zegt hij wat hij gaat doen.

forScore blijft de baas over je bibliotheek: **stukken die al in forScore staan worden nooit
aangeraakt** (niet overschreven, niet verplaatst, geen labels veranderd). Er komen alleen nieuwe
stukken en nieuwe setlists bij. Drumsheetz **kijkt** in de forScore-bibliotheek op je Mac
(alleen lezen) en stuurt bestanden die forScore zelf importeert. Wat daardoor niet automatisch kan,
krijg je na het synchroniseren als korte lijst **"Zelf doen in forScore"** in het Log.

| Wat | Hoe |
|---|---|
| **Herkennen** | Een nummer hoort bij een stuk in forScore als de bestandsnaam klopt ("Titel - Artiest.pdf"), óf als de **titel** gelijk is en de componist niet tegenspreekt. Ook stukken die je zelf in forScore hebt gezet, of die er onder een andere naam in staan, worden herkend. Twee nummers met dezelfde titel maar een andere artiest worden niet door elkaar gehaald. |
| **Stond al in forScore** | Een nummer dat al in forScore stond voordat er versies waren (bv. "The River.pdf"), wordt **V1**: er wordt niets verstuurd en er komt niets dubbel in. Pas als je het nummer verandert komt er "The River - Artiest V2" bij. |
| **Nieuw nummer** | Gaat als V1 (`.4sc`: PDF + titel "Titel V1", componist, **map als label**, genre, trefwoorden; zolang de zelftest dat niet heeft bevestigd als PDF). Daarna wordt gecontroleerd of het er staat. |
| **Gewijzigd nummer** | Wordt de volgende versie en gaat als **nieuw stuk** naar forScore ("… V2"), met de labels van de map. De oude versie blijft staan met je aantekeningen. |
| **Oude versies** | Na het synchroniseren zie je in het Log welke oude versies nog in forScore staan. Die mag je weggooien zodra je je aantekeningen hebt overgezet; het hoeft niet. |
| **Nummer naar andere map verplaatst** | forScore laat zijn labels niet van buitenaf veranderen. Je krijgt de taak "label toevoegen: … / label weghalen: …" en in de boom een ⚑ achter het nummer tot het klopt. |
| **Setlists** | Een setlist gebruikt altijd de **nieuwste versie** van elk nummer. Eerst gaan de stukken die nog ontbreken, dan de setlist (**Open Setlist**, "Bruiloft V1"), en er wordt gecontroleerd of hij **compleet** is. |
| **Gewijzigde setlist** | Verandert de setlist, of komt er van een nummer erin een nieuwe versie, dan gaat er een nieuwe setlist naar forScore: "Bruiloft V2". De oude blijft staan (mag weg). Een setlist die al in forScore stond (zonder V) wordt V1. |
| **Losse PDF's in een setlist** | Een gekochte PDF (`gekocht/song.pdf = Artiest - Titel`) wordt in forScore gezocht op bestandsnaam én op titel. Staat hij er al (ook onder een andere naam), dan wordt die gebruikt en niets verstuurd. Eén keer gevonden = onthouden. |
| **Dubbelen** | Staat een stuk twee keer in forScore (bv. "Naam 2.pdf"), dan zie je ⚠ in de boom en een taak om de kopie weg te gooien (meestal die zonder labels). |

**Bolletjes in de boom** (achter elk nummer en elke setlist): groen = actueel in forScore,
blauw = nog niet in forScore, oranje = gewijzigd (wordt een nieuwe versie bij de volgende ⇅).
Houd de muis erop voor de naam in forScore. ⚑ = labels kloppen niet met de map, ⚠ = dubbel in forScore.

**Blijft forScore hangen** op "Loading… 0 of 1 files imported"? Drumsheetz stuurt de bestanden één
voor één en wacht na elk bestand tot het echt in forScore staat. Komt een bestand er na 45 seconden niet
in, dan stopt hij en zegt hij welk bestand het was. Klik in forScore op **Cancel** (of beantwoord de
vraag die soms achter een ander venster staat); de rest gaat mee met de volgende ⇅ forScore. Blijft
forScore twee keer op dezelfde losse PDF hangen, dan probeert Drumsheetz het niet meer: sleep dat
bestand dan zelf in forScore, daarna wordt het vanzelf herkend.

**Kan forScore niet gelezen worden** (bv. geen toestemming), dan stuurt Drumsheetz geen nummers die nog
nooit verstuurd zijn: hij kan dan niet zien of ze er al in staan, en maakt liever geen dubbele.

### Opdrachten

```bash
python3 drums.py forscore                     # alles gelijk maken (nummers, versies én setlists)
python3 drums.py forscore "The River"         # alleen één nummer
python3 drums.py forscore "The River" --notitie "nieuwe brug"   # met notitie bij de nieuwe versie
python3 drums.py forscore --setlist bruiloft  # alleen een setlist (met de stukken die nog ontbreken)
python3 drums.py forscore --labels-ophalen    # labels die je in forScore extra gaf → 'labels:' (eerst bekijken)
python3 drums.py forscore --labels-ophalen --toepassen
python3 drums.py forscore --zelftest          # alles één keer uitproberen, met rapport
python3 drums.py forscore --onderzoek         # wat er in de forScore-database herkend wordt
```

**Zelftest:** stuurt een test-PDF, een test-`.4sc` en een testsetlist (alle drie "Drumsheetz
zelftest"), controleert per stap of ze in forScore verschijnen, en schrijft een rapport naar
`uitvoer/forscore-zelftest.txt`. Gooi de teststukken en de testsetlist daarna in forScore weg.

### Waarom niet via OneDrive of Dropbox?

forScore kan PDF's uit OneDrive/Dropbox/Google Drive **importeren**, maar maakt daar een eigen kopie
van: het houdt die map niet in de gaten, ziet geen wijzigingen en maakt van mappen geen labels. Je
zou dus alsnog alles met de hand opnieuw importeren en labelen. De weg via forScore op de Mac +
iCloud-sync doet dat wel automatisch, inclusief labels, titels en setlists.

De koppeling wordt getest tegen een nagemaakte forScore met dezelfde database en hetzelfde gedrag als
de echte (`python3 -m unittest discover -s tests`).

---

## 8. MIDI: oefenen met een meespeelbestand

```bash
python3 drums.py midi letlove                     # uitvoer/midi/letlove.mid
python3 drums.py midi letlove --tempo 80          # op 80% van het tempo (letlove-80pct.mid)
python3 drums.py midi letlove --klik --aftellen 2 # met metronoom en 2 maten aftellen
python3 drums.py maak --midi                      # bij het maken van de PDF's ook MIDI
```

De MIDI speelt alles uit wat op het blad staat: alle %-maten en herhalingen uitgeschreven,
volta's in de goede volgorde, tempowisselingen, dynamiek (pp…ff), accenten, ghost notes, flams,
drags, roffels/buzz, open hi-hat, en swing (`swing: ja`). Open het in GarageBand, Logic, MuseScore,
een DAW of een MIDI-speler op je telefoon. Sprongen (D.S./D.C.) worden niet gevolgd.

---

## 9. Archief

Alles van vóór deze versie staat in `archief/`, ongewijzigd:

| Map | Inhoud |
|---|---|
| `archief/songs/` | de oude Python-nummers (bron van de huidige `nummers/*.drum`) |
| `archief/oud/` | oudere handgeschreven versies (+ hun PDF's en MuseScore-bestanden) |
| `archief/pdf/`, `archief/mscz/`, `archief/xml/` | de oude uitvoer |
| `archief/set/` | de oude genummerde set |
| `archief/pdf-gekocht/` | gekochte PDF's (bruikbaar in setlists) |
| `archief/mp3-downloads/` | opnames |
| `archief/make.py`, `archief/auto.py`, `archief/aankooplijst.md` | de oude scripts en aankooplijst |

Alle oude nummers zijn omgezet naar `nummers/*.drum`; ze geven exact dezelfde noten en
%-maten als de oude sheets.

**Zelf archiveren:**

```bash
python3 drums.py archiveer letlove     # nummer + uitvoer → archief/2026-11-26/
python3 drums.py herstel letlove       # kopie terug naar nummers/
```

---

## 10. Het geavanceerde Python-formaat

Het oude formaat blijft volledig werken: zet een `.py`-bestand met `SONG`, `GROOVES` en `FILLS` in
`nummers/` en het wordt gewoon gemaakt. Handig als je dingen wilt **berekenen** (lussen,
variaties genereren, uit een transcriptie). `from common import FILLS_44, HIT, SUB` werkt nog.

```python
from common import FILLS_44, SUB

SONG = {
    "title": "Let Love Rule", "artist": "Lenny Kravitz", "subtitle": SUB,
    "bpm": 90, "meter": (4, 4), "feel": "Vintage soul-rock, laid back",
    "sections": [
        {"label": "Intro", "bars": 8, "groove": "v", "crash": False, "fill": "sd4"},
        {"label": "Refrein", "bars": 8, "groove": "ch", "crash": True, "fill": "tom34",
         "dyn": "f", "wedge": "crescendo"},
        {"label": "Vamp", "text": "gospel-opbouw", "end": True, "seq": [
            {"groove": "v", "bars": 8, "crash": True, "fill": "sd4"},
            {"groove": "ch", "bars": 8, "crash": True, "volta": [1]},
            {"groove": "ch", "bars": 8, "crash": True, "volta": [2], "fermata": True},
        ]},
    ],
}

GROOVES = {
    "v":  {"HH": "x-x-x-x-x-x-x-o-", "SD": "----x-------x---", "BD": "x------xx-x-----"},
    "ch": {"HH": "*8 *&:o", "SD": "2 4", "BD": "1 2& 3"},      # telnotatie mag ook
    "bossa": {"_bars": 2, "XS": "1 2& 4 || 2& 4", "BD": "1 3"},
    "wals": {"_meter": "3/4", "HH": "*8", "SD": "2 3", "BD": "1"},
    "ch2": {"_base": "ch", "HH": "-", "RD": "*8"},                # afgeleid
}
FILLS = FILLS_44
```

**Alle sleutels** (dezelfde mogelijkheden als het `.drum`-formaat):

| In `SONG` | | In een sectie of regel (`seq`) | |
|---|---|---|---|
| `title`, `artist`, `subtitle` | titel, artiest, ondertitel | `label` | naam in het kader (alleen sectie) |
| `bpm` | tempo (getal of `"4.=60"`) | `bars` | aantal maten |
| `meter` | `(6, 8)` of `"7/8 (2+2+3)"` | `groove` | patroonnaam (`None` = rust, `"tijd"` = slashes) |
| `feel`, `notes` | cursieve regels | `fill` | naam of lijst namen |
| `by` | uitgeschreven door | `crash` | `True` of instrumentcode (`"CR2"`) |
| `countin` | maten aftellen | `dyn` | `"mf"`, … |
| `layout` | `"doorlopend"` | `wedge` | `"crescendo"` / `"diminuendo"` |
| `bars_per_line` | maten per regel | `text` | cursieve tekst |
| `compress` | `False` = geen % | `tempo`, `tempo_text` | nieuw tempo, `"rit."` |
| `swing` | `"ja"`, `"16"` | `meter` | maatwissel |
| `duration`, `pdf`, `key`, `status`, … | voor setlists | `written` | `True` = uitschrijven |
| | | `repeat` | aantal keer (herhaaltekens) |
| | | `volta` | `[1]`, `[2]`, `[1, 2]` |
| | | `marks` | `["segno"]`, `["dsalcoda"]`, `["coda"]`, `["fine"]`, `["tocoda"]`, … |
| | | `fermata`, `newline`, `newpage`, `end` | `True` |

In `GROOVES`/`FILLS`: per instrument een rij (raster of tellen), plus optioneel `_bars`, `_meter`,
`_base` en `_doc`.

**Omzetten** van oud naar nieuw (het origineel blijft staan):

```bash
python3 drums.py converteer archief/oud/stl.py              # → nummers/stl.drum
python3 drums.py converteer *.py --naar nummers --overschrijf
```

---

## 11. Automatisch transcriberen uit een opname

`tools/auto.py` maakt van een transcriptie (`result.json` + `drums.wav` uit je eigen
transcriptie-tool) een `.drum`-bestand met elke maat als eigen patroon, inclusief secties,
dynamiek en vorken:

```bash
~/drumtools/.venv/bin/python tools/auto.py watch ~/drumtools/out/watch "Watch Over You" "Alter Bridge"
```

Daarna kun je het opschonen: geef terugkerende maten een duidelijke naam, voeg crashes en fills toe.
(Heeft numpy, soundfile en librosa nodig, net als vroeger.)

---

## 12. Instellingen

`instellingen.txt` in de hoofdmap:

```
naam: Sebastiaan Johan de Vries        # wordt ingevuld waar {naam} staat
vermelding:                            # standaard-tekst rechtsboven, bv. "Drum sheet: {naam}"; leeg = niets
ondertitel:                            # standaard-ondertitel; leeg = geen
musescore: /Applications/MuseScore 4.app/Contents/MacOS/mscore   # alleen nodig als hij niet gevonden wordt
regelafstand: 12                       # ruimte tussen de regels op het blad
stemmen: 1                             # 1 = alles stok omhoog in één stem, 2 = voeten apart omlaag
herhaalteller: binnen                  # 'N×' bij een %-maat: binnen (rechts naast het %), links, of boven
accenten: boven                        # accenten en open/dicht-tekens: boven, onder of auto
vorken: onder                          # crescendo/diminuendo (met hun letters): onder of boven
dynamiek: boven                        # losse dynamiektekens (mf, p, ...): boven of onder
tekstgrootte: klein                    # teksten bij de maten: klein, normaal, groot of punten (bv. 9)
stijlgrootte: normaal                  # de stijl/notitie-regel bovenaan
versie-op-blad: ja                     # 'Versie V3' linksboven op het blad (nee = weglaten)
```

MuseScore wordt gezocht in (op volgorde): `musescore:` in de instellingen, de omgevingsvariabele
`MUSESCORE`, de standaardplekken op Mac/Windows, en `mscore`/`musescore4`/`MuseScore4.exe`/… in het PATH.

---

## 13. Foutmeldingen en tips

Fouten noemen bestand, regelnummer en vaak een suggestie:

```
✗ nummers/x.drum, regel 7: patroon 'rok' bestaat niet. Bedoel je: rock, rock2?
✗ nummers/x.drum, regel 3: onbekend instrument 'SNR'. Bedoel je: SN, SNARE?
✗ nummers/x.drum, regel 3: patroon 'a', rij BD: tel 5 valt buiten een 4/4-maat
✗ nummers/x.drum, regel 9: optie 'fil' niet begrepen Bedoel je: fill?
  ! patroon 'a', HH: rij 'x-x-x-x-x-x-x-' heeft 14 tekens; bij 4/4 verwacht je een veelvoud van 4
```

**Tips**

- Werk met `python3 drums.py toon <nummer>` terwijl je schrijft: direct zien of het klopt, zonder MuseScore.
- Of laat `python3 drums.py kijk` draaien: bij elke keer opslaan wordt de PDF opnieuw gemaakt.
- Schrijf de groove één keer, en maak varianten met `groove b = a:`.
- Gebruik telnotatie voor eenvoudige partijen (`SD: 2 4`) en raster voor drukke 16den-patronen.
- Wil je iets met de hand verschuiven: open `uitvoer/mscz/<nummer>.mscz` in MuseScore. (Let op:
  bij opnieuw maken wordt dat bestand overschreven; sla je handwerk onder een andere naam op.)
- Een nummer dat MuseScore niet lukt: `maak --xml` en open de MusicXML handmatig in MuseScore
  voor een foutmelding.
- Duur van een nummer klopt niet? Zet `duur: 4:32` in de kop.

---

## 14. Spiekbrief

```
# ---------- kop ----------
titel: …   artiest: …   tempo: 92 (of 4.=60, 8=200)   maat: 4/4, 6/8, 7/8 (2+2+3)
stemmen: 1|2   tekstgrootte: klein|groot|9   stijl: …   notitie: …   aftellen: 1   swing: ja   layout: doorlopend   maten-per-regel: 4
herhaaltekens: nee   duur: 4:32   pdf: pad.pdf   door: naam

# ---------- patronen ----------
groove naam:              fill naam:              groove b = a:  (afgeleid; 'HH: -' = weg)
  info: …   maten: 2   maat: 6/8
  HH: x-x-x-x-x-x-x-x-    raster (lengte = verdeling; | of spatie = stukken; || = volgende maat)
  SD: 2 4 3e:g            tellen: 1 1e 1& 1a 1t 1l 2.5 1+1/6
  HH: *8 4&:o !3&         *4 *8 *16 *32 *8t *16t *& *e *a *t *l  3-4*16   !weg
  ST: RLRL…               sticking
groove kort: HH *8; SD 2 4; BD 1 3

# ---------- tekens (raster of na ':') ----------
x slag   X accent   ^ marcato   g ghost   f/F flam   d/D drag   r ruff   z/Z buzz   t/T roffel
o/O open   h half open   + dicht   c cross stick   @ rimshot   b/B bell   k/K choke   - rust

# ---------- instrumenten ----------
BD BD2 HF HS | SD XS RIM CL | T1 T2 T3 FT FT2 | HH HO RD RB CR CR2 SP CH STK
CB TAMB TRI SHK CLV WB WBL AGH AGL CGH CGL BGH BGL TBH TBL | CK SL | ST

# ---------- opbouw ----------
[Naam] 8 groove opties        [Naam]           [Naam] herhaal 2 / segno / coda / "tekst"
                                8 a mf           8 crash  (zelfde groove, met crash)
                                8 b fill x       1 {SD: *16; BD: 1}  (inline)
opties: crash  crash=CR2  china  splash  fill x  fill x,y  ppp…fff sfz fp  cresc dim  p<f  f>p  cresc p-f
        halftime  doubletime
        "tekst"  klein groot grootte=7  tempo=120  rit rall accel a-tempo  fermata  maat=7/8  uitgeschreven
        herhaal 2  volta 1  volta 2  segno coda fine naar-coda ds ds-al-coda dc dc-al-fine
        nieuweregel nieuwepagina doorlopen einde
rust: tacet  -  rust          slashes: tijd  vrij  time  /

# ---------- opdrachten ----------
python3 drums.py studio            (editor in je browser)
python3 drums.py maak [-a] [--xml] [--midi] [nummers]   toon x   lijst   controleer
nieuw "Titel" "Artiest"   midi x [--tempo 80 --klik --aftellen 1]   bibliotheek [--pdf]
instrumenten   archiveer x   herstel x   converteer x.py   kijk
setlist nieuw|toon|maak|lijst naam
```
