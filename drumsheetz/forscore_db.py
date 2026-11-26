"""De forScore-bibliotheek op de Mac uitlezen (alleen lezen).

forScore documenteert zijn database niet. Deze module herkent de structuur aan de INHOUD:
  - stukken:   de tabel met een kolom waarin vooral bestandsnamen op '.pdf' staan;
  - labels:    een tabel met 'LABEL' in de naam, gekoppeld via een koppeltabel of een tekstkolom;
  - setlists:  een tabel met 'SETLIST' in de naam, met de stukken via een koppel- of itemtabel.

Er wordt altijd een KOPIE van de database gelezen; forScore en iCloud merken er niets van.
Wat niet herkend wordt, wordt gemeld (zie 'python3 drums.py forscore --onderzoek').
"""
import os
import pathlib
import platform
import re
import shutil
import sqlite3
import tempfile

BUNDLE_HINTS = ("forscore",)
SYSTEM_TABLES = {"Z_PRIMARYKEY", "Z_METADATA", "Z_MODELCACHE", "SQLITE_SEQUENCE", "ACHANGE", "ATRANSACTION",
                 "ATRANSACTIONSTRING"}


def candidate_files():
    """Alle SQLite-databases in de containers van forScore op deze Mac, grootste eerst."""
    if platform.system() != "Darwin":
        return []
    roots = []
    for base in ("~/Library/Containers", "~/Library/Group Containers"):
        b = pathlib.Path(os.path.expanduser(base))
        try:
            roots += [p for p in b.iterdir() if any(h in p.name.lower() for h in BUNDLE_HINTS)]
        except OSError:
            continue
    found = []
    for r in roots:
        # de bibliotheek van forScore heet library.4sl (Data/Library/Preferences); die eerst
        direct = list(r.glob("Data/Library/Preferences/*.4sl")) + list(r.glob("**/library.4sl"))
        for p in direct:
            if p not in found:
                found.append(p)
        if direct:
            continue
        for p in r.rglob("*"):
            if any(part in ("WebKit", "Caches", "CloudKit", "HTTPStorages", ".tipkit") for part in p.parts):
                continue
            try:
                if p.is_file() and p.stat().st_size > 4096 and not p.name.endswith(("-wal", "-shm", "-journal")):
                    with open(p, "rb") as f:
                        if f.read(16) == b"SQLite format 3\x00":
                            found.append(p)
            except OSError:
                continue
    return sorted(found, key=lambda p: (p.suffix != ".4sl", -p.stat().st_size))


def _copy(db):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="drumsheetz-fs-"))
    dst = tmp / db.name
    shutil.copyfile(db, dst)
    for ext in ("-wal", "-shm"):
        side = pathlib.Path(str(db) + ext)
        if side.exists():
            shutil.copyfile(side, pathlib.Path(str(dst) + ext))
    return dst


def _connect(db):
    con = sqlite3.connect(f"file:{_copy(db)}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _tables(con):
    out = {}
    for (name,) in con.execute("select name from sqlite_master where type='table'"):
        cols = [(r[1], (r[2] or "").upper()) for r in con.execute(f'pragma table_info("{name}")')]
        out[name] = cols
    return out


def _count(con, t):
    try:
        return con.execute(f'select count(*) from "{t}"').fetchone()[0]
    except sqlite3.Error:
        return 0


def _pk(cols):
    names = [c for c, _ in cols]
    return "Z_PK" if "Z_PK" in names else "rowid"


def _text_cols(cols):
    return [c for c, t in cols if "CHAR" in t or "TEXT" in t or t == "" or "CLOB" in t]


def _sample(con, t, c, n=300):
    try:
        return [r[0] for r in con.execute(f'select "{c}" from "{t}" where "{c}" is not null limit {n}')]
    except sqlite3.Error:
        return []


class Library:
    """Wat er in forScore staat, zo goed als herkend."""

    def __init__(self):
        self.db = None
        self.scores = {}        # bestandsnaam (kleine letters) -> {"file", "title", "labels": set, "pk"}
        self.labels = set()
        self.setlists = {}      # titel -> [bestandsnaam, ...]
        self.notes = []         # wat wel/niet herkend is
        self.ok = False

    def has(self, filename):
        return filename.lower() in self.scores

    def get(self, filename):
        return self.scores.get(filename.lower())


def _find_scores(con, tables):
    best = None
    for t, cols in tables.items():
        if t.upper() in SYSTEM_TABLES or t.upper().startswith("Z_"):
            continue
        n = _count(con, t)
        if not n:
            continue
        for c in _text_cols(cols):
            vals = [str(v) for v in _sample(con, t, c) if isinstance(v, str)]
            if len(vals) < 1:
                continue
            pdf = sum(1 for v in vals if v.lower().endswith(".pdf"))
            if pdf / len(vals) >= 0.6 and (best is None or n > best[2]):
                best = (t, c, n)
    return best


def _name_col(con, t, cols, prefer=("ZTITLE", "ZNAME", "ZLABEL", "TITLE", "NAME")):
    names = [c for c, _ in cols]
    for p in prefer:
        if p in names:
            return p
    for c in _text_cols(cols):
        vals = [v for v in _sample(con, t, c, 50) if isinstance(v, str)]
        if vals and all(len(v) < 120 for v in vals):
            return c
    return None


def _join_tables(tables, keyword=None):
    """Core Data-koppeltabellen: Z_<n>NAAM met twee integer-kolommen. Met keyword alleen tabellen waarvan
    de naam of een kolom dat woord bevat (bv. LABEL of SETLIST), zodat ze niet verward worden."""
    out = []
    for t, cols in tables.items():
        if keyword and keyword not in t.upper() and not any(keyword in c.upper() for c, _ in cols):
            continue
        if t.upper().startswith("Z_") and t.upper() not in SYSTEM_TABLES:
            ints = [c for c, ty in cols if "INT" in ty and not c.upper().startswith("Z_FOK")]
            fok = [c for c, _ in cols if c.upper().startswith("Z_FOK")]
            if len(ints) >= 2:
                out.append((t, ints, fok[0] if fok else None))
    return out


def _pairs(con, jt, a, b, order=None):
    q = f'select "{a}" as a, "{b}" as b from "{jt}"' + (f' order by "{b}", "{order}"' if order else "")
    try:
        return [(r["a"], r["b"]) for r in con.execute(q)]
    except sqlite3.Error:
        return []


def _pkset(con, t, pk):
    try:
        return {r[0] for r in con.execute(f'select {pk} from "{t}"')}
    except sqlite3.Error:
        return set()


def _read_forscore_schema(con, tables, lib):
    """De echte opbouw van forScore (library.4sl, Core Data):
         ZITEM          stukken (ZPATH = bestandsnaam, ZTITLE), ook bladwijzers/plaatshouders
         ZMETA          componisten, genres, trefwoorden en labels (ZVALUE), soort via Z_ENT
         Z_4LABELS      koppeling stuk ↔ label (Z_4ITEMS2 ↔ Z_14LABELS), idem Z_4COMPOSERS, ...
         ZSETLIST       setlists (ZTITLE); ZCYLON = setlist-regels (ZITEM, ZSETLIST, volgorde Z_FOK_SETLIST)"""
    if not {"ZITEM", "ZMETA", "ZSETLIST"} <= set(tables):
        return False
    ents = {}
    if "Z_PRIMARYKEY" in tables:
        ents = {r["Z_ENT"]: str(r["Z_NAME"]) for r in con.execute("select Z_ENT, Z_NAME from Z_PRIMARYKEY")}
    icols = [c for c, _ in tables["ZITEM"]]
    has_score_ref = "ZSCORE" in icols
    q = "select Z_PK, Z_ENT, ZPATH, ZTITLE" + (", ZSCORE" if has_score_ref else "") + \
        (", ZPLACEHOLDER" if "ZPLACEHOLDER" in icols else "") + " from ZITEM"
    by_pk = {}
    for r in con.execute(q):
        ent = ents.get(r["Z_ENT"], "").lower()
        path = r["ZPATH"]
        if not path or not str(path).lower().endswith(".pdf"):
            continue
        if ent in ("bookmark", "placeholder") or (has_score_ref and r["ZSCORE"]):
            continue                                   # bladwijzer of plaatshouder, geen eigen stuk
        fname = pathlib.Path(str(path)).name
        rec = {"file": fname, "title": r["ZTITLE"] or fname[:-4], "labels": set(), "pk": r["Z_PK"],
               "composers": set()}
        lib.scores[fname.lower()] = rec
        by_pk[r["Z_PK"]] = rec
    mcols = [c for c, _ in tables["ZMETA"]]
    vcol = "ZVALUE" if "ZVALUE" in mcols else next((c for c in mcols if c.startswith("ZVALUE")), None)
    meta = {r["Z_PK"]: str(r["v"]) for r in con.execute(f'select Z_PK, "{vcol}" as v from ZMETA') if r["v"]} \
        if vcol else {}

    def join(kind, field):
        jt = next((t for t in tables if t.upper().startswith("Z_") and t.upper().endswith(kind)), None)
        if not jt:
            return None
        cols = [c for c, _ in tables[jt]]
        ci = next((c for c in cols if "ITEMS" in c.upper()), None)
        cm = next((c for c in cols if c != ci), None)
        if not (ci and cm):
            return None
        for r in con.execute(f'select "{ci}" as i, "{cm}" as m from "{jt}"'):
            if r["i"] in by_pk and r["m"] in meta:
                by_pk[r["i"]][field].add(meta[r["m"]])
        return jt

    jl = join("LABELS", "labels")
    join("COMPOSERS", "composers")
    lib.labels = {l for v in by_pk.values() for l in v["labels"]}
    titles = {r["Z_PK"]: str(r["ZTITLE"]) for r in con.execute("select Z_PK, ZTITLE from ZSETLIST") if r["ZTITLE"]}
    for t in titles.values():
        lib.setlists.setdefault(t, [])
    if "ZCYLON" in tables:
        ccols = [c for c, _ in tables["ZCYLON"]]
        order = "Z_FOK_SETLIST" if "Z_FOK_SETLIST" in ccols else "Z_PK"
        allitems = {r["Z_PK"]: r for r in con.execute("select Z_PK, ZPATH, ZTITLE from ZITEM")}
        for r in con.execute(f'select ZITEM, ZSETLIST from ZCYLON order by ZSETLIST, "{order}"'):
            if r["ZSETLIST"] in titles:
                it = allitems.get(r["ZITEM"])
                if it is not None and it["ZPATH"]:
                    lib.setlists[titles[r["ZSETLIST"]]].append(pathlib.Path(str(it["ZPATH"])).name)
                elif it is not None:
                    lib.setlists[titles[r["ZSETLIST"]]].append(f"[{it['ZTITLE'] or 'plaatshouder'}]")
    lib.ok = True
    lib.notes.append(f"forScore-bibliotheek: {len(by_pk)} stukken (ZITEM), {len(lib.labels)} labels "
                     f"({jl or 'geen koppeltabel'}), {len(titles)} setlists (ZSETLIST/ZCYLON)")
    return True


def read_library(db=None):
    lib = Library()
    dbs = [db] if db else candidate_files()
    if not dbs:
        lib.notes.append("geen forScore-database gevonden (alleen op een Mac met forScore voor Mac)")
        return lib
    for d in dbs:
        try:
            con = _connect(d)
        except (OSError, sqlite3.Error) as e:
            lib.notes.append(f"{d.name}: niet te lezen ({e})")
            continue
        try:
            tables = _tables(con)
            if _read_forscore_schema(con, tables, lib):
                lib.db = d
                break
            found = _find_scores(con, tables)
            if not found:
                continue
            st, scol, n = found
            lib.db = d
            spk = _pk(tables[st])
            tcol = _name_col(con, st, tables[st], ("ZTITLE", "ZNAME", "TITLE"))
            if tcol == scol:
                tcol = None
            for r in con.execute(f'select {spk} as pk, "{scol}" as f' + (f', "{tcol}" as t' if tcol else "")
                                 + f' from "{st}"'):
                if r["f"]:
                    fname = pathlib.Path(str(r["f"])).name
                    lib.scores[fname.lower()] = {"file": fname, "title": (r["t"] if tcol else None) or fname[:-4],
                                                 "labels": set(), "pk": r["pk"]}
            lib.ok = True
            lib.notes.append(f"stukken: tabel {st}, kolom {scol} ({n} rijen)" + (f", titel {tcol}" if tcol else ""))
            by_pk = {v["pk"]: v for v in lib.scores.values()}
            _read_labels(con, tables, st, spk, by_pk, lib)
            _read_setlists(con, tables, st, spk, scol, by_pk, lib)
        finally:
            con.close()
        if lib.ok:
            break
    if not lib.ok and not lib.notes:
        lib.notes.append("geen tabel met PDF-bestanden herkend")
    return lib


def _read_labels(con, tables, st, spk, by_pk, lib):
    lt = next((t for t in tables if "LABEL" in t.upper() and not t.upper().startswith("Z_")), None)
    if lt:
        lpk = _pk(tables[lt])
        lname = _name_col(con, lt, tables[lt])
        names = {}
        if lname:
            for r in con.execute(f'select {lpk} as pk, "{lname}" as n from "{lt}"'):
                if r["n"]:
                    names[r["pk"]] = str(r["n"])
            lib.labels = set(names.values())
        spks, lpks = set(by_pk), set(names)
        for jt, ints, _ in _join_tables(tables, "LABEL"):
            for a in ints:
                for b in ints:
                    if a == b:
                        continue
                    pairs = _pairs(con, jt, a, b)
                    if pairs and all(x in spks for x, _ in pairs) and all(y in lpks for _, y in pairs):
                        for x, y in pairs:
                            by_pk[x]["labels"].add(names[y])
                        lib.notes.append(f"labels: tabel {lt} ({lname}), koppeling {jt}.{a}/{b}")
                        return
        # labels als verwijzing vanuit de labeltabel naar een stuk
        for c, ty in tables[lt]:
            if "INT" in ty and c not in (lpk, "Z_ENT", "Z_OPT"):
                vals = [v for v in _sample(con, lt, c) if v is not None]
                if vals and all(v in spks for v in vals):
                    for r in con.execute(f'select "{c}" as s, "{lname}" as n from "{lt}"'):
                        if r["s"] in by_pk and r["n"]:
                            by_pk[r["s"]]["labels"].add(str(r["n"]))
                    lib.notes.append(f"labels: tabel {lt}.{c} verwijst naar stukken")
                    return
        lib.notes.append(f"labeltabel {lt} gevonden, maar de koppeling met stukken niet")
    # labels als tekst in de stukkentabel
    for c in _text_cols(tables[st]):
        if "LABEL" in c.upper():
            for r in con.execute(f'select {spk} as pk, "{c}" as n from "{st}"'):
                if r["n"] and r["pk"] in by_pk:
                    by_pk[r["pk"]]["labels"] |= {x.strip() for x in re.split(r"[,;\n]", str(r["n"])) if x.strip()}
            lib.labels |= {l for v in by_pk.values() for l in v["labels"]}
            lib.notes.append(f"labels: tekst in {st}.{c}")
            return
    if not lt:
        lib.notes.append("geen labels herkend")


def _read_setlists(con, tables, st, spk, scol, by_pk, lib):
    slt = next((t for t in tables if re.fullmatch(r"Z?SETLISTS?", t.upper())), None) or \
        next((t for t in tables if "SETLIST" in t.upper() and not t.upper().startswith("Z_")
              and "ITEM" not in t.upper()), None)
    if not slt:
        lib.notes.append("geen setlists herkend")
        return
    slpk = _pk(tables[slt])
    sname = _name_col(con, slt, tables[slt])
    titles = {r["pk"]: str(r["n"]) for r in con.execute(f'select {slpk} as pk, "{sname}" as n from "{slt}"')
              if r["n"]} if sname else {}
    for t in titles.values():
        lib.setlists.setdefault(t, [])
    spks, slpks = set(by_pk), set(titles)
    # 1) koppeltabel Z_nSETLISTS (eventueel met volgorde Z_FOK_...)
    for jt, ints, fok in _join_tables(tables, "SETLIST"):
        for a in ints:
            for b in ints:
                if a == b:
                    continue
                pairs = _pairs(con, jt, a, b, fok)
                if pairs and all(x in spks for x, _ in pairs) and all(y in slpks for _, y in pairs):
                    for x, y in pairs:
                        lib.setlists[titles[y]].append(by_pk[x]["file"])
                    lib.notes.append(f"setlists: tabel {slt} ({sname}), koppeling {jt}")
                    return
    # 2) itemtabel met een verwijzing naar de setlist en naar een stuk of een bestandsnaam
    for t, cols in tables.items():
        if t == slt or t == st or t.upper() in SYSTEM_TABLES:
            continue
        names = [c for c, _ in cols]
        ref_sl = next((c for c, ty in cols if "SETLIST" in c.upper() and "INT" in ty), None)
        if not ref_sl:
            continue
        order = next((c for c in names if any(k in c.upper() for k in ("ORDER", "INDEX", "POSITION", "SORT"))), None)
        ref_sc = next((c for c, ty in cols if "INT" in ty and c != ref_sl and
                       any(k in c.upper() for k in ("SCORE", "ITEM", "FILE", "DOCUMENT"))), None)
        path_c = next((c for c in _text_cols(cols) if any(str(v).lower().endswith(".pdf")
                                                         for v in _sample(con, t, c, 30))), None)
        if not (ref_sc or path_c):
            continue
        q = f'select "{ref_sl}" as sl, ' + (f'"{ref_sc}" as sc' if ref_sc else f'"{path_c}" as sc') + \
            f' from "{t}"' + (f' order by "{ref_sl}", "{order}"' if order else "")
        for r in con.execute(q):
            if r["sl"] in titles:
                f = by_pk[r["sc"]]["file"] if ref_sc and r["sc"] in by_pk else \
                    (pathlib.Path(str(r["sc"])).name if path_c and r["sc"] else None)
                if f:
                    lib.setlists[titles[r["sl"]]].append(f)
        lib.notes.append(f"setlists: tabel {slt} ({sname}), items in {t}")
        return
    lib.notes.append(f"setlisttabel {slt} gevonden, maar de stukken erin niet")


def investigate(log=print):
    """Laat zien wat er gevonden en herkend wordt (voor het afstemmen op jouw forScore-versie)."""
    if platform.system() != "Darwin":
        log("Dit werkt alleen op de Mac (waar forScore voor Mac staat).")
        return
    files = candidate_files()
    if not files:
        log("Geen forScore-database gevonden in ~/Library/Containers of ~/Library/Group Containers.")
        log("Staat forScore voor Mac geïnstalleerd en is hij een keer geopend? macOS kan ook vragen of de")
        log("Terminal 'gegevens van andere apps' mag lezen: sta dat toe.")
        return
    for db in files:
        log(f"\n=== {db}  ({db.stat().st_size // 1024} kB)")
        try:
            con = _connect(db)
            for t, cols in sorted(_tables(con).items()):
                log(f"  {t} ({_count(con, t)} rijen): " + ", ".join(f"{c}:{ty or '?'}" for c, ty in cols))
            con.close()
        except (OSError, sqlite3.Error) as e:
            log(f"  (niet te lezen: {e})")
    lib = read_library()
    log("\n=== herkend")
    for n in lib.notes:
        log("  " + n)
    log(f"  {len(lib.scores)} stukken, {len(lib.labels)} labels, {len(lib.setlists)} setlists")
    for v in list(lib.scores.values())[:8]:
        log(f"   · {v['file']}  [{', '.join(sorted(v['labels']))}]")
    for t, items in list(lib.setlists.items())[:5]:
        log(f"   ☰ {t}: {len(items)} stukken")
