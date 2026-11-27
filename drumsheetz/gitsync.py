"""De muziekmap als git-repo: zien wat er veranderd is, en per stuk of alles in één keer naar GitLab sturen.

Uitgangspunten:
  - Er gaat NIETS automatisch: alleen wat je zelf aanklikt wordt vastgelegd (commit) en verstuurd (push).
  - Zonder GitLab-adres werkt alles ook: dan wordt het alleen lokaal vastgelegd. Later het adres instellen
    (drums.py muziek gitlab <url>, of in de Studio (icoon GitLab, 🔗)) en dan gaat alles wat er nog niet was mee.
  - Bij elkaar wat bij elkaar hoort: een nummer is zijn .drum-bestand plus zijn versiegeschiedenis.
"""
import os
import pathlib
import re
import shutil
import socket
import subprocess

GITIGNORE = """# Drumsheetz muziekmap
uitvoer/
.DS_Store
*.tmp
"""

README = """# Drumsheetz-muziek

Mijn nummers, setlists en versies voor [Drumsheetz](https://github.com/).

- `nummers/`  de nummers (.drum), één map diep (map = label in forScore)
- `setlists/` de setlists
- `versies/`  de versiegeschiedenis (V1, V2, ...): niet met de hand aanpassen
- `archief/`  oude en gekochte PDF's
- `instellingen.txt`, `bibliotheek.drum`

`uitvoer/` (PDF's e.d.) staat niet in git: die maakt Drumsheetz zelf opnieuw.
"""


class GitError(Exception):
    pass


def available():
    return shutil.which("git") is not None


def git(root, *args, check=True, timeout=60):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C", LANG="C")
    try:
        r = subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, text=True,
                           timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise GitError(f"git {args[0]} duurde te lang (> {timeout} s): is de GitLab-server bereikbaar?")
    except OSError as e:
        raise GitError(f"git kon niet starten: {e}")
    if check and r.returncode:
        raise GitError((r.stderr or r.stdout).strip() or f"git {args[0]} mislukt")
    return r


# ---------------------------------------------------------------------------
# toestand

def state(project):
    """Kan de Studio (GitLab) met git werken? {enabled, reason, can_init}"""
    root = pathlib.Path(project.root)
    if not available():
        return {"enabled": False, "can_init": False,
                "reason": "git is niet geïnstalleerd. Op de Mac: xcode-select --install"}
    if not project.separate:
        return {"enabled": False, "can_init": False,
                "reason": "Je muziek staat nog in de programmamap. Maak eerst een eigen muziekmap: "
                          "python3 drums.py muziek maak ~/drumsheetz-muziek"}
    r = git(root, "rev-parse", "--show-toplevel", check=False)
    if r.returncode or pathlib.Path(r.stdout.strip()).resolve() != root.resolve():
        return {"enabled": False, "can_init": True,
                "reason": f"De muziekmap ({root}) is nog geen git-repo."}
    return {"enabled": True, "reason": "", "can_init": False, "remote": remote_url(project)}


def remote_url(project):
    r = git(project.root, "remote", "get-url", "origin", check=False)
    return r.stdout.strip() if not r.returncode else ""


def _has_head(root):
    return not git(root, "rev-parse", "--verify", "-q", "HEAD", check=False).returncode


def _ensure_identity(project):
    """Zonder naam/e-mail weigert git te committen: dan een lokale (alleen voor deze repo)."""
    root = project.root
    if not git(root, "config", "user.name", check=False).stdout.strip():
        git(root, "config", "user.name", project.config.get("name") or "Drumsheetz")
    if not git(root, "config", "user.email", check=False).stdout.strip():
        host = re.sub(r"[^a-z0-9.-]", "", socket.gethostname().lower()) or "localhost"
        git(root, "config", "user.email", f"drumsheetz@{host}")


def init(project, log=print):
    """Van de muziekmap een git-repo maken (met een eerste vastlegging van alles wat er staat)."""
    root = pathlib.Path(project.root)
    if not project.separate:
        raise GitError("de muziek staat nog in de programmamap; maak eerst een eigen muziekmap")
    if (root / ".git").exists():
        raise GitError("de muziekmap is al een git-repo")
    if git(root, "init", "-b", "main", check=False).returncode:
        git(root, "init")
        git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    if not (root / ".gitignore").exists():
        (root / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    _ensure_identity(project)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "Drumsheetz-muziek: begin")
    log(f"✓ git-repo gemaakt in {root}")
    return {"ok": True}


# ---------------------------------------------------------------------------
# wijzigingen

def _parse_porcelain(out):
    """'git status --porcelain=v1 -z' → [(pad, code, oud pad of None)]"""
    items, parts, i = [], out.split("\0"), 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if len(e) < 4:
            continue
        code, path = e[:2], e[3:]
        old = None
        if "R" in code or "C" in code:
            old = parts[i]
            i += 1
        items.append((path, code, old))
    return items


def _kind_of(code):
    if code == "??" or "A" in code:
        return "nieuw"
    if "D" in code:
        return "verwijderd"
    if "R" in code:
        return "verplaatst"
    return "gewijzigd"


def _group(path):
    """Bij welk 'stuk' hoort dit bestand? (soort, sleutel)"""
    parts = path.split("/")
    if parts[0] == "nummers" and path.endswith((".drum", ".py")) and len(parts) > 1:
        return "song", re.sub(r"\.(drum|py)$", "", "/".join(parts[1:]))
    if parts[0] == "versies" and len(parts) > 2:
        if parts[1] == ".setlists":
            stem = re.sub(r"\.json$", "", parts[2])
            return ("other", "versies") if stem.startswith("_") else ("setlist", stem)
        inner = parts[1:-1]
        if inner and inner[-1] == "reserve":
            inner = inner[:-1]
        return "song", "/".join(inner)
    if parts[0] == "setlists" and path.endswith(".txt") and len(parts) == 2:
        return "setlist", parts[1][:-4]
    return "other", parts[0] if len(parts) > 1 else path


def _title(root, path):
    p = pathlib.Path(root) / path
    try:
        head = p.read_text(encoding="utf-8").splitlines()[:40]
    except OSError:
        return ""
    t = a = ""
    for ln in head:
        m = re.match(r"^\s*(titel|title)\s*:\s*(.+?)\s*$", ln, re.I)
        if m:
            t = m.group(2)
        m = re.match(r"^\s*(artiest|artist)\s*:\s*(.+?)\s*$", ln, re.I)
        if m:
            a = m.group(2)
    return f"{t} – {a}" if t and a else t


def _setlist_title(root, stem):
    p = pathlib.Path(root) / "setlists" / f"{stem}.txt"
    try:
        for ln in p.read_text(encoding="utf-8").splitlines()[:20]:
            m = re.match(r"^\s*(titel|title)\s*:\s*(.+?)\s*$", ln, re.I)
            if m:
                return m.group(2)
    except OSError:
        pass
    return stem


def _blob_head(root, path):
    r = git(root, "rev-parse", "-q", "--verify", f"HEAD:{path}", check=False)
    return r.stdout.strip() if not r.returncode else None


def _blob_file(root, path):
    r = git(root, "hash-object", "--", path, check=False)
    return r.stdout.strip() if not r.returncode else None


def changes(project):
    """Alle wijzigingen ten opzichte van de laatste vastlegging, gegroepeerd per nummer/setlist/overig."""
    root = project.root
    raw = _parse_porcelain(git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout)
    groups = {}
    for path, code, old in raw:
        kind, key = _group(path)
        g = groups.setdefault((kind, key), {"kind": kind, "key": f"{kind}:{key}", "name": key, "paths": []})
        g["paths"].append({"path": path, "state": _kind_of(code), "from": old})
        if old:
            okind, okey = _group(old)
            if (okind, okey) != (kind, key):
                g.setdefault("moved_from", okey)
    # een nummer dat verplaatst is (oud weg, nieuw erbij, zelfde inhoud): samenvoegen
    songs = {k: g for (kd, k), g in groups.items() if kd == "song"}

    def main_file(g):
        return next((p for p in g["paths"] if p["path"].startswith("nummers/")), None)
    gone = {k: g for k, g in songs.items() if main_file(g) and main_file(g)["state"] == "verwijderd"}
    new = {k: g for k, g in songs.items() if main_file(g) and main_file(g)["state"] == "nieuw"}
    for nk, ng in new.items():
        nb = _blob_file(root, main_file(ng)["path"])
        for ok, og in list(gone.items()):
            if nb and _blob_head(root, main_file(og)["path"]) == nb:
                ng["paths"] += og["paths"]
                ng["moved_from"] = ok
                del groups[("song", ok)]
                del gone[ok]
                break
    out = []
    for (kind, key), g in groups.items():
        mf = next((p for p in g["paths"] if p["path"].startswith(("nummers/", "setlists/"))), None)
        if g.get("moved_from") and mf:
            old = next((p["path"] for p in g["paths"] if p["state"] == "verwijderd"
                        and p["path"].startswith(("nummers/", "setlists/"))), None)
            if old:
                mf["base"] = old                         # 'bekijk' vergelijkt met het oude bestand
        if g.get("moved_from"):
            st = "verplaatst"
        elif mf:
            st = mf["state"]
        elif kind in ("song", "setlist"):
            st = "versies"
        else:
            st = "gewijzigd" if all(p["state"] == "gewijzigd" for p in g["paths"]) else \
                ("nieuw" if all(p["state"] == "nieuw" for p in g["paths"]) else "gewijzigd")
        g["state"] = st
        g["main"] = mf["path"] if mf else (g["paths"][0]["path"] if len(g["paths"]) == 1 else None)
        g["title"] = _title(root, mf["path"]) if mf and mf["state"] != "verwijderd" and kind == "song" else ""
        if not g["title"] and kind == "song":
            g["title"] = _title(root, f"nummers/{key}.drum") or key.split("/")[-1]
        if not g["title"] and kind == "setlist":
            g["title"] = _setlist_title(root, key)
        g["paths"].sort(key=lambda p: (not p["path"].startswith(("nummers/", "setlists/")), p["path"]))
        out.append(g)
    order = {"song": 0, "setlist": 1, "other": 2}
    out.sort(key=lambda g: (order[g["kind"]], g["name"].lower()))
    return out


def status(project, fetch=False):
    st = state(project)
    if not st["enabled"]:
        return dict(st, items=[], root=str(project.root))
    root = project.root
    info = dict(st, root=str(root), branch="main", ahead=0, behind=0, upstream=False, last=None, fetch_error="")
    if _has_head(root):
        info["branch"] = git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        h, t, s = (git(root, "log", "-1", "--format=%h%x00%ct%x00%s").stdout.strip().split("\0") + ["", "", ""])[:3]
        info["last"] = {"hash": h, "time": int(t or 0), "subject": s}
    if info["remote"] and fetch:
        r = git(root, "fetch", "--quiet", "origin", check=False, timeout=25)
        if r.returncode:
            info["fetch_error"] = (r.stderr or r.stdout).strip()[:300]
    up = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
    if not up.returncode and up.stdout.strip():
        info["upstream"] = True
        cnt = git(root, "rev-list", "--left-right", "--count", "@{u}...HEAD", check=False).stdout.split()
        if len(cnt) == 2:
            info["behind"], info["ahead"] = int(cnt[0]), int(cnt[1])
    elif info["remote"] and info["last"]:
        info["ahead"] = int(git(root, "rev-list", "--count", "HEAD").stdout.strip() or 0)   # nog nooit verstuurd
    info["items"] = changes(project)
    return info


# ---------------------------------------------------------------------------
# versturen

def _message(items, message):
    if message:
        return message
    names = [i.get("title") or i["name"] for i in items]
    if not names:
        return "Drumsheetz: bijgewerkt"
    head = ", ".join(names[:4]) + (f" (+{len(names) - 4})" if len(names) > 4 else "")
    return f"Bijgewerkt: {head}"


def push(project, log=print):
    root = project.root
    if not remote_url(project):
        log("· nog geen GitLab-adres ingesteld: alleen lokaal vastgelegd (stel het adres in in de Studio (icoon GitLab, 🔗) "
            "of met: drums.py muziek gitlab <url>)")
        return False
    up = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
    args = ["push", "--quiet"] if not up.returncode and up.stdout.strip() else ["push", "--quiet", "-u", "origin", "HEAD"]
    r = git(root, *args, check=False, timeout=90)
    if r.returncode:
        log("✗ versturen naar GitLab mislukt: " + (r.stderr or r.stdout).strip()[:400])
        log("  (alles is wel lokaal vastgelegd; probeer het later opnieuw met 'Alles naar GitLab')")
        return False
    log("✓ naar GitLab verstuurd")
    return True


def send(project, keys=None, message="", log=print):
    """Leg de gekozen stukken vast (commit) en stuur ze naar GitLab (push). keys=None: alles."""
    st = state(project)
    if not st["enabled"]:
        raise GitError(st["reason"])
    root = project.root
    items = changes(project)
    if keys is not None:
        want = set(keys)
        items = [i for i in items if i["key"] in want]
        unknown = want - {i["key"] for i in items}
        if unknown and not items:
            log("= niets te versturen (al vastgelegd?)")
    paths = sorted({p["path"] for i in items for p in i["paths"]} |
                   {p["from"] for i in items for p in i["paths"] if p.get("from")})
    if paths:
        _ensure_identity(project)
        git(root, "add", "-A", "--", *paths)
        msg = _message(items, message)
        git(root, "commit", "-q", "-m", msg, "--", *paths)
        log(f"✓ vastgelegd: {msg}  ({len(paths)} bestand(en))")
    elif keys is None:
        log("= geen wijzigingen om vast te leggen")
    if remote_url(project):
        ok = push(project, log)
    else:
        push(project, log)               # meldt dat er nog geen GitLab-adres is
        ok = True
    return {"ok": ok, "committed": len(paths)}


def set_remote(project, url, log=None):
    lines = []
    say = log or lines.append
    st = state(project)
    if not st["enabled"]:
        raise GitError(st["reason"])
    url = (url or "").strip()
    cur = remote_url(project)
    if not url:
        if cur:
            git(project.root, "remote", "remove", "origin")
            say("✓ GitLab-adres weggehaald")
        return {"ok": True, "log": "\n".join(lines)}
    if re.search(r"\s", url):
        raise GitError("een GitLab-adres heeft geen spaties")
    git(project.root, "remote", "set-url" if cur else "add", "origin", url)
    say(f"✓ GitLab-adres: {url}")
    r = git(project.root, "ls-remote", "--heads", "origin", check=False, timeout=15)
    say("✓ GitLab is bereikbaar" if not r.returncode else
        "! GitLab is (nog) niet bereikbaar: " + (r.stderr or r.stdout).strip()[:300])
    return {"ok": True, "log": "\n".join(lines)}


def pull(project, log=print):
    """Ophalen van GitLab (alleen als dat zonder samenvoegen kan)."""
    if not remote_url(project):
        raise GitError("nog geen GitLab-adres ingesteld")
    root = project.root
    r = git(root, "pull", "--ff-only", "--quiet", check=False, timeout=90)
    if r.returncode:
        msg = (r.stderr or r.stdout).strip()
        log("✗ ophalen lukt niet automatisch: " + msg[:400])
        if "overwritten" in msg or "local changes" in msg:
            log("  Er zijn hier wijzigingen die nog niet naar GitLab zijn. Stuur die eerst, en haal daarna op.")
        elif "diverg" in msg or "Not possible to fast-forward" in msg:
            log("  Zowel hier als in GitLab is iets veranderd. Los dat op met git in de muziekmap.")
        return {"ok": False}
    log("✓ opgehaald van GitLab")
    return {"ok": True}


def diff(project, path, base=None):
    """Verschil tussen de laatste vastlegging (van 'base', bij een verplaatst bestand) en wat er nu staat."""
    from .versions import diff as vdiff
    root = pathlib.Path(project.root)
    for x in (path, base):
        if x is not None and (not x or x.startswith("/") or ".." in pathlib.PurePosixPath(x).parts):
            raise GitError("ongeldig pad")
    r = git(root, "show", f"HEAD:{base or path}", check=False)
    old = r.stdout if not r.returncode else ""
    f = root / path
    new = f.read_text(encoding="utf-8", errors="replace") if f.is_file() else ""
    lines = vdiff(old, new)
    plus = sum(1 for k, _ in lines if k == "+")
    minus = sum(1 for k, _ in lines if k == "-")
    what = "nieuw bestand" if r.returncode else ("verwijderd" if not f.exists() else f"+{plus} −{minus} regels")
    return {"lines": lines, "summary": what}


# ---------------------------------------------------------------------------
# muziekmap maken

def create_music_dir(project, dst, log=print):
    """Nieuwe muziekmap met een KOPIE van de muziek uit het huidige project, als git-repo."""
    from .project import MUSIC_ITEMS
    dst = pathlib.Path(dst)
    if dst.exists() and any(dst.iterdir()):
        log(f"✗ {dst} bestaat al en is niet leeg. Kies een nieuwe map, of gebruik hem met: drums.py muziek gebruik {dst}")
        return False
    src = pathlib.Path(project.root)
    if src in dst.parents:
        log("✗ zet de muziekmap niet binnen de programmamap (dan zit hij in de verkeerde git-repo)")
        return False
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in MUSIC_ITEMS:
        s = src / name
        if s.is_dir():
            shutil.copytree(s, dst / name, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc"))
            copied.append(name + "/")
        elif s.is_file():
            shutil.copy2(s, dst / name)
            copied.append(name)
    (dst / "nummers").mkdir(exist_ok=True)
    (dst / "setlists").mkdir(exist_ok=True)
    (dst / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    if not (dst / "README.md").exists():
        (dst / "README.md").write_text(README, encoding="utf-8")
    log(f"✓ muziekmap gemaakt: {dst}")
    log(f"  gekopieerd: {', '.join(copied) or '(niets: lege muziekmap)'}")
    if available():
        from .project import Project
        p = Project(dst)
        try:
            init(p, log=log)
        except GitError as e:
            log(f"! git: {e}")
    else:
        log("! git niet gevonden: de muziekmap is gemaakt, maar nog geen git-repo (xcode-select --install)")
    return True
