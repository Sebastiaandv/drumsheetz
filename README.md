# Drumsheetz

Drum sheets uitschrijven in gewone tekst en er nette PDF's van maken (via MuseScore), in de
vertrouwde opmaak: elke sectie in een kader op een nieuwe regel, herhaalde maten als % met "N×".
Plus setlists, MIDI om mee te oefenen en een bibliotheek met grooves en fills.

```
titel: Mijn Nummer
artiest: De Band
tempo: 120

groove couplet:
  HH: *8 4&:o
  SD: 2 4 3e:g
  BD: 1 2& 3

[Intro]    4 couplet crash fill sd4
[Couplet]  16 couplet mf fill pick8
[Refrein]  8 rockride crash f fill tom34
[Outro]    1 hit fermata
```

```bash
python3 drums.py maak              # alle gewijzigde nummers -> uitvoer/pdf/
python3 drums.py toon <nummer>     # als drumtab in de terminal
python3 drums.py setlist maak <naam>
python3 drums.py help
```

Nodig: Python 3.8+, [MuseScore 4](https://musescore.org) (Mac/Windows/Linux, wordt automatisch
gevonden) en voor setlist-boeken optioneel `pip3 install -r requirements.txt`.

**Alles staat in [HANDLEIDING.md](HANDLEIDING.md)**: elke notatie, functie en opdracht met voorbeelden.
Oude bestanden staan in [`archief/`](archief/).
