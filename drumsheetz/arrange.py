"""Van nummer (secties en regels) naar een rij geschreven maten voor de PDF,
en een rij gespeelde maten voor MIDI en duurberekening."""
import re
from dataclasses import dataclass, field
from fractions import Fraction as Fr

from .kit import KIT
from .midi import DYN_VEL
from .patterns import REST_NAMES, SLASH_NAMES, Bar, Hit, rest_bar
from .rows import NotationError, parse_meter


@dataclass
class Measure:
    bar: Bar
    number: int = 1              # echt maatnummer (eerste maat die deze geschreven maat voorstelt)
    pct: int = 0                 # >0: herhaalmaat (%) die voor dit aantal maten staat
    pct_unit: int = 1            # 1, 2 of 4: lengte van het herhaalde stuk
    pct_first: bool = False      # eerste maat van een (meer-maats) herhaalteken
    multirest: int = 0           # eerste maat van een groep rustmaten
    offset: int = 0              # 'tel op bij maatnummer' (MuseScore noOffset)
    start: list = field(default_factory=list)
    end: list = field(default_factory=list)
    new_system: bool = False
    new_page: bool = False
    left_repeat: bool = False
    right_repeat: int = 0        # aantal keer (0 = geen herhaalteken)
    ending_start: tuple = ()
    ending_stop: tuple = ()
    ending_type: str = "stop"    # stop of discontinue
    barline: str = ""            # light-light, light-heavy
    fermata: bool = False
    section: str = ""


@dataclass
class Played:
    bar: Bar
    qpm: float                   # kwartnoten per minuut
    dyn: str = "mf"
    section: str = ""


@dataclass
class Score:
    song: dict
    measures: list
    played: list
    meter: object
    tempo: tuple
    warnings: list = field(default_factory=list)

    @property
    def total_bars(self):
        return len(self.played)

    def seconds(self):
        return sum(float(p.bar.meter.length) * 60.0 / p.qpm for p in self.played)


UNIT_NAMES = {"1": Fr(4), "2": Fr(2), "2.": Fr(3), "4": Fr(1), "4.": Fr(3, 2), "8": Fr(1, 2),
              "8.": Fr(3, 4), "16": Fr(1, 4), "♩": Fr(1), "♩.": Fr(3, 2), "♪": Fr(1, 2), "♪.": Fr(3, 4),
              "q": Fr(1), "q.": Fr(3, 2), "e": Fr(1, 2), "h": Fr(2), "h.": Fr(3)}


def parse_tempo(val, meter):
    """'90' / 90 / '4.=60' / '8=200' -> (bpm, eenheid in kwarten)."""
    if val is None:
        return (120, meter.tempo_unit())
    if isinstance(val, (int, float)):
        return (val, meter.tempo_unit())
    s = str(val).strip().replace(" ", "")
    m = re.fullmatch(r"(?:([0-9.♩♪qeh]+)=)?(\d+(?:\.\d+)?)", s)
    if not m:
        raise NotationError(f"tempo '{val}' niet begrepen (voorbeelden: 90, 4.=60, 8=200)")
    bpm = float(m.group(2))
    bpm = int(bpm) if bpm.is_integer() else bpm
    if m.group(1):
        if m.group(1) not in UNIT_NAMES:
            raise NotationError(f"tempo-eenheid '{m.group(1)}' onbekend (gebruik 4, 4., 8, 2)")
        return (bpm, UNIT_NAMES[m.group(1)])
    return (bpm, meter.tempo_unit())


def qpm(tempo):
    return float(tempo[0]) * float(tempo[1])


# ---------------------------------------------------------------------------
def dedupe(hits):
    d = {}
    for h in hits:
        d[(h.pos, h.instr.code, h.text)] = h
    return tuple(sorted(d.values(), key=lambda h: (h.pos, -h.instr.staff_index, h.instr.code)))


def merge_fill(groove, fill):
    """Fill over de groove: alles vanaf de eerste handslag van de fill komt uit de fill.
    Heeft de fill geen voeten, dan loopt de bassdrum/hi-hat-voet van de groove door."""
    if fill.meter != groove.meter or groove.rest:
        return fill
    hands = [h.pos for h in fill.hits if not h.is_foot and h.instr.code != "ST"]
    start = min(hands) if hands else (min(h.pos for h in fill.hits) if fill.hits else groove.meter.length)
    has_feet = any(h.is_foot for h in fill.hits)
    keep = [h for h in groove.hits if h.pos < start or (h.is_foot and not has_feet)]
    return Bar(groove.meter, dedupe(keep + list(fill.hits)))


def add_crash(bar, code, kit):
    if bar.rest:
        return bar
    cr = kit.get(code) or KIT.get(code) or KIT["CR"]
    keep = [h for h in bar.hits if not (h.pos == 0 and h.instr.group in ("hh", "cymbal")
                                         and not h.is_foot) and not (h.pos == 0 and h.instr.code == "SL")]
    return Bar(bar.meter, dedupe(keep + [Hit(Fr(0), cr)]))


def slash_bar(meter):
    sl = KIT["SL"]
    return Bar(meter, tuple(Hit(p, sl, frozenset({"~"})) for p, _ in meter.beats()))


def click_bar(meter):
    ck = KIT["CK"]
    return Bar(meter, tuple(Hit(p, ck) for p, _ in meter.beats()))


# ---------------------------------------------------------------------------
class Arranger:
    def __init__(self, song, book):
        self.song, self.book = song, book
        self.meter = parse_meter(song.get("meter", (4, 4)))
        self.tempo = parse_tempo(song.get("bpm", 120), self.meter)
        self.measures, self.played, self.warnings = [], [], []
        self.bar_no = 1
        self.pending_offset = 0
        self.dyn = "mf"
        self.pending_dyn = None      # eindletter van een vork: komt op de eerste tel na de vork

    def err(self, msg, obj):
        return NotationError(msg, obj.get("_line") if isinstance(obj, dict) else None,
                             self.song.get("_file"))

    # ------------------------------------------------------------------
    def build_bars(self, ph, meter):
        groove = ph.get("groove")
        n = int(ph.get("bars", 1) or 0)
        if n < 1:
            raise self.err("aantal maten moet minstens 1 zijn", ph)
        fills = ph.get("fill") or []
        if isinstance(fills, str):
            fills = [f for f in fills.split(",") if f]
        if groove in REST_NAMES and not self.book.get(str(groove)):
            bars = [rest_bar(meter)] * n
        elif str(groove).lower() in SLASH_NAMES and not self.book.get(str(groove)):
            bars = [slash_bar(meter)] * n
        else:
            try:
                pat = self.book.compile(groove, meter)
            except NotationError as e:
                if e.line is None:
                    raise self.err(e.msg, ph)
                raise
            bars = [pat[i % len(pat)] for i in range(n)]
        unit = self.unit_len(groove, meter)
        if fills:
            fbars = []
            for f in fills:
                try:
                    fbars += self.book.compile(f, bars[-1].meter)
                except NotationError as e:
                    raise self.err(e.msg, ph) if e.line is None else e
            fbars = fbars[-n:]
            for j, fb in enumerate(fbars):
                idx = n - len(fbars) + j
                bars[idx] = merge_fill(bars[idx], fb)
        keys = [b.key() for b in bars]      # crash telt niet mee voor de %-herhaling (zoals vroeger)
        if ph.get("crash"):
            code = ph["crash"] if isinstance(ph["crash"], str) else "CR"
            bars[0] = add_crash(bars[0], code, self.book.kit)
        return bars, unit, keys

    def unit_len(self, groove, meter):
        if groove in REST_NAMES or not self.book.get(str(groove)):
            return 1
        try:
            return len(self.book.compile(groove, meter))
        except NotationError:
            return 1

    # ------------------------------------------------------------------
    def emit_phase(self, bars, unit, written, section_label, keys=None):
        """Schrijf maten met %-compressie. Geeft de lijst nieuwe Measure-objecten."""
        out = []
        keys = keys or [b.key() for b in bars]
        compress = self.song.get("compress", True) and not written
        i, n = 0, len(bars)

        def add(bar, **kw):
            m = Measure(bar, number=self.bar_no, section=section_label, **kw)
            if self.pending_offset:
                m.offset = self.pending_offset
                self.pending_offset = 0
            out.append(m)
            return m

        while i < n:
            b = bars[i]
            if b.rest:
                j = i
                while j < n and bars[j].rest:
                    j += 1
                cnt = j - i
                for k in range(cnt):
                    add(b, multirest=cnt if k == 0 else 0)
                    self.bar_no += 1
                i = j
                continue
            if compress and unit in (2, 4) and i + 2 * unit <= n and \
                    keys[i:i + unit] == keys[i + unit:i + 2 * unit]:
                r = 1
                while i + (r + 2) * unit <= n and keys[i:i + unit] == \
                        keys[i + (r + 1) * unit:i + (r + 2) * unit]:
                    r += 1
                for k in range(unit):
                    add(bars[i + k])
                    self.bar_no += 1
                for k in range(unit):
                    add(bars[i + k], pct=r * unit, pct_unit=unit, pct_first=(k == 0))
                self.bar_no += r * unit
                self.pending_offset += r * unit - unit
                i += unit * (1 + r)
                continue
            add(b)
            self.bar_no += 1
            j = i + 1
            if compress:
                while j < n and keys[j] == keys[i]:
                    j += 1
            cnt = j - i - 1
            if cnt >= 1:
                add(b, pct=cnt, pct_unit=1, pct_first=True)
                self.bar_no += cnt
                self.pending_offset += cnt - 1
            i = j
        return out

    # ------------------------------------------------------------------
    def arrange(self):
        song = self.song
        layout = str(song.get("layout", "secties")).lower()
        flow = layout in ("doorlopend", "flow", "compact")
        meter, tempo = self.meter, self.tempo
        first = True

        if song.get("countin"):
            ms = []
            for k in range(int(song["countin"])):
                ms += self.emit_phase([click_bar(meter)], 1, True, "")
            ms[0].start += [("tempo", tempo), ("feel",)]
            ms[0].start.append(("words", "aftellen"))
            for m in ms:
                self.played.append(Played(m.bar, qpm(tempo), "mf", "aftellen"))
            ms[-1].barline = "light-light"
            self.measures += ms
            first = False

        sections = song.get("sections", [])
        if not sections:
            raise NotationError("het nummer heeft geen secties", None, song.get("_file"))
        for si, sec in enumerate(sections):
            phases = sec.get("seq") or [sec]
            label = sec.get("label", "")
            sec_ms = []
            sec_played = []           # [(phase, played list)]
            if sec.get("meter"):
                meter = parse_meter(sec["meter"])
            for pi, ph in enumerate(phases):
                if ph is not sec and ph.get("meter"):
                    meter = parse_meter(ph["meter"])
                bars, unit, keys = self.build_bars(ph, meter)
                # tempo-eenheid volgt de maatsoort van de maten zelf (ook als het patroon die bepaalt)
                if pi == 0 and sec.get("tempo"):
                    tempo = parse_tempo(sec["tempo"], bars[0].meter)
                if ph is not sec and ph.get("tempo"):
                    tempo = parse_tempo(ph["tempo"], bars[0].meter)
                ms = self.emit_phase(bars, unit, ph.get("written") or sec.get("written"), label, keys)
                if not ms:
                    continue
                st = ms[0].start
                if pi == 0:
                    if si == 0 and first:
                        st += [("tempo", tempo), ("feel",)]
                    elif sec.get("tempo"):
                        st.append(("tempo", tempo))
                    if label:
                        st.append(("rehearsal", label))
                    if sec.get("text") and ph is not sec:
                        st.append(("words", sec["text"], sec.get("text_size")))
                    for mk in sec.get("marks", []) if ph is not sec else []:
                        if mk in ("segno", "coda"):
                            st.append((mk,))
                    if not first and not flow and sec.get("newline", True):
                        ms[0].new_system = True
                    if sec.get("newpage"):
                        ms[0].new_page = True
                if ph is not sec and ph.get("tempo") and not (pi == 0 and (sec.get("tempo") or (si == 0 and first))):
                    st.append(("tempo", tempo))
                if ph.get("tempo_text"):
                    st.append(("words", ph["tempo_text"]))
                for mk in ph.get("marks", []):
                    if mk in ("segno", "coda"):
                        st.append((mk,))
                if ph.get("text"):
                    st.append(("words", ph["text"], ph.get("text_size") or sec.get("text_size")))
                if self.pending_dyn and not ph.get("dyn"):
                    st.append(("dyn", self.pending_dyn, "hairpin"))
                    self.dyn = self.pending_dyn
                self.pending_dyn = None
                start_vel = DYN_VEL.get(self.dyn, 85) if isinstance(self.dyn, str) else self.dyn
                if ph.get("dyn"):
                    st.append(("dyn", ph["dyn"], "hairpin" if ph.get("wedge") else ""))
                    self.dyn = ph["dyn"]
                    start_vel = DYN_VEL.get(self.dyn, 85)
                if ph.get("wedge"):
                    st.append(("wedge", ph["wedge"]))
                    ms[-1].end.append(("wedge", "stop"))
                    if ph.get("dyn_end"):
                        self.pending_dyn = ph["dyn_end"]
                if ph.get("newline") and pi > 0:
                    ms[0].new_system = True
                if ph.get("newpage") and pi > 0:
                    ms[0].new_page = True
                for mk in ph.get("marks", []):
                    if mk not in ("segno", "coda"):
                        ms[-1].end.append(("jump", mk))
                if ph.get("fermata"):
                    ms[-1].fermata = True
                if ph.get("repeat") and ph is not sec:
                    ms[0].left_repeat = True
                    ms[-1].right_repeat = int(ph["repeat"])
                volta = ph.get("volta") if ph is not sec else None
                if volta:
                    ms[0].ending_start = tuple(volta)
                    ms[-1].ending_stop = tuple(volta)
                if ph.get("wedge"):     # MIDI: geleidelijk harder/zachter over de vork
                    up = ph["wedge"] == "crescendo"
                    end_vel = DYN_VEL.get(ph.get("dyn_end"), start_vel + (18 if up else -18))
                    nb = len(bars)
                    pl = [Played(b, qpm(tempo), int(start_vel + (end_vel - start_vel) * k / max(1, nb - 1 if nb > 1 else 1)),
                                 label) for k, b in enumerate(bars)]
                    if not ph.get("dyn_end"):
                        self.dyn = max(20, min(127, end_vel))
                else:
                    pl = [Played(b, qpm(tempo), self.dyn, label) for b in bars]
                sec_played.append((ph, pl))
                sec_ms += ms
                first = False
            if not sec_ms:
                continue
            for mk in sec.get("marks", []) if sec.get("seq") else []:
                if mk not in ("segno", "coda"):
                    sec_ms[-1].end.append(("jump", mk))
            self.repeats(sec, sec_ms, sec_played)
            if not sec_ms[-1].right_repeat:
                is_end = sec.get("end") or any(ph.get("end") for ph in phases if ph is not sec)
                sec_ms[-1].barline = "light-heavy" if is_end and si < len(sections) - 1 else "light-light"
            self.measures += sec_ms

        if self.pending_dyn and self.measures:
            self.measures[-1].end.append(("dyn", self.pending_dyn, "hairpin"))
        if self.measures:
            last = self.measures[-1]
            if not last.right_repeat:
                last.barline = "light-heavy"
        bpl = int(song.get("bars_per_line") or 0)
        if bpl:
            cnt = 0
            for m in self.measures:
                if m.new_system or m.new_page:
                    cnt = 0
                if m.pct and not m.pct_first:
                    continue
                if cnt == bpl:
                    m.new_system = True
                    cnt = 0
                cnt += 1
        return Score(song, self.measures, self.played, self.meter, self.tempo, self.warnings)

    def repeats(self, sec, sec_ms, sec_played):
        """Herhalingen en volta's: herhaaltekens zetten en de gespeelde volgorde uitrollen."""
        def rep(ph, pl):
            return pl * max(1, int(ph.get("repeat") or 1)) if ph is not sec else pl

        voltas = [(ph, pl) for ph, pl in sec_played if ph.get("volta") and ph is not sec]
        sec_rep = int(sec.get("repeat") or 0)
        if voltas:
            passes = max(max(max(ph["volta"]) for ph, _ in voltas), sec_rep)
            pre, vol, post = [], [], []
            for ph, pl in sec_played:
                if ph.get("volta"):
                    vol.append((ph, pl))
                elif not vol:
                    pre.append((ph, pl))
                else:
                    post.append((ph, pl))
            sec_ms[0].left_repeat = True
            last_v = tuple(voltas[-1][0]["volta"])
            for m in sec_ms:
                if m.ending_stop:
                    if m.ending_stop == last_v:
                        m.ending_type = "discontinue"
                    else:
                        m.right_repeat = passes
            for p in range(1, passes + 1):
                for ph, pl in pre:
                    self.played += rep(ph, pl)
                for ph, pl in vol:
                    if p in ph["volta"]:
                        self.played += rep(ph, pl)
            for ph, pl in post:
                self.played += rep(ph, pl)
            return
        if sec_rep:
            sec_ms[0].left_repeat = True
            sec_ms[-1].right_repeat = sec_rep
            once = []
            for ph, pl in sec_played:
                once += rep(ph, pl)
            self.played += once * sec_rep
            return
        for ph, pl in sec_played:
            self.played += rep(ph, pl)


def arrange(song, book):
    return Arranger(song, book).arrange()
