"""Score -> MusicXML. Volgt de opmaak van de oorspronkelijke drum sheets:
oefenletters in een kader, elke sectie op een nieuwe regel, herhaalmaten (%) met 'N×',
dubbele maatstreep na elke sectie en maatnummers die doortellen na de %-maten."""
from fractions import Fraction as Fr
from xml.sax.saxutils import escape

from .rhythm import divisions_for, voice_events

JUMPS = {
    "fine": "Fine", "tocoda": "To Coda", "ds": "D.S.", "dsalcoda": "D.S. al Coda",
    "dsalfine": "D.S. al Fine", "dc": "D.C.", "dcalcoda": "D.C. al Coda", "dcalfine": "D.C. al Fine",
}
BEAT_UNIT = {Fr(4): ("whole", 0), Fr(2): ("half", 0), Fr(3): ("half", 1), Fr(1): ("quarter", 0),
             Fr(3, 2): ("quarter", 1), Fr(1, 2): ("eighth", 0), Fr(3, 4): ("eighth", 1), Fr(1, 4): ("16th", 0)}


def esc(s):
    return escape(str(s))


class Writer:
    def __init__(self, score, config=None):
        self.score = score
        self.song = score.song
        self.cfg = config or {}
        self.out = []
        self.offsets = {}
        self.counts = []          # maten met een 'N×'-teller bij de %
        self.instr_ids = {}

    def w(self, s):
        self.out.append(s)

    # ------------------------------------------------------------------
    def build(self):
        ms = self.score.measures
        # stemmen uitrekenen
        self.voices = []
        all_ev = []
        voices = str(self.song.get("voices") or self.cfg.get("voices") or "2").strip()
        single = voices in ("1", "een", "één", "one")
        for m in ms:
            if m.bar.rest:
                v1 = voice_events([], m.bar.meter)
                v2 = []
            else:
                hands = [h for h in m.bar.hits if (single or not h.is_foot) and h.instr.code != "ST"]
                feet = [] if single else [h for h in m.bar.hits if h.is_foot]
                v1 = voice_events(hands, m.bar.meter, True)
                v2 = voice_events(feet, m.bar.meter, False)
                if not hands and not feet:
                    v1 = voice_events([], m.bar.meter)
            self.voices.append((v1, v2))
            all_ev += v1 + v2
        self.div = divisions_for(all_ev, [m.bar.meter.length for m in ms])

        used = {}
        for m in ms:
            for h in m.bar.hits:
                if h.instr.code != "ST":
                    used.setdefault(h.instr.code, h.instr)
        self.instr_ids = {}
        n = 0
        midi_used = set()
        for code, ins in used.items():
            n += 1
            self.instr_ids[code] = (f"P1-I{n}", ins)
            midi_used.add(ins.midi)

        self.header()
        self.w('<part id="P1">')
        prev_meter = None
        in_pct = False
        for idx, m in enumerate(ms):
            stop_pct = in_pct and not (m.pct and not m.pct_first)
            if stop_pct:
                in_pct = False
            self.measure(idx, m, prev_meter, stop_pct)
            if m.pct and m.pct_first:
                in_pct = True
            prev_meter = m.bar.meter
            if m.offset:
                self.offsets[idx] = m.offset
        self.w("</part>")
        self.w("</score-partwise>")
        return "\n".join(self.out)

    def header(self):
        s = self.song
        title = s.get("title", "Zonder titel")
        sub = s.get("subtitle") if "subtitle" in s else self.cfg.get("subtitle", "")
        self.subtitle = (sub or "").strip()
        artist = s.get("artist", "")
        name = s.get("by") or self.cfg.get("name", "")
        # vermelding rechtsboven (bv. "Drum sheet: {naam}"): per nummer, anders uit instellingen, anders niets
        credit = s["credit"] if "credit" in s else self.cfg.get("credit", "")
        credit = (credit or "").replace("{naam}", name).replace("{name}", name).strip()
        lines = [artist] if artist else []
        if credit:
            lines += [c.strip() for c in credit.split("\\n") if c.strip()]
        self.w('<?xml version="1.0" encoding="UTF-8"?>')
        self.w('<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
               '"http://www.musicxml.org/dtds/partwise.dtd">')
        self.w('<score-partwise version="4.0">')
        if self.subtitle:
            self.w(f"<work><work-title>{esc(self.subtitle)}</work-title></work>")
        self.w(f"<movement-title>{esc(title)}</movement-title>")
        # linksboven: componist, album/jaar, toonsoort, bron, status (alleen wat is ingevuld)
        left = []
        if s.get("composer"):
            left.append(f"Muziek: {s['composer']}")
        alb = " · ".join(str(x) for x in (s.get("album"), s.get("year")) if x)
        if alb:
            left.append(alb)
        if s.get("key"):
            left.append(f"Toonsoort: {s['key']}")
        if s.get("source"):
            left.append(f"Bron: {s['source']}")
        if s.get("status"):
            left.append(f"Status: {s['status']}")
        if lines or left:
            self.w("<identification>"
                   + ('<creator type="composer">' + "&#10;".join(esc(x) for x in lines) + "</creator>" if lines else "")
                   + ('<creator type="lyricist">' + "&#10;".join(esc(x) for x in left) + "</creator>" if left else "")
                   + "</identification>")
        parts = ['<part-list><score-part id="P1"><part-name>Drums</part-name>'
                 '<part-abbreviation>Dr.</part-abbreviation>']
        for code, (iid, ins) in self.instr_ids.items():
            parts.append(f'<score-instrument id="{iid}"><instrument-name>{esc(ins.name)}</instrument-name>'
                         '</score-instrument>')
        for code, (iid, ins) in self.instr_ids.items():
            if ins.midi:
                parts.append(f'<midi-instrument id="{iid}"><midi-channel>10</midi-channel>'
                             f'<midi-unpitched>{ins.midi + 1}</midi-unpitched></midi-instrument>')
        parts.append("</score-part></part-list>")
        self.w("".join(parts))

    # ------------------------------------------------------------------
    def direction(self, inner, placement="above", sound=""):
        return f'<direction placement="{placement}"><direction-type>{inner}</direction-type>{sound}</direction>'

    def words(self, text, extra="", size=None):
        if size:
            extra += f' font-size="{size}"'
        return self.direction(f'<words font-style="italic"{extra}>{esc(text)}</words>')

    def place(self, key, default):
        v = str(self.song.get(key) or self.cfg.get(key) or default).lower()
        return "below" if v in ("onder", "below") else "above"

    def dyn_dir(self, item):
        """Dynamiekteken. Letters die bij een vork horen staan aan dezelfde kant als de vork."""
        hairpin = len(item) > 2 and item[2] == "hairpin"
        pl = self.place("wedge_pos", "onder") if hairpin else self.place("dyn_pos", "boven")
        return self.direction(f"<dynamics><{esc(item[1])}/></dynamics>", pl)

    def size_of(self, value, key):
        """Tekstgrootte in punten: getal, of klein/normaal/groot; anders uit nummer/instellingen."""
        v = value or self.song.get(key) or self.cfg.get(key)
        if not v:
            return None
        v = str(v).strip().lower().replace(",", ".")
        named = {"klein": 8, "small": 8, "heelklein": 6.5, "normaal": 10, "normal": 10, "groot": 12, "big": 12,
                 "large": 12, "heelgroot": 14}
        if v in named:
            return named[v]
        try:
            return float(v) if "." in v else int(v)
        except ValueError:
            return None

    def tempo_dir(self, tempo):
        bpm, unit = tempo
        name, dot = BEAT_UNIT.get(unit, ("quarter", 0))
        q = float(bpm) * float(unit)
        qs = str(int(q)) if float(q).is_integer() else f"{q:g}"
        return self.direction(f'<metronome parentheses="no"><beat-unit>{name}</beat-unit>'
                              + ("<beat-unit-dot/>" if dot else "") + f"<per-minute>{bpm}</per-minute></metronome>",
                              sound=f'<sound tempo="{qs}"/>')

    def start_dirs(self, m):
        out = []
        for item in m.start:
            k = item[0]
            if k == "tempo":
                out.append(self.tempo_dir(item[1]))
            elif k == "feel":
                feel = self.song.get("feel")
                sw = self.song.get("swing")
                if sw and str(sw).lower() not in ("nee", "no", "0"):
                    feel = (feel + " · " if feel else "") + ("Swing" if str(sw).lower() in ("ja", "yes", "8", "1")
                                                            else f"Swing {sw}")
                fs = self.size_of(None, "feel_size")
                if feel:
                    out.append(self.words(feel, size=fs))
                if self.song.get("notes"):
                    out.append(self.words(self.song["notes"], size=fs))
            elif k == "rehearsal":
                out.append(self.direction(f'<rehearsal enclosure="rectangle">{esc(item[1])}</rehearsal>'))
            elif k == "words":
                size = self.size_of(item[2], "text_size") if len(item) > 2 else None
                out.append(self.words(item[1], size=size))
            elif k == "dyn":
                out.append(self.dyn_dir(item))
            elif k == "wedge":
                out.append(self.direction(f'<wedge type="{item[1]}"/>', self.place("wedge_pos", "onder")))
            elif k == "segno":
                out.append(self.direction("<segno/>", sound='<sound segno="segno"/>'))
            elif k == "coda":
                out.append(self.direction("<coda/>", sound='<sound coda="coda"/>'))
        return out

    def end_dirs(self, m):
        out = []
        for item in m.end:
            if item[0] == "wedge":
                out.append(self.direction('<wedge type="stop"/>', self.place("wedge_pos", "onder")))
            elif item[0] == "dyn":
                out.append(self.dyn_dir(item))
            elif item[0] == "jump":
                txt = JUMPS.get(item[1], item[1])
                if item[1] == "tocoda":
                    out.append(self.direction(f'<words halign="right" font-weight="bold">{txt}</words>'
                                              '</direction-type><direction-type><coda/>'))
                else:
                    out.append(self.direction(f'<words halign="right" font-weight="bold">{esc(txt)}</words>'))
        if m.right_repeat and m.right_repeat > 2:
            out.append(self.direction(f'<words halign="right" font-style="italic">{m.right_repeat}×</words>'))
        return out

    # ------------------------------------------------------------------
    def measure(self, idx, m, prev_meter, stop_pct):
        meter = m.bar.meter
        self.w(f'<measure number="{idx + 1}">')
        if m.new_page and idx:
            self.w('<print new-page="yes"/>')
        elif m.new_system and idx:
            self.w('<print new-system="yes"/>')
        if m.left_repeat or m.ending_start:
            b = '<barline location="left">'
            if m.left_repeat:
                b += "<bar-style>heavy-light</bar-style>"
            if m.ending_start:
                nums = ",".join(map(str, m.ending_start))
                b += f'<ending number="{nums}" type="start">{nums}.</ending>'
            if m.left_repeat:
                b += '<repeat direction="forward"/>'
            self.w(b + "</barline>")
        attrs = ""
        if idx == 0:
            attrs += f"<divisions>{self.div}</divisions><key><fifths>0</fifths></key>"
        if idx == 0 or meter != prev_meter:
            attrs += self.time_xml(meter)
        if idx == 0:
            attrs += "<clef><sign>percussion</sign><line>2</line></clef>"
        if attrs:
            self.w(f"<attributes>{attrs}</attributes>")
        # richtingen aan het begin
        for d in self.start_dirs(m):
            self.w(d)
        style = ""
        if stop_pct:
            style += '<measure-repeat type="stop"/>'
        if m.pct and m.pct_first:
            style += f'<measure-repeat type="start">{m.pct_unit}</measure-repeat>'
        if m.multirest > 1:
            style += f"<multiple-rest>{m.multirest}</multiple-rest>"
        if style:
            self.w(f"<attributes><measure-style>{style}</measure-style></attributes>")
        if m.pct and m.pct_first:
            reps = m.pct // m.pct_unit
            if reps > 1:
                self.w(self.words(f"{reps}×"))
                self.counts.append(idx)
        v1, v2 = self.voices[idx]
        sticking = {h.pos: h.text for h in m.bar.hits if h.instr.code == "ST"}
        self.voice(v1, 1, sticking, m, meter)
        for d in self.end_dirs(m):
            self.w(d)
        if v2 and not m.pct:
            self.w(f"<backup><duration>{self.dur(meter.length)}</duration></backup>")
            rest_stick = {p: t for p, t in sticking.items() if not any(e.start == p and e.hits for e in v1)}
            self.voice(v2, 2, rest_stick, None, meter)
        if m.right_repeat or m.ending_stop or m.barline:
            b = '<barline location="right">'
            if m.right_repeat:
                b += "<bar-style>light-heavy</bar-style>"
            elif m.barline:
                b += f"<bar-style>{m.barline}</bar-style>"
            if m.ending_stop:
                b += f'<ending number="{",".join(map(str, m.ending_stop))}" type="{m.ending_type}"/>'
            if m.right_repeat:
                t = f' times="{m.right_repeat}"' if m.right_repeat > 2 else ""
                b += f'<repeat direction="backward"{t}/>'
            self.w(b + "</barline>")
        self.w("</measure>")

    def time_xml(self, meter):
        return f"<time><beats>{meter.num}</beats><beat-type>{meter.den}</beat-type></time>"

    def dur(self, q):
        v = Fr(q) * self.div
        assert v.denominator == 1, (q, self.div)
        return int(v)

    # ------------------------------------------------------------------
    def voice(self, evs, vno, sticking, m, meter):
        stem = "up" if vno == 1 else "down"
        last_idx = len(evs) - 1
        for ei, e in enumerate(evs):
            fermata = m is not None and m.fermata and ei == last_idx
            if e.is_rest:
                s = "<note>"
                if e.measure_rest:
                    s += f'<rest measure="yes"/><duration>{self.dur(e.dur)}</duration><voice>{vno}</voice>'
                else:
                    s += f"<rest/><duration>{self.dur(e.dur)}</duration><voice>{vno}</voice>"
                    s += f"<type>{e.type}</type>" + "<dot/>" * e.dots
                    s += self.tmod(e)
                nots = self.tuplet_xml(e)
                if fermata:
                    nots += '<fermata type="upright"/>'
                if nots:
                    s += f"<notations>{nots}</notations>"
                self.w(s + "</note>")
                continue
            # voorslagen
            for h in e.hits:
                g = 1 if "f" in h.mods else 2 if "d" in h.mods else 3 if "r" in h.mods else 0
                for gi in range(g):
                    gt = "eighth" if g == 1 else "16th"
                    beam = ""
                    if g > 1:
                        pos = "begin" if gi == 0 else ("end" if gi == g - 1 else "continue")
                        beam = f'<beam number="1">{pos}</beam><beam number="2">{pos}</beam>'
                    slash = ' slash="yes"' if g == 1 else ""
                    self.w(f"<note><grace{slash}/>{self.pitch(h)}<instrument id=\"{self.iid(h)}\"/>"
                           f"<voice>{vno}</voice><type>{gt}</type><stem>{stem}</stem>{beam}"
                           f"{self.head(h, grace=True)}</note>")
            for hi, h in enumerate(e.hits):
                s = "<note>"
                if hi:
                    s += "<chord/>"
                s += self.pitch(h) + f"<duration>{self.dur(e.dur)}</duration>"
                s += f'<instrument id="{self.iid(h)}"/><voice>{vno}</voice>'
                s += f"<type>{e.type}</type>" + "<dot/>" * e.dots + self.tmod(e)
                if "~" in h.mods:
                    s += "<stem>none</stem>"
                else:
                    s += f"<stem>{stem}</stem>"
                s += self.head(h)
                nots = (self.tuplet_xml(e) if hi == 0 else "") + self.notations(h)
                if fermata and hi == 0:
                    nots += '<fermata type="upright"/>'
                if nots:
                    s += f"<notations>{nots}</notations>"
                if hi == 0 and e.start in sticking:
                    s += (f'<lyric number="1" placement="below"><syllabic>single</syllabic>'
                          f"<text>{esc(sticking[e.start])}</text></lyric>")
                self.w(s + "</note>")

    def iid(self, h):
        return self.instr_ids[h.instr.code][0]

    def pitch(self, h):
        return (f"<unpitched><display-step>{h.instr.step}</display-step>"
                f"<display-octave>{h.instr.octave}</display-octave></unpitched>")

    def head(self, h, grace=False):
        head = h.instr.head
        if "g" in h.mods and not grace:
            return f'<notehead parentheses="yes">{head}</notehead>'
        if head == "normal":
            return ""
        return f"<notehead>{head}</notehead>"

    def tmod(self, e):
        if not e.tuplet:
            return ""
        a, n = e.tuplet
        return f"<time-modification><actual-notes>{a}</actual-notes><normal-notes>{n}</normal-notes></time-modification>"

    def tuplet_xml(self, e):
        s = ""
        if e.tuplet and e.tup_start:
            s += '<tuplet type="start" bracket="yes"/>'
        if e.tuplet and e.tup_stop:
            s += '<tuplet type="stop"/>'
        return s

    def notations(self, h):
        md = h.mods
        pos = str(self.song.get("accent_pos") or self.cfg.get("accent_pos") or "boven").lower()
        pl = {"boven": ' placement="above"', "above": ' placement="above"', "onder": ' placement="below"',
              "below": ' placement="below"'}.get(pos, "")
        s = ""
        if "z" in md:
            s += '<ornaments><tremolo type="unmeasured">0</tremolo></ornaments>'
        elif "t" in md:
            s += '<ornaments><tremolo type="single">3</tremolo></ornaments>'
        tech = ""
        if "o" in md:
            tech += f"<open-string{pl}/>"
        if "h" in md:
            tech += f"<half-muted{pl}/>"
        if "+" in md:
            tech += f"<stopped{pl}/>"
        if tech:
            s += f"<technical>{tech}</technical>"
        art = ""
        if ">" in md:
            art += f"<accent{pl}/>"
        if "^" in md:
            art += f'<strong-accent type="up"{pl}/>'
        if "k" in md:
            art += "<breath-mark/>"
        if art:
            s += f"<articulations>{art}</articulations>"
        return s


def to_musicxml(score, config=None):
    w = Writer(score, config)
    xml = w.build()
    offsets = Offsets(w.offsets)
    mode = str(score.song.get("count_pos") or (config or {}).get("count_pos") or "binnen").lower()
    offsets.counts = [] if mode in ("boven", "above") else list(w.counts)
    offsets.count_side = "links" if mode in ("links", "binnen-links", "left") else "rechts"
    offsets.subtitle = w.subtitle
    offsets.accent = str(score.song.get("accent_pos") or (config or {}).get("accent_pos") or "boven").lower()
    return xml, offsets


class Offsets(dict):
    """Maatnummer-verschuivingen, plus de maten waarvan de 'N×' in de balk moet."""
    counts = []
    accent = "boven"
    subtitle = ""
    count_side = "rechts"
