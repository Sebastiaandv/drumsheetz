"""Het oude (geavanceerde) Python-formaat: SONG / GROOVES / FILLS in een .py-bestand.

Werkt nog steeds volledig, en kan alle nieuwe opties gebruiken (zelfde sleutels als hieronder
in to_drum_text). Ook omzetten naar het nieuwe .drum-formaat gebeurt hier."""
import importlib.util
import sys
import types

from .library import LEGACY_FILLS_44, builtin_book
from .patterns import Pattern, PatternBook
from .rows import NotationError


def _common_shim():
    """Vervanger voor de oude 'common.py' (FILLS_44, HIT, STOP, SUB)."""
    mod = types.ModuleType("common")
    lib = builtin_book()
    mod.FILLS_44 = {n: dict(lib.get(n).rows) for n in LEGACY_FILLS_44}
    mod.HIT = {"CR": "x---------------", "BD": "x---------------"}
    mod.STOP = dict(mod.HIT)
    mod.SUB = "Drum lead sheet"
    return mod


def load_py(path, library=None):
    path = str(path)
    import os
    folder = os.path.dirname(os.path.abspath(path))
    added = False
    if folder not in sys.path:
        sys.path.insert(0, folder)
        added = True
    had_common = "common" in sys.modules
    if not os.path.exists(os.path.join(folder, "common.py")):
        sys.modules["common"] = _common_shim()
    try:
        spec = importlib.util.spec_from_file_location("_song_" + os.path.basename(path)[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001 - toon elke fout in het nummerbestand
        raise NotationError(f"Python-fout: {type(e).__name__}: {e}", None, path)
    finally:
        if added:
            sys.path.remove(folder)
        if not had_common:
            sys.modules.pop("common", None)
    if not hasattr(mod, "SONG"):
        raise NotationError("bestand heeft geen SONG = {...}", None, path)
    return from_dicts(mod.SONG, getattr(mod, "GROOVES", {}), getattr(mod, "FILLS", {}), path, library)


def from_dicts(song, grooves, fills, path=None, library=None):
    import copy
    song = copy.deepcopy(song)
    book = PatternBook(parent=library)
    for name, rows in (grooves or {}).items():
        book.add(_pat(name, rows, path, "groove"))
    rename = {}
    for name, rows in (fills or {}).items():
        if name in (grooves or {}) and grooves[name] != rows:
            rename[name] = "fill_" + name
        book.add(_pat(rename.get(name, name), rows, path, "fill"))
    if rename:
        for sec in song.get("sections", []):
            for ph in [sec] + list(sec.get("seq", [])):
                f = ph.get("fill")
                if isinstance(f, str) and f in rename:
                    ph["fill"] = rename[f]
                elif isinstance(f, list):
                    ph["fill"] = [rename.get(x, x) for x in f]
    return song, book, []


def _pat(name, rows, path, kind):
    rows = dict(rows)
    p = Pattern(name, file=path, kind=kind)
    for k in ("_bars", "bars", "maten"):
        if k in rows:
            p.bars = int(rows.pop(k))
    for k in ("_meter", "meter", "maat"):
        if k in rows:
            v = rows.pop(k)
            p.meter = f"{v[0]}/{v[1]}" if isinstance(v, (tuple, list)) else str(v)
    for k in ("_base", "base", "basis"):
        if k in rows:
            p.base = rows.pop(k)
    for k in ("_doc", "info"):
        if k in rows:
            p.doc = rows.pop(k)
    p.rows = rows
    return p


# ---------------------------------------------------------------------------
# omzetten naar .drum

KEYS_OUT = [("title", "titel"), ("artist", "artiest"), ("subtitle", "ondertitel"), ("bpm", "tempo"),
            ("meter", "maat"), ("feel", "stijl"), ("notes", "notitie"), ("by", "door"),
            ("key", "toonsoort"), ("duration", "duur"), ("status", "status"), ("tags", "tags"),
            ("source", "bron"), ("audio", "audio"), ("pdf", "pdf"), ("countin", "aftellen"),
            ("layout", "layout"), ("voices", "stemmen"), ("text_size", "tekstgrootte"),
            ("feel_size", "stijlgrootte"), ("count_pos", "herhaalteller"), ("accent_pos", "accenten"), ("wedge_pos", "vorken"), ("dyn_pos", "dynamiek"), ("bars_per_line", "maten-per-regel"), ("swing", "swing"),
            ("composer", "componist"), ("year", "jaar"), ("album", "album")]
MARK_OUT = {"segno": "segno", "coda": "coda", "fine": "fine", "tocoda": "naar-coda", "ds": "ds",
            "dsalcoda": "ds-al-coda", "dsalfine": "ds-al-fine", "dc": "dc", "dcalcoda": "dc-al-coda",
            "dcalfine": "dc-al-fine"}
TT_OUT = {"rit.": "rit", "rall.": "rall", "accel.": "accel", "a tempo": "a-tempo", "Tempo I": "tempo-primo"}


def _opts(ph, section=False):
    o = []
    cr = ph.get("crash")
    if cr:
        o.append("crash" if cr is True or cr == "CR" else f"crash={cr}")
    f = ph.get("fill")
    if f:
        o.append("fill " + (",".join(f) if isinstance(f, (list, tuple)) else f))
    if ph.get("dyn"):
        o.append(ph["dyn"])
    if ph.get("wedge") and ph.get("dyn_end"):
        o.append(f"{'cresc' if ph['wedge'].startswith('cresc') else 'dim'} -{ph['dyn_end']}")
    elif ph.get("wedge"):
        o.append("cresc" if ph["wedge"].startswith("cresc") else "dim")
    if ph.get("tempo"):
        o.append(f"tempo={ph['tempo']}")
    if ph.get("tempo_text"):
        o.append(TT_OUT.get(ph["tempo_text"], ph["tempo_text"]))
    if ph.get("meter"):
        v = ph["meter"]
        o.append("maat=" + (f"{v[0]}/{v[1]}" if isinstance(v, (tuple, list)) else str(v)).replace(" ", ""))
    if ph.get("written"):
        o.append("uitgeschreven")
    if ph.get("repeat"):
        o.append(f"herhaal {ph['repeat']}")
    if ph.get("volta"):
        o.append("volta " + ",".join(map(str, ph["volta"])))
    for mk in ph.get("marks", []):
        o.append(MARK_OUT.get(mk, mk))
    if ph.get("fermata"):
        o.append("fermata")
    if ph.get("newpage"):
        o.append("nieuwepagina")
    if ph.get("newline") is True and not section:
        o.append("nieuweregel")
    if ph.get("newline") is False and section:
        o.append("doorlopen")
    if ph.get("end") and section:
        o.append("einde")
    if ph.get("text_size"):
        o.append(f"grootte={ph['text_size']}")
    if ph.get("text"):
        o.append('"' + ph["text"].replace('"', "'") + '"')
    return o


def _groove_name(g):
    return "tacet" if g is None else str(g)


def to_drum_text(song, book, header_comment=None):
    out = []
    if header_comment:
        out += ["# " + line for line in header_comment.splitlines()] + [""]
    for k, nk in KEYS_OUT:
        if k in song and song[k] not in (None, ""):
            v = song[k]
            if k == "meter" and isinstance(v, (tuple, list)):
                v = f"{v[0]}/{v[1]}"
            out.append(f"{nk}: {v}")
    if song.get("compress") is False:
        out.append("herhaaltekens: nee")
    out.append("")
    for code, ins in book.kit.items():
        out.append(f'instrument {code}: {ins.step}{ins.octave} {ins.head} {ins.midi} "{ins.name}"'
                   + (" voet" if ins.voice == 2 else ""))
    used = set()
    for sec in song.get("sections", []):
        for ph in [sec] + list(sec.get("seq", [])):
            if ph.get("groove") is not None:
                used.add(ph["groove"])
            f = ph.get("fill")
            if f:
                used.update([f] if isinstance(f, str) else f)
    lib = book.parent
    for name, pat in book.items.items():
        if name.startswith("~"):
            continue
        if lib is not None and lib.get(name) is not None and lib.get(name).rows == pat.rows \
                and not pat.base and not pat.meter and not pat.bars:
            continue   # staat al in de bibliotheek
        kind = "fill" if pat.kind == "fill" else "groove"
        head = f"{kind} {name}" + (f" = {pat.base}" if pat.base else "") + ":"
        out.append(head)
        if pat.doc:
            out.append(f"  info: {pat.doc}")
        if pat.meter:
            out.append(f"  maat: {pat.meter}")
        if pat.bars:
            out.append(f"  maten: {pat.bars}")
        w = max([len(k) for k in pat.rows] + [2])
        for k, v in pat.rows.items():
            if isinstance(v, (list, tuple)):
                v = " || ".join(v)
            out.append(f"  {k + ':':<{w + 1}} {v if str(v).strip() else '-'}")
        out.append("")
    for sec in song.get("sections", []):
        label = sec.get("label", "")
        if sec.get("seq"):
            sopts = {k: v for k, v in sec.items() if k in ("text", "text_size", "repeat", "marks", "newpage", "newline",
                                                           "end", "tempo", "meter", "written")}
            line = f"[{label}]"
            so = _opts(sopts, section=True)
            if so:
                line += " " + " ".join(so)
            out.append(line)
            for ph in sec["seq"]:
                out.append(f"  {ph.get('bars', 1)} {_groove_name(ph.get('groove'))}"
                           + ("" if not _opts(ph) else " " + " ".join(_opts(ph))))
        else:
            line = f"[{label}] {sec.get('bars', 1)} {_groove_name(sec.get('groove'))}"
            so = _opts(sec, section=True)
            if so:
                line += " " + " ".join(so)
            out.append(line)
    return "\n".join(out).rstrip() + "\n"
