"""De bouwstraat: nummers -> MusicXML -> (MuseScore) -> PDF + MuseScore-bestand, en MIDI."""
import hashlib
import json
import pathlib

from .arrange import arrange
from .musescore import MuseScoreError, find_musescore, render
from .musicxml import to_musicxml
from .rows import NotationError

ENGINE_VERSION = "2.0"


def load_and_arrange(project, path):
    song, book, warns = project.load(path)
    score = arrange(song, book)
    score.warnings = list(warns) + score.warnings
    return score


def build(project, paths, force=False, xml_only=False, midi=False, midi_opts=None, log=print):
    """Bouw de gegeven nummers. Geeft lijst (pad, score|None, fout|None)."""
    out_xml, out_pdf, out_mscz, out_midi = (project.out(d) for d in ("xml", "pdf", "mscz", "midi"))
    for d in (out_xml, out_pdf, out_mscz):
        d.mkdir(parents=True, exist_ok=True)
    cache_file = project.out(".cache.json")
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    results, todo = [], []
    for path in paths:
        sid = project.song_id(path)
        try:
            score = load_and_arrange(project, path)
            xml, offsets = to_musicxml(score, project.config)
        except NotationError as e:
            if not e.file:
                e.file = str(pathlib.Path(path).relative_to(project.root)) if pathlib.Path(path).is_absolute() \
                    else str(path)
            results.append((path, None, e))
            log(f"✗ {sid}: {e}")
            continue
        x = out_xml / f"{sid}.musicxml"
        x.write_text(xml, encoding="utf-8")
        if midi:
            from .midi import build_midi
            out_midi.mkdir(parents=True, exist_ok=True)
            (out_midi / f"{sid}.mid").write_bytes(build_midi(score, **(midi_opts or {})))
        key = hashlib.sha1((ENGINE_VERSION + xml + json.dumps(offsets, sort_keys=True)
                            + json.dumps(project.config, sort_keys=True)).encode()).hexdigest()
        pdf = out_pdf / f"{sid}.pdf"
        fresh = cache.get(sid) == key and pdf.exists()
        results.append((path, score, None))
        for w in score.warnings:
            log(f"  ! {sid}: {w}")
        if xml_only:
            log(f"✓ {sid}: MusicXML ({score.total_bars} maten)")
            continue
        if fresh and not force:
            log(f"= {sid}: al bijgewerkt")
            continue
        todo.append({"id": sid, "xml": x, "offsets": offsets, "pdf": pdf, "mscz": out_mscz / f"{sid}.mscz",
                     "key": key, "score": score})
    if todo:
        ms = find_musescore(project.config.get("musescore", ""))
        if not ms:
            log("! MuseScore niet gevonden: alleen MusicXML gemaakt (uitvoer/xml). Installeer MuseScore 4 of zet "
                "'musescore: /pad/naar/mscore' in instellingen.txt.")
            return results
        log(f"… MuseScore zet {len(todo)} nummer(s) om naar PDF")
        try:
            render(ms, todo, project.config, log)
        except MuseScoreError as e:
            log(f"✗ {e}")
        for it in todo:
            if it["pdf"].exists():
                cache[it["id"]] = it["key"]
                log(f"✓ {it['id']}: {it['score'].total_bars} maten → {it['pdf'].relative_to(project.root)}")
            else:
                log(f"✗ {it['id']}: geen PDF gemaakt")
        cache_file.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    return results
