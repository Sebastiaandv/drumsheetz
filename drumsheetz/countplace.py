"""'N×'-tellers bij de %-tekens netjes plaatsen: kaarsrecht boven het %-teken, of strak ernaast (rechts of links).

Werkwijze (zonder te gokken uit een tekening):
  1. MuseScore maakt de opmaak en geeft de posities van alle maten (.mpos) en van alle notensegmenten (.spos).
  2. Het %-teken staat bij MuseScore altijd midden in de maat: tussen het begin van de maat (of na sleutel/
     maatsoort aan het begin van een regel) en de maatstreep. Een 2- of 4-maats-% staat op de maatstreep in het
     midden van de groep. Zo rekent MuseScore het zelf ook (Measure::layoutMeasureElements).
  3. De teller hangt aan het eerste segment van de maat; zijn offset is dus (doel − segment) in spatiums.
     Hij wordt UITGELIJND op het doel (midden / links / rechts), zodat zijn breedte niet geschat hoeft te worden.
  4. Past een teller niet naast het %-teken, dan krijgt alleen die maat precies genoeg extra breedte en wordt
     er opnieuw gemeten. Past hij dan nog niet: kaarsrecht erboven.
"""
import json
import re
import xml.etree.ElementTree as ET

GLYPH_HALF = 1.45        # halve breedte van het %-teken (repeat1Bar), in spatiums
GAP = 0.35               # ruimte tussen %-teken en teller
EDGE = 0.35              # minimaal vrij van de maatstreep
LEAD = 1.0               # ruimte tussen sleutel/maatsoort en de eerste noot aan het begin van een regel
Y_INSIDE = 2.55          # basislijn in de balk (spatiums onder de bovenste lijn): cijfers rond de middelste lijn
Y_ABOVE = -1.0           # basislijn boven de balk

STYLE = ('<autoplace>0</autoplace><align>{align},baseline</align><offset x="{x}" y="{y}"/>'
         '<frameType>1</frameType><frameWidth>0</frameWidth><framePadding>0.15</framePadding>'
         '<frameFgColor r="255" g="255" b="255" a="0"/><frameBgColor r="255" g="255" b="255" a="255"/>')

COUNT_RE = re.compile(r"(<StaffText(?: [^>]*)?>)((?:(?!</StaffText>).)*?)"
                      r"(<text>(?:<[^>]+>)*\s*(\d+)\s*(?:×|&#215;|&#xd7;|&times;|x)\s*(?:<[^>]+>)*</text>)", re.S | re.I)
_REMOVE = re.compile(r"\s*<(autoplace|offset|frameType|frameWidth|framePadding|frameFgColor|frameBgColor|placement|align)"
                     r"\b[^>]*?(?:/>|>[^<]*</\1>)")
MEASURE_RE = re.compile(r"<Measure(?: [^>]*)?>.*?</Measure>", re.S)


def style_count(body, x, y, align):
    """De (eerste) teller in een maat de gegeven plek geven."""
    def sub(m):
        return m.group(1) + _REMOVE.sub("", m.group(2)) + STYLE.format(align=align, x=round(x, 2), y=y) + m.group(3)
    return COUNT_RE.subn(sub, body, count=1)


def edit_measures(text, fn):
    """fn(index, maattekst) -> nieuwe maattekst, voor elke maat van de eerste notenbalk.
    Samenvattingsmaten van een rustgroep (<multiMeasureRest>) tellen niet mee (zoals bij MuseScore zelf)."""
    try:
        start = text.index('<Staff id="1">', text.index("</Part>"))
        end = text.index("</Staff>", start)
    except ValueError:
        return text
    idx = [-1]

    def repl(m):
        body = m.group(0)
        if "<multiMeasureRest>" in body:
            return body
        idx[0] += 1
        return fn(idx[0], body)
    return text[:start] + MEASURE_RE.sub(repl, text[start:end]) + text[end:]


def display_map(mscx):
    """Maatnummer in het bestand -> maatnummer zoals getekend (.mpos). Een rustgroep ('4 maten rust') staat in het
    bestand als echte maten plus een samenvattingsmaat (<multiMeasureRest>N) direct na de eerste; getekend is
    de hele groep één maat."""
    out, d, covered = [], 0, 0
    try:
        start = mscx.index('<Staff id="1">', mscx.index("</Part>"))
        end = mscx.index("</Staff>", start)
    except ValueError:
        return None
    for m in MEASURE_RE.finditer(mscx, start, end):
        mm = re.search(r"<multiMeasureRest>(\d+)</multiMeasureRest>", m.group(0))
        if mm:
            covered = max(0, int(mm.group(1)) - 1)     # de eerste echte maat is al geteld
            continue
        if covered:
            covered -= 1
            out.append(d - 1)
        else:
            out.append(d)
            d += 1
    return out


def parse_positions(text):
    """.mpos/.spos → [(x, y, sx, sy, page)] in volgorde."""
    out = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return out
    for el in root.iter("element"):
        try:
            out.append((float(el.get("x", 0)), float(el.get("y", 0)), float(el.get("sx", 0)), float(el.get("sy", 0)),
                        int(float(el.get("page", 0)))))
        except ValueError:
            continue
    return out


def first_segments(measures, segments):
    """Per maat het eerste notensegment (x), door beide lijsten in volgorde door te lopen."""
    out, j = [], 0
    for (mx, my, msx, _msy, mp) in measures:
        found = None
        k = j
        while k < len(segments):
            sx_, sy_, _, _, sp_ = segments[k]
            if sp_ == mp and abs(sy_ - my) < 1 and mx - 1 <= sx_ <= mx + msx + 1:
                found = sx_
                j = k + 1
                break
            if sp_ > mp or (sp_ == mp and sy_ > my + 1):
                break                              # al voorbij deze maat: maat zonder segment
            k += 1
        out.append(found)
    return out


def spatium_mm(mscx):
    m = re.search(r"<Spatium>([\d.]+)</Spatium>", mscx)
    return float(m.group(1)) if m else 1.75


UNIT_CANDIDATES = (3600.0, 1200.0, 600.0, 300.0, 144.0, 100.0, 96.0, 72.0)   # eenheden per inch in .mpos/.spos


def units_per_spatium(measures, sp_mm):
    """Hoeveel .mpos-eenheden één spatium is. NIET uit de hoogte van een maat halen: dat is de hoogte van de hele
    regel (bij MuseScore 4 meer dan de notenbalk). Wel: de spatium in mm uit het bestand, en de eenheid per inch
    waarbij de breedste regel een echte paginabreedte heeft (A4/Letter: 5,5 tot 8,6 inch bedrukbaar)."""
    lines = {}
    for x, y, w, _h, p in measures:
        lo, hi = lines.get((p, round(y)), (x, x + w))
        lines[(p, round(y))] = (min(lo, x), max(hi, x + w))
    widest = max((hi - lo for lo, hi in lines.values()), default=0)
    if widest > 0:
        for dpi in UNIT_CANDIDATES:
            if 5.5 <= widest / dpi <= 8.6:
                return sp_mm / 25.4 * dpi, dpi
    return None, None


def text_width_sp(n_chars, size_pt, sp_mm):
    return n_chars * 0.62 * size_pt * 0.3528 / sp_mm


def plan(mscx, mpos, spos, counts, mode, font_pt=10.0):
    """Bereken per tellermaat: (x-offset, y, uitlijning, extra breedte nodig of 0).
    counts: {maatindex: (eenheid, tekst)}; mode: 'boven', 'rechts' of 'links'."""
    measures, segments = parse_positions(mpos), parse_positions(spos)
    if not measures or not segments:
        return None
    segs = first_segments(measures, segments)
    spmm = spatium_mm(mscx)
    sp_units, dpi = units_per_spatium(measures, spmm)
    dmap = display_map(mscx) or []
    result = {}
    for real, (unit, label) in counts.items():
        idx = dmap[real] if real < len(dmap) else real
        if idx >= len(measures) or segs[idx] is None:
            continue
        mx, my, msx, msy, mp = measures[idx]
        sp = sp_units or ((msy / 4.0) if msy > 0 else 250.0)
        seg = segs[idx]
        first_in_system = not any(p == mp and abs(y - my) < 1 and x < mx - 1 for (x, y, _, _, p) in measures)
        x1 = (seg - LEAD * sp) if first_in_system else mx
        x2 = mx + msx
        center = (x1 + x2) / 2
        if unit and unit > 1 and unit % 2 == 0:      # 2/4-maats-%: op de maatstreep midden in de groep
            def same_line(k):
                return k < len(measures) and abs(measures[k][1] - my) < 1 and measures[k][4] == mp
            mid, last = idx + unit // 2 - 1, idx + unit - 1
            if same_line(mid):
                center = measures[mid][0] + measures[mid][2]
            if same_line(last):
                x2 = measures[last][0] + measures[last][2]
        tw = text_width_sp(len(label), font_pt, spmm) * sp
        need = 0.0
        if mode == "boven":
            target, align, y = center, "center", Y_ABOVE
        elif mode == "links":
            target, align, y = center - (GLYPH_HALF + GAP) * sp, "right", Y_INSIDE
            room = (target - tw) - (x1 + EDGE * sp)
            if room < 0:
                need = -room
        else:
            target, align, y = center + (GLYPH_HALF + GAP) * sp, "left", Y_INSIDE
            room = (x2 - EDGE * sp) - (target + tw)
            if room < 0:
                need = -room
        result[real] = {"x": (target - seg) / sp, "y": y, "align": align, "need": need / sp if need else 0.0,
                       "width": msx / sp, "center": (center - seg) / sp, "sp": round(sp, 2), "dpi": dpi or 0}
    return result


def above(entry):
    """Terugval: kaarsrecht boven het %-teken."""
    return dict(entry, x=entry["center"], y=Y_ABOVE, align="center", need=0.0)


def apply(mscx, placements):
    """Plaatsingen toepassen; geeft (nieuwe tekst, aantal geplaatst)."""
    n = [0]

    def fn(i, body):
        p = placements.get(i)
        if not p:
            return body
        body, k = style_count(body, p["x"], p["y"], p["align"])
        n[0] += k
        return body
    return edit_measures(mscx, fn), n[0]


def add_stretch(mscx, stretches):
    """Alleen de maten die het nodig hebben iets breder maken (<stretch>)."""
    def fn(i, body):
        s = stretches.get(i)
        if not s:
            return body
        body = re.sub(r"\s*<stretch>[^<]*</stretch>", "", body)
        return body.replace(">", f">\n          <stretch>{round(s, 2)}</stretch>", 1)
    return edit_measures(mscx, fn)


def debug_report(placements, mode):
    return json.dumps({"mode": mode, "tellers": {str(k): {kk: (round(vv, 2) if isinstance(vv, float) else vv)
                                                          for kk, vv in v.items()} for k, v in placements.items()}},
                      indent=1, ensure_ascii=False)
