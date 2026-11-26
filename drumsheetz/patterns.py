"""Patronen (grooves en fills): opslag, afleiden (basis + wijzigingen) en omzetten naar maten."""
import difflib
from dataclasses import dataclass, field
from fractions import Fraction as Fr

from .kit import KIT, STICKING_ROWS, Instr, lookup, normalize_mods, resolve_hit
from .rows import Meter, NotationError, grid_warning, is_count_style, parse_meter, parse_row

STICK = Instr("ST", "sticking", "B", 4, "normal", 0, 1, "", "sticking")

REST_NAMES = {None, "", "-", "tacet", "rust", "rest", "stil", "pauze", "none", "None"}
SLASH_NAMES = {"/", "time", "vrij", "slash", "slashes", "tijd", "comp"}


@dataclass(frozen=True)
class Hit:
    pos: Fr
    instr: Instr
    mods: frozenset = frozenset()
    text: str = ""          # sticking-tekst (R, L, ...)

    @property
    def is_foot(self):
        return self.instr.voice == 2


@dataclass(frozen=True)
class Bar:
    meter: Meter
    hits: tuple = ()
    rest: bool = False       # hele maat rust
    slashes: bool = False    # ritme-slashes ('time')

    def key(self):
        return (self.meter, self.hits, self.rest, self.slashes)


@dataclass
class Pattern:
    name: str
    rows: dict = field(default_factory=dict)   # rijnaam -> tekst ('' of '-' = weghalen)
    bars: int = 0
    meter: str = None
    base: str = None
    line: int = None
    file: str = None
    doc: str = ""
    kind: str = "groove"     # groove of fill (alleen informatief)


class PatternBook:
    """Alle bekende patronen, met lagen: ingebouwd < bibliotheek < nummer."""

    def __init__(self, parent=None):
        self.parent = parent
        self.items = {}
        self.kit = dict(parent.kit) if parent else {}
        self._cache = {}

    def add(self, pat):
        self.items[pat.name] = pat
        self._cache.clear()

    def get(self, name):
        if name in self.items:
            return self.items[name]
        if self.parent:
            return self.parent.get(name)
        return None

    def names(self):
        s = set(self.parent.names()) if self.parent else set()
        return s | set(self.items)

    def instr(self, code):
        return lookup(code, self.kit)

    def suggest(self, name):
        m = difflib.get_close_matches(name, sorted(self.names()), n=3)
        return f" Bedoel je: {', '.join(m)}?" if m else ""

    # ------------------------------------------------------------------
    def rows_of(self, name, seen=()):
        pat = self.get(name)
        if pat is None:
            raise NotationError(f"patroon '{name}' bestaat niet.{self.suggest(name)}")
        if name in seen:
            raise NotationError(f"patroon '{name}' verwijst (via basis) naar zichzelf")
        rows, bars, meter = {}, pat.bars, pat.meter
        if pat.base:
            rows, b_bars, b_meter = self.rows_of(pat.base, seen + (name,))
            bars = bars or b_bars
            meter = meter or b_meter
        for k, v in pat.rows.items():
            key = self._rowkey(k)
            if str(v).strip() in ("", "-", "weg", "geen"):
                rows.pop(key, None)
            else:
                rows[key] = v
        return dict(rows), bars, meter

    def _rowkey(self, k):
        ku = k.upper()
        if ku in STICKING_ROWS:
            return "ST"
        ins = self.instr(k)
        return ins.code if ins else k

    def compile(self, name, meter):
        """Patroon -> lijst Bar-objecten."""
        ck = (name, meter)
        if ck in self._cache:
            return self._cache[ck]
        pat = self.get(name)
        rows, nbars, pmeter = self.rows_of(name)
        m = parse_meter(pmeter) if pmeter else meter
        parsed = {}
        for key, text in rows.items():
            if isinstance(text, (list, tuple)):
                text = " || ".join(text)
            text = str(text)
            sticking = key == "ST"
            if not sticking and self.instr(key) is None:
                raise NotationError(_unknown(key, self), pat.line, pat.file)
            if nbars and nbars > 1 and "||" not in text and not is_count_style(text) and not sticking:
                compact = "".join(text.split()).replace("|", "")
                if len(compact) % nbars == 0:
                    n = len(compact) // nbars
                    text = " || ".join(compact[i * n:(i + 1) * n] for i in range(nbars))
            try:
                parsed[key] = parse_row(text, m, sticking)
            except NotationError as e:
                raise NotationError(f"patroon '{name}', rij {key}: {e.msg}", pat.line, pat.file)
        nb = max([nbars or 1] + [len(v) for v in parsed.values()])
        out = []
        for bi in range(nb):
            hits = {}
            for key, bars in parsed.items():
                for pos, mods in bars[bi % len(bars)]:
                    if pos >= m.length:
                        continue
                    if key == "ST":
                        hits[(pos, "ST")] = Hit(pos, STICK, frozenset(), mods)
                        continue
                    ins, mm = resolve_hit(self.instr(key), normalize_mods(mods), self.kit)
                    hits[(pos, ins.code)] = Hit(pos, ins, mm)
            out.append(Bar(m, tuple(sorted(hits.values(), key=_hit_order))))
        self._cache[ck] = out
        return out

    def warnings(self, name, meter):
        rows, _, pmeter = self.rows_of(name)
        m = parse_meter(pmeter) if pmeter else meter
        out = []
        for k, v in rows.items():
            if k == "ST" or isinstance(v, (list, tuple)):
                continue
            w = grid_warning(str(v), m)
            if w:
                out.append(f"patroon '{name}', {k}: {w}")
        return out


def _hit_order(h):
    return (h.pos, -h.instr.staff_index, h.instr.code)


def _unknown(key, book):
    import difflib as d
    from .kit import ALIASES
    cands = sorted(set(KIT) | set(ALIASES) | set(book.kit))
    m = d.get_close_matches(key.upper(), cands, n=3)
    hint = f" Bedoel je: {', '.join(m)}?" if m else ""
    return f"onbekend instrument '{key}'.{hint} (zie 'python3 drums.py instrumenten')"


def rest_bar(meter):
    return Bar(meter, (), rest=True)


def slash_bar(meter):
    return Bar(meter, (), slashes=True)
