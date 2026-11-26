"""forScore-koppeling: nummers en setlists vanuit Drumsheetz in forScore (Mac → iCloud → iPad).

Bestandsformaten van forScore (uitgezocht, niet officieel gedocumenteerd):
  .4sc  = gzip-gecomprimeerde binaire Apple-plist; de PDF staat onder 'pdfData', gegevens onder
          '<bestandsnaam>.pdf|<veld>' (title, composer, keywords, labels, bpm, ...).
  .4ss  = setlist als tekst: <forScore kind="setlist" title="..."> met regels <score title=".." path=".."/>.

Veilige werkwijze:
  - Nieuw stuk          → .4sc (PDF + alle gegevens in één keer)
  - Alleen PDF gewijzigd → .pdf met dezelfde naam: in forScore 'Overschrijven' kiezen; je annotaties en
                           gegevens blijven dan bewaard
  - Alleen gegevens gewijzigd → melding; met 'gegevens forceren' gaat er een .4sc heen (dat overschrijft
                           ook annotaties, dus alleen als je dat wilt)
  - Setlists            → .4ss
"""
import gzip
import hashlib
import json
import pathlib
import platform
import plistlib
import shutil
import subprocess
from xml.sax.saxutils import quoteattr

from .project import fmt_duration, parse_duration, safe_filename

# Drumsheetz-kop → forScore-veld in een .4sc. Waar de sleutelnaam nog niet zeker is staat '?'.
KEYMAP = {
    "title": "title", "composer": "composer", "genre": "genre", "keywords": "keywords", "labels": "labels",
    "reference": "reference", "rating": "rating", "difficulty": "difficulty", "duration": "duration",
    "bpm": "bpm", "key": "key",
}
FIELDS = ["title", "composer", "genre", "keywords", "labels", "reference", "rating", "difficulty",
          "duration", "bpm", "key", "library"]


def forscore_name(song):
    if song.get("fs_name"):
        n = str(song["fs_name"])
        return n if n.lower().endswith(".pdf") else n + ".pdf"
    title = song.get("title") or song.get("_id", "nummer")
    artist = song.get("artist", "")
    return safe_filename(f"{title} - {artist}" if artist else title) + ".pdf"


def split_list(v):
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).replace(";", ",").split(",") if x.strip()]


def metadata(song, score=None):
    """De gegevens zoals ze in forScore horen te staan."""
    m = {"title": song.get("title", "")}
    comp = song.get("composer") or song.get("artist")
    if comp:
        m["composer"] = str(comp)
    if song.get("genre"):
        m["genre"] = ", ".join(split_list(song["genre"]))
    if song.get("tags"):
        m["keywords"] = ", ".join(split_list(song["tags"]))
    # mappen in Drumsheetz = labels in forScore (forScore kent zelf geen mappen)
    labels = []
    for x in split_list(song.get("fs_library")) + split_list(song.get("labels")):
        if x not in labels:
            labels.append(x)
    if labels:
        m["labels"] = ", ".join(labels)
    if song.get("reference"):
        m["reference"] = str(song["reference"])
    for k in ("rating", "difficulty"):
        if song.get(k) not in (None, ""):
            try:
                m[k] = max(0, min(5 if k == "rating" else 3, int(str(song[k]).strip())))
            except ValueError:
                pass
    if song.get("duration"):
        d = parse_duration(song["duration"])
        if d:
            m["duration"] = int(d)
    elif score is not None:
        m["duration"] = int(round(score.seconds()))
    if score is not None:
        try:
            m["bpm"] = int(round(float(score.tempo[0])))
        except (TypeError, ValueError):
            pass
    if song.get("key"):
        m["key"] = str(song["key"])
    return m


def build_4sc(name, pdf_bytes, meta):
    plist = {"pdfData": pdf_bytes}
    for k, v in meta.items():
        key = KEYMAP.get(k)
        if key and v not in (None, ""):
            plist[f"{name}|{key}"] = v
    return gzip.compress(plistlib.dumps(plist, fmt=plistlib.FMT_BINARY))


def build_4ss(title, scores):
    """scores: lijst (titel, bestandsnaam)."""
    lines = [f'<forScore kind="setlist" title={quoteattr(title)}>']
    for t, path in scores:
        lines.append(f"<score title={quoteattr(t)} path={quoteattr(path)}/>")
    lines.append("</forScore>")
    return "\n".join(lines) + "\n"


def add_pdf_metadata(src, dst, song):
    """PDF kopiëren met titel/artiest/trefwoorden erin (pypdf); anders gewone kopie."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        shutil.copyfile(src, dst)
        return False
    r = PdfReader(str(src))
    w = PdfWriter()
    for p in r.pages:
        w.add_page(p)
    meta = {"/Title": str(song.get("title", "")),
            "/Author": str(song.get("composer") or song.get("artist") or ""), "/Creator": "Drumsheetz"}
    kw = split_list(song.get("tags")) + split_list(song.get("genre"))
    if kw:
        meta["/Keywords"] = ", ".join(kw)
    if song.get("subtitle"):
        meta["/Subject"] = str(song["subtitle"])
    w.add_metadata(meta)
    with open(dst, "wb") as f:
        w.write(f)
    return True


# ---------------------------------------------------------------------------
def _hash(b):
    return hashlib.sha1(b).hexdigest()


class State:
    def __init__(self, project):
        self.file = project.out(".forscore.json")
        try:
            self.data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("songs", {k: v for k, v in self.data.items() if isinstance(v, dict) and "hash" in v})
        for k in list(self.data):
            if k not in ("songs", "setlists"):
                self.data.pop(k)
        self.data.setdefault("setlists", {})

    def save(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")

    def song(self, sid):
        return self.data["songs"].get(sid, {})


def song_status(project, song, score, state):
    """nieuw / pdf / gegevens / actueel / geen-pdf"""
    pdf = project.out("pdf", f"{song['_id']}.pdf")
    if not pdf.exists():
        return "geen-pdf", None, None
    ph = _hash(pdf.read_bytes())
    mh = _hash(json.dumps(metadata(song, score), sort_keys=True).encode() + forscore_name(song).encode())
    old = state.song(song["_id"])
    if not old:
        return "nieuw", ph, mh
    if old.get("hash") != ph and old.get("pdf") != ph:
        return "pdf", ph, mh
    if old.get("meta") and old.get("meta") != mh or old.get("name") and old.get("name") != forscore_name(song):
        return "gegevens", ph, mh
    return "actueel", ph, mh


def find_app():
    if platform.system() != "Darwin":
        return None
    try:
        r = subprocess.run(["mdfind", "kMDItemCFBundleIdentifier == 'com.mgsdevelopment.forscore'"],
                           capture_output=True, text=True, timeout=20)
        hits = [x for x in r.stdout.splitlines() if x.endswith(".app")]
        if hits:
            return hits[0]
    except (OSError, subprocess.SubprocessError):
        pass
    if pathlib.Path("/Applications/forScore.app").exists():
        return "/Applications/forScore.app"
    return "forScore"


def open_in_forscore(project, files, log):
    if not files:
        return True
    app = find_app()
    out = project.out("forscore")
    if not app:
        log(f"✓ {len(files)} bestand(en) klaar in {out.relative_to(project.root)}/ "
            "(forScore openen kan alleen op een Mac; sleep ze er zelf in)")
        return True
    try:
        subprocess.run(["open", "-a", app] + [str(f) for f in files], check=True, timeout=60)
        return True
    except (OSError, subprocess.SubprocessError) as e:
        log(f"✗ forScore openen lukte niet ({e}). De bestanden staan in {out.relative_to(project.root)}/")
        return False


def send(project, items, force=False, open_app=True, log=print, force_meta=False):
    """items: lijst (song, pdf-pad) of (song, pdf-pad, score). Stuurt alleen wat nodig is."""
    out = project.out("forscore")
    out.mkdir(parents=True, exist_ok=True)
    state = State(project)
    fmt = str(project.config.get("forscore_format", "4sc")).lower()
    todo, notes = [], []
    for it in items:
        song, pdf = it[0], it[1]
        score = it[2] if len(it) > 2 else None
        st, ph, mh = song_status(project, song, score, state)
        if st == "geen-pdf":
            log(f"  ! {song.get('_id')}: nog geen PDF (eerst 'maak')")
            continue
        name = forscore_name(song)
        old = state.song(song["_id"])
        if old.get("name") and old["name"] != name:
            notes.append(f"  ! {song['_id']}: naam in forScore wordt '{name}' (was '{old['name']}'): het komt als "
                         "nieuw stuk binnen; verwijder het oude zelf in forScore")
        if st == "actueel" and not force:
            continue
        if st == "gegevens" and not (force or force_meta):
            notes.append(f"  · {song['_id']}: alleen de gegevens zijn gewijzigd. Pas ze in forScore aan, of stuur "
                         "met 'gegevens forceren' (dat vervangt het stuk incl. annotaties)")
            continue
        use_4sc = (st == "nieuw" or force_meta) and fmt != "pdf"
        if use_4sc:
            dst = out / (name[:-4] + ".4sc")
            dst.write_bytes(build_4sc(name, pdf.read_bytes(), metadata(song, score)))
        else:
            dst = out / name
            add_pdf_metadata(pdf, dst, song)
        todo.append((song, dst, ph, mh, name, "4sc" if use_4sc else "pdf"))
    for n in notes:
        log(n)
    if not todo:
        log("= forScore: niets te versturen")
        return 0
    if open_app and not open_in_forscore(project, [t[1] for t in todo], log):
        return 0
    if not open_app:
        log(f"✓ {len(todo)} bestand(en) klaargezet in {out.relative_to(project.root)}/")
    else:
        log("✓ naar forScore: " + ", ".join(f"{n} ({k})" for _, _, _, _, n, k in todo))
        if any(k == "pdf" for *_, k in todo):
            log("  Vraagt forScore of hij moet overschrijven? Kies 'Overschrijven' (houdt annotaties en gegevens).")
    for song, dst, ph, mh, name, kind in todo:
        state.data["songs"][song["_id"]] = {"hash": ph, "meta": mh, "name": name}
    state.save()
    return len(todo)


def send_setlist(project, name, meta, entries, open_app=True, log=print):
    """Setlist als .4ss naar forScore. Nummers die nog niet in forScore staan worden eerst verstuurd."""
    out = project.out("forscore")
    out.mkdir(parents=True, exist_ok=True)
    scores = []
    for e in entries:
        if e.kind == "song" and e.path:
            from .build import load_and_arrange
            sc = load_and_arrange(project, e.path)
            scores.append((sc.song.get("title", e.title), forscore_name(sc.song)))
        elif e.kind == "pdf" and e.pdf:
            fname = pathlib.Path(e.pdf).name
            scores.append((e.title or fname[:-4], fname))
    title = meta.get("title") or name
    dst = out / (safe_filename(title) + ".4ss")
    dst.write_text(build_4ss(title, scores), encoding="utf-8")
    ext = [e for e in entries if e.kind == "pdf" and e.pdf]
    files = []
    for e in ext:                       # gekochte/externe PDF's ook meesturen
        p = out / pathlib.Path(e.pdf).name
        if not p.exists():
            shutil.copyfile(e.pdf, p)
            files.append(p)
    if open_app:
        open_in_forscore(project, files + [dst], log)
    state = State(project)
    state.data["setlists"][name] = {"hash": _hash(dst.read_bytes()), "title": title}
    state.save()
    log(f"✓ setlist '{title}' ({len(scores)} stukken) naar forScore: {dst.name}")
    return dst


def catalog(project):
    """Overzicht voor de Studio: alle nummers met hun forScore-gegevens en status, en de setlists."""
    from .build import load_and_arrange
    from .rows import NotationError
    from . import setlist as sl
    state = State(project)
    songs = []
    for f in project.song_files():
        try:
            sc = load_and_arrange(project, f)
        except NotationError as e:
            songs.append({"id": project.song_id(f), "path": str(f.relative_to(project.root)).replace("\\", "/"),
                          "title": f.stem,
                          "status": "fout", "error": e.msg})
            continue
        s = sc.song
        st, _, _ = song_status(project, s, sc, state)
        if st != "geen-pdf" and project.out_file("pdf", f, "pdf").stat().st_mtime < f.stat().st_mtime:
            st = "verouderd"           # het nummer is veranderd sinds de laatste PDF
        m = metadata(s, sc)
        songs.append({"id": project.song_id(f), "path": str(f.relative_to(project.root)).replace("\\", "/"),
                      "title": s.get("title", f.stem), "artist": s.get("artist", ""), "name": forscore_name(s),
                      "composer": m.get("composer", ""), "genre": split_list(s.get("genre")),
                      "tags": split_list(s.get("tags")), "labels": split_list(s.get("labels")),
                      "library": split_list(s.get("fs_library")), "rating": s.get("rating", ""),
                      "difficulty": s.get("difficulty", ""), "key": s.get("key", ""),
                      "duration": fmt_duration(m["duration"]) if m.get("duration") else "",
                      "bpm": m.get("bpm", ""), "status": st,
                      "sent": bool(state.song(project.song_id(f)))})
    setlists = []
    if project.setlists_dir.exists():
        for f in sorted(project.setlists_dir.glob("*.txt")):
            meta, entries = sl.parse_setlist(f.read_text(encoding="utf-8"), f.stem)
            sl.resolve(project, entries, f)
            items = [{"title": e.display if e.kind == "break" else (e.title or e.ref), "id": project.song_id(e.path) if e.path and e.kind == "song" else "",
                      "kind": e.kind} for e in entries if e.kind in ("song", "pdf", "break")]
            setlists.append({"name": f.stem, "path": f"setlists/{f.name}", "title": meta.get("title", f.stem),
                             "items": items, "sent": f.stem in state.data["setlists"]})
    return {"songs": songs, "setlists": setlists}
