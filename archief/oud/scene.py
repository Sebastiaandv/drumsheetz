from common import FILLS_44, HIT, SUB

SONG = {
    "title": "Iedereen Is Van De Wereld", "artist": "The Scene", "subtitle": SUB,
    "bpm": 116, "meter": (4, 4), "feel": "Rechte rock in 8sten",
    "sections": [
        {"label": "Intro", "bars": 8, "groove": "ch", "crash": True, "fill": "sd4"},
        {"label": "Couplet 1", "bars": 16, "groove": "v", "fill": "pick8"},
        {"label": "Refrein", "bars": 8, "groove": "ch", "fill": "tom34"},
        {"label": "Couplet 2", "bars": 16, "groove": "v", "fill": "pick8"},
        {"label": "Refrein", "bars": 8, "groove": "ch", "fill": "tom34"},
        {"label": "Brug", "bars": 8, "groove": "br", "fill": "tomfull"},
        {"label": "Refrein", "bars": 8, "groove": "ch", "fill": "tom34"},
        {"label": "Slotrefrein", "seq": [
            {"groove": "bd4", "bars": 8, "text": "meezingen · alleen bassdrum + backbeat", "crash": True,
             "fill": "sd34"},
            {"groove": "ch", "bars": 8, "crash": True, "fill": "tom34"},
        ]},
        {"label": "Outro", "end": True, "seq": [
            {"groove": "ch", "bars": 8, "crash": True, "fill": "tomfull"},
            {"groove": "hit", "bars": 1},
        ]},
    ],
}

GROOVES = {
    "v":   {"HH": "x-x-x-x-x-x-x-x-", "SD": "----x-------x---", "BD": "x-------x-x-----"},
    "ch":  {"HH": "o-o-o-o-o-o-o-o-", "SD": "----x-------x---", "BD": "x-----x-x-x-----"},
    "br":  {"RD": "x-x-x-x-x-x-x-x-", "SD": "----x-------x---", "BD": "x---x---x---x---"},
    "bd4": {"SD": "----x-------x---", "BD": "x---x---x---x---"},
    "hit": HIT,
}
FILLS = FILLS_44
