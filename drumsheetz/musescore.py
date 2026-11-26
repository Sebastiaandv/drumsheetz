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


# 'N×' midden in de balk, links van het %-teken, met een wit vlakje achter de tekst zodat de
# notenbalklijnen er niet doorheen lopen (offset in spatiums vanaf de bovenste lijn).
COUNT_STYLE = ('<autoplace>0</autoplace><offset x="0.3" y="2.55"/><frameType>1</frameType>'
               '<frameWidth>0</frameWidth><framePadding>0.15</framePadding>'
               '<frameFgColor r="255" g="255" b="255" a="0"/><frameBgColor r="255" g="255" b="255" a="255"/>')


# MuseScore 4 zet extra regels in een StaffText (bv. <eid>, <linkedMain/>, eigen stijl); die mogen er
# tussen staan. De tekst zelf kan cursief zijn of niet, en × kan als entiteit geschreven zijn.
COUNT_RE = re.compile(r"(<StaffText(?: [^>]*)?>)((?:(?!</StaffText>).)*?)"
                      r"(<text>(?:<[^>]+>)*\s*\d+\s*(?:×|&#215;|&#xd7;|&times;|x)\s*(?:<[^>]+>)*</text>)", re.S | re.I)
_REMOVE = re.compile(r"\s*<(autoplace|offset|frameType|frameWidth|framePadding|frameFgColor|frameBgColor|placement)"
                     r"\b[^>]*?(?:/>|>[^<]*</\1>)")


def _count_style(m):
    middle = _REMOVE.sub("", m.group(2))
    return m.group(1) + middle + COUNT_STYLE + m.group(3)


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
        if idx[0] in counts:
            body, n = COUNT_RE.subn(_count_style, body, count=1)
            placed[0] += n
        return body

    try:
        start = text.index('<Staff id="1">', text.index("</Part>"))
        end = text.index("</Staff>", start)
        staff = re.sub(r"<Measure(?: [^>]*)?>.*?</Measure>", repl, text[start:end], flags=re.S)
        text = text[:start] + staff + text[end:]
    except ValueError:
        pass
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
        for it in items:
            placed, wanted = patch_mscx(it["mscx"], it["offsets"], cfg.get("minSystemDistance", "12"))
            if placed < wanted:
                log(f"  ! {it.get('id', '')}: {wanted - placed} van {wanted} herhaaltellers niet in de balk gezet "
                    "(stuur uitvoer/debug/*.mscx mee als je dit meldt)")
                dbg = pathlib.Path(it["pdf"]).parent.parent / "debug"
                dbg.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(it["mscx"], dbg / f"{it.get('id', 'nummer')}.mscx")
            outs = [it["pdf"]] + ([it["mscz"]] if it.get("mscz") else [])
            for o in outs:
                pathlib.Path(o).parent.mkdir(parents=True, exist_ok=True)
                if pathlib.Path(o).exists():
                    pathlib.Path(o).unlink()
            jobs2.append((it["mscx"], outs))
        run_job(ms, jobs2)


def version(ms):
    try:
        r = subprocess.run([ms, "--version"], capture_output=True, text=True, env=_env(), timeout=60)
        return (r.stdout or r.stderr).strip().splitlines()[-1]
    except Exception:  # noqa: BLE001
        return "?"
