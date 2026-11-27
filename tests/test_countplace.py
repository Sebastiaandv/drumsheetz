"""Tests voor het plaatsen van de 'N×'-tellers bij de %-tekens (drumsheetz/countplace.py)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from drumsheetz import countplace as CP  # noqa: E402

SP = 250.0          # spatium in .mpos-eenheden (maat 1000 hoog = 4 spatiums)


def mpos(measures):
    rows = "".join(f'<element id="{i}" x="{x}" y="{y}" sx="{w}" sy="1000" page="{p}"/>' for i, (x, y, w, p) in enumerate(measures))
    return f"<score><elements>{rows}</elements></score>"


def mscx(n, mm=None, count_in=()):
    """Een minimaal .mscx met n maten op balk 1; mm=(na maat, lengte) voegt een rustgroep-samenvatting toe."""
    ms = []
    for i in range(n):
        body = "<Measure><voice>"
        if i in count_in:
            body += "<StaffText><text><i>3×</i></text></StaffText>"
        ms.append(body + "<Rest/></voice></Measure>")
        if mm and i == mm[0]:
            ms.append(f'<Measure len="16/4"><multiMeasureRest>{mm[1]}</multiMeasureRest><voice><Rest/></voice></Measure>')
    return ("<museScore><Score><Style><Spatium>1.75</Spatium></Style><Part></Part><Staff id=\"1\">"
            + "".join(ms) + "</Staff></Score></museScore>")


class PlanTest(unittest.TestCase):
    def test_centered_above_and_tight_beside(self):
        # regel met drie maten; de middelste (met de teller) loopt van 4000 tot 8000, segment op 4300
        M = [(1000, 5000, 3000, 0), (4000, 5000, 4000, 0), (8000, 5000, 3000, 0)]
        S = [(1900, 5000, 0, 0), (4300, 5000, 0, 0), (8300, 5000, 0, 0)]
        sp_ = mpos([(x, y, 0, p) for x, y, _, p in S])
        text = mscx(3, count_in=(1,))
        for mode, align, x in (("boven", "center", (6000 - 4300) / SP),
                               ("rechts", "left", (6000 + (CP.GLYPH_HALF + CP.GAP) * SP - 4300) / SP),
                               ("links", "right", (6000 - (CP.GLYPH_HALF + CP.GAP) * SP - 4300) / SP)):
            p = CP.plan(text, mpos(M), sp_, {1: (1, "3×")}, mode)[1]
            self.assertEqual(p["align"], align, mode)
            self.assertAlmostEqual(p["x"], x, places=3)
            self.assertEqual(p["need"], 0.0)
        new, n = CP.apply(text, {1: CP.plan(text, mpos(M), sp_, {1: (1, "3×")}, "boven")[1]})
        self.assertEqual(n, 1)
        self.assertIn("<align>center,baseline</align>", new)
        self.assertNotIn("<stretch>", new)

    def test_too_narrow_asks_for_room_and_falls_back_to_above(self):
        M = [(1000, 5000, 3000, 0), (4000, 5000, 1100, 0)]       # maat van 4,4 spatium: '3×' past er niet naast
        S = mpos([(1900, 5000, 0, 0), (4200, 5000, 0, 0)])
        p = CP.plan(mscx(2, count_in=(1,)), mpos(M), S, {1: (1, "3×")}, "rechts")[1]
        self.assertGreater(p["need"], 0)
        a = CP.above(p)
        self.assertEqual((a["align"], a["y"], a["x"]), ("center", CP.Y_ABOVE, p["center"]))
        st = CP.add_stretch(mscx(2, count_in=(1,)), {1: 1.4})
        self.assertIn("<stretch>1.4</stretch>", st)

    def test_multi_measure_rest_shifts_the_numbering(self):
        # bestand: maat 0, samenvatting (4 maten rust), maat 1, 2, 3, dan maat 4 (met teller)
        text = mscx(5, mm=(0, 4), count_in=(4,))
        self.assertEqual(CP.display_map(text), [0, 0, 0, 0, 1])
        M = [(1000, 5000, 6000, 0), (7000, 5000, 4000, 0)]      # getekend: rustgroep + de maat met de teller
        S = mpos([(1500, 5000, 0, 0), (7300, 5000, 0, 0)])
        p = CP.plan(text, mpos(M), S, {4: (1, "3×")}, "boven")
        self.assertAlmostEqual(p[4]["x"], (9000 - 7300) / SP, places=3)

    def test_two_bar_repeat_centers_on_the_middle_barline(self):
        M = [(1000, 5000, 3000, 0), (4000, 5000, 3000, 0), (7000, 5000, 3000, 0)]
        S = mpos([(1900, 5000, 0, 0), (4300, 5000, 0, 0), (7300, 5000, 0, 0)])
        p = CP.plan(mscx(3, count_in=(1,)), mpos(M), S, {1: (2, "4×")}, "boven")[1]
        self.assertAlmostEqual(p["x"], (7000 - 4300) / SP, places=3)      # maatstreep tussen maat 1 en 2

    def test_first_measure_of_a_line_starts_after_the_clef(self):
        M = [(1000, 5000, 5000, 0)]                               # eerste maat van de regel: sleutel/maatsoort ervoor
        S = mpos([(2500, 5000, 0, 0)])
        p = CP.plan(mscx(1, count_in=(0,)), mpos(M), S, {0: (1, "3×")}, "boven")[0]
        x1 = 2500 - CP.LEAD * SP
        self.assertAlmostEqual(p["x"], ((x1 + 6000) / 2 - 2500) / SP, places=3)

    def test_no_positions_gives_none(self):
        self.assertIsNone(CP.plan(mscx(1), "", "", {0: (1, "3×")}, "rechts"))


if __name__ == "__main__":
    unittest.main()
