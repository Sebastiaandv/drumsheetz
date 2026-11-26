"""Labels uit forScore op de Mac lezen, om ze als 'mappen' in Drumsheetz over te nemen.

forScore documenteert zijn database niet. Daarom:
  - we zoeken de database(s) in de app-container van forScore op de Mac;
  - we lezen ALLEEN een kopie (nooit het origineel), dus forScore en iCloud merken er niets van;
  - 'onderzoek' laat zien wat er gevonden is (tabellen en kolommen), zodat het precies gemaakt kan worden;
  - het koppelen van stukken aan labels gebeurt op bestandsnaam ('Titel - Artiest.pdf').
"""
import os
import pathlib
import platform
import re
import shutil
import sqlite3
import tempfile

SEARCH_ROOTS = [
    "~/Library/Containers/com.mgsdevelopment.forscore",
    "~/Library/Containers/com.mgsdevelopment.forscore.mac",
    "~/Library/Group Containers",
]


def candidate_files():
    """SQLite-bestanden in de forScore-containers op deze Mac."""
    found = []
    for root in SEARCH_ROOTS:
        base = pathlib.Path(os.path.expanduser(root))
        if not base.exists():
            continue
        if base.name == "Group Containers":
            bases = [p for p in base.iterdir() if "forscore" in p.name.lower()]
        else:
            bases = [base]
        for b in bases:
            for p in b.rglob("*"):
                try:
                    if p.is_file() and p.stat().st_size > 1024 and not p.name.endswith(("-wal", "-shm")):
                        with open(p, "rb") as f:
                            if f.read(16) == b"SQLite format 3\x00":
                                found.append(p)
                except OSError:
                    continue
    return found


def _copy(db):
    tmp = pathlib.Path(tempfile.mkdtemp())
    dst = tmp / db.name
    shutil.copyfile(db, dst)
    for ext in ("-wal", "-shm"):
        side = pathlib.Path(str(db) + ext)
        if side.exists():
            shutil.copyfile(side, pathlib.Path(str(dst) + ext))
    return dst


def schema(db):
    con = sqlite3.connect(f"file:{_copy(db)}?mode=ro", uri=True)
    try:
        out = {}
        for (name,) in con.execute("select name from sqlite_master where type='table'"):
            cols = [r[1] for r in con.execute(f'pragma table_info("{name}")')]
            n = con.execute(f'select count(*) from "{name}"').fetchone()[0]
            out[name] = (cols, n)
        return out
    finally:
        con.close()


def _pick(cols, *wanted):
    up = {c.upper(): c for c in cols}
    for w in wanted:
        if w in up:
            return up[w]
    for w in wanted:
        for cu, c in up.items():
            if w in cu:
                return c
    return None


def read_labels(db):
    """Probeer per bestandsnaam de labels te vinden. Geeft (dict bestandsnaam->set(labels), uitleg)."""
    con = sqlite3.connect(f"file:{_copy(db)}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        tables = {n: [r[1] for r in con.execute(f'pragma table_info("{n}")')]
                  for (n,) in con.execute("select name from sqlite_master where type='table'")}
        label_t = next((t for t in tables if re.fullmatch(r"Z?LABELS?", t.upper())), None) or \
            next((t for t in tables if "LABEL" in t.upper() and not t.upper().startswith("Z_")), None)
        score_t = next((t for t in tables if re.fullmatch(r"Z?(SCORE|ITEM|FILE|DOCUMENT)S?", t.upper())), None) or \
            next((t for t in tables if any(k in t.upper() for k in ("SCORE", "ITEM")) and not t.upper().startswith("Z_")), None)
        if not label_t or not score_t:
            return {}, f"geen label- of stukkentabel herkend (label: {label_t}, stukken: {score_t})"
        lname = _pick(tables[label_t], "ZTITLE", "ZNAME", "ZLABEL", "TITLE", "NAME")
        sfile = _pick(tables[score_t], "ZPATH", "ZFILENAME", "ZFILE", "PATH", "FILENAME", "ZNAME")
        lpk = "Z_PK" if "Z_PK" in tables[label_t] else "rowid"
        spk = "Z_PK" if "Z_PK" in tables[score_t] else "rowid"
        if not lname or not sfile:
            return {}, f"kolommen niet herkend in {label_t}/{score_t}"
        result = {}
        # 1) koppeltabel (Core Data veel-op-veel): Z_<n>LABELS met kolommen naar beide kanten
        sbase = re.sub(r"^Z", "", score_t.upper()).rstrip("S")
        lbase = re.sub(r"^Z", "", label_t.upper()).rstrip("S")
        for t, cols in tables.items():
            if not t.upper().startswith("Z_"):
                continue
            cl = next((c for c in cols if lbase in c.upper()), None)
            cs = next((c for c in cols if sbase in c.upper()), None)
            if cl and cs and cl != cs:
                q = (f'select s."{sfile}" as f, l."{lname}" as n from "{t}" j join "{score_t}" s on s.{spk}=j."{cs}" '
                     f'join "{label_t}" l on l.{lpk}=j."{cl}"')
                for r in con.execute(q):
                    if r["f"] and r["n"]:
                        result.setdefault(pathlib.Path(str(r["f"])).name, set()).add(str(r["n"]))
                if result:
                    return result, f"labels via koppeltabel {t}"
        # 2) labels als tekst in een kolom van de stukkentabel
        col = _pick(tables[score_t], "ZLABELS", "ZLABEL", "LABELS")
        if col:
            for r in con.execute(f'select "{sfile}" as f, "{col}" as n from "{score_t}"'):
                if r["f"] and r["n"] and isinstance(r["n"], str):
                    result[pathlib.Path(r["f"]).name] = {x.strip() for x in re.split(r"[,;\n]", r["n"]) if x.strip()}
            if result:
                return result, f"labels als tekst in {score_t}.{col}"
        return {}, "label- en stukkentabel gevonden, maar geen koppeling herkend"
    finally:
        con.close()


def investigate(log=print):
    if platform.system() != "Darwin":
        log("Dit werkt alleen op de Mac (waar forScore voor Mac staat).")
        return
    files = candidate_files()
    if not files:
        log("Geen forScore-database gevonden in ~/Library/Containers of ~/Library/Group Containers.")
        log("Staat forScore voor Mac geïnstalleerd en is hij een keer geopend?")
        return
    for db in files:
        log(f"\n=== {db}")
        try:
            sc = schema(db)
        except sqlite3.Error as e:
            log(f"  (niet te lezen: {e})")
            continue
        for t, (cols, n) in sorted(sc.items()):
            log(f"  {t} ({n} rijen): {', '.join(cols)}")
        try:
            labels, how = read_labels(db)
            log(f"  → labels: {how}; {len(labels)} stukken met labels")
            for f, ls in list(labels.items())[:10]:
                log(f"     {f}: {', '.join(sorted(ls))}")
        except sqlite3.Error as e:
            log(f"  → labels lezen mislukt: {e}")


def pull_labels(project, apply=False, log=print):
    """Labels uit forScore als 'map:' in de nummers zetten (alleen voor nummers die in forScore staan)."""
    from .build import load_and_arrange
    from .forscore import forscore_name, split_list
    from .rows import NotationError
    if platform.system() != "Darwin":
        log("Labels ophalen kan alleen op de Mac (waar forScore voor Mac staat).")
        return []
    best, how = {}, ""
    for db in candidate_files():
        try:
            labels, h = read_labels(db)
        except sqlite3.Error:
            continue
        if len(labels) > len(best):
            best, how = labels, h
    if not best:
        log("Geen labels gevonden in de forScore-database. Draai 'python3 drums.py forscore --onderzoek' "
            "en stuur de uitvoer op, dan maak ik het passend.")
        return []
    log(f"forScore: {len(best)} stukken met labels ({how})")
    by_name = {k.lower(): v for k, v in best.items()}
    changes = []
    for f in project.song_files(include_parked=True):
        if f.suffix != ".drum":
            continue
        try:
            song = load_and_arrange(project, f).song
        except NotationError:
            continue
        fs = by_name.get(forscore_name(song).lower())
        if fs is None:
            continue
        cur = split_list(song.get("fs_library"))
        other = set(split_list(song.get("labels")))          # aparte 'labels:' blijven labels
        new = sorted(x for x in fs if x not in other)
        if sorted(cur) != new:
            changes.append((f, cur, new))
    for f, cur, new in changes:
        log(f"  {project.song_id(f)}: map {', '.join(cur) or '—'} → {', '.join(new) or '—'}")
    if not changes:
        log("✓ mappen zijn al gelijk aan de labels in forScore")
    elif apply:
        from .studio import Studio
        st = Studio(project.root)
        for f, cur, new in changes:
            st.set_header({"path": str(f.relative_to(project.root)).replace("\\", "/"), "key": "map",
                           "value": ", ".join(new), "mode": "set"})
        log(f"✓ {len(changes)} nummer(s) bijgewerkt")
    else:
        log("(nog niets veranderd: gebruik --toepassen, of de knop in de Studio)")
    return changes
