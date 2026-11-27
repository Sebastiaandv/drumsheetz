"""Nagemaakte forScore voor de tests: doet bij het 'openen' van een bestand wat de echte forScore deed in de
zelftests op de Mac, en schrijft dat in een database met precies dezelfde opbouw als library.4sl.

Gebruik: python3 fake_forscore.py <bestand>      (database: $DRUMSHEETZ_FORSCORE_DB)
Gedrag bij een bestaand stuk: $FAKE_FORSCORE_MODE = overwrite (standaard) | duplicate | ignore
Blijft hangen op bestanden met $FAKE_FORSCORE_HANG in de naam.
"""
import gzip
import os
import pathlib
import plistlib
import re
import sqlite3
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ENT = {"Item": 4, "Score": 6, "Bookmark": 5, "Cylon": 3, "Composer": 10, "Genre": 12, "Keyword": 13,
       "Label": 14, "Setlist": 11, "Meta": 9}
META_COL = {"Composer": "ZVALUE", "Genre": "ZVALUE2", "Keyword": "ZVALUE3", "Label": "ZVALUE4"}
JOIN = {"Composer": ("Z_4COMPOSERS", "Z_4ITEMS1", "Z_10COMPOSERS"), "Genre": ("Z_4GENRES", "Z_4ITEMS4", "Z_12GENRES"),
        "Keyword": ("Z_4KEYWORDS", "Z_4ITEMS5", "Z_13KEYWORDS"), "Label": ("Z_4LABELS", "Z_4ITEMS2", "Z_14LABELS")}


def now():
    return time.time() - 978307200          # Core Data-tijd


def connect():
    db = pathlib.Path(os.environ["DRUMSHEETZ_FORSCORE_DB"])
    new = not db.exists()
    con = sqlite3.connect(db)
    if new:
        con.executescript("""
        create table Z_PRIMARYKEY(Z_ENT integer, Z_NAME varchar, Z_SUPER integer, Z_MAX integer);
        create table ZITEM(Z_PK integer primary key, Z_ENT integer, Z_OPT integer, ZBPM integer, ZKEY integer,
            ZPLACEHOLDER integer, ZSCORE integer, ZADDED timestamp, ZMODIFIED timestamp, ZPATH varchar,
            ZTITLE varchar, ZSIZE varchar, ZREFERENCE varchar, ZRATING integer, ZDIFFICULTY integer);
        create table ZMETA(Z_PK integer primary key, Z_ENT integer, Z_OPT integer, ZVALUE1 integer, ZVALUE5 integer,
            ZLAST varchar, ZVALUE varchar, ZVALUE2 varchar, ZVALUE3 varchar, ZVALUE4 varchar);
        create table Z_4COMPOSERS(Z_4ITEMS1 integer, Z_10COMPOSERS integer);
        create table Z_4GENRES(Z_4ITEMS4 integer, Z_12GENRES integer);
        create table Z_4KEYWORDS(Z_4ITEMS5 integer, Z_13KEYWORDS integer);
        create table Z_4LABELS(Z_4ITEMS2 integer, Z_14LABELS integer);
        create table Z_4LIBRARIES(Z_4ITEMS3 integer, Z_7LIBRARIES integer);
        create table ZSETLIST(Z_PK integer primary key, Z_ENT integer, Z_OPT integer, ZINDEX integer,
            ZTITLE varchar, ZUUID varchar);
        create table ZCYLON(Z_PK integer primary key, Z_ENT integer, Z_OPT integer, ZSHUFFLE integer, ZITEM integer,
            Z4_ITEM integer, ZSETLIST integer, Z_FOK_SETLIST integer, ZUUID varchar);
        """)
        con.executemany("insert into Z_PRIMARYKEY values (?,?,0,0)", [(v, k) for k, v in ENT.items()])
        con.commit()
    return con


def meta_id(con, kind, value):
    col = META_COL[kind]
    r = con.execute(f"select Z_PK from ZMETA where Z_ENT=? and {col}=?", (ENT[kind], value)).fetchone()
    if r:
        return r[0]
    cur = con.execute(f"insert into ZMETA (Z_ENT, Z_OPT, {col}) values (?,1,?)", (ENT[kind], value))
    return cur.lastrowid


def set_meta(con, item, kind, values):
    jt, ci, cm = JOIN[kind]
    for v in values:
        con.execute(f"insert into {jt} ({ci},{cm}) values (?,?)", (item, meta_id(con, kind, v)))


def add_score(con, name, size, title=None):
    mode = os.environ.get("FAKE_FORSCORE_MODE", "overwrite")
    r = con.execute("select Z_PK from ZITEM where ZPATH=?", (name,)).fetchone()
    if r:
        if mode == "overwrite":
            con.execute("update ZITEM set ZMODIFIED=?, ZSIZE=? where Z_PK=?", (now(), str(size), r[0]))
            return r[0], False
        if mode == "ignore":
            return r[0], False
        n = 2                                      # 'dupliceren': forScore maakt 'Naam 2.pdf'
        while con.execute("select 1 from ZITEM where ZPATH=?", (f"{name[:-4]} {n}.pdf",)).fetchone():
            n += 1
        name = f"{name[:-4]} {n}.pdf"
    t = now()
    cur = con.execute("insert into ZITEM (Z_ENT, Z_OPT, ZPATH, ZTITLE, ZADDED, ZMODIFIED, ZSIZE) values (?,1,?,?,?,?,?)",
                      (ENT["Score"], name, title or name[:-4], t, t, str(size)))
    return cur.lastrowid, True


def import_pdf(con, p):
    add_score(con, p.name, p.stat().st_size)


def import_4sc(con, p):
    plist = plistlib.loads(gzip.decompress(p.read_bytes()))
    keys = [k for k in plist if "|" in k]
    name = max({k.split("|", 1)[0] for k in keys}, key=lambda n: sum(k.startswith(n) for k in keys)) if keys \
        else p.stem + ".pdf"
    get = lambda f: plist.get(f"{name}|{f}")                       # noqa: E731
    item, new = add_score(con, name, len(plist["pdfData"]), get("title"))
    if not new:
        return
    if get("title"):
        con.execute("update ZITEM set ZTITLE=? where Z_PK=?", (get("title"), item))
    for f, kind in (("composer", "Composer"), ("labels", "Label"), ("genre", "Genre"), ("keywords", "Keyword")):
        v = get(f)
        if isinstance(v, str):                     # zoals de echte forScore: alleen tekst wordt overgenomen
            set_meta(con, item, kind, [x.strip() for x in v.split(",") if x.strip()])


def import_4ss(con, p):
    root = ET.fromstring(p.read_text(encoding="utf-8"))
    cur = con.execute("insert into ZSETLIST (Z_ENT, Z_OPT, ZINDEX, ZTITLE, ZUUID) values (?,1,0,?,?)",
                      (ENT["Setlist"], root.get("title"), str(uuid.uuid4())))
    sl = cur.lastrowid
    for i, el in enumerate(root, 1):
        if el.tag == "score":
            r = con.execute("select Z_PK from ZITEM where ZPATH=?", (el.get("path"),)).fetchone()
            if not r:
                continue                            # onbekend pad: forScore slaat het over
            item = r[0]
        elif el.tag == "placeholder":
            item = con.execute("insert into ZITEM (Z_ENT, Z_OPT, ZPATH, ZTITLE, ZPLACEHOLDER) values (?,1,?,?,0)",
                               (ENT["Score"], str(uuid.uuid4()).upper(), el.get("title"))).lastrowid
        else:
            continue
        con.execute("insert into ZCYLON (Z_ENT, Z_OPT, ZITEM, Z4_ITEM, ZSETLIST, Z_FOK_SETLIST) values (?,1,?,?,?,?)",
                    (ENT["Cylon"], item, ENT["Score"], sl, i))


def main():
    p = pathlib.Path(sys.argv[1])
    hang = os.environ.get("FAKE_FORSCORE_HANG")
    if hang and hang in p.name:                    # forScore blijft hangen op 'Loading… 0 of 1'
        log = os.environ.get("FAKE_FORSCORE_LOG")
        if log:
            with open(log, "a", encoding="utf-8") as f:
                f.write(p.name + "\n")
        return
    con = connect()
    {".pdf": import_pdf, ".4sc": import_4sc, ".4ss": import_4ss}[p.suffix.lower()](con, p)
    con.commit()
    con.close()
    log = os.environ.get("FAKE_FORSCORE_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(p.name + "\n")


if __name__ == "__main__":
    main()


def set_label(db, filename, label):
    """Hulpje voor de tests: een label zetten zoals je dat in forScore zelf zou doen."""
    os.environ["DRUMSHEETZ_FORSCORE_DB"] = str(db)
    con = connect()
    item = con.execute("select Z_PK from ZITEM where ZPATH=?", (filename,)).fetchone()[0]
    set_meta(con, item, "Label", [label])
    con.commit()
    con.close()


def items(db):
    con = sqlite3.connect(db)
    try:
        return [r[0] for r in con.execute("select ZPATH from ZITEM where ZPATH like '%.pdf' order by Z_PK")]
    finally:
        con.close()


_ = re
