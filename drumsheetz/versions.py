"""Versiebeheer voor nummers (en setlists).

Uitgangspunten (waterdicht):
  - Een versie is een vaste momentopname: de .drum-tekst (en de PDF) van dat moment, in versies/<nummer>/.
    Versiebestanden worden nooit veranderd of weggegooid (alleen-lezen, met controlesom).
  - Alleen MUZIKALE wijzigingen maken een nieuwe versie. Wat alleen voor forScore is (labels, genre,
    waardering, ...) telt niet mee, en spaties aan het eind van een regel ook niet.
  - Terugzetten schrijft een oude versie terug in het nummer; wat er stond wordt eerst als reservekopie bewaard.
    De geschiedenis loopt altijd door: terugzetten naar V2 wordt bij de volgende keer V5 (= V2).
  - Verplaatst of hernoemd nummer: de geschiedenis gaat mee (Studio), of wordt teruggevonden
    (aan de inhoud of aan titel + artiest) als het buiten de Studio om is verplaatst.
"""
import difflib
import hashlib
import json
import os
import pathlib
import re
import shutil
import time

VDIR = "versies"
INDEX = "versies.json"
SETLISTS = ".setlists"
# kopregels die alleen voor forScore zijn: geen nieuwe versie als alleen deze veranderen
FS_ONLY = {"labels", "fs_library", "genre", "tags", "rating", "difficulty", "reference", "fs_name"}
BODY_START = re.compile(r"^(groove|fill|patroon|pattern|ritme|instrument|kit)\s|^\s*(\[|\d)", re.I)
HEADER = re.compile(r"^([A-Za-z][\w\-]*)\s*:")


# ---------------------------------------------------------------------------
# inhoud

def normalize(text):
    """De tekst zoals die voor de versie telt (zonder forScore-velden en losse spaties)."""
    from .parser import HEADER_KEYS
    out, head = [], True
    for ln in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        s = ln.rstrip()
        if head:
            c = s.split("#", 1)[0]
            if BODY_START.match(c):
                head = False
            else:
                m = HEADER.match(c)
                if m and HEADER_KEYS.get(m.group(1).lower(), m.group(1).lower()) in FS_ONLY:
                    continue
        if not s and out and not out[-1]:
            continue                                # meerdere lege regels = één
        out.append(s)
    while out and not out[-1]:
        out.pop()
    while out and not out[0]:
        out.pop(0)
    return "\n".join(out) + "\n"


def content_hash(text):
    return hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()[:16]


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def regions(lines):
    """Per regel: in welk deel van het nummer hij staat ('kop', 'patroon X', 'deel X')."""
    out, cur = [], "kop"
    for ln in lines:
        c = ln.split("#", 1)[0]
        m = re.match(r"^\s*\[([^\]]+)\]", c)
        p = re.match(r"^(groove|fill|patroon|pattern|ritme)\s+([^\s:{]+)", c, re.I)
        if m:
            cur = f"deel {m.group(1).strip()}"
        elif p:
            cur = f"patroon {p.group(2)}"
        elif cur == "kop" and BODY_START.match(c):
            cur = "nummer"
        out.append(cur)
    return out


def summarize(old, new):
    """Korte omschrijving van wat er veranderd is: '+3 −1 regels: deel Refrein, kop'."""
    a, b = normalize(old).split("\n"), normalize(new).split("\n")
    ra, rb = regions(a), regions(b)
    plus = minus = 0
    where = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        minus += i2 - i1
        plus += j2 - j1
        for r in (ra[i1:i2] or ra[max(i1 - 1, 0):i1]) + rb[j1:j2]:
            if r not in where:
                where.append(r)
    if not plus and not minus:
        return "geen muzikale wijzigingen"
    return f"+{plus} −{minus} regels" + (f": {', '.join(where[:6])}" + (" …" if len(where) > 6 else "") if where else "")


def diff(old, new, context=3):
    """Regels voor een verschil-weergave: [(soort, tekst)] met soort ' ', '+', '-', '@'."""
    out = []
    for ln in difflib.unified_diff(str(old).splitlines(), str(new).splitlines(), lineterm="", n=context):
        if ln.startswith(("---", "+++")):
            continue
        out.append((ln[0] if ln[:1] in "+-@ " else " ", ln[1:] if ln[:1] in "+- " else ln))
    return out


# ---------------------------------------------------------------------------
# geschiedenis van één nummer

def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)                           # in één keer: nooit een half geschreven bestand


def _readonly(p):
    try:
        os.chmod(p, 0o444)
    except OSError:
        pass


def _norm(x):
    return re.sub(r"[^a-z0-9]+", "", str(x or "").lower())


class History:
    def __init__(self, project, sid):
        self.project = project
        self.sid = sid
        self.dir = root(project) / sid
        self.file = self.dir / INDEX
        try:
            self.data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("versions", [])
        self.data.setdefault("backups", [])

    # -- opvragen
    @property
    def versions(self):
        return self.data["versions"]

    @property
    def latest(self):
        return self.versions[-1] if self.versions else None

    def get(self, n):
        n = int(n)
        return next((v for v in self.versions if v["n"] == n), None)

    def text(self, n):
        v = self.get(n)
        if v is None:
            raise ValueError(f"V{n} bestaat niet")
        return (self.dir / v["file"]).read_text(encoding="utf-8")

    def pdf(self, n):
        v = self.get(n)
        p = self.dir / v["pdf"] if v and v.get("pdf") else None
        return p if p and p.exists() else None

    def next_number(self, h):
        """Het versienummer dat deze inhoud heeft (of krijgt)."""
        if self.latest and self.latest["hash"] == h:
            return self.latest["n"]
        return len(self.versions) + 1

    # -- veranderen
    def save(self):
        _write_json(self.file, self.data)

    def add(self, text, pdf=None, note="", adopted=None, song=None, auto=False):
        """Nieuwe versie vastleggen. adopted: bestaande forScore-naam (stuk stond er al)."""
        h = content_hash(text)
        prev = self.latest
        n = len(self.versions) + 1
        self.dir.mkdir(parents=True, exist_ok=True)
        ext = pathlib.Path(self.data.get("path", "x.drum")).suffix or ".drum"
        f = self.dir / f"V{n}{ext}"
        if f.exists():                              # zou niet mogen: nooit iets overschrijven
            f = self.dir / f"V{n}-{int(time.time())}{ext}"
        raw = text.encode("utf-8")
        f.write_bytes(raw)
        _readonly(f)
        v = {"n": n, "hash": h, "sha256": _sha(raw), "file": f.name, "time": int(time.time()),
             "note": note or "", "auto": bool(auto)}
        if prev is not None:
            v["changes"] = summarize(self.text(prev["n"]), text)
        same = next((o for o in reversed(self.versions) if o["hash"] == h), None)
        if same is not None:
            v["same_as"] = same["n"]
            if not note:
                v["note"] = f"gelijk aan V{same['n']}"
        pending = self.data.pop("pending_note", None)
        if pending and not note:
            v["note"] = pending
        if pdf is not None and pathlib.Path(pdf).exists():
            pf = self.dir / f"{f.stem}.pdf"
            shutil.copyfile(pdf, pf)
            _readonly(pf)
            v["pdf"] = pf.name
            v["pdf_sha256"] = _sha(pf.read_bytes())
        if adopted:
            v["forscore"] = adopted
            v["adopted"] = True
            v["sent"] = True
        if song is not None:
            self.data["title"] = song.get("title", "")
            self.data["artist"] = song.get("artist", "")
        self.versions.append(v)
        self.save()
        return v

    def backup(self, text, why):
        """Reservekopie van de werkversie (vóór terugzetten e.d.)."""
        bdir = self.dir / "reserve"
        bdir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        f = bdir / f"{stamp}.drum"
        i = 2
        while f.exists():
            f = bdir / f"{stamp}-{i}.drum"
            i += 1
        f.write_text(text, encoding="utf-8")
        _readonly(f)
        self.data["backups"].append({"file": f"reserve/{f.name}", "time": int(time.time()), "why": why,
                                     "hash": content_hash(text)})
        self.save()
        return f

    def check(self):
        """Controleer of alle versiebestanden er nog zijn en niet veranderd zijn."""
        problems = []
        for v in self.versions:
            p = self.dir / v["file"]
            if not p.exists():
                problems.append(f"{self.sid} V{v['n']}: bestand {v['file']} ontbreekt")
            elif _sha(p.read_bytes()) != v.get("sha256"):
                problems.append(f"{self.sid} V{v['n']}: {v['file']} is veranderd (hoort vast te staan)")
            if v.get("pdf"):
                pp = self.dir / v["pdf"]
                if not pp.exists():
                    problems.append(f"{self.sid} V{v['n']}: PDF {v['pdf']} ontbreekt")
                elif v.get("pdf_sha256") and _sha(pp.read_bytes()) != v["pdf_sha256"]:
                    problems.append(f"{self.sid} V{v['n']}: PDF {v['pdf']} is veranderd")
        return problems


def root(project):
    return pathlib.Path(project.root) / VDIR


def _all_histories(project):
    r = root(project)
    if not r.exists():
        return []
    return [p.parent for p in r.rglob(INDEX) if SETLISTS not in p.parts]


def history(project, path, attach=True):
    """De geschiedenis bij een nummerbestand. Staat die er niet onder het huidige id, dan wordt een
    'verweesde' geschiedenis gezocht (nummer buiten de Studio om verplaatst of hernoemd) en verhuisd."""
    path = pathlib.Path(path)
    if not path.is_absolute():
        path = pathlib.Path(project.root) / path
    sid = project.song_id(path)
    h = History(project, sid)
    rel = os.path.relpath(path, project.root).replace("\\", "/")
    if not h.versions:
        orphan = _find_orphan(project, path)
        if orphan is not None:
            if not attach:
                o = History(project, orphan)
                o.sid = sid
                return o
            dst = root(project) / sid
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(root(project) / orphan, dst)
            h = History(project, sid)
            h.data.setdefault("moved", []).append({"from": orphan, "time": int(time.time())})
    if attach and h.data.get("path") != rel and (h.versions or h.data.get("path")):
        h.data["path"] = rel
        h.save()
    elif not h.data.get("path"):
        h.data["path"] = rel
    return h


def _find_orphan(project, path):
    """Geschiedenis waarvan het nummer niet meer bestaat en die bij dit nummer past."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    hsh = content_hash(text)
    title = artist = ""
    for ln in text.splitlines()[:40]:
        m = re.match(r"^\s*(titel|title)\s*:\s*(.+)$", ln, re.I)
        if m:
            title = m.group(2).strip()
        m = re.match(r"^\s*(artiest|artist)\s*:\s*(.+)$", ln, re.I)
        if m:
            artist = m.group(2).strip()
    by_hash, by_name = [], []
    for d in _all_histories(project):
        try:
            data = json.loads((d / INDEX).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        p = data.get("path")
        if not data.get("versions") or not p or (pathlib.Path(project.root) / p).exists():
            continue                                 # nummer bestaat nog: niet verweesd
        sid = os.path.relpath(d, root(project)).replace("\\", "/")
        if any(v["hash"] == hsh for v in data["versions"]):
            by_hash.append(sid)
        elif title and _norm(data.get("title")) == _norm(title) and _norm(data.get("artist")) == _norm(artist):
            by_name.append(sid)
    for group in (by_hash, by_name):
        if len(group) == 1:
            return group[0]
    return None


def move(project, old_sid, new_sid):
    """Geschiedenis mee verhuizen (Studio: hernoemen/verplaatsen)."""
    src, dst = root(project) / old_sid, root(project) / new_sid
    if not (src / INDEX).exists() or dst.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)
    h = History(project, new_sid)
    h.data.setdefault("moved", []).append({"from": old_sid, "time": int(time.time())})
    ext = pathlib.Path(h.data.get("path", "x.drum")).suffix or ".drum"
    h.data["path"] = os.path.relpath(pathlib.Path(project.songs_dir) / (new_sid + ext),
                                     project.root).replace("\\", "/")
    h.save()
    _cleanup_empty(root(project))
    return True


def _cleanup_empty(base):
    if not base.exists():
        return
    for d in sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda x: -len(x.parts)):
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


def version_label(project, path, text=None):
    """Versienummer voor op het blad: het nummer dat deze inhoud heeft of bij de volgende versie krijgt."""
    try:
        text = text if text is not None else pathlib.Path(path).read_text(encoding="utf-8")
        h = history(project, path, attach=False)
        return h.next_number(content_hash(text))
    except Exception:  # noqa: BLE001 - het blad nooit laten mislukken op het versienummer
        return None


# ---------------------------------------------------------------------------
# acties (Studio en opdrachtregel)

def song_path(project, rel):
    p = pathlib.Path(project.root) / rel
    if not p.is_file():
        raise ValueError(f"nummer niet gevonden: {rel}")
    return p


def info(project, rel):
    p = song_path(project, rel)
    h = history(project, p)
    text = p.read_text(encoding="utf-8")
    hsh = content_hash(text)
    latest = h.latest
    vs = []
    for v in reversed(h.versions):
        vs.append(dict(v, has_pdf=bool(h.pdf(v["n"])), current=(v["hash"] == hsh)))
    return {"id": h.sid, "versions": vs, "backups": list(reversed(h.data["backups"])),
            "changed": latest is None or latest["hash"] != hsh, "next": h.next_number(hsh),
            "latest": latest["n"] if latest else None,
            "pending": summarize(h.text(latest["n"]), text) if latest and latest["hash"] != hsh else "",
            "problems": h.check()}


def create(project, rel, note="", log=print):
    """Handmatig een nieuwe versie maken (met PDF). Geen wijzigingen: dan alleen de notitie bijwerken."""
    from .build import build
    p = song_path(project, rel)
    h = history(project, p)
    text = p.read_text(encoding="utf-8")
    if h.latest and h.latest["hash"] == content_hash(text):
        if note:
            h.latest["note"] = note
            h.save()
            log(f"= geen muzikale wijzigingen sinds V{h.latest['n']}: alleen de notitie bijgewerkt")
        else:
            log(f"= geen muzikale wijzigingen sinds V{h.latest['n']}")
        return h.latest
    res = build(project, [p], log=log)
    if not res or res[0][1] is None:
        raise ValueError("het nummer bevat fouten; los die eerst op")
    pdf = project.out_file("pdf", p, "pdf")
    v = h.add(text, pdf if pdf.exists() else None, note=note, song=res[0][1].song)
    log(f"✓ V{v['n']} gemaakt" + (f" ({v['changes']})" if v.get("changes") else ""))
    return v


def set_note(project, rel, n, note):
    h = history(project, song_path(project, rel))
    v = h.get(n)
    if v is None:
        raise ValueError(f"V{n} bestaat niet")
    v["note"] = str(note or "").strip()
    v["auto"] = False
    h.save()
    return v


def restore(project, rel, n, log=print):
    """Oude versie terugzetten in het nummer. Eerst een reservekopie van wat er nu staat."""
    p = song_path(project, rel)
    h = history(project, p)
    old = h.text(n)
    cur = p.read_text(encoding="utf-8")
    if content_hash(cur) == h.get(n)["hash"] and cur == old:
        log(f"= het nummer is al gelijk aan V{n}")
        return {"ok": True, "changed": False}
    h.backup(cur, f"vóór terugzetten naar V{n}")
    p.write_text(old, encoding="utf-8")
    if h.latest and h.latest["n"] != n:
        h.data["pending_note"] = f"teruggezet naar V{n}"
        h.save()
    log(f"✓ V{n} teruggezet (wat er stond is bewaard als reservekopie)")
    return {"ok": True, "changed": True}


def restore_backup(project, rel, file, log=print):
    p = song_path(project, rel)
    h = history(project, p)
    b = next((x for x in h.data["backups"] if x["file"] == file), None)
    if b is None:
        raise ValueError("reservekopie niet gevonden")
    text = (h.dir / b["file"]).read_text(encoding="utf-8")
    h.backup(p.read_text(encoding="utf-8"), "vóór terugzetten van een reservekopie")
    p.write_text(text, encoding="utf-8")
    h.data.pop("pending_note", None)
    h.save()
    log("✓ reservekopie teruggezet")
    return {"ok": True}


def compare(project, rel, a, b="werk"):
    """Verschil tussen twee versies ('werk' = wat er nu in het nummer staat)."""
    p = song_path(project, rel)
    h = history(project, p)

    def get(x):
        return p.read_text(encoding="utf-8") if str(x) in ("werk", "", "None") else h.text(int(x))
    ta, tb = get(a), get(b)
    return {"lines": diff(ta, tb), "summary": summarize(ta, tb)}


def check_all(project):
    problems = []
    for d in _all_histories(project):
        sid = os.path.relpath(d, root(project)).replace("\\", "/")
        problems += History(project, sid).check()
    return problems


# ---------------------------------------------------------------------------
# setlists

class SetlistHistory:
    """Versies van een setlist zoals die naar forScore ging (titel + regels)."""

    def __init__(self, project, stem):
        self.file = root(project) / SETLISTS / f"{stem}.json"
        try:
            self.data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("versions", [])

    @property
    def versions(self):
        return self.data["versions"]

    @property
    def latest(self):
        return self.versions[-1] if self.versions else None

    def add(self, title, rows, text="", adopted=False):
        v = {"n": len(self.versions) + 1, "title": title, "rows": list(rows), "time": int(time.time()),
             "text": text}
        if adopted:
            v["adopted"] = True
        self.versions.append(v)
        _write_json(self.file, self.data)
        return v

    def save(self):
        _write_json(self.file, self.data)
