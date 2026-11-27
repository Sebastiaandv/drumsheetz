"""Opdrachtregel: python3 drums.py <opdracht> ...   (python3 drums.py help voor een overzicht)"""
import argparse
import datetime
import pathlib
import shutil
import sys
import time

from .project import Project, fmt_duration, quick_meta, simplify
from .rows import NotationError

TEMPLATE = """# {title} - {artist}
# Gemaakt op {date}. Zie HANDLEIDING.md voor alle mogelijkheden.
# Bouwen:  python3 drums.py maak {sid}      Controleren:  python3 drums.py toon {sid}

titel: {title}
artiest: {artist}
tempo: {tempo}
maat: {meter}
stijl: {feel}

# --- patronen ----------------------------------------------------------
# Raster (één teken per slag) of tellen (1 2& 3e 4a). Ingebouwde patronen
# zoals rock, ballad, disco, funk, shuffle, sd4, tom34 mag je direct gebruiken.
{grooves}
# --- opbouw ------------------------------------------------------------
# [Naam]  aantal-maten  patroon  opties (crash, fill x, mf, cresc, "tekst", ...)
{sections}
"""

TEMPLATES = {
    "4/4": ("groove couplet:\n  HH: *8\n  SD: 2 4\n  BD: 1 3 3&\n\n"
            "groove refrein = couplet:\n  HH: -\n  RD: *8 *4:b\n\n",
            "[Intro]     4 couplet crash fill sd4\n"
            "[Couplet 1] 16 couplet mf fill pick8\n"
            "[Refrein]   8 refrein crash f fill tom34\n"
            "[Couplet 2] 16 couplet mf fill pick8\n"
            "[Refrein]   8 refrein crash f fill tom34\n"
            "[Brug]      8 halftime crash mp cresc fill sd34\n"
            "[Refrein]   8 refrein crash ff fill tomfull\n"
            "[Outro]\n  4 refrein crash\n  1 hit fermata\n"),
    "6/8": ("groove couplet:\n  HH: *8\n  SD: 4\n  BD: 1 6\n\n",
            "[Intro]     4 couplet crash fill trip68\n"
            "[Couplet]   16 couplet fill trip68\n"
            "[Refrein]   8 couplet crash fill tom68\n"
            "[Outro]     4 couplet crash\n  1 hit fermata\n"),
    "3/4": ("groove couplet:\n  HH: *8\n  SD: 2 3\n  BD: 1\n\n",
            "[Intro]     4 couplet crash\n[Couplet]   16 couplet\n[Refrein]   8 couplet crash\n"
            "[Outro]     1 hit fermata\n"),
}


def main(argv=None, root=None):
    root = pathlib.Path(root or pathlib.Path.cwd())
    project = Project(root)
    ap = argparse.ArgumentParser(
        prog="drums.py", description="Drumsheetz: drum sheets uitschrijven, bouwen en setlists maken. "
                                     "Zie HANDLEIDING.md.")
    sub = ap.add_subparsers(dest="cmd", metavar="opdracht")

    p = sub.add_parser("maak", aliases=["build", "bouw"], help="maak PDF's (alleen gewijzigde, of -a voor alles)")
    p.add_argument("nummers", nargs="*", help="nummers (id, titel of stuk daarvan); leeg = alle")
    p.add_argument("-a", "--alles", action="store_true", help="ook ongewijzigde nummers opnieuw maken")
    p.add_argument("--xml", action="store_true", help="alleen MusicXML maken (geen MuseScore nodig)")
    p.add_argument("--midi", action="store_true", help="ook een MIDI-oefenbestand maken")
    p.add_argument("--open", action="store_true", help="open de PDF na afloop")
    p.add_argument("--forscore", action="store_true", help="gewijzigde PDF's daarna naar forScore sturen")

    p = sub.add_parser("toon", aliases=["show", "info"], help="laat een nummer als tekst-drumtab zien")
    p.add_argument("nummer")

    p = sub.add_parser("lijst", aliases=["list", "ls"], help="overzicht van alle nummers")
    p.add_argument("--zoek", default="", help="filter op tekst")

    p = sub.add_parser("controleer", aliases=["check", "test"], help="controleer nummers op fouten")
    p.add_argument("nummers", nargs="*")

    p = sub.add_parser("nieuw", aliases=["new"], help="nieuw nummer vanuit een sjabloon")
    p.add_argument("titel")
    p.add_argument("artiest", nargs="?", default="")
    p.add_argument("--maat", default="4/4")
    p.add_argument("--tempo", default="100")
    p.add_argument("--stijl", default="")
    p.add_argument("--id", default="", help="bestandsnaam (standaard de titel)")
    p.add_argument("--map", default="", help="submap in nummers/, bv. 'Hatikwa'")

    p = sub.add_parser("midi", help="maak een MIDI-oefenbestand")
    p.add_argument("nummers", nargs="+")
    p.add_argument("--tempo", type=int, default=100, help="oefentempo in procenten (bv. 80)")
    p.add_argument("--klik", action="store_true", help="metronoomklik toevoegen")
    p.add_argument("--aftellen", type=int, default=0, help="aantal maten aftellen")

    p = sub.add_parser("bibliotheek", aliases=["library", "lib"], help="ingebouwde en eigen grooves/fills")
    p.add_argument("naam", nargs="?", help="laat één patroon zien")
    p.add_argument("--pdf", action="store_true", help="maak een PDF-catalogus van alle patronen")

    sub.add_parser("instrumenten", aliases=["kit", "instruments"], help="alle instrumentcodes en tekens")

    p = sub.add_parser("archiveer", aliases=["archive"], help="verplaats nummers (en hun uitvoer) naar archief/")
    p.add_argument("nummers", nargs="+")

    p = sub.add_parser("herstel", aliases=["restore"], help="haal een gearchiveerd nummer terug")
    p.add_argument("nummer")

    p = sub.add_parser("converteer", aliases=["convert"], help="oud .py-nummer omzetten naar .drum")
    p.add_argument("bestanden", nargs="+")
    p.add_argument("--naar", default="nummers", help="doelmap (standaard nummers/)")
    p.add_argument("--overschrijf", action="store_true")

    p = sub.add_parser("kijk", aliases=["watch"], help="maak automatisch opnieuw bij opslaan")
    p.add_argument("nummers", nargs="*")
    p.add_argument("--xml", action="store_true")

    p = sub.add_parser("forscore", aliases=["fs"],
                       help="forScore gelijk maken aan Drumsheetz (zonder nummers: alles, ook setlists)")
    p.add_argument("nummers", nargs="*", help="leeg = alle nummers")
    p.add_argument("--geen-open", action="store_true", help="alleen klaarzetten in uitvoer/forscore/")
    p.add_argument("--notitie", default="", help="notitie bij een nieuwe versie (wat is er veranderd?)")
    p.add_argument("--setlist", action="append", default=[], help="stuur ook deze setlist (.4ss)")
    p.add_argument("--labels-ophalen", action="store_true",
                   help="labels uit forScore (Mac) als mappen in de nummers zetten (laat eerst zien wat er verandert)")
    p.add_argument("--toepassen", action="store_true", help="met --labels-ophalen: de wijzigingen echt doorvoeren")
    p.add_argument("--onderzoek", action="store_true", help="laat zien wat er in de forScore-database gevonden wordt")
    p.add_argument("--zelftest", action="store_true",
                   help="probeer PDF, .4sc en setlist één keer uit in forScore en maak een rapport")

    p = sub.add_parser("muziek", help="je muziek in een eigen map/git-repo (maak, gebruik, gitlab, status)")
    p.add_argument("actie", nargs="?", default="status", choices=["status", "maak", "gebruik", "gitlab"],
                   help="maak <pad>: nieuwe muziekmap met een kopie van je nummers; gebruik <pad>: bestaande "
                        "muziekmap gebruiken; gitlab <url>: GitLab-adres instellen (leeg = weghalen)")
    p.add_argument("pad", nargs="?", default=None)

    p = sub.add_parser("versies", aliases=["versie", "versions"], help="versies van een nummer: bekijken, maken, terugzetten")
    p.add_argument("nummer", nargs="?", help="nummer (leeg = overzicht van alle nummers)")
    p.add_argument("--nieuw", nargs="?", const="", default=None, metavar="NOTITIE",
                   help="nieuwe versie maken (met optionele notitie)")
    p.add_argument("--terug", type=int, metavar="N", help="versie N terugzetten (wat er stond wordt bewaard)")
    p.add_argument("--verschil", nargs="+", metavar="N", help="verschil tussen versie N en nu (of tussen N en M)")
    p.add_argument("--controleer", action="store_true", help="controleer of alle versiebestanden nog kloppen")

    p = sub.add_parser("studio", aliases=["interface", "ui", "app"], help="open de Studio (editor in je browser)")
    p.add_argument("--poort", type=int, default=8765)
    p.add_argument("--geen-browser", action="store_true", help="browser niet automatisch openen")
    p.add_argument("--server", action="store_true",
                   help="servermodus: luistert op het netwerk (alleen privé-adressen), opent geen browser")
    p.add_argument("--host", default=None, help="adres om op te luisteren (standaard 127.0.0.1, met --server 0.0.0.0)")

    p = sub.add_parser("setlist", aliases=["set"], help="setlists maken en bekijken")
    ssub = p.add_subparsers(dest="scmd")
    q = ssub.add_parser("nieuw", aliases=["new"], help="nieuwe setlist")
    q.add_argument("naam")
    q.add_argument("nummers", nargs="*")
    q = ssub.add_parser("toon", aliases=["show"], help="toon setlist met duur")
    q.add_argument("naam")
    q = ssub.add_parser("maak", aliases=["build"], help="maak PDF's, boek, voorblad en podiumlijst")
    q.add_argument("naam")
    q.add_argument("-a", "--alles", action="store_true")
    ssub.add_parser("lijst", aliases=["list"], help="alle setlists")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 0
    cmd = {"build": "maak", "bouw": "maak", "show": "toon", "info": "toon", "list": "lijst", "ls": "lijst",
           "check": "controleer", "test": "controleer", "new": "nieuw", "library": "bibliotheek",
           "lib": "bibliotheek", "kit": "instrumenten", "instruments": "instrumenten", "archive": "archiveer",
           "restore": "herstel", "convert": "converteer", "watch": "kijk", "set": "setlist",
           "interface": "studio", "ui": "studio", "app": "studio", "fs": "forscore",
           "versie": "versies", "versions": "versies"}.get(args.cmd, args.cmd)
    try:
        return COMMANDS[cmd](project, args) or 0
    except NotationError as e:
        print(f"✗ {e}")
        return 1
    except KeyboardInterrupt:
        return 130


def select(project, refs):
    if not refs:
        return project.song_files()
    out = []
    for r in refs:
        d = project.root / r
        if d.is_dir():                     # een map: alle nummers daarin (ook geparkeerde)
            out += [f for f in project.song_files(include_parked=True) if d.resolve() in f.resolve().parents]
        else:
            out.append(project.find(r))
    return out


# ---------------------------------------------------------------------------
def cmd_build(project, args):
    from .build import build
    paths = select(project, args.nummers)
    if not paths:
        print("Geen nummers gevonden in nummers/. Maak er een met: python3 drums.py nieuw \"Titel\" \"Artiest\"")
        return 1
    res = build(project, paths, force=args.alles, xml_only=args.xml, midi=args.midi)
    bad = [r for r in res if r[2]]
    auto = str(project.config.get("forscore", "")).lower() in ("ja", "automatisch", "auto", "aan")
    if (args.forscore or auto) and not args.xml:
        from .forscore import send
        send(project, [(sc.song, project.out_file("pdf", p, "pdf"), sc) for p, sc, err in res if sc])
    if args.open and not bad:
        for path, _, _ in res:
            _open(project.out_file("pdf", path, "pdf"))
    return 1 if bad else 0


def _open(path):
    import subprocess
    import platform
    if not path.exists():
        return
    s = platform.system()
    if s == "Darwin":
        subprocess.run(["open", str(path)])
    elif s == "Windows":
        import os
        os.startfile(str(path))  # noqa
    else:
        subprocess.run(["xdg-open", str(path)])


def cmd_show(project, args):
    from .build import load_and_arrange
    from .show import show_score
    sc = load_and_arrange(project, project.find(args.nummer))
    show_score(sc)
    for w in sc.warnings:
        print(f"! {w}")


def cmd_list(project, args):
    from .build import load_and_arrange
    rows = []
    for f in project.song_files():
        meta = quick_meta(f)
        if args.zoek and simplify(args.zoek) not in simplify(f.stem + meta.get("title", "") + meta.get("artist", "")):
            continue
        try:
            sc = load_and_arrange(project, f)
            dur = sc.song.get("duration") or fmt_duration(sc.seconds())
            rows.append((project.song_id(f), sc.song.get("title", ""), sc.song.get("artist", ""), str(sc.tempo[0]),
                         str(sc.meter).split(" ")[0], str(sc.total_bars), dur, sc.song.get("status", ""),
                         "✓" if project.out_file("pdf", f, "pdf").exists() else ""))
        except NotationError as e:
            rows.append((project.song_id(f), meta.get("title", ""), meta.get("artist", ""), "", "", "", "", f"FOUT: {e.msg}", ""))
    if not rows:
        print("Geen nummers.")
        return
    head = ("id", "titel", "artiest", "tempo", "maat", "maten", "duur", "status", "pdf")
    w = [max(len(r[i]) for r in rows + [head]) for i in range(len(head))]
    w[1] = min(w[1], 34)
    w[2] = min(w[2], 24)
    fmt = "  ".join(f"{{:<{x}}}" for x in w)
    print(fmt.format(*head))
    print(fmt.format(*("-" * x for x in w)))
    for r in rows:
        print(fmt.format(*(c[:w[i]] for i, c in enumerate(r))))
    print(f"\n{len(rows)} nummers")


def cmd_check(project, args):
    from .build import load_and_arrange
    from .musicxml import to_musicxml
    bad = 0
    for f in select(project, args.nummers):
        try:
            sc = load_and_arrange(project, f)
            to_musicxml(sc, project.config)
            warns = list(sc.warnings)
            song, book, _ = project.load(f)
            for name in book.items:
                if not name.startswith("~"):
                    try:
                        warns += book.warnings(name, sc.meter)
                    except NotationError:
                        pass
            print(f"✓ {project.song_id(f)}: {sc.total_bars} maten, ± {fmt_duration(sc.seconds())}")
            for w in warns:
                print(f"    ! {w}")
        except NotationError as e:
            bad += 1
            print(f"✗ {project.song_id(f)}: {e}")
    return 1 if bad else 0


def cmd_new(project, args):
    from .rows import parse_meter
    m = parse_meter(args.maat)
    from .project import safe_filename
    name = safe_filename(args.id or args.titel).strip(". ") or "nummer"
    from .project import folder_too_deep
    err = folder_too_deep(args.map) if args.map else None
    if err:
        print(f"✗ {err}")
        return 1
    folder = project.songs_dir / args.map if args.map else project.songs_dir
    path = folder / f"{name}.drum"
    sid = project.song_id(path)
    if path.exists():
        print(f"✗ {path.relative_to(project.root)} bestaat al (kies een ander --id)")
        return 1
    key = "6/8" if m.compound else ("3/4" if m.num == 3 else "4/4")
    grooves, sections = TEMPLATES[key]
    feel = args.stijl or ("Ballad in 6/8" if m.compound else "Rechte rock in 8sten")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.format(title=args.titel, artist=args.artiest, tempo=args.tempo, meter=args.maat,
                                    feel=feel, grooves=grooves, sections=sections, sid=sid,
                                    date=datetime.date.today().isoformat()), encoding="utf-8")
    print(f"✓ {path.relative_to(project.root)} gemaakt. Pas het aan en maak de PDF met:")
    print(f'    python3 drums.py maak "{sid}"')


def cmd_midi(project, args):
    from .build import load_and_arrange
    from .midi import build_midi
    out = project.out("midi")
    out.mkdir(parents=True, exist_ok=True)
    for f in select(project, args.nummers):
        sc = load_and_arrange(project, f)
        suffix = f"-{args.tempo}pct" if args.tempo != 100 else ""
        dst = project.out_file("midi", f, "mid", suffix)
        dst.write_bytes(build_midi(sc, tempo_pct=args.tempo, countin=args.aftellen, click=args.klik))
        print(f"✓ {dst.relative_to(project.root)}  ({sc.total_bars} maten, ± "
              f"{fmt_duration(sc.seconds() * 100 / args.tempo)})")


def cmd_library(project, args):
    from .rows import Meter
    from .show import bar_grid
    lib = project.library()
    if args.pdf:
        return library_pdf(project, lib)
    names = [args.naam] if args.naam else sorted(lib.names(), key=lambda n: (lib.get(n).kind != "groove", n))
    kind = None
    for n in names:
        pat = lib.get(n)
        if pat is None:
            raise NotationError(f"patroon '{n}' bestaat niet.{lib.suggest(n)}")
        if pat.kind != kind and not args.naam:
            kind = pat.kind
            print(f"\n==== {'GROOVES' if kind == 'groove' else 'FILLS'} ====")
        bars = lib.compile(n, Meter(4, 4))
        src = "" if (pat.file or "").startswith("<") else f"  [{pat.file}]"
        print(f"\n{n}  ({bars[0].meter}{', ' + str(len(bars)) + ' maten' if len(bars) > 1 else ''})"
              f"  {pat.doc}{src}")
        for b in bars:
            for line in bar_grid(b):
                print(line)


def library_pdf(project, lib):
    """Catalogus van alle patronen als drum sheet (zelfde opmaak)."""
    from .build import build
    lines = ["titel: Bibliotheek", "artiest: Alle grooves en fills", "tempo: 100", "maat: 4/4",
             "stijl: Gebruik in een nummer met de naam uit het kader", "layout: secties", ""]
    for n in sorted(lib.names(), key=lambda n: (lib.get(n).kind != "groove", n)):
        pat = lib.get(n)
        txt = f' "{pat.doc}"' if pat.doc else ""
        meter = f" maat={(pat.meter or '4/4').replace(' ', '')}"
        lines.append(f"[{n}] 1 {n} uitgeschreven{meter}{txt}")
    tmp = project.songs_dir / "_bibliotheek.drum"
    project.songs_dir.mkdir(exist_ok=True)
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        build(project, [tmp], force=True)
        src = project.out("pdf", "_bibliotheek.pdf")
        if src.exists():
            dst = project.out("bibliotheek.pdf")
            shutil.move(str(src), dst)
            print(f"✓ {dst.relative_to(project.root)}")
    finally:
        tmp.unlink()
        for d, ext in (("xml", "musicxml"), ("mscz", "mscz")):
            p = project.out(d, f"_bibliotheek.{ext}")
            if p.exists():
                p.unlink()


def cmd_kit(project, args):
    from .kit import ALIASES, KIT, MODS
    print("INSTRUMENTEN  (code · plek op de balk · nootkop · MIDI · omschrijving · ook bekend als)\n")
    for code, ins in KIT.items():
        al = sorted(a for a, c in ALIASES.items() if c == code)
        print(f"  {code:<5} {ins.step}{ins.octave}  {ins.head:<9} {ins.midi:>3}  {ins.name:<42} {', '.join(al)}")
    print("\n  ST    sticking-rij (R, L, ...) onder de noten\n")
    print("TEKENS in raster of na ':' in telnotatie\n")
    print("  -  .  _   rust")
    for ch, d in MODS.items():
        print(f"  {ch}         {d}")


def cmd_archive(project, args):
    stamp = datetime.date.today().isoformat()
    dest = project.archive_dir / stamp
    for ref in args.nummers:
        f = project.find(ref)
        dest.mkdir(parents=True, exist_ok=True)
        moved = [f]
        shutil.move(str(f), dest / f.name)
        for d, ext in (("pdf", "pdf"), ("mscz", "mscz"), ("xml", "musicxml"), ("midi", "mid")):
            p = project.out(d, f"{project.song_id(f)}.{ext}")
            if p.exists():
                (dest / d).mkdir(exist_ok=True)
                shutil.move(str(p), dest / d / p.name)
                moved.append(p)
        print(f"✓ {f.stem} → {dest.relative_to(project.root)}/ ({len(moved)} bestanden)")


def cmd_restore(project, args):
    cands = [p for p in project.archive_dir.rglob("*") if p.suffix in (".drum", ".py")
             and simplify(p.stem) == simplify(args.nummer) and "songs" not in p.parts and "oud" not in p.parts]
    if not cands:
        cands = [p for p in project.archive_dir.rglob("*") if p.suffix in (".drum", ".py")
                 and simplify(args.nummer) in simplify(p.stem + quick_meta(p).get("title", ""))]
    if not cands:
        raise NotationError(f"'{args.nummer}' niet gevonden in archief/")
    src = sorted(cands)[-1]
    dst = project.songs_dir / src.name
    if dst.exists():
        raise NotationError(f"{dst.relative_to(project.root)} bestaat al")
    project.songs_dir.mkdir(exist_ok=True)
    shutil.copy2(src, dst)
    print(f"✓ {src.relative_to(project.root)} → {dst.relative_to(project.root)}")


def cmd_convert(project, args):
    from .legacy import load_py, to_drum_text
    out = project.root / args.naar
    out.mkdir(parents=True, exist_ok=True)
    for b in args.bestanden:
        src = pathlib.Path(b)
        song, book, _ = load_py(src, project.library())
        dst = out / f"{src.stem}.drum"
        if dst.exists() and not args.overschrijf:
            print(f"= {dst.relative_to(project.root)} bestaat al (gebruik --overschrijf)")
            continue
        dst.write_text(to_drum_text(song, book, f"Omgezet uit {src}"), encoding="utf-8")
        print(f"✓ {src} → {dst.relative_to(project.root)}")


def cmd_watch(project, args):
    from .build import build
    print("Kijkt naar wijzigingen in nummers/ en bibliotheek.drum (Ctrl+C om te stoppen)…")
    seen = {}
    while True:
        paths = select(project, args.nummers)
        lib = project.root / "bibliotheek.drum"
        changed = []
        for p in paths + ([lib] if lib.exists() else []):
            mt = p.stat().st_mtime
            if seen.get(p) != mt:
                if p in seen:
                    changed.append(p)
                seen[p] = mt
        if changed:
            if lib in changed:
                project._library = None
                changed = paths
            print(time.strftime("%H:%M:%S"), "gewijzigd:", ", ".join(p.stem for p in changed))
            build(project, [p for p in changed if p != lib], xml_only=args.xml)
        time.sleep(1)


def cmd_setlist(project, args):
    from . import setlist as sl
    d = project.setlists_dir
    d.mkdir(exist_ok=True)
    sc = getattr(args, "scmd", None)
    if sc in (None, "lijst", "list"):
        files = sorted(d.glob("*.txt"))
        if not files:
            print("Nog geen setlists. Maak er een: python3 drums.py setlist nieuw <naam> [nummers...]")
        for f in files:
            meta, entries = sl.parse_setlist(f.read_text(encoding="utf-8"), f.stem)
            n = sum(1 for e in entries if e.kind == "song")
            print(f"  {f.stem:<24} {meta.get('title', '')}  ({n} nummers) {meta.get('date', '')}")
        return
    name = args.naam
    path = d / (name if name.endswith(".txt") else f"{name}.txt")
    name = path.stem
    if sc in ("nieuw", "new"):
        if path.exists():
            raise NotationError(f"{path.relative_to(project.root)} bestaat al")
        lines = [f"titel: {name}", f"datum: {datetime.date.today().isoformat()}", "plaats: ", "", "[Set 1]"]
        for r in args.nummers:
            f = project.find(r)
            lines.append(project.song_id(f))
        if not args.nummers:
            lines += ["# zet hier per regel een nummer (id of titel), eventueel met | notitie"]
            lines += [project.song_id(f) for f in project.song_files()[:3]]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"✓ {path.relative_to(project.root)} gemaakt")
        return
    if not path.exists():
        raise NotationError(f"setlist '{name}' niet gevonden in setlists/")
    meta, entries = sl.parse_setlist(path.read_text(encoding="utf-8"), name)
    errors = sl.resolve(project, entries, path)
    for e in errors:
        print(f"✗ {e}")
    if errors and sc not in ("toon", "show"):
        return 1
    from .build import build, load_and_arrange
    paths = [e.path for e in entries if e.kind == "song" and e.path]
    scores = {}
    if sc in ("maak", "build"):
        for p, score, _err in build(project, paths, force=args.alles):
            if score:
                scores[str(p)] = score
    else:
        for p in paths:
            try:
                scores[str(p)] = load_and_arrange(project, p)
            except NotationError as err:
                print(f"✗ {err}")
    sl.enrich(project, entries, scores)
    print()
    for line in sl.overview_lines(meta, entries):
        print(line)
    if sc in ("maak", "build"):
        print()
        sl.make_outputs(project, name, meta, entries)


def cmd_forscore(project, args):
    from .build import build
    from . import forscore as fs
    if args.zelftest:
        fs.selftest(project)
        return
    if args.onderzoek:
        from .forscore_db import investigate
        investigate()
        return
    if args.labels_ophalen:
        fs.pull_labels(project, apply=args.toepassen)
        return
    if not args.nummers and not args.setlist:
        fs.sync(project, open_app=not args.geen_open)
        return 0
    if args.nummers:
        paths = select(project, args.nummers)
        res = build(project, paths, log=lambda m: print(m) if m.startswith(("✗", "  !")) else None)
        fs.send(project, [(sc.song, project.out_file("pdf", p, "pdf"), sc) for p, sc, err in res if sc],
                open_app=not args.geen_open, note=args.notitie)
    ok = True
    for name in args.setlist:
        ok = fs.send_setlist(project, name, open_app=not args.geen_open) and ok
    return 0 if ok else 1


def cmd_music(project, args):
    from . import gitsync
    from .project import write_pointer
    if args.actie == "status":
        print(f"Muziekmap: {project.root}" + ("" if project.separate else "  (= de programmamap)"))
        st = gitsync.state(project)
        print("Git: " + ("ja" if st["enabled"] else st["reason"]))
        if st["enabled"]:
            print(f"GitLab: {st.get('remote') or 'nog niet ingesteld (drums.py muziek gitlab <url>)'}")
        return 0
    if args.actie == "gebruik":
        if not args.pad:
            print("✗ geef de map op: drums.py muziek gebruik ~/drumsheetz-muziek")
            return 1
        p = pathlib.Path(args.pad).expanduser().resolve()
        if not (p / "nummers").is_dir() and not (p / "instellingen.txt").exists():
            print(f"✗ {p} lijkt geen muziekmap (geen nummers/ en geen instellingen.txt)")
            return 1
        f = write_pointer(p)
        print(f"✓ Drumsheetz gebruikt nu {p}  (vastgelegd in {f.name})")
        return 0
    if args.actie == "maak":
        if not args.pad:
            print("✗ geef de nieuwe map op: drums.py muziek maak ~/drumsheetz-muziek")
            return 1
        dst = pathlib.Path(args.pad).expanduser().resolve()
        res = gitsync.create_music_dir(project, dst, log=print)
        if res:
            write_pointer(dst)
            print(f"✓ Drumsheetz gebruikt voortaan {dst}")
            print("  De oude nummers in de programmamap blijven (als reserve) staan, maar worden niet meer gebruikt.")
        return 0 if res else 1
    if args.actie == "gitlab":
        if not project.separate:
            print("✗ maak eerst een eigen muziekmap: drums.py muziek maak ~/drumsheetz-muziek")
            return 1
        print(gitsync.set_remote(project, args.pad or "")["log"])
        return 0
    return 1


def cmd_versions(project, args):
    import time as _t
    from . import versions as V
    if args.controleer:
        problems = V.check_all(project)
        for x in problems:
            print(f"✗ {x}")
        print("✓ alle versies zijn in orde" if not problems else f"{len(problems)} probleem/problemen")
        return 1 if problems else 0
    if not args.nummer:
        for f in project.song_files(include_parked=True):
            h = V.history(project, f, attach=False)
            cur = V.content_hash(f.read_text(encoding="utf-8"))
            lat = h.latest
            state = "nog geen versie" if lat is None else (f"V{lat['n']}" + (
                "" if lat["hash"] == cur else f"  (gewijzigd: wordt V{h.next_number(cur)})"))
            print(f"  {project.song_id(f):40} {state}")
        return 0
    f = project.find(args.nummer)
    rel = str(f.relative_to(project.root)).replace("\\", "/")
    if args.nieuw is not None:
        V.create(project, rel, args.nieuw)
        return 0
    if args.terug:
        V.restore(project, rel, args.terug)
        return 0
    if args.verschil:
        a = args.verschil[0]
        b = args.verschil[1] if len(args.verschil) > 1 else "werk"
        d = V.compare(project, rel, a, b)
        print(f"V{a} → {'nu' if b == 'werk' else 'V' + b}: {d['summary']}")
        for kind, line in d["lines"]:
            print(("" if kind == "@" else kind) + line)
        return 0
    i = V.info(project, rel)
    print(f"{i['id']}: " + ("nog geen versies" if not i["versions"] else f"{len(i['versions'])} versie(s)"))
    if i["changed"] and i["latest"]:
        print(f"  nu gewijzigd t.o.v. V{i['latest']} ({i['pending']}): wordt V{i['next']}")
    for v in i["versions"]:
        fs_ = f"  forScore: {v['forscore']}" if v.get("forscore") else ""
        print(f"  V{v['n']:<3} {_t.strftime('%d-%m-%Y %H:%M', _t.localtime(v['time']))}  "
              f"{v.get('note') or v.get('changes') or ''}{fs_}")
    for x in i["problems"]:
        print(f"  ✗ {x}")
    return 0


def cmd_studio(project, args):
    from .studio import serve
    serve(project.root, args.poort, not (args.geen_browser or args.server), server=args.server, host=args.host)


COMMANDS = {"muziek": cmd_music, "versies": cmd_versions, "studio": cmd_studio, "forscore": cmd_forscore, "maak": cmd_build, "toon": cmd_show, "lijst": cmd_list, "controleer": cmd_check, "nieuw": cmd_new,
            "midi": cmd_midi, "bibliotheek": cmd_library, "instrumenten": cmd_kit, "archiveer": cmd_archive,
            "herstel": cmd_restore, "converteer": cmd_convert, "kijk": cmd_watch, "setlist": cmd_setlist}

if __name__ == "__main__":
    sys.exit(main())
