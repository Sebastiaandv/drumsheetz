"""Maatsoorten en het lezen van één instrumentrij (raster- of telnotatie).

Rasternotatie:   HH: x-x-x-x-x-x-x-x-        (lengte bepaalt de verdeling)
                 HH: x-x-|xxx|x-x-|xxxxxx    (| of spatie: gelijke stukken, elk met eigen verdeling)
                 BD: x---x---||x-x-x---       (|| = volgende maat)
Telnotatie:      SD: 2 4                     (tellen)
                 BD: 1 2& 3 3a               (e & a = 16den, t l = triolen)
                 HH: *8 4&:o                 (*8 = alle 8sten; ':' = aanslag)
                 HH: *8 !3&                  (! = weghalen)
"""
import re
from dataclasses import dataclass
from fractions import Fraction as Fr

from .kit import REST_CHARS


class NotationError(Exception):
    """Fout in de notatie, met (optioneel) bestand en regelnummer."""

    def __init__(self, msg, line=None, file=None):
        super().__init__(msg)
        self.msg, self.line, self.file = msg, line, file

    def __str__(self):
        where = ""
        if self.file:
            where += str(self.file)
        if self.line:
            where += f", regel {self.line}"
        return f"{where}: {self.msg}" if where else self.msg


@dataclass(frozen=True)
class Meter:
    num: int
    den: int
    groups: tuple = ()          # groepering in eenheden van 1/den, bv. (2, 2, 3) voor 7/8

    @property
    def length(self):
        """Lengte van de maat in kwartnoten."""
        return Fr(4 * self.num, self.den)

    @property
    def unit(self):
        """Eén tel in de telnotatie (1/den), in kwartnoten."""
        return Fr(4, self.den)

    @property
    def compound(self):
        return self.den >= 8 and self.num % 3 == 0 and self.num > 3

    def grouping(self):
        if self.groups:
            return self.groups
        if self.den <= 4:
            return (1,) * self.num
        if self.compound:
            return (3,) * (self.num // 3)
        if self.den == 16 and self.num % 4 == 0:
            return (4,) * (self.num // 4)
        if self.num <= 3:
            return (self.num,)
        g = [2] * (self.num // 2)
        if self.num % 2:
            g[-1] = 3
        if self.num == 5:
            g = [3, 2]
        return tuple(g)

    def beats(self):
        """Lijst (start, lengte) van de tellen voor de notatie, in kwartnoten."""
        out, pos = [], Fr(0)
        for g in self.grouping():
            ln = g * self.unit
            out.append((pos, ln))
            pos += ln
        return out

    def tempo_unit(self):
        """Standaard nootwaarde voor 'tempo: N' (in kwartnoten)."""
        if self.compound:
            return Fr(3, 2)
        return Fr(4, self.den)

    def __str__(self):
        s = f"{self.num}/{self.den}"
        if self.groups:
            s += " (" + "+".join(map(str, self.groups)) + ")"
        return s


def parse_meter(value):
    if isinstance(value, Meter):
        return value
    if isinstance(value, (tuple, list)):
        if len(value) == 3:
            return Meter(int(value[0]), int(value[1]), tuple(value[2]))
        return Meter(int(value[0]), int(value[1]))
    s = str(value).strip()
    if s.upper() == "C":
        return Meter(4, 4)
    if s in ("C|", "¢"):
        return Meter(2, 2)
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)\s*(?:\(\s*([\d+\s]+)\))?", s)
    if not m:
        raise NotationError(f"maatsoort '{s}' niet begrepen (voorbeeld: 4/4, 6/8, 7/8 (2+2+3))")
    num, den = int(m.group(1)), int(m.group(2))
    if den not in (1, 2, 4, 8, 16, 32):
        raise NotationError(f"noemer van de maatsoort moet 2, 4, 8 of 16 zijn, niet {den}")
    groups = ()
    if m.group(3):
        groups = tuple(int(x) for x in m.group(3).replace(" ", "").split("+") if x)
        if sum(groups) != num:
            raise NotationError(f"groepering {m.group(3)} telt niet op tot {num}")
    return Meter(num, den, groups)


# ---------------------------------------------------------------------------
# rasternotatie

GRID_OK = set("xXgfFdDrzZtToOh+c@bBkK^-._")


def is_count_style(text):
    """Telnotatie als er cijfers, * of ! in staan; anders raster."""
    t = text.replace("||", " ")
    return bool(re.search(r"[0-9*!]", t))


def split_bars(text):
    return [b.strip() for b in text.split("||")]


def parse_grid_bar(text, length, sticking=False):
    """Eén maat in rasternotatie -> [(pos, teken)]"""
    segs = [s for s in re.split(r"[|\s]+", text) if s]
    if not segs:
        return []
    out = []
    seglen = length / len(segs)
    for si, seg in enumerate(segs):
        step = seglen / len(seg)
        for i, ch in enumerate(seg):
            if ch in REST_CHARS:
                continue
            if not sticking and ch not in GRID_OK:
                if ch == ":":
                    raise NotationError(f"':' werkt alleen bij tellen (bv. '1:f'). In een raster is elk teken één "
                                        f"slag: zet de letter zelf op die plek, bv. 'f' in plaats van 'x:f' ('{text}')")
                raise NotationError(f"onbekend teken '{ch}' in raster '{text}' (zie 'python3 drums.py instrumenten')")
            out.append((si * seglen + i * step, ch))
    return out


# ---------------------------------------------------------------------------
# telnotatie

SUBS = {
    "": Fr(0), "e": Fr(1, 4), "&": Fr(1, 2), "+": Fr(1, 2), "en": Fr(1, 2), "and": Fr(1, 2),
    "a": Fr(3, 4), "ah": Fr(3, 4), "t": Fr(1, 3), "trip": Fr(1, 3), "l": Fr(2, 3), "let": Fr(2, 3),
    "ta": Fr(1, 3), "te": Fr(2, 3),
}
VALUES = {"1": Fr(4), "2": Fr(2), "4": Fr(1), "8": Fr(1, 2), "16": Fr(1, 4), "32": Fr(1, 8), "64": Fr(1, 16)}

TOKEN = re.compile(r"^(?P<beat>\d+)(?P<sub>(?:\.\d+)|(?:\+\d+/\d+)|e|&|\+|en|and|ah|a|trip|let|ta|te|t|l)?$")


def _count_pos(tok, meter):
    m = TOKEN.match(tok)
    if not m:
        raise NotationError(f"tel '{tok}' niet begrepen (voorbeelden: 1, 2&, 3e, 4a, 1t, 1l)")
    beat = int(m.group("beat"))
    sub = m.group("sub") or ""
    if sub.startswith("."):
        frac = Fr(sub[1:]) / (10 ** len(sub[1:]))
    elif sub.startswith("+") and "/" in sub:
        frac = Fr(sub[1:])
    else:
        frac = SUBS[sub]
    return (beat - 1 + frac) * meter.unit, beat


def parse_count_bar(text, meter, sticking=False):
    hits = {}
    for tok in text.replace("|", " ").split():
        mods = "x"
        if ":" in tok:
            tok, mods = tok.split(":", 1)
            if not mods:
                mods = "x"
            if not sticking and any(c not in GRID_OK for c in mods):
                raise NotationError(f"onbekend aanslagteken in '{tok}:{mods}'")
        remove = tok.startswith("!")
        if remove:
            tok = tok[1:]
        positions = []
        if tok.startswith("*") or re.match(r"^\d+-\d+\*", tok):
            rng, _, what = tok.partition("*")
            a, b = 1, meter.num
            if rng:
                a, b = (int(x) for x in rng.split("-"))
            what = what.lower()
            start, end = (a - 1) * meter.unit, b * meter.unit
            if what in SUBS and what not in ("",):
                for beat in range(a, b + 1):
                    positions.append(((beat - 1) + SUBS[what]) * meter.unit)
            else:
                trip = what.endswith("t")
                v = what[:-1] if trip else what
                if v not in VALUES:
                    raise NotationError(f"'*{what}' niet begrepen: gebruik *4, *8, *16, *32, *8t, *16t, *&, *e, *a")
                step = VALUES[v] * (Fr(2, 3) if trip else 1)
                p = start
                while p < end:
                    positions.append(p)
                    p += step
        else:
            p, beat = _count_pos(tok, meter)
            if beat < 1 or beat > meter.num:
                raise NotationError(f"tel {tok} valt buiten een {meter.num}/{meter.den}-maat")
            positions.append(p)
        for p in positions:
            if remove:
                hits.pop(p, None)
            else:
                hits[p] = mods
    return sorted(hits.items())


def parse_row(text, meter, sticking=False):
    """Eén rij -> lijst van maten, elke maat een lijst (pos, tekens)."""
    text = str(text).strip()
    if text in ("", "-"):
        return [[]]
    count = (not sticking and is_count_style(text)) or (sticking and re.search(r"\d", text))
    bars = []
    for b in split_bars(text):
        if count:
            bars.append(parse_count_bar(b, meter, sticking))
        else:
            bars.append(parse_grid_bar(b, meter.length, sticking))
    return bars


def grid_warning(text, meter):
    """Waarschuwing als een rasterrij een vreemde lengte heeft (typfout?)."""
    if is_count_style(text):
        return None
    for b in split_bars(text):
        segs = [s for s in re.split(r"[|\s]+", b) if s]
        if len(segs) == 1:
            n = len(segs[0])
            beats = len(meter.grouping())
            if n % beats and n % meter.num:
                return f"rij '{b}' heeft {n} tekens; bij {meter} verwacht je een veelvoud van {meter.num}"
    return None
