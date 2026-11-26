"""Voorblad en podiumlijst voor setlists (met reportlab)."""
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .project import fmt_duration

W, H = A4
M = 50


def _fit(text, font, size, width):
    while stringWidth(text, font, size) > width and len(text) > 3:
        text = text[:-2] + "…" if not text.endswith("…") else text[:-2] + "…"
    return text


def cover(path, meta, entries):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(meta.get("title", "Setlist"))
    y = H - M

    def header():
        nonlocal y
        c.setFont("Times-Roman", 24)
        c.drawCentredString(W / 2, y - 10, meta.get("title", "Setlist"))
        y -= 34
        sub = " · ".join(x for x in (meta.get("date", ""), meta.get("place", ""), meta.get("band", "")) if x)
        if sub:
            c.setFont("Times-Roman", 12)
            c.drawCentredString(W / 2, y, sub)
            y -= 18
        if meta.get("notes"):
            c.setFont("Times-Italic", 11)
            c.drawCentredString(W / 2, y, meta["notes"])
            y -= 18
        y -= 12

    cols = [(M, "#"), (M + 20, "Titel"), (M + 188, "Artiest"), (M + 292, "Tempo"), (M + 326, "Maat"),
            (M + 356, "Duur"), (M + 392, "Notitie")]

    def table_head():
        nonlocal y
        c.setFont("Times-Bold", 10)
        for x, t in cols:
            c.drawString(x, y, t)
        y -= 4
        c.setLineWidth(0.6)
        c.line(M, y, W - M, y)
        y -= 14

    header()
    n, tot, sub_tot, in_set = 0, 0.0, 0.0, False
    need_head = True

    def subtotal():
        nonlocal y
        c.setFont("Times-Italic", 10)
        c.drawRightString(M + 386, y, f"subtotaal {fmt_duration(sub_tot)}")
        y -= 20

    for e in entries:
        if y < M + 60:
            c.showPage()
            y = H - M
            need_head = True
        if e.kind == "break":
            if in_set and sub_tot:
                subtotal()
            # blokje met tekst, net als de oefenletters op de sheets
            c.setFont("Times-Bold", 13)
            tw = stringWidth(e.display, "Times-Bold", 13)
            c.setLineWidth(1)
            c.rect(M - 4, y - 5, tw + 8, 19)
            c.drawString(M, y, e.display)
            y -= 26
            sub_tot, in_set, need_head = 0.0, True, True
            continue
        if need_head:
            table_head()
            need_head = False
        n += 1
        tot += e.duration or 0
        sub_tot += e.duration or 0
        c.setFont("Times-Bold", 11)
        c.drawString(cols[0][0], y, str(n))
        c.drawString(cols[1][0], y, _fit(e.title, "Times-Bold", 11, 164))
        c.setFont("Times-Roman", 10)
        c.drawString(cols[2][0], y, _fit(e.artist, "Times-Roman", 10, 100))
        c.drawString(cols[3][0], y, str(e.bpm))
        c.drawString(cols[4][0], y, str(e.meter))
        c.drawString(cols[5][0], y, fmt_duration(e.duration) if e.duration else "?")
        c.setFont("Times-Italic", 9)
        c.drawString(cols[6][0], y, _fit(e.note, "Times-Italic", 9, W - M - cols[6][0]))
        y -= 17
    if in_set and sub_tot:
        subtotal()
    y -= 6
    c.setLineWidth(0.6)
    c.line(M, y + 10, W - M, y + 10)
    c.setFont("Times-Bold", 11)
    c.drawString(M, y - 4, f"{n} nummers")
    c.drawRightString(W - M, y - 4, f"totale speelduur ± {fmt_duration(tot)}")
    c.save()


def podium(path, meta, entries):
    """Eén pagina met grote letters om op de grond te leggen."""
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(meta.get("title", "Setlist") + " (podium)")
    lines = []
    n = 0
    for e in entries:
        if e.kind == "break":
            lines.append(("break", e.display))
        else:
            n += 1
            lines.append(("song", f"{n}. {e.title}", f"{e.bpm}" if e.bpm else ""))
    avail = H - 2 * M - 30
    size = min(40, avail / max(1, len(lines)) / 1.25)
    longest = max([stringWidth(l[1], "Helvetica-Bold", 10) for l in lines] + [1])
    size = min(size, (W - 2 * M - 70) / longest * 10)
    c.setFont("Helvetica", 12)
    c.drawString(M, H - M, meta.get("title", ""))
    y = H - M - 20 - size
    for item in lines:
        if item[0] == "break":
            c.setFont("Helvetica-Oblique", size * 0.6)
            c.drawString(M, y + size * 0.2, f"— {item[1]} —")
            y -= size * 1.0
            continue
        c.setFont("Helvetica-Bold", size)
        c.drawString(M, y, item[1])
        if item[2]:
            c.setFont("Helvetica", size * 0.5)
            c.drawRightString(W - M, y, f"♩ {item[2]}".replace("♩", "") + " bpm")
        y -= size * 1.25
    c.save()
