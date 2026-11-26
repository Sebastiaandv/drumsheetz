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
    args = sys.argv[1:]
    if args[:1] in (["help"], ["hulp"]):
        args = ["-h"]
    try:
        sys.exit(main(args, ROOT))
    except BrokenPipeError:      # bv. bij '| head'
        sys.exit(0)
