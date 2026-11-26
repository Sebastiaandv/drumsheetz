"""MIDI-bestand om mee te oefenen: alle herhalingen uitgeschreven, met dynamiek, accenten,
ghost notes, flams, roffels en (optioneel) aftellen, klik en een oefentempo."""
import struct
from fractions import Fraction as Fr

TPQ = 480
DYN_VEL = {"pppp": 25, "ppp": 32, "pp": 42, "p": 55, "mp": 70, "mf": 85, "f": 100, "ff": 112, "fff": 122,
           "ffff": 127, "sfz": 115, "sf": 110, "fp": 100, "sfp": 110, "rfz": 110, "fz": 110}


def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _swing(pos, beats, mode):
    if not mode:
        return pos
    for a, ln in beats:
        if a <= pos < a + ln:
            rel = (pos - a) / ln
            if mode == "8" and rel == Fr(1, 2):
                return a + ln * Fr(2, 3)
            if mode == "16":
                if rel == Fr(1, 4):
                    return a + ln * Fr(1, 3)
                if rel == Fr(3, 4):
                    return a + ln * Fr(5, 6)
            return pos
    return pos


def build_midi(score, tempo_pct=100, countin=0, click=False):
    sw = str(score.song.get("swing", "") or "").lower()
    swing = "16" if sw in ("16", "16den", "16ths") else ("8" if sw and sw not in ("nee", "no", "0") else "")
    events = []   # (tick, order, bytes)
    t = Fr(0)
    last_qpm = None
    last_meter = None
    played = list(score.played)
    if countin:
        from .arrange import Played, click_bar
        first = played[0]
        played = [Played(click_bar(first.bar.meter), first.qpm, "mf", "aftellen")] * countin + played
    scale = tempo_pct / 100.0
    for p in played:
        qpm = p.qpm * scale
        tick0 = int(t * TPQ)
        if qpm != last_qpm:
            us = int(round(60_000_000 / qpm))
            events.append((tick0, 0, b"\xff\x51\x03" + us.to_bytes(3, "big")))
            last_qpm = qpm
        m = p.bar.meter
        if m != last_meter:
            dd = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4, 32: 5}[m.den]
            events.append((tick0, 0, bytes([0xFF, 0x58, 0x04, m.num, dd, 24, 8])))
            last_meter = m
        base = DYN_VEL.get(p.dyn, 85)
        beats = m.beats()
        hits = sorted(p.bar.hits, key=lambda h: h.pos)
        hand_onsets = sorted({h.pos for h in hits if not h.is_foot})
        for h in hits:
            if not h.instr.midi:
                continue
            md = h.mods
            vel = base
            if "g" in md:
                vel = max(20, base // 2 - 5)
            if ">" in md:
                vel = min(127, base + 25)
            if "^" in md:
                vel = 127
            pos = _swing(h.pos, beats, swing)
            tick = int((t + pos) * TPQ)
            note = h.instr.midi
            graces = 1 if "f" in md else 2 if "d" in md else 3 if "r" in md else 0
            for g in range(graces, 0, -1):
                events.append((max(0, tick - g * 35), 1, bytes([0x99, note, max(20, vel // 2)])))
                events.append((max(0, tick - g * 35) + 20, 2, bytes([0x89, note, 0])))
            if "z" in md or "t" in md:
                nxt = next((o for o in hand_onsets if o > h.pos), None)
                beat_end = next((a + ln for a, ln in beats if a <= h.pos < a + ln), m.length)
                end = min(nxt, beat_end) if nxt is not None else beat_end
                step = Fr(1, 8) if "t" in md else Fr(1, 12)
                q = h.pos
                first = True
                while q < end:
                    tk = int((t + q) * TPQ)
                    events.append((tk, 1, bytes([0x99, note, vel if first else max(25, vel * 2 // 3)])))
                    events.append((tk + 15, 2, bytes([0x89, note, 0])))
                    q += step
                    first = False
                continue
            events.append((tick, 1, bytes([0x99, note, vel])))
            events.append((tick + TPQ // 8, 2, bytes([0x89, note, 0])))
        if click:
            for i, (a, _) in enumerate(beats):
                tk = int((t + a) * TPQ)
                n = 76 if i == 0 else 77
                events.append((tk, 1, bytes([0x99, n, 100 if i == 0 else 75])))
                events.append((tk + 30, 2, bytes([0x89, n, 0])))
        t += m.length
    end_tick = int(t * TPQ)
    events.sort(key=lambda e: (e[0], e[1]))
    track = bytearray()
    prev = 0
    title = (score.song.get("title", "") or "").encode("utf-8")[:120]
    track += _vlq(0) + b"\xff\x03" + _vlq(len(title)) + title
    for tick, _, data in events:
        track += _vlq(max(0, tick - prev)) + data
        prev = max(prev, tick)
    track += _vlq(max(0, end_tick - prev)) + b"\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, TPQ) + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)
