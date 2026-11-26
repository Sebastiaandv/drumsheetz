from common import FILLS_44, SUB

SONG = {
    "title": "Let Love Rule", "artist": "Lenny Kravitz", "subtitle": SUB,
    "bpm": 90, "meter": (4, 4), "feel": "Vintage soul-rock, laid back",
    "sections": [
        {"label": "Intro", "bars": 8, "groove": "v", "crash": False, "fill": "sd4"},
        {"label": "Couplet 1", "bars": 16, "groove": "v", "crash": False, "fill": "pick8"},
        {"label": "Refrein", "bars": 8, "groove": "ch", "crash": True, "fill": "tom34"},
        {"label": "Couplet 2", "bars": 16, "groove": "v", "fill": "pick8"},
        {"label": "Refrein", "bars": 8, "groove": "ch", "crash": True, "fill": "tom34"},
        {"label": "Brug", "bars": 8, "groove": "br", "crash": True, "fill": "sd34"},
        {"label": "Refrein", "bars": 8, "groove": "ch", "crash": True, "fill": "tomfull"},
        {"label": "Vamp", "text": "gospel-opbouw met blazers en sax", "end": True, "seq": [
            {"groove": "v", "bars": 8, "crash": True, "fill": "sd4"},
            {"groove": "ch", "bars": 8, "crash": True, "fill": "sd34"},
            {"groove": "vamp", "bars": 8, "crash": True, "fill": "tom34"},
            {"groove": "vamp", "bars": 8, "crash": True, "fill": "tomfull"},
            {"groove": "vamp", "bars": 16, "crash": True, "text": "tot fade"},
        ]},
    ],
}

GROOVES = {
    "v":    {"HH": "x-x-x-x-x-x-x-o-", "SD": "----x-------x---", "BD": "x------xx-x-----"},
    "ch":   {"HH": "o-x-o-x-o-x-o-x-", "SD": "----x-------x---", "BD": "x------xx-x-----"},
    "br":   {"RD": "x-x-x-x-x-x-x-x-", "SD": "----x-------x---", "BD": "x-------x-------"},
    "vamp": {"RD": "x-x-x-x-x-x-x-x-", "SD": "----x-------x---", "BD": "x---x---x---x---"},
}
FILLS = FILLS_44
