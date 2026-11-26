"""Mappen, instellingen en het vinden/laden van nummers."""
import difflib
import os
import pathlib
import re
import unicodedata

from .library import builtin_book
from .rows import NotationError

SONG_DIR = "nummers"
OUT_DIR = "uitvoer"
SETLIST_DIR = "setlists"
ARCHIVE_DIR = "archief"
LIBRARY_FILE = "bibliotheek.drum"
CONFIG_FILE = "instellingen.txt"

DEFAULT_CONFIG = {
    "name": "",
    "subtitle": "",
    "credit": "",
    "musescore": "",
    "minSystemDistance": "12",
}
CONFIG_KEYS = {"naam": "name", "name": "name", "ondertitel": "subtitle", "subtitle": "subtitle",
               "credit": "credit", "vermelding": "credit", "musescore": "musescore", "mscore": "musescore",
               "regelafstand": "minSystemDistance", "minsystemdistance": "minSystemDistance",
               "pdf-viewer": "viewer", "stemmen": "voices", "voices": "voices",
               "herhaalteller": "count_pos", "teller": "count_pos",
               "accenten": "accent_pos", "accent": "accent_pos",
               "vorken": "wedge_pos", "crescendo": "wedge_pos", "dynamiek": "dyn_pos",
               "forscore": "forscore", "forscore-formaat": "forscore_format",
               "tekstgrootte": "text_size", "stijlgrootte": "feel_size"}


class Project:
    def __init__(self, root):
        self.root = pathlib.Path(root).resolve()
        self.config = dict(DEFAULT_CONFIG)
        cfg = self.root / CONFIG_FILE
        if cfg.exists():
            for line in cfg.read_text(encoding="utf-8").splitlines():
                line = line.split("#", 1)[0].strip()
                m = re.match(r"^([\w\-]+)\s*:\s*(.*)$", line)
                if m:
                    key = CONFIG_KEYS.get(m.group(1).lower(), m.group(1))
                    self.config[key] = m.group(2).strip()
        self._library = None

    # mappen -------------------------------------------------------------
    @property
    def songs_dir(self):
        return self.root / SONG_DIR

    def out(self, *parts):
        p = self.root / OUT_DIR
        for x in parts:
            p = p / x
        return p

    @property
    def setlists_dir(self):
        return self.root / SETLIST_DIR

    @property
    def archive_dir(self):
        return self.root / ARCHIVE_DIR

    # bibliotheek --------------------------------------------------------
    def library(self):
        if self._library is None:
            lib = builtin_book()
            f = self.root / LIBRARY_FILE
            if f.exists():
                from .parser import Parser
                p = Parser(f.read_text(encoding="utf-8"), str(f.relative_to(self.root)), lib)
                _, book = p.parse_patterns_only()
                lib = book
            self._library = lib
        return self._library

    # nummers ------------------------------------------------------------
    def song_files(self, include_parked=False):
        """Alle nummers in nummers/ (ook in submappen). Mappen die met '_' beginnen zijn 'geparkeerd':
        die worden niet meegenomen bij 'alles maken', lijsten en forScore-overzichten."""
        if not self.songs_dir.exists():
            return []
        out = []
        for p in sorted(self.songs_dir.rglob("*"), key=lambda x: str(x).lower()):
            rel = p.relative_to(self.songs_dir).parts
            if any(part.startswith(".") for part in rel):
                continue
            if not include_parked and any(part.startswith("_") for part in rel[:-1]):
                continue
            if p.suffix == ".drum" or (p.suffix == ".py" and p.stem not in ("common", "__init__")):
                out.append(p)
        return out

    def song_id(self, path):
        """Uniek id van een nummer: pad binnen nummers/ zonder extensie (bv. 'Hatikwa/The River').
        Ook de uitvoer (PDF, MuseScore, MIDI) krijgt die mappenstructuur."""
        p = pathlib.Path(path)
        if not p.is_absolute():
            p = (self.root / p)
        try:
            rel = p.resolve().relative_to(self.songs_dir.resolve())
            return rel.with_suffix("").as_posix()
        except ValueError:
            return p.stem

    def out_file(self, kind, path, ext, suffix=""):
        """uitvoer/<kind>/<id><suffix>.<ext>, met tussenliggende mappen aangemaakt."""
        f = self.out(kind, f"{self.song_id(path)}{suffix}.{ext}")
        f.parent.mkdir(parents=True, exist_ok=True)
        return f

    def load(self, path):
        path = pathlib.Path(path)
        rel = os.path.relpath(path, self.root) if path.is_absolute() else str(path)
        if path.suffix == ".py":
            from .legacy import load_py
            song, book, warns = load_py(path, self.library())
        else:
            from .parser import parse_text
            song, book, warns = parse_text(path.read_text(encoding="utf-8"), rel, self.library())
        song["_file"] = rel
        song["_path"] = str(path)
        song["_id"] = self.song_id(path)
        return song, book, warns

    def find(self, ref, files=None):
        """Zoek een nummer: bestandsnaam, id, titel of een stuk daarvan."""
        files = files if files is not None else self.song_files(include_parked=True)
        p = pathlib.Path(ref)
        if p.suffix in (".drum", ".py") and (self.root / p).exists():
            return self.root / p
        if p.suffix in (".drum", ".py") and p.exists():
            return p.resolve()
        key = simplify(ref)
        if (self.root / ref).is_file() and (self.root / ref).suffix in (".drum", ".py"):
            return self.root / ref
        ids = {simplify(f.stem): f for f in files}
        ids.update({simplify(self.song_id(f)): f for f in files})
        if key in ids:
            return ids[key]
        titles = {}
        for f in files:
            t = quick_meta(f)
            titles[simplify(t.get("title", ""))] = f
            titles[simplify(t.get("artist", "") + " " + t.get("title", ""))] = f
        if key in titles:
            return titles[key]
        hits = [f for k, f in list(ids.items()) + list(titles.items()) if key and key in k]
        if len(set(hits)) == 1:
            return hits[0]
        if len(set(hits)) > 1:
            names = ", ".join(sorted({h.stem for h in hits}))
            raise NotationError(f"'{ref}' past op meerdere nummers: {names}")
        close = difflib.get_close_matches(key, list(ids) + list(titles), n=1, cutoff=0.6)
        if close:
            return ids.get(close[0]) or titles[close[0]]
        raise NotationError(f"nummer '{ref}' niet gevonden in {SONG_DIR}/")


def simplify(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def quick_meta(path):
    """Titel/artiest snel uitlezen zonder het hele nummer te verwerken."""
    path = pathlib.Path(path)
    meta = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return meta
    if path.suffix == ".drum":
        for line in text.splitlines():
            m = re.match(r"^(titel|title|artiest|artist|band)\s*:\s*(.*)$", line.strip(), re.I)
            if m:
                k = "title" if m.group(1).lower() in ("titel", "title") else "artist"
                meta.setdefault(k, m.group(2).strip())
    else:
        for k in ("title", "artist"):
            m = re.search(rf"['\"]{k}['\"]\s*:\s*['\"]([^'\"]*)['\"]", text)
            if m:
                meta[k] = m.group(1)
    return meta


def safe_filename(s):
    s = re.sub(r'[\\/:*?"<>|]+', "-", str(s)).strip()
    return re.sub(r"\s+", " ", s)


def fmt_duration(sec):
    sec = int(round(sec))
    if sec >= 3600:
        return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"
    return f"{sec // 60}:{sec % 60:02d}"


def parse_duration(s):
    m = re.fullmatch(r"\s*(\d+):(\d{1,2})\s*", str(s))
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    try:
        return float(s) * 60
    except ValueError:
        return None
