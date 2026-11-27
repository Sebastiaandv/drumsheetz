"""Statuspagina: werkt alles? Elke controle geeft (groep, naam, toestand, uitleg, tip).

Toestand: ok (groen), warn (oranje: werkt, maar let op), err (rood: werkt niet), info (grijs).
"""
import os
import pathlib
import platform
import plistlib
import shutil
import subprocess
import sys
import time

FORSCORE_MIN_MACOS = (14, 0)
STARTED = time.time()
_CACHE = {}


def _cached(key, seconds, fn):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < seconds:
        return hit[1]
    val = fn()
    _CACHE[key] = (time.time(), val)
    return val


def _ver(s):
    out = []
    for x in str(s).split("."):
        try:
            out.append(int(x))
        except ValueError:
            break
    return tuple(out)


def _ago(t):
    if not t:
        return "nooit"
    d = int(time.time() - t)
    if d < 90:
        return "zojuist"
    if d < 3600:
        return f"{d // 60} min geleden"
    if d < 86400:
        return f"{d // 3600} uur geleden"
    return time.strftime("%d-%m-%Y %H:%M", time.localtime(t))


def _mac_model():
    try:
        return subprocess.run(["sysctl", "-n", "hw.model"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _musescore_version(path):
    try:
        r = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    import re
    for line in (r.stdout + "\n" + r.stderr).splitlines():       # bv. 'MuseScore4 4.6.3' (geen Qt-meldingen)
        if re.search(r"\b\d+\.\d+(\.\d+)?\b", line) and not line.lower().startswith(("qt.", "warning", "error")):
            return line.strip()
    return ""


def _app_version(app):
    try:
        with open(pathlib.Path(app) / "Contents" / "Info.plist", "rb") as f:
            return plistlib.load(f).get("CFBundleShortVersionString", "")
    except (OSError, ValueError, plistlib.InvalidFileException):
        return ""


def check(project, server=None):
    """Alle controles. server: {'host', 'port', 'server'} van de draaiende Studio."""
    from . import forscore as fs
    from . import gitsync
    from . import versions as V
    from .musescore import find_musescore
    out = []

    def add(group, name, state, detail="", hint=""):
        out.append({"group": group, "name": name, "state": state, "detail": detail, "hint": hint})

    # ---------------------------------------------------------------- systeem
    is_mac = platform.system() == "Darwin"
    macv = platform.mac_ver()[0] if is_mac else ""
    model = _cached("model", 3600, _mac_model) if is_mac else ""
    add("Systeem", "Besturingssysteem", "info",
        (f"macOS {macv}" + (f" · {model}" if model else "")) if is_mac else platform.platform())
    pyv = ".".join(map(str, sys.version_info[:3]))
    add("Systeem", "Python", "ok" if sys.version_info >= (3, 7) else "err", f"{pyv} ({sys.executable})",
        "" if sys.version_info >= (3, 7) else "Drumsheetz heeft Python 3.7 of nieuwer nodig")
    try:
        du = shutil.disk_usage(project.root)
        free = du.free / 1e9
        add("Systeem", "Schijfruimte", "ok" if free > 5 else ("warn" if free > 1 else "err"),
            f"{free:.1f} GB vrij van {du.total / 1e9:.0f} GB", "" if free > 5 else "Maak ruimte vrij")
    except OSError:
        pass
    if server:
        add("Systeem", "Studio", "ok",
            f"draait {_ago(STARTED).replace('zojuist', 'net')} gestart · {server.get('host')}:{server.get('port')}"
            + (" · servermodus (bereikbaar vanuit het thuisnetwerk)" if server.get("server") else " · alleen deze computer"))

    # ---------------------------------------------------------------- Drumsheetz
    from .project import CODE_ROOT
    r = gitsync.git(CODE_ROOT, "log", "-1", "--format=%h · %cd", "--date=format:%d-%m-%Y", check=False) \
        if gitsync.available() and (CODE_ROOT / ".git").exists() else None
    add("Drumsheetz", "Programma", "info", f"{CODE_ROOT}" + (f" · versie {r.stdout.strip()}" if r and not r.returncode else ""),
        "Bijwerken: git pull in de programmamap")
    songs = project.song_files(include_parked=True)
    setl = sorted(project.setlists_dir.glob("*.txt")) if project.setlists_dir.exists() else []
    add("Drumsheetz", "Muziekmap", "ok" if project.separate else "warn",
        f"{project.root} · {len(songs)} nummers, {len(setl)} setlists",
        "" if project.separate else "Je muziek staat nog in de programmamap. Maak een eigen muziekmap: "
                                    "python3 drums.py muziek maak ~/drumsheetz-muziek")
    nested = project.nested_folders()
    add("Drumsheetz", "Mappen", "ok" if not nested else "warn",
        "alle mappen zijn één laag diep" if not nested else f"te diep: {', '.join(nested)}",
        "" if not nested else "forScore kent geen mappen in mappen (map = label). Verplaats deze nummers naar "
                              "een map direct onder nummers/.")
    problems = V.check_all(project)
    nver = sum(1 for _ in V._all_histories(project))
    add("Drumsheetz", "Versies", "ok" if not problems else "err",
        f"{nver} nummer(s) met versies, alle bestanden in orde" if not problems else "; ".join(problems[:5]),
        "" if not problems else "Een versiebestand ontbreekt of is veranderd. Zet het terug uit git of je back-up.")

    # ---------------------------------------------------------------- MuseScore
    ms = find_musescore(project.config.get("musescore", ""))
    if ms:
        ver = _cached(f"ms:{ms}", 600, lambda: _musescore_version(ms))
        add("MuseScore", "MuseScore", "ok", f"{ver or 'gevonden'} · {ms}")
    else:
        add("MuseScore", "MuseScore", "err", "niet gevonden",
            "Installeer MuseScore 4 (op macOS 12: versie 4.6) of zet 'musescore: /pad/naar/mscore' in instellingen.txt")

    # ---------------------------------------------------------------- forScore
    app = fs.find_app() if (is_mac or os.environ.get(fs.TEST_OPEN)) else None
    too_old = is_mac and _ver(macv) < FORSCORE_MIN_MACOS
    if app and app != "test":
        add("forScore", "forScore voor Mac", "ok", f"versie {_app_version(app) or '?'} · {app}")
    elif app == "test":
        add("forScore", "forScore voor Mac", "info", "testmodus (nagemaakte forScore)")
    elif too_old:
        add("forScore", "forScore voor Mac", "err", f"niet mogelijk op macOS {macv}",
            "forScore voor Mac vraagt macOS 14 of nieuwer. Deze Mac kan officieel niet verder dan zijn huidige "
            "macOS; met OpenCore Legacy Patcher kan het (op eigen risico). Tot die tijd: forScore-sync vanaf een "
            "andere Mac.")
    elif is_mac:
        add("forScore", "forScore voor Mac", "err", "niet gevonden",
            "Installeer forScore uit de Mac App Store (zelfde Apple-ID als op de iPad) en zet Sync with iCloud aan")
    else:
        add("forScore", "forScore voor Mac", "info", "alleen op een Mac")
    if app:
        lib = fs.library()
        if lib.ok:
            add("forScore", "Bibliotheek", "ok",
                f"gelezen: {len(lib.scores)} stukken, {len(lib.labels)} labels, {len(lib.setlists)} setlists")
        else:
            add("forScore", "Bibliotheek", "err", "niet te lezen: " + "; ".join(lib.notes)[:300],
                "Geef Python 'Volledige schijftoegang' (Systeeminstellingen › Privacy en beveiliging) en herstart "
                "de Studio. Zonder dit kan Drumsheetz niet controleren wat er in forScore staat.")
        caps = fs.caps(project)
        add("forScore", "Zelftest", "ok" if caps.get("tested") else "warn",
            f"gedaan {_ago(caps.get('tested'))}" + (" · .4sc met gegevens" if caps.get("4sc") else " · alleen PDF")
            if caps.get("tested") else "nog niet gedaan",
            "" if caps.get("tested") else "Draai één keer: python3 drums.py forscore --zelftest")
        last = fs.last_action(project)
        add("forScore", "Laatste sync", "info" if last else "warn",
            f"{_ago(last['time'])} · {last.get('detail', '')}" if last else "nog nooit")
        if fs._HUNG:
            add("forScore", "Hangen", "warn", "forScore bleef hangen op: " + ", ".join(fs._HUNG[-5:]),
                "Kijk op de Mac (Schermdeling) of forScore een vraag stelt, of klik Cancel")
        icloud = list((pathlib.Path.home() / "Library" / "Mobile Documents").glob("*forscore*")) if is_mac else []
        add("forScore", "iCloud", "ok" if icloud else "info",
            "iCloud-map van forScore gevonden" if icloud else "niet gecontroleerd",
            "" if icloud else "Zet in forScore op deze Mac én op de iPad 'Sync with iCloud' aan")

    # ---------------------------------------------------------------- git
    st = gitsync.state(project)
    if not st["enabled"]:
        add("GitLab", "Muziek in git", "warn", st["reason"])
    else:
        info = gitsync.status(project)
        n = len(info["items"])
        add("GitLab", "Muziek in git", "ok" if not n else "info",
            f"branch {info['branch']} · " + ("geen wijzigingen" if not n else f"{n} wijziging(en) nog niet vastgelegd")
            + (f" · laatste: {info['last']['subject']} ({_ago(info['last']['time'])})" if info.get("last") else ""))
        if not info["remote"]:
            add("GitLab", "GitLab-server", "info", "nog niet ingesteld",
                "Later: adres instellen op de Sync-pagina of met drums.py muziek gitlab <url>")
        else:
            try:
                r = gitsync.git(project.root, "ls-remote", "--heads", "origin", check=False, timeout=8)
            except gitsync.GitError as e:
                r = type("R", (), {"returncode": 1, "stderr": str(e), "stdout": ""})()
            reach = not r.returncode
            add("GitLab", "GitLab-server", "ok" if reach else "err",
                f"{info['remote']} · " + ("bereikbaar" if reach else "niet bereikbaar"),
                "" if reach else (r.stderr or r.stdout).strip()[:200])
            if info["ahead"]:
                add("GitLab", "Nog te versturen", "warn", f"{info['ahead']} vastlegging(en) nog niet in GitLab",
                    "Sync-pagina › Alles naar GitLab")
    order = ["ok", "info", "warn", "err"]
    worst = max((order.index(c["state"]) for c in out), default=0)
    return {"checks": out, "overall": order[worst], "time": int(time.time()), "root": str(project.root)}
