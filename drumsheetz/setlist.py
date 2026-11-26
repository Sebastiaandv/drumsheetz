"""Setlists: een lijst nummers -> genummerde PDF's, één compleet boek met voorblad, een podiumlijst
en een overzicht met tempo's, maatsoorten en (geschatte) duur.

Formaat (setlists/<naam>.txt):

    titel: Bruiloft Anna & Tom
    datum: 12 juni 2026
    plaats: De Boerderij, Utrecht
    notitie: In-ears mee!

    [Set 1]
    always                        | rustig beginnen, brushes
    crime
    Iedereen is van de wereld     | lang uitspelen
    archief/pdf-gekocht/Somebody-To-Love_Queen.pdf = Queen - Somebody To Love [4:56]

    [Pauze 20 min]

    [Set 2]
    letlove
"""
import pathlib
import re
import shutil

from .project import fmt_duration, parse_duration, quick_meta, safe_filename
from .rows import NotationError

META_KEYS = {"titel": "title", "title": "title", "naam": "title", "datum": "date", "date": "date",
             "plaats": "place", "locatie": "place", "venue": "place", "notitie": "notes", "notes": "notes",
             "band": "band", "tussenpauze": "gap", "wissel": "gap"}


class Entry:
    def __init__(self, kind, ref="", display="", note="", duration=None, line=0):
        self.kind, self.ref, self.display, self.note, self.duration, self.line = kind, ref, display, note, duration, line
        self.path = None       # .drum/.py of extern .pdf
        self.title = self.artist = ""
        self.bpm = self.meter = self.key = ""
        self.pdf = None


def parse_setlist(text, name="setlist"):
    meta, entries = {"title": name}, []
    for ln, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip() if not raw.strip().startswith("#") else ""
        if not line:
            continue
        m = re.match(r"^([\w\-]+)\s*:\s*(.*)$", line)
        if m and m.group(1).lower() in META_KEYS and not entries:
            meta[META_KEYS[m.group(1).lower()]] = m.group(2).strip()
            continue
        m = re.match(r"^(?:\[(.*)\]|[-=]{3,}\s*(.*?)\s*[-=]*)$", line)
        if m:
            entries.append(Entry("break", display=(m.group(1) or m.group(2) or "").strip(), line=ln))
            continue
        if re.match(r"^(pauze|break|pause)\b", line, re.I):
            entries.append(Entry("break", display=line, line=ln))
            continue
        dur = None
        dm = re.search(r"\[(\d+:\d{2})\]", line)
        if dm:
            dur = parse_duration(dm.group(1))
            line = (line[:dm.start()] + line[dm.end():]).strip()
        ref, _, note = line.partition("|")
        ref, _, display = ref.partition("=")
        entries.append(Entry("song", ref.strip(), display.strip(), note.strip(), dur, ln))
    return meta, entries


def resolve(project, entries, setfile=None):
    """Zoek bij elke regel het nummer of het externe PDF-bestand."""
    files = project.song_files()
    errors = []
    for e in entries:
        if e.kind != "song":
            continue
        if e.ref.lower().endswith(".pdf"):
            p = pathlib.Path(e.ref)
            cands = [p, project.root / p]
            if setfile:
                cands.append(pathlib.Path(setfile).parent / p)
            cands.append(project.root / "extern" / p)
            found = next((c for c in cands if c.exists()), None)
            if not found:
                errors.append(f"regel {e.line}: PDF '{e.ref}' niet gevonden")
                continue
            e.kind, e.path, e.pdf = "pdf", found, found
            disp = e.display or found.stem.replace("_", " - ").replace("-", " ")
            if " - " in disp:
                e.artist, e.title = [x.strip() for x in disp.split(" - ", 1)]
            else:
                e.title = disp
            continue
        try:
            e.path = project.find(e.ref, files)
        except NotationError as err:
            errors.append(f"regel {e.line}: {err.msg}")
            continue
        meta = quick_meta(e.path)
        e.title = meta.get("title", e.path.stem)
        e.artist = meta.get("artist", "")
        if e.display:
            if " - " in e.display:
                e.artist, e.title = [x.strip() for x in e.display.split(" - ", 1)]
            else:
                e.title = e.display
    return errors


def enrich(project, entries, scores):
    """Tempo, maatsoort, duur en (eventueel) eigen PDF uit het geladen nummer halen."""
    for e in entries:
        if e.kind != "song" or e.path is None:
            continue
        sc = scores.get(str(e.path))
        if sc is None:
            continue
        song = sc.song
        e.bpm = str(sc.tempo[0])
        e.meter = str(sc.meter).split(" ")[0]
        e.key = song.get("key", "")
        if e.duration is None:
            e.duration = parse_duration(song["duration"]) if song.get("duration") else sc.seconds()
        ext = song.get("pdf")
        if ext:
            p = project.root / ext
            if p.exists():
                e.pdf = p
                continue
        e.pdf = project.out_file("pdf", e.path, "pdf")


def overview_lines(meta, entries):
    out = [f"# {meta.get('title', 'Setlist')}"]
    sub = " · ".join(x for x in (meta.get("date", ""), meta.get("place", ""), meta.get("band", "")) if x)
    if sub:
        out.append(sub)
    if meta.get("notes"):
        out.append(f"_{meta['notes']}_")
    out.append("")
    n, tot, set_tot, set_name = 0, 0.0, 0.0, None

    def close():
        if set_name is not None or set_tot:
            out.append(f"|   | **subtotaal** | | | | **{fmt_duration(set_tot)}** | |")
            out.append("")

    header = "| # | Titel | Artiest | Tempo | Maat | Duur | Notitie |\n|---|---|---|---|---|---|---|"
    started = False
    for e in entries:
        if e.kind == "break":
            if started:
                close()
            out.append(f"## {e.display}")
            out.append("")
            set_name, set_tot, started = e.display, 0.0, False
            continue
        if not started:
            out.append(header)
            started = True
        n += 1
        d = fmt_duration(e.duration) if e.duration else "?"
        tot += e.duration or 0
        set_tot += e.duration or 0
        out.append(f"| {n} | {e.title} | {e.artist} | {e.bpm} | {e.meter} | {d} | {e.note} |")
    if started and set_name is not None:
        close()
    out.append("")
    out.append(f"**{n} nummers · totale speelduur ± {fmt_duration(tot)}**")
    return out


def numbered_name(i, e):
    base = f"{e.artist} - {e.title}" if e.artist else e.title
    return f"{i:02d} {safe_filename(base)}.pdf"


def make_outputs(project, name, meta, entries, log=print):
    folder = project.out("setlists", name)
    if folder.exists():
        for p in folder.glob("*.pdf"):
            p.unlink()
    folder.mkdir(parents=True, exist_ok=True)
    songs = [e for e in entries if e.kind in ("song", "pdf")]
    copied = []
    for i, e in enumerate(songs, 1):
        if e.pdf and pathlib.Path(e.pdf).exists():
            dst = folder / numbered_name(i, e)
            shutil.copyfile(e.pdf, dst)
            copied.append((i, e, dst))
        else:
            log(f"  ! geen PDF voor {e.title} (MuseScore nodig: python3 drums.py maak)")
    md = project.out("setlists", f"{name}.md")
    md.write_text("\n".join(overview_lines(meta, entries)) + "\n", encoding="utf-8")
    log(f"✓ overzicht: {md.relative_to(project.root)}")
    log(f"✓ {len(copied)} genummerde PDF's in {folder.relative_to(project.root)}/")
    cover = podium = None
    try:
        from . import setlist_pdf
        cover = project.out("setlists", f"{name} - overzicht.pdf")
        setlist_pdf.cover(cover, meta, entries)
        podium = project.out("setlists", f"{name} - podium.pdf")
        setlist_pdf.podium(podium, meta, entries)
        log(f"✓ voorblad: {cover.relative_to(project.root)}")
        log(f"✓ podiumlijst (grote letters): {podium.relative_to(project.root)}")
    except ImportError:
        cover = None
        log("  ! voorblad/podiumlijst overgeslagen: installeer reportlab (pip3 install reportlab)")
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        log("  ! compleet boek overgeslagen: installeer pypdf (pip3 install pypdf)")
        return
    w = PdfWriter()
    page = 0
    if cover and cover.exists():
        r = PdfReader(str(cover))
        for p in r.pages:
            w.add_page(p)
        w.add_outline_item("Overzicht", 0)
        page = len(r.pages)
    for i, e, path in copied:
        r = PdfReader(str(path))
        for p in r.pages:
            w.add_page(p)
        w.add_outline_item(f"{i}. {e.title}", page)
        page += len(r.pages)
    full = project.out("setlists", f"{name} - compleet.pdf")
    with open(full, "wb") as f:
        w.write(f)
    log(f"✓ compleet boek ({page} pagina's, met bladwijzers): {full.relative_to(project.root)}")
