"""MuseScore vinden en aansturen (Mac, Windows en Linux).

MusicXML -> .mscx -> maatnummers laten doortellen na %-maten -> .pdf en .mscz"""
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import tempfile

from .countplace import style_count

CANDIDATES = {
    "Darwin": [
        "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
        "/Applications/MuseScore Studio 4.app/Contents/MacOS/mscore",
        "/Applications/MuseScore 3.app/Contents/MacOS/mscore",
        "~/Applications/MuseScore 4.app/Contents/MacOS/mscore",
    ],
    "Windows": [
        r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
        r"C:\Program Files\MuseScore Studio 4\bin\MuseScore4.exe",
        r"C:\Program Files\MuseScore 3\bin\MuseScore3.exe",
        r"C:\Program Files (x86)\MuseScore 3\bin\MuseScore3.exe",
    ],
    "Linux": [],
}
NAMES = ["mscore4portable", "musescore4", "mscore4", "musescore", "mscore", "musescore3", "mscore3",
         "MuseScore4", "MuseScore-Studio", "MuseScore4.exe", "MuseScore3.exe"]


class MuseScoreError(Exception):
    pass


def find_musescore(configured=""):
    for c in (configured, os.environ.get("MUSESCORE", "")):
        if c:
            p = pathlib.Path(os.path.expanduser(c))
            if p.exists():
                return str(p)
            w = shutil.which(c)
            if w:
                return w
    for c in CANDIDATES.get(platform.system(), []):
        p = pathlib.Path(os.path.expanduser(c))
        if p.exists():
            return str(p)
    for n in NAMES:
        w = shutil.which(n)
        if w:
            return w
    return None


def _env():
    env = dict(os.environ)
    if platform.system() == "Linux" and not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return env


def run(ms, src, dst, timeout=300):
    r = subprocess.run([ms, "-o", str(dst), str(src)], capture_output=True, text=True, env=_env(),
                       timeout=timeout)
    if not pathlib.Path(dst).exists():
        raise MuseScoreError(f"MuseScore kon {src} niet omzetten naar {dst}:\n{(r.stderr or r.stdout)[-800:]}")


def run_job(ms, jobs, timeout=900):
    """Meerdere omzettingen in één keer (veel sneller: MuseScore start maar één keer).
    jobs: lijst van (bron, [doelen]). Valt terug op losse aanroepen als het niet lukt."""
    if not jobs:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump([{"in": str(s), "out": [str(d) for d in outs] if len(outs) > 1 else str(outs[0])}
                   for s, outs in jobs], f)
        jf = f.name
    try:
        subprocess.run([ms, "-j", jf], capture_output=True, text=True, env=_env(), timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        pass
    finally:
        os.unlink(jf)
    for s, outs in jobs:
        for d in outs:
            if not pathlib.Path(d).exists():
                run(ms, s, d)


# Accenten/marcato/open-dicht boven (of onder) de noten zetten, ongeacht de stokrichting.
ARTIC_RE = re.compile(r"<Articulation>(?:(?!</Articulation>).)*?</Articulation>", re.S)


def _artic(m, up):
    a = m.group(0)
    if up:
        a = re.sub(r"(<subtype>artic\w*?)Below(</subtype>)", r"\1Above\2", a)
    else:
        a = re.sub(r"(<subtype>artic\w*?)Above(</subtype>)", r"\1Below\2", a)
    a = re.sub(r"\s*<direction>[^<]*</direction>", "", a)
    return a.replace("</subtype>", f"</subtype>\n              <direction>{'up' if up else 'down'}</direction>", 1)


def add_subtitle(text, sub):
    """Ondertitel als eigen regel onder de titel (MuseScore neemt hem uit MusicXML niet over)."""
    from xml.sax.saxutils import escape
    m = re.search(r"(<Text>\s*(?:<eid>[^<]*</eid>\s*)?<style>([Tt])itle</style>.*?</Text>)", text, re.S)
    if not m or re.search(r"<style>[Ss]ubtitle</style>", text):
        return text
    style = "Subtitle" if m.group(2) == "T" else "subtitle"
    block = m.group(1)
    new = re.sub(r"<eid>[^<]*</eid>\s*", "", block)
    new = re.sub(r"<style>[Tt]itle</style>", f"<style>{style}</style>", new)
    new = re.sub(r"<text>.*?</text>", lambda _: f"<text>{escape(sub)}</text>", new, flags=re.S)
    return text.replace(block, block + "\n        " + new, 1)


def fit_title_frame(text, has_sub):
    """Titelvak hoog genoeg maken: in MuseScore 4 staan de blokken links (componist, jaar, ...) en rechts
    (artiest, vermelding) onderaan het vak, op dezelfde hoogte als de ondertitel. Daarom het vak verhogen,
    zodat die blokken ónder de ondertitel komen."""
    m = re.search(r"<VBox>.*?</VBox>", text, re.S)
    if not m:
        return text
    box = m.group(0)

    def lines_of(style):
        t = re.search(r"<style>" + style + r"</style>.*?<text>(.*?)</text>", box, re.S | re.I)
        if not t:
            return 0
        return len([x for x in re.split(r"\n|<br\s*/?>|&#10;", t.group(1)) if x.strip()])

    n = max(lines_of("lyricist"), lines_of("composer"))
    if not n:
        return text
    need = (9.5 + 3.0 if has_sub else 9.5) + 1.9 * n
    h = re.search(r"<height>([\d.]+)</height>", box)
    cur = float(h.group(1)) if h else 10.0
    if need <= cur:
        return text
    val = f"{need:.1f}"
    new = box.replace(h.group(0), f"<height>{val}</height>", 1) if h else box.replace("<VBox>", f"<VBox>\n        <height>{val}</height>", 1)
    return text.replace(box, new, 1)


def patch_mscx(path, offsets, min_system_distance="12"):
    """Zet <noOffset> ('tel op bij maatnummer') op de maat na elke herhaalmaat,
    en geef de regels wat meer ruimte zodat dynamiek bij de juiste balk hoort."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    counts = set(getattr(offsets, "counts", []) or [])
    idx = [-1]
    placed = [0]

    def repl(m):
        body = m.group(0)
        if "<multiMeasureRest>" in body:      # samenvattingsmaat van een rustgroep: telt niet mee
            return body
        idx[0] += 1
        off = offsets.get(idx[0])
        if off:
            body = body.replace(">", f">\n          <noOffset>{off}</noOffset>", 1)
        if idx[0] in counts:                   # voorlopige plek; place_counts zet hem precies goed
            body, n = style_count(body, 0.3, 2.55, "left")
            placed[0] += n
        return body

    try:
        start = text.index('<Staff id="1">', text.index("</Part>"))
        end = text.index("</Staff>", start)
        staff = re.sub(r"<Measure(?: [^>]*)?>.*?</Measure>", repl, text[start:end], flags=re.S)
        text = text[:start] + staff + text[end:]
    except ValueError:
        pass
    sub = getattr(offsets, "subtitle", "")
    if sub:
        text = add_subtitle(text, sub)
    text = fit_title_frame(text, bool(sub))
    acc = getattr(offsets, "accent", "")
    if acc in ("boven", "above", "onder", "below"):
        up = acc in ("boven", "above")
        text = ARTIC_RE.sub(lambda m: _artic(m, up), text)
    if min_system_distance:
        tag = f"<minSystemDistance>{min_system_distance}</minSystemDistance>"
        if "<minSystemDistance>" in text:
            text = re.sub(r"<minSystemDistance>[^<]*</minSystemDistance>", tag, text, count=1)
        elif "<Style>" in text:
            text = text.replace("<Style>", "<Style>\n      " + tag, 1)
        else:
            text = text.replace("<Score>", "<Score>\n    <Style>\n      " + tag + "\n      </Style>", 1)
    pathlib.Path(path).write_text(text, encoding="utf-8")
    return placed[0], len(counts)


def render(ms, items, cfg, log=print):
    """items: lijst dicts met xml, offsets, pdf, mscz (paden). Maakt alles in twee MuseScore-rondes."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        jobs1 = []
        for i, it in enumerate(items):
            it["mscx"] = tmp / f"s{i}.mscx"
            jobs1.append((it["xml"], [it["mscx"]]))
        run_job(ms, jobs1)
        jobs2 = []
        counted = []
        for it in items:
            placed, wanted = patch_mscx(it["mscx"], it["offsets"], cfg.get("minSystemDistance", "12"))
            if placed:
                counted.append(it)
            if placed < wanted:
                log(f"  ! {it.get('id', '')}: {wanted - placed} van {wanted} herhaaltellers niet in de balk gezet "
                    "(stuur uitvoer/debug/*.mscx mee als je dit meldt)")
                dbg = pathlib.Path(it["pdf"]).parent.parent / "debug"
                dbg.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(it["mscx"], dbg / f"{it.get('id', 'nummer').replace('/', '_')}.mscx")
            outs = [it["pdf"]] + ([it["mscz"]] if it.get("mscz") else [])
            for o in outs:
                pathlib.Path(o).parent.mkdir(parents=True, exist_ok=True)
                if pathlib.Path(o).exists():
                    pathlib.Path(o).unlink()
            jobs2.append((it["mscx"], outs))
        if counted:
            place_counts(ms, counted, tmp, log)
        run_job(ms, jobs2)


def place_counts(ms, items, tmp, log=print):
    """De 'N×'-tellers precies bij de %-tekens zetten, met de maatposities die MuseScore zelf uitrekent
    (.mpos/.spos). Zie countplace.py. Past een teller er niet naast: die maat iets breder en opnieuw meten;
    past hij dan nog niet, dan kaarsrecht boven het %-teken."""
    from . import countplace as CP
    pending = list(items)
    for rnd in (1, 2):
        jobs = []
        for i, it in enumerate(pending):
            it["_mpos"], it["_spos"] = tmp / f"pos{rnd}-{i}.mpos", tmp / f"pos{rnd}-{i}.spos"
            jobs.append((it["mscx"], [it["_mpos"], it["_spos"]]))
        try:
            run_job(ms, jobs)
        except MuseScoreError:
            pass
        again = []
        for it in pending:
            mp, sp = pathlib.Path(it["_mpos"]), pathlib.Path(it["_spos"])
            for f in (mp, sp):
                if not f.exists():
                    try:
                        run(ms, it["mscx"], f)
                    except MuseScoreError:
                        pass
            text = pathlib.Path(it["mscx"]).read_text(encoding="utf-8")
            offs = it["offsets"]
            info = getattr(offs, "count_info", {}) or {}
            mode = getattr(offs, "count_mode", "rechts")
            pl = CP.plan(text, mp.read_text(encoding="utf-8") if mp.exists() else "",
                         sp.read_text(encoding="utf-8") if sp.exists() else "", info, mode) if info else None
            if not pl:
                log(f"  ! {it.get('id', '')}: MuseScore gaf geen maatposities; de herhaaltellers staan links in de maat.")
                continue
            needs = {i: p for i, p in pl.items() if p["need"] > 0}
            if needs and rnd == 1:
                stretches = {i: min(2.2, (p["width"] + p["need"] + 0.4) / max(p["width"], 1.0)) for i, p in needs.items()}
                text, _ = CP.apply(CP.add_stretch(text, stretches), pl)
                pathlib.Path(it["mscx"]).write_text(text, encoding="utf-8")
                again.append(it)
                continue
            final = {i: (CP.above(p) if p["need"] > 0 else p) for i, p in pl.items()}
            text, n = CP.apply(text, final)
            pathlib.Path(it["mscx"]).write_text(text, encoding="utf-8")
            if it.get("pdf"):                         # klein meetverslag, voor als het ooit toch niet klopt
                dbg = pathlib.Path(it["pdf"]).parent.parent / "debug" / "tellers"
                dbg.mkdir(parents=True, exist_ok=True)
                (dbg / (it.get("id", "nummer").replace("/", "_") + ".json")).write_text(
                    CP.debug_report(final, mode), encoding="utf-8")
            if n < len(info) and it.get("pdf"):
                log(f"  ! {it.get('id', '')}: {len(info) - n} van {len(info)} herhaaltellers niet geplaatst "
                    "(stuur uitvoer/debug/ mee als je dit meldt)")
                dbg = pathlib.Path(it["pdf"]).parent.parent / "debug"
                dbg.mkdir(parents=True, exist_ok=True)
                name = it.get("id", "nummer").replace("/", "_")
                (dbg / f"{name}-tellers.json").write_text(CP.debug_report(pl, mode), encoding="utf-8")
                for f in (mp, sp, pathlib.Path(it["mscx"])):
                    if f.exists():
                        shutil.copyfile(f, dbg / f"{name}{f.suffix}")
        pending = again
        if not pending:
            break


def version(ms):
    try:
        r = subprocess.run([ms, "--version"], capture_output=True, text=True, env=_env(), timeout=60)
        return (r.stdout or r.stderr).strip().splitlines()[-1]
    except Exception:  # noqa: BLE001
        return "?"
