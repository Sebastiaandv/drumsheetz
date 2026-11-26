"""Lezer voor het makkelijke .drum-formaat.

Een .drum-bestand bestaat uit drie soorten blokken:

    titel: Let Love Rule          <- kop met gegevens (sleutel: waarde)
    artiest: Lenny Kravitz
    tempo: 90
    maat: 4/4

    groove couplet:               <- patroon (groove of fill)
      HH: *8 4&:o
      SD: 2 4
      BD: 1 2a 3 3&

    [Intro] 8 couplet fill sd4    <- sectie met één of meer regels "aantal patroon opties"
    [Refrein]
      8 refrein crash mf
      8 refrein fill tom34 cresc

Alles wat het resultaat nodig heeft komt in een dict met dezelfde sleutels als het oude
Python-formaat (SONG / GROOVES / FILLS), zodat beide formaten dezelfde motor gebruiken.
"""
import re

from .kit import STICKING_ROWS, lookup, parse_instrument_def
from .patterns import Pattern, PatternBook
from .rows import NotationError, parse_meter

HEADER_KEYS = {
    "titel": "title", "title": "title", "naam": "title",
    "artiest": "artist", "artist": "artist", "band": "artist", "uitvoerder": "artist",
    "ondertitel": "subtitle", "subtitle": "subtitle",
    "tempo": "bpm", "bpm": "bpm",
    "maat": "meter", "maatsoort": "meter", "meter": "meter", "time": "meter",
    "stijl": "feel", "feel": "feel", "gevoel": "feel", "groove": "feel",
    "vermelding": "credit", "credit": "credit", "uitgeschreven-door": "credit",
    "door": "by", "transcriptie": "by", "by": "by", "arrangement": "by",
    "notitie": "notes", "notities": "notes", "notes": "notes", "opmerking": "notes",
    "toonsoort": "key", "key": "key",
    "duur": "duration", "duration": "duration", "lengte": "duration",
    "status": "status", "tags": "tags", "bron": "source", "source": "source",
    "audio": "audio", "mp3": "audio", "pdf": "pdf", "extern": "pdf",
    "aftellen": "countin", "countin": "countin", "count-in": "countin", "intel": "countin",
    "layout": "layout", "opmaak": "layout",
    "maten-per-regel": "bars_per_line", "regel": "bars_per_line", "maten_per_regel": "bars_per_line",
    "herhaaltekens": "compress", "compress": "compress", "procent": "compress",
    "swing": "swing", "shuffle": "swing",
    "herhaalteller": "count_pos", "teller": "count_pos",
    "accenten": "accent_pos", "accent": "accent_pos",
    "vorken": "wedge_pos", "crescendo": "wedge_pos", "dynamiek": "dyn_pos",
    "tekstgrootte": "text_size", "tekst-grootte": "text_size", "textsize": "text_size",
    "stijlgrootte": "feel_size", "stijl-grootte": "feel_size",
    "stemmen": "voices", "voices": "voices", "stem": "voices",
    "componist": "composer", "composer": "composer", "jaar": "year", "year": "year",
    "album": "album",
}

PATTERN_OPTS = {"maten": "bars", "bars": "bars", "maat": "meter", "meter": "meter",
                "basis": "base", "base": "base", "info": "doc", "uitleg": "doc", "doc": "doc"}

DYNAMICS = {"pppp", "ppp", "pp", "p", "mp", "mf", "f", "ff", "fff", "ffff",
            "sfz", "sf", "sffz", "fp", "sfp", "rfz", "rf", "fz", "sfzp"}
CRESC = {"cresc", "cresc.", "crescendo", "<", "aanzwellen"}
DIM = {"dim", "dim.", "decresc", "decresc.", "diminuendo", "decrescendo", ">", "afnemen"}
MARKS = {
    "segno": "segno", "coda": "coda", "fine": "fine",
    "naar-coda": "tocoda", "tocoda": "tocoda", "to-coda": "tocoda", "naarcoda": "tocoda",
    "ds": "ds", "d.s.": "ds", "ds-al-coda": "dsalcoda", "d.s.-al-coda": "dsalcoda",
    "ds-al-fine": "dsalfine", "dc": "dc", "d.c.": "dc", "dc-al-coda": "dcalcoda",
    "dc-al-fine": "dcalfine",
}
TEMPO_TEXT = {"rit": "rit.", "rit.": "rit.", "ritardando": "rit.", "rall": "rall.", "rall.": "rall.",
              "accel": "accel.", "accel.": "accel.", "accelerando": "accel.",
              "a-tempo": "a tempo", "atempo": "a tempo", "tempo-primo": "Tempo I",
              "halftime": "half time feel", "half-time": "half time feel",
              "doubletime": "double time feel", "double-time": "double time feel"}
CRASHES = {"crash": "CR", "crash2": "CR2", "china": "CH", "splash": "SP", "stack": "STK"}
FLAGS = {
    "fermata": ("fermata", True),
    "uitgeschreven": ("written", True), "voluit": ("written", True), "written": ("written", True),
    "full": ("written", True), "geen-procent": ("written", True),
    "nieuweregel": ("newline", True), "regel": ("newline", True), "newline": ("newline", True),
    "nieuwe-regel": ("newline", True),
    "doorlopen": ("newline", False), "geenregel": ("newline", False),
    "nieuwepagina": ("newpage", True), "pagina": ("newpage", True), "newpage": ("newpage", True),
    "nieuwe-pagina": ("newpage", True),
    "end": ("end", True), "einde": ("end", True),
    "stop": None,
}
VALUE_OPTS = {
    "fill": "fill", "fills": "fill", "crash": "crash",
    "tempo": "tempo", "bpm": "tempo", "maat": "meter", "meter": "meter",
    "herhaal": "repeat", "repeat": "repeat", "volta": "volta", "dyn": "dyn",
    "tekst": "text", "text": "text",
    "grootte": "text_size", "tekstgrootte": "text_size", "size": "text_size",
}
TEXT_SIZES = {"klein": "klein", "heelklein": "heelklein", "groot": "groot", "heelgroot": "heelgroot",
              "normaal": "normaal"}


def tokenize(s):
    """Splits op spaties, maar houdt "tekst tussen aanhalingstekens" en {inline patronen} heel."""
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c in "\"'“”":
            close = {"\"": "\"", "'": "'", "“": "”", "”": "”"}[c]
            j = s.find(close, i + 1)
            if j < 0:
                raise NotationError(f"aanhalingsteken niet gesloten in: {s}")
            out.append(("text", s[i + 1:j]))
            i = j + 1
            continue
        if c == "{":
            j = s.find("}", i + 1)
            if j < 0:
                raise NotationError(f"accolade {{ niet gesloten in: {s}")
            out.append(("inline", s[i + 1:j]))
            i = j + 1
            continue
        j = i
        while j < n and not s[j].isspace() and s[j] not in "\"{":
            j += 1
        out.append(("word", s[i:j]))
        i = j
    return out


def strip_comment(line):
    """Verwijder # commentaar (maar niet binnen aanhalingstekens)."""
    q = None
    for i, c in enumerate(line):
        if q:
            if c == q:
                q = None
        elif c in "\"“":
            q = "\"" if c == "\"" else "”"
        elif c == "#":
            return line[:i]
    return line


def parse_inline_rows(text):
    """'HH *8; SD 2 4; BD: 1 3' -> {'HH': '*8', ...}"""
    rows = {}
    for part in re.split(r"[;\n]", text):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([A-Za-z][A-Za-z0-9_\-]*)\s*:?\s*(.*)$", part)
        if not m:
            raise NotationError(f"rij '{part}' niet begrepen (verwacht bv. 'SD: 2 4')")
        rows[m.group(1)] = m.group(2).strip()
    return rows


class Parser:
    def __init__(self, text, filename=None, library=None):
        self.lines = text.splitlines()
        self.file = filename
        self.book = PatternBook(parent=library)
        self.song = {"sections": []}
        self.warnings = []
        self.anon = 0
        self.declared = set(re.findall(r"(?im)^(?:groove|fill|patroon|pattern|ritme)\s+([^\s=:]+)", text))

    def err(self, msg, ln):
        return NotationError(msg, ln, self.file)

    # ------------------------------------------------------------------
    def parse_patterns_only(self):
        return self.parse(require_sections=False)

    def parse(self, require_sections=True):
        i = 0
        section = None
        while i < len(self.lines):
            ln = i + 1
            raw = strip_comment(self.lines[i]).rstrip()
            i += 1
            if not raw.strip():
                continue
            indented = raw[0].isspace()
            line = raw.strip()

            m = re.match(r"^(groove|fill|patroon|pattern|ritme)\s+([^\s=:]+)\s*(?:=\s*([^\s:]+))?\s*:?\s*(.*)$",
                         line, re.I)
            if m and not indented:
                pat = Pattern(m.group(2), line=ln, file=self.file,
                              kind="fill" if m.group(1).lower() == "fill" else "groove")
                pat.base = m.group(3)
                if m.group(4).strip():
                    try:
                        pat.rows.update(parse_inline_rows(m.group(4)))
                    except NotationError as e:
                        raise self.err(e.msg, ln)
                # blok: ingesprongen regels of regels die met een instrumentcode beginnen
                while i < len(self.lines):
                    r2 = strip_comment(self.lines[i]).rstrip()
                    if not r2.strip():
                        i += 1
                        continue
                    km = re.match(r"^\s*([A-Za-z][A-Za-z0-9_\-]*)\s*:\s*(.*)$", r2)
                    is_row = km and (lookup(km.group(1), self.book.kit) or km.group(1).upper() in STICKING_ROWS
                                     or km.group(1).lower() in PATTERN_OPTS)
                    if not (r2[0].isspace() or is_row):
                        break
                    if not km:
                        raise self.err(f"regel '{r2.strip()}' in patroon '{pat.name}' niet begrepen "
                                       "(verwacht 'INSTRUMENT: noten')", i + 1)
                    key, val = km.group(1), km.group(2).strip()
                    opt = PATTERN_OPTS.get(key.lower())
                    if opt and not lookup(key, self.book.kit):
                        if opt == "bars":
                            pat.bars = int(val)
                        else:
                            setattr(pat, opt, val)
                    else:
                        pat.rows[key] = val
                    i += 1
                if not pat.rows and not pat.base:
                    raise self.err(f"patroon '{pat.name}' heeft geen rijen", ln)
                self.book.add(pat)
                section = None
                continue

            m = re.match(r"^(instrument|kit)\s+([A-Za-z][A-Za-z0-9_]*)\s*[:=]?\s*(.+)$", line, re.I)
            if m and not indented:
                try:
                    ins = parse_instrument_def(m.group(2), m.group(3))
                except ValueError as e:
                    raise self.err(str(e), ln)
                self.book.kit[ins.code] = ins
                continue

            m = re.match(r"^\[([^\]]*)\]\s*(.*)$", line)
            if m:
                section = {"label": m.group(1).strip(), "seq": [], "_line": ln}
                self.song["sections"].append(section)
                rest = m.group(2).strip()
                if rest:
                    self.section_line(section, rest, ln)
                continue

            m = re.match(r"^([A-Za-z][\w\-]*)\s*:\s*(.*)$", line)
            if m and section is None and not indented:
                key = m.group(1).lower()
                if key in HEADER_KEYS:
                    self.header(HEADER_KEYS[key], m.group(2).strip(), ln)
                    continue
                if lookup(m.group(1), self.book.kit):
                    raise self.err(f"rij '{line}' staat niet in een groove- of fill-blok", ln)
                raise self.err(f"onbekende kop '{m.group(1)}:'. Bekend: titel, artiest, tempo, maat, "
                               "stijl, ondertitel, aftellen, ... (zie HANDLEIDING.md)", ln)

            if section is None:
                if re.match(r"^\d", line):
                    section = {"label": "", "seq": [], "_line": ln}
                    self.song["sections"].append(section)
                else:
                    raise self.err(f"regel '{line}' niet begrepen. Een sectie begint met [Naam], "
                                   "een patroon met 'groove naam:'", ln)
            self.section_line(section, line, ln)

        if require_sections:
            self.finish()
        return self.song, self.book

    # ------------------------------------------------------------------
    def header(self, key, val, ln):
        if key == "meter":
            try:
                parse_meter(val)
            except NotationError as e:
                raise self.err(e.msg, ln)
        if key in ("countin", "bars_per_line"):
            if not val.isdigit():
                raise self.err(f"'{key}' verwacht een getal, niet '{val}'", ln)
            val = int(val)
        if key == "compress":
            val = val.lower() not in ("nee", "no", "uit", "false", "0", "off")
        if key == "bpm" and val.isdigit():
            val = int(val)
        if key == "notes" and "notes" in self.song:
            val = self.song["notes"] + " · " + val
        self.song[key] = val

    def section_line(self, section, line, ln):
        try:
            toks = tokenize(line)
        except NotationError as e:
            raise self.err(e.msg, ln)
        if not toks:
            return
        t0 = toks[0]
        if t0[0] == "word" and re.fullmatch(r"\d+x?", t0[1], re.I):
            phase = {"bars": int(t0[1].rstrip("xX")), "_line": ln}
            rest = toks[1:]
            if rest and rest[0] == ("word", "maten") or rest and rest[0] == ("word", "maat"):
                rest = rest[1:]
            if rest and rest[0][0] == "inline":
                phase["groove"] = self.inline_pattern(rest[0][1], ln)
                rest = rest[1:]
            elif rest and rest[0][0] == "word" and (rest[0][1] in self.declared or self.book.get(rest[0][1])
                                                    or not self.is_option(rest[0][1])):
                phase["groove"] = rest[0][1]
                rest = rest[1:]
            else:
                prev = section["seq"][-1] if section["seq"] else self.last_phase()
                phase["groove"] = prev.get("groove") if prev else None
            self.options(phase, rest, ln)
            section["seq"].append(phase)
        else:
            self.options(section, toks, ln, section_level=True)

    def last_phase(self):
        for s in reversed(self.song["sections"][:-1]):
            if s["seq"]:
                return s["seq"][-1]
        return None

    def inline_pattern(self, text, ln):
        self.anon += 1
        name = f"~{self.anon}"
        try:
            rows = parse_inline_rows(text)
        except NotationError as e:
            raise self.err(e.msg, ln)
        base = None
        for k in list(rows):
            if k.lower() in ("basis", "base", "van"):
                base = rows.pop(k)
        self.book.add(Pattern(name, rows=rows, base=base, line=ln, file=self.file))
        return name

    def is_option(self, w):
        lw = w.lower()
        if "=" in w or re.fullmatch(r"[a-z]+[<>][a-z]+", lw):
            return True
        return (lw in DYNAMICS or lw in CRESC or lw in DIM or lw in MARKS or lw in TEMPO_TEXT
                or lw in FLAGS or lw in VALUE_OPTS or lw in CRASHES or lw in TEXT_SIZES)

    def options(self, target, toks, ln, section_level=False):
        i = 0
        texts = []
        while i < len(toks):
            kind, w = toks[i]
            i += 1
            if kind == "text":
                texts.append(w)
                continue
            if kind == "inline":
                raise self.err("een {inline patroon} mag alleen direct na het aantal maten staan", ln)
            lw = w.lower()
            key, val = None, None
            if "=" in w or (":" in w and not w.endswith(":")):
                key, _, val = w.replace(":", "=", 1).partition("=")
                key = key.lower()
            elif lw.endswith(":"):
                key = lw[:-1]
            if key in ("cresc", "crescendo", "dim", "decresc", "diminuendo", "<", ">") and val:
                target["wedge"] = "crescendo" if key in ("cresc", "crescendo", "<") else "diminuendo"
                rng = re.fullmatch(r"([a-z]+)?\s*(?:-|\.\.|–|naar)\s*([a-z]+)", val.lower())
                if not rng or rng.group(2) not in DYNAMICS or (rng.group(1) and rng.group(1) not in DYNAMICS):
                    raise self.err(f"'{w}' niet begrepen: gebruik bv. cresc=p-f of dim=f-p", ln)
                if rng.group(1):
                    target["dyn"] = rng.group(1)
                target["dyn_end"] = rng.group(2)
                continue
            if key is None and lw in VALUE_OPTS and lw not in ("crash",):
                key = lw
            if key is not None:
                if val is None or val == "":
                    if i >= len(toks):
                        raise self.err(f"optie '{w}' mist een waarde", ln)
                    val = toks[i][1]
                    i += 1
                    if key == "tempo" and i < len(toks) and toks[i][0] == "word" and toks[i][1] in ("q", "kwart"):
                        i += 1
                self.set_value(target, key, val, ln)
                continue
            m = re.fullmatch(r"([a-z]+)\s*([<>])\s*([a-z]+)", lw)
            if m and m.group(1) in DYNAMICS and m.group(3) in DYNAMICS:     # p<f  of  f>p
                target["dyn"], target["dyn_end"] = m.group(1), m.group(3)
                target["wedge"] = "crescendo" if m.group(2) == "<" else "diminuendo"
            elif lw in DYNAMICS:
                target["dyn"] = lw
            elif lw in CRESC or lw in DIM:
                target["wedge"] = "crescendo" if lw in CRESC else "diminuendo"
                if i < len(toks) and toks[i][0] == "word":                 # cresc p-f  /  dim f-p
                    rng = re.fullmatch(r"([a-z]+)?\s*(?:-|\.\.|–|naar)\s*([a-z]+)", toks[i][1].lower())
                    if rng and rng.group(2) in DYNAMICS and (rng.group(1) or "p") in DYNAMICS:
                        if rng.group(1):
                            target["dyn"] = rng.group(1)
                        target["dyn_end"] = rng.group(2)
                        i += 1
            elif lw in MARKS:
                target.setdefault("marks", []).append(MARKS[lw])
            elif lw in TEMPO_TEXT:
                target["tempo_text"] = TEMPO_TEXT[lw]
            elif lw in TEXT_SIZES:
                target["text_size"] = TEXT_SIZES[lw]
            elif lw in CRASHES:
                target["crash"] = CRASHES[lw]
            elif lw in FLAGS and FLAGS[lw]:
                k, v = FLAGS[lw]
                target[k] = v
            elif re.fullmatch(r"\d+x", lw) and section_level:
                target["repeat"] = int(lw[:-1])
            else:
                import difflib
                known = sorted(set(DYNAMICS) | CRESC | DIM | set(MARKS) | set(TEMPO_TEXT) | set(FLAGS)
                               | set(VALUE_OPTS) | set(CRASHES) | set(TEXT_SIZES))
                close = difflib.get_close_matches(lw, known, n=2)
                hint = f" Bedoel je: {', '.join(close)}?" if close else ""
                if self.book.get(w):
                    hint = " (dit is een patroonnaam: zet het aantal maten ervoor, bv. '8 " + w + "')"
                raise self.err(f"optie '{w}' niet begrepen{hint}", ln)
        if texts:
            prev = target.get("text")
            target["text"] = " · ".join(([prev] if prev else []) + texts)

    def set_value(self, target, key, val, ln):
        key = VALUE_OPTS.get(key, key)
        if key == "fill":
            names = [v for v in val.split(",") if v]
            target["fill"] = names[0] if len(names) == 1 else names
        elif key == "crash":
            ins = lookup(val, self.book.kit)
            if not ins:
                raise self.err(f"crash-instrument '{val}' onbekend", ln)
            target["crash"] = ins.code
        elif key == "tempo":
            target["tempo"] = int(val) if val.isdigit() else val
        elif key == "meter":
            try:
                parse_meter(val)
            except NotationError as e:
                raise self.err(e.msg, ln)
            target["meter"] = val
        elif key == "repeat":
            if not val.rstrip("x×").isdigit():
                raise self.err(f"herhaal verwacht een aantal keer, niet '{val}'", ln)
            target["repeat"] = int(val.rstrip("x×"))
        elif key == "volta":
            target["volta"] = [int(x) for x in val.replace(".", "").split(",") if x]
        elif key == "dyn":
            target["dyn"] = val
        elif key == "text":
            target["text"] = val
        elif key == "text_size":
            target["text_size"] = val
        else:
            raise self.err(f"optie '{key}' onbekend", ln)

    def finish(self):
        for s in self.song["sections"]:
            if not s["seq"]:
                raise NotationError(f"sectie [{s['label']}] heeft geen maten (bv. '8 rock')", s["_line"], self.file)
        if "title" not in self.song:
            self.warnings.append("geen titel opgegeven")


def parse_text(text, filename=None, library=None):
    p = Parser(text, filename, library)
    song, book = p.parse()
    return song, book, p.warnings
