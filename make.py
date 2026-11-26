"""Gebruik: python3 make.py [naam ...]   (zonder namen: alle nummers in songs/)
Stappen: songs/<naam>.py -> xml/<naam>.musicxml -> MuseScore (.mscx) -> maatnummers
doortellen na %-maten -> pdf/<naam>.pdf en mscz/<naam>.mscz"""
import importlib.util, pathlib, re, subprocess, sys, tempfile
import drumxml

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT / "songs"))
MSCORE = "/Applications/MuseScore 4.app/Contents/MacOS/mscore"


def ms(src, dst):
    r = subprocess.run([MSCORE, "-o", str(dst), str(src)], capture_output=True, text=True)
    if not pathlib.Path(dst).exists():
        raise RuntimeError(r.stderr[-600:])


def patch_offsets(mscx_path, offsets):
    """Zet <noOffset> ('Tel op bij maatnummer') op de maat na elke herhaalmaat."""
    text = mscx_path.read_text(encoding="utf-8")
    idx = [-1]

    def repl(m):
        idx[0] += 1
        off = offsets.get(idx[0])
        return m.group(0) + (f"\n          <noOffset>{off}</noOffset>" if off else "")

    # alleen de eerste notenbalk bevat de maten die we tellen
    start = text.index('<Staff id="1">', text.index("</Part>"))
    end = text.index("</Staff>", start)
    staff = re.sub(r"<Measure(?: [^>]*)?>", repl, text[start:end])
    text = text[:start] + staff + text[end:]
    # meer ruimte tussen de regels, zodat dynamiek duidelijk bij de bovenste balk hoort
    if "<Style>" in text:
        text = text.replace("<Style>", "<Style>\n      <minSystemDistance>12</minSystemDistance>", 1)
    else:
        text = text.replace("<Score>", "<Score>\n    <Style>\n      <minSystemDistance>12</minSystemDistance>\n      </Style>", 1)
    mscx_path.write_text(text, encoding="utf-8")


names = sys.argv[1:] or sorted(p.stem for p in (ROOT / "songs").glob("*.py") if p.stem != "common")
for d in ("xml", "pdf", "mscz"):
    (ROOT / d).mkdir(exist_ok=True)
for name in names:
    spec = importlib.util.spec_from_file_location(name, ROOT / "songs" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    xml = drumxml.score(mod.SONG, mod.GROOVES, mod.FILLS)
    offsets = dict(drumxml.OFFSETS)
    x = ROOT / "xml" / f"{name}.musicxml"
    x.write_text(xml, encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        mscx = pathlib.Path(tmp) / f"{name}.mscx"
        ms(x, mscx)
        patch_offsets(mscx, offsets)
        ms(mscx, ROOT / "pdf" / f"{name}.pdf")
        ms(mscx, ROOT / "mscz" / f"{name}.mscz")
    total = sum(s.get("bars", 0) or sum(p["bars"] for p in s.get("seq", [])) for s in mod.SONG["sections"])
    print(f"{name}: ok, {total} maten")
