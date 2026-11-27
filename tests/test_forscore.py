"""Tests voor de forScore-koppeling tegen een nagemaakte forScore (tests/fake_forscore.py).

Draaien:  python3 -m unittest discover -s tests -v
"""
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import fake_forscore  # noqa: E402
from drumsheetz import forscore as fs  # noqa: E402
from drumsheetz import build as buildmod  # noqa: E402
from drumsheetz.project import Project  # noqa: E402

SONG = """titel: {title}
artiest: {artist}
tempo: 100
{extra}
[A] 4 rock
"""


def blank_pdf(path, marker=""):
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(200, 200)
    w.add_metadata({"/Subject": marker or str(time.time())})
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        w.write(f)


class ForScoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="ds-test-"))
        (self.dir / "nummers").mkdir()
        (self.dir / "setlists").mkdir()
        (self.dir / "instellingen.txt").write_text("naam: Test\n", encoding="utf-8")
        self.db = self.dir / "library.4sl"
        self.log_file = self.dir / "opened.txt"
        self.env = {"DRUMSHEETZ_FORSCORE_DB": str(self.db), "DRUMSHEETZ_FORSCORE_POLL": "0.05",
                    "DRUMSHEETZ_FORSCORE_OPEN": f"{sys.executable} {ROOT / 'tests' / 'fake_forscore.py'}",
                    "FAKE_FORSCORE_LOG": str(self.log_file), "FAKE_FORSCORE_MODE": "overwrite"}
        self.old_env = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        fake_forscore.connect().close()               # lege forScore-bibliotheek
        self.p = Project(self.dir)
        self.p.out().mkdir(parents=True, exist_ok=True)
        self.p.out(".forscore-caps.json").write_text(json.dumps(
            {"4sc": True, "style": "text", "fields": {"title": True, "labels": True, "composer": True}}))
        self.orig_build = buildmod.build
        buildmod.build = self.fake_build
        self.logs = []

    def tearDown(self):
        buildmod.build = self.orig_build
        for k, v in self.old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    # ----------------------------------------------------------------- hulpjes
    def fake_build(self, project, paths, **kw):
        from drumsheetz.build import load_and_arrange
        out = []
        for p in paths:
            pdf = project.out_file("pdf", p, "pdf")
            if not pdf.exists():
                blank_pdf(pdf)
            out.append((p, load_and_arrange(project, p), None))
        return out

    def song(self, rel, title, artist="", extra=""):
        f = self.dir / "nummers" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(SONG.format(title=title, artist=artist, extra=extra), encoding="utf-8")
        blank_pdf(self.p.out_file("pdf", f, "pdf"))
        return f

    def send(self, *files, **kw):
        res = self.fake_build(self.p, list(files))
        return fs.send(self.p, [(sc.song, self.p.out_file("pdf", p, "pdf"), sc) for p, sc, _ in res],
                       log=self.logs.append, **kw)

    def opened(self):
        return self.log_file.read_text().splitlines() if self.log_file.exists() else []

    def lib(self):
        return fs.library()

    def catalog_song(self, title):
        return next(s for s in fs.catalog(self.p)["songs"] if s["title"] == title)

    def edit(self, f, old, new):
        f.write_text(f.read_text().replace(old, new), encoding="utf-8")
        blank_pdf(self.p.out_file("pdf", f, "pdf"))          # 'opnieuw gebouwd'

    def history(self, f):
        from drumsheetz import versions as V
        return V.history(self.p, f, attach=False)

    def modified(self, name):
        return self.lib().get(name)["modified"]

    # ----------------------------------------------------------------- tests
    def test_new_song_goes_as_v1_with_title_and_folder_label(self):
        f = self.song("Hatikwa/The River.drum", "The River", "Hatikwa")     # de map wordt het label
        self.send(f)
        rec = self.lib().get("The River - Hatikwa V1.pdf")
        self.assertIsNotNone(rec, self.logs)
        self.assertEqual(rec["title"], "The River V1")
        self.assertEqual(rec["labels"], {"Hatikwa"})
        self.assertEqual(self.opened(), ["The River - Hatikwa V1.4sc"])
        c = self.catalog_song("The River")
        self.assertEqual((c["sent"], c["status"], c["version"], c["library"]), (True, "actueel", 1, ["Hatikwa"]))
        v = self.history(f).latest
        self.assertEqual((v["n"], v["forscore"], v["sent"]), (1, "The River - Hatikwa V1.pdf", True))
        self.assertTrue((self.history(f).dir / v["pdf"]).exists())

    def test_unchanged_is_not_sent_again(self):
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        self.send(f)
        self.assertEqual(len(self.opened()), 1)
        self.assertIn("= forScore: alles staat er al actueel in", self.logs)

    def test_change_becomes_new_version_and_old_one_is_never_touched(self):
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        before = self.modified("Lied - X V1.pdf")
        self.edit(f, "tempo: 100", "tempo: 120")
        self.assertEqual(self.catalog_song("Lied")["status"], "gewijzigd")
        self.assertEqual(self.catalog_song("Lied")["next"], 2)
        self.send(f)
        self.assertEqual(self.opened(), ["Lied - X V1.4sc", "Lied - X V2.4sc"])
        self.assertEqual(fake_forscore.items(self.db), ["Lied - X V1.pdf", "Lied - X V2.pdf"])
        self.assertEqual(self.modified("Lied - X V1.pdf"), before)         # V1 (met aantekeningen) onaangeroerd
        c = self.catalog_song("Lied")
        self.assertEqual((c["status"], c["version"], c["name"]), ("actueel", 2, "Lied - X V2.pdf"))
        self.assertEqual(c["old_in_forscore"], ["Lied - X V1.pdf"])
        self.assertIn("kop", self.history(f).latest["changes"])

    def test_forscore_only_fields_do_not_make_a_new_version(self):
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        self.edit(f, "tempo: 100", "tempo: 100   \nlabels: Kerst\nwaardering: 4")
        self.assertEqual(self.catalog_song("Lied")["status"], "actueel")
        self.send(f)
        self.assertEqual(len(self.opened()), 1)

    def test_existing_score_is_adopted_as_v1_without_sending(self):
        c = fake_forscore.connect()
        fake_forscore.add_score(c, "The River.pdf", 100)
        c.commit()
        c.close()
        fake_forscore.set_label(self.db, "The River.pdf", "Hatikwa")
        f = self.song("The River.drum", "The River", "Sebastiaan")
        self.assertEqual(self.catalog_song("The River")["status"], "actueel")
        self.send(f)
        self.assertEqual(self.opened(), [])                               # niets verstuurd, niets dubbel
        v = self.history(f).latest
        self.assertEqual((v["n"], v["forscore"], v.get("adopted")), (1, "The River.pdf", True))
        self.edit(f, "tempo: 100", "tempo: 90")
        self.send(f)
        self.assertEqual(fake_forscore.items(self.db), ["The River.pdf", "The River - Sebastiaan V2.pdf"])

    def test_restored_version_reuses_the_old_score_in_forscore(self):
        from drumsheetz import versions as V
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        self.edit(f, "tempo: 100", "tempo: 120")
        self.send(f)
        V.restore(self.p, "nummers/Lied.drum", 1, log=self.logs.append)
        blank_pdf(self.p.out_file("pdf", f, "pdf"))
        self.send(f)
        v = self.history(f).latest
        self.assertEqual((v["n"], v["same_as"], v["forscore"], v["note"]), (3, 1, "Lied - X V1.pdf", "teruggezet naar V1"))
        self.assertEqual(len(self.opened()), 2)                           # V3 = V1: niets nieuws verstuurd
        self.assertEqual(self.catalog_song("Lied")["status"], "actueel")

    def test_without_readable_library_new_songs_are_skipped(self):
        os.environ["DRUMSHEETZ_FORSCORE_DB"] = str(self.dir / "bestaat-niet.4sl")
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        self.assertEqual(self.opened(), [])
        self.assertTrue(any("overgeslagen" in m for m in self.logs))

    def test_duplicate_copy_is_reported(self):
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        c = fake_forscore.connect()
        fake_forscore.add_score(c, "Lied - X V1 2.pdf", 100)
        c.commit()
        c.close()
        self.assertEqual(self.catalog_song("Lied")["dups"], ["Lied - X V1.pdf", "Lied - X V1 2.pdf"])
        todo = fs.sync(self.p, log=self.logs.append)
        self.assertTrue(any("2× in forScore" in t and "Lied - X V1 2.pdf" in t for t in todo), todo)

    def test_pull_labels_into_header(self):
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        fake_forscore.set_label(self.db, "Lied - X V1.pdf", "Top 2000 band")
        changes = fs.pull_labels(self.p, apply=True, log=self.logs.append)
        self.assertEqual(len(changes), 1)
        self.assertIn("labels: Top 2000 band", f.read_text())
        self.assertEqual(fs.pull_labels(self.p, log=self.logs.append), [])
        self.assertEqual(self.catalog_song("Lied")["status"], "actueel")    # labels: maakt geen nieuwe versie

    def test_pull_labels_ignores_folder_label(self):
        f = self.song("Band/Lied.drum", "Lied", "X")
        self.send(f)
        self.assertEqual(fs.pull_labels(self.p, log=self.logs.append), [])

    def test_sync_everything_in_one_go(self):
        self.song("Kerk/Alpha.drum", "Alpha", "X")
        self.song("Band/Beta.drum", "Beta", "Y")
        self.song("_oud/Gamma.drum", "Gamma", "Z")                  # geparkeerd: gaat niet mee
        (self.dir / "setlists" / "dienst.txt").write_text("titel: Dienst\nAlpha\nBeta\n", encoding="utf-8")
        todo = fs.sync(self.p, log=self.logs.append)
        self.assertEqual(todo, [], self.logs)
        lib = self.lib()
        self.assertEqual(lib.get("Alpha - X V1.pdf")["labels"], {"Kerk"})
        self.assertEqual(lib.get("Beta - Y V1.pdf")["labels"], {"Band"})
        self.assertIsNone(lib.get("Gamma - Z V1.pdf"))
        self.assertEqual(lib.setlists["Dienst V1"], ["Alpha - X V1.pdf", "Beta - Y V1.pdf"])
        self.assertIn("\n✓ forScore is gelijk aan Drumsheetz", self.logs)
        n = len(self.opened())
        self.assertEqual(fs.sync(self.p, log=self.logs.append), [])   # tweede keer: niets te doen
        self.assertEqual(len(self.opened()), n)

    def test_setlist_follows_newest_versions_as_new_setlist_version(self):
        a = self.song("A.drum", "Alpha", "X")
        self.song("B.drum", "Beta", "Y")
        (self.dir / "setlists" / "dienst.txt").write_text(
            "titel: Dienst\n[Set 1]\nBeta\nAlpha\n[Pauze]\n", encoding="utf-8")
        fs.sync(self.p, log=self.logs.append)
        self.assertEqual(self.lib().setlists["Dienst V1"],
                         ["[Set 1]", "Beta - Y V1.pdf", "Alpha - X V1.pdf", "[Pauze]"])
        self.edit(a, "tempo: 100", "tempo: 130")
        self.logs.clear()
        fs.sync(self.p, log=self.logs.append)
        sets = self.lib().setlists
        self.assertEqual(sets["Dienst V2"], ["[Set 1]", "Beta - Y V1.pdf", "Alpha - X V2.pdf", "[Pauze]"])
        self.assertIn("Dienst V1", sets)                          # oude setlist blijft gewoon staan
        joined = "\n".join(self.logs)
        self.assertIn("Alpha - X V1 (nieuwste: Alpha - X V2)", joined)
        self.assertIn("setlist Dienst V1 (nieuwste: Dienst V2)", joined)
        st = next(s for s in fs.catalog(self.p)["setlists"] if s["name"] == "dienst")
        self.assertEqual((st["status"], st["version"], st["fs_title"]), ("actueel", 2, "Dienst V2"))

    def test_existing_setlist_is_adopted(self):
        c = fake_forscore.connect()
        fake_forscore.add_score(c, "Alpha.pdf", 100)
        c.commit()
        c.close()
        self.song("A.drum", "Alpha", "X")
        (self.dir / "setlists" / "s.txt").write_text("titel: S\nAlpha\n", encoding="utf-8")
        (self.dir / "s.4ss").write_text(fs.build_4ss("S", [("Alpha", "Alpha.pdf")]), encoding="utf-8")
        old, sys.argv = sys.argv, ["x", str(self.dir / "s.4ss")]
        try:
            fake_forscore.main()
        finally:
            sys.argv = old
        before = len(self.opened())
        fs.sync(self.p, log=self.logs.append)
        self.assertEqual(len(self.opened()), before)               # niets verstuurd
        self.assertEqual(list(self.lib().setlists), ["S"])

    def test_same_title_other_artist_is_not_confused(self):
        a = self.song("H1.drum", "Hallelujah", "Leonard Cohen")
        b = self.song("H2.drum", "Hallelujah", "Jeff Buckley")
        self.send(a)
        self.assertFalse(self.catalog_song_by_path("nummers/H2.drum")["sent"])
        self.send(b)
        self.assertEqual(sorted(fake_forscore.items(self.db)),
                         ["Hallelujah - Jeff Buckley V1.pdf", "Hallelujah - Leonard Cohen V1.pdf"])
        self.assertEqual(fs.catalog(self.p)["duplicates"], [])

    def catalog_song_by_path(self, rel):
        return next(s for s in fs.catalog(self.p)["songs"] if s["path"] == rel)

    def test_moved_song_gives_label_task_not_a_new_version(self):
        self.song("Kerk/Alpha.drum", "Alpha", "X")
        fs.sync(self.p, log=self.logs.append)
        (self.dir / "nummers" / "Band").mkdir()
        (self.dir / "nummers" / "Kerk" / "Alpha.drum").rename(self.dir / "nummers" / "Band" / "Alpha.drum")
        n = len(self.opened())
        todo = fs.sync(self.p, log=self.logs.append)
        self.assertEqual(len(self.opened()), n)                    # zelfde muziek: geen nieuwe versie
        self.assertTrue(any("label toevoegen: Band" in t and "label weghalen: Kerk" in t for t in todo), todo)
        self.assertTrue((self.dir / "versies" / "Band" / "Alpha" / "versies.json").exists())

    def test_catalog_only_forscore_and_counts(self):
        c = fake_forscore.connect()
        fake_forscore.add_score(c, "Los stuk.pdf", 10)
        c.commit()
        c.close()
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        cat = fs.catalog(self.p)
        self.assertTrue(cat["library_ok"])
        self.assertEqual(cat["only_forscore"], ["Los stuk.pdf"])
        self.assertEqual(cat["fs_counts"]["scores"], 2)

    def test_pdf_mode_when_4sc_not_confirmed(self):
        self.p.out(".forscore-caps.json").write_text(json.dumps({"4sc": False}))
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        self.assertEqual(self.opened(), ["Lied - X V1.pdf"])


if __name__ == "__main__":
    unittest.main()
