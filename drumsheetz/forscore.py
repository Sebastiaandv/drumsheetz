"""Koppeling met forScore (Mac → iCloud-synchronisatie → iPad).

Uitgangspunten:
  - Versturen gebeurt met wat forScore officieel ondersteunt: bestanden openen met forScore voor Mac
    (PDF; setlists als 'Open Setlist'-XML met de extensie .4ss).
  - Na het versturen wordt in de forScore-bibliotheek op de Mac GECONTROLEERD of het er echt staat
    (alleen lezen, zie forscore_db.py). Pas dan geldt een stuk als 'in forScore'.
  - Een stuk wordt herkend aan zijn bestandsnaam in forScore: 'Titel - Artiest.pdf' (of 'forscore-naam:').
  - Mappen in Drumsheetz = labels in forScore.
  - .4sc (PDF + gegevens in één bestand) is experimenteel: aanzetten met 'forscore-formaat: 4sc'.
"""
import gzip
import hashlib
import json
import pathlib
import platform
import plistlib
import shutil
import subprocess
import time
from xml.sax.saxutils import quoteattr

from .project import fmt_duration, parse_duration, safe_filename

VERIFY_SECONDS = 40


# ---------------------------------------------------------------------------
# namen en gegevens

def forscore_name(song):
    if song.get("fs_name"):
        n = str(song["fs_name"]).strip()
        return n if n.lower().endswith(".pdf") else n + ".pdf"
    title = song.get("title") or song.get("_id", "nummer").split("/")[-1]
    artist = song.get("artist", "")
    return safe_filename(f"{title} - {artist}" if artist else title) + ".pdf"


def split_list(v):
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).replace(";", ",").split(",") if x.strip()]


def song_labels(song):
    """Mappen + eigen labels = labels in forScore."""
    out = []
    for x in split_list(song.get("fs_library")) + split_list(song.get("labels")):
        if x not in out:
            out.append(x)
    return out


def metadata(song, score=None):
    m = {"title": song.get("title", "")}
    comp = song.get("composer") or song.get("artist")
    if comp:
        m["composer"] = str(comp)
    if song.get("genre"):
        m["genre"] = ", ".join(split_list(song["genre"]))
    if song.get("tags"):
        m["keywords"] = ", ".join(split_list(song["tags"]))
    labels = song_labels(song)
    if labels:
        m["labels"] = ", ".join(labels)
    if song.get("reference"):
        m["reference"] = str(song["reference"])
    for k, hi in (("rating", 5), ("difficulty", 3)):
        if song.get(k) not in (None, ""):
            try:
                m[k] = max(0, min(hi, int(str(song[k]).strip())))
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


def write_pdf(src, dst, song):
    """PDF kopiëren met titel, componist en trefwoorden in de PDF-gegevens (pypdf); anders gewone kopie."""
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


def build_4sc(name, pdf_bytes, meta):
    """Experimenteel: forScore-container (gzip + binaire plist). Sleutels: '<naam>.pdf|<veld>'."""
    plist = {"pdfData": pdf_bytes}
    for k, v in meta.items():
        if v not in (None, ""):
            plist[f"{name}|{k}"] = v
    return gzip.compress(plistlib.dumps(plist, fmt=plistlib.FMT_BINARY))


def build_4ss(title, items):
    """forScore 'Open Setlist' (forScore 12+). items: (titel, bestandsnaam) of (titel, None) = plaatshouder."""
    lines = ['<?xml version="1.0" encoding="UTF-8" ?>',
             f'<forScore kind="setlist" version="1.0" title={quoteattr(title)}>']
    for t, path in items:
        if path:
            lines.append(f"\t<score title={quoteattr(t)} path={quoteattr(path)} />")
        else:
            lines.append(f"\t<placeholder title={quoteattr(t)} />")
    lines.append("</forScore>")
    return "\n".join(lines) + "\n"


def _hash(b):
    return hashlib.sha1(b).hexdigest()


# ---------------------------------------------------------------------------
# administratie en de echte bibliotheek

class State:
    """Wat Drumsheetz naar forScore stuurde (per nummer: naam en PDF-hash)."""

    def __init__(self, project):
        self.file = project.out(".forscore.json")
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        songs = data.get("songs") if isinstance(data.get("songs"), dict) else \
            {k: v for k, v in data.items() if isinstance(v, dict) and "hash" in v}
        self.data = {"songs": songs, "setlists": data.get("setlists", {})}

    def save(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")

    def song(self, sid):
        return self.data["songs"].get(sid, {})


def library():
    """De forScore-bibliotheek op deze Mac (of een lege, als die niet te lezen is)."""
    from .forscore_db import Library, read_library
    try:
        return read_library()
    except Exception as e:  # noqa: BLE001 - nooit de rest laten mislukken op het lezen
        lib = Library()
        lib.notes.append(f"lezen mislukt: {type(e).__name__}: {e}")
        return lib


def find_app():
    if platform.system() != "Darwin":
        return None
    try:
        r = subprocess.run(["mdfind", "kMDItemCFBundleIdentifier == 'com.mgsdevelopment.forscore*'"],
                           capture_output=True, text=True, timeout=20)
        hits = [x for x in r.stdout.splitlines() if x.endswith(".app")]
        if hits:
            return hits[0]
    except (OSError, subprocess.SubprocessError):
        pass
    for p in ("/Applications/forScore.app", str(pathlib.Path.home() / "Applications/forScore.app")):
        if pathlib.Path(p).exists():
            return p
    try:
        r = subprocess.run(["mdfind", "kMDItemFSName == 'forScore.app'"], capture_output=True, text=True, timeout=20)
        hits = [x for x in r.stdout.splitlines() if x.endswith(".app")]
        if hits:
            return hits[0]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def open_files(files, log):
    """Bestanden één voor één met forScore openen (forScore importeert ze)."""
    app = find_app()
    if not app:
        log("✗ forScore voor Mac niet gevonden. Installeer forScore uit de Mac App Store (zelfde Apple-ID als "
            "op de iPad) en zet daar 'Sync with iCloud' aan.")
        return False
    for f in files:
        try:
            subprocess.run(["open", "-a", app, str(f)], check=True, timeout=60)
            time.sleep(0.8)
        except (OSError, subprocess.SubprocessError) as e:
            log(f"✗ openen in forScore mislukt voor {pathlib.Path(f).name}: {e}")
            return False
    return True


def wait_for(names, setlist=None, seconds=VERIFY_SECONDS, log=print):
    """Wacht tot de bestandsnamen (en eventueel de setlist) in de forScore-bibliotheek staan.
    Geeft (bibliotheek, ontbrekende namen) of (bibliotheek, None) als er niet gecontroleerd kan worden."""
    deadline = time.time() + seconds
    lib = None
    while time.time() < deadline:
        time.sleep(3)
        lib = library()
        if not lib.ok:
            return lib, None
        missing = [n for n in names if not lib.has(n)]
        if not missing and (setlist is None or setlist in lib.setlists):
            return lib, []
    return lib, [n for n in names if not (lib and lib.has(n))]


# ---------------------------------------------------------------------------
# versturen

def status(project, song, lib, state):
    """'geen-pdf', 'niet' (niet in forScore), 'gewijzigd', 'actueel'."""
    pdf = project.out("pdf", f"{song['_id']}.pdf")
    if not pdf.exists():
        return "geen-pdf"
    name = forscore_name(song)
    sent = state.song(song["_id"])
    in_fs = lib.has(name) if lib is not None and lib.ok else bool(sent)
    if not in_fs:
        return "niet"
    if sent and sent.get("hash") not in (None, _hash(pdf.read_bytes())):
        return "gewijzigd"
    return "actueel"


def send(project, items, force=False, open_app=True, log=print, force_meta=False, lib=None):
    """items: (song, pdf[, score]). Stuurt wat nieuw of gewijzigd is en controleert of het aankomt.
    Geeft de lijst bestandsnamen die (nu) in forScore staan."""
    out = project.out("forscore")
    out.mkdir(parents=True, exist_ok=True)
    state = State(project)
    lib = lib or library()
    fmt = str(project.config.get("forscore_format", "pdf")).lower()
    todo, present = [], []
    for it in items:
        song, pdf = it[0], it[1]
        score = it[2] if len(it) > 2 else None
        st = status(project, song, lib, state)
        name = forscore_name(song)
        if st == "geen-pdf":
            log(f"  ! {song.get('_id')}: nog geen PDF")
            continue
        if st == "actueel" and not force and not force_meta:
            present.append(name)
            continue
        new = st == "niet"
        if fmt == "4sc" and (new or force_meta):
            dst = out / (name[:-4] + ".4sc")
            dst.write_bytes(build_4sc(name, pdf.read_bytes(), metadata(song, score)))
        else:
            dst = out / name
            write_pdf(pdf, dst, song)
        todo.append((song, dst, name, _hash(pdf.read_bytes()), new))
    if not todo:
        log("= forScore: alles staat er al actueel in")
        return present
    if not open_app:
        log(f"✓ {len(todo)} bestand(en) klaargezet in {out.relative_to(project.root)}/")
        return present
    log(f"→ naar forScore: {', '.join(t[2] for t in todo)}")
    if any(not t[4] for t in todo):
        log("  forScore vraagt bij een bestaand stuk wat hij moet doen: kies 'Overschrijven' "
            "(je annotaties en gegevens blijven bewaard).")
    if not open_files([t[1] for t in todo], log):
        return present
    missing = []
    if lib.ok:
        log("  controleren in de forScore-bibliotheek…")
        _, missing = wait_for([t[2] for t in todo if t[4]], log=log)
        missing = missing or []
    else:
        log("  (de forScore-bibliotheek kon niet gelezen worden, dus niet gecontroleerd: kijk zelf in forScore)")
    for song, dst, name, h, new in todo:
        if name in missing:
            log(f"  ✗ {name}: niet in forScore verschenen (vroeg forScore iets? kijk in forScore op de Mac)")
            continue
        state.data["songs"][song["_id"]] = {"hash": h, "name": name, "time": int(time.time())}
        present.append(name)
        log(f"  ✓ {name}" + (" staat in forScore" if lib.ok and new else ""))
    state.save()
    return present


def send_setlist(project, name, open_app=True, log=print):
    """Setlist naar forScore: eerst ontbrekende stukken, dan de setlist (Open Setlist), en controleren."""
    from . import setlist as sl
    from .build import build
    f = project.setlists_dir / (name if name.endswith(".txt") else f"{name}.txt")
    if not f.exists():
        log(f"✗ setlist '{name}' niet gevonden")
        return False
    meta, entries = sl.parse_setlist(f.read_text(encoding="utf-8"), f.stem)
    for e in sl.resolve(project, entries, f):
        log(f"  ! {e}")
    lib = library()
    # 1. stukken die er nog niet (actueel) in staan
    songs = [e for e in entries if e.kind == "song" and e.path]
    res = build(project, [e.path for e in songs], log=lambda m: None)
    scores = {str(p): sc for p, sc, err in res if sc}
    send(project, [(sc.song, project.out_file("pdf", p, "pdf"), sc) for p, sc, err in res if sc],
         open_app=open_app, log=log, lib=lib)
    out = project.out("forscore")
    ext_files = []
    for e in entries:                       # externe (gekochte) PDF's
        if e.kind == "pdf" and e.pdf:
            fname = pathlib.Path(e.pdf).name
            if not (lib.ok and lib.has(fname)):
                shutil.copyfile(e.pdf, out / fname)
                ext_files.append(out / fname)
    if ext_files and open_app:
        log(f"→ externe PDF's naar forScore: {', '.join(p.name for p in ext_files)}")
        open_files(ext_files, log)
        if lib.ok:
            wait_for([p.name for p in ext_files], log=log)
    # 2. de setlist zelf
    lib = library()
    title = meta.get("title") or f.stem
    rows, missing = [], []
    for e in entries:
        if e.kind == "break":
            if e.display:
                rows.append((e.display, None))
            continue
        if e.kind == "song" and e.path and str(e.path) in scores:
            s = scores[str(e.path)].song
            fname, t = forscore_name(s), s.get("title", e.title)
        elif e.kind == "pdf" and e.pdf:
            fname, t = pathlib.Path(e.pdf).name, e.title or pathlib.Path(e.pdf).stem
        else:
            rows.append((e.title or e.ref, None))
            continue
        real = lib.get(fname) if lib.ok else None
        if lib.ok and not real:
            missing.append(fname)
            rows.append((t, None))                 # plaatshouder, zodat de setlist compleet blijft
        else:
            rows.append((t, real["file"] if real else fname))
    if missing:
        log(f"  ! niet (of nog niet) in forScore, als plaatshouder in de setlist: {', '.join(missing)}")
    dst = out / (safe_filename(title) + ".4ss")
    dst.write_text(build_4ss(title, rows), encoding="utf-8")
    if not open_app:
        log(f"✓ setlist klaargezet: {dst.relative_to(project.root)}")
        return True
    log(f"→ setlist '{title}' naar forScore ({sum(1 for r in rows if r[1])} stukken)")
    if not open_files([dst], log):
        return False
    if lib.ok:
        lib2, _ = wait_for([], setlist=title, log=log)
        if lib2 is not None and title in lib2.setlists:
            log(f"  ✓ setlist '{title}' staat in forScore ({len(lib2.setlists[title])} stukken gekoppeld)")
        else:
            log(f"  ✗ setlist '{title}' niet in forScore verschenen. Draai 'python3 drums.py forscore --zelftest' "
                "en stuur het rapport op.")
            return False
    st = State(project)
    st.data["setlists"][f.stem] = {"title": title, "time": int(time.time())}
    st.save()
    return True


# ---------------------------------------------------------------------------
# labels ophalen (forScore → mappen in Drumsheetz)

def pull_labels(project, apply=False, log=print):
    from .build import load_and_arrange
    from .rows import NotationError
    lib = library()
    if not lib.ok:
        log("De forScore-bibliotheek kon niet gelezen worden: " + "; ".join(lib.notes))
        return []
    changes = []
    for f in project.song_files(include_parked=True):
        if f.suffix != ".drum":
            continue
        try:
            song = load_and_arrange(project, f).song
        except NotationError:
            continue
        rec = lib.get(forscore_name(song))
        if rec is None:
            continue
        own = set(split_list(song.get("labels")))           # eigen 'labels:' blijven labels
        new = sorted(x for x in rec["labels"] if x not in own)
        cur = split_list(song.get("fs_library"))
        if sorted(cur) != new:
            changes.append((f, cur, new))
    for f, cur, new in changes:
        log(f"  {project.song_id(f)}: map {', '.join(cur) or '—'} → {', '.join(new) or '—'}")
    if not changes:
        log("✓ de mappen zijn gelijk aan de labels in forScore")
    elif apply:
        from .studio import Studio
        st = Studio(project.root)
        for f, cur, new in changes:
            st.set_header({"path": str(f.relative_to(project.root)).replace("\\", "/"), "key": "map",
                           "value": ", ".join(new), "mode": "set"})
        log(f"✓ {len(changes)} nummer(s) bijgewerkt")
    else:
        log("(nog niets veranderd)")
    return changes


# ---------------------------------------------------------------------------
# overzicht voor de Studio

def catalog(project):
    from . import setlist as sl
    from .build import load_and_arrange
    from .rows import NotationError
    state = State(project)
    lib = library()
    songs = []
    for f in project.song_files():
        sid = project.song_id(f)
        rel = str(f.relative_to(project.root)).replace("\\", "/")
        try:
            sc = load_and_arrange(project, f)
        except NotationError as e:
            songs.append({"id": sid, "path": rel, "title": f.stem, "status": "fout", "error": e.msg,
                          "sent": False, "library": []})
            continue
        s = sc.song
        st = status(project, s, lib, state)
        pdf = project.out_file("pdf", f, "pdf")
        if st not in ("geen-pdf", "niet") and pdf.stat().st_mtime < f.stat().st_mtime:
            st = "verouderd"
        name = forscore_name(s)
        rec = lib.get(name) if lib.ok else None
        songs.append({"id": sid, "path": rel, "title": s.get("title", f.stem), "artist": s.get("artist", ""),
                      "name": name, "status": st, "sent": st in ("actueel", "gewijzigd", "verouderd"),
                      "library": split_list(s.get("fs_library")),
                      "fs_labels": sorted(rec["labels"]) if rec else [],
                      "duration": fmt_duration(sc.seconds())})
    setlists = []
    if project.setlists_dir.exists():
        for f in sorted(project.setlists_dir.glob("*.txt")):
            meta, entries = sl.parse_setlist(f.read_text(encoding="utf-8"), f.stem)
            sl.resolve(project, entries, f)
            title = meta.get("title", f.stem)
            items = [{"title": e.display if e.kind == "break" else (e.title or e.ref),
                      "id": project.song_id(e.path) if e.path and e.kind == "song" else "", "kind": e.kind}
                     for e in entries if e.kind in ("song", "pdf", "break")]
            in_fs = (title in lib.setlists) if lib.ok else (f.stem in state.data["setlists"])
            setlists.append({"name": f.stem, "path": f"setlists/{f.name}", "title": title, "items": items,
                             "sent": in_fs})
    return {"songs": songs, "setlists": setlists, "library_ok": lib.ok, "notes": lib.notes,
            "fs_counts": {"scores": len(lib.scores), "labels": len(lib.labels), "setlists": len(lib.setlists)}}


# ---------------------------------------------------------------------------
# zelftest

def selftest(project, log=print):
    """Probeert alles één keer uit op deze Mac en schrijft een rapport (uitvoer/forscore-zelftest.txt)."""
    from .build import build
    from .forscore_db import investigate
    lines = []

    def say(m=""):
        lines.append(m)
        log(m)

    say("Drumsheetz × forScore zelftest")
    say(f"systeem: {platform.system()} {platform.mac_ver()[0]}")
    app = find_app()
    say(f"forScore-app: {app or 'NIET GEVONDEN'}")
    lib = library()
    say("bibliotheek: " + ("gelezen" if lib.ok else "NIET gelezen") + " — " + "; ".join(lib.notes))
    if not app:
        return _report(project, lines)
    out = project.out("forscore")
    out.mkdir(parents=True, exist_ok=True)
    pdfdir = project.out("pdf")
    pdf = next(iter(sorted(pdfdir.rglob("*.pdf"))), None) if pdfdir.exists() else None
    if pdf is None and project.song_files():
        build(project, project.song_files()[:1], log=lambda m: None)
        pdf = next(iter(sorted(pdfdir.rglob("*.pdf"))), None) if pdfdir.exists() else None
    if pdf is None:
        say("✗ geen PDF om mee te testen (maak eerst een nummer)")
        return _report(project, lines)
    a = out / "Drumsheetz zelftest - PDF.pdf"
    write_pdf(pdf, a, {"title": "Drumsheetz zelftest", "artist": "PDF", "tags": "drumsheetz-test"})
    say("\n1. PDF importeren")
    open_files([a], say)
    lib2, missing = wait_for([a.name], log=say)
    if missing is None:
        say("   (bibliotheek niet leesbaar: kijk zelf of 'Drumsheetz zelftest' in forScore staat)")
    elif missing:
        say("   ✗ niet verschenen in de bibliotheek")
    else:
        rec = lib2.get(a.name)
        say(f"   ✓ verschenen als '{rec['file']}', titel '{rec['title']}'")
    say("\n2. .4sc met gegevens (experimenteel)")
    b_name = "Drumsheetz zelftest - 4SC.pdf"
    b = out / (b_name[:-4] + ".4sc")
    b.write_bytes(build_4sc(b_name, pdf.read_bytes(), {"title": "Drumsheetz zelftest 4SC", "composer": "Zelftest",
                                                       "labels": "Drumsheetz test", "keywords": "drumsheetz-test",
                                                       "genre": "Test", "bpm": 100, "rating": 3}))
    open_files([b], say)
    lib3, missing = wait_for([b_name], log=say)
    if missing is None:
        say("   (niet te controleren)")
    elif missing:
        say("   ✗ .4sc niet verschenen: dit formaat wordt niet geaccepteerd (PDF blijft de standaard)")
    else:
        rec = lib3.get(b_name)
        say(f"   ✓ verschenen als '{rec['file']}', titel '{rec['title']}', labels {sorted(rec['labels'])}")
    say("\n3. setlist (Open Setlist .4ss)")
    s = out / "Drumsheetz zelftest.4ss"
    s.write_text(build_4ss("Drumsheetz zelftest", [("Pauze", None), ("Drumsheetz zelftest", a.name)]),
                 encoding="utf-8")
    open_files([s], say)
    lib4, _ = wait_for([], setlist="Drumsheetz zelftest", log=say)
    if lib4 is None or not lib4.ok:
        say("   (niet te controleren)")
    elif "Drumsheetz zelftest" in lib4.setlists:
        say(f"   ✓ setlist verschenen, gekoppelde stukken: {lib4.setlists['Drumsheetz zelftest']}")
    else:
        say("   ✗ setlist niet verschenen (of niet herkend in de database)")
    say("\n4. database (alleen namen van tabellen en kolommen, plus wat er herkend is)")
    investigate(log=say)
    say("\nVerwijder in forScore zelf: de stukken 'Drumsheetz zelftest…' en de setlist 'Drumsheetz zelftest'.")
    return _report(project, lines)


def _report(project, lines):
    p = project.out("forscore-zelftest.txt")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nRapport: {p.relative_to(project.root)}")
    return p
