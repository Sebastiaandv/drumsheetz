"""Van slagen op posities naar noten en rusten met nootwaarden, punten en triolen."""
from dataclasses import dataclass, field
from fractions import Fraction as Fr
from math import gcd

from .rows import NotationError

TYPES = [(Fr(4), "whole"), (Fr(2), "half"), (Fr(1), "quarter"), (Fr(1, 2), "eighth"), (Fr(1, 4), "16th"),
         (Fr(1, 8), "32nd"), (Fr(1, 16), "64th"), (Fr(1, 32), "128th")]
POW2 = [v for v, _ in TYPES]


def is_pow2_frac(x):
    """Heeft x een noemer die een macht van 2 is? (dus zonder triolen te schrijven)"""
    d = Fr(x).denominator
    return d & (d - 1) == 0


def notate(v):
    """Nootwaarde (in kwarten) -> (type, punten) of None."""
    for base, name in TYPES:
        if v == base:
            return name, 0
        if v == base * Fr(3, 2):
            return name, 1
        if v == base * Fr(7, 4):
            return name, 2
    return None


@dataclass
class Ev:
    start: Fr
    dur: Fr                 # werkelijke duur in kwarten
    type: str
    dots: int = 0
    hits: list = field(default_factory=list)   # leeg = rust
    tuplet: tuple = None    # (actual, normal)
    tup_start: bool = False
    tup_stop: bool = False
    measure_rest: bool = False

    @property
    def is_rest(self):
        return not self.hits


def _largest_note(gap):
    """Grootste schrijfbare nootwaarde <= gap."""
    best = None
    for base in POW2:
        for mult in (Fr(7, 4), Fr(3, 2), Fr(1)):
            v = base * mult
            if v <= gap and (best is None or v > best):
                best = v
    return best


def _rests(a, b, span_start=None, compound_span=None):
    """Rusten van a tot b: steeds de grootste schrijfbare waarde (ook gepunteerd),
    net als de oorspronkelijke drum sheets."""
    out = []
    while a < b:
        v = _largest_note(b - a)
        if v is None:
            raise NotationError(f"kan rust van {b - a} kwart niet schrijven")
        out.append((a, v, v))
        a += v
    return out


def minimal_n(start, length, positions, limit=48):
    rels = [(p - start) / length for p in positions]
    for n in range(1, limit + 1):
        if all((r * n).denominator == 1 for r in rels):
            return n
    raise NotationError("verdeling te fijn om te noteren (meer dan 48 slagen in één tel)")


def _span_plain(start, length, onsets, compound):
    """Tel zonder triolen."""
    evs = []
    end = start + length
    cspan = (start, length) if compound else None
    if not onsets or onsets[0] > start:
        first = onsets[0] if onsets else end
        for a, d, v in _rests(start, first, start, cspan):
            t, dots = notate(v)
            evs.append(Ev(a, d, t, dots))
    for i, p in enumerate(onsets):
        nxt = onsets[i + 1] if i + 1 < len(onsets) else end
        v = _largest_note(nxt - p)
        t, dots = notate(v)
        evs.append(Ev(p, v, t, dots, hits=None))   # hits worden later ingevuld
        if p + v < nxt:
            for a, d, vv in _rests(p + v, nxt, start, cspan):
                t2, d2 = notate(vv)
                evs.append(Ev(a, d, t2, d2))
    return evs


def _normal_for(n, length):
    """Normal-notes voor een n-tool over 'length' kwarten, zodat de basiswaarde schrijfbaar is."""
    cands = []
    for m in range(1, 64):
        base = length / m
        if is_pow2_frac(base) and Fr(base).numerator in (1, 2, 4):
            cands.append(m)
    below = [m for m in cands if m < n]
    if below:
        return max(below)
    return min(m for m in cands if m > n) if [m for m in cands if m > n] else n


def _span_tuplet(start, length, onsets, n):
    m = _normal_for(n, length)
    base = length / m
    slot = length / n
    slots = [int((p - start) / slot) for p in onsets]
    evs = []

    def emit(k_from, k_len, is_note, pos_hit):
        k = k_from
        remaining = k_len
        first = True
        while remaining > 0:
            j = remaining
            while j > 0 and notate(j * base) is None:
                j -= 1
            if j == 0:
                raise NotationError("triool niet te noteren")
            t, dots = notate(j * base)
            note = is_note and first
            evs.append(Ev(start + k * slot, j * slot, t, dots, hits=None if note else [], tuplet=(n, m)))
            first = False
            k += j
            remaining -= j
            if is_note:
                # rest van de ruimte na een noot wordt rust
                is_note = False

    if not slots or slots[0] > 0:
        emit(0, slots[0] if slots else n, False, None)
    for i, s in enumerate(slots):
        nxt = slots[i + 1] if i + 1 < len(slots) else n
        emit(s, nxt - s, True, onsets[i])
    evs[0].tup_start = True
    evs[-1].tup_stop = True
    return evs


def voice_events(hits, meter, whole_rest_if_empty=True):
    """Slagen van één stem -> lijst Ev, de hele maat gevuld."""
    length = meter.length
    if not hits:
        if not whole_rest_if_empty:
            return []
        return [Ev(Fr(0), length, "whole", 0, measure_rest=True)]
    by_pos = {}
    for h in hits:
        by_pos.setdefault(h.pos, []).append(h)
    onsets = sorted(by_pos)
    beats = meter.beats()
    compound = meter.compound

    def ons(a, ln):
        return [p for p in onsets if a <= p < a + ln]

    spans = []
    i = 0
    while i < len(beats):
        a, ln = beats[i]
        o = ons(a, ln)
        plain = all(is_pow2_frac(p - a) for p in o)
        if not plain and not compound and i + 1 < len(beats) and beats[i + 1][1] == ln and i % 2 == 0:
            o2 = ons(a, 2 * ln)
            try:
                n2 = minimal_n(a, 2 * ln, o2)
                na = minimal_n(a, ln, o)
                nb = minimal_n(a + ln, ln, ons(a + ln, ln))
                if n2 < na + nb and n2 in (3, 5, 6, 7):
                    spans.append((a, 2 * ln, o2, False))
                    i += 2
                    continue
            except NotationError:
                pass
        spans.append((a, ln, o, plain))
        i += 1

    evs = []
    for a, ln, o, plain in spans:
        if plain or all(is_pow2_frac(p - a) for p in o):
            evs += _span_plain(a, ln, o, compound and ln == Fr(3, 2))
        else:
            n = minimal_n(a, ln, o)
            evs += _span_tuplet(a, ln, o, n)
    for e in evs:
        if e.hits is None:
            e.hits = by_pos[e.start]
    return evs


def lcm(a, b):
    return a * b // gcd(a, b)


def divisions_for(all_events, measures_lengths):
    d = 4
    for e in all_events:
        d = lcm(d, Fr(e.dur).denominator)
        d = lcm(d, Fr(e.start).denominator)
    for ln in measures_lengths:
        d = lcm(d, Fr(ln).denominator)
    return d
