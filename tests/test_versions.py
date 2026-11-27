"""Tests voor het versiebeheer (drumsheetz/versions.py)."""
import os
import pathlib
import shutil
import stat
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from drumsheetz import versions as V  # noqa: E402
from drumsheetz.project import Project  # noqa: E402

SONG = """titel: Lied
artiest: X
tempo: 100
labels: Kerk

[Intro] 2 rock
[Refrein] 4 rock
"""


class VersionTest(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="ds-versie-"))
        (self.dir / "nummers").mkdir()
        (self.dir / "instellingen.txt").write_text("naam: Test\n", encoding="utf-8")
        self.f = self.dir / "nummers" / "Lied.drum"
        self.f.write_text(SONG, encoding="utf-8")
        self.p = Project(self.dir)
        self.rel = "nummers/Lied.drum"

    def tearDown(self):
        for p in self.dir.rglob("*"):
            try:
                os.chmod(p, stat.S_IWRITE | stat.S_IREAD | (stat.S_IEXEC if p.is_dir() else 0))
            except OSError:
                pass
        shutil.rmtree(self.dir, ignore_errors=True)

    def add(self, note=""):
        h = V.history(self.p, self.f)
        return h.add(self.f.read_text(encoding="utf-8"), note=note)

    def test_normalize_ignores_forscore_fields_and_spaces(self):
        a = V.content_hash(SONG)
        self.assertEqual(a, V.content_hash(SONG.replace("labels: Kerk", "labels: Band\ngenre: pop")
                                           .replace("tempo: 100", "tempo: 100   ") + "\n\n"))
        self.assertNotEqual(a, V.content_hash(SONG.replace("tempo: 100", "tempo: 101")))

    def test_summary_names_the_changed_sections(self):
        s = V.summarize(SONG, SONG.replace("[Refrein] 4 rock", "[Refrein] 8 rock"))
        self.assertEqual(s, "+1 −1 regels: deel Refrein")
        self.assertEqual(V.summarize(SONG, SONG.replace("labels: Kerk", "")), "geen muzikale wijzigingen")

    def test_version_files_are_read_only_and_checked(self):
        v = self.add()
        h = V.history(self.p, self.f)
        p = h.dir / v["file"]
        self.assertFalse(os.access(p, os.W_OK) and os.geteuid() != 0)
        self.assertEqual(h.check(), [])
        os.chmod(p, 0o644)
        p.write_text("geknoeid", encoding="utf-8")
        self.assertTrue(any("is veranderd" in x for x in V.check_all(self.p)))

    def test_create_restore_and_backup(self):
        self.add("eerste")
        self.f.write_text(SONG.replace("tempo: 100", "tempo: 120"), encoding="utf-8")
        self.add()
        werk = SONG.replace("tempo: 100", "tempo: 140")           # nog niet vastgelegd
        self.f.write_text(werk, encoding="utf-8")
        i = V.info(self.p, self.rel)
        self.assertEqual((i["changed"], i["latest"], i["next"]), (True, 2, 3))
        V.restore(self.p, self.rel, 1, log=lambda m: None)
        self.assertEqual(self.f.read_text(encoding="utf-8"), SONG)
        h = V.history(self.p, self.f)
        self.assertEqual(len(h.data["backups"]), 1)                # het werk van daarnet is bewaard
        self.assertEqual((h.dir / h.data["backups"][0]["file"]).read_text(encoding="utf-8"), werk)
        v3 = h.add(self.f.read_text(encoding="utf-8"))
        self.assertEqual((v3["n"], v3["same_as"], v3["note"]), (3, 1, "teruggezet naar V1"))
        V.restore_backup(self.p, self.rel, h.data["backups"][0]["file"], log=lambda m: None)
        self.assertEqual(self.f.read_text(encoding="utf-8"), werk)

    def test_compare(self):
        self.add()
        self.f.write_text(SONG.replace("[Intro] 2 rock", "[Intro] 4 rock"), encoding="utf-8")
        d = V.compare(self.p, self.rel, 1)
        self.assertIn(("-", "[Intro] 2 rock"), d["lines"])
        self.assertIn(("+", "[Intro] 4 rock"), d["lines"])

    def test_note_can_be_changed_but_content_cannot(self):
        self.add()
        V.set_note(self.p, self.rel, 1, "voor de kerstdienst")
        self.assertEqual(V.history(self.p, self.f).get(1)["note"], "voor de kerstdienst")

    def test_history_follows_studio_move(self):
        from drumsheetz.studio import Studio
        self.add()
        Studio(self.dir).move({"from": self.rel, "to": "nummers/Kerk/Lied"})
        self.assertTrue((self.dir / "versies" / "Kerk" / "Lied" / "versies.json").exists())
        self.assertFalse((self.dir / "versies" / "Lied").exists())
        h = V.history(self.p, self.dir / "nummers" / "Kerk" / "Lied.drum")
        self.assertEqual(len(h.versions), 1)

    def test_history_is_found_after_move_outside_the_studio(self):
        self.add()
        (self.dir / "nummers" / "Band").mkdir()
        new = self.dir / "nummers" / "Band" / "Mijn lied.drum"
        self.f.rename(new)
        h = V.history(self.p, new)
        self.assertEqual(len(h.versions), 1)
        self.assertTrue((self.dir / "versies" / "Band" / "Mijn lied" / "versies.json").exists())

    def test_version_number_on_the_sheet(self):
        from drumsheetz.build import load_and_arrange
        from drumsheetz.musicxml import to_musicxml
        sc = load_and_arrange(self.p, self.f)
        self.assertEqual(sc.song["_version"], 1)
        self.add()
        self.f.write_text(SONG.replace("tempo: 100", "tempo: 90"), encoding="utf-8")
        sc = load_and_arrange(self.p, self.f)
        self.assertEqual(sc.song["_version"], 2)
        self.assertIn("Versie V2", to_musicxml(sc, self.p.config)[0])
        (self.dir / "instellingen.txt").write_text("naam: Test\nversie-op-blad: nee\n", encoding="utf-8")
        self.assertNotIn("_version", load_and_arrange(Project(self.dir), self.f).song)


if __name__ == "__main__":
    unittest.main()
