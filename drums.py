#!/usr/bin/env python3
"""Drumsheetz — drum sheets uitschrijven, bouwen en setlists maken.

    python3 drums.py help            alle opdrachten
    python3 drums.py maak            alle gewijzigde nummers -> PDF
    python3 drums.py toon <nummer>   nummer als drumtab in de terminal

Alles staat uitgelegd in HANDLEIDING.md.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from drumsheetz.cli import main  # noqa: E402

if __name__ == "__main__":
    from drumsheetz.project import music_root
    args = sys.argv[1:]
    override = None
    if "--muziek" in args:                       # --muziek <pad>: deze muziekmap gebruiken
        i = args.index("--muziek")
        override = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
    if args[:1] in (["help"], ["hulp"]):
        args = ["-h"]
    root = ROOT if args[:1] == ["muziek"] and args[1:2] == ["gebruik"] else music_root(ROOT, override)
    try:
        sys.exit(main(args, root))
    except BrokenPipeError:      # bv. bij '| head'
        sys.exit(0)
