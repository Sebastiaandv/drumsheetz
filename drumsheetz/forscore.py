"""Nummers naar forScore sturen (Mac), dat via iCloud-synchronisatie op de iPad zet.

Werking:
  1. Elke PDF krijgt een vaste, leesbare bestandsnaam ("Titel - Artiest.pdf") en titel/artiest/tags
     in de PDF-gegevens (als pypdf geïnstalleerd is).
  2. Alleen nieuwe of gewijzigde PDF's worden naar uitvoer/forscore/ gekopieerd en met forScore op de
     Mac geopend (open -a forScore). forScore importeert ze; bij een bestaande naam kies je
     'Overschrijven' (gegevens en annotaties blijven dan bewaard).
  3. Met iCloud-synchronisatie aan in forScore staan ze daarna vanzelf op de iPad.
"""
import hashlib
import json
import pathlib
import platform
import shutil
import subprocess

from .project import safe_filename


def forscore_name(song):
    title = song.get("title") or song.get("_id", "nummer")
    artist = song.get("artist", "")
    return safe_filename(f"{title} - {artist}" if artist else title) + ".pdf"


def add_metadata(src, dst, song):
    """Kopieer de PDF en zet titel/artiest/trefwoorden erin. Zonder pypdf: gewone kopie."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        shutil.copyfile(src, dst)
        return False
    r = PdfReader(str(src))
    w = PdfWriter()
    for p in r.pages:
        w.add_page(p)
    meta = {"/Title": str(song.get("title", "")), "/Author": str(song.get("artist", "")),
            "/Creator": "Drumsheetz"}
    kw = [str(song[k]) for k in ("tags", "feel", "key") if song.get(k)]
    if kw:
        meta["/Keywords"] = ", ".join(kw)
    if song.get("subtitle"):
        meta["/Subject"] = str(song["subtitle"])
    w.add_metadata(meta)
    with open(dst, "wb") as f:
        w.write(f)
    return True


def find_app():
    """Is forScore op deze Mac geïnstalleerd?"""
    if platform.system() != "Darwin":
        return None
    try:
        r = subprocess.run(["mdfind", "kMDItemCFBundleIdentifier == 'com.mgsdevelopment.forscore'"],
                           capture_output=True, text=True, timeout=20)
        hits = [x for x in r.stdout.splitlines() if x.endswith(".app")]
        if hits:
            return hits[0]
    except (OSError, subprocess.TimeoutExpired):
        pass
    if pathlib.Path("/Applications/forScore.app").exists():
        return "/Applications/forScore.app"
    return "forScore"


def send(project, items, force=False, open_app=True, log=print):
    """items: lijst (song-dict, pad naar PDF). Geeft het aantal verstuurde bestanden."""
    out = project.out("forscore")
    out.mkdir(parents=True, exist_ok=True)
    state_file = project.out(".forscore.json")
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    todo, meta_ok = [], True
    for song, pdf in items:
        if not pdf.exists():
            log(f"  ! {song.get('_id')}: nog geen PDF (eerst 'maak')")
            continue
        digest = hashlib.sha1(pdf.read_bytes() + json.dumps(
            [song.get(k) for k in ("title", "artist", "tags", "feel", "key", "subtitle")]).encode()).hexdigest()
        name = forscore_name(song)
        old = state.get(song["_id"], {})
        if not force and old.get("hash") == digest and old.get("name") == name:
            continue
        dst = out / name
        meta_ok = add_metadata(pdf, dst, song) and meta_ok
        if old.get("name") and old["name"] != name:
            log(f"  ! {song['_id']}: naam veranderd ('{old['name']}' → '{name}'); "
                "in forScore komt dit als nieuw stuk binnen, verwijder daar zelf het oude")
        todo.append((song, dst, digest, name))
    if not todo:
        log("= forScore: alles is al bijgewerkt")
        return 0
    if not meta_ok:
        log("  ! pypdf niet gevonden: titel/artiest niet in de PDF gezet (pip3 install pypdf)")
    app = find_app() if open_app else None
    if open_app and not app:
        log(f"✓ {len(todo)} PDF('s) klaar in {out.relative_to(project.root)}/ "
            "(forScore openen kan alleen op een Mac; sleep ze er zelf in)")
    elif open_app:
        try:
            subprocess.run(["open", "-a", app] + [str(d) for _, d, _, _ in todo], check=True, timeout=60)
            log(f"✓ {len(todo)} PDF('s) naar forScore gestuurd: " + ", ".join(n for _, _, _, n in todo))
            log("  Vraagt forScore of hij moet overschrijven? Kies 'Overschrijven' (houdt je annotaties).")
        except (OSError, subprocess.SubprocessError) as e:
            log(f"✗ forScore openen lukte niet ({e}). De PDF's staan in {out.relative_to(project.root)}/")
            return 0
    for song, dst, digest, name in todo:
        state[song["_id"]] = {"hash": digest, "name": name}
    state_file.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    return len(todo)
