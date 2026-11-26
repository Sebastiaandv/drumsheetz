"""Tekstweergave in de terminal (drumtab), zonder MuseScore: handig om snel te controleren."""
from fractions import Fraction as Fr

from .rhythm import lcm

CHAR = [(">", "X"), ("^", "^"), ("g", "g"), ("f", "f"), ("d", "d"), ("r", "r"), ("z", "z"), ("t", "t"),
        ("o", "o"), ("h", "h"), ("+", "+"), ("k", "k")]


def hit_char(h):
    if "~" in h.mods:
        return "/"
    if h.instr.code == "XS":
        return "c"
    if h.instr.code == "RIM":
        return "@"
    if h.instr.code == "RB":
        return "b"
    md = set(h.mods)
    if h.instr.code in ("HO", "HS"):
        md.discard("o")
        return "O" if ">" in md else "o"
    for m, c in CHAR:
        if m in md and m != ">":
            return c.upper() if ">" in md and c in "fdzt" else c
    return "X" if ">" in md else "x"


def bar_grid(bar, row_codes=None):
    """Maat -> lijst regels 'HH  x-x-|x-x-|...'"""
    if bar.rest:
        return ["   (rust)"]
    steps_q = 1
    for h in bar.hits:
        steps_q = lcm(steps_q, Fr(h.pos).denominator)
    base = 4 if bar.meter.den <= 4 else 2
    if base % steps_q == 0:
        steps_q = base
    if steps_q > 24:
        steps_q = 24
    total = int(bar.meter.length * steps_q)
    rows = {}
    order = {}
    for h in bar.hits:
        code = "ST" if h.instr.code == "ST" else _row_code(h.instr.code)
        rows.setdefault(code, ["-"] * total)
        order[code] = -100 if code == "ST" else h.instr.staff_index
        i = int(round(h.pos * steps_q))
        if 0 <= i < total:
            rows[code][i] = (h.text[:1] if code == "ST" else hit_char(h))
    beat_starts = {int(a * steps_q) for a, _ in bar.meter.beats()}
    out = []
    for code in sorted(rows, key=lambda c: -order[c]):
        cells = rows[code]
        s = ""
        for i, c in enumerate(cells):
            if i in beat_starts and i:
                s += "|"
            s += c
        out.append(f"   {code:<4} {s}")
    return out


def _row_code(code):
    return {"HO": "HH", "XS": "SD", "RIM": "SD", "RB": "RD", "HS": "HF"}.get(code, code)


def show_score(score, print=print):
    song = score.song
    print(f"{song.get('title', '?')} — {song.get('artist', '')}")
    from .project import fmt_duration
    print(f"   {score.meter}  tempo {score.tempo[0]}  ·  {score.total_bars} maten  ·  ± {fmt_duration(score.seconds())}")
    if song.get("feel"):
        print(f"   {song['feel']}")
    for m in score.measures:
        heads = [s for s in m.start if s[0] in ("rehearsal",)]
        for s in heads:
            print(f"\n[{s[1]}]")
        extra = [s[1] if s[0] in ("words", "dyn", "wedge") else s[0] for s in m.start
                 if s[0] in ("words", "dyn", "wedge", "segno", "coda")]
        nums = f"{m.number}" if m.pct < 2 else f"{m.number}-{m.number + m.pct - 1}"
        flags = []
        if m.left_repeat:
            flags.append("|:")
        if m.ending_start:
            flags.append(f"volta {','.join(map(str, m.ending_start))}")
        if m.right_repeat:
            flags.append(f":| {m.right_repeat}×")
        for e in m.end:
            if e[0] == "jump":
                flags.append(e[1])
        if m.pct:
            if m.pct_first:
                unit = f" ({m.pct_unit} maten)" if m.pct_unit > 1 else ""
                print(f" {nums:>7}: %{unit}  {m.pct // m.pct_unit}×  " + " ".join(flags))
            continue
        if m.multirest:
            if m.multirest > 1:
                print(f" {f'{m.number}-{m.number + m.multirest - 1}':>7}: rust ({m.multirest} maten)")
            else:
                print(f" {m.number:>7}: rust")
            continue
        if m.bar.rest:
            continue
        info = ("  " + " · ".join(str(x) for x in extra)) if extra else ""
        print(f" {nums:>7}: {' '.join(flags)}{info}")
        for line in bar_grid(m.bar):
            print("        " + line)
