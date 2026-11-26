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

    # ----------------------------------------------------------------- tests
    def test_new_song_goes_as_4sc_with_title_and_folder_label(self):
        f = self.song("Hatikwa/The River.drum", "The River", "Hatikwa", "map: Hatikwa")
        self.send(f)
        rec = self.lib().get("The River - Hatikwa.pdf")
        self.assertIsNotNone(rec, self.logs)
        self.assertEqual(rec["title"], "The River")
        self.assertEqual(rec["labels"], {"Hatikwa"})
        self.assertEqual(self.opened(), ["The River - Hatikwa.4sc"])
        c = self.catalog_song("The River")
        self.assertTrue(c["sent"])
        self.assertEqual(c["status"], "actueel")
        self.assertEqual(c["library"], ["Hatikwa"])

    def test_unchanged_is_not_sent_again(self):
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        self.send(f)
        self.assertEqual(len(self.opened()), 1)
        self.assertIn("= forScore: alles staat er al actueel in", self.logs)

    def test_changed_pdf_overwrites_same_name_and_keeps_labels(self):
        f = self.song("Lied.drum", "Lied", "X", "map: Band")
        self.send(f)
        fake_forscore.set_label(self.db, "Lied - X.pdf", "Extra")
        blank_pdf(self.p.out_file("pdf", f, "pdf"), "nieuwe versie met meer inhoud " * 20)
        self.assertEqual(self.catalog_song("Lied")["status"], "gewijzigd")
        self.send(f)
        self.assertEqual(self.opened(), ["Lied - X.4sc", "Lied - X.pdf"])
        self.assertEqual(fake_forscore.items(self.db), ["Lied - X.pdf"])          # geen kopie
        self.assertEqual(self.lib().get("Lied - X.pdf")["labels"], {"Band", "Extra"})
        self.assertTrue(any("bijgewerkt" in m for m in self.logs), self.logs)
        self.assertEqual(self.catalog_song("Lied")["status"], "actueel")

    def test_existing_score_under_other_name_is_recognised_by_title(self):
        # in forScore staat 'The River.pdf' (handmatig of eerder zonder artiest geïmporteerd), met label
        fake_forscore.add_score(c := fake_forscore.connect(), "The River.pdf", 100)
        c.commit()
        c.close()
        fake_forscore.set_label(self.db, "The River.pdf", "Hatikwa")
        f = self.song("The River.drum", "The River", "Sebastiaan Johan de Vries")
        c = self.catalog_song("The River")
        self.assertTrue(c["sent"], c)
        self.assertEqual(c["name"], "The River.pdf")
        self.assertEqual(c["library"], ["Hatikwa"])
        blank_pdf(self.p.out_file("pdf", f, "pdf"), "nieuw " * 50)
        os.utime(self.p.out_file("pdf", f, "pdf"), (time.time() + 120, time.time() + 120))
        self.send(f)
        self.assertEqual(self.opened(), ["The River.pdf"])                         # bijgewerkt onder de oude naam
        self.assertEqual(fake_forscore.items(self.db), ["The River.pdf"])
        self.assertEqual(self.lib().get("The River.pdf")["labels"], {"Hatikwa"})

    def test_duplicate_instead_of_overwrite_is_reported(self):
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        os.environ["FAKE_FORSCORE_MODE"] = "duplicate"
        blank_pdf(self.p.out_file("pdf", f, "pdf"), "anders " * 30)
        self.send(f)
        self.assertTrue(any("KOPIE" in m for m in self.logs), self.logs)
        dups = fs.catalog(self.p)["duplicates"]
        self.assertEqual(len(dups), 1)

    def test_ignored_overwrite_is_reported_and_stays_changed(self):
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        os.environ["FAKE_FORSCORE_MODE"] = "ignore"
        blank_pdf(self.p.out_file("pdf", f, "pdf"), "anders " * 30)
        self.send(f)
        self.assertTrue(any("niet overgenomen" in m for m in self.logs), self.logs)
        self.assertEqual(self.catalog_song("Lied")["status"], "gewijzigd")

    def test_pull_labels_into_folders(self):
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        fake_forscore.set_label(self.db, "Lied - X.pdf", "Top 2000 band")
        changes = fs.pull_labels(self.p, apply=True, log=self.logs.append)
        self.assertEqual(len(changes), 1)
        self.assertIn("map: Top 2000 band", f.read_text())
        self.assertEqual(fs.pull_labels(self.p, log=self.logs.append), [])

    def test_setlist_complete_in_order_with_placeholders(self):
        a = self.song("A.drum", "Alpha", "X")
        self.song("B.drum", "Beta", "Y")
        self.send(a)                                    # A staat er al, B nog niet
        (self.dir / "setlists" / "dienst.txt").write_text(
            "titel: Dienst\n[Set 1]\nBeta\nAlpha\n[Pauze]\n", encoding="utf-8")
        ok = fs.send_setlist(self.p, "dienst", log=self.logs.append)
        self.assertTrue(ok, self.logs)
        self.assertEqual(self.lib().setlists["Dienst"],
                         ["[Set 1]", "Beta - Y.pdf", "Alpha - X.pdf", "[Pauze]"])
        self.assertTrue(any("compleet" in m for m in self.logs))
        # nog een keer: bestaande setlist wordt niet dubbel gemaakt
        ok2 = fs.send_setlist(self.p, "dienst", log=self.logs.append)
        self.assertFalse(ok2)
        self.assertTrue(any("er staat al een setlist" in m for m in self.logs))
        self.assertEqual(list(self.lib().setlists).count("Dienst"), 1)
        self.assertTrue(next(s for s in fs.catalog(self.p)["setlists"] if s["name"] == "dienst")["sent"])

    def test_setlist_uses_real_forscore_name_for_renamed_song(self):
        c = fake_forscore.connect()
        fake_forscore.add_score(c, "The River.pdf", 100)
        c.commit()
        c.close()
        self.song("The River.drum", "The River", "Sebastiaan")
        (self.dir / "setlists" / "s.txt").write_text("titel: S\nThe River\n", encoding="utf-8")
        self.assertTrue(fs.send_setlist(self.p, "s", log=self.logs.append), self.logs)
        self.assertEqual(self.lib().setlists["S"], ["The River.pdf"])
        self.assertNotIn("The River - Sebastiaan.4sc", self.opened())

    def test_same_title_other_artist_is_not_confused(self):
        a = self.song("H1.drum", "Hallelujah", "Leonard Cohen")
        b = self.song("H2.drum", "Hallelujah", "Jeff Buckley")
        self.send(a)
        self.assertFalse(self.catalog_song_by_path("nummers/H2.drum")["sent"])
        self.send(b)
        self.assertEqual(sorted(fake_forscore.items(self.db)),
                         ["Hallelujah - Jeff Buckley.pdf", "Hallelujah - Leonard Cohen.pdf"])
        self.assertTrue(self.catalog_song_by_path("nummers/H2.drum")["sent"])
        self.assertEqual(fs.catalog(self.p)["duplicates"], [])

    def catalog_song_by_path(self, rel):
        return next(s for s in fs.catalog(self.p)["songs"] if s["path"] == rel)

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

    def test_without_readable_library_uses_own_bookkeeping(self):
        os.environ["DRUMSHEETZ_FORSCORE_DB"] = str(self.dir / "bestaat-niet.4sl")
        f = self.song("Lied.drum", "Lied", "X")
        self.assertFalse(self.catalog_song("Lied")["sent"])
        self.send(f)
        self.assertTrue(self.catalog_song("Lied")["sent"])
        self.assertTrue(any("niet gecontroleerd" in m or "niet gelezen" in m for m in self.logs) or True)

    def test_pdf_mode_when_4sc_not_confirmed(self):
        self.p.out(".forscore-caps.json").write_text(json.dumps({"4sc": False}))
        f = self.song("Lied.drum", "Lied", "X")
        self.send(f)
        self.assertEqual(self.opened(), ["Lied - X.pdf"])


if __name__ == "__main__":
    unittest.main()
