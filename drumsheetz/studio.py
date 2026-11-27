"""Drumsheetz Studio: een lokale interface in je browser.

    python3 drums.py studio            start op http://127.0.0.1:8765 en opent de browser
    python3 drums.py studio --server   servermodus: bereikbaar vanuit het thuisnetwerk (bv. achter een proxy)

Standaard alleen bereikbaar vanaf deze computer. In servermodus alleen vanaf privé-adressen (thuisnetwerk,
VPN, proxy), nooit rechtstreeks vanaf internet. De .drum-bestanden blijven gewone tekstbestanden.
"""
import ipaddress
import contextlib
import io
import json
import mimetypes
import pathlib
import re
import threading
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .project import CODE_ROOT, Project, folder_too_deep, simplify

HERE = pathlib.Path(__file__).resolve().parent
LOCK = threading.Lock()
TEXT_EXT = {".drum", ".txt", ".py", ".md"}


# Documenteigenschappen (de kop van een .drum-bestand): (sleutel, intern, label, type, keuzes, uitleg, groep, instelling)
PROPS = [
    ("titel", "title", "Titel", "text", None, "Bovenaan de PDF", "Algemeen", None),
    ("ondertitel", "subtitle", "Ondertitel", "text", None, "Kleinere regel onder de titel", "Algemeen", "subtitle"),
    ("artiest", "artist", "Artiest", "text", None, "Rechtsboven", "Algemeen", None),
    ("vermelding", "credit", "Vermelding", "text", None,
     "Rechtsboven onder de artiest, bv. 'Drum sheet: {naam}'. Leeg = niets. Meerdere regels met \\n", "Algemeen", "credit"),
    ("componist", "composer", "Componist", "text", None, "Linksboven op het blad als 'Muziek: …'", "Algemeen", None),
    ("album", "album", "Album", "text", None, "Linksboven op het blad", "Algemeen", None),
    ("jaar", "year", "Jaar", "text", None, "Linksboven, achter het album", "Algemeen", None),
    ("tempo", "bpm", "Tempo", "text", None, "Bv. 92, of 4.=60 / 8=200", "Muziek", None),
    ("maat", "meter", "Maatsoort", "text", None, "Bv. 4/4, 6/8, 7/8 (2+2+3)", "Muziek", None),
    ("stijl", "feel", "Stijl", "text", None, "Cursieve regel onder het tempo", "Muziek", None),
    ("notitie", "notes", "Notitie", "text", None, "Extra cursieve regel", "Muziek", None),
    ("swing", "swing", "Swing", "select", ["", "ja", "16"], "'Swing' bij de stijl en swing in de MIDI", "Muziek", None),
    ("aftellen", "countin", "Aftellen (maten)", "number", None, "Maten stokken tikken vooraf", "Muziek", None),
    ("toonsoort", "key", "Toonsoort", "text", None, "Linksboven op het blad", "Muziek", None),
    ("stemmen", "voices", "Stemmen", "select", ["", "1", "2"],
     "1 = alles stok omhoog, 2 = voeten apart omlaag", "Opmaak", "voices"),
    ("layout", "layout", "Indeling", "select", ["", "secties", "doorlopend"],
     "secties = elke sectie op een nieuwe regel", "Opmaak", None),
    ("maten-per-regel", "bars_per_line", "Maten per regel", "number", None, "Vast aantal maten per regel", "Opmaak", None),
    ("herhaaltekens", "compress", "%-maten", "select", ["", "ja", "nee"], "nee = alles uitschrijven", "Opmaak", None),
    ("herhaalteller", "count_pos", "Plek van 'N×'", "select", ["", "binnen", "links", "boven"],
     "binnen = rechts naast het %-teken", "Opmaak", "count_pos"),
    ("tekstgrootte", "text_size", "Tekstgrootte", "text", None,
     "klein, normaal, groot of punten (bv. 9)", "Opmaak", "text_size"),
    ("stijlgrootte", "feel_size", "Grootte stijlregel", "text", None, "klein, normaal, groot of punten", "Opmaak",
     "feel_size"),
    ("accenten", "accent_pos", "Accenten", "select", ["", "boven", "onder", "auto"], "Boven of onder de noten",
     "Opmaak", "accent_pos"),
    ("vorken", "wedge_pos", "Crescendo/dim", "select", ["", "onder", "boven"], "Vorken met hun letters",
     "Opmaak", "wedge_pos"),
    ("dynamiek", "dyn_pos", "Losse dynamiek", "select", ["", "boven", "onder"], "mf, p, ... boven of onder",
     "Opmaak", "dyn_pos"),
    ("genre", "genre", "Genre", "text", None, "forScore: genres (meerdere met komma)", "forScore", None),
    ("labels", "labels", "Extra labels", "text", None,
     "forScore: labels naast de map(pen) waarin het nummer staat (meerdere met komma)", "forScore", None),
    ("waardering", "rating", "Waardering", "select", ["", "1", "2", "3", "4", "5"], "forScore: sterren", "forScore", None),
    ("moeilijkheid", "difficulty", "Moeilijkheid", "select", ["", "1", "2", "3"], "forScore: moeilijkheid (1-3)",
     "forScore", None),
    ("referentie", "reference", "Referentie", "text", None, "forScore: referentie (bv. boeknummer)", "forScore", None),
    ("forscore-naam", "fs_name", "Bestandsnaam", "text", None,
     "Naam in forScore (standaard 'Titel - Artiest'); niet veranderen na het eerste versturen", "forScore", None),
    ("duur", "duration", "Duur", "text", None, "Niet op het blad: voor de lijst en setlists, bv. 4:32 (anders berekend)", "Lijsten en setlists", None),
    ("status", "status", "Status", "text", None, "Bv. klaar, concept. Linksboven op het blad en in de lijst", "Algemeen", None),
    ("tags", "tags", "Tags", "text", None, "Niet op het blad: trefwoorden om op te zoeken (lijst --zoek)", "Lijsten en setlists", None),
    ("pdf", "pdf", "Externe PDF", "text", None, "Niet op het blad: in setlists deze PDF gebruiken in plaats van de eigen sheet",
     "Lijsten en setlists", None),
    ("bron", "source", "Bron", "text", None, "Linksboven op het blad als 'Bron: …'", "Algemeen", None),
    ("audio", "audio", "Audio", "text", None, "Niet op het blad: pad naar een opname om mee te oefenen", "Lijsten en setlists", None),
]


CODE_ITEMS = ("voorbeelden", "HANDLEIDING.md")      # horen bij het programma, niet bij je muziek


class Studio:
    def __init__(self, root):
        self.root = pathlib.Path(root).resolve()
        self.code = CODE_ROOT
        self.server_info = {}
        self._song_cache = {}

    # ------------------------------------------------------------------ hulp
    def project(self):
        return Project(self.root)

    def _base(self, rel):
        first = pathlib.PurePosixPath(str(rel).replace("\\", "/")).parts[:1]
        if self.code != self.root and first and first[0] in CODE_ITEMS:
            return self.code
        return self.root

    def safe(self, rel):
        base = self._base(rel)
        p = (base / rel).resolve()
        if base not in p.parents and p != base:
            raise ValueError("pad buiten de projectmap")
        return p

    def rel(self, p):
        p = pathlib.Path(p).resolve()
        try:
            return str(p.relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(p.relative_to(self.code)).replace("\\", "/")

    def run_cli(self, argv):
        """Voer een drums.py-opdracht uit en geef de uitvoer als tekst terug."""
        from .cli import main
        buf = io.StringIO()
        with LOCK, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                code = main(argv, self.root)
            except SystemExit as e:
                code = e.code
            except Exception:  # noqa: BLE001
                traceback.print_exc()
                code = 1
        return {"ok": not code, "log": buf.getvalue()}

    # ------------------------------------------------------------------ api
    def tree(self):
        def walk(d, exts):
            out = []
            if not d.exists():
                return out
            for p in sorted(d.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
                if p.name.startswith(".") or p.name == "__pycache__":
                    continue
                if p.is_dir():
                    out.append({"name": p.name, "path": self.rel(p), "dir": True, "children": walk(p, exts),
                                "parked": p.name.startswith("_")})
                elif p.suffix in exts:
                    out.append({"name": p.name, "path": self.rel(p), "dir": False})
            return out

        nodes = [
            {"name": "nummers", "path": "nummers", "dir": True, "open": True, "root": True,
             "children": walk(self.root / "nummers", {".drum", ".py"})},
            {"name": "setlists", "path": "setlists", "dir": True, "open": True, "root": True,
             "children": walk(self.root / "setlists", {".txt"})},
            {"name": "voorbeelden", "path": "voorbeelden", "dir": True, "root": True,
             "children": walk(self.safe("voorbeelden"), {".drum", ".py"})},
        ]
        for f in ("bibliotheek.drum", "instellingen.txt", "HANDLEIDING.md"):
            if self.safe(f).exists():
                nodes.append({"name": f, "path": f, "dir": False})
        return {"tree": nodes}

    def read(self, rel):
        p = self.safe(rel)
        return {"path": rel, "content": p.read_text(encoding="utf-8"), "kind": self.kind(rel)}

    def write(self, rel, content):
        p = self.safe(rel)
        if p.suffix not in TEXT_EXT:
            raise ValueError("alleen tekstbestanden (.drum, .txt, .py, .md) kunnen worden opgeslagen")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": rel}

    def kind(self, rel):
        rel = rel.replace("\\", "/")
        if rel == "bibliotheek.drum":
            return "library"
        if rel == "instellingen.txt":
            return "settings"
        if rel.startswith("setlists/") and rel.endswith(".txt"):
            return "setlist"
        if rel.endswith(".drum") or rel.endswith(".py"):
            return "song"
        return "text"

    def check(self, rel, content):
        """Controleer (ook niet-opgeslagen) inhoud. Geeft fout/waarschuwingen en de drumtab."""
        from .rows import NotationError
        kind = self.kind(rel)
        project = self.project()
        out = {"ok": True, "kind": kind, "error": None, "line": None, "warnings": [], "tab": "", "info": ""}
        try:
            if kind == "song":
                from .arrange import arrange
                from .musicxml import to_musicxml
                from .show import show_score
                from .project import fmt_duration
                if rel.endswith(".py"):
                    song, book, warns = project.load(self.safe(rel))
                else:
                    from .parser import parse_text
                    song, book, warns = parse_text(content, rel, project.library())
                    song["_file"], song["_id"] = rel, project.song_id(rel)
                score = arrange(song, book)
                to_musicxml(score, project.config)
                lines = []
                show_score(score, print=lines.append)
                out["tab"] = "\n".join(lines)
                out["warnings"] = list(warns) + score.warnings
                for name in list(book.items):
                    if not name.startswith("~"):
                        try:
                            out["warnings"] += book.warnings(name, score.meter)
                        except NotationError:
                            pass
                out["info"] = (f"{score.meter} · tempo {score.tempo[0]} · {score.total_bars} maten · "
                               f"± {fmt_duration(score.seconds())}")
                out["id"] = project.song_id(rel)
                out["pdf"] = project.out("pdf", f"{out['id']}.pdf").exists()
            elif kind == "library":
                from .library import builtin_book
                from .parser import Parser
                p = Parser(content, rel, builtin_book())
                _, book = p.parse_patterns_only()
                from .rows import Meter
                from .show import bar_grid
                lines = []
                for name, pat in book.items.items():
                    bars = book.compile(name, Meter(4, 4))
                    lines.append(f"{name}  ({bars[0].meter})  {pat.doc}")
                    for b in bars:
                        lines += bar_grid(b)
                    lines.append("")
                out["tab"] = "\n".join(lines)
                out["info"] = f"{len(book.items)} eigen patronen"
            elif kind == "setlist":
                from . import setlist as sl
                from .build import load_and_arrange
                meta, entries = sl.parse_setlist(content, pathlib.Path(rel).stem)
                errors = sl.resolve(project, entries, self.safe(rel))
                scores = {}
                for e in entries:
                    if e.kind == "song" and e.path:
                        try:
                            scores[str(e.path)] = load_and_arrange(project, e.path)
                        except NotationError as err:
                            errors.append(str(err))
                sl.enrich(project, entries, scores)
                out["tab"] = "\n".join(sl.overview_lines(meta, entries))
                out["warnings"] = errors
                n = sum(1 for e in entries if e.kind in ("song", "pdf"))
                out["info"] = f"setlist · {n} nummers"
                out["setlist"] = pathlib.Path(rel).stem
        except NotationError as e:
            out.update(ok=False, error=e.msg, line=e.line)
        except Exception as e:  # noqa: BLE001
            out.update(ok=False, error=f"{type(e).__name__}: {e}")
        return out

    def library(self):
        from .rows import Meter, parse_meter
        from .show import bar_grid
        lib = self.project().library()
        items = []
        for n in sorted(lib.names(), key=lambda n: (lib.get(n).kind != "groove", n)):
            pat = lib.get(n)
            try:
                bars = lib.compile(n, parse_meter(pat.meter) if pat.meter else Meter(4, 4))
                grid = "\n".join(line for b in bars for line in bar_grid(b))
                meter = str(bars[0].meter)
            except Exception:  # noqa: BLE001
                grid, meter = "", ""
            src = "ingebouwd" if (pat.file or "").startswith("<") else (pat.file or "")
            items.append({"name": n, "kind": pat.kind, "doc": pat.doc, "meter": meter, "grid": grid, "src": src})
        return {"items": items}

    def kit(self):
        from .kit import ALIASES, KIT, MODS
        inst = []
        for code, i in KIT.items():
            inst.append({"code": code, "name": i.name, "pos": f"{i.step}{i.octave}", "head": i.head,
                         "aliases": sorted(a for a, c in ALIASES.items() if c == code)})
        return {"instruments": inst, "mods": [{"ch": k, "desc": v} for k, v in MODS.items()]}

    def help(self):
        md = self.safe("HANDLEIDING.md")
        text = md.read_text(encoding="utf-8") if md.exists() else ""
        sections, cur = [], None
        in_code = False
        for line in text.splitlines():
            if line.startswith("```"):
                in_code = not in_code
            m = None if in_code else re.match(r"^(#{2,4})\s+(.*)$", line)
            if m:
                cur = {"level": len(m.group(1)), "title": m.group(2).strip(), "body": []}
                sections.append(cur)
            elif cur is not None:
                cur["body"].append(line)
        for s in sections:
            s["body"] = "\n".join(s["body"]).strip()
        return {"sections": [s for s in sections if s["body"] and s["title"] != "Inhoud"]}

    def props(self):
        from .parser import HEADER_KEYS
        cfg = self.project().config
        fields = [{"key": k, "id": i, "label": lab, "type": t, "options": o, "help": h, "group": g,
                   "default": (cfg.get(c, "") if c else "")} for k, i, lab, t, o, h, g, c in PROPS]
        return {"fields": fields, "aliases": HEADER_KEYS}

    def search(self, q, case=False):
        out = []
        if not q:
            return {"results": out}
        files = []
        for d, exts in (("nummers", (".drum", ".py")), ("setlists", (".txt",)), ("voorbeelden", (".drum", ".py"))):
            if self.safe(d).exists():
                files += sorted(p for p in self.safe(d).rglob("*") if p.suffix in exts)
        files += [self.safe(f) for f in ("bibliotheek.drum", "instellingen.txt", "HANDLEIDING.md")
                  if self.safe(f).exists()]
        needle = q if case else q.lower()
        for p in files:
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                if needle in (line if case else line.lower()):
                    out.append({"path": self.rel(p), "line": i, "text": line.strip()[:200]})
                    if len(out) >= 300:
                        return {"results": out, "more": True}
        return {"results": out}

    def fs_catalog(self):
        from .forscore import catalog
        with LOCK:
            return catalog(self.project())

    def set_header(self, data):
        """Kopregel in een .drum-bestand zetten/aanvullen/weghalen (voor slepen in de forScore-boom).
        mode: set (vervangen), add (aan lijst toevoegen), remove (uit lijst halen)."""
        from .parser import HEADER_KEYS
        rel, key, value, mode = data["path"], data["key"], str(data.get("value", "")).strip(), data.get("mode", "set")
        if not rel.endswith(".drum"):
            raise ValueError("alleen .drum-bestanden kunnen zo worden aangepast")
        p = self.safe(rel)
        lines = p.read_text(encoding="utf-8").split("\n")
        target = HEADER_KEYS.get(key.lower(), key)
        end = len(lines)
        for i, ln in enumerate(lines):
            c = ln.split("#", 1)[0]
            if re.match(r"^(groove|fill|patroon|pattern|ritme|instrument|kit)\s", c, re.I) or re.match(r"^\s*(\[|\d)", c):
                end = i
                break
        idx, cur = None, ""
        for i in range(end):
            m = re.match(r"^([A-Za-z][\w\-]*)\s*:\s*(.*?)\s*$", lines[i].split("#", 1)[0])
            if m and HEADER_KEYS.get(m.group(1).lower()) == target:
                idx, cur = i, m.group(2)
        items = [x.strip() for x in cur.split(",") if x.strip()]
        if mode == "add":
            if value and value not in items:
                items.append(value)
            new = ", ".join(items)
        elif mode == "remove":
            new = ", ".join(x for x in items if x != value)
        else:
            new = value
        if idx is not None:
            if new:
                lines[idx] = f"{key}: {new}"
            else:
                lines.pop(idx)
        elif new:
            last = max([i for i in range(end) if re.match(r"^[A-Za-z][\w\-]*\s*:", lines[i])] or [-1])
            lines.insert(last + 1, f"{key}: {new}")
        p.write_text("\n".join(lines), encoding="utf-8")
        return {"ok": True, "value": new}

    def status(self):
        from .musescore import find_musescore
        p = self.project()
        ms = find_musescore(p.config.get("musescore", ""))
        return {"musescore": ms or "", "root": str(self.root), "name": p.config.get("name", ""),
                "separate": p.separate}

    def new_song(self, data):
        from .project import safe_filename
        title = (data.get("title") or "").strip()
        if not title:
            raise ValueError("geef een titel op")
        argv = ["nieuw", title, data.get("artist") or ""]
        folder = (data.get("folder") or "").strip().strip("/")
        if folder.startswith("nummers"):
            folder = folder[len("nummers"):].strip("/")
        err = folder_too_deep(folder) if folder else None
        if err:
            raise ValueError(err)
        if folder:
            argv += ["--map", folder]
        if data.get("meter"):
            argv += ["--maat", data["meter"]]
        if data.get("tempo"):
            argv += ["--tempo", str(data["tempo"])]
        res = self.run_cli(argv)
        name = safe_filename(title).strip(". ") or "nummer"
        res["path"] = "/".join(x for x in ("nummers", folder, f"{name}.drum") if x)
        return res

    # ------------------------------------------------------------ bestanden beheren
    MANAGED = ("nummers", "setlists", "voorbeelden")

    def _check_managed(self, rel):
        parts = pathlib.PurePosixPath(rel).parts
        if not parts or parts[0] not in self.MANAGED:
            raise ValueError("alleen bestanden in nummers/, setlists/ en voorbeelden/ kunnen zo worden beheerd")
        for part in parts:
            if part in ("", ".", "..") or part.startswith(".") or any(c in part for c in '\\:*?"<>|'):
                raise ValueError(f"ongeldige naam '{part}' (niet met een punt beginnen, geen / \\ : * ? \" < > |)")
        return self.safe(rel)

    def _check_depth(self, rel_dir):
        """forScore kent geen mappen in mappen: nummers/<map> is het diepst, setlists/ heeft geen submappen."""
        parts = pathlib.PurePosixPath(rel_dir).parts
        if parts and parts[0] == "nummers":
            err = folder_too_deep(rel_dir)
            if err:
                raise ValueError(err)
        elif parts and parts[0] == "setlists" and len(parts) > 1:
            raise ValueError("setlists kunnen niet in mappen")

    def mkdir(self, data):
        p = self._check_managed(data["path"])
        self._check_depth(data["path"].strip("/"))
        if p.exists():
            raise ValueError("die map bestaat al")
        p.mkdir(parents=True)
        return {"ok": True, "path": self.rel(p)}

    def rmdir(self, data):
        p = self._check_managed(data["path"])
        if not p.is_dir():
            raise ValueError("geen map")
        if any(p.iterdir()):
            raise ValueError("de map is niet leeg: verplaats of archiveer eerst de inhoud")
        p.rmdir()
        return {"ok": True}

    def move(self, data):
        """Hernoemen of verplaatsen van een bestand of map. Uitvoer, setlists en forScore-administratie gaan mee."""
        src = self._check_managed(data["from"])
        dst_rel = data["to"].strip().strip("/")
        if src.is_file() and src.suffix and not pathlib.PurePosixPath(dst_rel).suffix:
            dst_rel += src.suffix                       # extensie hoeft niet getypt te worden
        dst = self._check_managed(dst_rel)
        if not src.exists():
            raise ValueError("bestand bestaat niet (meer)")
        if dst.exists() and dst.resolve() != src.resolve():
            raise ValueError(f"'{dst_rel}' bestaat al")
        if src.is_dir() and (dst.resolve() == src.resolve() or src.resolve() in dst.resolve().parents):
            raise ValueError("een map kan niet in zichzelf worden gezet")
        if self.rel(src).split("/")[0] != dst_rel.split("/")[0]:
            raise ValueError("verplaatsen kan alleen binnen dezelfde hoofdmap (nummers, setlists of voorbeelden)")
        # niet te diep: een map komt op dst_rel, een bestand in de map van dst_rel
        self._check_depth(dst_rel if src.is_dir() else str(pathlib.PurePosixPath(dst_rel).parent))
        if src.is_dir() and any(c.is_dir() and not c.name.startswith(".") for c in src.iterdir()) \
                and dst_rel.split("/")[0] == "nummers" and len(pathlib.PurePosixPath(dst_rel).parts) > 1:
            raise ValueError("deze map heeft zelf mappen; die kan niet in een andere map")
        project = self.project()
        songs = [src] if src.is_file() else [f for f in src.rglob("*") if f.suffix in (".drum", ".py")]
        mapping = []                                    # (oud pad, nieuw pad) per nummer
        for f in songs:
            new = dst if src.is_file() else dst / f.relative_to(src)
            mapping.append((f, new))
        with LOCK:
            dst.parent.mkdir(parents=True, exist_ok=True)
            old_ids = [(project.song_id(a), a.stem) for a, _ in mapping]
            src.rename(dst)
            if src.suffix == ".txt" and self.rel(dst).startswith("setlists/") and src.stem != dst.stem:
                self._move_setlist_extras(project, src.stem, dst.stem)
            for (a, b), (oid, ostem) in zip(mapping, old_ids):
                if b.suffix not in (".drum", ".py") or not str(b.resolve()).startswith(str(project.songs_dir.resolve())):
                    continue
                nid = project.song_id(b)
                if nid != oid:
                    self._move_outputs(project, oid, nid)
                    self._rename_refs(project, oid, ostem, nid)
            self._cleanup_empty(project)
        return {"ok": True, "path": self.rel(dst)}

    def _move_setlist_extras(self, project, old, new):
        """Bij een hernoemde setlist: versiegeschiedenis en gemaakte bestanden (uitvoer/setlists) gaan mee."""
        from . import versions as V
        h_old = V.root(project) / V.SETLISTS / f"{old}.json"
        h_new = V.root(project) / V.SETLISTS / f"{new}.json"
        if h_old.exists() and not h_new.exists():
            h_old.rename(h_new)
        out = project.out("setlists")
        if out.exists():
            for p in list(out.iterdir()):
                if p.name == old or p.name.startswith((old + ".", old + "-", old + " ")):
                    target = out / (new + p.name[len(old):])
                    if not target.exists():
                        p.rename(target)

    def delete_setlist(self, data):
        """Setlist 'verwijderen': naar archief/setlists/<datum>/ (terug te halen; de versiegeschiedenis blijft)."""
        import datetime
        rel = str(data.get("path", "")).strip().strip("/")
        p = self._check_managed(rel)
        if not (rel.startswith("setlists/") and p.suffix == ".txt" and p.is_file()):
            raise ValueError("alleen setlists (setlists/*.txt) kunnen zo worden verwijderd")
        project = self.project()
        folder = project.archive_dir / "setlists" / datetime.date.today().isoformat()
        folder.mkdir(parents=True, exist_ok=True)
        dst = folder / p.name
        i = 2
        while dst.exists():
            dst = folder / f"{p.stem}-{i}{p.suffix}"
            i += 1
        with LOCK:
            p.rename(dst)
        return {"ok": True, "archived": self.rel(dst)}

    def songs(self):
        """Alle nummers met titel, artiest, map, tempo, maatsoort en duur (voor de setlist-bouwer).
        Per bestand gecachet op wijzigingstijd, dus snel."""
        from .build import load_and_arrange
        from .project import parse_duration, quick_meta
        from .rows import NotationError
        project = self.project()
        out = []
        cfg_key = repr(sorted(project.config.items()))
        for f in project.song_files():
            try:
                mt = f.stat().st_mtime
            except OSError:
                continue
            key = str(f)
            hit = self._song_cache.get(key)
            if not hit or hit[0] != (mt, cfg_key):
                info = {"title": f.stem, "artist": "", "bpm": "", "meter": "", "duration": None, "error": ""}
                try:
                    sc = load_and_arrange(project, f)
                    s = sc.song
                    info.update(title=s.get("title") or f.stem, artist=s.get("artist", ""), bpm=str(sc.tempo[0]),
                                meter=str(sc.meter).split(" ")[0],
                                duration=parse_duration(s["duration"]) if s.get("duration") else round(sc.seconds()))
                except NotationError as e:
                    q = quick_meta(f)
                    info.update(title=q.get("title", f.stem), artist=q.get("artist", ""), error=e.msg)
                except Exception as e:  # noqa: BLE001 - één kapot nummer mag de lijst niet breken
                    info.update(error=f"{type(e).__name__}: {e}")
                hit = ((mt, cfg_key), info)
                self._song_cache[key] = hit
            rel = self.rel(f)
            sid = project.song_id(f)
            out.append(dict(hit[1], path=rel, id=sid, folder=sid.split("/")[0] if "/" in sid else ""))
        return {"songs": out}

    def setlist_info(self, rel, content):
        """Een setlist regel voor regel, met wat er bij elke regel hoort (voor de setlist-bouwer)."""
        from . import setlist as sl
        project = self.project()
        meta, entries = sl.parse_setlist(content, pathlib.Path(rel).stem)
        errors = sl.resolve(project, entries, self.safe(rel))
        bad = {}
        for e in errors:
            m = re.match(r"regel (\d+):\s*(.*)", e)
            if m:
                bad[int(m.group(1))] = m.group(2)
        songs = {s["path"]: s for s in self.songs()["songs"]}
        items = []
        for e in entries:
            d = {"line": e.line, "kind": e.kind, "ref": e.ref, "display": e.display, "note": e.note,
                 "title": e.title or e.display or e.ref, "artist": e.artist, "duration": e.duration,
                 "bpm": "", "meter": "", "path": "", "error": bad.get(e.line, "")}
            if e.kind == "song" and e.path:
                try:
                    d["path"] = self.rel(e.path)
                except ValueError:
                    d["path"] = str(e.path)
                info = songs.get(d["path"]) or {}
                d.update(bpm=info.get("bpm", ""), meter=info.get("meter", ""),
                         error=d["error"] or info.get("error", ""))
                if d["duration"] is None:
                    d["duration"] = info.get("duration")
            elif e.kind == "song" and not d["error"]:
                d["error"] = "niet gevonden"
            items.append(d)
        return {"meta": meta, "entries": items}

    def git(self, action, data):
        from . import gitsync
        project = self.project()
        logs = []
        with LOCK:
            if action == "status":
                return gitsync.status(project, fetch=bool(data.get("fetch")))
            if action == "diff":
                return gitsync.diff(project, data["path"], data.get("base"))
            if action == "send":
                keys = None if data.get("all") else list(data.get("keys") or [])
                res = gitsync.send(project, keys, data.get("message", ""), log=logs.append)
            elif action == "remote":
                res = gitsync.set_remote(project, data.get("url", ""), log=logs.append)
            elif action == "pull":
                res = gitsync.pull(project, log=logs.append)
            elif action == "init":
                res = gitsync.init(project, log=logs.append)
            else:
                raise ValueError("onbekende actie")
        return dict(res, log="\n".join(logs))

    def health(self):
        from . import health
        return health.check(self.project(), self.server_info)

    def versions(self, action, data):
        from . import versions as V
        project = self.project()
        rel = data["path"]
        logs = []
        with LOCK:
            if action == "info":
                return V.info(project, rel)
            if action == "create":
                v = V.create(project, rel, data.get("note", ""), log=logs.append)
                return {"version": v, "log": "\n".join(logs)}
            if action == "restore":
                return dict(V.restore(project, rel, int(data["n"]), log=logs.append), log="\n".join(logs))
            if action == "restore_backup":
                return dict(V.restore_backup(project, rel, data["file"], log=logs.append), log="\n".join(logs))
            if action == "note":
                return V.set_note(project, rel, int(data["n"]), data.get("note", ""))
            if action == "diff":
                return V.compare(project, rel, data.get("a"), data.get("b", "werk"))
        raise ValueError("onbekende actie")

    def _move_outputs(self, project, oid, nid):
        import json as _json
        from . import versions as V
        V.move(project, oid, nid)
        oname = pathlib.PurePosixPath(oid).name
        for kind, ext in (("pdf", "pdf"), ("mscz", "mscz"), ("xml", "musicxml"), ("midi", "mid")):
            folder = project.out(kind, *pathlib.PurePosixPath(oid).parts[:-1])
            if not folder.exists():
                continue
            for f in list(folder.iterdir()):
                if f.is_file() and f.suffix == "." + ext and (f.name == f"{oname}.{ext}" or
                                                                (f.name.startswith(oname + "-") and kind == "midi")):
                    target = project.out(kind, nid + f.name[len(oname):])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    f.rename(target)
        for state_file, sub in ((project.out(".cache.json"), None), (project.out(".forscore.json"), "songs")):
            try:
                data = _json.loads(state_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            d = data.get(sub, {}) if sub else data
            if oid in d:
                d[nid] = d.pop(oid)
                state_file.write_text(_json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")

    def _rename_refs(self, project, oid, ostem, nid):
        """Setlistregels die naar het oude id/de oude naam verwijzen bijwerken."""
        if not project.setlists_dir.exists():
            return
        keys = {simplify(oid), simplify(ostem)}
        for f in project.setlists_dir.glob("*.txt"):
            lines = f.read_text(encoding="utf-8").split("\n")
            changed = False
            for i, line in enumerate(lines):
                body, sep, comment = line.partition("#")
                ref_part = re.split(r"[|=\[]", body, maxsplit=1)[0]
                ref = ref_part.strip()
                if ref and ":" not in ref and not ref.startswith("[") and simplify(ref) in keys:
                    lead = ref_part[:len(ref_part) - len(ref_part.lstrip())]
                    trail = ref_part[len(ref_part.rstrip()):]
                    lines[i] = lead + nid + trail + body[len(ref_part):] + sep + comment
                    changed = True
            if changed:
                f.write_text("\n".join(lines), encoding="utf-8")

    def _cleanup_empty(self, project):
        for kind in ("pdf", "mscz", "xml", "midi"):
            base = project.out(kind)
            if base.exists():
                for d in sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda x: -len(x.parts)):
                    if not any(d.iterdir()):
                        d.rmdir()

    def new_setlist(self, data):
        name = re.sub(r"[^\w\-]+", "-", (data.get("name") or "").strip()).strip("-")
        if not name:
            raise ValueError("geef een naam op")
        res = self.run_cli(["setlist", "nieuw", name] + list(data.get("songs") or []))
        res["path"] = f"setlists/{name}.txt"
        return res

    def build(self, data):
        rel = data["path"]
        if data.get("content") is not None:
            self.write(rel, data["content"])
        kind = self.kind(rel)
        if kind == "setlist":
            name = pathlib.Path(rel).stem
            res = self.run_cli(["setlist", "maak", name] + (["-a"] if data.get("all") else []))
            pdf = f"uitvoer/setlists/{name} - compleet.pdf"
            if not (self.root / pdf).exists():
                pdf = None
            res["pdf"] = pdf
            return res
        if kind == "song":
            res = self.run_cli(["maak", "-a", rel])
            pf = self.project().out("pdf", f"{self.project().song_id(rel)}.pdf")
            res["pdf"] = self.rel(pf) if pf.exists() else None
            return res
        if kind == "library":
            res = self.run_cli(["bibliotheek", "--pdf"])
            res["pdf"] = "uitvoer/bibliotheek.pdf"
            return res
        raise ValueError("dit bestand kan niet gemaakt worden")

    def midi(self, data):
        argv = ["midi", data["path"], "--tempo", str(int(data.get("tempo") or 100))]
        if data.get("click"):
            argv.append("--klik")
        if data.get("countin"):
            argv += ["--aftellen", str(int(data["countin"]))]
        res = self.run_cli(argv)
        t = int(data.get("tempo") or 100)
        res["midi"] = self.rel(self.project().out_file("midi", data["path"], "mid", "" if t == 100 else f"-{t}pct"))
        return res


# ---------------------------------------------------------------------- http
class Handler(BaseHTTPRequestHandler):
    studio = None

    def log_message(self, fmt, *args):  # stil
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    server_mode = False
    allowed_nets = []          # extra netwerken (instelling 'toegang:'), naast privé-adressen en 100.64.0.0/10

    def _local_only(self):
        """Wie mag erbij? Normaal: alleen deze computer (ook de Host-kop moet lokaal zijn, tegen DNS-trucs).
        Servermodus: elk privé-adres (thuisnetwerk, VPN, proxy zoals Nginx Proxy Manager), nooit internet."""
        try:
            ip = ipaddress.ip_address(self.client_address[0])
            if getattr(ip, "ipv4_mapped", None):
                ip = ip.ipv4_mapped
        except ValueError:
            return False
        if self.server_mode:
            return ip.is_private or ip.is_loopback or ip.is_link_local or any(ip in n for n in self.allowed_nets)
        host = (self.headers.get("Host") or "").split(":")[0]
        return ip.is_loopback and host in ("127.0.0.1", "localhost", "[::1]", "::1")

    def do_GET(self):
        if not self._local_only():
            return self.send(403, {"error": "alleen lokaal"})
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        s = self.studio
        try:
            if u.path in ("/", "/index.html"):
                return self.send(200, (HERE / "studio.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
            if u.path in ("/sync", "/status"):            # oude losse pagina's: nu iconen in de Studio
                return self.send(200, (HERE / "studio.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
            if u.path == "/api/health":
                return self.send(200, s.health())
            if u.path == "/api/git/status":
                return self.send(200, s.git("status", {"fetch": q.get("fetch")}))
            if u.path == "/api/tree":
                return self.send(200, s.tree())
            if u.path == "/api/file":
                return self.send(200, s.read(q["path"]))
            if u.path == "/api/library":
                return self.send(200, s.library())
            if u.path == "/api/kit":
                return self.send(200, s.kit())
            if u.path == "/api/help":
                return self.send(200, s.help())
            if u.path == "/api/forscore/catalog":
                return self.send(200, s.fs_catalog())
            if u.path == "/api/search":
                return self.send(200, s.search(q.get("q", ""), q.get("case") == "1"))
            if u.path == "/api/songs":
                return self.send(200, s.songs())
            if u.path in ("/studio.css", "/studio.js", "/views.js"):
                ctype = "text/css" if u.path.endswith(".css") else "text/javascript"
                return self.send(200, (HERE / u.path[1:]).read_text(encoding="utf-8"), ctype + "; charset=utf-8")
            if u.path == "/api/props":
                return self.send(200, s.props())
            if u.path == "/api/status":
                return self.send(200, s.status())
            if u.path.startswith(("/uitvoer/", "/archief/", "/versies/")):
                p = s.safe(urllib.parse.unquote(u.path.lstrip("/")))
                if not p.is_file():
                    return self.send(404, {"error": "niet gevonden"})
                ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                extra = {"Content-Disposition": f'attachment; filename="{p.name}"'} if p.suffix == ".mid" else {}
                return self.send(200, p.read_bytes(), ctype, extra)
            return self.send(404, {"error": "onbekend"})
        except Exception as e:  # noqa: BLE001
            return self.send(400, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        if not self._local_only():
            return self.send(403, {"error": "alleen lokaal"})
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return self.send(415, {"error": "verwacht JSON"})
        n = int(self.headers.get("Content-Length") or 0)
        data = json.loads(self.rfile.read(n) or b"{}")
        s = self.studio
        routes = {
            "/api/save": lambda: s.write(data["path"], data["content"]),
            "/api/check": lambda: s.check(data["path"], data.get("content", "")),
            "/api/build": lambda: s.build(data),
            "/api/build-all": lambda: s.run_cli(["maak"] + (["-a"] if data.get("all") else [])),
            "/api/midi": lambda: s.midi(data),
            "/api/new-song": lambda: s.new_song(data),
            "/api/new-setlist": lambda: s.new_setlist(data),
            "/api/archive": lambda: s.run_cli(["archiveer", data["path"]]),
            "/api/move": lambda: s.move(data),
            "/api/delete-setlist": lambda: s.delete_setlist(data),
            "/api/mkdir": lambda: s.mkdir(data),
            "/api/deldir": lambda: s.rmdir(data),
            "/api/build-folder": lambda: s.run_cli(["maak", data["path"]] + (["-a"] if data.get("all") else [])),
            "/api/forscore": lambda: s.run_cli(["forscore"] + list(data.get("paths") or ([data["path"]] if data.get("path") else []))
                                                 + sum((["--setlist", n] for n in data.get("setlists") or []), [])),
            "/api/setlist-info": lambda: s.setlist_info(data["path"], data.get("content", "")),
            "/api/git/send": lambda: s.git("send", data),
            "/api/git/diff": lambda: s.git("diff", data),
            "/api/git/remote": lambda: s.git("remote", data),
            "/api/git/pull": lambda: s.git("pull", data),
            "/api/git/init": lambda: s.git("init", data),
            "/api/versions": lambda: s.versions("info", data),
            "/api/versions/create": lambda: s.versions("create", data),
            "/api/versions/restore": lambda: s.versions("restore", data),
            "/api/versions/restore-backup": lambda: s.versions("restore_backup", data),
            "/api/versions/note": lambda: s.versions("note", data),
            "/api/versions/diff": lambda: s.versions("diff", data),
            "/api/forscore/catalog": lambda: s.fs_catalog(),
            "/api/forscore/selftest": lambda: s.run_cli(["forscore", "--zelftest"]),
            "/api/forscore/labels": lambda: s.run_cli(["forscore", "--labels-ophalen"] + (["--toepassen"] if data.get("apply") else [])),
            "/api/set-header": lambda: s.set_header(data),
        }
        fn = routes.get(urllib.parse.urlparse(self.path).path)
        if not fn:
            return self.send(404, {"error": "onbekend"})
        try:
            return self.send(200, fn())
        except Exception as e:  # noqa: BLE001
            return self.send(400, {"error": f"{e}"})


def serve(root, port=8765, open_browser=True, server=False, host=None):
    Handler.studio = Studio(root)
    Handler.server_mode = server
    nets = [ipaddress.ip_network("100.64.0.0/10")]          # VPN's met 'carrier-grade' adressen (bv. Tailscale)
    for x in str(Handler.studio.project().config.get("access", "") or "").replace(";", ",").split(","):
        if x.strip():
            try:
                nets.append(ipaddress.ip_network(x.strip(), strict=False))
            except ValueError:
                print(f"! instelling 'toegang': '{x.strip()}' is geen netwerk (bv. 10.20.0.0/16)")
    Handler.allowed_nets = nets
    host = host or ("0.0.0.0" if server else "127.0.0.1")
    for p in range(port, port + (1 if server else 20)):
        try:
            httpd = ThreadingHTTPServer((host, p), Handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"poort {port} is bezet (draait de Studio al?)" if server else "geen vrije poort gevonden")
    Handler.studio.server_info = {"host": host, "port": p, "server": server}
    url = f"http://127.0.0.1:{p}/"
    print(f"Drumsheetz Studio draait op {url}  (Ctrl+C om te stoppen)")
    print(f"Muziekmap: {Handler.studio.root}")
    if server:
        print(f"Servermodus: bereikbaar op poort {p} vanaf privé-adressen (thuisnetwerk, VPN, proxy).")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nGestopt.")
    finally:
        httpd.server_close()
