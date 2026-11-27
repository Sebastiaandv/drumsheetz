"""Tests voor de muziekmap, de git-koppeling (Sync-pagina), mapdiepte, toegang en de statuspagina."""
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from drumsheetz import gitsync  # noqa: E402
from drumsheetz import project as P  # noqa: E402
from drumsheetz.project import Project  # noqa: E402

SONG = "titel: {t}\nartiest: X\ntempo: 100\n\n[A] 4 rock\n"
GIT_ENV = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


def run(*args, cwd=None):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, check=True,
                          env=dict(os.environ, **GIT_ENV)).stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="ds-server-"))
        # een 'oude' projectmap met muziek erin (zoals de programmamap nu)
        self.old = self.tmp / "oud"
        (self.old / "nummers" / "Kerk").mkdir(parents=True)
        (self.old / "setlists").mkdir()
        (self.old / "instellingen.txt").write_text("naam: Test\n", encoding="utf-8")
        for rel, t in (("nummers/Alpha.drum", "Alpha"), ("nummers/Kerk/Beta.drum", "Beta")):
            (self.old / rel).write_text(SONG.format(t=t), encoding="utf-8")
        (self.old / "setlists" / "s.txt").write_text("titel: Set\nAlpha\n", encoding="utf-8")
        self.music = self.tmp / "muziek"
        self.logs = []
        self.assertTrue(gitsync.create_music_dir(Project(self.old), self.music, log=self.logs.append), self.logs)
        self.p = self.project()

    def project(self):
        p = Project(self.music)
        p.code_root = self.old            # 'programmamap' = de oude map: de muziek staat dus apart
        return p

    def tearDown(self):
        for x in self.tmp.rglob("*"):
            try:
                os.chmod(x, stat.S_IWRITE | stat.S_IREAD | (stat.S_IEXEC if x.is_dir() else 0))
            except OSError:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class MusicDirTest(Base):
    def test_create_copies_music_and_makes_a_repo(self):
        for rel in ("nummers/Alpha.drum", "nummers/Kerk/Beta.drum", "setlists/s.txt", "instellingen.txt", ".gitignore"):
            self.assertTrue((self.music / rel).exists(), rel)
        self.assertTrue((self.old / "nummers" / "Alpha.drum").exists())           # kopie, niets verplaatst
        self.assertIn("Drumsheetz-muziek: begin", run("git", "log", "--oneline", cwd=self.music))
        self.assertFalse(gitsync.create_music_dir(Project(self.old), self.music, log=self.logs.append))  # niet leeg

    def test_music_root_pointer_env_and_override(self):
        code = self.tmp / "code"
        code.mkdir()
        self.assertEqual(P.music_root(code), code.resolve())                      # zoals vroeger
        P.write_pointer(self.music, code)
        self.assertEqual(P.music_root(code), self.music.resolve())
        os.environ["DRUMSHEETZ_MUZIEK"] = str(self.old)
        try:
            self.assertEqual(P.music_root(code), self.old.resolve())
            self.assertEqual(P.music_root(code, override=str(self.music)), self.music.resolve())
        finally:
            del os.environ["DRUMSHEETZ_MUZIEK"]
        (code / P.POINTER_FILE).write_text(str(self.tmp / "bestaat-niet"), encoding="utf-8")
        with self.assertRaises(SystemExit):
            P.music_root(code)

    def test_not_separate_means_no_git(self):
        p = Project(self.old)
        p.code_root = self.old
        st = gitsync.state(p)
        self.assertFalse(st["enabled"])
        self.assertIn("muziek maak", st["reason"])


class GitTest(Base):
    def items(self):
        return {i["key"]: i for i in gitsync.changes(self.p)}

    def test_changes_are_grouped_per_song_and_moves_are_recognised(self):
        (self.music / "nummers" / "Alpha.drum").write_text(SONG.format(t="Alpha") + "\n[B] 2 rock\n", encoding="utf-8")
        (self.music / "nummers" / "Kerk" / "Beta.drum").rename(self.music / "nummers" / "Beta.drum")
        (self.music / "nummers" / "Gamma.drum").write_text(SONG.format(t="Gamma"), encoding="utf-8")
        v = self.music / "versies" / "Alpha"
        v.mkdir(parents=True)
        (v / "versies.json").write_text("{}", encoding="utf-8")
        it = self.items()
        self.assertEqual(set(it), {"song:Alpha", "song:Beta", "song:Gamma"})
        self.assertEqual(it["song:Alpha"]["state"], "gewijzigd")
        self.assertEqual(sorted(p["path"] for p in it["song:Alpha"]["paths"]),
                         ["nummers/Alpha.drum", "versies/Alpha/versies.json"])
        self.assertEqual((it["song:Beta"]["state"], it["song:Beta"]["moved_from"]), ("verplaatst", "Kerk/Beta"))
        self.assertEqual(it["song:Gamma"]["state"], "nieuw")
        self.assertEqual(it["song:Gamma"]["title"], "Gamma – X")

    def test_send_one_item_commits_only_that(self):
        for t in ("Gamma", "Delta"):
            (self.music / "nummers" / f"{t}.drum").write_text(SONG.format(t=t), encoding="utf-8")
        res = gitsync.send(self.p, ["song:Gamma"], log=self.logs.append)
        self.assertEqual(res["committed"], 1)
        self.assertEqual(set(self.items()), {"song:Delta"})
        self.assertIn("Bijgewerkt: Gamma – X", run("git", "log", "-1", "--format=%s", cwd=self.music))
        self.assertTrue(any("nog geen GitLab-adres" in m for m in self.logs))

    def test_moved_song_is_sent_as_one_move(self):
        (self.music / "nummers" / "Kerk" / "Beta.drum").rename(self.music / "nummers" / "Beta.drum")
        gitsync.send(self.p, ["song:Beta"], log=self.logs.append)
        self.assertEqual(self.items(), {})
        files = run("git", "ls-files", cwd=self.music).split()
        self.assertIn("nummers/Beta.drum", files)
        self.assertNotIn("nummers/Kerk/Beta.drum", files)

    def test_push_to_gitlab_and_pull_back(self):
        remote = self.tmp / "gitlab.git"
        run("git", "init", "-q", "--bare", str(remote))
        out = gitsync.set_remote(self.p, str(remote))
        self.assertIn("bereikbaar", out["log"])
        st = gitsync.status(self.p)
        self.assertEqual((st["remote"], st["ahead"]), (str(remote), 1))        # begin-commit nog niet verstuurd
        (self.music / "nummers" / "Gamma.drum").write_text(SONG.format(t="Gamma"), encoding="utf-8")
        res = gitsync.send(self.p, None, "nieuw nummer", log=self.logs.append)
        self.assertTrue(res["ok"], self.logs)
        st = gitsync.status(self.p, fetch=True)
        self.assertEqual((st["ahead"], st["behind"], st["items"]), (0, 0, []))
        self.assertIn("nieuw nummer", run("git", "log", "--format=%s", "main", cwd=remote))
        # iemand anders (bv. een andere Mac) zet iets in GitLab; hier ophalen
        other = self.tmp / "ander"
        run("git", "clone", "-q", "-b", "main", str(remote), str(other))
        (other / "nummers" / "Delta.drum").write_text(SONG.format(t="Delta"), encoding="utf-8")
        run("git", "add", "-A", cwd=other)
        run("git", "commit", "-q", "-m", "Delta", cwd=other)
        run("git", "push", "-q", cwd=other)
        self.assertEqual(gitsync.status(self.p, fetch=True)["behind"], 1)
        self.assertTrue(gitsync.pull(self.p, log=self.logs.append)["ok"])
        self.assertTrue((self.music / "nummers" / "Delta.drum").exists())

    def test_unreachable_gitlab_keeps_the_commit_locally(self):
        gitsync.set_remote(self.p, str(self.tmp / "bestaat-niet.git"))
        (self.music / "nummers" / "Gamma.drum").write_text(SONG.format(t="Gamma"), encoding="utf-8")
        res = gitsync.send(self.p, None, log=self.logs.append)
        self.assertFalse(res["ok"])
        self.assertTrue(any("lokaal vastgelegd" in m for m in self.logs), self.logs)
        self.assertEqual(self.items(), {})

    def test_diff(self):
        (self.music / "nummers" / "Alpha.drum").write_text(SONG.format(t="Alpha").replace("100", "120"), encoding="utf-8")
        d = gitsync.diff(self.p, "nummers/Alpha.drum")
        self.assertIn(("-", "tempo: 100"), d["lines"])
        self.assertIn(("+", "tempo: 120"), d["lines"])
        with self.assertRaises(gitsync.GitError):
            gitsync.diff(self.p, "../oud/instellingen.txt")


class DepthTest(Base):
    def studio(self):
        from drumsheetz.studio import Studio
        s = Studio(self.music)
        s.code = self.old
        return s

    def test_folder_too_deep(self):
        self.assertIsNone(P.folder_too_deep("Kerk"))
        self.assertIsNone(P.folder_too_deep("nummers/Kerk"))
        self.assertIn("mappen in mappen", P.folder_too_deep("Kerk/Kerst"))

    def test_studio_refuses_nested_folders(self):
        s = self.studio()
        s.mkdir({"path": "nummers/Band"})
        with self.assertRaises(ValueError):
            s.mkdir({"path": "nummers/Band/Sub"})
        with self.assertRaises(ValueError):
            s.mkdir({"path": "setlists/sub"})
        with self.assertRaises(ValueError):                      # map in een map slepen
            s.move({"from": "nummers/Kerk", "to": "nummers/Band/Kerk"})
        s.move({"from": "nummers/Alpha.drum", "to": "nummers/Band/Alpha.drum"})     # nummer in een map: mag
        self.assertTrue((self.music / "nummers" / "Band" / "Alpha.drum").exists())
        with self.assertRaises(ValueError):
            s.new_song({"title": "Diep", "folder": "nummers/Band/Sub"})

    def test_nested_folders_are_reported(self):
        (self.music / "nummers" / "Kerk" / "Kerst").mkdir()
        self.assertEqual(self.p.nested_folders(), ["nummers/Kerk/Kerst"])


class BuilderApiTest(Base):
    def test_songs_and_setlist_info(self):
        from drumsheetz.studio import Studio
        st = Studio(self.music)
        songs = {x["id"]: x for x in st.songs()["songs"]}
        self.assertEqual(songs["Kerk/Beta"]["folder"], "Kerk")
        self.assertEqual((songs["Alpha"]["title"], songs["Alpha"]["bpm"], songs["Alpha"]["meter"]), ("Alpha", "100", "4/4"))
        self.assertGreater(songs["Alpha"]["duration"], 0)
        text = "titel: Set\n# commentaar\n[Set 1]\nAlpha | vol gas\nKerk/Beta [3:00]\nBestaatNiet\n"
        info = st.setlist_info("setlists/s.txt", text)
        e = info["entries"]
        self.assertEqual([x["kind"] for x in e], ["break", "song", "song", "song"])
        self.assertEqual([x["line"] for x in e], [3, 4, 5, 6])
        self.assertEqual((e[1]["path"], e[1]["note"]), ("nummers/Alpha.drum", "vol gas"))
        self.assertEqual(e[2]["duration"], 180)
        self.assertTrue(e[3]["error"])


class AccessTest(unittest.TestCase):
    def allowed(self, ip, server, host="127.0.0.1"):
        import ipaddress
        from drumsheetz.studio import Handler
        h = Handler.__new__(Handler)
        h.client_address = (ip, 1234)
        h.headers = {"Host": host}
        h.server_mode = server
        h.allowed_nets = [ipaddress.ip_network("100.64.0.0/10")]
        return h._local_only()

    def test_local_mode(self):
        self.assertTrue(self.allowed("127.0.0.1", False))
        self.assertFalse(self.allowed("127.0.0.1", False, host="drumsheetz.thuis"))     # DNS-truc
        self.assertFalse(self.allowed("192.168.1.5", False))

    def test_server_mode_only_private_networks(self):
        for ip in ("192.168.1.5", "10.0.0.2", "172.18.0.4", "127.0.0.1", "::1", "100.101.1.1", "::ffff:192.168.1.9"):
            self.assertTrue(self.allowed(ip, True, host="drumsheetz.thuis"), ip)
        for ip in ("8.8.8.8", "2a00:1450::1"):
            self.assertFalse(self.allowed(ip, True, host="drumsheetz.thuis"), ip)


class HealthTest(Base):
    def test_health_runs_and_reports_groups(self):
        from drumsheetz import health
        (self.music / "nummers" / "Kerk" / "Kerst").mkdir()
        d = health.check(self.p, {"host": "0.0.0.0", "port": 8765, "server": True})
        groups = {c["group"] for c in d["checks"]}
        self.assertTrue({"Systeem", "Drumsheetz", "MuseScore", "GitLab"} <= groups, groups)
        mappen = next(c for c in d["checks"] if c["name"] == "Mappen")
        self.assertEqual(mappen["state"], "warn")
        self.assertIn(d["overall"], ("ok", "info", "warn", "err"))


if __name__ == "__main__":
    unittest.main()
