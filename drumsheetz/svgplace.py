"""Meet in een SVG-export van MuseScore waar de %-tekens staan, zodat de 'N×'-tellers er precies
rechts naast kunnen. (De breedte van een maat is pas na de opmaak van MuseScore bekend.)"""
import re

NUM = re.compile(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?")
ELEM = re.compile(r"<(path|text|polyline|line)\b([^>]*?)(/>|>(.*?)</\1>)", re.S)
ATTR = re.compile(r'([\w:-]+)="([^"]*)"')
REPEAT_CLASSES = {"MeasureRepeat", "RepeatMeasure"}
BARLINE_CLASSES = {"BarLine"}


def _matrix(tr):
    if not tr:
        return None
    m = re.search(r"matrix\(([^)]*)\)", tr)
    if m:
        v = [float(x) for x in NUM.findall(m.group(1))]
        if len(v) == 6:
            return v
    m = re.search(r"translate\(([^)]*)\)", tr)
    if m:
        v = [float(x) for x in NUM.findall(m.group(1))] + [0.0]
        return [1, 0, 0, 1, v[0], v[1]]
    return None


def _apply(mx, x, y):
    if not mx:
        return x, y
    a, b, c, d, e, f = mx
    return a * x + c * y + e, b * x + d * y + f


def _bbox(pts):
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def parse(svg_text):
    """-> (notenbalken, %-tekens, teksten) met kaders (x0, y0, x1, y1)."""
    lines, repeats, texts, bars = [], [], [], []
    for tag, attrs, _, inner in ELEM.findall(svg_text):
        a = dict(ATTR.findall(attrs))
        cls = a.get("class", "")
        mx = _matrix(a.get("transform"))
        if cls == "StaffLines":
            nums = [float(x) for x in NUM.findall(a.get("points", "") or " ".join(a.get(k, "") for k in ("x1", "y1", "x2", "y2")))]
            pts = [_apply(mx, nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
            bb = _bbox(pts)
            if bb:
                lines.append(bb)
            continue
        if cls not in REPEAT_CLASSES and cls != "StaffText" and cls not in BARLINE_CLASSES:
            continue
        if tag in ("polyline", "line"):
            nums = [float(x) for x in NUM.findall(a.get("points", "") or " ".join(a.get(k, "") for k in ("x1", "y1", "x2", "y2")))]
            bb = _bbox([_apply(mx, nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)])
        elif tag == "path":
            nums = [float(x) for x in NUM.findall(re.sub(r"[A-Za-z]", " ", a.get("d", "")))]
            pts = [_apply(mx, nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
            bb = _bbox(pts)
        elif tag == "text":
            x, y = float(a.get("x", 0) or 0), float(a.get("y", 0) or 0)
            size = float(NUM.findall(a.get("font-size", "") or "12")[0]) if NUM.findall(a.get("font-size", "") or "12") else 12
            n = len(re.sub(r"<[^>]+>", "", inner or "").strip()) or 2
            (x0, y0), (x1, y1) = _apply(mx, x, y - size * 0.75), _apply(mx, x + n * size * 0.55, y)
            bb = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        else:
            bb = None
        if not bb:
            continue
        if cls in BARLINE_CLASSES:
            bars.append(bb)
        else:
            (repeats if cls in REPEAT_CLASSES else texts).append(bb)
    return group_staves(lines), repeats, texts, bars


def group_staves(lines):
    """Notenbalklijnen (horizontaal) groeperen tot balken van 5 lijnen."""
    ys = sorted({(round(b[1], 1), round(b[0], 1), round(b[2], 1)) for b in lines})
    staves, cur = [], []
    for y, x0, x1 in ys:
        if cur and (len(cur) == 5 or abs((y - cur[-1][0]) - (cur[1][0] - cur[0][0] if len(cur) > 1 else y - cur[-1][0])) > 1.5
                    or y - cur[-1][0] > 60):
            staves.append(cur)
            cur = []
        cur.append((y, x0, x1))
    if cur:
        staves.append(cur)
    out = []
    for s in staves:
        if len(s) >= 5:
            sp = (s[-1][0] - s[0][0]) / (len(s) - 1)
            out.append({"top": s[0][0], "bottom": s[-1][0], "left": min(x for _, x, _ in s),
                        "right": max(x for _, _, x in s), "sp": sp})
    return out


def merge(boxes, tol):
    """Een tekst met kader bestaat in de SVG uit meerdere stukken (kader + letters): samenvoegen."""
    out = []
    for b in boxes:
        if out and b[0] <= out[-1][2] + tol and b[1] <= out[-1][3] + tol and b[3] >= out[-1][1] - tol:
            o = out[-1]
            out[-1] = (min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3]))
        else:
            out.append(b)
    return out


def count_shifts(svg_pages, gap_sp=0.6):
    """Voor elke teller (in volgorde van het stuk): hoeveel spatiums hij naar rechts moet,
    of None als er geen %-teken bij gevonden werd."""
    result = []
    for svg in svg_pages:
        staves, repeats, texts, bars = parse(svg)
        found = []
        for si, st in enumerate(staves):
            def on_staff(bb):
                cy = (bb[1] + bb[3]) / 2
                return st["top"] - 0.2 * st["sp"] <= cy <= st["bottom"] + 0.2 * st["sp"] and \
                    bb[2] >= st["left"] and bb[0] <= st["right"]
            cnt = merge(sorted([t for t in texts if on_staff(t)], key=lambda b: b[0]), 0.4 * st["sp"])
            reps = sorted([r for r in repeats if on_staff(r)], key=lambda b: b[0])
            for t in cnt:
                cands = [r for r in reps if r[0] >= t[0] - 0.5 * st["sp"]]
                if not cands:
                    found.append((si, t[0], None))
                    continue
                r = cands[0]
                sp = st["sp"]
                width = t[2] - t[0]
                bar_x = min([b[0] for b in bars if on_staff(b) and b[0] > (r[0] + r[2]) / 2] + [st["right"]])
                target = r[2] + gap_sp * sp                       # rechts van het %-teken
                left = r[0] - gap_sp * sp - width
                prev_bar = max([b[2] for b in bars if on_staff(b) and b[2] < (r[0] + r[2]) / 2] + [st["left"]])
                if target + width > bar_x - 0.3 * sp and left > prev_bar + 0.3 * sp:   # rechts past niet, links wel
                    target = left
                shift = (target - t[0]) / sp
                found.append((si, t[0], shift))
        found.sort(key=lambda f: (f[0], f[1]))
        result += [f[2] for f in found]
    return result
