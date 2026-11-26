"""Het drumstel: alle instrumenten, hun plek op de notenbalk, nootkop en MIDI-nummer.

Plek op de balk (slagwerksleutel, 5 lijnen):
    C6  ── 2e hulplijn       splash, china
    B5     boven hulplijn    crash 2, stack, tamboerijn, triangel
    A5  ── 1e hulplijn       crash, cowbell, agogo
    G5     boven bovenste lijn  hi-hat
    F5  ── bovenste lijn     ride, ride bell
    E5     vak               tom 1 (hoog)
    D5  ── lijn              tom 2 (midden)
    C5     vak               snare, cross stick, rimshot, clap
    B4  ── middelste lijn    tom 3, ritme-slashes
    A4     vak               floor tom
    G4  ── lijn              floor tom 2
    F4     vak               bassdrum
    E4  ── onderste lijn     bassdrum 2 (dubbele voet)
    D4     onder de balk     hi-hat voet
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Instr:
    code: str
    name: str          # Nederlandse omschrijving
    step: str          # display-step
    octave: int        # display-octave
    head: str          # MusicXML notehead: normal, x, circle-x, diamond, triangle, slash, cross, square
    midi: int          # General MIDI nootnummer (0 = stil)
    voice: int = 1     # 1 = handen (stok omhoog), 2 = voeten (stok omlaag)
    mark: str = ""     # vaste markering: 'o' (open), '+' (dicht)
    group: str = ""    # 'cymbal', 'hh', 'drum', 'foot', 'perc', 'other'

    @property
    def staff_index(self):
        """Hoogte op de balk als getal (voor ASCII-weergave)."""
        return self.octave * 7 + "CDEFGAB".index(self.step)


_KIT = [
    # code  naam                       stap oct kop         midi stem markering groep
    Instr("BD", "bassdrum", "F", 4, "normal", 36, 2, "", "foot"),
    Instr("BD2", "bassdrum 2 / linkervoet dubbele pedaal", "E", 4, "normal", 35, 2, "", "foot"),
    Instr("HF", "hi-hat met de voet (dicht)", "D", 4, "x", 44, 2, "", "foot"),
    Instr("HS", "hi-hat voet-splash", "D", 4, "x", 46, 2, "o", "foot"),
    Instr("SD", "snare", "C", 5, "normal", 38, 1, "", "drum"),
    Instr("XS", "cross stick / side stick", "C", 5, "x", 37, 1, "", "drum"),
    Instr("RIM", "rimshot", "C", 5, "circle-x", 40, 1, "", "drum"),
    Instr("CL", "handclap", "C", 5, "triangle", 39, 1, "", "perc"),
    Instr("T1", "tom 1 (hoog)", "E", 5, "normal", 50, 1, "", "drum"),
    Instr("T2", "tom 2 (midden)", "D", 5, "normal", 48, 1, "", "drum"),
    Instr("T3", "tom 3 (laag)", "B", 4, "normal", 47, 1, "", "drum"),
    Instr("FT", "floor tom", "A", 4, "normal", 43, 1, "", "drum"),
    Instr("FT2", "floor tom 2 (laag)", "G", 4, "normal", 41, 1, "", "drum"),
    Instr("HH", "hi-hat (dicht, met stok)", "G", 5, "x", 42, 1, "", "hh"),
    Instr("HO", "hi-hat open", "G", 5, "x", 46, 1, "o", "hh"),
    Instr("RD", "ride", "F", 5, "x", 51, 1, "", "cymbal"),
    Instr("RB", "ride bell", "F", 5, "diamond", 53, 1, "", "cymbal"),
    Instr("CR", "crash", "A", 5, "x", 49, 1, "", "cymbal"),
    Instr("CR2", "crash 2", "B", 5, "x", 57, 1, "", "cymbal"),
    Instr("SP", "splash", "C", 6, "x", 55, 1, "", "cymbal"),
    Instr("CH", "china", "C", 6, "circle-x", 52, 1, "", "cymbal"),
    Instr("STK", "stack", "B", 5, "circle-x", 52, 1, "", "cymbal"),
    Instr("CB", "cowbell", "A", 5, "triangle", 56, 1, "", "perc"),
    Instr("TAMB", "tamboerijn", "B", 5, "diamond", 54, 1, "", "perc"),
    Instr("TRI", "triangel", "B", 5, "triangle", 81, 1, "", "perc"),
    Instr("SHK", "shaker", "G", 5, "triangle", 82, 1, "", "perc"),
    Instr("CLV", "claves", "F", 5, "triangle", 75, 1, "", "perc"),
    Instr("WB", "woodblock hoog", "E", 5, "triangle", 76, 1, "", "perc"),
    Instr("WBL", "woodblock laag", "D", 5, "triangle", 77, 1, "", "perc"),
    Instr("AGH", "agogo hoog", "A", 5, "diamond", 67, 1, "", "perc"),
    Instr("AGL", "agogo laag", "G", 5, "diamond", 68, 1, "", "perc"),
    Instr("CGH", "conga hoog", "E", 5, "diamond", 63, 1, "", "perc"),
    Instr("CGL", "conga laag", "D", 5, "diamond", 64, 1, "", "perc"),
    Instr("BGH", "bongo hoog", "E", 5, "cross", 60, 1, "", "perc"),
    Instr("BGL", "bongo laag", "D", 5, "cross", 61, 1, "", "perc"),
    Instr("TBH", "timbale hoog", "E", 5, "square", 65, 1, "", "perc"),
    Instr("TBL", "timbale laag", "D", 5, "square", 66, 1, "", "perc"),
    Instr("CK", "stokken tegen elkaar (aftellen)", "B", 4, "x", 31, 1, "", "other"),
    Instr("SL", "ritme-slash (ensemble-figuur, klinkt niet)", "B", 4, "slash", 0, 1, "", "other"),
]

KIT = {i.code: i for i in _KIT}

ALIASES = {
    # bassdrum
    "KICK": "BD", "BASS": "BD", "BASSDRUM": "BD", "K": "BD", "BD1": "BD", "KICK1": "BD",
    "KICK2": "BD2", "BASSDRUM2": "BD2", "LBD": "BD2",
    # hihat voet
    "HP": "HF", "HHF": "HF", "PEDAL": "HF", "HHP": "HF", "VOET": "HF", "HHFOOT": "HF",
    "HHS": "HS", "SPLASHVOET": "HS",
    # snare
    "S": "SD", "SN": "SD", "SNARE": "SD",
    "CS": "XS", "SS": "XS", "RS": "XS", "SIDESTICK": "XS", "CROSSSTICK": "XS", "RIMCLICK": "XS",
    "RIMSHOT": "RIM", "RSH": "RIM",
    "CLAP": "CL", "HC": "CL",
    # toms
    "HT": "T1", "TOM1": "T1", "MT": "T2", "TOM2": "T2", "LT": "T3", "TOM3": "T3",
    "F": "FT", "FLOOR": "FT", "FT1": "FT", "FLOORTOM": "FT", "LFT": "FT2", "FLOOR2": "FT2",
    # bekkens
    "H": "HH", "HIHAT": "HH", "HHC": "HH", "OH": "HO", "HHO": "HO",
    "R": "RD", "RIDE": "RD", "RC": "RD", "BELL": "RB", "RIDEBELL": "RB",
    "C": "CR", "CR1": "CR", "CRASH": "CR", "CC": "CR", "CRASH2": "CR2", "C2": "CR2",
    "SPLASH": "SP", "CHINA": "CH", "CN": "CH", "STACK": "STK",
    # percussie
    "COWBELL": "CB", "COW": "CB", "TB": "TAMB", "TAMBOERIJN": "TAMB", "TAMBOURINE": "TAMB",
    "TRIANGLE": "TRI", "TRIANGEL": "TRI", "SHAKER": "SHK", "SH": "SHK", "CLAVES": "CLV",
    "WOODBLOCK": "WB", "AGOGO": "AGH", "CONGA": "CGH", "BONGO": "BGH", "TIMBALE": "TBH",
    "STICKS": "CK", "CLICK": "CK", "STOKKEN": "CK",
    "SLASH": "SL", "RITME": "SL", "HITS": "SL",
}

# speciale rijen die geen instrument zijn
STICKING_ROWS = {"ST", "STICK", "STICKING", "PLAK", "HAND", "HANDEN"}

# Aanslag-tekens (één teken per slag in een raster, of na ':' in telnotatie)
MODS = {
    "x": "gewone slag",
    "X": "accent (>)",
    "^": "marcato / zwaar accent (^)",
    "g": "ghost note (tussen haakjes)",
    "f": "flam (voorslag)",
    "F": "flam met accent",
    "d": "drag (twee voorslagen)",
    "D": "drag met accent",
    "r": "ruff (drie voorslagen, 4-stroke ruff)",
    "z": "buzz roll (Z op de stok)",
    "Z": "buzz roll met accent",
    "t": "roffel (drie streepjes door de stok)",
    "T": "roffel met accent",
    "o": "open (hi-hat open / bekken open: rondje)",
    "O": "open met accent",
    "h": "half open hi-hat",
    "+": "dicht (plusje)",
    "c": "cross stick (op de snare-rij)",
    "@": "rimshot (op de snare-rij)",
    "b": "bell (op de ride-rij: ride bell)",
    "B": "bell met accent",
    "k": "choke (bekken direct afknijpen)",
    "K": "choke met accent",
}
UPPER_ACCENT = {"X": "x", "F": "f", "D": "d", "Z": "z", "T": "t", "O": "o", "B": "b", "K": "k"}
REST_CHARS = set("-._")


def lookup(code, custom=None):
    """Instrumentcode (of alias) -> Instr. Geeft None als onbekend."""
    if custom and code in custom:
        return custom[code]
    c = code.upper().replace("-", "").replace(" ", "")
    if custom and c in custom:
        return custom[c]
    c = ALIASES.get(c, c)
    if custom and c in custom:
        return custom[c]
    return KIT.get(c)


def normalize_mods(mods):
    """'Xo' -> set {'>', 'o'} : accent los van de rest."""
    out = set()
    for ch in mods:
        if ch == "X":
            out.add(">")
        elif ch in UPPER_ACCENT:
            out.add(">")
            out.add(UPPER_ACCENT[ch])
        elif ch == "x":
            continue
        else:
            out.add(ch)
    return frozenset(out)


def resolve_hit(instr, mods, kit):
    """Pas instrumentwissel toe door aanslagtekens: c op snare -> XS, @ -> RIM, b op ride -> RB,
    o op hi-hat -> HO. Geeft (Instr, mods) terug."""
    m = set(mods)
    if instr.code in ("SD", "RIM", "XS"):
        if "c" in m:
            m.discard("c")
            instr = kit.get("XS", KIT["XS"])
        elif "@" in m:
            m.discard("@")
            instr = kit.get("RIM", KIT["RIM"])
    else:
        if "c" in m:  # cross stick op een ander instrument: niet zinvol, negeer
            m.discard("c")
        if "@" in m:  # rimshot op een tom: cirkel-kop
            m.discard("@")
            instr = replace(instr, head="circle-x")
    if "b" in m:
        m.discard("b")
        if instr.code in ("RD", "RB"):
            instr = kit.get("RB", KIT["RB"])
        else:
            instr = replace(instr, head="diamond")
    if instr.code == "HH" and "o" in m:
        m.discard("o")
        instr = kit.get("HO", KIT["HO"])
    if instr.code == "HF" and "o" in m:
        m.discard("o")
        instr = kit.get("HS", KIT["HS"])
    if instr.mark and instr.mark not in m and not ("h" in m or "+" in m):
        m.add(instr.mark)
    return instr, frozenset(m)


def parse_instrument_def(code, spec):
    """'E5 triangle 56 "naam" stem=1'  ->  Instr. Voor eigen instrumenten in een .drum-bestand."""
    import shlex
    parts = shlex.split(spec)
    if not parts:
        raise ValueError("lege instrumentdefinitie")
    pos = parts[0].upper()
    if len(pos) < 2 or pos[0] not in "CDEFGAB" or not pos[1:].isdigit():
        raise ValueError(f"plek '{parts[0]}' moet een noot zijn zoals F4, C5 of G5")
    head, midi, name, voice = "normal", 0, code, 1
    base = KIT.get(code.upper())
    if base:
        head, midi, name, voice = base.head, base.midi, base.name, base.voice
    heads = {"normaal": "normal", "kruis": "x", "rondje-kruis": "circle-x", "ruit": "diamond",
             "driehoek": "triangle", "vierkant": "square", "plus": "cross"}
    for p in parts[1:]:
        pl = p.lower()
        if pl.isdigit():
            midi = int(pl)
        elif pl in ("normal", "x", "circle-x", "diamond", "triangle", "slash", "cross", "square",
                    "slashed", "back-slashed", "circle-dot", "inverted triangle", "do", "re", "mi", "fa", "la"):
            head = pl
        elif pl in heads:
            head = heads[pl]
        elif pl in ("voet", "stem=2", "omlaag", "down"):
            voice = 2
        elif pl in ("hand", "stem=1", "omhoog", "up"):
            voice = 1
        else:
            name = p
    group = "foot" if voice == 2 else (base.group if base else "perc")
    return Instr(code.upper(), name, pos[0], int(pos[1:]), head, midi, voice, "", group)
