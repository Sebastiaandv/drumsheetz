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
TEST_OPEN = "DRUMSHEETZ_FORSCORE_OPEN"     # voor de tests: commando dat forScore nabootst


def _poll():
    import os
    return float(os.environ.get("DRUMSHEETZ_FORSCORE_POLL", "3"))


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


LIST_FIELDS = ("composer", "labels", "genre", "keywords")


def build_4sc(name, pdf_bytes, meta, style="text"):
    """forScore-container (gzip + binaire plist): de PDF onder 'pdfData', gegevens onder '<naam>.pdf|<veld>'.
    style 'list': namen-velden (componist, labels, genre, trefwoorden) als lijst i.p.v. tekst."""
    plist = {"pdfData": pdf_bytes}
    for k, v in meta.items():
        if v in (None, ""):
            continue
        if style == "list" and k in LIST_FIELDS:
            v = split_list(v)
        plist[f"{name}|{k}"] = v
    return gzip.compress(plistlib.dumps(plist, fmt=plistlib.FMT_BINARY))


def caps(project):
    """Wat de zelftest heeft vastgesteld (uitvoer/.forscore-caps.json)."""
    try:
        return json.loads(project.out(".forscore-caps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def use_4sc(project):
    """(gebruik .4sc?, stijl) volgens 'forscore-formaat' (pdf | 4sc | auto) en de zelftest."""
    fmt = str(project.config.get("forscore_format", "auto") or "auto").lower()
    c = caps(project)
    style = c.get("style", "text")
    if fmt == "4sc":
        return True, style
    if fmt == "pdf":
        return False, style
    return bool(c.get("4sc") and any(v for k, v in c.get("fields", {}).items() if k != "title")), style


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
    import os
    if os.environ.get(TEST_OPEN):
        return "test"
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
    import os
    import shlex
    for f in files:
        try:
            if os.environ.get(TEST_OPEN):
                subprocess.run(shlex.split(os.environ[TEST_OPEN]) + [str(f)], check=True, timeout=60)
                continue
            subprocess.run(["open", "-a", app, str(f)], check=True, timeout=60)
            time.sleep(0.8)
        except (OSError, subprocess.SubprocessError) as e:
            log(f"✗ openen in forScore mislukt voor {pathlib.Path(f).name}: {e}")
            return False
    return True


def wait_for(names, setlist=None, seconds=None, log=print):
    """Wacht tot de bestandsnamen (en eventueel de setlist) in de forScore-bibliotheek staan.
    Geeft (bibliotheek, ontbrekende namen) of (bibliotheek, None) als er niet gecontroleerd kan worden."""
    deadline = time.time() + (seconds or VERIFY_SECONDS * _poll() / 3)
    lib = None
    while time.time() < deadline:
        time.sleep(_poll())
        lib = library()
        if not lib.ok:
            return lib, None
        missing = [n for n in names if not lib.has(n)]
        if not missing and (setlist is None or setlist in lib.setlists):
            return lib, []
    return lib, [n for n in names if not (lib and lib.has(n))]


# ---------------------------------------------------------------------------
# versturen

def _norm(x):
    import re
    import unicodedata
    x = unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", x)


def _base(filename):
    """Bestandsnaam zonder '.pdf' en zonder kopie-achtervoegsel (' 2', ' (2)', ' kopie', ' copy')."""
    import re
    stem = re.sub(r"\.pdf$", "", str(filename), flags=re.I)
    stem = re.sub(r"(\s+\d+|\s*\(\d+\)|\s+kopie|\s+copy)$", "", stem, flags=re.I)
    return _norm(stem)


def match(song, lib, state):
    """Zoek het stuk in forScore: eerst de onthouden naam, dan 'Titel - Artiest.pdf', dan op titel (+ componist).
    Geeft (record of None, lijst dubbele records)."""
    if lib is None or not lib.ok:
        return None, []
    sent = state.song(song["_id"]) if state else {}
    name = forscore_name(song)
    title, artist = _norm(song.get("title")), _norm(song.get("composer") or song.get("artist"))
    cands = []
    known = {_base(name)} | ({_base(sent["name"])} if sent.get("name") else set())
    for r in lib.scores.values():
        base = _base(r["file"])
        if base in known:
            cands.append(r)
        elif title and (_norm(r["title"]) == title or base == title):
            # zelfde titel, andere naam: alleen als de componist niet tegenspreekt
            comps = {_norm(c) for c in r["composers"]}
            if not (artist and comps and artist not in comps):
                cands.append(r)
    if artist and len(cands) > 1:
        narrowed = [r for r in cands if not r["composers"] or artist in {_norm(c) for c in r["composers"]}
                    or artist in _norm(r["file"])]
        cands = narrowed or cands
    if not cands:
        return None, []
    # voorkeur: de onthouden naam, dan het stuk mét labels (het 'echte'), dan het oudste
    pref = [r for r in cands if r["file"].lower() == str(sent.get("name", "")).lower()]
    best = pref[0] if pref else sorted(cands, key=lambda r: (not r["labels"], r.get("added") or 0))[0]
    return best, (cands if len(cands) > 1 else [])


def status(project, song, lib, state):
    """'geen-pdf', 'niet' (niet in forScore), 'gewijzigd', 'actueel'."""
    return resolve(project, song, lib, state)[0]


def resolve(project, song, lib, state):
    """(status, forScore-record of None, dubbelen)"""
    pdf = project.out("pdf", f"{song['_id']}.pdf")
    sent = state.song(song["_id"])
    rec, dups = match(song, lib, state) if lib is not None and lib.ok else (None, [])
    if not pdf.exists():
        return "geen-pdf", rec, dups
    if lib is not None and lib.ok:
        if rec is None:
            return "niet", None, []
    elif not sent:
        return "niet", None, []
    if sent and sent.get("hash") not in (None, _hash(pdf.read_bytes())):
        return "gewijzigd", rec, dups
    if not sent and rec is not None:
        # staat in forScore maar is niet door Drumsheetz gestuurd: vergelijk tijd van de PDF met forScore
        return "gewijzigd" if _pdf_newer(pdf, rec) else "actueel", rec, dups
    return "actueel", rec, dups


def _pdf_newer(pdf, rec):
    """Is onze PDF nieuwer dan het stuk in forScore? (Core Data-tijd = seconden sinds 2001-01-01)"""
    m = rec.get("modified") or rec.get("added")
    if not isinstance(m, (int, float)):
        return False
    return pdf.stat().st_mtime > m + 978307200 + 60


def wait_updated(file, before, seconds=None, log=print):
    """Wacht tot forScore het bestaande stuk heeft vervangen (wijzigingstijd of grootte verandert)."""
    deadline = time.time() + (seconds or 90 * _poll() / 3)
    while time.time() < deadline:
        time.sleep(_poll())
        lib = library()
        rec = lib.get(file) if lib.ok else None
        if rec is None:
            continue
        if (rec.get("modified"), rec.get("size")) != before:
            return True, lib
    return False, library()


def send(project, items, force=False, open_app=True, log=print, force_meta=False, lib=None):
    """items: (song, pdf[, score]). Nieuw → .4sc/PDF met gegevens; bestaand → PDF onder de BESTAANDE
    forScore-naam (forScore vraagt 'Overschrijven'; labels en annotaties blijven). Alles wordt gecontroleerd.
    Geeft de lijst forScore-bestandsnamen die (nu) in forScore staan."""
    out = project.out("forscore")
    out.mkdir(parents=True, exist_ok=True)
    state = State(project)
    lib = lib or library()
    four, style = use_4sc(project)
    new_items, upd_items, present = [], [], []
    for it in items:
        song, pdf = it[0], it[1]
        score = it[2] if len(it) > 2 else None
        st, rec, dups = resolve(project, song, lib, state)
        if st == "geen-pdf":
            log(f"  ! {song.get('_id')}: nog geen PDF")
            continue
        if dups:
            log(f"  ! {song.get('title')}: staat {len(dups)}× in forScore ({', '.join(d['file'] for d in dups)}). "
                f"Ik gebruik '{rec['file']}'; verwijder de andere in forScore.")
        if st == "actueel" and not force and not force_meta:
            present.append(rec["file"] if rec else forscore_name(song))
            if rec:
                state.data["songs"].setdefault(song["_id"], {"hash": _hash(pdf.read_bytes()), "name": rec["file"]})
            continue
        if rec is None:                                           # nieuw stuk
            name = forscore_name(song)
            if four:
                dst = out / (name[:-4] + ".4sc")
                dst.write_bytes(build_4sc(name, pdf.read_bytes(), metadata(song, score), style))
            else:
                dst = out / name
                write_pdf(pdf, dst, song)
            new_items.append((song, dst, name, _hash(pdf.read_bytes())))
        else:                                                     # bestaand stuk: altijd PDF, zelfde naam
            dst = out / rec["file"]
            write_pdf(pdf, dst, song)
            upd_items.append((song, dst, rec, _hash(pdf.read_bytes())))
    if not new_items and not upd_items:
        log("= forScore: alles staat er al actueel in")
        state.save()
        return present
    if not open_app:
        log(f"✓ {len(new_items) + len(upd_items)} bestand(en) klaargezet in {out.relative_to(project.root)}/")
        return present
    if new_items:
        log(f"→ nieuw in forScore: {', '.join(t[2] for t in new_items)}")
        if open_files([t[1] for t in new_items], log):
            missing = []
            if lib.ok:
                _, missing = wait_for([t[2] for t in new_items], log=log)
                missing = missing or []
            for song, dst, name, h in new_items:
                if name in missing:
                    log(f"  ✗ {name}: niet in forScore verschenen (vroeg forScore iets? kijk op de Mac)")
                    continue
                state.data["songs"][song["_id"]] = {"hash": h, "name": name, "time": int(time.time())}
                present.append(name)
                log(f"  ✓ {name}" + (" staat in forScore" if lib.ok else ""))
    for song, dst, rec, h in upd_items:
        log(f"→ bijwerken in forScore: {rec['file']}")
        log("  forScore vraagt wat hij moet doen met het bestaande stuk: kies OVERSCHRIJVEN (niet 'dupliceren').")
        before = (rec.get("modified"), rec.get("size"))
        if not open_files([dst], log):
            continue
        if lib.ok:
            ok, lib2 = wait_updated(rec["file"], before, log=log)
            dup = [r["file"] for r in lib2.scores.values() if r["file"] != rec["file"]
                   and _norm(r["file"][:-4]).startswith(_norm(rec["file"][:-4]))] if lib2.ok else []
            if dup:
                log(f"  ✗ forScore heeft een KOPIE gemaakt ({', '.join(dup)}) in plaats van te overschrijven. "
                    "Verwijder die kopie in forScore en probeer opnieuw (kies 'Overschrijven').")
                continue
            if not ok:
                log(f"  ✗ {rec['file']}: forScore heeft de nieuwe versie niet overgenomen (binnen 90 s). "
                    "Kies 'Overschrijven' in forScore op de Mac en klik daarna op ↻ in de Studio.")
                continue
            log(f"  ✓ {rec['file']} bijgewerkt (labels en annotaties blijven)")
        state.data["songs"][song["_id"]] = {"hash": h, "name": rec["file"], "time": int(time.time())}
        present.append(rec["file"])
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
        real = None
        if lib.ok:
            real = lib.get(fname)
            if real is None and e.kind == "song":
                real, _ = match(s, lib, State(project))
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
    if lib.ok and title in lib.setlists:
        log(f"  ! er staat al een setlist '{title}' in forScore ({len(lib.setlists[title])} regels). forScore werkt "
            "een bestaande setlist niet altijd goed bij: verwijder hem in forScore en stuur dan opnieuw.")
        return False
    log(f"→ setlist '{title}' naar forScore ({sum(1 for r in rows if r[1])} stukken, "
        f"{sum(1 for r in rows if not r[1])} plaatshouders)")
    if not open_files([dst], log):
        return False
    if lib.ok:
        lib2, _ = wait_for([], setlist=title, log=log)
        if lib2 is None or title not in lib2.setlists:
            log(f"  ✗ setlist '{title}' niet in forScore verschenen (vroeg forScore iets? kijk op de Mac)")
            return False
        got = lib2.setlists[title]
        want = [r[1] if r[1] else f"[{r[0]}]" for r in rows]
        got_files = [g.lower() for g in got]
        lost = [w for w in want if not w.startswith("[") and w.lower() not in got_files]
        if lost:
            log(f"  ✗ setlist staat in forScore, maar {len(lost)} stuk(ken) zijn niet gekoppeld: {', '.join(lost)}")
            return False
        log(f"  ✓ setlist '{title}' staat compleet in forScore ({len(got)} regels)")
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
        rec, _ = match(song, lib, State(project))
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
    matched = set()
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
        st, rec, dups = resolve(project, s, lib, state)
        pdf = project.out_file("pdf", f, "pdf")
        if st in ("actueel", "gewijzigd") and pdf.stat().st_mtime < f.stat().st_mtime:
            st = "verouderd"
        in_fs = rec is not None if lib.ok else bool(state.song(sid))
        if rec is not None:
            matched.add(rec["file"].lower())
            for d in dups:
                matched.add(d["file"].lower())
        # in forScore: de echte labels uit forScore zijn de mappen; anders de map uit het nummer
        folders = sorted(rec["labels"]) if rec is not None else split_list(s.get("fs_library"))
        songs.append({"id": sid, "path": rel, "title": s.get("title", f.stem), "artist": s.get("artist", ""),
                      "name": rec["file"] if rec else forscore_name(s), "status": st, "sent": in_fs,
                      "library": folders, "dups": [d["file"] for d in dups],
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
    # stukken in forScore die bij geen enkel nummer horen, en dubbele titels
    only_fs = [r["file"] for k, r in lib.scores.items() if k not in matched] if lib.ok else []
    duplicates = [s_["dups"] for s_ in songs if s_.get("dups")]     # per nummer: meerdere stukken in forScore
    seen = {f.lower() for d in duplicates for f in d}
    groups = {}
    for r in (lib.scores.values() if lib.ok else []):
        if r["file"].lower() not in seen:
            groups.setdefault(_base(r["file"]), []).append(r["file"])
    duplicates += [v for v in groups.values() if len(v) > 1]
    return {"songs": songs, "setlists": setlists, "library_ok": lib.ok, "notes": lib.notes,
            "only_forscore": sorted(only_fs), "duplicates": duplicates,
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
    stamp = time.strftime("%H%M%S")
    a = out / f"Drumsheetz zelftest {stamp} - PDF.pdf"
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
    say("\n2. .4sc met gegevens: welke manier neemt forScore over?")
    meta = {"composer": "Zelftest Componist", "labels": "Drumsheetz test", "genre": "Testgenre",
            "keywords": "drumsheetz-test", "bpm": 100, "rating": 3}
    results = {}
    files = {}
    for style in ("text", "list"):
        nm = f"Drumsheetz zelftest {stamp} - {style}.pdf"
        f4 = out / (nm[:-4] + ".4sc")
        f4.write_bytes(build_4sc(nm, pdf.read_bytes(), dict(meta, title=f"Zelftest {style}"), style))
        files[style] = (nm, f4)
    open_files([f for _, f in files.values()], say)
    lib3, missing = wait_for([n for n, _ in files.values()], log=say)
    if missing is None:
        say("   (niet te controleren)")
    for style, (nm, _) in files.items():
        rec = lib3.get(nm) if lib3 is not None and lib3.ok else None
        if rec is None:
            say(f"   ✗ {style}: niet verschenen")
            continue
        got = {"title": rec["title"] == f"Zelftest {style}", "composer": "Zelftest Componist" in rec.get("composers", ()),
               "labels": "Drumsheetz test" in rec["labels"], "genre": "Testgenre" in rec.get("genres", ()),
               "keywords": "drumsheetz-test" in rec.get("keywords", ())}
        results[style] = got
        say(f"   {style}: " + ", ".join(f"{k} {'✓' if v else '✗'}" for k, v in got.items()))
    if results:
        best = max(results, key=lambda s_: sum(results[s_].values()))
        found = {"4sc": True, "style": best, "fields": results[best], "tested": int(time.time())}
        project.out(".forscore-caps.json").write_text(json.dumps(found, indent=1), encoding="utf-8")
        say(f"   → onthouden: .4sc met '{best}'-velden ({', '.join(k for k, v in results[best].items() if v)})")
    else:
        project.out(".forscore-caps.json").write_text(json.dumps({"4sc": False, "tested": int(time.time())}),
                                                       encoding="utf-8")
        say("   → onthouden: geen .4sc, alleen PDF")

    say("\n3. setlist (Open Setlist .4ss)")
    st_title = f"Drumsheetz zelftest {stamp}"
    s = out / (st_title + ".4ss")
    s.write_text(build_4ss(st_title, [("Pauze", None), ("Drumsheetz zelftest", a.name),
                                      ("Zelftest text", files["text"][0])]), encoding="utf-8")
    open_files([s], say)
    lib4, _ = wait_for([], setlist=st_title, log=say)
    if lib4 is None or not lib4.ok:
        say("   (niet te controleren)")
    elif st_title in lib4.setlists:
        got = lib4.setlists[st_title]
        ok = a.name in got and files["text"][0] in got
        say(f"   {'✓' if ok else '✗'} setlist verschenen met: {got}")
    else:
        say("   ✗ setlist niet verschenen (of niet herkend in de database)")
    say("\n4. database (alleen namen van tabellen en kolommen, plus wat er herkend is)")
    investigate(log=say)
    say("\nVerwijder in forScore zelf: de stukken en de setlist die met 'Drumsheetz zelftest' beginnen.")
    return _report(project, lines)


def _report(project, lines):
    p = project.out("forscore-zelftest.txt")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nRapport: {p.relative_to(project.root)}")
    return p
