"""Koppeling met forScore (Mac → iCloud-synchronisatie → iPad).

Uitgangspunten:
  - Versturen gebeurt met wat forScore officieel ondersteunt: bestanden openen met forScore voor Mac
    (PDF; setlists als 'Open Setlist'-XML met de extensie .4ss).
  - Na het versturen wordt in de forScore-bibliotheek op de Mac GECONTROLEERD of het er echt staat
    (alleen lezen, zie forscore_db.py). Pas dan geldt een stuk als 'in forScore'.
  - Versies (versions.py): elke versie van een nummer is een eigen stuk in forScore, 'Titel - Artiest V2'.
    Bestaande stukken (met aantekeningen) worden NOOIT overschreven. Setlists gebruiken de nieuwste versie.
  - Stukken die er al stonden voordat er versies waren, worden herkend (naam, of titel + componist) en zijn V1.
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


def folder_labels(song):
    """De mappen waarin het nummer staat (binnen nummers/) = labels in forScore.
    Geparkeerde mappen (_naam) tellen niet mee."""
    parts = str(song.get("_id", "")).split("/")[:-1]
    return [p for p in parts if p and not p.startswith(("_", "."))]


def song_labels(song):
    """Labels in forScore: de mappen van het nummer, plus 'labels:' (en het oude 'map:') uit de kop."""
    out = []
    for x in folder_labels(song) + split_list(song.get("fs_library")) + split_list(song.get("labels")):
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


def version_name(song, n):
    """Bestandsnaam in forScore voor een versie: 'Titel - Artiest V2.pdf'."""
    return forscore_name(song)[:-4] + f" V{n}.pdf"


def version_title(song, n):
    return f"{song.get('title') or song.get('_id', '').split('/')[-1]} V{n}"


def _source(song):
    return pathlib.Path(song["_path"]).read_text(encoding="utf-8")


def _has(lib, name):
    return bool(name) and lib is not None and lib.ok and lib.has(name)


def fs_record(project, song, lib, hist=None):
    """Het stuk in forScore bij dit nummer: de nieuwste versie die in forScore staat.
    Geeft (record of None, dubbelen, versie of None). Zonder versies: herkennen op naam/titel."""
    from . import versions as V
    if lib is None or not lib.ok:
        return None, [], None
    hist = hist or V.history(project, song["_path"], attach=False)
    for v in reversed(hist.versions):
        if _has(lib, v.get("forscore")):
            rec = lib.get(v["forscore"])
            dups = [r for r in lib.scores.values()
                    if r["file"].lower() != rec["file"].lower() and _base(r["file"]) == _base(rec["file"])]
            return rec, ([rec] + dups if dups else []), v
    if not hist.versions:
        rec, dups = match(song, lib, None)
        return rec, dups, None
    return None, [], None


def old_versions_in_forscore(hist, lib, current):
    """Oudere versies die nog in forScore staan (mogen weg zodra je je aantekeningen hebt overgezet)."""
    seen, out = {str(current or "").lower()}, []
    for v in hist.versions:
        f = v.get("forscore")
        if f and f.lower() not in seen and _has(lib, f):
            seen.add(f.lower())
            out.append(f)
    return out


def song_status(project, song, lib):
    """Alles wat de Studio over één nummer moet weten."""
    from . import versions as V
    hist = V.history(project, song["_path"], attach=False)
    h = V.content_hash(_source(song))
    latest = hist.latest
    rec, dups, v_in = fs_record(project, song, lib, hist)
    if latest is None:
        st = "actueel" if rec is not None else "niet"
    elif latest["hash"] != h:
        st = "gewijzigd"
    elif (v_in is not None and v_in["n"] == latest["n"]) or \
            (latest.get("same_as") and v_in is not None and v_in["n"] == latest["same_as"]) or \
            (not lib.ok and latest.get("sent")):
        st = "actueel"
    else:
        st = "wacht"                                 # nieuwste versie staat nog niet in forScore
    if not lib.ok and latest is None:
        st = "niet"
    return {"status": st, "hist": hist, "rec": rec, "dups": dups, "v_in": v_in,
            "version": latest["n"] if latest else None, "next": hist.next_number(h),
            "old": old_versions_in_forscore(hist, lib, rec["file"] if rec else None) if lib.ok else []}


def status(project, song, lib, state=None):
    """'niet' (niet in forScore), 'gewijzigd' (wordt een nieuwe versie), 'wacht' (versie nog niet in forScore),
    'actueel'."""
    return song_status(project, song, lib)["status"]


# ---------------------------------------------------------------------------
# versturen: elke versie is een eigen stuk in forScore, er wordt NOOIT iets overschreven

def send(project, items, open_app=True, log=print, lib=None, note="", **_ignored):
    """items: (song, pdf[, score]). Per nummer:
      - geen versies, staat al in forScore  → dat stuk wordt V1 (er wordt niets verstuurd);
      - geen versies, niet in forScore      → V1, als nieuw stuk 'Titel - Artiest V1';
      - muzikaal gewijzigd                  → nieuwe versie Vn, als nieuw stuk 'Titel - Artiest Vn';
      - nieuwste versie staat in forScore   → niets.
    Bestaande stukken (met jouw aantekeningen) worden nooit aangeraakt. Alles wordt gecontroleerd.
    Geeft de forScore-bestandsnamen die (nu) in forScore staan."""
    from . import versions as V
    out = project.out("forscore")
    out.mkdir(parents=True, exist_ok=True)
    lib = lib or library()
    four, style = use_4sc(project)
    jobs, present = [], []
    for it in items:
        song, pdf = it[0], pathlib.Path(it[1])
        score = it[2] if len(it) > 2 else None
        title = song.get("title") or song.get("_id")
        hist = V.history(project, song["_path"])
        text = _source(song)
        h = V.content_hash(text)
        v = hist.latest
        if v is None:
            if not lib.ok:
                log(f"  ! {title}: overgeslagen. De forScore-bibliotheek kan niet gelezen worden, dus ik kan niet "
                    "controleren of het er al in staat (en maak liever geen dubbele).")
                continue
            rec, dups = match(song, lib, None)
            if rec is not None:
                v = hist.add(text, pdf, note="stond al in forScore", adopted=rec["file"], song=song)
                log(f"= {title}: stond al in forScore als '{rec['file']}'. Dat is nu V1 (niets verstuurd).")
                if dups:
                    log(f"  ! staat {len(dups)}× in forScore: {', '.join(d['file'] for d in dups)}")
                present.append(rec["file"])
                continue
            v = hist.add(text, pdf, note=note, song=song, auto=not note)
        elif v["hash"] != h:
            v = hist.add(text, pdf, note=note, song=song, auto=not note)
            log(f"• {title}: nieuwe versie V{v['n']}" + (f" ({v['changes']})" if v.get("changes") else ""))
        # staat deze versie al in forScore?
        if v.get("forscore") and (_has(lib, v["forscore"]) or (not lib.ok and v.get("sent"))):
            present.append(v["forscore"])
            continue
        if v.get("same_as") and lib.ok:
            old = hist.get(v["same_as"])
            if old and _has(lib, old.get("forscore")):
                v.update(forscore=old["forscore"], sent=True, reused=old["n"])
                hist.save()
                log(f"= {title}: V{v['n']} is gelijk aan V{old['n']}, en die staat nog in forScore "
                    f"('{old['forscore']}'): die wordt gebruikt")
                present.append(old["forscore"])
                continue
        name = version_name(song, v["n"])
        if _has(lib, name):
            v.update(forscore=name, sent=True)
            hist.save()
            present.append(name)
            continue
        src = hist.pdf(v["n"]) or pdf
        if not src.exists():
            log(f"  ! {title}: nog geen PDF")
            continue
        meta = metadata(song, score)
        meta["title"] = version_title(song, v["n"])
        if four:
            dst = out / (name[:-4] + ".4sc")
            dst.write_bytes(build_4sc(name, src.read_bytes(), meta, style))
        else:
            dst = out / name
            write_pdf(src, dst, dict(song, title=meta["title"]))
        jobs.append((hist, v, name, dst))
    if not jobs:
        log("= forScore: alles staat er al actueel in")
        return present
    if not open_app:
        log(f"✓ {len(jobs)} bestand(en) klaargezet in {out.relative_to(project.root)}/")
        return present
    log(f"→ naar forScore: {', '.join(j[2] for j in jobs)}")
    if not open_files([j[3] for j in jobs], log):
        return present
    missing = []
    if lib.ok:
        _, missing = wait_for([j[2] for j in jobs], log=log)
        missing = missing or []
    for hist, v, name, dst in jobs:
        if name in missing:
            log(f"  ✗ {name}: niet in forScore verschenen (vroeg forScore iets? kijk op de Mac)")
            continue
        v.update(forscore=name, sent=True, sent_time=int(time.time()))
        hist.save()
        present.append(name)
        log(f"  ✓ {name}" + (" staat in forScore" if lib.ok else " verstuurd (niet gecontroleerd)"))
    return present


# ---------------------------------------------------------------------------
# setlists: ook met versies; een setlist gebruikt altijd de nieuwste versie van elk nummer

def _rows_equal(a, b):
    return [str(x).lower() for x in a] == [str(x).lower() for x in b]


def setlist_rows(project, entries, lib):
    """[(titel, forScore-bestandsnaam of None)] voor een setlist."""
    from . import versions as V
    from .build import load_and_arrange
    from .rows import NotationError
    rows = []
    for e in entries:
        if e.kind == "break":
            if e.display:
                rows.append((e.display, None))
            continue
        if e.kind == "song":
            if not e.path:
                rows.append((e.title or e.ref, None))
                continue
            try:
                s = load_and_arrange(project, e.path).song
            except NotationError:
                rows.append((e.title or e.ref, None))
                continue
            if lib.ok:
                rec, _, _ = fs_record(project, s, lib)
                rows.append((s.get("title", e.ref), rec["file"] if rec else None))
            else:
                hist = V.history(project, s["_path"], attach=False)
                sent = [v for v in hist.versions if v.get("sent") and v.get("forscore")]
                rows.append((s.get("title", e.ref), sent[-1]["forscore"] if sent else None))
        elif e.kind == "pdf" and e.pdf:
            rows.append((e.title or pathlib.Path(e.pdf).stem, pathlib.Path(e.pdf).name))
    return rows


def _want(rows):
    return [r[1] if r[1] else f"[{r[0]}]" for r in rows]


def setlist_status(project, f, lib):
    """(status, versie-info) van een setlist: 'niet', 'gewijzigd', 'wacht' of 'actueel'."""
    from . import setlist as sl
    from . import versions as V
    meta, entries = sl.parse_setlist(f.read_text(encoding="utf-8"), f.stem)
    sl.resolve(project, entries, f)
    sh = V.SetlistHistory(project, f.stem)
    latest = sh.latest
    title = meta.get("title") or f.stem
    rows = setlist_rows(project, entries, lib)
    if latest is None:
        if lib.ok and title in lib.setlists:
            return ("actueel" if _rows_equal(lib.setlists[title], _want(rows)) else "gewijzigd"), sh, title
        return "niet", sh, title
    if not _rows_equal(latest["rows"], _want(rows)):
        return "gewijzigd", sh, title
    if (lib.ok and latest["title"] in lib.setlists) or (not lib.ok and latest.get("sent")):
        return "actueel", sh, title
    return "wacht", sh, title


def send_setlist(project, name, open_app=True, log=print, songs=True):
    """Setlist naar forScore: eerst ontbrekende/gewijzigde nummers, dan de setlist (Open Setlist).
    Verandert er iets aan de setlist (of aan een nummer erin), dan komt er een nieuwe versie:
    'Titel V2'. De oude setlist blijft staan; forScore-setlists worden nooit overschreven."""
    from . import setlist as sl
    from . import versions as V
    from .build import build
    f = project.setlists_dir / (name if name.endswith(".txt") else f"{name}.txt")
    if not f.exists():
        log(f"✗ setlist '{name}' niet gevonden")
        return False
    text = f.read_text(encoding="utf-8")
    meta, entries = sl.parse_setlist(text, f.stem)
    for e in sl.resolve(project, entries, f):
        log(f"  ! {e}")
    lib = library()
    if songs:
        res = build(project, [e.path for e in entries if e.kind == "song" and e.path], log=lambda m: None)
        send(project, [(sc.song, project.out_file("pdf", p, "pdf"), sc) for p, sc, err in res if sc],
             open_app=open_app, log=log, lib=lib)
    out = project.out("forscore")
    out.mkdir(parents=True, exist_ok=True)
    ext_files = []
    for e in entries:                       # externe (gekochte) PDF's
        if e.kind == "pdf" and e.pdf:
            fname = pathlib.Path(e.pdf).name
            if not _has(lib, fname):
                shutil.copyfile(e.pdf, out / fname)
                ext_files.append(out / fname)
    if ext_files and open_app:
        log(f"→ externe PDF's naar forScore: {', '.join(p.name for p in ext_files)}")
        open_files(ext_files, log)
        if lib.ok:
            wait_for([p.name for p in ext_files], log=log)
    lib = library()
    title = meta.get("title") or f.stem
    rows = setlist_rows(project, entries, lib)
    want = _want(rows)
    sh = V.SetlistHistory(project, f.stem)
    latest = sh.latest
    if latest is None and lib.ok and title in lib.setlists:      # stond er al (zonder versie): dat is V1
        latest = sh.add(title, lib.setlists[title], text, adopted=True)
        latest["sent"] = True
        sh.save()
        log(f"= setlist '{title}' stond al in forScore: dat is V1")
    if latest is not None and _rows_equal(latest["rows"], want):
        if (lib.ok and latest["title"] in lib.setlists) or (not lib.ok and latest.get("sent")):
            log(f"= setlist '{latest['title']}' staat er al actueel in")
            return True
        v = latest                                                # weggegooid in forScore: opnieuw sturen
    else:
        v = sh.add(f"{title} V{len(sh.versions) + 1}", want, text)
        if latest is not None:
            log(f"• setlist '{title}': nieuwe versie V{v['n']}")
    dst = out / (safe_filename(v["title"]) + ".4ss")
    dst.write_text(build_4ss(v["title"], rows), encoding="utf-8")
    if not open_app:
        log(f"✓ setlist klaargezet: {dst.relative_to(project.root)}")
        return True
    if lib.ok and v["title"] in lib.setlists:
        log(f"  ✗ er staat al een andere setlist '{v['title']}' in forScore. Geef die in forScore een andere naam "
            "of verwijder hem, en probeer opnieuw.")
        return False
    log(f"→ setlist '{v['title']}' naar forScore ({sum(1 for r in rows if r[1])} stukken, "
        f"{sum(1 for r in rows if not r[1])} plaatshouders)")
    if not open_files([dst], log):
        return False
    if lib.ok:
        lib2, _ = wait_for([], setlist=v["title"], log=log)
        if lib2 is None or v["title"] not in lib2.setlists:
            log(f"  ✗ setlist '{v['title']}' niet in forScore verschenen (vroeg forScore iets? kijk op de Mac)")
            return False
        got = [g.lower() for g in lib2.setlists[v["title"]]]
        lost = [w for w in want if not w.startswith("[") and w.lower() not in got]
        if lost:
            log(f"  ✗ setlist staat in forScore, maar {len(lost)} stuk(ken) zijn niet gekoppeld: {', '.join(lost)}")
            return False
        log(f"  ✓ setlist '{v['title']}' staat compleet in forScore ({len(got)} regels)")
    v["sent"] = True
    v["sent_time"] = int(time.time())
    sh.save()
    return True


# ---------------------------------------------------------------------------
# alles in één keer: Drumsheetz → forScore

def sync(project, open_app=True, log=print):
    """Zorg dat forScore gelijk is aan Drumsheetz: nieuwe nummers, nieuwe versies, setlists.
    Wat niet automatisch kan (labels van bestaande stukken) komt als takenlijst; oude versies die nog in
    forScore staan als (vrijblijvende) opruimlijst."""
    from . import versions as V
    from .build import build
    lib = library()
    if not lib.ok:
        log("! de forScore-bibliotheek kon niet gelezen worden (" + "; ".join(lib.notes) + "). Nummers die nog "
            "nooit naar forScore gingen worden overgeslagen, zodat er geen dubbele ontstaan.")
    files = project.song_files()
    log(f"… {len(files)} nummers bijwerken (PDF's maken waar nodig)")
    res = build(project, files, log=lambda m: log(m) if m.startswith(("✗", "  !")) else None)
    items = [(sc.song, project.out_file("pdf", p, "pdf"), sc) for p, sc, err in res if sc]
    send(project, items, open_app=open_app, log=log, lib=lib)
    todo, cleanup = [], []
    lib = library()
    if lib.ok:
        for song, pdf, sc in items:
            hist = V.history(project, song["_path"], attach=False)
            rec, dups, v = fs_record(project, song, lib, hist)
            if rec is None:
                continue
            want, have = set(song_labels(song)), set(rec["labels"])
            if want != have:
                extra, missing = sorted(have - want), sorted(want - have)
                todo.append(f"'{rec['file'][:-4]}': " + "; ".join(
                    ([f"label toevoegen: {', '.join(missing)}"] if missing else []) +
                    ([f"label weghalen: {', '.join(extra)}"] if extra else []))
                    + (f" (of zet het nummer in Drumsheetz in de map {' / '.join(extra)}, of zet "
                       f"'labels: {', '.join(extra)}' in het nummer)" if extra and not missing else ""))
            if dups:
                todo.append(f"'{rec['file'][:-4]}' staat {len(dups)}× in forScore: verwijder "
                            + ", ".join(d["file"] for d in dups if d["file"] != rec["file"]))
            old = old_versions_in_forscore(hist, lib, rec["file"])
            if old:
                cleanup.append(f"{', '.join(o[:-4] for o in old)} (nieuwste: {rec['file'][:-4]})")
    ok = True
    if project.setlists_dir.exists():
        for f in sorted(project.setlists_dir.glob("*.txt")):
            ok = send_setlist(project, f.stem, open_app=open_app, log=log, songs=False) and ok
            if lib.ok:
                sh = V.SetlistHistory(project, f.stem)
                lib = library()
                olds = [v["title"] for v in sh.versions[:-1] if v["title"] in lib.setlists
                        and sh.latest and v["title"] != sh.latest["title"]]
                if olds:
                    cleanup.append(f"setlist {', '.join(olds)} (nieuwste: {sh.latest['title']})")
    if cleanup:
        log("\nOude versies die nog in forScore staan (mag je weggooien als je je aantekeningen hebt overgezet):")
        for c in cleanup:
            log(f"  · {c}")
    if todo:
        log("\nZelf doen in forScore (dit kan Drumsheetz niet veilig voor je doen):")
        for t in todo:
            log(f"  • {t}")
    elif ok:
        log("\n✓ forScore is gelijk aan Drumsheetz")
    return todo


# ---------------------------------------------------------------------------
# labels ophalen (forScore → 'labels:' in de nummers)

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
        rec, _, _ = fs_record(project, song, lib)
        if rec is None:
            continue
        folders = set(folder_labels(song))                       # de map telt al als label
        new = sorted(x for x in rec["labels"] if x not in folders)
        cur = sorted(set(split_list(song.get("labels"))) | set(split_list(song.get("fs_library"))))
        if cur != new:
            changes.append((f, cur, new))
    for f, cur, new in changes:
        log(f"  {project.song_id(f)}: extra labels {', '.join(cur) or '—'} → {', '.join(new) or '—'}")
    if not changes:
        log("✓ de labels in forScore zijn gelijk aan Drumsheetz")
    elif apply:
        from .studio import Studio
        st = Studio(project.root)
        for f, cur, new in changes:
            rel = str(f.relative_to(project.root)).replace("\\", "/")
            st.set_header({"path": rel, "key": "map", "value": "", "mode": "set"})       # oud veld opruimen
            st.set_header({"path": rel, "key": "labels", "value": ", ".join(new), "mode": "set"})
        log(f"✓ {len(changes)} nummer(s) bijgewerkt")
    else:
        log("(nog niets veranderd)")
    return changes


# ---------------------------------------------------------------------------
# overzicht voor de Studio

def catalog(project):
    from .build import load_and_arrange
    from .rows import NotationError
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
        info = song_status(project, s, lib)
        rec, dups = info["rec"], info["dups"]
        if rec is not None:
            matched.add(rec["file"].lower())
            for d in dups:
                matched.add(d["file"].lower())
        for o in info["old"]:
            matched.add(o.lower())
        for v in info["hist"].versions:
            if v.get("forscore"):
                matched.add(v["forscore"].lower())
        want = song_labels(s)
        latest = info["hist"].latest
        songs.append({"id": sid, "path": rel, "title": s.get("title", f.stem), "artist": s.get("artist", ""),
                      "name": rec["file"] if rec else version_name(s, info["next"]),
                      "status": info["status"], "sent": rec is not None if lib.ok else bool(latest and latest.get("sent")),
                      "version": info["version"], "next": info["next"],
                      "fs_version": info["v_in"]["n"] if info["v_in"] else (1 if rec is not None else None),
                      "old_in_forscore": info["old"],
                      "library": sorted(rec["labels"]) if rec is not None else want,
                      "dups": [d["file"] for d in dups], "labels_want": want,
                      "labels_have": sorted(rec["labels"]) if rec is not None else [],
                      "label_todo": sorted(set(want) ^ set(rec["labels"])) if rec is not None else [],
                      "duration": fmt_duration(sc.seconds())})
    setlists = []
    if project.setlists_dir.exists():
        from . import setlist as sl
        for f in sorted(project.setlists_dir.glob("*.txt")):
            meta, entries = sl.parse_setlist(f.read_text(encoding="utf-8"), f.stem)
            sl.resolve(project, entries, f)
            st, sh, title = setlist_status(project, f, lib)
            items = [{"title": e.display if e.kind == "break" else (e.title or e.ref),
                      "id": project.song_id(e.path) if e.path and e.kind == "song" else "", "kind": e.kind}
                     for e in entries if e.kind in ("song", "pdf", "break")]
            setlists.append({"name": f.stem, "path": f"setlists/{f.name}", "title": title, "items": items,
                             "status": st, "sent": st == "actueel" or bool(sh.latest and sh.latest.get("sent")),
                             "version": sh.latest["n"] if sh.latest else None,
                             "fs_title": sh.latest["title"] if sh.latest else None})
    only_fs = [r["file"] for k, r in lib.scores.items() if k not in matched] if lib.ok else []
    duplicates = [s_["dups"] for s_ in songs if s_.get("dups")]
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
