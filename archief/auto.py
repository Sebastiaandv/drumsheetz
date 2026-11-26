"""Transcriptie (result.json uit ~/drumtools/transcribe.py) -> songs/<sleutel>.py

Gebruik: ~/drumtools/.venv/bin/python auto.py <sleutel> <map met result.json en drums.wav>
"""
import json, pathlib, sys
from collections import Counter
import numpy as np

META = {
    "always": ("I Will Always Love You", "Dolly Parton"),
    "crime": ("Crime Of The Century", "Supertramp"),
    "scene": ("Iedereen Is Van De Wereld", "The Scene"),
    "fields": ("Fields Of Gold", "Sting"),
    "froukje": ("Als Ik God Was", "Froukje"),
    "friend": ("You've Got a Friend", "Carole King"),
    "watch": ("Watch Over You", "Alter Bridge"),
    "letlove": ("Let Love Rule", "Lenny Kravitz"),
    "oml": ("One More Light", "Linkin Park"),
    "houme": ("Hou Me Vast (theatertour)", "De Dijk"),
    "annihilator": ("Sounds Good to Me", "Annihilator"),
}
# SUB wordt per maatsoort bepaald

key, folder = sys.argv[1], pathlib.Path(sys.argv[2])
data = json.loads((folder / "result.json").read_text())
hits, beats = data["hits"], data["beats"]

# --- maatsoort en tellen ------------------------------------------------------
bt = np.array([b[0] for b in beats])
pos = [b[1] for b in beats]
bars_len = Counter()
start = None
for i, p in enumerate(pos):
    if p == 1:
        if start is not None:
            bars_len[i - start] += 1
        start = i
meter = bars_len.most_common(1)[0][0]
ibi = float(np.median(np.diff(bt)))
bpm = int(round(60 / ibi))
half = meter == 4 and bpm > 140          # dubbel getelde tellen -> halveren
SUB = 2 if meter == 6 else 4             # 6/8: tel = 8ste -> 2 16den

# tellen uitbreiden naar voren/achteren zodat alle slagen in een maat vallen
first_db = pos.index(1)
bt = bt[first_db:]
if half:
    bt, ibi, bpm = bt[::2], ibi * 2, int(round(bpm / 2))
n0 = len(bt)
all_t = [t for v in hits.values() for t in v]
while min(all_t, default=bt[0]) < bt[0] - ibi / 4:
    bt = np.concatenate([[bt[0] - ibi], bt])
lead = len(bt) - n0  # toegevoegde tellen vooraan
pad_front = (-lead) % meter                  # aanvullen tot hele maat
for _ in range(pad_front):
    bt = np.concatenate([[bt[0] - ibi], bt])
while bt[-1] < max(all_t, default=0) + ibi:
    bt = np.append(bt, bt[-1] + ibi)
while len(bt) % meter:
    bt = np.append(bt, bt[-1] + ibi)
nbars = len(bt) // meter
steps = meter * SUB


def locate(t):
    i = int(np.searchsorted(bt, t, side="right") - 1)
    if i < 0 or i >= len(bt) - 1:
        return None
    frac = (t - bt[i]) / (bt[i + 1] - bt[i])
    s = int(round(frac * SUB))
    g = i * SUB + s
    return g if g < nbars * steps else None


# --- luidheid en toonhoogte uit de drumstem ----------------------------------
import soundfile as sf
import librosa
y, sr = sf.read(str(folder / "drums.wav"), always_2d=True)
y = y.mean(axis=1)


def loud(t):
    a = int(t * sr)
    seg = y[a:a + int(0.03 * sr)]
    return float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0


def pitch(t):
    a = int(t * sr)
    seg = y[a:a + int(0.08 * sr)]
    if len(seg) < 512:
        return 0.0
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    band = (f > 50) & (f < 500)
    return float(f[band][np.argmax(spec[band])])


grid = {}  # globale stap -> {instr: teken}


def put(g, ins, ch):
    grid.setdefault(g, {})
    if ins not in grid[g] or ch in "XxO":
        grid[g][ins] = ch


for t in hits.get("BD", []):
    g = locate(t)
    if g is not None:
        put(g, "BD", "x")

sd = [(t, loud(t)) for t in hits.get("SD", [])]
if sd:
    med = np.median([l for _, l in sd])
    for t, l in sd:
        g = locate(t)
        if g is not None:
            put(g, "SD", "g" if l < 0.35 * med else ("X" if l > 1.8 * med else "x"))

tt = [(t, pitch(t)) for t in hits.get("TT", [])]
if tt:
    ps = [p for _, p in tt]
    lo, hi = np.percentile(ps, [33, 67]) if len(set(ps)) > 2 else (min(ps), max(ps))
    for t, p in tt:
        g = locate(t)
        if g is not None:
            put(g, "FT" if p <= lo else ("T1" if p > hi else "T2"), "x")

for t in hits.get("HH", []):
    g = locate(t)
    if g is not None:
        put(g, "HH", "x")

cy = [locate(t) for t in hits.get("CY+RD", [])]
cy = [g for g in cy if g is not None]
per_bar = Counter(g // steps for g in cy)
for g in cy:
    put(g, "RD" if per_bar[g // steps] >= 4 else "CR", "x")

# --- maten als patronen -------------------------------------------------------
ORDER = ["CR", "RD", "HH", "T1", "T2", "SD", "FT", "BD"]


def bar_rows(b):
    rows = {}
    for s in range(steps):
        for ins, ch in grid.get(b * steps + s, {}).items():
            rows.setdefault(ins, ["-"] * steps)[s] = ch
    return {k: "".join(v) for k, v in sorted(rows.items(), key=lambda kv: ORDER.index(kv[0]))}


bars = [bar_rows(b) for b in range(nbars)]

# --- dynamiek per maat uit de drumstem ----------------------------------------
def span(b, h0=0.0, h1=1.0):
    t0 = bt[b * meter]
    t1 = bt[(b + 1) * meter] if (b + 1) * meter < len(bt) else bt[-1] + ibi
    a, z = t0 + (t1 - t0) * h0, t0 + (t1 - t0) * h1
    seg = y[int(a * sr):int(z * sr)]
    return 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9) if len(seg) else -120.0


bar_db = [span(b) if bars[b] else None for b in range(nbars)]
vals = [v for v in bar_db if v is not None]
ref = float(np.percentile(vals, 95)) if vals else 0.0
LEVELS = ["pp", "p", "mp", "mf", "f", "ff"]


def level_of(db, crash):
    r = db - ref
    if r >= -1 and crash:
        return 5
    return 4 if r >= -2.5 else 3 if r >= -5.5 else 2 if r >= -9 else 1 if r >= -14 else 0


lvl = [None] * nbars
nz = [b for b in range(nbars) if bar_db[b] is not None]
for k, b in enumerate(nz):
    win = [bar_db[nz[j]] for j in range(max(0, k - 2), min(len(nz), k + 3)) if abs(nz[j] - b) <= 2]
    lvl[b] = level_of(float(np.median(win)), "CR" in bars[b])
# runs korter dan 4 maten opgaan in het vorige niveau (ff mag kort: dat zijn climaxen)
changed = True
while changed:
    changed = False
    runs, k = [], 0
    while k < len(nz):
        m = k
        while m + 1 < len(nz) and lvl[nz[m + 1]] == lvl[nz[k]]:
            m += 1
        runs.append((k, m))
        k = m + 1
    for ri, (k, m) in enumerate(runs):
        if m - k + 1 < 4 and len(runs) > 1 and not (lvl[nz[k]] == 5 and m - k + 1 >= 2):
            src = runs[ri - 1] if ri > 0 else runs[ri + 1]
            for q in range(k, m + 1):
                lvl[nz[q]] = lvl[nz[src[0]]]
            changed = True
            break


def trend(a, b):
    """Luidheidsverloop binnen maten a..b-1 (dB, laatste helft min eerste helft)."""
    return span(b - 1, 0.5, 1.0) - span(a, 0.0, 0.5)


def events(r, kinds=None):
    return {(k, i) for k, v in r.items() if kinds is None or k in kinds for i, c in enumerate(v) if c != "-"}


def same(a, b):
    """Gelijk, of alleen 1 hihat/ride-slag verschil (detectieruis)."""
    if a == b:
        return True
    core = {"BD", "SD", "T1", "T2", "FT", "CR"}
    if events(a, core) != events(b, core):
        return False
    return len(events(a) ^ events(b)) <= 1


# --- delen herkennen (per 4 maten) ---------------------------------------------
def sig(bs):
    c = Counter()
    for r in bs:
        c.update(events(r, {"HH", "RD", "SD", "BD", "RS"}))
    return {e for e, n in c.items() if n >= max(1, len(bs) // 2)}


def jac(a, b):
    return len(a & b) / len(a | b) if a | b else 1.0


phrases = [bars[i:i + 4] for i in range(0, nbars, 4)]
sections = []  # (start_bar, sig)
for pi, ph in enumerate(phrases):
    s = sig(ph)
    empty = all(not r for r in ph)
    if not sections or (empty != sections[-1][2]) or jac(s, sections[-1][1]) < 0.5:
        sections.append([pi * 4, s, empty])
labels, known = [], []
for st, s, empty in sections:
    if empty:
        labels.append("Tacet")
        continue
    for name, ks in known:
        if jac(s, ks) >= 0.7:
            labels.append(name)
            break
    else:
        name = chr(ord("A") + len(known))
        known.append((name, s))
        labels.append(name)
if labels and labels[0] != "Tacet":
    pass

# --- SONG opbouwen --------------------------------------------------------------
grooves, gid = {}, {}


def gname(r):
    k = json.dumps(r, sort_keys=True)
    if k not in gid:
        gid[k] = f"b{len(gid)}"
        grooves[gid[k]] = r
    return gid[k]


song_sections, phases = [], []   # phases: (dict, startmaat, eindmaat)
bounds = [s[0] for s in sections] + [nbars]
for si, lab in enumerate(labels):
    a, b = bounds[si], bounds[si + 1]
    seq, i = [], a
    while i < b:
        r = bars[i]
        j = i + 1
        while j < b and same(bars[j], r) and lvl[j] == lvl[i]:
            j += 1
        if not r:
            ph = {"groove": None, "bars": j - i}
        else:
            ph = {"groove": gname(r), "bars": j - i, "crash": False}
        seq.append(ph)
        phases.append((ph, i, j))
        i = j
    song_sections.append({"label": lab, "seq": seq})
song_sections[-1]["end"] = True

# dynamiektekens en vorken
cur = None
played = [(ph, a, b) for ph, a, b in phases if ph["groove"] is not None]
for ph, a, b in phases:
    if ph["groove"] is None:
        cur = None
        continue
    if lvl[a] != cur:
        ph["dyn"] = LEVELS[lvl[a]]
        cur = lvl[a]
for k, (ph, a, b) in enumerate(played[:-1]):
    nph, na, nb = played[k + 1]
    if na != b:          # rust ertussen: geen vork
        continue
    d, tr = lvl[na] - lvl[a], trend(a, b)
    if d > 0 and tr >= 2.5:
        ph["wedge"] = "crescendo"
    elif d < 0 and tr <= -2.5:
        ph["wedge"] = "diminuendo"

title, artist = META[key]
song = {"title": title, "artist": artist, "subtitle": "Drum sheet",
        "bpm": int(round(bpm / 3)) if meter == 6 else bpm, "meter": (6, 8) if meter == 6 else (meter, 4),
        "feel": "Getranscribeerd uit de opname",
        "sections": song_sections}
out = pathlib.Path(__file__).parent / "songs" / f"{key}.py"
out.write_text("# Automatisch gegenereerd door auto.py uit de opname\n"
               f"SONG = {song!r}\n\nGROOVES = {grooves!r}\n\nFILLS = {{}}\n", encoding="utf-8")
print(f"{key}: {bpm} BPM{' (gehalveerd)' if half else ''}, {meter} tellen, {nbars} maten, {len(grooves)} unieke maten, delen: {' '.join(labels)}")
